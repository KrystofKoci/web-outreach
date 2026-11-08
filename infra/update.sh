#!/usr/bin/env bash
# Aktualizace: stáhne nový kód (git pull), nové obrazy, přebuilduje pipeline, restartuje jen to, co se změnilo.
# Před aktualizací udělá zálohu. Spouštěj jako uživatel deploy:  /opt/web-outreach/infra/update.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "==> záloha před aktualizací"
./backup.sh

echo "==> git pull"
git -C .. pull --ff-only

echo "==> obrazy"
docker compose pull --ignore-buildable
docker compose build pipeline

echo "==> restart změněných služeb"
docker compose up -d --remove-orphans

echo "==> úklid starých obrazů"
docker image prune -f

docker compose ps
echo "Hotovo. Po aktualizaci n8n zkontroluj v editoru, že workflowy jsou aktivní a bez varování u uzlů."
