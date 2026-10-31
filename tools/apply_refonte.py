"""Fail-closed additive integration into a local ORBITE checkout.
Does not overwrite consolidated backend or main application.
"""
from pathlib import Path
import sys

ROUTES="""    # QA v2: immutable history, scoped multiselect analysis and matching exports.
    if method in ('qaHistoricalCatalog','qaFilterOptions','qaQuickResult','qaDashboardExport'):
        import orb_q_analysis_v2 as qa_v2
        if method=='qaHistoricalCatalog':return qa_v2.historical_catalog(c)
        if method=='qaFilterOptions':return qa_v2.filter_options(c)
        if method=='qaQuickResult':
            return qa_v2.analyze_occurrence(c,p['episode_id'],p['occurrence_id'],p)
        return qa_v2.dashboard_export(c,p['path'],p.get('title') or 'ORBITE Studio',p['configuration'])
"""

def main(root):
    backend=root/'backend'/'orb_q06_bridge.py'
    preload=root/'electron'/'preload.cjs'
    router=root/'backend'/'orbite_backend.py'
    workflow=root/'.github'/'workflows'/'consolidation.yml'
    for p in (backend,preload,router,workflow):
        if not p.exists():raise FileNotFoundError(p)
    original=backend.read_text(encoding='utf-8')
    bridge=preload.read_text(encoding='utf-8')
    routing=router.read_text(encoding='utf-8')
    ci=workflow.read_text(encoding='utf-8')
    if 'def handle(c,method,p):' not in original:raise RuntimeError('Bridge contract changed: no files modified')
    if 'qaDashboardExport' not in bridge:raise RuntimeError('Missing Lot 4 preload: no files modified')
    if 'orb_q06_bridge' not in routing:raise RuntimeError('Backend router is not connected: no files modified')
    if '--hidden-import' not in ci or 'orb_q06_bridge' not in ci:
        raise RuntimeError('Workflow PyInstaller structure changed: no files modified')
    if 'qaFilterOptions' not in bridge:
        anchor="'qaHistoricalCatalog'"
        if anchor not in bridge:raise RuntimeError('Preload allowlist changed: no files modified')
        bridge=bridge.replace(anchor,"'qaFilterOptions',"+anchor,1)
    if '# QA v2: immutable history' not in original:
        original=original.replace('def handle(c,method,p):\n','def handle(c,method,p):\n'+ROUTES,1)
    if 'orb_q_analysis_v2' not in ci:
        anchor="'--hidden-import','orb_q06_bridge'"
        if anchor in ci:
            ci=ci.replace(anchor,anchor+",'--hidden-import','orb_q_analysis_v2'",1)
        else:
            anchor='--hidden-import orb_q06_bridge'
            if anchor not in ci:raise RuntimeError('Workflow hidden-import anchor missing: no files modified')
            ci=ci.replace(anchor,anchor+' --hidden-import orb_q_analysis_v2',1)
    if 'test_orb_q_analysis_v2' not in ci:
        anchor='test_orb_q06_bridge'
        if anchor not in ci:raise RuntimeError('Workflow test anchor missing: no files modified')
        ci=ci.replace(anchor,anchor+' test_orb_q_analysis_v2 test_orb_q_dashboard_export_v2',1)
    backend.write_text(original,encoding='utf-8')
    preload.write_text(bridge,encoding='utf-8')
    workflow.write_text(ci,encoding='utf-8')
    print('Patched QA bridge and preload. Inspect git diff and run full CI.')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python tools/apply_refonte.py <repo-root>')
    main(Path(sys.argv[1]).resolve())
