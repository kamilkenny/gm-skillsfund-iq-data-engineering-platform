import unittest
from decimal import Decimal
from src.etl import load_allocations, parse_published_count, borough_filter, provider_filter

class TestFunding(unittest.TestCase):
    def test_source_baseline(self):
        rows=load_allocations()
        self.assertEqual(len(rows),32)
        self.assertEqual(len({r['ukprn'] for r in rows}),29)
        self.assertEqual(sum(Decimal(r['allocation_gbp']) for r in rows), Decimal('97002960.34'))
        self.assertEqual(sum(r['funding_route']=='Grant' for r in rows),16)
        self.assertEqual(sum(r['funding_route']=='Procured' for r in rows),16)
    def test_suppression(self):
        self.assertEqual(parse_published_count('low'),(None,'low'))
        self.assertEqual(parse_published_count('c'),(None,'c'))
        self.assertEqual(parse_published_count('0'),(0,None))
        self.assertEqual(parse_published_count('70'),(70,None))
    def test_borough_grand_total_filter(self):
        row={'lad_name':'Bolton','geographic_level':'Local authority district','sex':'Total','ethnicity_major':'Total','family_learning':'Total','tailored_learning_purpose':'Total'}
        self.assertTrue(borough_filter(row))
        row['sex']='Female'
        self.assertFalse(borough_filter(row))
    def test_provider_match(self):
        self.assertTrue(provider_filter({'provider_ukprn':'10004181'}, {'10004181'}))
        self.assertFalse(provider_filter({'provider_ukprn':'10004182'}, {'10004181'}))

if __name__=='__main__': unittest.main()
