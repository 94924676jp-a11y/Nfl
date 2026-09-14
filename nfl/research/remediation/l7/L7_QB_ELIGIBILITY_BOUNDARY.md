# L7 — the quarterback pool obeys eligibility; the season boundary is untouched

**CODE CHANGED: YES, in two files only.** `nfl/production/run_forecast.py`
(+119 lines, one block inside `_candidate_qb_compute` plus one module constant
and two lines in the run summary) and a new `nfl/tests/test_qb_eligibility_den_kc.py`.
`nfl/production/nonqb/qb_allocation.py` was read and **not modified**. Frozen
QB3 §4 was not touched. No commit, add, stash or push was made.

Written 2026-09-14 by L7. Repo `/home/user/nfl`, branch
`claude/nfl-greenfield-architecture-stsxmk`, HEAD `9c3c29a`, interpreter
`python3.12`. Game `2026_01_DEN_KC`, kickoff `2026-09-15T00:15:00Z`.
Every measurement below used `--written-at 2026-09-14T16:30:00Z`, which is
strictly before both the kickoff and the wall clock at the time it was run.

---

## 1. The answer in one page

**Repair (A), QB eligibility, is implemented and it removes exactly one player
from tonight's two rooms: Kansas City's Chris Oladokun, `00-0037324`, roster
status `RES`. Denver loses nobody and Denver's numbers are bit-identical
before and after.**

**Repair (B), the season-boundary incumbent, must NOT be integrated tonight.**
The minimal repair is pre-registered — QB3-SB,
`nfl/research/qb3/predeclaration_qb3_seasonboundary.md`, sha256
`6cb5c522e3fbd63bb56c948e0ec7b070bcec2d96e6fde2a345ad1935b8763c08` — but it has
never been built, never been fitted and never been scored, and its own §10
forbids the integration anyway. Evidence in §5.

**Oladokun is still Kansas City's incumbent after repair (A).**
`previous_primary_detail(2026, 1)['KC']` returns him regardless of who is in the
pool, because the resolver reads the panel, not the room. Eligibility removes
him from the room, so the incumbent bit lands on **nobody** and KC moves from
`DISAGREE` to `NO_PREV_PRIMARY_IN_ROOM`. **The season boundary is the binding
mechanism. Eligibility is not.** This reproduces `d652afb` on a second game.

**Recommended configuration for tonight: `V1_CANDIDATE_R8` with repair (A)
applied**, carrying the limitation string in §7 verbatim in the seal. It is the
most defensible currently implemented configuration, and it is still not a
trustworthy quarterback room. Quarterback markets on this board stay
contaminated and inadmissible.

---

## 2. What was in the pool, measured

Roster vintage `nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz`,
observed `2026-09-14T16:16:25Z`. Depth chart
`depth_charts.f66f0c2583dba463`, inner `dt = 2026-09-14T13:53:31Z`.

| team | gsis_id | status | player | in pool before | after (A) |
|---|---|---|---|---|---|
| DEN | 00-0039732 | ACT | Bo Nix | yes | yes |
| DEN | 00-0035264 | ACT | Jarrett Stidham | yes | yes |
| DEN | 00-0036879 | ACT | Sam Ehlinger | yes | yes |
| KC | 00-0033873 | ACT | Patrick Mahomes | yes | yes |
| KC | 00-0036945 | ACT | Justin Fields | yes | yes |
| KC | 00-0040906 | ACT | Garrett Nussmeier | yes | yes |
| **KC** | **00-0037324** | **RES** | **Chris Oladokun** | **yes** | **NO** |

`roster_status.active_pool` evidence on this list: `n_in 7, n_kept 6,
dropped_by_status {"RES": 1}, n_unknown_status_kept 0,
kept_unrecognised_status {}`. One player, one declared code, nobody removed on
a code the module does not recognise, and nobody removed for being unknown to
the roster — an unknown status is still kept, exactly as the non-QB half keeps
him.

**DEN removes nobody.** All three Denver quarterbacks are `ACT`.

---

## 3. What repair (A) does to the rooms

Two sealed boards, `V1_CANDIDATE_R8`, 1,000 draws, seed 20260908, same
`--written-at`, same captures. The control is the **same code** with
`roster_status.active_pool` neutralised **for the all-quarterback call only**,
so the single difference between the two boards is the QB pool. Player counts
19 against 20 confirm the isolation: one row, and it is Oladokun.

Repaired run `f91800aba5022c2f`; control run `b79e09719c7f0682`.

### Denver — unchanged, every figure, to the last decimal

| player | qb/db mean | qb/att mean | qb/pyds mean | share of game dropbacks |
|---|--:|--:|--:|--:|
| Bo Nix | 34.06 | 30.54 | 202.35 | 0.4327 |
| Jarrett Stidham | 2.26 | 1.92 | 14.06 | 0.0287 |
| Sam Ehlinger | 0.90 | 0.77 | 4.54 | 0.0114 |

Control and repaired are identical in all of them. `qb3_configuration` for DEN
is `AGREE` on both boards, and Denver's week-1 incumbent **is** Bo Nix
(ordinal 202518), so Denver is the one room on this card where the boundary
happens not to bite.

### Kansas City — the defect moves

| player | qb/db mean | qb/att mean | qb/pyds mean | qb/pyds p50 | share |
|---|--:|--:|--:|--:|--:|
| Mahomes, control | 15.59 | 13.80 | 98.95 | 11.03 | 0.1981 |
| **Mahomes, repaired** | **22.82** | **20.20** | **144.02** | **160.00** | **0.2900** |
| Fields, control | 2.17 | 1.71 | 12.10 | 0.00 | 0.0276 |
| **Fields, repaired** | **13.20** | **10.34** | **72.59** | **12.29** | **0.1677** |
| Nussmeier, control | 0.82 | 0.72 | 4.82 | 0.00 | 0.0105 |
| **Nussmeier, repaired** | **5.47** | **4.87** | **34.57** | **12.64** | **0.0695** |
| **Oladokun, control** | **22.90** | **19.32** | **136.51** | **147.12** | **0.2909** |
| Oladokun, repaired | — removed — | | | | |

At the allocation layer, same seed and draws:

| room | Mahomes share | P(Mahomes 0 dropbacks) | next man | corr |
|---|--:|--:|---|--:|
| before (A) | 0.3776 | 0.4950 | Oladokun 0.5500 | −0.9686 |
| **after (A)** | **0.5474** | **0.4120** | **Fields 0.3201** | **−0.9936** |

**Read this the way `d652afb` read Dallas.** Removing a reserve-list
quarterback moved 55.00% of Kansas City's modelled dropbacks off a man who
cannot play. It did **not** produce a defensible room. Patrick Mahomes is still
modelled at 0.5474 of his club's dropbacks with a **41.20% chance of taking
zero**, his backup at 0.3201, and the two are correlated −0.9936 — the
one-hot primary draw shared between two men, which is the DAL/NYG shape
(Prescott 0.5416 / Howell 0.4584, P(0) 0.4273, corr −0.9240) reproduced on a
second game. A backup quarterback carrying 72.59 mean passing yards is not a
forecast anyone should price.

Repair (A) is applied because a `RES` quarterback inside a board that claims to
filter on eligibility is indefensible on its own terms, **not** because it fixes
the ordering. It does not.

---

## 4. Is Oladokun still KC's incumbent after (A)? Yes.

`previous_primary_detail(2026, 1)['KC']` returns, unchanged by the filter:

    {'pid': '00-0037324', 'ordinal': 202518, 'is_season_opener': True}

Ordinal `202518` is **2025 week 18**. The resolver reads `qb3_lib`'s panel by
`bisect` over `season*100 + week`; it has no idea which players are in the
room, so removing a man from the pool cannot change who it names. What changes
is only whether the named man is *present*: he is not, so
`qb3_configuration(trip, ...)` finds no `was_prev_primary` bit anywhere in the
room and returns `NO_PREV_PRIMARY_IN_ROOM`.

That is a **different** room, not a repaired one. Mahomes sits in cell `(1,0)`
either way — `p_primary` 0.4922, `P(share = 0)` 0.4735 — against cell `(1,1)`'s
0.9046 and 0.0736, a factor of 6.4 on the zero-share mass. The cell that would
put him where the depth chart says he belongs is reachable only by fixing the
incumbent, and that is repair (B).

**Verdict: the week-1 season-boundary incumbent is the binding mechanism on
this card. Eligibility is a separate, real, smaller defect.**

---

## 5. Repair (B): pre-registered, unbuilt, unscored — do not integrate

### 5.1 It is pre-registered

`nfl/research/qb3/predeclaration_qb3_seasonboundary.md` (QB3-SB), sha256
`6cb5c522e3fbd63bb56c948e0ec7b070bcec2d96e6fde2a345ad1935b8763c08`, written
2026-09-13. §2 defines the minimal change: `cell = (rank, was_prev_primary,
is_season_opener)` with everything else in QB3 unchanged. §3 gives the
predicate on the ordinal gap, not on `week == 1`.

### 5.2 It has never been built, fitted or run

* `nfl/research/qb3/qb3_lib.py:130` is `def cell_of(rank, was_prev)`. **Two
  arguments. No opener term.** `fit` at `:138` and `allocate` at `:157` key off
  that function and nothing else.
* `nfl/research/qb3/qb3_results.json` carries four arms — `QB3`,
  `B0_incumbent`, `B1_depth_chart`, `B2_current_production` — for 2022–2025.
  **There is no QB3-SB arm.** No CRPS, no clustered interval, no closure check.
* `is_season_opener` exists in production **only as diagnosis**:
  `qb_allocation.previous_primary_detail` computes it and
  `qb3_configuration` records it on the artifact. The function's own docstring
  says so: *"This is DIAGNOSIS CARRIED ONTO THE ARTIFACT. It changes no
  probability and no draw."* The production room `trip` is
  `(pid, min(rank,3), int(prev == pid))` — the opener bit never reaches it.

So there is nothing to validate. Building the estimator, fitting it
walk-forward on 2022–2024 and bootstrapping a team-clustered CRPS difference is
a piece of research work, not an integration, and it cannot be done and checked
before kickoff.

### 5.3 Even if it had been built and had passed, §10 forbids tonight

Quoted from the pre-registration, verbatim:

> If QB3-SB meets §8 on the exploratory folds, the proposed role is
> **prospective shadow only**: both arms are computed and recorded per week-1
> team-game, neither is published, and the comparison accumulates toward a
> genuinely out-of-sample record. Promotion into R8 requires a separate owner
> decision on evidence that does not exist yet and will not exist this season —
> week 1 happens once.

and

> Until then the baseline QB3 remains the production layer, and every QB market
> on a week-1 board stays contaminated and inadmissible.

Integrating QB3-SB into tonight's engine would break the document that is the
only thing authorising it. That is not a close call.

### 5.4 Three further reasons, each sufficient on its own

1. **It cannot be validated on anything near this season.** §4 fixes the
   evaluation seasons at 2022, 2023, 2024 because the committed depth-chart
   leaves stop at 2024. There is no 2025 fold and no 2026 fold, and §9 states
   the result would be **EXPLORATORY** in any case, since the 2020–2024 data
   selected the finding.
2. **Which candidate should carry this is an open owner decision.**
   `predeclaration_qb3_ab.md` §0 says QB3-AB *"subsumes"* QB3-SB and that *"If
   QB3-AB proceeds, QB3-SB should be withdrawn rather than run in parallel, and
   that is a decision for the owner, not for this document."* Choosing between
   them tonight would be making that decision by default.
3. **It cannot be implemented inside my authority.** QB3-SB changes
   `cell_of`, which is frozen QB3 §4 — the thing I was told not to mutate — and
   `qb3_lib.py` is not a file I own.

### 5.5 What I did not do

I did not implement QB-P1. I did not implement QB3-SB. I did not evaluate any
candidate on tonight's game, and no number on tonight's card was used to choose
anything. The two boards in §3 exist to **measure the eligibility repair the
ruling requires**, not to select between configurations.

---

## 6. The change, exactly

**`nfl/production/run_forecast.py`, inside `_candidate_qb_compute`,
immediately after `teams`/`m` are resolved and before `FE.qb_slate`:**

* under the same `active_roster_only` flag the non-QB half uses, call
  `roster_status.status_map(season, week, teams, observed_before=written_at,
  kickoff_utc=...)` and `roster_status.active_pool(qbp, statuses)`;
* return the refusal Outcome unchanged if either does not PASS — **there is no
  fallback to the unfiltered list**, for the reason R5 already states: running
  unfiltered under a filtered label reports a repair that did not happen;
* refuse by name, `QB_POOL_EMPTIED_BY_ELIGIBILITY`, if a club's entire room is
  ineligible. `qb_allocation` silently `continue`s past a team with no
  quarterback, so without this a board could carry a game one of whose clubs
  has no passer at all;
* record `fx['_r5_qb']` (the pool evidence, the capture name, the observation
  time, `n_qb_in`, `n_qb_kept`, the limitation string) and `fx['_r5_qb_applied']`;
* surface both in the sealed `run_status.json` as `qb_pool_eligibility` and
  `qb_participation_limitation`. Absent on a run that did not filter — absence
  stays absence and nothing is backfilled.

**One naming note that is load-bearing.** The flag read is spelled
`eligibility_on = bool(fl.get('active_roster_only'))` rather than inlined,
because `nfl/tests/test_r5_active_pool.py:127` locates the **non-QB** branch by
searching the source for the first inline spelling of that flag read. My block
is earlier in the file; an identical spelling silently redirected that guard
onto my window and the non-QB branch went unchecked while the suite stayed
green. I hit exactly that and it is why the module briefly failed. **The
locator is still fragile** — the next block added above line 727 will do the
same thing — and whoever owns `test_r5_active_pool.py` should make it locate by
function rather than by first substring. I did not edit that test, since it is
not mine.

**One governance item for you, not for me.** `candidate_mode.R5_REPAIR['what']`
reads *"restrict the **non-QB** allocation pool to players whose roster status
is ACT"*. Behaviour under that flag is now wider than that sentence. I did not
edit `candidate_mode.py`. Either the sentence should be widened or the QB
filter should get its own flag; the artifact says which happened regardless,
because `qb_pool_eligibility` is written separately from `_r5`.

**The controls are untouched.** The filter is gated on `active_roster_only`,
which `PRODUCTION_BASELINE` and `V1_CANDIDATE` do not carry (verified by
resolving all six modes: `None, None, True, True, True, True` for
`PRODUCTION_BASELINE, V1_CANDIDATE, R5, R6, R7, R8`). So the immutable control
arm is bit-identical to before this change, and only the R5-and-later
configurations filter the QB pool. The separate baseline QB path at
`run_forecast.py:~1076` is not touched at all.

**Nothing else changed.** `qb_allocation.py` was read and not edited. No
constant was introduced. No share was clipped, floored or rebalanced. The
filter consumes `DEV/RES/CUT/EXE` only; `INA` is refused upstream by
`roster_status` as post-hoc, so no gameday outcome enters a pregame pool.
No sportsbook data was opened.

---

## 7. The limitation string the run must record

Recorded automatically as `run_status.qb_participation_limitation` on any run
that filters the QB pool, and carried inside `qb_pool_eligibility` as
`qb_participation_limitation`. It is the module constant
`run_forecast.QB_PARTICIPATION_LIMITATION`, verbatim:

> QB participation is QB3 (contract nfl/research/qb3/predeclaration_qb3.md,
> sha256 be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e).
> Filtering the QB pool on roster status removes ineligible quarterbacks and
> does NOT repair either known participation defect. (1)
> QB3_WEEK1_SEASON_BOUNDARY: in a season opener the incumbent signal is the
> PRIOR SEASON FINAL-GAME primary passer, the game a club is most likely to
> rest a starter in. Measured league-wide, the depth-chart QB1 equals that
> passer in only 59 of 160 week-1 rooms (0.3688), and 77 of 192 team-seasons
> (0.4010) end with a primary who is not that season modal starter
> (nfl/research/qb3/QB3_WEEK1_INCUMBENT_AUDIT.json). Removing an ineligible
> incumbent does not restore the bit; it moves the room from DISAGREE to
> NO_PREV_PRIMARY_IN_ROOM, whose cell (1,0) carries p_primary 0.4922 and
> P(share=0) 0.4735 against cell (1,1) 0.9046 and 0.0736. (2) An unranked
> rostered quarterback is modelled at depth rank 3
> (nfl/production/nonqb/qb_allocation.py, "r = 3"), which is a populated cell
> and not a null: 27 of 119 rostered quarterbacks league-wide carry no
> depth-chart row. CONSEQUENCE: on a season-opening board the modelled split
> between a club starting quarterback and his backups is not trustworthy,
> quarterback-derived markets are CONTAMINATED and inadmissible, and no QB
> number here may be compared with a price.

The per-run evidence that instantiates it travels beside it — `qb3_configuration`
carries `is_season_opener: true`, `defect_id: QB3_WEEK1_SEASON_BOUNDARY` and the
declared incumbent for both clubs — so nothing in the string is asserted that
the artifact does not also show.

**Tonight the second clause bites on nobody:** all seven quarterbacks in these
two rooms carry a depth-chart rank, `unranked_players` is zero. It is in the
string because the string is general and because 27 league-wide roster QBs do
not carry one.

---

## 8. Guards and suites

`nfl/tests/test_qb_eligibility_den_kc.py` — new, 7 test functions, 28 checks,
all passing. It asserts that the QB stage filters under the same flag and the
same status map, that it never falls back to the unfiltered list, that
`QB_POOL_EMPTIED_BY_ELIGIBILITY` exists, that `RES`/`DEV` are dropped and an
unknown status is kept and counted, that tonight's drops are all on declared
codes and neither club is emptied, that **KC's incumbent is still resolved
across the season boundary and eligibility removes rather than corrects him**,
that the limitation string names both defects and reaches the seal, and that
Q9's `layers.py` is unmoved. Nothing in it conditions on any outcome.

Suites run (`python3.12 nfl/tests/run_suite.py --only <module>` only):

| module | result |
|---|---|
| `test_qb_eligibility_den_kc` | **PASS** — 7 functions, 28 checks, 0 failing, 0 blocked |
| `test_r5_active_pool` | **PASS** — 8 functions, 21 checks (failed first, see §6; the locator, not the repair) |
| `test_draw_coherence` | **PASS** — 11 functions, 135 checks |
| `test_production_pipeline` | **PASS** — 9 functions, 69 checks |
| `test_forecast_completeness` | **PASS** — 7 functions, 30 checks |
| `test_r8_synthesis` | **PASS** — 20 functions, 69 checks |
| `test_full_slate_rehearsal` | **PASS** — 7 functions, 30 checks |
| `test_prospective_contract` | **PASS** — 8 functions, 63 checks |
| `test_harness_audit` | **PASS** — 5 functions, 20 checks |

Nine modules, 0 failing checks, 0 raised, 0 zero-check functions, 0 blocked
functions. These are the modules that touch the path I changed; this is not a
full-suite run and is not offered as one.

**The repaired impossible-state guards hold on the sealed run.**
`draw_coherence` = `PASS / DRAW_COHERENCE_HOLDS`, spec `nfl-draw-coherence-1`.
The QB component reports **0 violations in 6,000 cells** on each of nine
checks, `qb_completions_and_interceptions_within_attempts` — the `cmp + int <=
att` case — among them. `counts_non_negative` 0 of 54,000.

One thing is **not** clean and is reported rather than buried: the `carries`
component records `team_qb_rush_opportunity_within_team_carries` with **6
violations in 2,000 cells**, listed under `diagnostics_not_clean`. The
component still returns PASS because that check is a diagnostic rather than a
hard invariant. It is present on the control board too, so it is **not** caused
by this repair, but it is a real non-clean diagnostic on tonight's board and
somebody should own it.

---

## 9. Q9 hash check

    sha256  nfl/production/nonqb/layers.py
            481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108
    sha16   481f005f682cd721
    bytes   33098
    declared in nfl/research/q9b/Q9_PROSPECTIVE_FREEZE.json -> 481f005f682cd721
    git status: clean, not modified

**MATCH. The Q9-frozen artifact is unchanged.** The check is also a standing
assertion in the new test module, so it fires on every suite run rather than
once in this document.

---

## 10. Recommendation

**Run `2026_01_DEN_KC` as `V1_CANDIDATE_R8` with repair (A) applied.** It obeys
current player eligibility, it passes the repaired impossible-state guards
including `cmp + int <= att`, it is chronology-clean (roster status selected
strictly before kickoff by `vintage_selector`, `INA` refused as post-hoc), and
it records the QB participation limitation explicitly in the seal.

**Do not integrate repair (B).** It is pre-registered but unbuilt and unscored,
and its own §10 confines it to prospective shadow pending a separate owner
decision. The fallback the ruling permits — run the incumbent as it stands and
record the limitation — is what I have implemented.

**What this board is not.** Kansas City's quarterback room is still resolved
through an incumbent signal that names a reserve-list quarterback from last
January, Patrick Mahomes still carries a 41.20% chance of zero dropbacks, and
Justin Fields still carries 72.59 mean passing yards. Those numbers are
outputs of a known defect. **No quarterback market on this card may be priced,
compared with a book, or published as a play.**

## 11. Reproduction

    python3.12 nfl/tests/run_suite.py --only test_qb_eligibility_den_kc

    python3.12 nfl/tools/make_board.py --game-id 2026_01_DEN_KC \
        --written-at 2026-09-14T16:30:00Z --out-dir <dir> \
        --model-configuration V1_CANDIDATE_R8 --draws 1000

The control board in §3 is the same invocation with
`nfl.production.nonqb.roster_status.active_pool` monkeypatched to a passthrough
**for all-quarterback calls only**, run from a scratchpad and never written
back. The allocation-layer figures come from
`football_engine.QA.allocate(2026, 1, ['DEN','KC'], qbp, m=1000,
seed=20260908)` with `qbp` taken from the roster vintage that
`information_set.build('2026-09-15T00:15:00Z',
observed_before='2026-09-14T16:30:00Z')` selects.
