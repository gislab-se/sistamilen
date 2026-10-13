import json
from pathlib import Path
import unittest

from scripts.build_fredriksberg_review import DEFAULT_SOURCE, import_archive
from transport_review import MAP_ROOT, asset_signature, embedded_map_html


class TransportReviewTests(unittest.TestCase):
    def test_exported_map_and_downloads_remove_registration_identifiers(self):
        original = import_archive(DEFAULT_SOURCE)[0] if DEFAULT_SOURCE.exists() else []
        registrations={t['vehicle'] for t in original}
        assets=['data/review-data.json','data/review-data.js','data/resor.csv','data/summeringar.csv']
        for name in assets:
            text=(MAP_ROOT/name).read_text(encoding='utf-8-sig')
            self.assertFalse(any(reg in text for reg in registrations),name)
        data=json.loads((MAP_ROOT/'data/review-data.json').read_text(encoding='utf-8'))
        ids={v['id'] for v in data['vehicles']}
        self.assertEqual(len(ids),20)
        self.assertTrue(all(t['vehicle'] in ids and t['source_sheet'] in ids for t in data['trips']))
        self.assertTrue(all(r['vehicle'] in ids for r in data['reports']))
        if original:
            self.assertEqual({t['id'] for t in original},{t['id'] for t in data['trips']})

    def test_embedded_map_is_self_contained_and_scripts_run_after_dom(self):
        html=embedded_map_html()
        self.assertNotRegex(html,r'<script[^>]*src=')
        self.assertNotRegex(html,r'<link[^>]*href="(?!https:)')
        self.assertGreater(html.index('const data = window.REVIEW_DATA'),html.index('id="map"'))
        self.assertLess(html.index('window.REVIEW_DATA ='),html.index('const data = window.REVIEW_DATA'))
        self.assertIn('data:text/csv;base64,',html)
        self.assertNotIn('href="data/adressmatchning.csv"',html)
        self.assertTrue(asset_signature())
        original = import_archive(DEFAULT_SOURCE)[0] if DEFAULT_SOURCE.exists() else []
        self.assertFalse(any(t['vehicle'] in html for t in original))

    def test_combined_context_uses_same_self_contained_map(self):
        html=embedded_map_html(context='combined')
        self.assertIn("window.REVIEW_CONTEXT='combined'",html)
        self.assertIn('window.REVIEW_WASTE =',html)
        self.assertIn('id="tract-layers"',html)
        self.assertNotRegex(html,r'<script[^>]*src=')


if __name__=='__main__':
    unittest.main()
