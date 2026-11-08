#!/usr/bin/env bash
# Zapne (aktivuje) workflowy 01–08 v n8n. 00_setup zůstává ruční.
# Použití: bash infra/activate.sh          – zapnout vše
#          bash infra/activate.sh off      – vypnout vše (nouzově; hlavní vypínač je OUTREACH_ENABLED v .env)
set -euo pipefail
cd "$(dirname "$0")"
STATE=true; [ "${1:-}" = "off" ] && STATE=false
for n in 01 02 03 04 05 06 07 08; do
  docker compose exec -T n8n n8n update:workflow --id="weboutreachwf0$n" --active=$STATE >/dev/null && echo "   workflow $n → active=$STATE"
done
docker compose restart n8n >/dev/null   # změna aktivace přes CLI se projeví po restartu
echo "✅ Hotovo. Stav: OUTREACH_ENABLED=$(grep -E '^OUTREACH_ENABLED=' .env | cut -d= -f2 | awk '{print $1}'), TEST_MODE=$(grep -E '^TEST_MODE=' .env | cut -d= -f2 | awk '{print $1}')"
