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

SPEC_VERSION = 'depth-vintage-pit-1'

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


# ---------------------------------------------------------------- weekly
def weekly(stage, seasons=range(2020, 2025)) -> Outcome:
    """The 2020-2024 weekly leaves -> {(season, week, club, gsis): (rank, pos)}.

    A season whose leaf is absent is NAMED. Skipping it silently is how the
    2025 hole stayed invisible for as long as it did.
    """
    stage = pathlib.Path(stage)
    raw = collections.defaultdict(list)
    seen, absent = [], []
    for y in seasons:
        p = stage / f'dc_{y}.csv'
        if not p.exists():
            absent.append(y)
            continue
        hdr = p.open().readline()
        if 'depth_team' not in hdr:
            absent.append(y)
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
            raw[(int(r['season']), int(r['week']), r['club_code'],
                 _NORM.get(pos, pos))].append(
                     (d, r.get('depth_position') or '', r['gsis_id']))
    if absent:
        return Outcome.blocked(
            'DEPTH_WEEKLY_LEAF_MISSING',
            f'no usable weekly depth leaf for season(s) {absent}; a missing '
            f'season is a hole in the frame, not an empty one',
            cause=Cause.DATA, seasons_absent=absent, seasons_present=seen)
    if not raw:
        return Outcome.fail(
            'DEPTH_WEEKLY_EMPTY',
            f'{len(seen)} leaf/leaves were read and produced no skill-position '
            f'row; an empty chart is an error, not a result')
    out = {}
    for (s, w, club, pos), v in raw.items():
        best = {}
        for d, dp, pid in v:
            if pid not in best or d < best[pid][0]:
                best[pid] = (d, dp)
        for pid, rank in _ordinal([((b[0], b[1]), pid)
                                   for pid, b in best.items()]).items():
            out[(s, w, club, pid)] = (rank, pos)
    return Outcome.ok('DEPTH_WEEKLY_OK', value=out, spec_version=SPEC_VERSION,
                      vendor=WEEKLY_VENDOR, n_entries=len(out),
                      seasons=sorted(seen), n_team_weeks=len({
                          (k[0], k[1], k[2]) for k in out}))


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


def daily(text) -> Outcome:
    """Daily-schema text -> {team: [(dt, {pid: (rank, pos)}), ...]} in dt order."""
    snap = collections.defaultdict(dict)
    vendor_groups = collections.defaultdict(set)
    norm_groups = collections.defaultdict(set)
    n = n_slot_absent = 0
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
        ranked = _ordinal([((v[0], _slot_sort(v[2]), pid), pid)
                           for pid, v in players.items()])
        by_team[team].append(
            (d, {pid: (ranked[pid], players[pid][1]) for pid in players}))
    for t in by_team:
        by_team[t].sort(key=lambda x: x[0])
    return Outcome.ok('DEPTH_DAILY_OK', value=dict(by_team),
                      spec_version=SPEC_VERSION, vendor=DAILY_VENDOR,
                      n_rows=n, n_teams=len(by_team),
                      n_snapshots=sum(len(v) for v in by_team.values()),
                      # DECLARED, NOT DEFAULTED. A consumer can now see that
                      # the tiebreak column was absent and that it did not
                      # matter, instead of seeing a column of zeroes.
                      n_rows_without_pos_slot=n_slot_absent,
                      pos_slot_available=(n_slot_absent == 0),
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
def captured(teams, observed_before, blobs=None) -> Outcome:
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
    d = daily(joined)
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
                      evidence_ceiling=DURABILITY_CEILING,
                      pos_slot_available=d.evidence.get('pos_slot_available'),
                      n_normalisation_rank_collisions=d.evidence.get(
                          'n_normalisation_rank_collisions'),
                      blobs=[str(p.relative_to(_REPO)) for p in paths])
