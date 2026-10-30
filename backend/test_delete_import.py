import unittest,tempfile
from pathlib import Path
from openpyxl import Workbook
import orbite_data as d,import_deletion as dele
class TestDeletion(unittest.TestCase):
 def test_legacy_protected_new_batch_deletable(self):
  with tempfile.TemporaryDirectory() as td:
   old=(d.DB,d.BASE);d.BASE=Path(td);d.DB=d.BASE/'orbite.sqlite'
   try:
    c=d.db();c.execute("INSERT INTO centres VALUES('C1','A','NORD/EST','Alsace')")
    c.execute("INSERT INTO imports(kind,filename,at,added,skipped) VALUES('nps','old.xlsx','2026-01-01',1,0)")
    c.execute("INSERT INTO nps(member_id,campaign,appt_type,clinic,region,score,comment,rating_date,send_date,answers,raw_source) VALUES('old','X','OPPS','C1','NORD/EST',9,'','2026-01-01','2026-01-01','[]','old.xlsx')")
    c.commit();c.close()
    w=Workbook();s=w.active;s.append(['CampaignMemberId','Rating','CampaignName','custom_clinic_id','custom_appointment_type','RatingTime','SurveySendTime']);s.append(['new',10,'X','C1','OPPS','2026-02-01','2026-02-01']);p=Path(td)/'new.xlsx';w.save(p)
    self.assertEqual(d.import_nps(p)['added'],1)
    items=dele.items(d);self.assertFalse(next(x for x in items if x['filename']=='old.xlsx')['can_delete'])
    target=next(x for x in items if x['filename']=='new.xlsx');self.assertTrue(target['can_delete'])
    with self.assertRaises(ValueError):dele.remove(d,1)
    self.assertEqual(dele.remove(d,target['id'])['deleted'],1)
    c=d.db();self.assertEqual(c.execute('SELECT member_id FROM nps').fetchone()[0],'old');c.close()
    self.assertTrue(list(Path(td).glob('avant-suppression-import-*.sqlite')))
   finally:d.DB,d.BASE=old
if __name__=='__main__':unittest.main()
