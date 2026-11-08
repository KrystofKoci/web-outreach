"""Premium šablony: výběr podle oboru/pravidel a render všech šablon CZ/EN s úplnými i chybějícími údaji."""
import re
import tempfile
import unittest
from pathlib import Path

from pipeline import premium
from pipeline.config import get_settings
from pipeline.models import Lead

HRS = ["Monday: 8:00 AM – 5:00 PM", "Tuesday: 8:00 AM – 5:00 PM", "Wednesday: 8:00 AM – 5:00 PM",
       "Thursday: 8:00 AM – 5:00 PM", "Friday: 8:00 AM – 4:00 PM", "Saturday: Closed", "Sunday: Closed"]


def _lead(lang="cs", full=True, **kw):
    base = dict(id="L1", name="Autoservis Novák s.r.o.", country="CZ" if lang == "cs" else "US", lang=lang,
                market="cz" if lang == "cs" else "en", city="Brno" if lang == "cs" else "Tulsa")
    if full:
        base.update(address="Křenová 12, Brno", phone="777 123 456", phone_intl="+420777123456", rating=4.6,
                    rating_count=120, opening_hours=HRS, maps_url="https://maps.google.com/?cid=1")
    base.update(kw)
    return Lead(**base)


def _visible(html: str) -> str:
    html = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S | re.I)
    return html


class TestPick(unittest.TestCase):
    def test_niches(self):
        cases = {
            "car_repair": "autoservis", "electrician": "elektrikar", "appliance_repair_service": "opravar",
            "barber_shop": "barber", "hair_salon": "kadernictvi", "restaurant": "restaurace", "florist": "kvetinarstvi",
        }
        for t, n in cases.items():
            self.assertEqual(premium.niche_for(_lead(primary_type=t, types=[t], name="X")), n, t)
        self.assertEqual(premium.niche_for(_lead(name="Holičství Pepa", types=["beauty_salon"])), "barber")
        self.assertIsNone(premium.niche_for(_lead(name="Zubní ordinace", types=["dentist"], primary_type="dentist")))

    def test_autoservis_rules(self):
        self.assertEqual(premium.pick_template(_lead(name="BMW servis Brno", types=["car_repair"])), "k-kalous")
        self.assertEqual(premium.pick_template(_lead(name="Autorizovaný servis Škoda Novák", types=["car_repair"])), "v10-autoservis")
        self.assertEqual(premium.pick_template(_lead(name="Autoservis Novák", types=["car_repair"])), "v13-autoservis")
        both = {premium.pick_template(_lead(name="Pneu Servis", types=["car_repair"]), slug=f"s{i}", branches=3) for i in range(30)}
        self.assertEqual(both, {"v10-autoservis", "v13-autoservis"})

    def test_elektro_share(self):
        small = [premium.pick_template(_lead(name="Elektro Dvořák", types=["electrician"], rating_count=5), slug=f"e{i}") for i in range(400)]
        share = small.count("v11-elektro") / len(small)
        self.assertTrue(0.1 < share < 0.3, share)
        big = {premium.pick_template(_lead(name="Elektro Dvořák s.r.o.", types=["electrician"], rating_count=5), slug=f"e{i}") for i in range(50)}
        self.assertEqual(big, {"v04-elektro"})

    def test_rotation_stable(self):
        a = premium.pick_template(_lead(name="Květiny", types=["florist"]), slug="fialka-brno")
        self.assertEqual(a, premium.pick_template(_lead(name="Květiny", types=["florist"]), slug="fialka-brno"))
        allk = {premium.pick_template(_lead(name="Květiny", types=["florist"]), slug=f"k{i}") for i in range(60)}
        self.assertEqual(allk, {"mesicek", "v08-kvetiny", "v11-kvetiny"})

    def test_brand_name(self):
        self.assertEqual(premium.brand_name("Autoservis Novák s.r.o."), "Novák")
        self.assertEqual(premium.brand_name("Barbershop"), "Barbershop")


class TestRender(unittest.TestCase):
    def test_all_templates(self):
        s = get_settings()
        s.form_webhook_url = "https://n8n.example/webhook/form"
        for niche, ids in premium.TEMPLATES_BY_NICHE.items():
            for tid in ids:
                for lang in ("cs", "en"):
                    self.assertTrue(premium.available(tid, lang), f"{tid}.{lang}")
                    for full in (True, False):
                        lead = _lead(lang, full, name="Firma Test")
                        html = premium.render(lead, tid, s, slug=f"t-{tid}", best_email="info@firma.cz" if full else "")
                        vis = _visible(html)
                        for bad in ("[doplnit", "@@", "{{", "{%", "[Ulice", "[Město"):
                            self.assertNotIn(bad, vis, f"{tid}.{lang} full={full}: {bad}")
                        self.assertIn("Firma Test", html, tid)
                        self.assertIn('"https://n8n.example/webhook/form"', html, tid)
                        self.assertIn(f"../_assets/{premium.ASSET_NS}/{tid}/", html, tid)
                        if full:
                            self.assertIn("777 123 456", vis, f"{tid}.{lang}")
                        else:
                            self.assertNotIn('href="tel:"', html, f"{tid}.{lang}")
                        if lang == "en":
                            self.assertIn('lang="en"', html[:400], tid)

    def test_assets_install(self):
        with tempfile.TemporaryDirectory() as d:
            done = premium.install_assets(Path(d), "k-kalous")
            self.assertTrue(any(p.endswith("f_0001.webp") for p in done))
            self.assertEqual(premium.install_assets(Path(d), "k-kalous"), [])


if __name__ == "__main__":
    unittest.main()
