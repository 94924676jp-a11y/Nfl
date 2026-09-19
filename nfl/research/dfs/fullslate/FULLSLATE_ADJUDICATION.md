# Full-slate DFS packet: claim adjudication

Packet: `external-research/nfl-fullslate-dfs-construction-2026-09-18/`,
sha256 `897caf23…`, 1,062 lines, ~19,500 words, preserved unchanged.
Reproduction: `reproduce_external_panel.py` → `FULLSLATE_REPRODUCTION.json`.

## 0. What reproduction could and could not mean here

The report names four companion files — two scripts and two result JSONs — as
"included alongside this report". **They did not arrive.** So this is not a
re-run of their code. It is a re-implementation from their written method,
which tests something different and, for adjudication, better: whether the
method as described reconstructs the numbers as published.

**The headline result of that exercise is an asymmetry.** The *realized-label*
panel reproduces almost exactly. The *ex-ante* panel does not. Since both come
out of the same stat-line builder, the same certified scoring adapters and the
same correlation code, the builder, the scoring and the statistics are
validated by the first, and the disagreement is isolated to how prior-week role
labels are formed.

| | published | reproduced | verdict |
|---|---:|---:|---|
| QB·PC1 **realized** 2024 | 0.420 | **0.421** | matches |
| QB·PC1 **realized** 2025 | 0.438 | **0.445** | matches |
| QB·PC1 **ex-ante** 2024 | 0.368 | **0.207** | disagrees |
| QB·PC1 **ex-ante** 2025 | 0.274 | **0.170** | disagrees |

Panel sizes match exactly — **512 ex-ante and 544 realized team-games per
season** — so the Week-1 exclusion is correct as described. Touchdown
attribution is exact: 809 `pass_touchdown` flags in 2024 produce 809 passing
and 809 receiving touchdowns in the rebuild, 511 rushing.

### Two measured causes of the ex-ante gap, neither of them ours

**Role collisions.** The method reads: "the quarterback is the player with the
most prior pass attempts, `PC1` through `PC3` are the three players with the
most prior targets, and `RUSH1` and `RUSH2` are the two players with the most
prior carries." Read literally the three rankings are independent, so one
player can hold two roles. Measured on 2024:

| collision | team-games | share |
|---|---:|---:|
| QB is also RUSH2 | 134 / 512 | **26.2%** |
| PC3 is also RUSH1 | 56 / 512 | 10.9% |
| PC2 is also RUSH1 | 46 / 512 | 9.0% |
| PC1 is also RUSH1 | 11 / 512 | 2.1% |

A player correlated with himself has r = 1, so the literal reading drives
QB·RUSH2 to **+0.435** against a published **+0.118**. The published number
cannot have been produced that way. Under sequential removal it is +0.078 and
RUSH1·RUSH2 lands on −0.118 against a published −0.121.

**An ex-ante window that appears to include the current game.** Re-running with
the cumulative window extended to include the game being labelled moves every
quarterback pairing toward the published value:

| pair | season | exclusive (ours) | inclusive | published |
|---|---|---:|---:|---:|
| QB·PC2 | 2024 | +0.250 | **+0.293** | +0.296 |
| QB·PC3 | 2024 | +0.108 | **+0.195** | +0.208 |
| QB·PC1 | 2024 | +0.207 | +0.257 | +0.368 |
| QB·PC1 | 2025 | +0.170 | +0.228 | +0.274 |

QB·PC2 and QB·PC3 land essentially on the published figures. This is evidence,
not proof, that the report's "ex-ante" labels carry current-game information.
**If so, its own headline ex-ante numbers are partially leaked, and the true
prediction-time correlations are lower still than it reports** — which
strengthens its central warning rather than weakening it.

## 1. The matrix

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | QB with PC1/PC2/PC3 positively correlated ex-ante | **REPRODUCED (direction), CONFLICTS (level)** | Ours +0.207/+0.250/+0.108 (2024) against +0.368/+0.296/+0.208. Sign and ordering hold; magnitudes are 25–50% lower. Invariant across all three role-assignment variants |
| 2 | QB with opposing DST ≈ −0.37 | **NOT_REPRODUCED_HERE** | No DST scoring adapter exists (`statline.NOT_SIMULATED`: "the engine produces no team-defence outputs at all") and DK points-allowed tiers cannot be verified without network. Not a disagreement — an inability, recorded as an architecture gap |
| 3 | Opposing QBs positively correlated unconditionally | **REPRODUCED (direction), lower** | Ours +0.053 / +0.086 against +0.088 / +0.180. Positive both seasons |
| 4 | Cross-team pass-catcher joint-tail lift | **PARTIALLY_REPRODUCED** | Same-team lift reproduces: QB·PC1 1.812 / 1.577, QB·PC2 1.882 / 1.434, QB·PC3 1.303 / 1.482 (report 1.550 / 1.706 for QB·PC3). PC1·PC2 1.022 / 1.110 against their 0.947 — both ≈ 1, and the *conclusion* ("no joint-ceiling benefit") reproduces |
| 5 | Stacking inflates the p95 ceiling | **REPRODUCED** | QB+PC1 **+6.08% / +5.77%**, QB+PC1+PC2 **+6.63% / +6.00%**, QB+PC1+PC2+PC3 **+8.19% / +8.23%** over a 200,000-draw independent resample of the same marginals |
| 6 | DK and FD correlation structure are near-identical | **REPRODUCED** | Max \|DK − FD\| across every same-team pair and both seasons: **0.0153**. Their claim is "less than 0.02 on nearly every pair". Confirmed |
| 7 | Realized labels inflate correlations (leakage) | **REPRODUCED, STRONGLY** | Independently, in our pipeline: QB·PC1 +0.207→+0.421 and +0.170→+0.445; PC1·PC2 −0.014→+0.206 and +0.072→+0.174; RUSH1·RUSH2 −0.118→+0.110 and −0.179→+0.070. Every pair inflates, by +0.10 to +0.28 |
| 8 | Stacking-field frequency claims (what % of the field stacks) | **SUPPORTED_EXTERNAL_ONLY** | No contest-entry data exists in this repository. Unverifiable here, and not verifiable by any football measurement |
| 9 | Bring-back claims | **HYPOTHESIS** | The mechanism claim — that bring-back value is a between-game environment effect, since opposing QBs are positive unconditionally and negative within realized-total terciles — is coherent and our unconditional sign agrees. The tercile conditioning uses a **realized** variable and is descriptive. Registered as DFS-H3 |
| 10 | RB with own DST / RB with opposing DST | **NOT_REPRODUCED_HERE** | Same DST blocker as row 2 |
| 11 | Salary and duplication claims | **SUPPORTED_EXTERNAL_ONLY / INDUSTRY_CONVENTION** | Requires contest results and field composition. No such data here |
| 12 | Field-model architecture (Dirichlet-multinomial opponent model) | **DESCRIPTIVE_ONLY** | A published method (*Management Science*), correctly cited. Nothing in this repository implements or tests it |
| 13 | Portfolio-construction recommendations | **HYPOTHESIS** | Depends on rows 8, 11 and 12, none of which is verifiable here |
| 14 | "The world generator has a sign error" | **UNSUPPORTED_AS_STATED** | See `FULLSLATE_COUPLING_RECONCILIATION.md`. It compares a historical correlation in **fantasy points** against a simulated one in **offensive yards**. Both reproduce under their own units; the sign difference is the unit, not an error |
| 15 | RUSH1·RUSH2 negative relationship "largely disappears in the tail" | **CONFLICTS_WITH_CURRENT_REPO_EVIDENCE** | Rests on a 2025 tail lift of 0.996. Ours is **0.735** — clearly below 1. The 2024 value (0.674 against their 0.578) is directionally similar. The claim that two backs are "a mediocre structure, not a forbidden one" does not follow from our numbers |
| 16 | QB+3 shows diminishing marginal dependence value | **CONFLICTS_WITH_CURRENT_REPO_EVIDENCE** | Our p95 inflation *increases* with stack size — +6.6% at QB+2 against **+8.2%** at QB+3, in both seasons. No diminishing return is visible at three |

## 2. Stale repo-state claims, re-resolved against HEAD `e6eeed5`

The report's §24 describes an earlier checkout. Every statement re-measured:

| Report says | Current state | Verdict |
|---|---|---|
| "`P7_DEPENDENCY_DAG_SPEC.md` as a specification only" | Phase 1 implemented at `44ff8ed`; `P7_DECLARED_READS.json` reports `PHASE_1_DECLARATION_ONLY` with 27 declared edges and audit `EVERY_VINTAGE_READ_DECLARED` | **STALE_REPO_STATE** |
| "`SYSTEM_STATE.json` is absent" | Present since `9bb5610`, generated by `nfl/tools/system_state.py` | **STALE_REPO_STATE** |
| "`CURRENT_STATE.md` is stale as of 2026-09-07" | Now *generated* from `SYSTEM_STATE.json`; a staleness test fails if it drifts | **STALE_REPO_STATE** |
| "across 169 test files" | 180 test files, 184 suite modules | **STALE_REPO_STATE** |
| "OAS1 `GO_NO_GO.md` records NO-GO on gates 3, 4 and 5" | All ten research-fit gates YES; the Week-2 candidate is fitted. Gates 11 and 12 remain NO and are *not* research-fit gates | **STALE_REPO_STATE** |
| "A Contract 4 mismatch remains open: 18 of 20 against `BATCH_AGREEMENT = 19`" | Corrected by append on 2026-09-17 at `340d581`, eighty minutes after introduction and before Contract 4 ran once. `P8` added `test_contract_text_matches_code.py` | **STALE_REPO_STATE** |
| "the Showdown solver had no both-teams constraint" | Repaired; `OPTIMAL_LINEUP_MUST_SATISFY_SITE_TEAM_COVERAGE` is enforced as a fourth DP dimension | **STALE_REPO_STATE** |
| "the Showdown `p_optimal` universe contained 28 players with no kickers and no DST, yet the portfolio rostered a kicker at 22.5%" | Repaired by the universe contract and player-keyed kicker identity | **STALE_REPO_STATE** |
| "`run_suite.py` … a tally-based runner with a `blocked()` escape hatch" | Accurate. `blocked` is a declared state, reported separately, and is not counted as a pass | **REPRODUCED** |
| "the DFS layer above the scoring adapter is essentially absent: no field model, no contest simulator, no duplication model, no portfolio optimizer" | Accurate | **REPRODUCED** |
| "FanDuel constants relayed by an operator rather than fetched" | Accurate, and unchanged: provenance stays `VERIFIED_RULE_VALUE_RELAYED_SOURCE` | **REPRODUCED** |

**Eight of eleven repo-state claims are stale.** None was inherited.

## 3. A finding about our own code, surfaced by this work

The two certified scoring adapters **do not share an interface**. DraftKings
keeps its bonuses inside `RULES` and has one `two_point` key; FanDuel puts
bonuses in a separate `BONUSES` dict and splits `two_point_scored` from
`two_point_thrown`. Both are faithful to their own site and neither is wrong,
but a caller written against one raises `KeyError` on the other — which is
exactly what happened on this reproduction's first run.

Handled in research code by `resolve_coefficients`, which refuses on a
coefficient it cannot find rather than defaulting to zero, because a silent
zero looks like a small correlation difference. **The certified adapters were
not touched**: changing a scoring contract's public shape to suit a research
consumer is how it stops meaning what it was verified to mean. Recorded in the
gap map instead.

## 4. What is explicitly not concluded

No portfolio optimizer is authorized. No constant from this report is
hardcoded. No simulator change is authorized. The descriptive tercile result
stays descriptive — see `DFS_HYPOTHESES.json`, DFS-H3, which converts it into a
prospective experiment using prediction-time variables only.

**V2 NOT YET EARNED**
