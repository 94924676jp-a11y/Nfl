"""Directive 7 §10 pre-flight, as a command rather than an assertion.

Everything below is checked against the repository, the manifest and the plan,
and each answer is a state with a reason. Nothing here marks anything covered
and nothing writes to the production manifest -- §10 forbids both, and a
pre-flight that could alter the thing it inspects would be worthless anyway.

    python3.12 nfl/tools/preflight_t90.py --season 2026 --week 1
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

MANIFEST = _REPO / "nfl" / "vintage_manifest.jsonl"


def _checks(season: int, week: int) -> list:
    from nfl.capture.coverage import coverage, load_week_plan
    from nfl.capture.execution import (ANCHORED_WORKFLOW, DISCHARGING_BASES,
                                       declaration_basis)
    from nfl.tools.gen_t90_schedule import WORKFLOW, render

    out = []
    now = dt.datetime.now(dt.timezone.utc)

    # 1. the anchored workflow exists and is what the generator produces
    if not WORKFLOW.exists():
        out.append(("anchored workflow present", Outcome.fail(
            "WORKFLOW_ABSENT", f"{WORKFLOW} does not exist.")))
    else:
        r = render(season, week)
        drift = (r.state is State.PASS and WORKFLOW.read_text() != r.value)
        out.append(("anchored workflow matches the current schedule",
                    Outcome.fail("WORKFLOW_STALE",
                                 "the committed cron no longer matches the "
                                 "captured schedule; regenerate it.")
                    if drift else Outcome.ok(
                        "WORKFLOW_CURRENT", value=WORKFLOW.name,
                        detail=f"{r.evidence.get('n_entries')} cron entries, "
                               f"schedule identity "
                               f"{r.evidence.get('schedule_identity')}")))

    # 2. the plan, and the first target still ahead of us
    plan = load_week_plan(season, week)
    if plan.state is not State.PASS:
        out.append(("week plan", plan))
        return out
    ia = sorted((c for c in plan.value if c.kind == "inactives"),
                key=lambda c: c.due_utc)
    upcoming = [c for c in ia if c.window[1] > now]
    if not upcoming:
        out.append(("a week-1 inactives window still lies ahead",
                    Outcome.fail(
                        "ALL_WINDOWS_CLOSED",
                        f"every week {week} inactives window has closed; "
                        f"pre-flight is too late to change anything.")))
    else:
        first = upcoming[0]
        lo, hi = first.window
        out.append(("first upcoming inactives target", Outcome.ok(
            "FIRST_TARGET", value=first.game_id,
            detail=f"{first.game_id}: window {lo.isoformat()} -> "
                   f"{hi.isoformat()}, kickoff "
                   f"{first.kickoff_utc.isoformat()}, opens in "
                   f"{(lo - now).total_seconds() / 3600:.1f}h")))
        out.append(("the window is exactly the owner's T-90 -> T-10",
                    Outcome.ok("WINDOW_UNCHANGED", value=80,
                               detail=f"{int((hi - lo).total_seconds() // 60)} "
                                      f"minutes wide; opens at kickoff minus "
                                      f"{int((first.kickoff_utc - lo).total_seconds() // 60)} min")
                    if (hi - lo) == dt.timedelta(minutes=80)
                    and (first.kickoff_utc - lo) == dt.timedelta(minutes=90)
                    else Outcome.fail(
                        "WINDOW_ALTERED",
                        "the inactives window is no longer T-90 -> T-10.")))
        # 3. that target must currently be UNCOVERED. If it already reads
        #    covered before the event, the gate is broken, not passed.
        cov = coverage(season, week, manifest_path=MANIFEST, now=now)
        covered_now = (cov.state is State.PASS
                       and cov.evidence.get("covered", 0) > 0)
        out.append(("the first target is not already covered",
                    Outcome.fail(
                        "TARGET_ALREADY_COVERED",
                        "coverage reports a covered target before the event. "
                        "Nothing should be covered yet.")
                    if covered_now else Outcome.ok(
                        "TARGET_OPEN", value=first.game_id,
                        detail=f"coverage says {cov.state.value}[{cov.code}]: "
                               f"covered={cov.evidence.get('covered')}, "
                               f"not_yet_due={cov.evidence.get('not_yet_due')}")))

    # 4. the executor can actually write. Checked by looking at what it has
    #    already done rather than by reading permissions we cannot verify.
    try:
        log = subprocess.run(
            ["git", "log", "--format=%an", "-40"], cwd=_REPO,
            capture_output=True, text=True, timeout=20).stdout.split("\n")
    except (OSError, subprocess.SubprocessError) as exc:
        log = []
        out.append(("git history readable", Outcome.blocked(
            "GIT_UNAVAILABLE", str(exc), cause=Cause.ENVIRONMENT)))
    bot = sum(1 for a in log if a.strip() == "nfl-capture[bot]")
    out.append(("the runner has already pushed evidence unattended",
                Outcome.ok("RUNNER_CAN_PUSH", value=bot,
                           detail=f"{bot} of the last {len(log)} commits were "
                                  f"authored by nfl-capture[bot]")
                if bot else Outcome.fail(
                    "RUNNER_HAS_NEVER_PUSHED",
                    "no commit by nfl-capture[bot] in recent history; the "
                    "executor's write path is unproven.")))

    # 5. the official sources have returned real content, and their artifacts
    #    still verify byte-for-byte.
    from nfl.capture.coverage import _blob_ok
    import json as _json
    seen = {}
    for line in MANIFEST.read_text().splitlines():
        if not line.strip():
            continue
        row = _json.loads(line)
        if row.get("state") != "PASS":
            continue
        src = row.get("source")
        if src not in ("official_inactives", "official_injury_report"):
            continue
        ok, why = _blob_ok(row.get("value") or {})
        s = seen.setdefault(src, {"ok": 0, "bad": 0, "why": set()})
        s["ok" if ok else "bad"] += 1
        if not ok:
            s["why"].add(why.split(":")[0])
    for src in ("official_inactives", "official_injury_report"):
        s = seen.get(src)
        out.append((f"{src}: real content, artifacts verify",
                    Outcome.ok("SOURCE_VERIFIED", value=s["ok"],
                               detail=f"{s['ok']} captures verify byte-for-byte, "
                                      f"{s['bad']} do not")
                    if s and s["ok"] and not s["bad"] else Outcome.fail(
                        "SOURCE_UNVERIFIED",
                        f"{src}: {s or 'never captured'}; "
                        f"{sorted(s['why']) if s else ''}")))

    # 6. failure paths cannot become silent success
    from nfl.capture.execution import BASIS_SWEEP
    out.append(("a sweep cannot discharge",
                Outcome.ok("BASIS_GATE_TIGHT", value=list(DISCHARGING_BASES),
                           detail=f"only {list(DISCHARGING_BASES)} may "
                                  f"discharge")
                if BASIS_SWEEP not in DISCHARGING_BASES else Outcome.fail(
                    "BASIS_GATE_OPEN", "a periodic sweep can discharge.")))
    out.append(("an unknown workflow falls back to non-discharging",
                Outcome.ok("BASIS_FAILSAFE", value=True, detail="unknown "
                           "workflow classifies as a sweep")
                if declaration_basis(
                    {"is_github_actions": True, "workflow": "?",
                     "event_name": "schedule"}) not in DISCHARGING_BASES
                else Outcome.fail("BASIS_FAILSAFE_OPEN",
                                  "an unknown workflow can discharge.")))
    out.append(("the anchored workflow name matches the generated file",
                Outcome.ok("WORKFLOW_NAME_MATCHES", value=ANCHORED_WORKFLOW,
                           detail="execution.ANCHORED_WORKFLOW is the name the "
                                  "generator writes")
                if WORKFLOW.exists()
                and f"name: {ANCHORED_WORKFLOW}" in WORKFLOW.read_text()
                else Outcome.fail(
                    "WORKFLOW_NAME_MISMATCH",
                    f"execution.ANCHORED_WORKFLOW is {ANCHORED_WORKFLOW!r} but "
                    f"the workflow file does not declare that name, so no run "
                    f"of it will ever classify as anchored.")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()

    results = _checks(args.season, args.week)
    worst = 0
    print(f"T-90 PRE-FLIGHT  season {args.season} week {args.week}  "
          f"{dt.datetime.now(dt.timezone.utc).isoformat()}\n")
    for label, o in results:
        mark = {"PASS": "ok  ", "FAIL": "FAIL", "BLOCKED": "BLKD",
                "DEFERRED": "DEFR", "NOT_APPLICABLE": "n/a "}[o.state.value]
        print(f"  {mark}  {label}")
        print(f"        {o.detail[:150]}")
        if o.state in (State.FAIL, State.BLOCKED):
            worst = 1
    n_fail = sum(1 for _l, o in results if o.state is State.FAIL)
    print(f"\n{len(results)} checks, {n_fail} failing")
    if n_fail:
        print("PRE-FLIGHT NOT CLEAR -- do not expect the first window to "
              "produce usable evidence until these are fixed.")
    return worst


if __name__ == "__main__":
    sys.exit(main())
