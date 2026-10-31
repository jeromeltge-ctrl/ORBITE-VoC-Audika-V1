import unittest,tempfile
from pathlib import Path
from orb_q_dashboard_export import export_dashboard
class Tests(unittest.TestCase):
 def test_exports_with_context(self):
  config={'filters':{'region':'Nord'},'widgets':[{'title':'Canal','sort':'percent-desc','series':[{'id':'s1','start':'2026-01-01','end':'2026-03-31','populations':['avec']}]}]}
  results={'s1':{'campaign':'NPS OPPS','question':'Canal','valid_respondents':20,'nonresponses':2,'distribution':[{'label':'Centre','count':12,'percent':60},{'label':'Téléphone','count':8,'percent':40}]}}
  with tempfile.TemporaryDirectory() as d:
   for ext in ('xlsx','pdf'):
    path=Path(d)/('report.'+ext)
    result=export_dashboard(path,'Analyse',config,results)
    self.assertEqual(result['rows'],2)
    self.assertGreater(path.stat().st_size,100)
if __name__=='__main__':unittest.main()
