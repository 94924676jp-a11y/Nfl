"""Score the frozen baselines on 2023-2024. Reads the freeze; never writes it.

GAMES ARE NOT INDEPENDENT OBSERVATIONS. Every interval reported here is a
block bootstrap that resamples GAME IDS, not rows: a team's receivers move
together, both teams in a game move together, and a naive interval over ~8,000
receiver-games would claim a precision the 544 games cannot support. The
resample is drawn ONCE per (quantity, frame) and reused across baselines, which
is also what makes the head-to-head delta against the league prior a PAIRED
comparison rather than a difference of two independent intervals.

The delta reported is `MAE(baseline) - MAE(B6-LEAGUE-POSITION-PRIOR)`. Negative
is better. B6 is the floor every other baseline has to clear to have earned its
complexity, and several of them do not clear it -- which is a result, not a
defect in the harness.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from nfl.research.baselines import estimators as E    # noqa: E402
from nfl.research.baselines import frame as F         # noqa: E402
from nfl.research.baselines import panel as P         # noqa: E402
from nfl.research.baselines import specs as S         # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, 'D8_BASELINE_RESULTS.json')

N_BOOT = 400
BOOT_SEED = 20260914

CORE = ('B1-SEASON-TO-DATE', 'B2-RECENT-N', 'B3-EWMA', 'B4-SHRINK',
        'B5-ROLE-AVERAGE', 'B6-LEAGUE-POSITION-PRIOR')
W1 = ('W1-PRIOR-SEASON-SHRUNK', 'W1-PRIOR-SEASON-MEAN', 'W1-FINAL-GAME',
      'B6-LEAGUE-POSITION-PRIOR')


def tables(idx, frames, quantity, season):
    prior = F.league_prior_table(idx, quantity, season, frames[quantity])
    role = F.role_table(idx, quantity, season, frames[quantity])
    return prior, role


def predict_all(idx, rows, quantity, const, win, prior_by_season,
                role_by_season):
    """rows -> {baseline: np.array of predictions}. One pass, all baselines."""
    k = const['k_prior_games']
    c = const['c_carryover_slope']
    n_recent = win['recent_n']
    half = win['ewma_half_life_games']
    out = {b: np.empty(len(rows)) for b in CORE + W1[:3]}
    for i, r in enumerate(rows):
        season, pos, o = r['season'], r['position'], r['ordinal']
        prior_tab = prior_by_season[season]
        role_tab = role_by_season[season]
        mu = prior_tab.get(pos)
        if mu is None:
            mu = float(np.mean(list(prior_tab.values())))
        hist = idx.hist(r['pid'], quantity, o)
        try:
            v = E.season_to_date(hist, season)
        except E.Undefined:
            v = E.w1_prior_season_shrunk(hist, season, mu, k, c)
        out['B1-SEASON-TO-DATE'][i] = v
        try:
            out['B2-RECENT-N'][i] = E.recent_n(hist, n_recent)
        except E.Undefined:
            out['B2-RECENT-N'][i] = mu
        try:
            out['B3-EWMA'][i] = E.ewma(hist, half)
        except E.Undefined:
            out['B3-EWMA'][i] = mu
        out['B4-SHRINK'][i] = E.shrunk(hist, season, mu, k, c)
        try:
            out['B5-ROLE-AVERAGE'][i] = E.role_average(role_tab, pos,
                                                       r['rank'])
        except E.Undefined:
            out['B5-ROLE-AVERAGE'][i] = mu
        out['B6-LEAGUE-POSITION-PRIOR'][i] = mu
        out['W1-PRIOR-SEASON-SHRUNK'][i] = E.w1_prior_season_shrunk(
            hist, season, mu, k, c)
        try:
            out['W1-PRIOR-SEASON-MEAN'][i] = E.w1_prior_season_mean(hist,
                                                                    season)
        except E.Undefined:
            out['W1-PRIOR-SEASON-MEAN'][i] = mu
        try:
            out['W1-FINAL-GAME'][i] = E.w1_final_game(hist, season)
        except E.Undefined:
            out['W1-FINAL-GAME'][i] = mu
    return out


def point_metrics(pred, act):
    n = act.size
    e = pred - act
    mae = float(np.mean(np.abs(e)))
    rmse = float(np.sqrt(np.mean(e ** 2)))
    sp, sa = float(np.std(pred, ddof=1)), float(np.std(act, ddof=1))
    if sp > 1e-12 and sa > 1e-12:
        r = float(np.corrcoef(pred, act)[0, 1])
        slope = float(np.cov(pred, act, ddof=1)[0, 1] / (sp ** 2))
    else:
        r, slope = float('nan'), float('nan')
    return dict(n=int(n), mean_pred=round(float(np.mean(pred)), 4),
                mean_actual=round(float(np.mean(act)), 4),
                bias=round(float(np.mean(e)), 4), mae=round(mae, 4),
                rmse=round(rmse, 4), sd_pred=round(sp, 4),
                sd_actual=round(sa, 4),
                sd_ratio=round(sp / sa, 4) if sa > 1e-12 else None,
                pearson_r=None if r != r else round(r, 4),
                calibration_slope=None if slope != slope else round(slope, 4))


def boot_indices(game_ids, rng, n_boot=N_BOOT):
    uniq, inv = np.unique(game_ids, return_inverse=True)
    buckets = [np.where(inv == g)[0] for g in range(uniq.size)]
    reps = []
    for _ in range(n_boot):
        pick = rng.integers(0, uniq.size, uniq.size)
        reps.append(np.concatenate([buckets[j] for j in pick]))
    return uniq.size, reps


def ci(vals):
    a = np.asarray(vals, float)
    a = a[np.isfinite(a)]
    if a.size < 20:
        return None
    return [round(float(np.percentile(a, 2.5)), 4),
            round(float(np.percentile(a, 97.5)), 4)]


def score_frame(rows, preds, names, rng):
    act = np.array([r['actual'] for r in rows], float)
    gids = np.array([r['game_id'] for r in rows])
    n_clusters, reps = boot_indices(gids, rng)
    base = preds['B6-LEAGUE-POSITION-PRIOR']
    out = {'n_rows': len(rows), 'n_game_clusters': int(n_clusters),
           'baselines': {}}
    for b in names:
        p = preds[b]
        m = point_metrics(p, act)
        rs, maes, dmaes = [], [], []
        for ridx in reps:
            pa, aa, ba = p[ridx], act[ridx], base[ridx]
            sp, sa = pa.std(ddof=1), aa.std(ddof=1)
            rs.append(np.corrcoef(pa, aa)[0, 1] if sp > 1e-12 and sa > 1e-12
                      else np.nan)
            mm = np.mean(np.abs(pa - aa))
            maes.append(mm)
            dmaes.append(mm - np.mean(np.abs(ba - aa)))
        m['pearson_r_ci95_game_clustered'] = ci(rs)
        m['mae_ci95_game_clustered'] = ci(maes)
        m['delta_mae_vs_league_prior'] = round(float(np.mean(dmaes)), 4)
        m['delta_mae_ci95_game_clustered'] = ci(dmaes)
        out['baselines'][b] = m
    return out


def main() -> int:
    doc = S.load()
    print(f'spec document_sha256 {doc["document_sha256"]} VERIFIED')
    pan = P.build_panel()
    idx = F.Index(pan)
    if idx.identity != doc['data_identity']:
        raise SystemExit(
            'BASELINE_DATA_IDENTITY_DRIFT: the panel bytes are not the bytes '
            'the spec was frozen against.')
    frames = {}
    for q in F.QUANTITY_POSITIONS:
        frames[q] = {s: idx.frame_a(q, (s,)) for s in P.LAWFUL_SEASONS}
    for q in F.TEAM_QUANTITIES:
        frames[q] = {s: idx.team_frame(q, (s,)) for s in P.LAWFUL_SEASONS}

    results = {'artifact': 'D8_BASELINE_RESULTS',
               'governance': 'DIAGNOSTICS ONLY; no baseline is wired anywhere',
               'spec_document_sha256': doc['document_sha256'],
               'spec_version': doc['spec_version'],
               'evaluation_seasons': doc['evaluation_seasons'],
               'n_boot': N_BOOT, 'boot_seed': BOOT_SEED,
               'clustering': 'game_id block bootstrap, resample drawn once '
                             'per (quantity, frame) and shared across '
                             'baselines so the delta is paired',
               'frame_c_note': ('FRAME_C is FRAME_B restricted to the '
                'within-team usage rank-1 subject -- the starting quarterback, the lead back, the top target. Rank is assigned from PRIOR games only, so FRAME_C conditions on the outcome exactly once (appearance), the same as FRAME_B. It exists because an r computed over a population that contains backups is mostly measuring starter-versus-backup and is NOT comparable to an r computed over starters.'),
               'quantities': {}}
    for q in doc['quantities']:
        rng = np.random.default_rng(BOOT_SEED)
        const, win = doc['constants'][q], doc['windows'][q]
        prior_by_season, role_by_season = {}, {}
        for s in F.EVALUATION_SEASONS:
            pt, rt = tables(idx, frames, q, s)
            prior_by_season[s], role_by_season[s] = pt, rt
        rows = []
        for s in F.EVALUATION_SEASONS:
            rows.extend(frames[q][s])
        preds = predict_all(idx, rows, q, const, win, prior_by_season,
                            role_by_season)
        a = score_frame(rows, preds, CORE, rng)
        idx_b = [i for i, r in enumerate(rows) if r['played'] == 1]
        rows_b = [rows[i] for i in idx_b]
        preds_b = {k: v[idx_b] for k, v in preds.items()}
        b = score_frame(rows_b, preds_b, CORE,
                        np.random.default_rng(BOOT_SEED + 1))
        ci_ = [i for i, r in enumerate(rows)
               if r['played'] == 1 and r['rank'] == 1]
        rows_c = [rows[i] for i in ci_]
        preds_c = {k: v[ci_] for k, v in preds.items()}
        c = score_frame(rows_c, preds_c, CORE,
                        np.random.default_rng(BOOT_SEED + 3))
        # season openers: the team has no completed game in this season
        w1i = [i for i, r in enumerate(rows)
               if not [x for x in idx.team_games[r['team']]
                       if x < r['ordinal'] and x // 100 == r['season']]]
        rows_w1 = [rows[i] for i in w1i]
        preds_w1 = {k: v[w1i] for k, v in preds.items()}
        w1 = score_frame(rows_w1, preds_w1, W1,
                         np.random.default_rng(BOOT_SEED + 2))
        results['quantities'][q] = {
            'positions': const['positions'],
            'frame_a_zero_actual_rate': round(
                sum(1 for r in rows if r['played'] == 0) / len(rows), 4),
            'FRAME_A_point_in_time': a,
            'FRAME_B_appeared_conditions_on_outcome': b,
            'FRAME_C_primary_role_appeared': c,
            'SEASON_OPENER_FRAME_A': w1,
        }
        print(f'  {q:16s} A n={a["n_rows"]:6d} g={a["n_game_clusters"]:4d}  '
              f'B n={b["n_rows"]:6d}  C n={c["n_rows"]:6d}  '
              f'W1 n={w1["n_rows"]:5d}')
    with open(RESULTS, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=1, sort_keys=True)
        fh.write('\n')
    print(f'WROTE {RESULTS}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
