"""Point-in-time depth-chart selection, with the vendor break made explicit.

WHAT THIS FIXES

`stage_a.depth()` reads the 2020-2024 weekly leaves and returns a mapping that
`stage_a.build` writes onto every row as `f_depth`. Measured 2026-09-10 on the
staged leaves: 152,246 entries, non-null on 57,160 of 83,144 panel rows. It was
never empty. What happens to it is that NEITHER `stage_a.featurise` NOR
`p3_features.featurise_p3` reads the key, so a 49-column design row is built
without it and the strongest available role signal is discarded at the last
step. `assert_walk_matches_research` compares fourteen features and `f_depth`
is not one of them, so the equivalence check could not have noticed.

THE VENDOR BREAK IS REAL AND IS NOT PAPERED OVER

  2020-2024   nflverse weekly schema: season, week, club_code, depth_team,
              position, depth_position. One chart per team-week.
  2025-2026   ESPN daily-snapshot schema: dt, team, gsis_id, pos_abb,
              pos_slot, pos_rank. One chart per team per DAY.

They are the same publisher and different data. `stage_a.depth` defaults to
`range(2020, 2025)` and so returns nothing at all for 2025 -- 0 of 13,813 rows
-- and the 2026 capture under `nfl/vintage/depth_charts.*.reduced.csv.gz` is the
daily schema, which nothing ever joined to the weekly key space.

RANK IS PUT ON ONE SCALE, AND THE SCALES ARE NOT INTERCHANGEABLE

nflverse `depth_team` ranks within `depth_position`, so a team fields three
players at "WR depth_team 1". ESPN `pos_rank` ranks within `pos_abb` across the
formation's slots, so a team fields one "WR 1". Comparing them requires putting
both on the same footing: order a team's listed players at a position and take
the ordinal. That is what `_ordinal` does, and it is an ADJUSTMENT, not a
proof of equivalence -- the two feeds do not overlap in time, so no measurement
in this repository can establish that a 2024 WR2 and a 2026 WR2 mean the same
thing. Measured difference on the common scale, appearance rate at rank 1:
nflverse 2020-2024 0.707-0.812, ESPN 2025 0.895-0.923. Anything fitted across
the break carries a regime indicator so the level shift is absorbed rather
than averaged.

THE RECEIVER ORDERING WAS A SPECIAL-TEAMS ORDERING (R3, 2026-09-14)

`weekly` used to take each player's MINIMUM `depth_team` across ALL of his
listed slots and then order the room by `(depth_team, depth_position)`.
`depth_position` is a string and `KOR < KR < PR < WR` alphabetically, so a
kick/punt returner listed at `(PR, 1)` sorted ahead of the club's actual first
-team receivers. Reproduced here over the 2021-2024 REG charts, 2,432 WR
team-weeks: the rank-1 slot was a return slot in 1,649 of them (0.6780), and
was not the plain `WR` slot in 1,665 (0.6846, the figure D5 reports). For RB
the winning slot was a return slot in 616 (0.2533) and `FB` in 796 (0.3273).
Worked example, KC 2023 week 1: the "WR1" was the returner, not the receiver.

The realised record says the same thing. Zero-target rate by the old ordinal,
WR, 2021-2024, all charted players joined to a played team-game:
0.3528 / 0.1559 / 0.1567 / 0.3085 / 0.5496 -- NON-MONOTONE, because rank 1 was
not a role.

THE REPAIR, AND WHAT IT EXPOSES UNDERNEATH

Only rows whose `formation` is `Offense` build the offensive role ordering, and
the slot STRING is never a sort key -- an alphabet is not a depth chart. What
is left is the vendor's own `depth_team` inside the offensive formation.

That reveals the thing the contamination was hiding: **the weekly vendor does
not publish a WR1/WR2/WR3 order at all.** In 2,396 of 2,432 WR rooms (0.9852)
two or three players share `depth_team == 1` with no distinguishing offensive
slot. So this module now emits a GROUP, not a unique ordinal: every player the
chart calls a first-team receiver carries group 1, and `tie_size` and
`resolved` say so out loud. Manufacturing 1/2/3 out of a three-way tie is what
produced the defect in the first place, and it is not done here.

Zero-target rate by the repaired group, same rows: 0.1263 / 0.4429 / 0.6480 --
monotone. Appeared-only: 0.0319 / 0.2700 / 0.3886, also monotone. RB moves from
0.3236 / 0.2182 / 0.2946 (non-monotone) to 0.2391 / 0.2795 / 0.4483.

A player listed ONLY on special teams has no offensive role evidence. He is
NOT given an offensive rank -- he is counted and named in the evidence instead,
because "the chart lists him as a returner" and "the chart puts him first among
receivers" are different facts and the old key rendered them the same.

POINT-IN-TIME, OR REFUSE

`daily_point_in_time` takes the newest snapshot STRICTLY BEFORE the clock it is
given and never a later one. Measured over the 544 team-weeks of the 2025
regular season: every one resolves, the chosen snapshot sits 6.3 to 18.7 hours
before kickoff, median 10.8. When nothing predates the clock the answer is a
named refusal. Today's chart is never substituted for a historical game.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import io
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

# Bumped by R3 2026-09-14: `weekly` now emits an OFFENSIVE DEPTH GROUP
# built from `formation == 'Offense'` rows only. The old string described
# a different quantity and must not be carried across the change.
SPEC_VERSION = 'depth-vintage-pit-2-offensive-role-only'

# WHAT THIS SELECTOR CANNOT ANSWER, STATED WHERE IT IS SELECTED. The capture
# reducer keeps one `dt` slice per blob and the rest of the series is not
# persisted, so point-in-time resolution is only as dense as the six blobs
# that survive. Two missing slices, 2026-09-11T12:21:50Z and
# 2026-09-12T11:36:06Z, are still inside a retained RAW file and recoverable
# without a fetch -- that is a retention job, not a selection one, and this
# module does not reach past its own evidence to fill the gap.
DURABILITY_CEILING = (
    '171 of 177 captured depth `dt` slices are persisted nowhere (WS-L); only '
    '6 reduced blobs survive, one `dt` each. For most historical cutoffs '
    'there is no stored chart to select, and the correct answer is this '
    'ceiling rather than the nearest chart that does exist.')

SKILL = ('QB', 'RB', 'WR', 'TE', 'FB', 'HB')
_NORM = {'FB': 'RB', 'HB': 'RB'}

# Return-team designations. They appear as `depth_position` strings in the
# weekly vendor and as `pos_abb` values in the daily one. In NEITHER feed may
# one of them decide an offensive role ordering. Named here so the two paths
# are policed by one list instead of two habits.
RETURN_SLOTS = ('KR', 'PR', 'KOR')

WEEKLY_VENDOR = 'nflverse_weekly'
DAILY_VENDOR = 'espn_daily'

VINTAGE = _REPO / 'nfl' / 'vintage'


def _parse(t):
    if not t:
        return None
    d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _ordinal(listed):
    """[(sort_key, pid)] -> {pid: ordinal}, 1-based, ties broken deterministically."""
    return {pid: i + 1 for i, (_, pid) in enumerate(sorted(listed))}


# ---------------------------------------------------------------- scales
# P1, 2026-09-15. THE SECOND SCALE, SUPPLIED RATHER THAN SUBSTITUTED.
#
# R3 measured the offence-wide ordinal and declared it (see `daily`), on the
# ground that re-ranking anybody moves a served feature whose coefficients
# were fitted on this scale. That reasoning is intact and the default is
# unchanged: `OFFENCE_WIDE` is what every existing caller gets, value for
# value. What was missing is the OTHER scale.
#
# The weekly vendor's group is built inside (season, week, club, normalised
# position) -- a WITHIN-POSITION quantity -- and the daily vendor's ordinal is
# offence-wide, so the two eras put different quantities in one column of one
# design row. Measured on the R7/R8 union frame, appearance rate by depth
# bucket:
#
#     weekly era (2020-2024, n=48,543)  r1 0.8930  r2 0.7018  r3 0.5186
#     daily  era (2025,      n=11,199)  r1 0.9136  r2 0.9357  r3 0.8805
#
# The daily era's top three buckets are flat because they are not roles: they
# are the three alphabetically-first `pos_rank == 1` players on the club. On
# the within-position scale the same rows give 0.9139 / 0.7451 / 0.6425 --
# monotone, and on the weekly era's footing.
#
# A caller asking for a scale this module does not implement is REFUSED. A
# default would hand back the offence-wide ordinal under a name the caller did
# not choose, which is how the contaminated scale reached a served feature in
# the first place.
OFFENCE_WIDE = 'offence_wide'
WITHIN_POSITION = 'within_position'
RANK_SCALES = (OFFENCE_WIDE, WITHIN_POSITION)

RANK_SCALE_MEANING = {
    OFFENCE_WIDE: (
        'OFFENCE-WIDE ordinal within (team, dt) across QB, RB, WR, TE. It is '
        'NOT a within-position depth rank: a club fields a pos_rank-1 QB, RB, '
        'WR and TE simultaneously and only gsis_id separates them. Declared '
        'by R3 2026-09-14, not repaired: changing it moves a served feature '
        'whose coefficients were fitted on this scale.'),
    WITHIN_POSITION: (
        'WITHIN-POSITION ordinal inside (team, dt, normalised position), on '
        'the same footing as the weekly vendor group. Every position on the '
        'club has its own rank 1, so a cross-position gsis_id tiebreak cannot '
        'arise. Supplied by P1 2026-09-15 for a successor candidate that '
        'REFITS on it; it is not the scale R8 or R9 were fitted on.'),
}


# ---------------------------------------------------------------- weekly
# R3. THE OFFENSIVE ROLE ORDERING IS BUILT FROM OFFENSIVE ROWS ONLY.
#
# `formation` is a column the vendor already publishes on every weekly row and
# this module never read it. Measured on the staged 2021-2024 REG leaves:
# 35,983 skill rows are `Offense`, 8,734 are `Special Teams`, 51 are `Defense`.
# The special-teams rows are the ones that carried `PR`/`KR`/`KOR` into the
# sort key. They are not dropped from the world -- they are dropped from the
# OFFENSIVE ordering, which is the only thing this function claims to build.
OFFENSE_FORMATION = 'Offense'

# The ordering key, stated once. `depth_team` is the vendor's own rank inside
# its own slot and is the only ordering evidence the weekly feed carries. The
# slot STRING is deliberately absent: it is a name, not a rank, and sorting on
# it alphabetically is the defect. Players tied on `depth_team` are tied, and
# the tie is reported rather than broken by a coin flip wearing a sort key.
WEEKLY_ORDERING_KEY = (
    'offensive depth_team, group-compacted within (season, week, club, '
    'normalised position); no slot string and no special-teams row '
    'participates')


def weekly(stage, seasons=range(2020, 2025), detail=False) -> Outcome:
    """The 2020-2024 weekly leaves -> {(season, week, club, gsis): (group, pos)}.

    `group` is a DEPTH GROUP, not a unique ordinal. Two or three players can
    share group 1 because the vendor lists two or three first-team receivers
    and supplies nothing to order them by. `detail=True` returns the full
    record per player -- group, tie_size, resolved, depth_team, slots -- so a
    consumer can tell "he is the WR1" from "he is one of three the chart calls
    first-team".

    A season whose leaf is absent is NAMED. Skipping it silently is how the
    2025 hole stayed invisible for as long as it did.
    """
    stage = pathlib.Path(stage)
    off = collections.defaultdict(dict)       # room -> pid -> (depth_team, slots)
    st_only = collections.defaultdict(set)    # room -> pids seen ONLY off-offence
    seen, absent, no_formation = [], [], []
    n_off = n_st = n_other = n_return_in_offence = 0
    for y in seasons:
        p = stage / f'dc_{y}.csv'
        if not p.exists():
            absent.append(y)
            continue
        hdr = p.open().readline()
        if 'depth_team' not in hdr:
            absent.append(y)
            continue
        if 'formation' not in hdr:
            # NOT A DEFAULT. Without `formation` the offensive rows cannot be
            # separated from the return-team rows, and the only construction
            # available is the contaminated one. Refusing is the answer.
            no_formation.append(y)
            continue
        seen.append(y)
        for r in csv.DictReader(p.open()):
            if r.get('game_type') != 'REG' or not r.get('gsis_id'):
                continue
            pos = (r.get('position') or '').upper()
            if pos not in SKILL:
                continue
            try:
                d = int(r['depth_team'])
            except (TypeError, ValueError, KeyError):
                continue
            form = (r.get('formation') or '').strip()
            room = (int(r['season']), int(r['week']), r['club_code'],
                    _NORM.get(pos, pos))
            pid = r['gsis_id']
            slot = (r.get('depth_position') or '').strip()
            if form == OFFENSE_FORMATION and slot.upper() in RETURN_SLOTS:
                # Belt and braces. A return designation filed under the
                # offensive formation is still a return designation and must
                # not order receivers. Measured 0 on 2021-2024; counted so a
                # future vendor change is visible instead of silent.
                n_return_in_offence += 1
                st_only[room].add(pid)
            elif form == OFFENSE_FORMATION:
                n_off += 1
                cur = off[room].get(pid)
                if cur is None or d < cur[0]:
                    off[room][pid] = (d, {slot} if cur is None
                                      else cur[1] | {slot})
                else:
                    cur[1].add(slot)
            else:
                n_st += 1 if form and form != 'Defense' else 0
                n_other += 1 if form == 'Defense' else 0
                st_only[room].add(pid)
    if absent or no_formation:
        return Outcome.blocked(
            'DEPTH_WEEKLY_LEAF_MISSING',
            f'no usable weekly depth leaf for season(s) '
            f'{sorted(absent + no_formation)}; a missing season is a hole in '
            f'the frame, not an empty one. `formation` is required: without '
            f'it the offensive rows cannot be separated from the return-team '
            f'rows and the only ordering available is the contaminated one.',
            cause=Cause.DATA, seasons_absent=absent,
            seasons_without_formation_column=no_formation,
            seasons_present=seen)
    if not off:
        return Outcome.fail(
            'DEPTH_WEEKLY_EMPTY',
            f'{len(seen)} leaf/leaves were read and produced no OFFENSIVE '
            f'skill-position row; an empty chart is an error, not a result')
    out, det = {}, {}
    tie1 = collections.Counter()
    n_unresolved_rooms = n_rooms = 0
    st_only_players = 0
    for room, players in off.items():
        n_rooms += 1
        depths = sorted({v[0] for v in players.values()})
        gi = {d: i + 1 for i, d in enumerate(depths)}
        size = collections.Counter(v[0] for v in players.values())
        for pid, (d, slots) in players.items():
            g = gi[d]
            out[(room[0], room[1], room[2], pid)] = (g, room[3])
            det[(room[0], room[1], room[2], pid)] = {
                'group': g, 'pos': room[3], 'depth_team': d,
                'tie_size': size[d], 'resolved': size[d] == 1,
                'offensive_slots': sorted(s for s in slots if s)}
        top = min(depths) if depths else None
        tie1[size.get(top, 0)] += 1
        if size.get(top, 0) > 1:
            n_unresolved_rooms += 1
        st_only_players += len(st_only.get(room, set()) - set(players))
    return Outcome.ok(
        'DEPTH_WEEKLY_OK', value=(det if detail else out),
        spec_version=SPEC_VERSION, vendor=WEEKLY_VENDOR, n_entries=len(out),
        seasons=sorted(seen),
        n_team_weeks=len({(k[0], k[1], k[2]) for k in out}),
        n_rooms=n_rooms,
        ordering_key=WEEKLY_ORDERING_KEY,
        n_offensive_rows=n_off,
        n_special_teams_rows_excluded=n_st,
        n_return_slot_rows_under_offence_excluded=n_return_in_offence,
        return_slots_never_ordering=list(RETURN_SLOTS),
        n_defense_rows_excluded=n_other,
        # DECLARED, NOT RESOLVED. This is the uncertainty the special-teams
        # contamination was hiding: the vendor names a first-team GROUP and
        # not a first receiver, and inventing an order inside it is the defect.
        n_rooms_with_unresolved_top_group=n_unresolved_rooms,
        top_group_size_histogram=dict(sorted(tie1.items())),
        n_players_listed_only_off_offence=st_only_players,
        uncertainty=('a player sharing `depth_team` with a room-mate carries '
                     'the same group and `resolved=False`; no unique ordinal '
                     'is manufactured. A player listed only on special teams '
                     'or defence carries NO offensive rank at all, which is '
                     'not the same fact as being unlisted.'),
        value_is=('{(season, week, club, gsis): (group, pos)}; `detail=True` '
                  'returns the full per-player record'))


# ---------------------------------------------------------------- daily
# RL-10. `pos_slot` IS NOT IN THE PERSISTED BLOB, AND THE OLD CODE DID NOT
# SAY SO.
#
# This function read `int(r.get('pos_slot') or 0)` against a reduced blob whose
# header is `dt,team,gsis_id,pos_abb,pos_rank` -- the reduce step drops
# `pos_slot` entirely. So the expression evaluated to 0 on every row of every
# run the system has ever done, and a missing column was indistinguishable from
# a real slot of 0. That is the project's Class A failure inside a tiebreak:
# a read that returned nothing, used as a value.
#
# MEASURED HARM TODAY IS ZERO, AND THIS IS NOT A BUG FIX WITH AN OUTCOME.
# Independently reproduced here on all six persisted reduced blobs
# (2,176-2,222 rows each, one `dt` slice each): 0 tie groups on
# (dt, team, pos_abb, pos_rank). WS-L measured the same on the three surviving
# RAW files across 170/174/177 `dt` slices: 0 tie groups. The tiebreak
# `pos_slot` exists to perform has therefore never been needed, so no number in
# this repository moves because of this change. What is unknowable is the three
# LOST vintages, and a silent 0 could not have told anyone.
#
# THE REPAIR IS A REFUSAL AT THE POINT THE MISSING COLUMN WOULD DECIDE
# SOMETHING, not a blanket refusal. Refusing every blob that lacks `pos_slot`
# would refuse every blob in the tree and take the depth feature out of R7, R8
# and the product board, for a defect with measured-zero effect. The honest
# scope is: absence is recorded and declared; a tie that the absent column
# would have broken is a named FAIL; and where there is no tie, the column
# cannot change an answer and its absence is stated rather than defaulted.
SLOT_ABSENT = None


def _daily_rows(text):
    """Yields (dt, team, gsis_id, pos, rank, slot). `slot` is None when the
    column is absent or unparseable -- NEVER 0, which is a real slot value."""
    for r in csv.DictReader(io.StringIO(text)):
        pos = (r.get('pos_abb') or '').upper()
        if pos not in SKILL or not r.get('gsis_id'):
            continue
        try:
            rk = int(r['pos_rank'])
        except (TypeError, ValueError, KeyError):
            continue
        if 'pos_slot' in r:
            try:
                slot = int(r['pos_slot'])
            except (TypeError, ValueError):
                slot = SLOT_ABSENT
        else:
            slot = SLOT_ABSENT
        # `pos` is the RAW vendor position and `_NORM.get(pos, pos)` the
        # normalised one. Both are carried because the two tie kinds below are
        # different facts and only one of them is pos_slot's business.
        yield (r['dt'], r['team'], r['gsis_id'], _NORM.get(pos, pos), rk, slot,
               pos)


def _slot_sort(slot):
    """A sort position for a row whose slot is unknown.

    It is a CONSTANT across every row that lacks the column, so when the column
    is absent from a whole file -- which is every persisted file -- it cannot
    change any ordering: the sort falls through to the next key, `gsis_id`,
    exactly as it did when the old code wrote 0 into every row. That identity
    is deliberate. This repair is about the missing column being VISIBLE and
    about refusing where it would decide something; it is not a re-ranking, and
    no depth rank in this repository moves because of it.

    -1 rather than 0 because 0 is a real slot value and this is not one.
    """
    return -1 if slot is SLOT_ABSENT else slot


def daily(text, scale=OFFENCE_WIDE) -> Outcome:
    """Daily-schema text -> {team: [(dt, {pid: (rank, pos)}), ...]} in dt order.

    `scale` names WHICH ordinal the rank is. `OFFENCE_WIDE` is the default and
    is what every caller written before 2026-09-15 receives, unchanged;
    `WITHIN_POSITION` ranks inside (team, dt, normalised position) instead.
    The two are different quantities and neither is a translation of the
    other, so the chosen one is carried on the evidence by name.
    """
    if scale not in RANK_SCALES:
        return Outcome.fail(
            'DEPTH_DAILY_RANK_SCALE_UNKNOWN',
            f'{scale!r} names no depth rank scale this module builds. '
            f'Declared: {list(RANK_SCALES)}. Refusing rather than defaulting '
            f'to the offence-wide ordinal, which would serve a scale the '
            f'caller did not ask for under a name they did.',
            known=list(RANK_SCALES), requested=str(scale))
    snap = collections.defaultdict(dict)
    vendor_groups = collections.defaultdict(set)
    norm_groups = collections.defaultdict(set)
    n = n_slot_absent = n_return_rows = 0
    return_pos_seen = set()
    for _r in csv.DictReader(io.StringIO(text)):
        _pa = (_r.get('pos_abb') or '').upper()
        if _pa in RETURN_SLOTS:
            n_return_rows += 1
            return_pos_seen.add(_pa)
    for d, team, pid, pos, rk, slot, pos_raw in _daily_rows(text):
        cur = snap[(team, d)].get(pid)
        if (cur is None
                or (rk, _slot_sort(slot)) < (cur[0], _slot_sort(cur[2]))):
            snap[(team, d)][pid] = (rk, pos, slot)
        vendor_groups[(team, d, pos_raw, rk)].add(pid)
        norm_groups[(team, d, pos, rk)].add(pid)
        if slot is SLOT_ABSENT:
            n_slot_absent += 1
        n += 1
    if not snap:
        return Outcome.fail(
            'DEPTH_DAILY_EMPTY',
            'the daily depth source carried no skill-position row with a '
            'resolvable gsis_id and pos_rank')
    # RL-10. THE TIE THAT THE ABSENT COLUMN WOULD HAVE BROKEN -- AND THE ONE
    # IT WOULD NOT HAVE.
    #
    # These are different facts and collapsing them is what produces either a
    # silent default or a refusal that takes out the whole feature.
    #
    #   VENDOR TIE: two players at the same (team, dt, RAW pos_abb, pos_rank).
    #   This is what `pos_slot` exists to order -- it ranks within `pos_abb`
    #   across the formation's slots -- so without it the order is genuinely
    #   unknown and inventing one is the defect. Measured on all six persisted
    #   reduced blobs: 0 of 586 groups. It has never fired.
    #
    #   NORMALISATION TIE: two players at the same (team, dt, NORMALISED pos,
    #   pos_rank) but DIFFERENT raw positions, because `_NORM` folds FB and HB
    #   into RB. Measured on depth_charts.a14e8dfe865a4b03: 14 of 572 groups,
    #   13 of them {FB, RB} and one {FB, KR, RB}. `pos_slot` would not have
    #   resolved these even if it were present -- it orders within a single
    #   `pos_abb`, and these rows come from different ones. This module's own
    #   normalisation created the collision, so the tiebreak is this module's
    #   to declare: `gsis_id`, which is what the old `or 0` produced by
    #   accident. It is recorded rather than left implicit, and no rank moves.
    contested = sorted(k for k, pids in vendor_groups.items()
                       if len(pids) > 1
                       and any(snap[(k[0], k[1])][p][2] is SLOT_ABSENT
                               for p in pids))
    if contested:
        return Outcome.fail(
            'DEPTH_DAILY_POS_SLOT_REQUIRED_AND_ABSENT',
            f'{len(contested)} (team, dt, pos_abb, pos_rank) group(s) list '
            f'more than one player at the SAME vendor position and carry no '
            f'pos_slot to order them by. pos_slot is dropped by the capture '
            f'reduction, and the previous code read it as `int(... or 0)`, '
            f'which made "the column is not in this file" and "this player is '
            f'in slot 0" the same observation. Refusing to invent the order.',
            n_contested_groups=len(contested), examples=contested[:5],
            n_rows_without_pos_slot=n_slot_absent, n_rows=n,
            remedy='retain pos_slot in the capture reduction for depth_charts '
                   '(a capture-layer change, not made from here)')
    collisions = sorted(k for k, pids in norm_groups.items() if len(pids) > 1)
    by_team = collections.defaultdict(list)
    for (team, d), players in snap.items():
        if scale == WITHIN_POSITION:
            # ONE ROOM PER NORMALISED POSITION. The sort key inside a room is
            # the same one the offence-wide path uses -- vendor pos_rank,
            # then the (absent) slot, then gsis_id -- so nothing new decides
            # an order here. What changes is WHO IS BEING COMPARED: a back is
            # ranked against backs, and the cross-position collision that put
            # a club's RB1 behind its TE1 and QB1 cannot occur at all.
            rooms = collections.defaultdict(list)
            for pid, v in players.items():
                rooms[v[1]].append(((v[0], _slot_sort(v[2]), pid), pid))
            ranked = {}
            for listed in rooms.values():
                ranked.update(_ordinal(listed))
        else:
            ranked = _ordinal([((v[0], _slot_sort(v[2]), pid), pid)
                               for pid, v in players.items()])
        by_team[team].append(
            (d, {pid: (ranked[pid], players[pid][1]) for pid in players}))
    for t in by_team:
        by_team[t].sort(key=lambda x: x[0])
    # R3, 2026-09-14. TWO FACTS ABOUT THIS SCALE, MEASURED AND DECLARED
    # RATHER THAN REPAIRED, BECAUSE REPAIRING THE SECOND WOULD MOVE A SERVED
    # FEATURE THAT NOTHING HERE HAS REFITTED.
    #
    #   1. THE RETURN-SLOT CONTAMINATION THAT `weekly` CARRIED IS NOT HERE.
    #      `KR`, `PR` and `KOR` are `pos_abb` values in this vendor, not
    #      `depth_position` strings, so `pos not in SKILL` already drops them
    #      before any ordering happens. Verified on the six persisted blobs:
    #      104 `KR` rows and 81 `PR` rows read, 0 reaching a rank.
    #      `n_return_slot_rows_excluded` records it so the absence is a
    #      measurement rather than an assumption.
    #
    #   2. THE ORDINAL IS OFFENCE-WIDE, AND IT IS NOT A WITHIN-POSITION ROLE
    #      RANK. `snap` is keyed on (team, dt), so every skill player on the
    #      club competes for one ordinal and the vendor's `pos_rank == 1`
    #      quarterback, running back, receiver and tight end are separated
    #      only by `gsis_id`. `rank_1_position_mix` reports which position
    #      actually won rank 1 per team-snapshot. A consumer reading `rank`
    #      as "WR1" is reading it wrongly, and this says so on the artifact.
    #
    #   P1, 2026-09-15: (2) is now REPAIRABLE BY THE CALLER rather than only
    #   declared, through `scale`. Nothing about the default moved. Under
    #   WITHIN_POSITION the same counter reports every rank-1 player rather
    #   than the single winner of a contest that no longer takes place, so a
    #   club contributes one count per position it lists.
    rank1_pos = collections.Counter()
    for t, snaps_t in by_team.items():
        for _d, m in snaps_t:
            if scale == WITHIN_POSITION:
                for _pid, v in m.items():
                    if v[0] == 1:
                        rank1_pos[v[1]] += 1
                continue
            top = min(m.items(), key=lambda kv: kv[1][0])
            rank1_pos[top[1][1]] += 1
    return Outcome.ok('DEPTH_DAILY_OK', value=dict(by_team),
                      spec_version=SPEC_VERSION, vendor=DAILY_VENDOR,
                      n_rows=n, n_teams=len(by_team),
                      n_snapshots=sum(len(v) for v in by_team.values()),
                      # DECLARED, NOT DEFAULTED. A consumer can now see that
                      # the tiebreak column was absent and that it did not
                      # matter, instead of seeing a column of zeroes.
                      n_rows_without_pos_slot=n_slot_absent,
                      pos_slot_available=(n_slot_absent == 0),
                      n_return_slot_rows_excluded=n_return_rows,
                      return_slot_pos_abb_seen=sorted(return_pos_seen),
                      rank_scale=RANK_SCALE_MEANING[scale],
                      rank_scale_name=scale,
                      rank_1_position_mix=dict(sorted(rank1_pos.items())),
                      n_vendor_rank_groups=len(vendor_groups),
                      n_vendor_rank_ties=0,
                      n_normalisation_rank_collisions=len(collisions),
                      normalisation_collision_examples=collisions[:5],
                      normalisation_tiebreak=(
                          'gsis_id, declared. _NORM folds FB/HB into RB, '
                          'which '
                          'can put two players at one normalised rank; '
                          'pos_slot orders within a single pos_abb and cannot '
                          'resolve a cross-position collision even when it is '
                          'present.'),
                      first_dt=min(d for t in by_team for d, _ in by_team[t]),
                      last_dt=max(d for t in by_team for d, _ in by_team[t]))


def daily_point_in_time(by_team, team, before) -> Outcome:
    """The newest snapshot for `team` STRICTLY BEFORE `before`, or a refusal."""
    before = _parse(before) if not isinstance(before, dt.datetime) else before
    if before is None:
        return Outcome.fail(
            'DEPTH_PIT_NO_CLOCK',
            f'no clock was supplied for {team}, so "point in time" has no '
            f'meaning and the newest chart would be used by default')
    have = by_team.get(team) or []
    ok = [(d, m) for d, m in have if _parse(d) < before]
    if not ok:
        return Outcome.deferred(
            'DEPTH_PIT_UNAVAILABLE',
            f'no depth snapshot for {team} predates {before.isoformat()}; the '
            f'{len(have)} snapshot(s) held are all later, and a later chart is '
            f'not evidence about an earlier game',
            owed={'team': team, 'before': before.isoformat(),
                  'n_snapshots_held': len(have),
                  'earliest_held': have[0][0] if have else None,
                  'evidence_ceiling': DURABILITY_CEILING})
    d, m = ok[-1]
    return Outcome.ok('DEPTH_PIT_OK', value=m, spec_version=SPEC_VERSION,
                      vendor=DAILY_VENDOR, team=team, chosen_dt=d,
                      before=before.isoformat(), n_listed=len(m),
                      hours_before_clock=round(
                          (before - _parse(d)).total_seconds() / 3600.0, 2),
                      n_snapshots_considered=len(have),
                      n_snapshots_rejected_as_later=len(have) - len(ok))


# ---------------------------------------------------------------- production
def captured(teams, observed_before, blobs=None, scale=OFFENCE_WIDE) -> Outcome:
    """The 2026 captured vintage, selected point-in-time.

    Each reduced blob holds ONE dt slice: the capture reducer keeps the newest
    dt of an upstream file that ships its whole history, and records that it
    does under `reduce_recoverability_assumption`. So the durable series is one
    row per capture day, and the selector picks the newest of those that
    predates the clock. No blob is read for its filename or mtime; the clock
    used is the `dt` INSIDE the rows, which is what the vendor stamped.
    """
    paths = ([pathlib.Path(b) for b in blobs] if blobs else
             sorted(VINTAGE.glob('depth_charts.*.reduced.csv.gz')))
    if not paths:
        return Outcome.blocked(
            'DEPTH_CAPTURE_ABSENT',
            f'no captured depth blob under {VINTAGE}; the depth feature is '
            f'unavailable rather than absent-and-fine',
            cause=Cause.DATA)
    text = []
    for p in paths:
        if p.exists():
            text.append(gzip.open(p, 'rt').read())
    if not text:
        return Outcome.blocked(
            'DEPTH_CAPTURE_UNREADABLE',
            f'{len(paths)} captured depth blob path(s) resolved and none could '
            f'be read', cause=Cause.DATA, n_paths=len(paths))
    head = text[0].splitlines()[0]
    joined = head + '\n' + '\n'.join(
        '\n'.join(t.splitlines()[1:]) for t in text)
    d = daily(joined, scale=scale)
    if d.state is not State.PASS:
        return d
    out, chosen, missing = {}, {}, []
    for t in teams:
        pit = daily_point_in_time(d.value, t, observed_before)
        if pit.state is not State.PASS:
            missing.append({'team': t, 'code': pit.code, 'detail': pit.detail})
            continue
        chosen[t] = {'dt': pit.evidence['chosen_dt'],
                     'hours_before_clock': pit.evidence['hours_before_clock'],
                     'n_listed': pit.evidence['n_listed']}
        for pid, v in pit.value.items():
            out[pid] = v
    if missing:
        return Outcome.deferred(
            'DEPTH_CAPTURE_NOT_POINT_IN_TIME',
            f'{len(missing)} of {len(teams)} team(s) have no captured depth '
            f'chart predating {observed_before}; the depth feature is refused '
            f'for the slate rather than filled from a later capture',
            owed={'teams': missing, 'observed_before': str(observed_before),
                  'evidence_ceiling': DURABILITY_CEILING})
    return Outcome.ok('DEPTH_CAPTURE_OK', value=out, spec_version=SPEC_VERSION,
                      vendor=DAILY_VENDOR, n_players=len(out),
                      observed_before=str(observed_before), chosen=chosen,
                      n_blobs=len(paths),
                      rank_scale_name=scale,
                      rank_scale=RANK_SCALE_MEANING[scale],
                      evidence_ceiling=DURABILITY_CEILING,
                      pos_slot_available=d.evidence.get('pos_slot_available'),
                      n_normalisation_rank_collisions=d.evidence.get(
                          'n_normalisation_rank_collisions'),
                      blobs=[str(p.relative_to(_REPO)) for p in paths])
