# Ticket: the suite runner yields zero information under any time bound

**Raised 2026-09-24. Class: operational. Cost so far: about 3.5 hours of
compute and two attempts that produced nothing at all.**

## What happened

`nfl/tests/run_suite.py` was launched twice today.

| attempt | started | bound | outcome | bytes of output |
|---|---|---|---|---|
| 1 | 18:22Z | 3,500s | killed by its own timeout at ~58 min | 344 (numpy warnings only) |
| 2 | 19:12Z | 9,000s | killed at ~2.5h, then the container restarted | **0** |

The second attempt was launched with `python3.12 -u` specifically to defeat
buffering. It still wrote nothing, because the runner accumulates its report
and prints at the end rather than emitting per-suite results as they land.

So the runner has a property worth naming: **under any time bound shorter than
a full pass, it returns exactly as much information as never having run it.**
A three-hour run that is interrupted at two hours fifty-nine tells you nothing
about the 200-odd suites that already finished.

## Why this matters more than the lost hours

The whole discipline here is that a step which returned nothing must not be
read as success. The runner inverts it: a step that did a great deal of work
returns nothing, and there is no way to tell a hang from slow progress from a
suite that failed at minute three. Twice today I reported "suite running"
based on a `pgrep` that was matching my own shell command, and there was no
output to contradict me. A runner that emitted a line per suite would have.

## The immediate workaround, already in use

`/tmp/claude-0/run_tests_durable.sh` runs the 239 discovered test files one at
a time with a 180-second per-file bound and appends one tab-separated row per
file as it completes: verdict, path, elapsed, tally. Partial results survive a
kill, a timeout or a container restart, and a single hanging file costs 180
seconds instead of the whole run.

This is a workaround, not the fix. It does not reproduce the runner's own
classification vocabulary (PASS / BLOCKED+cause / UNRESOLVED / DEFERRED / N-A
/ FAIL), and that vocabulary is the thing the project actually reasons with.

## The fix worth making

`run_suite.py` should write each suite's classified result to an append-only
file the moment that suite finishes, and keep the end-of-run summary as a
render over that file rather than as the only place the information exists.
Then an interrupted run is a partial result rather than no result, which is
the same principle the rest of this repository already applies to captures,
forecasts and refusals.

Two smaller things worth doing at the same time:

* a per-suite time bound, so one hanging suite cannot consume the whole run;
* emitting the suite list up front, so a reader can tell "not started" from
  "started and produced nothing", which is exactly the distinction this
  project spends most of its effort on everywhere else.

## Not done here

I have not changed `run_suite.py`. It is the instrument the project's own
acceptance criteria are phrased in, and changing how it reports on a game-day
evening is a worse risk than the one being fixed. Raised for a decision.
