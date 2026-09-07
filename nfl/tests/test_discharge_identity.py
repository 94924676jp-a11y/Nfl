"""Discharge requires a DECLARED target identity and an authorised basis.

Sixteen adversarial cases, from the owner directive of 2026-09-07, written
against the defect that directive was issued for: two practice obligations
discharged by the periodic sweep, `game_id` None, `attributed_captures: 0`,
coverage PASS with the first real T-90 window 49.5 hours away.

The governing rule these all test is one sentence:

    every event-anchored coverage obligation requires an explicitly declared
    target identity and an authorised discharging execution basis.

Note what is NOT the rule. It is not "only certain source kinds require game
identity" -- that was `GAME_SPECIFIC_KINDS` used as a discharge gate, and it is
what let `practice` through. Section P below asserts `_clears` no longer reads
that constant, by AST rather than by grepping the docstring that explains it.
"""
from __future__ import annotations

import ast
import datetime as dt
import inspect
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State  # noqa: E402
from nfl.capture import execution as X  # noqa: E402
from nfl.capture import schedule as S  # noqa: E402
from nfl.capture import coverage as C  # noqa: E402

PASSED = FAILED = 0
FIXTURE = (_REPO / "nfl" / "tests" / "fixtures"
           / "regression_2026_09_07_practice_false_cover.json")


def check(label, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILED += 1
        print(f"  FAIL {label}  {detail}")


UTC = dt.timezone.utc
KICK = dt.datetime(2026, 9, 10, 0, 20, tzinfo=UTC)


def target(kind, game_id="2026_01_NE_SEA", due=None, label=None):
    due = due or (KICK - dt.timedelta(minutes=90) if kind == "inactives"
                  else dt.datetime(2026, 9, 7, 20, 0, tzinfo=UTC))
    return S.CaptureDue(game_id=game_id, label=label or f"{kind}_x", due_utc=due,
                        kind=kind, confirmed=True, note="test", kickoff_utc=KICK)


def in_window(t):
    lo, hi = t.window
    return lo + (hi - lo) / 2


SRC = {"practice": "official_injury_report",
       "final_status": "official_injury_report",
       "inactives": "official_inactives"}


# --------------------------------------------------------------------------
def test_A_periodic_captures_do_not_discharge():
    print("\nA. an unattributed periodic capture inside the window discharges "
          "nothing, of any kind")
    for kind in ("practice", "final_status", "inactives"):
        t = target(kind)
        ts = in_window(t)
        check(f"{kind}: source authorised and timing perfect, still refused",
              not S._clears(t, (ts, SRC[kind], None)),
              f"{kind} cleared by an unattributed capture")
        check(f"{kind}: the two-tuple shape is refused too",
              not S._clears(t, (ts, SRC[kind])))
    # 1, 2, 3 of the directive list, and the same for the legacy 2-tuple.


def test_B_basis_must_be_anchored():
    print("\nB. a manual dispatch without an anchored basis cannot self-certify")
    t = target("practice")
    decl = {"basis": X.BASIS_OPERATOR,
            "targets": [{"game_id": t.game_id, "kind": t.kind,
                         "window_start_utc": t.window[0].isoformat(),
                         "window_end_utc": t.window[1].isoformat()}]}
    e = X.eligibility(decl, source=SRC["practice"], capture_state="PASS",
                      retrieved_at=in_window(t).isoformat(), sha256="a" * 64,
                      blob_path="nfl/vintage/x.gz", provenance_valid=True)
    check("operator dispatch is refused and named",
          e["n_eligible"] == 0
          and "MANUAL_DISPATCH_NOT_SELF_CERTIFYING" in e["targets"][0]["refusals"],
          str(e["targets"][0]["refusals"]))
    for basis in (X.BASIS_SWEEP, X.BASIS_LOCAL, "SOMETHING_NEW"):
        d2 = dict(decl, basis=basis)
        e2 = X.eligibility(d2, source=SRC["practice"], capture_state="PASS",
                           retrieved_at=in_window(t).isoformat(),
                           sha256="a" * 64, blob_path="nfl/vintage/x.gz",
                           provenance_valid=True)
        check(f"basis {basis} cannot discharge", e2["n_eligible"] == 0)
    check("and only the anchored basis is in DISCHARGING_BASES",
          X.DISCHARGING_BASES == (X.BASIS_ANCHORED,), str(X.DISCHARGING_BASES))


def test_C_identity_must_match_exactly():
    print("\nC. identity: None, wrong game, wrong kind, undeclared target")
    t = target("practice")
    ts = in_window(t)
    check("5. game_id None cannot discharge an event target",
          not S._clears(t, (ts, SRC["practice"], None, "practice")))
    check("6. wrong-game attribution cannot discharge",
          not S._clears(t, (ts, SRC["practice"], "2026_01_SF_LA", "practice")))
    check("7. wrong target kind cannot discharge",
          not S._clears(t, (ts, SRC["practice"], t.game_id, "final_status")))
    # 8: correct game, but the execution declared a different obligation, so
    # eligible_targets never emits this pair at all.
    val = {"discharge_eligibility": {"targets": [
        {"game_id": t.game_id, "kind": "final_status", "eligible": True}]}}
    pairs = X.eligible_targets(val)
    check("8. correct game but undeclared target is not emitted as clearing it",
          all(not S._clears(t, (ts, SRC["practice"], g, k)) for g, k in pairs),
          str(pairs))


def test_D_post_hoc_attribution_cannot_discharge():
    print("\nD. attribution invented after retrieval discharges nothing")
    val_legacy = {"discharge_claims": [{"game_id": "2026_01_NE_SEA",
                                        "kind": "practice"}]}
    check("9. the pre-Directive-7 discharge_claims field is not honoured",
          X.eligible_targets(val_legacy) == [], str(X.eligible_targets(val_legacy)))
    val_ineligible = {"discharge_eligibility": {"targets": [
        {"game_id": "2026_01_NE_SEA", "kind": "practice", "eligible": False,
         "refusals": ["BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP"]}]}}
    check("and a declared target the eligibility check refused is not emitted",
          X.eligible_targets(val_ineligible) == [])


def test_E_timestamp_coincidence_infers_nothing():
    print("\nE. 10. timing alone never infers a target")
    t = target("practice")
    lo, hi = t.window
    for off in (dt.timedelta(minutes=1), (hi - lo) / 2, hi - lo
                - dt.timedelta(minutes=1)):
        check(f"a capture {off} into the window still discharges nothing",
              not S._clears(t, (lo + off, SRC["practice"], None)))
    check("and window membership alone is still a separate, honest predicate",
          t.satisfied_by(lo + dt.timedelta(minutes=1)))


def test_F_a_properly_declared_capture_does_discharge():
    print("\nF. 11, 12. a predeclared scheduled anchored capture DOES discharge")
    for kind in ("practice", "inactives"):
        t = target(kind)
        ts = in_window(t)
        decl = {"basis": X.BASIS_ANCHORED,
                "targets": [{"game_id": t.game_id, "kind": t.kind,
                             "window_start_utc": t.window[0].isoformat(),
                             "window_end_utc": t.window[1].isoformat()}]}
        e = X.eligibility(decl, source=SRC[kind], capture_state="PASS",
                          retrieved_at=ts.isoformat(), sha256="a" * 64,
                          blob_path="nfl/vintage/x.gz", provenance_valid=True)
        check(f"{kind}: the declared target is eligible",
              e["n_eligible"] == 1, str(e["targets"][0]["refusals"]))
        pairs = X.eligible_targets({"discharge_eligibility": e})
        check(f"{kind}: and it clears its own target",
              any(S._clears(t, (ts, SRC[kind], g, k)) for g, k in pairs))
        check(f"{kind}: and does not clear the same kind for another game",
              not any(S._clears(target(kind, "2026_01_SF_LA"),
                                (ts, SRC[kind], g, k)) for g, k in pairs))


def test_G_multi_target_declaration():
    print("\nG. 13. an explicitly predeclared multi-target execution")
    a, b = target("practice"), target("practice", "2026_01_SF_LA",
                                      label="practice_mon")
    ts = in_window(a)
    decl = {"basis": X.BASIS_ANCHORED, "targets": [
        {"game_id": x.game_id, "kind": x.kind,
         "window_start_utc": x.window[0].isoformat(),
         "window_end_utc": x.window[1].isoformat()} for x in (a, b)]}
    e = X.eligibility(decl, source=SRC["practice"], capture_state="PASS",
                      retrieved_at=ts.isoformat(), sha256="a" * 64,
                      blob_path="nfl/vintage/x.gz", provenance_valid=True)
    pairs = X.eligible_targets({"discharge_eligibility": e})
    check("both declared targets are eligible", e["n_eligible"] == 2)
    check("and each clears its own obligation",
          any(S._clears(a, (ts, SRC["practice"], g, k)) for g, k in pairs)
          and any(S._clears(b, (ts, SRC["practice"], g, k)) for g, k in pairs))
    c = target("practice", "2026_01_KC_BUF", label="practice_wed")
    check("and a third game that was NOT declared is untouched",
          not any(S._clears(c, (ts, SRC["practice"], g, k)) for g, k in pairs))
    check("the artifact scope stays league-wide, separately recorded",
          e["source_artifact_scope"] == X.LEAGUE_WIDE)


def test_H_guard_deletion_execution_basis():
    print("\nH. 14. GUARD DELETION -- widen DISCHARGING_BASES and the sweep "
          "certifies")
    t = target("practice")
    ts = in_window(t)
    decl = {"basis": X.BASIS_SWEEP,
            "targets": [{"game_id": t.game_id, "kind": t.kind,
                         "window_start_utc": t.window[0].isoformat(),
                         "window_end_utc": t.window[1].isoformat()}]}
    clean = X.eligibility(decl, source=SRC["practice"], capture_state="PASS",
                          retrieved_at=ts.isoformat(), sha256="a" * 64,
                          blob_path="nfl/vintage/x.gz", provenance_valid=True)
    original = X.DISCHARGING_BASES
    try:
        X.DISCHARGING_BASES = original + (X.BASIS_SWEEP,)
        leaked = X.eligibility(decl, source=SRC["practice"],
                               capture_state="PASS", retrieved_at=ts.isoformat(),
                               sha256="a" * 64, blob_path="nfl/vintage/x.gz",
                               provenance_valid=True)
    finally:
        X.DISCHARGING_BASES = original
    check("clean: the sweep is refused", clean["n_eligible"] == 0)
    check("bypassed: the same sweep now discharges -- so the tuple is the guard",
          leaked["n_eligible"] == 1, str(leaked["targets"][0]["refusals"]))


def test_I_guard_deletion_explicit_target():
    print("\nI. 15. GUARD DELETION -- restore the unattributed entry and the "
          "false cover comes back")
    t = target("practice")
    ts = in_window(t)
    original = S._clears
    try:
        # The exact pre-repair predicate: game identity required only for
        # GAME_SPECIFIC_KINDS.
        def legacy(tg, p):
            if isinstance(p, tuple):
                a = (tuple(p) + (None, None))[:4]
                if tg.kind in S.GAME_SPECIFIC_KINDS and a[2] != tg.game_id:
                    return False
                return tg.discharges(a[0], a[1])
            return tg.satisfied_by(p)
        S._clears = legacy
        leaked = S._clears(t, (ts, SRC["practice"], None))
    finally:
        S._clears = original
    check("clean: unattributed refused", not S._clears(t, (ts, SRC['practice'],
                                                           None)))
    check("bypassed: the pre-repair predicate covers it again", leaked)


def test_J_the_two_real_false_positives_are_refused():
    print("\nJ. 16. the two observed false positives, replayed and refused")
    fx = json.loads(FIXTURE.read_text())
    caps = [(dt.datetime.fromisoformat(c["retrieved_at"].replace("Z", "+00:00")),
             c["source"], c["game_id"]) for c in fx["discharging_captures"]]
    check("the fixture records the contradiction that was observed",
          fx["observed_summary"]["covered"] == 2
          and fx["observed_summary"]["attributed_captures"] == 0)
    for spec in fx["falsely_covered_targets"]:
        t = S.CaptureDue(
            game_id=spec["game_id"], label=spec["label"],
            due_utc=dt.datetime.fromisoformat(
                spec["window_start_utc"].replace("Z", "+00:00")),
            kind=spec["kind"], confirmed=False, note="replayed from fixture",
            kickoff_utc=dt.datetime.fromisoformat(
                spec["kickoff_utc"].replace("Z", "+00:00")))
        lo, hi = t.window
        for ts, src, gid in caps:
            check(f"{spec['game_id']}/{spec['label']}: the {ts:%H:%M:%S} sweep "
                  f"is inside the window and still refused",
                  lo <= ts <= hi and not S._clears(t, (ts, src, gid)),
                  f"in_window={lo <= ts <= hi}")


def test_K_live_state_is_repaired():
    print("\nK. the live manifest no longer covers anything")
    man = _REPO / "nfl" / "vintage_manifest.jsonl"
    cov = C.coverage(2026, 1, manifest_path=man)
    e = cov.evidence
    check("nothing is covered", e["covered"] == 0, str(e.get("covered")))
    check("nothing is missed either -- no window has closed", e["missed"] == 0)
    check("the state is DEFERRED, which is a debt and not a pass",
          cov.state is State.DEFERRED and cov.code == "NO_WINDOW_HAS_CLOSED_YET",
          f"{cov.state}[{cov.code}]")
    check("covered and attributed_captures can no longer disagree",
          e["covered"] == 0 and e["attributed_captures"] == 0)
    check("and the historical captures are still read, not deleted",
          e["unattributed_captures"] > 300 and e["total_pass_rows"] > 300,
          f"unattributed={e.get('unattributed_captures')} "
          f"pass_rows={e.get('total_pass_rows')}")
    check("the real future obligation is still pending",
          e["not_yet_due"] == e["n_targets"] and e["n_targets"] > 60,
          f"{e.get('not_yet_due')}/{e.get('n_targets')}")


def test_L_clears_no_longer_reads_the_scope_constant():
    print("\nL. `_clears` does not consult GAME_SPECIFIC_KINDS (AST, not grep)")
    tree = ast.parse(inspect.getsource(S._clears))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    check("the identifier appears in no executable expression",
          "GAME_SPECIFIC_KINDS" not in (names | attrs),
          str(sorted(names | attrs)))
    check("it is still documented as artifact scope, and says so",
          "GAME_SPECIFIC_KINDS" in inspect.getsource(S._clears))
    # The constant may still be REPORTED. What it may never do again is gate a
    # decision, so the assertion is about comparison and membership tests
    # specifically, not about the identifier appearing at all.
    gating = []
    for mod, src in (("schedule", inspect.getsource(S)),
                     ("coverage", inspect.getsource(C))):
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, (ast.Compare, ast.If, ast.IfExp)):
                continue
            for sub in ast.walk(node):
                if ((isinstance(sub, ast.Name)
                     and sub.id == "GAME_SPECIFIC_KINDS")
                        or (isinstance(sub, ast.Attribute)
                            and sub.attr == "GAME_SPECIFIC_KINDS")):
                    gating.append(f"{mod}:{node.lineno}")
    check("and neither module tests membership of it to decide anything",
          not gating, str(gating))
    check("it survives only as a reported field",
          "game_specific_kinds" in inspect.getsource(C.coverage))


if __name__ == "__main__":
    for fn in (test_A_periodic_captures_do_not_discharge,
               test_B_basis_must_be_anchored,
               test_C_identity_must_match_exactly,
               test_D_post_hoc_attribution_cannot_discharge,
               test_E_timestamp_coincidence_infers_nothing,
               test_F_a_properly_declared_capture_does_discharge,
               test_G_multi_target_declaration,
               test_H_guard_deletion_execution_basis,
               test_I_guard_deletion_explicit_target,
               test_J_the_two_real_false_positives_are_refused,
               test_K_live_state_is_repaired,
               test_L_clears_no_longer_reads_the_scope_constant):
        fn()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
