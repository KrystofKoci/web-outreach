#!/usr/bin/env bash
# =====================================================================
#  install.sh – čistý Ubuntu 24.04 (Hetzner CX22/CX32) → běžící web-outreach
#
#  Použití (jako root):
#     bash infra/install.sh                 # uvnitř naklonovaného repozitáře
#     bash install.sh https://github.com/<ty>/web-outreach.git   # samostatně
#     bash infra/install.sh --reimport      # znovu naimportovat workflowy (PŘEPÍŠE tvé úpravy v n8n!)
#
#  Co udělá (idempotentně – můžeš pouštět opakovaně):
#   1) docker + compose, firewall 22/80/443, fail2ban, uživatel `deploy`
#   2) repozitář do /opt/web-outreach, infra/.env z .env.example
#   3) vygeneruje prázdná tajemství (openssl rand) a zapíše je zpět do .env
#   4) docker compose up -d, počká na n8n
#   5) naimportuje workflowy (n8n import:workflow) – jen poprvé, nebo s --reimport
#   6) vytvoří credentials bez prohlížeče (Pipeline, WhatsApp, LiteLLM, MCP, Anthropic)
#      + Google Sheets/Gmail s client ID/secret (přihlášení „Sign in with Google“ uděláš v n8n ručně)
# =====================================================================
set -euo pipefail

REPO_URL=""
REIMPORT=0
for a in "$@"; do
  case "$a" in
    --reimport) REIMPORT=1 ;;
    http*|git@*) REPO_URL="$a" ;;
  esac
done
DEPLOY_USER="deploy"
APP_DIR="/opt/web-outreach"

say()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
warn() { printf '\n\033[1;33m!!  %s\033[0m\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then echo "Spusť jako root (sudo bash infra/install.sh)"; exit 1; fi
grep -qi 'ubuntu' /etc/os-release || warn "Testováno na Ubuntu 24.04 – pokračuji bez záruky."

say "1/8 Systémové balíčky"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y ca-certificates curl gnupg git ufw fail2ban unattended-upgrades jq openssl python3

say "2/8 Docker + Docker Compose"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

say "3/8 Firewall (jen 22, 80, 443) + fail2ban"
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw allow 443/udp >/dev/null
ufw --force enable
systemctl enable --now fail2ban

say "4/8 Uživatel '$DEPLOY_USER'"
id "$DEPLOY_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$DEPLOY_USER"
usermod -aG docker "$DEPLOY_USER"
if [ -f /root/.ssh/authorized_keys ]; then
  mkdir -p /home/$DEPLOY_USER/.ssh
  cp /root/.ssh/authorized_keys /home/$DEPLOY_USER/.ssh/authorized_keys
  chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
  chmod 700 /home/$DEPLOY_USER/.ssh && chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys
fi

say "5/8 Repozitář → $APP_DIR"
SRC_DIR="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd || true)"
if [ -d "$APP_DIR/.git" ] && [ "$SRC_DIR" != "$APP_DIR" ]; then
  git -C "$APP_DIR" pull --ff-only || warn "git pull selhal – pokračuji se stávající verzí"
elif [ -n "$REPO_URL" ] && [ ! -d "$APP_DIR" ]; then
  git clone "$REPO_URL" "$APP_DIR"
elif [ -f "$SRC_DIR/infra/docker-compose.yml" ] && [ "$SRC_DIR" != "$APP_DIR" ]; then
  mkdir -p "$APP_DIR" && cp -rn "$SRC_DIR/." "$APP_DIR/"
fi
[ -f "$APP_DIR/infra/docker-compose.yml" ] || { echo "Repozitář nenalezen. Spusť: bash install.sh https://github.com/…/web-outreach.git"; exit 1; }
chown -R $DEPLOY_USER:$DEPLOY_USER "$APP_DIR"
cd "$APP_DIR/infra"

say "6/8 infra/.env – kontrola a generování tajemství"
if [ ! -f .env ]; then
  cp .env.example .env
  warn "Vytvořen $APP_DIR/infra/.env – vyplň sekci POVINNÉ (nano $APP_DIR/infra/.env) a spusť install.sh znovu."
fi
chmod 600 .env; chown $DEPLOY_USER:$DEPLOY_USER .env

# hodnota proměnné z .env (bez inline komentáře, bez uvozovek)
envget() { grep -E "^$1=" .env | tail -1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^[[:space:]]+//; s/[[:space:]]+$//; s/^"(.*)"$/\1/'; }
envset() {
  if grep -qE "^$1=" .env; then sed -i -E "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}
gen_if_empty() { # název, počet bajtů, prefix
  if [ -z "$(envget "$1")" ]; then envset "$1" "${3:-}$(openssl rand -hex "$2")"; echo "   vygenerováno: $1"; fi
}
gen_if_empty POSTGRES_PASSWORD 24
gen_if_empty N8N_ENCRYPTION_KEY 32
gen_if_empty API_TOKEN 32
gen_if_empty APPROVAL_SECRET 32
gen_if_empty UNSUB_SECRET 32
gen_if_empty WHATSAPP_VERIFY_TOKEN 16
gen_if_empty MCP_TOKEN_READ 32
gen_if_empty MCP_TOKEN_ADMIN 32
gen_if_empty LITELLM_MASTER_KEY 24 "sk-"

MISSING=""
for v in OWNER_EMAIL OWNER_WHATSAPP OWNER_ICO OWNER_ADDRESS GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET PLACES_API_KEY ANTHROPIC_API_KEY; do
  :
  [ -n "$(envget $v)" ] || MISSING="$MISSING $v"
done
[ -n "$(envget WHATSAPP_TOKEN)" ] || warn "WhatsApp zatím není vyplněný – schvalování a eskalace půjdou jen e-mailem (doplníš později a spustíš install.sh znovu)."
if [ -n "$MISSING" ]; then
  warn "V infra/.env chybí povinné hodnoty:$MISSING"
  warn "Doplň je (nano $APP_DIR/infra/.env) a spusť znovu: bash $APP_DIR/infra/install.sh"
  exit 2
fi

say "7/8 Spouštím kontejnery (první start stahuje obrazy, 2–5 min)"
sudo -u $DEPLOY_USER docker compose pull --ignore-buildable || true
sudo -u $DEPLOY_USER docker compose up -d --build
printf "   čekám na n8n"
for i in $(seq 1 60); do
  if docker compose exec -T n8n wget -qO- http://127.0.0.1:5678/healthz >/dev/null 2>&1; then echo " – běží"; break; fi
  printf "."; sleep 5
  [ "$i" = 60 ] && { echo; warn "n8n se nespustil do 5 min – docker compose logs n8n"; exit 3; }
done

say "8/8 Workflowy a credentials v n8n"
MARKER="$APP_DIR/infra/.n8n_imported"
if [ ! -f "$MARKER" ] || [ "$REIMPORT" = 1 ]; then
  docker compose exec -T n8n n8n import:workflow --separate --input=/workflows
  touch "$MARKER"; chown $DEPLOY_USER:$DEPLOY_USER "$MARKER"
  echo "   workflowy naimportovány (neaktivní – aktivuje je infra/activate.sh)"
else
  echo "   workflowy už jsou naimportované (znovu: install.sh --reimport – přepíše tvé úpravy)"
fi

TMPDIR_CREDS="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_CREDS"' EXIT
LITELLM_KEY="$(envget LLM_API_KEY)"; [ -n "$LITELLM_KEY" ] || LITELLM_KEY="$(envget LITELLM_MASTER_KEY)"
export C_API_TOKEN="$(envget API_TOKEN)" C_WA="$(envget WHATSAPP_TOKEN)" C_LLM="$LITELLM_KEY" C_ANT="$(envget ANTHROPIC_API_KEY)" \
       C_MR="$(envget MCP_TOKEN_READ)" C_MA="$(envget MCP_TOKEN_ADMIN)" C_GID="$(envget GOOGLE_OAUTH_CLIENT_ID)" C_GSEC="$(envget GOOGLE_OAUTH_CLIENT_SECRET)" \
       C_SENDER="$(envget SENDER_EMAIL)"
python3 - "$TMPDIR_CREDS" <<'PY'
import json, os, sys
d = sys.argv[1]; e = os.environ
base = [
  {"id": "pipeline-api", "name": "Pipeline API", "type": "httpHeaderAuth", "data": {"name": "Authorization", "value": "Bearer " + e["C_API_TOKEN"]}},
  {"id": "whatsapp-cloud", "name": "WhatsApp Cloud API", "type": "httpHeaderAuth", "data": {"name": "Authorization", "value": "Bearer " + e["C_WA"]}},
  {"id": "litellm", "name": "LiteLLM", "type": "openAiApi", "data": {"apiKey": e["C_LLM"], "url": "http://litellm:4000/v1"}},
  {"id": "anthropic-zaloha", "name": "Anthropic (záloha)", "type": "anthropicApi", "data": {"apiKey": e["C_ANT"]}},
  {"id": "mcp-read", "name": "MCP read token", "type": "httpBearerAuth", "data": {"token": e["C_MR"]}},
  {"id": "mcp-admin", "name": "MCP admin token", "type": "httpBearerAuth", "data": {"token": e["C_MA"]}},
]
sender = e.get("C_SENDER") or "kontakt@krystofkoci.com"
google = [
  {"id": "gsheets-outreach", "name": "Google Sheets – outreach", "type": "googleSheetsOAuth2Api", "data": {"clientId": e["C_GID"], "clientSecret": e["C_GSEC"]}},
  {"id": "gmail-kontakt", "name": "Gmail – " + sender, "type": "gmailOAuth2", "data": {"clientId": e["C_GID"], "clientSecret": e["C_GSEC"]}},
]
json.dump(base, open(os.path.join(d, "creds_base.json"), "w"), ensure_ascii=False)
json.dump(google, open(os.path.join(d, "creds_google.json"), "w"), ensure_ascii=False)
PY
chmod 600 "$TMPDIR_CREDS"/*.json
import_creds() {
  docker compose cp "$1" n8n:/tmp/creds.json >/dev/null
  docker compose exec -T -u root n8n chown node /tmp/creds.json 2>/dev/null || true
  docker compose exec -T n8n n8n import:credentials --input=/tmp/creds.json
  docker compose exec -T -u root n8n rm -f /tmp/creds.json || docker compose exec -T n8n rm -f /tmp/creds.json
}
import_creds "$TMPDIR_CREDS/creds_base.json"
GMARK="$APP_DIR/infra/.n8n_google_creds"
if [ ! -f "$GMARK" ]; then
  # Google credentials jen poprvé – opakovaný import by smazal tvé přihlášení (OAuth token)
  import_creds "$TMPDIR_CREDS/creds_google.json"
  touch "$GMARK"; chown $DEPLOY_USER:$DEPLOY_USER "$GMARK"
fi
rm -rf "$TMPDIR_CREDS"
echo "   credentials vytvořeny (dočasné JSON soubory smazány)"

# denní zálohy 03:30
if ! crontab -u $DEPLOY_USER -l 2>/dev/null | grep -q backup.sh; then
  (crontab -u $DEPLOY_USER -l 2>/dev/null; echo "30 3 * * * $APP_DIR/infra/backup.sh >> /var/log/web-outreach-backup.log 2>&1") | crontab -u $DEPLOY_USER -
  touch /var/log/web-outreach-backup.log && chown $DEPLOY_USER /var/log/web-outreach-backup.log
fi

IP=$(curl -4 -s --max-time 5 https://ifconfig.me || hostname -I | awk '{print $1}')
N8N_HOST_V="$(envget N8N_HOST)"; N8N_HOST_V="${N8N_HOST_V:-n8n.krystofkoci.com}"
cat <<MSG

=====================================================================
 HOTOVO. Další kroky (viz VYPLN_A_SPUST.md):
=====================================================================
 0) DNS: A záznamy  n8n → $IP   a   nahled → $IP   (krystofkoci.com @ a www nech na Webildu)
 1) bash $APP_DIR/infra/check_env.sh            – ověří klíče a živé API
 2) https://$N8N_HOST_V → založ účet, zapni 2FA → Credentials:
      „Google Sheets – outreach“ → Sign in with Google → Save
      „Gmail – …“                → Sign in with Google (jako kontakt@) → Save
 3) Workflow „00 Nastavení“ → Execute workflow → přijde SHEET_ID →
      bash $APP_DIR/infra/set_sheet_id.sh <SHEET_ID>
 4) bash $APP_DIR/infra/whatsapp_templates.sh   – šablony batch_ready / escalation / weekly_report
    Meta webhook: https://$N8N_HOST_V/webhook/whatsapp, verify token: $(envget WHATSAPP_VERIFY_TOKEN)
 5) bash $APP_DIR/infra/activate.sh             – zapne workflowy (TEST_MODE=true)
 6) test → v .env OUTREACH_ENABLED=true, pak TEST_MODE=false → docker compose up -d n8n
=====================================================================
MSG
