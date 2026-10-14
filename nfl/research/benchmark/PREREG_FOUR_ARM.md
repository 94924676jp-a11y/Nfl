# Pre-registration: does the football engine earn its complexity? (owner OD-003, 2026-10-14)

**Written** 2026-10-14, before any Week 6 slate exists. The commit time is authoritative.

**Question.** Does the full football forecast beat a simple baseline that has the same news, on the same slates, at
the same information cutoff?

## Arms

Every arm is scored on the same players, slates and actuals.

| arm | forecast |
|---|---|
| **A** | naive: 2026 mean DK points per appearance before the slate × appearance rate before the slate (club weeks). No news. |
| **B1** | A, except a player whose slate state marks him absent (any `availability.ABSENT_STATUSES`) is 0. |
| **B2** | absent per the slate state → 0; otherwise the per-appearance mean (news says he is not out, so no further appearance discount). |
| **C** | the incumbent production forecast: the mean of its prelock per-player draws. |
| **D** | a registered research challenger, run prelock on the same state. On no slate before Week 6 does a prelock D exist; D is **NOT_EVALUABLE** there. |

**The news is fixed.** It is the slate's own frozen prelock state: the same availability statuses C consumed. No arm
receives information that another arm lacked.

**Fallback for A and B when there is no 2026 history:**
1. the previous season's per-appearance mean (times the appearance rate in A and B1);
2. otherwise 0.

Coverage of each source is reported.

**Not scored:** kickers and team defences, until panel actuals exist for them.

## Data separation

| period | use |
|---|---|
| 2021–2023 | priors only |
| **2024** | **development**: diagnosis and challenger design; may be looked at freely |
| **2025** | **holdout**: each registered challenger is evaluated on it **once**; every look is logged in `HOLDOUT_LOOKS.jsonl`; no design change after a look without a new pre-registration |
| **2026 W1–W5** | already inspected; exploratory only, never confirmatory |
| **2026 W6 onward** | **prospective and confirmatory** |

**Historical news-adjusted arms (2024–2025 with injuries) are NOT_EVALUABLE.** The historical injury files have unknown
terms and are withheld (owner decision 2026-10-12; OD-001 decision 5). They wait for RES-010 and a rights decision.

## Metrics and strata

**Primary metric.** Mean absolute error of each arm's point forecast against realised DK points, over every scored
skill player. A player who did not play scores 0.

**Uncertainty.** Paired differences (C − B1, C − B2, C − A, and D − C once D exists), with a **game-blocked** bootstrap:
10,000 resamples, seed 20261014.

**Reported strata.** They inform; they do not decide.
- position
- expected workload: tercile of C's forecast mean (prediction-defined)
- playing-time uncertainty: the state's status, Questionable/Doubtful versus no designation
- projection magnitude: decile of C
- slate format: Classic or Showdown

## Decision rule (fixed now)

**When the analysis runs.** Once, when the prospective set (W6 onward) first reaches **30 games**. No interim look
decides anything.

**C earns its complexity** only if the upper 95% bound of C − B1 **and** of C − B2 is below 0 on the pooled primary
metric. In addition, no position may show C worse than B with an interval excluding 0.

**Otherwise.** The result is recorded as **NOT DEMONSTRATED**, and no further simulation layer is proposed for
promotion until a challenger (D) clears C on this same rule.

**D replaces nothing automatically.** Promotion is the owner's decision.

**Every progress report** carries the current C-versus-B result (owner requirement, OD-003), even before the analysis
point, labelled INTERIM / NOT A DECISION.

## AMENDMENT 1 (2026-10-14, before any Week 6 data exists; the decision rule is extended, not loosened)

**Why.** The slate state's news includes more than absences: it records the captured QB depth rank (`depth_rank`).
B1 and B2 use only absences. A starter-blind baseline would credit the engine with information any simple process also
has.

**New arm.**

| arm | forecast |
|---|---|
| **B3** | B2, except a QB whose slate-state `depth_rank` is not 1 is 0 |

**Decision rule, extended.** C earns its complexity only if the upper 95% bound of C − B1, C − B2 **and** C − B3 is below
0 on the pooled primary metric. The other conditions are unchanged.

**Already-inspected slates.** On 2026 W4–W5, B3 is computed as **exploratory**: those slates were inspected before this
amendment, as they were before the pre-registration itself.
