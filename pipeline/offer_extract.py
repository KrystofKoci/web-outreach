"""Extrakce nabídky (služby / produkty / ceny) z původního webu firmy.

Krok auditu „extrakce nabídky": stáhne domovskou stránku + až 4 podstránky, které
vypadají jako služby / ceník / menu, vytáhne čistý text a nechá LLM sestavit JSON
s konkrétními položkami nabídky. Výsledek se **neukládá do šablon** - použije se jen
pro náhled dané firmy (``offer_inject.inject`` nahradí texty služeb v premium šabloně,
``copy_writer`` ho dostane do zadání).

Pravidla:
- ceny jen takové, které jsou doslova na webu (kontrolujeme, že číslice ceny jsou v textu),
- žádné vymýšlení položek - když web nabídku nemá, vrátí se prázdný seznam,
- poznámka majitele (``owner_note`` ze schvalovací stránky) se do LLM předá jako pokyn,
  co přidat / odebrat / přejmenovat.

Nikdy nevyhazuje výjimku - chyba = prázdná nabídka + warning.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError

from .config import Settings, get_settings
from .llm import LLMError, LLMUnavailable, chat_json

log = logging.getLogger("pipeline.offer")

MAX_SUBPAGES = 4
MAX_TEXT_CHARS = 14000
MAX_ITEMS = 8
# alias modelu v LiteLLM; "copy" = Sonnet. Levnější: v litellm/config.yaml přidej alias "extract" (Haiku) a nastav OFFER_MODEL_ALIAS=extract
MODEL_ALIAS = os.environ.get("OFFER_MODEL_ALIAS", "copy").strip() or "copy"

# slova v odkazech, která ukazují na nabídku (cs + en + de/es jen okrajově)
_LINK_WORDS = re.compile(
    r"(slu[žz]b|cen[íi]k|nab[íi]dk|menu|j[íi]deln|poledn|produkt|sortiment|co\s*d[ěe]l[áa]me|"
    r"service|pricing|price|products?|offer|what\s*we\s*do|treatments?|catalog)", re.I)


class OfferItem(BaseModel):
    title: str = Field(min_length=2, max_length=70)
    text: str = Field(default="", max_length=260)
    price: str = Field(default="", max_length=40)


class OfferData(BaseModel):
    """Nabídka vytažená z původního webu. ``kind``: services | menu | products | mixed."""

    kind: str = "services"
    items: List[OfferItem] = Field(default_factory=list)
    specialties: List[str] = Field(default_factory=list)   # např. značky aut, styly, speciality kuchyně
    opening_hours: List[str] = Field(default_factory=list)
    about: str = ""                                          # 1-3 věty „o nás" z původního webu
    photos: List[str] = Field(default_factory=list)          # URL firemních fotek z původního webu (max 8)
    brands: List[str] = Field(default_factory=list)          # ZNACKY_PATCH_V1: značky, které firma na webu uvádí (max 12)
    brand_logos: Dict[str, str] = Field(default_factory=dict)  # značka -> URL loga z jejich webu
    source_urls: List[str] = Field(default_factory=list)
    source: str = "none"          # llm | none
    warnings: List[str] = Field(default_factory=list)

    @property
    def has_items(self) -> bool:
        return bool(self.items)

    def stats(self, lang: str = "cs") -> str:
        """[11 položek · 3 stránky · 5 fotek · o nás] – pro schvalovací stránku a rozhodnutí 1 vs. více stránek."""
        if lang == "cs":
            bits = [f"{len(self.items)} položek", f"{len(self.source_urls)} str. čteno", f"{len(self.photos)} fotek"] + (["o nás ✓"] if self.about else [])
        else:
            bits = [f"{len(self.items)} items", f"{len(self.source_urls)} pages read", f"{len(self.photos)} photos"] + (["about ✓"] if self.about else [])
        return "[" + " · ".join(bits) + "]"

    def summary(self, lang: str = "cs", limit: int = 900) -> str:
        """Krátký text pro CRM (sloupec ``extracted_offer``) a schvalovací stránku."""
        if not self.items and not self.about and not self.photos and not self.brands:
            return ""
        parts = []
        for it in self.items:
            p = it.title + (f" ({it.price})" if it.price else "")
            parts.append(p)
        s = self.stats(lang) + " " + "; ".join(parts)
        if self.specialties:
            s += (" | speciality: " if lang == "cs" else " | specialties: ") + ", ".join(self.specialties[:6])
        if self.brands:
            s += (" | značky: " if lang == "cs" else " | brands: ") + ", ".join(self.brands[:12])
        if self.about:
            s += (" | o nás: " if lang == "cs" else " | about: ") + self.about[:220]
        return s[:limit]


def empty_offer(*warnings: str) -> OfferData:
    return OfferData(warnings=[w for w in warnings if w])


# ---------------------------------------------------------------------------
# stahování a čištění textu
# ---------------------------------------------------------------------------
def _fetch_html(url: str, s: Settings) -> str:
    from .audit import _fetch  # stejná hlavička / timeout jako audit
    resp = _fetch(url, s)
    ctype = resp.headers.get("Content-Type", "")
    if resp.status_code >= 400 or ("html" not in ctype and "xml" not in ctype and ctype):
        return ""
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text or ""


def page_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "iframe", "header", "footer", "nav", "form"]):
        t.decompose()
    lines: List[str] = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "li", "p", "td", "th", "dt", "dd", "span", "a", "div"]):
        if el.find(["p", "li", "div", "h1", "h2", "h3"]):
            continue                       # jen listy stromu, ať se text nezdvojuje
        txt = " ".join(el.get_text(" ", strip=True).split())
        if 2 <= len(txt) <= 400:
            tag = el.name
            prefix = "## " if tag in ("h1", "h2", "h3", "h4") else "- " if tag in ("li", "dt", "td") else ""
            lines.append(prefix + txt)
    out, seen = [], set()
    for ln in lines:
        k = ln.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(ln)
    return "\n".join(out)


_BAD_IMG = re.compile(r"(logo|icon|favicon|sprite|arrow|button|banner-cookie|pixel|spacer|loading|placeholder|\.svg|\.gif|data:)", re.I)


def company_photos(html: str, base_url: str, limit: int = 8) -> List[str]:
    """URL firemních fotek: og:image + větší <img> (podle width/height nebo názvu), bez log a ikon."""
    soup = BeautifulSoup(html or "", "html.parser")
    out: List[str] = []
    seen = set()

    def add(u: str) -> None:
        if not u:
            return
        full = urljoin(base_url, u.strip().split(" ")[0]).split("#")[0]
        if full in seen or _BAD_IMG.search(full) or not full.lower().startswith("http"):
            return
        seen.add(full)
        out.append(full)

    for m in soup.find_all("meta", attrs={"property": "og:image"}):
        add(m.get("content", ""))
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        try:
            w, h = int(re.sub(r"\D", "", str(img.get("width") or 0)) or 0), int(re.sub(r"\D", "", str(img.get("height") or 0)) or 0)
        except ValueError:
            w = h = 0
        if (w and w < 250) or (h and h < 180):
            continue
        if _BAD_IMG.search(" ".join([src, str(img.get("alt") or ""), str(img.get("class") or "")])):
            continue
        add(src)
        if len(out) >= limit:
            break
    return out[:limit]


KNOWN_BRANDS = [
    # spotřebiče
    "Bosch", "Siemens", "Whirlpool", "Electrolux", "Samsung", "LG", "Beko", "Miele", "Gorenje", "AEG", "Candy", "Zanussi",
    "Indesit", "Hotpoint", "Ariston", "Philips", "Sharp", "Panasonic", "Haier", "Hisense", "Smeg", "Liebherr", "Teka",
    "Fagor", "Amica", "Mora", "ETA", "Hoover", "Gaggenau", "Neff", "Sencor", "Daewoo", "Tefal", "De'Longhi", "Jura",
    "Dyson", "Brandt", "Vestel", "Grundig", "Toshiba", "Vaillant", "Junkers", "Viessmann", "Baxi", "Protherm",
    # kadeřnictví
    "L'Oréal", "Wella", "Schwarzkopf", "Davines", "Kérastase", "Olaplex", "Redken", "Matrix", "Goldwell", "Kevin Murphy",
    "Alfaparf", "Revlon", "Joico", "Paul Mitchell", "Moroccanoil", "Londa", "Indola", "Framesi", "Inebrya", "Milk_shake",
    "Label.m", "Biolage", "Aveda", "Keune", "Selective", "Fanola", "Tigi", "Lakmé", "Subrina", "Artègo", "Nioxin", "Sebastian",
]


def _bnorm(t: str) -> str:
    import unicodedata as _ud
    t = _ud.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def image_candidates(html: str, base_url: str) -> List[tuple]:
    """ZNACKY_PATCH_V1: (url, popis) všech <img>/<svg image> – popis = alt + title + název souboru; pro hledání log značek."""
    soup = BeautifulSoup(html or "", "html.parser")
    out: List[tuple] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        if not src or src.startswith("data:"):
            continue
        full = urljoin(base_url, src.strip().split(" ")[0]).split("#")[0]
        if not full.lower().startswith("http"):
            continue
        label = " ".join([str(img.get("alt") or ""), str(img.get("title") or ""), full.rsplit("/", 1)[-1]])
        out.append((full, label))
    return out


def match_brands(names: List[str], imgs: List[tuple], text: str) -> tuple:
    """Vrátí (značky, {značka: url loga}). Značka musí být v textu webu nebo u obrázku (nic nevymýšlí);
    k uvedeným značkám se přidají známé značky, které jsou na webu jen jako logo."""
    hay_text = _bnorm(text)
    found: List[str] = []
    logos: Dict[str, str] = {}

    def add(n: str) -> None:
        k = _bnorm(n)
        if len(k) < 2 or any(_bnorm(f) == k for f in found):
            return
        img = next((u for u, lab in imgs if k in _bnorm(lab)), "")
        if not img and k not in hay_text:
            return
        found.append(n)
        if img:
            logos[n] = img

    for n in names:
        add(n)
    for n in KNOWN_BRANDS:
        k = _bnorm(n)
        if any(k in _bnorm(lab) for _, lab in imgs):
            add(n)
    return found[:12], {k: v for k, v in logos.items() if k in found[:12]}


def candidate_subpages(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    base_host = urlparse(base_url).netloc.lower().replace("www.", "")
    scored: List[tuple] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full = urljoin(base_url, href).split("#")[0]
        host = urlparse(full).netloc.lower().replace("www.", "")
        if host != base_host or full in seen or re.search(r"\.(pdf|jpg|jpeg|png|gif|webp|zip|docx?)($|\?)", full, re.I):
            continue
        label = (a.get_text(" ", strip=True) + " " + href).lower()
        if not _LINK_WORDS.search(label):
            continue
        seen.add(full)
        score = len(_LINK_WORDS.findall(label)) + (2 if a.find_parent(["nav", "header"]) else 0)
        scored.append((-score, full))
    scored.sort()
    return [u for _, u in scored[:MAX_SUBPAGES]]


def collect_site_text(url: str, s: Settings, home_html: Optional[str] = None) -> tuple:
    """Vrátí (text, použité_url, warnings, photos). Obrázky pro loga značek ukládá do collect_site_text.last_imgs."""
    collect_site_text.last_imgs = []
    warnings: List[str] = []
    urls: List[str] = []
    photos: List[str] = []
    try:
        html = home_html if home_html is not None else _fetch_html(url, s)
    except Exception as exc:          # noqa: BLE001
        return "", [], [f"nabídka: domovská stránka nejde stáhnout ({str(exc)[:60]})"], []
    if not html:
        return "", [], ["nabídka: domovská stránka je prázdná"], []
    chunks = [("## [HOME]", page_text(html))]
    urls.append(url)
    photos = company_photos(html, url)
    collect_site_text.last_imgs = image_candidates(html, url)
    for sub in candidate_subpages(html, url):
        try:
            sh = _fetch_html(sub, s)
        except Exception as exc:      # noqa: BLE001
            warnings.append(f"nabídka: {sub} nejde stáhnout ({str(exc)[:40]})")
            continue
        if sh:
            chunks.append((f"## [PAGE {sub}]", page_text(sh)))
            urls.append(sub)
            collect_site_text.last_imgs += image_candidates(sh, sub)
            for ph in company_photos(sh, sub):
                if ph not in photos and len(photos) < 8:
                    photos.append(ph)
    text = "\n".join(h + "\n" + t for h, t in chunks)
    return text[:MAX_TEXT_CHARS], urls, warnings, photos


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
_SYSTEM = {
    "cs": """Jsi analytik, který z textu webu malé místní firmy vytahuje její NABÍDKU.
Vrať POUZE platný JSON podle schématu. Nic nevymýšlej - jen to, co je v textu.

SCHÉMA:
{
 "kind": "services" | "menu" | "products" | "mixed",
 "items": [{"title": "název služby/jídla/produktu (max 60 znaků)", "text": "1 věta, co to je, podle webu (max 200 znaků, může být prázdné)", "price": "cena DOSLOVA z webu včetně měny, nebo prázdný řetězec"}],
 "specialties": ["krátké heslo"],   // značky, specializace, speciality kuchyně - max 6, jen pokud jsou na webu
 "brands": ["Bosch"],   // značky výrobců, které firma opravuje / používá / prodává – jen výslovně uvedené na webu, max 12, jinak []
 "opening_hours": ["Po-Pá 8:00-17:00"],   // jen pokud je na webu, jinak []
 "about": "1-3 věty o firmě (kdo jsou, od kdy, čím se liší) PŘEVZATÉ z webu, max 300 znaků; prázdné, když web nic takového nemá"
}

PRAVIDLA:
- 3 až 8 položek, seřazené podle důležitosti (nejdřív hlavní služby). Když web žádnou nabídku nepopisuje, vrať "items": [].
- Slučuj duplicity, vynech obecné věci (kontakt, o nás, cookies, novinky).
- "price" vyplň JEN když je cena u položky výslovně uvedená. Jinak "".
- Piš česky, pokud je web česky; jinak v jazyce webu. Krátce, bez marketingových frází.""",
    "en": """You are an analyst extracting the OFFER of a small local business from its website text.
Return ONLY valid JSON matching the schema. Invent nothing - only what the text says.

SCHEMA:
{
 "kind": "services" | "menu" | "products" | "mixed",
 "items": [{"title": "service/dish/product name (max 60 chars)", "text": "1 sentence describing it per the site (max 200 chars, may be empty)", "price": "price VERBATIM from the site incl. currency, or empty string"}],
 "specialties": ["short tag"],   // brands, specialisations, cuisine - max 6, only if on the site
 "brands": ["Bosch"],   // manufacturer brands the business repairs / uses / sells – only if explicitly on the site, max 12, else []
 "opening_hours": ["Mon-Fri 8:00-17:00"],   // only if on the site, else []
 "about": "1-3 sentences about the business (who they are, since when, what sets them apart) TAKEN from the site, max 300 chars; empty if the site has none"
}

RULES:
- 3 to 8 items ordered by importance (main services first). If the site describes no offer, return "items": [].
- Merge duplicates, skip generic pages (contact, about, cookies, news).
- Fill "price" ONLY when a price is explicitly given next to the item. Otherwise "".
- Write in the site's language. Short, no marketing fluff.""",
}


def _owner_note_block(note: str, lang: str) -> str:
    note = (note or "").strip()
    if not note:
        return ""
    if lang == "cs":
        return ("\n\nPOKYN MAJITELE SYSTÉMU K TOMUTO NÁVRHU (má přednost, zapracuj do položek - přidej/odeber/přejmenuj; "
                "ceny přidej jen pokud je majitel výslovně uvedl):\n" + note[:600])
    return ("\n\nSYSTEM OWNER'S INSTRUCTION FOR THIS DRAFT (takes priority - add/remove/rename items accordingly; "
            "add prices only if the owner stated them explicitly):\n" + note[:600])


def _validate(data: Dict[str, Any], source_text: str, owner_note: str) -> OfferData:
    items_raw = data.get("items") or []
    items: List[OfferItem] = []
    hay = re.sub(r"\s+", "", (source_text or "") + (owner_note or ""))
    for raw in items_raw[:MAX_ITEMS]:
        if not isinstance(raw, dict):
            continue
        title = " ".join(str(raw.get("title", "")).split())[:70]
        text = " ".join(str(raw.get("text", "")).split())[:260]
        price = " ".join(str(raw.get("price", "")).split())[:40]
        if price:
            digits = re.sub(r"\D", "", price)
            if not digits or digits not in re.sub(r"\D", "", hay):
                price = ""            # cena není na webu ani v poznámce -> ven
        if len(title) < 2:
            continue
        items.append(OfferItem(title=title, text=text, price=price))
    kind = str(data.get("kind") or "services")
    if kind not in ("services", "menu", "products", "mixed"):
        kind = "services"
    spec = [" ".join(str(x).split())[:40] for x in (data.get("specialties") or []) if str(x).strip()][:6]
    hours = [" ".join(str(x).split())[:60] for x in (data.get("opening_hours") or []) if str(x).strip()][:7]
    about = " ".join(str(data.get("about") or "").split())[:300]
    brands = [" ".join(str(x).split())[:40] for x in (data.get("brands") or []) if str(x).strip()][:12]
    return OfferData(kind=kind, items=items, specialties=spec, opening_hours=hours, about=about, brands=brands)


def extract_offer(url: str, lang: str = "cs", *, settings: Optional[Settings] = None, home_html: Optional[str] = None,
                  owner_note: str = "", use_llm: bool = True) -> OfferData:
    """Hlavní vstup. Nikdy nevyhazuje výjimku."""
    s = settings or get_settings()
    lang = "cs" if (lang or "cs") == "cs" else "en"
    if not url and not (owner_note or "").strip():
        return empty_offer()
    text, urls, warnings, photos = ("", [], [], [])
    if url:
        text, urls, warnings, photos = collect_site_text(url, s, home_html)
    if not text.strip() and not (owner_note or "").strip():
        return empty_offer(*warnings, "nabídka: web nemá použitelný text")
    if not (use_llm and s.llm_configured):
        return empty_offer(*warnings, "nabídka: LLM není nastaveno - nabídka se nevytahuje")
    user = (("TEXT WEBU:\n" if lang == "cs" else "WEBSITE TEXT:\n") + (text or "(žádný text / no text)")
            + _owner_note_block(owner_note, lang)
            + ("\n\nVrať jen JSON." if lang == "cs" else "\n\nReturn JSON only."))
    last = ""
    for attempt in (1, 2):
        try:
            prompt = user if attempt == 1 else user + "\n\nPREVIOUS ANSWER INVALID: " + last + "\nReturn the full JSON again."
            data = chat_json(_SYSTEM[lang], prompt, MODEL_ALIAS, max_tokens=1200, temperature=0.2, settings=s)
            offer = _validate(data if isinstance(data, dict) else {}, text, owner_note)
            offer.source = "llm"
            offer.source_urls = urls
            offer.photos = photos
            offer.warnings = warnings
            try:  # ZNACKY_PATCH_V1
                offer.brands, offer.brand_logos = match_brands(offer.brands, getattr(collect_site_text, "last_imgs", []), text)
            except Exception as exc:  # noqa: BLE001
                log.warning("značky z %s: %s", url, exc)
                offer.brands, offer.brand_logos = [], {}
            log.info("Nabídka z %s: %d položek (pokus %d)", url, len(offer.items), attempt)
            return offer
        except LLMUnavailable:
            o = empty_offer(*warnings, "nabídka: LLM nedostupné"); o.photos = photos; o.source_urls = urls; return o
        except (ValidationError, ValueError, LLMError) as exc:
            last = str(exc)[:400]
            log.warning("Nabídka z %s: pokus %d neplatný: %s", url, attempt, last[:160])
        except Exception as exc:      # noqa: BLE001
            last = str(exc)[:400]
            log.warning("Nabídka z %s: pokus %d selhal: %s", url, attempt, exc)
    o = empty_offer(*warnings, f"nabídka: LLM nevrátilo použitelný JSON ({last[:80]})"); o.photos = photos; o.source_urls = urls
    return o


def offer_from_dict(d: Any) -> OfferData:
    """Tolerantní načtení (např. z meta.json)."""
    try:
        if isinstance(d, str):
            d = json.loads(d)
        return OfferData(**(d or {}))
    except Exception:                 # noqa: BLE001
        return empty_offer()
