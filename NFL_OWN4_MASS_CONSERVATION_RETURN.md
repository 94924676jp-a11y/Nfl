# OWN-4 — QB draw-level mass conservation

**Mission:** the remaining 0.0518% mean loss, treated as a composition defect.
First question from the ruling: *why is a raw level draw being used as the
denominator of a quantity whose level is already owned by QB3 allocation?*

**The answer is that it is the same defect as XL1 and OWN-1, a third time.**

`qb2_lib.simulate` draws **`V` — the team dropback volume — from the team-dropback
pool, and `S` — the quarterback's share of it — from the share pool**, then sets
`DB = rint(V × S)`. Those are exactly the two quantities **D1 and QB3 already
own**. The composition in `run_game` then reconciles the duplicate by division:
`fac = target / drawn`.

**The zero-denominator behaviour is not an edge case. It is the signature of two
layers owning one level.** When QB V1's independently drawn level happens to be
zero, the ratio is undefined and the opportunity QB3 causally allocated is
destroyed.

**Repaired, deterministically, with nothing fitted.** Max per-draw shortfall
**37.71 dropbacks → 0.0000000000**. Team dropback closure **0.862 → exactly 0.0**.

---

## 1. Causal ownership, established

| quantity | who owns it | who was also drawing it |
|---|---|---|
| team dropback budget | **D1** `team_dropbacks_part` | QB V1, as `V` from the team-dropback pool |
| per-QB dropback level | **QB3 allocation** `share_j` | QB V1, as `S` from the share pool |
| sack / scramble / throw split | **QB V1** — correctly, as a chained multinomial | — |
| completion, yards, TD, INT, rushing | **QB V1** — correctly, as rates on the level | — |

Everything below the level is a **rate applied to it**, and every one of those
rates (`ps`, `psc_c`, `pc`, `ptd`, `pint`, `dpd`) is a **row-level scalar**; only
the per-completion yardage is a per-draw vector. QB V1's rate model is sound and
is not in question. What it should not be doing is drawing the level.

---

## 2. The repair, and why it needs no estimator

Because the rates are row-level scalars, **any non-zero draw of a row carries the
same rates as any other draw of that row**. So a cell whose own level draw is
zero can borrow a **donor draw from the same row** and be scaled to the allocated
target — reproducing exactly what the composition would have done had the level
draw not been zero.

`qb_accounting.conserve_allocated_mass(target, drawn, seed_parts)` returns a
source index per draw:

- unaffected cells **map to themselves**, so their composition is bit-for-bit
  unchanged;
- a cell holding allocated opportunity with a zero level draw borrows a donor
  from the same row;
- a row with **no** non-zero draw anywhere has nothing to borrow and the caller
  **refuses** — `QB_COMPOSITION_NO_DONOR_DRAW`.

Nothing fitted. Nothing clipped. No post-hoc overwrite. No survivor
renormalised. QB3's shares untouched. Terminal-state uncertainty preserved,
because the donor is a real draw and different cells draw different donors.
Per-QB attribution preserved, because the donor comes from **that quarterback's
own row** and never from another player.

On the live slate every affected row had a donor, so the refusal did not fire —
but it is implemented and tested, because a slate where it fires is possible and
the invariant permits refusal, never silent loss.

---

## 3. Gates

| gate | before | **after** |
|---|---|---|
| QB allocation share closure | 5.3168% lost, 23/32 teams | **PASS — 0.000000%, 0 teams** |
| **team dropback closure, per team per draw** | **FAIL — max abs diff 0.862** | **PASS — max abs diff 0.0, 16 team-games** |
| **zero silent mass loss** | 0.0518% mean, **37.71 in one draw** | **PASS — max per-draw shortfall 0.0000000000; total −0.0 of 119,372.62** |
| QB terminal-state closure | PASS | **PASS — 0 of 5,800 cells** |
| no alteration to unaffected draws | — | **PASS — 0 differences in 924 field comparisons, 84 quarterbacks** |
| no new hidden fallback | — | **PASS** — the only new path is a named refusal |
| suite | 2,593 checks | **42 modules, 448 functions, 2,607 checks, 0 failing** |

The repair fired on **3 cells across 3 row-instances** in 8 games at m=200, and
on **20 cells of 47,600** across the full slate at m=400.

**Tail diagnostic, as required.** The mean was never the point: before the
repair the worst single draw lost **37.71 allocated dropbacks** — an entire
team's passing game for that draw — against a mean loss of 0.0518%. After, the
maximum per-draw shortfall over 16 team-games and 200 draws is
**0.0000000000**.

### Outstanding

**C3 shared-pass closure has not been re-verified under this repair.** XL1
established those identities hold **by construction** — completions, passing
yards and passing touchdowns are generated once — and the repair changes only
which draw a QB's fields are composed from, not how C3 constructs them. That is
a reason to expect them to hold, not evidence that they do. Re-running the XL1
C3 arm under OWN-4 is queued and is compute, not a finding.

---

## 4. The deeper repair I did not take

The donor mechanism removes the **symptom**. The **cause** is that QB V1 draws a
level it does not own.

**R2 — remove the level draw entirely.** Let the composition set `db := target`
from D1 × QB3 and generate the terminal-state cascade at that level with the
row's existing rates. There would then be no denominator, no division and no
zero to repair, and the duplicate ownership would be gone rather than
reconciled.

**I did not do it, and the reason is not caution.** R2 changes **every**
quarterback's draws, not only the 20 affected cells, so it violates the
constraint that unaffected draws not move. It also has a real design tension: the
binomial cascade needs an integer level, while exact team closure currently
relies on the composition producing floats. That is a genuine architectural
question with more than one defensible answer, so under the ruling it needs its
own pre-registration before anything is scored — not a decision taken inside a
defect fix.

Recorded as the successor to OWN-4, with the ownership table in §1 as its
evidence.

---

## 5. Rushing gate

Classified as the ruling directs:

**`PREEXISTING_SYSTEM_GATE_FAILURE_OUTSIDE_OWN3_CAUSAL_SCOPE`**

`rushing` fails in 8 of 8 games under **both** arms and `qb_team_volume` is
4 PASS / 4 FAIL under **both** — the R4-recorded boundary where QB rush
opportunity is drawn at 0.284 of team carries against **0.157** measured
historically. Neither C0 nor the OWN-4 repair causes or cures it. Not waived,
not counted against either, and the production chain remains blocked by it.

---

## 6. Governance

`include_cold_start` remains **False** by default and is guarded by seven checks.
The OWN-4 repair is **not** behind a flag: it is an accounting repair that makes
a required invariant hold, and leaving allocated mass to vanish was the defect.
It is visible in every game's evidence as `qb_composition` with the repaired-cell
count and the maximum single-draw mass it protected.

`PATH_C_STATE.json` untouched · G0A **11/12** · NFL-1 **NOT AUTHORIZED** ·
QB3/A3/C3 rehearsal-only · no 2026 outcome used · no market, DFS or
restricted-vendor input.

## 7. Files

| File | Role |
|---|---|
| `nfl/production/qb_accounting.py` | `conserve_allocated_mass`, the named guard, and `ZERO_DRAW_ERASURE` |
| `nfl/production/nonqb/football_engine.py` | composition calls the guard; refuses on no donor; records the repair |
| `nfl/tests/test_xl1_shared_pass.py` | 14 checks including both seeded violations and the bypass proof |
