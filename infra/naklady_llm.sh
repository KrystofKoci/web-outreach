#!/usr/bin/env bash
# Útrata za LLM z logu LiteLLM (Postgres, db litellm, tabulka LiteLLM_SpendLogs). Spouštět na VPS:
#   bash /opt/web-outreach/infra/naklady_llm.sh          # posledních 30 dní
#   bash /opt/web-outreach/infra/naklady_llm.sh 7        # posledních 7 dní
set -euo pipefail
cd /opt/web-outreach/infra
DAYS=${1:-30}
U=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2); U=${U:-outreach}
Q() { docker compose exec -T postgres psql -U "$U" -d litellm -c "$1"; }
echo "== Logování zapnuto? (počet záznamů za $DAYS dní)"
Q "SELECT count(*) AS pozadavku, round(sum(spend)::numeric,3) AS usd, sum(prompt_tokens) AS vstup_tok, sum(completion_tokens) AS vystup_tok FROM \"LiteLLM_SpendLogs\" WHERE \"startTime\" > now() - interval '$DAYS days';"
echo "== Podle modelu/aliasu"
Q "SELECT model, model_group AS alias, count(*) AS pozadavku, round(sum(spend)::numeric,3) AS usd, round(avg(prompt_tokens)) AS prum_vstup, round(avg(completion_tokens)) AS prum_vystup FROM \"LiteLLM_SpendLogs\" WHERE \"startTime\" > now() - interval '$DAYS days' GROUP BY 1,2 ORDER BY usd DESC;"
echo "== Po dnech"
Q "SELECT date(\"startTime\") AS den, count(*) AS pozadavku, round(sum(spend)::numeric,3) AS usd FROM \"LiteLLM_SpendLogs\" WHERE \"startTime\" > now() - interval '$DAYS days' GROUP BY 1 ORDER BY 1 DESC LIMIT 31;"
echo "== Strop (max_budget) a útrata klíčů"
Q "SELECT key_alias, round(spend::numeric,3) AS usd, max_budget FROM \"LiteLLM_VerificationToken\" ORDER BY spend DESC LIMIT 10;" || true
echo
echo "Tip: 0 záznamů = LiteLLM nezapisuje do DB -> zkontroluj 'docker compose logs litellm | grep -i prisma' (DATABASE_URL, migrace)."
