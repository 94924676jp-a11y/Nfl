#!/usr/bin/env python3.12
"""Contests of one profile get different lineups (task #45 P0-4, owner contract 2026-10-11 clause 6).

On 2026-10-11 the two 20-entry contests (196461815, 196461816) received the same 20 lineups: classic_portfolio cached
one candidate set per pool and ran the same deterministic select() for each contest. select_group() now selects
same-profile contests together, round-robin, so a lineup chosen for one is unavailable to the other.

What is proven here:
  1. With ONE contest the new selector is the old one: a verbatim copy of the pre-change select() (HEAD a64e932f)
     and the new select() choose identical lineups on 40 random synthetic pools.
  2. Two contests of one profile share no lineup, both fill, and each respects its own exposure caps.
  3. A pool too small for both is reported as a short contest, never filled by duplicating a lineup.
"""
from __future__ import annotations

import collections
import pathlib
import random
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import classic_portfolio as P  # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _old_select(cands, ids, M, meta, n, prof):
    """VERBATIM copy of classic_portfolio.select at a64e932f, kept as the reference the new code must reproduce."""
    col = {dk: i for i, dk in enumerate(ids)}
    S_ = np.stack([M[[col[d] for d in c]].sum(0) for c in cands])
    T = np.quantile(S_, 1 - prof['q'], axis=0)
    best = np.full(M.shape[1], -np.inf)
    chosen, expo = [], collections.Counter()
    for _ in range(n):
        top, top_gain = None, -1.0
        for j, c in enumerate(cands):
            if j in chosen:
                continue
            ok = True
            for d in c:
                cap = (prof['qb_exposure_cap'] if meta[d]['pos'] == 'QB' else
                       prof['dst_exposure_cap'] if meta[d]['pos'] == 'DST' else prof['exposure_cap'])
                if (expo[d] + 1) > max(1, int(cap * n + 1e-9)):
                    ok = False
                    break
            if not ok or any(len(c & cands[i]) > prof['max_shared'] for i in chosen):
                continue
            gain = float(np.maximum(np.maximum(best, S_[j]) - T, 0).mean()
                         - np.maximum(best - T, 0).mean()) if chosen else float(np.maximum(S_[j] - T, 0).mean())
            gain += 1e-6 * float(S_[j].mean())
            if gain > top_gain:
                top, top_gain = j, gain
        if top is None:
            break
        chosen.append(top)
        best = np.maximum(best, S_[top])
        expo.update(cands[top])
    return chosen, S_, T


def _pool(seed, n_players=40, n_worlds=200, n_cands=120):
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    pos = ['QB'] * 4 + ['DST'] * 4 + ['RB'] * 10 + ['WR'] * 14 + ['TE'] * 8
    ids = [str(1000 + i) for i in range(n_players)]
    meta = {d: {'pos': pos[i]} for i, d in enumerate(ids)}
    M = nprng.gamma(2.0, 6.0, size=(n_players, n_worlds))
    by = collections.defaultdict(list)
    for d in ids:
        by[meta[d]['pos']].append(d)
    cands = []
    while len(cands) < n_cands:
        lu = frozenset([rng.choice(by['QB']), rng.choice(by['DST']), rng.choice(by['TE'])]
                       + rng.sample(by['RB'], 2) + rng.sample(by['WR'], 4))
        if lu not in cands:
            cands.append(lu)
    return ids, M, meta, cands


def test_01_one_contest_is_the_old_selector():
    print('\n01. one contest: identical choices to the pre-change selector on 40 random pools')
    diffs = []
    for seed in range(40):
        ids, M, meta, cands = _pool(seed)
        for prof_name, n in (('MAX150', 30), ('MAX20', 20)):
            prof = P.PROFILES[prof_name]
            a, _, _ = _old_select(cands, ids, M, meta, n, prof)
            b, _, _ = P.select(cands, ids, M, meta, n, prof)
            if a != b:
                diffs.append((seed, prof_name, a[:5], b[:5]))
    check('80 of 80 selections identical (same lineups, same order)', not diffs, diffs[:3])


def test_02_two_contests_of_one_profile_share_nothing():
    print('\n02. two 20-entry contests selected together share no lineup and each obeys its own caps')
    shared, short, cap_breach = [], [], []
    prof = P.PROFILES['MAX20']
    for seed in range(20):
        ids, M, meta, cands = _pool(seed, n_cands=200)
        (a, b), _, _ = P.select_group(cands, ids, M, meta, [20, 20], prof)
        if set(a) & set(b):
            shared.append(seed)
        if len(a) != 20 or len(b) != 20:
            short.append((seed, len(a), len(b)))
        for ch in (a, b):
            expo = collections.Counter(d for j in ch for d in cands[j])
            for d, k in expo.items():
                cap = (prof['qb_exposure_cap'] if meta[d]['pos'] == 'QB' else
                       prof['dst_exposure_cap'] if meta[d]['pos'] == 'DST' else prof['exposure_cap'])
                if k > max(1, int(cap * 20 + 1e-9)):
                    cap_breach.append((seed, d, k))
    check('no shared lineup in 20 of 20 pools', not shared, shared)
    check('both contests fill 20 of 20', not short, short)
    check('each contest respects its own exposure caps', not cap_breach, cap_breach[:3])
    ids, M, meta, cands = _pool(3, n_cands=200)
    (a, b), _, _ = P.select_group(cands, ids, M, meta, [20, 20], prof)
    solo, _, _ = P.select(cands, ids, M, meta, 20, prof)
    check('the first contest still gets the lineup the solo selector would pick first', a[0] == solo[0], (a[0], solo[0]))
    check('negative control: running select() twice on the same pool repeats every lineup (the old defect)',
          P.select(cands, ids, M, meta, 20, prof)[0] == solo)


def test_03_a_short_pool_is_reported_short_never_duplicated():
    print('\n03. too few candidates for both contests: the second is short, nothing is duplicated')
    ids, M, meta, cands = _pool(5, n_cands=25)
    prof = dict(P.PROFILES['MAX20'], exposure_cap=1.0, qb_exposure_cap=1.0, dst_exposure_cap=1.0, max_shared=9)
    (a, b), _, _ = P.select_group(cands, ids, M, meta, [20, 20], prof)
    check('together they use at most the 25 candidates there are', len(a) + len(b) <= 25, (len(a), len(b)))
    check('no lineup appears in both', not set(a) & set(b))
    check('at least one contest is short, which build() reports as not FILLED',
          len(a) < 20 or len(b) < 20, (len(a), len(b)))


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    assert FAILED == 0, f'{FAILED} check(s) failed'


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
