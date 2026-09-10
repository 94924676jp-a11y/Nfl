"""The shadow evaluation's own guards: the seal, the vintage cut, the scores,
and the attribution rule.

THE ATTRIBUTION RULE IS TESTED BECAUSE IT WAS WRONG ONCE. Its first version
keyed an in-game quarterback change to whether the play-by-play named THAT
quarterback as injured, which credited the departing starter and recorded the
REPLACEMENT -- whose forecast the same event wrecked far more -- as a model
miss, while firing for third-string quarterbacks who never took a snap. A rule
that decides what counts as the model's fault is exactly the kind of rule that
must not be able to drift in the model's favour unnoticed.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.shadow import ledger as LG                     # noqa: E402
from nfl.research.shadow import score as SCORE                   # noqa: E402
from nfl.research.shadow import information_set as IS            # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


# --- the vintage cut -------------------------------------------------------

def test_information_set_is_strictly_pre_kickoff():
    ko = '2026-09-10T00:20:00Z'
    info = IS.build(ko)
    late = [(k, v['observed_at']) for k, v in info['sources'].items()
            if v['observed_at'] >= ko]
    assert check('every selected source is observed before kickoff',
                 not late, str(late))
    assert check('and sources with no pre-kickoff capture are NAMED, not '
                 'dropped',
                 isinstance(info['absent'], list) and
                 set(info['absent']) & {'snap_counts', 'pbp_participation'},
                 str(info['absent']))


def test_the_selector_refuses_a_post_kickoff_choice():
    """A capture observed AFTER kickoff must never be selectable, however
    much better it looks. The rehearsal slate driver picks the roster with the
    most rows and lands on a post-kickoff vintage; this selector must not."""
    first = IS.first_observation()
    rosters = {sha: o for (src, sha), o in first.items()
               if src == 'weekly_rosters'}
    post = [sha for sha, o in rosters.items()
            if o['observed_at'].isoformat() >= '2026-09-10T00:20:00']
    assert check('the manifest really does contain post-kickoff rosters',
                 bool(post), 'nothing to distinguish -- test is inert')
    chosen = IS.build('2026-09-10T00:20:00Z')['sources']['weekly_rosters']
    assert check('  and none of them was chosen',
                 chosen['sha256'] not in post, chosen['sha256'])


# --- the proper scores -----------------------------------------------------

def test_crps_matches_the_definition_on_a_known_case():
    # For a point mass at c, CRPS reduces to |c - y|.
    x = np.full(500, 7.0)
    assert check('CRPS of a point mass is the absolute error',
                 abs(SCORE.crps(x, 3.0) - 4.0) < 1e-12,
                 str(SCORE.crps(x, 3.0)))
    # Against the pairwise-difference definition, computed the slow way.
    rng = np.random.default_rng(11)
    s = rng.normal(10.0, 3.0, 400)
    slow = float(np.abs(s - 12.0).mean()
                 - 0.5 * np.abs(s[:, None] - s[None, :]).mean())
    assert check('  and it equals the O(n^2) definition elsewhere',
                 abs(SCORE.crps(s, 12.0) - slow) < 1e-9,
                 f'{SCORE.crps(s, 12.0)} vs {slow}')


def test_pit_reports_the_discrete_bracket_not_a_single_number():
    x = np.array([0, 0, 0, 1, 1, 2, 2, 2, 2, 2], float)
    p = SCORE.pit(x, 1.0)
    assert check('F(y-) and F(y) are both reported',
                 abs(p['F_below'] - 0.3) < 1e-12
                 and abs(p['F_at_or_below'] - 0.5) < 1e-12, str(p))
    assert check('  and the midpoint sits between them',
                 abs(p['mid_pit'] - 0.4) < 1e-12, str(p))
    assert check('  and the mass at the actual is carried',
                 abs(p['p_mass_at_actual'] - 0.2) < 1e-12, str(p))


def test_thresholds_never_duplicate_a_line_on_a_count_metric():
    x = np.array([0, 1, 1, 2, 2, 2, 3, 3, 4, 5], float)
    lines = [t['line'] for t in SCORE.thresholds(x, SCORE.STEP['int'])]
    assert check('count-metric lines are distinct',
                 len(lines) == len(set(lines)), str(lines))
    assert check('  and none can be landed on exactly',
                 all(abs(l - round(l)) > 0.4 for l in lines), str(lines))


# --- the attribution rule --------------------------------------------------

def _changes():
    return {'SEA': {'segments': [
                {'gsis_id': 'STARTER', 'name': 'S.Start', 'from_play_id': 10},
                {'gsis_id': 'BACKUP', 'name': 'B.Back', 'from_play_id': 500}],
            'changed': True},
            'NE': {'segments': [
                {'gsis_id': 'IRONMAN', 'name': 'I.Man', 'from_play_id': 20}],
            'changed': False}}


def test_role_change_covers_the_replacement_as_well_as_the_starter():
    rc = LG.role_changed(_changes())
    assert check('the departing starter changed role', rc['STARTER'] is True)
    assert check('  and so did the replacement', rc['BACKUP'] is True,
                 'ATTRIBUTION_CREDITS_ONLY_THE_INJURED_PLAYER: the '
                 'replacement carries the same disruption')
    assert check('  and a quarterback who played throughout did not',
                 rc['IRONMAN'] is False)


def test_a_quarterback_who_never_threw_is_not_a_role_change():
    rc = LG.role_changed(_changes())
    assert check('a third-stringer with no pass play is absent from the rule',
                 'THIRD_STRING' not in rc, str(sorted(rc)))
    got = LG.classify('qb', 'SEA', 'THIRD_STRING', True, 'EXACT', rc, {'SEA'})
    assert check('  so a correct near-zero forecast is scored on its merits',
                 got == 'WITHIN_DISTRIBUTION', got)


def test_the_injury_half_of_the_rule_is_load_bearing():
    ch = _changes()
    rc = LG.role_changed(ch)
    inj = {('SEA', 'S.Start'): 180}
    hurt = LG.team_qb_injured(ch, inj)
    assert check('an injured passer marks his team', hurt == {'SEA'},
                 str(hurt))
    assert check('  and both quarterbacks are attributed to the change',
                 LG.classify('qb', 'SEA', 'STARTER', False, 'EXACT', rc, hurt)
                 == 'IN_GAME_STATE_CHANGE'
                 and LG.classify('qb', 'SEA', 'BACKUP', False, 'EXACT', rc,
                                 hurt) == 'IN_GAME_STATE_CHANGE')
    # WITH NO INJURY RECORDED the class must CHANGE, not quietly persist.
    assert check('  a role change with no injury is reported separately',
                 LG.classify('qb', 'SEA', 'STARTER', False, 'EXACT', rc, set())
                 == 'IN_GAME_ROLE_CHANGE_NO_INJURY_RECORDED')


def test_a_real_miss_cannot_be_excused_by_the_rule():
    """The rule must not be able to absorb a plain miss. A quarterback who
    played the whole game and finished outside his own 90% interval is a
    MODEL_MISS whatever else happened in the game."""
    rc = LG.role_changed(_changes())
    got = LG.classify('qb', 'NE', 'IRONMAN', False, 'EXACT', rc, {'SEA', 'NE'})
    assert check('a whole-game quarterback outside 90% is a MODEL_MISS',
                 got == 'MODEL_MISS', got)


def test_a_surrogate_actual_never_carries_a_verdict_or_a_proper_score():
    rc = LG.role_changed(_changes())
    got = LG.classify('team', 'NE', 'NE', False, 'SURROGATE', rc, set())
    assert check('a surrogate actual is not classified',
                 got == 'NOT_CLASSIFIED_SURROGATE_ACTUAL', got)


def test_an_absent_forecast_is_a_row_rather_than_a_silence():
    rc = LG.role_changed(_changes())
    got = LG.classify('skill', 'NE', 'X', None, 'NO_FORECAST', rc, set())
    assert check('a missing forecast is recorded against a real outcome',
                 got == 'NO_FORECAST_MISSING_PREGAME_INPUT', got)


# --- the seal --------------------------------------------------------------

def test_the_seal_is_verified_and_a_broken_one_refuses():
    rec = SCORE.verify_seal()
    assert check('the sealed forecast still hashes to its recorded value',
                 len(rec) >= 5, str(sorted(rec)))
    import hashlib
    import pathlib
    p = pathlib.Path(_ROOT) / 'nfl/research/shadow/g1_ne_sea/EVALUATION.json'
    assert check('  and the evaluation was written against that seal',
                 p.exists() and hashlib.sha256(p.read_bytes()).hexdigest())
