# SC2 pre-registration — reception/interception joint coherence

**Written before anything is built or scored.** Nothing in this file is
implemented. It exists so that the mechanism is chosen by a measurement named
in advance rather than by whichever construction happens to make a board seal.

---

## 1. The defect, measured, not asserted

`football_engine.credit_passing_line` needs

    team_receptions <= sum_q(attempts_q) - sum_q(interceptions_q)

and refuses by name when it does not hold. That refusal is correct and stays.
The refusal's own text already names the owed fix: *"an SC1-style coupling that
reserves intercepted throws out of the targeted budget, which is a
pre-registered mechanism change and not a patch."* This is that
pre-registration.

**Why the inequality can fail.** Under C3 the targeted-throw budget comes from
the quarterbacks' attempts (`shared_pass.targeted_throws`), those throws are
dealt to receivers, and RC1 converts them to catches. Interceptions are drawn
separately, by QB V1, as `Binomial(att - cmp, p_int)` on QB V1's OWN completion
count — which C3 then overwrites. So nothing in the chain reserves an
intercepted throw out of the pool that becomes catches, and the two quantities
meet for the first time inside the passer credit.

**Rate, measured on this repository's sealed runs.** `credit_passing_line`'s
docstring records 8 failing team-draws in 94,000 — 8.5e-5. Reproduced on
2026_02_DET_BUF at HEAD, same checkout, same seed, same written_at, changing
only the draw count and the candidate declaration:

| arm | draws | outcome |
|---|---|---|
| R9_W1P_G | 400 | PASS |
| R9_W1P_GA | 400 | PASS |
| R9_W1P_G | 8,000 | FAIL, 1 draw (worst 6211: 19 completions against 17 completable) |
| R9_W1P_GA | 8,000 | FAIL, 3 draws (worst 307: 24 completions against 23 completable) |

**It is arm-independent.** The earlier reading that "GA dropped C3 and G kept
it" is WITHDRAWN. G is the arm that did not run enough draws to reach a gap
present in both. Any comparison of the two at different draw counts was
comparing that luck.

## 2. Two candidate constructions, and neither is chosen here

**SC2-A — reserve the picks out of the catchable pool.** The targeted budget is
unchanged; RC1 converts over `targeted - interceptions` instead of `targeted`.
The inequality then holds by construction, with nothing clipped.

*The objection that has to be answered first, and it is not rhetorical.* In
play-by-play, a throw intercepted on a targeted pass **is already a target for
the intended receiver**. So RC1's catch rate was estimated on a denominator
that INCLUDES intercepted throws. Re-basing the conversion to a
picks-removed denominator without re-estimating the rate would lower every
receiver's receptions by roughly the pick share of targets — a systematic
downward bias introduced in the name of a coherence fix. Whether the correct
form is a re-estimated rate on the reduced denominator, or a different
construction entirely, is **an empirical question this file refuses to answer
by assertion**.

**SC2-B — a feasibility-constrained permutation, exactly as SC1.** For each
team, choose which draw index receives which interception value, subject to
`receptions_j <= sum(att_j) - sum(int_j)` in every draw j. A permutation leaves
the interception marginal **exactly** invariant, element for element, adds no
parameter and fits nothing — the property that made SC1 acceptable.

*Its cost, stated up front.* It breaks the dependence between a quarterback's
interceptions and his own attempts, which is a real dependence: more throws,
more chances to be picked. SC1 permuted a quantity whose measured model
coupling was +0.0299 against a historical +0.1802, so the permutation moved it
towards the truth. **No equivalent measurement exists for interceptions and
attempts**, and until it does, SC2-B cannot claim the same defence.

## 3. The measurement that decides, named before it is run

Pre-cutoff play-by-play, 2020–2025 REG, team-game level:

1. **corr(interceptions, attempts)** in history, and the same correlation in
   the model as it stands. SC2-B is admissible only if the model is
   *under*-coupled, i.e. if the permutation moves it toward history rather than
   away. If the model is already at or above the historical coupling, SC2-B is
   withdrawn without further argument.
2. **The historical catch rate on both denominators** — receptions/targets and
   receptions/(targets - interceptions) — with the difference reported in
   percentage points. This is what says whether SC2-A needs a re-estimated rate
   or is simply wrong.
3. **The realised frequency of the violation in football**: team-games where
   receptions exceed attempts minus interceptions. It is expected to be exactly
   zero, because the inequality is a law and not a convention, and if it is not
   zero then one of the three quantities is not what this file thinks it is.

## 4. Acceptance, fixed now

- The violation rate falls to **exactly zero** on a 50,000-draw DET-BUF run.
  Not "low". A construction that still fails sometimes is not a construction.
- Team receptions, team receiving yards and every receiver's mean targets move
  by no more than **Monte Carlo error** under SC2-B, which is guaranteed for
  the permuted quantity and must be *checked*, not assumed, for the rest.
- Under SC2-A the reception shift is **reported in full**, per receiver, and is
  not permitted to be described as a coherence fix if it is a level change.
- `published team targets == the consumed throw-process target budget`, per
  draw, both teams, exactly — the closure the owner named. This holds today and
  must keep holding.

## 5. What this does not do

It does not repair the 60 sealed boards that carry an unexplained
`not reached: [C3]`. Those seals are preserved unchanged. What was repaired
separately, and is not part of SC2, is that the refusal now reaches the
artifact instead of vanishing — `c3-refusal-transport-1`, which changes no
number and is a statement about a run that already happened.

It also does not promote anything. SC2 will take its own candidate identity and
will be REHEARSAL_ONLY, never an edit to R9_W1P_G or to any frozen arm.

V2 NOT YET EARNED.
