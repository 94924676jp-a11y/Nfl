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

N1, 2026-09-14. THREE THINGS CHANGED AND ONE DELIBERATELY DID NOT.

1. THE COMMITTED RAW ROSTER BLOBS ARE NOW READ. `nfl_vintage/` is gitignored
   (`.gitignore:7`), so source 1 above resolves 2,962 names in this working
   copy and ZERO in a fresh checkout. `nfl/vintage/weekly_rosters.*.raw.csv.gz`
   is tracked -- one blob, `bdab6ecee12d44a4`, which is the one tonight's board
   selected -- and it carries the same `full_name` column. Reading it makes
   the display name survive a clone. The ephemeral store is still read; it is
   simply no longer the only place a name can come from.

2. PRECEDENCE IS CHRONOLOGICAL, NOT ALPHABETICAL. The old form merged blobs in
   `sorted(glob(...))` order with `setdefault`, so when two lawful captures
   disagreed the winner was decided by a content hash in a filename. That is
   the defect `board.depth_rank_outcome` documents as L3, and this module had
   it too. Captures are now ordered by the observation time the manifest
   bounds them with, and the NEWEST lawful capture wins. Measured over the
   captures present here, exactly 4 of 2,962 ids carry more than one spelling
   (all of the form "Anthony Johnson" / "Anthony Johnson Jr."); none of them
   is on the DEN@KC board.

3. PER-NAME PROVENANCE IS AVAILABLE. `resolve()` returns, for every id, which
   blob and which column answered. A product row that prints a person's name
   should be able to say where the name came from, on the same terms as every
   other joined field.

Not changed: a name is still display-only, an unresolved id is still returned
as unresolved rather than guessed, and nothing here fuzzy-matches, transliterates
or falls back to a hardcoded table.
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
_RESOLVE_CACHE: dict = {}

#: Columns a capture may carry a display name in, best first. `full_name` is
#: the nflverse spelling on both the weekly roster and the injury report;
#: `player_name` appears on some older roster vintages. `football_name` is the
#: short broadcast form ("Pat") and is NOT used: it is a different field, not a
#: worse spelling of this one.
NAME_COLUMNS = ('full_name', 'player_name')

#: Where a name may be read from, as (label, glob). Every one of these is a
#: capture blob whose observation time the vintage manifest bounds.
_SOURCE_GLOBS = (
    ('weekly_rosters', str(_REPO / 'nfl' / 'vintage'
                           / 'weekly_rosters.*.raw.csv.gz')),
    ('weekly_rosters', str(_REPO / 'nfl_vintage' / 'raw'
                           / 'weekly_rosters.*.csv')),
    ('injuries', str(_REPO / 'nfl' / 'vintage' / 'injuries.*.csv.gz')),
)


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
            rdr = csv.DictReader(fh)
            return list(rdr), list(rdr.fieldnames or [])
    except (OSError, UnicodeDecodeError):
        return [], []


def _sha_stem(path) -> str:
    """The content hash the capture layer put in the filename."""
    parts = os.path.basename(path).split('.')
    return parts[1] if len(parts) > 1 else ''


def _observations() -> dict:
    """sha256 -> earliest observation, for the families that carry names."""
    from nfl.research.shadow import information_set as IS
    try:
        first = IS.first_observation()
    except Exception:                                        # noqa: BLE001
        return {}
    return {sha: o for (src, sha), o in first.items()
            if src in ('weekly_rosters', 'injuries')}


def _candidates(cut):
    """Every name-bearing blob lawful at `cut`, OLDEST FIRST.

    Oldest first is the whole point: the caller overwrites as it goes, so the
    newest lawful capture is the one whose spelling survives. A blob whose
    observation the manifest cannot bound is not lawful under a cut and is
    dropped; with no cut at all it is kept, ordered ahead of everything
    clocked so that a clocked capture always outranks an unclocked one.
    """
    by_sha = _observations()
    seen, out = set(), []
    for label, pattern in _SOURCE_GLOBS:
        for path in sorted(glob.glob(pattern)):
            stem = _sha_stem(path)
            obs = next((o for sha, o in by_sha.items()
                        if stem and sha.startswith(stem)), None)
            at = _parse((obs or {}).get('observed_at')) if obs else None
            if cut is not None and (at is None or at > cut):
                continue
            key = (label, stem)
            if key in seen:          # the same content under two filenames
                continue             # (raw / reduced, or two stores)
            seen.add(key)
            out.append({'source': label, 'path': path,
                        'blob': os.path.relpath(path, _REPO),
                        'sha16': stem,
                        'observed_at': (at.isoformat().replace('+00:00', 'Z')
                                        if at else None),
                        '_at': at})
    out.sort(key=lambda c: (c['_at'] is not None,
                            c['_at'] or dt.datetime.min.replace(
                                tzinfo=dt.timezone.utc),
                            c['blob']))
    return out


def from_capture(path, *, season=None, week=None, teams=None):
    """Every (gsis_id -> name) ONE blob carries, and what it actually was.

    Returns `(mapping, detail)`. An absent name column is a REAL STATE and is
    reported in `detail['columns_present'] == []` with an empty mapping -- it
    is not an exception and it is not silently the same as a blob that carries
    the column but no rows for these teams. The reduced roster vintage is
    exactly this case: its `reduce_cols` are (season, week, team, gsis_id,
    position) and it can never answer a name.
    """
    rows, fields = _rows(path)
    cols = [c for c in NAME_COLUMNS if c in fields]
    out, n_rows = {}, 0
    for r in rows:
        if season is not None and r.get('season') not in (None, str(season)):
            continue
        if week is not None and r.get('week') not in (None, str(week)):
            continue
        if teams is not None and r.get('team') is not None \
                and r.get('team') not in teams:
            continue
        n_rows += 1
        g = r.get('gsis_id')
        if not g:
            continue
        for c in cols:
            v = (r.get(c) or '').strip()
            if v:
                out.setdefault(g, (v, c))
                break
    detail = {'blob': os.path.relpath(path, _REPO),
              'columns_present': cols,
              'name_column_absent': not cols,
              'rows_in_scope': n_rows,
              'n_named': len(out),
              'filter': {'season': season, 'week': week,
                         'teams': sorted(teams) if teams else None}}
    return out, detail


def resolve(as_of=None, *, season=None, week=None, teams=None):
    """(gsis_id -> {'name', 'source', 'blob', 'column', 'observed_at'}).

    Newest lawful capture wins. Nothing is invented: an id absent from every
    lawful capture is simply absent from the mapping, and the caller renders
    the id.
    """
    key = (as_of or 'ALL', season, week,
           tuple(sorted(teams)) if teams else None)
    if key in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[key]
    cut = _parse(as_of)
    out, consulted = {}, []
    for c in _candidates(cut):
        m, d = from_capture(c['path'], season=season, week=week, teams=teams)
        for g, (nm, col) in m.items():
            out[g] = {'name': nm, 'source': c['source'], 'blob': c['blob'],
                      'column': col, 'observed_at': c['observed_at']}
        consulted.append({**d, 'source': c['source'],
                          'observed_at': c['observed_at']})
    _RESOLVE_CACHE[key] = (out, consulted)
    return out, consulted


def lookup(as_of=None) -> dict:
    """Every name resolvable from captures observed at or before `as_of`."""
    key = as_of or 'ALL'
    if key in _CACHE:
        return _CACHE[key]
    resolved, _ = resolve(as_of)
    out = {g: v['name'] for g, v in resolved.items()}
    _CACHE[key] = out
    return out


def cache_clear():
    _CACHE.clear()
    _RESOLVE_CACHE.clear()
