# `DUAL_PLATFORM_BOARD.json` is SUPERSEDED — do not use its FanDuel column

**Superseded by** `DUAL_PLATFORM_BOARD_v2.json` on 2026-09-18.

## CORRECTION: there is no v1 file, and there never was

This document first said the v1 artifact was "preserved byte-identical". It is
not preserved, because it was never written. The generating command was run as

    python3.12 nfl/dfs/scoring/dual_board.py | head -22

and `head` closed the pipe after 22 lines, killing the process on SIGPIPE
before it reached `out.write_text(...)`. The table printed, the file did not
appear, and the commit message that followed described an artifact that did not
exist. Nothing downstream consumed it, so nothing is wrong except the claim.

That is this project's most expensive recurring defect in its smallest form: a
step produced output on screen, and the output was read as evidence the step
had completed. The v1 NUMBERS below are real -- they are what that run printed,
under the wrong FanDuel table -- but the FILE is absent and this note exists so
a later reader does not go looking for it.

## What was wrong

v1 was built under `nfl-dfs-scoring-fanduel-1`, whose FanDuel table set all
three yardage bonuses to **0.0**. Official FanDuel Rules & Scoring, retrieved
2026-09-17, pays **+3** for each — 300 passing, 100 rushing, 100 receiving,
identical to DraftKings.

The v1 DraftKings column is unaffected and was correct: it reconciled to the
engine's own array at 7.1e-15 then and still does.

## The size of the error, on this board

| player | FD mean v1 (wrong) | FD mean v2 | understated by |
|---|---:|---:|---:|
| Amon-Ra St. Brown | 14.35 | 15.17 | 0.82 |
| Jahmyr Gibbs | 19.01 | 20.40 | 1.39 |
| Josh Allen | 20.14 | 20.85 | 0.71 |
| Jared Goff | 15.66 | 16.48 | 0.82 |

It is worse than the means suggest. A bonus is paid only in the worlds where
the threshold is crossed, so the error sits entirely in the upper tail — the
part of the distribution a tournament lineup is built to catch. v1 charged
three points to exactly the outcomes that win.

## What it teaches

All three wrong coefficients were the three the module had already flagged
`HIGHEST_RISK_IF_WRONG`, and the module refused to let them reach a portfolio.
The gate worked. The recollection did not. That is an argument for gating
recalled values, not against it.

## Also corrected at the same time

The FanDuel single-game format: **6 roster slots, not 5**, and the **MVP salary
IS multiplied by 1.5** — FanDuel changed that beginning in 2025. The recalled
configuration was a pre-2025 format. `salary_is_multiplied` had been flagged
highest-risk too, because it changes the shape of the optimisation rather than
rescaling it; had a FanDuel lineup been built on it, roughly a sixth of the cap
would have gone unspent on every entry.
