"""H1 step 1: the pregame-context table, one row per team-game, 2020-2025 REG.

WHAT THIS DOES NOT DO. It does not recompute any quantity the frozen QB
layer consumes. Attempts, completions, sacks, scrambles, designed rushes,
passing yards, touchdowns, interceptions, team plays and team dropbacks all
come from `nfl/research/qb2/qb.pkl`, which is the artifact
`nfl/production/qb_v1.FRAME_PATH` names and hashes. Rebuilding them here
would put a second copy of the definitions in the tree.

WHAT IT DOES. It reads only the fields the frozen layer does NOT carry and
that Question E needs: the game identifier, the opponent, the home flag, and
the two teams' scores. Everything else for the cuts is derived from qb.pkl.

MARKET COLUMNS ARE REFUSED BY NAME, on the same list `q7/panel.py` uses.
`spread_line`, `total_line`, `vegas_wp` and `vegas_wpa` are all present in
the source and none is read.
"""
from __future__ import annotations

import collections
import csv
import gzip
import hashlib
import json
import pathlib
import sys

csv.field_size_limit(10 ** 7)

_REPO = pathlib.Path(__file__).resolve().parents[4]
HERE = _REPO / 'nfl' / 'research' / 'v3' / 'h1'
RAW = _REPO / 'nfl' / 'research' / 'track1' / 'raw'
OUT = HERE / 'h1_team_context.csv.gz'
PROV = HERE / 'H1_CONTEXT_PROVENANCE.json'
SEASONS = (2020, 2021, 2022, 2023, 2024, 2025)

READ = ('game_id', 'season', 'season_type', 'week', 'posteam', 'defteam',
        'home_team', 'away_team', 'home_score', 'away_score',
        'rush_attempt', 'qb_kneel', 'qb_scramble', 'rushing_yards',
        'rusher_player_id')
FORBIDDEN = ('spread_line', 'total_line', 'vegas', 'moneyline', 'odds',
             'implied_prob')

bad = [c for c in READ if any(s in c.lower() for s in FORBIDDEN)]
if bad:
    raise SystemExit(f'H1_MARKET_COLUMN_IN_READ_LIST: {bad}')


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def build():
    rows, prov = [], []
    for s in SEASONS:
        p = RAW / f'play_by_play_{s}.csv.gz'
        if not p.exists():
            raise SystemExit(f'H1_RAW_SEASON_MISSING: {p}')
        games = {}
        rush = collections.defaultdict(lambda: [0, 0.0, 0])
        with gzip.open(p, 'rt', newline='') as fh:
            rd = csv.DictReader(fh)
            miss = [c for c in READ if c not in rd.fieldnames]
            if miss:
                raise SystemExit(f'H1_CONTEXT_FIELD_MISSING: {s} {miss}')
            for r in rd:
                if r.get('season_type') != 'REG':
                    continue
                gid = r.get('game_id')
                if not gid:
                    continue
                g = games.get(gid)
                if g is None:
                    g = games[gid] = {
                        'game_id': gid, 'season': s, 'week': _i(r.get('week')),
                        'home_team': r.get('home_team') or '',
                        'away_team': r.get('away_team') or '',
                        'home_score': _i(r.get('home_score')),
                        'away_score': _i(r.get('away_score'))}
                if not g['home_score'] and not g['away_score']:
                    g['home_score'] = _i(r.get('home_score'))
                    g['away_score'] = _i(r.get('away_score'))
                pos = r.get('posteam')
                if (pos and _i(r.get('rush_attempt'))
                        and (r.get('rusher_player_id') or '')
                        and not _i(r.get('qb_kneel'))):
                    k = (_i(r.get('week')), pos)
                    rush[k][0] += 1
                    rush[k][1] += float(r.get('rushing_yards') or 0.0)
                    if not _i(r.get('qb_scramble')):
                        rush[k][2] += 1
        if not games:
            raise SystemExit(f'H1_CONTEXT_EMPTY_SEASON: {s} produced no games')
        for g in games.values():
            for side in ('home', 'away'):
                me = g[f'{side}_team']
                you = g['away_team'] if side == 'home' else g['home_team']
                pf = g[f'{side}_score']
                pa = g['away_score'] if side == 'home' else g['home_score']
                if not me or not you:
                    raise SystemExit(
                        f'H1_CONTEXT_TEAMLESS_GAME: {g["game_id"]}')
                rk = rush.get((g['week'], me), [0, 0.0, 0])
                rows.append({'season': s, 'week': g['week'], 'team': me,
                             'opponent': you, 'game_id': g['game_id'],
                             'home': 1 if side == 'home' else 0,
                             'points_for': pf, 'points_against': pa,
                             'rush_plays': rk[0],
                             'rush_yards': round(rk[1], 1),
                             'designed_rush_plays': rk[2],
                             'ord': s * 100 + g['week']})
        raw = p.read_bytes()
        prov.append({'season': s, 'file': str(p.relative_to(_REPO)),
                     'sha256': hashlib.sha256(raw).hexdigest(),
                     'n_bytes': len(raw), 'n_games': len(games),
                     'source_name': 'nflverse_pbp', 'source_rank': 1})
    if not rows:
        raise SystemExit('H1_CONTEXT_EMPTY: no team-game rows. Empty is an '
                         'error, not a result.')
    seen = collections.Counter((r['season'], r['week'], r['team'])
                               for r in rows)
    dup = [k for k, v in seen.items() if v > 1]
    if dup:
        raise SystemExit(f'H1_CONTEXT_DUPLICATE_TEAM_WEEK: {dup[:5]}')
    rows.sort(key=lambda r: (r['ord'], r['team']))
    with gzip.open(OUT, 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    PROV.write_text(json.dumps({
        'artifact': 'NFL_H1_CONTEXT_PROVENANCE',
        'spec_version': 'h1-context-1',
        'market_columns_refused': list(FORBIDDEN),
        'fields_read': list(READ),
        'n_team_games': len(rows),
        'seasons': prov}, indent=1) + '\n')
    return {'team_game_rows': len(rows),
            'per_season': dict(collections.Counter(r['season'] for r in rows))}


def load():
    with gzip.open(OUT, 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit('H1_CONTEXT_EMPTY_READ')
    for r in rows:
        for k in ('season', 'week', 'ord', 'home', 'points_for',
                  'points_against', 'rush_plays', 'designed_rush_plays'):
            r[k] = int(r[k])
        r['rush_yards'] = float(r['rush_yards'])
    return rows


if __name__ == '__main__':
    print(json.dumps(build(), indent=1))
