"""Hämta SCB:s senaste publicerade platsområden för Dalarnas län.

Skriptet hämtar tre små GeoJSON-uttag från SCB:s officiella WFS:

* statistiska tätorter 2023,
* statistiska småorter 2023,
* statistiska fritidshusområden 2020.

Råuttagen bevaras oförändrade i ``data/external/scb``. Geometrierna
transformeras från SWEREF 99 TM (EPSG:3006) till WGS84 (EPSG:4326) och
skrivs till en gemensam, normaliserad GeoJSON i ``data/derived``.

SCB:s fält ``smaort`` och ``fritidshus`` är områdeskoder. De får därför
aldrig tolkas som namn respektive antal fritidshus.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pyproj import Transformer


ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DIR = ROOT / "data" / "external" / "scb"
DERIVED_DIR = ROOT / "data" / "derived"

WFS_BASE_URL = "https://geodata.scb.se/geoserver/stat/wfs"
WFS_CAPABILITIES_URL = (
    f"{WFS_BASE_URL}?service=WFS&version=1.1.0&request=GetCapabilities"
)
DERIVED_PATH = DERIVED_DIR / "scb_platsomraden_dalarna.geojson"
METADATA_PATH = EXTERNAL_DIR / "place_areas_source_metadata.json"


@dataclass(frozen=True)
class LayerSpec:
    """Konfiguration och kontrakt för ett SCB-lager."""

    layer: str
    area_type: str
    reference_year: int
    code_field: str
    name_field: str | None
    expected_count: int
    raw_filename: str


LAYERS = (
    LayerSpec(
        layer="stat:Tatorter_2023",
        area_type="Tätort",
        reference_year=2023,
        code_field="tatortskod",
        name_field="tatort",
        expected_count=114,
        raw_filename="tatorter_2023_dalarna_raw.geojson",
    ),
    LayerSpec(
        layer="stat:Smaorter_2023",
        area_type="Småort",
        reference_year=2023,
        code_field="smaort",
        name_field=None,
        expected_count=181,
        raw_filename="smaorter_2023_dalarna_raw.geojson",
    ),
    LayerSpec(
        layer="stat:Fritidshusomraden_2020",
        area_type="Fritidshusområde",
        reference_year=2020,
        code_field="fritidshus",
        name_field=None,
        expected_count=74,
        raw_filename="fritidshusomraden_2020_dalarna_raw.geojson",
    ),
)


def build_wfs_url(layer: str) -> str:
    """Bygg ett avgränsat WFS-anrop för Dalarnas län, i EPSG:3006."""
    params = {
        "service": "WFS",
        "version": "1.1.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "application/json",
        "srsName": "EPSG:3006",
        "CQL_FILTER": "lan='20'",
    }
    return f"{WFS_BASE_URL}?{urlencode(params)}"


def fetch_bytes(url: str) -> bytes:
    """Hämta en fast SCB-URL med timeout och identifierad klient."""
    request = Request(
        url,
        headers={
            "Accept": "application/geo+json, application/json",
            "User-Agent": "Region-Dalarna-paketleveranser-fas1/0.1",
        },
    )
    with urlopen(request, timeout=90) as response:  # noqa: S310 - fast SCB-URL
        return response.read()


def decode_geojson(raw: bytes, spec: LayerSpec) -> dict[str, Any]:
    """Avkoda och kontraktskontrollera ett WFS-svar."""
    payload = json.loads(raw.decode("utf-8-sig"))
    if payload.get("type") != "FeatureCollection":
        raise ValueError(f"{spec.layer} gav inte en GeoJSON FeatureCollection.")

    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError(f"{spec.layer} saknar en giltig feature-lista.")
    if len(features) != spec.expected_count:
        raise ValueError(
            f"{spec.layer}: förväntade {spec.expected_count} objekt i Dalarna, "
            f"fick {len(features)}. Kontrollera SCB:s aktuella årgång."
        )

    codes: list[str] = []
    for feature in features:
        properties = feature.get("properties") or {}
        if str(properties.get("lan", "")) != "20":
            raise ValueError(f"{spec.layer} innehåller objekt utanför län 20.")
        code = str(properties.get(spec.code_field, "")).strip()
        if not code:
            raise ValueError(
                f"{spec.layer} innehåller objekt utan {spec.code_field}."
            )
        codes.append(code)
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(
                f"{spec.layer} innehåller oväntad geometri: "
                f"{geometry.get('type')!r}."
            )

    if len(codes) != len(set(codes)):
        raise ValueError(f"{spec.layer} innehåller duplicerade områdeskoder.")
    return payload


def transform_coordinates(value: Any, transformer: Transformer) -> Any:
    """Transformera godtyckligt nästlade GeoJSON-koordinater."""
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        lon, lat = transformer.transform(value[0], value[1])
        return [round(float(lon), 7), round(float(lat), 7), *value[2:]]
    if isinstance(value, list):
        return [transform_coordinates(item, transformer) for item in value]
    raise ValueError("Oväntad koordinatstruktur i GeoJSON-geometrin.")


def iter_coordinate_pairs(value: Any):
    """Iterera över alla koordinatpar i en nästlad GeoJSON-geometri."""
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        yield float(value[0]), float(value[1])
        return
    if isinstance(value, list):
        for item in value:
            yield from iter_coordinate_pairs(item)


def text_or_empty(value: Any) -> str:
    """Normalisera saknad text till en uttrycklig tom sträng."""
    if value is None:
        return ""
    return str(value).strip()


def normalise_feature(
    feature: dict[str, Any], spec: LayerSpec, transformer: Transformer
) -> dict[str, Any]:
    """Skapa en gemensam feature utan att hitta på namn eller antal."""
    source = feature["properties"]
    name = text_or_empty(source.get(spec.name_field)) if spec.name_field else ""
    properties = {
        "omradestyp": spec.area_type,
        "referensar": spec.reference_year,
        "omradeskod": text_or_empty(source.get(spec.code_field)),
        "namn": name,
        "kommunkod": text_or_empty(source.get("kommun")),
        "kommunnamn": text_or_empty(source.get("kommunnamn")),
        "area_ha": source.get("area_ha"),
        "kallager": spec.layer,
    }
    geometry = feature["geometry"]
    return {
        "type": "Feature",
        "id": feature.get("id", properties["omradeskod"]),
        "properties": properties,
        "geometry": {
            "type": geometry["type"],
            "coordinates": transform_coordinates(
                geometry["coordinates"], transformer
            ),
        },
    }


def sha256_bytes(value: bytes) -> str:
    """Beräkna kontrollsumma för reproducerbar källdokumentation."""
    return hashlib.sha256(value).hexdigest()


def distinct_property_values(
    payload: dict[str, Any], property_name: str
) -> list[str]:
    """Returnera sorterade, icke-tomma värden för ett källfält."""
    values = {
        text_or_empty(feature.get("properties", {}).get(property_name))
        for feature in payload["features"]
    }
    return sorted(value for value in values if value)


def validate_derived(features: list[dict[str, Any]]) -> None:
    """Verifiera totalantal, egenskaper och rimliga WGS84-koordinater."""
    expected_total = sum(spec.expected_count for spec in LAYERS)
    if len(features) != expected_total:
        raise ValueError(
            f"Förväntade {expected_total} kombinerade objekt, fick {len(features)}."
        )

    required = {"omradestyp", "referensar", "omradeskod", "namn"}
    for feature in features:
        properties = feature.get("properties", {})
        if not required.issubset(properties):
            raise ValueError("Kombinerad feature saknar obligatoriska properties.")
        if not isinstance(properties["namn"], str):
            raise ValueError("Propertyn namn ska alltid vara en sträng.")
        if not properties["omradeskod"]:
            raise ValueError("Kombinerad feature saknar områdeskod.")
        for lon, lat in iter_coordinate_pairs(feature["geometry"]["coordinates"]):
            if not 10.0 < lon < 18.5 or not 59.0 < lat < 63.5:
                raise ValueError(
                    f"Koordinat utanför rimlig Dalarna-utbredning: {lon}, {lat}."
                )


def main() -> None:
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    fetched: list[tuple[LayerSpec, str, bytes, dict[str, Any]]] = []
    for spec in LAYERS:
        url = build_wfs_url(spec.layer)
        raw = fetch_bytes(url)
        payload = decode_geojson(raw, spec)
        fetched.append((spec, url, raw, payload))

    transformer = Transformer.from_crs(3006, 4326, always_xy=True)
    derived_features = [
        normalise_feature(feature, spec, transformer)
        for spec, _, _, payload in fetched
        for feature in payload["features"]
    ]
    validate_derived(derived_features)

    derived_geojson = {
        "type": "FeatureCollection",
        "name": "SCB_platsomraden_Dalarna",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": derived_features,
    }
    derived_raw = json.dumps(
        derived_geojson,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    # Skriv först när samtliga hämtningar och kontroller har passerat.
    for spec, _, raw, _ in fetched:
        (EXTERNAL_DIR / spec.raw_filename).write_bytes(raw)
    DERIVED_PATH.write_bytes(derived_raw)

    metadata_layers = []
    for spec, url, raw, payload in fetched:
        metadata_layers.append(
            {
                "layer": spec.layer,
                "omradestyp": spec.area_type,
                "reference_year": spec.reference_year,
                "url": url,
                "raw_file": (EXTERNAL_DIR / spec.raw_filename)
                .relative_to(ROOT)
                .as_posix(),
                "raw_sha256": sha256_bytes(raw),
                "source_crs": "EPSG:3006",
                "feature_count": len(payload["features"]),
                "source_code_field": spec.code_field,
                "source_name_field": spec.name_field,
                "valid_from_values": distinct_property_values(
                    payload, "validfrom"
                ),
                "valid_to_values": distinct_property_values(payload, "validto"),
            }
        )

    metadata = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Statistiska centralbyrån (SCB), öppna geodata via WFS",
        "source_page": (
            "https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/"
        ),
        "wfs_capabilities_url": WFS_CAPABILITIES_URL,
        "scope": "Dalarnas län (länskod 20)",
        "license": "Creative Commons CC0 1.0 Universal",
        "license_terms": (
            "https://www.scb.se/om-scb/om-scb.se-och-anvandningsvillkor"
        ),
        "layers": metadata_layers,
        "derived": {
            "file": DERIVED_PATH.relative_to(ROOT).as_posix(),
            "crs": "EPSG:4326",
            "feature_count": len(derived_features),
            "sha256": sha256_bytes(derived_raw),
            "properties": [
                "omradestyp",
                "referensar",
                "omradeskod",
                "namn",
                "kommunkod",
                "kommunnamn",
                "area_ha",
                "kallager",
            ],
        },
        "interpretation_notes": [
            "smaort är en områdeskod; WFS-lagret saknar småortsnamn.",
            "fritidshus är en områdeskod, inte antal fritidshus.",
            "namn är därför tomt för småorter och fritidshusområden.",
            "Inga syntetiska eller feltolkade antal har lagts till.",
        ],
        "metadata_note": (
            "Denna separata fil kompletterar source_metadata.json och ändrar "
            "inte metadata för DeSO-uttaget."
        ),
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    counts = ", ".join(
        f"{spec.area_type}={len(payload['features'])}"
        for spec, _, _, payload in fetched
    )
    print(f"Verifierade SCB-objekt i Dalarna: {counts}.")
    print(f"Skrev {len(derived_features)} objekt till {DERIVED_PATH}.")
    print(f"Källmetadata: {METADATA_PATH}.")


if __name__ == "__main__":
    main()
