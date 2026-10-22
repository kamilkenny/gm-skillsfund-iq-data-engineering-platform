"""Dashboard safeguards are testable without contacting Azure SQL."""
import unittest
from decimal import Decimal
from dashboard.logic import pounds, period_label, published_count, reconcile_funding, check_borough_evidence, is_comparable_period

class TestDashboardLogic(unittest.TestCase):
    def test_money(self):
        self.assertEqual(pounds(Decimal('97002960.34')), '£97,002,960.34')

    def test_period(self):
        self.assertEqual(period_label('202526'), '2025/26')

    def test_low_is_never_zero(self):
        self.assertEqual(published_count('low', None), 'low')
        self.assertEqual(published_count('0', 0), '0')

    def test_funding_not_multiplied_by_activity(self):
        n, total = reconcile_funding([{'total_allocation_gbp': Decimal('100.25')}, {'total_allocation_gbp': Decimal('50.00')}])
        self.assertEqual(n, 2)
        self.assertEqual(total, Decimal('150.25'))

    def test_boroughs_restricted(self):
        with self.assertRaises(ValueError):
            check_borough_evidence([{'borough_name':'Leeds','academic_period':'202425'}])

    def test_provisional_not_comparable(self):
        self.assertFalse(is_comparable_period('202425', '202526'))

if __name__ == '__main__':
    unittest.main()
