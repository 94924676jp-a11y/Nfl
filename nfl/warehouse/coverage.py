#!/usr/bin/env python3.12
"""The coverage ledger. Exactly the dimensions the mandate names, measured rather than asserted.

    season | source | statistic | games | players | teams | completeness | retrieval method |
    source timestamp | source digest

WHY A LEDGER RATHER THAN A README. A count written in prose goes stale the moment a capture is added,
and this project has already been burned by that -- three documents disagreed about how many test
suites existed and all three were wrong within a day. So the ledger is generated from the bytes on
every run, and anything it cannot establish is named rather than omitted.

THE THREE STATES ARE NOT INTERCHANGEABLE. A statistic reads AVAILABLE, NOT_AVAILABLE_FOR_ERA, or
UNKNOWN_PENDING_ACQUISITION. The second says the football world did not record it; the third says we
have not fetched it. Collapsing them would turn a purchasing problem into a fact about football.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import era, sources  # noqa: E402
from sportsplatform.governance.outcome import Outcome  # noqa: E402

SPEC_VERSION = 'coverage-1'
OUT = _REPO / 'nfl/warehouse/COVERAGE_LEDGER.json'
OUT_MD = _REPO / 'nfl/warehouse/COVERAGE_LEDGER.md'

TEAM_GAME = _REPO / 'nfl/warehouse/TEAM_GAME.json'
PLAYER_GAME = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
ROLE_HISTORY = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'

#: Statistics the ledger reports on, grouped by the table that would carry them.
LEDGER_STATS = {
    'team_game': ('points', 'spread', 'total_line', 'implied_total', 'moneyline', 'rest_days',
                  'weather_temp', 'weather_wind', 'roof', 'overtime', 'team_plays',
                  'situation_neutral_pass_rate', 'pace', 'team_drives', 'red_zone_usage'),
    'player_game': ('pass_attempts', 'completions', 'passing_yards', 'passing_td',
                    'interceptions_thrown', 'sacks_taken', 'rush_attempts', 'rushing_yards',
                    'rushing_td', 'targets', 'receptions', 'receiving_yards', 'receiving_td',
                    'air_yards', 'red_zone_usage', 'goal_line_usage', 'snap_counts'),
    'role_history': ('snap_counts', 'routes_run', 'alignment_slot_wide'),
}

#: statistic -> the warehouse column that evidences it, where the names differ
STAT_TO_COLUMN = {
    'spread': 'spread_line_raw', 'weather_temp': 'temp', 'weather_wind': 'wind',
    'team_plays': 'plays', 'situation_neutral_pass_rate': 'neutral_pass_rate',
    'pace': 'seconds_per_play', 'team_drives': 'drives', 'red_zone_usage': 'rz_trips',
    'rush_attempts': 'carries', 'goal_line_usage': 'gl_carries',
}


def _selection_provenance():
    """Retrieval method, timestamp and digest for every selected source."""
    out = {}
    reg = sources.registry()
    for name, dt in reg.items():
        per_season = '{season}' in ''.join(c['pattern'] for c in dt.candidates)
        if per_season:
            out[name] = {}
            for s in range(era.FIRST_SEASON, 2027):
                o = sources.select(dt, season=s)
                if o.state.name != 'PASS':
                    out[name][s] = {'state': o.state.name, 'reason': o.code}
                    continue
                m = sources.measure(_REPO / o.value['selected'], dt)
                out[name][s] = {
                    'state': 'SELECTED', 'source': o.value['selected'],
                    'tier': o.value['selected_tier'],
                    'retrieval_method': m.get('source') or 'CAPTURE_IN_REPOSITORY',
                    'source_timestamp': m.get('retrieved'),
                    'source_digest': m.get('digest_actual'),
                    'digest_matches_provenance': m.get('digest_matches_provenance'),
                    'n_rejected_candidates': o.value['n_rejected'],
                }
        else:
            o = sources.select(dt)
            if o.state.name != 'PASS':
                out[name] = {'state': o.state.name, 'reason': o.code}
                continue
            m = sources.measure(_REPO / o.value['selected'], dt)
            out[name] = {
                'state': 'SELECTED', 'source': o.value['selected'],
                'tier': o.value['selected_tier'],
                'retrieval_method': m.get('source') or 'CAPTURE_IN_REPOSITORY',
                'source_timestamp': m.get('retrieved'),
                'source_digest': m.get('digest_actual'),
                'digest_matches_provenance': m.get('digest_matches_provenance'),
                'n_rejected_candidates': o.value['n_rejected'],
                'seasons_present': m.get('seasons'),
            }
    return out


def build():
    prov = _selection_provenance()
    tg = json.loads(TEAM_GAME.read_text()) if TEAM_GAME.exists() else {'rows': {}}
    pg = json.loads(PLAYER_GAME.read_text()) if PLAYER_GAME.exists() else {'rows': {}}
    rh = json.loads(ROLE_HISTORY.read_text()) if ROLE_HISTORY.exists() else {'rows': {}}

    tg_by = collections.defaultdict(list)
    for r in tg['rows'].values():
        tg_by[r['season']].append(r)
    pg_by = collections.defaultdict(list)
    for r in pg['rows'].values():
        pg_by[r['season']].append(r)
    rh_by = collections.defaultdict(list)
    for r in rh['rows'].values():
        rh_by[r['season']].append(r)

    SENT = (era.NOT_AVAILABLE_FOR_ERA, era.UNKNOWN_PENDING_ACQUISITION)

    def field_state(rows, col):
        if not rows:
            return {'completeness': 0.0, 'state': era.UNKNOWN_PENDING_ACQUISITION,
                    'n_rows': 0}
        vals = [r.get(col) for r in rows]
        sent = collections.Counter(v for v in vals if v in SENT)
        present = sum(1 for v in vals if v is not None and v not in SENT)
        n = len(vals)
        if present:
            st = era.AVAILABLE
        elif sent:
            st = sent.most_common(1)[0][0]
        else:
            st = era.UNKNOWN_PENDING_ACQUISITION
        return {'completeness': round(present / n, 5), 'state': st, 'n_rows': n,
                'n_sentinel': sum(sent.values())}

    ledger = []
    for season in range(era.FIRST_SEASON, 2027):
        tgr, pgr, rhr = tg_by.get(season, []), pg_by.get(season, []), rh_by.get(season, [])
        base = {
            'season': season,
            'games': len({r['game_id'] for r in tgr}) or None,
            'teams': len({r['club'] for r in tgr}) or None,
            'players': len({r['player_id'] for r in pgr}) or None,
        }
        for table, statlist in LEDGER_STATS.items():
            rows = {'team_game': tgr, 'player_game': pgr, 'role_history': rhr}[table]
            src = prov.get('schedules') if table == 'team_game' else prov.get('play_by_play', {})
            if table == 'team_game':
                s_entry = src if isinstance(src, dict) and 'state' in src else {}
            else:
                s_entry = (src or {}).get(season, {}) if isinstance(src, dict) else {}
            for stat in statlist:
                col = STAT_TO_COLUMN.get(stat, stat)
                claimed = era.available(stat, season)
                fs = field_state(rows, col)
                # a claim cannot promote an absent measurement
                state = (era.AVAILABLE if fs['state'] == era.AVAILABLE
                         else (era.NOT_AVAILABLE_FOR_ERA
                               if claimed == era.NOT_AVAILABLE_FOR_ERA
                               else era.UNKNOWN_PENDING_ACQUISITION))
                ledger.append({
                    **base, 'table': table, 'statistic': stat, 'column': col,
                    'source': s_entry.get('source'),
                    'source_tier': s_entry.get('tier'),
                    'retrieval_method': s_entry.get('retrieval_method'),
                    'source_timestamp': s_entry.get('source_timestamp'),
                    'source_digest': s_entry.get('source_digest'),
                    'completeness': fs['completeness'],
                    'n_rows': fs['n_rows'], 'n_era_sentinel': fs.get('n_sentinel', 0),
                    'claimed_window_state': claimed,
                    'state': state,
                })
    by_state = collections.Counter(r['state'] for r in ledger)
    art = {'artifact': 'COVERAGE_LEDGER', 'spec_version': SPEC_VERSION,
           'first_season': era.FIRST_SEASON, 'n_rows': len(ledger),
           'by_state': dict(by_state),
           'THREE_STATES': {
               era.AVAILABLE: 'measured present in this checkout',
               era.NOT_AVAILABLE_FOR_ERA: 'the football world did not record it in that season',
               era.UNKNOWN_PENDING_ACQUISITION: 'it exists upstream and we have not fetched it'},
           'WHY_NOT_A_README': ('a count in prose goes stale the moment a capture is added. This '
                                'is generated from the bytes on every run.'),
           'source_selection': prov,
           'rows': ledger}
    OUT.write_text(json.dumps(art, indent=1, sort_keys=True, default=str))

    # a readable matrix, because a 1,000-row ledger is not something a person reads
    lines = ['# Warehouse coverage ledger', '',
             f'Generated from the bytes. {len(ledger)} statistic-seasons, first season '
             f'{era.FIRST_SEASON}.', '',
             '`A` measured present. `E` not available for that era. `?` exists upstream, not '
             'fetched.', '']
    stats_all = []
    for table, sl in LEDGER_STATS.items():
        for s in sl:
            if (table, s) not in stats_all:
                stats_all.append((table, s))
    idx = {(r['season'], r['table'], r['statistic']): r for r in ledger}
    hdr = '| season | games | teams | players | ' + ' | '.join(
        s[:11] for _t, s in stats_all) + ' |'
    lines.append(hdr)
    lines.append('|' + '---|' * (4 + len(stats_all)))
    for season in range(era.FIRST_SEASON, 2027):
        row = idx.get((season, 'team_game', 'points')) or {}
        cells = []
        for table, s in stats_all:
            r = idx.get((season, table, s))
            if not r:
                cells.append(' ')
            elif r['state'] == era.AVAILABLE:
                cells.append('A' if r['completeness'] > 0.98 else
                             f"{int(r['completeness'] * 100)}")
            elif r['state'] == era.NOT_AVAILABLE_FOR_ERA:
                cells.append('E')
            else:
                cells.append('?')
        lines.append(f"| {season} | {row.get('games') or '-'} | {row.get('teams') or '-'} | "
                     f"{row.get('players') or '-'} | " + ' | '.join(cells) + ' |')
    OUT_MD.write_text('\n'.join(lines) + '\n')
    return Outcome.ok('COVERAGE_LEDGER_BUILT', {'n_rows': len(ledger), 'by_state': dict(by_state)},
                      f'{len(ledger)} statistic-seasons')


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    print('  by state:', o.value['by_state'])
    print(f'  -> {OUT.relative_to(_REPO)}')
    print(f'  -> {OUT_MD.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
