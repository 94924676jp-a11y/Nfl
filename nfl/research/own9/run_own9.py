"""OWN-9: A0 versus A1 on the frozen historical evaluation set.

    INTEL1_PBP_GLOB='.../pbp20*.csv.gz' python3.12 nfl/research/own9/run_own9.py

Chronological: parameters for evaluation season ev come from seasons strictly
before ev. Evaluation 2022-2024; 2020-2021 are burn-in and are never scored,
because a team cannot be shown to have no prior history when the coverage
itself is new.

Refuses to run against a modified OWN-8 pre-registration.
"""
from __future__ import annotations

import collections
import glob
import gzip
import csv
import hashlib
import json
import os
import statistics
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
for _q in (_ROOT, HERE):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import a1_lib as A                                                # noqa: E402

PREDECL = os.path.join(_ROOT, 'nfl', 'research', 'own8',
                       'predeclaration_own8.md')
PREDECL_SHA = '90f6ecc37bcee427177f183be03374c13ec87fe1e14d667a4457c797748789db'
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
    """gsis_id -> position, from the panel. Identity by id only, never a name."""
    pos = {}
    with gzip.open(os.path.join(INPUTS, 'panel_p3.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            p = r.get('gsis_id')
            if p:
                pos.setdefault(p, r.get('position'))
    return pos


def summarise(x):
    x = np.asarray(x, float)
    return {'mean': round(float(x.mean()), 4), 'sd': round(float(x.std()), 4),
            'p05': round(float(np.percentile(x, 5)), 4),
            'p50': round(float(np.percentile(x, 50)), 4),
            'p95': round(float(np.percentile(x, 95)), 4),
            'zero_mass': round(float((x <= 0).mean()), 4),
            'p99': round(float(np.percentile(x, 99)), 4)}


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() == 0 or b.std() == 0:
        return None
    return round(float(np.corrcoef(a, b)[0, 1]), 4)


def main():
    sha = check_predeclaration()
    files = sorted(glob.glob(os.environ.get('INTEL1_PBP_GLOB', '')))
    if not files:
        raise SystemExit('PBP_NOT_LOCATED: set INTEL1_PBP_GLOB.')
    frame = A.attach_prior(A.build_frame(files, positions()))

    # frozen-category closure on the DATA itself, before any model runs
    res = [r['team_carries'] - r['scramble']
           - sum(r[c] for c in A.CATEGORIES) for r in frame]
    data_closure = {'exact': sum(1 for v in res if v == 0), 'n': len(res),
                    'max_abs': max(abs(v) for v in res)}

    per_draw = {arm: collections.Counter() for arm in ('A0', 'A1')}
    dist = {arm: collections.defaultdict(list) for arm in ('A0', 'A1')}
    # co-movement still uses the per-team-game predictive MEAN, which is the
    # right object for a correlation against a per-team-game budget.
    crps_tot = {arm: collections.defaultdict(list) for arm in ('A0', 'A1')}
    co = {arm: collections.defaultdict(list) for arm in ('A0', 'A1')}
    n_eval = 0
    degenerate = 0
    for ev in EVAL_SEASONS:
        par = A.fit(frame, ev)
        par0 = A.fit_a0(frame, ev)
        if par is None or par0 is None:
            continue
        for r in frame:
            if r['season'] != ev or r['rush_play_budget'] <= 0:
                continue
            n_eval += 1
            for arm in ('A0', 'A1'):
                rng = np.random.default_rng(
                    [SEED, r['ord'],
                     int.from_bytes(r['team'].encode()[-4:].ljust(4, b'0'),
                                    'little'),
                     1 if arm == 'A1' else 0])
                if arm == 'A1':
                    d, deg = A.draw_a1(r, par, rng, M)
                    degenerate += deg
                else:
                    d, _ = A.draw_a0(r, par, par0, rng, M)
                # PART G: per-draw closure of the whole carry ledger
                tot = (np.full(M, r['scramble'], np.int64)
                       + sum(np.asarray(d[c], np.int64) for c in A.CATEGORIES))
                bad = int((tot != r['team_carries']).sum())
                per_draw[arm]['draws'] += M
                per_draw[arm]['closure_violations'] += bad
                per_draw[arm]['negative'] += int(sum(
                    int((np.asarray(d[c]) < 0).sum()) for c in A.CATEGORIES))
                # designed QB rush must not exceed the budget it lives in
                over = int((np.asarray(d['designed_qb'], np.int64)
                            > r['rush_play_budget']).sum())
                per_draw[arm]['designed_qb_exceeds_budget'] += over
                for c in A.CATEGORIES:
                    # POOL THE DRAWS, not their means. A distribution of
                    # predictive MEANS has almost no zero mass and a far
                    # narrower spread than the predictive distribution it came
                    # from, so comparing it against realised outcomes would
                    # understate dispersion and overstate calibration. The
                    # first version of this script did exactly that.
                    dist[arm][c].append(np.asarray(d[c], np.int64))
                    crps_tot[arm][c].append(A.crps(d[c], r[c]))
                co[arm]['team_carries'].append(r['team_carries'])
                co[arm]['dropbacks'].append(r['dropbacks'])
                co[arm]['designed_qb'].append(float(np.mean(d['designed_qb'])))
                co[arm]['rb'].append(float(np.mean(d['rb'])))
                co[arm]['kneel'].append(float(np.mean(d['kneel'])))

    obs = {c: [r[c] for r in frame if r['season'] in EVAL_SEASONS
               and r['rush_play_budget'] > 0] for c in A.CATEGORIES}
    out = {'artifact': 'OWN9_A1_VS_A0', 'research_only': True,
           'promoted': False, 'predeclaration_sha256': sha,
           'eval_seasons': list(EVAL_SEASONS), 'burn_in': [2020, 2021],
           'n_team_games_evaluated': n_eval, 'n_draws_each': M,
           'budgets_oracled_identically_for_both_arms': True,
           'frozen_category_closure_in_the_DATA': data_closure,
           'a1_degenerate_draws_given_to_fringe': degenerate,
           'per_draw_invariants': {a: dict(v) for a, v in per_draw.items()},
           'category_distributions': {}, 'crps': {}, 'co_movement': {}}
    for arm in ('A0', 'A1'):
        out['category_distributions'][arm] = {
            c: summarise(np.concatenate(dist[arm][c])) for c in A.CATEGORIES}
        out['crps'][arm] = {c: round(statistics.mean(crps_tot[arm][c]), 5)
                            for c in A.CATEGORIES}
        out['co_movement'][arm] = {
            'designed_qb_vs_team_carries': corr(co[arm]['designed_qb'],
                                                co[arm]['team_carries']),
            'designed_qb_vs_dropbacks': corr(co[arm]['designed_qb'],
                                             co[arm]['dropbacks']),
            'kneel_vs_team_carries': corr(co[arm]['kneel'],
                                          co[arm]['team_carries']),
            'rb_vs_team_carries': corr(co[arm]['rb'], co[arm]['team_carries']),
        }
    out['observed'] = {c: summarise(obs[c]) for c in A.CATEGORIES}
    out['observed_co_movement'] = {
        'designed_qb_vs_team_carries': corr(
            obs['designed_qb'], [r['team_carries'] for r in frame
                                 if r['season'] in EVAL_SEASONS
                                 and r['rush_play_budget'] > 0]),
        'designed_qb_vs_dropbacks': corr(
            obs['designed_qb'], [r['dropbacks'] for r in frame
                                 if r['season'] in EVAL_SEASONS
                                 and r['rush_play_budget'] > 0]),
    }
    dest = os.path.join(HERE, 'own9_results.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    print(json.dumps(out, indent=2, sort_keys=True, default=float))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
