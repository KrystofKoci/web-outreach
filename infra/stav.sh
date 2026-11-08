#!/usr/bin/env bash
# Rychlá kontrola, jestli systém běží: režim, zapnuté workflowy, běhy a chyby za poslední 2 dny.
# Použití na serveru: bash /opt/web-outreach/infra/stav.sh   (nic nemění, jen čte)
set -uo pipefail
cd "$(dirname "$0")"
U=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2); U=${U:-outreach}
echo "== Režim (.env)"
grep -E '^(TEST_MODE|OUTREACH_ENABLED|DAILY_CAP|DAILY_PREVIEW_TARGET|APPROVAL_BATCH|LIVE_SINCE|PREMIUM_TEMPLATES)=' .env
echo "== n8n vidí: TEST_MODE=$(docker compose exec -T n8n printenv TEST_MODE 2>/dev/null)"
echo "== Kontejnery"
docker compose ps --format '{{.Service}}: {{.State}} {{.Health}}'
SQL() { docker compose exec -T postgres psql -U "$U" -d n8n -At -F ' | ' -c "$1"; }
echo "== Workflowy (název | zapnuto)"
SQL "select name, active from workflow_entity order by name;"
echo "== Běhy za 48 h (workflow | stav | počet | poslední)"
SQL "select w.name, e.status, count(*), to_char(max(e.\"startedAt\") at time zone 'UTC','DD.MM. HH24:MI') from execution_entity e join workflow_entity w on w.id=e.\"workflowId\" where e.\"startedAt\" > now() - interval '48 hours' group by 1,2 order by 1,2;"
echo "== Posledních 5 chyb (workflow | čas UTC | id běhu)"
SQL "select w.name, to_char(e.\"startedAt\" at time zone 'UTC','DD.MM. HH24:MI'), e.id from execution_entity e join workflow_entity w on w.id=e.\"workflowId\" where e.status in ('error','crashed') order by e.\"startedAt\" desc limit 5;"
echo "== Pipeline"
docker compose exec -T pipeline python -m pytest -q pipeline/tests 2>&1 | tail -1
