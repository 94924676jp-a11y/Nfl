"""Compositional opportunity allocation, conserving the team total exactly.

WHAT A SHARE IS HERE

A club throws its targets to somebody. The shares of a room therefore sum to
one by construction, and any layer that produces per-player shares which do not
is losing or inventing opportunity. This module allocates compositionally: the
composition is the object, the individual share is a coordinate of it, and the
sum is checked rather than hoped for.

THE THREE THINGS THAT CAN GO WRONG, AND WHAT IS DONE ABOUT EACH

1. A PLAYER WITH NO ESTABLISHED PARTICIPATION RECEIVES OPPORTUNITY.
   He does not. Allocation runs only over the set participation resolved, and
   the gate refuses a consumer that widens it.

2. THE MEASURED SHARES DO NOT COVER THE WHOLE ROOM.
   Some of last week's targets went to players who are no longer expected to
   play, or whose role is not established. Renormalising the survivors to one
   silently gives them that mass. So BOTH compositions are published: the raw
   `share_of_measured`, which sums to the retained mass, and
   `share_renormalised`, which sums to one -- with `reassigned_mass` attached
   and the assumption stated in words. A reader can see exactly how much of
   each player's number is his own measurement and how much is inheritance.

3. THE COMPOSITION IS MORE CONCENTRATED THAN THE MODEL SHOULD BELIEVE.
   Concentration is reported, not assumed: top-1, top-2, top-3, the
   Herfindahl index, Shannon entropy and the effective number of players
   (1/HHI). Each is placed against the LEAGUE distribution of the same
   statistic computed from the same blob, so "this club is unusually
   concentrated" is a comparison against thirty-two measured clubs rather than
   against a number somebody felt was right.

WHAT THIS MODULE DOES NOT DO

It does not smooth a share toward a room mean, regress it toward a prior,
widen it for uncertainty or bound it. One observed week is one observed week,
and a shrinkage constant chosen here would be a fitted constant. What it does
instead is report `n_observed_games` beside every share so a consumer knows
the evidence is thin, and refuse to be the layer that hides it.

It reads no price, no salary, no ownership figure and no realised outcome for
the game being forecast.
"""
from __future__ import annotations

import collections
import math
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import participation as PA            # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from sportsplatform.governance.outcome import (                    # noqa: E402
    Cause, Outcome)

SPEC_VERSION = 'nfl-compositional-allocation-1'

#: room -> the measured share column that room divides.
ROOM_SHARE = {
    RS.ROOM_TARGETS: 'target_share',
    RS.ROOM_CARRIES: 'carry_share',
}
ROOM_COUNT = {
    RS.ROOM_TARGETS: 'targets',
    RS.ROOM_CARRIES: 'carries',
}

ALLOCATED = 'ALLOCATION_RESOLVED'
NO_EVIDENCE = 'ALLOCATION_NO_MEASURED_SHARE'


def concentration(shares) -> dict:
    """Top-k, Herfindahl, entropy and effective players, on one composition.

    Defined on a composition that sums to one. Entropy is in nats and is
    reported beside its maximum for the room size, because entropy alone is
    not comparable between rooms of different sizes.
    """
    s = sorted((x for x in shares if x is not None and x > 0), reverse=True)
    n = len(s)
    if not n:
        return {'n': 0, 'top1': None, 'top2': None, 'top3': None,
                'hhi': None, 'entropy_nats': None, 'entropy_max_nats': None,
                'entropy_ratio': None, 'effective_players': None}
    tot = sum(s)
    p = [x / tot for x in s]
    hhi = sum(x * x for x in p)
    ent = -sum(x * math.log(x) for x in p if x > 0)
    emax = math.log(n) if n > 1 else 0.0
    return {
        'n': n,
        'top1': p[0],
        'top2': sum(p[:2]),
        'top3': sum(p[:3]),
        'hhi': hhi,
        'entropy_nats': ent,
        'entropy_max_nats': emax,
        'entropy_ratio': (ent / emax) if emax > 0 else None,
        'effective_players': 1.0 / hhi if hhi > 0 else None,
    }


def league_concentration(usage_rows, room) -> Outcome:
    """The same statistics for every club in the blob: the reference frame.

    A club's concentration means nothing on its own. It means something
    against the league's, and the league's is measured from the same bytes at
    the same cut rather than remembered.
    """
    col = ROOM_SHARE.get(room)
    if col is None:
        return Outcome.not_applicable(
            'ALLOCATION_ROOM_HAS_NO_SHARE_COLUMN',
            f'{room!r} is not a room this module divides.')
    by = collections.defaultdict(list)
    for v in usage_rows.values():
        if v.get(col) is not None:
            by[(v['week'], v['team'])].append(v[col])
    if not by:
        return Outcome.blocked(
            'ALLOCATION_NO_LEAGUE_FRAME',
            f'no club in the corpus carries a {col}, so there is no reference '
            f'distribution and a concentration figure would be uninterpretable.',
            cause=Cause.DATA)
    stats = {k: concentration(v) for k, v in by.items()}
    out = {}
    for key in ('top1', 'top3', 'hhi', 'entropy_ratio', 'effective_players'):
        vals = sorted(s[key] for s in stats.values() if s[key] is not None)
        if not vals:
            continue
        out[key] = {
            'n_club_weeks': len(vals),
            'min': vals[0], 'max': vals[-1],
            'median': statistics.median(vals),
            'mean': statistics.fmean(vals),
            'p10': vals[max(0, int(0.10 * (len(vals) - 1)))],
            'p90': vals[min(len(vals) - 1, int(0.90 * (len(vals) - 1)))],
        }
    return Outcome.ok(
        'ALLOCATION_LEAGUE_FRAME', value=out, room=room,
        n_club_weeks=len(stats),
        detail=f'{len(stats)} club-week(s) of {room} concentration')


def _pct_rank(v, vals):
    if v is None or not vals:
        return None
    return sum(1 for x in vals if x <= v) / len(vals)


def allocate(part_outcome, usage_rows, *, room) -> Outcome:
    """The composition for one room, per club, over the participation-resolved set."""
    col, cnt = ROOM_SHARE.get(room), ROOM_COUNT.get(room)
    if col is None:
        return Outcome.not_applicable(
            'ALLOCATION_ROOM_HAS_NO_SHARE_COLUMN',
            f'{room!r} is not a room this module divides.')
    prows = part_outcome.value or (part_outcome.evidence or {}).get('value') \
        or []
    if not prows:
        return Outcome.blocked(
            'ALLOCATION_NO_PARTICIPATION_ROWS',
            'participation produced no rows, so there is no set to allocate '
            'among.', cause=Cause.DEPENDENCY)

    # Measured share per player, summed over observed weeks weighted by that
    # week's room count -- which is the pooled share, not a mean of shares.
    num = collections.defaultdict(float)
    den = collections.defaultdict(float)
    nobs = collections.Counter()
    club_players = collections.defaultdict(set)
    for (w, club, pid), v in usage_rows.items():
        if v.get(col) is None:
            continue
        team_cnt = v[cnt] / v[col] if v[col] else 0.0
        num[(club, pid)] += v[cnt]
        den[(club, pid)] += team_cnt
        nobs[(club, pid)] += 1
        club_players[club].add(pid)

    lf = league_concentration(usage_rows, room)
    league = lf.value if lf.state.name == 'PASS' else {}
    league_vals = collections.defaultdict(list)
    by_cw = collections.defaultdict(list)
    for v in usage_rows.values():
        if v.get(col) is not None:
            by_cw[(v['week'], v['team'])].append(v[col])
    for k, vs in by_cw.items():
        c = concentration(vs)
        for key in ('top1', 'top3', 'hhi', 'entropy_ratio',
                    'effective_players'):
            if c[key] is not None:
                league_vals[key].append(c[key])

    rows, clubs = [], {}
    in_room = [r for r in prows if r['room'] == room]
    for club in sorted({r['team'] for r in in_room}):
        members = [r for r in in_room if r['team'] == club]
        resolved = [r for r in members
                    if r['participation_state'] == PA.RESOLVED]
        measured, unmeasured = [], []
        for r in resolved:
            k = (club, r['gsis_id'])
            if den[k] > 0:
                measured.append((r, num[k] / den[k], nobs[k]))
            else:
                unmeasured.append(r)
        retained = sum(s for _r, s, _n in measured)
        reassigned = 1.0 - retained if measured else None

        for r, s, n in measured:
            rows.append({
                'game_id': r.get('game_id'), 'team': club, 'room': room,
                'gsis_id': r['gsis_id'],
                'display_name': r.get('display_name'),
                'role': r['role'],
                'expected_snap_share': r['expected_snap_share'],
                'share_of_measured': s,
                'share_renormalised': (s / retained) if retained else None,
                'n_observed_games': n,
                'allocation_state': ALLOCATED,
                'evidence_is_thin': n < 2,
            })
        for r in unmeasured:
            rows.append({
                'game_id': r.get('game_id'), 'team': club, 'room': room,
                'gsis_id': r['gsis_id'],
                'display_name': r.get('display_name'),
                'role': r['role'],
                'expected_snap_share': r['expected_snap_share'],
                'share_of_measured': None, 'share_renormalised': None,
                'n_observed_games': 0,
                'allocation_state': NO_EVIDENCE,
                'why': (f'participation is established but he took no '
                        f'{room} opportunity in any observed week, so his '
                        f'share is unmeasured. It is not set to zero: a '
                        f'player can be on the field without a target and '
                        f'the two are different facts.'),
                'evidence_is_thin': True,
            })

        comp = concentration([s for _r, s, _n in measured])
        clubs[club] = {
            'room': room,
            'n_participation_resolved': len(resolved),
            'n_with_measured_share': len(measured),
            'n_without_measured_share': len(unmeasured),
            'retained_share_mass': retained,
            'reassigned_mass': reassigned,
            'renormalisation_assumption': (
                'share_renormalised divides each retained share by the '
                'retained total, which gives the survivors the opportunity '
                'that went to players no longer in the set, in proportion to '
                'what they already had. That is an assumption, not a '
                'measurement. share_of_measured carries the unassumed '
                'number and reassigned_mass is exactly how much separates '
                'them.'),
            'concentration': comp,
            'concentration_vs_league': {
                k: {'value': comp.get(k),
                    'league_median': (league.get(k) or {}).get('median'),
                    'league_p10': (league.get(k) or {}).get('p10'),
                    'league_p90': (league.get(k) or {}).get('p90'),
                    'percentile_in_league': _pct_rank(comp.get(k),
                                                      league_vals.get(k, []))}
                for k in ('top1', 'top3', 'hhi', 'entropy_ratio',
                          'effective_players')},
        }

    return Outcome.ok(
        'ALLOCATION_COMPOSED', value=rows,
        spec_version=SPEC_VERSION, room=room,
        n_rows=len(rows), clubs=clubs,
        league_frame=league, league_frame_state=lf.code,
        no_shrinkage_note=(
            'no share is smoothed, regressed or bounded here. One observed '
            'week is one observed week, and a shrinkage constant chosen in '
            'this file would be a fitted constant. n_observed_games travels '
            'with every share instead.'),
        detail=f'{len(rows)} {room} row(s) across {len(clubs)} club(s)')


def assert_allocation_conserves(alloc_outcome, *,
                                consuming_ids=None) -> Outcome:
    """The gate. The composition sums to one and nobody outside the set is in it.

    `consuming_ids` is whom the downstream layer will read. None BLOCKS, for
    the same reason as the role and participation gates: a composition nobody
    declared a use for cannot be certified against anything.
    """
    rows = alloc_outcome.value or []
    ev = alloc_outcome.evidence or {}
    clubs = ev.get('clubs') or {}
    problems = []
    for club, v in clubs.items():
        s = sum(r['share_renormalised'] for r in rows
                if r['team'] == club and r['share_renormalised'] is not None)
        if v['n_with_measured_share'] and abs(s - 1.0) > 1e-9:
            problems.append({'club': club, 'kind': 'COMPOSITION_NOT_UNIT',
                             'sum': s})
        if v['reassigned_mass'] is not None and v['reassigned_mass'] < -1e-9:
            problems.append({'club': club, 'kind': 'NEGATIVE_REASSIGNED_MASS',
                             'reassigned_mass': v['reassigned_mass']})
    if problems:
        return Outcome.fail(
            'ALLOCATION_DOES_NOT_CONSERVE',
            f'{len(problems)} club composition(s) do not conserve. A room '
            f'whose shares do not sum to one has lost or invented '
            f'opportunity, and every number derived from it inherits that.',
            cause=Cause.DATA, offending=problems)
    if consuming_ids is None:
        return Outcome.blocked(
            'NO_CONSUMING_SET_DECLARED',
            f'{len(rows)} allocation row(s) conserve, but no downstream layer '
            f'declared which players it will read. A composition nobody '
            f'declared a use for cannot be certified against anything.',
            cause=Cause.GOVERNANCE, n_rows=len(rows),
            clubs={c: {'reassigned_mass': v['reassigned_mass'],
                       'n_without_measured_share':
                           v['n_without_measured_share']}
                   for c, v in clubs.items()})
    allocated = {r['gsis_id'] for r in rows
                 if r['allocation_state'] == ALLOCATED}
    outside = sorted(set(consuming_ids) - allocated)
    if outside:
        idx = {r['gsis_id']: r for r in rows}
        return Outcome.fail(
            'CONSUMER_READS_OUTSIDE_THE_COMPOSITION',
            f'{len(outside)} player(s) the consumer intends to read carry no '
            f'allocated share. Reading a player the composition does not '
            f'contain means the number comes from somewhere this layer did '
            f'not put it.',
            cause=Cause.DATA,
            offending=[{'gsis_id': p,
                        'display_name': (idx.get(p) or {}).get('display_name'),
                        'allocation_state':
                            (idx.get(p) or {}).get('allocation_state',
                                                   'NOT_IN_ROOM')}
                       for p in outside])
    return Outcome.ok(
        'ALLOCATION_CONSERVES',
        value={'n_consuming': len(set(consuming_ids)),
               'clubs': {c: {'reassigned_mass': v['reassigned_mass']}
                         for c, v in clubs.items()}},
        certified=True,
        detail=f'{len(clubs)} composition(s) sum to one; '
               f'{len(set(consuming_ids))} player(s) read from inside them')
