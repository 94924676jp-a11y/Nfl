#!/usr/bin/env python3.12
"""Every production run gets its own sealed directory, so a past slate stays reproducible.

THE DEFECT. Production writes to fixed paths -- `DK_WEEK3_PROJECTIONS_V1.csv`,
`DK_WEEK3_PROJ_V1.json`, `CONTEST_PORTFOLIO.json` and the rest. A rerun overwrites them. So the
slate that was actually delivered on a given Sunday exists only until the next run, which means a
past run cannot be reproduced, cannot be compared against a later one, and cannot be audited after
the fact. Every guarantee the rest of this project builds -- lineage, seals, execution identity --
describes a run that the next run silently destroys.

WHAT THIS DOES. After a run, its outputs are copied into `nfl/production/runs/<run_id>/` and the
directory is SEALED: a `SEAL.json` records the SHA-256 of every archived file, and `verify()`
recomputes them. The fixed paths keep working exactly as before and become a pointer to the current
run, named in `runs/CURRENT.json`. Nothing about any projection changes; this is an archival wrapper
and it must never alter a number.

THE RUN ID CARRIES ITS OWN IDENTITY, not just a timestamp. It is
`<slate>__<utc>__<12 hex of sha256(code_version)>`, where the code version comes from
`identity.code_identity`. It is HASHED rather than truncated: the real version string is
`042fad48...+src1[025dff1b066fa876]`, whose commit sha alone is exactly 40 characters, so truncating
to a fixed width silently dropped the dirty-working-tree marker and gave a dirty and a clean tree the
same run id at the same second. The full version string is kept in the seal, so the short id is a
handle and never the record.

ARCHIVED FILES ARE GZIPPED, and the digest is of the ORIGINAL bytes. An uncompressed run is 7.7MB, so
a season of weekly runs would add gigabytes to the repository; gzipped it is a fraction of that. The
seal records the digest of the file's real content, not of the compressed container, so a sealed digest
can still be compared directly against the live output path -- which is what `verify_current()` does.
This follows the pattern already established for capture blobs: the manifest is the audit trail and the
payload lives gzipped beside it.

WHAT IT REFUSES. Archiving over a sealed run is refused -- an immutable record that can be rewritten
is not a record. Archiving a missing or empty source file is refused, because a run archived with a
hole in it looks complete forever afterwards. And `verify()` FAILs, naming the file, if any archived
byte has moved since the seal.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

#: The archive root. Overridable by NFL_RUN_ARCHIVE_DIR so a test that exercises the production run
#: cannot write into the permanent record. It had to be: every suite run calls sunday.run(), and each
#: call was sealing a new directory into nfl/production/runs, so the archive filled with test
#: artifacts that looked exactly like delivered slates.
RUNS = pathlib.Path(os.environ.get('NFL_RUN_ARCHIVE_DIR') or (_REPO / 'nfl/production/runs'))
CURRENT = RUNS / 'CURRENT.json'
SEAL_NAME = 'SEAL.json'

#: The outputs a run is defined by. A run archived without one of these is not a run of this
#: pipeline, so each is required rather than best-effort.
RUN_OUTPUTS = (
    'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json',
    'nfl/dfs/salaries/DK_WEEK3_PROJECTIONS_V1.csv',
    'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json',
    'nfl/dfs/salaries/FIELD_MODEL.json',
    'nfl/dfs/salaries/CONTEST_PORTFOLIO.json',
    'nfl/production/READINESS.json',
    'nfl/production/SUNDAY_RUN_REPORT.json',
)

#: Archived if present, not required: the spreadsheet deliverables, which a research run may skip.
RUN_OUTPUTS_OPTIONAL = (
    'nfl/dfs/salaries/DK_WEEK3_PROJECTIONS_V1.xlsx',
    'nfl/dfs/salaries/DK_WEEK3_DELIVERABLE_SUPPLEMENT.xlsx',
)


def _rel(p: pathlib.Path) -> str:
    """A repo-relative display path, or the absolute one. NEVER raises.

    pathlib.relative_to() raises when the path is outside the repo, which happens the moment the
    archive root is redirected -- exactly what a test must do to avoid writing into the permanent
    record. A governed function returning an Outcome must not raise out of its own display string.
    """
    try:
        return str(p.relative_to(_REPO))
    except ValueError:
        return str(p)


def digest(p: pathlib.Path):
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _code_version() -> tuple:
    try:
        from nfl.identity import code_identity as CI
        o = CI.code_identity()
        if o.state.name == 'PASS':
            return CI.code_version(o.value), o.value
        return f'UNRESOLVED_{o.code}', {'code_identity_state': o.state.value, 'code': o.code}
    except Exception as e:  # noqa: BLE001
        return 'UNRESOLVED_IMPORT', {'error': f'{type(e).__name__}: {e}'}


def run_id(slate: str, when=None, code_version: str | None = None) -> str:
    when = when or dt.datetime.now(dt.timezone.utc)
    stamp = when.strftime('%Y%m%dT%H%M%SZ')
    cv = code_version if code_version is not None else _code_version()[0]
    short = hashlib.sha256(str(cv).encode()).hexdigest()[:12]
    return f'{slate}__{stamp}__{short}'


def is_sealed(d: pathlib.Path) -> bool:
    return (d / SEAL_NAME).exists()


def archive(slate: str, *, when=None, note: str | None = None,
            outputs=None, optional=None) -> Outcome:
    """Copy this run's outputs into an immutable directory and seal it.

    `outputs` and `optional` default to None and are resolved from the module globals HERE rather
    than bound as default arguments. Binding them as defaults captured the lists at import time, so
    reassigning `run_archive.RUN_OUTPUTS` was accepted and silently ignored -- a caller would have
    archived the old set while believing it had changed it.
    """
    outputs = RUN_OUTPUTS if outputs is None else outputs
    optional = RUN_OUTPUTS_OPTIONAL if optional is None else optional
    missing = []
    for rel in outputs:
        p = _REPO / rel
        if not p.exists():
            missing.append({'path': rel, 'why': 'ABSENT'})
        elif p.stat().st_size == 0:
            missing.append({'path': rel, 'why': 'EMPTY'})
    if missing:
        return Outcome.fail(
            'RUN_OUTPUT_MISSING_OR_EMPTY',
            f'{len(missing)} required run output is absent or empty, so there is no complete run to '
            f'archive. Archiving anyway would leave a hole that looks like a finished run forever '
            f'afterwards.',
            missing=missing)

    cv, cv_detail = _code_version()
    rid = run_id(slate, when=when, code_version=cv)
    d = RUNS / rid
    if is_sealed(d):
        return Outcome.fail(
            'RUN_ALREADY_SEALED',
            f'{rid} is already sealed. An immutable record that can be rewritten is not a record; '
            f'archive under a new run id instead.',
            run_id=rid, directory=_rel(d))
    d.mkdir(parents=True, exist_ok=True)

    files = {}
    for rel in tuple(outputs) + tuple(optional):
        src = _REPO / rel
        if not src.exists():
            continue
        dest = d / (pathlib.Path(rel).name + '.gz')
        if dest.exists():
            return Outcome.fail(
                'ARCHIVED_NAME_COLLISION',
                f'two run outputs would archive to the same name {dest.name}. The archive is keyed '
                f'on basename, so a collision would silently keep one and lose the other.',
                collision=dest.name)
        raw = src.read_bytes()
        with gzip.open(dest, 'wb', compresslevel=9) as fh:
            fh.write(raw)
        files[dest.name] = {'source_path': rel,
                            'sha256': hashlib.sha256(raw).hexdigest(),
                            'SHA256_IS_OF': 'the uncompressed content, so it compares to the live '
                                            'output path directly',
                            'bytes_uncompressed': len(raw),
                            'bytes_stored_gzip': dest.stat().st_size,
                            'required': rel in outputs}

    seal = {
        'ARTIFACT': 'RUN_SEAL',
        'run_id': rid,
        'slate': slate,
        'sealed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'code_version': cv,
        'code_version_short': hashlib.sha256(str(cv).encode()).hexdigest()[:12],
        'CODE_VERSION_IS_HASHED_INTO_THE_ID': (
            'the run id carries sha256(code_version)[:12], not a truncation of the version string. '
            'The commit sha alone is 40 characters, so a fixed-width truncation dropped the '
            'dirty-working-tree marker and let a dirty and a clean tree share an id.'),
        'code_identity': cv_detail,
        'note': note,
        'n_files': len(files),
        'files': files,
        'IMMUTABLE': ('this directory is a record of one run. Nothing in it may be edited. A rerun '
                      'produces a NEW run id; it does not update this one.'),
        'WHAT_A_SEAL_PROVES_AND_DOES_NOT': (
            'it proves these bytes are the bytes this run produced, and that they have not moved '
            'since. It does NOT prove the run was correct, and it does NOT make the run '
            'reproducible on its own -- reproduction also needs the inputs, which the lineage '
            'block inside each artifact names.'),
    }
    (d / SEAL_NAME).write_text(json.dumps(seal, indent=2))
    CURRENT.write_text(json.dumps({
        'ARTIFACT': 'CURRENT_RUN',
        'run_id': rid,
        'directory': _rel(d),
        'sealed_at_utc': seal['sealed_at_utc'],
        'POINTER_SEMANTICS': (
            'the fixed paths under nfl/dfs/salaries are the CURRENT run and are overwritten by the '
            'next one. This names which sealed directory they currently correspond to. If the '
            'fixed paths have been rebuilt since, they correspond to nothing archived yet, which '
            'verify_current() detects.'),
    }, indent=2))
    return Outcome.ok('RUN_ARCHIVED', value={
        'run_id': rid, 'directory': _rel(d), 'n_files': len(files),
        'code_version': cv})


def verify(rid: str) -> Outcome:
    """Recompute every archived digest. FAILs naming the file if a byte has moved."""
    d = RUNS / rid
    sp = d / SEAL_NAME
    if not sp.exists():
        return Outcome.blocked('RUN_NOT_SEALED', f'{rid} has no {SEAL_NAME}', cause=Cause.DATA)
    seal = json.loads(sp.read_text())
    moved, absent, unreadable = [], [], []
    for name, rec in (seal.get('files') or {}).items():
        f = d / name
        if not f.exists():
            absent.append(name)
            continue
        try:
            with gzip.open(f, 'rb') as fh:
                now = hashlib.sha256(fh.read()).hexdigest()
        except Exception as e:  # noqa: BLE001
            unreadable.append({'file': name, 'error': f'{type(e).__name__}: {e}'})
            continue
        if now != rec['sha256']:
            moved.append({'file': name, 'sealed': rec['sha256'][:12], 'current': now[:12]})
    extra = sorted(p.name for p in d.iterdir()
                   if p.name != SEAL_NAME and p.name not in (seal.get('files') or {}))
    if moved or absent or extra or unreadable:
        return Outcome.fail(
            'SEALED_RUN_HAS_CHANGED',
            f'{rid}: {len(moved)} file(s) changed, {len(absent)} removed, {len(extra)} added and '
            f'{len(unreadable)} unreadable since the seal. A sealed run is a record, and a record '
            f'that changed is not one.',
            moved=moved, absent=absent, added=extra, unreadable=unreadable)
    return Outcome.ok('SEALED_RUN_INTACT', value={
        'run_id': rid, 'n_files': len(seal.get('files') or {}),
        'code_version': seal.get('code_version'), 'sealed_at_utc': seal.get('sealed_at_utc')})


def verify_current() -> Outcome:
    """Do the fixed production paths still match the run CURRENT.json names?"""
    if not CURRENT.exists():
        return Outcome.blocked('NO_CURRENT_RUN', f'{CURRENT.name} missing; nothing archived yet',
                               cause=Cause.DATA)
    cur = json.loads(CURRENT.read_text())
    rid = cur['run_id']
    v = verify(rid)
    if v.state.name != 'PASS':
        return v
    seal = json.loads((RUNS / rid / SEAL_NAME).read_text())
    drifted = []
    for name, rec in seal['files'].items():
        live = digest(_REPO / rec['source_path'])
        if live is None:
            drifted.append({'path': rec['source_path'], 'why': 'LIVE_PATH_ABSENT'})
        elif live != rec['sha256']:
            drifted.append({'path': rec['source_path'], 'why': 'REBUILT_SINCE_ARCHIVE'})
    if drifted:
        return Outcome.deferred(
            'CURRENT_PATHS_AHEAD_OF_ARCHIVE',
            f'{len(drifted)} live output differs from the newest sealed run {rid}',
            owed='archive the current run',
            drifted=drifted,
            note=('this is DEFERRED, not a failure: the live paths being newer than the archive is '
                  'the normal state between a rebuild and the next archive. It is visible as an '
                  'outstanding debt rather than silently fine.'))
    return Outcome.ok('CURRENT_MATCHES_ARCHIVE', value={'run_id': rid, 'n_files': len(seal['files'])})


def list_runs() -> Outcome:
    if not RUNS.exists():
        return Outcome.blocked('NO_RUNS_DIRECTORY', f"{_rel(RUNS)} does not exist",
                               cause=Cause.DATA)
    rows = []
    for d in sorted(p for p in RUNS.iterdir() if p.is_dir()):
        sp = d / SEAL_NAME
        if not sp.exists():
            rows.append({'run_id': d.name, 'state': 'UNSEALED'})
            continue
        s = json.loads(sp.read_text())
        v = verify(d.name)
        rows.append({'run_id': d.name, 'slate': s.get('slate'),
                     'sealed_at_utc': s.get('sealed_at_utc'),
                     'code_version': s.get('code_version'), 'n_files': s.get('n_files'),
                     'state': ('INTACT' if v.state.name == 'PASS' else v.code)})
    return Outcome.ok('RUNS_LISTED', value={'n_runs': len(rows), 'runs': rows})


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=('archive', 'list', 'verify', 'verify-current'))
    ap.add_argument('--slate', default='DK_NFL_WEEK3_2026')
    ap.add_argument('--run-id')
    ap.add_argument('--note')
    a = ap.parse_args()
    if a.action == 'archive':
        o = archive(a.slate, note=a.note)
    elif a.action == 'list':
        o = list_runs()
    elif a.action == 'verify':
        o = verify(a.run_id)
    else:
        o = verify_current()
    print(o.state, o.code)
    print(json.dumps(o.value if o.state.name == 'PASS' else (o.detail, o.evidence),
                     indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
