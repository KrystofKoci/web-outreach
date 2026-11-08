"""Tiny JSON HTTP API for n8n (stdlib only, no FastAPI).

Authentication: ``Authorization: Bearer <API_TOKEN>`` on every endpoint except
``GET /health``.  When ``API_TOKEN`` is empty the server refuses to start.

Endpoints (all JSON in / JSON out):

``GET  /health``                      liveness + public settings
``GET  /previews``                    registry of published previews
``POST /search``    {query | city+category, country, limit, market?, lang?}
``POST /audit``     {url}
``POST /process``   {lead:{...}, market?, lang?, force?, screenshots?}
``POST /plan_day``  {queue:[...], weights:{...}|[...], target?, skip_rate?}
``POST /learn``     {leads:[...], deals:[...], outcomes:[...]}
``POST /cleanup``   {older_than_days?, keep_statuses?, statuses?, dry_run?}

Error bodies: ``{"ok": false, "error": "<česky>"}``.  Logs go to stdout.
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

from . import __version__, audit, deploy_preview, learn, places_search, run
from .config import Settings, get_settings

log = logging.getLogger("pipeline.api")

MAX_BODY = 8 * 1024 * 1024


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# handlers (pure functions: body dict -> response dict) - easy to unit test
# ---------------------------------------------------------------------------
def handle_health(s: Settings) -> Dict[str, Any]:
    return {"ok": True, "version": __version__, "settings": s.as_public_dict()}


def handle_previews(s: Settings, body: Optional[dict] = None) -> Dict[str, Any]:
    include_demo = bool((body or {}).get("include_demo", True))
    return {"ok": True, "previews": deploy_preview.list_previews(s, include_demo=include_demo)}


def handle_search(s: Settings, body: dict) -> Dict[str, Any]:
    country = str(body.get("country") or body.get("region") or "").upper()
    limit = int(body.get("limit") or body.get("max_results") or 20)
    if s.is_blocked(country):
        raise ApiError(400, s.block_reason(country))
    query = body.get("query")
    if not query:
        city, category = body.get("city"), body.get("category")
        if not (city and category):
            raise ApiError(400, "Zadejte 'query' nebo dvojici 'city' + 'category'.")
        query = f"{category} {city}"
    try:
        out = places_search.search_places(
            str(query), region=country, language=str(body.get("language") or ""), max_results=limit,
            market=body.get("market"), lang=body.get("lang"), category=str(body.get("category") or ""),
            settings=s)
    except places_search.PlacesError as exc:
        raise ApiError(502, str(exc))
    out["ok"] = True
    return out


def handle_audit(s: Settings, body: dict) -> Dict[str, Any]:
    url = str(body.get("url") or "").strip()
    if not url:
        raise ApiError(400, "Chybí 'url'.")
    res = audit.audit_website(url, s, with_pagespeed=bool(body.get("pagespeed", True)))
    out = res.summary()
    out["ok"] = True
    return out


def handle_process(s: Settings, body: dict) -> Dict[str, Any]:
    lead = body.get("lead") if isinstance(body.get("lead"), dict) else body
    if not lead or not lead.get("name"):
        raise ApiError(400, "Chybí 'lead' s polem 'name'.")
    out = run.process_lead(
        lead, market=body.get("market"), lang=body.get("lang"), force=bool(body.get("force", False)),
        settings=s, with_screenshots=bool(body.get("screenshots", True)), with_llm=bool(body.get("llm", True)),
        with_images=bool(body.get("images", True)), with_pagespeed=bool(body.get("pagespeed", True)),
        owner_note=str(body.get("owner_note") or ""))
    out["ok"] = True
    return out


def handle_plan_day(s: Settings, body: dict) -> Dict[str, Any]:
    queue = body.get("queue") or body.get("queue_rows") or []
    if not isinstance(queue, list):
        raise ApiError(400, "'queue' musí být pole řádků {country, city, category, ...}.")
    plan = learn.plan_day(queue, body.get("weights"), int(body.get("target") or body.get("target_previews") or 30),
                          float(body.get("skip_rate", 0.5)), settings=s)
    return {"ok": True, "plan": plan, "count": len(plan), "total_limit": sum(p["limit"] for p in plan)}


def handle_learn(s: Settings, body: dict) -> Dict[str, Any]:
    for key in ("leads", "deals", "outcomes"):
        if key in body and not isinstance(body[key], list):
            raise ApiError(400, f"'{key}' musí být pole.")
    out = learn.compute_weights(body.get("leads") or [], body.get("deals") or [], body.get("outcomes") or [])
    out["ok"] = True
    return out


def handle_cleanup(s: Settings, body: dict) -> Dict[str, Any]:
    keep = body.get("keep_statuses") or deploy_preview.DEFAULT_KEEP_STATUSES
    out = deploy_preview.cleanup(int(body.get("older_than_days") or 60), keep, body.get("statuses") or {},
                                 include_demo=bool(body.get("include_demo", False)),
                                 dry_run=bool(body.get("dry_run", False)), settings=s)
    out["ok"] = True
    return out


def handle_status(s: Settings, body: dict) -> Dict[str, Any]:
    slug, status = str(body.get("slug") or ""), str(body.get("status") or "")
    if not (slug and status):
        raise ApiError(400, "Chybí 'slug' nebo 'status'.")
    return {"ok": deploy_preview.set_status(slug, status, s), "slug": slug, "status": status}


ROUTES = {
    ("GET", "/health"): handle_health,
    ("GET", "/previews"): handle_previews,
    ("POST", "/previews"): handle_previews,
    ("POST", "/search"): handle_search,
    ("POST", "/audit"): handle_audit,
    ("POST", "/process"): handle_process,
    ("POST", "/plan_day"): handle_plan_day,
    ("POST", "/learn"): handle_learn,
    ("POST", "/cleanup"): handle_cleanup,
    ("POST", "/status"): handle_status,
}


def dispatch(method: str, path: str, body: Optional[dict], token: Optional[str], s: Settings) -> Tuple[int, dict]:
    """Route one request. Returns ``(http_status, json_body)``."""
    path = path.split("?", 1)[0].rstrip("/") or "/"
    handler = ROUTES.get((method, path))
    if handler is None:
        return 404, {"ok": False, "error": f"Neznámá cesta {method} {path}."}
    if path != "/health":
        if not s.api_token:
            return 500, {"ok": False, "error": "API_TOKEN není nastaven - server odmítá požadavky."}
        if token != s.api_token:
            return 401, {"ok": False, "error": "Neplatný nebo chybějící token (Authorization: Bearer ...)."}
    try:
        if method == "GET":
            return 200, handler(s) if path == "/health" else handler(s, body or {})
        return 200, handler(s, body or {})
    except ApiError as exc:
        return exc.status, {"ok": False, "error": exc.message}
    except Exception as exc:          # noqa: BLE001
        log.error("Neošetřená chyba %s %s: %s", method, path, traceback.format_exc())
        return 500, {"ok": False, "error": f"Interní chyba: {exc}"}


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = f"web-outreach/{__version__}"
    settings: Settings = None  # type: ignore[assignment]

    def log_message(self, fmt, *args):        # route to logging instead of stderr
        log.info("%s %s", self.address_string(), fmt % args)

    def _token(self) -> Optional[str]:
        auth = self.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return self.headers.get("X-Api-Token") or None

    def _read_body(self) -> Optional[dict]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return None
        if length > MAX_BODY:
            raise ApiError(413, "Tělo požadavku je příliš velké.")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "Tělo požadavku není platný JSON.")
        if not isinstance(data, dict):
            raise ApiError(400, "Tělo požadavku musí být JSON objekt.")
        return data

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, method: str) -> None:
        try:
            body = self._read_body() if method == "POST" else None
        except ApiError as exc:
            self._send(exc.status, {"ok": False, "error": exc.message})
            return
        status, payload = dispatch(method, self.path, body, self._token(), self.settings or get_settings())
        self._send(status, payload)

    def do_GET(self):   # noqa: N802
        self._handle("GET")

    def do_POST(self):  # noqa: N802
        self._handle("POST")


def serve(settings: Optional[Settings] = None) -> None:
    s = settings or get_settings()
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not s.api_token:
        log.error("API_TOKEN není nastaven - nastavte ho v prostředí a spusťte znovu.")
        raise SystemExit(2)
    Handler.settings = s
    httpd = ThreadingHTTPServer((s.api_host, s.api_port), Handler)
    httpd.daemon_threads = True
    log.info("web-outreach API %s naslouchá na %s:%d (previews: %s)", __version__, s.api_host, s.api_port, s.preview_dir)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
