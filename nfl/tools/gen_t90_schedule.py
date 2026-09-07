"""Generate the event-anchored capture workflow from real kickoff times.

WHAT "EVENT-ANCHORED" MEANS HERE, AND WHAT IT CANNOT MEAN

The runner wakes BECAUSE a specific game's window is open. Each cron entry below
exists because a kickoff time in the captured schedule put a window there; none
is a round-number cadence that happens to overlap. That is the difference the
owner asked to be verified, and the `*/30` baseline in nfl-capture.yml does not
have it.

What it still cannot mean is a guarantee. GitHub documents that scheduled runs
may be delayed or dropped under load, and no arrangement of cron entries fixes
that. So this raises the number of chances inside each window from roughly two
to sixteen; it does not promise sixteen, and this file makes no availability
claim.

DISCHARGE IS JUDGED ON EVIDENCE, NOT ON WHICH WORKFLOW FIRED

A capture discharges a target when its `retrieved_at` is inside the window, its
source is authorised for the kind, and it is attributed to the game -- and never
because it came from this workflow rather than the baseline one. A baseline run
that happens to land inside a window is a real capture and counts. That
separation is deliberate: anchoring improves the odds of the evidence existing,
it is not itself the evidence.

REGENERATION AND DRIFT

The cron is derived from a captured schedule snapshot, so it goes stale when
kickoff times move -- and a stale schedule is silent, which is the Class C
failure. `nfl/tests/test_t90_workflow.py` regenerates from the current snapshot
and fails if the committed file differs, so drift is caught by the suite rather
than by a missed window.

    python3.12 nfl/tools/gen_t90_schedule.py --season 2026 --week 1 --write
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import io
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.capture.schedule import season_plan  # noqa: E402

WORKFLOW = _REPO / ".github" / "workflows" / "nfl-t90.yml"
VINTAGE = _REPO / "nfl" / "vintage"

# Inside a window, this is how often to wake. Five minutes is GitHub's finest
# scheduling granularity; there is no benefit to declaring anything finer and
# doing so would only misrepresent what the platform offers.
STEP_MINUTES = 5

# Only the tight, unrecoverable, per-game window is anchored. Practice and
# final-status windows are 20 hours wide and the baseline cadence covers them
# many times over; adding 20 hours of five-minute cron entries would be noise
# that buys nothing and would bury the entries that matter.
ANCHORED_KINDS = ("inactives",)


def _windows(season: int, week: int) -> Outcome:
    snaps = sorted(VINTAGE.glob("schedules.*.csv.gz"),
                   key=lambda p: p.stat().st_mtime)
    if not snaps:
        return Outcome.blocked(
            "NO_SCHEDULE_SNAPSHOT",
            "no schedules artifact has been captured, so there are no kickoff "
            "times to anchor to. Writing a cron from anything else would be "
            "inventing the schedule.", cause=Cause.DEPENDENCY)
    latest = snaps[-1]
    rows = [r for r in csv.DictReader(io.StringIO(gzip.open(latest, "rt").read()))
            if r.get("season") == str(season) and r.get("game_type") == "REG"
            and r.get("week") == str(week)]
    if not rows:
        return Outcome.blocked(
            "NO_GAMES_IN_SNAPSHOT",
            f"{latest.name} carries no {season} REG week {week} rows. An empty "
            f"cron is not a covered week.", cause=Cause.DATA)

    plan = [c for c in season_plan(rows) if c.kind in ANCHORED_KINDS]
    if not plan:
        return Outcome.blocked(
            "NO_ANCHORED_TARGETS",
            f"{len(rows)} games planned but none produced a target of kind "
            f"{ANCHORED_KINDS}. Emitting an empty schedule would look like "
            f"coverage.", cause=Cause.DATA)

    # Distinct windows: ten games kicking off together share one window and must
    # not produce ten copies of the same cron entry.
    merged: dict = {}
    for c in plan:
        merged.setdefault(c.window, []).append(c.game_id)
    return Outcome.ok("WINDOWS", value=sorted(merged.items()),
                      detail=f"{len(merged)} distinct windows over {len(plan)} "
                             f"games, from {latest.name}",
                      snapshot=latest.name, n_games=len(plan),
                      n_windows=len(merged))


def cron_entries(lo: dt.datetime, hi: dt.datetime) -> list:
    """Cover [lo, hi] at STEP_MINUTES, as GitHub 5-field UTC cron entries.

    Built by walking the window rather than by arithmetic on hour boundaries,
    because the windows cross midnight and month ends and the arithmetic version
    of this got that wrong. Walking cannot.
    """
    by_hour: dict = {}
    t = lo.replace(second=0, microsecond=0)
    t -= dt.timedelta(minutes=t.minute % STEP_MINUTES)
    if t < lo:
        t += dt.timedelta(minutes=STEP_MINUTES)
    while t <= hi:
        by_hour.setdefault((t.month, t.day, t.hour), []).append(t.minute)
        t += dt.timedelta(minutes=STEP_MINUTES)

    out = []
    full = set(range(0, 60, STEP_MINUTES))
    for (month, day, hour), minutes in sorted(by_hour.items()):
        mins = (f"*/{STEP_MINUTES}" if set(minutes) == full
                else ",".join(str(m) for m in sorted(minutes)))
        out.append(f"{mins} {hour} {day} {month} *")
    return out


def schedule_identity(windows) -> str:
    """Digest over the WINDOWS, not over the file they came from.

    The header used to name the source snapshot filename, and the drift test
    compared the file byte-for-byte. The bot re-captures schedules whenever the
    upstream bytes change -- which happens for reasons that have nothing to do
    with kickoff times -- so the guard fired on a new filename while all 16 cron
    entries were identical. Measured 2026-09-07: snapshot ebec1e45 -> e5d64b69,
    cron entries identical, two differing lines both in the comment.

    A guard that cries wolf is a guard that gets ignored, and the thing it would
    then miss is a genuinely moved kickoff. So the identity recorded here is the
    content the cron actually depends on: every (game, window) pair. It changes
    when a kickoff moves and not when a file is re-fetched.
    """
    blob = json.dumps(
        [[sorted(g), lo.isoformat(), hi.isoformat()]
         for (lo, hi), g in windows], sort_keys=True, separators=(",", ":"))
    return "SCHED-" + hashlib.sha256(blob.encode()).hexdigest()[:16]


def render(season: int, week: int) -> Outcome:
    w = _windows(season, week)
    if w.state is not State.PASS:
        return w
    windows = w.value
    sched_id = schedule_identity(windows)

    lines, summary = [], []
    for (lo, hi), gids in windows:
        entries = cron_entries(lo, hi)
        games = ", ".join(sorted(gids))
        summary.append((lo, hi, sorted(gids)))
        lines.append(f"    # {lo:%Y-%m-%d %H:%M}Z -> {hi:%H:%M}Z  "
                     f"({len(gids)} game{'s' if len(gids) != 1 else ''}: "
                     f"{games})")
        lines.extend(f"    - cron: '{e}'" for e in entries)

    n_entries = sum(1 for ln in lines if ln.lstrip().startswith("- cron"))
    body = f"""name: NFL T-90 anchored capture

# GENERATED FILE -- do not hand-edit.
#   nfl/tools/gen_t90_schedule.py --season {season} --week {week} --write
#   schedule identity: {sched_id}
#
# That identity is a digest over the (game, window) pairs themselves, not over
# the snapshot file they were read from. A re-captured schedule with unchanged
# kickoffs leaves it unchanged; a moved kickoff changes it and the drift test
# in nfl/tests/test_t90_workflow.py fails.
#
# Every cron entry below exists because a kickoff time in that snapshot put a
# capture window there. None is a round-number cadence. That is what makes this
# event-anchored and the `*/30` baseline in nfl-capture.yml not.
#
# {w.evidence['n_windows']} distinct windows, {w.evidence['n_games']} games, \
{n_entries} cron entries, {STEP_MINUTES}-minute step inside each window.
#
# WHAT THIS DOES NOT CLAIM. GitHub may delay or drop a scheduled run; no cron
# arrangement prevents that. This raises the chances inside an 80-minute window
# from about two to about sixteen. It does not promise any of them.
#
# A capture discharges a target on evidence -- retrieved_at inside the window,
# an authorised source, attributed to the game -- and never because this
# workflow fired rather than the baseline one.

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

      - name: Fail only on a real FAIL
        run: |
          if grep -qE '^FAIL ' /tmp/capture.log; then
            grep -E '^FAIL ' /tmp/capture.log
            exit 1
          fi
          echo "no FAIL states"

      - name: Commit anything captured
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
            -m "NFL T-90 anchored capture ${{CID:-unknown}}" \\
            -m "GitHub Actions run ${{GITHUB_RUN_ID}}, T-90 anchored workflow." \\
            -m "Append-only: adds manifest rows and content-addressed blobs."
          git pull --rebase --autostash origin main
          git push origin HEAD:main

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
    for lo, hi, gids in out.evidence["windows"]:
        print(f"{lo:%Y-%m-%d %H:%M}Z -> {hi:%H:%M}Z  "
              f"{len(gids):2d} game(s)  {', '.join(gids[:3])}"
              f"{' ...' if len(gids) > 3 else ''}")
    print(f"\n{out.detail}; snapshot {out.evidence['snapshot']}")
    if args.write:
        WORKFLOW.parent.mkdir(parents=True, exist_ok=True)
        WORKFLOW.write_text(out.value)
        print(f"wrote {WORKFLOW.relative_to(_REPO)}")
    else:
        print("(dry run; pass --write to emit the workflow)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
