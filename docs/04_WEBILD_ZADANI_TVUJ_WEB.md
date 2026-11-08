# Zadání: tvůj vlastní web ve Webildu (krystofkoci.com)

Postavíš si ho sám ve Webildu (jak sis vybral). Tady máš všechno, co do něj vložit: strukturu, hotové texty česky i anglicky, prompt pro generátor, barvy, obrázky, SEO a právní stránku. Odhad práce: 60–90 minut.

**Role webu v systému:** (1) odkaz „kdo mi píše“ v každém oslovovacím e-mailu, (2) galerie ukázek „takhle může vypadat váš web“ (demo weby z pipeline běží na `nahled.krystofkoci.com/demo-…`), (3) kontakt e-mailem nebo přes WhatsApp (žádné hovory), (4) právní stránka s informacemi o zpracování údajů (potřebná kvůli oslovování).

---

## 0. Než začneš

1. Doménu **krystofkoci.com** už máš. DNS přesměruj na Cloudflare (zdarma) – návod v `infra/README_infra.md`. Ve Webildu pak doménu připojíš jako vlastní (plán **Builder**, 9,99 $/měs při roční platbě). Do té doby stačí adresa, kterou ti Webild přidělí.
2. Založ účet na Webildu a udělej nejdřív **5min test** (`docs/05_WEBILD_TEST_5MIN.md`), ať víš, kolik kreditů stojí jedno generování.
3. Připrav si: jednu svoji fotku (portrét nebo při práci, stačí mobil, světlo zepředu), screenshot dashboardu ESL systému (bez interních dat JIP), odkazy na demo weby (po spuštění pipeline: `python -m pipeline.cli demo`).

## 1. Struktura webu

Jednostránkový web s kotvami + 3 podstránky:

| Část | URL | Účel |
|---|---|---|
| Domů (vše na jedné stránce) | `/` | úvod → co dělám → ukázky → jak to probíhá → ceny → o mně → reference ESL → kontakt |
| Anglická verze | `/en` | totéž anglicky, ceny v USD (pro USA/UK trh) |
| Ochrana údajů | `/ochrana-udaju` | povinné informace (GDPR čl. 13/14) + jak se odhlásit |
| Ukázky (volitelná samostatná stránka) | `/ukazky` | galerie demo webů s obrázky a odkazy |

Navigace: Co dělám · Ukázky · Ceny · O mně · Kontakt · **[Napsat mi]** (tlačítko) · EN

## 2. Prompt pro Webild (vlož jako první zadání, pak dolaď sekce)

```
Vytvoř jednostránkový profesionální web pro freelancera Kryštofa Kočího (Česko), který staví weby a automatizace pro místní firmy. Jazyk: čeština. Styl: čistý, klidný, důvěryhodný, bez korporátních frází – spíš řemeslník digitálu než agentura. Barvy: tmavě modrá (#0F2A44) jako základ, teplá jantarová (#F2A33A) jako akcent, hodně bílého prostoru, světle šedé pozadí sekcí (#F5F6F8). Písmo: moderní bezpatkové, velké čitelné nadpisy. Žádné stock fotky kancelářských lidí; použij 1 portrét (dodám), screenshoty webů (dodám) a jednoduché ikony.

Sekce v tomto pořadí:
1. Hero: nadpis "Nový web pro vaši firmu. Hotový návrh uvidíte dřív, než cokoliv zaplatíte." podnadpis "Weby a automatizace pro místní firmy. Jednostránkový web za 10 000 Kč do 5 pracovních dnů." Tlačítka: "Chci nezávazný návrh" (kotva #kontakt) a "Podívat se na ukázky" (kotva #ukazky).
2. "Jak to funguje" – 3 kroky s ikonami.
3. "Ukázky" – mřížka 6 karet (obrázek + název oboru + tlačítko Otevřít), odkazy dodám.
4. "Co dělám" – 3 služby: Web pro místní firmu, Úprava stávajícího webu, Automatizace poptávek a rezervací.
5. "Ceny" – 3 karty: Jednostránkový web 10 000 Kč, Vícestránkový od 23 000 Kč, Správa 490 Kč/měs; pod tím věta o 50 % záloze a vlastnictví domény.
6. "O mně" – portrét + text.
7. "Reference: ESL systém" – 1 karta s obrázkem dashboardu a krátkým textem.
8. "Kontakt" – e-mail kontakt@krystofkoci.com, formulář (jméno, e-mail, web firmy, zpráva), tlačítko "Napsat na WhatsApp" (odkaz wa.me/<tvoje číslo>), poznámka "Pracuji na dálku, odpovídám do 24 hodin."
9. Patička: jméno, IČO, "Informace o zpracování osobních údajů" (odkaz), rok.
Přidej sticky lištu s tlačítkem "Napsat mi" na mobilu (e-mail / WhatsApp).
```

Po vygenerování projdi sekce a texty **nahraď těmi níže** (AI generátor si jinak vymyslí vlastní čísla a sliby).

## 3. Texty – česky

### Hero
**Nový web pro vaši firmu. Hotový návrh uvidíte dřív, než cokoliv zaplatíte.**
Weby a automatizace pro místní firmy – řemeslníky, salony, servisy, ordinace a podniky. Jednostránkový web za 10 000 Kč, hotový do 5 pracovních dnů od dodání podkladů.
[Chci nezávazný návrh] [Podívat se na ukázky]

### Jak to funguje
1. **Podívám se na vaši firmu.** Projdu váš současný web (nebo zjistím, že žádný nemáte) a z veřejných informací připravím návrh nové podoby. Zdarma a nezávazně.
2. **Dostanete odkaz na náhled.** Otevřete si ho v mobilu a srovnáte s tím, co máte dnes. Texty a fotky jsou zatím zástupné – nahradíme je vašimi.
3. **Když se líbí, domluvíme se.** Domluvíme se e-mailem nebo přes WhatsApp, 50 % záloha, do 5 pracovních dnů web na vaší doméně. Druhá polovina až po předání.

### Ukázky
**Takhle může vypadat váš web.** Ukázkové weby pro šest oborů – stejný postup, kterým připravuji návrhy pro skutečné firmy. Vše se přizpůsobí vašim barvám, fotkám a službám.
- Řemeslo a služby – *Instalatérství Novák & syn* → `https://nahled.krystofkoci.com/demo-remeslo/`
- Kadeřnictví a kosmetika – *Salon Lucie* → `/demo-salon/`
- Autoservis – *Autoservis U Dvou Kol* → `/demo-autoservis/`
- Kavárna a restaurace – *Kavárna Pod Lípou* → `/demo-gastro/`
- Ordinace a zdraví – *Zubní ordinace Zdravý úsměv* → `/demo-zdravi/`
- Obecná firma – *Firma Vzor* → `/demo-obecny/`
(Pozn.: jde o smyšlené firmy. Jakmile budeš mít první skutečnou referenci, nahraď první kartu.)

### Co dělám
**Web pro místní firmu.** Jednostránkový nebo vícestránkový web, který se rychle načte na mobilu, má jasné „zavolejte / napište“ a najde ho Google. Včetně napojení domény, formuláře a základního SEO.
**Úprava stávajícího webu.** Nemusíte stavět znovu. Mobilní verze, zabezpečení (HTTPS), rychlost, kontaktní formulář, aktuální údaje – podle toho, co vašemu webu chybí.
**Automatizace poptávek a rezervací.** Aby vám neutíkali zákazníci, když zrovna pracujete: online rezervace termínů, automatické odpovědi na poptávky z webu a e-mailu, připomínky. Stavím na nástrojích n8n a AI, nastavuji a spravuji.

### Ceny
| **Jednostránkový web** | **Vícestránkový web** | **Správa webu** |
|---|---|---|
| **10 000 Kč** | **od 23 000 Kč** | **490 Kč / měsíc** |
| úvod, služby, o nás, hodnocení, otevírací doba, mapa, kontakt + formulář · napojení domény · základní SEO · 1 kolo úprav · hotovo do 5 pracovních dnů | 3–6 stránek · struktura a texty podle podkladů · přesměrování ze starého webu · 2 kola úprav · do 10–15 pracovních dnů | hosting a zálohy · aktualizace · drobné úpravy do 30 minut měsíčně · kontrola, že vše funguje · reakce do 2 pracovních dnů |

Platba 50 % předem, 50 % po předání. Doména i web jsou vaše. Ceny jsou bez DPH (nejsem plátce). `[uprav podle skutečnosti]`

### O mně
Jsem Kryštof Kočí, živnostník. Stavím systémy na zakázku – od elektrotechniky po weby a firemní automatizace. Většinu rutinní práce dělají moje AI nástroje, díky tomu jsem rychlý a dostupný; kontrolu, texty a úpravy dělám já. Nejsem agentura: píšete přímo mně a já vám přímo odpovídám. Pracuji na dálku, s klienty komunikuji e-mailem a videohovorem.

### Reference: ESL systém pro maloobchod
Pro síť prodejen připravuji systém **elektronických cenovek**: centrální správa cen, synchronizace se skladovým systémem, přehledový dashboard pro vedení. `[po spuštění doplň 2–3 čísla: počet prodejen, položek, úspora času]` Ukazuje, že zvládnu i větší systém než web – a že k webu umím napojit to, co firma už používá.

### Kontakt
**Napište mi – e-mailem, nebo přes WhatsApp.**
E-mail: kontakt@krystofkoci.com
[Napsat na WhatsApp] (odkaz wa.me/<tvoje číslo>)
Formulář: Jméno · E-mail · Web vaší firmy (nepovinné) · Zpráva · [Odeslat]
Pracuji na dálku. Odpovídám do 24 hodin v pracovní dny.

### Patička
© 2026 Kryštof Kočí · IČO `[DOPLNIT]` · [Informace o zpracování osobních údajů](/ochrana-udaju) · kontakt@krystofkoci.com

## 4. Texty – anglicky (/en)

### Hero
**A new website for your business. You see the finished draft before you pay anything.**
Websites and automation for local businesses – trades, salons, auto shops, clinics, cafés. One-page website for $400, live within 5 business days of receiving your materials.
[Get a free draft] [See examples]

### How it works
1. **I look at your business.** I review your current website (or notice you don't have one) and prepare a draft of a new design from public information. Free, no strings attached.
2. **You get a preview link.** Open it on your phone and compare with what you have today. Texts and photos are placeholders for now – we'll replace them with yours.
3. **If you like it, we talk.** A 20-minute video call, 50 % deposit, your website live on your domain within 5 business days. The second half only after handover.

### Examples
**This is what your website could look like.** Demo sites for six industries – built with the same process I use for real businesses. Everything adapts to your colours, photos and services. (odkazy na `…/demo-remeslo-en/` atd.)

### What I do
**Website for a local business.** One-page or multi-page, fast on mobile, with a clear "call / message" action and findable on Google. Domain setup, contact form and basic SEO included.
**Fixing your current website.** No need to rebuild: mobile version, HTTPS, speed, contact form, up-to-date details – whatever your site is missing.
**Automating enquiries and bookings.** So you don't lose customers while you work: online booking, automatic replies to enquiries from your website and e-mail, reminders. Built on n8n and AI, set up and maintained by me.

### Pricing
| **One-page website** | **Multi-page website** | **Care plan** |
|---|---|---|
| **$400** | **from $970** | **$29 / month** |
| intro, services, about, reviews, hours, map, contact form · domain setup · basic SEO · 1 round of edits · done within 5 business days | 3–6 pages · structure and copy from your materials · redirects from the old site · 2 rounds of edits · 10–15 business days | hosting & backups · updates · small edits up to 30 min/month · uptime checks · response within 2 business days |

50 % deposit, 50 % on handover. You own the domain and the website.

### About me
I'm Kryštof Kočí, an independent builder of custom systems – from electrical engineering to websites and business automation. My AI tools do most of the routine work, which keeps me fast and affordable; the review, copy and edits are mine. I'm not an agency: you write to me and I answer. I work remotely (currently in the Central time zone) and communicate by e-mail and video call.

### Case study: electronic shelf labels
For a retail chain I'm building an **electronic shelf label system**: central price management, sync with the inventory system, a dashboard for management. `[add 2–3 numbers after launch]` It shows I can handle more than a website – and connect your site to the tools you already use.

### Contact
**Write to me, or book a call right away.** E-mail: kontakt@krystofkoci.com · [Book a 20-minute video call] · Form: Name · E-mail · Your website (optional) · Message · [Send] · I work remotely and reply within 24 hours on business days.

### Footer
© 2026 Kryštof Kočí · Czech Republic · [Privacy information](/ochrana-udaju) · kontakt@krystofkoci.com

## 5. Stránka /ochrana-udaju (povinná – odkazuj na ni z e-mailů)

```
Informace o zpracování osobních údajů

Správce: Kryštof Kočí, IČO [DOPLNIT], sídlo [DOPLNIT], e-mail kontakt@krystofkoci.com.

1. Když mi napíšete (formulář, e-mail, WhatsApp), zpracovávám vaše jméno, e-mail a obsah zprávy, abych vám mohl odpovědět a připravit nabídku (plnění smlouvy / jednání o ní, čl. 6 odst. 1 písm. b GDPR). Údaje uchovávám po dobu jednání a 3 roky poté.

2. Když vás oslovím s nezávazným návrhem webu, použil jsem kontakt, který vaše firma sama zveřejnila (web, profil na Google). Důvodem je můj oprávněný zájem nabídnout službu související s vaším podnikáním (čl. 6 odst. 1 písm. f GDPR). Zpracovávám název firmy, veřejnou adresu, telefon, e-mail, adresu webu a jeho veřejně dostupný obsah. Proti tomuto zpracování můžete kdykoliv vznést námitku – stačí odpovědět na e-mail nebo kliknout na odkaz pro odhlášení; vaše údaje pak vyřadím a už vás neoslovím. Údaje firem, které neprojevily zájem, mažu do 12 měsíců.

3. Náhled webu, který jsem pro vás připravil, je dostupný jen tomu, kdo zná odkaz, není indexován vyhledávači a po 60 dnech ho smažu, pokud se nedomluvíme jinak.

4. Údaje nepředávám třetím stranám kromě poskytovatelů, které používám k provozu (hosting v EU, e-mail, rezervační systém, Webild Inc. jako platforma webu). Mimo EU mohou být údaje zpracovány u poskytovatelů se standardními smluvními doložkami.

5. Máte právo na přístup, opravu, výmaz, omezení zpracování, námitku a přenositelnost a právo podat stížnost u Úřadu pro ochranu osobních údajů (uoou.gov.cz).

Poslední aktualizace: [datum]
```
Anglická verze: stejný text přeložit (Webild to zvládne), správce zůstává česká OSVČ.

## 6. Design – na co dát pozor ve Webildu

- Hero bez obrázku pozadí, jen text + 2 tlačítka a vpravo mockup telefonu s jedním demo webem (screenshot z pipeline `new_mobile.png`).
- Karty ukázek: poměr 4:3, screenshot desktopové verze; při najetí „Otevřít“.
- Ceny: zvýrazni prostřední kartu? **Ne** – zvýrazni **jednostránkový web** (hlavní produkt).
- Mobil: sticky lišta dole „Napsat mi“. Zkontroluj v náhledu mobilu, že formulář má velká pole.
- Žádné animace, které zpomalují. Žádné „AI“ v nadpisech – klienti kupují web, ne technologii; AI zmiň jen v „O mně“.
- Odznak „Built with Webild“: na placeném plánu vypni.

## 7. SEO a technika

- Title (cz): `Kryštof Kočí – weby a automatizace pro místní firmy | návrh webu zdarma`
- Meta description (cz): `Jednostránkový web pro vaši firmu za 10 000 Kč do 5 dnů. Hotový návrh uvidíte dřív, než zaplatíte. Weby, úpravy webů a automatizace poptávek pro řemeslníky, salony, servisy a ordinace.`
- Title (en): `Kryštof Kočí – websites & automation for local businesses | free draft first`
- `hreflang` cs/en, pokud Webild umí; jinak alespoň odkaz „EN“ v menu.
- Formulář: Webild má vlastní „Inbox“ – odpovědi ti přijdou tam a na e-mail. Pokud chceš poptávky rovnou do CRM, do pole „děkovná stránka / redirect“ dej `https://n8n.krystofkoci.com/webhook/form` jen pokud Webild umí POST na webhook; jinak nech Inbox a poptávky z webu zapisuj do CRM ručně (jsou to jednotky týdně).
- Google Search Console: ověř doménu, odešli sitemapu (Webild ji generuje).
- Analytika: Webild má vlastní; stačí.

## 8. Checklist před zveřejněním

- [ ] Všechny ceny odpovídají `03_CENIK_A_MANTINELY_AGENTA.md`
- [ ] Žádný text, který generátor vymyslel (počty klientů, roky praxe, „100% spokojenost“)
- [ ] Odkazy na demo weby fungují (nahled.krystofkoci.com běží)
- [ ] Tlačítko WhatsApp otevře chat s tvým číslem; e-mail kontakt@krystofkoci.com funguje
- [ ] Stránka /ochrana-udaju existuje a je v patičce
- [ ] IČO a sídlo doplněné
- [ ] Mobil: hero čitelný, formulář použitelný, sticky tlačítko
- [ ] Odznak Webild vypnutý, vlastní doména připojená, HTTPS zelené
- [ ] Anglická verze: ceny v USD, odkazy na `-en` dema
