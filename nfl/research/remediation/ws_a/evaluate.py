"""WS-A step 2: the forward-chained, serve-shaped evaluation.

    python3.12 nfl/research/remediation/ws_a/evaluate.py

Every endpoint, margin, bucket and seed in this file was fixed in
PREREG_appearance_leak.md (sha256 b14738a0a4a262cc...) before any arm was
fitted. Results land in WS_A_RESULTS.json.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import pathlib
import pickle
import sys
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('wsa_harness', HERE / 'harness.py')
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)

import stage_a as SA                                              # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7              # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8              # noqa: E402
from sportsplatform.governance.outcome import State               # noqa: E402

CACHE = pathlib.Path(os.environ.get(
    'WSA_CACHE', '/tmp/claude-0/-home-user-mlb-prop-system-v7/'
    '8de98087-4781-5a10-ae09-ef74590f8116/scratchpad/wsa/blocks.pkl'))
OUT = HERE / 'WS_A_RESULTS.json'

EQUIV_MARGIN = 0.02        # calibration-in-the-large, predeclared
NI_MARGIN = 0.005          # Brier non-inferiority, predeclared
ALPHA_PER_CANDIDATE = 0.025  # Bonferroni over two promotion candidates

ARMS = {
    'BASE_INFRAME': {'train': 'P', 'score': 'P', 'feat': H.featurise_base,
                     'means': False, 'role': 'diagnostic control'},
    'BASE_SERVE':   {'train': 'P', 'score': 'S', 'feat': H.featurise_base,
                     'means': False, 'role': 'pre-repair failure'},
    'A':            {'train': 'P', 'score': 'S', 'feat': H.featurise_a,
                     'means': True,  'role': 'promotion candidate'},
    'B':            {'train': 'U', 'score': 'U', 'feat': H.featurise_b,
                     'means': False, 'role': 'promotion candidate'},
    'A0':           {'train': 'N', 'score': 'N', 'feat': H.featurise_a0,
                     'means': False, 'role': 'bounding control'},
}
CANDIDATES = ('A', 'B')


def _view(r, basis, blk_u, blk_s):
    q = dict(r)
    if basis == 'P':
        return q
    if basis == 'N':
        q['v1'] = None
        return q
    k = (r['s'], r['w'], r['t'], r['pid'])
    src = blk_u if basis == 'U' else blk_s
    b = src.get(k)
    if b is None:
        raise H.HarnessError(f'WS_A_BLOCK_MISSING basis={basis} key={k}')
    q['v1'] = b
    return q


# ------------------------------------------------------------------ metrics
def _brier(y, p):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def _logloss(y, p):
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _auc(y, p):
    return float(SA.auc(np.asarray(y), np.asarray(p, float)))


def _cal_bins(y, p, bins=10):
    y, p = np.asarray(y, float), np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    out, ece = [], 0.0
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        sel = (p >= lo) & ((p < hi) if i < bins - 1 else (p <= hi))
        n = int(sel.sum())
        if not n:
            out.append({'bin': f'{lo:.1f}-{hi:.1f}', 'n': 0})
            continue
        mp, ob = float(p[sel].mean()), float(y[sel].mean())
        out.append({'bin': f'{lo:.1f}-{hi:.1f}', 'n': n,
                    'mean_predicted': round(mp, 5), 'observed_rate': round(ob, 5),
                    'gap': round(mp - ob, 5)})
        ece += n / len(p) * abs(mp - ob)
    return out, round(float(ece), 6)


def _spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return None
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _pearson(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


# ------------------------------------------------------- cluster bootstrap
def cluster_bootstrap(cluster_ids, per_row, reps=H.BOOT, seed=H.SEED):
    """Resample whole clusters. `per_row` is a dict name -> per-row array whose
    statistic is a MEAN, so cluster sums are sufficient and the resample costs
    one matrix product instead of a row gather.

    Games are not independent observations; no binomial interval is computed
    anywhere in this file.
    """
    ids = list(cluster_ids)
    uniq = {}
    for i, c in enumerate(ids):
        uniq.setdefault(c, []).append(i)
    keys = sorted(uniq, key=lambda x: str(x))
    idx = [np.asarray(uniq[c], int) for c in keys]
    counts = np.array([len(i) for i in idx], float)
    sums = {}
    for name, arr in per_row.items():
        a = np.asarray(arr, float)
        sums[name] = np.array([a[i].sum() for i in idx], float)
    rng = np.random.default_rng(seed)
    n_c = len(keys)
    draws = rng.integers(0, n_c, size=(reps, n_c))
    out = {}
    denom = counts[draws].sum(axis=1)
    for name, s in sums.items():
        out[name] = s[draws].sum(axis=1) / denom
    return out, len(keys)


def _ci(v, lo=2.5, hi=97.5):
    return [round(float(np.percentile(v, lo)), 6),
            round(float(np.percentile(v, hi)), 6)]


# ------------------------------------------------------------------- main
def main():
    t0 = time.time()
    if not CACHE.exists():
        raise H.HarnessError(f'WS_A_CACHE_MISSING {CACHE}; run build_blocks.py')
    cache = pickle.load(open(CACHE, 'rb'))
    blk_u, blk_s = cache['blk_u'], cache['blk_s']
    S = H.load()
    urows = S['urows']

    # S4: no sportsbook or postgame-named field is read by this harness.
    consumed = sorted(set(urows[0].keys()) | set(H.V1_KEYS))
    bad = [f for f in consumed
           if any(s in f.lower() for s in H.FORBIDDEN_INPUTS)]
    if bad:
        raise H.HarnessError(f'WS_A_FORBIDDEN_INPUT {bad}')

    scored = {a: {} for a in ARMS}
    fit_log = []
    for season in H.EVAL_SEASONS:
        train = [r for r in urows if r['s'] < season and not R7.is_unsupported(r)]
        ev = [r for r in urows if r['s'] == season and not R7.is_unsupported(r)]
        if not train or not ev:
            raise H.HarnessError(f'WS_A_FOLD_EMPTY {season} '
                                 f'train={len(train)} eval={len(ev)}')
        # S5: chronology is a refusal, not a filter.
        if max(r['s'] for r in train) >= season:
            raise H.HarnessError(f'WS_A_TRAINING_LEAKAGE season {season}')
        ko = R8.reliability_k(urows, cut=int(season) * 100)
        if ko.state is not State.PASS:
            raise H.HarnessError(f'WS_A_K_UNAVAILABLE {ko.code}')
        k = ko.value
        for arm, cfg in ARMS.items():
            tr = [_view(r, cfg['train'], blk_u, blk_s) for r in train]
            means = H.a_means(tr) if cfg['means'] else None
            X = [cfg['feat'](r, k, means) for r in tr]
            y = np.array([float(r['appeared']) for r in tr])
            model = SA.fit_logistic(X, y, l2=H.L2)
            evv = [_view(r, cfg['score'], blk_u, blk_s) for r in ev]
            Xe = [cfg['feat'](r, k, means) for r in evv]
            p = np.asarray(SA.predict(model, Xe), float)
            if not len(p):
                raise H.HarnessError(f'WS_A_NO_PREDICTIONS {arm} {season}')
            for r, v in zip(ev, p):
                scored[arm][(r['s'], r['w'], r['t'], r['pid'])] = float(v)
            fit_log.append({'arm': arm, 'eval_season': season,
                            'n_train': len(tr), 'n_features': len(X[0]),
                            'n_eval': len(evv), 'k': round(k, 6),
                            'in_sample_brier': round(_brier(y, SA.predict(model, X)), 6),
                            'in_sample_auc': round(_auc(y, SA.predict(model, X)), 6),
                            'train_basis': cfg['train'], 'score_basis': cfg['score']})
            print(f'  {season} {arm:13s} n_train={len(tr)} n_feat={len(X[0])} '
                  f'n_eval={len(evv)}', flush=True)

    # ---- assemble the evaluation table -----------------------------------
    ev_all = [r for r in urows if r['s'] in H.EVAL_SEASONS
              and not R7.is_unsupported(r)]
    keys = [(r['s'], r['w'], r['t'], r['pid']) for r in ev_all]
    y = np.array([float(r['appeared']) for r in ev_all])
    P = {a: np.array([scored[a][kk] for kk in keys], float) for a in ARMS}
    clusters_game = [(r['s'], r['w'], r['t']) for r in ev_all]
    clusters_date = [(r['s'], r['w']) for r in ev_all]

    res = {
        'artifact': 'WS_A_APPEARANCE_LEAK_RESULTS',
        'spec_version': H.SPEC_VERSION,
        'preregistration_sha256': H.PREREG_SHA256,
        'is_research_only': True, 'promoted': False,
        'market_inputs_used': 0, 'realised_2026_outcomes_used': 0,
        'eval_seasons': list(H.EVAL_SEASONS),
        'n_eval_rows': len(ev_all),
        'observed_rate': round(float(y.mean()), 6),
        'frame_evidence': {kk: S['frame_evidence'].get(kk) for kk in (
            'n_rows', 'n_from_panel', 'n_added_by_depth_chart',
            'n_rows_with_the_v1_feature_block',
            'n_rows_without_the_v1_feature_block', 'seasons')},
        'p_join_presence': cache['p_join'],
        'n_synthetic_rows_union_basis': cache['n_synth_union'],
        'structural_label_flip_test': cache['flip_test'],
        'arms': {a: {'role': ARMS[a]['role'], 'train_basis': ARMS[a]['train'],
                     'score_basis': ARMS[a]['score']} for a in ARMS},
        'fit_log': fit_log,
        'l2': H.L2, 'bootstrap_reps': H.BOOT, 'bootstrap_seed': H.SEED,
        'equivalence_margin_calibration_in_the_large': EQUIV_MARGIN,
        'non_inferiority_margin_brier': NI_MARGIN,
        'alpha_per_candidate_bonferroni': ALPHA_PER_CANDIDATE,
        'crps_note': 'For a Bernoulli forecast CRPS is identically the Brier '
                     'score; it is reported as that identity, not separately.',
    }

    # ---- headline -------------------------------------------------------
    per_row = {}
    for a in ARMS:
        per_row[f'brier_{a}'] = (P[a] - y) ** 2
        pc = np.clip(P[a], 1e-9, 1 - 1e-9)
        per_row[f'll_{a}'] = -(y * np.log(pc) + (1 - y) * np.log(1 - pc))
        per_row[f'p_{a}'] = P[a]
    per_row['y'] = y
    boot_g, n_cg = cluster_bootstrap(clusters_game, per_row)
    boot_d, n_cd = cluster_bootstrap(clusters_date, per_row)
    res['n_clusters_game'] = n_cg
    res['n_clusters_date'] = n_cd

    head = {}
    for a in ARMS:
        cal = float(P[a].mean() - y.mean())
        bins, ece = _cal_bins(y, P[a])
        bg = boot_g[f'p_{a}'] - boot_g['y']
        bd = boot_d[f'p_{a}'] - boot_d['y']
        head[a] = {
            'n': len(y),
            'brier': round(_brier(y, P[a]), 6),
            'brier_ci95_cluster_game': _ci(boot_g[f'brier_{a}']),
            'brier_ci95_cluster_date': _ci(boot_d[f'brier_{a}']),
            'log_loss': round(_logloss(y, P[a]), 6),
            'log_loss_ci95_cluster_game': _ci(boot_g[f'll_{a}']),
            'auc': round(_auc(y, P[a]), 6),
            'mean_predicted': round(float(P[a].mean()), 6),
            'observed_rate': round(float(y.mean()), 6),
            'calibration_in_the_large': round(cal, 6),
            'calibration_in_the_large_ci90_cluster_game': _ci(bg, 5, 95),
            'calibration_in_the_large_ci90_cluster_date': _ci(bd, 5, 95),
            'tost_equivalence_margin': EQUIV_MARGIN,
            'tost_rejects_both_nulls_cluster_game': bool(
                np.percentile(bg, 5) > -EQUIV_MARGIN
                and np.percentile(bg, 95) < EQUIV_MARGIN),
            'expected_calibration_error': ece,
            'calibration_bins': bins,
        }
    res['headline'] = head

    # ---- paired arm differences -----------------------------------------
    pairs = {}
    for a in ARMS:
        if a == 'BASE_SERVE':
            continue
        d = boot_g[f'brier_{a}'] - boot_g['brier_BASE_SERVE']
        dd = boot_d[f'brier_{a}'] - boot_d['brier_BASE_SERVE']
        pairs[f'{a}_minus_BASE_SERVE'] = {
            'brier_difference': round(_brier(y, P[a]) - _brier(y, P['BASE_SERVE']), 6),
            'paired_ci95_cluster_game': _ci(d),
            'paired_ci95_cluster_date': _ci(dd),
            'one_sided_upper_97_5_cluster_game': round(float(np.percentile(d, 97.5)), 6),
            'non_inferior_at_margin': bool(np.percentile(d, 97.5) < NI_MARGIN),
            'superior_at_alpha_0_025': bool(np.percentile(d, 97.5) < 0.0),
            'is_promotion_candidate': a in CANDIDATES,
        }
    res['paired_vs_pre_repair'] = pairs

    # ---- subgroups ------------------------------------------------------
    def bucket_week(r):
        w = r['w']
        return '1' if w == 1 else ('2-4' if w <= 4 else
                                   ('5-9' if w <= 9 else '10-18'))

    def bucket_rank(r):
        rk = r.get('rank')
        return ('unlisted' if rk is None else
                ('r1' if rk == 1 else 'r2' if rk == 2 else
                 'r3' if rk == 3 else 'r4plus'))

    def bucket_ewma(r):
        v = r.get('app_ewma')
        if v is None:
            return 'none_cold_start'
        return ('lt_0.05' if v < 0.05 else '0.05-0.5' if v < 0.5 else
                '0.5-0.95' if v < 0.95 else '0.95-1')

    def bucket_carried(r):
        c = r.get('cm_carried') or 0
        return '0' if c == 0 else ('1-3' if c <= 3 else
                                   ('4-8' if c <= 8 else 'ge_9'))

    def bucket_pos(r):
        return r.get('pos')

    groupers = {'by_week': bucket_week, 'by_depth_rank': bucket_rank,
                'by_prior_participation': bucket_ewma,
                'by_carried_absence': bucket_carried,
                'by_position': bucket_pos}
    sub = {}
    for gname, fn in groupers.items():
        labels = [fn(r) for r in ev_all]
        tab = {}
        for lab in sorted(set(labels), key=str):
            sel = np.array([x == lab for x in labels], bool)
            tab[str(lab)] = {'n': int(sel.sum()),
                             'observed_rate': round(float(y[sel].mean()), 5)}
            for a in ARMS:
                tab[str(lab)][a] = {
                    'mean_predicted': round(float(P[a][sel].mean()), 5),
                    'gap': round(float(P[a][sel].mean() - y[sel].mean()), 5),
                    'brier': round(_brier(y[sel], P[a][sel]), 5)}
        sub[gname] = tab
    res['subgroups'] = sub

    # ---- pathological cells (Q8) ----------------------------------------
    cells = {
        'clear_RB1': lambda r: r['pos'] == 'RB' and r.get('rank') == 1,
        'WR1': lambda r: r['pos'] == 'WR' and r.get('rank') == 1,
        'long_absence_carried_ge_9': lambda r: (r.get('cm_carried') or 0) >= 9,
        'long_absence_app_ewma_lt_0.05': lambda r: (
            r.get('app_ewma') is not None and r['app_ewma'] < 0.05),
        'reserve_listed_rank_ge_4_thin_history': lambda r: (
            r.get('rank') is not None and r['rank'] >= 4
            and (r.get('n_prior') or 0) < 4),
        'unlisted_with_history': lambda r: (
            r.get('rank') is None and (r.get('n_prior') or 0) > 0),
        'week1_cold_start_listed': lambda r: (
            r['w'] == 1 and (r.get('n_cur') or 0) == 0
            and (r.get('n_prior') or 0) == 0 and r.get('rank') is not None),
        'designated_out_or_doubtful': lambda r: (
            r.get('inj_status') in ('Out', 'Doubtful')),
    }
    path = {}
    for name, fn in cells.items():
        sel = np.array([bool(fn(r)) for r in ev_all], bool)
        n = int(sel.sum())
        if not n:
            path[name] = {'n': 0, 'note': 'EMPTY CELL -- reported as empty, '
                                          'not as a passing result'}
            continue
        path[name] = {'n': n, 'observed_rate': round(float(y[sel].mean()), 5)}
        for a in ARMS:
            path[name][a] = {
                'mean_predicted': round(float(P[a][sel].mean()), 5),
                'gap': round(float(P[a][sel].mean() - y[sel].mean()), 5),
                'brier': round(_brier(y[sel], P[a][sel]), 5)}
    res['pathological_cells'] = path

    # ---- Q7 inversion diagnostic ----------------------------------------
    listed = np.array([bool(r.get('rank') is not None
                            and r.get('inj_status') in (None, ''))
                       for r in ev_all], bool)
    ew = np.array([(r.get('app_ewma') if r.get('app_ewma') is not None else np.nan)
                   for r in ev_all], float)
    cm = np.array([float(r.get('cm_carried') or 0) for r in ev_all], float)
    ok = listed & ~np.isnan(ew)
    inv = {'n_listed_non_designated': int(ok.sum()),
           'predeclared_sign_app_ewma': 'positive',
           'predeclared_sign_cm_carried': 'negative'}
    for a in ARMS:
        inv[a] = {'pearson_app_ewma_vs_p': round(_pearson(ew[ok], P[a][ok]), 5),
                  'pearson_cm_carried_vs_p': round(_pearson(cm[listed], P[a][listed]), 5)}
    res['inversion_diagnostic'] = inv

    # ---- Q6 ranking sanity ----------------------------------------------
    tw = collections.defaultdict(list)
    for i, r in enumerate(ev_all):
        if r.get('rank') is not None:
            tw[(r['s'], r['w'], r['t'])].append(i)
    rank_sanity = {}
    for a in ARMS:
        sps = []
        for _, ix in tw.items():
            if len(ix) < 3:
                continue
            rk = [ev_all[i]['rank'] for i in ix]
            sp = _spearman(rk, P[a][ix])
            if sp is not None:
                sps.append(sp)
        order = np.argsort(-P[a])
        top = order[:int(0.05 * len(order))]
        rank_sanity[a] = {
            'auc': round(_auc(y, P[a]), 6),
            'mean_within_team_week_spearman_rank_vs_p': round(float(np.mean(sps)), 5),
            'n_team_weeks_scored': len(sps),
            'top5pct_mean_predicted': round(float(P[a][top].mean()), 5),
            'top5pct_observed_rate': round(float(y[top].mean()), 5)}
    res['ranking_sanity'] = rank_sanity

    # ---- the leaked bit's own discriminative power ------------------------
    tr_all = [r for r in urows if r['s'] < max(H.EVAL_SEASONS)
              and not R7.is_unsupported(r)]
    bit = np.array([0.0 if r.get('v1') is None else 1.0 for r in tr_all])
    yy = np.array([float(r['appeared']) for r in tr_all])
    res['presence_bit_alone'] = {
        'n_train_rows': len(tr_all),
        'auc_of_the_presence_bit_alone': round(_auc(yy, bit), 6),
        'note': 'In training only. At serve the bit is a constant, so its '
                'serve-time AUC is undefined -- which is the defect.'}

    res['elapsed_seconds'] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(res, indent=1, default=str))
    print(f'wrote {OUT} in {res["elapsed_seconds"]}s', flush=True)
    for a in ARMS:
        h = head[a]
        print(f'{a:13s} brier={h["brier"]:.5f} ll={h["log_loss"]:.5f} '
              f'auc={h["auc"]:.5f} meanp={h["mean_predicted"]:.5f} '
              f'obs={h["observed_rate"]:.5f} cal={h["calibration_in_the_large"]:+.5f}',
              flush=True)


if __name__ == '__main__':
    main()
