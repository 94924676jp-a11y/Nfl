"""C1: the carry allocator's `other` mass on the denominator production uses.

Pre-registration `predeclaration_c1_denominator.md`, sha256
9d0443e1bd777d31371d2f7073c4e8acf2be9afcc6b4730471957b225e83e9a0.
EXPLORATORY under its section 8. Nothing here is promoted.

THE COMPARISON THIS RUNS, AND WHY IT IS NOT THE RESEARCH HARNESS

`run_p4c` evaluates the carries class against `T = team_carries`, which is the
denominator the class declares. Under that wiring the fitted mass is correct
and the modelled block takes 0.801 of team carries against a historical 0.8082.
THE RESEARCH ARM WAS NEVER WRONG.

Production does not use that wiring. `run_forecast` hands the allocator A1's
`rb` CATEGORY and keeps the same mass, so the modelled block takes 0.801 of a
budget that is itself 0.86 of the rush-play budget -- about 0.69 of team
carries. The defect lives in the seam between two changes that were each right
on their own: A1 became the sole owner of the rushing partition, and OWN-6/7
fixed the mass to be consumed as a share. Neither noticed the other had moved
the denominator.

So this harness reproduces PRODUCTION'S wiring on historical seasons and
varies exactly one thing.

    BASELINE   w_other = mass_pool      (fitted on the TEAM denominator)
    C1         w_other = mass_pool_rb   (the same rows, on the RB denominator)

TEAM VOLUME IS ORACLED, AND THAT IS A DECLARED CHOICE, NOT A CONVENIENCE.
The slate audit measured team volume as essentially unbiased (team_carries
z = +0.02). Holding it at its realised value isolates the allocation layer,
which is the layer under test. It also means these CRPS numbers are NOT
comparable with `run_p4c`'s, and they are not presented as such.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _p in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4c')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sportsplatform.governance.outcome import (                  # noqa: E402
    Cause, Outcome, State)
from nfl.production import derived as DERIVED                    # noqa: E402

# THE DERIVED ARTIFACTS ARE GITIGNORED AND LIVE IN THE PRODUCTION CACHE, NOT
# IN nfl/research/p4b. `derived.artifacts` points every research module that
# reads them at that cache and verifies their hashes first, so this evaluation
# reads the SAME bytes production does rather than a second copy.
_art = DERIVED.artifacts()
if _art.state is not State.PASS:                                 # pragma: no cover
    raise SystemExit(f'{_art.code}: {_art.detail}')

import p4c_build as B                                            # noqa: E402
import p4c_lib as L                                              # noqa: E402

SPEC_VERSION = 'c1-denominator-eval/1.0.0'
PREREG_SHA = '9d0443e1bd777d31371d2f7073c4e8acf2be9afcc6b4730471957b225e83e9a0'
CLS = 'carries'
EVAL_SEASONS = (2022, 2023, 2024)
M = 400
SEED = 20260914

# A1's league `rb` share, read from the frozen production parameters rather
# than retyped. If A1 is refit this moves with it instead of going stale.
def a1_rb_share() -> Outcome:
    from nfl.production.nonqb import rushing_a1 as RA1
    o = RA1.params(2026, 1)
    if o.state is not State.PASS:
        return o
    lg = o.value['league']
    return Outcome.ok('A1_LEAGUE_SHARES', value={k: float(v) for k, v in
                                                 lg.items()},
                      path=o.evidence.get('path'))


def mass_pools(sub, ev, rows_all) -> Outcome:
    """Both `other` pools from the SAME training rows, on both denominators.

    `mass_pool` reproduces `p4c_build` exactly -- 1.0 minus the modelled RBs'
    share of TEAM carries. `mass_pool_rb` is the same numerator over the RB
    mass instead, which is the share of the RUNNING-BACK budget taken by backs
    the pool does not model.

    A team-game with no running-back mass at all contributes to neither pool.
    Dropping it is not the same as scoring it zero and the count is returned.
    """
    c = L.CLASSES[CLS]
    skey = c['share']
    ms = collections.defaultdict(float)      # modelled RBs
    mall = collections.defaultdict(float)    # every position (== 1.0)
    mpos = collections.defaultdict(float)    # every RB, modelled or not
    seasons = set()
    for r in rows_all:
        if r['season'] >= ev or r['season'] in L.MASS_POOL_EXCLUDE_SEASONS:
            continue
        s = r.get(skey)
        if s is None:
            continue
        seasons.add(r['season'])
        k = (r['team'], r['ord'])
        mall[k] += s
        if r['position'] in c['pos']:
            mpos[k] += s
            if (r.get('f_n_prior') or 0) >= 1:
                ms[k] += s
    if not mall:
        return Outcome.blocked(
            'C1_MASS_POOL_EMPTY',
            f'no training rows before {ev}. An empty pool is an error, not a '
            f'measurement.', cause=Cause.DATA, ev=ev)
    base = np.array([max(0.0, min(0.95, mall[k] - ms[k])) for k in mall],
                    np.float32)
    keys_rb = [k for k in mall if mpos[k] > 1e-9]
    rb = np.array([max(0.0, min(0.95, (mpos[k] - ms[k]) / mpos[k]))
                   for k in keys_rb], np.float32)
    if not rb.size:
        return Outcome.blocked(
            'C1_RB_MASS_POOL_EMPTY',
            'every training team-game carried zero running-back mass, which '
            'cannot be true and is refused rather than returned as a pool.',
            cause=Cause.DATA, ev=ev)
    return Outcome.ok('C1_MASS_POOLS_BUILT', value={
        'mass_pool': base, 'mass_pool_rb': rb},
        n_team_games=len(mall),
        n_team_games_with_rb_mass=len(keys_rb),
        n_team_games_dropped_no_rb_mass=len(mall) - len(keys_rb),
        seasons_used=sorted(seasons),
        baseline_mean=round(float(base.mean()), 6),
        c1_mean=round(float(rb.mean()), 6))


def _groups(te):
    starts, counts, keys = [], [], []
    i = 0
    while i < len(te):
        k = (te[i]['team'], te[i]['ord'])
        j = i
        while j < len(te) and (te[j]['team'], te[j]['ord']) == k:
            j += 1
        starts.append(i)
        counts.append(j - i)
        keys.append(k)
        i = j
    return np.array(starts), np.array(counts), keys


def _metrics(Y, y, rng):
    """Everything section 5 of the pre-registration names, per row."""
    crps = L.crps_samples(Y, y)
    mean = Y.mean(axis=1)
    lo50, hi50 = np.percentile(Y, [25, 75], axis=1)
    lo80, hi80 = np.percentile(Y, [10, 90], axis=1)
    lo90, hi90 = np.percentile(Y, [5, 95], axis=1)
    return {'crps': crps, 'bias': mean - y, 'abs': np.abs(mean - y),
            'mean': mean,
            'in50': ((y >= lo50) & (y <= hi50)).astype(float),
            'in80': ((y >= lo80) & (y <= hi80)).astype(float),
            'in90': ((y >= lo90) & (y <= hi90)).astype(float),
            'pit': L.rpit(Y, y, rng)}


def run(eval_seasons=EVAL_SEASONS, m=M) -> Outcome:
    sh = a1_rb_share()
    if sh.state is not State.PASS:
        return sh
    rb_share = sh.value['rb']
    rows = B.load_panel()
    vol = B.load_volume()
    if not rows:
        return Outcome.blocked('C1_PANEL_EMPTY', 'the P4C panel loaded zero '
                               'rows.', cause=Cause.DATA)
    pa = B.appearance(rows)
    sub = B.prepare_class(rows, CLS)
    c = L.CLASSES[CLS]
    skey, ykey = c['share'], c['y']
    per_season, agg = {}, collections.defaultdict(list)
    for ev in eval_seasons:
        store = vol.get((c['den'], ev))
        if store is None:
            return Outcome.blocked(
                'C1_VOLUME_STORE_MISSING',
                f'no team-volume store for {c["den"]} season {ev}. Refused '
                f'rather than evaluated on a season it cannot draw.',
                cause=Cause.DATA, ev=ev)
        par = B.fit_params(sub, CLS, ev, rows)
        pools = mass_pools(sub, ev, rows)
        if pools.state is not State.PASS:
            return pools
        te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
              and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
              and r.get('_C') is not None
              and (r['team'], r['ord']) in store['index']]
        te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
        if len(te) < 200:
            return Outcome.blocked(
                'C1_TEST_FOLD_TOO_SMALL',
                f'season {ev} yielded {len(te)} test rows, below the 200 this '
                f'evaluation will score. Refused rather than reported thin.',
                cause=Cause.DATA, ev=ev, n=len(te))
        n = len(te)
        starts, counts, gkeys = _groups(te)
        G = len(starts)
        y = np.array([r[ykey] for r in te], float)
        C = np.array([r['_C'] for r in te], np.float32)
        positions = [r['position'] for r in te]
        p_app = np.array([pa[id(r)] for r in te], np.float32)
        ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
        row_cluster = [f"{r['team']}_{r['ord']}" for r in te]
        # TEAM VOLUME ORACLED at its realised level, declared in the docstring.
        # `y` is per player, so the team level is its group sum.
        team_lvl = np.zeros(G)
        for gi, (s0, cnt) in enumerate(zip(starts, counts)):
            team_lvl[gi] = y[s0:s0 + cnt].sum()
        # PRODUCTION'S WIRING: the budget is A1's `rb` category, not the team
        # level. Held identical across both arms so the only difference is the
        # mass.
        rb_budget = np.repeat((team_lvl * rb_share)[:, None], m, axis=1)
        rngA = np.random.default_rng(SEED + 1009)
        Ad = (rngA.random((n, m), np.float32) < p_app[:, None])
        W = B.gen_weights('C', C, positions, par, CLS, n, m,
                          np.random.default_rng(SEED + 3000))
        season_rec = {'n_rows': n, 'n_team_games': G,
                      'pool_evidence': dict(pools.evidence)}
        arms = {}
        for arm, key in (('BASELINE', 'mass_pool'), ('C1', 'mass_pool_rb')):
            pool = pools.value[key]
            rng = np.random.default_rng(SEED + 5000)
            w_other = pool[rng.integers(0, len(pool), (G, m))]
            S, other, nb = L.allocate(W, Ad, starts, counts, 'simplex', None,
                                      w_other)
            Y = (np.repeat(rb_budget, counts, axis=0) * S).astype(np.float32)
            mt = _metrics(Y, y, np.random.default_rng(SEED + 31))
            # CLOSURE, checked rather than asserted: the modelled shares plus
            # `other` must be 1 in every draw of every team-game.
            closure = float(np.abs(L.gsum(S, starts) + other - 1.0).max())
            arms[arm] = mt
            season_rec[arm] = {
                'crps': round(float(mt['crps'].mean()), 6),
                'bias': round(float(mt['bias'].mean()), 6),
                'mae': round(float(mt['abs'].mean()), 6),
                'mean_projected': round(float(mt['mean'].mean()), 6),
                'mean_actual': round(float(y.mean()), 6),
                'cov50': round(float(mt['in50'].mean()), 4),
                'cov80': round(float(mt['in80'].mean()), 4),
                'cov90': round(float(mt['in90'].mean()), 4),
                'pit_mean': round(float(np.mean(mt['pit'])), 4),
                'other_mean': round(float(other.mean()), 6),
                'closure_max_abs_dev': closure,
                'n_degenerate_groups': int(nb),
            }
            for k in ('crps', 'bias', 'abs', 'in50', 'in80', 'in90'):
                agg[f'{arm}|{k}'].extend(list(mt[k]))
        agg['cluster'].extend(row_cluster)
        agg['y'].extend(list(y))
        boot = L.block_boot(arms['C1']['crps'], arms['BASELINE']['crps'],
                            row_cluster, n=400, seed=SEED)
        season_rec['crps_diff_c1_minus_baseline'] = (
            round(season_rec['C1']['crps'] - season_rec['BASELINE']['crps'], 6))
        season_rec['crps_diff_clustered_bootstrap'] = boot
        per_season[ev] = season_rec
    pooled = {}
    for arm in ('BASELINE', 'C1'):
        pooled[arm] = {
            'crps': round(float(np.mean(agg[f'{arm}|crps'])), 6),
            'bias': round(float(np.mean(agg[f'{arm}|bias'])), 6),
            'mae': round(float(np.mean(agg[f'{arm}|abs'])), 6),
            'cov50': round(float(np.mean(agg[f'{arm}|in50'])), 4),
            'cov80': round(float(np.mean(agg[f'{arm}|in80'])), 4),
            'cov90': round(float(np.mean(agg[f'{arm}|in90'])), 4),
        }
    boot = L.block_boot(agg['C1|crps'], agg['BASELINE|crps'], agg['cluster'],
                        n=2000, seed=SEED)
    crit = {
        '1_crps_improves': pooled['C1']['crps'] < pooled['BASELINE']['crps'],
        '2_clustered_interval_excludes_zero': bool(
            boot and (boot['hi'] < 0 or boot['lo'] > 0)),
        '3_consistent_in_all_three_seasons': all(
            per_season[e]['crps_diff_c1_minus_baseline'] < 0
            for e in eval_seasons),
        '4_bias_moves_toward_zero_without_overshoot': (
            abs(pooled['C1']['bias']) < abs(pooled['BASELINE']['bias'])),
        '5_closure_exact': all(
            per_season[e][a]['closure_max_abs_dev'] < 1e-5
            for e in eval_seasons for a in ('BASELINE', 'C1')),
    }
    return Outcome.ok('C1_EVALUATION_COMPLETE', value={
        'artifact': 'C1_DENOMINATOR_EVALUATION',
        'spec_version': SPEC_VERSION,
        'preregistration_sha256': PREREG_SHA,
        'status': 'EXPLORATORY',
        'governance': ('Not prospective evidence. Not promoted. R8 remains '
                       'the accepted baseline.'),
        'design': {
            'arms': {'BASELINE': 'w_other from mass_pool, fitted on the TEAM '
                                 'denominator -- what production does today',
                     'C1': 'w_other from mass_pool_rb, the same numerator on '
                           'the RUNNING-BACK denominator'},
            'held_identical': ['weights W', 'appearance draws', 'A1 rb budget',
                               'seed', 'draw index', 'test rows'],
            'team_volume': 'ORACLED at the realised team level, declared',
            'a1_rb_league_share': round(float(rb_share), 6),
            'eval_seasons': list(eval_seasons), 'n_draws': m, 'seed': SEED,
        },
        'per_season': per_season,
        'pooled': pooled,
        'pooled_crps_diff_clustered_bootstrap': boot,
        'acceptance_criteria_section_7': crit,
        'accepted': all(crit.values()),
        'market_information_consulted': 'NONE',
    }, spec_version=SPEC_VERSION, accepted=all(crit.values()))


def main():
    o = run()
    print(f'{o.state.name} {o.code}')
    if o.state is not State.PASS:
        print(o.detail)
        return 1
    dest = _REPO / 'nfl' / 'research' / 'slate_audit' / 'C1_EVALUATION.json'
    dest.write_text(json.dumps(o.value, indent=1, default=float) + '\n')
    v = o.value
    print(f'\n{"":10} {"CRPS":>9} {"bias":>9} {"MAE":>9} {"cov50":>7} '
          f'{"cov80":>7} {"cov90":>7}')
    for arm in ('BASELINE', 'C1'):
        p = v['pooled'][arm]
        print(f'{arm:10} {p["crps"]:9.4f} {p["bias"]:+9.4f} {p["mae"]:9.4f} '
              f'{p["cov50"]:7.3f} {p["cov80"]:7.3f} {p["cov90"]:7.3f}')
    print('\nper season (C1 - BASELINE CRPS):')
    for e, r in v['per_season'].items():
        b = r['crps_diff_clustered_bootstrap'] or {}
        print(f"  {e}  {r['crps_diff_c1_minus_baseline']:+.5f}  "
              f"95% [{b.get('lo', float('nan')):+.5f}, "
              f"{b.get('hi', float('nan')):+.5f}]  clusters {b.get('n_clusters')}"
              f"   other: base {r['BASELINE']['other_mean']:.4f} -> "
              f"C1 {r['C1']['other_mean']:.4f}")
    print('\nacceptance:')
    for k, val in v['acceptance_criteria_section_7'].items():
        print(f'  {"PASS" if val else "FAIL"}  {k}')
    print(f'\nACCEPTED: {v["accepted"]}')
    print(f'wrote {dest.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
