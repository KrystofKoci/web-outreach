"""Google Places API (New) - Text Search -> :class:`Lead` list.

Endpoint::

    POST https://places.googleapis.com/v1/places:searchText
    X-Goog-Api-Key: ...
    X-Goog-FieldMask: places.id,places.displayName,...

Billing / SKU notes (Places API New, 2025 pricing model - check the console):

* The **field mask decides the SKU**.  Our mask requests ``websiteUri``,
  phone numbers, ``rating``, ``userRatingCount`` and ``regularOpeningHours``,
  which puts every request into the *Text Search Pro / Enterprise* tier
  (roughly 0.03-0.04 USD per request, 20 results per request).  Dropping
  the phone/hours/rating fields would move it to the cheaper *Essentials*
  tier but we need ``websiteUri`` + phone to decide the branch, so keep it.
* One search page = one billable request; ``nextPageToken`` pages are billed
  again.  ``max_results`` therefore directly controls cost
  (30 previews/day with ~50 % skip rate ~ 60-80 leads ~ 4-6 requests/day
  per the plan produced by :func:`pipeline.learn.plan_day`).
* Caching rules (Places ToS): you may store ``place.id`` indefinitely; every
  other field must be refreshed at most 30 days after retrieval.  The CRM
  therefore keeps ``place_id`` + status and re-fetches details when a
  preview is built; stale rows are anonymised by n8n (see ``sheets/``).
* No scraping of Google Maps outside the API.

Blocked countries (Costa Rica always, plus ``BLOCKED_COUNTRIES``) are dropped
here already and the count is logged, so they never reach the CRM.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from . import countries
from .config import Settings, get_settings
from .models import Lead

log = logging.getLogger("pipeline.places")

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.addressComponents",
    "places.location", "places.websiteUri", "places.nationalPhoneNumber", "places.internationalPhoneNumber",
    "places.rating", "places.userRatingCount", "places.regularOpeningHours", "places.primaryType",
    "places.primaryTypeDisplayName", "places.types", "places.googleMapsUri", "places.businessStatus",
    "nextPageToken",
])
PAGE_SIZE = 20
MAX_PAGES = 3   # Places returns at most 60 results per text query anyway


class PlacesError(RuntimeError):
    """Places API returned an error or is not configured."""


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
def _component(components: Iterable[dict], *types: str, short: bool = False) -> str:
    for comp in components or []:
        ctypes = set(comp.get("types") or [])
        if any(t in ctypes for t in types):
            return (comp.get("shortText") if short else comp.get("longText")) or comp.get("shortText") or ""
    return ""


def parse_address_components(components: List[dict], formatted: str = "") -> Dict[str, str]:
    """Return ``{country, admin_area, city, postal_code}`` from Google addressComponents."""
    country = _component(components, "country", short=True).upper()
    if not country:
        country = countries.country_from_text(formatted)
    admin = _component(components, "administrative_area_level_1", short=True)
    city = (_component(components, "locality") or _component(components, "postal_town")
            or _component(components, "sublocality_level_1") or _component(components, "administrative_area_level_2")
            or _component(components, "administrative_area_level_3"))
    postal = _component(components, "postal_code", short=True)
    return {"country": country, "admin_area": admin, "city": city, "postal_code": postal}


def place_to_lead(place: Dict[str, Any], market: Optional[str] = None, lang: Optional[str] = None,
                  category: str = "") -> Lead:
    """Normalise one Places ``place`` object to :class:`Lead`."""
    comps = parse_address_components(place.get("addressComponents") or [], place.get("formattedAddress", ""))
    display = place.get("displayName") or {}
    name = display.get("text") if isinstance(display, dict) else str(display or "")
    ptype_disp = place.get("primaryTypeDisplayName") or {}
    primary_label = ptype_disp.get("text") if isinstance(ptype_disp, dict) else ""
    loc = place.get("location") or {}
    hours = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    return Lead(
        id=place.get("id", ""),
        name=name or "Firma",
        category=category or primary_label or (place.get("primaryType") or "").replace("_", " "),
        primary_type=place.get("primaryType") or "",
        types=list(place.get("types") or []),
        country=comps["country"],
        admin_area=comps["admin_area"],
        city=comps["city"],
        postal_code=comps["postal_code"],
        address=place.get("formattedAddress", "") or "",
        phone=place.get("nationalPhoneNumber", "") or "",
        phone_intl=place.get("internationalPhoneNumber", "") or "",
        website=place.get("websiteUri", "") or "",
        rating=place.get("rating"),
        rating_count=place.get("userRatingCount"),
        opening_hours=list(hours),
        maps_url=place.get("googleMapsUri", "") or "",
        lat=loc.get("latitude"),
        lng=loc.get("longitude"),
        market=market or "",
        lang=lang or "",
        business_status=place.get("businessStatus", "") or "",
        source="places",
    )


def _post(payload: dict, api_key: str, timeout: int) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    try:
        resp = requests.post(PLACES_URL, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise PlacesError(f"Places API: síťová chyba ({exc})") from exc
    if resp.status_code >= 400:
        raise PlacesError(f"Places API HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise PlacesError("Places API: odpověď není JSON") from exc


def search_places(query: str, *, region: str = "", language: str = "", max_results: int = 20,
                  market: Optional[str] = None, lang: Optional[str] = None, category: str = "",
                  location_bias: Optional[Tuple[float, float, float]] = None,
                  settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Run one Text Search (with pagination) and return normalised leads.

    ``query`` e.g. ``"instalatér Kolín"`` / ``"plumber Austin TX"``.
    ``region`` is the ISO2 country (``regionCode``) - also decides the Places
    language when ``language`` is empty.  ``location_bias`` = (lat, lng, radius_m).

    Returns ``{"leads": [...], "dropped_blocked": n, "dropped_closed": n,
    "pages": n, "query": query}``.  Leads located in a blocked country are
    never returned.
    """
    s = settings or get_settings()
    if not s.places_api_key:
        raise PlacesError("Chybí PLACES_API_KEY - vyhledávání firem není možné.")
    region = (region or "").upper()
    cinfo = countries.get_country(region)
    language = language or (cinfo.places_language if region else ("cs" if (market or s.default_market) == "cz" else "en"))
    market = market or (cinfo.market if region else s.default_market)
    lang = lang or ("cs" if market == "cz" else "en")

    leads: List[Lead] = []
    seen = set()
    dropped_blocked = dropped_closed = 0
    page_token = None
    pages = 0
    while len(leads) < max_results and pages < MAX_PAGES:
        payload: Dict[str, Any] = {
            "textQuery": query,
            "languageCode": language,
            "pageSize": min(PAGE_SIZE, max(1, max_results - len(leads))),
        }
        if region:
            payload["regionCode"] = region
        if page_token:
            payload["pageToken"] = page_token
        if location_bias:
            lat, lng, radius = location_bias
            payload["locationBias"] = {"circle": {"center": {"latitude": lat, "longitude": lng},
                                                  "radius": float(radius)}}
        data = _post(payload, s.places_api_key, s.http_timeout)
        pages += 1
        for place in data.get("places") or []:
            pid = place.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            if (place.get("businessStatus") or "") == "CLOSED_PERMANENTLY":
                dropped_closed += 1
                continue
            try:
                lead = place_to_lead(place, market=market, lang=lang, category=category)
            except Exception as exc:       # malformed place - skip, never crash a batch
                log.warning("Places: nelze normalizovat místo %s: %s", pid, exc)
                continue
            if s.is_blocked(lead.country):
                dropped_blocked += 1
                continue
            leads.append(lead)
            if len(leads) >= max_results:
                break
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    if dropped_blocked:
        log.info("Places: %d firem vyřazeno kvůli blokované zemi (dotaz %r)", dropped_blocked, query)
    log.info("Places: %r -> %d leadů (%d stránek, %d trvale zavřeno)", query, len(leads), pages, dropped_closed)
    return {
        "query": query,
        "region": region,
        "language": language,
        "leads": [l.model_dump() for l in leads],
        "dropped_blocked": dropped_blocked,
        "dropped_closed": dropped_closed,
        "pages": pages,
    }


def search_city_category(city: str, category: str, country: str, *, limit: int = 20,
                         settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Convenience wrapper used by the CLI / API: ``"<category> <city>"`` in the country."""
    cinfo = countries.get_country(country)
    query = f"{category} {city}".strip()
    return search_places(query, region=country, max_results=limit, market=cinfo.market,
                         lang=cinfo.lang, category=category, settings=settings)
