#!/usr/bin/env python3.12
"""SHADOW archetype-first field generator and three-estimator duplicate stack. EXTERNAL_RESEARCH_SHADOW.

    python3.12 nfl/field/showdown_archetype_field.py EXPORT SCENARIO_DIR SHADOW_DIR [--k 50000]

Method candidates MC-FIELD-1 and MC-DUPE-1 (nfl/research/external/2026-10-05_addendum/METHOD_CANDIDATES.json).
PRODUCTION_CANDIDATE, NOT PROMOTED, NOT VALIDATED. Never a football input; never changes a production lineup.

GENERATOR (addendum section 4.2)
  1. archetype first: (away-team count, QB count, K+DST count) drawn from a prior
  2. CPT, then FLEX, drawn from Dirichlet-jittered slot shares -- one jitter per GENERATION of lineups -- restricted
     to players that keep the archetype's quotas satisfiable; DK legality (cap, distinct players) accept/reject
  3. iterative proportional calibration of the sampling weights until generated CPT and FLEX ownership match the
     targets; residuals reported
  WHAT IS NOT FITTED TONIGHT, AND IS SAID SO:
    - targets: the slot ownership of the optimizer-exposure SHADOW field passed in (FC_ONLY or BLEND), not a fitted
      ownership model (MC-OWN-1 has no Showdown history to fit on)
    - archetype prior: the joint archetype rates of that same optimizer field (DERIVED_FROM_OPTIMIZER_FIELD), not
      contest-bucket priors from standings; one contest bucket for all three contests
    - jitter concentration phi: ASSUMED; reported at PHIS so the sensitivity is visible
    - no salary-used target: any legal lineup is accepted; the resulting salary-left distribution is reported

DUPE STACK (addendum section 5.2), per production lineup, scaled to the ESTIMATED field size N:
  E1 independent product   N x CPT share x product of FLEX shares (targets)
  E2 adjusted product      E1 x ETR-seeded correlation factors only (CPT WR with own QB x2.0; CPT QB with the
                           opposing DST x0.36), SEEDED_NOT_FITTED; salary-left and construction factors 1.0, NOT_FITTED
  E3 empirical             copies in the generated field x N / K (linear scaling, stated; a count of 0 means fewer
                           than N/K copies, reported as an upper bound, never as 0)
  E4 optimizer field       copies in the optimizer-exposure shadow field x N / K_opt (existing estimator)
  FLAG when E1 and E3 differ by more than 2x (or one is below its resolution and the other is not).
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_shadow_field as SF  # noqa: E402
from nfl.tools import showdown_portfolio_audit as PA  # noqa: E402

LABEL = 'EXTERNAL_RESEARCH_SHADOW'
STATUS = 'PRODUCTION_CANDIDATE -- NOT PROMOTED, NOT VALIDATED'
PHIS = (50.0, 200.0, 1000.0)       # Dirichlet concentration: ASSUMED, swept; not fitted
PHI_REPORTED = 200.0               # the middle of the sweep is the one carried to the board; all three are written
K = 50000
GENERATIONS = 50                   # one Dirichlet jitter per generation of K / GENERATIONS lineups
CAL_ROUNDS = 40
CAL_K = 20000
SEED = 20261005
CAP = 50000
CORR_SEED = {'CPT_WR_WITH_OWN_QB': 2.0, 'CPT_QB_WITH_OPPOSING_DST': 0.36}   # ETR Showdown 101, SEEDED_NOT_FITTED
FLAG_RATIO = 2.0


def _cat(pos):
    return 'QB' if pos == 'QB' else ('KD' if pos in ('K', 'DST') else 'OT')


def targets(shadow_dir, slate):
    lines = np.load(pathlib.Path(shadow_dir) / 'shadow_field_lineups.npy', allow_pickle=True)
    field = [(r[0], tuple(sorted(r[1:]))) for r in lines]
    own = SF.ownership(field, None)
    away, home = slate['away'], slate['home']
    arche = collections.Counter()
    for c, f in field:
        seats = [c] + list(f)
        P = slate['players']
        arche[(sum(P[x]['dk_team'] == away for x in seats), sum(_cat(P[x]['position']) == 'QB' for x in seats),
               sum(_cat(P[x]['position']) == 'KD' for x in seats))] += 1
    n = len(field)
    return own, {a: v / n for a, v in arche.items()}, field


class Pool:
    def __init__(self, slate, own):
        P = slate['players']
        self.keys = sorted(k for k in own if own[k]['total'] > 0)
        self.team = np.array([P[k]['dk_team'] == slate['away'] for k in self.keys])      # True = away
        self.cat = np.array([_cat(P[k]['position']) for k in self.keys])
        self.sal = np.array([P[k]['flex']['salary'] for k in self.keys])
        self.csal = np.array([P[k]['cpt']['salary'] for k in self.keys])
        self.tc = np.array([own[k]['cpt'] / 100.0 for k in self.keys])                    # sums to 1
        self.tf = np.array([own[k]['flex'] / 100.0 for k in self.keys])                   # sums to 5
        self.pos = [P[k]['position'] for k in self.keys]


def generate(pool, arche, wc, wf, k, phi, rng):
    """Vectorised: each GENERATION is one Dirichlet jitter and a batch of lineups. Each slot is drawn by masked
    Gumbel-max over log-weights, which samples exactly in proportion to the weights among feasible players
    (archetype team / category quotas left, not already chosen). Over-cap lineups are rejected."""
    A = list(arche)
    pa = np.array([arche[a] for a in A])
    Aaway = np.array([a[0] for a in A])
    Aqb = np.array([a[1] for a in A])
    Akd = np.array([a[2] for a in A])
    n = len(pool.keys)
    is_away = pool.team.astype(bool)
    cat_i = np.array([{'QB': 0, 'KD': 1, 'OT': 2}[c] for c in pool.cat])
    per_gen = max(1, k // GENERATIONS)
    out, rejected, arch_of = [], 0, []
    short = np.zeros(len(A), dtype=int)
    while len(out) < k:
        jc = rng.dirichlet(np.maximum(phi * wc / wc.sum(), 1e-6))
        jf = rng.dirichlet(np.maximum(phi * wf / wf.sum(), 1e-6))
        B = int(per_gen / 0.3) + 64             # oversample: each archetype stratum fills from its own accepts
        ai = rng.choice(len(A), size=B, p=pa)
        qt = np.stack([6 - Aaway[ai], Aaway[ai]], axis=1)                      # [home, away] quotas
        qc = np.stack([Aqb[ai], Akd[ai], 6 - Aqb[ai] - Akd[ai]], axis=1)
        alive = qc[:, 2] >= 0
        used = np.zeros((B, n), dtype=bool)
        pick = np.zeros((B, 6), dtype=np.int64)
        budget = np.full(B, float(CAP))
        cheap = np.sort(pool.sal)
        for slot in range(6):
            lw = np.log(np.maximum(jc if slot == 0 else jf, 1e-300))
            cost = pool.csal if slot == 0 else pool.sal
            # budget-aware: a player is drawable only if the slots after him can still be filled at the cheapest
            # FLEX salaries (a lower bound; the exact cap check below still rejects)
            reserve = cheap[:5 - slot].sum() if slot < 5 else 0.0
            feas = (qt[:, is_away.astype(int)] > 0) & (qc[:, cat_i] > 0) & ~used \
                & (cost[None, :] + reserve <= budget[:, None])
            g = lw[None, :] - np.log(-np.log(rng.random((B, n))))
            g = np.where(feas, g, -np.inf)
            j = np.argmax(g, axis=1)
            ok = np.isfinite(g[np.arange(B), j])
            alive &= ok
            pick[:, slot] = j
            used[np.arange(B), j] = True
            qt[np.arange(B), is_away[j].astype(int)] -= 1
            qc[np.arange(B), cat_i[j]] -= 1
            budget -= cost[j]
        sal = pool.csal[pick[:, 0]] + pool.sal[pick[:, 1:]].sum(axis=1)
        good = alive & (sal <= CAP)
        rejected += int(B - good.sum())
        # STRATIFIED: each archetype gets its prior share of the generation from its own accepted draws, so a cap-
        # heavy archetype (two QBs) is not thinned out by rejection; draws for an archetype that cannot fill are kept
        # as they come and counted
        quota = np.floor(per_gen * pa + rng.random(len(A))).astype(int)
        for a_i in range(len(A)):
            rows = pick[good & (ai == a_i)][:quota[a_i]]
            short[a_i] += quota[a_i] - len(rows)
            for row in rows:
                out.append((int(row[0]), tuple(sorted(int(x) for x in row[1:]))))
                arch_of.append(a_i)
        if len(out) >= k:
            break
    out, arch_of = out[:k], arch_of[:k]
    generate.last = {'archetype_rates': {A[i]: round(c / len(out), 4) for i, c in collections.Counter(arch_of).items()},
                     'archetype_shortfall': {A[i]: int(v) for i, v in enumerate(short) if v > 0}}
    return out, rejected


def realised(pool, lines):
    n = len(lines)
    rc = np.zeros(len(pool.keys))
    rf = np.zeros(len(pool.keys))
    for c, f in lines:
        rc[c] += 1
        rf[list(f)] += 1
    return rc / n, rf / n


def calibrate(pool, arche, phi, rng):
    wc, wf = pool.tc.copy(), pool.tf.copy()
    hist = []
    for r in range(CAL_ROUNDS):
        L, _ = generate(pool, arche, wc, wf, CAL_K, phi, rng)
        rc, rf = realised(pool, L)
        hist.append({'round': r, 'cpt_rmse_pts': round(100 * float(np.sqrt(np.mean((rc - pool.tc) ** 2))), 3),
                     'flex_rmse_pts': round(100 * float(np.sqrt(np.mean((rf - pool.tf) ** 2))), 3)})
        # damped proportional update (square root of the ratio): the cap and the quotas couple the slots, and the
        # undamped update oscillates
        wc = wc * np.sqrt(np.where(rc > 0, pool.tc / np.maximum(rc, 1e-9), 1.0))
        wf = wf * np.sqrt(np.where(rf > 0, pool.tf / np.maximum(rf, 1e-9), 1.0))
    return wc, wf, hist


def stack(ours, pool_keys_index, pool, gen_counts, k, opt_counts, k_opt, own, slate, N):
    P = slate['players']
    rows = []
    for c, f in ours:
        key = (c, tuple(sorted(f)))
        e1 = N * (own.get(c, {}).get('cpt', 0) / 100.0) * math.prod(own.get(x, {}).get('flex', 0) / 100.0 for x in f)
        cpos = P[c]['position']
        fac, why = 1.0, []
        if cpos == 'WR' and any(P[x]['position'] == 'QB' and P[x]['dk_team'] == P[c]['dk_team'] for x in f):
            # ETR Showdown 101: completing a CPT WR + QB stack 5.1 -> 10.1 expected dupes; WR only, as stated
            fac *= CORR_SEED['CPT_WR_WITH_OWN_QB']
            why.append('CPT_WR_WITH_OWN_QB x2.0')
        if cpos == 'QB' and any(P[x]['position'] == 'DST' and P[x]['dk_team'] != P[c]['dk_team'] for x in f):
            fac *= CORR_SEED['CPT_QB_WITH_OPPOSING_DST']
            why.append('CPT_QB_WITH_OPPOSING_DST x0.36')
        e2 = e1 * fac
        gk = None
        if c in pool_keys_index and all(x in pool_keys_index for x in f):
            gk = (pool_keys_index[c], tuple(sorted(pool_keys_index[x] for x in f)))
        g = gen_counts.get(gk, 0) if gk else 0
        res3 = N / k
        e3 = g * N / k
        e4 = opt_counts.get(key, 0) * N / k_opt
        absent = [x for x in [c] + list(f) if x not in pool_keys_index]
        if absent:
            flag = 'PLAYER_ABSENT_FROM_FIELD_TARGETS'
        elif g == 0 and e1 >= res3:
            flag = 'E3_BELOW_RESOLUTION_E1_NOT'
        elif g == 0:
            flag = None
        elif e1 <= 0 or max(e1, e3) / max(min(e1, e3), 1e-12) > FLAG_RATIO:
            flag = 'E1_E3_DISAGREE_GT_2X'
        else:
            flag = None
        rows.append({'captain': P[c]['name'], 'flex': [P[x]['name'] for x in f],
                     'E1_independent_product': round(e1, 2), 'E2_adjusted_product': round(e2, 2),
                     'E2_factors': why or ['none'], 'E3_archetype_field': (round(e3, 1) if g else f'<{res3:.1f}'),
                     'E3_count_in_field': g, 'E4_optimizer_field': round(e4, 1), 'FLAG': flag,
                     'players_absent_from_field_targets': [P[x]['name'] for x in absent]})
    return rows


def run(export, sd, shadow_dir, k=K):
    sd, shadow_dir = pathlib.Path(sd), pathlib.Path(shadow_dir)
    R = PA.rebuild(export, sd)
    slate = R['L']['slate']
    sdoc = json.loads((shadow_dir / 'SHOWDOWN_ATL_NO_SHADOW_FIELD.json').read_text())
    src = 'BLEND' if sdoc.get('field_projection') == 'MEAN_OF_FC_AND_OURS' else 'FC_ONLY'
    own, arche, opt_field = targets(shadow_dir, slate)
    pool = Pool(slate, own)
    kidx = {k_: i for i, k_ in enumerate(pool.keys)}
    opt_counts = collections.Counter(opt_field)
    sizes = sdoc['field_size_estimates']
    result = {'ARTIFACT': 'SHOWDOWN_ARCHETYPE_FIELD_AND_DUPE_STACK', 'label': LABEL, 'STATUS': STATUS,
              'method_candidates': ['MC-FIELD-1', 'MC-DUPE-1'], 'targets_from': str(shadow_dir), 'field_projection': src,
              'NOT_FITTED': {'targets': 'optimizer-exposure shadow field ownership, not a fitted ownership model',
                             'archetype_prior': 'DERIVED_FROM_OPTIMIZER_FIELD (joint away-count x QB-count x K/DST-count)',
                             'phi': f'ASSUMED, swept {list(PHIS)}; {PHI_REPORTED} carried to the board',
                             'contest_bucket': 'one bucket for all three contests',
                             'E2': 'ETR-seeded correlation factors only; salary-left and construction factors 1.0'},
              'archetype_prior': {f'{a[0]}away_{a[1]}QB_{a[2]}KD': round(v, 4) for a, v in sorted(arche.items(), key=lambda x: -x[1])},
              'k': k, 'generations': GENERATIONS, 'field_size_estimates': sizes, 'by_phi': {}}
    for phi in PHIS:
        rng = np.random.default_rng(SEED)
        wc, wf, hist = calibrate(pool, arche, phi, rng)
        L, rej = generate(pool, arche, wc, wf, k, phi, rng)
        rc, rf = realised(pool, L)
        arch_rep = {f'{a[0]}away_{a[1]}QB_{a[2]}KD': {'prior': round(arche[a], 4),
                                                       'generated': generate.last['archetype_rates'].get(a, 0.0)}
                    for a in sorted(arche, key=lambda x: -arche[x])}
        gen_counts = collections.Counter(L)
        sal = [CAP - (pool.csal[c] + pool.sal[list(f)].sum()) for c, f in L]
        resid = sorted(((pool.keys[i], 100 * (rc[i] - pool.tc[i]), 100 * (rf[i] - pool.tf[i])) for i in range(len(pool.keys))),
                       key=lambda x: -abs(x[2]))
        P = slate['players']
        cnt = sorted(gen_counts.values(), reverse=True)
        block = {'archetypes_prior_vs_generated': arch_rep,
                 'archetype_shortfall': {f'{a[0]}away_{a[1]}QB_{a[2]}KD': v for a, v in generate.last['archetype_shortfall'].items()},
                 'calibration': hist, 'rejected': rej, 'accept_rate': round(k / (k + rej), 3),
                 'final_residual_rmse_pts': {'cpt': round(float(np.sqrt(np.mean((100 * (rc - pool.tc)) ** 2))), 3),
                                             'flex': round(float(np.sqrt(np.mean((100 * (rf - pool.tf)) ** 2))), 3)},
                 'largest_residuals_pts': [{'player': P[x]['name'], 'cpt': round(a, 2), 'flex': round(b, 2)} for x, a, b in resid[:8]],
                 'salary_left': {'mean': round(float(np.mean(sal))), 'p50': float(np.median(sal)),
                                 'share_0': round(float(np.mean(np.array(sal) == 0)), 3),
                                 'share_le_900': round(float(np.mean(np.array(sal) <= 900)), 3),
                                 'share_1000_1900': round(float(np.mean((np.array(sal) >= 1000) & (np.array(sal) <= 1900))), 3)},
                 'distinct_lineups': len(gen_counts), 'top_copies_in_field': cnt[:5], 'contests': {}}
        for cid, chosen in R['finals'].items():
            ours = [R['cands'][i] for i in chosen]
            N = sizes.get(cid, 50000)
            rows = stack(ours, kidx, pool, gen_counts, k, opt_counts, len(opt_field), own, slate, N)
            fl = collections.Counter(r['FLAG'] for r in rows)
            num = lambda v: v if isinstance(v, (int, float)) else 0.0
            block['contests'][cid] = {
                'N_estimate': N, 'n_lineups': len(rows),
                'mean': {'E1': round(float(np.mean([r['E1_independent_product'] for r in rows])), 2),
                         'E2': round(float(np.mean([r['E2_adjusted_product'] for r in rows])), 2),
                         'E3_lower_bound_mean': round(float(np.mean([num(r['E3_archetype_field']) for r in rows])), 2),
                         'E4': round(float(np.mean([r['E4_optimizer_field'] for r in rows])), 2)},
                'flags': {str(k_): v for k_, v in fl.items()},
                'lineups': rows if len(rows) <= 20 else None,
                'top10_by_E1': sorted(rows, key=lambda r: -r['E1_independent_product'])[:10] if len(rows) > 20 else None}
        result['by_phi'][str(phi)] = block
    p = sd / f'SHOWDOWN_ATL_NO_DUPE_STACK_{src}.json'
    p.write_text(json.dumps(result, indent=1, default=str))
    return p, result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('scenario_dir')
    ap.add_argument('shadow_dir')
    ap.add_argument('--k', type=int, default=K)
    a = ap.parse_args()
    p, r = run(a.export, a.scenario_dir, a.shadow_dir, a.k)
    print(p)
    for phi, b in r['by_phi'].items():
        print('phi', phi, 'accept', b['accept_rate'], 'resid', b['final_residual_rmse_pts'], 'salary_left', b['salary_left'],
              'distinct', b['distinct_lineups'], 'top', b['top_copies_in_field'])
        for cid, c in b['contests'].items():
            print('  ', cid, c['mean'], c['flags'])
