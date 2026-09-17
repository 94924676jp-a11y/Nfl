"""The forward chain. One rule, enforced as an assertion rather than described.

For a forecast of season S week W, every quantity used -- INCLUDING every
hyperparameter -- must be a function of data with ordinal strictly less than
S*100 + W. No random split, no future week informing an earlier week, and no
single hyperparameter chosen once over the whole chain and reused across it.

THE SUBTLE VIOLATION THIS GUARDS AGAINST: choosing hyperparameters by
averaging performance across the whole chain and then reporting that chain's
scores. That is tuning on the test set with extra steps, and it is the easiest
way to produce a chain that looks honest. So `tune()` is called INSIDE each
fold, sees only that fold's history, and the reported score is the score of the
configuration that fold would actually have shipped.

WHAT IS NOT DONE HERE: no Week-2 OAS1 candidate is fitted. This module scores
the baselines only. The candidate needs gate 5's pre-declaration committed
first, and that is a deliberate ordering, not an omission.
"""
from __future__ import annotations

import itertools
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.production import evaluator as EV                   # noqa: E402
from nfl.research.oas1 import baselines as BL                # noqa: E402

SPEC_VERSION = 'oas1-forward-chain-1'

#: How many completed weeks the inner tuning chain looks back over.
INNER_K = 8

CODE_OK = 'OAS1_CHAIN_COMPLETE'
CODE_LEAK = 'OAS1_CHAIN_ORDINAL_VIOLATION'
CODE_NO_FOLDS = 'OAS1_CHAIN_NO_FOLDS'


def _cfgs(name):
    g = BL.GRIDS[name]
    if not g:
        return [{}]
    keys = list(g)
    return [dict(zip(keys, v)) for v in itertools.product(*(g[k] for k in keys))]


def _shrink_key(name, cfg):
    """The pre-declared most-shrunken ordering, as a sort key."""
    out = []
    for k in BL.GRIDS[name]:
        v = float(cfg[k])
        out.append(-v if BL.SHRINK_DIRECTION[k] else v)
    return tuple(out)


def tune(name, hist, *, inner_k: int = INNER_K, metric: str = 'mae') -> Outcome:
    """Select a configuration using ONLY `hist`, by an inner forward chain."""
    cfgs = _cfgs(name)
    if len(cfgs) == 1:
        return Outcome.ok('OAS1_CFG_FIXED', value=cfgs[0],
                          detail=f'{name}: no hyperparameter to select',
                          baseline=name, cfg=dict(cfgs[0]), n_cfgs=1,
                          inner_folds=[], tie_break=BL.TIE_BREAK)
    ords = sorted({r['ordinal'] for r in hist})
    inner = [o for o in ords[1:]][-int(inner_k):]
    scores = {}
    folds = []
    for o in inner:
        tr = [r for r in hist if r['ordinal'] < o]
        te = [r for r in hist if r['ordinal'] == o]
        if not tr or not te:
            continue
        assert max(r['ordinal'] for r in tr) < o, 'inner fold leaks'
        y = np.array([r['epa'] for r in te], float)
        for c in cfgs:
            p = BL.predict(name, tr, te, c)
            if p.state.value != 'PASS':
                continue
            scores.setdefault(tuple(sorted(c.items())), []).append(
                EV.SCORERS[metric](y, p.value))
        folds.append({'ordinal': int(o), 'n_train': len(tr), 'n_test': len(te)})
    if not scores:
        return Outcome.fail(
            CODE_NO_FOLDS,
            f'{name}: no inner fold produced a score, so no configuration can '
            f'be selected from this history.', cause=Cause.DATA)
    means = {k: float(np.mean(v)) for k, v in scores.items()}
    ses = {k: float(np.std(v, ddof=1) / np.sqrt(len(v)))
           for k, v in scores.items() if len(v) > 1}
    best = min(means, key=lambda k: means[k])
    thr = means[best] + ses.get(best, 0.0)
    within = [k for k in means if means[k] <= thr]
    chosen = sorted(within, key=lambda k: _shrink_key(name, dict(k)))[0]
    return Outcome.ok(
        'OAS1_CFG_SELECTED', value=dict(chosen),
        detail=f'{name}: {dict(chosen)} from {len(cfgs)} config(s) over '
               f'{len(folds)} inner fold(s); best {dict(best)} at '
               f'{metric} {means[best]:.5f}, {len(within)} within 1 SE',
        baseline=name, cfg=dict(chosen), n_cfgs=len(cfgs),
        inner_folds=folds, inner_metric=metric,
        best_cfg=dict(best), best_score=means[best],
        one_se_threshold=thr, n_within_one_se=len(within),
        within_one_se=[dict(k) for k in within],
        tie_break=BL.TIE_BREAK,
        chosen_is_best=dict(chosen) == dict(best))


def _strata(hist, test):
    """True where the offensive club has NO prior-season history.

    The cold-start stratum is where B1 and B5 fall back, so scoring it
    separately is what stops a pooled number hiding that a sixth of the
    comparison was four estimators rather than six.
    """
    season = test[0]['season']
    seen = {r['offense_team'] for r in hist if r['season'] == season - 1}
    return [r['offense_team'] not in seen for r in test]


def _stratum_scores(y, p, strata):
    out = {}
    m = np.asarray(strata, bool)
    for label, sel in (('cold_start', m), ('established', ~m)):
        if sel.sum() == 0:
            out[f'mae_{label}'] = None
            out[f'n_{label}'] = 0
            continue
        out[f'mae_{label}'] = float(np.abs(y[sel] - p[sel]).mean())
        out[f'n_{label}'] = int(sel.sum())
    return out


def _fb_counts(fb):
    return {k: v for k, v in fb.items() if isinstance(v, int)}


def _b4_conv(fb):
    b = fb.get('b4')
    if not isinstance(b, dict):
        return None
    return {'converged': b.get('converged'), 'n_iter': b.get('n_iter'),
            'used': b.get('used'), 'final_change': b.get('final_change')}


#: A POINT FORECAST'S CRPS IS ITS ABSOLUTE ERROR. Verified numerically
#: against the imported `crps` on one-draw inputs: identical to 1e-12 on
#: every case tested. The baselines emit point forecasts, so the CRPS column
#: is MAE under another name and must not be read as a second piece of
#: evidence. A distributional candidate would make them differ.
CRPS_IS_MAE_FOR_POINT_FORECASTS = True


def run(rows, *, play_class: str, folds, inner_k: int = INNER_K) -> Outcome:
    """Score every baseline over the declared folds. Nothing is fitted here."""
    kept = [r for r in rows if r.get('play_class') == play_class
            and r.get('excluded_reason') == 'none'
            and r.get('offense_team') and r.get('defense_team')]
    out = {n: [] for n in BL.NAMES}
    fold_rows = []
    pooled_y, pooled_game, pooled_team = [], [], []
    pooled_pred = {}
    for ordi in folds:
        hist = [r for r in kept if r['ordinal'] < ordi]
        test = [r for r in kept if r['ordinal'] == ordi]
        if not hist or not test:
            continue
        # THE ORDINAL GUARD. An assertion, not a comment.
        mx = max(r['ordinal'] for r in hist)
        if mx >= ordi:
            return Outcome.fail(
                CODE_LEAK,
                f'fold {ordi}: the fitting set reaches ordinal {mx}. '
                f'A single off-by-one here improves every score and '
                f'invalidates the whole chain.',
                cause=Cause.GOVERNANCE, fold=int(ordi), max_hist_ordinal=mx)
        y = np.array([r['epa'] for r in test], float)
        games = [r['game_id'] for r in test]
        teams = [r['offense_team'] for r in test]
        # IDENTICAL ROW SETS FOR EVERY ESTIMATOR, recorded so it is checkable.
        h_hash, t_hash = BL.rowset_hash(hist), BL.rowset_hash(test)
        rec = {'ordinal': int(ordi), 'n_hist': len(hist), 'n_test': len(test),
               'hist_rowset_sha256': h_hash, 'test_rowset_sha256': t_hash,
               'n_game_clusters': len(set(games)),
               'n_team_clusters': len(set(teams))}
        preds = {}
        pooled_y.append(y)
        pooled_game.append(np.asarray(games, dtype=object))
        pooled_team.append(np.asarray(teams, dtype=object))
        strata = _strata(hist, test)
        rec['n_cold_start'] = int(sum(strata))
        rec['n_established'] = int(len(strata) - sum(strata))
        for name in BL.NAMES:
            t = tune(name, hist, inner_k=inner_k)
            if t.state.value != 'PASS':
                out[name].append({**rec, 'state': t.state.value,
                                  'code': t.code})
                continue
            p = BL.predict(name, hist, test, t.value)
            if p.state.value != 'PASS':
                out[name].append({**rec, 'state': p.state.value,
                                  'code': p.code})
                continue
            preds[name] = p.value
            pooled_pred.setdefault(name, []).append(p.value)
            cal = EV.calibration_slope(y, p.value)
            out[name].append({
                **rec, 'state': 'PASS', 'cfg': t.value,
                'cfg_is_best_scoring': t.evidence.get('chosen_is_best'),
                'n_within_one_se': t.evidence.get('n_within_one_se'),
                'mae': EV.SCORERS['mae'](y, p.value),
                'rmse': EV.SCORERS['rmse'](y, p.value),
                'calibration_slope': cal['slope'],
                'calibration_intercept': cal['intercept'],
                'predictor_variance': cal['predictor_variance'],
                'pred_sd': float(np.std(p.value)),
                'fallbacks': _fb_counts(p.evidence['fallbacks']),
                'b4_converged': _b4_conv(p.evidence['fallbacks']),
                # CRPS OF A POINT FORECAST IS EXACTLY ITS ABSOLUTE ERROR.
                # Reported because it was asked for, and labelled because a
                # third column identical to MAE would otherwise read as
                # independent evidence. See `crps_is_mae_for_point_forecasts`.
                'crps': EV.SCORERS['mae'](y, p.value),
                'season': int(ordi // 100),
                **_stratum_scores(y, p.value, strata),
            })
        fold_rows.append({'ordinal': int(ordi), **rec,
                          'baselines_scored': sorted(preds)})
    pooled_pred = {k: np.concatenate(v) for k, v in pooled_pred.items()
                   if len(v) == len(fold_rows)}
    if not fold_rows:
        return Outcome.fail(CODE_NO_FOLDS, 'no fold produced a score')
    # CLUSTERED DELTAS AGAINST THE DECISIVE COMPARATOR.
    #
    # Pooled across folds, resampling CLUSTERS rather than plays. i.i.d.
    # intervals are wrong here in a known direction: this project has already
    # measured them as roughly threefold too narrow, so a half-percent MAE gap
    # would look significant under them.
    #
    # Two clusterings, because they answer different questions. By GAME: all
    # plays in a game share weather, officiating, script and both rosters. By
    # TEAM: a unit estimate is reused across that club's whole season, which a
    # per-game cluster understates.
    deltas = {}
    if pooled_y:
        Y = np.concatenate(pooled_y)
        G = np.concatenate(pooled_game)
        T = np.concatenate(pooled_team)
        base = pooled_pred.get('B5')
        for name in BL.NAMES:
            if name == 'B5' or name not in pooled_pred or base is None:
                continue
            row = {}
            for lbl, cl in (('by_game', G), ('by_team', T)):
                try:
                    d = EV.clustered_delta(EV.SCORERS['mae'], Y,
                                           pooled_pred[name], base, cl)
                    row[lbl] = {k: d[k] for k in
                                ('delta', 'ci95', 'p_a_better', 'n_rows',
                                 'n_clusters', 'R')}
                except Exception as e:                        # noqa: BLE001
                    row[lbl] = {'error': f'{type(e).__name__}: {e}'}
            deltas[name] = row
    summ = {}
    for name in BL.NAMES:
        ok = [r for r in out[name] if r.get('state') == 'PASS']
        if not ok:
            summ[name] = {'n_folds': 0, 'state': 'NOT_SCORED'}
            continue
        sl = [r['calibration_slope'] for r in ok
              if r['calibration_slope'] is not None]
        n_cold = sum(r['n_cold_start'] for r in ok)
        n_est = sum(r['n_established'] for r in ok)
        # POOLED = play-weighted across folds, which is the honest pooling for
        # a per-play metric. A fold mean would weight a 500-play week the same
        # as a 1,200-play one.
        w = np.array([r['n_test'] for r in ok], float)
        mae_p = float(np.average([r['mae'] for r in ok], weights=w))
        rmse_p = float(np.sqrt(np.average([r['rmse'] ** 2 for r in ok],
                                          weights=w)))
        cold = [(r['mae_cold_start'], r['n_cold_start']) for r in ok
                if r['mae_cold_start'] is not None and r['n_cold_start']]
        est = [(r['mae_established'], r['n_established']) for r in ok
               if r['mae_established'] is not None and r['n_established']]
        nonconv = [r['b4_converged'] for r in ok
                   if r.get('b4_converged') is not None]
        fb_tot = {}
        for r in ok:
            for k, v in (r.get('fallbacks') or {}).items():
                fb_tot[k] = fb_tot.get(k, 0) + int(v)
        per_season = {}
        for sea in sorted({r['season'] for r in ok}):
            sr = [r for r in ok if r['season'] == sea]
            ws = np.array([r['n_test'] for r in sr], float)
            per_season[str(sea)] = {
                'n_folds': len(sr), 'n_plays': int(ws.sum()),
                'mae': float(np.average([r['mae'] for r in sr], weights=ws)),
                'rmse': float(np.sqrt(np.average(
                    [r['rmse'] ** 2 for r in sr], weights=ws)))}
        summ[name] = {
            'n_folds': len(ok),
            'n_plays_scored': int(w.sum()),
            'mae': float(np.mean([r['mae'] for r in ok])),
            'mae_pooled_play_weighted': mae_p,
            'rmse': float(np.mean([r['rmse'] for r in ok])),
            'rmse_pooled_play_weighted': rmse_p,
            'crps_pooled': mae_p,
            'crps_note': 'identical to MAE by construction: the CRPS of a '
                         'point forecast IS its absolute error',
            'mae_sd_across_folds': float(np.std([r['mae'] for r in ok],
                                                ddof=1)) if len(ok) > 1 else None,
            'calibration_slope_mean': float(np.mean(sl)) if sl else None,
            'n_folds_with_slope': len(sl),
            'n_folds_slope_undefined': len(ok) - len(sl),
            'pred_sd_mean': float(np.mean([r['pred_sd'] for r in ok])),
            'cfgs_selected': sorted({str(r.get('cfg')) for r in ok}),
            'n_distinct_cfgs': len({str(r.get('cfg')) for r in ok}),
            'per_season': per_season,
            'n_cold_start_plays': int(n_cold),
            'n_established_plays': int(n_est),
            'mae_cold_start': (float(np.average([c for c, _ in cold],
                                                weights=[n for _, n in cold]))
                               if cold else None),
            'mae_established': (float(np.average([c for c, _ in est],
                                                 weights=[n for _, n in est]))
                                if est else None),
            'fallback_counts_total': fb_tot,
            'b4_n_folds_converged': sum(1 for c in nonconv
                                        if c.get('converged')),
            'b4_n_folds_not_converged': sum(1 for c in nonconv
                                            if not c.get('converged')),
            'b4_fallback_used_in_folds': sorted(
                {c.get('used') for c in nonconv if c.get('used')}),
        }
    return Outcome.ok(
        CODE_OK, value={'per_fold': out, 'summary': summ,
                        'folds': fold_rows,
                        'clustered_delta_vs_B5': deltas},
        detail=f'{play_class}: {len(fold_rows)} fold(s), '
               f'{len(BL.NAMES)} baseline(s)',
        spec_version=SPEC_VERSION, play_class=play_class,
        n_folds=len(fold_rows), inner_k=int(inner_k),
        ordinal_guard='asserted per fold',
        identical_rowsets='every baseline receives the same hist and test '
                          'objects; both hashes recorded per fold')
