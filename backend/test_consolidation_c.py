import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from engine import setup,Analysis
from google_view import summary,overview,filter_options


class GoogleViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.path=self.root/'google.sqlite'
        with closing(sqlite3.connect(self.path)) as c,c:
            setup(c)
            c.executemany('INSERT INTO centres VALUES(?,?,?,?,?)',[('A','A','Nord','S',''),('B','B','Sud','S',''),('C','C','Nord','T','')])
            c.executemany('INSERT INTO historique VALUES(?,?,?,?)',[
                ('A','2024-12',5,4),('A','2025-01',6,4),('A','2025-12',10,4),('A','2026-01',12,4.5),
                ('B','2024-12',9,5),('B','2025-01',10,5),('B','2025-12',20,5),('B','2026-01',20,5),
                ('C','2026-01',0,None)])
        self.before=hashlib.sha256(self.path.read_bytes()).hexdigest()

    def tearDown(self):self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.before)

    def test_absent_google_does_not_create_database(self):
        root=self.root/'empty';root.mkdir()
        self.assertFalse(summary(root,{})['available']);self.assertFalse((root/'google.sqlite').exists())
        self.assertEqual(overview(root,{}),{'google_available':False})

    def test_independent_google_and_default_period(self):
        r=summary(self.root,{})
        self.assertTrue(r['available']);self.assertEqual(r['period'],['2026-01'])
        self.assertFalse((self.root/'orbite.sqlite').exists())
        self.assertEqual(r['n'],2);self.assertEqual(r['missing_n'],1)
        self.assertIsNone(r['evolution'])
        self.assertAlmostEqual(r['note'],(12*4.5+20*5)/32)

    def test_regional_and_sector_filters_are_intersections(self):
        r=summary(self.root,{'region':'Nord','sector':'S'})
        self.assertEqual(r['centres'],1);self.assertEqual(r['n'],2);self.assertEqual(r['n1'],1)
        self.assertEqual(r['evolution'],1)
        self.assertEqual([x['name'] for x in r['regions']],['Nord'])
        self.assertEqual([(x['region'],x['name']) for x in r['sectors']],[('Nord','S')])
        self.assertEqual(r['regions'][0]['n'],r['n'])

    def test_zero_is_not_missing(self):
        zero=summary(self.root,{'region':'Sud'})
        self.assertEqual(zero['n'],0);self.assertEqual(zero['zero_periode'],1)
        missing=summary(self.root,{'region':'Nord','sector':'T'})
        self.assertIsNone(missing['n']);self.assertIsNone(missing['moyenne'])
        self.assertIsNone(missing['zero_periode']);self.assertEqual(missing['zero_total'],1)

    def test_empty_scope_not_national_fallback(self):
        r=summary(self.root,{'region':'unknown'})
        self.assertEqual(r['centres'],0);self.assertIsNone(r['n']);self.assertIsNone(r['note'])
        self.assertEqual(r['regions'],[])

    def test_daily_bounds_disclosed_and_yearback_visible(self):
        r=summary(self.root,{'start':'15/01/2026','end':'20/01/2026'})
        self.assertTrue(r['partial_boundaries']);self.assertTrue(r['period_warning'])
        self.assertEqual(r['period'],['2026-01']);self.assertEqual(r['comparison_period'],['2025-01'])

    def test_historical_engine_not_changed(self):
        with closing(sqlite3.connect(self.path)) as c:
            a=Analysis(c);raw=a.stats(['2026-01'],a.codes('Nord','S'))
        shown=summary(self.root,{'region':'Nord','sector':'S'})
        for key in ('n','n1','note','evolution','moyenne','zero_periode'):
            self.assertEqual(raw[key],shown[key])

    def test_union_choices_does_not_merge_centres(self):
        result=filter_options(self.root,[{'region':'Est','sector':'X'}])
        self.assertEqual(result['regions'],['Est','Nord','Sud'])
        self.assertIn({'name':'S','region':'Sud'},result['sectors'])

    def test_overview_uses_same_period_and_values(self):
        params={'start':'2026-01','end':'2026-01','region':'Sud'}
        r=summary(self.root,params);o=overview(self.root,params)
        self.assertEqual(o['google_reviews'],r['n']);self.assertEqual(o['google_note'],r['note'])
        self.assertEqual(o['google_period_start'],r['period'][0])

if __name__=='__main__':unittest.main()
