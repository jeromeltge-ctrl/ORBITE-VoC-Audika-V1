"""Share ORBITE's NPS centre reference with the historical Google engine.
Only changes centre metadata. Historical reviews and Uberall data remain untouched.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from engine import import_ref,setup

def synchronize(data_dir, nps_data_module):
    base=Path(data_dir)
    source=nps_data_module.db()
    try:
        records=[tuple(r) for r in source.execute('SELECT code,name,region,sector FROM centres ORDER BY code')]
    finally:source.close()
    if not records:raise ValueError('Référentiel réseau NPS absent')
    google_db=base/'google.sqlite'
    base.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(google_db,timeout=30)
    try:
        setup(c)
        current=[tuple(r) for r in c.execute('SELECT code,nom,region,secteur FROM centres ORDER BY code')]
        if current==records:return {'centres':len(records),'updated':False}
        backup=base/f'google-before-reference-sync-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite'
        target=sqlite3.connect(backup)
        try:c.backup(target)
        finally:target.close()
        result=import_ref(c,records)
        return {'centres':len(records),'updated':True,'result':result,'backup':str(backup)}
    finally:c.close()
