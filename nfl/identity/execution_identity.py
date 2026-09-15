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

WHAT `code_version` AND `interpreter` MUST CARRY (WS-E, 2026-09-14)

Those two fields are identities A+B and C of the contract in
`nfl.identity.code_identity`, and the contract document is
`nfl/research/remediation/ws_e/WS_E_IDENTITY_CONTRACT.md`. Build them with
`code_identity.code_identity()`; do not assemble either by hand.

`validate()` now refuses the withdrawn count-keyed form `<sha>+dirty[N]`. That
string keyed the run identity on the NUMBER of dirty paths in the working tree,
which made a run's identity a function of its own outputs -- run 1 writes a
proof directory, run 2 counts one more path, and two bit-identical draw sets get
two different fingerprints. WS01, WS18 (F3) and WS19 found it independently and
WS18 measured it live. It is refused here rather than only in the caller,
because the next caller will be written by someone who did not read the caller
that was fixed.
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
from nfl.identity.code_identity import KEYS_ON_COUNT_MARKER as CODE_VERSION_COUNT_MARKER  # noqa: E402


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
        # THE WITHDRAWN CONTRACT. `<sha>+dirty[N]` keys the identity on a COUNT
        # of dirty paths, so (a) two different working trees with equal counts
        # alias to one identity, and (b) a run that writes an output file
        # changes its own identity. Refused by name, in the identity itself,
        # so no caller can reintroduce it quietly.
        if CODE_VERSION_COUNT_MARKER in str(self.code_version):
            return Outcome.fail(
                'IDENTITY_CODE_VERSION_KEYS_ON_COUNT',
                f'{self.spec_id}: code_version {self.code_version!r} carries '
                f'the withdrawn {CODE_VERSION_COUNT_MARKER!r} form, which keys '
                f'the run identity on the NUMBER of dirty working-tree paths. '
                f'A count cannot identify content -- two unrelated trees with '
                f'the same number of dirty files produce the same identity -- '
                f'and it moves when the run writes its own outputs. Build '
                f'code_version with nfl.identity.code_identity.code_identity().',
                code_version=self.code_version)
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
