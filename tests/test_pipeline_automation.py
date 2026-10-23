"""Pure unit tests; fixtures are illustrative, never dashboard source data."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'functions'))
from pipeline import validate_borough_coverage, validate_measure, _build_provider_insert, _build_borough_insert

BOROUGHS = ['Bolton', 'Bury', 'Manchester', 'Oldham', 'Rochdale',
            'Salford', 'Stockport', 'Tameside', 'Trafford', 'Wigan']


def borough_sample():
    return [dict(lad_name=b, time_period=period, geographic_level='Local authority district',
                 lad_code='E000', sex='Total', ethnicity_major='Total', family_learning='Total',
                 tailored_learning_purpose='Total', participation='low', learner_achievements='15')
            for period in ('202425', '202526') for b in BOROUGHS]


class TestAutomation(unittest.TestCase):
    def test_borough_complete_source(self):
        self.assertEqual(validate_borough_coverage(borough_sample()), ['202425', '202526'])

    def test_borough_future_period_supported(self):
        sample = borough_sample()
        for b in BOROUGHS:
            row = next(r for r in sample if r['lad_name'] == b).copy()
            row['time_period'] = '202627'
            sample.append(row)
        self.assertEqual(len(validate_borough_coverage(sample)), 3)

    def test_borough_missing_required(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete borough coverage'):
            validate_borough_coverage(borough_sample()[:-1])

    def test_borough_duplicate_blocked(self):
        rows = borough_sample()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate_borough_coverage(rows + [rows[0]])

    def test_disclosure_preserves_null(self):
        self.assertIsNone(validate_measure('low'))
        self.assertIsNone(validate_measure('c'))
        self.assertEqual(validate_measure('0'), 0)
        with self.assertRaises(ValueError):
            validate_measure('abc')

    def test_rows_parameterised_and_bounded(self):
        row = dict(provider_ukprn='10023139', time_period='202526', provision_type="College's",
                   regulated_status='Total', level='2', participation='low', learner_achievements='54')
        rec = _build_provider_insert([row], 'DFE_PROVIDER_abc')[0]
        self.assertEqual(rec[7], 'low')
        self.assertIsNone(rec[8])
        self.assertEqual(rec[10], 54)
        b = _build_borough_insert(borough_sample()[:1], 'DFE_BOROUGH_abc')[0]
        self.assertIsNone(b[6])
        self.assertEqual(len(b), 9)

if __name__ == '__main__':
    unittest.main()
