import json
import unittest
from pathlib import Path

from scripts.build_dva_place_points import place_parts, locate, OUT


class DvaPlacePointTests(unittest.TestCase):
    def test_compound_names_are_split_explicitly_and_source_text_preserved(self):
        parts=place_parts('Heden, Högberget Skampervägen, Heden, Hedslund/Nyheden')
        self.assertEqual([p['name'] for p in parts],['Heden','Högberget','Skampervägen','Hedslund','Nyheden'])
        self.assertEqual(parts[1]['source_text'],'Högberget Skampervägen')
        self.assertTrue(parts[1]['interpreted'])

    def test_unresolved_place_is_not_presented_as_its_tract_anchor(self):
        tract={'municipality':'Gagnef','anchor':{'lon':15,'lat':60}}
        p=locate({'name':'Unknown','source_text':'Unknown','interpreted':False},tract,{})
        self.assertEqual(p['status'],'fallback')
        self.assertEqual(p['precision'],'tract_anchor')
        self.assertEqual(p['coordinate'],[15,60])

    def test_ambiguous_names_do_not_silently_select_a_location(self):
        tract={'municipality':'Gagnef','anchor':{'lon':15,'lat':60}}
        index={('Gagnef','heden'):[{'coordinate':[14.99,60],'priority':1,'precision':'place','source':'a'},
                                  {'coordinate':[15.03,60],'priority':1,'precision':'place','source':'b'}]}
        p=locate({'name':'Heden','source_text':'Heden','interpreted':False},tract,index)
        self.assertEqual(p['status'],'fallback')

    def test_dataset_preserves_35_tracts_and_discloses_reserve_points(self):
        data=json.loads((OUT/'waste-data.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['tracts']),35)
        self.assertEqual(len({t['tract_id'] for t in data['tracts']}),35)
        points=[p for t in data['tracts'] for p in t['points']]
        self.assertEqual(len(points),293)
        self.assertEqual(len(data['nodes']),47)
        self.assertTrue(all(p['source'] and p['reason'] for p in points))
        self.assertGreater(sum(p['status']!='fallback' for p in points),200)
        self.assertTrue(all(p['precision']=='tract_anchor' for p in points if p['status']=='fallback'))


if __name__=='__main__':
    unittest.main()
