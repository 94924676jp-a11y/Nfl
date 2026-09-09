"""OWN-10: A1 versus A2(tau) on the frozen historical evaluation set.

    INTEL1_PBP_GLOB='.../pbp20*.csv.gz' python3.12 nfl/research/own10/run_own10.py

Every model statistic is computed on ONE DRAW PER TEAM-GAME -- the structure
reality has -- and reported as the distribution over draws. A statistic built
from per-team-game predictive MEANS is not comparable against a realised series
and is never used here; that defect is what OWN-10's pre-registration withdraws.

Refuses to run against a modified OWN-10 pre-registration.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import hashlib
import json
import os
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
_OWN9 = os.path.join(_ROOT, 'nfl', 'research', 'own9')
for _q in (_ROOT, _OWN9, HERE):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import a1_lib as A                                                # noqa: E402
import a2_lib as A2                                               # noqa: E402

PREDECL = os.path.join(HERE, 'predeclaration_own10.md')
PREDECL_SHA = '59ea7fa4363b202899e76f7668d2d3f8e517e2c572e4afd040079dbb14de5954'
INPUTS = os.path.join(_ROOT, 'nfl', 'research', 'inputs')
EVAL_SEASONS = (2022, 2023, 2024)
M = 400
SEED = 20260909


def check_predeclaration():
    got = hashlib.sha256(open(PREDECL, 'rb').read()).hexdigest()
    if got != PREDECL_SHA:
        raise SystemExit(f'PREDECLARATION_MODIFIED: {got} != {PREDECL_SHA}')
    return got


def positions():
    pos = {}
    with gzip.open(os.path.join(INPUTS, 'panel_p3.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            p = r.get('gsis_id')
            if p:
                pos.setdefault(p, r.get('position'))
    return pos


def cc(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def band(vals, obs):
    """A per-draw statistic against its realised counterpart. Never a mean."""
    v = np.asarray([x for x in vals if x is not None], float)
    if v.size == 0 or obs is None:
        return None
    lo, hi = float(np.percentile(v, 5)), float(np.percentile(v, 95))
    return {'observed': round(float(obs), 4),
            'model_per_draw_mean': round(float(v.mean()), 4),
            'model_per_draw_sd': round(float(v.std()), 4),
            'model_p05': round(lo, 4), 'model_p95': round(hi, 4),
            'observed_inside_90pct': bool(lo <= obs <= hi),
            'abs_gap': round(abs(float(v.mean()) - float(obs)), 4),
            'z': (round((float(obs) - float(v.mean())) / float(v.std()), 3)
                  if v.std() > 0 else None)}


def evaluate(rows, par, tau, gates):
    """Draw one arm over a fold. Returns per-category draw matrices."""
    D = {c: np.empty((len(rows), M), np.int64) for c in A.CATEGORIES}
    crps = collections.defaultdict(list)
    for i, r in enumerate(rows):
        rng = np.random.default_rng(
            [SEED, r['ord'],
             int.from_bytes(r['team'].encode()[-4:].ljust(4, b'0'), 'little'), 1])
        d, deg, floor = A2.draw_a2(r, par[r['season']], rng, M, tau)
        gates['degenerate_draws'] += deg
        gates['share_floor_binds'] += floor
        tot = np.full(M, r['scramble'], np.int64)
        for c in A.CATEGORIES:
            D[c][i] = d[c]
            tot += np.asarray(d[c], np.int64)
            gates['negative'] += int((np.asarray(d[c]) < 0).sum())
            crps[c].append(A.crps(d[c], r[c]))
        gates['draws'] += M
        gates['closure_violations'] += int((tot != r['team_carries']).sum())
        for c in A.CATEGORIES:
            gates['category_budget_overruns'] += int(
                (D[c][i] > r['rush_play_budget']).sum())
    return D, {c: round(statistics.mean(v), 5) for c, v in crps.items()}


def main():
    sha = check_predeclaration()
    files = sorted(glob.glob(os.environ.get('INTEL1_PBP_GLOB', '')))
    if not files:
        raise SystemExit('PBP_NOT_LOCATED: set INTEL1_PBP_GLOB.')
    frame = A.attach_prior(A.build_frame(files, positions()))
    par = {ev: A.fit(frame, ev) for ev in EVAL_SEASONS}
    if any(v is None for v in par.values()):
        raise SystemExit('FIT_RETURNED_NOTHING')

    out = {'artifact': 'OWN10_A1_VS_A2', 'research_only': True,
           'promoted': False, 'predeclaration_sha256': sha,
           'tau_grid': list(A2.TAU_GRID), 'tau_zero_is_exactly_A1': True,
           'eval_seasons': list(EVAL_SEASONS), 'burn_in': [2020, 2021],
           'n_draws_each': M, 'seed': SEED,
           'statistic_computed_identically_on_model_and_reality': True,
           'budgets_oracled_identically_for_every_arm': True,
           'production_files_changed': 0, 'consumed_2026_outcomes': False,
           'arms': {}}

    scopes = [('POOLED', EVAL_SEASONS)] + [(str(s), (s,)) for s in EVAL_SEASONS]
    for tau in A2.TAU_GRID:
        key = f'tau={tau:g}' + (' (=A1)' if tau == 0.0 else '')
        arm = {'tau': tau, 'gates': {}, 'folds': {}}
        gates = collections.Counter()
        for name, seasons in scopes:
            rows = [r for r in frame if r['season'] in seasons
                    and r['rush_play_budget'] > 0]
            g = collections.Counter()
            D, crps = evaluate(rows, par, tau, g)
            if name == 'POOLED':
                gates = g
            obs = {c: np.array([r[c] for r in rows], float) for c in A.CATEGORIES}
            tc = np.array([r['team_carries'] for r in rows], float)
            db = np.array([r['dropbacks'] for r in rows], float)
            f = {'n_team_games': len(rows), 'crps': crps,
                 'dependence': {}, 'dispersion': {}, 'cross_category': {},
                 'tail': {}}
            for c in A.CATEGORIES:
                for nm, x in (('team_carries', tc), ('dropbacks', db)):
                    f['dependence'][f'{c}_vs_{nm}'] = band(
                        [cc(D[c][:, j], x) for j in range(M)], cc(obs[c], x))
                f['dispersion'][c] = band(
                    [float(D[c][:, j].std()) for j in range(M)],
                    float(obs[c].std()))
                f['tail'][c] = {
                    'zero_mass': band([float((D[c][:, j] <= 0).mean())
                                       for j in range(M)],
                                      float((obs[c] <= 0).mean())),
                    'p95': band([float(np.percentile(D[c][:, j], 95))
                                 for j in range(M)],
                                float(np.percentile(obs[c], 95))),
                    'p99': band([float(np.percentile(D[c][:, j], 99))
                                 for j in range(M)],
                                float(np.percentile(obs[c], 99))),
                }
            for a, b in (('designed_qb', 'rb'), ('designed_qb', 'kneel'),
                         ('designed_qb', 'wr'), ('rb', 'wr'), ('kneel', 'rb')):
                f['cross_category'][f'{a}_vs_{b}'] = band(
                    [cc(D[a][:, j], D[b][:, j]) for j in range(M)],
                    cc(obs[a], obs[b]))
            arm['folds'][name] = f
        arm['gates'] = dict(gates)
        out['arms'][key] = arm
        print(f'{key}: done')

    dest = os.path.join(HERE, 'own10_results.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    print(f'wrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
