"""ORBITE Lot 1: historical questionnaire episodes inferred conservatively from responses.

Does not claim publishing dates. No writes to the NPS tables.
"""
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json


def _stable(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:24]


def _day(value):
    try:
        return date.fromisoformat(str(value or '')[:10]).isoformat()
    except (TypeError, ValueError):
        return None


def reconstruct(responses, *, min_support=3, dominance=0.7):
    """Identify high-confidence runs; retain ambiguity instead of inventing a version.

    Incomplete subsets of a dominant questionnaire are counted as compatible evidence,
    never as a new confirmed questionnaire without independent support.
    """
    if not isinstance(min_support, int) or min_support < 1 or not 0.5 < dominance <= 1:
        raise ValueError('Invalid historical detection thresholds')
    by_campaign = defaultdict(list)
    for r in responses:
        day = _day(r.get('date'))
        if not day or r.get('quality') != 'ok' or not r.get('composition_signature'):
            continue
        keys = frozenset(r.get('question_keys') or [])
        if keys:
            by_campaign[str(r.get('campaign') or 'Non classée')].append((day, r, keys))
    episodes, reviews = [], []
    for campaign, records in sorted(by_campaign.items()):
        by_day = defaultdict(list)
        for day, row, keys in records:
            by_day[day].append((row, keys))
        daily = []
        for day in sorted(by_day):
            entries = by_day[day]
            exact = Counter(r['composition_signature'] for r, _ in entries)
            keysets = {r['composition_signature']: keys for r, keys in entries}
            # Largest complete composition wins a tie; partial rows are compatible.
            candidates = sorted(exact, key=lambda sig: (-len(keysets[sig]), -exact[sig], sig))
            ranked = []
            for sig in candidates:
                keys = keysets[sig]
                support = sum(1 for _, observed in entries if observed.issubset(keys))
                # Must have direct evidence for the complete composition.
                direct = exact[sig]
                ranked.append((support, direct, len(keys), sig))
            support, direct, _, sig = max(ranked, key=lambda x: (x[0], x[1], x[2], x[3]))
            confidence = support / len(entries)
            # A subset can be a genuine questionnaire. Never certify it when a larger
            # composition was observed on the same day and could explain the subset.
            confirmed = direct >= min_support and confidence >= dominance
            if confirmed:
                competing = [other for other in candidates if other != sig and
                             not keysets[other].issubset(keysets[sig]) and
                             exact[other] >= min_support and exact[other] / len(entries) >= (1-dominance)]
                if competing:
                    confirmed = False
            daily.append({'date': day, 'signature': sig, 'status': 'observed' if confirmed else 'to_review',
                          'support': support, 'direct': direct, 'total': len(entries),
                          'confidence': round(confidence, 4), 'distribution': dict(exact)})
            if not confirmed:
                reviews.append({'id': _stable(campaign, day, sorted(exact.items())),
                                'campaign': campaign, 'date': day, 'reason': 'composition_ambiguous',
                                'confidence': round(confidence, 4), 'distribution': dict(exact)})
        current = None
        previous_keys = None
        for d in daily:
            # A previously observed complete questionnaire can explain a later
            # subset-only day. Without evidence of a genuine replacement, review it.
            current_keys = next((keys for row, keys in by_day[d['date']]
                                 if row['composition_signature'] == d['signature']), frozenset())
            if d['status'] == 'observed' and previous_keys and current_keys < previous_keys:
                d['status'] = 'to_review'
                reviews.append({'id': _stable(campaign, d['date'], 'subset_transition'),
                                'campaign': campaign, 'date': d['date'],
                                'reason': 'possible_incomplete_questionnaire',
                                'confidence': d['confidence'], 'distribution': d['distribution']})
            if d['status'] == 'to_review':
                if current:
                    episodes.append(current)
                    current = None
                continue
            previous_keys = current_keys
            if current and current['signature'] == d['signature']:
                current['last_observation'] = d['date']
                current['daily_support'] += d['direct']
                current['observed_days'] += 1
                current['respondents_observed'] += d['total']
            else:
                if current:
                    episodes.append(current)
                current = {'campaign': campaign, 'signature': d['signature'],
                           'first_observation': d['date'], 'last_observation': d['date'],
                           'daily_support': d['direct'], 'observed_days': 1,
                           'respondents_observed': d['total'], 'status': 'observed',
                           'confidence': d['confidence']}
        if current:
            episodes.append(current)
    for ep in episodes:
        ep['id'] = _stable(ep['campaign'], ep['signature'], ep['first_observation'])
        ep['note'] = 'Dates de première/dernière observation ; pas de dates de diffusion'
    return {'episodes': episodes, 'to_review': reviews,
            'policy': {'min_support': min_support, 'dominance': dominance,
                       'interpretation': 'Conservative observation, not publication dates'}}
