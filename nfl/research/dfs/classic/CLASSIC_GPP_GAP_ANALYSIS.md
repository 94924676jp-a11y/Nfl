# DK Classic GPP portfolio research — gap analysis against this repository

Research input: `dk-classic-gpp-portfolio-research.md`, owner-delivered
2026-09-20. Downstream DFS only. No ownership, lineup-construction, contest,
payout or sportsbook quantity from it may reach the football model.

---

## 0. The finding that reorders everything below

**The dossier's "internal correlation measurements" are the external packet
this repository already adjudicated and partly rejected.**

`[file:253]` and `[file:254]` are cited throughout as internal evidence. Their
numbers are the external packet's numbers, and
`nfl/research/dfs/fullslate/reproduce_external_panel.py` exists specifically to
ask whether that packet reconstructs from its stated method. It does not, in
places that matter:

| quantity | dossier (as "internal") | our canonical panel (DFS-FS1) |
|---|---|---|
| QB·PC1 Pearson | 0.37–0.42 realized, 0.27 ex-ante | **+0.207** [+0.103,+0.304] 2024 · **+0.170** [+0.070,+0.264] 2025 |
| PC1·PC2 | "near zero or slightly positive" | −0.014 / +0.072, **interval spans zero both seasons** |
| RUSH1·RUSH2 | −0.10 to −0.23 | **−0.118 / −0.179** — agrees |
| opposing QB (bring-back basis) | positive, "STRONG_EMPIRICAL_SUPPORT" | **+0.053** [−0.097,+0.190] · **+0.086** [−0.046,+0.211] |
| cross-team pairs overall | bring-backs ~7% p95 lift | **1 of 16** Pearson intervals excludes zero; **0 of 16** tail-lift intervals exclude 1.0 |
| QB+3 marginal value | "diminishing" | **contradicted** — the QB+2→QB+3 p95 increment exceeded QB+1→QB+2 in both seasons |

The dossier's numbers carry no intervals. Ours do, and they are
game-clustered, because the two team-games of one game share its scoring
environment and are not two independent draws.

**This does not make the dossier wrong.** It makes it a second reading of a
source we have already measured against, presented as independent
corroboration. Treating it as independent would be double-counting one packet.
Every classification below is therefore made against **DFS-FS1**, not against
the dossier's citations.

A second, smaller point: `DFS-H2` measured that realized-role labelling
inflates DFS correlations by **+0.10 to +0.28**. The dossier quotes realized
and ex-ante figures side by side without saying which drives its
recommendations. Where it says "ρ ≈ 0.37–0.42 realized; 0.27–0.27 ex-ante",
only the second number is available before lock.

---

## 1. Repo gap analysis

Classification per the owner's vocabulary. Evidence is a path, not a
recollection.

### Football worlds and scoring

| Concept | State | Evidence |
|---|---|---|
| Football simulated worlds (single game) | `IMPLEMENTED_BUT_NOT_VALIDATED` | 8,000-world sealed DET@BUF board exists; no player-level right-tail calibration evidence (roadmap A8) |
| Football simulated worlds (full slate, joint) | **`MISSING`** | Roadmap **A7**, the gating item. No path builds ~26 games into one joint object |
| DK scoring adapter | `IMPLEMENTED_AND_TESTED` | `nfl/dfs/scoring/draftkings.py`, `VERIFIED_AGAINST_ENGINE` |
| FD scoring adapter | `IMPLEMENTED_BUT_NOT_VALIDATED` | `fanduel.py`, `VERIFIED_RULE_VALUE_RELAYED_SOURCE` |
| Shared scoring interface | `MISSING` | The two adapters do not share a key schema; a caller written against one raises `KeyError` on the other |
| **DST scoring / distribution** | **`MISSING`** | `statline.NOT_SIMULATED`: "the engine produces no team-defence outputs at all". Not a coverage gap — there is no layer |
| Kicker scoring | `IMPLEMENTED_AND_TESTED` | `score_kicker`, distance-bucketed, both adapters |

### Stacking and correlation concepts

| Concept | State | Evidence |
|---|---|---|
| QB+1 stacking | `RESEARCH_ONLY` | FS1 measures QB·PC1 and QB·PC2 dependence; **no lineup construct exists anywhere in the repo** |
| QB+2 stacking | `RESEARCH_ONLY` | as above; p95 inflation measured in the reproduction, not implemented |
| Naked QB handling | `RESEARCH_ONLY` | no stack representation exists, so "naked" is not a case the code can distinguish |
| Bring-backs | `RESEARCH_ONLY` **and the evidence is weaker than the dossier states** | FS1 §3: cross-team dependence not distinguishable from zero |
| Double stacks (WR/TE) | `RESEARCH_ONLY` | FS1: PC1·PC2 spans zero both seasons — a QB-less two-receiver structure has no same-team dependence support |
| Game stacks | `RESEARCH_ONLY` | stack-sum p95 inflation measured; no game-stack object |
| Mini-correlations | `RESEARCH_ONLY` | pair panel exists; no consumer |
| **QB vs opposing DST** | **`NOT_APPLICABLE` today** | FS1 returns `FS1_DST_SCORING_ABSENT` for **every** DST pair. The dossier's one `HARD_CONSTRAINT` rests on a quantity this engine cannot produce |
| RB + DST | `NOT_APPLICABLE` today | same code |
| Same-team RB penalties | `RESEARCH_ONLY` | RUSH1·RUSH2 negative and stable across both seasons — the best-supported negative structure we hold |
| Empirical world correlation readout | `IMPLEMENTED_BUT_NOT_VALIDATED` | `nfl/dfs/showdown/correlation.py` — **and it refuses to interpret its own zeros**, see §0b below |

### Lineup, ownership, contest, portfolio

| Concept | State | Evidence |
|---|---|---|
| FLEX positional treatment | `MISSING` | `site_rules.SITES` holds `DRAFTKINGS_SHOWDOWN` and `FANDUEL_SINGLE_GAME`. **No Classic entry at all** — no cap, no roster slots, no FLEX rule |
| Salary-left handling | `PARTIALLY_IMPLEMENTED` | `showdown/candidates.salary_relief_dependence` measures feasibility dependence on the cheapest player. Explicitly sets **no threshold** |
| Ownership modeling | `MISSING` | No ownership data of any kind. (Note: `nfl/production/ownership_audit.py` and `nfl/research/own1..own9` are **not** DFS ownership — see §0c) |
| Duplication modeling | `MISSING` | |
| Field generation | `MISSING` | |
| Contest simulation | `MISSING` | |
| Payout splitting | `MISSING` | |
| Top-X / first-place probabilities | `PARTIALLY_IMPLEMENTED` | `showdown/captain_metrics.p_top1` is P(highest raw DK scorer **in the game**) — not a contest finish probability, and the module says so |
| Lineup overlap | `MISSING` | |
| Player exposure | `IMPLEMENTED_AND_TESTED` | `production/dfs/portfolio_guard.audit/authorize`, `test_dfs_portfolio_guard`. It is an **audit**, deliberately not an optimizer constraint |
| Game exposure | `MISSING` | |
| Stack exposure | `MISSING` | |
| Portfolio covariance | `MISSING` | |
| Scenario diversification | `PARTIALLY_IMPLEMENTED` | `showdown/scenarios.py` buckets worlds — and declares four of six requested buckets `NOT_AVAILABLE` because the board emits no score or margin |
| World-based candidate generation | `PARTIALLY_IMPLEMENTED` | `showdown/optimal_worlds.py` solves the exact optimal lineup **per world** — the right primitive, Showdown-shaped |
| Stochastic / seeded randomness | `IMPLEMENTED_AND_TESTED` | seeds throughout; `optimal_worlds` breaks ties deterministically **and reports the tie rate** |
| Reproducibility | `IMPLEMENTED_AND_TESTED` | execution identity, code identity, content digests, vintage selection under a declared clock |
| Portfolio auditability | `IMPLEMENTED_AND_TESTED` | `portfolio_guard` + `showdown/universe_contract.py` (four declared universes) + `showdown/portfolio_report.py` |

**Count: 14 `MISSING`, 6 `PARTIALLY_IMPLEMENTED`, 8 `RESEARCH_ONLY`,
5 `IMPLEMENTED_AND_TESTED`, 3 `IMPLEMENTED_BUT_NOT_VALIDATED`,
2 `NOT_APPLICABLE`.**

### 0b. The constraint that governs the whole architecture

`nfl/dfs/showdown/correlation.py` states it, quoting the draw manifest:

> `across_rows: INDEPENDENT_STREAMS_COLUMN_ALIGNED` — "Rows are seeded
> independently, so a CROSS-ROW correlation read off the same axis measures
> the generator's lack of coupling, not a football quantity."

**Every stacking concept in the dossier is a statement about joint behaviour.**
If player rows are seeded independently, a world-based optimizer built on these
draws cannot express QB+WR correlation, and any stack preference that emerged
from it would be an artifact of whatever residual team-level coupling leaks
through `shared_pass` and `game_coupling` — not football.

That is worse than a mean-based optimizer, because it would *look* like
simulation-emergent evidence. **DFS-FS2 is the test for this and it is
`BLOCKED` on A7.** No stack rule may be validated against our own worlds until
FS2 can run.

### 0c. A terminology collision worth naming before it causes a defect

Three unrelated things in this repo are called "ownership":

- `nfl/production/ownership_audit.py` — a **code**-ownership governance audit.
- `nfl/research/own1…own9` — **rushing** ownership: which player owns a carry.
- DFS ownership — what fraction of the field rosters a player. **Absent.**

A new module named `ownership.py` under `nfl/dfs/` would be the third meaning
in a tree that already holds two. Name it `field_ownership` and say why.

---

## 2. Implementation map — what the target pipeline would call today

```
football simulated worlds   A7 MISSING (single-game only, and rows seeded
                            independently — see §0b)
  ↓
DK scoring                  draftkings.score EXISTS, certified
                            DST MISSING ENTIRELY
  ↓
candidate lineup generation site_rules has NO Classic contract
                            no Classic solver of any kind
                            optimal_worlds.py is the right primitive, wrong shape
  ↓
ownership / field sim       MISSING, no data
  ↓
contest payout simulation   MISSING
  ↓
lineup utility              MISSING
  ↓
portfolio selection         MISSING
  ↓
exposure / overlap audit    portfolio_guard EXISTS and is the one layer that
                            is genuinely ready
```

Seven of eight stages are absent or blocked. The one that exists at the end is
the audit, which was deliberately built before any optimizer.

---

## 3. Proposed hard / soft / emergent rule matrix

Each row carries **what we hold**, not what the dossier asserts.

| Rule | Proposed type | Basis in our evidence |
|---|---|---|
| DK Classic roster legality (slots, cap, min teams) | `HARD_CONSTRAINT` | Site contract. **Not yet held** — OUT-025 |
| QB vs opposing DST forbidden | `RESEARCH_REQUIRED`, **not** hard | Dossier's only hard rule; FS1 returns `FS1_DST_SCORING_ABSENT` for every DST pair. We cannot score a DST, so we can neither measure nor enforce it |
| At least one QB + 1 pass catcher | **`RESEARCH_REQUIRED`** — see §4 | The dossier contradicts itself here |
| QB + 2 pass catchers | `SOFT_PREFERENCE` | QB·PC2 +0.250/+0.174, excludes zero both seasons |
| QB + 3 pass catchers | `SIMULATION_EMERGENT` | Our reproduction contradicts "diminishing": QB+2→QB+3 increment exceeded QB+1→QB+2 both seasons |
| Naked QB | `SIMULATION_EMERGENT` | Requires a QB-rush share feature; the engine has one, but no stack representation exists to express "naked" |
| Bring-back | `SIMULATION_EMERGENT`, **downgraded from the dossier's soft preference** | 0 of 16 cross-team tail-lift intervals exclude 1.0. Not an evidenced basis for a preference |
| WR1+WR2 double stack (with QB) | `SOFT_PREFERENCE` | Stack-sum p95 inflation is positive **with** the QB |
| WR1+WR2 without QB | `SIMULATION_EMERGENT` | PC1·PC2 spans zero both seasons |
| Same-team RB1+RB2 | `SOFT_PREFERENCE` (penalty) | RUSH1·RUSH2 −0.118/−0.179, excludes zero both seasons — our best-supported negative |
| RB + own DST | `NOT_APPLICABLE` today | No DST layer |
| RB vs opposing RB ban | `RESEARCH_REQUIRED` | Dossier itself calls it folk |
| WR in FLEX | `SOFT_PREFERENCE` | External only. No internal measurement |
| Salary left ≤ $800 | `RESEARCH_REQUIRED` | A fitted constant with no derivation is a bug in this project. `salary_relief_dependence` deliberately sets no threshold |
| Game exposure 2–4 core games | `PORTFOLIO_CONTROL` | Allocation policy, not a football claim |
| Player / stack exposure caps | `PORTFOLIO_CONTROL` | `portfolio_guard` already enforces confidence-tag caps |
| Overlap / diversity metrics | `PORTFOLIO_CONTROL` | |
| Duplication-aware utility | `PORTFOLIO_CONTROL` | Needs a field model first |

**Note the shape of this matrix against the dossier's.** The dossier proposes
three hard constraints. Two of them (QB vs opp DST, QB+1) are `RESEARCH_REQUIRED`
here — one because we cannot compute the quantity, one because the dossier
contradicts itself about it. Only roster legality survives as hard, and we do
not yet hold the contract that defines it.

---

## 4. The QB+1 conflict, named rather than resolved

**The dossier says both of these.**

§40.2, hard-constraint list, verbatim:
> **HARD_CONSTRAINTS**: … At least one QB stack (QB+1 pass catcher) per lineup.

§1.1 and §1.2, and the §67 stack-type matrix:
> Naked QB (no pass catcher): `MODERATE_EMPIRICAL_SUPPORT` *against* in most
> main-slate contexts, **except for rushing QBs** and rare "spread it around"
> situations.
> Best conditions: high rushing-QB share, low cost, sparse WR/TE pricing.

And §1.2's own engineering recommendation:
> Implement **soft preferences** for QB+1 and QB+2 stacks, with world-based
> simulation allowed to override when naked or triple stacks outperform.

So one engineering table says hard; the prose, the stack matrix and the
engineering recommendation all say soft. **I am not picking one.** A hard rule
would forbid a construction the same document calls conditionally valid; a soft
rule would discard the strongest empirical regularity in the dossier. The
difference is decidable by experiment — **DFS-X2** below.

Until it resolves, the build should carry QB+1 as a **generator archetype
weight**, not a feasibility constraint, because an archetype weight can be set
to 1.0 to reproduce the hard rule exactly, while a hard constraint cannot be
relaxed without rebuilding the generator. **The reversible choice is the one
that keeps the experiment runnable.**

---

## 5. Missing modules

New, in dependency order. None may be built before its dependency.

| Module | Purpose |
|---|---|
| `nfl/dfs/scoring/site_rules.py` → add `DRAFTKINGS_CLASSIC` | Cap, slots, FLEX eligibility, min teams, DST points-allowed ladder. **Blocked on OUT-025** |
| `nfl/dfs/scoring/dst.py` + engine DST layer | Sacks, INTs, fumble recoveries, defensive/return TDs, safeties, points-allowed ladder. **Football work, not DFS work** |
| `nfl/dfs/classic/universe.py` | Full-slate roster universe with the four declared universes, mirroring `showdown/universe_contract.py` |
| `nfl/dfs/classic/solver.py` | Legal Classic solver, brute-force fixtures |
| `nfl/dfs/classic/archetypes.py` | Stack shapes as generator archetypes, **not** constraints (§4) |
| `nfl/dfs/classic/field_ownership.py` | Player/stack/lineup ownership. Named `field_ownership`, not `ownership` (§0c) |
| `nfl/dfs/classic/field_generator.py` | Ownership- and archetype-weighted opponent lineup sampling |
| `nfl/dfs/classic/duplication.py` | Duplicate estimation from the field model, not an ownership-product heuristic |
| `nfl/dfs/classic/payout.py` | Contest structure, prize splitting on ties |
| `nfl/dfs/classic/lineup_utility.py` | Expected payout, ROI, P(top-X), P(solo first) |
| `nfl/dfs/classic/portfolio.py` | Joint selection under exposure/diversity |
| `nfl/dfs/classic/portfolio_audit.py` | Entropy, effective counts, overlap, game/stack exposure |

---

## 6. Internal experiments — pre-registrations

All seven follow the same frame. **Evaluation blocks on slates, not lineups**:
73 entries on one slate are one observation of a slate, not 73 observations.
**Leakage safeguards common to all:** point-in-time projections and ownership
only; no realized-role labels (DFS-H2 measured +0.10 to +0.28 inflation from
them); no sportsbook total as a game-environment variable (`DFS-H3` names this
explicitly as forbidden); the football forecast frozen and identical across
arms, so only the portfolio layer varies.

**None may run before A7.** Each is registered now and blocked.

### DFS-X1 — mean-based vs world-based portfolio generation
- **Hypothesis:** a portfolio selected on simulated contest EV beats one
  selected on mean projection, measured on contest ROI over blocked slates.
- **Inputs:** identical frozen worlds; arm A ranks by mean DK points, arm B by
  simulated expected payout against a common field.
- **Metric:** ROI per slate, blocked bootstrap over slates; secondary P(top 1%).
- **Threshold:** arm B's ROI interval excludes arm A's point estimate over a
  pre-declared slate count. Failure recorded as a measured negative.
- **Trap:** both arms must face the **same** field draw, or the comparison
  measures field sampling.

### DFS-X2 — QB+1 hard vs soft vs emergent  *(resolves §4)*
- **Hypothesis:** enforcing QB+1 as a feasibility constraint does not improve
  contest ROI over an archetype weight fitted from worlds.
- **Arms:** (a) hard — infeasible without QB+1; (b) soft — archetype weight,
  fitted; (c) emergent — no stack term, simulation free to choose.
- **Metric:** ROI; secondary, the realized share of QB+1 lineups in arm (c).
  **If (c) converges on QB+1 unprompted, that is the strongest possible
  answer** and it makes the hard rule redundant rather than wrong.
- **Threshold:** hard is adopted only if it beats both others *and* arm (c)'s
  emergent QB+1 share is below a pre-declared level. Otherwise soft.
- **Leakage:** the QB-rush-share feature must come from the pregame state
  generator (T1-C), never from realized rushing.

### DFS-X3 — bring-back required vs conditional vs absent
- **Hypothesis, stated against our own evidence:** given FS1 finds cross-team
  dependence indistinguishable from zero, a bring-back preference does **not**
  improve ROI. This is a null-leaning pre-registration on purpose.
- **Conditioning variable:** prediction-time game environment only — the T1-C
  pregame state generator, pace and pass-rate priors, team-volume layer.
  **Sportsbook totals are forbidden.**
- **Threshold:** a positive result requires the interval to exclude zero on
  slates not used to build the conditioner.

### DFS-X4 — duplication-aware vs duplication-blind
- **Hypothesis:** optimizing expected payout net of duplication beats
  optimizing gross expected payout.
- **Metric:** ROI, variance, max drawdown across slates.
- **Trap:** the duplication model is itself estimated; an arm that wins because
  its duplication estimate is optimistic has won nothing. Report the realized
  duplicate count against the predicted one as a calibration check, and
  **refuse the comparison if that check fails**.

### DFS-X5 — overlap caps vs scenario diversification
- **Hypothesis:** scenario-based diversification (coverage of world clusters)
  beats a max-shared-players cap at equal portfolio size.
- **Metric:** ROI; secondary, entropy and effective number of games.
- **Note:** the dossier calls overlap caps "cosmetic". That is a hypothesis
  here, not a finding.

### DFS-X6 — fixed exposure caps vs simulation-derived exposure
- **Hypothesis:** exposures emerging from world-based selection beat
  hand-set caps.
- **Constraint that does not move:** `portfolio_guard`'s confidence-tag caps
  are a **governance** floor, not a strategy parameter. They stay enforced in
  both arms. This experiment is about strategy caps only.

### DFS-X7 — deterministic top-N vs seeded stochastic world sampling
- **Hypothesis:** seeded stochastic sampling over worlds produces a portfolio
  with better tail coverage than deterministic top-N by utility.
- **Metric:** P(at least one lineup in top 0.1%) per slate.
- **Reproducibility:** every arm carries a seed and an execution identity; a
  result that does not re-run bit-identically is void.

---

## 7. Dependencies

```
OUT-025 (DK Classic site contract, network — assigned)
   └── site_rules.DRAFTKINGS_CLASSIC
          └── classic/solver.py ── classic/universe.py
A7 full-slate joint world generator   ← THE GATE, and it is football work
   ├── DFS-FS2 (simulated vs FS1 dependence)   ← must pass before ANY stack rule
   ├── DFS-X1 … DFS-X7
   └── everything downstream
DST engine layer + DK points-allowed ladder (needs OUT-025)
   └── QB-vs-opp-DST rule, RB+DST, any legal Classic lineup at all
Ownership data (external, not held)
   └── field_ownership → field_generator → duplication → payout → utility
```

**Three independent gates, and none is DFS work:** A7 (football), OUT-025
(network, assigned), ownership data (external). The optimizer cannot be the
critical path because it is not on it.

---

## 8. Safest implementation order

1. **Finish the football blockers.** Early Only production run, upstream
   repairs, sealed distributions. Nothing below is startable.
2. **A7 — full-slate joint worlds.** The gate. Football work.
3. **DFS-FS2.** Compare simulated dependence against FS1, sign and ordering
   only, magnitudes never. **If the simulator's cross-row structure is still
   generator artifact (§0b), stop here and fix the generator.** A portfolio
   engine on uncoupled worlds is a worse instrument than a mean.
4. **OUT-025 → `DRAFTKINGS_CLASSIC` contract.** Then, and only then, a legal
   solver with brute-force fixtures.
5. **DST layer**, or an explicit, recorded decision to exclude DST — which for
   Classic means no legal lineup, so it is not really optional.
6. **DFS-X1** (mean vs world). Cheapest decisive experiment; it validates the
   whole architecture choice before anything is built on top.
7. **Field/ownership/duplication/payout**, in that order. Each is useless
   without its predecessor.
8. **DFS-X2 … X7**, then portfolio selection.
9. **Portfolio audit last in the pipeline, built first.** It already is.

---

## 9. Would the Showdown optimizer create a conceptual error if reused?

**Yes — three of them, and one is silent.**

1. **`optimal_worlds.py` hard-codes a two-club mask.** "Showdown is two clubs,
   so the mask is two bits and the full mask is 3." Classic spans 8–14 clubs;
   the DP dimension is wrong and the team-coverage rule it enforces is a
   Showdown rule. Reused as-is it would silently constrain a Classic lineup to
   two teams.
2. **The captain slot has no Classic analogue.** `captain_metrics.py` computes
   `p_top1` and `p_optimal_captain` for a 1.5×points / 1.5×salary slot that does
   not exist in Classic. FLEX is a *positional* freedom, not a multiplier.
   Porting captain logic to FLEX would apply a scoring concept to a roster
   concept.
3. **The silent one: `p_optimal` is a single-game quantity.** In Showdown every
   lineup draws from one game, so "how often is this player in the optimal
   lineup" is well defined. On a full slate the optimal lineup is a joint object
   over ~26 games, and per-game optimality frequency **is not a component of
   it**. A player can be in his game's optimal six and never in the slate's
   optimal nine. Reusing the number under the same name would look right and
   mean something else.

**What is safely reusable, and it is the valuable part:** the *disciplines*.
`universe_contract.py`'s four declared universes (the defect it closes —
comparing an exposure to a `P(optimal)` computed over a different player set —
is not Showdown-specific). `portfolio_guard`'s audit-after-construction stance.
`optimal_worlds`' exact DP over a binding cap rather than a greedy top-N, and
its reporting of the tie rate. `candidates.py`'s `salary_relief_dependence`.
`scenarios.py`'s refusal to fake a margin bucket from fantasy points.

Port the reasoning. Do not import the module.

---

## 10. Exact files that would change

**Modified**
- `nfl/dfs/scoring/site_rules.py` — add `DRAFTKINGS_CLASSIC`, extend
  `assert_lineup_legal` for positional slots and FLEX. Blocked on OUT-025.
- `nfl/dfs/scoring/statline.py` — DST fields; remove `'dst'` from
  `NOT_SIMULATED` only when a real layer exists.
- `nfl/dfs/scoring/draftkings.py` — `score_dst`, points-allowed ladder.
- `nfl/dfs/scoring/fanduel.py` — same, for interface parity (roadmap A2/A5).
- `nfl/production/nonqb/football_engine.py` — DST event layer. **Football
  work, and it changes the forecast**, so it goes through the normal
  candidate/pre-registration path, never as a DFS change.
- `nfl/production/dfs/portfolio_guard.py` — accept Classic lineup shape.
- `nfl/capture/registry.py` — ownership data as a `DeliveredSpec` if it ever
  arrives, `forecast_eligible=False`.
- `nfl/production/pipeline.py` — EDGES for any new vintage read.
- `nfl/WORK_QUEUE.md`, `docs/AGENT_OUTBOX.md`.

**New** — the twelve modules in §5, plus a test per module.

**Untouched, deliberately:** everything under `nfl/production/` that computes
football. The wall holds in the same shape as the market board: no DFS module
may be imported by a forecast stage, and the import graph is walked rather than
asserted (`test_early_1pm_market_board.test_no_forecast_stage_imports_this` is
the pattern).

---

## 11. Work-queue items recommended

| ID | Classification | Depends on |
|---|---|---|
| `DFS-C0` | `RESEARCH_BLOCKER` — record this gap analysis and the dossier's provenance collision (§0) | none |
| `DFS-C1` | `RESEARCH_BLOCKER` — pre-register DFS-X1…X7 before any arm runs | DFS-C0 |
| `DFS-C2` | `PRODUCTION_BLOCKER` — `DRAFTKINGS_CLASSIC` site contract | OUT-025 |
| `DFS-C3` | `PRODUCTION_BLOCKER` — DST engine layer + DK ladder | DFS-C2, A7 |
| `DFS-C4` | `RESEARCH_BLOCKER` — DFS-FS2 gate: simulated dependence vs FS1 | A7 |
| `DFS-C5` | `NONBLOCKING_TECH_DEBT` — shared scoring interface (roadmap A2) | none |
| `DFS-C6` | `MEASUREMENT_DEFECT` — the `ownership` name collision (§0c); rename before a third meaning lands | none |
| `DFS-C7` | `RESEARCH_BLOCKER` — resolve QB+1 hard/soft/emergent via DFS-X2 | DFS-C1, A7 |

---

## What this analysis did not do

No optimizer was built. No rule was encoded. No constant was fitted. Nothing
from the dossier entered the football model, and nothing could have: the DFS
tree imports from `nfl/production` and is imported by nothing there.

**The football blockers remain the priority and this document does not compete
with them.** Its purpose is to make sure that when the worlds finally exist,
the layer above them is built on measurements this repository holds rather than
on a packet it has already partly rejected.

**V2 NOT YET EARNED**
