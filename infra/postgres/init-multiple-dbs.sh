#!/bin/bash
# Vytvoří další databáze vyjmenované v POSTGRES_MULTIPLE_DATABASES (oddělené čárkou).
# Spouští se jen při prvním startu s prázdným volume (standardní chování postgres image).
set -euo pipefail

if [ -n "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
  IFS=',' read -ra DBS <<< "$POSTGRES_MULTIPLE_DATABASES"
  for db in "${DBS[@]}"; do
    db="$(echo "$db" | xargs)"
    [ -z "$db" ] && continue
    echo "init: vytvářím databázi '$db' pro uživatele '$POSTGRES_USER'"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
      SELECT 'CREATE DATABASE "$db" OWNER "$POSTGRES_USER"'
      WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
  done
fi
