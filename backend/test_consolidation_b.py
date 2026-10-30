import unittest
from nps_analytics import metrics, legacy_metrics, dashboard, previous, valid_score
from periods import bounds


def row(score, campaign='Avec Prescription'):
    return {'score':score,'appt_type':campaign,'campaign':'not a business id','comment':'', 'rating_date':'2026-06-01'}


class NpsTests(unittest.TestCase):
    def test_positive_negative_zero(self):
        for scores, expected in [([10,9,0],100/3),([0,6,9],-100/3),([9,0],0)]:
            with self.subTest(scores=scores):self.assertAlmostEqual(metrics(map(row,scores))['nps'],expected)

    def test_boundaries(self):
        m=metrics(map(row,range(11)))
        self.assertEqual((m['promoteurs'],m['passifs'],m['detracteurs']),(2,2,7))
        self.assertEqual(m['reponses'],11)

    def test_invalid_scores_never_truncated_or_crash(self):
        bad=[None,'','abc',7.9,'9.5',-1,11,True,False,float('nan'),float('inf')]
        self.assertTrue(all(valid_score(v) is None for v in bad))
        self.assertEqual(metrics([row(v) for v in bad]+[row('9.0')])['nps'],100)
        self.assertEqual(legacy_metrics([row(v) for v in bad]+[row('9.0')])['answered'],1)

    def test_no_response(self):
        m=metrics([row(None)])
        self.assertIsNone(m['nps']);self.assertIsNone(m['part_promoteurs'])
        self.assertIsNone(metrics([])['nps'])

    def test_weighted_opps_and_national(self):
        rows=[row(10)]*9+[row(0,'Sans prescription')]
        data=dashboard(rows)
        self.assertEqual(data['global']['nps'],80)
        self.assertEqual(data['campaigns'][0]['nps'],80)
        self.assertEqual(len(data['campaigns']),3)
        self.assertEqual(sum(x['reponses'] for x in data['campaigns'][1:]),10)

    def test_missing_opps_view_and_campaign_id(self):
        data=dashboard([row(10),row(0,'MAIL')])
        self.assertIn('OPPS sans PM',[c['campagne'] for c in data['campaigns']])
        total=data['campaigns'][0];self.assertEqual(total['reponses'],1)
        self.assertEqual(total['nps'],100)

    def test_denominator_not_inferred(self):
        m=metrics([row(10),row(None)])
        self.assertEqual(m['enregistrements'],2)
        self.assertIsNone(m['taux_reponse']);self.assertIsNone(m['denominateur_reponse'])
        self.assertTrue(m['response_rate_reason'])
        self.assertIsNone(legacy_metrics([row(10)])['response_rate'])

    def test_previous_same_duration(self):
        p=previous({'start':'2026-03-01','end':'2026-03-31','region':'Nord'})
        self.assertEqual((p['start'],p['end']),('2026-01-29','2026-02-28'))
        self.assertEqual(p['region'],'Nord')
        self.assertEqual((p['current_start'],p['current_end']),('2026-03-01','2026-03-31'))

    def test_year_over_year_and_leap_day(self):
        p=previous({'start':'2024-02-29','end':'2024-03-01','comparison_mode':'year_over_year'})
        self.assertEqual((p['start'],p['end']),('2023-02-28','2023-03-01'))
        p=previous({'start':'2026-06','end':'2026-06','comparison_mode':'year_over_year'})
        self.assertEqual((p['start'],p['end']),('2025-06-01','2025-06-30'))

    def test_invalid_period_and_unknown_mode(self):
        with self.assertRaises(ValueError):previous({'start':'2026-02-01','end':'2026-01-01'})
        with self.assertRaises(ValueError):previous({'comparison_mode':'unknown'})
        self.assertIsNone(previous({'start':'2026-01-01'}))
        self.assertEqual(bounds('01/06/2026','30/06/2026'),('2026-06-01','2026-06-30'))

    def test_prior_only_campaign_and_empty_current(self):
        data=dashboard([], [row(10)])
        self.assertEqual(data['campaigns'][0]['evolution']['reponses'],-100)
        self.assertIsNone(data['global']['nps'])
        self.assertEqual(data['previous']['nps'],100)

if __name__=='__main__':unittest.main()
