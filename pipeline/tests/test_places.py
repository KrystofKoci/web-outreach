import unittest
from unittest import mock

from pipeline import places_search
from pipeline.config import Settings


def _place(pid, name, country, website="", status="OPERATIONAL", admin="", city=""):
    comps = [{"longText": country, "shortText": country, "types": ["country"]}]
    if admin:
        comps.append({"longText": admin, "shortText": admin, "types": ["administrative_area_level_1"]})
    if city:
        comps.append({"longText": city, "shortText": city, "types": ["locality"]})
    return {"id": pid, "displayName": {"text": name}, "formattedAddress": f"1 Main St, {city}, {country}",
            "addressComponents": comps, "location": {"latitude": 1.0, "longitude": 2.0},
            "websiteUri": website, "nationalPhoneNumber": "123 456 789", "rating": 4.5, "userRatingCount": 10,
            "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9:00 AM – 5:00 PM"]},
            "primaryType": "plumber", "primaryTypeDisplayName": {"text": "Plumber"}, "types": ["plumber"],
            "googleMapsUri": "https://maps.google.com/?cid=1", "businessStatus": status}


class _Resp:
    def __init__(self, body, status=200):
        self.status_code = status
        self._body = body
        self.text = "x"

    def json(self):
        return self._body


class PlacesTests(unittest.TestCase):
    def test_search_drops_blocked_and_closed_and_paginates(self):
        s = Settings(places_api_key="k")
        page1 = {"places": [_place("a", "Novak Plumbing", "US", "http://novak.com", admin="TX", city="Austin"),
                            _place("b", "Soda Tica", "CR", city="San José"),
                            _place("c", "Closed Co", "US", status="CLOSED_PERMANENTLY")],
                 "nextPageToken": "tok"}
        page2 = {"places": [_place("d", "Second", "US", city="Dallas"), _place("a", "dup", "US")]}
        with mock.patch("pipeline.places_search.requests.post", side_effect=[_Resp(page1), _Resp(page2)]) as post:
            out = places_search.search_places("plumber Austin", region="US", max_results=10, settings=s)
        self.assertEqual(out["dropped_blocked"], 1)
        self.assertEqual(out["dropped_closed"], 1)
        self.assertEqual(out["pages"], 2)
        self.assertEqual([l["id"] for l in out["leads"]], ["a", "d"])
        lead = out["leads"][0]
        self.assertEqual((lead["country"], lead["admin_area"], lead["city"], lead["tz"]), ("US", "TX", "Austin", "America/Chicago"))
        self.assertEqual((lead["market"], lead["lang"], lead["legal_regime"]), ("en", "en", "opt_out"))
        self.assertTrue(lead["has_website"])
        self.assertFalse(out["leads"][1]["has_website"])
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Goog-Api-Key"], "k")
        self.assertIn("places.websiteUri", headers["X-Goog-FieldMask"])
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["pageToken"], "tok")
        self.assertEqual(payload["regionCode"], "US")
        self.assertEqual(payload["languageCode"], "en")

    def test_cz_defaults(self):
        s = Settings(places_api_key="k")
        with mock.patch("pipeline.places_search.requests.post", return_value=_Resp({"places": [_place("x", "Instalatér Novák", "CZ", city="Kolín")]})) as post:
            out = places_search.search_city_category("Kolín", "instalatér", "CZ", settings=s)
        self.assertEqual(post.call_args.kwargs["json"]["languageCode"], "cs")
        self.assertEqual(out["leads"][0]["lang"], "cs")
        self.assertEqual(out["leads"][0]["category"], "instalatér")

    def test_missing_key(self):
        with self.assertRaises(places_search.PlacesError):
            places_search.search_places("x", settings=Settings(places_api_key=None))


if __name__ == "__main__":
    unittest.main()
