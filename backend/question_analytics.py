"""Analyze Answer1–Answer5 without fabricating question labels or survey versions."""
from collections import Counter
import json,unicodedata

def norm(text):return ''.join(c for c in unicodedata.normalize('NFKD',str(text or '').casefold()) if not unicodedata.combining(c))
def decode(raw):
    if raw is None or raw=='':return None
    value=raw
    if isinstance(raw,str):
        try:value=json.loads(raw)
        except (ValueError,TypeError):pass
    if isinstance(value,dict):
        label=value.get('question')
        answers=value.get('answer')
        if answers is None:return None
        return (label.strip() if isinstance(label,str) and label.strip() else None,answers if isinstance(answers,list) else [answers])
    return (None,value if isinstance(value,list) else [value])

def analyze(rows,search=''):
    groups={}
    for row in rows:
        try:answers=json.loads(row['answers'] or '[]')
        except (TypeError,ValueError):continue
        if not isinstance(answers,list):continue
        period=(row['rating_date'] or row['send_date'] or '')[:7]
        for position,raw in enumerate(answers[:5],1):
            item=decode(raw)
            if item is None:continue
            label,values=item;campaign=row['appt_type'] or 'Non classée'
            if search and norm(search) not in norm((label or '')+' '+campaign):continue
            key=(campaign,period,position,label)
            if key not in groups:groups[key]={'campaign':campaign,'period':period,'position':position,'wording':label,'identified':bool(label),'answers':0,'counts':Counter(),'sources':set()}
            group=groups[key];group['sources'].add(row['raw_source'] or '')
            for v in values:
                if v is None or v=='':continue
                group['answers']+=1;group['counts'][str(v)]+=1
    return [{'campaign':v['campaign'],'period':v['period'],'position':v['position'],'wording':v['wording'],'identified':v['identified'],'answers':v['answers'],'sources':sorted(v['sources']),
             'distribution':[{'label':name,'count':count,'percent':100*count/v['answers'] if v['answers'] else None} for name,count in v['counts'].most_common()]} for v in sorted(groups.values(),key=lambda x:(x['period'],x['campaign'],x['position'],x['wording'] or ''))]
