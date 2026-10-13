#!/usr/bin/env python3.12
"""Runs only against a proj_v1.py patched by patch_projfix1.py (the change was REJECTED and is not in production).
PROJ-FIX-1 (PREREG_PROJFIX1_ZERO_CLAIM.md): with NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE=1 a MEASURED zero claim takes no volume
in that field, a MISSING claim keeps the half-depth fallback, and every club identity still holds. Unset, the allocation is
byte-identical to the incumbent, and the incumbent's defect (a zero-claim tight end handed carries) is replayed."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import proj_v1 as PV  # noqa: E402

TV = {'proj_targets': 35.0, 'proj_rush_attempts': 25.0, 'proj_pass_attempts': 35.0}
GROUPS = {'targets': {'RB': 0.2, 'TE': 0.8}, 'carries': {'RB': 0.9, 'TE': 0.1}}


def _rows():
    spec = [('RB', 'RB0', {'targets': 0.10, 'carries': 0.60}, 1, True),
            ('RB', 'RB1', {'targets': 0.05, 'carries': 0.30}, 2, False),
            ('TE', 'TE0', {'targets': 0.20, 'carries': 0.0}, 1, True),     # measured: never carries (Kincaid's shape)
            ('TE', 'TE1', {'targets': 0.05}, 2, False)]                   # carry claim MISSING (None)
    return [{'position': p, '_dk': k, '_claims': c, 'role_band': 'ROTATIONAL', 'is_predicted_starter': s,
             '_chart_rank': ch} for p, k, c, ch, s in spec]


def _depth():
    return {pos: {'by_rank': {f'rank_{k}': {'unconditional_expected_share': 0.5 / k, 'appearance_rate': 1.0 / k}
                              for k in range(1, 7)}} for pos in ('RB', 'TE')}


def _alloc(flag):
    old = os.environ.pop('NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE', None)
    try:
        if flag is not None:
            os.environ['NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE'] = flag
        rows = _rows()
        out = PV.allocate_opportunity(rows, dict(TV), copy.deepcopy(_depth()), copy.deepcopy(GROUPS))
        return rows, out
    finally:
        os.environ.pop('NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE', None)
        if old is not None:
            os.environ['NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE'] = old


def _by(rows, field):
    return {r['_dk']: r.get(field) or 0.0 for r in rows}


def test_default_is_byte_identical_and_replays_the_defect():
    a, oa = _alloc(None)
    b, ob = _alloc('0')
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    assert json.dumps(oa, sort_keys=True, default=str) == json.dumps(ob, sort_keys=True, default=str)
    assert _by(a, 'carries')['TE0'] > 0, 'the incumbent hands a measured-zero tight end carries (the logged defect)'


def test_measured_zero_takes_nothing_missing_keeps_fallback_identities_hold():
    rows, _ = _alloc('1')
    c, t = _by(rows, 'carries'), _by(rows, 'targets')
    assert c['TE0'] == 0.0, c
    assert c['TE1'] > 0, 'a MISSING claim keeps the half-depth fallback'
    assert abs(sum(c.values()) - TV['proj_rush_attempts']) < 1e-6, c
    assert abs(sum(t.values()) - TV['proj_targets']) < 1e-6, t
    base, _ = _alloc(None)
    assert _by(rows, 'targets') == _by(base, 'targets'), 'no zero claim in targets, so targets are unchanged'
    assert c['RB0'] > _by(base, 'carries')['RB0'], 'the freed carries go back to the measured claimants'


if __name__ == '__main__':
    test_default_is_byte_identical_and_replays_the_defect()
    test_measured_zero_takes_nothing_missing_keeps_fallback_identities_hold()
    print('PASS')
