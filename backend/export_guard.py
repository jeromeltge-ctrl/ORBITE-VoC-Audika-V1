"""Protect the historical Excel export without modifying its source template or database."""
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from openpyxl import load_workbook
from openpyxl.workbook.properties import CalcProperties
from engine import Analysis, yearback
from google_view import period_for, stats


def historical_build(*args, **kwargs):
    # Load the workbook-specific implementation only for an actual Excel export.
    from interactive_export import build as original
    return original(*args, **kwargs)


def build(con,template,out,start,end,region='Toutes',sector='Tous'):
    target=Path(out).resolve();template=Path(template).resolve()
    if target.suffix.lower()!='.xlsx':raise ValueError('Destination Excel .xlsx requise')
    protected=[template]+[Path(r[2]).resolve() for r in con.execute('PRAGMA database_list') if r[2]]
    if target in protected:raise ValueError('La destination ne peut pas remplacer le modèle ou une base')
    if not template.is_file():raise FileNotFoundError('Modèle Consolide2 introuvable')
    if con.in_transaction:raise ValueError('Export refusé pendant une transaction non terminée')
    if not target.parent.is_dir():raise ValueError('Dossier de destination introuvable')
    with closing(sqlite3.connect(':memory:')) as scoped:
        con.backup(scoped)
        analysis=Analysis(scoped)
        period,partial=period_for(analysis,{'start':start,'end':end})
        if not period:raise ValueError('Aucune période Google disponible')
        codes=analysis.codes(region or 'Toutes',sector or 'Tous')
        if not codes:raise ValueError('Aucun centre pour ce périmètre')
        # Work on a disposable snapshot only. The existing builder now cannot leak
        # other regions in its detailed sheet or use a national centre denominator.
        with scoped:
            scoped.execute('CREATE TEMP TABLE selected_codes(code TEXT PRIMARY KEY)')
            scoped.executemany('INSERT INTO selected_codes VALUES(?)',[(code,) for code in codes])
            scoped.execute('DELETE FROM centres WHERE code NOT IN (SELECT code FROM selected_codes)')
        a=Analysis(scoped);metrics=stats(a,period,codes)
        with tempfile.TemporaryDirectory(prefix='orbite-export-',dir=target.parent) as td:
            staged=Path(td)/'result.xlsx'
            result=historical_build(scoped,template,staged,period[0],period[-1],region or 'Toutes',sector or 'Tous')
            w=load_workbook(staged)
            try:
                # Preserve the original dashboard sheets, charts and styles.
                # Correct missing-vs-zero display in the historical helper columns.
                last=20+len(a.centers)
                for name in ('01 VUE ENSEMBLE','02 MON SECTEUR','03 MES CENTRES'):
                    sh=w[name]
                    for r in range(21,last+1):
                        for column,count_column in (('V','X'),('W','Y')):
                            formula=sh[f'{column}{r}'].value
                            if isinstance(formula,str) and formula.startswith('='):
                                sh[f'{column}{r}']=f'=IF(OR({count_column}{r}="",{count_column}{r}=0),"",{formula[1:]})'
                view=w['01 VUE ENSEMBLE']
                view['B12']=f'=IF(COUNT(V21:V{last})=0,"N/C",SUM(V21:V{last}))'
                view['F12']=f'=IF(COUNT(W21:W{last})=0,"N/C",SUM(W21:W{last}))'
                # Comparison is unavailable if monthly coverage differs or is provisional.
                if not metrics['comparison_available']:view['J12']='N/C'
                centres=w['03 MES CENTRES']
                for r,values in enumerate(a.centers.values(),22):
                    code,name,reg,sec,_=values
                    def quoted(value):return str(value).replace('"','""')
                    scope=f'AND(OR($B$6="Toutes",$B$6="{quoted(reg)}"),OR($F$6="Tous",$F$6="{quoted(sec)}"))'
                    for col,value in ((2,code),(3,name),(4,reg),(5,sec)):
                        centres.cell(r,col,f'=IF({scope},"{quoted(value)}","")')
                # Detailed export is limited to N and the displayed N-1 comparison.
                details=w['04 DONNÉES DÉTAILLÉES']
                allowed=set(period)|{yearback(m) for m in period}
                for r in range(details.max_row,1,-1):
                    value=details.cell(r,2).value
                    if not hasattr(value,'strftime') or value.strftime('%Y-%m') not in allowed:
                        details.delete_rows(r)
                details.auto_filter.ref=f'A1:I{details.max_row}'
                audit=w.create_sheet('CONTROLES ORBITE')
                audit.append(['Périmètre','Valeur'])
                for key,value in [('Région',region),('Secteur',sector),('Début N',period[0]),('Fin N',period[-1]),('Début N-1',yearback(period[0])),('Fin N-1',yearback(period[-1])),('Résolution mensuelle',True),('Bornes journalières élargies aux mois',partial)]:
                    audit.append([key,str(value)])
                    for cell in audit[audit.max_row]:cell.data_type='s'
                audit.append(['Niveau','Région','Secteur','Code','Centres','Avis N connus','Avis N-1 connus','Évolution','Note pondérée','Sans avis période','Mois manquants N','Mois manquants N-1'])
                def append(level,r,s,code,subset):
                    m=stats(a,period,subset)
                    audit.append([level,r,s,code,m['centres'],m['n'],m['n1'],m['evolution'],m['note'],m['zero_periode'],m['missing_n'],m['missing_n1']])
                    for cell in list(audit[audit.max_row])[:4]:cell.data_type='s'
                append('TOTAL',region,sector,'',codes)
                for r in sorted({a.centers[c][2] for c in codes}):
                    subset=[c for c in codes if a.centers[c][2]==r];append('REGION',r,'','',subset)
                    for s in sorted({a.centers[c][3] for c in subset}):
                        append('SECTEUR',r,s,'',[c for c in subset if a.centers[c][3]==s])
                for code in codes:append('CENTRE',a.centers[code][2],a.centers[code][3],code,[code])
                audit.append(['Les volumes connus peuvent être incomplets ; les colonnes de couverture distinguent les absences des zéros.'])
                audit.freeze_panes='A11'
                w.calculation=CalcProperties(calcMode='auto',fullCalcOnLoad=True,forceFullCalc=True)
                w.save(staged)
            finally:w.close()
            with closing(load_workbook(staged,read_only=True)) as check:
                if 'CONTROLES ORBITE' not in check.sheetnames:raise ValueError('Export incomplet')
            backup=None
            if target.exists():
                backup=target.with_name(target.stem+'-avant-export-'+datetime.now().strftime('%Y%m%d%H%M%S%f')+'-'+uuid4().hex+target.suffix)
                shutil.copy2(target,backup)
            os.replace(staged,target)
        return {**result,'path':str(target),'backup':str(backup) if backup else None,
                'period':period,'comparison_period':[yearback(m) for m in period],
                'partial_boundaries':partial,'missing_n':metrics['missing_n'],'missing_n1':metrics['missing_n1'],
                'formula_recalculation_required':True}
