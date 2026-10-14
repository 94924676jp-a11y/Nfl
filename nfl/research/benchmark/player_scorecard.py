"""Benchmark mandate (2026-10-14), player scorecard step 2: metrics, paired comparisons and error decomposition from the
rows written by player_rows.py.

    python3.12 nfl/research/benchmark/player_scorecard.py STRICT_ROWS.json [LEGACY_ROWS.json] > SCORECARD.json

Every paired difference is computed on the SAME player-weeks and its uncertainty is a WEEK-BLOCKED bootstrap (players
within a week share games and clubs, so player-weeks are not independent; 10,000 resamples, seed 20261014). A
difference whose 95% interval spans zero is not a finding. Lower MAE/RMSE is better. Nothing here is fitted."""
import collections
import json
import math
import random
import statistics
import sys

PRED = ('proj', 'STD', 'L3', 'PRIOR_SEASON')
B, SEED = 10000, 20261014


def load(p):
    return json.load(open(p))


def metrics(rows, k):
    e = [r[k] - r['actual'] for r in rows]
    xs, ys = [r[k] for r in rows], [r['actual'] for r in rows]
    n = len(rows)
    out = {'n': n, 'mae': sum(abs(x) for x in e) / n, 'rmse': math.sqrt(sum(x * x for x in e) / n),
           'bias': sum(e) / n, 'level_ratio': (sum(xs) / sum(ys)) if sum(ys) else None}
    try:
        out['pearson'] = statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        out['pearson'] = None
    return {a: (round(b, 4) if isinstance(b, float) else b) for a, b in out.items()}


def blocked_diff(rows, a, b, stat='abs'):
    """Week-blocked bootstrap of mean(loss_a - loss_b); loss = |error| or error^2."""
    f = (lambda r, k: abs(r[k] - r['actual'])) if stat == 'abs' else (lambda r, k: (r[k] - r['actual']) ** 2)
    by = collections.defaultdict(list)
    for r in rows:
        by[(r['season'], r['week'])].append(f(r, a) - f(r, b))
    blocks = list(by.values())
    tot = sum(sum(x) for x in blocks) / sum(len(x) for x in blocks)
    rng = random.Random(SEED)
    bs = []
    for _ in range(B):
        s = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        bs.append(sum(sum(x) for x in s) / sum(len(x) for x in s))
    bs.sort()
    return {'diff': round(tot, 4), 'ci95': [round(bs[int(0.025 * B)], 4), round(bs[int(0.975 * B) - 1], 4)],
            'n_weeks': len(blocks), 'n_rows': sum(len(x) for x in blocks)}


def scorecard(rows, preds):
    """Metrics, paired week-blocked comparisons of `proj` against each baseline, and decompositions, over the rows
    where every predictor in `preds` exists."""
    common = [r for r in rows if all(r.get(k) is not None for k in preds)]
    out = {'n_rows_all': len(rows), 'n_rows_common': len(common),
           'coverage_common': round(len(common) / len(rows), 4) if rows else None,
           'n_weeks': len({(r['season'], r['week']) for r in rows})}
    out['overall'] = {k: metrics(common, k) for k in preds}
    out['paired_vs_baselines'] = {b: {'mae': blocked_diff(common, 'proj', b, 'abs'),
                                      'mse': blocked_diff(common, 'proj', b, 'sq')} for b in preds[1:]}
    ref = preds[1]
    by = collections.defaultdict(list)
    for r in common:
        by[r['pos']].append(r)
    out['by_position'] = {p: {'incumbent': metrics(v, 'proj'), ref: metrics(v, ref),
                              f'incumbent_minus_{ref}_mae': blocked_diff(v, 'proj', ref, 'abs')}
                          for p, v in sorted(by.items()) if len(v) >= 50}
    wk = collections.defaultdict(list)
    for r in common:
        wk[r['week']].append(r)
    out['by_week_of_season'] = {w: {'n': len(v), 'mae_incumbent': metrics(v, 'proj')['mae'],
                                    f'mae_{ref}': metrics(v, ref)['mae'], 'bias_incumbent': metrics(v, 'proj')['bias']}
                                for w, v in sorted(wk.items())}
    srt = sorted(common, key=lambda r: r['proj'])
    dec = {}
    for i in range(10):
        seg = srt[i * len(srt) // 10:(i + 1) * len(srt) // 10]
        if seg:
            dec[f'D{i + 1}'] = {'n': len(seg), 'mean_proj': round(statistics.fmean(r['proj'] for r in seg), 3),
                               'mean_actual': round(statistics.fmean(r['actual'] for r in seg), 3),
                               'mae': metrics(seg, 'proj')['mae']}
    out['by_projection_decile'] = dec
    segs = []
    for p_, v in by.items():
        v = sorted(v, key=lambda r: r['proj'])
        for i in range(5):
            seg = v[i * len(v) // 5:(i + 1) * len(v) // 5]
            if len(seg) >= 40:
                mi, ms = metrics(seg, 'proj'), metrics(seg, ref)
                segs.append({'segment': f'{p_} projection quintile {i + 1}', 'n': len(seg), 'mae_incumbent': mi['mae'],
                             f'mae_{ref}': ms['mae'], 'excess_mae': round(mi['mae'] - ms['mae'], 4),
                             'bias_incumbent': mi['bias'], f'bias_{ref}': ms['bias']})
    out['worst_segments'] = sorted(segs, key=lambda s_: -s_['excess_mae'])[:10]
    return out


# usage: player_scorecard.py STRICT_OFF.json STRICT_ON.json LEGACY_ON.json
off, on, leg = (load(x) for x in sys.argv[1:4])
res = {'artifact': 'PLAYER_SCORECARD', 'spec': 'benchmark-player-2', 'seasons': on['seasons'],
       'arm': on['arm'],
       'LIMITS': ['held-out seasons 2024-2025, forward chain: priors from seasons <= S-1, current season weeks < W',
                  'no market input (historical closing lines are not held): the club touchdown pool is the club own rate',
                  'paired differences week-blocked (10,000 resamples, seed 20261014); an interval spanning zero is not a finding',
                  'baselines are naive per-appearance means; they are not vendor projections'],
       'CONDITIONAL_GIVEN_PLAYING': {
           'what': 'players who played; incumbent WITHOUT the appearance discount vs per-appearance naive means',
           'vintage': off['vintage'], **scorecard(off['conditional'], ('proj', 'STD', 'L3', 'PRIOR_SEASON'))},
       'UNCONDITIONAL_DFS': {
           'what': ('every pool candidate, zero if he did not play; production incumbent (appearance-discounted) vs '
                    'naive means x his appearance rate before W'),
           'vintage': on['vintage'], **scorecard(on['unconditional'], ('proj', 'STD_U', 'L3_U', 'PRIOR_SEASON_U'))}}
lk = {(r['season'], r['week'], r['gsis']): r['proj'] for r in leg['unconditional']}
pair = [{**r, 'legacy': lk[(r['season'], r['week'], r['gsis'])]} for r in on['unconditional']
        if (r['season'], r['week'], r['gsis']) in lk]
res['VINTAGE_OPTIMISM_LEGACY_MINUS_STRICT'] = {
    'mae': blocked_diff(pair, 'legacy', 'proj', 'abs'), 'n_paired_rows': len(pair),
    'MEANING': 'negative = the pre-2026-10-14 full-period fit looked better than the vintage-correct fit (PIT-D4)'}
print(json.dumps(res, indent=1))
