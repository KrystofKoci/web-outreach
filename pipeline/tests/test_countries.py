import os
import unittest
from unittest import mock

from pipeline import countries
from pipeline.config import Settings, get_settings, parse_country_list
from pipeline.models import Lead


class CountryTests(unittest.TestCase):
    def test_regimes(self):
        self.assertEqual(countries.legal_regime("CZ"), "opt_in")
        self.assertEqual(countries.legal_regime("SK"), "opt_in")
        self.assertEqual(countries.legal_regime("US"), "opt_out")
        self.assertEqual(countries.legal_regime("GB"), "corporate_only")
        self.assertEqual(countries.legal_regime("IE"), "corporate_only")
        for c in ("CA", "AU", "NZ"):
            self.assertEqual(countries.legal_regime(c), "published_address")
        for c in ("DE", "AT", "CH", "NL", "CR"):
            self.assertEqual(countries.legal_regime(c), "blocked")
        self.assertEqual(countries.legal_regime("XX"), "unknown")
        self.assertTrue(countries.get_country("CZ").legal_note_cs)

    def test_tz_mapping(self):
        self.assertEqual(countries.guess_tz("CZ"), "Europe/Prague")
        self.assertEqual(countries.guess_tz("GB"), "Europe/London")
        self.assertEqual(countries.guess_tz("IE"), "Europe/Dublin")
        self.assertEqual(countries.guess_tz("SK"), "Europe/Bratislava")
        self.assertEqual(countries.guess_tz("PL"), "Europe/Warsaw")
        self.assertEqual(countries.guess_tz("NZ"), "Pacific/Auckland")
        self.assertEqual(countries.guess_tz("US", "NY"), "America/New_York")
        self.assertEqual(countries.guess_tz("US", "California"), "America/Los_Angeles")
        self.assertEqual(countries.guess_tz("US", "CO"), "America/Denver")
        self.assertEqual(countries.guess_tz("US"), "America/Chicago")
        self.assertEqual(countries.guess_tz("US", address="1200 Barton Springs Rd, Austin, TX 78704"), "America/Chicago")
        self.assertEqual(countries.guess_tz("US", address="1 Main St, Boston, MA 02108"), "America/New_York")
        self.assertEqual(countries.guess_tz("CA", "BC"), "America/Vancouver")
        self.assertEqual(countries.guess_tz("CA"), "America/Toronto")
        self.assertEqual(countries.guess_tz("AU", "Western Australia"), "Australia/Perth")
        self.assertEqual(countries.guess_tz("AU"), "Australia/Sydney")
        self.assertEqual(countries.guess_tz("ZZ"), "UTC")
        self.assertEqual(countries.guess_tz(""), "UTC")

    def test_cr_always_blocked(self):
        with mock.patch.dict(os.environ, {"BLOCKED_COUNTRIES": "", "ALLOWED_STRICT_COUNTRIES": "CR,DE"}):
            s = get_settings()
        self.assertTrue(s.is_blocked("CR"))
        self.assertTrue(s.is_blocked("cr"))
        self.assertFalse(s.is_blocked("DE"))      # explicitly allowed strict country
        self.assertTrue(s.is_blocked("AT"))       # strict, not allowed
        self.assertFalse(s.is_blocked("CZ"))
        self.assertIn("Kostarika", s.block_reason("CR"))

    def test_env_blocklist_merged(self):
        with mock.patch.dict(os.environ, {"BLOCKED_COUNTRIES": "pl, ie"}):
            s = get_settings()
        self.assertTrue(s.is_blocked("PL"))
        self.assertTrue(s.is_blocked("IE"))
        self.assertTrue(s.is_blocked("CR"))
        self.assertEqual(parse_country_list("cz;us,,x"), frozenset({"CZ", "US"}))

    def test_lead_derives_market_lang_tz(self):
        lead = Lead(name="Novak & Son Plumbing", country="US", admin_area="TX")
        self.assertEqual((lead.market, lead.lang, lead.tz, lead.legal_regime), ("en", "en", "America/Chicago", "opt_out"))
        lead = Lead(name="Instalatérství", country="CZ")
        self.assertEqual((lead.market, lead.lang, lead.tz, lead.legal_regime), ("cz", "cs", "Europe/Prague", "opt_in"))
        lead = Lead(name="Soda", address="Avenida Central, San José, Costa Rica")
        self.assertEqual(lead.country, "CR")
        self.assertEqual(lead.legal_regime, "blocked")
        flat = lead.as_flat()
        self.assertIn("legal_note_cs", flat)

    def test_settings_public_dict_has_no_secrets(self):
        s = Settings(places_api_key="secret", api_token="tok")
        d = s.as_public_dict()
        self.assertIs(d["places_api_key"], True)
        self.assertIs(d["api_token"], True)
        self.assertIn("CR", d["blocked_countries"])


if __name__ == "__main__":
    unittest.main()
