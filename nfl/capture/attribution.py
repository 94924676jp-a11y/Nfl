"""Which game(s) a capture was taken FOR. The missing half of the T-90 proof.

THE GAP THIS CLOSES

`schedule._clears` has always required a game-specific target to be cleared by a
capture carrying that target's own `game_id`. The capture tool recorded no
`game_id`, so under `_clears` no inactives target was ever clearable -- measured
2026-09-07: 63 week-1 targets, 0 covered, 0 of 60 captures attributed. The
runner could execute perfectly inside a window and the manifest would not say
which game the execution was for.

Authorized narrowly by the owner on 2026-09-07 alongside event-anchored
execution, and deliberately nothing else.

A CLAIM, NOT A VERDICT

What this module writes onto a capture row is a CLAIM: at `retrieved_at`, these
targets' windows were open and this source is authorised to serve their kind.
`coverage` re-verifies every claim against the plan independently and never
takes the claim's word for it, so a wrong or forged claim cannot discharge
anything. That asymmetry is on purpose -- the capture layer proposes, the
accounting layer disposes.

THE CLOCK IS `retrieved_at` AND ONLY `retrieved_at`

Not `requested_at`, not the workflow's start time, not `generated_at`. A request
issued at T-91 whose bytes arrive at T-89 captured the T-89 page; a request
issued inside the window whose bytes arrive after kickoff captured the wrong
information state. The clock that decides is the one on the bytes.

WHAT A CLAIM STILL DOES NOT PROVE

That the page actually listed that game's inactives. It proves the official
artifact was retrieved during that game's window, which is the obligation. The
80-minute window exists precisely because publication inside it is not
instantaneous, and repeated captures across the window are what show when the
list appeared. Confirming the content names the game is parser work and is NOT
claimed here.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

CLAIM_VERSION = "discharge_claim/1.0.0"


def _parse(ts) -> Optional[dt.datetime]:
    if isinstance(ts, dt.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)
    if not ts:
        return None
    try:
        d = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def claims_for(source: str, retrieved_at, plan: list) -> Outcome:
    """Targets this capture may claim, judged on timing AND source authority.

    Returns PASS with a possibly-EMPTY list. An empty list is the ordinary
    answer -- most captures happen outside every window -- and it is a result,
    not an absence, so it is returned rather than blocked on. What IS blocked on
    is an unreadable clock: a capture whose retrieval time cannot be parsed
    cannot be placed inside or outside any window, and guessing would be the
    whole defect.
    """
    ts = _parse(retrieved_at)
    if ts is None:
        return Outcome.blocked(
            "ATTRIBUTION_CLOCK_UNREADABLE",
            f"{source}: retrieved_at {retrieved_at!r} is not a timestamp, so "
            f"this capture cannot be placed inside or outside a window. "
            f"Attributing it anyway would invent the one fact the T-90 proof "
            f"rests on.", cause=Cause.DATA, source=source)
    if not plan:
        return Outcome.blocked(
            "ATTRIBUTION_NO_PLAN",
            f"{source}: no capture plan supplied, so no target can be named. "
            f"An empty plan is not 'no targets were open' -- it is not knowing.",
            cause=Cause.DEPENDENCY, source=source)

    from nfl.capture.registry import can_discharge

    claims = []
    for c in plan:
        if c.kind in ("seal", "unschedulable"):
            continue
        lo, hi = c.window
        if not (lo <= ts <= hi):
            continue
        # Timing alone is never enough. A routine mirror poll landing inside the
        # inactives window must not claim it.
        if not can_discharge(source, c.kind):
            continue
        claims.append({
            "game_id": c.game_id,
            "kind": c.kind,
            "label": c.label,
            "window_start_utc": lo.isoformat(),
            "window_end_utc": hi.isoformat(),
            "due_utc": c.due_utc.isoformat(),
            "cadence_confirmed": c.confirmed,
            "seconds_into_window": int((ts - lo).total_seconds()),
        })

    return Outcome.ok(
        "DISCHARGE_CLAIMS", value={
            "claim_version": CLAIM_VERSION,
            "source": source,
            "clock": "retrieved_at",
            "retrieved_at": ts.isoformat(),
            "authority": "DERIVED_DETERMINISTIC",
            "verified_by": "nfl.capture.coverage -- this is a claim, not a "
                           "verdict; coverage re-checks every entry against the "
                           "plan and does not trust this record.",
            "claims": claims,
        },
        detail=(f"{len(claims)} target(s) claimable by {source} at "
                f"{ts.isoformat()}: "
                + ", ".join(sorted({c['game_id'] for c in claims})
                            )[:200] if claims else
                f"no target window open for {source} at {ts.isoformat()}"),
        n_claims=len(claims))


def week_plan_for(season: int, week: int) -> Outcome:
    """The plan a capture is judged against. Thin, so the capture tool has one
    import and one failure mode rather than reimplementing the lookup."""
    from nfl.capture.coverage import load_week_plan
    return load_week_plan(season, week)


def claimed_game_ids(manifest_value: dict) -> list:
    """Every game_id a stored capture row claims. Tolerates rows written before
    this module existed, which claim nothing rather than claiming everything."""
    block = (manifest_value or {}).get("discharge_claims") or {}
    return [c["game_id"] for c in block.get("claims", []) if c.get("game_id")]
