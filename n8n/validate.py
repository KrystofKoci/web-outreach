#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kontrola n8n workflow JSONů před importem (bez sítě, bez n8n).

Spuštění:  python3 n8n/validate.py            (zkontroluje všechny n8n/*.json)
           python3 n8n/validate.py n8n/04_outreach_sequence.json

Co kontroluje:
  1. soubor je platný JSON s klíči name / nodes / connections / settings,
  2. názvy uzlů jsou unikátní, každý uzel má type, typeVersion, position, parameters,
  3. všechny spoje (connections) ukazují na existující uzly (zdroj i cíl),
  4. JavaScript v Code uzlech (jsCode) a Code Tool uzlech projde `node --check`
     (zabalí se do async funkce, n8n globály $input/$env/DateTime… jsou deklarované jako prázdné),
  5. v n8n/, infra/, emails/, sheets/ se nesmí vyskytnout zakázané kanály (telegram, cal.com, booking) –
     systém komunikuje jen e-mailem a WhatsAppem, bez schůzek (jinak CHYBA),
  6. varování: uzel bez připojení (kromě triggerů a poznámek), chybějící credentials u uzlů, které je potřebují,
     zapomenuté `=` u výrazů, podezřelé typeVersion.
Výstup: souhrn + návratový kód 0 (OK) / 1 (chyba).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FORBIDDEN = re.compile(r"telegram|cal\.com|calcom|booking", re.IGNORECASE)
FORBIDDEN_DIRS = ("n8n", "infra", "emails", "sheets")

TRIGGER_TYPES = {
    "n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.telegramTrigger", "n8n-nodes-base.gmailTrigger",
    "n8n-nodes-base.webhook", "n8n-nodes-base.errorTrigger", "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.executeWorkflowTrigger", "@n8n/n8n-nodes-langchain.mcpTrigger",
}
SUB_NODE_TYPES_PREFIX = ("@n8n/n8n-nodes-langchain.lmChat", "@n8n/n8n-nodes-langchain.tool",
                         "@n8n/n8n-nodes-langchain.outputParser", "@n8n/n8n-nodes-langchain.mcpClientTool")
NEEDS_CREDENTIALS = {
    "n8n-nodes-base.googleSheets": "googleSheetsOAuth2Api",
    "n8n-nodes-base.googleSheetsTool": "googleSheetsOAuth2Api",
    "n8n-nodes-base.gmail": "gmailOAuth2",
    "n8n-nodes-base.gmailTrigger": "gmailOAuth2",
    "n8n-nodes-base.telegram": "telegramApi",
    "n8n-nodes-base.telegramTool": "telegramApi",
    "n8n-nodes-base.telegramTrigger": "telegramApi",
    "@n8n/n8n-nodes-langchain.lmChatOpenAi": "openAiApi",
    "@n8n/n8n-nodes-langchain.lmChatAnthropic": "anthropicApi",
}
EXPECTED_VERSIONS = {
    "n8n-nodes-base.scheduleTrigger": {1.2}, "n8n-nodes-base.httpRequest": {4.2}, "n8n-nodes-base.httpRequestTool": {4.2},
    "n8n-nodes-base.googleSheets": {4.5}, "n8n-nodes-base.googleSheetsTool": {4.5}, "n8n-nodes-base.telegram": {1.2},
    "n8n-nodes-base.telegramTool": {1.2}, "n8n-nodes-base.telegramTrigger": {1.1, 1.2}, "n8n-nodes-base.gmail": {2.1},
    "n8n-nodes-base.gmailTrigger": {1.2}, "n8n-nodes-base.wait": {1.1}, "n8n-nodes-base.if": {2.2},
    "n8n-nodes-base.switch": {3.2}, "n8n-nodes-base.code": {2}, "n8n-nodes-base.set": {3.4}, "n8n-nodes-base.webhook": {2},
    "n8n-nodes-base.respondToWebhook": {1.1}, "n8n-nodes-base.splitInBatches": {3}, "n8n-nodes-base.stickyNote": {1},
    "n8n-nodes-base.aggregate": {1}, "n8n-nodes-base.manualTrigger": {1}, "n8n-nodes-base.noOp": {1}, "n8n-nodes-base.errorTrigger": {1},
}

# n8n globály, které v Code uzlech existují – pro `node --check` je stačí deklarovat
N8N_GLOBALS = ["$input", "$json", "$env", "$now", "$today", "$workflow", "$execution", "$prevNode", "$runIndex",
               "$itemIndex", "$vars", "$binary", "DateTime", "Interval", "Duration", "$jmespath", "$fromAI", "$getWorkflowStaticData",
               "query", "$helpers"]


def node_bin():
    return shutil.which("node")


def check_js(code: str, label: str, errors: list, warnings: list):
    nb = node_bin()
    if not nb:
        warnings.append(f"{label}: node není k dispozici – JS nezkontrolován")
        return
    # $('Název') – funkce; deklarujeme jako const $ = () => ({})
    wrapped = ("'use strict';\n" + "const " + ", ".join(f"{g} = undefined" for g in N8N_GLOBALS) +
               ";\nconst $ = (n) => ({});\nasync function __n8n_code() {\n" + code + "\n}\n")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(wrapped)
        path = f.name
    try:
        r = subprocess.run([nb, "--check", path], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            msg = (r.stderr or r.stdout).strip().splitlines()
            # posunutí čísla řádku o hlavičku (3 řádky)
            errors.append(f"{label}: syntaktická chyba JS → " + " | ".join(msg[:6]))
    finally:
        os.unlink(path)


def validate_file(path: Path):
    errors, warnings = [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [f"neplatný JSON: {e}"], warnings, {}
    for key in ("name", "nodes", "connections", "settings"):
        if key not in data:
            errors.append(f"chybí klíč '{key}'")
    nodes = data.get("nodes", [])
    names = {}
    stats = {"nodes": 0, "code": 0, "sticky": 0, "connections": 0, "js_checked": 0}
    for n in nodes:
        stats["nodes"] += 1
        name = n.get("name")
        if not name:
            errors.append("uzel bez názvu")
            continue
        if name in names:
            errors.append(f"duplicitní název uzlu '{name}'")
        names[name] = n
        for key in ("type", "typeVersion", "position", "parameters"):
            if key not in n:
                errors.append(f"uzel '{name}': chybí '{key}'")
        if "id" not in n:
            warnings.append(f"uzel '{name}': chybí id (n8n doplní)")
        t = n.get("type", "")
        tv = n.get("typeVersion")
        if t in EXPECTED_VERSIONS and tv not in EXPECTED_VERSIONS[t]:
            warnings.append(f"uzel '{name}': typeVersion {tv} pro {t} (očekáváno {sorted(EXPECTED_VERSIONS[t])})")
        if t == "n8n-nodes-base.stickyNote":
            stats["sticky"] += 1
        cred_type = NEEDS_CREDENTIALS.get(t)
        if cred_type and cred_type not in (n.get("credentials") or {}):
            warnings.append(f"uzel '{name}': chybí credentials '{cred_type}' (doplnit po importu)")
        params = n.get("parameters", {})
        js = None
        if t == "n8n-nodes-base.code":
            stats["code"] += 1
            js = params.get("jsCode")
            if not js:
                errors.append(f"uzel '{name}': Code bez jsCode")
        elif t == "@n8n/n8n-nodes-langchain.toolCode":
            js = params.get("jsCode")
        if js:
            stats["js_checked"] += 1
            check_js(js, f"{path.name} › '{name}'", errors, warnings)
        # zapomenuté '=' u výrazů v řetězcových parametrech
        def walk(v, p):
            if isinstance(v, str):
                if "{{" in v and not v.startswith("=") and not p.endswith(".jsCode") and not p.endswith(".content") \
                        and "AGENT_SYSTEM_PROMPT" not in p and not p.endswith(".toolDescription") and not p.endswith(".description") \
                        and not p.endswith(".inputSchema") and not p.endswith(".text") and "assignments" not in p:
                    warnings.append(f"uzel '{name}': parametr {p} obsahuje {{{{ }}}} bez úvodního '=' (nebude vyhodnocen)")
            elif isinstance(v, dict):
                for k, x in v.items():
                    walk(x, f"{p}.{k}")
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{p}[{i}]")
        walk(params, "parameters")

    conns = data.get("connections", {})
    connected = set()
    for src, by_type in conns.items():
        if src not in names:
            errors.append(f"spoj ze zdroje, který neexistuje: '{src}'")
        for ctype, outputs in by_type.items():
            for out_idx, targets in enumerate(outputs):
                for tgt in targets or []:
                    stats["connections"] += 1
                    dst = tgt.get("node")
                    if dst not in names:
                        errors.append(f"spoj '{src}' → neexistující uzel '{dst}'")
                    else:
                        connected.add(dst)
                    if tgt.get("type") != ctype:
                        warnings.append(f"spoj '{src}' → '{dst}': typ spoje {tgt.get('type')} ≠ {ctype}")
                    connected.add(src)
    for name, n in names.items():
        t = n.get("type", "")
        if t == "n8n-nodes-base.stickyNote":
            continue
        if name not in connected:
            if t in TRIGGER_TYPES or t.startswith(SUB_NODE_TYPES_PREFIX):
                # trigger musí mít aspoň výstup (pokud to není záměrně odpojený záložní uzel)
                if t in TRIGGER_TYPES and name not in conns:
                    warnings.append(f"trigger '{name}' nemá žádný výstupní spoj")
                elif t.startswith(SUB_NODE_TYPES_PREFIX) and name not in conns:
                    warnings.append(f"AI pod-uzel '{name}' není připojen (záměrně záložní?)")
            else:
                warnings.append(f"uzel '{name}' není nikam připojen")
    return errors, warnings, stats


def scan_forbidden():
    """Najde zakázaná slova ve všech textových souborech mých složek (kromě tohoto skriptu)."""
    hits = []
    for d in FORBIDDEN_DIRS:
        base = REPO / d
        if not base.exists():
            continue
        for f in sorted(base.rglob("*")):
            if not f.is_file() or f.resolve() == Path(__file__).resolve() or f.suffix in (".png", ".jpg", ".pyc"):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                m = FORBIDDEN.search(line)
                if m:
                    hits.append(f"{f.relative_to(REPO)}:{i}: zakázané slovo '{m.group(0)}'")
    return hits


def main(argv):
    files = [Path(a) for a in argv[1:]] or sorted(HERE.glob("*.json"))
    total_err = 0
    print(f"Kontrola {len(files)} souborů (node: {node_bin() or 'nenalezen'})\n")
    for f in files:
        errors, warnings, stats = validate_file(f)
        status = "OK " if not errors else "CHYBA"
        print(f"[{status}] {f.name}: uzlů {stats.get('nodes', 0)} (Code {stats.get('code', 0)}, poznámek {stats.get('sticky', 0)}), "
              f"spojů {stats.get('connections', 0)}, JS zkontrolováno {stats.get('js_checked', 0)}")
        for e in errors:
            print(f"    ✗ {e}")
        for w in warnings:
            print(f"    ⚠ {w}")
        total_err += len(errors)
    hits = scan_forbidden()
    print(f"\n[{'OK ' if not hits else 'CHYBA'}] zakázané kanály (telegram / cal.com / booking) v {', '.join(FORBIDDEN_DIRS)}: {len(hits)} nálezů")
    for h in hits[:50]:
        print(f"    ✗ {h}")
    total_err += len(hits)
    print(f"\nCelkem chyb: {total_err}")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
