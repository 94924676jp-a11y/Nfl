# NFL-V1-R2 — PRODUCTIONIZE THE ACCEPTED NON-QB BASELINES

**Starting HEAD** `ad2a74417b58c36abd93949ea850a3c10389a145` (clean tree)
**Freeze** `nfl/production/rehearsal/FREEZE_V1R1.json`
**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`

## DECISION: `V1_NONQB_PRODUCTION_BLOCKED`

**D1 team_environment is productionized, verified and live in the slate.**
**D2 onward is blocked on an upstream source that does not yet exist**, not on
engineering effort and not on unreproducible research code.

The blocker, precisely: the accepted appearance model is a logistic fitted on
P3 feature groups including `practice_progression` and `teammate_availability`.
Those require the nflverse injuries feed, and **`injuries_2026.csv` returns 404
— `SOURCE_NOT_YET_PUBLISHED`, recorded 40 times in our own manifest.** Without
appearance there is no availability term `A`, so D3's allocator cannot run, and
D4/D5 sit downstream of D3.

**I did not substitute a reduced feature set.** §C forbids silently
reinterpreting a research model, and dropping the two injury-dependent groups
would be exactly that.

G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. Nothing promoted, no
retuning, no feature search, no calibration against 2026.

---

## 1. The research code IS operationally reusable — proven first

Before claiming anything was blocked I checked the premise:

    nfl/research/repro/regenerate.py --emit
    OK  panel_enriched.pkl   7bbc8cb255dc0c0e   51,871,153 bytes
    OK  volume_store.npy     c47a52903bb038ce   86,035,459 bytes
    EXACT_REPRODUCIBLE -- both artifacts byte-identical in 30.3s

So `RESEARCH_PRODUCTION_EQUIVALENCE_BLOCKED` is **not** the right verdict. The
research code runs, its inputs regenerate byte-identically, and I productionized
a layer with it. The blocker is a missing 2026 input.

---

## 2. D1 team_environment — DONE

`nfl/production/team_volume_v1.py`, spec `team-volume-v1-p4b-frozen-1`.

**Equivalence by construction rather than by reimplementation.** The production
layer *imports* `p4b_volume` and calls its own `attach`, `baselines`,
`build_forms` and `draw`. There is no second copy of the mathematics to drift
from the first, and a test asserts the module defines no `ewma` or `baselines`
of its own.

**Selections are read, never re-chosen.** From the frozen `volume_results.json`,
the estimators selected by the research walk-forward on 2025:

| metric | estimator | form |
|---|---|---|
| `team_off_snaps` | `league_mean` | `coach_empirical` |
| `team_dropbacks_part` | **`coach_prior`** | `coach_empirical` |
| `team_targets` | `ewma` | `coach_empirical` |
| `team_carries` | **`coach_prior`** | `coach_empirical` |
| `team_rz_carries` | **`coach_prior`** | `coach_empirical` |

A test asserts production never minimises a score to pick an estimator —
re-selecting inside production would be the retuning this packet forbids.

**A load-bearing input I had to verify rather than assume:** three of five
metrics select `coach_prior`, so the 2026 head coach is a *model input*, not a
cosmetic field. The captured schedule carries `home_coach`/`away_coach` for
**16 of 16** games. A team with no resolvable coach refuses rather than
guessing.

**Chronology** reuses the frozen research `attach` — prospective rows are
appended at their own ordinal and the whole list re-sorted, so each inherits
the existing strictly-earlier cut. Forecasting a week the panel already
contains is refused outright.

Live output, 2026 week 1: NE dropbacks mean 34.1 against snaps 65.2; SEA
30.2/61.8; DAL 39.7/66.2; PHI 35.7/66.2. No negative draw in any metric.

**The accepted conclusion is preserved, not improved.** P4 found team volume
close to unforecastable — best simple baseline was the league mean in two
seasons of four, correlation peaked at 0.167. That limitation is carried in
`KNOWN_LIMITATIONS` and emitted as a run warning: *"these draws are honest
about that width; they do not narrow it."*

---

## 3. D2 participation — BLOCKED, with the evidence

The accepted Stage-2 method is `ewma_hl2` for WR, TE and RB (`s2_verdict.json`).
**That half is feasible** — the share history comes from `panel_p3`, 2020–2025,
and a week-1 forecast's priors are last season's.

The blocker is the other half. `p4c_build.appearance()` fits a logistic over
`set(FEATURE_GROUPS) - {'p2_base'}`, i.e.:

    practice_progression      needs the injury/practice report
    teammate_availability     needs to know who is out
    absence_history           history only
    role_volatility           history only

Two of the four require the injuries feed. Measured in our own manifest:

| source | 2026 state |
|---|---|
| `injuries` | **DEFERRED / SOURCE_NOT_YET_PUBLISHED — 404**, 40 rows |
| `pbp_participation` | `WATCH_ONLY`, never captured; 404 for 2026 |
| `snap_counts` | `WATCH_ONLY`, never captured |

The registry note says the injuries file is *"expected before the season opens
or before the week's first report"* — so this is a **timing** blocker, not a
permanent one.

**What I refused to do:** fit the appearance model on the two history-only
groups. It would have run, produced plausible numbers, and been a different
model wearing an accepted model's name.

---

## 4. D3 / D4 / D5 — feasible, and downstream of D2

I located every piece, so the blocker is precise rather than vague:

| layer | accepted mechanism | parameters recoverable? | blocked by |
|---|---|---|---|
| **D3 targets_carries** | P4C **system C**: `W = C + resample(add_pool)`, empirical OTHER mass, then `allocate(W, A, …)` in simplex/occupancy mode | **yes** — `alpha0` 17.53, `sigma_lr`/`sigma_lg`/`q_zero` per position, `mass_mean` 0.0111 all stored | needs `A` (appearance) from D2 |
| **D4 conversion** | RC1 baseline, `SIGNAL_WEAK` | yes, `rc1_lib` reusable | needs D3 opportunity |
| **D5 td_layer** | TD2 pooled positional control | yes | needs D3/D4 |

Two things worth recording about D3 while I was in there:

- The accepted allocator's OTHER residual mass is drawn from a **prior-season
  empirical pool**, not a fitted constant — so the "no clipping, name the
  residual" behaviour the packet asks to preserve is intrinsic to system C, not
  bolted on.
- P4C's scores show **system E at CRPS 0.4204 against C at 0.9520**. E is the
  realised-allocation *oracle* and is excluded from `ELIGIBLE_SYSTEMS`, with a
  guard-deletion proof showing that exclusion is what stops it. I mention it
  only because a reader comparing those numbers might otherwise think the
  accepted system was the weak one.

---

## 5. A governance discrepancy you should see

The pipeline's stage strings and the registered governance artifact disagree
about the word "accepted".

`run_forecast.py` carried `P4C system C ACCEPTED`, `Stage2 ewma_hl2 ACCEPTED`,
`team volume, accepted`. But `PATH_C_STATE.json` — the registered artifact,
owner directive 2026-09-08 — records:

| subsystem | knowledge | action |
|---|---|---|
| `team_volume` | RECOVERABILITY_CHARACTERIZED | **HOLD_CHARACTERIZED** |
| `rb_carry_allocation` | DECOMPOSED | **DEVELOPING** (arch: P4C system C) |
| `appearance` | DECOMPOSED | **INFORMATION_CONSTRAINED** |
| `target_allocation` | UNEXPLORED | **DATA_BLOCKED** |
| `receiving_conversion` | RECOVERABILITY_CHARACTERIZED | **HOLD_CHARACTERIZED** |
| `receiving_baseline_calibration` | BASELINED | **CALIBRATION_DEFECT** |
| `td_red_zone` | UNEXPLORED | **HOLD_TENTATIVE** |

**Nothing non-QB is at `PROMOTED` or `PROSPECTIVELY_VALIDATED`.** The prose
strings overstate the governance state. I did not change `PATH_C_STATE.json`
— it is the registered artifact and correcting the prose is your call — but I
did replace `team_environment`'s string with the real spec version, and the
rest now read `STAGE_DECLARED_UNIMPLEMENTED` rather than `...ACCEPTED`.

This matters for interpretation: productionizing these layers would put
`HOLD_CHARACTERIZED` and `CALIBRATION_DEFECT` components into a live path.

---

## 6. Full-slate rehearsal R2 (§I)

16 games, 2026 week 1, through the real entrypoint.

| | |
|---|---|
| status | **16 of 16 SEALED** |
| accounting failures | **0** |
| publication | `NFL1_NOT_AUTHORIZED` on all 16 |
| completeness | `PARTIAL_PLAYER_COVERAGE` |
| layers present | `team_environment` (**new**), `qb_layer` |
| absent layers | `appearance`, `conversion`, `feature_build`, `participation`, `targets_carries`, `td_layer` |
| roster | 2,955 players; skill positions 921 |
| players with distributions | **84** (QB) |
| coverage | **9.1%** — unchanged |

**Coverage did not move, and I am not going to present D1 as if it did.**
Team volume is a team-level input to the player layers; it produces no player
distribution by itself. Its value is that D3 can now be built on a real
production team-volume source the moment appearance is unblocked.

| position | roster | forecast |
|---|---|---|
| QB | 119 | 84 |
| WR | 381 | **0** |
| RB | 214 | **0** |
| TE | 207 | **0** |

---

## 7. Tests (§L)

`nfl/tests/test_v1_nonqb_production.py` — **35 checks**:

- production imports the research module and calls its four functions, and
  defines no mathematics of its own;
- estimator and form match the frozen 2025 selections exactly, and were chosen
  on a season strictly earlier than the forecast;
- a future week is allowed, a week already in the panel is refused, and the
  panel genuinely stops before 2026 so the test is not vacuous;
- same seed identical, different seed different;
- `coach_prior` is load-bearing, an unresolvable coach refuses, and the real
  slate resolves all 32;
- no negative volume draw; dropbacks below snaps for every team;
- and the layers that could not be productionized declare it rather than fake
  it.

**Canonical suite: 37 modules, 374 test functions, 2,190 checks, 0 failing,
0 raised — SUITE PASS.**

---

## 8. Unresolved debt

1. **`injuries_2026.csv` is 404.** Everything from D2 down waits on it. It is
   expected imminently; the capture path already polls it and will record it
   when it appears.
2. `pbp_participation` and `snap_counts` are `WATCH_ONLY` and never captured.
   D2's share history for **week 2 onward** will need them; week 1 runs on
   prior-season history alone.
3. D1 refits per game per metric — 80 fits per slate, and the rehearsal is slow
   as a result. Correct but wasteful; a per-slate fit cache is an obvious
   improvement and is not a model change.
4. The `PATH_C_STATE` / stage-string discrepancy in §5.

---

## 9. Answer to the packet's own question

> If an accepted research artifact cannot be reproduced faithfully in
> production, stop and name the blocker.

The artifacts **can** be reproduced faithfully — I did it for D1 and the
regeneration is byte-exact. What cannot be reproduced is a **2026 prediction**
for the layers whose accepted mechanism consumes a 2026 input that has not been
published. That is the blocker, it is dated, and it clears itself.

---

## 10. Changed files

| file | change |
|---|---|
| `nfl/production/team_volume_v1.py` | **new** — D1, importing the frozen research |
| `nfl/production/run_forecast.py` | team_environment executes real logic; spec string corrected |
| `nfl/production/rehearsal/run_slate.py` | requests team volume |
| `nfl/tests/test_v1_nonqb_production.py` | **new**, 35 checks |

**Not touched:** `nfl/capture`, `gen_t90_schedule.py`, both anchored workflows,
`nfl/research/*` (read only), `PATH_C_STATE.json`, `NFL_G0A_CHECKLIST.md`,
`qb_v1.py` model logic.

**Ending HEAD:** `46452efb738e01d240e6967ff2b52869b37aeafc`
**G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. Nothing promoted.**

**THEN STOP.**
