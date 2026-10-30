"""Apply small, fail-closed integration patches to an ORBITE checkout.
Usage: python tools/apply_q06.py <path-to-repository>
"""
import sys
from pathlib import Path

def inject(path,needle,replacement):
    text=path.read_text(encoding='utf-8')
    if replacement in text:return 'already applied'
    if text.count(needle)!=1:raise RuntimeError(f'Cannot safely patch {path}: anchor missing or ambiguous')
    path.write_text(text.replace(needle,replacement+needle),encoding='utf-8')
    return 'patched'

def main(repo):
    backend=repo/'backend'/'orbite_backend.py'
    preload=repo/'electron'/'preload.cjs'
    main_ts=repo/'src'/'main.tsx'
    for p in (backend,preload,main_ts):
        if not p.exists():raise FileNotFoundError(p)
    # Preflight all anchors before writing any file.
    b0=backend.read_text(encoding='utf-8');p0=preload.read_text(encoding='utf-8');m0=main_ts.read_text(encoding='utf-8')
    if 'import question_analytics as qa' not in b0 or (" if method=='googleInspect':" not in b0 and "if method.startswith('qa')" not in b0):
        raise RuntimeError('Backend has changed: inspect patch manually')
    if 'const allowed=new Set([' not in p0:
        raise RuntimeError('Preload allowlist has changed')
    if "import SurveyLibrary from './SurveyLibrary';" not in m0 or ('{tab===2&&<SurveyLibrary filters={f} onError={setMessage}/>}' not in m0 and '<QuestionsWorkspace filters={f}' not in m0):
        raise RuntimeError('React navigation has changed: inspect patch manually')
    text=b0
    if 'import orb_q06_bridge as q06' not in text:
        text=text.replace('import question_analytics as qa','import question_analytics as qa\nimport orb_q06_bridge as q06',1)
    if "if method.startswith('qa')" not in text:
        needle=" if method=='googleInspect':"
        if needle not in text:raise RuntimeError('Backend dispatch anchor not found')
        text=text.replace(needle," if method.startswith('qa'):"+"\n  c=d.db()\n  try:return q06.handle(c,method,p)\n  finally:c.close()\n"+needle,1)
    backend.write_text(text,encoding='utf-8')
    req=repo/'backend'/'requirements.txt'
    requirements=req.read_text(encoding='utf-8')
    if 'reportlab' not in requirements:
        req.write_text(requirements.rstrip()+'\nreportlab>=4,<5\n',encoding='utf-8')
    text=preload.read_text(encoding='utf-8')
    methods="'qaHistoricalCatalog','qaQuickResult','qaDashboardSave','qaDashboardList','qaDashboardLoad','qaDashboardDuplicate','qaDashboardDelete','qaStatistics','qaExport',"
    if "'qaHistoricalCatalog'" not in text:
        needle='const allowed=new Set(['
        if needle not in text:raise RuntimeError('preload allowlist not found')
        text=text.replace(needle,needle+methods,1)
        preload.write_text(text,encoding='utf-8')
    text=main_ts.read_text(encoding='utf-8')
    if "import QuestionsWorkspace from './QuestionsWorkspace'" not in text
        text=text.replace("import SurveyLibrary from './SurveyLibrary';","import SurveyLibrary from './SurveyLibrary';\nimport QuestionsWorkspace from './QuestionsWorkspace';",1)
    old='{tab===2&&<SurveyLibrary filters={f} onError={setMessage}/>}'
    new='{tab===2&&<QuestionsWorkspace filters={f} onError={setMessage} Legacy={SurveyLibrary}/>}'
    if new not in text:
        if old not in text:raise RuntimeError('SurveyLibrary mount not found; inspect main.tsx manually')
        text=text.replace(old,new,1)
    main_ts.write_text(text,encoding='utf-8')
    print('Applied Q06 bridge to backend, preload and React navigation. Inspect git diff and run CI.')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python tools/apply_q06.py <repo>')
    main(Path(sys.argv[1]).resolve())
