"""Premium šablony náhledů (schválené návrhy majitele, CZ + EN).

Výběr šablony podle oboru leadu (Google typy, kategorie z fronty, název) a pravidel níže,
render přes Jinja2 a instalace sdílených souborů do ``<PREVIEW_DIR>/_assets/p2/<id>/``.

Šablony:   pipeline/templates/premium/<id>.<cs|en>.html.j2
Soubory:   pipeline/premium_assets/<id>/...
Zdroj:     převodník ``tools/premium/build.py`` (jednorázově z HTML návrhů; .j2 jsou teď zdroj pravdy).

PRAVIDLA VÝBĚRU (výchozí hodnoty – majitel je zatím neschválil, mění se jen tady v RULES):
  autoservis     K (Kalous)  = prémiové servisy: značka z PREMIUM_BRANDS v názvu nebo v adrese webu
                 V10 (Píst)  = autorizované / značkové servisy: slovo z AUTHORISED_WORDS v názvu, kategorii nebo webu;
                               firmy s více pobočkami (branches > 1) střídat V10 a V13 (stabilně podle slugu)
                 V13 (Kardan)= ostatní; data-pobocky = počet poboček (výchozí 1)
  elektrikář     V11 = „firma do 2 lidí“ (heuristika: bez právní formy v názvu a < SMALL_FIRM_MAX_REVIEWS recenzí),
                       a jen ~20 % takových (podle slugu); jinak V04
  opravář        V03
  kadeřnictví    V12 (dámské kadeřnictví)
  restaurace     V04 / V11 rovnoměrně (podle slugu)
  květinářství   Měsíček / V08 / V11 rovnoměrně (podle slugu)
  barbershop     V12 barber
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

log = logging.getLogger("pipeline.premium")

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates" / "premium"
ASSETS = HERE / "premium_assets"
ASSET_NS = "p2"          # /_assets/p2/<id>/ – při nové generaci souborů zvýšit (cache)

# ---------------------------------------------------------------- pravidla (jedno místo)
RULES: Dict[str, Any] = {
    "PREMIUM_BRANDS": ["bmw", "mercedes", "mercedes-benz", "audi", "porsche", "lexus", "jaguar", "land rover",
                       "range rover", "volvo", "tesla", "maserati", "bentley", "ferrari", "lamborghini", "alfa romeo", "mini"],
    "AUTHORISED_WORDS": ["autorizovan", "značkov", "znackov", "authorised", "authorized", "dealer", "dealership",
                         "vertrags", "official service", "oficiální servis", "oficialni servis"],
    "LEGAL_FORMS": [r"s\.\s?r\.\s?o\.", r"spol\.\s?s\s?r\.\s?o", r"a\.\s?s\.", r"\bgmbh\b", r"\bltd\b", r"\binc\b",
                    r"\bllc\b", r"\bcorp\b", r"\bplc\b", r"\bco\.\b"],
    "SMALL_FIRM_MAX_REVIEWS": 30,
    "ELEKTRO_SMALL_SHARE": 0.20,     # podíl V11 mezi malými firmami
}

# ---------------------------------------------------------------- obory (premium „niche“)
NICHE_TYPES: Dict[str, List[str]] = {
    "autoservis": ["car_repair", "auto_repair_shop", "mechanic", "auto_body_shop", "car_service", "tire_shop",
                   "oil_change_service", "car_inspection_station", "auto_electrical_service", "truck_repair_shop"],
    "elektrikar": ["electrician", "electrical_contractor", "electrical_installation_service", "electrical_repair_shop"],
    "opravar": ["appliance_repair_service", "appliance_repair", "electronics_repair_shop", "washing_machine_repair_service",
                "appliance_store_repair"],
    "barber": ["barber_shop", "barber"],
    "kadernictvi": ["hair_salon", "hair_care", "beauty_salon_hair", "womens_hair_salon"],
    "restaurace": ["restaurant", "czech_restaurant", "italian_restaurant", "bistro", "brunch_restaurant", "steak_house",
                   "mediterranean_restaurant", "vegetarian_restaurant", "seafood_restaurant", "american_restaurant",
                   "european_restaurant", "fine_dining_restaurant", "french_restaurant", "spanish_restaurant",
                   "greek_restaurant", "lunch_restaurant", "family_restaurant", "gastropub"],
    "kvetinarstvi": ["florist", "flower_shop", "flower_delivery"],
}
NICHE_WORDS: Dict[str, List[str]] = {
    "autoservis": ["autoservis", "auto servis", "auto repair", "car repair", "garage", "mechanic", "pneuservis", "autodílna"],
    "elektrikar": ["elektrikář", "elektrikar", "elektroinstal", "electrician", "electrical contractor"],
    "opravar": ["oprav spotřebič", "opravy spotřebič", "oprava praček", "oprava pracek", "servis spotřebič", "appliance repair",
                "opravář", "opravar"],
    "barber": ["barber", "holičství", "holicstvi", "holič", "holic"],
    "kadernictvi": ["kadeřnictví", "kadernictvi", "dámské kadeř", "hair salon", "hairdresser", "kadeřnice"],
    "restaurace": ["restaurace", "restaurant", "bistro", "hospoda", "gastropub"],
    "kvetinarstvi": ["květinářství", "kvetinarstvi", "florist", "flower shop", "květiny", "kvetiny"],
}
# pořadí kontroly – specifičtější dřív (barber před kadeřnictvím)
NICHE_ORDER = ["barber", "kvetinarstvi", "opravar", "elektrikar", "autoservis", "kadernictvi", "restaurace"]

TEMPLATES_BY_NICHE: Dict[str, List[str]] = {
    "autoservis": ["k-kalous", "v10-autoservis", "v13-autoservis"],
    "elektrikar": ["v04-elektro", "v11-elektro"],
    "opravar": ["v03-opravar"],
    "kadernictvi": ["v12-kadernictvi"],
    "restaurace": ["v04-restaurace", "v11-restaurace"],
    "kvetinarstvi": ["mesicek", "v08-kvetiny", "v11-kvetiny"],
    "barber": ["v12-barber"],
}
NICHE_TEMPLATES = TEMPLATES_BY_NICHE  # zpětná kompatibilita názvu

LABELS = {
    "autoservis": ("Autoservis", "Car service"), "elektrikar": ("Elektrikář", "Electrician"),
    "opravar": ("Opravy spotřebičů", "Appliance repair"), "kadernictvi": ("Kadeřnictví", "Hair salon"),
    "restaurace": ("Restaurace", "Restaurant"), "kvetinarstvi": ("Květinářství", "Florist"), "barber": ("Barbershop", "Barbershop"),
}
DESCRIPTIONS = {
    "autoservis": ("Servis a opravy aut, objednání online.", "Car servicing and repairs – book online."),
    "elektrikar": ("Elektroinstalace, revize a opravy.", "Electrical installations, inspections and repairs."),
    "opravar": ("Opravy praček, myček, trub a dalších spotřebičů.", "Repairs of washing machines, dishwashers, ovens and other appliances."),
    "kadernictvi": ("Střih, barva a účesy – rezervace termínu online.", "Cuts, colour and styling – book online."),
    "restaurace": ("Polední menu, stálá nabídka a rezervace stolu.", "Lunch menu, à la carte and table reservations."),
    "kvetinarstvi": ("Kytice na míru, pokojové rostliny a květiny k oslavám.", "Bespoke bouquets, houseplants and flowers for celebrations."),
    "barber": ("Střih, úprava vousů a holení břitvou.", "Haircuts, beard trims and straight-razor shaves."),
}

# 6. pád měst z fronty (+ běžná města); neznámé město -> neutrální „ve vašem okolí“
CITY_LOC = {
    "praha": "v Praze", "brno": "v Brně", "ostrava": "v Ostravě", "plzeň": "v Plzni", "olomouc": "v Olomouci",
    "liberec": "v Liberci", "české budějovice": "v Českých Budějovicích", "hradec králové": "v Hradci Králové",
    "pardubice": "v Pardubicích", "zlín": "ve Zlíně", "ústí nad labem": "v Ústí nad Labem", "jihlava": "v Jihlavě",
    "kladno": "na Kladně", "most": "v Mostě", "opava": "v Opavě", "frýdek-místek": "ve Frýdku-Místku", "karviná": "v Karviné",
    "teplice": "v Teplicích", "děčín": "v Děčíně", "karlovy vary": "v Karlových Varech", "chomutov": "v Chomutově",
    "jablonec nad nisou": "v Jablonci nad Nisou", "mladá boleslav": "v Mladé Boleslavi", "prostějov": "v Prostějově",
    "přerov": "v Přerově", "třinec": "v Třinci", "kolín": "v Kolíně", "trutnov": "v Trutnově", "tábor": "v Táboře",
    "příbram": "v Příbrami", "znojmo": "ve Znojmě", "cheb": "v Chebu", "písek": "v Písku", "kroměříž": "v Kroměříži",
    "třebíč": "v Třebíči", "uherské hradiště": "v Uherském Hradišti", "vsetín": "ve Vsetíně", "šumperk": "v Šumperku",
}


def city_in(city: str, lang: str) -> str:
    c = (city or "").strip()
    if lang != "cs":
        return f"in {c} and the surrounding area" if c else "in your area"
    loc = CITY_LOC.get(c.lower())
    return f"{loc} a okolí" if loc else "ve vašem okolí"


_DAYS = {"cs": ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"],
         "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]}
_GENERIC_WORDS = r"(autoservis|auto servis|pneuservis|car service|auto repair|garage|elektro|elektrikář|elektroinstalace|" \
                 r"kadeřnictví|kadernictvi|hair salon|holičství|barbershop|barber shop|restaurace|restaurant|bistro|" \
                 r"květinářství|kvetinarstvi|florist|flowers|opravy|oprava|opravna|servis|spotřebičů|spotrebicu|spotřebiče|praček|pracek|" \
                 r"car|auto|repair|repairs|appliance|appliances|electrical|electric|salon|hair|barbers|kitchen)"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _bucket(key: str, n: int) -> int:
    return int(hashlib.sha1((key or "x").encode("utf-8")).hexdigest(), 16) % max(1, n)


def _frac(key: str) -> float:
    return (int(hashlib.sha1(("f:" + (key or "x")).encode("utf-8")).hexdigest(), 16) % 10000) / 10000.0


def niche_for(lead) -> Optional[str]:
    """Premium obor leadu, nebo None (pak se použije stávající generátor)."""
    types = [t for t in ([getattr(lead, "primary_type", "")] + list(getattr(lead, "types", []) or [])) if t]
    for n in NICHE_ORDER:
        if any(t in NICHE_TYPES[n] for t in types):
            # dámské kadeřnictví vs. barber: barber_shop v typech má přednost
            return n
    text = _norm(" ".join([getattr(lead, "category", "") or "", getattr(lead, "name", "") or ""]))
    for n in NICHE_ORDER:
        if any(_norm(w) in text for w in NICHE_WORDS[n]):
            return n
    return None


def _is_small_firm(lead) -> bool:
    name = (getattr(lead, "name", "") or "").lower()
    if any(re.search(p, name) for p in RULES["LEGAL_FORMS"]):
        return False
    cnt = getattr(lead, "rating_count", None) or 0
    return cnt < RULES["SMALL_FIRM_MAX_REVIEWS"]


def pick_template(lead, niche: Optional[str] = None, *, slug: str = "", branches: int = 1) -> Optional[str]:
    niche = niche or niche_for(lead)
    if not niche or niche not in TEMPLATES_BY_NICHE:
        return None
    key = slug or getattr(lead, "id", "") or getattr(lead, "name", "")
    opts = TEMPLATES_BY_NICHE[niche]
    if niche == "autoservis":
        hay = _norm(" ".join([getattr(lead, "name", "") or "", getattr(lead, "website", "") or ""]))
        if any(re.search(r"(?<![a-z])" + re.escape(_norm(b)) + r"(?![a-z])", hay) for b in RULES["PREMIUM_BRANDS"]):
            return "k-kalous"
        hay2 = _norm(" ".join([hay, getattr(lead, "category", "") or ""]))
        if any(_norm(w) in hay2 for w in RULES["AUTHORISED_WORDS"]):
            return "v10-autoservis"
        if branches and branches > 1:
            return ["v10-autoservis", "v13-autoservis"][_bucket(key, 2)]
        return "v13-autoservis"
    if niche == "elektrikar":
        if _is_small_firm(lead) and _frac(key) < RULES["ELEKTRO_SMALL_SHARE"]:
            return "v11-elektro"
        return "v04-elektro"
    return opts[_bucket(key, len(opts))]


# ---------------------------------------------------------------- data pro šablonu
def brand_name(name: str, city: str = "") -> str:
    """Krátký název do loga: bez právní formy a obecných slov oboru, max. 3 slova (město samo o sobě název není)."""
    s = name or ""
    for p in RULES["LEGAL_FORMS"]:
        s = re.sub(p, "", s, flags=re.I)
    s = re.sub(r"[,|–—-]\s*.*$", "", s).strip() if len(s) > 28 else s
    s2 = re.sub(r"\b" + _GENERIC_WORDS + r"\b", "", s, flags=re.I)
    s2 = re.sub(r"\s{2,}", " ", s2).strip(" ,.-–&")
    if len(s2) >= 2 and _norm(s2) != _norm(city) and not re.fullmatch(r"(&|and|a|u|the)", s2, flags=re.I):
        s = s2
    words = s.split()
    s = " ".join(words[:3]) if words else (name or "").strip()
    s = re.sub(r"(\s+(&|and|a|u|the|of))+$", "", s, flags=re.I).strip(" ,.-–&")
    return s.strip() or (name or "").strip()


def _hours(lead, lang: str) -> List[Tuple[str, str]]:
    from .generate_site import parse_opening_hours  # lokální import kvůli cyklu
    return parse_opening_hours(getattr(lead, "opening_hours", []) or [], lang)


def _num(lang: str, v: float) -> str:
    s = f"{v:.1f}"
    return s.replace(".", ",") if lang == "cs" else s


def build_context(lead, template_id: str, settings, *, slug: str, preview_url: str = "", best_email: str = "",
                  demo: bool = False, branches: int = 1) -> Dict[str, Any]:
    lang = "cs" if (getattr(lead, "lang", "") or "cs") == "cs" else "en"
    niche = next((n for n, ids in TEMPLATES_BY_NICHE.items() if template_id in ids), "")
    hours = _hours(lead, lang)
    hday = [v for _, v in hours] if hours else [""] * 7
    today = datetime.now(timezone.utc).weekday()
    phone = getattr(lead, "phone", "") or getattr(lead, "phone_intl", "") or ""
    phone_href = re.sub(r"[^\d+]", "", getattr(lead, "phone_intl", "") or phone)
    rating = getattr(lead, "rating", None)
    rcount = getattr(lead, "rating_count", None) or 0
    name = (getattr(lead, "name", "") or "").strip()
    brand = brand_name(name, getattr(lead, "city", "") or "")
    label_cs, label_en = LABELS.get(niche, ("", ""))
    desc_cs, desc_en = DESCRIPTIONS.get(niche, ("", ""))
    want_url = f"mailto:{settings.owner_email}?subject=" + (
        "Chci%20tento%20web%20-%20" if lang == "cs" else "I%20want%20this%20website%20-%20") + slug
    wa = "".join(ch for ch in (getattr(settings, "owner_whatsapp", "") or "") if ch.isdigit())
    wa_url = (f"https://wa.me/{wa}?text=" + ("Dobr%C3%BD%20den%2C%20m%C3%A1m%20z%C3%A1jem%20o%20web%20" if lang == "cs"
                                             else "Hello%2C%20I%27m%20interested%20in%20the%20website%20") + slug) if wa else ""
    city = (getattr(lead, "city", "") or "").strip()
    address = (getattr(lead, "address", "") or "").strip()
    maps_url = getattr(lead, "maps_url", "") or ""
    # MAPA_PATCH_V1: vložená mapa – adresa firmy, jinak jen město (oblast působnosti)
    from urllib.parse import quote_plus as _qp
    _mq = ", ".join(x for x in [name, address] if x) if address else city
    map_is_area = not address
    map_embed_url = (f"https://maps.google.com/maps?q={_qp(_mq)}&hl={'cs' if lang == 'cs' else 'en'}&z={12 if map_is_area else 16}&output=embed") if _mq else ""
    map_link_url = maps_url or (f"https://www.google.com/maps/search/?api=1&query={_qp(_mq)}" if _mq else "")
    dn = ' class="dnes"'
    rows = "".join(f"<span{dn if i == today else ''}>{escape(d)}</span><span{dn if i == today else ''}>{escape(v)}</span>"
                   for i, (d, v) in enumerate(hours))
    rows_m = "".join(f"<div><span>{escape(d)}</span><b>{escape(v)}</b></div>" for d, v in hours)
    biz_wa = re.sub(r"\D", "", getattr(lead, "phone_intl", "") or "")
    if biz_wa and not (getattr(lead, "phone_intl", "") or "").startswith("+"):
        biz_wa = ""
    ctx: Dict[str, Any] = {
        "lang": lang, "lead": lead, "niche": niche, "template_id": template_id,
        "A": f"../_assets/{ASSET_NS}/{template_id}/",
        "name": name, "brand": brand, "brand_up": brand.upper(),
        "page_title": f"{name} – {label_cs if lang == 'cs' else label_en}" + (f", {city}" if city else ""),
        "meta_description": f"{name}: " + (desc_cs if lang == "cs" else desc_en) + (f" {city}." if city else ""),
        "phone": phone, "phone_href": phone_href, "email": best_email or "", "address": address, "city": city,
        "maps_url": maps_url, "map_embed_url": map_embed_url, "map_is_area": map_is_area, "map_link_url": map_link_url, "maps_url_js": maps_url.replace("'", "%27") or "#", "website": getattr(lead, "website", "") or "",
        "hours": hours, "hday": hday, "hours_today": hday[today] if hours else "",
        "hours_rows": Markup(rows), "hours_rows_mesicek": Markup(rows_m),
        "rating": bool(rating and rating > 0), "rating_txt": _num(lang, float(rating)) if rating else "",
        "rating_raw": f"{float(rating):.1f}" if rating else "", "rating_pct": int(round(float(rating or 0) / 5 * 100)),
        "rating_count": rcount, "rating_count_raw": str(rcount) if rcount else "", "show_count": rcount >= 50,
        "rating_js": f"{float(rating):.1f}" if rating else "null", "rating_count_js": str(int(rcount)),
        "city_in": city_in(city, lang),
        "price_text": "Cena na dotaz" if lang == "cs" else "Price on request",
        "t_map": "Otevřít mapu" if lang == "cs" else "Open map",
        "wa_digits": biz_wa,
        "pobocky": max(1, min(3, int(branches or 1))),
        "lead_id": getattr(lead, "id", "") or slug, "form_webhook_url": getattr(settings, "form_webhook_url", "") or "",
        "owner_name": settings.owner_name, "owner_site": settings.owner_site, "owner_email": settings.owner_email,
        "want_url": want_url, "wa_url": wa_url, "show_banner": not demo, "slug": slug, "preview_url": preview_url,
        "year": datetime.now().year,
    }
    try:  # SEKCE_PATCH_V1 – recenze, O nás, značky
        from . import sekce as _sekce
        ctx.update(_sekce.context(lead, template_id, settings, ctx))
    except Exception:  # noqa: BLE001
        log.exception("sekce context selhal")
        ctx.update({"reviews": [], "reviews_js": "[]", "onas": None, "onas_text": "", "brands": [], "brands_title": ""})
    return ctx


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html", "j2", "html.j2"], default=True))


def available(template_id: str, lang: str) -> bool:
    return (TEMPLATES / f"{template_id}.{lang}.html.j2").is_file()


def render(lead, template_id: str, settings, *, slug: str, preview_url: str = "", best_email: str = "",
           demo: bool = False, branches: int = 1) -> str:
    ctx = build_context(lead, template_id, settings, slug=slug, preview_url=preview_url, best_email=best_email,
                        demo=demo, branches=branches)
    return _env().get_template(f"{template_id}.{ctx['lang']}.html.j2").render(**ctx)


def install_assets(preview_dir: Path, template_id: Optional[str] = None) -> List[str]:
    """Zkopíruje sdílené soubory šablon do ``<preview_dir>/_assets/p2/<id>/`` (jen chybějící nebo změněné)."""
    done: List[str] = []
    ids = [template_id] if template_id else sorted(p.name for p in ASSETS.iterdir() if p.is_dir())
    for tid in ids:
        src = ASSETS / tid
        if not src.is_dir():
            continue
        dst = Path(preview_dir) / "_assets" / ASSET_NS / tid
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            t = dst / f.relative_to(src)
            if t.exists() and t.stat().st_size == f.stat().st_size:
                continue
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            done.append(str(t))
    return done


# ---------------------------------------------------------------- UNIQUE_CITY_V2
# Jedna šablona oboru max. jednou v jednom městě. Obsazené = náhledy (meta.json) aktivních leadů z ACTIVE_IDS
# (n8n 02 je posílá v poli _active_ids: čekají na schválení, schválené, oslovené…; zamítnuté šablonu uvolní).
ACTIVE_IDS: set = set()
# pořadí náhradních šablon, když je výchozí obsazená (prémiová Kalous až nakonec)
FALLBACK_ORDER: Dict[str, List[str]] = {
    "autoservis": ["v13-autoservis", "v10-autoservis", "k-kalous"],
    "elektrikar": ["v04-elektro", "v11-elektro"],
}


def _city_key(c: str) -> str:
    return re.sub(r"\s+", " ", _norm(c or "")).strip()


def taken_in_city(base_dir, lead, niche: Optional[str]) -> Dict[str, str]:
    city = _city_key(getattr(lead, "city", "") or "")
    me = str(getattr(lead, "id", "") or "")
    out: Dict[str, str] = {}
    if not city or not niche or niche not in TEMPLATES_BY_NICHE:
        return out
    opts = set(TEMPLATES_BY_NICHE[niche])
    for mp in Path(base_dir).glob("*/meta.json"):
        try:
            m = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        lid = str(m.get("lead_id") or "")
        if not lid or lid == me or lid not in ACTIVE_IDS:
            continue
        t = m.get("premium_template") or ""
        if t in opts and _city_key(m.get("city") or "") == city:
            out[t] = str(m.get("name") or lid)
    return out


def pick_unique(lead, base_dir, *, slug: str = "", branches: int = 1) -> Optional[str]:
    niche = niche_for(lead)
    first = pick_template(lead, niche, slug=slug, branches=branches)
    if not first or niche not in TEMPLATES_BY_NICHE:
        return first
    taken = taken_in_city(base_dir, lead, niche)
    if first not in taken:
        return first
    for t in FALLBACK_ORDER.get(niche, TEMPLATES_BY_NICHE[niche]):
        if t not in taken:
            log.info("šablona %s je ve městě obsazená (%s) -> %s", first, taken[first], t)
            return t
    return first   # sem se nedojde – run.py lead předem přeskočí


def unique_check(lead, base_dir) -> Tuple[bool, str]:
    niche = niche_for(lead)
    if not niche or niche not in TEMPLATES_BY_NICHE:
        return True, ""
    taken = taken_in_city(base_dir, lead, niche)
    if all(t in taken for t in TEMPLATES_BY_NICHE[niche]):
        firms = ", ".join(sorted(set(taken.values())))
        return False, (f"všechny šablony oboru {LABELS.get(niche, (niche,))[0]} ({len(TEMPLATES_BY_NICHE[niche])}) jsou ve městě "
                       f"{getattr(lead, 'city', '')} už obsazené ({firms}) – čeká, až se některá uvolní (zamítnutí / firma nemá zájem)")
    return True, ""
