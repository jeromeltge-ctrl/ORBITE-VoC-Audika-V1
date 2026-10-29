"""Native ORBITE adapter to the unchanged historical Audika Google engine.
No Tkinter, no second executable. Google data stays isolated in google.sqlite.
"""
import hashlib,os,sqlite3,shutil,tempfile
from pathlib import Path
from datetime import datetime
from openpyxl import load_workbook
from engine import setup,import_ref,import_history,import_uberall,Analysis,months,month
from interactive_export import build

FIELDS={
 'referentiel':['Code centre','Nom centre','Région','Secteur'],
 'historique':['Année','Mois (fin de mois)','Code centre','Nom centre','Adresse','Note cumulée','Nombre cumulé'],
 'uberall':['Code centre','Nom centre','Adresse','Note du mois','Nouveaux avis du mois']
}
DEFAULTS={
 'referentiel':['CODE CENTRE','NOM CENTRE','REGION AUDIK@NET','NOM SECTEUR'],
 'historique':['Année A','Date','Code centre','Nom du centre','Adresse','Note moyenne','Nombre de note'],
 'uberall':['Location Identifier','Location Name','Address','Average Rating','Total Rating']
}

def connect(data_dir):
 base=Path(data_dir);base.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(base/'google.sqlite',timeout=30);setup(c);return c

def workbook(path):
 p=Path(path)
 if not p.is_file() or p.suffix.lower()!='.xlsx':raise ValueError('Fichier Excel .xlsx requis')
 return load_workbook(p,read_only=True,data_only=True)

def inspect(path,kind):
 if kind not in FIELDS:raise ValueError('Type d’import inconnu')
 w=workbook(path)
 try:
  it=w.active.iter_rows(values_only=True)
  header=[str(x or '') for x in next(it)]
  sample=[]
  for row in it:
   if any(v is not None and str(v).strip() for v in row):sample.append([str(v)[:100] if v is not None else '' for v in row[:len(header)]])
   if len(sample)==4:break
  return {'kind':kind,'headers':header,'fields':FIELDS[kind],'suggested':{f:(DEFAULTS[kind][i] if DEFAULTS[kind][i] in header else '') for i,f in enumerate(FIELDS[kind])},'sample':sample,'size':Path(path).stat().st_size,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
 finally:w.close()

def mapped_rows(path,kind,mapping):
 w=workbook(path)
 try:
  it=w.active.iter_rows(values_only=True);headers=[str(x or '') for x in next(it)]
  indices=[]
  for field in FIELDS[kind]:
   name=mapping.get(field)
   if name not in headers:raise ValueError('Colonne manquante pour '+field)
   indices.append(headers.index(name))
  if len(set(indices))!=len(indices):raise ValueError('Colonnes associées en double')
  if kind=='uberall':next(it,None) # historical app skips explanatory second row
  for row in it:
   if row and any(v is not None and str(v).strip() for v in row):
    yield tuple(row[i] if i<len(row) else None for i in indices)
 finally:w.close()

def import_file(data_dir,params):
 kind=params['kind'];path=params['path'];mapping=params['mapping']
 if kind not in FIELDS:raise ValueError('Type inconnu')
 if not params.get('confirm'):raise ValueError('Validation explicite requise')
 if params.get('sha256')!=inspect(path,kind)['sha256']:raise ValueError('Fichier modifié depuis sa prévisualisation')
 base=Path(data_dir);base.mkdir(parents=True,exist_ok=True);c=connect(base)
 # Backup BEFORE writing. The historical engine is intentionally unchanged.
 backup=base/('google-backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.sqlite')
 try:
  c.commit();snapshot=sqlite3.connect(backup)
  try:c.backup(snapshot)
  finally:snapshot.close()
  records=mapped_rows(path,kind,mapping)
  if kind=='referentiel':result=import_ref(c,records)
  elif kind=='historique':result=import_history(c,records)
  else:
   if not params.get('start') or not params.get('end'):raise ValueError('Dates Uberall requises')
   result=import_uberall(c,records,params['start'],params['end'],bool(params.get('replace',False)))
  return {'result':result,'backup':str(backup),'kind':kind}
 finally:c.close()

def summary(data_dir,params):
 c=connect(data_dir)
 try:
  a=Analysis(c)
  if not a.centers or not a.snap:return {'available':False,'message':'Importer référentiel et historique Google'}
  period=months(params.get('start') or '2026-01',params.get('end') or '2026-10')
  reg=params.get('region') or 'Toutes';sector=params.get('sector') or 'Tous'
  if reg=='':reg='Toutes'
  if sector=='':sector='Tous'
  codes=a.codes(reg,sector);stats=a.stats(period,codes)
  regions=sorted({x[2] for x in a.centers.values()});sectors=sorted({x[3] for x in a.centers.values() if reg=='Toutes' or x[2]==reg})
  return {'available':True,**stats,'regions':[{'name':r,**a.stats(period,a.codes(r))} for r in regions], 'sectors':[{'name':s,**a.stats(period,a.codes(reg,s))} for s in sectors],'period':period,'source':'engine.py historique'}
 finally:c.close()

def export(data_dir,params,template):
 if not params.get('path'):raise ValueError('Chemin export requis')
 c=connect(data_dir)
 try:
  return build(c,template,params['path'],month(params['start']),month(params['end']),params.get('region') or 'Toutes',params.get('sector') or 'Tous')
 finally:c.close()
