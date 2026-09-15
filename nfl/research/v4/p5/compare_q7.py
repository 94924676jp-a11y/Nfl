"""Before/after on every published Q7 conclusion, read out of the artifacts.

    python3.12 nfl/research/v4/p5/compare_q7.py

Three files are read and never written: the PUBLISHED Q7 result, this repair's
re-run on the SUPERSEDED panel, and its re-run on the CORRECTED panel.

THE PUBLISHED-VERSUS-OLD COLUMN IS THE HARNESS CHECK. If the re-run on the
superseded panel does not reproduce the published number, the after column is
measuring this driver and not the repair, and every row is suspect. It is
printed first for that reason.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[4]
HERE = _REPO / 'nfl' / 'research' / 'v4' / 'p5'
PUB = _REPO / 'nfl' / 'research' / 'q7' / 'Q7_FORWARD_CHAIN_RESULTS.json'
OLD = HERE / 'Q7_RESULTS_OLD_PANEL.json'
NEW = HERE / 'Q7_RESULTS_NEW_PANEL.json'


def g(d, *path, default=None):
    for p in path:
        if d is None:
            return default
        d = d.get(p) if isinstance(d, dict) else None
    return default if d is None else d


def fmt(v):
    if isinstance(v, float):
        return f'{v:.5g}'
    return str(v)


def row(label, a, b, c, out):
    same_pub = (a == b)
    moved = (b != c)
    out.append({'quantity': label, 'published': a, 'rerun_old_panel': b,
                'rerun_corrected_panel': c,
                'harness_reproduces_published': same_pub, 'moved': moved})


def main():
    for p in (PUB, OLD, NEW):
        if not p.exists():
            raise SystemExit(f'P5_MISSING_INPUT: {p}')
    pub, old, new = (json.loads(p.read_text()) for p in (PUB, OLD, NEW))
    out = []

    row('n_scored_rows', pub['n_scored_rows'], old['n_scored_rows'],
        new['n_scored_rows'], out)
    row('decision (headline arm)', pub['decision']['decision'],
        old['decision']['decision'], new['decision']['decision'], out)
    for arm in ('Q7_WIDTH', 'Q7_SHRINK', 'Q7_BOTH'):
        row(f'verdict {arm}', g(pub, 'decision_by_arm', arm, 'decision'),
            g(old, 'decision_by_arm', arm, 'decision'),
            g(new, 'decision_by_arm', arm, 'decision'), out)

    # Findings 1, 2, 5, 6 -- per estimand, per arm, per regime
    for est in ('cmp|att', 'ptd|cmp', 'pyds|cmp', 'pyds|att',
                'rec|targets', 'rec_yds|rec', 'rec_yds|targets'):
        for arm in ('BASELINE', 'Q7_WIDTH', 'Q7_SHRINK', 'Q7_BOTH'):
            base = ('estimands', est, 'by_arm', arm)
            if g(pub, *base) is None:
                continue
            for f in ('n', 'bias', 'rmse', 'mean_crps',
                      'rmse_over_predictive_sd'):
                row(f'{est} [{arm}] {f}', g(pub, *base, f), g(old, *base, f),
                    g(new, *base, f), out)
            row(f'{est} [{arm}] calibration slope',
                g(pub, *base, 'mean_calibration', 'slope'),
                g(old, *base, 'mean_calibration', 'slope'),
                g(new, *base, 'mean_calibration', 'slope'), out)
            row(f'{est} [{arm}] PIT chi2', g(pub, *base, 'pit', 'chi2'),
                g(old, *base, 'pit', 'chi2'), g(new, *base, 'pit', 'chi2'), out)
            for L in ('50', '90'):
                row(f'{est} [{arm}] coverage {L}',
                    g(pub, *base, 'coverage', L), g(old, *base, 'coverage', L),
                    g(new, *base, 'coverage', L), out)
            regs = sorted(set(g(pub, *base, 'by_opportunity_regime',
                                default={})))
            for rg in regs:
                for f in ('n', 'bias', 'mean_crps',
                          'rmse_over_predictive_sd'):
                    row(f'{est} [{arm}] @{rg} {f}',
                        g(pub, *base, 'by_opportunity_regime', rg, f),
                        g(old, *base, 'by_opportunity_regime', rg, f),
                        g(new, *base, 'by_opportunity_regime', rg, f), out)
                row(f'{est} [{arm}] @{rg} coverage 90',
                    g(pub, *base, 'by_opportunity_regime', rg, 'coverage', '90'),
                    g(old, *base, 'by_opportunity_regime', rg, 'coverage', '90'),
                    g(new, *base, 'by_opportunity_regime', rg, 'coverage', '90'),
                    out)
            for dp in sorted(set(g(pub, *base, 'by_sample_depth', default={}))):
                for f in ('n', 'bias', 'rmse_over_predictive_sd'):
                    row(f'{est} [{arm}] depth {dp} {f}',
                        g(pub, *base, 'by_sample_depth', dp, f),
                        g(old, *base, 'by_sample_depth', dp, f),
                        g(new, *base, 'by_sample_depth', dp, f), out)
            # Finding 3 -- the paired delta and its significance
            d = ('paired_crps_delta_vs_baseline',)
            if g(pub, *base, *d) is not None:
                for f in ('delta_mean', 'delta_pct'):
                    row(f'{est} [{arm}] {f}', g(pub, *base, *d, f),
                        g(old, *base, *d, f), g(new, *base, *d, f), out)
                row(f'{est} [{arm}] delta excludes zero',
                    g(pub, *base, *d, 'block_bootstrap_by_game',
                      'excludes_zero'),
                    g(old, *base, *d, 'block_bootstrap_by_game',
                      'excludes_zero'),
                    g(new, *base, *d, 'block_bootstrap_by_game',
                      'excludes_zero'), out)
                for rg in sorted(set(g(pub, *base, 'by_regime_delta_pct',
                                       default={}))):
                    row(f'{est} [{arm}] @{rg} delta_pct',
                        g(pub, *base, 'by_regime_delta_pct', rg, 'delta_pct'),
                        g(old, *base, 'by_regime_delta_pct', rg, 'delta_pct'),
                        g(new, *base, 'by_regime_delta_pct', rg, 'delta_pct'),
                        out)
                    row(f'{est} [{arm}] @{rg} delta excludes zero',
                        g(pub, *base, 'by_regime_delta_pct', rg,
                          'block_bootstrap_by_game', 'excludes_zero'),
                        g(old, *base, 'by_regime_delta_pct', rg,
                          'block_bootstrap_by_game', 'excludes_zero'),
                        g(new, *base, 'by_regime_delta_pct', rg,
                          'block_bootstrap_by_game', 'excludes_zero'), out)

    # Finding 4 -- the estimated shrinkage constants
    for season in sorted(set(g(pub, 'shrinkage', 'by_season', default={}))):
        for q in ('completion_rate', 'yards_per_completion'):
            for f in ('k', 'n_players'):
                row(f'shrinkage {season} {q} {f}',
                    g(pub, 'shrinkage', 'by_season', season, q, f),
                    g(old, 'shrinkage', 'by_season', season, q, f),
                    g(new, 'shrinkage', 'by_season', season, q, f), out)

    # The required decomposition
    for f in ('n', 'opportunity_error_mean', 'efficiency_error_mean',
              'combined_error_mean', 'mean_abs_opportunity_error',
              'mean_abs_efficiency_error', 'mean_abs_combined_error',
              'offsetting_rate'):
        row(f'COMPOSED {f}', g(pub, 'decomposition', 'COMPOSED', f),
            g(old, 'decomposition', 'COMPOSED', f),
            g(new, 'decomposition', 'COMPOSED', f), out)
    for f in ('SAME_SIGN', 'OFFSETTING', 'ZERO_COMPONENT'):
        row(f'COMPOSED {f}',
            g(pub, 'decomposition', 'COMPOSED', 'same_sign_or_offsetting', f),
            g(old, 'decomposition', 'COMPOSED', 'same_sign_or_offsetting', f),
            g(new, 'decomposition', 'COMPOSED', 'same_sign_or_offsetting', f),
            out)
    for f in ('n', 'efficiency_error_mean', 'combined_error_mean'):
        row(f'ISOLATED {f}', g(pub, 'decomposition', 'ISOLATED', f),
            g(old, 'decomposition', 'ISOLATED', f),
            g(new, 'decomposition', 'ISOLATED', f), out)

    bad_harness = [r for r in out if not r['harness_reproduces_published']]
    moved = [r for r in out if r['moved']]
    print(f'quantities compared            : {len(out)}')
    print(f'harness reproduces published   : '
          f'{len(out) - len(bad_harness)}/{len(out)}')
    print(f'MOVED on the corrected panel   : {len(moved)}')
    if bad_harness:
        print('\nHARNESS DISAGREES WITH THE PUBLISHED ARTIFACT '
              '(the after column is not trustworthy for these):')
        for r in bad_harness[:40]:
            print(f"  {r['quantity']:52s} pub {fmt(r['published'])}  "
                  f"rerun {fmt(r['rerun_old_panel'])}")
    print('\nMOVED:')
    for r in moved:
        print(f"  {r['quantity']:52s} {fmt(r['rerun_old_panel'])}"
              f"  ->  {fmt(r['rerun_corrected_panel'])}")
    (HERE / 'P5_Q7_BEFORE_AFTER.json').write_text(
        json.dumps({'artifact': 'NFL_P5_Q7_BEFORE_AFTER',
                    'n_compared': len(out),
                    'n_harness_disagreements': len(bad_harness),
                    'n_moved': len(moved),
                    'rows': out}, indent=1) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
