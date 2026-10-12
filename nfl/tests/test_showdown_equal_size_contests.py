#!/usr/bin/env python3.12
"""Equal-size Showdown contests do not share lineups by default (owner contract #45 clause 6; owner ruling 2026-10-12:
keep zero overlap in production, test overlap in shadow). 2026-10-12 BUF@LAR precompute R4 built the two 20-entry
contests from identical inputs and they came out identical, 20 of 20."""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_portfolio as SP  # noqa: E402


def _fixture(n_c=400, n_w=600, n_p=24, seed=7):
    rng = np.random.default_rng(seed)
    seats_of = [list(rng.choice(n_p, 6, replace=False)) for _ in range(n_c)]
    q = rng.uniform(0.02, 0.2, n_c)
    hit = rng.random((n_c, n_w)) < q[:, None]
    cand_rows = [{'first_place_proxy': float(hit[i].mean()), 'structural_duplication_index': 0.0} for i in range(n_c)]
    def c(name, n):
        return {'name': name, 'fee': '$0.25', 'entries': [{'entry_id': f'{name}{i}'} for i in range(n)]}
    contests = {'DIME': c('NFL Showdown $5K Dime Package', 20), 'JUKE': c('NFL Showdown $10K Quarter Jukebox', 20),
                'MAX': c('NFL Showdown $100K mini-MAX [150 Entry Max]', 150)}
    return hit, cand_rows, seats_of, contests, n_w


def test_equal_size_contests_share_no_lineup_and_the_shadow_records_the_cost():
    hit, cand_rows, seats_of, contests, n_w = _fixture()
    P = SP.build_contests(hit, cand_rows, seats_of, contests, n_w)
    assert list(P) == list(contests), 'the result keeps the contests\' own order'
    j, d, m = (set(P[k]['chosen']) for k in ('JUKE', 'DIME', 'MAX'))
    assert len(j) == 20 and len(d) == 20 and len(m) == 150
    assert not (j & d), f'the two 20-entry contests share {len(j & d)} lineup(s)'
    pol = P['DIME']['overlap_policy']
    assert pol['build_order'][:2] == ['MAX', 'JUKE'], f'size then prize pool: {pol["build_order"]}'
    assert P['JUKE']['overlap_policy']['shadow'] is None and pol['excluded_n'] == 20
    sh = pol['shadow']
    assert sh['arm'] == 'SHADOW_OVERLAP_ALLOWED' and sh['shared_with_earlier_equal_size'] > 0, sh
    assert sh['objective_cost_of_exclusion'] >= -1e-9, 'the unrestricted build cannot score below the restricted one'
    # a contest of a different size is never restricted by another size's lineups
    assert P['MAX']['overlap_policy']['excluded_n'] == 0


def test_default_policy_lets_different_sizes_overlap_and_global_policy_forbids_it(monkeypatch=None):
    """The default (EQUAL_SIZE) is unchanged: the 150 may share lineups with a 20. Opt-in GLOBAL: 190 distinct, and the
    shadow records what the exclusion cost each later contest. An unknown policy refuses rather than falling back."""
    import os
    hit, cand_rows, seats_of, contests, n_w = _fixture()
    old = os.environ.pop('NFL_SHOWDOWN_OVERLAP_POLICY', None)
    try:
        D = SP.build_contests(hit, cand_rows, seats_of, contests, n_w)
        os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'] = 'GLOBAL'
        G = SP.build_contests(hit, cand_rows, seats_of, contests, n_w)
        os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'] = 'EQUAL'
        try:
            SP.build_contests(hit, cand_rows, seats_of, contests, n_w)
            raise AssertionError('an unknown overlap policy must refuse')
        except ValueError:
            pass
    finally:
        os.environ.pop('NFL_SHOWDOWN_OVERLAP_POLICY', None)
        if old is not None:
            os.environ['NFL_SHOWDOWN_OVERLAP_POLICY'] = old
    dm, dj = set(D['MAX']['chosen']), set(D['JUKE']['chosen'])
    assert dm & dj, 'fixture must exercise the default cross-size overlap (else the GLOBAL check proves nothing)'
    assert D['JUKE']['overlap_policy']['rule'] == 'EXCLUDE_LINEUPS_OF_EARLIER_EQUAL_SIZE_CONTESTS'
    gm, gj, gd = (set(G[k]['chosen']) for k in ('MAX', 'JUKE', 'DIME'))
    assert len(gm | gj | gd) == 190, f'GLOBAL must give 190 distinct lineups, got {len(gm | gj | gd)}'
    assert G['MAX']['chosen'] == D['MAX']['chosen'], 'the first-built contest is unaffected by the policy'
    assert G['JUKE']['overlap_policy']['rule'] == 'EXCLUDE_LINEUPS_OF_EVERY_EARLIER_CONTEST'
    assert G['JUKE']['overlap_policy']['excluded_n'] == 150 and G['DIME']['overlap_policy']['excluded_n'] == 170
    assert G['JUKE']['overlap_policy']['shadow']['objective_cost_of_exclusion'] >= -1e-9


if __name__ == '__main__':
    test_equal_size_contests_share_no_lineup_and_the_shadow_records_the_cost()
    test_default_policy_lets_different_sizes_overlap_and_global_policy_forbids_it()
    print('PASS')
