"""RBDEP: the pre-registered minimal ablation.

    python3.12 nfl/research/rbdep/run_rbdep.py

Two arms, one argument apart. INC is the standing default and takes no
argument; SHR shares one `add_pool` resample position across the players of a
team-game. Five lambda frames, the pre-declared grid. Frame H (lambda = 1) is
the only frame on which anything is scored against an outcome.

The pre-registration is pinned by sha256 below and REVERIFIED here at run time.
A moved pre-registration is a refusal, not a warning: scoring against a
document that changed after the numbers appeared is the thing pre-registration
exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import rbdep_lib as L                                             # noqa: E402
import p4c_build as CB                                            # noqa: E402
from sportsplatform.governance.outcome import (                   # noqa: E402
    Cause, Outcome, State)

PREDECLARATION = os.path.join(HERE, 'predeclaration_rbdep.md')
PREDECLARATION_SHA256 = (
    'f922f2c30d6d5780158be8551ac448da5506aa2da56db6cae4de5cae96697ee5')

ARMS = ('INC', 'SHR')
CRPS_DETERIORATION_LIMIT = 0.010          # section 9.4, relative
TIE_CRPS = 0.002                          # section 5
TIE_R = 0.02                              # section 5
DEGENERACY_INFLATION_FACTOR = 3.0         # section 8, G6


def verify_predeclaration(path=PREDECLARATION, expect=PREDECLARATION_SHA256):
    """GUARD. The pre-registration must be present and byte-identical.

    Load-bearing: with it bypassed the runner scores against whatever the file
    currently says, which is exactly the failure a pre-registration prevents.
    """
    if not os.path.exists(path):
        return Outcome.blocked(
            'RBDEP_PREDECLARATION_ABSENT',
            f'{path} does not exist, so there is nothing to score against.',
            cause=Cause.GOVERNANCE)
    got = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    if got != expect:
        return Outcome.fail(
            'RBDEP_PREDECLARATION_MOVED',
            f'{os.path.basename(path)} hashes {got}, pinned {expect}. The '
            f'pre-registration changed after it was pinned; refusing to score '
            f'a comparison against it.',
            observed=got, pinned=expect)
    return Outcome.ok('RBDEP_PREDECLARATION_VERIFIED', value=got, sha256=got)


def fit_all(rows, vol, pa, sub):
    """Fit once per evaluation season and reuse.

    `fit_params` also writes each row's `_C`, so the eligible-row set and the
    point forecast are captured HERE, in the same call, and every arm then
    reads the same frozen inputs. Refitting inside the arm loop would be
    identical arithmetic ten times over, and would put a mutation of `sub`
    between two arms that are supposed to differ in one argument.
    """
    out = {}
    for ev in L.EVAL:
        store = vol[('team_carries', ev)]
        par = CB.fit_params(sub, L.CLS, ev, rows)
        te = L.eligible_rows(sub, ev, pa, store)
        if not te:
            raise RuntimeError(f'RBDEP_EMPTY_EVAL_SEASON: {ev} produced no '
                               f'eligible rows; an empty step is an error')
        frozen = []
        for r in te:
            d = dict(r)
            d['_p_app'] = pa[id(r)]           # identity is lost by the copy
            frozen.append(d)
        out[ev] = (par, frozen, store)
    return out


def run_arm(fitted, pc, arm, lam, m):
    """One arm at one lambda, pooled over the evaluation seasons."""
    N1, N2, T, y1, y2, Ts = [], [], [], [], [], []
    allrows_draws, allrows_y = [], []
    gates = None
    per_season = {}
    for ev in L.EVAL:
        par, te, store = fitted[ev]
        sim = L.simulate(te, par, None, store, arm, lam, m)
        g = sim['gates']
        gates = g if gates is None else {
            k: (gates[k] + g[k] if k.startswith(('n_', 'G')) and
                not k.endswith(('_rate', '_max_abs_dev')) else
                max(gates[k], g[k]) if k.endswith('_max_abs_dev') else
                gates[k])
            for k in gates}
        starts, counts = sim['starts'], sim['counts']
        y = np.array([r['y_carries'] for r in te], float)
        ti = np.array([store['index'][(r['team'], r['ord'])] for r in te],
                      dtype=np.int64)
        tstar = store['realized'][ti[starts]].astype(float)
        allrows_draws.append(sim['draws'])
        allrows_y.append(y)
        per_season[str(ev)] = {'n_rows': len(te),
                               'n_team_games': int(len(starts)),
                               'gates': g}
        for gi in range(len(starts)):
            s = int(starts[gi])
            e = s + int(counts[gi])
            if e - s < 2:
                continue
            pr = L.rank_two(te, s, e, pc)
            if pr is None:
                continue
            i1, i2 = pr
            N1.append(sim['draws'][i1])
            N2.append(sim['draws'][i2])
            T.append(sim['T'][gi])
            y1.append(y[i1])
            y2.append(y[i2])
            Ts.append(tstar[gi])
    if not N1:
        raise RuntimeError('RBDEP_NO_RANKED_PAIRS: zero team-games supplied '
                           'two prior-ranked backs. An empty result is an '
                           'error, not a finding.')
    # G6 is a rate over group cells; recompute it from the summed counts.
    gates['G5_weight_floor_rate'] = (gates['G5_weight_floor_cells']
                                     / float(gates['n_cells']))
    gates['G6_degenerate_group_rate'] = (gates['G6_degenerate_group_cells']
                                         / float(gates['n_group_cells']))
    out = {'arm': arm, 'lambda': lam, 'gates': gates,
           'gate_verdict': L.gates_verdict(gates).as_dict(),
           'per_season': per_season,
           'dependence': L.dependence(np.stack(N1), np.stack(N2), np.stack(T),
                                      np.array(y1), np.array(y2),
                                      np.array(Ts))}
    if lam == 1.0:
        D = np.concatenate(allrows_draws, axis=0)
        Y = np.concatenate(allrows_y, axis=0)
        mg, _ = L.marginals(D, Y)
        out['marginals'] = mg
    else:
        out['marginals'] = Outcome.not_applicable(
            'RBDEP_MARGINALS_NOT_SCORED_ON_FRAME_L',
            f'lambda={lam} deliberately degrades the share forecast, so a '
            f'CRPS computed there measures the degradation and not the '
            f'model. Section 6 forbids reading quality off Frame L.'
        ).as_dict()
    return out


def decide(res):
    """Section 9, in order. Returns (verdict, notes)."""
    notes = []
    gate_failed = [k for k, v in res.items()
                   if v['gate_verdict']['state'] != 'PASS']
    if gate_failed:
        return 'GATE_FAILED', [f'gates failed for {sorted(gate_failed)}']
    inc_h = res[('INC', 1.0)]['dependence'][
        'LIKE_FOR_LIKE_between_team_game_counts']
    shr_h = res[('SHR', 1.0)]['dependence'][
        'LIKE_FOR_LIKE_between_team_game_counts']
    lam_plus = [lam for lam in L.LAMBDA_GRID
                if res[('INC', lam)]['dependence'][
                    'LIKE_FOR_LIKE_between_team_game_counts']['median'] >= 0]
    if lam_plus:
        fixed = all(res[('SHR', lam)]['dependence'][
            'LIKE_FOR_LIKE_between_team_game_counts']['median'] < 0
            for lam in lam_plus)
        sub = 'ABLATION_FIXES_SIGN' if fixed else 'ABLATION_DOES_NOT_FIX_SIGN'
        notes.append(f'incumbent median r >= 0 at lambda {lam_plus}; '
                     f'ablation {"does" if fixed else "does NOT"} take every '
                     f'one of them negative')
    else:
        sub = 'SIGN_NEVER_WRONG_ON_GRID'
        notes.append('the incumbent median r is negative at every grid point')
    if inc_h['median'] < 0 and inc_h['p_gt_zero'] <= 0.05:
        verdict = 'ABLATION_UNNECESSARY_ON_FRAME_H'
        notes.append(
            f'Frame H incumbent median r {inc_h["median"]:+.4f}, P(r>0) '
            f'{inc_h["p_gt_zero"]:.3f}: the sign is not materially wrong where '
            f'outcomes exist, so no fix is warranted there. Frame L verdict '
            f'{sub}.')
    else:
        verdict = sub
    ci = res[('INC', 1.0)]['marginals']['crps']
    cs = res[('SHR', 1.0)]['marginals']['crps']
    rel = (cs - ci) / ci
    notes.append(f'Frame H CRPS INC {ci:.4f} SHR {cs:.4f} ({rel:+.3%})')
    if rel > CRPS_DETERIORATION_LIMIT:
        notes.append(f'MARGINAL_DETERIORATION: SHR CRPS is {rel:+.3%} against '
                     f'the pre-declared {CRPS_DETERIORATION_LIMIT:+.1%} limit')
        verdict = 'MARGINAL_DETERIORATION'
    dg = (res[('SHR', 1.0)]['gates']['G6_degenerate_group_rate']
          / max(res[('INC', 1.0)]['gates']['G6_degenerate_group_rate'], 1e-12))
    notes.append(f'G6 degenerate-group rate SHR/INC = {dg:.2f}x '
                 f'(pre-declared threshold {DEGENERACY_INFLATION_FACTOR:.0f}x)')
    if dg > DEGENERACY_INFLATION_FACTOR:
        notes.append('SHARED_ARM_DEGENERACY_INFLATION: as predicted in '
                     'section 8, and it counts against SHR')
    if (abs(rel) <= TIE_CRPS
            and abs(shr_h['median'] - inc_h['median']) <= TIE_R):
        notes.append('TIE by section 5, and the incumbent wins ties')
    return verdict, notes


def main():
    t0 = time.time()
    pre = verify_predeclaration()
    print(f'{pre.state.value}[{pre.code}]')
    if pre.state is not State.PASS:
        print(pre.detail)
        return 2
    inp = L.load_inputs()
    if inp.state is not State.PASS:
        print(f'{inp.state.value}[{inp.code}] {inp.detail}')
        return 2
    rows, vol = inp.value
    seas = L.assert_no_future_season(rows)
    if seas.state is not State.PASS:
        print(f'{seas.state.value}[{seas.code}] {seas.detail}')
        return 2
    print(f'seasons {seas.evidence["seasons"]}, scored '
          f'{seas.evidence["scored"]}, burn-in never scored '
          f'{seas.evidence["burn_in_never_scored"]}')
    pa = CB.appearance(rows)
    sub = CB.prepare_class(rows, L.CLS)
    pc = L.prior_week_carries(rows)
    fitted = fit_all(rows, vol, pa, sub)
    print('fitted ' + ', '.join(f'{ev}:{len(fitted[ev][1])} rows'
                                for ev in L.EVAL))
    m = 1000

    res = {}
    for lam in L.LAMBDA_GRID:
        for arm in ARMS:
            res[(arm, lam)] = run_arm(fitted, pc, arm, lam, m)
            r = res[(arm, lam)]
            b = r['dependence']['LIKE_FOR_LIKE_between_team_game_counts']
            g = r['gates']
            print(f'lam {lam:.2f} {arm}  between-team-game counts median r '
                  f'{b["median"]:+.4f}  P(r>0) {b["p_gt_zero"]:.3f}  '
                  f'[p05 {b["p05"]:+.4f} p95 {b["p95"]:+.4f}]   '
                  f'G1 {g["G1_closure_violations"]} G2 '
                  f'{g["G2_budget_violations"]} G3 '
                  f'{g["G3_negative_shares"]}/{g["G3_negative_counts"]} G4 '
                  f'{g["G4_waterfill_bind"]}  floor '
                  f'{g["G5_weight_floor_rate"]:.4f}  degen '
                  f'{g["G6_degenerate_group_rate"]:.4f}')

    verdict, notes = decide(res)
    print(f'\nVERDICT {verdict}')
    for n in notes:
        print(f'  - {n}')
    out = {
        'predeclaration': pre.as_dict(),
        'inputs': inp.as_dict(),
        'seasons': seas.as_dict(),
        'n_draws': m,
        'exploratory': (
            'EXPLORATORY. The evaluation seasons are the seasons P4B and P4C '
            'were selected on. This cannot establish that any variant is '
            'better; a confirmatory result needs games no design decision has '
            'touched.'),
        'arms': {f'{a}|lambda={l}': v for (a, l), v in res.items()},
        'verdict': verdict, 'notes': notes,
        'elapsed_s': round(time.time() - t0, 1),
    }
    with open(f'{HERE}/rbdep_results.json', 'w') as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f'\n-> {HERE}/rbdep_results.json  ({time.time()-t0:.0f}s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
