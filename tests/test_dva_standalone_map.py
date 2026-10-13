import unittest

from scripts.build_dva_standalone_map import (
    GEOCODE_CACHE,
    MAP_HTML,
    RAW_HTML,
    VENDOR_DIR,
    load_geocode_cache,
    parse_schedule,
    read_service_nodes,
)


class DvaStandaloneMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tracts, cls.schedule = parse_schedule(RAW_HTML.read_text(encoding="utf-8"))

    def test_expected_tracts_are_extracted(self):
        self.assertEqual(len(self.tracts), 35)
        counts = {
            municipality: sum(t["municipality"] == municipality for t in self.tracts)
            for municipality in ("Gagnef", "Leksand", "Rättvik", "Vansbro")
        }
        self.assertEqual(counts, {"Gagnef": 10, "Leksand": 10, "Rättvik": 8, "Vansbro": 7})

    def test_schedule_is_normalized_and_quality_flagged(self):
        self.assertEqual(len(self.schedule), 1830)
        self.assertTrue(all(event["date"].startswith("2026-") for event in self.schedule))
        self.assertTrue(
            any(
                "datum_avviker_från_angiven_veckodag" in event["source_flags"]
                for event in self.schedule
            )
        )

    def test_every_tract_has_a_cached_anchor(self):
        cache = load_geocode_cache()
        self.assertTrue(GEOCODE_CACHE.exists())
        for tract in self.tracts:
            anchor = cache[tract["tract_id"]]
            self.assertIsInstance(anchor["lat"], float)
            self.assertIsInstance(anchor["lon"], float)

    def test_map_is_independent_and_retains_improved_tract_controls(self):
        content = MAP_HTML.read_text(encoding="utf-8")
        self.assertIn('id="tract-layers"', content)
        self.assertNotIn('vehicle-layers', content)
        self.assertNotIn("__TRACT_DATA__", content)
        self.assertIn('src="data/dva-places.js"', content)
        self.assertNotIn('review-data', content)
        self.assertTrue((VENDOR_DIR / "LICENSE").exists())
        self.assertEqual(len(read_service_nodes()), 47)


if __name__ == "__main__":
    unittest.main()
