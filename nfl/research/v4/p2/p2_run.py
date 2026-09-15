"""P2 repair 3: rerun the exact 2025 starting-QB cohort, incumbent vs R12.

WHAT IS REUSED RATHER THAN REBUILT. The frame is `h1_frame.build`, the
eligibility rule is `h1_run.eligible`, the scoring of a draw matrix against a
realisation is `h1_run.score` (mean, sd, P10/P50/P90, CRPS, PIT), the
randomized PIT is `h1_run.rpit`, and the CRPS itself is
`p4b_volume.crps_samples` reached through `h1_run`. The simulator is
`qb2_lib.simulate`, called unmodified in both arms -- the arms differ in ONE
keyword, `share_spec`, and in nothing else. Seeds, draw count, rung and row
order are identical, so a difference between them is the specification.

WHAT IS NOT RERUN. The two P4B team layers. This repair does not touch team
volume, and rerunning a layer that cannot move would only invite the reader to
read noise as an effect.

EXPLORATORY. 2025 is development data in this project, and worse for this
study than for H1: the three candidate share specifications were compared on
this same 540-game frame before the one shipped here was chosen. Forward
chaining controls parameter leakage; it does not control specification
leakage. A confirmatory result needs untouched games.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
_REPO = HERE.parents[3]
for _q in (str(HERE), str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
           str(_REPO / 'nfl' / 'research' / 'rc1'),
           str(_REPO / 'nfl' / 'research' / 'p4b'),
           str(_REPO / 'nfl' / 'research' / 'v3' / 'h1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import h1_run as RUN                                              # noqa: E402
import p2_cohort as C                                             # noqa: E402
import qb2_lib as Q                                               # noqa: E402

OUT = HERE / 'P2_RESULTS.json'

# PREDECLARED, and written down before the comparison was run.
SHARE_BIAS_MARGIN = 0.010      # one percentage point of dropback share
PYDS_CRPS_MARGIN = 1.0         # yards; ~2% of the L1 CRPS of 48.64 in qb_v1
ALPHA = 0.01                   # uniformity test level, 10-bin chi-square, 9 df

ARMS = (('incumbent', None),
        ('R12_starter_conditioned', Q.SHARE_SPEC_STARTER_CONDITIONED))


def _vs_matrix(keep, po, spec):
    """V and S for every row, on `simulate`'s own RNG stream and call order.

    `simulate` returns draw matrices but not the two layers it built them
    from, so they are reproduced here exactly as `h1_run.vs_draws` does it and
    the reproduction is CHECKED against `simulate`'s own `db` matrix by the
    caller. A share layer this task cannot prove it observed is not scored.
    """
    V = np.zeros((len(keep), C.M))
    S = np.zeros((len(keep), C.M))
    for i, r in enumerate(keep):
        rng = np.random.default_rng(
            [C.SEED, int(r['ord']),
             int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little')])
        w = Q.rung_weight(r, C.RUNG)
        V[i] = Q._mix(rng, r['h_team_db_series'], po['team_db'], w, C.M, False)
        S[i] = (np.clip(Q._mix(rng, r['h_share'], po['share'], w, C.M, False),
                        0, 1) if spec is None
                else Q.share_draws(r, po, rng, w, False, C.M, spec))
    return V, S


def _layer_rows(keep, draws, actual, discrete, pit_rng):
    """One scored record per game, using h1_run's own scorer."""
    out = []
    for i, r in enumerate(keep):
        y = actual(r)
        s = RUN.score(draws[i], y, pit_rng, discrete)
        s['rpit'] = RUN.rpit(draws[i], y, pit_rng)
        s['game_id'] = r['game_id']
        s['lagged_primary'] = (r['prior_primary'] is True)
        out.append(s)
    return out


def _summarise(rows, name):
    e = np.array([r['error'] for r in rows])
    crps = np.array([r['crps'] for r in rows])
    u = np.array([r['rpit'] for r in rows])
    mid = np.array([r['pit'] for r in rows])
    gid = [r['game_id'] for r in rows]
    c_r, h_r, df = C.pit_chi2(u)
    c_m, h_m, _ = C.pit_chi2(mid)
    bboot, gk = C.block_boot(
        rows, gid, lambda rs: float(np.mean([x['error'] for x in rs])))
    cboot, _ = C.block_boot(
        rows, gid, lambda rs: float(np.mean([x['crps'] for x in rs])))
    return {
        'layer': name, 'n': len(rows), 'n_game_clusters': len(gk),
        'mean_pred': float(np.mean([r['pred_mean'] for r in rows])),
        'mean_actual': float(np.mean([r['actual'] for r in rows])),
        'signed_bias': float(e.mean()),
        'signed_bias_ci95_game_blocked': C.ci95(bboot),
        'mae': float(np.abs(e).mean()),
        'rmse': float(np.sqrt((e ** 2).mean())),
        'mean_crps': float(crps.mean()),
        'mean_crps_ci95_game_blocked': C.ci95(cboot),
        'randomized_pit_chi2': c_r, 'randomized_pit_df': df,
        'randomized_pit_p': C.chi2_sf(c_r, df), 'randomized_pit_hist10': h_r,
        'mid_pit_chi2': c_m, 'mid_pit_hist10': h_m,
        'quantile_coverage_below_p10': float(np.mean([r['below_p10'] for r in rows])),
        'quantile_coverage_below_p50': float(np.mean([r['below_p50'] for r in rows])),
        'quantile_coverage_below_p90': float(np.mean([r['below_p90'] for r in rows])),
        'randomized_coverage_u_lt_010': float(np.mean(u < 0.10)),
        'randomized_coverage_u_lt_050': float(np.mean(u < 0.50)),
        'randomized_coverage_u_lt_090': float(np.mean(u < 0.90)),
    }


def _paired_delta(a_rows, b_rows, field, gid):
    """R12 minus incumbent, per game, block bootstrapped over whole games."""
    d = [{'d': b[field] - a[field], 'game_id': g}
         for a, b, g in zip(a_rows, b_rows, gid)]
    boot, gk = C.block_boot(d, gid, lambda rs: float(np.mean([x['d'] for x in rs])))
    point = float(np.mean([x['d'] for x in d]))
    return {'point': point, 'ci95_game_blocked': C.ci95(boot),
            'n_game_clusters': len(gk),
            'boot_se': float(np.std(boot, ddof=1))}


def run():
    keep, allrows, po, meta = C.cohort()
    gid = [r['game_id'] for r in keep]
    n_lag_false = sum(1 for r in keep if r['prior_primary'] is not True)
    res = {
        'artifact': 'NFL_P2_REPAIR3_RESULTS',
        'spec_version': 'p2-repair3-1',
        'status': ('EXPLORATORY -- 2025 is development data, and the share '
                   'specification shipped here was chosen after comparing '
                   'three candidates on this same frame. Forward chaining '
                   'controls parameter leakage only.'),
        'cohort': {'n_rows': len(keep), 'n_games': len(set(gid)),
                   'eval_season': C.EVAL_SEASON, 'rung': C.RUNG,
                   'seed': C.SEED, 'm': C.M, 'pit_seed': C.PIT_SEED,
                   'block_bootstrap': {'unit': 'whole game',
                                       'resamples': C.N_BOOT,
                                       'seed': C.BOOT_SEED},
                   'qb_frame_sha256': meta['frame']['qb_frame_sha256'],
                   'rows_whose_lagged_role_is_not_primary': n_lag_false},
        'predeclared': {'share_bias_equivalence_margin': SHARE_BIAS_MARGIN,
                        'pyds_crps_noninferiority_margin': PYDS_CRPS_MARGIN,
                        'uniformity_alpha': ALPHA},
        'arms': {}, 'deltas': {}, 'splits': {},
    }
    store = {}
    for name, spec in ARMS:
        pit_rng = np.random.default_rng(C.PIT_SEED)
        V, S = _vs_matrix(keep, po, spec)
        D = Q.simulate(keep, C.EVAL_SEASON, allrows, seed=C.SEED, m=C.M,
                       rung=C.RUNG,
                       share_spec=(spec or Q.SHARE_SPEC_UNCONDITIONAL))
        mism = int((np.maximum(np.rint(V * S), 0).astype(int)
                    != D['db'].astype(int)).any(axis=1).sum())
        if mism:
            raise SystemExit(
                f'P2_VS_REPRODUCTION_FAILED: arm {name}, {mism} of '
                f'{len(keep)} rows could not be reproduced from simulate\'s '
                f'own RNG stream. Refusing to score a share layer that cannot '
                f'be shown to be the one the simulator used.')
        res.setdefault('vs_reproduction_exact', {})[name] = True
        share_rows = _layer_rows(
            keep, S, lambda r: r['db'] / r['team_db'], False, pit_rng)
        db_rows = _layer_rows(keep, D['db'], lambda r: r['db'], True, pit_rng)
        py_rows = _layer_rows(keep, D['pyds'], lambda r: r['pyds'], False,
                              pit_rng)
        att_rows = _layer_rows(keep, D['att'], lambda r: r['att'], True,
                               pit_rng)
        store[name] = {'share': share_rows, 'qb_dropbacks': db_rows,
                       'qb_passing_yards': py_rows, 'qb_attempts': att_rows}
        res['arms'][name] = {
            k: _summarise(v, k) for k, v in store[name].items()}
        b = res['arms'][name]['share']['signed_bias']
        bb, _ = C.block_boot(share_rows, gid,
                             lambda rs: float(np.mean([x['error'] for x in rs])))
        res['arms'][name]['share']['bias_tost'] = C.tost(
            b, bb, SHARE_BIAS_MARGIN)

    a, b = ARMS[0][0], ARMS[1][0]
    for layer in ('share', 'qb_dropbacks', 'qb_attempts', 'qb_passing_yards'):
        res['deltas'][layer] = {
            'mean_crps_R12_minus_incumbent': _paired_delta(
                store[a][layer], store[b][layer], 'crps', gid),
            'signed_bias_R12_minus_incumbent': _paired_delta(
                store[a][layer], store[b][layer], 'error', gid),
        }
    d = res['deltas']['qb_passing_yards']['mean_crps_R12_minus_incumbent']
    res['deltas']['qb_passing_yards']['noninferiority'] = {
        'margin': PYDS_CRPS_MARGIN,
        'upper_95_game_blocked': d['ci95_game_blocked'][1],
        'verdict': ('NOT_WORSE_WITHIN_MARGIN'
                    if d['ci95_game_blocked'][1] < PYDS_CRPS_MARGIN
                    else 'NOT_SHOWN_NOT_WORSE'),
        'point_favours': ('R12' if d['point'] < 0 else 'incumbent'),
    }

    # THE SPLIT THAT MATTERS, AND IT IS NOT A CUT CHOSEN AFTER THE FACT: the
    # repair can only help where the lagged role is the role he played.
    for nm, want in (('lagged_role_primary', True),
                     ('lagged_role_not_primary', False)):
        res['splits'][nm] = {}
        for arm in (a, b):
            for layer in ('share', 'qb_passing_yards'):
                rs = [r for r in store[arm][layer]
                      if r['lagged_primary'] is want]
                if rs:
                    res['splits'][nm][f'{arm}.{layer}'] = {
                        'n': len(rs),
                        'signed_bias': float(np.mean([r['error'] for r in rs])),
                        'mean_crps': float(np.mean([r['crps'] for r in rs])),
                    }
    OUT.write_text(json.dumps(res, indent=1) + '\n')
    return res


if __name__ == '__main__':
    r = run()
    print(json.dumps({'cohort': r['cohort'], 'predeclared': r['predeclared']},
                     indent=1))
    for arm in r['arms']:
        for lay in ('share', 'qb_dropbacks', 'qb_passing_yards'):
            s = r['arms'][arm][lay]
            print(f"{arm:26s} {lay:18s} bias {s['signed_bias']:+9.4f} "
                  f"{s['signed_bias_ci95_game_blocked']} CRPS "
                  f"{s['mean_crps']:.5f} rPIT chi2 {s['randomized_pit_chi2']:7.2f} "
                  f"p {s['randomized_pit_p']:.3e}")
    print(json.dumps(r['deltas'], indent=1))
    print(json.dumps(r['splits'], indent=1))
