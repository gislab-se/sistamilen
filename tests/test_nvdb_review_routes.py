"""Behavioral checks for routing priorities, topology and source-data limits."""
import json
from pathlib import Path
import unittest
from scipy.sparse.csgraph import dijkstra

from scripts.build_nvdb_review_routes import CLASS_FACTORS, direction_matches, make_state_graph, motor_ban

ROOT = Path(__file__).resolve().parents[1]


def edge(u, v, seq, seconds, klass, direction=1, physical=None):
    return dict(u=u, v=v, seq=seq, mid=.5, direction=direction,
                physical=physical or seq, cost=seconds*CLASS_FACTORS[klass])


class RoadRoutingTests(unittest.TestCase):
    def test_prefer_major_road_despite_small_time_detour(self):
        edges = [edge('a', 'b', 'local', 100, 9), edge('a', 'c', 'major1', 65, 1),
                 edge('c', 'b', 'major2', 65, 1)]
        graph, sources, incoming = make_state_graph(edges, {})
        dist, pred = dijkstra(graph, indices=sources['a'], return_predecessors=True)
        target = min(incoming['b'], key=lambda i: dist[i])
        self.assertEqual(target, 2)
        self.assertEqual(pred[target], 1)

    def test_turn_prohibition_uses_edge_history(self):
        edges = [edge('a', 'b', 'from', 1, 0), edge('b', 'c', 'to', 1, 0),
                 edge('b', 'd', 'detour1', 5, 0), edge('d', 'c', 'detour2', 5, 0)]
        restriction = {'from': [dict(FROM_DIRECTION=1, TO_DIRECTION=1,
                       FROM_FROM_MEASURE=0, FROM_TO_MEASURE=1, TO_FROM_MEASURE=0,
                       TO_TO_MEASURE=1, TO_LINKSEQUENCE_OID='to')]}
        graph, sources, incoming = make_state_graph(edges, restriction)
        dist = dijkstra(graph, indices=sources['a'])
        self.assertEqual(min(dist[i] for i in incoming['c']), 11)

    def test_topology_does_not_connect_separate_nodes(self):
        graph, sources, incoming = make_state_graph([edge('a', 'bridge', 'one', 1, 0),
                                                     edge('underpass', 'z', 'two', 1, 0)], {})
        self.assertEqual(float(dijkstra(graph, indices=sources['a'])[incoming['z'][0]]), float('inf'))

    def test_direction_and_vehicle_profile(self):
        self.assertTrue(direction_matches('Mot', 2))
        self.assertFalse(direction_matches('Mot', 1))
        self.assertTrue(direction_matches('Med och mot', 1))
        self.assertTrue(motor_ban({'Galler_fordon1': 'motordrivna fordon'}))
        self.assertFalse(motor_ban({'Galler_fordon1': 'tung lastbil'}))

    def test_generated_pilot_and_missing_route_semantics(self):
        folder = ROOT / 'prototypes/fredriksberg_resor/data'
        data = json.loads((folder / 'review-data.json').read_text(encoding='utf-8'))
        routes = json.loads((folder / 'road-routes.json').read_text(encoding='utf-8'))
        self.assertEqual(set(routes['trips']), {t['id'] for t in data['trips']})
        pilot_id = next(v['id'] for v in data['vehicles'] if v['fredriksberg'])
        pilot = next(t for t in data['trips'] if t['vehicle']==pilot_id and t['date']=='2026-09-23'
                     and t['distance_km']==131)
        path = routes['paths'][routes['trips'][pilot['id']]['path']]
        self.assertTrue(120 < path['distance_km'] < 140)
        self.assertGreater(sum(v for k,v in path['class_km'].items() if int(k)<=3)/path['distance_km'], .9)
        for t in data['trips']:
            result=routes['trips'][t['id']]
            if result['status']!='routed':
                self.assertNotIn('path', result)
            else:
                p=routes['paths'][result['path']]
                self.assertAlmostEqual(sum(p['class_km'].values()),p['distance_km'],delta=.01)
                points=[c for s in p['sections'] for c in s['coordinates']]
                for coordinate,address in ((points[0],t['origin']),(points[-1],t['destination'])):
                    self.assertLess(max(abs(a-b) for a,b in zip(coordinate,routes['addresses'][address]['coordinate'])),2e-6)


if __name__=='__main__':
    unittest.main()
