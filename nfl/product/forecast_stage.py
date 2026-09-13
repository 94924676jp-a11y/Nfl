"""The two-stage pregame forecast product: PRE_INACTIVES and POST_INACTIVES_FINAL.

WHY TWO STAGES AND NOT ONE GATE.

Until now the market comparator refused any board that was not post-inactives.
That is correct about evidence and wrong about product: it means no projection
exists at all until roughly ninety minutes before kickoff, even though roster
membership, the depth chart, the injury report, historical workload and the
team environment are all legitimately known hours earlier. The absence of the
official list is a reason to be UNCERTAIN about availability. It is not a
reason to have no forecast.

So availability is represented rather than assumed:

  * STAGE 1, PRE_INACTIVES, is sealed from what is known at `written_at`.
    Nobody is asserted ACTIVE. A player whose availability is unknown is
    carried with whatever uncertainty the accepted layers already express, and
    a metric the evidence cannot support is refused BY NAME rather than
    guessed.
  * STAGE 2, POST_INACTIVES_FINAL, is sealed after the authoritative list is
    ingested, with explicitly inactive players resolved.

THE FIRST STAGE IS NEVER REWRITTEN. Stage 2 is a NEW artifact beside stage 1,
not a replacement of it: its own run_id, its own written_at, its own evidence
hashes. Every earlier forecast keeps the clocks it was sealed with, because a
restamped forecast cannot be scored and a forecast that cannot be scored cannot
tell us what the official list was worth. Measuring that -- the information
value of the inactives themselves -- is the reason both stages are kept.

OMISSION IS NEVER ACTIVE, AT EITHER STAGE. Stage 1 has no list, so it asserts
nothing about who is out. Stage 2 has a list of players who ARE out, and a
player absent from that list is simply not named by it.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'forecast-stage/1.0.0'

PRE = 'PRE_INACTIVES'
POST = 'POST_INACTIVES_FINAL'
STAGES = (PRE, POST)

# The directory prefix each stage seals under. The vocabulary is closed: a
# directory that matches neither is UNKNOWN and is refused, never defaulted to
# the permissive stage.
DIR_PREFIX = {'pre_inactives': PRE, 'post_inactives': POST}

STAGE_MEANING = {
    PRE: 'sealed before the authoritative inactive list existed. Availability '
         'is unresolved: no player is asserted active, and none is asserted '
         'inactive either.',
    POST: 'sealed after the authoritative list was ingested and explicitly '
          'inactive players were resolved. Omission from the list remains a '
          'non-claim, not a promotion to active.',
}


def stage_of_dirname(name) -> str | None:
    """PRE, POST, or None. Longest prefix wins so 'post_' never reads as 'pre_'."""
    n = str(name or '')
    for pre in sorted(DIR_PREFIX, key=len, reverse=True):
        if n.startswith(pre):
            return DIR_PREFIX[pre]
    return None


def resolve_stage(cfg_dir) -> Outcome:
    """The stage a sealed board directory belongs to, or a named refusal."""
    name = pathlib.Path(cfg_dir).name
    st = stage_of_dirname(name)
    if st is None:
        return Outcome.blocked(
            'FORECAST_STAGE_UNKNOWN',
            f'{name!r} matches neither {sorted(DIR_PREFIX)}. A board whose '
            f'stage cannot be named cannot be labelled, and an unlabelled '
            f'projection must never be presented beside a labelled one.',
            cause=Cause.GOVERNANCE)
    return Outcome.ok('FORECAST_STAGE_RESOLVED', value=st, stage=st,
                      meaning=STAGE_MEANING[st], directory=name,
                      spec_version=SPEC_VERSION)


# --------------------------------------------------------- QB admissibility
#
# Two DIFFERENT reasons a quarterback metric may be inadmissible, deliberately
# kept apart because they are not the same claim and do not clear together.
QB_AVAILABILITY_UNRESOLVED = 'QB_AVAILABILITY_UNRESOLVED_PRE_INACTIVES'
QB_WEEK1_BOUNDARY = 'QB3_WEEK1_SEASON_BOUNDARY'
QB_OWNERSHIP_NOT_ENFORCED = 'QB_INACTIVE_OWNERSHIP_NOT_ENFORCED'


def _derived_week1_blocker(board):
    """The season-boundary condition for a board that does not record it.

    Returns the blocker id, or None when the rooms are demonstrably NOT
    season-opener rooms. Any failure to establish that returns the blocker:
    an unanswerable question about contamination is answered conservatively.
    """
    gid = str((board or {}).get('game_id') or '')
    parts = gid.split('_')
    if len(parts) < 2:
        return QB_WEEK1_BOUNDARY
    try:
        season, week = int(parts[0]), int(parts[1])
    except ValueError:
        return QB_WEEK1_BOUNDARY
    try:
        from nfl.production.nonqb import qb_allocation as QA
        detail = QA.previous_primary_detail(season, week)
    except Exception:
        return QB_WEEK1_BOUNDARY
    teams = list((board or {}).get('teams') or ())
    if not teams:
        return QB_WEEK1_BOUNDARY
    flags = [(detail.get(t) or {}).get('is_season_opener') for t in teams]
    if any(f is None for f in flags):
        return QB_WEEK1_BOUNDARY
    return QB_WEEK1_BOUNDARY if any(flags) else None


def qb_metric_blockers(board, stage) -> list:
    """Named reasons a `qb/` metric is inadmissible on this board.

    NOT INTERCHANGEABLE WITH ONE ANOTHER:

      * QB_AVAILABILITY_UNRESOLVED_PRE_INACTIVES is a STAGE fact. It says the
        official list did not exist when this was sealed. It clears at stage 2
        and says nothing about model quality.
      * QB3_WEEK1_SEASON_BOUNDARY is a SPECIFICATION fact. The room crossed a
        season boundary, so the incumbent signal is the prior season's final
        game -- a rested or replaced quarterback can dilute the current QB1.
        It does NOT clear at stage 2, because ingesting an inactive list does
        not repair a cell definition.
      * QB_INACTIVE_OWNERSHIP_NOT_ENFORCED is an ENFORCEMENT fact: a
        post-inactives board that did not consume the list it should have.

    Collapsing them would let the wrong one clear the other, which is how a
    contaminated quarterback projection reaches a card.
    """
    out = []
    if stage == PRE:
        out.append(QB_AVAILABILITY_UNRESOLVED)
    cfg = (board or {}).get('qb3_configuration') or {}
    if cfg:
        if any((v or {}).get('week1_specification_defect')
               for v in cfg.values()):
            out.append(QB_WEEK1_BOUNDARY)
    else:
        # AN ABSENT FIELD IS NOT A CLEARED ONE, AND THIS FAILS CLOSED.
        #
        # `qb3_configuration` was added to the board on 2026-09-13 at ~21:20Z.
        # Every board sealed before that -- the whole 1 PM and 4:25 slates --
        # lacks it, and reading it as "no defect recorded" let all 14 QB
        # markets of the 4:25 slate through the comparator unrefused. The
        # DAL_NYG refusal worked only because that board had been rebuilt.
        # When the board cannot answer, the condition is recomputed from the
        # same governed source the allocation uses; if even that cannot be
        # reached, the boundary blocker is applied rather than skipped.
        out.append(_derived_week1_blocker(board))
        out = [x for x in out if x]
    if stage == POST and not (board or {}).get(
            'qb_inactive_ownership_enforced'):
        out.append(QB_OWNERSHIP_NOT_ENFORCED)
    return out


def qb_blocker_detail(board, stage) -> str:
    cfg = (board or {}).get('qb3_configuration') or {}
    parts = []
    for team, v in sorted(cfg.items()):
        v = v or {}
        parts.append(f'{team}={v.get("configuration")}'
                     f'{" (season opener)" if v.get("is_season_opener") else ""}')
    return '; '.join(parts) or 'no qb3_configuration recorded on this board'
