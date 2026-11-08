"""Render one self-contained preview page (``index.html`` + ``meta.json``).

``build_site(lead, copy, industry_key, ...)`` -> :class:`BuildResult`

The page is a single HTML file: inline CSS, one Google Fonts link, a few lines
of vanilla JS (mobile nav, dismissible preview banner, JSON POST of the
contact form to ``FORM_WEBHOOK_URL``).  Photos are hot-linked from Pexels or
replaced by a dashed placeholder, so the directory contains no binary assets
except the screenshots added later by :mod:`pipeline.screenshot_compare`.

UI strings live in ``I18N`` - add a language by adding a key there, in
:mod:`pipeline.industries` (services/faq) and :mod:`pipeline.copy_writer`.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import images, industries, offer_inject, premium
from .config import Settings, get_settings
from .models import BuildResult, Lead, SiteCopy
from .slug import make_slug

log = logging.getLogger("pipeline.build")

I18N: Dict[str, Dict[str, str]] = {
    "cs": {
        "in_city": "–", "nav_label": "Hlavní navigace", "nav_services": "Služby", "nav_about": "O nás",
        "nav_hours": "Otevírací doba", "nav_contact": "Kontakt", "menu": "Menu", "write_us": "Napsat",
        "today": "Dnes", "services_title": "S čím vám pomůžeme", "why_title": "Proč k nám",
        "see_on_google": "Zobrazit hodnocení na Google", "hours_missing": "Otevírací dobu doplníme podle vašich podkladů.",
        "map_title": "Mapa – kde nás najdete", "contact_sub": "Zavolejte, napište nebo se zastavte.",
        "phone": "Telefon", "address": "Adresa", "email": "E-mail",
        "form_name": "Jméno", "form_email": "E-mail", "form_message": "Zpráva", "form_send": "Odeslat zprávu",
        "form_placeholder": "S čím potřebujete pomoci?", "form_ok": "Děkujeme, ozveme se vám.",
        "form_err": "Odeslání se nepovedlo. Zavolejte nám prosím nebo zkuste znovu.",
        "form_note": "Odesláním souhlasíte s tím, že vás kontaktujeme zpět k vaší zprávě.",
        "faq_title": "Časté dotazy", "prepared_by": "Návrh webu:", "demo_footer": "Ukázkový web –",
        "banner_aria": "Informace o náhledu", "banner_text_before": "Nezávazný návrh nového webu pro",
        "banner_prepared": "připravil", "banner_want": "Chci tento web", "banner_wa": "WhatsApp", "banner_hide": "Nezobrazovat",
    },
    "en": {
        "in_city": "in", "nav_label": "Main navigation", "nav_services": "Services", "nav_about": "About",
        "nav_hours": "Hours", "nav_contact": "Contact", "menu": "Menu", "write_us": "Message us",
        "today": "Today", "services_title": "What we can help with", "why_title": "Why choose us",
        "see_on_google": "See reviews on Google", "hours_missing": "Opening hours will be added from your details.",
        "map_title": "Map – where to find us", "contact_sub": "Call, write or drop by.",
        "phone": "Phone", "address": "Address", "email": "E-mail",
        "form_name": "Name", "form_email": "E-mail", "form_message": "Message", "form_send": "Send message",
        "form_placeholder": "What do you need help with?", "form_ok": "Thank you, we'll get back to you.",
        "form_err": "Sending failed. Please call us or try again.",
        "form_note": "By sending you agree that we contact you back about your message.",
        "faq_title": "Common questions", "prepared_by": "Website draft by", "demo_footer": "Demo website –",
        "banner_aria": "Preview information", "banner_text_before": "Non-binding draft of a new website for",
        "banner_prepared": "prepared by", "banner_want": "I want this website", "banner_wa": "WhatsApp", "banner_hide": "Hide",
    },
}

_DAYS = {
    "cs": ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
_DAY_ALIASES = {
    "monday": 0, "pondělí": 0, "pondeli": 0, "montag": 0, "pondelok": 0,
    "tuesday": 1, "úterý": 1, "utery": 1, "dienstag": 1, "utorok": 1,
    "wednesday": 2, "středa": 2, "streda": 2, "mittwoch": 2,
    "thursday": 3, "čtvrtek": 3, "ctvrtek": 3, "donnerstag": 3, "štvrtok": 3,
    "friday": 4, "pátek": 4, "patek": 4, "freitag": 4, "piatok": 4,
    "saturday": 5, "sobota": 5, "samstag": 5,
    "sunday": 6, "neděle": 6, "nedele": 6, "sonntag": 6, "nedeľa": 6,
}
_CLOSED_WORDS = {"closed": {"cs": "Zavřeno", "en": "Closed"}, "zavřeno": {"cs": "Zavřeno", "en": "Closed"},
                 "geschlossen": {"cs": "Zavřeno", "en": "Closed"}, "zatvorené": {"cs": "Zavřeno", "en": "Closed"}}


def _env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "j2", "html.j2"], default=True),
        trim_blocks=True, lstrip_blocks=True,
    )


def parse_opening_hours(descriptions: List[str], lang: str) -> List[Tuple[str, str]]:
    """``["Monday: 8:00 AM – 5:00 PM", ...]`` -> ``[("Pondělí", "8:00–17:00"), ...]`` ordered Mon..Sun."""
    lang = "cs" if lang == "cs" else "en"
    found: Dict[int, str] = {}
    for line in descriptions or []:
        if ":" not in line:
            continue
        day, _, val = line.partition(":")
        idx = _DAY_ALIASES.get(day.strip().lower())
        if idx is None:
            continue
        val = val.strip()
        low = val.lower()
        if low in _CLOSED_WORDS:
            val = _CLOSED_WORDS[low][lang]
        elif lang == "cs":
            val = _to_24h(val)
        val = val.replace(" – ", "–").replace(" - ", "–")
        found[idx] = val
    if not found:
        return []
    return [(_DAYS[lang][i], found.get(i, _CLOSED_WORDS["closed"][lang])) for i in range(7)]


def _to_24h(val: str) -> str:
    def rep(m):
        h, mi, ap = int(m.group(1)), m.group(2) or "00", m.group(3).upper()
        if ap == "PM" and h != 12:
            h += 12
        if ap == "AM" and h == 12:
            h = 0
        return f"{h}:{mi}"
    return re.sub(r"(\d{1,2})(?::(\d{2}))?\s*([AaPp][Mm])", rep, val).replace(" ", " ").replace(" ", "")


def _phone_href(phone: str) -> str:
    p = re.sub(r"[^\d+]", "", phone or "")
    return p


def favicon_svg(letter: str, bg: str, fg: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="{bg}"/>'
            f'<text x="32" y="42" font-family="Arial,Helvetica,sans-serif" font-size="34" font-weight="700" '
            f'text-anchor="middle" fill="{fg}">{letter}</text></svg>')


def build_context(lead: Lead, copy: SiteCopy, industry_key: str, s: Settings, *, demo: bool,
                  slug: str, preview_url: str, image_ctx: Dict[str, Any], best_email: str = "") -> Dict[str, Any]:
    lang = "cs" if (lead.lang or "cs") == "cs" else "en"
    ind = industries.get_industry(industry_key)
    hours = parse_opening_hours(lead.opening_hours, lang)
    today_idx = datetime.now(timezone.utc).weekday()
    hours_today = hours[today_idx][1] if hours else ""
    phone = lead.phone or lead.phone_intl
    want_url = f"mailto:{s.owner_email}?subject=" + (
        "Chci%20tento%20web%20-%20" if lang == "cs" else "I%20want%20this%20website%20-%20") + slug
    wa_digits = "".join(ch for ch in (s.owner_whatsapp or "") if ch.isdigit())
    wa_url = (f"https://wa.me/{wa_digits}?text=" + (
        "Dobr%C3%BD%20den%2C%20m%C3%A1m%20z%C3%A1jem%20o%20web%20" if lang == "cs" else "Hello%2C%20I%27m%20interested%20in%20the%20website%20")
        + slug) if wa_digits else ""
    palette = ind["palette"]
    stars_pct = int(round((float(lead.rating or 0) / 5.0) * 100)) if lead.rating else 0
    ctx: Dict[str, Any] = {
        "lead": lead, "copy": copy, "lang": lang, "t": I18N[lang], "industry_key": industry_key,
        "industry_label": ind["label_cs"] if lang == "cs" else ind["label_en"],
        "palette": palette, "fonts": ind["fonts"], "hero_variant": ind.get("hero_variant", "block"),
        "hero_on_brand": ind.get("hero_variant", "block") in ("block", "split"),
        "hours": hours, "today_idx": today_idx, "hours_today": hours_today,
        "phone": phone, "phone_href": _phone_href(lead.phone_intl or phone),
        "email": best_email, "map_query": f"{lead.name}, {lead.address}" if lead.address else lead.name,
        "stars_pct": stars_pct, "year": datetime.now().year,
        "owner_name": s.owner_name, "owner_site": s.owner_site, "owner_email": s.owner_email,
        "want_url": want_url, "wa_url": wa_url, "form_webhook_url": s.form_webhook_url,
        "lead_id": lead.id or slug, "demo": demo, "slug": slug, "preview_url": preview_url,
        "og_image_url": f"{preview_url}og.png" if preview_url else "",
        "favicon_svg": favicon_svg(lead.name[:1].upper(), palette["brand"], "#FFFFFF"),
    }
    ctx.update(image_ctx)
    return ctx


def render_html(lead: Lead, copy: SiteCopy, industry_key: str, settings: Optional[Settings] = None, *,
                demo: bool = False, slug: str = "", preview_url: str = "", image_ctx: Optional[Dict[str, Any]] = None,
                best_email: str = "") -> str:
    s = settings or get_settings()
    industry_key = industry_key if industry_key in industries.INDUSTRIES else "obecny"
    image_ctx = image_ctx or images.image_context(industry_key, lead.lang, s, use_network=False)
    env = _env(s.templates_dir)
    tpl = env.get_template(f"industries/{industry_key}.html.j2")
    ctx = build_context(lead, copy, industry_key, s, demo=demo, slug=slug, preview_url=preview_url,
                        image_ctx=image_ctx, best_email=best_email)
    return tpl.render(**ctx)


def build_site(lead: Lead, copy: SiteCopy, industry_key: str, *, out_dir: Optional[Path] = None,
               slug: Optional[str] = None, demo: bool = False, settings: Optional[Settings] = None,
               use_images: bool = True, best_email: str = "", audit_summary: Optional[dict] = None,
               branches: int = 1, offer=None, owner_note: str = "") -> BuildResult:
    """Render and write ``<out_dir or PREVIEW_DIR>/<slug>/index.html`` + ``meta.json``."""
    s = settings or get_settings()
    industry_key = industry_key if industry_key in industries.INDUSTRIES else "obecny"
    slug = slug or make_slug(lead.name, lead.city, unique=lead.id or lead.address, lang=lead.lang or "cs")
    base_dir = Path(out_dir) if out_dir else s.preview_dir
    target = base_dir / slug
    target.mkdir(parents=True, exist_ok=True)
    preview_url = s.preview_url(slug)
    premium_id = ""
    lang = "cs" if (lead.lang or "cs") == "cs" else "en"
    if getattr(s, "premium_templates", False):
        try:
            premium_id = premium.pick_unique(lead, base_dir, slug=slug, branches=branches) or ""  # UNIQUE_CITY_V2
            if premium_id and not premium.available(premium_id, lang):
                premium_id = ""
        except Exception:  # výběr nesmí shodit build – spadne se na starý generátor
            log.exception("premium pick failed for %s", slug)
            premium_id = ""
    if premium_id:
        premium.install_assets(base_dir, premium_id)
        html = premium.render(lead, premium_id, s, slug=slug, preview_url=preview_url, best_email=best_email,
                              demo=demo, branches=branches)
        image_ctx = {"image_source": "premium"}
        if offer is not None and getattr(offer, "items", None):
            html = offer_inject.inject(html, premium_id, offer, lang)
    else:
        image_ctx = images.image_context(industry_key, lead.lang, s, seed=slug, use_network=use_images)
        html = render_html(lead, copy, industry_key, s, demo=demo, slug=slug, preview_url=preview_url,
                           image_ctx=image_ctx, best_email=best_email)
    html_path = target / "index.html"
    html_path.write_text(html, encoding="utf-8")
    meta = {
        "slug": slug, "url": preview_url, "name": lead.name, "lead_id": lead.id, "country": lead.country,
        "city": lead.city, "industry": industry_key, "lang": lead.lang, "market": lead.market, "demo": demo,
        "copy_source": copy.source, "image_source": image_ctx.get("image_source", "placeholder"),
        "premium_template": premium_id, "premium_niche": premium.niche_for(lead) if premium_id else "",
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "lead": lead.model_dump(), "copy": copy.model_dump(),
        "audit": audit_summary or {},
        "offer": offer.model_dump() if offer is not None and hasattr(offer, "model_dump") else {},
        "owner_note": owner_note or "",
    }
    meta_path = target / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Built %s (%d bytes) -> %s", slug, len(html), html_path)
    return BuildResult(slug=slug, path=str(target), url=preview_url, html_path=str(html_path),
                       html_bytes=len(html.encode("utf-8")), meta_path=str(meta_path), industry=industry_key,
                       lang=lead.lang or "cs", demo=demo, image_source=str(image_ctx.get("image_source", "placeholder")))
