# Spuštění krok za krokem (plán na 4 dny před odletem)

> **Přesné příkazy a pořadí instalace jsou v [`VYPLN_A_SPUST.md`](../VYPLN_A_SPUST.md) – při rozporu platí ten.** Tady je jen rozvržení do dnů a kontroly.

Všechno, co zakládá účty nebo platí, děláš ty. Všechno ostatní je v balíčku. Odhad: **6–8 hodin tvojí práce celkem**, rozložených do 4 dnů. Pořadí je důležité – každý den končí kontrolou.

## Den 1 (neděle 25. 10.) – účty a server · ~2 h

1. **Doména** `krystofkoci.com` (máš). DNS správu přepni na **Cloudflare** (zdarma; návod `infra/README_infra.md` § DNS).
2. **Hetzner Cloud**: projekt → server **CX22, Ubuntu 24.04, lokalita Norimberk/Falkenstein** (blíž ČR; pro USA stačí – web se jen posílá) → přidej svůj SSH klíč. Zapiš IP.
3. DNS na Cloudflare: `A n8n → IP`, `A nahled → IP` (oba *DNS only*, šedý mráček – Caddy si vystaví HTTPS sám), `krystofkoci.com` zatím nic (bude Webild).
4. **Google Cloud**: nový projekt `web-outreach` → zapnout **Places API (New)** a **PageSpeed Insights API** → API klíč (omezit na tyto dvě API) → OAuth consent screen (External, **Publish = In production**) → OAuth klient „Web application“ s redirect `https://n8n.krystofkoci.com/rest/oauth2-credential/callback` → zapnout **Gmail API, Google Sheets API**.
5. **Anthropic API** klíč + kredit 10–20 USD.
6. **WhatsApp Business Cloud API** (Meta): Meta Business účet → developers.facebook.com → app typu Business → produkt WhatsApp → nejdřív **testovací číslo** (zdarma, zprávy jen na tvoje ověřené číslo – na schvalování stačí) → trvalý systémový token, `PHONE_NUMBER_ID`, tvoje číslo v E.164. Ke schválení pošli šablony `batch_ready` a `escalation` (kategorie Utility). Návod: `infra/README_infra.md` § WhatsApp.
7. **Server**: nahraj balíček a spusť instalaci podle `VYPLN_A_SPUST.md` § 2 (`install.sh` → vyplnit `infra/.env` → `install.sh` → `check_env.sh`).
8. **Kontrola dne 1:** `https://n8n.krystofkoci.com` otevře n8n (založ owner účet), `https://nahled.krystofkoci.com/` vrátí 404 „Náhled nenalezen“ (správně – ještě nic není), `docker compose ps` ukazuje 5 služeb *healthy*.

## Den 2 (pondělí 26. 10.) – n8n, CRM, první náhledy · ~2 h

1. **Google Sheets**: nový sešit „Web outreach CRM“ → 5 listů `leads`, `queue`, `deals`, `weights`, `blocklist` → první řádky z `sheets/*.csv` (import CSV). ID sešitu do `.env` (`SHEET_ID`).
2. **n8n credentials**: Google OAuth2 (Sheets + Gmail z jednoho klienta), WhatsApp (HTTP Header Auth `Authorization: Bearer <WHATSAPP_TOKEN>`), LiteLLM (HTTP header auth / OpenAI-compatible: Base URL `http://litellm:4000/v1`, klíč = virtuální klíč z `http://localhost:4000/ui` přes SSH tunel), Pipeline (Header Auth `Authorization: Bearer <API_TOKEN>`).
3. **Workflowy** naimportuje `install.sh` sám; v n8n jen přihlas Google (2 credentials) a spusť `00 Nastavení` → `set_sheet_id.sh` (viz `VYPLN_A_SPUST.md` § 3–4).
4. **Demo weby**: na serveru `docker compose exec pipeline python -m pipeline.cli demo --out /srv/nahled` → otevři `https://nahled.krystofkoci.com/demo-remeslo/` atd. na mobilu. Tohle je galerie pro tvůj web.
5. **První skutečný náhled ručně**: v n8n spusť `01_lead_finder` ručně s jedním řádkem fronty (`enabled=TRUE` jen u „Brno, instalatér“), pak `02` a ručně `03` → na WhatsApp a e-mail ti přijde odkaz na schvalovací stránku. Zkontroluj náhled podle checklistu v `pipeline/README.md` („Kontrola před odesláním“).
6. **Kontrola dne 2:** ve `leads` je ≥ 5 řádků se `preview_url`, schvalovací stránka se otevře na mobilu, karty mají obrázek DNES/NOVÝ a tlačítka, kliknutí na ❌ změní status na `rejected`.

## Den 3 (úterý 27. 10.) – e-mail, agent, tvůj web · ~2–3 h

1. **Odesílací adresa**: Google Workspace Starter pro `kontakt@krystofkoci.com` (čistší), nebo v Gmailu „Odesílat jako“ alias přes SMTP u tvého registrátora. DNS: SPF, DKIM, DMARC podle `infra/README_infra.md` § E-mail. Test na mail-tester.com ≥ 9/10.
2. `TEST_MODE=true` → aktivuj `04` → schval 2 karty → do **tvé** schránky přijdou e-maily 1 (a po úpravě čekání i 2 a 3). Zkontroluj patičku, odkaz na odhlášení (klikni – musí vrátit „Odhlášeno“ a změnit status), zobrazení na mobilu.
3. Aktivuj `05` → odpověz si sám z jiné adresy na testovací e-mail → agent musí odpovědět písemně, a tobě přijde kopie na WhatsApp/e-mail. Zkus napsat „kolik to stojí“, „můžeme si zavolat?“ (musí odpovědět, že vše písemně, žádný hovor) a „máte to za 200 dolarů?“ (musí skončit eskalací). Pak si z jiného čísla napiš na firemní WhatsApp – agent musí odpovědět ve stejném duchu.
4. Zapni `07` (veřejné webhooky vč. WhatsApp – URL a verify token vlož v Meta app → WhatsApp → Configuration) a `08` (MCP); otestuj `claude mcp add …` podle README.
5. **Tvůj web ve Webildu**: 5min test (`05_WEBILD_TEST_5MIN.md`), pak zadání `04_WEBILD_ZADANI_TVUJ_WEB.md`. Stránka `/ochrana-udaju` je povinná před ostrým odesíláním.
6. **Kontrola dne 3:** mail-tester ≥ 9, odhlášení funguje, agent eskaluje pod floor, web má /ochrana-udaju, agent odmítne hovor a odpoví písemně, příchozí WhatsApp zpráva dostane odpověď.

## Den 4 (středa 28. 10.) – ostrý start · ~1 h

1. Projdi `02_PRAVNI_CHECKLIST.md` § 6 (IČO, sídlo, blocklist úřadů/škol).
2. `.env`: `TEST_MODE=false`, `OUTREACH_ENABLED=true`, `DAILY_CAP=10` (první týden; na 30 až po týdnu bez problémů s doručitelností) → `docker compose up -d` (znovu načte env).
3. Fronta: zapni řádky podle `06_KDE_ZACIT_ANALYZA.md` (USA střed, Kanada prérie, ČR mimo Prahu). Aktivuj `01`.
4. Ráno v 8:00 ti přijde první dávka. Schvaluj jen náhledy, za které by ses nestyděl.
5. Zálohy: ověř, že `infra/backup.sh` běží z cronu a první archiv existuje.

## V Kostarice (od 29. 10.)

- `OWNER_TZ=America/Costa_Rica` → dávky v 8/11/14 tvého času; e-maily se posílají v pásmu adresáta samy.
- Denně: 3× odkaz na WhatsApp/e-mail se schvalovací stránkou (10 min), odpovědi, které agent eskaloval.
- Neděle večer: e-mail s doporučeními z učení (+ upozornění na WhatsApp); pondělí ráno: report e-mailem.
- Když něco hoří: `OUTREACH_ENABLED=false` v `.env` + `docker compose up -d`, nebo deaktivuj workflow `04` v n8n.

## Kde co je

| Potřebuji | Soubor |
|---|---|
| pochopit nápad, klady/zápory, architekturu | `docs/01_ANALYZA_NAPADU.md` |
| právo ČR/USA/UK, patičky, checklist | `docs/02_PRAVNI_CHECKLIST.md` |
| ceny, floor, pravidla agenta, prompt | `docs/03_CENIK_A_MANTINELY_AGENTA.md` |
| můj web ve Webildu | `docs/04_WEBILD_ZADANI_TVUJ_WEB.md`, `05_WEBILD_TEST_5MIN.md` |
| kam mířit (trhy, obory, města) | `docs/06_KDE_ZACIT_ANALYZA.md` |
| server, Docker, DNS, e-mail, zálohy | `infra/README_infra.md` |
| n8n: import, credentials, test, MCP, LiteLLM | `n8n/00_README_n8n.md` |
| generátor, audit, API, učení | `pipeline/README.md` |
| stavy leadu | `sheets/STATUSY.md` |
| texty e-mailů | `emails/` |
