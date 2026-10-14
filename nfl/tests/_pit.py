"""Test helper: run a historical replay under a REAL point-in-time manifest at the replay's own cutoff (PIT-D1).

Production replays set NFL_PIT_MANIFEST before the process starts, so every module-level PIT.resolve() is correct.
A test activates the manifest after import, so `at_cutoff` also re-binds the fixed-path attributes those modules
resolved at import (TEAM_GAME / TG) and restores them afterwards. Nothing is hand-edited: the manifest is built by
point_in_time.build from the tree's own clocks, into a temporary directory."""
from __future__ import annotations

import contextlib
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.warehouse import point_in_time as PIT  # noqa: E402

_LIVE_TG = _REPO / 'nfl/warehouse/TEAM_GAME.json'
_BUILT: dict = {}


def manifest(cutoff: str, label: str) -> pathlib.Path:
    if cutoff not in _BUILT:
        import atexit
        import shutil
        d = tempfile.mkdtemp(prefix='pit_test_')
        atexit.register(shutil.rmtree, d, True)          # a suite run must not leak a manifest per call onto the disk
        out, _ = PIT.build(cutoff, label, 'TEST_REPLAY: the replayed slate\'s own cutoff', out_dir=d)
        _BUILT[cutoff] = out
    return _BUILT[cutoff]


@contextlib.contextmanager
def at_cutoff(cutoff: str, label: str = 'TEST'):
    path = manifest(cutoff, label)
    saved = []
    PIT._reset_for_tests(path)
    try:
        lawful = PIT.resolve(_LIVE_TG)
        for m in list(sys.modules.values()):
            for attr in ('TEAM_GAME', 'TG'):
                v = getattr(m, attr, None)
                if isinstance(v, pathlib.Path) and v == _LIVE_TG:
                    saved.append((m, attr, v))
                    setattr(m, attr, lawful)
        yield path
    finally:
        PIT._reset_for_tests(None)
        for m, attr, v in saved:
            setattr(m, attr, v)


@contextlib.contextmanager
def vintage_team_game(commit: str):
    """LOGIC fixtures only: point every loaded module's TEAM_GAME / TG at the warehouse file as it stood at `commit`
    (read from git, never edited), and restore afterwards. Pair it with pit_exempt: the state is then stamped
    NOT_POINT_IN_TIME, because the derived caches and captures are still today's."""
    import shutil
    import subprocess
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='tg_vintage_')) / 'TEAM_GAME.json'
    tmp.write_bytes(subprocess.run(['git', 'show', f'{commit}:nfl/warehouse/TEAM_GAME.json'], cwd=_REPO,
                                   capture_output=True, check=True).stdout)
    saved = []
    for m in list(sys.modules.values()):
        for attr in ('TEAM_GAME', 'TG'):
            v = getattr(m, attr, None)
            if isinstance(v, pathlib.Path) and v == _LIVE_TG:
                saved.append((m, attr, v))
                setattr(m, attr, tmp)
    try:
        yield tmp
    finally:
        for m, attr, v in saved:
            setattr(m, attr, v)
        shutil.rmtree(tmp.parent, ignore_errors=True)
