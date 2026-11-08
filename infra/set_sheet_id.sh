#!/usr/bin/env bash
# Zapíše SHEET_ID (z e-mailu / WhatsAppu od workflow 00_setup) do infra/.env – jediné místo – a restartuje n8n.
# Použití: bash infra/set_sheet_id.sh 1AbCdEf...   (nebo celou URL tabulky)
set -euo pipefail
cd "$(dirname "$0")"
ARG="${1:-}"
ID="$(printf '%s' "$ARG" | sed -E 's|.*/spreadsheets/d/([A-Za-z0-9_-]+).*|\1|')"
if ! printf '%s' "$ID" | grep -qE '^[A-Za-z0-9_-]{30,}$'; then
  echo "❌ Neplatné SHEET_ID: '$ARG'. Zkopíruj ho z e-mailu „CRM sešit vytvořen“ (dlouhý řetězec z URL tabulky)."; exit 1
fi
[ -f .env ] || { echo "❌ infra/.env neexistuje – nejdřív install.sh"; exit 1; }
if grep -qE '^SHEET_ID=' .env; then sed -i -E "s|^SHEET_ID=.*|SHEET_ID=$ID|" .env; else echo "SHEET_ID=$ID" >> .env; fi
docker compose up -d n8n >/dev/null
echo "✅ SHEET_ID=$ID zapsán do infra/.env, n8n restartován."
echo "   Tabulka: https://docs.google.com/spreadsheets/d/$ID/edit"
