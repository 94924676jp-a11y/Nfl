# NFL V1 freeze packet

**2026-09-09.** Suite **50 modules, 527 test functions, 3,102 checks, 0 failing,
0 raised**. Production entrypoint **16/16 SEALED**. G0A **11/12**. NFL-1 **NOT
AUTHORIZED**. `PATH_C_STATE` untouched. No 2026 outcome read. Nothing promoted.

---

## A. V1 verdict

# `V1_REHEARSAL_READY_WITH_NAMED_BLOCKERS`

Six of the seven authorized repairs landed and are verified by execution. Two
things stop me writing `V1_ENGINEERING_READY_WAITING_ON_G0A`, and neither is
external:

1. **One hard accounting invariant still FAILs on every game.** QB rush
   opportunity exceeds the non-RB carry pool in **190 of 2,800 draw cells**,
   worst **21.6 carries**. That is wrong causal ownership by the ruling's own
   list. Its fix is **A1**, pre-registered in OWN-8 and validated in OWN-9 —
   and this ruling does not authorize implementing it. I did not implement it.
2. **The V1 candidate mode is not reachable from the production entrypoint.**
   R2 + C3 + C0 + A3G run through `engine_rehearsal`; `run_forecast` still
   drives the QB layer directly. Sealing 16/16 today therefore proves the
   entrypoint works, not that it carries the candidate architecture.

## B. Blocking table

| # | blocker | severity before | repaired | evidence after |
|---|---|---|---|---|
| **B8** | QB composition stretched small draws | passing-TD max **49.14** (record 7); factor to **59.85**; 55.8% of cells stretched | **YES — R2** | max **9.00**; cells above the record **47 → 3**; non-integer draws **51.9% → 0%**; **no ratio is formed at all** |
| **B9** | passing/receiving generated twice | identity failed **12,800/12,800** draws; mean residual 98.7 yd; corr **+0.001** | **YES — C3** | **32/32 PASS**; max residual **5.9e-15**; corr **1.0000**; TD mismatch gone |
| **B10** | two teams drawn independently | SD(total plays) **12.271** vs 9.265; **1.520%** of games outside the entire 2020–25 range | **YES — A3G** | SD **9.269**; outside-range **0.188%**; mean corr error 0.2717 → **0.1239** |
| **B11** | RB1↔RB2 wrong-signed | +0.081 vs −0.329 | **REFRAMED — not a defect** | premise was an estimand mismatch; like-for-like the incumbent gives **−0.3559** vs realised **−0.3716**, P(r>0)=0.000 |
| **B12** | QB allocation share leaked | **2.29% / 6.91%** of dropbacks | **YES — C0** | **16/16 `QB_ALLOCATION_SHARE_CONSUMED`**, 0.0% lost, no survivor renormalisation |
| **B13** | no draws emitted | four quantiles only | **YES** | raw draws, lossless by construction, one shared draw index, sha256 replay identity; 216,800 cells over the slate |
| **B14** | accounting FAILs did not gate | any FAIL could seal | **YES** | **9 HARD** invariants gate, **3 DIAGNOSTIC** never do; every artifact carries all twelve |
| **B15** | non-QB coverage | 2 of 32 teams filed | **DATA_BLOCKED** | chain defers by name |
| **NEW** | **rushing ownership** | — | **NO** | `qb_rush_contained_in_other` **190/2,800**, worst 21.6 — fix is **A1, unauthorized** |

## C. Accepted V1 candidate architecture — one owner per quantity

```
schedule ─► D1 team_volume ──(A3G rank copula: the two teams share ONE coupled
   │           index; marginals unmoved by construction)
   ▼
team_dropbacks_part ──► QB3 shares ──► largest-remainder apportionment  [R2]
   │                                     │
   │                                     ▼
   │                        INTEGER per-QB level, closes exactly
   │                                     │
   │                                     ▼
   │                        QB V1 supplies CONDITIONAL RATES ONLY
   │                        (no level; no division; no donor needed)
   │                                     │
   │        ┌────────────────────────────┴──────────────┐
   │        ▼                                           ▼
   │   sacks / scrambles                          attempts = THROW BUDGET  [C3]
   │                                                    │
   │                                   named untargeted pool ─┐
   │                                                    ▼     │
   │                                    every remaining throw dealt to
   │                                    exactly ONE receiver by the SAME simplex
   │                                                    │
   │                                                    ▼
   │                                   receptions ─► receiving yards ─► receiving TD
   │                                                    │
   │                                                    ▼
   └────────────────► passing line CREDITED BACK from that event  [C3]
                      cmp / pyds / ptd are the receiving totals attributed
                      on the targeted-throw share — one event, generated once

team_carries ─┬─ scrambles (dropback-owned)          ✓
              └─ rush_play_budget ─ kneel/designed QB/RB/WR/TE/fringe
                    ✗ QB rush still exceeds the pool — A1 unimplemented
```

**Duplicate owners removed:** the QB dropback level (was QB V1 *and* D1×QB3),
the target budget (was D1 `team_targets` *and* the throw process), and the
passing line (was QB V1 *and* the receiving layer). **Remaining:** rushing.

## D. Full-slate rehearsal — real 2026 week 1, 16 games, 0 halted

| check | result |
|---|---|
| cross-layer reconciliation | **32/32 PASS**, max residual **5.9e-15** |
| QB composition | **16/16 PASS** `QB_LEVEL_OWNED_BY_D1_X_QB3`, amplification **0** |
| QB allocation mass loss | **0.0%**, 16/16 consumed |
| receiving accounting | **16/16 PASS**, opportunity identity in **exact integer counts** |
| C3 target-count closure | **0** violating cells |
| passer credit | **16/16 PASS** |
| QB team volume | 12 PASS / 4 FAIL — QB-rush only, **4 of 400 cells** |
| **rushing** | **16/16 FAIL** — 190/2,800 cells, worst 21.6 |
| impossible tails | passing TD max **9.00** (was 49.14); non-integer draws **0%** |
| home/away dependence | SD(total plays) **9.269** vs historical 9.265; outside-range **0.188%** |
| RB1↔RB2 sign | **−0.3559** like-for-like vs realised −0.3716 |
| cross-game RNG | independent (0.0634, sampling noise); same `game_id` reproduces bit-for-bit |
| distribution artifact | 216,800 draw cells, lossless, shared draw index, sha256 replay id |
| deterministic replay | 16 distinct run ids; `code_commit` carries `+dirty[n]` |
| publication | `NFL1_NOT_AUTHORIZED` on all 16 |

## E. Scientific status

**Now in the V1 candidate architecture** (engineering integration, *not*
prospective promotion): R2, C3, C0, A3G. **Rejected this round:** A2 (already),
the RB1↔RB2 shared-`add_pool` ablation — it flips the sign *positive* at flat
week-1 priors. **Unimplemented:** A1. Full inventory in
`NFL_V1_RESEARCH_LEDGER.md`.

**Three subagent findings I verified personally before acting**, because each
changed architecture: A3G's marginal-preservation claim, B11's estimand
reframing, and B13's draw-index semantics.

**Reported against my own interest.** The A3G stream's *pre-registered* verdict
was that **no candidate cleared**; two of its clauses turned out to reject the
incumbent against itself, and the agent proved that rather than quietly
amending. I integrated A3G on the corrected clauses and am recording that the
pre-registered verdict failed on its own terms.

**Three defects I introduced and caught by re-running, not by review:**
applying R2 against an uncoupled volume while games drew a coupled one (383/400
cells); passing C3's integer other-pool count where a share was wanted (moved
the failure rather than removing it); and my own test anchoring a `find` that
R2's new branch shadowed.

## F. Governance

**G0A = 11/12. NFL-1 = NOT AUTHORIZED.** Item 1 needs an anchored capture in a
real T−90 window and was not touched. `PATH_C_STATE` unedited. Every candidate
remains rehearsal-only; no default changed; no 2026 outcome read.

## G. What still prevents V1 — three items

1. **Rushing ownership** — the one remaining hard accounting FAIL. A1 is
   pre-registered and validated; implementing it needs authorization.
2. **The candidate mode is not wired into `run_forecast`** — pure engineering,
   no science, and the next thing I would do.
3. **Non-QB player coverage is data-blocked** — 2 of 32 teams filed.

Items 1 and 2 are engineering-visible. With both closed, the remaining gap is
external (G0A and the injury feed) and the verdict becomes
`V1_ENGINEERING_READY_WAITING_ON_G0A`.
