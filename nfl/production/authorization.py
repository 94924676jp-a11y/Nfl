"""The publication gate. NFL-1 must be explicitly authorized by the owner.

THERE IS NO PATH FROM A GREEN TEST SUITE TO AUTHORIZATION. The guard reads the
structured gate state and an owner authorization record, and refuses anything
else -- a passing suite, a discharged checklist, an environment variable, a
caller-supplied flag.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

STATE = _REPO / 'nfl' / 'research' / 'PATH_C_STATE.json'
AUTH_RECORD = _REPO / 'nfl' / 'NFL1_OWNER_AUTHORIZATION.json'


def gate_state() -> dict:
    return json.loads(STATE.read_text())['gates']


def may_publish() -> Outcome:
    """The only function permitted to say a forecast may be PUBLISHED."""
    g = gate_state()
    if g.get('NFL_1') != 'AUTHORIZED':
        return Outcome.blocked(
            'NFL1_NOT_AUTHORIZED',
            f'NFL-1 is {g.get("NFL_1")!r} and G0A is {g.get("G0A")!r}. A '
            f'forecast may be COMPUTED and SEALED locally, but it may not be '
            f'published. No test result, checklist state or caller flag can '
            f'change this -- only an owner authorization record.',
            cause=Cause.GOVERNANCE, gates=g)
    if not AUTH_RECORD.exists():
        return Outcome.fail(
            'AUTHORIZATION_RECORD_MISSING',
            'the gate reads AUTHORIZED but no owner authorization record '
            'exists. A gate flipped without a record behind it is exactly the '
            'auto-authorization this guard prevents.')
    rec = json.loads(AUTH_RECORD.read_text())
    if rec.get('basis') != 'OWNER_DECISION' or not rec.get('owner_decision_id'):
        return Outcome.fail(
            'AUTHORIZATION_BASIS_INVALID',
            f'authorization basis is {rec.get("basis")!r}. Only an explicit, '
            f'identified owner decision authorizes publication.')
    return Outcome.ok('PUBLICATION_AUTHORIZED',
                      value=rec.get('owner_decision_id'), gates=g)


def may_compute() -> Outcome:
    """Computing and sealing locally is always allowed. Publishing is not."""
    return Outcome.ok('COMPUTE_ALLOWED', value=True,
                      detail='a run may compute and seal; publication is gated '
                             'separately by may_publish()')
