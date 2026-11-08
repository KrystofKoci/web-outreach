"""Website copy for one preview: LLM (strict JSON) with a deterministic fallback.

Rules baked into the prompt (both languages):

* use ONLY the facts in the brief (name, category, city, hours, rating,
  phone, services known from the audit) - never invent prices, awards,
  years in business, certifications, team size or guarantees;
* unknown -> leave out, or write ``[DOPLNÍTE]`` / ``[TO BE ADDED]``;
* plain, local, friendly tone; no superlatives, no "leading provider".

The model answer is validated against :class:`SiteCopy`; on failure we retry
once with the validation error attached; if that fails too (or no LLM is
configured) :func:`fallback_copy` builds natural per-industry copy.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from . import industries
from .config import Settings, get_settings
from .llm import LLMError, LLMUnavailable, chat_json
from .models import FaqItem, Lead, ServiceItem, SiteCopy

log = logging.getLogger("pipeline.copy")

_FORBIDDEN_PATTERNS = {
    "cs": [r"\b(?:od|za)\s*\d+\s*(?:kč|czk|,-)", r"\d+\s*(?:kč|czk)\b", r"\b(?:od roku|již od|since)\s*(?:19|20)\d{2}",
           r"\b\d+\s*let (?:zkušeností|praxe|na trhu)", r"certifik", r"ocenění", r"nejlepší v", r"č\.\s*1\b",
           r"záruka \d+", r"\b\d+\s*% sleva"],
    "en": [r"[$£€]\s*\d+", r"\b\d+\s*(?:usd|gbp|eur|dollars?)\b", r"\bsince\s*(?:19|20)\d{2}",
           r"\b\d+\+?\s*years? (?:of )?(?:experience|in business)", r"certified", r"award[- ]winning",
           r"\b(?:the\s+)?best\s+(?:\w+\s+){0,3}in\s+\w+", r"#1\b", r"\d+\s*%\s*off", r"guarantee\w*\s+\d+"],
}

_SYSTEM = {
    "cs": """Jsi copywriter, který píše texty na jednoduché weby malých místních firem v Česku.
Napiš texty pro jednostránkový web firmy podle zadání.

PRAVIDLA (přísná):
- Používej VÝHRADNĚ fakta ze zadání. Nic si nevymýšlej.
- NIKDY neuváděj ceny, slevy, ocenění, certifikace, roky působení („od roku…“, „20 let zkušeností“), velikost týmu ani záruky, pokud nejsou výslovně v zadání.
- Co nevíš, vynech nebo napiš doslova [DOPLNÍTE].
- Piš přirozenou, místní, lidskou češtinou. Žádné superlativy, žádné „přední poskytovatel“, žádné marketingové fráze.
- Oslovuj zákazníka „vy“. Krátké věty. Konkrétní, srozumitelné.
- Odpověz POUZE platným JSON objektem přesně podle schématu, bez komentářů.
- Pokud zadání obsahuje "services_on_old_site", sekce "services" MUSÍ vycházet z těchto skutečných služeb firmy (stejné názvy, krátce přeformulovaný popis); ceny uveď jen ty, které jsou v zadání.
- Pokud zadání obsahuje "owner_instructions", je to pokyn majitele systému k tomuto návrhu a má přednost - zapracuj ho.

SCHÉMA:
{
 "headline": "max 70 znaků, co firma dělá a kde",
 "subheadline": "1–2 věty, max 160 znaků",
 "cta_primary": "text hlavního tlačítka, max 25 znaků (např. „Zavolat“, „Objednat se“)",
 "about_title": "nadpis sekce O nás",
 "about_text": "max 80 slov",
 "services": [{"title": "...", "text": "1–2 věty"}],   // 3 až 6 položek
 "why_us": ["krátký bod", "krátký bod", "krátký bod"],  // přesně 3
 "hours_title": "nadpis sekce otevírací doby",
 "contact_title": "nadpis kontaktní sekce",
 "faq": [{"q": "otázka", "a": "odpověď"}],              // 2 až 3
 "footer_note": "jedna krátká věta do patičky nebo prázdný řetězec"
}""",
    "en": """You are a copywriter for simple websites of small local businesses.
Write the copy for a one-page website based on the brief.

STRICT RULES:
- Use ONLY the facts in the brief. Do not invent anything.
- NEVER mention prices, discounts, awards, certifications, years in business ("since…", "20 years of experience"), team size or guarantees unless they are explicitly in the brief.
- If you don't know something, leave it out or write literally [TO BE ADDED].
- Plain, local, human tone. No superlatives, no "leading provider", no marketing clichés.
- Address the customer as "you". Short sentences. Concrete and clear.
- Respond ONLY with a valid JSON object matching the schema, no commentary.
- If the brief contains "services_on_old_site", the "services" section MUST be built from these real services (same names, briefly reworded description); mention only prices present in the brief.
- If the brief contains "owner_instructions", it is the system owner's instruction for this draft and takes priority - apply it.

SCHEMA:
{
 "headline": "max 70 characters, what the business does and where",
 "subheadline": "1–2 sentences, max 160 characters",
 "cta_primary": "main button text, max 25 characters (e.g. 'Call us', 'Book now')",
 "about_title": "About section heading",
 "about_text": "max 80 words",
 "services": [{"title": "...", "text": "1–2 sentences"}],   // 3 to 6 items
 "why_us": ["short point", "short point", "short point"],   // exactly 3
 "hours_title": "opening hours heading",
 "contact_title": "contact section heading",
 "faq": [{"q": "question", "a": "answer"}],                 // 2 to 3
 "footer_note": "one short footer sentence or empty string"
}""",
}


# ---------------------------------------------------------------------------
# brief
# ---------------------------------------------------------------------------
def build_brief(lead: Lead, industry_key: str, audit_facts: Optional[Dict[str, Any]] = None,
                offer=None, owner_note: str = "") -> Dict[str, Any]:
    """Facts the model is allowed to use. Everything else is forbidden."""
    ind = industries.get_industry(industry_key)
    lang = lead.lang or "cs"
    facts: Dict[str, Any] = {
        "business_name": lead.name,
        "category": lead.category or lead.primary_type.replace("_", " "),
        "industry": ind["label_cs"] if lang == "cs" else ind["label_en"],
        "city": lead.city,
        "address": lead.address,
        "country": lead.country,
        "phone": lead.phone or lead.phone_intl,
        "opening_hours": lead.opening_hours,
        "google_rating": lead.rating,
        "google_rating_count": lead.rating_count,
        "language": lang,
    }
    if audit_facts:
        # only safe, factual things from the old site
        for k in ("title", "h1", "meta_description"):
            v = audit_facts.get(k)
            if v:
                facts[f"old_site_{k}"] = str(v)[:200]
        if audit_facts.get("emails"):
            facts["email"] = audit_facts["emails"][0]
    if offer is not None and getattr(offer, "items", None):
        facts["services_on_old_site"] = [
            {"title": it.title, "text": it.text, **({"price": it.price} if it.price else {})} for it in offer.items]
        if getattr(offer, "specialties", None):
            facts["specialties"] = list(offer.specialties)
    if offer is not None and getattr(offer, "about", ""):
        facts["old_site_about"] = offer.about[:300]
    if (owner_note or "").strip():
        facts["owner_instructions"] = owner_note.strip()[:600]
    return {k: v for k, v in facts.items() if v not in (None, "", [], {})}


def brief_to_user_prompt(brief: Dict[str, Any], lang: str) -> str:
    head = "ZADÁNÍ (jediný zdroj faktů):" if lang == "cs" else "BRIEF (the only source of facts):"
    tail = ("\nNapiš texty v češtině. Vrať jen JSON." if lang == "cs"
            else "\nWrite the copy in English. Return JSON only.")
    return head + "\n" + json.dumps(brief, ensure_ascii=False, indent=1) + tail


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
def _normalise_llm_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    svcs = []
    for item in out.get("services") or []:
        if isinstance(item, dict):
            svcs.append({"title": str(item.get("title", "")).strip(), "text": str(item.get("text", "")).strip()})
        elif isinstance(item, str) and item.strip():
            svcs.append({"title": item.strip()[:60], "text": item.strip()})
    out["services"] = svcs
    faq = []
    for item in out.get("faq") or []:
        if isinstance(item, dict):
            q = item.get("q") or item.get("question") or ""
            a = item.get("a") or item.get("answer") or ""
            if q and a:
                faq.append({"q": str(q).strip(), "a": str(a).strip()})
    out["faq"] = faq
    if isinstance(out.get("why_us"), str):
        out["why_us"] = [p.strip() for p in re.split(r"[;\n]", out["why_us"]) if p.strip()]
    out.pop("reviews_line", None)
    out.pop("source", None)
    return out


def find_forbidden_claims(copy: SiteCopy, lang: str, brief: Dict[str, Any]) -> List[str]:
    """Return human-readable hits for invented prices / years / awards."""
    text = " ".join([copy.headline, copy.subheadline, copy.about_text, copy.footer_note]
                    + [s.title + " " + s.text for s in copy.services] + copy.why_us
                    + [f.q + " " + f.a for f in copy.faq]).lower()
    hits = []
    for pat in _FORBIDDEN_PATTERNS.get(lang, _FORBIDDEN_PATTERNS["en"]):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            hits.append(m.group(0))
    return hits


def validate_copy(data: Dict[str, Any], lang: str, brief: Dict[str, Any]) -> SiteCopy:
    copy = SiteCopy(**_normalise_llm_payload(data))
    hits = find_forbidden_claims(copy, lang, brief)
    if hits:
        raise ValueError("forbidden claims (not in brief): " + "; ".join(hits))
    return copy


# ---------------------------------------------------------------------------
# reviews line (code, not model)
# ---------------------------------------------------------------------------
def reviews_line(lead: Lead) -> str:
    if not lead.rating or not lead.rating_count:
        return ""
    if lead.lang == "cs":
        n = lead.rating_count
        word = "hodnocení"
        rating = f"{lead.rating:.1f}".replace(".", ",")
        return f"{rating} z 5 · {n} {word} na Google"
    return f"{lead.rating:.1f} out of 5 · {lead.rating_count} Google reviews"


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------
_FALLBACK = {
    "cs": {
        "headline": {
            "remeslo": "{category} – {city_loc}. Rychle, pořádně a na rovinu",
            "salon": "{name} – péče o vlasy a vzhled, {city}",
            "autoservis": "{name} – servis vašeho auta, {city_loc}",
            "gastro": "{name} – místo, kam se vracíte",
            "zdravi": "{name} – péče, které rozumíte",
            "obecny": "{name} – {category}, {city_loc}",
        },
        "headline_nocity": {
            "remeslo": "{category} – rychle, pořádně a na rovinu",
            "salon": "{name} – péče o vlasy a vzhled",
            "autoservis": "{name} – servis vašeho auta",
            "gastro": "{name} – místo, kam se vracíte",
            "zdravi": "{name} – péče, které rozumíte",
            "obecny": "{name} – {category}",
        },
        "subheadline": {
            "remeslo": "Zavolejte a domluvíme termín. Řekneme vám předem, co bude potřeba.",
            "salon": "Objednejte se telefonicky nebo přes formulář. Rádi vám poradíme, co vašim vlasům sedne.",
            "autoservis": "Diagnostika, servis i pneuservis pod jednou střechou. Cenu znáte dřív, než začneme.",
            "gastro": "Čerstvě připravené jídlo a dobrá káva. Přijďte posedět nebo si vezměte s sebou.",
            "zdravi": "Objednejte se telefonicky nebo přes formulář. Vysvětlíme vám každý krok.",
            "obecny": "Jsme místní firma. Ozvěte se nám telefonicky nebo přes formulář níže.",
        },
        "cta": {"remeslo": "Zavolat", "salon": "Objednat se", "autoservis": "Domluvit termín", "gastro": "Zavolat",
                "zdravi": "Objednat se", "obecny": "Zavolat"},
        "about_title": "Kdo jsme",
        "about": {
            "remeslo": "{name}: {category_l}{city_in}. Děláme práci, na kterou se můžete spolehnout: domluvený termín platí, rozsah i cenu si řekneme předem a po sobě uklidíme. Když si nejste jistí, co potřebujete, zavolejte – poradíme.",
            "salon": "{name}{city_par} je místo, kam si přijdete odpočinout a odejdete s účesem, který vám sedne. Před každým zákrokem se vás zeptáme, co chcete, a poradíme, co vašim vlasům prospěje.",
            "autoservis": "{name} se stará o auta{city_in}. Závadu najdeme, vysvětlíme vám ji lidsky a opravu uděláme za cenu, kterou odsouhlasíte předem. Staré díly vám ukážeme.",
            "gastro": "{name}{city_par} je podnik, kde vaříme z čerstvých surovin a známe své hosty jménem. Zastavte se na kávu, oběd nebo večeři – uvnitř i venku.",
            "zdravi": "{name}{city_par}: každý postup vysvětlíme srozumitelně a bez spěchu, abyste věděli, co se děje a proč. Objednat se můžete telefonicky nebo přes formulář.",
            "obecny": "{name} je místní firma{city_in}. Záleží nám na tom, aby domluva byla jasná a výsledek takový, jak jsme slíbili. Ozvěte se – rádi probereme, s čím vám můžeme pomoci.",
        },
        "hours_title": "Otevírací doba",
        "contact_title": "Kontakt",
        "footer_note": "",
    },
    "en": {
        "headline": {
            "remeslo": "{category} in {city} – fast, tidy and straightforward",
            "salon": "{name} – hair and beauty in {city}",
            "autoservis": "{name} – your car, looked after in {city}",
            "gastro": "{name} – the place you come back to in {city}",
            "zdravi": "{name} – care you understand",
            "obecny": "{name} – {category} in {city}",
        },
        "headline_nocity": {
            "remeslo": "{category} – fast, tidy and straightforward",
            "salon": "{name} – hair and beauty",
            "autoservis": "{name} – your car, looked after",
            "gastro": "{name} – the place you come back to",
            "zdravi": "{name} – care you understand",
            "obecny": "{name} – {category}",
        },
        "subheadline": {
            "remeslo": "Call us and we'll agree a time. We tell you up front what the job needs.",
            "salon": "Book by phone or through the form. We're happy to advise what suits your hair.",
            "autoservis": "Diagnostics, servicing and tyres under one roof. You know the price before we start.",
            "gastro": "Freshly made food and good coffee. Sit in or take away.",
            "zdravi": "Book by phone or through the form. We explain every step.",
            "obecny": "We're a local business. Reach us by phone or through the form below.",
        },
        "cta": {"remeslo": "Call us", "salon": "Book now", "autoservis": "Book a slot", "gastro": "Call us",
                "zdravi": "Book now", "obecny": "Call us"},
        "about_title": "Who we are",
        "about": {
            "remeslo": "{name}: {category_l}{city_in}. We do work you can rely on: the agreed time holds, scope and price are set before we start, and we clean up after ourselves. Not sure what you need? Call and we'll advise.",
            "salon": "{name} is a salon{city_in} where you come to unwind and leave with a look that suits you. Before every service we ask what you want and advise what will do your hair good.",
            "autoservis": "{name} looks after cars{city_in}. We find the fault, explain it in plain words and do the repair at a price you approve first. We show you the old parts.",
            "gastro": "{name} is a place{city_in} where we cook with fresh ingredients and know our regulars by name. Drop in for coffee, lunch or dinner – inside or out.",
            "zdravi": "{name} provides care{city_in}. We explain every procedure clearly and without rush, so you know what's happening and why. Book by phone or through the form.",
            "obecny": "{name} is a local business{city_in}. We care about clear agreements and results that match what we promised. Get in touch – we'll gladly talk through how we can help.",
        },
        "hours_title": "Opening hours",
        "contact_title": "Contact",
        "footer_note": "",
    },
}

def _city_phrases(city: str, lang: str) -> Dict[str, str]:
    """Phrases that stay grammatical without declining the city name.

    Czech locative/accusative forms of town names are irregular ("v Kolíně",
    "v Praze", "v Plzni"), so the fallback copy only uses the nominative in
    appositions: "pro Kolín a okolí" is avoided in favour of "Kolín a okolí"
    after a dash and "v oblasti Kolín a okolí" (standard Czech apposition).
    """
    if not city:
        return {"city": "", "city_loc": "", "city_in": "", "city_par": ""}
    if lang == "cs":
        return {"city": city, "city_loc": f"{city} a okolí", "city_in": f" v oblasti {city} a okolí", "city_par": f" ({city})"}
    return {"city": city, "city_loc": city, "city_in": f" in {city}", "city_par": f" ({city})"}


def fallback_copy(lead: Lead, industry_key: str, lang: Optional[str] = None) -> SiteCopy:
    """Deterministic, natural copy when the LLM is unavailable or invalid."""
    lang = lang or lead.lang or "cs"
    lang = "cs" if lang == "cs" else "en"
    key = industry_key if industry_key in industries.INDUSTRIES else "obecny"
    ind = industries.get_industry(key)
    fb = _FALLBACK[lang]
    cat = (lead.category or (ind["label_cs"] if lang == "cs" else ind["label_en"])).strip()
    cat_l = cat[:1].lower() + cat[1:] if cat else ""
    ph = _city_phrases(lead.city, lang)
    fmt = dict(name=lead.name, category=cat, category_l=cat_l, **ph)
    headline_tpl = fb["headline"][key] if lead.city else fb["headline_nocity"][key]
    headline = headline_tpl.format(**fmt)
    about = fb["about"][key].format(**fmt).replace("  ", " ")
    services = [ServiceItem(title=t, text=x, icon=icon)
                for (t, x), icon in zip(ind["services_cs" if lang == "cs" else "services_en"], ind["icons"])]
    faq = [FaqItem(q=q, a=a) for q, a in ind["faq_cs" if lang == "cs" else "faq_en"]][:3]
    copy = SiteCopy(
        headline=headline[:140],
        subheadline=fb["subheadline"][key],
        cta_primary=fb["cta"][key],
        about_title=fb["about_title"],
        about_text=about,
        services=services[:5],
        why_us=list(ind["why_cs" if lang == "cs" else "why_en"]),
        reviews_line=reviews_line(lead),
        hours_title=fb["hours_title"],
        contact_title=fb["contact_title"],
        faq=faq,
        footer_note=fb["footer_note"],
        source="fallback",
    )
    return copy


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------
def _assign_icons(copy: SiteCopy, industry_key: str) -> SiteCopy:
    icons = industries.get_industry(industry_key)["icons"]
    for i, svc in enumerate(copy.services):
        if not svc.icon or svc.icon == "check":
            svc.icon = icons[i % len(icons)]
    return copy


def write_copy(lead: Lead, industry_key: str, audit_facts: Optional[Dict[str, Any]] = None,
               settings: Optional[Settings] = None, use_llm: bool = True, offer=None,
               owner_note: str = "") -> SiteCopy:
    """Return validated :class:`SiteCopy` - LLM first, fallback otherwise. Never raises."""
    s = settings or get_settings()
    lang = "cs" if (lead.lang or "cs") == "cs" else "en"
    brief = build_brief(lead, industry_key, audit_facts, offer=offer, owner_note=owner_note)
    if use_llm and s.llm_configured:
        system = _SYSTEM[lang]
        user = brief_to_user_prompt(brief, lang)
        last_error = ""
        for attempt in (1, 2):
            try:
                prompt = user if attempt == 1 else (
                    user + ("\n\nPŘEDCHOZÍ ODPOVĚĎ BYLA NEPLATNÁ: " if lang == "cs" else "\n\nPREVIOUS ANSWER WAS INVALID: ")
                    + last_error + ("\nOprav to a vrať celý JSON znovu." if lang == "cs" else "\nFix it and return the full JSON again."))
                data = chat_json(system, prompt, "copy", max_tokens=1500, temperature=0.4, settings=s)
                copy = validate_copy(data, lang, brief)
                copy.reviews_line = reviews_line(lead)
                copy.source = "llm"
                log.info("Copy for %s: LLM ok (attempt %d)", lead.name, attempt)
                return _assign_icons(copy, industry_key)
            except LLMUnavailable:
                break
            except (ValidationError, ValueError, LLMError) as exc:
                last_error = str(exc)[:600]
                log.warning("Copy for %s: LLM attempt %d invalid: %s", lead.name, attempt, last_error[:200])
            except Exception as exc:          # noqa: BLE001 - LLM must never break the pipeline
                last_error = str(exc)[:600]
                log.warning("Copy for %s: LLM attempt %d failed: %s", lead.name, attempt, exc)
    copy = fallback_copy(lead, industry_key, lang)
    return _assign_icons(copy, industry_key)
