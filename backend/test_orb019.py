import sys,tempfile,sqlite3,types,unittest
from pathlib import Path
sys.path.insert(0,'/mnt/data')
from engine import setup
class TestOverview(unittest.TestCase):
 def test_google_stats_and_region(self):
  with tempfile.TemporaryDirectory() as td:
   c=sqlite3.connect(Path(td)/'google.sqlite');setup(c)
   c.executemany('INSERT INTO centres VALUES(?,?,?,?,?)',[('C1','A','NORD/EST','Alsace',''),('C2','B','OUEST','Bretagne','')])
   c.executemany('INSERT INTO historique VALUES(?,?,?,?)',[('C1','2025-12',5,4.0),('C1','2026-01',7,4.5),('C1','2025-01',4,4.0),('C1','2024-12',3,4.0),('C2','2025-12',10,5.0),('C2','2026-01',11,5.0),('C2','2025-01',9,5.0),('C2','2024-12',8,5.0)])
   c.commit();c.close()
   # Isolate test from the UI and import adapter, without touching Google business code.
   fake=types.ModuleType('ereputation_bridge');fake.connect=lambda root:sqlite3.connect(Path(root)/'google.sqlite');sys.modules['ereputation_bridge']=fake
   sys.path.insert(0,str(Path(__file__).parent))
   import orbite_backend as b
   old=b.root;b.root=Path(td)
   try:
    x=b.overview_google({'start':'2026-01-01','end':'2026-01-31','region':'NORD/EST','sector':'Alsace'})
    self.assertTrue(x['google_available']);self.assertEqual(x['google_reviews'],2);self.assertEqual(x['google_centres'],1);self.assertAlmostEqual(x['google_reviews_per_center_month'],2);self.assertEqual(x['google_note'],4.5)
    self.assertEqual(x['google_reviews_n1'],1)
   finally:b.root=old
if __name__=='__main__':unittest.main()
