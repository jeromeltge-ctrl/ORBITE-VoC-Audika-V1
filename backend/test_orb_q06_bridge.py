import json,sqlite3,tempfile,unittest
from pathlib import Path
import orb_q06_bridge as q
class TestBridge(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.execute('CREATE TABLE nps(member_id TEXT, appt_type TEXT,rating_date TEXT,send_date TEXT,clinic TEXT,region TEXT,answers TEXT)')
  self.c.execute('CREATE TABLE centres(code TEXT,sector TEXT)')
  for day,qs in [('2026-04-10',['A','B']),('2026-04-11',['A','B']),('2026-04-16',['C']),('2026-04-17',['C'])]:
   for i in range(4):
    answers=[json.dumps({'question':word,'answer':['Oui','Non'] if word=='A' else ['Oui']}) for word in qs]
    self.c.execute('INSERT INTO nps VALUES(?,?,?,?,?,?,?)',(day+str(i),'Appareillage',day,day,'001','IDF',json.dumps(answers)))
  self.c.commit()
 def tearDown(self):self.c.close()
 def test_catalog_and_quick(self):
  cat=q.handle(self.c,'qaHistoricalCatalog',{})
  self.assertEqual(len(cat['episodes']),2)
  ep=cat['episodes'][1];question=ep['questions'][0]
  result=q.handle(self.c,'qaQuickResult',{'episode_id':ep['id'],'occurrence_id':question['occurrence_id']})
  self.assertEqual(result['valid_respondents'],8)
 def test_save(self):
  ident=q.handle(self.c,'qaDashboardSave',{'title':'Mon tableau','configuration':{'widgets':[]}})['id']
  self.assertEqual(q.handle(self.c,'qaDashboardLoad',{'id':ident})['title'],'Mon tableau')
 def test_exports(self):
  ep=q.handle(self.c,'qaHistoricalCatalog',{})['episodes'][0]
  with tempfile.TemporaryDirectory() as tmp:
   for suffix in ['xlsx','pdf','csv']:
    path=str(Path(tmp)/('test.'+suffix))
    result=q.handle(self.c,'qaExport',{'episode_id':ep['id'],'occurrence_id':ep['questions'][0]['occurrence_id'],'path':path})
    self.assertTrue(Path(path).stat().st_size>20)
if __name__=='__main__':unittest.main()

class TestStatistics(unittest.TestCase):
 def test_spearman(self):
  import orb_q05
  self.assertAlmostEqual(orb_q05.spearman_descriptive([1,2,3],[3,2,1])['spearman_rho'],-1.0)
