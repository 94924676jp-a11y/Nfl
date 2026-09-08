"""What a capture execution was FOR, declared before it fetches anything.

DIRECTIVE 7 §6 NAMES THE DEFECT IN THE PREVIOUS VERSION OF THIS

    "Do not infer the target set after the fact from timestamps alone."

That is exactly what `attribution.claims_for` did. It took `retrieved_at` --
available only once the bytes had arrived -- and worked out which windows
contained it. Every claim it produced was a post-hoc reading of a clock, and a
capture that wandered into a window by accident was indistinguishable from one
taken because that window was open.

Directive 7 §2 sets the standard the record has to meet: a capture row may carry
a game_id only because "this capture execution was intentionally scheduled to
satisfy that game's evidence obligation". Intent is a fact about the execution,
so it must be written down BEFORE the execution does anything. That is what this
module is: the declaration is built at run start, from the plan, and the bytes
are then judged against it.

FOUR SCOPES, DELIBERATELY NOT ONE FIELD (§2)

  source_artifact_scope   what the retrieved bytes actually cover. nfl.com's
                          inactives page is LEAGUE_WIDE and stays league-wide no
                          matter which game we fetched it for.
  execution_target_scope  the game obligations this run set out to satisfy.
                          THIS is where a game_id lives.
  parsed_row_applicability   which team/game a parsed ROW applies to. Parser
                          territory, downstream, not decided here.
  coverage_obligation     which target a capture is permitted to discharge.
                          Computed from the other three plus the evidence.

Collapsing any two of these produces a specific lie. Collapsing the first two
says the league page is a document about one game. Collapsing the second and
fourth says intending to capture something is the same as having captured it.

INTENT IS NECESSARY AND NOWHERE NEAR SUFFICIENT (§14)

A declaration is a statement of what a run meant to do. It discharges nothing.
`eligibility()` below re-checks the bytes against the declared target and can
refuse for any of eight named reasons, and `coverage` re-checks the whole thing
again from persisted artifacts. Declaring a target the run then failed to
capture leaves the target exactly as open as it was.

WHY A PERIODIC SWEEP CANNOT DISCHARGE, EVEN IN-WINDOW (§5)

Directive 7 §5 is explicit: "A generic background capture does not discharge
it", and §6 forbids letting one unattributed capture "accidentally satisfy N
games through timing coincidence". The `*/30` baseline waking inside a window is
that coincidence. So a sweep records what it saw -- the evidence is real and is
kept -- and discharges nothing.

This reverses something I told the owner in the previous report, where I said a
baseline run landing inside a window "counts exactly the same". Under §5 it does
not, and the directive is right: the whole point of anchoring is that the
execution knew what it was for.
"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

DECLARATION_VERSION = "execution_target/1.0.0"

# The workflow whose cron entries are GENERATED from kickoff times. A run of
# this workflow, fired by the scheduler, is the only thing that constitutes an
# intentionally targeted execution.
ANCHORED_WORKFLOW = "NFL T-90 anchored capture"

# A SECOND anchored path, deliberately separate, serving the obligations the
# G0A workflow does not: practice and final_status. It exists because those
# kinds had no anchored execution at all -- ANCHORED_KINDS is ("inactives",) --
# so two of them closed unfilled on 2026-09-08 despite an authorised source
# publishing rows throughout the window. See P3A.
#
# IT IS ISOLATED FROM G0A BY CONSTRUCTION, NOT BY CONVENTION. Its basis is a
# different constant and that constant is restricted to a fixed kind set below,
# so it cannot discharge `inactives` even if it is fired inside the T-90 window
# by an authorised source. The G0A obligation is reachable only from
# ANCHORED_WORKFLOW.
NON_G0A_ANCHORED_WORKFLOW = "NFL status anchored capture"

# How this run came to be pointed at a target, and whether that basis is capable
# of discharging one at all.
BASIS_ANCHORED = "SCHEDULED_WINDOW_ANCHORED"    # cron generated for the window
BASIS_ANCHORED_NON_G0A = "SCHEDULED_WINDOW_ANCHORED_NON_G0A"
BASIS_OPERATOR = "OPERATOR_TARGETED"            # a person dispatched it
BASIS_SWEEP = "PERIODIC_SWEEP"                  # the */30 baseline
BASIS_LOCAL = "LOCAL_INVOCATION"                # a developer's machine

# Only the first discharges. Operator dispatch is deliberately excluded: §11
# says a manually dispatched run is not equivalent proof, and a mechanism that
# let me dispatch a workflow during a live window and record a discharge would
# be a way to hand-write the result of the one test this gate exists for.
DISCHARGING_BASES = (BASIS_ANCHORED, BASIS_ANCHORED_NON_G0A)

# WHICH KINDS EACH BASIS MAY DISCHARGE. `None` means "no restriction from the
# basis" -- the source authorisation and the window still apply. This map is
# the structural isolation: the non-G0A basis is confined to a tuple that does
# not contain "inactives", so widening it is an explicit, reviewable edit
# rather than a side effect of adding a cron entry.
BASIS_KINDS: dict = {
    BASIS_ANCHORED: None,
    BASIS_ANCHORED_NON_G0A: ("practice", "final_status"),
}

# The one obligation kind that carries the outstanding G0A item. Reachable only
# from ANCHORED_WORKFLOW.
G0A_KIND = "inactives"
assert G0A_KIND not in BASIS_KINDS[BASIS_ANCHORED_NON_G0A], (
    "the non-G0A basis must never be able to discharge the G0A kind")

# The page is what it is regardless of why we fetched it (§2).
LEAGUE_WIDE = "LEAGUE_WIDE"


def executor_identity() -> dict:
    """Who is running this, from the environment rather than from assumption."""
    env = os.environ.get
    return {
        "workflow": env("GITHUB_WORKFLOW"),
        "run_id": env("GITHUB_RUN_ID"),
        "run_attempt": env("GITHUB_RUN_ATTEMPT"),
        "run_number": env("GITHUB_RUN_NUMBER"),
        "event_name": env("GITHUB_EVENT_NAME"),
        "repository": env("GITHUB_REPOSITORY"),
        "ref": env("GITHUB_REF"),
        "sha": env("GITHUB_SHA"),
        "runner_os": env("RUNNER_OS"),
        "is_github_actions": env("GITHUB_ACTIONS") == "true",
    }


def declaration_basis(ident: dict) -> str:
    """Classify the execution. Fail-safe: anything unrecognised is a sweep.

    An unknown workflow must never fall through to the discharging class. The
    default has to be the one that cannot certify anything.
    """
    if not ident.get("is_github_actions"):
        return BASIS_LOCAL
    if ident.get("workflow") == ANCHORED_WORKFLOW:
        return (BASIS_ANCHORED if ident.get("event_name") == "schedule"
                else BASIS_OPERATOR)
    if ident.get("workflow") == NON_G0A_ANCHORED_WORKFLOW:
        return (BASIS_ANCHORED_NON_G0A if ident.get("event_name") == "schedule"
                else BASIS_OPERATOR)
    return BASIS_SWEEP


def declare(plan: list, *, declared_at: Optional[dt.datetime] = None,
            identity: Optional[dict] = None,
            plan_snapshot: Optional[str] = None) -> Outcome:
    """The target set this execution is attempting, fixed BEFORE any fetch.

    `declared_at` is the run's own start, not a byte-arrival time -- that clock
    does not exist yet, and the whole point of declaring here is that it does
    not exist yet.

    Targets are those whose window contains `declared_at`. On an anchored run
    that set is the reason the cron entry exists at all; on a sweep it is merely
    what happened to be open, which is why the basis is recorded beside it and
    why a sweep cannot discharge.
    """
    if declared_at is None:
        declared_at = dt.datetime.now(dt.timezone.utc)
    if declared_at.tzinfo is None:
        declared_at = declared_at.replace(tzinfo=dt.timezone.utc)
    ident = identity if identity is not None else executor_identity()
    basis = declaration_basis(ident)

    if not plan:
        return Outcome.blocked(
            "DECLARATION_NO_PLAN",
            "no capture plan available, so this execution cannot say what it is "
            "for. An execution that cannot name its target must not be recorded "
            "as having satisfied one.",
            cause=Cause.DEPENDENCY, basis=basis)

    targets = []
    for c in plan:
        if c.kind in ("seal", "unschedulable"):
            continue
        lo, hi = c.window
        if lo <= declared_at <= hi:
            targets.append({
                "game_id": c.game_id,
                "kind": c.kind,
                "label": c.label,
                "window_start_utc": lo.isoformat(),
                "window_end_utc": hi.isoformat(),
                "due_utc": c.due_utc.isoformat(),
                "kickoff_utc": (c.kickoff_utc.isoformat()
                                if c.kickoff_utc else None),
                "cadence_confirmed": c.confirmed,
            })

    return Outcome.ok(
        "EXECUTION_TARGETS_DECLARED",
        value={
            "declaration_version": DECLARATION_VERSION,
            "declared_at": declared_at.isoformat(),
            "declared_before_fetch": True,
            "basis": basis,
            "basis_can_discharge": basis in DISCHARGING_BASES,
            "executor": ident,
            "plan_snapshot": plan_snapshot,
            "targets": targets,
            "note": ("Intent, recorded before any bytes were requested. It "
                     "discharges nothing on its own: eligibility() re-checks "
                     "the bytes against these targets and coverage re-checks "
                     "the whole chain from persisted artifacts."),
        },
        detail=(f"{basis}: {len(targets)} target(s) declared at "
                f"{declared_at.isoformat()}"),
        basis=basis, n_targets=len(targets))


# --- after the bytes arrive -------------------------------------------------
def eligibility(declaration: dict, *, source: str, capture_state: str,
                retrieved_at, sha256: Optional[str],
                blob_path: Optional[str],
                provenance_valid: bool) -> dict:
    """Per declared target: may THIS capture discharge it, and if not, why not.

    Every refusal is named. A single boolean would make an out-of-window capture
    and an unauthorised source look like the same event, and they need different
    responses -- one is a scheduling problem, the other is a governance one.
    """
    from nfl.capture.registry import can_discharge

    out = []
    ts = _parse(retrieved_at)
    basis = declaration.get("basis")
    for t in declaration.get("targets", []):
        reasons = []
        if capture_state != "PASS":
            reasons.append(f"CAPTURE_NOT_PASS:{capture_state}")
        if not can_discharge(source, t["kind"]):
            reasons.append("SOURCE_NOT_AUTHORISED_FOR_KIND")
        if basis not in DISCHARGING_BASES:
            reasons.append(
                "MANUAL_DISPATCH_NOT_SELF_CERTIFYING" if basis == BASIS_OPERATOR
                else f"BASIS_CANNOT_DISCHARGE:{basis}")
        else:
            allowed = BASIS_KINDS.get(basis)
            if allowed is not None and t["kind"] not in allowed:
                # The isolation. A non-G0A anchored run fired inside the T-90
                # window by an authorised source still cannot discharge the
                # inactives obligation.
                reasons.append(f"BASIS_NOT_AUTHORISED_FOR_KIND:{basis}")
        if ts is None:
            reasons.append("RETRIEVED_AT_UNREADABLE")
        else:
            lo, hi = _parse(t["window_start_utc"]), _parse(t["window_end_utc"])
            if not (lo <= ts <= hi):
                # Declared inside the window, bytes landed outside it. The
                # declaration stands as a record of intent and the capture is
                # still real evidence -- it just is not THIS target's evidence.
                reasons.append("RETRIEVED_AT_OUTSIDE_DECLARED_WINDOW")
        if not sha256 or len(sha256) != 64:
            reasons.append("RAW_SHA256_ABSENT_OR_MALFORMED")
        if not blob_path:
            reasons.append("RAW_ARTIFACT_NOT_PERSISTED")
        if not provenance_valid:
            reasons.append("PROVENANCE_INVALID")
        out.append({
            "game_id": t["game_id"], "kind": t["kind"],
            "eligible": not reasons,
            "refusals": reasons,
            "window_start_utc": t["window_start_utc"],
            "window_end_utc": t["window_end_utc"],
            "kickoff_utc": t.get("kickoff_utc"),
        })
    return {
        "source_artifact_scope": LEAGUE_WIDE,
        "scope_note": ("The retrieved page covers every game. Fetching it for "
                       "one target does not make the artifact that target's "
                       "document; execution_target_scope is a separate field "
                       "for exactly that reason."),
        "evaluated_at_clock": "retrieved_at",
        "targets": out,
        "n_eligible": sum(1 for e in out if e["eligible"]),
    }


def _parse(ts) -> Optional[dt.datetime]:
    if isinstance(ts, dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
    if not ts:
        return None
    try:
        d = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def eligible_targets(manifest_value: dict) -> list:
    """(game_id, kind) pairs a stored row is permitted to discharge.

    Reads only the new field. Rows written before Directive 7 carry the old
    post-hoc `discharge_claims`, and those are deliberately NOT honoured here:
    they were inferred from timestamps, which is the thing §6 forbids. They stay
    in the manifest as history and discharge nothing.
    """
    block = (manifest_value or {}).get("discharge_eligibility") or {}
    return [(t["game_id"], t["kind"]) for t in block.get("targets", [])
            if t.get("eligible")]
