#!/usr/bin/env python3.12
"""Point-in-time role state for a PAST week, so the live role-state mechanism becomes testable.

WHAT WAS MISSING. `forward_chain.historical_band` says it outright: "Role state is not
reconstructible for a historical week ... the evidence CEILING cannot be applied here ... the chain
does NOT test the appearance adjustment or the starter cap." So the two things that matter most about
the live role state -- the hard cap that stops an injury-replacement share outliving the injury, and
the position-scoped depth rank -- were asserted in production and never measured anywhere.

A second, quieter gap sat next to it. `historical_band` is computed at `through = season - 1`, which
makes the band SEASON-CONSTANT: a player promoted in week 4 carries his previous season's band
through week 18, and a player who lost his job keeps it too. The live path updates weekly. So the
chain was not even testing the band assignment production uses.

WHY ROLE_HISTORY CANNOT BE READ DIRECTLY, and this is the trap. `ROLE_HISTORY` already carries
`depth`, `depth_rank` and `transition` per season-week-player, and its rank is position-scoped inside
the club-week, which is what production wanted. It is still unusable as a pregame state, because
`role_history.build` ranks players by THAT WEEK'S OWN usage measure: the rank for week W is a
description of what happened in week W. Feeding it in as a week-W input is direct outcome leakage. It
is a realised role, not a predicted one, and the names look identical.

SO THE RANK IS REBUILT FROM PRIOR WEEKS ONLY. Everything here reads weeks strictly before the scored
week, which `assert_no_leakage` re-derives rather than trusts.

TWO ARMS, AND THE SECOND ONE IS AN ORACLE AND IS LABELLED AS ONE.

    PREGAME             availability is unknown, as it is on a real Sunday morning minus the injury
                        report. A club's starter at a position is whoever led it in the most recent
                        prior week. If that player is in fact out, this arm does not know.
    ORACLE_AVAILABILITY who actually appeared in the scored week is fed in, so the cap fires on the
                        right player. This measures the cap's MECHANISM given correct availability.
                        It is not live performance and must never be quoted as such. It is the same
                        oracle condition as feeding a simulator the actual batting order.

The gap between the two arms is the value of knowing who is out -- which is exactly what an injury
report buys, and this repository holds none for past Sundays (OUT-038). Reporting both separates
"the cap is the wrong idea" from "the cap is right and we cannot see who is injured".
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

#: The usage measure that defines depth at each position, matching role_history's own choice.
DEPTH_MEASURE = {'RB': 'carries', 'WR': 'targets', 'TE': 'targets', 'QB': 'pass_attempts'}

#: Band ceilings by pregame depth rank within club and position. The live module's mechanism: a
#: player who is not his club's starter at his position cannot be ASKED about ALPHA or PRIMARY,
#: whatever his own history says.
RANK_CEILING = {1: 'ALPHA', 2: 'SECONDARY', 3: 'ROTATIONAL'}
CEILING_BEYOND_RANK_3 = 'FRINGE'

TIER_ORDER = ('FRINGE', 'ROTATIONAL', 'SECONDARY', 'PRIMARY', 'ALPHA')

#: How many prior weeks of the current season define the pregame depth ordering. DECLARED, not
#: fitted: role_history uses the same lookback for its transition labels, and a single prior week
#: would make one rested starter look like a demotion.
LOOKBACK_WEEKS = 3

ARM_PREGAME = 'PREGAME'
ARM_ORACLE = 'ORACLE_AVAILABILITY'

AVAILABILITY_UNAVAILABLE = (
    'no injury or inactive report exists in this checkout for a past Sunday (OUT-038), so the '
    'PREGAME arm cannot know who is out. It is not proxied by who actually played: that is the '
    'ORACLE arm, kept separate and labelled.')


def _cap(band, ceiling):
    return band if TIER_ORDER.index(band) <= TIER_ORDER.index(ceiling) else ceiling


def pregame_depth(panel, pos_of, season, week, *, appeared=None):
    """Depth rank within club and position, from weeks STRICTLY BEFORE `week`.

    `appeared` is the ORACLE: a set of player ids known to have played in the scored week. When it
    is given, a prior leader who did not play is skipped so the cap falls on the man behind him.
    When it is None the arm is pregame and does not know.
    """
    usage = collections.defaultdict(float)
    club_of = {}
    for gsis, seasons in panel['players'].items():
        pos = pos_of.get(gsis)
        if pos not in DEPTH_MEASURE:
            continue
        meas = DEPTH_MEASURE[pos]
        wk = (seasons.get(str(season)) or {})
        for w, row in wk.items():
            iw = int(w)
            if iw >= week or iw < week - LOOKBACK_WEEKS:
                continue
            usage[gsis] += float(row.get(meas) or 0.0)
            club_of[gsis] = row.get('team') or club_of.get(gsis)
    groups = collections.defaultdict(list)
    for gsis, tot in usage.items():
        club = club_of.get(gsis)
        if not club:
            continue
        groups[(club, pos_of.get(gsis))].append((tot, gsis))
    out = {}
    for (club, pos), members in groups.items():
        members.sort(key=lambda t: (-t[0], t[1]))
        rank = 0
        for tot, gsis in members:
            if tot <= 0:
                out[gsis] = {'club': club, 'position': pos, 'pregame_rank': None,
                             'prior_usage': 0.0, 'ceiling': CEILING_BEYOND_RANK_3,
                             'ceiling_source': 'NO_PRIOR_USAGE_IN_LOOKBACK'}
                continue
            if appeared is not None and gsis not in appeared:
                # ORACLE ONLY. A prior leader who did not play this week does not hold the slot,
                # so he is not ranked and the man behind him moves up.
                out[gsis] = {'club': club, 'position': pos, 'pregame_rank': None,
                             'prior_usage': tot, 'ceiling': CEILING_BEYOND_RANK_3,
                             'ceiling_source': 'ORACLE_DID_NOT_APPEAR'}
                continue
            rank += 1
            out[gsis] = {'club': club, 'position': pos, 'pregame_rank': rank,
                         'prior_usage': tot,
                         'ceiling': RANK_CEILING.get(rank, CEILING_BEYOND_RANK_3),
                         'ceiling_source': f'PREGAME_RANK_{rank}_IN_CLUB_POSITION'}
    return out


def weekly_band(panel, pos_of, gsis, pos, season, week, historical_band_fn):
    """The stronger of the season-entry band and what prior weeks of THIS season show.

    The live module takes the stronger of history and current usage so that neither a demoted
    starter stays alpha nor a star has two quiet games cost him his band. The chain took history
    alone, at season granularity. This adds the current-season half, still pregame.
    """
    hist = historical_band_fn(panel, pos_of, gsis, pos, season - 1)
    meas = DEPTH_MEASURE.get(pos)
    if not meas:
        return hist, 'HISTORY_ONLY_POSITION_HAS_NO_DEPTH_MEASURE'
    wk = (panel['players'].get(gsis) or {}).get(str(season)) or {}
    prior = [(int(w), r) for w, r in wk.items() if int(w) < week]
    if not prior:
        return hist, 'HISTORY_ONLY_NO_PRIOR_WEEKS_THIS_SEASON'
    club = None
    tot = 0.0
    for _w, r in prior:
        tot += float(r.get(meas) or 0.0)
        club = r.get('team') or club
    club_tot = 0.0
    tm = (panel['teams'].get(club) or {}).get(str(season)) or {}
    team_field = {'carries': 'rush_attempts', 'targets': 'targets',
                  'pass_attempts': 'pass_attempts'}[meas]
    for w, r in tm.items():
        if int(w) < week:
            club_tot += float(r.get(team_field) or 0.0)
    if club_tot <= 0:
        return hist, 'HISTORY_ONLY_CLUB_VOLUME_ZERO'
    share = tot / club_tot
    # the same share thresholds role_state uses for an observed band, declared there
    observed = ('ALPHA' if share >= 0.25 else 'PRIMARY' if share >= 0.18
                else 'SECONDARY' if share >= 0.10 else 'ROTATIONAL' if share >= 0.04
                else 'FRINGE')
    stronger = max((hist, observed), key=lambda b: TIER_ORDER.index(b))
    return stronger, ('OBSERVED_STRONGER' if stronger == observed and observed != hist
                      else 'HISTORY_STRONGER' if stronger == hist and observed != hist
                      else 'AGREE')


def role_state_for_week(panel, pos_of, season, week, historical_band_fn, *, arm=ARM_PREGAME,
                        appeared=None) -> Outcome:
    """The reconstructed state for one past week. Returns per-player band, ceiling and capped band."""
    if arm == ARM_ORACLE and appeared is None:
        return Outcome.fail(
            'ORACLE_ARM_WITHOUT_ORACLE',
            'the ORACLE_AVAILABILITY arm was asked for without the set of players who appeared. '
            'Silently running it as PREGAME would label a pregame result as an oracle one.')
    if arm == ARM_PREGAME and appeared is not None:
        return Outcome.fail(
            'PREGAME_ARM_GIVEN_THE_OUTCOME',
            'the PREGAME arm was handed the appearance set for the scored week. That is the leak '
            'this module exists to make impossible, so it is refused rather than ignored.')
    depth = pregame_depth(panel, pos_of, season, week,
                          appeared=(appeared if arm == ARM_ORACLE else None))
    rows, counts = {}, collections.Counter()
    for gsis, d in depth.items():
        pos = d['position']
        band, why = weekly_band(panel, pos_of, gsis, pos, season, week, historical_band_fn)
        capped = _cap(band, d['ceiling'])
        counts['capped' if capped != band else 'uncapped'] += 1
        counts[f'band_{capped}'] += 1
        rows[gsis] = {**d, 'band_before_cap': band, 'band_source': why,
                      'role_band': capped, 'was_capped': capped != band}
    if not rows:
        return Outcome.blocked(
            'NO_PREGAME_ROLE_STATE',
            f'{season} week {week} produced no pregame role state, which for a week after the '
            f'lookback window is an error rather than an empty slate',
            cause=Cause.DATA)
    return Outcome.ok('PREGAME_ROLE_STATE', value={
        'season': season, 'week': week, 'arm': arm,
        'n_players': len(rows),
        'AVAILABILITY': (AVAILABILITY_UNAVAILABLE if arm == ARM_PREGAME
                         else 'ORACLE: who appeared in the scored week was supplied'),
        'counts': dict(counts), 'rows': rows})


def assert_no_leakage(panel, pos_of, season, week, historical_band_fn) -> Outcome:
    """Re-derive the state with the scored week and everything after it DELETED. It must not move.

    This is the check that makes the pregame claim mean something. A reconstruction that reads the
    scored week would produce a different answer once that week is gone, and an assertion in a
    docstring would not notice.
    """
    full = role_state_for_week(panel, pos_of, season, week, historical_band_fn)
    if full.state.name != 'PASS':
        return full
    trimmed = {'players': {}, 'teams': {}}
    for g, ss in panel['players'].items():
        trimmed['players'][g] = {
            s: {w: r for w, r in ws.items() if not (int(s) == season and int(w) >= week)}
            for s, ws in ss.items() if int(s) <= season}
    for c, ss in panel['teams'].items():
        trimmed['teams'][c] = {
            s: {w: r for w, r in ws.items() if not (int(s) == season and int(w) >= week)}
            for s, ws in ss.items() if int(s) <= season}
    cut = role_state_for_week(trimmed, pos_of, season, week, historical_band_fn)
    if cut.state.name != 'PASS':
        return cut
    a, b = full.value['rows'], cut.value['rows']
    moved = [{'player_id': g, 'with_future': a[g]['role_band'], 'without_future': b[g]['role_band']}
             for g in set(a) & set(b)
             if a[g]['role_band'] != b[g]['role_band']
             or a[g]['pregame_rank'] != b[g]['pregame_rank']]
    only = sorted(set(a) ^ set(b))
    if moved or only:
        return Outcome.fail(
            'PREGAME_ROLE_STATE_READS_THE_FUTURE',
            f'{len(moved)} players change band or rank and {len(only)} appear on only one side when '
            f'week {week} of {season} and everything after it is deleted from the panel',
            moved=moved[:8], only_one_side=only[:8])
    return Outcome.ok('PREGAME_ROLE_STATE_IS_POINT_IN_TIME', value={
        'season': season, 'week': week, 'n_players_checked': len(set(a) & set(b)),
        'METHOD': ('the state is rebuilt from a panel with the scored week and every later week '
                   'removed, and every band and rank must be identical')})
