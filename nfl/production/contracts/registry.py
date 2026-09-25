"""The contract registry. What a complete artifact of each CLASS looks like.

WHAT A CONTRACT IS, AND THE LINE IT MUST NOT CROSS

A contract describes the SEMANTICS OF AN ARTIFACT CLASS: which layers a
football player-draw artifact carries, which metrics each layer owns, which
row axis it is keyed on, and whether zero rows can ever be legal. Every NFL
game has players who catch passes and players who carry the ball, so a
player-draw artifact that carries no receiving layer is not a thin instance
of its class -- it is a malformed one.

It is NOT the place for game-specific or team-specific completeness. "Did BOTH
clubs get receiving rows" and "was every expected player accounted for" are
questions about a particular game against a particular point-in-time roster,
and they belong to the coverage layer (blueprint 6), not here. A contract that
knew about clubs would have to know about rosters, and then the artifact
schema would move every time a roster did.

ZERO ROWS MUST BE DECLARED, NEVER INFERRED

Blueprint 5.2. A stage that has not said whether emptiness is legal cannot be
allowed to return an empty artifact, because the reader has no way to tell a
legitimate empty from a silent failure. `register` therefore REFUSES a layer
whose `zero_rows_legal_when` is unset -- the registration itself fails, at
import time, rather than the defect surfacing on a Sunday.

This is the mechanism blueprint 20 of the research packet asks for: "the
schema registry refuses to register a stage without min_rows and
zero_rows_legal_when".
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from typing import ClassVar

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class ContractRegistrationError(ValueError):
    """Raised at REGISTRATION time, not at run time.

    A contract with an undeclared emptiness rule is a defect in the contract,
    and a defect in a contract must not wait for production data to be found.
    """


@dataclasses.dataclass(frozen=True)
class LayerSpec:
    """One layer inside an artifact class.

    name
        The layer key as the manifest spells it (`receiving`, `qb`, ...).
    row_axis
        What a row means. `gsis_id` for player layers, `team` for club-level
        layers. Checked against the manifest so a layer cannot quietly change
        what its rows are keyed on.
    metrics
        Metrics this layer MUST carry. A declared metric with no bytes is
        `DECLARED_METRIC_BYTES_ABSENT`, never a skipped column.
    scope
        WHICH PRODUCT the layer is required BY. `football` layers are the
        simulation itself. `dfs_product` layers are deterministic
        TRANSFORMATIONS of it.

        CORRECTED BY OWNER RULING. `dk_scoring` was first marked required
        with the reason "every NFL game has scoring". That conflated two
        different things: an NFL game has scoring, but DRAFTKINGS scoring is
        a downstream arithmetic transform of football statistics, not a
        football fact. Marking it a football requirement meant a missing DK
        transform would have declared an otherwise complete and valid
        football simulation invalid -- the decision products reaching back
        and invalidating the football layer, which is the exact direction of
        travel this project forbids. A missing `dk_scoring` must block a
        DraftKings board and nothing else.
    required
        Whether an artifact is malformed without the layer WITHIN ITS SCOPE.
    min_rows
        Fewest rows a present layer may carry.
    zero_rows_legal_when
        Prose stating the ONLY condition under which zero rows is a result
        rather than a failure. Required for every layer. `NEVER` is a
        legitimate and common answer, and it is an answer.
    """

    name: str
    row_axis: str
    metrics: tuple[str, ...]
    required: bool
    min_rows: int
    zero_rows_legal_when: str
    scope: str = 'football'

    def __post_init__(self):
        if not self.zero_rows_legal_when:
            raise ContractRegistrationError(
                f'layer {self.name!r} declares no zero_rows_legal_when. A '
                f'stage that has not said whether emptiness is legal cannot '
                f'return an empty artifact, because a reader cannot tell a '
                f'legitimate empty from a silent failure. Write "NEVER" if '
                f'that is the answer -- silence is not.')
        if self.min_rows < 0:
            raise ContractRegistrationError(
                f'layer {self.name!r} has min_rows {self.min_rows}')
        if not self.metrics:
            raise ContractRegistrationError(
                f'layer {self.name!r} declares no metrics; a layer that owns '
                f'no metric has no bytes to check and cannot be verified')


@dataclasses.dataclass(frozen=True)
class ArtifactContract:
    """One artifact class.

    producer
        Import path of the code that writes it. Recorded so a reader can get
        from a bad artifact to the stage that made it without grepping.
    requires_run_identity
        Whether an instance must name the run that produced it and the digest
        of its own contents.

        CORRECTED DURING P0-A. This field first read
        `requires_information_cut`, and the checker looked for `written_at`
        on the draw manifest. No draw manifest has ever carried that key:
        this class records provenance BY REFERENCE (`run_id`, `game_id`,
        `content_digest`) and the information cut lives in
        `run_status.json`. The check failed all eight real Week-2 artifacts
        over a field the class does not own -- a contract asserting a
        remembered field name instead of the artifact's actual semantics,
        which is the precise defect this module exists to kill, committed
        inside the fix for it. The cut is checked where it lives, in the
        state and certificate layer (P0-C).
    """

    name: str
    schema_version: str
    producer: str
    layers: tuple[LayerSpec, ...]
    requires_run_identity: bool = True

    def layer(self, name: str) -> LayerSpec | None:
        for ls in self.layers:
            if ls.name == name:
                return ls
        return None

    #: THE SCOPE DEPENDENCY GRAPH. Football is the root truth; everything
    #: else consumes it.
    #:
    #: CORRECTED BY OWNER RULING, SECOND PASS. This was first a flat tuple
    #: and `required_layers` filtered on `ls.scope == scope`, which made the
    #: scopes INDEPENDENT. Asking for `dfs_product` then required only
    #: `dk_scoring`, so PHI@TEN -- no receiving layer, no rushing layer --
    #: returned football FAIL and dfs_product PASS. That is the Week-2 defect
    #: recreated one layer higher: a downstream artifact calling itself valid
    #: while the model beneath it is broken. DK point bytes are not evidence
    #: that DFS is sound when they were computed from a broken football
    #: world.
    #:
    #: The rule the ruling actually states, and the one enforced here:
    #:
    #:     upstream validity flows DOWNWARD;
    #:     downstream invalidity does NOT flow upward.
    #:
    #: A child scope ADDS requirements and can never erase its parent's.
    SCOPE_PARENTS: ClassVar[dict[str, tuple[str, ...]]] = {
        'football': (),
        'dfs_product': ('football',),
        # `prop_product: ('football',)` drops in here with no change to the
        # abstraction. Deployment gates -- field model, ownership,
        # duplication, payout, market freshness, calibration -- build ABOVE
        # these artifact scopes and are deliberately not artifact layers.
    }

    def ancestors(self, scope: str) -> tuple[str, ...]:
        """`scope` and every scope it depends on, roots first."""
        if scope not in self.SCOPE_PARENTS:
            raise ContractRegistrationError(
                f'unknown scope {scope!r}; known '
                f'{tuple(self.SCOPE_PARENTS)}')
        seen, order = set(), []

        def walk(s):
            if s in seen:
                return
            seen.add(s)
            for parent in self.SCOPE_PARENTS.get(s, ()):
                walk(parent)
            order.append(s)
        walk(scope)
        return tuple(order)

    def required_layers(self, scope: str = 'football') -> tuple[str, ...]:
        """Layers an artifact must carry to be complete FOR ONE PRODUCT.

        CUMULATIVE over the scope's ancestors. `dfs_product` requires every
        football layer AND `dk_scoring`; a DFS transform computed on a broken
        football world is not a valid DFS transform.
        """
        chain = set(self.ancestors(scope))
        return tuple(ls.name for ls in self.layers
                     if ls.required and ls.scope in chain)


REGISTRY: dict[str, ArtifactContract] = {}


def register(c: ArtifactContract) -> ArtifactContract:
    if c.name in REGISTRY:
        raise ContractRegistrationError(f'{c.name!r} already registered')
    if not c.layers:
        raise ContractRegistrationError(
            f'{c.name!r} declares no layers; there would be nothing to check')
    REGISTRY[c.name] = c
    return c


def get(name: str) -> ArtifactContract:
    if name not in REGISTRY:
        raise KeyError(
            f'no contract registered under {name!r}; known: '
            f'{sorted(REGISTRY)}')
    return REGISTRY[name]


def names() -> list[str]:
    return sorted(REGISTRY)


# ---------------------------------------------------------------------------
# PLAYER_DRAWS -- the artifact PHI@TEN shipped malformed.
#
# The four football player layers are REQUIRED because they are properties of
# the class, not of a slate: every NFL game is played by receivers, backs and
# a quarterback, and every one of them is scored. A game in which the model
# emits no receiving layer has not produced a thin forecast; it has produced
# an artifact that is not a member of this class.
#
# `gadget_rush`, `rush_category`, `rush_player_pool` and `kicking` are NOT
# required: they are conditional on candidate flags (`allocate_gadget_rush`,
# `rush_single_owner`) and on a kicker being rostered, so their absence is a
# configuration fact rather than a malformation. They are still listed, so
# that when they ARE present their metrics and row axis are checked.
# ---------------------------------------------------------------------------
PLAYER_DRAWS = register(ArtifactContract(
    name='player_draws',
    schema_version='nfl-player-draws-contract-1',
    producer='nfl.production.run_forecast:_draws',
    layers=(
        LayerSpec(
            name='receiving', row_axis='gsis_id',
            metrics=('targets', 'receptions', 'receiving_yards',
                     'receiving_td'),
            required=True, min_rows=1,
            zero_rows_legal_when='NEVER. Every NFL game is played by pass '
                                 'catchers; an emitted game with no '
                                 'receiving rows is malformed, not empty.'),
        LayerSpec(
            name='rushing', row_axis='gsis_id',
            metrics=('carries', 'rushing_yards', 'rushing_td'),
            required=True, min_rows=1,
            zero_rows_legal_when='NEVER. Every NFL game is played by ball '
                                 'carriers.'),
        LayerSpec(
            name='qb', row_axis='gsis_id',
            metrics=('att', 'cmp', 'pyds', 'ptd', 'int'),
            required=True, min_rows=1,
            zero_rows_legal_when='NEVER. Every NFL game is played by '
                                 'quarterbacks.'),
        LayerSpec(
            name='dk_scoring', row_axis='gsis_id', metrics=('dk_points',),
            required=True, min_rows=1, scope='dfs_product',
            zero_rows_legal_when='NEVER when a DraftKings product is being '
                                 'built. Its ABSENCE blocks a DK board and '
                                 'says nothing about the football '
                                 'simulation, which is complete without it.'),
        LayerSpec(
            name='rushing_total', row_axis='gsis_id',
            metrics=('rushing_yards',),
            required=False, min_rows=1,
            zero_rows_legal_when='NEVER when present.'),
        LayerSpec(
            name='team_volume', row_axis='team',
            metrics=('team_carries', 'team_targets', 'team_off_snaps'),
            required=False, min_rows=1,
            zero_rows_legal_when='NEVER when present; a club-level layer '
                                 'with no clubs is malformed.'),
        LayerSpec(
            name='kicking', row_axis='gsis_id',
            metrics=('fgm', 'fga', 'dk_points'),
            required=False, min_rows=1,
            zero_rows_legal_when='Legal to be ABSENT when no kicker is in '
                                 'the emitted pool; never legal to be '
                                 'present with zero rows.'),
        LayerSpec(
            name='gadget_rush', row_axis='gsis_id',
            metrics=('wr', 'te', 'kneel'),
            required=False, min_rows=1,
            zero_rows_legal_when='Legal to be ABSENT when the '
                                 'allocate_gadget_rush flag is off; never '
                                 'legal to be present with zero rows.'),
        LayerSpec(
            name='rush_category', row_axis='team',
            metrics=('rb', 'wr', 'te', 'designed_qb', 'kneel', 'fringe'),
            required=False, min_rows=1,
            zero_rows_legal_when='Legal to be ABSENT when the '
                                 'rush_single_owner flag is off; never legal '
                                 'to be present with zero rows.'),
        LayerSpec(
            name='rush_player_pool', row_axis='team',
            metrics=('unmodelled_back_pool',),
            required=False, min_rows=1,
            zero_rows_legal_when='Legal to be ABSENT when the '
                                 'rush_single_owner flag is off; never legal '
                                 'to be present with zero rows.'),
    ),
))


#: The metric name under which DraftKings fantasy points are stored.
DK_METRIC = 'dk_points'


class NoDkBearingLayer(RuntimeError):
    """The artifact declares no player-keyed layer carrying DK points."""


def dk_bearing_layers(manifest: dict) -> list:
    """Every player-keyed layer in this artifact that carries DK points.

    WHY THIS LIVES WITH THE CONTRACT AND NOT WITH DFS.

    "Which layers carry DK points" is a property of the ARTIFACT, discoverable
    from its own manifest, so it belongs beside the contract that describes the
    artifact. It sat in `nfl.dfs.player_universe`, which also reads DK salary
    CSVs and contest files -- so any module needing the fact had to import a
    module that reaches into live DK data.

    That mattered immediately. `review/dossier.py` needed this to give a kicker
    a headline metric, and `test_dossier_migration` forbids the dossier from
    importing `player_universe` by name: football evidence must arrive through
    PregameSlateState, while projection and simulation artifacts are the
    dossier's own to read. The invariant was right and the helper was in the
    wrong place. Reading a layer list out of a manifest the dossier already
    holds is not reading a football source.

    DISCOVERED, NEVER LISTED. Six production modules named `dk_scoring` alone
    and so never saw a kicker -- among them the slate board, the dossier and
    postgame grading (DEF-060). Seven more name `dk_scoring` AND `kicking` by
    hand: correct today, silently wrong the day a third DK-bearing layer
    appears. This reads the artifact instead.
    """
    out = []
    for name, spec in sorted((manifest.get('layers') or {}).items()):
        if not isinstance(spec, dict) or spec.get('row_axis') != 'gsis_id':
            continue
        if DK_METRIC in (spec.get('metrics') or ()):
            out.append(name)
    if not out:
        raise NoDkBearingLayer(
            'no player-keyed layer declares a dk_points metric; a DK universe '
            'cannot be built from this artifact and must not be faked')
    return out
