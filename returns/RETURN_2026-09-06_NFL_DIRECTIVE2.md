# Return: NFL Greenfield — Owner Directive 2 correction pass

**Date:** 2026-09-06 · **Branch:** `claude/nfl-greenfield-architecture-stsxmk`
**Scope honoured:** no advanced opportunity, skill, simulator, DFS or market
predictive production code was written. One specification was **frozen**, not
implemented.

Three of the corrections found real defects rather than imprecision, and two of
those were mine. They are stated first in each section rather than buried.

---

## 1. Revised roadmap with G0A/G0B

`nfl/NFL_EXPERIMENTAL_ROADMAP.md` — revision 2. Revision 1 is preserved in git.

The contradiction was real: G0 required ≥2 weeks of reconciliation before NFL-1,
while NFL-4 required predictions sealed from Week 1. **Governance would have
consumed the evidence it exists to protect.**

**G0A — pre-kickoff integrity gate.** Blocks execution of any frozen predictive
baseline. Twelve requirements, exactly as specified in the directive.

**G0B — evidence-system maturation.** Runs concurrently after G0A. Holds the ≥2
weeks reconciliation, match rate as a first-class metric, owed-`DEFERRED` closure
behaviour, operational monitoring, and long-running source checks. Blocks
promotion, not start.

**No control was weakened to achieve the split.** Every revision-1 requirement
survives; each was allocated to the gate it actually belongs to. Nothing moved
from "required" to "optional", and nothing was softened in wording.

---

## 2. G0A checklist and current state

Full per-item audit with evidence: `nfl/NFL_G0A_CHECKLIST.md`. Audited against
code at commit `196aa4b`, not against design intent.

**2 PASS · 10 FAIL · 0 DEFERRED.**

| # | Requirement | State |
|---|---|---|
| 1 | Kickoff-anchored capture scheduled and running | **FAIL** — two manual invocations; `/etc/cron.d` empty, `crontab -l` empty; tool has no game-date concept |
| 2 | Raw bytes before parse | **PASS** (durability defect, below) |
| 3 | Append-only / content-addressed | **PASS** (durability defect, below) |
| 4 | Complete five-clock provenance | **FAIL** — `effective_for_date` absent; `Provenance` named only in a docstring; `validate()` never called |
| 5 | sha256 inside execution identity | **FAIL** — hashes recorded; **no NFL execution identity exists** to hold them |
| 6 | Leakage quarantine at ingest | **FAIL** — not implemented |
| 7 | Replay test that fails if quarantine removed | **FAIL** — no NFL test file exists |
| 8 | Denominator-aware non-null validation | **FAIL** — not implemented |
| 9 | Named `PFR_ID_UNMAPPED` + replay test | **FAIL** — not implemented |
| 10 | Draw-archive schema frozen incl. `cross_game_dependence` | **FAIL** — prose, not an artifact |
| 11 | `written_at` / `captured_at` / kickoff ordering | **FAIL** — not implemented |
| 12 | Seal a forecast immutably before kickoff | **FAIL** — not implemented |

**Nothing is recorded DEFERRED.** DEFERRED means *not yet, and owed by something
specific*. These are unbuilt. Calling unbuilt work deferred is the attractive lie
Rule 001 exists to refuse, and it would have made this table look far better than
the system is.

**A durability defect is recorded against the two passing items**, rather than
taking the technicality. The raw blobs live in `nfl_vintage/`, gitignored and in
an ephemeral container. The manifest is committed and survives; **the bytes it
attests to do not.** A hash with no retrievable bytes proves only that something
once existed — **this is the M0 failure in advance.** Proposed fix is
size-differentiated: commit the injury blobs (~0.8 MB/capture, the only
irreplaceable stream, ~14 MB/season), reduce or diff the 48 MB depth-chart
captures since upstream retains its own `dt` history.

---

## 3. Week-1 cold-start specification — **frozen**

Specification and evidence: `nfl/research/C3_COLD_START_SPEC.md`.
Freeze record: `nfl/NFL_COLDSTART_FREEZE.json`.

**Frozen 2026-09-06T19:37:33Z**, spec sha256 `b356ecaa…9b9fa`, against `games.csv`
snapshot `c563178a…8fda9`. Verified on that exact hashed snapshot at freeze time:
**272 REG rows for 2026, 272 of 272 with null `result` and null `home_score`.**

**Form.** A shrunk prior-season prior blended into season-to-date by
`θ_g = g/(g+M)`. Week 1 needs no special branch — it is the schedule at `g = 0`.
Constants: `λ_off = 0.430572`, `λ_def = 0.414683`, `M_off = 8.8764`,
`M_def = 23.2199`, plus a home term `h`. Inputs are prior-season final scores
only, all present today, all fixed before kickoff.

**What the evidence does and does not support.** All five candidate families land
between r = 0.3238 and 0.3420; the game-clustered 95% CI on r is **~0.21 wide**
against a 0.018 spread, so **the families cannot be ranked and the document does
not rank them.** The only resolved comparison is that a prior-season prior beats
the league mean (paired ΔRMSE +0.4405 [+0.2295, +0.6515]).

Two independent routes to the shrinkage agree: variance components give
λ_off = 0.4265 / λ_def = 0.3886; OLS on 23 season-pairs gives 0.4306 / 0.4147.
Roster discontinuity is the reason regression is heavy — YoY team-scoring
persistence decays r = 0.3475 → 0.2703 → 0.1425 → 0.1340 across lags 1–4.

**Against over-fitting:** a 17-parameter per-week θ curve fitted **in sample** is
**0.0074 RMSE worse** than the two derived constants. The bootstrapped argmin for
M is not well resolved (M_off [6,12], M_def [16,48]) and the whole plausible
region sits within 0.6% of best RMSE — reported as unresolved, not as a curve.

**One owner ruling is open, with a hard deadline.**

> **T1 — estimation-window floor: 2002 (specified) vs recent-era.** λ moves
> 0.43 → 0.53, h moves 2.19 → 1.57, but scorecards are indistinguishable
> (ΔRMSE +0.0117, CI [−0.0372, +0.0595]). Evidence favours 2002: the short window
> is dominated by 2019–2020 (h = −0.14, +0.05) while the most recent block is
> +2.15, near the long-run +2.19.
> **Any change must land before 2026-09-09.** Revising a constant after the first
> result forfeits the fixed-holdout property for the whole season.

Also flagged: **T3** — the home term is the weakest element, paired CI
[−0.0361, +0.1840] does not clear noise; setting `h = 0` requires no other change.

**Not asserted by the freeze:** that the spec is implemented (it is not),
executed, checked against its own worked example (`29.109936` — that is G1's job
under predeclared tolerance), or optimal.

**Also caught:** points-allowed is **provably identical** to points-scored on this
frame, to machine precision. Reporting it as separate evidence would be exactly
the nested-list double-count `CLAUDE.md` warns about.

---

## 4. Corrected 2026 prospective-evaluation terminology

Revision 1 called the season "a genuinely untouched prospective window" without
qualification. Corrected in both documents:

| Regime | Definition | Strength |
|---|---|---|
| **Fixed prospective holdout** | **One** specification frozen before **any** 2026 outcome, evaluated without adapting to 2026 results | Strong |
| **Sequential prospective evaluation** | Each prediction sealed before its own kickoff, but later versions may have learned from earlier 2026 outcomes | Weaker; **not** a holdout |

The 272-game season **may not be described as a fixed-model holdout** unless the
evaluated model was frozen before the first result. Any mid-season revision
produces sequential evidence only. Both are legitimate; conflating them is not,
and the two are never pooled.

**The permanently frozen Week-1 stream is preserved** — by §3's freeze. Which
leads to item 7.

---

## 5. Audit of the P(play) = 0.943 population

`nfl/research/C1_AVAILABILITY_POPULATION_AUDIT.md`. **This found a real defect of
mine that would have reached production as an availability prior.**

**The 0.943 was measured on the opposite population from the one the state code
names.** `n = 3,386` is exactly the count of blank `report_status` rows in
`injuries_2024.csv` — no join, no roster filter. Reproduced independently: 6,215
rows, 3,386 blank, 3,203 REG, and **3,203 / 3,203 of those carry a
`practice_status`**. The cell is *"named on the practice report with an ailment,
then cleared of a game designation"* — a player the team looked at and passed.
`PLAYER_NOT_ON_REPORT` names players **absent** from the report.

| Population | P(≥1 snap) | n | Bias from flat 0.943 |
|---|---|---|---|
| On practice report, no game designation | 0.9430 | 3,386 | — |
| Off report, **gameday-eligible** | **0.8876** | 24,101 | +0.055 |
| Off report, **roster membership only** | **0.5553** | 38,524 | **+0.388** |
| Practice squad | **0.0000** | — | **+0.943** |

Replicates on 2025 within 0.005 on every cell.

**The obvious fix is also wrong**, and the audit says so: 0.8876 is itself a
mixture marginal — substituting it corrects the label and keeps the defect. Most
of the apparent on-report advantage is **role composition** (the report is 67.6%
depth-1 starters vs 43.7% off-report; standardising on depth rank closes 60% of
the 0.0745 gap).

**Dressed ≠ plays a role**, and this is the largest effect in the audit. Within
the same off-report cell, across prior-week snap-share buckets, P(≥1 snap) moves
0.8505 → 0.9905 while **P(offense_pct ≥ 50%) moves 0.0098 → 0.9325 — a factor of
95.** A skill player with no snaps last week and no designation is **0.4685** to
take a single snap. QBs off-report: P(dressed) 0.9095, P(snap) 0.4783.

**The four-way separation the directive asked for**, measured from data rather
than recalled: gameday active limit **48** (sd 0.34); **46.7** distinct players
take a snap per team-game; eligible pool **54.34**. Production must condition on
roster membership, gameday universe, report presence **and** football role.

Single clearest statement of why report-absence cannot carry a prior alone:
**59% of gameday inactives never appear on the injury report at all.**

**New leakage finding.** `weekly_rosters.status` is a **post-hoc gameday
outcome**, not a roster state: `ACT` → 0.9715 snap rate, `INA` → **0 of 3,438**,
`DEV` → 3 of 8,306. Near-perfect predictor of playing, available only after the
fact. Quarantined at ingest alongside the market columns — which leaves
**prediction-time eligibility currently unsatisfiable from reachable data.**
Recorded as an assignment, not blocked, not stubbed.

---

## 6. Corrected power, pooled r, ffopportunity, market timing

`nfl/research/C2_POWER_AND_CLUSTERING.md`.

**Power — withdrawn as a unit error, not downgraded.** "2,000–3,000
game-equivalents / 7–11 seasons" was `377 × 7.93`: a **game** count for a
**game-level r**, times a **row-level** design effect measured on a
**calibration** statistic.

**This repository had already diagnosed that exact defect.**
`v8/experiments/J2_STOPPING_RULE.md:47-52` records it for MLB, quoting
`J2-handedness-01.md:84` — *"games do not nest inside games"* — and warns that
correcting the square alone yields *"a more precise wrong number"*. Revision 1
inherited the correction to the square and not to the unit. Verified by reading
both files.

**NFL clustering, measured directly.** The design effect is a *function of rows
per player-game*, not a constant:

| Grading design | rows/player-game | DEFF (by game) |
|---|---|---|
| One row per player-game per market | 1.0 | 0.83–1.12 (CIs include 1.0) |
| Eight markets, one line each | 2.9 | 2.39 ± 0.28 |
| Eight markets, laddered | 9.3 | 7.12 ± 0.64 |

**MLB's 7.93 ≈ NFL's 7.12 is coincidence, not validation** — MLB at 31.4
rows/player-game, NFL at 9.3. Per row NFL is *more* coupled. MLB's figure is not
promoted to an NFL constant. Transferable quantity: **~14–19 effective
independent prop observations per game.**

A third layer previously missed: the **discrimination** DEFF is ~**3.5× smaller**
than the calibration DEFF on the same rows.

**Corrected planning figures:** **0.2–1.0 seasons** for broad receiving /
anytime-TD; **2.3–5.9** for QB/RB. So "7–11 seasons" was roughly right for QB
passing and ~**10× too pessimistic for receiving** — treating it as uniform would
have wrongly suppressed the markets with the most supply. Marked planning-level
DERIVED (measured clustering, assumed effect sizes); reported DEFFs are upper
bounds.

**Pooled player r = 0.5907** may not be a promotion target on its own; any use
must carry within-player or residualised metrics alongside. **ffopportunity
r = 0.8419 is not a gate** until outbox A3 confirms the field is genuinely
oracle-opportunity and establishes its information set.

**Market gate timing — conclusion partly survives, reasoning does not.** 369 was
never per-market supply and the gate is per market: measured week-1 supply is
**152** (`rec_yds`), **39** (`rush_yds`), **34** (`pass_yds`). The binding
constraint was never rows — it is **`min_distinct_dates = 10`**, with cumulative
gamedays 4/7/10, making **week 3 a calendar floor**. "Fast" holds for **3 of 8**
markets; `rush_yds` and `pass_yds` need **8–11 weeks**.

**The 300 floor was not re-scaled, deliberately.** `board_config.json` sets
`gate_floor_unit: "rows"` under a 2026-08-30 ruling: *"count ROWS … correlation is
handled in the estimator rather than by discarding rows."* Applying a DEFF to the
floor would contradict a ruling already made. Both readings are tabulated; neither
is presented as the rule; **`board_config.json` was not changed.** Noted without
proposing it: raising `min_distinct_player_games` would be a smaller, more
auditable lever — an owner call.

**Trigger stays `DEFERRED` / "≥5 seasons"**, with six named prerequisites. One is
perishable and belongs to the networked researcher: **Hard Rock NFL market list
and ladder depth** — that single number selects between columns differing 3–6×.

---

## 7. Can G0A pass without weakening any gate?

**No — not today, and not by 2026-09-09 in a form that would let a baseline
execute.** Ten controls are unbuilt; four of them (10, 11, 12, and the execution
identity in 5) are exactly what a sealed forecast depends on; item 12, the
sealing capability itself, does not exist in any form.

Ten controls plus their replay tests in three days would mean writing guards and
the tests that check them under deadline pressure. That is the precise condition
that produces `assert_batch_games_are_new` — a guard that passed on every input
it was ever given because it read a field no row carried. It is in this
repository.

**But the Week-1 evidence is not lost, and the reason is the useful part of this
return.**

The property making 2026 a fixed prospective holdout is that **the specification
was frozen before any 2026 outcome existed** — not that predictions were executed
pre-kickoff. §3's freeze establishes that at 19:37Z today, verified against a
snapshot with 272/272 null results. The spec can therefore be **executed after
G0A passes** and the holdout property still holds for every week it covers.

So the three-day deadline was never the baseline build. It was (a) the capture,
already running and already accepted, and (b) **the specification freeze, now
done.** Neither required weakening a control.

Residual risk, stated rather than hidden: the freeze is only as good as the
spec's determinism. If implementation reveals genuine ambiguity, the honest
response is to record that the fixed-holdout claim is weakened, **not** to patch
the constants and keep the claim.

---

## 8. Exact artifacts and tests if NFL-1 is authorised

Nothing below has been written. This is the manifest that would be created.

### 8a. G0A controls — prerequisite, before any baseline executes

| Artifact | Closes |
|---|---|
| `nfl/ingest/allowlist.py` | 6 — exhaustive column allowlist; named `MARKET_COLUMN_ACCESS`, `COLUMN_NOT_ALLOWLISTED`, `POSTHOC_COLUMN_ACCESS`. Covers the 14 market columns, `result`/`total`, `away_qb_id`/`home_qb_id`, **`weekly_rosters.status`**, and the 31 unconfirmed model-derived columns |
| `nfl/ingest/validate.py` | 8 — per-column non-null assertions **scoped to the denominator the field is defined on** (the coverage columns are 51.2% blank file-wide, 0.23% on dropbacks) |
| `nfl/ingest/identifiers.py` | 9 — named `PFR_ID_UNMAPPED` FAIL instead of a silent inner join |
| `nfl/identity/execution_identity.py` | 5 — NFL execution identity **consuming** the capture manifest's sha256 per partition |
| `nfl/identity/seal.py` | 11, 12 — immutable pre-kickoff forecast seal; enforces `written_at < captured_at < kickoff` |
| `nfl/schema/draw_archive.schema.json` | 10 — frozen, versioned, hashed; **`cross_game_dependence` required** |
| `nfl/tools/capture_vintage.py` (extend) | 1, 4 — kickoff-anchored cadence from `games.csv`; construct and `validate()` a real `Provenance` incl. `effective_for_date` |
| blob durability change | 2, 3 — commit injury blobs; diff/reduce depth charts |

### 8b. G0A tests — each must fail when its control is removed

`nfl/tests/test_quarantine.py` · `test_denominator_validation.py` ·
`test_identifier_mapping.py` · `test_seal_ordering.py` ·
`test_provenance_clocks.py` · `test_capture_states.py`

Seeded from real defects, not imagination: a market column reaching a forecast
function; a column empty on its own denominator vs blank where undefined; the 6
unmapped snap rows where a name fallback **silently mis-joins 2**; a forecast
written after kickoff; a cache hit claiming fresh retrieval; `EMPTY_PAYLOAD_200`
and `SOURCE_NOT_YET_PUBLISHED` as distinct states.

**Each test must be demonstrated failing with its control deleted.** A quarantine
whose test still passes when the quarantine is removed is not enforcement.

### 8c. NFL-1 artifacts

| Artifact | Purpose |
|---|---|
| `nfl/experiments/NFL1_PREDECLARATION.md` | Reproduction tolerances, metrics, clustering and multiplicity **hashed before the run** (Rule 004a) |
| `nfl/baseline/coldstart.py` | Implementation of the frozen spec. Consumes only the allowlist; no RNG |
| `nfl/baseline/NFL1_BASELINE_FREEZE.json` | Execution identity + input manifest hashes of the frozen control |
| `nfl/baseline/scorecard_nfl1.json` | Full **linked** scorecard — r, SD ratio, slope together — plus CRPS, PIT, coverage |

### 8d. NFL-1 tests

- `test_coldstart_reference_values.py` — the worked example must return
  **29.109936**; the full 32-team 2025 input table reproduces.
- `test_coldstart_determinism.py` — bit-identical across two runs and two
  processes; asserts no RNG is reachable.
- `test_coldstart_no_market_access.py` — AST/import defence modelled on
  `v7/test_price_capture.py`; **fails if the allowlist is removed.**
- `test_coldstart_week1_no_special_case.py` — Week 1 is `g = 0` in the same
  schedule, not a branch.

**G1 exit:** reproduces within predeclared tolerance, reruns bit-identically
under one execution identity, every input hashed inside that identity, full
linked scorecard emitted. **Improvement is not required at G1** — that is NFL-2's
burden against this control.

---

## 9. What I did not do

No advanced opportunity, skill, simulator, DFS or market predictive production
code. No broad external research duplicating the networked researcher — every
measurement above came from data already cached or from nflverse, which this
environment can verify directly. `board_config.json` was not modified. No
constant was tuned. Nothing was stubbed or mocked.

**Three defects of mine were found and are recorded rather than edited away:**
the 0.943 population, the power unit error, and the market-gate reasoning. The
second is the one worth remembering — it repeated a mistake this repository had
already diagnosed and written down.

---

## 10. Decisions waiting on you

1. **T1** — cold-start estimation window, 2002 vs recent-era. **Before 2026-09-09.**
   Default stands at 2002 if you say nothing; evidence favours it.
2. **T3** — retain or zero the home term. No deadline; `h = 0` needs no other change.
3. **Authorise the G0A build?** It is not predictive code and it is the gate's
   prerequisite. Not started, awaiting your word.
4. **`min_distinct_player_games`** — noted as a smaller, more auditable lever than
   redefining the row unit. Not proposed, not actioned.
