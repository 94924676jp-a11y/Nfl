# A source-family contract must separate "no rows now" from "cannot carry rows"

Owner ruling 2026-09-25, permanent.

> A source-family contract must distinguish "this URL currently has no rows"
> from "this URL class is structurally incapable of carrying the governed data."

## Why this is worth a doctrine file

`official_inactives` returned `SOURCE_HAS_NO_ROWS_YET` on 468 captures across ten
days. The verdict was accurate about each artifact and wrong about the world.
Measured over the 367 committed blobs: **0 carry `<tr`, `<table` or `<tbody`;
363 contain "check back soon"; none carries a JS-shell marker.** The rows were
never in those bytes and never will be.

The cost of not having this distinction is specific and large: somebody spends
hours improving an extractor for a page that does not contain the data. Two of my
own hypotheses today were exactly that mistake — first that egress had failed,
then that the executing branch ran a different parser. Both were wrong, and both
would have led to work on the wrong layer.

## The three verdicts, and what each one authorises

| verdict | means | remedy |
|---|---|---|
| `DEBT_WITHIN_WINDOW` | deferred, publication window still open | wait |
| `CONTENT_PRESENT_EXTRACTION_EMPTY` | row containers present, extractor silent | fix the extractor |
| `SOURCE_PATH_CANNOT_YIELD_ROWS` | no capture ever carried a row container | **find the right artifact; the extractor is irrelevant** |

A JS-shell marker splits the third case again: render it, versus find a different
URL. `official_inactives` has no shell marker, so it is a landing page rather
than an unrendered one.

## What the third verdict obliges

Not a replacement constant. Pasting in whichever article URL works this week
replaces one brittle hardcoded page with a fresher brittle hardcoded page and
hides the same failure until the next redesign.

It obliges **discovery**: a mechanism that locates a content-bearing artifact for
a specific game and publication window, qualifies each candidate against ten
named checks, and pins the one that passes. `nfl/capture/source_discovery.py`.

The ten checks are separate because each has failed somewhere in this project:
official domain · game attribution · publication time · both-team coverage ·
content bearing · player-name presence · raw bytes preserved · hash of the stored
bytes · parser compatibility · cutoff legality.

**There is no score.** A partial pass is a refusal, because "eight of ten"
invites somebody to decide which two did not matter.

## Two boundaries that hold regardless

**Discovery may run before evidence freeze. A pin may not move after it.**
Once an artifact is pinned, forecast execution consumes that artifact and does
not resolve its own source — a stage that looks things up for itself has its own
information clock, which is the defect the whole evidence boundary exists to
prevent.

**History is marked, never rewritten.** The pre-2026-09-15 era recorded roughly
374 `PASS/CAPTURED` rows for this source with `n_data_rows` set to a count of the
word "inactive" in the page's own chrome. Those rows stay exactly where they are,
marked unusable (DEF-050). A register that edits its past to look better cannot
be used to audit anything.
