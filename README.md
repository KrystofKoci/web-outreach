# web-outreach – „nový web jako první kontakt“

Automatizovaný systém pro Kryštofa Kočího: najde místní firmy se zastaralým nebo žádným webem (celý svět, **kromě Kostariky**), vygeneruje jim jednostránkový náhled nového webu, ty ho **schválíš jedním klepnutím přes odkaz z WhatsAppu / e-mailu** (dávky 8:00 / 11:00 / 14:00), systém pošle osobní e-mail + 2 připomenutí, odpoví na dotazy v mantinelech ceníku (floor **350 USD / 8 000 Kč**) – **vše jen písemně, e-mailem, případně WhatsAppem, žádné schůzky ani hovory** – a učí se z uzavřených zakázek, kam mířit dál.

```
          queue + weights           Google Places            audit + šablony + Claude
  n8n 01 ───────────────► pipeline /search ──► n8n 02 ──► pipeline /process ──► nahled.krystofkoci.com/<firma>/
                                                               │
      WhatsApp + e-mail: odkaz na schvalovací stránku ◄── n8n 03 ◄─┘ compare.png
                              │ ✅
  Gmail (1 + 2 připomenutí) ◄── n8n 04 ──► CRM (Google Sheets)
  odpověď klienta (e-mail, nebo WhatsApp když napíše první) ──► n8n 05 inbox agent (LiteLLM → Claude) ──► písemná odpověď / eskalace tobě (WhatsApp + e-mail)
  neděle: /learn → weights · pondělí: report e-mailem
  MCP: outreach-read (AI_COM, kontrola) · outreach-admin (ty)
```

## Struktura

| Složka | Obsah |
|---|---|
| `docs/` | **začni `00_SPUSTENI_KROK_ZA_KROKEM.md`**; analýza nápadu, právní checklist, ceník a mantinely agenta, zadání tvého webu (Webild), kde začít |
| `pipeline/` | Python: hledání firem, audit webu, generátor webu (6 oborových šablon), screenshoty, učení (`learn.py`), HTTP API pro n8n, CLI |
| `n8n/` | 8 workflowů k importu + README (credentials, env, testy, MCP, LiteLLM) + `validate.py` |
| `infra/` | Docker Compose (n8n, Postgres, LiteLLM, pipeline, Caddy), `install.sh` pro Hetzner, zálohy, `.env.example`, README |
| `emails/` | texty e-mailů CZ/EN (3 kroky, předměty A/B/C), právní patičky podle země |
| `sheets/` | šablony listů CRM (`leads`, `queue`, `deals`, `weights`, `blocklist`) a popis stavů |

## Zásady, které kód vynucuje

- Nic se neodešle bez tvého schválení (každý lead zvlášť nebo celá dávka).
- Kostarika a `BLOCKED_COUNTRIES` se nikdy nezpracují.
- Agent nikdy nejde pod floor, neslibuje termíny ani záruky, po 2 odpovědích eskaluje; jakmile odpovíš ručně, mlčí.
- Náhledy: jen veřejná fakta, žádné ceny, žádné cizí fotky, `noindex`, smazání po 60 dnech.
- Každý e-mail má identifikaci, odhlášení a patičku podle právního režimu země.
- Všechna volání modelů jdou přes LiteLLM (rozpočet, log, fallback).

## Rychlý start

Viz `docs/00_SPUSTENI_KROK_ZA_KROKEM.md` (4 dny, ~6–8 h tvé práce). Lokálně bez serveru si můžeš vyzkoušet generátor:

```bash
cd web-outreach
pip install -r pipeline/requirements.txt && playwright install chromium
python -m pipeline.cli demo --out ./demo-out      # 12 demo webů (6 oborů × cs/en)
python -m unittest discover -s pipeline/tests -t .
```

## Licence a původ

Vlastní kód (MIT). Inspirace: šablony n8n (#13753, #6026, #20363, #15911), Zie619/n8n-workflows, poznámky ze složky Instagram-napady (albert.olgaard, valeridoesai, idanbuild). Žádný cizí kód se nepřebírá beze čtení.
