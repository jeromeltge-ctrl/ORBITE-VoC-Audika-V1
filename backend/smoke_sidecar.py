"""Check packaged backend methods via stdin/stdout JSON on Windows."""
import os,sys,json,subprocess,tempfile
from pathlib import Path
exe=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory() as tmp:
 env={**os.environ,'ORBITE_DATA_DIR':tmp,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8'}
 req=[{'id':i,'method':method,'params':{}} for i,method in enumerate(('health','npsDashboard','questionAnalysis'),1)]
 p=subprocess.run([str(exe)],input='\n'.join(json.dumps(r) for r in req)+'\n',capture_output=True,text=True,encoding='utf-8',env=env,timeout=90)
 if p.returncode:raise RuntimeError('Backend crash: '+p.stderr[-1000:])
 messages=[json.loads(x) for x in p.stdout.splitlines()]
 if len(messages)!=3 or any('error' in x for x in messages):raise RuntimeError('Backend IPC failed: '+str(messages))
 print('Backend sidecar IPC OK')
