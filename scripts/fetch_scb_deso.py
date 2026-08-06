"""Hämta och bearbeta officiell DeSO-geografi och befolkning för Dalarna.

Skriptet gör två små, reproducerbara uttag från SCB:

* DeSO 2025-gränser för län 20 via SCB:s WFS.
* Folkmängd 2024, totalt och 65+, via Statistikdatabasens API v2.

Råuttagen sparas oförändrade i ``data/external/scb``. En WGS84-GeoJSON,
en befolkningstabell och en nod–DeSO-korsning skrivs till ``data/derived``.
Ingen extern hämtning görs när Streamlit-appen startar.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard_data import build_service_nodes, load_dashboard_data  # noqa: E402


EXTERNAL_DIR = ROOT / "data" / "external" / "scb"
DERIVED_DIR = ROOT / "data" / "derived"

WFS_BASE_URL = "https://geodata.scb.se/geoserver/stat/wfs"
WFS_PARAMS = {
    "service": "WFS",
    "version": "1.1.0",
    "request": "GetFeature",
    "typeName": "stat:DeSO_2025",
    "outputFormat": "application/json",
    "CQL_FILTER": "lanskod='20'",
}
WFS_URL = f"{WFS_BASE_URL}?{urlencode(WFS_PARAMS)}"

POPULATION_BASE_URL = (
    "https://statistikdatabasen.scb.se/api/v2/tables/TAB6574/data"
)
POPULATION_PARAMS = [
    ("lang", "sv"),
    ("valueCodes[Region]", "20*"),
    ("codelist[Region]", "vs_DeSO2025"),
    ("valueCodes[Alder]", "totalt,65-69,70-74,75-79,80-"),
    ("valueCodes[Kon]", "1+2"),
    ("valueCodes[ContentsCode]", "000007Y7"),
    ("valueCodes[Tid]", "2024"),
    ("outputFormat", "csv"),
]
POPULATION_URL = f"{POPULATION_BASE_URL}?{urlencode(POPULATION_PARAMS)}"


def fetch_bytes(url: str) -> bytes:
    """Hämta en URL med tydlig klientidentifiering och timeout."""
    request = Request(
        url,
        headers={"User-Agent": "Region-Dalarna-paketleveranser-fas1/0.1"},
    )
    with urlopen(request, timeout=90) as response:  # noqa: S310 - fasta SCB-URL:er
        return response.read()


def transform_coordinates(value: Any, transformer: Transformer) -> Any:
    """Transformera valfritt nästlade GeoJSON-koordinater."""
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        lon, lat = transformer.transform(value[0], value[1])
        return [round(float(lon), 7), round(float(lat), 7), *value[2:]]
    return [transform_coordinates(item, transformer) for item in value]


def ring_area(ring: list[list[float]]) -> float:
    """Beräkna en rings plana area med shoelace-formeln."""
    return abs(
        sum(
            first[0] * second[1] - second[0] * first[1]
            for first, second in zip(ring, ring[1:] + ring[:1])
        )
    ) / 2


def geometry_area_km2(geometry: dict[str, Any]) -> float:
    """Beräkna polygonarea i km²; källgeometrin ligger i EPSG:3006."""
    coordinates = geometry["coordinates"]
    polygons = [coordinates] if geometry["type"] == "Polygon" else coordinates
    area_m2 = 0.0
    for polygon in polygons:
        if not polygon:
            continue
        area_m2 += ring_area(polygon[0])
        area_m2 -= sum(ring_area(hole) for hole in polygon[1:])
    return max(area_m2, 0.0) / 1_000_000


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    """Ray-casting-test för en punkt i en polygonring."""
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[:2]
        x2, y2 = current[:2]
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            boundary_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < boundary_x:
                inside = not inside
        previous = current
    return inside


def point_in_geometry(x: float, y: float, geometry: dict[str, Any]) -> bool:
    """Testa om SWEREF-punkten ligger i en Polygon eller MultiPolygon."""
    coordinates = geometry["coordinates"]
    polygons = [coordinates] if geometry["type"] == "Polygon" else coordinates
    for polygon in polygons:
        if polygon and point_in_ring(x, y, polygon[0]):
            if not any(point_in_ring(x, y, hole) for hole in polygon[1:]):
                return True
    return False


def parse_population(raw_csv: bytes) -> pd.DataFrame:
    """Normalisera SCB:s långa CSV till en rad per DeSO."""
    text = raw_csv.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    long = pd.DataFrame(rows).rename(
        columns={
            "Region": "region_api",
            "Alder": "alder",
            "Kon": "kon",
            "000007Y7 2024": "befolkning",
        }
    )
    required = {"region_api", "alder", "kon", "befolkning"}
    if not required.issubset(long.columns):
        raise ValueError(f"Oväntade kolumner från SCB: {list(long.columns)}")
    long["desokod"] = long["region_api"].str.replace(
        "_DeSO2025", "", regex=False
    )
    long["befolkning"] = pd.to_numeric(long["befolkning"], errors="raise")

    total = (
        long.loc[long["alder"].eq("totalt"), ["desokod", "befolkning"]]
        .rename(columns={"befolkning": "befolkning_2024"})
        .set_index("desokod")
    )
    older = (
        long.loc[long["alder"].ne("totalt")]
        .groupby("desokod")["befolkning"]
        .sum()
        .rename("befolkning_65_plus_2024")
    )
    population = total.join(older, how="left").reset_index()
    population["andel_65_plus_2024"] = (
        population["befolkning_65_plus_2024"]
        / population["befolkning_2024"]
    )
    return population.sort_values("desokod").reset_index(drop=True)


def assign_nodes_to_deso(
    nodes: pd.DataFrame, features: list[dict[str, Any]]
) -> pd.DataFrame:
    """Koppla varje servicenod till officiell DeSO-polygon i EPSG:3006."""
    indexed = []
    for feature in features:
        geometry = feature["geometry"]
        all_pairs: list[list[float]] = []

        def collect(value: Any) -> None:
            if (
                isinstance(value, list)
                and len(value) >= 2
                and isinstance(value[0], (int, float))
            ):
                all_pairs.append(value)
            else:
                for item in value:
                    collect(item)

        collect(geometry["coordinates"])
        xs = [pair[0] for pair in all_pairs]
        ys = [pair[1] for pair in all_pairs]
        indexed.append(
            (
                feature["properties"]["desokod"],
                geometry,
                (min(xs), min(ys), max(xs), max(ys)),
            )
        )

    assignments = []
    for node in nodes.itertuples(index=False):
        matches = [
            desokod
            for desokod, geometry, bounds in indexed
            if bounds[0] <= node.e <= bounds[2]
            and bounds[1] <= node.n <= bounds[3]
            and point_in_geometry(float(node.e), float(node.n), geometry)
        ]
        assignments.append(
            {
                "kluster_id": node.kluster_id,
                "uuidadrpl": node.uuidadrpl,
                "nodnamn": node.nodnamn,
                "kommun": node.kommun,
                "desokod": matches[0] if len(matches) == 1 else pd.NA,
                "antal_deso_traf": len(matches),
            }
        )
    return pd.DataFrame(assignments)


def main() -> None:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    raw_geojson = fetch_bytes(WFS_URL)
    raw_population = fetch_bytes(POPULATION_URL)
    source_geojson = json.loads(raw_geojson.decode("utf-8-sig"))
    population = parse_population(raw_population)

    features = source_geojson.get("features", [])
    if len(features) != 175:
        raise ValueError(f"Förväntade 175 DeSO i Dalarna, fick {len(features)}.")
    source_codes = {feature["properties"]["desokod"] for feature in features}
    population_codes = set(population["desokod"])
    if source_codes != population_codes:
        raise ValueError(
            "Geometri och befolkning har olika DeSO-koder: "
            f"{len(source_codes - population_codes)} utan befolkning, "
            f"{len(population_codes - source_codes)} utan geometri."
        )

    _, service, _, clusters, _ = load_dashboard_data(ROOT)
    nodes = build_service_nodes(service, clusters)
    node_deso = assign_nodes_to_deso(nodes, features)
    unmatched = int(node_deso["desokod"].isna().sum())
    if unmatched:
        raise ValueError(f"{unmatched} servicenoder kunde inte kopplas till ett DeSO.")

    node_counts = node_deso.groupby("desokod").size().rename("antal_servicenoder")
    population_index = population.set_index("desokod")
    transformer = Transformer.from_crs(3006, 4326, always_xy=True)
    derived_features = []
    area_records = []
    for feature in features:
        properties = dict(feature["properties"])
        desokod = properties["desokod"]
        stats = population_index.loc[desokod]
        area_km2 = geometry_area_km2(feature["geometry"])
        properties.update(
            {
                "befolkning_2024": int(stats["befolkning_2024"]),
                "befolkning_65_plus_2024": int(
                    stats["befolkning_65_plus_2024"]
                ),
                "andel_65_plus_2024": round(
                    float(stats["andel_65_plus_2024"]), 6
                ),
                "area_km2": round(area_km2, 3),
                "befolkning_per_km2_2024": round(
                    float(stats["befolkning_2024"]) / area_km2, 3
                )
                if area_km2
                else None,
                "antal_servicenoder": int(node_counts.get(desokod, 0)),
            }
        )
        area_records.append(
            {
                "desokod": desokod,
                "kommunkod": str(properties["kommunkod"]),
                "area_km2": properties["area_km2"],
                "befolkning_per_km2_2024": properties[
                    "befolkning_per_km2_2024"
                ],
                "antal_servicenoder": properties["antal_servicenoder"],
            }
        )
        derived_features.append(
            {
                "type": "Feature",
                "id": feature.get("id", desokod),
                "properties": properties,
                "geometry": {
                    "type": feature["geometry"]["type"],
                    "coordinates": transform_coordinates(
                        feature["geometry"]["coordinates"], transformer
                    ),
                },
            }
        )

    derived_geojson = {
        "type": "FeatureCollection",
        "name": "DeSO_2025_Dalarna_med_befolkning_2024",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": derived_features,
    }

    (EXTERNAL_DIR / "deso_2025_dalarna_raw.geojson").write_bytes(raw_geojson)
    (EXTERNAL_DIR / "folkmangd_deso_2024_raw.csv").write_bytes(raw_population)
    (DERIVED_DIR / "deso_2025_dalarna.geojson").write_text(
        json.dumps(derived_geojson, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    population_enriched = population.merge(
        pd.DataFrame(area_records), on="desokod", how="left", validate="1:1"
    )
    population_enriched.to_csv(
        DERIVED_DIR / "deso_befolkning_2024.csv",
        index=False,
        encoding="utf-8-sig",
    )
    node_deso.merge(
        population_enriched, on="desokod", how="left", validate="many_to_one"
    ).to_csv(
        DERIVED_DIR / "nod_deso_2025.csv",
        index=False,
        encoding="utf-8-sig",
    )

    metadata = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Dalarnas län (länskod 20)",
        "geometry": {
            "source": "SCB Geodata, WFS",
            "url": WFS_URL,
            "layer": "stat:DeSO_2025",
            "source_crs": "EPSG:3006",
            "derived_crs": "EPSG:4326",
            "feature_count": len(features),
        },
        "population": {
            "source": "SCB Statistikdatabasen, tabell TAB6574",
            "url": POPULATION_URL,
            "reference_date": "2024-12-31",
            "unit": "antal personer",
            "sex": "totalt (1+2)",
            "ages": ["totalt", "65-69", "70-74", "75-79", "80-"],
            "note": "65+ är summering av fyra publicerade åldersgrupper.",
        },
        "quality": {
            "node_count": len(nodes),
            "nodes_with_exactly_one_deso": int(
                node_deso["antal_deso_traf"].eq(1).sum()
            ),
            "unmatched_nodes": unmatched,
        },
    }
    (EXTERNAL_DIR / "source_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Hämtade {len(features)} DeSO och {len(population)} befolkningsrader.")
    print(f"Kopplade {len(nodes) - unmatched}/{len(nodes)} servicenoder till DeSO.")
    print("Skrev data/external/scb och tre bearbetade filer i data/derived.")


if __name__ == "__main__":
    main()
