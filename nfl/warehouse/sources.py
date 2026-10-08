#!/usr/bin/env python3.12
"""GAP 8. A source registry that selects on measured properties, never on where a file sits.

THE DEFECT THIS REPLACES, WHICH HAPPENED TWICE. A capture was chosen with `sorted(glob(...))[0]`
and by directory habit. Once it read `nfl/vintage/pbp_2026` -- week 1 only, 2,756 rows -- instead of
`nfl/research/postgame/pbp_2026.6643f82adb1158c8` at weeks 1-2 and 5,489 rows, silently halving the
current season. Once it read the narrower of two depth-chart captures. Neither was detectable from
the output, because a smaller file produces smaller numbers, not an error.

WHAT SELECTION MEANS HERE. Every candidate is OPENED and measured before anything is chosen:

    coverage      distinct seasons and weeks actually present in the bytes
    completeness  non-empty rate on the fields the data type declares as required
    freshness     the newest event in the data, not the file's mtime -- a file copied today can
                  hold last month's football
    reliability   whether the candidate carries a provenance sidecar, and whether its digest
                  matches it

Candidates are ranked on the data type's own declared priority over those measures. The result names
the winner, every rejected candidate, and the measured reason for each rejection, so a selection can
be argued with.

TIERS. PRIMARY / SECONDARY / FALLBACK is a statement about AUTHORITY, not about quality: a fallback
that happens to be wider than the primary does not thereby become authoritative. Tier is compared
first, and the measures break ties inside a tier. A selection that had to drop below PRIMARY says so
in its result, because silently using a fallback is how a Sunday decision ends up resting on a news
aggregator.
"""
from __future__ import annotations

import csv
import glob
import gzip
import hashlib
import io
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.warehouse import point_in_time as PIT  # noqa: E402

PRIMARY, SECONDARY, FALLBACK = 'PRIMARY', 'SECONDARY', 'FALLBACK'
TIER_RANK = {PRIMARY: 0, SECONDARY: 1, FALLBACK: 2}

#: How many data rows to read when measuring a candidate. Measuring the whole of a 19MB
#: play-by-play capture for every selection would make the registry too slow to use, and the
#: quantities being ranked -- which seasons and weeks are present, how complete the required fields
#: are -- are established long before the file ends. DECLARED, and the cap is reported in the
#: result so a reader knows the measurement was partial.
MEASURE_ROW_CAP = 60000


class DataType:
    """One kind of data, its required fields, and its ranked candidate sources."""

    def __init__(self, name, required, season_field=None, week_field=None,
                 prefer=('tier', 'seasons', 'weeks', 'completeness', 'freshness'),
                 note=''):
        self.name = name
        self.required = tuple(required)
        self.season_field = season_field
        self.week_field = week_field
        self.prefer = tuple(prefer)
        self.note = note
        self.candidates = []

    def add(self, pattern, tier, label=None, note=''):
        self.candidates.append({'pattern': pattern, 'tier': tier,
                                'label': label or pattern, 'note': note})
        return self


def _open_text(path):
    p = pathlib.Path(path)
    if p.suffix == '.gz':
        return gzip.open(p, 'rt', newline='', encoding='utf-8', errors='replace')
    return p.open('r', newline='', encoding='utf-8', errors='replace')


def _digest(path):
    """Full-file sha256. NOT capped.

    The first version stopped after 8 MB, so a 19 MB play-by-play capture could never match a
    full-file digest in its sidecar, and the registry rejected a PRIMARY source for
    DIGEST_DISAGREES_WITH_PROVENANCE that was perfectly intact. Declaring an integrity failure
    caused by my own truncation is worse than not checking: it routed the build onto a SECONDARY
    copy while reporting a reason that was false.
    """
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


#: Measurement cache. Selecting among 393 daily schedule snapshots means opening 393 files; the
#: measurement of a given file cannot change unless the file does, so it is keyed on path and the file's
#: full content digest (it was path, size and mtime until 2026-10-08, which a same-second rewrite defeats). This is a speed cache only -- it never substitutes for opening a file that has changed,
#: and a cache miss measures the bytes exactly as a cold run would.
_CACHE_PATH = _REPO / 'nfl/derived/SOURCE_MEASUREMENT_CACHE.json'
_CACHE = None


def _cache():
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(_CACHE_PATH.read_text())
        except Exception:  # noqa: BLE001
            _CACHE = {}
    return _CACHE


def cache_flush():
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(_cache(), sort_keys=True))
    except Exception:  # noqa: BLE001
        pass


def measure(path, dt: DataType):
    """Open a candidate and measure it. Never infers anything from the filename."""
    p = pathlib.Path(path)
    st = p.stat()
    # CONTENT-BOUND KEY (independent P0 fixture DATA-measurement_cache): path|size|mtime returned a stale measurement
    # after a same-size, same-second replacement. The full-file digest is cheaper than the parse it saves.
    ck = f'{p}|{_digest(p)}|{dt.name}|{MEASURE_ROW_CAP}'
    hit = _cache().get(ck)
    if hit is not None:
        return dict(hit)
    out = {'path': str(p.relative_to(_REPO)) if str(p).startswith(str(_REPO)) else str(p),
           'bytes': p.stat().st_size}
    try:
        with _open_text(p) as fh:
            rdr = csv.DictReader(fh)
            cols = rdr.fieldnames or []
            out['n_columns'] = len(cols)
            out['missing_required_columns'] = sorted(set(dt.required) - set(cols))
            seasons, weeks = set(), set()
            filled = {f: 0 for f in dt.required if f in cols}
            n = 0
            for row in rdr:
                n += 1
                if dt.season_field and row.get(dt.season_field):
                    seasons.add(str(row[dt.season_field]).strip())
                if dt.week_field and row.get(dt.week_field):
                    weeks.add(str(row[dt.week_field]).strip())
                for f in filled:
                    v = row.get(f)
                    if v is not None and str(v).strip() not in ('', 'NA', 'None', 'nan'):
                        filled[f] += 1
                if n >= MEASURE_ROW_CAP:
                    out['measurement_truncated_at_rows'] = MEASURE_ROW_CAP
                    break
            out['n_rows_measured'] = n
            out['seasons'] = sorted(seasons)
            out['n_seasons'] = len(seasons)
            out['n_weeks'] = len(weeks)
            out['completeness'] = ({f: round(c / n, 5) for f, c in filled.items()} if n else {})
            out['completeness_min'] = (min(out['completeness'].values())
                                       if out['completeness'] else 0.0)
            out['freshest_season'] = max(seasons) if seasons else None
    except Exception as e:  # noqa: BLE001
        out['unreadable'] = f'{type(e).__name__}: {e}'
        return out
    # provenance sidecar, and whether it agrees with the bytes
    side = None
    for cand in (p.with_suffix(p.suffix + '.provenance.json'),
                 pathlib.Path(str(p).replace('.csv.gz', '.csv.provenance.json')),
                 pathlib.Path(str(p) + '.provenance.json')):
        if cand.exists():
            side = cand
            break
    out['has_provenance'] = side is not None
    if side:
        try:
            prov = json.loads(side.read_text())
            out['provenance_keys'] = sorted(prov)[:12]
            claimed = (prov.get('sha256') or prov.get('digest')
                       or prov.get('source_sha256') or prov.get('content_sha256'))
            if claimed:
                actual = _digest(p)
                c = str(claimed).lower().strip()
                # a sidecar may carry a TRUNCATED digest, which is what the filename discriminator
                # is. A prefix match is a match; only a same-length disagreement is a failure.
                out['digest_claimed'] = c[:24]
                out['digest_actual'] = actual[:24]
                out['digest_claimed_length'] = len(c)
                out['digest_matches_provenance'] = (
                    actual.startswith(c) if 8 <= len(c) < 64 else c == actual)
            out['retrieved'] = prov.get('retrieved') or prov.get('retrieved_at')
            out['source'] = prov.get('source') or prov.get('url')
        except Exception as e:  # noqa: BLE001
            out['provenance_unreadable'] = str(e)
    # last-resort tiebreak material: when two candidates are identical on every measured content
    # property -- which is what daily snapshots of the same upstream look like -- the newer
    # RETRIEVAL is preferred. Recorded as a measurement, used only after content is exhausted.
    out['retrieved_sort'] = str(out.get('retrieved') or '') or f'mtime:{int(st.st_mtime)}'
    _cache()[ck] = dict(out)
    return out


def _score(m, dt):
    """Sort key from the data type's declared preference order. Higher is better, so values are
    negated where sorting ascending."""
    key = []
    for k in dt.prefer:
        if k == 'tier':
            key.append(TIER_RANK.get(m.get('_tier'), 9))
        elif k == 'seasons':
            key.append(-m.get('n_seasons', 0))
        elif k == 'weeks':
            key.append(-m.get('n_weeks', 0))
        elif k == 'completeness':
            key.append(-round(m.get('completeness_min') or 0.0, 4))
        elif k == 'freshness':
            key.append(-int(m.get('freshest_season') or 0))
        elif k == 'rows':
            key.append(-m.get('n_rows_measured', 0))
    # ALWAYS last, never earlier: with content identical, take the newer retrieval. Putting this
    # any higher would reintroduce selection by file age, which is the habit this module exists to
    # end -- a file copied today can hold last month's football.
    key.append(_Desc(m.get('retrieved_sort') or ''))
    return tuple(key)


class _Desc:
    """Descending-order wrapper for a string sort key."""

    __slots__ = ('v',)

    def __init__(self, v):
        self.v = v

    def __lt__(self, other):
        return self.v > other.v

    def __eq__(self, other):
        return self.v == getattr(other, 'v', None)


def select(dt: DataType, season=None):
    """Measure every candidate and choose. Returns an Outcome carrying the full comparison."""
    measured, rejected = [], []
    for cand in dt.candidates:
        pat = cand['pattern'].format(season=season) if season is not None else cand['pattern']
        hits = PIT.admit(sorted(glob.glob(str(_REPO / pat))), dt.name)   # sealed run: only admitted captures
        if not hits:
            rejected.append({**cand, 'reason': 'NO_FILE_MATCHES_PATTERN', 'pattern': pat})
            continue
        for h in hits:
            m = measure(h, dt)
            m['_tier'] = cand['tier']
            m['_label'] = cand['label']
            if m.get('unreadable'):
                rejected.append({**m, 'reason': 'UNREADABLE'})
                continue
            if m['missing_required_columns']:
                rejected.append({**m, 'reason': 'MISSING_REQUIRED_COLUMNS'})
                continue
            if m['n_rows_measured'] == 0:
                rejected.append({**m, 'reason': 'ZERO_DATA_ROWS'})
                continue
            if season is not None and str(season) not in m['seasons'] and m['seasons']:
                rejected.append({**m, 'reason': f'SEASON_{season}_NOT_PRESENT'})
                continue
            if m.get('digest_matches_provenance') is False:
                rejected.append({**m, 'reason': 'DIGEST_DISAGREES_WITH_PROVENANCE'})
                continue
            measured.append(m)
    if not measured:
        return Outcome.blocked(
            f'NO_USABLE_SOURCE_{dt.name.upper()}',
            f'{len(rejected)} candidate(s) examined and none is usable for {dt.name}'
            + (f' season {season}' if season is not None else ''),
            cause=Cause.DATA, rejected=rejected[:12], data_type=dt.name)
    measured.sort(key=lambda m: _score(m, dt))
    cache_flush()
    win = measured[0]
    others = measured[1:]
    for o in others:
        rejected.append({**o, 'reason': 'RANKED_BELOW_SELECTED'})
    ev = {
        'data_type': dt.name, 'season': season,
        'selected': win['path'], 'selected_tier': win['_tier'],
        'selected_label': win['_label'],
        'n_seasons': win['n_seasons'], 'n_weeks': win['n_weeks'],
        'completeness_min': win['completeness_min'],
        'freshest_season': win['freshest_season'],
        'rows_measured': win['n_rows_measured'],
        'has_provenance': win['has_provenance'],
        'digest_matches_provenance': win.get('digest_matches_provenance'),
        'preference_order': list(dt.prefer),
        'n_candidates_measured': len(measured),
        'n_rejected': len(rejected),
        'rejected': [{'path': r.get('path') or r.get('pattern'), 'tier': r.get('_tier')
                      or r.get('tier'), 'reason': r['reason'],
                      'n_seasons': r.get('n_seasons'), 'n_weeks': r.get('n_weeks'),
                      'completeness_min': r.get('completeness_min')} for r in rejected[:16]],
        'SELECTED_ON': ('measured coverage, completeness and freshness inside the highest '
                        'available authority tier. NOT on filename, directory or mtime.'),
    }
    if win['_tier'] != PRIMARY:
        ev['DEGRADED_TO'] = win['_tier']
        ev['DEGRADED_NOTE'] = (
            f'no PRIMARY source was usable, so a {win["_tier"]} source is in use. Tier is '
            f'authority, not quality: a wider fallback does not become authoritative.')
        return Outcome.ok(f'SOURCE_SELECTED_DEGRADED_{dt.name.upper()}', ev,
                          f'{dt.name}: {win["path"]} at tier {win["_tier"]}', **{
                              'tier': win['_tier']})
    return Outcome.ok(f'SOURCE_SELECTED_{dt.name.upper()}', ev,
                      f'{dt.name}: {win["path"]}', tier=PRIMARY)


# --------------------------------------------------------------------------- the registry
def registry():
    """Every data type the warehouse consumes, with its ranked sources."""
    reg = {}

    sched = DataType(
        'schedules',
        required=('game_id', 'season', 'week', 'home_team', 'away_team'),
        season_field='season', week_field='week',
        note='team-game context: market, weather, rest, result')
    sched.add('nfl/vintage/schedules.*.csv.gz', PRIMARY, 'nflverse schedules capture')
    sched.add('nfl/research/postgame/schedules*.csv*', SECONDARY, 'postgame schedules')
    reg['schedules'] = sched

    pbp = DataType(
        'play_by_play',
        required=('game_id', 'season_type', 'week', 'posteam', 'play_type'),
        season_field=None, week_field='week',
        prefer=('tier', 'weeks', 'completeness', 'rows'),
        note='play level detail; one capture per season')
    pbp.add('nfl/research/postgame/pbp_{season}.*.csv.gz', PRIMARY, 'postgame pbp capture')
    pbp.add('nfl/vintage/pbp_{season}.*.csv.gz', SECONDARY, 'vintage pbp copy')
    reg['play_by_play'] = pbp

    ros = DataType(
        'weekly_rosters',
        required=('gsis_id', 'position', 'team'),
        season_field='season', week_field='week',
        note='identity and position by player-week')
    ros.add('nfl/vintage/weekly_rosters.*raw.csv.gz', PRIMARY, 'weekly roster capture')
    reg['weekly_rosters'] = ros

    dc = DataType(
        'depth_charts',
        required=('team', 'gsis_id', 'pos_abb', 'pos_rank'),
        season_field=None, week_field=None,
        prefer=('tier', 'completeness', 'rows'),
        note='declared depth position; NOT alignment')
    dc.add('nfl/vintage/depth_charts.*.raw.csv.gz', PRIMARY, 'depth chart capture')
    dc.add('nfl/vintage/depth_charts.*.reduced.csv.gz', FALLBACK, 'reduced depth chart')
    reg['depth_charts'] = dc
    return reg


def audit():
    """Run every selection and return the board. This is the GAP 8 artifact."""
    reg = registry()
    out = {}
    for name, dt in reg.items():
        if '{season}' in ''.join(c['pattern'] for c in dt.candidates):
            per = {}
            for s in range(2000, 2027):
                o = select(dt, season=s)
                per[s] = {'state': o.state.name, 'code': o.code,
                          'selected': (o.value or {}).get('selected') if o.value else None,
                          'n_weeks': (o.value or {}).get('n_weeks') if o.value else None,
                          'tier': (o.value or {}).get('selected_tier') if o.value else None,
                          'n_rejected': (o.value or {}).get('n_rejected') if o.value else None}
            out[name] = {'per_season': per,
                         'seasons_usable': sorted(s for s, v in per.items()
                                                  if v['state'] == 'PASS')}
        else:
            o = select(dt)
            out[name] = {'state': o.state.name, 'code': o.code,
                         'evidence': o.value if o.state.name == 'PASS' else None,
                         'detail': getattr(o, 'detail', None)}
    return out
