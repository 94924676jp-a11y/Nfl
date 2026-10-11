#!/usr/bin/env python3.12
"""SIM-D9 measurement (PREREG_SIMD9.md section 2). League history only; no 2026 game is read.

    python3.12 nfl/research/accounting_repair/simd9_measure.py fit       -> SIMD9_FIT.json      (2021-2023)
    python3.12 nfl/research/accounting_repair/simd9_measure.py holdout   -> SIMD9_HOLDOUT.json  (2024-2025; refuses
                                                                            until SIMD9_DECISION.json exists)
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).parent
SETS = {'fit': (2021, 2022, 2023), 'holdout': (2024, 2025)}
BANDS = ((0.0, 0.10), (0.10, 0.18), (0.18, 0.25), (0.25, 1.01))
MIN_CLUB_TARGETS = 15
B, SEED = 2000, 20261011


def _pbp(season):
    hits = sorted((_REPO / 'nfl/research/postgame').glob(f'pbp_{season}.*.csv.gz'))
    if len(hits) != 1:
        raise SystemExit(f'pbp_{season}: expected one file, found {len(hits)}')
    with gzip.open(hits[0], 'rt', encoding='utf-8', newline='') as fh:
        yield from csv.DictReader(fh)


def units(seasons):
    """[(club_season, band, t, n, s_bar, c, r_bar)] for player-games with >= 1 target in club-games >= 15 targets."""
    club = collections.Counter()                       # (season, club, game) -> targets
    pg = collections.defaultdict(lambda: [0, 0])       # (season, club, game, player) -> [targets, catches]
    for s in seasons:
        for r in _pbp(s):
            if r.get('season_type') != 'REG' or r.get('pass_attempt') != '1' or not r.get('receiver_player_id') \
                    or not r.get('posteam'):
                continue
            k = (s, r['posteam'], r['game_id'])
            club[k] += 1
            x = pg[k + (r['receiver_player_id'],)]
            x[0] += 1
            x[1] += r.get('complete_pass') == '1'
    keep = {k for k, n in club.items() if n >= MIN_CLUB_TARGETS}
    season_sum = collections.defaultdict(lambda: [0.0, 0, 0, 0])   # (season, club, player) -> [share sum, games, t, c]
    for (s, c, g, p), (t, cat) in pg.items():
        if (s, c, g) in keep:
            a = season_sum[(s, c, p)]
            a[0] += t / club[(s, c, g)]
            a[1] += 1
            a[2] += t
            a[3] += cat
    out = []
    for (s, c, g, p), (t, cat) in pg.items():
        if (s, c, g) not in keep:
            continue
        a = season_sum[(s, c, p)]
        sb = a[0] / a[1]
        rb = a[3] / a[2] if a[2] else 0.0
        band = next(i for i, (lo, hi) in enumerate(BANDS) if lo <= sb < hi)
        out.append(((s, c), band, t, club[(s, c, g)], sb, cat, rb))
    return out


def ratios(us):
    num_t = collections.defaultdict(float)
    den_t = collections.defaultdict(float)
    num_c = collections.defaultdict(float)
    den_c = collections.defaultdict(float)
    nbar = collections.defaultdict(list)
    for _cs, b, t, n, sb, c, rb in us:
        num_t[b] += (t - n * sb) ** 2
        den_t[b] += n * sb * (1 - sb)
        num_c[b] += (c - t * rb) ** 2
        den_c[b] += t * rb * (1 - rb)
        nbar[b].append(n)
    return {b: {'R_targets': num_t[b] / den_t[b] if den_t[b] else None,
                'R_catches': num_c[b] / den_c[b] if den_c[b] else None,
                'n_bar': sum(nbar[b]) / len(nbar[b]), 'n_units': len(nbar[b])} for b in nbar}


def measure(which):
    us = units(SETS[which])
    point = ratios(us)
    by_block = collections.defaultdict(list)
    for u in us:
        by_block[u[0]].append(u)
    blocks = list(by_block)
    rng = random.Random(SEED)
    boot = collections.defaultdict(lambda: {'R_targets': [], 'R_catches': []})
    for _ in range(B):
        samp = [u for _k in range(len(blocks)) for u in by_block[blocks[rng.randrange(len(blocks))]]]
        for b, v in ratios(samp).items():
            for f in ('R_targets', 'R_catches'):
                if v[f] is not None:
                    boot[b][f].append(v[f])

    def ci(xs):
        xs = sorted(xs)
        return [round(xs[int(0.025 * (len(xs) - 1))], 4), round(xs[int(0.975 * (len(xs) - 1))], 4)]
    pooled = ratios([(u[0], 0) + u[2:] for u in us])[0]
    res = {}
    for b in sorted(point):
        v = point[b]
        rt = v['R_targets']
        res[f'{BANDS[b][0]:.2f}-{BANDS[b][1]:.2f}'] = {
            'n_units': v['n_units'], 'n_bar': round(v['n_bar'], 3),
            'R_targets': round(rt, 4), 'R_targets_ci95': ci(boot[b]['R_targets']),
            'concentration': round((v['n_bar'] - rt) / (rt - 1), 2) if rt > 1 else None,
            'state': 'OVER_DISPERSED' if rt > 1 else 'UNDER_DISPERSED',
            'R_catches': round(v['R_catches'], 4), 'R_catches_ci95': ci(boot[b]['R_catches'])}
    return {'ARTIFACT': f'SIMD9_{which.upper()}', 'prereg': 'PREREG_SIMD9.md', 'seasons': list(SETS[which]),
            'bootstrap': {'B': B, 'seed': SEED, 'block': 'club-season', 'n_blocks': len(blocks)},
            'pooled': {'R_targets': round(pooled['R_targets'], 4), 'R_catches': round(pooled['R_catches'], 4),
                       'n_bar': round(pooled['n_bar'], 3), 'n_units': pooled['n_units']},
            'bands': res,
            'NOTE': 'season-mean shares and catch rates: within-season role drift inflates every ratio (upper bounds)'}


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'fit'
    if which not in SETS:
        raise SystemExit(f'usage: {sys.argv[0]} fit|holdout')
    if which == 'holdout' and not (HERE / 'SIMD9_DECISION.json').exists():
        raise SystemExit('REFUSED: the hold-out is read only after SIMD9_DECISION.json records the section 3 decision')
    doc = measure(which)
    (HERE / f'SIMD9_{which.upper()}.json').write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps(doc, indent=1))
