#!/usr/bin/env python3.12
"""Player-game table. One row per player per game, with DK scoring under CURRENT rules.

SCORED UNDER TODAY'S RULES ON PURPOSE. A 2021 game is scored with the 2026 DraftKings scoring so
that a historical prior is expressed in the units the product predicts. The alternative -- each
season under its contemporary scoring -- answers a different question and would make a prior
incomparable across seasons. Recorded here because it is a choice, not an accident.

COVERAGE. Built from the play-by-play captures this checkout holds. A season without a capture is
absent from the table entirely rather than present with zeros, and coverage.py records which seasons
those are. Play-by-play exists upstream from 1977, so a missing season is an ACQUISITION gap.

WHAT IS DERIVABLE HERE AND WHAT IS NOT.

  derivable     attempts, completions, yards, touchdowns, interceptions, sacks taken, carries,
                targets, receptions, air yards, red-zone and goal-line usage by TYPE, down-and-
                distance splits, game participation
  NOT derivable snap counts before 2012 (era.py), routes run at any season in this checkout,
                alignment (slot, wide, inline). Roster position is NOT alignment and is never used
                as a proxy for it.

PARTICIPATION IS AN OPPORTUNITY ROW, NOT A SNAP. A player appears here when he recorded an
opportunity -- a target, a carry, an attempt -- or was credited with a touchdown. That is not the
same as playing, and the field is named `opportunity_row` rather than `played` so no consumer can
read it as participation.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import era, sources  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'player-game-1'
OUT_DIR = _REPO / 'nfl/warehouse'
OUT = OUT_DIR / 'PLAYER_GAME.json'

#: Current DraftKings classic scoring, read from the contest rules.
DK = {'pass_yd': 0.04, 'pass_td': 4.0, 'int': -1.0, 'rush_yd': 0.1, 'rush_td': 6.0,
      'rec': 1.0, 'rec_yd': 0.1, 'rec_td': 6.0, 'fumble_lost': -1.0,
      'bonus_100_rush': 3.0, 'bonus_100_rec': 3.0, 'bonus_300_pass': 3.0,
      'two_point': 2.0}

COUNTERS = (
    'pass_attempts', 'completions', 'passing_yards', 'passing_td', 'interceptions_thrown',
    'sacks_taken', 'carries', 'rushing_yards', 'rushing_td', 'targets', 'receptions',
    'receiving_yards', 'receiving_td', 'air_yards', 'fumbles_lost',
    'rz_targets', 'rz_carries', 'gl_targets', 'gl_carries',
    'early_down_carries', 'late_down_carries', 'third_down_targets', 'first_down_targets',
    'two_point_conversions', 'designed_runs', 'scramble_runs',
)


def _f(v, d=0.0):
    if v is None:
        return d
    t = str(v).strip()
    if t in ('', 'NA', 'None', 'nan'):
        return d
    try:
        return float(t)
    except ValueError:
        return d


def dk_points(r):
    """DK points for one player-game row under current rules."""
    pts = (_f(r.get('passing_yards')) * DK['pass_yd']
           + _f(r.get('passing_td')) * DK['pass_td']
           - _f(r.get('interceptions_thrown')) * abs(DK['int'])
           + _f(r.get('rushing_yards')) * DK['rush_yd']
           + _f(r.get('rushing_td')) * DK['rush_td']
           + _f(r.get('receptions')) * DK['rec']
           + _f(r.get('receiving_yards')) * DK['rec_yd']
           + _f(r.get('receiving_td')) * DK['rec_td']
           - _f(r.get('fumbles_lost')) * abs(DK['fumble_lost'])
           + _f(r.get('two_point_conversions')) * DK['two_point'])
    if _f(r.get('rushing_yards')) >= 100:
        pts += DK['bonus_100_rush']
    if _f(r.get('receiving_yards')) >= 100:
        pts += DK['bonus_100_rec']
    if _f(r.get('passing_yards')) >= 300:
        pts += DK['bonus_300_pass']
    return round(pts, 4)


def build_season(season):
    o = sources.select(sources.registry()['play_by_play'], season=season)
    if o.state.name != 'PASS':
        return {'state': era.UNKNOWN_PENDING_ACQUISITION, 'reason': o.code,
                'NOTE': ('play-by-play exists upstream from 1977, so a season missing here is an '
                         'acquisition gap. The season is ABSENT from the table rather than present '
                         'with zeros.')}
    path = _REPO / o.value['selected']
    agg = collections.defaultdict(lambda: collections.Counter())
    meta = {}
    with gzip.open(path, 'rt', newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r.get('season_type') != 'REG':
                continue
            gid = r.get('game_id')
            if not gid:
                continue
            wk = r.get('week')
            pt, dt = r.get('posteam'), r.get('defteam')
            pl = (r.get('play_type') or '').strip()
            yl = _f(r.get('yardline_100'), None)
            down = _f(r.get('down'), None)
            two = r.get('two_point_attempt') == '1'

            def touch(pid, club):
                if not pid:
                    return None
                k = (gid, pid)
                meta.setdefault(k, {'game_id': gid, 'season': season, 'week': wk,
                                    'player_id': pid, 'club': club,
                                    'opponent': (dt if club == pt else pt)})
                return agg[k]

            # passer
            pid = (r.get('passer_player_id') or '').strip()
            if pid and pl == 'pass':
                c = touch(pid, pt)
                if two:
                    if r.get('two_point_conv_result') == 'success':
                        c['two_point_conversions'] += 1
                else:
                    c['pass_attempts'] += 1
                    if r.get('complete_pass') == '1':
                        c['completions'] += 1
                        c['passing_yards'] += _f(r.get('passing_yards'))
                    if r.get('pass_touchdown') == '1':
                        c['passing_td'] += 1
                    if r.get('interception') == '1':
                        c['interceptions_thrown'] += 1
            # sacked quarterback
            sid = (r.get('passer_player_id') or '').strip()
            if r.get('sack') == '1' and sid:
                touch(sid, pt)['sacks_taken'] += 1
            # rusher
            rid = (r.get('rusher_player_id') or '').strip()
            if rid and pl == 'run':
                c = touch(rid, pt)
                if two:
                    if r.get('two_point_conv_result') == 'success':
                        c['two_point_conversions'] += 1
                else:
                    c['carries'] += 1
                    c['rushing_yards'] += _f(r.get('rushing_yards'))
                    if r.get('rush_touchdown') == '1':
                        c['rushing_td'] += 1
                    if yl is not None and yl <= 20:
                        c['rz_carries'] += 1
                    if yl is not None and yl <= 5:
                        c['gl_carries'] += 1
                    if down is not None:
                        if down <= 2:
                            c['early_down_carries'] += 1
                        else:
                            c['late_down_carries'] += 1
                    if r.get('qb_scramble') == '1':
                        c['scramble_runs'] += 1
                    else:
                        c['designed_runs'] += 1
            # receiver
            wid = (r.get('receiver_player_id') or '').strip()
            if wid and pl == 'pass':
                c = touch(wid, pt)
                if two:
                    if r.get('two_point_conv_result') == 'success':
                        c['two_point_conversions'] += 1
                else:
                    c['targets'] += 1
                    c['air_yards'] += _f(r.get('air_yards'))
                    if r.get('complete_pass') == '1':
                        c['receptions'] += 1
                        c['receiving_yards'] += _f(r.get('receiving_yards'))
                    if r.get('pass_touchdown') == '1':
                        c['receiving_td'] += 1
                    if yl is not None and yl <= 20:
                        c['rz_targets'] += 1
                    if yl is not None and yl <= 5:
                        c['gl_targets'] += 1
                    if down is not None:
                        if down == 1:
                            c['first_down_targets'] += 1
                        elif down >= 3:
                            c['third_down_targets'] += 1
            # fumbles lost, credited to whoever fumbled
            fid = (r.get('fumbled_1_player_id') or '').strip()
            if r.get('fumble_lost') == '1' and fid:
                ft = r.get('fumbled_1_team') or pt
                touch(fid, ft)['fumbles_lost'] += 1

    rows = {}
    for k, c in agg.items():
        row = dict(meta[k])
        for f in COUNTERS:
            row[f] = (round(c[f], 2) if f in ('passing_yards', 'rushing_yards',
                                              'receiving_yards', 'air_yards') else int(c[f]))
        row['opportunity_row'] = True
        row['OPPORTUNITY_NOT_PARTICIPATION'] = True
        row['snap_counts'] = (era.NOT_AVAILABLE_FOR_ERA if season < 2012
                              else era.UNKNOWN_PENDING_ACQUISITION)
        row['routes_run'] = era.UNKNOWN_PENDING_ACQUISITION
        row['alignment'] = era.UNKNOWN_PENDING_ACQUISITION
        row['dk_points_current_rules'] = dk_points(row)
        rows[f'{k[0]}|{k[1]}'] = row
    return {'state': 'BUILT', 'source': o.value['selected'], 'rows': rows,
            'n_player_games': len(rows)}


def build(seasons=range(era.FIRST_SEASON, 2027)):
    table, per_season = {}, {}
    for s in seasons:
        r = build_season(s)
        if r['state'] != 'BUILT':
            per_season[s] = {'state': r['state'], 'reason': r.get('reason')}
            continue
        table.update(r['rows'])
        pts = [v['dk_points_current_rules'] for v in r['rows'].values()]
        per_season[s] = {
            'state': 'BUILT', 'source': r['source'], 'n_player_games': r['n_player_games'],
            'n_players': len({v['player_id'] for v in r['rows'].values()}),
            'n_games': len({v['game_id'] for v in r['rows'].values()}),
            'n_clubs': len({v['club'] for v in r['rows'].values()}),
            'n_weeks': len({v['week'] for v in r['rows'].values()}),
            'mean_dk_points': round(sum(pts) / len(pts), 4) if pts else None,
            'max_dk_points': round(max(pts), 2) if pts else None,
            'snap_counts': (era.NOT_AVAILABLE_FOR_ERA if s < 2012
                            else era.UNKNOWN_PENDING_ACQUISITION),
        }
    if not table:
        return Outcome.blocked('PLAYER_GAME_EMPTY', 'no season produced rows', cause=Cause.DATA)
    art = {'artifact': 'PLAYER_GAME', 'spec_version': SPEC_VERSION,
           'n_player_games': len(table),
           'SCORED_UNDER': 'CURRENT DraftKings classic rules, for every season',
           'WHY': ('a historical prior must be expressed in the units the product predicts. Scoring '
                   'each season under its contemporary rules answers a different question and would '
                   'make priors incomparable across seasons.'),
           'ABSENT_SEASON_SEMANTICS': ('a season without a play-by-play capture is ABSENT from this '
                                       'table, never present with zeros'),
           'per_season': per_season, 'counters': list(COUNTERS), 'rows': table}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, separators=(',', ':'), sort_keys=True))
    return Outcome.ok('PLAYER_GAME_BUILT', {'per_season': per_season, 'n': len(table)},
                      f'{len(table)} player-games')


def main() -> int:
    o = build()
    print(o.render() if hasattr(o, 'render') else f'{o.state.name}[{o.code}]')
    if o.state.name != 'PASS':
        return 1
    ps = o.value['per_season']
    built = [s for s, v in ps.items() if v['state'] == 'BUILT']
    absent = [s for s, v in ps.items() if v['state'] != 'BUILT']
    print(f"  {o.value['n']} player-games; built {len(built)} seasons, absent {len(absent)}")
    print(f"  {'yr':>5s} {'pgames':>7s} {'players':>7s} {'games':>6s} {'wks':>4s} "
          f"{'meanDK':>7s} {'maxDK':>6s} snaps")
    for s in built:
        v = ps[s]
        print(f"  {s:5d} {v['n_player_games']:7d} {v['n_players']:7d} {v['n_games']:6d} "
              f"{v['n_weeks']:4d} {v['mean_dk_points']:7.3f} {v['max_dk_points']:6.1f} "
              f"{v['snap_counts']}")
    if absent:
        print(f"  ABSENT (acquisition gap, never zero-filled): {absent[0]}-{absent[-1]}")
    print(f"  -> {OUT.relative_to(_REPO)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
