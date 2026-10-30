"""Run the actual sidecar, not mocked routers; also supports the packaged EXE."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook
import orbite_data as d
from engine import setup


class LotAIpc(unittest.TestCase):
    def call(self, base, requests):
        executable = os.environ.get('ORBITE_TEST_EXECUTABLE')
        command = [executable] if executable else [sys.executable, str(Path(__file__).with_name('orbite_backend.py'))]
        env = {**os.environ, 'ORBITE_DATA_DIR': str(base), 'LOCALAPPDATA': str(base / 'local'),
               'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
        payload = [{'id': index, 'method': method, 'params': params} for index, (method, params) in enumerate(requests, 1)]
        result = subprocess.run(command, input='\n'.join(json.dumps(x) for x in payload) + '\n',
                                text=True, encoding='utf-8', capture_output=True, env=env, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([x['id'] for x in output], [x['id'] for x in payload], result.stdout)
        return output

    def test_full_import_reimport_delete_reset_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with patch.object(d, 'DB', base / 'orbite.sqlite'), patch.object(d, 'BASE', base):
                with closing(d.db()) as c, c:
                    c.execute("INSERT INTO centres VALUES('C1','Centre','Nord','Secteur')")
                    old = c.execute("INSERT INTO imports(kind,filename,added,skipped) VALUES('nps','old.xlsx',1,0)").lastrowid
                    c.execute("INSERT INTO nps(member_id,clinic,score,comment,answers,raw_source) VALUES('old','C1',9,'','[]','old.xlsx')")
            with closing(sqlite3.connect(base / 'google.sqlite')) as c, c:
                setup(c)
                c.execute("INSERT INTO centres VALUES('C1','Centre','Nord','Secteur','')")
                c.execute("INSERT INTO historique VALUES('C1','2026-01',12,4.5)")
            fingerprint = hashlib.sha256((base / 'google.sqlite').read_bytes()).hexdigest()
            path = base / 'entrée NPS.xlsx'
            w = Workbook(); w.active.append(['CampaignMemberId','Rating','CampaignName','custom_clinic_id'])
            w.active.append(['new',10,'MAIL','C1']); w.save(path); w.close()
            imported = self.call(base, [('importNps', {'path':str(path)}), ('importNps', {'path':str(path)})])
            self.assertNotIn('error', imported[0], imported)
            self.assertNotIn('error', imported[1], imported)
            first, duplicate = [x['data'] for x in imported]
            self.assertEqual((first['added'], duplicate['added'], duplicate['ignored']), (1,0,1))
            identifier = first['import_id']
            output = self.call(base, [
                ('imports', {}), ('legacyImportStatus', {}),
                ('deleteImport', {'id':identifier}),
                ('deleteImport', {'id':old, 'confirmation':f'SUPPRIMER IMPORT NPS {old}'}),
                ('resetLegacyNps', {'confirmation':'wrong'}), ('health', {}),
                ('deleteImport', {'id':identifier, 'confirmation':f'SUPPRIMER IMPORT NPS {identifier}'}),
                ('health', {}), ('resetLegacyNps', {'confirmation':'REINITIALISER ANCIENS NPS'}),
                ('health', {}), ('imports', {}), ('filters', {}),
            ])
            self.assertEqual(output[1]['data'], {'legacy_rows':1,'legacy_imports':1})
            for index in (2,3,4):
                self.assertIn('error', output[index], output)
            for index in (0,1,5,6,7,8,9,10,11):
                self.assertNotIn('error', output[index], output)
            self.assertEqual(output[5]['data']['nps_rows'], 2)
            self.assertEqual(output[6]['data']['deleted'], 1)
            self.assertTrue(Path(output[6]['data']['backup']).is_file())
            self.assertEqual(output[7]['data']['nps_rows'], 1)
            self.assertEqual(output[8]['data']['deleted'], 1)
            self.assertTrue(Path(output[8]['data']['backup']).is_file())
            self.assertEqual(output[9]['data']['nps_rows'], 0)
            self.assertEqual([x['import_id'] for x in output[10]['data']], [duplicate['import_id']])
            self.assertEqual(output[11]['data']['centres'][0]['code'], 'C1')
            self.assertEqual(hashlib.sha256((base / 'google.sqlite').read_bytes()).hexdigest(), fingerprint)
            with closing(sqlite3.connect(base / 'orbite.sqlite')) as c:
                self.assertEqual(c.execute('SELECT COUNT(*) FROM import_deletion_log').fetchone()[0], 2)

    def test_destructive_ids_are_not_coerced(self):
        with tempfile.TemporaryDirectory() as tmp:
            requests = [('deleteImport', {'id':value, 'confirmation':f'SUPPRIMER IMPORT NPS {value}'})
                        for value in (True, 1.9, '1', None, -1, 0)]
            output = self.call(Path(tmp), requests + [('health', {})])
            for response in output[:-1]:
                self.assertIn('error', response)
                self.assertIn('Identifiant', response['error'])
            self.assertEqual(output[-1]['data']['nps_rows'], 0)
            self.assertFalse(list(Path(tmp).glob('avant-*.sqlite')))

    def test_empty_reset_is_noop_and_does_not_create_google(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = self.call(Path(tmp), [('health', {}), ('legacyImportStatus', {}),
                ('resetLegacyNps', {'confirmation':'REINITIALISER ANCIENS NPS'})])
            self.assertFalse(any('error' in x for x in output), output)
            self.assertEqual(output[-1]['data'], {'deleted':0,'imports_removed':0,'backup':None})
            self.assertFalse((Path(tmp) / 'google.sqlite').exists())
            self.assertFalse(list(Path(tmp).glob('avant-*.sqlite')))


if __name__ == '__main__':
    unittest.main()
