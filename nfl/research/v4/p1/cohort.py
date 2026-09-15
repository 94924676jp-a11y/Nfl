"""P1: the forward-chained appearance cohort, R8 against its successor R10.

    python3.12 -m nfl.research.v4.p1.cohort

WHAT THIS IS AND WHAT IT IS NOT

It is the same cohort construction R8's own evidence used: the R7/R8 union
frame, trained on seasons STRICTLY EARLIER than the evaluation season and
scored on that season, for 2022 through 2025. Identical rows, identical
`is_unsupported` exclusion, identical l2, and the SAME reliability weight `k`
in both arms -- `k` is estimated from appearance outcomes alone and neither
repair touches it, so it is computed once per season and handed to both.

It is EXPLORATORY and cannot be anything else. Both defects were found by
reading a sealed board built from these seasons, and the repair was designed
with the frame in front of me. Forward chaining controls parameter leakage; it
says nothing about specification leakage. A confirmatory result needs games
nobody has looked at.

THE TWO ARMS DIFFER IN EXACTLY TWO COLUMNS' WORTH OF DESIGN

  R8   `min(v or 9, 9) / 9.0` for f_weeks_since_appear, no missingness flag,
       and the depth bucket read off `rank` -- a within-position group in the
       2020-2024 weekly era and an offence-wide ordinal in 2025.
  R10  value-then-flag with an explicit `is None` test and a monotone
       encoding, and the depth bucket read off `rank_pos`, the within-position
       ordinal in both eras.

Nothing else moves. No constant is introduced by either repair.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production.nonqb import appearance_model as AM              # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8                 # noqa: E402

SPEC_VERSION = 'p1-appearance-cohort-1'
HERE = _REPO / 'nfl' / 'research' / 'v4' / 'p1'
EVAL_SEASONS = (2022, 2023, 2024, 2025)
L2 = 1.0
BINS = 10
N_BOOT = 2000
SEED = 20260915

# PREDECLARED, BEFORE THE FIT WAS RUN. The autopsy's charge is that having a
# history is being PENALISED, so the split that decides it is prior frame
# rows -- the same quantity the defect encodes -- and not anything measured
# after the fact.
HISTORY_BUCKETS = (('none (n_prior = 0)', 0, 0),
                   ('short (1-7)', 1, 7),
                   ('medium (8-15)', 8, 15),
                   ('long (16+)', 16, 10 ** 9))
WEEK_BUCKETS = (('w1', 1, 1), ('w2-4', 2, 4), ('w5-9', 5, 9),
                ('w10-18', 10, 18))


def _brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def _logloss(y, p):
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _auc(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    n1, n0 = float(y.sum()), float((1 - y).sum())
    if n1 == 0 or n0 == 0:
        return None
    r = np.empty(len(p), dtype=float)
    order = np.argsort(p, kind='mergesort')
    sp = p[order]
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def reliability(y, p, bins=BINS):
    """Equal-width bins, with the count carried so an empty bin is visible."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    out, ece = [], 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        m = (p >= lo) & (p < hi) if i < bins - 1 else (p >= lo) & (p <= hi)
        n = int(m.sum())
        if not n:
            out.append({'bin': f'[{lo:.1f},{hi:.1f})', 'n': 0,
                        'mean_predicted': None, 'realised': None})
            continue
        mp, my = float(p[m].mean()), float(y[m].mean())
        out.append({'bin': f'[{lo:.1f},{hi:.1f})', 'n': n,
                    'mean_predicted': round(mp, 4),
                    'realised': round(my, 4),
                    'gap': round(mp - my, 4)})
        ece += n / len(p) * abs(mp - my)
    return out, float(ece)


def _block_bootstrap(rows, ya, pa, pb, n_boot=N_BOOT, seed=SEED):
    """Paired Brier difference, resampled over TEAM-WEEKS, not over rows.

    Players inside one team-week appear or sit together -- a coach rests a
    unit, a club travels short -- so a row-level interval would understate the
    uncertainty by pretending 11,000 correlated rows are 11,000 observations.
    """
    idx = collections.defaultdict(list)
    for i, r in enumerate(rows):
        idx[(r['s'], r['w'], r['t'])].append(i)
    keys = sorted(idx)
    ya, pa, pb = np.asarray(ya), np.asarray(pa), np.asarray(pb)
    rng = np.random.default_rng(seed)
    obs = _brier(ya, pb) - _brier(ya, pa)
    diffs = np.empty(n_boot)
    groups = [np.asarray(idx[k]) for k in keys]
    for b in range(n_boot):
        pick = rng.integers(0, len(groups), len(groups))
        sel = np.concatenate([groups[j] for j in pick])
        diffs[b] = _brier(ya[sel], pb[sel]) - _brier(ya[sel], pa[sel])
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {'brier_r10_minus_r8': round(float(obs), 6),
            'ci95': [round(float(lo), 6), round(float(hi), 6)],
            'n_team_weeks': len(keys), 'n_resamples': n_boot,
            'blocked_by': 'team-week'}


def _bucket_table(rows, y, arms, buckets, field):
    out = []
    y = np.asarray(y, dtype=float)
    for label, lo, hi in buckets:
        m = np.array([lo <= (r.get(field) or 0) <= hi for r in rows])
        if not m.any():
            out.append({'bucket': label, 'n': 0})
            continue
        row = {'bucket': label, 'n': int(m.sum()),
               'realised_appearance_rate': round(float(y[m].mean()), 4)}
        for name, p in arms.items():
            p = np.asarray(p)
            row[f'mean_predicted_{name}'] = round(float(p[m].mean()), 4)
            row[f'brier_{name}'] = round(_brier(y[m], p[m]), 5)
        out.append(row)
    return out


def run(eval_seasons=EVAL_SEASONS, n_boot=N_BOOT):
    f8 = R8.enriched_frame()
    if f8.state is not State.PASS:
        return {'fatal': f'{f8.state.value}[{f8.code}] {f8.detail[:200]}'}
    f10 = R8.enriched_frame_r10()
    if f10.state is not State.PASS:
        return {'fatal': f'{f10.state.value}[{f10.code}] {f10.detail[:200]}'}
    rows8, rows10 = f8.value, f10.value
    if len(rows8) != len(rows10):
        return {'fatal': 'the two frames are not the same rows'}
    M, A, F = AM._frozen()
    out = {'artifact': 'P1_APPEARANCE_COHORT', 'spec_version': SPEC_VERSION,
           'governance': 'EXPLORATORY -- the defects were found on these same '
                         'seasons, so forward chaining controls parameter '
                         'leakage only. This is not a confirmatory result and '
                         'no sportsbook price entered any part of it.',
           'r8_spec': R8.SPEC_VERSION, 'r10_spec': R8.SPEC_VERSION_R10,
           'n_frame_rows': len(rows8),
           'depth_rank_rows_rescaled':
               f10.evidence.get('n_daily_vendor_rows_rescaled'),
           'depth_rank_rows_moved':
               f10.evidence.get('n_rows_whose_depth_rank_moved'),
           'seasons': {}}
    pooled = {'rows': [], 'y': [], 'R8': [], 'R10': []}
    for Y in eval_seasons:
        ko = R8.reliability_k(rows8, cut=Y * 100)
        if ko.state is not State.PASS:
            out['seasons'][str(Y)] = {'blocked': ko.code}
            continue
        k = ko.value
        keep = [i for i, r in enumerate(rows8) if not R8.is_unsupported(r)]
        tr = [i for i in keep if rows8[i]['s'] < Y]
        te = [i for i in keep if rows8[i]['s'] == Y]
        if not tr or not te:
            out['seasons'][str(Y)] = {'blocked': 'EMPTY_SPLIT',
                                      'n_train': len(tr), 'n_test': len(te)}
            continue
        y_tr = [rows8[i]['appeared'] for i in tr]
        y_te = np.array([rows8[i]['appeared'] for i in te], dtype=float)
        preds = {}
        for name, src, feat in (('R8', rows8, R8.featurise),
                                ('R10', rows10, R8.featurise_r10)):
            model = A.fit_logistic([feat(src[i], k) for i in tr], y_tr, l2=L2)
            preds[name] = np.asarray(
                A.predict(model, [feat(src[i], k) for i in te]), dtype=float)
        te_rows = [rows8[i] for i in te]
        rel8, ece8 = reliability(y_te, preds['R8'])
        rel10, ece10 = reliability(y_te, preds['R10'])
        out['seasons'][str(Y)] = {
            'n_train': len(tr), 'n_test': len(te), 'k': round(k, 6),
            'base_rate': round(float(y_te.mean()), 4),
            'brier': {'R8': round(_brier(y_te, preds['R8']), 5),
                      'R10': round(_brier(y_te, preds['R10']), 5)},
            'logloss': {'R8': round(_logloss(y_te, preds['R8']), 5),
                        'R10': round(_logloss(y_te, preds['R10']), 5)},
            'auc': {'R8': round(_auc(y_te, preds['R8']), 5),
                    'R10': round(_auc(y_te, preds['R10']), 5)},
            'ece': {'R8': round(ece8, 5), 'R10': round(ece10, 5)},
            'reliability': {'R8': rel8, 'R10': rel10},
            'by_week': _bucket_table(te_rows, y_te, preds, WEEK_BUCKETS, 'w'),
            'by_history': _bucket_table(te_rows, y_te, preds, HISTORY_BUCKETS,
                                        'n_prior'),
            'paired': _block_bootstrap(te_rows, y_te, preds['R8'],
                                       preds['R10'], n_boot=n_boot),
        }
        pooled['rows'].extend(te_rows)
        pooled['y'].extend(list(y_te))
        pooled['R8'].extend(list(preds['R8']))
        pooled['R10'].extend(list(preds['R10']))
    if pooled['rows']:
        y = np.asarray(pooled['y'])
        p8 = np.asarray(pooled['R8'])
        p10 = np.asarray(pooled['R10'])
        rel8, ece8 = reliability(y, p8)
        rel10, ece10 = reliability(y, p10)
        out['pooled'] = {
            'n': len(y), 'base_rate': round(float(y.mean()), 4),
            'brier': {'R8': round(_brier(y, p8), 5),
                      'R10': round(_brier(y, p10), 5)},
            'logloss': {'R8': round(_logloss(y, p8), 5),
                        'R10': round(_logloss(y, p10), 5)},
            'auc': {'R8': round(_auc(y, p8), 5), 'R10': round(_auc(y, p10), 5)},
            'ece': {'R8': round(ece8, 5), 'R10': round(ece10, 5)},
            'reliability': {'R8': rel8, 'R10': rel10},
            'by_week': _bucket_table(pooled['rows'], y,
                                     {'R8': p8, 'R10': p10}, WEEK_BUCKETS, 'w'),
            'by_history': _bucket_table(pooled['rows'], y,
                                        {'R8': p8, 'R10': p10},
                                        HISTORY_BUCKETS, 'n_prior'),
            'paired': _block_bootstrap(pooled['rows'], y, p8, p10,
                                       n_boot=n_boot),
        }
        # THE AUTOPSY'S CHARGE, TESTED DIRECTLY. "Having a history is being
        # penalised" is a statement about two populations that are otherwise
        # alike: depth-listed at the top of their own position room, one with
        # a long record and one with none. If the charge is right, R8 gives
        # the historyless man the HIGHER probability and the realised rates
        # disagree with it.
        top = np.array([(r.get('rank_pos') if 'rank_pos' in r else r.get('rank'))
                        == 1 for r in pooled['rows']])
        nohist = np.array([(r.get('n_prior') or 0) == 0
                           for r in pooled['rows']])
        longh = np.array([(r.get('n_prior') or 0) >= 16
                          for r in pooled['rows']])
        cells = {}
        for label, m in (('rank_1_no_history', top & nohist),
                         ('rank_1_long_history', top & longh)):
            if m.any():
                cells[label] = {
                    'n': int(m.sum()),
                    'realised': round(float(y[m].mean()), 4),
                    'mean_p_R8': round(float(p8[m].mean()), 4),
                    'mean_p_R10': round(float(p10[m].mean()), 4)}
        if len(cells) == 2:
            a, b = cells['rank_1_no_history'], cells['rank_1_long_history']
            cells['direction'] = {
                'realised_long_minus_none':
                    round(b['realised'] - a['realised'], 4),
                'R8_long_minus_none':
                    round(b['mean_p_R8'] - a['mean_p_R8'], 4),
                'R10_long_minus_none':
                    round(b['mean_p_R10'] - a['mean_p_R10'], 4),
                'reading': ('a model that rewards history has the same sign '
                            'here as the realised column; R8 having the '
                            'opposite sign is the perverse direction the '
                            'autopsy names')}
        out['pooled']['history_direction'] = cells
    return out


def main(argv=None):
    out = run()
    p = HERE / 'P1_COHORT_EVIDENCE.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, sort_keys=False) + '\n')
    print(json.dumps(out.get('pooled', out), indent=1)[:4000])
    print('written', p)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
