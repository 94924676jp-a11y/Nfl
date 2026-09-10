"""gsis_id -> player name, for DISPLAY ONLY.

A NAME IS NOT A FORECAST INPUT. Nothing in the model consumes it, no
projection changes if it is missing, and a board that cannot resolve one shows
the gsis_id rather than guessing or dropping the row. It is still taken from a
pre-kickoff capture, because reaching for a post-kickoff file out of
convenience is how a chronology rule gets treated as negotiable in the one
place it happens not to matter -- and then in the places it does.

Sources, in order of coverage:
  1. the raw weekly-roster capture, which carries `full_name` for ~2,945
     players where the reduced form in `nfl/vintage/` carries none;
  2. any injuries capture, which carries `full_name` for the players on it.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import gzip
import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]
_CACHE: dict = {}


def _parse(t):
    if not t:
        return None
    try:
        d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _rows(path):
    op = gzip.open if str(path).endswith('.gz') else open
    try:
        with op(path, 'rt') as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeDecodeError):
        return []


def lookup(as_of=None) -> dict:
    """Every name resolvable from captures observed at or before `as_of`."""
    key = as_of or 'ALL'
    if key in _CACHE:
        return _CACHE[key]
    cut = _parse(as_of)
    out = {}

    # The raw roster capture. Its observation time is the capture that
    # produced it; the manifest is the authority on when that was.
    from nfl.research.shadow import information_set as IS
    try:
        first = IS.first_observation()
    except Exception:                                        # noqa: BLE001
        first = {}
    by_sha = {sha: o for (src, sha), o in first.items()
              if src in ('weekly_rosters', 'injuries')}

    for path in sorted(glob.glob(str(_REPO / 'nfl_vintage' / 'raw' / '*.csv'))):
        base = os.path.basename(path)
        if not base.startswith('weekly_rosters.'):
            continue
        stem = base.split('.')[1]
        obs = next((o for sha, o in by_sha.items() if sha.startswith(stem)),
                   None)
        if cut is not None and (obs is None or obs['observed_at'] > cut):
            continue
        for r in _rows(path):
            g = r.get('gsis_id')
            nm = r.get('full_name') or r.get('player_name')
            if g and nm:
                out.setdefault(g, nm)

    for path in sorted(glob.glob(str(_REPO / 'nfl' / 'vintage'
                                     / 'injuries.*.csv.gz'))):
        stem = os.path.basename(path).split('.')[1]
        obs = next((o for sha, o in by_sha.items() if sha.startswith(stem)),
                   None)
        if cut is not None and (obs is None or obs['observed_at'] > cut):
            continue
        for r in _rows(path):
            g = r.get('gsis_id')
            nm = r.get('full_name')
            if g and nm:
                out.setdefault(g, nm)

    _CACHE[key] = out
    return out


def cache_clear():
    _CACHE.clear()
