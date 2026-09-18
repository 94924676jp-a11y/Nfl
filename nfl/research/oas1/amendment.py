"""Pre-fit amendment A1: two dead axes come out of the Week-2 search space.

THE BLOCKER THIS RESOLVES. `WEEK2_FIT_CONFIG.json` carries `half_life` and
`min_plays` in the search space, and the preregistration declares no mechanism
by which either enters the Week-2 OBJECTIVE. Running the fit with them in
would have selected over axes that cannot change a score, and afterwards there
would have been no way to tell which reading of them had been assumed. The
refusal was correct; this is the prospective resolution of it.

WHY REMOVAL RATHER THAN DEFINITION

`min_plays`. The preregistration's only statement about it is a REPORTING
rule: "a unit with fewer than min_plays current-season plays is reported with
n_plays_current_season and prior_weight_effective attached". Reporting does
not move the inner-fold score, so all three grid values give an identical
objective at every configuration. It is retained as a reporting parameter
FIXED AT 0 -- every unit is reported, with its play count attached -- and
removed from the search.

`half_life`. Two readings exist and the preregistration picks neither:

  (i)  decay WITHIN the current season. Exactly degenerate at week 2:
       the training set carries ONE 2026 ordinal, 202601 with 1,888 plays,
       so every current-season play is zero games back and
       0.5 ** (0 / h) = 1 for all five values of h.
  (ii) decay over ALL training games, prior season included. Not degenerate,
       but `rho` and `kappa` ALREADY parameterise the prior-versus-current
       trade-off -- the prior enters as pseudo-observations with response
       rho * theta_prev and weight kappa -- so (ii) would double-parameterise
       one quantity. It would also be borrowing B3's `games_back` formula,
       which the owner ruled may not be borrowed without independent
       justification, and there is none.

Choosing between them AFTER seeing which fits better is the thing a
preregistration exists to prevent. So the axis comes out for week 2, and
reinstating it needs a further amendment declaring its SCOPE, written before
any fit that has two or more current-season weeks to decay over.

WHAT AN AMENDMENT MAY AND MAY NOT DO. It may only REMOVE a search axis. It may
not add a value, widen a grid, move a threshold, change a comparator or alter
a promotion rule. `validate()` enforces that against the frozen
preregistration, which is not rewritten: the original is untouched on disk and
this file is additive.

THE MULTIPLICITY POINT, WHICH IS NOT MERELY COMPUTE. The declared space is
3 x 5 x 6 x 12 x 3 x 4 = 12,960 configurations, of which only 864 are
distinct: fifteen exact copies of each. "Within one standard error of the
best" over a space that is fifteen-sixteenths duplicates is a tie-break among
copies, and the most-shrunken rule would have been resolving ties on axes that
do nothing.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402
from nfl.research.oas1 import preregistration as PRE                  # noqa: E402

SPEC_VERSION = 'oas1-week2-preregistration-amendment-a1'
AMENDMENT_ID = 'A1'
PATH = _REPO / 'nfl/research/oas1/WEEK2_PREREG_AMENDMENT_A1.json'
CONFIG = _REPO / 'nfl/research/oas1/WEEK2_FIT_CONFIG.json'

DECLARED_BEFORE_ANY_WEEK2_FIT = True

#: The axes removed, each with the reason and the evidence for it.
REMOVED = {
    'half_life': {
        'reason': 'NO_DECLARED_SCOPE',
        'detail': ('the preregistration declares neither a current-season '
                   'scope nor an all-training scope. Under the current-season '
                   'reading the axis is exactly degenerate at week 2; under '
                   'the all-training reading it double-parameterises the '
                   'prior weight that rho and kappa already carry, and would '
                   'borrow B3\'s games_back formula without justification.'),
        'degeneracy_evidence': {
            'current_season_ordinals_in_training': [202601],
            'plays_at_202601': 1888,
            'games_back_for_every_current_season_play': 0,
            'weight_for_every_half_life': 1.0,
            'measured_from': 'nfl.research.oas1.frame.build over the three '
                             'governed blobs in WEEK2_FIT_CONFIG.inputs',
        },
        'reinstatement': ('a further amendment declaring the SCOPE, written '
                          'before any fit whose training set carries two or '
                          'more current-season weeks.'),
        'declared_grid': list(PRE.HALF_LIFE_GRID),
    },
    'min_plays': {
        'reason': 'REPORTING_ONLY_NO_PATH_INTO_THE_OBJECTIVE',
        'detail': ('the only declared statement is MIN_SAMPLE_RULES, a '
                   'reporting rule. Reporting cannot move an inner-fold '
                   'score, so all three values give an identical objective.'),
        'retained_as': {'role': 'reporting', 'fixed_value': 0,
                        'meaning': 'every unit is reported, with '
                                   'n_plays_current_season and '
                                   'prior_weight_effective attached'},
        'declared_grid': list(PRE.MIN_PLAYS_GRID),
    },
}

#: Tie-break with the two dead keys struck. Order of the survivors unchanged.
AMENDED_TIE_BREAK_ORDER = tuple(
    k for k in PRE.TIE_BREAK_ORDER
    if not any(k.endswith(dead) for dead in REMOVED))

LIVE_AXES = ('garbage_time', 'kappa', 'lambda', 'rho')

CODE_OK = 'OAS1_AMENDMENT_VALID'
CODE_BAD = 'OAS1_AMENDMENT_WOULD_WIDEN'


def effective_space() -> dict:
    """The search space after A1. Removal only."""
    return {
        'garbage_time': list(PRE.GARBAGE_TIME_SEARCH_SPACE),
        'kappa': list(PRE.KAPPA_GRID),
        'lambda': list(PRE.LAMBDA_GRID),
        'rho': list(PRE.RHO_GRID),
    }


def _size(space) -> int:
    n = 1
    for v in space.values():
        n *= len(v)
    return n


def declared_space() -> dict:
    cfg = json.loads(CONFIG.read_text())
    return cfg['search_spaces']


def validate() -> Outcome:
    """An amendment may only remove. Never add, widen, or loosen."""
    declared = declared_space()
    eff = effective_space()
    added_axes = sorted(set(eff) - set(declared))
    widened = []
    for axis, vals in eff.items():
        d = declared.get(axis)
        if d is None:
            continue
        # compare as strings: the config stores half_life as strings and the
        # numeric grids as numbers, and an amendment must not depend on that.
        if not set(map(str, vals)) <= set(map(str, d)):
            widened.append({'axis': axis,
                            'added': sorted(set(map(str, vals))
                                            - set(map(str, d)))})
    removed = sorted(set(declared) - set(eff))
    ev = {'spec_version': SPEC_VERSION, 'amendment': AMENDMENT_ID,
          'declared_axes': sorted(declared), 'effective_axes': sorted(eff),
          'removed_axes': removed,
          'declared_configurations': _size({k: v for k, v in
                                            declared.items()}),
          'effective_configurations': _size(eff),
          'amended_tie_break_order': list(AMENDED_TIE_BREAK_ORDER),
          'declared_before_any_week2_fit': DECLARED_BEFORE_ANY_WEEK2_FIT,
          'removal_only': True}
    if added_axes or widened:
        return Outcome.fail(
            CODE_BAD,
            f'amendment {AMENDMENT_ID} would add {added_axes} and widen '
            f'{widened}. An amendment may only remove an axis; adding one '
            f'after the preregistration is not an amendment, it is a new '
            f'experiment.', cause=Cause.GOVERNANCE,
            added_axes=added_axes, widened=widened, **ev)
    if removed != sorted(REMOVED):
        return Outcome.fail(
            CODE_BAD,
            f'the axes actually removed {removed} are not the axes the '
            f'amendment documents {sorted(REMOVED)}. A removal without a '
            f'written reason is an undeclared change.',
            cause=Cause.GOVERNANCE, **ev)
    dup = ev['declared_configurations'] // ev['effective_configurations']
    return Outcome.ok(
        CODE_OK, value=eff,
        detail=f'{AMENDMENT_ID}: {len(removed)} axis(es) removed '
               f'({", ".join(removed)}), {ev["declared_configurations"]:,} '
               f'declared configurations collapse to '
               f'{ev["effective_configurations"]:,} distinct ones '
               f'({dup}x duplication); nothing added or widened',
        duplication_factor=dup, removed=dict(REMOVED), **ev)


def write() -> pathlib.Path:
    o = validate()
    body = {'artifact': 'OAS1_WEEK2_PREREG_AMENDMENT_A1',
            'spec_version': SPEC_VERSION,
            'amendment': AMENDMENT_ID,
            'state': o.state.value, 'code': o.code, 'detail': o.detail,
            'declared_before_any_week2_fit': DECLARED_BEFORE_ANY_WEEK2_FIT,
            'preregistration_is_unmodified': True,
            'removed': REMOVED,
            'effective_search_space': effective_space(),
            'amended_tie_break_order': list(AMENDED_TIE_BREAK_ORDER),
            'evidence': {k: v for k, v in o.evidence.items()
                         if k not in ('cause', 'removed')},
            'may_not': ['add a search value', 'widen a grid',
                        'move a threshold', 'change a comparator',
                        'alter a promotion rule',
                        'be written after a Week-2 fit has been run']}
    PATH.write_text(json.dumps(body, indent=1, sort_keys=True))
    return PATH


def main() -> int:
    o = validate()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    p = write()
    print(f'written: {p}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
