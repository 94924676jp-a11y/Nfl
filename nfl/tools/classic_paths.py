"""Where a Classic chain reads and writes its slate artifacts (task #45, owner decision E2: arms run beside each other).

The production chain uses nfl/dfs/salaries. A declared arm (the corrected forecast) runs the SAME governed tools with
NFL_CLASSIC_OUT_DIR set to its own folder under nfl/dfs/salaries/arms/<ARM>/, so it can never overwrite a production
file and every artifact it writes carries its own release record. The override must stay inside the repository
(relative paths and hashes are recorded against it) and must not be the production folder under another spelling.
"""
from __future__ import annotations

import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]
PRODUCTION = _REPO / 'nfl/dfs/salaries'
ARMS = PRODUCTION / 'arms'


def out_dir() -> pathlib.Path:
    v = os.environ.get('NFL_CLASSIC_OUT_DIR')
    if not v:
        return PRODUCTION
    p = pathlib.Path(v)
    p = (p if p.is_absolute() else _REPO / p).resolve()
    if not p.is_relative_to(ARMS.resolve()):
        raise SystemExit(f'NFL_CLASSIC_OUT_DIR={v!r} must be a folder under {ARMS.relative_to(_REPO)}/')
    p.mkdir(parents=True, exist_ok=True)
    return p


def arm() -> str:
    """The declared arm of this process: INCUMBENT unless NFL_CLASSIC_ARM names another."""
    return os.environ.get('NFL_CLASSIC_ARM') or 'INCUMBENT'
