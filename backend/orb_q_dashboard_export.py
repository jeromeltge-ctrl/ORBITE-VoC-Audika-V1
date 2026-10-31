"""ORBITE QA: complete dashboard exports, filtered series, deterministic sorting."""
from pathlib import Path
from datetime import datetime,timezone


def safe(value):
    text=str(value if value is not None else '')
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text


def sorted_distribution(distribution,mode):
    rows=list(distribution or [])
    if mode=='original':return rows
    if mode in ('percent-desc','percent-asc'):
        return sorted(rows,key=lambda r:((r.get('percent') if r.get('percent') is not None else (-1 if mode.endswith('desc') else 101)),r.get('label','')),reverse=mode.endswith('desc'))
    if mode in ('count-desc','count-asc'):
        return sorted(rows,key=lambda r:(r.get('count',0),r.get('label','')),reverse=mode.endswith('desc'))
    if mode in ('alpha-desc','alpha-asc'):
        return sorted(rows,key=lambda r:r.get('label','').casefold(),reverse=mode.endswith('desc'))
    return rows


def export_dashboard(path,title,configuration,series_results):
    target=Path(path).expanduser().resolve()
    if target.suffix.lower() not in ('.xlsx','.pdf'):raise ValueError('Format non pris en charge')
    if not isinstance(configuration,dict) or not isinstance(configuration.get('widgets'),list):raise ValueError('Configuration invalide')
    widgets=configuration['widgets']
    if len(widgets)>100:raise ValueError('Trop de widgets')
    rows=[]
    for widget in widgets:
        for i,series in enumerate(widget.get('series',[]),1):
            key=series.get('id');result=series_results.get(key)
            if not result:raise ValueError('Série non calculée')
            context={**(configuration.get('filters') or {}),**{k:v for k,v in series.items() if k in ('start','end','regions','sectors','centers','populations') and v}}
            for item in sorted_distribution(result.get('distribution',[]),widget.get('sort','percent-desc')):
                rows.append({'widget':safe(widget.get('title','')),'series':i,'campaign':safe(result.get('campaign','')),
                    'question':safe(result.get('question','')),'context':safe('; '.join(f'{k}: {v}' for k,v in context.items())),
                    'respondents':result.get('valid_respondents',0),'nonresponses':result.get('nonresponses',0),
                    'modality':safe(item.get('label','')),'count':item.get('count',0),'percent':item.get('percent')})
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.suffix.lower()=='.xlsx':
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='Analyse'
        ws.append(['ORBITE — Studio d analyse',safe(title)])
        ws.append(['Généré UTC',datetime.now(timezone.utc).isoformat()])
        ws.append(['Widget','Série','Campagne','Question','Filtres appliqués','Répondants','Non-réponses','Modalité','Effectif','Pourcentage'])
        for r in rows:ws.append([r['widget'],r['series'],r['campaign'],r['question'],r['context'],r['respondents'],r['nonresponses'],r['modality'],r['count'],r['percent']])
        ws.freeze_panes='A4';ws.auto_filter.ref=ws.dimensions
        for c in ('A','D','E','H'):ws.column_dimensions[c].width=40
        wb.save(target)
    else:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        pdf=canvas.Canvas(str(target),pagesize=A4);height=A4[1];y=height-50
        def line(value):
            nonlocal y
            if y<55:pdf.showPage();y=height-50
            pdf.drawString(35,y,str(value).encode('latin-1','replace').decode('latin-1')[:110]);y-=17
        line('ORBITE - Studio d analyse : '+str(title))
        for r in rows:
            line('Widget : '+r['widget']+' / Serie '+str(r['series'])+' / '+r['campaign'])
            line('Question : '+r['question'])
            line('Filtres : '+r['context'])
            line('n='+str(r['respondents'])+' / non-reponses='+str(r['nonresponses']))
            line(r['modality']+' : '+str(r['count'])+' / '+str(r['percent'])+' %')
        pdf.save()
    return {'path':str(target),'format':target.suffix[1:],'series_count':len(set((r['widget'],r['series']) for r in rows)),'rows':len(rows)}
