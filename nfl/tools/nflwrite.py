#!/usr/bin/env python3.12
"""Write a file into the NFL repository, or refuse. Never guess from cwd.

    cat <<'EOF' | python3.12 nfl/tools/nflwrite.py docs/thing.md
    ...
    EOF

    python3.12 nfl/tools/nflwrite.py --check          # assert the root only

WHY THIS EXISTS

Three times in one session a compound shell command of the form

    cd /home/user/nfl && nohup long_job & ; cat > FILE.md <<'EOF'

wrote FILE.md into the OTHER repository, because everything after `&` runs in
the ORIGINAL working directory. Twice it was caught by a later `git status`;
once it silently created an 81-line stray in the MLB checkout. A comment saying
"remember the cwd" would not have stopped any of them.

THE GUARD

The repository root is resolved from THIS FILE's own location, never from the
current directory, so a wrong cwd cannot mislead it. The root must carry the
NFL repository's marker files, and the destination must resolve inside it after
symlinks. Anything else is refused with a non-zero exit before a byte is
written.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

# Files that identify THIS repository and no other checkout on this machine.
MARKERS = ('nfl/production/qb_v1.py', 'nfl/tests/run_suite.py',
           'NFL_DECISION_LEDGER.md')
FOREIGN_MARKERS = ('board_config.json', 'v7/gamesim.py')


def repo_root() -> pathlib.Path:
    """The NFL root, from this file's own path. Refuses if it is not the NFL repo."""
    root = pathlib.Path(__file__).resolve().parents[2]
    missing = [m for m in MARKERS if not (root / m).exists()]
    if missing:
        raise SystemExit(
            f'NFLWRITE_ROOT_NOT_NFL_REPO: {root} is missing {missing}. This '
            f'guard resolves the root from its own file location, so a wrong '
            f'working directory cannot reach here -- a missing marker means '
            f'the checkout itself is not the NFL repository.')
    foreign = [m for m in FOREIGN_MARKERS if (root / m).exists()]
    if foreign:
        raise SystemExit(
            f'NFLWRITE_ROOT_IS_FOREIGN_REPO: {root} carries {foreign}, which '
            f'belong to another project. Refusing to treat it as the NFL root.')
    return root


def resolve(dest: str) -> pathlib.Path:
    root = repo_root()
    p = pathlib.Path(dest)
    target = (p if p.is_absolute() else root / p)
    # resolve() follows symlinks and normalises '..' BEFORE the containment
    # test, so neither can be used to escape.
    target = target.resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        raise SystemExit(
            f'NFLWRITE_DESTINATION_OUTSIDE_REPO: {target} resolves outside '
            f'{root}. Refused before writing. If this path was meant to be '
            f'inside the NFL repo, the cwd or the path is wrong -- that is the '
            f'bug this guard exists to catch.')
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('dest', nargs='?')
    ap.add_argument('--check', action='store_true',
                    help='assert the root resolves and exit')
    ap.add_argument('--append', action='store_true')
    a = ap.parse_args()
    root = repo_root()
    if a.check:
        print(f'NFLWRITE_ROOT_OK {root}')
        return 0
    if not a.dest:
        raise SystemExit('NFLWRITE_NO_DESTINATION: a destination is required')
    target = resolve(a.dest)
    data = sys.stdin.buffer.read()
    if not data:
        raise SystemExit(
            f'NFLWRITE_EMPTY_PAYLOAD: refusing to write 0 bytes to {target}. '
            f'An empty write is how a heredoc failure looks when it succeeds.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, 'ab' if a.append else 'wb') as fh:
        fh.write(data)
    print(f'NFLWRITE_OK {target} ({len(data)} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
