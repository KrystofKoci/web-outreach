"""SEKCE_PATCH_V1 – data pro nové sekce premium šablon: recenze z Google (pás), O nás (barevný blok), značky.

* Recenze: Places API (New) Place Details, pole ``reviews`` (max 5), jen když je PLACES_API_KEY a lead.id je place id.
  Bere recenze s textem a ≥ 4 hvězdami. Při chybě vrací [] (sekce se nezobrazí). REVIEWS_ENABLED=false vypne.
* O nás: obecný text oboru s městem; offer_inject ho přepíše textem „o nás“ z původního webu, když existuje.
  Každá šablona má vlastní barvu bloku (ONAS), aby se šablony od sebe lišily.
* Značky: jen opravář a kadeřnictví; loga v premium_assets/<id>/znacky/ (stáhne infra/stahni_loga.sh),
  když logo chybí, ukáže se název značky.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

log = logging.getLogger("pipeline.sekce")

# barva bloku O nás pro každou šablonu: pozadí, text, tlumený text, písmo nadpisu, fotka (relativně k assetům)
ONAS: Dict[str, Dict[str, str]] = {
    "k-kalous":        dict(bg="#C9A96B", fg="#0B0C10", mut="#3A3122", font="'Cormorant Garamond', serif", foto="kalous/cards/diagnostika.webp"),
    "mesicek":         dict(bg="#F2A33A", fg="#22140C", mut="#4A2E14", font="'Bodoni Moda', serif", foto="flowers/02_pivonka.jpg"),
    "v03-opravar":     dict(bg="#E8590C", fg="#1B1F24", mut="#3A2414", font="'Schibsted Grotesk', sans-serif", foto=""),
    "v04-elektro":     dict(bg="#6E8FFF", fg="#090B12", mut="#1E2647", font="'Archivo', sans-serif", foto="img/V04-elektro-dum-svetla.webp"),
    "v04-restaurace":  dict(bg="#D2452B", fg="#FFFFFF", mut="#FBE3DC", font="'DM Serif Display', serif", foto="img/V04-restaurace-k-kuchar.webp"),
    "v08-kvetiny":     dict(bg="#EDC9D2", fg="#2A1219", mut="#5A3540", font="'Bodoni Moda', serif", foto="img/V08-kvetiny-broskvova.webp"),
    "v10-autoservis":  dict(bg="#A31C1B", fg="#FFF7F3", mut="#F6D3CC", font="'Instrument Serif', serif", foto="img/V10-autoservis-dilna2.webp"),
    "v11-elektro":     dict(bg="#1546D9", fg="#FFFFFF", mut="#D6E0FF", font="'Archivo', sans-serif", foto="img/V11-elektro-meric.webp"),
    "v11-kvetiny":     dict(bg="#B4472A", fg="#FFFFFF", mut="#F6DCD2", font="'Unbounded', sans-serif", foto="img/V11-kvetiny-aranzovani.webp"),
    "v11-restaurace":  dict(bg="#3B2416", fg="#F6EEE3", mut="#D9C6B3", font="'DM Serif Display', serif", foto="img/V11-restaurace-kuchar.webp"),
    "v12-barber":      dict(bg="#C8421C", fg="#FFF8F3", mut="#F8D7CB", font="'Inter Tight', sans-serif", foto="img/V12-barber-strih-3.webp"),
    "v12-kadernictvi": dict(bg="#7444E8", fg="#FFFFFF", mut="#E4DAFF", font="'Bricolage Grotesque', sans-serif", foto="img/V12-kadernictvi-sluzba-konzultace.webp"),
    "v13-autoservis":  dict(bg="#E8B517", fg="#14202A", mut="#3B3410", font="'Unbounded', sans-serif", foto="img/V13-autoservis-dilna.webp"),
}

ONAS_TEXT = {
    "autoservis": ("Jsme autoservis {kde}. Starají se o vás mechanici, kteří auta opravují roky a řeknou vám rovnou, co je potřeba a co počká. Před každou opravou víte cenu, po ní dostanete auto zpátky čisté a s vysvětlením, co jsme dělali.",
                   "We are a car service {kde}. Your car is in the hands of mechanics with years of experience who tell you straight what needs doing and what can wait. You know the price before any repair and get the car back clean, with a clear explanation."),
    "elektrikar": ("Elektroinstalace děláme {kde} pro domácnosti i firmy. Záleží nám na bezpečnosti, čistotě práce a na tom, aby vám všechno fungovalo dlouhé roky. Domluvíme se rychle, termín dodržíme a po sobě uklidíme.",
                   "We do electrical work {kde} for homes and businesses. We care about safety, tidy work and installations that keep working for years. Quick to arrange, on time, and we clean up after ourselves."),
    "opravar": ("Opravujeme domácí spotřebiče {kde}. Pračky, myčky, sporáky i chladničky raději opravíme, než abyste kupovali nové. Na místě zjistíme závadu, řekneme cenu a většinu oprav uděláme hned.",
                "We repair home appliances {kde}. Washing machines, dishwashers, cookers and fridges are often worth fixing rather than replacing. We diagnose on site, give you the price and fix most faults straight away."),
    "kadernictvi": ("Jsme kadeřnictví {kde}. Každá návštěva začíná rozhovorem o tom, co chcete a co vašim vlasům sedí. Pracujeme s profesionální kosmetikou a poradíme vám i s péčí doma.",
                    "We are a hair salon {kde}. Every visit starts with a chat about what you want and what suits your hair. We use professional products and help you look after your hair at home."),
    "restaurace": ("Vaříme {kde} z poctivých surovin a hlavně s chutí. Rádi vás uvidíme na obědě, večeři i při oslavě. Každý den připravujeme jídla tak, abyste k nám chodili znovu.",
                   "We cook {kde} with honest ingredients and real care. Join us for lunch, dinner or a celebration – we cook every day so that you want to come back."),
    "kvetinarstvi": ("Jsme květinářství {kde}. Kytice vážeme z čerstvých květin, na počkání i na objednávku. Poradíme s výběrem pro každou příležitost a květiny vám rádi doručíme.",
                     "We are a florist {kde}. We arrange bouquets from fresh flowers, on the spot or to order, help you choose for every occasion and are happy to deliver."),
    "barber": ("Jsme barbershop {kde}. Střih i úprava vousů bez spěchu, s péčí o detail a tak, aby vám to sedělo i za tři týdny.",
               "We are a barbershop {kde}. Haircuts and beard trims without rushing, with attention to detail, so it still looks right three weeks later."),
}

# značky: (soubor loga v znacky/, název, barva textu když logo chybí)
BRANDS: Dict[str, List[tuple]] = {
    "v03-opravar": [("bosch.svg", "Bosch", "#ED0007"), ("siemens.svg", "Siemens", "#009999"), ("whirlpool.svg", "Whirlpool", "#272425"),
                    ("electrolux.svg", "Electrolux", "#041E41"), ("samsung.svg", "Samsung", "#1428A0"), ("lg.svg", "LG", "#A50034"),
                    ("beko.svg", "Beko", "#0070C0"), ("miele.svg", "Miele", "#8C0014"), ("gorenje.svg", "Gorenje", "#1B1B1B"),
                    ("aeg.svg", "AEG", "#E2001A"), ("candy.svg", "Candy", "#E2001A"), ("zanussi.svg", "Zanussi", "#1B1B1B")],
    "v12-kadernictvi": [("loreal.svg", "L’Oréal Professionnel", "#000000"), ("", "Wella Professionals", "#1B1B1B"),
                        ("", "Schwarzkopf Professional", "#1B1B1B"), ("", "Davines", "#1B1B1B"), ("", "Kérastase", "#1B1B1B"),
                        ("", "Olaplex", "#1B1B1B")],
}
BRANDS_TITLE = {
    "v03-opravar": ("Opravujeme všechny běžné značky", "We repair all common brands"),
    "v12-kadernictvi": ("Pracujeme s profesionální kosmetikou", "We work with professional products"),
}


def fetch_reviews(lead, settings, lang: str) -> List[Dict[str, Any]]:
    if os.environ.get("REVIEWS_ENABLED", "true").lower() in ("0", "false", "no"):
        return []
    key = getattr(settings, "places_api_key", None)
    pid = (getattr(lead, "id", "") or "").strip()
    if not key or not pid or not pid.startswith("ChIJ") and len(pid) < 20:
        return []
    try:
        import requests
        r = requests.get(f"https://places.googleapis.com/v1/places/{pid}",
                         params={"languageCode": "cs" if lang == "cs" else "en"},
                         headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "reviews"},
                         timeout=getattr(settings, "http_timeout", 15) or 15)
        if r.status_code >= 400:
            log.warning("reviews %s: HTTP %s %s", pid, r.status_code, r.text[:200])
            return []
        out = []
        for rv in r.json().get("reviews") or []:
            text = ((rv.get("text") or {}).get("text") or (rv.get("originalText") or {}).get("text") or "").strip()
            stars = int(rv.get("rating") or 0)
            if not text or stars < 4:
                continue
            out.append({"jmeno": ((rv.get("authorAttribution") or {}).get("displayName") or "Google").strip(),
                        "hvezdy": stars, "text": text[:420] + ("…" if len(text) > 420 else ""),
                        "kdy": (rv.get("relativePublishTimeDescription") or "").strip()})
        return out[:5]
    except Exception as exc:  # noqa: BLE001 – recenze nesmí shodit build
        log.warning("reviews %s selhaly: %s", pid, exc)
        return []


def context(lead, template_id: str, settings, ctx: Dict[str, Any]) -> Dict[str, Any]:
    lang = ctx.get("lang", "cs")
    niche = ctx.get("niche", "")
    reviews = [] if ctx.get("show_banner") is False else fetch_reviews(lead, settings, lang)
    on = ONAS.get(template_id, ONAS["v03-opravar"])
    city = ctx.get("city") or ""
    kde = (ctx.get("city_in") or ("v " + city)) if lang == "cs" else (f"in {city}" if city else "locally")
    txt = ONAS_TEXT.get(niche, ONAS_TEXT["opravar"])[0 if lang == "cs" else 1]
    if not city:
        txt = txt.replace(" {kde}", "")
    brands = [dict(soubor=f, nazev=n, barva=c) for f, n, c in BRANDS.get(template_id, [])]
    return {
        "reviews": reviews,
        "reviews_js": json.dumps(reviews, ensure_ascii=False).replace("</", "<\\/"),
        "onas": on, "onas_text": txt.format(kde=kde),
        "brands": brands, "brands_title": BRANDS_TITLE.get(template_id, ("", ""))[0 if lang == "cs" else 1],
    }
