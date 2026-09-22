"""The slate board: every number priced, graded, and every move explained.

The board is the governing internal product. These cases pin the three rules
it must not bend: a missing value is never a zero, every material move has a
named cause, and the board never invents a number the model did not emit.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.board import player_board as PB
from nfl.production.state import availability as AV                 # noqa: E402
from nfl.production.review import dossier as DOS                    # noqa: E402
from nfl.production.review import evidence as EV                    # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T23:05:00Z'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def row(pid, **kw):
    r = dict(game_id='G', season=2026, week=2, team='NYG', opponent='LA',
             gsis_id=pid, display_name=pid, roster_position='RB',
             roster_status='ACT', officially_inactive=False,
             support_state='MODEL_SUPPORTED', information_cut=CUT,
             offensive_depth_rank=1, offensive_depth_state='x',
             special_teams_role=None, pfr_id=None,
             injury_report_status=None, injury_practice_status=None)
    r.update(kw)
    return r


def dossiers(ids, **kw):
    return DOS.build_dossiers(universe_rows=[row(p) for p in ids],
                              information_cut=CUT, **kw).value['dossiers']


def draws(per, n=64, seed=7):
    rng = np.random.default_rng(seed)
    ids = list(per)
    arrays, layers = {}, {}
    for key, col in (('dk_scoring/dk_points', 'dk_points'),
                     ('rushing/carries', 'carries'),
                     ('receiving/targets', 'targets')):
        layer = key.split('/')[0]
        M = np.stack([np.maximum(0.0, rng.normal(per[p].get(col, 0.0), 0.4, n))
                      for p in ids])
        arrays[key] = M
        layers.setdefault(layer, {'row_ids': ids})
    return arrays, layers


def build(ids, per, **kw):
    a, l = draws(per)
    return PB.build(slate_key='S', dossiers=dossiers(ids), arrays=a,
                    layers=l, information_cut=CUT, **kw)


# -- 1. a missing value is never a zero -------------------------------------
def test_a_player_with_no_projection_reads_NOT_EMITTED():
    o = build(['A', 'B'], {'A': {'dk_points': 12.0}})
    r = {x['gsis_id']: x for x in o.value['rows']}
    ok(r['B']['dk_mean'] == PB.NOT_EMITTED,
       f'a player the model skipped reads {PB.NOT_EMITTED}, not 0.0')
    ok(isinstance(r['A']['dk_mean'], float),
       'while a projected player carries a number')


def test_no_salary_reads_UNAVAILABLE_and_has_no_value():
    o = build(['A'], {'A': {'dk_points': 12.0}})
    r = o.value['rows'][0]
    ok(r['salary'] == PB.SALARY_UNAVAILABLE,
       f'an unpriced player reads {PB.SALARY_UNAVAILABLE}, not $0')
    ok(r['value_per_1k'] is None,
       'and has no value, rather than a value computed against zero')
    o2 = build(['A'], {'A': {'dk_points': 12.0}}, salaries={'A': 6000.0})
    r2 = o2.value['rows'][0]
    # Against the row's OWN dk_mean, not a literal: the draws are sampled,
    # so the mean is near 12.0 and not exactly it. Asserting 2.0 would be
    # asserting the sampler, not the arithmetic.
    ok(abs(r2['value_per_1k'] - r2['dk_mean'] / 6.0) < 5e-5,
       f'priced, the value is DK per $1k: {r2["value_per_1k"]:.4f} from '
       f'{r2["dk_mean"]:.4f} at $6,000')


def test_a_player_with_no_current_season_evidence_reads_COLD_START():
    o = build(['A'], {'A': {'dk_points': 5.0}})
    ok(o.value['rows'][0]['current_season_avg'] == EV.COLD_START,
       'no measured current-season game reads COLD_START, not 0.0')


# -- 2. every material move has a named cause -------------------------------
def test_an_immaterial_move_is_not_attributed():
    a = build(['A'], {'A': {'dk_points': 10.0}})
    prev = {r['gsis_id']: r for r in a.value['rows']}
    b = build(['A'], {'A': {'dk_points': 10.0}}, previous_board=prev)
    ok(b.value['rows'][0]['change_cause'] is None,
       'a move below the declared material threshold gets no cause, rather '
       'than a manufactured one')


def test_a_model_change_is_named_as_one():
    a = build(['A'], {'A': {'dk_points': 10.0}})
    prev = {r['gsis_id']: r for r in a.value['rows']}
    b = build(['A'], {'A': {'dk_points': 18.0}}, previous_board=prev,
              run_identity='MODE_B', previous_run_identity='MODE_A')
    r = b.value['rows'][0]
    ok(r['change_cause'] == 'MODEL_UPDATE',
       f'the engine changing is itself a cause: {r["change_cause"]}')
    ok('MODE_A -> MODE_B' in str(r['change_evidence']),
       f'naming both identities: {r["change_evidence"]}')


def test_an_unexplained_move_says_so_rather_than_bucketing_it():
    a = build(['A'], {'A': {'dk_points': 10.0}})
    prev = {r['gsis_id']: r for r in a.value['rows']}
    b = build(['A'], {'A': {'dk_points': 18.0}}, previous_board=prev)
    r = b.value['rows'][0]
    ok(r['change_cause'] == 'UNEXPLAINED',
       'with no model change and nothing on the row moving, the cause is '
       'UNEXPLAINED')
    ok('finding' in str(r['change_evidence']),
       'and it is stated as a finding, not as a "model refresh" bucket')
    ok(b.value['n_unexplained_changes'] == 1,
       'and it is counted, so a board full of them cannot look clean')


def test_gaining_or_losing_a_projection_is_a_named_change():
    a = build(['A', 'B'], {'A': {'dk_points': 10.0}})
    prev = {r['gsis_id']: r for r in a.value['rows']}
    b = build(['A', 'B'], {'A': {'dk_points': 10.0}, 'B': {'dk_points': 9.0}},
              previous_board=prev)
    r = {x['gsis_id']: x for x in b.value['rows']}['B']
    ok(r['change_cause'] == 'MODEL_UPDATE',
       f'a player who gained a projection is named, not silently new: '
       f'{r["change_cause"]}')
    ok('emitted no projection for him before' in str(r['change_evidence']),
       f'with the absence described: {r["change_evidence"]}')


# -- 3. the board reads; it does not invent ---------------------------------
def test_a_misaligned_draw_axis_is_refused():
    a, l = draws({'A': {'dk_points': 5.0}})
    l['dk_scoring']['row_ids'] = ['A', 'GHOST']
    o = PB.build(slate_key='S', dossiers=dossiers(['A']), arrays=a, layers=l)
    ok(o.state.name == 'FAIL' and o.code == 'BOARD_DRAW_AXIS_MISALIGNED',
       'a row axis that disagrees with the manifest is refused, not '
       'silently truncated')


def test_an_empty_population_is_refused():
    o = PB.build(slate_key='S', dossiers=[])
    ok(o.state.name == 'BLOCKED' and o.code == 'BOARD_POPULATION_EMPTY',
       'an empty board is never reported as a board')


def test_write_verifies_the_row_count_on_disk():
    o = build(['A', 'B'], {'A': {'dk_points': 9.0}, 'B': {'dk_points': 4.0}})
    with tempfile.TemporaryDirectory() as td:
        w = PB.write(o.value, td)
        ok(w.state.name == 'PASS', f'the board writes: {w.code}')
        ok(w.value['n_rows'] == 2,
           'and the CSV row count is re-read from disk, not asserted')
        for f in ('PLAYER_BOARD.json', 'PLAYER_BOARD.csv',
                  'PROJECTION_CHANGE_LOG.json'):
            ok((pathlib.Path(td) / f).exists(), f'{f} exists')


def test_salary_loader_names_what_it_could_not_match():
    p = _REPO / 'nfl/dfs/salaries/DK_WEEK2_SALARY_UNIVERSE.json'
    if not p.exists():
        ok(True, 'salary artifact absent in this checkout; case skipped')
        return
    o = PB.load_salaries(p)
    ok(o.state.name == 'PASS' and o.value['n_matched'] > 400,
       f'{o.value["n_matched"]} salary row(s) resolved to a gsis_id')
    ok('n_unmatched_identity' in o.value,
       f'and the {o.value["n_unmatched_identity"]} it could not match are '
       f'counted and named, not dropped silently')


def test_missing_salary_artifact_refuses_rather_than_pricing_at_zero():
    o = PB.load_salaries('/nonexistent/salaries.json')
    ok(o.state.name == 'BLOCKED' and o.code == 'SALARY_ARTIFACT_ABSENT',
       'no artifact means no prices, by name')


def test_not_on_inactive_list_can_never_mean_a_teammate_went_out():
    """A SUBSTRING test used to decide this, and 'NOT_ON_INACTIVE_LIST'
    contains 'INACTIVE'. A player whose availability moved from UNKNOWN to
    NOT_ON_INACTIVE_LIST -- a change that asserts nothing about whether
    anybody plays -- would have had his projection movement attributed to a
    teammate going out."""
    def cause(av, pav):
        row = {'dk_mean': 10.0, 'availability': av}
        prev = {'dk_mean': 5.0, 'availability': pav}
        return PB._cause(row, prev, None)['cause']

    for pav in (AV.UNKNOWN, AV.NOT_ON_INACTIVE_LIST, 'ACTIVE',
                AV.INJURY_QUESTIONABLE, AV.OFFICIAL_INACTIVE, 'INACTIVE'):
        if pav == AV.NOT_ON_INACTIVE_LIST:
            continue
        c = cause(AV.NOT_ON_INACTIVE_LIST, pav)
        ok(c != 'TEAMMATE_INACTIVE',
           f'{pav} -> NOT_ON_INACTIVE_LIST is attributed to {c}, never '
           f'TEAMMATE_INACTIVE')
    ok('INACTIVE' in AV.NOT_ON_INACTIVE_LIST,
       'and the trap is real: the string NOT_ON_INACTIVE_LIST does contain '
       'INACTIVE, which is why membership replaced containment')


def test_every_availability_state_has_a_declared_cause():
    for st in AV.STATES:
        if st == AV.GAME_ACTIVE:
            continue          # never produced; see state/availability.py
        ok(st in PB.AVAILABILITY_CAUSE,
           f'{st} has a declared cause: {PB.AVAILABILITY_CAUSE.get(st)}')
    ok(PB.AVAILABILITY_CAUSE[AV.INJURY_OUT] == 'TEAMMATE_INACTIVE',
       'a club OUT designation is treated as will-not-play, not as a '
       'practice note')
    ok(PB.AVAILABILITY_CAUSE[AV.INJURY_QUESTIONABLE] == 'PRACTICE_OR_INJURY'
       and PB.AVAILABILITY_CAUSE[AV.INJURY_DOUBTFUL] == 'PRACTICE_OR_INJURY',
       'while a designation of uncertainty is not')
    ok(all(c in PB.CAUSES for c in PB.AVAILABILITY_CAUSE.values()),
       'and every mapped cause is one the board declares')


def test_an_unrecognised_availability_value_is_not_guessed_at():
    row = {'dk_mean': 10.0, 'availability': 'SOMETHING_NOBODY_DECLARED',
           'offensive_depth': 1, 'role': 'X', 'opportunity_basis': 'Y'}
    prev = {'dk_mean': 5.0, 'availability': AV.UNKNOWN,
            'offensive_depth': 1, 'role': 'X', 'opportunity_basis': 'Y'}
    c = PB._cause(row, prev, None)['cause']
    ok(c != 'TEAMMATE_INACTIVE' and c != 'PRACTICE_OR_INJURY',
       f'an undeclared availability value falls through rather than being '
       f'guessed at, and ends as {c}')


def main():
    for t in (test_a_player_with_no_projection_reads_NOT_EMITTED,
              test_no_salary_reads_UNAVAILABLE_and_has_no_value,
              test_a_player_with_no_current_season_evidence_reads_COLD_START,
              test_an_immaterial_move_is_not_attributed,
              test_a_model_change_is_named_as_one,
              test_an_unexplained_move_says_so_rather_than_bucketing_it,
              test_gaining_or_losing_a_projection_is_a_named_change,
              test_a_misaligned_draw_axis_is_refused,
              test_an_empty_population_is_refused,
              test_write_verifies_the_row_count_on_disk,
              test_salary_loader_names_what_it_could_not_match,
              test_missing_salary_artifact_refuses_rather_than_pricing_at_zero,
              test_not_on_inactive_list_can_never_mean_a_teammate_went_out,
              test_every_availability_state_has_a_declared_cause,
              test_an_unrecognised_availability_value_is_not_guessed_at):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
