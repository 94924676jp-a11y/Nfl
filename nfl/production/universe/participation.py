"""Participation before opportunity, with a budget the game itself fixes.

WHY THIS LAYER COMES FIRST

Opportunity is allocated among players who are on the field. A layer that
allocates targets without first establishing who is playing has to assume
participation, and an assumed participation is the quietest possible way to
hand a player a workload. So this runs before allocation and its output is the
denominator allocation is permitted to divide.

THE BUDGET IS STRUCTURAL AND IT IS MEASURED, NOT CHOSEN

Eleven players are on the field for every offensive snap. Five are linemen and
one is the quarterback, so the non-QB skill positions share five. Measured
over the 32 team-games of 2026 week 1:

    all positions        11.0022  sd 0.0096
    quarterbacks          1.0003  sd 0.0017
    non-QB skill          4.9678  sd 0.0439   (min 4.82, max 5.01)

The 0.032 deficit against a nominal 5 is six-lineman personnel, and the spread
is what varies between clubs. So the budget is not a constant this file picked:
it is re-estimated from whatever weeks the capture holds, and the sd travels
with it so a caller can see how tightly it binds.

WHAT HAPPENS TO A PLAYER WHOSE ROLE IS UNKNOWN, AND WHY IT IS NOT A SHARE

A club whose room contains ROLE_UNCERTAIN players cannot have its budget closed
by the players who ARE measured, because the unknown players will take snaps
and nobody knows how many. There are two ways to respond. One is to distribute
the leftover among the unknown players by some rule, which is the cold start
that put a linebacker in a lead back's chair. The other is to refuse to
distribute it and NAME it.

This file names it. `unresolved_participation_mass` is the part of a club's
five-man budget that measured participation does not account for. It is not
allocated, not smoothed, and not hidden: it is the exact size of what the
system does not know about that club's offence, in units a reader understands
(1.0 = one full-time player's worth of snaps).

That number then decides whether anything downstream may be published, which
is the whole point of computing it.

WHAT THIS LAYER DOES NOT DO

It produces no target, carry, dropback or fantasy point. It does not widen or
narrow anyone's share to make a club close. A club that does not close stays
open and says by how much.

DISPERSION IS NOT IDENTIFIED HERE AND THE FILE SAYS SO

A player's week-to-week variation in snap share needs at least two observed
weeks of him. The lawful capture holds one. So this layer emits an expected
share and an explicit `dispersion_state = UNIDENTIFIED_FROM_ONE_WEEK`; it does
not manufacture an interval from between-player spread, which is a different
quantity and would be wrong in a direction nobody could audit.
"""
from __future__ import annotations

import collections
import statistics
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import governed_thresholds as GT      # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from sportsplatform.governance.outcome import (                    # noqa: E402
    Cause, Outcome)

SPEC_VERSION = 'nfl-participation-budget-1'

#: Positions that share the non-QB skill budget. QB is budgeted separately
#: because exactly one is on the field, which is a different kind of fact.
SKILL_NONQB = ('RB', 'FB', 'HB', 'WR', 'TE')
QB = 'QB'

RESOLVED = 'PARTICIPATION_RESOLVED'
INCOMPLETE = 'PARTICIPATION_INCOMPLETE'
UNSUPPORTED = 'PARTICIPATION_UNSUPPORTED'

DISPERSION_UNIDENTIFIED = 'UNIDENTIFIED_FROM_ONE_WEEK'
DISPERSION_MEASURED = 'MEASURED_WITHIN_PLAYER'


def measure_budget(snap_rows) -> Outcome:
    """The five-man budget and the one-QB budget, re-estimated from the capture.

    Nothing is assumed. If the measured all-position total is not close to
    eleven the capture is not what this file thinks it is, and the right
    answer is to refuse rather than to divide by a number that does not mean
    what its name says.
    """
    by = collections.defaultdict(lambda: collections.Counter())
    for r in snap_rows:
        pct = RS._f(r.get('offense_pct'))
        if pct is None:
            continue
        pos = (r.get('position') or '').upper()
        k = (r.get('team'), r.get('week'))
        by[k]['all'] += pct
        if pos == QB:
            by[k]['qb'] += pct
        elif pos in SKILL_NONQB:
            by[k]['skill'] += pct
    if not by:
        return Outcome.blocked(
            'PARTICIPATION_BUDGET_NO_ROWS',
            'no snap row carries an offensive percentage, so the budget '
            'cannot be measured and there is no default to fall back on.',
            cause=Cause.DATA)
    allv = [v['all'] for v in by.values()]
    qbv = [v['qb'] for v in by.values()]
    skv = [v['skill'] for v in by.values()]
    mean_all = statistics.fmean(allv)
    # ELEVEN IS THE GAME, NOT A PARAMETER. If the measured total is not
    # eleven the column does not mean what the schema says, and every budget
    # below would be a ratio of two misunderstood quantities.
    if abs(mean_all - 11.0) > 0.25:
        return Outcome.fail(
            'PARTICIPATION_BUDGET_NOT_ELEVEN_ON_FIELD',
            f'the measured all-position snap share sums to {mean_all:.4f} per '
            f'team-game against the eleven players football puts on the field. '
            f'`offense_pct` therefore does not mean snaps over team plays here, '
            f'and every share derived from it would be wrong in an '
            f'unauditable way.',
            cause=Cause.DATA, mean_all_positions=mean_all,
            n_team_games=len(by))
    val = {
        'skill_nonqb_budget': statistics.fmean(skv),
        'skill_nonqb_sd': statistics.pstdev(skv),
        'qb_budget': statistics.fmean(qbv),
        'qb_sd': statistics.pstdev(qbv),
        'all_positions': mean_all,
        'all_positions_sd': statistics.pstdev(allv),
        'n_team_games': len(by),
    }
    return Outcome.ok(
        'PARTICIPATION_BUDGET_MEASURED', value=val,
        derivation=('mean over team-games of the summed offense_pct, by '
                    'position group. Eleven on the field less five linemen '
                    'less one quarterback is the structure; the deficit '
                    'against a nominal five is six-lineman personnel and is '
                    'measured, not assumed.'),
        detail=f'non-QB skill budget {val["skill_nonqb_budget"]:.4f} '
               f'sd {val["skill_nonqb_sd"]:.4f} over {len(by)} team-game(s)')


def assess(role_rows, *, budget=None, snap_rows=None) -> Outcome:
    """Expected participation per player and the unresolved mass per club.

    A player with measured participation carries his own measured share. A
    player without it carries NO share -- not a zero, not an anchor -- and his
    room's share of the budget stays open by exactly that much.
    """
    if budget is None:
        if snap_rows is None:
            return Outcome.blocked(
                'PARTICIPATION_NO_BUDGET_SOURCE',
                'neither a measured budget nor the snap rows to measure one '
                'were supplied.', cause=Cause.DEPENDENCY)
        bo = measure_budget(snap_rows)
        if bo.state.name != 'PASS':
            return bo
        budget, bev = bo.value, bo.evidence
    else:
        bev = {'supplied_by_caller': True}

    rows, by_club = [], collections.defaultdict(list)
    for r in role_rows:
        pos_room = r.get('room')
        if pos_room not in (RS.ROOM_CARRIES, RS.ROOM_TARGETS,
                            RS.ROOM_DROPBACKS):
            continue                                # kickers take no snaps
        snaps = r['evidence']['current_season_snaps']
        share = snaps.get('mean_offense_pct')
        n = snaps.get('n_games_at_this_club') or 0
        if share is None:
            state, why = UNSUPPORTED, (
                'no measured offensive participation at this club, and the '
                'alternative -- an anchor from his listing -- is the cold '
                'start this layer exists to refuse')
        elif r['role_support'] == RS.ROLE_UNSUPPORTED:
            state, why = UNSUPPORTED, (
                f'participation was measured ({share:.4f}) but the role it '
                f'sits in is not established: '
                f'{", ".join(r["role_unsupported_why"])}')
        else:
            state, why = RESOLVED, (
                f'{share:.4f} of his club\'s offensive snaps, measured over '
                f'{n} game(s)')
        row = {
            'game_id': r.get('game_id'), 'team': r['team'],
            'gsis_id': r['gsis_id'], 'display_name': r.get('display_name'),
            'room': pos_room, 'role': r['role'],
            'role_support': r['role_support'],
            'expected_snap_share': share if state == RESOLVED else None,
            'measured_snap_share': share,
            'n_observed_games': n,
            'participation_state': state,
            'participation_why': why,
            'dispersion_state': (DISPERSION_MEASURED if n >= 2
                                 else DISPERSION_UNIDENTIFIED),
            'dispersion_why': (
                'week-to-week variation in a player\'s own snap share needs '
                'at least two observed weeks of him. Between-player spread '
                'is a different quantity and is not substituted.'),
            'p_meaningful_participation': None,
            'p_meaningful_why': (
                'a probability of taking at least one offensive snap needs a '
                'repeated-observation base rate this capture does not carry. '
                'It is left unset rather than filled with a share, which is '
                'a different quantity.'),
        }
        rows.append(row)
        by_club[r['team']].append(row)

    clubs = {}
    for club, rs in sorted(by_club.items()):
        nonqb = [x for x in rs if x['room'] != RS.ROOM_DROPBACKS]
        qbs = [x for x in rs if x['room'] == RS.ROOM_DROPBACKS]
        acc = sum(x['expected_snap_share'] for x in nonqb
                  if x['expected_snap_share'] is not None)
        qacc = sum(x['expected_snap_share'] for x in qbs
                   if x['expected_snap_share'] is not None)
        unresolved = budget['skill_nonqb_budget'] - acc
        frac = (unresolved / budget['skill_nonqb_budget']
                if budget['skill_nonqb_budget'] else None)
        clubs[club] = {
            'budget': budget['skill_nonqb_budget'],
            'budget_sd': budget['skill_nonqb_sd'],
            'accounted_nonqb': acc,
            'unresolved_participation_mass': unresolved,
            'unresolved_fraction_of_budget': frac,
            'unresolved_means': (
                'full-time players\' worth of offensive snaps that measured, '
                'role-supported participation does not account for. 1.0 is '
                'one player on the field for every snap. It is NOT allocated.'),
            'qb_budget': budget['qb_budget'],
            'accounted_qb': qacc,
            'n_players': len(rs),
            'n_resolved': sum(1 for x in rs
                              if x['participation_state'] == RESOLVED),
            'n_unsupported': sum(1 for x in rs
                                 if x['participation_state'] == UNSUPPORTED),
            'unsupported_players': [
                {'display_name': x['display_name'], 'role': x['role'],
                 'measured_snap_share': x['measured_snap_share'],
                 'why': x['participation_why']}
                for x in rs if x['participation_state'] == UNSUPPORTED],
            # THERE IS NO TOLERANCE IN THIS FILE, DELIBERATELY. A club
            # closes when measured participation accounts for the whole
            # budget and not otherwise. Comparing the residual against the
            # league total's sd, which the first draft did, compares two
            # different quantities: one is how much clubs differ from each
            # other, the other is how much of THIS club we failed to
            # reconstruct. How much unreconstructed mass is acceptable is a
            # decision belonging to whoever divides by the denominator, and
            # it is taken in `assert_participation_supports_allocation`
            # where it must be declared and is recorded.
            'state': RESOLVED if abs(unresolved) == 0.0 else INCOMPLETE,
        }

    open_clubs = [c for c, v in clubs.items() if v['state'] != RESOLVED]
    ev = dict(
        spec_version=SPEC_VERSION, budget=budget, budget_evidence=bev,
        clubs=clubs, n_rows=len(rows),
        clubs_open=open_clubs,
        dispersion_state=DISPERSION_UNIDENTIFIED,
        summary=f'{len(rows)} participation row(s) across {len(clubs)} '
                f'club(s); {len(open_clubs)} club(s) do not close within the '
                f'measured budget sd')
    if open_clubs:
        worst = max(clubs.items(),
                    key=lambda kv: abs(kv[1]['unresolved_participation_mass']))
        return Outcome.blocked(
            'PARTICIPATION_INCOMPLETE',
            f'{len(open_clubs)} club(s) do not close their five-man snap '
            f'budget from measured, role-supported participation alone. The '
            f'largest gap is {worst[0]} at '
            f'{worst[1]["unresolved_participation_mass"]:+.4f} full-time '
            f'players\' worth of snaps '
            f'({worst[1]["unresolved_fraction_of_budget"]:.1%} of the '
            f'budget), unallocated by design: distributing it among players '
            f'whose role is unknown is the cold start this layer refuses. '
            f'Whether that much unreconstructed mass is acceptable is the '
            f'allocator\'s declaration to make, not this layer\'s.',
            cause=Cause.DATA, value=rows, **ev)
    return Outcome.ok('PARTICIPATION_RESOLVED', value=rows, **ev)


def assert_participation_supports_allocation(
        part_outcome, *, allocating_ids=None,
        max_unresolved_fraction=None) -> Outcome:
    """The gate. Allocation may divide only a denominator that is established.

    `allocating_ids` is the set the opportunity layer intends to allocate
    among. None means no consumer declared one, which BLOCKS rather than
    passing, for the same reason the role and coverage gates do.

    `max_unresolved_fraction` is how much of a club's snap budget may be
    carried unreconstructed. It is NOT the caller's to choose. The caller may
    pass one, and it is then treated as a CANDIDATE tolerance: the gate
    computes and reports against it and returns a non-passing state, so the
    verdict machine reads RESEARCH_ONLY.

    THIS IS THE CORRECTION OF 2026-09-21. The gate previously passed on any
    number the caller supplied, so New York's 21.1% unresolved mass cleared
    against a 25% figure with no justification whatsoever. That reproduced the
    exact pattern this project is eliminating: BLOCKED, but below our chosen
    tolerance, therefore PASS. A threshold nobody has validated certifies
    nothing, and the number that decides what passes must not be settable at
    the call site that wants it to pass.

    Only `governed_thresholds.PARTICIPATION_UNRESOLVED_FRACTION` marked
    PRODUCTION_CERTIFIED can clear this gate. Today none is.
    """
    rows = part_outcome.value or (part_outcome.evidence or {}).get('value') \
        or []
    ev = part_outcome.evidence or {}
    clubs = ev.get('clubs') or {}
    idx = {r['gsis_id']: r for r in rows}
    unsupported = {r['gsis_id'] for r in rows
                   if r['participation_state'] == UNSUPPORTED}
    gov = GT.PARTICIPATION_UNRESOLVED_FRACTION
    governed = gov['max_unresolved_fraction']
    certification = gov['certification']
    # The governed value is what applies. A caller-supplied number is recorded
    # as what it is -- a proposal -- and never replaces it.
    applied = governed
    proposed = max_unresolved_fraction
    if allocating_ids is None:
        missing = ['allocating_ids']
        return Outcome.blocked(
            'NO_ALLOCATING_DECLARATION',
            f'{len(rows)} participation row(s) exist and {len(unsupported)} '
            f'are unsupported, but no allocator declared whom it will divide '
            f'opportunity among. A PASS here would certify a denominator '
            f'nobody named.',
            cause=Cause.GOVERNANCE, n_rows=len(rows),
            n_unsupported=len(unsupported), missing_declarations=missing,
            club_unresolved={c: v['unresolved_fraction_of_budget']
                             for c, v in clubs.items()})
    offenders = [idx[p] for p in sorted(set(allocating_ids)) if p in unsupported]
    in_play = sorted({idx[p]['team'] for p in allocating_ids if p in idx})
    open_clubs = sorted(
        c for c in in_play
        if abs((clubs.get(c) or {}).get('unresolved_fraction_of_budget') or
               0.0) > applied)
    tol_ev = {
        'governed_max_unresolved_fraction': governed,
        'governed_certification': certification,
        'caller_proposed_max_unresolved_fraction': proposed,
        'applied_max_unresolved_fraction': applied,
        'caller_proposal_was_not_applied': (
            proposed is not None and proposed != applied),
        'club_unresolved_fraction': {
            c: (clubs.get(c) or {}).get('unresolved_fraction_of_budget')
            for c in in_play},
    }

    # A CANDIDATE tolerance cannot clear the gate however wide the margin.
    if not GT.is_clearing(certification) and not offenders and not open_clubs:
        return Outcome.blocked(
            'PARTICIPATION_TOLERANCE_NOT_CERTIFIED',
            f'every club in the allocating set is within the governed '
            f'tolerance of {governed:.1%}, but that tolerance is '
            f'{certification}, not PRODUCTION_CERTIFIED. Passing on it would '
            f'certify a board against a standard nobody has shown to mean '
            f'anything. What certification needs: '
            f'{gov["certification_requires"]}',
            cause=Cause.GOVERNANCE,
            certification_requires=gov['certification_requires'], **tol_ev)
    if offenders or open_clubs:
        return Outcome.fail(
            'PARTICIPATION_DOES_NOT_SUPPORT_ALLOCATION',
            f'{len(offenders)} player(s) with unestablished participation '
            f'would receive opportunity, and {len(open_clubs)} club(s) in '
            f'the allocating set carry more unreconstructed snap mass than '
            f'the governed tolerance of {applied:.1%}. '
            f'Dividing a total among players whose presence is unknown '
            f'assigns the unknown a number, which is the defect, not the '
            f'workaround.',
            cause=Cause.DATA, **tol_ev,
            offending=[{'gsis_id': r['gsis_id'],
                        'display_name': r['display_name'],
                        'team': r['team'], 'role': r['role'],
                        'why': r['participation_why']} for r in offenders],
            open_clubs=[{'club': c,
                         'unresolved_participation_mass':
                             clubs[c]['unresolved_participation_mass'],
                         'unresolved_fraction_of_budget':
                             clubs[c]['unresolved_fraction_of_budget'],
                         'unsupported_players':
                             clubs[c]['unsupported_players']}
                        for c in open_clubs])
    return Outcome.ok(
        'PARTICIPATION_SUPPORTS_ALLOCATION',
        value={'n_allocating': len(set(allocating_ids)),
               'n_withheld': len(unsupported), **tol_ev},
        certified=True, **tol_ev,
        detail=f'{len(set(allocating_ids))} player(s) may be allocated among; '
               f'{len(unsupported)} withheld for unestablished participation')
