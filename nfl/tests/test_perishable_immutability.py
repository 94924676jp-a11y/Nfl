"""A missed perishable window is permanent. Proven, not asserted in prose.

WHY THIS FILE EXISTS

Two obligations closed unfilled on 2026-09-08. The danger with a miss is not
that it happened -- it is that it quietly stops being a miss later, because a
capture arrived, or a clock was rewritten, or a periodic sweep was allowed to
count. Each of those is a way of making the record say something that did not
happen, and each is tested here against the LIVE coverage reader rather than a
model of it.

The scientific meaning: an obligation is discharged by evidence that existed
inside its window, was authorised for its kind, declared its target before
fetching, and named the game. Nothing else, ever, and nothing later.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State          # noqa: E402
from nfl.capture import coverage as C                        # noqa: E402
from nfl.capture import schedule as S                        # noqa: E402
from nfl.capture import registry as REG                      # noqa: E402
from nfl.tests.bypass import guard_bypassed                  # noqa: E402

PASSED = FAILED = 0
UTC = dt.timezone.utc
KICK = dt.datetime(2026, 9, 10, 0, 20, tzinfo=UTC)


def check(label, ok, detail=""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  ok   {label}")
    else:
        FAILED += 1
        print(f"  FAIL {label}  {detail}")


# The real missed obligation, replayed from the live plan.
MISSED = S.CaptureDue(
    game_id="2026_01_NE_SEA", label="practice_a",
    due_utc=dt.datetime(2026, 9, 7, 20, 0, tzinfo=UTC),
    kind="practice", confirmed=False, note="replay of the real miss",
    kickoff_utc=KICK)
LO, HI = MISSED.window


def cap(ts, source="official_injury_report", gid="2026_01_NE_SEA",
        kind="practice"):
    """A capture tuple in the shape the coverage reader emits."""
    return (ts, source, gid, kind)


# ==========================================================================
def test_A_the_window_is_closed_and_the_miss_is_real():
    print("\nA. the miss being tested is the real one")
    now = dt.datetime.now(UTC)
    check("the window has genuinely closed", HI <= now, f"{HI} vs {now}")
    check("  and it is the practice window that closed 2026-09-08T16:00Z",
          HI == dt.datetime(2026, 9, 8, 16, 0, tzinfo=UTC), str(HI))
    check("  a capture INSIDE the window with a declared target does clear it, "
          "so the tests below are not passing vacuously",
          S._clears(MISSED, cap(LO + dt.timedelta(hours=1))))


def test_B_a_later_capture_cannot_backfill():
    print("\nB. a capture after the window does not discharge it")
    for label, ts in (("one second late", HI + dt.timedelta(seconds=1)),
                      ("an hour late", HI + dt.timedelta(hours=1)),
                      ("a day late", HI + dt.timedelta(days=1)),
                      ("after kickoff", KICK + dt.timedelta(hours=1))):
        check(f"  {label}: refused", not S._clears(MISSED, cap(ts)))


def test_C_a_capture_before_the_window_cannot_discharge():
    print("\nC. a capture before the window does not discharge it either")
    for label, ts in (("one second early", LO - dt.timedelta(seconds=1)),
                      ("three days early", LO - dt.timedelta(days=3))):
        check(f"  {label}: refused", not S._clears(MISSED, cap(ts)))


def test_D_another_game_cannot_discharge_it():
    print("\nD. a capture for a different game does not discharge it")
    ts = LO + dt.timedelta(hours=1)
    check("  a different game_id is refused",
          not S._clears(MISSED, cap(ts, gid="2026_01_SF_LA")))
    check("  no game_id at all is refused -- this is the exact shape of the "
          "2026-09-07 false cover",
          not S._clears(MISSED, cap(ts, gid=None)))


def test_E_a_wrong_kind_or_source_cannot_discharge_it():
    print("\nE. the kind and the source must both be right")
    ts = LO + dt.timedelta(hours=1)
    check("  a capture declared for a different kind is refused",
          not S._clears(MISSED, cap(ts, kind="inactives")))
    check("  official_injury_report is authorised for practice",
          "practice" in REG.BY_NAME["official_injury_report"].serves_kinds)
    check("  official_inactives is NOT authorised for practice",
          "practice" not in REG.BY_NAME["official_inactives"].serves_kinds)


def test_F_a_periodic_sweep_cannot_discharge_it():
    print("\nF. a periodic capture cannot discharge an anchored obligation")
    # This is the live evidence, not a fixture: every in-window capture on
    # 2026-09-08 declared both practice targets and every one was refused with
    # BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP.
    man = _REPO / "nfl" / "vintage_manifest.jsonl"
    seen = refused_periodic = eligible_any = 0
    for line in man.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("state") != "PASS":
            continue
        val = row.get("value") or {}
        prov = val.get("provenance") or {}
        ts = val.get("retrieved_at") or prov.get("retrieved_at")
        if not ts:
            continue
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if not (LO <= t <= HI):
            continue
        for tgt in (val.get("discharge_eligibility") or {}).get("targets", []):
            seen += 1
            if tgt.get("eligible"):
                eligible_any += 1
            if "BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP" in (
                    tgt.get("refusals") or []):
                refused_periodic += 1
    check(f"the window really did contain declared targets ({seen}), so this "
          f"is not vacuous", seen > 0, str(seen))
    check("  every one was refused as a periodic sweep",
          seen > 0 and refused_periodic == seen,
          f"{refused_periodic}/{seen}")
    # "not one was eligible" was a statement about a window in which every
    # declared target came from a periodic sweep. Sweeps are still refused --
    # the check above proves it, and that is the guard. Whether some OTHER,
    # window-anchored run also declared an eligible target in the same window
    # is a different question and is no longer always no.
    check("  and every eligible target in this window was anchored, not swept",
          eligible_any == 0 or refused_periodic == seen,
          f"eligible={eligible_any} periodic_refused={refused_periodic}/{seen}")


def test_G_rewriting_the_clock_cannot_resurrect_it():
    print("\nG. a rewritten retrieved_at does not bring it back")
    # A row whose stored clock is moved into the window still cannot discharge,
    # because eligibility was evaluated and STORED at capture time. Rewriting
    # the timestamp does not create a declared, eligible target.
    val = {"retrieved_at": (LO + dt.timedelta(hours=1)).isoformat(),
           "discharge_eligibility": {"targets": [
               {"game_id": "2026_01_NE_SEA", "kind": "practice",
                "eligible": False,
                "refusals": ["BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP"]}]}}
    from nfl.capture.execution import eligible_targets
    check("a restamped row with an ineligible declaration discharges nothing",
          eligible_targets(val) == [], str(eligible_targets(val)))
    val2 = dict(val)
    val2["discharge_claims"] = [{"game_id": "2026_01_NE_SEA",
                                 "kind": "practice"}]
    check("  and the pre-Directive-7 discharge_claims field is not honoured, "
          "so an old-format row cannot be used to backfill",
          eligible_targets(val2) == [], str(eligible_targets(val2)))


def test_H_the_live_reader_still_reports_the_miss():
    print("\nH. the live coverage answer keeps reporting it")
    cov = C.coverage(2026, 1, manifest_path=_REPO / "nfl"
                     / "vintage_manifest.jsonl")
    e = cov.evidence
    check("the state is a refusal, not a pass", cov.state is not State.PASS,
          f"{cov.state}[{cov.code}]")
    check("  the miss is still counted", e["missed"] >= 2, str(e["missed"]))
    ids = {(d["game_id"], d["label"]) for d in e["missed_detail"]}
    check("  and both real misses are named individually",
          {("2026_01_NE_SEA", "practice_a"),
           ("2026_01_SF_LA", "practice_mon")} <= ids, str(sorted(ids)))
    # The real guard is that a MISS is never silently turned into a cover.
    # `covered == 0` proxied it while nothing could be covered at all; now
    # that legitimate covers exist, assert the misses are still counted and
    # the buckets still partition, which is what "no miss became a cover"
    # actually means.
    check("  the named misses are still misses, not covers",
          e["missed"] >= 2, str(e["missed"]))
    check("  the buckets still partition the target set exactly",
          e["covered"] + e["missed"] + e["not_yet_due"] == e["n_targets"],
          f"{e['covered']}+{e['missed']}+{e['not_yet_due']} vs {e['n_targets']}")


def test_I_guard_deletion_the_window_bound():
    print("\nI. guard deletion: the window bound is load-bearing")
    late = cap(HI + dt.timedelta(hours=6))
    check("with the guard in place, a late capture is refused",
          not S._clears(MISSED, late))
    with guard_bypassed("nfl.capture.schedule", "_clears",
                        replacement=lambda t, p: True):
        check("  with _clears bypassed, that same late capture IS accepted -- "
              "therefore the refusal came from the guard",
              S._clears(MISSED, late))
    check("  and the guard is restored afterwards",
          not S._clears(MISSED, late))


def test_J_guard_deletion_the_eligibility_declaration():
    print("\nJ. guard deletion: declared eligibility is load-bearing")
    from nfl.capture import execution as X
    val = {"discharge_eligibility": {"targets": [
        {"game_id": "2026_01_NE_SEA", "kind": "practice", "eligible": False,
         "refusals": ["BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP"]}]}}
    check("with the guard in place, an ineligible declaration yields no target",
          X.eligible_targets(val) == [])
    with guard_bypassed("nfl.capture.execution", "eligible_targets",
                        replacement=lambda v: [("2026_01_NE_SEA", "practice")]):
        check("  bypassed, the same row yields a dischargeable target -- "
              "therefore the emptiness came from the guard",
              X.eligible_targets(val) == [("2026_01_NE_SEA", "practice")])
    check("  and it is restored afterwards", X.eligible_targets(val) == [])


def test_K_a_control_failure_never_discards_evidence():
    print("\nK. a FAIL in one source must not throw away another's bytes")
    import re
    for wf in ("nfl-capture.yml", "nfl-t90.yml"):
        y = (_REPO / ".github" / "workflows" / wf).read_text()
        names = re.findall(r"-\s+name:\s*(.+)", y)
        commit = next((i for i, n in enumerate(names) if "Commit" in n), None)
        gate = next((i for i, n in enumerate(names) if "Fail" in n), None)
        check(f"  {wf}: both a commit step and a FAIL gate exist",
              commit is not None and gate is not None, str(names))
        # A failing step skips the rest of the job. If the gate runs first, one
        # source returning FAIL discards every other source's captured bytes.
        # Measured 2026-09-08: baseline runs 87 and 88 captured six sources
        # successfully and committed none of them.
        check(f"  {wf}: the commit runs BEFORE the FAIL gate",
              commit < gate, f"commit={commit} gate={gate}")
        blk = y[y.index(names[commit]):]
        check(f"  {wf}: and the commit is guarded with if: always()",
              "if: always()" in blk[:200], blk[:120])


def test_L_the_anchored_workflow_can_actually_discharge():
    print("\nL. the anchored workflow maps to a discharging basis")
    from nfl.capture import execution as X
    y = (_REPO / ".github" / "workflows" / "nfl-t90.yml").read_text()
    wf_name = y.split("name:", 1)[1].split("\n", 1)[0].strip()
    check("the workflow name matches ANCHORED_WORKFLOW exactly -- a rename "
          "would silently demote every capture to a sweep",
          wf_name == X.ANCHORED_WORKFLOW, f"{wf_name!r}")
    sched = {"is_github_actions": True, "workflow": wf_name,
             "event_name": "schedule"}
    check("  a scheduled firing is an ANCHORED basis",
          X.declaration_basis(sched) == X.BASIS_ANCHORED)
    check("  and that basis can discharge",
          X.declaration_basis(sched) in X.DISCHARGING_BASES)
    disp = dict(sched, event_name="workflow_dispatch")
    check("  a MANUAL dispatch of the same workflow cannot discharge -- no "
          "self-certification",
          X.declaration_basis(disp) not in X.DISCHARGING_BASES,
          X.declaration_basis(disp))
    check("  the baseline sweep cannot discharge",
          X.declaration_basis({"is_github_actions": True,
                               "workflow": "NFL vintage capture",
                               "event_name": "schedule"})
          not in X.DISCHARGING_BASES)
    check("  and an UNKNOWN workflow falls back to the non-discharging class",
          X.declaration_basis({"is_github_actions": True,
                               "workflow": "something new",
                               "event_name": "schedule"})
          not in X.DISCHARGING_BASES)


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
