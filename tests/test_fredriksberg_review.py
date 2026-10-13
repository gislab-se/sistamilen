"""Verify source reconciliation and coordinate provenance for the review map."""
import io
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

from scripts.build_fredriksberg_review import DEFAULT_SOURCE, address_parts, import_archive, local_places, seconds


class ImportReviewTests(unittest.TestCase):
    @unittest.skipUnless(DEFAULT_SOURCE.exists(), 'Privat originalarkiv finns endast lokalt')
    def test_supplied_archive_reconciles_detail_and_reports(self):
        trips, reports, files, flags = import_archive(DEFAULT_SOURCE)
        self.assertEqual(len(files), 8)
        self.assertEqual(len(trips), 1116)
        self.assertEqual(len({t['id'] for t in trips}), 1116)
        self.assertEqual(sum(r['trip_count'] for r in reports if r['kind'] == 'day'), 1218)
        differences = [f for f in flags if f['type'] == 'summary_difference']
        self.assertEqual(sum(f['difference'] for f in differences), 102)
        self.assertEqual(sum(r['trip_count'] for r in reports if r['kind'] == 'month'), 5403)
        self.assertEqual(sum('Fredriksberg' in t['origin'] + t['destination'] for t in trips), 14)
        self.assertTrue(all(t['source_row'] > 12 for t in trips))

    def test_missing_trip_is_flagged_and_overlapping_detail_is_deduplicated(self):
        workbook = Workbook()
        summary = workbook.active
        summary.append(['Period'])
        summary.append(['Registreringsnummer', 'Antal resor', 'Körsträcka', 'CO2'])
        summary.append(['TEST', 2, 10, 1])
        details = workbook.create_sheet('TEST')
        details.append(['Start', 'Från', 'Stopp', 'Till', 'Antal passager', 'Sträcka', 'Restid', 'Stopptid'])
        details.append([datetime(2026, 9, 21, 9), 'A, 770 10 Fredriksberg', datetime(2026, 9, 21, 10),
                        'B, 791 31 Falun', 0, 10, timedelta(hours=1), timedelta(minutes=4)])
        buffer = io.BytesIO()
        workbook.save(buffer)
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / 'data.zip'
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.writestr('report_2026-09-21_2026-09-22.xlsx', buffer.getvalue())
                archive.writestr('overlap_2026-09-21_2026-09-22.xlsx', buffer.getvalue())
            trips, _, _, flags = import_archive(archive_path)
        self.assertEqual(len(trips), 1)
        self.assertEqual(trips[0]['travel_seconds'], 3600)
        self.assertTrue(any(f['type'] == 'duplicate_trip' for f in flags))
        self.assertTrue(any(f['type'] == 'summary_difference' for f in flags))

    def test_fredriksberg_anchor_uses_both_scb_parts(self):
        places = local_places()
        p = places['fredriksberg']
        self.assertIn('östra och västra', p['source'])
        self.assertTrue(14 < p['coordinate'][0] < 15)
        self.assertTrue(60 < p['coordinate'][1] < 61)
        self.assertEqual(places['dala-floda']['name'], 'Floda / Dala-Floda')

    def test_address_and_long_duration_preserved(self):
        self.assertEqual(address_parts('Filipstadsvägen 36, 770 10 Fredriksberg'), ('Filipstadsvägen 36', '77010', 'Fredriksberg'))
        self.assertEqual(seconds(timedelta(days=2, hours=1)), 176400)
        self.assertIsNone(seconds(None))


if __name__ == '__main__':
    unittest.main()
