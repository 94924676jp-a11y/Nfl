"""The stored digest reproduces from the stored bytes, and moves for one cell.

TWO THINGS THAT ARE NOT THE SAME, AND THIS FILE ONLY DOES THE FIRST

  ARTIFACT HASH CONSISTENCY  the digest written into the manifest is the digest
                             of the draws sitting next to it. Cheap, and it
                             catches a manifest that has drifted from its own
                             payload.
  REPLAY DETERMINISM         running the forecast twice from the same pinned
                             evidence produces the same draws. Requires two
                             full runs and is NOT established by anything here.

Conflating them would let "the hash checks out" stand in for "the run
reproduces", which is the stronger claim and the one nobody has evidence for.
`nfl/tools/determinism_proof.py` is the tool for the second; it needs
--out-root-a and --out-root-b and two executions.

Measured 2026-09-25 on the 2026_03_ATL_GB artifact: declared and recomputed
digests are identical, recomputation is stable, and perturbing ONE cell by
1e-9 changes it.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import draws_artifact as DA                # noqa: E402

PASSED = 0
FAILED = 0
BLOCKED = 0

_ART = _REPO / 'nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  blocked {label}: {why}')


def _digest(arrays: dict, layers: dict) -> str:
    h = hashlib.sha256()
    h.update(DA.DRAW_ARTIFACT_VERSION.encode())
    for key in sorted(arrays):
        a = arrays[key]
        h.update(b'\x00' + key.encode() + b'\x00')
        h.update(json.dumps(list(a.shape)).encode())
        h.update(DA._canonical_bytes(a))
    for layer in sorted(layers):
        h.update(b'\x01' + layer.encode() + b'\x00')
        h.update(json.dumps(layers[layer]['row_ids']).encode())
    return h.hexdigest()


def _load():
    man = json.loads((_ART / 'player_draws_manifest.json').read_text())
    z = np.load(_ART / 'player_draws.npz', allow_pickle=True)
    arrays = {k.replace('__', '/', 1): z[k] for k in z.files}
    layers = {k: {'row_ids': v.get('row_ids') or []}
              for k, v in man['layers'].items()}
    return man, arrays, layers


def test_A_declared_digest_reproduces():
    print('\nA. the manifest agrees with the payload beside it')
    if not (_ART / 'player_draws_manifest.json').exists():
        blocked('artifact present', f'{_ART} absent')
        return
    man, arrays, layers = _load()
    check('artifact version matches the module',
          man.get('draw_artifact_version') == DA.DRAW_ARTIFACT_VERSION,
          f"{man.get('draw_artifact_version')} vs {DA.DRAW_ARTIFACT_VERSION}")
    rec = _digest(arrays, layers)
    check('declared content_digest reproduces exactly',
          rec == man.get('content_digest'),
          f"declared {man.get('content_digest')} recomputed {rec}")
    check('and recomputation is stable', _digest(arrays, layers) == rec)


def test_B_one_altered_cell_moves_it():
    print('\nB. a digest that survives a changed draw is not an identity')
    if not (_ART / 'player_draws_manifest.json').exists():
        blocked('artifact present', f'{_ART} absent')
        return
    _man, arrays, layers = _load()
    base = _digest(arrays, layers)
    tampered = dict(arrays)
    a = np.array(arrays['dk_scoring/dk_points'], dtype=np.float64, copy=True)
    a[0, 0] += 1e-9
    tampered['dk_scoring/dk_points'] = a
    check('perturbing one cell by 1e-9 changes the digest',
          _digest(tampered, layers) != base)
    dropped = {k: v for k, v in arrays.items() if k != 'kicking/dk_points'}
    check('dropping a whole layer changes the digest',
          _digest(dropped, layers) != base)


def test_C_replay_determinism_is_not_claimed_here():
    print('\nC. what this file does NOT establish')
    blocked('replay determinism',
            'needs two full runs from the same pinned evidence via '
            'nfl/tools/determinism_proof.py --out-root-a/--out-root-b. Hash '
            'consistency is not replay determinism and must not be reported '
            'as it.')
