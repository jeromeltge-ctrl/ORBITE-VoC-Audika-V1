"""Audited, backed-up Google data deletion. Does not modify historical engine rules."""
import sqlite3
from pathlib import Path
from datetime import datetime
from engine import setup,month

CONFIRM={'history':'SUPPRIMER HISTORIQUE GOOGLE','uberall':'SUPPRIMER UBERALL','all':'REINITIALISER GOOGLE'}

def _connect(base):
    path=Path(base)/'google.sqlite'
    if not path.is_file():return None
    c=sqlite3.connect(path,timeout=30)
    c.row_factory=sqlite3.Row
    setup(c)
    c.execute('''CREATE TABLE IF NOT EXISTS orbite_google_deletions
      (id INTEGER PRIMARY KEY, operation TEXT NOT NULL, period TEXT, deleted INTEGER NOT NULL, backup TEXT NOT NULL, created TEXT NOT NULL)''')
    return c

def inventory(base):
    c=_connect(base)
    if c is None:return {'history':0,'uberall':0,'months':[],'available':False}
    try:
        return {'available':True,
                'history':c.execute('SELECT COUNT(*) FROM historique').fetchone()[0],
                'uberall':c.execute('SELECT COUNT(*) FROM uberall').fetchone()[0],
                'months':[dict(x) for x in c.execute('SELECT mois AS month,COUNT(*) AS rows FROM uberall GROUP BY mois ORDER BY mois DESC')],
                'history_months':[dict(x) for x in c.execute('SELECT mois AS month,COUNT(*) AS rows FROM historique GROUP BY mois ORDER BY mois DESC')]}
    finally:c.close()

def delete(base,operation,confirmation,period=None):
    if operation=='uberall_month':
        if not isinstance(period,str) or len(period)!=7 or month(period)!=period:raise ValueError('Mois Uberall invalide')
        expected='SUPPRIMER UBERALL '+period
    else:expected=CONFIRM.get(operation)
    if expected is None:raise ValueError('Opération non autorisée')
    if confirmation!=expected:raise ValueError('Confirmation textuelle incorrecte')
    c=_connect(base)
    if c is None:raise ValueError('Aucune base Google existante')
    try:
        targets={'history':['historique'],'uberall':['uberall'],'all':['historique','uberall'],'uberall_month':['uberall']}
        tables=targets[operation]
        where=' WHERE mois=?' if operation=='uberall_month' else ''
        args=(period,) if operation=='uberall_month' else ()
        expected_rows=sum(c.execute('SELECT COUNT(*) FROM '+table+where,args).fetchone()[0] for table in tables)
        if not expected_rows:return {'deleted':0,'backup':None,'operation':operation}
        dest=Path(base)/('google-before-deletion-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite')
        snap=sqlite3.connect(dest)
        try:
            c.backup(snap)
            if snap.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Sauvegarde SQLite invalide')
        except Exception:
            snap.close()
            dest.unlink(missing_ok=True)
            raise
        finally:
            try:snap.close()
            except Exception:pass
        with c:
            removed=sum(c.execute('DELETE FROM '+table+where,args).rowcount for table in tables)
            c.execute('INSERT INTO orbite_google_deletions(operation,period,deleted,backup,created) VALUES(?,?,?,?,?)',
                      (operation,period,removed,str(dest),datetime.now().isoformat()))
        return {'deleted':removed,'backup':str(dest),'operation':operation,'period':period}
    finally:c.close()
