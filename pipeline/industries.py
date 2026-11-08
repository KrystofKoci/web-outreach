"""Industry knowledge: Google type -> industry key, visual tokens, fallback copy.

Industry keys (also the template names in ``templates/industries/``):

``remeslo``    trades - plumber, electrician, roofer, painter, builder ...
``salon``      hair & beauty - hair salon, barber, nails, spa, massage
``autoservis`` car repair, car wash, tyres, parts
``gastro``     restaurant, cafe, bakery, bar, pizza
``zdravi``     dentist, doctor, physio, vet, pharmacy, chiropractor
``obecny``     everything else

Adding an industry: add a key to ``INDUSTRIES`` (palette, fonts, copy in both
languages, ``queue_suggestions``), map its Google types in ``TYPE_TO_INDUSTRY``
and create ``templates/industries/<key>.html.j2`` (it can simply extend the
base template and override the ``hero_art`` block).

Adding a language (``es``/``de``): add ``services_<lang>``, ``faq_<lang>``,
``stock_<lang>`` and ``label_<lang>`` to each industry and fallback strings in
:mod:`pipeline.copy_writer`.
"""

from __future__ import annotations

from typing import Dict, List, Optional

INDUSTRY_KEYS = ("remeslo", "salon", "autoservis", "gastro", "zdravi", "obecny")

TYPE_TO_INDUSTRY: Dict[str, str] = {}

_TYPE_GROUPS = {
    "remeslo": [
        "plumber", "electrician", "roofing_contractor", "painter", "general_contractor", "locksmith",
        "moving_company", "hvac_contractor", "carpenter", "landscaper", "cleaning_service", "handyman",
        "flooring_contractor", "glazier", "masonry_contractor", "tiling_contractor", "window_installation_service",
        "insulation_contractor", "fence_contractor", "paving_contractor", "pest_control_service",
        "home_improvement_store", "garden_center", "chimney_sweep", "welder", "upholsterer", "tailor",
        "shoe_repair", "appliance_repair", "water_damage_restoration_service", "tree_service",
        "house_cleaning_service", "lawn_care_service", "pool_cleaning_service", "security_system_installer",
        "solar_energy_contractor", "plumbing_supply_store", "electrical_supply_store",
    ],
    "salon": [
        "hair_salon", "barber_shop", "beauty_salon", "nail_salon", "spa", "massage", "massage_therapist",
        "hair_care", "beautician", "skin_care_clinic", "tanning_studio", "wellness_center", "makeup_artist",
        "eyebrow_bar", "waxing_hair_removal_service", "day_spa", "sauna", "tattoo_shop", "body_art_service",
    ],
    "autoservis": [
        "car_repair", "car_wash", "tire_shop", "auto_parts_store", "car_dealer", "auto_body_shop",
        "mechanic", "motorcycle_repair_shop", "auto_glass_shop", "car_detailing_service", "oil_change_service",
        "towing_service", "auto_electrical_service", "truck_repair_shop", "car_inspection_station",
        "electric_vehicle_charging_station", "auto_painting_service",
    ],
    "gastro": [
        "restaurant", "cafe", "bakery", "bar", "pizza_restaurant", "coffee_shop", "fast_food_restaurant",
        "meal_takeaway", "meal_delivery", "pub", "bistro", "brunch_restaurant", "breakfast_restaurant",
        "italian_restaurant", "czech_restaurant", "vegetarian_restaurant", "vegan_restaurant", "sushi_restaurant",
        "steak_house", "hamburger_restaurant", "ice_cream_shop", "wine_bar", "tea_house", "confectionery",
        "sandwich_shop", "diner", "food_court", "dessert_shop", "cat_cafe", "brewery", "pastry_shop",
        "mexican_restaurant", "chinese_restaurant", "indian_restaurant", "thai_restaurant", "greek_restaurant",
        "seafood_restaurant", "asian_restaurant", "american_restaurant", "mediterranean_restaurant",
    ],
    "zdravi": [
        "dentist", "dental_clinic", "doctor", "physiotherapist", "veterinary_care", "pharmacy", "chiropractor",
        "medical_clinic", "hospital", "optician", "psychologist", "dermatologist", "pediatrician",
        "orthodontist", "physician", "drugstore", "medical_lab", "nutritionist", "midwife", "speech_therapist",
        "occupational_therapist", "acupuncturist", "general_practitioner", "wellness_clinic", "yoga_studio",
        "pilates_studio", "fitness_center", "gym", "sports_club", "personal_trainer", "dental_hygienist",
    ],
}
for _key, _types in _TYPE_GROUPS.items():
    for _t in _types:
        TYPE_TO_INDUSTRY[_t] = _key

# keywords for fuzzy matching on names/categories when types are missing
_NAME_HINTS = {
    "remeslo": ["instalat", "elektrik", "elektro", "pokrýva", "pokryva", "malíř", "malir", "zedn", "stavebn",
                "zámečn", "zamecn", "stěhov", "stehov", "topen", "truhlá", "truhla", "klempíř", "klempir",
                "úklid", "uklid", "zahradn", "podlah", "sklenář", "plumb", "electric", "roof", "paint", "builder",
                "contractor", "locksmith", "moving", "hvac", "carpent", "landscap", "cleaning", "handyman"],
    "salon": ["kadeř", "kader", "holič", "holic", "barber", "salon", "kosmet", "nehty", "nehtov", "manik", "pedik",
              "masáž", "masaz", "spa", "beauty", "hair", "nail", "lash", "brow", "massage"],
    "autoservis": ["autoserv", "pneu", "autoopr", "autodíl", "autodil", "myčka", "mycka", "karosá", "karosa",
                   "auto ", "car ", "tire", "tyre", "mechanic", "garage", "body shop", "detailing", "oil change"],
    "gastro": ["restaur", "kavár", "kavar", "café", "cafe", "pekár", "pekar", "cukrár", "cukrar", "pizz", "bistro",
               "hospod", "pivnic", "bar ", "bar", "coffee", "bakery", "pub", "grill", "burger", "sushi", "diner"],
    "zdravi": ["zubn", "stomat", "dent", "ordinac", "lékař", "lekar", "fyzio", "physio", "veterin", "lékárn",
               "lekarn", "pharm", "chiro", "clinic", "klinik", "doctor", "medical", "optik", "optic", "rehab"],
}


def industry_for(primary_type: str = "", types: Optional[List[str]] = None,
                 name: str = "", category: str = "") -> str:
    """Return the industry key for a lead (``obecny`` when nothing matches)."""
    for t in [primary_type or ""] + list(types or []):
        key = TYPE_TO_INDUSTRY.get((t or "").strip().lower())
        if key:
            return key
    hay = f"{name} {category} {primary_type}".lower()
    for key, hints in _NAME_HINTS.items():
        for h in hints:
            if h in hay:
                return key
    return "obecny"


# ---------------------------------------------------------------------------
# Per-industry definition
# ---------------------------------------------------------------------------
# Palette tokens: bg (page), ink (text), brand (dominant block colour), accent
# (CTA / highlights), soft (tinted section background). All pairs used for text
# are >= 4.5:1 contrast (checked by hand with WCAG formula).
INDUSTRIES: Dict[str, dict] = {
    "remeslo": {
        "label_cs": "Řemeslo a služby pro dům",
        "label_en": "Trades & home services",
        "palette": {"bg": "#FBF7F1", "ink": "#1B2A41", "brand": "#1B2A41", "accent": "#E8651A",
                    "accent_ink": "#FFFFFF", "soft": "#F1E9DE", "muted": "#5B6778", "line": "#DED4C6"},
        "fonts": {"link": "https://fonts.googleapis.com/css2?family=Barlow:wght@500;700;800&family=Barlow+Semi+Condensed:wght@700;800&display=swap",
                  "display": "'Barlow Semi Condensed', 'Poppins', 'Inter', system-ui, sans-serif",
                  "body": "'Barlow', 'Poppins', 'Inter', system-ui, sans-serif"},
        "hero_variant": "block",
        "icons": ["wrench", "bolt", "home", "clock", "shield", "truck"],
        "stock_cs": ["instalatér při práci", "řemeslník nářadí", "rekonstrukce koupelny"],
        "stock_en": ["plumber at work", "tradesman tools", "home renovation"],
        "services_cs": [
            ("Opravy a havárie", "Přijedeme, zjistíme příčinu a opravíme to na místě, pokud to jde."),
            ("Montáže a instalace", "Nové rozvody, zařizovací předměty i kompletní instalace."),
            ("Rekonstrukce", "Od návrhu po předání – domluvíme rozsah, termín a postup předem."),
            ("Pravidelná údržba", "Kontrola a servis, aby vás nepřekvapila porucha v nejhorší chvíli."),
            ("Poradenství", "Řekneme na rovinu, co je potřeba a co počká."),
        ],
        "services_en": [
            ("Repairs & emergencies", "We come out, find the cause and fix it on the spot whenever possible."),
            ("Installations", "New fittings, fixtures and complete installations done properly."),
            ("Renovations", "From plan to handover – scope, timing and approach agreed up front."),
            ("Maintenance", "Regular checks and servicing so a breakdown doesn't catch you out."),
            ("Honest advice", "We tell you straight what needs doing now and what can wait."),
        ],
        "faq_cs": [
            ("Jak rychle dokážete přijet?", "Záleží na vytížení a vzdálenosti. Zavolejte a domluvíme nejbližší možný termín."),
            ("Jak probíhá domluva ceny?", "Rozsah práce si projdeme předem a cenu řekneme dřív, než začneme."),
            ("Pracujete i o víkendu?", "[DOPLNÍTE]"),
        ],
        "faq_en": [
            ("How quickly can you come out?", "It depends on workload and distance. Call us and we'll agree the earliest slot."),
            ("How is the price agreed?", "We go through the scope first and tell you the price before we start."),
            ("Do you work weekends?", "[TO BE ADDED]"),
        ],
        "why_cs": ["Domluvený termín platí", "Po práci uklidíme", "Cena jasná předem"],
        "why_en": ["We turn up when we say", "We tidy up after the job", "Price agreed before we start"],
        "queue_suggestions": ["instalatér", "elektrikář", "pokrývač", "malíř pokojů", "zámečník", "stěhování",
                              "plumber", "electrician", "roofer", "painter decorator", "locksmith", "handyman",
                              "hvac contractor", "landscaper"],
    },
    "salon": {
        "label_cs": "Kadeřnictví, barber a kosmetika",
        "label_en": "Hair, barber & beauty",
        "palette": {"bg": "#FFF8F3", "ink": "#3A1F33", "brand": "#4A1942", "accent": "#B4476A",
                    "accent_ink": "#FFFFFF", "soft": "#F6E7E6", "muted": "#6E5566", "line": "#E9D6D6"},
        "fonts": {"link": "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Jost:wght@400;500;600&display=swap",
                  "display": "'Cormorant Garamond', 'Lora', Georgia, serif",
                  "body": "'Jost', 'Inter', system-ui, sans-serif"},
        "hero_variant": "editorial",
        "icons": ["scissors", "sparkle", "leaf", "clock", "heart", "star"],
        "stock_cs": ["kadeřnický salon interiér", "barber stříhání", "kosmetika péče o pleť"],
        "stock_en": ["hair salon interior", "barber haircut", "beauty skincare treatment"],
        "services_cs": [
            ("Střih a styling", "Střih podle tvaru obličeje a typu vlasů, foukaná a úprava na každý den."),
            ("Barvení a melír", "Barva, odrosty i jemné tóny – vždy s ohledem na zdraví vlasů."),
            ("Péče o vlasy", "Regenerace, hloubková výživa a poradenství, co dělat doma."),
            ("Úprava vousů", "Tvarování, zastřižení a péče o pleť pod vousy."),
            ("Kosmetické ošetření", "Čištění pleti, úprava obočí a péče, po které se budete cítit líp."),
        ],
        "services_en": [
            ("Cut & styling", "A cut that suits your face and hair type, with styling you can repeat at home."),
            ("Colour & highlights", "Full colour, roots and subtle tones – always with hair health in mind."),
            ("Hair treatments", "Repair, deep nourishment and advice on what to do between visits."),
            ("Beard grooming", "Shaping, trimming and care for the skin underneath."),
            ("Beauty treatments", "Facials, brows and the kind of care that makes you feel better."),
        ],
        "faq_cs": [
            ("Musím se objednat předem?", "Doporučujeme to – zavolejte nebo napište a najdeme vám termín."),
            ("Jak dlouho trvá barvení?", "Obvykle 1,5–3 hodiny podle délky vlasů a zvolené techniky."),
            ("Máte dárkové poukazy?", "[DOPLNÍTE]"),
        ],
        "faq_en": [
            ("Do I need to book in advance?", "We recommend it – call or message us and we'll find you a slot."),
            ("How long does colouring take?", "Usually 1.5–3 hours depending on hair length and technique."),
            ("Do you offer gift vouchers?", "[TO BE ADDED]"),
        ],
        "why_cs": ["Konzultace před každým zákrokem", "Čas jen pro vás", "Poradíme s domácí péčí"],
        "why_en": ["Consultation before every service", "Your time, undisturbed", "Advice for care at home"],
        "queue_suggestions": ["kadeřnictví", "barber", "kosmetika", "nehtové studio", "masáže",
                              "hair salon", "barber shop", "beauty salon", "nail salon", "massage therapist"],
    },
    "autoservis": {
        "label_cs": "Autoservis a pneuservis",
        "label_en": "Auto repair & tyres",
        "palette": {"bg": "#F3F4F6", "ink": "#15181C", "brand": "#15181C", "accent": "#D7263D",
                    "accent_ink": "#FFFFFF", "soft": "#E6E8EC", "muted": "#4D555F", "line": "#D5D9DF"},
        "fonts": {"link": "https://fonts.googleapis.com/css2?family=Inter+Tight:wght@500;700;800&family=Inter:wght@400;500;600&display=swap",
                  "display": "'Inter Tight', 'Inter', system-ui, sans-serif",
                  "body": "'Inter', system-ui, sans-serif"},
        "hero_variant": "split",
        "icons": ["car", "wrench", "gauge", "clock", "shield", "tire"],
        "stock_cs": ["autoservis mechanik", "pneuservis", "auto na zvedáku"],
        "stock_en": ["car mechanic garage", "tire service", "car on lift"],
        "services_cs": [
            ("Servis a opravy", "Běžný servis, brzdy, podvozek, rozvody – na všech běžných značkách."),
            ("Diagnostika", "Načteme závady, vysvětlíme, co znamenají, a navrhneme postup."),
            ("Pneuservis", "Přezutí, vyvážení, uskladnění pneumatik."),
            ("Příprava na STK", "Zkontrolujeme auto předem, aby prohlídka proběhla napoprvé."),
            ("Klimatizace", "Plnění, čištění a kontrola těsnosti."),
        ],
        "services_en": [
            ("Servicing & repairs", "Routine service, brakes, suspension, timing belts – all common makes."),
            ("Diagnostics", "We read the fault codes, explain what they mean and suggest the next step."),
            ("Tyres", "Fitting, balancing and seasonal storage."),
            ("Inspection prep", "We check the car beforehand so it passes first time."),
            ("Air conditioning", "Regas, cleaning and leak checks."),
        ],
        "faq_cs": [
            ("Musím se objednat?", "U větších oprav ano, zavolejte a domluvíme termín. Drobnosti řešíme podle vytížení."),
            ("Dostanu předem odhad ceny?", "Ano. Po diagnostice vám řekneme rozsah a cenu, než začneme opravovat."),
            ("Nabízíte náhradní vozidlo?", "[DOPLNÍTE]"),
        ],
        "faq_en": [
            ("Do I need an appointment?", "For bigger jobs yes – call and we'll book you in. Small things depend on the day."),
            ("Will I get an estimate first?", "Yes. After diagnostics we tell you the scope and price before any work starts."),
            ("Do you offer a courtesy car?", "[TO BE ADDED]"),
        ],
        "why_cs": ["Vysvětlíme, co a proč měníme", "Cena odsouhlasená předem", "Staré díly vám ukážeme"],
        "why_en": ["We explain what we replace and why", "Price approved before work", "We show you the old parts"],
        "queue_suggestions": ["autoservis", "pneuservis", "autoopravna", "myčka aut", "autodíly",
                              "auto repair", "car mechanic", "tire shop", "car wash", "auto body shop"],
    },
    "gastro": {
        "label_cs": "Restaurace, kavárny a pekárny",
        "label_en": "Restaurants, cafes & bakeries",
        "palette": {"bg": "#F7EEDF", "ink": "#22332A", "brand": "#22402E", "accent": "#C98A10",
                    "accent_ink": "#1E1A10", "soft": "#EFE2CC", "muted": "#5A6A5F", "line": "#DECFB4"},
        "fonts": {"link": "https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;0,9..144,700;1,9..144,500&family=Source+Sans+3:wght@400;600&display=swap",
                  "display": "'Fraunces', 'Lora', Georgia, serif",
                  "body": "'Source Sans 3', 'Inter', system-ui, sans-serif"},
        "hero_variant": "editorial",
        "icons": ["coffee", "fork", "bread", "clock", "leaf", "heart"],
        "stock_cs": ["kavárna interiér", "čerstvé pečivo", "restaurace talíř"],
        "stock_en": ["cafe interior", "fresh pastry", "restaurant plate"],
        "services_cs": [
            ("Denní nabídka", "Každý den něco čerstvého – co se vaří dnes, se dozvíte u nás nebo telefonicky."),
            ("Posezení uvnitř i venku", "Místo na kávu ve dvou i na oběd s celou partou."),
            ("S sebou", "Všechno, co máme, zabalíme i na cestu."),
            ("Oslavy a akce", "Narozeniny, firemní setkání nebo rodinný oběd – domluvíme menu i prostor."),
            ("Káva a dezerty", "Dobrá káva a něco sladkého k ní."),
        ],
        "services_en": [
            ("Daily menu", "Something fresh every day – ask in person or by phone what's cooking today."),
            ("Seating inside & out", "A table for coffee for two or lunch with the whole crew."),
            ("Takeaway", "Everything we make, packed to go."),
            ("Events & parties", "Birthdays, team gatherings or family lunches – menu and space arranged with you."),
            ("Coffee & desserts", "Good coffee and something sweet to go with it."),
        ],
        "faq_cs": [
            ("Dá se u vás rezervovat stůl?", "Ano, nejlépe telefonicky. Pro větší skupiny prosíme o rezervaci předem."),
            ("Vaříte i bezlepkově nebo vegetariánsky?", "[DOPLNÍTE]"),
            ("Máte parkování?", "[DOPLNÍTE]"),
        ],
        "faq_en": [
            ("Can I book a table?", "Yes, ideally by phone. For larger groups please book ahead."),
            ("Do you have vegetarian or gluten-free options?", "[TO BE ADDED]"),
            ("Is there parking?", "[TO BE ADDED]"),
        ],
        "why_cs": ["Čerstvé suroviny", "Místo, kam se vracíte", "Obsluha, která vás zná"],
        "why_en": ["Fresh ingredients", "A place you come back to", "Staff who know your name"],
        "queue_suggestions": ["restaurace", "kavárna", "pekárna", "cukrárna", "pizzerie", "hospoda",
                              "restaurant", "cafe", "bakery", "coffee shop", "pizza restaurant", "pub"],
    },
    "zdravi": {
        "label_cs": "Zdraví a péče",
        "label_en": "Health & care",
        "palette": {"bg": "#F4FAF8", "ink": "#12303A", "brand": "#0F6E68", "accent": "#0F6E68",
                    "accent_ink": "#FFFFFF", "soft": "#E1F1ED", "muted": "#4A6670", "line": "#CDE3DE"},
        "fonts": {"link": "https://fonts.googleapis.com/css2?family=Nunito:wght@500;700;800&display=swap",
                  "display": "'Nunito', 'Poppins', 'Inter', system-ui, sans-serif",
                  "body": "'Nunito', 'Inter', system-ui, sans-serif"},
        "hero_variant": "calm",
        "icons": ["heart", "shield", "tooth", "clock", "leaf", "plus"],
        "stock_cs": ["zubní ordinace", "lékař ordinace", "fyzioterapie"],
        "stock_en": ["dental clinic", "doctor office", "physiotherapy"],
        "services_cs": [
            ("Preventivní prohlídky", "Pravidelná kontrola odhalí problém dřív, než začne bolet."),
            ("Ošetření a léčba", "Postup vám vysvětlíme srozumitelně a předem."),
            ("Akutní případy", "Když to bolí, zavolejte – domluvíme nejbližší možný termín."),
            ("Dentální hygiena", "Profesionální čištění a nácvik správné péče doma."),
            ("Poradenství", "Zodpovíme otázky bez spěchu a bez odborného žargonu."),
        ],
        "services_en": [
            ("Check-ups", "Regular checks catch problems before they start to hurt."),
            ("Treatment", "We explain the plan clearly and before we begin."),
            ("Urgent appointments", "When it hurts, call – we'll find the earliest possible slot."),
            ("Dental hygiene", "Professional cleaning and guidance on care at home."),
            ("Advice", "Your questions answered without rush and without jargon."),
        ],
        "faq_cs": [
            ("Přijímáte nové pacienty?", "[DOPLNÍTE]"),
            ("Jak se objednat?", "Telefonicky v ordinačních hodinách nebo přes formulář níže – ozveme se zpět."),
            ("Máte smlouvy se zdravotními pojišťovnami?", "[DOPLNÍTE]"),
        ],
        "faq_en": [
            ("Are you accepting new patients?", "[TO BE ADDED]"),
            ("How do I book?", "By phone during opening hours or through the form below – we'll get back to you."),
            ("Which insurance do you accept?", "[TO BE ADDED]"),
        ],
        "why_cs": ["Vysvětlíme každý krok", "Objednání bez dlouhého čekání", "Klidné a čisté prostředí"],
        "why_en": ["Every step explained", "Appointments without long waits", "A calm, clean environment"],
        "queue_suggestions": ["zubní ordinace", "fyzioterapie", "veterinář", "praktický lékař", "lékárna",
                              "dentist", "physiotherapist", "veterinary clinic", "chiropractor", "family doctor"],
    },
    "obecny": {
        "label_cs": "Místní firma",
        "label_en": "Local business",
        "palette": {"bg": "#F7F8FA", "ink": "#1E2A3B", "brand": "#243B6B", "accent": "#C77800",
                    "accent_ink": "#FFFFFF", "soft": "#E9EDF4", "muted": "#55627A", "line": "#D9DFE8"},
        "fonts": {"link": "https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap",
                  "display": "'Manrope', 'Inter', system-ui, sans-serif",
                  "body": "'Manrope', 'Inter', system-ui, sans-serif"},
        "hero_variant": "block",
        "icons": ["check", "clock", "chat", "shield", "star", "pin"],
        "stock_cs": ["malá firma tým", "obchod interiér", "kancelář"],
        "stock_en": ["small business team", "shop interior", "office"],
        "services_cs": [
            ("Co nabízíme", "Stručný přehled toho, s čím se na nás můžete obrátit. [DOPLNÍTE]"),
            ("Poradenství", "Pomůžeme vybrat řešení, které dává smysl pro vaši situaci."),
            ("Individuální přístup", "Každou zakázku řešíme podle toho, co skutečně potřebujete."),
            ("Rychlá komunikace", "Na telefon i e-mail odpovídáme co nejdřív."),
            ("Spolehlivost", "Co slíbíme, to platí."),
        ],
        "services_en": [
            ("What we do", "A short overview of what you can come to us for. [TO BE ADDED]"),
            ("Advice", "We help you choose what actually makes sense for your situation."),
            ("Personal approach", "Every job handled according to what you really need."),
            ("Quick to respond", "We answer calls and e-mails as soon as we can."),
            ("Reliability", "What we promise, we deliver."),
        ],
        "faq_cs": [
            ("Jak vás nejlépe kontaktovat?", "Nejrychleji telefonicky; na zprávy z formuláře odpovídáme obvykle do jednoho pracovního dne."),
            ("Kde vás najdu?", "Adresa a mapa jsou níže na této stránce."),
            ("Jaká je otevírací doba?", "Aktuální otevírací dobu najdete v sekci výše."),
        ],
        "faq_en": [
            ("What's the best way to reach you?", "Phone is quickest; form messages are usually answered within one business day."),
            ("Where are you based?", "Address and map are further down this page."),
            ("What are your opening hours?", "Current hours are listed in the section above."),
        ],
        "why_cs": ["Osobní přístup", "Jasná domluva", "Místní firma, kterou znáte"],
        "why_en": ["Personal service", "Clear agreements", "A local business you know"],
        "queue_suggestions": ["účetní", "květinářství", "fotograf", "čistírna", "realitní kancelář",
                              "accountant", "florist", "photographer", "dry cleaner", "real estate agent"],
    },
}


def get_industry(key: Optional[str]) -> dict:
    """Return the industry definition (``obecny`` for unknown keys)."""
    return INDUSTRIES.get(key or "", INDUSTRIES["obecny"])


def label(key: str, lang: str) -> str:
    ind = get_industry(key)
    return ind["label_cs"] if lang == "cs" else ind["label_en"]


def queue_suggestions(key: Optional[str] = None) -> Dict[str, List[str]]:
    """Search phrases per industry (Czech + English) for seeding the n8n queue."""
    if key:
        return {key: list(get_industry(key)["queue_suggestions"])}
    return {k: list(v["queue_suggestions"]) for k, v in INDUSTRIES.items()}
