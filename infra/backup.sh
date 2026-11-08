#!/usr/bin/env bash
# Denní záloha: obě Postgres databáze (n8n, litellm), složka n8n (/home/node/.n8n – obsahuje
# klíče a nastavení), náhledy a .env. Uchovává 14 dní. Spouští cron (viz install.sh):
#   30 3 * * * /opt/web-outreach/infra/backup.sh >> /var/log/web-outreach-backup.log 2>&1
# Obnova: viz README_infra.md → „Obnova ze zálohy“.
set -euo pipefail
cd "$(dirname "$0")"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/web-outreach}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# .env se nesourcuje (hodnoty s mezerami / komentáři) – čteme jen to, co potřebujeme
PGUSER="$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2 | awk '{print $1}')"
PGUSER="${PGUSER:-outreach}"

echo "[$STAMP] záloha → $BACKUP_DIR"
docker compose exec -T postgres pg_dump -U "$PGUSER" -d n8n     | gzip > "$BACKUP_DIR/n8n-db-$STAMP.sql.gz"
docker compose exec -T postgres pg_dump -U "$PGUSER" -d litellm | gzip > "$BACKUP_DIR/litellm-db-$STAMP.sql.gz"

# n8n data volume (encryption key, nastavení, binární data) + náhledy
docker run --rm -v web-outreach_n8n_data:/src:ro -v "$BACKUP_DIR":/dst alpine \
  tar -czf "/dst/n8n-data-$STAMP.tar.gz" -C /src .
docker run --rm -v web-outreach_previews:/src:ro -v "$BACKUP_DIR":/dst alpine \
  tar -czf "/dst/previews-$STAMP.tar.gz" -C /src .

cp ./.env "$BACKUP_DIR/env-$STAMP.bak"
chmod 600 "$BACKUP_DIR"/env-*.bak

# úklid
find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" -delete
du -sh "$BACKUP_DIR"
echo "[$STAMP] hotovo"

# Volitelné: odeslání mimo server (odkomentuj a nastav rclone remote, např. Hetzner Storage Box / Backblaze):
# rclone sync "$BACKUP_DIR" storagebox:web-outreach-backups --max-age 15d
