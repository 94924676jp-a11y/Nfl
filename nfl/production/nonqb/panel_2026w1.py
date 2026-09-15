"""2026 week-1 panel rows, derived from evidence already held. R9_W1P only.

WHY THIS EXISTS. `participation_prior` refuses PARTICIPATION_HISTORY_STALE for
2026 week 2: the accepted ewma_hl2 weights the most recent games hardest and
the panel stops at ordinal 202518. The named missing input is
`pbp_participation_2026`, which has never been captured.

A FIELD-BY-FIELD AUDIT FOUND EXACTLY ONE MISSING FIELD, not a missing dataset:

    season, week             pbp_2026 / snap_counts_2026      EXACT
    gsis_id                  roster pfr_id -> gsis_id         EXACT
    position                 weekly_rosters                   EXACT
    team_dropbacks_part      pbp qb_dropback per team-game    EXACT
    offense_pct (appeared)   snap_counts_2026                 EXACT
    targets                  pbp receiver_player_id           EXACT
    carries                  pbp rusher_player_id             EXACT
    pass_snaps               needs per-play on-field presence  ** MISSING **

`offense_players` is absent from the play-by-play -- checked, along with
offense_personnel, defense_players and n_offense. Per-play presence exists only
in pbp_participation. So six of seven fields are exact and one is not derivable.

WHAT IS DONE ABOUT THE ONE. `pass_snaps` is APPROXIMATED as

    pass_snaps_approx = offense_snaps * (team_dropbacks / team_offense_plays)

which assumes a player's pass/run snap split equals his team's. That is
systematically wrong for exactly the players it matters for: a blocking tight
end and an early-down back are over-credited with pass participation, a
third-down back and a slot receiver under-credited.

SO THE ERROR IS BOUNDED RATHER THAN ASSERTED. Given a player's offensive snaps
S, his team's dropbacks D and its runs R = plays - D, his true pass snaps
cannot be outside

    lo = max(0, S - R)        he ran out of run plays to have been on
    hi = min(S, D)            he cannot pass-block on more dropbacks than exist

Both bounds are arithmetic, not modelled. Every row carries them, so a consumer
can see the width of what the approximation is guessing instead of taking the
point value on trust.

THIS IS NOT THE ACCEPTED ESTIMATOR AND MUST NEVER BE FED TO IT. The accepted
arm is ewma_hl2 over TRUE pass_snaps. Rows from here are consumed only by the
separately identified candidate V1_CANDIDATE_R9_W1P, and every row is stamped
`pass_snaps_basis='APPROXIMATED_FROM_TEAM_DROPBACK_RATE'`.

COVERAGE IS PARTIAL AND SAYS SO. pbp_2026 covers 10 of 16 week-1 games and
snap_counts 15; the intersection is 10. Both DET's and BUF's week-1 games are
in it (2026_01_NO_DET, 2026_01_BUF_HOU), so the two clubs that matter carry
their own evidence -- but the league-wide positional mean drawn from these rows
is a 10-game sample and is NOT a league mean.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import hashlib
import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

SPEC_VERSION = 'panel-2026w1-derived-1'
SEASON = 2026
WEEK = 1
POSITIONS = ('WR', 'TE', 'RB')
BASIS = 'APPROXIMATED_FROM_TEAM_DROPBACK_RATE'


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _num(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _widest(pattern, week=None):
    """The capture with the most rows for the week. An empty match is absence."""
    best, bn, bf = None, -1, None
    for f in glob.glob(str(_REPO / pattern)):
        try:
            rows = list(csv.DictReader(gzip.open(f, 'rt')))
        except Exception:                                        # noqa: BLE001
            continue
        if week is not None:
            rows = [r for r in rows if str(r.get('week')) == str(week)]
        if len(rows) > bn:
            best, bn, bf = rows, len(rows), f
    return best, bf


def build() -> Outcome:
    """Derive the 2026 week-1 rows, or refuse naming what is absent."""
    pbp, pbp_f = _widest('nfl/research/postgame/pbp_2026.*.csv.gz', WEEK)
    if not pbp:
        return Outcome.blocked(
            'W1P_PBP_ABSENT',
            'no 2026 play-by-play capture carries week 1, so neither team '
            'dropbacks nor targets can be counted.', cause=Cause.DATA)
    snaps, snap_f = _widest('nfl/availability_raw/snap_counts_2026.*.csv.gz',
                            WEEK)
    if not snaps:
        return Outcome.blocked(
            'W1P_SNAP_COUNTS_ABSENT',
            'no 2026 snap-count capture carries week 1, so offensive snaps '
            'and the appeared flag are both unavailable.', cause=Cause.DATA)

    ident, roster_f = {}, None
    for f in sorted(glob.glob(str(_REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        rows = list(csv.DictReader(gzip.open(f, 'rt')))
        if not rows or 'pfr_id' not in rows[0]:
            continue
        roster_f = f
        for r in rows:
            pid = (r.get('pfr_id') or '').strip()
            g = (r.get('gsis_id') or '').strip()
            if pid and g:
                ident[pid] = (g, (r.get('position') or '').strip(),
                              (r.get('full_name') or '').strip())
    if not ident:
        return Outcome.blocked(
            'W1P_IDENTITY_BRIDGE_ABSENT',
            'no raw roster capture carries pfr_id, so snap-count rows cannot '
            'be resolved to gsis_id. Snap counts are keyed by pfr_player_id '
            'and the panel by gsis_id; without the bridge nothing joins.',
            cause=Cause.DATA)

    # TEAM TOTALS, EXACT, from play-by-play.
    db, runs, plays = collections.Counter(), collections.Counter(), \
        collections.Counter()
    tgt, car = collections.Counter(), collections.Counter()
    games = collections.defaultdict(set)
    for r in pbp:
        t = r.get('posteam')
        if not t:
            continue
        gid = r.get('game_id')
        is_db = str(r.get('qb_dropback') or '0') in ('1', '1.0')
        is_rush = str(r.get('rush_attempt') or '0') in ('1', '1.0')
        if is_db or is_rush:
            plays[t] += 1
            games[t].add(gid)
        if is_db:
            db[t] += 1
        if is_rush and not is_db:
            runs[t] += 1
        rec = (r.get('receiver_player_id') or '').strip()
        if rec:
            tgt[rec] += 1
        rush = (r.get('rusher_player_id') or '').strip()
        if rush:
            car[rush] += 1

    out, skipped = [], collections.Counter()
    for s in snaps:
        pid = (s.get('pfr_player_id') or '').strip()
        team = (s.get('team') or '').strip()
        if not pid or pid not in ident:
            skipped['no_identity_bridge'] += 1
            continue
        g, pos, name = ident[pid]
        if pos not in POSITIONS:
            skipped['not_a_target_position'] += 1
            continue
        if team not in db or db[team] <= 0:
            # A club with snap counts but no play-by-play cannot be given a
            # denominator, and a share over a guessed denominator is a guess.
            skipped['team_has_no_pbp'] += 1
            continue
        S = _num(s.get('offense_snaps'))
        D, R = float(db[team]), float(runs[team])
        P = float(plays[team]) or 1.0
        approx = S * (D / P)
        lo = max(0.0, S - R)
        hi = min(S, D)
        out.append({
            'season': SEASON, 'week': WEEK, 'team': team, 'gsis_id': g,
            'game_id': s.get('game_id'), 'position': pos,
            'player_name': name,
            'team_plays': int(P), 'team_dropbacks': int(D),
            'team_dropbacks_part': int(D),
            'targets': tgt.get(g, 0), 'carries': car.get(g, 0),
            'offense_snaps': S, 'offense_pct': s.get('offense_pct'),
            'pass_snaps': approx,
            # THE THREE FIELDS THAT KEEP THIS HONEST.
            'pass_snaps_basis': BASIS,
            'pass_snaps_lower_bound': lo,
            'pass_snaps_upper_bound': hi,
        })
    if not out:
        return Outcome.blocked(
            'W1P_NO_ROWS_DERIVED',
            f'every candidate row was skipped: {dict(skipped)}. Zero rows is '
            f'an absence, not an empty week.', cause=Cause.DATA,
            skipped=dict(skipped))

    prov = {
        'artifact': 'NFL_PANEL_2026W1_DERIVED',
        'spec_version': SPEC_VERSION,
        'pass_snaps_basis': BASIS,
        'sources': {
            'pbp': {'path': os.path.relpath(pbp_f, _REPO),
                    'sha256': _sha(pbp_f), 'week1_rows': len(pbp)},
            'snap_counts': {'path': os.path.relpath(snap_f, _REPO),
                            'sha256': _sha(snap_f), 'week1_rows': len(snaps)},
            'identity_bridge': {'path': os.path.relpath(roster_f, _REPO),
                                'sha256': _sha(roster_f)},
        },
        'coverage': {
            'teams_with_pbp': len(db),
            'games_with_pbp': len({g for v in games.values() for g in v}),
            'rows_derived': len(out), 'skipped': dict(skipped),
        },
    }
    return Outcome.ok(
        'W1P_PANEL_DERIVED', value=out,
        detail=f'{len(out)} row(s) for {len(db)} team(s); pass_snaps '
               f'{BASIS}', provenance=prov, spec_version=SPEC_VERSION,
        n_rows=len(out), n_teams=len(db), skipped=dict(skipped))
