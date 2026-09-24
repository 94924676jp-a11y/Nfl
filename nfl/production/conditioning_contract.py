"""Name the event a projection is conditioned on, and store it.

THE DEFECT

A projection table prints one number per player. Jordan Love's 15.25 is very
nearly a conditional figure because he records opportunity in 96% of worlds;
Cooper Rush's 9.23 is not, because a third of its mass comes from worlds where
he never takes a snap. Read side by side they look like the same quantity and
they are not.

The repair is not a ratio. Anyone can divide 14.04 by 9.23 and recover 0.657,
but recovering a probability by division tells you nothing about WHICH EVENT
it is the probability of -- and that is the part a reader needs. "He plays",
"he is active", "he has a meaningful role" and "he records a modelled
opportunity" are four different events with four different probabilities, and
a table that leaves the reader to guess which one is in play has not answered
the question.

So the event is DECLARED per position, its definition is stored beside the
number, and the number says which event it is conditioned on by name.

WHAT IS HONESTLY MEASURABLE TODAY, AND WHAT IS NOT

The draw artifact carries opportunity, not participation. A receiver on the
field all game who is never thrown to records nothing. So the event this
module can actually evaluate is ANY_MODELLED_OPPORTUNITY, which is a LOWER
BOUND on participation. The richer chains below -- active, then role, then
opportunity -- are declared as the contract each position OUGHT to carry, with
the stages that have no estimator marked NOT_IDENTIFIED rather than filled in.

Declaring a chain we cannot yet evaluate is not aspiration dressed as fact: it
is the difference between "we did not measure this" and "this does not exist",
and a reader must be able to tell those apart.
"""
from __future__ import annotations

import numpy as np

SPEC_VERSION = 'conditioning-contract/1.0.0'

#: Event definitions. Each is a sentence a reader can check a number against.
EVENTS = {
    'ROSTER_ACTIVE': 'the club listed him on the game roster and no terminal '
                     'designation rules him out',
    'MEANINGFUL_ROLE': 'he occupies a role that generates opportunity, as '
                       'opposed to dressing and not featuring',
    'ANY_MODELLED_OPPORTUNITY': 'he records at least one non-zero modelled '
                                'opportunity -- a dropback, target, carry or '
                                'kick attempt -- in the simulated world',
    'OWNS_MEANINGFUL_DROPBACKS': 'he is the quarterback taking the club\'s '
                                 'dropbacks rather than a backup who never '
                                 'throws',
    'TEAM_SCORING_OPPORTUNITY': 'his club generates a kick attempt',
    'GAME_LEVEL_EVENT': 'a team-defence score is a property of the game, not '
                        'of a player, and does not condition on an individual',
}

#: The chain each position OUGHT to carry, outermost first.
CHAINS = {
    'QB': ('ROSTER_ACTIVE', 'OWNS_MEANINGFUL_DROPBACKS',
           'ANY_MODELLED_OPPORTUNITY'),
    'RB': ('ROSTER_ACTIVE', 'MEANINGFUL_ROLE', 'ANY_MODELLED_OPPORTUNITY'),
    'WR': ('ROSTER_ACTIVE', 'MEANINGFUL_ROLE', 'ANY_MODELLED_OPPORTUNITY'),
    'TE': ('ROSTER_ACTIVE', 'MEANINGFUL_ROLE', 'ANY_MODELLED_OPPORTUNITY'),
    'K': ('ROSTER_ACTIVE', 'TEAM_SCORING_OPPORTUNITY',
          'ANY_MODELLED_OPPORTUNITY'),
    'DST': ('GAME_LEVEL_EVENT',),
}

#: The only stage these draws can evaluate. Everything else is declared.
EVALUABLE = frozenset({'ANY_MODELLED_OPPORTUNITY'})

NOT_IDENTIFIED = 'NOT_IDENTIFIED'
MEASURED = 'MEASURED'
NOT_APPLICABLE = 'NOT_APPLICABLE'

#: Below this many qualifying draws a conditional mean is withheld.
MIN_CONDITIONAL_DRAWS = 200


class ContractError(RuntimeError):
    """The contract cannot be built for this input."""


def chain_for(position: str) -> tuple:
    pos = (position or '').upper()
    if pos not in CHAINS:
        raise ContractError(
            f'no conditioning chain is declared for position {position!r}. '
            f'Add one deliberately rather than defaulting to the receiver '
            f'chain, which would assert a role structure nobody chose.')
    return CHAINS[pos]


def build(position, values, *, opportunity_mask=None, player=None) -> dict:
    """A projection with its conditioning event named and defined.

    `values` are the player's per-draw scoring values; `opportunity_mask` is
    the per-draw boolean for ANY_MODELLED_OPPORTUNITY, or None when it cannot
    be measured for this player.
    """
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        raise ContractError(
            'no draws supplied; an empty distribution is not a projection')

    chain = chain_for(position)
    stages = []
    for event in chain:
        if event == 'GAME_LEVEL_EVENT':
            stages.append({'event': event, 'definition': EVENTS[event],
                           'state': NOT_APPLICABLE, 'p': None,
                           'why': 'a team defence has no individual '
                                  'participation event to condition on'})
            continue
        if event in EVALUABLE and opportunity_mask is not None:
            mask = np.asarray(opportunity_mask, dtype=bool)
            stages.append({
                'event': event, 'definition': EVENTS[event],
                'state': MEASURED,
                'p': float(mask.mean()),
                'n_qualifying': int(mask.sum()),
                'basis': 'counted directly from the draws'})
            continue
        stages.append({
            'event': event, 'definition': EVENTS[event],
            'state': NOT_IDENTIFIED, 'p': None,
            'why': ('no estimator for this stage exists in the current '
                    'artifact, so its probability is NOT measured. That is '
                    'different from it being one.')})

    measured = [s for s in stages if s['state'] == MEASURED]
    out = {
        'spec_version': SPEC_VERSION,
        'player': player,
        'position': (position or '').upper(),
        'declared_chain': list(chain),
        'stages': stages,
        'mean_unconditional': float(values.mean()),
        'unconditional_means_what': (
            'integrates over every stage of the chain, including the worlds '
            'in which he does not appear. For a DFS slot this is the correct '
            'number, because a player who does not appear scores zero.'),
    }

    if not measured:
        out['conditioned_on'] = None
        out['mean_conditional'] = None
        out['conditional_basis'] = NOT_IDENTIFIED
        out['note'] = (
            'no stage of this position\'s chain is measurable from these '
            'draws, so no conditional mean is offered. A ratio computed by a '
            'reader would not name the event it conditions on.')
        return out

    # The innermost MEASURED stage is what a conditional mean can condition on.
    stage = measured[-1]
    mask = np.asarray(opportunity_mask, dtype=bool)
    n = int(mask.sum())
    out['conditioned_on'] = stage['event']
    out['conditioned_on_definition'] = stage['definition']
    out['p_conditioning_event'] = stage['p']
    if n < MIN_CONDITIONAL_DRAWS:
        out['mean_conditional'] = None
        out['conditional_basis'] = 'TOO_FEW_QUALIFYING_DRAWS'
        out['note'] = (f'{n} qualifying draws is below the floor of '
                       f'{MIN_CONDITIONAL_DRAWS}, so the conditional mean is '
                       f'withheld rather than printed as noise')
        return out
    kept = values[mask]
    out['mean_conditional'] = float(kept.mean())
    out['conditional_basis'] = MEASURED
    out['conditional_means_what'] = (
        f'the average across worlds in which {stage["event"]} holds, where '
        f'that event is defined as: {stage["definition"]}')
    out['unmeasured_stages'] = [s['event'] for s in stages
                                if s['state'] == NOT_IDENTIFIED]
    return out


def assert_event_named(record: dict) -> None:
    """Refuse a record whose conditional number has no named event.

    This is the whole contract in one assertion: a conditional mean that does
    not say what it is conditional on is the defect, not the fix.
    """
    if record.get('mean_conditional') is None:
        return
    if not record.get('conditioned_on'):
        raise ContractError(
            'a conditional mean was produced with no conditioning event '
            'named. A number conditioned on an unnamed event cannot be '
            'checked by a reader and must not be published.')
    if not record.get('conditioned_on_definition'):
        raise ContractError(
            f'{record["conditioned_on"]} is named but not defined. A reader '
            f'cannot verify a number against an event they must guess at.')
