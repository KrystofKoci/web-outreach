# Kde začít: trhy, obory, města (analýza k 24. 10. 2026)

Cíl: ~30 náhledů denně, schvaluješ ve 3 dávkách, zakázky z celého světa, **Kostarika vyloučena**, spodní hranice 350 USD. Tahle analýza říká, kam těch 30 náhledů denně na začátku posílat a proč. Po 4 týdnech ji přepíše tvůj vlastní „vzorec“ (týdenní učení ze zakázek – `pipeline/learn.py`, list `weights`).

## 1. Kritéria výběru trhu

| Kritérium | Proč | Váha |
|---|---|---|
| Právní režim e-mailu | opt-out (USA) / adresa zveřejněná (CA, AU, NZ) / jen firmy (UK, IE) je bezpečné; opt-in (ČR, SK, většina EU) je riziko | 30 % |
| Cena, kterou trh unese | 400 USD je v USA/CA/AU/UK „levné“, v ČR je 10 000 Kč běžná spodní cena | 25 % |
| Hustota malých firem se špatným/žádným webem | řemeslníci, salony, servisy mimo velká města | 20 % |
| Časové pásmo vůči tobě (UTC−6 od 29. 10.) | odpovědi během tvého dne | 15 % |
| Jazyk | čeština (ty), angličtina (ty + agent); španělština/němčina až po doplnění šablon | 10 % |

## 2. Pořadí trhů

| Pořadí | Trh | Režim e-mailu | Cena (jednostránkový) | Pásmo vůči UTC−6 | Verdikt |
|---|---|---|---|---|---|
| **1** | **USA – střed a hory** (TX, OK, KS, MO, NE, CO, ID, UT, AZ, NM) | opt-out (CAN-SPAM) | 400 USD list, 350 floor; trh unese i 600–900 | 0 až +1 h | **Start hned.** Největší trh, nejbezpečnější právně, stejné pásmo. Vyhnout se NYC/LA/SF (přesyceno agenturami) |
| **2** | **Kanada – prérie a západ** (Calgary, Edmonton, Winnipeg, Saskatoon, Regina, Kelowna) | adresa zveřejněná + relevance k roli (CASL) | 400–500 USD ekv. (CAD) | 0 až −1 h | **Start v týdnu 1–2.** Patička musí říct, že adresa byla zveřejněná a nabídka se týká jejich podnikání |
| **3** | **ČR** (krajská a okresní města mimo Prahu) | opt-in – riziko, zmírněné schvalováním a objemem | 10 000 Kč list, 8 000 Kč floor | +7 h (odpovědi ráno tvého času) | **Start hned, ale max. 5–8 e-mailů denně.** Tvůj jazyk, tvoje reference, nejnižší cena. Slovensko stejně (SK, opt-in) |
| **4** | **UK + Irsko** (Leeds, Sheffield, Bristol, Nottingham, Glasgow, Cork, Limerick) | jen právnické osoby (Ltd) bez souhlasu | 320–400 GBP | +6 h | **Týden 2–3.** Filtrovat „Ltd“ v názvu/na webu; živnostníci (sole traders) ne |
| **5** | **Austrálie + Nový Zéland** (Adelaide, Perth, Hobart, Christchurch, Dunedin) | adresa zveřejněná + relevance (Spam Act) | 500–700 AUD | +16/17 h (odpovědi přes noc) | **Týden 3–4.** Dobrá cena; vše písemně, takže časový posun nevadí – odpovídáš na jejich ráno = tvůj večer |
| později | Španělsky mluvící LatAm (Mexiko, Kolumbie, Chile) | v praxi opt-out, slabší vymáhání | 250–400 USD – u hranice | 0 až +1 h | až po doplnění `es` šablon a textů agenta; ceny tlačí k floor 350 |
| později | Francie, Španělsko, Itálie | B2B na profesní adresy povolené s odhlášením | 350–600 EUR | +7 h | jazykové šablony fr/es/it |
| **ne** | Německo, Rakousko, Švýcarsko, Nizozemsko | de facto opt-in (UWG), aktivní abmahnung | – | – | `legal_regime=blocked` v pipeline |
| **nikdy** | **Kostarika** | – | – | – | **natvrdo vyloučeno v kódu (CR) – tvoje pravidlo** |

## 3. Obory (seřazené podle šance na zakázku)

Kritéria: podíl firem se zastaralým/žádným webem, hodnota zákazníka (ochota zaplatit 400 USD), jednoduchost webu (jedna stránka stačí), nízká konkurence agentur.

| Pořadí | Obor (šablona) | Proč | Typické dotazy do Places |
|---|---|---|---|
| 1 | **Řemeslo a stavebnictví** (`remeslo`) – instalatér, elektrikář, pokrývač, malíř, zedník, topenář, zámečník, stěhování, úklid, zahradník | nejhorší weby, vysoká hodnota zakázky (jedna oprava = cena webu), web = telefon + služby + území | plumber, electrician, roofing contractor, painter, handyman, HVAC, landscaper / instalatér, elektrikář, pokrývač, malíř, zedník |
| 2 | **Holičství a kadeřnictví** (`salon`) – barber, kadeřnictví, kosmetika, nehty, masáže | často jen Instagram/Facebook, bez webu → větev `no_website`; web s rezervací je silný argument | barber shop, hair salon, nail salon, beauty salon / holičství, kadeřnictví, kosmetika |
| 3 | **Autoservisy** (`autoservis`) – servis, pneuservis, myčka, autoelektrika | zastaralé weby z let 2008–2015, stálá poptávka | auto repair, tire shop, car wash / autoservis, pneuservis |
| 4 | **Zdraví** (`zdravi`) – zubař, fyzioterapie, veterinář, chiropraktik | vyšší ceny, ale vyšší nároky (texty, legislativa); v USA výborné | dentist, physiotherapy, veterinarian, chiropractor / zubní ordinace, fyzioterapie, veterinář |
| 5 | **Gastro a ubytování** (`gastro`) – kavárna, bistro, pizzerie, penzion | hodně firem, ale nízká marže a časté zavírání; web s menu a otevírací dobou | café, pizza, bistro, guest house / kavárna, pizzerie, penzion |
| 6 | Ostatní (`obecny`) – fitness studio, fotograf, účetní, autoškola | doplněk, když chybí objem | gym, photographer, accountant, driving school |

Doporučený mix prvních 30 náhledů denně: 40 % řemeslo, 25 % salony/holičství, 15 % autoservisy, 10 % zdraví, 10 % gastro/ostatní. Po 2 týdnech převezme mix `weights`.

## 4. Města – proč střední a menší

- Ve velkých městech (Praha, NYC, Londýn, Sydney) má většina firem web od agentury a dostává denně nabídky. V městech 30–300 tisíc obyvatel je podíl zastaralých webů vyšší a ochota odpovědět větší.
- Places Text Search vrací max. 60 výsledků na dotaz → na 30 náhledů denně (při ~50 % skipů) stačí 3–5 dotazů denně. Fronta rotuje města, aby se stejná firma neoslovovala dvakrát (dedupe přes place id + doména).

Startovní fronta (`sheets/queue.csv`): USA – Tulsa, Omaha, Boise, San Antonio, Kansas City, Colorado Springs, Albuquerque; CA – Calgary, Winnipeg, Saskatoon; ČR – Brno, Olomouc, Plzeň, Hradec Králové, Zlín, Jihlava, Pardubice; UK – Leeds, Sheffield, Bristol; AU – Adelaide, Perth. Každý řádek má `weight` (start 1,0), `enabled` a jazyk.

## 5. Ceny podle trhu (ceník je v `03_CENIK_A_MANTINELY_AGENTA.md`)

| Trh | Jednostránkový list | Floor | Vícestránkový | Správa |
|---|---|---|---|---|
| USA, CA, AU, NZ | 400 USD (CAD/AUD ekv.) | **350 USD** | od 970 USD | 29 USD/měs |
| UK, IE | 320 GBP / 370 EUR | 280 GBP / 320 EUR (≈350 USD) | od 770 GBP | 25 GBP/měs |
| ČR, SK | 10 000 Kč | **8 000 Kč** (≈350 USD) | od 23 000 Kč | 490 Kč/měs |
| LatAm (později) | 400 USD | 350 USD | od 970 USD | 29 USD/měs |

Floor je tvoje absolutní hranice; agent pod ni nejde a nad ní smí slevit jen výměnou (reference, platba předem, roční správa).

## 6. Co měřit od prvního dne (plní se do `leads` a `deals`, vyhodnocuje `learn.py`)

- Odpověď na 1. e-mail podle: země × obor × skóre auditu × varianta předmětu (A/B/C) × den/hodina odeslání.
- Odpověď → písemné jednání o ceně (`negotiating`) → zakázka (konverzní trychtýř) a dny mezi kroky.
- Cena nabídnutá vs. uzavřená (kolik slev agent dal).
- Podíl `no_website` větve (jen firmy s veřejným e-mailem), která skončila zakázkou, vs. `redesign`.
- Každou neděli: e-mail se shrnutím + nové váhy (krátké upozornění na WhatsApp); každé pondělí: report e-mailem.

Po 100 odeslaných e-mailech máš první směrodatná čísla; po 300 má smysl přepsat tuhle analýzu podle dat.

## 7. Realistická očekávání (můj odhad, ne slib)

- Odpověď: 3–8 % z osobních e-mailů s hotovým náhledem (USA/CA výš než ČR).
- Zakázka: 1–2 ze 100 odeslaných → při 30 e-mailech denně (≈600/měsíc) 6–12 jednostránkových webů měsíčně, tj. 2 400–4 800 USD + správa, pokud udržíš kvalitu náhledů.
- Největší riziko není právo ani technika, ale **kvalita náhledu** – 10 zkontrolovaných náhledů přinese víc než 100 ledabylých. Proto schvaluješ ty.

## Zdroje
- Google Maps Platform – ceník Places API (New), free kvóty 10 000 / 5 000 / 1 000 událostí měsíčně: https://developers.google.com/maps/billing-and-pricing/pricing
- Places API (New) – pole podle SKU, pageSize 20, max 60 výsledků: https://developers.google.com/maps/documentation/places/web-service/text-search
- Places API – zásady (ukládat jen place ID, atribuce): https://developers.google.com/maps/documentation/places/web-service/policies
- Právní rámec ČR/EU, USA, UK: `02_PRAVNI_CHECKLIST.md`
