# tools/premium – konvertor ručních návrhů na šablony pipeline

Není součástí běhu pipeline. Převádí ruční HTML návrhy (K, V03…V13, Měsíček, dávka 1) na
`pipeline/templates/premium/<id>.<cs|en>.html.j2` a `pipeline/premium_assets/<id>/`.

    VZORY_DIR=/cesta/k/vzorum python3 build.py            # vše
    VZORY_DIR=... python3 build.py --only v12-barber      # jedna šablona
    python3 leftovers.py                                  # čeština, která zůstala v EN šablonách
    python3 render_all.py /tmp/out full|empty             # vyrenderuje všechny šablony s testovacím leadem
    node check.js /tmp/out 8801 /tmp/shots [ids]          # Playwright 1440/390 (běžící http server na portu)

- `pages.py` – nastavení každé stránky (úpravy textů, co odstranit, rozšíření dávky 1),
- `engine.py` – nahrazení `[doplnit]` daty leadu / skrytí řádku, když data chybí,
- `common.py` – společné bloky (hodnocení Google, patička, lišta náhledu, odeslání formuláře na n8n),
- `en/*.json` – anglické texty (klíč = česká věta).
