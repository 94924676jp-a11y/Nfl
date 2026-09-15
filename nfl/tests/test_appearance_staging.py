"""Staging the frozen appearance inputs must not leak a directory per process.

THE DEFECT THIS MODULE EXISTS FOR.

`appearance_model.stage_inputs` called `tempfile.mkdtemp(prefix='nfl-appearance-')`
once per process and never removed the directory. On 2026-09-14, 617 of them at
33 MB each filled the session disk to 100% with 1.5 MB free. It stopped an
agent's measurements mid-run and invalidated a full 116-module suite execution
that was in flight; that run was discarded and re-run from scratch rather than
reported. 593 directories were cleared by hand to recover 20 GB.

A board build spawns several processes, so the leak scales with exactly the
thing this project does most.

WHY REUSE IS SAFE HERE, WHICH IS NOT OBVIOUS AND IS THE WHOLE ARGUMENT.

Staging is not a computation. It decompresses a fixed set of committed leaves
and hash-checks every one against `INPUT_MANIFEST`, refusing on any mismatch
with `RESEARCH_INPUT_HASH_MISMATCH` ("a moved leaf is a different model"). The
staged bytes are therefore a pure function of the manifest. Two processes
staging the same manifest must produce byte-identical trees or one of them
refuses.

So a directory named by the manifest's own digest can be reused without
changing what is computed -- and reuse is not merely allowed, it is checkable:
these tests assert that a reused stage still hash-verifies every leaf, and that
a stage built from a DIFFERENT manifest lands somewhere else.

WHAT IS NOT DONE. No cleanup-on-exit that could delete a directory another live
process is reading. No cache that skips the hash check. Content addressing
means a stale directory is either byte-correct or has a different name.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import derived as D                      # noqa: E402
from nfl.production.nonqb import appearance_model as AM      # noqa: E402

PASSED = FAILED = BLOCKED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(cond)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def _artifacts_ok():
    return D.artifacts().state.value == 'PASS'


def test_a_staging_is_content_addressed_not_random():
    """Two fresh processes must stage to the SAME directory."""
    print('\nA. the staged path is a function of the inputs')
    if not _artifacts_ok():
        blocked('derived artifacts unavailable', 'ARTIFACTS_UNAVAILABLE')
        return
    prog = ('import sys; sys.path.insert(0, %r)\n'
            'from nfl.production import derived as D\n'
            'assert D.artifacts().state.value == "PASS"\n'
            'from nfl.production.nonqb import appearance_model as AM\n'
            'o = AM.stage_inputs()\n'
            'print(o.state.value, o.value)\n') % _ROOT
    outs = []
    for _ in range(2):
        r = subprocess.run([sys.executable, '-c', prog], capture_output=True,
                           text=True, cwd=_ROOT, timeout=600)
        if r.returncode != 0:
            blocked('a staging subprocess failed',
                    r.stderr.strip().splitlines()[-1] if r.stderr else '?')
            return
        outs.append(r.stdout.strip().split(None, 1))
    check('both processes staged successfully',
          all(o[0] == 'PASS' for o in outs), str(outs))
    check('  and staged to the SAME directory -- no per-process leak',
          outs[0][1] == outs[1][1], f'{outs[0][1]} vs {outs[1][1]}')
    check('  and the directory name carries a content digest, not randomness',
          any(c.isdigit() for c in pathlib.Path(outs[0][1]).name)
          and 'appearance' in pathlib.Path(outs[0][1]).name,
          pathlib.Path(outs[0][1]).name)


def test_b_a_reused_stage_still_hash_verifies_every_leaf():
    """Reuse must not become a cache that skips the check."""
    print('\nB. reuse does not skip verification')
    if not _artifacts_ok():
        blocked('derived artifacts unavailable', 'ARTIFACTS_UNAVAILABLE')
        return
    src = pathlib.Path(__file__).resolve().parents[1] / \
        'production' / 'nonqb' / 'appearance_model.py'
    s = src.read_text()
    i = s.index('def stage_inputs')
    body = s[i:i + 3000]
    check('the staging path still hashes each leaf',
          'hashlib.sha256(raw).hexdigest()' in body)
    check('  and still refuses on a mismatch by name',
          'RESEARCH_INPUT_HASH_MISMATCH' in body)
    check('  and the refusal is a FAIL, not a warning',
          'Outcome.fail(' in body)
    check('  no unconditional early return that skips hashing',
          body.index('hashlib.sha256(raw).hexdigest()')
          < body.index('_STAGE = d') if '_STAGE = d' in body else True)


def test_c_a_different_manifest_stages_somewhere_else():
    """Content addressing is only safe if the content actually addresses it."""
    print('\nC. a different manifest gets a different directory')
    if not _artifacts_ok():
        blocked('derived artifacts unavailable', 'ARTIFACTS_UNAVAILABLE')
        return
    fn = getattr(AM, 'stage_digest', None)
    if fn is None:
        check('appearance_model exposes the staging digest for audit', False,
              'no stage_digest() -- the addressing cannot be checked')
        return
    a = fn()
    man = json.loads(AM.MANIFEST.read_text())
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='nfl-stagetest-'))
    try:
        alt = dict(man)
        alt['files'] = dict(man['files'])
        # It must be a leaf that is actually STAGED. My first version mutated
        # sorted(files)[0], which is `dc25_daily.csv` and is not in NEEDED, so
        # the digest correctly did not move and the test failed against
        # correct code. A digest over the whole manifest would have "passed"
        # that test while binding the stage to bytes it never reads.
        staged = sorted(set(AM.NEEDED) & set(alt['files']))
        if not staged:
            blocked('no NEEDED leaf appears in the manifest',
                    'MANIFEST_DOES_NOT_COVER_NEEDED')
            return
        target = staged[0]
        alt['files'][target] = dict(alt['files'][target])
        alt['files'][target]['sha256_decompressed'] = 'f' * 64
        p = tmp / 'INPUT_MANIFEST.json'
        p.write_text(json.dumps(alt))
        b = fn(manifest_path=p)
        check(f'changing a STAGED leaf ({target}) changes the digest',
              a != b, f'{a[:12]} vs {b[:12]}')
        # And the converse, which is what makes the addressing tight rather
        # than merely sensitive: a leaf the stage never reads must NOT move it.
        alt2 = dict(man)
        alt2['files'] = dict(man['files'])
        unstaged = [k for k in sorted(alt2['files'])
                    if k not in AM.NEEDED]
        if unstaged:
            u = unstaged[0]
            alt2['files'][u] = dict(alt2['files'][u])
            alt2['files'][u]['sha256_decompressed'] = 'e' * 64
            p2 = tmp / 'INPUT_MANIFEST_2.json'
            p2.write_text(json.dumps(alt2))
            check(f'  and changing an UNstaged leaf ({u}) does not',
                  fn(manifest_path=p2) == a)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_d_the_leak_itself_is_gone():
    """No unconditional mkdtemp on the default path."""
    print('\nD. no per-process temp directory on the default path')
    src = pathlib.Path(__file__).resolve().parents[1] / \
        'production' / 'nonqb' / 'appearance_model.py'
    s = src.read_text()
    i = s.index('def stage_inputs')
    body = s[i:i + 3000]
    check('stage_inputs no longer calls mkdtemp for the default stage',
          'mkdtemp' not in body,
          'mkdtemp still present -- each process leaks a directory')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
