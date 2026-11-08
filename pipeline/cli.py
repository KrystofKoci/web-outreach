"""Příkazová řádka pipeline (``python -m pipeline.cli <příkaz>``).

Příkazy:

  search     vyhledat firmy přes Google Places (New)
  audit      zauditovat jeden web
  process    zpracovat jeden lead z JSON souboru (audit -> texty -> náhled -> screenshoty)
  plan-day   naplánovat dnešní vyhledávání z fronty (JSON) a vah
  learn      spočítat váhy segmentů z exportů CRM (leads/deals/outcomes JSON)
  demo       vygenerovat 6 fiktivních ukázkových webů (cs + en)
  cleanup    smazat staré náhledy
  serve      spustit HTTP API pro n8n

Výstup příkazů je JSON na stdout (vhodné pro n8n Execute Command), logy jdou na stderr.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from . import __version__, audit, deploy_preview, generate_site, industries, learn, places_search, run, screenshot_compare
from .config import get_settings
from .copy_writer import write_copy
from .models import Lead


def _out(data: Any) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=1, default=str) + "\n")


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# demo data - fictional businesses (no real company data)
# ---------------------------------------------------------------------------
_HOURS_CS = ["pondělí: 8:00–17:00", "úterý: 8:00–17:00", "středa: 8:00–17:00", "čtvrtek: 8:00–17:00",
             "pátek: 8:00–15:00", "sobota: Zavřeno", "neděle: Zavřeno"]
_HOURS_EN = ["Monday: 8:00 AM – 5:00 PM", "Tuesday: 8:00 AM – 5:00 PM", "Wednesday: 8:00 AM – 5:00 PM",
             "Thursday: 8:00 AM – 5:00 PM", "Friday: 8:00 AM – 3:00 PM", "Saturday: Closed", "Sunday: Closed"]
_HOURS_GASTRO_CS = ["pondělí: Zavřeno", "úterý: 8:00–18:00", "středa: 8:00–18:00", "čtvrtek: 8:00–18:00",
                    "pátek: 8:00–20:00", "sobota: 9:00–20:00", "neděle: 9:00–16:00"]
_HOURS_GASTRO_EN = ["Monday: Closed", "Tuesday: 8:00 AM – 6:00 PM", "Wednesday: 8:00 AM – 6:00 PM",
                    "Thursday: 8:00 AM – 6:00 PM", "Friday: 8:00 AM – 8:00 PM", "Saturday: 9:00 AM – 8:00 PM",
                    "Sunday: 9:00 AM – 4:00 PM"]

DEMO_BUSINESSES: List[Dict[str, Any]] = [
    {"industry": "remeslo", "cs": dict(name="Instalatérství Novák & syn", category="Instalatér", city="Kolín",
                                       address="Pražská 123, 280 02 Kolín", phone="+420 777 123 456",
                                       rating=4.8, rating_count=37, opening_hours=_HOURS_CS),
     "en": dict(name="Novak & Son Plumbing", category="Plumber", city="Austin", admin_area="TX",
                address="1200 Barton Springs Rd, Austin, TX 78704", phone="(512) 555-0134",
                rating=4.8, rating_count=112, opening_hours=_HOURS_EN)},
    {"industry": "salon", "cs": dict(name="Salon Lucie", category="Kadeřnictví", city="Brno",
                                     address="Veveří 45, 602 00 Brno", phone="+420 605 222 333",
                                     rating=4.9, rating_count=58, opening_hours=_HOURS_CS),
     "en": dict(name="Lucy's Hair Studio", category="Hair salon", city="Leeds",
                address="12 Call Lane, Leeds LS1 6DT", phone="0113 496 0123",
                rating=4.9, rating_count=74, opening_hours=_HOURS_EN)},
    {"industry": "autoservis", "cs": dict(name="Autoservis U Dvou Kol", category="Autoservis", city="Plzeň",
                                          address="Domažlická 88, 318 00 Plzeň", phone="+420 377 123 987",
                                          rating=4.6, rating_count=121, opening_hours=_HOURS_CS),
     "en": dict(name="Two Wheels Auto Repair", category="Auto repair shop", city="Calgary", admin_area="AB",
                address="4510 Macleod Trail SW, Calgary, AB T2G 0A4", phone="(403) 555-0199",
                rating=4.6, rating_count=203, opening_hours=_HOURS_EN)},
    {"industry": "gastro", "cs": dict(name="Kavárna Pod Lípou", category="Kavárna", city="Olomouc",
                                      address="Horní náměstí 7, 779 00 Olomouc", phone="+420 585 111 222",
                                      rating=4.7, rating_count=215, opening_hours=_HOURS_GASTRO_CS),
     "en": dict(name="The Linden Tree Café", category="Café", city="Dublin",
                address="18 Camden Street Lower, Dublin 2", phone="01 496 0123",
                rating=4.7, rating_count=340, opening_hours=_HOURS_GASTRO_EN)},
    {"industry": "zdravi", "cs": dict(name="Zubní ordinace Zdravý úsměv", category="Zubní ordinace", city="Hradec Králové",
                                      address="Gočárova třída 15, 500 02 Hradec Králové", phone="+420 495 333 444",
                                      rating=4.9, rating_count=46, opening_hours=_HOURS_CS),
     "en": dict(name="Healthy Smile Dental", category="Dentist", city="Melbourne", admin_area="VIC",
                address="220 Collins St, Melbourne VIC 3000", phone="(03) 5550 1234",
                rating=4.9, rating_count=88, opening_hours=_HOURS_EN)},
    {"industry": "obecny", "cs": dict(name="Firma Vzor s.r.o.", category="Účetní kancelář", city="Pardubice",
                                      address="Masarykovo náměstí 2, 530 02 Pardubice", phone="+420 466 555 666",
                                      rating=4.5, rating_count=12, opening_hours=_HOURS_CS),
     "en": dict(name="Sample Company Ltd", category="Accounting firm", city="Wellington",
                address="50 Lambton Quay, Wellington 6011", phone="04 555 0123",
                rating=4.5, rating_count=19, opening_hours=_HOURS_EN)},
]
_DEMO_COUNTRY = {"cs": "CZ", "en": {"remeslo": "US", "salon": "GB", "autoservis": "CA", "gastro": "IE", "zdravi": "AU", "obecny": "NZ"}}


def cmd_demo(args: argparse.Namespace) -> int:
    s = get_settings()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for item in DEMO_BUSINESSES:
        ind = item["industry"]
        if args.industry and ind != args.industry:
            continue
        for lang in ("cs", "en"):
            if args.lang and lang != args.lang:
                continue
            data = dict(item[lang])
            country = _DEMO_COUNTRY["cs"] if lang == "cs" else _DEMO_COUNTRY["en"][ind]
            slug = f"demo-{ind}" + ("" if lang == "cs" else "-en")
            lead = Lead(id=slug, name=data.pop("name"), country=country, lang=lang,
                        market="cz" if lang == "cs" else "en", maps_url="https://www.google.com/maps", source="demo", **data)
            copy = write_copy(lead, ind, settings=s, use_llm=not args.no_llm)
            build = generate_site.build_site(lead, copy, ind, out_dir=out_dir, slug=slug, demo=True, settings=s,
                                             use_images=not args.no_images)
            row = {"slug": slug, "path": build.path, "industry": ind, "lang": lang, "copy_source": copy.source}
            if args.screenshots:
                shots = screenshot_compare.make_screenshots(build.path, old_url="", name=lead.name, lang=lang,
                                                            brand_hex=industries.get_industry(ind)["palette"]["brand"],
                                                            settings=s, with_playwright=True)
                row["screenshots"] = {k: v for k, v in shots.items() if k != "warnings"}
                row["warnings"] = shots.get("warnings", [])
            if out_dir.resolve() == Path(s.preview_dir).resolve():
                row["urls"] = deploy_preview.publish(slug, status="demo", settings=s)
            results.append(row)
            logging.getLogger("pipeline.cli").info("demo %s hotovo (%s)", slug, copy.source)
    _out({"ok": True, "out": str(out_dir), "built": results})
    return 0


# ---------------------------------------------------------------------------
# other commands
# ---------------------------------------------------------------------------
def cmd_search(args: argparse.Namespace) -> int:
    s = get_settings()
    if s.is_blocked(args.country):
        _out({"ok": False, "error": s.block_reason(args.country)})
        return 2
    try:
        if args.query:
            out = places_search.search_places(args.query, region=args.country, max_results=args.limit, settings=s)
        else:
            out = places_search.search_city_category(args.city, args.category, args.country, limit=args.limit, settings=s)
    except places_search.PlacesError as exc:
        _out({"ok": False, "error": str(exc)})
        return 2
    out["ok"] = True
    _out(out)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    res = audit.audit_website(args.url, get_settings(), with_pagespeed=not args.no_pagespeed)
    _out(res.summary())
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    data = _load_json(args.lead)
    if isinstance(data, dict) and "lead" in data:
        data = data["lead"]
    out = run.process_lead(data, market=args.market, lang=args.lang, force=args.force,
                           with_screenshots=not args.no_screenshots, with_llm=not args.no_llm,
                           with_images=not args.no_images)
    _out(out)
    return 0 if out.get("branch") != "blocked" else 3


def cmd_plan_day(args: argparse.Namespace) -> int:
    queue = _load_json(args.queue)
    weights = _load_json(args.weights) if args.weights else None
    plan = learn.plan_day(queue, weights, args.target, args.skip_rate,
                          state_path=Path(args.state) if args.state else None)
    _out({"ok": True, "plan": plan, "count": len(plan), "total_limit": sum(p["limit"] for p in plan)})
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    leads = _load_json(args.leads) if args.leads else []
    deals = _load_json(args.deals) if args.deals else []
    outcomes = _load_json(args.outcomes) if args.outcomes else []
    out = learn.compute_weights(leads, deals, outcomes)
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    _out(out if not args.brief else {"basis": out["basis"], "totals": out["totals"],
                                     "recommendations_cs": out["recommendations_cs"]})
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    out = deploy_preview.cleanup(args.older_than_days, include_demo=args.include_demo, dry_run=args.dry_run)
    _out(out)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from . import api
    api.serve()
    return 0


def cmd_queue_suggestions(args: argparse.Namespace) -> int:
    _out(industries.queue_suggestions(args.industry))
    return 0


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pipeline.cli", description="web-outreach pipeline (náhledy webů pro oslovení firem)")
    p.add_argument("--version", action="version", version=f"web-outreach {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="podrobnější logy na stderr")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", help="vyhledat firmy přes Google Places")
    sp.add_argument("--query", help="volný dotaz, např. 'instalatér Kolín'")
    sp.add_argument("--city", help="město (použije se s --category)")
    sp.add_argument("--category", help="kategorie / fráze, např. 'plumber'")
    sp.add_argument("--country", required=True, help="ISO2 země, např. CZ, US")
    sp.add_argument("--limit", type=int, default=20, help="max. počet leadů (výchozí 20)")
    sp.set_defaults(func=cmd_search)

    ap = sub.add_parser("audit", help="zauditovat web")
    ap.add_argument("url")
    ap.add_argument("--no-pagespeed", action="store_true", help="nevolat PageSpeed ani s klíčem")
    ap.set_defaults(func=cmd_audit)

    pp = sub.add_parser("process", help="zpracovat jeden lead")
    pp.add_argument("--lead", required=True, help="cesta k lead.json")
    pp.add_argument("--market", choices=("cz", "en"))
    pp.add_argument("--lang", choices=("cs", "en"))
    pp.add_argument("--force", action="store_true", help="postavit náhled i pro větev skip")
    pp.add_argument("--no-screenshots", action="store_true")
    pp.add_argument("--no-llm", action="store_true", help="použít jen šablonové texty")
    pp.add_argument("--no-images", action="store_true", help="nevolat Pexels")
    pp.set_defaults(func=cmd_process)

    dp = sub.add_parser("plan-day", help="naplánovat dnešní vyhledávání")
    dp.add_argument("--queue", required=True, help="JSON pole řádků fronty {country, city, category, enabled}")
    dp.add_argument("--weights", help="JSON výstup příkazu learn (nepovinné)")
    dp.add_argument("--target", type=int, default=30, help="cílový počet náhledů (výchozí 30)")
    dp.add_argument("--skip-rate", type=float, default=0.5, help="očekávaný podíl leadů s dobrým webem (výchozí 0.5)")
    dp.add_argument("--state", help="cesta k plan.json se stavem rotace (výchozí PREVIEW_DIR/_state/plan.json)")
    dp.set_defaults(func=cmd_plan_day)

    lp = sub.add_parser("learn", help="spočítat váhy segmentů ('vzorec')")
    lp.add_argument("--leads", help="JSON export listu leads")
    lp.add_argument("--deals", help="JSON export listu deals")
    lp.add_argument("--outcomes", help="JSON export listu outcomes/events")
    lp.add_argument("--out", help="kam uložit výsledek (JSON)")
    lp.add_argument("--brief", action="store_true", help="vypsat jen souhrn a doporučení")
    lp.set_defaults(func=cmd_learn)

    mp = sub.add_parser("demo", help="vygenerovat ukázkové weby (6 fiktivních firem × cs/en)")
    mp.add_argument("--out", required=True, help="výstupní adresář (např. /srv/nahled)")
    mp.add_argument("--industry", choices=industries.INDUSTRY_KEYS, help="jen jeden obor")
    mp.add_argument("--lang", choices=("cs", "en"), help="jen jeden jazyk")
    mp.add_argument("--screenshots", action="store_true", help="vyrobit i new_mobile/compare/og PNG (Playwright)")
    mp.add_argument("--no-llm", action="store_true", help="použít jen šablonové texty")
    mp.add_argument("--no-images", action="store_true", help="nevolat Pexels")
    mp.set_defaults(func=cmd_demo)

    cp = sub.add_parser("cleanup", help="smazat staré náhledy")
    cp.add_argument("--older-than-days", type=int, default=60)
    cp.add_argument("--include-demo", action="store_true")
    cp.add_argument("--dry-run", action="store_true")
    cp.set_defaults(func=cmd_cleanup)

    qp = sub.add_parser("queue-suggestions", help="vypsat doporučené vyhledávací fráze podle oboru")
    qp.add_argument("--industry", choices=industries.INDUSTRY_KEYS)
    qp.set_defaults(func=cmd_queue_suggestions)

    sv = sub.add_parser("serve", help="spustit HTTP API pro n8n (port API_PORT, výchozí 8077)")
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
