#!/usr/bin/env python3.12
"""The frontier must be a curve with declared constraints, not one hard-coded point.

These checks encode the owner's objection: a 15-point projection sacrifice cannot be
justified by the word "diversification", exposure caps are heuristics until a model derives
them, and no mode may be declared best while the field model does not exist.

Two of them exist because I got it wrong twice. `t_no_negative_gap` exists because my first
optimum reference was WORSE than the portfolios it bounded, which showed up as negative
gaps. `t_reference_is_a_lower_bound` exists because the owner's own file then beat my
corrected reference, proving the search is still not optimal.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import portfolio_frontier as PF  # noqa: E402
from nfl.tools import portfolio_modes as M  # noqa: E402

OWNER_SHA = '13ce2da14da94f961f8288f46faabeea016394290594338ca77124297f216e53'
ORDER = ['PROJECTION_MAX', 'LIGHT_DIVERSIFICATION', 'BALANCED', 'HIGH_DIVERSIFICATION']
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def art():
    assert PF.OUT.exists(), 'the frontier artifact has not been built'
    return json.loads(PF.OUT.read_text())


@check('four modes span the frontier and SIM_OPTIMAL is refused, not approximated')
def t_modes():
    a = art()
    for m in ORDER:
        assert m in a['modes'], f'{m} missing'
        assert a['modes'][m]['state'] == 'OK', a['modes'][m]
        assert a['modes'][m]['n'] == 48, a['modes'][m]['n']
    so = a['sim_optimal']
    assert so['state'] == 'UNAVAILABLE'
    assert len(so['requires']) == 4, so['requires']
    return (f'{len(ORDER)} modes at 48 lineups each; SIM_OPTIMAL UNAVAILABLE with '
            f'{len(so["requires"])} named missing inputs')


@check('the frontier is monotone: more diversification costs projection')
def t_monotone():
    a = art()
    means = [a['modes'][m]['proj_mean'] for m in ORDER]
    for i in range(len(means) - 1):
        assert means[i] >= means[i + 1] - 1e-9, (
            f'{ORDER[i]} {means[i]} < {ORDER[i + 1]} {means[i + 1]}: the curve is not '
            f'monotone, so the modes are not ordered by diversification')
    span = means[0] - means[-1]
    assert span > 0, 'no measurable cost at all, which would make the modes identical'
    return (f'{means[0]} -> {means[-1]}, a real cost of {span:.1f} points across the '
            f'frontier -- not the 15 I originally claimed')


@check('no negative gap: the reference cannot be worse than what it bounds')
def t_no_negative_gap():
    a = art()
    for m in ORDER:
        g = a['modes'][m]['gap_to_optimum_pct']
        assert g >= 0, (
            f'{m} has gap {g}: the reference is below the portfolio it bounds, which is '
            f'the local-optimum bug caught on 2026-09-27')
    return f'all {len(ORDER)} gaps non-negative'


@check('the reference is declared a LOWER BOUND, not a proven optimum')
def t_reference_is_a_lower_bound():
    a = art()
    assert 'BEST_KNOWN_NOT_PROVEN_OPTIMAL' in a, 'the reference claims to be optimal'
    assert 'lower bound' in a['BEST_KNOWN_NOT_PROVEN_OPTIMAL']
    o = a['optimum_legal_lineup']
    if 'beaten_by_benchmark' in o:
        b = o['beaten_by_benchmark']
        assert b['benchmark_best'] > b['search_best'], b
        assert 'NOT optimal' in b['implication']
    return ('reference labelled a lower bound'
            + (f'; benchmark {o["beaten_by_benchmark"]["benchmark_best"]} beat search '
               f'{o["beaten_by_benchmark"]["search_best"]}'
               if 'beaten_by_benchmark' in o else ''))


@check('every constraint declares value, reason, source and whether it bound')
def t_constraints_declared():
    a = art()
    for m in ORDER:
        cons = a['modes'][m]['constraints']
        assert cons, f'{m} has no declared constraints'
        for name, c in cons.items():
            for f in ('name', 'value', 'reason', 'source', 'became_binding'):
                assert f in c, f'{m}.{name} lacks {f}'
            assert c['source'] in (M.OWNER, M.HEURISTIC, M.MODEL_DERIVED), c
            if c['source'] != M.OWNER:
                assert c['reason'], f'{m}.{name} is a heuristic with no stated reason'
    owner_only = {n for n, c in a['modes']['BALANCED']['constraints'].items()
                  if c['source'] == M.OWNER}
    assert owner_only == {'salary_cap', 'no_duplicate_player',
                          'no_reported_absent_player'}, owner_only
    return (f'every constraint carries provenance; exactly {len(owner_only)} are '
            f'OWNER-sourced: {sorted(owner_only)}')


@check('no diversification constraint is MODEL_DERIVED yet, and that is stated')
def t_none_model_derived():
    a = art()
    derived = [(m, n) for m in ORDER
               for n, c in a['modes'][m]['constraints'].items()
               if c['source'] == M.MODEL_DERIVED]
    assert not derived, f'a constraint claims model provenance it does not have: {derived}'
    return ('zero MODEL_DERIVED constraints: every exposure cap is an admitted heuristic '
            'until the field model exists')


@check('PROJECTION_MAX is genuinely unconstrained on diversification')
def t_projection_max_unbound():
    a = art()
    s = a['modes']['PROJECTION_MAX']
    assert not s['binding_constraints'], s['binding_constraints']
    c = s['constraints']
    assert c['max_player_exposure']['value'] == 1.0
    assert c['max_qb_exposure']['value'] == 1.0
    assert c['max_pairwise_overlap']['value'] == 9
    for m in ORDER[1:]:
        assert a['modes'][m]['binding_constraints'], (
            f'{m} constrains nothing, so it is not a distinct point on the curve')
    return ('PROJECTION_MAX binds nothing; all three diversified modes have binding caps, '
            'so the curve has four real points')


@check('no mode is declared best, and the reason is recorded')
def t_no_winner():
    a = art()
    assert 'NO_MODE_IS_BEST' in a
    txt = a['NO_MODE_IS_BEST']
    assert 'ownership model' in txt and 'simulation' in txt
    blob = json.dumps(a['modes'])
    for banned in ('"recommended"', '"best_mode"', '"winner"'):
        assert banned not in blob, f'the artifact names a {banned}'
    return 'no winner declared; missing inputs named'


@check("the owner benchmark is scored on the same yardstick and never modified")
def t_benchmark():
    a = art()
    b = a.get('owner_benchmark')
    assert b, 'no benchmark comparison'
    assert b['mode'] == 'OWNER_FC_PLACEHOLDERS'
    assert b['n'] == 48, b['n']
    assert 'never modified' in b['intent'].lower()
    assert 'biases this benchmark DOWN' in b['note']
    digest = hashlib.sha256(PF.OWNER_CSV.read_bytes()).hexdigest()
    assert digest == OWNER_SHA, 'the owner placeholder file changed'
    return (f'benchmark mean {b["proj_mean"]} vs PROJECTION_MAX '
            f'{a["modes"]["PROJECTION_MAX"]["proj_mean"]}; owner file byte-identical')


@check('the projection-loss guard reports a number, not a phrase')
def t_loss_guard():
    a = art()
    for m in ORDER:
        g = a['modes'][m]['projection_loss_guard']
        for f in ('mean_loss_vs_optimum', 'max_loss_guardrail', 'state',
                  'guardrail_source'):
            assert f in g, f'{m} loss guard lacks {f}'
        assert isinstance(g['mean_loss_vs_optimum'], float)
        assert g['guardrail_source'] == M.HEURISTIC
    return 'every mode reports a measured loss against the reference'


@check('totals are labelled FC, never described as ours')
def t_fc_labelled():
    a = art()
    assert a['projection_source'] == 'EXTERNAL_FC_FALLBACK'
    assert 'not our model' in a['NOT_OUR_PROJECTION'].lower()
    return 'every total labelled FantasyCruncher'


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
