# NFL 2026 evaluation arms

**Created** 2026-09-06 under owner Directive 3 §3.
**Status:** specification. Neither arm has been executed.
**It changes no frozen constant.** Both arms consume the identical constants in
`nfl/research/C3_COLD_START_SPEC.md` §7.2, whose freeze is recorded in
`nfl/NFL_COLDSTART_FREEZE.json` and corrected — by appended record, not rewrite —
in `nfl/NFL_COLDSTART_FREEZE_CORRECTION_01.json`.

---

## The claim that was too strong

Directive-2 said that freezing the specification before the first 2026 outcome
made the 272-game season a fixed prospective holdout. It does not, and the reason
is in the frozen arithmetic itself.

The frozen transition is `θ_g = g / (g + M)`. For any week after the first,
`g > 0`, so the forecast **consumes 2026 results** — legitimately, by a rule
fixed in advance, but it consumes them.

**A frozen formula is not a frozen information set.** The specification is fixed;
the information the specification eats is not. Calling that an untouched holdout
overstates it.

---

## Three arms, kept apart

| | **Arm A — static fixed prospective holdout** | **Arm B — frozen-specification prequential** | **Arm C — sequential adaptive** |
|---|---|---|---|
| Specification frozen before any 2026 outcome | yes | yes | no |
| Consumes 2026 outcomes | **never** | yes, by the pre-frozen rule only | yes |
| Parameters may change mid-season | no | no | yes |
| Each forecast sealed pre-kickoff | yes | yes | yes |
| Evidential strength | strongest untouched arm | strong prospective/prequential | weakest |

**They are never pooled.** Reporting a combined figure across arms would average
away exactly the distinction that makes Arm A worth having.

---

## Arm A — static fixed prospective holdout

**What it predicts.** The same quantity as Arm B (team points for each side of
each game), for every regular-season game of 2026.

**What it consumes.** Only the inputs available before Week 1: prior-season final
scores from the frozen `games.csv` snapshot
(sha256 `c563178a…8fda9`), the franchise map, and the eight frozen constants.
**No 2026 result, at any point in the season.**

**The arithmetic, stated exactly so it is not a silent redefinition.** Arm A is
the frozen specification evaluated with the games-played counter **pinned at its
Week-1 value for the entire season**:

```
g_i := 0        for every team i, in every week of 2026
θ_off = 0/(0 + M_off) = 0        exactly
θ_def = 0/(0 + M_def) = 0        exactly
```

Substituting θ = 0 into the frozen blend leaves the prior component alone:

```
mu_off_i = L + lambda_off * (OFF_i - L)
mu_def_i = L + lambda_def * (DEF_i - L)
forecast(i vs j) = mu_off_i  combined with  mu_def_j,  ± h/2 for home/away
```

with `L`, `λ_off`, `λ_def`, `h`, `OFF_i`, `DEF_i` all taken from the frozen
2025 inputs. **Every symbol is already defined in the frozen spec; nothing new is
introduced and no constant moves.** Arm A is not a second model — it is the
frozen model held at its `g = 0` information state.

**Consequence, stated plainly:** Arm A's forecast for a given team is the **same
number in Week 1 and Week 18**. It will lose to Arm B on accuracy, and that is
expected. Its value is not accuracy — it is that its information set is provably
untouched by 2026, so it is the one arm whose result cannot be explained by
within-season adaptation.

**Cost to run:** one number per team, computed once. Effectively free, which is
why Directive 3 asks for it to be preserved "if inexpensive". It is.

---

## Arm B — frozen-specification prequential

**What it predicts.** Team points per side per game, for every regular-season
game.

**What it consumes.** The Arm A inputs, **plus** 2026 results from weeks strictly
earlier than the game being forecast, folded in **only** by the transition rule
frozen before Week 1:

```
theta_off = g_i / (g_i + M_off)      M_off = 8.8764
theta_def = g_j / (g_j + M_def)      M_def = 23.2199
```

**The constraint that makes it prequential and not merely sequential:** every
forecast may use only information available before **its own** forecast
timestamp, enforced structurally by `nfl/identity/seal.py`
(`CAPTURE_AFTER_WRITE`, `WRITE_AFTER_KICKOFF`) rather than by care.

**How it must be described.** "Frozen-specification prequential evidence over the
2026 season." **Not** "an untouched 272-game fixed holdout." The specification was
untouched; the information set was not.

---

## Arm C — sequential adaptive

Any later NFL-2+ candidate whose parameters, features or architecture changed
after observing 2026 outcomes. Predictions still sealed pre-kickoff, so it is
still prospective — but it is the weakest of the three and must be labelled as
such. **Never pooled with A or B.**

The seal ledger makes arm membership checkable after the fact rather than
asserted: an arm is identified by its `spec_sha256`, and a changed specification
produces a different execution identity fingerprint.

---

## What each arm can and cannot support

| Question | Arm A | Arm B | Arm C |
|---|---|---|---|
| "Did a pre-registered specification beat a naive benchmark on unseen games?" | **yes** | yes | no |
| "Is the within-season update rule earning its complexity?" | — | **yes, against Arm A** | no |
| "Did this candidate improve on the frozen control?" | no | no | **yes, with adaptation declared** |

The **A-vs-B contrast is the reason to keep both**, and it is worth more than
either alone: A and B share every constant and differ *only* in whether the
season's own results are consumed. Their difference is therefore a clean estimate
of what the within-season update is worth — a comparison that is unavailable if
only B is run, and one that C can never provide.

---

## Registration

Both arms are registered **before** execution and before any 2026 result exists.

- Arm A: `DEFERRED / NOT_YET_EXECUTED` — blocked on G0A, not on evidence.
- Arm B: `DEFERRED / NOT_YET_EXECUTED` — same.
- Expected first confirmatory answer on either: **`DEFERRED / UNDERPOWERED`**.
  Registered now so it is not later read as a null result (Rule 006a).
