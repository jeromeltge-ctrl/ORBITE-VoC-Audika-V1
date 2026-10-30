"""NPS analytics. Only valid integer scores enter the denominator; no inferred invitations."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from periods import comparison

ALIASES={'avec prescription':'OPPS avec PM','sans prescription':'OPPS sans PM'}
OPPS=('OPPS avec PM','OPPS sans PM')


def family(row):
    raw=str(row['appt_type'] or '').strip()
    return ALIASES.get(raw.casefold(),raw or 'Non classée')


def valid_score(value):
    if value is None or isinstance(value,bool):return None
    try:
        score=Decimal(str(value).strip())
        if not score.is_finite() or score != score.to_integral_value() or not 0 <= score <= 10:
            return None
        return int(score)
    except (InvalidOperation,ValueError,TypeError):return None


def metrics(rows):
    rows=list(rows)
    scores=[score for r in rows if (score:=valid_score(r['score'])) is not None]
    p=sum(s>=9 for s in scores);q=sum(7<=s<=8 for s in scores);d=sum(s<=6 for s in scores)
    n=len(scores);total=len(rows)
    # Keep legacy count keys for API compatibility. They count records, NOT validated invitations.
    return {'nps':100*(p-d)/n if n else None,'reponses':n,'sollicitations':total,
            'enregistrements':total,'denominateur_reponse':None,'taux_reponse':None,
            'response_rate_reason':'Nombre de sollicitations fiable non établi ; les enregistrements importés ne constituent pas une cohorte d’envoi validée.',
            'invalid_scores':sum(r['score'] not in (None,'') and valid_score(r['score']) is None for r in rows),
            'promoteurs':p,'passifs':q,'detracteurs':d,
            'part_promoteurs':100*p/n if n else None,'part_passifs':100*q/n if n else None,'part_detracteurs':100*d/n if n else None}


def legacy_metrics(rows):
    rows=list(rows);m=metrics(rows)
    return {'total':m['enregistrements'],'answered':m['reponses'],'response_rate':m['taux_reponse'],
            'response_rate_reason':m['response_rate_reason'],'response_denominator':None,
            'nps':m['nps'],'comments':sum(bool(str(r['comment'] or '').strip()) for r in rows),
            'promoters':m['promoteurs'],'passives':m['passifs'],'detractors':m['detracteurs'],
            'invalid_scores':m['invalid_scores']}


def previous(params):
    return comparison(params)


def difference(a,b):
    if b is None:return None
    return {'nps':a['nps']-b['nps'] if a['nps'] is not None and b['nps'] is not None else None,
            'taux_reponse':a['taux_reponse']-b['taux_reponse'] if a['taux_reponse'] is not None and b['taux_reponse'] is not None else None,
            'reponses':100*(a['reponses']/b['reponses']-1) if b['reponses'] else None}


def dashboard(rows,prior=None,window=None):
    rows=list(rows);prior=list(prior) if prior is not None else None
    by=defaultdict(list);by_prior=defaultdict(list)
    for r in rows:by[family(r)].append(r)
    for r in prior or []:by_prior[family(r)].append(r)
    names=set(by)|set(by_prior)
    if names.intersection(OPPS):names.update(OPPS)
    campaigns=[]
    for name in sorted(names):
        current=metrics(by[name]);old=metrics(by_prior[name]) if prior is not None else None
        campaigns.append({'campagne':name,**current,'precedent':old,'evolution':difference(current,old)})
    if names.intersection(OPPS):
        opps=[r for r in rows if family(r) in OPPS]
        old_opps=[r for r in prior or [] if family(r) in OPPS]
        cur=metrics(opps);old=metrics(old_opps) if prior is not None else None
        campaigns.insert(0,{'campagne':'OPPS total',**cur,'precedent':old,'evolution':difference(cur,old)})
    by_month=defaultdict(list)
    for r in rows:
        if valid_score(r['score']) is not None and r['rating_date'] and len(r['rating_date'])>=7:
            by_month[r['rating_date'][:7]].append(r)
    timeline=[{'mois':month,**metrics(values)} for month,values in sorted(by_month.items())]
    current=metrics(rows);old=metrics(prior) if prior is not None else None
    return {'campaigns':campaigns,'global':current,'previous':old,'evolution':difference(current,old),
            'distribution':current,'timeline':timeline,
            'comparison_mode':window.get('comparison_mode','previous_period') if window else None,
            'current_window':{'start':window.get('current_start'),'end':window.get('current_end')} if window else None,
            'comparison_window':{'start':window['start'],'end':window['end']} if window else None}
