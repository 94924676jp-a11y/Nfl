#!/usr/bin/env python3.12
"""The search-quality gate must fire today and must be clearable in principle.

Owner ruling 2026-09-27: the FC placeholder portfolio is a minimum search-quality regression
target, and an optimizer that cannot recover it fails the build.

Two things have to be true for this gate to be worth anything. It must FAIL on the current
optimizer -- otherwise it measures nothing. And it must PASS when fed a result that meets the
floor -- otherwise it is unclearable and would just be a permanent red light nobody acts on.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import search_quality_gate as G  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('the gate now PASSES, on a PROVEN optimum rather than a search result')
def t_passes_on_exact():
    r = G.evaluate()
    assert r.state is State.PASS, f'the gate failed on the exact solver: {r}'
    checks = r.value['checks'] if isinstance(r.value, dict) else r.evidence['checks']
    assert all(c['pass'] for c in checks), [c for c in checks if not c['pass']]
    for c in checks:
        assert c.get('optimality') == 'PROVEN_OPTIMAL', (
            f"{c['check']} cleared the floor without proving optimality: {c.get('optimality')}. A "
            f"gate cleared by an unproven search is the thing this file exists to prevent.")
    return '; '.join(f"{c['check']} {c['optimizer']} vs {c['benchmark']}" for c in checks)


@check('LOAD-BEARING: the gate still FAILS on a degraded search, so it measures something')
def t_still_measures():
    # A gate that cannot fail is decoration. Feed it a deliberately worse result and require a
    # refusal -- this is the check that survived the optimiser being fixed.
    import copy
    art = json.loads(G.FRONTIER.read_text())
    saved = G.FRONTIER.read_text()
    worse = copy.deepcopy(art)
    for m in worse.get('modes', {}).values():
        if isinstance(m, dict) and m.get('state') == 'OK':
            m['proj_max'] = 100.0
            m['proj_mean'] = 95.0
    try:
        G.FRONTIER.write_text(json.dumps(worse))
        # the exact path is what clears the floor, so degrade it too by banning the whole pool
        real = G.exact_check
        G.exact_check = lambda: Outcome.fail('STUBBED_WORSE_SEARCH', 'deliberately degraded',
                                             exact_optimum=100.0, exact_top_n_mean=95.0,
                                             optimality='HEURISTIC',
                                             clears_portfolio_floor=False)
        r = G.evaluate()
        assert r.state is State.FAIL, (
            'the gate passed on a search scoring 100 against a 171.59 floor, so it is no longer '
            'measuring anything')
        assert r.code == 'SEARCH_QUALITY_BELOW_BENCHMARK', r.code
    finally:
        G.exact_check = real
        G.FRONTIER.write_text(saved)
        G.evaluate()
    return 'refused a search at 100.0 against a 171.59 floor; real state restored'


@check('the gate PASSES when the floor is met, so it is clearable')
def t_clearable():
    art = json.loads(G.FRONTIER.read_text())
    faked = copy.deepcopy(art)
    m = faked['modes'][G.COMPARISON_MODE]
    m['proj_max'] = G.BENCHMARK['best_single_lineup'] + 0.01
    m['proj_mean'] = G.BENCHMARK['portfolio_mean'] + 0.01
    faked['optimum_legal_lineup'].pop('source', None)
    faked['optimum_legal_lineup'].pop('beaten_by_benchmark', None)
    r = G.evaluate(faked)
    assert r.state is State.PASS, f'the gate cannot be cleared even at the floor: {r}'
    # restore the real artifact's gate output so the repo does not hold a faked GREEN
    G.evaluate()
    return 'a search meeting both floors clears the gate; real state restored afterwards'


@check('the optimum is computed from the pool, not taken from the benchmark file')
def t_not_copied_from_benchmark():
    # UPDATED DELIBERATELY. The old check required the reference to come FROM the benchmark file and
    # therefore to be below it, which was the correct test while the search could not reach the
    # floor. Now the optimum is solved for, so the property that matters is the opposite: it must be
    # computed, and being ABOVE the benchmark is the evidence that it was not copied from it.
    r = G.exact_check()
    assert r.state is State.PASS, r
    v = r.value
    assert v['exact_optimum'] > G.BENCHMARK['best_single_lineup'], (
        f"the computed optimum {v['exact_optimum']} merely equals the benchmark, which is what "
        f"copying it would look like")
    assert v['pool_size'] > 200, f"pool of {v['pool_size']} is too small to be the real slate"
    assert 'PROOF' in v and 'exhaustive' in v['PROOF']
    names = {row['name'] for row in v['lineup']}
    assert len(names) == 9, names
    return (f"computed {v['exact_optimum']} from a {v['pool_size']}-player pool, "
            f"{v['margin_over_benchmark']:+.2f} over the benchmark")


@check('the benchmark is frozen with its digest and the file is unchanged')
def t_benchmark_frozen():
    b = G.BENCHMARK
    p = _REPO / b['source']
    assert p.exists(), b['source']
    assert hashlib.sha256(p.read_bytes()).hexdigest() == b['source_sha256'], (
        'the benchmark file changed, so the frozen floors no longer describe it')
    assert b['n_lineups'] == 48
    assert 'understated' in b['downward_bias_note']
    return f'{p.name} digest matches; floors {b["best_single_lineup"]}/{b["portfolio_mean"]}'


@check('the comparison is unconstrained, not against a diversified mode')
def t_unconstrained_comparison():
    assert G.COMPARISON_MODE == 'PROJECTION_MAX', G.COMPARISON_MODE
    art = json.loads(G.FRONTIER.read_text())
    assert not art['modes'][G.COMPARISON_MODE]['binding_constraints'], (
        'the comparison mode has binding diversification caps, which would confuse a '
        'deliberate trade-off with a search defect')
    return ('compared against PROJECTION_MAX with zero binding caps, so a diversification '
            'choice cannot be mistaken for a search failure')


@check('the gate records how it went from red to green, and prices diversification')
def t_records_history():
    G.evaluate()
    a = json.loads(G.OUT.read_text())
    assert a['state'] == 'GREEN', a['state']
    assert 'HISTORY' in a and 'hill-climb' in a['HISTORY'], (
        'the gate no longer records that it was red for the hill-climb. A gate that forgets what it '
        'used to refuse cannot be trusted to refuse again.')
    assert 'owner_ruling' in a
    dp = a.get('diversification_price') or {}
    assert dp.get('price_in_dk_points') is not None, (
        'the price of diversification is not recorded. Without it, a diversified portfolio scoring '
        'below the floor looks like a search failure, which is the confusion this gate caused '
        'before.')
    assert dp['price_in_dk_points'] > 0
    return (f"state GREEN; diversification costs {dp['price_in_dk_points']} DK points against a "
            f"proven maximum")


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
