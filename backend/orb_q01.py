"""ORB-Q01: non-destructive parser of Answer1..Answer5 cells."""
import json, hashlib, unicodedata

def stable_hash(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',',':')).encode()).hexdigest()[:24]

def normalize_label(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).split())

def parse_cell(raw, position):
    if raw is None or raw == '': return {'state':'absent','position':position}
    try:
        data=json.loads(raw) if isinstance(raw,str) else raw
    except (TypeError,ValueError):
        return {'state':'invalid','position':position,'reason':'invalid_json'}
    if not isinstance(data,dict) or not isinstance(data.get('question'),str) or not data['question'].strip():
        return {'state':'invalid','position':position,'reason':'missing_question'}
    question=normalize_label(data['question'])
    value=data.get('answer')
    if value is None: values=[]
    elif isinstance(value,list): values=value
    else: values=[value]
    values=[str(v).strip() for v in values if v is not None and str(v).strip()]
    return {'state':'answered' if values else 'unanswered','position':position,
            'question':question,'question_key':stable_hash(question),'answers':values}

def parse_response(row, *, response_id, campaign, response_date=None, center=None):
    cells=[parse_cell(row.get('Answer'+str(i)),i) for i in range(1,6)]
    valid=[x for x in cells if x['state'] in ('answered','unanswered')]
    signature=stable_hash(campaign, sorted(set(x['question_key'] for x in valid))) if valid else None
    return {'response_id':str(response_id),'campaign':str(campaign),'date':response_date,
            'center':center,'cells':cells,'composition_signature':signature,
            'question_keys':sorted(set(x['question_key'] for x in valid)),
            'quality': 'invalid' if any(x['state']=='invalid' for x in cells) else ('empty' if not valid else 'ok')}
