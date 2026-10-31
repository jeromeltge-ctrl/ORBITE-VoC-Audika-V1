"""Additive SQLite audit and manual review for historical questionnaire compositions."""
import json
from datetime import datetime, timezone

SCHEMA = '''CREATE TABLE IF NOT EXISTS qa_history_reviews (
 review_id TEXT PRIMARY KEY, campaign TEXT NOT NULL, observation_date TEXT NOT NULL,
 decision TEXT NOT NULL CHECK(decision IN ('confirmed','rejected','pending')),
 comment TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL,
 updated_at TEXT NOT NULL
)'''


def initialize(con):
    con.execute(SCHEMA)
    con.commit()


def record_review(con, review_id, campaign, observation_date, decision, reviewer, comment=''):
    if decision not in ('confirmed', 'rejected', 'pending'):
        raise ValueError('Décision inconnue')
    if not all(isinstance(v, str) and v.strip() for v in (review_id, campaign, observation_date, reviewer)):
        raise ValueError('Identifiants et auteur requis')
    now = datetime.now(timezone.utc).isoformat()
    with con:
        con.execute('''INSERT INTO qa_history_reviews VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(review_id) DO UPDATE SET
                       decision=excluded.decision,comment=excluded.comment,
                       reviewer=excluded.reviewer,updated_at=excluded.updated_at''',
                    (review_id, campaign, observation_date, decision, comment, reviewer, now))
    return {'id': review_id, 'decision': decision, 'reviewer': reviewer, 'updated_at': now}


def list_reviews(con):
    return [dict(id=r[0], campaign=r[1], date=r[2], decision=r[3], comment=r[4],
                 reviewer=r[5], updated_at=r[6]) for r in con.execute(
        'SELECT review_id,campaign,observation_date,decision,comment,reviewer,updated_at FROM qa_history_reviews ORDER BY observation_date DESC')]
