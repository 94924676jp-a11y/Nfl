"""Promote a validated capture surface to `capture-prod`. Governed, allowlisted.

D24, owner decision 2026-09-15. The scheduled workflow used
`actions/checkout@v4` with no `ref:`, so a `schedule:` trigger took the DEFAULT
branch -- and against origin/main three capture modules DID NOT EXIST:
payload_contract.py, persisted_provenance.py, evidence_layers.py. D20's
row_container, D22's payload contracts and D24's own persisted-digest guard were
all absent from the only code that actually captures, while their tests passed
on the development branch.

THE DECISION IMPLEMENTED HERE

    development -> capture-specific verification -> approved capture release
                -> capture-prod -> scheduled execution

General model and research development is NOT merged to main, and a
reconciliation cadence is NOT the deployment control. `capture-prod` carries the
validated capture surface and nothing else.

THE ALLOWLIST IS THE POINT. A promotion that could carry a forecasting change
would let model development reach production through the capture door, which is
the failure this whole mechanism exists to prevent. Anything outside
`ALLOWED_PREFIXES` is refused by name, and the refusal lists what it saw.

A MUTABLE BRANCH NAME IS NOT PROVENANCE. `ref: capture-prod` says which branch;
it does not say which commit ran. So a release records the RESOLVED SHA, and the
capture job records the SHA it actually executed, and the two are compared. A
job that cannot prove which commit it ran is a job whose output cannot be
attributed.

WHAT THIS MODULE REFUSES TO DO. It does not push, it does not create branches on
a remote, and it does not approve its own release. It prepares and verifies; the
act of publishing is a human's, or a workflow's operating under a human's
credentials.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import posixpath
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.capture import capture_identity as CI                       # noqa: E402

SPEC_VERSION = 'capture_release/1.0.0'
PROD_BRANCH = 'capture-prod'

#: EVERYTHING a scheduled capture needs, and nothing a forecast needs.
#: Deliberately narrow. Widening it is a governance change, not a convenience.
ALLOWED_PREFIXES = (
    'nfl/capture/',
    'nfl/tools/capture_vintage.py',
    # THE RELEASE TOOL ITSELF TRAVELS. capture-prod runs --check-executor before
    # it fetches anything, so the checker has to be there. Added deliberately
    # after this allowlist refused the first promotion attempt for omitting it,
    # which is the guard working rather than a reason to route around it.
    #
    # It is in the ALLOWLIST (what may be promoted) and NOT in
    # capture_identity.CAPTURE_SURFACE (what is hashed as deciding a capture's
    # MEANING). Those are different questions: the surface is the code whose
    # change would change what a row means; the allowlist is the code permitted
    # to reach production at all.
    'nfl/tools/capture_release.py',
    'nfl/tools/check_retention.py',
    'nfl/tools/preflight_t90.py',
    'nfl/tools/gen_t90_schedule.py',
    'nfl/tools/nflwrite.py',
    'nfl/identity/',
    'sportsplatform/governance/',
    '.github/workflows/',
)

#: Paths that must NEVER appear in a capture release even if a prefix would
#: otherwise admit them. Belt and braces: a forecasting module that migrated
#: under an allowed prefix would otherwise ride along silently.
DENY_SUBSTRINGS = (
    'nfl/production/',
    'nfl/research/',
    'nfl/prospective/',
    'nfl/product/',
)

#: THE DEVELOPMENT-SIDE LEDGER. Append-only, holds every release ever built,
#: and carries the resolved development commit each was built from.
RELEASES = _REPO / 'nfl' / 'capture' / 'CAPTURE_RELEASES.jsonl'

#: THE DEPLOYED-SIDE RECORD, and it exists because of a regress rather than an
#: oversight. A ledger row is appended AFTER the promotion commit is made, so
#: `CAPTURE_RELEASES.jsonl` can never be inside the release it describes --
#: and putting it in the NEXT release does not help, because that release's row
#: is appended after it too. Measured on CAPREL-631e3d2212cba417: 11 changed
#: paths, no ledger among them.
#:
#: So capture-prod carries ONE self-describing record instead, pinned on the
#: SURFACE DIGEST. The digest is computable before the commit exists and does
#: not move when the commit does, which is exactly the property the ledger row
#: lacks. Without this file a clean capture-prod checkout answers
#: NO_APPROVED_CAPTURE_RELEASE and every scheduled capture refuses to run --
#: measured 2026-09-15, which is what sent this repair.
APPROVED = _REPO / 'nfl' / 'capture' / 'APPROVED_RELEASE.json'


def _git(*args):
    return subprocess.run(['git', *args], capture_output=True, text=True,
                          cwd=_REPO)


def resolve(ref: str) -> Outcome:
    """The commit a ref points at right now. A name is not a commit."""
    r = _git('rev-parse', '--verify', f'{ref}^{{commit}}')
    if r.returncode != 0:
        return Outcome.blocked('CAPTURE_REF_UNRESOLVABLE',
                               f'{ref}: {r.stderr.strip()}',
                               cause=Cause.ENVIRONMENT, ref=ref)
    return Outcome.ok('CAPTURE_REF_RESOLVED', value=r.stdout.strip(), ref=ref)


def path_is_allowed(path: str) -> bool:
    """Allowlisted, after normalisation, and never escaping the tree.

    NORMALISE FIRST. The first cut checked the raw string, so
    `nfl/capture/../production/layers.py` passed: it startswith an allowed
    prefix, and the literal `nfl/production/` the deny list looks for is not in
    it. git diff --name-only does not emit `..` today -- and "the caller never
    sends that" is exactly the assumption that turns into a defect the first
    time some other caller does. Caught by this module's own test.
    """
    if not isinstance(path, str) or not path.strip():
        return False
    norm = posixpath.normpath(path.replace('\\', '/'))
    if norm.startswith('/') or norm == '..' or norm.startswith('../'):
        return False
    if any(d in norm for d in DENY_SUBSTRINGS):
        return False
    return any(norm == p.rstrip('/') or norm.startswith(p)
               for p in ALLOWED_PREFIXES)


def assert_allowlisted(paths) -> Outcome:
    """Refuse a promotion carrying anything outside the capture surface."""
    bad = sorted(p for p in paths if not path_is_allowed(p))
    if bad:
        return Outcome.fail(
            'CAPTURE_RELEASE_CARRIES_NON_CAPTURE_PATHS',
            f'{len(bad)} path(s) are outside the capture allowlist: '
            f'{bad[:10]}. A capture release that can carry a forecasting '
            f'change lets model development reach production through the '
            f'capture door.',
            rejected=bad, n_rejected=len(bad),
            allowed_prefixes=list(ALLOWED_PREFIXES))
    return Outcome.ok('CAPTURE_RELEASE_PATHS_ALLOWLISTED',
                      value=sorted(paths), n_paths=len(paths))


def diff_paths(from_ref: str, to_ref: str) -> Outcome:
    r = _git('diff', '--name-only', f'{from_ref}..{to_ref}')
    if r.returncode != 0:
        return Outcome.blocked('CAPTURE_DIFF_FAILED', r.stderr.strip(),
                               cause=Cause.ENVIRONMENT)
    paths = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    return Outcome.ok('CAPTURE_DIFF_READ', value=paths, n_paths=len(paths))


def release_id(capture_code_sha: str, resolved_sha: str) -> str:
    """Stable, derived, and not a timestamp -- two releases of the same code
    from the same commit are the same release."""
    h = hashlib.sha256(f'{capture_code_sha}:{resolved_sha}'.encode())
    return 'CAPREL-' + h.hexdigest()[:16]


def build_release(source_ref='HEAD') -> Outcome:
    """Verify and describe a candidate capture release. Publishes nothing."""
    res = resolve(source_ref)
    if res.state is not State.PASS:
        return res
    resolved = res.value

    drift = CI.drift()
    if drift['verdict'] != 'MATCHES':
        return Outcome.fail(
            'CAPTURE_SURFACE_NOT_VALIDATED',
            f"the source tree does not match its own validated contract: "
            f"{drift['verdict']}. {drift.get('detail', '')} Promote a tree "
            f"that has been validated, not one that merely builds.",
            **{k: v for k, v in drift.items() if k != 'detail'})

    prod = resolve(PROD_BRANCH)
    if prod.state is State.PASS:
        d = diff_paths(prod.value, resolved)
        if d.state is not State.PASS:
            return d
        allowed = assert_allowlisted(d.value)
        if allowed.state is not State.PASS:
            return allowed
        changed = d.value
    else:
        # FIRST RELEASE. There is no prod branch to diff against, so the
        # allowlist is applied to the capture surface itself rather than to a
        # diff. Stated explicitly because "no diff" must not read as "nothing
        # to check".
        changed = None
        allowed = assert_allowlisted(list(CI.CAPTURE_SURFACE))
        if allowed.state is not State.PASS:
            return allowed

    surf = CI.surface()
    code_sha = CI.capture_code_sha(surf)
    rid = release_id(code_sha, resolved)
    doc = {
        'spec_version': SPEC_VERSION,
        'capture_release_id': rid,
        'capture_code_sha': code_sha,
        'capture_surface': surf,
        'source_ref': source_ref,
        'resolved_source_sha': resolved,
        'prod_branch': PROD_BRANCH,
        'prod_sha_before': prod.value if prod.state is State.PASS else None,
        'changed_paths': changed,
        'n_changed_paths': None if changed is None else len(changed),
        'allowlist': list(ALLOWED_PREFIXES),
        'deny_substrings': list(DENY_SUBSTRINGS),
        'parser_version': CI.SPEC_VERSION,
        'source_contract_version': _source_contract_version(),
        'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'published': False,
        'note': ('A release is PREPARED here and published by a human or a '
                 'credentialed workflow. This module does not push and does '
                 'not approve its own release.'),
    }
    return Outcome.ok('CAPTURE_RELEASE_BUILT', value=doc,
                      detail=f'{rid} from {resolved[:12]} '
                             f'({0 if changed is None else len(changed)} '
                             f'capture path(s) changed)',
                      capture_release_id=rid, capture_code_sha=code_sha,
                      resolved_source_sha=resolved)


def _source_contract_version():
    """The declared payload-contract shape, so a row proves which one ran."""
    try:
        from nfl.capture import payload_contract as PC
        return getattr(PC, 'SPEC_VERSION', None) or 'payload_contract/unknown'
    except Exception:                                            # noqa: BLE001
        return None


def assert_executor_matches_release(release, executed_sha=None) -> Outcome:
    """FAIL CLOSED if the running surface is not the approved release.

    This is what the capture job calls before it fetches anything. A job that
    discovers afterwards that it ran the wrong code has already written rows
    nobody can attribute.
    """
    if not release:
        return Outcome.fail(
            'NO_APPROVED_CAPTURE_RELEASE',
            'the capture job has no approved release to check itself against. '
            'Running anyway would produce rows whose implementation cannot be '
            'proven, which is the defect this exists to end.')
    surf = CI.surface()
    running = CI.capture_code_sha(surf)
    want = release.get('capture_code_sha')
    if running != want:
        absent = sorted(r for r, v in surf.items()
                        if v is None
                        and (release.get('capture_surface') or {}).get(r))
        return Outcome.fail(
            'CAPTURE_EXECUTOR_SURFACE_MISMATCH',
            f'the running capture surface hashes to {running[:16]} but the '
            f'approved release {release.get("capture_release_id")} is '
            f'{str(want)[:16]}. '
            + (f'{len(absent)} approved module(s) are ABSENT here: {absent}. '
               if absent else '')
            + 'Refusing to capture with unapproved code.',
            running_capture_code_sha=running, approved_capture_code_sha=want,
            absent=absent,
            capture_release_id=release.get('capture_release_id'))
    # THE SURFACE IS IDENTITY; THE COMMIT IS PROVENANCE. These were conflated,
    # and the conflation made the gate self-invalidating: the capture job
    # COMMITS ITS CAPTURED BYTES BACK to the branch it checked out, so the tip
    # moves on every run. Keyed on commit equality, the gate would have passed
    # the first capture and refused every capture after it -- invalidating
    # itself by operating normally, which is not a gate.
    #
    # The owner's requirement is that the resolved sha be RECORDED and that the
    # job fail closed when the deployed SURFACE does not match. Both hold here.
    # The surface digest above is the fail-closed identity; data commits do not
    # move it. The commit is recorded, and still refuses a genuinely unrelated
    # commit -- what it no longer does is refuse its own output.
    commit = _commit_provenance(release, executed_sha)
    if commit['state'] == 'DIVERGED_FROM_RELEASE_COMMIT':
        return Outcome.fail(
            'CAPTURE_EXECUTOR_COMMIT_MISMATCH',
            f'the job reports executing {str(executed_sha)[:12]}, which does '
            f'not descend from the approved release commit '
            f'{str(release.get("resolved_source_sha"))[:12]}. A branch name is '
            f'not provenance; the commit is.',
            executed_sha=executed_sha,
            approved_sha=release.get('resolved_source_sha'),
            commit_provenance=commit['state'])
    return Outcome.ok(
        'CAPTURE_EXECUTOR_MATCHES_RELEASE',
        value=release.get('capture_release_id'),
        detail=f'running surface {running[:16]} matches approved release '
               f'{release.get("capture_release_id")} '
               f'[commit {commit["state"]}]',
        capture_release_id=release.get('capture_release_id'),
        capture_code_sha=running, executed_sha=executed_sha,
        # NOT_ESTABLISHED IS CARRIED, NEVER DROPPED. An ancestry check that
        # could not run is not an ancestry check that passed, and a summary
        # that omits it would read as though it had.
        commit_provenance=commit['state'],
        commit_provenance_detail=commit['detail'],
        release_record_source=release.get('_record_source'))


def _commit_provenance(release, executed_sha):
    """What can honestly be said about the commit this executor is running.

    Five states, and the undecidable one is named rather than rounded to yes.
    """
    want = release.get('resolved_source_sha')
    if not executed_sha:
        return {'state': 'EXECUTED_SHA_NOT_REPORTED',
                'detail': 'the job did not report the commit it resolved'}
    if not want:
        return {'state': 'RELEASE_PINS_NO_COMMIT',
                'detail': 'the deployed record pins a surface digest, not a '
                          'commit; the development ledger holds the commit'}
    if executed_sha == want:
        return {'state': 'MATCHES_RELEASE_COMMIT', 'detail': ''}
    r = _git('merge-base', '--is-ancestor', want, executed_sha)
    if r.returncode == 0:
        return {'state': 'DESCENDS_FROM_RELEASE_COMMIT',
                'detail': f'{executed_sha[:12]} descends from {want[:12]}; '
                          f'the capture job commits its own output, so this '
                          f'is the normal steady state'}
    if r.returncode == 1:
        return {'state': 'DIVERGED_FROM_RELEASE_COMMIT', 'detail': ''}
    return {'state': 'COMMIT_ANCESTRY_NOT_ESTABLISHED',
            'detail': f'git could not decide: {r.stderr.strip()[:200]}. This '
                      f'is NOT ASKED, not a pass; the surface digest is what '
                      f'is holding the gate closed here'}


def deployable_record(doc) -> dict:
    """The release record that TRAVELS to capture-prod.

    It deliberately drops `resolved_source_sha`. That field names the commit the
    release was built FROM, and the executor runs a capture-prod commit which
    will never be it -- so shipping it would ship a comparison guaranteed to
    fail. The commit stays recorded on the development-side ledger, which is
    where it can be written after the fact without a regress.
    """
    keep = ('spec_version', 'capture_release_id', 'capture_code_sha',
            'capture_surface', 'prod_branch', 'allowlist', 'deny_substrings',
            'parser_version', 'source_contract_version', 'built_at_utc',
            'changed_paths', 'n_changed_paths')
    out = {k: doc[k] for k in keep if k in doc}
    out['promoted_from_development_sha'] = doc.get('resolved_source_sha')
    out['resolved_source_sha_recorded_in'] = (
        'nfl/capture/CAPTURE_RELEASES.jsonl on the development branch')
    out['published'] = True
    out['note'] = (
        'The deployed copy of an approved capture release. Pinned on the '
        'surface digest, which does not move when the branch does. The '
        'executor compares its running surface against capture_code_sha and '
        'refuses to fetch anything if they differ.')
    return out


def approved_release(path=None):
    """The release THIS TREE is running under, from whichever record it has.

    TWO RECORDS, DELIBERATELY, and which one is present tells you which tree you
    are on. Development carries the append-only ledger. capture-prod carries the
    single deployed record, because a ledger row cannot be inside the release it
    describes (see APPROVED above). The source is stamped onto the returned
    record so a log never has to guess which one answered.
    """
    if path:
        p = pathlib.Path(path)
        if not p.exists():
            return None
        if p.suffix == '.json':
            rec = json.loads(p.read_text())
            rec['_record_source'] = str(p)
            return rec
        rows = [json.loads(ln) for ln in p.read_text().splitlines()
                if ln.strip()]
        pub = [r for r in rows if r.get('published')]
        if not pub:
            return None
        pub[-1]['_record_source'] = str(p)
        return pub[-1]

    if RELEASES.exists():
        rows = [json.loads(ln) for ln in RELEASES.read_text().splitlines()
                if ln.strip()]
        pub = [r for r in rows if r.get('published')]
        if pub:
            rec = pub[-1]
            rec['_record_source'] = 'CAPTURE_RELEASES.jsonl'
            # BOTH PRESENT MUST AGREE. On the development tree both files
            # exist; if they name different surfaces then the deployed record
            # is stale and the tree cannot say what production is running.
            # Stamped, not silently preferred.
            if APPROVED.exists():
                try:
                    dep = json.loads(APPROVED.read_text())
                except json.JSONDecodeError:
                    dep = {}
                if dep.get('capture_code_sha') != rec.get('capture_code_sha'):
                    rec['_record_source'] = (
                        'CAPTURE_RELEASES.jsonl (DISAGREES WITH '
                        'APPROVED_RELEASE.json)')
            return rec

    if APPROVED.exists():
        rec = json.loads(APPROVED.read_text())
        rec['_record_source'] = 'APPROVED_RELEASE.json'
        return rec
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', action='store_true',
                    help='verify and describe a candidate release')
    ap.add_argument('--check-executor', action='store_true',
                    help='fail closed unless this tree is the approved release')
    ap.add_argument('--emit-approved-record', action='store_true',
                    help='write nfl/capture/APPROVED_RELEASE.json so the '
                         'deployed tree can prove its own release')
    ap.add_argument('--source-ref', default='HEAD')
    ap.add_argument('--executed-sha', default=None)
    a = ap.parse_args(argv)
    if a.check_executor:
        out = assert_executor_matches_release(approved_release(),
                                              a.executed_sha)
    elif a.emit_approved_record:
        out = build_release(a.source_ref)
        if out.state is State.PASS:
            rec = deployable_record(out.value)
            APPROVED.write_text(json.dumps(rec, indent=2, sort_keys=True) +
                                '\n')
            out = Outcome.ok(
                'CAPTURE_APPROVED_RECORD_WRITTEN',
                value=str(APPROVED),
                detail=f'{rec["capture_release_id"]} pinned on surface '
                       f'{rec["capture_code_sha"][:16]}',
                capture_release_id=rec['capture_release_id'],
                capture_code_sha=rec['capture_code_sha'])
    else:
        out = build_release(a.source_ref)
    print(json.dumps({'state': out.state.value, 'code': out.code,
                      'detail': out.detail,
                      'evidence': out.evidence}, indent=2, default=str))
    return 0 if out.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
