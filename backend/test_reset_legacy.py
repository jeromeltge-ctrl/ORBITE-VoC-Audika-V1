import unittest,tempfile,sqlite3
from pathlib import Path
from openpyxl import Workbook
import orbite_data as d,import_deletion as i
class ResetTests(unittest.TestCase):
 def test_reset_preserves_new_and_reference(self):
  with tempfile.TemporaryDirectory() as td:
   old=(d.DB,d.BASE);d.BASE=Path(td);d.DB=d.BASE/'orbite.sqlite'
   try:
    c=d.db();c.execute("INSERT INTO centres VALUES('C1','A','NORD/EST','Alsace')")
    c.execute("INSERT INTO imports(kind,filename,at,added,skipped) VALUES('nps','legacy.xlsx','2026-01-01',1,0)")
    c.execute("INSERT INTO nps(member_id,campaign,appt_type,clinic,region,score,comment,rating_date,send_date,answers,raw_source) VALUES('old','X','OPPS','C1','NORD/EST',9,'','2026-01-01','2026-01-01','[]','old.xlsx')")
    c.commit();c.close()
    w=Workbook();s=w.active;s.append(['CampaignMemberId','Rating','CampaignName','custom_clinic_id']);s.append(['new',10,'X','C1']);p=Path(td)/'new.xlsx';w.save(p)
    self.assertEqual(d.import_nps(p)['added'],1)
    self.assertEqual(i.legacy_status(d),{'legacy_rows':1,'legacy_imports':1})
    with self.assertRaises(ValueError):i.reset_legacy(d,'wrong')
    result=i.reset_legacy(d,'REINITIALISER ANCIENS NPS');self.assertEqual(result['deleted'],1)
    c=d.db();self.assertEqual(c.execute('SELECT member_id FROM nps').fetchone()[0],'new');self.assertEqual(c.execute('SELECT COUNT(*) FROM centres').fetchone()[0],1);c.close()
    backup=sqlite3.connect(result['backup']);self.assertEqual(backup.execute('SELECT COUNT(*) FROM nps').fetchone()[0],2);backup.close()
   finally:d.DB,d.BASE=old
if __name__=='__main__':unittest.main()
