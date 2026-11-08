# Analýza nápadu: „Nový web jako první kontakt“ – a co z něj stavíme

Stav: 24. 10. 2026 · pro Kryštofa Kočího · součást balíčku `web-outreach`

## 1. Zdroj a co přesně autoři tvrdí

| Poznámka (Instagram-napady) | Co ukazuje | Hodnocení v poznámce |
|---|---|---|
| **albert.olgaard – Nový web jako oslovení místních firem** (Lead-a-ziskavani-klientu, IG kolekce *Web*, 8. 10.) | Systém na Claude: najde firmy na Google Mapách → vybere ty se zastaralým webem → postaví nový z jejich údajů → nahraje náhled → odkaz pošle přes **kontaktní formulář firmy**, takže zpráva „vypadá jako poptávka od zákazníka“. Kód za komentář „SITE“. | Průměrné – nápad silný, doručení klamavé a v EU problematické |
| **valeridoesai – Kimi Work** (Web, 10. 10.) | Jeden úkol: najít 50 newyorských firem **bez webu** a každé postavit stránku; 150+ agentů paralelně; výstup = tabulka + weby. | Lákadlo bez obsahu – kvalita a odezva nedoložené |
| **idanbuild – Webild** (Lead, 12. 10.) | Google Maps → firma → vygenerovat web ve Webildu → koupit doménu → ukázat majiteli. Tvrzení 67 492 USD/měs. | Průměrné – postup jasný, výdělek je reklama |
| vyřazené: **siteswithryan – SiteScout**, **cashflow.automations – hromadné maily z Gmailu** | hotový placený nástroj na totéž; hromadné maily (v ČR nelegální, ban Gmailu) | – |

Společné jádro: **„Ukaž hotovou práci místo prosby o schůzku.“** Rozdíly jsou jen v tom, *kdo* web generuje (Claude / Kimi / Webild) a *jak* se doručí.

## 2. Funguje to?

**Ano v jádru.** Hotový návrh webu je nejsilnější forma prvního kontaktu, jakou lze pro tuhle službu vymyslet: majitel rozhoduje nad konkrétní věcí (svůj web na mobilu), ne nad slibem; problém „zastaralý web“ je viditelný a nemusí se vysvětlovat; náklad na jeden náhled jsou jednotky Kč (texty z AI) a hosting zdarma; škáluje to na desítky denně.

**Ne v podobě z videí**, a to ze čtyř důvodů:
1. **Zpráva vydávaná za poptávku** = klamání. Zničí důvěru hned v první větě a v EU je to nekalá praktika.
2. **Hromadný e-mail bez souhlasu**: v ČR je obchodní sdělení opt-in i vůči firmám (z. 480/2004 Sb.), pokuta až 10 mil. Kč; v USA opt-out (CAN-SPAM) je legální; UK jen právnické osoby; CA/AU/NZ „adresa zveřejněná + relevance“. Detail: `02_PRAVNI_CHECKLIST.md`.
3. **Scraping Google Map** je proti podmínkám → Places API (New) s měsíčním kreditem zdarma (Enterprise pole s webem/telefonem: 1 000 dotazů/měs zdarma, 1 dotaz = až 20 firem).
4. **Cizí fotky a texty** na náhledu = autorská práva; AI web bez kontroly si vymýšlí ceny a údaje.

**Nikdo z autorů nedoložil čísla** (odpovědi, zakázky). Můj odhad z praxe personalizovaného outreache s hotovou ukázkou: odpověď 3–8 %, zakázka 1–2 ze 100. První směrodatná čísla budeš mít po ~100 odeslaných e-mailech – systém je měří sám.

## 3. Silné a slabé stránky

**Silné:** hodnota předem · viditelný problém · škáluje · navazuje správa webu, rezervace, AI recepční (tvoje další služby) · dvě větve zákazníků (zastaralý web / žádný web) · levný provoz (desítky Kč denně) · dá se řídit odkudkoli (Telegram, MCP) · sbírá data o tom, co funguje.

**Slabé:** právní rámec ČR pro e-mail · když to dělá víc lidí, majitelé otupí (proto osobní text a kvalita) · AI web = kód, který klient sám neupraví (řešení: finální web ve Webildu s editorem, nebo tvoje správa) · doručitelnost nové domény (zahřátí, malé dávky) · AI agent smí jednat jen v mantinelech, závazek potvrzuješ ty · pro větev „nemá web“ často chybí e-mail → telefon.

## 4. Co je potřeba (a co balíček obsahuje)

| Vrstva | Řešení | Kde |
|---|---|---|
| Sběr firem | Google Places API (New), fronta zemí/měst/oborů, denní plán na ~30 náhledů podle vah, **Kostarika a `BLOCKED_COUNTRIES` nikdy** | `pipeline/places_search.py`, `learn.plan_day`, `n8n/01` |
| Audit webu | HTTPS, mobil, rok v patičce, technologie, formulář, rychlost (PageSpeed API zdarma), e-maily z kontaktní stránky → skóre 0–100, větev `redesign` / `no_website` / `skip` | `pipeline/audit.py` |
| Generátor webu | 6 oborových šablon (jednostránkový, responzivní, bez frameworků), texty z Claude přes LiteLLM jen z veřejných faktů, bez cen; fotky Pexels nebo zástupné; náhledový pruh „Chci tento web“; `noindex` | `pipeline/templates`, `copy_writer.py`, `generate_site.py` |
| Srovnání | screenshot „DNES vs. NOVÝ NÁVRH“ na mobilu (Playwright) → obrázek na schvalovací stránku a do e-mailu | `pipeline/screenshot_compare.py` |
| Hosting náhledů | Caddy na VPS, `nahled.krystofkoci.com/<firma>/`, zdarma, bez limitu; po 60 dnech úklid | `infra/Caddyfile`, `deploy_preview.py` |
| Schvalování | dávky v 8:00 / 11:00 / 14:00 (`OWNER_TZ`): WhatsApp zpráva + e-mail s odkazem na mobilní schvalovací stránku, ~10 karet, tlačítka Poslat / Upravit / Zahodit / Nekontaktovat + „Schválit celou dávku“ | `n8n/03` |
| E-mail | Gmail/Workspace z `kontakt@krystofkoci.com`, 1 + 2 připomenutí, okno Po–Pá v pásmu adresáta, limit 30/den, A/B/C předměty, právní patička podle režimu země, odhlášení s HMAC | `n8n/04`, `emails/` |
| Odpovědi | Inbox agent: klasifikace → odpověď z ceníku a FAQ v mantinelech (floor 350 USD / 8 000 Kč) → vše písemně (e-mail, WhatsApp jen když klient napíše první), žádné hovory → eskalace tobě; max 2 automatické odpovědi; ruční převzetí | `n8n/05`, `03_CENIK_A_MANTINELY_AGENTA.md` |
| Schůzky | **žádné** – jen písemná komunikace; příchozí WhatsApp → inbox agent | `n8n/06` |
| CRM + učení | Google Sheets `leads`, `deals`, `weights`, `blocklist`, `queue`; neděle: `/learn` → váhy + doporučení; pondělí: report | `sheets/`, `pipeline/learn.py`, `n8n/06` |
| LLM brána | LiteLLM: jeden klíč, rozpočet/měsíc, log útraty, fallback (Sonnet → Haiku), přepnutí poskytovatele v configu | `infra/litellm/` |
| MCP | n8n MCP server: `outreach-read` (fronta, stav, report, kontrola náhledu – pro AI_COM) a `outreach-admin` (schválit, vytvořit náhled, uzavřít zakázku – jen ty); MCP klient v agentovi pro externí servery | `n8n/08` |
| Tvůj web | Webild podle zadání (texty CS/EN, struktura, prompt, GDPR stránka, galerie demo webů) | `04_WEBILD_ZADANI_TVUJ_WEB.md` |
| Infra | Hetzner VPS, Docker Compose (n8n, Postgres, LiteLLM, pipeline, Caddy), instalační skript, zálohy | `infra/` |

Účty, které zakládáš jen ty: doména, Hetzner, Google Cloud (Places + OAuth), Anthropic API, WhatsApp Business (Meta), Webild.

## 5. Dvě větve zákazníků

**A) Má web, ale zastaralý** (`redesign`, skóre ≥ 45): audit dá 2–3 konkrétní důvody („na mobilu se nezobrazuje“, „bez HTTPS“, „patička 2014“) → e-mail cituje první důvod → náhled + srovnání. Kontakt: e-mail z webu.

**B) Nemá web vůbec** (`no_website`, skóre 100): Places vrátí firmu bez `websiteUri` (nebo doména parkuje). Náhled vzniká jen z profilu na Google (název, adresa, otevírací doba, hodnocení, obor) + oborové texty. Argument: „zákazníci vás hledají a najdou jen mapu – takhle by to mohlo vypadat“. Kontakt: e-mail obvykle **není** → status `needs_phone_contact`, telefonní skript 60 s (`emails/no_website_call_script_*.md`): po souhlasu v hovoru pošleš náhled e-mailem – a tím je e-mail legální i v ČR. Pro salony/holičství bývá Instagram/Facebook – zpráva poctivě pod svým jménem.

## 6. Jak vzniká nový web (krok za krokem)

1. **Data:** Places (název, adresa, telefon, otevírací doba, hodnocení, typ) + audit starého webu (e-maily, služby zmíněné v textu, sociální sítě).
2. **Obor → šablona:** `plumber`→`remeslo`, `hair_salon`→`salon`… každá šablona má vlastní akcent, ikony, pořadí sekcí.
3. **Texty:** Claude (přes LiteLLM) dostane jen fakta a pravidla: nic nevymýšlet, žádné ceny/roky/certifikáty, neznámé → `[DOPLNÍTE]`. Výstup je JSON se schématem, validuje se; při výpadku modelu nastoupí předpřipravené oborové texty.
4. **Fotky:** licencované ilustrační (Pexels, s kreditem) nebo zástupné boxy „Vaše fotografie“. Nikdy fotky ze starého webu.
5. **Sestavení:** jeden HTML soubor (inline CSS, bez frameworků, rychlý na mobilu), náhledový pruh, `noindex`, formulář → n8n.
6. **Srovnání:** screenshot starého i nového webu na mobilu vedle sebe.
7. **Publikace:** `nahled.krystofkoci.com/<slug>/` + záznam do CRM → dávka ke schválení.
8. **Po zakázce:** finální web postavíš ve **Webildu** z hotových textů (15–30 min), připojíš doménu klienta, převedeš vlastnictví nebo necháš pod svou správou (490 Kč / 29 USD měsíčně). Alternativa: nasadit vygenerovaný kód přímo na doménu klienta (zdarma, bez editoru).

## 7. Co jsem našel na GitHubu / v hotových šablonách (a proč stavíme vlastní)

- **Zie619/n8n-workflows** (≈57 tis. ★, MIT, 4 343 workflow) a **enescingoz/awesome-n8n-templates** – knihovny vzorů; žádný neřeší celý řetězec. Použité jako inspirace pro strukturu uzlů.
- Oficiální šablony n8n blízké našim krokům: *Extract leads from Google Maps into Google Sheets using the Places API* (#13753), *Automate Email Responses with OpenAI and Telegram Approval for Gmail* (#6026), *Personalized cold email sequences with Google Sheets and Gmail* (#20363), *Monitor Core Web Vitals with PageSpeed API* (#15911). Náš balíček dělá totéž, ale dohromady, česky/anglicky, s právními patičkami, floor cenami a učením.
- **Abrar881/website-audit-leadgen** (0 ★): Places + PageSpeed + skóre + SQLite dashboard – potvrzuje přístup, bez oslovení a bez generátoru; nepřebíráno.
- Open-source AI buildery (**bolt.diy**, **dyad**, **onlook**, **openui**) jsou interaktivní nástroje pro jednoho uživatele, ne dávkový generátor → nevhodné pro 30 náhledů denně; proto šablony + JSON texty.
- Hosting náhledů: **Netlify Free** 300 kreditů/měs (15 za produkční deploy → max. 20 deployů), **Cloudflare Pages** 100 projektů/účet a REST upload jen reverzně zdokumentovaný, **GitHub Pages** zakazuje komerční využití → **vlastní VPS s Caddy** (žádné limity, žádná závislost).
- E-mailové služby **Resend, Brevo, Mailgun, Postmark výslovně zakazují cold outreach** (ověřeno v jejich AUP 10/2026) → odesílání přes vlastní schránku (Google Workspace, limit 2 000/den; Gmail 500/den) v malých dávkách.

## 8. Náklady provozu (odhad měsíčně)

| Položka | Kč/měs |
|---|---|
| VPS Hetzner CX22 | ~110 |
| Doména .cz | ~25 (250/rok) |
| Google Workspace Starter (schránka kontakt@, Gmail API) – nebo 0 Kč s Gmail aliasem | 0–170 |
| LLM přes LiteLLM (30 náhledů/den + odpovědi) | 150–400 (rozpočet nastavíš, výchozí 20 USD) |
| Places API | 0 (do 1 000 Enterprise dotazů/měs), pak 35 USD/1 000 |
| PageSpeed API, Pexels, n8n self-host | 0 |
| WhatsApp Cloud API (utility šablony ~90 zpráv/měs, cena dle země – ověřit v Meta ceníku) | jednotky USD |
| Webild Builder (až s prvním klientem) | ~230 (9,99 USD) |
| **Celkem** | **~300–900 Kč/měs** |

## 9. Rizika a jak je balíček řeší

| Riziko | Opatření |
|---|---|
| Stížnost na ÚOOÚ (ČR) | opt-out okamžitě, patička dle zákona, max. jednotky e-mailů denně v ČR, blocklist, při stížnostech zastavit trh cz |
| Google zablokuje odesílání | 30/den, osobní texty, SPF/DKIM/DMARC, sledování bounce, `TEST_MODE` před startem |
| Špatný náhled poškodí jméno | schvaluješ každý; checklist kontroly; model nesmí vymýšlet; `[DOPLNÍTE]` místo nesmyslů |
| Agent slíbí nesmysl | guardrail kód (floor, zakázaná slova, data), max. 2 odpovědi, eskalace, ruční převzetí |
| Výpadek LLM/brány | fallback texty, záložní přímé napojení na Anthropic v n8n |
| Ztráta dat | denní zálohy n8n + Postgres + náhledů, 14 dní |
| Places quota | denní plán drží ≤ 5 dotazů; kód hlásí 429 e-mailem / WhatsApp |

## 10. Co dál (po prvním týdnu)

1. Doplnit `es` texty a šablony → LatAm (stejné pásmo).
2. První skutečná reference → nahradit demo kartu na webu.
3. Z uzavřených zakázek nechat `learn.py` přepsat `06_KDE_ZACIT_ANALYZA.md` čísly.
4. AI_COM: audit balíčku jako M1 (code review, testy), pak denní kontrola náhledů přes `outreach-read`.
5. Doplňkové produkty na stejném kanálu: rezervace, AI recepční, úprava stávajícího webu.
