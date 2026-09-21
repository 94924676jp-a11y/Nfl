"""The machine verdict. DEPLOYABLE / RESEARCH_ONLY / NO_SUPPORTED_EDGE.

WHY THIS FILE IS SHORT AND WHY IT MUST STAY SHORT

It is not a governance project. It is the one place where "is this usable?"
stops being a sentence a human remembers to write and becomes a function of
gates that already exist. Everything it knows, it is told; it computes
nothing about football.

THE THREE ANSWERS ARE DIFFERENT CLAIMS

    DEPLOYABLE          every required gate for that product scope passed.
    RESEARCH_ONLY       analyzable output exists, but a required readiness
                        gate failed or is unsupported.
                        -> the system is NOT READY to make the claim.
    NO_SUPPORTED_EDGE   the product path is valid enough to evaluate, and the
                        evidence does not justify a deployable edge.
                        -> the system IS ready, and finds nothing.

Collapsing the last two would let a broken model hide behind "no edge found",
so a scope reaches NO_SUPPORTED_EDGE only when every readiness gate has
already passed.

SCOPES ARE CUMULATIVE, EXACTLY AS IN THE ARTIFACT CONTRACT

Football is the root truth. A prop or DFS product inherits every football
gate and adds its own. Upstream validity flows downward; downstream
invalidity never flows upward -- an unvalidated calibrator says nothing about
the football simulation beneath it.

PROSE CANNOT OVERRIDE THIS

`render_status_line` takes the verdict and the blocking gate and nothing
else. There is no argument for a human note, an override flag or a severity
hint, because a function that accepts one will eventually be passed one.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (                  # noqa: E402
    Cause, Outcome, State)

SPEC_VERSION = 'nfl-product-verdict-1'

DEPLOYABLE = 'DEPLOYABLE'
RESEARCH_ONLY = 'RESEARCH_ONLY'
NO_SUPPORTED_EDGE = 'NO_SUPPORTED_EDGE'
VERDICTS = (DEPLOYABLE, RESEARCH_ONLY, NO_SUPPORTED_EDGE)

#: Gate results. Only PASS clears a gate. Everything else blocks, and the
#: distinctions exist so the report can say WHICH kind of not-passing it was.
PASS = 'PASS'
FAIL = 'FAIL'
BLOCKED = 'BLOCKED'
UNSUPPORTED = 'UNSUPPORTED'
NOT_EVALUATED = 'NOT_EVALUATED'
CLEARING = (PASS,)

SCOPE_PARENTS = {
    'football': (),
    'prop_product': ('football',),
    'dfs_product': ('football',),
}

#: gate -> the scope that owns it. A gate is REQUIRED by its own scope and by
#: every scope that descends from it.
GATE_SCOPE = {
    # --- football ---------------------------------------------------------
    'DRAW_ARTIFACT_INTEGRITY': 'football',
    'PLAYER_COVERAGE': 'football',
    'PER_CLUB_POSITION_COVERAGE': 'football',
    'PER_CLUB_LAYER_COVERAGE': 'football',
    'INACTIVE_APPLICATION': 'football',
    'ROLE_PLAUSIBILITY': 'football',
    'PARTICIPATION_COMPLETENESS': 'football',
    'OPPORTUNITY_CONSERVATION': 'football',
    'GAME_ACCOUNTING_COHERENCE': 'football',
    'DATA_FRESHNESS': 'football',
    'ROSTER_IDENTITY': 'football',
    'CURRENT_SEASON_INPUTS': 'football',
    'ARTIFACT_SEALED': 'football',
    'MODEL_MANIFEST_FROZEN': 'football',
    'PROMOTION_STATUS_VALID_FOR_SCOPE': 'football',
    # --- prop product -----------------------------------------------------
    'MARKET_SNAPSHOT_STATUS': 'prop_product',
    'PROP_CALIBRATION_STATUS': 'prop_product',
    # --- DFS product ------------------------------------------------------
    'DK_SCORING_PRESENT': 'dfs_product',
    'DFS_FIELD_MODEL_STATUS': 'dfs_product',
    'DST_SUPPORT_STATUS': 'dfs_product',
    # --- money ------------------------------------------------------------
    'REAL_MONEY_SCOPE_AUTHORIZED': 'football',
}

#: Gates that decide whether an EDGE is justified rather than whether the
#: system is READY. They are evaluated only after every readiness gate in the
#: scope has passed, and a failure among them yields NO_SUPPORTED_EDGE.
EDGE_GATES = {
    'prop_product': ('PROP_CALIBRATION_STATUS',),
    'dfs_product': ('DFS_FIELD_MODEL_STATUS',),
    'football': (),
}


def ancestors(scope: str) -> tuple[str, ...]:
    if scope not in SCOPE_PARENTS:
        raise KeyError(f'unknown scope {scope!r}; known {tuple(SCOPE_PARENTS)}')
    out, seen = [], set()

    def walk(s):
        if s in seen:
            return
        seen.add(s)
        for p in SCOPE_PARENTS.get(s, ()):
            walk(p)
        out.append(s)
    walk(scope)
    return tuple(out)


def required_gates(scope: str) -> tuple[str, ...]:
    chain = set(ancestors(scope))
    return tuple(g for g, own in GATE_SCOPE.items() if own in chain)


def from_outcome(o) -> str:
    """A governance Outcome mapped onto a gate result. PASS is the only clear."""
    if o is None:
        return NOT_EVALUATED
    st = getattr(o, 'state', None)
    if st is State.PASS:
        return PASS
    if st is State.FAIL:
        return FAIL
    if st is State.BLOCKED:
        return BLOCKED
    if st is State.NOT_APPLICABLE:
        return UNSUPPORTED
    if st is State.DEFERRED:
        return NOT_EVALUATED
    return NOT_EVALUATED


def assess(gate_results: dict, scope: str = 'football') -> Outcome:
    """The verdict for one product scope, and the gate that decides it.

    `gate_results` maps gate name -> one of the result constants, or a
    governance Outcome (mapped by `from_outcome`). A required gate that is
    ABSENT from the dict is NOT_EVALUATED, never assumed passing: a gate
    nobody ran is not a gate that passed.
    """
    req = required_gates(scope)
    resolved, blocking = {}, []
    for g in req:
        r = gate_results.get(g)
        r = r if isinstance(r, str) else from_outcome(r)
        if r not in (PASS, FAIL, BLOCKED, UNSUPPORTED, NOT_EVALUATED):
            r = NOT_EVALUATED
        resolved[g] = r

    edge = set(EDGE_GATES.get(scope, ()))
    readiness = [g for g in req if g not in edge]
    failed_readiness = [{'gate': g, 'result': resolved[g],
                         'owning_scope': GATE_SCOPE[g],
                         'is_upstream': GATE_SCOPE[g] != scope}
                        for g in readiness if resolved[g] not in CLEARING]
    failed_edge = [{'gate': g, 'result': resolved[g],
                    'owning_scope': GATE_SCOPE[g], 'is_upstream': False}
                   for g in sorted(edge) if resolved[g] not in CLEARING]

    if failed_readiness:
        verdict = RESEARCH_ONLY
        blocking = failed_readiness
        why = ('a required readiness gate did not pass, so the system is NOT '
               'READY to make this claim')
    elif failed_edge:
        verdict = NO_SUPPORTED_EDGE
        blocking = failed_edge
        why = ('every readiness gate passed and the evidence does not '
               'justify a deployable edge. The system IS ready, and finds '
               'nothing')
    else:
        verdict = DEPLOYABLE
        why = 'every required gate for this scope passed'

    upstream = sorted({b['owning_scope'] for b in blocking
                       if b.get('is_upstream')})
    value = {
        'spec_version': SPEC_VERSION, 'scope': scope,
        'scope_chain': list(ancestors(scope)),
        'VERDICT': verdict, 'why': why,
        'blocking_gates': blocking,
        'first_blocking_gate': blocking[0]['gate'] if blocking else None,
        'blocked_by_upstream_scopes': upstream,
        'gates': resolved,
        'n_required': len(req),
        'n_passed': sum(1 for v in resolved.values() if v == PASS),
    }
    # The Outcome state mirrors the verdict so a caller who reads only the
    # state cannot see success on a non-deployable product.
    if verdict == DEPLOYABLE:
        return Outcome.ok('PRODUCT_DEPLOYABLE', value=value, **value)
    return Outcome.blocked(
        f'PRODUCT_{verdict}',
        f'{scope}: {verdict}. {why}. First blocking gate: '
        f'{value["first_blocking_gate"]} = '
        f'{resolved.get(value["first_blocking_gate"])}.',
        cause=Cause.GOVERNANCE, value=value, **value)


def render_status_line(verdict_outcome) -> str:
    """The delivery note's first line, generated. Takes no prose argument.

    There is deliberately no parameter for a human note, an override or a
    severity hint. A function that accepts one will eventually be passed one.
    """
    # A blocked Outcome carries its payload in evidence, not in `.value`.
    # Reading only `.value` produced a None scope and crashed the very line
    # that is supposed to be un-skippable, which would have meant no status
    # line at all on exactly the boards that most need one.
    v = (verdict_outcome.value
         or (verdict_outcome.evidence or {}).get('value')
         or verdict_outcome.evidence or {})
    scope, verdict = v.get('scope'), v.get('VERDICT')
    g = v.get('first_blocking_gate')
    if verdict == DEPLOYABLE:
        return (f'{scope.upper()}: {verdict} '
                f'({v.get("n_passed")}/{v.get("n_required")} gates passed)')
    res = (v.get('gates') or {}).get(g)
    return (f'{scope.upper()}: {verdict} -- blocked by {g} = {res} '
            f'({v.get("n_passed")}/{v.get("n_required")} gates passed)')
