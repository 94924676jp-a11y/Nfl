"""Per-game T-90 coverage, computed from the plan and the manifest.

WHY THIS MODULE EXISTS: TWO MODULES DISAGREED AND THE WEAKER ONE WAS PRINTING

Measured 2026-09-07, before this module was written:

    registry.unmet_targets(manifest) -> {'unmet': [], 'met': ['final_status',
                                         'inactives', 'practice'], ...}

All three perishable targets reported MET. At that moment no game had reached
its T-90 window -- the first is 2026-09-09T22:50Z, two days out -- and no
capture had ever been attributed to a game. `unmet_targets` answers "has a
source authorised for this kind ever been captured at all", which has no time
dimension and no game dimension. Read as coverage it says a Sunday poll of the
inactives page discharges a Thursday kickoff's T-90 obligation.

`schedule._clears` already refuses exactly that: for a GAME_SPECIFIC_KIND it
requires the capture to carry the target's own game_id, and the capture tool
records no game_id, so under `schedule` no inactives target is clearable. Two
modules, opposite answers to the same question, and the runner printed the
optimistic one. This module makes the game-anchored answer the one that gets
printed, and states plainly what the source-level answer does and does not mean.

WHAT "COVERED" MEANS HERE AND WHAT IT DOES NOT

Covered: a manifest PASS from a source authorised for that kind, whose
`retrieved_at` lies inside THIS target's own window, attributed to THIS game.
Nothing weaker counts, and in particular:

  * a capture in the right window from an unauthorised source does not count;
  * a capture from the right source outside the window does not count;
  * a capture of the right kind for another game does not count;
  * a run of the periodic cron does not count for anything by itself. Being
    awake is not an observation.

A window that has not closed yet is DEFERRED, never MISSED. Conflating "not yet"
with "failed" is the Class B failure and it would make every plan look broken
the moment it was written.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.capture.execution import eligible_targets  # noqa: E402
from nfl.capture.schedule import (GAME_SPECIFIC_KINDS, CaptureDue,  # noqa: E402
                                  season_plan)


def _parse_ts(v) -> Optional[dt.datetime]:
    if not v:
        return None
    try:
        d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _blob_ok(value: dict) -> tuple:
    """Does the raw artifact actually exist, and do its bytes hash correctly?

    Directive 7 §5 requires "a real persisted raw artifact" for discharge, and
    §9.9/§9.11 require that a persistence failure or a wrong hash PREVENTS
    coverage. A manifest row is a claim about a file; this opens the file. The
    two have already disagreed once in this project -- the `.reduced` blobs are
    named for a digest that is not their own -- so the row's word is not taken.
    """
    import gzip as _gzip, hashlib as _hashlib
    blob = (value or {}).get("blob")
    sha = (value or {}).get("sha256")
    if not blob:
        return False, "RAW_ARTIFACT_NOT_PERSISTED"
    if not sha or len(sha) != 64:
        return False, "RAW_SHA256_ABSENT_OR_MALFORMED"
    path = _REPO / blob
    if not path.exists():
        return False, f"RAW_ARTIFACT_MISSING_ON_DISK:{blob}"
    try:
        raw = (_gzip.open(path, "rb").read() if str(path).endswith(".gz")
               else path.read_bytes())
    except OSError as exc:
        return False, f"RAW_ARTIFACT_UNREADABLE:{type(exc).__name__}"
    if _hashlib.sha256(raw).hexdigest() != sha:
        return False, "RAW_SHA256_MISMATCH"
    return True, None


def performed_from_manifest(manifest_path, *, verify_artifacts: bool = True
                            ) -> Outcome:
    """Every capture that may discharge something, as `(retrieved_at, source,
    game_id)`, with the reasons anything was excluded.

    THE MANIFEST HAS TWO SCHEMAS AND THE FIRST VERSION OF THIS READ ONE

    Measured 2026-09-07 on the live manifest: 54 of 60 PASS rows nest the real
    clock under `value.provenance.retrieved_at`, and 6 older rows carry it at
    `value.retrieved_at`. This function originally read only the top level, so
    it silently dropped 54 rows -- 90% of the evidence -- and reported
    `total_captures: 6`. Both locations are read now, and a PASS row carrying
    NEITHER is a refusal rather than a skip.

    WHAT COUNTS AS ATTRIBUTED CHANGED UNDER DIRECTIVE 7

    Only `discharge_eligibility` entries marked eligible are emitted as
    attributed captures, and those exist only where the run DECLARED the target
    before fetching. The older `discharge_claims` field is read for reporting
    but discharges nothing: it inferred its target set from `retrieved_at` after
    the fact, which §6 forbids. Those rows stay in the manifest as history.
    """
    mp = pathlib.Path(manifest_path)
    if not mp.exists():
        return Outcome.not_applicable(
            "NO_MANIFEST", f"no manifest at {mp}; nothing has been captured "
                           f"through this record, so there are no performed "
                           f"captures to judge coverage against.")
    out, undated, n_pass, excluded = [], [], 0, []
    legacy = 0
    for line in mp.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("state") != "PASS":
            continue
        n_pass += 1
        val = row.get("value") or {}
        prov = val.get("provenance") or {}
        ts = _parse_ts(val.get("retrieved_at") or prov.get("retrieved_at"))
        if ts is None:
            undated.append(row.get("source"))
            continue
        if val.get("discharge_claims") and not val.get("discharge_eligibility"):
            legacy += 1

        # Unattributed entry: still clears team-week kinds, where one fetch of a
        # weekly report legitimately serves every game that team plays.
        out.append((ts, row.get("source"), None))

        ok, why = ((True, None) if not verify_artifacts
                   else _blob_ok(val))
        if not ok:
            excluded.append({"source": row.get("source"),
                             "capture_id": row.get("capture_id"),
                             "reason": why})
            continue
        for gid, _kind in eligible_targets(val):
            out.append((ts, row.get("source"), gid))

    if undated:
        return Outcome.blocked(
            "CAPTURE_CLOCK_UNREADABLE",
            f"{len(undated)} of {n_pass} PASS rows carry no readable "
            f"retrieved_at at value.retrieved_at or value.provenance."
            f"retrieved_at: {sorted(set(undated))}. An undated capture cannot "
            f"be placed inside or outside a window, and skipping it would "
            f"understate coverage silently.",
            cause=Cause.DATA, undated_sources=sorted(set(undated)),
            n_undated=len(undated), n_pass=n_pass)
    return Outcome.ok("CAPTURES_READ", value=out,
                      detail=f"{len(out)} dated PASS captures of {n_pass}; "
                             f"{len(excluded)} excluded on artifact "
                             f"verification; {legacy} legacy pre-Directive-7 "
                             f"rows discharge nothing",
                      n_captures=len(out), n_pass_rows=n_pass,
                      artifact_excluded=excluded, legacy_claim_rows=legacy)


def load_week_plan(season: int, week: int, vintage_dir=None) -> Outcome:
    """The capture plan for one week, built from the captured schedule snapshot.

    The schedule is itself a captured artifact rather than a constant, so the
    plan inherits its vintage. If no snapshot has been captured there is no plan
    and this refuses; inventing kickoff times to keep a report populated is the
    exact defect class this project exists to prevent.
    """
    vintage_dir = pathlib.Path(vintage_dir or (_REPO / "nfl" / "vintage"))
    snaps = sorted(vintage_dir.glob("schedules.*.csv.gz"),
                   key=lambda p: p.stat().st_mtime)
    if not snaps:
        return Outcome.blocked(
            "NO_SCHEDULE_SNAPSHOT",
            "no schedules artifact has been captured, so no kickoff time is "
            "known and no T-90 target can be located in time. There is no "
            "plan to check coverage against.",
            cause=Cause.DEPENDENCY, searched=str(vintage_dir))
    latest = snaps[-1]
    rows = [r for r in csv.DictReader(
                io.StringIO(gzip.open(latest, "rt").read()))
            if r.get("season") == str(season)
            and r.get("game_type") == "REG"
            and r.get("week") == str(week)]
    if not rows:
        return Outcome.blocked(
            "NO_GAMES_IN_SNAPSHOT",
            f"the schedule snapshot {latest.name} carries no {season} regular "
            f"season week {week} rows. An empty plan is not full coverage.",
            cause=Cause.DATA, snapshot=latest.name)
    plan = season_plan(rows)
    return Outcome.ok(
        "WEEK_PLAN_BUILT", value=plan,
        detail=f"{len(plan)} targets across {len(rows)} games, from "
               f"{latest.name}",
        snapshot=latest.name, n_games=len(rows), n_targets=len(plan))


def coverage(season: int, week: int, *, manifest_path,
             now: Optional[dt.datetime] = None, vintage_dir=None,
             verify_artifacts: bool = True) -> Outcome:
    """Per-target coverage for one week. The game-anchored answer."""
    now = now or dt.datetime.now(dt.timezone.utc)
    planned = load_week_plan(season, week, vintage_dir=vintage_dir)
    from sportsplatform.governance.outcome import State
    if planned.state is not State.PASS:
        return planned
    plan = planned.value
    read = performed_from_manifest(manifest_path,
                                   verify_artifacts=verify_artifacts)
    if read.state is State.BLOCKED:
        return read
    performed = read.value if read.state is State.PASS else []

    from nfl.capture.schedule import _clears
    covered, missed, pending = [], [], []
    for c in plan:
        if c.kind in ("seal", "unschedulable"):
            continue
        lo, hi = c.window
        hit = [p for p in performed if _clears(c, p)]
        if hit:
            covered.append((c, min(h[0] for h in hit)))
        elif hi <= now:
            missed.append(c)
        else:
            pending.append(c)

    summary = {
        "season": season, "week": week,
        "as_of_utc": now.isoformat(),
        "n_targets": len(covered) + len(missed) + len(pending),
        "covered": len(covered), "missed": len(missed),
        "not_yet_due": len(pending),
        "game_specific_kinds": list(GAME_SPECIFIC_KINDS),
        "attributed_captures": sum(1 for p in performed if p[2]),
        "total_captures": len(performed),
        "artifacts_verified": verify_artifacts,
        "artifact_excluded": read.evidence.get("artifact_excluded", []),
        "legacy_claim_rows": read.evidence.get("legacy_claim_rows", 0),
        "missed_detail": [c.as_dict() for c in missed],
        "next_window": min((c.as_dict() for c in pending),
                           key=lambda d: d["window_start_utc"], default=None),
    }

    if missed:
        return Outcome.fail(
            "PERISHABLE_WINDOWS_MISSED",
            f"{len(missed)} of {summary['n_targets']} targets had their window "
            f"close with no authorised, in-window, game-attributed capture. "
            f"These are not recoverable later: the pages they name are "
            f"overwritten in place.",
            **summary)
    if not covered:
        return Outcome.deferred(
            "NO_WINDOW_HAS_CLOSED_YET",
            f"{len(pending)} targets are planned and none has come due. "
            f"Nothing is covered and nothing is missed. This is the honest "
            f"state before a season opens, and it must not be read as "
            f"coverage -- registry.unmet_targets reports these kinds as met on "
            f"the strength of out-of-window polls, which is a source-level "
            f"answer to a game-level question.",
            owed=[c.as_dict() for c in pending][:5], **summary)
    return Outcome.ok(
        "WINDOWS_COVERED", value=summary,
        detail=f"{len(covered)} covered, {len(pending)} not yet due, none "
               f"missed", **summary)


def event_anchored(plan: list, cadence_minutes: int) -> Outcome:
    """Can a fixed periodic cron discharge these targets? Answer with evidence.

    This is the question the workflow comment answered by arithmetic: an 80
    minute window against a 30 minute cadence "lands at least twice inside it".
    Two things are wrong with reading that as fulfilment.

    First, coverage in TIME is not attribution to a GAME. A run that happens to
    be inside game A's window captures a league-wide page and records no
    game_id, so it discharges nothing under `_clears`.

    Second, the arithmetic assumes the cron fires. GitHub documents that
    scheduled runs may be delayed or dropped under load, and a dropped run is
    not a delayed one. The measured base rate here is n=3 scheduled runs, which
    cannot support any statement about drop probability.

    So this returns the timing fact and refuses to convert it into a discharge
    claim.
    """
    windows = [c for c in plan if c.kind in GAME_SPECIFIC_KINDS]
    if not windows:
        return Outcome.not_applicable(
            "NO_GAME_SPECIFIC_TARGETS",
            "this plan carries no per-game targets, so no event anchoring is "
            "required for it.")
    widths = {int((c.window[1] - c.window[0]).total_seconds() // 60)
              for c in windows}
    narrowest = min(widths)
    return Outcome.blocked(
        "PERIODIC_CADENCE_IS_NOT_EVENT_ANCHORING",
        f"{len(windows)} per-game targets, narrowest window {narrowest} "
        f"minutes, against a {cadence_minutes}-minute periodic cadence. A "
        f"periodic run can only ever make a capture LIKELY to fall inside a "
        f"window; it cannot make that capture attributable to the game whose "
        f"window it fell in, and `schedule._clears` correctly refuses an "
        f"unattributed capture for a game-specific kind. Closing this needs an "
        f"execution anchored on `next_target`, and a capture row carrying the "
        f"game_id it was taken for.",
        cause=Cause.DEPENDENCY,
        n_windows=len(windows), narrowest_window_minutes=narrowest,
        cadence_minutes=cadence_minutes,
        distinct_window_widths=sorted(widths))
