"""Stable stream identities for every seeded draw in the predictive path.

WHY THIS MODULE EXISTS

Two production layers derived an RNG component from Python's builtin `hash()`
of a string:

    layers.targets_carries   np.random.default_rng([seed, hash(cls) % 9973])
    team_volume_v1.forecast  np.random.default_rng([seed, ordinal,
                                                    hash(metric) % 9973])

Python randomises string hashing per process and `PYTHONHASHSEED` is unset in
this repository, so BOTH layers drew a different stream on every run. Measured
before the repair: three processes, identical inputs and identical declared
seed, produced three different allocation share matrices and `other` masses of
0.005328 / 0.006891 / 0.004916.

A declared seed that does not determine the draw is not a seed. It also breaks
the project's fingerprint discipline at the root: an experiment whose draw
cannot be reproduced has no execution identity, and every "same seed" comparison
across processes was comparing streams rather than the thing under test.

THE CONTRACT

An explicit integer per named stream. No hashing of any kind, builtin or
cryptographic -- a table this small should be readable, and a reader should be
able to see which integer a stream got without running anything. Unknown keys
are REFUSED, never defaulted, so a new metric or allocation class cannot
silently share a stream with an existing one.

Ids are FROZEN. Changing an id changes every draw that uses it, so a new stream
takes the next free integer and existing ones are never renumbered. The
contract version below travels in execution identity.
"""
from __future__ import annotations

import hashlib
import sys
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome  # noqa: E402

SEED_CONTRACT = 'nfl-stream-seed-v1'

# namespace -> {stream name: frozen integer id}. Never renumber; append only.
STREAMS = {
    'p4c_alloc': {
        'snaps': 1,
        'pass_snaps': 2,
        'targets': 3,
        'carries': 4,
        'rz_carries': 5,
    },
    'team_volume': {
        'team_off_snaps': 1,
        'team_dropbacks_part': 2,
        'team_targets': 3,
        'team_carries': 4,
        'team_rz_carries': 5,
    },
}


def stream_id(namespace: str, name: str) -> Outcome:
    """The frozen integer for one named stream, or a named refusal.

    Refuses rather than defaulting: a stream with no declared id must not
    silently collide with one that has an id, because two layers sharing a
    stream is a correlation nobody declared.
    """
    ns = STREAMS.get(namespace)
    if ns is None:
        return Outcome.fail(
            'SEED_NAMESPACE_UNKNOWN',
            f'{namespace!r} is not a declared seed namespace; the declared '
            f'namespaces are {sorted(STREAMS)}',
            namespace=namespace, known=sorted(STREAMS))
    sid = ns.get(name)
    if sid is None:
        return Outcome.fail(
            'SEED_STREAM_UNDECLARED',
            f'{name!r} has no declared stream id in namespace {namespace!r}. '
            f'Add one -- appending the next free integer, never renumbering an '
            f'existing id -- rather than letting it fall back onto another '
            f'stream. Declared: {sorted(ns)}',
            namespace=namespace, name=name, known=sorted(ns))
    return Outcome.ok('SEED_STREAM_ID', value=int(sid),
                      detail=f'{namespace}/{name} -> {sid}',
                      seed_contract=SEED_CONTRACT,
                      derived_from_python_hash=False)


def contract() -> dict:
    """The whole mapping, for execution identity and provenance."""
    return {'seed_contract': SEED_CONTRACT,
            'streams': {ns: dict(v) for ns, v in STREAMS.items()},
            'uses_python_hash': False,
            'stable_across': ['process', 'machine', 'invocation order',
                              'PYTHONHASHSEED']}


def game_component(game_id: str) -> Outcome:
    '''A stable per-GAME integer, so two games never share one stream.

    THE DEFECT THIS CLOSES. Three seeded sites carried no game identity at all:

        layers.appearance        [seed, season * 100 + week, 11]
        layers._run_real         [seed, season * 100 + week, 11]
        layers.targets_carries   [seed, stream_id]        -- not even the week

    Every game on a slate therefore drew from the SAME stream. Measured on two
    disjoint synthetic games with equal player counts, the non-modelled target
    mass vectors were bit-identical (r = 1.000) and the appearance draw rows
    correlated at r = +0.545 ACROSS GAMES THAT SHARE NO PLAYER.

    That is the mirror image of the project's usual dependence defect: not a
    dependence missing where football has one, but a dependence of exactly 1.0
    invented between games that are independent. A slate of sixteen such games
    is not sixteen games, and any across-game aggregate carries the wrong
    dispersion with an unstable sign.

    WHY A HASH HERE, WHEN `stream_id` REFUSES ONE. `stream_id` enumerates a
    small closed set that a reader should be able to check by eye. Game ids are
    an open set -- one per matchup per week forever -- so a table is not
    available. What the seed contract actually requires is determinism across
    processes, which `hash()` violated and sha256 does not: the same game_id
    yields the same integer on every machine, every process and every value of
    PYTHONHASHSEED. Nothing is fitted and no marginal moves; only the stream a
    game draws from changes.
    '''
    if not game_id or not isinstance(game_id, str):
        return Outcome.fail(
            'SEED_GAME_ID_MISSING',
            f'a per-game stream component needs a game id; got {game_id!r}. '
            f'Refusing rather than defaulting to a shared stream, which is '
            f'exactly the collision this function exists to remove.',
            game_id=game_id)
    d = hashlib.sha256(f'{SEED_CONTRACT}|{game_id}'.encode()).digest()
    return Outcome.ok(
        'SEED_GAME_COMPONENT',
        value=int.from_bytes(d[:4], 'big'),
        detail=f'{game_id} -> stable 32-bit component',
        seed_contract=SEED_CONTRACT, derived_from_python_hash=False,
        stable_across_processes=True)
