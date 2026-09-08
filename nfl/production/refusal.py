"""Production refusal codes. The system prefers NO FORECAST to an
unverifiable one.

Every refusal is persisted and auditable. A refusal is a RESULT -- a recorded
statement that the system declined and why -- and never a silent absence.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

REFUSALS = {
    'SOURCE_MISSING': 'a required authorized source produced no bytes',
    'SOURCE_TOO_LATE': 'a source was retrieved at or after written_at',
    'SOURCE_CHRONOLOGY_FAILURE': 'source clocks are internally impossible',
    'RAW_HASH_MISMATCH': 'stored bytes do not hash to the recorded digest',
    'IDENTITY_UNRESOLVED': 'a player or team could not be resolved deterministically',
    'REQUIRED_GAME_MISSING': 'a game in the requested slate is absent from the schedule',
    'SCHEMA_DRIFT': 'an input schema does not match an accepted shape',
    'UNAUTHORIZED_INPUT': 'an input outside the authorized registry was supplied',
    'MODEL_ARTIFACT_MISSING': 'a required model artifact is absent',
    'MODEL_HASH_MISMATCH': 'a model artifact does not match its recorded hash',
    'COLD_START_VIOLATION': 'the cold-start freeze identity does not match',
    'ARM_RULE_VIOLATION': 'the run would consume data its arm forbids',
    'INCOMPLETE_PLAYER_ACCOUNTING': 'team and player totals do not reconcile',
    'JOINT_RECONCILIATION_FAILURE': 'the joint draw could not be made physically valid',
    'ARTIFACT_SEALING_FAILURE': 'the forecast artifact failed its own contract',
    'NFL1_NOT_AUTHORIZED': 'publication requires an explicit owner authorization',
    'STAGE_NOT_IMPLEMENTED': 'a pipeline stage has no production model yet',
    'EMPTY_FORECAST_ARTIFACT': 'the artifact would seal carrying no player '
                               'distributions at all',
}


@dataclasses.dataclass(frozen=True)
class Refusal:
    code: str
    stage: str
    detail: str
    run_id: str
    at: str

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def refuse(code: str, stage: str, detail: str, run_id: str) -> Outcome:
    if code not in REFUSALS:
        return Outcome.fail(
            'UNKNOWN_REFUSAL_CODE',
            f'{code!r} is not a declared refusal. An undeclared refusal cannot '
            f'be audited, and inventing one at the call site is how a category '
            f'of failure becomes invisible.', offending_code=code)
    r = Refusal(code=code, stage=stage, detail=detail, run_id=run_id,
                at=_dt.datetime.now(_dt.timezone.utc).isoformat())
    return Outcome.blocked(code, f'{stage}: {detail}', cause=Cause.GOVERNANCE,
                           refusal=r.as_dict())


def persist(refusals: list, out_dir: pathlib.Path) -> Outcome:
    """Append-only. A refusal that is not written down did not happen."""
    if not refusals:
        return Outcome.not_applicable('NO_REFUSALS', 'the run produced none')
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / 'refusals.jsonl'
    with open(p, 'a') as fh:
        for r in refusals:
            fh.write(json.dumps(r, sort_keys=True) + '\n')
    return Outcome.ok('REFUSALS_PERSISTED', value=len(refusals),
                      detail=f'{len(refusals)} refusal(s) appended to {p.name}')
