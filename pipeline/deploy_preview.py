"""Publishing previews.

Caddy (see ``infra/``) serves ``PREVIEW_DIR`` as ``https://nahled.krystofkoci.com/``
with ``file_server``; nothing needs to be "deployed" - :func:`publish` only
makes sure the directory is complete and world-readable, updates the
``PREVIEW_DIR/index.json`` registry and returns the public URLs.

:func:`cleanup` deletes previews older than N days unless their status (as
reported by n8n from the CRM) is in ``keep_statuses`` - called by n8n through
``POST /cleanup`` from the monthly housekeeping workflow.

:func:`publish_cloudflare_pages` is a stub for a later static-hosting option.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import Settings, get_settings

log = logging.getLogger("pipeline.deploy")

DEFAULT_KEEP_STATUSES = ("replied", "offer_sent", "won", "customer", "interested", "demo", "in_progress", "negotiating")
REQUIRED_FILES = ("index.html",)
OPTIONAL_FILES = ("meta.json", "compare.png", "og.png", "new_mobile.png", "old_mobile.png")


def _registry_path(s: Settings) -> Path:
    return s.preview_dir / "index.json"


def load_registry(settings: Optional[Settings] = None) -> Dict[str, dict]:
    s = settings or get_settings()
    p = _registry_path(s)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        log.warning("index.json je poškozený - začínám s prázdným registrem")
        return {}


def save_registry(reg: Dict[str, dict], settings: Optional[Settings] = None) -> None:
    s = settings or get_settings()
    s.preview_dir.mkdir(parents=True, exist_ok=True)
    tmp = _registry_path(s).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, _registry_path(s))
    try:
        os.chmod(_registry_path(s), 0o644)
    except OSError:
        pass


def _ensure_perms(directory: Path) -> None:
    try:
        os.chmod(directory, 0o755)
        for f in directory.iterdir():
            if f.is_file():
                os.chmod(f, 0o644)
    except OSError as exc:
        log.warning("Nelze nastavit práva pro %s: %s", directory, exc)


def preview_urls(slug: str, directory: Path, s: Settings) -> Dict[str, str]:
    base = s.preview_url(slug)
    out = {"preview_url": base}
    for name, key in (("compare.png", "compare_png_url"), ("og.png", "og_png_url"),
                      ("new_mobile.png", "new_mobile_png_url"), ("old_mobile.png", "old_mobile_png_url")):
        out[key] = base + name if (directory / name).exists() else ""
    return out


def publish(slug: str, *, status: str = "built", extra: Optional[dict] = None,
            settings: Optional[Settings] = None) -> Dict[str, str]:
    """Validate ``PREVIEW_DIR/<slug>``, fix permissions, register and return URLs."""
    s = settings or get_settings()
    directory = s.preview_dir / slug
    if not directory.is_dir():
        raise FileNotFoundError(f"Náhled {slug} neexistuje v {s.preview_dir}")
    for req in REQUIRED_FILES:
        if not (directory / req).exists():
            raise FileNotFoundError(f"Náhled {slug}: chybí {req}")
    _ensure_perms(directory)
    meta: dict = {}
    mp = directory / "meta.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except ValueError:
            meta = {}
    reg = load_registry(s)
    entry = reg.get(slug, {})
    entry.update({
        "slug": slug,
        "name": meta.get("name", entry.get("name", "")),
        "lead_id": meta.get("lead_id", entry.get("lead_id", "")),
        "country": meta.get("country", entry.get("country", "")),
        "industry": meta.get("industry", entry.get("industry", "")),
        "lang": meta.get("lang", entry.get("lang", "")),
        "demo": bool(meta.get("demo", entry.get("demo", False))),
        "status": status or entry.get("status", "built"),
        "built_at": meta.get("built_at", entry.get("built_at", "")),
        "published_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "url": s.preview_url(slug),
    })
    if extra:
        entry.update(extra)
    reg[slug] = entry
    save_registry(reg, s)
    log.info("Published %s -> %s", slug, entry["url"])
    return preview_urls(slug, directory, s)


def set_status(slug: str, status: str, settings: Optional[Settings] = None) -> bool:
    """Update the status of one preview in the registry (n8n syncs CRM statuses here)."""
    s = settings or get_settings()
    reg = load_registry(s)
    if slug not in reg:
        return False
    reg[slug]["status"] = status
    reg[slug]["status_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    save_registry(reg, s)
    return True


def list_previews(settings: Optional[Settings] = None, include_demo: bool = True) -> List[dict]:
    s = settings or get_settings()
    reg = load_registry(s)
    rows = []
    for slug, entry in reg.items():
        if not include_demo and entry.get("demo"):
            continue
        d = s.preview_dir / slug
        row = dict(entry)
        row["exists"] = d.is_dir()
        rows.append(row)
    rows.sort(key=lambda r: r.get("published_at", ""), reverse=True)
    return rows


def _dir_age_days(directory: Path, built_at: str, now: datetime) -> float:
    if built_at:
        try:
            dt = datetime.fromisoformat(built_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (now - dt).total_seconds() / 86400
        except ValueError:
            pass
    try:
        return (now - datetime.fromtimestamp(directory.stat().st_mtime, tz=timezone.utc)).total_seconds() / 86400
    except OSError:
        return 0.0


def cleanup(older_than_days: int = 60, keep_statuses: Iterable[str] = DEFAULT_KEEP_STATUSES,
            statuses: Optional[Dict[str, str]] = None, *, include_demo: bool = False, dry_run: bool = False,
            settings: Optional[Settings] = None) -> Dict[str, object]:
    """Delete previews older than ``older_than_days`` unless their status must be kept.

    ``statuses`` maps slug -> current CRM status (n8n passes it); it overrides
    the registry.  Demo pages are kept unless ``include_demo``.  Directories
    without a registry entry are judged by mtime.
    """
    s = settings or get_settings()
    now = datetime.now(timezone.utc)
    keep = {k.strip().lower() for k in keep_statuses}
    statuses = {k: (v or "").lower() for k, v in (statuses or {}).items()}
    reg = load_registry(s)
    deleted, kept, errors = [], [], []
    if not s.preview_dir.is_dir():
        return {"deleted": [], "kept": [], "errors": [], "older_than_days": older_than_days}
    for d in sorted(s.preview_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
            continue
        slug = d.name
        entry = reg.get(slug, {})
        is_demo = bool(entry.get("demo")) or slug.startswith("demo-")
        if is_demo and not include_demo:
            kept.append({"slug": slug, "why": "demo"})
            continue
        status = statuses.get(slug, entry.get("status", "")).lower()
        if status in keep:
            kept.append({"slug": slug, "why": f"status={status}"})
            continue
        age = _dir_age_days(d, entry.get("built_at", ""), now)
        if age < older_than_days:
            kept.append({"slug": slug, "why": f"age={age:.0f}d"})
            continue
        if dry_run:
            deleted.append({"slug": slug, "age_days": round(age), "dry_run": True})
            continue
        try:
            shutil.rmtree(d)
            reg.pop(slug, None)
            deleted.append({"slug": slug, "age_days": round(age)})
        except OSError as exc:
            errors.append({"slug": slug, "error": str(exc)})
    if not dry_run:
        save_registry(reg, s)
    log.info("Cleanup: smazáno %d, ponecháno %d, chyb %d", len(deleted), len(kept), len(errors))
    return {"deleted": deleted, "kept": kept, "errors": errors, "older_than_days": older_than_days,
            "cutoff": (now - timedelta(days=older_than_days)).isoformat()}


def publish_cloudflare_pages(slug: str, settings: Optional[Settings] = None) -> Dict[str, object]:
    """Placeholder for a future Cloudflare Pages / R2 deployment.

    Not wired to n8n.  Returns a structured "not implemented" answer instead
    of raising so a future caller can detect it.
    """
    s = settings or get_settings()
    return {"ok": False, "provider": "cloudflare_pages", "slug": slug,
            "message": "Nasazení na Cloudflare Pages zatím není implementováno; náhledy servíruje Caddy z PREVIEW_DIR.",
            "url": s.preview_url(slug)}
