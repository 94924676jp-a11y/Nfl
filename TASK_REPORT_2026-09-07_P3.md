# P3 — availability quality, role transition, identifier integrity, selective mixture

**Date:** 2026-09-07 · **Repository:** `94924676jp-a11y/nfl`
**Track:** quarantined research. G0A untouched at **11/12**. NFL-1 not executed.
**2026 outcomes used:** none.

---

## Answers to the four questions, up front

**Q1 — Does richer availability information improve Stage A? Marginally, yes.**
Brier 0.1286 → 0.1257 and AUC 0.8712 → 0.8783 in 2024. Real, consistent across
seasons, and small. The gain comes from teammate availability and role
volatility. **Practice progression contributes essentially nothing**, for a
reason that is itself the finding — see Q1 detail.

**Q2 — Can role transition be anticipated? Partly, and asymmetrically.**
AUC 0.74–0.84 depending on target. **Losing a role is more predictable than
gaining one**: `from_starter` AUC 0.841 against `to_starter` 0.769. At an
operating point calling as many transitions as occur, precision and recall sit
around 0.57 for the primary target — real signal, not an operational tool.

**Q3 — Can identifier loss be eliminated? Yes, essentially completely.**
Snap-share coverage goes from **95.370% to 99.868%** — missing rows fall from
2,670 to **76** — using the repository's own `Crosswalk` on nflverse
`players.csv`, with zero fuzzy matching and zero disagreements where both joins
fire.

**Q4 — Does a selective mixture beat both U and mechanical A×C? Partially, and
its real value is defensive.** It beats plain U on every target and season, but
beats *mechanical* A×C significantly on only 3 of 8 test-season comparisons.
What it reliably does is **stop A×C from hurting when the information is not
there** — in 2025, with no injury vintage, the chosen policy uses A×C on **0%**
of rows and turns P2's 2025 regression into a tie.

---

## 1–4. HEAD, commits, tests, seasons

| | |
|---|---|
| HEAD at start | `4f4cfbe` |
| Commits added | see §25 |
| Adversarial checks | **28 passed, 0 failed** |
| G0A suite | 1,230 assertions, 0 failing — unchanged by this work |
| Seasons | 2020–2025 regular season; tune 2022–2023, test 2024–2025 |
| Panel rows | 57,670 (83,144 extended with pregame-identifiable non-appearances) |
| Stage A candidates | 52,330 |
| Role-transition population | 41,234 |

---

## 5–6. Appearance feature changes, and what the practice data actually is

Added to the P2 set: cross-week practice transition, teammate availability by
opportunity class, workload immediately before an absence, and prior role
volatility.

### The practice-progression finding is a data fact, not a model result

The directive asks whether a practice *sequence* (DNP → DNP → LP) beats a single
final designation. **It cannot be tested on this data, and I am not going to
pretend otherwise.** Measured before building anything:

| Season | injury rows | distinct player-weeks | player-weeks with >1 row | max distinct timestamps per player-week |
|---|---|---|---|---|
| 2022 | 5,450 | 5,450 | **0** | **1** |
| 2024 | 5,954 | 5,952 | 2 | 2 |

The nflverse injuries file holds **exactly one row per player-week with one
timestamp**. It does not preserve the Wednesday → Thursday → Friday
progression. And because that timestamp is the last pregame scrape,
`practice_status` is the **final** designation — what was knowable on Friday,
not on Wednesday. A final retroactive row is not a live snapshot, and the
directive says so.

What *is* available is a **cross-week** progression — last week's designation
into this week's — on 13,969 player-weeks. That is what was built and tested,
and its measured contribution is between −0.0005 and +0.0008 Brier: **nothing**.

Transition counts, for the record:

```
none>FP 6125   FP>FP 3200   LP>FP 1699   FP>DNP  754
none>DNP 4148  DNP>DNP 2456 DNP>FP 1372  LP>DNP  620
none>LP 3231   LP>LP 1995   DNP>LP 1207  FP>LP   594
```

**Intraweek practice progression is therefore an open acquisition need, not a
modelling gap.** It is exactly what the live capture track collects going
forward and exactly what no historical file contains.

---

## 10–12. Identifier repair — the clearest result in P3

### Architecture

```
snap_counts.pfr_player_id
        │  nflverse players.csv  (sha256 5d14969f…, 22,653 pairs, injective)
        ▼  via the repository's own nfl/ingest/identifiers.Crosswalk
      gsis_id  ──►  panel row
```

Priority 1 in the directive's list — an existing stable crosswalk already in the
repository — rather than anything new. **No fuzzy-name matching.**
`Crosswalk.map_by_name` exists and is deliberately never called: on the six real
unmapped MLB players it recovers two, **silently mis-joins two**, and fails two.

The alternative bridge through `weekly_rosters.pfr_id` was measured and
**rejected**: 77.51% coverage and **non-injective** — `IzzoRy00` and `YounBy01`
each map to two different `gsis_id`s.

### Match rate, before and after

Raw snap-count rows, 2020–2025 REG:

| | rows | mapped | unmapped | rate |
|---|---|---|---|---|
| pfr → gsis via `players.csv` | 150,351 | **150,183** | **168** | **99.8883%** |

Every failure carries the project's existing named refusal `PFR_ID_UNMAPPED`.
Unmapped by position: TE 35, WR 31, G 25, T 21, DL 12, FS 9, DB 8, RB 7, C 6,
CB 5 — no concentration in a skill position.

Panel rows carrying a snap share:

| Panel | rows | with snap share | missing | loss |
|---|---|---|---|---|
| P1/P2 name+team join | 57,670 | 55,000 | 2,670 | **4.630%** |
| **P3 identifier join** | 57,670 | **57,594** | **76** | **0.132%** |

Per season, identifier-only recoveries: 2024 **+410 rows**, 2025 **+581 rows**.

**Where both joins fire they never disagree — 0 rows out of ~55,000.** So the
old join was *incomplete*, not *wrong*: no previously reported snap-share value
was incorrect, but 4.6% of the population was silently absent from every one of
them, and that share was rising (4.1% in 2020 to 6.1% in 2025).

---

## 7–8. Role-transition target and results

All eight candidates from `predeclaration_p3.md` §1 were scored. The primary was
nominated by the **predeclared stability rule** — lowest across-season AUC
standard deviation among targets with a base rate in [0.05, 0.40] — and not by
best AUC.

| target | base | AUC mean | AUC sd | precision | recall |
|---|---|---|---|---|---|
| `abs_10` | 0.499 | 0.743 | 0.0067 | 0.671 | 0.671 |
| `abs_20` (P2's) | 0.276 | 0.783 | 0.0155 | 0.574 | 0.574 |
| `abs_30` | 0.163 | 0.800 | 0.0250 | 0.489 | 0.489 |
| `up_20` | 0.138 | 0.786 | 0.0203 | 0.431 | 0.431 |
| **`down_20`** | 0.138 | **0.820** | 0.0218 | 0.465 | 0.465 |
| `to_starter` | 0.098 | 0.769 | 0.0258 | 0.341 | 0.341 |
| **`from_starter`** | 0.071 | **0.839** | 0.0151 | 0.340 | 0.340 |
| **`pos_specific`** ← primary | 0.258 | 0.794 | **0.0135** | 0.569 | 0.569 |

*(all figures from the identifier-repaired panel, population 42,719)*

**`from_starter` has the highest AUC at 0.839 and was not chosen**, because the
rule fixed in advance selects on stability, not magnitude. Recording that
explicitly is the point of having written the rule down first.

**The asymmetry is the substantive finding.** Losing a role is materially more
predictable than gaining one:

| | AUC |
|---|---|
| `from_starter` (losing a starting role) | **0.839** |
| `to_starter` (gaining one) | 0.769 |
| `down_20` | **0.820** |
| `up_20` | 0.786 |

That is what you would expect if injury designations are the dominant signal:
the report tells you who is about to lose snaps. It says almost nothing about
*who inherits them*, which is the same asymmetry P1 and P2 found in the
redistribution experiments from the opposite direction.

Precision and recall are quoted at the threshold that makes as many positive
calls as there are events, so they are directly comparable across targets.

---

## 9. Teammate-availability results

Teammate availability was added as a **feature** (vacated snap / route / target
/ carry share held by a same-position teammate now designated Out or Doubtful),
before any redistribution rule.

Leave-one-group-out on Stage A, change in Brier when removed:

| group | 2022 | 2023 | 2024 |
|---|---|---|---|
| **teammate availability** | +0.0011 | +0.0011 | **+0.0014** |
| **role volatility** | +0.0006 | +0.0016 | +0.0011 |
| absence history | +0.0009 | +0.0014 | +0.0009 |
| **practice progression** | −0.0000 | +0.0008 | **+0.0001** |

Teammate availability is the largest single P3 addition and it is still small —
about 1% of Brier. P2's accepted redistribution findings are unchanged and were
not re-litigated: snaps/routes may use backup-weighting, targets/red-zone/
third-down should use nothing, proportional stays rejected.

**Vacated opportunity is not assumed to be fully reallocated.** The feature
records what was vacated; nothing forces it to sum into the candidate set, and
P2 measured that it does not.

---

## 16. 2025 archival injury investigation

**UNAVAILABLE — NO TRUSTWORTHY HISTORICAL VINTAGE FOUND from this executor.**

| Path | Result |
|---|---|
| nflverse `injuries_2025.csv` | Exists, 6,068 rows, **`date_modified` absent entirely**. This is the final-season backfill the directive forbids labelling point-in-time. Rejected. |
| GitHub release asset history | GitHub retains only the *current* version of each release asset; prior uploads are not kept. No per-week vintage recoverable. |
| Wayback Machine (`archive.org`) snapshots of nfl.com/injuries | **HTTP 000 — blocked by this executor's egress proxy.** Not tested on its merits. |
| This project's own live capture track | 31 `official_injury_report` captures — all **2026**. Cannot reach backwards. |

**Documented for the agent that has network**, per §13's disclosure requirement:

- **Source:** Internet Archive Wayback Machine, `https://www.nfl.com/injuries/league/{season}/REG{week}`.
- **Dates needed:** 2025 weeks 1–18, ideally 2–3 snapshots per week (Wed/Fri/Sun).
- **Timestamps:** Wayback stamps each capture, so chronology would be
  establishable per snapshot — the property `injuries_2025.csv` lacks.
- **Intraweek revisions:** preserved only to the extent the crawler happened to
  capture them; coverage is unknown and must be measured, not assumed.
- **Identifiers:** the page carries no gsis_id (measured in the parser work), so
  the existing `PLAYER_GSIS_UNMAPPED` debt would apply.
- **Authority:** archival copy of an official source — not the official source.
- **Reproducible:** yes, by URL and timestamp.
- **Suitability:** retrospective research only. It must not enter production
  without owner governance, and this report does not import it.

**No backfill was performed and no 2025 injury feature was fabricated.** Every
2025 result in P3 runs without injury information, which is why 2025 remains the
weak season throughout.

---

## 17. Zero-history cohort

| | |
|---|---|
| Player-games with **zero** prior games in the panel | **1,273** |
| Distinct players | **1,273** (each appears once, by definition) |
| WR / TE / RB / QB | 505 / 274 / 341 / 153 |

**These are excluded from every model in P1, P2 and P3**, all of which require
`f_n_prior ≥ 1`. So P2's cold-start finding — that shrinkage harms low-history
players — applies to players with **1–3** prior games and **must not be extended
to these 1,273**. They are ~2.2% of the panel and have no own-history feature at
all, so the priors P2 rejected (position, team-position, depth chart) are the
only inputs available for them and remain untested.

A cold-start model for this cohort is not built here. The sample is large enough
to support one (1,273 player-games), and it is a self-contained P4 question.

---

## 13–15. Selective mixture — candidates, results, and information quality

### Predeclared candidates (`predeclaration_p3.md` §2)

`P0_always_U` (control) · `P1_always_AC` (control) · `P2_info_quality` ·
`P3_uncertain_band` · `P4_zero_persistence` · `P5_scale` · `P6_combined`.

Band endpoints tuned on a fixed 4×4 grid over **2022–2023 only**. **The policy
itself is also chosen on 2022–2023 only** — the first version of this reported,
per evaluation season, whichever policy happened to score best on that season,
which is choosing after seeing the outcome and is what the directive's own probe
12 tests for. That was corrected before any number below was read.

### Results — chosen policy carried unchanged into 2024–2025

| Target | Policy chosen on tuning | Season | U | A×C | Policy | A×C used | vs U | vs A×C |
|---|---|---|---|---|---|---|---|---|
| `snap_share` | `P2_info_quality` | 2024 | 0.1544 | 0.1426 | **0.1389** | 18% | **−0.0152** ✓ | −0.0035 [−.0070,+.0007] |
| | | 2025 | 0.1551 | 0.1574 | **0.1551** | **0%** | 0.0000 = | −0.0025 [−.0061,+.0012] |
| `rpr` | `P2_info_quality` | 2024 | 0.1549 | 0.1458 | **0.1398** | 18% | **−0.0149** ✓ | **−0.0058** ✓ |
| | | 2025 | 0.1564 | 0.1609 | **0.1564** | **0%** | 0.0000 = | **−0.0046** ✓ |
| `target_share` | `P5_scale` | 2024 | 0.0469 | 0.0431 | **0.0431** | 100% | **−0.0037** ✓ | 0.0000 = |
| | | 2025 | 0.0460 | 0.0453 | **0.0453** | 100% | **−0.0007** ✓ | 0.0000 = |
| `carry_share` | `P4_zero_persistence` | 2024 | 0.1261 | 0.1082 | **0.1084** | 73% | **−0.0175** ✓ | −0.0001 [−.0034,+.0033] |
| | | 2025 | 0.1056 | 0.1030 | **0.0961** | 74% | **−0.0095** ✓ | **−0.0069** ✓ |

Against the acceptance rule fixed in advance — beat **both** controls on
2024–2025 — the honest verdict is **partial**:

- **beats U** on 6 of 8 test-season comparisons and ties it on the other 2;
- **beats mechanical A×C** on 3 of 8; ties on 3 (two of them structurally,
  since `P5_scale` on a small-scale target *is* always-A×C); never loses.

### What the policy actually buys, and it is not what I expected

**`P5_scale` is degenerate and should be read as such.** For `target_share` it
selects A×C for 100% of rows, so it is `P1_always_AC` wearing a different name.
Its zero difference is arithmetic, not evidence.

**The real result is 2025.** P2 found that mechanical A×C is *worse* than U in
2025 — the season with no usable injury vintage. `P2_info_quality` uses A×C on
**0% of 2025 rows**, because the HIGH class requires a current-week injury row
with a pre-kickoff timestamp and 2025 has none. So the policy degenerates to U in
exactly the season where A×C hurts, and the 2025 regression disappears:

| | 2025 snap_share | 2025 rpr |
|---|---|---|
| U | 0.1551 | 0.1564 |
| mechanical A×C | 0.1574 (**worse than U**) | 0.1609 (**worse than U**) |
| selective | **0.1551 (= U)** | **0.1564 (= U)** |

**That is the answer to Q4 and to §12's hypothesis together.** The selective
policy's value is not that it finds extra accuracy; it is that it declines to
use the mixture when the information feeding it is absent. P2's hypothesis —
that the model is only as good as the appearance information — is confirmed, and
the information-quality flag is a sufficient pregame signal to act on it.

### The price of predeclaration, stated

Where the chosen policy is not the per-season best, the gap is the cost of not
choosing after the fact:

| Target / season | chosen | oracle (post-hoc) | cost |
|---|---|---|---|
| `snap_share` 2025 | `P2_info_quality` 0.1551 | `P4_zero_persistence` 0.1508 | **0.0043** |
| `rpr` 2025 | `P2_info_quality` 0.1564 | `P4_zero_persistence` 0.1538 | 0.0026 |
| `carry_share` 2024 | `P4_zero_persistence` 0.1084 | `P5_scale` 0.1082 | 0.0002 |

Reporting the oracle alongside the honest number is the point: a P3 that quoted
0.1508 for 2025 would have looked better and meant less.

### §12 information-quality stratification

Classes defined structurally in advance: **HIGH** = a current-week injury row
exists whose own `date_modified` precedes kickoff — **retrospective chronology
defensibility, not prospective capture integrity**; see
`NFL_P3_ADDENDUM_R1.md`, which corrects this wording and measures the exposure
(99.09% of rows stamped >24h before kickoff, none inside the final 90 minutes); **MEDIUM** = none for this player but ≥1 for his
team this week and ≥4 prior games; **LOW** = neither.

Population: HIGH 7,847 · MEDIUM 31,634 · LOW 12,849.

Stage A Brier by class (P2 → P3 features):

| Season | HIGH | MEDIUM | LOW |
|---|---|---|---|
| 2023 | 0.0934 → **0.0891** (n=1,567) | 0.1408 → **0.1369** (n=6,873) | 0.1371 → 0.1351 (n=479) |
| 2024 | 0.0852 → 0.0873 (n=1,577) | 0.1365 → **0.1324** (n=6,758) | 0.1587 → 0.1578 (n=496) |
| 2025 | — | — | 0.1544 → 0.1538 (n=8,896, **all LOW**) |

**A caveat that matters for reading this.** HIGH has the *lowest* Brier, but
HIGH is not "a randomly chosen player about whom we know more" — it is "a player
who is on the injury report", which is a different and more predictable
population (many are designated Out). The classes are confounded with who they
select, so the HIGH−LOW gap is **not** a clean estimate of the value of
information. What is clean is the 2025 row: an entire season forced into LOW,
and that is where mechanical A×C fails.

---

## 18. Ablation table

Stage A, leave-one-group-out, change in Brier when the group is removed
(the block is removed entirely, not zeroed, so a dropped group cannot leave its
intercept behind):

| feature group | 2022 | 2023 | 2024 | verdict |
|---|---|---|---|---|
| **teammate availability** | +0.0011 | +0.0011 | +0.0014 | largest P3 addition |
| **role volatility** | +0.0006 | +0.0016 | +0.0011 | second |
| absence history (workload before absence) | +0.0009 | +0.0014 | +0.0009 | third |
| **practice progression** | −0.0000 | +0.0008 | +0.0001 | **no contribution** |

For scale, P2's ablation put **history rates at +0.025 to +0.033** and **injury
designation at +0.008 to +0.009**. Every P3 addition is an order of magnitude
smaller than the P2 injury feature and two orders below prior appearance rates.

**That ordering is the honest summary of Track A**: the availability information
that matters is the injury designation P2 already had, and the marginal returns
to engineering more features around it are small.

## 19. Features that helped

- **the identifier repair** — not a model feature, and the largest single
  improvement in P3 by any measure (4.630% → 0.132% row loss)
- teammate availability by opportunity class (+0.0011 to +0.0014 Brier)
- prior role volatility and swing (+0.0006 to +0.0016)
- workload immediately before an absence (+0.0009 to +0.0014)

## 20. Features that failed to help

- **cross-week practice progression** — no measurable contribution, and the
  intraweek version it stands in for does not exist in the data at all
- (carried from P2, unchanged) position indicators, team change, shrinkage for
  low-history players, proportional redistribution, Model C standalone

## 21. Unsafe or unavailable inputs

| Input | Status |
|---|---|
| `weekly_rosters.status` | **quarantined**, not used |
| intraweek practice sequence | **does not exist historically** — one row, one timestamp per player-week |
| injuries 2025 | **unusable** — no `date_modified`; no archival substitute reachable (§16) |
| `depth_charts` 2025 | schema changed to daily snapshots; used 2020–2024 only |
| fuzzy name matching | **available and deliberately unused** — `Crosswalk.map_by_name` |
| `weekly_rosters.pfr_id` bridge | **rejected** — 77.51% coverage, non-injective |
| true routes run, `ngs_air_yards`, air-yards share | unchanged from P1/P2 |
| market variables, nflfastR model fields, 2026 outcomes | excluded by rule |

## 23. Remaining data and identifier debts

| Debt | State |
|---|---|
| `PLAYER_GSIS_UNMAPPED` on the official injury page | **open** — the page carries no gsis_id |
| 168 snap rows `PFR_ID_UNMAPPED` | **open, and now bounded** — 0.11%, no positional concentration |
| 2025 point-in-time injury vintage | **open** — see §16; needs the networked agent |
| intraweek practice progression | **open acquisition need**, not a modelling gap |
| `prediction_time_eligibility` | **open** — Stage A is the model that consumes it |
| zero-history cohort (1,273 player-games) | **open** — untested, outside every model here |
| broadcast UUID join, `.reduced` blob hash naming | unchanged |

---

## 24. Recommendation for P4

**The information is now about as good as history allows. The binding
constraint has moved from modelling to acquisition, and P4 should say so with
its scope.**

**1. Stop adding availability features to the historical panel.** P3's four new
groups together contribute less than the single injury designation P2 already
had, and the one that should have mattered most — practice progression — cannot
be built at all, because the historical file holds one row per player-week. That
is not a modelling failure to fix with better features; it is a data property.

**2. The acquisition targets are specific and small.** In descending value:
 - **intraweek practice progression**, which only the live capture track can
   produce and which no historical file contains;
 - **2025 point-in-time injury vintage** via Wayback (§16) — needs the agent
   with network, and would restore the season that breaks every mixture result;
 - **transactions / elevations**, still `ENDPOINT_NOT_YET_VERIFIED`.

**3. Role transition is where the remaining modelling headroom is, and it is
asymmetric.** Losing a role is predictable (AUC 0.84); gaining one is not
(0.77). P4 should treat *inheritance* as its own question rather than as the
mirror of departure — that is the same asymmetry the redistribution experiments
found from the other side, and it has now appeared three times.

**4. Build the zero-history cold-start model, or declare it out of scope.**
1,273 player-games sit outside every model in P1–P3. That is small but not
negligible, and it is exactly the Week-1 rookie case a live system meets first.

**5. Do not enlarge the model class.** Nothing in P1, P2 or P3 suggests the
ceiling is model capacity. Every gain so far has come from better information or
from an honest decomposition, and every attempt to add machinery has returned
less than the last.

**What I would not do in P4:** fantasy points, touchdowns, efficiency, boosted
trees, joint simulation, DFS, markets.

## 26. Markdown task-report path

`TASK_REPORT_2026-09-07_P3.md`, repository root.
Addendum: `NFL_P3_ADDENDUM_R1.md` — external evidence review, the clock-taxonomy
correction to my own wording, and the recorded R2/R3/capture backlog.

---

## Governance

Quarantined retrospective research. Nothing is promoted for having improved a
historical metric and no promotion is requested. **G0A remains 11/12**, Item 1
remains PARTIAL / PENDING REAL EVENT, NFL-1 remains unexecuted. 2026 outcomes
untouched; no frozen 2026 artifact modified. No fantasy-point, touchdown,
efficiency, DFS, ownership, lineup, market or wagering work was done. No wager
is recommended or discussed.
---

## 25. Files changed

Research artifacts only. No production module, no G0A file, no capture path, no
2026 artifact touched.

```
A  nfl/research/p3/predeclaration_p3.md    written before any policy result
A  nfl/research/p3/build_panel_p3.py       identifier-joined panel
A  nfl/research/p3/p3_features.py          availability + teammate + volatility
A  nfl/research/p3/run_p3a.py              Stage A, ablation, info quality
A  nfl/research/p3/run_p3b.py              eight role-transition targets
A  nfl/research/p3/run_p3c.py              selective mixture, zero-history
A  nfl/research/p3/run_p3_adversarial.py   28 probes + 2 guard-deletion proofs
A  nfl/research/p3/*.json, *.log           every metric and every run log
A  TASK_REPORT_2026-09-07_P3.md            this file
```

### Two mistakes of my own, recorded

**I misread a hardcoded log line as a filename** — `build_panel_p3.py` prints
`"wrote panel.csv"` as a literal while writing `panel_p3.csv` — and my own `mv`
then overwrote the repaired panel with the stale one. Caught by checking the
file's contents (2,670 missing rows, not 76) rather than trusting the message.
Later, two of my own concurrent background rebuilds raced and one deleted the
other's output. Both cost time and neither reached a reported number: every
figure above is from the verified panel with 76 missing rows.

**I initially reported, per evaluation season, whichever selective policy scored
best on that season** — choosing after seeing the outcome, which §10 forbids and
§16 probe 12 tests for. The policy is now fixed on 2022–2023 and carried
unchanged into 2024–2025, and the oracle gap is reported.
