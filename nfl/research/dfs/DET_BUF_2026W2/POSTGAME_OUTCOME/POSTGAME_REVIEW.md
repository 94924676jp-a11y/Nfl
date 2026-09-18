# DET @ BUF, week 2 2026 — postgame review state

**Status: NOT FROZEN.** `POSTGAME_REVIEW_FROZEN` cannot be declared. Phase 1
did not complete, and ten of the twelve phases are measurements against a
result this repository does not have.

## Phase 1 — capture the final outcome authoritatively

**BLOCKED, cause DATA.** Assigned to the other agent as `OUT-023`.

Every source reachable from this executor was tried and the evidence is in
`CAPTURE_ATTEMPT.json` with hashes:

| source | result |
|---|---|
| nflverse `play_by_play_2026.csv.gz` | 200, sha256 `b69f55a172965e16` — byte-identical to the pre-kickoff capture, week 1 only |
| nflverse `stats_player_week_2026.csv` | 200, week 1 only; retried 2026-09-18T04:07:07Z, still week 1, 1,118 rows, 0 week-2 DET/BUF rows |
| nflverse `snap_counts_2026.csv` | 200, week 1 only |
| nflverse `schedules.csv` | 404 |
| nfl.com, espn.com, detroitlions.com | 403 at CONNECT |

The one piece of outcome information that reached this executor — "a
high-scoring 41-31 game" — is recorded as `UNVERIFIED_SECONDARY — NOT
INGESTED`. It has no source, no timestamp and no hash, it does not say which
side scored 41, and a per-stat grade cannot be computed from a final score
under any circumstances.

**A blocked capture is not a small result. It is no result.** Nothing below
was estimated, partially graded, or filled in from the relayed score.

## Phases 2–11 — the measurements

All **NOT_EXECUTED**, every one of them gated on Phase 1. What exists is the
harness, built and tested against a synthetic fixture so that the day the
outcome lands is not also the day the graders are first exercised.

| phase | grader | state |
|---|---|---|
| 2 projection grading, per stat | `nfl/postgame/grade_projections.py` | BUILT, TESTED, REFUSES |
| 3 Buffalo role-defect review | (needs phase 2 output) | NOT_EXECUTED |
| 4 prop grading, 43 supported lines | `nfl/postgame/grade_props.py` | BUILT, TESTED, REFUSES |
| 5 card grading | `grade_props.py` `card_as_ordered` | BUILT, TESTED, REFUSES |
| 6 portfolio grading, both 40-lineup sets | `nfl/postgame/grade_portfolios.py` | BUILT, TESTED, REFUSES |
| 7 perfect lineup and regret | `grade_portfolios.optimal_lineup` | BUILT, TESTED, REFUSES |
| 8 captain research review | (needs phase 6/7 output) | NOT_EXECUTED |
| 9 cheap-punt review | (needs phase 6/7 output) | NOT_EXECUTED |
| 10 calibration and ledger | `nfl/postgame/ledger.py` | REGISTERED, AWAITING_OUTCOME |
| 11 game environment and correlation | (needs phase 2 output) | NOT_EXECUTED |

Each grader stops at one gate, `nfl.postgame.outcome.require`, which returns
`BLOCKED[POSTGAME_OUTCOME_NOT_CAPTURED]`. There is no path around it and no
flag that relaxes it.

## Phase 5 — a correction to the request's premise

**There is no top-ten betting card for this game, because nothing was staked
and no price was ever accepted.** What section 8 of
`DET_BUF_PREKICKOFF_PROJECTIONS_2026-09-17.md` published was an ordering of the
43 supported lines by |model − market|, under an explicit "None of this is an
edge claim". `grade_props.py` grades the top ten of that ordering as
`CARD_AS_ORDERED` and reports ROI, realised performance and closing-line value
as `NOT_AVAILABLE` — not as zero.

Worth stating before any result exists, because it will be the first thing the
grade shows: **nine of those top ten rows are `ROLE_STATE_CONCERN`.** James
Cook (five lines), Dalton Kincaid (two), DJ Moore (two). The ordering by
disagreement with the market is very nearly an ordering by the severity of the
known Buffalo role defect. Whichever way those nine settle, they measure the
defect and not the model's edge, and they may not be read as either.

## Phase 12 — ingest without leakage

**DONE.** `nfl/postgame/eligibility.py` classifies every DET @ BUF artifact as
`PREGAME_FROZEN_ARTIFACT`, `POSTGAME_TRAINING_ELIGIBLE_ARTIFACT` or
`MARKET_EVALUATION_ONLY_ARTIFACT`, and `assert_may_train` refuses the first
two classes outright and embargoes the outcome from training any model
evaluated on this game. An artifact absent from the registry is refused rather
than defaulted to eligible.

The asymmetry it encodes: the same stat line is training-eligible for next
week's model and ineligible for this one. Eligibility is a property of the
pair (artifact, consumer), never of a file.

## Closing-line value is gone, and saying so now is cheaper than later

There is no closing player-prop vintage. The only prop capture is
2026-09-17T21:44–21:45Z, about two and a half hours before kickoff; vintages 2
and 3 are game-line displays at 23:05Z and 23:06Z. Unless a later Hard Rock
prop snapshot exists in storage outside this checkout, closing-line comparison
for this game is permanently `NOT_AVAILABLE` and will be reported that way
rather than approximated from the pre-kickoff board.

## What one slate could establish, if the outcome arrives

A defect, and a hypothesis. Not a threshold, not an exposure cap, not an
architectural reversal, and not a ranking of the two portfolio architectures
against each other. The ledger block exists so the record accumulates toward a
sample that can carry those claims; this game is one row in it.
