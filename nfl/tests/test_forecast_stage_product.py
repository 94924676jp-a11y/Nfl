"""The two-stage forecast product: stage vocabulary, QB blockers, PRE->POST delta.

WHAT THIS PROTECTS.

  * A FORECAST EXISTS BEFORE THE OFFICIAL LIST DOES. The comparator used to
    refuse any board that was not post-inactives, so there was no projection at
    all until roughly ninety minutes before kickoff -- even though roster,
    depth chart, injury report, workload history and team environment were all
    known hours earlier. Missing availability is a reason to be uncertain, not
    a reason to be silent.

  * THE THREE QB BLOCKERS ARE NOT INTERCHANGEABLE. Stage, specification and
    enforcement are different claims. If they were pooled, the arrival of an
    inactive list would appear to clear a season-boundary defect that ingesting
    a list cannot possibly repair.

  * STAGE 1 IS NEVER REWRITTEN. Stage 2 is a new artifact beside it. A delta
    computed against a rewritten stage 1 measures nothing, and a restamped
    forecast cannot be scored -- which would destroy the only reason both
    stages are kept: measuring what the official list is actually worth.

  * THE DELTA JOINS ON IDENTITY. A positional join across two boards would pair
    one player's pre distribution with another's post distribution. That defect
    was measured on 2026_01_ARI_LAC and made a team dropback split read
    74.6/4.9 against a true 41.3/38.2.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.product import forecast_stage as FS                         # noqa: E402
from nfl.tools import stage_delta as SD                              # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


OPENER = {'DAL': {'configuration': 'DISAGREE', 'is_season_opener': True,
                  'week1_specification_defect': True},
          'NYG': {'configuration': 'AGREE', 'is_season_opener': True,
                  'week1_specification_defect': True}}
MIDSEASON = {'DAL': {'configuration': 'AGREE', 'is_season_opener': False,
                     'week1_specification_defect': False}}


def test_a_the_stage_vocabulary_is_closed():
    print('\n-- the stage vocabulary --')
    check('a pre-inactives directory names stage 1',
          FS.stage_of_dirname('pre_inactives_V1_CANDIDATE_R8') == FS.PRE)
    check('a post-inactives directory names stage 2',
          FS.stage_of_dirname('post_inactives_V1_CANDIDATE_R8') == FS.POST)
    check("  and 'post' is never read as 'pre'",
          FS.stage_of_dirname('post_inactives_x') != FS.PRE)
    o = FS.resolve_stage('/x/some_other_directory')
    check('an unrecognised directory is REFUSED, not defaulted',
          o.state is State.BLOCKED and o.code == 'FORECAST_STAGE_UNKNOWN',
          f'{o.state.value}[{o.code}]')
    check('  because an unlabelled projection must never sit beside a '
          'labelled one', 'unlabelled' in o.detail)
    check('the vocabulary has exactly two members', len(FS.STAGES) == 2)


def test_b_the_three_qb_blockers_stay_distinct():
    print('\n-- stage vs specification vs enforcement --')
    pre = FS.qb_metric_blockers({'qb3_configuration': OPENER}, FS.PRE)
    check('at stage 1 the availability blocker is present',
          FS.QB_AVAILABILITY_UNRESOLVED in pre, str(pre))
    check('  and so is the season-boundary specification defect',
          FS.QB_WEEK1_BOUNDARY in pre, str(pre))
    post = FS.qb_metric_blockers(
        {'qb3_configuration': OPENER,
         'qb_inactive_ownership_enforced': True}, FS.POST)
    check('at stage 2 the availability blocker CLEARS',
          FS.QB_AVAILABILITY_UNRESOLVED not in post, str(post))
    check('  but the season-boundary defect DOES NOT',
          FS.QB_WEEK1_BOUNDARY in post,
          'ingesting an inactive list cannot repair a cell definition')
    clean = FS.qb_metric_blockers(
        {'qb3_configuration': MIDSEASON,
         'qb_inactive_ownership_enforced': True}, FS.POST)
    check('a mid-season enforced board has NO qb blocker', clean == [],
          str(clean))
    unen = FS.qb_metric_blockers(
        {'qb3_configuration': MIDSEASON,
         'qb_inactive_ownership_enforced': False}, FS.POST)
    check('an unenforced stage-2 board is blocked on ENFORCEMENT',
          unen == [FS.QB_OWNERSHIP_NOT_ENFORCED], str(unen))
    check('the three ids are distinct strings',
          len({FS.QB_AVAILABILITY_UNRESOLVED, FS.QB_WEEK1_BOUNDARY,
               FS.QB_OWNERSHIP_NOT_ENFORCED}) == 3)
    # AN ABSENT FIELD IS NOT A CLEARED ONE. This check's NAME was right and
    # its assertion was backwards: it pinned the behaviour where a board with
    # no `qb3_configuration` produced no boundary blocker. That is what let
    # all 55 quarterback markets of the 4:25 slate through the comparator
    # unrefused, because every board sealed before 21:20Z lacks the field.
    bare = FS.qb_metric_blockers({}, FS.POST)
    check('a board with no recorded configuration FAILS CLOSED',
          FS.QB_WEEK1_BOUNDARY in bare, str(bare))
    check('  and the detail says the board could not answer',
          'no qb3_configuration recorded' in FS.qb_blocker_detail({}, FS.POST))
    check('  a real pre-21:20Z board is now blocked too',
          FS.QB_WEEK1_BOUNDARY in FS.qb_metric_blockers(
              {'game_id': '2026_01_ARI_LAC', 'teams': ['ARI', 'LAC'],
               'qb_inactive_ownership_enforced': True}, FS.POST))
    check('  while a board that RECORDS a non-opener room is not blocked',
          FS.QB_WEEK1_BOUNDARY not in FS.qb_metric_blockers(
              {'qb3_configuration': MIDSEASON,
               'qb_inactive_ownership_enforced': True}, FS.POST))


def _stage_dir(root, cut, run, players, arrays, run_id, written_at):
    d = pathlib.Path(root) / f'{cut}_V1_CANDIDATE_R8' / run
    d.mkdir(parents=True, exist_ok=True)
    (d / 'board.json').write_text(json.dumps({
        'game_id': '2026_01_ZZ_YY', 'run_id': run_id, 'teams': ['ZZ', 'YY'],
        'players': players, 'freshness': {'written_at': written_at},
        'qb_inactive_ownership': {'inactive_qbs_excluded': {'ZZ': ['QB2']}},
    }))
    (d / 'player_draws_manifest.json').write_text(json.dumps({
        'layers': {'qb': {'row_axis': 'gsis_id',
                          'row_ids': [p['gsis_id'] for p in players],
                          'shape': [len(players), 100]}}}))
    np.savez(d / 'player_draws.npz', **arrays)
    return d


def _pair(root, post_players, post_arr):
    pre_players = [{'gsis_id': 'QB1', 'team': 'ZZ', 'position': 'QB',
                    'metrics': {'qb/db': {}}},
                   {'gsis_id': 'QB2', 'team': 'ZZ', 'position': 'QB',
                    'metrics': {'qb/db': {}}}]
    _stage_dir(root, 'pre_inactives', 'r1', pre_players,
               {'qb__db': np.vstack([np.full(100, 20.0), np.full(100, 10.0)])},
               'r1', '2026-09-13T15:00:00Z')
    _stage_dir(root, 'post_inactives', 'r2', post_players, post_arr,
               'r2', '2026-09-13T23:00:00Z')


def test_c_the_delta_joins_by_identity_and_conserves():
    print('\n-- the PRE -> POST delta --')
    with tempfile.TemporaryDirectory() as tmp:
        post_players = [{'gsis_id': 'QB1', 'team': 'ZZ', 'position': 'QB',
                         'metrics': {'qb/db': {}}},
                        {'gsis_id': 'QB2', 'team': 'ZZ', 'position': 'QB',
                         'metrics': {'qb/db': {}}}]
        # QB2 is ruled out; his 10 moves to QB1. Rows are stored in the
        # OPPOSITE order to stage 1, so a positional join would read backwards.
        _pair(tmp, post_players[::-1],
              {'qb__db': np.vstack([np.full(100, 0.0), np.full(100, 30.0)])})
        d = pathlib.Path(tmp)
        # rewrite the post manifest to the reversed identity order
        mp = next((d / 'post_inactives_V1_CANDIDATE_R8').glob('*/player_draws_manifest.json'))
        mp.write_text(json.dumps({'layers': {'qb': {
            'row_axis': 'gsis_id', 'row_ids': ['QB2', 'QB1'],
            'shape': [2, 100]}}}))
        rows, summ = SD.delta_for_game('2026_01_ZZ_YY', d,
                                       'V1_CANDIDATE_R8',
                                       {'QB1': 'Starter', 'QB2': 'Backup'})
    check('both stages were found', summ['status'] == 'OK', str(summ))
    by = {r['gsis_id']: r for r in rows}
    check('  the starter GAINS, read through row identity not position',
          by['QB1']['delta_mean'] == 10.0, str(by['QB1']))
    check('  the ruled-out quarterback goes to exactly zero',
          by['QB2']['post_mean'] == 0.0 and by['QB2']['delta_mean'] == -10.0,
          str(by['QB2']))
    check('  and he is marked as officially inactive',
          by['QB2']['became_officially_inactive'] is True)
    check('  the share is conserved: what one loses the other gains',
          abs(by['QB1']['delta_mean'] + by['QB2']['delta_mean']) < 1e-9)
    check('stage 1 is recorded as preserved', summ['stage_1_preserved'] is True)
    check('  with two different run ids',
          summ['pre_run_id'] != summ['post_run_id'])
    check('  and two different written_at clocks, neither restamped',
          summ['pre_written_at'] == '2026-09-13T15:00:00Z'
          and summ['post_written_at'] == '2026-09-13T23:00:00Z')


def test_d_a_missing_stage_is_a_named_state_not_a_crash():
    print('\n-- the expected pre-kickoff state --')
    with tempfile.TemporaryDirectory() as tmp:
        _stage_dir(tmp, 'pre_inactives', 'r1',
                   [{'gsis_id': 'QB1', 'team': 'ZZ', 'position': 'QB',
                     'metrics': {'qb/db': {}}}],
                   {'qb__db': np.full((1, 100), 20.0)}, 'r1',
                   '2026-09-13T15:00:00Z')
        rows, summ = SD.delta_for_game('2026_01_ZZ_YY', pathlib.Path(tmp),
                                       'V1_CANDIDATE_R8', {})
    check('a game with only stage 1 is NOT an error',
          summ['status'] == 'NO_POST_INACTIVES_BOARD', str(summ))
    check('  and the state says it is the expected one before kickoff',
          'expected state' in summ['detail'])
    check('  with no delta rows invented', rows == [])


def test_e_a_stage_2_that_rewrote_stage_1_is_refused():
    print('\n-- the restamp guard --')
    with tempfile.TemporaryDirectory() as tmp:
        pl = [{'gsis_id': 'QB1', 'team': 'ZZ', 'position': 'QB',
               'metrics': {'qb/db': {}}}]
        arr = {'qb__db': np.full((1, 100), 20.0)}
        _stage_dir(tmp, 'pre_inactives', 'same', pl, arr, 'same',
                   '2026-09-13T15:00:00Z')
        _stage_dir(tmp, 'post_inactives', 'same', pl, arr, 'same',
                   '2026-09-13T15:00:00Z')
        rows, summ = SD.delta_for_game('2026_01_ZZ_YY', pathlib.Path(tmp),
                                       'V1_CANDIDATE_R8', {})
    check('two stages sharing a run_id is REFUSED',
          summ['status'] == 'STAGES_SHARE_A_RUN_ID', str(summ))
    check('  because stage 2 must be a new artifact, never a rewrite',
          'never a rewrite of stage 1' in summ['detail'])
    check('  and no delta is produced from it', rows == [])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'\n{fn}')
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
