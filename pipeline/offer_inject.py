"""Dosazení vytažené nabídky (``offer_extract.OfferData``) do vyrenderované premium šablony.

Šablony (``templates/premium/*.j2``) zůstávají beze změny - pracuje se až s hotovým HTML
náhledu jedné firmy. Pro každou šablonu je tu mapa selektorů: kde je sekce služeb, co je
jedna položka a kde v ní je název / popis / cena. Fotky položek zůstávají ze šablony.

Chování:
- položky z nabídky se dosadí do existujících slotů v pořadí,
- u „plain list" šablon (clone=True) se přebytečné položky nabídky doklonují (max ``max``)
  a nadbytečné slotové položky šablony se odstraní (pokud nabídka má aspoň 3 položky),
- u šablon s fotkou na položku (clone=False) se nadbytečné sloty šablony nechají,
- cena se přepíše jen když ji nabídka má, jinak zůstane text šablony („Cena na dotaz").

``inject(html, template_id, offer, lang)`` nikdy nevyhazuje výjimku - při chybě vrátí původní HTML.
"""
from __future__ import annotations

import copy as _copy
import logging
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

log = logging.getLogger("pipeline.offer_inject")

_LIST = dict(section="#sluzby", items="ul.radky > li", title="h3", text="p", price=".cena", clone=True, max=8)

MAP: Dict[str, Dict[str, Any]] = {
    "k-kalous":        dict(section="#sluzby", items="ol.fc-sr > li", title="span.n", text="span.p", price=".cena", clone=False),
    "v10-autoservis":  dict(section="#sluzby", items="ul.radky > li", title="h3", text="p", price=".cena", clone=False),
    "v13-autoservis":  dict(section="#sluzby", items="ul[data-sluzby] > li.sl", title="h3", text="p", price=".cena", clone=False),
    "v04-elektro":     _LIST,
    "v11-elektro":     _LIST,
    "v03-opravar":     _LIST,
    "v12-barber":      dict(section="#sluzby", items="ul > li", title="h3", text="p", price=".cena", clone=True, max=8),
    "v12-kadernictvi": dict(section="#sluzby", items="ul.karty-sluzeb > li.sluzba", title="h3", text="p", price=".cena", clone=False),
    "mesicek":         dict(section="#sluzby", items=".svc > .r", title="h3", text="p", price=None, clone=True, max=6),
    "v08-kvetiny":     dict(section="#sluzby", items="figure.karta-fan", title="figcaption .co", text="figcaption .veta",
                            price=None, clone=False, skip_without_title=True),
    "v11-kvetiny":     dict(section="#sluzby", items="figure.karta-fan", title="figcaption .co", text="figcaption .veta",
                            price=None, clone=False, skip_without_title=True),
    "v11-restaurace":  dict(section="#nabidka", items="article.menu-radek", title=".menu-text h3", text=".menu-text p",
                            price=None, clone=False),
    "v04-restaurace":  dict(section="#listek", items="ul.jidla > li", title="h3", text="p", price=".cena", clone=True, max=8,
                            empty_item='<li><div class="radek"><h3></h3><span class="tecky"></span><span class="cena"></span></div><p></p></li>',
                            empty_list="ul.jidla"),
}

PRICE_DEFAULT = {"cs": "Cena na dotaz", "en": "Price on request"}


def _set_text(node, value: str) -> None:
    if node is None:
        return
    node.clear()
    node.append(value)


def _fill(item_el, it, m: Dict[str, Any], lang: str) -> None:
    t = item_el.select_one(m["title"]) if m.get("title") else None
    _set_text(t, it.title)
    p = item_el.select_one(m["text"]) if m.get("text") else None
    if p is not None:
        if it.text:
            _set_text(p, it.text)
        # bez popisu: necháme text šablony jen u položek bez názvu-shody? ne - raději vyprázdnit, ať nelže
        else:
            _set_text(p, "")
    c = item_el.select_one(m["price"]) if m.get("price") else None
    if c is not None and it.price:
        _set_text(c, it.price)
    elif c is None and it.price:  # SEKCE_PATCH_V1: šablona nemá u položky místo na cenu -> přidat ji pod popis/název
        span = BeautifulSoup("", "html.parser").new_tag("span", attrs={"class": "pz-cena", "style": "display:block;margin-top:6px;font-weight:600;font-variant-numeric:tabular-nums"})
        span.string = it.price
        anchor = p if p is not None and p.parent is not None else t
        if anchor is not None and anchor.parent is not None:
            anchor.insert_after(span)
        else:
            item_el.append(span)
    # položka restaurace bez popisu: smazat prázdný <p>
    if p is not None and not it.text and m.get("empty_item"):
        p.decompose()


def _inject_about(html: str, offer) -> str:
    """SEKCE_PATCH_V1: blok O nás – text „o nás“ a první fotka firmy z původního webu (když existují)."""
    try:
        about = (getattr(offer, "about", "") or "").strip() if offer is not None else ""
        photos = [u for u in (getattr(offer, "photos", None) or []) if str(u).startswith("http")] if offer is not None else []
        if not about and not photos and not (getattr(offer, "brands", None) if offer is not None else None):
            return html
        soup = BeautifulSoup(html, "html.parser")
        t = soup.select_one("[data-onas-text]")
        if t is not None and about:
            _set_text(t, about)
        img = soup.select_one("img[data-onas-foto]")
        if img is not None and photos:
            img["src"] = str(photos[0])
        _inject_brands(soup, offer)
        return str(soup)
    except Exception as exc:          # noqa: BLE001
        log.warning("offer_inject O nás selhal: %s", exc)
        return html


def _inject_brands(soup, offer) -> None:
    """ZNACKY_PATCH_V1: sekce značek = značky z webu firmy; logo z jejich webu, jinak naše logo (když ho máme), jinak název."""
    brands = list(getattr(offer, "brands", None) or [])
    ul = soup.select_one("section.pz-zn ul")
    if not brands or ul is None:
        return
    logos = dict(getattr(offer, "brand_logos", None) or {})
    norm = lambda t: "".join(ch for ch in str(t).lower() if ch.isalnum())
    ours = {}
    for li in ul.find_all("li", recursive=False):
        im = li.find("img")
        ours[norm(im.get("alt", "") if im else li.get_text())] = li
    ul.clear()
    for b in brands[:12]:
        li = soup.new_tag("li")
        if logos.get(b):
            li.append(soup.new_tag("img", attrs={"src": logos[b], "alt": b, "loading": "lazy", "onerror": "this.replaceWith(this.alt)"}))
        elif norm(b) in ours and ours[norm(b)].find("img") is not None:
            li = ours[norm(b)]
        else:
            li["style"] = "color:inherit"
            li.string = b
        ul.append(li)


def inject(html: str, template_id: str, offer, lang: str = "cs") -> str:
    """Vrátí HTML s dosazenou nabídkou; při čemkoli nečekaném původní HTML."""
    return _inject_items(_inject_about(html, offer), template_id, offer, lang)


def _inject_items(html: str, template_id: str, offer, lang: str = "cs") -> str:
    try:
        if offer is None or not getattr(offer, "items", None):
            return html
        m = MAP.get(template_id)
        if not m:
            log.info("offer_inject: šablona %s nemá mapu selektorů - nabídka se nedosazuje", template_id)
            return html
        soup = BeautifulSoup(html, "html.parser")
        sec = soup.select_one(m["section"])
        if sec is None:
            return html
        items = list(offer.items)
        slots = [el for el in sec.select(m["items"])]
        if m.get("skip_without_title"):
            slots = [el for el in slots if el.select_one(m["title"]) is not None]
        if not slots and m.get("empty_item") and m.get("empty_list"):
            lst = sec.select_one(m["empty_list"])
            if lst is None:
                return html
            proto = BeautifulSoup(m["empty_item"], "html.parser").find()
            for _ in range(min(len(items), m.get("max", 8))):
                lst.append(_copy.copy(proto))
            slots = list(lst.find_all(recursive=False))
        if not slots:
            return html
        n = min(len(items), len(slots))
        for i in range(n):
            _fill(slots[i], items[i], m, lang)
        if m.get("clone") and len(items) > len(slots):
            proto = slots[-1]
            parent = proto.parent
            for it in items[len(slots):m.get("max", 8)]:
                clone = _copy.copy(proto)
                parent.append(clone)
                _fill(clone, it, m, lang)
        elif m.get("clone") and len(items) >= 3 and len(items) < len(slots):
            for el in slots[len(items):]:
                el.decompose()
        shown = len(slots) if not m.get("clone") else min(len(items), m.get("max", 8))
        rest = items[shown:]
        if rest:
            names = ", ".join(it.title for it in rest[:6]) + ("…" if len(rest) > 6 else "")
            p = soup.new_tag("p", attrs={"class": "dalsi-sluzby", "style": "margin:18px auto 0;max-width:72ch;font-size:15px;opacity:.75;text-align:center;padding:0 16px"})
            p.string = (f"…a dalších {len(rest)}: {names}" if lang == "cs" else f"…and {len(rest)} more: {names}")
            sec.append(p)
        return str(soup)
    except Exception as exc:          # noqa: BLE001
        log.warning("offer_inject selhal (%s): %s", template_id, exc)
        return html
