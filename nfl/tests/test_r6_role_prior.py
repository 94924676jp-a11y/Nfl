"""R6: the role-conditional class prior. Guards on a repair, not a preference."""
from __future__ import annotations

import os
import statistics
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                 # noqa: E402
from nfl.production import candidate_mode as CM                     # noqa: E402
from nfl.production.nonqb import role_prior as RP                   # noqa: E402

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


def test_r6_inherits_r5_and_adds_exactly_one_flag():
    r5 = CM.resolve(CM.V1_CANDIDATE_R5).value['flags']
    r6 = CM.resolve(CM.V1_CANDIDATE_R6).value['flags']
    check('R6 keeps every R5 flag',
          all(r6.get(k) == v for k, v in r5.items()), str(r6))
    check('  and adds exactly one',
          set(r6) - set(r5) == {'role_prior'}, str(set(r6) - set(r5)))
    v1 = CM.resolve(CM.V1_CANDIDATE).value['flags']
    check('  V1 remains the untouched control',
          'role_prior' not in v1 and 'active_roster_only' not in v1, str(v1))
    check('  and R6 is its own declared identity',
          CM.V1_CANDIDATE_R6 in CM.MODES)
    # Same lesson as R5's: assert the property, not a name that a later
    # candidate will make real.
    unknown = 'V1_CANDIDATE_' + 'X' * 8
    check('  an unknown configuration is still refused',
          unknown not in CM.MODES
          and CM.resolve(unknown).state is State.FAIL, unknown)


def test_the_shrinkage_constant_is_estimated_not_chosen():
    check('R6 declares it introduces no constant',
          CM.R6_REPAIR['introduces_no_constant'] is True)
    src = open(os.path.join(_ROOT,
                            'nfl/production/nonqb/role_prior.py')).read()
    check('  and the module states k is estimated',
          'never chosen' in src and 'within/between' in src.lower()
          or 'within-player' in src)


def test_a_long_history_is_not_overwritten_by_the_tier():
    """R6 must not replace an established starter with a league average."""
    prior = {'tier_mean': {'WR1': 0.22, 'WR4': 0.06}, 'k': {'WR': 0.87},
             'trailing_snap': {}, 'n_history': {}}
    own = 0.31
    long_hist = RP.weight('x', 'WR', own, 100, 1, prior)
    check('with 100 games his own value is returned almost unchanged',
          abs(long_hist - own) < 0.01, f'{long_hist:.4f} vs {own}')
    short = RP.weight('x', 'WR', own, 1, 1, prior)
    check('  with one game it is pulled toward his tier',
          prior['tier_mean']['WR1'] < short < own, f'{short:.4f}')
    none = RP.weight('x', 'WR', None, 0, 1, prior)
    check('  with no history it IS the tier mean',
          abs(none - 0.22) < 1e-9, f'{none:.4f}')


def test_tier_changes_the_answer_for_a_player_with_no_history():
    """This is the whole repair: a no-history WR1 and a no-history WR4 must
    not price the same, which is exactly what the positional mean did."""
    prior = {'tier_mean': {'WR1': 0.22, 'WR4': 0.06}, 'k': {'WR': 0.87},
             'trailing_snap': {}, 'n_history': {}}
    top = RP.weight('a', 'WR', None, 0, 1, prior)
    low = RP.weight('b', 'WR', None, 0, 4, prior)
    check('a no-history top-tier player prices above a no-history fringe one',
          top > low, f'{top:.3f} vs {low:.3f}')
    check('  and the ratio reflects the historical spread, not 1:1',
          top / low > 3.0, f'{top / low:.2f}')


def test_tier_assignment_is_point_in_time_and_names_its_basis():
    prior = {'tier_mean': {}, 'k': {}, 'trailing_snap': {'A': 0.8, 'B': 0.4},
             'n_history': {}}
    players = [{'gsis_id': 'A', 'team': 'SF', 'position': 'WR'},
               {'gsis_id': 'B', 'team': 'SF', 'position': 'WR'},
               {'gsis_id': 'C', 'team': 'SF', 'position': 'WR'},
               {'gsis_id': 'D', 'team': 'SF', 'position': 'WR'}]
    got = RP.assign_tiers(players, prior, depth_rank={'C': 2})
    check('trailing snap share ranks the players who have it',
          got['tier']['A'] == 1 and got['tier']['B'] == 2, str(got['tier']))
    check('  the depth chart ranks the one who does not',
          got['basis']['C'] == 'depth_chart', got['basis']['C'])
    check('  and a player with neither is placed lowest and SAID to be',
          got['basis']['D'] == 'no_information_lowest_tier'
          and got['tier']['D'] > got['tier']['C'], str(got['basis']))


def test_no_player_or_team_is_hard_coded():
    src = open(os.path.join(_ROOT,
                            'nfl/production/nonqb/role_prior.py')).read()
    for bad in ('Nacua', 'McCaffrey', 'Kittle', 'Adams', 'Purdy', 'Stafford',
                "'SF'", "'LA'"):
        check(f'  no hard-coded {bad}', bad not in src, bad)


def test_a_prior_over_nothing_refuses():
    o = RP.build([], 'target_share', ('WR',), 202601)
    check('an empty history refuses by name',
          o.state is not State.PASS and o.code == 'ROLE_PRIOR_NO_HISTORY',
          o.code)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
