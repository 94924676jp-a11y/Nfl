#!/usr/bin/env python3.12
"""Attribute captured league-wide vintages to ONE game. G0A item 1, downstream.

    python3.12 -m nfl.truth.game_truth --game-id 2026_03_ATL_GB \
        --vintage-dir <dir with the reduced csv.gz blobs> --out <path.json>

WHAT THIS IS, AND THE SMALLER-THAN-EXPECTED GAP IT CLOSES

The capture layer stores LEAGUE-WIDE artifacts: one depth-chart file for all
32 teams, one injury file for the week, one roster file for the season. The
manifest says so itself -- `source_artifact_scope: LEAGUE_WIDE`, with the note
that "fetching it for one target does not make the artifact that target's
document". So the bytes for this game exist and nothing had turned them into
this game's state.

CORRECTION TO A STALE BRIEFING LINE. `CLAUDE.md` says the open G0A item is
open "because no parser exists". That was true when written and is not true
now: `nfl/parse/injury_report.py` exists, and run against today's capture it
returns PASS, 259 rows, 2026 week 3, 16 games. What is missing is narrower --
the nflverse CSV sources need no parser at all, because they already carry
`team`, `week` and `gsis_id`. For those, attribution is a filter, not a parse.

WHY THE nflverse CSVs AND NOT THE OFFICIAL HTML

Both are used, for different jobs, and the difference is the identifier spine.
The official report is authoritative but carries no gsis_id, so every row is
PLAYER_GSIS_UNMAPPED against this project's spine -- its own parser says so.
The nflverse CSVs carry gsis_id directly. So the CSVs build the state and the
official report corroborates it; the reverse would require a name crosswalk,
and a silent name match is exactly what this project refuses.

THE RULE THAT SHAPES EVERY RECORD

Absence of a row is NEVER availability. A player with no injury row is
UNKNOWN_NO_DESIGNATION, not ACTIVE. A player who did not practise but carries
no game designation is UNKNOWN_NO_DESIGNATION too, and A.J. Terrell is exactly
that case in this game -- "Did Not Participate In" with an empty
`report_status`. Reading that as ACTIVE would be inference from omission, which
the owner forbade and which would quietly promote a doubtful player to a
certain one.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import sys

PARSER_VERSION = 'game_truth/1.0.0'

# Availability vocabulary. UNKNOWN_NO_DESIGNATION is the default and the point.
OUT = 'OUT'
DOUBTFUL = 'DOUBTFUL'
QUESTIONABLE = 'QUESTIONABLE'
UNKNOWN = 'UNKNOWN_NO_DESIGNATION'
INACTIVE_OFFICIAL = 'INACTIVE_OFFICIAL'

_STATUS_MAP = {
    'out': OUT,
    'doubtful': DOUBTFUL,
    'questionable': QUESTIONABLE,
}


class TruthError(RuntimeError):
    pass


def _rows(path: pathlib.Path) -> list:
    if not path.exists():
        raise TruthError(f'MISSING_VINTAGE_ARTIFACT: {path}')
    with gzip.open(path, 'rt', newline='') as fh:
        out = list(csv.DictReader(fh))
    if not out:
        # An empty artifact is an error, not an empty truth state.
        raise TruthError(f'EMPTY_VINTAGE_ARTIFACT: {path}')
    return out


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def names_from_raw_roster(path: pathlib.Path, teams: tuple,
                          season: int, week: int | None = None) -> dict:
    """gsis_id -> display name, from the RAW roster blob.

    WHY THE RAW AND NOT THE REDUCED. The reduction keeps
    `season,week,team,gsis_id,position` and drops the name. That is fine for
    the capture layer's purpose and fatal for this one: the existing
    availability feed joins ON DISPLAY NAME and asks the caller for the
    id -> name map it already trusts, so a snapshot with no names cannot
    drive it. Measured before this existed: 137 of 159 players had no name.

    ONLY THE NAME IS TAKEN FROM HERE, AND THAT IS A GOVERNANCE LINE, NOT A
    CONVENIENCE. The same file carries `status` and `status_description_abbr`,
    and CLAUDE.md records that `weekly_rosters.status` may NOT close
    PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE because it is post-hoc -- INA
    resolves to 0 snaps in 3,438 cases, which is the outcome written back
    into the roster after the game. Reading it here would import a postgame
    field into a pregame state through the back door. Identity is safe to
    take; availability is not.
    """
    out = {}
    with gzip.open(path, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if r.get('team') not in teams:
                continue
            if r.get('season') and r['season'].isdigit() and int(r['season']) != season:
                continue
            # NO WEEK FILTER, DELIBERATELY. A display name is an identity
            # attribute, not a weekly state: it does not change between
            # week 2 and week 3. The newest retained raw roster blob covers
            # weeks 1-2 only -- newer captures keep the reduced artifact and
            # not the raw -- so filtering on the target week resolved zero
            # names and left 137 of 159 players unnamed. Season and team
            # still bound it, and nothing else is read from this file.
            gid = r.get('gsis_id')
            nm = r.get('full_name') or r.get('football_name')
            if gid and nm:
                out[gid] = nm
    return out


def parse_game_id(game_id: str) -> tuple:
    """`2026_03_ATL_GB` -> (2026, 3, 'ATL', 'GB'). Refuses anything else."""
    parts = game_id.split('_')
    if len(parts) != 4:
        raise TruthError(f'UNPARSEABLE_GAME_ID: {game_id!r}')
    season, week, away, home = parts
    if not season.isdigit() or not week.isdigit():
        raise TruthError(f'UNPARSEABLE_GAME_ID: {game_id!r}')
    return int(season), int(week), away, home


def build(game_id: str, vintage: dict) -> dict:
    """The truth state for one game. `vintage` maps source -> file path."""
    season, week, away, home = parse_game_id(game_id)
    teams = (away, home)

    sched = _rows(vintage['schedules'])
    game = [r for r in sched
            if r.get('game_id') == game_id]
    if not game:
        raise TruthError(f'GAME_NOT_IN_SCHEDULE: {game_id}')
    g = game[0]

    roster = [r for r in _rows(vintage['weekly_rosters'])
              if r['team'] in teams and int(r['season']) == season
              and int(r['week']) == week]
    if not roster:
        raise TruthError(f'NO_ROSTER_ROWS: {game_id} week {week}')

    depth = [r for r in _rows(vintage['depth_charts']) if r['team'] in teams]

    # Identity names, needed because the downstream availability feed joins on
    # display name. Absent -> recorded, never silently empty.
    names = {}
    name_source = None
    if vintage.get('weekly_rosters_raw'):
        names = names_from_raw_roster(vintage['weekly_rosters_raw'], teams,
                                      season, week)
        name_source = str(vintage['weekly_rosters_raw'])
    inj = [r for r in _rows(vintage['injuries'])
           if r['team'] in teams and int(r['season']) == season
           and int(r['week']) == week]

    # ---- index by the identifier spine -------------------------------
    depth_by_id, inj_by_id = {}, {}
    for r in depth:
        depth_by_id.setdefault(r['gsis_id'], []).append(r)
    for r in inj:
        inj_by_id[r['gsis_id']] = r

    players, unresolved = [], []
    roster_ids = {r['gsis_id'] for r in roster}

    for r in sorted(roster, key=lambda x: (x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        d = sorted(depth_by_id.get(pid, []),
                   key=lambda x: int(x.get('pos_rank') or 99))
        i = inj_by_id.get(pid)
        status_raw = (i or {}).get('report_status', '') or ''
        availability = _STATUS_MAP.get(status_raw.strip().lower(), UNKNOWN)
        players.append({
            'game_id': game_id,
            'team': r['team'],
            'gsis_id': pid,
            'full_name': names.get(pid) or (i or {}).get('full_name'),
            'name_source': ('weekly_rosters_raw' if names.get(pid)
                            else ('injuries' if (i or {}).get('full_name')
                                  else None)),
            'position': r.get('position'),
            'depth_positions': [{'pos_abb': x.get('pos_abb'),
                                 'pos_rank': x.get('pos_rank')} for x in d],
            'on_depth_chart': bool(d),
            'availability': availability,
            'report_status_raw': status_raw or None,
            'report_primary_injury': (i or {}).get('report_primary_injury'),
            'practice_status': (i or {}).get('practice_status'),
            # The distinction the governance rule turns on.
            'availability_basis': ('DECLARED_GAME_DESIGNATION' if availability
                                   != UNKNOWN else 'NO_DECLARATION_FOUND'),
        })

    # A depth-chart or injury identity absent from the roster is surfaced,
    # never matched by name into one that is.
    for pid in sorted(set(depth_by_id) - roster_ids):
        unresolved.append({'gsis_id': pid, 'source': 'depth_charts',
                           'reason': 'NOT_ON_WEEKLY_ROSTER',
                           'depth': depth_by_id[pid][0]})
    for pid in sorted(set(inj_by_id) - roster_ids):
        unresolved.append({'gsis_id': pid, 'source': 'injuries',
                           'reason': 'NOT_ON_WEEKLY_ROSTER',
                           'full_name': inj_by_id[pid].get('full_name')})

    counts = {}
    for t in teams:
        tp = [p for p in players if p['team'] == t]
        counts[t] = {
            'roster': len(tp),
            'on_depth_chart': sum(1 for p in tp if p['on_depth_chart']),
            'declared_out': sum(1 for p in tp if p['availability'] == OUT),
            'declared_questionable':
                sum(1 for p in tp if p['availability'] == QUESTIONABLE),
            'declared_doubtful':
                sum(1 for p in tp if p['availability'] == DOUBTFUL),
            'unknown_no_designation':
                sum(1 for p in tp if p['availability'] == UNKNOWN),
            'with_display_name': sum(1 for p in tp if p['full_name']),
            'without_display_name': sum(1 for p in tp if not p['full_name']),
        }

    return {
        'schema': 'nfl_game_truth',
        'schema_version': PARSER_VERSION,
        'game_id': game_id,
        'season': season,
        'week': week,
        'away_team': away,
        'home_team': home,
        'kickoff_local': f"{g.get('gameday')} {g.get('gametime')}",
        'roof': g.get('roof'),
        'surface': g.get('surface'),
        'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'identity_name_source': name_source,
        'official_inactives_ingested': False,
        'official_inactives_note':
            'Not yet released. Until they are, no player here is INACTIVE and '
            'no player is confirmed active. Absence of a designation is '
            'UNKNOWN_NO_DESIGNATION.',
        'source_vintages': {k: {'path': str(v), 'sha256': _sha(v)}
                            for k, v in sorted(vintage.items())},
        'counts': counts,
        'unresolved_identities': unresolved,
        'players': players,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--vintage-dir', required=True)
    ap.add_argument('--out', default='')
    a = ap.parse_args(argv)

    d = pathlib.Path(a.vintage_dir)
    vintage = {}
    for src in ('schedules', 'weekly_rosters', 'depth_charts', 'injuries'):
        hits = sorted(d.glob(f'{src}.*.csv.gz'))
        # Prefer the reduced artifact where both exist; raw is 50MB+.
        red = [h for h in hits if '.reduced.' in h.name]
        pick = red or [h for h in hits if '.raw.' not in h.name] or hits
        if not pick:
            print(f'MISSING_SOURCE: {src} in {d}')
            return 2
        vintage[src] = pick[0]

    # THE RAW MATCHING THE SELECTED REDUCED, NOT JUST ANY RAW. The first
    # version took sorted(...)[0] and picked f7e970be -- a weeks 1-2 vintage
    # -- while the reduced artifact in use was 0efeaede, which carries weeks
    # 1-3. Two vintages of the same family in one snapshot is exactly the
    # split-clock defect the run-input contract exists to stop, and it left
    # two ATL players unnamed that the correct vintage names.
    #
    # The two blobs share a capture digest, so the reduced name yields the raw
    # name directly. An unmatched raw is NOT substituted.
    red = vintage.get('weekly_rosters')
    if red is not None:
        cand = d / red.name.replace('.reduced.csv.gz', '.raw.csv.gz')
        if cand.exists():
            vintage['weekly_rosters_raw'] = cand

    try:
        state = build(a.game_id, vintage)
    except TruthError as exc:
        print(f'TRUTH_REFUSED {exc}')
        return 1

    text = json.dumps(state, indent=1) + '\n'
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(text)
        print(f'wrote {a.out} ({len(text)} bytes)')
    for t, c in state['counts'].items():
        print(f"  {t}: {c}")
    print(f"  unresolved identities: {len(state['unresolved_identities'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
