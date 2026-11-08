"""Pydantic v2 models shared by all pipeline stages.

They are re-exported from the module that "owns" them (``places_search.Lead``,
``audit.AuditResult``, ``copy_writer.SiteCopy``, ``generate_site.BuildResult``)
so callers can import from either place.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from . import countries

Branch = Literal["no_website", "redesign", "skip", "blocked"]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Lead(BaseModel):
    """A local business found via Google Places (or supplied by hand)."""

    id: str = ""
    name: str
    category: str = ""                 # human readable, e.g. "Instalatér" / "Plumber"
    primary_type: str = ""             # Google primaryType, e.g. "plumber"
    types: List[str] = Field(default_factory=list)
    country: str = ""                  # ISO 3166-1 alpha-2, e.g. "CZ", "US"
    admin_area: str = ""               # state / province / kraj (short name when available)
    city: str = ""
    postal_code: str = ""
    address: str = ""
    phone: str = ""                    # national format as displayed
    phone_intl: str = ""               # +420 ...
    website: str = ""
    has_website: bool = False
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    opening_hours: List[str] = Field(default_factory=list)  # weekday descriptions
    maps_url: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    market: str = ""                   # "cz" | "en" (filled from country when empty)
    lang: str = ""                     # "cs" | "en"  (filled from market when empty)
    tz: str = ""                       # IANA zone, guessed from country/region
    legal_regime: str = ""             # see pipeline.countries
    business_status: str = ""
    source: str = "places"

    @field_validator("website", mode="before")
    @classmethod
    def _website_str(cls, v):
        return (v or "").strip()

    @field_validator("country", mode="before")
    @classmethod
    def _country_up(cls, v):
        return (v or "").strip().upper()

    @field_validator("name", mode="before")
    @classmethod
    def _name_str(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("rating", mode="before")
    @classmethod
    def _rating_num(cls, v):
        if v in ("", None):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @field_validator("rating_count", mode="before")
    @classmethod
    def _rating_count_num(cls, v):
        if v in ("", None):
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    @field_validator("opening_hours", "types", mode="before")
    @classmethod
    def _list_or_split(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [p.strip() for p in v.replace("\n", ";").split(";") if p.strip()]
        return list(v)

    def model_post_init(self, __context) -> None:  # noqa: D401
        if self.website and not self.has_website:
            self.has_website = True
        if not self.phone and self.phone_intl:
            self.phone = self.phone_intl
        if not self.country and self.address:
            self.country = countries.country_from_text(self.address)
        if not self.market:
            self.market = countries.market_for_country(self.country, default="")
        if not self.lang:
            self.lang = {"cz": "cs", "en": "en"}.get(self.market, countries.lang_for_country(self.country))
        if not self.market:
            self.market = "cz" if self.lang == "cs" else "en"
        if not self.tz:
            self.tz = countries.guess_tz(self.country, self.admin_area, self.address)
        if not self.legal_regime:
            self.legal_regime = countries.legal_regime(self.country)

    @property
    def country_info(self) -> countries.CountryInfo:
        return countries.get_country(self.country)

    def as_flat(self) -> Dict[str, Any]:
        """Lead fields the way n8n / Sheets want them (JSON friendly)."""
        d = self.model_dump()
        d["legal_note_cs"] = self.country_info.legal_note_cs
        d["legal_note_en"] = self.country_info.legal_note_en
        return d


class AuditReason(BaseModel):
    key: str
    weight: int
    text_cs: str
    text_en: str

    def text(self, lang: str) -> str:
        return self.text_cs if lang == "cs" else self.text_en


class SocialLinks(BaseModel):
    facebook: str = ""
    instagram: str = ""
    linkedin: str = ""
    youtube: str = ""
    tiktok: str = ""

    def any(self) -> bool:
        return any(self.model_dump().values())


class AuditResult(BaseModel):
    """Outcome of :func:`pipeline.audit.audit_website` / :func:`pipeline.audit.audit_html`."""

    url: str = ""
    final_url: str = ""
    reachable: bool = False
    parked: bool = False
    status_code: Optional[int] = None
    error: str = ""

    https_ok: bool = False
    https_redirect: bool = False
    cert_error: bool = False

    title: str = ""
    meta_description: str = ""
    h1: str = ""
    lang: str = ""
    generator: str = ""
    cms: str = ""
    cms_version: str = ""
    jquery_version: str = ""
    tech: List[str] = Field(default_factory=list)

    viewport: bool = False
    responsive_signals: List[str] = Field(default_factory=list)
    copyright_year: Optional[int] = None
    has_flash: bool = False
    table_layout: bool = False
    legacy_tags: List[str] = Field(default_factory=list)
    has_contact_form: bool = False
    tel_links: List[str] = Field(default_factory=list)
    mailto_links: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    social: SocialLinks = Field(default_factory=SocialLinks)

    page_weight_kb: int = 0
    images_total: int = 0
    images_without_alt: int = 0
    last_modified: str = ""
    pagespeed_mobile: Optional[int] = None

    score: int = 0
    branch: Branch = "skip"
    reasons: List[AuditReason] = Field(default_factory=list)
    screenshot_able: bool = False
    fetched_at: str = Field(default_factory=utcnow_iso)

    def reasons_text(self, lang: str) -> List[str]:
        return [r.text(lang) for r in self.reasons]

    def summary(self) -> dict:
        """Compact dict stored in ``meta.json`` and returned by the API."""
        return {
            "url": self.url,
            "final_url": self.final_url,
            "reachable": self.reachable,
            "parked": self.parked,
            "status_code": self.status_code,
            "score": self.score,
            "branch": self.branch,
            "reasons": [r.model_dump() for r in self.reasons],
            "reasons_cs": self.reasons_text("cs"),
            "reasons_en": self.reasons_text("en"),
            "title": self.title,
            "cms": self.cms,
            "cms_version": self.cms_version,
            "tech": self.tech,
            "viewport": self.viewport,
            "copyright_year": self.copyright_year,
            "https_ok": self.https_ok,
            "cert_error": self.cert_error,
            "emails": self.emails,
            "phones": self.phones,
            "social": self.social.model_dump(),
            "pagespeed_mobile": self.pagespeed_mobile,
            "page_weight_kb": self.page_weight_kb,
            "lang": self.lang,
            "last_modified": self.last_modified,
            "fetched_at": self.fetched_at,
            "error": self.error,
        }


class ServiceItem(BaseModel):
    title: str = Field(min_length=2, max_length=60)
    text: str = Field(min_length=5, max_length=260)
    icon: str = "check"


class FaqItem(BaseModel):
    q: str = Field(min_length=5, max_length=160)
    a: str = Field(min_length=5, max_length=400)


class SiteCopy(BaseModel):
    """Texts for one preview page. Produced by the LLM or the template fallback."""

    headline: str = Field(min_length=3, max_length=140)
    subheadline: str = Field(min_length=3, max_length=260)
    cta_primary: str = Field(min_length=2, max_length=40)
    about_title: str = Field(min_length=2, max_length=80)
    about_text: str = Field(min_length=10)
    services: List[ServiceItem] = Field(min_length=3, max_length=6)
    why_us: List[str] = Field(min_length=3, max_length=3)
    reviews_line: str = ""
    hours_title: str = Field(min_length=2, max_length=60)
    contact_title: str = Field(min_length=2, max_length=60)
    faq: List[FaqItem] = Field(min_length=2, max_length=3)
    footer_note: str = ""
    source: str = "fallback"          # "llm" | "fallback"

    @field_validator("about_text")
    @classmethod
    def _about_max_words(cls, v: str) -> str:
        words = v.split()
        if len(words) > 80:
            raise ValueError(f"about_text has {len(words)} words, maximum is 80")
        return v.strip()

    @field_validator("why_us")
    @classmethod
    def _why_us_clean(cls, v: List[str]) -> List[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if len(cleaned) != 3:
            raise ValueError("why_us must contain exactly 3 non-empty bullets")
        return cleaned


class BuildResult(BaseModel):
    slug: str
    path: str                      # directory with index.html
    url: str
    html_path: str = ""
    html_bytes: int = 0
    meta_path: str = ""
    industry: str = "obecny"
    lang: str = "cs"
    demo: bool = False
    image_source: str = "placeholder"   # "pexels" | "placeholder"
    built_at: str = Field(default_factory=utcnow_iso)


class ProcessResult(BaseModel):
    """Flat result of :func:`pipeline.run.process_lead` - what n8n stores in Sheets."""

    # lead fields (flattened so Sheets columns map 1:1)
    lead_id: str = ""
    name: str = ""
    category: str = ""
    primary_type: str = ""
    country: str = ""
    admin_area: str = ""
    city: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    has_website: bool = False
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    maps_url: str = ""
    market: str = "cz"
    lang: str = "cs"
    tz: str = "UTC"
    legal_regime: str = "unknown"
    legal_note_cs: str = ""
    legal_note_en: str = ""

    # audit
    branch: Branch = "skip"
    score: int = 0
    reasons_cs: List[str] = Field(default_factory=list)
    reasons_en: List[str] = Field(default_factory=list)
    reason_keys: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    best_email: str = ""
    final_url: str = ""
    cms: str = ""
    tech: List[str] = Field(default_factory=list)
    pagespeed_mobile: Optional[int] = None

    # build
    industry: str = ""
    slug: str = ""
    preview_url: str = ""
    compare_png_url: str = ""
    og_png_url: str = ""
    new_mobile_png_url: str = ""
    copy_source: str = ""          # "llm" | "fallback" | ""
    # nabídka z původního webu (offer_extract) - pro CRM a schvalovací stránku
    extracted_offer: dict = Field(default_factory=dict)   # OfferData.model_dump()
    offer_summary: str = ""        # krátký text do sloupce extracted_offer
    offer_photos: str = ""         # URL firemních fotek z původního webu, oddělené mezerou
    owner_note: str = ""           # poznámka majitele, se kterou se náhled stavěl
    image_source: str = ""
    built: bool = False
    blocked_reason: str = ""
    warnings: List[str] = Field(default_factory=list)
    processed_at: str = Field(default_factory=utcnow_iso)


# ---------------------------------------------------------------------------
# learn.py models
# ---------------------------------------------------------------------------
class SegmentStat(BaseModel):
    """One segment of the owner's "formula" (``learn.compute_weights``)."""

    key: str                         # e.g. "country=US|industry=autoservis"
    dimension: str = ""              # "country", "industry", "country_industry", "score_bucket", ...
    country: str = ""
    industry: str = ""
    score_bucket: str = ""
    subject_variant: str = ""
    weekday: str = ""
    hour: str = ""
    sent: int = 0
    replied: int = 0
    meetings: int = 0
    won: int = 0
    reply_rate: float = 0.0
    win_rate: float = 0.0
    smoothed_reply_rate: float = 0.0
    smoothed_win_rate: float = 0.0
    weight: float = 1.0


class LearnResult(BaseModel):
    generated_at: str = Field(default_factory=utcnow_iso)
    basis: str = "win"               # "win" | "reply" (what the weights are driven by)
    totals: Dict[str, Any] = Field(default_factory=dict)
    segments: List[SegmentStat] = Field(default_factory=list)
    recommendations_cs: List[str] = Field(default_factory=list)
    recommendations_en: List[str] = Field(default_factory=list)


class PlanRow(BaseModel):
    """One Places search n8n should run today."""

    country: str
    city: str
    category: str
    industry: str = ""
    lang: str = "en"
    market: str = "en"
    limit: int = 10
    weight: float = 1.0
    query: str = ""
