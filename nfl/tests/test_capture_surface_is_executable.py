"""D24, second defect: the deployed surface could not prove its own release.

WHAT WAS MEASURED, 2026-09-15, BEFORE THE REPAIR. A clean checkout of the
capture branch was extracted with `git archive capture-prod` and asked the one
question the scheduled job asks before it fetches anything:

    $ python3.12 nfl/tools/capture_release.py --check-executor \
          --executed-sha e984ca6c2de8d668cf3ba5e0134a8777f0830bb4
    {"state": "FAIL", "code": "NO_APPROVED_CAPTURE_RELEASE", ...}

Every scheduled capture would have refused to run. The gate was RIGHT; the
deployed content was incomplete.

THE ROOT CAUSE IS A REGRESS, NOT AN OVERSIGHT. A release row is appended to
`nfl/capture/CAPTURE_RELEASES.jsonl` AFTER the promotion commit is made, so the
ledger can never be inside the release it describes. Adding it to the next
release does not help: that release's row is appended after it too. Measured on
CAPREL-631e3d2212cba417 -- 11 changed paths, no ledger among them.

So the deployed branch carries `APPROVED_RELEASE.json`: a self-describing
record pinned on the SURFACE DIGEST, which is computable before the commit
exists and does not move when the commit does. The resolved commit sha stays
where it belongs -- recorded as provenance, on the development-side ledger.

TWO MORE DEFECTS FALL OUT OF THE SAME READING, and both are here:

  * Both workflows check out `ref: capture-prod` and then
    `git push origin HEAD:main`. That rebases the capture-prod tree onto main
    and pushes it there -- precisely the accidental promotion of research and
    model code that this whole mechanism exists to prevent. Section B.

  * The executor gate failed closed when the executed sha differed from the
    release's `resolved_source_sha`. But the capture job COMMITS CAPTURED DATA
    BACK to the branch it checked out, so the tip moves on every run: from the
    second capture onward the gate would refuse forever. A gate that
    invalidates itself by operating normally is not a gate. Section C.

WHAT MUST NOT BE LOST WHILE FIXING THAT. Sections D and E are the properties
the repair could plausibly break: a surface edit must still fail closed, and an
unapproved path must still be refused. Loosening the commit check must not
loosen those.

Run standalone:  python3.12 nfl/tests/test_capture_surface_is_executable.py
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import capture_identity as CI                     # noqa: E402
from nfl.tools import capture_release as CR                        # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github' / 'workflows'
CAPTURE_WORKFLOWS = ('nfl-capture.yml', 'nfl-t90.yml')
PROD_BRANCH = CR.PROD_BRANCH


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  ..   NOT_EXECUTED {label} -- {why}')


def _branch_exists(ref=PROD_BRANCH):
    r = subprocess.run(['git', 'rev-parse', '--verify', f'{ref}^{{commit}}'],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


#: WHAT A CAPTURE EXECUTOR ACTUALLY NEEDS. Scoped deliberately: the full tree
#: is 1.1 GB, almost all of it captured vintage blobs, and extracting it once
#: per section would move 4+ GB per suite run to answer a question about six
#: source files. `_surface_is_inside_scope` below is the guard that keeps the
#: scoping honest -- if a surface module ever moves outside these prefixes the
#: test fails rather than quietly stopping to look at it.
EXECUTOR_PATHS = ('nfl/__init__.py', 'nfl/capture', 'nfl/tools', 'nfl/identity',
                  'sportsplatform', '.github')


def _surface_is_inside_scope():
    bad = [rel for rel in CI.CAPTURE_SURFACE
           if not any(rel == s or rel.startswith(s.rstrip('/') + '/')
                      for s in EXECUTOR_PATHS)]
    return bad


def _export(ref=PROD_BRANCH):
    """A clean checkout of the deployed executor, exactly as the runner sees it.

    `git archive` rather than a worktree: this must not touch the repository the
    suite is diffing.
    """
    d = pathlib.Path(tempfile.mkdtemp(prefix='capprod_'))
    tar = subprocess.run(['git', 'archive', ref, '--', *EXECUTOR_PATHS],
                         cwd=ROOT, capture_output=True)
    if tar.returncode != 0:
        shutil.rmtree(d, ignore_errors=True)
        return None
    subprocess.run(['tar', '-x', '-C', str(d)], input=tar.stdout, check=True)
    return d


def _branch_tree(ref=PROD_BRANCH):
    """Every path on the branch, read without extracting a gigabyte of it."""
    r = subprocess.run(['git', 'ls-tree', '-r', '--name-only', ref],
                       cwd=ROOT, capture_output=True, text=True)
    return set(r.stdout.splitlines()) if r.returncode == 0 else set()


def _identity_in(root):
    """Ask the EXPORTED tree what it is, rather than asking the tree we are in.

    Read in the exported interpreter's own terms: importing the development
    copy and calling it a measurement of the deployed copy is how three absent
    modules passed their tests on the development branch while production ran
    without them.
    """
    src = (
        'import json,sys;sys.path.insert(0,".");'
        'from nfl.capture import capture_identity as CI;'
        'from nfl.capture import payload_contract as PC;'
        'print(json.dumps({"surface":CI.surface(),'
        '"capture_code_sha":CI.capture_code_sha(),'
        '"parser_version":CI.SPEC_VERSION,'
        '"source_contract_version":PC.SPEC_VERSION}))')
    r = subprocess.run([sys.executable, '-c', src], cwd=str(root),
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {'_error': r.stderr.strip()[-400:]}


def _check_executor(root, executed_sha=None):
    """Run the runner's own pre-fetch gate inside `root`. Returns parsed JSON."""
    cmd = [sys.executable, 'nfl/tools/capture_release.py', '--check-executor']
    if executed_sha:
        cmd += ['--executed-sha', executed_sha]
    r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
    try:
        return json.loads(r.stdout), r.returncode
    except json.JSONDecodeError:
        return {'state': 'UNPARSEABLE', 'stdout': r.stdout,
                'stderr': r.stderr[-800:]}, r.returncode


# --------------------------------------------------------------------------
# A. the deployed surface can prove its own release, with nothing else present
# --------------------------------------------------------------------------
def test_a_a_clean_deployed_checkout_proves_its_own_release():
    print(f'\nA. a clean {PROD_BRANCH} checkout proves its own release')
    if not _branch_exists():
        not_executed(f'{PROD_BRANCH} exists locally',
                     'nothing to export; this is BLOCKED, not a pass')
        return
    outside = _surface_is_inside_scope()
    check('the scoped export still covers every surface module',
          not outside,
          f'{outside} sit outside EXECUTOR_PATHS, so a scoped export would '
          f'stop looking at them without saying so')
    tree = _branch_tree()
    missing = [rel for rel in CI.CAPTURE_SURFACE if rel not in tree]
    check('every surface module exists on the branch itself',
          not missing, f'absent from {PROD_BRANCH}: {missing}')
    d = _export()
    if d is None:
        not_executed('export succeeded', 'git archive failed')
        return
    try:
        check('the release checker travels with the surface',
              (d / 'nfl/tools/capture_release.py').exists())
        check('an approved release record travels with it',
              (d / 'nfl/capture/APPROVED_RELEASE.json').exists(),
              'without this the job returns NO_APPROVED_CAPTURE_RELEASE and '
              'every scheduled capture refuses to run')
        out, rc = _check_executor(d)
        check('the gate returns ok from a clean checkout',
              out.get('state') == 'OK',
              f'state={out.get("state")} code={out.get("code")}')
        check('  and exits 0', rc == 0, f'exit={rc}')
        check('  and names the release it matched',
              bool(out.get('evidence', {}).get('capture_release_id')
                   or out.get('value')),
              str(out)[:200])

        # THE RECORD MUST DESCRIBE THIS TREE, not merely be well-formed.
        rec_path = d / 'nfl/capture/APPROVED_RELEASE.json'
        if not rec_path.exists():
            not_executed('release metadata validated from the archive',
                         'no APPROVED_RELEASE.json to validate')
            return
        rec = json.loads(rec_path.read_text())
        ident = _identity_in(d)
        check('  the record pins the surface this tree actually has',
              rec.get('capture_code_sha') == ident.get('capture_code_sha'),
              f'record {str(rec.get("capture_code_sha"))[:16]} vs running '
              f'{str(ident.get("capture_code_sha"))[:16]} '
              f'{ident.get("_error", "")}')
        check('  every per-file digest agrees too',
              (rec.get('capture_surface') or {}) == (ident.get('surface') or {}),
              'a matching aggregate over disagreeing parts would mean the '
              'digest is not covering what it claims to')
        check('  the record declares its parser version',
              rec.get('parser_version') == ident.get('parser_version'),
              f'{rec.get("parser_version")} vs {ident.get("parser_version")}')
        check('  and its source contract version',
              rec.get('source_contract_version')
              == ident.get('source_contract_version'),
              f'{rec.get("source_contract_version")} vs '
              f'{ident.get("source_contract_version")}')
        check('  and the branch it is the release for',
              rec.get('prod_branch') == PROD_BRANCH,
              str(rec.get('prod_branch')))
        check('  and it does not pin a tip that normal capture will move',
              'resolved_source_sha' not in rec,
              'a deployed record pinning a commit refuses its own output from '
              'the second capture onward')
        check('  while still saying where the commit IS recorded',
              bool(rec.get('resolved_source_sha_recorded_in')),
              'dropping the pin must not drop the provenance')
        # WORKFLOW IDENTITY, read from the archive rather than the dev tree.
        for name in CAPTURE_WORKFLOWS:
            wp = d / '.github' / 'workflows' / name
            if not wp.exists():
                check(f'  {name} travels with the release', False, 'absent')
                continue
            wf = _load_workflow(wp)
            if wf is None:
                not_executed(f'{name} parsed from the archive', 'no parser')
                continue
            check(f'  {name} in the archive names {PROD_BRANCH}',
                  _checkout_refs(wf) == [PROD_BRANCH],
                  str(_checkout_refs(wf)))
            check(f'  {name} in the archive writes to {PROD_BRANCH}',
                  bool(_push_targets(wf))
                  and all(tg == PROD_BRANCH for _, tg in _push_targets(wf)),
                  str(_push_targets(wf)))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------
# B. captured bytes go back to the branch that was checked out
# --------------------------------------------------------------------------
def _load_workflow(path):
    """Parse it, never grep it.

    THE FIRST CUT OF THIS FUNCTION GREPPED FOR `ref:` and took the first match.
    The repaired workflow explains itself in a header comment that contains the
    literal `ref: capture-prod`, so the grep would have read the COMMENT and
    reported the pin satisfied whatever the checkout step actually said. That is
    the D20 class exactly -- a marker word found in chrome and counted as
    substance -- and it is the reason this parses the document instead.
    """
    try:
        import yaml
    except ImportError:
        return None
    try:
        return yaml.safe_load(path.read_text())
    except Exception:                                            # noqa: BLE001
        return None


def _resolve(value, wf):
    """`${{ env.X }}` or `$X` down to the literal the workflow declares."""
    if not isinstance(value, str):
        return value
    v = value.strip().strip('"\'')
    m = re.fullmatch(r'\$\{\{\s*env\.(\w+)\s*\}\}', v) \
        or re.fullmatch(r'\$\{?(\w+)\}?', v)
    if m:
        return ((wf or {}).get('env') or {}).get(m.group(1), v)
    return v


def _steps(wf):
    for job in ((wf or {}).get('jobs') or {}).values():
        for step in (job.get('steps') or []):
            if isinstance(step, dict):
                yield step


def _checkout_refs(wf):
    """Every ref an actions/checkout step names, resolved. Structural."""
    out = []
    for step in _steps(wf):
        if 'checkout' in str(step.get('uses') or ''):
            out.append(_resolve((step.get('with') or {}).get('ref'), wf))
    return out


def _push_targets(wf):
    """Every branch a step body writes to, read from `run:` bodies only.

    Comments in the YAML header are not step bodies, so a branch name discussed
    in prose cannot be counted as a branch the workflow writes to.
    """
    out = []
    for step in _steps(wf):
        body = step.get('run')
        if not isinstance(body, str):
            continue
        for m in re.finditer(r'git\s+push\s+origin\s+HEAD:(\S+)', body):
            out.append(('push', _resolve(m.group(1), wf)))
        for m in re.finditer(r'git\s+pull\s+[^\n]*?origin\s+(\S+)', body):
            out.append(('pull', _resolve(m.group(1), wf)))
    return out


def test_b_captured_bytes_return_to_the_branch_that_ran():
    print('\nB. captured bytes return to the branch that was checked out')
    for name in CAPTURE_WORKFLOWS:
        p = WORKFLOWS / name
        if not p.exists():
            not_executed(f'{name} present', 'workflow absent')
            continue
        wf = _load_workflow(p)
        if wf is None:
            not_executed(f'{name} parsed', 'no yaml parser, or invalid yaml')
            continue
        refs = _checkout_refs(wf)
        check(f'{name}: it checks something out at all', bool(refs))
        for r in refs:
            check(f'{name}: checkout names the governed branch',
                  r == PROD_BRANCH, f'ref={r!r}')
        targets = _push_targets(wf)
        check(f'{name}: it writes somewhere at all', bool(targets))
        for kind, tgt in targets:
            check(f'{name}: git {kind} targets {PROD_BRANCH}',
                  tgt == PROD_BRANCH,
                  f'targets {tgt!r} while running {refs!r} -- this rebases '
                  f'the capture tree onto {tgt} and pushes it there')
        check(f'{name}: the branch is declared once, not per-site',
              (wf.get('env') or {}).get('CAPTURE_BRANCH') == PROD_BRANCH,
              'the ref and the push target naming it separately is how they '
              'came to disagree')


# --------------------------------------------------------------------------
# C. a data commit on top of the release does not invalidate the executor
# --------------------------------------------------------------------------
def test_c_a_data_commit_does_not_invalidate_the_executor():
    print('\nC. committing captured data back does not invalidate the gate')
    if not _branch_exists():
        not_executed('data-commit simulation', f'{PROD_BRANCH} absent')
        return
    d = _export()
    if d is None:
        not_executed('data-commit simulation', 'git archive failed')
        return
    try:
        base, _ = _check_executor(d)
        if base.get('state') != 'OK':
            not_executed('data-commit simulation',
                         f'the clean checkout already fails '
                         f'({base.get("code")}); section A owns that')
            return
        # exactly what a capture run adds: a vintage blob and a manifest row.
        vd = d / 'nfl' / 'vintage'
        vd.mkdir(parents=True, exist_ok=True)
        (vd / 'schedules.deadbeefdeadbeef.reduced.csv.gz').write_bytes(b'\x1f\x8b0')
        mf = d / 'nfl' / 'vintage_manifest.jsonl'
        with mf.open('a') as fh:
            fh.write(json.dumps({'partition_id':
                                 'schedules@deadbeefdeadbeef'}) + '\n')
        after, rc = _check_executor(d, executed_sha='0' * 40)
        check('the gate still returns ok after a data-only change',
              after.get('state') == 'OK',
              f'state={after.get("state")} code={after.get("code")} -- the '
              f'capture job commits its own output back, so the tip always '
              f'moves; a gate keyed on commit equality refuses from run 2 on')
        check('  and exits 0', rc == 0, f'exit={rc}')
        check('  and the surface digest is unchanged by data',
              after.get('evidence', {}).get('capture_code_sha')
              == base.get('evidence', {}).get('capture_code_sha'))
        check('  and the executed commit is recorded, not discarded',
              after.get('evidence', {}).get('executed_sha') == '0' * 40,
              'the owner required the resolved sha be recorded; relaxing the '
              'comparison must not stop recording it')
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------
# D. the property the repair could break: a surface edit still fails closed
# --------------------------------------------------------------------------
def test_d_a_surface_edit_still_fails_closed():
    print('\nD. a surface edit still fails closed')
    if not _branch_exists():
        not_executed('surface-edit bypass', f'{PROD_BRANCH} absent')
        return
    d = _export()
    if d is None:
        not_executed('surface-edit bypass', 'git archive failed')
        return
    try:
        base, _ = _check_executor(d)
        if base.get('state') != 'OK':
            not_executed('surface-edit bypass',
                         f'clean checkout already fails ({base.get("code")})')
            return
        victim = d / 'nfl' / 'capture' / 'registry.py'
        original = victim.read_bytes()
        victim.write_bytes(original + b'\n# unapproved edit\n')
        out, rc = _check_executor(d)
        check('editing a surface module is refused',
              out.get('state') == 'FAIL', f'state={out.get("state")}')
        check('  with the surface-mismatch code',
              out.get('code') == 'CAPTURE_EXECUTOR_SURFACE_MISMATCH',
              f'code={out.get("code")}')
        check('  and a non-zero exit', rc != 0, f'exit={rc}')
        victim.write_bytes(original)
        restored, _ = _check_executor(d)
        check('  and restoring the byte restores the ok',
              restored.get('state') == 'OK',
              'if this fails the check is not reading the file it claims to')
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------
# E. an unapproved path is still refused by the allowlist
# --------------------------------------------------------------------------
def test_e_unapproved_paths_are_still_refused():
    print('\nE. the allowlist still refuses what it refused before')
    forbidden = [
        'nfl/production/layers.py',
        'nfl/research/shadow/replay_contract.py',
        'nfl/prospective/q9shadow/inputs.py',
        'nfl/product/board.py',
        'nfl/capture/../production/layers.py',
        'nfl/capture/../../nfl/research/x.py',
    ]
    for p in forbidden:
        check(f'refused: {p}', not CR.path_is_allowed(p))
    for p in ('nfl/capture/registry.py', 'nfl/capture/APPROVED_RELEASE.json',
              'nfl/tools/capture_vintage.py', '.github/workflows/nfl-capture.yml'):
        check(f'admitted: {p}', CR.path_is_allowed(p))


# --------------------------------------------------------------------------
# F. absence is a value, never the empty hash
# --------------------------------------------------------------------------
def test_f_absence_is_never_the_empty_hash():
    print('\nF. an absent surface module is ABSENT, not a hash of nothing')
    import hashlib
    empty = hashlib.sha256(b'').hexdigest()
    surf = CI.surface()
    check('the surface enumerates every declared module',
          set(surf) == set(CI.CAPTURE_SURFACE),
          f'{sorted(set(CI.CAPTURE_SURFACE) - set(surf))} missing')
    check('no module hashes to the empty digest',
          all(v != empty for v in surf.values() if v),
          'an absent file recorded as the empty hash is an absent file '
          'reported as present-and-empty; they are different facts')
    fabricated = dict(surf)
    first = CI.CAPTURE_SURFACE[0]
    fabricated[first] = None
    check('absence changes the surface digest',
          CI.capture_code_sha(fabricated) != CI.capture_code_sha(surf))



# --------------------------------------------------------------------------
# G. the cycle proof: normal capture moves the tip and must not self-invalidate
# --------------------------------------------------------------------------
def _seed_repo(d):
    """Make the exported surface a real repository, so a commit can move a tip."""
    for cmd in (['git', 'init', '-q', '-b', PROD_BRANCH],
                ['git', 'config', 'user.email', 't@t'],
                ['git', 'config', 'user.name', 't'],
                ['git', 'add', '-A'],
                ['git', 'commit', '-q', '-m', 'deployed capture surface']):
        r = subprocess.run(cmd, cwd=str(d), capture_output=True, text=True)
        if r.returncode != 0:
            return None
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(d),
                          capture_output=True, text=True).stdout.strip()


def _commit(d, msg):
    subprocess.run(['git', 'add', '-A'], cwd=str(d), capture_output=True)
    subprocess.run(['git', 'commit', '-q', '-m', msg], cwd=str(d),
                   capture_output=True)
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(d),
                          capture_output=True, text=True).stdout.strip()


def test_g_a_capture_cycle_does_not_invalidate_the_next_capture():
    """The property the whole repair exists for.

    A capture job COMMITS ITS OWN OUTPUT back to the branch it ran, so the tip
    moves every single run. If the executor gate cannot tell that movement apart
    from a code change, it passes capture 1 and refuses capture 2 onward -- and
    the failure looks exactly like a security control working, which is the
    worst kind of false alarm. Six numbered steps, in order.
    """
    print('\nG. a full capture cycle, and the cycle after it')
    if not _branch_exists():
        not_executed('capture cycle', f'{PROD_BRANCH} absent')
        return
    d = _export()
    if d is None:
        not_executed('capture cycle', 'git archive failed')
        return
    try:
        pre, _ = _check_executor(d)
        if pre.get('state') != 'OK':
            not_executed('capture cycle',
                         f'the surface does not validate at rest '
                         f'({pre.get("code")}); section A owns that')
            return
        tip0 = _seed_repo(d)
        if not tip0:
            not_executed('capture cycle', 'could not seed a git repo')
            return

        # 1. the executor validates before anything is fetched
        s1, rc1 = _check_executor(d, executed_sha=tip0)
        check('1. the executor validates at the release tip',
              s1.get('state') == 'OK' and rc1 == 0,
              f'{s1.get("code")}')
        sha0 = s1.get('evidence', {}).get('capture_code_sha')

        # 2. the capture entry point runs. THE FETCH ITSELF CANNOT RUN HERE --
        #    this environment has no egress -- so what is proven is that the
        #    deployed surface imports and its entry point executes, and the
        #    network leg is reported NOT_EXECUTED rather than assumed.
        r = subprocess.run([sys.executable, 'nfl/tools/capture_vintage.py',
                            '--season', '2026', '--plan-only'],
                           cwd=str(d), capture_output=True, text=True)
        check('2. the deployed capture entry point imports and runs',
              'Traceback' not in r.stderr and 'ImportError' not in r.stderr
              and 'ModuleNotFoundError' not in r.stderr,
              r.stderr.strip()[-300:])
        not_executed('2b. a real fetch of live bytes',
                     'no egress in this environment; the network leg belongs '
                     'to the connector-holding agent, and assuming it here '
                     'would be the exact defect this file exists to stop')

        # 3. evidence is persisted the way a capture persists it
        (d / 'nfl' / 'vintage').mkdir(parents=True, exist_ok=True)
        blob = d / 'nfl' / 'vintage' / 'schedules.deadbeefdeadbeef.reduced.csv.gz'
        blob.write_bytes(b'\x1f\x8b\x08\x00captured')
        mf = d / 'nfl' / 'vintage_manifest.jsonl'
        with mf.open('a') as fh:
            fh.write(json.dumps({'partition_id': 'schedules@deadbeefdeadbeef',
                                 'captured_at_utc': '2026-09-15T18:00:00Z'})
                     + '\n')
        check('3. evidence is persisted', blob.exists() and mf.exists())

        # 4. the commit advances the branch tip
        tip1 = _commit(d, 'NFL vintage capture 20260915T180000Z')
        check('4. the capture commit advances the tip',
              bool(tip1) and tip1 != tip0, f'{str(tip0)[:8]} -> {str(tip1)[:8]}')

        # 5. and the NEXT executor still validates
        s2, rc2 = _check_executor(d, executed_sha=tip1)
        check('5. the next executor still validates',
              s2.get('state') == 'OK' and rc2 == 0,
              f'{s2.get("code")} -- this is the whole point: a moved tip is '
              f'not a changed surface')
        check('   and the surface digest did not move with the tip',
              s2.get('evidence', {}).get('capture_code_sha') == sha0,
              f'{str(sha0)[:16]} vs '
              f'{str(s2.get("evidence", {}).get("capture_code_sha"))[:16]}')
        check('   and the executed commit is recorded',
              s2.get('evidence', {}).get('executed_sha') == tip1)
        check('   and the commit provenance is stated, not implied',
              bool(s2.get('evidence', {}).get('commit_provenance')),
              str(s2.get('evidence', {}))[:200])

        # 6. but a change to the protected surface refuses
        reg = d / 'nfl' / 'capture' / 'registry.py'
        reg.write_bytes(reg.read_bytes() + b'\n# drift\n')
        tip2 = _commit(d, 'unapproved surface change')
        s3, rc3 = _check_executor(d, executed_sha=tip2)
        check('6. a change to the protected surface refuses',
              s3.get('state') == 'FAIL', f'{s3.get("state")}')
        check('   with the surface-mismatch code',
              s3.get('code') == 'CAPTURE_EXECUTOR_SURFACE_MISMATCH',
              f'{s3.get("code")}')
        check('   and a non-zero exit', rc3 != 0, f'exit={rc3}')
        check('   and it is the SURFACE, not the tip, that refused it',
              tip2 != tip1 and s2.get('state') == 'OK',
              'step 5 moved the tip and passed; step 6 moved the surface and '
              'failed. That contrast is the proof.')
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------
# H. the commit-provenance states, including the one that must not read as yes
# --------------------------------------------------------------------------
def test_h_commit_provenance_states_are_all_reachable():
    print('\nH. commit provenance: five states, and NOT_ESTABLISHED is not yes')
    fn = getattr(CR, '_commit_provenance', None)
    if fn is None:
        not_executed('commit provenance states', '_commit_provenance absent')
        return
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    old = subprocess.run(['git', 'rev-list', '--max-parents=0', '-n', '1',
                          'HEAD'], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    check('no executed sha -> NOT REPORTED',
          fn({'resolved_source_sha': head}, None)['state']
          == 'EXECUTED_SHA_NOT_REPORTED')
    check('release pins no commit -> stated as such',
          fn({}, head)['state'] == 'RELEASE_PINS_NO_COMMIT')
    check('equal -> MATCHES_RELEASE_COMMIT',
          fn({'resolved_source_sha': head}, head)['state']
          == 'MATCHES_RELEASE_COMMIT')
    if head and old and head != old:
        check('descendant -> DESCENDS_FROM_RELEASE_COMMIT',
              fn({'resolved_source_sha': old}, head)['state']
              == 'DESCENDS_FROM_RELEASE_COMMIT',
              'a capture commit on top of the release is the normal case')
        check('not a descendant -> DIVERGED, and that one fails closed',
              fn({'resolved_source_sha': head}, old)['state']
              == 'DIVERGED_FROM_RELEASE_COMMIT')
    else:
        not_executed('ancestry states', 'no two-commit history to compare')
    unknown = fn({'resolved_source_sha': 'f' * 40}, '0' * 40)['state']
    check('an undecidable ancestry is NOT rounded to a pass',
          unknown in ('COMMIT_ANCESTRY_NOT_ESTABLISHED',
                      'DIVERGED_FROM_RELEASE_COMMIT'),
          f'got {unknown!r}; NOT ASKED must never render as yes')


if __name__ == '__main__':
    test_a_a_clean_deployed_checkout_proves_its_own_release()
    test_b_captured_bytes_return_to_the_branch_that_ran()
    test_c_a_data_commit_does_not_invalidate_the_executor()
    test_d_a_surface_edit_still_fails_closed()
    test_e_unapproved_paths_are_still_refused()
    test_f_absence_is_never_the_empty_hash()
    test_g_a_capture_cycle_does_not_invalidate_the_next_capture()
    test_h_commit_provenance_states_are_all_reachable()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
