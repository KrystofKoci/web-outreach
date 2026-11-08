#!/usr/bin/env bash
# =====================================================================
#  whatsapp_templates.sh – vytvoří šablony WhatsApp (kategorie UTILITY, cs + en) přes Graph API:
#     batch_ready   {{1}} počet návrhů, {{2}} odkaz na schvalovací stránku
#     escalation    {{1}} kdo/co, {{2}} důvod
#     weekly_report {{1}} krátké shrnutí
#  POST /{WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates. Pak jen počkej na schválení Metou
#  (minuty až hodiny); stav ukáže tento skript i check_env.sh. Existující šablony přeskočí.
#  Použití: bash infra/whatsapp_templates.sh
# =====================================================================
set -uo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "❌ infra/.env neexistuje"; exit 1; }
exec python3 - <<'PY'
import json, re, sys, time, urllib.error, urllib.request

E = {}
for line in open(".env", encoding="utf-8"):
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.rstrip("\n").split("=", 1)
        E[k.strip()] = re.sub(r"\s+#.*$", "", v).strip().strip('"')
tok, waba, ver = E.get("WHATSAPP_TOKEN"), E.get("WHATSAPP_BUSINESS_ACCOUNT_ID"), E.get("WHATSAPP_GRAPH_VERSION", "v21.0")
if not tok or not waba:
    sys.exit("❌ V .env chybí WHATSAPP_TOKEN nebo WHATSAPP_BUSINESS_ACCOUNT_ID.")
host = E.get("N8N_HOST", "n8n.krystofkoci.com")
url_example = f"https://{host}/webhook/approve?batch=d20261026-0800&t=1793015212.4d270199344ff34b55a2106b0029ba55"

TEMPLATES = {
    E.get("WHATSAPP_TEMPLATE_BATCH", "batch_ready") or "batch_ready": {
        "cs": ("Nová dávka ke schválení: {{1}} návrhů webů. Schvalovací stránka: {{2}} (odkaz platí 24 hodin).", ["10", url_example]),
        "en": ("New batch ready for approval: {{1}} website drafts. Approval page: {{2}} (link valid for 24 hours).", ["10", url_example]),
    },
    E.get("WHATSAPP_TEMPLATE_ESCALATION", "escalation") or "escalation": {
        "cs": ("Je potřeba vaše odpověď: {{1}}. Důvod: {{2}}. Podrobnosti a návrh odpovědi jsou v e-mailu.", ["Instalatérství Novák", "klient chce objednat"]),
        "en": ("Your reply is needed: {{1}}. Reason: {{2}}. Details and a draft reply are in your e-mail.", ["Novak Plumbing", "the client wants to order"]),
    },
}
rep = E.get("WHATSAPP_TEMPLATE_REPORT", "weekly_report")
if rep:
    TEMPLATES[rep] = {
        "cs": ("Týdenní přehled outreach je v e-mailu: {{1}}.", ["12 nových, 30 odesláno, 4 odpovědi, 1 zakázka"]),
        "en": ("Your weekly outreach summary is in your e-mail: {{1}}.", ["12 new, 30 sent, 4 replies, 1 deal"]),
    }

def call(method, path, body=None):
    req = urllib.request.Request(f"https://graph.facebook.com/{ver}/{path}", method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}

s, j = call("GET", f"{waba}/message_templates?fields=name,language,status&limit=200")
if s != 200:
    sys.exit(f"❌ Nelze načíst šablony (HTTP {s}): {j.get('error', {}).get('message', j)}\n   → zkontroluj token (whatsapp_business_management) a WHATSAPP_BUSINESS_ACCOUNT_ID")
existing = {(t["name"], t["language"]): t["status"] for t in j.get("data", [])}
errors = 0
for name, langs in TEMPLATES.items():
    for lang, (text, example) in langs.items():
        if (name, lang) in existing:
            print(f"⏭  {name} ({lang}) už existuje – stav {existing[(name, lang)]}")
            continue
        body = {"name": name, "language": lang, "category": "UTILITY",
                "components": [{"type": "BODY", "text": text, "example": {"body_text": [example]}}]}
        s, r = call("POST", f"{waba}/message_templates", body)
        if s == 200:
            print(f"✅ {name} ({lang}) odeslána ke schválení – stav {r.get('status', 'PENDING')}, kategorie {r.get('category', 'UTILITY')}")
        else:
            errors += 1
            print(f"❌ {name} ({lang}) HTTP {s}: {r.get('error', {}).get('error_user_msg') or r.get('error', {}).get('message', r)}")
        time.sleep(1)
print("\nStav schválení zkontroluješ: bash infra/check_env.sh (nebo WhatsApp Manager → Message templates).")
print("Pozn.: Meta může šablonu s odkazem přeřadit do jiné kategorie – zkontroluj, že zůstala UTILITY.")
sys.exit(1 if errors else 0)
PY
