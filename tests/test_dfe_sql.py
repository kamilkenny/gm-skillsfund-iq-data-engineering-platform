import unittest
from src.load_dfe_sql import integer_or_null, literal, validate_and_convert_provider, validate_and_convert_borough

class TestDfESqlGenerator(unittest.TestCase):
    def test_suppression_does_not_become_zero(self):
        for marker in ('low', 'c', 'x', 'z'):
            self.assertEqual(integer_or_null(marker), 'NULL')
        self.assertEqual(integer_or_null('70'), '70')
    def test_sql_literal_quotes_are_escaped(self):
        self.assertEqual(literal("Provider's College"), "N'Provider''s College'")
    def test_provider_ukprn_restriction(self):
        row=dict(provider_ukprn='10091956',time_period='202324',provision_type='Education and Training',regulated_status='Regulated',level='Level 3',participation='low',learner_achievements='low')
        self.assertEqual(len(validate_and_convert_provider([row], {'10091956'})),1)
        with self.assertRaises(ValueError):
            validate_and_convert_provider([row], {'10000000'})
    def test_borough_all_periods_required(self):
        row=dict(lad_name='Bolton',lad_code='E08000001',time_period='202425',geographic_level='Local authority district',sex='Total',ethnicity_major='Total',family_learning='Total',tailored_learning_purpose='Total',participation='2080',learner_achievements='1510')
        with self.assertRaises(ValueError):
            validate_and_convert_borough([row])

if __name__=='__main__': unittest.main()
