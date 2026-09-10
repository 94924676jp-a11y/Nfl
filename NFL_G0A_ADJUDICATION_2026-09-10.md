# G0A adjudication — 2026-09-10

# `G0A_11_OF_12_ITEM1_NOT_CLEARED`

**No repair was made. Nothing was loosened. V1 engineering is untouched.**

---

## Item 1 — FAIL, with the exact failing predicate

Obligation `2026_01_NE_SEA / inactives`, from
`nfl/capture/t90_obligation_reconciliation.json`:

```
kickoff_utc                       2026-09-10T00:20:00Z
window_start_utc                  2026-09-09T22:50:00Z
window_end_utc                    2026-09-10T00:10:00Z
window_opened                     True
window_closed                     True
qualifying_captures               0
nonqualifying_in_window_captures  0
status                            MISSED
reason   window closed with no authorised, in-window, game-attributed capture
```

**The failing predicate is `qualifying_captures == 0`.** And
`nonqualifying_in_window_captures == 0` too, which settles the question the
directive asks: this is **not** a capture that was taken and rejected on a
technicality, and **not** a readiness-implementation defect. Nothing was
captured in the window at all.

## Why no legitimate artifact exists — measured, not inferred

| check | result |
|---|---|
| manifest rows total | 751 |
| **newest manifest row** | **2026-09-08T17:06:03Z** — ~30 h *before* the window opened |
| captures on/after 2026-09-09 | **0** |
| rows carrying `game_id`, `basis` or `schedule_id` | **0 of 751** — nothing in the manifest is anchored to a target game |
| blobs committed since 2026-09-09 | 37 `schedules`, 1 `depth_charts`, 1 `injuries`, 1 `weekly_rosters` |
| `inactives` / `practice` / `final_status` blobs since 2026-09-09 | **0** |
| newest perishable blob of any kind | 2026-09-08T17:06:09Z |

**The capture bot's recent commits are real but are the wrong kind.** Runs
34428060587 and 34430233471 (2026-09-10T02:05Z and 02:38Z) each added a single
`schedules` blob and **wrote no manifest row**. `schedules` is not a perishable
item-1 kind. A workflow run is not a discharge.

Nothing was substituted: no periodic sweep, no manual dispatch, no practice
capture and no historical artifact is being credited toward the inactives
obligation, because none is present in the window to credit.

Four other perishable obligations are also MISSED and equally not creditable:
`NE_SEA/practice`, `NE_SEA/final_status`, `SF_LA/practice` ×2.

## NFL-1 — NOT AUTHORIZED

Derived from the canonical gate, not asserted:

```
authorization.may_publish() -> BLOCKED[NFL1_NOT_AUTHORIZED]
gates: {'G0A': '11/12', 'NFL_1': 'NOT AUTHORIZED'}
```

**The exact remaining gate is G0A item 1.** The contract also states that no
test result, checklist state or caller flag can change it — only an owner
authorization record at `nfl/NFL1_OWNER_AUTHORIZATION.json`, and
`assert_no_auto_authorization` enforces that no code path may create one. No
flag was flipped.

## Live input readiness

`INJURIES_2026_PUBLISHED_BUT_INSUFFICIENT` — the feed parses but covers **2 of
32** slate teams, and `report_status` is populated on **0** of 11 rows. So the
appearance layer defers, and with it participation, targets/carries, conversion
and the TD layer. **Full non-QB player coverage is unavailable, and that is an
external input state, not an engineering defect.**

**C3 is NOT_REACHED for exactly one reason:** it needs the receiving target
budget, which is built from the appearance layer, which is deferred on that
feed. Nothing in C3 is broken.

No input is stale or violates chronology in a way that was silently accepted:
the one chronology refusal below is the guard firing correctly.

## Canonical dry run — `V1_CANDIDATE`, `--written-at 2026-09-10T12:00:00Z`

Pre-kickoff for every target it forecast.

| | |
|---|---|
| result | **15 SEALED, 1 REFUSED** |
| the refusal | `SOURCE_CHRONOLOGY_FAILURE` on `2026_01_NE_SEA`, which kicked off 2026-09-10T00:20Z — the guard working |
| model configuration | `V1_CANDIDATE`; `promoted` False; `prospective_eligible` False |
| manifest | A1, A3G, C0, C3, R2, SC1 |
| APPLIED | **A1, A3G, C0, R2, SC1** |
| NOT_REACHED | **C3** |
| hard invariants | **10 HARD PASS**, 1 HARD DEFERRED (`qb_cross_layer_reconciliation`, recorded as *owed*) |
| draw artifact | present, hashed; 15 distinct run ids for 15 games |
| publication | `NFL1_NOT_AUTHORIZED` on all 16 |

No masquerade: the artifact names its configuration and every component, and
`assert_not_promoted` passed at the seal on all 15.

## V1 engineering — frozen and unchanged

`git diff 42613b1 HEAD -- nfl/production/ nfl/prospective/ nfl/research/sc1 nfl/tests/`
is **empty**. The only changes since the freeze commit are two `schedules`
blobs from the capture bot.

**Freeze commit `42613b13324c988316da773f9f4f486683af4a2f` stands.**
