"""Cross-module acceptance through the actual Python/packaged JSON process."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from openpyxl import Workbook
import test_consolidation_a_ipc as ipc


class StabilisationTests(unittest.TestCase):
    call=ipc.LotAIpc.call

    def workbook(self,path,header,rows):
        w=Workbook();w.active.append(header)
        for row in rows:w.active.append(row)
        w.save(path);w.close()

    def test_google_only_import_reimport_and_filter_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ref=root/'ref.xlsx'
            self.workbook(ref,['CODE CENTRE','NOM CENTRE','REGION AUDIK@NET','NOM SECTEUR'],[['G1','Google','Nord','S']])
            preview=self.call(root,[('googleInspect',{'kind':'referentiel','path':str(ref)})])[0]['data']
            params={'kind':'referentiel','path':str(ref),'mapping':preview['suggested'],'sha256':preview['sha256'],'confirm':True}
            result=self.call(root,[('googleImport',params)])
            self.assertNotIn('error',result[0],result)
            self.assertFalse((root/'orbite.sqlite').exists())
            history=root/'history.xlsx'
            self.workbook(history,['Année A','Date','Code centre','Nom du centre','Adresse','Note moyenne','Nombre de note'],[[2025,'2025-12-31','G1','Google','',4,10],[2026,'2026-01-31','G1','Google','',4.5,12]])
            preview=self.call(root,[('googleInspect',{'kind':'historique','path':str(history)})])[0]['data']
            params={'kind':'historique','path':str(history),'mapping':preview['suggested'],'sha256':preview['sha256'],'confirm':True}
            output=self.call(root,[('googleImport',params),('googleImport',params),('googleSummary',{'start':'2026-01','end':'2026-01'}),('filters',{})])
            self.assertFalse(any('error' in x for x in output),output)
            self.assertEqual(output[2]['data']['n'],2)
            self.assertEqual(output[3]['data']['regions'],['Nord'])
            with closing(sqlite3.connect(root/'google.sqlite')) as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM historique').fetchone()[0],2)
            before=hashlib.sha256((root/'google.sqlite').read_bytes()).hexdigest()
            rejected=self.call(root,[('googleImport',{**params,'confirm':False}),('googleImport',{**params,'sha256':'invalid'})])
            self.assertTrue(all('error' in x for x in rejected))
            self.assertEqual(hashlib.sha256((root/'google.sqlite').read_bytes()).hexdigest(),before)

    def test_nps_comparisons_questions_network_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.call(root,[('health',{})])
            with closing(sqlite3.connect(root/'orbite.sqlite')) as c,c:
                c.execute("INSERT INTO centres VALUES('C1','Centre','Nord','S')")
            source=root/'nps.xlsx'
            answers=json.dumps({'question':'Accueil ?','answer':'Très bien'},ensure_ascii=False)
            self.workbook(source,['CampaignMemberId','Rating','CampaignName','custom_clinic_id','custom_appointment_type','RatingTime','SurveySendTime','UserComment','Answer1'],[
                ['n',10,'MAIL','C1','Avec Prescription','15/06/2026','01/06/2026','Excellent',answers],
                ['prior',0,'SMS','C1','Sans prescription','2025-06-15','2025-06-01','Ancien',answers],
                ['prev',8,'MAIL','C1','Avec Prescription','2026-05-20','2026-05-01','Précédent',answers],
            ])
            self.assertNotIn('error',self.call(root,[('importNps',{'path':str(source)})])[0])
            p={'start':'2026-06-01','end':'2026-06-30','region':'Nord','sector':'S'}
            csv=root/'verbatims.csv'
            output=self.call(root,[('npsDashboard',{**p,'comparison_mode':'year_over_year'}),('npsDashboard',{**p,'comparison_mode':'previous_period'}),('summary',p),('network',p),('questionAnalysis',p),('exportVerbatims',{**p,'path':str(csv),'search':'Excellent'}),('googleSummary',p),('unknownMethod',{})])
            self.assertFalse(any('error' in x for x in output[:-1]),output)
            self.assertIn('error',output[-1])
            self.assertEqual(output[0]['data']['global']['nps'],100)
            self.assertEqual(output[0]['data']['previous']['nps'],-100)
            self.assertEqual(output[0]['data']['evolution']['nps'],200)
            self.assertEqual(output[1]['data']['previous']['nps'],0)
            self.assertIsNone(output[2]['data']['response_rate'])
            self.assertFalse(output[2]['data']['google_available'])
            self.assertEqual(output[3]['data'][0]['nps'],100)
            self.assertEqual(output[4]['data'][0]['wording'],'Accueil ?')
            self.assertEqual(output[5]['data']['exported'],1)
            self.assertIn('Excellent',csv.read_text(encoding='utf-8-sig'))
            self.assertFalse(output[6]['data']['available'])
            self.assertFalse((root/'google.sqlite').exists())

    def test_both_sources_remain_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.call(root,[('health',{})])
            from engine import setup
            with closing(sqlite3.connect(root/'google.sqlite')) as c,c:
                setup(c);c.execute("INSERT INTO centres VALUES('G','Google','Sud','T','')")
                c.executemany('INSERT INTO historique VALUES(?,?,?,?)',[('G','2025-12',4,4),('G','2026-01',5,4.2)])
            with closing(sqlite3.connect(root/'orbite.sqlite')) as c,c:
                c.execute("INSERT INTO centres VALUES('N','NPS','Nord','S')")
                c.execute("INSERT INTO nps(member_id,clinic,score,comment,rating_date,answers) VALUES('n','N',9,'','2026-01-15','[]')")
            output=self.call(root,[('filters',{}),('summary',{'start':'2026-01-01','end':'2026-01-31'}),('summary',{'region':'Sud','start':'2026-01-01','end':'2026-01-31'})])
            self.assertFalse(any('error' in x for x in output),output)
            self.assertEqual(output[0]['data']['regions'],['Nord','Sud'])
            self.assertEqual(output[1]['data']['nps'],100)
            self.assertEqual(output[1]['data']['google_reviews'],1)
            self.assertIsNone(output[2]['data']['nps'])
            self.assertEqual(output[2]['data']['google_reviews'],1)

if __name__=='__main__':unittest.main()
