import unittest,os,tempfile,subprocess,sys,json
from pathlib import Path
import orbite_data as d
class Contracts(unittest.TestCase):
 def test_contracts_and_data(self):
  with tempfile.TemporaryDirectory() as t:
   env={**os.environ,'ORBITE_DATA_DIR':t,'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'}
   old=d.DB;d.DB=Path(t)/'orbite.sqlite'
   try:
    c=d.db();c.execute("INSERT INTO centres VALUES('C1','Centre Rhône','NORD/EST','Alsace')")
    q=json.dumps([json.dumps({'question':'Accueil ?','answer':['Très bien']},ensure_ascii=False),'9',None,None,None],ensure_ascii=False)
    rows=[('1','MAIL','Avec Prescription','C1','NORD/EST',10,'Très bien','2026-06-15','2026-06-01',q,'import.xlsx'),('2','SMS','Sans prescription','C1','NORD/EST',6,'À revoir','2026-06-16','2026-06-01',json.dumps([None]*5),'import.xlsx'),('3','MAIL','Avec Prescription','C1','NORD/EST',None,'','', '2026-06-01',json.dumps([None]*5),'import.xlsx')]
    c.executemany('INSERT INTO nps(member_id,campaign,appt_type,clinic,region,score,comment,rating_date,send_date,answers,raw_source) VALUES(?,?,?,?,?,?,?,?,?,?,?)',rows);c.commit();c.close()
    requests=[{'id':1,'method':'health','params':{}},{'id':2,'method':'npsDashboard','params':{'region':'NORD/EST','sector':'Alsace'}},{'id':3,'method':'questionAnalysis','params':{'region':'NORD/EST','sector':'Alsace'}},{'id':4,'method':'filters','params':{}}]
    p=subprocess.run([sys.executable,str(Path(__file__).parent/'orbite_backend.py')],input='\n'.join(json.dumps(r) for r in requests)+'\n',text=True,encoding='utf-8',capture_output=True,env=env,timeout=30)
    self.assertEqual(p.returncode,0,p.stderr)
    output=[json.loads(line) for line in p.stdout.splitlines()]
    self.assertEqual(len(output),4);self.assertFalse(any('error' in x for x in output),output)
    dashboard=output[1]['data'];self.assertEqual(dashboard['global']['reponses'],2);self.assertEqual(dashboard['global']['sollicitations'],3)
    self.assertEqual(dashboard['global']['nps'],0);self.assertEqual(dashboard['campaigns'][0]['campagne'],'OPPS total')
    self.assertEqual(dashboard['timeline'][0]['mois'],'2026-06')
    self.assertEqual(output[2]['data'][0]['wording'],'Accueil ?');self.assertEqual(output[3]['data']['campaigns'],['Avec Prescription','Sans prescription'])
   finally:d.DB=old
if __name__=='__main__':unittest.main()
