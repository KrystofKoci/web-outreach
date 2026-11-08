#!/usr/bin/env bash
# Malá aktualizace n8n: ceník v. 2 (05 Inbox agent) + opětovné odeslání firem z TEST režimu (04 Outreach).
# Šablony webů, pipeline ani frontu NEMĚNÍ (ty jsou z balíčku „šablony 2“).
# Použití na serveru jako root:
#   bash /opt/web-outreach/infra/aktualizovat.sh /opt/web-outreach-cenik.tgz   # nahraje 04 + 05, TEST_MODE nemění
#   bash /opt/web-outreach/infra/aktualizovat.sh --ostre                        # přepne na ostro (15/den) + LIVE_SINCE
set -euo pipefail
APP=/opt/web-outreach
cd "$APP/infra"
setenv() { if grep -qE "^$1=" .env; then sed -i -E "s|^$1=.*|$1=$2|" .env; else printf '\n%s=%s\n' "$1" "$2" >> .env; fi; echo "   .env: $1=$2"; }

# n8n musí vidět proměnnou LIVE_SINCE (doplní se do docker-compose.yml jen jednou, se zálohou)
if ! grep -q 'LIVE_SINCE:' docker-compose.yml; then
  cp docker-compose.yml "docker-compose.yml.bak-$(date +%Y%m%d-%H%M)"
  sed -i -E 's|^( +)TEST_MODE: \$\{TEST_MODE:-true\}$|&\n\1LIVE_SINCE: ${LIVE_SINCE:-}|' docker-compose.yml
  grep -q 'LIVE_SINCE:' docker-compose.yml || { echo "!! LIVE_SINCE se do docker-compose.yml nepodařilo doplnit – končím, nic se nezměnilo"; exit 1; }
  echo "   docker-compose.yml: doplněno LIVE_SINCE"
fi

if [ "${1:-}" = "--ostre" ]; then
  setenv TEST_MODE false
  setenv DAILY_CAP 15
  setenv OUTREACH_ENABLED true
  # čas přepnutí (jen poprvé): firmy, kterým šel 1. e-mail jen tobě, ho teď dostanou skutečně
  grep -qE '^LIVE_SINCE=.+' .env || setenv LIVE_SINCE "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  docker compose up -d n8n
  sleep 8
  echo "✅ OSTŘE: n8n TEST_MODE=$(docker compose exec -T n8n printenv TEST_MODE), LIVE_SINCE=$(docker compose exec -T n8n printenv LIVE_SINCE)"
  exit 0
fi

PKG="${1:?Zadej cestu k balíčku web-outreach-cenik.tgz}"
gzip -t "$PKG"
tar -xzf "$PKG" -C "$APP" n8n/04_outreach_sequence.json n8n/05_inbox_agent.json infra/stav.sh infra/aktualizovat.sh
chmod +x stav.sh aktualizovat.sh
docker compose up -d n8n          # načte LIVE_SINCE; ostatní hodnoty v .env zůstávají
sleep 10
docker compose exec -T n8n n8n import:workflow --input=/workflows/04_outreach_sequence.json
docker compose exec -T n8n n8n import:workflow --input=/workflows/05_inbox_agent.json
bash ./activate.sh
echo "✅ Nahráno: 04 (firmy z TEST režimu dostanou na ostro 1. e-mail znovu) + 05 (ceník v. 2). TEST_MODE je: $(docker compose exec -T n8n printenv TEST_MODE)"
