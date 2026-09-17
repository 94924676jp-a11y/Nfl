"""Current-season QB incumbency rows, so the previous game is the previous game.

WHAT THIS FIXES. `qb3_lib.load_qb_panel()` reads `panel_p3.csv.gz`, which holds
2020-2025 and a maximum ordinal of 202518. Every 2026 week-2 forecast therefore
gave all 32 clubs a 2025 week-18 previous primary and classed all 32 a season
opener. `qb_allocation.panel_freshness` now BLOCKS on that; this module is the
data that stops it firing.

WHY A NEW MODULE AND NOT A REWRITE OF THE PANEL. `panel_p3.csv.gz` is a frozen
input whose bytes are inside the identity of every sealed candidate. Rewriting
it would silently move every historical fit. These rows are ADDITIVE: the panel
is unchanged and untouched, and a caller that does not ask for current-season
rows gets exactly what it got before.

TWO SOURCES, IN A DECLARED ORDER, AND THE PROXY IS NAMED AS ONE
---------------------------------------------------------------
1. PLAY-BY-PLAY -- `qb_dropback == 1` grouped by `posteam` and
   `passer_player_id`. This is the SAME quantity `qb3_lib.primary_of` counts on
   the panel, so a row built this way is the same kind of row.
2. SNAP COUNTS -- the quarterback with the most `offense_snaps`. A PROXY. It
   extends coverage from 20 clubs to 30 and every row it produces is marked
   `source='snap_proxy'` and counted.

Measured 2026-09-17 on week 1: the two agree on 20 of 20 clubs where both
exist, with 0 snap rows failing the `pfr_id -> gsis_id` bridge. TWENTY OF
TWENTY IS n = 20 AND IS NOT A VALIDATED RATE. No historical snap capture exists
in this repository to check it against, and its risk case is a mid-game change
where the starter leaves early and the snap leader is not the dropback primary.
Play-by-play is preferred wherever it exists precisely for that reason.

3. NOTHING. A club with neither is returned in `missing_clubs` and gets NO row.
   It is never inferred, and the caller keeps the stale panel answer for it --
   visibly, because the club is named.

THE CLOCK IS ENFORCED, NOT ASSERTED. Every capture carries a retrieval instant
and a capture whose instant is not strictly before `as_of` is DROPPED, with the
drop counted. Week-1 results are pregame evidence for a week-2 forecast and
postgame bytes for a week-1 one; the clock is what tells those apart, so there
is no path through this module that reads the future.
"""
from __future__ import annotations

import collections
import csv
import datetime as _dt
import glob
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'current-season-qb-panel-1'

PBP_GLOB = 'nfl/research/postgame/pbp_%d.*.csv.gz'
SNAP_GLOB = 'nfl/availability_raw/snap_counts_%d.*.csv.gz'
ROSTER_GLOB = 'nfl/vintage/weekly_rosters.*raw.csv*'

SOURCES = ('play_by_play', 'snap_proxy')

_CACHE: dict = {}


class CurrentSeasonPanelError(ValueError):
    """Named so a caller can tell a refusal from an arithmetic failure."""


def _parse(ts):
    if not ts:
        return None
    s = str(ts).strip().replace('Z', '+00:00')
    try:
        d = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def _lawful(retrieved, as_of):
    """STRICTLY before. A capture taken at the forecast instant is not evidence
    that existed before it."""
    if as_of is None:
        return True
    r = _parse(retrieved)
    return r is not None and r < _parse(as_of)


def _pbp_rows(season, week, as_of):
    """(team -> Counter(passer -> dropbacks), evidence). Widest LAWFUL capture."""
    best, ev = None, {'considered': 0, 'dropped_by_clock': 0, 'blob': None,
                      'retrieved_at': None, 'games': []}
    for f in sorted(glob.glob(str(_REPO / (PBP_GLOB % season)))):
        prov = pathlib.Path(str(f).replace('.csv.gz', '.csv.provenance.json'))
        if not prov.exists():
            continue
        p = json.loads(prov.read_text())
        ev['considered'] += 1
        if not _lawful(p.get('retrieved_at'), as_of):
            ev['dropped_by_clock'] += 1
            continue
        n = len(p.get('games') or [])
        if best is None or n > best[0]:
            best = (n, f, p)
    if best is None:
        return {}, ev
    _, f, p = best
    ev.update(blob=pathlib.Path(f).name, retrieved_at=p.get('retrieved_at'),
              games=list(p.get('games') or []))
    db = collections.defaultdict(collections.Counter)
    with gzip.open(f, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            if str(r.get('week')) != str(week) or not r.get('posteam'):
                continue
            if (r.get('qb_dropback') or '0') not in ('1', '1.0'):
                continue
            pid = (r.get('passer_player_id') or '').strip()
            if pid:
                db[r['posteam']][pid] += 1
    return dict(db), ev


def _identity_bridge():
    """pfr_id -> (gsis_id, name). Identity is by ID. Name matching is FORBIDDEN
    here, exactly as in `appearance_panel_2026`."""
    ident = {}
    for f in sorted(glob.glob(str(_REPO / ROSTER_GLOB))):
        op = gzip.open if str(f).endswith('.gz') else open
        with op(f, 'rt', errors='ignore') as fh:
            for r in csv.DictReader(fh):
                pid = (r.get('pfr_id') or '').strip()
                g = (r.get('gsis_id') or '').strip()
                if pid and g and pid not in ident:
                    ident[pid] = (g, (r.get('full_name') or '').strip())
    return ident


def _snap_rows(season, week, as_of):
    """(team -> [(snaps, gsis_id, name)], evidence). Widest LAWFUL capture."""
    ident = _identity_bridge()
    best, ev = None, {'considered': 0, 'dropped_by_clock': 0, 'blob': None,
                      'retrieved_at': None, 'unresolved_identity': 0,
                      'n_identity_bridge': len(ident)}
    for f in sorted(glob.glob(str(_REPO / (SNAP_GLOB % season)))):
        meta = pathlib.Path(str(f).replace('.csv.gz', '.meta.json'))
        if not meta.exists():
            continue
        m = json.loads(meta.read_text())
        ev['considered'] += 1
        if not _lawful(m.get('first_retrieved_at'), as_of):
            ev['dropped_by_clock'] += 1
            continue
        n = int(m.get('n_bytes') or 0)
        if best is None or n > best[0]:
            best = (n, f, m)
    if best is None or not ident:
        return {}, ev
    _, f, m = best
    ev.update(blob=pathlib.Path(f).name,
              retrieved_at=m.get('first_retrieved_at'))
    out = collections.defaultdict(list)
    with gzip.open(f, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            if r.get('position') != 'QB' or str(r.get('week')) != str(week):
                continue
            got = ident.get((r.get('pfr_player_id') or '').strip())
            if not got:
                ev['unresolved_identity'] += 1
                continue
            out[r['team']].append((float(r.get('offense_snaps') or 0),
                                   got[0], got[1]))
    return dict(out), ev


def rows_for(season: int, week: int, as_of=None, all_clubs=None) -> Outcome:
    """Panel-shaped rows for ONE current-season week.

    Shape matches `qb3_lib.load_qb_panel()`: season, week, team, pid, name, db,
    ord. `db` is a real dropback count from play-by-play, or -- on a snap-proxy
    row -- the OFFENSIVE SNAP COUNT, which is NOT a dropback count and is
    labelled so no caller can mistake one for the other.
    """
    key = (int(season), int(week), str(as_of))
    if key in _CACHE:
        return _CACHE[key]
    pbp, pev = _pbp_rows(season, week, as_of)
    snap, sev = _snap_rows(season, week, as_of)
    o = int(season) * 100 + int(week)
    rows, by_source = [], collections.Counter()
    for t, c in sorted(pbp.items()):
        for pid, n in c.items():
            rows.append({'season': int(season), 'week': int(week), 'team': t,
                         'pid': pid, 'name': None, 'db': int(n), 'ord': o,
                         'source': 'play_by_play'})
        by_source['play_by_play'] += 1
    for t, v in sorted(snap.items()):
        if t in pbp:
            continue                       # play-by-play wins where it exists
        for snaps, pid, name in sorted(v, reverse=True):
            rows.append({'season': int(season), 'week': int(week), 'team': t,
                         'pid': pid, 'name': name, 'db': int(snaps), 'ord': o,
                         'source': 'snap_proxy',
                         'db_is_offensive_snaps_not_dropbacks': True})
        by_source['snap_proxy'] += 1
    covered = set(pbp) | set(snap)
    missing = sorted(set(all_clubs or ()) - covered)
    ev = {'spec_version': SPEC_VERSION, 'season': int(season),
          'week': int(week), 'ordinal': o, 'as_of': str(as_of),
          'n_rows': len(rows), 'n_clubs': len(covered),
          'clubs_by_source': dict(by_source),
          'missing_clubs': missing, 'n_missing_clubs': len(missing),
          'play_by_play': pev, 'snap_counts': sev,
          'agreement_note': 'the snap leader and the dropback primary agreed '
                            '20 of 20 on the 2026 week-1 overlap; n = 20 is '
                            'not a validated rate'}
    if not rows:
        out = Outcome.blocked(
            'CURRENT_SEASON_PANEL_EMPTY',
            f'no lawful current-season evidence for {season} week {week} at or '
            f'before {as_of}. Zero rows is an absence, not a season with no '
            f'quarterbacks.', cause=Cause.DATA, **ev)
    else:
        out = Outcome.ok('CURRENT_SEASON_PANEL_OK', value=rows,
                         detail=f'{len(rows)} row(s) over {len(covered)} club(s)'
                                f'; {len(missing)} club(s) have NO current-'
                                f'season evidence and keep the frozen panel',
                         **ev)
    _CACHE[key] = out
    return out


def rows_before(season: int, week: int, as_of=None, all_clubs=None) -> Outcome:
    """Every current-season week STRICTLY EARLIER than `week`, concatenated.

    A week-4 forecast needs weeks 1-3, not just week 1. The loop is here rather
    than at the call site so no caller can forget a week.
    """
    got, evs, seen = [], [], set()
    miss = None
    for w in range(1, int(week)):
        o = rows_for(season, w, as_of=as_of, all_clubs=all_clubs)
        evs.append({'week': w, 'state': o.state.value, 'code': o.code,
                    'n_rows': len(o.value or []) if o.state is State.PASS else 0,
                    'missing_clubs': o.evidence.get('missing_clubs')})
        if o.state is State.PASS:
            got.extend(o.value)
            seen |= {r['team'] for r in o.value}
            miss = o.evidence.get('missing_clubs') if miss is None else \
                sorted(set(miss) & set(o.evidence.get('missing_clubs') or ()))
    ev = {'spec_version': SPEC_VERSION, 'season': int(season),
          'through_week_exclusive': int(week), 'as_of': str(as_of),
          'n_rows': len(got), 'n_clubs': len(seen), 'weeks': evs,
          'missing_clubs': sorted(set(all_clubs or ()) - seen),
          'n_missing_clubs': len(set(all_clubs or ()) - seen)}
    if not got:
        return Outcome.blocked(
            'CURRENT_SEASON_PANEL_EMPTY',
            f'no lawful current-season evidence earlier than {season} week '
            f'{week} at or before {as_of}.', cause=Cause.DATA, **ev)
    return Outcome.ok('CURRENT_SEASON_PANEL_OK', value=got,
                      detail=f'{len(got)} row(s) over {len(seen)} club(s) from '
                             f'{season} weeks 1-{int(week) - 1}', **ev)


def cache_clear():
    _CACHE.clear()
