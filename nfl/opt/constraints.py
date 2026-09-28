#!/usr/bin/env python3.12
"""Every optimiser constraint, declared once, compiled explicitly, and verified on the answer.

WHY THIS MODULE EXISTS

`solve()` accepted `required_players`, passed it down, and the enumerator took the parameter and
never read it. The constrained solve returned the UNCONSTRAINED lineup and labelled it
PROVEN_OPTIMAL. A proof was attached to a different question, and the suite did not catch it because
nothing exercised the argument.

Fixing that one call site is not the fix. The fix is that a constraint cannot be silently dropped,
by construction, so this module makes the drop detectable rather than trusting the solver:

    REQUESTED   what the caller asked for
    COMPILED    what the chosen solve path will actually enforce
    VERIFIED    what was checked against the returned roster, player by player

Those three sets must reconcile. REQUESTED minus COMPILED is a dropped constraint. COMPILED minus
VERIFIED is an unchecked claim. Either one makes the solve a FAILURE, and neither can be reached by
forgetting to write a check, because the reconciliation is over a registry rather than over code
paths.

THE OPTIMALITY RULE THAT FOLLOWS

PROVEN_OPTIMAL means optimal under the COMPLETE enforced constraint set. A solve that satisfies a
constraint by luck is not proven, and a solve that gave up looking is not proven either. So the only
statuses available are:

    PROVEN_OPTIMAL   exhaustive over the enforced set, and every constraint verified
    BEST_KNOWN       a satisfying lineup was found but the search budget ended before exhaustion
    HEURISTIC        nothing here produces this; it exists so the vocabulary cannot be borrowed

A constraint this module does not know how to enforce is an ERROR, never a no-op. Portfolio-level
requests such as exposure caps are refused on a single solve with a named code, because a single
lineup cannot satisfy a constraint about forty-eight of them.
"""
from __future__ import annotations

import collections
import pathlib
import sys
from typing import Any, Callable, Mapping

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SALARY_CAP = 50000
SALARY_STEP = 100

# How a constraint is enforced. This is the field that makes dropping one impossible: a constraint
# with no enforcement route cannot be compiled, and an uncompiled request fails the reconciliation.
NATIVE_DP = 'NATIVE_DP'            # the salary dynamic program enforces it directly
ENUMERATED = 'ENUMERATED'          # exact enumeration in value order, filtered by a predicate
PORTFOLIO_ONLY = 'PORTFOLIO_ONLY'  # meaningless for one lineup; refused here


class Spec:
    """One constraint type: how it is enforced, and how a roster is checked against it."""

    def __init__(self, name, route, verify: Callable, describe: Callable,
                 is_active: Callable | None = None):
        self.name = name
        self.route = route
        self.verify = verify
        self.describe = describe
        self._is_active = is_active

    def active(self, value) -> bool:
        if self._is_active is not None:
            return bool(self._is_active(value))
        return value not in (None, (), [], {}, set(), frozenset(), 0, False)


def _ids(lineup):
    return set(lineup)


def _v_salary(lineup, idx, value):
    return sum(idx[i]['salary'] for i in lineup) <= value


def _v_required(lineup, idx, value):
    return set(value) <= _ids(lineup)


def _v_banned(lineup, idx, value):
    return not (set(value) & _ids(lineup))


def _v_excluded(lineup, idx, value):
    return frozenset(lineup) not in {frozenset(x) for x in value}


def _v_shape(lineup, idx, value):
    counts = collections.Counter(idx[i]['position'] for i in lineup)
    return any(dict(counts) == dict(s) for s in value)


def _v_max_from_team(lineup, idx, value):
    counts = collections.Counter(idx[i].get('team') for i in lineup
                                 if idx[i].get('team') is not None)
    return not counts or max(counts.values()) <= value


def _v_qb_stack_min(lineup, idx, value):
    qbs = [i for i in lineup if idx[i]['position'] == 'QB']
    if not qbs:
        return False
    club = idx[qbs[0]].get('team')
    if club is None:
        return False
    n = sum(1 for i in lineup
            if i != qbs[0] and idx[i].get('team') == club
            and idx[i]['position'] in ('WR', 'TE'))
    return n >= value


def _v_bring_back_min(lineup, idx, value):
    qbs = [i for i in lineup if idx[i]['position'] == 'QB']
    if not qbs:
        return False
    opp = idx[qbs[0]].get('opponent')
    if opp is None:
        return False
    n = sum(1 for i in lineup if idx[i].get('team') == opp
            and idx[i]['position'] in ('WR', 'TE', 'RB'))
    return n >= value


def _v_forbid_dst_against_qb_opp(lineup, idx, value):
    if not value:
        return True
    qbs = [i for i in lineup if idx[i]['position'] == 'QB']
    if not qbs:
        return False
    opp = idx[qbs[0]].get('opponent')
    dsts = [i for i in lineup if idx[i]['position'] == 'DST']
    return all(idx[d].get('team') != opp for d in dsts)


def _v_max_ownership_sum(lineup, idx, value):
    own = [idx[i].get('ownership') for i in lineup]
    if any(o is None for o in own):
        return None  # cannot be verified: the pool does not carry ownership
    return sum(own) <= value


def _v_min_salary(lineup, idx, value):
    return sum(idx[i]['salary'] for i in lineup) >= value


REGISTRY: dict[str, Spec] = {
    'salary_cap': Spec('salary_cap', NATIVE_DP, _v_salary,
                       lambda v: f'total salary at most {v}',
                       is_active=lambda v: v is not None),
    'min_salary': Spec('min_salary', ENUMERATED, _v_min_salary,
                       lambda v: f'total salary at least {v}'),
    'shape': Spec('shape', NATIVE_DP, _v_shape,
                  lambda v: f'one of {len(v)} legal position shapes',
                  is_active=lambda v: bool(v)),
    'required_players': Spec('required_players', NATIVE_DP, _v_required,
                             lambda v: f'must include {sorted(v)}'),
    'locked_players': Spec('locked_players', NATIVE_DP, _v_required,
                           lambda v: f'locked in: {sorted(v)}'),
    'banned_players': Spec('banned_players', NATIVE_DP, _v_banned,
                           lambda v: f'must exclude {sorted(v)}'),
    'excluded_lineups': Spec('excluded_lineups', ENUMERATED, _v_excluded,
                             lambda v: f'{len(v)} exact lineups forbidden'),
    'max_from_team': Spec('max_from_team', ENUMERATED, _v_max_from_team,
                          lambda v: f'at most {v} players from any one club'),
    'qb_stack_min': Spec('qb_stack_min', ENUMERATED, _v_qb_stack_min,
                         lambda v: f'at least {v} pass catcher(s) from the quarterback\'s club'),
    'bring_back_min': Spec('bring_back_min', ENUMERATED, _v_bring_back_min,
                           lambda v: f'at least {v} player(s) from the quarterback\'s opponent'),
    'forbid_dst_against_qb_opp': Spec('forbid_dst_against_qb_opp', ENUMERATED,
                                      _v_forbid_dst_against_qb_opp,
                                      lambda v: 'no defence facing the quarterback\'s opponent'),
    'max_ownership_sum': Spec('max_ownership_sum', ENUMERATED, _v_max_ownership_sum,
                              lambda v: f'summed field ownership at most {v}'),
    'max_exposure': Spec('max_exposure', PORTFOLIO_ONLY, lambda *a: None,
                         lambda v: f'no player in more than {v} of the portfolio'),
    'min_unique_players': Spec('min_unique_players', PORTFOLIO_ONLY, lambda *a: None,
                               lambda v: f'at least {v} distinct players across the portfolio'),
}


class ConstraintSet:
    """A request, its compilation, and the verification of a returned roster against both."""

    def __init__(self, requested: Mapping[str, Any]):
        self.requested = {k: v for k, v in requested.items()
                          if k in REGISTRY and REGISTRY[k].active(v)}
        self.unknown = sorted(set(requested) - set(REGISTRY))
        self.compiled: dict[str, Any] = {}
        self.route: dict[str, str] = {}
        self.verified: dict[str, bool] = {}
        self.unverifiable: dict[str, str] = {}

    # -- compilation ---------------------------------------------------------------------
    def compile(self, native_supported: tuple[str, ...]) -> Outcome:
        """Decide how each requested constraint will be enforced, or refuse to proceed."""
        if self.unknown:
            return Outcome.fail(
                'CONSTRAINT_UNKNOWN',
                f'constraints not in the registry: {self.unknown}',
                unknown=self.unknown, known=sorted(REGISTRY),
                note=('an unrecognised constraint is an error, never a no-op. Silently ignoring '
                      'one is the defect this module exists to make impossible.'))
        portfolio = [k for k in self.requested if REGISTRY[k].route == PORTFOLIO_ONLY]
        if portfolio:
            return Outcome.fail(
                'CONSTRAINT_IS_PORTFOLIO_LEVEL',
                f'{portfolio} cannot be enforced on a single lineup',
                portfolio_level=portfolio,
                note=('a single roster cannot satisfy a constraint about a set of rosters. These '
                      'belong to portfolio construction, and accepting them here would look like '
                      'enforcement while doing nothing.'))
        for k in self.requested:
            spec = REGISTRY[k]
            self.route[k] = NATIVE_DP if (spec.route == NATIVE_DP and k in native_supported) \
                else ENUMERATED
            self.compiled[k] = self.requested[k]
        dropped = sorted(set(self.requested) - set(self.compiled))
        if dropped:
            return Outcome.fail('CONSTRAINT_DROPPED_AT_COMPILE', f'{dropped} were not compiled',
                                dropped=dropped)
        return Outcome.ok('CONSTRAINTS_COMPILED', value={
            'n': len(self.compiled),
            'by_route': dict(collections.Counter(self.route.values())),
        })

    def enumerated(self) -> dict[str, Any]:
        return {k: v for k, v in self.compiled.items() if self.route.get(k) == ENUMERATED}

    def satisfies(self, lineup, idx) -> bool:
        """Predicate for the enumeration: does this roster meet every ENUMERATED constraint?"""
        for k, v in self.enumerated().items():
            if REGISTRY[k].verify(lineup, idx, v) is False:
                return False
        return True

    # -- verification --------------------------------------------------------------------
    def verify_all(self, lineup, idx) -> Outcome:
        """Check the returned roster against every compiled constraint, one at a time."""
        failures, unver = [], {}
        for k, v in self.compiled.items():
            res = REGISTRY[k].verify(lineup, idx, v)
            if res is None:
                unver[k] = 'NOT_VERIFIABLE_FROM_THIS_POOL'
                continue
            self.verified[k] = bool(res)
            if not res:
                failures.append({'constraint': k, 'requirement': REGISTRY[k].describe(v)})
        self.unverifiable = unver
        missing = sorted(set(self.compiled) - set(self.verified) - set(unver))
        if failures or missing or unver:
            return Outcome.fail(
                'CONSTRAINT_VIOLATED_OR_UNVERIFIED',
                f'{len(failures)} violated, {len(missing)} unchecked, {len(unver)} unverifiable',
                violated=failures, unchecked=missing, unverifiable=unver,
                note=('a constraint that cannot be checked against the roster cannot be claimed as '
                      'enforced, so this fails rather than reporting an optimum.'))
        return Outcome.ok('CONSTRAINTS_VERIFIED', value={'n': len(self.verified)})

    # -- the manifest --------------------------------------------------------------------
    def manifest(self, exhaustive: bool, search_note: str = '') -> dict:
        # VERIFIED means verified TRUE. Comparing the KEYS of self.verified let a constraint that
        # had been checked and FAILED still reconcile, because it had been checked -- the same
        # silent-success shape this module exists to remove, one level up in the bookkeeping. A
        # violation now breaks reconciliation on its own.
        req, comp = set(self.requested), set(self.compiled)
        ver = {k for k, v in self.verified.items() if v}
        violated = sorted(k for k, v in self.verified.items() if not v)
        reconciles = (req == comp == ver) and not violated and not self.unverifiable
        return {
            'requested_constraints': {k: REGISTRY[k].describe(v)
                                      for k, v in sorted(self.requested.items())},
            'compiled_constraints': {k: {'requirement': REGISTRY[k].describe(v),
                                         'route': self.route[k]}
                                     for k, v in sorted(self.compiled.items())},
            'verified_constraints': {k: self.verified[k] for k in sorted(self.verified)},
            'violated_constraints': violated,
            'requested_not_compiled': sorted(req - comp),
            'compiled_not_verified': sorted(comp - ver),
            'unverifiable': self.unverifiable,
            'RECONCILES': reconciles,
            'search_was_exhaustive': exhaustive,
            'search_note': search_note,
            'OPTIMALITY_MEANING': (
                'PROVEN_OPTIMAL is relative to the COMPLETE compiled constraint set above and '
                'nothing else. It requires the three sets to reconcile AND the search to have been '
                'exhaustive rather than budget-limited.'),
        }


def status_for(manifest: dict) -> str:
    from nfl.opt import exact
    if not manifest['RECONCILES']:
        return 'INVALID'
    return exact.PROVEN_OPTIMAL if manifest['search_was_exhaustive'] else exact.BEST_KNOWN


def index(pool) -> dict:
    """id -> row, with the fields the verifiers need."""
    return {p['id']: p for p in pool}
