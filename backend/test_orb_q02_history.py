import unittest, sqlite3
from orb_q02 import reconstruct
from orb_q_history_store import initialize, record_review, list_reviews

def row(day, sig, keys, index, campaign='Appareillage'):
    return {'date': day, 'campaign': campaign, 'composition_signature': sig,
            'question_keys': keys, 'quality': 'ok', 'response_id': str(index)}

class HistoryTests(unittest.TestCase):
    def test_change_and_preserve(self):
        rows=[]
        for d,s,k in [('2026-04-10','AB',['A','B']),('2026-04-15','AB',['A','B']),
                      ('2026-04-16','C',['C']),('2026-05-05','CD',['C','D'])]:
            rows.extend(row(d,s,k,i) for i in range(5))
        result=reconstruct(rows)
        self.assertEqual([x['signature'] for x in result['episodes']], ['AB','C','CD'])
        self.assertEqual(result['episodes'][0]['last_observation'],'2026-04-15')
    def test_incomplete_subsets(self):
        rows=[row('2026-04-10','AB',['A','B'],i) for i in range(4)]
        rows.append(row('2026-04-10','A',['A'],5))
        result=reconstruct(rows)
        self.assertEqual(len(result['episodes']),1)
        self.assertEqual(result['episodes'][0]['signature'],'AB')
    def test_ambiguous(self):
        rows=[row('2026-04-10','AB',['A','B'],0),row('2026-04-10','C',['C'],1)]
        result=reconstruct(rows)
        self.assertFalse(result['episodes'])
        self.assertEqual(len(result['to_review']),1)
    def test_reappearance_distinct(self):
        rows=[]
        for d,s,k in [('2026-04-10','AB',['A','B']),('2026-04-16','C',['C']),('2026-05-05','AB',['A','B'])]:
            rows.extend(row(d,s,k,i) for i in range(4))
        ids=[x['id'] for x in reconstruct(rows)['episodes']]
        self.assertEqual(len(set(ids)),3)
    def test_manual_review_persists(self):
        con=sqlite3.connect(':memory:');initialize(con)
        record_review(con,'r1','OPPS','2026-04-10','confirmed','testeur','Vérifié')
        self.assertEqual(list_reviews(con)[0]['decision'],'confirmed')
        con.close()
if __name__=='__main__': unittest.main()
