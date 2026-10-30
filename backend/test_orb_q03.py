import unittest, json
from orb_q01 import parse_response
from orb_q02 import reconstruct
from orb_q03 import catalog, analyze_question
class Tests(unittest.TestCase):
 def setUp(self):
  self.rows=[]
  for day,qs in [('2026-04-10',['A','B']),('2026-04-11',['A','B']),('2026-04-16',['C']),('2026-04-17',['C'])]:
   for i in range(4):
    raw={'Answer'+str(j):json.dumps({'question':q,'answer':['Oui','Peut-être'] if q=='A' else ['Non']}) for j,q in enumerate(qs,1)}
    self.rows.append(parse_response(raw,response_id=day+str(i),campaign='Appareillage',response_date=day,center='001'))
  self.episodes=reconstruct(self.rows)['episodes'];self.cat=catalog(self.rows,self.episodes)
 def test_catalog(self):
  self.assertEqual(len(self.cat),2)
  self.assertEqual(len(self.cat[1]['questions']),2)
 def test_multi_denominator(self):
  e=self.cat[1];q=e['questions'][0]
  result=analyze_question(self.rows,{**q,'signature':e['signature']},campaign='Appareillage',start=e['first_observation'],end=e['last_observation'])
  self.assertEqual(result['valid_respondents'],8)
  self.assertEqual(sum(x['percent'] for x in result['distribution']),200)
 def test_geo(self):
  e=self.cat[1];q=e['questions'][0]
  self.assertEqual(analyze_question(self.rows,{**q,'signature':e['signature']},centers={'bad'})['valid_respondents'],0)
if __name__=='__main__':unittest.main()
