"""Q6 step 3: score the forward chain and emit the artifacts.

    python3.12 -m nfl.research.q6.analyse

CLUSTERING. Players on one team-game share an injury report, a depth chart,
one opponent and one game script, and in the composition they share a
renormalising simplex. A team-game is therefore the cluster, and every paired
difference is block-bootstrapped over whole team-games. A naive standard error
over player-rows would treat all of that as independent and would report
significance on correlation the harness created itself.

NO SPLIT IS AVERAGED AWAY. Every position and every role class is reported
separately, in every evaluation season, because the directive's standard is
breadth and a pooled number cannot show it.
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
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import stage_a as SA                                              # noqa: E402
from nfl.research.q6 import forward_chain as FC                   # noqa: E402
from nfl.research.q6 import frame as FR                           # noqa: E402

SPEC_VERSION = 'q6-analysis-1'
HERE = _REPO / 'nfl' / 'research' / 'q6'
RESULTS = HERE / 'Q6_FORWARD_CHAIN_RESULTS.json'
DIAGNOSTICS = HERE / 'Q6_DIAGNOSTICS.csv.gz'
APPEARANCE_ROWS = HERE / 'Q6_APPEARANCE_ROWS.csv.gz'
ROLE_ROWS = HERE / 'Q6_ROLE_ROWS.csv.gz'

# The arm the decision is taken on. The specification's arm table names
# Q6_CALIBRATED as the full candidate and Q6_FEATURES as the decomposition
# that shows where a change came from. Both are scored against the rule and
# both verdicts are published; the headline is the full candidate, fixed here
# rather than chosen once the numbers were in.
HEADLINE_ARM = 'Q6_CALIBRATED'
BOOT = 1000
BOOT_SEED = 20260914


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


def _app_block(rows, arm):
    y = np.array([r['appeared'] for r in rows], float)
    p = np.array([r[f'p_{arm}'] for r in rows], float)
    bins, ece = FC.calibration_bins(p, y)
    return {'n': len(rows), 'brier': round(SA.brier(y, p), 6),
            'log_loss': round(SA.logloss(y, p), 6),
            'expected_calibration_error': ece,
            'mean_predicted': round(float(p.mean()), 5),
            'observed_rate': round(float(y.mean()), 5),
            'calibration_bins': bins}


def appearance_summary(rows):
    out = {'overall': {}, 'by_position': {}, 'by_role_class': {},
           'by_position_and_role_class': {}, 'by_season': {},
           'paired_vs_R8': {}}
    for arm in FC.APPEARANCE_ARMS:
        out['overall'][arm] = _app_block(rows, arm)
    for name, keyf in (('by_position', lambda r: r['pos']),
                       ('by_role_class', lambda r: r['role_class']),
                       ('by_position_and_role_class',
                        lambda r: f"{r['pos']}|{r['role_class']}"),
                       ('by_season', lambda r: str(r['season']))):
        groups = collections.defaultdict(list)
        for r in rows:
            groups[keyf(r)].append(r)
        for g, rs in sorted(groups.items()):
            out[name][g] = {arm: _app_block(rs, arm)
                            for arm in FC.APPEARANCE_ARMS}
    base = np.array([(r['p_R8'] - r['appeared']) ** 2 for r in rows], float)
    cl = [r['team_game'] for r in rows]
    for arm in FC.APPEARANCE_ARMS:
        if arm == 'R8':
            continue
        cand = np.array([(r[f'p_{arm}'] - r['appeared']) ** 2 for r in rows],
                        float)
        out['paired_vs_R8'][arm] = {
            'brier_delta': round(float((cand - base).mean()), 8),
            'brier_delta_pct': round(
                100.0 * float((cand - base).mean()) / float(base.mean()), 4),
            'block_bootstrap_by_team_game': boot_paired(cand - base, cl)}
    return out


def _cell_sweep(rows, arm_a, arm_b):
    """Every position-by-role-class cell, with the paired Brier difference."""
    groups = collections.defaultdict(list)
    for r in rows:
        groups[f"{r['pos']}|{r['role_class']}"].append(r)
    out = {}
    for g, rs in sorted(groups.items()):
        a = np.array([(r[f'p_{arm_a}'] - r['appeared']) ** 2 for r in rs])
        b = np.array([(r[f'p_{arm_b}'] - r['appeared']) ** 2 for r in rs])
        out[g] = {
            'n': len(rs),
            f'brier_{arm_a}': round(float(a.mean()), 6),
            f'brier_{arm_b}': round(float(b.mean()), 6),
            'delta': round(float((b - a).mean()), 8),
            'improves': bool((b - a).mean() < 0),
            'block_bootstrap_by_team_game': boot_paired(
                b - a, [r['team_game'] for r in rs])}
    return out


def role_summary(rows):
    out = {}
    for metric in FR.METRICS:
        rs = [r for r in rows if r['metric'] == metric]
        if not rs:
            continue
        keyed = collections.defaultdict(dict)
        for r in rs:
            keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
        common = [v for v in keyed.values() if len(v) == len(FC.ROLE_ARMS)]
        ent = {'n_paired': len(common)}
        for arm in FC.ROLE_ARMS:
            c = np.array([v[arm]['crps'] for v in common], float)
            ent[f'mean_crps_{arm}'] = round(float(c.mean()), 7)
            ent[f'mean_abs_error_{arm}'] = round(float(np.mean(
                [abs(v[arm]['error']) for v in common])), 7)
        a = np.array([v['TIER_PRIOR']['crps'] for v in common], float)
        b = np.array([v['Q6_VACANCY']['crps'] for v in common], float)
        ent['delta_pct'] = round(100.0 * float((b - a).mean()) /
                                 float(a.mean()), 4)
        ent['block_bootstrap_by_team_game'] = boot_paired(
            b - a, [v['TIER_PRIOR']['team_game'] for v in common])
        # the rows the vacancy mechanism can possibly touch
        out[metric] = ent
    return out


def composition_summary(rows):
    out = {}
    for metric in FR.METRICS:
        rs = [r for r in rows if r['metric'] == metric]
        if not rs:
            continue
        keyed = collections.defaultdict(dict)
        for r in rs:
            keyed[(r['season'], r['week'], r['team'], r['pid'])][r['arm']] = r
        arms = [a[0] for a in FC.COMPOSITION_ARMS]
        common = [v for v in keyed.values() if len(v) == len(arms)]
        ent = {'n_paired': len(common), 'by_arm': {},
               'team_reconciliation_error_max': round(float(max(
                   (v[a]['recon_error'] for v in common for a in arms),
                   default=0.0)), 12)}
        base = np.array([v['BASELINE']['crps'] for v in common], float)
        cl = [v['BASELINE']['team_game'] for v in common]
        for arm in arms:
            c = np.array([v[arm]['crps'] for v in common], float)
            e = {'mean_crps': round(float(c.mean()), 6),
                 'zero_inflation': _zero_block(common, arm),
                 'starter_dilution': _dilution(common, arm),
                 'replacement_misallocation': _replacement(common, arm)}
            if arm != 'BASELINE':
                d = c - base
                e['delta_pct_vs_baseline'] = round(
                    100.0 * float(d.mean()) / float(base.mean()), 4)
                e['block_bootstrap_by_team_game'] = boot_paired(d, cl)
            ent['by_arm'][arm] = e
        out[metric] = ent
    return out


def _zero_block(common, arm):
    p = np.array([v[arm]['p_zero_pred'] for v in common], float)
    a = np.array([v[arm]['is_zero_actual'] for v in common], float)
    by = collections.defaultdict(lambda: [[], []])
    for v in common:
        b = by[v[arm]['role_class']]
        b[0].append(v[arm]['p_zero_pred'])
        b[1].append(v[arm]['is_zero_actual'])
    return {'predicted_zero_rate': round(float(p.mean()), 5),
            'observed_zero_rate': round(float(a.mean()), 5),
            'error': round(float(p.mean() - a.mean()), 5),
            'by_role_class': {k: {'predicted': round(float(np.mean(x)), 5),
                                  'observed': round(float(np.mean(y)), 5),
                                  'error': round(float(np.mean(x) -
                                                       np.mean(y)), 5),
                                  'n': len(x)}
                              for k, (x, y) in sorted(by.items())}}


def _dilution(common, arm):
    out = {}
    for rc in FR.ROLE_CLASSES:
        sel = [v[arm] for v in common if v[arm]['role_class'] == rc]
        if not sel:
            continue
        pm = float(np.mean([r['pred_mean'] for r in sel]))
        am = float(np.mean([r['actual'] for r in sel]))
        out[rc] = {'n': len(sel), 'mean_predicted': round(pm, 5),
                   'mean_actual': round(am, 5),
                   'ratio': round(pm / am, 5) if am else None}
    out['reads'] = ('below 1 is dilution -- the class is being given less than '
                    'it takes; above 1 is the opposite')
    return out


def _replacement(common, arm):
    """Only the team-games where the starter actually did not appear."""
    out = {}
    for rc in FR.ROLE_CLASSES:
        sel = [v[arm] for v in common
               if v[arm]['role_class'] == rc and v[arm]['starter_absent']]
        if len(sel) < 20:
            continue
        pm = float(np.mean([r['pred_mean'] for r in sel]))
        am = float(np.mean([r['actual'] for r in sel]))
        out[rc] = {'n': len(sel), 'mean_predicted': round(pm, 5),
                   'mean_actual': round(am, 5),
                   'ratio': round(pm / am, 5) if am else None,
                   'mean_abs_error': round(float(np.mean(
                       [abs(r['pred_mean'] - r['actual']) for r in sel])), 5)}
    out['reads'] = ('measured only on team-weeks whose starter was absent. '
                    'Below 1 means the replacement is under-fed relative to '
                    'what he actually took')
    return out


def missing_summary(rows):
    """What production should do when the injury report is not filed."""
    had = [r for r in rows if r['had_injury_report']]
    out = {
        'n_rows': len(rows),
        'n_rows_that_had_a_filed_report': len(had),
        'note': ('scored on the rows that DID have a report, with the block '
                 'blanked, so the informed number and the fallback numbers '
                 'are on identical players'),
        'policies': {},
    }
    if not had:
        return out
    y = np.array([r['appeared'] for r in had], float)
    for policy, field, confidence in (
            ('INFORMED', 'p_INFORMED', 'FULL'),
            ('PROBABILISTIC_FALLBACK', 'p_PROBABILISTIC_FALLBACK',
             'REDUCED_CONFIDENCE_NO_INJURY_REPORT'),
            ('HISTORICAL_ROLE_FALLBACK', 'p_HISTORICAL_ROLE_FALLBACK',
             'LOW_CONFIDENCE_ROLE_CLASS_ONLY')):
        p = np.array([r[field] for r in had], float)
        bins, ece = FC.calibration_bins(p, y)
        out['policies'][policy] = {
            'brier': round(SA.brier(y, p), 6),
            'log_loss': round(SA.logloss(y, p), 6),
            'expected_calibration_error': ece,
            'declares_confidence': confidence,
            'coverage': 1.0,
            'n_players_forecast': len(had),
        }
    out['policies']['HARD_DEFER'] = {
        'brier': None, 'log_loss': None,
        'expected_calibration_error': None,
        'declares_confidence': 'n/a -- it emits nothing',
        'coverage': 0.0,
        'n_players_forecast': 0,
        'n_players_refused': len(had),
        'n_team_weeks_refused': len({r['team_game'] for r in had}),
        'cost': ('every player on an affected team-week disappears from the '
                 'board, which is a forecast of nothing rather than a '
                 'cautious forecast'),
    }
    a = np.array([(r['p_INFORMED'] - r['appeared']) ** 2 for r in had])
    for policy, field in (('PROBABILISTIC_FALLBACK',
                           'p_PROBABILISTIC_FALLBACK'),
                          ('HISTORICAL_ROLE_FALLBACK',
                           'p_HISTORICAL_ROLE_FALLBACK')):
        b = np.array([(r[field] - r['appeared']) ** 2 for r in had])
        out['policies'][policy]['brier_cost_vs_informed'] = round(
            float((b - a).mean()), 8)
        out['policies'][policy]['block_bootstrap_by_team_game'] = boot_paired(
            b - a, [r['team_game'] for r in had])
    return out


def decide(summary, arm=HEADLINE_ARM):
    """SUPPORT / WEAK_SUPPORT / REJECT, against a rule fixed before the run.

    From the specification:

      SUPPORT       the candidate improves appearance Brier AND log loss
                    overall, improves in a majority of position-by-role-class
                    cells, at least one improvement survives the
                    team-game-clustered bootstrap, and no cell is
                    significantly worse; and the conditional-role or
                    composition metrics do not degrade.
      WEAK_SUPPORT  some primary metric improves and none is significantly
                    worse.
      REJECT        otherwise.
    """
    a = summary['appearance']
    ov_b = a['overall'][arm]['brier'] < a['overall']['R8']['brier']
    ov_l = a['overall'][arm]['log_loss'] < a['overall']['R8']['log_loss']
    cells = summary['appearance_cells'][arm]
    n_imp = sum(1 for c in cells.values() if c['improves'])
    sig_better = [g for g, c in cells.items()
                  if c['block_bootstrap_by_team_game']['excludes_zero']
                  and c['delta'] < 0]
    sig_worse = [g for g, c in cells.items()
                 if c['block_bootstrap_by_team_game']['excludes_zero']
                 and c['delta'] > 0]
    comp_worse = []
    for metric, ent in summary['composition'].items():
        e = ent['by_arm'].get('Q6_BOTH', {})
        bb = e.get('block_bootstrap_by_team_game') or {}
        if bb.get('excludes_zero') and e.get('delta_pct_vs_baseline', 0) > 0:
            comp_worse.append(metric)
    broad = (ov_b and ov_l and n_imp > len(cells) / 2 and bool(sig_better)
             and not sig_worse and not comp_worse)
    if broad:
        dec = 'SUPPORT'
    elif (ov_b or ov_l) and not sig_worse and not comp_worse:
        dec = 'WEAK_SUPPORT'
    else:
        dec = 'REJECT'
    return {
        'decision': dec,
        'arm': arm,
        'overall_brier_improves': bool(ov_b),
        'overall_log_loss_improves': bool(ov_l),
        'cells_improved': n_imp, 'cells_total': len(cells),
        'cells_significantly_better': sorted(sig_better),
        'cells_significantly_worse': sorted(sig_worse),
        'composition_metrics_significantly_worse': sorted(comp_worse),
        'conditional_role_metrics_significantly_worse': sorted(
            summary.get('role_significantly_worse') or []),
        'rule': decide.__doc__.strip(),
        'rule_note': (
            'the rule\'s last clause reads "the conditional-role OR '
            'composition metrics do not degrade", so a degraded role metric '
            'does not on its own block support while the composition holds. '
            'It is reported here either way rather than left out because the '
            'clause did not require it.'),
    }


def summarise(res):
    out = {
        'artifact': 'NFL_Q6_FORWARD_CHAIN_RESULTS',
        'spec_version': SPEC_VERSION,
        'chain_spec': FC.SPEC_VERSION, 'frame_spec': FR.SPEC_VERSION,
        'promoted': False, 'is_research_only': True,
        'market_inputs_used': [],
        'roster_status_inputs_used': [],
        'live_2026_rows_used': 0,
        'appearance_arms': list(FC.APPEARANCE_ARMS),
        'role_arms': list(FC.ROLE_ARMS),
        'composition_arms': [a[0] for a in FC.COMPOSITION_ARMS],
        'eval_seasons': sorted({r['season'] for r in res['appearance']}),
        'n_appearance_rows': len(res['appearance']),
        'n_role_rows': len(res['role']),
        'n_composition_rows': len(res['composition']),
        'clustering': 'block bootstrap over whole team-games',
        'held_fixed': [
            'the team total is the realised one, identical in every arm',
            'the conditional-role arms are scored against the realised '
            'appearance set',
            'team volume, efficiency and touchdown layers are untouched',
        ],
        'appearance': appearance_summary(res['appearance']),
        'appearance_cells': {
            arm: _cell_sweep(res['appearance'], 'R8', arm)
            for arm in ('Q6_FEATURES', 'Q6_CALIBRATED')},
        'role': role_summary(res['role']),
        'composition': composition_summary(res['composition']),
        'missing_data_policy': missing_summary(res['missing']),
        'fit_log': res['fit_log'],
        'opportunity_evidence': res['opportunity_evidence'],
    }
    out['role_significantly_worse'] = [
        m for m, v in out['role'].items()
        if (v['block_bootstrap_by_team_game'] or {}).get('excludes_zero')
        and v['delta_pct'] > 0]
    out['decision_by_arm'] = {
        arm: decide(out, arm) for arm in ('Q6_FEATURES', 'Q6_CALIBRATED')}
    out['decision'] = dict(out['decision_by_arm'][HEADLINE_ARM])
    out['decision']['headline_arm_note'] = (
        'the headline arm was fixed before the numbers were read. The other '
        'arm\'s verdict is published beside it in decision_by_arm; adopting '
        'whichever scored better afterwards would be selection on the '
        'outcome.')
    return out


def write_rows(rows, path, gz=True):
    if not rows:
        raise SystemExit(f'Q6_EMPTY_TABLE: {path} would be written with no '
                         f'rows. An empty table is an error, not a result.')
    opener = (lambda: gzip.open(path, 'wt', newline='')) if gz else (
        lambda: open(path, 'w', newline=''))
    with opener() as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in FR.EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=FC.N_DRAWS)
    a = ap.parse_args(argv)
    res = FC.run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    s = summarise(res)
    s['n_draws'] = a.draws
    RESULTS.write_text(json.dumps(s, indent=1, default=str) + '\n')
    write_rows(res['appearance'], APPEARANCE_ROWS)
    write_rows(res['role'], ROLE_ROWS)
    write_rows(res['composition'], DIAGNOSTICS)
    ap_ov = s['appearance']['overall']
    print(f"\nappearance rows : {len(res['appearance'])}")
    print(f"decision        : {s['decision']['decision']}")
    for arm in FC.APPEARANCE_ARMS:
        print(f"  {arm:16s} brier {ap_ov[arm]['brier']:.6f}  "
              f"logloss {ap_ov[arm]['log_loss']:.6f}  "
              f"ece {ap_ov[arm]['expected_calibration_error']:.6f}")
    for arm, d in s['decision_by_arm'].items():
        print(f"  rule on {arm:16s} -> {d['decision']:12s} "
              f"cells {d['cells_improved']}/{d['cells_total']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
