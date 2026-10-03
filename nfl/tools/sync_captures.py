#!/usr/bin/env python3.12
"""Bring the scheduled captures from the capture branch into this working tree, verified.

WHY THIS EXISTS. The capture surface runs every thirty minutes on GitHub and writes depth charts,
weekly rosters, injuries and schedules to `capture-prod` (measured 2026-10-02: every source captured
at 04:57Z that morning). The projection pipeline reads `nfl/vintage` from the checkout it runs in,
and nothing carried the captures across, so the owner was relaying roster and depth files by hand
while the system already owned their acquisition. This closes that gap without a merge: the
manifest is append-only and the development branch's copy is an exact PREFIX of the live one, so
a sync is the missing manifest rows appended byte-for-byte plus the blobs they name, each verified
against the sha256 the manifest recorded when it was captured.

WHAT IT REFUSES, BY NAME. A fetch that fails (BLOCKED, cause NETWORK: the executor, not the world).
A local manifest that is not a prefix of the remote one (SYNC_MANIFEST_DIVERGED: somebody wrote to
one side; nothing is appended). A blob whose bytes do not hash to what its manifest row says
(SYNC_BLOB_HASH_MISMATCH: the file is removed again and nothing is appended). A sync that brings
nothing is reported as SYNC_NOTHING_NEW with the remote sha, never as success-with-nothing.

PROVENANCE. Every sync appends one row to nfl/vintage/SYNC_PROVENANCE.jsonl: remote branch and
commit, capture ids appended, blobs written with their hashes, the clock. A capture's own
retrieved_at is untouched: syncing moves bytes, not evidence time.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome, Cause  # noqa: E402

REMOTE = 'origin'
BRANCH = 'capture-prod'
MANIFEST = 'nfl/vintage_manifest.jsonl'
PROVENANCE = _REPO / 'nfl/vintage/SYNC_PROVENANCE.jsonl'


def _git(*args, retries: int = 3, **kw) -> subprocess.CompletedProcess:
    last = None
    for i in range(retries):
        p = subprocess.run(['git', *args], cwd=_REPO, capture_output=True, **kw)
        if p.returncode == 0:
            return p
        last = p
        time.sleep(2 ** i)
    return last


def plan(local_lines: list, remote_lines: list) -> Outcome:
    """Pure: which rows to append, or why not. Lines are exact bytes-as-text, newline-stripped."""
    n = len(local_lines)
    forked = None
    if remote_lines[:n] == local_lines:
        new = remote_lines[n:]
    else:
        # TWO APPEND-ONLY LOGS THAT FORKED. Measured 2026-10-02: the development branch's manifest
        # carries 646 rows from row 6111 on (a 2026-09-10 backfill and owner-relayed captures) that
        # capture-prod never saw, while capture-prod carries every scheduled capture since. Each row
        # is immutable, self-describing evidence keyed by its own capture_id and blob, so the union
        # is well defined: the remote-only rows are appended in remote order (the newest lands last,
        # which is what "latest by file order" readers rely on), the local-only rows stay, and a
        # blob path present on both sides with different hashes is a conflict that refuses the sync.
        first = next((i for i in range(min(n, len(remote_lines))) if remote_lines[i] != local_lines[i]),
                     min(n, len(remote_lines)))
        local_set = set(local_lines)
        new = [ln for ln in remote_lines if ln not in local_set]
        remote_set = set(remote_lines)
        local_only = [ln for ln in local_lines if ln not in remote_set]
        lb = {}
        for ln in local_only:
            try:
                v = (json.loads(ln).get('value') or {})
            except ValueError:
                continue
            if v.get('blob'):
                lb[v['blob']] = v.get('blob_file_sha256')
        for ln in new:
            try:
                v = (json.loads(ln).get('value') or {})
            except ValueError:
                continue
            b = v.get('blob')
            if b and b in lb and lb[b] and v.get('blob_file_sha256') and lb[b] != v['blob_file_sha256']:
                return Outcome.fail('SYNC_BLOB_CONFLICT_ACROSS_FORK',
                                    f'{b} is named on both sides with different hashes', cause=Cause.DATA,
                                    blob=b, first_difference_row=first)
        forked = {'fork_row': first, 'n_local_only_rows': len(local_only), 'n_remote_only_rows': len(new),
                  'MEANING': 'union of two append-only evidence logs; no row was altered or dropped'}
    rows = []
    for line in new:
        try:
            rows.append(json.loads(line))
        except ValueError:
            return Outcome.fail('SYNC_MANIFEST_ROW_UNPARSEABLE', line[:120], cause=Cause.DATA)
    blobs = {}
    for r in rows:
        v = r.get('value') or {}
        if r.get('state') == 'PASS' and v.get('blob'):
            blobs[v['blob']] = v.get('blob_file_sha256')
    return Outcome.ok('SYNC_PLANNED', {'new_lines': new, 'rows': rows, 'blobs': blobs, 'forked': forked},
                      f'{len(new)} manifest row(s) to append, {len(blobs)} blob(s) named'
                      + (f"; FORKED at row {forked['fork_row']}, {forked['n_local_only_rows']} local-only row(s) kept" if forked else ''),
                      n_rows=len(new), n_blobs=len(blobs), forked=forked)


def verify_blob(data: bytes, expected_sha256) -> Outcome:
    got = hashlib.sha256(data).hexdigest()
    if not expected_sha256:
        # OWNER RULE 1 (2026-10-02): a blob with nothing to verify against was not verified. This
        # used to return PASS SYNC_BLOB_VERIFIED with verified=False in the evidence, which is a
        # verdict that contradicts its own code. BLOCKED/NOT_EXECUTED names the missing hash; the
        # bytes' own digest is carried so the caller can record what it copied.
        return Outcome.not_executed(
            'SYNC_BLOB_HASH_NOT_RECORDED',
            f'manifest row carries no blob_file_sha256, so there is nothing to verify the bytes '
            f'against; they hash to {got[:16]} and that is a record, not a verification',
            missing='blob_file_sha256', sha256=got, verified=False)
    if got != expected_sha256:
        return Outcome.fail('SYNC_BLOB_HASH_MISMATCH', f'expected {expected_sha256[:16]}, got {got[:16]}',
                            cause=Cause.DATA, expected=expected_sha256, got=got)
    return Outcome.ok('SYNC_BLOB_VERIFIED', got, 'hash matches the manifest', verified=True)


def run(*, dry_run: bool = False, show=None, fetch=None) -> Outcome:
    """`show(sha, path) -> bytes` and `fetch() -> sha` are injectable for tests."""
    t0 = time.time()
    if fetch is None:
        def fetch():
            p = _git('fetch', REMOTE, BRANCH)
            if p.returncode != 0:
                return None
            return _git('rev-parse', 'FETCH_HEAD').stdout.decode().strip()
    if show is None:
        def show(sha, path):
            p = _git(sha and f'show' or 'show', f'{sha}:{path}', retries=1)
            return p.stdout if p.returncode == 0 else None
    sha = fetch()
    if not sha:
        return Outcome.blocked('SYNC_FETCH_FAILED', f'git fetch {REMOTE} {BRANCH} did not succeed; '
                               f'this is the executor, not the capture branch', cause=Cause.NETWORK)
    remote_raw = show(sha, MANIFEST)
    if remote_raw is None:
        return Outcome.fail('SYNC_REMOTE_MANIFEST_ABSENT', f'{MANIFEST} not at {sha[:12]}', cause=Cause.DATA)
    local_path = _REPO / MANIFEST
    local_lines = local_path.read_text().splitlines() if local_path.exists() else []
    remote_lines = remote_raw.decode().splitlines()
    p = plan(local_lines, remote_lines)
    if p.state.value != 'PASS':
        return p
    v = p.value
    if not v['new_lines']:
        return Outcome.ok('SYNC_NOTHING_NEW', {'remote_sha': sha, 'n_rows_local': len(local_lines)},
                          f'local manifest already matches {BRANCH}@{sha[:12]} ({len(local_lines)} rows)')
    # OWNER RULE 1 (2026-10-02): a manifest row without blob_file_sha256 (3,086 of 7,748 PASS rows
    # on 2026-10-02, all from writers before the durable-retention ruling) names a blob this sync can
    # copy but cannot verify. The union of the two evidence logs still proceeds -- the rows are
    # immutable and the bytes come from the named commit -- but the blob is recorded as UNVERIFIED
    # and the sync verdict is INCOMPLETE naming each one, never a PASS that treats it as verified.
    written, skipped, unverified, nbytes = [], [], [], 0
    for blob, expected in sorted(v['blobs'].items()):
        dst = _REPO / blob
        if dst.exists():
            ver = verify_blob(dst.read_bytes(), expected)
            if ver.state.value == 'PASS':
                skipped.append(blob)
                continue
            if ver.non_evidentiary:
                # Local bytes exist and nothing says whether they are the right ones. They are kept
                # (never overwritten on no evidence) and the verdict carries the gap.
                unverified.append({'blob': blob, 'where': 'local', 'code': ver.code,
                                   'sha256': ver.evidence.get('sha256')})
                skipped.append(blob)
                continue
            return Outcome.fail('SYNC_LOCAL_BLOB_CONFLICTS', f'{blob} exists locally with a different hash',
                                cause=Cause.DATA, blob=blob)
        data = show(sha, blob)
        if data is None:
            return Outcome.fail('SYNC_BLOB_ABSENT_ON_REMOTE', f'{blob} named by the manifest is not at {sha[:12]}',
                                cause=Cause.DATA, blob=blob)
        ver = verify_blob(data, expected)
        if ver.state.value == 'FAIL':
            return Outcome.fail('SYNC_BLOB_HASH_MISMATCH', f'{blob}: {ver.detail}', cause=Cause.DATA, blob=blob)
        verified = ver.state.value == 'PASS'
        digest = ver.value if verified else ver.evidence.get('sha256')
        if not verified:
            unverified.append({'blob': blob, 'where': 'remote', 'code': ver.code, 'sha256': digest})
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
        written.append({'blob': blob, 'sha256': digest, 'bytes': len(data), 'verified': verified,
                        **({} if verified else {'unverified_because': ver.code})})
        nbytes += len(data)
    capture_ids = sorted({r.get('capture_id') for r in v['rows'] if r.get('capture_id')})
    record = {
        'synced_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'remote': f'{REMOTE}/{BRANCH}', 'remote_sha': sha, 'dry_run': dry_run,
        'manifest_rows_before': len(local_lines), 'manifest_rows_after': len(local_lines) + len(v['new_lines']),
        'n_rows_appended': len(v['new_lines']), 'capture_ids': capture_ids, 'forked': v.get('forked'),
        'capture_id_range': [capture_ids[0], capture_ids[-1]] if capture_ids else None,
        'n_blobs_written': len(written), 'n_blobs_already_present': len(skipped), 'bytes_written': nbytes,
        'n_blobs_unverified': len(unverified), 'blobs_unverified': unverified,
        'blobs': written, 'elapsed_seconds': round(time.time() - t0, 1),
        'EVIDENCE_TIME_UNTOUCHED': 'each row keeps its own retrieved_at; syncing moves bytes, not evidence time',
    }
    if not dry_run:
        with local_path.open('a') as f:
            f.write(''.join(line + '\n' for line in v['new_lines']))
        PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
        with PROVENANCE.open('a') as f:
            f.write(json.dumps(record, sort_keys=True) + '\n')
    code = ('SYNC_DRY_RUN' if dry_run else 'SYNC_APPLIED') + ('_FORKED_UNION' if v.get('forked') else '')
    summary = (f"{len(v['new_lines'])} row(s), {len(written)} blob(s), {nbytes/1048576:.1f} MiB from "
               f"{BRANCH}@{sha[:12]}; captures {record['capture_id_range']}")
    if unverified:
        # OWNER RULE 1 (2026-10-02): the sync ran, but its verification ran on part of its input.
        # Codes emitted here, for the reader who greps: SYNC_DRY_RUN_UNVERIFIED_BLOBS,
        # SYNC_APPLIED_UNVERIFIED_BLOBS, SYNC_DRY_RUN_FORKED_UNION_UNVERIFIED_BLOBS,
        # SYNC_APPLIED_FORKED_UNION_UNVERIFIED_BLOBS.
        n_named = len(v['blobs'])
        return Outcome.incomplete(
            code + '_UNVERIFIED_BLOBS',
            summary + f"; {len(unverified)} of {n_named} blob(s) have no blob_file_sha256 in their "
                      f"manifest row and were NOT verified: {[u['blob'] for u in unverified][:5]}",
            expected=n_named, got=n_named - len(unverified), record=record,
            unverified=[u['blob'] for u in unverified], n_rows=len(v['new_lines']), n_blobs=len(written))
    return Outcome.ok(code, record, summary, n_rows=len(v['new_lines']), n_blobs=len(written))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    o = run(dry_run=a.dry_run)
    print(o.state.value, o.code)
    print(' ', o.detail)
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
