# Early Only projection audit — do usable Week-2 projections exist?

**No.** Zero of the 256 Early Only players has a current usable projection.

229 have **readable distributions, including DraftKings fantasy points**, from
runs that are disqualified three times over: they refused to seal, they are
flagged `dry_run`/`prospective_eligible=false` by construction, and their
input-validation stage passed on a **placeholder source hash** rather than on a
real capture. Numbers exist. A forecast does not. That distinction is the
entire finding and a ready/not-ready flag would destroy it.

Evidence: `nfl/dfs/salaries/DK_EARLY_ONLY_PROJECTION_AUDIT.json` (451 KB, one
row per player).

## The verification rule, and a correction it forced

> A player is not projected because his `gsis_id` appears in a manifest or in
> a `row_ids` list.

I was about to report 240 "covered" from exactly that. `row_ids` is a claim a
run makes about itself. So every state below is established by **opening the
npz, indexing the row, and checking the vector** — right length, finite,
present.

| | |
|---|---|
| ids claimed in `row_ids` across 15 runs | 466 |
| ids with a distribution actually **read** | **466** |
| unreadable rows | **0** |

The first pass of that check returned **0 verified**, which I nearly reported.
It was my bug: the manifest spells a metric `layer/metric` and the npz stores
`layer__metric`, so every lookup missed. Both spellings are now tried and the
one that answered is recorded per metric. Had I trusted `row_ids` I'd have said
240; had I trusted my own first check I'd have said 0. Both were wrong.

## Totals — the 256-player Early Only universe

| state | n |
|---|---|
| `CURRENT_PROJECTION_AVAILABLE` | **0** |
| `STALE_PROJECTION_AVAILABLE` | **0** |
| `MODEL_REACHABLE_BUT_NO_CURRENT_PROJECTION` | **229** |
| `MODEL_REFUSED` | **0** |
| `IDENTITY_UNRESOLVED` | **0** |
| `NOT_MODELED` | **11** |
| `DST_UNSUPPORTED` | **16** |

## Universe validation

256 rows, 16 clubs, 8 games, QB 43 / RB 53 / WR 84 / TE 60 / DST 16, salaries
$2,100–$8,200, **0 missing salaries, 0 duplicate names**.
sha256 `b34b389e…7498fbc3`.

**Identity: 240 MATCHED, 16 DST, 0 UNMATCHED, 0 AMBIGUOUS, 0 duplicate
canonical ids, 0 team disagreements.** 234 exact, 5 normalised, 1 declared
alias (Hollywood Brown → Marquise Brown). All 256 also joined to official
DraftKings player IDs — 248 exact, 8 normalised (`JaMarr Chase` ↔ `Ja'Marr
Chase`, `Travis Etienne` ↔ `Travis Etienne Jr.`, and six like them). That join
is between two DraftKings-derived files, each authoritative about its own
spelling and neither about the other's; it uses the same punctuation-and-suffix
normalisation and **no edit distance**.

## The six questions

**1. How many have a current usable projection? — Zero.**

A projection is current only if it comes from a **sealed** board. Searching
every `board.json` in the repository: the only Week-2 boards that exist are
three for `2026_02_DET_BUF` — Thursday's game, already played, not on this
slate. For all eight Early Only games:

| game | sealed boards |
|---|---|
| CAR@ATL, CIN@HOU, CLE@TB, GB@NYJ, MIN@CHI, NO@BAL, PHI@TEN, PIT@NE | **0 each** |

**2. Football projection but no DK conversion? — Zero.**

All 229 reachable rows carry a `dk_scoring/dk_points` distribution. The DK
scoring adapter is implemented and running; it is not the blocker. (Across all
15 rehearsal games, 436 of 466 verified players carry DK points; the 30 without
are kickers and other non-DK-scored rows.)

**3. Merely model-reachable with no current projection? — 229.**

Per game: PIT@NE 32, PHI@TEN 31, CLE@TB 30, CAR@ATL 29, CIN@HOU 29, GB@NYJ 29,
NO@BAL 27, MIN@CHI 22.

**4. Which games are currently refusing? — All eight, and at TWO different
stages depending on how they are run.**

*As the rehearsal driver runs them*, every Early Only game **ran**: the engine
completed appearance, participation, targets/carries, conversion, TD, QB, joint
reconciliation, draws and scoring. Each then hit
`BLOCKED[ARTIFACT_SEALING_FAILURE]` on `current_season_input_freshness` —
`denom_panel` is BLOCKED-BY-DECLARATION (`CURRENT_SEASON_SOURCE_UNVERIFIED`)
and `team_volume_history` is `CURRENT_SEASON_INPUT_STALE` at ordinal **202518**
against a required **202601**. `denom_panel.csv.gz` holds 3,230 rows from
202001 to 202518 and **zero rows for 2026**.

*As the production entrypoint runs them*, they never get that far. Measured
just now, all eight at `--written-at 2026-09-20T05:00:00Z`, configuration
`V1_CANDIDATE_R8`, no `--fixtures`:

    BLOCKED[SOURCE_MISSING] capture_validation
    "no source captures were supplied"

Not one layer executes. The two results are not in conflict; they are the same
fact seen from two callers, and the next section is what the difference means.

So the narrow blocker is **`DK_SCORING_CONTRACT_INCOMPLETE`: no — that one is
fine.** It is `SEALING_REFUSED_NO_2026_DENOMINATOR_PANEL` **behind**
`NO_PRODUCTION_FIXTURE_ASSEMBLER`.

**5. Are existing projections stale? — Yes, all 229, by 13.5 hours.**

The runs read `injuries`, `official_injury_report` and `depth_charts` at
capture_id **20260919T150538Z**. The capture surface has since advanced to
**20260920T043746Z**. Every one of the 229 carries that gap in its `freshness`
field.

They are classified `MODEL_REACHABLE…` rather than `STALE_PROJECTION_AVAILABLE`
because the latter means a *sealed* artifact whose clock has aged. These were
never sealed. Both facts are true and the artifact records both.

`official_inactives` has **not** advanced — newest PASS is still
2026-09-15T17:05:12Z. Today's inactives have not published yet.

**6. Smallest step to a preliminary board tonight.**

**My first answer to this was wrong and I am withdrawing it.** It was: emit the
refused run's numbers as a `PROVISIONAL_UNSEALED` artifact. That cannot be done
honestly, for the reason in the next section — those numbers come from a run
whose input-validation stage was satisfied by a placeholder hash. Publishing
them under any label would be publishing numbers whose inputs were never
validated, and the label would not repair that.

The smallest honest step is one bounded piece of repository work:

> **Build a production fixture assembler.** Read the vintage manifest, emit
> true `source_hashes` — real sha256, real `retrieved_at` — for every
> registered source a slate run consumes, and hand that to
> `run_forecast.build`. Then `capture_validation` is satisfied by evidence
> instead of by `'b' * 64`, and the run need not be flagged `dry_run`.

That is inside this repository, needs no network, and is mine. It does not
weaken a gate; it removes a bypass. It also does not produce a board on its
own: sealing still refuses on the 2026 denominator panel (SUN-5) afterwards.

**Therefore there is no honest preliminary Early Only board tonight**, and the
deadline does not change that. Step (a), ingesting the fresh capture, is done
(commit `7e50eec`). Steps (b) and (c) as I described them are cancelled.

## The correction this audit needed, and it is the largest finding here

The first version of this document said the 229 reachable rows came from runs
that refused at `artifact_sealing`, and were 13.5 hours stale. Both true. Both
understate it, because I read the refusal and did not read the run's own
status file. It says:

| field | value, all 15 runs |
|---|---|
| `dry_run` | **true** |
| `prospective_eligible` | **false** |

That is not incidental. `nfl/production/rehearsal/run_slate.py` is the **only**
slate driver in the repository. Its own docstring opens "REHEARSAL ONLY", and
it passes `dry_run=True` in the call itself — there is no flag to turn off and
no non-rehearsal path from the vintage manifest to a slate run.

The reason it is declared rehearsal-only sits one line above that call
(`run_slate.py:96`):

```python
'source_hashes': {'schedules': {'sha256': 'b' * 64,
                                'retrieved_at': '2026-09-08T12:00:00Z'}},
```

Sixty-four `b` characters. And `capture_validation`
(`run_forecast.py:266-306`) iterates **the set it is handed** and has no
required-source check, so one synthetic entry passes the entire stage and it
returns `PASS[INPUTS_VALIDATED]`.

**Two things must be said precisely, because they are different.** The football
layers below that stage *do* read real captures, through
`nfl/production/nonqb/vintage_selector.py`, with real capture ids — which is
how the 13.5-hour figure was measurable at all. So the numbers rest on real
evidence. What rests on a placeholder is **the stage that certifies the
inputs**. A number can be computed from real data and still have no valid
provenance record, and that is exactly the state here.

Two defects, recorded separately:

- **DK-3 (`CRITICAL_CORRECTNESS`)** — `capture_validation` validates only the
  supplied set. It cannot detect a missing required source, so its PASS is a
  statement about the caller, not about the captures.
- **DK-4 (`PRODUCTION_BLOCKER`)** — no production fixture assembler exists. The
  only driver fabricates one source record; the direct entrypoint refuses
  `SOURCE_MISSING`. There is no third option today.

Had I stopped at the sealing refusal, this document would have read as *one
blocker away from a board*. It is not one blocker away.

## The 11 NOT_MODELED

Six are CHI, whose appearance layer was deferred for an incomplete injury
report. Only one is above $5,000:

| player | team | pos | salary |
|---|---|---|---|
| **D'Andre Swift** | CHI | RB | **$6,300** |
| Kyle Monangai | CHI | RB | $5,300 |
| Josh Johnson | CIN | QB | $4,000 |
| Roschon Johnson | CHI | RB | $4,000 |
| CJ Donaldson | NO | RB | $4,000 |
| Travis Homer | PIT | RB | $4,000 |
| + 5 more at $3,100 or less | | | |

Swift is a genuine hole at a usable price, and it traces to OUT-027 — CHI's
injury report. Fixing that recovers him and the five other Bears.

## DST — exact state for all sixteen

`DST_UNSUPPORTED`, all 16, and not because of coverage: **the engine produces
no team-defence outputs at all** (`statline.NOT_SIMULATED`: "the engine
produces no team-defence outputs at all"). There is no DST layer to be missing
data — there is no DST layer.

A Classic lineup must field one, so this alone prevents a legal lineup
regardless of how the offensive side resolves. The smallest football-native
implementation would model the DraftKings scoring events — sacks,
interceptions, fumble recoveries, defensive and return touchdowns, safeties,
and the points-allowed ladder — and the ladder's tier boundaries are part of
the Classic contract this repository does not yet hold (OUT-025).

Blocker code: `DST_DISTRIBUTION_UNAVAILABLE`, and behind it
`DK_CLASSIC_CONTRACT_ABSENT`.

## Portfolio readiness

**`NOT_READY`.**

Objective reasons, narrowest first:

1. `NO_PRODUCTION_FIXTURE_ASSEMBLER` — the only slate driver is
   rehearsal-only and satisfies `capture_validation` with a placeholder
   hash; the direct entrypoint refuses `SOURCE_MISSING`. **New, and it
   sits upstream of everything below.**
2. `SEALING_REFUSED_NO_2026_DENOMINATOR_PANEL` — 0 of 256 has a sealed
   projection.
3. `DST_DISTRIBUTION_UNAVAILABLE` — 16 of 16; no legal Classic lineup exists
   without one.
4. `DK_CLASSIC_CONTRACT_ABSENT` — no salary cap, roster slots, FLEX rule or
   DST points-allowed ladder in `site_rules.py`. (The *pool's* roster slots and
   FLEX eligibility ARE now known, from DK's own export; the contest rules are
   not.)
5. `PROJECTIONS_STALE_BY_13.5_HOURS` — being fixed as this is written.
6. `OFFICIAL_INACTIVES_NOT_YET_AVAILABLE` — expected, not a defect.

What is **not** blocking: identity (0 unresolved, 0 ambiguous), the slate
(resolved from DK's own export), DK scoring (implemented, running), the
offensive engine (all eight games ran every layer).
