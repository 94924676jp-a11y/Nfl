# Suite attribution: e050090 → 3270829

**Seven newly-introduced items. One cause. Fixed.** Everything else red was
already red, and none of it was touched.

## Totals

| | baseline `e050090` | current `3270829` | delta |
|---|---:|---:|---:|
| modules | 169 | 178 | **+9** |
| test functions | 1,831 | 1,914 | **+83** |
| checks | 9,940 | 10,222 | **+282** |
| failing checks | 62 | 64 | **+2** |
| raised | 22 | 26 | **+4** |
| zero-check functions | 1 | 1 | 0 |
| blocked functions | 22 | 22 | 0 |
| verdict | SUITE FAIL | SUITE FAIL | — |

## Classification

| class | n |
|---|---:|
| PRE_EXISTING | 136 |
| NEWLY_INTRODUCED | 7 |
| RESOLVED_SINCE_BASELINE | 0 |
| CHANGED_CLASSIFICATION | 0 |
| ENVIRONMENTAL | 0 |

By kind: failing checks 62 pre-existing / 2 new; raised 22 / 4; module-level
failures 29 / 1; blocked 22 / 0; zero-check 1 / 0.

## The one cause

All seven trace to a single site:

```
nfl/production/assumptions/registry.py  →  OWNERSHIP_AUDIT_UNREVIEWED_SITE
  ('opponent_pass_strength_v1', 'nfl/production/assumptions/registry.py')
  ('opponent_rush_strength_v1', 'nfl/production/assumptions/registry.py')
```

Introduced by **`5e602b4`** (Automatic Scientist v0). `A3_ROLE_CONTINUITY_
ACROSS_REGIME_CHANGE` names `nfl.research.oas1.baselines` in its
`downstream_dependencies`, so a falsified role-continuity assumption is known
to reach OAS1's priors. The ownership audit's component matcher saw the token
`oas1`, classified the file an application candidate, found no disposition,
and failed — taking `test_ownership_audit` (2 failing checks, 3 raised, 1
module entry) and `test_gate_ids::test_C` (1 raised) with it.

**Both modules existed at baseline and passed there.** My work broke them.

### Resolution: read the site, record the disposition

This is the audit's designed workflow — *"A site nobody has opened is not a
clean site. Read it and record what it does in DISPOSITIONS."* — and it is the
**second** time the gate has fired on the next file written after it was
built. The first was `gate_ids.py`, dispositioned `DECLARATION_NOT_APPLICATION`
for the same reason.

Read: the only match is the literal string `"nfl.research.oas1.baselines"`
inside a `downstream_dependencies` tuple. The module builds frozen
`Assumption` records; it imports only `assumption` and `outcome`, holds no
frame, computes no estimate, reads no strength. The token is the **name of a
consumer a falsified assumption would block** — the opposite of applying an
adjustment.

Recorded as `DECLARATION_NOT_APPLICATION` with that evidence and a read date.
Audit now `PASS[OWNERSHIP_AUDIT_COMPLETE]`; `test_ownership_audit` 47/0,
`test_gate_ids` 26/0.

**The audit was not weakened and no rule was added to skip declarative files.**
A rule that skipped files that look declarative would skip the next real
applier that happens to look that way too.

## The zero-check case, named

`nfl/tests/test_participant_class.py::test_d_a_week_one_inactive_is_not_a_week_two_exclusion`

It reaches its second guard — no member of the classified week-2 output
carries an `INA` status basis in this game — and declares
`NOT_EXECUTED week-1 INA carry-forward`. It recorded that in its own
module-level `NOT_EXECUTED` list. **`run_suite.blocked_tally` reads only an
integer named `BLOCKED`, `blocked_count` or `SKIPPED`, and this module exposed
none of them.**

So it was a **declaration-channel mismatch, not a silent skip**: the module
did say it had not run, in a channel the runner does not read.

Repair: `BLOCKED` is now an integer that `not_executed()` increments. The
runner confirms `ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 1` for that module.
This is not suppression — the count still shows in the summary, the reason
still prints, and a function that records nothing **without** declaring it
still lands as zero-check, because `not_executed` is the only thing that moves
the number.

It was **PRE_EXISTING**: present at both commits, unchanged by any work in
this session.

## Two methodology defects in my own tooling, caught and fixed

Both would have produced a false attribution, and both are recorded rather
than quietly corrected.

**1. Worktree paths read as regressions.** The first classification reported 9
newly-introduced items and 2 resolved. Four of those were one unchanged check
each, keyed differently because the two runs print their own checkout root —
a phantom regression and a phantom repair from the same untouched check.
`suite_diff` now collapses declared roots to `<ROOT>` before keying.

**2. "New module" was inferred from silence.** The flag meant "produced no
items at baseline", which is what a **passing** module looks like. It labelled
`test_ownership_audit.py` a new module and would have excused a real
regression as the arrival of new code. It now asks **git** for the baseline
tree, and refuses to guess if it cannot.

## Environment: the first run pair was not comparable, and was discarded

The first attempt ran both suites in parallel worktrees and produced baseline
RAISED 64 / current 68 against 22 in the main checkout. 37 of those were four
modules failing on `nfl_vintage/raw/weekly_rosters.*.csv` — a **gitignored**
data directory present in the main checkout and absent from a fresh worktree.

Those logs were **discarded, not classified**. The 37 ignored non-`__pycache__`
artifacts (329 MB) were copied into both worktrees and the pair was re-run
**serially**, removing the contention question as well. The serial pair
reconciles with the main-checkout run: baseline RAISED 22, zero-check 1,
blocked 22 — matching exactly.

`board.json` is missing in **all three** checkouts including main, so
`test_draw_coherence`'s three raises are a genuine pre-existing repository
state, not a worktree artefact.

## The parser refuses to understate

`suite_diff.parse` reconciles its parsed item counts against `run_suite`'s own
header totals and **refuses to diff** on a mismatch. A parser that silently
drops items produces a diff that silently understates a regression, which is
precisely what this exercise exists to prevent. Both logs reconcile exactly.

## Do P0–P5 and A1–A2 remain valid?

**Yes, all of them.** The attribution touches no measurement:

| work | status after attribution |
|---|---|
| P0 review freeze | valid — artifact only |
| P1 solver legality | valid — `test_showdown_site_legality` 12/0, DP proved against brute force |
| P2 universe contract | valid — 30/0 |
| P3 kicker identity | valid — resolved by gsis_id, unaffected |
| P4 CS2 | valid — 33/0, forward chain untouched |
| P5 game coupling | valid — 27/0, measurement reproducible |
| A1 | valid — 1,585/1,702, falsification stands |
| A2 | valid — 1,257 events, falsification stands |

The single regression was a **governance guard firing on a dependency
declaration**. It changed no projection, no draw, no score and no measurement.

**V2 NOT YET EARNED**
