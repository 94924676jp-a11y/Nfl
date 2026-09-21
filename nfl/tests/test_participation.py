"""Participation is a budget the game fixes, and what is unknown stays named.

WHAT THIS PINS

1. The budget is MEASURED. Eleven on the field, one quarterback, five linemen,
   five skill players. If the capture does not reproduce eleven, `offense_pct`
   does not mean what the schema says and the layer refuses rather than
   dividing by a misunderstood quantity.
2. A player with no measured participation gets NO share -- not a zero and not
   an anchor. His club's budget stays open by exactly the amount he is not
   accounted for.
3. The unresolved mass is reported, never distributed. Distributing it among
   players whose role is unknown is the cold start the role engine exists to
   refuse, and it would be undone here if this layer smoothed it away.
4. There is NO TOLERANCE IN THE LAYER. How much unreconstructed mass is
   acceptable belongs to whoever divides by the denominator; the gate requires
   that declaration and records it. The first draft compared the residual
   against the league total's standard deviation, which is a different
   quantity: one is how much clubs differ from each other, the other is how
   much of this club was not reconstructed.
5. Dispersion is not identified from one observed week and the layer says so
   instead of substituting between-player spread.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import governed_thresholds as GT      # noqa: E402
from nfl.production.universe import participation as PA            # noqa: E402
from nfl.production.universe import player_universe as PU          # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from nfl.production.nonqb import (                                 # noqa: E402
    current_season_nonqb_panel as CP)
from sportsplatform.governance.outcome import State                # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T19:12:00Z'
_C = {}


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _ctx():
    if 'snaps' not in _C:
        s = RS.load_snaps(2026, 2)
        _C['snaps'] = s.value if s.state is State.PASS else []
        u = CP.usage_season(2026, as_of=CUT)
        _C['usage'] = u.value if u.state is State.PASS else {}
        _C['budget'] = PA.measure_budget(_C['snaps'])
    return _C


def _game(game_id):
    c = _ctx()
    if game_id not in _C:
        uni = PU.build(2026, 2, game_id, CUT)
        ro = RS.assign(uni.value, season=2026, week=2, usage_rows=c['usage'])
        po = PA.assess(ro.value, budget=c['budget'].value)
        _C[game_id] = (ro, po)
    return _C[game_id]


def _rows(po):
    return po.value or (po.evidence or {}).get('value') or []


def test_the_budget_is_measured_and_is_the_game_itself():
    c = _ctx()
    b = c['budget']
    ok(b.state is State.PASS, f'the budget measures: {b.code}')
    v = b.value
    ok(abs(v['all_positions'] - 11.0) < 0.05,
       f'all positions sum to eleven on the field: {v["all_positions"]:.4f}')
    ok(abs(v['qb_budget'] - 1.0) < 0.02,
       f'exactly one quarterback: {v["qb_budget"]:.4f}')
    ok(4.7 < v['skill_nonqb_budget'] < 5.0,
       f'the non-QB skill budget is just under five, the deficit being '
       f'six-lineman personnel: {v["skill_nonqb_budget"]:.4f}')
    ok(v['skill_nonqb_sd'] > 0,
       f'and the spread between clubs travels with it: '
       f'{v["skill_nonqb_sd"]:.4f}')
    ok(v['n_team_games'] >= 30,
       f'estimated from the whole league, not two clubs: '
       f'{v["n_team_games"]} team-games')

    # The structural check refuses a capture whose column means something else.
    half = [dict(r, offense_pct=str((PA.RS._f(r.get('offense_pct')) or 0) / 2))
            for r in c['snaps']]
    bad = PA.measure_budget(half)
    ok(bad.state is State.FAIL
       and bad.code == 'PARTICIPATION_BUDGET_NOT_ELEVEN_ON_FIELD',
       f'a capture that does not reproduce eleven is refused: {bad.code}')
    ok(PA.measure_budget([]).state is State.BLOCKED,
       'and an empty capture is blocked rather than defaulted')


def test_an_unmeasured_player_gets_no_share_not_a_zero():
    ro, po = _game('2026_02_NYG_LA')
    rows = _rows(po)
    ok(rows, f'the layer produced rows: {len(rows)}')
    unmeasured = [r for r in rows if r['measured_snap_share'] is None]
    ok(unmeasured, f'the game contains unmeasured players: {len(unmeasured)}')
    ok(all(r['expected_snap_share'] is None for r in unmeasured),
       'none of them carries an expected share')
    ok(all(r['participation_state'] == PA.UNSUPPORTED for r in unmeasured),
       'each is explicitly unsupported')
    ok(all('cold start' in r['participation_why'] for r in unmeasured),
       'and the row says why, in the words of the rule it obeys')

    # A measured player whose ROLE is unsupported also gets no share: a share
    # is only as good as the role it sits in.
    roleless = [r for r in rows if r['measured_snap_share'] is not None
                and r['role_support'] == RS.ROLE_UNSUPPORTED]
    ok(all(r['expected_snap_share'] is None for r in roleless),
       f'{len(roleless)} measured-but-role-unsupported player(s) carry no '
       f'expected share either')

    resolved = [r for r in rows if r['participation_state'] == PA.RESOLVED]
    ok(all(r['expected_snap_share'] == r['measured_snap_share']
           for r in resolved),
       'a resolved player carries exactly his own measured share, unsmoothed')
    ok(all(r['expected_snap_share'] is not None for r in resolved),
       'and never a None')


def test_the_unresolved_mass_is_named_and_never_distributed():
    for gid in ('2026_02_NYG_LA', '2026_02_IND_KC'):
        ro, po = _game(gid)
        clubs = po.evidence['clubs']
        ok(len(clubs) == 2, f'{gid}: both clubs are reported: {sorted(clubs)}')
        for club, v in clubs.items():
            acc = sum(r['expected_snap_share'] for r in _rows(po)
                      if r['team'] == club
                      and r['room'] != RS.ROOM_DROPBACKS
                      and r['expected_snap_share'] is not None)
            ok(abs(acc - v['accounted_nonqb']) < 1e-9,
               f'{club}: the accounted mass is exactly the sum of the '
               f'resolved shares ({acc:.4f}), with nothing added')
            ok(abs((v['accounted_nonqb']
                    + v['unresolved_participation_mass']) - v['budget'])
               < 1e-9,
               f'{club}: accounted plus unresolved is the budget, so no mass '
               f'is lost or invented')
            ok(v['unresolved_fraction_of_budget'] is not None,
               f'{club}: the gap is expressed as a fraction a reader can use')
            if v['n_unsupported']:
                ok(len(v['unsupported_players']) == v['n_unsupported'],
                   f'{club}: every withheld player is itemised by name')


def test_dispersion_is_not_manufactured_from_one_week():
    ro, po = _game('2026_02_IND_KC')
    rows = _rows(po)
    ok(po.evidence['dispersion_state'] == PA.DISPERSION_UNIDENTIFIED,
       f'the layer declares dispersion unidentified: '
       f'{po.evidence["dispersion_state"]}')
    one_week = [r for r in rows if (r['n_observed_games'] or 0) < 2]
    ok(one_week, f'most players have one observed game: {len(one_week)}')
    ok(all(r['dispersion_state'] == PA.DISPERSION_UNIDENTIFIED
           for r in one_week),
       'and each says so on his own row')
    ok(all('different quantity' in r['dispersion_why'] for r in rows),
       'naming the substitution it refuses to make')
    ok(all(r['p_meaningful_participation'] is None for r in rows),
       'a participation probability is left unset rather than filled with a '
       'share, which is a different quantity')


def test_a_caller_supplied_tolerance_cannot_certify_anything():
    """The correction of 2026-09-21, pinned as a property.

    The gate previously passed on whatever number the caller handed it, so
    New York's 21.1% unresolved mass cleared against a 25% figure with no
    justification of any kind. That reproduced exactly the pattern this
    project is eliminating: BLOCKED, but below our chosen tolerance,
    therefore PASS. The number that decides what passes must not be settable
    at the call site that wants it to pass.
    """
    ro, po = _game('2026_02_NYG_LA')
    rows = _rows(po)
    alloc = {r['gsis_id'] for r in rows
             if r['participation_state'] == PA.RESOLVED}
    worst = max(abs(v['unresolved_fraction_of_budget'])
                for v in po.evidence['clubs'].values())
    ok(worst > 0, f'this game has real unreconstructed mass: {worst:.2%}')

    # A caller tolerance wide enough to swallow the gap must NOT pass.
    loose = PA.assert_participation_supports_allocation(
        po, allocating_ids=alloc, max_unresolved_fraction=worst * 2.0)
    ok(loose.state is not State.PASS,
       f'a caller-supplied tolerance twice the gap does not clear the gate: '
       f'{loose.state.name}[{loose.code}]')
    ev = loose.evidence or {}
    ok(ev.get('applied_max_unresolved_fraction')
       == GT.PARTICIPATION_UNRESOLVED_FRACTION['max_unresolved_fraction'],
       f'the GOVERNED value is what applied, not the caller\'s: '
       f'{ev.get("applied_max_unresolved_fraction")}')
    ok(ev.get('caller_proposed_max_unresolved_fraction') == worst * 2.0,
       'the caller\'s proposal is recorded as what it was -- a proposal')
    ok(ev.get('caller_proposal_was_not_applied') is True,
       'and the record says plainly that it was not applied')

    # The governed value is itself only CANDIDATE, so even a club inside it
    # cannot clear.
    ok(GT.PARTICIPATION_UNRESOLVED_FRACTION['certification']
       == GT.CANDIDATE,
       'the governed tolerance is CANDIDATE, not PRODUCTION_CERTIFIED')
    ok(not GT.is_clearing(GT.PARTICIPATION_UNRESOLVED_FRACTION[
        'certification']),
       'and a CANDIDATE certification clears nothing')

    clean = [r for r in rows if r['team'] == min(
        po.evidence['clubs'],
        key=lambda c: abs(po.evidence['clubs'][c][
            'unresolved_fraction_of_budget']))]
    inside = PA.assert_participation_supports_allocation(
        po, allocating_ids={r['gsis_id'] for r in clean
                            if r['participation_state'] == PA.RESOLVED})
    ok(inside.state is not State.PASS,
       f'even the better club does not clear, because the standard it would '
       f'be judged against has not been validated: {inside.code}')

    nos = PA.assert_participation_supports_allocation(po)
    ok(nos.state is State.BLOCKED
       and nos.code == 'NO_ALLOCATING_DECLARATION',
       f'no declared allocating set still blocks: {nos.code}')

    # An unsupported player in the allocating set fails on its own terms.
    uns = [r['gsis_id'] for r in rows
           if r['participation_state'] == PA.UNSUPPORTED]
    if uns:
        g = PA.assert_participation_supports_allocation(
            po, allocating_ids=alloc | {uns[0]})
        ok(g.state is State.FAIL,
           f'an unestablished player in the allocating set fails: {g.code}')
        ok(len(g.evidence['offending']) == 1, 'and exactly he is named')

    ok(GT.summary()['n_production_certified'] == 0,
       'nothing in the system is production-certified today, and the '
       'registry says so rather than letting a gate imply otherwise')


def test_the_layer_produces_no_football_output():
    ro, po = _game('2026_02_IND_KC')
    forbidden = ('targets', 'carries', 'yards', 'touchdown', 'dk_points',
                 'fantasy', 'salary', 'price', 'odds', 'ownership')
    for r in _rows(po)[:6]:
        hit = [k for k in r if any(f in k.lower() for f in forbidden)]
        ok(not hit, f'{r["display_name"]}: no opportunity or price field '
                    f'leaked onto a participation row: {hit}')
    ok(all(r['room'] in (RS.ROOM_CARRIES, RS.ROOM_TARGETS, RS.ROOM_DROPBACKS)
           for r in _rows(po)),
       'kickers take no offensive snaps and are not given a budget share')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_the_budget_is_measured_and_is_the_game_itself,
              test_an_unmeasured_player_gets_no_share_not_a_zero,
              test_the_unresolved_mass_is_named_and_never_distributed,
              test_dispersion_is_not_manufactured_from_one_week,
              test_a_caller_supplied_tolerance_cannot_certify_anything,
              test_the_layer_produces_no_football_output):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
