"""DraftKings positions and player IDs, read from DK's own file.

TWO GAPS THIS CLOSES, BOTH FOUND BY LOOKING RATHER THAN ASSUMING

1. **The board cannot tell a pass-catching back from a receiver.** The board
   carries a modelled ROOM -- dropbacks, carries, targets -- and a back who
   catches passes sits in the targets room. DraftKings says he is an RB. Only
   DraftKings' own file is authoritative about what DraftKings will accept, so
   the position comes from there and from nowhere else.

2. **DST has no gsis_id at all.** Measured on the week-2 artifact: 32 of 33
   rows with no canonical id are defences. They are not modelled players, they
   have no dossier and they cannot come through the board. They enter the pool
   from this file, keyed on their DK id, and are marked as such.

THE FILE HAS TWO TABLES IN ONE CSV. The entry rows come first; the player
table is EMBEDDED to their right, beginning at a header cell reading
`Position`. Parsing only the first header is how a reader concludes the file
has no IDs in it -- which is exactly what happened before this module existed.

NO EDIT-DISTANCE MATCHING. Identity is by exact DK id. Where a gsis_id is
needed it comes from a supplied crosswalk, and a row that cannot be resolved
is COUNTED AND NAMED, never guessed.
"""
from __future__ import annotations

import collections
import csv
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome        # noqa: E402

SPEC_VERSION = 'dk-classic-identity-1'

#: The embedded player table's header, as DraftKings writes it.
PLAYER_HEADER = ('Position', 'Name + ID', 'Name', 'ID', 'Roster Position',
                 'Salary', 'Game Info', 'TeamAbbrev', 'AvgPointsPerGame')

DK_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'DST')

_ID_IN_NAME = re.compile(r'\((\d+)\)\s*$')


def parse_salary_file(path) -> Outcome:
    """Every DK player row: id, name, position, salary, team, game.

    Reads the EMBEDDED player table, wherever in the row it starts. A file
    whose player table cannot be found is a named refusal, because an empty
    parse here would silently produce a pool with no DK ids and an export
    that refuses much later for a reason that looks unrelated.
    """
    p = pathlib.Path(path)
    if not p.exists():
        return Outcome.blocked(
            'DK_SALARY_FILE_ABSENT',
            f'{p} does not exist. Without DraftKings\' own file there is no '
            f'authority on what position DraftKings will accept a player at.',
            cause=Cause.DATA)

    rows: List[Dict[str, Any]] = []
    start: Optional[int] = None
    with p.open(newline='', errors='ignore') as fh:
        for cells in csv.reader(fh):
            if start is None:
                for i, c in enumerate(cells):
                    if c.strip() == 'Position' and \
                            cells[i:i + len(PLAYER_HEADER)] == \
                            list(PLAYER_HEADER):
                        start = i
                        break
                continue
            seg = cells[start:start + len(PLAYER_HEADER)]
            if len(seg) < len(PLAYER_HEADER) or not seg[3].strip():
                continue
            pos = seg[0].strip().upper()
            roster_pos = seg[4].strip().upper()
            try:
                sal = int(float(seg[5]))
            except (TypeError, ValueError):
                continue
            rows.append({
                'dk_id': seg[3].strip(),
                'name': seg[2].strip(),
                'position': pos,
                'roster_position': roster_pos,
                'salary': sal,
                'game_info': seg[6].strip(),
                'team': seg[7].strip().upper(),
                'dk_avg_points': seg[8].strip(),
            })

    if start is None:
        return Outcome.fail(
            'DK_PLAYER_TABLE_NOT_FOUND',
            f'no embedded player table in {p.name}: no row carries the header '
            f'{PLAYER_HEADER[:4]}... The entry rows come first and the player '
            f'table sits to their right, so reading only the first header '
            f'finds no ids and wrongly concludes the file has none.',
            value={'file': str(p)})
    if not rows:
        return Outcome.fail(
            'DK_PLAYER_TABLE_EMPTY',
            f'the player table in {p.name} was found but carries no usable '
            f'rows. An empty parse read as "no players" is the failure mode '
            f'this project pays for most.',
            value={'file': str(p), 'header_at_column': start})

    by_pos = collections.Counter(r['position'] for r in rows)
    unknown = sorted({r['position'] for r in rows} - set(DK_POSITIONS))
    dups = [k for k, n in collections.Counter(
        r['dk_id'] for r in rows).items() if n > 1]
    return Outcome.ok(
        'DK_SALARY_FILE_PARSED',
        {'rows': rows, 'n_rows': len(rows),
         'by_position': dict(by_pos.most_common()),
         'positions_not_recognised': unknown,
         'duplicate_dk_ids': dups,
         'n_teams': len({r['team'] for r in rows}),
         'n_games': len({r['game_info'] for r in rows if r['game_info']}),
         'header_at_column': start,
         'source': str(p), 'spec_version': SPEC_VERSION},
        detail=f'{len(rows)} DK player(s) from {p.name}; {dict(by_pos)}; '
               f'{len({r["team"] for r in rows})} team(s)')


def crosswalk(parsed: Outcome, gsis_by_dk_id: Optional[Dict[str, str]] = None,
              gsis_by_name_team: Optional[Dict[Any, str]] = None) -> Outcome:
    """DK rows keyed to gsis_id, with every unresolved row named.

    Resolution is by DK id where a crosswalk gives one, else by EXACT
    (name, team). There is no fuzzy fallback: an unresolved row is reported,
    and for DST that is the expected state rather than a failure.
    """
    if parsed.state.name != 'PASS':
        return parsed
    rows = parsed.value['rows']
    by_id = dict(gsis_by_dk_id or {})
    by_nt = dict(gsis_by_name_team or {})

    positions: Dict[str, str] = {}
    ids: Dict[str, str] = {}
    salaries: Dict[str, int] = {}
    dst: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []

    for r in rows:
        if r['position'] == 'DST':
            dst.append(r)
            continue
        g = by_id.get(r['dk_id']) or by_nt.get((r['name'], r['team']))
        if not g:
            unresolved.append({'dk_id': r['dk_id'], 'name': r['name'],
                               'team': r['team'], 'position': r['position']})
            continue
        positions[g] = r['position']
        ids[g] = r['dk_id']
        salaries[g] = r['salary']

    return Outcome.ok(
        'DK_CROSSWALK_BUILT',
        {'dk_positions': positions, 'dk_ids': ids, 'salaries': salaries,
         'n_resolved': len(positions),
         'dst_rows': dst, 'n_dst': len(dst),
         'unresolved': unresolved[:60], 'n_unresolved': len(unresolved),
         'dst_note': 'defences carry no gsis_id and have no dossier; they '
                     'enter the pool from this file keyed on the DK id and '
                     'are never expected to resolve',
         'spec_version': SPEC_VERSION},
        detail=f'{len(positions)} of {len(rows) - len(dst)} non-DST row(s) '
               f'resolved; {len(dst)} DST; {len(unresolved)} unresolved')
