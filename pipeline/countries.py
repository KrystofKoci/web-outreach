"""Country knowledge: language, market, currency, time zone, legal regime.

The *country of the business* (ISO 3166-1 alpha-2, derived from Google
``addressComponents``) drives three things:

* which copy language / market the preview and e-mail use,
* which IANA time zone n8n should use to schedule the e-mail (so a US lead
  receives it at 9:00 local, not at 3:00 in the night),
* which legal regime applies to the first cold e-mail (``legal_regime`` +
  ``legal_note_cs`` are returned by ``/process`` so the n8n flow can pick the
  right footer or refuse to send).

Legal regime labels (see ``docs/02_PRAVNI_CHECKLIST.md``):

``opt_in``            consent required (CZ, SK) - individual e-mail to a published
                      company contact, owner approves each one, instant opt-out.
``opt_out``           CAN-SPAM style (US) - allowed with identification + unsubscribe.
``corporate_only``    GB/IE PECR - allowed for corporate subscribers (Ltd), not sole traders.
``published_address`` CA (CASL implied consent for conspicuously published business
                      addresses), AU/NZ (published address not marked "no commercial").
``blocked``           strict regimes (DE, AT, CH, NL) blocked by default, and CR always.
``unknown``           not in the table - n8n must not send without a human check.

Costa Rica (``CR``) is **never** processed - this is a hard rule enforced in
:mod:`pipeline.config`, :mod:`pipeline.places_search`, :mod:`pipeline.run`
and :mod:`pipeline.learn`.
"""

from __future__ import annotations

import re
from typing import Dict, Literal, Optional

LegalRegime = Literal["opt_in", "opt_out", "published_address", "corporate_only", "blocked", "unknown"]

_LEGAL_NOTES_CS: Dict[str, str] = {
    "opt_in": ("Opt-in režim (z. 480/2004 Sb.): pouze individuální e-mail na veřejně uvedený firemní "
               "kontakt, schválený majitelem, s označením obchodního sdělení, identifikací a odhlášením."),
    "opt_out": ("Opt-out režim (CAN-SPAM): cold e-mail firmě je povolen; nutná pravdivá hlavička, "
                "poštovní adresa odesílatele a funkční odhlášení."),
    "corporate_only": ("PECR: e-mail bez souhlasu jen pro firmy typu Ltd/PLC/LLP. Živnostníci (sole traders) "
                       "vyžadují souhlas - před odesláním ověřit právní formu."),
    "published_address": ("Veřejně zveřejněná firemní adresa platí jako konkludentní souhlas (CASL / Spam Act), "
                          "pokud není označena 'žádná obchodní sdělení'. Nutná identifikace a odhlášení."),
    "blocked": "Blokovaná země - neoslovovat.",
    "unknown": "Právní rámec země není v tabulce - před odesláním nutná ruční kontrola.",
}
_LEGAL_NOTES_EN: Dict[str, str] = {
    "opt_in": ("Opt-in regime: only an individual e-mail to a published business contact, approved by the owner, "
               "labelled as commercial, with sender identification and unsubscribe."),
    "opt_out": ("Opt-out regime (CAN-SPAM): cold e-mail to a business is allowed; truthful headers, "
                "sender postal address and working unsubscribe required."),
    "corporate_only": ("PECR: e-mail without consent only to corporate subscribers (Ltd/PLC/LLP). "
                       "Sole traders require consent - verify legal form before sending."),
    "published_address": ("A conspicuously published business address counts as implied consent "
                          "(CASL / Spam Act) unless marked 'no commercial messages'. Identification and unsubscribe required."),
    "blocked": "Blocked country - do not contact.",
    "unknown": "Legal regime not in the table - manual check required before sending.",
}


class CountryInfo(dict):
    """Plain dict with attribute access (keeps JSON serialisation trivial)."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


def _c(code: str, name_cs: str, name_en: str, lang: str, market: str, currency: str,
       tz: str, regime: str, places_lang: Optional[str] = None) -> CountryInfo:
    return CountryInfo(
        code=code, name_cs=name_cs, name_en=name_en, lang=lang, market=market,
        currency=currency, tz=tz, legal_regime=regime,
        places_language=places_lang or lang,
        legal_note_cs=_LEGAL_NOTES_CS[regime], legal_note_en=_LEGAL_NOTES_EN[regime],
    )


COUNTRIES: Dict[str, CountryInfo] = {
    "CZ": _c("CZ", "Česko", "Czech Republic", "cs", "cz", "CZK", "Europe/Prague", "opt_in"),
    "SK": _c("SK", "Slovensko", "Slovakia", "cs", "cz", "EUR", "Europe/Bratislava", "opt_in", places_lang="sk"),
    "US": _c("US", "USA", "United States", "en", "en", "USD", "America/Chicago", "opt_out"),
    "GB": _c("GB", "Velká Británie", "United Kingdom", "en", "en", "GBP", "Europe/London", "corporate_only"),
    "IE": _c("IE", "Irsko", "Ireland", "en", "en", "EUR", "Europe/Dublin", "corporate_only"),
    "CA": _c("CA", "Kanada", "Canada", "en", "en", "CAD", "America/Toronto", "published_address"),
    "AU": _c("AU", "Austrálie", "Australia", "en", "en", "AUD", "Australia/Sydney", "published_address"),
    "NZ": _c("NZ", "Nový Zéland", "New Zealand", "en", "en", "NZD", "Pacific/Auckland", "published_address"),
    "PL": _c("PL", "Polsko", "Poland", "en", "en", "PLN", "Europe/Warsaw", "unknown", places_lang="pl"),
    "DE": _c("DE", "Německo", "Germany", "en", "en", "EUR", "Europe/Berlin", "blocked", places_lang="de"),
    "AT": _c("AT", "Rakousko", "Austria", "en", "en", "EUR", "Europe/Vienna", "blocked", places_lang="de"),
    "CH": _c("CH", "Švýcarsko", "Switzerland", "en", "en", "CHF", "Europe/Zurich", "blocked", places_lang="de"),
    "NL": _c("NL", "Nizozemsko", "Netherlands", "en", "en", "EUR", "Europe/Amsterdam", "blocked", places_lang="nl"),
    "CR": _c("CR", "Kostarika", "Costa Rica", "en", "en", "CRC", "America/Costa_Rica", "blocked", places_lang="es"),
}

UNKNOWN_COUNTRY = CountryInfo(
    code="", name_cs="neznámá", name_en="unknown", lang="en", market="en", currency="",
    tz="UTC", legal_regime="unknown", places_language="en",
    legal_note_cs=_LEGAL_NOTES_CS["unknown"], legal_note_en=_LEGAL_NOTES_EN["unknown"],
)

# ---------------------------------------------------------------------------
# Sub-national time zones
# ---------------------------------------------------------------------------
US_STATE_TZ: Dict[str, str] = {
    # Eastern
    "CT": "America/New_York", "DE": "America/New_York", "DC": "America/New_York", "FL": "America/New_York",
    "GA": "America/New_York", "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York",
    "NH": "America/New_York", "NJ": "America/New_York", "NY": "America/New_York", "NC": "America/New_York",
    "OH": "America/New_York", "PA": "America/New_York", "RI": "America/New_York", "SC": "America/New_York",
    "VT": "America/New_York", "VA": "America/New_York", "WV": "America/New_York", "MI": "America/New_York",
    "IN": "America/New_York", "KY": "America/New_York",
    # Central
    "AL": "America/Chicago", "AR": "America/Chicago", "IL": "America/Chicago", "IA": "America/Chicago",
    "KS": "America/Chicago", "LA": "America/Chicago", "MN": "America/Chicago", "MS": "America/Chicago",
    "MO": "America/Chicago", "NE": "America/Chicago", "ND": "America/Chicago", "OK": "America/Chicago",
    "SD": "America/Chicago", "TN": "America/Chicago", "TX": "America/Chicago", "WI": "America/Chicago",
    # Mountain
    "AZ": "America/Denver", "CO": "America/Denver", "ID": "America/Denver", "MT": "America/Denver",
    "NM": "America/Denver", "UT": "America/Denver", "WY": "America/Denver",
    # Pacific
    "CA": "America/Los_Angeles", "NV": "America/Los_Angeles", "OR": "America/Los_Angeles",
    "WA": "America/Los_Angeles",
    # others (nearest of the four allowed zones is not meaningful; use proper zones)
    "AK": "America/Anchorage", "HI": "Pacific/Honolulu",
}
US_STATE_NAMES: Dict[str, str] = {
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "new hampshire": "NH", "new jersey": "NJ", "new york": "NY", "north carolina": "NC",
    "ohio": "OH", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "vermont": "VT",
    "virginia": "VA", "west virginia": "WV", "michigan": "MI", "indiana": "IN", "kentucky": "KY",
    "alabama": "AL", "arkansas": "AR", "illinois": "IL", "iowa": "IA", "kansas": "KS", "louisiana": "LA",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "nebraska": "NE", "north dakota": "ND",
    "oklahoma": "OK", "south dakota": "SD", "tennessee": "TN", "texas": "TX", "wisconsin": "WI",
    "arizona": "AZ", "colorado": "CO", "idaho": "ID", "montana": "MT", "new mexico": "NM", "utah": "UT",
    "wyoming": "WY", "california": "CA", "nevada": "NV", "oregon": "OR", "washington": "WA",
    "alaska": "AK", "hawaii": "HI", "district of columbia": "DC",
}
CA_PROVINCE_TZ: Dict[str, str] = {
    "BC": "America/Vancouver", "AB": "America/Edmonton", "SK": "America/Regina", "MB": "America/Winnipeg",
    "ON": "America/Toronto", "QC": "America/Toronto", "NB": "America/Halifax", "NS": "America/Halifax",
    "PE": "America/Halifax", "NL": "America/St_Johns", "YT": "America/Whitehorse", "NT": "America/Yellowknife",
    "NU": "America/Iqaluit",
}
CA_PROVINCE_NAMES: Dict[str, str] = {
    "british columbia": "BC", "alberta": "AB", "saskatchewan": "SK", "manitoba": "MB", "ontario": "ON",
    "quebec": "QC", "québec": "QC", "new brunswick": "NB", "nova scotia": "NS", "prince edward island": "PE",
    "newfoundland and labrador": "NL", "yukon": "YT", "northwest territories": "NT", "nunavut": "NU",
}
AU_STATE_TZ: Dict[str, str] = {
    "NSW": "Australia/Sydney", "ACT": "Australia/Sydney", "VIC": "Australia/Melbourne", "TAS": "Australia/Hobart",
    "QLD": "Australia/Brisbane", "SA": "Australia/Adelaide", "NT": "Australia/Darwin", "WA": "Australia/Perth",
}
AU_STATE_NAMES: Dict[str, str] = {
    "new south wales": "NSW", "australian capital territory": "ACT", "victoria": "VIC", "tasmania": "TAS",
    "queensland": "QLD", "south australia": "SA", "northern territory": "NT", "western australia": "WA",
}

_US_ADDR_RE = re.compile(r",\s*([A-Z]{2})\s+\d{5}(?:-\d{4})?\b")
_CA_ADDR_RE = re.compile(r",\s*([A-Z]{2})\s+[A-Z]\d[A-Z]\s?\d[A-Z]\d\b")
_AU_ADDR_RE = re.compile(r"\b(NSW|ACT|VIC|TAS|QLD|SA|NT|WA)\s+\d{4}\b")


def get_country(code: Optional[str]) -> CountryInfo:
    """Return the :class:`CountryInfo` for an ISO2 code (``UNKNOWN_COUNTRY`` when missing)."""
    return COUNTRIES.get((code or "").strip().upper(), UNKNOWN_COUNTRY)


def legal_regime(code: Optional[str]) -> str:
    return get_country(code).legal_regime


def lang_for_country(code: Optional[str], default: str = "en") -> str:
    info = COUNTRIES.get((code or "").upper())
    return info.lang if info else default


def market_for_country(code: Optional[str], default: str = "en") -> str:
    info = COUNTRIES.get((code or "").upper())
    return info.market if info else default


def _norm_region(region: Optional[str], names: Dict[str, str]) -> str:
    r = (region or "").strip()
    if not r:
        return ""
    if len(r) <= 3 and r.isalpha():
        return r.upper()
    return names.get(r.lower(), "")


def guess_tz(country: Optional[str], admin_area: Optional[str] = None, address: Optional[str] = None) -> str:
    """Best-effort IANA time zone for a business.

    ``admin_area`` is the Google ``administrative_area_level_1`` (short or long
    name); when it is missing the state/province is sniffed from the formatted
    address. Unknown -> country default -> ``UTC``.
    """
    code = (country or "").strip().upper()
    info = COUNTRIES.get(code)
    addr = address or ""
    if code == "US":
        st = _norm_region(admin_area, US_STATE_NAMES)
        if not st:
            m = _US_ADDR_RE.search(addr)
            st = m.group(1) if m else ""
        return US_STATE_TZ.get(st, "America/Chicago")
    if code == "CA":
        pr = _norm_region(admin_area, CA_PROVINCE_NAMES)
        if not pr:
            m = _CA_ADDR_RE.search(addr)
            pr = m.group(1) if m else ""
        return CA_PROVINCE_TZ.get(pr, "America/Toronto")
    if code == "AU":
        st = _norm_region(admin_area, AU_STATE_NAMES)
        if not st:
            m = _AU_ADDR_RE.search(addr)
            st = m.group(1) if m else ""
        return AU_STATE_TZ.get(st, "Australia/Sydney")
    if info:
        return info.tz
    return "UTC"


def country_from_text(address: str) -> str:
    """Very rough fallback when addressComponents are missing (hand-made leads)."""
    a = (address or "").lower()
    tails = {
        "czechia": "CZ", "czech republic": "CZ", "česko": "CZ", "česká republika": "CZ",
        "slovakia": "SK", "slovensko": "SK", "united states": "US", "usa": "US",
        "united kingdom": "GB", "uk": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
        "ireland": "IE", "canada": "CA", "australia": "AU", "new zealand": "NZ", "poland": "PL",
        "germany": "DE", "deutschland": "DE", "austria": "AT", "österreich": "AT", "switzerland": "CH",
        "netherlands": "NL", "costa rica": "CR",
    }
    for key, code in tails.items():
        if a.endswith(key) or f", {key}" in a:
            return code
    if _US_ADDR_RE.search(address or ""):
        return "US"
    if _CA_ADDR_RE.search(address or ""):
        return "CA"
    if _AU_ADDR_RE.search(address or ""):
        return "AU"
    if re.search(r"\b\d{3} ?\d{2}\b", address or "") and not re.search(r"\d{5}", address or ""):
        return "CZ"
    return ""
