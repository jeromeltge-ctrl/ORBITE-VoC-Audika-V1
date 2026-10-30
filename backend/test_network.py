import unittest,tempfile
from pathlib import Path
import orbite_data as d,network_analytics as n
class NetworkTests(unittest.TestCase):
 def test_reference_scope_and_nps(self):
  with tempfile.TemporaryDirectory() as td:
   old=d.DB;d.DB=Path(td)/'db.sqlite'
   try:
    c=d.db();c.executemany('INSERT INTO centres VALUES(?,?,?,?)',[('C1','A','NORD/EST','Alsace'),('C2','B','NORD/EST','Alsace'),('C3','C','SUD','Autre')]);c.execute("INSERT INTO nps(member_id,campaign,appt_type,clinic,region,score,comment,rating_date,send_date,answers,raw_source) VALUES('1','OPPS','Avec Prescription','C1','NORD/EST',10,'','2026-06-01','2026-06-01','[]','test')");c.commit()
    rows=d.filtered(c,region='NORD/EST',sector='Alsace');result=n.build(c,rows,region='NORD/EST',sector='Alsace')
    self.assertEqual(len(result),2);self.assertEqual(result[0]['nps'],100);self.assertIsNone(result[1]['nps']);self.assertEqual(result[1]['reponses'],0)
    c.close()
   finally:d.DB=old
if __name__=='__main__':unittest.main()
