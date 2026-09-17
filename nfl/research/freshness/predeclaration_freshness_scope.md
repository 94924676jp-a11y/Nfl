# `CURRENT_SEASON_INPUT_FRESHNESS` — scoped, fail-closed, no inference

**Pre-registered before implementation.** Contract 3 untouched. No existing
seal rewritten.

## 1. Why scope is the whole design

The blanket question "is the current-season panel fresh?" has no single right
answer, because two different consumers need two different things from the same
artifact:

- The **DET–BUF board** uses current-season state to establish **BUF and DET**
  incumbency. Both clubs are present and lawful. Demanding 32 of 32 would block
  a board on the absence of two clubs it never reads.
- A **league-wide model fit** — a rate estimated across all clubs — that silently
  drops DEN and KC is fitting on 30 clubs while reporting as though on 32. That
  must refuse.

A rule with one threshold either blocks the first or admits the second. **So
scope is declared per requirement, not per artifact.**

## 2. The two scopes

| scope | rule | refusal |
|---|---|---|
| **`FIXTURE_LOCAL`** | every club **the forecasted fixture names** must be current to the required ordinal | a missing fixture club is `BLOCKED` |
| **`LEAGUE_WIDE`** | every club in the **declared expected set** must be current | **30 of 32 is `BLOCKED`.** No majority rule, no quorum |

**`expected_clubs` is supplied by the caller and never inferred from what the
data happens to contain.** Deriving the expected set from the present set makes
the check tautological — it is the exact failure that let a 30-club panel look
complete.

## 3. The ordinal rule

For a forecast at `S*100 + W`:

- **`W == 1`** → `NOT_APPLICABLE_AT_A_SEASON_OPENER`. Never `FRESH`. A season
  opener legitimately has no current-season prior week, and conflating that
  with a passing check is precisely what hid the defect for a week.
- **`W >= 2`** → every registered input must carry `max_ordinal >= S*100 + (W-1)`.

**Ordinals, not wall-clock.** A file cannot be made fresh by `touch`.

## 4. What the invariant reports, always

Per registered input, whether it passes or fails:

```
input_id            panel_p3
scope               FIXTURE_LOCAL | LEAGUE_WIDE
expected_clubs      [...]            # supplied, never inferred
present_clubs       [...]
missing_clubs       [...]            # named; never filled in
newest_ordinal      202601
required_ordinal    202601
state               PASS | BLOCKED
code                CURRENT_SEASON_INPUT_FRESH | CURRENT_SEASON_INPUT_STALE
                    | CURRENT_SEASON_INPUT_INCOMPLETE
                    | NOT_APPLICABLE_AT_A_SEASON_OPENER
cause               DATA (on any BLOCKED)
provenance          [ {club, source, blob, sha256, retrieved_at, row_kind} ]
```

**`provenance` carries a row for every ADMITTED club**, naming the blob and its
retrieval instant. A club admitted by the snap proxy is marked as such, so
`play_by_play` and `snap_proxy` can never be read as the same evidence.

**Two distinct failures, two distinct codes.** `..._STALE` means the newest
ordinal is too old. `..._INCOMPLETE` means the ordinal is fine and clubs are
missing. Collapsing them would repeat the `is_season_opener` mistake of one flag
for two conditions.

## 5. The registry

Explicit and versioned, `FRESHNESS_REGISTRY_VERSION = 1`:

| input | scope for a single-fixture board | scope for a league-wide fit |
|---|---|---|
| `panel_p3` (QB incumbency) | `FIXTURE_LOCAL` | `LEAGUE_WIDE` |
| `denom_panel` | **`LEAGUE_WIDE`, and currently BLOCKED** | `LEAGUE_WIDE` |
| team-volume history | `FIXTURE_LOCAL` | `LEAGUE_WIDE` |

**`denom_panel` stays BLOCKED and is not refreshed.** Its 2026 source, vintage,
completeness, coverage, field definitions and identity behaviour are not
established, and a partially complete denominator produces confidently wrong
shares rather than a nameable refusal. It is stale **by declaration**.

## 6. DET–BUF, decided

`panel_p3` at `FIXTURE_LOCAL` for `2026_02_DET_BUF`: expected `{DET, BUF}`,
present `{DET, BUF}`, missing `{}`, newest ordinal `202601`, required `202601`
→ **PASS**, on the evidence that Josh Allen took 58 snaps at 100% and Jared Goff
77 at 100% in week 1, both from a capture retrieved 2026-09-14T18:33:36Z,
43h50m before the earliest arm was written.

The **same input at `LEAGUE_WIDE`** is `CURRENT_SEASON_INPUT_INCOMPLETE`,
missing `{DEN, KC}`. **Both verdicts are true at once, which is the point of
scoping them.** No model fit may claim league-wide current-season state until
DEN and KC are admitted from `nfl/capture/live_evidence_2026_01_DEN_KC.json`
with their own provenance rows.

## 7. Where it is enforced

`nfl/prospective/artifact.INVARIANTS`, class **HARD**, evaluated **before any
board may publish**. `qb_allocation.panel_freshness` is retained as the
**per-input ordinal primitive**; this rule is the registry, the scope, the club
accounting and the refusal.

## 8. What would make this wrong

- **A caller declaring `FIXTURE_LOCAL` for something it uses league-wide.** The
  scope is a claim by the caller and the invariant cannot verify the claim. It
  can only make the claim explicit and recorded — which is strictly better than
  the claim being implicit, and is not the same as proving it.
- **An expected set that is itself wrong.** Passing `{DET, BUF}` for a fixture
  that also reads a third club's state would pass while being incomplete.

**V2 NOT YET EARNED**
