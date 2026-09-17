# CS1 result — the refresh applied, and it moved the quantity QBSEM could not

`V1_CANDIDATE_R9_W1P_GSVUC` against `V1_CANDIDATE_R9_W1P_GSVU`, 8,000 draws,
seed 20260908, `written_at` 2026-09-16T15:45:14Z, game `2026_02_DET_BUF`, same
checkout, one declared component apart.

**Components applied: A1, A3G, C0, C3, CS1, R2, R5, R6, R8, R9, SC1, SC2.
Not reached: none.**

**Nothing is sealed and nothing is promoted.**

---

## 1. Refreshed inputs

| source | blob | retrieved | coverage |
|---|---|---|---|
| play-by-play | `pbp_2026.1415dd98ba7f701a.csv.gz` | 2026-09-14T00:25:56Z | 10 games, **20 clubs** |
| snap counts (proxy) | `snap_counts_2026.4da350a50d0bb39b.csv.gz` | 2026-09-14T18:33:36Z | **+10 clubs** |
| roster identity bridge | `weekly_rosters.*raw.csv` | — | 1,986 ids, **0 unresolved** |

35 rows, 30 clubs, **missing = exactly DEN and KC**, which keep the frozen
answer and are named. `panel_p3.csv.gz` is unchanged and unread-from-disk-anew:
the rows are appended in memory only when a caller asks.

## 2. DET–BUF state, before and after

| club | before | after |
|---|---|---|
| BUF | `00-0033869`, ord **202518**, opener **True**, `defect_id` set | **`00-0034857` (Josh Allen)**, ord **202601**, opener **False**, `defect_id` **None** |
| DET | `00-0033106`, ord **202518**, opener **True** | `00-0033106`, ord **202601**, opener **False**, `defect_id` **None** |

30 of 32 clubs changed state league-wide.

## 3. The projection deltas caused by the refresh alone

**Conservation holds exactly in both arms**: `sum_i db_i == team dropbacks` in
**8,000 of 8,000** draws on both clubs, worst integer deviation **0**.

### The QB room

| QB | mean db GSVU → CS1 | **P(db = 0) GSVU → CS1** | DK Δ |
|---|---|---|---|
| Josh Allen | 34.6857 → 32.9454 | **0.003875 → 0.044000** | **−1.1454** |
| Jared Goff | 34.9415 → 33.0429 | **0.003000 → 0.045125** | **−0.9079** |
| Kyle Allen | 1.7361 → **3.4765** | 0.763375 → 0.723250 | **+0.9132** |
| Joshua Dobbs | 1.6923 → **3.5909** | 0.762500 → 0.720375 | **+1.0639** |

> **This is the quantity QBSEM was built to move and could not.** Josh Allen's
> zero-dropback mass rises **elevenfold**, from 0.0039 to 0.0440, against his
> cell's realised **0.0694** — and it does so with no change to the QB room's
> mechanism at all. QBSEM attacked the room's relief rate; the cause was
> upstream state, and correcting the state moved the number an order of
> magnitude further than QBSEM did.
>
> **It does not close the gap.** 0.0440 against 0.0694 leaves a residual, and
> that residual is the starter renormalisation already identified in
> `nfl/research/qbsem/QBSEM_RESULT.md` §1. **QBSEM remains withdrawn and is not
> re-run here.**

### Everything else

Every non-QB row moves by **less than 0.13 DK**. Largest: Gibbs −0.1266,
Ray Davis +0.1219, Keon Coleman −0.1101.

**The effect is NOT confined to the QB room, and that is expected rather than a
leak.** `receiving/targets`, `receiving/receiving_yards`, `rushing/carries` and
`team_volume/team_targets` all move, because C3 derives the team target budget
from the throw process, so a different QB allocation deals a different budget.
`team_volume/team_carries` is **bit-identical**, which is the check that the
propagation runs through the passing path and not through something it should
not touch.

## 4. The p90 instability numbers, and why two of them ROSE

| QB | `qb/pyds` p90 bootstrap sd, GSVU → CS1 |
|---|---|
| Josh Allen | 2.2403 → **2.0051** |
| Jared Goff | 2.5158 → **2.3186** |
| Joshua Dobbs | 1.4712 → **6.2034** |
| Kyle Allen | 1.8408 → **5.6759** |

**The two large rises are the zero atom lifting, not instability appearing.**
Under GSVU the backups' `P(pyds = 0)` was 0.8081 and 0.8084 and their p90 sat
inside the zero atom, where the statistic is nearly constant and its sd is
small for a reason that has nothing to do with convergence. Under CS1 their
participation rises, `P(pyds = 0)` falls to 0.7670 and 0.7694, and the p90
leaves the atom and becomes a real quantile with real spread.

**A smaller sd was the worse state.** This is exactly the `DEGENERATE_AT_ZERO`
case pre-registered in `nfl/research/contract4/`, and it is the second time in
this work that a bootstrap sd of near zero has meant degeneracy rather than
stability. The starters', which were never degenerate, both fell.

## 5. What is NOT claimed

- **No proper-score comparison exists for this board and cannot.** DET–BUF
  kicks off 2026-09-18T00:15Z and has not been played, so there is no outcome
  to score. Brier, log loss, coverage and the clustered baseline delta are
  computable only forward-chained on history or prospectively after the game.
  **CS1 is therefore UNPROVEN on proper scores, and saying otherwise would be
  fabricating a comparison.**
- **No claim that CS1 forecasts better.** It feeds the model the state that is
  true instead of one nine months stale. Whether truer state forecasts better
  is an out-of-sample question, and the honest test is a forward-chained replay
  of weeks 2–18 across past seasons with the current-season panel withheld.
  Not run here.
- **QBSEM is not revived.** No QBSEM arm was run under this candidate.
- **Contract 3 is untouched.**

**V2 NOT YET EARNED**
