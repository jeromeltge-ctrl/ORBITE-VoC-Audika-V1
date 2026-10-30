"""Lot A acceptance tests: synthetic Excel and disposable SQLite databases only."""
import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from openpyxl import Workbook
import orbite_data as d
import import_deletion as deletion
from engine import setup


class LotA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.old = d.DB, d.BASE
        d.BASE = self.base
        d.DB = self.base / 'orbite.sqlite'
        self.addCleanup(self.restore)
        with closing(d.db()) as c, c:
            c.execute("INSERT INTO centres VALUES('C1','Centre','Nord','Secteur')")
            c.execute("INSERT INTO settings VALUES('sentinel','preserve')")
            c.execute("INSERT INTO surveys VALUES('survey','OPPS','Enquête','2026-01-01')")
        self.google = self.base / 'google.sqlite'
        with closing(sqlite3.connect(self.google)) as c, c:
            setup(c)
            c.execute("INSERT INTO centres VALUES('G1','Google','Nord','Secteur','Adresse')")
            c.execute("INSERT INTO historique VALUES('G1','2026-01',17,4.5)")
            c.execute("INSERT INTO uberall VALUES('G1','2026-02',3,5,1,'2026-02-01','2026-02-28')")
        self.google_hash = hashlib.sha256(self.google.read_bytes()).hexdigest()

    def restore(self):
        d.DB, d.BASE = self.old

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.google.read_bytes()).hexdigest(), self.google_hash)
        self.assertEqual(self.read('SELECT * FROM centres'), [('C1','Centre','Nord','Secteur')])
        self.assertEqual(self.read('SELECT * FROM settings'), [('sentinel','preserve')])
        self.assertEqual(self.read('SELECT id FROM surveys'), [('survey',)])

    def read(self, sql, args=(), path=None):
        with closing(sqlite3.connect(path or d.DB)) as c:
            return c.execute(sql, args).fetchall()

    def write(self, sql, args=()):
        with closing(sqlite3.connect(d.DB)) as c, c:
            return c.execute(sql, args).lastrowid

    def workbook(self, name='nps.xlsx', rows=None):
        path = self.base / name
        w = Workbook()
        w.active.append(['CampaignMemberId','Rating','CampaignName','custom_clinic_id'])
        for row in rows if rows is not None else [('new',10,'MAIL','C1')]:
            w.active.append(row)
        w.save(path)
        w.close()
        return path

    def legacy(self, member='old', import_id=None):
        batch = self.write("INSERT INTO imports(kind,filename,at,added,skipped) VALUES('nps','nps.xlsx','2026-01-01',1,0)")
        self.write("INSERT INTO nps(member_id,clinic,score,comment,answers,raw_source,import_id) VALUES(?,'C1',9,'','[]','nps.xlsx',?)", (member, import_id))
        return batch

    def dump(self):
        with closing(sqlite3.connect(d.DB)) as c:
            return '\n'.join(c.iterdump())

    def test_new_import_contract_and_persistent_batch(self):
        result = d.import_nps(self.workbook())
        self.assertEqual(result['added'], 1)
        self.assertEqual(result['affected_rows'], 1)
        self.assertTrue(result['can_delete'])
        self.assertEqual(result['deletion_reason'], '')
        item = deletion.items(d)[0]
        self.assertEqual(item['id'], result['import_id'])
        self.assertEqual(item['import_id'], result['import_id'])
        self.assertEqual(item['affected_rows'], 1)
        self.assertEqual(self.read('SELECT import_id FROM nps'), [(result['import_id'],)])
        with closing(d.db()) as c:
            deletion.ensure(c)
        self.assertEqual(deletion.items(d)[0]['import_id'], result['import_id'])

    def test_reimport_has_no_duplicate_or_reassignment(self):
        path = self.workbook(rows=[('a',10,'MAIL','C1'),('a',10,'MAIL','C1'),('b',8,'MAIL','C1')])
        first = d.import_nps(path)
        second = d.import_nps(path)
        self.assertEqual((first['added'], first['ignored']), (2,1))
        self.assertEqual((second['added'], second['ignored']), (0,3))
        self.assertGreater(second['import_id'], first['import_id'])
        self.assertEqual(self.read('SELECT DISTINCT import_id FROM nps'), [(first['import_id'],)])
        self.assertEqual(deletion.remove(d, second['import_id'])['deleted'], 0)
        self.assertEqual(self.read('SELECT COUNT(*) FROM nps'), [(2,)])

    def test_overlapping_files_and_other_batches_preserved(self):
        self.legacy()
        first = d.import_nps(self.workbook(rows=[('a',10,'MAIL','C1')]))
        second = d.import_nps(self.workbook('other.xlsx', [('a',6,'SMS','C1'),('b',7,'SMS','C1')]))
        self.assertEqual((second['added'], second['ignored']), (1,1))
        deletion.remove(d, second['import_id'])
        self.assertEqual(self.read('SELECT member_id,score,import_id FROM nps ORDER BY member_id'), [('a',10,first['import_id']),('old',9,None)])

    def test_legacy_and_reference_deletion_refused(self):
        old = self.legacy()
        ref = self.write("INSERT INTO imports(kind,filename,added,skipped) VALUES('referentiel','ref.xlsx',1,0)")
        for item in deletion.items(d):
            self.assertFalse(item['can_delete'])
            self.assertTrue(item['deletion_reason'])
        before = self.dump()
        for identifier in (old, ref, 99999):
            with self.assertRaises(ValueError):
                deletion.remove(d, identifier)
        self.assertEqual(self.dump(), before)
        self.assertFalse(list(self.base.glob('avant-*.sqlite')))

    def test_backup_is_pre_deletion_and_log_is_persisted(self):
        result = d.import_nps(self.workbook())
        removed = deletion.remove(d, result['import_id'])
        self.assertEqual(removed['deleted'], 1)
        self.assertEqual(self.read('SELECT member_id FROM nps', path=removed['backup']), [('new',)])
        self.assertEqual(self.read('PRAGMA integrity_check', path=removed['backup']), [('ok',)])
        self.assertEqual(self.read('SELECT import_id,filename,deleted,backup FROM import_deletion_log'), [(result['import_id'],'nps.xlsx',1,removed['backup'])])
        self.assertEqual(self.read('SELECT COUNT(*) FROM tracked_nps_imports'), [(0,)])
        again = d.import_nps(self.workbook())
        self.assertGreater(again['import_id'], result['import_id'])

    def test_failed_backup_blocks_both_deletions(self):
        self.legacy()
        result = d.import_nps(self.workbook())
        before = self.dump()
        with patch.object(deletion, '_snapshot', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                deletion.remove(d, result['import_id'])
            with self.assertRaises(OSError):
                deletion.reset_legacy(d, deletion.RESET_CONFIRMATION)
        self.assertEqual(self.dump(), before)

    def test_failed_audit_rolls_back_both_deletions(self):
        self.legacy()
        result = d.import_nps(self.workbook())
        self.write("CREATE TRIGGER fail_audit BEFORE INSERT ON import_deletion_log BEGIN SELECT RAISE(ABORT,'audit failure'); END")
        before = self.dump()
        with self.assertRaises(sqlite3.IntegrityError):
            deletion.remove(d, result['import_id'])
        self.assertEqual(self.dump(), before)
        with self.assertRaises(sqlite3.IntegrityError):
            deletion.reset_legacy(d, deletion.RESET_CONFIRMATION)
        self.assertEqual(self.dump(), before)
        self.assertEqual(len(list(self.base.glob('avant-*.sqlite'))), 2)

    def test_import_failure_rolls_back_rows_batch_and_marker(self):
        self.write("CREATE TRIGGER fail_import BEFORE INSERT ON nps WHEN NEW.member_id='boom' BEGIN SELECT RAISE(ABORT,'import failure'); END")
        before = self.dump()
        with self.assertRaises(sqlite3.IntegrityError):
            d.import_nps(self.workbook(rows=[('first',10,'MAIL','C1'),('boom',9,'MAIL','C1')]))
        self.assertEqual(self.dump(), before)

    def test_wal_snapshot_and_writer_lock(self):
        with closing(sqlite3.connect(d.DB)) as keeper:
            self.assertEqual(keeper.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
            self.legacy()
            result = d.import_nps(self.workbook())
            original = deletion._snapshot
            def locked_snapshot(data, prefix):
                with closing(sqlite3.connect(d.DB, timeout=0)) as writer:
                    with self.assertRaises(sqlite3.OperationalError):
                        writer.execute("INSERT INTO settings VALUES('racing','write')")
                return original(data, prefix)
            with patch.object(deletion, '_snapshot', side_effect=locked_snapshot):
                removed = deletion.remove(d, result['import_id'])
                reset = deletion.reset_legacy(d, deletion.RESET_CONFIRMATION)
            self.assertEqual(self.read('SELECT COUNT(*) FROM nps', path=removed['backup']), [(2,)])
            self.assertEqual(self.read('SELECT member_id FROM nps', path=reset['backup']), [('old',)])

    def test_reset_only_legacy_and_is_idempotent(self):
        old = self.legacy()
        result = d.import_nps(self.workbook())
        before = self.dump()
        with self.assertRaises(ValueError):
            deletion.reset_legacy(d, 'incorrect')
        self.assertEqual(self.dump(), before)
        reset = deletion.reset_legacy(d, deletion.RESET_CONFIRMATION)
        self.assertEqual((reset['deleted'], reset['imports_removed']), (1,1))
        self.assertEqual(self.read('SELECT member_id,import_id FROM nps'), [('new',result['import_id'])])
        self.assertEqual(self.read('SELECT id FROM imports WHERE id=?', (old,)), [])
        self.assertEqual(self.read('SELECT COUNT(*) FROM nps', path=reset['backup']), [(2,)])
        self.assertEqual(self.read('SELECT deleted FROM import_deletion_log'), [(1,)])
        self.assertEqual(deletion.reset_legacy(d, deletion.RESET_CONFIRMATION), {'deleted':0,'imports_removed':0,'backup':None})
        self.assertEqual(len(list(self.base.glob('avant-*.sqlite'))), 1)

    def test_orphaned_provenance_can_only_be_reset(self):
        self.legacy(import_id=99999)
        self.legacy(member='null')
        result = d.import_nps(self.workbook())
        self.assertEqual(deletion.legacy_status(d), {'legacy_rows':2,'legacy_imports':2})
        reset = deletion.reset_legacy(d, deletion.RESET_CONFIRMATION)
        self.assertEqual(reset['deleted'], 2)
        self.assertEqual(self.read('SELECT import_id FROM nps'), [(result['import_id'],)])

    def test_inconsistent_tracked_batch_is_protected(self):
        result = d.import_nps(self.workbook())
        self.write('UPDATE imports SET added=2 WHERE id=?', (result['import_id'],))
        item = deletion.items(d)[0]
        self.assertFalse(item['can_delete'])
        self.assertIn('incohérente', item['deletion_reason'])
        with self.assertRaises(ValueError):
            deletion.remove(d, result['import_id'])
        self.assertEqual(deletion.reset_legacy(d, deletion.RESET_CONFIRMATION)['deleted'], 0)
        self.assertEqual(self.read('SELECT COUNT(*) FROM nps'), [(1,)])

    def test_all_imports_remain_accessible_after_100_batches(self):
        with closing(d.db()) as c, c:
            for _ in range(101):
                identifier = c.execute("INSERT INTO imports(kind,filename,added,skipped) VALUES('nps','empty.xlsx',0,0)").lastrowid
                c.execute('INSERT INTO tracked_nps_imports VALUES(?)', (identifier,))
        self.assertEqual(len(deletion.items(d)), 101)
        self.assertTrue(all(item['can_delete'] for item in deletion.items(d)))

    def test_invalid_input_and_outside_reference_keep_existing_rules(self):
        result = d.import_nps(self.workbook(rows=[('a',10,'MAIL','C1'),('bad',11,'MAIL','C1'),('outside',9,'MAIL','UNKNOWN'),('empty',None,'MAIL','C1')]))
        self.assertEqual((result['added'], result['ignored'], result['outside_reference']), (2,1,1))
        self.assertEqual(self.read('SELECT skipped FROM imports'), [(2,)])
        w = Workbook(); path = self.base / 'missing.xlsx'; w.save(path); w.close()
        before = self.dump()
        with self.assertRaises(ValueError):
            d.import_nps(path)
        self.assertEqual(self.dump(), before)

    def test_rpc_confirmation_and_identifiers(self):
        result = d.import_nps(self.workbook())
        identifier = result['import_id']
        for invalid in (None, True, False, 0, -1, 1.5, str(identifier)):
            with self.subTest(identifier=invalid), self.assertRaises(ValueError):
                deletion.remove_confirmed(d, invalid, f'SUPPRIMER IMPORT NPS {invalid}')
        for confirmation in (None, '', 'SUPPRIMER IMPORT NPS 99999'):
            with self.assertRaises(ValueError):
                deletion.remove_confirmed(d, identifier, confirmation)
        self.assertEqual(self.read('SELECT COUNT(*) FROM nps'), [(1,)])
        self.assertFalse(list(self.base.glob('avant-*.sqlite')))
        self.assertEqual(deletion.remove_confirmed(d, identifier, f'SUPPRIMER IMPORT NPS {identifier}')['deleted'], 1)


if __name__ == '__main__':
    unittest.main()
