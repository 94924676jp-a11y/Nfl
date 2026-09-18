# Contract 3 is unattainable for an integer quantile, and the reason is not noise

**Contract 3 is NOT amended.** Its verdict on every arm run so far stands as
recorded: `chosen: null`. This file diagnoses *why* it cannot be met for one
class of quantity, classifies the engine's outputs by **mathematical support**
rather than by observed cardinality, and pre-registers **Contract 4** for the
discrete class only.

---

## 1. The diagnosis, measured

Contract 3 asks a single question of every quantity: resample the sealed draws,
recompute the quantile, and require its bootstrap sd below a native-unit
threshold — 1.0 for yards, **0.25 for counts**, 0.25 for DK, 0.01 for
probabilities.

The binding quantity on the QBSEM arm at 8,000 and 16,000 draws is
**`qb/cmp` p10 for Jared Goff**. Bootstrap sd, R = 400, same seed, four draw
counts:

| draws | boot sd | support of the bootstrap quantile | threshold |
|---|---|---|---|
| 2,000 | 0.4126 | 15 ×312, 16 ×83 | 0.25 |
| 4,000 | 0.4526 | 15 ×283, 16 ×109 | 0.25 |
| 8,000 | 0.4977 | 16 ×201, 15 ×189 | 0.25 |
| 16,000 | **0.5004** | **15 ×200, 16 ×199** | 0.25 |

**The sd rises with n and converges to 0.5.** It does not fall at all.

The bootstrap p10 takes exactly **two adjacent integer values, 15 and 16**, and
as the draw count grows the split converges to 50/50 — because the true p10
sits on the boundary between two atoms. For a two-atom statistic the sd is
`sqrt(p(1-p)) × 1`, which is **0.5 at an even split and has no n in it.**

> **More draws do not reduce this. They resolve the tie more precisely onto the
> boundary and make it worse.** A 0.25 threshold requires a split more lopsided
> than about 93/7; nothing about the forecast can be asked to deliver that.

Contrast the same run's `qb/pyds` p90, which *is* converging:
3.6255 → 2.8013 → 1.7940 → 1.4764 across 2k → 16k, close to the 1/sqrt(n) that
Monte Carlo error predicts. **Contract 3 is the right instrument for that
quantity and the wrong instrument for the one beside it.**

### The irony that has to be recorded

`qb/pyds` is testable by a continuous threshold **only because of a defect**.
`football_engine.credit_passing_line` splits team passing yards among a team's
quarterbacks by a continuous completion share:

```
pyds_q = np.where(Ki > 0, cmp_q / denom * Y, 0.0)
```

so a quarterback's passing yards are a *fraction of a team total*, not a sum of
integer yards. Measured on the GSVU board: `qb/pyds` non-integer in **5,594 of
32,000** cells (17.48%), `qb/ryds` in 5,760 of 32,000 (18.00%), with fractional
parts that are exactly the `k/n` completion-share denominators.

**Integerising yards — which §4 says is right — would move `qb/pyds` from the
continuous class into the discrete class, and Contract 3 would then be
unattainable for it too.** Fixing the support defect makes *more* of Contract 3
unmeetable, not less. That is a reason to classify by support first and choose
the instrument second, which is what this file does.

---

## 2. Classification by mathematical support, not observed cardinality

Measured over every draw array on the DET–BUF GSVU board, 8,000 draws.

| class | support | arrays | instrument |
|---|---|---|---|
| **integer count** | `{0, 1, 2, …}` | `rushing/carries`, `receiving/targets`, `receiving/receptions`, `qb/att`, `qb/cmp`, `qb/db`, `qb/sacks`, `qb/scr`, `qb/int`, `qb/ptd`, `qb/rtd`, `qb/rush_opp`, `receiving/receiving_td`, `rushing/rushing_td`, `kicking/fga`, `kicking/fgm`, `kicking/xpa`, `kicking/xpm`, `team_volume/team_carries`, `team_volume/team_targets`, `team_volume/team_off_snaps` | **Contract 4** — modal agreement / batch stability |
| **integer count, CURRENTLY EMITTED FRACTIONAL** | should be `{0,1,2,…}` | `qb/pyds`, `qb/ryds`, `rushing_total/rushing_yards` | repair first (§4), then Contract 4 |
| **continuous level** | `[0, ∞)`, never rounded at source | `team_volume/team_dropbacks_part`, `team_volume/team_rz_carries` | Contract 3 as written |
| **lattice** | multiples of 0.02 once yards are integral | `dk_scoring/dk_points` | Contract 4 on the lattice step |
| **probability** | `[0, 1]` | every `thresholds[].p`, `touchdown.anytime` | Contract 3, threshold 0.01 |
| **zero-inflated / atomic mixture** | `{0} ∪ support` with an atom at 0 | every player quantity whose `P(=0) > 0` — on this board 27 of 29 rows | **neither, alone** — see §3 |

**Two arrays that look like counts are not.** `team_volume/team_dropbacks_part`
and `team_rz_carries` are **100% non-integer by design** — continuous levels
that downstream consumers `rint`. They must never be scored as counts, and the
present contract does not distinguish them.

**`receiving/receiving_yards` and `rushing/rushing_yards` are already all-integer.**
The fractional-yard defect is confined to the QB layer and what inherits from it.

---

## 3. Contract 4 — pre-registered, for the discrete class only

**Scope: integer-valued quantiles only.** Contract 3 continues to govern
continuous levels and probabilities, unamended.

For an integer quantile `q` of a quantity with integer support:

1. **Batch the sealed draws into B = 20 disjoint batches** of equal size, in
   draw-index order. No resampling: bootstrap resampling of a discrete
   statistic is what produces the 0.5 floor above.
2. Compute the quantile within each batch. Each is an integer.
3. **MODAL AGREEMENT** `a = (count of batches equal to the modal value) / B`.
4. The quantity **CLEARS** at that draw count when `a >= 0.95` — at least
   **19 of 20** batches agree on the same integer.
5. When it does not clear, report the **modal value and its runner-up with
   their counts**, so a reader sees `15 ×11, 16 ×9` rather than a distance.
6. A quantity whose two top values are **adjacent integers** and whose modal
   agreement is below 0.95 at every draw count on the grid is recorded
   **`INTRINSICALLY_TIED`** — the quantile sits on an atom boundary and no draw
   count resolves it. That is a **property of the forecast, not a failure of
   convergence**, and it is reported as such rather than as a failing check.

**CORRECTION OF RECORD, 2026-09-17, BEFORE THIS CONTRACT HAS RUN.**

This section originally read:

<!-- SUPERSEDED-BEGIN withdrawn 2026-09-17 at 340d581: this wording relaxed a standing 0.95 to 0.90 while asserting it was the same number. Quoted verbatim, never deleted. The markers are HTML comments and change no rendered word; they exist so a checker can tell live prose from a quotation of withdrawn prose without judging it. -->
*"The quantity CLEARS when `a >= 0.90` — at least
18 of 20 batches agree... B = 20 matches the existing `N_BATCHES` in
`draw_contract3.py`; 0.90 is the same 18-of-20 agreement its `BATCH_AGREEMENT`
constant already uses, so neither is a new number in this project."*
<!-- SUPERSEDED-END -->

**That was wrong.** `nfl/tools/draw_contract3.py:28` reads
`BATCH_AGREEMENT = 19`, and its test at line 129 is `n_mode >= BATCH_AGREEMENT`.
The existing constant is **19 of 20, which is 0.95**. `B = 20` does match the
existing `N_BATCHES`. **The agreement threshold did not.** The pre-declaration
relaxed a standing 0.95 to 0.90 *while asserting that it was the same number*.

It was an error of recollection and not of intent, and that makes no difference
to how it must be handled. A threshold loosened by a factor the document claims
is not a change is indistinguishable in effect from one loosened deliberately,
and the rule against weakening a gate has no exception for accidents.

**The threshold is 19 of 20, `a >= 0.95`, matching `BATCH_AGREEMENT`.** It is
corrected here **before the contract has run even once**, so no result is being
reinterpreted. <!-- SUPERSEDED-BEGIN not a threshold statement: this sentence FORBIDS the withdrawn number rather than declaring it. Marked so a checker does not read a prohibition as a declaration. -->If a case for 18 of 20 ever exists it must be argued on its own
merits and pre-registered as a new number, never as precedent.<!-- SUPERSEDED-END -->

Found by external review (Perplexity, against HEAD `887f4f2`) and verified
against source before adoption.

**B = 20 and 0.95 are declared here, before the contract is run, and are not
chosen against a result.** Both now match `draw_contract3.py` exactly.

### FINAL PRE-EXECUTION SPECIFICATION, 2026-09-17

Six items must be complete before Contract 4 runs. It has **not** run.

**1. Metric-kind registry coverage.** Classification is driven by
`nfl.product.metrics.SUPPORTED`, never by a table in this file — the reasoning
`draw_coherence.py` already applies when it derives `COUNT_ARRAYS` from that
registry rather than hardcoding a tuple. **Measured at HEAD: `SUPPORTED` holds
17 entries, 14 of kind `count` and 3 of kind `yards`, with no `probability`
kind, no `lattice` kind and no `dk_scoring` entry at all**, while the board
emits 54 matrices across 10 layers. **Contract 4 cannot run until every emitted
array carries a declared kind.** A quantity whose kind is undeclared is
`UNCLASSIFIED` and counts against coverage; it is never guessed from dtype,
because `rushing/carries` is int-typed nowhere and `qb/pyds` is float and
declared yards.

**2. CDF-at-atom is the PRIMARY criterion for discrete quantiles.** Modal
agreement is retained only as a secondary report.

For an integer quantity at level `q`, the published quantile is the smallest
integer `k` with `F(k) >= q/100`. **The quantile is an integer and cannot
converge. `F(k)` is a probability, converges at `1/sqrt(n)`, and can.** So
estimate `F(k-1)` and `F(k)` with Monte Carlo standard errors and classify:

| verdict | condition |
|---|---|
| **DETERMINED** | `F(k-1) < q/100 <= F(k)` with both intervals excluding `q/100` |
| **INTRINSICALLY_TIED** | an interval around `F(k)` or `F(k-1)` contains `q/100` and **narrows with n** — the level sits on an atom boundary |
| **NOT_YET_CONVERGED** | the standard errors are still too wide to decide |

Three reasons this replaces the instability test. It uses a **convergent**
statistic, so more draws always help, where modal agreement got *worse* with n
(0.4126 → 0.5004). It **separates "on a boundary" from "under-sampled"**, which
modal agreement provably cannot, since both present as two adjacent values
failing at every grid point. And it reuses Contract 3's existing probability
threshold of **0.01** rather than inventing an instrument.

**3. Coverage semantics, and `INCOMPLETE`.** Contract 4 publishes the fraction
of in-scope quantities in **each** terminal state. Below a declared minimum
certified fraction the overall verdict is **`INCOMPLETE`**, never a pass.

> **An overall PASS while most rows are DEGENERATE, UNCLASSIFIED or
> INTRINSICALLY_TIED is FORBIDDEN.** A contract satisfiable by having almost
> nothing in scope is not a gate. On the DET-BUF board **27 of 29 player rows
> are zero-inflated**, so this is the live risk, not a hypothetical one.

**4. Zero-inflated quantities are graded in two parts, now.** Not deferred.
The atom mass `P(X = 0)` is a **probability** and is graded under Contract 3 at
threshold 0.01. The conditional positive part `X | X > 0` is graded by its own
support class. A quantile falling **inside** the zero atom is
`DEGENERATE_AT_ZERO` — neither passing nor failing — and counts against
coverage under item 3.

**5. `dk_points` is EXCLUDED from modal agreement.** DK points is a weighted sum
of many components on a fine lattice, taking hundreds of attainable values, so
its quantile behaves essentially continuously. Modal agreement across 20 batches
on a support that fine approaches zero **for reasons unrelated to convergence**,
guaranteeing failure for every arm regardless of forecast quality. It is graded
as continuous under Contract 3, or by the CDF criterion in item 2. **Contract 4
is reserved for coarse integer supports where modal agreement means something.**

**6. Exchangeability of the batching must be tested, not assumed.** Batching is
contiguous in draw-index order, which assumes the draw index is exchangeable.
The artifact records `seed_protocol` as `"per-row seed 20260908"` and **whether
contiguous blocks of that stream are exchangeable is UNKNOWN.** The contract
computes modal agreement under contiguous blocks **and** under a declared random
permutation of the index, and the two must agree within sampling error. If they
do not, contiguous batching is biased and the permuted form governs.

### A conservatism that must be declared, not hidden

Batching splits `n` draws into 20 blocks, so each batch quantile is computed on
`n/20` draws — **400 at n = 8,000**. The contract therefore grades the stability
of a 400-draw quantile while the board publishes the 8,000-draw one. A **pass**
is trustworthy, since stability at 400 implies stability at 8,000. A **failure
is not diagnostic**, and could push a genuinely stable quantity into a terminal
state that reads as a property of the forecast. **The full-sample quantile is
therefore reported beside every batch verdict**, so a reader sees what is
published next to what was graded.

### The zero-inflated case, stated and NOT solved here

A quantity with an atom at zero is not one distribution. When `P(=0)` exceeds
`1 - q/100`, the `q`th quantile **is** zero and is perfectly stable for a
reason that has nothing to do with convergence — the DET–BUF backups' `qb/pyds`
p90 is exactly 0.00 with bootstrap sd 0.0000 because their `P(pyds=0)` is
0.9086. **Reporting that as stability would be false.** Contract 4 therefore
records, beside every discrete verdict, whether the quantile falls inside the
zero atom, and a quantity in that state is **`DEGENERATE_AT_ZERO`**, neither
passing nor failing. A separate contract for the mixture — the atom mass and
the conditional distribution scored apart — is **owed work and is not
pre-registered here.**

---

## 4. The support repair, owed and not done here

`qb/pyds` and `qb/ryds` must be dealt as integers at the generative source, not
rounded at the boundary — rounding after the fact would break the closure that
`credit_passing_line` refuses rather than clips. The natural construction is
the one the module already uses for completions and touchdowns: a
**multivariate hypergeometric deal of the team's integer yards** among the
quarterbacks who completed passes, which sums to the team total by
construction.

**That is a mechanism change, it takes a new candidate identity, and it is not
attempted in this pass.** It is recorded here with its consequence: once done,
`qb/pyds` joins the discrete class and must be judged by Contract 4.

---

## 5. What is NOT claimed

- No statement that any arm's convergence improved. Contract 3's verdicts stand.
- No threshold in Contract 3 is moved, and its grid is not extended.
- Contract 4 has been **pre-registered and not yet run**. Until it runs, no
  quantity has cleared it.

**V2 NOT YET EARNED**
