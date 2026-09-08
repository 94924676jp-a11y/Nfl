"""Deterministic fantasy scoring. Pure infrastructure.

WHAT THIS IS: given a completed football-stat draw, compute a fantasy score
exactly, under a versioned scoring profile.

WHAT THIS IS NOT, and the separation is structural rather than a promise:

  * the football model does not import this module;
  * scoring constants are CONFIGURATION, never code;
  * a fantasy score may never be fed back upstream into a football prediction,
    and `nfl.schema.player_draw.validate` REFUSES a draw set that carries one.

This is not authorization to begin DFS research. No optimizer, no ownership, no
salary, no contest structure, no betting logic is present or implied.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from typing import Mapping

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402


@dataclasses.dataclass(frozen=True)
class ScoringProfile:
    """Every constant is data. Changing a rule is a config edit, not a patch."""
    name: str
    version: str
    per_pass_yard: float = 0.0
    per_pass_td: float = 0.0
    per_interception: float = 0.0
    per_rush_yard: float = 0.0
    per_rush_td: float = 0.0
    per_reception: float = 0.0
    per_rec_yard: float = 0.0
    per_rec_td: float = 0.0
    per_fumble_lost: float = 0.0
    bonus_100_rush_yards: float = 0.0
    bonus_100_rec_yards: float = 0.0
    bonus_300_pass_yards: float = 0.0


# Named for their shape, not asserted to be any operator's current rules --
# an operator may change scoring at any time and this file cannot know that.
DRAFTKINGS_STYLE = ScoringProfile(
    name='draftkings_style', version='1',
    per_pass_yard=0.04, per_pass_td=4.0, per_interception=-1.0,
    per_rush_yard=0.1, per_rush_td=6.0,
    per_reception=1.0, per_rec_yard=0.1, per_rec_td=6.0,
    per_fumble_lost=-1.0,
    bonus_100_rush_yards=3.0, bonus_100_rec_yards=3.0,
    bonus_300_pass_yards=3.0)

FANDUEL_STYLE = ScoringProfile(
    name='fanduel_style', version='1',
    per_pass_yard=0.04, per_pass_td=4.0, per_interception=-1.0,
    per_rush_yard=0.1, per_rush_td=6.0,
    per_reception=0.5, per_rec_yard=0.1, per_rec_td=6.0,
    per_fumble_lost=-2.0)

STANDARD_NON_PPR = ScoringProfile(
    name='standard_non_ppr', version='1',
    per_pass_yard=0.04, per_pass_td=4.0, per_interception=-2.0,
    per_rush_yard=0.1, per_rush_td=6.0,
    per_reception=0.0, per_rec_yard=0.1, per_rec_td=6.0,
    per_fumble_lost=-2.0)

PROFILES = {p.name: p for p in (DRAFTKINGS_STYLE, FANDUEL_STYLE,
                                STANDARD_NON_PPR)}

_STAT_FIELDS = ('pass_yards', 'pass_td', 'interceptions', 'rush_yards',
                'rush_td', 'receptions', 'rec_yards', 'rec_td', 'fumbles_lost')


def score_line(stats: Mapping, profile: ScoringProfile) -> Outcome:
    """Score ONE completed stat line. Missing fields are refused, not zeroed."""
    if not isinstance(profile, ScoringProfile):
        return Outcome.blocked('UNKNOWN_SCORING_PROFILE',
                               f'{profile!r} is not a ScoringProfile',
                               cause=Cause.GOVERNANCE)
    unknown = [k for k in stats if k not in _STAT_FIELDS]
    if unknown:
        return Outcome.fail(
            'UNKNOWN_STAT_FIELD',
            f'{unknown} are not scoring inputs. Silently ignoring an unknown '
            f'field is how a scoring change goes unnoticed.', unknown=unknown)
    v = {k: float(stats.get(k, 0.0)) for k in _STAT_FIELDS}
    p = profile
    pts = (v['pass_yards'] * p.per_pass_yard
           + v['pass_td'] * p.per_pass_td
           + v['interceptions'] * p.per_interception
           + v['rush_yards'] * p.per_rush_yard
           + v['rush_td'] * p.per_rush_td
           + v['receptions'] * p.per_reception
           + v['rec_yards'] * p.per_rec_yard
           + v['rec_td'] * p.per_rec_td
           + v['fumbles_lost'] * p.per_fumble_lost)
    if v['rush_yards'] >= 100: pts += p.bonus_100_rush_yards
    if v['rec_yards'] >= 100: pts += p.bonus_100_rec_yards
    if v['pass_yards'] >= 300: pts += p.bonus_300_pass_yards
    return Outcome.ok('SCORED', value=round(pts, 6),
                      detail=f'{p.name} v{p.version}: {round(pts, 2)} pts',
                      profile=p.name, profile_version=p.version)


def score_draws(stats_arrays: Mapping, profile: ScoringProfile) -> Outcome:
    """Score a whole draw matrix, preserving the draw index."""
    import numpy as np
    n = None
    for k, a in stats_arrays.items():
        if k not in _STAT_FIELDS:
            return Outcome.fail('UNKNOWN_STAT_FIELD', f'{k!r} is not a '
                                f'scoring input.', unknown=[k])
        a = np.asarray(a)
        if n is None:
            n = a.shape[0]
        elif a.shape[0] != n:
            return Outcome.fail(
                'DRAW_LENGTH_MISMATCH',
                f'{k} has {a.shape[0]} draws against {n}. Scoring a ragged set '
                f'would combine draw i of one field with draw j of another.',
                field=k)
    if n is None:
        return Outcome.fail('NO_STATS', 'no stat arrays supplied.')
    out = np.zeros(n, float)
    for i in range(n):
        o = score_line({k: np.asarray(a)[i] for k, a in stats_arrays.items()},
                       profile)
        out[i] = o.value
    return Outcome.ok('SCORED_DRAWS', value=out,
                      detail=f'{profile.name} v{profile.version}: {n} draws',
                      profile=profile.name)
