"""Read-only check for ORBITE Questions additionnelles integration."""
from pathlib import Path
import sys

def main(root):
    expected={
        'src/QuestionsWorkspace.tsx':['QuestionsStudio','QuestionsQuickAnalysis'],
        'src/QuestionsStudio.tsx':['qaDashboardExport','qaDashboardSave'],
        'src/QuestionsQuickAnalysis.tsx':['loadResult'],
        'src/questions-audika.css':['qa-root'],
        'backend/orb_q06_bridge.py':['qaDashboardExport','qaHistoricalCatalog'],
        'backend/orb_q_dashboard_export.py':['export_dashboard'],
        'backend/orb_q_history_store.py':['record_review'],
        'backend/orbite_backend.py':['orb_q06_bridge'],
        'electron/preload.cjs':['qaDashboardExport','deleteImport','legacyImportStatus','resetLegacyNps'],
        'backend/requirements.txt':['openpyxl','reportlab'],
        '.github/workflows/consolidation.yml':['orb_q_dashboard_export','orb-q01-q02-questions-historiques'],
    }
    problems=[]
    for rel,needles in expected.items():
        path=root/rel
        if not path.exists():problems.append('Absent : '+rel);continue
        text=path.read_text(encoding='utf-8')
        for needle in needles:
            if needle not in text:problems.append(rel+' : manque '+needle)
    if problems:
        print('\n'.join(problems));return 1
    print('Présence des raccordements vérifiée (pas une validation fonctionnelle).')
    return 0
if __name__=='__main__':
    sys.exit(main(Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()))
