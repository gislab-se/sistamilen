"""Locate named public DVA tract places using local SCB/OSM and explicit fallbacks.

The optional public-map download sends only a fixed county query, no travel logs
or addresses. Never infer collection points, routes or tract boundaries.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shapely.geometry import Point, shape
from shapely.ops import unary_union

from scripts.build_dva_standalone_map import ROOT, OUTPUT_DIR, RAW_HTML, SOURCE_URL, parse_schedule, load_geocode_cache, read_service_nodes
from scripts.geocode_review_addresses import canonical, distance_km

OUT = ROOT / 'prototypes/fredriksberg_resor/data'
PUBLIC = ROOT / 'data/external/osm/dva_named_places.json.gz'
QUERY = '[out:json][timeout:180];area["ISO3166-2"="SE-W"]["admin_level"="4"]->.county;(nwr["place"]["name"](area.county);way["highway"]["name"](area.county););out center tags;'
CODES = {'Gagnef': '2026', 'Leksand': '2029', 'Rättvik': '2031', 'Vansbro': '2021'}
COLORS = {'Gagnef': '#16705a', 'Leksand': '#a65f12', 'Rättvik': '#8b3e78', 'Vansbro': '#4967a8'}
SPLITS = {'Högberget Skampervägen': ['Högberget', 'Skampervägen'], 'Sälje Forsgärdet': ['Sälje', 'Forsgärdet'],
          'Insjön Tunsta': ['Insjön', 'Tunsta'], 'Ål-Tällberg Nedre Heden': ['Ål-Tällberg', 'Nedre Heden'],
          'Norr och Söder Bergsäng': ['Norr Bergsäng', 'Söder Bergsäng'],
          'Hedslund/Nyheden': ['Hedslund', 'Nyheden'], 'Dalasågen Nordanåker': ['Dalasågen', 'Nordanåker']}
ALIASES = {'Björbo Centrum': 'Björbo', 'Djurås Centrum': 'Djurås', 'Djurås By': 'Djurås',
           'Vikarbyn N om RV 70 fram till Röjeråsv.': 'Vikarbyn', 'Vikarbyn söder om RV 70': 'Vikarbyn',
           'Söderåsbacken RV 69': 'Söderås', 'Vansbro C': 'Vansbro', 'Börjesväg': 'Börjes väg',
           'Östlundsväg': 'Östlunds väg', 'Wallenkampfsväg': 'Wallenkampfs väg', 'Persslogsväg': 'Persslogs väg'}
LOOKUPS = OUTPUT_DIR/'source/tract_place_queries.json'


def target_name(part, municipality):
    return ALIASES.get(part['name'], 'Rättvik' if part['name'] == 'Centrum' and municipality == 'Rättvik' else part['name'])


def lookup_public_names(payload):
    cache = json.loads(LOOKUPS.read_text(encoding='utf-8')) if LOOKUPS.exists() else {}
    requests = sorted({(t['municipality'], target_name(p, t['municipality'])) for t in payload['tracts'] for p in t['points'] if p['status'] == 'fallback'})
    for number, (municipality, name) in enumerate(requests, 1):
        key = municipality + '|' + name
        if key in cache:
            continue
        url = 'https://nominatim.openstreetmap.org/search?' + urlencode({'q': f'{name}, {municipality} kommun, Sverige',
            'format': 'jsonv2', 'addressdetails': 1, 'countrycodes': 'se', 'limit': 5})
        started = time.monotonic()
        request = Request(url, headers={'User-Agent': 'SistaMilen-Dalarna-public-place-review/1.0 (https://github.com/gislab-se/sistamilen)'})
        try:
            with urlopen(request, timeout=20) as response:
                results = json.load(response)
        except (HTTPError, URLError) as error:
            print(f'Public place lookup stopped: {type(error).__name__}', flush=True)
            break
        cache[key] = {'query': f'{name}, {municipality} kommun, Sverige', 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(), 'results': results}
        LOOKUPS.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Public place {number}/{len(requests)}', flush=True)
        time.sleep(max(0, 1.2-(time.monotonic()-started)))


def place_parts(description):
    result, seen = [], set()
    for text in description.split(','):
        text = text.strip()
        if not text:
            continue
        for name in SPLITS.get(text, [text]):
            if canonical(name) not in seen:
                result.append({'name': name, 'source_text': text, 'interpreted': name != text})
                seen.add(canonical(name))
    return result


def download_public():
    endpoint = 'https://overpass-api.de/api/interpreter'
    request = Request(endpoint, data=urlencode({'data': QUERY}).encode(),
                      headers={'User-Agent': 'SistaMilen-Dalarna-public-map/1.0 (https://github.com/gislab-se/sistamilen)'})
    with urlopen(request, timeout=210) as response:
        raw = response.read()
    data = json.loads(raw)
    if data.get('remark') or not data.get('elements'):
        raise ValueError('Incomplete public-map response: ' + str(data.get('remark')))
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(PUBLIC, 'wb') as stream:
        stream.write(raw)
    PUBLIC.with_suffix('.metadata.json').write_text(json.dumps({'source': 'OpenStreetMap via Overpass API',
        'endpoint': endpoint, 'query': QUERY, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        'sha256': hashlib.sha256(raw).hexdigest(), 'elements': len(data['elements']), 'license': 'ODbL 1.0'},
        ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Public county map: {len(data['elements'])} named objects", flush=True)


def geographic_index():
    areas = json.loads((ROOT/'data/derived/deso_2025_dalarna.geojson').read_text(encoding='utf-8'))
    borders = {name: unary_union([shape(f['geometry']) for f in areas['features'] if f['properties']['kommunkod'] == code])
               for name, code in CODES.items()}
    index = defaultdict(list)
    scb = json.loads((ROOT/'data/derived/scb_platsomraden_dalarna.geojson').read_text(encoding='utf-8'))
    for f in scb['features']:
        p = f['properties']
        if p['kommunkod'] not in CODES.values() or p['omradestyp'] not in ('Tätort', 'Småort'):
            continue
        municipality = next(name for name, code in CODES.items() if code == p['kommunkod'])
        g = shape(f['geometry'])
        if g.geom_type == 'MultiPolygon':
            g = max(g.geoms, key=lambda part: part.area)
        point = g.centroid if g.covers(g.centroid) else g.representative_point()
        index[(municipality, canonical(p['namn']))].append({'coordinate': [point.x, point.y], 'precision': 'locality',
            'source': f"SCB {p['omradestyp']} {p['referensar']} · {p['namn']}", 'priority': 0})
    if PUBLIC.exists():
        with gzip.open(PUBLIC, 'rt', encoding='utf-8') as stream:
            public = json.load(stream)
        for e in public['elements']:
            c = e.get('center', e)
            if c.get('lon') is None or not e.get('tags', {}).get('name'):
                continue
            point = Point(c['lon'], c['lat'])
            for municipality, boundary in borders.items():
                if not boundary.covers(point):
                    continue
                tags = e['tags']
                for name in [tags['name'], *tags.get('alt_name', '').split(';')]:
                    if name:
                        index[(municipality, canonical(name))].append({'coordinate': [point.x, point.y],
                            'precision': 'street' if 'highway' in tags else 'place', 'priority': 2 if 'highway' in tags else 1,
                            'source': f"OpenStreetMap {e['type']}/{e['id']} · {tags['name']}"})
                break
    # Reuse public tract geocodes only for their named anchor, not every place.
    for tract_id, anchor in load_geocode_cache().items():
        prefix = tract_id.split('-')[0]
        municipality = next(name for name in CODES if canonical(name).replace('ä', 'a').replace('ö', 'o') == prefix)
        street = canonical(anchor['query_place']).endswith(('vägen', 'väg', 'gatan', 'gata'))
        index[(municipality, canonical(anchor['query_place']))].append({'coordinate': [anchor['lon'], anchor['lat']],
            'precision': 'street' if street else 'place', 'priority': 2 if street else 1, 'source': 'Sparad DVA-ortmatchning · OpenStreetMap Nominatim'})
    cache = json.loads(LOOKUPS.read_text(encoding='utf-8')) if LOOKUPS.exists() else {}
    for key, query in cache.items():
        municipality, name = key.split('|', 1)
        for result in query['results']:
            detail = result.get('address', {})
            coordinate = [float(result['lon']), float(result['lat'])]
            named = [result.get('name', '')] + [detail.get(k, '') for k in ('road', 'hamlet', 'village', 'town', 'city', 'suburb', 'neighbourhood', 'quarter')]
            if detail.get('country_code') != 'se' or not borders[municipality].covers(Point(coordinate)) or not any(canonical(n) == canonical(name) for n in named):
                continue
            street = result.get('class') == 'highway' or result.get('category') == 'highway'
            index[(municipality, canonical(name))].append({'coordinate': coordinate, 'precision': 'street' if street else 'place',
                'priority': 2 if street else 1, 'source': f"OpenStreetMap Nominatim {result.get('osm_type')}/{result.get('osm_id')} · {name}"})
    return index, borders


def locate(part, tract, index):
    name = part['name']
    target = target_name(part, tract['municipality'])
    part = {**part, 'comparison_name': target}
    anchor = tract.get('anchor', {})
    anchor_point = [anchor.get('lon'), anchor.get('lat')]
    candidates = index.get((tract['municipality'], canonical(target)), [])
    if candidates:
        priority = min(c['priority'] for c in candidates)
        choices = [c for c in candidates if c['priority'] == priority]
        if priority == 2:
            # Long or separate same-name streets do not get a false precise match.
            choices = sorted(choices, key=lambda c: distance_km(c['coordinate'], anchor_point))
            nearest = choices[0]
            nearby = [c for c in choices if distance_km(c['coordinate'], nearest['coordinate']) <= 2]
            coordinate = [sum(c['coordinate'][i] for c in nearby)/len(nearby) for i in (0, 1)]
            return {**part, 'coordinate': coordinate, 'precision': 'street', 'status': 'review',
                    'reason': 'Ungefärlig gatupunkt. Hämtställen och vilken del av gatan som ingår är okända.',
                    'source': nearby[0]['source']}
        choices = sorted(choices, key=lambda c: distance_km(c['coordinate'], anchor_point))
        first = choices[0]
        separated = [c for c in choices[1:] if distance_km(c['coordinate'], first['coordinate']) > 1.5]
        ambiguous = bool(separated)
        if ambiguous:
            d1 = distance_km(first['coordinate'], anchor_point)
            d2 = min(distance_km(c['coordinate'], anchor_point) for c in separated)
            if d1 > 12 or d1 + 4 > d2:
                candidates = []
            else:
                return {**part, **{k: first[k] for k in ('coordinate', 'precision', 'source')}, 'status': 'review',
                        'reason': 'Flera liknamniga platser i kommunen. Närmaste traktankare används och behöver granskas.'}
        else:
            interpreted = target != name or part['interpreted']
            return {**part, **{k: first[k] for k in ('coordinate', 'precision', 'source')},
                    'status': 'review' if interpreted else 'matched',
                    'reason': 'Tolkad traktbeskrivning; punkten anger orten, inte angiven del eller hämtställe.' if interpreted else 'Namngiven ort/plats i rätt kommun; ungefärlig ortpunkt, inte hämtställe.'}
    return {**part, 'coordinate': anchor_point if all(v is not None for v in anchor_point) else None,
            'precision': 'tract_anchor', 'status': 'fallback', 'reason': 'Platsen saknar entydig träff. Reserv vid traktens befintliga ortankare, inte platsens läge.',
            'source': 'DVA-traktens sparade ortankare · OpenStreetMap Nominatim'}


def build():
    tracts, schedule = parse_schedule(RAW_HTML.read_text(encoding='utf-8'))
    anchors = load_geocode_cache()
    index, borders = geographic_index()
    scb = json.loads((ROOT/'data/derived/scb_platsomraden_dalarna.geojson').read_text(encoding='utf-8'))
    settlement_areas = [(f['properties'], shape(f['geometry'])) for f in scb['features']
                        if f['properties']['kommunkod'] in CODES.values() and f['properties']['omradestyp'] in ('Tätort', 'Småort')]

    def settlement_for(coordinate, municipality):
        if not coordinate or municipality not in CODES:
            return None
        matches = [(props, geometry) for props, geometry in settlement_areas
                   if props['kommunkod'] == CODES[municipality] and geometry.covers(Point(coordinate))]
        if not matches:
            return None
        props, _ = min(matches, key=lambda pair: pair[1].area)
        return {'id': props['omradeskod'], 'name': props['namn'], 'type': props['omradestyp'], 'year': props['referensar']}
    rows = []
    for tract in tracts:
        tract['anchor'] = anchors.get(tract['tract_id'], {})
        tract['label'] = f"{tract['municipality']} · trakt {tract['tract']}"
        tract['color'] = COLORS[tract['municipality']]
        tract['points'] = [locate(part, tract, index) for part in place_parts(tract['places'])]
        for number, point in enumerate(tract['points'], 1):
            point['comparison_area'] = settlement_for(point['coordinate'], tract['municipality']) if point['status'] != 'fallback' else None
            point['id'] = tract['tract_id'] + ':' + str(number)
            rows.append({'tract_id': tract['tract_id'], 'municipality': tract['municipality'], 'name': point['name'],
                         'source_text': point['source_text'], 'status': point['status'], 'precision': point['precision'],
                         'lon': point['coordinate'][0] if point['coordinate'] else '', 'lat': point['coordinate'][1] if point['coordinate'] else '',
                         'reason': point['reason'], 'source': point['source']})
    # Municipality tags let a single filter compare both datasets reliably.
    review = json.loads((OUT/'review-data.json').read_text(encoding='utf-8'))
    address_municipalities = {}
    address_areas = {}
    for address, info in review['addresses'].items():
        coordinate = info.get('address_coordinate')
        address_municipalities[address] = next((name for name, border in borders.items() if coordinate and border.covers(Point(coordinate))), None)
        address_areas[address] = settlement_for(coordinate, address_municipalities[address])
    payload = {'meta': {'source_url': SOURCE_URL, 'source_snapshot_sha256': hashlib.sha256(RAW_HTML.read_bytes()).hexdigest(),
        'built_at_utc': datetime.now(timezone.utc).isoformat(), 'source_period': '2026', 'trip_period': ['2026-09-21', '2026-09-27'],
        'place_counts': dict(Counter(row['status'] for row in rows)), 'point_count': len(rows), 'tract_count': len(tracts),
        'method': 'SCB tätort/småort och offentliga OSM-namn inom kommunen. Reservpunkter använder traktankare. Punkter anger inte hämtställen eller traktgränser.'},
        'tracts': tracts, 'nodes': read_service_nodes(), 'municipalities': list(CODES), 'waste_types': ['Matavfall', 'Restavfall', 'Plastförpackningar', 'Pappersförpackningar'],
        'address_municipalities': address_municipalities, 'address_areas': address_areas}
    text = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    (OUT/'waste-data.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT/'waste-data.js').write_text('window.REVIEW_WASTE = ' + text + ';\n', encoding='utf-8')
    public = {k: payload[k] for k in ('tracts', 'nodes', 'municipalities', 'waste_types')}
    public['meta'] = {k:v for k,v in payload['meta'].items() if k != 'trip_period'}
    public_text = json.dumps(public, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    (OUTPUT_DIR/'data/dva-places.json').write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT_DIR/'data/dva-places.js').write_text('window.DVA_DATA = ' + public_text + ';\n', encoding='utf-8')
    shutil.copyfile(OUT/'geography.js', OUTPUT_DIR/'data/geography.js')
    shutil.copyfile(OUT.parent/'waste-model.js', OUTPUT_DIR/'model.js')
    with (OUTPUT_DIR/'data/dva_platser_2026.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'tracts': len(tracts), 'points': len(rows), 'counts': payload['meta']['place_counts']}, ensure_ascii=True), flush=True)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-public-places', action='store_true')
    parser.add_argument('--lookup-public-names', action='store_true', help='Sequential cached lookup of remaining public tract-place names')
    args = parser.parse_args()
    if args.download_public_places:
        download_public()
    payload = build()
    if args.lookup_public_names:
        lookup_public_names(payload)
        build()
