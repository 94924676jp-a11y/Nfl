"""Parse a DraftKings GameCenter contest-standings export.

A PARSER, NOT A SCRAPER. It is handed a file the owner downloaded. There is
no browser automation here, no session handling, no login, no retry against
draftkings.com. The priority is preserving data safely, not automating a
site, and an archive that depends on beating a bot check is not an archive.

WHAT THE FILE IS SHAPED LIKE, AND HOW SURE WE ARE

Practitioner reports describe a contest-standings CSV carrying an entry
table -- rank, entry id, entry name, time remaining, points, lineup -- with
a per-athlete summary table EMBEDDED to its right: athlete, roster position,
percent drafted, fantasy points. That is the same two-tables-in-one-file
shape DraftKings uses for its salary export, which this repository has
already read and verified first-hand in `dfs/classic/dk_identity.py`.

WE HAVE NOT READ A REAL GAMECENTER FILE. No such artifact exists in this
checkout. So the column names below are recorded at PRACTITIONER_REPORT
confidence, NOT VERIFIED_PRIMARY, and the parser is written to survive being
wrong about them: it finds each table by HEADER MATCH rather than by column
index, accepts any of several spellings, records the schema fingerprint of
what it actually saw, and REFUSES by name when it finds nothing rather than
returning an empty parse. The first real file either confirms the headers or
produces a named refusal naming the row it could not read -- and either
outcome is informative, which a silent empty result would not be.

FIELDS THE SOURCE DOES NOT SUPPLY STAY ABSENT. DraftKings athlete ids and
salaries are not assumed to be in this file. Where a column is missing the
value is None and the fingerprint says the column was not there.
"""
from __future__ import annotations

import csv
import io
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.history import contracts as C                           # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome         # noqa: E402

SPEC_VERSION = 'nfl-dfs-gamecenter-parser-0'

#: Header spellings accepted for the ENTRY table, lowercased. Several are
#: listed per concept because the exact casing and wording are at
#: PRACTITIONER_REPORT confidence, not verified here.
ENTRY_COLUMNS: Dict[str, Tuple[str, ...]] = {
    'rank': ('rank',),
    'entry_id': ('entryid', 'entry id'),
    'entry_name': ('entryname', 'entry name'),
    'time_remaining': ('timeremaining', 'time remaining'),
    'points': ('points', 'fpts'),
    'lineup': ('lineup',),
}
#: ... and for the embedded ATHLETE summary table.
ATHLETE_COLUMNS: Dict[str, Tuple[str, ...]] = {
    'athlete_name': ('player', 'name'),
    'roster_position': ('roster position', 'rosterposition'),
    'percent_drafted': ('%drafted', '% drafted', 'drafted%', 'draft%',
                        'ownership'),
    'fantasy_points': ('fpts', 'fantasy points', 'points'),
    'athlete_id': ('player id', 'playerid', 'id'),
}

#: A lineup cell looks like "QB Josh Allen RB James Cook RB ...". The slot
#: tokens are the DK Classic and Showdown roster positions.
SLOT_TOKENS = ('QB', 'RB', 'WR', 'TE', 'FLEX', 'DST', 'CPT', 'UTIL')
_SLOT_RE = re.compile(r'\b(' + '|'.join(SLOT_TOKENS) + r')\b')


def _norm(s: str) -> str:
    return (s or '').strip().lower().replace('_', ' ')


def _match(cells: Sequence[str], spec: Dict[str, Tuple[str, ...]],
           required: Sequence[str]) -> Optional[Dict[str, int]]:
    """Column index per concept, or None if the required ones are absent."""
    found: Dict[str, int] = {}
    for i, c in enumerate(cells):
        n = _norm(c)
        for concept, spellings in spec.items():
            if concept in found:
                continue
            if n in spellings or n.replace(' ', '') in spellings:
                found[concept] = i
    if any(r not in found for r in required):
        return None
    return found


def _f(v) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace('%', '').replace(',', '')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _i(v) -> Optional[int]:
    f = _f(v)
    return None if f is None else int(f)


def parse_lineup(cell: str) -> Tuple[Tuple[str, str], ...]:
    """(slot, athlete) pairs out of a DK lineup string.

    Returns EMPTY when no slot token is present. An unparsed lineup is a
    stated fact -- `ContestEntry.parsed` is False -- and never a guess at
    what the entrant rostered.
    """
    s = (cell or '').strip()
    if not s:
        return ()
    hits = list(_SLOT_RE.finditer(s))
    if not hits:
        return ()
    out: List[Tuple[str, str]] = []
    for k, m in enumerate(hits):
        end = hits[k + 1].start() if k + 1 < len(hits) else len(s)
        name = s[m.end():end].strip()
        if name:
            out.append((m.group(1), name))
    return tuple(out)


def schema_fingerprint(header_cells: Sequence[str]) -> str:
    """What columns were actually seen, in order, lowercased.

    Stored with the artifact so that a later parser change can be told apart
    from a later FILE change.
    """
    return '|'.join(_norm(c) for c in header_cells)


def parse(raw: bytes, *, contest: C.DFSContestIdentity = None,
          snapshot_type: str = C.SNAPSHOT_UNKNOWN,
          raw_sha256: str = None) -> Outcome:
    """Entries and, where the file carries one, the athlete summary table."""
    if not raw:
        return Outcome.blocked(
            'GAMECENTER_FILE_EMPTY',
            'the file has no bytes. An empty parse is not a contest with no '
            'entrants.', cause=Cause.DATA)
    text = raw.decode('utf-8-sig', errors='replace')
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return Outcome.blocked(
            'GAMECENTER_FILE_UNREADABLE',
            'no CSV row could be read from the file.', cause=Cause.DATA)

    entry_cols = athlete_cols = None
    entry_header: List[str] = []
    athlete_header: List[str] = []
    entries: List[C.ContestEntry] = []
    athletes: List[C.ContestAthleteSummary] = []
    unparsed_lineups = 0

    for cells in rows:
        if entry_cols is None:
            m = _match(cells, ENTRY_COLUMNS, ('entry_id', 'lineup'))
            if m is not None:
                entry_cols, entry_header = m, list(cells)
                # the athlete table may share this header row
                rest = cells[max(m.values()) + 1:]
                off = max(m.values()) + 1
                a = _match(rest, ATHLETE_COLUMNS, ('athlete_name',))
                if a is not None:
                    athlete_cols = {k: v + off for k, v in a.items()}
                    athlete_header = list(rest)
                continue
        if athlete_cols is None:
            a = _match(cells, ATHLETE_COLUMNS, ('athlete_name',))
            if a is not None and entry_cols is not None and \
                    min(a.values()) > max(entry_cols.values()):
                athlete_cols, athlete_header = a, list(cells)
                continue
        if entry_cols is not None:
            def g(concept):
                i = entry_cols.get(concept)
                return cells[i] if i is not None and i < len(cells) else None
            eid, lu = g('entry_id'), g('lineup')
            if (eid or '').strip() or (lu or '').strip():
                slots = parse_lineup(lu or '')
                if (lu or '').strip() and not slots:
                    unparsed_lineups += 1
                entries.append(C.ContestEntry(
                    entry_id=(eid or '').strip() or None,
                    entry_name=(g('entry_name') or '').strip() or None,
                    rank=_i(g('rank')), points=_f(g('points')),
                    lineup_raw=(lu or '').strip() or None,
                    lineup_slots=slots,
                    time_remaining=(g('time_remaining') or '').strip() or None,
                    snapshot_type=snapshot_type, raw_sha256=raw_sha256))
        if athlete_cols is not None:
            def h(concept):
                i = athlete_cols.get(concept)
                return cells[i] if i is not None and i < len(cells) else None
            nm = (h('athlete_name') or '').strip()
            if nm and _norm(nm) not in ATHLETE_COLUMNS['athlete_name']:
                athletes.append(C.ContestAthleteSummary(
                    athlete_name=nm,
                    roster_position=(h('roster_position') or '').strip()
                    or None,
                    percent_drafted=_f(h('percent_drafted')),
                    fantasy_points=_f(h('fantasy_points')),
                    athlete_id=(h('athlete_id') or '').strip() or None,
                    raw_sha256=raw_sha256))

    if entry_cols is None:
        return Outcome.fail(
            'GAMECENTER_ENTRY_TABLE_NOT_FOUND',
            f'no row matched an entry-table header. Required columns are an '
            f'entry id and a lineup, under any of {ENTRY_COLUMNS["entry_id"]} '
            f'and {ENTRY_COLUMNS["lineup"]}. The first row read was '
            f'{rows[0][:8]}. This is a REFUSAL rather than an empty parse '
            f'because the column names here are at PRACTITIONER_REPORT '
            f'confidence and being wrong about them must be visible.',
            value={'first_row': rows[0][:12], 'n_rows': len(rows)})
    if not entries:
        return Outcome.fail(
            'GAMECENTER_NO_ENTRIES',
            f'the entry table header was found and carries no entrant rows. '
            f'A contest with no entrants is not a contest.',
            value={'header': entry_header})

    return Outcome.ok(
        'GAMECENTER_PARSED',
        {'entries': entries, 'athletes': athletes,
         'n_entries': len(entries), 'n_athletes': len(athletes),
         'entry_columns_found': sorted(entry_cols),
         'athlete_columns_found': (sorted(athlete_cols) if athlete_cols
                                   else []),
         'athlete_table_present': athlete_cols is not None,
         'columns_absent': sorted(
             set(ENTRY_COLUMNS) - set(entry_cols or {})),
         'athlete_columns_absent': sorted(
             set(ATHLETE_COLUMNS) - set(athlete_cols or {})),
         'schema_fingerprint': schema_fingerprint(
             list(entry_header) + list(athlete_header)),
         'n_lineups_unparsed': unparsed_lineups,
         'parser_version': SPEC_VERSION,
         'header_confidence': C.PRACTITIONER_REPORT,
         'header_confidence_why':
             'no real GameCenter export exists in this checkout, so the '
             'accepted column spellings are reported, not verified. The '
             'parser matches headers rather than positions so that a wrong '
             'guess refuses by name instead of mis-reading.'},
        detail=f'{len(entries)} entry row(s), {len(athletes)} athlete '
               f'summary row(s), {unparsed_lineups} lineup(s) unparsed')
