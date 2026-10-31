"""ORB-Q06 backend adapter. Additive: reads NPS, saves studio, exports reports."""
import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from orb_q01 import parse_response
from orb_q02 import reconstruct
from orb_q03 import catalog, analyze_question
import orb_q05 as studio


def _normalized(c, params):
    # Read source NPS without changing its schema. Limits are applied to raw rows first.
    sql='SELECT member_id, appt_type, rating_date, send_date, clinic, region, answers FROM nps WHERE 1=1'
    args=[]
    for col,key in [('appt_type','campaign'),('region','region')]:
        if params.get(key):sql+=f' AND {col}=?';args.append(params[key])
    if params.get('start'):
        sql+=' AND substr(COALESCE(NULLIF(rating_date,\'\'),send_date),1,10)>=?';args.append(params['start'][:10])
    if params.get('end'):
        sql+=' AND substr(COALESCE(NULLIF(rating_date,\'\'),send_date),1,10)<=?';args.append(params['end'][:10])
    if params.get('center'):
        sql+=' AND clinic=?';args.append(params['center'])
    if params.get('sector'):
        sql+=' AND clinic IN (SELECT code FROM centres WHERE sector=?)';args.append(params['sector'])
    normalized=[]
    for row in c.execute(sql,args):
        r=dict(row)
        try: raw=json.loads(r['answers'] or '[]')
        except (ValueError,TypeError):raw=[]
        cells={'Answer'+str(i):raw[i-1] if isinstance(raw,list) and len(raw)>=i else None for i in range(1,6)}
        normalized.append(parse_response(cells,response_id=r['member_id'],campaign=r['appt_type'],
            response_date=(r['rating_date'] or r['send_date'] or '')[:10],center=r['clinic']))
    return normalized

def _observations(c,p):
    rows=_normalized(c,p)
    episodes=reconstruct(rows,min_support=int(p.get('min_support') or 3),dominance=float(p.get('dominance') or .7))
    return rows,episodes,catalog(rows,episodes['episodes'])

def _dashboard_export(c,p):
    """Resolve all widget series server-side; never trust client-computed results."""
    from orb_q_dashboard_export import export_dashboard
    config=p.get('configuration')
    if not isinstance(config,dict) or not isinstance(config.get('widgets'),list):
        raise ValueError('Configuration de tableau de bord invalide')
    if len(config['widgets'])>100:raise ValueError('Trop de widgets')
    base=config.get('filters') or {}
    computed={}
    for widget in config['widgets']:
        for series in widget.get('series',[]):
            key=series.get('id')
            if not key or key in computed:raise ValueError('Identifiant de serie manquant ou duplique')
            params={**base}
            for field in ('start','end','region','sector','center'):
                if series.get(field):params[field]=series[field]
            rows,_,items=_observations(c,params)
            ep=next((x for x in items if x['id']==series.get('episode_id')),None)
            if ep is None:raise ValueError('Liste historique non disponible dans le perimetre')
            question=next((x for x in ep['questions'] if x['occurrence_id']==series.get('occurrence_id')),None)
            if question is None:raise ValueError('Question historique non disponible')
            computed[key]=analyze_question(rows,{**question,'signature':ep['signature']},
                campaign=ep['campaign'],start=ep['first_observation'],end=ep['last_observation'])
    return export_dashboard(p['path'],p.get('title') or 'ORBITE Studio',config,computed)

def handle(c,method,p):
    if method=='qaDashboardExport':return _dashboard_export(c,p)
    if method=='qaHistoricalCatalog':
        _,episodes,items=_observations(c,p)
        return {'episodes':items,'to_review':episodes['to_review'],'notice':'Observations, non dates de diffusion certifiees'}
    if method=='qaQuickResult':
        rows,episodes,items=_observations(c,p)
        ep=next((x for x in items if x['id']==p.get('episode_id')),None)
        if ep is None:raise ValueError('Occurrence historique introuvable sur ce perimetre')
        q=next((x for x in ep['questions'] if x['occurrence_id']==p.get('occurrence_id')),None)
        if q is None:raise ValueError('Question introuvable dans la liste')
        # Restrict to the historical episode and current filters.
        return analyze_question(rows,{**q,'signature':ep['signature']},campaign=ep['campaign'],start=ep['first_observation'],end=ep['last_observation'])
    if method in ('qaDashboardSave','qaDashboardList','qaDashboardLoad','qaDashboardDuplicate','qaDashboardDelete'):
        studio.initialize(c)
        # Local Windows user is not an authorization boundary for multi-user sharing.
        owner=os.environ.get('USERNAME') or os.environ.get('USER') or 'local'
        if method=='qaDashboardSave':return {'id':studio.save_dashboard(c,owner,p['title'],p['configuration'],p.get('id'))}
        if method=='qaDashboardList':return studio.list_dashboards(c,owner)
        if method=='qaDashboardLoad':return studio.load_dashboard(c,owner,p['id'])
        if method=='qaDashboardDuplicate':return {'id':studio.duplicate_dashboard(c,owner,p['id'])}
        if method=='qaDashboardDelete':return {'deleted':studio.delete_dashboard(c,owner,p['id'])}
    if method=='qaStatistics':
        if p.get('kind')=='chi_square':return studio.contingency_statistics(p['matrix'])
        if p.get('kind')=='spearman':return studio.spearman_descriptive(p['x'],p['y'])
        raise ValueError('Analyse statistique non disponible')
    if method=='qaExport':
        from openpyxl import Workbook
        path=Path(p['path']).expanduser().resolve();fmt=path.suffix.lower()
        if fmt not in ('.xlsx','.pdf','.csv'):raise ValueError('Format attendu : xlsx, pdf ou csv')
        rows,episodes,items=_observations(c,p)
        ep=next((x for x in items if x['id']==p.get('episode_id')),None)
        if ep is None:raise ValueError('Liste historique introuvable')
        q=next((x for x in ep['questions'] if x['occurrence_id']==p.get('occurrence_id')),None)
        if q is None:raise ValueError('Question introuvable')
        result=analyze_question(rows,{**q,'signature':ep['signature']},campaign=ep['campaign'],start=ep['first_observation'],end=ep['last_observation'])
        metadata={'campagne':ep['campaign'],'question':q['wording'],'periode':ep['first_observation']+' / '+ep['last_observation'],
                  'repondants_valides':result['valid_respondents'],'denominateur':'repondants ayant repondu','statut':'observation'}
        data=[{**x,'denominator':result['valid_respondents']} for x in result['distribution']]
        path.parent.mkdir(parents=True,exist_ok=True)
        if fmt=='.csv':path.write_text(studio.export_distribution_csv(data,metadata),encoding='utf-8')
        elif fmt=='.xlsx':
            wb=Workbook();ws=wb.active;ws.title='Question additionnelle'
            for k,v in metadata.items():ws.append([k,v])
            ws.append([]);ws.append(['Modalite','Effectif','Pourcentage','Denominateur'])
            for x in data:
                label=str(x['label'])
                if label.lstrip().startswith(('=', '+', '-', '@')):label="'"+label
                ws.append([label,x['count'],x['percent'],x['denominator']])
            ws.freeze_panes='A9';ws.column_dimensions['A'].width=65;ws.column_dimensions['B'].width=25
            wb.save(path)
        else:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            pdf=canvas.Canvas(str(path),pagesize=A4);width,height=A4;y=height-55
            def line(text):
                nonlocal y
                if y<70:pdf.showPage();y=height-55
                pdf.drawString(40,y,str(text).encode('latin-1','replace').decode('latin-1')[:105]);y-=18
            line('ORBITE - Questions additionnelles')
            for k,v in metadata.items():line(k+' : '+str(v))
            line('Modalite / Effectif / Pourcentage')
            for x in data:line(str(x['label'])+' : '+str(x['count'])+' / '+str(x['percent'])+' %')
            pdf.save()
        return {'path':str(path),'format':fmt[1:],'rows':len(data)}
    raise ValueError('Methode QA inconnue')
