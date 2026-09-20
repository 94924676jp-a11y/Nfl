"""The DraftKings Showdown player universe, read out of the owner's entry file.

WHAT THIS FILE IS FOR AND WHAT IT MUST NEVER DO

It supplies IDENTITY and SALARY for the downstream Showdown section. Neither
is a football input. Nothing in this module is imported by the forecast path
and nothing it returns may reach a projection, a role, a team volume or a
touchdown probability. Salary exists here so a downstream optimiser can price
a lineup, and for no other reason.

THE SECOND FILE IS CONTEXT ONLY, AND THAT IS ENFORCED BY NOT PARSING IT.

The owner also supplied a third-party sheet carrying `VegasPts`, `FC Proj`,
`My Proj`, `Floor`, `Ceiling`, `Def v Pos` and an exposure column. Those are
exactly the fields that must not flow backwards into the model. The safest
handling is not a rule about ignoring them but a refusal to read them at all,
so this module parses the DK entry file and never opens the other one. The
sheet is preserved read-only as evidence under a name that says CONTEXT_ONLY.

NO EDIT-DISTANCE MATCHING. A DK name resolves to a gsis_id by exact
normalised match within the club, or it does not resolve and is reported by
name. A fuzzy match that silently attaches the wrong player to a salary is
worse than an unresolved row a human can see.
"""
from __future__ import annotations

import csv
import gzip
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

ENTRIES = ('nfl/dfs/salaries/raw/DKEntries_IND_KC_SHOWDOWN_2026W2.csv',
           '54601675c68c2b725871d11374e9ec9aad24739dc462c170a1e976d0ccda05'
           '23')
ROSTER = 'nfl/vintage/weekly_rosters.73f1d36a204ec591.raw.csv.gz'
_SUFFIX = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b')


def _norm(s: str) -> str:
    s = (s or '').lower().replace('.', '').replace("'", '').replace('-', ' ')
    s = _SUFFIX.sub('', s)
    return ' '.join(s.split())


def read_universe() -> Outcome:
    """Every CPT and FLEX row DraftKings offers for this Showdown."""
    p = _REPO / ENTRIES[0]
    if not p.exists():
        return Outcome.blocked('DK_ENTRY_FILE_MISSING', str(p),
                               cause=Cause.DATA)
    rows = list(csv.reader(open(p, newline='')))
    # The player table is embedded to the RIGHT of the entry columns. Find
    # its header by content rather than by a remembered column index, so a
    # different export width does not silently shift every field.
    hdr_i = hdr_j = None
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            if c.strip() == 'Position' and 'Name + ID' in r[j:j + 3]:
                hdr_i, hdr_j = i, j
                break
        if hdr_i is not None:
            break
    if hdr_i is None:
        return Outcome.blocked(
            'DK_PLAYER_TABLE_HEADER_NOT_FOUND',
            'no "Position,Name + ID,..." header in the entry file; the '
            'column layout was NOT guessed', cause=Cause.DATA)
    head = [c.strip() for c in rows[hdr_i][hdr_j:hdr_j + 9]]
    need = ['Position', 'Name + ID', 'Name', 'ID', 'Roster Position',
            'Salary', 'Game Info', 'TeamAbbrev', 'AvgPointsPerGame']
    if head != need:
        return Outcome.blocked('DK_PLAYER_TABLE_SCHEMA_MISMATCH',
                               f'got {head}', cause=Cause.DATA)
    out = []
    for r in rows[hdr_i + 1:]:
        cells = [c.strip() for c in r[hdr_j:hdr_j + 9]]
        if len(cells) < 9 or not cells[3]:
            continue
        out.append({'position': cells[0], 'name': cells[2], 'dk_id': cells[3],
                    'roster_position': cells[4],
                    'salary': int(cells[5]) if cells[5] else None,
                    'team': cells[7]})
    if not out:
        return Outcome.blocked('DK_PLAYER_TABLE_EMPTY',
                               'header found but zero player rows parsed',
                               cause=Cause.DATA)
    cpt = [r for r in out if r['roster_position'] == 'CPT']
    flex = [r for r in out if r['roster_position'] == 'FLEX']
    if not cpt or not flex:
        return Outcome.blocked(
            'DK_SHOWDOWN_SLOTS_INCOMPLETE',
            f'{len(cpt)} CPT and {len(flex)} FLEX rows; a Showdown needs '
            f'both', cause=Cause.DATA)
    return Outcome.ok('DK_UNIVERSE_READ', value=out, n_rows=len(out),
                      n_cpt=len(cpt), n_flex=len(flex),
                      teams=sorted({r['team'] for r in out}))


def resolve_identity(universe, season=2026, week=2) -> Outcome:
    """DK name+club -> gsis_id by EXACT normalised match. No fuzzy fallback."""
    ros = []
    with gzip.open(_REPO / ROSTER, 'rt') as f:
        for r in csv.DictReader(f):
            if r.get('season') == str(season) and r.get('week') == str(week):
                ros.append(r)
    idx = {}
    for r in ros:
        for nm in (r.get('full_name'), r.get('football_name')):
            if nm:
                idx.setdefault((r.get('team'), _norm(nm)), set()).add(
                    r['gsis_id'])
    resolved, unresolved, ambiguous = {}, [], []
    for u in universe:
        if u['position'] == 'DST':
            continue
        hit = idx.get((u['team'], _norm(u['name'])))
        if not hit:
            unresolved.append({'name': u['name'], 'team': u['team'],
                               'dk_id': u['dk_id'],
                               'why': 'no roster row on this club answers to '
                                      'this displayed name; no edit-distance '
                                      'fallback is permitted'})
        elif len(hit) > 1:
            ambiguous.append({'name': u['name'], 'team': u['team'],
                              'candidates': sorted(hit)})
        else:
            resolved[u['dk_id']] = next(iter(hit))
    return Outcome.ok('DK_IDENTITY_RESOLVED', value=resolved,
                      n_resolved=len(resolved),
                      n_unresolved=len(unresolved),
                      n_ambiguous=len(ambiguous),
                      unresolved=unresolved, ambiguous=ambiguous)
