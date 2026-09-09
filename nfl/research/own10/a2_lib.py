"""OWN-10: A2, the chartered dependence refinement. Research only.

A2(tau) is A1 with one additional term and nothing else changed: a per-team-game
per-draw latent on the designed-QB share, independent of the budget, the
dropbacks and every other category.

    u ~ Normal(0, tau)
    p_designed_qb = max(centre + residual + u, 0)

then normalised across the six categories exactly as A1 normalises, and
partitioned by the same multinomial over the same rush_play_budget. The latent
moves a probability; it cannot move a carry, so closure is structurally
untouched.

tau = 0 reproduces A1 EXACTLY, draw for draw, when the RNG is consumed in the
same order. That is the point: the grid contains its own null, so "A2 does not
help" and "A1 is A2 at tau = 0" are the same statement rather than two.
"""
from __future__ import annotations

import numpy as np

import a1_lib as A

CATEGORIES = A.CATEGORIES
EPS = A.EPS
TAU_GRID = (0.0, 0.0025, 0.005, 0.01, 0.02, 0.04)
_QB = CATEGORIES.index('designed_qb')


def draw_a2(r, par, rng, m, tau):
    """One per-draw partition of the same rush-play budget, with the latent.

    Returns (counts, degenerate, floor_binds). `floor_binds` counts the
    share-floor activations so that the "no clipping" gate is a measurement.
    A share floor cannot move a carry -- only a probability -- but it is
    counted for both arms rather than asserted away.
    """
    budget = int(r['rush_play_budget'])
    p = np.empty((len(CATEGORIES), m), np.float64)
    floor = 0
    for j, cat in enumerate(CATEGORIES):
        c = A._centre(r, cat, par)
        pool = par['resid'].get(cat)
        add = (pool[rng.integers(0, len(pool), m)] if pool is not None
               and len(pool) else np.zeros(m, np.float32))
        raw = c + add
        if j == _QB and tau > 0.0:
            # DRAWN AFTER the residual so that tau = 0 consumes the RNG in
            # exactly A1's order and reproduces A1 draw for draw.
            raw = raw + rng.normal(0.0, tau, m)
        floor += int((raw < 0.0).sum())
        p[j] = np.maximum(raw, 0.0)
    tot = p.sum(0)
    degenerate = tot <= EPS
    p[:, degenerate] = 0.0
    p[CATEGORIES.index('fringe'), degenerate] = 1.0
    tot = np.where(degenerate, 1.0, tot)
    p = p / tot
    out = np.empty((len(CATEGORIES), m), np.int64)
    for j in range(m):
        out[:, j] = rng.multinomial(budget, p[:, j])
    return ({cat: out[j] for j, cat in enumerate(CATEGORIES)},
            int(degenerate.sum()), floor)
