# Vyplň a spusť (1 strana)

## 1. Účty (jednou, ~1–2 h klikání)

| Účet | Odkaz | Co z něj vezmeš do `infra/.env` |
|---|---|---|
| Hetzner Cloud (server Ubuntu 24.04, CX22) | https://console.hetzner.cloud | IP adresa → DNS |
| Doména krystofkoci.com + DNS | tvůj registrátor | A záznamy `n8n` a `nahled` → IP serveru (`@`/`www` nech na Webildu) |
| Google Workspace (schránka kontakt@krystofkoci.com) | https://workspace.google.com | nic – přihlásíš ji v n8n; nastav SPF/DKIM/DMARC |
| Google Cloud projekt | https://console.cloud.google.com | `PLACES_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` (redirect URI `https://n8n.krystofkoci.com/rest/oauth2-credential/callback`, consent screen **In production**; zapni Places API (New), Sheets, Drive, Gmail) |
| Anthropic | https://console.anthropic.com | `ANTHROPIC_API_KEY` |
| Meta Business + WhatsApp Cloud API | https://business.facebook.com, https://developers.facebook.com | `WHATSAPP_TOKEN` (System user, bez expirace), `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID`, volitelně `WHATSAPP_APP_SECRET` |
| Ty | – | `OWNER_EMAIL`, `OWNER_WHATSAPP` (+420…), `OWNER_ICO`, `OWNER_ADDRESS` |

Podrobný návod ke každému účtu: `infra/README_infra.md` (kap. 4 a 5a).

## 2. Příkazy na serveru (jako root)

```bash
# z tvého PC: scp web-outreach.zip root@<IP>:/opt/ && ssh root@<IP>
cd /opt && apt-get install -y unzip && unzip web-outreach.zip   # → /opt/web-outreach
bash /opt/web-outreach/infra/install.sh        # 1. běh vytvoří infra/.env a skončí
nano /opt/web-outreach/infra/.env              # vyplň JEN sekci POVINNÉ (11 hodnot)
bash /opt/web-outreach/infra/install.sh        # 2. běh: tajemství, Docker, import workflowů + credentials
bash /opt/web-outreach/infra/check_env.sh      # ✅/❌ formáty + živé API (Places, Anthropic, WhatsApp, LiteLLM…)
```

## 3. n8n v prohlížeči (4 kroky)

1. Otevři https://n8n.krystofkoci.com → založ účet → zapni 2FA.
2. *Credentials* → **Google Sheets – outreach** → **Sign in with Google** → *Save*.
3. *Credentials* → **Gmail – kontakt@krystofkoci.com** → **Sign in with Google** (jako kontakt@) → *Save*.
4. Workflow **00 Nastavení** → *Execute workflow* → e-mailem ti přijde SHEET_ID.

## 4. Dokončení

```bash
bash /opt/web-outreach/infra/set_sheet_id.sh <SHEET_ID>    # zapíše do .env, restart n8n
bash /opt/web-outreach/infra/whatsapp_templates.sh         # šablony batch_ready, escalation, weekly_report → čekej na schválení Metou
bash /opt/web-outreach/infra/activate.sh                   # zapne workflowy 01–08
```
Meta app → WhatsApp → Configuration → Webhook: `https://n8n.krystofkoci.com/webhook/whatsapp`, Verify token vypsal `install.sh` (je v `.env` jako `WHATSAPP_VERIFY_TOKEN`), odebírej pole *messages*.

## 5. Test a ostrý start

1. **TEST_MODE test** (`TEST_MODE=true`, `OUTREACH_ENABLED=true` v `.env` → `cd /opt/web-outreach/infra && docker compose up -d n8n`): projdi 10 kroků v `n8n/00_README_n8n.md` kap. 4 – všechny e-maily firmám jdou jen tobě.
2. **Ostrý start:** `TEST_MODE=false`, první 2 týdny `DAILY_CAP=15` → `docker compose up -d n8n`. Dávky ke schválení ti chodí v 08:00, 11:00, 14:00 (WhatsApp + e-mail). Nic se neodešle bez tvého ✅.
3. **Nouzově vypnout:** `OUTREACH_ENABLED=false` (odesílání) nebo `bash infra/activate.sh off` (vše).
4. Od 29. 10. na Kostarice: `OWNER_TZ=America/Costa_Rica` → `docker compose up -d n8n`. Kostarika se jako trh nikdy nezpracuje.
