"""Calendar normalization shared by adapters; no storage or business mapping."""
import calendar
from datetime import date, datetime, timedelta


def day(value, end=False):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or '').strip()
    if len(text) == 7 and text[4] == '-':
        year, month = map(int, text.split('-'))
        return date(year, month, calendar.monthrange(year, month)[1] if end else 1)
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace('Z', '+00:00')).date()
        except ValueError:
            return datetime.strptime(text, '%d/%m/%Y').date()


def bounds(start='', end=''):
    a = day(start) if start else None
    b = day(end, end=True) if end else None
    if a and b and a > b:
        raise ValueError('Période inversée')
    return a.isoformat() if a else '', b.isoformat() if b else ''


def comparison(params):
    mode = params.get('comparison_mode') or 'previous_period'
    if mode not in ('previous_period', 'year_over_year'):
        raise ValueError('Mode de comparaison inconnu')
    a, b = bounds(params.get('start'), params.get('end'))
    if not a or not b:
        return None
    first, last = date.fromisoformat(a), date.fromisoformat(b)
    if mode == 'previous_period':
        length = (last - first).days + 1
        before, after = first - timedelta(days=length), first - timedelta(days=1)
    else:
        def yearback(d):
            return d.replace(year=d.year-1, day=min(d.day, calendar.monthrange(d.year-1,d.month)[1]))
        before, after = yearback(first), yearback(last)
    return {**params, 'start':before.isoformat(), 'end':after.isoformat(), 'comparison_mode':mode,
            'current_start':a, 'current_end':b}
