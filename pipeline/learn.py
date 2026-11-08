"""The owner's "formula": learn which segments convert and plan tomorrow's searches.

Everything is deterministic and explainable - no ML, just counting with
Bayesian smoothing so that a segment with 2 sent / 1 won does not look
better than one with 200 sent / 40 won.

``compute_weights(leads, deals, outcomes)``
    merges the three CRM sheets, aggregates per segment (country, industry,
    country x industry, score bucket, subject variant, weekday and hour of
    sending) and returns smoothed rates, a weight per segment and Czech +
    English recommendation sentences.

    Smoothing (Laplace / Bayesian toward the global mean, prior strength
    ``PRIOR_STRENGTH`` = 10)::

        smoothed = (won + 10 * global_rate) / (sent + 10)
        weight   = clip(smoothed / global_rate, 0.3, 3.0)

    While there are fewer than ``MIN_WON_FOR_WIN_BASIS`` won deals overall the
    weights are driven by the *reply* rate instead (``basis = "reply"``),
    otherwise by the *win* rate.

``plan_day(queue_rows, weights, target_previews=30, skip_rate=0.5)``
    turns the queue (country/city/category rows from Sheets) into today's
    list of Places searches, allocating lead limits proportionally to the
    segment weights, honouring ``enabled``, excluding blocked countries
    (Costa Rica always) and rotating cities round-robin with a cursor stored
    in ``PREVIEW_DIR/_state/plan.json``.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import countries, industries
from .config import Settings, get_settings
from .models import LearnResult, PlanRow, SegmentStat

log = logging.getLogger("pipeline.learn")

PRIOR_STRENGTH = 10.0
WEIGHT_MIN, WEIGHT_MAX = 0.3, 3.0
MIN_WON_FOR_WIN_BASIS = 3
MIN_SENT_FOR_RECOMMENDATION = 10
HOUR_BUCKETS = [(6, 8, "06-08"), (8, 10, "08-10"), (10, 12, "10-12"), (12, 14, "12-14"),
                (14, 17, "14-17"), (17, 20, "17-20")]
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_WEEKDAY_CS = {"mon": "v pondělí", "tue": "v úterý", "wed": "ve středu", "thu": "ve čtvrtek", "fri": "v pátek",
               "sat": "v sobotu", "sun": "v neděli"}
_WEEKDAY_EN = {"mon": "on Mondays", "tue": "on Tuesdays", "wed": "on Wednesdays", "thu": "on Thursdays",
               "fri": "on Fridays", "sat": "on Saturdays", "sun": "on Sundays"}
_INDUSTRY_CS_PL = {"remeslo": "Řemeslníci", "salon": "Salony", "autoservis": "Autoservisy", "gastro": "Gastro podniky",
                   "zdravi": "Zdravotnická zařízení", "obecny": "Ostatní firmy"}
_INDUSTRY_EN_PL = {"remeslo": "Trades", "salon": "Salons", "autoservis": "Auto repair shops", "gastro": "Restaurants & cafes",
                   "zdravi": "Health practices", "obecny": "Other businesses"}
_COUNTRY_CS_LOC = {"CZ": "v Česku", "SK": "na Slovensku", "US": "v USA", "GB": "ve Velké Británii", "IE": "v Irsku",
                   "CA": "v Kanadě", "AU": "v Austrálii", "NZ": "na Novém Zélandu", "PL": "v Polsku",
                   "DE": "v Německu", "AT": "v Rakousku", "CH": "ve Švýcarsku", "NL": "v Nizozemsku"}

_POSITIVE_EVENTS = {"replied": {"replied", "reply", "answered", "odpoved", "odpovedel", "interested"},
                    "meeting": {"negotiating", "offer_sent", "nabidka", "meeting", "demo"},  # = písemné jednání o ceně (schůzky se nedělají)
                    "won": {"won", "deal", "paid", "customer", "vyhrano", "zakaznik"}}
_SENT_STATUSES = {"sent", "contacted", "odeslano", "followup", "follow_up", "replied", "meeting", "won", "lost",
                  "unsubscribed", "bounced", "negotiating", "interested", "not_interested", "no_reply"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    txt = str(value).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%Y-%m-%d"):
        try:
            return datetime.fromisoformat(txt) if fmt is None else datetime.strptime(txt, fmt)
        except ValueError:
            continue
    return None


def _truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "ano", "y", "won", "x"}


def score_bucket(score: Any, branch: str = "") -> str:
    if branch == "no_website":
        return "no_website"
    try:
        sc = int(float(score))
    except (TypeError, ValueError):
        return "unknown"
    if sc >= 80:
        return "80-100"
    if sc >= 60:
        return "60-79"
    if sc >= 45:
        return "45-59"
    return "<45"


def hour_bucket(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    for lo, hi, label in HOUR_BUCKETS:
        if lo <= dt.hour < hi:
            return label
    return "other"


def _industry_of(row: dict) -> str:
    ind = (row.get("industry") or "").strip().lower()
    if ind in industries.INDUSTRIES:
        return ind
    return industries.industry_for(row.get("primary_type", ""), row.get("types") or [],
                                   row.get("name", ""), row.get("category", ""))


def merge_records(leads: Iterable[dict], deals: Iterable[dict], outcomes: Iterable[dict]) -> Dict[str, dict]:
    """Return per-lead facts: sent, replied, meeting, won + segment attributes."""
    per: Dict[str, dict] = {}
    for row in leads or []:
        lid = str(row.get("lead_id") or row.get("id") or "").strip()
        if not lid:
            continue
        status = str(row.get("status") or "").strip().lower()
        sent_at = _parse_dt(row.get("sent_at") or row.get("first_sent_at"))
        rec = per.setdefault(lid, {"sent": False, "replied": False, "meeting": False, "won": False})
        rec.update({
            "country": str(row.get("country") or "").upper(),
            "industry": _industry_of(row),
            "score_bucket": score_bucket(row.get("score"), str(row.get("branch") or "")),
            "subject_variant": str(row.get("subject_variant") or row.get("variant") or "").strip().upper(),
            "sent_at": sent_at,
        })
        if sent_at or status in _SENT_STATUSES or _truthy(row.get("sent")):
            rec["sent"] = True
        for key, names in _POSITIVE_EVENTS.items():
            if status in names or _truthy(row.get(key)):
                rec[key] = True
    for row in outcomes or []:
        lid = str(row.get("lead_id") or row.get("id") or "").strip()
        if not lid:
            continue
        rec = per.setdefault(lid, {"sent": False, "replied": False, "meeting": False, "won": False,
                                   "country": "", "industry": "obecny", "score_bucket": "unknown",
                                   "subject_variant": "", "sent_at": None})
        event = str(row.get("event") or row.get("type") or row.get("status") or "").strip().lower()
        at = _parse_dt(row.get("at") or row.get("timestamp") or row.get("date"))
        if event in {"sent", "odeslano", "email_sent"}:
            rec["sent"] = True
            if at and not rec.get("sent_at"):
                rec["sent_at"] = at
        for key, names in _POSITIVE_EVENTS.items():
            if event in names:
                rec[key] = True
                rec["sent"] = True
    for row in deals or []:
        lid = str(row.get("lead_id") or row.get("id") or "").strip()
        if not lid:
            continue
        rec = per.setdefault(lid, {"sent": True, "replied": True, "meeting": False, "won": False,
                                   "country": "", "industry": "obecny", "score_bucket": "unknown",
                                   "subject_variant": "", "sent_at": None})
        status = str(row.get("status") or "").strip().lower()
        if _truthy(row.get("won")) or status in _POSITIVE_EVENTS["won"]:
            rec["won"] = True
            rec["replied"] = True
            rec["sent"] = True
        if status in _POSITIVE_EVENTS["meeting"] or _truthy(row.get("meeting")):
            rec["meeting"] = True
    # implied funnel: won -> meeting? not necessarily; replied -> sent
    for rec in per.values():
        if rec["won"] or rec["meeting"] or rec["replied"]:
            rec["sent"] = True
        if rec["won"]:
            rec["replied"] = True
    return per


# ---------------------------------------------------------------------------
# weights
# ---------------------------------------------------------------------------
def _segment_keys(rec: dict) -> List[Tuple[str, str, dict]]:
    """(dimension, key, attributes) for every segment a lead belongs to."""
    out = []
    c, i, sb, sv = rec.get("country", ""), rec.get("industry", ""), rec.get("score_bucket", ""), rec.get("subject_variant", "")
    dt = rec.get("sent_at")
    if c:
        out.append(("country", f"country={c}", {"country": c}))
    if i:
        out.append(("industry", f"industry={i}", {"industry": i}))
    if c and i:
        out.append(("country_industry", f"country={c}|industry={i}", {"country": c, "industry": i}))
    if sb:
        out.append(("score_bucket", f"score_bucket={sb}", {"score_bucket": sb}))
    if sv:
        out.append(("subject_variant", f"subject_variant={sv}", {"subject_variant": sv}))
    if dt:
        wd = WEEKDAYS[dt.weekday()]
        out.append(("weekday", f"weekday={wd}", {"weekday": wd}))
        hb = hour_bucket(dt)
        if hb:
            out.append(("hour", f"hour={hb}", {"hour": hb}))
    return out


def _smooth(successes: int, trials: int, global_rate: float) -> float:
    return (successes + PRIOR_STRENGTH * global_rate) / (trials + PRIOR_STRENGTH) if trials + PRIOR_STRENGTH > 0 else global_rate


def _weight(smoothed: float, global_rate: float) -> float:
    if global_rate <= 0:
        return 1.0
    return round(max(WEIGHT_MIN, min(WEIGHT_MAX, smoothed / global_rate)), 3)


def compute_weights(leads: List[dict], deals: List[dict], outcomes: List[dict]) -> Dict[str, Any]:
    """See module docstring. Returns a JSON-serialisable dict (``LearnResult``)."""
    per = merge_records(leads, deals, outcomes)
    sent_recs = [r for r in per.values() if r["sent"]]
    total_sent = len(sent_recs)
    total_replied = sum(1 for r in sent_recs if r["replied"])
    total_meet = sum(1 for r in sent_recs if r["meeting"])
    total_won = sum(1 for r in sent_recs if r["won"])
    g_reply = total_replied / total_sent if total_sent else 0.0
    g_win = total_won / total_sent if total_sent else 0.0
    basis = "win" if total_won >= MIN_WON_FOR_WIN_BASIS else "reply"
    g_basis = g_win if basis == "win" else g_reply

    agg: Dict[str, dict] = {}
    for rec in sent_recs:
        for dim, key, attrs in _segment_keys(rec):
            a = agg.setdefault(key, {"dimension": dim, "attrs": attrs, "sent": 0, "replied": 0, "meetings": 0, "won": 0})
            a["sent"] += 1
            a["replied"] += int(rec["replied"])
            a["meetings"] += int(rec["meeting"])
            a["won"] += int(rec["won"])

    segments: List[SegmentStat] = []
    for key, a in agg.items():
        s_reply = _smooth(a["replied"], a["sent"], g_reply)
        s_win = _smooth(a["won"], a["sent"], g_win)
        seg = SegmentStat(
            key=key, dimension=a["dimension"], **a["attrs"],
            sent=a["sent"], replied=a["replied"], meetings=a["meetings"], won=a["won"],
            reply_rate=round(a["replied"] / a["sent"], 4) if a["sent"] else 0.0,
            win_rate=round(a["won"] / a["sent"], 4) if a["sent"] else 0.0,
            smoothed_reply_rate=round(s_reply, 4), smoothed_win_rate=round(s_win, 4),
            weight=_weight(s_win if basis == "win" else s_reply, g_basis),
        )
        segments.append(seg)
    segments.sort(key=lambda x: (x.dimension, -x.weight, x.key))

    rec_cs, rec_en = _recommendations(segments, basis, total_sent, g_reply, g_win)
    result = LearnResult(
        basis=basis,
        totals={"leads": len(per), "sent": total_sent, "replied": total_replied, "meetings": total_meet, "won": total_won,
                "reply_rate": round(g_reply, 4), "win_rate": round(g_win, 4), "prior_strength": PRIOR_STRENGTH},
        segments=segments, recommendations_cs=rec_cs, recommendations_en=rec_en,
    )
    return result.model_dump()


def _ratio_cs(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "×"


def _label_cs(seg: SegmentStat) -> str:
    ind = _INDUSTRY_CS_PL.get(seg.industry, seg.industry)
    cty = _COUNTRY_CS_LOC.get(seg.country, f"v zemi {seg.country}")
    if seg.dimension == "country_industry":
        return f"{ind} {cty}"
    if seg.dimension == "country":
        return f"Firmy {cty}"
    if seg.dimension == "industry":
        return ind
    if seg.dimension == "score_bucket":
        return "Firmy bez webu" if seg.score_bucket == "no_website" else f"Weby se skóre {seg.score_bucket}"
    return seg.key


def _label_en(seg: SegmentStat) -> str:
    ind = _INDUSTRY_EN_PL.get(seg.industry, seg.industry)
    cty = countries.get_country(seg.country).name_en if seg.country else ""
    if seg.dimension == "country_industry":
        return f"{ind} in {cty}"
    if seg.dimension == "country":
        return f"Businesses in {cty}"
    if seg.dimension == "industry":
        return ind
    if seg.dimension == "score_bucket":
        return "Businesses without a website" if seg.score_bucket == "no_website" else f"Sites scored {seg.score_bucket}"
    return seg.key


def _recommendations(segments: List[SegmentStat], basis: str, total_sent: int, g_reply: float,
                     g_win: float) -> Tuple[List[str], List[str]]:
    cs: List[str] = []
    en: List[str] = []
    verb_cs = "uzavírají zakázku" if basis == "win" else "odpovídají"
    verb_en = "convert" if basis == "win" else "reply"
    if total_sent < 30:
        cs.append(f"Zatím málo dat ({total_sent} odeslaných e-mailů) – doporučení jsou orientační, váhy se drží blízko 1.")
        en.append(f"Little data so far ({total_sent} e-mails sent) – recommendations are indicative, weights stay close to 1.")
    if basis == "reply":
        cs.append("Váhy zatím vychází z míry odpovědí (méně než 3 uzavřené zakázky); po prvních zakázkách se přepnou na míru výher.")
        en.append("Weights are based on reply rate for now (fewer than 3 won deals); they switch to win rate once deals come in.")

    for dim in ("country_industry", "country", "industry", "score_bucket"):
        for seg in [x for x in segments if x.dimension == dim and x.sent >= MIN_SENT_FOR_RECOMMENDATION]:
            if seg.weight >= 1.3:
                cs.append(f"{_label_cs(seg)} {verb_cs} {_ratio_cs(seg.weight)} častěji než průměr – navýšit podíl.")
                en.append(f"{_label_en(seg)} {verb_en} {seg.weight:.1f}× more often than average – increase share.")
            elif seg.weight <= 0.7:
                pct = int(round((1 - seg.weight) * 100))
                cs.append(f"{_label_cs(seg)} {verb_cs} o {pct} % méně často než průměr – snížit podíl.")
                en.append(f"{_label_en(seg)} {verb_en} {pct}% less often than average – reduce share.")

    subj = [x for x in segments if x.dimension == "subject_variant" and x.sent >= MIN_SENT_FOR_RECOMMENDATION]
    if len(subj) >= 2:
        subj.sort(key=lambda x: -x.smoothed_reply_rate)
        best, second = subj[0], subj[1]
        if second.smoothed_reply_rate > 0:
            diff = int(round((best.smoothed_reply_rate / second.smoothed_reply_rate - 1) * 100))
            if diff >= 10:
                cs.append(f"Předmět {best.subject_variant} má o {diff} % vyšší odpověď než předmět {second.subject_variant} – používat přednostně.")
                en.append(f"Subject {best.subject_variant} gets {diff}% more replies than subject {second.subject_variant} – prefer it.")

    days = [x for x in segments if x.dimension == "weekday" and x.sent >= MIN_SENT_FOR_RECOMMENDATION]
    hours = [x for x in segments if x.dimension == "hour" and x.sent >= MIN_SENT_FOR_RECOMMENDATION]
    if days:
        best_d = max(days, key=lambda x: x.smoothed_reply_rate)
        if hours:
            best_h = max(hours, key=lambda x: x.smoothed_reply_rate)
            cs.append(f"Nejvíce odpovědí přinášejí e-maily odeslané {_WEEKDAY_CS[best_d.weekday]} mezi {best_h.hour.replace('-', '–')} h "
                      f"(odpověď {best_d.reply_rate * 100:.0f} % / {best_h.reply_rate * 100:.0f} %).")
            en.append(f"Most replies come from e-mails sent {_WEEKDAY_EN[best_d.weekday]} between {best_h.hour.replace('-', '–')} "
                      f"(reply {best_d.reply_rate * 100:.0f}% / {best_h.reply_rate * 100:.0f}%).")
        else:
            cs.append(f"Nejvíce odpovědí přinášejí e-maily odeslané {_WEEKDAY_CS[best_d.weekday]} ({best_d.reply_rate * 100:.0f} %).")
            en.append(f"Most replies come from e-mails sent {_WEEKDAY_EN[best_d.weekday]} ({best_d.reply_rate * 100:.0f}%).")
    if total_sent and g_reply:
        cs.append(f"Celkem: {total_sent} odesláno, odpověď {g_reply * 100:.0f} %, výhra {g_win * 100:.1f} %.")
        en.append(f"Overall: {total_sent} sent, reply {g_reply * 100:.0f}%, win {g_win * 100:.1f}%.")
    return cs, en


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------
def _weight_lookup(weights: Any) -> Dict[str, float]:
    if not weights:
        return {}
    segs = weights.get("segments") if isinstance(weights, dict) else weights
    out: Dict[str, float] = {}
    for seg in segs or []:
        key = seg.get("key") if isinstance(seg, dict) else getattr(seg, "key", None)
        w = seg.get("weight") if isinstance(seg, dict) else getattr(seg, "weight", 1.0)
        if key:
            try:
                out[key] = float(w)
            except (TypeError, ValueError):
                pass
    return out


def group_weight(country: str, industry: str, lookup: Dict[str, float]) -> float:
    key = f"country={country}|industry={industry}"
    if key in lookup:
        return lookup[key]
    w = lookup.get(f"country={country}", 1.0) * lookup.get(f"industry={industry}", 1.0)
    return max(WEIGHT_MIN, min(WEIGHT_MAX, w))


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"cursors": {}}


def _save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        log.warning("Nelze uložit stav plánu do %s: %s", path, exc)


def plan_day(queue_rows: List[dict], weights: Any = None, target_previews: int = 30, skip_rate: float = 0.5,
             *, state_path: Optional[Path] = None, settings: Optional[Settings] = None,
             max_limit: int = 20, min_limit: int = 5) -> List[dict]:
    """Allocate today's Places searches. Returns ``[PlanRow dict, ...]``.

    ``queue_rows``: ``{country, city, category, industry?, lang?, market?, enabled?, priority?}``.
    ``weights``: output of :func:`compute_weights` (or its ``segments`` list) - optional.
    """
    s = settings or get_settings()
    skip_rate = min(0.95, max(0.0, float(skip_rate)))
    needed = max(1, math.ceil(int(target_previews) / (1.0 - skip_rate)))
    lookup = _weight_lookup(weights)
    state_path = Path(state_path) if state_path else s.state_dir / "plan.json"
    state = _load_state(state_path)
    cursors: Dict[str, int] = dict(state.get("cursors") or {})

    groups: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    skipped_blocked = 0
    for row in queue_rows or []:
        if not _truthy(row.get("enabled", True)):
            continue
        country = str(row.get("country") or "").strip().upper()
        city = str(row.get("city") or "").strip()
        category = str(row.get("category") or "").strip()
        if not (country and city and category):
            continue
        if s.is_blocked(country):
            skipped_blocked += 1
            continue
        ind = _industry_of(row)
        groups[(country, ind)].append({**row, "country": country, "city": city, "category": category, "industry": ind})
    if skipped_blocked:
        log.info("plan_day: %d řádků fronty vynecháno (blokovaná země)", skipped_blocked)
    if not groups:
        return []

    gw: Dict[Tuple[str, str], float] = {}
    for gkey, rows in groups.items():
        prio = sum(float(r.get("priority") or 1.0) for r in rows) / len(rows)
        gw[gkey] = group_weight(gkey[0], gkey[1], lookup) * max(0.1, prio)
    total_w = sum(gw.values())
    alloc = {g: needed * w / total_w for g, w in gw.items()}

    plan: List[PlanRow] = []
    for gkey in sorted(groups, key=lambda g: (-gw[g], g)):
        rows = groups[gkey]
        remaining = alloc[gkey]
        ckey = f"{gkey[0]}|{gkey[1]}"
        cursor = int(cursors.get(ckey, 0)) % len(rows)
        picks = 0
        while remaining > 0.5 and picks < len(rows):
            row = rows[cursor]
            cursor = (cursor + 1) % len(rows)
            picks += 1
            limit = int(min(max_limit, max(min_limit, round(remaining))))
            cinfo = countries.get_country(gkey[0])
            lang = str(row.get("lang") or cinfo.lang)
            market = str(row.get("market") or cinfo.market)
            plan.append(PlanRow(country=gkey[0], city=row["city"], category=row["category"], industry=gkey[1],
                                lang=lang, market=market, limit=limit, weight=round(gw[gkey], 3),
                                query=f"{row['category']} {row['city']}"))
            remaining -= limit
        cursors[ckey] = cursor
    state["cursors"] = cursors
    state["last_run"] = datetime.now().replace(microsecond=0).isoformat()
    state["needed"] = needed
    _save_state(state_path, state)
    return [p.model_dump() for p in plan]
