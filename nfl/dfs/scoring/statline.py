"""The stat line: one player, one world, in the units a scoring system reads.

THE POINT OF SEPARATING THIS OUT

A scoring adapter that reaches into the draw file decides two things at once --
what the football was, and what it is worth on a site. Those have to come
apart, because the whole architecture rests on ONE set of football worlds
feeding SEVERAL scoring systems. If DraftKings and FanDuel each assembled their
own stat line from the arrays, a difference between them could be a rules
difference or an assembly bug and nobody could tell which.

So the arrays are assembled here, once, and every adapter is handed the same
`StatLine`.

ASSEMBLY IS NOT OBVIOUS AND WAS WRONG ONCE

A first attempt reproduced stored DK points exactly for pure runners and missed
by up to 17.0 points for receivers. The cause was `rushing_total/rushing_yards`
-- gadget carries by wide receivers, which live in their own layer and which a
formula written from the obvious components does not include. Jameson Williams
in world 2602: 102 receiving yards, 6 catches, and 140 rushing yards nobody had
counted.

That is why `verify_against_stored_dk` exists and why it asserts EXACT equality
rather than closeness. The stored `dk_scoring/dk_points` array is an
independent implementation of DraftKings scoring, already in the artifact, and
reproducing it to floating-point is the only evidence that this assembly is
complete.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'nfl-dfs-statline-1'

#: Events the football simulation DOES NOT PRODUCE. Named, so an adapter
#: refuses rather than scoring a zero it invented. A zero here would be a
#: claim that the event never happens, and the simulation makes no such claim.
NOT_SIMULATED = {
    'fumbles_lost': 'no fumble model exists in the engine',
    'two_point_conversions': 'no two-point conversion model exists',
    'return_td': 'no kick or punt return model exists',
    'passing_2pt': 'same as two_point_conversions',
    'dst': 'the engine produces no team-defence outputs at all',
    'fg_missed_penalty': 'missed field goals are simulated (fga - fgm) but no '
                         'site scored here penalises them; recorded so a '
                         'future site that does is not silently mis-scored',
}


@dataclasses.dataclass
class StatLine:
    """Per-world arrays for one player. Every field is (n_worlds,)."""
    name: str
    pass_yards: np.ndarray
    pass_td: np.ndarray
    interceptions: np.ndarray
    rush_yards: np.ndarray
    rush_td: np.ndarray
    rec_yards: np.ndarray
    receptions: np.ndarray
    rec_td: np.ndarray
    fg_made: np.ndarray
    fg_att: np.ndarray
    xp_made: np.ndarray
    xp_att: np.ndarray
    fg_made_by_bucket: dict

    @property
    def n_worlds(self) -> int:
        return int(self.pass_yards.shape[0])


def _z(n):
    return np.zeros(n)


def assemble(gid: str, name: str, layers: dict, arrays, n_worlds: int) -> StatLine:
    """Build one stat line from the draw arrays.

    RUSHING YARDS COME FROM ONE LAYER AND IT IS NOT THE OBVIOUS ONE.

    `rushing_total/rushing_yards` is the authoritative per-player total: it
    equals `rushing/rushing_yards` for backs, equals the gadget yards for
    receivers, and for quarterbacks it is NOT equal to `qb/ryds` -- Josh Allen
    means 30.82 against 32.46, so `qb/ryds` counts something the scorer does
    not, most likely kneels.

    Both wrong answers were tried against the engine's own DK array. Summing
    the three sources double-counts backs and misses by up to 33.8 points;
    preferring `qb/ryds` for quarterbacks misses by up to 6.0. Using
    `rushing_total` alone reproduces all 29 players over all 8,000 worlds to
    0.0. That is why this is a lookup and not an addition.
    """
    def g(layer, metric):
        spec = layers.get(layer)
        if not spec:
            return None
        ids = spec.get('row_ids') or []
        if gid not in ids:
            return None
        k = f'{layer}__{metric}'
        if k not in arrays.files:
            return None
        return np.asarray(arrays[k])[ids.index(gid)].astype(float)

    def gz(layer, metric):
        v = g(layer, metric)
        return _z(n_worlds) if v is None else v

    rush = gz('rushing_total', 'rushing_yards')
    rtd = gz('rushing', 'rushing_td') + gz('qb', 'rtd')
    buckets = {}
    for b in ('FG<20', 'FG20s', 'FG30s', 'FG40s', 'FG50+'):
        v = g('kicking', f'made_{b}')
        if v is not None:
            buckets[b] = v
    return StatLine(
        name=name,
        pass_yards=gz('qb', 'pyds'), pass_td=gz('qb', 'ptd'),
        interceptions=gz('qb', 'int'),
        rush_yards=rush, rush_td=rtd,
        rec_yards=gz('receiving', 'receiving_yards'),
        receptions=gz('receiving', 'receptions'),
        rec_td=gz('receiving', 'receiving_td'),
        fg_made=gz('kicking', 'fgm'), fg_att=gz('kicking', 'fga'),
        xp_made=gz('kicking', 'xpm'), xp_att=gz('kicking', 'xpa'),
        fg_made_by_bucket=buckets)


def from_line(n_worlds: int = 1, **kw) -> StatLine:
    """A hand-built stat line, for unit tests with a known answer."""
    f = {k.name: _z(n_worlds) for k in dataclasses.fields(StatLine)
         if k.name not in ('name', 'fg_made_by_bucket')}
    for k, v in kw.items():
        if k in f:
            f[k] = np.full(n_worlds, float(v))
    return StatLine(name=kw.get('name', 'test'), fg_made_by_bucket={}, **f)
