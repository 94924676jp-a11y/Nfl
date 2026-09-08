"""RC1 simulator and oracle arms.

Y = T x C x V, drawn rather than estimated, so CRPS and coverage mean something.

ORACLE vs CANDIDATE SUBSTITUTION -- the distinction that matters, and it is not
a detail. See addendum_rc1_substitution.md, written before any result was seen.

  ORACLE     the component's TRUE value, which by definition carries no
             uncertainty. Collapsing its dispersion is what "perfect" means,
             and arm E can only reproduce Y exactly if it does.
  CANDIDATE  a MODEL's estimate, which does carry uncertainty. Replacing its
             draws with a point estimate destroys dispersion and manufactures
             apparent harm. R1 measured this: CV 0.914 of dispersion lost,
             +0.0542 of the +0.0100 apparent harm attributable to the
             substitution itself rather than the candidate.

Both rules live here and are asserted separately by the test suite.
"""
from __future__ import annotations

import collections, itertools, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rc1_lib as L                                            # noqa: E402

COMPONENTS = ('T', 'C', 'V')


def pools(sub, ev):
    """Positional pools from STRICTLY PRIOR seasons. Never the eval season."""
    pT = collections.defaultdict(list)
    pV = collections.defaultdict(list)
    pR = collections.defaultdict(lambda: [0, 0])
    for r in sub:
        if r['season'] >= ev or not r['appeared']:
            continue
        pos = r['position']
        pT[pos].append(r['T'])
        pR[pos][0] += r['R']
        pR[pos][1] += r['T']
        pV[pos].extend(r.get('rec_yards_list') or [])
    return ({k: np.array(v, float) for k, v in pT.items()},
            {k: np.array(v, float) for k, v in pV.items()},
            {k: (v[0] / v[1] if v[1] else 0.0) for k, v in pR.items()})


def simulate(rs, ev, sub, oracle=(), M=L.M_DRAWS, seed=L.SEED,
             candidate=None):
    """Draw M receiving-yard realisations per row.

    `oracle` names components substituted with their realised value.
    `candidate` is a dict {'C': fn, 'V': fn} replacing a component's ESTIMATE
    while preserving dispersion -- the composition-test path.
    """
    pT, pV, prate = pools(sub, ev)
    n = len(rs)
    out = np.zeros((n, M), float)

    for idx, r in enumerate(rs):
        pos = r['position']
        # PER-ROW INDEPENDENT RNG, keyed on the row's identity rather than on
        # its position in the list.
        #
        # A single shared stream made rows coupled: each row consumes a
        # variable number of draws (one per simulated reception), so a change
        # anywhere shifted every LATER row's numbers. The adversarial leakage
        # probe caught it -- 21 rows moved whose prior-only features had not
        # moved at all. That is not leakage, but it made the probe unable to
        # tell leakage from stream drift, and it meant an oracle arm differed
        # from the baseline partly by reshuffling rather than by information.
        # Seeding from (seed, ordinal, player) makes every row reproducible on
        # its own and independent of what any other row did.
        rng = np.random.default_rng(
            [seed, int(r['ord']),
             int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little')])
        w = r['h_n'] / (r['h_n'] + L.K_SHRINK)

        # ---- T ------------------------------------------------------------
        if 'T' in oracle:
            T = np.full(M, r['T'], float)
        else:
            own = np.asarray(r['h_T'], float)
            pool = pT.get(pos, np.array([0.0]))
            use_own = rng.random(M) < w if len(own) else np.zeros(M, bool)
            T = np.where(use_own,
                         own[rng.integers(0, max(len(own), 1), M)] if len(own)
                         else 0.0,
                         pool[rng.integers(0, len(pool), M)])
        T = np.maximum(T, 0).astype(int)

        # ---- C --------------------------------------------------------------
        if 'C' in oracle:
            # Perfect conversion RATE. With T also oracled this returns R
            # exactly; with T drawn it applies the true rate to a drawn volume.
            c = (r['R'] / r['T']) if r['T'] > 0 else prate.get(pos, 0.0)
            R = np.rint(T * c).astype(int)
        else:
            if candidate and 'C' in candidate:
                c = candidate['C'](r, prate.get(pos, 0.0), w)
            else:
                own_rate = (r['h_rec'] / r['h_tgt']) if r['h_tgt'] > 0 else None
                c = (w * own_rate + (1 - w) * prate.get(pos, 0.0)
                     if own_rate is not None else prate.get(pos, 0.0))
            c = min(max(c, 0.0), 1.0)
            R = rng.binomial(T, c)
        R = np.minimum(R, T)

        # ---- V --------------------------------------------------------------
        if 'V' in oracle:
            # Perfect yards per reception. When the player caught nothing, V is
            # undefined and the product is zero regardless, so the pool mean is
            # a placeholder that cannot affect any arm.
            v = (r['Y'] / r['R']) if r['R'] > 0 else float(
                np.mean(pV.get(pos, np.array([0.0]))))
            out[idx] = R * v
            continue

        own_v = np.asarray(r.get('h_V_flat') or [], float)
        pool_v = pV.get(pos, np.array([0.0]))
        total = int(R.sum())
        if total == 0:
            continue
        use_own = (rng.random(total) < w) if len(own_v) else np.zeros(total, bool)
        picks = np.where(
            use_own,
            own_v[rng.integers(0, max(len(own_v), 1), total)] if len(own_v)
            else 0.0,
            pool_v[rng.integers(0, len(pool_v), total)])
        # Split the flat pick vector back into per-draw sums.
        # np.add.reduceat CANNOT express a zero-length segment -- a draw with
        # zero receptions produces a repeated index and it raises. A cumulative
        # sum differenced at the segment bounds handles R = 0 correctly and
        # returns exactly 0 there, which is the right answer rather than a
        # borrowed neighbouring value.
        if candidate and 'V' in candidate:
            # DRAW-PRESERVING RECENTRING, and this is R1's lesson made
            # operational. The candidate supplies a MEAN yards-per-reception.
            # Replacing the picks with that number would collapse the
            # per-catch spread -- R1 lost CV 0.914 that way and charged the
            # loss to the candidate. Instead every pick is scaled by
            # Vhat / mean(picks), which moves the centre and leaves the
            # coefficient of variation, and therefore the tail, untouched.
            vhat = candidate['V'](r, float(pool_v.mean()) if len(pool_v) else 0.0, w)
            mu = float(picks.mean())
            if abs(mu) > 1e-9:
                picks = picks * (vhat / mu)
        cs = np.concatenate([[0.0], np.cumsum(picks)])
        ends = np.cumsum(R)
        starts = ends - R
        out[idx] = cs[ends] - cs[starts]
    return out


def shapley(vals: dict) -> dict:
    """Exact Shapley over the 2^3 subsets of {T, C, V}.

    `vals` maps a frozenset of oracled components to that coalition's value.
    Order-invariant by construction: interaction is shared by the formula, not
    assigned to whichever component happened to be substituted first.
    """
    n = len(COMPONENTS)
    phi = {}
    for c in COMPONENTS:
        rest = [x for x in COMPONENTS if x != c]
        tot = 0.0
        for k in range(len(rest) + 1):
            for S in itertools.combinations(rest, k):
                fs = frozenset(S)
                wgt = (math.factorial(k) * math.factorial(n - k - 1)
                       / math.factorial(n))
                tot += wgt * (vals[fs | {c}] - vals[fs])
        phi[c] = tot
    return phi
