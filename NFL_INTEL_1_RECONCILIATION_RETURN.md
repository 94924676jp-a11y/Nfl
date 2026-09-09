# NFL-INTEL-1 — reconciling the Perplexity frontier capability audit against the real system

**Task:** classify every material capability and recommendation in the supplied
report against measured project evidence, trying to falsify it rather than
agree with it, and then say whether anything in it displaces cross-layer
passing ↔ receiving from the front of the queue.

**Answer, stated first: nothing in the report displaces it.** The report's own
top-ranked item is blocked on an input that returns 404 for the season being
forecast, and its ceiling was already measured here. Its ninth-ranked item —
predictive distribution and dependence structure — is the one this project has
already measured to be broken by ~45% of the quantity, and the report ranks it
eighth of ten. On the ordering question the report is **wrong by its own
criteria**, because it ranked without access to the measurements.

**But it is not wrong everywhere, and one of its cautions caught a real defect
in code I wrote last session.** See §3.

---

## 0. Provenance of the thing being reconciled

| | |
|---|---|
| File | `c43a40fb-nflintel1frontiercapabilityaudit.pplx.md` |
| sha256 | `8d9d194592aea2372b78c7ba8e674ac817337a763113ad8e83876ab69fdd1fab` |
| Size | 484 lines, 18,903 words |
| Read | in full, all 484 lines |
| Status | external research intelligence. Not project truth, not a roadmap, not a specification. |
| Repo HEAD at reconciliation | `6cfb0e7`, branch `main` |
| G0A | unchanged, **11/12** |
| NFL-1 | unchanged, **NOT AUTHORIZED** |
| `PATH_C_STATE.json` | **not modified** |
| 2026 outcomes consumed | **none** |

New measurement code: `nfl/research/intel1/measure_intel1.py`, results in
`nfl/research/intel1/intel1_measurements.json`. Every number below that is not a
citation of an existing artifact comes from that script.

**A fairness note the report earns.** It is unusually careful for its genre. It
repeatedly says "whether the existing system does X **is not established from
the supplied architecture**", it distinguishes ownability from predictability
from forecast value, it declines to assert lift where it found none, and it
labels its own priority table "analyst judgments about research order, not
measured expected value". Most of what follows is not the report being wrong.
It is the report being **uninformed by the measurements**, which it says of
itself. Where it is actually wrong I say so; where it is right and we were
wrong, §3.

---

## 1. The classification

Categories are the owner's. `ALREADY TESTED-NEGATIVE` is used only where this
project ran the test and the answer came back against the recommendation.

### 1.1 The report's TOP 10 CAPABILITY GAPS

| # | Report's gap | Classification | The measurement that settles it |
|---|---|---|---|
| 1 | Player play participation and role state (route / block / release) | **DATA BLOCKED** + **ALREADY TESTED-NEGATIVE** on identifiability | ROUTE-BB1 already classified this per position from lawful free data: **WR `PROBABILISTICALLY_INFERABLE` (level only)**, **TE `NOT_IDENTIFIABLE`**, **RB `NOT_IDENTIFIABLE`** — block-vs-release is exactly the unobserved thing. Decision `DATA_BLOCKED_BUY_CANDIDATE`. `participation.route` is the **targeted** receiver's route, one scalar per play — the report says the same thing and it was already in the source inventory. `pbp_participation` **404s for 2026**, verified twice daily by `.github/workflows/nfl-availability.yml`. |
| 2 | All-route target demand rather than targeted play selection | **DATA BLOCKED** for the all-route half; **ALREADY COVERED** for the denominator half | Stage-2's participation target is **`s_pass_snaps`** — the player's share of **team dropbacks** (`s2_lib.TARGET`), not offensive snap share. The report's H1 contrasts route/dropback denominators against *snap-share* denominators; on the dropback half this system is already on the correct side. What remains is routes vs pass snaps, which is item 1 and blocked. |
| 3 | Dynamic role transition within season | **ALREADY COVERED**, and the added complexity is **ALREADY TESTED-NEGATIVE** in its nearest form | The accepted Stage-2 estimator is **`ewma_hl2`** — an exponentially weighted updating state with a **two-game half-life** (`nfl/production/nonqb/layers.py:35`, `166`). That is not a season-to-date aggregate, which is H2's stated baseline. P4E's feature ladder was run and failed; P4F found the low-history failure was an **estimator defect, not an information ceiling**. A change-point / state-space specification specifically has not been tried, so this is not closed — but the baseline the report proposes to beat is misdescribed. |
| 4 | Teammate replacement and reallocation under availability change | **GENUINE GAP** (already known, ranked 3rd here) | Opportunity **is** conserved and **does** redistribute: `allocation_only_when_available` ties allocation to appearance **on one draw index**, and share closure is enforced per draw (`accounting.NONQB_IDENTITIES`). What is absent is *role-aware* substitution — redistribution is proportional within the simplex. That is exactly H3. Measured consequence: within-team dependence is understated — **RB carries ↔ own targets +0.053 simulated against +0.308 historical (5.8×)**, competing receivers' targets **+0.207 against +0.584 (2.8×)**. |
| 5 | Team play volume and drive count as simulated outputs | **GENUINE GAP** — independently identified here before the report was read, ranked 2nd | D1 draws each team independently. Measured against 3,230 historical team-games: **opposing teams' carries +0.001 simulated against −0.535 historical**; **opposing teams' snaps +0.012 against −0.464**. J1's A3 cannot reach this: it couples metrics *within* a team. The report adds confirmation and no new information. |
| 6 | Availability as continuous practice and snap status | **PARTIALLY COVERED**; one **GENUINE sub-GAP** the report states more sharply than we had | C1 audited precisely this and found the headline P(play) = **0.9430** was being applied to the wrong population: off-report but gameday-eligible is **0.8876** (error +0.0554), off-report on any roster row is **0.5553** (error **+0.3877**). Appearance is `DECOMPOSED / INFORMATION_CONSTRAINED`. **The sub-gap is real:** the report's three-way split — uncertainty about *participating*, the distribution *conditional on playing*, and *in-game exit* — is not maintained here. Appearance is one binary. We have never named that third channel. |
| 7 | Pressure/protection and QB competing terminal outcomes | **ALREADY COVERED** for the accounting; **RIGHTS BLOCKED** for the process features | See §2 — this is the clearest falsification in the report and it is also its own H4 and its own experiment 4. |
| 8 | Contextual efficiency conditioned on forecast rather than realised conditions | **ALREADY TESTED-NEGATIVE**, and reopening it is refused by a standing decision | RC1: conversion holds **46.14%** of the oracle share and the ladder recovered **4.89%** of it. `receiving_conversion` is `RECOVERABILITY_CHARACTERIZED / HOLD_CHARACTERIZED / SIGNAL_WEAK`, decision `RC1-ACCEPT-001`, with `condition_to_reopen` = **"materially new INFORMATION, not another same-input estimator ladder."** The report's recommendation — "compare lagged adjusted residuals, coarse tendency interactions" — is another same-input estimator ladder. Refused on a rule set before the report existed. |
| 9 | Predictive distribution validation and dependence unit | **ALREADY COVERED as method**; **GENUINE GAP as result**, and it is the current #1 | The method is in place: CRPS, **energy score**, PIT, interval coverage, and **game / team-game clustered bootstrap** (C2), with naive SEs forbidden. H6 — "is coverage miscalibrated under independence relative to game-clustered" — is not an open hypothesis here, it is settled practice. The *result* is the finding: **team passing TD ↔ receiving TD +0.055 simulated against 1.000000 historical, exact in 3,230 of 3,230 team-games**; passing yards ↔ receiving yards **+0.334 against 0.9996**. This is the report's ninth-ranked item and it is our first. |
| 10 | Provenance, as-of timestamps, definition versioning | **ALREADY COVERED**, and more completely than the report describes | `nfl/capture/` carries content-addressed raw-before-parse capture, a first-seen ledger, `schema_fingerprint`, and **two accepted `pbp_participation` schemas** recorded by design (20 columns 2016–2022, 26 columns 2023–2025 — a strict superset). **Six clocks are kept separate and named**: `requested_at`, `retrieved_at`, `source_timestamp`, `probe_response_date`, `cache_timestamp`, `generated_at`, plus `effective_for_date` bound to the season and never derived from a file's own clock. `nfl_vintage/raw` holds content-hashed vintages. Standing rule: never treat final historical files as PIT vintages. The report ranks this **last on football relevance**; this project treats it as the floor everything else stands on, and had built it before the report was written. |

### 1.2 The report's TOP 5 OWNABLE DATA PRIMITIVES

All five are player-resolved tracking observations. There is **no tracking feed
in this project and no grant to one**; the report says so itself ("no such grant
is established by this technical audit").

| Primitive | Classification | Note |
|---|---|---|
| Route participation and blocking/release state | **RIGHTS BLOCKED** (and `CONTRACT_GATED`) | The FTN draft contract is unsigned; the FTN sample was **not unblinded** (ROUTE-BB1 §G). Prerequisite for the report's own item 1. |
| Alignment coordinates and role classification | **PARTIALLY COVERED / DATA BLOCKED** | ALIGN-B1 exists and its decision is **`DATA_INSUFFICIENT`** — the frozen taxonomy and classifier were delivered; the labels were not. The report explicitly says "Keep ALIGN-B1A frozen and evaluate it as supplied", which is the correct instruction and is already the state. |
| Player-resolved pre-snap motion and shift trajectories | **RIGHTS BLOCKED** | Requires raw pre-snap tracking. The report's own caveat — 19 motion types asserted publicly with no published definitions — is a reason not to buy an ontology, which agrees with ALIGN-B1's approach of freezing our own. |
| Route geometry and route family | **RIGHTS BLOCKED**, **LOW PRIORITY** | Downstream of a primitive we cannot obtain, for a conversion layer already measured `SIGNAL_WEAK`. |
| Separation and leverage windows | **RIGHTS BLOCKED**, **LOW PRIORITY** | Same. |

**One genuinely useful contribution in this section, and it is a caution not a
capability:** "Route and blocking indicators may both be true for a chip-and-release
player; forcing them into exclusive labels would lose the observation." That is
a good constraint to have written down *before* anyone builds the schema, and it
is consistent with ROUTE-BB1's finding that RB and TE are `NOT_IDENTIFIABLE`
precisely because the alternative assignment is invisible. Recorded.

### 1.3 The report's TOP 5 EXPERIMENTS and hypotheses H1–H7

| Item | Classification | Why |
|---|---|---|
| **Exp 1 / H1** — all-route denominator, predicted share | **DATA BLOCKED**, partly **ALREADY COVERED** | Denominator is already team dropbacks (§1.1 row 2). The all-route half needs item 1's input, which 404s for 2026. ROUTE-BB1 already measured what the *oracle* would be worth: at ρ = 0.10 the gain is **+10.29% CRPS [+0.0869, +0.0907]**; at ρ = 0.00 it is **−0.87%**. And the accounting ceiling: pooled **ρ_max 0.756**, with **23.9% of rows unreachable even at routes = pass_snaps**. So the value is bounded and known, not unknown. |
| **Exp 2 / H2** — dynamic role state vs season-to-date | **PARTIALLY COVERED**; baseline misdescribed | `ewma_hl2` is already an updating state. A change-point specification is a legitimate untried variant, but the headline contrast the report proposes has no baseline in this system. |
| **Exp 3 / H3** — as-of availability reallocation vs proportional renormalisation | **GENUINE GAP**, and the best experiment in the report | This is the sharpest, most correctly designed item the report contains: hold availability probabilities **fixed** and vary only the allocation mechanism, which cleanly isolates redistribution from injury forecasting. It maps to our own #3. Held behind cross-layer only because cross-layer is an exact identity violated in ~100% of draws by ~45% of the quantity, and this is a dependence understatement of 5.8× in a smaller quantity. |
| **Exp 4 / H4** — disjoint dropback terminal-state multinomial vs separate marginals | **ALREADY COVERED — the baseline it wants to beat does not exist here** | See §2. |
| **Exp 5 / H5** — two-stage measurement then forecast ablation; process-level charted constructs | **RIGHTS BLOCKED / CONTRACT_GATED** | Needs tracking or FTN. W2 §5 already measured what is reachable: **scramble rate reliability 0.670 [+0.382, +0.840]** on 47 QBs, but **sack given pressure 0.452 [+0.048, +0.722]** on 29 QBs — an interval that nearly touches zero. The process signal the report is chasing is, on our own measurement, weak where it matters. |
| **H6** — independence vs game-clustered interval coverage | **ALREADY COVERED** | Settled practice (C2). Not a hypothesis. |
| **H7** — definition-version mixing degrades forecasts | **ALREADY COVERED / NOT TESTABLE in the useful direction** | Version mixing is refused by construction (two accepted schemas, fingerprinted). We cannot run the contrast without deliberately building the defect. The report itself concedes an indistinguishable result would establish nothing. |

---

## 2. The clearest falsification: H4 describes a system we do not have

The report's experiment 4 and hypothesis H4 propose testing whether "a disjoint
multinomial over dropback terminal states outperforms **separate marginal
models** for attempts, sacks, and scramble rushes."

**There are no separate marginal models here.** `qb2_lib.simulate` draws the
terminal states as a sequential conditional binomial decomposition:

```
tot = max(pa + ps + psc, 1e-9); pa, ps, psc = pa/tot, ps/tot, psc/tot
SACK = rng.binomial(DB, ps)
rem  = DB - SACK
SCR  = rng.binomial(rem, psc / (pa + psc))
ATT  = rem - SCR
```

That is algebraically a `Multinomial(DB; pa, ps, psc)` — the standard chained
construction of one. The rates are normalised to the simplex before drawing, so
the partition is disjoint by construction. It closes exactly, and the closure is
enforced rather than assumed, in two places: `qb_v1.forecast` refuses
`QB_V1_INCOHERENT_DRAWS` if `att + sacks + scr > db` in any cell, and
`qb_v1.identity_check` refuses `QB_DROPBACK_IDENTITY_VIOLATED` on any inequality.

It also carries the comment recording *why*, which is the R1 lesson: drawing
`rint(DB × rate)` instead "gives a point value per draw and destroys the
binomial spread — sacks came back at **0.715** nominal-90 coverage and rush
opportunities at **0.724**."

So H4's candidate is the incumbent, its baseline was tried, measured to break
coverage, and rejected. The report's instruction for exactly this case is the
right one — "if it already implements the proposed capability, use a documented
removal/re-addition ablation rather than pretending the baseline is simpler than
it is" — and that ablation is already in the repository history.

**Where the report is nonetheless right in this section:** its accounting
taxonomy names spikes, kneels, penalties and nullified plays as requiring
declared treatment. `qb_v1` carries a `spikes` field and W2 §3.1–§3.6 establishes
the sentinel hazards (`pass_attempt` includes sacks; the QB is absent from
`passer_player_id` on 5.25% of dropbacks, which would bias dropbacks down ~5%;
sack yards are not passing yards). Penalty / nullified-play treatment is
declared nowhere I could find. That is a small open item, recorded, not urgent.

---

## 3. Where the report caught us — and it caught a defect I introduced last week

The report says, of yardage accounting:

> "receiving yards can accrue without a reception, so receptions times a
> per-catch construction is not a universal identity."

Last session I added `zero_receptions_implies_zero_yards` to
`NONQB_IDENTITIES` as a hard per-draw identity. I went to falsify the report's
claim and nearly published the wrong answer.

**The wrong answer, measured first.** In RC1's own frame, `recv.pkl`, 25,934
player-games: **0** have zero receptions with nonzero receiving yards. 82 contain
a lateral. Clean refutation of the report — and it is worthless, because
`build_recv.py` keys on `receiver_player_id`, so a player whose only receiving
yards came on a lateral **is not a row in that frame at all**. He is absent, not
zero. Reading that zero as evidence would have been this project's own most
expensive defect class, committed in the act of auditing someone else for it.

**The right answer, measured on raw pbp, 2020–2025 REG, 25,947 player-games:**

| | |
|---|---|
| lateral-reception plays | **82** |
| player-games receiving a lateral | **82** |
| of those, **never targeted themselves** (invisible to RC1's frame) | **13** |
| **player-games with 0 receptions and nonzero receiving yards** | **16** |
| rate | **6.17 per 10,000 player-games** |

**The report is correct and my identity is wrong as stated.** It is exact for
our *generator*, which resamples per-catch gains and cannot produce a lateral,
and it is false of realised football at 6.2e-4. The distinction matters when the
identity is used as a *validation* check against realised outcomes rather than as
an internal draw check — 16 player-games in six seasons would be scored as
defects of a forecaster that is behaving correctly, which is precisely what
CLAUDE.md's rule 6 forbids.

**Action taken: none yet, deliberately.** Changing an accounting identity is not
a change to make inside a reconciliation packet, and the fix is a one-line
documented exception rather than a loosening — the identity stays enforced on
draws, and gains a named realised-outcome exception mirroring the existing
`LATERAL_EXCEPTION` already carried by `qb_accounting.reconcile_cross_layer`.
Queued as a small, separately committed item.

**A second caution of the report's, tested and also correct:** "Do not impose
equality between total receiver targets and total pass attempts." Measured on
this project's 3,230 team-games: mean `pass_att − targets` = **3.7997**, median
4, max 13, and the two are equal in only **128 team-games (3.96%)**. Targets
never exceed attempts (**0** team-games). This project does not impose that
equality anywhere and never did — but the gap is now quantified, and any future
cross-layer identity must use **targeted attempts**, not attempts.

---

## 4. Where the report is wrong, or at least unearned

1. **Its priority ordering is inverted relative to the measurements.** It ranks
   route/block/release state **first** and predictive dependence structure
   **ninth**. Route participation is blocked on an input that returns **404 for
   2026**, and its oracle ceiling is already measured. Dependence structure is
   where a hard identity is currently violated in **~93–100% of draws by ~45% of
   the quantity**. The report says its own table is "analyst judgments about
   research order, not measured expected value," which is exactly the right
   disclaimer — and exactly why it should not reorder our queue.

2. **"Whether the existing system does X is not established"** is used ten
   times, and in seven of those ten cases it *is* established, in this
   repository, with numbers. That is not the report's fault — it was not given
   the artifacts — but the correct disposition of an unestablished-therefore-
   audit item is to run the audit, which is what this document is, and then let
   the finding replace the recommendation.

3. **Its evidence base is largely vendor marketing and single papers with
   mismatched estimands**, and it says so with unusual candour: the DFS coverage
   result is about *opponent lineup composition*, not player performance; the
   expected-points coverage result is a *drive-outcome class*, not a player-week
   interval; PFF's R² = 0.41 is *persistence*, not transition. After those
   caveats are applied, almost none of the cited evidence supports a forecasting
   claim at our estimand. The report is honest about this. The consequence is
   that it supplies **framing**, not evidence.

4. **It recommends re-running an experiment we closed on a stated rule.** Item 8
   is another same-input estimator ladder over receiving efficiency; RC1's
   acceptance decision names exactly that as the thing that will not reopen it.

---

## 5. What the report is worth keeping

Three things earn their place and are recorded as project constraints:

1. **The lateral exception at player-game grain** — §3, with a measured rate.
2. **Targets sum to targeted attempts, not attempts** — §3, with a measured gap
   of 3.80 per team-game. Load-bearing for the cross-layer work starting now.
3. **The three-way availability split** — participation uncertainty, the
   distribution conditional on playing, and in-game exit are three channels and
   this system carries one binary. Named here for the first time.

Two more are correct restatements of things we already enforce, and it is
reassuring rather than informative that an outside reader arrived at them:
routes across players need not sum to one on a dropback, and a QB passing TD
with its receiver's receiving TD is **one score with two player credits**, which
is precisely why `reconcile_cross_layer` compares team sums and why the
**1.000000, 3,230-of-3,230** historical identity is the benchmark our simulator
misses at **+0.055**.

---

## 6. Verdict on the ordering question

**Cross-layer passing ↔ receiving stays first.** Nothing in the report is
demonstrably larger. Revised queue, unchanged in order, with the report's
contributions folded in:

1. **Cross-layer passing ↔ receiving.** An exact identity, violated in ~100% of
   draws by ~45% of the quantity, with a written guard already waiting and now
   fed. The report agrees this must hold and adds two accounting constraints
   (§5.1, §5.2) that the architecture must respect.
2. **Opposing-team dependence.** Needs a game-level play-budget object that does
   not exist. Report item 5 confirms independently.
3. **Within-team player dependence / role-aware reallocation.** Report
   experiment 3 is the best-designed item it contains and should be adopted as
   the shape of this work when it is reached.
4. Lateral exception on the receiving identity (small, from §3).
5. P5A rectification (retained).
6. QB3b week-1 incumbency (retained).

Governance unchanged: A3 remains enabled in rehearsal and **not promoted**; QB3
remains `REHEARSAL_ONLY` and **not promoted**; `PATH_C_STATE.json` untouched;
G0A **11/12**; NFL-1 **NOT AUTHORIZED**; no 2026 outcomes consumed; no market,
DFS, or restricted-vendor input read.

Proceeding to the cross-layer architecture.
