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


def performed_from_manifest(manifest_path) -> list:
    """Every successful capture as `(retrieved_at, source, game_id)`.

    `game_id` is None for every row today, and that is the honest reading rather
    than a placeholder: the capture tool fetches league-wide pages and records no
    game attribution, so no row can claim to be a particular game's T-90 capture.
    `schedule._clears` turns that None into a refusal for game-specific kinds,
    which is the correct direction -- unattributed evidence clears fewer targets,
    never more.
    """
    mp = pathlib.Path(manifest_path)
    if not mp.exists():
        return []
    out = []
    for line in mp.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("state") != "PASS":
            continue
        val = row.get("value") or {}
        ts = _parse_ts(val.get("retrieved_at"))
        if ts is None:
            continue
        out.append((ts, row.get("source"), val.get("game_id")))
    return out


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
             now: Optional[dt.datetime] = None, vintage_dir=None) -> Outcome:
    """Per-target coverage for one week. The game-anchored answer."""
    now = now or dt.datetime.now(dt.timezone.utc)
    planned = load_week_plan(season, week, vintage_dir=vintage_dir)
    from sportsplatform.governance.outcome import State
    if planned.state is not State.PASS:
        return planned
    plan = planned.value
    performed = performed_from_manifest(manifest_path)

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
