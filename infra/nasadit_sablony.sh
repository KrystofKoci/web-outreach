#!/usr/bin/env bash
# Nasazení balíčku „šablony 2" (premium šablony webů do pipeline).
#
# Použití (na serveru jako root nebo deploy):
#   bash /opt/web-outreach/infra/nasadit_sablony.sh /opt/web-outreach-sablony-2.tgz            # testovací režim
#   bash /opt/web-outreach/infra/nasadit_sablony.sh /opt/web-outreach-sablony-2.tgz --ostre    # ostrý provoz
#   bash /opt/web-outreach/infra/nasadit_sablony.sh --ostre                                    # jen přepnout na ostro
#
# Co dělá:
#   1) záloha (infra/backup.sh)
#   2) rozbalí balíček do /opt/web-outreach – .env ani žádný infra/.env* nikdy nepřepíše
#   3) v infra/.env nastaví jen tyto klíče: TEST_MODE, PREMIUM_TEMPLATES (+ DAILY_CAP při --ostre)
#   4) přebuilduje a restartuje pipeline, n8n přenačte proměnné (up -d)
#   5) workflowy n8n naimportuje jen tehdy, když balíček obsahuje změněné n8n/*.json
#   6) ověří, že n8n běží v TEST_MODE (resp. v ostrém režimu), a spustí pytest v kontejneru pipeline
set -euo pipefail

ROOT="${ROOT:-/opt/web-outreach}"
INFRA="$ROOT/infra"
ENVF="$INFRA/.env"
PKG=""
OSTRE=0
for a in "$@"; do
  case "$a" in
    --ostre) OSTRE=1 ;;
    -h|--help) sed -n 2,16p "$0"; exit 0 ;;
    *) PKG="$a" ;;
  esac
done

[ -f "$ENVF" ] || { echo "!! $ENVF neexistuje – je ROOT správně? ($ROOT)"; exit 1; }
cd "$INFRA"

# nastaví KEY=VALUE v .env (jen daný klíč, ostatní řádky beze změny, hodnoty se nevypisují kromě tohoto klíče)
setenv() {
  local k="$1" v="$2"
  if grep -qE "^${k}=" "$ENVF"; then
    sed -i -E "s|^${k}=.*|${k}=${v}|" "$ENVF"
  else
    printf '\n%s=%s\n' "$k" "$v" >> "$ENVF"
  fi
  echo "   .env: $k=$v"
}

echo "==> 1) záloha"
./backup.sh

CHANGED_WF=()
if [ -n "$PKG" ]; then
  [ -f "$PKG" ] || { echo "!! balíček $PKG nenalezen"; exit 1; }
  echo "==> 2) rozbalení $PKG (bez .env)"
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  tar -xzf "$PKG" -C "$TMP" --exclude='.env' --exclude='*/.env' --exclude='infra/.env*' --exclude='.n8n_google_creds'
  # workflowy: zjistit, které se liší (import jen změněných)
  if [ -d "$TMP/n8n" ]; then
    for f in "$TMP"/n8n/*.json; do
      [ -e "$f" ] || continue
      b="$(basename "$f")"
      if ! cmp -s "$f" "$ROOT/n8n/$b" 2>/dev/null; then CHANGED_WF+=("$b"); fi
    done
  fi
  # pipeline: staré premium šablony/soubory pryč, ať nezůstanou osiřelé
  rm -rf "$ROOT/pipeline/templates/premium" "$ROOT/pipeline/premium_assets"
  # kopie bez přepisu .env (cp -a zachová práva; .env v balíčku není)
  (cd "$TMP" && find . -type f ! -name '.env' ! -path './infra/.env*' -print0 | while IFS= read -r -d '' x; do
      mkdir -p "$ROOT/$(dirname "$x")"; cp -a "$x" "$ROOT/$x"; done)
  chmod +x "$INFRA"/*.sh 2>/dev/null || true
  echo "   rozbaleno: $(cd "$TMP" && find . -type f | wc -l) souborů"
fi

echo "==> 3) .env"
setenv PREMIUM_TEMPLATES true
if [ "$OSTRE" = 1 ]; then
  setenv TEST_MODE false
  setenv DAILY_CAP 15
else
  setenv TEST_MODE true
fi

echo "==> 4) build + restart pipeline, n8n přenačte .env"
docker compose build pipeline
docker compose up -d pipeline n8n

if [ "${#CHANGED_WF[@]}" -gt 0 ]; then
  echo "==> 5) import změněných workflowů: ${CHANGED_WF[*]}"
  for b in "${CHANGED_WF[@]}"; do
    docker compose exec -T n8n n8n import:workflow --input="/workflows/$b"
  done
  echo "   po importu zkontroluj v editoru credentials a aktivaci (infra/activate.sh)"
else
  echo "==> 5) workflowy beze změny – import přeskočen"
fi

echo "==> 6) kontrola"
for i in $(seq 1 30); do
  st="$(docker compose ps --format '{{.Health}}' pipeline 2>/dev/null || true)"
  [ "$st" = "healthy" ] && break; sleep 4
done
echo "   pipeline: ${st:-?}"
TM="$(docker compose exec -T n8n printenv TEST_MODE || true)"
PT="$(docker compose exec -T pipeline printenv PREMIUM_TEMPLATES || true)"
echo "   n8n TEST_MODE=$TM   pipeline PREMIUM_TEMPLATES=$PT"
if [ "$OSTRE" = 1 ]; then
  [ "$TM" = "false" ] || { echo "!! n8n neběží v ostrém režimu"; exit 1; }
else
  [ "$TM" = "true" ] || { echo "!! n8n NEBĚŽÍ v TEST_MODE – zastav se a zkontroluj infra/.env"; exit 1; }
fi
docker compose exec -T pipeline python -c "from pipeline import premium as p; ids=sorted({t for v in p.TEMPLATES_BY_NICHE.values() for t in (v if isinstance(v,(list,tuple)) else [v])}); miss=[i+'.'+l for i in ids for l in ('cs','en') if not p.available(i,l)]; print('   šablon:', len(ids), '| chybí:', miss or 'nic')"
docker compose exec -T pipeline python -c "import os; from pathlib import Path; from pipeline import premium as p; print('   assety nainstalovány:', len(p.install_assets(Path(os.environ.get('PREVIEW_DIR','/srv/nahled')))), 'souborů nových/změněných')"
docker compose exec -T pipeline sh -c "pip install -q pytest >/dev/null 2>&1; cd /app && python -m pytest -q pipeline/tests" \
  || { echo "!! pytest v kontejneru selhal"; exit 1; }

echo
if [ "$OSTRE" = 1 ]; then
  echo "Hotovo – OSTRÝ režim (DAILY_CAP=15)."
else
  echo "Hotovo – TESTOVACÍ režim. Pusť testovací dávku a zkontroluj náhledy; na ostro: $0 --ostre"
fi
