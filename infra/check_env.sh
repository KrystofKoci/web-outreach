#!/usr/bin/env bash
# =====================================================================
#  check_env.sh – zkontroluje infra/.env: povinné hodnoty, formáty a (bez rizika) živé API.
#  Použití:  bash infra/check_env.sh            – vše včetně živých testů
#            bash infra/check_env.sh --offline  – jen formáty
#  Živé testy nic neposílají a nic nemění: Places (1 výsledek), Anthropic (seznam modelů),
#  LiteLLM a pipeline (health uvnitř Dockeru), WhatsApp (údaje o čísle + stav šablon), PageSpeed.
# =====================================================================
set -uo pipefail
cd "$(dirname "$0")"
[ -f .env ] || { echo "❌ infra/.env neexistuje – spusť: cp infra/.env.example infra/.env  (nebo install.sh)"; exit 1; }
DOCKER_OK=0
command -v docker >/dev/null 2>&1 && docker compose ps --status running 2>/dev/null | grep -q n8n && DOCKER_OK=1
export CHECK_OFFLINE="${1:-}" DOCKER_OK
exec python3 - <<'PY'
import json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request

def load_env(path=".env"):
    env = {}
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = re.sub(r"\s+#.*$", "", v).strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        env[k.strip()] = v
    return env

E = load_env()
OFFLINE = os.environ.get("CHECK_OFFLINE") == "--offline"
DOCKER = os.environ.get("DOCKER_OK") == "1"
fails = warns = 0

def ok(msg):
    print(f"✅ {msg}")

def bad(msg, fix):
    global fails
    fails += 1
    print(f"❌ {msg}\n   → {fix}")

def warn(msg, fix=""):
    global warns
    warns += 1
    print(f"⚠️  {msg}" + (f"\n   → {fix}" if fix else ""))

def fmt(name, pattern, fix, required=True):
    v = E.get(name, "")
    if not v:
        (bad if required else warn)(f"{name} není vyplněné", fix)
        return False
    if pattern and not re.fullmatch(pattern, v):
        bad(f"{name} má špatný formát", fix)
        return False
    ok(f"{name}")
    return True

def http(url, method="GET", headers=None, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}

def errmsg(j):
    e = j.get("error", j)
    if isinstance(e, dict):
        return str(e.get("message") or e.get("status") or e)[:200]
    return str(e)[:200]

print("── Povinné hodnoty a formáty ─────────────────────────────")
fmt("OWNER_EMAIL", r"[^@\s]+@[^@\s]+\.[a-z]{2,}", "tvůj osobní e-mail, např. jmeno@gmail.com")
fmt("OWNER_WHATSAPP", r"\+[1-9]\d{7,14}", "formát E.164 se znaménkem +, bez mezer: +420777123456")
fmt("OWNER_ICO", r"\d{8}", "IČO má 8 číslic (bez mezer)")
fmt("OWNER_ADDRESS", r".{10,}", "celá adresa sídla: ulice, PSČ, město, země")
fmt("GOOGLE_OAUTH_CLIENT_ID", r"[0-9]+-[a-z0-9]+\.apps\.googleusercontent\.com", "Google Cloud → Credentials → OAuth client ID (Web application), končí .apps.googleusercontent.com")
fmt("GOOGLE_OAUTH_CLIENT_SECRET", r"[A-Za-z0-9_-]{20,}", "Client secret ze stejného OAuth klienta (obvykle GOCSPX-…)")
fmt("PLACES_API_KEY", r"AIza[0-9A-Za-z_-]{35}", "Google Cloud → Credentials → API key (39 znaků, začíná AIza)")
fmt("ANTHROPIC_API_KEY", r"sk-ant-[A-Za-z0-9_-]{20,}", "console.anthropic.com → API Keys (začíná sk-ant-)")
fmt("WHATSAPP_TOKEN", r"[A-Za-z0-9]{100,}", "trvalý System User token z Meta Business Settings (dlouhý, začíná EAA)")
fmt("WHATSAPP_PHONE_NUMBER_ID", r"\d{10,20}", "Phone number ID z API Setup (jen číslice, NE telefonní číslo)")
fmt("WHATSAPP_BUSINESS_ACCOUNT_ID", r"\d{10,20}", "WhatsApp Business Account ID z API Setup (jen číslice)")

print("── Generovaná tajemství ──────────────────────────────────")
for k, n in [("API_TOKEN", 32), ("APPROVAL_SECRET", 32), ("UNSUB_SECRET", 32), ("N8N_ENCRYPTION_KEY", 32), ("LITELLM_MASTER_KEY", 20),
             ("POSTGRES_PASSWORD", 16), ("WHATSAPP_VERIFY_TOKEN", 16), ("MCP_TOKEN_READ", 32), ("MCP_TOKEN_ADMIN", 32)]:
    v = E.get(k, "")
    if not v:
        bad(f"{k} je prázdné", "spusť bash infra/install.sh – vygeneruje ho")
    elif len(v) < n:
        bad(f"{k} je příliš krátké ({len(v)} znaků)", f"min. {n} znaků; smaž hodnotu a spusť install.sh")
    else:
        ok(k)
if E.get("MCP_TOKEN_READ") and E.get("MCP_TOKEN_READ") == E.get("MCP_TOKEN_ADMIN"):
    bad("MCP_TOKEN_READ a MCP_TOKEN_ADMIN jsou stejné", "musí být různé – smaž jeden a spusť install.sh")

print("── Ostatní ───────────────────────────────────────────────")
if not E.get("SHEET_ID"):
    warn("SHEET_ID zatím chybí", "v n8n spusť workflow „00 Nastavení“ a pak bash infra/set_sheet_id.sh <ID>")
else:
    fmt("SHEET_ID", r"[A-Za-z0-9_-]{30,}", "ID z URL tabulky docs.google.com/spreadsheets/d/<ID>/edit")
if not E.get("WHATSAPP_APP_SECRET"):
    warn("WHATSAPP_APP_SECRET není vyplněný – podpis příchozích WhatsApp zpráv se neověřuje", "App Settings → Basic → App secret")
if "CR" not in [c.strip().upper() for c in E.get("BLOCKED_COUNTRIES", "CR").split(",")]:
    warn("BLOCKED_COUNTRIES neobsahuje CR", "Kostarika je blokovaná v kódu vždy, ale pro přehlednost ji tam nech")
tz = E.get("OWNER_TZ", "Europe/Prague")
if tz not in ("Europe/Prague", "America/Costa_Rica"):
    warn(f"OWNER_TZ={tz}", "obvykle Europe/Prague nebo America/Costa_Rica")
print(f"ℹ️  OUTREACH_ENABLED={E.get('OUTREACH_ENABLED', 'false')}  TEST_MODE={E.get('TEST_MODE', 'true')}  DAILY_CAP={E.get('DAILY_CAP', '30')}")

if OFFLINE:
    print("\n(--offline: živé testy přeskočeny)")
else:
    print("── Živé testy (nic neposílají) ───────────────────────────")
    if E.get("PLACES_API_KEY"):
        s, j = http("https://places.googleapis.com/v1/places:searchText", "POST",
                    {"X-Goog-Api-Key": E["PLACES_API_KEY"], "X-Goog-FieldMask": "places.id,places.displayName"},
                    {"textQuery": "plumber in Tulsa OK", "pageSize": 1})
        if s == 200 and j.get("places"):
            ok(f"Places API (New): nalezeno „{j['places'][0].get('displayName', {}).get('text', '?')}“")
        else:
            bad(f"Places API (New) HTTP {s}: {errmsg(j)}", "zapni Places API (New) v GCP, zkontroluj omezení klíče a billing účet")
    if E.get("ANTHROPIC_API_KEY"):
        s, j = http("https://api.anthropic.com/v1/models?limit=1", headers={"x-api-key": E["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
        if s == 200:
            ok("Anthropic API klíč platí")
        else:
            bad(f"Anthropic API HTTP {s}: {errmsg(j)}", "zkontroluj klíč a kredit na console.anthropic.com")
    if E.get("WHATSAPP_TOKEN") and E.get("WHATSAPP_PHONE_NUMBER_ID"):
        ver = E.get("WHATSAPP_GRAPH_VERSION", "v21.0")
        h = {"Authorization": "Bearer " + E["WHATSAPP_TOKEN"]}
        s, j = http(f"https://graph.facebook.com/{ver}/{E['WHATSAPP_PHONE_NUMBER_ID']}?fields=display_phone_number,verified_name,quality_rating", headers=h)
        if s == 200:
            ok(f"WhatsApp číslo {j.get('display_phone_number')} („{j.get('verified_name')}“, kvalita {j.get('quality_rating', '?')})")
        else:
            bad(f"WhatsApp Cloud API HTTP {s}: {errmsg(j)}", "token vypršel nebo nemá práva / špatné Phone number ID")
        if E.get("WHATSAPP_BUSINESS_ACCOUNT_ID"):
            s, j = http(f"https://graph.facebook.com/{ver}/{E['WHATSAPP_BUSINESS_ACCOUNT_ID']}/message_templates?fields=name,status,language&limit=100", headers=h)
            if s == 200:
                have = {(t.get("name"), t.get("language")): t.get("status") for t in j.get("data", [])}
                lang = E.get("WHATSAPP_TEMPLATE_LANG", "cs")
                for name in [E.get("WHATSAPP_TEMPLATE_BATCH", "batch_ready"), E.get("WHATSAPP_TEMPLATE_ESCALATION", "escalation"), E.get("WHATSAPP_TEMPLATE_REPORT", "weekly_report")]:
                    if not name:
                        continue
                    st = have.get((name, lang))
                    if st == "APPROVED":
                        ok(f"šablona {name} ({lang}) schválená")
                    elif st:
                        warn(f"šablona {name} ({lang}) ve stavu {st}", "počkej na schválení Metou (minuty až hodiny)")
                    else:
                        warn(f"šablona {name} ({lang}) neexistuje", "spusť bash infra/whatsapp_templates.sh")
            else:
                bad(f"WABA HTTP {s}: {errmsg(j)}", "špatné WHATSAPP_BUSINESS_ACCOUNT_ID nebo token bez whatsapp_business_management")
    if E.get("PAGESPEED_API_KEY"):
        q = urllib.parse.urlencode({"url": "https://example.com", "strategy": "mobile", "category": "performance", "key": E["PAGESPEED_API_KEY"]})
        s, j = http("https://www.googleapis.com/pagespeedonline/v5/runPagespeed?" + q, timeout=90)
        if s == 200:
            ok("PageSpeed Insights API")
        else:
            bad(f"PageSpeed HTTP {s}: {errmsg(j)}", "zapni PageSpeed Insights API v GCP nebo nech PAGESPEED_API_KEY prázdné")
    else:
        warn("PAGESPEED_API_KEY prázdný – audit rychlosti se přeskočí (volitelné)")
    if DOCKER:
        def inside(cmd):
            r = subprocess.run(["docker", "compose", "exec", "-T", "n8n", "sh", "-c", cmd], capture_output=True, text=True, timeout=30)
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        good, out = inside("wget -qO- http://litellm:4000/health/liveliness")
        ok("LiteLLM brána běží") if good else bad(f"LiteLLM neodpovídá: {out[:150]}", "docker compose logs litellm")
        good, out = inside("wget -qO- http://pipeline:8077/health")
        ok("pipeline API běží") if good else bad(f"pipeline neodpovídá: {out[:150]}", "docker compose logs pipeline")
    else:
        warn("Docker kontejnery neběží – test LiteLLM a pipeline přeskočen", "po install.sh spusť check_env.sh znovu")

print("──────────────────────────────────────────────────────────")
if fails:
    print(f"❌ {fails} chyb, {warns} upozornění – oprav infra/.env a spusť znovu.")
    sys.exit(1)
print(f"✅ Vše v pořádku ({warns} upozornění).")
PY
