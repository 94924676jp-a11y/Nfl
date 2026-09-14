# WS-I — QB participation: architecture study and design report

**CODE CHANGED: NO.** Research only. Nothing outside
`nfl/research/remediation/ws_i/` was created or modified. No production module,
no frozen artifact, no test, no governance file was touched. The suite was not
run. No market data was opened. No forecast was produced or resealed. No 2026
game was scored.

Written 2026-09-14. Repo `/home/user/nfl`, branch
`claude/nfl-greenfield-architecture-stsxmk`, HEAD `837d52f`, interpreter
`python3.12`.

**Companion pre-registration:** `PREREG_qb_participation.md`,
sha256 `88c671e1d713833c83c5a6b4ac16bc47ea125a0f74cece8a59591fc07f028c68`
(sha16 `88c671e1d713833c`), 37,845 bytes, written **before** this report and
before any candidate code exists. That document is the binding one. This report
explains and evidences it.

---

## 1. The answer in one page

**The smallest architecture I can justify is three stages carrying two estimated
objects.**

```
Stage 0   deterministic eligibility gate          NO PARAMETER
Stage 1   P(who takes the first snap | room)      ESTIMATED OBJECT #1
Stage 2   joint share vector | first-snap taker   ESTIMATED OBJECT #2
```

Conceptual stages 2 through 6 — planned package, exit hazard, conditional
replacement allocation, blowout tail, kneel usage — are **real phenomena that
this repository cannot identify separately**. They are represented jointly and
implicitly by Stage 2's donor vectors, in their realised proportions and with
their realised co-occurrence structure. The architecture says so rather than
fitting five models, three of which would measure agreement with a predeclared
rule and one of which has a single labelled team-game.

**The two changes that do the work are both definitional, not statistical.**

1. **"Starter" becomes the man who took the first snap**, not the arg-max
   dropback taker. Under that definition `P(starter takes zero dropbacks | he
   started)` is **0 by construction**. The incumbent assigns that event 7.36% of
   the mass in its cleanest cell against a realised 0 of 1,700. This is a
   structural repair, not a fitted correction, not a floor, not a clip.
2. **The share vector is resampled whole**, not composed from marginals. The
   incumbent draws an identity from renormalised marginal starting rates and
   then spreads the leftover by those same rates. A realised vector already
   contains the dependence; composing one manufactures it.

**Nothing here is authorised, built, fitted or applied.** Implementation is
blocked on an owner ruling (§7.1 of the prereg) because QB-P1 does not amend
frozen QB3 §4, it replaces it.

---

## 2. Why not the obvious repairs

### 2.1 Not eligibility

The external review implied constraining the QB pool to the active 53. **That
was already run**, in `d652afb`, and titled honestly: *"Removing the wrong
quarterback moved the defect, it did not fix it."* Result: Prescott 0.5416,
Howell 0.4584, `P(Prescott takes 0 dropbacks) = 0.4273`, corr(Prescott, Howell)
= **−0.9240**. WS24 R7 records the same verdict. **Eligibility was never the
binding mechanism** and is not re-proposed as one in this design.

The QB pool's exemption from R5 (`run_forecast.py:638`, comment at `:625-628`
*"The QB pool is untouched"*) and the 27 roster-QBs with no depth row who are
all promoted to rank 3 are real and they are recorded — but they change **which
man** receives the defective allocation, not **that** the allocation is
defective.

### 2.2 Not tweaking the pooled cell probabilities

Per the standing instruction, and independently because the evidence says the
cell structure is the wrong object, not a mis-valued one. Cell `(1,0)` is 101
week-1 rows at mean share 0.9783 with `P(0) = 0.0000`, plus 220 mid-season rows
at mean 0.2726 with `P(0) = 0.6909` — **one cell, two populations, 3.6× apart in
the mean and opposite in the mode**. The pooled 0.4946 describes neither.
Re-estimating 0.4946 to some other single number cannot describe both either.

### 2.3 Not six fitted stages

See §5. Three of the six would be fitted against predeclared rules
(`rotation_max_share: 0.35`, `blowout_margin: 17`,
`late_seconds_remaining: 900`); one has one labelled team-game; one is
computable but not identified for a share estimand. Fitting them would add
parameters and subtract honesty.

---

## 3. What I measured, and what it says

All measurements are WS-I's own, computed 2026-09-14 on this checkout under
`python3.12`. They are **development-data measurements on seasons 2020–2024**
and the prereg §1.3 declares them as such. Sources: `panel_p3.csv.gz`
(`6cb51092175c7a06`), `dc_2020..2024.csv.gz`, and
`nfl/research/postgame/pbp_2021..2024.*.csv.gz`.

### 3.1 The room, and the frame

| quantity | value |
|---|--:|
| frame rows (charted QB × team-week, 2020–2024) | 6,446 |
| charted team-games | 2,685 |
| charted room size distribution | `{1: 34, 2: 1549, 3: 1094, 4: 8}` |
| week-1 charted team-games | **160** |
| charted team-games matched to pbp (2021–2024) | **2,173**, **0 unmatched** |
| of those, first-snap taker **is** in the charted room | **2,133** (98.16%) |

### 3.2 First snap is a different object from arg-max, and it is the right one

Measured on pbp 2021–2024, REG only, n = 2,174 team-games with ≥ 1 dropback:

| quantity | value |
|---|--:|
| first-snap taker ≠ arg-max taker | **61 of 2,174 (0.0281)** |
| distinct dropback-takers per team-game | `{1: 1653, 2: 482, 3: 39}` |
| mean first-snap-taker share | **0.9571** |
| `P(first-snap taker's share = 1)` | **0.7603** |

That 2.81% is the entire "started and was pulled" population. Under
`qb3_lib.primary_of` (arg-max, `:79-81`) it is definitionally invisible — WS03
F10 names this and it is confirmed here on the play-by-play.

### 3.3 Donor availability for the conditional joint

Charted first-snapper, pbp 2021–2024, n = 2,133, keyed by (starter's clipped
depth rank, number of other QBs in the room):

| key | n | mean starter share | P(starter share = 1) |
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

Five strata carry n ≥ 39 and cover 2,099 of 2,133 team-games. The rest back off
under the ladder declared in prereg §3.3, floor n = 30, declared before any fit.

**In every one of these strata `P(starter share = 0)` is zero by construction.**
That is the repair of the single decisive number in
`QB_PARTICIPATION_CAUSAL_AUDIT.json`: reality 0 of 1,700, incumbent 0.0736.

### 3.4 The model couples backup QBs; realised football does not — two halves of one defect

**Two measurements of two different objects.** They are reported together
because the pair is the finding; neither overturns the other, and an earlier
draft of this report was wrong to phrase it as a contradiction of WS09.

**Half one — the model's dependence structure, measured by WS09.**
`nfl/research/parallel_pass/ws09/WS09_JOINT_STRUCTURE.md:494`, row **J-9**:
*"Backup QBs enter the game together rather than alternatively — **CONFIRMED**
(+0.87 … +0.96), mechanism located at `qb3_lib.py:183-192`"*. That correlation
is between backup quarterbacks' **draws in the model's sealed artifacts**.
WS09's frame is declared in its own title — *"Joint simulation structure,
audited **from the stored draws**"* — and its §13 closes J-18 with *"no outcome
data was touched; this workstream measured **structure only**"*. J-9 is a
statement about the engine and never claimed to be a statement about realised
football.

**Half two — realised football, measured here.** WS-I's own measurement on
realised play-by-play 2021–2024, same frame as §3.3, n = 2,133, counting
**QB-position** dropback takers:

| quantity | value |
|---|--:|
| QB-position dropback takers per team-game | `{1: 1786, 2: 342, 3: 5}` |
| `P(≥ 2 QB takers)` | **0.1627** |
| `P(≥ 3 QB takers)` | **0.0023** |
| `P(a third QB throws \| a second does)` | **0.0144** |

**Taken together the two halves are a confirmed defect, sharply quantified,
with each half independently established on its own frame.** The engine couples
backup quarterbacks at **+0.87 … +0.96** — one `rem` scalar fanning out to
every non-primary quarterback in fixed proportion, so they enter **together**
(`qb3_lib.py:183-192`) — while in realised football they enter
**alternatively**: conditional on a second quarterback throwing, a third does so
**1.44%** of the time, and three quarterbacks throw in **0.23%** of team-games.
The model's dependence structure is wrong **in a measured direction and by a
measured amount**. That is the direct evidence for the Stage 2 joint-resampling
design, which is the only element of QB-P1 that changes a dependence structure.

A donor resample reproduces 0.0144 because 0.0144 is what the donors contain.
No coefficient is fitted to achieve it.

### 3.5 The denominator defect — also new

The room's shares are closed to 1.0, but dropbacks are taken by men outside the
room. Over the same 2,133 team-games:

| quantity | value |
|---|--:|
| non-room dropback share, mean | **0.0069** |
| non-room dropback share, median | 0.0000 |
| team-games with non-room mass > 0 | **221 (0.1036)** |
| team-games with non-room mass ≥ 0.05 | **32** |

And on the wider frame of all 2,685 charted team-games against the panel
denominator: mean uncharted share **0.0218**, exceeding 0.01 in **85**
team-games. These are two different frames, not two estimates of one number, and
both are reported as such.

**Who these men are** — position of dropback-takers outside the charted room, in
relief events: **WR 110, P 32, QB 32, RB 27, TE 19, DB 3, K 1, LB 1, OL 1,
not-in-panel 3.** Trick plays, punter fakes, Wildcat. Only 32 of 229 are
quarterbacks.

And the consequence for a Stage 4 design: the chart rank of the **first**
reliever, when the starter's share is below 1, is
`{rank 1: 10, rank 2: 269, rank 3: 36, not in the charted room: 196}`.
**38.4% of first relievers are not in the charted QB room at all.** A
rank-indexed allocation over the room structurally cannot represent that. A
donor vector with an explicit `OTHER` slot can, and does, for free.

### 3.6 Room-configuration keys are far less sparse than feared

2,685 charted team-games, 2020–2024:

| key form | distinct keys | team-games in keys n ≥ 30 | n ≥ 50 | n ≥ 100 |
|---|--:|--:|--:|--:|
| without opener term | 18 | 2,591 (0.965) | 2,556 (0.952) | 2,417 (0.900) |
| with opener term | 27 | 2,547 (0.949) | 2,430 (0.905) | 2,254 (0.839) |

This is the finding that makes a **directly estimated room-conditional
multinomial** feasible, which is what removes the renormalisation defect: the
incumbent renormalises marginal starting rates whose in-room sum runs
**0.5608 / 1.0014 / 1.2056** (min / median / max) across the 32 week-1 2026
rooms, rescaling by up to 1.78×, with nothing logged. A distribution estimated
as a distribution sums to 1 because it was estimated that way.

**But week 1 alone is 160 team-games over 10 keys**, only two of them above
n = 40. That is the ceiling, and it is not repairable by compute.

---

## 4. The architecture, and how each defect dies

| defect | incumbent mechanism | how QB-P1 addresses it | by construction or by estimate? |
|---|---|---|---|
| **D-ZERO** starter carries `P(share=0)` reality assigns 0 | `build_frame` conditions on the room, not on having started | first-snap conditioning | **construction** |
| **D-MARG** marginal rates renormalised in-room | `qb3_lib.py:169-171` | Stage 1 is a directly estimated room-conditional multinomial | **construction** |
| **D-RELIEF** starting rates reused as relief weights | `qb3_lib.py:183-192` | remainder is the donor's realised remainder | **construction** |
| **D-ANTI** corr = −1.0000 in a 2-QB room | residual allocation with n = 2 | joint resample carries realised dependence | **construction** |
| **D-FANOUT** model couples backups at r = +0.87…+0.96 (WS09 J-9, from the stored draws) against realised alternation | one `rem` scalar fans out | donors contain the realised `P(third \| second) = 0.0144` | **estimate**, from 2,133 team-games of realised play-by-play |
| **D-DENOM** shares closed to 1 over the QB room | closure at `:196-197` | explicit `OTHER` slot | **construction** |
| **D-BOUND** week-1 incumbent = prior week 18 | `previous_primary_detail` `:117` / `:452` | opener flag at rung 1 of the key; incumbent definition as a **declared arm** | **estimate, and unproven** — see §6 |
| **D-POOL** no week term in `cell_of` | `qb3_lib.py:130` | the opener flag is part of the key | **construction** |
| **D-ELIG** QB pool exempt from R5 | `run_forecast.py:638-644` | **not addressed, deliberately** — `d652afb` showed it is not binding | — |

The column on the right matters more than it looks. **Six of the eight repairs
are definitional**: they follow from conditioning on the first snap and
resampling a vector, and they hold whatever the data turn out to say. Only two
depend on an estimate being right, and one of those two — the boundary — is the
one this repository **cannot** confirm.

---

## 5. Which stages the evidence supports, and which it cannot

| stage | verdict | the reason, stated once |
|---|---|---|
| **0 — eligibility** | **REPRESENTABLE, NOT IMPROVABLE** | No pregame active-53 / practice-squad / reserve signal exists (WS03 F12). Official inactives only, ~90 min out. A data gap, not a modelling gap. Outbox §8.3 is the only lever |
| **1 — pregame starter probability** | **SUPPORTED pooled; NOT SUPPORTED week-1-specific** | 18–27 keys, 94.9–96.5% of team-games in keys with n ≥ 30. But week 1 is 160 team-games over 10 keys, two above n = 40, accruing at 32 per season |
| **2 — planned package** | **NOT SEPARATELY SUPPORTED** | Its 250 labelled team-games are labelled by a predeclared rule, `rotation_max_share: 0.35`. A model fitted against them measures agreement with the rule. And no pregame feature in this repository predicts a planned package |
| **3 — exit / replacement hazard** | **COMPUTABLE, NOT IDENTIFIED for this estimand** | pbp carries play order and game state, so exit times exist. But `s_dropbacks` is a share, not a time — a hazard adds parameters without adding an identified quantity for it. And play-by-play **cannot separate an injury from a benching**: `REPLACEMENT_NO_RETURN` (142 team-games) is not an injury rate and must never be quoted as one |
| **4 — conditional replacement allocation** | **NOT SEPARATELY IDENTIFIED** | 511 relief events. **38.4% of first relievers are outside the charted room**, and by position overwhelmingly not quarterbacks (§3.5). Rank-indexed allocation over the room cannot represent that |
| **5 — blowout tail** | **NOT SUPPORTED** | Labels come from predeclared thresholds `blowout_margin: 17`, `late_seconds_remaining: 900`. A Stage 5 fitted against them measures agreement with a rule |
| **6 — kneel / package without exit** | **NOT DESIGNABLE** | `KNEEL_OR_SPECIAL` holds **1 labelled team-game**. The realised footprint exists — second-QB share in (0, 0.10) in 6.15% of team-games — but is unlabelled |

**So: two stages can be estimated, one is a gate with no parameter, and four are
absorbed because the evidence cannot separate them.** That is the honest
architecture, and the absorption is not a shortcut — a realised share vector
contains every one of those four phenomena in the proportion it actually occurs.

---

## 6. The ceiling, stated before any result

### 6.1 There is no `pbp_2025`, and that is the binding fact

`nfl/research/postgame/` holds `pbp_2021`, `pbp_2022`, `pbp_2023`, `pbp_2024`
and **`pbp_2026`**. `panel_p3.csv.gz` *does* carry 2025 (9,638 rows), so the
outcome side of a 2025 fold exists — but **arg-max only**. The first-snap
definition on which six of the eight repairs rest is computable for **2021–2024
and no other historical season in this repository.**

Consequence, stated plainly: **QB-P1 has no confirmatory fold as the repository
stands.** 2021–2024 is the fit frame and is also the frame that selected the
hypothesis. Everything computed on it is exploratory and cannot promote
anything. What would change that is outbox item 8.1 (`pbp_2025`) together with
8.2 (the schedule join), fit-blind, or a prospective 2026 shadow accumulated
forward under a ruling on prereg §7.5.

### 6.2 The week-1 sample does not grow

160 week-1 team-games in the whole historical frame, 10 configuration keys,
32 new ones per season. The DISAGREE stratum carrying the largest effect is
**21 team-games across 16 team clusters**. **No amount of compute raises this.**
A confirmatory week-1 result on historical data alone is roughly a decade away,
and that is the honest answer.

### 6.3 What is already settled, and what it settles

Two realised rates are exactly zero and therefore bound the truth by rule of
three: `P(starter takes zero dropbacks | he started) = 0/1700` (~0.0018 upper
bound) and `P(week-1 lower-ranked incumbent is primary) = 0/21` (~0.133).
Against model values of 0.0736 and 0.6167 those are **decisive as refutations**.
They are **not** informative about what the right value is. Refuting 0.6167 is
not establishing 0.05.

### 6.4 The AGREE trap

90.7% of the mid-season frame is AGREE, so the AGREE cell and the league
marginal are nearly the same estimate. *"The model matches reality in AGREE
rooms"* is not validation, in either arm, and is declared unusable in prereg §5.

---

## 7. The preregistered evaluation design, in brief

Full statement in `PREREG_qb_participation.md` §6. Summary:

**Arms.** A0 incumbent · A1 QB-P1 with the incumbent's own incumbent definition
(the clean architectural treatment, declared **primary**) · A2 QB-P1 with a
prior-season **modal** incumbent · A3 QB-P1 with a prior-season modal
**first-snap** incumbent. A2 and A3 exist so the architecture change and the
boundary change are never confounded — A2-against-A0 alone would leave it
impossible to say which half moved.

**Strata, all seven required.** S1 season opener · S2 weeks 2+ · S3 established
starter · S4 uncertain starter · S5 rotation/package · S6 injury replacement ·
S7 blowout. **S5, S6 and S7 are rule-defined**, so they are reported and never
used as an acceptance gate.

**Metrics.** Brier on `took_the_first_snap` · CRPS on `s_dropbacks` (the
incumbent's own metric, so the comparison is like for like) · **energy score on
the room's share vector**. The third is the point: D-ANTI and D-FANOUT are
dependence defects and no per-player metric can see them.

**Uncertainty.** Blocked bootstrap B = 2,000, clustered by **team-game**
(primary), **team** (required for every week-1 stratum), and **game date**;
**the widest of the three is reported**, always with its cluster count. No naive
binomial SE anywhere. Below 20 clusters, two significant figures only.

**Acceptance.** Six clauses, all required, rejection the default; degradation
checked by **TOST** against margins declared in advance (0.002 Brier, 0.002
CRPS, 2% of baseline energy score). The words "unbiased", "stable", "closed"
and "correct" do not appear in the reporting except inside that one equivalence
clause, which is why it carries a margin and a test.

**Sample splitting.** 2021–2024 is fit + exploratory and cannot promote.
Confirmation requires 2025 fit-blind (needs outbox 8.1 and 8.2) or a sealed
prospective 2026 shadow (needs a ruling). Walk-forward throughout: for
evaluation season *Y*, every frequency and donor pool comes from seasons `< Y`,
with a strictly-earlier **ordinal** prefix cut by `bisect`, because a team can
carry two rows at one ordinal after a mid-week move.

---

## 8. What week 2 must decide

**The hard constraint, not a caveat: 100% of the current live QB rows are season
openers, so a general QB-allocation defect and a week-1 cold-start defect cannot
be separated in this sample.** Every statement about "the QB defect" made on
week-1 data alone is a statement about a confounded population, and this report
does not make one.

Week 2 2026 is the first slate on which `is_season_opener` is false. It is the
first observation that can **assign** the defect to a population. Preregistered
before the slate:

| id | what is recorded, both arms sealed pregame | what it decides |
|---|---|---|
| **W2-1** | room key, Stage 1 vector, `P(charted QB1 share = 0)`, `P(≥2 QB with share ≥ 0.10)`, backup–backup correlation, realised outcome | **persists** → the defect is general (D-MARG, D-RELIEF, D-ANTI, D-ZERO) and the boundary is a magnifier, not the cause. **collapses** → the defect is predominantly cold-start (D-BOUND, D-POOL) and the priority ordering changes |
| **W2-2** | whether unranked roster QBs are still promoted to rank 3 once the week-2 chart lands — 119 roster QBs against 92 charted, 27 with no depth row | whether the eligibility residue still routes anyone into a high-share cell |
| **W2-3** | realised QB-position dropback-taker counts against the model's implied distribution and against historical `{1: 1786, 2: 342, 3: 5}` | whether D-FANOUT is visible live |

**What week 2 may not decide, declared now.** One week is 32 team-games, at most
32 team clusters, on a **single date cluster**. It cannot deliver a confirmatory
verdict, it cannot promote anything, and **no threshold in the week-2 read may
be loosened, re-specified or promoted into a test after the slate is seen.**
Week 2 assigns the defect to a population; it does not measure an improvement.
An empty or null week-2 read is a valid result.

---

## 9. Owner-ruling items

Flagged, not acted on. Full statements in prereg §7.

1. **QB-P1 replaces frozen QB3 §4, it does not amend it.**
   `predeclaration_qb3.md` (`be61392619d45f3a`) §4 declares two variables and
   *"No other feature enters."* QB-P1 substitutes a room-configuration key and a
   donor joint. **Frozen §4 has not been edited and must not be until this is
   ruled on.** Implementation is blocked on it.
2. **`pbp_2026` is a standing leakage hazard.** Two files
   (`1415dd98ba7f701a`, 10 games; `d9e442ae17ba88e7`, 2 games) hold 2026 week-1
   REG outcomes in the same directory as the historical folds. WS-I's own first
   feasibility pass globbed `pbp_20*` and picked them up; it was caught and
   re-run on 2021–2024 only, and **no 2026 row reached any number in this
   report**. Anyone else's glob will do the same. Recommend quarantine or a
   distinguishing prefix. Not WS-I's file.
3. **The estimand's denominator changes.** The `OTHER` slot makes
   `s_dropbacks` a share of *team* dropbacks rather than of *QB-room* dropbacks
   closed to 1. Mean 0.0069, positive in 10.4% of team-games. Touches the
   production interface contract.
4. **First-snap replaces arg-max as the definition of "starter."** Changes the
   estimand and makes every prior QB3 artifact non-comparable on that axis —
   they differ in 2.81% of team-games. Any table putting an old and a new number
   side by side needs a note saying so.
5. **WS03 §3.7 forbids scoring any 2026 game, while the only forward path to a
   confirmatory result is a 2026 prospective shadow.** These are in tension.
   WS-I does not resolve it and does not proceed on either reading.
6. **Four QB predeclarations would now be live** — `qb3`, `_ab`
   (`07b36d0e1e608cef`), `_seasonboundary` (`6cb5c522e3fbd63b`), and this one.
   WS03 already ruled AB and SB must not run in parallel. QB-P1 **subsumes** the
   season-boundary proposal and is **broader than** QB3-AB. The owner must
   choose which survive. None was modified.

---

## 10. Outbox requests

Assigned, not blocked. Exact statements in prereg §8.

1. **`pbp_2025` regular-season play-by-play** — season 2025, `season_type ==
   REG`, weeks 1–18, all 272 games, with the column list and the acceptance test
   in prereg §8.1. **Market columns explicitly excluded from the delivery**:
   `spread_line`, `total_line`, `vegas_wp`, `vegas_home_wp`, `vegas_wpa`,
   `vegas_home_wpa`, `xpass`, `pass_oe`. *Highest value: without it the
   first-snap definition has no season outside the fit frame and QB-P1 has no
   confirmatory fold at all.* `pbp_2020` is a secondary request that would
   extend the fit frame to match depth-chart coverage.
2. **2025 NFL regular-season schedule** — `game_id, season, week, game_type,
   gameday, kickoff UTC, home_team, away_team` for 2025 weeks 1–18, to build the
   `dt → (season, week)` join for `dc25_daily.csv.gz` (`5e0eba5bac474334`,
   146,246 rows, 221 distinct `dt`, 2025-08-03T10:09:07Z → 2026-03-14T07:32:09Z,
   21,342 QB rows, no season or week column). Acceptance test in prereg §8.2:
   every `dt` maps to exactly one `(season, week)`, strictly before that team's
   kickoff, yielding ~544 team-games and 32 week-1 rooms.
3. **Pregame roster status** — active-53 / practice squad / PS-elevated / IR /
   PUP / NFI / suspended, per team per week, 2020–2026, timestamped strictly
   before kickoff. **The only thing that can lift the Stage 0 ceiling.** A data
   gap, not a modelling gap; no estimator repairs it.

None is stubbed, mocked into a passing test, or routed around.

---

## 11. Disagreements recorded

**With `predeclaration_qb3_ab.md` §0**, which states that *"the season boundary
is a symptom of the mixing, not the disease"* and proposes withdrawing QB3-SB.
WS03 already disagreed; this report agrees with WS03 and adds a second reason.
`P(starts) × P(share | starts)` does not repair the boundary, because Stage A's
declared feature set still contains `was_prev_primary` with no boundary term —
worth 0.4609 at the boundary against 0.8768 mid-season, with the sign reversing
in the DISAGREE stratum. **But the sharper point is that the split alone also
does not repair D-ANTI, D-FANOUT, D-RELIEF or D-DENOM**, because QB3-AB leaves
steps 2 and 3 of `qb3_lib.allocate` untouched, and those four defects all live
in step 3. This is a disagreement about a frozen artifact's reasoning, not about
anything irreversible; it is recorded, needs no escalation, and the design in
§7 is built so that whichever reading is right, A1-against-A0 answers it.

**A line-number correction carried forward.**
`DAL_NYG_PARTICIPATION_ROOT_CAUSE_AUDIT.md` cites `qb_allocation.py:193`.
Line 193 is `previous_primary()`, which has **zero callers repo-wide**. The live
path is `previous_primary_detail` at `:117`, called from `:452`. The finding is
unaffected; the citation is wrong and should not propagate further.

---

## 12. Declarations

- **CODE CHANGED: NO.** No production code was written.
- No file outside `nfl/research/remediation/ws_i/` was created or modified.
- Frozen QB3 §4 was **not** edited (owner-ruling item §9.1).
- `nfl/production/nonqb/qb_allocation.py`, `layers.py`, `football_engine.py`,
  `run_forecast.py`, `nfl/prospective/q9shadow/` and the WS-F / WS-G scorers
  were not touched.
- The suite was not run. No market data was opened. No wager is recommended and
  none is implied.
- No 2026 game was scored and no 2026 row entered any number in this report.
- Every anticipated result on 2021–2024 is **EXPLORATORY** and cannot promote
  anything.
- Nothing in this document is adequacy. Where a difference is not rejected, that
  is a failure to reject, not evidence of equivalence.
