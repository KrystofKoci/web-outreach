import html as html_mod
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import copy_writer, industries
from pipeline.config import Settings
from pipeline.generate_site import build_site, parse_opening_hours
from pipeline.models import Lead, SiteCopy


def _lead(lang="cs", **kw):
    base = dict(id="p1", name="Instalatérství Novák & syn", category="Instalatér", primary_type="plumber",
                country="CZ" if lang == "cs" else "US", city="Kolín" if lang == "cs" else "Austin",
                address="Pražská 123, 280 02 Kolín" if lang == "cs" else "1 Main St, Austin, TX 78704",
                phone="+420 777 123 456", rating=4.8, rating_count=37, lang=lang, market="cz" if lang == "cs" else "en",
                opening_hours=["pondělí: 8:00–17:00", "sobota: Zavřeno"] if lang == "cs" else ["Monday: 8:00 AM – 5:00 PM", "Saturday: Closed"],
                maps_url="https://maps.google.com/?cid=1")
    base.update(kw)
    return Lead(**base)


class FallbackCopyTests(unittest.TestCase):
    def test_fallback_every_industry_and_lang(self):
        for key in industries.INDUSTRY_KEYS:
            for lang in ("cs", "en"):
                copy = copy_writer.fallback_copy(_lead(lang), key, lang)
                self.assertIsInstance(copy, SiteCopy)
                self.assertEqual(copy.source, "fallback")
                self.assertGreaterEqual(len(copy.services), 3)
                self.assertEqual(len(copy.why_us), 3)
                self.assertGreaterEqual(len(copy.faq), 2)
                self.assertIn("Instalatérství Novák & syn", copy.headline + copy.about_text)
                self.assertNotIn("None", copy.headline + copy.about_text)
                self.assertFalse(copy_writer.find_forbidden_claims(copy, lang, {}), f"{key}/{lang} invented claims")
        cs = copy_writer.fallback_copy(_lead("cs"), "remeslo")
        self.assertEqual(cs.reviews_line, "4,8 z 5 · 37 hodnocení na Google")
        en = copy_writer.fallback_copy(_lead("en"), "remeslo")
        self.assertEqual(en.reviews_line, "4.8 out of 5 · 37 Google reviews")

    def test_industry_detection(self):
        self.assertEqual(industries.industry_for("plumber"), "remeslo")
        self.assertEqual(industries.industry_for("", ["hair_salon"]), "salon")
        self.assertEqual(industries.industry_for("", [], "Autoservis Kuba"), "autoservis")
        self.assertEqual(industries.industry_for("cafe"), "gastro")
        self.assertEqual(industries.industry_for("dentist"), "zdravi")
        self.assertEqual(industries.industry_for("florist"), "obecny")
        self.assertTrue(industries.queue_suggestions()["remeslo"])

    def test_llm_invalid_then_retry_then_fallback(self):
        s = Settings(llm_base_url="http://x", llm_api_key="k")
        bad = {"headline": "Instalatér od roku 1998 – nejlepší v Kolíně", "subheadline": "x" * 20, "cta_primary": "Zavolat",
               "about_title": "O nás", "about_text": "slovo " * 20, "services": [{"title": "A", "text": "bbbbbb"}] * 3,
               "why_us": ["a", "b", "c"], "hours_title": "Hodiny", "contact_title": "Kontakt",
               "faq": [{"q": "Otázka?", "a": "Odpověď."}] * 2, "footer_note": ""}
        with mock.patch("pipeline.copy_writer.chat_json", return_value=bad) as cj:
            copy = copy_writer.write_copy(_lead(), "remeslo", settings=s)
        self.assertEqual(cj.call_count, 2)          # one retry with the error
        self.assertIn("NEPLATNÁ", cj.call_args.args[1])
        self.assertEqual(copy.source, "fallback")

    def test_llm_valid(self):
        s = Settings(llm_base_url="http://x", llm_api_key="k")
        good = {"headline": "Instalatér pro Kolín a okolí", "subheadline": "Zavolejte, domluvíme termín.", "cta_primary": "Zavolat",
                "about_title": "Kdo jsme", "about_text": "Jsme malá firma z Kolína, která dělá vodu, topení a plyn.",
                "services": [{"title": "Voda", "text": "Rozvody vody."}, {"title": "Topení", "text": "Kotle a radiátory."},
                             {"title": "Plyn", "text": "Revize a přípojky."}],
                "why_us": ["Termín platí", "Uklidíme", "Cena předem"], "hours_title": "Otevírací doba",
                "contact_title": "Kontakt", "faq": [{"q": "Jak rychle přijedete?", "a": "Podle vytížení."},
                                                    {"q": "Platí se předem?", "a": "Ne, po práci."}], "footer_note": ""}
        with mock.patch("pipeline.copy_writer.chat_json", return_value=good):
            copy = copy_writer.write_copy(_lead(), "remeslo", settings=s)
        self.assertEqual(copy.source, "llm")
        self.assertEqual(copy.services[0].icon, "wrench")
        self.assertTrue(copy.reviews_line)


class BuildSiteTests(unittest.TestCase):
    def test_build_contains_name_and_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(preview_dir=Path(tmp), form_webhook_url="https://n8n.example/webhook/form", owner_whatsapp="+420 777 123 456")
            for key in industries.INDUSTRY_KEYS:
                for lang in ("cs", "en"):
                    lead = _lead(lang)
                    copy = copy_writer.fallback_copy(lead, key, lang)
                    res = build_site(lead, copy, key, settings=s, use_images=False, best_email="info@firma.cz")
                    html = Path(res.html_path).read_text(encoding="utf-8")
                    self.assertIn(html_mod.escape(lead.name), html)   # '&' is escaped in HTML
                    self.assertIn("Nezávazný návrh" if lang == "cs" else "Non-binding draft", html)
                    self.assertIn("Chci tento web" if lang == "cs" else "I want this website", html)
                    self.assertIn('content="noindex,nofollow"', html)
                    self.assertIn('lang="%s"' % lang, html)
                    self.assertIn("https://wa.me/420777123456", html)
                    self.assertIn("mailto:", html)
                    self.assertIn("https://n8n.example/webhook/form", html)
                    self.assertIn("maps?q=", html)
                    self.assertIn("og:title", html)
                    self.assertNotIn("None", html)
                    self.assertNotIn("[object", html)
                    self.assertNotIn("&#39;", html.split("<style>")[1].split("</style>")[0])   # font names not escaped in CSS
                    meta = json.loads(Path(res.meta_path).read_text(encoding="utf-8"))
                    self.assertEqual(meta["industry"], key)
                    self.assertEqual(res.url, f"https://nahled.krystofkoci.com/{res.slug}/")

    def test_demo_has_no_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(preview_dir=Path(tmp))
            lead = _lead()
            copy = copy_writer.fallback_copy(lead, "gastro")
            res = build_site(lead, copy, "gastro", settings=s, demo=True, slug="demo-gastro", use_images=False)
            html = Path(res.html_path).read_text(encoding="utf-8")
            self.assertNotIn('id="pv"', html)
            self.assertIn("Ukázkový web", html)
            self.assertEqual(res.slug, "demo-gastro")

    def test_parse_hours(self):
        rows = parse_opening_hours(["Monday: 8:00 AM – 5:00 PM", "Tuesday: Closed", "Sunday: 9:00 AM – 1:30 PM"], "cs")
        self.assertEqual(rows[0], ("Pondělí", "8:00–17:00"))
        self.assertEqual(rows[1], ("Úterý", "Zavřeno"))
        self.assertEqual(rows[6], ("Neděle", "9:00–13:30"))
        self.assertEqual(len(rows), 7)
        self.assertEqual(parse_opening_hours([], "en"), [])


if __name__ == "__main__":
    unittest.main()
