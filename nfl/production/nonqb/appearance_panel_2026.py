"""2026 week-1 OBSERVED rows, so the previous game is the previous game.

WHAT THIS FIXES. The appearance panel ends at 2025 week 18. Every player on a
2026 week-2 board therefore carries week 18 as his most recent game, and week
18 is a rest week across the league: measured f_prev_snap means 0.332 for
Buffalo and 0.368 for Detroit against a normal starter share near 0.8.

James Cook is the clearest instance and he is an INSTANCE, not a special
case. His appearance history is otherwise perfect -- f_prev_appeared 1,
f_rate3 and f_rate5 1.0, f_rate_ewma 0.99968, f_consec_missed 0, 67 prior
games -- and the single feature dragging him to 0.7138, essentially the
0.6936 training base rate, is f_prev_snap = 0.03 from a 2-snap rest game. His
true previous game is 2026 week 1 at 0.72.

WHY A NEW MODULE AND NOT AN EDIT TO panel_2026w1. That panel exists for the
non-QB PARTICIPATION estimator and its identity is part of the R9_W1P
candidate, so it may not be edited. It also filters `POSITIONS = ('WR','TE',
'RB')`, which is correct for what it feeds and wrong here: quarterbacks have
no 2026 row at all, which is why Josh Allen sits at 0.4188 and why the
f_prev_snap substitution does nothing for him. This module reads the same
snap-count capture and keeps every position the appearance model scores.

APPEARANCE IS SNAPS, NOT STATISTICS. A player appeared if he was on the field
for an offensive snap. A quarterback who hands off forty times appeared; a
receiver targeted zero times appeared. So `did_not_appear` is resolved from
offense_snaps and from nothing else, and a player with no snap-count row is
left UNKNOWN rather than recorded as absent -- the capture covers 30 of 32
clubs and a missing club is missing evidence, not a team that did not play.
"""
from __future__ import annotations

import csv
import glob
import gzip
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'appearance-panel-2026w1-1'

#: Every position the appearance model scores. Kickers are included because
#: the board now carries a kicking line and his appearance matters to it.
POSITIONS = ('QB', 'RB', 'FB', 'HB', 'WR', 'TE', 'K')

_CACHE: dict = {}


def _widest(pattern):
    """The capture carrying the most rows. Coverage, not recency.

    These captures are partial by club -- one holds two teams, another
    thirty -- so the newest is routinely the thinnest. The widest is chosen
    and the choice is reported, because "which blob" must have one answer.
    """
    best = None
    for f in sorted(glob.glob(str(_REPO / pattern))):
        op = gzip.open if f.endswith('.gz') else open
        try:
            rows = list(csv.DictReader(op(f, 'rt', errors='ignore')))
        except OSError:
            continue
        if best is None or len(rows) > len(best[0]):
            best = (rows, f)
    return best or ([], None)


def build(season: int = 2026, week: int = 1) -> Outcome:
    """Observed appearance rows for `season` week `week`, all offence."""
    key = (season, week)
    if key in _CACHE:
        return _CACHE[key]
    snaps, snap_f = _widest(f'nfl/availability_raw/snap_counts_{season}.*.csv.gz')
    if not snaps:
        return Outcome.blocked(
            'APPEARANCE_2026_NO_SNAP_CAPTURE',
            f'no snap-count capture for {season}, so offensive snaps cannot '
            f'be read and appearance cannot be resolved. It is NOT inferred '
            f'from statistics: a player with no target still appeared.',
            cause=Cause.DATA)

    # pfr_player_id -> gsis_id, from the roster capture. Identity is by id;
    # a snap row this cannot resolve is REPORTED, never name-matched.
    ident, n_roster = {}, 0
    for f in sorted(glob.glob(str(_REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        op = gzip.open if f.endswith('.gz') else open
        for r in csv.DictReader(op(f, 'rt', errors='ignore')):
            pid = (r.get('pfr_id') or '').strip()
            g = (r.get('gsis_id') or '').strip()
            if pid and g and pid not in ident:
                ident[pid] = (g, (r.get('position') or '').strip().upper(),
                              (r.get('team') or '').strip().upper(),
                              (r.get('full_name') or '').strip())
                n_roster += 1
    if not ident:
        return Outcome.blocked(
            'APPEARANCE_2026_NO_IDENTITY_BRIDGE',
            'no raw roster capture carries pfr_id, so snap-count rows cannot '
            'be joined to a gsis_id. Name matching is forbidden here.',
            cause=Cause.DATA)

    rows, unresolved, skipped_pos, teams = [], 0, 0, set()
    for s in snaps:
        try:
            if int(s.get('season') or 0) != int(season) or \
                    int(s.get('week') or 0) != int(week):
                continue
        except ValueError:
            continue
        pid = (s.get('pfr_player_id') or '').strip()
        got = ident.get(pid)
        if not got:
            unresolved += 1
            continue
        g, rpos, rteam, name = got
        pos = (s.get('position') or rpos or '').strip().upper()
        if pos not in POSITIONS:
            skipped_pos += 1
            continue
        try:
            off = float(s.get('offense_snaps') or 0)
        except ValueError:
            off = 0.0
        try:
            st = float(s.get('st_snaps') or 0)
        except ValueError:
            st = 0.0
        pct = s.get('offense_pct')
        try:
            pct = float(pct) if pct not in (None, '') else None
        except ValueError:
            pct = None
        # A KICKER TAKES NO OFFENSIVE SNAP AND HE CERTAINLY APPEARED.
        # Reading appearance off `offense_snaps` marked Tyler Bass absent
        # from a game in which he went 3-for-3 on field goals. For a kicker
        # the snaps that exist are SPECIAL TEAMS snaps, so his appearance and
        # his share are read from that column instead.
        if pos == 'K':
            # HIS APPEARANCE IS A FACT; HIS SNAP SHARE IS NOT DEFINED ON THE
            # SCALE THE MODEL LEARNED. The appearance feature `snap_share` is
            # an OFFENSIVE share throughout the training panel, and a kicker
            # takes no offensive snap. Handing over his special-teams share
            # instead read 0.45 for Tyler Bass -- which on the offensive scale
            # means a rotational player -- and drove him 0.9970 -> 0.6850 on a
            # game he kicked three field goals in. That is a category error,
            # not evidence.
            #
            # So the appearance is kept and the share is left MISSING, which
            # the featuriser already has a flag for. The training panel holds
            # 47 kicker rows against 21,219 receivers, so this position is
            # thin support at best and is not worth a fabricated number.
            counted, pct = st, None
        else:
            counted = off
        team = (s.get('team') or rteam or '').strip().upper()
        teams.add(team)
        rows.append({
            'season': int(season), 'week': int(week),
            'ord': int(season) * 100 + int(week),
            'gsis_id': g, 'player_name': name, 'position': pos, 'team': team,
            'game_id': (s.get('game_id') or '').strip(),
            'offense_snaps': off, 'st_snaps': st,
            'offense_pct': pct, 'snap_share': pct,
            'snap_share_defined': pct is not None,
            'snaps_counted': counted,
            'snap_basis': 'ST_SNAPS' if pos == 'K' else 'OFFENSE_SNAPS',
            # APPEARANCE IS SNAPS -- the snaps his position actually takes.
            'did_not_appear': 0 if counted > 0 else 1,
            'appeared': 1 if counted > 0 else 0,
            'source_blob': pathlib.Path(snap_f).name,
        })
    if not rows:
        return Outcome.blocked(
            'APPEARANCE_2026_NO_ROWS',
            f'the widest {season} snap capture carries no week-{week} '
            f'offensive row this module can resolve. Zero rows is an absence, '
            f'not a week nobody played.', cause=Cause.DATA,
            blob=pathlib.Path(snap_f).name if snap_f else None)
    import collections
    return Outcome.ok(
        'APPEARANCE_2026_PANEL', value=rows, spec_version=SPEC_VERSION,
        n_rows=len(rows), n_teams=len(teams), teams=sorted(teams),
        by_position=dict(collections.Counter(r['position'] for r in rows)),
        n_appeared=sum(1 for r in rows if r['appeared']),
        n_did_not_appear=sum(1 for r in rows if not r['appeared']),
        snap_blob=pathlib.Path(snap_f).name,
        n_snap_rows_unresolved_identity=unresolved,
        n_rows_skipped_non_offensive_position=skipped_pos,
        appearance_rule='offensive snaps > 0, except a KICKER, whose '
                        'appearance is special-teams snaps -- he takes no '
                        'offensive snap and reading that column marked a '
                        'kicker absent from a game he kicked three field '
                        'goals in. A player with no snap-count row '
                        'is absent from this panel and stays UNKNOWN -- the '
                        'capture covers a subset of clubs and a missing club '
                        'is missing evidence, not a team that did not play.',
        coverage_caveat=f'{len(teams)} club(s) covered')


def by_id(season: int = 2026, week: int = 1):
    """{gsis_id: row}, or an empty dict when the panel refuses."""
    o = build(season, week)
    return {r['gsis_id']: r for r in o.value} if o.ok else {}
