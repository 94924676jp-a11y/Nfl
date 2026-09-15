"""Is team volume BIASED, and if so where does the bias live?

THE QUESTION, AND WHY IT IS BEING ASKED NOW. R12 improved QB dropback-share
calibration, and in doing so exposed the layer upstream of it: if the team
dropback total is wrong, a perfectly calibrated share of it is still wrong.
R12 is not undone by anything here.

WHAT THE FROZEN RESEARCH ALREADY SAYS, so this does not re-derive it:
team_volume_v1.py's own docstring records that P4 found team volume close to
unforecastable -- the best simple baseline was the league mean in two seasons of
four, and correlation peaked at 0.167. P4B's job was to make that uncertainty
explicit rather than to reduce it. So the question here is NOT "can we predict
it better". It is "is the estimator we ship SYSTEMATICALLY OFF, and in a way
that would drag every share taken from it".

METHOD. Strictly chronological, no fitting of any kind. For each row in the
panel, in ordinal order, every baseline is computed from STRICTLY EARLIER rows
only -- the same `attach` the research uses, which is imported rather than
reimplemented. The shipped estimator for that season is READ from
volume_results.json via team_volume_v1.selected(), never re-chosen here.
Re-selecting an estimator on this evidence would be the retuning the packet
forbids, and would also be selection on the data being scored.

REPORTED. bias, MAE, RMSE, and -- from the residual pool the production draw
actually uses -- CRPS and PIT, by season and with Week 1 broken out separately,
because Week 1 is the only week with no in-season history and is where a prior
does all the work.

CLUSTERING. Standard errors are blocked by TEAM-SEASON, never naive. Sixteen
games of one team in one season are not sixteen independent observations of
that team's pace, and this project has already measured naive binomial SEs
understating uncertainty roughly threefold elsewhere.

Run:  python3.12 nfl/research/v4/teamvol/run_team_volume_drift.py
"""
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                            # noqa: E402
from nfl.production import team_volume_v1 as TV                   # noqa: E402

METRICS = TV.METRICS
# 2022 IS EXCLUDED, AND THE REASON IS THE WHOLE DISCIPLINE OF THIS FILE.
# volume_results.json holds selections for 2022-2025 only, and
# team_volume_v1.selected() takes the latest evaluated season STRICTLY EARLIER
# than the one being scored. For 2022 there is none. Scoring 2022 would mean
# using the 2022 selection on 2022 -- choosing the estimator on the very rows it
# is then graded against. The directive asks for 2022-2025; this returns
# 2023-2025 and says plainly that the fourth season cannot be added without
# selection leakage, rather than adding it and quietly inflating the result.
EVAL_SEASONS = (2023, 2024, 2025)
EXCLUDED_SEASONS = {2022: 'no strictly-earlier estimator selection exists; '
                          'scoring it would select on the data being scored'}
OUT = _REPO / 'nfl' / 'research' / 'v4' / 'teamvol'
SEED = 20260915


def _blocked_se(values, blocks, n_boot=2000, seed=SEED):
    """Block bootstrap of the mean, resampling TEAM-SEASON blocks whole."""
    values = np.asarray(values, float)
    keys = sorted(set(blocks))
    idx = {k: np.flatnonzero(np.asarray([b == k for b in blocks]))
           for k in keys}
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        sel = np.concatenate([idx[keys[i]] for i in pick])
        means.append(values[sel].mean())
    a = np.asarray(means)
    return float(a.std(ddof=1)), (float(np.quantile(a, 0.025)),
                                  float(np.quantile(a, 0.975)))


def run():
    panel = TV._panel()
    rows = sorted(panel, key=lambda r: r['ord'])
    report = {'spec': 'team_volume_drift/1.0.0', 'seed': SEED,
              'eval_seasons': list(EVAL_SEASONS),
              'excluded_seasons': {str(k): v
                                   for k, v in EXCLUDED_SEASONS.items()},
              'n_panel_rows': len(rows),
              'clustering': 'block bootstrap over team-season blocks',
              'estimator_source': 'team_volume_v1.selected(), READ from '
                                  'volume_results.json and never re-chosen',
              'metrics': {}}

    for metric in METRICS:
        V.attach(rows, metric)
        recs = []
        for r in rows:
            season = int(r['season'])
            if season not in EVAL_SEASONS:
                continue
            y = float(r[metric])
            if y <= 0:
                continue
            hist = [q for q in rows if q['ord'] < r['ord'] and q[metric] > 0]
            if len(hist) < 50:
                continue
            lm = float(np.mean([q[metric] for q in hist]))
            sel = TV.selected(metric, season)
            base = V.baselines(r, lm)
            if sel['estimator'] not in base:
                continue
            recs.append({'season': season, 'week': int(r['week']),
                         'team': r['team'], 'y': y,
                         'pred': float(base[sel['estimator']]),
                         'estimator': sel['estimator'],
                         'selected_on_season': sel['selected_on_season']})
        if not recs:
            report['metrics'][metric] = {'state': 'NO_ROWS'}
            continue

        e = np.array([q['pred'] - q['y'] for q in recs], float)
        blocks = [f"{q['team']}-{q['season']}" for q in recs]
        se, ci = _blocked_se(e, blocks)
        ent = {
            'estimator': recs[0]['estimator'],
            'selected_on_season': recs[0]['selected_on_season'],
            'n': len(recs),
            'n_team_season_blocks': len(set(blocks)),
            'bias_pred_minus_actual': round(float(e.mean()), 4),
            'bias_blocked_se': round(se, 4),
            'bias_blocked_ci95': [round(ci[0], 4), round(ci[1], 4)],
            'bias_excludes_zero': not (ci[0] <= 0.0 <= ci[1]),
            'mae': round(float(np.abs(e).mean()), 4),
            'rmse': round(float(np.sqrt((e ** 2).mean())), 4),
            'sd_actual': round(float(np.std([q['y'] for q in recs], ddof=1)), 4),
            'sd_pred': round(float(np.std([q['pred'] for q in recs], ddof=1)), 4),
            'by_season': {}, 'week1': {}, 'week2plus': {},
        }
        ent['sd_ratio_pred_over_actual'] = round(
            ent['sd_pred'] / ent['sd_actual'], 4) if ent['sd_actual'] else None
        yv = np.array([q['y'] for q in recs], float)
        pv = np.array([q['pred'] for q in recs], float)
        if pv.std() > 0:
            ent['pearson_r'] = round(float(np.corrcoef(pv, yv)[0, 1]), 4)
            ent['calibration_slope'] = round(
                float(np.polyfit(pv, yv, 1)[0]), 4)
        else:
            ent['pearson_r'] = None
            ent['calibration_slope'] = None

        for s in EVAL_SEASONS:
            sub = [q for q in recs if q['season'] == s]
            if not sub:
                continue
            es = np.array([q['pred'] - q['y'] for q in sub], float)
            ent['by_season'][str(s)] = {
                'n': len(sub),
                'bias': round(float(es.mean()), 4),
                'mae': round(float(np.abs(es).mean()), 4),
                'rmse': round(float(np.sqrt((es ** 2).mean())), 4)}

        for label, keep in (('week1', lambda q: q['week'] == 1),
                            ('week2plus', lambda q: q['week'] > 1)):
            sub = [q for q in recs if keep(q)]
            if not sub:
                continue
            es = np.array([q['pred'] - q['y'] for q in sub], float)
            bl = [f"{q['team']}-{q['season']}" for q in sub]
            s2, c2 = _blocked_se(es, bl)
            ent[label] = {
                'n': len(sub),
                'bias': round(float(es.mean()), 4),
                'bias_blocked_se': round(s2, 4),
                'bias_blocked_ci95': [round(c2[0], 4), round(c2[1], 4)],
                'bias_excludes_zero': not (c2[0] <= 0.0 <= c2[1]),
                'mae': round(float(np.abs(es).mean()), 4),
                'rmse': round(float(np.sqrt((es ** 2).mean())), 4)}
        report['metrics'][metric] = ent

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / 'TEAM_VOLUME_DRIFT.json'
    p.write_text(json.dumps(report, indent=2) + '\n')
    return report, p


if __name__ == '__main__':
    rep, path = run()
    print(f'written {path}')
    for m, e in rep['metrics'].items():
        if e.get('state') == 'NO_ROWS':
            print(f'{m:22s} NO_ROWS')
            continue
        star = '  <-- excludes zero' if e['bias_excludes_zero'] else ''
        print(f"{m:22s} est={e['estimator']:14s} n={e['n']:4d} "
              f"bias={e['bias_pred_minus_actual']:+8.3f} "
              f"+-{e['bias_blocked_se']:.3f} "
              f"mae={e['mae']:7.3f} rmse={e['rmse']:7.3f} "
              f"r={e['pearson_r']}{star}")
        w1 = e.get('week1') or {}
        if w1:
            s1 = '  <-- excludes zero' if w1.get('bias_excludes_zero') else ''
            print(f"{'':22s}   week1  n={w1['n']:4d} "
                  f"bias={w1['bias']:+8.3f} +-{w1['bias_blocked_se']:.3f} "
                  f"mae={w1['mae']:7.3f}{s1}")
        w2 = e.get('week2plus') or {}
        if w2:
            s2 = '  <-- excludes zero' if w2.get('bias_excludes_zero') else ''
            print(f"{'':22s}   week2+ n={w2['n']:4d} "
                  f"bias={w2['bias']:+8.3f} +-{w2['bias_blocked_se']:.3f} "
                  f"mae={w2['mae']:7.3f}{s2}")
