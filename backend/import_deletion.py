"""Safe NPS import deletion. Legacy imports without provenance are deliberately protected."""
import sqlite3
from datetime import datetime
from pathlib import Path

def ensure(c):
    fields={r[1] for r in c.execute('PRAGMA table_info(nps)')}
    if 'import_id' not in fields:
        c.execute('ALTER TABLE nps ADD COLUMN import_id INTEGER')
    c.execute('CREATE INDEX IF NOT EXISTS ix_nps_import_id ON nps(import_id)')
    c.execute('CREATE TABLE IF NOT EXISTS tracked_nps_imports(import_id INTEGER PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS import_deletion_log
       (id INTEGER PRIMARY KEY, import_id INTEGER, filename TEXT, deleted INTEGER, at TEXT, backup TEXT)''')

def remove(data_module,import_id):
    c=data_module.db()
    try:
        ensure(c)
        row=c.execute('SELECT id,kind,filename,added FROM imports WHERE id=?',(int(import_id),)).fetchone()
        if row is None:raise ValueError('Import introuvable')
        if row['kind']!='nps':raise ValueError('Le référentiel ne peut pas être supprimé depuis cet écran')
        if not c.execute('SELECT 1 FROM tracked_nps_imports WHERE import_id=?',(import_id,)).fetchone():
            raise ValueError('Import ancien non traçable : suppression refusée')
        count=c.execute('SELECT COUNT(*) FROM nps WHERE import_id=?',(import_id,)).fetchone()[0]
        if count!=row['added']:
            raise ValueError('Import historique non traçable : suppression refusée pour préserver les données')
        # Backup with SQLite backup API: safe even if database uses WAL.
        base=Path(data_module.DB).parent
        dest=base/f'avant-suppression-import-{import_id}-{datetime.now():%Y%m%d%H%M%S%f}.sqlite'
        backup=sqlite3.connect(dest)
        try:c.backup(backup)
        finally:backup.close()
        with c:
            c.execute('DELETE FROM nps WHERE import_id=?',(import_id,))
            c.execute('DELETE FROM imports WHERE id=?',(import_id,))
            c.execute('DELETE FROM tracked_nps_imports WHERE import_id=?',(import_id,))
            c.execute('INSERT INTO import_deletion_log(import_id,filename,deleted,at,backup) VALUES(?,?,?,?,?)',(import_id,row['filename'],count,datetime.now().isoformat(),str(dest)))
        return {'deleted':count,'backup':str(dest)}
    finally:c.close()

def items(data_module):
    c=data_module.db()
    try:
        ensure(c)
        rows=[]
        for row in c.execute('SELECT * FROM imports ORDER BY id DESC LIMIT 100'):
            item=dict(row)
            count=c.execute('SELECT COUNT(*) FROM nps WHERE import_id=?',(item['id'],)).fetchone()[0] if item['kind']=='nps' else 0
            tracked=c.execute('SELECT 1 FROM tracked_nps_imports WHERE import_id=?',(item['id'],)).fetchone()
            item['can_delete']=item['kind']=='nps' and bool(tracked) and count==item['added']
            item['deletion_reason']=('Référentiel protégé' if item['kind']!='nps' else 'Import ancien sans traçabilité complète') if not item['can_delete'] else ''
            rows.append(item)
        return rows
    finally:c.close()

def legacy_status(data_module):
    """Count old NPS rows that have no trustworthy import provenance."""
    c=data_module.db()
    try:
        ensure(c)
        rows=c.execute('SELECT COUNT(*) FROM nps WHERE import_id IS NULL').fetchone()[0]
        batches=c.execute('''SELECT COUNT(*) FROM imports i WHERE i.kind='nps'
           AND NOT EXISTS(SELECT 1 FROM tracked_nps_imports t WHERE t.import_id=i.id)''').fetchone()[0]
        return {'legacy_rows':rows,'legacy_imports':batches}
    finally:c.close()

def reset_legacy(data_module,confirmation):
    """Remove ONLY legacy NPS rows; preserve new traceable batches, centre reference, Google DB."""
    if confirmation!='REINITIALISER ANCIENS NPS':
        raise ValueError('Confirmation textuelle incorrecte')
    c=data_module.db()
    try:
        ensure(c)
        status=legacy_status(data_module)
        if not status['legacy_rows'] and not status['legacy_imports']:
            return {'deleted':0,'imports_removed':0,'backup':None}
        base=Path(data_module.DB).parent
        dest=base/f'avant-reinitialisation-anciens-nps-{datetime.now():%Y%m%d%H%M%S%f}.sqlite'
        snap=sqlite3.connect(dest)
        try:c.backup(snap)
        finally:snap.close()
        try:
            with c:
                removed=c.execute('DELETE FROM nps WHERE import_id IS NULL').rowcount
                c.execute("""DELETE FROM imports WHERE kind='nps' AND id NOT IN
                    (SELECT import_id FROM tracked_nps_imports)""")
                c.execute('INSERT INTO import_deletion_log(import_id,filename,deleted,at,backup) VALUES(?,?,?,?,?)',
                    (None,'REINITIALISATION ANCIENS NPS',removed,datetime.now().isoformat(),str(dest)))
            return {'deleted':removed,'imports_removed':status['legacy_imports'],'backup':str(dest)}
        except Exception:
            raise ValueError('Réinitialisation interrompue : aucune suppression validée. Sauvegarde : '+str(dest))
    finally:c.close()
