# The player-by-player evidence review as a mandatory pipeline stage

Status: **implemented and running**, not a proposal awaiting approval. The
modules are in `nfl/production/review/`, the suite is
`nfl/tests/test_player_review.py`, and the first slate artifact is at
`nfl/research/player_review/2026_02_NYG_LA/`.

Candidate identity unchanged: `CANDIDATE_NOT_ACCEPTED_BASELINE`. This stage
reviews projections; it does not produce or alter one.

---

## 1. Architecture

The required order, with the owner of each stage:

```
raw evidence            vintage store, append-only manifest
   |
player dossier          review/dossier.py        <-- NEW
   |
evidence reconciliation review/dossier.py grades every axis
   |
role / opportunity      universe/role_state.py, universe/allocation.py
   |
projection              production/run_forecast.py
   |
simulation              sealed draw artifact (npz + manifest + digest)
   |
projection audit        review/audit.py          <-- NEW
   |
optimizer               gated by review/slate_report.py
                        assert_player_review_complete()   <-- NEW GATE
```

Five modules, each with one job:

| Module | Job | Refuses |
|---|---|---|
| `evidence.py` | the typed axis, its grade, and the registry of sources this checkout cannot obtain | turning an absent source into a zero |
| `dossier.py` | one `PlayerPregameDossier` per player, plus the projection decomposed per component with a grade and the artifact digest | inferring availability from omission; letting special-teams depth touch an offensive room |
| `audit.py` | every disagreement between a published number and the evidence grade under it | comparing against a market or an external projection |
| `escalation.py` | IMPACT x DISAGREEMENT x UNCERTAINTY, allocated against a stated reviewer capacity | letting an external number reach anything but a priority |
| `slate_report.py` | the saved artifact, and the gate that stops an unreviewed slate | reporting a partial write as success |

Conceptual names from the directive, mapped to what was actually built.
`PlayerPregameDossier`, `ProjectionConflict` (as typed conflict records),
`PlayerReviewVerdict` and `SlateReviewReport` are present under those names.
`RoleEvidence`, `ParticipationEvidence`, `OpportunityEvidence` and
`CurrentGameEvidence` were **not** built as four classes. They collapsed into
one `Axis` type carrying `(value, grade, source, observed_at, window, note)`,
because four parallel classes with the same five fields would have needed four
copies of the grading rule, and the defect this stage exists to prevent is two
facts sharing a field. One axis type, many named axes, one grading rule.
`ProjectionProvenance` became `ProjectionComponent` plus the artifact digest on
the dossier, so provenance is attached per number rather than per player.

### Why the audit is a separate stage from the layer that computes

The layer that produces a number is the worst judge of it. Every defect this
project has paid for was green in the layer that caused it: `role_state` was
satisfied with its role, the allocator was satisfied that it conserved, the
sealer was satisfied that it sealed. None of them asked whether a back the club
lists fourth out-carrying the back it lists first is a thing that should be
published. That question needs a reader that owns no layer.

---

## 2. What the first run found

One change was made to production-adjacent code, with the review run before and
after it. Baseline -> one change -> compare, as the rules require.

### The defect

`player_universe.py` kept **one depth row per player**, newest `dt` wins. But
every row in an nflverse depth capture carries the **same `dt`**, so the `>`
comparison never fired and the survivor was decided by the order rows happened
to sit in the file. Measured on the 2026-09-21 capture:

| Player | Club listing | Survived as | Offensive rank read |
|---|---|---|---|
| Kyren Williams | RB1 **and** PR2 | PR2 | none |
| Tyrone Tracy Jr. | RB4 **and** KR2 | KR2 | none |
| Blake Corum | RB2 **and** KR4 | KR4 | none |
| Devin Singletary | RB3 **and** KR3 | KR3 | none |
| Ronnie Rivers | RB **and** KR2 | KR2 | none |
| Xavier Smith | WR **and** PR1 | PR1 | none |

`depth_role.offensive_depth_rank` then correctly returned
`OFFENSIVE_DEPTH_UNKNOWN` for each — correct, because by that point the
offensive row was gone. **The typing was right and the row selection was
wrong.** Six of the two clubs' skill players, including both starting running
backs, reached the role layer with no offensive depth at all.

This is a third distinct claim about the same players, and the first two are
withdrawn. Commit `c182e68` said `role_prior` reads Tracy's KR2 as RB2 — false,
`depth_vintage.daily` drops return groups and production returns `('RB', 4)`.
Commit `14850dd` retracted that and located the KR2 in the candidate universe
layer — correct as far as it went, but it described the KR2 as a rank being
mistyped. It was not: the rank was never mistranslated, the wrong **row** was
selected, under a tie-break that did not exist.

### The fix

`depth_role.select_listings(rows, model_position)` selects the offensive row
and the special-teams row **independently**, under a total ordering (newest
`dt`, then strongest rank, then group name) so file order cannot decide
anything. `player_universe` keeps every listing and records them all in a new
`depth_listings` field. The legacy `depth_pos_abb` / `depth_rank` pair is now
offensive-only: a consumer reading `depth_rank` is asking a workload question,
and a return rank is not an answer to it.

### Before and after, same slate, same sealed draws

| | before | after |
|---|---|---|
| `SPECIAL_TEAMS_ONLY_PLAYER_CARRIES_OFFENSIVE_LOAD` | 6 | **0** |
| `ROOM_OPPORTUNITY_ORDER_INVERTS_ROLE_ORDER` | 4 | **8** |
| blocking conflicts | 11 | 5 |
| uncertainty `OFFENSIVE_DEPTH_UNKNOWN` | 9 | 4 |
| uncertainty `EVIDENCE_SUFFICIENT` | 18 | 24 |

The inversions **rose** because the check needs an offensive rank to compare
against, and six players did not have one. That is the check starting to work,
not a regression.

### The inversion it now raises by itself

> Tyrone Tracy Jr., listed **carries rank 4**, projected **8.094 carries**,
> ahead of Cam Skattebo at **rank 1** on **6.144** — while measuring no higher
> on snap share (**0.03** vs **0.61**) or on prior usage (**2** carries vs
> **18**).

That is the defect the owner caught by hand last night, found automatically,
pre-optimizer, with the evidence attached. Eight such inversions in total, four
on each club.

**The gate FAILS on last night's slate.** Five blocking
`UNSUPPORTED_ROLE_PUBLISHED` conflicts remain: Najee Harris, Jameis Winston,
Patrick Ricard, Max Klare, Tutu Atwell all carry material opportunity on roles
`role_state` itself refused to support. Had this stage existed, the slate would
have stopped before the optimizer rather than after the owner read it.

---

## 3. Data sources

### Available and used

| Source | Axes it fills |
|---|---|
| `weekly_rosters` vintage | roster status, position, tenure, identity |
| `depth_charts` vintage | offensive depth rank, special-teams role, every listing |
| `injuries` vintage | report status, practice status |
| PFR snap counts (`availability_raw/snap_counts_2026`) | `offense_pct`, `offense_snaps`, `st_pct`, `st_snaps`, `defense_pct` |
| lawful play-by-play usage panel | carries, targets, carry share, target share, club of record |
| owner-supplied inactive board | official availability, at its true tier |
| sealed draw artifact | the projection, per component, with both file digests |
| post-inactives redistribution accounting | vacated opportunity, graded `REDISTRIBUTED` |

### Missing, registered rather than worked around

`evidence.UNAVAILABLE_SOURCES` holds eleven entries. Every dossier reports all
eleven on every player, so nobody can read a role as examined on an axis that
was never read.

| Missing | Why | Who owns it |
|---|---|---|
| routes, routes per dropback | `pbp_participation` 404s for 2026 | network agent |
| pass-block / run-block snaps | no pass/run split in the PFR snap file | network agent |
| personnel 11 / 12 / 13 / 21 | lives in `pbp_participation` | network agent |
| slot / outside alignment | needs participation or charting | network agent |
| coach news | no egress: nfl.com, club sites, open web all refuse | network agent |
| transactions | no egress, endpoint unverified | network agent |

**This directly limits the TE requirement.** "Do NOT use raw snaps alone;
separate routes, pass blocking, run blocking, personnel grouping" **cannot be
satisfied with the data in this checkout.** Zero participation columns are
present. Rather than approximate it, every receiver with material projected
targets now carries an explicit `RECEIVING_ROLE_RESTS_ON_RAW_SNAPS_ONLY` note —
21 of them on this slate — saying the axis that would settle the question was
not read. Requests go to `docs/AGENT_OUTBOX.md`; the work is **assigned, not
blocked.**

---

## 4. Automated checks

Nine conflict codes, each with a severity that is about publishability rather
than size.

**BLOCKING** — stops the slate:
- `INACTIVE_PLAYER_OWNS_OPPORTUNITY`
- `UNSUPPORTED_ROLE_PUBLISHED`
- `SPECIAL_TEAMS_ONLY_PLAYER_CARRIES_OFFENSIVE_LOAD`
- `ACTIVE_PLAYER_NOT_EMITTED_BY_MODEL` — silence is not a forecast

**REVIEW** — a human reads before the slate is used:
- `DECLARED_STARTER_PROJECTED_AT_ZERO`
- `COLD_START_CARRIES_MATERIAL_PROJECTION`
- `ROOM_OPPORTUNITY_ORDER_INVERTS_ROLE_ORDER`
- `REDISTRIBUTED_OPPORTUNITY_DOMINATES_MEASURED`

**NOTE** — recorded, no action implied:
- `RECEIVING_ROLE_RESTS_ON_RAW_SNAPS_ONLY`

The inversion check is deliberately narrow. It does **not** enforce the depth
chart — clubs are wrong about their own backfields constantly, and a measured
usage share is better evidence than a listing. It fires only when the
higher-projected player measures **no higher on any readable axis**, and it
stays silent when neither player has a measured axis at all, because "no axis
supports it" is vacuous when no axis contradicts it either. Both behaviours are
pinned by test.

### Thresholds and their provenance

There is one numeric threshold, `material_opportunity = 1.0`, and it is
declared in the artifact as `DECLARED REVIEW-CAPACITY CHOICE, NOT MEASURED`:
one expected opportunity per game is the smallest quantity that can move a DK
lineup at all. It is not calibrated, has no empirical support, and must not be
adjusted to make a slate pass. The two escalation weight tables are declared
**orderings**, not estimates, with the same statement attached.

---

## 5. Escalation logic

`priority = impact x disagreement x uncertainty`, each in [0, 1].

- **IMPACT** — projected DK points as a fraction of the slate maximum.
  Scale-free on purpose: a slate projected uniformly low still ranks its own
  players correctly, which the absolute version did not.
- **DISAGREEMENT** — the maximum conflict severity weight, optionally raised by
  a quarantined external gap.
- **UNCERTAINTY** — the weight of the player's named uncertainty state:
  `CURRENT_ROLE_COLD_START` 1.0, `OFFENSIVE_DEPTH_UNKNOWN` 0.85,
  `CURRENT_GAME_ROLE_UNCERTAIN` 0.7, `HISTORICAL_PRIOR_DOMINANT` 0.5,
  `EVIDENCE_SUFFICIENT` 0.15.

**A product, not a sum**, so any zero factor zeroes the priority. A player
nobody can roster needs no research however uncertain; a player whose evidence
is complete and agreed needs none however large his projection. The
intersection is what is worth an hour.

**Tiers are a capacity allocation, not a score threshold.** The caller states
how many players can genuinely receive deep research; the highest-priority that
many get it. A threshold here would be a fitted constant with nothing behind
it. The one override is a blocking conflict, which escalates at zero capacity,
because it stops the slate either way.

### Where market and external numbers are allowed

An external projection or a Hard Rock line may raise `disagreement` and may do
nothing else. It is passed in a separate argument, stored under
`external_disagreement_quarantine`, and reaches no axis, no role, no share, no
team volume, no appearance probability and no draw. The test asserts the
dossier is **byte-identical** before and after an external gap is applied.

Owner's rule, enforced here: sportsbook prices must not become predictive
inputs into the football model. Raising a research priority is not an input to
a forecast; moving a number toward a market is.

### First real queue (NYG @ LAR, capacity 12)

| | Player | priority | I | D | U | state |
|---|---|---|---|---|---|---|
| 1 | Najee Harris | 0.3118 | 0.312 | 1.00 | 1.00 | COLD_START |
| 2 | Tutu Atwell | 0.1587 | 0.159 | 1.00 | 1.00 | COLD_START |
| 3 | Max Klare | 0.1306 | 0.131 | 1.00 | 1.00 | COLD_START |
| 4 | Jameis Winston | 0.0660 | 0.066 | 1.00 | 1.00 | COLD_START |
| 5 | Patrick Ricard | 0.0547 | 0.078 | 1.00 | 0.70 | ROLE_UNCERTAIN |
| 6 | Tyrone Tracy Jr. | 0.0502 | 0.558 | 0.60 | 0.15 | SUFFICIENT |

Najee Harris first — the player the owner removed by hand last night. Tracy
sixth, on a high impact and a real conflict against otherwise sufficient
evidence.

---

## 6. Coverage

Measured on the live slate, not estimated:

- **156 dossiers**, one per player in the point-in-time universe (LA 77,
  NYG 79)
- **28 of 28 publishable players covered — 1.0000**
- 156 files written and 156 files verified on disk; a count mismatch is a named
  `FAIL`

Coverage is measured against the **publishable** population, not the universe,
and the two are reported separately. "100% of the universe" would be the weaker
claim: the universe includes practice-squad players nobody will roster. The
claim that matters is that every number an optimizer can use has a dossier
behind it.

Uncertainty spread: 80 `CURRENT_ROLE_COLD_START`, 48
`CURRENT_GAME_ROLE_UNCERTAIN`, 24 `EVIDENCE_SUFFICIENT`, 4
`OFFENSIVE_DEPTH_UNKNOWN`. Most of the 80 are deep bench and special-teams
players with no 2026 offensive snap, which is the honest reading of a week-2
slate.

---

## 7. The saved artifact

```
nfl/research/player_review/<slate_key>/
    SLATE_REVIEW.json          coverage, conflicts, queue, digests
    players/<gsis_id>.json     one dossier per player
```

1.4 MB for this slate. `SLATE_REVIEW.json` digests every player file, and the
sealed draw artifact's own two digests are carried on every dossier that quotes
a projection — `d73aa88a...` for the npz here, matching
`PRE_GAME_BOUNDARY.json` exactly.

Tracy's file answers the three-weeks-later question without reconstructing
anything: RB4, BACKUP, snap share 0.03 over one observed game against derived
floors 0.5361/0.3735/0.2084, 2 prior carries, carry share 0.054 — and a
projection of 8.094 carries and 9.145 DK points, with routes marked
UNAVAILABLE and why.

One reading caution. A projection component's grade describes **what produced
it**, not whether it is right: Tracy's carries read `MEASURED` because
`role_state` and the usage panel are measured inputs. The judgement lives in
the conflict list on the same file, not in the grade.

---

## 8. Tests

`nfl/tests/test_player_review.py` — **53 checks, 53 passing.** Seven groups:

1. the collapse defect, including 40 row-shuffles proving selection no longer
   depends on file order, and the four named players recovering their listings
2. missing sources named, never zeroed
3. availability never inferred from omission, in both directions
4. the audit: every blocking code, plus the inversion check's silence when
   measured usage supports the inversion and its firing when nothing does
5. escalation: product semantics, blocking at zero capacity, capacity as a
   budget, and the byte-identical dossier after an external gap
6. the gate: missing dossier, unresolved blocking conflict, digest mismatch,
   empty write
7. the live slate end to end, asserting coverage 1.0, 156 files on disk, and
   the Tracy inversion with its evidence

Regression state across the suites that touch the changed modules, all at the
corrected code:

| Suite | Result |
|---|---|
| `test_player_review` | 53 / 53 |
| `test_depth_role_contamination` | 45 / 45 |
| `test_player_universe_coverage` | 44 / 44 |
| `test_false_greens` | 66 / 66 |
| `test_allocation` | 74 / 74 |
| `test_role_state` | 62 / 62 |
| `test_participation` | 57 / 57 |

**Four assertions in `test_depth_role_contamination` were corrected, not
accommodated.** They had pinned the collapse as intended behaviour — that
Tracy's universe row reads `KR` and his offensive rank is therefore refused.
That was the bug being asserted as a feature. Each now pins the corrected
invariant, with the reason written in the file so the wrong version cannot be
restored, and the unconditional rule (a KR rank can never become a backfield
rank on any path) is still proved separately.

---

## 9. Files added and changed

**Added**
- `nfl/production/review/__init__.py`
- `nfl/production/review/evidence.py`
- `nfl/production/review/dossier.py`
- `nfl/production/review/audit.py`
- `nfl/production/review/escalation.py`
- `nfl/production/review/slate_report.py`
- `nfl/production/review/run_review.py`
- `nfl/production/review/PLAYER_REVIEW_STAGE.md`
- `nfl/tests/test_player_review.py`
- `nfl/research/player_review/2026_02_NYG_LA/` (157 files)

**Changed**
- `nfl/production/universe/depth_role.py` — `select_listings`, `_neg`
- `nfl/production/universe/player_universe.py` — keep every listing; select
  the two axes independently; `depth_listings` field; offensive-only legacy pair
- `nfl/tests/test_depth_role_contamination.py` — four corrected assertions

**Untouched, as required:** accepted baseline R8, Q9 promotion state,
governance, sealing requirements, model registry status.

---

## 10. What is not done

Named rather than left implied.

1. **The gate is not yet wired into `run_forecast` or the optimizer.** It
   exists, it runs, and it refuses correctly, but nothing calls it yet. Wiring
   it is a separate measured change — baseline, one change, run, compare — and
   it will stop slates, so it needs the owner's word on whether an unresolved
   blocking conflict halts a card or annotates it.
2. **Routes, blocking splits and personnel remain unavailable**, so the TE
   requirement stays unsatisfiable here. Assigned to the network agent.
3. **The five `UNSUPPORTED_ROLE_PUBLISHED` conflicts are unexplained.** The
   review found them; it does not say why `run_forecast` publishes opportunity
   on a role `role_state` refused. That is Phase 1 item 3, cold-start priors.
4. **The Tracy/Skattebo inversion is now measured but still not explained.**
   Depth contamination is eliminated as its cause in the candidate layer, and
   production already read him RB4, so the mechanism remains downstream of
   tiering. Phase 2.
5. **`depth_role.guard_rank_map` is still not wired into `run_forecast`**,
   where `dr[k] = v[1]` continues to discard the group. Pending as its own
   measured change.

No result from the NYG @ LAR game was used anywhere in this work. The
pre-kickoff boundary in `PRE_GAME_BOUNDARY.json` holds.
