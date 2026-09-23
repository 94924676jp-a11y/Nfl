"""Carry the chain's conservation verdict to the layer that publishes.

THE GAP THIS CLOSES, AND THE ONE IT DOES NOT.

`allocation.assert_allocation_conserves` runs inside `run_chain.py` and its
verdict is recorded per club-room. The review gate re-derives its decision
from `run_status.json` and the review directory, and `run_chain.py` is a
SEPARATE ENTRY POINT from `run_forecast.py`, so that verdict has never
reached the gate. A safeguard that exists is not a safeguard that is
evidenced in the governed path.

This module is the carrier: the chain writes a governed artifact, the review
layer reads it, and `conservation_integrity` produces findings from it. It
does NOT recompute anything -- the review layer does not hold the allocation
rows, and a producer that recomputed from partial inputs would be a second
implementation of the invariant, disagreeing with the first at the worst
possible moment.

WHAT IT STILL DOES NOT DO. Measured 2026-09-23: `run_chain.run` has NO
CALLER in this repository outside its own CLI. Nothing orchestrates a chain
run alongside a forecast run, so no review directory is currently handed a
bridge artifact. The carrier is ready; the orchestration is not, and until it
exists the two allocation codes stay RELINQUISHED rather than being
advertised on the strength of a path nothing walks.

THE CERTIFICATE IS THE POINT. A bridge that transported a verdict without
proving which composition it was about would let a stale artifact certify a
new slate. The body is hashed, the hash travels with it, and a mismatch
BLOCKS rather than degrading to NOT_CHECKED: a document that fails its own
integrity check is worse evidence than no document.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib
import sys
from typing import Any, Dict, Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nfl-conservation-bridge-0'
FILENAME = 'CONSERVATION_BRIDGE.json'
PRODUCER = 'universe.allocation.assert_allocation_conserves'

CODE_WRITTEN = 'CONSERVATION_BRIDGE_WRITTEN'
CODE_READ = 'CONSERVATION_BRIDGE_READ'
CODE_ABSENT = 'CONSERVATION_BRIDGE_ABSENT'
CODE_UNREADABLE = 'CONSERVATION_BRIDGE_UNREADABLE'
CODE_CERTIFICATE_MISMATCH = 'CONSERVATION_BRIDGE_CERTIFICATE_MISMATCH'
CODE_SLATE_MISMATCH = 'CONSERVATION_BRIDGE_SLATE_MISMATCH'
CODE_EMPTY = 'CONSERVATION_BRIDGE_EMPTY'


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _certificate(body: Dict[str, Any]) -> str:
    blob = json.dumps(body, sort_keys=True, separators=(',', ':'),
                      default=str).encode()
    return 'CB-' + hashlib.sha256(blob).hexdigest()[:16]


def body_of(chain: Dict[str, Any], *, slate_key: str = None,
            information_cut: str = None,
            source_artifacts: Dict[str, str] = None) -> Dict[str, Any]:
    """Exactly what the producers need, and the identity of what it is about.

    `offending` is carried whole. A verdict that said only FAIL would force
    the review layer to guess which club lost opportunity, and guessing is
    what this whole layer exists to stop.
    """
    alloc = ((chain or {}).get('layers') or {}).get('allocation') or {}
    rooms = {}
    for room, entry in sorted(alloc.items()):
        g = (entry or {}).get('gate') or {}
        rooms[room] = {'code': g.get('code'), 'state': g.get('state'),
                       'offending': g.get('offending') or []}
    return {
        'spec_version': SPEC_VERSION,
        'producer': PRODUCER,
        'producer_version': (chain or {}).get('spec_version') or SPEC_VERSION,
        'slate_key': slate_key or (chain or {}).get('game_id'),
        'information_cut': information_cut or (chain or {}).get('cut'),
        'run_id': (chain or {}).get('run_id'),
        'rooms': rooms,
        'source_artifacts': dict(sorted((source_artifacts or {}).items())),
    }


def write(chain: Dict[str, Any], review_dir, *, slate_key: str = None,
          information_cut: str = None,
          source_artifacts: Dict[str, str] = None) -> Outcome:
    """Persist the chain's conservation verdict and READ IT BACK."""
    body = body_of(chain, slate_key=slate_key,
                   information_cut=information_cut,
                   source_artifacts=source_artifacts)
    if not body['rooms']:
        return Outcome.blocked(
            CODE_EMPTY,
            'the chain result carries no allocation gate verdict for any '
            'club room, so there is nothing to transport. An empty bridge '
            'would read back as a clean one.', cause=Cause.DATA)
    doc = dict(body)
    doc['certificate'] = _certificate(body)
    doc['written_at'] = _now()
    d = pathlib.Path(review_dir)
    d.mkdir(parents=True, exist_ok=True)
    p = d / FILENAME
    p.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str)
                 + '\n')
    back = json.loads(p.read_text())
    if back.get('certificate') != doc['certificate']:
        return Outcome.fail(
            CODE_UNREADABLE,
            f'{p} did not read back with the certificate it was written '
            f'with.')
    return Outcome.ok(
        CODE_WRITTEN, {'path': str(p), 'certificate': doc['certificate'],
                       'n_rooms': len(body['rooms'])},
        detail=f'{len(body["rooms"])} club-room verdict(s) -> {p.name}')


def read(review_dir, *, slate_key: str = None) -> Outcome:
    """Load and VERIFY. A failed certificate blocks; it never degrades.

    Returns a document shaped like a `run_chain` result, so
    `conservation_integrity` reads a bridge and a live chain result through
    the same accessor and cannot grow two code paths.
    """
    p = pathlib.Path(review_dir) / FILENAME
    if not p.exists():
        return Outcome.blocked(
            CODE_ABSENT,
            f'no {FILENAME} beside the review at {review_dir}. The chain\'s '
            f'conservation verdict was not transported, so the invariant is '
            f'unevaluated here -- which is NOT_CHECKED, never a pass.',
            cause=Cause.DATA)
    try:
        doc = json.loads(p.read_text())
    except Exception as e:                                    # noqa: BLE001
        return Outcome.fail(
            CODE_UNREADABLE,
            f'{p} is not readable JSON ({type(e).__name__}). A document that '
            f'fails its own integrity check is worse evidence than none.')
    got = doc.get('certificate')
    want = _certificate({k: v for k, v in doc.items()
                         if k not in ('certificate', 'written_at')})
    if got != want:
        return Outcome.fail(
            CODE_CERTIFICATE_MISMATCH,
            f'{p} carries certificate {got} and its body hashes to {want}. '
            f'The verdict and the composition it claims to be about have '
            f'come apart, and a transported verdict nobody can tie to a '
            f'composition is not evidence about that composition.',
            certificate_recorded=got, certificate_recomputed=want)
    if slate_key and doc.get('slate_key') and doc['slate_key'] != slate_key:
        return Outcome.fail(
            CODE_SLATE_MISMATCH,
            f'{p} carries a verdict about {doc["slate_key"]!r} and this '
            f'review is of {slate_key!r}. A conservation verdict from '
            f'another slate certifies nothing about this one.',
            bridge_slate=doc.get('slate_key'), review_slate=slate_key)
    rooms = doc.get('rooms') or {}
    if not rooms:
        return Outcome.blocked(
            CODE_EMPTY, f'{p} transports no club-room verdict.',
            cause=Cause.DATA)
    return Outcome.ok(
        CODE_READ,
        {'layers': {'allocation': {room: {'gate': g}
                                   for room, g in rooms.items()}},
         'certificate': got, 'slate_key': doc.get('slate_key'),
         'information_cut': doc.get('information_cut'),
         'producer': doc.get('producer'),
         'producer_version': doc.get('producer_version'),
         'source_artifacts': doc.get('source_artifacts') or {}},
        detail=f'{len(rooms)} club-room verdict(s) from {p.name}, '
               f'certificate {got}')
