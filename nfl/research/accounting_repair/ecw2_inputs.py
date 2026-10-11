#!/usr/bin/env python3.12
"""ECW-2 measured inputs from 2021-2025 regular-season play-by-play (league history; no slate outcome is read).

    python3.12 nfl/research/accounting_repair/ecw2_inputs.py      -> ECW2_INPUTS.json

  overtime     how regular-season games tied at the end of regulation end: still tied, won by a field goal (margin 3),
               or won by a touchdown (margin >= 6), and the home side's share of OT wins. Feeds ECW-D1 (ties).
  catch_shape  the distribution of yards on a single reception divided by that player-season's mean yards per
               reception (player-seasons with >= 20 receptions), on a 201-point quantile grid. Scale-free, so any
               player's catch yards are his projected yards-per-catch times draws from this shape. Feeds ECW-D4
               (receiver dispersion: the raw simulator's per-world yards-per-target ratio widened every receiver).
  benchmark    the historical coefficient of variation of single-game receiving yards for receivers with > 2 catches,
               the number ECW-D4 compared against (median 0.53 per the 2026-10-09 evaluation), recomputed here.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).parent
SEASONS = (2021, 2022, 2023, 2024, 2025)


def _pbp(season):
    hits = sorted((_REPO / 'nfl/research/postgame').glob(f'pbp_{season}.*.csv.gz'))
    if len(hits) != 1:
        raise SystemExit(f'pbp_{season}: expected one file, found {len(hits)}')
    with gzip.open(hits[0], 'rt', encoding='utf-8', newline='') as fh:
        yield from csv.DictReader(fh)


def main() -> int:
    games = {}
    catches = collections.defaultdict(list)            # (season, player) -> yards per reception
    game_rec = collections.defaultdict(lambda: [0, 0.0])  # (game, player) -> [receptions, yards]
    for s in SEASONS:
        for r in _pbp(s):
            if r.get('season_type') != 'REG':
                continue
            g = games.setdefault(r['game_id'], {'reg_home': None, 'reg_away': None, 'final_home': None,
                                                'final_away': None, 'ot': False})
            try:
                th, ta = float(r['total_home_score']), float(r['total_away_score'])
            except (TypeError, ValueError):
                continue
            q = r.get('qtr')
            if q in ('1', '2', '3', '4'):
                g['reg_home'], g['reg_away'] = th, ta
            elif q and int(float(q)) >= 5:
                g['ot'] = True
            g['final_home'], g['final_away'] = th, ta
            if r.get('complete_pass') == '1' and r.get('receiver_player_id'):
                try:
                    y = float(r.get('receiving_yards') or r.get('yards_gained') or 0)
                except ValueError:
                    continue
                catches[(s, r['receiver_player_id'])].append(y)
                gr = game_rec[(r['game_id'], r['receiver_player_id'])]
                gr[0] += 1
                gr[1] += y
    tied = [g for g in games.values() if g['reg_home'] is not None and g['reg_home'] == g['reg_away']]
    out_ot = collections.Counter()
    home_wins = 0
    for g in tied:
        m = g['final_home'] - g['final_away']
        if m == 0:
            out_ot['TIE'] += 1
        elif abs(m) == 3:
            out_ot['FG'] += 1
        elif abs(m) >= 6:
            out_ot['TD'] += 1
        else:
            out_ot[f'OTHER_MARGIN_{abs(m):g}'] += 1
        home_wins += m > 0
    n_t = len(tied)
    ratios = []
    for (_s, _p), ys in catches.items():
        if len(ys) >= 20:
            m = statistics.mean(ys)
            if m > 0:
                ratios += [y / m for y in ys]
    ratios.sort()
    grid = [round(ratios[min(len(ratios) - 1, int(i / 200 * (len(ratios) - 1)))], 5) for i in range(201)]
    cvs = []
    by_player = collections.defaultdict(list)
    for (gid, p), (n, y) in game_rec.items():
        if n > 2:
            by_player[(gid[:4], p)].append(y)
    for v in by_player.values():
        if len(v) >= 6 and statistics.mean(v) > 0:
            cvs.append(statistics.pstdev(v) / statistics.mean(v))
    doc = {'ARTIFACT': 'ECW2_INPUTS', 'seasons': list(SEASONS), 'source': 'nfl/research/postgame/pbp_<season>.*.csv.gz, REG',
           'overtime': {'n_regular_season_games': len(games), 'n_tied_after_regulation': n_t,
                        'share_tied_after_regulation': round(n_t / len(games), 5) if games else None,
                        'outcomes': dict(out_ot), 'p': {k: round(v / n_t, 5) for k, v in out_ot.items()} if n_t else {},
                        'home_share_of_ot_wins': round(home_wins / max(1, n_t - out_ot['TIE']), 5),
                        'final_tie_share_of_all_games': round(out_ot['TIE'] / len(games), 5) if games else None},
           'catch_shape': {'n_receptions': len(ratios), 'n_player_seasons_min20': sum(1 for v in catches.values()
                                                                                    if len(v) >= 20),
                           'mean': round(statistics.mean(ratios), 5), 'cv': round(statistics.pstdev(ratios), 5),
                           'quantiles_201': grid},
           'benchmark_receiving_yards_cv_gt2_catches': {'n_player_seasons': len(cvs),
                                                         'median_cv': round(statistics.median(cvs), 4) if cvs else None,
                                                         'definition': 'within player-season SD/mean of single-game '
                                                                       'receiving yards, games with > 2 catches, '
                                                                       'player-seasons with >= 6 such games'}}
    (HERE / 'ECW2_INPUTS.json').write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps({k: v for k, v in doc['overtime'].items()}))
    print({k: v for k, v in doc['catch_shape'].items() if k != 'quantiles_201'})
    print(doc['benchmark_receiving_yards_cv_gt2_catches'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
