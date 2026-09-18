"""An artifact is claimed by verifying the file, never by printing a path.

THE DEFECT THIS EXISTS TO PREVENT HAPPENED ON 2026-09-18, TO THE AGENT WRITING
THIS MODULE.

`nfl/dfs/scoring/dual_board.py` was run as

    python3.12 nfl/dfs/scoring/dual_board.py | head -22

Its table printed. `head` closed the pipe after twenty-two lines, the process
took SIGPIPE, and it died before reaching `out.write_text(...)`. The file was
never created. The screen looked like a successful run, so the commit message
that followed described an artifact that did not exist, and a supersession note
was later written claiming that absent file had been "preserved byte-identical".

Nothing consumed it and the printed numbers were right, so the cost was only
the false claim. Next time the cost is a gate comparing against a file that
isn't there, or a rebuild silently reading a stale copy of the one before it.

WHY PRINTING IS NOT EVIDENCE

`print()` writes to a buffer. The buffer reaches a terminal, a pipe, or a log,
and whether it survives has nothing to do with whether the write that mattered
happened. Worse, stdout is flushed EARLIER than a file write that comes after
it in the source, so the ordering people rely on -- "it printed the path, so it
must have written the file" -- is exactly backwards under a pipe.

THE FIVE THINGS A CLAIM MUST ESTABLISH

  1. the file EXISTS on disk;
  2. its size is greater than zero;
  3. its expected schema or header is present -- a zero-byte file and a file
     containing `{}` are both technically written and neither is an artifact;
  4. any hash is computed FROM THE BYTES ON DISK, not from the object that was
     supposed to have been serialised;
  5. the path reported to the caller is the path that was verified, resolved,
     so a claim cannot describe one file while having checked another.

`ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE` is the refusal. It is a FAIL rather than
a BLOCKED: nothing external is missing, the generator simply did not do what it
said.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import pathlib
import zipfile

from sportsplatform.governance.outcome import Cause, Outcome, State

SPEC_VERSION = 'artifact-claim-1'

CODE_OK = 'ARTIFACT_CLAIM_VERIFIED'
CODE_UNVERIFIED = 'ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE'

#: Reasons, kept apart so a caller can tell "you never wrote it" from
#: "you wrote something that is not the thing you said".
ABSENT = 'FILE_ABSENT'
EMPTY = 'FILE_EMPTY'
SCHEMA = 'SCHEMA_MISSING'
UNREADABLE = 'FILE_UNREADABLE'
PATH_MISMATCH = 'REPORTED_PATH_IS_NOT_THE_VERIFIED_PATH'
HASH_MISMATCH = 'HASH_DOES_NOT_MATCH_BYTES_ON_DISK'


def _schema_ok(path: pathlib.Path, raw: bytes, schema):
    """Is the expected shape present? Returns (ok, detail, observed)."""
    if schema is None:
        return True, 'no schema declared', None
    suffix = path.suffix.lower()
    try:
        if suffix == '.json':
            obj = json.loads(raw.decode('utf-8'))
            if isinstance(schema, (list, tuple, set)):
                missing = [k for k in schema
                           if not (isinstance(obj, dict) and k in obj)]
                return (not missing,
                        f'missing top-level key(s) {missing}' if missing
                        else f'{len(schema)} required key(s) present',
                        sorted(obj) if isinstance(obj, dict) else type(obj).__name__)
            return bool(obj), 'non-empty JSON', type(obj).__name__
        if suffix == '.csv':
            first = raw.decode('utf-8', 'replace').splitlines()[:1]
            if not first:
                return False, 'no header row', None
            header = next(csv.reader(first))
            missing = [c for c in schema if c not in header]
            return (not missing,
                    f'missing column(s) {missing}' if missing
                    else f'{len(schema)} required column(s) present',
                    header)
        if suffix == '.npz':
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = {n[:-4] if n.endswith('.npy') else n
                         for n in z.namelist()}
            missing = [k for k in schema if k not in names]
            return (not missing,
                    f'missing array(s) {missing}' if missing
                    else f'{len(schema)} required array(s) present',
                    sorted(names))
        text = raw.decode('utf-8', 'replace')
        missing = [s for s in schema if s not in text]
        return (not missing,
                f'missing marker(s) {missing}' if missing
                else f'{len(schema)} required marker(s) present',
                None)
    except Exception as e:                                  # noqa: BLE001
        return False, f'{type(e).__name__}: {e}', None


def verify(path, *, schema=None, min_bytes: int = 1, expect_sha256: str = None,
           reported_as=None, label: str = 'artifact') -> Outcome:
    """The five checks. Returns the RESOLVED path, so the caller reports it."""
    p = pathlib.Path(path)
    resolved = p.resolve()
    ev = {'spec_version': SPEC_VERSION, 'label': label,
          'claimed_path': str(p), 'resolved_path': str(resolved)}
    if reported_as is not None:
        rep = pathlib.Path(reported_as).resolve()
        if rep != resolved:
            return Outcome.fail(
                CODE_UNVERIFIED,
                f'{label}: the path being reported ({rep}) is not the path '
                f'that was verified ({resolved}). A claim that describes one '
                f'file while checking another is worth nothing.',
                cause=Cause.GOVERNANCE, reason=PATH_MISMATCH,
                reported_path=str(rep), **ev)
    if not resolved.exists():
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: {resolved} does not exist. It was claimed as written '
            f'and it is not on disk -- printed output is not evidence that a '
            f'write happened, and under a pipe stdout is flushed BEFORE a '
            f'later file write, so the usual reasoning is backwards.',
            cause=Cause.GOVERNANCE, reason=ABSENT, **ev)
    if not resolved.is_file():
        return Outcome.fail(
            CODE_UNVERIFIED, f'{label}: {resolved} is not a regular file',
            cause=Cause.GOVERNANCE, reason=ABSENT, **ev)
    size = resolved.stat().st_size
    ev['n_bytes'] = size
    if size < max(min_bytes, 1):
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: {resolved} is {size} byte(s), below the {min_bytes} '
            f'required. A file that exists and holds nothing is a failed '
            f'write wearing a filename.',
            cause=Cause.GOVERNANCE, reason=EMPTY, **ev)
    try:
        raw = resolved.read_bytes()
    except OSError as e:
        return Outcome.fail(
            CODE_UNVERIFIED, f'{label}: {resolved} could not be read: {e}',
            cause=Cause.GOVERNANCE, reason=UNREADABLE, **ev)
    sha = hashlib.sha256(raw).hexdigest()
    ev['sha256'] = sha
    if expect_sha256 is not None and sha != expect_sha256:
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: sha256 of the bytes on disk is {sha[:16]}, not the '
            f'claimed {str(expect_sha256)[:16]}.',
            cause=Cause.GOVERNANCE, reason=HASH_MISMATCH,
            expected_sha256=expect_sha256, **ev)
    ok, detail, observed = _schema_ok(resolved, raw, schema)
    ev['schema_detail'] = detail
    ev['schema_observed'] = observed
    if not ok:
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: {resolved} exists and is non-empty but its shape is '
            f'wrong -- {detail}. A partially written file is the failure mode '
            f'that looks most like success.',
            cause=Cause.GOVERNANCE, reason=SCHEMA, **ev)
    return Outcome.ok(
        CODE_OK, value=str(resolved),
        detail=f'{label}: {resolved.name}, {size} bytes, sha256 {sha[:16]}, '
               f'{detail}',
        **ev)


def claim(path, *, schema=None, min_bytes: int = 1, label: str = 'artifact',
          quiet: bool = False) -> Outcome:
    """What a generator calls INSTEAD of printing "wrote X".

    Returns the verified Outcome and, unless `quiet`, prints a line that is
    produced FROM the verification rather than from an intention. If the file
    is missing the line says so -- the generator cannot accidentally announce
    a success it did not have.
    """
    o = verify(path, schema=schema, min_bytes=min_bytes, label=label)
    if not quiet:
        if o.state is State.PASS:
            print(f'VERIFIED {o.value} '
                  f'({o.evidence["n_bytes"]} bytes, '
                  f'sha256 {o.evidence["sha256"][:16]})')
        else:
            print(f'{o.code}[{o.evidence.get("reason")}] {o.detail}')
    return o


def claim_or_raise(path, *, schema=None, min_bytes: int = 1,
                   label: str = 'artifact') -> str:
    """For a generator whose exit status should reflect the claim."""
    o = claim(path, schema=schema, min_bytes=min_bytes, label=label)
    if o.state is not State.PASS:
        raise SystemExit(f'{CODE_UNVERIFIED}: {o.detail}')
    return o.value
