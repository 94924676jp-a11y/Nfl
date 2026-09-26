"""Realised Week-N player outcomes, loaded once and refused when thin.

WHAT THIS IS AND IS NOT

It is a READER of a preserved snapshot. It fetches nothing at grading time:
the bytes were retrieved once, written to `nfl/research/postgame/raw/` with
their sha256, and set read-only. Regrading therefore reads the same bytes
that produced the first grade, which is the only way a grade is auditable.

THE FAILURE THIS GUARDS AGAINST

The recurring defect in this project is a step that returned nothing, or
something partial, being read as success. A weekly stats file that is present
but covers three of eight games is EXACTLY that shape: the join succeeds, the
report prints, and the missing games look like players who did nothing. So
this module states which game_ids the snapshot actually contains, and a
caller that wants a game it does not contain is refused by name rather than
silently graded against absence.

RESULTS ARE NEVER PREDICTIVE INPUTS. Nothing here is imported by the
production forecast path, and nothing here may be. A realised outcome used to
forecast its own game is the leak this project exists to prevent.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

RAW = _REPO / 'nfl' / 'research' / 'postgame' / 'raw'
#: The preserved weekly player snapshot and the bytes it must still be.
WEEKLY = ('nflverse_stats_player_week_2026_retrieved_2026-09-20T2221Z.csv',
          '9f03279558503bf8aef46b1d3ff5398458da262c86f1a671222575b3301d7736')
SNAPS = ('nflverse_snap_counts_2026_retrieved_2026-09-20T2221Z.csv',
         '271167b454534d6e868c20f7768654a0fa7a7a1cc28c0ae32325678ee138a967')

#: Every realised quantity the grader is allowed to read, named here so a
#: renamed upstream column is a refusal instead of a column of zeros.
NUMERIC = ('completions', 'attempts', 'passing_yards', 'passing_tds',
           'passing_interceptions', 'carries', 'rushing_yards', 'rushing_tds',
           'receptions', 'targets', 'receiving_yards', 'receiving_tds',
           'rushing_fumbles_lost', 'receiving_fumbles_lost',
           'sack_fumbles_lost', 'fantasy_points_ppr', 'fg_made', 'fg_att')


def _sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load_weekly(season: int, week: int) -> Outcome:
    """Realised rows for one week, keyed by gsis_id.

    The key is `player_id`, which IS the gsis_id in this feed, so the join to
    our projections needs no name matching. No edit-distance matching is
    performed anywhere in this pipeline.
    """
    name, want = WEEKLY
    p = RAW / name
    if not p.exists():
        return Outcome.blocked('ACTUALS_SNAPSHOT_MISSING',
                               f'{p} is absent; grading cannot proceed from '
                               f'a file that is not there', cause=Cause.DATA)
    got = _sha256(p)
    if got != want:
        return Outcome.blocked(
            'ACTUALS_SNAPSHOT_BYTES_CHANGED',
            f'{name} hashes {got[:16]} but the pipeline was built against '
            f'{want[:16]}. A grade computed on different bytes is not the '
            f'same grade.', cause=Cause.DATA)
    rows = list(csv.DictReader(open(p, newline='')))
    if not rows:
        return Outcome.blocked('ACTUALS_SNAPSHOT_EMPTY',
                               f'{name} parsed to zero rows', cause=Cause.DATA)
    missing = [c for c in NUMERIC + ('player_id', 'game_id', 'position')
               if c not in rows[0]]
    if missing:
        return Outcome.blocked(
            'ACTUALS_SCHEMA_MISMATCH',
            f'{name} lacks {missing}. Reading a renamed column as absent '
            f'would grade every player at zero.', cause=Cause.DATA)
    sel = [r for r in rows
           if r['season'] == str(season) and r['week'] == str(week)]
    if not sel:
        return Outcome.blocked(
            'ACTUALS_WEEK_NOT_PRESENT',
            f'{name} contains no rows for {season} week {week}',
            cause=Cause.DATA)
    # A BLANK CELL IS MISSING. IT IS NOT A ZERO.
    #
    # This loop used to coerce None/''/'NA' straight to 0.0, which is the
    # repo-wide invariant inverted in the one place it costs most: these ARE
    # the actuals, so a blank cell became a realised zero and grading scored a
    # projection against it as though the player had genuinely recorded
    # nothing. The schema guard above already names this risk for a whole
    # COLUMN ('reading a renamed column as absent would grade every player at
    # zero'); the same argument applies cell by cell.
    #
    # MEASURED on the pinned snapshot 2026-09-20T2221Z: 0 blank or NA cells
    # across 1,674 rows and all 18 numeric columns, so refusing here changes
    # nothing today. It is worth having anyway because the snapshot is
    # REPLACED each week: the hash pin refuses a file that changed underneath
    # us, but it cannot object to the new file a human deliberately pins, and
    # that is exactly when a feed with blanks would arrive unannounced.
    blanks = {}
    for r in sel:
        for c in NUMERIC:
            if r.get(c) in (None, '', 'NA'):
                blanks[c] = blanks.get(c, 0) + 1
    if blanks:
        return Outcome.blocked(
            'ACTUALS_NUMERIC_CELL_BLANK',
            f'{sum(blanks.values())} blank or NA numeric cell(s) across '
            f'{len(blanks)} column(s) in {name} for {season} week {week}: '
            f'{dict(sorted(blanks.items()))}. These were previously read as '
            f'0.0, which grades a player as having recorded nothing when the '
            f'feed simply did not say. Declare the rule for these cells or '
            f'fix the feed; no value is invented here.',
            cause=Cause.DATA, blank_cells_by_column=dict(sorted(blanks.items())))
    by_id = {}
    for r in sel:
        for c in NUMERIC:
            r[c] = float(r[c])
        by_id[r['player_id']] = r
    games = sorted({r['game_id'] for r in sel})
    return Outcome.ok('ACTUALS_LOADED', value=by_id,
                      games_present=games, n_rows=len(sel),
                      blank_numeric_cells=0,
                      blank_numeric_cells_note=(
                          'checked, not assumed: every numeric cell in every '
                          'selected row carried a value, so no zero in this '
                          'result came from an absent one'),
                      snapshot=name, snapshot_sha256=got)


def dk_points_actual(r: dict) -> float:
    """Actual DK points from realised components.

    IT USES THE SAME SCORER THE PROJECTION USED. Re-deriving DK points with a
    second hand-written formula would make every projected-vs-actual gap a
    mixture of football error and two scoring functions disagreeing.
    """
    from nfl.product import dk_scoring as DKS
    fl = (r['rushing_fumbles_lost'] + r['receiving_fumbles_lost']
          + r['sack_fumbles_lost'])
    v = DKS.skill_points(
        1, pass_yds=[r['passing_yards']], pass_td=[r['passing_tds']],
        ints=[r['passing_interceptions']], rush_yds=[r['rushing_yards']],
        rush_td=[r['rushing_tds']], rec=[r['receptions']],
        rec_yds=[r['receiving_yards']], rec_td=[r['receiving_tds']],
        fumbles_lost=[fl])
    return round(float(v[0]), 2)
