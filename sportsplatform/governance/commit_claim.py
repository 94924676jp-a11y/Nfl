"""A commit is claimed by reading git, never by a command appearing to work.

THE COMPANION TO artifact_claim, AND IT EXISTS FOR THE SAME REASON ON THE SAME
DAY. Minutes after writing the rule that an artifact must be verified from the
filesystem, I ran:

    git add sportsplatform/... nfl/tests/... COMMANDS.md 2>/dev/null; git commit ...

`COMMANDS.md` exists in the MLB repository and not this one. `git add` fails
ATOMICALLY on an unknown pathspec -- it staged nothing at all, not merely
everything else -- and its stderr went to /dev/null. The commit then reported
"no changes added to commit", which is a message people skim past, and the
work was one step from being announced as committed by a command that had
done nothing.

WHAT MAKES THIS DIFFERENT FROM ORDINARY CARE

Three properties of git conspire here and each is individually reasonable:

  1. `git add` is atomic over its pathspecs. One bad path stages zero files,
     so a nine-of-ten-correct command is not nine-tenths successful.
  2. `git commit` with nothing staged exits NON-ZERO, but in a `;`-chained
     shell line the previous failure is already invisible and the message is
     easy to read as routine.
  3. `git push` on an unchanged branch prints "Everything up-to-date" and
     exits ZERO. A push that pushed nothing is indistinguishable from a push
     that pushed something, by exit status alone.

So the three states have to be verified separately, from git, and the module
refuses to collapse them: STAGED is not COMMITTED and COMMITTED is not PUSHED.

DELIBERATELY NARROW. Three verifiers and a runner. This is not a workflow
framework and must not grow into one.
"""
from __future__ import annotations

import pathlib
import subprocess

from sportsplatform.governance.outcome import Cause, Outcome, State

SPEC_VERSION = 'commit-claim-1'

CODE_OK = 'COMMIT_CLAIM_VERIFIED'
CODE_UNVERIFIED = 'COMMIT_CLAIM_WITHOUT_VERIFIED_GIT_STATE'

NOT_STAGED = 'EXPECTED_PATHS_NOT_STAGED'
NO_SUCH_COMMIT = 'COMMIT_DOES_NOT_EXIST'
SHA_MISMATCH = 'REPORTED_SHA_IS_NOT_THE_COMMIT_VERIFIED'
NOT_IN_COMMIT = 'EXPECTED_PATHS_NOT_IN_COMMIT'
NOT_PUSHED = 'REMOTE_DOES_NOT_CARRY_THE_COMMIT'
COMMAND_FAILED = 'GIT_COMMAND_FAILED'


def run(args, *, repo=None, check: bool = True) -> Outcome:
    """A git call whose stderr CANNOT be discarded by the caller.

    Every failure comes back as a refusal carrying the exit status and the
    stderr text, so `2>/dev/null` is not available as a way to make a broken
    command look fine.
    """
    cwd = str(repo) if repo else None
    p = subprocess.run(['git'] + list(args), cwd=cwd, capture_output=True,
                       text=True)
    ev = {'spec_version': SPEC_VERSION, 'argv': ['git'] + list(args),
          'returncode': p.returncode, 'stdout': p.stdout,
          'stderr': p.stderr.strip()}
    if check and p.returncode != 0:
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'`git {" ".join(args)}` exited {p.returncode}: '
            f'{p.stderr.strip() or "(no stderr)"}',
            cause=Cause.GOVERNANCE, reason=COMMAND_FAILED, **ev)
    return Outcome.ok('GIT_OK', value=p.stdout, detail=f'git {args[0]}', **ev)


def _lines(s):
    return [x for x in (s or '').splitlines() if x.strip()]


def verify_staged(expect_paths, *, repo=None, label='staging') -> Outcome:
    """Are the intended paths actually in the index?

    This is the check that `git add a b_missing 2>/dev/null` needs: git staged
    NOTHING, and nothing downstream noticed.
    """
    o = run(['diff', '--cached', '--name-only'], repo=repo)
    if o.state is not State.PASS:
        return o
    staged = set(_lines(o.value))
    want = [str(p) for p in expect_paths]
    missing = sorted(p for p in want if p not in staged)
    ev = {'spec_version': SPEC_VERSION, 'label': label,
          'n_staged': len(staged), 'staged': sorted(staged),
          'expected': want, 'missing': missing}
    if missing:
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: {len(missing)} expected path(s) are not staged: '
            f'{missing}. `git add` is ATOMIC over its pathspecs -- one path '
            f'that does not exist stages zero files, not all the others -- so '
            f'a partially wrong add is a completely empty one.',
            cause=Cause.GOVERNANCE, reason=NOT_STAGED, **ev)
    return Outcome.ok(CODE_OK, value=sorted(staged),
                      detail=f'{label}: {len(want)} expected path(s) staged',
                      **ev)


def verify_commit(sha='HEAD', *, expect_paths=(), reported_as=None, repo=None,
                  label='commit') -> Outcome:
    """The commit exists, is the one being reported, and contains the files."""
    r = run(['rev-parse', '--verify', f'{sha}^{{commit}}'], repo=repo,
            check=False)
    if r.state is not State.PASS or not r.value.strip():
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: {sha} does not resolve to a commit in this repository.',
            cause=Cause.GOVERNANCE, reason=NO_SUCH_COMMIT, sha=str(sha),
            spec_version=SPEC_VERSION, label=label)
    resolved = r.value.strip()
    ev = {'spec_version': SPEC_VERSION, 'label': label, 'sha': resolved,
          'short_sha': resolved[:7]}
    if reported_as is not None:
        rep = str(reported_as).strip()
        if not (resolved.startswith(rep) or rep.startswith(resolved[:7])):
            return Outcome.fail(
                CODE_UNVERIFIED,
                f'{label}: the sha being reported ({rep}) is not the commit '
                f'that was verified ({resolved[:12]}).',
                cause=Cause.GOVERNANCE, reason=SHA_MISMATCH,
                reported_sha=rep, **ev)
    files = run(['show', '--name-only', '--format=', resolved], repo=repo)
    if files.state is not State.PASS:
        return files
    in_commit = set(_lines(files.value))
    ev['n_files_in_commit'] = len(in_commit)
    ev['files_in_commit'] = sorted(in_commit)
    want = [str(p) for p in expect_paths]
    missing = sorted(p for p in want if p not in in_commit)
    ev['expected'] = want
    ev['missing'] = missing
    if missing:
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: commit {resolved[:7]} exists but does not contain '
            f'{missing}. A commit that happened is not a commit that carried '
            f'the work.',
            cause=Cause.GOVERNANCE, reason=NOT_IN_COMMIT, **ev)
    # WORKING TREE STATE IS REPORTED, NEVER FOLDED INTO THE VERDICT. A clean
    # commit can sit beside uncommitted changes and that is not a failure --
    # but it is a thing a reader should be told rather than left to assume.
    st = run(['status', '--porcelain'], repo=repo, check=False)
    dirty = _lines(st.value) if st.state is State.PASS else []
    ev['working_tree_dirty_entries'] = dirty
    ev['working_tree_is_clean'] = not dirty
    return Outcome.ok(
        CODE_OK, value=resolved,
        detail=f'{label}: {resolved[:7]}, {len(in_commit)} file(s), '
               f'{len(want)} expected present; working tree '
               f'{"clean" if not dirty else f"has {len(dirty)} uncommitted entry(ies)"}',
        **ev)


def verify_pushed(branch, *, sha='HEAD', remote='origin', repo=None,
                  label='push') -> Outcome:
    """Does the REMOTE carry this commit? Separate question from committing.

    `git push` on an unchanged branch prints "Everything up-to-date" and exits
    zero, so exit status cannot distinguish a push that moved the branch from
    one that moved nothing.
    """
    local = run(['rev-parse', '--verify', f'{sha}^{{commit}}'], repo=repo,
                check=False)
    if local.state is not State.PASS or not local.value.strip():
        return Outcome.fail(
            CODE_UNVERIFIED, f'{label}: {sha} is not a commit here',
            cause=Cause.GOVERNANCE, reason=NO_SUCH_COMMIT,
            spec_version=SPEC_VERSION)
    want = local.value.strip()
    ls = run(['ls-remote', remote, f'refs/heads/{branch}'], repo=repo,
             check=False)
    ev = {'spec_version': SPEC_VERSION, 'label': label, 'branch': branch,
          'remote': remote, 'local_sha': want,
          'ls_remote_stdout': (ls.value or '').strip()}
    if ls.state is not State.PASS:
        return Outcome.blocked(
            CODE_UNVERIFIED,
            f'{label}: {remote} could not be reached, so whether it carries '
            f'{want[:7]} is unknown. Unknown is not pushed.',
            cause=Cause.NETWORK, **ev)
    head = (ls.value or '').split('\t')[0].strip()
    ev['remote_sha'] = head
    if head != want:
        return Outcome.fail(
            CODE_UNVERIFIED,
            f'{label}: {remote}/{branch} is at {head[:7] or "(absent)"}, not '
            f'{want[:7]}. "Everything up-to-date" exits zero whether or not '
            f'anything was pushed.',
            cause=Cause.GOVERNANCE, reason=NOT_PUSHED, **ev)
    return Outcome.ok(
        CODE_OK, value=want,
        detail=f'{label}: {remote}/{branch} carries {want[:7]}', **ev)


def claim(branch=None, *, sha='HEAD', expect_paths=(), remote='origin',
          repo=None, quiet: bool = False) -> Outcome:
    """Commit first, push second, reported apart. Never one verdict for both."""
    c = verify_commit(sha, expect_paths=expect_paths, repo=repo)
    if not quiet:
        print(f'{"COMMITTED" if c.state is State.PASS else c.code} '
              f'{c.detail}')
    if c.state is not State.PASS or branch is None:
        return c
    p = verify_pushed(branch, sha=c.value, remote=remote, repo=repo)
    if not quiet:
        print(f'{"PUSHED" if p.state is State.PASS else p.code} {p.detail}')
    return p
