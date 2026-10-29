"""ORBITE VoC - persistent historical survey/question library. No UI dependencies."""
import sqlite3, json, uuid, unicodedata, difflib
from datetime import datetime, timezone

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS surveys(id TEXT PRIMARY KEY,campaign TEXT NOT NULL,name TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS survey_versions(id TEXT PRIMARY KEY,survey_id TEXT NOT NULL REFERENCES surveys(id),version TEXT NOT NULL,year INTEGER,period_start TEXT,period_end TEXT,valid_from TEXT,valid_to TEXT,status TEXT NOT NULL CHECK(status IN ('preparation','active','archivee')),source TEXT,created_at TEXT NOT NULL, UNIQUE(survey_id,version));
CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY,category TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS question_versions(id TEXT PRIMARY KEY,question_id TEXT NOT NULL REFERENCES questions(id),version INTEGER NOT NULL,wording TEXT NOT NULL,answer_type TEXT,options_json TEXT,valid_from TEXT,valid_to TEXT,created_at TEXT NOT NULL,UNIQUE(question_id,version));
CREATE TABLE IF NOT EXISTS survey_questions(survey_version_id TEXT NOT NULL REFERENCES survey_versions(id),position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 5),question_version_id TEXT NOT NULL REFERENCES question_versions(id),PRIMARY KEY(survey_version_id,position),UNIQUE(survey_version_id,question_version_id));
CREATE TABLE IF NOT EXISTS question_results(id TEXT PRIMARY KEY,survey_version_id TEXT NOT NULL,question_version_id TEXT NOT NULL,period TEXT NOT NULL,scope TEXT NOT NULL DEFAULT 'national',metric TEXT NOT NULL,value REAL,denominator INTEGER,source TEXT,FOREIGN KEY(survey_version_id,question_version_id) REFERENCES survey_questions(survey_version_id,question_version_id));
CREATE INDEX IF NOT EXISTS idx_surveys_campaign ON surveys(campaign);
CREATE INDEX IF NOT EXISTS idx_sv_year ON survey_versions(year,status);
CREATE INDEX IF NOT EXISTS idx_qv_wording ON question_versions(wording);
CREATE INDEX IF NOT EXISTS idx_qr_period ON question_results(period,scope);
'''
# The composite FK above requires a matching unique index in SQLite.
SCHEMA += 'CREATE UNIQUE INDEX IF NOT EXISTS uq_sq_version_pair ON survey_questions(survey_version_id,question_version_id);\n'

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(text or '').casefold()) if not unicodedata.combining(c))
def connect(path):
    con=sqlite3.connect(path);con.row_factory=sqlite3.Row;con.execute('PRAGMA foreign_keys=ON');con.executescript(SCHEMA);return con

def add_survey(con,campaign,name,survey_id=None):
    if not name.strip() or not campaign.strip():raise ValueError('Campagne et nom requis')
    sid=survey_id or uid()
    with con:con.execute('INSERT INTO surveys VALUES(?,?,?,?)',(sid,campaign,name,now()))
    return sid

def add_version(con,survey_id,version,year=None,period_start=None,period_end=None,valid_from=None,valid_to=None,status='preparation',source=None):
    if status not in ('preparation','active','archivee'):raise ValueError('Statut invalide')
    if year is not None and not (1900<=int(year)<=2200):raise ValueError('Année invalide')
    if period_start and period_end and period_start>period_end:raise ValueError('Période inversée')
    vid=uid()
    with con:con.execute('INSERT INTO survey_versions VALUES(?,?,?,?,?,?,?,?,?,?,?)',(vid,survey_id,str(version),year,period_start,period_end,valid_from,valid_to,status,source,now()))
    return vid

def add_question(con,wording,answer_type=None,options=None,category=None,question_id=None,valid_from=None,valid_to=None):
    if not wording.strip():raise ValueError('Libellé requis')
    # Reuse only exact matches with identical modalities; no fuzzy automatic equivalence.
    opt=json.dumps(options,ensure_ascii=False,sort_keys=True) if options is not None else None
    existing=con.execute('SELECT q.id,qv.id FROM questions q JOIN question_versions qv ON q.id=qv.question_id WHERE qv.wording=? AND qv.answer_type IS ? AND qv.options_json IS ? LIMIT 1',(wording,answer_type,opt)).fetchone()
    if existing and question_id is None:return existing['id'],existing['id'] and existing[1]
    qid=question_id or uid()
    with con:
        if question_id is None:con.execute('INSERT INTO questions VALUES(?,?,?)',(qid,category,now()))
        v=con.execute('SELECT COALESCE(MAX(version),0)+1 FROM question_versions WHERE question_id=?',(qid,)).fetchone()[0]
        qvid=uid();con.execute('INSERT INTO question_versions VALUES(?,?,?,?,?,?,?,?,?)',(qvid,qid,v,wording,answer_type,opt,valid_from,valid_to,now()))
    return qid,qvid

def set_questions(con,survey_version_id,question_version_ids):
    if not 1<=len(question_version_ids)<=5:raise ValueError('Une enquête contient 1 à 5 questions')
    if len(set(question_version_ids))!=len(question_version_ids):raise ValueError('Question dupliquée')
    with con:
        if con.execute('SELECT 1 FROM survey_questions WHERE survey_version_id=?',(survey_version_id,)).fetchone():raise ValueError('Version déjà composée : créer une nouvelle version')
        for i,qvid in enumerate(question_version_ids,1):con.execute('INSERT INTO survey_questions VALUES(?,?,?)',(survey_version_id,i,qvid))

def list_surveys(con,search='',campaign=None,year=None,status=None,limit=100,offset=0):
    sql='''SELECT s.id survey_id,s.name,s.campaign,v.id version_id,v.version,v.year,v.period_start,v.period_end,v.status,COUNT(sq.position) question_count,(SELECT COALESCE(SUM(denominator),0) FROM question_results r WHERE r.survey_version_id=v.id) reported_denominators FROM surveys s JOIN survey_versions v ON v.survey_id=s.id LEFT JOIN survey_questions sq ON sq.survey_version_id=v.id WHERE 1=1'''
    args=[]
    if campaign:sql+=' AND s.campaign=?';args.append(campaign)
    if year is not None:sql+=' AND v.year=?';args.append(year)
    if status:sql+=' AND v.status=?';args.append(status)
    sql+=' GROUP BY v.id ORDER BY v.year DESC,s.name,v.version LIMIT ? OFFSET ?';args.extend([max(1,min(int(limit),500)),max(0,int(offset))])
    rows=[dict(r) for r in con.execute(sql,args)]
    if search:
        q=norm(search);rows=[r for r in rows if q in norm(r['name']) or any(q in norm(z[0]) for z in con.execute('SELECT qv.wording FROM survey_questions sq JOIN question_versions qv ON qv.id=sq.question_version_id WHERE sq.survey_version_id=?',(r['version_id'],)))]
    return rows

def survey_detail(con,version_id):
    r=con.execute('SELECT s.id survey_id,s.name,s.campaign,v.* FROM survey_versions v JOIN surveys s ON s.id=v.survey_id WHERE v.id=?',(version_id,)).fetchone()
    if not r:raise KeyError(version_id)
    result=dict(r)
    result['questions']=[dict(z) for z in con.execute('''SELECT sq.position,q.id question_id,qv.id question_version_id,qv.version question_version,qv.wording,qv.answer_type,qv.options_json FROM survey_questions sq JOIN question_versions qv ON qv.id=sq.question_version_id JOIN questions q ON q.id=qv.question_id WHERE sq.survey_version_id=? ORDER BY sq.position''',(version_id,))]
    return result

def question_detail(con,question_id):
    q=con.execute('SELECT * FROM questions WHERE id=?',(question_id,)).fetchone()
    if not q:raise KeyError(question_id)
    return {'question':dict(q),'versions':[dict(x) for x in con.execute('SELECT * FROM question_versions WHERE question_id=? ORDER BY version',(question_id,))], 'uses':[dict(x) for x in con.execute('''SELECT s.name,s.campaign,v.version,v.year,v.period_start,v.period_end,sq.position,qv.wording FROM survey_questions sq JOIN question_versions qv ON qv.id=sq.question_version_id JOIN survey_versions v ON v.id=sq.survey_version_id JOIN surveys s ON s.id=v.survey_id WHERE qv.question_id=? ORDER BY v.year,s.name''',(question_id,))]}

def compare(con,first,second):
    a,b=survey_detail(con,first),survey_detail(con,second)
    aa=a['questions'];bb=b['questions'];used=set();changes=[]
    for x in aa:
        y=next((z for z in bb if z['question_id']==x['question_id'] and z['question_version_id'] not in used),None)
        if y is None:y=next((z for z in bb if z['wording']==x['wording'] and z['answer_type']==x['answer_type'] and z['options_json']==x['options_json'] and z['question_version_id'] not in used),None)
        if y:
            used.add(y['question_version_id']);kind='identique' if (x['wording'],x['answer_type'],x['options_json'])==(y['wording'],y['answer_type'],y['options_json']) else 'reformulee_ou_modalites_modifiees'
            changes.append({'type':kind,'before':x,'after':y,'moved':x['position']!=y['position'],'comparable':kind=='identique'})
        else:
            candidate=next((z for z in bb if z['question_version_id'] not in used and difflib.SequenceMatcher(None,norm(x['wording']),norm(z['wording'])).ratio()>=0.65),None)
            if candidate:
                used.add(candidate['question_version_id']);changes.append({'type':'equivalence_a_verifier','before':x,'after':candidate,'moved':x['position']!=candidate['position'],'comparable':False})
            else:changes.append({'type':'supprimee','before':x,'after':None,'comparable':False})
    for y in bb:
        if y['question_version_id'] not in used:changes.append({'type':'ajoutee','before':None,'after':y,'comparable':False})
    return {'first':{'id':first,'name':a['name'],'version':a['version'],'year':a['year']},'second':{'id':second,'name':b['name'],'version':b['version'],'year':b['year']},'changes':changes}

def add_result(con,survey_version_id,question_version_id,period,metric,value,denominator=None,scope='national',source=None):
    if denominator is not None and denominator<0:raise ValueError('Dénominateur négatif')
    rid=uid()
    with con:con.execute('INSERT INTO question_results VALUES(?,?,?,?,?,?,?,?,?)',(rid,survey_version_id,question_version_id,period,scope,metric,value,denominator,source))
    return rid

def history(con,question_id):
    return [dict(r) for r in con.execute('''SELECT s.name survey,s.campaign,v.year,v.version,qv.wording,qv.answer_type,qv.options_json,r.period,r.scope,r.metric,r.value,r.denominator,r.source FROM question_results r JOIN survey_versions v ON v.id=r.survey_version_id JOIN surveys s ON s.id=v.survey_id JOIN question_versions qv ON qv.id=r.question_version_id WHERE qv.question_id=? ORDER BY r.period''',(question_id,))]
