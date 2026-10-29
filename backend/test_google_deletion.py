import tempfile,sqlite3,unittest
from pathlib import Path
from engine import setup
import google_deletion as g
class GoogleDeletionTests(unittest.TestCase):
 def test_scope_backup_and_confirmation(self):
  with tempfile.TemporaryDirectory() as td:
   base=Path(td);c=sqlite3.connect(base/'google.sqlite');setup(c)
   c.execute("INSERT INTO centres VALUES('C1','Centre','Nord','Alsace','')")
   c.executemany('INSERT INTO historique VALUES(?,?,?,?)',[('C1','2026-09',12,4.5),('C1','2026-10',13,4.5)])
   c.executemany('INSERT INTO uberall VALUES(?,?,?,?,?,?,?)',[('C1','2026-09',2,4.5,1,'2026-09-01','2026-09-30'),('C1','2026-10',1,4.5,0,'2026-10-01','2026-10-28')]);c.commit();c.close()
   with self.assertRaises(ValueError):g.delete(base,'all','incorrect')
   self.assertFalse(list(base.glob('google-before-deletion-*')))
   r=g.delete(base,'uberall_month','SUPPRIMER UBERALL 2026-10','2026-10')
   self.assertEqual(r['deleted'],1);self.assertTrue(Path(r['backup']).is_file())
   snap=sqlite3.connect(r['backup']);self.assertEqual(snap.execute('SELECT COUNT(*) FROM uberall').fetchone()[0],2);snap.close()
   self.assertEqual(g.inventory(base)['uberall'],1)
   r=g.delete(base,'history','SUPPRIMER HISTORIQUE GOOGLE');self.assertEqual(r['deleted'],2)
   c=sqlite3.connect(base/'google.sqlite');self.assertEqual(c.execute('SELECT COUNT(*) FROM centres').fetchone()[0],1);self.assertEqual(c.execute('SELECT COUNT(*) FROM uberall').fetchone()[0],1);self.assertEqual(c.execute('SELECT COUNT(*) FROM orbite_google_deletions').fetchone()[0],2);c.close()
   r=g.delete(base,'all','REINITIALISER GOOGLE');self.assertEqual(r['deleted'],1)
   self.assertEqual(g.inventory(base)['history'],0);self.assertEqual(g.inventory(base)['uberall'],0)
if __name__=='__main__':unittest.main()
