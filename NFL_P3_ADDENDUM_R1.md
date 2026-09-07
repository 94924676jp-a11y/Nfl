# P3 addendum — Perplexity R1 external evidence, and a correction to my own wording

**Date:** 2026-09-07 · **Repository:** `94924676jp-a11y/nfl`
**Status:** addendum to the completed P3 return. **P3 itself is unchanged** —
no result was re-run, no threshold moved, no predeclaration edited. G0A remains
**11/12**. NFL-1 not executed.

---

## 1. The owner qualification lands on something I got wrong

> *A final historical file containing a pre-kickoff row timestamp may support a
> retrospective chronology test without proving that the same artifact was
> retrievable in that exact form at forecast time. Do not collapse those
> concepts.*

**I collapsed them.** P2 and P3 describe the injury feature as
"chronology-proven", "provably pregame", and the HIGH information-quality class
as requiring "a chronology-proven current-week injury row". Those phrases read as
*prospective capture integrity* — that the artifact existed in that form when a
forecast would have been written. What I actually established is
**retrospective chronology defensibility**: the surviving row's own
`date_modified` precedes kickoff in the final file.

The wording is corrected in `nfl/research/p2/stage_a.py`,
`nfl/research/p3/p3_features.py`, `run_p3_adversarial.py` and in the P3 report.

### Direct evidence that the two differ

The 2024 file holds two player-weeks with more than one row, and both are
mid-week revisions:

| week | team | player | report_status | `date_modified` |
|---|---|---|---|---|
| 15 | HOU | Cade Stover | **Questionable** | 2024-12-15T03:34:33Z |
| 15 | HOU | Cade Stover | **Out** | 2024-12-15T14:17:06Z |
| 15 | NYJ | Tyler Conklin | **Questionable** | 2024-12-14T20:55:19Z |
| 15 | NYJ | Tyler Conklin | **Out** | 2024-12-15T13:57:00Z |

**Designations are revised within the pregame window, and the file normally
keeps one row per player-week** (5,952 of 5,954 in 2024). So where a revision
occurred, the surviving row is generally the *later* state — a state that did
not exist at an earlier forecast time, even though its stamp is still
pre-kickoff. That is the owner's point, demonstrated rather than conceded.

### How much exposure this actually creates — measured

Lead time from `date_modified` to kickoff, all 27,600 REG rows 2020–2024 with a
matched kickoff:

| bucket | rows | share | cumulative |
|---|---|---|---|
| after kickoff | 17 | 0.062% | 0.062% |
| T−0 to T−90 min | **0** | **0.000%** | 0.062% |
| T−90 min to T−4h | 7 | 0.025% | 0.087% |
| T−4h to T−24h | 226 | 0.819% | 0.906% |
| T−24h to T−48h | 12,831 | 46.489% | 47.395% |
| earlier than T−48h | 14,519 | 52.605% | 100.000% |

**99.09% of rows are stamped more than 24 hours before kickoff, and not one row
is stamped inside the final 90 minutes.** The mass sits at T−24h to T−48h,
exactly where the Friday filing deadline puts it. By designation: 0.02% of
`Out`, 0.00% of `Doubtful`, 0.08% of `Questionable` land inside T−4h.

**So the retrospective test is strong for a forecast written at T−90 minutes** —
99.94% of rows would have existed in their final form by then. What it is *not*
is a proof of prospective capture integrity, and the correction stands.

### The assumption I never stated, now stated

Stage A implicitly assumes a **forecast time at or after the final pregame
filing**, roughly T−24h. For an earlier forecast time — a Wednesday projection —
the surviving row may reflect a revision that had not happened yet, and the
measurement above cannot bound that, because the superseded rows are gone.

**This is a live-system caveat, not a retrospective one**, and it is exactly what
the T−90 capture track is built to remove: a captured artifact has a
`retrieved_at`, so prospective integrity becomes a fact about our record rather
than an assumption about someone else's file.

### Taxonomy preserved, not flattened

| concept | in this project | status for the injury feature |
|---|---|---|
| source / effective time | `date_modified` on the row | present 2020–2024, absent 2025 |
| `retrieved_at` | when *we* obtained the bytes | **only exists for live captures**, never for a historical nflverse file |
| `forecast.written_at` | when a projection is produced | assumed ≥ final filing (above) |
| kickoff | game start | from the captured schedule |
| historical file vintage | which build of `injuries_YYYY.csv` | **unknown and unrecoverable** — nflverse retains only the current asset |
| row-level effective timestamp | `date_modified` | measured above |
| retrospective chronology defensibility | can we show the row predates kickoff | **YES**, 99.94% at T−90 |
| prospective capture integrity | was it retrievable then, in that form | **NO** — not establishable from this file |

---

## 2. R1 findings against what P1–P3 measured independently

Recorded as concordance, **not** adopted. No P3 number moved.

| R1 finding | Our independent result | Verdict |
|---|---|---|
| Opportunity persists more strongly than conversion/efficiency | P1: snap share r ≈ 0.71–0.78, target share ≈ 0.68–0.75 from persistence alone; efficiency never modelled | **Concordant.** Ours is measured on our own frame. |
| Naive proportional redistribution poorly supported as a universal rule | P1: proportional MAE 0.0453 vs 0.0384 for no redistribution, winning 14.8%. P2: worst or near-worst in **all six** opportunity classes | **Concordant, and ours is stronger** — proportional is worse than doing nothing, not merely unsupported. |
| Redistribution fails through several distinct mechanisms | P2 measured mechanism-dependence but did not decompose *why*: backup-weighting helps snaps/routes (−11% MAE), nothing helps targets/red-zone/third-down | **Partially concordant.** We show the *what*, not the *why*. R1's four mechanisms are untested here. |
| RB and receiver vacancies may behave differently | Our split is by **opportunity class**, not position: snaps/routes redistribute, targets/red-zone/third-down do not | **Neither confirmed nor refuted.** Different cut of the data. Logged as a hypothesis for R-queue, not acted on. |
| Point-in-time availability data scarce and poorly versioned | Measured exactly: `date_modified` present 2020–2024, **absent in all of 2025**; no archival vintage reachable (P3 §16); intraweek sequence does not exist at all | **Strongly concordant**, and ours is a specific measurement rather than a general observation. |
| Providers expose mutable current-week products, not reproducible historical states | Not tested — no provider was ingested | **Untested.** Consistent with §1 above about nflverse's own file. |
| True player-level routes remain an acquisition gap | P1/W4: `participation.route` is the *targeted* receiver's route, one scalar per play. `rpr` is a participation proxy and is named as one | **Concordant**, independently established. |
| Reliability/autocorrelation ≠ next-game predictive value | P1 built this in from the start: every claim is walk-forward next-game MAE/r, never a within-sample autocorrelation | **Concordant by construction.** |

**Nothing here changes a P3 conclusion.** Where R1 agrees, it agrees with a
number we produced ourselves; where it offers a mechanism or a position split we
did not test, it is logged and not adopted.

**External numerical claims are not imported.** No target-share stability figure,
route-rate figure, CPOE, PROE, position-group stability, redistribution
percentage or injury-return effect from R1 enters any model, feature, threshold
or report as project truth.

---

## 3. Future research queue — recorded, not executed

| id | question | status |
|---|---|---|
| **R2** | Does pass tendency / PROE add genuine chronological next-game predictive value for **team pass volume** beyond simple historical baselines? | **backlog.** Directly aimed at P1's weakest result: team dropbacks r ≈ 0.10–0.22, with last week worse than the league mean. |
| **R3** | Reconcile routes/game, route rate, route participation and routes/dropback under identical samples and definitions | **backlog.** Would put a bound on the `rpr` proxy gap, currently unmeasured. |
| **Benchmark Capture** | Forward contemporaneous capture of selected professional projections, so external forecasts can be compared using true pre-kickoff snapshots | **backlog.** Note it is a *capture* design, which §1 shows is the only way to get prospective integrity. |
| **DFS Historical Capture** | Forward salary / ownership / contest-result capture, since retroactive availability is poor | **backlog, and gated** — only when the DFS phase is authorized. |

None of these was executed. No PROE experiment, efficiency model, fantasy-point
model, professional-benchmark ingestion or DFS work was added to P3.

---

## 4. What changed in the repository

Wording only, plus this file. **No result, threshold, predeclaration or metric
was altered**, and nothing was re-run.

```
M  nfl/research/p2/stage_a.py            "provably pregame" -> retrospectively defensible
M  nfl/research/p3/p3_features.py        same correction
M  nfl/research/p3/run_p3_adversarial.py same correction
M  TASK_REPORT_2026-09-07_P3.md          §12 wording + pointer to this addendum
A  NFL_P3_ADDENDUM_R1.md                 this file
```

G0A remains **11/12**, Item 1 PARTIAL / PENDING REAL EVENT, NFL-1 unexecuted,
2026 outcomes untouched. No wager recommended or discussed.
