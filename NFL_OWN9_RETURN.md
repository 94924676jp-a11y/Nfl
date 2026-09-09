# OWN-9 — A1 single-owner rushing

**Decision: `OWN9_A1_SINGLE_OWNER_RUSHING_VALID`**

A1 closes exactly where A0 violates **82.1%** of draws, wins CRPS on **every**
category, and **repairs the sign defect** OWN-8 identified rather than merely
forcing arithmetic. Closure did not cost dispersion — it improved it, sharply.

**Not promoted.** Research only, no production file changed (`git status
--porcelain nfl/production` → **0**).

---

## Part 0 — the write guard

`nfl/tools/nflwrite.py`. Three times this session a compound command of the
form `cd repo && job & ; cat > FILE` wrote FILE into the **other** repository,
because everything after `&` runs in the original working directory. A comment
would not have stopped any of them.

The guard resolves the repository root **from its own `__file__`**, never from
the shell, so a wrong cwd cannot mislead it. It requires the NFL marker files,
refuses a root carrying another project's markers, resolves the destination
through symlinks and `..` **before** the containment test, and refuses a
zero-byte payload — because an empty write is what a failed heredoc looks like
when it succeeds.

Verified from `/tmp`: absolute escape refused, `..` traversal refused, parent
escape refused, empty payload refused, legitimate write accepted. **21 checks.**
Every generated artifact in this task went through it.

## Part A — the pre-registration is unmodified

`nfl/research/own8/predeclaration_own8.md` hashes to
`90f6ecc37bcee427177f183be03374c13ec87fe1e14d667a4457c797748789db`, matching
the committed value. The runner refuses to start otherwise. Frozen category
definitions were carried over unchanged and none was redefined.

**The categorisation closes in the data before any model runs: 3,230 of 3,230
team-games, max residual 0.** Every carry belongs to exactly one category.

## Parts B–E — what was refit, and what was not

`rush_play_budget = team_carries − scrambles`. Scrambles are a **prior claim**,
outside the fitted simplex. The budget is partitioned across **designed QB
rush, kneel, RB, WR, TE, fringe**.

WR and TE **are** separable under the original data (WR 0.95, TE 0.047 carries
per team-game) and were kept apart rather than merged.

| parameter | status |
|---|---|
| per-team ewma of prior category shares, half-life 2 | **refit** — the denominator and category set changed |
| league category share (fallback for no history) | **refit**, same reason |
| additive share-residual pool per category | **refit** |
| shrinkage `n/(n+K)`, **K = 4.0** | **inherited**, P4C's constant, not re-chosen |
| ewma half-life 2 | **inherited**, Stage-2's accepted value |
| estimator family | **inherited** — ewma prior + additive residual pool |
| A0's `drush_per_dropback` | **inherited for A0 only** |

**Part E — `drush_per_dropback` was not converted.** OWN-8 proved designed
rushes are carry-owned, so a dropback-denominated rate cannot legitimately
transfer. A1's control is estimated fresh on the carry denominator under the
same chronology. No post-hoc calibration to any historical mean.

Chronological throughout: parameters for season `ev` come from seasons strictly
before `ev`. Evaluation **2022–2024**, **1,630 team-games**, 400 draws each;
2020–2021 burn-in, never scored.

**Both arms were given the same realised `team_carries`, `dropbacks` and
`scrambles`.** That is an oracle on the budgets, identical for both, and it is
deliberate: the allocation architecture is what is under test, and letting the
budgets differ would confound it. Stated, not discovered.

---

## Part G — per-draw invariants

652,000 draws per arm.

| | **A0** | **A1** |
|---|---|---|
| closure violations | **535,354 (82.1%)** | **0** |
| negative allocations | 0 | **0** |
| designed QB rush exceeding its budget | 15 | **0** |
| degenerate draws | — | **0** |

Every carry has exactly one owner in every simulated world under A1. No
clipping, no renormalisation, no dumping into OTHER, no deleted draws.

## Part H — distributional science

**A1 wins CRPS on every category.**

| category | A0 | **A1** | change |
|---|---|---|---|
| designed QB rush | 1.3790 | **1.0083** | **−26.9%** |
| RB | 1.7227 | **1.3970** | **−18.9%** |
| fringe | 0.0957 | **0.0938** | −2.0% |
| WR | 0.5847 | **0.5736** | −1.9% |
| TE | 0.0481 | **0.0473** | −1.7% |
| kneel | 0.5084 | **0.5070** | −0.3% |

**Pooled predictive draws against realised outcomes** — the headline is
designed QB rush, where A0 under-disperses badly:

| designed QB rush | mean | sd | p95 | p99 | zero mass |
|---|---|---|---|---|---|
| **observed** | 1.9000 | **2.7751** | **7** | **12** | **0.3669** |
| A0 | 1.7596 | **1.3574** | 4 | 6 | 0.1789 |
| **A1** | 2.0108 | **2.6516** | **7** | **11** | **0.3977** |

A0's spread is **half** the truth and it puts only 18% of mass at zero against
an observed 37%. A1 matches p95 exactly, p99 within one, and zero mass within
3 points.

| RB | mean | sd | p05 | p95 |
|---|---|---|---|---|
| observed | 21.4301 | 6.7517 | 11 | 33 |
| A0 | 22.8098 | 7.1444 | 12 | 35 |
| **A1** | **21.0027** | **6.8350** | **11** | **33** |

*A methodological correction made before reporting.* The first version of this
diagnostic summarised the distribution of per-team-game predictive **means** and
compared it against realised outcomes. A distribution of means has almost no
zero mass and a far narrower spread than the predictive distribution it came
from, so it would have understated dispersion and flattered calibration on both
arms. The draws are now pooled.

### The sign defect is repaired — this is the test that mattered

| designed QB rush vs | **observed** | A0 | **A1** |
|---|---|---|---|
| team carries | **+0.3140** | **−0.4115** | **+0.5070** |
| dropbacks | **−0.1521** | **+0.9724** | **−0.2651** |

**A0 has the sign backwards on both axes.** A1 has the correct sign on both.

**And the honest caveat: A1 overshoots the magnitude.** It couples designed
rushes to the carry budget about 60% more tightly than reality (+0.507 against
+0.314) because it draws them as a share of that budget, so the coupling is
mechanical. Reality carries extra independent variation. A1 is right about the
*direction* and too confident about the *strength* — which is exactly the
territory A2's common latent was pre-registered for, and it is a refinement of
A1, not a replacement.

## Part D — kneels are representable

`A1_KNEEL_MODEL_UNDEFINED` is **not** the verdict. The P4C-style
historical-share mechanism represents kneel mass under the same chronology and
objective, as an explicit modelled category — not buried in OTHER:

| kneel | mean | sd | p95 | zero mass |
|---|---|---|---|---|
| observed | 0.7706 | 1.0433 | 3 | 0.5509 |
| **A1** | **0.8170** | 1.3345 | 4 | **0.5971** |

Mean within 6%, zero mass within 4.6 points, right shape, **over-dispersed in
the tail** (sd 1.33 against 1.04). Representable and honest about its
limitation. No new estimator class was introduced.

## Part I — downstream

`RUSHING_CONVERSION_CONTROL_UNDEFINED` remains in force; **no rushing-yard
model was built.** No production file changed, so the deterministic seed
contract, D1, QB dropback closure, OWN-4 mass conservation, C3 completions /
passing yards / passing TDs, receiving accounting and terminal-state accounting
all stand exactly as OWN-7 and OWN-8 verified them. Re-running them against an
unchanged system would not be evidence.

**Suite: 43 modules, 457 test functions, 2,659 checks, 0 failing.**

## Part J — decision and its limits

**`OWN9_A1_SINGLE_OWNER_RUSHING_VALID`.** Not promoted, and three limits belong
with it:

1. **Budgets are oracled.** This validates the allocation architecture, not a
   whole-forecast improvement.
2. **A1 over-couples** designed rushes to the carry budget (§H).
3. **This is development evidence.** It can reject; it cannot promote.

## Files

`nfl/tools/nflwrite.py` · `nfl/tests/test_own9_write_guard.py` ·
`nfl/research/own9/a1_lib.py` · `run_own9.py` · `own9_results.json`
