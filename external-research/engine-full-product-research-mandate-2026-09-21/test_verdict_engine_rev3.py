"""Regressions for the four reproduced verdict-engine failures and findings 5 to 8.

Every test here failed against `verdict_engine_rev2.py` before the fix. The
nine tests shipped with Revision 2 live in `test_verdict_engine.py` and still
pass unchanged; this file is additive, because a test suite that had to be
rewritten to accommodate a fix is not evidence the fix was correct.

Synthetic gate statuses only. No gate has been evaluated and nothing here is
deployment evidence. CANDIDATE_NOT_ACCEPTED_BASELINE / V2 NOT YET EARNED.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import verdict_engine as ve                                      # noqa: E402
import offer_edge as oe                                          # noqa: E402

GATES = ve.load_gates()
SCOPES = ve.load_scopes()
LEGS = ["P1.receiving_yards", "P1.anytime_td"]

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok     {what}")
    else:
        FAILED += 1
        print(f"  FAIL   {what}")


def all_pass():
    g = {gid: "PASS" for gid in GATES}
    g["G-XX-2"] = "PASS_FAVORABLE"
    g["G-XXIX-2"] = "PASS_FAVORABLE"
    return g


def ev(gr=None, codes=(), **kw):
    kw.setdefault("sgp_legs", LEGS)
    return ve.evaluate_release(gr if gr is not None else all_pass(),
                               list(codes), **kw)


# --- R2-1 and R2-2: upstream blockers must propagate -----------------------
def test_weather_proxy_on_f1_reaches_everything_built_on_f1():
    out = ev(codes=["WEATHER_PROXY:game1"])
    ok(out["F1"].verdict == "RESEARCH_ONLY", "F1 is blocked by its own code")
    for sid in ("F2", "F3", "F4", "F5", "P1.receiving_yards", "D1", "D2",
                "D5", "D5.showdown", "N3"):
        ok(out[sid].verdict != "DEPLOYABLE",
           f"{sid} does not return DEPLOYABLE on a blocked F1: "
           f"{out[sid].verdict}")
    ok(any(b.startswith("UPSTREAM_NOT_DEPLOYABLE:") for b in
           out["D5"].upstream_blockers), "D5 records an upstream blocker")
    ok(out["D5"].upstream_blockers[0].endswith("WEATHER_PROXY:game1"),
       f"and names the ROOT cause rather than the chain or the verdict: "
       f"{out['D5'].upstream_blockers[0]}")
    ok("game1" in out["D5"].blocked_entities,
       f"the affected entity travels downstream: {out['D5'].blocked_entities}")
    # N2 reads evidence only and depends on nothing.
    ok(out["N2"].verdict == "DEPLOYABLE",
       "the evidence viewer, which depends on no football scope, is untouched")


def test_routes_proxy_on_f2_reaches_f3_props_and_dfs():
    out = ev(codes=["ROUTES_PROXY:player1"])
    ok(out["F1"].verdict == "DEPLOYABLE",
       "F1 is UPSTREAM of F2 and is not demoted: invalidity flows down only")
    ok(out["F2"].verdict == "RESEARCH_ONLY", "F2 is blocked by its own code")
    for sid in ("F3", "P1.receiving_yards", "P1.targets", "D1", "D5"):
        ok(out[sid].verdict != "DEPLOYABLE",
           f"{sid} inherits the F2 blocker: {out[sid].verdict}")
    ok(out["F4"].verdict == "DEPLOYABLE",
       "the kicker scope depends on F1, not F2, and is unaffected")


# --- R2-3: the calibration blocker, both directions ------------------------
def test_calibration_infeasible_reaches_every_consumer_of_those_weights():
    out = ev(codes=["CALIBRATION_INFEASIBLE:receiving_yards"])
    ok(out["P1.receiving_yards"].verdict == "RESEARCH_ONLY",
       "the named family is blocked")
    for sid in ("D1", "D2", "D3", "D4", "D5", "D3.showdown", "D5.showdown"):
        ok(out[sid].verdict != "DEPLOYABLE",
           f"{sid} reads the same weighted worlds and is blocked: "
           f"{out[sid].verdict}")
    ok("CALIBRATION_INFEASIBLE:receiving_yards" in out["D1"].reason_codes,
       "and carries the code itself, not just an upstream marker")
    ok(SCOPES["D1"].consumes_weighted_worlds,
       "the consumer relation is DERIVED from requiring G-XVIII-1, so a new "
       "consumer cannot be forgotten out of a hand-kept list")


def test_calibration_infeasible_does_not_touch_unrelated_families():
    out = ev(codes=["CALIBRATION_INFEASIBLE:receiving_yards"])
    for sid in ("P1.rushing_yards", "P1.passing_yards", "P1.kicking_points"):
        ok(out[sid].verdict == "DEPLOYABLE",
           f"{sid} is a different family and is not blocked: "
           f"{out[sid].verdict}")
    for sid in ("F1", "F2", "F3", "F4", "F5"):
        ok(out[sid].verdict == "DEPLOYABLE",
           f"{sid} is upstream football and a calibration failure never "
           f"flows up into it: {out[sid].verdict}")


# --- R2-4: statuses validated by gate class --------------------------------
def test_an_exact_gate_requires_an_actual_pass():
    for bad in ("PASS_INCLUDES_ZERO", "PASS_FAVORABLE"):
        g = all_pass()
        g["G-X-1"] = bad
        out = ev(g)
        ok(out["F1"].verdict == "RESEARCH_ONLY",
           f"G-X-1 (EXACT_CORRECTNESS) = {bad} does not clear F1: "
           f"{out['F1'].verdict}")
        ok(any(c.startswith("GATE_STATUS_INVALID_FOR_CLASS:G-X-1")
               for c in out["F1"].reason_codes),
           f"and is named a class error rather than a failure: "
           f"{out['F1'].reason_codes[:1]}")
        ok(out["D1"].verdict != "DEPLOYABLE",
           f"and it propagates: D1 = {out['D1'].verdict}")

    # Every exact/provenance/statistical gate behaves the same way.
    for gid, gate in GATES.items():
        if gate.gate_class == "MARKET_COMPARISON":
            continue
        ok(ve.PASS_INCLUDES_ZERO not in ve.CLASS_PERMITTED[gate.gate_class],
           f"{gid} ({gate.gate_class}) cannot carry a market status")
    ok(ve.CLASS_CLEARING["MARKET_COMPARISON"] == frozenset({"PASS_FAVORABLE"}),
       "and a market gate is cleared only by PASS_FAVORABLE")
    ok(ve.CLASS_CLEARING["EXACT_CORRECTNESS"] == frozenset({"PASS"}),
       "while an exact gate is cleared only by PASS")


def test_component_inclusion_never_fails_a_scope():
    g = all_pass()
    g["G-XII-1"] = "FAIL"
    out = ev(g)
    ok(out["F3"].verdict == "DEPLOYABLE",
       f"a matchup component that does not earn inclusion is EXCLUDED, not a "
       f"scope failure: {out['F3'].verdict}")
    ok(any("G-XII-1" in c for c in out["F3"].excluded_components),
       f"and the exclusion is recorded: {out['F3'].excluded_components}")


# --- R2-5: scoped gate-result identities -----------------------------------
def test_one_result_cannot_silently_speak_for_every_family():
    fam = "receiving_yards"
    res = [ve.GateResult(gid, "PASS") for gid in GATES
           if GATES[gid].gate_class != "MARKET_COMPARISON"]
    res.append(ve.GateResult("G-XX-2", "PASS_FAVORABLE", family=fam))
    res.append(ve.GateResult("G-XXIX-2", "PASS_FAVORABLE"))
    out = ev(res)
    ok(out[f"P1.{fam}"].verdict == "DEPLOYABLE",
       f"the family the market result names is deployable: "
       f"{out[f'P1.{fam}'].verdict}")
    ok(out["P1.rushing_yards"].verdict == "RESEARCH_ONLY",
       f"a family it does not name is NOT: "
       f"{out['P1.rushing_yards'].verdict}")
    ok(any("G-XX-2" in c for c in out["P1.rushing_yards"].reason_codes),
       "and says the market gate was not evaluated for it")

    # Specificity ordering, and a genuine tie is refused.
    ctx = ve.Context(scope_id="P1.receiving_yards", family=fam,
                     game_id="g1")
    st, _r, _n = ve.resolve_result(
        "G-XX-2", GATES["G-XX-2"], ctx,
        [ve.GateResult("G-XX-2", "PASS_INCLUDES_ZERO"),
         ve.GateResult("G-XX-2", "PASS_FAVORABLE", family=fam)])
    ok(st == "PASS_FAVORABLE",
       f"the more specific result wins: {st}")
    st2, _r2, notes = ve.resolve_result(
        "G-XX-2", GATES["G-XX-2"], ctx,
        [ve.GateResult("G-XX-2", "PASS_FAVORABLE", family=fam),
         ve.GateResult("G-XX-2", "PASS_INCLUDES_ZERO", family=fam)])
    ok(st2 == "NOT_EVALUATED"
       and any(c.startswith("AMBIGUOUS_GATE_RESULT") for c in notes),
       f"two results disagreeing at equal specificity clear nothing: "
       f"{st2} {notes}")


def test_strict_scoping_refuses_an_unscoped_per_entity_result():
    loose = ev(all_pass())
    ok(loose["P1.receiving_yards"].verdict == "DEPLOYABLE",
       "the legacy flat mapping still evaluates, for compatibility")
    ok(any("GATE_RESULT_UNSCOPED" in c
           for c in loose["P1.receiving_yards"].display_codes),
       "but an unscoped per-entity result is always surfaced, never silent")
    strict = ev(all_pass(), strict_scoping=True)
    ok(strict["P1.receiving_yards"].verdict == "RESEARCH_ONLY",
       f"and under strict scoping it refuses: "
       f"{strict['P1.receiving_yards'].verdict}")
    ok(any("GATE_RESULT_UNSCOPED" in c
           for c in strict["P1.receiving_yards"].reason_codes),
       "naming the gate whose result had no identity")


# --- R2-7: SGP legs and the Showdown path ----------------------------------
def test_sgp_depends_on_its_selected_legs_only():
    res = [ve.GateResult(gid, "PASS") for gid in GATES
           if GATES[gid].gate_class != "MARKET_COMPARISON"]
    res.append(ve.GateResult("G-XX-2", "PASS_INCLUDES_ZERO",
                             family="rushing_yards"))
    for fam in ("receiving_yards", "anytime_td"):
        res.append(ve.GateResult("G-XX-2", "PASS_FAVORABLE", family=fam))
    res.append(ve.GateResult("G-XXIX-2", "PASS_FAVORABLE"))
    out = ve.evaluate_release(res, [], sgp_legs=LEGS)
    ok(out["P1.rushing_yards"].verdict == "NO_SUPPORTED_EDGE",
       f"the unselected family finds no edge: "
       f"{out['P1.rushing_yards'].verdict}")
    # AND THE SGP IS NOT CARRIED BY ITS LEGS. A joint has its own price and
    # its own comparison; correlation between legs is the entire reason the
    # product exists, so leg-level market results cannot establish it. With
    # no SGP-level result the honest answer is RESEARCH_ONLY.
    ok(out["P2"].verdict == "RESEARCH_ONLY"
       and any("G-XX-2" in c for c in out["P2"].reason_codes),
       f"the SGP is not deployable off its legs' market results: "
       f"{out['P2'].verdict} {out['P2'].reason_codes[:1]}")

    ticket = list(res) + [ve.GateResult("G-XX-2", "PASS_FAVORABLE",
                                        scope_id="P2")]
    out_t = ve.evaluate_release(ticket, [], sgp_legs=LEGS)
    ok(out_t["P2"].verdict == "DEPLOYABLE",
       f"an SGP-level market result does establish it: "
       f"{out_t['P2'].verdict}")

    out2 = ve.evaluate_release(ticket, [],
                               sgp_legs=LEGS + ["P1.rushing_yards"])
    ok(out2["P2"].verdict != "DEPLOYABLE",
       f"and selecting a no-edge family as a leg reaches the SGP: "
       f"{out2['P2'].verdict}")

    undeclared = ve.evaluate_release(all_pass(), [])
    ok(undeclared["P2"].verdict == "RESEARCH_ONLY"
       and "SGP_LEGS_NOT_DECLARED" in undeclared["P2"].reason_codes,
       f"an SGP with no declared legs is refused rather than assumed to be "
       f"every family: {undeclared['P2'].reason_codes[:1]}")


def test_showdown_has_its_own_complete_path():
    for sid in ("D3.showdown", "D4.showdown", "D5.showdown"):
        ok(sid in SCOPES, f"{sid} exists")
    chain = ve.dependency_closure("D5.showdown", SCOPES)
    ok("D2" in chain, f"Showdown contest simulation descends from D2: {chain}")
    ok("D1" not in chain,
       f"and not from Classic, which was its only path in Revision 2: "
       f"{chain}")
    ok("D1" in ve.dependency_closure("D5", SCOPES),
       "while Classic contest simulation still descends from D1")
    g = all_pass()
    g["G-XXX-1"] = "FAIL"          # Showdown captain transform
    out = ev(g)
    ok(out["D5.showdown"].verdict != "DEPLOYABLE",
       f"a Showdown-only failure reaches the Showdown chain: "
       f"{out['D5.showdown'].verdict}")
    ok(out["D5"].verdict == "DEPLOYABLE",
       f"and does not reach Classic: {out['D5'].verdict}")


# --- R2-6: model validation is not an offer edge ---------------------------
def test_offer_edge_is_downstream_and_cannot_promote_a_scope():
    offer = oe.Offer(market_id="m1", family="receiving_yards",
                     player_id="p1", game_id="g1", side="OVER", line=54.5,
                     american_odds=-110, settlement_rule=oe.NO_PUSH,
                     book="hardrock", observed_at="2026-09-21T23:00:00Z")
    blocked = oe.evaluate_offer(offer, p_win=0.60, p_push=0.0, mc_se=0.004,
                                scope_verdict="RESEARCH_ONLY",
                                scope_id="P1.receiving_yards")
    ok(blocked.verdict == "NOT_EVALUATED"
       and any(c.startswith("SCOPE_NOT_DEPLOYABLE") for c in blocked.refusals),
       f"an offer on an unvalidated model is not evaluated: "
       f"{blocked.refusals}")

    good = oe.evaluate_offer(offer, p_win=0.60, p_push=0.0, mc_se=0.004,
                             scope_verdict="DEPLOYABLE",
                             scope_id="P1.receiving_yards")
    ok(good.verdict == "EV_POSITIVE",
       f"a 60% side at -110 has positive EV: {good.ev_per_unit:.4f}")
    ok(good.ev_interval[0] > 0,
       f"with an interval excluding zero: {good.ev_interval}")

    # The separation, stated as a property: a DEPLOYABLE family can still
    # contain an offer with no edge.
    thin = oe.evaluate_offer(offer, p_win=0.524, p_push=0.0, mc_se=0.01,
                             scope_verdict="DEPLOYABLE",
                             scope_id="P1.receiving_yards")
    ok(thin.verdict == "EV_INCLUDES_ZERO",
       f"a validated model at a marginal price yields no offer edge: "
       f"{thin.verdict} ev={thin.ev_per_unit:.4f} {thin.ev_interval}")
    ok(thin.mc_se == 0.01 and thin.ev_interval[0] < 0 < thin.ev_interval[1],
       "and the probability's Monte Carlo error is inside the EV interval")

    stale = oe.evaluate_offer(offer, p_win=0.60, p_push=0.0, mc_se=0.004,
                              scope_verdict="DEPLOYABLE",
                              scope_id="P1.receiving_yards",
                              now="2026-09-21T23:30:00Z",
                              max_price_age_seconds=300)
    ok(any(c.startswith("PRICE_STALE") for c in stale.refusals),
       f"a price half an hour old is refused: {stale.refusals}")

    bad_push = oe.evaluate_offer(offer, p_win=0.55, p_push=0.03, mc_se=0.004,
                                 scope_verdict="DEPLOYABLE",
                                 scope_id="P1.receiving_yards")
    ok(any(c.startswith("PUSH_MASS_ON_A_NO_PUSH_LINE")
           for c in bad_push.refusals),
       f"push mass on a half-point line is a contradiction, not a rounding "
       f"matter: {bad_push.refusals}")

    whole = oe.Offer(**{**offer.__dict__, "line": 54.0,
                        "settlement_rule": oe.PUSH_REFUND})
    pushed = oe.evaluate_offer(whole, p_win=0.55, p_push=0.06, mc_se=0.004,
                               scope_verdict="DEPLOYABLE",
                               scope_id="P1.receiving_yards")
    ok(pushed.p_lose is not None
       and abs(pushed.p_win + pushed.p_push + pushed.p_lose - 1.0) < 1e-9,
       "on a whole-number line the three outcomes are a distribution")
    ok(pushed.ev_per_unit > oe.evaluate_offer(
        whole, p_win=0.55, p_push=0.06, mc_se=0.004,
        scope_verdict="DEPLOYABLE", scope_id="P1.receiving_yards"
    ).ev_per_unit - 1e-12, "and the settlement rule is applied, not assumed")


# --- structural invariants -------------------------------------------------
def test_no_scope_is_deployable_above_a_blocked_dependency():
    import itertools
    gates_to_break = ["G-X-1", "G-VII-2", "G-IX-1", "G-XXII-1", "G-XXIII-1"]
    for gid in gates_to_break:
        g = all_pass()
        g[gid] = "FAIL"
        out = ev(g)
        for sid, scope in SCOPES.items():
            if out[sid].verdict != "DEPLOYABLE":
                continue
            for dep in ve.dependency_closure(sid, SCOPES, LEGS):
                ok(out[dep].verdict == "DEPLOYABLE",
                   f"[{gid} FAIL] {sid} is DEPLOYABLE so its dependency "
                   f"{dep} must be too, but is {out[dep].verdict}")


def test_verdict_domain_and_non_betting_rule_hold_everywhere():
    for codes in ([], ["WEATHER_PROXY:g1"], ["RELEASE_UNPROVEN"],
                  ["CALIBRATION_INFEASIBLE:receiving_yards"],
                  ["IDENTITY_UNRESOLVED:draftkings:J. Smith"]):
        out = ev(all_pass(), codes)
        ok(all(v.verdict in ve.VERDICTS for v in out.values()),
           f"every verdict is in the domain under {codes}")
        ok(all(v.verdict != "NO_SUPPORTED_EDGE"
               for sid, v in out.items()
               if SCOPES[sid].scope_kind == "NON_BETTING"),
           f"no non-betting scope finds no edge under {codes}")


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f"{FAILED} check(s) failed in this module")


def main():
    for t in (test_weather_proxy_on_f1_reaches_everything_built_on_f1,
              test_routes_proxy_on_f2_reaches_f3_props_and_dfs,
              test_calibration_infeasible_reaches_every_consumer_of_those_weights,
              test_calibration_infeasible_does_not_touch_unrelated_families,
              test_an_exact_gate_requires_an_actual_pass,
              test_component_inclusion_never_fails_a_scope,
              test_one_result_cannot_silently_speak_for_every_family,
              test_strict_scoping_refuses_an_unscoped_per_entity_result,
              test_sgp_depends_on_its_selected_legs_only,
              test_showdown_has_its_own_complete_path,
              test_offer_edge_is_downstream_and_cannot_promote_a_scope,
              test_no_scope_is_deployable_above_a_blocked_dependency,
              test_verdict_domain_and_non_betting_rule_hold_everywhere):
        print(f"== {t.__name__}")
        t()
    print(f"\nPASSED {PASSED} FAILED {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
