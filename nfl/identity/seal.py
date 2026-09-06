"""Immutable pre-kickoff forecast seal. G0A items 11 and 12.

THE CLOCK ORDER, CORRECTED

An earlier draft of this control proposed

    written_at < captured_at < kickoff

which is backwards for any partition the forecast actually consumed: a forecast
cannot legitimately read bytes that arrived after it was written. Owner Directive
3 §4. The enforced order is

    source / effective  ->  retrieved_at (captured_at)  ->  written_at  ->  kickoff

and at minimum, for every consumed partition:

    partition.retrieved_at  <=  forecast.written_at  <  kickoff

The five clocks are NOT collapsed to satisfy that ordering. `source_timestamp`,
`effective_for_date`, `retrieved_at`, `generated_at` and `cache_timestamp` stay
distinct, and the per-partition consistency between them -- including a cache hit
that falsely claims a fresh retrieval -- is delegated to
`sportsplatform.governance.provenance.validate`, which already encodes it and already carries
the V7 weather defect as a replay test.

WHAT SEALING MEANS

A sealed forecast is identified by the sha256 of its payload plus its execution
identity fingerprint. Re-sealing the same forecast_id with different content is a
named failure, not an update. That is what makes "sealed before kickoff" a fact
about the artifact rather than a claim about the process.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import pathlib
import sys
from typing import Iterable, Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.identity.execution_identity import ExecutionIdentity  # noqa: E402


def _parse(ts, field: str) -> dt.datetime:
    if isinstance(ts, dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
    d = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


@dataclasses.dataclass(frozen=True)
class Seal:
    forecast_id: str
    game_id: str
    written_at: str
    kickoff_utc: str
    payload_sha256: str
    identity_fingerprint: str
    identity: dict
    consumed_partition_ids: tuple

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)

    def seal_sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True,
                                         separators=(',', ':')).encode()
                              ).hexdigest()


def seal_forecast(*, forecast_id: str, game_id: str, kickoff_utc: str,
                  payload: bytes, identity: ExecutionIdentity,
                  consumed_partition_ids: Iterable[str],
                  written_at: Optional[str] = None) -> Outcome:
    """Seal a forecast, or refuse with a named code. No third outcome."""
    written_at = written_at or dt.datetime.now(dt.timezone.utc).isoformat()

    iv = identity.validate()
    if iv.state is not State.PASS:
        return iv

    if not payload:
        return Outcome.fail(
            'SEAL_PAYLOAD_EMPTY',
            f'{forecast_id}: refusing to seal an empty forecast. An empty '
            f'artifact sealed before kickoff would satisfy every ordering check '
            f'here and contain nothing.')

    try:
        w = _parse(written_at, 'written_at')
        k = _parse(kickoff_utc, 'kickoff_utc')
    except (ValueError, TypeError) as exc:
        return Outcome.blocked('SEAL_TIMESTAMP_UNPARSEABLE', str(exc),
                               cause=Cause.DATA)

    consumed = list(consumed_partition_ids)
    if not consumed:
        return Outcome.fail(
            'SEAL_NO_CONSUMED_INPUTS',
            f'{forecast_id}: the forecast declares no consumed partitions. A '
            f'forecast that read nothing cannot be reproduced, and a forecast '
            f'that read something and did not say so is worse.')

    # (1) Every partition the forecast actually read must be inside the identity.
    #     Otherwise a substituted input changes the result without changing the
    #     fingerprint -- the MLB M0 failure mode exactly.
    missing = sorted(set(consumed) - identity.partition_ids())
    if missing:
        return Outcome.fail(
            'PARTITION_NOT_IN_IDENTITY',
            f'{forecast_id}: consumed {missing} but the execution identity does '
            f'not contain them. An input outside the identity is invisible to '
            f'the fingerprint.',
            missing=missing, consumed=sorted(consumed),
            in_identity=sorted(identity.partition_ids()))

    by_id = {p.partition_id: p for p in identity.partitions}

    # (2) THE CORRECTED ORDERING. Nothing the forecast read may have arrived
    #     after the forecast was written.
    late = []
    for pid in consumed:
        r = _parse(by_id[pid].provenance.retrieved_at, 'retrieved_at')
        if r > w:
            late.append({'partition_id': pid,
                         'retrieved_at': by_id[pid].provenance.retrieved_at,
                         'written_at': written_at,
                         'seconds_after_write': (r - w).total_seconds()})
    if late:
        return Outcome.fail(
            'CAPTURE_AFTER_WRITE',
            f'{forecast_id}: {len(late)} consumed partition(s) were retrieved '
            f'AFTER the forecast was written. A forecast cannot consume bytes '
            f'that had not arrived: {late}',
            violations=late)

    # (3) The forecast itself must predate kickoff.
    if w >= k:
        return Outcome.fail(
            'WRITE_AFTER_KICKOFF',
            f'{forecast_id}: written_at {written_at} is at or after kickoff '
            f'{kickoff_utc}. This is not a prospective forecast.',
            written_at=written_at, kickoff_utc=kickoff_utc,
            seconds_late=(w - k).total_seconds())

    payload_sha = hashlib.sha256(payload).hexdigest()
    s = Seal(forecast_id=forecast_id, game_id=game_id, written_at=written_at,
             kickoff_utc=kickoff_utc, payload_sha256=payload_sha,
             identity_fingerprint=identity.fingerprint(),
             identity=identity.as_dict(),
             consumed_partition_ids=tuple(sorted(consumed)))
    return Outcome.ok('FORECAST_SEALED', value=s,
                      detail=f'{forecast_id}: sealed {(k - w).total_seconds() / 3600:.2f}h '
                             f'before kickoff; identity {identity.fingerprint()}',
                      payload_sha256=payload_sha, seal_sha256=s.seal_sha256())


def append_seal(seal: Seal, ledger_path) -> Outcome:
    """Append-only. A second seal for the same forecast_id with different
    content is a named failure, never an overwrite."""
    p = pathlib.Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        for ln in p.read_text().splitlines():
            if not ln.strip():
                continue
            prior = json.loads(ln)
            if prior.get('forecast_id') == seal.forecast_id:
                if prior.get('seal_sha256') == seal.seal_sha256():
                    return Outcome.not_applicable(
                        'SEAL_ALREADY_RECORDED',
                        f'{seal.forecast_id} is already sealed with identical '
                        f'content; re-recording it would add nothing.')
                return Outcome.fail(
                    'SEAL_IMMUTABLE_VIOLATION',
                    f'{seal.forecast_id} is already sealed with DIFFERENT '
                    f'content (prior seal {prior.get("seal_sha256")}, new '
                    f'{seal.seal_sha256()}). A seal is not an update.',
                    prior_seal=prior.get('seal_sha256'))
    rec = seal.as_dict()
    rec['seal_sha256'] = seal.seal_sha256()
    with open(p, 'a') as fh:
        fh.write(json.dumps(rec, sort_keys=True) + '\n')
    return Outcome.ok('SEAL_APPENDED', value=str(p),
                      detail=f'{seal.forecast_id} appended to {p.name}')
