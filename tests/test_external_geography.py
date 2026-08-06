"""Kontrakttester för det lokalt sparade SCB-uttaget."""

import json
from pathlib import Path
import unittest
from collections import Counter

import pandas as pd

from dashboard_data import rank_comparable_deso
from dashboard_ui import build_municipality_boundaries


ROOT = Path(__file__).resolve().parents[1]


class ExternalGeographyContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "data/derived/deso_2025_dalarna.geojson").open(
            encoding="utf-8"
        ) as file:
            cls.geojson = json.load(file)
        cls.population = pd.read_csv(
            ROOT / "data/derived/deso_befolkning_2024.csv",
            encoding="utf-8-sig",
            dtype={"kommunkod": str},
        )
        cls.node_deso = pd.read_csv(
            ROOT / "data/derived/nod_deso_2025.csv",
            encoding="utf-8-sig",
            dtype={"kommunkod": str},
        )
        with (ROOT / "data/derived/scb_platsomraden_dalarna.geojson").open(
            encoding="utf-8"
        ) as file:
            cls.place_areas = json.load(file)
        cls.population_grid = pd.read_csv(
            ROOT / "data/derived/befolkning_1km_2025_dalarna.csv",
            encoding="utf-8-sig",
            dtype={"rutid": str, "kommunkod": str},
        )
        with (ROOT / "data/derived/befolkning_1km_2025_dalarna.geojson").open(
            encoding="utf-8"
        ) as file:
            cls.population_grid_geojson = json.load(file)

    def test_dalarna_deso_contract(self) -> None:
        self.assertEqual(len(self.geojson["features"]), 175)
        self.assertEqual(len(self.population), 175)
        self.assertEqual(self.population["desokod"].nunique(), 175)
        self.assertTrue(self.population["kommunkod"].str.startswith("20").all())
        self.assertEqual(int(self.population["befolkning_2024"].sum()), 286_546)

    def test_all_nodes_have_one_deso(self) -> None:
        self.assertEqual(len(self.node_deso), 236)
        self.assertFalse(self.node_deso["desokod"].isna().any())
        self.assertTrue(self.node_deso["antal_deso_traf"].eq(1).all())

    def test_derived_geojson_is_wgs84(self) -> None:
        geometry = self.geojson["features"][0]["geometry"]
        coordinates = geometry["coordinates"]
        while isinstance(coordinates[0], list):
            coordinates = coordinates[0]
        lon, lat = coordinates[:2]
        self.assertGreater(lon, 10)
        self.assertLess(lon, 18)
        self.assertGreater(lat, 59)
        self.assertLess(lat, 63)

    def test_municipality_boundaries_are_derived_from_deso(self) -> None:
        boundaries = build_municipality_boundaries(self.geojson)
        self.assertEqual(
            {
                code
                for feature in boundaries["features"]
                for code in feature["properties"]["kommunkoder"]
            },
            set(self.population["kommunkod"]),
        )
        self.assertEqual(
            sum(
                len(feature["geometry"]["coordinates"])
                for feature in boundaries["features"]
            ),
            14_439,
        )
        self.assertTrue(
            all(
                feature["geometry"]["type"] == "MultiLineString"
                and feature["geometry"]["coordinates"]
                for feature in boundaries["features"]
            )
        )

    def test_bingsjo_context_is_area_not_place_population(self) -> None:
        row = self.node_deso.loc[
            self.node_deso["nodnamn"].eq("Bingsjö Lanthandel")
        ].iloc[0]
        self.assertEqual(row["desokod"], "2031A0010")
        self.assertEqual(int(row["befolkning_2024"]), 2_659)

    def test_comparable_deso_ranking(self) -> None:
        comparable = rank_comparable_deso(
            self.population, "2031A0010", limit=5
        )
        self.assertEqual(len(comparable), 5)
        self.assertNotIn("2031A0010", set(comparable["desokod"]))
        self.assertTrue(comparable["likhetsavstand"].is_monotonic_increasing)

    def test_scb_place_area_contract(self) -> None:
        features = self.place_areas["features"]
        counts = Counter(
            feature["properties"]["omradestyp"] for feature in features
        )
        self.assertEqual(
            counts,
            {"Tätort": 114, "Småort": 181, "Fritidshusområde": 74},
        )
        for feature in features:
            properties = feature["properties"]
            self.assertNotIn("antal_fritidshus", properties)
            if properties["omradestyp"] != "Tätort":
                self.assertFalse(properties["namn"])

    def test_population_grid_contract(self) -> None:
        self.assertEqual(len(self.population_grid), 4_004)
        self.assertEqual(len(self.population_grid_geojson["features"]), 4_004)
        self.assertEqual(int(self.population_grid["befolkning_2025"].sum()), 285_587)
        self.assertEqual(self.population_grid["kommunkod"].nunique(), 15)
        self.assertTrue(self.population_grid["befolkning_2025"].gt(0).all())
        self.assertTrue(self.population_grid["lon"].between(10, 18).all())
        self.assertTrue(self.population_grid["lat"].between(59, 63).all())
        self.assertEqual(
            set(self.population_grid["rutid"]),
            {
                feature["properties"]["rutid"]
                for feature in self.population_grid_geojson["features"]
            },
        )


if __name__ == "__main__":
    unittest.main()
