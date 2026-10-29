"""NPS analytics — isolated from Google; dates and campaign types from NPS exports."""
from collections import defaultdict
from datetime import date,timedelta

# Only explicit, previously observed business aliases. Unknown values are kept verbatim.
ALIASES={'avec prescription':'OPPS avec PM','sans prescription':'OPPS sans PM'}
def family(row):
    raw=str(row['appt_type'] or '').strip()
    return ALIASES.get(raw.casefold(),raw or 'Non classée')

def metrics(rows):
    scores=[int(r['score']) for r in rows if r['score'] is not None and 0<=int(r['score'])<=10]
    p=sum(s>=9 for s in scores);q=sum(7<=s<=8 for s in scores);d=sum(s<=6 for s in scores)
    n=len(scores);total=len(rows)
    return {'nps':100*(p-d)/n if n else None,'reponses':n,'sollicitations':total,'taux_reponse':100*n/total if total else None,'promoteurs':p,'passifs':q,'detracteurs':d,'part_promoteurs':100*p/n if n else None,'part_passifs':100*q/n if n else None,'part_detracteurs':100*d/n if n else None}

def previous(params):
    if not params.get('start') or not params.get('end'):return None
    a=date.fromisoformat(params['start'][:10]);b=date.fromisoformat(params['end'][:10]);length=(b-a).days+1
    if length<1:raise ValueError('Période inversée')
    return {**params,'start':(a-timedelta(days=length)).isoformat(),'end':(a-timedelta(days=1)).isoformat()}

def difference(a,b):
    if b is None:return None
    return {'nps':a['nps']-b['nps'] if a['nps'] is not None and b['nps'] is not None else None,
            'taux_reponse':a['taux_reponse']-b['taux_reponse'] if a['taux_reponse'] is not None and b['taux_reponse'] is not None else None,
            'reponses':100*(a['reponses']/b['reponses']-1) if b['reponses'] else None}

def dashboard(rows,prior=None,window=None):
    by=defaultdict(list);by_prior=defaultdict(list)
    for r in rows:by[family(r)].append(r)
    for r in prior or []:by_prior[family(r)].append(r)
    campaigns=[]
    for name in sorted(by):
        current=metrics(by[name]);old=metrics(by_prior[name]) if prior is not None and by_prior[name] else None
        campaigns.append({'campagne':name,**current,'precedent':old,'evolution':difference(current,old)})
    opps=[r for r in rows if family(r) in ('OPPS avec PM','OPPS sans PM')]
    if opps:
        old_opps=[r for r in prior or [] if family(r) in ('OPPS avec PM','OPPS sans PM')]
        cur=metrics(opps);old=metrics(old_opps) if prior is not None and old_opps else None
        campaigns.insert(0,{'campagne':'OPPS total',**cur,'precedent':old,'evolution':difference(cur,old)})
    by_month=defaultdict(list)
    for r in rows:
        if r['score'] is not None and r['rating_date'] and len(r['rating_date'])>=7:
            by_month[r['rating_date'][:7]].append(r)
    timeline=[{'mois':month,**metrics(values)} for month,values in sorted(by_month.items())]
    global_current=metrics(rows);global_prior=metrics(prior) if prior else None
    return {'campaigns':campaigns,'global':global_current,'previous':global_prior,'evolution':difference(global_current,global_prior),'distribution':global_current,'timeline':timeline,'comparison_window':{'start':window['start'],'end':window['end']} if window else None}
