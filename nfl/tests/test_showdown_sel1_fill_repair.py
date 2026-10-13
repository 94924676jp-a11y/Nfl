#!/usr/bin/env python3.12
"""SEL-1 fill repair (PREREG_SEL1_FILL_REPAIR.md): a greedy shortfall at a rung is repaired by single exchanges before the
ladder relaxes. Every repaired portfolio is lawful (size, caps, overlap, exclusions) and never relaxes further than greedy;
the default selector is unchanged; an unknown selector refuses."""
from __future__ import annotations

import collections
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_portfolio as SP  # noqa: E402


def _fixture(seed, n_c=300, n_w=400, n_p=14):
    rng = np.random.default_rng(seed)
    seats_of = [list(rng.choice(n_p, 6, replace=False)) for _ in range(n_c)]
    q = rng.uniform(0.02, 0.25, n_c)
    hit = rng.random((n_c, n_w)) < q[:, None]
    rows = [{'first_place_proxy': float(hit[i].mean()), 'structural_duplication_index': 0.0} for i in range(n_c)]
    return hit, rows, seats_of, n_w


def _lawful(P, seats_of, n, exclude):
    ch = P['chosen']
    assert len(ch) == n and len(set(ch)) == n, 'size / distinct'
    assert not (set(ch) & set(exclude)), 'exclusion'
    exp = collections.Counter(k for j in ch for k in seats_of[j])
    cexp = collections.Counter(seats_of[j][0] for j in ch)
    assert max(exp.values()) <= P['caps']['player'] and max(cexp.values()) <= P['caps']['captain'], 'caps'
    sets = [set(seats_of[j]) for j in ch]
    assert all(len(a & b) <= P['caps']['overlap'] for i, a in enumerate(sets) for b in sets[i + 1:]), 'overlap'


def _run(sel, hit, rows, seats_of, n, n_w, exclude=frozenset()):
    old = os.environ.pop('NFL_SHOWDOWN_SELECTOR', None)
    try:
        if sel:
            os.environ['NFL_SHOWDOWN_SELECTOR'] = sel
        return SP.ladder(hit, rows, seats_of, n, n_w, exclude)
    finally:
        os.environ.pop('NFL_SHOWDOWN_SELECTOR', None)
        if old is not None:
            os.environ['NFL_SHOWDOWN_SELECTOR'] = old


def test_repair_is_lawful_never_relaxes_more_and_completes_some_greedy_shortfall():
    completed_at_stricter = 0
    for seed in range(40):
        hit, rows, seats_of, n_w = _fixture(seed)
        excl = frozenset(range(0, 300, 37))
        G, _ = _run(None, hit, rows, seats_of, 20, n_w, excl)
        R, log = _run('FILL_REPAIR_V1', hit, rows, seats_of, 20, n_w, excl)
        if R['short'] == 0:
            _lawful(R, seats_of, 20, excl)
        assert R['relaxation_level'] <= G['relaxation_level'], (seed, R['relaxation_level'], G['relaxation_level'])
        if R['relaxation_level'] < G['relaxation_level']:
            completed_at_stricter += 1
            assert any(x.get('repair') == 'COMPLETED' for x in log)
    assert completed_at_stricter > 0, 'fixture never exercised a greedy shortfall that a repair completes'


def test_default_unchanged_and_unknown_selector_refuses():
    hit, rows, seats_of, n_w = _fixture(3)
    a, la = _run(None, hit, rows, seats_of, 20, n_w)
    b, lb = _run('GREEDY', hit, rows, seats_of, 20, n_w)
    assert a['chosen'] == b['chosen'] and la == lb and 'repair' not in a
    try:
        _run('FILL', hit, rows, seats_of, 20, n_w)
        raise AssertionError('an unknown selector must refuse')
    except ValueError:
        pass


if __name__ == '__main__':
    test_repair_is_lawful_never_relaxes_more_and_completes_some_greedy_shortfall()
    test_default_unchanged_and_unknown_selector_refuses()
    print('PASS')
