# DET @ BUF, week 2 2026 — postgame review

**Final: DET 31 @ BUF 41.** Captured, hashed, graded.

**One slate.** It can show a defect and generate a hypothesis. It cannot fit a
threshold, an exposure cap or an architectural choice, and it cannot rank the
two portfolio architectures against each other. Nothing below was tuned to it.

## Phase 1 — the outcome, captured

| artifact | source | sha256 |
|---|---|---|
| `FINAL_SCORE.json` | nfldata `games.csv` | `9c3b8476cb7d3fab…` |
| `OUTCOME.json` — 72 player rows | + nflverse `stats_player_week_2026.csv` | file hash recorded in the ledger |

Raw bytes were written to `raw/` before being parsed. The first three capture
attempts are on the record in `CAPTURE_ATTEMPT.json`: nflverse carried week 1
only until roughly 04:35Z, and the graders refused throughout rather than
grade against a partial box score.

The sentence relayed in conversation — "a high-scoring 41-31 game" — stays
recorded as `UNVERIFIED_SECONDARY — NOT INGESTED`. It did not say which side
scored 41. A hashed source does: Buffalo.

## Phase 2 — the board, stat by stat

29 players, 217 stat observations, **0 unscorable**.

**The model was low, and it was low almost everywhere.** Board DK total
predicted **189.5** against **250.4** actual, a ratio of **1.32**.

| player | predicted mean DK | actual DK | error | where the actual landed |
|---|---:|---:|---:|---|
| Josh Allen | 20.85 | 40.82 | −19.97 | ABOVE_P90 |
| Amon-Ra St. Brown | 18.54 | 38.20 | −19.66 | ABOVE_P90 |
| Dalton Kincaid | 5.88 | 22.50 | −16.62 | ABOVE_P90 |
| Jared Goff | 16.48 | 32.78 | −16.30 | ABOVE_P90 |
| James Cook | 8.82 | 23.90 | −15.08 | ABOVE_P90 |
| DJ Moore | 8.12 | −0.10 | **+8.22** | BELOW_P10 |
| Ray Davis | 7.16 | 0.00 | +7.16 | P10_P25 |

Bucket shares over all 217 observations, against nominal:

| bucket | observed | nominal |
|---|---:|---:|
| BELOW_P10 | 0.014 | 0.10 |
| P10_P25 | 0.032 | 0.15 |
| P25_P75 | 0.724 | 0.50 |
| P75_P90 | 0.138 | 0.15 |
| ABOVE_P90 | 0.092 | 0.10 |

**Read that as a shape, not a calibration result.** 217 observations from 29
players in one game are heavily correlated within player and within game, so
these shares have no usable standard error and none is quoted. What the shape
suggests — and it is a hypothesis for the ledger, not a finding — is a
predictive distribution that is too wide in the middle and roughly right in
the tails, in a game that ran hot.

**Seven players recorded nothing and are graded as zero, not dropped.** Frank
Gore Jr., Jackson Hawes, Jackson Meeks, Joshua Dobbs, Kyle Allen, Skyler Bell,
Tyler Conklin. Their clubs are in the outcome, so zero is a measurement.
Excluding them would have graded the model only on the players it got onto the
field — which are exactly the ones it got right.

## Phases 4 and 5 — the 43 frozen Hard Rock main lines

| | hits | n | rate |
|---|---:|---:|---:|
| model's own side | 18 | 43 | 0.419 |
| model's lean vs the market | 18 | 43 | 0.419 |
| `MODEL_SUPPORTED` | 9 | 27 | 0.333 |
| `ROLE_STATE_CONCERN` | 9 | 16 | 0.562 |

**No standard error is reported and the refusal is deliberate.** 43 lines over
16 players in one game are not 43 independent observations. The measured
understatement from naive binomial SEs on this project's prop grading is
roughly threefold. Cluster counts travel with every rate instead.

By the probability the model gave its own side: 0.50–0.60 → 12/19; 0.60–0.70 →
2/13; 0.70–0.80 → 2/5; 0.80–0.90 → 2/6. **The model did worse the more
confident it was.** On one slate that is a hypothesis with a cluster count of
eight, not a calibration curve.

**The card.** There is no staked card — nothing was wagered, no price was
accepted. Section 8's ordering by |model − market|, graded as
`CARD_AS_ORDERED`, went **4/10**. Nine of its ten rows were
`ROLE_STATE_CONCERN`, so it was very nearly an ordering by severity of the
known Buffalo role defect. Six of the ten were James Cook or Dalton Kincaid
unders; Cook ran for 135 and Kincaid caught 7 for 95.

ROI, realised performance and closing-line value are `NOT_AVAILABLE`, not
zero. There is no closing player-prop vintage and there never will be: the
only prop capture is 21:44–21:45Z, and vintages 2 and 3 are game-line displays
at 23:05Z and 23:06Z.

## Phases 6 and 7 — both portfolios, and the lineup that won

**Actual optimal 174.51** — CPT Josh Allen, with Amon-Ra St. Brown, Dalton
Kincaid, Dawson Knox, Jared Goff, Joshua Palmer, at $49,900.

| | mean | median | best | worst | regret | contains optimal |
|---|---:|---:|---:|---:|---:|---|
| delivered (CLAUDE) | 128.47 | 128.08 | 145.62 | 112.10 | 28.89 | no |
| ALTERNATE | 135.88 | 132.83 | 156.21 | 109.03 | 18.30 | no |

**This does not rank the two architectures.** The portfolios overlap heavily —
about 2.5 of 6 players' mean pairwise uniqueness — so forty lineups are not
forty independent samples and the gap is mostly variance.

What the pregame board said about the optimal lineup, before it was known:
Josh Allen `p_optimal` 0.65 but `p_optimal_captain` only **0.167**; St. Brown
0.558; Goff 0.559; Kincaid 0.142; Knox 0.170; Palmer 0.167. **The three cheap
pieces of the winning lineup were all `ROLE_STATE_CONCERN`.** A player rostered
for a bad reason who scores is still rostered for a bad reason, and nothing
here promotes an exposure because it worked once.

## Two defects this grading pass found in the graders themselves

Both were found because the numbers looked wrong, and both are now pinned by
tests.

**Identity.** DraftKings spells him *James Cook III*; the stat feed spells him
*James Cook*. A raw-string join dropped him, and with a zero-by-absence rule
sitting on top of it, the week's second-best running back would have been
scored as nothing. Same for *Joshua Palmer* against *Josh Palmer*. Identity is
now resolved through `universe.norm` before anything is scored or zeroed.

**Kickers.** `actual_dk` knew only offensive stats, so Jake Bates — a 31-yard
field goal and four extra points, **7.0 DK** — scored zero, in fifteen of
forty delivered lineups. The model's refusal to name a kicker is a statement
about the MODEL's (team, position) join and says nothing about what the box
score knows. Kicking is now carried in the outcome artifact with distance
buckets and scored through `DK.score_kicker`.

## Phase 12 — ingestion, with the classes kept apart

`eligibility.py` holds the line: `PREGAME_FROZEN_ARTIFACT` may never train,
`MARKET_EVALUATION_ONLY` may never train, and this outcome is embargoed from
any model evaluated on this game. The same stat line is training-eligible for
next week's model and ineligible for this one.

## The ledger

`DET_BUF_2026W2` was registered `AWAITING_OUTCOME` **before** the result was
capturable, with the scope pinned — 29 players, 12 stats, 43 supported lines,
two portfolios — and is now `GRADED` with every artifact hash attached. The
registration cannot be rewritten; a correction would be a further append.

## What this game does NOT establish

A calibration curve. A hit rate. A ranking of the two portfolios. A reason to
change an exposure cap, a threshold, a parameter or an architecture. It is one
row.

**POSTGAME_REVIEW_FROZEN**

**V2 NOT YET EARNED**
