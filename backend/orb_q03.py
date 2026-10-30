"""ORB-Q03 read-only quick analysis over normalized ORB-Q01 response dictionaries."""
from collections import Counter, defaultdict

def catalog(responses, episodes):
    """Produce chronological campaign/year/episode catalog, preserving occurrence IDs."""
    result=[]
    for ep in episodes:
        rows=[r for r in responses if r.get('campaign')==ep['campaign'] and ep['first_observation']<=str(r.get('date') or '')[:10]<=ep['last_observation'] and r.get('composition_signature')==ep['signature']]
        questions={}
        for r in rows:
            for cell in r.get('cells',[]):
                if cell.get('state') not in ('answered','unanswered'):continue
                key=cell['question_key']
                entry=questions.setdefault(key,{'occurrence_id':ep['id']+':'+key,'question_key':key,'wording':cell['question'],'responses':0,'respondents':set()})
                if cell['state']=='answered':
                    entry['responses']+=1;entry['respondents'].add(r['response_id'])
        items=[{**v,'respondents':len(v['respondents'])} for v in questions.values()]
        result.append({**ep,'year':ep['first_observation'][:4],'questions':sorted(items,key=lambda q:q['wording']),'response_count':len(rows),'respondents':len(set(r['response_id'] for r in rows))})
    return sorted(result,key=lambda x:(x['first_observation'],x['id']),reverse=True)

def analyze_question(responses, occurrence, *, campaign=None, start=None, end=None, centers=None):
    """Count one respondent once in the denominator, multiple modalities independently."""
    key=occurrence['question_key']; sig=occurrence['signature']
    seen=set(); answered=set(); choices=defaultdict(set); present=set()
    for r in responses:
        day=str(r.get('date') or '')[:10]
        if campaign and r.get('campaign')!=campaign:continue
        if start and day<start:continue
        if end and day>end:continue
        if centers is not None and r.get('center') not in centers:continue
        if r.get('composition_signature')!=sig:continue
        rid=r['response_id'];seen.add(rid)
        for cell in r.get('cells',[]):
            if cell.get('question_key')!=key:continue
            present.add(rid)
            if cell['state']=='answered':
                answered.add(rid)
                for v in set(cell.get('answers',[])):choices[v].add(rid)
    n=len(answered)
    return {'respondents_in_scope':len(seen),'question_present':len(present),'valid_respondents':n,'nonresponses':len(present-answered),
            'distribution':[{'label':label,'count':len(ids),'percent':round(100*len(ids)/n,2) if n else None} for label,ids in sorted(choices.items())],
            'denominator':'respondents with at least one answer to this question','multi_select_percentages_may_exceed_100':True}
