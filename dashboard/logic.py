"""Pure formatting and evidence safeguards for the public prototype."""
from __future__ import annotations

from decimal import Decimal


BOUROUGHS = frozenset({
    'Bolton', 'Bury', 'Manchester', 'Oldham', 'Rochdale', 'Salford',
    'Stockport', 'Tameside', 'Trafford', 'Wigan'
})


def pounds(value):
    if value is None:
        return 'Not available'
    return f'£{Decimal(str(value)):,.2f}'


def period_label(value):
    value = str(value)
    if len(value) == 6 and value.isdigit():
        return f'{value[:4]}/{value[4:]}'
    return value


def published_count(raw, parsed):
    """Preserve statistical disclosure values instead of converting to zero."""
    if parsed is not None:
        return f'{int(parsed):,}'
    return str(raw) if raw is not None else 'Not available'


def reconcile_funding(rows):
    """Reconcile across one row per provider, not joined to activity detail."""
    total = sum((Decimal(str(r['total_allocation_gbp'])) for r in rows), Decimal('0'))
    return len(rows), total


def check_borough_evidence(rows):
    valid = {r['borough_name'] for r in rows}
    if not valid.issubset(BOUROUGHS):
        raise ValueError('Unexpected borough included in results')
    periods = {r['academic_period'] for r in rows}
    return len(valid), sorted(periods)


def is_comparable_period(period_a, period_b):
    """Do not claim year-on-year annual movement against provisional 2025/26."""
    if '202526' in {period_a, period_b}:
        return False
    return period_a == period_b
