# Thursday DET-BUF — literal-assumption audit, repairs, and where it still stops

**Game** `2026_02_DET_BUF`, Thursday 2026-09-17 20:15 ET (kickoff
`2026-09-18T00:15Z`).
**Written at** 2026-09-15T20:30Z. **Dev HEAD** `7b4588e`.
**Status: there is no DET-BUF board.** The eligibility chain is repaired; two
model-layer blockers remain.

---

## 1. What was asked

Audit the production path for places where a **data label is mistaken for
football reality**, repair only what materially distorts Thursday, then run
DET-BUF.

## 2. Findings

### L1 — "no week-2 roster capture" read as "no players exist" — BLOCKING

```
status_map(2026, week=2, ['DET','BUF'])
  -> BLOCKED  ROSTER_STATUS_EMPTY
     "weekly_rosters.bdab6ecee12d44a4.csv carries no 2026 week 2 rows"
```

`active_roster_only=True` lives in `R5_FLAGS` and is inherited by R6–R13,
including **R9**. Missing evidence about roster *status* was being converted
into a claim that the participant *universe* is empty.

### L2 — the only ACT authority is a post-hoc column that does not exist for week 2

Week-2 **membership** exists (`weekly_rosters.6ff9a4981106676c`, weeks 1 and 2).
Week-2 **status** exists nowhere: one raw blob was retained, week 1 only,
because `durability="reduce"` and `reduce_cols` omits `status`. That week-1 raw
status is `{ACT 1546, DEV 520, INA 187, RET 23, EXE 5, RES 266}` — and `INA` is
a gameday outcome.

### L3 — pool size is the dilution lever, and the board hides it

| | QB | RB | WR | TE | K | skill total | board shows |
|---|---|---|---|---|---|---|---|
| DET | 4 | 6 | 10 | 6 | 1 | **27** | 7 |
| BUF | 3 | 5 | 12 | 4 | 1 | **25** | 7 |

`candidate_mode.py:150` records the mechanism: an unfiltered pool of 22–23 made
the simplex divide by 2.25/2.04, **halving every real starter's share**.

### L4 — WR4+ is one bucket

Tiers: WR1 22.7% / WR2 18.3% / WR3 13.3% / **WR4+ 6.1%**. At cold start the tier
mean *is* the whole forecast. BUF's 4th and 12th receivers get the same anchor.
Real, second-order for Thursday.

### Already handled — not re-litigated

- **depth rank ≠ role**: `depth_vintage` measured that **2,396 of 2,432** WR
  rooms publish no WR1/2/3 order at all ("KC 2023 week 1: the WR1 was the
  returner"). R3 replaced two-pass ordering with one continuous scale.
- **pass snap ≠ route ≠ target**: `role_prior` states participation is "an upper
  bound on routes run". No route layer exists — a real gap, absorbed because the
  class prior is fitted on realised target share.

---

## 3. The repair I proposed first was wrong

> week-2 membership + status unavailable + injury/inactives do the excluding

Injury designations and inactives are statements **about the game roster**. They
say nothing about someone never on it. Measured on the actual week-2 membership,
skill positions:

| | wk2 skill rows | ACT | DEV | RES | INA | CUT | RET |
|---|---|---|---|---|---|---|---|
| DET | 23 | 15 | 5 | 2 | – | – | **1** |
| BUF | 23 | 15 | 4 | 1 | 2 | 1 | – |
| League | 810 | 487 | 173 | 71 | 64 | 3 | 9 |

**DET's week-2 skill membership contains a retired player.** No injury report was
ever going to remove him. That repair would have recreated R5's exact dilution.

---

## 4. What participation actually is

30 teams, 2026 week 1, skill positions, joined
`weekly_rosters.pfr_id -> snap_counts.pfr_player_id`:

| status | n | took an offensive snap | rate |
|---|---|---|---|
| ACT | 417 | 361 | **0.8657** |
| DEV | 120 | 0 | 0 |
| RES | 63 | 0 | 0 |
| CUT | 53 | 0 | 0 |
| RET | 6 | 0 | 0 |
| INA | 62 | 0 | *tautology* |

**Zero of 305 non-ACT skill players took a single offensive snap** — R5's premise
confirmed rather than assumed. And ACT is **0.8657, not 1.0**: 56 of 417 active
players took no offensive snap, which is "ACTIVE ≠ meaningful offensive role"
quantified.

Rates live in `PARTICIPATION_RATE_BY_STATUS.json` with n, source blob sha256s
and the join. No constant is chosen.

---

## 5. The graded chain — and three things it refuses to do

`nfl/production/nonqb/participant_class.py`

- **It does not read INA's 0/62 as a week-2 prior.** That zero is true by
  construction. A week-1 inactive is a 53-man member, so his week-2 class is
  `ACTIVE_ROSTER_EXPECTED` at the ACT rate. Two BUF players are exactly this and
  keep full weight. The injury-persistence adjustment is **not identified** from
  one week and is left unmeasured rather than invented.
- **It does not turn a measured 0/120 into a hard zero.** Every class carries its
  Jeffreys mean — practice squad 0.0041. Small, not a claim of impossibility.
- **It does not resolve UNKNOWN.** Marginal over all members, **0.5000
  [361/722]** — between practice squad and active, decided by neither.

`ELEVATION_CONFIRMED` can never currently be assigned: `official_transactions`
has **no verified endpoint** (459 manifest rows, all
`BLOCKED/ENDPOINT_NOT_YET_VERIFIED`), so authorities 3–5 of the chain are
unavailable. Reported as `elevation_authority: UNAVAILABLE_NO_TRANSACTIONS_ENDPOINT`.

### Result on the real game — `test_participant_class` 27/0

| | members | effective participants |
|---|---|---|
| DET | 23 | **13.08** |
| BUF | 23 | **14.74** |

Against the 14–15 pool R5 was fitted for, **with nobody deleted**. Retired QB
0.0714, nine practice-squad 0.0041, reserve 0.0078, released 0.0093.
WR4/WR5/TE2/RB2 keep full weight on both clubs.

---

## 6. Wiring, and what running it taught

**Three call sites, not one.** `status_map` is read by the non-QB pool, the QB
pool, *and* `eligibility_gate.snapshot`. Repairing one left the other two to
kill the run — the fix looked applied and did nothing.

**The rule.** Roster status is **authority rank 3**. A rank that cannot be read
is an *unavailable authority*, not an empty league. Ranks 1 and 2 still exclude
exactly who they excluded before.

**The same rule at rank 2.** With rank 3 graded, the run died on
`ELIGIBILITY_INJURY_SLICE_EMPTY`. That refusal's reasoning is correct and was
kept — an empty slice is a statement about a capture. But on the Tuesday before
a Thursday game the week's injury report **has not published yet**: an EARLY
vintage, not a broken pipeline.

**An absent authority must be *shaped* like the one it replaces.** My substitute
omitted keys the consumer reads → `KeyError: 'vintage'` inside the appearance
stage, an unnamed crash two layers from its cause. Then I passed a list where a
dict was read. Same lesson twice.

**The weight is now what the defect statement always said.** `candidate_mode`:
*"P4C weights are conditional-on-appearing shares consumed as unconditional
weights."* So `class_point_forecast` multiplies

```
E[share] = P(appears) * E[share | appears]
```

A player with no prior is untouched, so frozen arms keep exact behaviour. Where
supplied, the prior is uniform across the active pool and cancels in
normalisation — active players score identically to the hard filter.

---

## 7. Where DET-BUF stops now

```
capture_validation     PASS             INPUTS_VALIDATED
identity_resolution    PASS             IDENTITY_RESOLVED
feature_build          PASS             STAGE_DECLARED_UNIMPLEMENTED
team_environment       PASS             TEAM_ENVIRONMENT_OK
appearance ... td_layer NOT_APPLICABLE  SLATE_FITS_RAISED
qb_layer               BLOCKED          A1_PBP_SOURCE_NOT_LOCATED
```

Both are **model-layer**, not the eligibility chain. Neither is fixed.

## 8. Not claimed

- DET-BUF produces **no board**.
- The five properties are proven on the **classifier**, not on a simulated
  slate. "All targets/carries have lawful owners" is **unexercised** because the
  engine has not run.
- Participation rates are fitted on **one week of 2026** — a same-week rate with
  **no week-to-week persistence term**. OUT-018's 2023–2025 snap counts would fix
  this.
- The reducer still discards `status`. Retaining it is a `registry.py` change,
  therefore a capture-surface change and a new governed release.

## 9. Next

1. Trace `SLATE_FITS_RAISED` in the non-QB engine.
2. Resolve `A1_PBP_SOURCE_NOT_LOCATED` for 2026 week 2.
3. Re-run DET-BUF; prove target/carry ownership on the simulated slate.
4. Retain `status` in the vintage reduction (governed capture release).
5. Publication states EARLY / PROVISIONAL / NEAR_FINAL / FINAL_PREGAME, so an
   unavailable rank-2 authority downgrades the vintage instead of blanking the
   board.

**V2 NOT YET EARNED**
