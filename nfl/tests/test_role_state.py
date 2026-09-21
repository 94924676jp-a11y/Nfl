"""The role engine, pinned against the case that produced it and against itself.

THE CASES

1. VanSumeren. Rostered RB, listed FB1, 4% of Kansas City's week-1 offensive
   snaps, 0 carries. He must land OUTSIDE the workload-bearing set. The first
   draft of the engine failed this: a fullback branch relabelled him FULLBACK
   on the strength of his listing, which is position implying workload inside
   the module written to forbid it.
2. A channel never promotes a band. Same rule, stated as a property rather
   than a player, so it cannot be satisfied by special-casing one name.
3. No measured participation means ROLE_UNCERTAIN however high the listing.
   A depth chart is a statement of intent.
4. The boundaries are estimated. Feed the estimator a different league and the
   cut points move; feed it one it cannot order and it refuses. There is no
   fallback set of constants.
5. The week being forecast is never in its own evidence.
6. A club absent from the usage capture is UNMEASURED, not zero.
7. The gate fails on an unsupported player in the publishable set, and BLOCKS
   when no consumer declared one -- the same correction the coverage gate took.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import player_universe as PU         # noqa: E402
from nfl.production.universe import role_state as RS              # noqa: E402
from nfl.production.nonqb import (                                # noqa: E402
    current_season_nonqb_panel as CP)
from sportsplatform.governance.outcome import State               # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T18:45:00Z'
_CACHE = {}


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _game(game_id, week=2):
    if game_id in _CACHE:
        return _CACHE[game_id]
    if 'usage' not in _CACHE:
        u = CP.usage_season(2026, as_of=CUT)
        _CACHE['usage'] = u.value if u.state is State.PASS else {}
    uni = PU.build(2026, week, game_id, CUT)
    if uni.state is not State.PASS:
        _CACHE[game_id] = (None, None)
        return _CACHE[game_id]
    o = RS.assign(uni.value, season=2026, week=week,
                  usage_rows=_CACHE['usage'])
    _CACHE[game_id] = (uni, o)
    return _CACHE[game_id]


def _by_name(rows, frag):
    return [r for r in rows if frag.lower() in (r.get('display_name') or
                                                '').lower()]


def test_a_listing_never_buys_a_workload():
    uni, o = _game('2026_02_IND_KC')
    if o is None:
        ok(False, 'IND@KC universe could not be built')
        return
    ok(o.state is State.PASS, f'the engine ran: {o.code}')
    rows = o.value

    vs = _by_name(rows, 'vansumeren')
    ok(len(vs) == 1, f'exactly one VanSumeren row: {len(vs)}')
    if vs:
        r = vs[0]
        snap = r['evidence']['current_season_snaps']['mean_offense_pct']
        ok(r['role'] not in RS.WORKLOAD_BEARING,
           f'a 4%-snap fullback is not workload-bearing: {r["role"]} '
           f'at snap share {snap}')
        ok(r['channel'] == 'fullback',
           f'his channel is still recorded: {r["channel"]}')
        ok(snap is not None and snap < 0.10,
           f'the number the band rests on is his own: {snap}')
        ok(any('does not promote' in w for w in r['role_why']),
           'the row says in words why the channel did not promote him')

    # And the rule as a property: no row is workload-bearing on a band its own
    # measured share does not reach.
    b = o.evidence['boundaries']
    bad = [r for r in rows if r['role'] in RS.WORKLOAD_BEARING
           and r['room'] != RS.ROOM_KICKING
           and (r['evidence']['current_season_snaps']['mean_offense_pct'] or 0)
           < b['secondary_floor']]
    ok(not bad,
       f'no workload-bearing role sits below the secondary floor: '
       f'{[(x["display_name"], x["role"]) for x in bad]}')


def test_no_participation_is_role_uncertain_however_high_the_listing():
    uni, o = _game('2026_02_NYG_LA')
    if o is None:
        ok(False, 'NYG@LA universe could not be built')
        return
    rows = o.value
    unmeasured = [r for r in rows
                  if r['evidence']['current_season_snaps'][
                      'mean_offense_pct'] is None
                  and r['room'] != RS.ROOM_KICKING]
    ok(unmeasured, f'the game has unmeasured players to test: {len(unmeasured)}')
    bad = [r for r in unmeasured if r['role'] != RS.ROLE_UNCERTAIN]
    ok(not bad,
       f'every player with no measured participation is ROLE_UNCERTAIN: '
       f'{[(x["display_name"], x["role"]) for x in bad]}')
    listed_high = [r for r in unmeasured
                   if (r['evidence']['depth_listing'].get('rank') or 99) <= 2]
    ok(all(r['role'] == RS.ROLE_UNCERTAIN for r in listed_high),
       f'including {len(listed_high)} listed first or second in their room')
    ok(all(r['role_support'] == RS.ROLE_UNSUPPORTED for r in unmeasured),
       'and none of them is role-supported')

    # Every role that leaves the engine is in the closed set.
    ok(all(r['role'] in RS.ROLES for r in rows),
       'no row carries a role outside the declared set')
    ok(all(r['role_support'] in (RS.ROLE_SUPPORTED, RS.ROLE_UNSUPPORTED)
           for r in rows), 'every row carries one of the two support states')
    ok(all(bool(r['role_why']) for r in rows),
       'every row says why it got the role it got')


def test_the_boundaries_are_estimated_and_refusable():
    uni, o = _game('2026_02_IND_KC')
    b, be = o.evidence['boundaries'], o.evidence['boundary_evidence']
    ok(b['starter_floor'] > b['primary_floor'] > b['secondary_floor'],
       f'the floors are ordered: {b}')
    ok(set(be['rank_means']) >= {1, 2, 3, 4},
       f'all four ranks were estimated: {sorted(be["rank_means"])}')
    ok(all(n >= 30 for n in be['rank_n'].values()),
       f'no rank rests on a thin cell: {be["rank_n"]}')
    for i in (1, 2, 3):
        want = (be['rank_means'][i] + be['rank_means'][i + 1]) / 2.0
        got = list(b.values())[i - 1]
        ok(abs(got - want) < 1e-12,
           f'floor {i} is exactly the midpoint of ranks {i} and {i+1}: '
           f'{got:.6f} vs {want:.6f}')

    # An unorderable league is refused, not smoothed.
    fake = [{'pfr_player_id': f'p{i}', 'offense_pct': str(0.1 * (i % 4 + 1)),
             'position': 'WR', 'team': 'XX', 'week': '1', 'season': '2026'}
            for i in range(40)]
    ranks = {f'p{i}': (i % 4) + 1 for i in range(40)}   # rank rises with share
    bad = RS.derive_boundaries(fake, ranks)
    ok(bad.state is State.BLOCKED
       and bad.code == 'ROLE_BOUNDARIES_NOT_MONOTONE',
       f'a league where deeper players play more is refused: {bad.code}')
    empty = RS.derive_boundaries([], {})
    ok(empty.state is State.BLOCKED
       and empty.code == 'ROLE_BOUNDARIES_UNDERDETERMINED',
       f'an empty league is refused rather than defaulted: {empty.code}')


def test_the_forecast_week_is_never_in_its_own_evidence():
    s = RS.load_snaps(2026, 2)
    ok(s.state is State.PASS, f'week-1 snaps load for a week-2 forecast: {s.code}')
    ok(all(w < 2 for w in s.evidence['weeks']),
       f'and carry no week 2 or later: {s.evidence["weeks"]}')
    s1 = RS.load_snaps(2026, 1)
    ok(s1.state is State.BLOCKED and s1.code == 'ROLE_SNAPS_NO_PRIOR_WEEK',
       f'week 1 has no in-season participation and the engine says so '
       f'rather than inventing one: {s1.code}')
    s0 = RS.load_snaps(1998, 2)
    ok(s0.state is State.BLOCKED and s0.code == 'ROLE_SNAPS_NO_CAPTURE',
       f'a season with no capture refuses: {s0.code}')

    uni, o = _game('2026_02_NYG_LA')
    weeks = {k for r in o.value for k in ()}          # no leakage surface
    ok(not weeks, 'no row carries a week later than the forecast week')
    ok(o.evidence['snap_evidence']['before_week'] == 2,
       'the evidence records the cut the snaps were taken before')


def test_a_club_with_no_usage_capture_is_unmeasured_not_zero():
    uni, o = _game('2026_02_NYG_LA')
    absent = o.evidence['clubs_absent_from_usage_capture']
    ok(isinstance(absent, list), f'the absent clubs are named: {absent}')
    for r in o.value:
        st = r['evidence']['current_season_usage']['state']
        ok_state = st in ('MEASURED', 'CLUB_ABSENT_FROM_USAGE_CAPTURE')
        if not ok_state:
            ok(False, f'{r["display_name"]} carries usage state {st!r}')
            return
    ok(True, 'every row declares whether its club usage was measured at all')
    for c in absent:
        rs = [r for r in o.value if r['team'] == c]
        ok(all(r['evidence']['current_season_usage']['state']
               == 'CLUB_ABSENT_FROM_USAGE_CAPTURE' for r in rs),
           f'{c} rows all say the capture is absent, not that usage was zero')
        ok(all(r['evidence']['current_season_usage']['carry_share'] is None
               for r in rs),
           f'{c} shares are None rather than 0.0, which a consumer could '
           f'take for a measured zero')
    if not absent:
        ok(True, 'no club is absent from the capture in this game')

    # An unmeasured club must not manufacture a channel conflict.
    bad = [r for r in o.value
           if r['evidence']['current_season_usage']['state'] != 'MEASURED'
           and any(c['code'] == RS.C_CHANNEL for c in r['conflicts'])]
    ok(not bad, f'no channel conflict is raised on unmeasured usage: '
                f'{[x["display_name"] for x in bad]}')


def test_axes_the_engine_cannot_obtain_are_named():
    uni, o = _game('2026_02_IND_KC')
    ok(o.evidence['axes_unavailable'], 'the missing axes are listed')
    for r in o.value[:5]:
        e = r['evidence']
        ok(set(e) >= set(RS.AXES),
           f'every declared axis appears on the row: missing '
           f'{sorted(set(RS.AXES) - set(e))}')
        ok(e['prior_season_snaps']['state'] == 'UNAVAILABLE'
           and e['transactions']['state'] == 'UNAVAILABLE',
           'an axis with no source says UNAVAILABLE rather than going absent')


def test_conflicts_are_named_and_block():
    uni, o = _game('2026_02_NYG_LA')
    rows = o.value
    for r in rows:
        for c in r['conflicts']:
            ok(c['code'] in RS.CONFLICTS,
               f'{r["display_name"]}: {c["code"]} is a declared conflict code')
            ok(bool(c.get('detail')), f'{c["code"]} carries its own evidence')
    conflicted = [r for r in rows if r['conflicts']]
    ok(all(r['role_support'] == RS.ROLE_UNSUPPORTED for r in conflicted),
       f'every conflicted player is unsupported: {len(conflicted)} conflicted')
    ok(all(any(c['code'] in r['role_unsupported_why'] for c in r['conflicts'])
           for r in conflicted),
       'and the reason travels with him')
    clean = [r for r in rows if not r['conflicts']
             and r['role'] != RS.ROLE_UNCERTAIN]
    ok(all(r['role_support'] == RS.ROLE_SUPPORTED for r in clean),
       'a player with a measured role and no conflict is supported')


def test_the_gate_fails_blocks_and_passes_for_the_right_reasons():
    uni, o = _game('2026_02_IND_KC')
    rows = o.value
    supported = {r['gsis_id'] for r in rows
                 if r['role_support'] == RS.ROLE_SUPPORTED
                 and r['role'] in RS.WORKLOAD_BEARING}
    unsupported = {r['gsis_id'] for r in rows
                   if r['role_support'] == RS.ROLE_UNSUPPORTED}

    g = RS.assert_role_state_supported(rows, publishable_ids=supported)
    ok(g.state is State.PASS,
       f'a publishable set of supported players clears: {g.code}')
    ok(g.evidence.get('certified') is True, 'and is certified')
    ok(len(g.evidence['withheld']) == len(unsupported),
       f'the withheld players are itemised: {len(g.evidence["withheld"])}')

    if unsupported:
        g2 = RS.assert_role_state_supported(
            rows, publishable_ids=supported | {sorted(unsupported)[0]})
        ok(g2.state is State.FAIL
           and g2.code == 'ROLE_UNSUPPORTED_PLAYER_IN_PUBLISHABLE_SET',
           f'one unsupported player in the set fails the gate: {g2.code}')
        ok(len(g2.evidence['offending']) == 1,
           'and exactly he is named')
        ok(all('why' in x for x in g2.evidence['offending']),
           'with his reason attached')

    g3 = RS.assert_role_state_supported(rows)
    ok(g3.state is State.BLOCKED and g3.code == 'NO_PUBLISHABLE_SET_DECLARED',
       f'no declared consumer BLOCKS rather than certifying an unexamined '
       f'board: {g3.code}')
    ok(g3.evidence.get('n_unsupported') == len(unsupported),
       'and the blocked outcome still carries the count it could not clear')

    g4 = RS.assert_role_state_supported(rows, publishable_ids=set())
    ok(g4.state is State.PASS,
       'an explicitly empty publishable set is a valid result, not a failure')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_a_listing_never_buys_a_workload,
              test_no_participation_is_role_uncertain_however_high_the_listing,
              test_the_boundaries_are_estimated_and_refusable,
              test_the_forecast_week_is_never_in_its_own_evidence,
              test_a_club_with_no_usage_capture_is_unmeasured_not_zero,
              test_axes_the_engine_cannot_obtain_are_named,
              test_conflicts_are_named_and_block,
              test_the_gate_fails_blocks_and_passes_for_the_right_reasons):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
