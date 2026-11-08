import unittest

from pipeline.slug import make_slug, slugify, unique_slug


class SlugTests(unittest.TestCase):
    def test_czech_diacritics(self):
        self.assertEqual(slugify("Instalatérství Novák & syn"), "instalaterstvi-novak-a-syn")
        self.assertEqual(slugify("Řeznictví U Šťastných"), "reznictvi-u-stastnych")

    def test_english_ampersand(self):
        self.assertEqual(slugify("Novak & Son Plumbing", lang="en"), "novak-and-son-plumbing")

    def test_empty_and_symbols(self):
        self.assertEqual(slugify(""), "web")
        self.assertEqual(slugify("***"), "web")
        self.assertEqual(slugify("  Café   Ølsen!!  "), "cafe-olsen")

    def test_max_len(self):
        s = slugify("a" * 30 + " " + "b" * 30, max_len=20)
        self.assertLessEqual(len(s), 20)
        self.assertFalse(s.endswith("-"))

    def test_make_slug_stable(self):
        a = make_slug("Salon Lucie", "Brno", unique="place123")
        b = make_slug("Salon Lucie", "Brno", unique="place123")
        c = make_slug("Salon Lucie", "Brno", unique="place999")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("salon-lucie-brno-"))

    def test_unique_slug(self):
        self.assertEqual(unique_slug("x", ["x", "x-2"]), "x-3")
        self.assertEqual(unique_slug("y", ["x"]), "y")


if __name__ == "__main__":
    unittest.main()
