"""DraftKings Classic CSV export, preserving DK player IDs.

DK ACCEPTS IDS, NOT NAMES. A lineup exported by name is a lineup DraftKings
may reject or, worse, match to the wrong player. So a row without a `dk_id`
is a REFUSAL here, not a row written with a blank: an upload that silently
drops a player is the failure this file exists to prevent.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import sys
from typing import Any, Dict, List, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.classic import rules as R                              # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome        # noqa: E402

SPEC_VERSION = 'dk-nfl-classic-export-1'

#: DraftKings Classic upload header, in DK's own order.
HEADER = ('QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST')

#: Which slot each position fills, in order. The FLEX takes whichever of
#: RB/WR/TE is in surplus for that lineup's shape.
def _slot(players) -> List[Any]:
    by = {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'DST': []}
    for p in players:
        by[p['pos']].append(p)
    for k in by:
        by[k].sort(key=lambda x: -float(x.get('value') or 0))
    out = [by['QB'][0], by['RB'][0], by['RB'][1],
           by['WR'][0], by['WR'][1], by['WR'][2]]
    te = by['TE']
    out.append(te[0])
    flex = (by['RB'][2:] + by['WR'][3:] + te[1:])
    out.append(flex[0])
    out.append(by['DST'][0])
    return out


def write_csv(portfolio: Dict[str, Any], path) -> Outcome:
    """One row per lineup, DK IDs only, verified by re-reading the file."""
    lineups = portfolio.get('lineups') or []
    if not lineups:
        return Outcome.blocked(
            'NO_LINEUPS_TO_EXPORT',
            'the portfolio carries no lineups, so there is nothing to upload. '
            'Writing a header-only CSV would look like a successful export.',
            cause=Cause.DATA)

    missing = sorted({p['name'] for lu in lineups for p in lu['players']
                      if not p.get('dk_id')})
    if missing:
        return Outcome.fail(
            'DK_ID_MISSING',
            f'{len(missing)} player(s) have no DraftKings id: '
            f'{missing[:10]}. DraftKings matches on id, so exporting them by '
            f'name risks the wrong player or a rejected upload.',
            value={'missing': missing})

    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for lu in lineups:
        slotted = _slot(lu['players'])
        if len(slotted) != R.ROSTER_SIZE:
            return Outcome.fail(
                'EXPORT_SLOTTING_FAILED',
                f'a lineup slotted to {len(slotted)} of {R.ROSTER_SIZE} '
                f'positions; shape {lu.get("shape")}',
                value={'shape': lu.get('shape')})
        rows.append([x['dk_id'] for x in slotted])

    with p.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)

    back = list(csv.reader(p.open()))
    if len(back) != len(rows) + 1:
        return Outcome.fail(
            'EXPORT_ROW_COUNT_MISMATCH',
            f'{len(rows)} lineup(s) written but {len(back) - 1} read back '
            f'from {p}.', value={'written': len(rows), 'read': len(back) - 1})
    if any(len(r) != R.ROSTER_SIZE for r in back[1:]):
        return Outcome.fail(
            'EXPORT_WIDTH_MISMATCH',
            f'a CSV row is not {R.ROSTER_SIZE} columns wide',
            value={'widths': sorted({len(r) for r in back[1:]})})

    return Outcome.ok(
        'CLASSIC_CSV_WRITTEN',
        {'path': str(p), 'n_lineups': len(rows),
         'header': list(HEADER),
         'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
         'ids_only': True, 'spec_version': SPEC_VERSION},
        detail=f'{len(rows)} lineup(s) -> {p}, verified by re-read')
