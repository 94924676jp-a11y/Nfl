#!/usr/bin/env python3.12
"""Every projection guard must FIRE on V0. That is what makes V0 worth keeping.

V0 (commit 89c919d) is the only bad projection board this project has. Its slate mean was
61% of a commercial baseline and four structural defects caused it. If a guard cannot catch
V0 it cannot catch a repeat, so each test below asserts the guard returns FAIL against the
real V0 artifact with the real defect named.

The contract for a future version: run `projection_guards.run_all` and every guard must
PASS. These tests will then be inverted for that version -- the guards are the reusable
part, V0 is the fixture proving they work.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import fc_context as FC  # noqa: E402
from nfl.tools import projection_guards as G  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402

V0 = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V0_VS_FC.json'
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
AUDIT = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PLACEHOLDER_PORTFOLIO_AUDIT.json'

from nfl.tests import _registry  # noqa: E402

#: RUN THIS MODULE IN A FRESH INTERPRETER. run_suite reads this from source and re-runs the
#: module through itself in a subprocess, so it is judged by identical logic.
REQUIRES_OWN_PROCESS = 'the level-band guard needs the external baseline from fc_context; in a proprietary interpreter the firewall refuses it and the guard reads LEVEL_BAND_SAMPLE_TOO_SMALL on 0 players'

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _load():
    v0 = json.loads(V0.read_text())
    post = json.loads(POST.read_text())
    players = post['players']
    fcr = FC.load()
    ext = {}
    if fcr.state is State.PASS:
        by, _, _ = FC.join_to_dk(fcr.value, players)
        ext = {k: ((v.get(FC.CONTEXT_KEY) or {}).get('FC Proj')) for k, v in by.items()}
    starters = {(v['name'], v['team']) for v in players.values()
                if (v.get('predicted_lineup_context') or {})
                .get('in_predicted_starting_group')}
    return v0['records'], players, ext, starters, post['identity_conflicts'], post


@check('V0 is preserved and is still the failed board we think it is')
def t_v0_preserved():
    v0 = json.loads(V0.read_text())
    assert v0['label'] == 'PROPRIETARY_V0_UNVALIDATED', v0['label']
    assert 'NOT_VALIDATED' in v0
    assert v0['counts']['PROPRIETARY_V0_UNVALIDATED'] == 247, v0['counts']
    ch = next(c for c in v0['comparison'] if c['player'] == "Ja'Marr Chase")
    assert ch['ours_mean'] < 9 and ch['fc_proj'] > 26, ch
    return (f"V0 intact: 247 means, Chase {ch['ours_mean']} vs FC {ch['fc_proj']} "
            f"(delta {ch['delta']}) still reproduces")


@check('GUARD FIRES: level out of band -- the one-line check I skipped')
def t_level():
    recs, players, ext, _, _, _ = _load()
    sal = {k: v.get('salary') for k, v in players.items()}
    r = G.assert_level_within_band(recs, ext, salaries=sal)
    assert r.state is State.FAIL, f'the level guard did not fire on V0: {r}'
    assert r.code == 'PROJECTION_LEVEL_OUT_OF_BAND'
    w = r.evidence['worst']
    assert w['ratio'] < 0.85, r.evidence
    # the flat mean must NOT be what the verdict rests on -- it passes on V0
    assert 0.85 <= r.evidence['flat_ratio'] <= 1.15, (
        'the flat ratio is out of band too, so this test no longer demonstrates that '
        'slicing is what catches V0')
    return (f"worst slice {w['slice']} ratio {w['ratio']} (ours {w['ours_mean']} vs "
            f"{w['external_mean']}, n={w['n']}); flat ratio "
            f"{r.evidence['flat_ratio']} would have PASSED")


@check('GUARD FIRES: established roles shrunk toward a population mean')
def t_established():
    recs, *_ = _load()
    r = G.assert_established_role_not_shrunk_down(recs)
    assert r.state is State.FAIL, f'did not fire on V0: {r}'
    assert r.code == 'ESTABLISHED_ROLE_SHRUNK_TOWARD_POPULATION_MEAN'
    assert r.evidence['n_violations'] >= 20, r.evidence['n_violations']
    worst = r.evidence['violations'][0]
    return (f"{r.evidence['n_violations']} cases; worst {worst['player']} "
            f"{worst['observed']} -> {worst['used']} ({worst['haircut_pct']}%)")


@check('GUARD FIRES: zero touchdown expectation on real volume')
def t_td():
    recs, *_ = _load()
    r = G.assert_td_rate_not_raw_count(recs)
    assert r.state is State.FAIL, f'did not fire on V0: {r}'
    assert r.code == 'ZERO_TD_EXPECTATION_ON_REAL_VOLUME'
    return (f"{r.evidence['n_violations']} player(s) with real volume and 0.000 expected "
            f"touchdowns: "
            f"{[v['player'] for v in r.evidence['violations'][:4]]}")


@check('GUARD FIRES: stale injury-replacement role retained')
def t_stale():
    recs, players, _, starters, _, _ = _load()
    r = G.assert_no_stale_replacement_role(recs, players, starters)
    assert r.state is State.FAIL, f'did not fire on V0: {r}'
    assert r.code == 'STALE_REPLACEMENT_ROLE_RETAINED'
    names = {v['player'] for v in r.evidence['violations']}
    assert 'Drew Lock' in names, names
    top = r.evidence['violations'][0]
    return (f"{r.evidence['n_violations']} non-starters at starter level; worst "
            f"{top['player']} {top['projected_points']} pts behind an available starter")


@check('GUARD FIRES: DST has no proprietary coverage')
def t_coverage():
    recs, players, *_ = _load()
    r = G.assert_positional_coverage(recs, players)
    assert r.state is State.FAIL, f'did not fire on V0: {r}'
    assert r.code == 'POSITION_HAS_NO_PROPRIETARY_COVERAGE'
    assert 'DST' in r.evidence['missing'], r.evidence
    return f"missing coverage: {r.evidence['missing']}; counts {r.evidence['counts']}"


@check('GUARD PASSES on V0: no unresolved identity was projected')
def t_identity():
    recs, players, _, _, conflicts, _ = _load()
    r = G.assert_cold_start_identity_resolved(recs, players, conflicts)
    assert r.state is State.PASS, str(r)
    mc = [v for k, v in recs.items() if v.get('player') == 'Malik McClain']
    assert mc and mc[0].get('mean') is None, mc
    return ('Malik McClain carries an OPEN identity conflict and V0 correctly declined to '
            'project him (mean is None, not a number)')


@check('GUARD PASSES on the portfolio audit: heavy exposure is classified')
def t_concentration():
    audit = json.loads(AUDIT.read_text())
    r = G.assert_concentration_classified(audit)
    assert r.state is State.PASS, str(r)
    w = next(c for c in audit['concentration_verdicts']
             if c['player'] == 'Deshaun Watson')
    assert w['verdict'] == 'SALARY_VALUE_ARTEFACT', w['verdict']
    assert w['fc_points_per_1k_salary'] == 4.55, w
    return (f"{r.value} players above 40%; Watson {w['exposure_pct']}% classified "
            f"{w['verdict']} at {w['fc_points_per_1k_salary']} pts per $1k")


@check('run_all reports every guard and V0 fails four of them')
def t_run_all():
    recs, players, ext, starters, conflicts, _ = _load()
    audit = json.loads(AUDIT.read_text())
    out = G.run_all(recs, players, ext, starters, conflicts, audit)
    failed = sorted(k for k, v in out.items() if v.state is State.FAIL)
    assert failed == ['established_role_not_shrunk_down', 'level_within_band',
                      'no_stale_replacement_role', 'positional_coverage',
                      'td_rate_not_raw_count'], failed
    assert len(failed) == 5, failed
    assert list(out)[0] == 'level_within_band', 'level check must run first'
    return f'{len(out)} guards run, {len(failed)} fail on V0: {failed}'


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
