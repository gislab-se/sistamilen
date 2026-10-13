"""Build local review routes on NVDB topology, using functional road class.

No network calls. Source geometries stay read-only. This is a light motor-vehicle
scenario, not truck navigation or reconstruction of actual driven paths.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np
from pyproj import Transformer
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from shapely import STRtree, Point, from_wkb, force_2d
from shapely.ops import substring

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'prototypes' / 'fredriksberg_resor'
SNAPSHOT = 20260818
CLASS_FACTORS = [1, 1.02, 1.08, 1.15, 1.25, 1.4, 1.6, 1.9, 2.3, 2.8]
DEFAULT_SPEEDS = [110, 100, 90, 80, 70, 60, 50, 40, 30, 20]


def gp_geometry(blob):
    envelope = (blob[3] >> 1) & 7
    return force_2d(from_wkb(blob[8 + [0, 32, 48, 48, 64][envelope]:]))


def active_rows(connection, table):
    connection.row_factory = sqlite3.Row
    return [dict(r) for r in connection.execute(
        f'SELECT * FROM "{table}" WHERE VALID_FROM<=? AND VALID_TO>?', (SNAPSHOT, SNAPSHOT))]


def by_sequence(rows):
    result = defaultdict(list)
    for row in rows:
        result[row['ELEMENT_ID']].append(row)
    return result


def at_measure(rows, measure):
    return [r for r in rows if r['START_MEASURE'] - 1e-10 <= measure < r['END_MEASURE'] + 1e-10]


def direction_matches(value, direction):
    return value in (None, 'Med och mot', 3) or value == ('Med' if direction == 1 else 'Mot') or value == direction


def motor_ban(row):
    """Exclude general motor bans conservatively, including conditional exemptions."""
    return any(row.get(f'Galler_fordon{i}') in ('fordon', 'motordrivna fordon', 'personbil') for i in (1, 2, 3))


def turn_blocked(incoming, outgoing, restrictions):
    for r in restrictions.get(incoming['seq'], []):
        if (outgoing['seq'] == r['TO_LINKSEQUENCE_OID']
                and direction_matches(r['FROM_DIRECTION'], incoming['direction'])
                and direction_matches(r['TO_DIRECTION'], outgoing['direction'])
                and r['FROM_FROM_MEASURE'] - 1e-8 <= incoming['mid'] <= r['FROM_TO_MEASURE'] + 1e-8
                and r['TO_FROM_MEASURE'] - 1e-8 <= outgoing['mid'] <= r['TO_TO_MEASURE'] + 1e-8):
            return True
    return False


def make_state_graph(edges, restrictions):
    """States are directed edges, preserving turn restrictions at real NVDB nodes."""
    incoming, outgoing = defaultdict(list), defaultdict(list)
    for i, e in enumerate(edges):
        outgoing[e['u']].append(i)
        incoming[e['v']].append(i)
    starts, ends, weights = [], [], []
    for node, ins in incoming.items():
        outs = outgoing[node]
        for i in ins:
            for j in outs:
                a, b = edges[i], edges[j]
                if turn_blocked(a, b, restrictions):
                    continue
                reverse = a['physical'] == b['physical'] and a['direction'] != b['direction']
                # Prefer junctions over immediate reversal, while retaining dead-end access.
                penalty = 90 if reverse and len(outs) > 1 else 0
                starts.append(i); ends.append(j); weights.append(b['cost'] + penalty)
    # One source state per topological node; targets are incoming edge states.
    node_sources = {}
    for node, outs in outgoing.items():
        state = len(edges) + len(node_sources)
        node_sources[node] = state
        for j in outs:
            starts.append(state); ends.append(j); weights.append(edges[j]['cost'])
    n = len(edges) + len(node_sources)
    return csr_matrix((weights, (starts, ends)), shape=(n, n)), node_sources, incoming


def build(gpkg):
    source_stat = gpkg.stat()
    connection = sqlite3.connect(gpkg.resolve().as_uri() + '?mode=ro', uri=True)
    print('Reading NVDB attributes and topology', flush=True)
    classes = by_sequence(active_rows(connection, 'NVDB_DK_O_38_FunkVagklass'))
    networks = by_sequence(active_rows(connection, 'NVDB_DK_O_88_Vagtrafiknat'))
    speeds = by_sequence(active_rows(connection, 'NVDB_DK_O_48_Hastighetsgrans'))
    direction_bans = by_sequence(active_rows(connection, 'NVDB_DK_O_77_ForbjudenFardriktning'))
    traffic_bans = by_sequence([r for r in active_rows(connection, 'NVDB_DK_O_12_ForbudTrafik') if motor_ban(r)])
    restrictions = defaultdict(list)
    turn_rows = active_rows(connection, 'NVDB_DK_O_76_ForbjudenSvang')
    for r in turn_rows:
        vehicles = [r.get(f'Galler_fordon{i}') for i in (1, 2, 3)]
        if not any(vehicles) or motor_ban(r):
            restrictions[r['FROM_LINKSEQUENCE_OID']].append(r)
    data_bytes = (APP / 'data/review-data.json').read_bytes()
    data = json.loads(data_bytes)
    to_xy = Transformer.from_crs(4326, 3006, always_xy=True)
    to_lonlat = Transformer.from_crs(3006, 4326, always_xy=True)
    physical = []
    nodes_xy = {r['OID']: gp_geometry(r['geom']) for r in active_rows(connection, 'Net_VAG_Node')}
    for row in active_rows(connection, 'Net_VAG_Link'):
        seq, lo, hi = row['LINKSEQUENCE_OID'], row['START_MEASURE'], row['END_MEASURE']
        if hi <= lo:
            continue
        geometry = gp_geometry(row['geom'])
        if geometry.geom_type != 'LineString' or not geometry.length:
            continue
        start_point = nodes_xy.get(row['START_NODE_OID'])
        if start_point and Point(geometry.coords[-1]).distance(start_point) < Point(geometry.coords[0]).distance(start_point):
            geometry = type(geometry)(list(geometry.coords)[::-1])
        boundaries = {lo, hi}
        for collection in (classes, networks, speeds, direction_bans, traffic_bans):
            for r in collection.get(seq, []):
                boundaries.update(m for m in (r['START_MEASURE'], r['END_MEASURE']) if lo + 1e-8 < m < hi - 1e-8)
        cuts = []
        for m in sorted(boundaries):
            if not cuts or m - cuts[-1] > 1e-8:
                cuts.append(m)
        for a, b in zip(cuts, cuts[1:]):
            if b - a < 1e-9:
                continue
            mid = (a+b)/2
            if not any(r['Nattyp'] == 'bilnät' for r in at_measure(networks.get(seq, []), mid)):
                continue
            classification = at_measure(classes.get(seq, []), mid)
            road_class = min(int(r['Klass']) for r in classification) if classification else 9
            g = substring(geometry, (a-lo)/(hi-lo), (b-lo)/(hi-lo), normalized=True)
            if g.geom_type != 'LineString' or g.length < .01:
                continue
            u = row['START_NODE_OID'] if a == lo else f'{seq}@{a:.12f}'
            v = row['END_NODE_OID'] if b == hi else f'{seq}@{b:.12f}'
            available = {}
            for direction in (1, 2):
                bans = at_measure(direction_bans.get(seq, []), mid) + at_measure(traffic_bans.get(seq, []), mid)
                if any(direction_matches(r['DIRECTION'], direction) for r in bans):
                    continue
                limits = [float(r['Hogsta_tillatna_hastighet']) for r in at_measure(speeds.get(seq, []), mid)
                          if direction_matches(r['DIRECTION'], direction) and str(r['Hogsta_tillatna_hastighet']).isdigit()
                          and 0 < float(r['Hogsta_tillatna_hastighet']) <= 120]
                available[direction] = (min(limits) if limits else DEFAULT_SPEEDS[road_class], not limits)
            if available:
                physical.append(dict(seq=seq, lo=a, hi=b, u=u, v=v, g=g, road_class=road_class,
                                     available=available, length=float(row['LENGTH'])*(b-a)/(hi-lo)))
    connection.close()
    print(f'{len(physical)} motor-road segments; snapping address points', flush=True)
    tree = STRtree([p['g'] for p in physical])
    snaps, cut_points = {}, defaultdict(dict)
    for address, info in data['addresses'].items():
        coordinate = info.get('address_coordinate')
        if not coordinate:
            snaps[address] = {'status': 'missing_point'}
            continue
        point = Point(to_xy.transform(*coordinate))
        index = int(tree.nearest(point))
        p = physical[index]
        distance = point.distance(p['g'])
        # County-only graph must not pull outside places across its border.
        if distance > 1500:
            snaps[address] = {'status': 'outside_network', 'distance_m': round(distance, 1)}
            continue
        fraction = p['g'].project(point, normalized=True)
        if fraction * p['g'].length < .1:
            fraction, node = 0., p['u']
        elif (1-fraction) * p['g'].length < .1:
            fraction, node = 1., p['v']
        else:
            fraction = round(fraction, 10)
            node = f'snap:{index}:{fraction}'
            cut_points[index][fraction] = node
        xy = p['g'].interpolate(fraction, normalized=True)
        snaps[address] = {'status': 'snapped', 'node': node, 'distance_m': round(distance, 1),
                          'coordinate': [round(x, 7) for x in to_lonlat.transform(xy.x, xy.y)],
                          'precision': info.get('geocoding', {}).get('precision'),
                          'geocoding_status': info.get('geocoding', {}).get('status')}
    edges = []
    for index, p in enumerate(physical):
        cuts = sorted({0.: p['u'], 1.: p['v'], **cut_points[index]}.items())
        for part, ((a, u), (b, v)) in enumerate(zip(cuts, cuts[1:])):
            geometry = substring(p['g'], a, b, normalized=True)
            length = p['length'] * (b-a)
            for direction, (speed, estimated) in p['available'].items():
                seconds = length / (speed / 3.6 * .8)
                edges.append(dict(u=u if direction == 1 else v, v=v if direction == 1 else u,
                                  seq=p['seq'], mid=p['lo']+(p['hi']-p['lo'])*(a+b)/2, direction=direction,
                                  physical=(index, part), g=geometry, length=length, road_class=p['road_class'],
                                  seconds=seconds, estimated=estimated, cost=seconds*CLASS_FACTORS[p['road_class']]))
    del physical, tree, nodes_xy
    graph, sources, arrivals = make_state_graph(edges, restrictions)
    print(f'{len(edges)} directed edges; {graph.nnz} permitted transitions; calculating routes', flush=True)
    requests = defaultdict(list)
    trip_results = {}
    pairs = defaultdict(list)
    for t in data['trips']:
        pairs[(t['origin'], t['destination'])].append(t['id'])
    for (origin, destination), ids in pairs.items():
        a, b = snaps[origin], snaps[destination]
        if a['status'] != 'snapped' or b['status'] != 'snapped':
            result = {'status': 'outside_network', 'reason': 'En ändpunkt saknar närliggande bilväg i länsuttaget.'}
        elif a['node'] == b['node']:
            result = {'status': 'same_point', 'reason': 'Samma kartpunkt; körning eller slinga kan inte återskapas från ändpunkterna.'}
        elif a['node'] not in sources or b['node'] not in arrivals:
            result = {'status': 'no_path', 'reason': 'Ändpunkt saknar tillåten anslutning i denna fordonsprofil.'}
        else:
            requests[a['node']].append((b['node'], ids))
            continue
        for id_ in ids:
            trip_results[id_] = result
    paths, path_cache = {}, {}
    for number, (node, destinations) in enumerate(requests.items()):
        distances, predecessors = dijkstra(graph, directed=True, indices=sources[node], return_predecessors=True)
        for target, ids in destinations:
            possible = arrivals[target]
            end = min(possible, key=lambda i: distances[i])
            if not np.isfinite(distances[end]):
                result = {'status': 'no_path', 'reason': 'Ingen sammanhängande tillåten väg i länsuttaget och denna profil.'}
            else:
                key = (node, target)
                if key not in path_cache:
                    states, cursor = [], end
                    while cursor != sources[node]:
                        if cursor < 0 or cursor >= len(edges):
                            raise ValueError('Broken route predecessor chain')
                        states.append(int(cursor)); cursor = int(predecessors[cursor])
                    states.reverse()
                    sections, class_m = [], Counter()
                    length = seconds = estimated_m = 0.
                    for state in states:
                        edge = edges[state]
                        g = edge['g'].simplify(3)
                        coords = list(g.coords)
                        if edge['direction'] == 2:
                            coords.reverse()
                        points = [[round(lon, 6), round(lat, 6)] for lon, lat in (to_lonlat.transform(x, y) for x, y in coords)]
                        klass = edge['road_class']
                        if sections and sections[-1]['class'] == klass and sections[-1]['coordinates'][-1] == points[0]:
                            sections[-1]['coordinates'].extend(points[1:])
                        else:
                            sections.append({'class': klass, 'coordinates': points})
                        length += edge['length']; seconds += edge['seconds']; class_m[klass] += edge['length']
                        if edge['estimated']:
                            estimated_m += edge['length']
                    path_id = str(len(paths))
                    paths[path_id] = {'sections': sections, 'distance_km': round(length/1000, 3),
                                      'travel_minutes': round(seconds/60, 1),
                                      'class_km': {str(k): round(v/1000, 3) for k, v in sorted(class_m.items())},
                                      'estimated_speed_km': round(estimated_m/1000, 3)}
                    path_cache[key] = path_id
                result = {'status': 'routed', 'path': path_cache[key]}
            for id_ in ids:
                trip_results[id_] = result
        if number % 25 == 0:
            print(f'Origins {number+1}/{len(requests)}, paths {len(paths)}', flush=True)
    counts = dict(Counter(r['status'] for r in trip_results.values()))
    payload = {'meta': {'source': gpkg.name, 'source_bytes': source_stat.st_size, 'snapshot': '2026-08-18',
                        'source_modified_utc': datetime.fromtimestamp(source_stat.st_mtime, timezone.utc).isoformat(),
                        'trip_data_sha256': hashlib.sha256(data_bytes).hexdigest(),
                        'built_at_utc': datetime.now(timezone.utc).isoformat(), 'license': 'CC0', 'crs': 'EPSG:3006',
                        'class_factors': CLASS_FACTORS, 'default_speeds_kmh': DEFAULT_SPEEDS,
                        'speed_factor': .8, 'snap_max_m': 1500, 'directed_edges': len(edges),
                        'turn_restrictions': sum(map(len, restrictions.values())), 'counts': counts,
                        'profile': 'Lätt motorfordon. Allmänna motortrafikförbud tillämpas konservativt även vid villkor/undantag. Ingen tungfordonsprofil, vikt/höjd/bärighet eller tidsvillkorsutvärdering.'},
               'addresses': snaps, 'paths': paths, 'trips': trip_results}
    text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    (APP / 'data/road-routes.json').write_text(text, encoding='utf-8')
    (APP / 'data/road-routes.js').write_text('window.REVIEW_ROUTES='+text+';\n', encoding='utf-8')
    print(json.dumps({'counts': counts, 'paths': len(paths), 'bytes': len(text.encode())}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpkg', type=Path, required=True)
    build(parser.parse_args().gpkg)
