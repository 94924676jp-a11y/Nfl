# Football intelligence audit, v0 (Showdown production path), 2026-10-08

**Owner directives:**
- the QB-replacement handoff, with the independent Perplexity package pinned at `e8a2a3ae`;
- the repository-wide football intelligence, causal dependency and simulation integrity audit.

**Scope of this version.**
- **Audited:** the Showdown production path, end to end, from the slate state to the DK upload.
- **Not yet audited:**
  - the Classic `run_forecast` path;
  - FanDuel scoring;
  - the ownership and field models;
  - late swap;
  - the Classic optimizer;
  - the non-QB `vintage_selector` pipeline;
  - the prospective/q9 shadow paths.
- **Not claimed:** "the repository has been audited". It has not.

**Machine-readable graph:** `nfl/research/intel/DEPENDENCY_GRAPH_SHOWDOWN_v0.json`. It holds 29 edges, each with:
- its status;
- the code that implements (or fails to implement) it;
- its evidence;
- whether it is an accounting rule, a causal hypothesis, a statistical association, data lineage or governance;
- its downstream consumers.

| Status | Edges |
|---|---:|
| Consumed | 10 |
| Implemented, never consumed | 3 |
| Missing | 9 |
| Incorrect | 5 |
| Shadow only | 1 |
| Excluded by owner instruction | 1 |

## 1. The independent audit, reconciled against HEAD

**What changed since `e8a2a3ae`.**
- Only these changed: the readiness split, the point-in-time wiring (the identity in live mode), the runner ledger fix
  and new tools.
- These are byte-identical: `proj_v1`, `sim/game`, `showdown_draws`, `classic_slate_run` and `role_state`.
- So every Perplexity edge classification carries to HEAD. Each was re-verified here, not taken on trust.

| Perplexity claim | At HEAD | Evidence |
|---|---|---|
| QB identity reaches its own attempts, carries and efficiency | **confirmed** | Daniels' pass factor is 0.736 and Mayfield's 0.911 (DRAWS `player_mean_anchor`) |
| Team attempts, target pool and scoring centre are QB-invariant | **confirmed** | `proj_v1.team_volume(panel, env)` (`:167`) and `football_points.expected_points` (`:68`) take no QB |
| Receiver targets are equal to 2 dp, not exactly | **confirmed**; my earlier "identical" was imprecise | Egbuka 7.7480 vs 7.7469 |
| QB completion is not consumed at the catch draw | **confirmed** | no `completion` token in `showdown_draws` or `sim/game`; catches are `_binom(tgt, receiver catch_rate)` |
| Independent post-transform yard factors break passer = receiver | **confirmed, and reproduced through the real function** | `test_world_accounting_check` (the 100/50 probe gives 50/100) |
| Final-world TB gap of −29.977 (Daniels) and +10.065 (Mayfield) | **reproduced exactly** | `nfl/research/accounting/WORLD_ACCOUNTING_TB_DAL_*.json` |
| Catch/yard/TD unlinking is a *risk candidate* | **now measured: a confirmed defect** | section 2 |
| INT/DST disagreement is a *risk candidate* | **now measured: a confirmed defect** | section 2 |
| Different player lists consume different RNG draws | **confirmed by code reading** | `sim/game` draws in player order. Scenario A/Bs are not common-random-number controlled |
| `proj_v1` defaults to the MARKET arm; Showdown selects FOOTBALL_ONLY | **confirmed** | the market firewall check passes for Showdown only |
| One ALPHA per club and position is a model convention | **confirmed** | `role_state.ALPHA_LIMIT` (`:75`), demotion at `:257-276` |
| 311 screened changes; 0 eligible for a prelock A/B | **agreed** | their screen uses the postgame primary passer |

**A correction to my own work.**
- `QB_CHANGE_EFFECT.json` labels the starter after the fact: the QB with the most attempts in the game.
- Its exclusion of mid-game changes also conditions on in-game events.
- So the −1.06-point figure for in-season replacements is a **descriptive association on outcome-labelled cases**. It
  is not a pregame forecast effect and must not be quoted as one.
- `QB_DEPENDENCY_AUDIT_2026-10-08.md` §2 carries this caveat from this commit on.

## 2. Statistical integrity: what the PUBLISHED worlds actually contain

**The tool.**
- `nfl/tools/world_accounting_check.py` (QBCTX-C1, validation-only, no gate); tests 9/9.
- It reads the arrays the optimizer scores: the post-`efficiency_worlds` and post-DST-anchor `*_WORLDS.npz` and
  `*_DRAWS.json`.
- The simulator's own certificate covers only the raw worlds.
- **Exceptions:** the simulator has no lateral, non-QB-pass or penalty events, so no legitimate exception is available
  to any world. Valid synthetic controls pass, and a bonus-line storage-rounding control passes.

Each cell below is worlds with a violation, out of 2,000.

| Check (ordinary-event law) | TB@DAL Daniels R7 | TB@DAL Mayfield R4 | ATL@NO production |
|---|---|---|---|
| Club passing yards = receiving yards | TB 1,993, DAL 1,925 | TB 1,848, DAL 1,930 | ATL 1,988, NO 1,970 |
| Club passing TDs = receiving TDs | 2 + 2 | 0 | 1 |
| Receiving yards require a reception | 1,534 (2,757 player-worlds) | 1,499 | 1,527 |
| Receiving TD requires a reception | 528 (610 player-worlds) | 508 | 422 |
| Interceptions thrown ≤ opposing DST takeaways | TB 414, DAL 538 | TB 396, DAL 524 | ATL 303, NO 491 |
| Club points ≥ 6 × offensive TDs | TB 72, DAL 44 | TB 67, DAL 55 | ATL 83, NO 70 |
| An inactive player records events | 0 | 0 | 0 |
| Scored DK = DK recomputed from the published stats | 0 (2 bonus-line rounding cells) | 0 (4) | 0 (1) |

### Where each break enters

The decomposition divides each published stat by its recorded per-player efficiency factor to recover the raw worlds.

| Break | Stage | Detail |
|---|---|---|
| Passer ≠ receiver yards | `efficiency_worlds`, plus off-slate "ghost" players | The **mean** gap is almost entirely the transform: TB Daniels −29.87 of −29.98 yards, Mayfield +10.14 of +10.06. The raw worlds' off-slate players average about 0 but move single worlds by up to 35–46 yards. The published worlds carry no ghost totals, so the exact per-world identity cannot be checked on them. |
| Catchless yards and catchless TDs | the raw simulator | `sim/game` splits club receiving yards and TDs by share and draws catches independently. A scale factor cannot create or remove either. |
| INT > opposing takeaways | the transform | INTs are drawn in `efficiency_worlds` from the projection-level `int_rate` (`showdown_slate_run.py:109`), after and independent of the raw DST components. |
| Points < 6 × TDs | the score-first centring | Points are a centred continuous draw; TDs are drawn from the centre. |

These are correctness findings about the incumbent that produced ATL@NO's live portfolio. They are not a reason to
retune that portfolio.

## 3. Gap register (deliverable A), ranked

| # | Gap | Class | Severity | Evidence |
|---|---|---|---|---|
| G1 | Passer and receiver credits come from different numbers (AC1) | INCORRECT, accounting | **High**: QB–WR stack correlation and captain choice read these worlds | the checker; the audit probe |
| G2 | Receiving yards and TDs without a catch (AC2) | INCORRECT, accounting | **High**: DK PPR scoring awards 1 point a catch | the checker |
| G3 | INTs not linked to the opposing DST (AC3) | INCORRECT, accounting | **Medium-high**: QB-vs-opposing-DST pairs | the checker |
| G4 | Points not built from scoring events (AC4) | INCORRECT, accounting | Medium: DST points-allowed, kicker, script | the checker |
| G5 | Raw certification standing in for the published arrays (AC5) | INCORRECT, governance | High: it let G1–G4 pass silently | DRAWS metadata |
| G6 | QB → team volume and scoring (QB1, QB2) | MISSING, causal | **High** for QB-change slates; blocks READY today | stored scenarios; outcome-labelled association |
| G7 | QB completion and depth → receiver catch and gain (QB3) | IMPLEMENTED_NOT_CONSUMED | High | code |
| G8 | QB → target allocation (QB4) | MISSING | Medium | stored scenarios |
| G9 | QB style → opposing DST, drive survival (QB5) | MISSING | Medium | code |
| G10 | No possession or drive state (GS2) | MISSING | Medium-high: score-first worlds cause G4 | code |
| G11 | Weather and rest carried but never consumed (EN1, EN2) | IMPLEMENTED_NOT_CONSUMED | Medium; magnitude unknown | grep |
| G12 | OL and defensive personnel; coaching (PE1–PE3) | MISSING; the **data is not established** | unknown | grep |
| G13 | In-game injury and relief (PE4) | MISSING (successor is SHADOW_ONLY) | Medium | code |
| G14 | Scenario A/Bs are not common-random-number controlled | INCORRECT, experimental design | Medium: it confounds every counterfactual | code |
| G15 | Opponent adjustment (EN3) | NOT_MODELLED by owner instruction (item 9) | owner decision | code |
| G16 | One ALPHA per room (RL1) | model convention; harm unmeasured | Low-medium | code |

## 4. Simplification and assumption register (deliverable C), partial

| Approximation | Where | Justification on record | Risk |
|---|---|---|---|
| Club volume and scoring from club history (current season + 4 prior pseudo-games) | `proj_v1`, `football_points` | declared blend | QB-, coach- and personnel-blind |
| Proportional redistribution when a skill player is out | `allocate_opportunity` | historical shares | no scheme or personnel response |
| Score-first centred worlds | `sim/game` | centring to projection means | events cannot sum to the score (G4) |
| Independent per-player efficiency recentring | `efficiency_worlds` | matches projection means per opportunity | breaks joint laws (G1, G3) |
| Projection-level INT rate | `efficiency_worlds` | — | unlinked to the defence (G3) |
| Archetype prior for thin-history QBs | `player_prior` | cohort pooling | cohort support is reported as if personal (Daniels) |
| `ALPHA_LIMIT` | `role_state` | "two priors that did not know about each other" | a model prior written as a football law |
| Weather and opponent not modelled | `football_points`, `kicker_world` | declared NOT_MODELLED; opponent by owner | declared, not hidden |

## 5. Counterfactual test library (deliverable E): plan, with one prerequisite

**The prerequisite is G14.** Today a scenario change also changes the random path. Before any perturbation is read as
an effect, the harness needs either semantic random streams or a negative control: the same scenario, relabelled
players, same seed, measured movement. Without one, "changed numbers" are not evidence. Building the streams changes
the incumbent's random path, so it is research-arm only.

**The harness.**
- the real entrypoint (`showdown_tonight`);
- a sealed point-in-time manifest per perturbation;
- a fixed seed;
- the read inventory (`NFL_PIT_TRACE`);
- the dependency graph's consumers asserted.

A perturbation passes when the declared mechanism is reached by its declared consumer. A large numeric change is not
required.

| Counterfactual | Expected under the incumbent (from the graph) |
|---|---|
| QB swap | QB lines move; team volume, centre and targets do not (G6–G8) |
| RB1 out | shares renormalize over the active backs |
| WR1 out | targets renormalize; no coverage response |
| OL or defensive injury | no consumer; must show "no mechanism", not "zero effect" |
| Weather change | no consumer (G11) |
| Game-script change | volume responds through GS1 |
| In-game injury | no consumer (G13) |
| Multiple simultaneous changes | interactions only through the shares |

## 6. Implementation board (deliverable F), ranked

| # | Work item | Modules | Class | Dependencies | Cost | Acceptance | Risk | Eligibility |
|---|---|---|---|---|---|---|---|---|
| 1 | **C1 published-world checker** | `world_accounting_check` | validation-only | — | done | 9/9; findings reproduced | none (no gate) | in repo, report-only |
| 2 | **Publish ghost (off-slate) totals in the worlds** so C1 is exact | `showdown_slate_run` world writer | publication (adds arrays) | — | low | the uploads are byte-identical; C1 gives an exact per-world identity | the certificate refuses added arrays (A4), so it must be declared | production-eligible after a matched regression |
| 3 | **C2 event-credit research arm `QBCTX_2026_10_C2`**: one pass-event ledger | new `nfl/research/qbctx/` consuming the raw `sim/game` events | research | the raw stat draws | moderate | C1 shows 0 violations on unrounded worlds; a valid lateral control; QB efficiency **kept** as a team-passing quantity | repeats EL_S1's failure if QB efficiency is dropped | shadow only; production needs the owner and a new frozen study (EL_S1's confirmation data may not be reused) |
| 4 | **Common random numbers** for scenario A/Bs (G14) | research copy of the `sim/game` RNG | research | — | low-moderate | a relabel negative control shows 0 movement | changes the incumbent's random path | research only |
| 5 | **M1 crossed QB/receiver completion and gain model `QBCTX_2026_10_M1`** | new research fit; inputs from admitted PBP (passer, receiver, complete, air yards, YAC) | research | #3, #4 | moderate | chronological out-of-sample against receiver-only and QB-only baselines | QB/team confounding, sparse pairs | shadow only |
| 6 | **SC-QB-ENV-1** (QB → team volume and centre; already pre-registered) | research copies of `team_volume` and `football_points` | research | #5 for passing quality | moderate | §3 of `QB_DEPENDENCY_AUDIT` | the outcome-labelled history | shadow only |
| 7 | Qualify the historical QB-change cohort with **pregame** labels | point-in-time injury/depth captures per week | data | captures that do not exist yet for 2021–2025 | data-bound | a cohort with pregame starter evidence and a cutoff | there may be no lawful historical labels | research |
| 8 | Event-derived INT ↔ DST and points ↔ events (G3, G4) | part of #3, later a possession model (G10) | research | #3 | high (possession model) | C1 at 0 on INT and points | large refactor | shadow only |
| 9 | Weather and rest consumers (G11) | research | research | the data exists in `TEAM_GAME` | low-moderate | out-of-sample | small effects | shadow only |
| 10 | `ALPHA_LIMIT` ablation (G16) | research copy of `role_state` | research | #4 | low | out-of-sample | — | shadow only |
| 11 | F1 game-date check; F2b ordering by capture time | `showdown_slate_state`, `player_prior` | validation / data | — | low | matched regression | F2b can move outputs | owner review |

**Recommended order:** 1 (done) → 2 → 4 → 3 → 5 → 6, each a separate change, each measured against the incumbent.

**What I did not do.** Make C1 a READY gate. Every published world today violates G1–G4, so the gate would refuse
every slate, the valid incumbent included. That is an owner decision: see the dashboard.

## 7. Predictive research program (deliverable G)

- **Fit windows:** 2021–2024. 2025 has been read descriptively (`QB_CHANGE_EFFECT`), so it is development data, not a
  holdout.
- **Confirmation:** prospective 2026, week 6 onward, frozen before reading.
- **Metrics:**
  - player DK CRPS;
  - team points CRPS;
  - passing and receiving yards CRPS;
  - joint energy and variogram scores;
  - C1 violations;
  - DFS exposure changes, reported but never a bar.
- **Clustering:** by game date and team.
- **Margins:** declared before any fit.
- **Retrospective payouts** are never promotion evidence.

## 8. Owner decision dashboard (deliverable H)

| Component | State |
|---|---|
| Starter identity and availability | **CORRECTLY IMPLEMENTED** (P0 repaired; 6 integration items still unverified) |
| Point-in-time selection | **IMPLEMENTED, REPLAY-PROVEN**, opt-in |
| QB own projection | **IMPLEMENTED** (thin-history QBs on cohort priors) |
| QB → team volume, scoring, receivers | **MISSING**; Daniels-scenario READY is blocked |
| Passer/receiver/INT/points accounting in the published worlds | **INCORRECT** (measured) |
| Event-linked repair (EL_S1) | **SHADOW, failed confirmation** |
| Weather, rest | **DATA PRESENT, NOT CONSUMED** |
| OL, defensive personnel, coaching, in-game injury | **MISSING**; data not established |
| Opponent adjustment | **EXCLUDED BY OWNER** |
| Counterfactual harness | **PLANNED**; needs common random numbers first |

**Owner decisions requested.**
1. Should C1 become a READY gate now? It would refuse every slate. Or after C2?
2. Re-open the opponent adjustment (item 9)?
3. Approve a fresh prospective confirmation block (2026 week 6 onward) for the QBCTX arms.
4. Approve item 2 (publishing ghost totals) as a declared publication change.
