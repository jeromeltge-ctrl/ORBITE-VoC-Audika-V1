"""ORBITE QA v2: separate immutable historical catalog from filtered analytical results.
Read-only NPS access; never changes historical tables.
"""
import json
from collections import Counter
from orb_q01 import parse_response
from orb_q02 import reconstruct
from orb_q03 import catalog


def normalize_campaign(raw):
    """Normalize only explicit OPPS aliases; never guess prescription from unknown text."""
    text=str(raw or '').strip()
    key=text.casefold()
    if key in ('avec prescription','avec prescription médicale','avec prescription medicale'):
        return 'NPS OPPS','avec'
    if key in ('sans prescription','sans prescription médicale','sans prescription medicale'):
        return 'NPS OPPS','sans'
    if key in ('nps opps','opps','appareillage'):
        return 'NPS OPPS','inconnu'
    return text or 'Non classée','sans_objet'


def _date(row):
    return str(row['rating_date'] or row['send_date'] or '')[:10]


def _all_rows(con):
    return [dict(r) for r in con.execute('SELECT member_id,appt_type,rating_date,send_date,clinic,region,answers FROM nps')]


def _normalize(row):
    campaign, prescription=normalize_campaign(row.get('appt_type'))
    try: raw=json.loads(row.get('answers') or '[]')
    except (ValueError,TypeError):raw=[]
    cells={'Answer'+str(i):raw[i-1] if isinstance(raw,list) and len(raw)>=i else None for i in range(1,6)}
    r=parse_response(cells,response_id=row['member_id'],campaign=campaign,response_date=_date(row),center=row.get('clinic'))
    r['region']=row.get('region');r['prescription']=prescription
    return r


def _reference(con):
    return [dict(r) for r in con.execute('SELECT code,name,region,sector FROM centres ORDER BY name')]


def _filter_rows(rows, filters, centres):
    f=filters or {}
    def selected(k):
        v=f.get(k)
        if v is None or v=='':return None
        if isinstance(v,list):return set(str(x) for x in v)
        return {str(v)}
    campaigns=selected('campaigns') or selected('campaign')
    regions=selected('regions')
    global_region=selected('region')
    sectors=selected('sectors')
    global_sector=selected('sector')
    codes=selected('centers')
    global_center=selected('center')
    years=selected('years')
    months=selected('months')
    populations=selected('populations')
    lookup={str(c['code']):c for c in centres}
    output=[]
    for r in rows:
        d=r.get('date') or ''; ref=lookup.get(str(r.get('center')),{})
        if campaigns and r['campaign'] not in campaigns:continue
        region=r.get('region') or ref.get('region')
        if global_region and region not in global_region:continue
        if regions and region not in regions:continue
        if global_sector and ref.get('sector') not in global_sector:continue
        if sectors and ref.get('sector') not in sectors:continue
        if global_center and str(r.get('center')) not in global_center:continue
        if codes and str(r.get('center')) not in codes:continue
        if years and d[:4] not in years:continue
        if months and d[5:7] not in months:continue
        if f.get('start') and d<str(f['start'])[:10]:continue
        if f.get('end') and d>str(f['end'])[:10]:continue
        if populations and 'total' not in populations and r['prescription'] not in populations:continue
        output.append(r)
    return output


def _catalog_views(rows):
    """Separate OPPS total/avec/sans observations without splitting the campaign."""
    history=reconstruct(rows)
    items=catalog(rows,history['episodes'])
    for ep in items:
        ep['population_view']='Total OPPS' if ep['campaign']=='NPS OPPS' else ''
    reviews=list(history.get('to_review',[]))
    for code,label in (('avec','Avec prescription'),('sans','Sans prescription')):
        subset=[r for r in rows if r['campaign']=='NPS OPPS' and r['prescription']==code]
        if not subset:continue
        result=reconstruct(subset)
        for ep in catalog(subset,result['episodes']):
            ep['id']='opps-'+code+'-'+ep['id']
            ep['population_view']=label
            for q in ep['questions']:
                q['occurrence_id']='opps-'+code+'-'+q['occurrence_id']
            items.append(ep)
        reviews.extend({**r,'population_view':label} for r in result.get('to_review',[]))
    return items,reviews


def historical_catalog(con):
    """Catalog built from all available rows, never from current UI date filters."""
    rows=[_normalize(r) for r in _all_rows(con)]
    items,reviews=_catalog_views(rows)
    return {'episodes':items,'to_review':reviews,
            'note':'Périodes observées, non dates de diffusion',
            'campaigns':sorted(set(r['campaign'] for r in rows))}


def filter_options(con):
    refs=_reference(con)
    return {'regions':sorted(set(str(x['region']) for x in refs if x.get('region'))),
            'sectors':[{'name':x['sector'],'region':x['region']} for x in refs if x.get('sector')],
            'centers':[{'code':str(x['code']),'name':x['name'],'region':x['region'],'sector':x['sector']} for x in refs]}


def analyze_occurrence(con, episode_id, occurrence_id, filters=None):
    allrows=[_normalize(r) for r in _all_rows(con)]
    items,_=_catalog_views(allrows)
    ep=next((x for x in items if x['id']==episode_id),None)
    if ep is None:raise ValueError('Liste historique inconnue')
    q=next((x for x in ep['questions'] if x['occurrence_id']==occurrence_id),None)
    if q is None:raise ValueError('Question historique inconnue')
    refs=_reference(con)
    chosen=_filter_rows(allrows,filters,refs)
    # Question identity is stable across questionnaire compositions; the same
    # wording can therefore be analysed in N-1 even if its list changed.
    # Comparability of answer modalities must still be checked by the caller.
    chosen=[r for r in chosen if r['campaign']==ep['campaign']]
    if ep.get('population_view')=='Avec prescription':chosen=[r for r in chosen if r['prescription']=='avec']
    if ep.get('population_view')=='Sans prescription':chosen=[r for r in chosen if r['prescription']=='sans']
    valid=set();present=set();choices={};population=Counter()
    for r in chosen:
        rid=str(r['response_id']);population[r['prescription']]+=1
        for cell in r['cells']:
            if cell.get('question_key')!=q['question_key']:continue
            present.add(rid)
            if cell.get('state')=='answered':
                valid.add(rid)
                for answer in set(cell.get('answers',[])):
                    choices.setdefault(answer,set()).add(rid)
    n=len(valid)
    distribution=[{'label':label,'count':len(ids),'percent':round(len(ids)*100/n,2) if n else None} for label,ids in sorted(choices.items())]
    return {'campaign':ep['campaign'],'population_view':ep.get('population_view',''),'question':q['wording'],'episode_id':episode_id,'occurrence_id':occurrence_id,
            'respondents_in_scope':len(set(str(r['response_id']) for r in chosen)),
            'question_present':len(present),'valid_respondents':n,'nonresponses':len(present-valid),
            'distribution':distribution,'populations':dict(population),'filters_applied':filters or {},
            'denominator':'répondants ayant répondu à la question',
            'method_note':'Comparaison possible uniquement après vérification de l’équivalence des modalités'}


def dashboard_export(con, path, title, configuration):
    """Recompute all series on server; never trust client-provided aggregates."""
    from orb_q_dashboard_export import export_dashboard
    if not isinstance(configuration,dict) or not isinstance(configuration.get('widgets'),list):
        raise ValueError('Configuration de tableau de bord invalide')
    if len(configuration['widgets'])>100:raise ValueError('Trop de widgets')
    base=configuration.get('filters') or {}
    computed={}
    for widget in configuration['widgets']:
        for series in widget.get('series',[]):
            key=series.get('id')
            if not key or key in computed:raise ValueError('Identifiant de série absent ou dupliqué')
            params={**base}
            for field in ('start','end','regions','sectors','centers','populations','years','months'):
                value=series.get(field)
                if value:params[field]=value
            computed[key]=analyze_occurrence(con,series['episode_id'],series['occurrence_id'],params)
    return export_dashboard(path,title,configuration,computed)
