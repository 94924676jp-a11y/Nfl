# P9 — target ownership closure and the receiving/pass-event identity

Items 1.11 and 1.12. Measured 2026-09-15 on every sealed board in this
repository. `python3.12`. Nothing committed, nothing pushed.

---

## 0. Verdict, before the detail

| question | verdict |
|---|---|
| **A.** Does the target partition close? | **YES, by construction**, against the level the game consumed. 113 sealed C3 team-runs, 139,800 draws, residual never negative, minimum `0.0000`. |
| **A.** Does it close against the level **the board publishes**? | **NO, and it cannot.** The published level is a different quantity and three of the four vectors of the identity are not sealed at all. |
| **A.** Is the prior `stored_team_targets_is_not_the_denominator` finding the defect? | **NO — it is a mis-specified comparison when read as a closure test.** Its two sides are a published-but-unused draw and the throw budget; neither is the partitioned level, and the check never gated. Its own name says so. |
| **B.** Does the C3 pass-event identity hold per draw? | **YES.** Receptions vs completions and receiving TD vs passing TD are exact — 0 violating cells in 139,800 draws, worst \|diff\| `0`. Receiving yards vs passing yards is exact to `1.1369e-13`, float summation order. |
| **B.** Is anything on the receiving side incoherent? | **NO.** 2,005,800 player-draw cells: zero receptions above targets, zero receiving TDs above receptions, zero yards on zero receptions. |
| What *is* incoherent | The **quarterback** side of pre-R9 boards, from the superseded `credit_to_passers`. R9 and R11 boards carry **zero**. That is P4's finding and P4's repair; reproduced here, not claimed. |

**Two outcomes the brief asked for explicitly, and both happened.** A reported
defect turned out to be a mis-specified comparison (§2). And underneath it
there is a real, separate, previously unstated defect (§3) — which is the
receiving analogue of R11's **third** rush cause and **only** the third.

---

## 1. What was measured, and on what

`nfl/research/v4/p9/P9_TARGET_CLOSURE_MEASUREMENT.json` carries every number
below, per team-run. The frame is every sealed run under `nfl/research/`
carrying `player_draws.npz`, a manifest, a board and a forecast artifact,
whose **own declaration** (`candidate_components_applied`) says C3 was live and
which carries a receiving layer. Regime is read, never inferred.

    169 run directories with draws
    127 evaluable by nfl/product/conservation
    113 team-runs declaring C3 with both sides of the passing event
    139,800 draws
    2,005,800 receiver player-draw cells

Named cohort board for the per-team reproduction:
`nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R9/96954efc523bd7d3`
— the same board P3 used for the rush repair, used here as a **fixture of the
measurement**, never as a scoreboard. No realized DEN@KC outcome appears
anywhere in this work; it is not in this repository.

---

## 2. Question A, part one: the reported defect is a mis-specified comparison

The prior measurement is `stored_team_targets_is_not_the_denominator`:
`team_volume/team_targets` agrees with the C3 budget in **0 of 100,000 draws
across 68 team-runs**, reproducing WS09 J-12
(`nfl/research/v2/d6/D6_CONSERVATION_DASHBOARD.md:291`). On the larger frame
here it reproduces again: **0 of 139,800**.

**Read as "the target partition does not close", that comparison is
mis-specified, and in two independent ways.**

1. **Its left-hand side is not the denominator.** `team_volume/team_targets`
   is D1's own, separately drawn, *continuous* team target level. Under C3
   nothing consumes it. `football_engine.run_game` says so in its own evidence
   block — `'d1_team_targets_unused': True`, `football_engine.py:882`.
2. **Its right-hand side is not the denominator either.**
   `conservation.target_view` compares against `rint(sum qb/att)`, which is
   `throws`. The partition was dealt from `targeted = throws − untargeted`.
   So the check compares an unused quantity against the *parent* of the
   consumed one.

The check is nonetheless **correctly specified for what its name claims** — it
is a gauge on a second, published, unused owner, it is classed `RESIDUAL`, and
it gates nothing. D6 already states this in its "Trap 1" and enforces it
behaviourally: the dashboard test triples `team_volume/team_targets` and
requires every target record to come back bit-identical. **Nothing here
disputes that check. What is withdrawn is reading it as evidence that target
ownership fails to close.**

**Against the level the partition actually consumed, it closes, and the
containment is not marginal.**

| quantity | result |
|---|---|
| draws where `sum(named targets) > rint(sum qb/att)` | **0 / 139,800** |
| minimum residual `throws − sum(targets)` | **+0.0000** |
| mean residual | **+1.7651** |
| team-runs | 113 |

This is a construction, not luck. `shared_pass.deal_targets` hands an integer
targeted-throw budget to a multinomial over the receivers plus the named
`other` pool, so `sum_i T_i + other == targeted` holds per team per draw
exactly; `football_engine.run_game` asserts it and **halts** if it ever does
not (`C3_TARGET_COUNT_DOES_NOT_CLOSE`). The non-C3 branch has since been
brought onto the same construction via `stat_contract.deal_counts`, so a
target is dealt rather than multiplied on both paths.

**The three rush failure modes, checked one at a time.**

| rush cause | receiving analogue | verdict |
|---|---|---|
| 1. coupling bound constrained the wrong quantity | the budget is the **whole** throw process (`rint(sum att)`), not a sub-component of it | **absent** |
| 2. two owners for one quantity, both live | D1's `team_targets` and the throw process both claim team targets — but D1's is **inert** under C3, where A1's `designed_qb` was not | **present and inert** |
| 3. published level ≠ partitioned level | see §3 | **present, and it is the finding** |

---

## 3. Question A, part two: the real defect, which is a publication defect

`run_forecast` seals `team_volume/team_targets` — the unused continuous draw —
under a name that asserts it is the team's targets, and seals **nothing** of
the level that was partitioned.

**Measured across the same 113 team-runs / 139,800 draws:**

| | |
|---|--:|
| `sum(named receivers' targets) == published team_targets`, exactly | **0 / 139,800** |
| `... == rint(published)`, exactly | 10,849 / 139,800 |
| `...` **exceeds** the published level | **71,550 / 139,800 (51.18%)** |
| worst per-draw excess over the published level | **+28.6291** |
| worst per-draw shortfall | −30.9651 |

**On the named cohort board** (`96954efc523bd7d3`, 1,000 draws):

| team | mean named targets | mean published level | draws over published | max excess | exact | residual vs consumed budget |
|---|--:|--:|--:|--:|--:|--:|
| DEN | 31.6080 | 33.7495 | **298 / 1000** | **+10.6326** | 0 | min +0.0000, mean +1.7210 |
| KC | 34.7630 | 28.7035 | **926 / 1000** | **+19.0395** | 0 | min +0.0000, mean +1.8700 |

The published level is also not an integer: it is a continuous draw sealed
under a count's name, which is the same shape of defect `stat_contract` was
written to end on the R4 target path.

**Why this is worse than a mislabelled column.** Three of the four vectors of
the identity are absent from **every** board in this repository — verified,
not assumed, in `test_c` below:

    throws == untargeted + sum_i targets_i + other      (per team, per draw)
      throws      recoverable as rint(sum qb/att)        SEALED (derivable)
      targets     receiving/targets                      SEALED
      targeted    the level the partition consumed       NOT SEALED
      untargeted  the named throwaway/spike pool         NOT SEALED
      other       the unmodelled-receiver pool           NOT SEALED

So a consumer cannot recover the right denominator even after being told which
one it is. Only the **weak** form `sum(targets) <= throws` is checkable from a
board; the exact identity is not. D6 already names this gap as the ABSENT
contract `team_target_pool_membership` — "neither vector is sealed". This
report supplies the size of what that gap hides.

**Is it live?** Not today, and that is stated rather than left for a reader to
find. `nfl/product/board.py:_shares` divides a receiver's targets by the
**modelled pool**, not by the published team level, so the printed target share
is not affected. `nfl/research/postgame.py` refuses the
`team_volume/team_targets` estimand by name (`ESTIMAND_UNVERIFIED`). The defect
is **latent**: any consumer who does the obvious thing — divide by the level
named "team targets" — gets a target share above 1.0 in half the draws.

---

## 4. Question B: the receiving/pass-event identity closes

Reported **separately per quantity**, because a single pass/fail over three
quantities is what hides the one that moved.

| identity | violating cells | worst \|diff\| |
|---|--:|--:|
| team receptions vs team completions | **0 / 139,800** | **0** |
| team receiving TD vs team passing TD | **0 / 139,800** | **0** |
| team receiving yards vs team passing yards | **0 / 139,800** | **1.13687e-13** |

The yards residual is float summation order over a different row count on
integer-valued yardage — it reproduces the `1.1e-13` the P4 credit migration
reported, and it is not a modelling deviation.

**Receiving-side per-player coherence**, 2,005,800 cells:

| property | violating |
|---|--:|
| receptions ≤ targets | **0** |
| receiving TD ≤ receptions | **0** |
| receiving yards on zero receptions | **0** |

**What is incoherent, and whose it is.** The quarterback side: 7,407 cells with
`cmp > att`, 8,291 with `cmp + int > att`, 1,003 with `ptd > cmp`, 16,133 with
passing yards on zero completions. Split by configuration:

| mode | runs | incoherent QB cells |
|---|--:|--:|
| V1_CANDIDATE | 4 | 2,371 |
| V1_CANDIDATE_R5 | 4 | 2,340 |
| V1_CANDIDATE_R6 | 4 | 2,345 |
| V1_CANDIDATE_R7 | 4 | 2,363 |
| V1_CANDIDATE_R8 | 31 | 23,415 |
| **V1_CANDIDATE_R9** | 11 | **0** |
| **V1_CANDIDATE_R11** | 1 | **0** |

Every affected board was built by the superseded
`shared_pass.credit_to_passers`; `football_engine.credit_passing_line` replaced
it at the R9 rebuild and carries zero. **This is P4's finding and P4's repair.**
It is reproduced here so P9 does not claim it, and so that a future reader sees
the replacement verified by measurement rather than by docstring.

---

## 5. What landed, and it changes no drawn value

Two additions to `nfl/production/nonqb/shared_pass.py` — 252 insertions, and
the one deletion is the import line. Nothing existing was modified.

**`compose_pass_event_ownership(...)`** — the composition point, in one named
function with one owner, mirroring `rushing_a1.compose_rush_ownership`.
`targeted_throws` and `deal_targets` were already correct and are called here
**unchanged**, in the same order, on the same generator; the composed output is
asserted bit-identical to the uncomposed deal. What did not exist was a single
place holding all four vectors of the identity at once and naming which of them
a board must publish — and the two halves are already one step from drifting,
because `football_engine` keeps `tgt_vol` and `c3_other` as locals, reduces
them to means for its evidence block, and discards the vectors.

It returns `published_level = targeted`, and asserts **both halves separately**
(`sum_i targets_i + other == targeted`, and `targeted + untargeted == throws`)
so a failure names the half it is in.

**`assert_target_ownership_closure(...)`** — the decomposed fence, mirroring
`rushing_a1.assert_named_owner_containment`. It returns every series it
measured, always: `named_only`, `named_plus_other`, `full_partition`, plus
whether the level is integral and whether each pool was supplied at all.
Tolerance defaults to **zero**. It repairs nothing; it counts and it names.

Plus `PUBLISHED_TARGET_LEVEL_STATUS`, `TARGET_IDENTITY` and
`TARGET_VECTORS_NOT_SEALED`, so the finding lives in the module a future reader
opens first rather than only in this report.

**No clip, no truncation, no renormalisation, no deleted draw, no constant.**

### Blast radius: zero, and proven rather than argued

`grep` confirms **no production call site** for any new name. The trial build
run under the mandated command:

    python3.12 /tmp/run_tonight.py 2026-09-14T23:27:47Z \
        nfl/research/v4/p9/trial_after 1000 V1_CANDIDATE_R9
    status SEALED   run_id 06a25b4655c08474   163.0s

| | before (sealed `96954efc523bd7d3`) | after (trial `06a25b4655c08474`) |
|---|---|---|
| `draw_content_digest` | `31455f2c617af10b…` | **`31455f2c617af10b…` identical** |
| arrays differing | — | **none, all 29 bit-identical** |
| DEN mean targets / receptions / recv yards | 31.6080 / 21.4500 / 225.0080 | **identical** |
| KC mean targets / receptions / recv yards | 34.7630 / 24.0560 / 259.3240 | **identical** |
| completion marginal (DEN / KC) | 21.4500 / 24.0560 | **identical** |
| `sum(cmp) == sum(receptions)` every draw | yes | **yes** |
| draws over published level (DEN / KC) | 298 / 926 | **298 / 926 — unchanged** |
| negative residual vs consumed budget | 0 / 0 | **0 / 0** |

The violation counts are **unchanged** because nothing was repaired yet — see
§6. What is established is that the diagnostic landed without moving a number.

---

## 6. What did NOT land, and why — this needs a decision

**The repair is three lines of composition in files this workstream may not
edit.** Publishing the level that was partitioned requires, exactly:

1. `nfl/production/nonqb/football_engine.py` — `run_game` already computes
   `tgt_vol` (the targeted budget), `c3_other` and each team's `untargeted`
   vector at lines ~845-880. It reduces them to **means** for the `c3` evidence
   block and discards the vectors. It would need to return them, ideally by
   calling `shared_pass.compose_pass_event_ownership` in place of the two
   separate calls, and to set `_published_team_targets`.
2. `nfl/production/run_forecast.py` — one override beside the existing R11
   block at `run_forecast.py:1811-1834` (`_published_team_carries`), plus a
   `pass_event` layer seal beside `rush_player_pool` carrying `targeted`,
   `untargeted` and `other` with `row_axis='team'`.
3. `nfl/production/candidate_mode.py` — this changes what the board publishes
   and therefore needs a **new successor candidate, R13**, inheriting R9 and
   not R10/R11/R12, registered additively exactly as R11 was.

All three are on this workstream's do-not-edit list, and two other agents are
running. **Stopping here rather than editing them.** The instruction to
register a successor candidate and the instruction not to edit
`candidate_mode.py` cannot both be followed; the explicit prohibition wins and
the conflict is reported instead of resolved unilaterally.

**The shape R13 should take, so whoever holds those files does not re-derive
it.** It is a strictly smaller repair than R11 was — one cause, not three:

    published_team_targets := targeted          # what the multinomial dealt from
    seal pass_event/targeted, /untargeted, /other

and then, because `deal_targets` partitions an integer budget,

    sum_i targets_i + other == published        in every draw
    sum_i targets_i         <= published        in every draw, no clip

Under C3 that substitution **changes the published team-target marginal** —
from D1's continuous draw to the throw process's integer budget — so it is a
new configuration identity and not an edit to R9. It changes no receiver's
targets, no reception, no yard and no completion: the partition already
consumed the new level.

**Two open items, named rather than smoothed.**

- The non-C3 path deals from `integerise_level(team_volume/team_targets)`, so
  its published-vs-partitioned gap is a bounded rounding residual rather than a
  different quantity. **No sealed board in this repository exercises it with a
  receiving layer** — every board that has receivers ran C3 — so that branch is
  unmeasured here, not clean.
- `product/board.py:_shares` labels a share of the **modelled** target pool as
  `share_of_game_pool`. With unowned mass at ~5.3% of the throw budget, that
  label overstates what it names. It is a different file, a different owner,
  and not touched.

---

## 7. Tests

`nfl/tests/test_p9_target_closure.py`, 12 functions, **42 checks, 0 failing,
0 blocked, 0 zero-check functions.**

    python3.12 nfl/tests/run_suite.py --only test_p9_target_closure
    SUITE PASS

Decomposed so each check names **which quantity** and **which side**:

| | |
|---|---|
| A | reproduction, publication side — named receivers exceed the published level, per team, at its measured size |
| B | reproduction, allocation side — containment against the **consumed** level holds in 139,800/139,800 draws |
| C | the gap — no board carries `targeted`, `untargeted` or `other` |
| D | the composition closes **both halves** by construction, on synthetic inputs no corpus contains |
| E | `published_level` IS the partitioned level, and is integral |
| F | the composition is bit-identical to the uncomposed deal — clips and renormalises nothing |
| G | **bypass**: the fence REFUSES a seeded one-target breach, and names `full_partition` and exactly one draw |
| H | the fence run on the sealed board as a consumer would, and what it says |
| I | the three C3 identities, reported separately |
| J | receiving-side per-player coherence |
| K | passer-line incoherence confined to pre-R9 boards |
| L | the module states the defect by name |

**Shown failing first.** D, E, F, G, H, C and L were run against
`git show HEAD:nfl/production/nonqb/shared_pass.py` loaded under the production
module name. All seven fail with `AttributeError` on
`compose_pass_event_ownership`, `assert_target_ownership_closure`,
`TARGET_VECTORS_NOT_SEALED` and `PUBLISHED_TARGET_LEVEL_STATUS`. A and B are
reproductions and pass in both states by design: a board sealed before a repair
does not stop carrying what it carried.

### Every suite that imports `shared_pass`

| suite | result | attributable to this work? |
|---|---|---|
| `test_xl1_shared_pass` | **PASS** — 17 functions, 115 checks, 0 failing | — |
| `test_governance_transport` | **PASS** — 23 functions, 74 checks, 0 failing | — |
| `test_appearance_team_scope` | **PASS** (1 declared BLOCKED) | — |
| `test_p9_target_closure` | **PASS** — 42 checks | new |
| `test_passer_credit_migration` | FAIL, 3 checks | **no** — P4 recorded exactly 3 after its migration, "all three declared residuals owned elsewhere"; `rushing_td <= carries` is its documented 442 |
| `test_draw_coherence` | FAIL, 9 checks | **no** — P3 and P4 both record 9, unchanged |
| `test_conservation` | FAIL, 6 checks | **no** — P3 records 6, unchanged; failures are `CONSERVATION_RUN_INCOMPLETE` on run dirs other agents are writing |
| `test_product_orchestration` | FAIL, 1 check (`the reproduction run sealed REFUSED`) | **no** — it rebuilds the latest `WRITTEN` row of a shared board index two other agents are writing concurrently; the index read back 0 WRITTEN rows minutes later |

The construction argument is stronger than the reruns and is stated plainly:
the diff is **252 insertions and one import line**, and `grep` finds **no call
site** for any new name outside this module and its own test. Nothing existing
can behave differently.

---

## 8. Integrity

| | |
|---|---|
| `nfl/production/nonqb/layers.py` | `481f005f682cd721…` at start **and at end** — unchanged |
| `board_pointer.verify_seal('V1_SEALED')` | `PASS[SEAL_INTACT]` |
| `board_pointer.verify_seal('MNF_REBUILD')` | `BLOCKED[SEAL_NOT_REGISTERED]` — pre-existing, no path registered |
| files written | `shared_pass.py`, `test_p9_target_closure.py`, `research/v4/p9/*` |
| `nfl/research/live/` | not written |
| commits / pushes | none |
| market data, external projections | none consulted |
| DEN@KC realized outcome | not in this repository, not sought, not used |

---

## 9. One sentence

The receiving target partition closes exactly against the level it consumed and
the C3 passing identity holds to the bit; what does not close is a number the
board publishes and nothing partitions, and the check that has been flagging
this for three workstreams was measuring the right gap under a reading that
made it look like the wrong defect.
