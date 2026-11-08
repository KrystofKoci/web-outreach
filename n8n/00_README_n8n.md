# n8n – workflowy, nastavení, testy

Import i credentials dělá `infra/install.sh` automaticky (viz `VYPLN_A_SPUST.md` v kořeni). Ručně se v n8n přihlašuje jen Google (2× „Sign in with Google“). Komunikace: **firmám jen e-mail** (první kontakt), **tobě WhatsApp + e-mail**, klientům WhatsApp jen když napíšou první. Žádné hovory ani schůzky – vše se dotahuje písemně.

| Soubor | Co dělá | Spouštěč |
|---|---|---|
| `00_setup.json` | vytvoří Google sešit „Web outreach CRM“ (leads, queue, deals, weights, blocklist + hlavičky + doporučená fronta), pošle SHEET_ID | ručně, jednou |
| `01_lead_finder.json` | queue + weights → `/plan_day` → `/search` → dedup → `leads` (`new`) | denně 06:30 |
| `02_audit_and_build.json` | `new` → `/process` → náhled + e-mail → `awaiting_approval` / `needs_email` / `skipped` | každých 20 min |
| `03_approval_batches.json` | dávka ~10 leadů → WhatsApp šablona `batch_ready` + e-mail s odkazem → mobilní schvalovací stránka (`/webhook/approve`, akce `/webhook/approve-action`, HMAC 24 h) | 08:00, 11:00, 14:00 |
| `04_outreach_sequence.json` | e-mail 1 → +3 prac. dny → 2 → +4 prac. dny → 3; okna v čase příjemce; potlačení; A/B/C předměty | každých 15 min |
| `05_inbox_agent.json` | e-mail (Gmail) + příchozí WhatsApp (`/webhook/whatsapp`): bounce, OOO, ruční převzetí, klasifikace, AI agent s guardrailem, eskalace (WhatsApp `escalation` + e-mail) | každou minutu / webhook |
| `06_reports_learning.json` | týdenní report (e-mail + WhatsApp), nedělní učení, měsíční úklid, won → deals, **error workflow** | různé |
| `07_webhooks_public.json` | `GET /webhook/odhlasit`, `POST /webhook/form` | veřejné webhooky |
| `08_mcp_server.json` | MCP `outreach-read` a `outreach-admin` | MCP |

## 1. Co udělá install.sh (nemusíš nic)

- `n8n import:workflow --separate --input=/workflows` – všechny workflowy (stabilní ID `weboutreachwf000`–`008`, neaktivní). Opakovaný import jen `install.sh --reimport` (přepíše tvé úpravy, např. prompty!).
- `n8n import:credentials` z dočasného JSON (pak se smaže):

| Credential | Typ | Obsah |
|---|---|---|
| Pipeline API | Header Auth | `Authorization: Bearer <API_TOKEN>` |
| WhatsApp Cloud API | Header Auth | `Authorization: Bearer <WHATSAPP_TOKEN>` |
| LiteLLM | OpenAI | klíč `LLM_API_KEY` (nebo master key), Base URL `http://litellm:4000/v1` |
| Anthropic (záloha) | Anthropic | `ANTHROPIC_API_KEY` (jen pro odpojený záložní uzel) |
| MCP read token / MCP admin token | Bearer Auth | `MCP_TOKEN_READ` / `MCP_TOKEN_ADMIN` |
| Google Sheets – outreach, Gmail – kontakt@krystofkoci.com | OAuth2 | client ID + secret z `.env`; **přihlášení uděláš ty** |

Když změníš token v `.env` (např. nový WhatsApp token), spusť `install.sh` znovu – přepíše credentials kromě Google (tvé přihlášení zůstane).

## 2. Tvoje kroky v n8n (4 kliky)

1. `https://n8n.krystofkoci.com` → založ účet majitele → *Settings → Personal* → 2FA.
2. *Credentials* → **Google Sheets – outreach** → **Sign in with Google** → *Save*.
3. *Credentials* → **Gmail – kontakt@krystofkoci.com** → **Sign in with Google** jako kontakt@ → *Save*.
4. Workflow **00 Nastavení** → *Execute workflow* → na server `bash infra/set_sheet_id.sh <ID>` → `bash infra/activate.sh`.

U každého workflow pak v *Settings → Error workflow* vyber „06 Reporty, učení, úklid a chyby“ (pády ti přijdou e-mailem a na WhatsApp).

## 3. Proměnné (`infra/.env` → kontejner n8n)

Workflowy čtou `$env.*`. Nejdůležitější: `SHEET_ID` (zapíše set_sheet_id.sh), `OWNER_EMAIL`, `OWNER_WHATSAPP`, `OWNER_TZ`, `APPROVAL_BATCH`, `APPROVAL_SECRET`, `DAILY_CAP`, `SEND_PER_RUN`, `TEST_MODE`, `OUTREACH_ENABLED`, `UNSUB_SECRET` (neměnit), `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE_*`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `MCP_TOKEN_*`, `BLOCKED_COUNTRIES` (CR je blokovaná vždy). Popis každé je v `infra/.env.example`. Po změně: `docker compose up -d n8n`.

## 4. Test s jedním falešným leadem (TEST_MODE=true)

1. `.env`: `TEST_MODE=true`, `OUTREACH_ENABLED=true`; `docker compose up -d n8n`.
2. Do listu `leads` vlož řádek: `id=test-1`, `name=Test Instalatér`, `city=Brno`, `country=CZ`, `lang=cs`, `market=cz`, `tz=Europe/Prague`, `website=<nějaký starý web>`, `email=<tvoje druhá adresa>`, `status=new`.
3. **02** → *Execute workflow* → řádek dostane náhled a `awaiting_approval`.
4. **03** → *Execute workflow* → přijde WhatsApp (`batch_ready`) i e-mail s odkazem → otevři v mobilu → ✏️ uprav předmět → ✅ Schválit.
5. **04** → *Execute workflow* v okně (po–pá 08:30–11:30 / 13:30–16:00 dle `tz`) → e-mail „[TEST] …“ přijde na OWNER_EMAIL, řádek `sent_1`.
6. Odpověz na ten e-mail z jiné adresy → **05** do minuty: e-mail tobě s klasifikací + odpověď agenta. Zkus napsat „můžeme si zavolat?“ → agent slušně odpoví, že vše řešíš písemně. Napiš „beru to“ → eskalace (WhatsApp + e-mail).
7. Klikni na odkaz pro odhlášení v patičce → stránka „Hotovo“, status `unsubscribed`, řádky v `blocklist`.
8. Z jiného telefonu napiš na firemní WhatsApp → neznámé číslo → upozornění tobě; doplň to číslo do `whatsapp` u test-1 a napiš znovu → agent odpoví přes WhatsApp.
9. **06**: spusť uzel „Pondělí 08:00“ → report e-mailem.
10. Smaž testovací řádky; `TEST_MODE=false` až po 2–3 úspěšných kolech.

## 5. Kill switch

- **Vše kromě odpovědí:** `.env` → `OUTREACH_ENABLED=false` → `docker compose up -d n8n`. 01, 02 a 04 se zastaví; inbox agent, webhooky (odhlášení!) a MCP běží dál.
- **Okamžitě vše:** `bash infra/activate.sh off` (zapnutí zpět `bash infra/activate.sh`).
- **Jen agent:** v n8n deaktivuj workflow 05.

## 6. Jak změnit časy dávek

Workflow 03 → uzel **„Dávky 08/11/14“** → tři cron výrazy `0 8 * * *`, `0 11 * * *`, `0 14 * * *` (minuta hodina …), v `OWNER_TZ`. Uprav i `OWNER_APPROVAL_TIMES` v `.env` (informativní). Dávka mimo plán: workflow 03 → *Execute workflow*. Odkaz platí 24 h; prošlý odkaz ukáže „platnost vypršela“.

## 7. LiteLLM

Modely jdou přes `http://litellm:4000/v1` (credential **LiteLLM**). Aliasy: `classify` (Haiku, klasifikace), `agent-reply` (Sonnet, odpovědi), `copy` (Sonnet, texty náhledů v pipeline). Modely, fallbacky a měsíční strop (`LLM_MONTHLY_BUDGET_USD`) jsou v `infra/litellm/config.yaml`. Záloha: v 05 odpojený uzel „Anthropic Chat Model (záloha)“.

## 8. MCP (Claude Code, claude.ai, AI_COM)

| Server | URL | Token | Nástroje |
|---|---|---|---|
| `outreach-read` | `https://n8n.krystofkoci.com/mcp/outreach-read` | `MCP_TOKEN_READ` – smíš dát AI_COM / revizorům | `fronta_ke_schvaleni`, `stav_leadu(id_or_email)`, `report(days)`, `seznam_nahledu`, `kontrola_nahledu(id)` |
| `outreach-admin` | `https://n8n.krystofkoci.com/mcp/outreach-admin` | `MCP_TOKEN_ADMIN` – **jen ty** | `schvalit(id)`, `zamitnout(id)`, `nekontaktovat(id)`, `vytvor_nahled(name, city, country, website?)`, `hledej_firmy(country, city, category, limit)`, `uzavrit_zakazku(id, price, currency)` |

⚠️ `schvalit` spouští odeslání e-mailu (stejně jako ✅ na schvalovací stránce).

```bash
claude mcp add --transport http outreach-read https://n8n.krystofkoci.com/mcp/outreach-read --header "Authorization: Bearer <MCP_TOKEN_READ>"
claude mcp add --transport http outreach-admin https://n8n.krystofkoci.com/mcp/outreach-admin --header "Authorization: Bearer <MCP_TOKEN_ADMIN>"
```
claude.ai: *Settings → Connectors → Add custom connector* → URL + Bearer token. Přesnou URL ověř v uzlu MCP Server Trigger (*Production URL*, podle verze může končit `/sse`).

## 9. Zkontrolovat po importu

- Google Sheets uzly mají dokument `{{ $env.SHEET_ID }}` (By ID) a list podle názvu; u update *Column to match on* = `id`. Po zapsání SHEET_ID otevři jeden Sheets uzel a ověř, že se načtou sloupce.
- Gmail Trigger (05): *Simplify* vypnuté. HTTP uzly „Gmail API“ a „Sheets API“ používají Google credentials (predefined).
- AI uzly: `chainLlm` 1.4, `agent` 1.7, `lmChatOpenAi` 1.2, `outputParserStructured` 1.2, `toolCode` 1.1, `mcpTrigger` 1, `mcpClientTool` 1, `googleSheetsTool` 4.5, `httpRequestTool` 4.2 – pokud n8n nabídne upgrade uzlu, přijmi a zkontroluj *System Message* a `$fromAI`.
- Modely v „Model: classify“ / „Model: agent-reply“ zadané ručně (By ID).
- Meta webhook (05): Callback `https://n8n.krystofkoci.com/webhook/whatsapp`, Verify token `WHATSAPP_VERIFY_TOKEN`, pole *messages*.
- Prompt agenta (uzly `AGENT_SYSTEM_PROMPT`, `AGENT_SYSTEM_PROMPT_EN`, `PRICELIST`) synchronizovat s `docs/03_CENIK_A_MANTINELY_AGENTA.md`; e-mailové šablony v 04 se `emails/`.

## 10. Kontrola před importem

```bash
python3 n8n/validate.py
```
JSON, unikátní názvy uzlů, spoje, typy/verze/pozice, JavaScript Code uzlů (`node --check`) a zákaz nepoužívaných kanálů v `n8n/`, `infra/`, `emails/`, `sheets/`.
