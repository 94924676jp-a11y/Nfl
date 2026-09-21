"""Unit tests for verdict_engine.py. Run: python3 -m pytest test_verdict_engine.py -q  (or python3 test_verdict_engine.py)."""

import verdict_engine as ve

GATES = ve.load_gates()
SCOPES = ve.load_scopes()


def all_pass():
    return {g: "PASS" for g in GATES}


def test_every_gate_in_scopes_exists_in_matrix():
    for s in SCOPES.values():
        for g in s.required_gates:
            assert g in GATES, g
        if s.market_gate:
            assert s.market_gate in GATES


def test_no_gate_orphaned():
    used = set()
    for s in SCOPES:
        used.update(ve.transitive_gates(s, SCOPES))
    for s in SCOPES.values():
        if s.market_gate:
            used.add(s.market_gate)
    # COMPONENT_INCLUSION gates decide whether an optional component enters a release; they are not scope gates
    orphans = {g for g in set(GATES) - used if GATES[g].gate_class != 'COMPONENT_INCLUSION'}
    assert not orphans, orphans


def test_default_everything_unevaluated_is_research_only():
    out = ve.evaluate_release({}, [])
    assert all(v.verdict == "RESEARCH_ONLY" for v in out.values())
    assert all(any(c.startswith("GATE_NOT_EVALUATED:") for c in v.reason_codes) for v in out.values())


def test_all_pass_football_scope_deployable_and_betting_needs_market_gate():
    gr = all_pass()
    out = ve.evaluate_release(gr, [])
    assert out["F1"].verdict == "DEPLOYABLE"
    assert out["N1"].verdict == "DEPLOYABLE"
    # market gate is plain PASS, not PASS_FAVORABLE, so betting scopes are not deployable
    assert out["P1.receiving_yards"].verdict == "RESEARCH_ONLY"
    gr["G-XX-2"] = "PASS_FAVORABLE"
    out = ve.evaluate_release(gr, [])
    assert out["P1.receiving_yards"].verdict == "DEPLOYABLE"
    gr["G-XX-2"] = "PASS_INCLUDES_ZERO"
    out = ve.evaluate_release(gr, [])
    assert out["P1.receiving_yards"].verdict == "NO_SUPPORTED_EDGE"
    assert "MARKET_INTERVAL_INCLUDES_ZERO" in out["P1.receiving_yards"].reason_codes


def test_upstream_fail_propagates_downstream_only():
    gr = all_pass()
    gr["G-XX-2"] = "PASS_FAVORABLE"
    gr["G-XXIX-2"] = "PASS_FAVORABLE"
    gr["G-VII-2"] = "FAIL"  # F2 exact gate
    out = ve.evaluate_release(gr, [])
    assert out["F1"].verdict == "DEPLOYABLE"
    assert out["F2"].verdict == "RESEARCH_ONLY"
    assert out["F3"].verdict == "RESEARCH_ONLY"
    assert out["D1"].verdict == "RESEARCH_ONLY"
    assert out["F4"].verdict == "DEPLOYABLE"
    assert "GATE_FAIL:G-VII-2" in out["D1"].reason_codes


def test_identity_failure_blocks_dfs_but_not_football():
    gr = all_pass()
    gr["G-XX-2"] = "PASS_FAVORABLE"
    codes = ["IDENTITY_UNRESOLVED:draftkings:J. Smith"]
    out = ve.evaluate_release(gr, codes)
    assert out["F3"].verdict == "DEPLOYABLE"
    assert codes[0] in out["F3"].display_codes
    assert out["P1.receiving_yards"].verdict == "DEPLOYABLE"
    assert out["D1"].verdict == "RESEARCH_ONLY"
    assert codes[0] in out["D1"].reason_codes


def test_release_unproven_blocks_everything_but_evidence_viewer():
    gr = all_pass()
    out = ve.evaluate_release(gr, ["RELEASE_UNPROVEN"])
    assert out["F1"].verdict == "RESEARCH_ONLY"
    assert out["D5"].verdict == "RESEARCH_ONLY"
    assert out["N2"].verdict == "DEPLOYABLE"


def test_non_betting_never_no_supported_edge():
    gr = all_pass()
    gr["G-XX-2"] = "PASS_INCLUDES_ZERO"
    gr["G-XXIX-2"] = "PASS_INCLUDES_ZERO"
    out = ve.evaluate_release(gr, [])
    for sid, v in out.items():
        if SCOPES[sid].scope_kind == "NON_BETTING":
            assert v.verdict != "NO_SUPPORTED_EDGE"


def test_verdict_domain():
    gr = all_pass()
    out = ve.evaluate_release(gr, ["STALE_INPUT:nflverse_depth_charts"])
    assert set(v.verdict for v in out.values()) <= set(ve.VERDICTS)
    assert out["F1"].verdict == "RESEARCH_ONLY"


if __name__ == "__main__":
    import sys
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except AssertionError as e:
                failures += 1
                print("FAIL", name, e)
    sys.exit(1 if failures else 0)
