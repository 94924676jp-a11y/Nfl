#!/usr/bin/env python3.12
"""The paired COMPLETE artifact can now take its five shared layers from a production seal -- and is
credited only where that seal's own verdict allows. Forced both ways, and on the real DET_BUF R9 seal.
"""
from __future__ import annotations

import glob
import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.prospective.q9shadow import complete as C  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []
DETBUF = pathlib.Path(glob.glob(str(_REPO / 'nfl/research/live/**/117a78668a0b7a0e'), recursive=True)[0])


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


@check('the verdict parser reads the ABSENT list out of a real eligibility verdict')
def _verdict():
    art = json.loads((DETBUF / 'forecast_artifact.json').read_text())
    a = C._verdict_absent(art)
    assert {'appearance', 'participation', 'targets_carries', 'td_layer'} <= a, a
    assert C._verdict_absent({'eligibility_verdict': 'X|PRODUCED:all'}) == set()
    return f'DET_BUF R9 absent: {sorted(a)}'


@check('REAL SEAL: DET_BUF R9 credits team_volume and the three QB layers, refuses carries BY NAME')
def _real_seal():
    o = C.shared_layers_from_seal(DETBUF)
    assert o.state is State.PASS, o
    st = o.value['states']
    assert st['team_volume'] == 'PASS' and st['qb_attempts'] == 'PASS' \
        and st['qb_passing_yards'] == 'PASS' and st['qb_td'] == 'PASS', st
    assert st['carries'] == 'BLOCKED:PRODUCTION_LAYER_ABSENT:targets_carries', st
    return f"{o.detail}; carries -> {st['carries']}"


@check('a matrix present on disk is NOT credited when the verdict says the producing layer was absent')
def _verdict_beats_matrix():
    man = json.loads((DETBUF / 'player_draws_manifest.json').read_text())
    assert 'carries' in (man['layers']['rushing']['metrics'] or []), 'fixture changed'
    o = C.shared_layers_from_seal(DETBUF)
    assert o.value['states']['carries'].startswith('BLOCKED:PRODUCTION_LAYER_ABSENT'), o.value['states']
    return 'rushing/carries matrix exists in the manifest; still BLOCKED because targets_carries is ABSENT'


def _synthetic(tmp, verdict='V|PRODUCED:qb_layer,targets_carries|ABSENT:', drop_layer=None):
    layers = {'team_volume': {'metrics': ['team_off_snaps', 'team_dropbacks_part'], 'row_ids': ['A', 'B']},
              'qb': {'metrics': ['att', 'pyds', 'ptd'], 'row_ids': ['00-1']},
              'rushing': {'metrics': ['carries', 'rushing_td'], 'row_ids': ['00-2']}}
    if drop_layer:
        layers.pop(drop_layer)
    (tmp / 'player_draws_manifest.json').write_text(json.dumps({'layers': layers, 'content_digest': 'abc'}))
    (tmp / 'forecast_artifact.json').write_text(json.dumps({'game_id': '2026_09_X_Y',
                                                             'eligibility_verdict': verdict}))
    return tmp


@check('a complete production seal credits all five shared layers')
def _all_five():
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        o = C.shared_layers_from_seal(_synthetic(tmp))
        assert o.state is State.PASS and all(v == 'PASS' for v in o.value['states'].values()), o.value['states']
        return f"{o.detail}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check('a seal missing a layer refuses that layer by name; a seal missing its files is refused outright')
def _missing():
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        o = C.shared_layers_from_seal(_synthetic(tmp, drop_layer='qb'))
        assert o.value['states']['qb_attempts'] == 'BLOCKED:SEAL_LAYER_ABSENT:qb', o.value['states']
        assert o.value['states']['carries'] == 'PASS'
        for f in tmp.iterdir():
            f.unlink()
        e = C.shared_layers_from_seal(tmp)
        assert e.state is State.BLOCKED and e.code == 'SHARED_SEAL_INCOMPLETE', e
        return 'qb absent -> BLOCKED:SEAL_LAYER_ABSENT:qb; empty dir -> SHARED_SEAL_INCOMPLETE'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check('COMPLETENESS: all-PASS shared + all-PASS arms reads COMPLETE; the DET_BUF states read PARTIAL')
def _completeness():
    import numpy as np
    arms = {a: {'targets': np.ones((2, 3)), 'receptions': np.ones((2, 3)),
                'receiving_yards': np.ones((2, 3)), 'receiving_td': np.ones((2, 3))}
            for a in ('A', 'B')}
    full = {k: 'PASS' for k in C.SHARED_LAYER_REQUIREMENTS}
    v1, verdict1 = C.completeness_value(C.matrix(arms, full))
    st = C.shared_layers_from_seal(DETBUF).value['states']
    v2, verdict2 = C.completeness_value(C.matrix(arms, st))
    assert v1 == C.CONTRACT_COMPLETE, (v1, verdict1)
    assert v2 == C.CONTRACT_PARTIAL, (v2, verdict2)
    return f'all PASS -> {v1} ({verdict1}); DET_BUF shared states -> {v2} ({verdict2})'


@check('the partition still covers exactly the nine required layers')
def _partition():
    o = C.assert_partition_covers_required()
    assert o.state is State.PASS, o
    assert set(C.SHARED_LAYER_REQUIREMENTS) == set(C.SHARED_LAYERS), (sorted(C.SHARED_LAYER_REQUIREMENTS), sorted(C.SHARED_LAYERS))
    return o.detail


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
