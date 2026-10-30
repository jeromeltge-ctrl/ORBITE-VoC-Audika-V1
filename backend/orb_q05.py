"""ORB-Q05: local SQLite dashboard configurations, basic contingency statistics, CSV export.
Standalone additive module. Does not modify ORBITE production tables.
"""
import csv
import io
import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone

SCHEMA = '''CREATE TABLE IF NOT EXISTS qa_dashboards (
 id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
 configuration TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
)'''

def initialize(connection):
    connection.execute(SCHEMA)
    connection.execute('CREATE INDEX IF NOT EXISTS idx_qa_dashboards_owner ON qa_dashboards(owner)')
    connection.commit()

def _validate(config):
    if not isinstance(config, dict) or not isinstance(config.get('widgets', []), list):
        raise ValueError('Configuration invalide : widgets doit etre une liste')
    if len(json.dumps(config, ensure_ascii=False)) > 250000:
        raise ValueError('Configuration trop volumineuse')
    return json.dumps(config, ensure_ascii=False, separators=(',', ':'))

def save_dashboard(connection, owner, title, configuration, dashboard_id=None):
    if not owner or not str(owner).strip() or not title or not str(title).strip():
        raise ValueError('Proprietaire et titre requis')
    encoded = _validate(configuration)
    now = datetime.now(timezone.utc).isoformat()
    if dashboard_id:
        cursor = connection.execute('UPDATE qa_dashboards SET title=?,configuration=?,updated_at=? WHERE id=? AND owner=?',
                                    (title, encoded, now, dashboard_id, owner))
        if cursor.rowcount != 1:
            connection.rollback()
            raise PermissionError('Tableau de bord absent ou non autorise')
        result = dashboard_id
    else:
        result = str(uuid.uuid4())
        connection.execute('INSERT INTO qa_dashboards VALUES (?,?,?,?,?,?)',
                           (result, owner, title, encoded, now, now))
    connection.commit()
    return result

def list_dashboards(connection, owner):
    return [dict(id=r[0], title=r[1], updated_at=r[2]) for r in connection.execute(
        'SELECT id,title,updated_at FROM qa_dashboards WHERE owner=? ORDER BY updated_at DESC', (owner,))]

def load_dashboard(connection, owner, dashboard_id):
    row = connection.execute('SELECT id,title,configuration FROM qa_dashboards WHERE id=? AND owner=?',
                             (dashboard_id, owner)).fetchone()
    if not row: raise PermissionError('Tableau de bord absent ou non autorise')
    return dict(id=row[0], title=row[1], configuration=json.loads(row[2]))

def duplicate_dashboard(connection, owner, dashboard_id):
    existing = load_dashboard(connection, owner, dashboard_id)
    return save_dashboard(connection, owner, existing['title'] + ' (copie)', existing['configuration'])

def delete_dashboard(connection, owner, dashboard_id):
    cursor = connection.execute('DELETE FROM qa_dashboards WHERE id=? AND owner=?', (dashboard_id, owner))
    connection.commit()
    return cursor.rowcount == 1

def contingency_statistics(matrix):
    """Pearson chi-square and Cramer's V; no p-value without a statistical library.
    Reject small expected counts rather than reporting an unreliable inference.
    """
    if not matrix or len(matrix) < 2 or any(not isinstance(r, (list, tuple)) for r in matrix):
        raise ValueError('Tableau croise avec au moins deux lignes requis')
    cols = len(matrix[0])
    if cols < 2 or any(len(r) != cols for r in matrix): raise ValueError('Au moins deux colonnes de meme longueur')
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or int(v) != v for r in matrix for v in r):
        raise ValueError('Effectifs entiers positifs requis')
    n = sum(map(sum, matrix))
    if not n: raise ValueError('Effectif nul')
    rs = list(map(sum, matrix)); cs = [sum(r[j] for r in matrix) for j in range(cols)]
    if any(x == 0 for x in rs + cs): raise ValueError('Lignes ou colonnes sans observation')
    expected = [[r*c/n for c in cs] for r in rs]
    chi2 = sum((matrix[i][j]-expected[i][j])**2/expected[i][j] for i in range(len(rs)) for j in range(cols))
    df = (len(rs)-1)*(cols-1)
    v = math.sqrt(chi2/(n*min(len(rs)-1, cols-1)))
    low = sum(x < 5 for row in expected for x in row)
    return {'n':n, 'chi_square':chi2, 'degrees_of_freedom':df, 'cramers_v':v,
            'expected_below_5':low, 'inference_recommended':low == 0,
            'p_value':None, 'warning': 'Effectifs attendus insuffisants' if low else None}

def export_distribution_csv(rows, metadata):
    """CSV UTF-8 for distribution results, with filters/denominator metadata.
    Formula-like labels are escaped to mitigate spreadsheet formula injection.
    """
    out = io.StringIO(newline='')
    writer = csv.writer(out, delimiter=';')
    for key, value in sorted(metadata.items()): writer.writerow(['# '+str(key), str(value)])
    writer.writerow(['Modalite', 'Effectif', 'Pourcentage', 'Denominateur'])
    for row in rows:
        label = str(row.get('label',''))
        if label.lstrip().startswith(('=', '+', '-', '@')): label = "'" + label
        writer.writerow([label, row.get('count', 0), row.get('percent') if row.get('percent') is not None else '', row.get('denominator','')])
    return '\ufeff' + out.getvalue()
