import sqlite3, json, hashlib, shutil, zipfile, os, tempfile
from pathlib import Path
from datetime import datetime
from openpyxl import load_workbook
from survey_library import connect as survey_connect
import import_deletion
BASE=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'ORBITEVoC';BASE.mkdir(parents=True,exist_ok=True)
DB=BASE/'orbite.sqlite'
def db():
 c=survey_connect(DB)
 c.executescript('''CREATE TABLE IF NOT EXISTS centres(code TEXT PRIMARY KEY,name TEXT,region TEXT,sector TEXT);
 CREATE TABLE IF NOT EXISTS nps(member_id TEXT PRIMARY KEY,campaign TEXT,appt_type TEXT,clinic TEXT,region TEXT,score INTEGER,comment TEXT,rating_date TEXT,send_date TEXT,answers TEXT,raw_source TEXT);
 CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,filename TEXT,at TEXT,added INTEGER,skipped INTEGER);
 CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);''')
 import_deletion.ensure(c)
 return c

def import_reference(path):
 w=load_workbook(path,read_only=True,data_only=True);rows=w.active.iter_rows(values_only=True);head=[str(x or '').strip().upper() for x in next(rows)];indexes=[head.index(x) for x in ['CODE CENTRE','NOM CENTRE','REGION AUDIK@NET','NOM SECTEUR']];found={}
 for r in rows:
  v=[str(r[i] or '').strip() for i in indexes];code=v[0].upper()
  if code and code not in ('CODE CENTRE','NONE'):
   if code in found and found[code]!=tuple(v):raise ValueError('Code centre contradictoire : '+code)
   found[code]=(code,*v[1:])
 w.close()
 if not found:raise ValueError('Référentiel vide')
 c=db()
 with c:
  c.execute('DELETE FROM centres');c.executemany('INSERT INTO centres VALUES(?,?,?,?)',found.values());c.execute('INSERT INTO imports(kind,filename,at,added,skipped) VALUES(?,?,?,?,?)',('referentiel',Path(path).name,datetime.now().isoformat(),len(found),0))
 c.close();return len(found)

def import_nps(path):
 w=load_workbook(path,read_only=True,data_only=True);it=w.active.iter_rows(values_only=True);head=[str(x or '') for x in next(it)];needed=['CampaignMemberId','Rating','CampaignName','custom_clinic_id'];missing=[x for x in needed if x not in head]
 if missing:raise ValueError('Colonnes manquantes : '+', '.join(missing))
 c=db();valid={x[0] for x in c.execute('SELECT code FROM centres')};added=skipped=unmapped=0
 import_deletion.ensure(c)
 with c:
  new_import=c.execute('INSERT INTO imports(kind,filename,at,added,skipped) VALUES(?,?,?,?,?)',('nps',Path(path).name,datetime.now().isoformat(),0,0)).lastrowid
  c.execute('INSERT INTO tracked_nps_imports(import_id) VALUES(?)',(new_import,))
  for row in it:
   d=dict(zip(head,row));mid=d.get('CampaignMemberId')
   if mid is None:continue
   clinic=str(d.get('custom_clinic_id') or '').strip().upper()
   if valid and clinic not in valid:unmapped+=1;continue
   rating=d.get('Rating');score=None
   if rating not in (None,''):
    try:
     score=int(rating)
     if score!=float(rating) or not 0<=score<=10:raise ValueError()
    except (ValueError,TypeError):skipped+=1;continue
   def iso(x):return x.isoformat() if hasattr(x,'isoformat') else str(x or '')
   vals=(str(mid),str(d.get('CampaignName') or ''),str(d.get('custom_appointment_type') or ''),clinic,str(d.get('custom_region_name') or ''),score,str(d.get('UserComment') or ''),iso(d.get('RatingTime')),iso(d.get('SurveySendTime')),json.dumps([d.get('Answer'+str(i)) for i in range(1,6)],ensure_ascii=False,default=str),Path(path).name)
   cur=c.execute('INSERT OR IGNORE INTO nps(member_id,campaign,appt_type,clinic,region,score,comment,rating_date,send_date,answers,raw_source,import_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(*vals,new_import))
   if cur.rowcount:added+=1
   else:skipped+=1
  c.execute('UPDATE imports SET added=?,skipped=? WHERE id=?',(added,skipped+unmapped,new_import))
 c.close();w.close();return {'added':added,'ignored':skipped,'outside_reference':unmapped}

def filtered(c,region='',sector='',campaign='',start='',end=''):
 sql='SELECT n.* FROM nps n LEFT JOIN centres ct ON ct.code=n.clinic WHERE 1=1';args=[]
 for field,value in [('ct.region',region),('ct.sector',sector),('n.appt_type',campaign)]:
  if value:sql+=' AND '+field+'=?';args.append(value)
 if start:sql+=' AND substr(COALESCE(NULLIF(n.rating_date,\'\'),n.send_date),1,10)>=?';args.append(start)
 if end:sql+=' AND substr(COALESCE(NULLIF(n.rating_date,\'\'),n.send_date),1,10)<=?';args.append(end)
 return list(c.execute(sql,args))

def metrics(rows):
 total=len(rows);valid=[r['score'] for r in rows if r['score'] is not None];p=sum(x>=9 for x in valid);d=sum(x<=6 for x in valid)
 return {'total':total,'answered':len(valid),'response_rate':100*len(valid)/total if total else None,'nps':100*(p-d)/len(valid) if valid else None,'comments':sum(bool(r['comment'].strip()) for r in rows),'promoters':p,'passives':sum(7<=x<=8 for x in valid),'detractors':d}

def publish(path):
 c=db();c.close();manifest={'format':'ORBITEVoC','schema':1,'created':datetime.now().isoformat()}
 with tempfile.TemporaryDirectory() as td:
  snap=Path(td)/'orbite.sqlite';src=sqlite3.connect(DB);dst=sqlite3.connect(snap);src.backup(dst);src.close();dst.close();manifest['sha256']=hashlib.sha256(snap.read_bytes()).hexdigest()
  with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.write(snap,'orbite.sqlite');z.writestr('manifest.json',json.dumps(manifest))
 return path

def load_publication(path):
 with zipfile.ZipFile(path) as z:
  if sorted(z.namelist())!=['manifest.json','orbite.sqlite']:raise ValueError('Publication invalide')
  meta=json.loads(z.read('manifest.json'))
  if meta.get('format')!='ORBITEVoC' or meta.get('schema')!=1:raise ValueError('Version incompatible')
  payload=z.read('orbite.sqlite')
  if hashlib.sha256(payload).hexdigest()!=meta.get('sha256'):raise ValueError('Empreinte invalide')
  with tempfile.TemporaryDirectory() as td:
   tmp=Path(td)/'db.sqlite';tmp.write_bytes(payload);check=sqlite3.connect(tmp)
   if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Base corrompue')
   check.close()
   if DB.exists():shutil.copy2(DB,BASE/'orbite-before-publication.sqlite')
   os.replace(tmp,DB)
 return meta
