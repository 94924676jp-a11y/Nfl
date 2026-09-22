"""Raw bytes first, then everything else points at their hash.

THE ORDER IS THE POINT, and it is the order `inactives` and `oddsclient`
already use:

    raw bytes -> sha256 -> store -> manifest -> parse -> derive

A parser improves; the bytes do not. Storing the file before interpreting it
is what makes a later parser change a re-derivation rather than a loss, and
it is why an archive built this way survives its own maintenance.

THE LAYOUT IS A CONVENIENCE. IDS AND HASHES ARE THE CONTRACT.

Files land under dfs_history/<provider>/<season>/<week>/<contest key>/, which
is pleasant to browse and is NOT the semantic contract. What identifies an
artifact is its sha256 and the contest identity recorded beside it; a
directory can be reorganised without anything downstream noticing, and
nothing may key on the path.

COMPLETENESS IS DECLARED, NEVER INFERRED. `assert_completeness` compares the
entries held against the contest's declared field size and returns COMPLETE
only when both exist AND agree. A field size nobody supplied gives
COMPLETENESS_UNKNOWN, not a pass -- the same rule the integrity contract
uses, for the same reason.
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.history import contracts as C                           # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome         # noqa: E402

SPEC_VERSION = 'nfl-dfs-history-store-0'
ROOT = _REPO / 'nfl' / 'dfs_history'
MANIFEST_NAME = 'manifest.json'


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def contest_dir(contest: C.DFSContestIdentity, *, root=None) -> pathlib.Path:
    base = pathlib.Path(root or ROOT)
    safe = contest.key.replace(':', '_').replace('/', '_')
    week = f'week_{contest.week}' if contest.week is not None \
        else 'week_unknown'
    return (base / contest.provider.lower()
            / str(contest.season or 'season_unknown') / week / safe)


def store_raw(raw: bytes, *, contest: C.DFSContestIdentity,
              artifact_type: str, retrieved_at: str = None,
              original_filename: str = None,
              provider_timestamp: str = None,
              snapshot_type: str = C.SNAPSHOT_UNKNOWN,
              schema_fingerprint: str = None, row_count: int = None,
              parser_version: str = None,
              confidence: str = C.VERIFIED_PRIMARY,
              note: str = None, root=None) -> Outcome:
    """Write the operator's bytes unchanged and describe them.

    `confidence` defaults to VERIFIED_PRIMARY because the bytes ARE the
    primary artifact -- we hold them. That says nothing about whether our
    INTERPRETATION of them is verified, which is the parser's own claim and
    is recorded separately.
    """
    if not raw:
        return Outcome.blocked(
            'DFS_RAW_EMPTY',
            'no bytes were supplied. An empty file is not a capture.',
            cause=Cause.DATA)
    if artifact_type not in C.ARTIFACT_TYPES:
        return Outcome.fail(
            'DFS_ARTIFACT_TYPE_NOT_DECLARED',
            f'{artifact_type!r} is not one of {C.ARTIFACT_TYPES}. An '
            f'undeclared type cannot be found again by anyone who does not '
            f'already know it exists.')
    if snapshot_type not in C.SNAPSHOTS:
        return Outcome.fail(
            'DFS_SNAPSHOT_TYPE_NOT_DECLARED',
            f'{snapshot_type!r} is not one of {C.SNAPSHOTS}.')
    if confidence not in C.CONFIDENCE:
        return Outcome.fail(
            'DFS_CONFIDENCE_NOT_DECLARED',
            f'{confidence!r} is not one of {C.CONFIDENCE}.')

    digest = C.sha256_bytes(raw)
    d = contest_dir(contest, root=root) / 'raw'
    d.mkdir(parents=True, exist_ok=True)
    ext = pathlib.Path(original_filename or '').suffix or '.bin'
    p = d / f'{artifact_type.lower()}.{digest[:16]}{ext}'
    if p.exists() and p.read_bytes() != raw:          # pragma: no cover
        return Outcome.fail(
            'DFS_RAW_HASH_COLLISION',
            f'{p} exists with different bytes under the same digest prefix.')
    p.write_bytes(raw)
    back = p.read_bytes()
    if C.sha256_bytes(back) != digest:                # pragma: no cover
        return Outcome.fail(
            'DFS_RAW_DID_NOT_READ_BACK',
            f'{p} did not read back as the bytes written.')

    art = C.DFSRawArtifact(
        artifact_type=artifact_type, provider=contest.provider,
        contest=contest, retrieved_at=retrieved_at or _now(),
        raw_sha256=digest, original_filename=original_filename,
        provider_timestamp=provider_timestamp,
        stored_path=str(p.relative_to(_REPO)) if str(p).startswith(str(_REPO))
        else str(p),
        n_bytes=len(raw), schema_fingerprint=schema_fingerprint,
        row_count=row_count, parser_version=parser_version,
        snapshot_type=snapshot_type, confidence=confidence, note=note)
    return Outcome.ok(
        'DFS_RAW_STORED', art, path=str(p), sha256=digest,
        detail=f'{artifact_type} {len(raw)} byte(s) -> {p.name}')


def assert_completeness(*, n_entries_held: int,
                        declared_field_size: Optional[int]) -> Dict[str, str]:
    """COMPLETE only when both numbers exist and agree."""
    if declared_field_size is None:
        return {'completeness': C.COMPLETENESS_UNKNOWN,
                'why': f'{n_entries_held} entry(ies) held and the contest\'s '
                       f'own field size was not supplied, so whether this is '
                       f'the whole field is not established. Absence of a '
                       f'field size is not evidence that we have all of it.'}
    if n_entries_held == declared_field_size:
        return {'completeness': C.COMPLETE,
                'why': f'{n_entries_held} entry(ies) held and the contest '
                       f'declares a field of {declared_field_size}; they '
                       f'agree.'}
    return {'completeness': C.INCOMPLETE,
            'why': f'{n_entries_held} entry(ies) held against a declared '
                   f'field of {declared_field_size}. '
                   f'{abs(declared_field_size - n_entries_held)} '
                   f'{"missing" if n_entries_held < declared_field_size else "unexpected"}.'}


def write_manifest(manifest: C.DFSContestManifest, *, root=None) -> Outcome:
    """Persist and READ BACK. A manifest nobody verified is not a record."""
    d = contest_dir(manifest.contest, root=root)
    d.mkdir(parents=True, exist_ok=True)
    p = d / MANIFEST_NAME
    doc = manifest.as_dict()
    p.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str)
                 + '\n')
    back = json.loads(p.read_text())
    if back.get('manifest_hash') != manifest.manifest_hash():
        return Outcome.fail(
            'DFS_MANIFEST_DID_NOT_READ_BACK',
            f'{p} reads back with a different manifest hash.')
    for k in ('contest', 'artifacts', 'completeness', 'snapshot_type',
              'manifest_hash'):
        if k not in back:
            return Outcome.fail(
                'DFS_MANIFEST_INCOMPLETE',
                f'{p} is missing {k!r}, which the archive contract requires '
                f'for the capture to be replayable.', missing=k)
    return Outcome.ok(
        'DFS_MANIFEST_WRITTEN',
        {'path': str(p), 'manifest_hash': manifest.manifest_hash(),
         'n_artifacts': len(manifest.artifacts)},
        detail=f'{len(manifest.artifacts)} artifact(s) -> {p}')


def rehydrate(path, *, root=None) -> Outcome:
    """Read a manifest back and VERIFY every raw file still hashes true.

    This is the acceptance standard for the whole package: a contest file
    captured today is a verifiable research artifact years from now, without
    DraftKings still hosting it. That is only true if somebody can check.
    """
    p = pathlib.Path(path)
    if p.is_dir():
        p = p / MANIFEST_NAME
    if not p.exists():
        return Outcome.blocked(
            'DFS_MANIFEST_ABSENT', f'{p} does not exist.', cause=Cause.DATA)
    doc = json.loads(p.read_text())
    checked, bad, missing = [], [], []
    for a in doc.get('artifacts') or ():
        sp = a.get('stored_path')
        fp = (_REPO / sp) if sp and not pathlib.Path(sp).is_absolute() \
            else pathlib.Path(sp or '')
        if not sp or not fp.exists():
            missing.append({'artifact_type': a.get('artifact_type'),
                            'stored_path': sp})
            continue
        got = C.sha256_bytes(fp.read_bytes())
        (checked if got == a.get('raw_sha256') else bad).append(
            {'artifact_type': a.get('artifact_type'), 'expected':
             a.get('raw_sha256'), 'found': got, 'path': sp})
    if missing or bad:
        return Outcome.fail(
            'DFS_ARCHIVE_NOT_VERIFIABLE',
            f'{len(missing)} artifact file(s) absent and {len(bad)} whose '
            f'bytes no longer hash to the value recorded. An archive that '
            f'cannot be verified is a story about a file.',
            value={'missing': missing, 'mismatched': bad,
                   'verified': checked})
    return Outcome.ok(
        'DFS_ARCHIVE_VERIFIED',
        {'manifest_hash': doc.get('manifest_hash'),
         'contest_key': doc.get('contest_key'),
         'completeness': doc.get('completeness'),
         'snapshot_type': doc.get('snapshot_type'),
         'n_verified': len(checked), 'verified': checked,
         'document': doc},
        detail=f'{len(checked)} artifact(s) hash true for '
               f'{doc.get("contest_key")}')
