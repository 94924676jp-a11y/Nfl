"""Hash what the guard certified; verify it again at the seal.

THE FAILURE CLASS, NAMED BY THE REPOSITORY ITSELF. Commit `8c81079`, the most
recent change to `draw_coherence.py`, is titled:

    "The guard ran, then the values it guarded were overwritten."

That is an ORDER-OF-OPERATIONS gap between certification and publication, not a
missing guard. A conservation suite that runs before the last mutation of the
data it certifies is not a conservation suite; it is a statement about an
intermediate state nobody ships. Every accounting check can pass and the
published board still be incoherent, because each check looks at the array at
the moment it runs.

TWO MUTATION SHAPES, AND ONLY ONE IS OBVIOUS. A downstream stage can mutate an
array IN PLACE, or it can REPLACE the entry with a different object. A digest
taken at guard time catches the first automatically, because the digest is a
snapshot and the array is live. It catches the second only if verification
re-reads from the mapping that is actually published rather than from the
references the guard happened to hold. **So `verify` takes the publication-time
arrays, and the test proves both shapes are caught.**

WHAT IS AND IS NOT NORMALISED
  * dtype and C-contiguity are pinned, because the same numbers in a different
    memory layout hash differently and that is a false alarm, not a mutation.
  * `-0.0` is normalised to `0.0`. It is bitwise distinct and numerically
    identical, so leaving it would raise on a difference that is not a change.
  * NaN is COUNTED rather than normalised. Two NaNs never compare equal, and a
    silent hash difference must not be how anyone learns one appeared.
  * Row ids are inside the digest. A permutation that preserves the bytes but
    changes whose row is whose is a real defect, not a reordering.
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

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'coherence-certificate-1'

CODE_CERTIFIED = 'COHERENCE_CERTIFIED'
CODE_VERIFIED = 'COHERENCE_CERTIFICATE_VERIFIED'
CODE_BROKEN = 'COHERENCE_CERTIFICATE_BROKEN'
CODE_MISSING = 'COHERENCE_CERTIFICATE_MISSING'
CODE_EMPTY = 'COHERENCE_CERTIFICATE_EMPTY'


def digest(a, row_ids=None) -> dict:
    """One array's fingerprint. Values, shape and identity, in that order."""
    x = np.ascontiguousarray(np.asarray(a, dtype=np.float64))
    n_nan = int(np.isnan(x).sum())
    # -0.0 -> 0.0. Bitwise distinct, numerically identical.
    x = x + 0.0
    h = hashlib.sha256()
    h.update(x.tobytes())
    h.update(json.dumps(list(x.shape)).encode())
    h.update(json.dumps(list(row_ids or [])).encode())
    return {'sha256': h.hexdigest(), 'shape': list(x.shape),
            'n_nan': n_nan, 'n_rows_declared': len(row_ids or [])}


def certify(arrays, row_ids=None, guards=None) -> Outcome:
    """Fingerprint every guarded array at the moment the guard certified it.

    `arrays` is {key: ndarray}. `row_ids` is {layer_or_key: [gsis_id, ...]}.
    `guards` names the checks whose verdict this certificate stands behind, so
    a reader can tell WHAT was certified and not merely that something was.
    """
    if not arrays:
        return Outcome.blocked(
            CODE_EMPTY,
            'nothing was handed to the certifier. An empty certificate would '
            'verify successfully against anything, which is worse than no '
            'certificate at all.', cause=Cause.GOVERNANCE)
    rid = row_ids or {}
    entries = {}
    for k in sorted(arrays):
        layer = k.split('/', 1)[0] if '/' in k else k
        entries[k] = digest(arrays[k], rid.get(k) or rid.get(layer))
    return Outcome.ok(
        CODE_CERTIFIED,
        value={'spec_version': SPEC_VERSION, 'n_arrays': len(entries),
               'entries': entries, 'guards': sorted(guards or ())},
        spec_version=SPEC_VERSION, n_arrays=len(entries),
        guards=sorted(guards or ()),
        detail=f'{len(entries)} array(s) fingerprinted at guard time')


def verify(certificate, arrays, row_ids=None) -> Outcome:
    """Re-verify at publication. REFUSES on any difference.

    `arrays` MUST be the publication-time mapping, not the references the guard
    held: re-reading is what catches a replaced entry as well as a mutated one.
    """
    if not certificate or not (certificate.get('entries') or {}):
        return Outcome.blocked(
            CODE_MISSING,
            'no coherence certificate was recorded for this run, so there is '
            'nothing to verify against. Publishing an uncertified board is '
            'the state this check exists to prevent.',
            cause=Cause.GOVERNANCE)
    rid = row_ids or {}
    entries = certificate['entries']
    changed, absent, added = [], [], []
    for k, want in sorted(entries.items()):
        if k not in arrays:
            absent.append(k)
            continue
        layer = k.split('/', 1)[0] if '/' in k else k
        got = digest(arrays[k], rid.get(k) or rid.get(layer))
        if got['sha256'] != want['sha256']:
            changed.append({'array': k,
                            'certified_sha256': want['sha256'][:16],
                            'published_sha256': got['sha256'][:16],
                            'certified_shape': want['shape'],
                            'published_shape': got['shape']})
    for k in sorted(arrays):
        if k not in entries:
            added.append(k)
    ev = {'spec_version': SPEC_VERSION,
          'n_certified': len(entries), 'n_published': len(arrays),
          'n_changed': len(changed), 'changed': changed,
          'n_absent_at_publication': len(absent), 'absent': absent,
          'n_added_after_certification': len(added), 'added': added,
          'guards': certificate.get('guards') or []}
    if changed or absent:
        return Outcome.fail(
            CODE_BROKEN,
            f'{len(changed)} certified array(s) changed and {len(absent)} '
            f'disappeared between the coherence guard and publication. The '
            f'guard report describes numbers that are not the ones being '
            f'sealed.', cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok(
        CODE_VERIFIED, value=dict(ev),
        detail=f'all {len(entries)} certified array(s) unchanged from guard to '
               f'publication', **ev)
