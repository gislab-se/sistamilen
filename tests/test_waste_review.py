import json
import re
import unittest

from waste_review import MAP_ROOT,asset_signature,embedded_map_html


class IndependentWasteReviewTests(unittest.TestCase):
    def test_public_dataset_has_no_trip_or_address_mapping(self):
        data=json.loads((MAP_ROOT/'data/dva-places.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['tracts']),35)
        self.assertEqual(sum(len(t['points']) for t in data['tracts']),293)
        self.assertEqual(len(data['nodes']),47)
        for key in ('trips','vehicles','address_areas','address_municipalities'):
            self.assertNotIn(key,data)

    def test_embedded_map_contains_only_its_own_public_controls(self):
        html=embedded_map_html()
        self.assertIn('window.DVA_DATA =',html)
        self.assertIn('id="tract-layers"',html)
        self.assertNotIn('id="vehicle-layers"',html)
        self.assertNotIn('id="overlap-rows"',html)
        self.assertNotIn('window.REVIEW_DATA =',html)
        self.assertNotIn('window.REVIEW_ROUTES=',html)
        self.assertNotRegex(html,r'<script[^>]*src=')
        self.assertGreater(html.index('const data=window.DVA_DATA'),html.index('id="map"'))
        self.assertTrue(asset_signature())


if __name__=='__main__':unittest.main()
