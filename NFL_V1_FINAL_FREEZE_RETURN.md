# NFL V1 final engineering closure

**2026-09-10.** Suite **51 modules, 549 test functions, 3,219 checks, 0 failing,
0 raised**. G0A **11/12**. NFL-1 **NOT AUTHORIZED**. `PATH_C_STATE` untouched.
No 2026 outcome consumed for tuning. Nothing promoted.

---

## Verdict

# `V1_REHEARSAL_READY_WITH_NAMED_BLOCKERS`

Both authorized items landed. **Integrating A1 exposed one defect that no
previous rehearsal could see**, and it is an impossible-football state, so the
freeze criteria are not met and I am not declaring
`V1_ENGINEERING_READY_WAITING_ON_G0A`.

## The one blocker

**`SCRAMBLE_CARRY_LEVEL_INCOHERENCE`** — classified **V1_BLOCKER**
(impossible football; production inability to forecast one game).

`team_carries` comes from D1. QB scrambles come from a QB-layer binomial on
dropbacks. They are **drawn independently**, so their tails cross into a state
with more scrambles than total team carries — a negative rush-play budget, and
a team that ran the ball fewer times than its quarterback scrambled.

Measured on the affected game (TB@CIN, m=200):

| team | scrambles mean / max | carries mean / min | impossible cells |
|---|---|---|---|
| TB | 6.740 / 15.0 | 29.00 / 5.3 | 2 / 200 |
| CIN | 4.365 / 17.0 | 22.87 / 8.4 | 1 / 200 |
| | | | **3 of 400 (0.75%)** |

**A1 surfaced this; it did not cause it.** Under the incumbent the same
incoherence was invisible — QB rush simply exceeded the carry pool and the
guard reported it as a rushing violation. A1 refuses by name rather than
clipping, which is the correct behaviour and is why the game does not seal.

**The fix is upstream coupling between the scramble draw and the carry budget.
That is a model change requiring pre-registration, which this ruling does not
authorize, so I did not build it.** OWN-8 already established that scrambles
are *dropback*-owned, so the naive move — making them a share of carries — is
the one thing that is already known to be wrong.

## Freeze checklist, against the ruling's list

| check | result |
|---|---|
| 16/16 games execute | **NO — 14/16 seal** under the candidate; 15/16 baseline |
| 0 hard accounting failures | **YES** on every sealed game (9 HARD PASS, 1 HARD DEFERRED) |
| QB allocation share consumed | **YES** — 0.0% lost |
| exact QB dropback closure | **YES** — integer-exact, worst \|sum − N\| = 0 |
| no composition amplification | **YES** — 0; no ratio is formed |
| pass/receive count-yard-TD identities close | **YES in the engine** (32/32, residual 5.9e-15); **C3 NOT REACHED from the entrypoint** — needs the receiving budget, data-blocked |
| rushing opportunity closes | **YES on 14 games**; refuses by name on the 15th |
| game-coupling checks pass | **YES** — A3G applied, SD(total plays) 9.269 vs historical 9.265 |
| cross-game RNG separated | **YES** — 0.0634, sampling noise |
| lossless draw artifact emitted and replayable | **YES** — sha256 replay identity, shared draw index |
| hard FAILs gate publication | **YES**, demonstrated three times against my own work |
| candidate mode reachable from run_forecast | **YES** — `--model-configuration V1_CANDIDATE` |
| deterministic replay / hash identity | **YES** — 0 of 16 games share a run id across configurations |
| suite green | **YES** — 3,219 checks, 0 failing |
| no 2026 outcomes consumed for tuning | **YES** |

Two refusals are **correct behaviour, not defects**: `SOURCE_CHRONOLOGY_FAILURE`
on the Thursday game, which has now been played and cannot be forecast at a
`written_at` after its kickoff, and the A1 refusal above.

## What the candidate configuration is

`nfl/production/candidate_mode.py` — one readable table, not booleans threaded
through call sites. A component with no row cannot be switched on; an unknown
mode name is **refused**, never defaulted to the baseline, because defaulting
would run the *promoted* model while the operator believed they were running
the candidate. Applied on the slate: **A1, A3G, C0, R2**. Not reached: **C3**.

The masquerade guard runs at the seal on the assembled artifact, so it cannot
be satisfied by an invocation-time flag a later edit forgets to carry.

## Three defects of mine, all caught by running rather than by review

1. The candidate path emitted no verdicts for three declared HARD invariants —
   B14's gate refused all 16 games with `INVARIANT_VERDICT_MISSING`.
2. I declared `rushing_single_owner` HARD **globally**, so the baseline — which
   has no A1 to evaluate — then refused every game the same way. A
   configuration that cannot evaluate a declared invariant still owes it a
   verdict: `NOT_APPLICABLE` with a reason, never silence.
3. The candidate path routed `QB_SLATE_EMPTY` through `RF.refuse`, inventing an
   undeclared production refusal code — caught by the suite's own "every
   refusal code raised in the production path is declared" check.

Also repaired: `test_preflight` asserted the literal `2026_01_NE_SEA` as the
first upcoming game, so the suite began failing on the passage of time once
that game kicked off. It now asserts the property, not the calendar.

## Two debts the A1 module declared, both closed

1. **Seed registry.** `rushing_a1` was not a declared namespace in `seeds.py`,
   so the stream fell back to a sha256 derivation — deterministic across
   processes, never a correctness problem, but a closed set belongs in the
   readable table. Declared; `registry_debt()` now returns
   `PASS[A1_SEED_NAMESPACE_DECLARED]`.

2. **Parameter reproducibility.** The frozen parameters lived only in the
   gitignored `nfl/derived/`, and the six pbp files a refit needs are **not in
   this repository** — so a fresh checkout had neither the parameters nor the
   means of rebuilding them. That is the shape of the failure that left the
   sibling project's M0 baseline permanently non-reproducible. The frozen file
   is now committed gzipped (193 KB, json sha256 `9d56c260…`) beside the
   module, and `params()` falls back to it: verified by removing the cache and
   loading from the committed copy. **A refit still needs pbp**, and
   `pbp_sources()` still BLOCKS by name without it — that debt is real,
   remains open, and is not papered over by the fallback.

## What would close V1

One thing: **couple the QB scramble count to the carry budget it must fit
inside.** It needs a pre-registration and an authorization. Everything else on
the ruling's checklist passes, and the remaining limitations — the injury feed
at 2 of 32 teams, and G0A item 1 — are external.

`RUSHING_CONVERSION_CONTROL_UNDEFINED` remains in force; carry ownership being
coherent is not a reason to build a rushing-yard model, and none was built.
A2 was not reopened.
