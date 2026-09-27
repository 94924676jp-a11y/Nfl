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
from sportsplatform.governance.outcome import State  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('the gate FAILS on the current optimizer, so it measures something')
def t_fires():
    r = G.evaluate()
    assert r.state is State.FAIL, f'the gate passed on a search we know is worse: {r}'
    assert r.code == 'SEARCH_QUALITY_BELOW_BENCHMARK'
    bad = [c for c in r.evidence['checks'] if not c['pass']]
    assert len(bad) == 2, bad
    return '; '.join(f'{c["check"]} short {c["shortfall"]}' for c in bad)


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


@check('a benchmark lineup does not count as the optimizer finding it')
def t_no_credit_for_benchmark():
    art = json.loads(G.FRONTIER.read_text())
    ref = art['optimum_legal_lineup']
    assert ref.get('source') == 'OWNER_BENCHMARK_LINEUP', (
        'the reference no longer comes from the benchmark; update this test deliberately')
    r = G.evaluate()
    best = next(c for c in r.evidence['checks'] if c['check'] == 'best_single_lineup')
    assert best['optimizer'] < G.BENCHMARK['best_single_lineup'], (
        'the optimizer was credited with a lineup that came from the benchmark file')
    return (f'optimizer credited {best["optimizer"]}, not the benchmark-sourced '
            f'{G.BENCHMARK["best_single_lineup"]}')


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


@check('the gate records that being red today is intentional')
def t_intentionally_red():
    G.evaluate()
    a = json.loads(G.OUT.read_text())
    assert a['state'] == 'RED', a['state']
    assert 'DELIBERATELY_RED_TODAY' in a
    assert 'would not be measuring anything' in a['DELIBERATELY_RED_TODAY']
    assert 'owner_ruling' in a
    return f'state {a["state"]}, ruling recorded, {a["n_failed"]} floors unmet'


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
