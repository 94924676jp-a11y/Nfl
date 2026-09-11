"""Track 1 step 5: score the forward chain and emit the acceptance artifacts.

    python3.12 -m nfl.research.track1.analyse

WHAT THE UNCERTAINTY HERE IS CLUSTERED ON, AND WHY IT HAS TO BE.

A slate is not 32 independent observations. The two teams in one game share a
single simulated score path by construction, so their Track 1 multipliers are
exactly opposed; and every game on one weekend shares the week's fitted
response curve, its fitted state model and its residual pool. A naive standard
error over team-games would treat all of that as independent and would report
a difference as significant on the strength of correlation it created itself.

So every paired CRPS difference is bootstrapped by resampling whole GAMES and,
separately, whole WEEKS, and both intervals are reported. Where they disagree
the wider one is the one that counts.

WHAT "BROAD" MEANS FOR THE DECISION, DECLARED BEFORE THE NUMBERS ARE READ.

The directive's standard is broad forward-chain improvement, not one era or
one metric. This module therefore reports every metric in every evaluation
season separately and never averages a split away. If improvement is confined
to a subset, the subset is the finding.
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

from nfl.research.track1 import forward_chain as FC                # noqa: E402
from nfl.research.track1 import response as RESP                   # noqa: E402
from nfl.research.track1 import state as ST                        # noqa: E402

SPEC_VERSION = 'track1-analysis-1'
HERE = _REPO / 'nfl' / 'research' / 'track1'
RESULTS = HERE / 'TRACK1_FORWARD_CHAIN_RESULTS.json'
DIAGNOSTICS = HERE / 'TRACK1_DIAGNOSTICS.csv'
ROWS = HERE / 'TRACK1_SCORED_ROWS.csv.gz'
BOOT = 2000
BOOT_SEED = 20260912


def _boot_paired(diffs, clusters, n=BOOT, seed=BOOT_SEED):
    """Block bootstrap of a paired mean difference, resampling whole clusters."""
    diffs = np.asarray(diffs, float)
    keys = list(dict.fromkeys(clusters))
    idx = collections.defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    pos = [np.asarray(idx[k], int) for k in keys]
    rng = np.random.default_rng(seed)
    out = np.empty(n)
    for b in range(n):
        pick = rng.integers(0, len(pos), size=len(pos))
        sel = np.concatenate([pos[j] for j in pick])
        out[b] = diffs[sel].mean()
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {'mean': float(diffs.mean()), 'ci_lo': float(lo), 'ci_hi': float(hi),
            'n_clusters': len(keys), 'n_rows': int(len(diffs)),
            'excludes_zero': bool(lo > 0 or hi < 0)}


def _pit_chi2(pits, bins=10):
    h, _ = np.histogram(np.asarray(pits, float), bins=bins, range=(0, 1))
    e = len(pits) / bins
    return {'hist': h.tolist(), 'expected_per_bin': round(e, 2),
            'chi2': round(float(((h - e) ** 2 / e).sum()), 3), 'df': bins - 1}


def _channel_diagnostics(rs):
    """What the pregame margin is actually worth for this metric, measured.

    THE TWO CHANNELS THAT A SIMULATED STATE CONFLATES.

    Within a game, trailing raises play count and pass rate -- that is the
    response curve, and it is large and real. Across games, a pregame
    favourite is simply a BETTER TEAM, and better teams sustain more drives
    whatever the script. The Track 1 multiplier carries only the first
    channel. Where the two agree in sign it should help; where they oppose,
    the multiplier can point the wrong way even though the response curve it
    came from is correct.

    Three measurements, so the reader can tell which case a metric is in:

      corr(own expected margin, realised value)     what the pregame signal is
                                                    worth for this metric, net
                                                    of both channels;
      corr(own expected margin, multiplier)         which way the state channel
                                                    points;
      corr(baseline point, multiplier)              whether the baseline
                                                    estimator already carried
                                                    the script.

    An earlier reading of this experiment attributed the negative result to
    the baseline already carrying the script. The first correlation below is
    small for every metric, so that explanation is WITHDRAWN rather than
    defended: the baseline does not carry it, and the opposing-channel account
    is what the numbers support.
    """
    b = np.array([r['baseline_point'] for r in rs], float)
    m = np.array([r['multiplier_expected'] for r in rs], float)
    y = np.array([r['actual'] for r in rs], float)
    mu = np.array([r['expected_margin'] for r in rs], float)
    # the multiplier is expressed from the forecast team's own side, so the
    # margin has to be too: a home underdog and an away underdog are the same
    # football situation.
    own = np.array([mu[i] if rs[i]['side'] == 'home' else -mu[i]
                    for i in range(len(rs))], float)
    out = {}
    if b.std() > 1e-12 and m.std() > 1e-12:
        out['corr_baseline_point_with_multiplier'] = round(
            float(np.corrcoef(b, m)[0, 1]), 5)
    if own.std() > 1e-12:
        out['corr_own_expected_margin_with_actual'] = round(
            float(np.corrcoef(own, y)[0, 1]), 5)
        if m.std() > 1e-12:
            out['corr_own_expected_margin_with_multiplier'] = round(
                float(np.corrcoef(own, m)[0, 1]), 5)
        else:
            # An untreated metric has a constant multiplier, so this
            # correlation does not exist. Saying so beats emitting a NaN that
            # a later reader has to guess the meaning of.
            out['corr_own_expected_margin_with_multiplier'] = None
            out['multiplier_is_constant'] = True
    out['reads'] = (
        'if the first correlation is near zero the pregame margin carries no '
        'net signal for this metric and any multiplier is noise; if it has '
        'the OPPOSITE sign to the second, the between-team quality channel '
        'outweighs the within-game script channel and the state response '
        'points the wrong way')
    return out


def _mechanism_calibration(rs):
    """Is the state response applied at the RIGHT strength, or over-applied?

    Regress the realised value on the baseline point and on the multiplier's
    own contribution. A coefficient of 1 on the contribution means the
    mechanism is scaled correctly; below 1 means it is applied too hard, above
    1 too softly. This is a DIAGNOSTIC, not a fitted correction -- nothing in
    either arm uses it.
    """
    y = np.array([r['actual'] for r in rs], float)
    b = np.array([r['baseline_point'] for r in rs], float)
    m = np.array([r['multiplier_expected'] for r in rs], float)
    contrib = b * (m - 1.0)
    if contrib.std() <= 1e-12:
        return None
    X = np.column_stack([np.ones(len(y)), b, contrib])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(1, len(y) - 3)
    s2 = float((resid ** 2).sum() / dof)
    cov = s2 * np.linalg.pinv(X.T @ X)
    se = float(np.sqrt(max(cov[2, 2], 0.0)))
    return {'coef_on_state_contribution': round(float(beta[2]), 4),
            'se': round(se, 4),
            'ci95': [round(float(beta[2] - 1.96 * se), 4),
                     round(float(beta[2] + 1.96 * se), 4)],
            'reads': ('1.0 means correctly scaled; below 1 over-applied; '
                      'above 1 under-applied')}


def summarise(rows, diags):
    by_metric = collections.defaultdict(list)
    for r in rows:
        by_metric[r['metric']].append(r)

    out = {
        'artifact': 'NFL_TRACK1_FORWARD_CHAIN_RESULTS',
        'spec_version': SPEC_VERSION,
        'response_spec': RESP.SPEC_VERSION,
        'state_spec': ST.SPEC_VERSION,
        'chain_spec': FC.SPEC_VERSION,
        'arms': list(FC.ARMS),
        'promoted': False,
        'is_research_only': True,
        'market_inputs_used': [],
        'n_scored_rows': len(rows),
        'eval_seasons': sorted({r['season'] for r in rows}),
        'metrics': {},
        'untreated_metrics': list(RESP.UNTREATED),
        'clustering_note': (
            'the two sides of a game share one simulated score path, so a '
            'team-game is not an independent observation. Every interval is '
            'a block bootstrap over whole games and, separately, whole weeks.'),
    }
    for metric, rs in sorted(by_metric.items()):
        base = np.array([r['BASELINE_crps'] for r in rs], float)
        entry = {
            'n': len(rs),
            'estimator': sorted({r['estimator'] for r in rs}),
            'is_treated': metric not in RESP.UNTREATED,
            'mean_crps': {},
            'discrimination_pearson_r': {},
            'sd_of_point': {},
            'sd_of_actual': round(float(np.std(
                [r['actual'] for r in rs])), 4),
            'pit_chi2': {},
            'coverage': {},
            'paired_crps_delta_vs_baseline': {},
            'by_season': {},
            'mechanism_calibration': _mechanism_calibration(rs),
            'channel_diagnostics': _channel_diagnostics(rs),
            'multiplier_sd': round(float(np.std(
                [r['multiplier_expected'] for r in rs])), 6),
        }
        y = np.array([r['actual'] for r in rs], float)
        for arm in FC.ARMS:
            c = np.array([r[f'{arm}_crps'] for r in rs], float)
            p = np.array([r[f'{arm}_mean'] for r in rs], float)
            entry['mean_crps'][arm] = round(float(c.mean()), 5)
            entry['sd_of_point'][arm] = round(float(p.std()), 5)
            entry['discrimination_pearson_r'][arm] = (
                round(float(np.corrcoef(p, y)[0, 1]), 5)
                if p.std() > 0 else None)
            entry['pit_chi2'][arm] = _pit_chi2(
                [r[f'{arm}_pit'] for r in rs])
            entry['coverage'][arm] = {
                str(L): round(float(np.mean([r[f'{arm}_cov{L}'] for r in rs])), 4)
                for L in (50, 80, 90, 95)}
            if arm == 'BASELINE':
                continue
            d = c - base
            entry['paired_crps_delta_vs_baseline'][arm] = {
                'delta_mean': round(float(d.mean()), 5),
                'delta_pct_of_baseline': round(
                    100.0 * float(d.mean()) / float(base.mean()), 4),
                'block_bootstrap_by_game': _boot_paired(
                    d, [r['game_id'] for r in rs]),
                'block_bootstrap_by_week': _boot_paired(
                    d, [f"{r['season']}-{r['week']}" for r in rs]),
                'n_rows_improved': int((d < 0).sum()),
                'n_rows_worsened': int((d > 0).sum()),
            }
        for season in sorted({r['season'] for r in rs}):
            srs = [r for r in rs if r['season'] == season]
            sb = np.array([r['BASELINE_crps'] for r in srs], float)
            ent = {'n': len(srs),
                   'mean_crps': {a: round(float(np.mean(
                       [r[f'{a}_crps'] for r in srs])), 5) for a in FC.ARMS}}
            for arm in FC.ARMS[1:]:
                sa = np.array([r[f'{arm}_crps'] for r in srs], float)
                ent[f'{arm}_delta_pct'] = round(
                    100.0 * float((sa - sb).mean()) / float(sb.mean()), 4)
                ent[f'{arm}_improves'] = bool((sa - sb).mean() < 0)
            entry['by_season'][str(season)] = ent
        out['metrics'][metric] = entry

    out['downstream_qb_propagation'] = _qb_summary(diags)
    return out


def _qb_summary(diags):
    """The propagation harness, with volume and efficiency error kept apart."""
    if not diags:
        return {'n': 0, 'note': 'no propagation rows were produced'}
    by_arm = collections.defaultdict(list)
    for d in diags:
        by_arm[d['arm']].append(d)
    keyed = {}
    for arm, ds in by_arm.items():
        keyed[arm] = {(d['season'], d['week'], d['team']): d for d in ds}
    common = set.intersection(*(set(v) for v in keyed.values()))
    out = {
        'harness_note': (
            'a fixed forward-chained room-share and efficiency model, '
            'byte-identical across arms including its random indices. It '
            'measures propagation of a team budget change. It is NOT the '
            'production quarterback layer and is never reported as its '
            'quality.'),
        'unit': 'QB ROOM per team-game, not the individual quarterback',
        'why_the_room': (
            'the split inside a room is not pregame-observable when a starter '
            'is replaced in game; charging that to a volume experiment would '
            'measure the wrong thing'),
        'n_team_games': len(common),
        'by_arm': {},
        'offsetting_error_rate': {},
    }
    base = {k: keyed['BASELINE'][k] for k in common}
    for arm in FC.ARMS:
        ds = [keyed[arm][k] for k in sorted(common)]
        ent = {}
        for m in ('room_dropbacks', 'room_attempts', 'room_pass_yards'):
            c = np.array([d[f'crps_{m}'] for d in ds], float)
            ent[f'mean_crps_{m}'] = round(float(c.mean()), 5)
            if arm != 'BASELINE':
                b = np.array([base[k][f'crps_{m}']
                              for k in sorted(common)], float)
                dd = c - b
                ent[f'delta_pct_{m}'] = round(
                    100.0 * float(dd.mean()) / float(b.mean()), 4)
                ent[f'block_bootstrap_by_game_{m}'] = _boot_paired(
                    dd, [keyed[arm][k]['game_id'] for k in sorted(common)])
        ent['mean_err_volume_dropbacks'] = round(float(np.mean(
            [d['err_volume_dropbacks'] for d in ds])), 4)
        ent['mean_err_volume_attempts'] = round(float(np.mean(
            [d['err_volume_attempts'] for d in ds])), 4)
        ent['mean_err_efficiency_ypa'] = round(float(np.mean(
            [d['err_efficiency_ypa'] for d in ds if d['err_efficiency_ypa'] != ''])), 5)
        ent['mean_err_final_pass_yards'] = round(float(np.mean(
            [d['err_final_pass_yards'] for d in ds])), 4)
        out['by_arm'][arm] = ent
        out['offsetting_error_rate'][arm] = round(float(np.mean(
            [d['offsetting'] for d in ds])), 4)
    out['offsetting_note'] = (
        'the share of team-games whose volume error and efficiency error have '
        'OPPOSITE signs, so the final yardage error is smaller than either '
        'component. A good final number produced this way is not mechanistic '
        'success and is not counted as one.')
    return out


def decide(summary):
    """SUPPORT / WEAK_SUPPORT / REJECT, against a rule stated before the run.

    The rule, from the directive: support requires BROAD forward-chain
    improvement, not one era or one metric. Operationalised as:

      SUPPORT       every treated metric improves overall, a majority of
                    treated metric-seasons improve, and at least one primary
                    metric's improvement survives the game-clustered bootstrap.
      WEAK_SUPPORT  some treated metric improves and no treated metric is
                    significantly worse under the game-clustered bootstrap.
      REJECT        otherwise.
    """
    treated = {m: e for m, e in summary['metrics'].items() if e['is_treated']}
    if not treated:
        return {'decision': 'REJECT', 'why': 'no metric was treated'}
    arm = 'TRACK1'
    improves, worse_sig, better_sig, seasons_improved, seasons_total = \
        [], [], [], 0, 0
    for m, e in treated.items():
        d = e['paired_crps_delta_vs_baseline'][arm]
        if d['delta_mean'] < 0:
            improves.append(m)
        bg = d['block_bootstrap_by_game']
        if bg['excludes_zero'] and d['delta_mean'] > 0:
            worse_sig.append(m)
        if bg['excludes_zero'] and d['delta_mean'] < 0:
            better_sig.append(m)
        for s, se in e['by_season'].items():
            seasons_total += 1
            seasons_improved += 1 if se[f'{arm}_improves'] else 0
    broad = (len(improves) == len(treated)
             and seasons_improved > seasons_total / 2
             and bool(better_sig))
    if broad:
        dec = 'SUPPORT'
    elif improves and not worse_sig:
        dec = 'WEAK_SUPPORT'
    else:
        dec = 'REJECT'
    return {
        'decision': dec,
        'treated_metrics': sorted(treated),
        'metrics_improved': sorted(improves),
        'metrics_significantly_better_by_game_cluster': sorted(better_sig),
        'metrics_significantly_worse_by_game_cluster': sorted(worse_sig),
        'metric_seasons_improved': seasons_improved,
        'metric_seasons_total': seasons_total,
        'rule': decide.__doc__.strip(),
    }


def write_rows(rows, path=ROWS):
    """Persist every scored row. A summary nobody can re-derive is an assertion."""
    if not rows:
        raise SystemExit('TRACK1_NO_SCORED_ROWS: an empty scoring table is an '
                         'error, not a result.')
    cols = list(rows[0])
    with gzip.open(path, 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def write_diagnostics(diags, path=DIAGNOSTICS):
    if not diags:
        raise SystemExit('TRACK1_NO_DIAGNOSTIC_ROWS: an empty diagnostics '
                         'table is an error, not a result.')
    cols = list(diags[0])
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(diags)
    return len(diags)


_NUMERIC_PREFIXES = ('BASELINE_', 'TRACK1_', 'TRACK1_MEAN_')


def _coerce(r):
    out = {}
    for k, v in r.items():
        if k in ('season', 'week'):
            out[k] = int(v)
        elif (k in ('actual', 'expected_margin', 'multiplier_expected',
                    'baseline_point', 'estimator_season')
                or any(k.startswith(p) for p in _NUMERIC_PREFIXES)):
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                out[k] = v
        else:
            out[k] = v
    return out


def load_scored_rows(path=ROWS):
    """Re-read the persisted scoring table. A re-summary is not a re-run."""
    with gzip.open(path, 'rt', newline='') as fh:
        return [_coerce(r) for r in csv.DictReader(fh)]


def load_diagnostic_rows(path=DIAGNOSTICS):
    with open(path, newline='') as fh:
        rows = []
        for r in csv.DictReader(fh):
            d = dict(r)
            for k, v in list(d.items()):
                if k in ('season', 'week', 'offsetting'):
                    d[k] = int(v)
                elif k.startswith(('actual_', 'pred_', 'crps_', 'err_')):
                    d[k] = float(v) if str(v).strip() != '' else ''
            rows.append(d)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in FC.EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=FC.N_DRAWS)
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--resummarise', action='store_true',
                    help='recompute the summary from the persisted scoring '
                         'table instead of re-running the chain. Changes how '
                         'results are REPORTED, never what they are.')
    a = ap.parse_args(argv)
    if a.resummarise:
        rows = load_scored_rows()
        diags = load_diagnostic_rows()
        prev = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
        res = {'rows': rows, 'diagnostics': diags,
               'half_life_by_season': prev.get('half_life_by_season', {}),
               'fit_log': prev.get('fit_log', [])}
        a.draws = prev.get('n_draws', a.draws)
    else:
        res = FC.run(tuple(int(x) for x in a.seasons.split(',')), a.draws,
                     progress=not a.quiet)
    s = summarise(res['rows'], res['diagnostics'])
    s['half_life_by_season'] = {str(k): v for k, v in
                                res['half_life_by_season'].items()}
    s['fit_log'] = res['fit_log']
    s['n_draws'] = a.draws
    s['decision'] = decide(s)
    RESULTS.write_text(json.dumps(s, indent=1, default=str) + '\n')
    if not a.resummarise:
        write_diagnostics(res['diagnostics'])
        write_rows(res['rows'])
    n = len(res['diagnostics'])
    print(f'\nscored rows      : {len(res["rows"])}')
    print(f'diagnostic rows  : {n}')
    print(f'decision         : {s["decision"]["decision"]}')
    for m, e in s['metrics'].items():
        if not e['is_treated']:
            continue
        d = e['paired_crps_delta_vs_baseline']['TRACK1']
        print(f'  {m:22s} dCRPS {d["delta_pct_of_baseline"]:+7.3f}%  '
              f'ci[{d["block_bootstrap_by_game"]["ci_lo"]:+.4f},'
              f'{d["block_bootstrap_by_game"]["ci_hi"]:+.4f}]  '
              f'r {e["discrimination_pearson_r"]["BASELINE"]:+.4f} -> '
              f'{e["discrimination_pearson_r"]["TRACK1_MEAN"]:+.4f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
