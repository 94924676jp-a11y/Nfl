"""Task 4: sampling behaviour of the frozen harm rules (decile MAE change <= +2 %, position <= +1 %)."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/h1review/src')
from lib import *

B = 4000
out = {}


def strata_changes(proj, cand, act, pos, idx):
    """% MAE change by pooled projection decile (deciles re-formed on these rows, by production proj)
    and by position, for the row subset idx."""
    p, c, a, ps = proj[idx], cand[idx], act[idx], pos[idx]
    ep, ec = np.abs(p - a), np.abs(c - a)
    order = np.argsort(p, kind='stable'); n = len(order)
    lab = np.empty(n, int)
    for k in range(10):
        lab[order[k * n // 10:(k + 1) * n // 10]] = k
    sp = np.bincount(lab, ep, 10); sc = np.bincount(lab, ec, 10)
    dec = (sc / sp - 1) * 100
    posc = np.array([(ec[ps == q].sum() / ep[ps == q].sum() - 1) * 100 for q in POS])
    return dec, posc


for name in ('CHECKA', 'DEV'):
    df = pd.read_csv(f'{R}/scored_{name}.csv.gz', dtype={'gsis': str})
    f = df[(df.appeared == 1) & df.fitted].reset_index(drop=True)
    proj, cand, act, pos = f.proj.to_numpy(), f.cand.to_numpy(), f.actual_dk.to_numpy(), f.pos.to_numpy()
    wk_rows = [np.flatnonzero(f.widx.to_numpy() == w) for w in sorted(f.widx.unique())]
    nW = len(wk_rows)
    allidx = np.arange(len(f))
    dec0, pos0 = strata_changes(proj, cand, act, pos, allidx)
    rng = np.random.default_rng(7)
    # (1) week-block bootstrap of the observed candidate's strata changes
    D, P = np.empty((B, 10)), np.empty((B, 4))
    for b in range(B):
        idx = np.concatenate([wk_rows[i] for i in rng.integers(0, nW, nW)])
        D[b], P[b] = strata_changes(proj, cand, act, pos, idx)
    fail_obs = ((D.max(1) > 2) | (P.max(1) > 1)).mean()
    res = {'n_rows': len(f), 'n_weeks': nW,
           'observed_decile_change_pct': dec0.round(3).tolist(), 'observed_position_change_pct': dict(zip(POS, pos0.round(3).tolist())),
           'boot_sd_decile_pct': D.std(0, ddof=1).round(3).tolist(),
           'boot_ci_decile_pct': [np.percentile(D[:, k], [2.5, 97.5]).round(2).tolist() for k in range(10)],
           'boot_sd_position_pct': dict(zip(POS, P.std(0, ddof=1).round(3).tolist())),
           'boot_ci_position_pct': {q: np.percentile(P[:, i], [2.5, 97.5]).round(2).tolist() for i, q in enumerate(POS)},
           'boot_P_position_exceeds_1pct': {q: round(float((P[:, i] > 1).mean()), 4) for i, q in enumerate(POS)},
           'boot_P_any_harm_rule_fails': round(float(fail_obs), 4)}
    # (2) NULL by week-level relabelling: in each week swap production and candidate with prob 1/2.
    # Under H0 (exchangeable errors within a week) this is the sampling distribution of the strata
    # changes for a candidate whose perturbation has this candidate's size but no systematic effect.
    fails, fd, fp = 0, 0, 0
    DN, PN = np.empty((B, 10)), np.empty((B, 4))
    for b in range(B):
        sw = rng.random(nW) < 0.5
        c2, p2 = cand.copy(), proj.copy()
        for i in np.flatnonzero(sw):
            r = wk_rows[i]; c2[r], p2[r] = proj[r], cand[r]
        # deciles still formed on the production (incumbent) projection, as the frozen evaluation does
        # -> use p2 as the incumbent; this mirrors relabelling which arm is 'production'
        DN[b], PN[b] = strata_changes(p2, c2, act, pos, allidx)
    res['null_weekswap_sd_decile_pct'] = DN.std(0, ddof=1).round(3).tolist()
    res['null_weekswap_sd_position_pct'] = dict(zip(POS, PN.std(0, ddof=1).round(3).tolist()))
    res['null_weekswap_P_decile_rule_fails'] = round(float((DN.max(1) > 2).mean()), 4)
    res['null_weekswap_P_position_rule_fails'] = round(float((PN.max(1) > 1).mean()), 4)
    res['null_weekswap_P_either_fails'] = round(float(((DN.max(1) > 2) | (PN.max(1) > 1)).mean()), 4)
    # (3) NULL by a zero-mean, small perturbation of the same footprint: a candidate that moves the
    # same top-quartile rows by +/- the same absolute amount with a random sign per player-week.
    # Its expected effect on bias is zero; its effect on MAE is a pure noise penalty, so this is the
    # 'harmless-looking but useless' candidate. Scaled to 25 % of the observed move.
    delta = cand - proj
    for scale in (0.25, 1.0):
        DZ, PZ = np.empty((B, 10)), np.empty((B, 4))
        for b in range(B):
            s = np.where(rng.random(len(f)) < 0.5, 1.0, -1.0)
            c3 = proj + scale * s * np.abs(delta)
            DZ[b], PZ[b] = strata_changes(proj, c3, act, pos, allidx)
        res[f'zero_bias_perturb_x{scale}_P_decile_rule_fails'] = round(float((DZ.max(1) > 2).mean()), 4)
        res[f'zero_bias_perturb_x{scale}_P_position_rule_fails'] = round(float((PZ.max(1) > 1).mean()), 4)
        res[f'zero_bias_perturb_x{scale}_mean_decile_pct'] = DZ.mean(0).round(3).tolist()
        res[f'zero_bias_perturb_x{scale}_mean_position_pct'] = dict(zip(POS, PZ.mean(0).round(3).tolist()))
    # (4) Generic: for a stratum with true change exactly 0, P(point estimate > margin) = 1 - Phi(margin/sd)
    from math import erf, sqrt
    Phi = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
    res['P_exceed_if_true_zero_decile'] = [round(1 - Phi(2 / s), 4) if s > 0 else 0.0 for s in D.std(0, ddof=1)]
    res['P_exceed_if_true_zero_position'] = {q: round(1 - Phi(1 / s), 4) for q, s in zip(POS, P.std(0, ddof=1))}
    # (5) What the rule would say under an interval (non-inferiority) reading at the same margins:
    res['NI_upper95_decile_le_2'] = [bool(np.percentile(D[:, k], 97.5) <= 2) for k in range(10)]
    res['NI_upper95_position_le_1'] = {q: bool(np.percentile(P[:, i], 97.5) <= 1) for i, q in enumerate(POS)}
    out[name] = res
    print(name, json.dumps(res, indent=None)[:4000])
json.dump(out, open(f'{R}/rule_sim.json', 'w'), indent=1)
