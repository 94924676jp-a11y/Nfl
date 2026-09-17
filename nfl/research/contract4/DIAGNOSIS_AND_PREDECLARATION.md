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
4. The quantity **CLEARS** at that draw count when `a >= 0.90` — at least 18 of
   20 batches agree on the same integer.
5. When it does not clear, report the **modal value and its runner-up with
   their counts**, so a reader sees `15 ×11, 16 ×9` rather than a distance.
6. A quantity whose two top values are **adjacent integers** and whose modal
   agreement is below 0.90 at every draw count on the grid is recorded
   **`INTRINSICALLY_TIED`** — the quantile sits on an atom boundary and no draw
   count resolves it. That is a **property of the forecast, not a failure of
   convergence**, and it is reported as such rather than as a failing check.

**0.90 and B = 20 are declared here, before the contract is run, and are not
chosen against a result.** B = 20 matches the existing `N_BATCHES` in
`draw_contract3.py`; 0.90 is the same 18-of-20 agreement its `BATCH_AGREEMENT`
constant already uses, so neither is a new number in this project.

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
