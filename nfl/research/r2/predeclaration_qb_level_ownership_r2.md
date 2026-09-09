# `QB_LEVEL_OWNERSHIP_R2` — pre-registration

**Written under OWN-5 Part C. Nothing here is implemented and nothing is
scored.** The owner's instruction is explicit: *"Do not score R2 or implement it
in this task."* This file exists so that when R2 is authorised, the design is
already fixed and cannot be chosen after seeing a number.

**Why R2 exists.** OWN-4 established that `qb2_lib.simulate` draws `V` — the team
dropback volume — from the team-dropback pool and `S` — the quarterback's share —
from the share pool, then sets `DB = rint(V × S)`. Those are the two quantities
**D1 and QB3 already own**. `run_game` reconciles the duplicate by division,
`fac = target / drawn`. OWN-4 repaired the symptom — a zero denominator erasing
allocated opportunity — with a donor draw. **R2 removes the cause.**

---

## 1. Ownership, as R2 fixes it

| quantity | sole owner under R2 | today |
|---|---|---|
| **team dropbacks** | **D1** `team_dropbacks_part` | D1, and also QB V1 as `V` |
| **per-QB dropback allocation** | **QB3** `share_j`, summing to 1 per draw | QB3, and also QB V1 as `S` |
| **terminal-state conditional rates** — `p(sack\|db)`, `p(scramble\|db)`, `p(cmp\|att)`, `p(td\|cmp)`, `p(int\|inc)`, `p(designed\|db)` | **QB V1**, and nothing else | QB V1 (correct today) |
| **per-completion yardage, per-rush yardage** | **QB V1**, resampled | QB V1 (correct today) |
| **the composition** | multiplies the level by the rates; owns no level and no rate | divides one level by another |

**R2's single rule: QB V1 never draws a level.** It supplies conditional rates
only. The level is `target_j = team_dropbacks_part × share_j`, and the terminal
states are generated at that level.

---

## 2. The integer problem, stated before it is solved

The terminal-state cascade is binomial, so it needs an **integer** number of
trials. Exact team closure — `Σ_q db_q == team_dropbacks_part` per draw — is
today achieved because the composition emits **floats**. These pull in opposite
directions and R2 must choose. The choice is declared here.

**Declared: integerise AFTER allocation, by a per-draw largest-remainder
apportionment of the team's integer dropback budget across its quarterbacks.**

1. `N_t = rint(team_dropbacks_part_t)` — one integer team budget per draw.
2. Apportion `N_t` across that team's quarterbacks by `share_j` using
   **largest remainder** (Hamilton). Every `n_{j}` is a non-negative integer and
   `Σ_j n_j == N_t` **exactly, by construction, in every draw**.
3. Run the existing cascade at `n_j` trials.

*Why after, not before.* Integerising each quarterback independently
(`rint(share_j × N_t)`) does not sum to `N_t` — the rounding residual is exactly
the silent mass loss OWN-4 exists to prevent. Largest remainder distributes the
residual to the largest fractional parts and closes exactly. It is deterministic,
introduces no parameter, and its tie-break is declared: **ties broken by
descending `share_j`, then by `gsis_id` ascending**, so it is reproducible.

*What is given up, and it is stated rather than discovered later.* Team dropbacks
become integers, so `Σ_q db_q == rint(team_dropbacks_part)` rather than the float
`team_dropbacks_part`. **The invariant changes from float-exact to
integer-exact**, and the difference is at most 0.5 dropbacks per team-draw. R2
must not be reported as preserving the current invariant; it replaces it with a
different one that is arguably more physical, since a dropback is a countable
event.

---

## 3. Invariants that must remain exact

1. `Σ_j n_j == N_t` in every draw, every team — **by construction**.
2. `att + sacks + scr == db` in every draw — the QB dropback identity.
3. No allocated mass disappears: `share_j > 0` must yield a modelled state, or a
   **named refusal**. The OWN-4 donor mechanism becomes unnecessary under R2 —
   there is no denominator to be zero — and must be **removed, not left dormant**.
   A guard that can never fire is not a guard; this project has found three.
4. C3 shared-pass closure: completions, passing yards and passing touchdowns
   agree between layers in every draw.
5. Rushing: no double counting of scrambles and designed runs;
   `rush_opp == designed + scrambles` by construction.
6. Zero carries implies zero rushing yards; negative rushing outcomes allowed.
7. No clipping, no survivor renormalisation, no post-hoc overwrite.

## 4. Stochastic uncertainty that must be preserved

- The binomial spread of every terminal state. R1's lesson stands: `rint(DB ×
  rate)` gives a point where a distribution belongs and broke coverage to
  **0.715** (sacks) and **0.724** (rush opportunity). R2 draws, never rounds a
  product.
- Per-completion and per-rush yardage stay **resampled**, never a point rate.
- Between-draw variation in the level, which under R2 comes from D1 and QB3
  rather than from QB V1's own pool — a *transfer* of the variance source, not a
  removal, and the comparison in §5 must show what it does to the spread.

## 5. Comparator

**Same seed, same slate, same draws, against current OWN-4.** Report:

| quantity | requirement |
|---|---|
| team dropback closure | integer-exact under R2; float-exact under OWN-4; both reported |
| max per-draw shortfall | must remain **0** |
| per-QB dropback distribution | mean, sd, p05, p50, p95 — the transfer of variance quantified |
| terminal-state closure | 0 violating cells |
| C3 identities | 0 violating draws |
| coverage of sacks, scrambles, rush opportunity | must not regress from OWN-4 |
| donor mechanism | must be **unreachable** under R2 and removed |

**Declared in advance:** R2 is preferred **only if** it holds every invariant in
§3 and does not widen any terminal-state interval relative to OWN-4. If it
merely relocates the level's variance without improving closure or coverage, the
simpler incumbent stands — OWN-4 already conserves mass, and R2's case rests on
removing the duplicate ownership, not on a score.

## 6. What R2 is not

- Not a change to QB3's shares or to D1's volumes.
- Not a new estimator. No parameter is fitted anywhere in R2.
- Not a promotion. Development evidence may reject it; it may never promote it.

## 7. Order of execution when authorised

1. Re-verify this file's sha256 against its commit.
2. Implement the largest-remainder apportionment and the rate-only QB V1 path.
3. Invariants in §3 as gates — pass/fail, never traded.
4. Comparator in §5, same seed.
5. Remove the OWN-4 donor mechanism and prove it unreachable.
6. Report, including everything that disagrees with this file.
