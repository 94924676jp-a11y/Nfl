"""Stage 3: the joint DIAGNOSTIC simulator scaffold.

DIAGNOSTIC ONLY. This harness exists to ask one question -- do individually
reasonable marginal distributions produce coherent and realistic joint football
outcomes -- and it is built so that it cannot quietly become anything else.

Three things it refuses to conflate, because P4C proved they come apart:

    MARGINAL CALIBRATION   is each player's own distribution honest?
    JOINT DEPENDENCE       do players move together the way real ones do?
    ACCOUNTING COHERENCE   do the pieces add up to a legal team game?

P4C showed a system can buy accounting coherence and simultaneously
manufacture dependence that is not there: the compositional families reconciled
perfectly and produced a top1-to-remainder correlation of -0.44 where the truth
was +0.01. So there is no combined score here, and there never will be. Three
blocks, reported side by side.

And every quantity is reported PRE-RECONCILIATION and POST-RECONCILIATION.
Reporting only the reconciled number is how a marginal defect gets absorbed by
the normaliser and disappears from the report.

It uses accepted models only and does not improve them. It may FLAG a marginal
subsystem for re-examination; it may not reject or promote one.
"""
from __future__ import annotations

import collections
import os
import sys

import numpy as np

S = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
for p in (f'{S}/p4e', f'{S}/p4c', f'{S}/p4f'):
    sys.path.insert(0, p)
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p4e_build as PB                                         # noqa: E402
from run_p4c import groups_of                                  # noqa: E402


class DiagnosticOnly(RuntimeError):
    """Raised when something tries to use this harness for a decision."""


# Anything on this list is not a diagnostic question, and asking the harness
# for it is an error rather than an empty result.
FORBIDDEN_USES = ('wager', 'bet', 'stake', 'dfs', 'ownership', 'salary',
                  'lineup', 'portfolio', 'market', 'price', 'odds', 'edge',
                  'roi', 'bankroll', 'parlay', 'prop')


def refuse_if_decision(purpose: str):
    """Every public entry point declares its purpose, and a decision purpose is
    refused. A comment saying 'diagnostic only' is not a control; this is."""
    low = str(purpose).lower()
    hit = [w for w in FORBIDDEN_USES if w in low]
    if hit:
        raise DiagnosticOnly(
            f'DIAGNOSTIC_ONLY: this harness refuses purpose {purpose!r} '
            f'({hit}). It produces joint draws for diagnosis. It does not '
            f'price, stake, optimise or rank anything for money.')
    return True


# ---------------------------------------------------------------------------
# The joint draw schema. One object per (class, evaluation season).
# ---------------------------------------------------------------------------
class JointDraws:
    """A team-game-blocked set of joint draws, with its own provenance.

    Fields, all aligned on the same row order:

      rows      list of panel rows, sorted (ord, team, gsis_id)
      starts    team-game start indices;  counts  team-game sizes
      T         (n, M) team volume draws, SHARED within a team-game
      A         (n, M) appearance indicator draws
      W         (n, M) PRE-reconciliation weights, as the marginal produced them
      S         (n, M) POST-reconciliation shares
      y         (n,)   realised absolute outcome
      S_star    (n,)   realised share;  A_star (n,) realised appearance
      cap       physical per-player share cap;  group_cap  per team-game cap
    """

    def __init__(self, cls, ev, rows, starts, counts, T, A, W, S, y,
                 S_star, A_star, cap, group_cap, marginal_id, mode):
        self.cls, self.ev, self.mode = cls, ev, mode
        self.rows, self.starts, self.counts = rows, starts, counts
        self.T, self.A, self.W, self.S = T, A, W, S
        self.y, self.S_star, self.A_star = y, S_star, A_star
        self.cap, self.group_cap = cap, group_cap
        self.marginal_id = marginal_id          # what produced W; see below
        self.n, self.M = W.shape
        self.G = len(starts)

    # The absolute outcome, before and after reconciliation. PRE uses the
    # weight AS THE MARGINAL PRODUCED IT, with no normalisation at all.
    def Y_pre(self):
        return (self.T * (self.W * self.A)).astype(np.float32)

    def Y_post(self):
        return (self.T * self.S).astype(np.float32)

    def share_pre(self):
        return (self.W * self.A).astype(np.float32)

    def share_post(self):
        return self.S


# ---------------------------------------------------------------------------
def _fisher(c):
    c = np.asarray(c, float)
    c = c[np.isfinite(c)]
    if not len(c):
        return None
    return float(np.tanh(np.mean(np.arctanh(np.clip(c, -0.999, 0.999)))))


def _corr_across_units(A, B):
    a = A - A.mean(0, keepdims=True)
    b = B - B.mean(0, keepdims=True)
    d = np.sqrt((a * a).sum(0)) * np.sqrt((b * b).sum(0))
    return np.divide((a * b).sum(0), d, out=np.full(A.shape[1], np.nan),
                     where=d > 1e-12)


def _pear(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 30 or a[m].std() < 1e-12 or b[m].std() < 1e-12:
        return None
    return float(np.corrcoef(a[m], b[m])[0, 1])


def ppc(Xs, Xr, Ys, Yr, min_units=30):
    """Posterior predictive check on a MATCHED estimand: the across-team-game
    correlation, computed per draw index on the model side and once on the
    realised side. Never compares a within-draw correlation to an across-game
    one -- that was P4E's withdrawn rule 5 and it is not repeated."""
    if len(Xr) < min_units:
        return {'state': 'NOT_APPLICABLE', 'n_units': int(len(Xr))}
    rm = _corr_across_units(Xs, Ys)
    rm = rm[np.isfinite(rm)]
    rstar = _pear(Xr, Yr)
    if rstar is None or len(rm) < 100:
        return {'state': 'NOT_APPLICABLE', 'n_units': int(len(Xr))}
    med, sd = float(np.median(rm)), float(rm.std())
    lo, hi = float(np.percentile(rm, 2.5)), float(np.percentile(rm, 97.5))
    return {'state': 'PASS', 'n_units': int(len(Xr)),
            'model_median_r': med, 'model_ci95': [lo, hi], 'model_sd_r': sd,
            'realised_r': rstar, 'realised_inside_ci95': bool(lo <= rstar <= hi),
            'z': float((rstar - med) / sd) if sd > 1e-12 else None}


# ---------------------------------------------------------------------------
# BLOCK 1: accounting coherence
# ---------------------------------------------------------------------------
def accounting(j: JointDraws, which: str):
    S = j.share_pre() if which == 'pre' else j.share_post()
    Y = j.Y_pre() if which == 'pre' else j.Y_post()
    ss = CL.gsum(S, j.starts)
    Tg = j.T[j.starts]
    ys = CL.gsum(Y, j.starts)
    ss_real = CL.gsum((j.S_star * j.A_star)[:, None], j.starts)[:, 0]
    return {
        'stage': which,
        'impossible_share_gt_cap': float((S > j.cap + 1e-6).mean()),
        'impossible_share_lt_zero': float((S < -1e-9).mean()),
        'individual_cap_violation_rate': float((S > j.cap + 1e-6).mean()),
        'team_group_sum_gt_cap_rate': float((ss > j.group_cap + 1e-6).mean()),
        'team_group_sum_max': float(ss.max()),
        'team_group_sum_physical_cap': float(j.group_cap),
        'team_group_sum_max_over_cap_ratio': float(ss.max() / j.group_cap),
        'realised_group_sum_max': float(
            CL.gsum((j.S_star * j.A_star)[:, None], j.starts)[:, 0].max()),
        'team_accounting_error_mean_abs': float(np.abs(ys - ss * Tg).mean()),
        'modelled_mass_mean': float(ss.mean()),
        'modelled_mass_realised_mean': float(ss_real.mean()),
        'residual_other_mass_mean': (float(1.0 - ss.mean())
                                     if j.mode == 'simplex' else None),
        'residual_other_mass_realised': (float(1.0 - ss_real.mean())
                                         if j.mode == 'simplex' else None),
        'over_allocation_pct': float(100 * (ss.mean() - ss_real.mean())
                                     / max(ss_real.mean(), 1e-9)),
        'team_sum_distribution': {
            'sim_mean': float(ys.mean()), 'sim_sd': float(ys.std()),
            'realised_mean': float(CL.gsum(j.y[:, None], j.starts)[:, 0].mean()),
            'coverage_90': float((
                (CL.gsum(j.y[:, None], j.starts)[:, 0]
                 >= np.percentile(ys, 5, axis=1))
                & (CL.gsum(j.y[:, None], j.starts)[:, 0]
                   <= np.percentile(ys, 95, axis=1))).mean())},
    }


# ---------------------------------------------------------------------------
# BLOCK 2: marginal calibration
# ---------------------------------------------------------------------------
def marginal(j: JointDraws, which: str, rng):
    Y = j.Y_pre() if which == 'pre' else j.Y_post()
    y = j.y
    pit = CL.pit_stats(CL.rpit(Y, y, rng))
    q = {}
    for lvl in (0.50, 0.80, 0.90, 0.95, 0.99):
        lo = np.percentile(Y, 100 * (1 - lvl) / 2, axis=1)
        hi = np.percentile(Y, 100 * (1 + lvl) / 2, axis=1)
        q[str(int(lvl * 100))] = {
            'coverage': float(((y >= lo) & (y <= hi)).mean()),
            'mean_width': float((hi - lo).mean())}
    p99 = np.percentile(Y, 99, axis=1)
    p01 = np.percentile(Y, 1, axis=1)
    return {'stage': which, 'crps': float(CL.crps_samples(Y, y).mean()),
            'mae': float(np.abs(Y.mean(1) - y).mean()),
            'bias': float((Y.mean(1) - y).mean()),
            'randomised_pit': pit, 'coverage': q,
            'tail': {'exceed_p99_rate': float((y > p99).mean()),
                     'below_p01_rate': float((y < p01).mean()),
                     'nominal_upper': 0.01, 'nominal_lower': 0.01}}


# ---------------------------------------------------------------------------
# BLOCK 3: joint dependence
# ---------------------------------------------------------------------------
def dependence(j: JointDraws, which: str, kmax=3):
    S = j.share_pre() if which == 'pre' else j.share_post()
    Y = j.Y_pre() if which == 'pre' else j.Y_post()
    pred = Y.mean(1)
    Sr = j.S_star * j.A_star
    ranks = {k: [] for k in range(1, kmax + 1)}
    pos_pairs = collections.defaultdict(lambda: ([], []))
    gi = []
    for g, s in enumerate(j.starts):
        e = s + j.counts[g]
        idx = list(range(s, e))
        order = sorted(idx, key=lambda i: -pred[i])
        if len(order) < 2:
            continue
        gi.append(g)
        for k in range(1, kmax + 1):
            ranks[k].append(order[k - 1] if len(order) >= k else -1)
        byp = collections.defaultdict(list)
        for i in idx:
            byp[j.rows[i]['position']].append(i)
        for p_ in byp:
            byp[p_].sort(key=lambda i: -pred[i])
        for a, b in (('WR', 'WR'), ('WR', 'TE'), ('WR', 'RB'), ('TE', 'RB')):
            la, lb = byp.get(a, []), byp.get(b, [])
            if a == b:
                if len(la) >= 2:
                    pos_pairs[f'{a}1-{a}2'][0].append(la[0])
                    pos_pairs[f'{a}1-{a}2'][1].append(la[1])
            elif la and lb and la[0] != lb[0]:
                pos_pairs[f'{a}1-{b}1'][0].append(la[0])
                pos_pairs[f'{a}1-{b}1'][1].append(lb[0])
    out = {'stage': which, 'n_team_games_ranked': len(gi), 'pairs': {}}
    R = {k: np.array(v) for k, v in ranks.items()}
    for lbl, (a, b) in (('rank1-rank2', (1, 2)), ('rank1-rank3', (1, 3)),
                        ('rank2-rank3', (2, 3))):
        ia, ib = R[a], R[b]
        m = (ia >= 0) & (ib >= 0)
        ia, ib = ia[m], ib[m]
        out['pairs'][lbl] = ppc(S[ia], Sr[ia], S[ib], Sr[ib])
    for lbl, (ia, ib) in pos_pairs.items():
        if len(ia) < 30:
            continue
        ia, ib = np.array(ia), np.array(ib)
        out['pairs'][lbl] = ppc(S[ia], Sr[ia], S[ib], Sr[ib])
        out['pairs'][lbl]['kind'] = ('same_position' if lbl.split('-')[0][:2]
                                     == lbl.split('-')[1][:2]
                                     else 'cross_position')
    ys = CL.gsum(Y, j.starts)
    Rem = CL.gexp(ys, j.counts) - Y
    i1 = R[1][R[1] >= 0]
    g1 = np.array(gi)
    rem_real = CL.gsum(j.y[:, None], j.starts)[:, 0][g1] - j.y[i1]
    out['pairs']['top1-remainder'] = ppc(Y[i1], j.y[i1], Rem[i1], rem_real)
    ss = CL.gsum(S, j.starts)
    hhi = np.divide(CL.gsum(S * S, j.starts), np.maximum(ss ** 2, 1e-12))
    p = np.divide(S, np.maximum(CL.gexp(ss, j.counts), 1e-12))
    ent = -CL.gsum(np.where(p > 1e-9, p * np.log(np.maximum(p, 1e-9)), 0.0),
                   j.starts)
    ssr = CL.gsum(Sr[:, None], j.starts)[:, 0]
    pr = np.divide(Sr, np.maximum(CL.gexp(ssr[:, None], j.counts)[:, 0], 1e-12))
    out['concentration'] = {
        'hhi_sim': float(hhi.mean()), 'hhi_sim_sd': float(hhi.std()),
        'hhi_realised': float(np.mean(np.divide(
            CL.gsum((Sr ** 2)[:, None], j.starts)[:, 0],
            np.maximum(ssr ** 2, 1e-12)))),
        'entropy_sim': float(ent.mean()),
        'entropy_realised': float(np.mean(-CL.gsum(
            np.where(pr > 1e-9, pr * np.log(np.maximum(pr, 1e-9)), 0.0)[:, None],
            j.starts)[:, 0]))}
    return out


def diagnose(j: JointDraws, purpose='diagnostic', seed=None):
    """The full battery, PRE and POST, in three separate blocks."""
    refuse_if_decision(purpose)
    rng_seed = CL.SEED + 31 if seed is None else seed
    return {
        'class': j.cls, 'season': j.ev, 'mode': j.mode, 'n': j.n, 'G': j.G,
        'M_draws': j.M, 'marginal_id': j.marginal_id,
        'accounting_coherence': {w: accounting(j, w) for w in ('pre', 'post')},
        'marginal_calibration': {
            w: marginal(j, w, np.random.default_rng(rng_seed))
            for w in ('pre', 'post')},
        'joint_dependence': {w: dependence(j, w) for w in ('pre', 'post')},
        'reporting_rule': ('pre and post are reported side by side, and the '
                           'three blocks are never combined into one score'),
    }
