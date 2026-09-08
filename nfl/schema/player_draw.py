"""Canonical per-player-game draw schema. Sport-level, scoring-system-free.

WHY THIS EXISTS AS A SCHEMA AND NOT A CONVENTION

Every downstream consumer -- the joint simulator, the accounting invariants, the
prospective forecast artifact, the fantasy scoring engine -- needs the same
answer to "what is a draw". A convention drifts silently between modules; a
schema fails loudly.

TWO RULES THAT ARE STRUCTURAL, NOT STYLISTIC

1. FANTASY SCORING IS NOT A MODELLED QUANTITY. This schema carries football
   statistics only. Fantasy points are computed FROM a completed draw by
   nfl/scoring, never stored here and never fed back upstream. A model that
   optimises a scoring system has stopped modelling football.

2. EVERY DRAW IS TRACEABLE. A draw with no provenance is not evidence about
   anything, so the fields below are required and validation refuses a draw set
   that omits any of them.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SCHEMA_VERSION = 'nfl-player-draw-1'

# Per position, the statistics a complete draw must carry.
QB_FIELDS = ('dropbacks', 'attempts', 'completions', 'sacks', 'pass_yards',
             'pass_td', 'interceptions', 'designed_rushes', 'scrambles',
             'rush_yards', 'rush_td')
RB_FIELDS = ('appeared', 'pass_snaps', 'carries', 'rush_yards', 'rush_td',
             'targets', 'receptions', 'rec_yards', 'rec_td')
WR_TE_FIELDS = ('appeared', 'pass_snaps', 'targets', 'receptions', 'rec_yards',
                'rec_td')
BY_POSITION = {'QB': QB_FIELDS, 'RB': RB_FIELDS,
               'WR': WR_TE_FIELDS, 'TE': WR_TE_FIELDS}

# Provenance every draw set must carry. Absent any one of these the draw cannot
# be traced back to what produced it, and an untraceable draw is not evidence.
REQUIRED_TRACE = ('execution_id', 'model_arm', 'spec_hash', 'code_commit',
                  'input_capture_hashes', 'written_at', 'game_id', 'player_id',
                  'seed', 'schema_version')

VALID_ARMS = ('A', 'B', 'C')

# Statistics that may never be negative.
NON_NEGATIVE = set(QB_FIELDS) | set(RB_FIELDS) | set(WR_TE_FIELDS)
NON_NEGATIVE -= {'pass_yards', 'rush_yards', 'rec_yards'}   # can be negative

# Within-draw orderings that must hold on EVERY draw index, not on the mean.
ORDERINGS = (
    ('completions', 'attempts'),
    ('receptions', 'targets'),
    ('attempts', 'dropbacks'),
    ('pass_td', 'completions'),
    ('rec_td', 'receptions'),
)


@dataclasses.dataclass(frozen=True)
class DrawSet:
    """One player-game's draws. `stats` maps field -> array of length n_draws."""
    player_id: str
    position: str
    game_id: str
    n_draws: int
    stats: dict
    trace: dict

    def as_dict(self) -> dict:
        return {'player_id': self.player_id, 'position': self.position,
                'game_id': self.game_id, 'n_draws': self.n_draws,
                'fields': sorted(self.stats), 'trace': dict(self.trace)}


def validate(ds: DrawSet) -> Outcome:
    """Refuse anything that is not a complete, traceable, coherent draw set."""
    import numpy as np

    need = BY_POSITION.get(ds.position)
    if need is None:
        return Outcome.blocked(
            'UNKNOWN_POSITION',
            f'{ds.position!r} has no declared draw schema. An undeclared '
            f'position is undeclared, not clean.', cause=Cause.GOVERNANCE,
            position=ds.position)

    missing = [f for f in need if f not in ds.stats]
    if missing:
        return Outcome.fail(
            'DRAW_FIELDS_MISSING',
            f'{ds.position} {ds.player_id}: missing {missing}. A partial draw '
            f'is not a draw -- downstream would read the absence as zero.',
            missing=missing)

    mt = [f for f in REQUIRED_TRACE if not ds.trace.get(f)]
    if mt:
        return Outcome.fail(
            'DRAW_TRACE_INCOMPLETE',
            f'{ds.player_id}: trace is missing {mt}. A draw that cannot be '
            f'traced to the execution, spec and inputs that produced it is not '
            f'evidence about anything.', missing=mt)

    if ds.trace.get('model_arm') not in VALID_ARMS:
        return Outcome.fail(
            'UNKNOWN_MODEL_ARM',
            f'model_arm {ds.trace.get("model_arm")!r} is not one of '
            f'{VALID_ARMS}. Arms carry different evidentiary status and may '
            f'never be pooled, so an unlabelled draw cannot be scored.')

    if ds.trace.get('schema_version') != SCHEMA_VERSION:
        return Outcome.fail(
            'SCHEMA_VERSION_MISMATCH',
            f'draw declares {ds.trace.get("schema_version")!r}, this code is '
            f'{SCHEMA_VERSION!r}.')

    for f in need:
        a = np.asarray(ds.stats[f])
        if a.shape[0] != ds.n_draws:
            return Outcome.fail(
                'DRAW_LENGTH_MISMATCH',
                f'{f} has {a.shape[0]} draws, expected {ds.n_draws}. Ragged '
                f'draws break the joint identity: draw i of one field would '
                f'not be draw i of another.', field=f)
        if f in NON_NEGATIVE and (a < 0).any():
            return Outcome.fail(
                'NEGATIVE_COUNT',
                f'{f} carries {int((a < 0).sum())} negative value(s).', field=f)

    for lo, hi in ORDERINGS:
        if lo in ds.stats and hi in ds.stats:
            a, b = np.asarray(ds.stats[lo]), np.asarray(ds.stats[hi])
            bad = int((a > b).sum())
            if bad:
                return Outcome.fail(
                    'DRAW_ORDERING_VIOLATED',
                    f'{lo} exceeds {hi} on {bad} of {ds.n_draws} draws. '
                    f'Checked PER DRAW, not on the mean: a mean-level check '
                    f'passes while individual draws are impossible.',
                    lo=lo, hi=hi, n_bad=bad)

    if 'fantasy_points' in ds.stats or 'fantasy' in ds.stats:
        return Outcome.fail(
            'FANTASY_IN_FOOTBALL_SCHEMA',
            'a fantasy score was stored in the football draw schema. Scoring '
            'is computed FROM a draw and must never become a modelled '
            'quantity, or the model starts optimising a scoring system rather '
            'than football.')

    return Outcome.ok('DRAW_SET_VALID', value=ds.as_dict(),
                      detail=f'{ds.position} {ds.player_id}: {ds.n_draws} '
                             f'draws, {len(need)} fields, trace complete')
