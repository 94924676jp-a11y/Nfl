#!/usr/bin/env python3.12
"""Lower-tail calibration of the Showdown worlds: how often does a high-scoring player have a dud game?

    python3.12 nfl/research/tail_calibration/star_dud_rate.py STATS_DIR [--worlds DRAWS.json ...] [--out OUT.json]

STATS_DIR holds nflverse stats_player_week_<season>.csv for 2021-2025 (release `stats_player`; the sha256 of every file
used is recorded in the output). For each WR/RB/TE game with at least three prior games that season, the condition is
the player's season-to-date DK mean (PPR + the DK 100-yard bonus); the outcome is the next game's DK points.

EMPIRICAL quantities: P(DK < 5) and P(DK < 0.25 x prior mean) by prior-mean band and position, with a cluster bootstrap
over PLAYER-SEASONS (games of one player-season are not independent). WORLD quantities: the same probabilities in our
published draws for every player whose simulated mean falls in a band.

What it can and cannot say. The season-to-date mean is a noisy, regressing predictor, so the empirical dud rate given a
high prior mean is an UPPER-leaning reference for a player whose true mean is that high. A world whose dud rate is an
order of magnitude below even the P(< 0.25 x mean) reference is under-dispersed in the lower tail; a factor of 1.5 would
not be distinguishable. Nothing here changes a forecast.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

import numpy as np
import pandas as pd

BANDS = ((20, 1e9), (15, 20), (10, 15))


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def empirical(stats_dir, seasons=range(2021, 2026), n_boot=1000, seed=20261009):
    fr, src = [], {}
    for y in seasons:
        p = pathlib.Path(stats_dir) / f'stats_player_week_{y}.csv'
        src[p.name] = _sha(p)
        s = pd.read_csv(p, low_memory=False)
        s = s[(s.season_type == 'REG') & s.position.isin(['WR', 'TE', 'RB'])].copy()
        if s.empty:
            raise RuntimeError(f'EMPTY_STATS {p}')
        s['dk'] = s.fantasy_points_ppr.fillna(0) + 3 * ((s.receiving_yards.fillna(0) >= 100)
                                                         | (s.rushing_yards.fillna(0) >= 100))
        s = s.sort_values(['player_id', 'week'])
        s['prior_mean'] = s.groupby('player_id').dk.transform(lambda x: x.shift().expanding().mean())
        s['prior_n'] = s.groupby('player_id').cumcount()
        s['cluster'] = s.player_id.astype(str) + f'_{y}'
        fr.append(s)
    a = pd.concat(fr)
    a = a[a.prior_n >= 3]
    rng = np.random.default_rng(seed)
    out = {}
    for lo, hi in BANDS:
        x = a[(a.prior_mean >= lo) & (a.prior_mean < hi)]
        for pos in ('ALL', 'WR', 'RB', 'TE'):
            xp = x if pos == 'ALL' else x[x.position == pos]
            if len(xp) < 50:
                continue
            g = xp.groupby('cluster')
            lt5 = g.apply(lambda d: ((d.dk < 5).sum(), len(d)), include_groups=False)
            num = np.array([v[0] for v in lt5]); den = np.array([v[1] for v in lt5])
            bs = [num[i].sum() / den[i].sum() for i in (rng.integers(0, len(num), len(num)) for _ in range(n_boot))]
            out[f'{lo:g}-{hi:g}|{pos}'] = {
                'n_games': int(len(xp)), 'n_player_seasons': int(len(num)),
                'p_lt5': round(float(num.sum() / den.sum()), 4),
                'p_lt5_cluster_boot_95': [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)],
                'p_lt_quarter_mean': round(float((xp.dk < 0.25 * xp.prior_mean).mean()), 4)}
    return out, src


def worlds(paths):
    out = []
    for p in paths:
        d = json.loads(pathlib.Path(p).read_text())
        for k, v in d['draws'].items():
            v = np.asarray(v, dtype=float)
            if v.mean() >= 10:
                out.append({'worlds': pathlib.Path(p).name, 'player': k, 'mean': round(float(v.mean()), 2),
                            'p_lt5': round(float((v < 5).mean()), 4),
                            'p_lt_quarter_mean': round(float((v < 0.25 * v.mean()).mean()), 4)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stats_dir')
    ap.add_argument('--worlds', nargs='*', default=[])
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    emp, src = empirical(a.stats_dir)
    doc = {'ARTIFACT': 'STAR_DUD_RATE', 'sources_sha256': src, 'empirical': emp, 'worlds': worlds(a.worlds),
           'READING': __doc__.split('What it can and cannot say.')[1].strip()}
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps(doc['empirical'], indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
