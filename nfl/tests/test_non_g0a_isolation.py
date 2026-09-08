"""The non-G0A anchored path cannot touch the G0A obligation.

WHAT THIS PROTECTS

`nfl-status.yml` was added so practice and final_status obligations stop being
knowingly missed. It fires inside windows, from the same authorised sources, on
the same repository. The one thing it must never do is discharge the
outstanding G0A `inactives` obligation -- the single item standing between
G0A 11/12 and 12/12.

Isolation is structural, not conventional, and every layer of it is asserted
here: a distinct workflow name, a distinct basis constant, a basis->kinds map
that excludes the G0A kind, and a distinct schedule identity prefix. A test
that only checked the comment would be worthless.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.capture import execution as X                         # noqa: E402
from nfl.capture import coverage as C                          # noqa: E402
from nfl.prospective import nfl1_readiness as RD               # noqa: E402
from nfl.tests.bypass import guard_bypassed                    # noqa: E402

PASSED = FAILED = 0
UTC = dt.timezone.utc
WF_G0A = _REPO / ".github" / "workflows" / "nfl-t90.yml"
WF_NG = _REPO / ".github" / "workflows" / "nfl-status.yml"

# The accepted, repaired G0A workflow. Frozen by owner ruling until the event.
G0A_IDENTITY = "SCHED-2a2924d4966fbd3d"
# The T-90 window that carries the outstanding G0A item.
G0A_WINDOW = (dt.datetime(2026, 9, 9, 22, 50, tzinfo=UTC),
              dt.datetime(2026, 9, 10, 0, 10, tzinfo=UTC))


def check(label, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILED += 1
        print(f"  FAIL {label}  {detail}")


def _decl(basis, kind, game_id="2026_01_NE_SEA", window=G0A_WINDOW):
    return {"basis": basis, "targets": [{
        "game_id": game_id, "kind": kind,
        "window_start_utc": window[0].isoformat(),
        "window_end_utc": window[1].isoformat(),
        "kickoff_utc": "2026-09-10T00:20:00+00:00"}]}


def _elig(basis, kind, source="official_inactives", window=G0A_WINDOW):
    """Everything else made maximally favourable, so only the basis decides."""
    return X.eligibility(
        _decl(basis, kind, window=window), source=source, capture_state="PASS",
        retrieved_at=window[0] + dt.timedelta(minutes=10),
        sha256="a" * 64, blob_path="nfl/vintage/x.html.gz",
        provenance_valid=True)


# ==========================================================================
def test_A_the_two_paths_are_distinct():
    print("\nA. two workflows, two identities, two bases")
    check("both workflow files exist", WF_G0A.exists() and WF_NG.exists())
    g0a, ng = WF_G0A.read_text(), WF_NG.read_text()
    check("  the G0A workflow still carries its frozen identity",
          G0A_IDENTITY in g0a, "identity changed")
    # Parse the DECLARED identity rather than substring-searching the file.
    # The non-G0A header deliberately names the G0A workflow and its identity
    # as the path it must not touch, so a substring search would fail on the
    # documentation that exists to prevent the confusion.
    def declared_identity(text):
        for ln in text.splitlines():
            if "schedule identity:" in ln:
                return ln.split("schedule identity:")[1].strip()
        return None
    g0a_id, ng_id = declared_identity(g0a), declared_identity(ng)
    check("  each workflow declares an identity", g0a_id and ng_id,
          f"{g0a_id} / {ng_id}")
    check("  the G0A workflow declares the frozen identity",
          g0a_id == G0A_IDENTITY, str(g0a_id))
    check("  the non-G0A workflow declares a DIFFERENT one",
          ng_id != G0A_IDENTITY, str(ng_id))
    check("  and a different prefix, so the two can never be read as the "
          "same schedule",
          ng_id.startswith("SCHEDNG-") and g0a_id.startswith("SCHED-")
          and not g0a_id.startswith("SCHEDNG-"), f"{g0a_id} / {ng_id}")
    check("  the workflow names differ",
          X.ANCHORED_WORKFLOW != X.NON_G0A_ANCHORED_WORKFLOW)
    check("  and each file declares its own name",
          f"name: {X.ANCHORED_WORKFLOW}" in g0a
          and f"name: {X.NON_G0A_ANCHORED_WORKFLOW}" in ng)
    check("  the bases differ",
          X.BASIS_ANCHORED != X.BASIS_ANCHORED_NON_G0A)


def test_B_the_non_g0a_basis_cannot_discharge_inactives():
    print("\nB. the non-G0A basis cannot discharge the G0A kind")
    e = _elig(X.BASIS_ANCHORED_NON_G0A, "inactives")
    t = e["targets"][0]
    check("an inactives target is REFUSED even with everything else perfect: "
          "in window, authorised source, PASS capture, valid provenance, "
          "raw blob persisted",
          not t["eligible"], str(t["refusals"]))
    check("  and the refusal names the basis restriction, not something vague",
          f"BASIS_NOT_AUTHORISED_FOR_KIND:{X.BASIS_ANCHORED_NON_G0A}"
          in t["refusals"], str(t["refusals"]))
    check("  n_eligible is zero", e["n_eligible"] == 0)


def test_C_the_non_g0a_basis_CAN_discharge_its_own_kinds():
    print("\nC. and it does discharge the kinds it exists for")
    win = (dt.datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
           dt.datetime(2026, 9, 9, 16, 0, tzinfo=UTC))
    for kind in ("practice", "final_status"):
        e = _elig(X.BASIS_ANCHORED_NON_G0A, kind,
                  source="official_injury_report", window=win)
        check(f"  {kind}: eligible", e["targets"][0]["eligible"],
              str(e["targets"][0]["refusals"]))
    check("  so section B is a real restriction, not a broken code path", True)


def test_D_the_g0a_basis_is_unrestricted_and_still_works():
    print("\nD. the G0A path is unchanged by any of this")
    e = _elig(X.BASIS_ANCHORED, "inactives")
    check("the G0A basis still discharges inactives",
          e["targets"][0]["eligible"], str(e["targets"][0]["refusals"]))
    check("  BASIS_KINDS places no restriction on it",
          X.BASIS_KINDS[X.BASIS_ANCHORED] is None)
    check("  and the G0A kind is excluded from the non-G0A tuple",
          X.G0A_KIND not in X.BASIS_KINDS[X.BASIS_ANCHORED_NON_G0A])


def test_E_only_the_g0a_workflow_reaches_the_g0a_obligation():
    print("\nE. no other execution reaches the NE@SEA inactives obligation")
    for wf, ev, why in (
            (X.NON_G0A_ANCHORED_WORKFLOW, "schedule", "the non-G0A schedule"),
            (X.NON_G0A_ANCHORED_WORKFLOW, "workflow_dispatch",
             "a manual dispatch of it"),
            (X.ANCHORED_WORKFLOW, "workflow_dispatch",
             "a manual dispatch of the G0A workflow"),
            ("NFL vintage capture", "schedule", "the periodic baseline"),
            ("something new", "schedule", "an unknown workflow")):
        basis = X.declaration_basis(
            {"is_github_actions": True, "workflow": wf, "event_name": ev})
        e = _elig(basis, "inactives")
        check(f"  {why} cannot discharge inactives",
              not e["targets"][0]["eligible"], f"{basis} {e['targets'][0]}")
    basis = X.declaration_basis({"is_github_actions": True,
                                 "workflow": X.ANCHORED_WORKFLOW,
                                 "event_name": "schedule"})
    check("  ONLY a scheduled firing of the G0A workflow can",
          _elig(basis, "inactives")["targets"][0]["eligible"])


def test_F_a_non_g0a_capture_does_not_move_g0a():
    print("\nF. G0A readiness is unmoved by non-G0A success")
    r = RD.report()
    check("G0A is 11 of 12", r["q2_discharged"] == 11 and r["q1_items"] == 12,
          f"{r.get('q2_discharged')}/{r.get('q1_items')}")
    check("  the remaining item names the T-90 capture proof",
          "T-90" in r["q4_remaining"], r["q4_remaining"][:80])
    check("  and it is the inactives kind that carries it, which the non-G0A "
          "basis cannot serve",
          X.G0A_KIND not in X.BASIS_KINDS[X.BASIS_ANCHORED_NON_G0A])
    check("  no artifact claims 12/12",
          RD.assert_no_artifact_claims_12_of_12().state is State.PASS)
    check("  and code cannot authorize NFL-1",
          r["q8_can_code_authorize_nfl1_without_owner"] == "NO")


def test_F2_the_stale_item1_reason_is_corrected_not_erased():
    print("\nF2. item 1's reason is corrected by a dated artifact")
    import json
    p = _REPO / "nfl" / "NFL_G0A_ITEM1_REASON_CORRECTION.json"
    check("the correction artifact exists", p.exists())
    d = json.loads(p.read_text())
    check("  it is dated", bool(d.get("recorded_utc")))
    check("  it records the superseded egress diagnosis verbatim",
          "egress alone" in d["old_diagnosis"]["as_written"])
    check("  it states the old diagnosis was correct WHEN WRITTEN, rather "
          "than calling it a mistake",
          d["old_diagnosis"]["was_correct_when_written"] is True)
    check("  it carries the measured evidence that superseded it",
          d["measured_correction"]["evidence"]["official_inactives"][
              "pass_captures"] > 50)
    check("  the numerical state is explicitly unchanged",
          d["numerical_state_unchanged"]["G0A"] == "11/12")
    check("  and the checklist itself was NOT rewritten -- history preserved",
          d["history_preserved"]["checklist_file_modified"] is False)
    chk = (_REPO / "nfl" / "NFL_G0A_CHECKLIST.md").read_text()
    check("  the original wording is still present in the checklist",
          "egress alone" in chk)
    r = RD.report()
    c = r["q4a_item1_reason_correction"]
    check("  machine-readable readiness POINTS at the correction",
          c["state"] == "RECORDED", str(c.get("state")))
    check("  and carries the current reason, not the stale one",
          "egress" not in c["current_reason"].lower(), c["current_reason"][:80])


def test_G_a_closed_window_cannot_be_rescued_by_the_new_workflow():
    print("\nG. the new workflow cannot backfill the two closed misses")
    # The generator emits the whole week, including the window that already
    # closed. Those cron entries are in the past and will never fire -- and if
    # one somehow did, retrieved_at would fall outside the window.
    closed = (dt.datetime(2026, 9, 7, 20, 0, tzinfo=UTC),
              dt.datetime(2026, 9, 8, 16, 0, tzinfo=UTC))
    e = X.eligibility(
        _decl(X.BASIS_ANCHORED_NON_G0A, "practice", window=closed),
        source="official_injury_report", capture_state="PASS",
        retrieved_at=dt.datetime.now(UTC),      # i.e. after it closed
        sha256="a" * 64, blob_path="nfl/vintage/x.html.gz",
        provenance_valid=True)
    t = e["targets"][0]
    check("a capture now cannot discharge a window that closed",
          not t["eligible"], str(t["refusals"]))
    check("  refused specifically on the window, not incidentally",
          "RETRIEVED_AT_OUTSIDE_DECLARED_WINDOW" in t["refusals"],
          str(t["refusals"]))
    cov = C.coverage(2026, 1, manifest_path=_REPO / "nfl"
                     / "vintage_manifest.jsonl")
    ids = {(d["game_id"], d["label"]) for d in cov.evidence["missed_detail"]}
    check("  and both original misses are still MISSED",
          {("2026_01_NE_SEA", "practice_a"),
           ("2026_01_SF_LA", "practice_mon")} <= ids, str(sorted(ids)))


def test_H_generator_refuses_to_emit_the_g0a_kind():
    print("\nH. the generator itself refuses the G0A kind")
    import nfl.tools.gen_status_schedule as G
    check("NON_G0A_KINDS is exactly practice and final_status",
          G.NON_G0A_KINDS == ("practice", "final_status"), str(G.NON_G0A_KINDS))
    check("  it does not contain the G0A kind", X.G0A_KIND not in G.NON_G0A_KINDS)
    check("  and it matches what the basis may discharge, so the workflow "
          "never fires for a target it cannot satisfy",
          set(G.NON_G0A_KINDS)
          == set(X.BASIS_KINDS[X.BASIS_ANCHORED_NON_G0A]))
    src = (_REPO / "nfl" / "tools" / "gen_t90_schedule.py").read_text()
    check("  and the G0A generator still anchors inactives ONLY",
          'ANCHORED_KINDS = ("inactives",)' in src)


def test_I_guard_deletion_the_basis_kind_restriction():
    print("\nI. guard deletion: the basis->kind restriction is load-bearing")
    def run():
        return _elig(X.BASIS_ANCHORED_NON_G0A, "inactives")["targets"][0][
            "eligible"]
    check("with the restriction in place, inactives is refused", not run())
    saved = dict(X.BASIS_KINDS)
    try:
        X.BASIS_KINDS[X.BASIS_ANCHORED_NON_G0A] = None      # remove the guard
        check("  with BASIS_KINDS bypassed, the non-G0A basis WOULD discharge "
              "inactives -- therefore the refusal came from the restriction",
              run())
    finally:
        X.BASIS_KINDS.clear()
        X.BASIS_KINDS.update(saved)
    check("  and the restriction is restored", not run())


def test_J_guard_deletion_the_workflow_name_mapping():
    print("\nJ. guard deletion: the workflow->basis mapping is load-bearing")
    ident = {"is_github_actions": True,
             "workflow": X.NON_G0A_ANCHORED_WORKFLOW, "event_name": "schedule"}
    check("with the mapping in place, the non-G0A workflow gets its own basis",
          X.declaration_basis(ident) == X.BASIS_ANCHORED_NON_G0A)
    with guard_bypassed("nfl.capture.execution", "declaration_basis",
                        replacement=lambda i: X.BASIS_ANCHORED):
        check("  bypassed to return the G0A basis, the same identity would "
              "discharge inactives -- therefore the mapping is what stops it",
              _elig(X.declaration_basis(ident), "inactives")["targets"][0][
                  "eligible"])
    check("  and it is restored", X.declaration_basis(ident)
          == X.BASIS_ANCHORED_NON_G0A)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f"{FAILED} check(s) failed in this module")
    if PASSED == 0:
        raise AssertionError("this module recorded ZERO checks")


if __name__ == "__main__":
    for _n in sorted(n for n in dir() if n.startswith("test_")):
        globals()[_n]()
    print(f"\n{PASSED} passed, {FAILED} failed")
    sys.exit(1 if FAILED else 0)
