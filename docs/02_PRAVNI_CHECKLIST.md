# Právní checklist pro oslovování firem (ČR/EU, USA, UK)

Stav: 24. 10. 2026. **Toto je obecné upozornění, ne právní rada.** Rozhodnutí, jak oslovovat, je tvoje; systém je postavený tak, aby šel provozovat v nejbezpečnější variantě a aby se dal kdykoliv zpřísnit.

## 0. Co jsi zvolil a jaké to má riziko

Zvolená varianta pro ČR: **individuální e-mail na veřejně uvedený firemní kontakt, pod vlastním jménem, s identifikací, s odhlášením, v malých dávkách.**

Co to znamená právně: podle zákona č. 480/2004 Sb. (§ 7) je obchodní sdělení e-mailem **opt-in** – souhlas předem – a to i vůči firmám; výjimka je jen pro vlastní zákazníky. ÚOOÚ dlouhodobě říká, že kontakt dohledaný na webu není souhlas. Pokuta až 10 mil. Kč pro právnickou osobu, až 100 000 Kč pro fyzickou; odpovídá i ten, kdo rozesílku objednal nebo z ní má prospěch. Chystaný zákon o digitální ekonomice (sněmovní tisk 776) rámec přebírá a sankce zvyšuje (až 20 mil. EUR / 4 % obratu), zatím není účinný.

Jak to vypadá v praxi: ÚOOÚ řeší v drtivé většině **hromadný spam na základě stížností** (v roce 2023 1 388 podnětů, pokuty celkem 8,6 mil. Kč, většina méně závažných případů skončila napomenutím). Jednotlivá, osobně psaná nabídka firmě na její obecný kontakt vede ke stížnosti výjimečně – ale **riziko není nula** a nelze ho slíbit.

Dvě věci, které riziko zásadně snižují a systém je vynucuje:
1. **Nic z toho není hromadné ani anonymní**: každý e-mail schválíš ty, každý je psaný konkrétně k jedné firmě (její web, její problém, její náhled), max. 15 prvních e-mailů denně.
2. **Okamžité a trvalé odhlášení**: odkaz + odpověď „NEMÁM ZÁJEM“ → status `unsubscribed`, blocklist, už nikdy.

## 1. Česko a EU – co musí každý e-mail splňovat (systém to dělá automaticky)

| Povinnost | Zdroj | Jak je to v systému |
|---|---|---|
| Zřetelně označit jako obchodní sdělení | § 7 odst. 4 písm. a) z. 480/2004 Sb. | Patička: „Toto je obchodní sdělení – jednorázová individuální nabídka…“ (`emails/cz/footer_legal.txt`) |
| Jasná identifikace odesílatele | § 7 odst. 4 písm. b) | Jméno, IČO, sídlo, e-mail – **doplň IČO a sídlo do `.env` / patičky před prvním odesláním** |
| Platná adresa pro odmítnutí dalších sdělení | § 7 odst. 4 písm. c) | Odkaz `/webhook/odhlasit?id=…&t=…` + instrukce odpovědět „NEMÁM ZÁJEM“ |
| Nezastírat/nefalšovat totožnost, pravdivý předmět | § 7 odst. 4, zákon o reklamě | Předměty v `emails/*/subjects.md` jsou věcné; **nikdy** se nevydávat za poptávku zákazníka (to je ta část z videa, kterou nekopírujeme) |
| GDPR – informační povinnost (čl. 14) při získání údajů z veřejných zdrojů | GDPR | Odkaz na `krystofkoci.com/ochrana-udaju` v patičce (text stránky je v `04_WEBILD_ZADANI_TVUJ_WEB.md`, oddíl 5) |
| GDPR – právní titul oprávněný zájem (čl. 6 odst. 1 písm. f) + možnost námitky | GDPR | Zpracováváme jen veřejné firemní údaje; námitka = odhlášení; data neúspěšných leadů se mažou do 12 měsíců (workflow `06` – měsíční úklid) |
| Žádné cizí fotografie a texty na náhledu | autorský zákon | Pipeline používá jen licencované ilustrační fotky (Pexels) nebo zástupné boxy; texty generuje z faktů, nekopíruje web |
| Náhled není veřejný ani indexovaný | dobrá praxe, GDPR minimalizace | `noindex`, odkaz zná jen adresát, smazání po 60 dnech |

**Co NEdělat (zvyšuje riziko skokově):** nákup databází kontaktů; posílání na osobní adresy zaměstnanců (jmeno.prijmeni@) místo obecných; více než 1 e-mail + 2 připomenutí; pokračování po odmítnutí; hromadné stahování Google Maps mimo Places API; předmět typu „Poptávka“ nebo „Re:“ u prvního kontaktu.

**Kanály:** první kontakt výhradně e-mailem – žádné telefonáty, pošta ani osobní návštěvy. WhatsApp jen když klient napíše první nebo o něj sám požádá; cold WhatsApp porušuje pravidla WhatsApp Business a hrozí zablokování čísla. Firmy bez webu oslovujeme jen tehdy, když mají veřejně uvedený e-mail (jinak se přeskočí).

## 2. USA (trh č. 2) – CAN-SPAM Act

Opt-out režim: **cold e-mail firmám je legální bez předchozího souhlasu**, když dodržíš:
1. pravdivé hlavičky (od, odpovědět-na, doména) – ✔ vlastní doména, Gmail/Workspace;
2. předmět odpovídá obsahu – ✔;
3. označení, že jde o nabídku/reklamu (nemusí být doslovné, ale jasné z textu) – ✔ „non-binding draft I prepared“;
4. **fyzická poštovní adresa** odesílatele – **doplň do `emails/en/footer_legal.txt`** (může být sídlo OSVČ v ČR);
5. funkční odhlášení, vyřízené do 10 pracovních dnů – ✔ okamžitě, automaticky;
6. odpovědnost i za to, co posílá někdo za tebe (zde n8n) – ✔ schvaluješ.
Sankce až cca 53 000 USD za e-mail (částku FTC každoročně valorizuje), v praxi míří na velké spamery. Státní zákony (např. Kalifornie) jsou přísnější na klamavost, ne na souhlas.

## 3. Velká Británie – PECR + UK GDPR

- **Corporate subscribers** (Ltd, PLC, LLP): e-mail bez souhlasu je povolený, musíš se identifikovat a nabídnout odhlášení. ✔
- **Sole traders a běžné partnerships** se počítají jako jednotlivci → vyžadují souhlas (opt-in). ⚠ Systém to nepozná z dat Places – u UK leadů proto v CRM sloupec `legal_form` a oslovovat jen „Ltd“ (ověř v názvu/na webu).
- ICO pokuty až 500 000 GBP za PECR, zákazové příkazy; UK GDPR vyšší.
- Patička: název, adresa, odhlášení, odkaz na privacy page. ✔ (`emails/en/footer_legal.txt`)

## 4. Odkud posíláš, hraje roli

I když budeš fyzicky v Kostarice a adresát v USA, posíláš jako **český podnikatel** – dozor ÚOOÚ nad tebou formálně trvá, prakticky řeší stížnosti českých adresátů. Pro Kostariku samotnou (Ley 8968) neřešíme, protože tam neoslovuješ.

## 5. Google Places API – smluvní podmínky

- Data se smí použít pro tvoji aplikaci; **ukládat trvale smíš jen `place id`**, ostatní pole se mají obnovovat (do 30 dnů). CRM proto ukládá place id a obnovuje údaje při stavbě náhledu; po 60 dnech bez zájmu se řádek anonymizuje (zůstane place id + status), viz `sheets/STATUSY.md`.
- Žádné scrapování map přes prohlížeč – vše přes API s klíčem.
- Hodnocení (hvězdičky + počet) na náhledu zobrazuj s textem „na Google“ a odkazem na profil – to podmínky dovolují; nekopíruj texty recenzí.

## 6. Checklist před prvním odesláním (odškrtni)

- [ ] IČO + sídlo doplněné v `.env` (`OWNER_ICO`, `OWNER_ADDRESS`) a propsané do patiček
- [ ] Stránka `krystofkoci.com/ochrana-udaju` existuje a odkaz v patičce funguje
- [ ] Odhlašovací webhook otestovaný (klik → „Odhlášeno“ → řádek `unsubscribed` → další e-mail se neodešle)
- [ ] `TEST_MODE=true` → 3 testovací e-maily přišly tobě, vypadají správně na mobilu
- [ ] `DAILY_CAP=15`, odesílací okno Po–Pá, `OUTREACH_ENABLED=true` až po tomto checklistu
- [ ] Blocklist obsahuje: tvoje vlastní domény, úřady, školy, nemocnice (nejsou cílovka, zbytečné riziko)
- [ ] V CRM nejsou osobní adresy zaměstnanců (jen obecné firemní kontakty)
- [ ] Po první stížnosti: okamžitě `do_not_contact`, omluva jednou větou, žádná diskuse, zápis do `notes` – a pokud přijdou dvě za týden, v ČR oslovování zastavit (`OUTREACH_ENABLED=false` pro trh cz) a projít texty.

## Zdroje

- Zákon č. 480/2004 Sb., § 7 – https://www.zakonyprolidi.cz/cs/2004-480
- Právní prostor: Rozesílání obchodních sdělení elektronickou formou – https://pravniprostor.cz/clanky/obchodni-pravo/rozesilani-obchodnich-sdeleni-elektronickou-formou
- epravo.cz: Regulace obchodních sdělení podle návrhu zákona o digitální ekonomice – https://www.epravo.cz/top/clanky/regulace-obchodnich-sdeleni-ve-staronovem-kabate-podle-navrhu-zakona-o-digitalni-ekonomice-118675.html
- ÚOOÚ – https://uoou.gov.cz
- FTC CAN-SPAM (shrnutí pravidel a sankcí 2026) – https://tomba.io/blog/can-spam-penalties
- UK PECR cheat-sheet (corporate vs. individual subscribers) – https://sprintlaw.co.uk/articles/email-marketing-laws-uk-compliance-cheatsheet/
- Google Maps Platform Terms (caching) – https://cloud.google.com/maps-platform/terms
