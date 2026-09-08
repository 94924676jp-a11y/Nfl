# RECEIVING INFORMATION GAP RETURN

Information qualification study. **No predictive model was built.** Nothing here
promotes, freezes, or authorises anything.

Executed 2026-09-08. Start HEAD `f2a73a3`. Every figure below was measured in
this session unless it carries the tag `UNVERIFIED-RECALL`.

---

## 1. Canonical state

| | |
|---|---|
| Canonical repository | `94924676jp-a11y/Nfl` |
| HEAD at start | `f2a73a3` — pre-declaration of the proxy probe |
| Commits added by this study | `90585aa` (probe void addendum), plus this return |
| Working tree | clean before and after; all builds wrote to a scratchpad |

**`R11` does not exist.** A filesystem search and a content grep across the
canonical tree return nothing for `R11` — no artifact, no reference in any
markdown or JSON. The directive's assumed baseline is absent, so no part of this
return is scored against it.

The most recent completed research units, and their recorded verdicts:

| Unit | Verdict | Where |
|---|---|---|
| S4 oracle decomposition | A 11.73% / T 13.84% / P 28.47% / R 45.95% | `nfl/research/s4/s4_results.json` |
| R1 target rate given participation | `SIGNAL_WEAK` / `RETAIN_P4C` | `nfl/research/r1/r1_ladder.json` |
| P recoverability | `P_SIGNAL_WEAK` / `RETAIN_P_DEVELOPMENT_CANDIDATE` (`ewma_hl1`) | `nfl/research/p1s/p_study.json` |

---

## 2. Current receiving state

The project's receiving chain is decomposed **A × T × P × R** — appearance,
team pass volume, participation, allocation given participation.

| Component | Shapley share of total target error | Best result on record |
|---|---|---|
| A appearance | 11.73% | MULTIPLE_INDEPENDENT_TESTS |
| T team volume | 13.84% | MULTIPLE_INDEPENDENT_TESTS |
| **P participation** | **28.47%** | best simple `ewma_hl1`; best ladder rung `P0` — **no feature block beat the control**; per-season gain over control 1.18%–2.55%, **0 of 4 seasons** cleared the 5% bar |
| **R allocation** | **45.95%** | best rung `R_ABCD`, +7.18% relative MAE over the position mean, **0 of 4 seasons** cleared the 10% bar; downstream substitution made CRPS **worse** |

**P is pass-snap participation — an upper bound on route participation.** A
player on the field for a dropback may block. It is not routes run, and no
number in this project has ever been routes run.

The two largest components, P and R, are both stuck against their own controls
using the information currently held. That is what motivated this study. It is a
statement about *the information currently held*, not a ceiling.

---

## 3. True routes inventory — source by source

"True routes run" means a **per-player, per-game count of routes run on
pass plays**, attributable to a player identifier.

| Source | Reachable from here | Carries per-player routes run? | Evidence |
|---|---|---|---|
| `nflverse pbp_participation` | YES, 2016–2025 (200); 2026 **404** | **NO** | 26 columns. Column 18 is `route`, a **single route-type string per play** — `QUICK OUT`, `HITCH/CURL`, `GO`, `SCREEN`, `IN/DIG`… — populated on 18,871 of 45,184 plays (41.8%) in 2025, with **no player identifier attached**. It describes the targeted receiver's route on that play. It is one route on one play, not a count per player. Per the directive it is **not** reinterpreted as routes run. |
| `nflverse ftn_charting` | YES, 2025 (200) | **NO** | 29 columns, all play-level and QB/pressure-centric: `is_play_action`, `is_screen_pass`, `is_rpo`, `n_blitzers`, `n_pass_rushers`, `read_thrown`, `is_catchable_ball`. No receiver-level field of any kind. |
| `nflverse pfr_advstats` week receiving | YES (200) | **NO** | 17 columns: broken tackles, drops, drop pct, int, rating. No routes. |
| `nflverse pfr_advstats` season receiving | YES (200) | **NO** | 25 columns: `tgt rec yds td x1d ybc ybc_r yac yac_r adot brk_tkl rec_br drop drop_percent int rat`. No routes. |
| `nflverse snap_counts` | YES, 2016–2025 (200); 2026 **404** | **NO** | 16 columns: `offense_snaps`, `offense_pct`, `defense_*`, `st_*`. **No pass/run split**, so it cannot even bound pass-play participation. |
| `nflverse nextgen_stats` receiving | Partially — `ngs_2025_receiving.csv` **404**, `ngs_receiving.csv` **404**, `ngs_receiving.csv.gz` 200 but the 200 is a "Not Found" body | **NOT ESTABLISHED** | The asset naming could not be resolved from here. The GitHub **releases API is blocked for this session** (`api.github.com/repos/nflverse/nflverse-data/releases` returns a scope refusal), so the release index cannot be enumerated. NGS receiving is separation/cushion/air-yards-share in every description I hold — `UNVERIFIED-RECALL` — and no NGS product I can name publishes routes run. |
| PFF | **NO** — `pff.com`, `www.pff.com` return `000` (proxy refuses CONNECT) | **UNKNOWN** | See §5. |
| Sports Info Solutions | **NO** — `sportsinfosolutions.com` returns `000` | **UNKNOWN** | See §5. |
| SportsDataIO | **NO** — `sportsdata.io` returns `000` | **UNKNOWN** | See §5. |
| NFL Next Gen Stats site | **NO** — `nextgenstats.nfl.com` returns `000` | **UNKNOWN** | See §5. |
| Stathead / PFR subscription | **NO** — `stathead.com` returns `000` | **UNKNOWN** | See §5. |

**Result: no source reachable from this executor carries true routes run.** That
is a complete statement about the free/open sources; it is **not** a statement
about the vendors, which are unqualified rather than negative.

W4 already recorded this conclusion for `pbp_participation`
(`nfl/research/W4_RECEIVER_OPPORTUNITY.md:97–106`). This study re-derived it
from live 2025 schemas rather than quoting it.

---

## 4. Pregame role / participation state inventory — source by source

"Pregame role state" means a record of a player's expected role **as it stood
before kickoff**, retrievable at that time — depth position, injury designation,
inactive status, snap-role expectation.

| Source | Historical as-of record 2022–2025 | Prospective | Evidence |
|---|---|---|---|
| Project vintage capture | **NONE** | **LIVE** | `nfl/vintage_manifest.jsonl` holds 663 rows, **every one `season: 2026`**, `capture_id` spanning `20260906T185049Z` → `20260908T124251Z`. 533 PASS, 90 BLOCKED, 40 DEFERRED. 265 stored blobs. **The project's entire point-in-time record begins 2026-09-06.** |
| Captured sources | — | 8 | `injuries` 87, `depth_charts` 87, `schedules` 87, `weekly_rosters` 87, `official_injury_report` 81, `official_inactives` 78, `espn_injuries_json` 78, `official_transactions` 78 |
| **`pbp_participation`** | — | **NOT CAPTURED** | Absent from the vintage source list |
| **`snap_counts`** | — | **NOT CAPTURED** | Absent from the vintage source list |
| `nflverse injuries` final files | Final state only | 2026 file now 200, Last-Modified `Mon, 07 Sep 2026` | A final file is an overwritten file. Per the standing constraint, a final-file modified time **does not** prove historical retrievability, and none is claimed. |
| `weekly_rosters.status` | — | — | **Forbidden as a feature** by standing constraint; not evaluated. |

**Result: there is no as-of pregame role record for any development season.**
The P study located the accepted control's residual precisely in role
transitions — R² 0.753 stable versus 0.496 / 0.498 up / down, with a lag bias of
−0.027 rising and +0.038 falling — and the obvious external fix for that residual
**cannot be tested on 2022–2025 at all**, because the record does not exist.

### A prospective availability finding that constrains everything else

`pbp_participation_2026.csv` → **404**. `snap_counts_2026.csv` → **404**.
Measured 2026-09-08, after the 2026 season has opened.

**The entire participation feature family — P itself, and every prior-only
feature derived from it, including the personnel proxy probed in §8 — is
currently unavailable prospectively.** Historical publication timing does not
resolve this: `pbp_participation_2025.csv` was last modified `10 Feb 2026`,
after that season ended, and `pbp_participation_2024.csv` on `04 Sep 2025`.
Those are final-write times and, per the standing constraint, prove nothing
about in-season availability in either direction.

This is not a reason to stop; it is a fact that any prospective receiving plan
has to survive, and it should be watched rather than assumed.

---

## 5. Vendor qualification

**Every vendor-specific field is `UNKNOWN — NOT VERIFIABLE FROM THIS
EXECUTOR`.** The egress proxy refuses CONNECT to every vendor domain. Measured
2026-09-08:

| Host | HTTP |
|---|---|
| `api.github.com` | 200 |
| `raw.githubusercontent.com` | 301 (follows to 200) |
| `pff.com` / `www.pff.com` | **000** |
| `sportsdata.io` | **000** |
| `nextgenstats.nfl.com` | **000** |
| `sportsinfosolutions.com` | **000** |
| `stathead.com` | **000** |

| Field | PFF | SIS | SportsDataIO | Stathead |
|---|---|---|---|---|
| Publishes per-player routes run | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Historical depth | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Delivery latency / in-season cadence | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Point-in-time or restated | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Licence terms for model use | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Redistribution terms | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| Price | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

There is **no committed evidence** in the canonical repository on any of these
either — `R11` does not exist, and nothing else in the tree records a vendor
qualification. So the table cannot be filled from memory or from the repo.

I will not write down a recalled price, a recalled licence term, or a recalled
historical depth. Per the standing constraint, **rights are not inferred from
silence**, and an unqualified vendor is not a negative result.

**No vendor was contacted. No account was created. No money was spent.**

### The one identity-quality question that *is* answerable, and its answer

If routes data were ever acquired, it would have to join to this project's
players **deterministically** — fuzzy name matching is forbidden. That is
checkable here, and it clears:

Measured against the actual WR/TE/RB study frame — 47,215 player-games,
1,126 distinct players — using the `nflverse players.csv` crosswalk
(Last-Modified `08 Sep 2026`):

| Identifier | Players covered | Player-games covered |
|---|---|---|
| `pff_id` | 1,126 / 1,126 = **100.0%** | 47,215 / 47,215 = **100.0%** |
| `nfl_id` | 1,126 / 1,126 = **100.0%** | 47,215 / 47,215 = **100.0%** |
| `pfr_id` | 1,120 / 1,126 = 99.5% | 47,125 / 47,215 = 99.8% |

The naive whole-file figures are much worse — `pff_id` is present on only
11,615 / 24,826 rows of `players.csv` — but that shortfall is a long tail of
historical and never-active players this project does not model. **Within the
frame, identity is not a blocker.** This is the one vendor-relevant field that
came back green, and it is worth knowing before any acquisition decision.

---

## 6. Same-day acquisition

| | |
|---|---|
| **Verdict** | **NO.** Nothing carrying true routes run can be acquired today from this executor. |
| **Best option if public** | None exists. Every reachable open source was enumerated in §3 and none carries the quantity. |
| **Cost if public** | Not applicable — there is no public source to price. |
| **Rights status** | For what *is* reachable: `nflverse-data` is **CC BY 4.0**, verified by fetching `LICENSE.md` from the repository and reading `Attribution 4.0 International` in the header. Model use with attribution is permitted. For vendors: UNKNOWN, per §5. |
| **Time to use** | For nflverse-derived personnel/formation features: **already built and already tested** — see §8; the answer was no signal. For true routes: not estimable while the vendor branch is unqualified. |

---

## 7. Value-of-information map

**What each information class would let the project *test*.** Not what it would
improve — the directive forbids that claim and there is no basis for it.

| Information | Component it bears on | Share of total target error | Hypothesis it would let us test |
|---|---|---|---|
| **True routes run, per player per game** | P, and the P/R boundary | P is 28.47%; R is 45.95% | Whether the residual in P is *measurement* rather than *modelling* — i.e. whether P's known upper-bound slack (blocking snaps counted as participation) is where the 28.47% sits. This is the only hypothesis that can separate "our participation number is the wrong quantity" from "participation is hard to forecast". **Nothing currently held can separate those two.** It would also re-express R on a routes denominator (targets per route) instead of a snaps denominator, which is a different estimand from the one R1 tested and not a re-run of it. |
| **Pregame role state, as-of** | P, and A | P 28.47%, A 11.73% | Whether the P control's role-transition residual — R² 0.753 stable vs 0.496/0.498 up/down, lag bias −0.027 rising / +0.038 falling — is recoverable from information that existed before kickoff. Today this is untestable on 2022–2025 for want of an as-of record, not because it was tested and failed. |
| **Personnel / formation usage (already held)** | P | — | Tested in §8. No detectable incremental signal. |

Two limits on this map, stated because they are easy to lose:

- **Oracle opportunity is not recoverability.** S4's own caveat. A 45.95% share
  makes R the best *question*, and R1 then recovered little of it. A share is
  not a promise.
- **Personnel is not routes.** A weak personnel result says nothing about
  routes. This was fixed in writing before the probe ran and it still holds.

---

## 8. Existing proxy adequacy — the pre-declared probe, and why it was voided

### 8.1 What was asked, before any result existed

`predeclaration_proxy_probe.md`, committed at `f2a73a3` **before the probe ran**:
does prior-game personnel and formation usage contain *any* incremental signal
for next-game pass-snap participation, beyond the accepted control? Five
prior-only EWMA(half-life 2) features — `pers_3wr`, `pers_2te`, `pers_2rb`,
`form_shotgun`, `form_empty` — built by replicating P1's exact pass-snap join
(`nfl/research/p1/build_panel.py:118–150`), 57,179 player-games profiled.
Materiality fixed in advance at **≥ 1% relative pooled MAE**.

### 8.2 What it returned, and why it is void

| pooled 2022–2025 | n | MAE control | MAE treatment | relative |
|---|---|---|---|---|
| as pre-declared | 22,483 | 0.149545 | 0.136371 | **+8.8095%** |

Nominally 8.8× over the bar. **It is void.** Substituting the five probe columns
while changing nothing else:

| five columns replaced by | correlation with the real features | relative gain |
|---|---|---|
| the real features | 1.000 | +8.8095% |
| permuted within the same team-game | +0.36 to +0.70 | +8.9788% |
| permuted across the whole league | +0.006 to +0.013 | +9.0253% |
| **pure Gaussian noise** | 0 by construction | **+9.0114%** |

Pure noise reproduces the whole effect and slightly exceeds it.

**Mechanism, identified and confirmed.** `p_fit._fit` forms the ridge as
`A = Z.T @ Z + lam * n / max(p, 1) * eye(p)`, so the penalty is divided by the
column count: the control at p=2 is penalised at `1.0*n/2`, the treatment at p=7
at `1.0*n/7`. Adding *any* five columns relaxes the penalty on `p_ewma1` and
`p_ewma2` by 3.5×. Padding the control with five noise columns and changing
nothing else moves MAE from 0.149587 to 0.136107 — **+9.0114%**.

The defect is in my pre-declaration, not in `p_fit`; the P ladder selects `lam`
per rung in an inner loop, which absorbs the scaling. Fixing `lam = 1.0` across
two widths exposed it. The void result is recorded, not deleted, in
`addendum_probe_void.md` and `probe_result.json`.

Chronology was separately clean: masking the panel at four ordinals
(`202110`, `202301`, `202410`, `202516`) changed **0** feature values on every
surviving row. The failure was estimator design, not leakage.

### 8.3 The repair, and the answer

Specified in `addendum_probe_void.md` and committed at `90585aa` **before it was
run**. Primary comparison holds the column count fixed at p=7 on both sides —
five real probe features versus five pure-noise columns, identical penalty — so
the confound cannot recur. Bar unchanged at 1%. Labelled `POST_HOC_REPAIR`: it
was specified after the void result was seen and does not carry the standing of
a genuine pre-registration.

| PRIMARY, column-count matched | n | MAE noise reference | MAE probe features | relative |
|---|---|---|---|---|
| 2022 | 5,640 | 0.142800 | 0.142847 | −0.0325% |
| 2023 | 5,701 | 0.132682 | 0.133213 | −0.3998% |
| 2024 | 5,570 | 0.135408 | 0.135831 | −0.3127% |
| 2025 | 5,572 | 0.133366 | 0.133585 | −0.1642% |
| **pooled** | **22,483** | **0.136065** | **0.136371** | **−0.2244%** |

| SECONDARY, penalty `lam*n`, width-invariant | pooled relative |
|---|---|
| control p=2 vs treatment p=7 | **+0.4626%** (per season: +1.01%, +0.19%, +0.17%, +0.47%) |

**Verdict: `NO_DETECTABLE_INCREMENTAL_SIGNAL`.** The primary governs at
−0.22% — the five real features perform marginally *worse* than five columns of
noise. The secondary agrees at +0.46%, below the 1% bar, in all four seasons
individually and pooled.

**What this does and does not license.** It says the personnel/formation proxy
this project already holds carries no measurable incremental signal for
participation. It says **nothing** about true routes. Personnel is not routes;
that was written down before the result existed and it is not being revised now
that the result is weak.

### 8.4 One adequacy question checked and cleared

Raw `pbp_participation` coverage looked alarming across the panel's own seasons:
`offense_personnel` is populated on 75.3%–76.2% of rows in 2016–2022 and 100% in
2023–2025, and `offense_players` on ~91.4% versus 100%. That would have meant P
was measured on different footing across the walk-forward.

**It does not.** The shortfall is entirely non-plays. Of 4,292 rows with empty
`offense_players` in 2022, 4,290 also have no `possession_team`; 2023 has zero
such rows because nflverse stopped emitting them. On the **joined dropbacks that
actually build P**, personnel is complete:

| season | dropbacks in join | missing personnel | missing formation |
|---|---|---|---|
| 2022 | 20,210 | **0 (0.00%)** | 11 (0.05%) |
| 2023 | 20,693 | **0 (0.00%)** | 39 (0.19%) |

Confirmed independently inside the panel: QB pass-snaps ÷ `team_dropbacks_part`
is 1.0036 / 1.0023 / 1.0004 / 1.0110 / 0.9996 / 1.0020 for 2020–2025 — the
denominator already counts only plays with populated participation. **No defect.
No change made.**

### 8.5 An unexploited extension, stated without a recommendation

`pbp_participation` returns 200 for **2016–2019**, populated at the same
~91.5% / ~75.4% raw rates that 2020–2022 shows, i.e. the same non-play artefact.
The project's panel begins 2020. Four additional seasons of participation
history are therefore reachable and lawful. Whether that is worth building is
not this study's call and no work was done on it.

---

## 9. Legal / rights blockers

| Source | Licence | Status |
|---|---|---|
| `nflverse-data` | **CC BY 4.0** — verified by fetching `LICENSE.md` and reading `Attribution 4.0 International` | **CLEAR for model use with attribution.** Everything this project currently consumes falls here. |
| PFF, SIS, SportsDataIO, Stathead, NGS site | **UNKNOWN** | Domains unreachable (`000`). Terms not read. **Rights are not inferred from silence** — this is "not qualified", not "not permitted". |

No rights blocker is asserted against any vendor, because no vendor's terms were
read. The blocker is that they **cannot be read from this executor**.

---

## 10. Chronology blockers

1. **No as-of pregame role record exists for 2022–2025.** The vintage manifest
   is 663 rows, all `season: 2026`, captures from `2026-09-06` onward. Any
   pregame-role hypothesis is untestable on development data — not falsified,
   untestable.
2. **Final-file modified times prove nothing.** `injuries_2025.csv`
   (`07 Sep 2026`), `pbp_participation_2025.csv` (`10 Feb 2026`),
   `players.csv` (`08 Sep 2026`) are all overwritten finals. No historical
   retrievability is claimed from any of them.
3. **`pbp_participation` and `snap_counts` are not in the vintage capture set,**
   so the project is not currently accumulating a point-in-time record for the
   one input family P depends on.
4. **2026 participation does not exist yet** (404 for both files on
   2026-09-08), so nothing participation-derived is available prospectively
   today.
5. Same-week ordinal collisions remain live in this frame — 1,318 player-ordinal
   pairs carry two rows from mid-week team changes. Every feature built in this
   study used the strictly-earlier-ordinal `bisect` prefix cut, and the masking
   audit in §8.2 confirms it held.

---

## 11. Scientific negatives

Stated plainly, including the one that is mine.

1. **The pre-declared probe was invalid and I designed it that way.** It
   compared two ridge fits of different widths under a penalty that scales with
   width. It measured its own estimator. Pure noise reproduced its entire
   headline. It is recorded, not deleted.
2. **The repaired probe returns no signal**: −0.22% primary, +0.46% secondary,
   against a 1% bar, in every season and pooled. The personnel proxy this
   project already holds does not help participation.
3. **The repair is post-hoc.** It was written down before it was run and its bar
   was not moved, but it was specified after the void result was seen and it
   does not carry pre-registration standing. It is labelled `POST_HOC_REPAIR`
   everywhere it appears.
4. **No source reachable from this executor carries true routes run.** Six open
   schemas were read live and enumerated in §3.
5. **The vendor branch is entirely unqualified.** Seven fields × four vendors,
   all UNKNOWN. This is a limit of the executor, not a finding about the
   vendors, and it must not be reported as one.
6. **The nflverse release index could not be enumerated** — `api.github.com`
   scope refusal for `nflverse/nflverse-data`. Assets were probed by name, so
   §3 is a statement about the assets I could name, not a proof that no other
   asset exists. The NGS receiving row in §3 is `NOT ESTABLISHED` for exactly
   this reason.
7. **Both largest components are stuck against their own controls** — P at 0 of
   4 seasons over a 5% bar, R at 0 of 4 over a 10% bar. That is the state of the
   evidence. **This is not an information ceiling** and is not offered as one;
   the vendor branch is unqualified and the pregame-role branch is untested for
   want of a record, so the question of what better information would do
   remains open.
8. **The sample is previously-exposed development data.** 2022–2025 has selected
   design decisions in this project repeatedly. Nothing in §8 is confirmatory.

---

## 12. FINAL STATE

### `PROSPECTIVE_DATA_PATH_ONLY`

Scoped, because one state has to cover two questions that resolved differently:

- **(B) pregame role** — a data path **exists and is already running**: the
  vintage capture, 8 sources, 533 PASS rows, live since 2026-09-06. It has
  **zero historical depth**, so it can support a prospective study and cannot
  support a development-data study.
- **(A) true routes** — **no qualified path**, historical or prospective, from
  any source this executor can reach. The vendor branch is **UNKNOWN, not
  negative**, and only §13 can move it.

The state is not `DATA_RIGHTS_BLOCKED` (no vendor terms were read, so no rights
blocker is established), not `DATA_SEMANTICS_BLOCKED` (the open schemas are
unambiguous — the quantity is absent, not ambiguous), and not `UNRESOLVED` (every
reachable source resolved cleanly; only the unreachable ones did not).

**Two gating facts belong with this state.** The vintage capture does not include
`pbp_participation` or `snap_counts`, and 2026 files for both return 404 — so
today the prospective path covers pregame role but **not** participation itself.

---

## 13. OWNER DECISION NEEDED

**One decision.**

> **Authorise the networked agent to perform a read-only vendor qualification
> pass on true routes run — or decline it.**

Scope if authorised, and nothing beyond it: read published documentation,
published licence and redistribution terms, published historical coverage, and
published delivery cadence, for PFF, Sports Info Solutions, SportsDataIO and
Stathead. **No contact. No account creation. No purchase. No money.** The
deliverable is §5's table filled with sourced values or an explicit
`NOT PUBLISHED`.

- **If authorised**, the vendor branch becomes qualifiable and a routes
  acquisition decision becomes possible on evidence. Identity is already cleared
  — `pff_id` covers 100% of the frame's 1,126 players and 47,215 player-games,
  deterministically.
- **If declined**, (A) stays permanently unqualified and the receiving track has
  one path only: the prospective pregame-role capture, which as of today holds
  two days of data and does not yet capture participation at all.

I am not recommending which. The choice turns on how much a routes acquisition
is worth to the owner, which is a value judgement with no measurable answer, and
that is his to make.

---

## Artifacts

| File | What it holds |
|---|---|
| `predeclaration_proxy_probe.md` | the probe as fixed before it ran (`f2a73a3`) |
| `addendum_probe_void.md` | the void finding and the repair, fixed before the repair ran (`90585aa`) |
| `build_personnel.py` | the P1-replicating personnel/formation builder, 57,179 player-games |
| `run_probe.py` / `probe_result.json` | the pre-declared probe — **VOID** |
| `check_leak.py`, `check_leak2.py` / `probe_leakcheck*.json` | masking and the three placebos |
| `check_mech.py` / `probe_mechanism.json` | the noise-column mechanism proof |
| `run_probe_repaired.py` / `probe_repaired.json` | the `POST_HOC_REPAIR` and its answer |
| `AGENT_OUTBOX.md` | the exact asks for the networked agent, if §13 is authorised |
