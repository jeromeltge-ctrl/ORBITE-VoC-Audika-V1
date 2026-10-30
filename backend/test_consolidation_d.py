import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook,load_workbook
from engine import setup
import export_guard as export


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=self.root/'google.sqlite'
        self.con=sqlite3.connect(self.db);self.addCleanup(self.con.close)
        setup(self.con)
        self.con.executemany('INSERT INTO centres VALUES(?,?,?,?,?)',[('A','Centre "A"','Nord','S',''),('B','B','Sud','T','')])
        self.con.executemany('INSERT INTO historique VALUES(?,?,?,?)',[('A','2025-12',10,4),('A','2026-01',12,4.5),('B','2025-12',9,5),('B','2026-01',10,5)])
        self.con.commit()
        self.template=self.root/'template.xlsx';w=Workbook();w.save(self.template);w.close()
        self.target=self.root/'out.xlsx'

    def fake_builder(self,c,template,path,start,end,region,sector):
        self.assertEqual(c.execute('SELECT code FROM centres').fetchall(),[('A',)])
        w=Workbook();w.remove(w.active)
        for name in ('01 VUE ENSEMBLE','02 MON SECTEUR','03 MES CENTRES','04 DONNÉES DÉTAILLÉES'):
            sh=w.create_sheet(name);sh['V21']='=SUM(1,1)';sh['W21']='=SUM(0)';sh['X21']=1;sh['Y21']=0
        from datetime import datetime
        sh=w['04 DONNÉES DÉTAILLÉES'];sh['A1']='Année';sh['B1']='Date'
        sh.append([2026,datetime(2026,1,1),'A']);sh.append([2025,datetime(2025,12,1),'A'])
        w.save(path);w.close();return {'centres':1,'template':'test'}

    def test_atomic_scoped_output_and_original_preservation(self):
        before=self.db.read_bytes();template=self.template.read_bytes();self.target.write_bytes(b'previous export')
        with patch.object(export,'historical_build',side_effect=self.fake_builder):
            result=export.build(self.con,self.template,self.target,'2026-01','2026-01','Nord','S')
        self.assertEqual(self.db.read_bytes(),before);self.assertEqual(self.template.read_bytes(),template)
        self.assertEqual(Path(result['backup']).read_bytes(),b'previous export')
        with closing(load_workbook(self.target)) as w:
            self.assertIn('CONTROLES ORBITE',w.sheetnames)
            self.assertEqual(w['04 DONNÉES DÉTAILLÉES'].max_row,2)
            self.assertIn('""A""',w['03 MES CENTRES']['C22'].value)
            self.assertEqual(w['01 VUE ENSEMBLE']['J12'].value,'N/C')
            self.assertIn('COUNT(',w['01 VUE ENSEMBLE']['B12'].value)

    def test_failed_export_preserves_existing_destination(self):
        self.target.write_bytes(b'preserve')
        with patch.object(export,'historical_build',side_effect=ValueError('failure')):
            with self.assertRaises(ValueError):export.build(self.con,self.template,self.target,'2026-01','2026-01','Nord','S')
        self.assertEqual(self.target.read_bytes(),b'preserve')
        self.assertFalse(list(self.root.glob('orbite-export-*')))

    def test_protected_path_and_empty_scope(self):
        with self.assertRaises(ValueError):export.build(self.con,self.template,self.template,'2026-01','2026-01')
        with self.assertRaises(ValueError):export.build(self.con,self.template,self.target,'2026-01','2026-01','unknown')
        self.assertFalse(self.target.exists())

    def test_real_historical_template_when_present(self):
        template=Path(__file__).with_name('modele_consolide2.xlsx')
        if not template.is_file():self.skipTest('Modèle historique non disponible dans cette copie locale')
        before=hashlib.sha256(template.read_bytes()).hexdigest()
        result=export.build(self.con,template,self.target,'2026-01','2026-01','Nord','S')
        self.assertEqual(result['centres'],1)
        self.assertEqual(hashlib.sha256(template.read_bytes()).hexdigest(),before)
        with closing(load_workbook(template)) as original, closing(load_workbook(self.target)) as output:
            for name in ('01 VUE ENSEMBLE','02 MON SECTEUR','03 MES CENTRES'):
                self.assertEqual(len(original[name]._charts),len(output[name]._charts))
                self.assertEqual(set(map(str,original[name].merged_cells)),set(map(str,output[name].merged_cells)))
            self.assertIn('CONTROLES ORBITE',output.sheetnames)
            self.assertNotIn('B',[row[2].value for row in output['04 DONNÉES DÉTAILLÉES'].iter_rows(min_row=2)])

if __name__=='__main__':unittest.main()
