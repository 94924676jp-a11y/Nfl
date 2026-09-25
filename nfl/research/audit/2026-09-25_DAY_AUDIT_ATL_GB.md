# Day audit — 2026-09-24/25, ATL @ GB

Written 2026-09-25 ~04:15Z, about four hours after the final whistle. Every
number here was read out of this repository or out of a named external source
cited in place. Where a figure could not be established it says
NOT_ESTABLISHED rather than carrying an estimate.

## 1. The game happened, and the board never published

**Final: Atlanta 35, Green Bay 14**, at Lambeau. Scoring summary as reported by
packers.com in-game updates, NBC News, footballnationusa and The Falcoholic,
consistent across all four:

| Q | play | score |
|---|---|---|
| 1 | Love → Watson, 4 yd | GB 7-0 |
| 1 | Bijan Robinson, 3 yd run | 7-7 |
| 2 | Folk 44 yd FG | ATL 10-7 |
| 2 | Penix → Hooper, 5 yd | ATL 17-7 |
| 3 | Brian Robinson, 7 yd run | ATL 24-7 |
| 3 | Folk 31 yd FG | ATL 27-7 |
| 4 | Love → Golden, 15 yd | ATL 27-14 |
| 4 | Bijan Robinson, 2 yd run + 2-pt | ATL 35-14 |

The board (`nfl/research/v2/r5/active_board_pointer.json`, pointer_version 139)
never left `PRELIMINARY_PROVISIONAL`. Its last refusal stands at
`NFL1_NOT_AUTHORIZED`, blocked by `QUALITY_GATES`,
`QUALITY_GATES_INSUFFICIENT_EVIDENCE` and the authorization code. **The board
was right to refuse and the refusal reasons named, in advance, two of the three
things that actually went wrong.** That is the most important sentence in this
document.

## 2. Player grading, verified components only

DK NFL classic scoring. A LOWER BOUND row means the verified stat line is
incomplete (e.g. a TD catch is confirmed but the receiver's total yardage is
not), so the true score is at least the figure shown. Percentile is the actual
against that player's own 8,000 stored draws.

| player | model mean | p90 | actual | pctile | |
|---|---|---|---|---|---|
| Bijan Robinson | 21.35 | 35.4 | **34.4** | 89% | 29 car, 194 yd, 2 TD — LOWER BOUND |
| Drake London | 11.09 | 22.6 | **31.4** | 97% | 9 rec, 194 yd — complete |
| Jordan Love | 15.25 | 26.3 | **22.5** | 81% | 28/53, 312, 2 TD, 1 INT — LOWER BOUND |
| Michael Penix Jr. | 14.13 (cond.) | 17.9 | **13.2** | 83% | 18/25, 256, 1 TD, 1 INT — LOWER BOUND |
| Nick Folk | 8.26 | 15.0 | **10.0** | 64% | 2/2 FG, 3/3 XP — complete |
| Matthew Golden | 9.48 | 21.2 | **8.5** | 54% | 15-yd TD — LOWER BOUND |
| Austin Hooper | 3.41 | 9.7 | **7.5** | 84% | 5-yd TD — LOWER BOUND |
| Christian Watson | 13.30 | 28.3 | **7.4** | 34% | 4-yd TD — LOWER BOUND |
| Brian Robinson Jr. | 7.15 | 16.3 | **6.7** | 57% | 7-yd TD run — LOWER BOUND |
| Trey Smack | 8.13 | 14.0 | **2.0** | 6% | 2 XP, no FG — complete |

NOT_ESTABLISHED, no verified line available from any reachable source: MarShawn
Lloyd, Tucker Kraft, Jahan Dotson, Kyle Pitts Sr., Chris Brooks, J. Michael
Sturdivant, Chris Blair, Jonnu Smith. A request for the authoritative box score
is in the outbox; until it lands this grading is partial and is labelled so.

### What the player grades say

* **The Penix conditional was the best call of the day and was made in the
  wrong place.** Predicted 14.13, actual 13.24. The stored marginal would have
  said 4.63, because it carried a 69% chance of near-zero for a confirmed
  starter. The correction was right and it was applied by hand in a DFS
  selector instead of being routed through the gate that exists for exactly
  this, `HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY`. A right answer obtained outside
  the governance is worse than a wrong one obtained inside it, because it
  teaches the wrong lesson about where correctness comes from.
* **Atlanta's two stars both landed in the top decile of their own
  distributions** (Bijan 89th, London 97th). The model's central tendency was
  too low on both, and London most of all.
* **Both kickers were projected and both projections were usable.** Folk 8.26
  → 10.0. Smack 8.13 → 2.0. See §4.
* **The clearest single over-projection was Kyle Pitts Sr.** at mean 7.95
  against a player PFF reports has two catches across three games.

## 3. Portfolio grading

Ten entries were uploaded (`nfl/dfs/entries/2026-09-25_ATL_GB_DKEntries_UPLOAD.csv`).
Verified floor = sum of verified components only, so each is a true lower bound
with the unscored-slot count beside it.

| # | CPT | proj mean | verified floor | unscored slots | floor − proj |
|---|---|---|---|---|---|
| 1 | Bijan | 81.47 | 89.0 | 2 | +7.5 |
| 2 | Bijan | 80.88 | **102.2** | 1 | **+21.3** |
| 3 | Watson | 78.87 | 81.2 | 2 | +2.3 |
| 4 | Watson | 78.20 | 74.7 | 2 | −3.5 |
| 5 | Love | 77.43 | 76.6 | 3 | −0.8 |
| 6 | Love | 76.21 | 75.5 | 3 | −0.7 |
| 7 | Penix | 72.29 | 58.7 | 3 | −13.6 |
| 8 | Penix | 69.88 | 66.5 | 2 | −3.4 |
| 9 | Lloyd | 66.00 | **53.1** | 3 | −12.9 |
| 10 | London | 64.36 | 68.8 | 3 | +4.5 |

Spearman rho between projected mean and verified floor is **0.867** on n=10.
That is indicative only — the floors are partial and the ten lineups share most
of their players, so these are not ten independent observations. It is not
evidence of discrimination and must not be quoted as such.

### The finding that costs the most

Restricting to the ten players whose actual score is verified, the best legal
lineup available at lock was:

> **CPT Drake London** + Bijan Robinson, Jordan Love, Michael Penix Jr.,
> Austin Hooper, Brian Robinson Jr. — $50,000 exactly, **131.4 points**.

Our best verified floor was 102.2, and **we ranked London captain tenth of
ten.** London was in fact the best captain on the board. The reason is
structural, not a tuning error: the shape that won was a correlated Atlanta
blowout — Bijan, London, Penix, Hooper, B. Robinson and Folk all scoring
together, driven by one shared game state. Independent per-player streams
cannot represent "Atlanta wins by three scores" as a coherent world, so the
selector could not see that shape at all. It ranked by marginal means, and
marginal means are blind to exactly the correlation that decides a Showdown
contest.

This is the dependence limitation showing up as a measured loss rather than as
a caveat in a doctrine file. It is the strongest argument yet for **B3, the
minimal shared-football-world candidate**, and I would now rank B3 above every
other item on the football-research track.

Our exposure was also the wrong way round for the result: Love 6, Watson 6,
Lloyd 6 against Bijan 6, Penix 6. Half the portfolio's weight sat on the losing
side of a 35-14 game.

## 4. The kicker join failure, and its honest cost

I told the owner the model "cannot project" kickers. That was false. The draw
artifact carries a `kicking` layer with both of them, and they had the lowest
zero-probability of any players in the pool (P(≤0.5) of 0.022 and 0.023). The
selector built its universe from the `dk_scoring` layer alone and never joined
`kicking` — a join that returned a partial result and was read as a complete
one, which is the single most expensive defect class in this project.

**The cost was not what I implied when I admitted it.** Measured against actual
results: Folk scored 10.0 against a projection of 8.26, so including him would
have helped. Smack scored 2.0 against 8.13, so including him would have hurt.
The process defect is real and the scoring consequence was mixed. Reporting the
defect as a straightforward loss would have been a second error on top of the
first.

Genuinely unprojected, confirmed: both DSTs (no layer exists) and Kedon Slovis
(absent from the 30 modelled rows).

## 5. Board review — the gates were right

Two gate states from the last refusal, quoted from the pointer:

* `AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY` — **INSUFFICIENT_EVIDENCE**, not
  passed: no authoritative inactive list was ingested. Measured cost of treating
  it as passed: 28 officially inactive players carried mean forecast
  participation 0.247, with 101 of 144 rows strictly positive, and one club's
  QB1 was projected 19.7 dropbacks.
* `HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY` — **fired**, WITHHOLD_ROW on a QB
  labelled QB1 and simultaneously assigned P(zero dropbacks) = 0.412 against a
  realised rate of 0 in 128 week-1 chart QB1s.

Both described the failures that then occurred. Jayden Reed, declared OUT, held
0.241 of the WR gadget draws. Josh Jacobs, on the exempt list, was in the
searchable universe until the owner caught it. Penix, the confirmed starter,
carried 69% near-zero mass. **The governance layer was ahead of me on every one
of these.** What was missing was not a gate but the wiring that makes a fired
gate stop a downstream consumer, and a DFS selector is a downstream consumer.

## 6. Errors I made today

Thirteen, in the order they were made. Each is listed because the pattern
matters more than any single one.

1. Claimed no source in the repository could supply official inactives. False —
   I had probed for the string `Inactives:` with a colon and the documents do
   not use it. Deleted the finding and wrote a corrected one.
2. The repaired inactives parser then produced a **false positive**: `GB:
   ['Justin Jefferson']`, a Vikings receiver attributed to Green Bay. Fixed by
   requiring position-prefix entry grammar instead of first-mention anchoring.
3. `source_validity.RESTRICTED` failed every purpose — a FAIL with a nicer
   name. Made it purpose-scoped via `authorised_for`.
4. The discovery auditor counted its own six references. Excluded self; the
   test now asserts it.
5. The AUDIT-0 tracer silently fell back `refusal_code` → `code` and would have
   reported 11 of 14 stages as covered. Fixed to record `code_kind`.
6. Wrote a standalone inactives parser when `nfl/production/nonqb/inactives.py`
   already existed. Deleted mine, fixed production.
7. Opened a QB ticket already measured on n=699 in
   `qb_v1.KNOWN_LIMITATIONS['multi_qb_over_prediction']`. Withdrew it.
8. The first portfolio violated the owner's directive outright — one player in
   all ten lineups, one thesis with zero coverage.
9. Claimed ten commits were unpushed, from a stale `refs/remotes/origin/…`.
   `git ls-remote` disproved it within a minute.
10. Used `pgrep -f run_suite.py`, which matched my own shell command, making
    every "suite is running" report unreliable.
11. Cited 402 PASS rows as a live defect; REG-1 showed they predate the 09-16
    repair.
12. **The kicker join failure and its wrong diagnosis** (§4).
13. **Filed two outbox items as needing "bytes we do not have" without ever
    testing egress.** `WebSearch` works in this session and was available the
    whole time. The nuance matters and cuts both ways: WebFetch is blocked for
    every sports domain tried (ESPN, PFR, CBS, Fox, Yahoo, packers.com,
    site.api.espn.com — all `EGRESS_BLOCKED` or proxy 403), so search returns a
    **secondary relay**, not a content-bearing artifact with provenance, and the
    governed pipeline is right to refuse it. The outbox items were correctly
    filed; the sentence "bytes we do not have" was wrong and should have read
    "no content-bearing source, though a secondary relay is reachable."

Read together, eleven of the thirteen are one failure: **a step returned
something partial or empty and I treated it as complete.** A wrong-string probe,
a first-mention match, a self-counting audit, a silent key fallback, a stale
ref, a self-matching pgrep, an unjoined layer, an untested network assumption.
The project already names this as its most expensive class. It is still the one
producing the errors.

## 7. What I would change, ranked

1. **Promote `unavailable_owns_nothing` from DIAGNOSTIC to HARD, and make a
   fired gate block the DFS selector.** The gates saw Reed, Jacobs and Penix
   before I did and nothing downstream was obliged to listen. Owner's call on
   the promotion; the wiring is not.
2. **B3, the shared-football-world candidate, moves to the top of the football
   track.** §3 is the first measured cost of its absence: 131.4 was available,
   we ranked its captain last, and no amount of marginal-mean work reaches it.
3. **Every layer join asserts its key coverage and names the missing side.** The
   kicker gap would have been a loud refusal instead of a silent 27-of-29
   universe.
4. **Probe the environment instead of inheriting its description.** One curl at
   the start of the day would have settled §6.13 and changed how two outbox
   items were worded.
5. **Model K and DST, or refuse to present a Showdown portfolio.** A selector
   that cannot see two of the six roster positions is not searching the contest.
6. **Grade the entered portfolio automatically against a box score** (C1). This
   document was assembled by hand four hours after the whistle and is partial
   because of it.

## 8. What remains unestablished

* Eight of the twenty-six players in the entered lineups have no verified stat
  line. The floors in §3 are lower bounds, not scores.
* The contest result — where these ten placed, what the winning score was, what
  the field looked like — is entirely unknown. Nothing in this document says
  anything about whether the portfolio won money.
* Nothing here is evidence about model quality in general. It is one game, it
  was selected by the owner's contest and not by us, and the project's own rules
  forbid promoting on a single game.

V2 NOT YET EARNED
