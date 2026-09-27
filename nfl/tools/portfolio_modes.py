#!/usr/bin/env python3.12
"""Portfolio modes and declared constraints. No hard-coded diversification targets.

WHY THIS REPLACES THE PREVIOUS OBJECTIVE. The first generator hard-coded a maximum QB
exposure of 35%, a maximum pairwise overlap of 6, and a stack size of 1-2, and the portfolio
it produced projected 140-150 against the owner's 165-171. I described that 15-point gap as
"the cost of diversification". That was a claim I had not earned: without an ownership model
or a field simulation there is nothing that says 12 quarterbacks beats 4, and a number I
chose cannot justify a sacrifice it caused.

So every constraint is now a declared object carrying its VALUE, its REASON, its SOURCE
-- OWNER, HEURISTIC or MODEL_DERIVED -- and whether it actually BECAME BINDING on the run.
A heuristic that never binds costs nothing. A heuristic that binds and costs 15 projected
points has to be visible as exactly that.

THE FOUR AVAILABLE MODES span the projection/diversification frontier rather than picking a
point on it. SIM_OPTIMAL is declared and refused: solving for tournament value needs joint
simulation, an ownership model and contest payouts, and we have none of the three.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'portfolio-modes-1'

OWNER = 'OWNER'
HEURISTIC = 'HEURISTIC'
MODEL_DERIVED = 'MODEL_DERIVED'


@dataclasses.dataclass
class Constraint:
    name: str
    value: object
    reason: str
    source: str
    became_binding: bool = False
    binding_detail: str | None = None

    def as_dict(self):
        return dataclasses.asdict(self)


def _c(name, value, reason, source=HEURISTIC):
    return Constraint(name=name, value=value, reason=reason, source=source)


#: Structural rules that are football, not diversification. These are legality-adjacent:
#: a quarterback with nobody he throws to has no mechanism linking his ceiling to a
#: teammate, and a team defence against our own quarterback is two contradictory stories.
def structural(min_stack=1, max_stack=3):
    return {
        'min_pass_catchers_with_qb': _c(
            'min_pass_catchers_with_qb', min_stack,
            'a lineup whose quarterback throws to nobody in it has no correlated scoring '
            'path. This is a football requirement, not a diversification target.',
            HEURISTIC),
        'max_pass_catchers_with_qb': _c(
            'max_pass_catchers_with_qb', max_stack,
            'an upper bound only to keep the candidate pool from degenerating into one '
            'team. Not a claim that triple stacks are wrong.', HEURISTIC),
        'no_dst_against_own_qb': _c(
            'no_dst_against_own_qb', True,
            'the defence needs our quarterback to fail while the lineup needs him to '
            'succeed. Mathematically justified as a contradiction, so it is enforced.',
            HEURISTIC),
        'salary_cap': _c('salary_cap', 50_000,
                         'DraftKings contest rule', OWNER),
        'no_duplicate_player': _c('no_duplicate_player', True,
                                  'DraftKings contest rule', OWNER),
        'no_reported_absent_player': _c(
            'no_reported_absent_player', True,
            'a player reported out cannot score. Availability truth, not preference.',
            OWNER),
    }


MODES = {
    'PROJECTION_MAX': {
        'label': 'PROJECTION_MAX',
        'intent': ('maximise projected total subject only to legality and the structural '
                   'football rules. The reference point for what diversification costs.'),
        'constraints': lambda: structural(1, 3) | {
            'max_player_exposure': _c(
                'max_player_exposure', 1.00,
                'none. Every lineup may use the same player.', HEURISTIC),
            'max_qb_exposure': _c('max_qb_exposure', 1.00, 'none', HEURISTIC),
            'max_pairwise_overlap': _c(
                'max_pairwise_overlap', 9,
                'none beyond exact-duplicate rejection', HEURISTIC),
            'reject_exact_duplicates': _c(
                'reject_exact_duplicates', True, 'two byte-identical lineups in one contest cannot finish differently, so the second one buys nothing. The only constraint no mode switches off.', HEURISTIC),
        },
    },
    'LIGHT_DIVERSIFICATION': {
        'label': 'LIGHT_DIVERSIFICATION',
        'intent': 'allow meaningful concentration; basic anti-clone only.',
        'constraints': lambda: structural(1, 3) | {
            'max_player_exposure': _c('max_player_exposure', 0.90,
                                      'anti-clone only', HEURISTIC),
            'max_qb_exposure': _c('max_qb_exposure', 0.70, 'anti-clone only', HEURISTIC),
            'max_pairwise_overlap': _c('max_pairwise_overlap', 8,
                                       'one differing player minimum', HEURISTIC),
            'reject_exact_duplicates': _c(
                'reject_exact_duplicates', True, 'two byte-identical lineups in one contest cannot finish differently, so the second one buys nothing. The only constraint no mode switches off.', HEURISTIC),
        },
    },
    'BALANCED': {
        'label': 'BALANCED',
        'intent': 'moderate concentration limits.',
        'constraints': lambda: structural(1, 3) | {
            'max_player_exposure': _c('max_player_exposure', 0.75, 'moderate', HEURISTIC),
            'max_qb_exposure': _c('max_qb_exposure', 0.50, 'moderate', HEURISTIC),
            'max_pairwise_overlap': _c('max_pairwise_overlap', 7, 'moderate', HEURISTIC),
            'reject_exact_duplicates': _c(
                'reject_exact_duplicates', True, 'two byte-identical lineups in one contest cannot finish differently, so the second one buys nothing. The only constraint no mode switches off.', HEURISTIC),
        },
    },
    'HIGH_DIVERSIFICATION': {
        'label': 'HIGH_DIVERSIFICATION',
        'intent': ('broad spread. This is the mode the first generator hard-coded, and '
                   'its projection cost is now measurable rather than asserted.'),
        'constraints': lambda: structural(1, 2) | {
            'max_player_exposure': _c('max_player_exposure', 0.60, 'broad spread',
                                      HEURISTIC),
            'max_qb_exposure': _c('max_qb_exposure', 0.35, 'broad spread', HEURISTIC),
            'max_pairwise_overlap': _c('max_pairwise_overlap', 6, 'broad spread',
                                       HEURISTIC),
            'reject_exact_duplicates': _c(
                'reject_exact_duplicates', True, 'two byte-identical lineups in one contest cannot finish differently, so the second one buys nothing. The only constraint no mode switches off.', HEURISTIC),
        },
    },
}

SIM_OPTIMAL_UNAVAILABLE = {
    'mode': 'SIM_OPTIMAL',
    'state': 'UNAVAILABLE',
    'requires': ['joint game simulation with within-draw reconciliation',
                 'player outcome distributions, not means',
                 'opponent ownership / field model',
                 'contest payout structure and field size'],
    'why': ('tournament value is an expectation over a joint distribution against a field. '
            'None of the four inputs exists, so this mode is not merely unimplemented -- it '
            'is not yet a well-posed problem for us. It stays refused rather than '
            'approximated, because an approximation here would be handcrafted optimiser '
            'settings wearing the word optimal.'),
}

#: Unless diversification is justified by a model, a portfolio should not give up more than
#: this share of the best legal lineup's projection. A guardrail, not a truth.
DEFAULT_MAX_PROJECTION_LOSS = 0.08


def projection_loss_guard(chosen, optimum, max_loss=DEFAULT_MAX_PROJECTION_LOSS):
    """Measure what diversification actually cost against the best legal lineup found.

    This exists because "diversification" was used to explain a 15-point sacrifice without
    anybody measuring it. Until a field model can price the benefit, the cost at least has
    to be on the board.
    """
    if not chosen or not optimum:
        return {'state': 'NOT_COMPUTABLE', 'reason': 'no lineups or no optimum reference'}
    mean = sum(c['proj_total'] for c in chosen) / len(chosen)
    best = max(c['proj_total'] for c in chosen)
    loss_mean = (optimum - mean) / optimum
    loss_best = (optimum - best) / optimum
    return {
        'state': 'BREACH' if loss_mean > max_loss else 'WITHIN_GUARDRAIL',
        'optimum_legal_lineup': round(optimum, 2),
        'portfolio_mean': round(mean, 2),
        'portfolio_best': round(best, 2),
        'mean_loss_vs_optimum': round(loss_mean, 4),
        'best_loss_vs_optimum': round(loss_best, 4),
        'max_loss_guardrail': max_loss,
        'guardrail_source': HEURISTIC,
        'interpretation': (
            f'the portfolio gives up {100 * loss_mean:.1f}% of the best legal lineup '
            f'projection on average. Whether that is worth paying is a question for a '
            f'field model, which does not exist; the guardrail only stops the cost being '
            f'invisible.'),
    }
