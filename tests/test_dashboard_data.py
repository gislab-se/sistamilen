"""Datakontrakt för Fas 1-underlagen."""

import unittest
from pathlib import Path

import pandas as pd

from dashboard_data import (
    aggregate_grid_service_options_by_municipality,
    aggregate_grid_accessibility_to_deso,
    build_service_nodes,
    calculate_grid_accessibility,
    calculate_grid_service_options,
    load_dashboard_data,
)


ROOT = Path(__file__).resolve().parents[1]


class Phase1DataContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.packages, cls.service, cls.profile, cls.clusters, _ = (
            load_dashboard_data(ROOT)
        )
        cls.nodes = build_service_nodes(cls.service, cls.clusters)
        cls.population_grid = pd.read_csv(
            ROOT / "data/derived/befolkning_1km_2025_dalarna.csv",
            encoding="utf-8-sig",
            dtype={"rutid": str, "kommunkod": str},
        )
        cls.population_grid["kommun"] = cls.population_grid["kommunkod"].map(
            cls.nodes.drop_duplicates("kommun").set_index("kommunkod")["kommun"]
            if "kommunkod" in cls.nodes.columns else {}
        )
        cls.deso_population = pd.read_csv(
            ROOT / "data/derived/deso_befolkning_2024.csv",
            encoding="utf-8-sig",
            dtype={"desokod": str, "kommunkod": str},
        )
        municipality_names = (
            cls.population_grid.dropna(subset=["kommun"])
            .drop_duplicates("kommunkod").set_index("kommunkod")["kommun"]
        )
        cls.deso_population["kommun"] = cls.deso_population["desokod"].str[:4].map(
            municipality_names
        )

    def test_source_shapes(self) -> None:
        self.assertEqual(len(self.packages), 15)
        self.assertEqual(len(self.service), 487)
        self.assertEqual(len(self.clusters), 236)

    def test_physical_node_contract(self) -> None:
        self.assertEqual(len(self.nodes), 236)
        self.assertEqual(self.service["kluster_id"].nunique(), 236)
        self.assertEqual(self.service["uuidadrpl"].nunique(), 236)
        self.assertEqual(len(self.service[["e", "n"]].drop_duplicates()), 236)
        self.assertEqual(int(self.nodes["aktorstjanster"].sum()), 487)
        self.assertEqual(
            int(self.nodes["qa_nara_annan_nod_under_25m"].sum()), 6
        )
        self.assertEqual(int(self.nodes["en_aktor"].sum()), 126)
        self.assertEqual(int((~self.nodes["en_aktor"]).sum()), 110)
        self.assertEqual(
            int(self.nodes["leveransfrekvens_saknas"].sum()), 7
        )
        self.assertFalse(
            self.service.duplicated(
                ["kluster_id", "aktor", "typ_servicepunkt"]
            ).any()
        )
        self.assertEqual(
            self.service[["kluster_id", "aktor"]].drop_duplicates().shape[0],
            473,
        )

    def test_node_geography(self) -> None:
        self.assertTrue(self.nodes["lon"].between(10, 18).all())
        self.assertTrue(self.nodes["lat"].between(59, 63).all())
        self.assertTrue(self.nodes["narmaste_annan_nod_km"].gt(0).all())

    def test_municipality_profile_keeps_both_units(self) -> None:
        self.assertEqual(int(self.profile["aktorstjanster"].sum()), 487)
        self.assertEqual(int(self.profile["servicenoder"].sum()), 236)
        for column in [
            "screening_efterfragetryck",
            "screening_nodgleshet",
            "screening_aktorberoende",
            "screening_leveransunderlag",
        ]:
            self.assertTrue(self.profile[column].between(0, 100).all())

    def test_named_cases_are_not_overclaimed(self) -> None:
        bingsjo = self.service.astype(str).apply(
            lambda column: column.str.contains("Bingsjö", case=False, na=False)
        ).any(axis=1)
        self.assertEqual(int(bingsjo.sum()), 1)
        exact_by = self.service["postort"].astype(str).str.fullmatch(
            "By", case=False, na=False
        )
        self.assertFalse(exact_by.any())

    def test_grid_accessibility_scenario_is_a_reversible_comparison(self) -> None:
        baseline = calculate_grid_accessibility(self.population_grid, self.nodes)
        population_by_node = baseline.groupby("narmaste_nod_fore_id")[
            "befolkning_2025"
        ].sum()
        removed_node_id = int(population_by_node.idxmax())
        scenario = calculate_grid_accessibility(
            self.population_grid,
            self.nodes,
            removed_node_id=removed_node_id,
        )
        expected_affected = baseline["narmaste_nod_fore_id"].eq(removed_node_id)
        self.assertTrue(scenario["avstand_efter_km"].ge(scenario["avstand_fore_km"]).all())
        self.assertTrue(scenario["paverkad"].eq(expected_affected).all())
        self.assertNotIn(removed_node_id, set(scenario["narmaste_nod_efter_id"]))
        self.assertGreater(
            int(scenario.loc[scenario["paverkad"], "befolkning_2025"].sum()),
            0,
        )

    def test_grid_accessibility_requires_ordered_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            calculate_grid_accessibility(
                self.population_grid,
                self.nodes,
                thresholds_km=(5, 4, 20, 30),
            )

    def test_multiple_nodes_can_be_removed_in_one_scenario(self) -> None:
        baseline = calculate_grid_accessibility(self.population_grid, self.nodes)
        removed_ids = tuple(
            baseline.groupby("narmaste_nod_fore_id")["befolkning_2025"]
            .sum().nlargest(2).index.astype(int)
        )
        scenario = calculate_grid_accessibility(
            self.population_grid, self.nodes, removed_node_ids=removed_ids
        )
        expected_affected = baseline["narmaste_nod_fore_id"].isin(removed_ids)
        self.assertTrue(scenario["paverkad"].eq(expected_affected).all())
        self.assertFalse(set(removed_ids) & set(scenario["narmaste_nod_efter_id"]))
        self.assertTrue(
            scenario["avstand_efter_km"].ge(scenario["avstand_fore_km"]).all()
        )

    def test_grid_scenario_aggregates_once_to_deso(self) -> None:
        baseline = calculate_grid_accessibility(self.population_grid, self.nodes)
        summary = aggregate_grid_accessibility_to_deso(
            baseline, self.deso_population
        )
        self.assertEqual(len(summary), 175)
        self.assertEqual(int(summary["rutbefolkning_2025"].sum()), 285_587)
        self.assertEqual(int(summary["befolkade_rutor"].sum()), 4_004)
        self.assertEqual(int(summary["berord_befolkning"].sum()), 0)

        removed_node_id = int(
            baseline.groupby("narmaste_nod_fore_id")["befolkning_2025"].sum().idxmax()
        )
        scenario = calculate_grid_accessibility(
            self.population_grid, self.nodes, removed_node_id=removed_node_id
        )
        scenario_summary = aggregate_grid_accessibility_to_deso(
            scenario, self.deso_population
        )
        expected = int(scenario.loc[scenario["paverkad"], "befolkning_2025"].sum())
        self.assertEqual(int(scenario_summary["berord_befolkning"].sum()), expected)
        self.assertEqual(
            int(scenario_summary["berort_deso"].sum()),
            int(scenario.loc[scenario["paverkad"], "desokod"].nunique()),
        )

    def test_grid_service_options_are_ordered_and_actor_distinct(self) -> None:
        options = calculate_grid_service_options(self.population_grid, self.nodes)
        self.assertEqual(len(options), 4_004)
        self.assertTrue(
            options["avstand_andra_nod_km"]
            .ge(options["avstand_forsta_nod_km"])
            .all()
        )
        self.assertTrue(
            options["avstand_alternativ_aktor_km"]
            .ge(options["avstand_forsta_nod_km"])
            .all()
        )
        self.assertFalse(options["forsta_nod_id"].eq(options["andra_nod_id"]).any())
        self.assertFalse(options["alternativ_aktor_nod_id"].isna().any())
        self.assertTrue(options["nya_aktorer_vid_alternativ"].str.len().gt(0).all())

    def test_grid_service_options_aggregate_population_once(self) -> None:
        grid = self.population_grid.copy()
        municipality_names = {
            "2021": "Vansbro", "2023": "Malung-Sälen", "2026": "Gagnef",
            "2029": "Leksand", "2031": "Rättvik", "2034": "Orsa",
            "2039": "Älvdalen", "2061": "Smedjebacken", "2062": "Mora",
            "2080": "Falun", "2081": "Borlänge", "2082": "Säter",
            "2083": "Hedemora", "2084": "Avesta", "2085": "Ludvika",
        }
        grid["kommun"] = grid["kommunkod"].map(municipality_names)
        options = calculate_grid_service_options(grid, self.nodes)
        summary = aggregate_grid_service_options_by_municipality(options)
        self.assertEqual(len(summary), 15)
        self.assertEqual(int(summary["befolkning_2025"].sum()), 285_587)
        self.assertEqual(int(summary["befolkade_rutor"].sum()), 4_004)
        for column in [
            "screening_forsta_nod",
            "screening_andra_nod",
            "screening_alternativ_aktor",
            "screening_redundansgap",
        ]:
            self.assertTrue(summary[column].between(0, 100).all())


if __name__ == "__main__":
    unittest.main()
