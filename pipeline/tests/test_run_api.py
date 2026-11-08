import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import api, deploy_preview, run
from pipeline.config import Settings
from pipeline.tests.test_audit import FIX


class ProcessLeadTests(unittest.TestCase):
    def test_blocked_country(self):
        s = Settings()
        out = run.process_lead({"name": "Soda Tica", "country": "CR", "website": "http://x.cr"}, settings=s)
        self.assertEqual(out["branch"], "blocked")
        self.assertIn("Kostarika", out["blocked_reason"])
        self.assertFalse(out["built"])

    def test_unknown_country_blocked_unless_forced(self):
        out = run.process_lead({"name": "Firma", "website": ""}, settings=Settings())
        self.assertEqual(out["branch"], "blocked")

    def test_no_website_builds_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(preview_dir=Path(tmp))
            lead = {"id": "p9", "name": "Kavárna Pod Lípou", "country": "CZ", "city": "Olomouc", "primary_type": "cafe",
                    "address": "Horní náměstí 7, Olomouc", "phone": "+420 585 111 222", "rating": "4.7", "rating_count": "215"}
            out = run.process_lead(lead, settings=s, with_screenshots=False, with_llm=False, with_images=False)
            self.assertEqual(out["branch"], "no_website")
            self.assertEqual(out["score"], 100)
            self.assertEqual(out["industry"], "gastro")
            self.assertTrue(out["built"])
            self.assertTrue(out["preview_url"].startswith("https://nahled.krystofkoci.com/kavarna-pod-lipou-olomouc-"))
            self.assertTrue(out["og_png_url"].endswith("og.png"))
            self.assertTrue(out["compare_png_url"].endswith("compare.png"))
            self.assertEqual(out["tz"], "Europe/Prague")
            self.assertEqual(out["legal_regime"], "opt_in")
            self.assertTrue(out["legal_note_cs"])
            self.assertEqual(out["copy_source"], "fallback")
            self.assertTrue((Path(tmp) / out["slug"] / "index.html").exists())
            self.assertTrue((Path(tmp) / out["slug"] / "compare.png").exists())
            reg = deploy_preview.load_registry(s)
            self.assertIn(out["slug"], reg)
            self.assertEqual(deploy_preview.list_previews(s)[0]["slug"], out["slug"])
            # cleanup keeps young previews, dry-run deletes nothing
            res = deploy_preview.cleanup(0, statuses={out["slug"]: "sent"}, dry_run=True, settings=s)
            self.assertEqual(res["deleted"][0]["slug"], out["slug"])
            res = deploy_preview.cleanup(0, statuses={out["slug"]: "won"}, settings=s)
            self.assertEqual(res["deleted"], [])
            res = deploy_preview.cleanup(0, statuses={out["slug"]: "lost"}, settings=s)
            self.assertEqual(res["deleted"][0]["slug"], out["slug"])
            self.assertFalse((Path(tmp) / out["slug"]).exists())

    def test_skip_branch_does_not_build(self):
        html = (FIX / "modern_site.html").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(preview_dir=Path(tmp))
            from pipeline import audit
            fake = audit.audit_html(html, "https://autoservis-dvorak.cz/", final_url="https://autoservis-dvorak.cz/")
            with mock.patch("pipeline.run.audit_mod.audit_website", return_value=fake):
                out = run.process_lead({"name": "Autoservis Dvořák", "country": "CZ", "website": "https://autoservis-dvorak.cz/",
                                        "primary_type": "car_repair"}, settings=s, with_screenshots=False, with_llm=False)
            self.assertEqual(out["branch"], "skip")
            self.assertFalse(out["built"])
            self.assertEqual(out["best_email"], "servis@autoservis-dvorak.cz")
            self.assertEqual(out["emails"], ["servis@autoservis-dvorak.cz"])


class ApiDispatchTests(unittest.TestCase):
    def setUp(self):
        self.s = Settings(api_token="secret")

    def test_health_no_auth(self):
        status, body = api.dispatch("GET", "/health", None, None, self.s)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_auth_required(self):
        status, body = api.dispatch("POST", "/audit", {"url": "x"}, None, self.s)
        self.assertEqual(status, 401)
        self.assertIn("token", body["error"].lower())
        status, _ = api.dispatch("POST", "/nope", {}, "secret", self.s)
        self.assertEqual(status, 404)

    def test_validation_errors_in_czech(self):
        status, body = api.dispatch("POST", "/audit", {}, "secret", self.s)
        self.assertEqual(status, 400)
        self.assertIn("Chybí", body["error"])
        status, body = api.dispatch("POST", "/search", {"query": "soda", "country": "CR"}, "secret", self.s)
        self.assertEqual(status, 400)
        status, body = api.dispatch("POST", "/search", {"query": "x", "country": "CZ"}, "secret", self.s)
        self.assertEqual(status, 502)   # no PLACES_API_KEY

    def test_learn_and_plan(self):
        status, body = api.dispatch("POST", "/learn", {"leads": [], "deals": [], "outcomes": []}, "secret", self.s)
        self.assertEqual(status, 200)
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(api_token="secret", preview_dir=Path(tmp))
            status, body = api.dispatch("POST", "/plan_day", {"queue": [{"country": "CZ", "city": "Brno", "category": "barber"}],
                                                              "target": 10}, "secret", s)
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 1)

    def test_process_blocked_via_api(self):
        status, body = api.dispatch("POST", "/process", {"lead": {"name": "X", "country": "CR"}}, "secret", self.s)
        self.assertEqual(status, 200)
        self.assertEqual(body["branch"], "blocked")


if __name__ == "__main__":
    unittest.main()
