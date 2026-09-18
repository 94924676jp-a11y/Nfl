"""The postgame graders: they refuse without a result, and they run with one.

WHY A SYNTHETIC OUTCOME IS USED HERE AND NOWHERE ELSE. On 2026-09-18 the real
DET @ BUF result could not be captured -- nflverse still carried week 1 and
every official host refused CONNECT. Without a fixture the three graders would
sit in the tree untested until the day they are first needed, which is the day
a bug in them is most expensive.

The fixture is tagged TEST_FIXTURE_ONLY and NOT_PROSPECTIVE_EVIDENCE, it is
written to a temporary directory, and `test_E` proves the gate refuses it if
it is ever moved to the real artifact path. NOTHING measured here is a result
about this game, and no number produced from it may be quoted, graded or
carried into the evaluation ledger.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import outcome as OC                              # noqa: E402
from nfl.postgame import grade_projections as GP                    # noqa: E402
from nfl.postgame import grade_props as GR                          # noqa: E402
from nfl.postgame import grade_portfolios as GF                     # noqa: E402
from nfl.postgame import ledger as LG                               # noqa: E402
from nfl.postgame import eligibility as EL                          # noqa: E402
from sportsplatform.governance.outcome import State                 # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

FIX = _REPO/'nfl/research/dfs/DET_BUF_2026W2'

#: TEST FIXTURE. Invented numbers, chosen to exercise every branch -- an over,
#: an under, a zero, a player in the board and absent from the outcome. They
#: are not a forecast, not a result, and not evidence of anything.
TEST_FIXTURE_ONLY = True
NOT_PROSPECTIVE_EVIDENCE = True

_LINE = dict(pass_att=0, pass_cmp=0, pass_yards=0, pass_td=0, interceptions=0,
             rush_att=0, rush_yards=0, rush_td=0,
             targets=0, receptions=0, rec_yards=0, rec_td=0)

_FIXTURE_PLAYERS = {
    'Jared Goff': dict(_LINE, team='DET', position='QB', pass_att=40,
                       pass_cmp=27, pass_yards=284, pass_td=2,
                       interceptions=1, rush_att=2, rush_yards=3),
    'Josh Allen': dict(_LINE, team='BUF', position='QB', pass_att=29,
                       pass_cmp=19, pass_yards=241, pass_td=3,
                       interceptions=0, rush_att=8, rush_yards=44, rush_td=1),
    'Jahmyr Gibbs': dict(_LINE, team='DET', position='RB', rush_att=21,
                         rush_yards=103, rush_td=1, targets=5, receptions=4,
                         rec_yards=28),
    'James Cook': dict(_LINE, team='BUF', position='RB', rush_att=19,
                       rush_yards=88, rush_td=1, targets=3, receptions=2,
                       rec_yards=14),
    'Ray Davis': dict(_LINE, team='BUF', position='RB', rush_att=4,
                      rush_yards=7, targets=1, receptions=1, rec_yards=5),
    'Amon-Ra St. Brown': dict(_LINE, team='DET', position='WR', targets=11,
                              receptions=8, rec_yards=94, rec_td=1),
    'Jameson Williams': dict(_LINE, team='DET', position='WR', targets=6,
                             receptions=3, rec_yards=51),
    'Sam LaPorta': dict(_LINE, team='DET', position='TE', targets=7,
                        receptions=5, rec_yards=44),
    'Isaac TeSlaa': dict(_LINE, team='DET', position='WR', targets=2,
                         receptions=1, rec_yards=9),
    'Brock Wright': dict(_LINE, team='DET', position='TE', targets=2,
                         receptions=1, rec_yards=6),
    'Sione Vaki': dict(_LINE, team='DET', position='RB', rush_att=2,
                       rush_yards=3),
    'Khalil Shakir': dict(_LINE, team='BUF', position='WR', targets=8,
                          receptions=6, rec_yards=61),
    'Dalton Kincaid': dict(_LINE, team='BUF', position='TE', targets=6,
                           receptions=4, rec_yards=47, rec_td=1),
    'Keon Coleman': dict(_LINE, team='BUF', position='WR', targets=4,
                         receptions=2, rec_yards=33),
    'Dawson Knox': dict(_LINE, team='BUF', position='TE', targets=2,
                        receptions=1, rec_yards=11),
    'DJ Moore': dict(_LINE, team='BUF', position='WR', targets=3,
                     receptions=1, rec_yards=12),
}


def _write_fixture(d: pathlib.Path) -> pathlib.Path:
    p = d/'OUTCOME_FIXTURE.json'
    p.write_text(json.dumps({
        'TEST_FIXTURE_ONLY': True,
        'NOT_PROSPECTIVE_EVIDENCE': True,
        'game_id': OC.GAME_ID,
        'source': 'SYNTHETIC TEST FIXTURE -- not a source',
        'retrieved_at_utc': '2026-09-18T00:00:00Z',
        'source_sha256': '0'*64,
        'final_score': {'DET': 31, 'BUF': 41},
        'players': _FIXTURE_PLAYERS}, indent=1, sort_keys=True))
    return p


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def test_A_no_outcome_is_a_refusal_not_a_zero():
    """Every grader stops at the gate. None of them grades against nothing."""
    missing = FIX/'POSTGAME_OUTCOME'/'DOES_NOT_EXIST.json'
    for label, fn in (('outcome.require', OC.require),
                      ('grade_projections', GP.grade),
                      ('grade_props', GR.grade),
                      ('grade_portfolios', GF.grade)):
        o = fn(missing)
        check(f'A {label} blocks without a verified outcome',
              o.state is State.BLOCKED
              and o.code == OC.CODE_MISSING, f'{o.state}[{o.code}]')


def test_B_projections_grade_every_stat_separately():
    with tempfile.TemporaryDirectory() as d:
        p = _write_fixture(pathlib.Path(d))
        o = GP.grade(p)
        check('B projections grade', o.state is State.PASS,
              f'{o.state}[{o.code}] {o.detail}')
        if o.state is not State.PASS:
            return
        rows = o.value['rows']
        check('B every graded player carries per-stat rows, not one MAE',
              rows and all(len(r['stats']) >= len(GP.MAP) for r in rows),
              str(len(rows)))
        one = next(r for r in rows if r['player'] == 'Jared Goff')
        py = one['stats']['pass_yards']
        check('B the actual is carried and placed in the distribution',
              py['actual'] == 284 and py['bucket'] in OC.BUCKETS
              and 0.0 <= py['percentile_of_actual'] <= 1.0, str(py))
        # DK and FD differ in exactly one scored quantity, the reception, so
        # the gap must show on a receiver and must be exactly 0.5 a catch.
        wr = next(r for r in rows if r['player'] == 'Amon-Ra St. Brown')
        check('B both sites are scored from the same stat line, and differ '
              'only by half a point per reception',
              abs((wr['stats']['dk_points']['actual']
                   - wr['stats']['fd_points']['actual']) - 0.5*8) < 1e-9,
              str((wr['stats']['dk_points']['actual'],
                   wr['stats']['fd_points']['actual'])))
        check('B a quarterback with no catches scores the same at both sites',
              abs(one['stats']['dk_points']['actual']
                  - one['stats']['fd_points']['actual']) < 1e-9,
              str((one['stats']['dk_points']['actual'],
                   one['stats']['fd_points']['actual'])))
        check('B nominal shares are carried but not scored against',
              o.evidence['nominal_shares'] == OC.NOMINAL
              and 'descriptive'
              in o.evidence['one_game_cannot_estimate_calibration'],
              o.evidence.get('one_game_cannot_estimate_calibration', '')[:80])


def test_C_props_grade_settles_and_refuses_the_rest():
    with tempfile.TemporaryDirectory() as d:
        p = _write_fixture(pathlib.Path(d))
        o = GR.grade(p)
        check('C props grade', o.state is State.PASS,
              f'{o.state}[{o.code}] {o.detail}')
        if o.state is not State.PASS:
            return
        g = o.value['graded']
        check('C only supported lines are graded',
              g and all(r['support_status'] == GR.SUPPORTED for r in g),
              str(len(g)))
        check('C unsupported lines are listed with a reason, not dropped',
              o.value['not_graded']
              and all(r['reason'] for r in o.value['not_graded']),
              str(len(o.value['not_graded'])))
        # Goff 284 passing yards against the 260.5 line settles OVER.
        row = next(r for r in g if r['player'] == 'Jared Goff'
                   and r['market'] == 'Player Passing Yards')
        check('C settlement reads the actual against the line',
              row['settled'] == 'OVER' and row['actual'] == 284.0
              and row['model_correct'] is False, str(row))
        # Cook 88 + 14 = 102 against 102.5 settles UNDER.
        comb = next(r for r in g if r['player'] == 'James Cook'
                    and r['market'] == 'Player Rushing + Receiving Yards')
        check('C a combined market sums its components',
              comb['actual'] == 102.0 and comb['settled'] == 'UNDER',
              str(comb))
        check('C a naive standard error is refused',
              o.evidence['standard_error'].startswith('REFUSED')
              and o.value['overall_model_side']['n_player_clusters']
              < o.value['overall_model_side']['n'],
              str(o.value['overall_model_side']))
        check('C the role-state split is reported',
              'ROLE_STATE_CONCERN' in o.value['by_confidence_tag'],
              str(sorted(o.value['by_confidence_tag'])))


def test_D_the_card_is_graded_without_being_called_a_card():
    with tempfile.TemporaryDirectory() as d:
        p = _write_fixture(pathlib.Path(d))
        o = GR.grade(p)
        if o.state is not State.PASS:
            NOT_EXECUTED.append('D card grading (props grade did not pass)')
            return
        c = o.value['card_as_ordered']
        check('D ten rows, ordered by disagreement with the market',
              len(c['rows']) == GR.CARD_N
              and all(abs(c['rows'][i]['model_minus_market'])
                      >= abs(c['rows'][i+1]['model_minus_market'])
                      for i in range(len(c['rows'])-1)), str(len(c['rows'])))
        check('D ROI and closing-line value are NOT_AVAILABLE, not zero',
              c['roi'] == 'NOT_AVAILABLE_NO_STAKED_PLAYS'
              and c['closing_line_value'] == 'NOT_AVAILABLE_NO_CLOSING_VINTAGE',
              str((c['roi'], c['closing_line_value'])))
        check('D it says plainly that nothing was staked',
              'NOT a staked card' in c['what_it_is'])


def test_E_a_fixture_may_not_sit_at_the_real_artifact_path():
    """The one thing that turns a test fixture into a quoted result."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_fixture(pathlib.Path(d))
        body = json.loads(p.read_text())
        check('E the fixture declares itself',
              body['TEST_FIXTURE_ONLY'] is True
              and body['NOT_PROSPECTIVE_EVIDENCE'] is True)
        real = OC.ARTIFACT
        if real.exists():
            NOT_EXECUTED.append('E fixture-at-real-path (a real outcome '
                                'artifact exists and must not be disturbed)')
            return
        real.parent.mkdir(parents=True, exist_ok=True)
        try:
            real.write_text(p.read_text())
            o = OC.require()
            check('E the gate refuses a fixture at the production path',
                  o.state is State.FAIL
                  and o.code == 'TEST_FIXTURE_AT_PRODUCTION_PATH',
                  f'{o.state}[{o.code}]')
        finally:
            real.unlink(missing_ok=True)


def test_F_portfolios_grade_against_the_actual_optimal():
    with tempfile.TemporaryDirectory() as d:
        p = _write_fixture(pathlib.Path(d))
        o = GF.grade(p)
        check('F portfolios grade', o.state is State.PASS,
              f'{o.state}[{o.code}] {o.detail}')
        if o.state is not State.PASS:
            NOT_EXECUTED.append('F portfolio assertions')
            return
        ps = o.value['portfolios']
        check('F both portfolios are measured, not just ours',
              set(ps) == set(GF.PORTFOLIOS), str(sorted(ps)))
        check('F regret is measured against an exactly solved optimal',
              all(r.get('regret_vs_optimal') is not None
                  for r in ps.values()),
              str({k: v.get('regret_vs_optimal') for k, v in ps.items()}))
        check('F one slate is not allowed to rank the two architectures',
              'one_slate_cannot_rank_architectures' in o.evidence)


def test_G_the_frozen_pregame_set_is_untouched():
    o = OC.assert_pregame_untouched()
    check('G the pregame frozen set is intact', o.state is State.PASS,
          f'{o.state}[{o.code}] {o.detail}')


def test_H_the_ledger_is_append_only_and_registration_comes_first():
    with tempfile.TemporaryDirectory() as d:
        L = pathlib.Path(d)/'LEDGER.jsonl'
        early = LG.grade_block(block_id='X', outcome={'a': 1},
                               grades={'b': 2}, path=L)
        check('H a grade before a registration is refused',
              early.state is State.FAIL
              and early.code == 'LEDGER_GRADE_WITHOUT_REGISTRATION',
              f'{early.state}[{early.code}]')
        r = LG.register(block_id='X', game_id='G', forecast_identity='F',
                        sealed_inputs={'s': 1}, scope={'n': 1}, path=L)
        check('H registration appends', r.state is State.PASS,
              f'{r.state}[{r.code}]')
        again = LG.register(block_id='X', game_id='G', forecast_identity='F',
                            sealed_inputs={'s': 1}, scope={'n': 1}, path=L)
        check('H a scope cannot be re-registered after the fact',
              again.state is State.FAIL
              and again.code == 'LEDGER_BLOCK_ALREADY_REGISTERED',
              f'{again.state}[{again.code}]')
        before = L.read_text()
        g = LG.grade_block(block_id='X', outcome={'a': 1}, grades={'b': 2},
                           path=L)
        check('H grading appends after registration', g.state is State.PASS,
              f'{g.state}[{g.code}]')
        check('H nothing already on disk was rewritten',
              L.read_text().startswith(before))
        twice = LG.grade_block(block_id='X', outcome={'a': 1},
                               grades={'b': 2}, path=L)
        check('H a graded block cannot be graded again',
              twice.state is State.FAIL
              and twice.code == 'LEDGER_BLOCK_ALREADY_GRADED',
              f'{twice.state}[{twice.code}]')
        a = LG.audit(L)
        check('H the audit is clean and counts the blocks',
              a.state is State.PASS and a.evidence['n_blocks'] == 2,
              f'{a.state}[{a.code}] {a.evidence.get("n_blocks")}')


def test_I_the_real_det_buf_block_is_registered_and_still_awaiting():
    a = LG.audit()
    check('I the live ledger audits clean', a.state is State.PASS,
          f'{a.state}[{a.code}] {a.detail}')
    if a.state is not State.PASS:
        return
    check('I DET_BUF_2026W2 is registered before its outcome',
          'DET_BUF_2026W2' in a.evidence['awaiting'],
          str(a.evidence['awaiting']))
    blk = next(r for r in a.value if r['block_id'] == 'DET_BUF_2026W2')
    check('I the registration carries no result',
          blk['outcome'] is None and blk['grades'] is None
          and blk['scope']['declared_before_outcome'] is True, str(blk['status']))


def test_J_a_sealed_board_can_never_become_training_data():
    frozen = 'nfl/research/dfs/DET_BUF_2026W2/frozen/sealed_player_draws.npz'
    o = EL.assert_may_train(frozen)
    check('J the sealed board is refused as a training input',
          o.state is State.FAIL and o.code == EL.FROZEN_REFUSED,
          f'{o.state}[{o.code}]')
    mkt = 'nfl/research/market/DET_BUF_2026W2/MAIN_LINE_BOARD.csv'
    o = EL.assert_may_train(mkt)
    check('J market data may only evaluate',
          o.state is State.FAIL and o.code == EL.MARKET_REFUSED,
          f'{o.state}[{o.code}]')
    out = ('nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME/OUTCOME.json')
    same = EL.assert_may_train(out, evaluation_games=('2026_02_DET_BUF',))
    later = EL.assert_may_train(out, evaluation_games=('2026_03_ANY_GAME',))
    check('J the same outcome is embargoed for its own game and eligible '
          'for a later one',
          same.state is State.FAIL and same.code == EL.EMBARGOED
          and later.state is State.PASS,
          f'{same.code} / {later.code}')
    o = EL.assert_may_train('nfl/research/not_registered_anywhere.csv')
    check('J an unclassified artifact is refused, not defaulted to eligible',
          o.state is State.FAIL and o.code == EL.UNCLASSIFIED,
          f'{o.state}[{o.code}]')
    # A registry entry pointing at nothing is a typo that would silently
    # stop protecting the file it names.
    absent = [k for k, v in EL.REGISTRY.items()
              if v != EL.POSTGAME_TRAINING_ELIGIBLE
              and not (_REPO/k).exists()]
    check('J every classified artifact except the awaited outcome exists',
          not absent, str(absent))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_no_outcome_is_a_refusal_not_a_zero,
               test_B_projections_grade_every_stat_separately,
               test_C_props_grade_settles_and_refuses_the_rest,
               test_D_the_card_is_graded_without_being_called_a_card,
               test_E_a_fixture_may_not_sit_at_the_real_artifact_path,
               test_F_portfolios_grade_against_the_actual_optimal,
               test_G_the_frozen_pregame_set_is_untouched,
               test_H_the_ledger_is_append_only_and_registration_comes_first,
               test_I_the_real_det_buf_block_is_registered_and_still_awaiting,
               test_J_a_sealed_board_can_never_become_training_data):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
