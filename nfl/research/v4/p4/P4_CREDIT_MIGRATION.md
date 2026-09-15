# P4 / repair 5 — migrating every board to the replacement passing-credit function

**Scope.** Rebuild the per-quarterback passing line on every sealed board built
by `shared_pass.credit_to_passers`, through the replacement that already exists
in the tree, `football_engine.credit_passing_line`. Preserve every sealed byte.

**Frozen file verified unchanged at start and at end.**
`nfl/production/nonqb/layers.py` =
`481f005f682cd72129e6bf02e55cba86913ddffd7d88367743c616e3e11c0108`.

**`board_pointer.verify_seal('V1_SEALED')` at start and at end: `PASS
SEAL_INTACT`.**

---

## 1. What I confirmed before acting

The brief's reading is correct, and I checked it rather than accepting it.

* `shared_pass.py:172 credit_to_passers` splits completions and passing
  touchdowns multinomially on `w = att_q / sum(att)` and yardage as
  `pyds_q = w * team_pyds` (line 189), independent of the completion draw. A
  multinomial samples a finite pool **with** replacement.
* `football_engine.py:84 credit_passing_line` deals completions by
  multivariate hypergeometric over `attempts - interceptions`, touchdowns over
  the credited completions, and yards on the **completion** share, and asserts
  `cmp <= att`, `cmp <= att - int`, `ptd <= cmp`, `cmp == 0 -> pyds == 0` at
  lines 285–300.
* **Production already calls the replacement** (`football_engine.py:1531`).
  Nothing in the production path still calls the old credit. So this is a
  migration of *artifacts*, not a code repair — which is what the brief said,
  and it is the reason no new credit scheme was written.

**The board families are a switch, not a gradient — reproduced exactly.** Family
is assigned by content, not by label or commit date: the two schemes put yardage
on different shares and both are deterministic given the stored inputs, so the
stored `qb/pyds` reproduces one of them to the bit. Measured over 121 boards:
`d_old == 0.0` exactly on **100** team-sides, `d_new == 0.0` exactly on **4**,
138 sides carry no receiving layer so the credit never ran on them, and **no
side is ambiguous** — nothing classified UNDETERMINED.

---

## 2. The failing test, written first

`nfl/tests/test_passer_credit_migration.py`, run before any migration existed.
Full output preserved at `nfl/research/v4/p4/BEFORE_test_passer_credit_migration.txt`.

```
python3.12 nfl/tests/run_suite.py --only test_passer_credit_migration
  modules 1  test functions 9  checks 27  FAILING CHECKS 6
  FAIL a migration has actually been recorded
  FAIL   UNCHANGED: ZERO impossible passing-line cells  36587 cell(s) across 50 board(s)
  ...
```

The per-row box-score assertion over every scanned board, on the sealed corpus
as built — 121 boards, 990,000 QB cells, 516,000 rushing cells:

| identity | violating cells |
|---|---|
| `cmp <= att` | 8,214 |
| `cmp + int <= att` | 9,189 |
| `ptd <= cmp` | 1,113 |
| `ptd <= att` | 30 |
| `cmp == 0 -> pyds == 0` | 18,041 |
| `rushing_td <= carries` | 442 |

All six reproduce the X1 census exactly. The test names every offending board
and its per-check counts; the worst are
`2026_01_DAL_NYG/pre_inactives_V1_CANDIDATE_R8/3dddf9f62c9260b0` (3,340
passing-line cells) and
`2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec` (1,830).

**Corpus discovery is `sealed_index.live_draw_files()`.** This module owns no
glob. Running it with `exclude=()` reaches all 121 boards including the twelve
`REPLAY_C1/*`; the fence corpus proper is the 109 outside that declared
namespace.

### A correction to the census headline

**"27,564 genuinely impossible per-QB cells" does not reproduce, and no
aggregation of the measured numbers produces it.** The six component counts
quoted beside it all reproduce exactly, so the components are right and the
total is not. For the record:

| aggregation | value |
|---|---|
| sum of all six quoted checks | 37,029 |
| sum of the five per-QB passing checks | **36,587** |
| distinct QB cells violating any of the five | 27,332 |
| that plus the 442 rushing cells | 27,774 |
| every 4-subset sum of the six | none equals 27,564 |

I use **36,587** as the pre-migration figure, because that is the quantity the
acceptance bar is about: cells that violate a passing-line identity.

---

## 3. What was migrated, and how

`nfl/tools/passer_credit_migration.py`. It rebuilds **one step** — the
per-quarterback passing line — from each sealed board's own stored inputs, and
copies every other matrix through unchanged.

* **Inputs.** `qb/att` and `qb/int` are the original QB V1 draws; the credit
  only ever wrote back `cmp`, `pyds` and `ptd`. The team totals are derived
  from the **receiving** layer of the same side (`receptions`,
  `receiving_yards`, `receiving_td` summed), which is the side that owns the
  event under C3, and are then asserted equal to the stored per-quarterback
  sums in every draw — an independent second derivation of the same quantity.
  No board failed that cross-check.
* **Randomness, declared.** `seed = int(sha256(f'{SPEC_VERSION}|{run_id}|{team}')[:16], 16)`,
  one stream per (source run, team side), so the result does not depend on team
  iteration order, the clock, or batch size. The original engine stream is
  **not** recoverable — the credit rng is seeded once per game and its *state*
  at the credit call depends on the whole preceding run — and a re-created one
  would be a guess wearing provenance. Determinism is asserted by the test:
  the same board migrated twice gives identical arrays and the same run id.
* **Not re-run end to end.** A full re-run would need the pre-kickoff feeds,
  injury state and roster vintage, and would not reproduce the sealed draws
  even if they were present. Rebuilding the credit step on the sealed inputs is
  the only rebuild that isolates the treatment.
* **Not a board.** `board.json` and `BOARD.md` are deliberately not
  regenerated: their means, percentiles, thresholds and confidence scores are a
  rendering produced by code this workstream does not own. Each migrated
  artifact says so in its `MIGRATION.json` and names what is owed (run the
  existing renderer over these draws).
* **Where it went, and why not under `live/`.** Migrated artifacts are at
  `nfl/research/v4/p4/migrated/<game>/<label>/<new_run_id>/`. `live/` is the
  **prospective** namespace — everything in it was sealed before a kickoff and
  `live_draw_files()` is what the prospective ledger reads. A post-hoc rebuild
  filed there would be counted as a prospective forecast. That is the exact
  contamination class this repository has already paid for, so they are kept
  out and each one records that it is inadmissible as prospective evidence.
  Nothing under `live/` changed, so `test_sealed_corpus_census` still passes
  unchanged.

### Spot check against the census's own example

`797eed72f07fbd9b`, ARI `00-0033119`, draw 57 — the cell X1 quotes:

| | att | db | int | cmp | ptd | pyds |
|---|---|---|---|---|---|---|
| sealed | 4 | 4 | 0 | **7** | 0 | 36.36 |
| migrated | 4 | 4 | 0 | **4** | 0 | 50.0 |

### The allocation still closes exactly

Total completions across all 42 migrated boards: **1,809,472 before, 1,809,472
after.** The C3 identity re-checked on the migrated artifacts over 84 C3-bound
team-sides: worst absolute difference `cmp` 0.0, `ptd` 0.0, `pyds` 1.1e-13.

Mean absolute per-quarterback completion shift, over the 84 migrated sides:
mean 0.350, min 0.117, max 0.807 completions. The team mean is unchanged
because the allocation closes.

---

## 4. Per-family before and after

121 boards, 990,000 QB cells. "Impossible" = the five passing-line identities.

| family | status | boards | QB cells | impossible before | impossible after |
|---|---|---|---|---|---|
| `C3_OLD_CREDIT` | **MIGRATED** | 42 | 314,000 | 27,046 | **0** |
| `C3_OLD_CREDIT` | **UNMIGRATABLE** | 8 | 144,000 | 9,541 | 9,541 |
| `C3_NEW_CREDIT` | not applicable | 3 | 18,000 | 0 | 0 |
| `QB_ONLY` | not applicable | 68 | 514,000 | 0 | 0 |
| **total** | | **121** | **990,000** | **36,587** | **9,541** |

The 42 migrated split 30 under game namespaces and 12 under `REPLAY_C1`.

**Acceptance bar, part one: met on every board that could be migrated.** Zero
impossible passing-line cells on all 42 rebuilt boards and on all 71 boards
that never needed rebuilding — 113 boards, 846,000 QB cells, zero. The
remaining 9,541 cells sit entirely on the 8 boards named in section 5, which
are declared rather than dropped.

`rushing_td <= carries` is unchanged at 442 and is discussed in section 7. The
passing credit does not touch the rushing layer.

---

## 5. The eight boards that could not be migrated

Not fabricated, not half-written, not clipped. `credit_passing_line` refuses by
name, and the migration refuses the whole board rather than writing one side
rebuilt and one side not.

Code: **`PASSER_CREDIT_EXCEEDS_COMPLETABLE_ATTEMPTS`** on all eight.

| board | side | bad draws | worst draw: completions vs completable attempts |
|---|---|---|---|
| `2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/4b186a21b83a49ec` | DAL | 1 | draw 1184: 19 vs 18 (21 att − 3 int) |
| `2026_01_DAL_NYG/pre_inactives_V1_CANDIDATE_R8/3dddf9f62c9260b0` | NYG | 1 | draw 1796: 27 vs 26 (29 − 3) |
| `2026_01_SF_LA/post_inactives_V1_CANDIDATE_R5/ee1c94270bb53963` | SF | 2 | draw 190: 18 vs 17 (21 − 4) |
| `2026_01_SF_LA/post_inactives_V1_CANDIDATE_R7/e264f9c6b84837d9` | SF | 1 | draw 190: 18 vs 17 (21 − 4) |
| `2026_01_SF_LA/pre_inactives_V1_CANDIDATE` | SF | 1 | draw 752: 23 vs 21 (24 − 3) |
| `2026_01_SF_LA/pre_inactives_V1_CANDIDATE_R6` | SF | 1 | draw 190: 18 vs 17 (21 − 4) |
| `2026_01_TB_CIN/post_inactives_V1_CANDIDATE_R5/819a8eba1596697d` | TB | 1 | draw 243: 20 vs 19 (22 − 3) |
| `2026_01_TB_CIN/post_inactives_V1_CANDIDATE_R6/35c0c1c10aadf799` | CIN | 2 | draw 225: 11 vs 9 (11 − 2) |

Ten team-draws out of the 100,000 on old-credit C3-bound sides (100 sides x
1,000 draws). In each, the receiving chain caught more balls than the
quarterbacks had non-intercepted attempts to throw.

**What is needed.** An SC1-style coupling that reserves intercepted throws out
of the targeted-throw budget in `shared_pass.targeted_throws` *before* RC1
converts it to catches. `credit_passing_line`'s own docstring names this as
owed work. It is a pre-registered mechanism change, not a patch, and it sits in
`shared_pass.py` (mine) coupled to the receiving chain in `layers.py` (frozen)
— so it needs a pre-registration and an owner decision, not a fix slipped into
a migration. Clipping the completion count to fit was refused.

---

## 6. The upper tail, and its bound

**Do not read this as a repair-5 success. It is not one, and the brief said it
might not be.**

### The bound, derived

Two bounds, and the difference matters.

1. **Hard, from the rules of the game.** A completed forward pass gains at most
   99 yards — the line of scrimmage sits at most on a 1-yard line and the play
   ends between the goal lines — so `abs(pyds) <= 99 * cmp`. This is the only
   bound that holds unconditionally and it is deliberately loose.
2. **Record-anchored, on the rate.** 554 yards (Norm Van Brocklin, LA Rams at
   NY Yanks, 1951-09-28) is a *realisation*, not a bound. A Monte Carlo engine
   that can never exceed the all-time record is wrong in the other direction —
   some mass above it is correct — so the fence is on the exceedance **rate**:
   1. Estimation corpus: every quarterback game-line in
      `nfl/research/qb2/qb.pkl` with at least one completion — **n = 3,787**,
      seasons 2020–2025. This is the generator's own donor pool
      (`qb2_lib.pools` resamples yards-per-completion from exactly these rows),
      not an outside yardstick.
   2. Observed maximum in that corpus: **525 yards**. Games above 554: **0**.
   3. Zero events in n trials does not mean the probability is zero. The rule
      of three gives the exact one-sided 95% upper confidence limit,
      `p_max = 1 − 0.05 ** (1/n)` = **7.907e-4** (the familiar `3/n` = 7.922e-4).
   4. Fence: the share of simulated quarterback game-lines above 554 must not
      exceed `p_max`.

Nothing is clipped anywhere to satisfy either bound. Both are measured on the
draws as they are.

### What it measures

Split by **side**, because the two generators are different: a side with a
receiving layer takes its passing yards from the receiving event, a side
without one takes them from `qb2_lib`'s yards-per-completion resample.

| side family | cells | above 554 | rate | vs limit 7.907e-4 | max draw | outside `99·cmp` |
|---|---|---|---|---|---|---|
| `C3_SIDE` (migrated + clean) | 326,000 | 80 | 2.454e-4 | **inside** | 755 | **0** |
| `QB_ONLY_SIDE` | 520,000 | 680 | 1.308e-3 | **OUTSIDE, 1.65×** | 1,587 | 0 |
| declared unmigratable, counted apart | 144,000 | 37 | 2.569e-4 | inside | — | 4,630 |

**The migration fixed the hard-rule bound and did not fix the record tail.**

* On the 42 migrated boards the count outside `abs(pyds) <= 99·cmp` went
  **13,413 → 0**. Those were the `cmp == 0` cells carrying yards: at zero
  completions the hard bound is zero, so every one of them was outside a bound
  no football game can be outside. That is now zero by construction.
* Record exceedances on the same 42 boards moved **72 → 74**, max unchanged at
  755. The migration moves yardage between passers within a team; it does not
  change the team total, so it cannot move this tail materially, and it did
  not.
* **Residual: 680 cells above the all-time record, max 1,587 yards, on the 68
  quarterback-only boards.** Repair 5 does not touch them and cannot. The
  mechanism is `qb2_lib.py:306-307`, `PY = CMP * ypc_d` — one game-level
  yards-per-completion ratio resampled whole and multiplied by an
  independently drawn completion count, with the donor pool's maximum ratio
  (75.0 yards per completion) coming from a one-completion game. `qb2_lib.py`
  is held by another agent. **This check is left FAILING in
  `test_passer_credit_migration` rather than absorbed.**

---

## 7. `rushing_td <= carries` — measured, attributed, left red

442 cells corpus-wide, unchanged by the migration and outside its reach: the
passing credit never touches the rushing layer. The count is also **not** a
credit-function signature — one of the 442 sits on `f91342d6787a66a1`, a
`C3_NEW_CREDIT` board with zero passing-line violations.

What it actually is: **`rushing/carries` is not a count.** It is stored as
float64 and **327,103 of 516,000 cells (63.4%) are not integers**. Every one of
the 442 violating cells has `0 < carries < 1` with `rushing_td == 1`, and the
count falls to **zero** against `ceil(carries)` or `rint(carries)`. This is the
same int-vs-float mismatch X1 §2.5 records for `team_volume/team_carries`.

So the identity is being evaluated against a continuous level rather than a
realised carry count. The fix is to deal an integer carry count in the rushing
allocation (`nfl/production/nonqb/rushing_a1.py`, held by another agent, with
`layers.py` frozen beneath it). **Not repair 5. Not weakened to
`rushing_td <= ceil(carries)` to make it green** — that would be moving a fence
to fit the data.

---

## 8. Seal verification

Three independent checks, all after the migration ran for real:

1. **`board_pointer.verify_seal('V1_SEALED')` → `PASS SEAL_INTACT`.**
   `nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1`,
   recomputed draws sha256
   `53fc6fed4998d9486e8c789c265fcd14d8bf9394266e928c5eaf84290c3b347b`
   equals the declared value.
2. **A full byte snapshot** — sha256 of every file in every one of the 121
   sealed run directories, taken before and after running the whole migration
   into a temporary root, inside
   `test_passer_credit_migration::test_e_the_migration_leaves_every_sealed_byte_alone`.
   Zero files changed, zero removed, zero added inside a sealed directory.
3. **`git status -- nfl/research/live/` is empty.**

And a fourth, structural: `test_a` asserts the violations are **still present**
in the sealed bytes. If that check ever reads zero, a seal was rewritten or the
scan stopped scanning.

---

## 9. Open: `test_draw_coherence` cannot reach zero, and why

The brief asked for the migration to drive `test_draw_coherence`'s failing
checks to zero, and separately for every old seal to be preserved
byte-identical. **Those two instructions are in direct conflict and I could not
satisfy both.** Reporting it rather than picking one quietly.

`test_draw_coherence.sealed_corpus()` is `sealed_index.live_draw_files()` — the
109 sealed boards under `live/`, whose bytes are immutable. The migration
cannot lower a count measured on bytes it must not touch. Measured now, after
the migration, and identical to before it:

```
qb_completions_within_attempts               6,085   (baseline 5,278)
qb_completions_and_interceptions_within_att  6,827   (baseline 5,929)
qb_passing_td_within_completions               841   (baseline   731)
qb_passing_td_within_attempts                   24   (baseline    22)
qb_zero_completions_zero_passing_yards      13,524   (baseline 11,616)
```

**I did not touch those baselines.** Raising them to the measured values would
absorb the discovery the file's own comment says must stay visible; setting them
to zero would make the fence fail harder. What the repair actually achieves is
zero on the 113 boards of the *effective* corpus, and that is asserted in
`test_passer_credit_migration::test_b`.

**What would close it, and why I did not do it.** The fence would have to scan
the effective corpus — the migrated artifact where one exists, the sealed board
otherwise. That needs a supersession rule inside
`sealed_index.live_draw_files()` **and** the matching rule in
`test_sealed_corpus_census.expected_corpus()`, or the two fences disagree about
what the corpus is and the census fails. I did not make that change for two
reasons, and the second is the real one:

1. Neither file is mine, and both were re-frozen by repair 7 this session.
2. **It would be wrong.** `live_draw_files()` is also what the prospective
   ledger reads. Those 42 sealed boards *are* the prospective forecasts; the
   migrated rebuilds are post-hoc artifacts built after kickoff. Teaching the
   shared discovery to return a post-hoc rebuild in place of a prospective
   forecast would contaminate the prospective evidence base to fix a coherence
   count.

My recommendation, for whoever owns that fence: leave the corpus discovery
alone and reframe `test_draw_coherence` as what its own docstring already calls
it — a regression fence on immutable history, asserting the sealed generation
carries *exactly* its measured counts (6,085 / 6,827 / 841 / 24 / 13,524, which
are the post-repair-7 full-corpus numbers), with the migration ledger cited as
where the coherent generation lives. That needs an owner's decision, not mine.

---

## 10. Test results

| suite | result |
|---|---|
| `--only test_passer_credit_migration` (before migration) | **FAIL**, 6 failing checks — the reproduction, 36,587 cells / 50 boards |
| `--only test_passer_credit_migration` (after migration) | 32 passed, **3 failed** — all three declared residuals owned elsewhere (2 rushing, 1 quarterback-only upper tail) |
| `--only test_sealed_corpus_census` | **PASS**, 10 checks, 0 failing |
| `--only test_draw_coherence` | FAIL, 9 failing checks — **unchanged by this work**, see section 9 |
| `--only test_xl1_shared_pass` | **PASS**, 115 checks, 0 failing |
| `--only test_product_orchestration` | **PASS**, 51 checks, 0 failing |
| `--only test_football_engine_r4` | **PASS**, 142 checks, 0 failing |
| `--only test_v1_nonqb_production` | **PASS**, 35 checks, 0 failing |
| `--only test_conservation` | FAIL, 6 failing checks — unchanged by this work, same corpus-fence class as section 9 |
| `--only test_stat_contract` | FAIL, 1 failing check — unchanged by this work, and it is the same rushing-carries non-integrality as section 7, fenced there at 62.75% |

Full before/after transcripts:
`nfl/research/v4/p4/BEFORE_test_passer_credit_migration.txt` and
`AFTER_test_passer_credit_migration.txt`.

---

## 11. Files

**Written or changed by this workstream, and nothing else:**

* `nfl/tools/passer_credit_migration.py` — new. The migration tool, the
  coherence scan, the derived tail bound, the effective-corpus reader.
* `nfl/tests/test_passer_credit_migration.py` — new. The per-row box-score
  fence and the seal-preservation proof.
* `nfl/production/nonqb/shared_pass.py` — `CREDIT_TO_PASSERS_STATUS` and
  `CREDIT_TO_PASSERS_REPLACEMENT` added, plus a supersession note in the
  docstring. **The function body is unchanged**: fixing it in place would alter
  what the historical generator does and destroy the one property it is still
  kept for.
* `nfl/research/v4/p4/` — this report, the ledger, the two transcripts, and
  `migrated/` (42 artifacts).

**Read but not modified:** `football_engine.py` (sha256 at migration time
`7218606c8fa859c20308d959c9938cd54861f9c779b9e3c7b499b3fecebd8ec9` — it is held
by another agent and was being edited during this session, so a rerun against a
different version may not reproduce these bytes), `sealed_index.py`, `qb2_lib.py`,
`rushing_a1.py`, `layers.py`, `test_draw_coherence.py`,
`test_sealed_corpus_census.py`.

**DEN@KC was not tuned to.** Its realised outcome is not in this repository;
`pbp_2026` predates the kickoff and carries zero DEN and zero KC rows. The three
DEN@KC boards are `C3_NEW_CREDIT`, were already coherent, and were not migrated
or altered.

## 12. Reproduce

```
sha256sum nfl/production/nonqb/layers.py          # 481f005f682cd721...
python3.12 nfl/tools/passer_credit_migration.py   # writes migrated/ + the ledger
python3.12 nfl/tests/run_suite.py --only test_passer_credit_migration
python3.12 nfl/tests/run_suite.py --only test_sealed_corpus_census
python3.12 nfl/tests/run_suite.py --only test_draw_coherence
python3.12 -c "import sys;sys.path.insert(0,'.');from nfl.product import board_pointer as B;print(B.verify_seal('V1_SEALED'))"
```
