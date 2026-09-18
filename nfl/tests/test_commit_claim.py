"""COMMIT_CLAIM_WITHOUT_VERIFIED_GIT_STATE, with the real failure reproduced.

Test C is the case that happened: `git add <good paths> <path that does not
exist> 2>/dev/null`, in a real repository, with stderr thrown away exactly as
it was. It asserts what made the defect believable -- the add looked survivable
and the pipeline kept going -- and then that the verifier refuses anyway,
because it reads git rather than intent.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import commit_claim as CC                # noqa: E402
from sportsplatform.governance.outcome import Cause, State              # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def git(repo, *args, check_rc=True):
    p = subprocess.run(['git'] + list(args), cwd=repo, capture_output=True,
                       text=True)
    if check_rc and p.returncode != 0:
        raise AssertionError(f'git {args}: {p.stderr}')
    return p


def fresh_repo(d):
    git(d, 'init', '-q', '-b', 'main')
    git(d, 'config', 'user.email', 'test@example.invalid')
    git(d, 'config', 'user.name', 'test')
    (pathlib.Path(d) / 'seed.txt').write_text('seed\n')
    git(d, 'add', 'seed.txt')
    git(d, 'commit', '-q', '-m', 'seed')
    return pathlib.Path(d)


def test_A_a_real_commit_verifies():
    print('\nA. the happy path')
    with tempfile.TemporaryDirectory() as d:
        r = fresh_repo(d)
        (r / 'a.py').write_text('x = 1\n')
        (r / 'b.md').write_text('# b\n')
        git(r, 'add', 'a.py', 'b.md')
        git(r, 'commit', '-q', '-m', 'add a and b')
        o = CC.verify_commit('HEAD', expect_paths=['a.py', 'b.md'], repo=r)
        check('it passes', o.state is State.PASS, f'{o.state}[{o.code}]')
        check('  the sha returned is the resolved full sha',
              len(o.value) == 40, o.value)
        check('  both expected files are recorded as in the commit',
              set(o.evidence['files_in_commit']) == {'a.py', 'b.md'},
              str(o.evidence['files_in_commit']))
        check('  and the working tree state is reported SEPARATELY, not folded '
              'into the verdict', o.evidence['working_tree_is_clean'] is True)


def test_B_a_commit_that_does_not_carry_the_work():
    print('\nB. the commit happened; the file was not in it')
    with tempfile.TemporaryDirectory() as d:
        r = fresh_repo(d)
        (r / 'wanted.py').write_text('x = 1\n')
        (r / 'other.py').write_text('y = 2\n')
        git(r, 'add', 'other.py')
        git(r, 'commit', '-q', '-m', 'committed the wrong file')
        o = CC.verify_commit('HEAD', expect_paths=['wanted.py'], repo=r)
        check('refused', o.state is State.FAIL
              and o.code == 'COMMIT_CLAIM_WITHOUT_VERIFIED_GIT_STATE',
              f'{o.state}[{o.code}]')
        check('  naming EXPECTED_PATHS_NOT_IN_COMMIT',
              o.evidence['reason'] == CC.NOT_IN_COMMIT)
        check('  and the missing path', o.evidence['missing'] == ['wanted.py'])
        check('  with the distinction stated: a commit that happened is not a '
              'commit that carried the work',
              'carried the work' in o.detail, o.detail[:90])


def test_C_the_atomic_add_reproduced_not_mocked():
    """git add <good> <missing> 2>/dev/null stages NOTHING."""
    print('\nC. THE REGRESSION: one bad path, stderr suppressed, zero staged')
    with tempfile.TemporaryDirectory() as d:
        r = fresh_repo(d)
        (r / 'real_one.py').write_text('x = 1\n')
        (r / 'real_two.py').write_text('y = 2\n')
        # EXACTLY THE SHAPE OF THE COMMAND THAT FAILED.
        add = subprocess.run(
            'git add real_one.py real_two.py COMMANDS.md 2>/dev/null',
            cwd=r, shell=True, capture_output=True, text=True)
        check('git add exits non-zero', add.returncode != 0,
              str(add.returncode))
        check('  but its stderr was discarded, so a `;`-chained line sees '
              'nothing', add.stderr == '', repr(add.stderr))
        st = git(r, 'diff', '--cached', '--name-only').stdout.strip()
        check('  and ZERO files are staged -- not two of three',
              st == '', repr(st))
        o = CC.verify_staged(['real_one.py', 'real_two.py'], repo=r)
        check('verify_staged REFUSES', o.state is State.FAIL
              and o.evidence['reason'] == CC.NOT_STAGED,
              f'{o.state}[{o.code}]')
        check('  naming both paths', o.evidence['missing'] ==
              ['real_one.py', 'real_two.py'], str(o.evidence['missing']))
        check('  and explaining that git add is atomic over pathspecs',
              'ATOMIC' in o.detail, o.detail[:100])
        # And the commit that follows in such a line does nothing.
        c = subprocess.run('git commit -q -m "work" 2>/dev/null', cwd=r,
                           shell=True, capture_output=True, text=True)
        check('  the following commit also exits non-zero with nothing staged',
              c.returncode != 0, str(c.returncode))
        head_msg = git(r, 'log', '-1', '--format=%s').stdout.strip()
        check('  HEAD is still the seed commit', head_msg == 'seed', head_msg)
        v = CC.verify_commit('HEAD', expect_paths=['real_one.py'], repo=r)
        check('  verify_commit refuses too', v.state is State.FAIL
              and v.evidence['reason'] == CC.NOT_IN_COMMIT,
              f'{v.state}[{v.code}]')
        # THE CONTROL: the same add without the bad path.
        git(r, 'add', 'real_one.py', 'real_two.py')
        ok = CC.verify_staged(['real_one.py', 'real_two.py'], repo=r)
        check('CONTROL: dropping the missing path stages both',
              ok.state is State.PASS, f'{ok.state}[{ok.code}]')
        git(r, 'commit', '-q', '-m', 'work')
        okc = CC.verify_commit('HEAD', expect_paths=['real_one.py',
                                                     'real_two.py'], repo=r)
        check('  and the commit then verifies', okc.state is State.PASS,
              f'{okc.state}[{okc.code}]')


def test_D_suppressed_stderr_cannot_be_read_as_success():
    print('\nD. the runner does not let stderr be discarded')
    with tempfile.TemporaryDirectory() as d:
        r = fresh_repo(d)
        o = CC.run(['add', 'does_not_exist.py'], repo=r)
        check('a failing git call returns a refusal, not a value',
              o.state is State.FAIL
              and o.evidence['reason'] == CC.COMMAND_FAILED,
              f'{o.state}[{o.code}]')
        check('  carrying the exit status', o.evidence['returncode'] != 0)
        check('  and the stderr text, which the caller cannot throw away',
              'did not match' in o.evidence['stderr'],
              repr(o.evidence['stderr'][:70]))


def test_E_a_reported_sha_must_be_the_verified_one():
    print('\nE. the sha reported is the sha checked')
    with tempfile.TemporaryDirectory() as d:
        r = fresh_repo(d)
        (r / 'a.py').write_text('x = 1\n')
        git(r, 'add', 'a.py')
        git(r, 'commit', '-q', '-m', 'a')
        head = git(r, 'rev-parse', 'HEAD').stdout.strip()
        o = CC.verify_commit('HEAD', reported_as='deadbee', repo=r)
        check('a mismatched reported sha is refused', o.state is State.FAIL
              and o.evidence['reason'] == CC.SHA_MISMATCH,
              f'{o.state}[{o.code}]')
        ok = CC.verify_commit('HEAD', reported_as=head[:7], repo=r)
        check('  and the short sha of the real commit is accepted',
              ok.state is State.PASS, f'{ok.state}[{ok.code}]')
        gone = CC.verify_commit('0' * 40, repo=r)
        check('  a sha that is not a commit here is refused',
              gone.state is State.FAIL
              and gone.evidence['reason'] == CC.NO_SUCH_COMMIT)


def test_F_commit_and_push_are_separate_verdicts():
    print('\nF. COMMITTED is not PUSHED')
    with tempfile.TemporaryDirectory() as d:
        bare = pathlib.Path(d) / 'remote.git'
        subprocess.run(['git', 'init', '-q', '--bare', str(bare)], check=True)
        work = pathlib.Path(d) / 'work'
        work.mkdir()
        r = fresh_repo(work)
        git(r, 'remote', 'add', 'origin', str(bare))
        git(r, 'push', '-q', '-u', 'origin', 'main')
        (r / 'new.py').write_text('z = 3\n')
        git(r, 'add', 'new.py')
        git(r, 'commit', '-q', '-m', 'unpushed work')
        c = CC.verify_commit('HEAD', expect_paths=['new.py'], repo=r)
        check('the commit verifies', c.state is State.PASS,
              f'{c.state}[{c.code}]')
        p = CC.verify_pushed('main', sha='HEAD', repo=r)
        check('  but the push does NOT, because the remote is behind',
              p.state is State.FAIL and p.evidence['reason'] == CC.NOT_PUSHED,
              f'{p.state}[{p.code}]')
        check('  and it says why exit status cannot tell the difference',
              'Everything up-to-date' in p.detail, p.detail[:120])
        git(r, 'push', '-q', 'origin', 'main')
        p2 = CC.verify_pushed('main', sha='HEAD', repo=r)
        check('  after a real push the remote carries it',
              p2.state is State.PASS, f'{p2.state}[{p2.code}]')
        # AND THE SECOND PUSH: exits zero, moves nothing.
        again = subprocess.run(['git', 'push', 'origin', 'main'], cwd=r,
                               capture_output=True, text=True)
        check('  a redundant push exits 0 and says Everything up-to-date, '
              'which is why exit status is not evidence',
              again.returncode == 0
              and 'up-to-date' in (again.stderr + again.stdout),
              repr((again.stderr + again.stdout)[:60]))


def test_G_working_tree_state_is_reported_not_conflated():
    print('\nG. a dirty tree is reported, and is not a failure')
    with tempfile.TemporaryDirectory() as d:
        r = fresh_repo(d)
        (r / 'a.py').write_text('x = 1\n')
        git(r, 'add', 'a.py')
        git(r, 'commit', '-q', '-m', 'a')
        (r / 'untracked.py').write_text('w = 9\n')
        o = CC.verify_commit('HEAD', expect_paths=['a.py'], repo=r)
        check('the commit still verifies', o.state is State.PASS,
              f'{o.state}[{o.code}]')
        check('  and the tree is reported as dirty',
              o.evidence['working_tree_is_clean'] is False
              and o.evidence['working_tree_dirty_entries'],
              str(o.evidence['working_tree_dirty_entries']))
        check('  with the count in the detail line, so a reader is told rather '
              'than left to assume', 'uncommitted' in o.detail, o.detail[:110])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_a_real_commit_verifies,
               test_B_a_commit_that_does_not_carry_the_work,
               test_C_the_atomic_add_reproduced_not_mocked,
               test_D_suppressed_stderr_cannot_be_read_as_success,
               test_E_a_reported_sha_must_be_the_verified_one,
               test_F_commit_and_push_are_separate_verdicts,
               test_G_working_tree_state_is_reported_not_conflated):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
