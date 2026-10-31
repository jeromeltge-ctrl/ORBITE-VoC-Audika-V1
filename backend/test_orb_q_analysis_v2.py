import unittest,sqlite3,json
from orb_q_analysis_v2 import normalize_campaign,historical_catalog,analyze_occurrence,filter_options
class Tests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.execute('CREATE TABLE nps(member_id TEXT,appt_type TEXT,rating_date TEXT,send_date TEXT,clinic TEXT,region TEXT,answers TEXT)')
  self.c.execute('CREATE TABLE centres(code TEXT,name TEXT,region TEXT,sector TEXT)')
  self.c.execute("INSERT INTO centres VALUES ('001','Centre A','Nord','S1')")
  for year in (2025,2026):
   for day in (10,11,12,13):
    for replicate in range(4):
     answers=json.dumps([json.dumps({'question':'Canal','answer':['Centre'] if year==2025 else ['Téléphone']})])
     self.c.execute('INSERT INTO nps VALUES (?,?,?,?,?,?,?)',(str(year)+str(day)+str(replicate),'Avec Prescription',f'{year}-04-{day}',f'{year}-04-{day}','001','Nord',answers))
  self.c.commit()
 def tearDown(self):self.c.close()
 def test_campaign(self):
  self.assertEqual(normalize_campaign('Sans Prescription'),('NPS OPPS','sans'))
  self.assertEqual(normalize_campaign('Avec Prescription'),('NPS OPPS','avec'))
 def test_catalog_independent_of_period(self):
  result=historical_catalog(self.c);self.assertTrue(result['episodes'])
  ep=result['episodes'][0];q=ep['questions'][0]
  a=analyze_occurrence(self.c,ep['id'],q['occurrence_id'],{'start':'2025-01-01','end':'2025-12-31'})
  b=analyze_occurrence(self.c,ep['id'],q['occurrence_id'],{'start':'2026-01-01','end':'2026-12-31'})
  self.assertEqual(a['valid_respondents'],16);self.assertEqual(b['valid_respondents'],16)
  self.assertNotEqual(a['distribution'][0]['label'],b['distribution'][0]['label'])
 def test_population_and_scope(self):
  ep=historical_catalog(self.c)['episodes'][0];q=ep['questions'][0]
  a=analyze_occurrence(self.c,ep['id'],q['occurrence_id'],{'populations':['avec'],'region':'Nord','regions':['Sud']})
  self.assertEqual(a['valid_respondents'],0)
  b=analyze_occurrence(self.c,ep['id'],q['occurrence_id'],{'populations':['total']})
  self.assertEqual(b['valid_respondents'],32)
 def test_opps_hierarchy(self):
  labels={e.get('population_view') for e in historical_catalog(self.c)['episodes']}
  self.assertIn('Total OPPS',labels)
  self.assertIn('Avec prescription',labels)
 def test_geo(self):
  self.assertEqual(filter_options(self.c)['centers'][0]['name'],'Centre A')
if __name__=='__main__':unittest.main()
