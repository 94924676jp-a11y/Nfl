"""Measure what a feed returns over time, so a cap cannot hide inside PASS.

THE DETECTOR THAT WOULD HAVE CAUGHT IT ON DAY ONE

`espn_injuries_json` returned exactly 25 entries for every club in every one
of 648 captures -- 20,736 club-entries, one distinct value, zero variation --
while declaring `"status": "success"` with no pagination metadata anywhere in
the document. Nothing in the capture layer looked at the shape of the numbers,
so the cap sat inside a green light for six weeks.

A live census over 32 clubs and six weeks does not produce a one-valued
distribution. A page size does. That is the whole detector, and it needs no
knowledge of the endpoint: **a count that never varies across many captures of
a changing world is a property of the container, not of the world.**

WHY THE THRESHOLDS ARE SHAPED THE WAY THEY ARE

`MIN_CAPTURES_FOR_INVARIANCE` exists because one capture returning the same
number as the next is not evidence of anything. Two captures an hour apart
SHOULD agree; sixty over six weeks should not. The constant is a floor on
when the question becomes askable, not a tuned parameter, and it is stated
here rather than hidden in a comparison.

Nothing here decides that a feed is broken. It reports shape, and shape is
evidence a human or a validity report acts on. The census that diagnosed
itself would be the same defect one level up.
"""
from __future__ import annotations

import collections
import statistics

SPEC_VERSION = 'source-census/1.0.0'

#: Below this many captures, invariance is not yet a question worth asking.
#: Two captures minutes apart agreeing is the expected behaviour of any feed.
MIN_CAPTURES_FOR_INVARIANCE = 10

#: Findings this module can raise. Closed set: a census that could invent a
#: finding type could also invent a reassurance.
SUSPECTED_TRUNCATION = 'SUSPECTED_TRUNCATION'
ENTITY_COUNT_INVARIANT = 'ENTITY_COUNT_INVARIANT'
SCHEMA_DRIFT = 'SCHEMA_DRIFT'
ENTITY_COVERAGE_DROP = 'ENTITY_COVERAGE_DROP'
EMPTY_CAPTURE = 'EMPTY_CAPTURE'


class CensusError(RuntimeError):
    """The census cannot be computed. Distinct from a feed looking wrong."""


def _round_shape(keys) -> str:
    return '|'.join(sorted(str(k) for k in keys))


def census(observations) -> dict:
    """Summarise a family's captures.

    `observations` is a sequence of dicts, one per capture:
        {'capture_id', 'per_entity': {entity: count}, 'schema': [field, ...]}

    Returns shape, never a verdict about the endpoint.
    """
    obs = list(observations or ())
    if not obs:
        raise CensusError(
            'no observations supplied; an empty census is not a clean bill of '
            'health and must not be reported as one')

    per_capture_totals, entity_counts, schemas, entity_sets = [], [], [], []
    for o in obs:
        pe = o.get('per_entity') or {}
        per_capture_totals.append(sum(pe.values()))
        entity_counts.extend(pe.values())
        entity_sets.append(frozenset(pe))
        if o.get('schema') is not None:
            schemas.append(_round_shape(o['schema']))

    distinct_counts = collections.Counter(entity_counts)
    n_captures = len(obs)
    all_entities = set().union(*entity_sets) if entity_sets else set()

    out = {
        'spec_version': SPEC_VERSION,
        'n_captures': n_captures,
        'n_entity_observations': len(entity_counts),
        'distinct_per_entity_counts': dict(sorted(distinct_counts.items())),
        'entities_seen': len(all_entities),
        'entities_per_capture': sorted({len(s) for s in entity_sets}),
        'total_per_capture': {
            'min': min(per_capture_totals), 'max': max(per_capture_totals),
            'mean': round(statistics.fmean(per_capture_totals), 2)},
        'distinct_schemas': sorted(set(schemas)),
        'findings': [],
    }

    def finding(code, detail, **ev):
        out['findings'].append({'code': code, 'detail': detail, **ev})

    if not entity_counts or all(c == 0 for c in entity_counts):
        finding(EMPTY_CAPTURE,
                'every entity returned zero rows; an empty result is an error, '
                'not a measurement')

    if (n_captures >= MIN_CAPTURES_FOR_INVARIANCE
            and len(distinct_counts) == 1 and entity_counts):
        value = next(iter(distinct_counts))
        if value > 0:
            finding(
                ENTITY_COUNT_INVARIANT,
                f'every entity returned exactly {value} rows in all '
                f'{len(entity_counts)} entity-observations across '
                f'{n_captures} captures, with no variation at all. A live '
                f'census of a changing world does not do that; a page size '
                f'does.',
                value=value, n_entity_observations=len(entity_counts))
            finding(
                SUSPECTED_TRUNCATION,
                f'COVERAGE_NOT_ESTABLISHED / SUSPECTED_TRUNCATION at '
                f'{value} per entity. Completeness is unproven until the '
                f'endpoint semantics are established; absence from this feed '
                f'is not evidence of absence in the world.',
                page_size_suspected=value)

    if len(out['distinct_schemas']) > 1:
        finding(SCHEMA_DRIFT,
                f'{len(out["distinct_schemas"])} distinct field sets across '
                f'{n_captures} captures. A feed that changed shape mid-season '
                f'may have changed meaning too.',
                schemas=out['distinct_schemas'])

    if all_entities and len(out['entities_per_capture']) > 1:
        finding(ENTITY_COVERAGE_DROP,
                f'captures cover between {min(out["entities_per_capture"])} '
                f'and {max(out["entities_per_capture"])} entities out of '
                f'{len(all_entities)} ever seen, so some captures are missing '
                f'entities others carry',
                per_capture=out['entities_per_capture'])

    out['state'] = 'FINDINGS' if out['findings'] else 'NO_FINDINGS'
    out['reading'] = (
        'This reports SHAPE. It does not decide that a feed is broken, and '
        '"no findings" means these particular detectors found nothing rather '
        'than that the feed is complete.')
    return out


def completeness_axis(report: dict) -> dict:
    """Translate a census into the completeness axis of a validity report."""
    codes = {f['code'] for f in report.get('findings', ())}
    if SUSPECTED_TRUNCATION in codes:
        page = next((f.get('page_size_suspected')
                     for f in report['findings']
                     if f['code'] == SUSPECTED_TRUNCATION), None)
        return {'state': 'PARTIAL',
                'detail': (f'COVERAGE_NOT_ESTABLISHED / SUSPECTED_TRUNCATION '
                           f'at {page} per entity'),
                'page_size_suspected': page}
    if EMPTY_CAPTURE in codes:
        return {'state': 'FAIL', 'detail': 'every entity returned zero rows'}
    if report.get('n_captures', 0) < MIN_CAPTURES_FOR_INVARIANCE:
        return {'state': 'NOT_ESTABLISHED',
                'detail': (f'{report.get("n_captures")} capture(s) is below '
                           f'the floor of {MIN_CAPTURES_FOR_INVARIANCE} at '
                           f'which invariance becomes askable')}
    return {'state': 'PASS',
            'detail': 'counts vary across captures as a live feed should'}
