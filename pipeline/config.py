"""Runtime settings read from environment variables.

Nothing is hardcoded here except safe defaults. Every secret (API keys, the
shared API token) must come from the environment / Docker secrets.

Usage::

    from pipeline.config import get_settings
    s = get_settings()
    s.preview_dir

Markets
-------
``cz`` - Czech copy (``cs``), Czech legal footer.
``en`` - English copy for US/GB/IE/CA/AU/NZ... The *country* of the lead (not
the market) decides time zone and legal regime, see :mod:`pipeline.countries`.
Adding ``es`` / ``de`` later means: a new key in ``MARKET_LANG``, copy
dictionaries in :mod:`pipeline.industries` / :mod:`pipeline.copy_writer`
and template strings in ``templates/_i18n.html.j2``.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import FrozenSet, Optional

SUPPORTED_MARKETS = ("cz", "en")

# market -> UI / copy language
MARKET_LANG = {
    "cz": "cs",
    "en": "en",
}

# Countries that are hard-blocked no matter what the environment says.
ALWAYS_BLOCKED_COUNTRIES: FrozenSet[str] = frozenset({"CR"})

# Countries with a strict e-mail regime (blocked by default, can be enabled
# one by one through ALLOWED_STRICT_COUNTRIES - never CR).
STRICT_COUNTRIES: FrozenSet[str] = frozenset({"DE", "AT", "CH", "NL"})


def lang_for_market(market: Optional[str]) -> str:
    """Return the copy language ('cs' or 'en') for a market code."""
    return MARKET_LANG.get((market or "cz").lower(), "en")


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_opt(name: str) -> Optional[str]:
    value = _env(name, "")
    return value or None


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def parse_country_list(raw: str) -> FrozenSet[str]:
    """``"cr, de,,at"`` -> ``{"CR", "DE", "AT"}``."""
    out = set()
    for part in (raw or "").replace(";", ",").split(","):
        code = part.strip().upper()
        if len(code) == 2 and code.isalpha():
            out.add(code)
    return frozenset(out)


@dataclass
class Settings:
    """All tunables of the pipeline. Built by :func:`get_settings`."""

    # --- external APIs -----------------------------------------------------
    places_api_key: Optional[str] = None
    # LLM gateway (LiteLLM, OpenAI-compatible). Preferred backend.
    llm_base_url: str = "http://litellm:4000/v1"
    llm_api_key: Optional[str] = None
    llm_model_copy: str = "copy"
    llm_model_classify: str = "classify"
    # Direct Anthropic access - fallback when the gateway is not configured.
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_base_url: str = "https://api.anthropic.com"
    pagespeed_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None

    # --- previews ----------------------------------------------------------
    preview_dir: Path = field(default_factory=lambda: Path("/srv/nahled"))
    preview_base_url: str = "https://nahled.krystofkoci.com"
    form_webhook_url: str = ""
    premium_templates: bool = True          # PREMIUM_TEMPLATES – schválené premium šablony (pipeline/premium.py)

    # --- owner identity shown on previews ---------------------------------
    owner_name: str = "Kryštof Kočí"
    owner_email: str = "kontakt@krystofkoci.com"
    owner_site: str = "https://krystofkoci.com"
    owner_whatsapp: Optional[str] = None   # E.164, e.g. +420777123456 – only for "write me on WhatsApp" link

    # --- behaviour ---------------------------------------------------------
    default_market: str = "cz"
    blocked_countries: FrozenSet[str] = ALWAYS_BLOCKED_COUNTRIES
    allowed_strict_countries: FrozenSet[str] = frozenset()
    api_token: Optional[str] = None
    api_host: str = "0.0.0.0"
    api_port: int = 8077
    http_timeout: int = 15
    screenshot_timeout_s: int = 20
    user_agent: str = (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36 "
        "web-outreach-audit/0.1 (+https://krystofkoci.com)"
    )

    # --- derived -----------------------------------------------------------
    @property
    def market(self) -> str:           # backwards compatible alias
        return self.default_market

    @property
    def lang(self) -> str:
        return lang_for_market(self.default_market)

    @property
    def templates_dir(self) -> Path:
        return Path(__file__).resolve().parent / "templates"

    @property
    def state_dir(self) -> Path:
        return self.preview_dir / "_state"

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key) or bool(self.anthropic_api_key)

    @property
    def effective_blocked_countries(self) -> FrozenSet[str]:
        """Hard blocked (CR + BLOCKED_COUNTRIES) plus strict countries not explicitly allowed."""
        strict = STRICT_COUNTRIES - (self.allowed_strict_countries - ALWAYS_BLOCKED_COUNTRIES)
        return frozenset(self.blocked_countries | ALWAYS_BLOCKED_COUNTRIES | strict)

    def is_blocked(self, country: Optional[str]) -> bool:
        return (country or "").upper() in self.effective_blocked_countries

    def block_reason(self, country: Optional[str], lang: str = "cs") -> str:
        code = (country or "").upper()
        if code in ALWAYS_BLOCKED_COUNTRIES:
            return ("Kostarika (CR) se nikdy neoslovuje - pevné pravidlo systému."
                    if lang == "cs" else "Costa Rica (CR) is never contacted - hard system rule.")
        if code in self.blocked_countries:
            return (f"Země {code} je v BLOCKED_COUNTRIES." if lang == "cs"
                    else f"Country {code} is listed in BLOCKED_COUNTRIES.")
        if code in STRICT_COUNTRIES:
            return (f"Země {code} má přísný režim (opt-in, vysoké pokuty) - blokována, "
                    f"povolit lze přes ALLOWED_STRICT_COUNTRIES={code}." if lang == "cs"
                    else f"Country {code} has a strict regime - blocked by default, "
                         f"enable via ALLOWED_STRICT_COUNTRIES={code}.")
        if not code:
            return ("Země leadu není známa - nelze ověřit, zda není blokována."
                    if lang == "cs" else "Lead country unknown - cannot verify block list.")
        return ""

    def preview_url(self, slug: str) -> str:
        return f"{self.preview_base_url.rstrip('/')}/{slug}/"

    def as_public_dict(self) -> dict:
        """Settings without secrets (for /health and logs)."""
        d = asdict(self)
        d["preview_dir"] = str(self.preview_dir)
        d["blocked_countries"] = sorted(self.effective_blocked_countries)
        d["allowed_strict_countries"] = sorted(self.allowed_strict_countries)
        for key in ("places_api_key", "llm_api_key", "anthropic_api_key",
                    "pagespeed_api_key", "pexels_api_key", "api_token"):
            d[key] = bool(d.get(key))
        d["llm_configured"] = self.llm_configured
        return d


def get_settings() -> Settings:
    """Build :class:`Settings` from the current environment (cheap, no caching)."""
    market = _env("DEFAULT_MARKET", _env("MARKET", "cz")).lower()
    if market not in SUPPORTED_MARKETS:
        market = "cz"
    blocked = parse_country_list(_env("BLOCKED_COUNTRIES", "CR")) | ALWAYS_BLOCKED_COUNTRIES
    allowed_strict = parse_country_list(_env("ALLOWED_STRICT_COUNTRIES", "")) - ALWAYS_BLOCKED_COUNTRIES

    return Settings(
        places_api_key=_env_opt("PLACES_API_KEY"),
        llm_base_url=_env("LLM_BASE_URL", "http://litellm:4000/v1").rstrip("/"),
        llm_api_key=_env_opt("LLM_API_KEY"),
        llm_model_copy=_env("LLM_MODEL_COPY", "copy"),
        llm_model_classify=_env("LLM_MODEL_CLASSIFY", "classify"),
        anthropic_api_key=_env_opt("ANTHROPIC_API_KEY"),
        anthropic_model=_env("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        anthropic_base_url=_env("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        pagespeed_api_key=_env_opt("PAGESPEED_API_KEY"),
        pexels_api_key=_env_opt("PEXELS_API_KEY"),
        preview_dir=Path(_env("PREVIEW_DIR", "/srv/nahled")),
        preview_base_url=_env("PREVIEW_BASE_URL", "https://nahled.krystofkoci.com"),
        form_webhook_url=_env("FORM_WEBHOOK_URL", ""),
        premium_templates=_env("PREMIUM_TEMPLATES", "true").strip().lower() not in ("0", "false", "no", "ne", "off"),
        owner_name=_env("OWNER_NAME", "Kryštof Kočí"),
        owner_email=_env("OWNER_EMAIL", "kontakt@krystofkoci.com"),
        owner_site=_env("OWNER_SITE", "https://krystofkoci.com"),
        owner_whatsapp=_env_opt("OWNER_WHATSAPP"),
        default_market=market,
        blocked_countries=frozenset(blocked),
        allowed_strict_countries=frozenset(allowed_strict),
        api_token=_env_opt("API_TOKEN"),
        api_host=_env("API_HOST", "0.0.0.0"),
        api_port=_env_int("API_PORT", 8077),
        http_timeout=_env_int("HTTP_TIMEOUT", 15),
        screenshot_timeout_s=_env_int("SCREENSHOT_TIMEOUT", 20),
    )
