# R2 — Stage-0 eligibility gate: the ineligible never enter the choice set

**Game** `2026_01_DEN_KC`, kickoff `2026-09-15T00:15:00Z`.
**Cutoff used** `observed_before = 2026-09-14T18:00:00Z`.
**Branch** `claude/nfl-greenfield-architecture-stsxmk`, base `2dc44ab`.
**Interpreter** `python3.12`. Nothing was committed, added, stashed or pushed.

| Artifact | Path |
|---|---|
| The gate | `nfl/production/eligibility_gate.py` (new) |
| Its tests | `nfl/tests/test_eligibility_gate.py` (new) |
| Tonight's snapshot | `nfl/research/v2/r2/R2_ELIGIBILITY_SNAPSHOT_2026_01_DEN_KC.json` |

```
python3.12 nfl/tests/run_suite.py --only test_eligibility_gate
modules 1  test functions 23  checks 78  FAILING CHECKS 0  RAISED 0
ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 0
SUITE PASS
```

`inactives.py` and `roster_status.py` were **not modified**. The gate consumes
them. `layers.py`, `qb_allocation.py`, `qb_room_v2.py`, `football_engine.py`,
`rushing_a1.py`, `depth_vintage.py`, `role_prior.py` and `nfl/product/**` were
not touched. The one call-site change the gate needs is in `run_forecast.py`,
which I do not own and which another agent has already modified in this working
tree — it is handed over in section 8 and **not applied**.

---

## 1. The snapshot schema

One audited row per player, keyed on `gsis_id`. No row is produced by inference.

| Field | What it carries |
|---|---|
| `status` | `OFFICIAL_INACTIVE` · `INJURY_OUT` · `SUSPENDED` · `ROSTER_RES` · `ROSTER_CUT` · `ROSTER_EXE` · `ROSTER_DEV` · `INJURY_DOUBTFUL` · `INJURY_QUESTIONABLE` · `ROSTER_ACT` · `NO_EVIDENCE` |
| `determination` | `determined` or `uncertain` |
| `authority` | `OFFICIAL_INACTIVE_LIST` (rank 1) · `OFFICIAL_INJURY_REPORT` (2) · `LEAGUE_SUSPENSION` (2) · `WEEKLY_ROSTER_STATUS` (3) |
| `authority_rank` | the integer, so precedence is readable rather than implied |
| `source_vintage` | the blob the statement was read out of |
| `content_hash` | sha256 of those bytes |
| `known_from` | the publication clock, where one exists |
| `known_from_authority` | e.g. `DERIVED_DETERMINISTIC`, `DELIVERED_EXPLICIT` |
| `known_by_no_later_than` | publication clock, else observation clock — retrieval is never earlier than publication, so this is a genuine upper bound and is kept in its own field rather than dressed up as `known_from` |
| `hours_known_before_kickoff` | the D7 question, per player |
| `reason` | plain-language sentence |
| `simulation_eligibility` | `EXCLUDED_DETERMINISTIC` · `EXCLUDED_BY_POOL_RULE` · `IN_CHOICE_SET` |
| `gameday_activity` | `RESOLVED` or `UNRESOLVED` |
| `unresolved_note` | written on every affected row when no official inactive list exists, rather than in a footnote |

**Three states, not two.** `determined` / `uncertain` is kept apart from
`EXCLUDED` / `IN_CHOICE_SET` on purpose, because they are different questions.
Collapsing `uncertain` into `determined` fabricates an authority nobody issued;
collapsing it into eligible reads absence of evidence as evidence. `ROSTER_ACT`
is worded in the module as *the absence of evidence against him, not evidence
that he will dress* — 53 are rostered and 48 may dress — so no caller can quote
it as availability.

**`official_inactive_ids=None` and `()` are different facts and the gate treats
them so.** `None` is *no list was available*; `()` is *a list was read and it
named nobody*. Tonight is `None`. Test:
`test_no_inactive_list_is_recorded_as_ignorance_not_as_nobody_out`.

**`DEV` is deliberately not a determination.** A practice-squad player can be
elevated on gameday, so calling him legally ineligible would be a false claim.
R5 removes him for a *denominator* reason (`roster_status.py` header: the fitted
C-sum was 1.24 and the unfiltered pool gave 2.25). The gate keeps that removal,
labels it `EXCLUDED_BY_POOL_RULE`, marks it `uncertain`, and reports it in its
own count — a declared exclusion, not a silent zero.

**Equal-rank disagreement is a refusal.** Two rank-2 statements that conflict
have no declared tiebreak, so `snapshot` returns
`ELIGIBILITY_AUTHORITY_CONFLICT` rather than letting dict order decide. Seeded
test: `test_equal_rank_disagreement_refuses`.

**A post-hoc status cannot govern.** `INA` is a gameday outcome.
`roster_status.status_map` already refuses a capture carrying it; the gate
refuses it a second time on the off chance a caller supplies statuses directly
(`ELIGIBILITY_POSTHOC_STATUS`, seeded test).

**A blank designation is not a clearance.** Settled already in
`STATUS_EVIDENCE_CONTRACT_EVALUATION.json`; the gate counts blanks
(`non_vocabulary_or_blank`) and never turns one into a status. Ten of the twelve
DEN/KC injury rows tonight are blank.

**An empty slice is an error.** `injury_designations` on a team with no rows
returns `ELIGIBILITY_INJURY_SLICE_EMPTY`, not `{}`.

---

## 2. Every DEN/KC player whose status I enforce tonight, and on what evidence

Two sources, both point-in-time selected through `vintage_selector`:

| Source | Blob | sha256 | Clock |
|---|---|---|---|
| Weekly roster (raw, `status` retained) | `nfl_vintage/raw/weekly_rosters.bdab6ecee12d44a4.csv` | `bdab6ece…f614f3` | observed `2026-09-14T16:16:25Z` (7.98 h pre-kickoff); **no publication clock exists for this family** |
| Official injury report | `nfl/vintage/injuries.66e960ec81fccc6e.csv.gz` | `66e960ec…f86865` | published `2026-09-13T12:41:50Z` (`DERIVED_DETERMINISTIC`, HTTP Last-Modified), 35.55 h pre-kickoff |

Clock guards both passed: the roster capture is strictly pre-kickoff for both
clubs and carries **no `INA` row**, so it is roster membership and not a gameday
partition (`ROSTER_STATUS_OK`, counts `ACT 106 / DEV 34 / RES 15 / CUT 23 /
EXE 2`).

### Over the full 180-player DEN/KC roster

| status | n | determination | effect |
|---|--:|---|---|
| `ROSTER_ACT` | 104 | uncertain | in choice set |
| `ROSTER_CUT` | 23 | **determined** | excluded |
| `ROSTER_RES` | 15 | **determined** | excluded |
| `ROSTER_EXE` | 2 | **determined** | excluded |
| `INJURY_OUT` | **2** | **determined** | excluded |
| `ROSTER_DEV` | 34 | uncertain | excluded by pool rule (named) |

**42 determined ineligible, 34 removed under the R5 pool rule, 104 unresolved
and in the choice set.**

### The two `Out` designations, which are the only rank-2 enforcement tonight

| gsis_id | name | team | pos | roster status | injury | known from | h before kickoff |
|---|---|---|---|---|---|---|--:|
| `00-0038982` | Chamarri Conner | KC | DB (S) | **ACT** | `Out` (Knee, DNP) | 2026-09-13T12:41:50Z | 35.55 |
| `00-0040116` | Josh Simmons | KC | OL (T) | **ACT** | `Out` (Back, DNP) | 2026-09-13T12:41:50Z | 35.55 |

**Both are `ACT` on the roster.** The roster arm alone would have kept them; only
the injury arm removes them. That is the ATL gap reproduced on tonight's game
with tonight's data — and it is the reason the gate cannot be `active_pool` with
a new name.

**Neither plays a modelled position.** Both are excluded from the offensive skill
pool before eligibility is even consulted, so **tonight the injury arm binds on
nobody in the modelled choice set.** I am stating that plainly rather than
reporting the gate as having caught something it did not: on this slate the
enforcement that changes the board is the roster arm.

### Over the modelled skill pool (QB/RB/WR/TE/FB), which is what the engine sees

58 players in, **33 out the other side**: 14 determined ineligible removed, 11
removed by the DEV pool rule, 33 kept (DEN 17 ACT, KC 16 ACT).

The 14 determined ineligible, each with authority rank 3
(`WEEKLY_ROSTER_STATUS`), content hash `bdab6ece…f614f3`, known by no later than
`2026-09-14T16:16:25Z`:

| gsis_id | name | team | pos | status |
|---|---|---|---|---|
| `00-0037324` | Chris Oladokun | KC | QB | `ROSTER_RES` |
| `00-0038145` | Thomas Odukoya | KC | TE | `ROSTER_EXE` |
| `00-0038492` | Jason Brownlee | KC | WR | `ROSTER_CUT` |
| `00-0039702` | Mason Pline | KC | TE | `ROSTER_CUT` |
| `00-0040120` | Jimmy Holiday | KC | WR | `ROSTER_RES` |
| `00-0040240` | Caleb Lohner | DEN | TE | `ROSTER_RES` |
| `00-0040953` | Jeff Caldwell | KC | WR | `ROSTER_RES` |
| `00-0040955` | John Michael Gyllenborg | KC | TE | `ROSTER_RES` |
| `00-0040964` | EJ Smith | KC | RB | `ROSTER_RES` |
| `00-0040967` | Jacob De Jesus | KC | WR | `ROSTER_CUT` |
| `00-0041020` | Xavier Loyd | KC | WR | `ROSTER_CUT` |
| `00-0041294` | Joseph Manjack | DEN | WR | `ROSTER_CUT` |
| `00-0041299` | Cameron Ross | DEN | WR | `ROSTER_CUT` |
| `00-0041575` | Jeff Weimer | KC | WR | `ROSTER_CUT` |

The 11 `ROSTER_DEV` removals (Prentice, Bandy, Krull, VanSumeren, Schrader,
Armstrong, Carter, Evans, Ott, Katsis, Key) are reported **separately** and are
**not** described as ineligible.

---

## 3. The over-draws invariant, and what it measured

`eligibility_gate.assert_zero_opportunity_over_draws(layers, arrays, ids)` reads
the **stored draw matrices, cell by cell**. It takes the per-layer `row_ids` /
`row_axis: 'gsis_id'` block from the draw manifest and the matrices from the
`.npz`, and for each ineligible player returns one of:

- `ABSENT` — he holds no row index in any player-axis layer. Zero by
  construction, which is what a choice-set gate produces.
- `ZERO_ROW` — he holds a row and every cell of it is exactly zero. Passes the
  invariant; counted separately, because this is what allocate-then-zero
  produces and it still leaves the renormalisation behind.
- otherwise **FAIL**, naming player, layer, metric, non-zero draw count, max and
  mean.

It reads no config flag, no evidence key and no summary. It refuses rather than
passing when there is nothing to read: an empty ineligible set is
`BLOCKED[ZERO_OPPORTUNITY_NOTHING_TO_CHECK]`, and a manifest whose layers are
all team-axis is `FAIL[ZERO_OPPORTUNITY_NO_PLAYER_AXIS]`.

### Result on tonight's sealed board

Artifact: `nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1/player_draws.npz`
(22 matrices; `qb` 6×1000, `receiving` 13×1000, `rushing` 3×1000,
`team_volume` 2×1000).

```
ZERO_OPPORTUNITY_HOLDS
n_players_checked        14
n_player_layers           3
n_row_slots_scanned     308
n_absent_from_every_layer 14
n_present_but_all_zero    0
n_cells_read              0
```

**All 14 determined-ineligible players are ABSENT from every player-axis layer
of the sealed board. None has a row; none has a cell.**

`n_cells_read = 0` is reported as its own number and not buried inside a green.
It is the honest consequence of the players being absent, and it is exactly why
the next test exists.

### The checker bites — the load-bearing test

Told that Travis Kelce (`00-0030506`, who is in the sealed receiving draws) is
ineligible, the same function on the same artifact returns:

```
FAIL[ZERO_OPPORTUNITY_VIOLATED]   4 violations, 4,000 cells read
  receiving/receiving_td      309/1000 non-zero, max 3,   mean 0.375
  receiving/receiving_yards   974/1000 non-zero, max 208, mean 54.07
  receiving/receptions        974/1000 non-zero, max 16,  mean 4.735
  receiving/targets           …
```

### The defect reproduced, and the gate contrasted against it, end to end

A 12-player synthetic pool through the production chain
`layers.appearance → layers.participation → layers.targets_carries`
(TEST-ONLY fixture; the P4C residual pools here are synthetic and labelled so —
this proves ordering and wiring, not a fitted allocation), m = 128 draws:

| | rows | ineligible player's row | team-mates' summed share |
|---|--:|---|--:|
| no gate at all | 12 | 115/128 draws non-zero, mean share 0.1375 | 91.05 |
| allocate-then-zero (`inactives.apply_to_appearance`, which is what `layers.py:236` calls) | **12** | all-zero | **108.65** |
| **Stage-0 gate** | **11** | **no row exists** | n/a — he was never in the denominator |

**The pool is identical before and after the inactive list is applied (12 rows
either way), and 17.60 units of share move onto his team-mates.** That reproduces
D7's `n_pre_only_rows = 0` / `n_post_only_rows = 0` on demand, and it is the
renormalisation the gate removes rather than corrects.

Running the *same* checker on the ungated draws of that chain returns
`FAIL[ZERO_OPPORTUNITY_VIOLATED]`, and on the gated draws returns `PASS` with the
player marked `ABSENT`.

---

## 4. The ATL case, replayed through the gate

**Yes, the gate catches it.**

Replay conditions: `2026_01_ATL_PIT`, kickoff `2026-09-13T17:00:00Z`, cutoff
`2026-09-13T16:00:00Z`, pool built from the **pre-kickoff** roster capture
`weekly_rosters.cef497eaeddef07b.csv`. (The newer capture cannot be used: ATL and
PIT have played, and `roster_status` correctly refuses it with
`ROSTER_STATUS_POSTHOC_CONTAMINATION` because the vendor re-partitions `ACT`
after a game. The guard working is why the replay needs the older file.)

55 skill players in. `00-0036212` (ATL QB1, Tua Tagovailoa) resolves to:

```
status                     INJURY_OUT
determination              determined
authority                  OFFICIAL_INJURY_REPORT   (rank 2)
source_vintage             nfl/vintage/injuries.66e960ec81fccc6e.csv.gz
content_hash               66e960ec…f86865
known_from                 2026-09-13T12:41:50Z
simulation_eligibility     EXCLUDED_DETERMINISTIC
```

`choice_set` returns 30 of 55 (13 determined ineligible, 12 DEV) and **he is not
among them**. He therefore has no row in any allocation, no appearance draw, and
no dropback or passing-yard distribution to seal. The 19.7 dropbacks and 131.2
passing yards cannot be produced by a run that starts from this choice set.

### How long the statement had stood — `first_seen`

The point-in-time selector answers *what does the report say*; it does not answer
*how long have we known*. `eligibility_gate.first_seen` scans **every** lawful
injury vintage at or before the cut (7 of them here) and returns the earliest
that already carried the designation:

```
00-0036212  Tua Tagovailoa  ATL  Out
  first_vintage   nfl/vintage/injuries.0bc645a4b9aa6255.csv.gz
  content_hash    0bc645a4…501208
  known_from      2026-09-11T21:02:00Z
  authority       DELIVERED_EXPLICIT (provenance.publication_time)
  clock_basis     PUBLICATION
  hours before kickoff   43.97
  vintages carrying it   2
```

That is D7's 42.7-hours-before-the-seal figure, independently re-derived from the
bytes, measured to kickoff instead of to the seal. **The evidence existed, in this
repository, with a publication clock, in two separate captures, and did not reach
the simulation.**

### A defect this turned up in `vintage_selector`, which I do not own

`FAMILIES['injuries']['publication_clock']` is `effective_scope.valid_from`. A
**delivered** capture has no `effective_scope.valid_from`; it carries the
league's stated publication instant at `provenance.publication_time`. Measured on
`injuries.0bc645a4b9aa6255`: `published_authority = 'DELIVERED_EXPLICIT'`,
`published_at = None`, `provenance.publication_time = '2026-09-11T21:02:00Z'`.
So the selector **labels the row as having an explicit delivered clock and then
returns `None` for it** — the strongest publication clock in the tree is the one
it drops.

`first_seen` reads it directly for the gate's own use
(`_delivered_publication_time`, and it says in the docstring that it is not
patching the selector). The selector fix is section 8, item 2.

---

## 5. What I left as uncertainty rather than resolving

1. **Gameday activity for every DEN/KC player.** No official inactive list exists
   for this game — the `official_inactives` family covers **13 distinct games** in
   the manifest and `2026_01_DEN_KC` is not one of them, matching your escalation
   result. Every row therefore carries `gameday_activity: UNRESOLVED`, the
   snapshot carries `official_inactive_list: NOT_AVAILABLE`, and
   `board_finality` reads `PRELIMINARY_PROVISIONAL — no official gameday
   inactive list; final eligibility is NOT inferred and no player is assumed to
   dress`. **104 roster players are `ACT` and 48 may dress. The gate does not
   guess which 48.**

2. **The 33 skill players in the choice set.** All are `ROSTER_ACT`, which the
   module words as absence of evidence against them. None is asserted available.

3. **`ROSTER_DEV` (34 league-wide on these two clubs, 11 in the skill pool).**
   Left `uncertain`. They are removed by the R5 denominator rule, which is named
   in the artifact as a different rule with a different reason. I did **not**
   upgrade that removal into an eligibility determination, and I did not remove
   the removal either — changing R5's pool would change tonight's board and is
   not my call to make unilaterally.

4. **Scenario weights.** `scenarios()` builds discrete eligibility worlds —
   `{label, excluded, weight}`, a set of excluded ids per world, never a
   multiplier on a projection. Tonight it returns **one world** with
   `weights_estimated: False`. There are zero `Questionable` or `Doubtful`
   designations on DEN or KC in the lawful report, and no evidence-based way to
   weight the unresolved 33, so inventing a weight would put a fabricated number
   into an artifact where it would be indistinguishable from a measured one. The
   machinery is tested and works (two weighted players → four worlds summing to
   1.0, with the independence assumption declared in the evidence); it is simply
   not fed.

5. **Suspensions.** `SUSPENDED` exists in the vocabulary at rank 2 and the
   snapshot accepts a `suspensions=` mapping. **No parseable suspension source
   exists in this checkout** — `official_transactions` has 179 manifest rows, of
   which **0 carry a sha256, 0 carry a game_id, and 0 blobs exist on disk**; it
   is a declared cadence with no retained content. I did not stub it, did not mock
   it into a passing test, and did not infer absence of suspension from absence
   of a source. Tonight `suspensions` is empty because nothing was supplied, and
   that is recorded rather than described as "nobody is suspended".

6. **No publication clock for the roster family.** `known_from` is genuinely
   `null` for every roster-derived status; `known_by_no_later_than` carries the
   observation clock instead, in its own field. I did not write a retrieval time
   into a publication field.

---

## 6. Corrections to two claims in the brief

Both are small, both are measurable, and I would rather they be right in the
ledger.

**(a) "`appearance_r8.predict` has no eligibility input at all" — not exactly.**
`appearance_r8.predict(season, week, players, injuries_rows, …)` does take the
injury rows (`appearance_r8.py:358`), parses them
(`appearance_r8.py:403`, `appearance_model.parse_injuries_rows`), and sets
`inj_status` / `inj_practice` / `inj_available` on each row
(`appearance_r8.py:466-468`). `Out` reaches the model as a **one-hot feature with
a fitted coefficient** (`appearance_r7.featurise`, `appearance_r7.py:346-350`,
which R8 calls first). So it is not that the designation is absent — it is that
it enters as a **soft learned feature and never as a determination**, which is
why a player listed `Out` can come back at `p_app = 0.624`. The substance of your
point stands and is arguably sharper this way: the model is being asked to *infer*
from a designation that is not a prediction problem at all.

**(b) The shape-only fixture branch of `layers.appearance` ignores
`inactive_ids`.** `layers.py:165-178` returns from the `p_appear` path without
ever reaching `_run_real`, where the inactives are applied. Measured: passing
`inactive_ids=[pid]` on that branch leaves his draws untouched (max |share|
0.3829 rather than 0). That branch is TEST-ONLY and cannot reach an artifact, so
it is **not a production defect** — but a test written against it would prove
nothing, and mine therefore calls `inactives.apply_to_appearance` directly, which
is the same function `layers.py:236` calls.

---

## 7. One observation outside my scope, for whoever owns it

The sealed board's non-QB layers are **entirely KC**: all 13 `receiving` row_ids
and all 3 `rushing` row_ids are KC players; **DEN has zero receivers and zero
rushers** in the draw artifact, while carrying 17 `ACT` skill players. The `qb`
layer carries 3 and 3. D7 already points at `DEN_KC_LIVE_RUN_RECORD.json` for a
KC pathology. This is not an eligibility effect — DEN's absent players are `ACT`
and `IN_CHOICE_SET` in the snapshot — so it is not mine to fix and I have changed
nothing. Flagging it because a board with one team's receivers missing will not be
improved by getting eligibility right.

---

## 8. Patches for call sites I do not own

Neither is applied. `run_forecast.py` is already modified in this working tree by
another agent, so applying anything to it from here would collide.

### Patch 1 — `nfl/production/run_forecast.py`, the non-QB pool block (currently lines 840-864)

Replace the `roster_status`-only filter with the Stage-0 gate, keeping the
existing `_r5` evidence keys so nothing downstream that reads them breaks.

```python
        if fl.get('active_roster_only'):
            from nfl.production import eligibility_gate as EG
            snap = EG.snapshot(
                args.season, args.week, teams, players,
                kickoff_utc=fx.get('kickoff_utc'),
                observed_before=args.written_at,
                game_id=args.game_id,
                # None means NO LIST WAS AVAILABLE. () would mean a list was
                # read and named nobody. They are different facts.
                official_inactive_ids=fx.get('official_inactive_ids'))
            if snap.state is not State.PASS:
                fx['_nonqb'] = {'fatal': snap}
                return fx['_nonqb']
            cs = EG.choice_set(players, snap)
            if cs.state is not State.PASS:
                fx['_nonqb'] = {'fatal': cs}
                return fx['_nonqb']
            players = list(cs.value)
            fx['_eligibility'] = {k: v for k, v in snap.evidence.items()
                                  if k != 'value'}
            fx['_eligibility_choice_set'] = {
                k: v for k, v in cs.evidence.items() if k != 'value'}
            fx['_r5'] = {k: v for k, v in cs.evidence.items() if k != 'value'}
            fx['_r5']['roster_status_source'] = \
                snap.evidence['roster_vintage']['source']
            fx['_r5']['roster_status_observed_at'] = \
                snap.evidence['roster_vintage']['observed_at']
            fx['_r5_applied'] = True
            fx['_eligibility_gate_applied'] = True
```

Three notes on it. First, this filters **QBs too** — the current block splits
`qbs + pool.value` and leaves the QB list to the separate block at line 439, and
that block runs `active_pool`, which is roster-status only and would have kept
Tua. Whether the two blocks should merge is your call and R1's, not mine; if they
stay separate, the QB block needs the same substitution
(`EG.snapshot` + `EG.choice_set` over `qbp`), keeping its existing
`QB_POOL_EMPTIED_BY_ELIGIBILITY` refusal, which the gate does not replace.
Second, `test_r5_active_pool` locates the non-QB branch by searching the source
for the literal spelling of the flag read — the comment at line 430 says so —
so that test needs re-pointing in the same change. Third, once this lands,
`layers.appearance(..., inactive_ids=...)` becomes belt-and-braces rather than
the mechanism; I would keep it, because `ZERO_ROW` still passes the invariant.

### Patch 2 — `nfl/production/nonqb/vintage_selector.py`, `FAMILIES['injuries']`

A delivered capture's publication clock is dropped. Suggested shape: let
`publication_clock` be a tuple of candidate paths tried in order —
`('effective_scope.valid_from', 'provenance.publication_time')` — and carry the
authority from whichever hit. The family already labels such rows
`DELIVERED_EXPLICIT`, so the label and the value are currently inconsistent.
This is a read-path change with no effect on any stored byte.

---

## 9. What is still open

- The gate is written, tested and produces tonight's snapshot, but **nothing in
  the production path calls it yet** — patch 1 is unapplied by design. Until it
  lands, tonight's board is governed by `active_pool` alone.
- Suspension input: no source. `docs/AGENT_OUTBOX.md` is the right place if you
  want one requested; I have not written the request because it is not blocking
  tonight and the entry should name the endpoint you can actually reach.
- `n_cells_read = 0` on the sealed board is correct and honest, but it means the
  real-artifact arm of the invariant is currently proved by absence. The seeded
  violation and the end-to-end synthetic chain are what give it teeth. When a
  board is next sealed with an official inactive list present, the `ZERO_ROW`
  arm becomes exercisable on real data too.
