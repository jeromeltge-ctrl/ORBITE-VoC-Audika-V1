"""ORB-Q02: conservative, read-only detection of observed questionnaire episodes.

No inferred publishing dates; uncertain cases are flagged for review.
"""
from collections import Counter,defaultdict
from datetime import date
from orb_q01 import stable_hash

def reconstruct(responses, *, min_support=3, dominance=0.7):
    if min_support<1 or not 0.5<dominance<=1: raise ValueError('Invalid thresholds')
    by_campaign=defaultdict(list)
    for r in responses:
        if r.get('date') and r.get('composition_signature') and r.get('quality')=='ok':
            try: day=date.fromisoformat(str(r['date'])[:10]).isoformat()
            except ValueError: continue
            by_campaign[r['campaign']].append((day,r))
    episodes=[]; reviews=[]
    for campaign, records in by_campaign.items():
        days=defaultdict(list)
        for day,r in records: days[day].append(r)
        observed=[]
        for day in sorted(days):
            counts=Counter(r['composition_signature'] for r in days[day]); sig,count=counts.most_common(1)[0]
            confidence=count/len(days[day]); status='candidate' if count<min_support or confidence<dominance else 'confirmed_daily'
            observed.append((day,sig,status,count,len(days[day])))
            if status=='candidate': reviews.append({'campaign':campaign,'date':day,'reason':'insufficient_evidence','distribution':dict(counts)})
        current=None
        for day,sig,status,count,total in observed:
            if status=='candidate':
                if current: episodes.append(current);current=None
                continue
            if current and current['signature']==sig:
                current['last_observation']=day;current['daily_support']+=count;current['observed_days']+=1
            else:
                if current:episodes.append(current)
                current={'campaign':campaign,'signature':sig,'first_observation':day,
                         'last_observation':day,'daily_support':count,'observed_days':1,'status':'observed'}
        if current:episodes.append(current)
    for ep in episodes:
        ep['id']=stable_hash(ep['campaign'],ep['signature'],ep['first_observation'])
        ep['note']='Dates de premiere et derniere observation, pas dates de diffusion'
    return {'episodes':episodes,'to_review':reviews,'policy':{'min_support_per_day':min_support,'dominance':dominance}}
