#!/usr/bin/env bash
# Every 30 minutes (cron): fetch published references from n8n, photograph new client websites, write /reference/data.json for the website.
set -uo pipefail
SITE="$1"; HERE="$(cd "$(dirname "$0")" && pwd)"
exec 9>"$HERE/.lock"; flock -n 9 || exit 0   # never two runs at once
REF="$SITE/reference"; MEDIA="$REF/media"; mkdir -p "$MEDIA"
PW_IMG="mcr.microsoft.com/playwright:v1.49.1-noble"; FF_IMG="linuxserver/ffmpeg:latest"
curl -fsS --max-time 30 "https://n8n.krystofkoci.com/webhook/reference-verejne" -o "$HERE/refs.json" || exit 0
grep -q '"reference"' "$HERE/refs.json" || exit 0
cp "$HERE/capture.js" "$HERE/work/" 2>/dev/null || { mkdir -p "$HERE/work"; cp "$HERE/capture.js" "$HERE/work/"; }
cp "$HERE/refs.json" "$HERE/work/refs.json"
# photograph the websites that have no picture yet (Playwright package is installed once into work/node_modules)
docker run --rm --ipc=host -v "$HERE/work:/work" -v "$MEDIA:/media" -w /work "$PW_IMG" bash -c \
  "[ -d node_modules/playwright ] || npm i --no-save --silent playwright@1.49.1 >/dev/null 2>&1; node capture.js refs.json /media" || true
# short MP4 of the hero (skips the first 1.5 s of loading), plays everywhere incl. Safari
for raw in "$MEDIA"/*.webm; do
  [ -e "$raw" ] || continue; mp4="${raw%.webm}.mp4"
  [ -e "$mp4" ] || docker run --rm -v "$MEDIA:/m" "$FF_IMG" -loglevel error -y -ss 1.5 -i "/m/$(basename "$raw")" -t 5 -vf "scale=960:-2" -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p -movflags +faststart -an "/m/$(basename "$mp4")" || true
  [ -s "$mp4" ] && rm -f "$raw"
done
# data for the website: only published references that have a picture
python3 - "$HERE/refs.json" "$MEDIA" "$REF/data.json" <<'PY'
import json, os, sys
refs = json.load(open(sys.argv[1], encoding="utf-8")).get("reference", [])
media, out = sys.argv[2], []
for r in refs:
    if os.path.exists(os.path.join(media, r["id"] + ".jpg")):
        r["img"] = "/reference/media/%s.jpg" % r["id"]
        r["video"] = "/reference/media/%s.mp4" % r["id"] if os.path.exists(os.path.join(media, r["id"] + ".mp4")) else ""
        out.append(r)
tmp = sys.argv[3] + ".tmp"
json.dump({"reference": out}, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
os.replace(tmp, sys.argv[3])
PY
chmod -R a+rX "$REF"
