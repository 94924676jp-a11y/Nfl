"""Can the worker touch the files that authorize the worker?

For as long as this transport has existed, yes -- all of them.

`enforce_protected_paths` was correct. `PROTECTED_PATHS` was correct. The
list of things a worker may not write was right there and enforced. What was
wrong sat one layer below: `changed_paths()` handed the check a corrupted
path, and a corrupted path matches no prefix, so the check passed everything.

    .github/workflows/nfl-capture.yml   ->  github/workflows/nfl-capture.yml
    coordination/AUTOMATION_POLICY.json ->  oordination/AUTOMATION_POLICY.json

`git status --porcelain` is fixed-width: two status columns, then a space.
`_git` stripped the whole output; an UNSTAGED modification has a space in
column one; stripping ate it; `ln[3:]` then ate the first character of the
path. Measured 2026-09-25 by running an actual MOCK pass: every protected
path was uncaught, AUTOMATION_POLICY.json among them -- the file holding the
two flags that authorize spending money.

The exposure was not a corner case. The engineering packet instructs the
worker "Do not commit. The workflow commits what you leave in the working
tree", so its changes are unstaged BY CONTRACT. The single arrangement the
parser got wrong is the one the system asks for on every task.

Reading the code did not find this and could not have: both halves looked
right. Running the loop found it in one pass. That is the lesson worth more
than the fix.

So these tests drive real git state rather than fixtures -- a fixture would
encode whatever the author believed porcelain emits, which is exactly the
belief that was wrong.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _sh(*args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


class _Sandbox:
    """A real repository, because the bug was in reading real git output."""

    def __enter__(self):
        self.d = tempfile.TemporaryDirectory()
        self.root = Path(self.d.name)
        _sh('git', 'init', '-q', cwd=self.root)
        _sh('git', 'config', 'user.email', 'a@b.c', cwd=self.root)
        _sh('git', 'config', 'user.name', 't', cwd=self.root)
        for rel in self.FILES:
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('seed\n')
        _sh('git', 'add', '-A', cwd=self.root)
        _sh('git', 'commit', '-qm', 'seed', cwd=self.root)
        from coordination.orchestrator import state as S
        self._prev = S.REPO
        S.REPO = self.root
        return self

    FILES = ('.github/workflows/w.yml', 'coordination/AUTOMATION_POLICY.json',
             'coordination/OWNER_DECISIONS.md',
             'coordination/orchestrator/MODELS.json',
             'nfl/production/authorization.py', 'nfl/production/review/gate.py',
             'nfl/dfs/ordinary.py')

    def __exit__(self, *exc):
        from coordination.orchestrator import state as S
        S.REPO = self._prev
        self.d.cleanup()

    def reset(self):
        _sh('git', 'checkout', '--', '.', cwd=self.root)
        _sh('git', 'clean', '-fdq', cwd=self.root)
        _sh('git', 'reset', '-q', cwd=self.root)
        _sh('git', 'checkout', '--', '.', cwd=self.root)

    def edit(self, rel, stage=False):
        (self.root / rel).write_text('seed\nworker\n')
        if stage:
            _sh('git', 'add', rel, cwd=self.root)


def _protected():
    from coordination.orchestrator import contracts as C
    return [p for p in C.PROTECTED_PATHS]


def test_changed_paths_reports_the_path_git_reported():
    """The regression itself: no character may be lost, in any stage state."""
    from coordination.orchestrator import github_runtime as G
    with _Sandbox() as sb:
        for rel in sb.FILES:
            for stage in (False, True):
                sb.reset()
                sb.edit(rel, stage=stage)
                got = G.changed_paths()
                check(f'{"staged " if stage else "unstaged"} {rel}',
                      got == [rel], f'got {got!r}')


def test_every_protected_path_is_refused_when_the_worker_leaves_it_unstaged():
    """The exposure, at the exact contract the packet imposes on the worker."""
    from coordination.orchestrator import github_runtime as G, locks
    from coordination.orchestrator import contracts as C
    with _Sandbox() as sb:
        for rel in _protected():
            target = rel.rstrip('/')
            if target.endswith('/') or '.' not in Path(target).name:
                target = f'{target}/w.yml'
            if not (sb.root / target).exists():
                continue
            sb.reset()
            sb.edit(target)
            try:
                locks.enforce_protected_paths(G.changed_paths(), C.Worker.ENGINEER)
                check(f'unstaged write to {target} refused', False,
                      'NOT CAUGHT -- the worker may edit its own authority')
            except locks.Refusal as r:
                check(f'unstaged write to {target} refused',
                      r.code == 'PROTECTED_PATH_WRITTEN', r.code)


def test_an_ordinary_path_is_still_allowed():
    """A containment check that refuses everything protects nothing anyone
    would notice, because the loop simply stops working."""
    from coordination.orchestrator import github_runtime as G, locks
    from coordination.orchestrator import contracts as C
    with _Sandbox() as sb:
        sb.reset()
        sb.edit('nfl/dfs/ordinary.py')
        try:
            locks.enforce_protected_paths(G.changed_paths(), C.Worker.ENGINEER)
            check('ordinary edit allowed', True)
        except locks.Refusal as r:
            check('ordinary edit allowed', False, f'wrongly refused {r.code}')


def test_a_rename_out_of_a_protected_path_counts_as_writing_it():
    """Moving a file away is not a way to stop it being protected."""
    from coordination.orchestrator import github_runtime as G, locks
    from coordination.orchestrator import contracts as C
    with _Sandbox() as sb:
        sb.reset()
        _sh('git', 'mv', 'nfl/production/authorization.py',
            'nfl/production/elsewhere.py', cwd=sb.root)
        got = G.changed_paths()
        check('rename reports both sides',
              'nfl/production/authorization.py' in got, got)
        try:
            locks.enforce_protected_paths(got, C.Worker.ENGINEER)
            check('rename off a protected path refused', False, 'NOT CAUGHT')
        except locks.Refusal:
            check('rename off a protected path refused', True)


def test_a_path_with_a_space_survives():
    """`-z` exists for this. A split on whitespace would truncate here, and
    the truncated head could fall outside a protected prefix."""
    from coordination.orchestrator import github_runtime as G
    with _Sandbox() as sb:
        sb.reset()
        p = sb.root / '.github' / 'workflows' / 'two words.yml'
        p.write_text('x\n')
        got = G.changed_paths()
        check('spaced path intact', '.github/workflows/two words.yml' in got, got)


def test_deletion_of_a_protected_file_is_caught():
    """Deleting the kill switch is not less serious than editing it."""
    from coordination.orchestrator import github_runtime as G, locks
    from coordination.orchestrator import contracts as C
    with _Sandbox() as sb:
        sb.reset()
        os.remove(sb.root / 'coordination' / 'AUTOMATION_POLICY.json')
        got = G.changed_paths()
        check('deletion reported', 'coordination/AUTOMATION_POLICY.json' in got, got)
        try:
            locks.enforce_protected_paths(got, C.Worker.ENGINEER)
            check('deletion refused', False, 'NOT CAUGHT')
        except locks.Refusal:
            check('deletion refused', True)
