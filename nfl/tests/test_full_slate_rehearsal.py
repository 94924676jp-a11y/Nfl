"""NFL-V1-R1 regression tests: one per structural defect the rehearsal found.

Each of these passed silently before. That is the point -- every one of them is
a way the production path reported success while doing less than it claimed.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'qb2'),
           os.path.join(_ROOT, 'nfl', 'research', 'rc1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.production import run_forecast as RUN                   # noqa: E402
from nfl.production import qb_v1 as QBV1                         # noqa: E402
from nfl.production import refusal as RF                         # noqa: E402
from nfl.production.rehearsal import run_slate as SL             # noqa: E402

PASSED = FAILED = 0
TMP = pathlib.Path(tempfile.mkdtemp())


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _args(**o):
    d = dict(season=2026, week=1, game_id='2026_01_NE_SEA', arm='A',
             written_at='2026-09-08T23:00:00Z', out_dir=str(TMP),
             seed=20260908, dry_run=True, fixtures=None)
    d.update(o)
    return argparse.Namespace(**d)


def _fx(**o):
    _, rows = SL.roster(2026, 1)
    players = [{'gsis_id': r['gsis_id'], 'position': r['position'],
                'team': r['team']} for r in rows if r['team'] in ('NE', 'SEA')]
    f = {'kickoff_utc': '2026-09-10T00:20:00Z',
         'source_hashes': {'schedules': {'sha256': 'b' * 64,
                                         'retrieved_at':
                                             '2026-09-08T12:00:00Z'}},
         'players': players, 'team_ids': ['NE', 'SEA'],
         'qb_slate': {'prospective': True}, 'qb_draws': 40,
         'distributions': {}}
    f.update(o)
    return f


# ==========================================================================
def test_A_empty_artifact_is_refused():
    print('\nA. an artifact carrying no forecasts must not seal')
    check('EMPTY_FORECAST_ARTIFACT is a declared refusal code',
          'EMPTY_FORECAST_ARTIFACT' in RF.REFUSALS)
    s = RUN.build(_args(), _fx(qb_slate={}, players=[{'gsis_id': '00-0000001',
                                                      'position': 'WR',
                                                      'team': 'NE'}]))
    check('a run where no layer produced a distribution REFUSES',
          s['status'] == 'REFUSED', s['status'])
    check('  with EMPTY_FORECAST_ARTIFACT, not a generic failure',
          any(r['code'] == 'EMPTY_FORECAST_ARTIFACT' for r in s['refusals']),
          s['refusals'])


def test_B_a_stage_cannot_claim_a_spec_and_produce_nothing():
    """A layer must declare WHY it produced nothing, and the two reasons are
    different facts.

    This originally required STAGE_DECLARED_UNIMPLEMENTED for the whole non-QB
    chain. That label was false: those five layers ARE implemented and are
    blocked on a captured input, and reporting them as never-built lost the
    real cause -- `slate_rehearsal` calling the same layers got
    DEFERRED[INJURY_REPORT_NOT_YET_FILED] while the production entrypoint said
    "no production implementation" and recorded PASS.

    The check now distinguishes the two, which is the property that matters:
    an unimplemented stage says so, and an implemented-but-blocked stage names
    its blocker instead of borrowing the unimplemented label.
    """
    print('\nB. a layer that produced nothing declares WHY, and truthfully')
    s = RUN.build(_args(), _fx())
    codes = {r['stage']: r['code'] for r in s['stages']}
    states = {r['stage']: r['state'] for r in s['stages']}

    check('  team_environment -> STAGE_DECLARED_UNIMPLEMENTED',
          codes.get('team_environment') == 'STAGE_DECLARED_UNIMPLEMENTED',
          codes.get('team_environment'))

    # The implemented chain must name a real blocker, never the debt label.
    for stage in ('appearance', 'participation', 'targets_carries',
                  'conversion', 'td_layer'):
        c = codes.get(stage)
        check(f'  {stage} names its own blocker, not the debt label',
              c not in (None, 'STAGE_DECLARED_UNIMPLEMENTED')
              and ('BLOCKED' in c or 'INJURY' in c or 'NOT_YET' in c
                   or 'INCOMPLETE' in c),
              c)
        check(f'  {stage} does not report PASS while producing nothing',
              states.get(stage) != 'PASS', states.get(stage))

    check('  and the QB layer, which IS implemented, still reports OK',
          codes.get('qb_layer') == 'QB_LAYER_OK', codes.get('qb_layer'))


def test_C_completeness_is_computed_not_asserted():
    print('\nC. the artifact reports partial coverage truthfully')
    import json
    s = RUN.build(_args(), _fx())
    check('the run seals', s['status'] == 'SEALED', s['status'])
    art = json.load(open(TMP / s['run_id'] / 'forecast_artifact.json'))
    check('  completeness is PARTIAL_PLAYER_COVERAGE, not COMPLETE',
          art['completeness'] == 'PARTIAL_PLAYER_COVERAGE',
          art['completeness'])
    check('  and the absent layers are NAMED in the artifact',
          len(art['absent_layers']) >= 5, art['absent_layers'])
    check('  the artifact carries real distributions for what did run',
          len(art['distributions']) > 0, len(art['distributions']))
    check('  publication is still refused',
          s['publication']['code'] == 'NFL1_NOT_AUTHORIZED')


def test_D_prospective_slate_refuses_a_seen_week():
    print('\nD. the QB layer will not forecast a week its history contains')
    o = QBV1.slate_prospective(2024, 1, [{'gsis_id': '00-0033077',
                                          'team': 'DAL'}])
    check('forecasting 2024 wk1 from a frame containing 2024 REFUSES',
          o.state is State.FAIL
          and o.code == 'QB_HISTORY_NOT_STRICTLY_EARLIER', o.code)
    o2 = QBV1.slate_prospective(2026, 1, [{'gsis_id': '00-0033077',
                                           'team': 'DAL'}])
    check('  while a genuinely future week is allowed',
          o2.state is State.PASS, o2.code)
    check('  and a QB with no prior appearance is NAMED, not dropped',
          'no_history' in o2.evidence)


def test_E_unidentified_players_are_excluded_and_named():
    print('\nE. one unidentifiable player does not block a whole game')
    good = [{'gsis_id': f'00-000{i:04d}', 'position': 'WR', 'team': 'NE'}
            for i in range(200)]
    s = RUN.build(_args(), _fx(players=good + [{'gsis_id': '', 'position': 'RB',
                                                'team': 'NYJ'}],
                               qb_slate={}))
    ident = [r for r in s['stages'] if r['stage'] == 'identity_resolution'][0]
    check('identity resolution PASSES with one unidentified of 201',
          ident['state'] == 'PASS', ident['code'])
    check('  and the exclusion is a warning, not silence',
          any('excluded' in w for w in (ident.get('warnings') or [])),
          ident.get('warnings'))
    many = good[:50] + [{'gsis_id': '', 'position': 'RB', 'team': 'NYJ'}
                        for _ in range(10)]
    s2 = RUN.build(_args(), _fx(players=many, qb_slate={}))
    check('  but 10 of 60 unidentified REFUSES -- a broken feed, not an '
          'incomplete one',
          any(r['code'] == 'IDENTITY_UNRESOLVED' for r in s2['refusals']),
          s2['refusals'])


def test_F_full_slate_runs():
    print('\nF. the whole slate runs through the production entrypoint')
    r = SL.build(2026, 1, str(TMP / 'slate'), '2026-09-08T23:00:00Z')
    check('16 games resolved', r['n_games'] == 16, r.get('n_games'))
    sealed = [g for g in r['results'] if g['status'] == 'SEALED']
    check('  every game seals', len(sealed) == 16,
          [g['status'] for g in r['results']])
    check('  every game refuses publication',
          all(g['publication'] == 'NFL1_NOT_AUTHORIZED' for g in r['results']))
    check('  and no game reports an unnamed failure',
          all(not g['failures'] for g in r['results']),
          [g['failures'] for g in r['results'] if g['failures']][:1])


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
