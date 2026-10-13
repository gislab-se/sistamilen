"""Build a standalone screening map from DVA's public 2026 collection schedule.

The generated map is deliberately a screening artefact.  Public tract tables do
not contain route geometry, stop order, exact collection points, or arrival
times.  The map therefore renders one geocoded anchor per tract and never calls
that anchor a route.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "prototypes" / "dva_transportnarvaro"
RAW_HTML = OUTPUT_DIR / "source" / "sophamtningsschema_2026.html"
GEOCODE_CACHE = OUTPUT_DIR / "source" / "tract_anchor_geocodes.json"
TRACT_CSV = OUTPUT_DIR / "data" / "dva_trakter_2026.csv"
SCHEDULE_CSV = OUTPUT_DIR / "data" / "dva_schema_2026.csv"
MAP_HTML = OUTPUT_DIR / "index.html"
VENDOR_DIR = OUTPUT_DIR / "vendor"
SOURCE_URL = (
    "https://www.dalavattenavfall.se/avfall-och-atervinning/"
    "sophamtningsschema.html"
)
SERVICE_NODE_CSV = ROOT / "data" / "derived" / "servicenoder_2026.csv"
LEAFLET_ASSETS = {
    "leaflet.css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "leaflet.js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "LICENSE": "https://unpkg.com/leaflet@1.9.4/LICENSE",
    "images/layers.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png",
    "images/layers-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png",
    "images/marker-icon.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    "images/marker-icon-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    "images/marker-shadow.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
}

MUNICIPALITIES = ["Gagnef", "Leksand", "Rättvik", "Vansbro"]
WASTE_TYPES = ["Matavfall", "Restavfall", "Plastförpackningar", "Pappersförpackningar"]
MONTHS = {
    "januari": 1,
    "februari": 2,
    "jebruari": 2,  # source typo; retained as a quality flag
    "mars": 3,
    "april": 4,
    "maj": 5,
    "juni": 6,
    "juli": 7,
    "augusti": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}
WEEKDAYS = {
    "måndag": 0,
    "tisdag": 1,
    "onsdag": 2,
    "torsdag": 3,
    "fredag": 4,
}
DAY_LABELS = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
ANCHOR_OVERRIDES = {
    # The source's first label is either a neighbourhood, a compound label, or
    # not independently indexed by the geocoder.  Use a named place from the
    # same published tract description as the tract-level screening anchor.
    "gagnef-2": "Björbo",
    "gagnef-5": "Björka",
    "leksand-1": "Insjön",
    "rattvik-2": "Vikarbyn",
    "rattvik-4": "Rättvik",
}


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u00ad", "")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{2,}", "\n", value)
    return value.strip()


class TableParser(HTMLParser):
    """Extract visible cell text from the four schedule tables."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
        elif self._table_depth == 1 and tag == "tr":
            self._current_row = []
        elif self._table_depth == 1 and tag in {"th", "td"}:
            self._current_cell = []
        elif self._current_cell is not None and tag in {"br", "p", "div", "li"}:
            self._current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._table_depth == 1 and tag in {"th", "td"} and self._current_cell is not None:
            assert self._current_row is not None
            self._current_row.append(clean_text("".join(self._current_cell)))
            self._current_cell = None
        elif self._table_depth == 1 and tag == "tr" and self._current_row is not None:
            if any(self._current_row):
                assert self._current_table is not None
                self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            self._table_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)


def fetch_source() -> str:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": (
                "Region-Dalarna-package-delivery-screening/0.1 "
                "(public research prototype)"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")


def source_html(*, refresh: bool) -> str:
    if refresh or not RAW_HTML.exists():
        content = fetch_source()
        RAW_HTML.parent.mkdir(parents=True, exist_ok=True)
        RAW_HTML.write_text(content, encoding="utf-8")
        return content
    return RAW_HTML.read_text(encoding="utf-8")


def ensure_leaflet_assets(*, refresh: bool = False) -> None:
    """Cache Leaflet locally so opening the HTML does not depend on a CDN."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in LEAFLET_ASSETS.items():
        target = VENDOR_DIR / filename
        if target.exists() and not refresh:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Region-Dalarna-package-delivery-screening/0.1"},
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            content = response.read()
        if len(content) < 500:
            raise ValueError(f"Downloaded Leaflet asset is unexpectedly short: {url}")
        target.write_bytes(content)


def parse_dates(text: str) -> tuple[list[str], list[str]]:
    dates: list[str] = []
    flags: list[str] = []
    for day_text, month_text in re.findall(
        r"\b(\d{1,2})\s+(januari|februari|jebruari|mars|april|maj|juni|juli|"
        r"augusti|september|oktober|november|december)\b",
        text.lower(),
    ):
        if month_text == "jebruari":
            flags.append("källstavning:jebruari")
        try:
            parsed = date(2026, MONTHS[month_text], int(day_text))
        except ValueError:
            flags.append(f"ogiltigt_datum:{day_text}_{month_text}")
            continue
        dates.append(parsed.isoformat())
    return dates, flags


def parse_tract_cell(text: str) -> dict[str, Any]:
    compact = clean_text(text)
    tract_match = re.search(r"^\s*(\d{1,2})\b", compact)
    day_match = re.search(
        r"\b(Måndag(?:ar)?|Tisdag(?:ar)?|Onsdag(?:ar)?|Torsdag(?:ar)?|Fredag(?:ar)?)\b",
        compact,
        re.IGNORECASE,
    )
    parity_match = re.search(
        r"\b(Jämna|Udda)\s+veck(?:a|an|or)\b", compact, re.IGNORECASE
    )
    if not (tract_match and day_match and parity_match):
        raise ValueError(f"Could not parse tract header: {compact[:160]!r}")

    weekday_key = day_match.group(1).lower().removesuffix("ar")
    places = compact[parity_match.end() :].strip(" \n,|")
    return {
        "tract": int(tract_match.group(1)),
        "weekday": DAY_LABELS[WEEKDAYS[weekday_key]],
        "weekday_number": WEEKDAYS[weekday_key],
        "week_parity": parity_match.group(1).capitalize(),
        "places": re.sub(r"\s*\n\s*", " ", places).strip(),
    }


def parse_schedule(content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parser = TableParser()
    parser.feed(content)
    if len(parser.tables) != 4:
        raise ValueError(f"Expected four municipal schedule tables, found {len(parser.tables)}")

    tracts: list[dict[str, Any]] = []
    schedule: list[dict[str, Any]] = []
    for municipality, table in zip(MUNICIPALITIES, parser.tables, strict=True):
        tract_rows = [row for row in table if row and re.match(r"^\s*\d{1,2}\b", row[0])]
        for row in tract_rows:
            if len(row) < 5:
                raise ValueError(
                    f"{municipality}: tract row has {len(row)} cells instead of at least five"
                )
            tract = parse_tract_cell(row[0])
            tract_id = f"{municipality.lower().replace('ä', 'a').replace('ö', 'o')}-{tract['tract']}"
            quality_flags: set[str] = set()
            tract_dates: dict[str, list[str]] = {}
            for waste_type, cell in zip(WASTE_TYPES, row[1:5], strict=True):
                parsed_dates, flags = parse_dates(cell)
                quality_flags.update(flags)
                tract_dates[waste_type] = parsed_dates
                for iso_date in parsed_dates:
                    event_date = date.fromisoformat(iso_date)
                    event_flags = list(flags)
                    if event_date.weekday() != tract["weekday_number"]:
                        event_flags.append("datum_avviker_från_angiven_veckodag")
                        quality_flags.add("datum_avviker_från_angiven_veckodag")
                    schedule.append(
                        {
                            "tract_id": tract_id,
                            "municipality": municipality,
                            "tract": tract["tract"],
                            "waste_type": waste_type,
                            "date": iso_date,
                            "source_flags": ";".join(sorted(set(event_flags))),
                        }
                    )
            tracts.append(
                {
                    "tract_id": tract_id,
                    "municipality": municipality,
                    **tract,
                    "dates": tract_dates,
                    "source_flags": sorted(quality_flags),
                }
            )

    expected_counts = {"Gagnef": 10, "Leksand": 10, "Rättvik": 8, "Vansbro": 7}
    actual_counts = {
        municipality: sum(t["municipality"] == municipality for t in tracts)
        for municipality in MUNICIPALITIES
    }
    if actual_counts != expected_counts:
        raise ValueError(f"Unexpected tract counts: {actual_counts}; expected {expected_counts}")
    return tracts, schedule


def anchor_candidate(places: str) -> str:
    """Choose a conservative first named place for tract-level anchoring."""
    candidates = [clean_text(part).strip(" .,|") for part in places.split(",")]
    candidates = [candidate for candidate in candidates if len(candidate) >= 2]
    if not candidates:
        raise ValueError(f"No place candidate in {places!r}")
    first = candidates[0]
    first = re.sub(r"\s+(?:N|S|Ö|V)\s+om\b.*$", "", first, flags=re.IGNORECASE)
    return first.strip()


def load_geocode_cache() -> dict[str, Any]:
    if not GEOCODE_CACHE.exists():
        return {}
    return json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))


def geocode_tract_anchors(tracts: list[dict[str, Any]], *, refresh: bool) -> None:
    cache = load_geocode_cache()
    changed = False
    for index, tract in enumerate(tracts, start=1):
        tract_id = tract["tract_id"]
        query_place = ANCHOR_OVERRIDES.get(tract_id, anchor_candidate(tract["places"]))
        query = f"{query_place}, {tract['municipality']} kommun, Sverige"
        cached = cache.get(tract_id)
        if cached and not refresh and cached.get("query") == query:
            tract["anchor"] = cached
            continue

        params = urllib.parse.urlencode(
            {
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "se",
            }
        )
        request = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/search?{params}",
            headers={
                "User-Agent": (
                    "Region-Dalarna-package-delivery-screening/0.1 "
                    "(public research prototype)"
                )
            },
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            results = json.loads(response.read().decode("utf-8"))
        if results:
            result = results[0]
            cached = {
                "query": query,
                "query_place": query_place,
                "lat": float(result["lat"]),
                "lon": float(result["lon"]),
                "display_name": result.get("display_name", ""),
                "provider": "OpenStreetMap Nominatim",
            }
        else:
            cached = {
                "query": query,
                "query_place": query_place,
                "lat": None,
                "lon": None,
                "display_name": "",
                "provider": "OpenStreetMap Nominatim",
            }
        cache[tract_id] = cached
        tract["anchor"] = cached
        changed = True
        print(f"Geocoded {index:02d}/{len(tracts)}: {tract_id} -> {cached['lat']}, {cached['lon']}")
        time.sleep(1.05)

    if changed:
        GEOCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        GEOCODE_CACHE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def read_service_nodes() -> list[dict[str, Any]]:
    municipality_prefixes = ("Gagnef", "Leksand", "R", "Vansbro")
    nodes: list[dict[str, Any]] = []
    with SERVICE_NODE_CSV.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            municipality = row["kommun"]
            # Rättvik is matched by prefix to avoid a host-shell encoding edge case.
            if not municipality.startswith(municipality_prefixes):
                continue
            nodes.append(
                {
                    "id": row["kluster_id"],
                    "name": row["nodnamn"],
                    "address": f"{row['adress']}, {row['postort']}",
                    "municipality": municipality,
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "operators": row["aktorer"],
                    "service_types": row["servicetyper"],
                    "operator_count": int(float(row["antal_aktorer"])),
                    "one_operator": row["en_aktor"].lower() == "true",
                    "median_delivery_days": (
                        float(row["median_leveransdagar_per_vecka"])
                        if row["median_leveransdagar_per_vecka"]
                        else None
                    ),
                }
            )
    return nodes


def write_csv_outputs(tracts: list[dict[str, Any]], schedule: list[dict[str, Any]]) -> None:
    TRACT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with TRACT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "tract_id",
            "municipality",
            "tract",
            "weekday",
            "week_parity",
            "places",
            "anchor_place",
            "anchor_lat",
            "anchor_lon",
            "source_flags",
            "source_url",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for tract in tracts:
            anchor = tract.get("anchor", {})
            writer.writerow(
                {
                    "tract_id": tract["tract_id"],
                    "municipality": tract["municipality"],
                    "tract": tract["tract"],
                    "weekday": tract["weekday"],
                    "week_parity": tract["week_parity"],
                    "places": tract["places"],
                    "anchor_place": anchor.get("query_place", ""),
                    "anchor_lat": anchor.get("lat", ""),
                    "anchor_lon": anchor.get("lon", ""),
                    "source_flags": ";".join(tract["source_flags"]),
                    "source_url": SOURCE_URL,
                }
            )
    with SCHEDULE_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["tract_id", "municipality", "tract", "waste_type", "date", "source_flags"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(schedule)


def json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build_map_html(tracts: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> str:
    return (OUTPUT_DIR/'index.template.html').read_text(encoding='utf-8')



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-source", action="store_true")
    parser.add_argument("--refresh-geocodes", action="store_true")
    parser.add_argument("--refresh-leaflet", action="store_true")
    parser.add_argument("--skip-geocoding", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()

    content = source_html(refresh=args.refresh_source)
    tracts, schedule = parse_schedule(content)
    if args.inspect:
        print(json.dumps(tracts, ensure_ascii=False, indent=2))
        return
    if not args.skip_geocoding:
        geocode_tract_anchors(tracts, refresh=args.refresh_geocodes)
    else:
        cache = load_geocode_cache()
        for tract in tracts:
            tract["anchor"] = cache.get(tract["tract_id"], {})

    ensure_leaflet_assets(refresh=args.refresh_leaflet)
    write_csv_outputs(tracts, schedule)
    # Keep place points and dates synchronized with the same source snapshot.
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.build_dva_place_points import build as build_place_points
    build_place_points()
    nodes = read_service_nodes()
    MAP_HTML.parent.mkdir(parents=True, exist_ok=True)
    MAP_HTML.write_text(build_map_html(tracts, nodes), encoding="utf-8")
    print(f"Wrote {MAP_HTML}")
    print(f"Tracts: {len(tracts)}; schedule events: {len(schedule)}; service nodes: {len(nodes)}")


if __name__ == "__main__":
    main()
