import sqlite3
import unittest
from orb_q05 import *
class TestQ05(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');initialize(self.db)
 def tearDown(self):self.db.close()
 def test_save_load_duplicate_delete(self):
  ident=save_dashboard(self.db,'jerome','Analyse',{'widgets':[{'type':'table'}]})
  self.assertEqual(load_dashboard(self.db,'jerome',ident)['configuration']['widgets'][0]['type'],'table')
  copied=duplicate_dashboard(self.db,'jerome',ident)
  self.assertNotEqual(copied,ident)
  self.assertEqual(len(list_dashboards(self.db,'jerome')),2)
  self.assertTrue(delete_dashboard(self.db,'jerome',ident))
 def test_isolation(self):
  ident=save_dashboard(self.db,'jerome','A',{'widgets':[]})
  with self.assertRaises(PermissionError):load_dashboard(self.db,'autre',ident)
  with self.assertRaises(PermissionError):save_dashboard(self.db,'autre','B',{'widgets':[]},ident)
 def test_stats(self):
  x=contingency_statistics([[20,10],[10,20]])
  self.assertAlmostEqual(x['cramers_v'],1/3)
  self.assertTrue(x['inference_recommended'])
 def test_small_expected(self):
  x=contingency_statistics([[1,1],[1,1]])
  self.assertFalse(x['inference_recommended'])
 def test_csv(self):
  s=export_distribution_csv([{'label':'=HYPERLINK("x")','count':2,'percent':50,'denominator':4}],{'campagne':'OPPS'})
  self.assertIn("'=HYPERLINK",s)
  self.assertIn('OPPS',s)
if __name__=='__main__':unittest.main()
