#!/usr/bin/env python3.12
"""Two guards named `assert_publishable`. One STOPS a forecast. One does not.

The census recorded both as NOT_ESTABLISHED. Both are now established, and they
land in different places, which is the point: a guard does not earn LOAD_BEARING
by having tests, by being imported, or by emitting PASS/FAIL. It earns it when
bad state -> guard fails -> the caller receives the failure -> the protected
action does not happen.

A. `current_season_team_volume.assert_publishable` IS LOAD-BEARING. The census
   labelled its site DOWNGRADE, which is right locally and understates it: the
   downgrade CHAINS INTO A STOP. run_forecast.py:1587 builds `verified_inputs`
   only when the guard PASSes, `denom_panel` is declared blocked in
   nfl.production.freshness.REGISTRY, so an empty verified set leaves it blocked,
   and assert_fresh then refuses BEFORE SIMULATION.

B. `layers.assert_publishable` IS ADVISORY, and that is not a defect. Its
   docstring claims a run touched by a TEST-ONLY fixture "can never become an
   artifact", and football_engine.py:2063 writes its verdict into a string and
   never consults it again -- while the same function refuses 25 other ways.
   It looks like an unenforced publication gate. It is not, because the only
   route to `test_only` in the production path is `--dry-run`, which IS tagged
   and IS refused downstream by q9shadow.ledger.assert_not_dry_run.

   So B is REDUNDANT rather than missing -- but the redundancy is only safe while
   two specific properties hold, and both are pinned below. If either stops
   holding, B's discarded FAIL becomes the only detection, and it is discarded.
"""
from __future__ import annotations

import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import current_season_evidence as CSE
from nfl.production.nonqb import layers as LY
from nfl.production import freshness as FRESH
from nfl.prospective.q9shadow import ledger as QL
from sportsplatform.governance.outcome import Outcome, State, Cause

passed = failed = 0


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label} {detail}')


# Week 3 with the prior week present, so freshness turns ONLY on verified_inputs.
# The key is `max_week_used`; an earlier draft of this test used `max_week` and
# both arms blocked, which looked like the guard failing to discriminate and was
# really the fixture being wrong.
EV = Outcome.ok('CURRENT_SEASON_EVIDENCE_OK',
                {'weeks_present': [1, 2], 'max_week_used': 2,
                 'by_player': {'X': {}}, 'n_players': 1}, 'fixture')
GOOD = Outcome.ok('TEAM_VOLUME_PUBLISHABLE', None, 'fixture PASS')
BAD = Outcome.blocked('TEAM_VOLUME_PARTIAL_DENOMINATOR', 'fixture FAIL',
                      cause=Cause.DATA)


def _freshness(tvp):
    """Exactly run_forecast.py:1587's construction of verified_inputs."""
    verified = ({'denom_panel': tvp, 'team_volume_history': tvp}
                if tvp.state is State.PASS else {})
    return CSE.assert_fresh(EV, season=2026, week=3, verified_inputs=verified)


def test_a_the_chain_the_load_bearing_claim_rests_on():
    check('denom_panel is declared blocked in the registry',
          'denom_panel' in CSE.declared_blocked_inputs(),
          sorted(CSE.declared_blocked_inputs()))
    check('  and the declaration comes from the freshness REGISTRY',
          bool(FRESH.REGISTRY.get('denom_panel', {}).get('declared_blocked')))


def test_a_the_guard_discriminates_and_a_failure_stops_the_forecast():
    good, bad = _freshness(GOOD), _freshness(BAD)
    check('PASS -> freshness PASSes, the run proceeds',
          good.state is State.PASS, f'{good.state.value}[{good.code}]')
    check('FAIL -> freshness BLOCKS, run_forecast returns before simulation',
          bad.state is not State.PASS, f'{bad.state.value}[{bad.code}]')
    check('  and the two arms differ, so the guard is not decorative',
          (good.state is State.PASS) != (bad.state is State.PASS))


def test_a_the_key_is_not_the_verification():
    # Smuggling a non-PASS outcome in under the right key must not unblock it,
    # or the gate is a keyring.
    f = CSE.assert_fresh(EV, season=2026, week=3,
                         verified_inputs={'denom_panel': BAD,
                                          'team_volume_history': BAD})
    check('a non-PASS outcome under the right key is still blocked',
          f.state is not State.PASS, f'{f.state.value}[{f.code}]')


def test_a_run_forecast_really_returns_on_that_refusal():
    # The early return is read from the source rather than trusted, because the
    # whole claim is that the CALLER acts on the verdict.
    src = (_REPO / 'nfl/production/run_forecast.py').read_text()
    tree = ast.parse(src)
    found = False
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        t = ast.unparse(n.test)
        if '_fresh.state' in t and 'PASS' in t:
            body = ast.unparse(n)
            found = found or ('return' in body and 'fatal' in body)
    check('run_forecast returns a fatal outcome when freshness is not PASS',
          found)


def test_b_the_layers_guard_fires_but_its_caller_never_consults_it():
    clean = Outcome.ok('LAYER_OK', None, 'no fixture')
    tainted = Outcome.ok('LAYER_FROM_FIXTURE', None, 'fixture', test_only=True)
    check('clean -> PASS',
          LY.assert_publishable(clean, clean).state is State.PASS)
    bad = LY.assert_publishable(clean, tainted)
    check('tainted -> FAIL', bad.state is not State.PASS, bad.code)
    check('  named TEST_ONLY_DATA_IN_PRODUCTION_PATH',
          bad.code == 'TEST_ONLY_DATA_IN_PRODUCTION_PATH', bad.code)

    # AST, not string matching: find the binding and look for any branch on it.
    tree = ast.parse((_REPO
                      / 'nfl/production/nonqb/football_engine.py').read_text())
    site = None
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for n in ast.walk(fn):
            if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                    and 'assert_publishable' in ast.unparse(n.value.func)):
                site = (fn, n)
    check('the call site is found', site is not None)
    if site:
        fn, assign = site
        name = assign.targets[0].id
        consulted = [type(n).__name__ for n in ast.walk(fn)
                     if isinstance(n, (ast.If, ast.Assert, ast.Raise))
                     and any(isinstance(x, ast.Name) and x.id == name
                             for x in ast.walk(n))]
        check('no branch, assert or raise consults the verdict -- ADVISORY',
              not consulted, consulted)
        refusals = [n for n in ast.walk(fn) if isinstance(n, ast.Return)
                    and 'None' in ast.unparse(n)]
        check('  while the same function refuses many other ways',
              len(refusals) > 10, len(refusals))


def test_b_property_one_the_production_call_site_passes_no_fixture():
    # football_engine builds a TEST-ONLY fixture iff injuries_rows is not None.
    # run_forecast hard-codes None. If that changes, `test_only` can become true
    # with dry_run false, and then B's discarded FAIL is the only detection.
    tree = ast.parse((_REPO / 'nfl/production/run_forecast.py').read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and 'run_game' in ast.unparse(n.func)]
    check('exactly one production run_game call site', len(calls) == 1,
          len(calls))
    for c in calls:
        kw = {k.arg: ast.unparse(k.value) for k in c.keywords}
        check('injuries_rows is passed as a literal None', kw.get(
            'injuries_rows') == 'None', kw.get('injuries_rows'))
        check('and test_only comes from the dry_run flag alone',
              'dry_run' in (kw.get('test_only') or ''), kw.get('test_only'))


def test_b_property_two_a_dry_run_artifact_is_refused_as_evidence():
    # The mechanism that actually enforces what B advertises.
    for art, why in (({'dry_run': True, 'forecast_id': 'f1'}, 'dry_run true'),
                     ({'prospective_evidence': False, 'forecast_id': 'f2'},
                      'prospective_evidence false')):
        o = QL.assert_not_dry_run(art)
        check(f'{why} -> not counted as evidence', o.state is not State.PASS,
              f'{o.state.value}[{o.code}]')
    o = QL.assert_not_dry_run({'forecast_id': 'f3'})
    check('an ordinary artifact IS prospective', o.state is State.PASS, o.code)


def test_b_property_three_run_forecast_tags_the_dry_run():
    src = (_REPO / 'nfl/production/run_forecast.py').read_text()
    check("summary['dry_run'] is written from args.dry_run",
          "summary['dry_run'] = bool(args.dry_run)" in src)
    check("  and prospective_eligible is forced False for a dry run",
          "summary['prospective_eligible'] = False if args.dry_run else None"
          in src)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_publishable_guards_are_load_bearing: {passed} ok, '
          f'{failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
