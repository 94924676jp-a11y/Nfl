#!/usr/bin/env python3.12
"""The #99 shrinkage study's mechanism and its refusals.

The study's conclusion rests on a per-tier prior cap being a NO-OP when every tier gets the same
value. If it silently changed something else, every arm difference would be measuring that instead,
so that parity is checked here as well as inside the run.

The other checks are the ones that stop a convenient reading. A ratio to a near-zero denominator
exploded to 34.4 and would have been quotable as "separation"; a preregistered confirmation season
turned out to be one in which the treatment cannot act at all, and dropping such a season is exactly
the move that has to leave a trace.
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.shrinkage import study as S  # noqa: E402
from nfl.tools import proj_v1 as V  # noqa: E402

ART = _REPO / 'nfl/research/shrinkage/SHRINKAGE_STUDY.json'
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('a per-tier cap equal to the global cap changes nothing')
def t_parity():
    saved = dict(V.PRIOR_WEIGHT_CAP_BY_TIER)
    try:
        V.PRIOR_WEIGHT_CAP_BY_TIER = {}
        base = [V._combine(0.3, n, 0.1, c)[0] for n in (0.5, 2.0, 50.0) for c in (0, 1, 4)]
        V.PRIOR_WEIGHT_CAP_BY_TIER = {t: V.PRIOR_WEIGHT_CAP
                                      for t in S.OWN_TIERS + S.COHORT_TIERS}
        tiered = [V._combine(0.3, n, 0.1, c, cap=V.prior_cap_for('ROLE_GROUP'))[0]
                  for n in (0.5, 2.0, 50.0) for c in (0, 1, 4)]
    finally:
        V.PRIOR_WEIGHT_CAP_BY_TIER = saved
    assert base == tiered, f'per-tier cap is not a no-op at the global value: {base} != {tiered}'
    return f'{len(base)} (prior_n, current_n) combinations identical under both paths'


@check('an unknown tier falls back to the global cap rather than to zero')
def t_unknown_tier():
    saved = dict(V.PRIOR_WEIGHT_CAP_BY_TIER)
    try:
        V.PRIOR_WEIGHT_CAP_BY_TIER = {'ROLE_GROUP': 0.0}
        assert V.prior_cap_for('ROLE_GROUP') == 0.0
        assert V.prior_cap_for('SOME_TIER_ADDED_LATER') == V.PRIOR_WEIGHT_CAP, (
            'a tier not named in the override dict must keep the global cap. Defaulting it to 0 '
            'would silently switch off any tier added later.')
        assert V.prior_cap_for(None) == V.PRIOR_WEIGHT_CAP
    finally:
        V.PRIOR_WEIGHT_CAP_BY_TIER = saved
    return 'a named tier is overridden; an unnamed one and None keep the global cap'


@check('a cap of zero still supplies the prior when the current season is silent')
def t_fallback_survives():
    v, acct = V._combine(0.31, 500.0, None, 0, cap=0.0)
    assert v == 0.31 and acct['basis'] == 'PRIOR_ONLY', (
        'a cap of 0 must stop the prior OUTVOTING evidence, not stop it FILLING A GAP. If it also '
        'removed the fallback, a player with no current-season evidence would lose his number, '
        'which is the UNKNOWN-is-not-zero failure.')
    v2, acct2 = V._combine(0.31, 500.0, 0.12, 2, cap=0.0)
    assert v2 == 0.12 and acct2['prior_weight_fraction'] == 0.0
    return 'silent current season keeps the prior at weight 1.0; present evidence takes it to 0.0'


@check('a separation ratio refuses a near-zero denominator instead of exploding')
def t_ratio_floor():
    tiny = [0.0] * 30 + [40.0] * 5
    assert S.top_decile_to_median(tiny) is None, (
        'a top-decile-over-median ratio against a median of zero is undefined, not large. It '
        'returned 34.4 for ROLE_GROUP before this floor and was quotable as a finding.')
    real = list(range(1, 41))
    assert S.top_decile_to_median(real) is not None
    return 'a median at or below the declared floor returns None; an ordinary spread still reports'


@check('the artifact records the voided season rather than quietly dropping it')
def t_void_recorded():
    if not ART.exists():
        raise AssertionError(f'{ART} not built; run nfl/research/shrinkage/study.py')
    d = json.loads(ART.read_text())
    pre = d['PREREGISTERED']
    assert pre['confirmation_seasons_as_preregistered'] == [2021, 2022]
    assert pre['confirmation_seasons'] == [2022]
    assert '2021' in pre['confirmation_seasons_dropped'], (
        'a preregistered season was dropped after the data was seen. That is sometimes right and '
        'it is never allowed to be invisible.')
    v = d['VOID_SEASON_2021']
    assert v['state'] == 'VOID' and 'CONSEQUENCE_FOR_THE_EXISTING_CONSTANT' in v
    return 'the drop, its cause and its consequence for PRIOR_WEIGHT_CAP are all in the artifact'


@check('the artifact does not let itself be read as validating the projection system')
def t_not_validated():
    d = json.loads(ART.read_text())
    assert d['PROJECTION_SYSTEM_STATE'] == 'NOT_VALIDATED'
    assert 'MULTIPLICITY_COST' in d and 'TIERS_THE_HISTORY_CANNOT_TEST' in d
    lim = d['TIERS_THE_HISTORY_CANNOT_TEST']
    assert 'ARCHETYPE' in lim['observed_on_the_live_week_3_slate']
    assert 'ARCHETYPE' not in lim['observed_in_the_forward_chain'], (
        'if ARCHETYPE now appears in the chain this limitation is stale and the claim that the '
        'arm differences are a lower bound has to be re-derived')
    return 'NOT_VALIDATED, the multiplicity cost, and the tier the history cannot test are all stated'


@check('every arm is preregistered and production is among them as the reference')
def t_arms_declared():
    d = json.loads(ART.read_text())
    declared = {a['name'] for a in d['PREREGISTERED']['arms']}
    assert declared == set(d['arms']), f'arms run and arms declared differ: {declared ^ set(d["arms"])}'
    assert 'PRODUCTION' in declared
    prod = d['arms']['PRODUCTION']
    assert prod['own_cap'] == prod['cohort_cap'] == V.PRIOR_WEIGHT_CAP, (
        'the PRODUCTION arm must carry the cap production actually ships, or the comparison has no '
        'reference point')
    assert 'COHORT_ONLY' in declared, (
        'the mirror-image arm must be present. Without it the design only tests the direction it '
        'expected to win.')
    return f'{len(declared)} arms, declared before the run, production pinned at cap {V.PRIOR_WEIGHT_CAP}'


@check('the week-blocked SE treats weeks, not players, as the unit')
def t_blocked_se():
    per_week = [0.4, 0.5, 0.6, 0.5]
    m, se, n = S.block_mean_se(per_week)
    assert n == 4 and abs(m - 0.5) < 1e-9
    expect = statistics.stdev(per_week) / 2.0
    assert abs(se - expect) < 1e-12, f'{se} != {expect}'
    m2, se2, n2 = S.block_mean_se([0.4, None, 0.6])
    assert n2 == 2, 'a week with no computable statistic must drop out, not count as zero'
    d, dse, dn = S.paired_block([0.5, 0.6], [0.4, 0.4])
    assert dn == 2 and abs(d - 0.15) < 1e-9
    return 'SE divides by the number of WEEKS; an uncomputable week drops out rather than becoming 0'


@check('the conclusion rests on the cohort prior, not on the own-history prior')
def t_decomposition_holds():
    d = json.loads(ART.read_text())
    p = d['paired_vs_production']
    own_off = p['COHORT_ONLY']['confirmation.rho']['mean_diff_vs_production']
    cohort_off = p['OWN_ON_COHORT_OFF']['confirmation.rho']['mean_diff_vs_production']
    assert abs(cohort_off) > abs(own_off) * 3, (
        f'turning the cohort prior off is worth {cohort_off} and turning the own-history prior off '
        f'is worth {own_off}. The verdict says the cohort prior carries essentially all of it; if '
        f'that ordering has changed the verdict is stale.')
    both = p['OWN_OFF_COHORT_OFF']['confirmation.rho']['mean_diff_vs_production']
    assert both >= cohort_off, 'turning both off should not beat turning neither off'
    return (f'cohort off {cohort_off:+.4f} against own-history off {own_off:+.4f} on the '
            f'confirmation season')


# EXPOSE EVERY CHECK TO run_suite, which is the authoritative execution path. Without this the
# runner reports `0 fn, NO TALLY` and executes NONE of them, while a direct run of this file prints
# a confident pass. See nfl/tests/_registry.py.
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
    test_zz_every_check_passed.__doc__
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
