import sys,os,json,sqlite3,csv,traceback
from pathlib import Path
os.environ.setdefault('ORBITE_DATA_DIR',str(Path.home()/'.orbite-voc'))
import orbite_data as d
import survey_library as lib
import nps_analytics as npsa
import question_analytics as qa
import ereputation_bridge as er
import network_analytics as net
root=Path(os.environ['ORBITE_DATA_DIR']);root.mkdir(parents=True,exist_ok=True);d.BASE=root;d.DB=root/'orbite.sqlite'

def filters(p):return {k:str(p.get(k) or '') for k in ['region','sector','campaign','start','end']}
def records(c,p):return d.filtered(c,**filters(p))
def safe(r):return dict(r)
def run(method,p):
 if method=='googleInspect':return er.inspect(p['path'],p['kind'])
 if method=='googleImport':return er.import_file(root,p)
 if method=='googleSummary':return er.summary(root,p)
 if method=='googleExport':return er.export(root,p,Path(os.environ.get('ORBITE_MODEL_PATH',str(Path(__file__).resolve().parent/'modele_consolide2.xlsx'))))
 if method=='health':
  c=d.db()
  try:return {'status':'ok','nps_rows':c.execute('SELECT COUNT(*) FROM nps').fetchone()[0]}
  finally:c.close()
 if method=='importReference':return {'centres':d.import_reference(p['path'])}
 if method=='importNps':return d.import_nps(p['path'])
 if method=='publish':return {'path':str(d.publish(p['path']))}
 if method=='loadPublication':return d.load_publication(p['path'])
 if method=='exportVerbatims':
  c=d.db();rows=records(c,p);search=str(p.get('search') or '').casefold()
  with open(p['path'],'w',newline='',encoding='utf-8-sig') as f:
   w=csv.writer(f,delimiter=';');w.writerow(['Date','Campagne','Centre','Score','Commentaire'])
   for r in rows:
    if search in r['comment'].casefold():w.writerow([r['rating_date'],r['appt_type'],r['clinic'],r['score'],r['comment']])
  c.close();return {'exported':len(rows),'path':p['path']}
 if method=='exportEreputation':
  # Do not simulate a historical report: the engine requires validated source imports.
  raise ValueError("L'export Excel historique nécessite les fichiers d'entrée et paramètres du moteur e-réputation V10. Le classeur original est préservé dans le projet.")
 c=d.db()
 try:
  if method=='filters':
   return {'regions':[x[0] for x in c.execute("SELECT DISTINCT region FROM centres WHERE region<>'' ORDER BY region")], 'sectors':[{'name':x[0],'region':x[1]} for x in c.execute("SELECT DISTINCT sector,region FROM centres WHERE sector<>'' ORDER BY sector")], 'centres':[dict(x) for x in c.execute('SELECT code,name,region,sector FROM centres ORDER BY name')], 'campaigns':[x[0] for x in c.execute("SELECT DISTINCT appt_type FROM nps WHERE appt_type<>'' ORDER BY appt_type")]}
  if method=='npsDashboard':
   current=records(c,p);prior_filter=npsa.previous(p);prior=records(c,prior_filter) if prior_filter else None
   return npsa.dashboard(current,prior,prior_filter)
  if method=='questionAnalysis':return qa.analyze(records(c,p),p.get('search',''))
  if method=='questionHistory':return [x for x in qa.analyze(records(c,p)) if x['wording']==p.get('wording')]
  if method=='questionProfile':return lib.question_detail(c,p['id'])
  if method=='questionResults':return lib.history(c,p['id'])
  if method=='summary':
   rows=records(c,p);m=d.metrics(rows);m['centres']=c.execute('SELECT COUNT(*) FROM centres WHERE (?="" OR region=?) AND (?="" OR sector=?)',(p.get('region',''),p.get('region',''),p.get('sector',''),p.get('sector',''))).fetchone()[0]
   m['google_note']=None;m['google_reviews']=None;return m
  if method=='campaigns':
   rows=records(c,p);return [{'name':name,**d.metrics([r for r in rows if r['appt_type']==name])} for name in sorted({r['appt_type'] for r in rows})]
  if method=='timeline':
   grouped={}
   for r in records(c,p):
    dt=(r['rating_date'] if r['score'] is not None else '')[:7]
    if dt:grouped.setdefault(dt,[]).append(r)
   return [{'month':key,**d.metrics(grouped[key])} for key in sorted(grouped)]
  if method=='verbatims':
   search=str(p.get('search') or '').casefold();rows=[r for r in records(c,p) if search in (r['comment'] or '').casefold()]
   rows.sort(key=lambda r:r['rating_date'] or r['send_date'],reverse=True)
   offset=max(0,int(p.get('offset') or 0));limit=min(200,max(1,int(p.get('limit') or 30)))
   return {'total':len(rows),'items':[safe(x) for x in rows[offset:offset+limit]]}
  if method=='network':
   prior=npsa.previous(p)
   return net.build(c,records(c,p),records(c,prior) if prior else None,p.get('region',''),p.get('sector',''))
  if method=='questions':return lib.list_surveys(c,search=p.get('search',''),campaign=p.get('campaign') or None,year=int(p['year']) if p.get('year') else None,status=p.get('status') or None)
  if method=='surveyDetail':return lib.survey_detail(c,p['id'])
  if method=='compareSurveys':return lib.compare(c,p['first'],p['second'])
  if method=='surveyCreate':
   # Explicitly supplied, authenticated metadata only; no invented historical record.
   sid=lib.add_survey(c,p['campaign'],p['name']);vid=lib.add_version(c,sid,p['version'],p.get('year'),p.get('start'),p.get('end'),status=p.get('status','preparation'),source=p.get('source'))
   ids=[]
   for q in p['questions']:
    _,qid=lib.add_question(c,q['wording'],q.get('type'),q.get('options'));ids.append(qid)
   lib.set_questions(c,vid,ids);return {'survey':sid,'version':vid}
  if method=='imports':return [dict(x) for x in c.execute('SELECT * FROM imports ORDER BY id DESC LIMIT 100')]
  raise ValueError('Méthode inconnue : '+method)
 finally:c.close()

if __name__=='__main__':
 for line in sys.stdin:
  try:
   req=json.loads(line);data=run(req['method'],req.get('params') or {});response={'id':req.get('id'),'data':data}
  except Exception as e:response={'id':req.get('id') if 'req' in locals() else None,'error':str(e)}
  sys.stdout.write(json.dumps(response,ensure_ascii=False,default=str)+'\n');sys.stdout.flush()
