"""A1 production verification run. Scratch harness, not a test and not a fit.

    NFL_A1_PBP_GLOB='.../pbp20*.csv.gz' \
    python3.12 nfl/research/a1prod/run_a1prod_verification.py

What it does, and nothing else:

1.  checks the OWN-8 pre-registration hash;
2.  resolves play-by-play and positions (positions through the PRODUCTION
    derived-artifact cache, never a research path);
3.  builds the frame and asserts the categorisation closes in the DATA;
4.  freezes 2026 week 1 parameters into production's own cache;
5.  REPLICATES OWN-9's oracle condition through the PRODUCTION allocator --
    realised team_carries and scrambles handed in as the budgets, identical to
    the research arm -- and counts every hard requirement;
6.  reports dependence ONE DRAW PER TEAM-GAME as a distribution over draws,
    and reports the mean-based statistic only under a name saying it is not
    comparable.

No parameter is chosen here. Nothing is promoted. PATH_C_STATE untouched.
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.production.nonqb import rushing_a1 as R                 # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
EVAL = (2022, 2023, 2024)
M = 400
SEED = 20260909
FORECAST = (2026, 1)


def main() -> int:
    out: dict = {'artifact': 'A1PROD_VERIFICATION', 'promoted': False,
                 'path_c_state_touched': False, 'm': M, 'seed': SEED,
                 'eval_seasons': list(EVAL), 'burn_in': [2020, 2021]}
    pre = R.predeclaration()
    print(pre)
    out['predeclaration'] = pre.as_dict()
    if pre.state is not State.PASS:
        return 2
    out['estimator_identity'] = R.estimator_identity()
    out['seed_contract'] = R.seed_contract()
    out['registry_debt'] = R.registry_debt().as_dict()

    src = R.pbp_sources()
    print(src)
    if src.state is not State.PASS:
        out['blocked'] = src.as_dict()
        (HERE / 'a1prod_verification.json').write_text(
            json.dumps(out, indent=1, sort_keys=True, default=float))
        return 3
    pos = R.positions()
    print(pos)
    if pos.state is not State.PASS:
        out['blocked'] = pos.as_dict()
        (HERE / 'a1prod_verification.json').write_text(
            json.dumps(out, indent=1, sort_keys=True, default=float))
        return 3
    out['positions'] = {k: v for k, v in pos.evidence.items()}

    fr = R.build_frame(src.value, pos.value)
    print(fr)
    if fr.state is not State.PASS:
        out['blocked'] = fr.as_dict()
        return 4
    frame = fr.value
    out['frame'] = {k: v for k, v in fr.evidence.items()}

    prov = {'pbp_files': [os.path.basename(f) for f in src.value],
            'pbp_sha256': {os.path.basename(f): R._sha_file(f)
                           for f in src.value},
            'positions_source': pos.evidence.get('source'),
            'positions_sha256': pos.evidence.get('source_sha256'),
            'n_positions': len(pos.value),
            'built_by': 'nfl/research/a1prod/run_a1prod_verification.py'}
    fz = R.freeze(*FORECAST, frame=frame, provenance=prov)
    print(fz)
    out['forecast_freeze'] = fz.as_dict()

    # ---- OWN-9's oracle replication, through the production allocator -----
    hard = collections.Counter()
    floor = degen = 0
    n_tg = 0
    # FLAT, IN ITERATION ORDER. A first version keyed these by team and
    # then stacked team-major while the realised series stayed
    # week-major, which misaligned every row and drove the pooled
    # correlations to zero. The per-fold figures, which were always built
    # flat, exposed it.
    draws = {c: [] for c in R.CATEGORIES}
    real = collections.defaultdict(list)
    obs = {c: [] for c in R.CATEGORIES}
    per_fold: dict = {}
    for ev in EVAL:
        par = R.fit_frozen(ev, 0, frame=frame, provenance=prov)
        if par.state is not State.PASS:
            print(par)
            return 5
        p = par.value
        rows = [r for r in frame if r['season'] == ev
                and r['rush_play_budget'] > 0]
        byweek = collections.defaultdict(list)
        for r in rows:
            byweek[r['week']].append(r)
        fold = collections.Counter()
        fold_draws = {c: [] for c in R.CATEGORIES}
        fold_real = collections.defaultdict(list)
        for wk in sorted(byweek):
            wr = byweek[wk]
            teams = [r['team'] for r in wr]
            pw = dict(p)
            pw['history'] = {
                r['team']: {'n': int(r['h_n']),
                            **{c: list(r[f'h_{c}']) for c in R.CATEGORIES}}
                for r in wr}
            tc = {r['team']: np.full(M, r['team_carries'], np.int64)
                  for r in wr}
            scr = {r['team']: np.full(M, r['scramble'], np.int64) for r in wr}
            o = R.allocate(ev, wk, teams, tc, scr, m=M, seed=SEED, params=pw)
            if o.state is not State.PASS:
                print('ALLOCATION REFUSED', o)
                out['refusal'] = o.as_dict()
                (HERE / 'a1prod_verification.json').write_text(
                    json.dumps(out, indent=1, sort_keys=True, default=float))
                return 6
            for k in ('draws', 'closure_violations', 'negative_allocations',
                      'category_budget_overruns', 'ledger_violations',
                      'carries_with_no_owner', 'carries_with_two_owners'):
                hard[k] += int(o.evidence[k])
                fold[k] += int(o.evidence[k])
            floor += int(o.evidence['share_floor_binds'])
            degen += int(o.evidence[
                'degenerate_draws_named_and_given_to_fringe'])
            for r in wr:
                n_tg += 1
                t = r['team']
                for c in R.CATEGORIES:
                    draws[c].append(o.value['carries'][(t, c)])
                    fold_draws[c].append(o.value['carries'][(t, c)])
                    obs[c].append(r[c])
                for nm in ('team_carries', 'dropbacks'):
                    real[nm].append(r[nm])
                    fold_real[nm].append(r[nm])
                # the ledger identity, re-checked outside the allocator
                tot = sum(o.value['carries'][(t, c)] for c in R.CATEGORIES)
                if not np.array_equal(tot + o.value['scrambles'][t],
                                      o.value['team_carries'][t]):
                    raise SystemExit('LEDGER_BROKEN')
                if not np.array_equal(o.value['scrambles'][t],
                                      scr[t]):
                    raise SystemExit('SCRAMBLES_MUTATED')
                if not np.array_equal(o.value['qb_rush_opportunity'][t],
                                      scr[t]
                                      + o.value['carries'][(t, 'designed_qb')]):
                    raise SystemExit('QB_RUSH_OPPORTUNITY_WRONG')
        pf = {'n_team_games': len(rows), 'hard': dict(fold)}
        for c in ('designed_qb', 'kneel', 'rb'):
            X = np.vstack(fold_draws[c])
            for nm in ('team_carries', 'dropbacks'):
                d = R.per_draw_dependence(X, np.asarray(fold_real[nm]))
                pf[f'{c}_vs_{nm}'] = (d.value if d.state is State.PASS
                                      else d.as_dict())
        per_fold[ev] = pf

    out['hard_requirements'] = dict(hard)
    out['share_floor_binds'] = floor
    out['degenerate_draws_named_and_given_to_fringe'] = degen
    out['n_team_games'] = n_tg
    out['per_fold'] = per_fold

    # pooled: pooled DRAWS against realised, never predictive means
    pooled = {}
    for c in R.CATEGORIES:
        allc = np.concatenate(draws[c])
        o_ = np.asarray(obs[c], float)
        pooled[c] = {
            'model_mean': round(float(allc.mean()), 4),
            'model_sd': round(float(allc.std()), 4),
            'model_p95': float(np.percentile(allc, 95)),
            'model_zero_mass': round(float((allc <= 0).mean()), 4),
            'observed_mean': round(float(o_.mean()), 4),
            'observed_sd': round(float(o_.std()), 4),
            'observed_p95': float(np.percentile(o_, 95)),
            'observed_zero_mass': round(float((o_ <= 0).mean()), 4)}
    out['pooled_category_distributions'] = pooled

    dep = {}
    for c in ('designed_qb', 'kneel', 'rb'):
        X = np.vstack(draws[c])
        assert X.shape[0] == len(real['team_carries']), 'ROW_ORDER_MISALIGNED'
        for nm in ('team_carries', 'dropbacks'):
            y = np.asarray(real[nm], float)
            d = R.per_draw_dependence(X, y)
            dep[f'{c}_vs_{nm}'] = (d.value if d.state is State.PASS
                                   else d.as_dict())
            if c == 'designed_qb' and nm == 'team_carries':
                mb = R.mean_based_dependence(X, y)
                dep['designed_qb_vs_team_carries_MEAN_BASED_NOT_COMPARABLE'] \
                    = mb.evidence['value_not_comparable']
        oc = np.asarray(obs[c], float)
        for nm in ('team_carries', 'dropbacks'):
            y = np.asarray(real[nm], float)
            dep[f'OBSERVED_{c}_vs_{nm}'] = round(
                float(np.corrcoef(oc, y)[0, 1]), 4)
    out['per_draw_dependence'] = dep

    dest = HERE / 'a1prod_verification.json'
    dest.write_text(json.dumps(out, indent=1, sort_keys=True, default=float))
    print(json.dumps({k: out[k] for k in
                      ('hard_requirements', 'share_floor_binds',
                       'degenerate_draws_named_and_given_to_fringe',
                       'n_team_games')}, indent=1))
    print(json.dumps(out['per_draw_dependence'], indent=1, default=float))
    print(f'wrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
