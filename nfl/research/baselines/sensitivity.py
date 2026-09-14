"""Two diagnostics that sit beside the freeze without changing it.

1. LOSS SENSITIVITY OF THE WINDOW SELECTION. N and H were frozen by MAE on the
   estimation window. MAE is minimised by a conditional MEDIAN, and roughly 30%
   of FRAME_A rows are structural zeros, so short windows are favoured for a
   reason that has nothing to do with football. This reports what RMSE would
   have chosen instead. It does NOT re-freeze anything: the spec keeps the MAE
   choice, and a reader can see the size of the dependence.

2. THE WEEK-1 EVIDENCE, MEASURED ON THE ESTIMATION WINDOW ONLY. The frozen
   week-1 baseline uses the prior season's MEAN rather than its FINAL GAME. The
   principle was stated first; this is the supporting measurement, taken on
   2021 -> 2022 so that it is strictly prior to the 2023-2024 evaluation window
   and cannot be the thing that chose the estimator.
"""
from __future__ import annotations

import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from nfl.research.baselines import estimators as E     # noqa: E402
from nfl.research.baselines import frame as F          # noqa: E402
from nfl.research.baselines import panel as P          # noqa: E402
from nfl.research.baselines import specs as S          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'D8_SENSITIVITY.json')


def loss_sensitivity(idx, frames, doc):
    out = {}
    for q in doc['quantities']:
        rows = []
        for s in S.SELECTION_SEASONS:
            rows.extend(frames[q][s])
        hs = [(r, idx.hist(r['pid'], q, r['ordinal'])) for r in rows]
        hs = [(r, h) for r, h in hs if h]
        best = {}
        for loss in ('mae', 'rmse'):
            bn = bh = None
            for n in S.N_GRID:
                e = [E.recent_n(h, n) - r['actual'] for r, h in hs]
                v = (statistics.mean(abs(x) for x in e) if loss == 'mae'
                     else (statistics.mean(x * x for x in e)) ** 0.5)
                if bn is None or v < bn[1]:
                    bn = (n, v)
            for hl in S.H_GRID:
                e = [E.ewma(h, hl) - r['actual'] for r, h in hs]
                v = (statistics.mean(abs(x) for x in e) if loss == 'mae'
                     else (statistics.mean(x * x for x in e)) ** 0.5)
                if bh is None or v < bh[1]:
                    bh = (hl, v)
            best[loss] = {'recent_n': bn[0], 'ewma_half_life': bh[0]}
        out[q] = {
            'frozen_by_mae': {
                'recent_n': doc['windows'][q]['recent_n'],
                'ewma_half_life': doc['windows'][q]['ewma_half_life_games']},
            'would_have_been_by_rmse': best['rmse'],
            'agrees': (best['mae'] == best['rmse']),
            'n_rows': len(hs),
        }
    return out


def _corr(xs, ys):
    if len(xs) < 10:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx > 0 and syy > 0 else None


def week1_evidence(idx):
    """Prior-season FINAL GAME vs prior-season MEAN as a predictor of the next
    season's per-game mean. 2021 -> 2022 only."""
    out = {}
    for q, pos in list(F.QUANTITY_POSITIONS.items()):
        a, b = {}, {}
        for r in idx.players:
            if r['position'] not in pos:
                continue
            if r['season'] == 2021:
                a.setdefault(r['gsis_id'], []).append(
                    (r['week'], float(r[q])))
            elif r['season'] == 2022:
                b.setdefault(r['gsis_id'], []).append(float(r[q]))
        finals, means, nxt = [], [], []
        for pid in sorted(set(a) & set(b)):
            if len(a[pid]) < 6 or len(b[pid]) < 6:
                continue
            games = sorted(a[pid])
            finals.append(games[-1][1])
            means.append(statistics.mean(v for _, v in games))
            nxt.append(statistics.mean(b[pid]))
        out[q] = {
            'n_players': len(nxt),
            'r_final_game_vs_next_season_mean': (
                None if _corr(finals, nxt) is None
                else round(_corr(finals, nxt), 4)),
            'r_prior_season_mean_vs_next_season_mean': (
                None if _corr(means, nxt) is None
                else round(_corr(means, nxt), 4)),
        }
    return out


def main() -> int:
    doc = S.load()
    pan = P.build_panel()
    idx = F.Index(pan)
    frames = {}
    for q in F.QUANTITY_POSITIONS:
        frames[q] = {s: idx.frame_a(q, (s,)) for s in P.LAWFUL_SEASONS}
    for q in F.TEAM_QUANTITIES:
        frames[q] = {s: idx.team_frame(q, (s,)) for s in P.LAWFUL_SEASONS}
    res = {
        'artifact': 'D8_BASELINE_SENSITIVITY',
        'governance': 'DIAGNOSTICS ONLY; changes no frozen value',
        'spec_document_sha256': doc['document_sha256'],
        'window_selection_loss_sensitivity': loss_sensitivity(idx, frames, doc),
        'week1_final_game_vs_prior_season_mean_2021_to_2022':
            week1_evidence(idx),
    }
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
        fh.write('\n')
    print(f'WROTE {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
