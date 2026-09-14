# PREREG — QB-P1: a candidate architecture for QB participation

**Status: PRE-REGISTRATION. NOT AUTHORISED. NOT BUILT. NOT FITTED. NOT APPLIED.**
**CODE CHANGED: NO.** Nothing outside `nfl/research/remediation/ws_i/` was
written. No production module, no frozen artifact, no test, no governance file
was touched. No suite was run. No sportsbook data was opened. No 2026 game was
scored.

Written 2026-09-14 by WS-I. Repo `/home/user/nfl`, branch
`claude/nfl-greenfield-architecture-stsxmk`, HEAD `837d52f`, interpreter
`python3.12`.

This document is written **before any candidate code exists**, which is the
whole point of it. Every number quoted below as *design input* was measured
before this document was written, and §1.3 lists exactly which measurements were
made and on which sample, so that nobody can later claim an independence this
work does not have.

---

## 0. What is being pre-registered, in one paragraph

The incumbent QB allocation (`nfl/research/qb3/qb3_lib.py`, sha16
`771724a3ffb20f5e`; production entry `nfl/production/nonqb/qb_allocation.py`,
sha16 `a4530000488223ff`) estimates **one** unconditional quantity, the share of
team dropbacks `s_dropbacks`, inside **five** pooled cells keyed on clipped
depth rank and one incumbent bit. QB-P1 proposes replacing that with **three
stages carrying two estimated objects**: a deterministic eligibility gate, a
**room-conditional** distribution over *who takes the first snap*, and a
**conditional joint share vector** resampled whole from matched historical
rooms. No stage introduces a fitted constant. No stage clips, floors, caps or
rebalances a share by rule.

---

## 1. Provenance of the inputs, and of the hypothesis

### 1.1 Artifacts read in full before writing

| artifact | sha16 |
|---|---|
| `nfl/research/remediation/WAVE0_BASELINE.json` | (baseline of record, head `837d52f`) |
| `nfl/research/parallel_pass/ws03/WS03_QB_PARTICIPATION_ARCHITECTURE.md` | read in full |
| `nfl/research/parallel_pass/ws24/WS24_EXTERNAL_ADJUDICATION.md` items R7, R13 | read |
| `nfl/research/parallel_pass/ws20/WS20_SEASON_BOUNDARY.md` findings 1, 2 | read |
| `nfl/research/qb3/predeclaration_qb3.md` | `be61392619d45f3a` |
| `nfl/research/qb3/predeclaration_qb3_ab.md` | `07b36d0e1e608cef` |
| `nfl/research/qb3/predeclaration_qb3_seasonboundary.md` | `6cb5c522e3fbd63b` |
| `nfl/research/qb3/QB_PARTICIPATION_CAUSAL_AUDIT.json` | `5da31885a93cc63f` |
| `nfl/research/qb3/QB3_WEEK1_INCUMBENT_AUDIT.json` | `c5c0ef97cff22719` |

### 1.2 Data available to this design

| input | sha16 | coverage | what it can define |
|---|---|---|---|
| `nfl/research/inputs/panel_p3.csv.gz` | `6cb51092175c7a06` | seasons **2020–2025** (9,231 / 9,754 / 9,675 / 9,744 / 9,628 / 9,638 rows) | team-week dropback counts per player; **arg-max primary only** |
| `nfl/research/inputs/dc_2020..2024.csv.gz` | — | 2020–2024, `game_type == REG` | depth rank, the QB room |
| `nfl/research/inputs/dc25_daily.csv.gz` | `5e0eba5bac474334` | 146,246 rows, **221 distinct `dt`**, 2025-08-03T10:09:07Z → 2026-03-14T07:32:09Z, 21,342 QB rows; schema `dt, team, gsis_id, pos_abb, pos_rank` — **no `season`, no `week`, no `game_type`** | 2025 depth rank, **only after** a `dt → (season, week)` join that does not exist here |
| `nfl/research/postgame/pbp_2021..2024.*.csv.gz` | per `QB_PARTICIPATION_CAUSAL_AUDIT.json` | **2021–2024 only** | **first-snap identity**, play order, game state |
| `nfl/research/postgame/pbp_2026.*.csv.gz` | `1415dd98ba7f701a` (10 games), `d9e442ae17ba88e7` (2 games) | 2026 week 1 REG | **PROHIBITED. See §7.2.** |

**There is no `pbp_2025` in this checkout.** This is the binding structural fact
of the whole design and it is stated here before anything is built: the
first-snap definition on which QB-P1 rests is computable for **2021–2024 and for
no other historical season available to this repository**.

### 1.3 Measurements made BEFORE this document, and the independence they cost

Everything in this list was computed by WS-I on 2026-09-14 on seasons
**2020–2024** and is therefore **development data**. Writing a pre-registration
afterwards does not restore independence, and §6 treats every result on this
frame as exploratory for that reason.

Declared inspected quantities:

1. Charted-room structure: 6,446 frame rows over **2,685 charted team-games**
   (2020–2024); room size `{1: 34, 2: 1549, 3: 1094, 4: 8}`; **160** week-1
   charted team-games.
2. Room-configuration key counts (§3.2), both with and without an opener term.
3. First-snap vs arg-max agreement from pbp 2021–2024.
4. Donor counts for the conditional joint (§3.3) by (starter clipped rank,
   number of other QBs in room), and the corresponding realised
   `P(starter share = 1)`.
5. Distinct dropback-taker counts per team-game, and the position of
   dropback-takers outside the charted room.

**No contrast between candidate variants was computed.** In particular, no
alternative incumbent definition (final-game vs modal vs any other) was scored
here; the 59/160 and 77/160 figures quoted in WS20 finding 1 and WS03 are
**pre-existing** and are treated as hypothesis-selecting, not as evidence.

---

## 2. The defects this architecture is answering

Restated from WS03's failure map so the candidate can be checked clause by
clause against them. Each is a **specification** defect: WS03 F15 and
`QB3_WEEK1_INCUMBENT_AUDIT.json.implementation_conformance` both record that
`qb3_lib` implements its contract faithfully.

| id | defect | incumbent mechanism |
|---|---|---|
| D-BOUND | week-1 incumbent resolves to the prior season's **week 18** | `qb_allocation.py:117` `previous_primary_detail`, called at `:452`; `bisect` over `season*100+week` |
| D-POOL | no week or opener term exists anywhere in the cell definition | `qb3_lib.py:130 cell_of` reads clipped rank and the incumbent bit, nothing else |
| D-MARG | starter-selection **marginal** rates are renormalised in-room and used as an identity distribution | `qb3_lib.py:169-171`; `sum(p_primary)` over the 32 week-1 2026 rooms runs 0.5608 / 1.0014 / 1.2056 |
| D-RELIEF | those same starter rates are reused as **relief-share weights** | `qb3_lib.py:183-192` |
| D-ANTI | in a 2-QB room the backup's share is a deterministic function of the starter's | `qb3_lib.py:184-192` with `n = 2`; corr = −1.0000 in share space, −0.9240 in count space after `d652afb` |
| D-FANOUT | one `rem` scalar fans out to every non-primary QB at once, so backups enter **together** | `qb3_lib.py:183-192`; WS09 measured backup–backup r = +0.87 … +0.96 |
| D-ZERO | the charted starter carries `P(share = 0)` that reality assigns zero | `qb3_lib.py:84-124 build_frame` conditions on the room, not on having started |
| D-DENOM | shares are closed to 1.0 over the **QB room**, but dropbacks are taken by men outside it | closure at `qb3_lib.py:196-197` |
| D-ELIG | the QB pool is exempt from the only eligibility filter; unranked roster QBs enter at rank 3 | `run_forecast.py:638-644`, comment `:625-628` *"The QB pool is untouched"*; `qb_allocation.py:471-476` |

**D-ELIG is explicitly NOT the binding mechanism and is not re-proposed as one.**
Commit `d652afb` constrained the QB pool to the active 53 and titled the result
honestly — *"Removing the wrong quarterback moved the defect, it did not fix
it"*: Prescott 0.5416, Howell 0.4584, `P(Prescott takes 0 dropbacks) = 0.4273`,
corr(Prescott, Howell) = −0.9240. WS24 R7 records the same verdict. The
governing counter-example stands: Milton is DAL's week-18 2025 primary passer →
`was_prev_primary = 1` → cell `('2+', 1)`, `p_primary` **0.6167**, against
Prescott's `(1, 0)` at **0.4922**.

---

## 3. QB-P1: the candidate, stated exactly

### 3.1 Stage 0 — deterministic eligibility gate. NOT ESTIMATED.

The room is the set of rostered quarterbacks, minus anyone on the **official
inactive list** for that game, which reaches the system roughly 90 minutes
before kickoff.

Stage 0 has **no free parameter and no fitted quantity**. It is declared as a
stage so that its ceiling is visible rather than implicit:

> **Declared Stage 0 ceiling.** No pregame active-53 / practice-squad / reserve
> signal exists in this repository (WS03 F12; `weekly_rosters.status` is
> quarantined POSTHOC and correctly so). Every PRE-stage board is therefore
> structurally unable to know who is dressed. **No estimator repairs this; only
> an ingestion does.** Outbox item §8.3.

Stage 0 does **not** change `run_forecast.py:638`. Whether the R5 exemption
should be lifted is a separate question owned by WS-D and is **out of scope
here**, because `d652afb` already showed it is not the binding mechanism.

### 3.2 Stage 1 — pregame first-snap identity. ESTIMATED OBJECT #1.

**Estimand.** For a room of `k` eligible quarterbacks, the categorical
distribution `P(member j takes the team's first dropback of the game)`,
`j = 1..k`, summing to exactly 1 over the room plus one `NONE` outcome for a
team-game in which no room member takes the first dropback.

**Why first snap and not arg-max dropbacks.** `qb3_lib.primary_of` (`:79-81`)
is arg-max, so *"started and was pulled at half"* and *"came off the bench and
out-threw the starter"* are the same row (WS03 F10). Measured on pbp 2021–2024,
**n = 2,174** team-games with at least one dropback, the first-snap taker
differs from the arg-max taker in **61 team-games (0.0281)**. That 2.8% is
precisely the replaced-starter population the product needs to represent, and
under arg-max it is definitionally invisible.

The first-snap definition is what structurally removes **D-ZERO**: conditional
on taking the first snap, `P(share = 0) = 0` **by construction**, not by a
fitted correction and not by a floor.

**Estimator.** An empirical conditional frequency over a **room-configuration
key**, not a renormalised vector of marginal rates. This is what answers
**D-MARG**: the distribution sums to 1 because it was estimated as a
distribution, so nothing is silently rescaled and nothing needs to be.

Key, declared now:

```
key = ( tuple of clipped depth ranks in the room, sorted ),
      ( tuple of incumbent bits, aligned to that sort ),
      is_season_opener )
```

with `clipped rank = min(rank, 3)`, an unranked rostered QB entering at rank 3
exactly as production does today, and `is_season_opener` read off the ordinal
gap in `previous_primary_detail` (`qb_allocation.py:110`) — a boolean about a
gap, **not a fitted constant**.

**Measured key coverage, 2,685 charted team-games, 2020–2024:**

| key form | distinct keys | team-games in keys with n ≥ 30 | n ≥ 50 | n ≥ 100 |
|---|--:|--:|--:|--:|
| without opener term | 18 | 2,591 (0.965) | 2,556 (0.952) | 2,417 (0.900) |
| with opener term | 27 | 2,547 (0.949) | 2,430 (0.905) | 2,254 (0.839) |

Largest keys, with opener term: `((1,2),(1,0),0)` n=1,347; `((1,2,3),(1,0,0),0)`
n=907; `((1,2,3),(0,1,0),0)` n=99; `((1,2),(0,1),0)` n=77; `((1,2),(0,0),1)`
n=43; `((1,2),(1,0),1)` n=40.

**Week-1 alone: 160 team-games over 10 keys**, of which only two exceed n = 40
(`((1,2),(0,0),1)` n=43 and `((1,2),(1,0),1)` n=40). This is the ceiling WS03 §4
names and it is not repairable by compute.

**Back-off ladder, declared now, before any fit** (a cell with fewer than the
floor backs off one rung; the floor is declared here, not chosen after seeing
which cells are thin):

```
floor n = 30
rung 1: (ranks, incumbent bits, is_season_opener)
rung 2: (ranks, incumbent bits)                       # opener term dropped
rung 3: (ranks collapsed to {1, 2+}, incumbent bits)
rung 4: marginal by the member's own (clipped rank, incumbent bit)
```

**The incumbent bit itself is a declared arm, not a chosen one.** Three
definitions are named here and **none is preferred in advance**:

- **I-LAST** — the prior team-game's arg-max primary. This is the incumbent
  definition, `previous_primary_detail`, and it is the **baseline arm**.
- **I-MODAL** — the modal primary passer of the team's prior *season*, used only
  when `is_season_opener` is true; I-LAST otherwise.
- **I-FIRSTSNAP** — the modal **first-snap** taker of the prior season, opener
  only; I-LAST otherwise. Computable only where pbp exists.

WS20 finding 1 and WS03 report that the chart QB1 equals the prior-season
final-game primary in **59/160** week-1 rooms (0.3688) against **77/160** for
the modal primary, and that **40.1%** of team-seasons end with a non-modal
primary. **Those numbers selected this hypothesis and are therefore not
evidence for it.** I-MODAL and I-FIRSTSNAP may be scored **only** on a fold that
satisfies §6.2.

### 3.3 Stage 2 — conditional joint share vector. ESTIMATED OBJECT #2.

**Estimand.** Conditional on quarterback `j` having taken the first snap, the
**joint** vector of realised shares over the whole room *plus* an explicit
`OTHER` slot:

```
( s_starter, s_2nd_by_rank, s_3rd_by_rank, ..., s_OTHER ),  summing to exactly 1
```

**Estimator.** Resample a complete historical vector — **the whole vector at
once, never a marginal** — from the donor stratum
`(starter's clipped depth rank, number of other QBs in the room)`, aligned by
rank order among the non-starters.

This single object is what collapses conceptual stages 2, 3, 4, 5 and 6, and
the reason is not convenience. A realised share vector **already contains**, in
its realised proportion and with its realised co-occurrence structure, every
planned package, every exit, every blowout substitution and every kneel that
actually happened. Fitting them separately would add five estimated objects
without adding a single identified quantity — and, in three of the five cases,
would fit against a predeclared rule rather than against the world (§5).

**Measured donor counts, pbp 2021–2024, charted first-snapper, n = 2,133:**

| (starter clipped rank, n other QBs) | n | mean starter share | P(starter share = 1) |
|---|--:|--:|--:|
| (1, 1) | **1,145** | 0.9647 | 0.7913 |
| (1, 2) | **706** | 0.9561 | 0.7394 |
| (2, 1) | **113** | 0.9343 | 0.6903 |
| (2, 2) | **96** | 0.9278 | 0.6771 |
| (3, 2) | **39** | 0.9313 | 0.7436 |
| (1, 0) | 14 | 0.9895 | 0.7143 |
| (2, 0) | 11 | 0.9467 | 0.8182 |
| (1, 3) | 4 | 0.8391 | 0.2500 |
| (3, 1) | 4 | 0.9043 | 0.5000 |
| (2, 3) | 1 | 0.1930 | 0.0000 |

Donor back-off, declared now, floor n = 30: `(rank, n_other)` →
`(rank, min(n_other, 2))` → `(min(rank, 2), min(n_other, 2))` → all donors
pooled. A donor vector shorter than the target room is padded with zeros in the
lowest rank slots; a donor longer than the target room has its surplus slots
folded into `OTHER`. Both rules are declared here and neither is a fitted
quantity.

**What this repairs, clause by clause:**

- **D-ZERO.** `P(starter share = 0 | he took the first snap) = 0` by
  construction. Realised `P(share = 1)` of 0.74–0.79 is carried directly rather
  than re-derived. Compare the incumbent's cell `(1,1)` at `P(share = 0) =
  0.0736` against a realised 0/1,700 (`QB_PARTICIPATION_CAUSAL_AUDIT.json`).
- **D-RELIEF.** The remainder is the donor's realised remainder. `p_primary` —
  a starting rate — is never reused as a relief weight.
- **D-ANTI.** Dependence is whatever the donor vector showed. The incumbent's
  corr = −1.0000 in a 2-QB room is an artefact of residual allocation, not an
  estimate, and it disappears when the joint is resampled.
- **D-FANOUT.** Measured on the same 2,133 team-games, the number of
  **QB-position** dropback takers per team-game is `{1: 1786, 2: 342, 3: 5}`:
  `P(≥2 QB takers) = 0.1627`, `P(≥3) = 0.0023`, and
  `P(a third QB throws | a second does) = 0.0144`. Backups enter
  **alternatively, essentially never together.** WS09 measured the incumbent's
  backup–backup correlations at **+0.87 … +0.96**. A donor resample reproduces
  0.0144 because 0.0144 is what the donors contain.
- **D-DENOM.** The `OTHER` slot. Dropback takers outside the charted room over
  the same frame are, by panel position: **WR 110, P 32, QB 32, RB 27, TE 19,
  DB 3, K 1, LB 1, OL 1, not-in-panel 3** — trick plays, fakes and Wildcat, not
  quarterbacks. Their mass is small but systematic: non-room dropback share has
  mean **0.0069**, is strictly positive in **221 of 2,133 team-games (0.1036)**
  and reaches ≥ 0.05 in **32**. Closing the room's shares to 1.0 hands that mass
  to quarterbacks who did not take it. On the wider frame of all 2,685 charted
  team-games measured against the panel denominator the uncharted share averages
  **0.0218** and exceeds 0.01 in **85** team-games; both definitions are
  reported because they are different frames, not two estimates of one number.

### 3.4 What QB-P1 may NOT do

Stated now so that no later result can be reinterpreted.

1. It may **not** introduce a fitted constant anywhere. Both estimated objects
   are empirical frequencies and empirical resamples. The two back-off floors
   (n = 30, twice) are declared in this document, before any fit.
2. It may **not** clip, floor, bound, cap or rebalance any share by rule, and
   may **not** assign any quarterback a share of 1.0 by rule.
3. It may **not** consume any sportsbook price, backup-QB availability market,
   or any market-derived column — including, by name,
   `spread_line`, `total_line`, `vegas_wp`, `vegas_home_wp`, `vegas_wpa`,
   `vegas_home_wpa`, `total_line`, `xpass` and `pass_oe`, which are present in
   the pbp schema and are prohibited as features, rules, filters, conditioning
   variables, or diagnostics.
4. It may **not** consume any postgame information in a pregame feature.
   Stage 1's features are depth rank, the incumbent bit, room composition, the
   opener flag and official inactives. Nothing else.
5. It may **not** score any 2026 game. See §7.2.
6. It may **not** be promoted, wired into production, or allowed to change
   `PATH_C_STATE`. The only proposed role, if §6.4 is met on a qualifying fold,
   is **prospective shadow: both arms computed and recorded per team-game,
   neither published.**
7. It may **not** edit `nfl/production/nonqb/qb_allocation.py`, `layers.py`
   (Q9-frozen, `481f005f682cd721`), `football_engine.py`, `run_forecast.py`, or
   anything under `nfl/prospective/q9shadow/`.
8. It may **not** be implemented at all until §7.1 is ruled on by the owner.

---

## 4. Which stages the evidence supports

The instruction was to seek the smallest architecture that correctly represents
the process, not to build six models. Here is the verdict on each of the six
conceptual stages, with the reason.

| stage | in QB-P1 | supported by the evidence in this repository? |
|---|---|---|
| **0 — deterministic eligibility** | Yes, as a gate with no parameter | **REPRESENTABLE, NOT IMPROVABLE.** Capped absolutely by the data gap (WS03 F12). Official inactives only, ~90 minutes out. Outbox §8.3 is the only lever |
| **1 — pregame starter probability** | Yes, estimated object #1 | **SUPPORTED for the pooled and mid-season regime**: 18–27 keys, 94.9–96.5% of team-games in keys with n ≥ 30. **NOT SUPPORTED as a week-1-specific estimate**: 160 week-1 team-games over 10 keys, two of them above n = 40 |
| **2 — planned package probability** | **No separate model.** Absorbed into the Stage 2 joint | **NOT SEPARATELY SUPPORTED.** Its 250 labelled team-games are labelled by a **predeclared rule** (`rotation_max_share: 0.35`), so a model fitted against them measures agreement with the rule. No pregame feature in this repository predicts a planned package |
| **3 — in-game exit / replacement hazard** | **No separate model.** Absorbed | **COMPUTABLE, NOT IDENTIFIED FOR THIS ESTIMAND.** pbp 2021–2024 carries play order and game state, so exit times exist. But (a) `s_dropbacks` is a share, not a time, and a hazard adds parameters without adding an identified quantity for it; (b) play-by-play **cannot separate an injury from a benching** — `REPLACEMENT_NO_RETURN` (142 team-games) is not an injury rate and must never be quoted as one |
| **4 — conditional replacement allocation** | **No separate model.** Absorbed | **NOT SEPARATELY IDENTIFIED.** 511 relief events in 2021–2024. The chart rank of the first reliever is `{rank 1: 10, rank 2: 269, rank 3: 36, not in the charted room: 196}` — **38% of first relievers are not in the charted QB room at all**, and by position they are overwhelmingly not quarterbacks. A rank-indexed allocation over the room cannot represent that; a donor vector with an `OTHER` slot can |
| **5 — blowout / garbage-time tail** | **No separate model.** Absorbed | **NOT SUPPORTED.** Its labels come from predeclared thresholds (`blowout_margin: 17`, `late_seconds_remaining: 900`). A Stage 5 fitted against them measures agreement with a rule, exactly as WS03 §4.6 states |
| **6 — kneel / package usage not requiring an exit** | **No separate model.** Absorbed | **NOT DESIGNABLE.** `KNEEL_OR_SPECIAL` holds **1 labelled team-game**. The realised footprint exists (second-QB share in (0, 0.10) in 6.15% of team-games) but is unlabelled. Nothing in this repository can design it |

**So the smallest defensible architecture is three stages and two estimated
objects**, and the honest statement of it is: *stages 2 through 6 are real
phenomena that this repository cannot identify separately, so they are
represented jointly and implicitly, in their realised proportions, and the
architecture says so rather than fitting five models that would each measure a
rule or a definition.*

---

## 5. Predeclared strata for evaluation

Seven strata are required. Four of them are defined by **predeclared rules**
rather than by ground truth, and that is marked, because a metric computed
inside a rule-defined stratum measures agreement with the rule.

| stratum | definition | ground truth or rule? |
|---|---|---|
| S1 **season opener** | `is_season_opener == True` from the ordinal gap | fact |
| S2 **weeks 2+** | its complement | fact |
| S3 **established starter** | the room's rank-1 QB was the arg-max primary in **each** of the team's three preceding team-games | **rule** (window length declared here) |
| S4 **uncertain starter** | room configuration is DISAGREE or NO_PREV_PRIMARY_IN_ROOM, per `qb_allocation`'s own labels | fact, from the chart |
| S5 **legitimate rotation / package QB** | `PLANNED_ROTATION_OR_PACKAGE`, `rotation_max_share: 0.35` | **rule** |
| S6 **injury replacement** | `REPLACEMENT_NO_RETURN` | **rule, and not an injury rate** |
| S7 **blowout backup use** | `BLOWOUT_RELIEF`, `blowout_margin: 17`, `late_seconds_remaining: 900` | **rule** |

S5, S6 and S7 are **reported, never used as an acceptance gate**, for exactly
that reason.

**The AGREE trap, declared.** 90.7% of the mid-season frame is AGREE, so the
AGREE cell and the league marginal are nearly the same estimate. *"The model
matches reality in AGREE rooms"* is **not validation** and may not be quoted as
one, in either arm.

---

## 6. Evaluation design

**Designed here. Not run here. No confirmatory comparison is authorised by this
document.**

### 6.1 Arms

- **A0 — incumbent.** `cell_of` / `allocate` as frozen. Baseline of record.
- **A1 — QB-P1 with I-LAST.** The architecture change alone, incumbent
  definition **unchanged**. This is the clean architectural treatment.
- **A2 — QB-P1 with I-MODAL.** A1 plus the boundary-aware incumbent.
- **A3 — QB-P1 with I-FIRSTSNAP.** A1 plus the first-snap-based incumbent.

A1 is declared the **primary** candidate. A2 and A3 are secondary and exist so
that the architecture change and the incumbent change are never confounded —
reporting only A2 against A0 would leave it impossible to say which half moved.

Same rows, same prefix cut, same seed, same draw count, same frame builder, same
room assembly in every arm. A fold that cannot run is reported with a **named
cause**, never averaged in as `nan`.

### 6.2 Folds, and the sample-splitting rule

**The rule: no candidate may be selected on the sample that justified the
hypothesis.**

- **2021–2024** (n = 2,133 team-games with a charted first-snapper) is the
  **fit and exploratory** frame. §1.3 lists what was already inspected on it.
  Every result on this frame is labelled **EXPLORATORY** in every artifact,
  every table and every summary sentence, and **cannot promote anything**.
- Within it, all estimation is **walk-forward**: for evaluation season *Y*,
  every frequency and every donor pool comes from seasons `< Y` only, and the
  incumbent feature uses a strictly-earlier **ordinal** prefix cut by `bisect`,
  because a team can carry two rows at one ordinal after a mid-week move.
  Exploratory evaluation folds: **2022, 2023, 2024**. 2021 is fit-only.
- **A confirmatory fold requires untouched games and there is exactly one
  candidate inside reach: 2025.** It requires two outbox deliveries (§8.1,
  §8.2). If they arrive, 2025 is sealed **fit-blind**: the arms, the code sha,
  the back-off floors and the donor strata are frozen and hashed **before any
  2025 row is scored**, and the seal is recorded before the first read.
- **2026 is prospective shadow only** and is subject to §7.2 and §7.5.

**Stated plainly: as the repository stands today, QB-P1 has no confirmatory
fold. Nothing this workstream produces on 2021–2024 can establish that a
variant is better. What would establish it is 2025 with `pbp_2025` and the
schedule join, fit-blind, or a prospective 2026 shadow accumulated forward.**

### 6.3 Metrics

**Primary, pre-specified, in this order:**

1. **Brier score on `took_the_first_snap`**, per QB-game, pooled over folds.
   This is Stage 1's own estimand and must be scored directly. Defined only
   where pbp exists.
2. **CRPS of `s_dropbacks`**, per QB-game, pooled. This is the incumbent's own
   metric, so the comparison is like for like.
3. **Energy score of the room's share vector**, per team-game, pooled. This is
   new and it is the point: D-ANTI and D-FANOUT are **dependence** defects, and
   no per-quarterback metric can see them. A proper multivariate score can.

**Reported beside, never in place of:**

- all three metrics stratified by S1–S7 with **n and cluster count on every
  row**;
- `P(charted QB1 share = 0)` against realised, per stratum;
- `P(≥ 2 QB with share ≥ 0.10)` against realised — incumbent slate value
  **0.1877** against a realised base rate **0.0826**;
- `P(≥ 3 QB takers)` against realised **0.0023**, and
  `P(third | second) = 0.0144`;
- backup–backup correlation against WS09's **+0.87 … +0.96**;
- team closure residual, which must remain exactly **0.0000**;
- the `OTHER` slot's mean mass against realised **0.0069**;
- the week-1 DISAGREE stratum on its own.

### 6.4 Uncertainty, clustering, and acceptance

**Games are not independent observations.** Clustering is predeclared here:

- **primary cluster: team-game**, blocked bootstrap, **B = 2,000**, on the
  paired per-observation metric difference;
- **secondary cluster: team** (≤ 32 clusters), required for every week-1
  stratum, since one team contributes one row per season;
- **tertiary cluster: game date / slate**;
- **the reported interval is the widest of the three**, always with its cluster
  count printed;
- **no naive binomial standard error is emitted anywhere**;
- where the cluster count is below 20, results are reported to **two
  significant figures only**.

**Acceptance criteria, fixed before any result.** A1 is preferred over A0 only
if **all** of:

1. pooled Brier on `took_the_first_snap` improves; **and**
2. pooled CRPS on `s_dropbacks` improves or the widest 95% interval on the CRPS
   difference lies entirely at or below +0.0000; **and**
3. pooled energy score on the room share vector improves and its widest 95%
   interval excludes zero; **and**
4. the direction of (1) and (3) is consistent in **all three** exploratory folds
   (2022, 2023, 2024); **and**
5. closure residual is exactly **0.0000** in every fold; **and**
6. **no stratum is degraded**: within S2 (weeks 2+) and S3 (established
   starter), Brier and CRPS may not worsen by more than a predeclared
   equivalence margin of **0.002** each, and the energy score by more than
   **2% of A0's pooled energy score in the same stratum**, judged by **TOST** at
   the 95% level, clustered as above.

**Rejection is the default.** If (1) and (3) hold but (2) or (6) fails, the
return reads: *the architecture improves starter identification and the joint
dependence at the cost of the marginal share distribution, and is not adopted.*
If a week-1 stratum improves but the pooled metrics do not, the return reads:
*the treatment is confined to 160 team-games across five seasons and the pooled
evidence does not support it.*

**The words "unbiased", "stable", "closed" and "correct" are not used anywhere
in the reporting of this experiment**, except where clause 6 makes an
equivalence claim, which carries a predeclared margin and a TOST for exactly
that reason. A failure to reject is a failure to reject, never evidence of
adequacy. The one exception is the closure residual in clause 5, which is an
arithmetic identity of the resampler and is checked as such, not asserted as a
statistical property.

### 6.5 Week 2 — what it must decide, and what it may not

**A hard constraint on every conclusion, not a caveat: 100% of the current live
QB rows are season openers, so a general QB-allocation defect and a week-1
cold-start defect cannot be separated in this sample.** Every statement about
"the QB defect" made on week-1 data alone is a statement about a confounded
population.

Week 2 2026 is the first slate on which `is_season_opener` is false, and it is
therefore the first observation that can **assign** the defect to a population.
Predeclared now, before the slate:

**W2-1. The separation observation.** Record, per team-game, both arms sealed
pregame: the room key, the Stage 1 vector, `P(charted QB1 share = 0)`,
`P(≥ 2 QB with share ≥ 0.10)`, the backup–backup correlation, and the realised
outcome. The reading:

- if the incumbent's elevated `P(charted QB1 share = 0)` **persists** in week 2,
  the defect is **general** — D-MARG, D-RELIEF, D-ANTI, D-ZERO — and the
  boundary is a magnifier, not the cause;
- if it **collapses** toward the realised rate, the defect is **predominantly
  cold-start** — D-BOUND and D-POOL — and the architecture's priority ordering
  changes accordingly.

**W2-2. The eligibility residue.** Record whether unranked rostered
quarterbacks are still promoted to rank 3 once the week-2 chart lands — 119
roster QBs against 92 charted, 27 with no depth row — and whether any of them
still routes into a high-share cell.

**W2-3. The fanout.** Record the realised count of QB-position dropback takers
per team-game against the model's implied distribution, and against the
historical `{1: 1786, 2: 342, 3: 5}`.

**W2-4. What week 2 may NOT decide, declared in advance.** One week is 32
team-games, at most 32 team clusters, on a **single date cluster**. It cannot
deliver a confirmatory verdict on any arm, it cannot promote anything, and **no
threshold in the week-2 read may be loosened, re-specified or promoted into a
test after the slate is seen.** Week 2 assigns the defect to a population. It
does not measure an improvement. An empty or null week-2 read is a valid result.

---

## 7. Owner-ruling items

Flagged, **not acted on**. Each is either irreversible, changes a rule the owner
set, changes what counts as evidence, or exposes a conflict between two of his
own prior statements.

**7.1 — QB-P1 does not amend frozen QB3 §4; it replaces it.**
`predeclaration_qb3.md` (sha16 `be61392619d45f3a`) §4 reads, verbatim:

> Two pregame variables, both declared by football logic before any evaluation:
> `rank` ∈ {1, 2, 3+} from the depth chart; `was_prev_primary` ∈ {yes, no} …
> **No other feature enters.**

QB-P1 replaces the cell structure with a room-configuration key and a donor
joint. This is **not** the "one extra argument" change WS03 §3.2 proposed. It
requires owner approval before any implementation. **Frozen §4 has not been
edited and must not be until that ruling exists.**

**7.2 — `pbp_2026` is in the tree and is a standing leakage hazard.**
`nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz` (10 games) and
`pbp_2026.d9e442ae17ba88e7.csv.gz` (2 games) hold 2026 week-1 REG play-by-play,
i.e. **forecast-season outcomes**, in the same directory as the historical
folds. WS-I's own first feasibility pass globbed `pbp_20*` and picked them up;
it was caught and re-run on 2021–2024 only, and no 2026 row reached any number
in this document. A glob that anyone else writes will do the same. Recommend
quarantine or a distinguishing prefix. Not WS-I's file; coordinator/owner
ruling.

**7.3 — the estimand's denominator changes.** The `OTHER` slot means
`s_dropbacks` becomes *share of team dropbacks*, of which the QB room takes
1 − `OTHER`, rather than *share of QB-room dropbacks* closed to 1. Mean 0.0069,
positive in 10.4% of team-games. This changes what the number means and touches
the production interface contract. Owner ruling.

**7.4 — first-snap replaces arg-max as the definition of "starter".** This
changes the estimand's definition and makes every prior QB3 artifact
non-comparable on that axis (they differ in 2.81% of team-games). Owner ruling,
and a required note on any table that puts an old and a new number side by side.

**7.5 — WS03 §3.7 forbids scoring any 2026 game, while the only forward path
to a confirmatory result is a 2026 prospective shadow.** These two are in
tension. WS-I does not resolve it and does not proceed on either reading. A
prospective shadow that is sealed pregame, never published, and never allowed to
change `PATH_C_STATE` may satisfy both, but that is a ruling, not a deduction.

**7.6 — four QB predeclarations would now be live.** `predeclaration_qb3.md`
(baseline), `_ab` (`07b36d0e1e608cef`), `_seasonboundary`
(`6cb5c522e3fbd63b`), and this one. WS03 already ruled that AB and SB must not
run in parallel. The owner must choose which survive. QB-P1 **subsumes** the
season-boundary proposal (its opener term is QB-P1's rung-1 key) and is
**broader than** QB3-AB (which leaves steps 2 and 3 of `allocate` untouched).
Neither is modified by this document.

---

## 8. Outbox requests

These are **assigned, not blocked**. Each states exactly what is needed.

**8.1 — `pbp_2025` regular-season play-by-play. Highest value.**
Season 2025, `season_type == REG`, weeks 1–18, all 272 games. Required columns:
`game_id, old_game_id, season, week, season_type, posteam, defteam, play_id,
order_sequence, qtr, game_seconds_remaining, score_differential, qb_dropback,
qb_kneel, qb_spike, qb_scramble, sack, pass_attempt, passer_player_id,
passer_player_name, rusher_player_id, rusher_player_name`.
**Explicitly excluded and must not be delivered in the file:** `spread_line`,
`total_line`, `vegas_wp`, `vegas_home_wp`, `vegas_wpa`, `vegas_home_wpa`,
`xpass`, `pass_oe` — market-derived columns, prohibited by §3.4 clause 3.
Acceptance test: 272 REG games; every `(season, week, posteam)` with ≥ 1
`qb_dropback == 1` resolves to a non-empty passer or rusher id; team-game count
in the 540–544 range. Delivered with a sha256 and a provenance block matching
the 2021–2024 convention.
*Why it matters:* without it the first-snap definition has **no season outside
the fit frame**, and QB-P1 has **no confirmatory fold at all**. `pbp_2020`
(same schema, same exclusions) is a secondary request that would extend the fit
frame to match the depth-chart coverage.

**8.2 — 2025 NFL regular-season schedule, to build the `dt → (season, week)`
join.** For season 2025, weeks 1–18, `game_type == REG`: `game_id, season,
week, game_type, gameday (date), gametime / kickoff timestamp in UTC,
home_team, away_team`. Needed to key
`nfl/research/inputs/dc25_daily.csv.gz` (sha16 `5e0eba5bac474334`, 146,246
rows, 221 distinct `dt` from 2025-08-03T10:09:07Z to 2026-03-14T07:32:09Z,
21,342 QB rows, schema `dt, team, gsis_id, pos_abb, pos_rank` with no season or
week column). Acceptance test: every `dt` maps to exactly one `(season, week)`;
the snapshot `dt` is **strictly before** that team's kickoff for that week; and
the resulting 2025 QB frame yields ~544 team-games and 32 week-1 rooms, matching
WS03 §4.4. A daily snapshot cut at the pregame instant is **stronger**
provenance than a season leaf, which may be post-hoc.

**8.3 — pregame roster status: active-53 vs practice squad vs reserve.**
Per team, per week, seasons 2020–2026, timestamped, with the timestamp
**strictly before kickoff**: `season, week, team, gsis_id, position,
roster_status` distinguishing at minimum ACTIVE-53, PRACTICE_SQUAD,
PS_ELEVATED, IR, PUP, NFI, SUSPENDED, and the status-effective timestamp.
Acceptance test: for any (season, week, team) the ACTIVE-53 count is ≤ 53 and
the QB subset is ≥ 1; no row carries a timestamp at or after that team's
kickoff. *This is the only thing that can lift the Stage 0 ceiling* (§3.1;
WS03 F12, §4.8). It is a **data gap, not a modelling gap**, and no estimator
repairs it.

None of these is stubbed, mocked, or routed around. Until 8.1 and 8.2 arrive,
QB-P1's evaluation is exploratory and the design says so in §6.2.

---

## 9. Declarations

- **CODE CHANGED: NO.** No production code was written in this phase.
- No file outside `nfl/research/remediation/ws_i/` was created or modified.
- Frozen QB3 §4 was **not** edited. It is flagged as owner-ruling item §7.1.
- The suite was not run. No market data was opened. No wager is recommended and
  none is implied.
- No 2026 game was scored, and no 2026 row entered any number in this document.
- Every result this pre-registration anticipates on 2021–2024 is
  **EXPLORATORY** and cannot promote anything.
