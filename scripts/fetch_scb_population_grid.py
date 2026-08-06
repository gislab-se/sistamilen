"""Hämta SCB:s öppna befolkning på 1 km-rutor för Dalarna.

Råuttaget sparas oförändrat. Bearbetade filer innehåller endast befolkade
rutor vars mittpunkt ligger i ett DeSO i Dalarnas län. Kommunanknytningen är
därmed en transparent mittpunktsklassning, inte en exakt fördelning av
befolkning i rutor som korsar en kommungräns.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pandas as pd
from pyproj import Transformer

from fetch_scb_deso import fetch_bytes, point_in_geometry, transform_coordinates


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DIR = ROOT / "data" / "external" / "scb"
DERIVED_DIR = ROOT / "data" / "derived"
DESO_SOURCE_PATH = EXTERNAL_DIR / "deso_2025_dalarna_raw.geojson"

WFS_BASE_URL = "https://geodata.scb.se/geoserver/stat/wfs"
LAYER = "stat:befolkning_1km_2025"
OLDER_COLUMNS = [
    "ald65_69",
    "ald70_74",
    "ald75_79",
    "ald80_84",
    "ald85_89",
    "ald90_94",
    "ald95_99",
    "ald100w",
]


def collect_coordinate_pairs(value: Any, target: list[list[float]]) -> None:
    """Samla koordinatpar ur godtyckligt nästlade GeoJSON-koordinater."""
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        target.append(value)
        return
    for item in value:
        collect_coordinate_pairs(item, target)


def geometry_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    pairs: list[list[float]] = []
    collect_coordinate_pairs(geometry["coordinates"], pairs)
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    return min(xs), min(ys), max(xs), max(ys)


def feature_centroid(feature: dict[str, Any]) -> tuple[float, float]:
    """Returnera rutans centrum från dess plana SWEREF-utbredning."""
    min_x, min_y, max_x, max_y = geometry_bounds(feature["geometry"])
    return (min_x + max_x) / 2, (min_y + max_y) / 2


def index_deso(features: list[dict[str, Any]]) -> list[tuple[str, str, Any, Any]]:
    return [
        (
            str(feature["properties"]["desokod"]),
            str(feature["properties"]["kommunkod"]),
            feature["geometry"],
            geometry_bounds(feature["geometry"]),
        )
        for feature in features
    ]


def main() -> None:
    if not DESO_SOURCE_PATH.exists():
        raise FileNotFoundError(
            "DeSO-rådata saknas. Kör scripts/fetch_scb_deso.py först."
        )

    with DESO_SOURCE_PATH.open(encoding="utf-8") as file:
        deso_source = json.load(file)
    deso_features = deso_source["features"]
    deso_index = index_deso(deso_features)
    min_x = min(item[3][0] for item in deso_index)
    min_y = min(item[3][1] for item in deso_index)
    max_x = max(item[3][2] for item in deso_index)
    max_y = max(item[3][3] for item in deso_index)

    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": LAYER,
        "outputFormat": "application/json",
        "srsName": "EPSG:3006",
        "bbox": f"{min_x},{min_y},{max_x},{max_y},EPSG:3006",
    }
    source_url = f"{WFS_BASE_URL}?{urlencode(params)}"
    raw_geojson = fetch_bytes(source_url)
    source = json.loads(raw_geojson.decode("utf-8-sig"))

    transformer = Transformer.from_crs(3006, 4326, always_xy=True)
    records: list[dict[str, Any]] = []
    derived_features: list[dict[str, Any]] = []
    unmatched = 0

    for feature in source.get("features", []):
        properties = feature["properties"]
        population = int(properties.get("beftotalt") or 0)
        if population <= 0:
            continue
        center_e, center_n = feature_centroid(feature)
        matches = [
            (deso_code, municipality_code)
            for deso_code, municipality_code, geometry, bounds in deso_index
            if bounds[0] <= center_e <= bounds[2]
            and bounds[1] <= center_n <= bounds[3]
            and point_in_geometry(center_e, center_n, geometry)
        ]
        if len(matches) != 1:
            unmatched += 1
            continue

        deso_code, municipality_code = matches[0]
        lon, lat = transformer.transform(center_e, center_n)
        older_population = sum(int(properties.get(column) or 0) for column in OLDER_COLUMNS)
        grid_id = str(properties.get("rutid_scb") or properties.get("rutid_inspire"))
        record = {
            "rutid": grid_id,
            "desokod": deso_code,
            "kommunkod": municipality_code,
            "e": round(center_e, 3),
            "n": round(center_n, 3),
            "lon": round(float(lon), 7),
            "lat": round(float(lat), 7),
            "befolkning_2025": population,
            "befolkning_65_plus_2025": older_population,
        }
        records.append(record)
        feature_properties = dict(record)
        feature_properties["referenstid"] = properties.get("referenstid")
        derived_features.append(
            {
                "type": "Feature",
                "id": grid_id,
                "properties": feature_properties,
                "geometry": {
                    "type": feature["geometry"]["type"],
                    "coordinates": transform_coordinates(
                        feature["geometry"]["coordinates"], transformer
                    ),
                },
            }
        )

    if not records:
        raise ValueError("SCB-uttaget gav inga befolkade rutor i Dalarna.")

    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    (EXTERNAL_DIR / "befolkning_1km_2025_dalarna_bbox_raw.geojson").write_bytes(
        raw_geojson
    )
    pd.DataFrame(records).sort_values("rutid").to_csv(
        DERIVED_DIR / "befolkning_1km_2025_dalarna.csv",
        index=False,
        encoding="utf-8-sig",
    )
    derived_geojson = {
        "type": "FeatureCollection",
        "name": "Befolkning_1km_2025_Dalarna",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": derived_features,
    }
    (DERIVED_DIR / "befolkning_1km_2025_dalarna.geojson").write_text(
        json.dumps(derived_geojson, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    metadata = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "SCB Statistik på rutor, WFS",
        "source_url": source_url,
        "layer": LAYER,
        "reference_year": 2025,
        "source_crs": "EPSG:3006",
        "derived_crs": "EPSG:4326",
        "selection": (
            "Befolkade 1 km-rutor vars mittpunkt ligger i DeSO 2025 för "
            "Dalarnas län."
        ),
        "feature_count": len(records),
        "population_total": sum(row["befolkning_2025"] for row in records),
        "population_65_plus_sum": sum(
            row["befolkning_65_plus_2025"] for row in records
        ),
        "unmatched_populated_bbox_cells": unmatched,
        "privacy_note": (
            "SCB använder statistiskt röjandeskydd. Summerade delgrupper kan "
            "därför avvika från redovisad totalbefolkning."
        ),
    }
    (EXTERNAL_DIR / "population_grid_source_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"Sparade {len(records)} befolkade 1 km-rutor med "
        f"{metadata['population_total']} invånare."
    )
    print(f"Befolkade bbox-rutor utan entydig mittpunktsmatch: {unmatched}.")


if __name__ == "__main__":
    main()
