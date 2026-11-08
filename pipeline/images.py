"""Hero / section imagery for previews.

* With ``PEXELS_API_KEY``: one landscape photo per preview from the Pexels
  search API (free, 200 req/h, attribution appreciated).  We hot-link the
  ``large2x`` URL (allowed by Pexels), add the photographer credit as an HTML
  comment and a small footer line.
* Without a key (or on any error): a per-industry CSS gradient + inline SVG
  motif and a dashed "Vaše fotografie" / "Your photos" placeholder, so the
  owner immediately sees where their real photos go.

Nothing here raises - the worst case is the placeholder.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import requests

from . import industries
from .config import Settings, get_settings

log = logging.getLogger("pipeline.images")

PEXELS_URL = "https://api.pexels.com/v1/search"

PLACEHOLDER_LABEL = {"cs": "Vaše fotografie", "en": "Your photos"}
PLACEHOLDER_HINT = {"cs": "Sem patří fotky z vaší provozovny – dodáte je vy, nebo je nafotím.",
                    "en": "Photos of your place go here – you supply them or I take them."}
CREDIT_LABEL = {"cs": "Ilustrační foto", "en": "Stock photo"}

# subtle decorative motifs per industry (inline SVG, currentColor so they inherit the brand colour)
_MOTIFS: Dict[str, str] = {
    "remeslo": '<svg viewBox="0 0 120 120" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="3" d="M10 110 60 60m0 0 20-20m-20 20 12 12m-12-12-12-12M80 40l10-10 20 20-10 10zM20 20l10 10"/></svg>',
    "salon": '<svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="40" cy="80" r="14" fill="none" stroke="currentColor" stroke-width="3"/><circle cx="80" cy="80" r="14" fill="none" stroke="currentColor" stroke-width="3"/><path fill="none" stroke="currentColor" stroke-width="3" d="M50 70 90 20M70 70 30 20"/></svg>',
    "autoservis": '<svg viewBox="0 0 120 120" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="3" d="M10 80h100M20 80l10-25h60l10 25M30 95a8 8 0 1 0 0-1M90 95a8 8 0 1 0 0-1"/></svg>',
    "gastro": '<svg viewBox="0 0 120 120" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="3" d="M30 20v30a10 10 0 0 0 20 0V20M40 20v90M80 20c-10 0-14 20-14 35s4 15 14 15v40"/></svg>',
    "zdravi": '<svg viewBox="0 0 120 120" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="3" d="M60 100C30 80 15 60 15 42a20 20 0 0 1 45-12 20 20 0 0 1 45 12c0 18-15 38-45 58z"/><path fill="none" stroke="currentColor" stroke-width="3" d="M35 60h15l6-14 8 28 6-14h15"/></svg>',
    "obecny": '<svg viewBox="0 0 120 120" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="3" d="M20 100V50l40-30 40 30v50H20zM50 100V70h20v30"/></svg>',
}


class HeroImage(dict):
    """``{"url", "alt", "photographer", "photographer_url", "source_url", "provider"}``."""


def pexels_search(query: str, settings: Optional[Settings] = None, per_page: int = 3,
                  orientation: str = "landscape") -> List[HeroImage]:
    s = settings or get_settings()
    if not s.pexels_api_key:
        return []
    try:
        resp = requests.get(PEXELS_URL, headers={"Authorization": s.pexels_api_key},
                            params={"query": query, "per_page": per_page, "orientation": orientation},
                            timeout=10)
        if resp.status_code != 200:
            log.warning("Pexels HTTP %s for %r", resp.status_code, query)
            return []
        out = []
        for ph in resp.json().get("photos") or []:
            src = ph.get("src") or {}
            out.append(HeroImage(
                url=src.get("large2x") or src.get("large") or src.get("original") or "",
                alt=(ph.get("alt") or query)[:140],
                photographer=ph.get("photographer", ""),
                photographer_url=ph.get("photographer_url", ""),
                source_url=ph.get("url", ""),
                provider="pexels",
                avg_color=ph.get("avg_color", ""),
            ))
        return [o for o in out if o["url"]]
    except Exception as exc:       # noqa: BLE001
        log.warning("Pexels failed for %r: %s", query, exc)
        return []


def pick_hero_image(industry_key: str, lang: str, settings: Optional[Settings] = None,
                    seed: str = "") -> Optional[HeroImage]:
    """First usable Pexels photo for the industry (keyword rotated by ``seed``) or ``None``."""
    s = settings or get_settings()
    if not s.pexels_api_key:
        return None
    ind = industries.get_industry(industry_key)
    keywords = ind["stock_en"]            # Pexels search works best in English
    if not keywords:
        return None
    idx = sum(ord(c) for c in seed) % len(keywords) if seed else 0
    for i in range(len(keywords)):
        photos = pexels_search(keywords[(idx + i) % len(keywords)], s)
        if photos:
            return photos[0]
    return None


def placeholder_context(industry_key: str, lang: str) -> Dict[str, str]:
    """Template context for the no-photo case."""
    lang = "cs" if lang == "cs" else "en"
    return {
        "placeholder_label": PLACEHOLDER_LABEL[lang],
        "placeholder_hint": PLACEHOLDER_HINT[lang],
        "motif_svg": _MOTIFS.get(industry_key, _MOTIFS["obecny"]),
    }


def image_context(industry_key: str, lang: str, settings: Optional[Settings] = None,
                  seed: str = "", use_network: bool = True) -> Dict[str, object]:
    """Everything the templates need: ``hero_image`` (or None) + placeholder strings."""
    ctx: Dict[str, object] = dict(placeholder_context(industry_key, lang))
    hero = pick_hero_image(industry_key, lang, settings, seed) if use_network else None
    ctx["hero_image"] = hero
    ctx["image_source"] = "pexels" if hero else "placeholder"
    ctx["credit_label"] = CREDIT_LABEL["cs" if lang == "cs" else "en"]
    return ctx
