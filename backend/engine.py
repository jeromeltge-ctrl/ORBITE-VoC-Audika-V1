"""Audika E-reputation V10: separate cumulative history from Uberall monthly flows."""
import sqlite3,calendar
from datetime import datetime,date

def month(m):
 if isinstance(m,(date,datetime)):return m.strftime('%Y-%m')
 for fmt in ('%Y-%m','%Y-%m-%d','%d/%m/%Y'):
  try:return datetime.strptime(str(m).strip(),fmt).strftime('%Y-%m')
  except ValueError:pass
 raise ValueError('Mois invalide')
def prev(m):
 y,n=map(int,m.split('-'));return f'{y-1}-12' if n==1 else f'{y}-{n-1:02d}'
def yearback(m):return f'{int(m[:4])-1}-{m[5:]}'
def months(a,b):
 a,b=month(a),month(b)
 if a>b:raise ValueError('Dates inversées')
 y,n=map(int,a.split('-'));out=[]
 while f'{y}-{n:02d}'<=b:
  out.append(f'{y}-{n:02d}');y,n=(y+1,1) if n==12 else (y,n+1)
 return out

def setup(con):
 con.executescript('''CREATE TABLE IF NOT EXISTS centres(code TEXT PRIMARY KEY,nom TEXT,region TEXT,secteur TEXT,adresse TEXT);
 CREATE TABLE IF NOT EXISTS historique(code TEXT,mois TEXT,cumul INTEGER,note REAL,PRIMARY KEY(code,mois));
 CREATE TABLE IF NOT EXISTS uberall(code TEXT,mois TEXT,avis INTEGER,note REAL,complete INTEGER,start TEXT,end TEXT,PRIMARY KEY(code,mois));
 CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,source TEXT,mois TEXT,created TEXT,filename TEXT,imported INTEGER,ignored INTEGER);
 CREATE TABLE IF NOT EXISTS changements(id INTEGER PRIMARY KEY,code TEXT,champ TEXT,ancien TEXT,nouveau TEXT,date TEXT);''')

def norm_num(v):
 if v is None or str(v).strip()=='':return 0
 x=float(str(v).replace(' ','').replace(',','.'))
 if x<0 or x!=int(x):raise ValueError('Nombre invalide')
 return int(x)
def norm_note(v):
 if v is None or str(v).strip().upper() in ('','N/A','NA'):return None
 x=float(str(v).replace(',','.'))
 if x==0:return None
 if not 1<=x<=5:raise ValueError('Note hors 1-5')
 return x

def import_ref(con,records):
 staged={}
 for code,name,region,secteur,*rest in records:
  code=str(code or '').strip().upper()
  if not code:continue
  if code in staged:raise ValueError('Code centre en doublon: '+code)
  staged[code]=(code,str(name or ''),str(region or ''),str(secteur or ''),str(rest[0] or '') if rest else '')
 if not staged:raise ValueError('Référentiel vide')
 existing={r[0]:r for r in con.execute('SELECT code,nom,region,secteur,adresse FROM centres')}
 changes=[]
 for code,new in staged.items():
  if code in existing:
   for j,label in enumerate(['nom','region','secteur','adresse'],1):
    if new[j]!=existing[code][j]:changes.append((code,label,existing[code][j],new[j],datetime.now().isoformat(timespec='seconds')))
 with con:
  con.executemany('INSERT OR REPLACE INTO centres VALUES(?,?,?,?,?)',staged.values())
  con.executemany('INSERT INTO changements(code,champ,ancien,nouveau,date) VALUES(?,?,?,?,?)',changes)
  con.execute('DELETE FROM centres WHERE code NOT IN ('+','.join('?' for _ in staged)+')',tuple(staged))
 return {'centres':len(staged),'changes':len(changes),'removed':len(set(existing)-set(staged))}

def import_history(con,records):
 known={r[0] for r in con.execute('SELECT code FROM centres')};staged={};ignored=0
 for year,m,code,name,address,note,cumul in records:
  code=str(code or '').strip().upper()
  if code not in known:ignored+=1;continue
  m=month(m)
  if str(year)[:4]!=m[:4]:raise ValueError('Année et mois incohérents')
  key=(code,m)
  if key in staged:raise ValueError('Doublon historique '+str(key))
  staged[key]=(code,m,norm_num(cumul),norm_note(note))
 with con:con.executemany('INSERT OR REPLACE INTO historique VALUES(?,?,?,?)',staged.values())
 return {'imported':len(staged),'ignored':ignored}

def import_uberall(con,records,start,end,replace=False):
 a=datetime.strptime(start,'%d/%m/%Y').date();b=datetime.strptime(end,'%d/%m/%Y').date()
 if a>b or a.year!=b.year or a.month!=b.month or a.day!=1:raise ValueError('Extraction attendue du 1er jour à une date du même mois')
 m=a.strftime('%Y-%m');complete=b.day==calendar.monthrange(b.year,b.month)[1]
 known={r[0] for r in con.execute('SELECT code FROM centres')};staged={};ignored=0
 for code,name,address,note,avis in records:
  code=str(code or '').strip().upper()
  if code not in known:ignored+=1;continue
  if code in staged:raise ValueError('Doublon Uberall '+code)
  staged[code]=(code,m,norm_num(avis),norm_note(note),int(complete),a.isoformat(),b.isoformat())
 if not staged:raise ValueError('Aucun centre reconnu')
 existing=con.execute('SELECT COUNT(*) FROM uberall WHERE mois=?',(m,)).fetchone()[0]
 if existing and not replace:raise ValueError('Période déjà importée : remplacement explicite nécessaire')
 with con:
  if existing:con.execute('DELETE FROM uberall WHERE mois=?',(m,))
  con.executemany('INSERT INTO uberall VALUES(?,?,?,?,?,?,?)',staged.values())
 return {'imported':len(staged),'ignored':ignored,'complete':complete,'month':m,'replaced':bool(existing)}

class Analysis:
 def __init__(self,con):
  self.centers={r[0]:r for r in con.execute('SELECT code,nom,region,secteur,adresse FROM centres')}
  self.h={(c,m):(n,r) for c,m,n,r in con.execute('SELECT code,mois,cumul,note FROM historique') if c in self.centers}
  self.u={(c,m):(n,r,bool(ok)) for c,m,n,r,ok in con.execute('SELECT code,mois,avis,note,complete FROM uberall') if c in self.centers}
  self.snap=dict(self.h)
  for c,m in sorted(self.u,key=lambda x:(x[0],x[1])):
   if (c,m) in self.h:continue
   old=self.snap.get((c,prev(m)))
   if old is None:continue
   n,r,complete=self.u[c,m];total=old[0]+n
   score=(None if total==0 else old[1] if n==0 else r if old[0]==0 else ((old[0]*old[1]+n*r)/total if old[1] is not None and r is not None else None))
   self.snap[c,m]=(total,score)
 def codes(self,reg='Toutes',sector='Tous'):
  return [c for c,v in self.centers.items() if (reg=='Toutes' or v[2]==reg) and (sector=='Tous' or v[3]==sector)]
 def delta(self,c,m):
  if (c,m) in self.u:
   return self.u[c,m][0]  # Partial months remain provisional, not discarded
  a=self.snap.get((c,m));b=self.snap.get((c,prev(m)))
  if not a or not b:return None
  n=a[0]-b[0];return n if n>=0 else None
 def comparable(self,c,period):
  x=[self.delta(c,m) for m in period];y=[self.delta(c,yearback(m)) for m in period]
  return (sum(x),sum(y)) if all(v is not None for v in x+y) else None
 def stats(self,period,codes):
  codes=list(codes);end=period[-1]
  nvals=[self.delta(c,m) for c in codes for m in period]
  pvals=[self.delta(c,yearback(m)) for c in codes for m in period]
  n=sum(x for x in nvals if x is not None);p=sum(x for x in pvals if x is not None)
  good=[pair for c in codes if (pair:=self.comparable(c,period)) is not None]
  ratings=[self.snap[c,end] for c in codes if (c,end) in self.snap and self.snap[c,end][0]>0 and self.snap[c,end][1] is not None]
  return {'n':n,'n1':p,'evolution':(n/p-1 if p else None),'comparable':len(good),
          'centres':len(codes),'note':(sum(x*y for x,y in ratings)/sum(x for x,y in ratings) if ratings else None),
          'moyenne':(n/len(codes)/len(period) if codes and period else None),
          'zero_total':sum((c,end) in self.snap and self.snap[c,end][0]==0 for c in codes),
          'zero_periode':sum(all(self.delta(c,m) is not None for m in period) and all(self.delta(c,m)==0 for m in period) for c in codes),
          'missing_n':sum(x is None for x in nvals),'missing_n1':sum(x is None for x in pvals),
          'partial_months':sorted({m for c in codes for m in period if (c,m) in self.u and not self.u[c,m][2]})}
