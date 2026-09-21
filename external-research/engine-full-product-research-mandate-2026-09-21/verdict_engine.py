"""Executable verdict precedence for the NFL forecasting engine product scopes.

REVISION 3. Unaccepted implementation specification. Running this on real gate
results is a future step; no gate has been evaluated. Synthetic tests are not
deployment-gate evidence. CANDIDATE_NOT_ACCEPTED_BASELINE / V2 NOT YET EARNED.

WHAT REVISION 2 GOT WRONG, ALL FOUR REPRODUCED BEFORE BEING FIXED

R2-1 and R2-2. RELEASE REASON CODES DID NOT PROPAGATE. `evaluate_scope`
    matched release codes against `scope.blocking_reason_codes` -- the scope's
    OWN list -- and nothing else. WEATHER_PROXY is blocking for F1 and appears
    in no other scope's list, so F1 went RESEARCH_ONLY while F2, F3, every prop
    family and every DFS scope built on top of it returned DEPLOYABLE. Same for
    ROUTES_PROXY on F2. Gates propagated transitively; the codes did not, and a
    blocker that stops a layer must stop what is built on that layer.

R2-3. A CALIBRATION FAILURE DID NOT REACH ITS OTHER CONSUMERS, AND REACHED
    SCOPES IT SHOULD NOT. CALIBRATION_INFEASIBLE:receiving_yards blocked every
    P1 family including rushing_yards, because matching was by code PREFIX with
    the entity thrown away -- and did not block D1, D2 or D5, because the DFS
    scopes do not list the code and do not depend on P1. Block XIX says every
    consumer reads the SAME weighted worlds, which is exactly why DFS is a
    consumer. Under-blocking and over-blocking in one defect.

R2-4. STATUSES WERE NOT VALIDATED BY GATE CLASS. The loop reacted to FAIL,
    NOT_EVALUATED and INSUFFICIENT_DATA; anything else fell through as
    clearing. So G-X-1 -- accounting invariants, EXACT_CORRECTNESS -- set to
    PASS_INCLUDES_ZERO left F1 DEPLOYABLE. A market-comparison status is
    meaningless on an exactness gate and must be rejected, not tolerated.

R2-5. GATE RESULTS WERE KEYED BY GATE ID ALONE, so one G-XX-2 result covered
    all thirteen prop families and one calibration result covered every
    release, game and player. The matrix itself says these gates are evaluated
    per prop family and per game; a dict keyed by gate id cannot express that.

R2-6. MARKET OUTPERFORMANCE WAS TREATED AS A BETTING EDGE. G-XX-2 compares
    the model against the de-vig market on a proper score, historically and in
    aggregate. That is a statement about the MODEL. It is not a statement that
    a particular price offered now has positive expected value. The two are
    separated here: G-XX-2 stays a scope gate, and offer-level EV moves
    downstream into `evaluate_offer`, which needs the price, the line, the
    settlement and push rules, the timestamps and its own uncertainty.

R2-7. SGP DEPENDED ON `P1.*`, every prop family, rather than on the legs a
    given SGP actually selects; and Showdown had no field, contest or
    portfolio path of its own, so D5 (contest simulation) descended only from
    Classic.

WHAT THIS FILE DOES NOT DO. It does not evaluate a real gate, promote a
candidate, change governance or declare readiness. Prose cannot override it.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))

VERDICTS = ("DEPLOYABLE", "RESEARCH_ONLY", "NO_SUPPORTED_EDGE")

# --- gate statuses ---------------------------------------------------------
PASS = "PASS"
FAIL = "FAIL"
NOT_EVALUATED = "NOT_EVALUATED"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
PASS_FAVORABLE = "PASS_FAVORABLE"
PASS_INCLUDES_ZERO = "PASS_INCLUDES_ZERO"

GATE_STATUSES = (PASS, PASS_FAVORABLE, PASS_INCLUDES_ZERO, FAIL,
                 NOT_EVALUATED, INSUFFICIENT_DATA)

#: WHICH STATUSES EACH GATE CLASS MAY CARRY AT ALL. A status outside its
#: class's domain is a category error, not a lenient pass: PASS_INCLUDES_ZERO
#: describes a confidence interval straddling zero, which an exactness check
#: does not have. Rejecting it is R2-4.
CLASS_PERMITTED: Dict[str, frozenset] = {
    "EXACT_CORRECTNESS": frozenset({PASS, FAIL, NOT_EVALUATED,
                                    INSUFFICIENT_DATA}),
    "PROVENANCE": frozenset({PASS, FAIL, NOT_EVALUATED, INSUFFICIENT_DATA}),
    "STATISTICAL_READINESS": frozenset({PASS, FAIL, NOT_EVALUATED,
                                        INSUFFICIENT_DATA}),
    "DIAGNOSTIC": frozenset({PASS, FAIL, NOT_EVALUATED, INSUFFICIENT_DATA}),
    "COMPONENT_INCLUSION": frozenset({PASS, FAIL, NOT_EVALUATED,
                                      INSUFFICIENT_DATA}),
    "MARKET_COMPARISON": frozenset({PASS_FAVORABLE, PASS_INCLUDES_ZERO, FAIL,
                                    NOT_EVALUATED, INSUFFICIENT_DATA}),
}

#: WHICH STATUS CLEARS. Exactly one per class, and never more.
CLASS_CLEARING: Dict[str, frozenset] = {
    "EXACT_CORRECTNESS": frozenset({PASS}),
    "PROVENANCE": frozenset({PASS}),
    "STATISTICAL_READINESS": frozenset({PASS}),
    "DIAGNOSTIC": frozenset({PASS}),
    "COMPONENT_INCLUSION": frozenset({PASS}),
    "MARKET_COMPARISON": frozenset({PASS_FAVORABLE}),
}

#: A component that does not earn inclusion is EXCLUDED from the release. The
#: scope is unaffected -- that is what the matrix's own pass_rule says -- so
#: these never block and never appear as a scope failure.
NON_BLOCKING_CLASSES = frozenset({"COMPONENT_INCLUSION"})

#: Gates whose evaluation unit makes a release-wide result meaningless. A
#: single G-XX-2 cannot speak for thirteen prop families (R2-5).
ENTITY_SCOPED_UNITS = frozenset({"prop family", "game", "player-game",
                                 "player-contest", "slate", "contest",
                                 "team-game", "opportunity", "entry",
                                 "record", "player-slate", "world",
                                 "scoring event", "output row", "attempt",
                                 "fact", "gate", "view", "event"})


@dataclass(frozen=True)
class Gate:
    gate_id: str
    gate_class: str
    reason_code_on_fail: str
    evaluation_unit: str = ""
    block: str = ""
    component: str = ""


@dataclass
class Scope:
    scope_id: str
    scope_kind: str
    depends_on: List[str]
    required_gates: List[str]
    blocking_codes: List[str]
    non_blocking_codes: List[str]
    market_gate: str

    @property
    def family(self) -> Optional[str]:
        """The prop family a P1 scope speaks for, or None."""
        if self.scope_id.startswith("P1."):
            return self.scope_id.split(".", 1)[1]
        return None

    @property
    def consumes_weighted_worlds(self) -> bool:
        """Whether this scope reads the shared weighted world set.

        G-XVIII-1 asserts that props, SGP and DFS share one world id set and
        one weight hash. A scope that is required to satisfy it is by
        definition a consumer of those weights, so a calibration that cannot
        be made feasible reaches it. This is the structural fact R2-3 missed;
        it is DERIVED from the matrix rather than hand-listed per scope, so a
        new consumer cannot be forgotten.
        """
        return "G-XVIII-1" in self.required_gates


@dataclass
class GateResult:
    """One gate's result, with the identity of what it was evaluated on.

    `scope_id`, `family`, `game_id`, `player_id` and `market_id` are the
    qualifiers. A qualifier left None means "this result does not speak to
    that axis", and a result matches a context only when every qualifier it
    DOES set agrees with the context. An unqualified result is therefore
    release-wide -- which is legitimate for a release-unit gate and is exactly
    the silent over-reach R2-5 names for a per-family one.
    """
    gate_id: str
    status: str
    release_id: Optional[str] = None
    scope_id: Optional[str] = None
    family: Optional[str] = None
    game_id: Optional[str] = None
    player_id: Optional[str] = None
    market_id: Optional[str] = None
    interval: Optional[Tuple[float, float]] = None
    n: Optional[int] = None
    evidence: Optional[str] = None

    QUALIFIERS = ("release_id", "scope_id", "family", "game_id", "player_id",
                  "market_id")

    @property
    def specificity(self) -> int:
        return sum(1 for q in self.QUALIFIERS if getattr(self, q) is not None)

    def matches(self, ctx: "Context") -> bool:
        for q in self.QUALIFIERS:
            mine = getattr(self, q)
            if mine is None:
                continue
            theirs = getattr(ctx, q, None)
            if theirs is None or theirs != mine:
                return False
        return True


@dataclass(frozen=True)
class Context:
    """What a scope is being evaluated ON."""
    scope_id: str
    release_id: Optional[str] = None
    family: Optional[str] = None
    game_id: Optional[str] = None
    player_id: Optional[str] = None
    market_id: Optional[str] = None


@dataclass
class ScopeVerdict:
    scope_id: str
    verdict: str
    reason_codes: List[str] = field(default_factory=list)
    display_codes: List[str] = field(default_factory=list)
    gates_evaluated: List[str] = field(default_factory=list)
    blocked_entities: List[str] = field(default_factory=list)
    excluded_components: List[str] = field(default_factory=list)
    upstream_blockers: List[str] = field(default_factory=list)


def _split(value: str) -> List[str]:
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def load_gates(path: str = os.path.join(HERE, "gate_matrix.csv")
               ) -> Dict[str, Gate]:
    with open(path, newline="") as f:
        return {
            r["gate_id"]: Gate(
                r["gate_id"], r["gate_class"], r["reason_code_on_fail"],
                r.get("evaluation_unit", ""), r.get("block", ""),
                r.get("component", ""))
            for r in csv.DictReader(f)
        }


def load_scopes(path: str = os.path.join(HERE,
                                         "scope_gate_dependencies.csv")
                ) -> Dict[str, Scope]:
    with open(path, newline="") as f:
        return {
            r["scope_id"]: Scope(
                r["scope_id"], r["scope_kind"],
                _split(r["depends_on_scopes"]), _split(r["required_gates"]),
                _split(r["blocking_reason_codes"]),
                _split(r["non_blocking_reason_codes"]),
                (r["market_comparison_gate"] or "").strip(),
            )
            for r in csv.DictReader(f)
        }


def _expand(dep: str, scopes: Dict[str, Scope],
            sgp_legs: Optional[Sequence[str]] = None) -> List[str]:
    """Resolve a dependency, including the SGP wildcard.

    `P1.*` in the CSV means "the legs this SGP selects", NOT every prop family
    in the catalogue (R2-7). With legs declared the wildcard resolves to them;
    with none declared it resolves to nothing and the caller raises
    SGP_LEGS_NOT_DECLARED, because an SGP whose legs nobody named cannot be
    evaluated against anything.
    """
    if dep.endswith("*"):
        prefix = dep[:-1]
        if sgp_legs is not None:
            return [s for s in sgp_legs if s.startswith(prefix) and s in scopes]
        return [s for s in scopes if s.startswith(prefix)]
    return [dep]


def dependency_closure(scope_id: str, scopes: Dict[str, Scope],
                       sgp_legs: Optional[Sequence[str]] = None,
                       seen: Optional[Set[str]] = None) -> List[str]:
    """Every scope this one rests on, transitively, nearest first."""
    seen = seen if seen is not None else set()
    out: List[str] = []
    for dep in scopes[scope_id].depends_on:
        for d in _expand(dep, scopes, sgp_legs):
            if d in seen or d not in scopes:
                continue
            seen.add(d)
            out.append(d)
            out.extend(dependency_closure(d, scopes, sgp_legs, seen))
    return out


def transitive_gates(scope_id: str, scopes: Dict[str, Scope],
                     seen: Optional[Set[str]] = None,
                     sgp_legs: Optional[Sequence[str]] = None) -> List[str]:
    """All gates required by a scope, including those of its dependencies."""
    seen = seen if seen is not None else set()
    if scope_id in seen:
        return []
    seen.add(scope_id)
    scope = scopes[scope_id]
    gates: List[str] = list(scope.required_gates)
    # A CONSUMER OF THE WEIGHTED WORLDS INHERITS THE CALIBRATION GATES. R2-3.
    if scope.consumes_weighted_worlds:
        gates.extend(["G-XIX-1", "G-XIX-2", "G-XIX-3", "G-XIX-4"])
    for dep in scope.depends_on:
        for d in _expand(dep, scopes, sgp_legs):
            if d in scopes:
                gates.extend(transitive_gates(d, scopes, seen, sgp_legs))
    ordered: List[str] = []
    for g in gates:
        if g not in ordered:
            ordered.append(g)
    return ordered


def _code_prefix(code: str) -> str:
    return code.split(":", 1)[0]


def _code_entity(code: str) -> Optional[str]:
    parts = code.split(":", 1)
    return parts[1] if len(parts) > 1 else None


#: Codes whose entity names a PROP FAMILY. A family-scoped blocker must reach
#: that family and the consumers of its weights, and must not touch an
#: unrelated family (the over-blocking half of R2-3).
FAMILY_SCOPED_CODES = frozenset({"CALIBRATION_INFEASIBLE"})


def _code_applies(code: str, scope: Scope, ctx: Context) -> bool:
    """Whether a release code bites THIS scope on THIS context."""
    prefix = _code_prefix(code)
    declared = prefix in scope.blocking_codes
    # A DERIVED CONSUMER IS STILL A CONSUMER. The DFS scopes do not list
    # CALIBRATION_INFEASIBLE in the shipped CSV, which is the under-blocking
    # half of R2-3. The declared map is reconciled alongside this, but the
    # derived rule stays as the backstop: a scope that is required to satisfy
    # G-XVIII-1 reads the same weight vector, and a new consumer added later
    # cannot be forgotten out of a hand-maintained list.
    if not declared and not (prefix in FAMILY_SCOPED_CODES
                             and scope.consumes_weighted_worlds):
        return False
    if prefix in FAMILY_SCOPED_CODES:
        entity = _code_entity(code)
        if entity is None:
            return True                       # unqualified: bites everything
        if scope.family is not None:
            return scope.family == entity
        # A consumer of the shared weights is bitten by any family's
        # infeasibility, because it reads the same weight vector.
        return scope.consumes_weighted_worlds
    return True


def resolve_result(gate_id: str, gate: Gate, ctx: Context,
                   results: Sequence[GateResult]
                   ) -> Tuple[str, Optional[GateResult], List[str]]:
    """The most specific applicable result for this gate in this context.

    Returns (status, result, notes). Ties at equal specificity with different
    statuses are AMBIGUOUS and do not clear: two results disagreeing about the
    same thing is not a state anything should be certified against.
    """
    notes: List[str] = []
    applicable = [r for r in results if r.gate_id == gate_id and r.matches(ctx)]
    if not applicable:
        return NOT_EVALUATED, None, notes
    best = max(r.specificity for r in applicable)
    top = [r for r in applicable if r.specificity == best]
    if len({r.status for r in top}) > 1:
        notes.append(f"AMBIGUOUS_GATE_RESULT:{gate_id}")
        return NOT_EVALUATED, None, notes
    chosen = top[0]
    if (chosen.specificity == 0
            and gate.evaluation_unit in ENTITY_SCOPED_UNITS):
        notes.append(f"GATE_RESULT_UNSCOPED:{gate_id}")
    return chosen.status, chosen, notes


def normalise_results(gate_results) -> List[GateResult]:
    """Accept the legacy {gate_id: status} mapping or a list of GateResult."""
    if gate_results is None:
        return []
    if isinstance(gate_results, dict):
        return [GateResult(gate_id=g, status=s) for g, s in
                gate_results.items()]
    return list(gate_results)


def evaluate_scope(
    scope_id: str,
    gate_results,
    release_codes: Iterable[str],
    gates: Dict[str, Gate],
    scopes: Dict[str, Scope],
    ctx: Optional[Context] = None,
    strict_scoping: bool = False,
    sgp_legs: Optional[Sequence[str]] = None,
) -> ScopeVerdict:
    scope = scopes[scope_id]
    ctx = ctx or Context(scope_id=scope_id, family=scope.family)
    results = normalise_results(gate_results)
    required = transitive_gates(scope_id, scopes, sgp_legs=sgp_legs)
    out = ScopeVerdict(scope_id=scope_id, verdict="RESEARCH_ONLY",
                       gates_evaluated=required)

    # An SGP that has not named its legs has nothing to be evaluated against.
    if any(d.endswith("*") for d in scope.depends_on) and sgp_legs is None:
        out.reason_codes.append("SGP_LEGS_NOT_DECLARED")

    for code in release_codes:
        prefix = _code_prefix(code)
        if _code_applies(code, scope, ctx):
            out.reason_codes.append(code)
            ent = _code_entity(code)
            if ent:
                out.blocked_entities.append(ent)
        elif prefix in scope.non_blocking_codes:
            out.display_codes.append(code)

    for gate_id in required:
        gate = gates[gate_id]
        status, _res, notes = resolve_result(gate_id, gate, ctx, results)
        if status not in GATE_STATUSES:
            out.reason_codes.append(
                f"INVALID_GATE_STATUS:{gate_id}:{status}")
            continue
        # STATUS MUST BE LEGAL FOR THE CLASS BEFORE IT CAN CLEAR. R2-4.
        permitted = CLASS_PERMITTED.get(gate.gate_class)
        if permitted is not None and status not in permitted:
            out.reason_codes.append(
                f"GATE_STATUS_INVALID_FOR_CLASS:{gate_id}:"
                f"{gate.gate_class}:{status}")
            continue
        if gate.gate_class in NON_BLOCKING_CLASSES:
            if status not in CLASS_CLEARING[gate.gate_class]:
                out.excluded_components.append(
                    f"COMPONENT_NOT_INCLUDED:{gate_id}")
                out.display_codes.append(f"COMPONENT_NOT_INCLUDED:{gate_id}")
            continue
        for n in notes:
            (out.reason_codes if strict_scoping else out.display_codes
             ).append(n)
        if gate_id == scope.market_gate:
            continue                       # decided after readiness, below
        clearing = CLASS_CLEARING.get(gate.gate_class, frozenset({PASS}))
        if status in clearing:
            continue
        if status == FAIL:
            code = gate.reason_code_on_fail
            out.reason_codes.append(
                code if (":" in code or code in ("NO_OUTPUT",
                                                 "RELEASE_UNPROVEN"))
                else f"GATE_FAIL:{gate_id}")
        elif status == NOT_EVALUATED:
            out.reason_codes.append(f"GATE_NOT_EVALUATED:{gate_id}")
        elif status == INSUFFICIENT_DATA:
            out.reason_codes.append(f"GATE_INSUFFICIENT_DATA:{gate_id}")
        else:
            out.reason_codes.append(f"GATE_NOT_CLEARING:{gate_id}:{status}")

    if out.reason_codes:
        out.verdict = "RESEARCH_ONLY"
        return out

    if scope.market_gate:
        gate = gates[scope.market_gate]
        status, _res, _n = resolve_result(scope.market_gate, gate, ctx,
                                          results)
        if status == PASS_FAVORABLE:
            out.verdict = "DEPLOYABLE"
        elif status == PASS_INCLUDES_ZERO:
            out.verdict = "NO_SUPPORTED_EDGE"
            out.reason_codes.append("MARKET_INTERVAL_INCLUDES_ZERO")
        else:
            out.verdict = "RESEARCH_ONLY"
            out.reason_codes.append(
                f"GATE_{'FAIL' if status == FAIL else 'NOT_EVALUATED'}:"
                f"{scope.market_gate}")
        return out

    out.verdict = "DEPLOYABLE"
    return out


def _root_cause(scope_id: str, verdicts: Dict[str, ScopeVerdict],
                scopes: Dict[str, Scope],
                sgp_legs: Optional[Sequence[str]] = None,
                seen: Optional[Set[str]] = None) -> str:
    """The first real failure under `scope_id`, not a propagation marker.

    A scope blocked only because something beneath it is blocked has no
    reason of its own. Reporting its verdict as the cause tells a reader
    nothing, so this walks down to the nearest scope that failed on a gate or
    a reason code and returns that.
    """
    seen = seen if seen is not None else set()
    if scope_id in seen:
        return "DEPENDENCY_CYCLE"
    seen.add(scope_id)
    v = verdicts.get(scope_id)
    if v is None:
        return "UNKNOWN_SCOPE"
    own = [c for c in v.reason_codes
           if not c.startswith("UPSTREAM_NOT_DEPLOYABLE:")]
    if own:
        return own[0]
    for dep in scopes[scope_id].depends_on:
        for d in _expand(dep, scopes, sgp_legs):
            if d in verdicts and verdicts[d].verdict != "DEPLOYABLE":
                return _root_cause(d, verdicts, scopes, sgp_legs, seen)
    return v.verdict


def evaluate_release(
    gate_results,
    release_codes: Iterable[str],
    ctx_by_scope: Optional[Dict[str, Context]] = None,
    strict_scoping: bool = False,
    sgp_legs: Optional[Sequence[str]] = None,
    gates: Optional[Dict[str, Gate]] = None,
    scopes: Optional[Dict[str, Scope]] = None,
) -> Dict[str, ScopeVerdict]:
    """Every scope's verdict, with upstream blockers propagated downward.

    TWO PASSES, AND THE SECOND IS THE FIX FOR R2-1 AND R2-2. The first pass
    decides each scope on its own gates and its own applicable codes. The
    second walks the dependency graph and demotes any scope resting on one
    that is not DEPLOYABLE, carrying the upstream reason with it.

    THE DIRECTION IS ONE-WAY, WHICH IS WHAT KEEPS THE IDENTITY AXES SEPARATE.
    Upstream invalidity flows DOWN. A salary-identity failure blocks the DFS
    scopes that consume salary and never touches the football scopes beneath
    them, because those football scopes are upstream and nothing flows up.
    """
    gates = gates or load_gates()
    scopes = scopes or load_scopes()
    codes = list(release_codes)
    ctx_by_scope = ctx_by_scope or {}

    # COMPONENT INCLUSION IS A RELEASE-LEVEL FACT, NOT A SCOPE GATE. The
    # matrix's own pass rule says a component that does not earn inclusion is
    # excluded and "the football scope is unaffected", which is why these
    # gates appear in no scope's required list. They still have to be
    # REPORTED, or a release silently ships without a component nobody
    # mentioned.
    results_l = normalise_results(gate_results)
    excluded: List[str] = []
    for gid, g in gates.items():
        if g.gate_class != "COMPONENT_INCLUSION":
            continue
        st, _r, _n = resolve_result(gid, g, Context(scope_id="__release__"),
                                    results_l)
        if st not in CLASS_CLEARING["COMPONENT_INCLUSION"]:
            excluded.append(f"COMPONENT_NOT_INCLUDED:{gid}")

    out: Dict[str, ScopeVerdict] = {}
    for sid in scopes:
        out[sid] = evaluate_scope(
            sid, gate_results, codes, gates, scopes,
            ctx=ctx_by_scope.get(sid), strict_scoping=strict_scoping,
            sgp_legs=sgp_legs)

    for v in out.values():
        for e in excluded:
            if e not in v.excluded_components:
                v.excluded_components.append(e)
                v.display_codes.append(e)

    for sid, scope in scopes.items():
        v = out[sid]
        if v.verdict == "RESEARCH_ONLY" and not v.upstream_blockers:
            pass                              # already blocked on its own
        for dep in dependency_closure(sid, scopes, sgp_legs):
            up = out.get(dep)
            if up is None or up.verdict == "DEPLOYABLE":
                continue
            # NAME THE ROOT CAUSE, NOT THE CHAIN AND NOT THE VERDICT.
            # Quoting the upstream's first reason code verbatim nests each
            # hop inside the next, so D5 carried a marker with six colons and
            # the cause buried at the end. Taking only its own reasons is not
            # enough either: a scope that is purely a victim of propagation
            # has none, and the marker degrades to "RESEARCH_ONLY", which
            # names nothing. `_root_cause` walks to the first scope that
            # actually failed on something.
            root = _root_cause(dep, out, scopes, sgp_legs)
            marker = f"UPSTREAM_NOT_DEPLOYABLE:{dep}:{root}"
            if marker not in v.upstream_blockers:
                v.upstream_blockers.append(marker)
                v.reason_codes.append(marker)
            for ent in up.blocked_entities:
                if ent not in v.blocked_entities:
                    v.blocked_entities.append(ent)
        if v.upstream_blockers and v.verdict != "RESEARCH_ONLY":
            v.verdict = "RESEARCH_ONLY"

    for sid, v in out.items():
        if scopes[sid].scope_kind == "NON_BETTING" \
                and v.verdict == "NO_SUPPORTED_EDGE":
            raise AssertionError(
                f"non-betting scope {sid} cannot be NO_SUPPORTED_EDGE")
        if v.verdict not in VERDICTS:
            raise AssertionError(f"{sid} produced {v.verdict!r}")
    return out


if __name__ == "__main__":
    import json
    import sys

    payload = (json.load(sys.stdin) if not sys.stdin.isatty()
               else {"gate_results": {}, "release_codes": []})
    result = evaluate_release(payload.get("gate_results", {}),
                              payload.get("release_codes", []),
                              sgp_legs=payload.get("sgp_legs"))
    print(json.dumps({k: v.__dict__ for k, v in result.items()}, indent=1))
