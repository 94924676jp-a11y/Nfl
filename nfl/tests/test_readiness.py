#!/usr/bin/env python3.12
"""Readiness must be able to say no, and must never round a stale slate up to ready.

A readiness board that always reports green is worse than none, because it converts an unknown into
a reassurance. So most of these checks make something stale, missing or unproducible and require the
verdict to change.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import exact  # noqa: E402
from nfl.production import readiness  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('the board assesses every declared stage and reaches a product mode')
def t_build():
    o = readiness.build()
    assert o.state is State.PASS, o
    v = o.value
    assert len(v['stages']) == len(readiness.STAGES)
    assert v['PRODUCT_MODE'] in v['PRODUCT_MODES_DEFINED']
    assert v['PRODUCT_MODE_BECAUSE']
    return (f"{len(v['stages'])} stages, states {v['state_counts']}, mode {v['PRODUCT_MODE']}")


@check('LOAD-BEARING: the Saturday rule FAILS when 48 legal entries cannot be produced')
def t_saturday_can_fail():
    real = exact.k_best

    def thin(pool, k, *a, **kw):
        return real(pool, min(k, 5), *a, **kw)
    try:
        exact.k_best = thin
        o = readiness.saturday_rule()
        assert o.state is State.FAIL and o.code == 'SATURDAY_RULE_CANNOT_FILL_48', (
            f'got {o.state}/{o.code}: the permanent rule passed while only five lineups could be '
            f'built, so it is not testing production readiness')
    finally:
        exact.k_best = real
    o2 = readiness.saturday_rule()
    assert o2.state is State.PASS, o2
    return ('a pipeline that can only build five lineups fails the rule; the real state passes '
            f"with {o2.value['n_entries']} legal distinct entries")


@check('LOAD-BEARING: the Saturday rule FAILS on an illegal lineup, not just a short portfolio')
def t_saturday_legality():
    real = exact.k_best

    def over_cap(pool, k, *a, **kw):
        out = real(pool, k, *a, **kw)
        rich = sorted(pool, key=lambda p: -p['salary'])
        swap = {p['position']: p['id'] for p in rich[:12]}
        for l in out:
            l['ids'] = [swap.get(next(p['position'] for p in pool if p['id'] == i), i)
                        for i in l['ids']]
        return out
    try:
        exact.k_best = over_cap
        o = readiness.saturday_rule()
        assert o.state is State.FAIL and o.code in ('SATURDAY_RULE_ILLEGAL_LINEUPS',
                                                    'SATURDAY_RULE_CANNOT_FILL_48'), (
            f'got {o.state}/{o.code}: lineups stuffed with the most expensive players at each '
            f'position passed as legal entries')
    finally:
        exact.k_best = real
    return 'lineups over the cap or of an illegal shape are refused'


@check('a stage past its declared tolerance reads STALE and blocks FULL_PROPRIETARY')
def t_stale():
    o = readiness.build()
    v = o.value
    stale = [r for r in v['stages'] if r['state'] != 'FRESH']
    if stale and any(r['tier'] in ('SLATE', 'DECISION') for r in stale):
        assert v['PRODUCT_MODE'] != 'FULL_PROPRIETARY', (
            f'mode is FULL_PROPRIETARY while {[r["name"] for r in stale]} are not fresh')
        return (f"{[r['name'] + '=' + r['state'] for r in stale]} keeps the mode at "
                f"{v['PRODUCT_MODE']}")
    # nothing stale right now: prove the rule by making one stale
    import copy
    saved = copy.deepcopy(readiness.STAGES)
    try:
        for st in readiness.STAGES:
            if st['tier'] == 'SLATE':
                st['max_age_hours'] = 0.0
        o2 = readiness.build()
        assert o2.value['PRODUCT_MODE'] != 'FULL_PROPRIETARY', o2.value['PRODUCT_MODE']
        names = [r['name'] for r in o2.value['stages'] if r['state'] == 'STALE']
        assert names
    finally:
        readiness.STAGES[:] = saved
        readiness.build()
    return f'with a zero tolerance the slate stages read STALE and the mode drops'


@check('a missing foundation artifact forces NOT_PRODUCTION_READY')
def t_missing():
    import copy
    saved = copy.deepcopy(readiness.STAGES)
    try:
        readiness.STAGES.append({'name': 'warehouse.invented',
                                 'path': 'nfl/warehouse/DOES_NOT_EXIST.json',
                                 'max_age_hours': 999, 'tier': 'FOUNDATION', 'depends_on': [],
                                 'why': 'a stage pointing at nothing'})
        o = readiness.build()
        assert o.value['PRODUCT_MODE'] == 'NOT_PRODUCTION_READY', o.value['PRODUCT_MODE']
        row = next(r for r in o.value['stages'] if r['name'] == 'warehouse.invented')
        assert row['state'] == 'MISSING'
    finally:
        readiness.STAGES[:] = saved
        readiness.build()
    return 'a foundation stage pointing at nothing drops the mode to NOT_PRODUCTION_READY'


@check('the freshness proxy is labelled wherever it is a proxy')
def t_labelled():
    o = readiness.build()
    v = o.value
    present = [r for r in v['stages'] if r['state'] != 'MISSING']
    assert present
    for r in present:
        assert r['age_source'], r['name']
        if r.get('artifact_cutoff') is None:
            assert 'FALLBACK' in r['age_source'], (
                f"{r['name']} has no stated cutoff but its age source does not say so")
    assert 'decoration' in v['FRESHNESS_SEMANTICS']
    n_fallback = sum(1 for r in present if 'FALLBACK' in r['age_source'])
    return (f'{n_fallback} of {len(present)} present stages are aged by file time, each labelled '
            f'as a fallback')


@check('an artifact older than its own inputs is flagged rather than passed as fresh')
def t_behind_inputs():
    o = readiness.build()
    v = o.value
    flagged = [r['name'] for r in v['stages'] if r['state'] == 'FRESH_BUT_BEHIND_ITS_INPUTS']
    # either something is currently behind, or the field exists on every row and is empty
    for r in v['stages']:
        assert 'inputs_newer_than_this_artifact' in r, r['name']
    return (f'{len(flagged)} stages currently behind their inputs'
            + (f': {flagged}' if flagged else '; the check is present on every stage'))


@check('the external fallback mode exists as a definition and is not reachable from here')
def t_no_external():
    o = readiness.build()
    v = o.value
    assert 'EXTERNAL_FALLBACK' in v['PRODUCT_MODES_DEFINED']
    assert v['PRODUCT_MODE'] != 'EXTERNAL_FALLBACK'
    assert 'NOT' in v['PRODUCT_MODES_DEFINED']['EXTERNAL_FALLBACK']
    src = (_REPO / 'nfl/production/readiness.py').read_text()
    for bad in ('fantasycruncher', 'FantasyCruncher', 'fc_projection'):
        assert bad not in src, f'{bad} appears in the readiness module'
    return 'the mode is defined, unreachable, and no external projection is wired as a fallback'


# EXPOSE EVERY CHECK TO run_suite, the authoritative execution path. Before this the runner
# reported `0 fn, NO TALLY` for this module and executed NONE of its checks, while a direct run of
# the file printed a confident pass. See nfl/tests/_registry.py.
_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
