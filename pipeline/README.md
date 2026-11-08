# pipeline – Python část systému „nový web jako první kontakt“

Balíček `pipeline/` dělá všechno od vyhledání firmy po hotový náhled webu a obrázek
„dnes vs. nový návrh“. Schvalování, e-maily a odpovědi řeší n8n (`n8n/`), které
s tímto balíčkem mluví přes HTTP API (`pipeline.api`) nebo CLI (`pipeline.cli`).

```
Google Places ──► audit webu ──► větev (no_website / redesign / skip)
                                     │
                                     ▼
          texty (LLM / šablona) ──► náhled HTML ──► screenshoty ──► publikace
```

Trhy: `cz` (čeština) a `en` (US, GB, IE, CA, AU, NZ …). **Firmy z Kostariky (CR)
se nikdy nezpracují** – blokace je napevno v kódu a nejde vypnout proměnnou.

---

## Moduly

| Soubor | Co dělá |
|---|---|
| `config.py` | Načte nastavení z prostředí (`get_settings()`), blokované země, výchozí trh. Žádný klíč není v kódu. |
| `countries.py` | Země → jazyk, trh, měna, časová zóna (včetně států USA, provincií Kanady, států Austrálie), **právní režim** (`opt_in`, `opt_out`, `corporate_only`, `published_address`, `blocked`, `unknown`) a česká/anglická poznámka pro n8n. |
| `models.py` | Pydantic modely: `Lead`, `AuditResult`, `SiteCopy`, `BuildResult`, `ProcessResult`, `SegmentStat`, `PlanRow`. |
| `slug.py` | `slugify()` bez knihoven (diakritika přes `unicodedata`), `make_slug(name, city, unique=place_id)`. |
| `places_search.py` | Places API (New) Text Search, stránkování, normalizace na `Lead`, vyřazení trvale zavřených a blokovaných zemí. |
| `audit.py` | `audit_html()` (čistá funkce) + `audit_website()` (stažení, https, certifikát, kontaktní podstránka, PageSpeed). Skóre 0–100 s vysvětlenými důvody česky i anglicky. |
| `industries.py` | Google typ → obor (`remeslo`, `salon`, `autoservis`, `gastro`, `zdravi`, `obecny`), barvy, fonty, ikony, náhradní služby/FAQ cs+en, `queue_suggestions`. |
| `copy_writer.py` | Texty webu: přísný JSON brief pro LLM (jen fakta, žádné ceny/ocenění/roky), validace, 1 opakování, jinak přirozený šablonový text podle oboru. |
| `images.py` | Foto z Pexels (s kreditem) nebo přechod + SVG motiv + rámeček „Vaše fotografie“. |
| `templates/` | Jinja2: `base.html.j2`, `industries/*.html.j2` (6 vizuálních variant), `partials/` (ikony, formulář, lišta náhledu). |
| `generate_site.py` | `build_site()` → `PREVIEW_DIR/<slug>/index.html` + `meta.json`. Jeden soubor, inline CSS, `noindex`, OG tagy, lišta „Nezávazný návrh…“. |
| `screenshot_compare.py` | Playwright 390×844 @2x (starý web i nový náhled), Pillow `compare.png` („DNES“ / „NOVÝ NÁVRH“), `new_mobile.png`, `og.png` 1200×630. |
| `deploy_preview.py` | `publish(slug)` (práva, `index.json`, URL), `cleanup(older_than_days)`, `set_status()`, stub `publish_cloudflare_pages()`. Náhledy servíruje Caddy přímo z `PREVIEW_DIR`. |
| `learn.py` | „Vzorec“: `compute_weights()` + `plan_day()` – viz níže. |
| `run.py` | `process_lead(dict)` – celý řetězec pro jeden lead, nikdy nevyhodí výjimku, vrací plochý JSON. |
| `api.py` | HTTP JSON API (stdlib `ThreadingHTTPServer`), Bearer token. |
| `cli.py` | Příkazy `search`, `audit`, `process`, `plan-day`, `learn`, `demo`, `cleanup`, `queue-suggestions`, `serve`. |
| `tests/` | `unittest` – spustit z kořene repozitáře: `python -m unittest discover -s pipeline/tests -t .` |

---

## Proměnné prostředí

| Proměnná | Výchozí | Význam |
|---|---|---|
| `PLACES_API_KEY` | – | **povinné** pro vyhledávání (Google Places API New) |
| `LLM_BASE_URL` | `http://litellm:4000/v1` | OpenAI-kompatibilní brána (LiteLLM) |
| `LLM_API_KEY` | – | klíč k bráně; bez něj se zkusí Anthropic, bez obojího šablonové texty |
| `LLM_MODEL_COPY` / `LLM_MODEL_CLASSIFY` | `copy` / `classify` | aliasy modelů v LiteLLM |
| `ANTHROPIC_API_KEY` | – | přímé volání Anthropic Messages API (záloha) |
| `ANTHROPIC_MODEL` | `claude-sonnet-5-5` | model pro přímé volání |
| `PAGESPEED_API_KEY` | – | nepovinné; zapne PageSpeed mobile skóre v auditu (+10–40 s na web) |
| `PEXELS_API_KEY` | – | nepovinné; ilustrační fotky do hero sekce |
| `PREVIEW_DIR` | `/srv/nahled` | kam se zapisují náhledy (sdílený svazek s Caddy) |
| `PREVIEW_BASE_URL` | `https://nahled.krystofkoci.com` | veřejná URL náhledů |
| `FORM_WEBHOOK_URL` | – | n8n webhook, kam formulář na náhledu POSTuje `{lead_id,name,email,message,source:"preview"}` |
| `OWNER_NAME` / `OWNER_EMAIL` / `OWNER_SITE` | Kryštof Kočí / kontakt@krystofkoci.com / https://krystofkoci.com | identita v patičce a liště |
| `OWNER_WHATSAPP` | – | tvoje číslo v E.164 (`+420…`); přidá do lišty náhledu tlačítko „WhatsApp“ (wa.me). „Chci tento web“ vždy vede na `mailto:` OWNER_EMAIL |
| `API_TOKEN` | – | **povinné** pro `serve`; n8n posílá `Authorization: Bearer …` |
| `API_PORT` / `API_HOST` | `8077` / `0.0.0.0` | port API |
| `BLOCKED_COUNTRIES` | `CR` | čárkami oddělené ISO2 kódy; **CR se přidá vždy** |
| `ALLOWED_STRICT_COUNTRIES` | – | povolí země s přísným režimem (DE, AT, CH, NL); CR povolit nelze |
| `DEFAULT_MARKET` | `cz` | trh, když ho nelze odvodit ze země |
| `HTTP_TIMEOUT` / `SCREENSHOT_TIMEOUT` | `15` / `20` | sekundy |

---

## API pro n8n

Všechny požadavky JSON, odpověď JSON. Kromě `/health` je nutná hlavička
`Authorization: Bearer <API_TOKEN>`. Chyby: `{"ok": false, "error": "<česky>"}`.

| Metoda a cesta | Tělo | Vrací |
|---|---|---|
| `GET /health` | – | verze, veřejná nastavení (bez klíčů), blokované země |
| `GET /previews` | – | registr publikovaných náhledů (`index.json`) |
| `POST /search` | `{"query":"plumber Austin","country":"US","limit":20}` nebo `{"city","category","country"}` | `{leads:[Lead…], dropped_blocked, dropped_closed, pages}` |
| `POST /audit` | `{"url":"https://…"}` | skóre, větev, důvody cs/en, e-maily, telefony, sociální sítě, CMS |
| `POST /process` | `{"lead":{…z /search nebo ze Sheets…}, "force":false, "screenshots":true}` | plochý záznam: `branch` (`no_website`/`redesign`/`skip`/`blocked`), `score`, `reasons_cs`, `reasons_en`, `emails`, `best_email`, `phones`, `preview_url`, `compare_png_url`, `og_png_url`, `industry`, `country`, `tz`, `legal_regime`, `legal_note_cs`, `copy_source`, `warnings[]` |
| `POST /plan_day` | `{"queue":[{country,city,category,enabled,priority?}], "weights":<výstup /learn>, "target":30, "skip_rate":0.5}` | `{plan:[{country,city,category,industry,lang,market,limit,query}], total_limit}` |
| `POST /learn` | `{"leads":[…], "deals":[…], "outcomes":[…]}` (exporty listů Sheets) | segmenty s váhami + `recommendations_cs` / `recommendations_en` |
| `POST /cleanup` | `{"older_than_days":60, "statuses":{slug:status}, "dry_run":false}` | co bylo smazáno / ponecháno |
| `POST /status` | `{"slug":"…","status":"sent"}` | zapíše stav do registru (pro cleanup) |

Větev `skip` vrací audit bez stavby náhledu. Větev `blocked` vrací
`blocked_reason` a nic nestahuje ani nestaví. Pole `tz` použij v n8n pro
naplánování odeslání na 8–10 h místního času adresáta; `legal_regime`
rozhoduje o patičce (`emails/`) a u `corporate_only` (GB/IE) o kontrole právní formy.

Spuštění: `python -m pipeline.cli serve` (v Dockeru je to `CMD`). Build obrazu
z kořene repozitáře: `docker build -f pipeline/Dockerfile -t web-outreach-pipeline .`

---

## CLI

```bash
python -m pipeline.cli search --country CZ --city Kolín --category instalatér --limit 20
python -m pipeline.cli audit https://example.cz
python -m pipeline.cli process --lead lead.json [--force] [--no-llm] [--no-screenshots]
python -m pipeline.cli plan-day --queue queue.json --weights weights.json --target 30
python -m pipeline.cli learn --leads leads.json --deals deals.json --outcomes outcomes.json --brief
python -m pipeline.cli demo --out /srv/nahled [--screenshots] [--no-llm] [--no-images]
python -m pipeline.cli cleanup --older-than-days 60 --dry-run
python -m pipeline.cli queue-suggestions --industry remeslo
```

### Demo

`demo` vytvoří 6 fiktivních firem × cs/en do `DIR/demo-<obor>[-en]/`:
Instalatérství Novák & syn, Salon Lucie, Autoservis U Dvou Kol, Kavárna Pod Lípou,
Zubní ordinace Zdravý úsměv, Firma Vzor s.r.o. (+ anglické protějšky v US/GB/CA/IE/AU/NZ).
Demo stránky nemají lištu náhledu a v patičce mají „Ukázkový web – Kryštof Kočí“.
Odkazy na ně patří do galerie na krystofkoci.com.

---

## Přidání oboru / jazyka

**Obor:** v `industries.py` přidej klíč do `INDUSTRIES` (paleta, fonty, `services_cs/en`,
`faq_cs/en`, `why_cs/en`, `stock_cs/en`, `icons`, `queue_suggestions`), namapuj Google typy
v `_TYPE_GROUPS` a vytvoř `templates/industries/<klíč>.html.j2` (stačí `{% extends 'base.html.j2' %}`
a blok `extra_css`). Doplň řádek do `_FALLBACK` v `copy_writer.py`.

**Jazyk (`es`, `de`):** `config.MARKET_LANG`, `countries.COUNTRIES` (lang/market),
`generate_site.I18N`, `generate_site._DAYS`, `copy_writer._SYSTEM` + `_FALLBACK` + `_FORBIDDEN_PATTERNS`,
`industries.*_<lang>`, `screenshot_compare.LABELS`, `images.PLACEHOLDER_*`.

---

## Premium šablony (balíček „šablony 2“)

> **Pozor: pravidla výběru šablon zatím NESCHVÁLIL majitel.** Jsou to výchozí hodnoty z
> zadání; měnit se dají na jednom místě – `premium.py` → `RULES`, `NICHE_TYPES`, `NICHE_WORDS`,
> `TEMPLATES_BY_NICHE`.

Když je `PREMIUM_TEMPLATES=true` (výchozí) a lead patří do jednoho ze 7 oborů, `generate_site`
vyrenderuje ručně navrženou šablonu `templates/premium/<id>.<cs|en>.html.j2` místo obecného
generátoru. Sdílené soubory (obrázky, CSS, JS, three.js…) se kopírují do
`<PREVIEW_DIR>/_assets/p2/<id>/` (`premium.install_assets`). Při chybě se použije starý generátor.
`meta.json` dostane `premium_template` a `premium_niche`.

| Obor | Šablony | Pravidlo (výchozí) |
|---|---|---|
| autoservis | `k-kalous`, `v10-autoservis`, `v13-autoservis` | prémiová značka v názvu nebo na webu firmy (BMW, Mercedes, Audi, Porsche, Lexus, Jaguar, Land Rover, Volvo, Tesla…) → **K**; „autorizovaný/značkový servis, dealer“ → **V10**; víc poboček → střídání V10/V13; jinak **V13** (`data-pobocky=1`) |
| elektrikář | `v04-elektro`, `v11-elektro` | **V11** jen pro „firmu do 2 lidí“ (bez s.r.o./a.s./GmbH/Ltd/Inc/LLC v názvu a < 30 recenzí) a z nich ~20 % (`ELEKTRO_SMALL_SHARE`), jinak **V04** |
| opravář spotřebičů | `v03-opravar` | vždy |
| dámské kadeřnictví | `v12-kadernictvi` | vždy |
| barbershop | `v12-barber` | vždy (barber má přednost před kadeřnictvím) |
| restaurace | `v04-restaurace`, `v11-restaurace` | rovnoměrně |
| květinářství | `mesicek`, `v08-kvetiny`, `v11-kvetiny` | rovnoměrně |

Rozdělení „rovnoměrně / ~20 %“ je stabilní podle slugu (sha1), takže stejný lead dostane vždy
stejnou šablonu. Počet poboček se zatím nezjišťuje (`branches=1`).

Data v šablonách jsou jen z leadu: chybějící telefon/e-mail/adresa/otevírací doba/hodnocení
se skryjí (žádné `[doplnit]`). Ceny = „Cena na dotaz“ / „Price on request“. Hodnocení: pod 50
recenzí jen známka, od 50 i počet. Formuláře posílají JSON na `FORM_WEBHOOK_URL` s `lead_id`.

Šablony se generují konvertorem z ručních návrhů (`tools/premium/`, není součástí běhu pipeline):
`python3 build.py` → `templates/premium/` + `premium_assets/`. EN texty jsou ve slovnících
`tools/premium/en/*.json`.

Nasazení: `infra/nasadit_sablony.sh <balíček.tgz>` (testovací režim) a pak `--ostre`.

---

## Limity a náklady

* **Google Places API (New)** – maska polí s `websiteUri`, telefony, hodnocením a otevírací dobou
  spadá do dražšího SKU (Text Search Pro/Enterprise, řádově 0,03–0,04 USD za požadavek,
  20 výsledků). Každá další stránka je další požadavek. Při 30 náhledech/den a 50 % skip
  je to cca 4–6 požadavků denně. Trvale se smí ukládat jen `place_id`; ostatní pole obnovit
  do 30 dnů (`docs/02_PRAVNI_CHECKLIST.md`, oddíl 5).
* **PageSpeed Insights v5** – zdarma s klíčem (25 000/den), ale 10–40 s na web; zapnuto jen
  s `PAGESPEED_API_KEY`, lze vypnout per požadavek (`"pagespeed": false`).
* **Pexels** – zdarma, 200 požadavků/hod; fotky se hot-linkují s kreditem fotografa.
* **LLM přes LiteLLM** – jeden požadavek ≈ 1 500 výstupních tokenů na náhled, při chybné
  odpovědi jedno opakování. Bez brány i bez `ANTHROPIC_API_KEY` se použijí šablonové texty
  (`copy_source: "fallback"`) – náhled vznikne vždy.
* **Playwright** – starý web má 20 s, pak šedý zástupný obrázek; nový náhled se renderuje
  z `file://`. Chromium je v Docker obrazu.
* Každý náhled je jeden HTML soubor (~30 kB) + 4 PNG (~1–2 MB). Úklid po 60 dnech přes `/cleanup`.

## Blokované země

`CR` je blokováno natvrdo (`config.ALWAYS_BLOCKED_COUNTRIES`) – vyřadí se už při vyhledávání
(`places_search`, loguje se počet), `process_lead` vrátí `branch: "blocked"`, `plan_day` řádek
fronty přeskočí. `BLOCKED_COUNTRIES` přidává další země. `DE`, `AT`, `CH`, `NL` jsou blokované
kvůli přísnému režimu, dokud je nepovolíš v `ALLOWED_STRICT_COUNTRIES`. Lead bez země se
nezpracuje (bezpečnostní výchozí stav) – doplň `country` nebo spusť s `force`.

## Jak funguje „vzorec“ (`learn.py`)

1. `compute_weights(leads, deals, outcomes)` spojí tři listy CRM podle `lead_id` a pro každý
   odeslaný lead zjistí: odpověděl / schůzka / vyhráno, zemi, obor, skóre, variantu předmětu,
   den a hodinu odeslání.
2. Pro každý segment (země, obor, země×obor, pásmo skóre, varianta předmětu, den, hodina)
   spočítá míru odpovědí a výher a **vyhladí je k celkovému průměru** (prior síly 10):
   `smoothed = (won + 10·global) / (sent + 10)`. Segment se 2 odeslanými a 1 výhrou tak
   nevypadá lépe než segment s 200 odeslanými a 40 výhrami.
3. `weight = clip(smoothed / global, 0.3, 3.0)`. Dokud nejsou aspoň 3 výhry, váhy vycházejí
   z míry odpovědí (`basis: "reply"`), potom z míry výher.
4. Vrátí české i anglické věty typu „Autoservisy v USA uzavírají zakázku 2,1× častěji než
   průměr – navýšit podíl“, „Předmět B má o 40 % vyšší odpověď než předmět A“, nejlepší den a hodina.
5. `plan_day(queue, weights, target=30, skip_rate=0.5)` spočítá potřebný počet leadů
   (`30 / (1 − 0,5) = 60`), rozdělí ho mezi skupiny země×obor úměrně vahám (× `priority` řádku),
   v každé skupině točí města round-robin (kurzor v `PREVIEW_DIR/_state/plan.json`) a
   každému vybranému řádku dá `limit` 5–20. Vypnuté řádky (`enabled: false`) a blokované země
   se nikdy neplánují. Výsledek je deterministický – stejný vstup, stejný plán.

## Kontrola před odesláním (checklist)

- [ ] `branch` je `no_website` nebo `redesign` a `score` dává smysl proti `reasons_cs`.
- [ ] `country` ≠ CR a `legal_regime` není `blocked`/`unknown`; u GB/IE ověřena právní forma (Ltd).
- [ ] `preview_url` se otevře, lišta „Nezávazný návrh…“ je vidět, tlačítko „Chci tento web“ míří na e-mail (a „WhatsApp“ na tvé číslo, je-li nastavené).
- [ ] Texty neobsahují ceny, roky, certifikace ani sliby, které firma neuvedla; `[DOPLNÍTE]` je v pořádku (ukazuje, co doplní klient).
- [ ] `compare.png` – vlevo skutečně jejich web (ne cizí), vpravo nový návrh; jméno firmy správně.
- [ ] `best_email` je obecná firemní schránka (info@, kontakt@…), ne osobní adresa zaměstnance.
- [ ] `tz` odpovídá adrese; e-mail naplánovat na 8–10 h místního času.
- [ ] Fotka z Pexels sedí k oboru (jinak nechat zástupný rámeček).
- [ ] `warnings[]` prázdné nebo pochopené (chybějící screenshot starého webu je OK u `no_website`).
