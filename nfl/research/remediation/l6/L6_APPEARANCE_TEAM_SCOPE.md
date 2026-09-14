# L6 — the appearance refusal is scoped to the team it is about

**Verdict: the repair holds.** Tonight's board for `2026_01_DEN_KC` goes from
**6 rows, all quarterbacks** to **19 rows — the same 6 quarterbacks plus 13
Kansas City skill players** (6 WR, 4 TE, 3 RB). Denver's
`INJURY_REPORT_INCOMPLETE` still fires, with the same code and the same reason,
and not one Denver skill player reaches a modelled quantity.

`nfl/production/nonqb/layers.py` is **UNTOUCHED**: sha256
`481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`, matching
Q9's frozen candidate identity `481f005f682cd721`. No change to
`run_forecast.py` was needed and none was made — **no patch is owed to you.**

| | |
|---|---|
| Files changed | `nfl/production/nonqb/football_engine.py` (+155 / -16) |
| File added | `nfl/tests/test_appearance_team_scope.py` |
| Suite | `run_suite.py --only test_appearance_team_scope` → **SUITE PASS**, 11 functions, 51 checks, 0 failing, 0 zero-check |
| Base | HEAD `9c3c29a`, python3.12 |

---

## 1. What was changed, and where

Nothing in the frozen module. At the `_lay('appearance', ap)` call site in
`football_engine.run_game`:

1. **Readiness is resolved first**, per team, from `RD.team_readiness` — the
   same function `layers.appearance` calls, with the same arguments.
2. If **some but not all** teams are READY, `ateams` becomes the READY subset,
   the receiver frame is built over `ateams`, and `layers.appearance` is handed
   `teams=ateams` together with only those teams' players.
3. Every downstream expression that describes the **non-QB allocation frame**
   reads `ateams`: the receiver and carry group layouts, the `_empty` check,
   the C3 throw-budget stack, the target- and carry-volume stacks, the A1
   budget checks, and the quarterback-rush vector that `reconcile_rushing`
   stacks against `rb_starts`/`rb_counts`.
4. Everything that is a **statement about the game** keeps both clubs:
   `g['teams']`, the team-volume forecast, the QB record contract,
   `reconcile_allocation_share`, `reconcile_team_volume` (which is where the
   both-club "do the QBs' rushes fit inside this club's carries" question is
   still asked in full), `reconcile_cross_layer`, and the payload's
   `team_draws`.

### Why this is allowed to be narrowed

This is WS15's **EVIDENCE-GAP** class: "I do not know whether Denver's players
are available" is a statement about Denver. A **CONSTRUCTION-INVARIANT**
refusal — a partition exceeding the thing it partitions, a count identity that
does not close, a player allocated opportunity with no appearance vector — is a
statement about the whole construction and is never narrowed. None of those was
touched. C3's exact count-closure identity ran and held on the narrowed frame
(the run would have halted at `shared_pass` otherwise); `reconcile_nonqb`,
`reconcile_rushing`, `reconcile_chain` and the publication gate all ran.

### Two branches that deliberately do nothing

* **Every team READY** → `ateams = tuple(teams)`, and every rewritten line is
  the line that was there before. This is the bit-identity case, proved below.
* **No team READY** → there is no unit left with evidence, so the whole-game
  deferral is correct and `layers.appearance` is left to produce it in its own
  words. Verified live on `2026_01_NE_SEA` (NE 3 rows, SEA 8 rows, neither
  designated, `written_at` 2026-09-09T20:00Z): `DEFERRED[INJURY_REPORT_INCOMPLETE]`,
  `halted_at: appearance`, no payload, `owed.teams` still naming both clubs and
  still carrying "a team with no filed report is NOT a team with no injuries".
  No scope record is written. That is `test_j`.

### One thing worth naming

`RD.team_readiness` appends to a **context-var gate-cut handoff** that
`readiness.latest_injuries_rows` may later consume. Probing readiness at the
call site would have appended a second, identical entry per team and moved
`n_gate_evaluations` in the feed's own evidence on a run that is otherwise
unchanged. The probe therefore saves and restores that handoff. The cuts are
identical either way — same kickoff, same `written_at`, same teams — so nothing
is lost, and it is what makes the byte-level proof below come out clean.

---

## 2. The both-teams-READY bit-identity proof

**Game:** `2026_01_DAL_NYG`, `written_at` 2026-09-13T20:00:00Z. DAL READY
(4 injury rows), NYG READY (6 rows), against the captured
`injuries.66e960ec81fccc6e` feed. A committed, already-played game.

**Method — the strong version, run once out of suite.** A pristine copy of
`football_engine.py` as it stood before the repair (sha256
`29cd070e1916a595772e1eb7d504d03812cb1c35dd2f6cf80a0c293b1564ee2d`) was loaded
as a second module. The **real production pipeline** (`make_board.build_one`,
`V1_CANDIDATE_R8`, 400 draws) was run for that game with a spy on
`FE.run_game`, capturing the exact argument tuple the pipeline builds —
`players`, `fits`, the coupled `tv`, the `qb` object, A1's rushing budget, the
SC1-permuted carry override, `shared_pass='c3'`, `game_coupling`,
`inactive_ids`. Both engines were then run on independent deep copies of that
one argument set, and every output canonicalised: each ndarray as
`(shape, dtype, sha256(bytes))`, each `Outcome` as state + code + detail +
evidence + value, the whole thing sorted-key JSON.

```
baseline digest 554697f41e9e80bbc2bdd118fd271bafb3db1cb400790347abecf3c744290803
patched  digest 554697f41e9e80bbc2bdd118fd271bafb3db1cb400790347abecf3c744290803
IDENTICAL
```

Every draw matrix matched byte for byte:

| matrix | shape | sha256 (both) |
|---|---|---|
| targets | 30 x 400 | `5e079aa69d841c3c…` |
| receptions | 30 x 400 | `ade81826d0d9fc11…` |
| receiving_yards | 30 x 400 | `8fa19d97eac7ea7c…` |
| receiving_td | 30 x 400 | `586862adc793e18c…` |
| carries | 9 x 400 | `c1f659609d348a64…` |
| rush_td | 9 x 400 | `32f96dc1bf3521b9…` |

…as did every layer verdict, every accounting block, every player record and
the whole `index` and `allocation` payload.

**Honest note on one iteration.** My first version also added an additive
`index['game_teams']` key to the payload. It changed no number, but it made the
diff non-empty, so I removed it: `g['teams']` and `g['appearance_team_scope']`
already carry that information, and an exactly-identical payload is worth more
than a convenience key.

**The in-suite version.** The byte replay needs a copy of the pre-repair file,
which the tree does not carry, so `test_i` runs it only when
`L6_BASELINE_ENGINE` points at one (and records a `blocked()` check, not a
pass, when it does not). What runs unconditionally is the pair that makes the
byte result follow:

* `test_d` — **structural**: `ateams` is assigned exactly twice, the
  initialiser is `tuple(teams)`, and the only reassignment is inside
  `if _ready and _notready:` which is itself inside `if injuries_rows is None:`.
  Readiness is probed exactly once and only on the real path. So all-READY ⇒
  `ateams == tuple(teams)` ⇒ every downstream expression is textually the old
  one.
* `test_c` — **behavioural** on the real both-READY game: no scope record, no
  `team_scope` evidence, no `APPEARANCE_TEAM_DEFERRED` warning, allocation
  frame `['DAL', 'NYG']`, and all 49 modelled-position players present.

With `L6_BASELINE_ENGINE` set, `test_i` also passes (51 checks, 0 blocked).

---

## 3. How Denver's deferral is recorded on tonight's board

Sealed run `0a578f7740fc5118`, `written_at` 2026-09-14T16:30:00Z,
`V1_CANDIDATE_R8`, 400 draws, draw digest `6f3d50f170400ff5…`.

**In `board.json` / `BOARD.md`, under `layer_governance`, stage `appearance`,
state `PASS[APPEARANCE_OK]`, as a named warning carried verbatim through
`run_forecast._governance_facts`:**

> `appearance: APPEARANCE_TEAM_DEFERRED: DEN is INJURY_REPORT_INCOMPLETE and is
> deferred -- 14 player(s) carry no appearance estimate and no projection. The
> appearance layer ran on KC only. a team with no filed report is NOT a team
> with no injuries. No appearance probability, no allocation and no projection
> is emitted for any player of a deferred team.`

It is rendered in `BOARD.md` §"Layer governance" (line 347) and beside it, in
the freshness block (line 27), the status table still reads:

> `DEN | INJURY_REPORT_INCOMPLETE — DEN has 1 row(s) but report_status is
> unfilled on every one. teammate_availability reads it…`

**Structured, on the engine result** (`g['appearance_team_scope']`, mirrored at
`g['deferred_teams']`): `code: APPEARANCE_TEAM_DEFERRED`, `ready_teams: ['KC']`,
both clubs' states, and for Denver its `state`, its `reason` **verbatim from
`readiness.team_readiness`**, `n_injury_rows: 1`, `n_players_excluded`, and
**every excluded player listed by `gsis_id`**. `test_e` asserts the state and
reason are character-identical to what `RD.team_readiness` returns live, so the
record cannot drift into a softer wording.

**Not** as a new `g['layers']` key — that would raise
`ENGINE_LAYER_NOT_REPORTED` in `run_forecast._assert_every_layer_is_reported`,
which is that guard working. `test_f` asserts the scoped run declares no layer
the unscoped run does not.

The board's `completeness` is `PARTIAL_PLAYER_COVERAGE`, which is the honest
state: half the game is modelled.

---

## 4. Tonight's board, before and after

Both runs are the real pipeline on the same clock, same mode, same seed, 400
draws; the only difference is which `run_game` executed.

| | pre-repair (`0e656aeb1afc2add`) | repaired (`0a578f7740fc5118`) |
|---|---|---|
| board rows | **6** — 3 DEN QB, 3 KC QB | **19** — the same 6 QB + 6 KC WR, 4 KC TE, 3 KC RB |
| sealed draw rows | qb 6, team_volume 2 | qb 6, **receiving 13**, **rushing 3**, team_volume 2 |
| appearance stage | `NOT_APPLICABLE[INJURY_REPORT_INCOMPLETE]` | `PASS[APPEARANCE_OK]` + the scoped warning |
| participation / targets_carries / conversion / td_layer | all `NOT_APPLICABLE[BLOCKED_UPSTREAM_APPEARANCE]` | all PASS |
| C3 | `NOT_REACHED` | applied |
| DEN skill players modelled | 0 | **0** |
| KC skill players modelled | 0 | **13** |

Every receiving row and every rushing row in the sealed manifest is a Kansas
City player — checked by `gsis_id` against the roster vintage, never
positionally.

**13 is the number under `V1_CANDIDATE_R8`** (`active_roster_only`), and it
matches L3's audit exactly: L3 measured 13 KC non-QBs and 14 DEN non-QBs in the
R8 allocation pool, and 14 is precisely the count in the deferral record. Run
without the R5/R8 roster-status filters the same repair carries 28 KC players.

### The QB consequence, which is real and which you should see

Comparing the two sealed `player_draws.npz` row by row (rows addressed by
`manifest['layers']['qb']['row_ids']`, `row_axis: gsis_id`):

* **All three Denver quarterbacks: every field bit-identical** — `att`, `db`,
  `cmp`, `pyds`, `ptd`, `int`, `rush_opp`, `ryds`. Denver is untouched.
* **All three Kansas City quarterbacks:** `att`, `db`, `int`, `rush_opp`,
  `ryds` identical; **`cmp`, `pyds` and `ptd` differ.** Those are exactly the
  three fields C3 credits from the receiving event, and C3 could not run before
  because there were no receivers. Mahomes' mean completions 12.63 → 12.68,
  passing yards 139.82 → 136.05, passing TD 0.99 → 0.92.

**Say this out loud when the board is read:** in this one artifact Kansas
City's passing line is *credited from its own receiving event* while Denver's
is *drawn independently by QB V1*. Two mechanisms for the same quantity in one
game. That is a direct and unavoidable consequence of modelling one club and
not the other, it is visible in `candidate_components` (C3 applied) but it is
not currently flagged per club, and it is not something I fixed.

---

## 5. The mixed-case RNG statement, stated plainly

`layers._game_stream` gives the game **one** appearance stream, consumed
sequentially across the player dict:

```
parts, sep = _game_stream([seed, season*100 + week, 11], game_id)
rng = np.random.default_rng(parts)
draws = {pid: rng.binomial(1, ..., size=m) for pid, pv in o.value.items()}
```

With only Kansas City's players in that dict, the stream is consumed over a
different player set than a both-teams run would consume it over. So:

> **The property "Kansas City's draws are the same whether or not Denver was
> ready" is FALSE by construction.** This repair is *not* draw-preserving in
> the mixed case and I am not claiming it is.

What is true, and is the whole defence: **there is no both-teams run tonight to
perturb.** The pre-repair code produces nothing at all for this game — 0
receiving rows, 0 rushing rows, appearance `NOT_APPLICABLE`. The comparison is
against an empty set, not against a different set of numbers.

The claim I *do* make is the one proved in §2: **when every team is READY,
behaviour is bit-identical.** That is the property that separates "scoped the
refusal" from "weakened the guard", and it is the only identity claim in this
report.

`test_h` asserts the artifact itself carries this statement (`rng_note` on the
scope record), so a later edit cannot quietly start implying draw preservation.

---

## 6. What I did not do

* **Did not touch `layers.py`.** Hash verified unchanged at the end of the
  work: `481f005f682cd721…`. `test_a` asserts it, and also asserts the file
  contains neither `ateams` nor `team_scope`.
* **Did not weaken the readiness contract.** `test_b` calls
  `LY.appearance(..., teams=('DEN','KC'))` on the real feed and asserts it
  still returns `DEFERRED[INJURY_REPORT_INCOMPLETE]`.
* **Did not touch** `readiness.py`, `depth_vintage.py`, `roster_status.py`,
  `vintage_selector.py`, `run_forecast.py`, `nfl/capture/**`, `appearance_*.py`,
  `pool_audit.py`, `authorization.py`, `determinism_proof.py`.
* **Did not attempt** the "refuse only when `report_status` AND
  `practice_status` are both blank" repair. I read
  `nfl/research/slate_audit/EVIDENCE_CEILING_injury_report_publication.md`
  before forming a view and I agree with the withdrawal: both-blank is 0 in
  all seven captures (48/11/29/182/139/11/167 rows), so the condition can
  never fire and the change deletes the guard silently. See §8 — this repair
  is the complement to that one, not a retry of it.
* **Did not fetch anything.** No network, no sportsbook data.
* **Did not `git add`, `commit`, `stash` or `push`.**

## 7. Notes for integration

* Regression suites run individually, all **SUITE PASS**:
  `test_football_engine_r4` (142 checks), `test_nonqb_r3` (129),
  `test_r7_appearance_frame` (67), `test_inactives_propagation` (43),
  `test_accounting_invariants` (41), `test_draw_coherence` (135),
  `test_production_pipeline` (69), `test_forecast_completeness` (30),
  `test_slate_runner` (44), plus `test_appearance_team_scope` (51).
* My proof runs sealed into `/tmp` out-dirs only. The two rows added to
  `nfl/prospective/q9shadow/Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl` in the working
  tree are for `2024_01_ARI_BUF` and are **not** mine.
* `nfl/tests/test_appearance_team_scope.py` runs three real `run_game` calls
  on captured inputs at `m=64` with `qb=None`; it writes nothing and takes
  about a minute.

**Artifact digests at hand-off**

| file | sha256 |
|---|---|
| `nfl/production/nonqb/football_engine.py` | `bda30672df02a4564a63e951cf1dce5ad6772f68ad3b8d71dbcf35e5559eff6d` |
| `nfl/tests/test_appearance_team_scope.py` | `090bc63cb6833b568c3a3974f1eb672a086334b6bad9a88ba7ab406bcc801ffc` |
| `nfl/production/nonqb/layers.py` (unchanged) | `481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108` |


---

## 8. Relationship to the withdrawn evidence-ceiling branch

`EVIDENCE_CEILING_injury_report_publication.md` closes by naming three
instances of one blast-radius defect class. Two were repaired as **pure
scoping**, needing no new evidence:

* `NONQB_PLAYER_FRAME_INCOMPLETE` — one player of 190 without a position cost
  NYJ@TEN its board; now excluded **by name**.
* `ALLOCATION_PLAYER_WITHOUT_APPEARANCE` — one player without an appearance
  draw cost CHI@CAR and CLE@JAX theirs; now excluded **by name**, refusing only
  when a team is left with nobody.

The third — `INJURY_REPORT_INCOMPLETE` — was recorded as waiting on the
ceiling, because the branch that was tried tried to make the *refusal itself*
go away, and that needs a publication clock the feed does not carry.

**This repair does not lift that ceiling and does not try to.** Denver is still
refused, for exactly the reason the document gives: from these bytes, "the
final report is out and nobody is designated" and "the report is not out yet"
are the same four columns. What it does is apply the *same pure-scoping move as
the other two*, one level up — from **player-scoped** to **team-scoped**. The
two halves of the game were always separable and the layer's own `owed` block
already carried both states.

So the practical position changes: of the games the document lists as waiting,
the **READY** club's board is recoverable today on evidence already in hand,
and only the unfiled club's players still wait. The ceiling still governs what
it always governed — whether we can say anything at all about a club with no
filed designation — and the answer is still no.

The three lifts named in that document (a publication clock; `official_injury_report`
captured as its own source; a long enough series to derive rather than pick a
slate-level cut) remain the things that would let Denver's fourteen onto a
board. That request is L1's and the outbox's, not mine.
