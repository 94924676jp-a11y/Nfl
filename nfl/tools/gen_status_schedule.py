"""Generate the NON-G0A anchored capture workflow: practice and final_status.

WHY A SECOND WORKFLOW RATHER THAN A WIDER FIRST ONE

Two practice obligations closed unfilled on 2026-09-08 while an authorised
source published rows throughout their window, because `gen_t90_schedule.py`
anchors `("inactives",)` only and nothing else ever generated an anchored
execution for a practice or final_status window. A periodic sweep cannot
discharge an anchored obligation, so those windows were unreachable.

The obvious repair -- widen `ANCHORED_KINDS` -- was rejected by owner ruling
2026-09-08. It would change the execution surface and the schedule identity of
the workflow carrying the one outstanding G0A obligation, hours before the only
window that can discharge it. This file is the alternative: a separate path,
separate identity, separate basis, and no ability to touch G0A.

WHAT KEEPS IT ISOLATED, structurally rather than by convention:

  * its workflow name is `execution.NON_G0A_ANCHORED_WORKFLOW`, which maps to
    `BASIS_ANCHORED_NON_G0A`;
  * `execution.BASIS_KINDS` confines that basis to ("practice",
    "final_status"), and an assert in that module refuses to let the G0A kind
    into the tuple;
  * so a run of this workflow inside the T-90 window, from an authorised
    source, still records `BASIS_NOT_AUTHORISED_FOR_KIND` against `inactives`.

WHY HOURLY RATHER THAN EVERY FIVE MINUTES

The inactives window is 80 minutes and unrecoverable, which is what justifies a
five-minute step there. These windows are twenty hours. A five-minute step
would be 240 entries per window, burying the schedule in noise to buy nothing:
the failure being fixed is having NO anchored execution, not having too few.
Hourly gives about twenty anchored chances per window.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.capture.schedule import season_plan                          # noqa: E402
from nfl.capture import execution as X                                # noqa: E402

WORKFLOW = _REPO / ".github" / "workflows" / "nfl-status.yml"
VINTAGE = _REPO / "nfl" / "vintage"

# Exactly the kinds the G0A generator does not anchor, and never the G0A kind.
NON_G0A_KINDS = ("practice", "final_status")
assert X.G0A_KIND not in NON_G0A_KINDS, (
    "this generator must never emit an anchored execution for the G0A kind")
assert set(NON_G0A_KINDS) == set(X.BASIS_KINDS[X.BASIS_ANCHORED_NON_G0A]), (
    "the kinds generated here and the kinds the basis may discharge must "
    "match, or the workflow would fire for targets it cannot satisfy")


def _windows(season: int, week: int) -> Outcome:
    snaps = sorted(VINTAGE.glob("schedules.*.csv.gz"),
                   key=lambda p: p.stat().st_mtime)
    if not snaps:
        return Outcome.blocked(
            "NO_SCHEDULE_SNAPSHOT",
            "no schedules artifact has been captured, so there are no kickoff "
            "times to anchor to.", cause=Cause.DEPENDENCY)
    latest = snaps[-1]
    rows = [r for r in csv.DictReader(io.StringIO(gzip.open(latest, "rt").read()))
            if r.get("season") == str(season) and r.get("game_type") == "REG"
            and r.get("week") == str(week)]
    if not rows:
        return Outcome.blocked(
            "NO_GAMES_IN_SNAPSHOT",
            f"{latest.name} carries no {season} REG week {week} rows. An empty "
            f"cron is not a covered week.", cause=Cause.DATA)
    plan = [c for c in season_plan(rows) if c.kind in NON_G0A_KINDS]
    if not plan:
        return Outcome.blocked(
            "NO_ANCHORED_TARGETS",
            f"{len(rows)} games planned but none produced a target of kind "
            f"{NON_G0A_KINDS}. Emitting an empty schedule would look like "
            f"coverage.", cause=Cause.DATA)
    merged: dict = {}
    for c in plan:
        merged.setdefault(c.window, []).append((c.game_id, c.kind, c.label))
    return Outcome.ok("WINDOWS", value=sorted(merged.items()),
                      detail=f"{len(merged)} distinct windows over {len(plan)} "
                             f"targets, from {latest.name}",
                      snapshot=latest.name, n_targets=len(plan),
                      n_windows=len(merged))


def cron_entries(lo: dt.datetime, hi: dt.datetime) -> list:
    """Cover [lo, hi] hourly, compressed per calendar day.

    Walked rather than computed, for the same reason the G0A generator walks:
    these windows cross midnight and month ends, and the arithmetic version of
    this got that wrong.
    """
    by_day: dict = {}
    t = lo.replace(minute=0, second=0, microsecond=0)
    if t < lo:
        t += dt.timedelta(hours=1)
    while t <= hi:
        by_day.setdefault((t.month, t.day), []).append(t.hour)
        t += dt.timedelta(hours=1)
    out = []
    for (month, day), hours in sorted(by_day.items()):
        hs = sorted(set(hours))
        runs, start = [], hs[0]
        for a, b in zip(hs, hs[1:] + [None]):
            if b != a + 1:
                runs.append(f"{start}-{a}" if a > start else str(start))
                start = b
        out.append(f"0 {','.join(runs)} {day} {month} *")
    return out


def schedule_identity(windows) -> str:
    """Digest over the (window, game, kind) triples themselves.

    Deliberately NOT over the snapshot filename: the bot re-captures schedules
    whenever upstream bytes change for reasons unrelated to kickoff times, and
    a guard that cries wolf gets ignored. Prefix differs from the G0A
    generator's so the two identities can never be confused for one another.
    """
    blob = "\n".join(
        f"{lo.isoformat()}|{hi.isoformat()}|"
        + ",".join(f"{g}:{k}:{lab}" for g, k, lab in sorted(items))
        for (lo, hi), items in windows)
    return "SCHEDNG-" + hashlib.sha256(blob.encode()).hexdigest()[:16]


def render(season: int, week: int) -> Outcome:
    w = _windows(season, week)
    if w.state is not State.PASS:
        return w
    windows = w.value
    sched_id = schedule_identity(windows)

    lines, summary = [], []
    for (lo, hi), items in windows:
        entries = cron_entries(lo, hi)
        kinds = sorted({k for _, k, _ in items})
        summary.append((lo, hi, sorted({g for g, _, _ in items}), kinds))
        lines.append(f"    # {lo:%Y-%m-%d %H:%M}Z -> {hi:%m-%d %H:%M}Z  "
                     f"({len(items)} target{'s' if len(items) != 1 else ''}, "
                     f"{'/'.join(kinds)})")
        lines.extend(f"    - cron: '{e}'" for e in entries)

    n_entries = sum(1 for ln in lines if ln.lstrip().startswith("- cron"))
    body = f"""name: {X.NON_G0A_ANCHORED_WORKFLOW}

# GENERATED FILE -- do not hand-edit.
#   nfl/tools/gen_status_schedule.py --season {season} --week {week} --write
#   schedule identity: {sched_id}
#
# NON-G0A. This workflow serves {NON_G0A_KINDS} only. It CANNOT discharge the
# outstanding G0A `inactives` obligation, and that is enforced in
# nfl/capture/execution.py rather than by this comment: its runs classify as
# {X.BASIS_ANCHORED_NON_G0A}, and BASIS_KINDS confines that basis to
# {NON_G0A_KINDS}. A run of this workflow inside the T-90 window, from an
# authorised source, records BASIS_NOT_AUTHORISED_FOR_KIND against inactives.
#
# The G0A path is .github/workflows/nfl-t90.yml, schedule identity
# SCHED-2a2924d4966fbd3d, and nothing here touches it.
#
# {len(windows)} distinct windows, {w.evidence['n_targets']} targets,
# {n_entries} cron entries at an hourly step. These windows are 20 hours wide;
# the five-minute step used for the 80-minute inactives window would be 240
# entries each and would buy nothing.
#
# WHAT THIS DOES NOT CLAIM. GitHub may delay or drop a scheduled run. A capture
# discharges a target on evidence -- retrieved_at inside the window, an
# authorised source, a declared target, an anchored basis -- and never because
# this workflow fired.

on:
  schedule:
{chr(10).join(lines)}
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: nfl-vintage-capture      # shared with the baseline: never race it
  cancel-in-progress: false

jobs:
  capture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Capture
        run: |
          set +e
          python3 nfl/tools/capture_vintage.py --season {season} | tee /tmp/capture.log
          echo "exit=$?" >> "$GITHUB_OUTPUT"

      # COMMIT BEFORE JUDGING. A failing step skips the rest of the job, so
      # with the FAIL gate first one misbehaving source discards every other
      # source's bytes for the run. Measured on the baseline workflow
      # 2026-09-08: runs 87 and 88 captured six sources and committed none.
      - name: Commit anything captured
        if: always()
        run: |
          git config user.name  "nfl-capture[bot]"
          git config user.email "nfl-capture@users.noreply.github.com"
          git add nfl/vintage nfl/vintage_manifest.jsonl
          if git diff --cached --quiet; then
            echo "nothing new captured; not committing"
            exit 0
          fi
          CID=$(grep -oE 'capture [0-9]{{8}}T[0-9]{{6}}Z' /tmp/capture.log | head -1 | awk '{{print $2}}')
          git commit \\
            -m "NFL status anchored capture ${{CID:-unknown}}" \\
            -m "GitHub Actions run ${{GITHUB_RUN_ID}}, NON-G0A anchored workflow." \\
            -m "Append-only: adds manifest rows and content-addressed blobs."
          git pull --rebase --autostash origin main
          git push origin HEAD:main

      - name: Fail only on a real FAIL
        if: always()
        run: |
          # Runs AFTER the commit: the signal is kept, and so are the bytes.
          if grep -qE '^FAIL ' /tmp/capture.log; then
            grep -E '^FAIL ' /tmp/capture.log
            exit 1
          fi
          echo "no FAIL states"

      - name: Report game-level coverage
        if: always()
        run: |
          grep -A6 'GAME-LEVEL COVERAGE' /tmp/capture.log || \\
            echo "no coverage line -- check the capture output"
"""
    return Outcome.ok("WORKFLOW_RENDERED", value=body,
                      detail=f"{n_entries} cron entries over "
                             f"{w.evidence['n_windows']} windows",
                      n_entries=n_entries, windows=summary,
                      schedule_identity=sched_id,
                      snapshot=w.evidence["snapshot"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    out = render(args.season, args.week)
    if out.state is not State.PASS:
        print(f"{out.state.value}[{out.code}] {out.detail}")
        return 1
    for lo, hi, gids, kinds in out.evidence["windows"]:
        print(f"{lo:%Y-%m-%d %H:%M}Z -> {hi:%m-%d %H:%M}Z  "
              f"{len(gids):2d} game(s)  {'/'.join(kinds)}")
    print(f"\n{out.detail}; identity {out.evidence['schedule_identity']}")
    if args.write:
        WORKFLOW.parent.mkdir(parents=True, exist_ok=True)
        WORKFLOW.write_text(out.value)
        print(f"wrote {WORKFLOW.relative_to(_REPO)}")
    else:
        print("(dry run; pass --write to emit the workflow)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
