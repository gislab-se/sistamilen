"""Match review addresses locally against a cached public OSM address extract.

The optional download uses a fixed query for four public counties. No workbook,
trip address, vehicle, person, or visit time is sent to the data service.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from scripts.build_fredriksberg_review import APP, ROOT, address_parts, local_places

PUBLIC_CACHE = ROOT / "data" / "external" / "osm" / "review_county_addresses.json.gz"
MATCH_CACHE = APP / "source" / "address_matches.json"
PUBLIC_QUERY = '''[out:json][timeout:180];
area["ISO3166-2"~"^SE-(W|C|U|X)$"]["boundary"="administrative"]->.counties;
nwr["addr:housenumber"]["addr:street"](area.counties);
out body center;'''


def download_public_addresses():
    url = "https://overpass-api.de/api/interpreter"
    request = Request(url, data=urlencode({"data": PUBLIC_QUERY}).encode(),
                      headers={"User-Agent": "SistaMilen-Dalarna-public-map-extract/1.0 (https://github.com/gislab-se/sistamilen)"})
    with urlopen(request, timeout=210) as response:
        raw = response.read()
    payload = json.loads(raw)
    if payload.get("remark") or not payload.get("elements"):
        raise ValueError("Public OSM extract incomplete: " + str(payload.get("remark")))
    PUBLIC_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(PUBLIC_CACHE, "wb") as stream:
        stream.write(raw)
    metadata = {"source": "OpenStreetMap via Overpass API", "url": url, "query": PUBLIC_QUERY,
                "scope": "Dalarna, Uppsala, Västmanland, Gävleborg", "sha256": hashlib.sha256(raw).hexdigest(),
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "osm_timestamp": payload.get("osm3s", {}).get("timestamp_osm_base"),
                "elements": len(payload["elements"]), "license": "ODbL 1.0",
                "attribution": "© OpenStreetMap contributors, https://www.openstreetmap.org/copyright"}
    PUBLIC_CACHE.with_suffix(".metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"public_elements": len(payload["elements"]), "bytes": len(raw)}), flush=True)


def canonical(text):
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return re.sub(r"[^\w]", "", text)


def street_number(text):
    match = re.match(r"^(.*?)\s+(\d+\s*[A-Za-zÅÄÖåäö]?)$", text.strip())
    return (canonical(match[1]), canonical(match[2])) if match else (canonical(text), "")


def distance_km(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlat = lat2-lat1
    dlon = math.radians(b[0]-a[0])
    return 6371 * 2 * math.asin(min(1, math.sqrt(math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2)))


def public_index(elements):
    index = defaultdict(list)
    for element in elements:
        tags = element.get("tags", {})
        location = element if element.get("type") == "node" else element.get("center", {})
        if not tags.get("addr:street") or not tags.get("addr:housenumber") or "lon" not in location:
            continue
        item = {"coordinate": [location["lon"], location["lat"]], "postcode": canonical(tags.get("addr:postcode", "")),
                "city": tags.get("addr:city", ""), "street": tags["addr:street"], "house_number": tags["addr:housenumber"],
                "osm_type": element["type"], "osm_id": element["id"],
                "geometry": "address_node" if element["type"] == "node" else "bounding_box_center"}
        index[(canonical(item["street"]), canonical(item["house_number"]))].append(item)
    return index


def match_address(address, index, anchor):
    street, postcode, _ = address_parts(address)
    key = street_number(street)
    candidates = index.get(key, [])
    nearby = [c for c in candidates if anchor and distance_km(anchor, c["coordinate"]) < 30]
    exact_postcode = [c for c in nearby if c["postcode"] == postcode]
    candidates = exact_postcode or [c for c in nearby if distance_km(anchor, c["coordinate"]) < 10]
    result = {"coordinate": None, "status": "unmatched", "precision": "unmapped", "candidates": len(candidates),
              "reason": "Ingen entydig lokal träff på gatunamn och hela husnumret", "source": "OpenStreetMap, lokal adressmatchning"}
    if not candidates:
        return result
    # Node and building polygon may describe the same address. Do not merge
    # different sites or invent an entrance coordinate.
    if any(distance_km(candidates[0]["coordinate"], c["coordinate"]) > .1 for c in candidates):
        result.update(status="ambiguous", reason="Flera geografiskt åtskilda träffar på samma adress")
        return result
    chosen = sorted(candidates, key=lambda c: c["geometry"] != "address_node")[0]
    conflicting_postcode = bool(chosen["postcode"] and chosen["postcode"] != postcode)
    result.update(chosen, status="review" if conflicting_postcode else "matched", precision="address",
                  reason="Postnummer avviker – kontrollera träffen" if conflicting_postcode else "Gatunamn och hela husnumret matchar; platsen kontrollerad mot ortankaret",
                  source=f"OpenStreetMap {chosen['osm_type']}/{chosen['osm_id']}",
                  source_url=f"https://www.openstreetmap.org/{chosen['osm_type']}/{chosen['osm_id']}")
    return result


def build_matches():
    previous=json.loads(MATCH_CACHE.read_text(encoding="utf-8")) if MATCH_CACHE.exists() else {}
    with gzip.open(PUBLIC_CACHE, "rt", encoding="utf-8") as stream:
        public = json.load(stream)
    index = public_index(public["elements"])
    data = json.loads((APP / "data" / "review-data.json").read_text(encoding="utf-8"))
    places = local_places()
    matches = {address: match_address(address, index, places.get(item["locality"].casefold(), {}).get("coordinate"))
               for address, item in data["addresses"].items()}
    # Reuse curated address coordinates only on the full street/house/postcode
    # key. A nearby service node does not locate a different visit address.
    local_nodes = defaultdict(list)
    with (ROOT / "data" / "derived" / "servicenoder_2026.csv").open(encoding="utf-8-sig") as stream:
        for node in csv.DictReader(stream):
            local_nodes[(*street_number(node["adress"]), canonical(node["postnummer"]))].append(node)
    for address in matches:
        street, postcode, _ = address_parts(address)
        nodes = local_nodes.get((*street_number(street), postcode), [])
        if nodes:
            coords = [[float(n["lon"]),float(n["lat"])] for n in nodes]
            if all(distance_km(coords[0], c)<.1 for c in coords):
                node=nodes[0]
                matches[address]={"coordinate":coords[0],"status":"matched","precision":"address",
                                  "reason":"Gatunamn, hela husnumret och postnummer matchar en befintlig lokal adresskoordinat",
                                  "source":f"Servicepunkter_2026_Dalarna.xlsx, kluster {node['kluster_id']}","geometry":"source_address_point"}
    for address,prior in previous.get("addresses",{}).items():
        if address in matches and not matches[address].get("coordinate") and (
            "Nominatim" in (prior.get("source") or "") or "Nominatim" in (prior.get("reason") or "")):
            matches[address]=prior
    metadata = json.loads(PUBLIC_CACHE.with_suffix(".metadata.json").read_text(encoding="utf-8"))
    metadata["additional_local_source"]="data/derived/servicenoder_2026.csv"
    if previous.get("metadata",{}).get("additional_geocoder"):
        metadata["additional_geocoder"]=previous["metadata"]["additional_geocoder"]
    output = {"metadata": metadata, "addresses": matches}
    MATCH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    MATCH_CACHE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    with (APP / "data" / "adressmatchning.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["address", "status", "reason", "source", "lon", "lat"])
        writer.writeheader()
        for address, item in matches.items():
            writer.writerow({"address": address, **{k: item[k] for k in ("status", "reason", "source")},
                             "lon": item["coordinate"][0] if item["coordinate"] else "",
                             "lat": item["coordinate"][1] if item["coordinate"] else ""})
    print(json.dumps(dict(Counter(m["status"] for m in matches.values())), ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-public-map", action="store_true", help="Download a fixed public county extract; no review data is sent")
    args = parser.parse_args()
    if args.download_public_map:
        download_public_addresses()
    build_matches()
