import unittest,tempfile
from pathlib import Path
from orb_q_dashboard_export import export_dashboard
class Tests(unittest.TestCase):
 def test_both_exports(self):
  config={'filters':{'start':'2026-01-01','end':'2026-03-31'},'widgets':[{'title':'Essai','series':[{'id':'s1'}]}]}
  results={'s1':{'valid_respondents':12,'distribution':[{'label':'Oui','count':8,'percent':66.7}]}}
  with tempfile.TemporaryDirectory() as d:
   for ext in ('xlsx','pdf'):
    p=Path(d)/('report.'+ext)
    self.assertEqual(export_dashboard(p,'Tableau',config,results)['series_count'],1)
    self.assertGreater(p.stat().st_size,100)
 def test_uncomputed_series_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):
    export_dashboard(Path(d)/'a.xlsx','A',{'widgets':[{'series':[{'id':'missing'}]}]}, {})
if __name__=='__main__':unittest.main()
