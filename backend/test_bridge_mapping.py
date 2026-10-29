import unittest,tempfile,sys,shutil
from pathlib import Path
from openpyxl import Workbook
sys.path.insert(0,str(Path(__file__).parent))
import ereputation_bridge as b
class MappingTests(unittest.TestCase):
 def fixture(self,kind):
  td=tempfile.TemporaryDirectory();p=Path(td.name)/'import.xlsx';w=Workbook();s=w.active;s.append(b.DEFAULTS[kind]);
  if kind=='referentiel':s.append(['C2131','ARRAS','NORD/EST','Nord'])
  elif kind=='historique':s.append([2024,'2024-01-31','C3493','Centre','Adresse',5,8])
  else:s.append(['Description']*5);s.append(['C2131','ARRAS','Adresse',4.5,10])
  w.save(p);return td,p
 def test_three_previews_and_mappings(self):
  for kind in b.FIELDS:
   with self.subTest(kind=kind):
    td,p=self.fixture(kind)
    try:
     preview=b.inspect(p,kind);mapping=preview['suggested']
     self.assertEqual(len(b.resolve_columns(p,kind,mapping)),len(b.FIELDS[kind]))
     self.assertEqual(len(list(b.mapped_rows(p,kind,mapping))),1)
    finally:td.cleanup()
 def test_missing_mapping_uses_unique_exact_suggestion(self):
  for kind in b.FIELDS:
   with self.subTest(kind=kind):
    td,p=self.fixture(kind)
    try:
     m=b.inspect(p,kind)['suggested'];m.pop(b.FIELDS[kind][0])
     self.assertEqual(len(b.resolve_columns(p,kind,m)),len(b.FIELDS[kind]))
    finally:td.cleanup()
 def test_missing_field_fails_before_backup(self):
  td,p=self.fixture('referentiel')
  try:
   preview=b.inspect(p,'referentiel');mapping=preview['suggested'].copy();mapping.pop('Région')
   # No silent fallback if the expected header is absent.
   w=Workbook();ws=w.active;ws.append(['CODE CENTRE','NOM CENTRE','AUTRE REGION','NOM SECTEUR']);ws.append(['C1','Centre','NORD/EST','Nord']);w.save(p)
   with self.assertRaisesRegex(ValueError,'Correspondance non renseignée pour Région'):
    b.import_file(td.name,{'kind':'referentiel','path':str(p),'mapping':mapping,'sha256':b.inspect(p,'referentiel')['sha256'],'confirm':True})
   self.assertFalse(list(Path(td.name).glob('google-backup-*')))
  finally:td.cleanup()
if __name__=='__main__':unittest.main()
