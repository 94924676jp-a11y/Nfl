"""NFL-V1-R2: research-to-production equivalence for the productionized layers.

EQUIVALENCE BY CONSTRUCTION. `team_volume_v1` imports p4b_volume and calls its
`attach`, `baselines`, `build_forms` and `draw`. There is no second copy of the
mathematics, so these tests check the property that actually matters: that the
production layer reads the FROZEN research selections rather than re-choosing
them, and that its chronology and determinism hold.
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import numpy as np                                                # noqa: E402
from sportsplatform.governance.outcome import State               # noqa: E402
from nfl.production import team_volume_v1 as TV                   # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


TEAMS = ['NE', 'SEA', 'DAL', 'PHI']


def test_A_production_calls_the_research_code():
    print('\nA. the production layer is not a reimplementation')
    import p4b_volume as V
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'team_volume_v1.py')).read()
    check('it imports the research module', 'import p4b_volume as V' in src)
    for fn in ('V.attach', 'V.baselines', 'V.build_forms', 'V.draw'):
        check(f'  it calls {fn}', fn in src)
    check('  and defines no ewma/baseline mathematics of its own',
          'def ewma' not in src and 'def baselines' not in src)
    check('  the research functions it calls exist',
          all(hasattr(V, f) for f in ('attach', 'baselines', 'build_forms',
                                      'draw')))


def test_B_selections_are_read_not_rechosen():
    print('\nB. estimator and form are READ from the frozen research output')
    res = json.loads(TV.RESULTS.read_text())
    for metric in TV.METRICS:
        sel = TV.selected(metric, 2026)
        want = res[metric]['2025']['point_estimator']
        check(f'  {metric}: estimator {sel["estimator"]} matches the frozen '
              f'2025 selection', sel['estimator'] == want,
              f'{sel["estimator"]} vs {want}')
        check(f'    and it was selected on a season strictly earlier than the '
              f'forecast season', sel['selected_on_season'] < 2026)
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'team_volume_v1.py')).read()
    check('  production never minimises a score to pick an estimator',
          'min(' not in src.split('def selected')[1].split('def ')[0])


def test_C_chronology():
    print('\nC. chronology')
    o = TV.forecast(2026, 1, TEAMS, m=20)
    check('a genuinely future week is allowed', o.state is State.PASS, o.code)
    panel = TV._panel()
    check('  and the panel really does stop before it, so this is not vacuous',
          max(r['ord'] for r in panel) < 202601,
          max(r['ord'] for r in panel))
    ords = sorted({r['ord'] for r in panel})
    seen = ords[-1]
    o2 = TV.forecast(seen // 100, seen % 100, TEAMS, m=20)
    check('  a week the panel already contains is REFUSED',
          o2.state is State.FAIL
          and o2.code == 'TEAM_VOLUME_HISTORY_NOT_STRICTLY_EARLIER', o2.code)


def test_D_determinism_and_stochasticity():
    print('\nD. same seed identical, different seed different')
    a = TV.forecast(2026, 1, TEAMS, m=30, seed=1)
    b = TV.forecast(2026, 1, TEAMS, m=30, seed=1)
    c = TV.forecast(2026, 1, TEAMS, m=30, seed=2)
    check('same seed -> identical draws',
          all(np.array_equal(a.value[k], b.value[k]) for k in a.value))
    check('different seed -> different draws',
          any(not np.array_equal(a.value[k], c.value[k]) for k in a.value))


def test_E_coach_is_a_required_model_input():
    print('\nE. coach_prior is load-bearing, so a missing coach is a refusal')
    sel = {m: TV.selected(m, 2026)['estimator'] for m in TV.METRICS}
    n = sum(1 for v in sel.values() if v == 'coach_prior')
    check(f'{n} of {len(TV.METRICS)} metrics select coach_prior', n >= 3,
          str(sel))
    o = TV.forecast(2026, 1, ['NOT_A_TEAM'], m=10)
    check('  a team with no resolvable coach REFUSES rather than guessing',
          o.state is not State.PASS and o.code == 'NO_COACH_FOR_SLATE', o.code)
    co = TV.coaches(2026, 1)
    check('  and the real slate resolves a coach for every team',
          co.state is State.PASS and co.evidence['n_teams'] >= 32,
          co.evidence.get('n_teams') if co.state is State.PASS else co.code)


def test_F_draws_are_physically_possible():
    print('\nF. accounting: volumes are non-negative and coherent')
    o = TV.forecast(2026, 1, TEAMS, m=60)
    check('the layer produced draws', o.state is State.PASS, o.code)
    neg = sum(int((v < 0).sum()) for v in o.value.values())
    check('  no negative volume draw', neg == 0, neg)
    for t in TEAMS:
        db = o.value[('team_dropbacks_part', t)]
        sn = o.value[('team_off_snaps', t)]
        check(f'  {t}: mean dropbacks {db.mean():.1f} < mean snaps '
              f'{sn.mean():.1f}', db.mean() < sn.mean())
    check('  and the near-unforecastability limitation travels with the run',
          'team_volume_is_near_unforecastable' in TV.KNOWN_LIMITATIONS)


def test_G_the_blocked_layers_are_declared_not_faked():
    print('\nG. the layers that could not be productionized say so')
    from nfl.production import run_forecast as RUN
    src = open(RUN.__file__).read()
    check('an unimplemented layer returns STAGE_DECLARED_UNIMPLEMENTED',
          'STAGE_DECLARED_UNIMPLEMENTED' in src)
    check('  and no appearance/participation model was invented here',
          'def appearance' not in open(os.path.join(
              _ROOT, 'nfl', 'production', 'team_volume_v1.py')).read())


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
