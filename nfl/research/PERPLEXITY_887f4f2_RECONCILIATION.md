# Reconciling the Perplexity guidance against HEAD

External guidance dated against HEAD `887f4f2`. Reconciled at HEAD `9886b87`
(three CS1 commits later). Every repo-specific claim below was re-read from
source before being accepted or rejected. **External review is evidence about
the code only where the code confirms it.**

| # | claim | verdict | what the source says |
|---|---|---|---|
| 1 | `joint.py` is unwired research scaffolding | **VERIFIED** | 114 lines; importers are `research/p1s/`, `research/s3/` ×3, and `tests/test_production_pipeline.py`. No production module |
| 2 | `draw_coherence.py` is the wired production coherence layer | **VERIFIED** | 699 lines, **7** non-test importers across `production/`, `product/`, `prospective/` |
| 3 | commit `8c81079` names the real failure class | **VERIFIED** | title, verbatim: *"The guard ran, then the values it guarded were overwritten"* |
| 4 | `reconcile_team_total` returns PASS on unattributed mass | **VERIFIED** | `scale = np.where(s > tol, T / np.maximum(s, tol), 0.0)` then `Outcome.ok`. A positive team total with zero player rows passes |
| 5 | `enforce_possible` clips negatives on every array handed it | **VERIFIED** | `neg = v < 0; fixed[k] = np.where(neg, 0.0, v)` |
| 6 | that clip would contradict a declared invariant | **VERIFIED** | `draw_coherence.py:44-54`: 2,261 negative `qb/pyds`, 2,821 `qb/ryds`, 8,213 `receiving/receiving_yards`; *"`pyds >= 0`, `pyds >= -k` and any clip are refused. Only a negative COUNT is impossible."* |
| 7 | `panel_freshness` is evidence-only and does not block | **VERIFIED** | computed at `qb_allocation.py:755`, recorded at `:887`. No caller refuses on it anywhere outside tests |
| 8 | `draw_contract3.BATCH_AGREEMENT` is 19, not 18 | **VERIFIED — and it is a defect in MY pre-declaration** | line 28 `BATCH_AGREEMENT = 19`; test at 129 `n_mode >= BATCH_AGREEMENT`. See below |
| 9 | `metrics.SUPPORTED` holds 17 entries, 14 `count` + 3 `yards`, no `dk_scoring` | **VERIFIED** exactly | and therefore no `probability` and no `lattice` kind |
| 10 | inactive players are already hard-zeroed | **VERIFIED** | `qb_accounting.assert_inactive_qbs_own_nothing`: *"Every officially inactive quarterback owns EXACTLY zero, in every draw"* |
| 11 | DEN/KC recoverable from a separate capture | **VERIFIED** | `nfl/capture/live_evidence_2026_01_DEN_KC.json`, 32,765 bytes |
| 12 | BUF = Josh Allen 58 snaps, DET = Jared Goff 77, both 100% | **VERIFIED** — independently measured in this session before the report arrived |
| 13 | `denom_panel` 2026 source unverified; do not refresh | **VERIFIED, and ACCEPTED** | no 2026 denominator source has been established. A partially complete denominator produces confidently wrong shares instead of a nameable refusal |
| 14 | **`nfl/production/evaluator.py` grades nothing; only its own test imports it** | **VERIFIED for that module — but the claim is NARROWED, see below** | |

---

## The one claim that is narrowed, and it corrects the reviewer and me alike

**There are TWO evaluator modules, and the reviewer saw one of them.**

| module | status |
|---|---|
| `nfl/production/evaluator.py` | **mine**, written today at `887f4f2`. Imported by `test_evaluator.py` **only**. Grades nothing. The reviewer is right about this one |
| `nfl/product/evaluator.py` | **pre-existing**, 325 lines, added 2026-09-10 in commit `81fdad1`. Imported by `nfl/tools/score_game.py`, which is called by `research/postgame.py`, `research/same_day_retrospective.py`, `prospective/q9shadow/inputs.py`, `prospective/q9shadow/reuse.py` and three test modules. **It is wired, and it is the live scoring path.** |

And it already carries what the guidance says to add:

- **`crps(x, y)`** — exact empirical CRPS. The reviewer's headline gap, *"No CRPS… while twelve private CRPS implementations exist elsewhere"*, is a **thirteenth** if I add my own.
- **`pit(x, y)`** — non-randomised, reporting the bracket rather than one dishonest number for a discrete forecast.
- **`LEVELS = (0.50, 0.80, 0.90, 0.95)`** — the same four levels I independently chose.
- **`CLUSTER_UNIT = 'game'`**, `MIN_GAMES_FOR_CANDIDATE = 4`.
- **`verify_seal()`** — *"refuses unless every sealed file still hashes to the value recorded at seal time"*. That is the guard-then-overwrite protection the guidance calls its highest-value coherence item, **already implemented at scoring time**.

**I built a duplicate without checking whether one existed.** That is the DUPLICATED-component class this project tracks, and I introduced an instance of it. It is my error, not the reviewer's.

**Consequence for the plan.** The guidance's item "add CRPS to `SCORERS`" must **not** be satisfied by writing a new CRPS. The correct move is to reuse `nfl.product.evaluator.crps`, and to decide explicitly whether `nfl/production/evaluator.py` should be merged into the wired module or kept as a distinct scoring-statistics library that imports from it. **That decision is not made here**, because deleting or moving a module is a separate change from marking it, and I am not compounding one unverified build with a second.

**What my module does add** that the wired one lacks: Brier, log loss with a counted clip, sharpness, and `clustered_delta` / `against_baseline` with a required cluster argument. Those are real and are not duplicated.

---

## The correction of record against my own work

`nfl/research/contract4/DIAGNOSIS_AND_PREDECLARATION.md` stated that its 0.90
modal-agreement threshold was *"the same 18-of-20 agreement its
`BATCH_AGREEMENT` constant already uses, so neither is a new number in this
project."*

`draw_contract3.py:28` reads **`BATCH_AGREEMENT = 19`**. The standing threshold
is **19 of 20 = 0.95**. `B = 20` matched; **the threshold did not**. The
pre-declaration relaxed 0.95 to 0.90 while asserting it was not a change.

It was an error of recollection, and that changes nothing about how it is
handled. A threshold loosened by a factor the document says is not a change is
indistinguishable in effect from one loosened on purpose.

**Corrected to 19 of 20 in the pre-declaration, before the contract has run
even once**, so no result is being reinterpreted. Recorded in the document
itself rather than silently edited.

---

## Adopted, with the reasons

- **Do NOT wire `joint.py`.** Kept as research. Production coherence work
  continues in `draw_coherence.py`. Claims 1–6 are all verified and claim 4
  alone — unattributed mass returning `ok` — would have been a regression.
- **Do NOT refresh `denom_panel.csv.gz`** until its 2026 source, vintage,
  completeness, coverage, field definitions and identity behaviour are
  established. Explicitly stale beats confidently wrong.
- **Promote freshness from evidence to a HARD gate**, `CURRENT_SEASON_INPUT_FRESHNESS`,
  on ordinals rather than wall-clock so a `touch` cannot satisfy it, with week 1
  recording `NOT_APPLICABLE` rather than `FRESH`.
- **Contract 4 threshold is 19 of 20.** Corrected before execution.
- **Grade the CDF at the atom** rather than the integer quantile's instability:
  `F(k-1) < q <= F(k)` with Monte Carlo error on both bounds, classifying
  DETERMINED / NOT_YET_CONVERGED / INTRINSICALLY_TIED. It uses a convergent
  statistic, so more draws always help, and it separates *on a boundary* from
  *under-sampled*, which modal agreement provably cannot.
- **`dk_points` is not a Contract 4 quantity.** On a fine lattice, modal
  agreement approaches zero for reasons unrelated to convergence, so applying
  it would guarantee failure for every arm regardless of forecast quality.
- **Contract 4 must report coverage** and return `INCOMPLETE` below a minimum
  certified fraction. A contract satisfiable by having almost nothing in scope
  is not a gate.
- **Drive classification from `metrics.SUPPORTED`,** not from a markdown table.
  Requires extending it from 17 entries to every emitted array first.

## Held, not adopted yet

- **The QB-yard integer deal.** The construction must be a deal over a
  **signed** integer total. A multivariate hypergeometric is defined on
  non-negative counts; applied naively to 2,261 lawful negative `qb/pyds` cells
  it would fail or clip, and clipping breaks the HARD
  `qb_cross_layer_reconciliation`. **The math is pre-registered before any
  code.**
- **Opponent-adjusted strength.** Verified absent from research *and*
  production, so it is a build. Pre-registration first, forward-chained, and it
  must beat the *simple* opponent-adjusted baseline or remain research.

**V2 NOT YET EARNED**
