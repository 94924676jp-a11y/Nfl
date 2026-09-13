"""WHICH sealed board a reader means, when a game has several.

MEASURED 2026-09-13, ON THE FIRST REAL PRODUCTION SLATE.

A game accumulates one sealed run directory per forecast. By Sunday morning
ATL_PIT held three. Three separate readers -- the slate assessor, the research
board export and the product board -- each selected one with

    list(board_dir.glob('**/board.json'))[0]

which is filesystem order, not chronology. So after fresh injury evidence was
ingested and every one of the day's twelve games was re-forecast, the slate
still reported DEFERRED_INJURY_REPORT_INCOMPLETE on five layers that had just
executed and passed, and the exported CSV still carried
`forecast_written_at 2026-09-11T15:41:57Z`. Nothing was wrong with the
forecasts. Everything was wrong with which forecast was being read.

That is this project's standing defect class in its purest form: something
partial or stale returned without complaint, and read as the answer. The fix
is not a sort order tucked into three places -- it is one function that says
out loud which artifact is meant and records how it chose.

THE RULE. A caller that knows the directory it just sealed passes it and gets
it back. Otherwise the newest `run_status.written_at` wins. Filesystem order
is never a tiebreak, and mtime is used only when no board in the directory
carries a clock at all -- which is itself reported rather than assumed away.
"""
from __future__ import annotations

import json
import pathlib

SELECTED_BY = ('SEALED_BY_THIS_RUN', 'NEWEST_WRITTEN_AT', 'NEWEST_MTIME')


def board_written_at(run_dir) -> str | None:
    """The clock the board in this directory was sealed at, or None."""
    rs = pathlib.Path(run_dir) / 'run_status.json'
    if not rs.exists():
        return None
    try:
        return json.load(open(rs)).get('written_at')
    except (ValueError, OSError):
        return None


def newest_board_dir(board_dir, sealed=None):
    """(run directory, how it was chosen), or (None, None) if there is none.

    `sealed` is the directory the caller itself just wrote. It wins outright:
    a reader that knows the answer should not go looking for it.
    """
    if sealed:
        sd = pathlib.Path(sealed)
        if (sd / 'board.json').exists():
            return sd, 'SEALED_BY_THIS_RUN'
    board_dir = pathlib.Path(board_dir)
    cands = [bj.parent for bj in board_dir.glob('**/board.json')]
    if not cands:
        return None, None
    dated = [(w, str(bd)) for bd in cands if (w := board_written_at(bd))]
    if dated:
        return pathlib.Path(max(dated)[1]), 'NEWEST_WRITTEN_AT'
    return (max(cands, key=lambda b: b.stat().st_mtime), 'NEWEST_MTIME')
