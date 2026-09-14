"""Directive 7 §10 pre-flight, as a command rather than an assertion.

Everything below is checked against the repository, the manifest and the plan,
and each answer is a state with a reason. Nothing here marks anything covered
and nothing writes to the production manifest -- §10 forbids both, and a
pre-flight that could alter the thing it inspects would be worthless anyway.

    python3.12 nfl/tools/preflight_t90.py --season 2026 --week 1

THE FALSE GREEN THIS VERSION EXISTS TO END, MEASURED BEFORE IT WAS WRITTEN

Run at 2026-09-14T11:52Z, 10.9 hours before the last open week-1 window, with
the anchored executor dead since 2026-09-11T00:44Z and 47 of 63 week-1 targets
already closed unfilled, this command printed:

    10 checks, 0 failing

Two separate mechanisms produced that. Both are repaired below.

  1. `the runner has already pushed evidence unattended` answered "has the
     executor EVER pushed" -- 198 times, so PASS -- and printed the date of the
     most recent push as decoration. A capability is not a liveness property,
     and the comment in this file correctly says so; what it did not do is
     CHECK the liveness property anywhere else. Nothing in this repository
     noticed that every scheduled workflow stopped, all four of them at once,
     on 2026-09-11T03:38Z. Coverage cannot notice: a target is DEFERRED until
     its window closes, so the alarm arrives only after the evidence is
     unrecoverable. That is the whole defect in one sentence -- the only
     detector was downstream of the loss.

  2. `the first target is not already covered` CALLED coverage, received
     `FAIL[PERISHABLE_WINDOWS_MISSED]  covered=15`, printed that string, and
     marked itself `ok`. It failed only on `covered > 0` while coverage was in
     PASS, so a coverage FAIL was structurally invisible to it.

TWO RESULT SETS, AND WHY THEY ARE SEPARATE FUNCTIONS

`_checks()` asks whether the MECHANISM is correctly built: does the anchored
workflow exist, does its cron still match the captured kickoffs, is the window
still T-90 -> T-10, can a sweep discharge, would a renamed workflow silently
demote every capture. Those are facts about this repository, deterministic, and
they pass today.

`_live_state()` asks whether the WORLD is in a state where the next window can
produce evidence: is the executor alive, does a cron entry actually fire inside
the next window, what does the store already hold, what has already been lost.
Those are observations, and today three of them fail.

They are separate because they are different questions and because
`nfl/tests/test_preflight.py::test_A` asserts that every `_checks()` result
passes today -- an assertion about the mechanism, which is sound, and which
would force a live-state observation to be softened to keep it green. Neither
set is privileged: `main()` prints both, counts both, and exits non-zero on a
failure in either. The new test module
`nfl/tests/test_capture_obligations.py` locks that exit code so the split
cannot be used to hide a failure.

WHAT THIS STILL CANNOT DO, AND IT IS NOT A SMALL THING

Nothing that runs inside GitHub Actions can detect GitHub Actions being off,
and nothing in this checkout can read the Actions run history -- absence of a
commit is not proof that a run did not start. The liveness check below measures
the arrival of EVIDENCE, which is the observable consequence, not the cause. The
cause is filed as OUT-011 in docs/AGENT_OUTBOX.md and needs the Actions API.
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
BASELINE_WORKFLOW = _REPO / ".github" / "workflows" / "nfl-capture.yml"

# HOW LONG SILENCE IS ALLOWED TO LAST, DERIVED RATHER THAN CHOSEN.
#
# The baseline capture workflow declares its own cadence in its cron entry, and
# that number is read from the file rather than written here. The only judgement
# is the multiplier, and it is the smallest one that can distinguish the two
# things GitHub's documentation distinguishes: scheduled runs "may be delayed
# during periods of high load". A delay that pushes one run past the next tick
# is indistinguishable from a drop, so a single missed tick proves nothing. TWO
# consecutive ticks with no evidence cannot be one delayed run.
#
# It is therefore a floor on detection, not a tuned threshold: raising it hides
# outages, lowering it cannot make the check more correct because one tick is
# genuinely ambiguous. Measured gap at the time of writing, 2026-09-14T11:52Z
# against a last GitHub-Actions manifest row of 2026-09-11T00:43:57Z: 83.1
# hours, which is 166 consecutive missed ticks. Nothing about this detection
# needed to be sensitive.
MISSED_TICKS_BEFORE_DEAD = 2

# The failures an unattended scheduled run can actually do something about, and
# the ONLY thing `--gate scheduler` changes. Everything else is still computed,
# still printed, still listed under the failure summary; it simply does not turn
# an hourly heartbeat permanently red over evidence that was lost on 2026-09-09
# and cannot be recovered. A guard that is red forever is a guard nobody reads,
# and the alternative -- deleting the orphan blobs to clear R8 -- would destroy
# evidence to make a light turn green.
SCHEDULER_GATED_CODES = ("ANCHORED_EXECUTOR_SILENT",
                         "WINDOW_HAS_NO_CRON_ENTRY",
                         "WORKFLOW_STALE", "WORKFLOW_ABSENT",
                         "WORKFLOW_NAME_MISMATCH",
                         "BASIS_GATE_OPEN", "BASIS_FAILSAFE_OPEN",
                         "CRON_EXPRESSION_UNPARSED",
                         "NO_GITHUB_ACTIONS_EVIDENCE_EVER")


def _baseline_cadence_minutes() -> Outcome:
    """The baseline capture cadence, read from the workflow that declares it."""
    if not BASELINE_WORKFLOW.exists():
        return Outcome.blocked(
            "BASELINE_WORKFLOW_ABSENT",
            f"{BASELINE_WORKFLOW.name} does not exist, so the cadence the "
            f"liveness check measures against is unknown. It is not assumed.",
            cause=Cause.DEPENDENCY)
    import re
    m = re.search(r"-\s*cron:\s*'\*/(\d+) \* \* \* \*'",
                  BASELINE_WORKFLOW.read_text())
    if not m:
        return Outcome.blocked(
            "BASELINE_CADENCE_UNREADABLE",
            f"{BASELINE_WORKFLOW.name} carries no `*/N * * * *` cron entry. "
            f"The cadence is not guessed and no default is substituted.",
            cause=Cause.DATA)
    return Outcome.ok("BASELINE_CADENCE", value=int(m.group(1)),
                      detail=f"{m.group(1)}-minute baseline cadence, read from "
                             f"{BASELINE_WORKFLOW.name}")


def _cron_field_matches(field: str, value: int, lo: int, hi: int) -> bool:
    """One cron field against one value. Supports *, */n, a, a-b, a-b/n, lists.

    Deliberately small and deliberately strict: an expression shape this does
    not understand raises rather than returning False, because silently
    answering "no this cron does not fire" about an entry nobody parsed is the
    same class of defect as everything else in this file.
    """
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a_s, b_s = part.split("-", 1)
            a, b = int(a_s), int(b_s)
        else:
            a = b = int(part)
            if step != 1:
                raise ValueError(f"unsupported cron term {part}/{step}")
        if a <= value <= b and (value - a) % step == 0:
            return True
    return False


def cron_fires_in(expr: str, lo: dt.datetime, hi: dt.datetime) -> bool:
    """Does this 5-field UTC cron entry fire at any minute in [lo, hi]?

    Evaluated minute by minute. The windows here are 80 minutes (inactives) and
    20 hours (practice/final_status), so the loop is bounded and cheap, and an
    exact answer is worth more than a clever one.
    """
    mi, ho, dom, mon, dow = expr.split()
    t = lo.replace(second=0, microsecond=0)
    while t <= hi:
        dom_ok = _cron_field_matches(dom, t.day, 1, 31)
        dow_ok = _cron_field_matches(dow, (t.weekday() + 1) % 7, 0, 6)
        # GitHub/POSIX: when BOTH day fields are restricted the match is an OR,
        # not an AND. Every entry this repository generates leaves day-of-week
        # as `*`, but the rule is implemented rather than assumed away.
        day_ok = ((dom_ok or dow_ok) if (dom != "*" and dow != "*")
                  else (dom_ok and dow_ok))
        if (_cron_field_matches(mi, t.minute, 0, 59)
                and _cron_field_matches(ho, t.hour, 0, 23)
                and _cron_field_matches(mon, t.month, 1, 12) and day_ok):
            return True
        t += dt.timedelta(minutes=1)
    return False


def last_anchored_evidence(manifest_path=None) -> Outcome:
    """When did a GitHub-Actions execution last append a manifest row?

    THE CLOCK IS THE EVIDENCE'S, NOT THE COMMIT'S. A bot commit is a proxy: the
    workflow commits only when the working tree changed, so a run that captured
    nothing leaves no commit and a reader cannot tell it from a run that never
    happened. A manifest row carries the executor identity the run recorded
    about itself -- `value.execution_target.executor.is_github_actions` -- so it
    answers the question directly.
    """
    import json as _json
    mp = pathlib.Path(manifest_path or MANIFEST)
    if not mp.exists():
        return Outcome.blocked(
            "NO_MANIFEST", f"no manifest at {mp}.", cause=Cause.DEPENDENCY)
    latest, n_gh, n_local, latest_wf = None, 0, 0, None
    for line in mp.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = _json.loads(line)
        except ValueError:
            continue
        val = row.get("value") or {}
        decl = val.get("execution_target") or {}
        ident = decl.get("executor") or {}
        if not ident:
            continue
        if ident.get("is_github_actions") is not True:
            n_local += 1
            continue
        n_gh += 1
        prov = val.get("provenance") or {}
        ts = (val.get("retrieved_at") or prov.get("retrieved_at")
              or decl.get("declared_at"))
        d = _parse_iso(ts) or _parse_capture_id(row.get("capture_id"))
        if d and (latest is None or d > latest):
            latest, latest_wf = d, ident.get("workflow")
    if latest is None:
        return Outcome.fail(
            "NO_GITHUB_ACTIONS_EVIDENCE_EVER",
            f"{n_gh} row(s) name a GitHub-Actions executor and not one carries "
            f"a readable clock; {n_local} row(s) were written by a local "
            f"executor. The anchored path has never demonstrably produced "
            f"dated evidence.", n_github_rows=n_gh, n_local_rows=n_local)
    return Outcome.ok("ANCHORED_EVIDENCE_CLOCK", value=latest,
                      detail=f"last GitHub-Actions manifest row "
                             f"{latest.isoformat()} from {latest_wf!r}; "
                             f"{n_gh} GitHub-Actions rows, {n_local} local",
                      n_github_rows=n_gh, n_local_rows=n_local,
                      last_workflow=latest_wf)


def _parse_iso(v):
    if not v:
        return None
    try:
        d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _parse_capture_id(cid):
    if not cid:
        return None
    try:
        return dt.datetime.strptime(str(cid), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        return None



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
    # A CAPABILITY IS NOT A RECENCY PROPERTY, and this used to read the last
    # 40 commits only. The runner had pushed 198 times, but a single session
    # of 40 human commits displaced every one of them out of the window and
    # the check reported RUNNER_HAS_NEVER_PUSHED -- "the executor's write path
    # is unproven" -- about a path proven 198 times. Whether the executor CAN
    # write is answered by whether it EVER has; how recently is a separate
    # question and is reported beside it rather than folded into it.
    # THE AUTHOR IS MATCHED EXACTLY, NEVER THROUGH git's --author.
    # `--author=nfl-capture[bot]` reads the brackets as a REGEX CHARACTER
    # CLASS, so it looks for "nfl-capture" followed by one of b, o or t and
    # finds nothing. It returned 0 against a real 198. The author string is
    # compared as a string, which is what the original did correctly.
    bot = last = None
    try:
        rows = subprocess.run(
            ["git", "log", "--format=%an|%h|%ad", "--date=short"],
            cwd=_REPO, capture_output=True, text=True,
            timeout=60).stdout.splitlines()
        hits = [r for r in rows
                if r.split("|", 1)[0].strip() == "nfl-capture[bot]"]
        bot = len(hits)
        last = " ".join(hits[0].split("|")[1:]) if hits else None
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        out.append(("git history readable", Outcome.blocked(
            "GIT_UNAVAILABLE", str(exc), cause=Cause.ENVIRONMENT)))
    out.append(("the runner has already pushed evidence unattended",
                Outcome.ok("RUNNER_CAN_PUSH", value=bot,
                           detail=f"{bot} commit(s) in the whole history are "
                                  f"authored by nfl-capture[bot]; most "
                                  f"recent {last}",
                           n_commits=bot, most_recent=last)
                if bot else Outcome.fail(
                    "RUNNER_HAS_NEVER_PUSHED",
                    "no commit by nfl-capture[bot] anywhere in history; the "
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


def _live_state(season: int, week: int) -> list:
    """Is the world in a state where the NEXT window can produce evidence?

    Every check here is an observation, not a property of the repository, and
    every one of them would have fired before 2026-09-13 if it had existed.
    """
    from nfl.capture.coverage import coverage, load_week_plan
    from nfl.capture.execution import (DISCHARGING_BASES, declaration_basis,
                                       executor_identity)
    from nfl.tools.gen_t90_schedule import WORKFLOW

    out = []
    now = dt.datetime.now(dt.timezone.utc)

    # L1. IS THE ANCHORED EXECUTOR ALIVE. The check that did not exist.
    cad = _baseline_cadence_minutes()
    ev = last_anchored_evidence()
    if cad.state is not State.PASS or ev.state is not State.PASS:
        out.append(("the anchored executor is alive",
                    cad if cad.state is not State.PASS else ev))
    else:
        gap_min = (now - ev.value).total_seconds() / 60.0
        ticks = gap_min / cad.value
        horizon = MISSED_TICKS_BEFORE_DEAD * cad.value
        detail = (f"last GitHub-Actions manifest row {ev.value.isoformat()}, "
                  f"{gap_min / 60:.1f}h ago = {ticks:.0f} missed "
                  f"{cad.value}-minute ticks; horizon is "
                  f"{MISSED_TICKS_BEFORE_DEAD} ticks ({horizon} min)")
        out.append(("the anchored executor is alive",
                    Outcome.fail("ANCHORED_EXECUTOR_SILENT",
                                 f"NO EVIDENCE HAS ARRIVED FROM ANY "
                                 f"GitHub-Actions execution for {gap_min / 60:.1f} "
                                 f"hours. {detail}. Absence of a commit is not "
                                 f"proof a run did not start, so this measures "
                                 f"the arrival of evidence, not the scheduler. "
                                 f"Either way no obligation can be discharged "
                                 f"while this is true: the local executor "
                                 f"classifies as LOCAL_INVOCATION and cannot "
                                 f"discharge even with egress.",
                                 gap_hours=round(gap_min / 60, 2),
                                 missed_ticks=int(ticks),
                                 cadence_minutes=cad.value,
                                 last_evidence_utc=ev.value.isoformat())
                    if gap_min > horizon else
                    Outcome.ok("ANCHORED_EXECUTOR_ALIVE", value=round(gap_min, 1),
                               detail=detail,
                               gap_hours=round(gap_min / 60, 2),
                               cadence_minutes=cad.value)))

    # L2. CAN THE EXECUTOR RUNNING THIS COMMAND DISCHARGE ANYTHING. W2: the
    # surviving executor is local, so even a successful fetch discharges
    # nothing. That is a fact about authority, separate from egress, and both
    # were true at once on 2026-09-13.
    ident = executor_identity()
    basis = declaration_basis(ident)
    out.append(("this executor's basis can discharge an obligation",
                Outcome.ok("BASIS_CAN_DISCHARGE", value=basis,
                           detail=f"basis {basis}")
                if basis in DISCHARGING_BASES else Outcome.blocked(
                    "BASIS_CANNOT_DISCHARGE",
                    f"this execution classifies as {basis} "
                    f"(is_github_actions={ident.get('is_github_actions')}, "
                    f"workflow={ident.get('workflow')!r}). Only "
                    f"{list(DISCHARGING_BASES)} may discharge, so a capture "
                    f"taken from here would be real evidence that satisfies no "
                    f"obligation. This is assigned work, not blocked work: it "
                    f"needs the anchored runner, not a different threshold.",
                    cause=Cause.ENVIRONMENT, basis=basis, executor=ident)))

    # L3. WILL A CRON ENTRY ACTUALLY FIRE INSIDE THE NEXT WINDOW. The anchored
    # workflow's entries are absolute dates generated from one week's kickoffs.
    # When the last of them elapses the file still parses, still passes the
    # drift check, and fires never again. Nothing detected that; this does.
    plan = load_week_plan(season, week)
    if plan.state is not State.PASS:
        out.append(("a cron entry fires inside the next window", plan))
    else:
        upcoming = sorted((c for c in plan.value
                           if c.kind not in ("seal", "unschedulable")
                           and c.window[1] > now),
                          key=lambda c: c.window[0])
        if not upcoming:
            out.append(("a cron entry fires inside the next window",
                        Outcome.not_applicable(
                            "NO_WINDOW_REMAINS",
                            f"every {season} week {week} window has closed. "
                            f"There is no next window to schedule for.")))
        else:
            c = upcoming[0]
            lo, hi = c.window
            import re as _re
            entries = _re.findall(r"-\s*cron:\s*'([^']+)'",
                                  WORKFLOW.read_text()) if WORKFLOW.exists() else []
            try:
                hits = [e for e in entries if cron_fires_in(e, lo, hi)]
                unparsed = []
            except ValueError as exc:
                hits, unparsed = [], [str(exc)]
            if unparsed:
                out.append(("a cron entry fires inside the next window",
                            Outcome.blocked(
                                "CRON_EXPRESSION_UNPARSED",
                                f"{unparsed[0]}. An entry nobody parsed cannot "
                                f"be reported as not firing.",
                                cause=Cause.DATA)))
            else:
                out.append(("a cron entry fires inside the next window",
                            Outcome.ok(
                                "WINDOW_HAS_CRON_COVER", value=len(hits),
                                detail=f"{len(hits)} of {len(entries)} cron "
                                       f"entries fire inside {c.game_id} "
                                       f"{c.kind} {lo:%Y-%m-%dT%H:%MZ} -> "
                                       f"{hi:%H:%MZ}")
                            if hits else Outcome.fail(
                                "WINDOW_HAS_NO_CRON_ENTRY",
                                f"not one of the {len(entries)} cron entries in "
                                f"{WORKFLOW.name} fires inside the next open "
                                f"window ({c.game_id} {c.kind}, "
                                f"{lo.isoformat()} -> {hi.isoformat()}). The "
                                f"workflow is scheduled for dates that have "
                                f"passed; regenerate it for the current week.",
                                game_id=c.game_id, kind=c.kind,
                                n_entries=len(entries))))

    # L4. WHAT THE RECORD ALREADY SAYS. Surfaced rather than swallowed: the old
    # version received FAIL[PERISHABLE_WINDOWS_MISSED] here and marked itself
    # ok. A miss cannot be un-missed and this check will not go green by being
    # run again -- that is the point of recording it.
    cov = coverage(season, week, manifest_path=MANIFEST, now=now)
    if cov.state is State.FAIL:
        e = cov.evidence
        out.append(("no window has already closed unfilled", Outcome.fail(
            "PRIOR_WINDOWS_MISSED",
            f"{e.get('missed')} of {e.get('n_targets')} targets closed with no "
            f"authorised, in-window, game-attributed capture. "
            f"{e.get('missed_with_uncredited_evidence')} of those have "
            f"hash-verified game-anchored bytes in the manifest that no rule "
            f"permits to discharge them (a declaration and schema defect); "
            f"{e.get('missed_with_no_evidence_at_all')} have nothing at all (a "
            f"capture failure). These are not recoverable and this line does "
            f"not clear.",
            missed=e.get("missed"), covered=e.get("covered"),
            n_targets=e.get("n_targets"),
            missed_with_uncredited_evidence=e.get(
                "missed_with_uncredited_evidence"),
            missed_with_no_evidence_at_all=e.get(
                "missed_with_no_evidence_at_all"))))
    else:
        out.append(("no window has already closed unfilled", Outcome.ok(
            "NO_PRIOR_MISS", value=cov.evidence.get("covered"),
            detail=f"coverage {cov.state.value}[{cov.code}]: "
                   f"covered={cov.evidence.get('covered')}, "
                   f"missed={cov.evidence.get('missed')}")))

    # L5. THE STORE'S OWN INTEGRITY, at the scope that matters. `R8
    # NO_ORPHAN_BLOBS` ran green through the whole of W3 because
    # check_retention.py was pointed at a 2-blob store.
    try:
        from nfl.tools.check_retention import (STORES,
                                               assert_no_orphan_blobs_scoped)
        cfg = STORES["vintage"]
        root, man = pathlib.Path(cfg["blob_root"]), pathlib.Path(cfg["manifest"])
        blobs = {q.name for q in root.glob(cfg["glob"])} if root.exists() else set()
        rows = [ln for ln in man.read_text().splitlines() if ln.strip()]
        out.append(("the vintage store has no orphan blobs",
                    assert_no_orphan_blobs_scoped(blobs, rows,
                                                  f"/{root.name}/")))
    except (OSError, ImportError, KeyError) as exc:
        out.append(("the vintage store has no orphan blobs", Outcome.blocked(
            "ORPHAN_CENSUS_UNAVAILABLE", f"{type(exc).__name__}: {exc}",
            cause=Cause.ENVIRONMENT)))
    return out


_MARK = {"PASS": "ok  ", "FAIL": "FAIL", "BLOCKED": "BLKD",
         "DEFERRED": "DEFR", "NOT_APPLICABLE": "n/a "}


def _print(results) -> tuple:
    n_fail = n_blocked = 0
    for label, o in results:
        print(f"  {_MARK[o.state.value]}  {label}")
        print(f"        {o.detail[:220]}")
        if o.state is State.FAIL:
            n_fail += 1
        elif o.state is State.BLOCKED:
            n_blocked += 1
    return n_fail, n_blocked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--gate", default="all", choices=("all", "scheduler"),
                    help="which failures decide the EXIT CODE. 'all' is every "
                         "check. 'scheduler' is the subset a scheduled run can "
                         "act on -- the executor being silent, and the next "
                         "window having no cron entry. Both modes print every "
                         "check and every failure; the gate narrows the exit "
                         "code only, so that an unattended hourly run does not "
                         "sit permanently red on losses that cannot be "
                         "repaired and thereby stop being read. Nothing is "
                         "suppressed and no threshold is loosened.")
    args = ap.parse_args()

    print(f"T-90 PRE-FLIGHT  season {args.season} week {args.week}  "
          f"{dt.datetime.now(dt.timezone.utc).isoformat()}")

    print("\nMECHANISM -- is the anchored capture path correctly built?\n")
    mech = _checks(args.season, args.week)
    m_fail, m_blk = _print(mech)

    print("\nLIVE STATE -- can the next window actually produce evidence?\n")
    live = _live_state(args.season, args.week)
    l_fail, l_blk = _print(live)

    n_fail, n_blk = m_fail + l_fail, m_blk + l_blk
    total = len(mech) + len(live)
    gated = [(lbl, o) for lbl, o in mech + live
             if o.state in (State.FAIL, State.BLOCKED)
             and (args.gate == "all"
                  or o.code in SCHEDULER_GATED_CODES)]
    # ONE SUMMARY LINE, BOTH SETS IN IT. The split exists so a live-state
    # observation is not forced to soften itself to keep a mechanism test green;
    # it must never be usable to make a failure disappear from the total.
    print(f"\n{total} checks ({len(mech)} mechanism + {len(live)} live state), "
          f"{n_fail} failing, {n_blk} blocked")
    if n_fail or n_blk:
        print("PRE-FLIGHT NOT CLEAR -- do not expect the next window to "
              "produce usable evidence until these are answered.")
        for label, o in mech + live:
            if o.state in (State.FAIL, State.BLOCKED):
                mark = "" if (args.gate == "all"
                              or o.code in SCHEDULER_GATED_CODES) \
                    else "   [reported, not gating]"
                print(f"  {o.state.value:<8}{o.code:<34}{label}{mark}")
    else:
        print("PRE-FLIGHT CLEAR.")
    print(f"gate={args.gate}: {len(gated)} gating failure(s)")
    return 1 if gated else 0


if __name__ == "__main__":
    sys.exit(main())
