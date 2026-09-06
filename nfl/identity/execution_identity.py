"""Execution identity that CONSUMES its input hashes. G0A item 5.

WHY THE WORD "CONSUMES" IS THE WHOLE POINT

MLB's M0 is preserved and not reproducible. The corpus was never committed, and
-- the part that matters here -- `SIM_FORMULA` EXCLUDED the corpus, so
substituting the data changed the outputs while leaving the fingerprint
`FP-ab18309e17e7e16e` identical. The fingerprint could not catch it because the
inputs were never inside it.

Recording a sha256 next to a run is the easy half and does not help. The hash has
to be inside the identity that the fingerprint is computed over, so that changing
an input necessarily changes the fingerprint. That is the difference this module
exists to make.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import sys
from typing import Any, Mapping, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from sportsplatform.governance.provenance import Provenance, validate as validate_prov  # noqa: E402


@dataclasses.dataclass(frozen=True)
class ConsumedPartition:
    """One input actually read by a run, with the bytes identified."""
    partition_id: str
    source: str
    url: str
    sha256: str
    provenance: Provenance

    def __post_init__(self):
        if not self.sha256 or len(self.sha256) != 64:
            raise ValueError(
                f'{self.partition_id}: sha256 must be a full 64-char digest, '
                f'got {self.sha256!r}. A truncated or absent hash cannot '
                f'identify bytes.')

    def as_dict(self) -> dict:
        return {'partition_id': self.partition_id, 'source': self.source,
                'url': self.url, 'sha256': self.sha256,
                'provenance': dataclasses.asdict(self.provenance)}


@dataclasses.dataclass(frozen=True)
class ExecutionIdentity:
    """Everything that must match for two results to be comparable."""
    spec_id: str
    spec_sha256: str
    code_version: str
    interpreter: str
    seed: Any
    partitions: tuple

    def as_dict(self) -> dict:
        return {
            'spec_id': self.spec_id,
            'spec_sha256': self.spec_sha256,
            'code_version': self.code_version,
            'interpreter': self.interpreter,
            'seed': self.seed,
            # Sorted so the fingerprint does not depend on read order.
            'partitions': sorted((p.as_dict() for p in self.partitions),
                                 key=lambda d: d['partition_id']),
        }

    def fingerprint(self) -> str:
        """sha256 over the canonical identity INCLUDING every input hash."""
        blob = json.dumps(self.as_dict(), sort_keys=True,
                          separators=(',', ':')).encode()
        return 'NFLFP-' + hashlib.sha256(blob).hexdigest()[:16]

    def partition_ids(self) -> set:
        return {p.partition_id for p in self.partitions}

    def validate(self) -> Outcome:
        if not self.partitions:
            return Outcome.fail(
                'IDENTITY_WITHOUT_INPUTS',
                f'{self.spec_id}: execution identity carries no consumed '
                f'partitions. An identity that does not name its inputs cannot '
                f'detect a substituted one -- this is exactly how MLB M0 became '
                f'irreproducible while its fingerprint stayed constant.')
        if not self.spec_sha256:
            return Outcome.fail(
                'IDENTITY_SPEC_UNHASHED',
                f'{self.spec_id}: no spec_sha256. A frozen specification that '
                f'is not hashed is not frozen.')
        bad = {}
        for p in self.partitions:
            v = validate_prov(p.provenance)
            if v.state is not State.PASS:
                bad[p.partition_id] = v.code
        if bad:
            return Outcome.fail(
                'IDENTITY_PARTITION_PROVENANCE_INVALID',
                f'{self.spec_id}: {len(bad)} partitions carry invalid '
                f'provenance: {bad}',
                failures=bad)
        return Outcome.ok('IDENTITY_VALID', value=self.fingerprint(),
                          detail=f'{self.spec_id}: {len(self.partitions)} '
                                 f'partitions, fingerprint {self.fingerprint()}',
                          n_partitions=len(self.partitions))
