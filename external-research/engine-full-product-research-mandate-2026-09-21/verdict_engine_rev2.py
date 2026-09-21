"""Executable verdict precedence for the NFL forecasting engine product scopes.

Reads `gate_matrix.csv` and `scope_gate_dependencies.csv` from this folder and a
set of gate results plus release-level reason codes, and emits exactly one of the
three mandate verdicts per scope: DEPLOYABLE, RESEARCH_ONLY, NO_SUPPORTED_EDGE.

Rules implemented (Section 4.3 and 5.2 of the research packet):
1. Verdict domain is the three values only. NON_BETTING scopes cannot be
   NO_SUPPORTED_EDGE.
2. Required gates are collected transitively through `depends_on_scopes`.
   A wildcard dependency such as `P1.*` expands to every scope with that prefix.
3. Any required gate with status FAIL, NOT_EVALUATED or INSUFFICIENT_DATA yields
   RESEARCH_ONLY with the gate's typed reason code.
4. Release-level reason codes (for example RELEASE_UNPROVEN, STALE_INPUT:<src>,
   IDENTITY_UNRESOLVED:<platform>:<name>) yield RESEARCH_ONLY only for scopes
   whose `blocking_reason_codes` list contains the code's prefix. Codes in
   `non_blocking_reason_codes` are attached for display but do not demote.
5. If all required gates PASS and no blocking code applies, a scope with no
   `market_comparison_gate` is DEPLOYABLE. A scope with a market comparison gate
   is DEPLOYABLE when that gate's result is PASS_FAVORABLE and NO_SUPPORTED_EDGE
   when it is PASS_INCLUDES_ZERO (the statistical work passed but the interval
   includes zero).
6. Prose never overrides the output. This module is deterministic and has no
   knowledge of prose.

Gate statuses accepted: PASS, PASS_FAVORABLE, PASS_INCLUDES_ZERO, FAIL,
NOT_EVALUATED, INSUFFICIENT_DATA.

Research completion does not constitute model acceptance. Running this engine
on real gate results is a future step; no gate has been evaluated in this
session.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set

HERE = os.path.dirname(os.path.abspath(__file__))
VERDICTS = ("DEPLOYABLE", "RESEARCH_ONLY", "NO_SUPPORTED_EDGE")
GATE_STATUSES = (
    "PASS",
    "PASS_FAVORABLE",
    "PASS_INCLUDES_ZERO",
    "FAIL",
    "NOT_EVALUATED",
    "INSUFFICIENT_DATA",
)


@dataclass
class Gate:
    gate_id: str
    gate_class: str
    reason_code_on_fail: str


@dataclass
class Scope:
    scope_id: str
    scope_kind: str
    depends_on: List[str]
    required_gates: List[str]
    blocking_codes: List[str]
    non_blocking_codes: List[str]
    market_gate: str


@dataclass
class ScopeVerdict:
    scope_id: str
    verdict: str
    reason_codes: List[str] = field(default_factory=list)
    display_codes: List[str] = field(default_factory=list)
    gates_evaluated: List[str] = field(default_factory=list)


def _split(value: str) -> List[str]:
    return [v for v in value.split(";") if v]


def load_gates(path: str = os.path.join(HERE, "gate_matrix.csv")) -> Dict[str, Gate]:
    with open(path, newline="") as f:
        return {
            r["gate_id"]: Gate(r["gate_id"], r["gate_class"], r["reason_code_on_fail"])
            for r in csv.DictReader(f)
        }


def load_scopes(path: str = os.path.join(HERE, "scope_gate_dependencies.csv")) -> Dict[str, Scope]:
    with open(path, newline="") as f:
        return {
            r["scope_id"]: Scope(
                r["scope_id"],
                r["scope_kind"],
                _split(r["depends_on_scopes"]),
                _split(r["required_gates"]),
                _split(r["blocking_reason_codes"]),
                _split(r["non_blocking_reason_codes"]),
                r["market_comparison_gate"],
            )
            for r in csv.DictReader(f)
        }


def _expand(dep: str, scopes: Dict[str, Scope]) -> List[str]:
    if dep.endswith("*"):
        prefix = dep[:-1]
        return [s for s in scopes if s.startswith(prefix)]
    return [dep]


def transitive_gates(scope_id: str, scopes: Dict[str, Scope], seen: Set[str] | None = None) -> List[str]:
    """All gates required by a scope, including those of its dependency scopes."""
    seen = seen if seen is not None else set()
    if scope_id in seen:
        return []
    seen.add(scope_id)
    scope = scopes[scope_id]
    gates: List[str] = list(scope.required_gates)
    for dep in scope.depends_on:
        for d in _expand(dep, scopes):
            gates.extend(transitive_gates(d, scopes, seen))
    ordered: List[str] = []
    for g in gates:
        if g not in ordered:
            ordered.append(g)
    return ordered


def _code_prefix(code: str) -> str:
    return code.split(":", 1)[0]


def evaluate_scope(
    scope_id: str,
    gate_results: Dict[str, str],
    release_codes: Iterable[str],
    gates: Dict[str, Gate],
    scopes: Dict[str, Scope],
) -> ScopeVerdict:
    scope = scopes[scope_id]
    required = transitive_gates(scope_id, scopes)
    out = ScopeVerdict(scope_id=scope_id, verdict="RESEARCH_ONLY", gates_evaluated=required)

    for code in release_codes:
        prefix = _code_prefix(code)
        if prefix in scope.blocking_codes:
            out.reason_codes.append(code)
        elif prefix in scope.non_blocking_codes:
            out.display_codes.append(code)

    exact_first = sorted(required, key=lambda g: 0 if gates[g].gate_class == "EXACT_CORRECTNESS" else 1)
    for gate_id in exact_first:
        status = gate_results.get(gate_id, "NOT_EVALUATED")
        if status not in GATE_STATUSES:
            raise ValueError(f"unknown gate status {status} for {gate_id}")
        if gate_id == scope.market_gate:
            continue
        if status == "FAIL":
            code = gates[gate_id].reason_code_on_fail
            out.reason_codes.append(code if ":" in code or code in ("NO_OUTPUT", "RELEASE_UNPROVEN") else f"GATE_FAIL:{gate_id}")
        elif status == "NOT_EVALUATED":
            out.reason_codes.append(f"GATE_NOT_EVALUATED:{gate_id}")
        elif status == "INSUFFICIENT_DATA":
            out.reason_codes.append(f"GATE_INSUFFICIENT_DATA:{gate_id}")

    if out.reason_codes:
        out.verdict = "RESEARCH_ONLY"
        return out

    if scope.market_gate:
        status = gate_results.get(scope.market_gate, "NOT_EVALUATED")
        if status == "PASS_FAVORABLE":
            out.verdict = "DEPLOYABLE"
        elif status == "PASS_INCLUDES_ZERO":
            out.verdict = "NO_SUPPORTED_EDGE"
            out.reason_codes.append("MARKET_INTERVAL_INCLUDES_ZERO")
        else:
            out.verdict = "RESEARCH_ONLY"
            out.reason_codes.append(f"GATE_{'FAIL' if status == 'FAIL' else 'NOT_EVALUATED'}:{scope.market_gate}")
        return out

    out.verdict = "DEPLOYABLE"
    if scope.scope_kind == "NON_BETTING" and out.verdict == "NO_SUPPORTED_EDGE":
        raise AssertionError("non-betting scope cannot be NO_SUPPORTED_EDGE")
    return out


def evaluate_release(gate_results: Dict[str, str], release_codes: Iterable[str]) -> Dict[str, ScopeVerdict]:
    gates, scopes = load_gates(), load_scopes()
    codes = list(release_codes)
    return {sid: evaluate_scope(sid, gate_results, codes, gates, scopes) for sid in scopes}


if __name__ == "__main__":
    import json
    import sys

    payload = json.load(sys.stdin) if not sys.stdin.isatty() else {"gate_results": {}, "release_codes": []}
    result = evaluate_release(payload.get("gate_results", {}), payload.get("release_codes", []))
    print(json.dumps({k: v.__dict__ for k, v in result.items()}, indent=1))
