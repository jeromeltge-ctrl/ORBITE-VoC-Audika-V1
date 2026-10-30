"""Safe NPS import deletion; no operation in this module opens google.sqlite."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from uuid import uuid4

RESET_CONFIRMATION = 'REINITIALISER ANCIENS NPS'
# A filename is never proof of provenance. NULL and orphaned IDs are untraceable.
LEGACY_ROWS = """NOT EXISTS (
    SELECT 1 FROM tracked_nps_imports t JOIN imports i ON i.id=t.import_id
    WHERE t.import_id=nps.import_id AND i.kind='nps')"""
LEGACY_IMPORTS = """kind='nps' AND NOT EXISTS (
    SELECT 1 FROM tracked_nps_imports t WHERE t.import_id=imports.id)"""


def ensure(c):
    fields = {r[1] for r in c.execute('PRAGMA table_info(nps)')}
    if 'import_id' not in fields:
        c.execute('ALTER TABLE nps ADD COLUMN import_id INTEGER')
    c.execute('CREATE INDEX IF NOT EXISTS ix_nps_import_id ON nps(import_id)')
    c.execute('CREATE TABLE IF NOT EXISTS tracked_nps_imports(import_id INTEGER PRIMARY KEY)')
    c.execute('''CREATE TABLE IF NOT EXISTS import_deletion_log
       (id INTEGER PRIMARY KEY, import_id INTEGER, filename TEXT, deleted INTEGER, at TEXT, backup TEXT)''')


def _snapshot(data_module, prefix):
    """Caller holds BEGIN IMMEDIATE. A separate reader avoids backing up a writer.

    The reservation prevents concurrent writes between validation and deletion.
    SQLite's backup API includes committed WAL pages. Never use a raw file copy.
    """
    source = Path(data_module.DB).resolve()
    dest = source.parent / f'{prefix}-{datetime.now():%Y%m%d%H%M%S%f}-{uuid4().hex}.sqlite'
    with dest.open('xb'):
        pass
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as reader:
            with closing(sqlite3.connect(dest)) as backup:
                reader.backup(backup)
                if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Sauvegarde SQLite invalide : suppression annulée')
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest


def _item(c, row):
    item = dict(row)
    count = c.execute('SELECT COUNT(*) FROM nps WHERE import_id=?', (item['id'],)).fetchone()[0]
    tracked = c.execute('SELECT 1 FROM tracked_nps_imports WHERE import_id=?', (item['id'],)).fetchone()
    if item['kind'] != 'nps':
        reason = 'Référentiel protégé'
    elif not tracked:
        reason = 'Import ancien sans traçabilité complète'
    elif count != item['added']:
        reason = 'Traçabilité incohérente : nombre de lignes différent du lot enregistré'
    else:
        reason = ''
    item.update(import_id=item['id'], affected_rows=count,
                can_delete=not bool(reason), deletion_reason=reason)
    return item


def remove(data_module, import_id):
    """Internal API; interactive confirmation is enforced by the Electron bridge."""
    if isinstance(import_id, bool) or not isinstance(import_id, (int, str)):
        raise ValueError('Identifiant import invalide')
    if isinstance(import_id, str) and (not import_id.isascii() or not import_id.isdecimal()):
        raise ValueError('Identifiant import invalide')
    import_id = int(import_id)
    if import_id <= 0:
        raise ValueError('Identifiant import invalide')
    with closing(data_module.db()) as c:
        ensure(c)
        with c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM imports WHERE id=?', (import_id,)).fetchone()
            if row is None:
                raise ValueError('Import introuvable')
            item = _item(c, row)
            if not item['can_delete']:
                raise ValueError(item['deletion_reason'] + ' : suppression refusée')
            dest = _snapshot(data_module, f'avant-suppression-import-{import_id}')
            removed = c.execute('DELETE FROM nps WHERE import_id=?', (import_id,)).rowcount
            if removed != item['affected_rows']:
                raise ValueError('Nombre de lignes modifié : suppression annulée')
            c.execute('DELETE FROM imports WHERE id=?', (import_id,))
            c.execute('DELETE FROM tracked_nps_imports WHERE import_id=?', (import_id,))
            c.execute('INSERT INTO import_deletion_log(import_id,filename,deleted,at,backup) VALUES(?,?,?,?,?)',
                      (import_id, row['filename'], removed, datetime.now().isoformat(), str(dest)))
        return {'import_id': import_id, 'deleted': removed, 'backup': str(dest)}


def items(data_module):
    with closing(data_module.db()) as c:
        ensure(c)
        with c:
            c.execute('BEGIN')
            # Do not hide traceable batches after the first 100 imports.
            return [_item(c, row) for row in c.execute('SELECT * FROM imports ORDER BY id DESC')]


def _legacy_status(c):
    return {
        'legacy_rows': c.execute('SELECT COUNT(*) FROM nps WHERE ' + LEGACY_ROWS).fetchone()[0],
        'legacy_imports': c.execute('SELECT COUNT(*) FROM imports WHERE ' + LEGACY_IMPORTS).fetchone()[0],
    }


def legacy_status(data_module):
    with closing(data_module.db()) as c:
        ensure(c)
        with c:
            c.execute('BEGIN')
            return _legacy_status(c)


def reset_legacy(data_module, confirmation):
    """Explicit reset of untraceable NPS only, never centres or traceable batches."""
    if confirmation != RESET_CONFIRMATION:
        raise ValueError('Confirmation textuelle incorrecte')
    with closing(data_module.db()) as c:
        ensure(c)
        with c:
            c.execute('BEGIN IMMEDIATE')
            status = _legacy_status(c)
            if not status['legacy_rows'] and not status['legacy_imports']:
                return {'deleted': 0, 'imports_removed': 0, 'backup': None}
            dest = _snapshot(data_module, 'avant-reinitialisation-anciens-nps')
            removed = c.execute('DELETE FROM nps WHERE ' + LEGACY_ROWS).rowcount
            batches = c.execute('DELETE FROM imports WHERE ' + LEGACY_IMPORTS).rowcount
            if (removed, batches) != (status['legacy_rows'], status['legacy_imports']):
                raise ValueError('Périmètre modifié : réinitialisation annulée')
            c.execute('INSERT INTO import_deletion_log(import_id,filename,deleted,at,backup) VALUES(?,?,?,?,?)',
                      (None, 'REINITIALISATION ANCIENS NPS', removed, datetime.now().isoformat(), str(dest)))
        return {'deleted': removed, 'imports_removed': batches, 'backup': str(dest)}
