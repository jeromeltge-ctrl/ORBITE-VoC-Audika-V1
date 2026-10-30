import unittest
from orb_q01 import parse_cell,parse_response
from orb_q02 import reconstruct
import json
class TestQuestionPacks(unittest.TestCase):
 def row(self,questions):
  return {'Answer'+str(i):json.dumps({'question':q,'answer':['Oui']}) for i,q in enumerate(questions,1)}
 def test_multi(self):
  x=parse_cell(json.dumps({'question':'Q','answer':['A','B']}),1)
  self.assertEqual(x['answers'],['A','B'])
 def test_missing_vs_unanswered(self):
  self.assertEqual(parse_cell(None,1)['state'],'absent')
  self.assertEqual(parse_cell(json.dumps({'question':'Q','answer':[]}),1)['state'],'unanswered')
 def test_invalid(self):self.assertEqual(parse_cell('{',1)['state'],'invalid')
 def test_position_independent(self):
  a=parse_response(self.row(['A','B']),response_id='1',campaign='OPPS')
  b=parse_response(self.row(['B','A']),response_id='2',campaign='OPPS')
  self.assertEqual(a['composition_signature'],b['composition_signature'])
 def test_episodes(self):
  rows=[]
  for day,questions in [('2026-04-10',['A','B']),('2026-04-11',['A','B']),('2026-04-16',['C']),('2026-04-17',['C'])]:
   for i in range(4):rows.append(parse_response(self.row(questions),response_id=day+str(i),campaign='Appareillage',response_date=day))
  out=reconstruct(rows)
  self.assertEqual(len(out['episodes']),2)
  self.assertEqual(out['episodes'][0]['first_observation'],'2026-04-10')
  self.assertEqual(out['episodes'][1]['first_observation'],'2026-04-16')
 def test_incomplete_is_not_new_episode(self):
  rows=[]
  for day in ['2026-04-10','2026-04-11']:
   for i in range(4):rows.append(parse_response(self.row(['A','B']),response_id=day+str(i),campaign='OPPS',response_date=day))
  rows.append(parse_response(self.row(['A']),response_id='partial',campaign='OPPS',response_date='2026-04-11'))
  self.assertEqual(len(reconstruct(rows)['episodes']),1)
if __name__=='__main__':unittest.main()
