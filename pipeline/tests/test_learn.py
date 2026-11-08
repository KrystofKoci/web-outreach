import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import learn
from pipeline.config import Settings


def synthetic(seed=7, n=400):
    rnd = random.Random(seed)
    leads, deals, outcomes = [], [], []
    # autoservis/US converts much better than the rest; subject B better than A
    for i in range(n):
        country = rnd.choice(["CZ", "US", "GB", "CR"])
        industry = rnd.choice(["autoservis", "remeslo", "salon"])
        variant = rnd.choice(["A", "B"])
        score = rnd.choice([50, 70, 90])
        hour = rnd.choice([8, 9, 11, 15])
        weekday = rnd.choice([0, 1, 2, 3, 4])
        day = 6 + weekday + 7 * (i % 3)
        sent_at = f"2026-10-{day:02d}T{hour:02d}:15:00"
        p_reply = 0.1 + (0.35 if (country, industry) == ("US", "autoservis") else 0) + (0.12 if variant == "B" else 0)
        replied = rnd.random() < p_reply
        won = replied and rnd.random() < 0.4
        leads.append({"lead_id": f"L{i}", "country": country, "industry": industry, "score": score,
                      "subject_variant": variant, "sent_at": sent_at, "status": "replied" if replied else "sent"})
        if won:
            deals.append({"lead_id": f"L{i}", "status": "won"})
        outcomes.append({"lead_id": f"L{i}", "event": "sent", "at": sent_at})
    return leads, deals, outcomes


class LearnTests(unittest.TestCase):
    def test_compute_weights(self):
        leads, deals, outcomes = synthetic()
        out = learn.compute_weights(leads, deals, outcomes)
        self.assertEqual(out["basis"], "win")
        segs = {s["key"]: s for s in out["segments"]}
        self.assertEqual(out["totals"]["sent"], 400)
        us_auto = segs["country=US|industry=autoservis"]
        self.assertGreater(us_auto["weight"], 1.3)
        self.assertLessEqual(us_auto["weight"], 3.0)
        self.assertGreater(us_auto["win_rate"], segs["industry=remeslo"]["win_rate"])
        # smoothing pulls tiny segments toward the mean
        for s in out["segments"]:
            self.assertGreaterEqual(s["weight"], 0.3)
            self.assertLessEqual(s["weight"], 3.0)
        self.assertTrue(any("Autoservisy v USA" in r for r in out["recommendations_cs"]), out["recommendations_cs"])
        self.assertTrue(any("Předmět B" in r for r in out["recommendations_cs"]), out["recommendations_cs"])
        self.assertEqual(len(out["recommendations_cs"]), len(out["recommendations_en"]))
        self.assertTrue(any(s["dimension"] == "weekday" for s in out["segments"]))
        self.assertTrue(any(s["dimension"] == "hour" for s in out["segments"]))
        json.dumps(out)   # serialisable

    def test_reply_basis_when_no_deals(self):
        leads, _, outcomes = synthetic(n=60)
        out = learn.compute_weights(leads, [], outcomes)
        self.assertEqual(out["basis"], "reply")
        self.assertTrue(any("míry odpovědí" in r for r in out["recommendations_cs"]))

    def test_empty_input(self):
        out = learn.compute_weights([], [], [])
        self.assertEqual(out["segments"], [])
        self.assertEqual(out["totals"]["sent"], 0)

    def test_plan_day_excludes_blocked_and_rotates(self):
        leads, deals, outcomes = synthetic()
        weights = learn.compute_weights(leads, deals, outcomes)
        queue = [
            {"country": "US", "city": "Austin", "category": "auto repair", "enabled": True},
            {"country": "US", "city": "Dallas", "category": "auto repair", "enabled": True},
            {"country": "US", "city": "Houston", "category": "auto repair", "enabled": True},
            {"country": "CZ", "city": "Kolín", "category": "instalatér", "enabled": True},
            {"country": "CZ", "city": "Brno", "category": "kadeřnictví", "enabled": "ano"},
            {"country": "CZ", "city": "Praha", "category": "instalatér", "enabled": False},
            {"country": "CR", "city": "San José", "category": "taller mecánico", "enabled": True},
            {"country": "DE", "city": "Berlin", "category": "Klempner", "enabled": True},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(preview_dir=Path(tmp))
            state = Path(tmp) / "plan.json"
            plan1 = learn.plan_day(queue, weights, target_previews=30, skip_rate=0.5, state_path=state, settings=s)
            plan2 = learn.plan_day(queue, weights, target_previews=30, skip_rate=0.5, state_path=state, settings=s)
            self.assertTrue(state.exists())
            self.assertIn("cursors", json.loads(state.read_text()))
        self.assertTrue(plan1)
        countries = {p["country"] for p in plan1}
        self.assertNotIn("CR", countries)
        self.assertNotIn("DE", countries)
        self.assertNotIn("Praha", {p["city"] for p in plan1})
        total = sum(p["limit"] for p in plan1)
        self.assertGreaterEqual(total, 40)
        self.assertLessEqual(total, 90)
        us = [p for p in plan1 if p["country"] == "US"]
        cz_rem = [p for p in plan1 if p["country"] == "CZ" and p["industry"] == "remeslo"]
        self.assertGreater(sum(p["limit"] for p in us), sum(p["limit"] for p in cz_rem))
        self.assertTrue(all(p["lang"] == "en" and p["market"] == "en" for p in us))
        # rotation: the first US city differs between day 1 and day 2 when not all cities were used
        if len(us) < 3:
            self.assertNotEqual(us[0]["city"], [p for p in plan2 if p["country"] == "US"][0]["city"])

    def test_plan_day_never_plans_cr_even_without_weights(self):
        queue = [{"country": "CR", "city": "Liberia", "category": "restaurante"},
                 {"country": "cz", "city": "Olomouc", "category": "kavárna"}]
        with tempfile.TemporaryDirectory() as tmp:
            plan = learn.plan_day(queue, None, state_path=Path(tmp) / "p.json", settings=Settings(preview_dir=Path(tmp)))
        self.assertEqual([p["country"] for p in plan], ["CZ"])
        self.assertEqual(plan[0]["query"], "kavárna Olomouc")


if __name__ == "__main__":
    unittest.main()
