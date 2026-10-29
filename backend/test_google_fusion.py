import unittest,tempfile,os,sys
from pathlib import Path
from openpyxl import Workbook
import ereputation_bridge as er
class FusionTests(unittest.TestCase):
 def test_real_data_when_available(self):
  root=Path(os.environ.get('ORBITE_TEST_DATA',''))
  if not os.environ.get('ORBITE_TEST_DATA'):self.skipTest('Fichiers métier non distribués dans GitHub')
  with tempfile.TemporaryDirectory() as td:
   for kind,file,start,end in [('referentiel','referentiel.xlsx',None,None),('historique','Historique.xlsx',None,None),('uberall','dashboard-export-2026-10-28.xlsx','01/10/2026','28/10/2026')]:
    p=root/file;meta=er.inspect(p,kind)
    result=er.import_file(td,{'kind':kind,'path':str(p),'mapping':meta['suggested'],'sha256':meta['sha256'],'confirm':True,'start':start,'end':end})
    self.assertTrue(Path(result['backup']).exists())
   s=er.summary(td,{'start':'2026-01','end':'2026-10'})
   self.assertEqual((s['n'],s['n1'],s['centres'],s['zero_total']),(4054,4116,650,9))
   self.assertAlmostEqual(s['note'],4.747551054291881)
   self.assertAlmostEqual(s['moyenne'],0.6236923076923077)
 def test_synthetic_validation(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'ref.xlsx';w=Workbook();s=w.active;s.append(['CODE CENTRE','NOM CENTRE','REGION AUDIK@NET','NOM SECTEUR']);s.append(['C1','Écoute','NORD/EST','Alsace']);w.save(p)
   m=er.inspect(p,'referentiel');self.assertEqual(m['suggested']['Code centre'],'CODE CENTRE')
   with self.assertRaises(ValueError):er.import_file(td,{'kind':'referentiel','path':str(p),'mapping':m['suggested'],'sha256':m['sha256'],'confirm':False})
   result=er.import_file(td,{'kind':'referentiel','path':str(p),'mapping':m['suggested'],'sha256':m['sha256'],'confirm':True})
   self.assertEqual(result['result']['centres'],1)
if __name__=='__main__':unittest.main()
