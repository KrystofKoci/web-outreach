import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline import copy_writer, screenshot_compare
from pipeline.config import Settings
from pipeline.generate_site import build_site
from pipeline.models import Lead


class ComposeTests(unittest.TestCase):
    def test_compose_without_playwright(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = screenshot_compare.compose_compare(None, None, Path(tmp) / "compare.png", name="Firma Vzor s.r.o.",
                                                     lang="cs", owner_name="Kryštof Kočí")
            with Image.open(out) as img:
                self.assertEqual(img.size[0], 780 * 2 + 60 * 2 + 60)
            og = screenshot_compare.compose_og(None, Path(tmp) / "og.png", name="Firma Vzor", lang="en", owner_name="K")
            with Image.open(og) as img:
                self.assertEqual(img.size, (1200, 630))
            res = screenshot_compare.make_screenshots(Path(tmp), old_url="", name="X", lang="cs", with_playwright=False)
            self.assertTrue(Path(res["compare_png"]).exists())

    @unittest.skipUnless(os.environ.get("RUN_PLAYWRIGHT") == "1", "set RUN_PLAYWRIGHT=1 to render with Chromium")
    def test_playwright_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(preview_dir=Path(tmp))
            lead = Lead(id="t", name="Salon Lucie", country="CZ", city="Brno", address="Veveří 45, Brno", phone="+420 605 222 333")
            copy = copy_writer.fallback_copy(lead, "salon")
            build = build_site(lead, copy, "salon", settings=s, use_images=False)
            res = screenshot_compare.make_screenshots(Path(build.path), old_url="", name=lead.name, lang="cs", settings=s)
            self.assertTrue(res["new_ok"], res)
            with Image.open(res["new_mobile_png"]) as img:
                self.assertEqual(img.size, (780, 1688))
            self.assertTrue(Path(res["og_png"]).exists())


if __name__ == "__main__":
    unittest.main()
