"""Network read model; NPS-only until validated Google fusion is enabled."""
import nps_analytics as nps

def build(c,rows,prior=None,region='',sector=''):
    refs=c.execute('SELECT code,name,region,sector FROM centres WHERE (?="" OR region=?) AND (?="" OR sector=?) ORDER BY region,sector,name',(region,region,sector,sector)).fetchall()
    current={};old={}
    for r in rows:current.setdefault(r['clinic'],[]).append(r)
    for r in prior or []:old.setdefault(r['clinic'],[]).append(r)
    out=[]
    for ref in refs:
        a=nps.metrics(current.get(ref['code'],[]));b=nps.metrics(old[ref['code']]) if ref['code'] in old else None
        out.append({**dict(ref),'nps':a['nps'],'reponses':a['reponses'],'sollicitations':a['sollicitations'],'taux_reponse':a['taux_reponse'],'nps_delta':a['nps']-b['nps'] if b and a['nps'] is not None and b['nps'] is not None else None,'google_note':None,'google_avis_n':None})
    return out
