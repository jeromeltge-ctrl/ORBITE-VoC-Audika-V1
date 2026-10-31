"""ORBITE Lot 4: export entire Studio dashboard (XLSX/PDF).

Receives precomputed, individually validated series results from a trusted backend.
Never reads client data from arbitrary paths or interprets HTML.
"""
from pathlib import Path
from datetime import datetime, timezone


def _safe(value):
    text = str(value if value is not None else '')
    if text.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + text
    return text


def _rows(title, configuration, series_results):
    if not isinstance(configuration, dict) or not isinstance(configuration.get('widgets'), list):
        raise ValueError('Configuration invalide')
    if len(configuration['widgets']) > 100:
        raise ValueError('Trop de widgets')
    output=[]
    for widget in configuration['widgets']:
        for series in widget.get('series', []):
            result=series_results.get(series.get('id'))
            if not result:
                raise ValueError('Série non calculée ou non autorisée')
            output.append({'widget':_safe(widget.get('title')),'series':_safe(series.get('id')),
                           'start':series.get('start') or configuration.get('filters',{}).get('start',''),
                           'end':series.get('end') or configuration.get('filters',{}).get('end',''),
                           'respondents':result.get('valid_respondents',0),
                           'distribution':result.get('distribution',[])})
    return output


def export_dashboard(path, title, configuration, series_results):
    target=Path(path).expanduser().resolve()
    if target.suffix.lower() not in ('.xlsx','.pdf'):
        raise ValueError('Format non pris en charge')
    rows=_rows(title,configuration,series_results)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.suffix.lower()=='.xlsx':
        from openpyxl import Workbook
        wb=Workbook();ws=wb.active;ws.title='Synthèse'
        ws.append(['ORBITE - Studio d analyse',_safe(title)])
        ws.append(['Actualisation UTC',datetime.now(timezone.utc).isoformat()])
        ws.append(['Widget','Série','Début','Fin','Répondants','Modalité','Effectif','Pourcentage'])
        for entry in rows:
            for d in entry['distribution']:
                ws.append([entry['widget'],entry['series'],entry['start'],entry['end'],entry['respondents'],
                           _safe(d.get('label')),d.get('count'),d.get('percent')])
        ws.freeze_panes='A4';ws.auto_filter.ref=ws.dimensions
        for col in ('A','F'):ws.column_dimensions[col].width=42
        wb.save(target)
    else:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        pdf=canvas.Canvas(str(target),pagesize=A4)
        _,height=A4;y=height-48
        def line(text):
            nonlocal y
            if y<55:pdf.showPage();y=height-48
            pdf.drawString(40,y,_safe(text).encode('latin-1','replace').decode('latin-1')[:100]);y-=17
        line('ORBITE - Studio d analyse')
        line('Tableau de bord : '+str(title))
        line('Actualisation UTC : '+datetime.now(timezone.utc).isoformat())
        for entry in rows:
            line('Widget : '+entry['widget'])
            line('Periode : '+str(entry['start'])+' / '+str(entry['end'])+' - n='+str(entry['respondents']))
            for d in entry['distribution']:
                line(str(d.get('label'))+' : '+str(d.get('count'))+' / '+str(d.get('percent'))+' %')
        pdf.save()
    return {'path':str(target),'format':target.suffix[1:],'series_count':len(rows)}
