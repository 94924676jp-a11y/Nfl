# R5 — product quality gates, the board pointer, and what they say about V1

Written 2026-09-14 at branch `claude/nfl-greenfield-architecture-stsxmk`,
HEAD `2dc44ab`, python3.12. Nothing here was committed, no sealed artifact was
read-modify-written, and no candidate was promoted.

**Deliverables**

* `nfl/product/quality_gates.py` — eight HARD gates, five SOFT diagnostics,
  the nine-state product vocabulary, and the K / DST absence verification.
* `nfl/product/board_pointer.py` — `V1_SEALED` and `MNF_REBUILD`, the atomic
  pointer swap, and the seal guard.
* `nfl/tests/test_quality_gates.py` — 24 test functions, **253 checks,
  `SUITE PASS`** under
  `python3.12 nfl/tests/run_suite.py --only test_quality_gates`.
* This report.

**Headline.** Run over every sealed board in the tree — 102 runs, all 15
week-1 games — the gates return **WITHHELD on 102 of 102**. Tonight's DEN@KC
V1 board is one of them, with **31 hard findings, 1 gate with no evidence at
all, and 6 soft flags**. That is not the gates being harsh; six of the eight
fire on a contradiction the board makes with its own fields, and each
threshold is a measurement with a citation.

---

## 1. The separation that the rest of this depends on

A HARD gate **withholds a row or quarantines a family or board**. A SOFT
diagnostic **flags for review and changes nothing** — no distribution, no
state, no pointer. The external contract makes this distinction and names the
trap: a healthy-QB1 low mean should send you to *starter probability and the
exit / replacement model*, **not to a yardage floor**.

That is enforced, not just written down:

* `SOFT_DIAGNOSTICS` entries carry `action: FLAG_FOR_REVIEW` only, and each
  one declares an `inspect` field and a `never` field. The test asserts no
  soft entry carries a quarantine or withhold action.
* `HEALTHY_QB1_LOW_CENTRAL_TENDENCY.never` reads, in the module:
  *"NOT a yardage floor. This diagnostic must never be discharged by raising a
  projection."*
* The module opens no file for writing, calls no `clip` / `fill` / `put` /
  `resize`, and never assigns into any name bound from the draw artifact. That
  is asserted on the AST, and the AST check is written so it is not vacuous:
  it first collects the names that actually came out of `DEC.matrix(...)` and
  `np.load(...)`, then asserts none of them is ever mutated. A blanket "no
  subscript assignment" rule would have flagged every dictionary in the file
  and would therefore have been ignored.
* Neither new module imports any market, odds or price module. Asserted on the
  imports. **A price is never an input to a gate.**

---

## 2. The eight hard gates

Every threshold below has an entry in `quality_gates.GROUNDING` carrying its
value, the sample it was measured on, and the artifact path it was read out
of. `test_b_every_threshold_is_grounded` fails on a constant that does not.

| gate | fires when | grounding | structural? |
|---|---|---|---|
| `HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY` | a row the board labels **QB1**, carrying no withholding designation, has `P(dropbacks == 0) >= 0.25` | week-1 depth-chart QB1s 2021–24: **0 zero-dropback games in 128**. Rule-of-three 95% upper bound **0.0234**. The model assigns ≥ 0.25 to **39.8%** of that population and up to 0.465. 0.25 is 10.7× the evidence bound. `D5_ZERO_MASS_AUDIT.md#2.3` | **Yes.** It is a contradiction between two of the board's own fields: `depth_chart` says QB1 and the draws say he may never take a snap. |
| `QB_ROOM_SPLIT_ANOMALY` | a team's QB room has `P(two or more passers at ≥ 5 dropbacks) > 0.078` | realised 2026 wk1 **0.000**; historical wk1 **0.039**; wks 2+ **0.078**; model **0.333**. The threshold is the *most permissive* of the three measured rates. `D7_CENTRAL_TENDENCY_SCORECARD.md#3` | **No, and it says so in its own declaration.** It triggers on a forecast probability against a measured base rate, so it quarantines only that one team's QB family. |
| `ROLE_STATE_SOURCE_CONFLICT` | the sources that fix a role state disagree, **or** a source the board names as its own authority was never consumed | the board's `qb_inactive_ownership` block, its `readiness` block and its `vintage_selection.refusals` — read from the artifact, not from a prior | **Yes.** The board asserts a role while recording that the evidence for that role was not ingested. |
| `AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY` | a player on an **ingested** official inactive list carries any opportunity mass | 28 officially inactive players who took zero snaps carried mean forecast participation **0.247** over 144 rows, 101 of them strictly positive; ATL's QB1 was listed **Out 42.7 h** before the seal and was still projected **19.7 dropbacks**. `D7#5` | **Yes.** An inactive player cannot take a snap. Positive mass is impossible, not unlikely. |
| `RUSH_ACCOUNTING_FAILURE` | any draw deals the named rush owners **more** carries than the team's own carry level (margin 0.5 carries), or any draw recovers a **negative** designed-rush count | largest observed over-allocation in the corpus is **13.45 carries** (ARI_LAC/LAC) — three orders above float noise, so 0.5 separates an over-deal from rounding and is not a materiality judgement. `D6#5` | **Yes.** `sum(owners) > level` is arithmetically impossible. |
| `COUNT_SUPPORT_FAILURE` | a metric declared `kind: 'count'` in `nfl/product/metrics.py` has non-integer or negative draws | `rushing/carries` is declared a count and is float64: **243,766 of 384,000 cells (63.48%)** non-integer across the sealed corpus — reproducing the 63.4% figure independently | **Yes.** A count with fractional support cannot occur, and every published "10+ carries" probability is computed on values the world cannot produce. |
| `IDENTITY_DEPTH_ROLE_CONFLICT` | a row has no human-readable name, no declared position, layers its position may not draw from, or a depth-chart tag that disagrees with its roster position | `metrics.POSITION_LAYERS` and the board's own `depth_chart` / `position` / `layers` fields | **Yes.** A row that cannot be rendered as a person is not a product row. Escalates to **board scope** when *every* row is nameless. |
| `UNATTRIBUTED_OPPORTUNITY_MASS` | a team pool the board publishes shares against has **positive mass and zero owner rows** | 67 sealed team-runs with a rushing layer: mean unowned **24.10%**, range **0.616%–45.290%**. `D6#5`. The gate does not trigger on that range — it triggers on *no owner existing at all* | **Yes.** Every share published against that pool has a denominator no row can be checked against. The mass is unattributable in principle, not merely unattributed. |

### The five soft diagnostics

| diagnostic | flags when | what to inspect | what it must never do |
|---|---|---|---|
| `HEALTHY_QB1_ZERO_MASS_ABOVE_EVIDENCE_BOUND` | `0.0234 < P(zero db) < 0.25` | starter probability, exit / replacement | no rescaling, no clipping of the zero mass |
| `HEALTHY_QB1_LOW_CENTRAL_TENDENCY` | unconditional mean sits >10% below the mean over draws where he plays | starter probability and exit / replacement — the gap *is* mass moved off him | **not a yardage floor**; never discharged by raising a projection |
| `ROOM_TOP_SHARE_BELOW_HISTORICAL` | mean top-passer share < 0.9289 | the room allocation | nothing is reallocated |
| `RUSH_UNOWNED_SHARE_OUTSIDE_CORPUS_RANGE` | mean unowned share outside [0.00616, 0.45290] | A1's `kneel` / `wr` / `te` / `fringe`, which own the residual lawfully | a positive residual is expected and lawful and is never repaired |
| `DEGENERATE_DISTRIBUTION_WIDTH` | the board's own confidence component reports the middle half of the draws identical | whether it is a real point mass or a collapsed allocation | the distribution is not widened |

### How the gates behave across the whole sealed corpus

102 boards, evaluated with the same code. A gate that fires everywhere is
worth knowing about, and two do.

| hard gate | boards it fires on (of 102) |
|---|--:|
| `IDENTITY_DEPTH_ROLE_CONFLICT` | 102 |
| `QB_ROOM_SPLIT_ANOMALY` | 102 |
| `HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY` | 75 |
| `RUSH_ACCOUNTING_FAILURE` | 75 |
| `UNATTRIBUTED_OPPORTUNITY_MASS` | 69 |
| `ROLE_STATE_SOURCE_CONFLICT` | 64 |
| `COUNT_SUPPORT_FAILURE` | 34 |
| `AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY` | **0 — and never PASS either; it is `INSUFFICIENT_EVIDENCE` on all 102** |

**Stated against my own work:** `QB_ROOM_SPLIT_ANOMALY` at 102/102 and
`IDENTITY_DEPTH_ROLE_CONFLICT` at 102/102 carry no discriminating information
today. They are correct — the name defect really is universal and the split
room really is systematic — but a gate that never distinguishes two boards
cannot rank them, and if either is ever proposed as a *promotion criterion*
rather than a *publication criterion* it will need re-deriving on a frame
where it varies. `COUNT_SUPPORT_FAILURE` at 34/102 is the shape a gate should
have: it fires exactly on the runs that sealed a rushing layer.

---

## 3. What the gates say about the V1 board as it stands

`nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1`,
run `f91342d6787a66a1`. **140 findings: 31 hard fired, 1 hard with no
evidence, 6 soft flagged. Board state WITHHELD.**

| finding | measured | reading |
|---|---|---|
| `HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY` — **KC/00-0033873** | `P(zero dropbacks) = 0.4120`, mean 22.82 db, no withholding designation on the row | **17.6×** the rule-of-three evidence bound. The board says he is the QB1 and says he has a two-in-five chance of never dropping back. |
| same gate — **DEN/00-0039732** | `P(zero dropbacks) = 0.0480` | **PASSES** the hard gate and raises the soft one at 2.05× the bound. The asymmetry reproduces D5 exactly: one club's chart QB1 is also the previous primary and the other's is not. |
| `QB_ROOM_SPLIT_ANOMALY` — **KC/qb** | `P(2 QBs ≥ 5 db) = 0.480`, **6.2×** the highest measured base rate; mean top-passer share 0.849 | fires |
| `QB_ROOM_SPLIT_ANOMALY` — **DEN/qb** | `0.102`, **1.31×** | fires, marginally. Recorded as marginal rather than dressed up. |
| `ROLE_STATE_SOURCE_CONFLICT` — **both clubs** | `qb_inactive_ownership.enforced = False`, failed conditions `official_inactive_evidence_ingested`, `evidence_tied_to_this_game_and_team`, `no_unresolved_identity`; DEN readiness `INJURY_REPORT_INCOMPLETE` (1 row, `report_status` unfilled on all of it) | the board publishes a QB room whose own ownership mechanism records that the evidence for it was never ingested |
| `RUSH_ACCOUNTING_FAILURE` — **KC/rushing** | **390 of 1,000 draws** deal the named owners more carries than KC's own carry level, by up to **9.96 carries**; 0 negative designed-rush draws | arithmetically impossible on 39% of the draws |
| `COUNT_SUPPORT_FAILURE` — **KC's three RBs** | `rushing/carries` is float64 and non-integer in **795 / 604 / 783** of 1,000 cells | reproduces D1's 795 exactly for RB1 |
| `UNATTRIBUTED_OPPORTUNITY_MASS` — **DEN/rushing** | pool `team_carries` mean **27.55**, owner rows sealed **0**, unattributed share **1.0** | |
| `UNATTRIBUTED_OPPORTUNITY_MASS` — **DEN/receiving** | pool `team_targets` mean **33.75**, owner rows sealed **0**, unattributed share **1.0** | |
| `IDENTITY_DEPTH_ROLE_CONFLICT` | **19 of 19 rows** carry no name → escalated to `WITHHOLD_BOARD` | see §6 |
| `AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY` | **INSUFFICIENT_EVIDENCE** | see §5 |

### Three things this measurement corrects or sharpens

**(a) The 0.6% unowned rush figure is the best case only if you read the mean,
and the mean is the wrong statistic here.** Tonight's KC board does carry the
smallest mean unowned share in the corpus — I re-derived it at **0.616%**
against a corpus mean of 24.10% — but it simultaneously carries **390 of
1,000 over-allocated draws**, and D6 already recorded the anti-correlation:
*"A small mean here is cancellation, not closure... Any future summary that
ranks boards by mean residual will rank them close to backwards."* So
`RUSH_ACCOUNTING_FAILURE` is written on the **count of impossible draws**, not
on the residual mean, and the residual mean is demoted to a soft diagnostic.
On that reading tonight's board is not the corpus best case; it is among the
worst.

**(b) The unowned-rush range does not cover DEN, because DEN is not in the
frame at all.** The 24.1% / 0.6–45.3% frame is the **67 team-runs that sealed
a rushing layer**. There are **137 team-runs in the same corpus with no
rushing rows whatsoever**, DEN tonight among them. For those the mass is not
24% unowned, it is **100% unattributable**, and quoting the corpus range at
them would put a number where a missing family belongs. That is why the
no-owner case is a separate gate rather than the tail of a distribution.

**(c) DEN is missing 14 of its 33 intended rows, and the run record says so.**
`DEN_KC_LIVE_RUN_RECORD.json` records `intended_full_two_team_board: 33`,
`total_player_rows: 19`, `missing: 14`, `missing_all_from: "DEN"`,
`missing_cause: "APPEARANCE_TEAM_DEFERRED_DEN"`. The board has **three DEN
quarterbacks and no other Denver player** — no RB, no WR, no TE. My gates
found the consequence independently from the draws before I read that line,
which is the check I wanted on them.

---

## 4. The board pointer, and how the V1 seal is protected

Two named identities, one small pointer file, and **the pointer is the only
thing that ever moves**.

```
V1_SEALED     nfl/research/live/2026_01_DEN_KC/
              PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1
              run_id f91342d6787a66a1                        IMMUTABLE
MNF_REBUILD   registered at build time by register_candidate()
active pointer -> nfl/research/v2/r5/active_board_pointer.json
```

**Seal protection, in four independent mechanisms.**

1. `_assert_writable()` resolves every destination (following symlinks and
   normalising `..` *before* the containment test) and raises `SealViolation`
   for anything under `nfl/research/live/`, **and** for anything outside
   `nfl/research/v2/r5/`, which is the only directory this module owns. A
   swap therefore cannot write into a board even by accident.
2. `verify_seal()` re-derives the sealed board's digests on **every** pointer
   operation, including one pointing somewhere else entirely, and compares
   them to constants frozen in the module. A mismatch is `FAIL
   SEAL_INTEGRITY_VIOLATED` — never a repair and never a new baseline.
3. **The two digests are different objects and were conflated once, by me.**
   `41350b5bac617b709c81f609fe3818b5` is not the board's `draw_content_digest`
   and is not a prefix of it. It is the **determinism-proof draw digest** in
   `DEN_KC_LIVE_RUN_RECORD.json` (`determinism_proof.draw_digest`, 22/22
   arrays bit-identical over 134,000 cells across two independent output
   roots). The board's own content digest is the 256-bit
   `86e3707db4...c46b26a`. Both are frozen, both are re-read from their own
   file, and the module does not choose between two provenance claims.
   Verified state right now: `SEAL_INTACT`, all three match.
4. The test module hashes every file under the seal at import and again at the
   end, and fails if a byte moved. It also proves the tamper path *does* fail,
   on a temporary **copy** — the seal itself is never written to.

**The swap.** `swap(to=...)` returns PASS only when the pointer actually
moved. Every refusal leaves the previous pointer exactly where it was.

1. `verify_seal(V1_SEALED)` — intact.
2. `_no_mixed_versions(candidate)` — board `run_id`, `game_id` and
   `draw_content_digest` must equal the manifest's, the draw file must hash to
   the board's declared `draws_sha256`, and **every board row must resolve to
   a row of this manifest**. A board assembled from two runs is refused, not
   published with a footnote.
3. **The hard gates are re-run here over the candidate's own artifact.** A
   caller-supplied verdict is never accepted, and `swap()` takes no
   `verdict` / `passed` / `force` / `override` argument — asserted on its
   signature. That is the same defect `authorization.ForbiddenBasis` exists to
   refuse: a decision taken from a flag instead of from the facts.
4. `authorization.may_publish()` is **consulted, not reimplemented**. The
   module defines no `may_publish` of its own and weakens nothing.
5. Refusal reasons are recorded **separately** — `blocked_by` lists
   `QUALITY_GATES`, `QUALITY_GATES_INSUFFICIENT_EVIDENCE` and
   `AUTHORIZATION:<code>` as distinct entries — so "the gates failed" and
   "nobody authorized it" are never read as one thing.
6. The write is `os.replace` over a temp file in the same directory after
   `fsync`, so a reader sees the old pointer or the new one and never a torn
   one, and it is version-checked: a swap racing another swap fails
   `POINTER_VERSION_CONFLICT` and writes nothing.

**Publication state stays `PRELIMINARY_PROVISIONAL` on both paths.** `FINAL`
is declared in the vocabulary and is never assigned. No gate result and no
green suite can raise it — `FINAL` requires an authoritative inactive list,
and tonight there is none.

**Stale rather than blank.** `begin_candidate()` records a rebuild in flight;
`resolve()` keeps returning the prior identity with `stale: true` and a
warning naming what is computing and since when. Blanking the board during a
rebuild would replace a stale number with no number and tell the reader less.
The most recent refusal is also surfaced to the reader, so *why* nothing newer
is showing is visible on the product rather than in a log nobody opens.

**Live result.** `swap('V1_SEALED')` returns
`BLOCKED BOARD_SWAP_REFUSED`, blocked by
`['QUALITY_GATES', 'QUALITY_GATES_INSUFFICIENT_EVIDENCE', 'AUTHORIZATION:NFL1_NOT_AUTHORIZED']`.
The pointer did not move. There is currently **no active user-facing board**,
and `resolve()` says so in those words rather than offering an empty page.

---

## 5. Honest missingness — the nine states

| state | means | carries a number? | publishable? |
|---|---|:--:|:--:|
| `FINAL` | every input is authoritative and settled | yes | yes |
| `PRELIMINARY` | best information at the seal, outstanding inputs named | yes | yes |
| `UNVALIDATED` | produced, no gate evaluated against it | yes | **no** |
| `WITHHELD` | produced, and a hard gate refuses to show it | **no** | no |
| `UNAVAILABLE` | no governed layer produces the quantity at all | **no** | no |
| `DATA_ERROR` | an input was missing, empty or out of schema | **no** | no |
| `MODEL_ERROR` | the engine produced something structurally impossible | **no** | no |
| `INSUFFICIENT_EVIDENCE` | a gate could not be evaluated for want of evidence | **no** | no |
| `INELIGIBLE` | a governance rule excludes the row or family | **no** | no |

Six of the nine carry no number, and the test asserts that anything
`publishable` must carry one. **Missingness is never replaced by a number to
make the board look complete.**

`INSUFFICIENT_EVIDENCE` is the state this vocabulary exists for.
`AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY` lands there on all 102 sealed
boards and on tonight's, and **never returns PASS without an ingested list**.
The cost of the alternative is measured: treating "no list" as "nothing
wrong" is exactly how 28 officially inactive players kept a mean forecast
participation of 0.247, and how one club's QB1 was projected 19.7 dropbacks
42.7 hours after being listed Out.

I have not attempted `FINAL` and the module refuses to write it. Your source
ladder is consistent with what I can see from here: I have no network at all,
so I can neither confirm nor extend it, and I have not marked anything blocked
on it — the board-pointer path does not need it to work, it needs it to reach
`FINAL`, which it correctly does not claim.

---

## 6. K and DST — verified against the code, not taken on your word

Both verdicts: **`UNAVAILABLE`**, and `verify_absent_families()` re-derives
them from the registry at call time rather than asserting them, so the day a
layer appears the claim stops being made.

### K — `NO_KICKING_OR_SCORING_CONTRACT`

**Evidence.** `nfl/product/metrics.py` `POSITION_LAYERS` declares exactly
`QB`, `RB`, `WR`, `TE` — no `K`. Neither `SUPPORTED` nor `UNSUPPORTED`
declares any field-goal, extra-point, kick-distance or team-points metric. No
such array is sealed: the draw manifest carries 22 matrices across
`qb`, `receiving`, `rushing` and `team_volume`, and none of them is a kicking
or scoring quantity. Grepping `nfl/production/`, `nfl/product/`, `nfl/schema/`
and `nfl/accounting/` for field goal / extra point / kicker / punt terms
returns exactly two real hits, and **neither is a forecasting layer**: a punt-
and kick-returner note in `pool_audit.py`, and a `play_type: 'field_goal'`
carve-out in `nfl/accounting/invariants.py:198` for a blocked field goal in
historical play-by-play. There is nothing to withhold, because there is
nothing computed.

**What it would need.** (i) A team scoring-drive / red-zone conversion layer
producing field-goal **attempts as a distribution**, not a rate on a mean.
(ii) A **distance** distribution for those attempts — make probability is a
function of distance, and a pooled make rate would misstate its own
uncertainty. (iii) An extra-point opportunity count, which is a function of
modelled touchdowns the team layer does not close —
`team_touchdowns_close` is already a declared ABSENT contract in
`nfl/product/conservation.py`. (iv) A kicker identity and status feed;
kickers do not reach the board through the roster reduce at all.

### DST — `NO_OPPONENT_LINKED_DEFENSIVE_LAYER`

**Evidence.** The only sack quantity anywhere in the artifact is `qb/sacks`,
and `nfl/production/qb_v1.py` uses it on the **offensive** side of the
identity `dropbacks == attempts + sacks + scrambles` (`qb_v1.py:266`) — sacks
**taken** by the passer, never credited to a defence. `qb/int` is
interceptions **thrown**, not takeaways forced; there is no fumble quantity at
all, so a takeaway count built from `qb/int` alone would be a systematic
undercount presented as a forecast. The only place an opponent is read
anywhere in `nfl/production` is `coupling_rho` at
`nfl/production/team_volume_v1.py:364`, which couples two teams' **volume**
and produces no defensive quantity. No points-allowed, yards-allowed,
takeaway or defensive-touchdown distribution exists.

**What it would need.** (i) An offence–defence join so one team's *allowed*
stats are the other team's *produced* stats **on the same draw index**. Today
that is not merely absent, it is contradicted by the artifact: the manifest's
own `draw_index_semantics.across_rows` is
`INDEPENDENT_STREAMS_COLUMN_ALIGNED`, and it warns in its own words that a
cross-row correlation read off that axis "measures the generator's lack of
coupling, not a football quantity". (ii) A turnover layer including fumbles.
(iii) A points-allowed contract — which needs the same scoring layer K needs.
(iv) Defensive and special-teams touchdowns, which no layer produces.

**Verdict on both: produce them as `UNAVAILABLE` with the reason and the gap
named. Do not synthesise either tonight.** A DST number assembled from
`qb/sacks` and `qb/int` would be the exact move `metrics.py` calls the
anti-fabrication spine of the product layer — a plausible number where a blank
looks like a bug.

---

## 7. The name defect, stated as a product defect

Every one of the 19 rows on the sealed V1 board has **no name field at all**.
It is not `name: None` in this artifact — the key is absent, which is the same
defect one step further along: a renderer reaching for `row['name']` gets a
`KeyError`, and one using `.get()` prints a gsis_id.

The cause is two-sided and both sides are in the tree:

* `nfl/product/board.py:build()` never joins a name. `nfl/product/names.py`
  exists, is documented for exactly this ("gsis_id -> player name, for DISPLAY
  ONLY"), and is imported by `market_comparison.py`, `market_product_export.py`,
  `stage_delta.py`, `run_market_diagnostic.py` and `make_board.py` — **every
  consumer except the board itself**.
* The vintage the board *does* read cannot supply one. `nfl/capture/registry.py`
  reduces the weekly roster to
  `('season', 'week', 'team', 'gsis_id', 'position')` — `full_name` is dropped
  at the reduce step, which `nfl/tools/ingest_inactives.py:292` already
  records: *"full_name is not retained for the vintage the pool uses"*.

So this is a one-line join away on one side and a `reduce_cols` change away on
the other, and it is worth stating plainly because it is the single defect that
makes the board unpublishable **as a product** independent of every modelling
question in this report. I have not fixed it: `board.py` and the capture
registry are not mine, and a reduce-column change is a capture-contract change.
`IDENTITY_DEPTH_ROLE_CONFLICT` escalates to `WITHHOLD_BOARD` when every row
fails it, which is the honest product answer in the meantime — withholding 19
rows individually and calling what remains a board would be a board of nothing.

---

## 8. Limits, stated against my own work

* **Nothing here is evidence that a gate is correctly calibrated.** Each
  threshold is asserted to be *declared, sourced and behaving as declared* —
  not to be right. No equivalence margin is predeclared and no TOST is run, so
  no gate is written as "correct", "stable" or "closed".
* **Two gates fire on 102 of 102 boards** and therefore carry no
  discriminating information today (§2). They are publication criteria, not
  promotion criteria, and must not be reused as the latter without
  re-derivation on a frame where they vary.
* **The 128-game QB1 frame and the 18 team-game split frame are the same
  development data** that produced D5 and D7. Thresholds set on them are
  reasonable operating points, not confirmatory findings, and a gate tuned on
  a frame cannot also be evidence about that frame.
* `ROLE_STATE_SOURCE_CONFLICT` currently reads three named board fields. It
  will not see a conflict between two sources the board does not carry, and it
  does not pretend to — a source the board never records is invisible to it.
* I did not run the full suite, only `--only test_quality_gates` as instructed,
  so I have no statement about any other module's state.
* `swap()` has never been observed to return PASS, because no board has yet
  cleared both the gates and NFL-1. The success path is exercised only by
  construction, not by a real promotion. That is a real gap in the evidence
  for the swap, and I am naming it rather than letting 253 green checks imply
  otherwise.
