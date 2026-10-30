"""Read-only presentation adapter. The historical engine and SQLite files stay separate."""
import sqlite3
from contextlib import closing
from pathlib import Path
from engine import Analysis, months, yearback
from periods import bounds


def connection(root):
    path=Path(root).resolve()/'google.sqlite'
    return sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)


def period_for(a,params):
    available=sorted({m for _,m in a.h}|{m for _,m in a.u})
    if not available:return [],False
    start,end=bounds(params.get('start'),params.get('end'))
    first=(start or available[-1][:4]+'-01-01')[:7]
    last=(end or available[-1])[:7]
    period=months(first,last)
    # Monthly sources cannot represent arbitrary daily boundaries exactly.
    import calendar
    partial=bool(start and start[-2:]!='01') or bool(end and int(end[-2:])!=calendar.monthrange(int(end[:4]),int(end[5:7]))[1])
    return period,partial


def stats(a,period,codes):
    codes=list(codes);raw=a.stats(period,codes);result=dict(raw)
    total=len(codes)*len(period)
    known=total-raw['missing_n'];known1=total-raw['missing_n1']
    result.update(known_n=raw['n'],known_n1=raw['n1'],observed_n=known,observed_n1=known1,
                  expected_observations=total,coverage_n=known/total if total else None,
                  coverage_n1=known1/total if total else None)
    if not known:result['n']=None;result['moyenne']=None
    if not known1:result['n1']=None
    prior=a.stats([yearback(m) for m in period],codes)
    complete=bool(total) and known==total and known1==total and not raw['partial_months'] and not prior['partial_months']
    if not complete:result['evolution']=None
    result['comparison_available']=complete
    result['comparison_reason']='' if complete else 'Couverture incomplète, mois provisoires ou périmètre vide : comparaison indisponible.'
    result['partial_months_n1']=prior['partial_months']
    result['note_n1']=prior['note']
    result['note_delta']=raw['note']-prior['note'] if raw['note'] is not None and prior['note'] is not None else None
    result['note_centres']=sum((c,period[-1]) in a.snap and a.snap[c,period[-1]][0]>0 and a.snap[c,period[-1]][1] is not None for c in codes)
    if not codes:
        result['zero_total']=None;result['zero_periode']=None
    elif not any((c,period[-1]) in a.snap for c in codes):
        result['zero_total']=None
    if codes and not any(all(a.delta(c,m) is not None for m in period) for c in codes):
        result['zero_periode']=None
    return result


def summary(root,params):
    if not (Path(root)/'google.sqlite').is_file():
        return {'available':False,'message':'Données Google indisponibles','regions':[],'sectors':[],'period':[]}
    with closing(connection(root)) as c:
        c.execute('BEGIN')
        a=Analysis(c)
        period,partial=period_for(a,params)
        if not a.centers or not period:
            return {'available':False,'message':'Importer le référentiel et les données Google','regions':[],'sectors':[],'period':[]}
        codes=a.codes(params.get('region') or 'Toutes',params.get('sector') or 'Tous')
        result=stats(a,period,codes)
        result.update(available=True,period=period,comparison_period=[yearback(m) for m in period],
                      requested_start=params.get('start') or '',requested_end=params.get('end') or '',
                      monthly_resolution=True,partial_boundaries=partial,source='engine.py historique / adaptateur de couverture')
        result['period_warning']='Les données Google sont mensuelles : les mois contenant les bornes demandées sont utilisés en entier.' if partial else ''
        result['regions']=[{'name':r,**stats(a,period,[code for code in codes if a.centers[code][2]==r])} for r in sorted({a.centers[code][2] for code in codes})]
        result['sectors']=[{'name':s,'region':r,**stats(a,period,[code for code in codes if a.centers[code][2:4]==(r,s)])} for r,s in sorted({a.centers[code][2:4] for code in codes})]
        return result


def overview(root,params):
    result=summary(root,params)
    if not result['available']:return {'google_available':False}
    return {'google_available':True,'google_note':result['note'],'google_reviews':result['n'],
            'google_reviews_n1':result['n1'],'google_reviews_evolution':result['evolution'],
            'google_reviews_per_center_month':result['moyenne'],
            'google_reviews_per_center_month_n1':result['n1']/result['centres']/len(result['period']) if result['n1'] is not None and result['centres'] else None,
            'google_note_delta':result['note_delta'],'google_centres':result['centres'],
            'google_period_start':result['period'][0],'google_period_end':result['period'][-1],
            'google_missing_n':result['missing_n'],'google_missing_n1':result['missing_n1'],
            'google_period_warning':result['period_warning'],'google_comparison_reason':result['comparison_reason']}


def filter_options(root,nps_centres):
    """Union of geographic choices only; no implicit centre remapping or database writes."""
    pairs={(x['region'],x['sector']) for x in nps_centres}
    if (Path(root)/'google.sqlite').is_file():
        with closing(connection(root)) as c:
            pairs.update(c.execute('SELECT DISTINCT region,secteur FROM centres'))
    return {'regions':sorted({r for r,s in pairs if r}),
            'sectors':[{'name':s,'region':r} for r,s in sorted(pairs,key=lambda pair:(pair[0] or '',pair[1] or '')) if s]}
