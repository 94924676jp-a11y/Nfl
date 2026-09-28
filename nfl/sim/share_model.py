#!/usr/bin/env python3.12
"""Logistic-normal opportunity shares, because a Dirichlet cannot represent co-moving teammates.

THE ALGEBRAIC OBSTACLE

Shares must sum to one, so they are compositional and cannot be independent. A Dirichlet handles that
constraint but pays for it with a fixed sign: cov(s_i, s_j) = -w_i w_j / (a + 1), negative for EVERY
pair, with only the magnitude free. Tuning the concentration moves how hard teammates compete; it
cannot let them co-operate.

Football does. Measured in centred-log-ratio space over 1,350 club-games, 10 of the 56 off-diagonal
target-share correlations are POSITIVE -- WR1 with WR2 at +0.219 and WR2 with WR3 at +0.332, which is
what a two-receiver offence looks like. No Dirichlet concentration exists for that, which is why the
simulated WR1~WR2 correlation came out at -0.053 against a measured +0.170: not mistuned, the wrong
family.

THE FAMILY THAT WORKS

A logistic-normal keeps the constraint and frees the sign:

    s = softmax(log w + e),    e ~ MVN(0, Sigma)

The shares still sum to one because the softmax makes them, and Sigma is unrestricted, so positive
and negative co-movement are both representable. Sigma is estimated in centred-log-ratio space, which
is the standard chart for compositional data: it turns a constrained simplex into an unconstrained
Euclidean space where an ordinary covariance means what it usually means.

WHAT IS ESTIMATED OVER, AND WHY IT IS SLOTS

Rosters differ every week, so a covariance over PLAYERS is not identified. It is estimated over
pregame depth SLOTS -- WR1, WR2, WR3, TE1, TE2, RB1, RB2 and everyone else -- which are consistent
across club-games and are the units the projection already speaks in. Ranks are pregame, never from
the stat line being measured.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

PG = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
RH = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'
OUT = _REPO / 'nfl/sim/SHARE_COVARIANCE.json'

RANK_MEASURE = {'QB': 'pass_attempts', 'RB': 'carries', 'WR': 'targets', 'TE': 'targets'}
TARGET_SLOTS = ['WR1', 'WR2', 'WR3', 'TE1', 'TE2', 'RB1', 'RB2', 'OTHER']
CARRY_SLOTS = ['RB1', 'RB2', 'RB3', 'QB1', 'OTHER']
MIN_CLUB = 15
MIN_COMPOSITIONS = 300
IDENTIFIABILITY_MULTIPLE = 2.0
FLOOR = 0.5  # a zero in a composition is a structural zero; CLR needs a positive floor


def _rows(p):
    a = json.loads(p.read_text())
    r = a['rows']
    return r if isinstance(r, list) else list(r.values())


def slot_of(position, depth_rank, slots):
    if depth_rank is None:
        return 'OTHER'
    key = f'{position}{int(depth_rank)}'
    return key if key in slots else 'OTHER'


def _compositions(by_club, rank, field, slots):
    out, sizes = [], []
    for ps in by_club.values():
        tot = sum(float(p[field]) for p in ps if isinstance(p.get(field), (int, float)))
        if tot < MIN_CLUB:
            continue
        acc = collections.Counter()
        for p in ps:
            v = p.get(field)
            if not isinstance(v, (int, float)):
                continue
            pr = rank.get((int(p['season']), int(p['week']), p['player_id']))
            acc[slot_of(pr[0], pr[1], slots) if pr else 'OTHER'] += float(v)
        if acc['OTHER'] <= 0:
            continue
        out.append([max(acc[s], FLOOR) / tot for s in slots])
        sizes.append(tot)
    return out, sizes


def _clr_moments(comps, slots, sample_sizes=None):
    """CLR mean and covariance, with the MULTINOMIAL SAMPLING COMPONENT DECONVOLVED.

    The compositions measured from history are REALISED shares, so their spread already contains the
    sampling noise of drawing a finite number of targets or carries. Feeding that covariance back in
    as a latent shock counts the same dispersion twice, and the first attempt did exactly that: share
    variance ran far above the measured level, which decorrelated a quarterback from his own
    receivers and drove eleven reproduced pairs down to seven.

    For a multinomial with n draws the log-share has approximate variance (1 - w) / (n w) and
    covariance -1 / n between slots. Subtracting that expectation leaves the LATENT covariance, which
    is what the generative model should carry, since the simulator adds the multinomial layer itself.
    Any diagonal driven non-positive by the subtraction is floored rather than left indefinite, and
    the number of floored entries is reported.
    """
    clr = []
    for c in comps:
        lg = [math.log(x) for x in c]
        m = sum(lg) / len(lg)
        clr.append([x - m for x in lg])
    n, k = len(clr), len(slots)
    mu = [sum(r[i] for r in clr) / n for i in range(k)]
    cov = [[sum((r[i] - mu[i]) * (r[j] - mu[j]) for r in clr) / (n - 1) for j in range(k)]
           for i in range(k)]
    floored, identified = 0, None
    if sample_sizes:
        mean_w = [sum(c[i] for c in comps) / len(comps) for i in range(k)]
        nbar = sum(sample_sizes) / len(sample_sizes)
        # IDENTIFIABILITY FIRST. For a thin slot the observed spread is almost entirely sampling
        # noise, so subtracting it leaves a latent variance at or below zero. Flooring that and
        # dividing by it produced correlations of +287, which is not a number to ship. A slot is
        # kept separate only where the observed variance materially exceeds the sampling variance;
        # the rest are not identified at this sample and are reported as such rather than modelled.
        identified = []
        for i in range(k):
            w = max(1e-6, mean_w[i])
            samp = (1.0 - w) / (nbar * w)
            if cov[i][i] > IDENTIFIABILITY_MULTIPLE * samp:
                identified.append(slots[i])
        for i in range(k):
            w = max(1e-6, mean_w[i])
            samp = (1.0 - w) / (nbar * w)
            cov[i][i] = cov[i][i] - samp
            if cov[i][i] <= 1e-6:
                cov[i][i] = 1e-6
                floored += 1
            for j in range(k):
                if i != j:
                    cov[i][j] = cov[i][j] + (1.0 / nbar)
        # re-symmetrise after the off-diagonal correction
        cov = [[(cov[i][j] + cov[j][i]) / 2 for j in range(k)] for i in range(k)]
    corr = [[cov[i][j] / math.sqrt(cov[i][i] * cov[j][j]) if cov[i][i] > 0 and cov[j][j] > 0 else 0.0
             for j in range(k)] for i in range(k)]
    pos = [(slots[i], slots[j], round(corr[i][j], 4))
           for i in range(k) for j in range(i + 1, k) if cov[i][j] > 0]
    return {
        'n_compositions': n, 'slots': list(slots),
        'clr_mean': [round(x, 5) for x in mu],
        'clr_covariance': [[round(v, 6) for v in row] for row in cov],
        'clr_correlation': [[round(v, 4) for v in row] for row in corr],
        'positive_pairs': sorted(pos, key=lambda t: -t[2]),
        'n_positive_off_diagonal': len(pos),
        'n_off_diagonal': k * (k - 1) // 2,
        'sampling_noise_deconvolved': bool(sample_sizes),
        'n_diagonals_floored_after_deconvolution': floored,
        'identified_slots': identified,
        'unidentified_slots': ([s for s in slots if s not in (identified or [])]
                               if identified is not None else None),
        'IDENTIFIABILITY_RULE': (f'a slot is modelled only where its observed CLR variance exceeds '
                                 f'{IDENTIFIABILITY_MULTIPLE}x the multinomial sampling variance. '
                                 f'Below that the latent covariance is not identified at this '
                                 f'sample and the slot is left to the unmodelled remainder.'),
        'DIRICHLET_WOULD_FORCE': ('every one of these off-diagonals to be negative, so the positive '
                                  'pairs listed above are not representable by any concentration'),
    }


def cholesky(cov, jitter=1e-9):
    """Lower-triangular factor, with jitter added until the matrix is positive definite.

    A sample covariance can be numerically indefinite in its smallest directions, and a silent
    failure here would produce shares drawn from something that is not the measured distribution.
    So the jitter is escalated explicitly and the amount used is reported.
    """
    k = len(cov)
    for attempt in range(12):
        eps = jitter * (10 ** attempt)
        a = [[cov[i][j] + (eps if i == j else 0.0) for j in range(k)] for i in range(k)]
        L = [[0.0] * k for _ in range(k)]
        ok = True
        for i in range(k):
            for j in range(i + 1):
                s = sum(L[i][m] * L[j][m] for m in range(j))
                if i == j:
                    d = a[i][i] - s
                    if d <= 0:
                        ok = False
                        break
                    L[i][j] = math.sqrt(d)
                else:
                    L[i][j] = (a[i][j] - s) / L[j][j]
            if not ok:
                break
        if ok:
            return L, eps
    return None, None


class ShareModel:
    """Draws a slot-level multiplicative shock with the measured covariance."""

    def __init__(self, art: dict):
        self.by_field = {}
        for field, d in art['fields'].items():
            keep = d.get('identified_slots') or d['slots']
            idx = [i for i, s in enumerate(d['slots']) if s in keep]
            if len(idx) < 2:
                continue
            sub = [[d['clr_covariance'][i][j] for j in idx] for i in idx]
            L, eps = cholesky(sub)
            if L is None:
                continue
            self.by_field[field] = {'slots': [d['slots'][i] for i in idx], 'L': L, 'jitter': eps,
                                    'unmodelled': [s for s in d['slots'] if s not in keep]}

    @classmethod
    def load(cls) -> Outcome:
        if not OUT.exists():
            return Outcome.blocked('SHARE_COVARIANCE_ABSENT', 'SHARE_COVARIANCE.json missing',
                                   cause=Cause.DATA)
        art = json.loads(OUT.read_text())
        m = cls(art)
        missing = [f for f in art['fields'] if f not in m.by_field]
        if missing:
            return Outcome.fail('SHARE_COVARIANCE_NOT_FACTORABLE',
                                f'no positive-definite factor for {missing}', missing=missing)
        return Outcome.ok('SHARE_MODEL_LOADED', value=m)

    def shock(self, field, rng) -> dict:
        """One draw of exp(e) per slot. Multiply a pregame share by its slot's value."""
        d = self.by_field.get(field)
        if d is None:
            return {}
        k = len(d['slots'])
        z = [rng.gauss(0.0, 1.0) for _ in range(k)]
        e = [sum(d['L'][i][j] * z[j] for j in range(i + 1)) for i in range(k)]
        return {s: math.exp(v) for s, v in zip(d['slots'], e)}


def build() -> Outcome:
    if not PG.exists() or not RH.exists():
        return Outcome.blocked('SHARE_INPUTS_ABSENT', 'player-game or role-history missing',
                               cause=Cause.DATA)
    pg, rh = _rows(PG), _rows(RH)
    rank = {}
    for r in rh:
        if RANK_MEASURE.get(r.get('position')) != r.get('measure'):
            continue
        if isinstance(r.get('depth_rank'), (int, float)):
            rank[(int(r['season']), int(r['week']), r['player_id'])] = (r['position'],
                                                                       int(r['depth_rank']))
    by_club = collections.defaultdict(list)
    for r in pg:
        by_club[(r['game_id'], r['club'])].append(r)

    fields = {}
    for field, slots in (('targets', TARGET_SLOTS), ('carries', CARRY_SLOTS)):
        comps, sizes = _compositions(by_club, rank, field, slots)
        if len(comps) < MIN_COMPOSITIONS:
            fields[field] = {'state': 'NOT_IDENTIFIED_TOO_FEW', 'n': len(comps)}
            continue
        fields[field] = {'state': 'MEASURED', **_clr_moments(comps, slots, sizes)}
    art = {
        'ARTIFACT': 'SHARE_COVARIANCE',
        'FAMILY': 'logistic-normal: s = softmax(log w + e), e ~ MVN(0, Sigma)',
        'WHY_NOT_DIRICHLET': ('a Dirichlet forces cov(s_i, s_j) negative for every pair, with only '
                              'the magnitude free. Measured target shares co-move positively for '
                              'receivers, so no concentration fits them.'),
        'CHART': ('covariance estimated in centred-log-ratio space, the standard chart for '
                  'compositional data, then applied as a multiplicative slot shock'),
        'RANKS_ARE_PREGAME': 'slots come from the role table, never from the stat line measured',
        'fields': {k: v for k, v in fields.items() if v.get('state') == 'MEASURED'},
        'refused': {k: v for k, v in fields.items() if v.get('state') != 'MEASURED'},
    }
    OUT.write_text(json.dumps(art, indent=2))
    if not art['fields']:
        return Outcome.fail('SHARE_COVARIANCE_NOT_IDENTIFIED', 'no field could be estimated',
                            refused=art['refused'])
    return Outcome.ok('SHARE_COVARIANCE_MEASURED', value=art)


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code)
    v = o.value if o.value else o.evidence
    for f, d in (v.get('fields') or {}).items():
        print(f"  {f}: {d['n_compositions']} compositions, "
              f"{d['n_positive_off_diagonal']} of {d['n_off_diagonal']} off-diagonals POSITIVE")
        for a, b, r in d['positive_pairs'][:5]:
            print(f'     {a:>5s} ~ {b:<6s} {r:+.4f}')
    m = ShareModel.load()
    print('  factorable:', m.state.value, m.code)
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
