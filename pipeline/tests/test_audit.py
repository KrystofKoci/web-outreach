import unittest
from datetime import datetime, timezone
from pathlib import Path

from pipeline import audit
from pipeline.config import Settings

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


class AuditHtmlTests(unittest.TestCase):
    def test_old_site_scores_high(self):
        html = (FIX / "old_site.html").read_text(encoding="utf-8")
        res = audit.audit_html(html, "http://www.instalaterstvi-novak.cz/", final_url="http://www.instalaterstvi-novak.cz/", now=NOW)
        keys = {r.key for r in res.reasons}
        self.assertFalse(res.viewport)
        self.assertEqual(res.copyright_year, 2014)
        self.assertEqual(res.cms, "FrontPage")
        self.assertEqual(res.jquery_version, "1.4.2")
        self.assertTrue(res.has_flash)
        self.assertTrue(res.table_layout)
        for k in ("no_viewport", "old_copyright", "old_jquery", "flash", "table_layout", "legacy_tags", "no_https"):
            self.assertIn(k, keys)
        self.assertGreaterEqual(res.score, 80)
        self.assertEqual(res.branch, "redesign")
        self.assertEqual(res.emails[0], "info@example.com")
        self.assertIn("josef.novak@example.com", res.emails)
        # sorted by weight desc
        weights = [r.weight for r in res.reasons]
        self.assertEqual(weights, sorted(weights, reverse=True))
        self.assertTrue(all(r.text_cs and r.text_en for r in res.reasons))

    def test_modern_site_scores_low(self):
        html = (FIX / "modern_site.html").read_text(encoding="utf-8")
        res = audit.audit_html(html, "https://autoservis-dvorak.cz/", final_url="https://autoservis-dvorak.cz/", now=NOW)
        self.assertTrue(res.viewport)
        self.assertIn("media-queries", res.responsive_signals)
        self.assertTrue(res.has_contact_form)
        self.assertEqual(res.tel_links, ["+420377123987"])
        self.assertEqual(res.social.facebook, "https://www.facebook.com/autoservisdvorak")
        self.assertEqual(res.lang, "cs")
        self.assertLess(res.score, 20)
        self.assertEqual(res.branch, "skip")
        self.assertEqual(res.emails, ["servis@example.com"])

    def test_parked_site_is_no_website(self):
        html = (FIX / "parked_site.html").read_text(encoding="utf-8")
        res = audit.audit_html(html, "http://kavarnapodlipou.cz/", now=NOW)
        self.assertTrue(res.parked)
        self.assertEqual(res.branch, "no_website")
        self.assertEqual(res.score, 100)
        self.assertEqual(res.reasons[0].key, "parked")

    def test_empty_page_is_placeholder(self):
        res = audit.audit_html("<html><body></body></html>", "http://x.cz/", now=NOW)
        self.assertTrue(res.parked)

    def test_pagespeed_and_cert(self):
        html = (FIX / "modern_site.html").read_text(encoding="utf-8")
        res = audit.audit_html(html, "http://autoservis-dvorak.cz/", final_url="http://autoservis-dvorak.cz/",
                               cert_error=True, pagespeed_mobile=35, now=NOW)
        keys = {r.key for r in res.reasons}
        self.assertIn("cert_error", keys)
        self.assertIn("slow_mobile", keys)

    def test_rank_emails(self):
        ranked = audit.rank_emails(["jan.novak@firma.cz", "info@firma.cz", "logo@2x.png", "x@example.com", "info@firma.cz"], "firma.cz")
        self.assertEqual(ranked, ["info@firma.cz", "jan.novak@firma.cz"])

    def test_social_only_is_no_website(self):
        self.assertEqual(audit.social_only_result("https://www.facebook.com/salonlucie").reasons[0].key, "social_only")
        self.assertEqual(audit.social_only_result("http://www.firmy.cz/detail/123").reasons[0].key, "directory_only")
        self.assertIsNone(audit.social_only_result("https://salonlucie.cz"))
        self.assertEqual(audit.audit_website("https://instagram.com/x", Settings()).branch, "no_website")

    def test_unreachable_and_none(self):
        self.assertEqual(audit.unreachable_result("http://x.cz", "timeout").branch, "no_website")
        self.assertEqual(audit.no_website_result().reasons[0].key, "no_website")
        self.assertEqual(audit.normalise_url("firma.cz"), "http://firma.cz")


if __name__ == "__main__":
    unittest.main()
