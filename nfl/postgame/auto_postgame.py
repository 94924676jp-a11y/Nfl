#!/usr/bin/env python3.12
"""Recurring postgame runner: find every configured Showdown slate whose game is final in nflverse, and grade it.

    python3.12 nfl/postgame/auto_postgame.py [--pbp LOCAL_PBP_GZ] [--history TAG=DK_ENTRY_HISTORY.csv ...]

For each nfl/postgame/*/POSTGAME_CONFIG.json without a written <tag>_POSTGAME.json:
  1. obtain nflverse play-by-play (download from the nflverse-data GitHub release, or --pbp), content-addressed;
  2. if the game is absent or not final, record PENDING with the reason in POSTGAME_STATUS.json and move on --
     an absent game is never graded against absence;
  3. otherwise run showdown_postgame.run (frozen-artifact hash check first), and cross-check the pbp-derived player
     lines against nflverse's own weekly player stats when that file carries the game.

It never retrains, re-projects or promotes anything, and its outputs are never forecast inputs (POSTGAME_ACTUAL layer).
Contest financials stay UNKNOWN unless an authenticated DK entry-history export is supplied for the tag.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import sys
import tempfile
import urllib.request

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import join_provenance as JP  # noqa: E402
from nfl.postgame import showdown_postgame as SP  # noqa: E402

PBP_URL = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz'
STATS_URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'
#: pbp-derived line field -> nflverse weekly stats column, for the cross-check
CROSS = {'pass_yds': 'passing_yards', 'pass_td': 'passing_tds', 'int': 'passing_interceptions', 'carries': 'carries',
         'rush_yds': 'rushing_yards', 'rush_td': 'rushing_tds', 'targets': 'targets', 'rec': 'receptions',
         'rec_yds': 'receiving_yards', 'rec_td': 'receiving_tds'}


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def fetch(url, dest):
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, 'wb') as f:
        f.write(r.read())
    if pathlib.Path(dest).stat().st_size == 0:
        raise SP.PostgameError(f'EMPTY_DOWNLOAD {url}')
    return dest


def cross_check(doc, state, stats_csv, game):
    """Our pbp aggregation against nflverse's published player stats for the same game. Disagreement is reported by
    player and field; it is how a scorer bug would show up."""
    rows = [r for r in csv.DictReader(open(stats_csv)) if r.get('game_id') == game]
    if not rows:
        return {'STATUS': 'NOT_AVAILABLE', 'reason': f'stats_player_week has no rows for {game} yet'}
    by = {r['player_id']: r for r in rows}
    diffs, n = [], 0
    for v in state['players'].values():
        k = f"{v['name']}|{v['team']}"
        a = doc['player_actuals'].get(k)
        if not a or a['pos'] in ('K', 'DST'):
            continue
        r = by.get(v.get('gsis_id'))
        s = a['stats']
        for ours, theirs in CROSS.items():
            t = float(r.get(theirs) or 0) if r else 0.0
            n += 1
            if abs(float(s.get(ours, 0)) - t) > 1e-6:
                diffs.append({'player': k, 'field': ours, 'pbp_derived': float(s.get(ours, 0)), 'nflverse_stats': t})
    return {'STATUS': 'AGREE' if not diffs else 'DISAGREE', 'cells_compared': n, 'disagreements': diffs}


def run_all(pbp=None, histories=None, configs=None):
    histories = histories or {}
    out = []
    cfgs = configs or sorted((_REPO / 'nfl/postgame').glob('*/POSTGAME_CONFIG.json'))
    with tempfile.TemporaryDirectory() as td:
        cache = {}
        for cp in cfgs:
            cfg = json.loads(pathlib.Path(cp).read_text())
            od = _REPO / cfg['out_dir']
            done = od / f"{cfg['tag']}_POSTGAME.json"
            status = od / 'POSTGAME_STATUS.json'
            if done.exists():
                out.append({'tag': cfg['tag'], 'state': 'ALREADY_GRADED'})
                continue
            season = int(cfg['game'][:4])
            try:
                if pbp:
                    pf = pbp
                else:
                    if season not in cache:
                        cache[season] = fetch(PBP_URL.format(season=season), f'{td}/pbp_{season}.csv.gz')
                    pf = cache[season]
                doc = SP.run(cp, pf, histories.get(cfg['tag']))
                try:
                    sp = fetch(STATS_URL.format(season=season), f'{td}/stats_{season}.csv')
                    sd = _REPO / cfg['forecast_scenario_dir']
                    st = json.loads(next(sd.glob('SHOWDOWN_*_STATE.json')).read_text())
                    doc['nflverse_stats_cross_check'] = cross_check(doc, st, sp, cfg['game'])
                except Exception as e:  # noqa: BLE001 -- the cross-check is advisory; its absence is recorded
                    doc['nflverse_stats_cross_check'] = {'STATUS': 'NOT_RUN', 'reason': repr(e)[:200]}
                # A slate is GRADED only if every scored player row proves its join (join_provenance contract).
                for k, r in doc['player_actuals'].items():
                    JP.assert_graded_row(r, actual=r['dk_A'], where=f"{cfg['tag']}:{k}")
                done.write_text(json.dumps(doc, indent=1, default=float) + '\n')
                rec = {'tag': cfg['tag'], 'state': 'GRADED', 'at': _now(), 'final': doc['final_score'],
                       'cross_check': doc['nflverse_stats_cross_check']['STATUS']}
            except SP.PostgameError as e:
                rec = {'tag': cfg['tag'], 'state': 'PENDING', 'at': _now(), 'reason': str(e)}
            od.mkdir(parents=True, exist_ok=True)
            hist = json.loads(status.read_text()) if status.exists() else []
            hist.append(rec)
            status.write_text(json.dumps(hist, indent=1) + '\n')
            out.append(rec)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--pbp')
    ap.add_argument('--history', action='append', default=[], help='TAG=PATH to a DK entry-history export')
    a = ap.parse_args(argv)
    hist = dict(h.split('=', 1) for h in a.history)
    res = run_all(a.pbp, hist)
    print(json.dumps(res, indent=1, default=str))
    return 0 if all(r['state'] != 'PENDING' for r in res) else 3


if __name__ == '__main__':
    raise SystemExit(main())
