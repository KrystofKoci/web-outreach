# Infrastruktura – krok za krokem pro začátečníka

Celý systém běží na **jednom malém VPS** v Dockeru. Nepotřebuješ umět Linux do hloubky – stačí umět se připojit přes SSH a kopírovat příkazy. Počítej s **~2 hodinami** na první zprovoznění (většinu času čekáš na DNS a klikáš v Google Cloud Console).

```
 internet ──► Caddy (80/443, HTTPS zdarma)
               ├── n8n.krystofkoci.com     → n8n (workflowy, webhooky, MCP)
               └── nahled.krystofkoci.com  → statické soubory /srv/nahled (náhledy)
 vnitřní síť:  n8n ↔ pipeline:8077 (Python API) ↔ litellm:4000 (LLM brána) ↔ postgres
```

## 0. Co potřebuješ mít připravené

| Co | Kde | Poznámka |
|---|---|---|
| Doména `krystofkoci.com` | registrátor (Wedos, Forpsi, Cloudflare…) | apex + www míří na **Webild** (tvůj web), subdomény `n8n` a `nahled` na VPS |
| E-mail `kontakt@krystofkoci.com` | Google Workspace Business Starter (~7 USD/měs) | nutné kvůli Gmail OAuth v n8n a doručitelnosti (SPF/DKIM/DMARC nastav v Workspace admin) |
| Google Cloud projekt | console.cloud.google.com | Places API (New), Sheets API, Gmail API, OAuth consent screen **In production** |
| Meta Business účet + WhatsApp Business Cloud API | business.facebook.com, developers.facebook.com | dávky ke schválení a eskalace tobě; odpovědi klientům, kteří napíšou první (viz kap. 5a) |
| Anthropic API klíč | console.anthropic.com | předplať kredit, nastav si tam vlastní limit |
| Hetzner účet | console.hetzner.cloud | nebo jiný VPS s Ubuntu 24.04 |

## 1. Server (Hetzner)

1. Hetzner Cloud → **New project** → **Add server**: lokalita Norimberk/Helsinky, image **Ubuntu 24.04**, typ **CX22** (2 vCPU, 4 GB RAM, 40 GB – stačí; pokud bude Playwright v pipeline padat na paměť, zvětši na CX32), **SSH key** nahraj svůj veřejný klíč (na Macu/Linuxu `cat ~/.ssh/id_ed25519.pub`, na Windows `type %USERPROFILE%\.ssh\id_ed25519.pub`; když nemáš, `ssh-keygen -t ed25519`).
2. Po vytvoření si opiš **IPv4 adresu**.
3. Připoj se: `ssh root@<IP>`.
4. Spusť instalaci (nahraď URL svého repozitáře, nebo nahraj složku přes `scp`):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/<TVUJ_GITHUB>/web-outreach/main/infra/install.sh -o install.sh
   bash install.sh https://github.com/<TVUJ_GITHUB>/web-outreach.git
   ```
   Skript nainstaluje Docker, nastaví firewall (jen 22/80/443), založí uživatele `deploy`, naklonuje repozitář do `/opt/web-outreach`, vygeneruje `.env` s náhodnými hesly a spustí kontejnery.
5. Na konci vypíše, co doplnit ručně. **Nezavírej okno**, budeš se vracet.

## 2. DNS

U registrátora přidej dva **A záznamy** na IP serveru:

| Typ | Název | Hodnota | TTL |
|---|---|---|---|
| A | `n8n` | `<IP serveru>` | 300 |
| A | `nahled` | `<IP serveru>` | 300 |

`@` a `www` nech (nebo nastav) podle návodu Webildu – tam běží tvůj vlastní web `krystofkoci.com`. Ověř: `dig +short n8n.krystofkoci.com` musí vrátit IP serveru. Caddy si pak **sám** vystaví HTTPS certifikát (může to trvat minutu po prvním požadavku).

## 3. Vyplnění `.env` (jediný soubor, který vyplňuješ)

```bash
ssh root@<IP>
nano /opt/web-outreach/infra/.env      # Ctrl+O uložit, Ctrl+X zavřít
bash /opt/web-outreach/infra/install.sh   # znovu – vygeneruje tajemství, spustí vše, naimportuje workflowy
bash /opt/web-outreach/infra/check_env.sh # ✅/❌ s radou, co opravit (formáty + živé API)
```

Vyplňuješ **jen sekci POVINNÉ** (11 hodnot: e-mail, WhatsApp číslo, IČO, adresa, Google OAuth client ID+secret, Places klíč, Anthropic klíč, 3× WhatsApp ID/token). Sekci „DOPLNÍ SE SAMO“ nech prázdnou – `install.sh` tajemství vygeneruje (`openssl rand`) a zapíše zpět, `SHEET_ID` zapíše `set_sheet_id.sh`. Volitelné hodnoty mají rozumné výchozí nastavení.

Nech zatím `OUTREACH_ENABLED=false` a `TEST_MODE=true`. Po ruční změně `.env` vždy `cd /opt/web-outreach/infra && docker compose up -d`.

## 4. Kde co získat (klikací část)

**Google Cloud (jeden projekt na vše):**
1. console.cloud.google.com → nový projekt „web-outreach“, připoj billing účet (Places API to vyžaduje; měsíční kredit Googlu běžný provoz pokryje).
2. *APIs & Services → Library*: zapni **Places API (New)**, **Google Sheets API**, **Google Drive API**, **Gmail API**, volitelně **PageSpeed Insights API**.
3. *Credentials → Create credentials → API key* → omez na Places API (New) (+ PageSpeed) → `PLACES_API_KEY` (a `PAGESPEED_API_KEY`).
4. *OAuth consent screen*: typ **External**, název „Web outreach“, tvůj e-mail, a hlavně **Publish app → In production** (jinak přihlášení v n8n vyprší po 7 dnech).
5. *Credentials → Create OAuth client ID → Web application*, Authorized redirect URI: `https://n8n.krystofkoci.com/rest/oauth2-credential/callback` → `GOOGLE_OAUTH_CLIENT_ID` a `GOOGLE_OAUTH_CLIENT_SECRET`.
6. Google může u Gmail scope ukázat varování „unverified app“ – pro tvůj vlastní účet klikni *Advanced → Go to … (unsafe)*; ověření aplikace není pro jednoho uživatele potřeba.

**Google Sheets (CRM):** nic nezakládáš ručně – workflow **00 Nastavení** vytvoří sešit „Web outreach CRM“ se všemi listy, hlavičkami a doporučenou frontou a pošle ti `SHEET_ID`; ten zapíše `bash infra/set_sheet_id.sh <ID>`.

**WhatsApp:** viz kapitola „5a. WhatsApp Cloud API – založení“ (šablony vytvoří `bash infra/whatsapp_templates.sh`).

**LiteLLM virtuální klíč (volitelné):** bez něj se použije `LITELLM_MASTER_KEY`. Oddělený klíč s vlastním rozpočtem:
```bash
cd /opt/web-outreach/infra
docker compose exec litellm sh -c 'curl -s http://127.0.0.1:4000/key/generate -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" -d "{\"key_alias\":\"n8n\",\"max_budget\":20,\"budget_duration\":\"30d\"}"'
```
Výstup `"key":"sk-…"` zapiš do `.env` jako `LLM_API_KEY` a spusť `install.sh` znovu (přepíše credential LiteLLM).

## 5. n8n – co udělá install.sh a co ty

`install.sh` po startu kontejnerů sám: naimportuje workflowy 00–08 (`n8n import:workflow`, poprvé; `--reimport` přepíše) a vytvoří credentials **Pipeline API**, **WhatsApp Cloud API**, **LiteLLM**, **Anthropic (záloha)**, **MCP read/admin token** a dva Google credentials s vyplněným client ID/secret. Ty uděláš jen:

1. Otevři `https://n8n.krystofkoci.com`, založ účet majitele, v *Settings → Personal* zapni 2FA.
2. *Credentials* → **Google Sheets – outreach** → **Sign in with Google** → vyber svůj Google účet → povol → *Save*.
3. *Credentials* → **Gmail – kontakt@krystofkoci.com** → **Sign in with Google** → přihlas se jako **kontakt@krystofkoci.com** → povol → *Save*.
4. Workflow **00 Nastavení** → *Execute workflow* → `bash infra/set_sheet_id.sh <SHEET_ID>` → `bash infra/activate.sh`.

Podrobnosti k workflowům: `../n8n/00_README_n8n.md`.

## 5a. WhatsApp Cloud API – založení

Systém posílá přes WhatsApp **jen tobě** (odkaz na dávku ke schválení, eskalace, krátké upozornění na report) a odpovídá **jen klientům, kteří napsali první** (do 24 h od jejich zprávy). Cold WhatsApp nikdy. Firmy se prvně oslovují výhradně e-mailem.

1. **Meta Business účet:** business.facebook.com → vytvoř firmu (tvoje jméno / OSVČ), ověř e-mail. Ověření firmy (Business verification, doklad o IČO) zvedne limity – pro posílání sobě a pár odpovědí klientům na začátku stačí neověřený účet.
2. **App:** developers.facebook.com → *My Apps → Create app* → typ **Business** → přidej produkt **WhatsApp**. Meta automaticky založí WhatsApp Business Account (WABA).
3. **Testovací vs. vlastní číslo:**
   - *Testovací číslo* (API Setup) je zdarma a hned funguje, ale smí psát jen na max. 5 ověřených příjemců (přidej tam své `OWNER_WHATSAPP`) – ideální na první test.
   - *Vlastní číslo* (doporučeno pro provoz, protože na něj budou psát klienti): *WhatsApp Manager → Phone numbers → Add* – číslo nesmí být zároveň aktivní v běžné aplikaci WhatsApp (nebo použij režim koexistence, pokud ho Meta pro tvé číslo nabízí). Nastav zobrazované jméno „Kryštof Kočí“ (schvaluje Meta).
   - `WHATSAPP_PHONE_NUMBER_ID` = *Phone number ID* z API Setup (ne samotné číslo).
4. **Trvalý token:** *Business Settings → Users → System users → Add* (role Admin) → *Assign assets* (app + WABA) → *Generate token* s oprávněními `whatsapp_business_messaging`, `whatsapp_business_management`, bez expirace → `WHATSAPP_TOKEN`. (Dočasný token z API Setup vyprší za 24 h – jen na test.)
5. **Šablony ke schválení** (*WhatsApp Manager → Message templates → Create*, kategorie **Utility**, jazyk Czech = `cs`; schválení obvykle minuty až hodiny):
   - `batch_ready` – tělo např. „Nová dávka ke schválení: {{1}} návrhů webů. Otevřete: {{2}}“ (ukázka: {{1}}=10, {{2}}=https://n8n.krystofkoci.com/webhook/approve?batch=…). Business-initiated zpráva mimo 24h okno **musí** jít šablonou – proto i zprávy tobě jdou přes ni.
   - `escalation` – „Je potřeba vaše odpověď: {{1}}. Důvod: {{2}}. Podrobnosti máte v e-mailu.“
   - `weekly_report` (volitelná) – „Týdenní přehled je v e-mailu: {{1}}“. Když ji nechceš, nastav `WHATSAPP_TEMPLATE_REPORT=` prázdné → report jde jen e-mailem.
   - Parametry nesmí obsahovat zalomení řádku – workflowy je čistí samy. Názvy šablon a jazyk lze změnit v `.env` (`WHATSAPP_TEMPLATE_*`).
6. **Webhook (příchozí zprávy klientů):** v app → *WhatsApp → Configuration → Webhook*: Callback URL `https://n8n.krystofkoci.com/webhook/whatsapp`, Verify token = `WHATSAPP_VERIFY_TOKEN` z `.env` (workflow 05 musí být aktivní – odpoví na ověření). Pak *Webhook fields → messages → Subscribe*. `WHATSAPP_APP_SECRET` (App Settings → Basic) slouží k ověření podpisu příchozích zpráv.
7. **Test:** v n8n spusť ručně workflow 03 (s aspoň jedním leadem `awaiting_approval`) → přijde WhatsApp i e-mail s odkazem. Pak napiš z jiného telefonu na firemní číslo → v n8n *Executions* workflow 05 uvidíš příchozí zprávu.
8. **Ceny (orientačně, ověř aktuální ceník Meta pro CZ a země klientů):** Meta účtuje za doručenou šablonu podle kategorie a země příjemce; *utility* šablona do ČR řádově jednotky centů (≈ 0,01–0,03 USD), *marketing* je dražší (tu nepoužíváme). Odpovědi v rámci 24h okna po zprávě klienta (service conversation) jsou podle aktuálních pravidel zdarma nebo výrazně levnější. Při 3 dávkách denně + eskalacích počítej s jednotkami USD měsíčně. Platební kartu přidej ve WhatsApp Manageru (*Payment settings*), jinak se po vyčerpání bezplatné kvóty šablony neodešlou.

## 6. Ověření, že vše běží

```bash
cd /opt/web-outreach/infra
docker compose ps                      # všechny služby "running (healthy)"
docker compose logs -f --tail=50 n8n   # Ctrl+C ukončí sledování
docker compose exec n8n wget -qO- http://pipeline:8077/health   # {"ok":true,…}
curl -I https://nahled.krystofkoci.com/ # HTTP/2 200 + X-Robots-Tag: noindex
```

## 7. Náklady (orientačně, měsíčně)

| Položka | Cena | Poznámka |
|---|---|---|
| Hetzner CX22 | ~4,5 € | CX32 ~7 € pokud bude málo RAM |
| Doména .cz | ~0,3 € (≈ 300 Kč/rok) | |
| Google Workspace Business Starter | ~7 USD | kvůli kontakt@ a doručitelnosti |
| Google Places API (New) | 0–30 USD | 30 hledání/den × Text Search + Details; Google dává 200 USD kredit měsíčně → prakticky zdarma |
| PageSpeed API, Pexels | 0 | |
| Anthropic (přes LiteLLM) | ≤ 20 USD | tvrdý strop `LLM_MONTHLY_BUDGET_USD` |
| WhatsApp utility šablony tobě (dávky 3×/den, eskalace, report) | ~2–6 USD | orientačně, ověř aktuální ceník Meta; odpovědi klientům v 24h okně jsou levnější / zdarma podle aktuálních pravidel |
| n8n (self-host), Caddy, LiteLLM | 0 | |
| **Celkem** | **≈ 15–35 USD** | |

## 8. Bezpečnost – co je uděláno a na co nesahat

- Zvenku jsou otevřené jen porty 22, 80, 443 (ufw). Postgres, LiteLLM, pipeline a n8n jsou jen ve vnitřní Docker síti.
- `fail2ban` blokuje hádání SSH hesel; přihlašuj se jen klíčem (`PasswordAuthentication no` v `/etc/ssh/sshd_config` – install.sh to nemění, udělej po ověření, že klíč funguje).
- Všechna tajemství jsou **jen** v `infra/.env` (práva 600, v `.gitignore`). `N8N_ENCRYPTION_KEY` šifruje credentials v n8n – **po prvním startu ho nikdy neměň** a měj ho v záloze.
- n8n: jeden uživatel, 2FA, žádné veřejné sdílení workflowů. Veřejné webhooky: `/webhook/odhlasit` (HMAC `UNSUB_SECRET`), `/webhook/form` (honeypot), `/webhook/approve` + `/webhook/approve-action` (HMAC `APPROVAL_SECRET`, platnost 24 h) a `/webhook/whatsapp` (verify token + podpis `WHATSAPP_APP_SECRET`). Vše ostatní chce token.
- MCP: `MCP_TOKEN_READ` můžeš dát AI_COM / revizorům (jen čtení), `MCP_TOKEN_ADMIN` nikomu.
- Náhledy mají `X-Robots-Tag: noindex`, žádný výpis adresářů, mažou se po 60 dnech.
- Aktualizace systému: `unattended-upgrades` běží automaticky; Docker obrazy aktualizuješ ručně `./update.sh` (watchtower je v compose zakomentovaný – zapni až po pár týdnech stabilního provozu).

## 9. Zálohy a obnova

`backup.sh` běží denně 03:30 (cron uživatele `deploy`) a ukládá do `/var/backups/web-outreach`: dump obou databází, `n8n_data` (klíče a nastavení), náhledy a kopii `.env`. Uchovává 14 dní. **Doporučeno:** odkomentuj na konci `backup.sh` `rclone sync` na Hetzner Storage Box (1 TB za ~3 €/měs) nebo Backblaze – záloha na stejném serveru nechrání proti smazání serveru.

**Obnova na novém serveru:**
```bash
bash install.sh <repo>                       # čistá instalace
cd /opt/web-outreach/infra && docker compose down
cp /cesta/k/zaloze/env-<datum>.bak .env      # VČETNĚ původního N8N_ENCRYPTION_KEY
docker compose up -d postgres && sleep 10
gunzip -c n8n-db-<datum>.sql.gz     | docker compose exec -T postgres psql -U outreach -d n8n
gunzip -c litellm-db-<datum>.sql.gz | docker compose exec -T postgres psql -U outreach -d litellm
docker run --rm -v web-outreach_n8n_data:/dst -v /cesta/k/zaloze:/src alpine sh -c "cd /dst && tar -xzf /src/n8n-data-<datum>.tar.gz"
docker run --rm -v web-outreach_previews:/dst -v /cesta/k/zaloze:/src alpine sh -c "cd /dst && tar -xzf /src/previews-<datum>.tar.gz"
docker compose up -d
```

## 10. Běžné problémy

| Příznak | Příčina / řešení |
|---|---|
| `https://n8n.…` nejde, Caddy log „obtaining certificate“ | DNS ještě nemíří na server, nebo port 80 blokovaný. `dig +short n8n.krystofkoci.com`. |
| n8n hlásí „Google credential expired“ po týdnu | OAuth consent screen je v režimu *Testing* → přepni na *In production*. |
| Nepřišla WhatsApp zpráva s dávkou | Šablona `batch_ready` není schválená, `OWNER_WHATSAPP` není ve formátu E.164, nebo vypršel token. Odkaz vždy přijde i e-mailem; chybu uvidíš v n8n *Executions* (uzel „WhatsApp: …“). |
| `/process` trvá dlouho / padá | Playwright potřebuje RAM – `docker stats`; zvaž CX32. Logy: `docker compose logs pipeline`. |
| LiteLLM vrací 429 „budget exceeded“ | Měsíční strop vyčerpán – zvyš `LLM_MONTHLY_BUDGET_USD` a `docker compose up -d litellm`. |
| E-maily končí ve spamu | Nastav SPF, DKIM, DMARC v Google Workspace; posílej z nové domény max 20–30/den první měsíc. |
| Změna času (Kostarika) | `OWNER_TZ=America/Costa_Rica` v `.env`, `docker compose up -d n8n`. Dávky a reporty se posunou; okna leadů se řídí jejich `tz`, ta se nemění. |
