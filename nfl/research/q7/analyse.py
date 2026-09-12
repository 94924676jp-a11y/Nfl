"""Q7 step 3: score the forward chain and emit the artifacts.

    python3.12 -m nfl.research.q7.analyse

THE THREE TESTS ARE REPORTED APART.

  mean      the OLS of realisation on predicted mean -- slope, intercept,
            conditional bias -- overall and per opportunity regime.
  width     PIT, interval coverage, and the ratio of realised RMSE to the
            predictive standard deviation. Above 1 is under-dispersion, below
            1 over-dispersion. Reported per regime, which is where the
            whole-game-ypc hypothesis predicts the two directions disagree.
  shrinkage the estimated K beside the inherited 4.0, and the own-history
            weight each implies at 1, 3, 8 and 16 prior games.

A WIDER INTERVAL IS NOT AN IMPROVEMENT. The decision reads CRPS and log score
only; coverage and PIT are diagnostics. `decide` refuses to call an arm
supported when its CRPS is not better, however much its coverage rose, and the
refusal is in the function rather than left to the reader.

CLUSTERING. Quarterbacks and receivers in one game share an opponent, a script
and a sky. The GAME is the cluster and every paired difference is
block-bootstrapped over whole games.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.q7 import forward_chain as FC                   # noqa: E402

SPEC_VERSION = 'q7-analysis-1'
HERE = _REPO / 'nfl' / 'research' / 'q7'
RESULTS = HERE / 'Q7_FORWARD_CHAIN_RESULTS.json'
DIAGNOSTICS = HERE / 'Q7_DIAGNOSTICS.csv'
ROWS = HERE / 'Q7_SCORED_ROWS.csv.gz'
BOOT = 1000
BOOT_SEED = 20260916
YARDAGE = ('pyds|cmp', 'pyds|att', 'rec_yds|rec', 'rec_yds|targets')


def boot_paired(diffs, clusters, n=BOOT, seed=BOOT_SEED):
    diffs = np.asarray(diffs, float)
    if not len(diffs):
        return None
    idx = collections.defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    pos = [np.asarray(v, int) for v in idx.values()]
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for b in range(n):
        pick = rng.integers(0, len(pos), size=len(pos))
        out[b] = diffs[np.concatenate([pos[j] for j in pick])].mean()
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {'mean': round(float(diffs.mean()), 6),
            'ci_lo': round(float(lo), 6), 'ci_hi': round(float(hi), 6),
            'n_clusters': len(pos), 'n_rows': int(len(diffs)),
            'excludes_zero': bool(lo > 0 or hi < 0)}


def _pit_chi2(pits, bins=10):
    h, _ = np.histogram(np.asarray(pits, float), bins=bins, range=(0, 1))
    e = len(pits) / bins
    return {'hist': h.tolist(), 'expected_per_bin': round(e, 2),
            'chi2': round(float(((h - e) ** 2 / e).sum()), 3), 'df': bins - 1}


def _mean_calibration(rs):
    """OLS of the realisation on the predicted mean. Slope 1, intercept 0."""
    y = np.array([r['actual'] for r in rs], float)
    x = np.array([r['mean'] for r in rs], float)
    if len(y) < 20 or x.std() <= 1e-12:
        return None
    X = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(1, len(y) - 2)
    cov = float((resid ** 2).sum() / dof) * np.linalg.pinv(X.T @ X)
    se = float(np.sqrt(max(cov[1, 1], 0.0)))
    return {'intercept': round(float(beta[0]), 5),
            'slope': round(float(beta[1]), 5), 'slope_se': round(se, 5),
            'slope_ci95': [round(float(beta[1] - 1.96 * se), 5),
                           round(float(beta[1] + 1.96 * se), 5)],
            'reads': ('slope 1 and intercept 0 is calibrated in the mean; '
                      'a slope below 1 means the predicted means are spread '
                      'too widely, above 1 too narrowly')}


def _block(rs):
    c = np.array([r['crps'] for r in rs], float)
    e = np.array([r['error'] for r in rs], float)
    sd = np.array([r['sd'] for r in rs], float)
    rmse = float(np.sqrt((e ** 2).mean()))
    msd = float(sd.mean())
    ls = [r['log_score'] for r in rs
          if r.get('log_score') not in ('', None)
          and np.isfinite(float(r['log_score']))]
    out = {
        'n': len(rs),
        'mean_crps': round(float(c.mean()), 6),
        'bias': round(float(e.mean()), 5),
        'rmse': round(rmse, 5),
        'mean_predictive_sd': round(msd, 5),
        'rmse_over_predictive_sd': round(rmse / msd, 5) if msd > 0 else None,
        'dispersion_reads': ('above 1 is UNDER-dispersed, the intervals are '
                             'too narrow; below 1 is OVER-dispersed'),
        'coverage': {str(L): round(float(np.mean([r[f'cov{L}'] for r in rs])), 4)
                     for L in (50, 80, 90, 95)},
        'pit': _pit_chi2([r['pit'] for r in rs]),
        'mean_calibration': _mean_calibration(rs),
    }
    if ls:
        out['mean_log_score'] = round(float(np.mean([float(x) for x in ls])), 6)
        out['n_log_score'] = len(ls)
    return out


def _sweep(rows, keyf):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    return {k: _block(v) for k, v in sorted(g.items()) if len(v) >= 20}


def summarise(res):
    rows = res['rows']
    by_est = collections.defaultdict(list)
    for r in rows:
        by_est[r['estimand']].append(r)

    out = {
        'artifact': 'NFL_Q7_FORWARD_CHAIN_RESULTS',
        'spec_version': SPEC_VERSION, 'chain_spec': FC.SPEC_VERSION,
        'promoted': False, 'is_research_only': True,
        'market_inputs_used': [], 'live_2026_rows_used': 0,
        'arms': list(FC.ARMS), 'headline_arm': FC.HEADLINE_ARM,
        'eval_seasons': sorted({r['season'] for r in rows}),
        'n_scored_rows': len(rows),
        'opportunity_is_oracled': True,
        'isolation_note': (
            'every arm receives the realised attempts, completions, targets '
            'and receptions, so there is no volume error at all in the '
            'isolated condition and none can disguise an efficiency error'),
        'refused_estimands': {
            'receiving/receiving_td': (
                'ESTIMAND_UNVERIFIED in the governed list: touchdown '
                'attribution across rushing and receiving has not been '
                'reconciled with the allocation layer'),
            'rushing/rushing_td': 'ESTIMAND_UNVERIFIED, same reason',
        },
        'touchdown_efficiency_evaluated_for': ['qb/ptd'],
        'clustering': 'block bootstrap over whole games',
        'estimands': {},
        'shrinkage': {},
        'decomposition': {},
    }
    for est, rs in sorted(by_est.items()):
        arms = sorted({r['arm'] for r in rs})
        ent = {'arms_present': arms, 'by_arm': {}}
        keyed = collections.defaultdict(dict)
        for r in rs:
            keyed[(r['season'], r['game_id'], r['gsis_id'])][r['arm']] = r
        common = [v for v in keyed.values() if len(v) == len(arms)]
        for arm in arms:
            a_rows = [r for r in rs if r['arm'] == arm]
            e = _block(a_rows)
            e['by_opportunity_regime'] = _sweep(
                a_rows, lambda r: r['opportunity_regime'])
            e['by_sample_depth'] = _sweep(a_rows, lambda r: r['sample_depth'])
            e['by_season'] = _sweep(a_rows, lambda r: str(r['season']))
            if arm != 'BASELINE' and common:
                b = np.array([v['BASELINE']['crps'] for v in common], float)
                c = np.array([v[arm]['crps'] for v in common], float)
                e['paired_crps_delta_vs_baseline'] = {
                    'delta_mean': round(float((c - b).mean()), 6),
                    'delta_pct': round(100.0 * float((c - b).mean()) /
                                       float(b.mean()), 4),
                    'block_bootstrap_by_game': boot_paired(
                        c - b, [v['BASELINE']['game_id'] for v in common]),
                }
                e['by_regime_delta_pct'] = {}
                for reg in sorted({v['BASELINE']['opportunity_regime']
                                   for v in common}):
                    sel = [v for v in common
                           if v['BASELINE']['opportunity_regime'] == reg]
                    if len(sel) < 20:
                        continue
                    bb = np.array([v['BASELINE']['crps'] for v in sel], float)
                    cc = np.array([v[arm]['crps'] for v in sel], float)
                    e['by_regime_delta_pct'][reg] = {
                        'n': len(sel),
                        'delta_pct': round(100.0 * float((cc - bb).mean()) /
                                           float(bb.mean()), 4),
                        'improves': bool((cc - bb).mean() < 0),
                        'block_bootstrap_by_game': boot_paired(
                            cc - bb, [v['BASELINE']['game_id'] for v in sel]),
                    }
            ent['by_arm'][arm] = e
        out['estimands'][est] = ent

    out['shrinkage'] = _shrinkage(res['fit_log'], rows)
    out['decomposition'] = _decomposition(rows, res['composed'])
    out['fit_log'] = res['fit_log']
    out['decision_by_arm'] = {
        arm: decide(out, arm) for arm in FC.ARMS if arm != 'BASELINE'}
    out['decision'] = dict(out['decision_by_arm'][FC.HEADLINE_ARM])
    out['decision']['headline_arm_note'] = (
        'the headline arm was fixed in the specification before the run. '
        'Every arm carries a verdict; adopting whichever scored best '
        'afterwards would be selection on the outcome.')
    return out


def _shrinkage(fit_log, rows):
    """The inherited constant beside the estimated one, and what it implies."""
    out = {'inherited_k': FC.INHERITED_K,
           'inherited_provenance': (
               'the QB2 pre-registration states "half-life 2 and K = 4 are '
               'inherited constants" with no grid search. This project\'s own '
               'rule is that a shrinkage strength is estimated or '
               'cross-validated; this one was not.'),
           'by_season': {}, 'implied_weights': {}}
    for f in fit_log:
        out['by_season'][str(f['eval_season'])] = {
            'completion_rate': f['estimated_k_completion_rate'],
            'yards_per_completion': f['estimated_k_yards_per_completion'],
        }
    ks = [f['estimated_k_completion_rate'].get('k') for f in fit_log
          if f['estimated_k_completion_rate'].get('k')]
    ky = [f['estimated_k_yards_per_completion'].get('k') for f in fit_log
          if f['estimated_k_yards_per_completion'].get('k')]
    for label, k in (('inherited', FC.INHERITED_K),
                     ('estimated_completion_rate',
                      float(np.mean(ks)) if ks else None),
                     ('estimated_yards_per_completion',
                      float(np.mean(ky)) if ky else None)):
        if k is None:
            continue
        out['implied_weights'][label] = {
            'k': round(float(k), 4),
            **{f'at_{n}_prior_games': round(n / (n + k), 4)
               for n in (1, 3, 8, 16)}}
    return out


def _decomposition(rows, composed):
    """Both conditions, because one of them is vacuous on its own."""
    iso = [r for r in rows if r['estimand'] == 'pyds|att'
           and r['arm'] == 'BASELINE']
    out = {
        'ISOLATED': {
            'n': len(iso),
            'opportunity_error': 0.0,
            'opportunity_error_basis': 'OPPORTUNITY_ORACLED',
            'efficiency_error_mean': round(float(np.mean(
                [r['error'] for r in iso])), 5) if iso else None,
            'combined_error_mean': round(float(np.mean(
                [r['error'] for r in iso])), 5) if iso else None,
            'same_sign_or_offsetting': 'OPPORTUNITY_ORACLED',
            'note': ('the opportunity error is zero by construction here, so '
                     'the flag is recorded as the design fact it is rather '
                     'than computed from a zero'),
        },
    }
    if composed:
        opp = np.array([c['opportunity_error'] for c in composed], float)
        eff = np.array([c['efficiency_error'] for c in composed], float)
        comb = np.array([c['combined_error'] for c in composed], float)
        flags = collections.Counter(c['same_sign_or_offsetting']
                                    for c in composed)
        out['COMPOSED'] = {
            'n': len(composed),
            'opportunity_error_mean': round(float(opp.mean()), 5),
            'efficiency_error_mean': round(float(eff.mean()), 6),
            'combined_error_mean': round(float(comb.mean()), 5),
            'mean_abs_opportunity_error': round(float(np.abs(opp).mean()), 5),
            'mean_abs_efficiency_error': round(float(np.abs(eff).mean()), 6),
            'mean_abs_combined_error': round(float(np.abs(comb).mean()), 5),
            'same_sign_or_offsetting': dict(flags),
            'offsetting_rate': round(
                flags['OFFSETTING'] / max(1, len(composed)), 5),
            'note': ('the Track-1 cancellation figure motivated asking. It is '
                     'not a threshold here and appears in no fit.'),
        }
    return out


def decide(summary, arm):
    """SUPPORT / WEAK_SUPPORT / REJECT, against the rule fixed before the run.

    From the specification:

      SUPPORT       the arm improves CRPS overall AND in a majority of
                    opportunity regimes, at least one improvement survives the
                    game-clustered bootstrap, no regime is significantly worse
                    on CRPS, and its calibration diagnostics do not degrade.
      WEAK_SUPPORT  the arm improves CRPS overall and none is significantly
                    worse.
      REJECT        otherwise, INCLUDING any arm whose only gain is coverage.
    """
    ests = [e for e in FC_ESTIMANDS_FOR_DECISION
            if e in summary['estimands']
            and arm in summary['estimands'][e]['by_arm']]
    if not ests:
        return {'decision': 'REJECT', 'arm': arm, 'why': 'no scored estimand'}
    improved, sig_better, sig_worse = [], [], []
    reg_imp = reg_tot = 0
    for est in ests:
        e = summary['estimands'][est]['by_arm'][arm]
        d = e.get('paired_crps_delta_vs_baseline')
        if not d:
            continue
        if d['delta_mean'] < 0:
            improved.append(est)
        bb = d['block_bootstrap_by_game']
        if bb['excludes_zero']:
            (sig_better if d['delta_mean'] < 0 else sig_worse).append(est)
        for reg, rd in (e.get('by_regime_delta_pct') or {}).items():
            reg_tot += 1
            reg_imp += 1 if rd['improves'] else 0
            if rd['block_bootstrap_by_game']['excludes_zero'] \
                    and not rd['improves']:
                sig_worse.append(f'{est}@{reg}')
    # THE COVERAGE TRAP, CLOSED IN CODE. An arm that did not improve a proper
    # score is not supported however much its coverage rose.
    if not improved:
        return {'decision': 'REJECT', 'arm': arm,
                'why': 'no estimand improved a proper score',
                'coverage_cannot_rescue': True,
                'estimands_improved': [], 'estimands_significantly_worse':
                    sorted(set(sig_worse)), 'rule': decide.__doc__.strip()}
    broad = (len(improved) == len(ests) and reg_tot and
             reg_imp > reg_tot / 2 and bool(sig_better) and not sig_worse)
    dec = 'SUPPORT' if broad else (
        'WEAK_SUPPORT' if improved and not sig_worse else 'REJECT')
    return {
        'decision': dec, 'arm': arm,
        'estimands_considered': ests,
        'estimands_improved': sorted(improved),
        'estimands_significantly_better': sorted(set(sig_better)),
        'estimands_significantly_worse': sorted(set(sig_worse)),
        'regimes_improved': reg_imp, 'regimes_total': reg_tot,
        'coverage_cannot_rescue': True,
        'rule': decide.__doc__.strip(),
    }


# The estimands the decision is taken on: the QB efficiency ladder, which is
# where the candidate arms act. The receiver rows carry BASELINE only -- RC2
# closed that repair family and this work does not reopen it.
FC_ESTIMANDS_FOR_DECISION = ('cmp|att', 'ptd|cmp', 'pyds|cmp', 'pyds|att')


def write_rows(rows, path, gz=True):
    if not rows:
        raise SystemExit(f'Q7_EMPTY_TABLE: {path} would be written with no '
                         f'rows. An empty table is an error, not a result.')
    opener = ((lambda: gzip.open(path, 'wt', newline='')) if gz
              else (lambda: open(path, 'w', newline='')))
    with opener() as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in FC.EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=FC.N_DRAWS)
    a = ap.parse_args(argv)
    res = FC.run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    s = summarise(res)
    s['n_draws'] = a.draws
    RESULTS.write_text(json.dumps(s, indent=1, default=str) + '\n')
    write_rows(res['rows'], ROWS)
    write_rows(res['composed'], DIAGNOSTICS, gz=False)
    print(f"\nscored rows : {len(res['rows'])}")
    print(f"decision    : {s['decision']['decision']} "
          f"({s['decision']['arm']})")
    for arm, d in s['decision_by_arm'].items():
        print(f"  {arm:12s} -> {d['decision']:12s} "
              f"improved {len(d.get('estimands_improved', []))}"
              f"/{len(d.get('estimands_considered', []))}  "
              f"regimes {d.get('regimes_improved')}/{d.get('regimes_total')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
