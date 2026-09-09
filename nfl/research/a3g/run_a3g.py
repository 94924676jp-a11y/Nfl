"""A3G runner. Everything scored here was fixed in predeclaration_a3g.md.

The pre-registration's sha256 is pinned below and re-verified at start. A
pre-registration edited after seeing a result is not the pre-registration the
result was produced under, so the runner refuses rather than warns.

    python3.12 nfl/research/a3g/run_a3g.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
for _q in (_ROOT, _HERE):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import a3g_lib as A                                              # noqa: E402
from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.production import team_volume_v1 as TV                  # noqa: E402

PREREG = 'd3620883e52fd6d2da9b56403a219210e82e52d5a65bf73cbd23f1d13d4e78ea'
PREREG_FILE = os.path.join(_HERE, 'predeclaration_a3g.md')
RESULTS = os.path.join(_HERE, 'a3g_results.json')

SEASON, WEEK = 2026, 1
M = 4000                       # draws per team
REPS = 4000                    # historical subset resamples
SEED = 20260909
CANDIDATES = ('off_snaps', 'zmean', 'pc1')   # simplest first, per prereg
INCUMBENT = 'none'

# The six clauses of the decision rule, §8 of the pre-registration.
D_IMPROVEMENT = 0.05
R_TOLERANCE = 0.15
OOR_LO, OOR_HI = 106.0, 173.0          # the 2020-2025 observed range
MARGINAL_TOLERANCE = 0.01


def verify_prereg():
    if not os.path.exists(PREREG_FILE):
        raise SystemExit(f'A3G_PREREG_MISSING: {PREREG_FILE}')
    got = hashlib.sha256(open(PREREG_FILE, 'rb').read()).hexdigest()
    if got != PREREG:
        raise SystemExit(
            f'A3G_PREREG_HASH_MOVED: pinned {PREREG} but the file on disk '
            f'hashes to {got}. Refusing to produce a result under a '
            f'pre-registration that is not the one this runner declares.')
    return got


def uniformity_proof(n=37, k=11):
    """floor(u*n) over an exactly-uniform grid hits every pool slot k times.

    This is the marginal-preservation claim of §3 checked as arithmetic rather
    than as a sample statistic: the index map itself is exactly uniform, so no
    amount of coupling can move a marginal.
    """
    u = (np.arange(n * k) + 0.5) / (n * k)
    keys = [('T', i) for i in range(n)]
    score = {kk: float(i * 0.5) for i, kk in enumerate(keys)}
    ix = TV.coupled_index(u, keys, score)
    counts = np.bincount(ix, minlength=n)
    return {'pool': n, 'multiple': k, 'every_slot_exactly_k_times':
            bool((counts == k).all()), 'min': int(counts.min()),
            'max': int(counts.max())}


def measure(arm, drawn, pairs, hist, rng):
    r = {'arm': arm}
    corr = {}
    for mm in A.METRICS:
        Am, Bm = A.sides(drawn, pairs, mm)
        pr = A.per_draw(Am, Bm, lambda a, b: A._sym_corr(a, b))
        sp = A.per_draw(Am, Bm, lambda a, b: A._sym_corr(a, b, rank=True))
        corr[mm] = {'pearson_per_draw': A.band(pr),
                    'spearman_per_draw': A.band(sp)}
    r['within_game_corr'] = corr

    Am, Bm = A.sides(drawn, pairs, A.TOTAL_METRIC)
    tot = Am + Bm                                    # (n_games, m)
    r['total_game_plays'] = {
        'sd_per_draw': A.band(np.array([tot[:, d].std(ddof=1)
                                        for d in range(tot.shape[1])])),
        'mean_per_draw': A.band(np.array([tot[:, d].mean()
                                          for d in range(tot.shape[1])])),
        'pooled_sd': float(tot.std(ddof=1)),
        'pooled_min': float(tot.min()), 'pooled_max': float(tot.max()),
    }
    oor = (tot < OOR_LO) | (tot > OOR_HI)
    boot = [float(oor[rng.integers(0, oor.shape[0], oor.shape[0])].mean())
            for _ in range(1000)]
    r['outside_historical_range'] = {
        'range': [OOR_LO, OOR_HI],
        'fraction': float(oor.mean()),
        'game_clustered_p05': float(np.percentile(boot, 5)),
        'game_clustered_p95': float(np.percentile(boot, 95)),
        'n_game_draws': int(oor.size)}
    r['zero_floor_draws'] = A.zero_floor_count(drawn)
    return r


def main():
    t0 = time.time()
    sha = verify_prereg()
    sl = A.slate(SEASON, WEEK)
    if sl.state is not State.PASS:
        print(sl); return 1
    pairs = sl.value
    hg = A.historical_games()
    if hg.state is not State.PASS:
        print(hg); return 1
    paired = hg.value
    k = len(pairs)

    hist = {'n_paired_games': len(paired),
            'n_unpaired_dropped': hg.evidence['n_unpaired_dropped'],
            'seasons': sorted({g[0]['season'] for g in paired}),
            'per_metric': {}, 'subset_games': k}
    for mm in A.METRICS:
        a = np.array([g[0][mm] for g in paired], float)
        b = np.array([g[1][mm] for g in paired], float)
        hist['per_metric'][mm] = {
            'full_sample_pearson': A._sym_corr(a, b),
            'full_sample_spearman': A._sym_corr(a, b, rank=True),
            f'{k}_game_subset_band': A.hist_subset_band(paired, mm, k, REPS,
                                                        SEED)}
    tot = np.array([g[0][A.TOTAL_METRIC] + g[1][A.TOTAL_METRIC]
                    for g in paired], float)
    hist['total_game_plays'] = {
        'full_sample_sd': float(tot.std(ddof=1)),
        'full_sample_mean': float(tot.mean()),
        'observed_min': float(tot.min()), 'observed_max': float(tot.max()),
        f'{k}_game_subset_sd_band': A.hist_total_band(paired, k, REPS, SEED)}

    OUT = {'artifact': 'A3G_RESULTS',
           'prereg_sha256': sha,
           'label': 'EXPLORATORY -- 2020-2025 are development data and 2026 '
                    'week 1 has no outcomes. Nothing is promoted and no '
                    'production default changes.',
           'owner_ruling': 'B10',
           'spec_version': TV.SPEC_VERSION,
           'slate': {'season': SEASON, 'week': WEEK, 'n_games': k,
                     'pairs': [list(p) for p in pairs],
                     'schedule_snapshot': sl.evidence['snapshot']},
           'draws_per_team': M, 'seed': SEED,
           'call_shape': 'per_game (the shape production uses)',
           'historical': hist,
           'index_map_uniformity_proof': uniformity_proof(),
           'arms': {}, 'marginals': {}, 'decision': {}}

    rng = np.random.default_rng(SEED)
    TV.cache_clear()
    drawn, marg = {}, {}
    for arm in (INCUMBENT,) + CANDIDATES:
        t = time.time()
        d = A.draw_slate(SEASON, WEEK, pairs, arm, M, SEED, per_game=True)
        if d.state is not State.PASS:
            print(f'{arm}: {d}'); return 1
        drawn[arm] = d.value
        marg[arm] = A.marginal_summary(d.value)
        OUT['arms'][arm] = measure(arm, d.value, pairs, hist, rng)
        ev = d.evidence['first_call_evidence']
        sel = ev['selections'][A.TOTAL_METRIC]
        OUT['arms'][arm]['draw_evidence'] = {
            'game_coupling': ev.get('game_coupling'),
            'draw_mode': ev.get('draw_mode'),
            'rho_gaussian': sel.get('rho_gaussian'),
            'rho_spearman': sel.get('rho_spearman'),
            'coupling_paired_games': sel.get('coupling_paired_games'),
            'joint_pool_team_games': sel.get('joint_pool_team_games'),
            'rows_game_coupled': sel.get('rows_game_coupled'),
            'rows_not_game_coupled': sel.get('rows_not_game_coupled'),
            'rows_on_global_fallback': sel.get('rows_on_global_fallback'),
            'coupling_score_evidence': sel.get('coupling_score_evidence')}
        print(f'  {arm}: {time.time() - t:.1f}s', flush=True)

    # marginal evidence, every candidate against the incumbent
    for arm in CANDIDATES:
        OUT['marginals'][f'{arm}_vs_{INCUMBENT}'] = A.marginal_max_move(
            marg[INCUMBENT], marg[arm])
    OUT['marginals']['per_team_metric_summary'] = {
        arm: marg[arm] for arm in (INCUMBENT,) + CANDIDATES}

    # ------------------------------------------------------ decision rule
    def D_of(arm):
        return float(np.mean([
            abs(OUT['arms'][arm]['within_game_corr'][mm]['pearson_per_draw']
                ['mean'] - hist['per_metric'][mm]['full_sample_pearson'])
            for mm in A.METRICS]))

    hsd = hist['total_game_plays']['full_sample_sd']
    d0 = D_of(INCUMBENT)
    oor0 = OUT['arms'][INCUMBENT]['outside_historical_range']['fraction']
    z0 = OUT['arms'][INCUMBENT]['zero_floor_draws']
    OUT['decision']['incumbent'] = {
        'arm': INCUMBENT, 'D': d0,
        'R': OUT['arms'][INCUMBENT]['total_game_plays']['sd_per_draw']['mean']
             / hsd,
        'outside_range_fraction': oor0, 'zero_floor_draws': z0}
    clears = []
    for arm in CANDIDATES:
        a = OUT['arms'][arm]
        D = D_of(arm)
        R = a['total_game_plays']['sd_per_draw']['mean'] / hsd
        oor = a['outside_historical_range']['fraction']
        signs = {mm: (np.sign(a['within_game_corr'][mm]['pearson_per_draw']
                              ['mean'])
                      == np.sign(hist['per_metric'][mm]['full_sample_pearson']))
                 for mm in A.METRICS}
        mv = OUT['marginals'][f'{arm}_vs_{INCUMBENT}']['max_abs_relative_move']
        cl = {
            '1_D_improves_by_0.05': bool(d0 - D >= D_IMPROVEMENT),
            '2_R_within_0.15': bool(abs(R - 1.0) <= R_TOLERANCE),
            '3_outside_range_at_most_half': bool(oor <= oor0 / 2.0),
            '4_every_sign_matches_history': bool(all(signs.values())),
            '5_marginals_move_under_1pct': bool(mv <= MARGINAL_TOLERANCE),
            '6_no_new_zero_floor_draws': bool(a['zero_floor_draws'] <= z0)}
        OUT['decision'][arm] = {
            'D': D, 'D_improvement_vs_incumbent': d0 - D, 'R': R,
            'outside_range_fraction': oor,
            'sign_matches_history': {m: bool(v) for m, v in signs.items()},
            'marginal_max_abs_relative_move': mv,
            'zero_floor_draws': a['zero_floor_draws'],
            'clauses': cl, 'clears_all_clauses': all(cl.values())}
        if all(cl.values()):
            clears.append(arm)
    chosen, why = INCUMBENT, ('no candidate cleared every clause of the '
                              'decision rule, so the incumbent is retained')
    if clears:
        chosen = clears[0]
        why = (f'{chosen} is the simplest candidate that clears every clause '
               f'(§8 simplest-wins ordering)')
        for arm in clears[1:]:
            if (OUT['decision'][chosen]['D'] - OUT['decision'][arm]['D']
                    >= D_IMPROVEMENT):
                chosen, why = arm, (
                    f'{arm} clears every clause and improves D by at least '
                    f'{D_IMPROVEMENT} over {chosen}')
    OUT['decision']['candidates_clearing_all_clauses'] = clears
    OUT['decision']['recommended_mode'] = chosen
    OUT['decision']['rationale'] = why
    OUT['decision']['production_default_unchanged'] = (
        TV.GAME_COUPLING_DEFAULT == 'none'
        and TV.JOINT_RESIDUALS_DEFAULT is False)
    OUT['runtime_seconds'] = round(time.time() - t0, 1)
    with open(RESULTS, 'w') as fh:
        json.dump(OUT, fh, indent=1, sort_keys=False)
    print(f'\nwrote {RESULTS}  ({OUT["runtime_seconds"]}s)')
    print(f'recommended: {chosen} -- {why}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
