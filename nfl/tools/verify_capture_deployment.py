"""Is the REMOTE scheduler executing validated capture code?

D24 closes only when this passes against the actual remote repository and the
actual default-branch workflows. A local branch that looks correct is exactly
what D24 was: the development branch had every protection and passed every test
while the scheduler ran code missing three modules.

Every check reads the remote via `git show <remote-ref>:<path>`, never the
working tree. Checking the local copy would prove nothing about what runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import capture_identity as CI                     # noqa: E402
from nfl.tools import capture_release as CR                        # noqa: E402

PROD = 'capture-prod'
CAPTURE_WORKFLOWS = ('nfl-capture.yml', 'nfl-t90.yml')

# OWNER RULE 1 (2026-10-02): a check row carrying one of these causes did not
# run on evidence. It is neither a pass nor a true failure, and the verdict
# distinguishes it: DEPLOYMENT_NOT_VERIFIED, never DEPLOYED_AND_VERIFIED.
NON_EVIDENTIARY = ('EMPTY_INPUT', 'NOT_EXECUTED', 'INCOMPLETE')
VERIFIED = 'DEPLOYED_AND_VERIFIED'
NOT_DEPLOYED = 'NOT_DEPLOYED'
NOT_VERIFIED = 'DEPLOYMENT_NOT_VERIFIED'
MODEL_PREFIXES = ('nfl/production/', 'nfl/research/', 'nfl/prospective/',
                  'nfl/product/')


def _git(*a):
    return subprocess.run(['git', *a], capture_output=True, text=True,
                          cwd=_REPO)


def _show(ref, path):
    r = _git('show', ref + ':' + path)
    return r.stdout if r.returncode == 0 else None


def _wf(text):
    """Parse the workflow. THE OLD CHECK WAS `('ref: ' + PROD) in text`, which
    a comment mentioning the branch satisfies just as well as a checkout step
    does. The repaired workflows do carry such a comment, so the substring
    check would now report the pin satisfied whatever the step said -- the D20
    class, arriving in the tool built to prevent it."""
    try:
        import yaml
        return yaml.safe_load(text)
    except Exception:                                            # noqa: BLE001
        return None


def _wf_steps(wf):
    for job in ((wf or {}).get('jobs') or {}).values():
        for s in (job.get('steps') or []):
            if isinstance(s, dict):
                yield s


def _wf_resolve(v, wf):
    if not isinstance(v, str):
        return v
    v = v.strip().strip('"\'')
    m = re.fullmatch(r'\$\{\{\s*env\.(\w+)\s*\}\}', v) \
        or re.fullmatch(r'\$\{?(\w+)\}?', v)
    return ((wf or {}).get('env') or {}).get(m.group(1), v) if m else v


def _wf_refs(wf):
    return [_wf_resolve((s.get('with') or {}).get('ref'), wf)
            for s in _wf_steps(wf) if 'checkout' in str(s.get('uses') or '')]


def _wf_write_targets(wf):
    out = []
    for s in _wf_steps(wf):
        body = s.get('run')
        if not isinstance(body, str):
            continue
        for m in re.finditer(r'git\s+push\s+origin\s+HEAD:(\S+)', body):
            out.append(_wf_resolve(m.group(1), wf))
        for m in re.finditer(r'git\s+pull\s+[^\n]*?origin\s+(\S+)', body):
            out.append(_wf_resolve(m.group(1), wf))
    return out


def _surface_digest_check(deployed: dict, want: dict) -> dict:
    """The surface comparison as one check row.

    OWNER RULE 1 (2026-10-02). This used to be `not differing and not absent`,
    which is True when `want` is empty or nothing could be read from the
    deployed branch: the digest check then PASSED having compared no file. A
    comparison over zero files is BLOCKED/EMPTY_INPUT, carried on the row as
    code SURFACE_DIGEST_EMPTY_INPUT and cause EMPTY_INPUT.
    """
    absent = sorted(k for k, v in deployed.items() if v is None)
    compared = sorted(k for k, v in deployed.items()
                      if v is not None and want.get(k))
    differing = sorted(k for k in compared if deployed[k] != want[k])
    name = 'the deployed surface digest matches the approved release'
    if not compared:
        return {'check': name, 'ok': False, 'code': 'SURFACE_DIGEST_EMPTY_INPUT',
                'cause': 'EMPTY_INPUT', 'n_compared': 0,
                'n_surface_files': len(deployed), 'n_approved_digests': len(want),
                'detail': ('nothing compared: ' + str(len(deployed)) + ' surface '
                           'file(s), ' + str(len(want)) + ' approved digest(s), '
                           + str(len(absent)) + ' absent on the deployed branch. '
                           'A digest check that read no file has not verified '
                           'the surface.')}
    ok = not differing and not absent
    return {'check': name, 'ok': ok, 'n_compared': len(compared),
            'detail': str(differing) if ok or differing else
            str(len(absent)) + ' surface file(s) absent: ' + str(absent)}


def _model_path_checks(parent, remote_sha, changed) -> list:
    """The two deployed-path checks as rows.

    OWNER RULE 1 (2026-10-02). Without a release parent commit or a remote tip
    the diff cannot be taken; the old code skipped both checks silently and
    the verdict read DEPLOYED_AND_VERIFIED with them never run. They are now
    recorded as NOT_EXECUTED. `changed` is the diff's path list when it ran.
    """
    names = ('no model/research/prospective/product path is deployed',
             '  and every deployed path is allowlisted')
    if not (parent and remote_sha):
        why = ('the approved release records no prod_parent_sha'
               if not parent else 'the remote ' + PROD + ' tip is unknown')
        return [{'check': n, 'ok': False, 'code': 'MODEL_PATH_CHECK_NOT_EXECUTED',
                 'cause': 'NOT_EXECUTED',
                 'detail': 'NOT_EXECUTED: ' + why + ', so the deployed diff '
                           'could not be taken'} for n in names]
    if not changed:
        # An empty diff examines no path. "No model path among zero paths" is
        # BLOCKED/EMPTY_INPUT, not a clean deployment.
        return [{'check': n, 'ok': False, 'code': 'MODEL_PATH_CHECK_EMPTY_INPUT',
                 'cause': 'EMPTY_INPUT', 'n_changed': 0,
                 'detail': 'EMPTY_INPUT: the diff between the release parent and '
                           'the deployed tip names no path, so no path was checked'}
                for n in names]
    leaked = sorted(p for p in changed
                    if any(p.startswith(m) for m in MODEL_PREFIXES))
    al = CR.assert_allowlisted(changed)
    rows = [{'check': names[0], 'ok': not leaked, 'detail': str(leaked),
             'n_changed': len(changed)}]
    row = {'check': names[1], 'ok': al.state.name == 'PASS', 'code': al.code,
           'detail': str(len(changed)) + ' changed path(s): ' + al.code}
    if al.non_evidentiary:
        row['cause'] = (al.evidence or {}).get('cause')
    rows.append(row)
    return rows


def _verdict(res: dict) -> dict:
    """Fold the check rows into the verdict, keeping unmeasured apart from failed."""
    failed = [c for c in res['checks'] if not c['ok']]
    unmeasured = [c for c in failed if c.get('cause') in NON_EVIDENTIARY]
    true_failed = [c for c in failed if c.get('cause') not in NON_EVIDENTIARY]
    res['n_checks'] = len(res['checks'])
    res['n_failed'] = len(true_failed)
    res['failed'] = [c['check'] for c in true_failed]
    res['n_unmeasured'] = len(unmeasured)
    res['unmeasured'] = [{'check': c['check'], 'cause': c['cause'],
                          'code': c.get('code')} for c in unmeasured]
    if true_failed:
        res['verdict'] = NOT_DEPLOYED
    elif unmeasured:
        res['verdict'] = NOT_VERIFIED
        res['cause'] = sorted({c['cause'] for c in unmeasured})
    elif not res['checks']:
        res['verdict'] = NOT_VERIFIED
        res['cause'] = ['EMPTY_INPUT']
        res['n_unmeasured'] = 1
        res['unmeasured'] = [{'check': 'any check at all', 'cause': 'EMPTY_INPUT',
                              'code': 'NO_CHECKS_RAN'}]
    else:
        res['verdict'] = VERIFIED
    return res


def verify(remote='origin', default_branch='main'):
    res = {'checks': [], 'remote': remote, 'default_branch': default_branch}

    def rec(name, ok, detail='', **ev):
        res['checks'].append({'check': name, 'ok': bool(ok),
                              'detail': detail, **ev})

    # EXPLICIT REFSPEC. `git fetch origin main` updates FETCH_HEAD and NOT
    # refs/remotes/origin/main, which is how this project spent four days
    # believing main had stopped capturing.
    _git('fetch', remote, 'refs/heads/*:refs/remotes/' + remote + '/*',
         '--prune')

    rel = CR.approved_release()
    rec('an approved capture release exists', rel is not None,
        (rel or {}).get('capture_release_id', 'none'))
    if rel is None:
        res['verdict'] = 'NO_APPROVED_RELEASE'
        res['n_checks'] = len(res['checks'])
        res['n_failed'] = 1
        res['failed'] = ['an approved capture release exists']
        return res

    ls = _git('ls-remote', '--heads', remote, PROD)
    remote_sha = ls.stdout.split('\t')[0].strip() if ls.stdout.strip() else None
    res['remote_capture_prod_sha'] = remote_sha
    rec('remote ' + PROD + ' exists', bool(remote_sha), str(remote_sha))
    # THE TIP MOVES BY DESIGN. The capture job commits its captured bytes back
    # to capture-prod, so demanding the remote tip EQUAL the release commit
    # would go red after the first successful capture -- and a check that goes
    # red on success teaches everyone to ignore it. What must hold is that the
    # tip DESCENDS from the release and that the surface has not changed under
    # it. The surface is checked below; this is the ancestry.
    want_sha = rel.get('resolved_source_sha')
    if want_sha and remote_sha:
        anc = _git('merge-base', '--is-ancestor', want_sha, remote_sha)
        rec('remote ' + PROD + ' descends from the approved release commit',
            anc.returncode == 0,
            'remote ' + str(remote_sha)[:12] + ' vs approved '
            + str(want_sha)[:12] + ' rc=' + str(anc.returncode))
    else:
        rec('remote ' + PROD + ' descends from the approved release commit',
            bool(remote_sha),
            'the record in hand pins a surface digest, not a commit; the '
            'surface digest check below is what carries the identity')

    prod_ref = remote + '/' + PROD
    db_ref = remote + '/' + default_branch
    res['default_branch_sha'] = _git('rev-parse', db_ref).stdout.strip() or None

    for wf in CAPTURE_WORKFLOWS:
        text = _show(db_ref, '.github/workflows/' + wf)
        if text is None:
            rec(wf + ' exists on the default branch', False, 'absent')
            continue
        doc = _wf(text)
        if doc is None:
            rec(wf + ' on the default branch parses', False, 'invalid yaml')
            continue
        refs = _wf_refs(doc)
        rec(wf + ' on the default branch pins ref: ' + PROD,
            bool(refs) and all(r == PROD for r in refs),
            str(len(refs)) + ' checkout step(s): ' + str(refs))
        targets = _wf_write_targets(doc)
        # THE DETAIL MUST NOT NARRATE A FAILURE ON A PASSING LINE. This printed
        # "a job that checks out capture-prod and pushes to main promotes the
        # capture tree into the default branch" next to an `ok`, which reads as
        # though the green line had found that. A reader should never have to
        # work out whether the prose applies.
        _ok = bool(targets) and all(t == PROD for t in targets)
        rec(wf + ' on the default branch writes back to ' + PROD, _ok,
            str(targets) if _ok else
            str(targets) + ' -- a job that checks out ' + PROD + ' and pushes '
            'to ' + default_branch + ' promotes the capture tree into the '
            'default branch')
        rec(wf + ' declares the capture branch once',
            ((doc.get('env') or {}).get('CAPTURE_BRANCH')) == PROD,
            str((doc.get('env') or {}).get('CAPTURE_BRANCH')))
        rec(wf + ' records the resolved commit',
            'rev-parse HEAD' in text and 'executed_sha' in text)
        i_chk = text.find('--check-executor')
        i_cap = text.find('capture_vintage.py')
        rec(wf + ' checks the executor before capturing',
            i_chk > 0 and (i_cap < 0 or i_chk < i_cap),
            'check@' + str(i_chk) + ' capture@' + str(i_cap))

    deployed = {}
    for relpath in CI.CAPTURE_SURFACE:
        blob = _show(prod_ref, relpath)
        deployed[relpath] = (hashlib.sha256(blob.encode()).hexdigest()
                             if blob is not None else None)
    absent = sorted(k for k, v in deployed.items() if v is None)
    if deployed:
        rec('every approved surface file exists on the deployed branch',
            not absent, str(absent))
    else:
        rec('every approved surface file exists on the deployed branch', False,
            'NOT_EXECUTED: the capture surface lists no file',
            code='SURFACE_EXISTENCE_EMPTY_INPUT', cause='EMPTY_INPUT')
    want = rel.get('capture_surface') or {}
    res['checks'].append(_surface_digest_check(deployed, want))

    # WITHOUT THIS THE WHOLE GATE IS INERT. Measured 2026-09-15: a clean
    # capture-prod checkout answered NO_APPROVED_CAPTURE_RELEASE, so every
    # scheduled capture would have refused to run. The ledger cannot travel --
    # its row is appended after the promotion commit -- so a self-describing
    # record does.
    appr = _show(prod_ref, 'nfl/capture/APPROVED_RELEASE.json')
    rec('the deployed branch carries an approved release record',
        appr is not None,
        'absent -- the deployed executor cannot prove its own release'
        if appr is None else 'present')
    if appr is not None:
        try:
            ar = json.loads(appr)
        except json.JSONDecodeError:
            ar = {}
        rec('  and it pins the same surface as the approved release',
            ar.get('capture_code_sha') == rel.get('capture_code_sha'),
            str(ar.get('capture_code_sha'))[:16] + ' vs '
            + str(rel.get('capture_code_sha'))[:16])
        rec('  and the release checker travels with it',
            _show(prod_ref, 'nfl/tools/capture_release.py') is not None)

    reg = _show(prod_ref, 'nfl/capture/registry.py') or ''
    rec('D20 row_container is present in the deployed registry',
        'row_container' in reg and 'row_container=(' in reg,
        'the marker-word-only check let an empty page pass 374 times')
    pc = _show(prod_ref, 'nfl/capture/payload_contract.py')
    rec('D22 payload_contract is present in the deployed executor',
        pc is not None and 'def check_json' in (pc or '')
        and 'def check_csv' in (pc or ''),
        'absent' if pc is None else 'present')
    rec('  and the deployed registry declares payload_path / required_columns',
        'payload_path' in reg and 'required_columns' in reg)
    pp = _show(prod_ref, 'nfl/capture/persisted_provenance.py')
    rec('persisted-digest protection is present in the deployed executor',
        pp is not None and 'def defect_rows' in (pp or ''),
        'absent' if pp is None else 'present')
    cv = _show(prod_ref, 'nfl/tools/capture_vintage.py') or ''
    rec('the deployed capture_vintage consumes the payload contract',
        'payload_contract' in cv and 'check_csv' in cv and 'check_json' in cv)

    parent = rel.get('prod_parent_sha')
    changed = None
    if parent and remote_sha:
        d = _git('diff', '--name-only', parent, prod_ref)
        changed = [ln.strip() for ln in d.stdout.splitlines() if ln.strip()]
    res['checks'].extend(_model_path_checks(parent, remote_sha, changed))

    rec('allowlist refuses traversal',
        not CR.path_is_allowed('nfl/capture/../production/layers.py')
        and not CR.path_is_allowed('../outside.py')
        and not CR.path_is_allowed('/etc/passwd'))

    return _verdict(res)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--remote', default='origin')
    ap.add_argument('--default-branch', default='main')
    a = ap.parse_args(argv)
    r = verify(a.remote, a.default_branch)
    for c in r['checks']:
        mark = ('ok  ' if c['ok'] else
                'N/M ' if c.get('cause') in NON_EVIDENTIARY else 'FAIL')
        line = '  ' + mark + ' ' + c['check']
        if c.get('detail'):
            line += '  ' + str(c['detail'])
        print(line)
    print('')
    print(str(r['n_checks'] - r['n_failed']) + '/' + str(r['n_checks'])
          + ' -> ' + r['verdict'])
    if r['failed']:
        print('failed: ' + str(r['failed']))
    if r.get('unmeasured'):
        print('not measured: ' + str([u['check'] for u in r['unmeasured']]))
    if r['verdict'] == VERIFIED:
        return 0
    return 3 if r['verdict'] == NOT_VERIFIED else 1


if __name__ == '__main__':
    raise SystemExit(main())
