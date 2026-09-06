# W8 — Benchmark and DFS layer

**Worker 8, NFL Greenfield Architecture research pass. Written 2026-09-06.**

**Status: RESEARCH ARTIFACT.** No code written, no production file touched, no
wager, no play, no lineup, no recommendation to stake anything, anywhere in this
document including its examples. `v7/board_config.json:303` holds
`real_money.status` NOT ENABLED and `:306` holds `weekly_exposure_cap` UNSET with
`unset_is_blocking: true`. Nothing here changes that and nothing here should be
read as moving toward it.

## Labelling

Per `nfl/research/_GROUNDING.md:9-17`, every substantive claim below carries one
of:

- **VERIFIED** — I ran the command or opened the file in this container, this
  pass, and cite it.
- **DERIVED** — arithmetic or logic from something VERIFIED, with the derivation
  shown.
- **UNVERIFIED-RECALL** — believed from training, **not** checked. A lead, never
  a constant, never the basis of a design commitment.

**A fourth label is needed here and I am adding it explicitly**, because this
repository contains prior research compiled in an environment that *did* have
network:

- **REPO-RECORDED** — the repository asserts it, with a source URL, from a
  session that could fetch. I can verify *that the file says it*; I cannot
  re-verify the external fact. Treat as stronger than UNVERIFIED-RECALL and
  weaker than VERIFIED.

General web egress is blocked in this container. I therefore state **nothing**
about a DFS site's roster rules, salaries, rake, payout curves, contest sizes or
ownership as fact. Every such number is an outbox item in §6.

## What already exists that this builds on, so it is not rebuilt

- `docs/research/v8gap/DFS_ARCHITECTURE_GAP_REPORT.md` (661 lines) — Worker 7's
  MLB-side DFS report, 2026-09-06. **VERIFIED (read).** Its §2 (forecast quality
  vs strategy quality), §5.2 (why cheaper storage options fail), §7.2 (the solver
  is not a forecaster) and §7.4 (DFS ambition may not admit a projection feature)
  are correct as written and are **adopted here by reference, not restated**.
  This document supplies the NFL-specific arithmetic, the interface contract, and
  the market-floor consequence, which are not in it.
- `v8/V8_SYSTEM_CONSTITUTION.md:342-361` Rule 016 "Three engines, one direction
  of flow". **VERIFIED.** Its enforcement line reads *"**To be built** as an
  explicit input-set check."* §1 below is a specification for that check.
- `v7/guards.py:5235-5270` `assert_price_use_permitted`, with allowlist
  `('research_comparison', 'diagnostic_analysis')` and denylist
  `('promotion', 'model_quality_claim', 'experiment_success', 'gating',
  'staking')`. **VERIFIED.**
- `v7/test_price_capture.py:1-50` — the AST/import defence, and its own statement
  that *"Defence 1 is the real one. Defence 2 catches a caller who states their
  intent honestly, which is the easy case."* **VERIFIED.** This is the pattern
  §1.3 extends to salary and ownership.
- `v7/guards.py:5191` `assert_post_hoc_capture` and `:804`
  `assert_no_bankroll_import_in_selection`. **VERIFIED** (function definitions
  read).

---

## 1. The separation principle, as a concrete interface

This section is architecture, not external fact. It is the part of my scope I can
reason about rigorously and I have not hedged it.

### 1.1 The contract

Three engines, one direction (Rule 016). The **only** object that crosses from
the forecasting side to the DFS side is the **joint draw archive** defined in §2,
plus two small companions:

| Crossing forecast → DFS | Content |
|---|---|
| **Joint draw archive** | §2.2 schema. Component stats only. Never fantasy points. |
| **Identity map** | `gsis_id` → the DFS site's player key, built by the DFS layer from the site's file, resolved against nflverse `players.csv`. Lives on the DFS side. |
| **Availability state** | Per player: `ACTIVE / OUT / DOUBTFUL / QUESTIONABLE / UNKNOWN`, with its own `information_cutoff_utc`. A *forecast* input, exported so the DFS layer can display why a player is absent — never re-derived downstream. |

Nothing else crosses in that direction, and **nothing at all crosses back**.

### 1.2 The prohibited set, named field by field

A projection module may not read, import, or name any of these. Naming them
explicitly is the point — Rule 016 currently says "salary, ownership, leverage,
contest structure, implied team totals and any price" in prose, and prose does
not enforce.

**DFS-layer fields (forbidden as projection inputs):**
`salary`, `salary_change`, `site_position_eligibility`, `roster_slot`,
`projected_ownership`, `actual_ownership`, `leverage`, `duplication_count`,
`contest_id`, `field_size`, `entry_fee`, `payout_table`, `max_entries`,
`optimizer_used_count`, `lineup_exposure`, `contest_roi`.

**Market-layer fields (already forbidden by Rule 012; restated because they ship
inside the NFL data itself):**
`spread_line`, `total_line`, `away_moneyline`, `home_moneyline`,
`over_odds`, `under_odds`, `away_spread_odds`, `home_spread_odds`,
`vegas_wp`, `vegas_home_wp`, `vegas_wpa`, `vegas_home_wpa`, implied team total.

**This is not hypothetical for NFL.** I confirmed in this container that
`play_by_play_2024.csv`'s header carries `vegas_wpa` (col 98), `vegas_home_wpa`
(99), `vegas_wp` (102), `vegas_home_wp` (103) — **VERIFIED**, via
`curl -r 0-4000` on the release URL. `_GROUNDING.md:135-141` records
`spread_line` and `total_line` in the same file. The nflverse schedule file
carries the full historical market: `spread_line`, `total_line`,
`away_moneyline`, `home_moneyline`, `over_odds`, `under_odds`,
`away_spread_odds`, `home_spread_odds` — **VERIFIED**, I read the 46-column
header of `games.csv` (2,177,171 bytes, 7,548 rows).

So the NFL "neutral" data source ships the sportsbook inside it. Quarantine at
ingest — a drop list applied when the raw file is written to the lake, so the
columns are never present in any downstream frame — not a "we did not select
them" convention.

**Also forbidden, and it is not a field:** DFS usefulness as a *reason* to admit
a projection feature. `DFS_ARCHITECTURE_GAP_REPORT.md:526-551` (§7.4) states the
rule; I endorse it unchanged and note it is the channel a field-level check does
not close.

### 1.3 Enforcement, three layers, strongest first

1. **AST / import check.** No module in the projection formula set, and no gating
   module, may import the DFS module or the market module, or name their artifact
   paths or filename patterns (`*salar*`, `*ownership*`, `*contest*`, `*payout*`,
   `*odds*`). This is exactly `v7/test_price_capture.py`'s defence 1
   (**VERIFIED**), extended by one word — from `pricecapture` to the DFS set.
   **This is the real defence.** It fails closed and does not depend on anyone
   declaring intent.
2. **Input-set allowlist at the projection boundary.** The projection declares
   its complete input field set in a manifest; any field arriving that is not on
   the manifest **refuses** with a named error rather than being ignored. An
   allowlist, not a denylist — `assert_price_use_permitted`'s own docstring gives
   the reason (`v7/guards.py:5265-5268`, **VERIFIED**): *"a denylist falls open
   for every use nobody thought to forbid."* This is the "explicit input-set
   check" Rule 016 says is to be built.
3. **Named-use allowlist.** A `dfs_use_permitted` analogue of
   `assert_price_use_permitted`. Permitted: `lineup_construction`,
   `contest_evaluation`, `research_comparison`. Forbidden by name:
   `projection_input`, `feature_admission`, `model_promotion`,
   `experiment_success`, `gating`. Catches the honest caller. Weakest of the
   three and should be described that way, not as the guard.

### 1.4 The ordering check, which is what makes blindness provable

Salary and ownership arrive on a clock. So does a price. `test_price_capture.py`
makes post-hoc capture *mechanical*: every prediction row carries
`written_at_utc`, every observation carries `captured_at_utc`, and if the capture
precedes the write, the row is **REFUSED, not recorded with a caveat**
(**VERIFIED**, `v7/test_price_capture.py:36-45`).

Apply the identical rule to salary and ownership. A salary or ownership value may
be joined to a projection row only when `projection.written_at_utc <
observation.captured_at_utc`. Without this, "the projection did not see the
salary" is prose. With it, it is a check that can fail.

### 1.5 One thing that is *not* a violation, stated so it is not over-applied

The DFS layer legitimately reads the forecast. Reading is the whole point. What
is forbidden is the reverse edge and the write. A leverage score computed inside
the DFS layer from projections plus ownership is correct architecture; the same
number written back onto a projection row, or used to select which players get
projected, is the violation. The boundary is directional, not a wall.

---

## 2. What the DFS layer needs from the simulator

### 2.1 Why marginals are useless here, in NFL-specific terms

A lineup score is `S = Σ_j X_j` over the roster slots. Tournaments are decided by
the **upper tail of S**. Stored marginals give `E[S]` exactly and give nothing
about `Var(S)` or the shape of its tail, because those depend on
`Cov(X_j, X_k)` — which marginals do not contain. This is the same finding as
`DFS_ARCHITECTURE_GAP_REPORT.md:31-44`, and MLB's nine stored percentiles are the
concrete example of getting it wrong (`CLAUDE.md`, "nine stored percentiles
cannot support exact CRPS, log score, or tail calibration").

**NFL's version of this is mechanically stronger than baseball's, and that is
checkable from the schema rather than recalled.** I verified that
`play_by_play_2024.csv` carries `passer_player_id` (col 171),
`receiver_player_id` (174), `rusher_player_id` (177) and `td_player_id` (53) **on
the same play row** (**VERIFIED**, `curl -r 0-4000`). One event therefore credits
two players simultaneously and by construction: a touchdown pass increments the
passer's yards and passing TD and the receiver's yards and receiving TD from a
single draw. There is no configuration in which those two players' outcomes are
independent. Any storage layer that keeps them separately keeps something that
cannot be reassembled.

The negative side is equally structural: two running backs on one team share a
finite carry count in the same simulated game, and two receivers share a finite
target count. A marginal store cannot represent "these two cannot both have a big
game", and a lineup built from marginals will systematically overstate the
probability of the exact outcome that pays.

**Consequence, and it is the single highest-leverage decision in NFL-0:** store
full joint draws from the first simulation the system ever runs. Retrofitting is
not possible — the correlation is destroyed at write time, not degraded. This
costs nothing on day one and is unrecoverable afterwards.

### 2.2 The draw archive: what a row must carry

Two objects. An archive header, once per game, and a draw matrix.

**Header** (this is where MLB's M0-D lesson lands — `CLAUDE.md`: `SIM_FORMULA`
excluded the corpus, so substituting it left the fingerprint identical):

```
game_id, season, week, slate_id
engine_version, sim_formula_fingerprint
seed, seed_rule
n_sims
information_cutoff_utc          # nothing after this influenced any draw
input_manifest_hash             # content hash of EVERY consumed input file
cross_game_dependence           # see 2.3 — a required declared field
written_at_utc
```

**Draw matrix**, keyed `(sim_index, game_id, entity_id, entity_role)`:

- `sim_index` — int32, **shared across every entity in the game**. This is the
  correlation. Nothing else in the archive carries it.
- `entity_role` ∈ `skill | kicker | dst`, selecting which component vector
  applies.

*Skill component vector (20 integers):* `pass_att, pass_cmp, pass_yds, pass_td,
pass_int, pass_2pt, sacks_taken, rush_att, rush_yds, rush_td, rush_2pt, targets,
rec, rec_yds, rec_td, rec_2pt, fum_lost, longest_rush, longest_rec, first_downs`.

*Kicker vector (8):* `fg_att, fg_made, fg_made_0_39, fg_made_40_49, fg_made_50p,
xp_att, xp_made, fg_longest`.

*Team-defence vector (12):* `sacks, ints, fum_rec, def_td, st_td, safeties,
blocked_kicks, pts_allowed, yds_allowed, punt_ret_yds, kick_ret_yds, two_pt_ret`.

*Game-level vector (10), carrying the same `sim_index`:* `home_score,
away_score, home_plays, away_plays, home_pass_att, away_pass_att, home_td,
away_td, total_yds, overtime`.

**Three rules on the schema:**

- **Components, never fantasy points.** A points column bakes one site's scoring
  rule into the forecast artifact and makes it unable to answer a second site's
  question or survive a rules change. `DFS_ARCHITECTURE_GAP_REPORT.md:369-373`
  says this for MLB; it applies unchanged. A points column is legitimate only as
  a clearly labelled derived cache beside the store.
- **`longest_rush` / `longest_rec` are in the vector on purpose.** They are not
  DFS fields — they are prop markets, and they are not recoverable from totals.
  Omitting them is the kind of choice that is free today and blocking in a year.
- **No salary, no ownership, no price columns exist in this schema at all.** Not
  nullable, not reserved. Absent.

### 2.3 The cross-game alignment trap

Within a game, `sim_index` is meaningful and mandatory. **Across** games in a
slate it is meaningful only if the games were simulated jointly.

If games are independent by construction, then aligning game A's sim 7 with game
B's sim 7 is arbitrary and harmless, and a DFS lineup spanning both is correctly
scored. If a later version introduces *any* cross-game term — a league-wide
scoring-environment shock, a shared weather regime, a common officiating-crew
effect — then post-hoc pairing of independently drawn games becomes **silently
wrong**, and it will look fine, because the marginals will be perfect.

So `cross_game_dependence` is a **required** header field with values
`INDEPENDENT_BY_CONSTRUCTION` or `JOINT`, and the DFS layer **refuses** to
construct a multi-game lineup from an archive where the field is missing. This is
Rule 001 applied to a specific silent-success channel: absence must get a state,
not a default.

### 2.4 The write guard

`v7/runtotals.py:65` `assert_lossless` proves the round trip on every write
rather than asserting it in a comment (**REPO-RECORDED** via
`DFS_ARCHITECTURE_GAP_REPORT.md:418-421`; I did not open `runtotals.py`). The
joint archive needs the same: on every write, re-derive each field's marginal
histogram from the matrix, require equality with the source draws' histogram, and
require the row count to equal `n_sims × entities`. A transposed axis in a
five-million-element matrix produces plausible marginals and destroys every
correlation — this project's recurring defect class in a new costume.

### 2.5 Size — the arithmetic, DERIVED

**VERIFIED inputs, measured in this container this pass:**

| Quantity | Value | How |
|---|---|---|
| Regular-season games, 2026 | **272** | `games.csv`, `season=2026`, `game_type=REG` |
| Weeks | **18** | same file |
| Games per week | mean 15.11, median 15.5, range 13–16 | same file |
| Distinct gamedays, 2026 season | **57** (2026-09-09 → 2027-01-10) | same file |
| Skill players (QB/RB/WR/TE/FB) with >0 offensive snaps, per game, both teams | **mean 24.4**, median 24, range 20–29, n=272 games | `snap_counts_2024.csv`, `game_type=REG` |
| All offensive players with >0 offensive snaps per game | 37.0 | same |
| All players with any snaps per game | 93.4 | same |

**DERIVED — entities per game:** 24.4 skill + 2 kickers + 2 team-defence units =
**28.4**; design figure **30**, which covers the observed 29-skill maximum.

**DERIVED — integers per simulation per game:**
24.4 × 20 (skill) + 2 × 8 (K) + 2 × 12 (DST) + 10 (game-level)
= 488 + 16 + 24 + 10 = **538**. Design figure **540**.

**DERIVED — byte width:** count fields fit `int8`; yardage fields
(`pass_yds` up to ~600, `rec_yds`, `yds_allowed`) need `int16`. Roughly 6 of 20
skill fields are int16, giving a true mean near 1.3 bytes. **Use 2 bytes as the
conservative design figure.**

**DERIVED — archive size:**

| N sims/game | Per game | Per week (15.11 games) | Per season (272 games) |
|---|---|---|---|
| 10,000 | 5.40 M ints → **10.8 MB** | **163 MB** | **2.94 GB** |
| 20,000 (MLB's `card.py:87` production N) | 10.8 M ints → **21.6 MB** | **326 MB** | **5.88 GB** |

Uncompressed. The matrix is dominated by structural zeros — a wide receiver's
`pass_att` column is zero in every simulation, most players score no touchdown in
most simulations — so a columnar layout with a general compressor should reduce
this by roughly an order of magnitude. **That last factor is an estimate, not a
measurement**, and should be measured on the first real slate rather than assumed.

**DERIVED — the comparison that settles the "is this too big" question:** MLB
would need 2,430 games × 300 ints × 20,000 sims = 14.6 billion integers per
season (300 from `DFS_ARCHITECTURE_GAP_REPORT.md:394-396`). NFL needs
272 × 540 × 20,000 = 2.94 billion — **about one fifth of MLB's**. Storage is not
a reason to skip this, and it was never the reason MLB skipped it either
(`DFS_ARCHITECTURE_GAP_REPORT.md:406-407` says so directly).

---

## 3. Contest simulation: the structure, and what it requires

**Every empirical specific in this section is UNVERIFIED-RECALL or unavailable.**
I state the structure, which is reasoning, and name the inputs, which are outbox
items. I give no salary, no rake, no payout curve, no field size, no roster rule,
no ownership figure — not even as an illustration, because illustrations in this
repository have a history of becoming constants.

### 3.1 The five components and their required inputs

| Component | What it is | Required input | Obtainable here? |
|---|---|---|---|
| **Contest definition** | Field size, entry fee, max entries per user, payout table, roster slots and positional eligibility, salary cap | The site's own published contest data | **No** — outbox |
| **Salary table** | Per player, per slate, per site | The site's slate file | **No** — outbox |
| **Ownership forecast** | P(a random field entry holds player *p*) | Historical contest results + a model | **No** — outbox |
| **Opponent field model** | F simulated opponent lineups | The above, plus a *construction* model | **No** |
| **Payout evaluation** | Rank → prize, given your score and F opponents | The payout table | **No** |

Note what this table says: **four of five components are gated on external data
that this container cannot reach**, and the fifth is trivial once the payout
table exists. The DFS layer is not primarily a modelling problem for this agent.
It is a data-acquisition problem for the networked agent, wrapped around the
joint archive from §2, which *is* this agent's problem.

### 3.2 Four structural points that do not depend on any external number

These are reasoning, and I am willing to be wrong about them in public.

**(a) Ownership marginals do not determine the field, and assuming they do biases
in the flattering direction.** Two fields with byte-identical per-player
ownership can have completely different duplication and correlation structure,
because entrants do not choose players independently — they choose *lineups*, and
lineups contain deliberate stacks. Sampling opponent lineups independently from
ownership marginals under-represents stacks. Under-representing stacks understates
how many opponents share your outcome when your stack hits, which **overstates
your rank when you win**. The error runs in the direction that makes your own
lineup look better. That is the direction an error is least likely to be noticed.

**(b) Duplication is a property of the field's construction process, not of
ownership.** It cannot be computed from marginal ownership at all. Any duplication
number derived from marginals alone is a different quantity wearing the same name.

**(c) Leverage is a ranking statistic of the DFS layer and must never be written
back.** It is a function of (your holding, the field's holding, the payout curve).
It says nothing about a player's outcome distribution. Rule 016 plus §1.2 above
plus `DFS_ARCHITECTURE_GAP_REPORT.md` §7.4 all close this from different sides,
which is appropriate for a channel this attractive.

**(d) The payout curve chooses the objective function, and the choice changes the
answer.** Under a flat or near-flat payout the objective is approximately
`P(S > threshold)` for one threshold. Under a top-heavy payout it is
approximately `E[payout(rank(S))]`, which is dominated by the far right tail. The
optimal lineup differs between the two. This is provable arithmetic on constructed
cases — no external data needed to demonstrate it, and it should be demonstrated
that way rather than argued.

### 3.3 How each piece must be tested — and it is two different regimes

`DFS_ARCHITECTURE_GAP_REPORT.md` §7.2 and §7.3 make the distinction and I adopt
it. Restating only the consequence for NFL:

- **Solver, duplication arithmetic, payout evaluation, portfolio construction:**
  deterministic. They make no claim about the world. Test against constructed
  cases with known answers. They are *correct or incorrect*, never *calibrated or
  miscalibrated*, and grading them against outcomes is a category error.
- **Ownership projection and field simulation:** genuine forecasts, about *human
  entrants*, not football. They get their own registered unit, their own floor,
  and their own gate. They may **not** borrow the football forecast's ledger.
  They are also adversarial and non-stationary in a way football is not — a field
  reacts to published projections — so a calibration established on one season's
  field is not obviously valid on the next.

**One NFL-specific addition to that.** NFL runs one slate per week, not one per
night. An ownership model therefore accumulates evidence at roughly one twelfth
of a baseball ownership model's rate, against a field that changes across a
season. The sample-size problem in §4 applies to the ownership forecast too, and
harder.

---

## 4. The market layer — kept separate, gated identically, and the blunt answer

### 4.1 The rules, unchanged

Per `CLAUDE.md` rule 10 and `v7/board_config.json` (**VERIFIED**, read this pass):

- **Hard Rock Bet only.** `guards.assert_only_hard_rock` (`v7/guards.py:646`)
  refuses any other book and refuses an empty price list.
- **Combined-leg wagers of every kind are prohibited, including in discussion.**
  `guards.assert_no_parlay` (`v7/guards.py:707-720`) refuses on a six-term
  substring list covering the ordinary names for them. This document proposes
  none, names none, and prices none — an NFL layer inherits the same prohibition
  with the same guard, and the guard's substring list should be carried over
  verbatim rather than re-derived.
- **De-vig before comparing anything.**
- **No tiers.** One continuous ordered list.
- **An empty card is a valid result**, and no threshold may be loosened to
  manufacture a play (`guards.assert_no_threshold_relaxation`,
  `v7/guards.py:781`).
- **Two-stage bar** (`board_config.json:259-264`): calibration is the **gate**,
  margin over Hard Rock is the **trigger**, `gate_min = 300` graded predictions
  rising to `gate_min_low_probability = 500` below 0.20 implied,
  `trigger_min = 300` graded *resolved bets* rising to 500. Ordering is not
  optional: a margin computation on a market that has not passed the calibration
  gate must **refuse to run**, not run and be labelled provisional.
- **Breadth** (`board_config.json:282-283`): `min_distinct_dates = 10`,
  `min_distinct_player_games = 50`, and *unmeasured is refusal*.

An NFL market layer inherits all of this literally. Nothing about NFL justifies a
different floor, and if anyone later proposes one on the grounds that NFL is
slower, that is a **loosening** and an escalation, not a configuration change.

### 4.2 How fast the calibration GATE clears — DERIVED

Supply, from §2.5's VERIFIED table: 15.11 games/week × 24.4 skill players/game =
**369 skill player-games per week**; 6,637 per season.

- **Row floor.** The gate counts graded *predictions* — rows, per the
  `gate_floor_unit: "rows"` ruling — and needs no price at all. Even one market
  with one line per skill player-game gives 369 rows in week 1, clearing 300
  immediately. The 500-row low-probability floor clears in week 2
  (500 / 369 = 1.36).
- **Player-game breadth.** 50 distinct player-games: cleared in week 1.
- **Date breadth binds.** Gamedays per week, **VERIFIED** from the 2026 schedule:
  week 1 = 4, weeks 2–6 = 3 each. Cumulative: 4, 7, **10** at the end of week 3.

**DERIVED: the calibration gate on a high-volume NFL player market is reachable
at the end of week 3 — about 21 days into the season.** That is fast, and it is
the good news in this document.

**It has one precondition and the precondition is absolute.**
`board_config.json` `graded_prediction_means` requires that *"Predicted
probabilities must come from stored draws or a dense CDF, never from
percentiles."* If NFL-0 ships without the §2 archive, the clock in the paragraph
above **does not start at all** — not slowly, not partially. Every prediction
made before the archive exists is ineligible for the gate forever. This is the
same failure that left MLB's 251-game development set and its 2026-08-30 ledger
unable to satisfy the requirement (`CLAUDE.md`, "satisfied for game totals from
2026-08-31 forward, and unmet for the 251-game development set").

### 4.3 How fast the margin TRIGGER clears — DERIVED, and the answer is bad

The trigger counts **graded resolved bets** per market: terminal settlement only,
each requiring a Hard Rock price, each on a market that has already passed the
gate. It cannot begin before the end of week 3, leaving **15 weeks** (4–18) in a
season.

**Requirement for a single-season clear:** 300 / 15 = **20 staked plays per week
in one market**.

Is 20/week plausible? The only empirical anchor available is MLB's, and I quote
it as what the config asserts rather than as a measurement, per `CLAUDE.md`'s
explicit caution that the figure cannot be reconstructed from the ledger file
alone:

> `retroactive_note`: *"As of 2026-08-30 the entire graded ledger since epoch
> 2026-08-27 is 25 plays across all markets combined."* (**VERIFIED** that
> `board_config.json` says this.)

**DERIVED, and every step is visible so it can be attacked:**

1. 25 plays over 4 calendar days at roughly 13 MLB games/day → 25 / 52 ≈ **0.48
   plays per game, across all markets combined**.
2. NFL season supply: 272 games → 272 × 0.48 ≈ **131 plays per season across all
   markets**.
3. Across 12+ registered markets → roughly **11 plays per market per season**.
4. 300 / 11 ≈ **27 seasons** for one market to reach the trigger floor.
5. Generous variant: assume NFL props yield **5×** MLB's per-game qualifying rate
   (more markets per player, larger rosters). Then ~655 plays/season all markets,
   ~55 per market → 300 / 55 ≈ **5.5 seasons**.

**The blunt answer, which is what was asked for: on every input I can construct,
no single NFL market reaches the 300-resolved-bet trigger in under roughly five
seasons, and the central estimate is over twenty.** The step-1 input is a
four-day MLB snapshot and is weak; it is also the only empirical anchor that
exists, and replacing it with an assumption would not make the conclusion
stronger, only less visible. Even a 10× error in step 1 leaves the answer at
"multiple seasons".

### 4.4 The season-boundary interaction, which may make it worse than slow

`board_config.json` `season_boundary` is `CARRY_UNLESS_STRUCTURAL_CHANGE`
(**VERIFIED**): graded predictions pool across a season boundary, and pooling is
refused only when a **league-wide structural rule change** is declared between the
pooled seasons, and then only for affected markets. MLB's declared examples are
ball specification, pitch clock, strike zone, expanded rosters, mound distance.

The NFL analogues are obvious: kickoff format, overtime format, roster size,
extra-point distance, injured-reserve return rules, reviewability changes.

**UNVERIFIED-RECALL: the NFL changes at least one rule of this class in most
offseasons.** I cannot check this and it is an outbox item (§6, item 8). But the
conditional is worth stating now, because §4.3's answer depends on it:

> If that recall is correct, a scoring-environment-sensitive NFL market resets its
> pooled evidence roughly annually, while needing 5–27 seasons to clear the
> trigger. The trigger would then be **structurally unreachable**, not merely
> slow.

That is not a reason to loosen the floor. It is a reason to decide *now*, under
Rule 006a, which state the NFL market layer is registered in. Rule 006a requires
the registry to say, at all times, `DEFERRED` (accumulating, with the count so far
and the count required both stated), `BLOCKED` (evidence cannot accumulate, and
what is missing), or `NOT_APPLICABLE`.

**My recommendation: register the NFL margin trigger as `DEFERRED` with the
required count stated as "≥5 seasons at the best plausible rate", and escalate to
`BLOCKED` if and only if the offseason-rule-change recall is confirmed.**
`DEFERRED` implies the count eventually arrives; that implication should not be
made until §6 item 8 comes back.

### 4.5 What this means for how NFL work should be sequenced

The gate is 21 days away. The trigger is years away, possibly unreachable. Those
two facts are not a disappointment to manage; they are a sequencing instruction.

**All NFL market-layer work should target the gate and treat the trigger as out
of reach on any planning horizon.** Concretely: build the calibration ledger,
build the de-vig, build the price-capture-after-prediction ordering check, and
build the refusal that stops a margin computation running on an ungated market.
Do not build a staking layer, an exposure model, or a bankroll module — nothing
will reach them, and building them creates the appearance of a system waiting on
a threshold rather than one that has correctly concluded it should not bet.

Rule 006a's sentence applies exactly: *"a governed system that has promoted
nothing is not thereby working"* — and its converse, which is the one that matters
here: a system that has correctly refused for five seasons is not thereby broken.

---

## 5. Benchmarks

### 5.1 The principle, stated first because it drives the list

A simple public benchmark that is actually obtainable is worth more than a
sophisticated one that is not. An unobtainable benchmark produces a number
somebody recalls, and this project has a written record of what that costs
(`CLAUDE.md`, "Claims you may encounter that are FALSE").

### 5.2 Obtainable in this container today — measured this pass

I measured two, because the brief asked which are obtainable and the honest way
to answer is to obtain them.

**Benchmark A — the trivial pre-game baseline.** Predict a player's week-*w*
fantasy points by the mean of their own prior weeks that season, requiring ≥4
prior weeks. No opponent, no injury, no market, no model.

*Source:* `ffopportunity` `ep_weekly_2024.csv` (5,380,748 bytes, 6,006 rows),
reachable at
`github.com/ffverse/ffopportunity/releases/download/latest-data/ep_weekly_2024.csv`
— **VERIFIED**, HTTP 200 in this container. 2025 also reachable (5,426,028
bytes); 2026 returns 404, as expected on 2026-09-06.

| Position | n | r | r² | MAE | sd_pred/sd_actual |
|---|---|---|---|---|---|
| QB | 425 | 0.3928 | 0.154 | 6.487 | 0.588 |
| RB | 968 | 0.6123 | 0.375 | 4.937 | 0.712 |
| WR | 1,448 | 0.5080 | 0.258 | 5.139 | 0.600 |
| TE | 718 | 0.5297 | 0.281 | 4.070 | 0.549 |
| **All** | **3,576** | **0.5907** | **0.349** | **5.005** | **0.666** |

**VERIFIED** — computed in this container, 2024 season.

**Benchmark B — the oracle-opportunity ceiling.** The same file's
`total_fantasy_points_exp` against realised `total_fantasy_points`. This column is
an expected-points model *conditioned on the game's realised opportunity* —
realised attempts, targets and air yards are inputs to it.

| Population | n | r | r² |
|---|---|---|---|
| All, pooled | 6,005 | **0.8419** | 0.709 |
| QB | 697 | 0.8014 | 0.642 |
| RB | 1,477 | 0.8520 | 0.726 |
| WR | 2,233 | 0.8044 | 0.647 |
| TE | 1,139 | 0.8334 | 0.694 |
| All, **within-player demeaned** (players with ≥8 weeks) | 5,177 | **0.6853** | 0.470 |

**VERIFIED** — computed in this container, 2024 season.

**This is a ceiling, not a peer, and using it as a peer would be a leakage
error.** It has seen the game. It is the direct NFL analogue of MLB's oracle
validation, which fed the simulator the actual boxscore batting orders and which
`CLAUDE.md` insists must not be quoted as live performance. Same discipline here.

**What the pair actually tells you, and it is the most useful architectural
statement in this document:** once weekly opportunity is known, r ≈ 0.84 pooled
and r ≈ 0.69 within-player. **The hard part of NFL player forecasting is
projecting opportunity — attempts, targets, air yards, snap share — not converting
opportunity into points.** That is consistent with `_GROUNDING.md:74-86` making
route participation and targets-per-route-run computable from `pbp_participation`,
and it says where the modelling effort belongs.

**A warning I want on the record, because it is the exact error this project has
already paid for twice.** These r values are **not comparable to MLB's
r = 0.1101**. Different unit (player-week vs game total), different population,
and the pooled versions include between-player variance — a WR1 against a WR4 —
which the MLB game-total figure does not contain. Anyone who reports "NFL gets
0.59 where MLB got 0.11" has produced a false finding. The within-player demeaned
column exists in the table above specifically so that the honest comparison is
available and the dishonest one is visibly labelled. Constitution Rule 005 applies:
r, SD ratio and calibration slope are algebraically one fact and none may be
quoted alone.

**Benchmark C — other trivial baselines, all obtainable, none yet measured.**
Positional league average; rolling-N-game mean; prior-season per-game rate;
opponent-adjusted positional average. All computable from nflverse in this
container. Worth building as a *suite*, because a single naive baseline is easy to
beat by accident.

**Benchmark D — the historical market, with a large caveat.** `games.csv` carries
`spread_line`, `total_line`, both moneylines and both totals prices for every
game back through the file's span (**VERIFIED**, 46-column header, 7,548 rows).
This is a complete free historical market benchmark for game totals and margins.

**Three things must be true before it is used.** (i) It is **not** Hard Rock Bet
and carries no named book; `guards.assert_only_hard_rock` would refuse it in any
pricing path, correctly. (ii) Using it as a *forecasting comparison* is a
different use from pricing a play, and that use must be **explicitly declared and
allowed**, in the shape of `assert_price_use_permitted`'s allowlist — not assumed
because it seemed harmless. (iii) The same columns must be quarantined from every
projection input at ingest (§1.2). It is simultaneously the best free benchmark
available and the most likely leakage vector in the whole NFL data stack, and both
facts are about the same eight columns.

### 5.3 Not obtainable here — needs the networked agent

Public projection benchmarks (consensus rankings, commercial projection systems,
site projections), DFS salaries, contest structures, payout tables, realised
ownership, contest results, and any Hard Rock Bet price, live or historical.
**UNVERIFIED-RECALL** that several such benchmarks publish historical accuracy;
that is item 5 in §6, not a claim.

`v7/INDUSTRY_RESEARCH.md` and `v7/INDUSTRY_PRACTICE.md` are **REPO-RECORDED**
prior research with source URLs, compiled 2026-08-28/29 from an environment with
network. They are a good starting point for the networked agent and are **not**
re-verified here. `v7/INDUSTRY_RESEARCH.md:106-108` records a vendor describing a
contest-sim layer — lineups simulated against a field inside a payout structure,
sorted by simulated ROI, with duplicates discounted — which is structurally the
same architecture as §3 and is worth reading as prior art, not as a specification.

---

## 6. Assignment list for the networked agent

Per `CLAUDE.md`: *"never mark a task blocked on something outside this repository
without first writing the request into `docs/AGENT_OUTBOX.md`"* and DEC-029 *"not
blocked — assigned"*. **This section is the source text for those outbox entries.
I have not written to `docs/AGENT_OUTBOX.md`; my brief is one file.** Whoever
consolidates this pass should transcribe items 1–9 there.

Ordered by what unblocks the most downstream work.

**1. Does any DFS site publish historical salaries, and under what terms?**
*Why it matters:* without a historical salary series, the DFS layer cannot be
backtested at all, and every §3 component stays unbuilt. This is the single
highest-value item on the list. *Wanted:* which sites publish, how far back, at
what granularity (per slate? per contest?), and the licence. *Do not paste
salaries into a document as examples* — confirm availability first.

**2. Contest structure, exactly, for one named contest type per site.**
*Why:* §3's payout evaluation and roster solver cannot be specified without roster
slots, positional eligibility, salary cap, field size, max entries per user, and
the full payout table. *Wanted:* the site's own published page for one specific
contest, quoted, with a URL and a retrieval date. **Every one of these is
currently UNVERIFIED-RECALL in this document and I have deliberately written none
of them down.**

**3. Historical contest results with realised ownership.**
*Why:* the opponent-field model in §3.2(a) is the component most likely to be
wrong in the flattering direction, and it cannot be validated without realised
ownership *and* realised lineup construction — ownership marginals alone are
insufficient, which is the whole point of that subsection. *Wanted:* whether
lineup-level results are published or purchasable, and whether they include the
full lineup or only the top of the field.

**4. Hard Rock Bet NFL market coverage.**
*Why:* §4.3's trigger arithmetic assumes markets exist to bet. *Wanted:* which NFL
player markets Hard Rock actually offers, when lines post relative to kickoff, and
whether a price can be captured programmatically with provenance. Note
`v7/oddsclient.py`'s discipline — refuse prices arriving without provenance, write
every raw response to disk before parsing — is worth preserving whatever the
transport.

**5. Public NFL projection accuracy benchmarks.**
*Why:* §5.3. *Wanted:* which providers publish historical accuracy, on what
metric, over what population, and whether the underlying per-player predictions
(not just a summary statistic) are retrievable. A published summary r is nearly
useless; retrievable predictions are a real benchmark. **UNVERIFIED-RECALL that
any of them publish this.**

**6. Confirm the `ffopportunity` `_exp` semantics.**
*Why:* §5.2's entire framing of Benchmark B as an oracle ceiling rests on my
reading that `total_fantasy_points_exp` conditions on realised opportunity. The
r ≈ 0.84 and the presence of realised `pass_attempt` beside `pass_completions_exp`
in the same row strongly support it, but I inferred it from the schema rather than
reading the package's documentation. *Wanted:* the package's own statement of what
`_exp` conditions on. **If I am wrong here, §5.2's central conclusion changes.**

**7. Whether nflverse's `games.csv` market columns have a named source book, and
whether they are opening or closing.**
*Why:* §5.2 Benchmark D. "The market" is not one number; opening and closing lines
are different benchmarks and comparing to the wrong one silently changes the
result. *Wanted:* the documented provenance of `spread_line`, `total_line`,
`over_odds`, `under_odds`.

**8. NFL structural rule changes by offseason, for the last ~10 seasons.**
*Why:* §4.4. If scoring-environment-relevant rules change most offseasons, the
margin trigger moves from `DEFERRED` to `BLOCKED`, which is a governance state
change and not a modelling detail. *Wanted:* a dated list from a primary source
(league rulebook change summaries), against MLB's declared category —
league-wide, uniform, shifts baselines for everyone at once. Roster churn, coaching
changes and a new calendar year do **not** qualify.

**9. Whether weekly injury-report vintages are obtainable from any live feed
starting immediately.**
*Why:* `_GROUNDING.md:114-133` establishes that the historical archive holds one
row per player-week stamped near the Friday report, so Wednesday's status is
overwritten and the cascade cannot be reconstructed. Today is 2026-09-06 and the
season starts **2026-09-09** (**VERIFIED** from the schedule). *Every week not
captured from week 1 onward is permanently unavailable.* This is the only item on
this list with a hard deadline, and the deadline is in three days.

---

## 7. What I did not do, and where I may be wrong

- **I ran no simulator and wrote no code that survives this pass.** The
  measurements in §2.5 and §5.2 came from throwaway scripts in the scratchpad,
  which `_GROUNDING.md:182-188` explicitly permits as evidence. Nothing was
  committed to `nfl/`.
- **§2.2's field lists are a proposal, not a settled schema.** I chose 20/8/12/10
  fields by reasoning about which markets and which scoring components exist. A
  worker with the actual market list should revise them. The *count* feeding
  §2.5's arithmetic is robust to reasonable changes — doubling the field count
  doubles a 2.94 GB figure, which changes no conclusion.
- **§4.3's step 1 is weak and I have said so twice.** A four-day MLB snapshot is
  the only anchor available. If the networked agent can produce a longer MLB play
  rate, redo the arithmetic; I would rather the number moved than that it was
  quietly defended.
- **§4.4 rests on an UNVERIFIED-RECALL** about NFL offseason rule changes and is
  written as a conditional for that reason. It is item 8.
- **§5.2 Benchmark B's oracle framing rests on a schema inference**, not
  documentation. It is item 6, and it is the claim in this document I would most
  like checked.
- **I did not verify anything about any commercial system, DFS site or sportsbook**
  and have stated no number about any of them. That is not a gap in the research;
  it is the correct output of a container with no egress, and filling it from
  recall is the specific failure this pass was warned about.
