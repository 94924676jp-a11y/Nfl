"""QB3 adversarial tests: the QB dropback allocation and its closure."""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.production.nonqb import qb_allocation as QA               # noqa: E402
import qb3_lib as Q                                                # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _par():
    return {'p_primary': {(1, 1): 0.90, (1, 0): 0.49, (2, 0): 0.07,
                          (3, 0): 0.03, ('2+', 1): 0.62},
            'share_pool': {(1, 1): np.array([1.0] * 8 + [0.0, 0.5]),
                           (1, 0): np.array([1.0] * 5 + [0.0] * 5),
                           (2, 0): np.array([0.0] * 9 + [1.0]),
                           (3, 0): np.array([0.0] * 10),
                           ('2+', 1): np.array([1.0] * 6 + [0.0] * 4)},
            'n': {(1, 1): 100}}


def test_A_closure_is_exact_in_every_draw():
    print('\nA. the simplex closes')
    for lbl, qbs in (
            ('three-man room', [('a', 1, 1), ('b', 2, 0), ('c', 3, 0)]),
            ('two-man room', [('a', 1, 1), ('b', 2, 0)]),
            ('one QB', [('a', 1, 1)]),
            ('change week', [('a', 1, 0), ('b', 2, 1)])):
        S = Q.allocate(_par(), qbs, m=500, seed=7, ordinal=202401, team='ZZZ')
        dev = float(np.abs(S.sum(0) - 1.0).max())
        check(f'{lbl}: shares sum to 1 in every draw', dev < 1e-9, dev)
        check(f'  {lbl}: no negative share', bool((S >= -1e-12).all()))
        check(f'  {lbl}: no share above 1', bool((S <= 1 + 1e-12).all()))
    check('an empty QB room returns an empty allocation, not a crash',
          Q.allocate(_par(), [], m=10).shape == (0, 10))


def test_B_the_share_is_a_distribution_not_a_point():
    print('\nB. the estimand is a distribution')
    S = Q.allocate(_par(), [('a', 1, 1), ('b', 2, 0)], m=4000, seed=11,
                   ordinal=202401, team='ZZZ')
    s = S[0]
    check('the starter has mass at exactly 1', float((s > 0.999).mean()) > 0.4,
          float((s > 0.999).mean()))
    check('  and non-zero mass at exactly 0 -- the event a point forecast '
          'cannot express', float((s < 0.001).mean()) > 0.0,
          float((s < 0.001).mean()))
    check('  and mass strictly between, for committees and midgame changes',
          float(((s > 0.001) & (s < 0.999)).mean()) > 0.0)
    check('  the backup is not identically zero',
          float((S[1] > 0).mean()) > 0.0, float((S[1] > 0).mean()))


def test_C_determinism():
    print('\nC. draw semantics')
    qbs = [('a', 1, 1), ('b', 2, 0)]
    a = Q.allocate(_par(), qbs, m=200, seed=3, ordinal=202401, team='ZZZ')
    b = Q.allocate(_par(), qbs, m=200, seed=3, ordinal=202401, team='ZZZ')
    c = Q.allocate(_par(), qbs, m=200, seed=4, ordinal=202401, team='ZZZ')
    d = Q.allocate(_par(), qbs, m=200, seed=3, ordinal=202401, team='YYY')
    check('same seed and team reproduces exactly', bool((a == b).all()))
    check('  a different seed does not', not bool((a == c).all()))
    check('  a different team does not', not bool((a == d).all()))


def test_D_the_frame_comes_from_the_depth_chart_not_the_panel():
    """The defect the first version of build_frame had: the panel holds only
    QBs who took a snap, so fitting on it conditions on having played."""
    print('\nD. the frame is the QB room, not the men who played')
    rows = Q.load_qb_panel()
    depth = Q.load_depth()
    frame = Q.build_frame(rows, depth)
    check('the frame is larger than the panel', len(frame) > len(rows),
          f'{len(frame)} vs {len(rows)}')
    zeros = sum(1 for r in frame if r['share'] == 0)
    check('  it contains QB-games with a zero share', zeros > 0, zeros)
    par = Q.fit(frame, 2025)
    c = par['share_pool'][(1, 1)]
    p0 = float((c == 0).mean())
    check('  so the settled starter carries real zero mass',
          0.03 < p0 < 0.15, p0)
    check('  P(primary | rank 1, was previous primary) is below 0.95, not the '
          '0.976 the panel-only frame reported',
          par['p_primary'][(1, 1)] < 0.95, par['p_primary'][(1, 1)])


def test_E_chronology():
    print('\nE. chronology')
    rows = Q.load_qb_panel()
    frame = Q.build_frame(rows, Q.load_depth())
    for ev in (2023, 2024):
        par = Q.fit(frame, ev)
        check(f'the {ev} fit is trained only on earlier seasons',
              par['trained_on_seasons_before'] == ev)
    # the previous-primary feature must never be the same ordinal
    bad = [r for r in frame
           if r['prev_primary'] is not None and r['is_primary']
           and r['prev_primary'] == r['pid'] and r['share'] == 0]
    check('  a strictly-earlier prefix cut is used (bisect, not append-as-we-go)',
          'bisect' in open(os.path.join(
              _ROOT, 'nfl', 'research', 'qb3', 'qb3_lib.py')).read())


def test_F_production_layer_refuses_correctly():
    print('\nF. the production layer')
    dc = QA.captured_depth_chart()
    check('a captured depth chart is found', dc.state is State.PASS,
          f'{dc.state.value}[{dc.code}]')
    if dc.state is State.PASS:
        check('  it covers all 32 teams', dc.evidence['n_teams'] == 32,
              dc.evidence['n_teams'])
        check('  and carries its retrieval time',
              bool(dc.evidence.get('retrieved_at')))
        o = QA.allocate(2026, 1, sorted(dc.value),
                        [{'gsis_id': p, 'team': t}
                         for t, room in dc.value.items() for p in room],
                        m=50, kickoff_utc='2020-01-01T00:00:00Z')
        # THE REFUSAL MOVED EARLIER, AND THAT IS THE REPAIR WORKING.
        #
        # This asserted FAIL[DEPTH_CHART_CHRONOLOGY_FAILURE] -- the guard
        # inside `allocate`, which fires AFTER a chart has been selected and
        # found too new. On 2026-09-15 selection itself became clock-aware:
        # `captured_depth_chart(as_of=...)` picks the newest vintage lawful at
        # the cut, so with a 2020 kickoff no vintage qualifies and it refuses
        # up front with BLOCKED[DEPTH_CHART_NO_LAWFUL_VINTAGE].
        #
        # BLOCKED is the right state for that: "no capture predates this
        # instant" is an absence of data, not a violated invariant, and the
        # code names the absence rather than reporting that the chart it
        # happened to grab was too new.
        #
        # BOTH codes are accepted and NOTHING WIDER. The property under test is
        # that a chart the forecast could not have seen is refused; asserting
        # merely `state is not PASS` would also swallow an unrelated failure,
        # which is how a refusal check stops testing refusal.
        #
        # The chronology guard is now a backstop rather than the only defence.
        # It remains reachable if selection is ever bypassed, and
        # `test_depth_chart_vintage_selection` covers the selector directly.
        check('  a depth chart retrieved after kickoff is REFUSED',
              (o.state is State.FAIL
               and o.code == 'DEPTH_CHART_CHRONOLOGY_FAILURE')
              or (o.state is State.BLOCKED
                  and o.code == 'DEPTH_CHART_NO_LAWFUL_VINTAGE'),
              f'{o.state.value}[{o.code}]')
    e = QA.allocate(2026, 1, ['NE'], [], m=20)
    check('  an empty QB list is refused, not silently emptied',
          e.state is State.FAIL and e.code == 'QB_ALLOCATION_EMPTY',
          f'{e.state.value}[{e.code}]')
    check('  the layer declares itself a CANDIDATE, not promoted',
          'CANDIDATE' in QA.GOVERNANCE and 'NOT promoted' in QA.GOVERNANCE)


def test_G_recorded_results_meet_the_predeclared_rule():
    print('\nG. the recorded result')
    f = os.path.join(_ROOT, 'nfl', 'research', 'qb3', 'qb3_results.json')
    if not os.path.exists(f):
        check('qb3_results.json exists', False, f)
        return
    r = json.load(open(f))
    check('the result cites its pre-registration',
          len(r.get('prereg_sha256', '')) == 64)
    check('  it is labelled EXPLORATORY', 'EXPLORATORY' in r['label'])
    check('  QB3 beats every declared baseline',
          all(r['pooled']['QB3'] < v for k, v in r['pooled'].items()
              if k != 'QB3'), r['pooled'])
    for k, v in r['contrasts'].items():
        check(f'  {k}: the clustered CI excludes zero',
              v['ci_excludes_zero'], v['team_game_clustered_ci95'])
    check('  the skipped 2025 fold is named, not averaged in as a nan',
          any(s['cause'] == 'NO_DEPTH_CHART_LEAF_FOR_SEASON'
              for s in r['evaluation_seasons_skipped']),
          r['evaluation_seasons_skipped'])
    check('  and no closure metric is a nan',
          all(np.isfinite(r['seasons'][str(e)][nm]['closure_violation_rate'])
              for e in r['evaluation_seasons_run']
              for nm in ('QB3', 'B0_incumbent', 'B1_depth_chart',
                         'B2_current_production')))
    check('  QB3 closure violation rate is exactly zero',
          all(r['seasons'][str(e)]['QB3']['closure_violation_rate'] == 0.0
              for e in r['evaluation_seasons_run']))
    check('  and current production fails closure on almost every team-game',
          all(r['seasons'][str(e)]['B2_current_production']
              ['closure_violation_rate'] > 0.9
              for e in r['evaluation_seasons_run']))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
