#!/usr/bin/env bash
# Daily ECB exchange rates for the price section (USD -> CZK, EUR), saved as <site>/rates.json
SITE="$1"; TMP="$SITE/.rates.tmp"
for U in "https://api.frankfurter.dev/v1/latest?base=USD&symbols=CZK,EUR" "https://api.frankfurter.app/latest?from=USD&to=CZK,EUR"; do
  if curl -fsS --max-time 20 "$U" -o "$TMP" && grep -q '"CZK"' "$TMP"; then chmod a+r "$TMP"; mv "$TMP" "$SITE/rates.json"; exit 0; fi
done
rm -f "$TMP"; exit 1
