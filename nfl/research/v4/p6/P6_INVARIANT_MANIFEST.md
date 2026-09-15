# P6 — the invariant-execution manifest, and the false-green census

    Repo          /home/user/nfl @ 64783d0 (working tree modified by six concurrent agents;
                  see Evidence ceiling)
    Interpreter   python3.12
    Date          2026-09-15
    Scope         Phase 9 Part A (manifest) and Phase 1 Part B (false greens)
    Built         nfl/tools/invariant_manifest.py, nfl/tests/test_p6_false_greens.py
    Changed       NOTHING under nfl/production, nfl/product, nfl/research,
                  nfl/prospective, nfl/capture, nfl/ingest or nfl/identity.
                  run_suite.py is unmodified. No seal was written or moved.

The governing rule this work is built around, from the directive:

> **A blocked/refused invariant counts as failure to certify, never success.**

Everything below follows from taking that literally. "It did not fail" and "it
was evaluated and held" are different statements, and a measurement system that
renders them the same colour will eventually tell you a bad model is a good one.

---

## Part A — the invariant-execution manifest

### The gap it closes

`nfl/tests/run_suite.py` already does two things well and they are not this
one. It reads each module's own tally, so a printing `check()` that fails turns
the suite red. And since WS11 it reads the tally around **every test function**,
so a function that returns before its first check is named as a ZERO-CHECK
FUNCTION and fails the suite. That closes *the whole test went missing*.

It does not close the smaller and far more common thing:

> a test function that runs, records eleven checks, passes, and never reaches
> the two checks that were the reason it was written.

An early `return` after some checks, a `for` loop over a collection that came
back empty, an `if fr.state is State.PASS:` arm that did not fire — in every
one of those the function's tally still moves, so the function is not
zero-check, so the runner is satisfied, and the suite is green. **The invariant
was declared in the source and was never evaluated, and nothing in this
repository said so.**

Calibration, run against a seeded module and then removed:

    def test_silently_skips():
        check('the first property', True)
        if not ROWS:
            return
        check('THE PROPERTY THIS TEST EXISTS FOR', len(ROWS) > 0)

    $ python3.12 nfl/tests/run_suite.py --only test_zzz_p6_probe
      modules 1  test functions 2  checks 1  FAILING CHECKS 0  RAISED 0
      ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 0
      SUITE PASS

    $ python3.12 nfl/tools/invariant_manifest.py --only test_zzz_p6_probe
      R1_CHECK_SITE   2 declared   1 CERTIFIED   1 NOT_CERTIFIED
      FAILURE TO CERTIFY: nfl/tests/test_zzz_p6_probe.py:18
                          THE PROPERTY THIS TEST EXISTS FOR
      MANIFEST FAILURE_TO_CERTIFY

### Design: three registers, none of them hand-written

A hand-written list of invariants goes stale the moment one is added, and then
certifies a system it no longer describes. Every register is derived from the
repository's own declarations.

**R1 — check sites.** Every `check(...)` and `blocked(...)` call site in every
test module, located by AST with its full line span, its enclosing function and
its label literal. That is this repository's own vocabulary for "here is a
property I claim to enforce"; all 126 test modules discovered on this run
define `check` and carry a tally, so the coverage is total. Each module is then imported and its `check`
and `blocked` replaced by recorders that read the module's tally before and
after the real call and attribute the verdict to the caller's line. Declared
minus executed is the answer, **at check-site granularity** rather than
function granularity.

**R2 — refusal codes.** Every non-PASS `Outcome` code constructed anywhere in
the shipping tree — `Outcome.fail`, `.blocked`, `.deferred`, `.not_applicable`
— is a guard the system claims to have. `Outcome.__post_init__` is patched
**once, before any test module is imported**, so every Outcome built anywhere
during the run records its own code and state. A declared refusal code that no
test caused to be constructed is a guard no test has seen fire. CLAUDE.md rule
4: "A guard is not demonstrated because compliant data passes it."

**R3 — load-bearing guards.** Every `(module_path, attr)` pair passed to
`nfl/tests/bypass.py`, with `guard_bypassed` patched to record. A declared
bypass proof that stopped running becomes visible.

The patch ordering in R2/R3 is load-bearing and is commented as such: a test
module that does `from nfl.tests.bypass import guard_bypassed` binds the name
at import time, so a patch applied afterwards would record the guard as never
used — a false NOT_CERTIFIED, which is this audit committing its own defect in
reverse.

### The verdict vocabulary

    CERTIFIED       declared, executed, and it passed
    FAILED          declared, executed, and it failed
    BLOCKED         declared, executed, and it said out loud it could not run
    NOT_CERTIFIED   declared and NEVER EXECUTED on this run
    NEGATIVE_ARM    a site whose verdict argument is the literal False
    BLOCKED_ARM_NOT_TAKEN
                    a `blocked(...)` site that did not fire: the fixture WAS
                    there and the real checks ran
    BLOCKED_BRANCH  a site in a function where a `blocked()` DID fire: the
                    untaken half of a declared either/or

**NOT_CERTIFIED is distinct from both PASS and FAIL**, which is what the
directive asks for. BLOCKED and NOT_CERTIFIED are both failures to certify and
are reported apart because they are different defects: BLOCKED is honest and
NOT_CERTIFIED is silent, and the silent one is the reason the tool exists.

`NEGATIVE_ARM` exists so the tool does not manufacture the defect it hunts.
This shape is everywhere in the suite:

    try:
        R.pbp_path(2026)
        check('pbp_path(2026) refuses', False, 'it returned')
    except R.ChronologyError:
        check('pbp_path(2026) refuses', True)

The `False` site is written to be unreachable while the guard works, so calling
it NOT_CERTIFIED would mark a correctly refusing guard as uncertified. A site
whose verdict argument is the literal `False` is counted apart; if it *does*
execute it records a real FAILED, which is the point of it. Both arms missing
still shows, because the positive arm is an ordinary site.

### The gate, and why it is shaped this way

Exit 1 when any R1 check site or R3 bypass proof is NOT_CERTIFIED or FAILED.
BLOCKED alone exits 0 — printed and carried in the JSON, but a runner that
turned a declared block red would push authors back toward the silent return,
which is the defect the whole tool exists to end.

**R2 is reported and not gated unless `--strict-refusals` is passed, and that
is a judgement worth stating rather than burying.** Most of the several hundred
named refusal codes guard a data condition no test can currently produce, so a
gate including them would be red on the day it was written and stay red, and a
gate that is always red is a gate nobody reads. The number is printed either
way and it *is* a failure to certify. This is a decision about what a runner
blocks on, not a claim that the rest are fine.

`--baseline PREVIOUS.json` switches to regression mode: exit non-zero only for
an invariant that was CERTIFIED or BLOCKED in the baseline and is not certified
now. **That is the form to wire into a workflow.** It lets the standing census
be worked down while making it impossible for a check that executes today to
stop executing in silence tomorrow. The first full run below is the baseline;
it is written to `nfl/research/v4/p6/INVARIANT_MANIFEST.json`.

### What the manifest is not

It is not a coverage tool and it does not measure the production line. A check
site that executed proves only that the assertion was **evaluated** — not that
it was a good assertion. **Executing a tautology records CERTIFIED.** Every
finding in Part B would still be CERTIFIED by this tool. The two halves of this
work are complementary and neither substitutes for the other: the manifest
answers *was it run*, and the census answers *was it worth running*.

### The first full run

    $ python3.12 nfl/tools/invariant_manifest.py -v
      126 modules, 2026-09-15 05:11-05:44 UTC

    register          declared CERTIFIED FAILED BLOCKED NOT_CERT  not-taken
    R1_CHECK_SITE         6783      6291     31       6       57        398
    R2_REFUSAL_CODE        823       446      0       0      377          0
    R3_LOAD_BEARING         52        51      0       0        1          0
    TOTAL                 7658      6788     31       6      435        398

    MANIFEST FAILURE_TO_CERTIFY
    wrote nfl/research/v4/p6/INVARIANT_MANIFEST.json

`not-taken` is the three declared-either-or classes counted apart:
`NEGATIVE_ARM` (232), `BLOCKED_ARM_NOT_TAKEN` (163) and `BLOCKED_BRANCH` (3).

**The two arm classes were added after this run and applied to its rows without
re-executing anything**, and the JSON says so in a `relabelled` field. No
verdict changed; only the name given to a site that never executed. They matter
because on the first pass **163 of the 223 apparent failures to certify were a
`blocked(...)` site that did not fire** — which means the fixture WAS there and
the real checks ran. Counting those would have buried the 57 that are real
under three times their number of noise, and a headline that cries wolf is how
a measurement tool stops being read. The rule for crediting them is the
repository's own escape hatch and nothing softer: a site is only excused when
it is itself a `blocked()` call, or sits in a function where a `blocked()`
actually fired **on this run**. A function that returned silently gets nothing.

### What the first run found

**57 check sites were declared and never evaluated**, and nothing else in the
repository would have said so. They concentrate:

| Module | Never-executed `check()` sites |
|---|---|
| `test_appearance_team_scope.py` | 16 |
| `test_accounting_invariants.py` | 7 |
| `test_preflight.py` | 6 |
| `test_product_orchestration.py` | 6 |
| `test_injury_parser.py` | 3 |
| eleven other modules | 1-2 each |

`test_appearance_team_scope.py` is the shape to read first, because it is
honest and still loses coverage. It is built as an either/or — build a fixture,
and if it cannot be built call `blocked(...)` and return — and it uses the
escape hatch properly in four places. But three of its guarded returns are
followed by sixteen `check()` sites that describe the DEN@KC team-scope
property in detail ("the ready frame is KC only", "Denver is the deferred
club", "no Denver player is in the allocation frame", "every eligible Kansas
City player IS modelled"), and on this run none of them was reached. The
module passes. `run_suite.py` reports no zero-check function, because each
function banked checks before the return. The property those sixteen lines
describe was not tested and the suite said nothing.

**31 check sites failed.** Fifteen are `test_p6_false_greens.py`, the
deliberate reproductions in Part B. The other sixteen are in ten modules
`test_draw_coherence` (4), `test_passer_credit_migration` (3),
`test_conservation` (2), `test_q9_live_feature_builder` (2), and one each in
`test_c1_denominator`, `test_p7_data_plane`, `test_product_orchestration`,
`test_qb_eligibility_den_kc`, `test_stat_contract` — and they are **not P6's
findings and are not attributed here**. The repository was being edited by six
other agents while this ran; some of these are very likely the transient state
of work in flight. They are recorded because a run that saw them and did not
say so would be the defect this whole document is about. The suite was already
red before `test_p6_false_greens.py` existed.

**377 of 823 named refusal codes were never constructed by any test.** That is
46% of the guards the shipping tree declares, never once seen to fire during a
full suite run. It is a lower bound on the gap rather than a defect list — a
guard can be exercised through a path that returns a different code — and it is
reported rather than gated for the reason given above. It is also the single
largest number in this document and the one most worth someone's attention.

**One of the 52 declared load-bearing guards never executed**, and the reason
is worth the whole R3 register on its own. `test_qb2_production.py:500`:

    assert_guard_is_load_bearing(
        run=seeded('ptd', 99), module_path='nfl.production.run_forecast',
        attr='QBACC', caught=lambda s: s['status'] == 'REFUSED',
        replacement=None,
        returns=None) if False else None
    # (done explicitly below -- QBACC is a module reference, not a callable)

A bypass proof disabled by `if False`, left standing in the source. It is
benign — the comment is true and the work is done explicitly below with
`guard_bypassed` — but the declaration still reads as coverage to anything that
greps for it, and R3 is the only thing in the repository that noticed.

### Calibration of the runner, and of this tool

    $ python3.12 nfl/tests/run_suite.py --only test_p6_false_greens
      modules 1  test functions 12  checks 36  FAILING CHECKS 19  RAISED 1
      ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 0
      SUITE FAIL

The runner reads the new module correctly: 36 checks, 19 failing, the tripwire
raising, no spurious zero-check report. `run_suite.py` itself was not modified.

**Regression mode, proven end to end against a seeded skip** (the seed module
was created, run, and removed; it is not in the tree):

    # step 1 - baseline, with the fixture present
    $ invariant_manifest.py --only test_zzz_p6_probe --name probe_base.json
      R1_CHECK_SITE  2 declared  2 CERTIFIED
      MANIFEST FULLY_CERTIFIED

    # step 2 - the fixture goes away, so the second check is never reached
    $ invariant_manifest.py --only test_zzz_p6_probe --baseline probe_base.json
      R1_CHECK_SITE  2 declared  1 CERTIFIED  1 NOT_CERTIFIED
      REGRESSION MODE: 1 invariant(s) that were certified in the baseline are
      not certified now.
        NOT_CERTIFIED  nfl/tests/test_zzz_p6_probe.py:17
                       THE PROPERTY THIS TEST EXISTS FOR
      MANIFEST FAILURE_TO_CERTIFY

    # the same module, same moment, through the runner every agent uses
    $ python3.12 nfl/tests/run_suite.py --only test_zzz_p6_probe
      modules 1  test functions 2  checks 1  FAILING CHECKS 0  RAISED 0
      ZERO-CHECK FUNCTIONS 0  BLOCKED FUNCTIONS 0
      SUITE PASS

That is the whole argument for the tool in nine lines: a named invariant
stopped being evaluated, and the suite went green.

And the tool does not exempt itself: one site in `test_p6_false_greens.py` is
reported NOT_CERTIFIED — the `check('the tautological RNG proof is gone', True)`
arm that fires only once the function it names has been deleted. That is a
declared either/or the arm rules do not cover, it is correctly named, and it is
left in the census rather than special-cased.

---

## Part B — the false-green census

### What counts as a false green here

A check is a FALSE GREEN when it **reports a property as holding without having
evaluated that property**. Five mechanisms account for everything found:

| Class | The mechanism |
|---|---|
| **tautology** | The assertion restates its own definition, or a library's contract. It cannot fail for any input. |
| **silent narrowing** | The fence scans a subset of what it names, and the subset shrinks without saying so. |
| **refusal-read-as-success** | A BLOCKED / DEFERRED / refused result is counted as, or rendered as, a pass. |
| **brittle-source-slice** | A property of code is proven by substring search over a fixed-width window that drifts off what it must cover. |
| **structurally-degenerate column** | A built column is constant, near-constant, or empty, so every statistic computed from it is arithmetic on a zero. |

**The polarity rule, which is the one general thing this audit adds to the
brittle-window class.** `test_r5_active_pool` was repaired because its
`src[i:i+900]` window grew past the branch and the checks *failed* while every
line they sought was present. That is the LOUD direction. The same construction
carrying a NEGATIVE assertion — `X not in window` — fails the other way: when
the construct grows past the window, the forbidden token leaves the window, and
the check **passes**. A positive windowed assertion degrades into a false red;
a negative one degrades into a false green, and nothing announces it. Both
instances of the negative form are in this census (P6-FG-7).

### The census, ranked by how much a reader would have trusted the green

Rank is "what would a careful reader have concluded from this, and how wrong
would they have been", not severity of the underlying bug.

| # | Finding | Class | State | Reproduction (all in `nfl/tests/test_p6_false_greens.py`) |
|---|---|---|---|---|
| 1 | `recon_error` is `\|multinomial(n,p).sum() − n\|`, published as exactly 0.0 on 276,968 + 104,130 + 4,348 rows | tautology | **ACTIVE** | `test_fg2_the_reconciliation_error_can_detect_a_wrong_allocation` |
| 2 | `cfg.glob('*/board.json')` sees **104 of 121** sealed boards; `D7_ROWS_ALL_SEALS_2026W1.csv` holds 1 seal for SF_LA against 4–8 for every other game | silent narrowing | **ACTIVE** | `test_fg1_the_board_selectors_see_every_sealed_board`, `test_fg1b_the_all_seals_artifact_is_not_all_seals` |
| 3 | `state_qb_game.csv.gz:scrambles` = 0 in **4,023 of 4,024** QB-games | structurally-degenerate column | **ACTIVE** | `test_fg3_built_count_columns_are_not_structurally_zero` |
| 4 | `stat_contract.tabulate()` verifies `agg['dropbacks'] == c['pass_attempt']+c['sack']+c['scramble']` where `agg['dropbacks']` is defined as exactly that sum | tautology | **ACTIVE (mitigated)** | `test_fg9_the_stat_contract_identities_are_not_their_own_definitions` |
| 5 | Six "the guard fails when bypassed" proofs that reach no production code — two compare string literals directly, a third compares against a literal assigned two lines above, one re-seeds a single RNG twice, two re-type the guard's own logic into the test body | tautology | **ACTIVE** | `test_fg6_a_bypass_proof_executes_the_thing_it_proves`, `test_fg6b_an_rng_reseeded_identically_proves_nothing` |
| 6 | Negative assertions over fixed-width source windows: the halting guarantee (`NONQB_CHAIN`, 220 chars) and the staging-leak guard (`stage_inputs`, 3,000 chars vs a 1,680-char function) | brittle-source-slice | **ACTIVE** | `test_fg7_a_negative_source_window_cannot_narrow_itself_into_a_pass` |
| 7 | `USAGE_PANEL.csv.gz:starter_class` is empty in **21,558 of 21,558** rows | structurally-degenerate column | **ACTIVE** | `test_fg4_a_published_panel_column_is_not_empty_in_every_row` |
| 8 | `v3/h1/h1_frame.py:40` still reads `q7_qb_game.csv.gz`, declared superseded with its sha256 in `Q7_PANEL_SUPERSESSION.json` | silent narrowing (stale input) | **ACTIVE** | `test_fg5_no_module_reads_an_artifact_its_owner_calls_superseded` |
| 9 | WS11 FG-4: the four frozen module hashes are checked for **length**, never recomputed | tautology | **ACTIVE, latent** | `test_fg8_the_frozen_module_hashes_are_recomputed_not_measured_for_length` — supplies the missing proof; passes today |
| 10 | `readiness_t90.py:131` renders `State.BLOCKED` as `READY` | refusal-read-as-success | ACTIVE, declared in place | reported only (see §B.10) |
| 11 | `test_capture_manifest_integrity.py:84` falls back to a 900-char window when its end marker is absent, without asserting the marker was found | brittle-source-slice | ACTIVE, low | reported only |
| 12 | `test_injury_parser.py:611` accepts `State.PASS` **or** `State.BLOCKED`; `test_capture_states.py:226` passes whenever its subject refuses | refusal-read-as-success | ACTIVE, low | reported only |
| 13 | `test_qb2_production.py:500` declares a load-bearing-guard proof and disables it with `if False else None`; the declaration still reads as coverage | tautology (dead declaration) | ACTIVE, benign | found by the manifest's R3 register; reported only |
| — | `test_r5_active_pool` fixed-width window | brittle-source-slice | **REPAIRED** | window now runs marker-to-marker and raises if the end marker moves |
| — | `test_refbands` raw-text grep catching its own warning comment | silent narrowing | **REPAIRED** | replaced by `_executable_refbands_reach()`, an AST reachability scan that exempts docstrings |
| — | Three corpus fences globbing three levels, 104 of 121 boards | silent narrowing | **REPAIRED** | `sealed_index.live_draw_files()` — but only for **draw files**; see finding 2 |
| — | `q7/panel.py` composed-identity tautology and structurally-zero `scr` | tautology + degenerate column | **REPAIRED** | `q7_qb_game_r2.csv.gz`, 5,864 scrambles, reconciled against nflverse `qb_dropback` |
| — | `conservation.team_rows` returning `BLOCKED[CONSERVATION_ROW_AXIS_UNKNOWN]` on every A1 team-axis board | refusal-read-as-success | **REPAIRED** | `row_axis == 'team'` is now understood and joined by identity; an unknown axis is still refused by name |
| — | WS11 FG-1 / FG-2 / FG-3 / FG-6 (producers never called) | artifact-only proof | **REPAIRED** | `dryrun.run()`, `PAR.run()`, `LF.parity()` now have call sites |
| — | WS11 FG-11, the 25 silent skips | silent narrowing | **REPAIRED structurally** | `run_suite.py` now reads the tally around **every** function and names a zero-check function |

### B.1 — `recon_error` reconciles numpy, not the allocator

`nfl/research/q9b/family.py:282` and `nfl/research/q6/forward_chain.py:489`:

    T[d] = rng.multinomial(int(budget[d]), P[d] / P[d].sum())
    ...
    recon = float(np.abs(T.sum(axis=1) - budget).max())

`numpy.random.Generator.multinomial(n, p)` returns counts summing to `n` by
contract. The statistic is therefore zero for every allocation the code can
produce, and it is published as exactly `0.0` on every row of three artifacts:

| Artifact | Column | Rows | Distinct values |
|---|---|---|---|
| `nfl/research/q6/Q6_DIAGNOSTICS.csv.gz` | `recon_error` | 276,968 | 1 (`0.0`) |
| `nfl/research/q9b/Q9B_FAMILY_ROWS.csv.gz` | `recon_error` | 104,130 | 1 (`0.0`) |
| `nfl/research/q9/Q9_DIAGNOSTICS.csv` | `max_reconciliation_error` | 4,348 | 1 (`0.0`) |

Measured, not argued. The reproduction allocates a budget of 30 across five
players and then breaks the allocation three ways:

| Seeded defect | `recon_error` |
|---|---|
| correct multinomial allocation | 0.0 |
| **every unit given to one player** | **0.0** |
| **one player zeroed, his mass moved to a neighbour** | **0.0** |
| allocation built to 3× the budget it is scored against | 60.0 |

The last row is kept and reported as a pass because it **bounds the claim**:
the statistic is not inert in every direction. What it cannot see is any error
that preserves the total — which is every allocation error. A reader of
`recon_error = 0.0` on 104,130 rows concludes the allocator conserves team mass
on every draw; what has been established is that `multinomial` sums to `n`.

This is the same defect q7 found in itself and named precisely, in
`Q7_PANEL_SUPERSESSION.json`:

> The only dropback check was the composed identity `att + sacks + scr == db`,
> which is true of any three numbers and cannot detect a counter that is never
> reached.

**A non-tautological replacement exists and q7 already built it**: reconcile
against an independently sourced total (q7 compares its composed dropbacks to
nflverse's own `qb_dropback` flag and enumerates the nine-row residual). The
analogue here is to compare the realised allocation against the team budget as
the **upstream stage** computed it, not as this stage passed it in.

### B.2 — a board fence that scans one level, and an artifact named ALL_SEALS

`nfl/research/sealed_index.py` fixed exactly this shape for **draw files** and
wrote down why:

> That shape hard-codes THREE levels below `live/` … The fences reported 104
> boards, called it "every sealed board", and were re-frozen at that number.
> … The twelve REPLAY_C1 directories are the proof that the file extension was
> never the cause: they are `.npz` and were missed anyway. Depth was.

The **board.json** readers were not repaired. Three of them still carry
`cfg.glob('*/board.json')`:

    nfl/research/same_day_retrospective.py:803
    nfl/research/v2/d7/d7_central_tendency.py:289
    nfl/research/market_outcome_audit.py:189

Measured now, against the tree at HEAD:

| Scan | Boards found |
|---|---|
| `cfg.glob('*/board.json')` over every game and config directory | **104** |
| `cfg.rglob('board.json')` over the same directories | **121** |
| `*_V1_CANDIDATE_R8/*/board.json` | **65** |
| `*_V1_CANDIDATE_R8/**/board.json` | **66** |

The 17 missed are the same 17: five `2026_01_SF_LA/pre_inactives_*` boards and
twelve `REPLAY_C1/*`. REPLAY_C1 is a declared exclusion and not a game
directory, so the live loss to these three selectors is SF_LA's five
pre-inactives boards, one of which is its only pre-inactives R8 seal.

**The consequence, measured on the published artifact rather than inferred.**
`D7_ROWS_ALL_SEALS_2026W1.csv` (2,939 rows) contains, for `2026_01_SF_LA`,
exactly **one** seal — `post_inactives_V1_CANDIDATE_R8/5e70d884…` — against
four to eight seals for every other game on the slate, while ten `board.json`
files sit in SF_LA's directory. A file whose name asserts ALL SEALS is not all
seals.

**Why it is masked rather than absent today.** The default selection is
`--seal last`, and SF_LA's post-inactives board (`written_at`
2026-09-11T00:13:09Z) is later than its invisible pre-inactives board
(2026-09-10T21:18:56Z), so `last` happens to land on the same board either way.
Under `--seal first` and `--seal all` — the latter is what produced
`D7_ROWS_ALL_SEALS` — the answer is different from the one the data supports.
That is a false green that survives on a coincidence of ordering.

### B.3 — the scramble column q7 repaired, still broken in track1

`nfl/research/track1/build_state_panel.py` line 160 takes
`pid = (r.get('passer_player_id') or '').strip()` and line 168 accumulates
`qc['scrambles'] += 1 if scr else 0` against that id. A `qb_scramble` play
carries no passer id — nflverse charges it to `rusher_player_id`, which this
builder does not read at all (its column list at line 61 omits it).

    nfl/research/track1/state_qb_game.csv.gz : scrambles == 0 in 4,023 of 4,024

The team-level column at line 150 is unaffected because it needs no player id,
which is why the defect is invisible in aggregate. q7's repaired panel measures
**5,864** scrambles over the same six seasons.

`nfl/research/q7/q7_qb_game.csv.gz` shows the same 1-in-4,025 signature and is
**not** counted against anyone: it is declared superseded, with its sha256, in
`Q7_PANEL_SUPERSESSION.json`, and deliberately retained because the published
Q7 conclusions were computed from it. The reproduction reads that record and
honours it — a declared exclusion is honoured, an undeclared one is not, which
is the rule `sealed_index.FENCE_EXCLUDED_NAMESPACES` already follows. track1
has no such record.

### B.4 — a production identity that restates its own definition

`nfl/production/stat_contract.py`:

    AGGREGATES = {'dropbacks': ('pass_attempt', 'sack', 'scramble'), ...}
    agg = {k: sum(c[t] for t in terms) for k, terms in AGGREGATES.items()}
    ident['dropback_partition'] = (agg['dropbacks']
                                   == c['pass_attempt'] + c['sack']
                                   + c['scramble'])

`X == X`. All three identities are that shape, so `broken` is always empty and
`STAT_CONTRACT_IDENTITY_BROKEN` cannot be raised by this path. The docstring
calls a failure "an arithmetic defect in this module, never a tolerance to
widen"; the arithmetic being tested is Python's. The reproduction runs the
three identities over 2,000 **random** class-count vectors — including vectors
no play stream could produce — and all three hold on all 2,000.

**Ranked below the two above because it is mitigated.** `VERIFIED_AGAINST` pins
the corpus class counts (`'scramble': 5054` among them) and
`test_stat_contract.py:178` calls `SC.tabulate(_pbp_rows())` on the real
play-by-play and compares class by class at line 186, so a `classify_play`
regression IS caught — elsewhere. What is not true is the thing `identities_hold` says to a
reader: that the partition was checked on the rows just counted.

### B.5 — six bypass proofs that bypass nothing

`nfl/tests/bypass.py` states the standard and why the second half is the half
that matters: "A test that would still pass with the guard deleted is testing
nothing." Six functions named for that standard reach no production code at
all:

| Function | What it actually asserts |
|---|---|
| `test_capture_manifest_integrity::test_the_guards_fail_when_bypassed` | three `str not in str` comparisons between literals written in the test body |
| `test_v1_entrypoint_integration::test_the_guards_fail_when_bypassed` | two of the same, plus `'DERIVED.artifacts' not in _calls(ast.parse('x = 1\n'))` |
| `test_v1_game_stream_separation::test_the_guard_fails_when_bypassed` | two RNGs seeded identically produce identical draws |
| `test_own10_dependence_metric::test_the_guard_fails_when_bypassed` | a re-typed copy of the guard's logic, run against a fixture |
| `test_own10_dependence_metric::test_the_withdrawn_number_guard_fails_when_bypassed` | same, over test-local helpers |
| `test_v1_composition_fidelity::test_the_guard_fails_when_bypassed` | `'FAIL[...]' not in fake`, where `fake` is a string literal assigned two lines above |

WS11 found the first of these and called it "the most structurally hollow
function found in the suite". It is still there, and there are five more.

**The detector is deliberately weak so that it cannot over-report**: reaching
any production alias once clears a function. `test_v1_scramble_coherence::
test_the_guards_fail_when_bypassed` clears on a single `SC.couple(...)` call
even though two of its three arms are numpy identities, and that is the right
outcome for a mechanical check — the remaining judgement belongs in prose.

For the RNG one the reproduction states the point as a measurement rather than
an opinion: identical seeds agree for **every** seed tried, so the assertion is
numpy's contract and cannot be a property of this repository.

### B.6 — negative assertions over fixed-width source windows

`test_v1_entrypoint_integration.py:195`, proving that the halting relaxation
did not reach the required stages:

    i = src.find('NONQB_CHAIN = (')
    window = src[i:i + 220]
    for required in ('qb_layer', 'team_environment', ...):
        assert check(f'{required} is NOT in the non-halting set',
                     f"'{required}'" not in window, ...)

The tuple is 109 characters today, so the window also scans 111 characters of
the *following* function's docstring. Seed the defect — a chain padded past 220
characters with `'qb_layer'` at the end — and the check reports **no** required
stage as non-halting, at character 511, with the token plainly present. The
halting guarantee is proven by a substring search over a region that shrinks
relative to what it must cover.

`test_appearance_staging.py:187` is the same shape guarding the staging leak
that took the machine down at HEAD:

    body = s[i:i + 3000]
    check('stage_inputs no longer calls mkdtemp for the default stage',
          'mkdtemp' not in body, ...)

`stage_inputs` is **1,680** characters, so today the window over-covers by
1,320 characters of neighbouring functions (a false-red risk), and the moment
the function passes 3,000 an `mkdtemp` beyond that point becomes invisible.

The repair pattern is already in this repository, written out in full in
`test_r5_active_pool.py`: slice marker-to-marker and raise if the end marker
moves, rather than to a character count.

### B.7 — an empty published column

`nfl/research/refbands/build_refbands.py:84` writes the panel with
`r.get(k, '')`, and `refbands.py:493` assigns `r['starter_class']` later, in a
different pass. The default is what ships:

    nfl/research/refbands/USAGE_PANEL.csv.gz : starter_class == '' in 21,558 of 21,558

`write()` refuses zero bytes — `REFBANDS_EMPTY_ARTIFACT` — and has no opinion
about a column that is empty in every row. That is the generalisable gap: the
non-empty assertion is at the file level and the absence is at the column
level.

### B.8 — a superseded artifact that still has a reader

`Q7_PANEL_SUPERSESSION.json` is a careful record: it names the defect, names
why it was not caught, pins the sha256 of each superseded artifact, states that
they are retained on purpose, and enumerates
`conclusions_drawn_from_the_superseded_panel`. What it enumerates is
**artifacts**. `nfl/research/v3/h1/h1_frame.py:40` is **code**:

    Q7 = _REPO / 'nfl' / 'research' / 'q7' / 'q7_qb_game.csv.gz'

and `q7_crosscheck()` reconciles h1's own scramble totals against it, reporting
`q7_total_scrambles` (1) beside `h1_total_scrambles`. The function is honestly
labelled "Reported, not trusted" and refuses nothing, so this is a stale input
rather than a wrong verdict — but a crosscheck against the panel its owner has
withdrawn is not the crosscheck it appears to be.

### B.9 — WS11 FG-4, re-checked

`test_q9b_model_family.py:368` still reads

    len(ci['module_source_sha16']) >= 4
    and all(len(v) == 16 for v in ci['module_source_sha16'].values())

The hashes are checked for **length**. `freeze._module_hash` is in the same
package. P6 does not own that module and did not edit it; instead
`test_fg8_...` supplies the proof it lacks, recomputing all four against the
live source. All four still match
(`bb51133641338547`, `5b411b4f00e28e6f`, `1f320b1ee3170e64`,
`481f005f682cd721`), so the finding is **latent**: the freeze COULD stop
describing the candidate it names without anything saying so, and has not yet.

### B.10 — the ones reported without a failing test, and why

- `nfl/research/s5/readiness_t90.py:131` renders `State.BLOCKED` as `READY`
  and says so in the detail string it prints, naming the G0A egress debt. It is
  a refusal rendered as a pass in the top-line column, and it is declared in
  place. Reported, not failed, because turning a documented and explained
  rendering red would teach the wrong lesson.
- `test_capture_manifest_integrity.py:84`'s `s[i:j if j > i else i + 900]`
  falls back to a fixed window when its end marker is absent, without asserting
  that the marker was found. Low, and partly redundant with two neighbouring
  checks that grep the real files.
- `test_injury_parser.py:611` accepts `State.PASS` **or** `State.BLOCKED`; it
  prints the real state beside the check, so nothing is hidden.
  `test_capture_states.py:226` is `o.state is not State.PASS or o.value[...]`,
  an implication that passes whenever its subject refuses, under a label that
  makes the stronger claim. A sweep of every test module found exactly two
  such implication-shaped checks and the other one
  (`test_coverage.py:90`, "never PASS while nothing has come due") is
  legitimate — the implication IS the property.

### B.11 — sweeps that came back clean, stated so they are not re-run

- **Production callers treating a BLOCKED Outcome as acceptable.** Every
  `if X.state is State.FAIL:` site outside the test tree was read.
  `nonqb/layers.py:105` falls through to `if v.state is not State.PASS: return v`;
  `run_forecast.py:1574` carries DEFERRED into the artifact as OWED with a
  comment saying so; `stat_contract.py:259` handles NOT_APPLICABLE by name.
  No unhandled refusal-as-success found in production.
- **Fixed-depth `parts[-3]` / nested-star globs.** Only `sealed_index.py`
  carries the shape, in its own docstring describing the repair. The remaining
  `parts[n]` sites index parsed identifiers, not paths.
- **Constant-vs-constant comparisons across every test module.** Six, all
  accounted for above.

---

## What needs an owner, and what P6 deliberately did not touch

P6 owns `nfl/tests/run_suite.py`, `nfl/tools/invariant_manifest.py`,
`nfl/tests/test_p6_false_greens.py` and `nfl/research/v4/p6/`. Every finding
above lives somewhere else. **No production or research module was edited**,
and `run_suite.py` was not edited either — the manifest is a separate tool
precisely so that six other agents' dependence on the runner is not disturbed.

| Finding | Repair, in one line | Belongs to |
|---|---|---|
| B.1 `recon_error` | reconcile against the budget as the **upstream stage** computed it, not the one this stage was handed; q7's nflverse crosscheck is the worked example | q6 / q9b owner |
| B.2 board glob | route the three selectors through a depth-agnostic finder, as `sealed_index.live_draw_files()` already does for draw files; then rebuild `D7_ROWS_ALL_SEALS` | d7 / retrospective / market-audit owner |
| B.3 track1 scrambles | charge `qb_scramble` to `rusher_player_id` and add it to the read column list; q7's repair is transcribable | track1 owner |
| B.4 stat_contract identities | compare `agg` against a sum computed **from the rows**, not from `AGGREGATES` | stat_contract owner (A-series) |
| B.5 six bypass proofs | route each through `bypass.guard_bypassed`, or delete the function and say why the guard needs no proof | each test's owner |
| B.6 negative windows | slice marker-to-marker and raise when the end marker moves — `test_r5_active_pool.py:130` is the written-out pattern | entrypoint / appearance-staging owners |
| B.7 `starter_class` | assign before writing, and make `build_refbands.write()` refuse a column empty in every row as it already refuses zero bytes | refbands owner |
| B.8 h1 reads superseded q7 | point `h1_frame.Q7` at `q7_qb_game_r2.csv.gz`, and extend `Q7_PANEL_SUPERSESSION.json` to enumerate readers as well as artifacts | v3/h1 owner, q7 owner |
| B.9 freeze hashes | call `freeze._module_hash` and compare, three lines | q9b owner |
| A: 57 never-executed check sites | for each, either reach the branch or record `blocked()` so the runner and the manifest can see it; 16 of the 57 are one module, `test_appearance_team_scope.py` | each test's owner |
| A: 377 of 823 refusal codes never constructed | not a defect list and not repairable in one pass; the useful first step is to decide which codes are meant to be reachable from a test at all, and to seed violations for those | whoever owns the guard |
| A: the `if False` bypass declaration | delete the dead call, or re-enable it; the comment beside it is already correct | qb2 owner |

**The one structural repair that would prevent most of the column findings**
(B.3, B.7, and the `q7` defect before it) is a single rule applied at build
time rather than at audit time: **a stage that writes a column must refuse a
column that is constant, empty, or non-zero in fewer than some declared number
of rows, unless the degeneracy is declared.** `build_refbands.write()` already
refuses zero bytes; the absence it cannot see is one level down. That is the
same generalisation the MLB briefing draws about non-empty, schema-correct
stage outputs, applied to columns instead of files.

## Evidence ceiling

**Established by measurement.**
- Every count in Part B was read off the tree or the artifact at the commit
  named at the top, with the command in the reproduction test beside it.
- 104 of 121, and 65 of 66, were counted by walking `nfl/research/live`, not
  inferred from the sealed_index docstring.
- The `recon_error` tautology was demonstrated by corrupting an allocation
  three ways and reading the statistic, not argued from the source.
- The invariant manifest's calibration (a seeded silent skip that `run_suite`
  reports as SUITE PASS and the manifest reports as FAILURE_TO_CERTIFY) was run
  end to end and the seed removed afterwards.
- All four q9b freeze module hashes were recomputed against live source.

**Not established.**
- **The census is not claimed to be exhaustive.** It is four mechanical sweeps
  (fixed-width slices, fixed-depth globs, constant-vs-constant comparisons,
  degenerate columns in every CSV under `nfl/research`) plus hand-reading the
  sites each sweep returned. A fifth shape — a test that mutates state a later
  test depends on — was not searched for, and WS11 did not search for it
  either.
- **The degenerate-column sweep covers stored CSV artifacts, not in-memory
  columns.** A column that is degenerate only at runtime, or that lives in an
  `.npz`, was not sampled.
- **A full `run_suite.py` baseline was started and did not survive.** It ran
  for roughly 40 minutes against a machine carrying six other agents' jobs
  (load average 8-15 on four cores) and was terminated before it flushed its
  output, leaving a zero-byte log. Nothing was recovered from it and no claim
  in this document rests on it. The full-suite evidence here is the invariant
  manifest run, which imports and executes every test function in every
  module and records every check verdict, plus the targeted `run_suite --only`
  runs named beside each result.
- **The repository was being edited by other agents throughout.** `git status`
  at the time of the run showed thirteen modified files and seven untracked
  ones, including `nfl/research/q7/panel.py` being rewritten and
  `nfl.research.q7.panel` being re-run in another process. Counts taken from
  artifacts under active rebuild are snapshots of this moment, and the
  reproductions re-measure rather than pinning numbers, so they follow the tree
  instead of going stale.
- **B.2's live consequence is bounded, not total.** Under `--seal last`, the
  default, the missing SF_LA board does not change the selection. The
  demonstrated wrong answer is under `--seal all`, in
  `D7_ROWS_ALL_SEALS_2026W1.csv`. Whether any downstream conclusion turned on
  that row set was not traced.
- **B.4 is mitigated and is ranked accordingly.** A `classify_play` regression
  is caught by the pinned corpus counts re-measured at
  `test_stat_contract.py:178-192`. The claim
  is about what `identities_hold` tells a reader, not that the partition is
  unverified anywhere.
- **The manifest's R2 register says a code was never CONSTRUCTED during the
  suite.** It does not say the guard is untested — a guard can be exercised
  through a path that returns a different code. R2 is a lower bound on
  coverage, and that is why it does not gate.

---

## Files P6 added or changed

| Path | What it is |
|---|---|
| `nfl/tools/invariant_manifest.py` | the manifest tool (new) |
| `nfl/tests/test_p6_false_greens.py` | one failing reproduction per ACTIVE finding (new) |
| `nfl/research/v4/p6/P6_INVARIANT_MANIFEST.md` | this document (new) |
| `nfl/research/v4/p6/INVARIANT_MANIFEST.json` | the first full manifest run (126 modules, 7,658 declared invariants), and the baseline for `--baseline` regression mode (new) |
| `nfl/tests/run_suite.py` | **unchanged** |

## A note on commits

P6 was instructed not to commit or push and did not. At 05:24 UTC another
agent's `git add -A` sweep committed `nfl/tools/invariant_manifest.py`,
`nfl/tests/test_p6_false_greens.py` and an earlier draft of this document into
`53a3c27` mid-edit, so the versions in that commit are not the ones described
here. The current versions, and `INVARIANT_MANIFEST.json`, are in the working
tree uncommitted. Nothing was lost and nothing needs undoing; it is recorded
because a reader comparing `53a3c27` against this document would otherwise find
them disagreeing and have no way to know why.

## A note on the colour of the suite

`nfl/tests/test_p6_false_greens.py` fails, on purpose, and it will keep failing
until the modules it names are repaired by their owners. That is the honest
state of the repository and it is the whole point of the module: the alternative
— reporting these findings in prose while the suite stays green — is the exact
shape of defect this work was sent to find.

The module's own docstring says so at the top, names the owner of every finding,
and says plainly that the cheapest way to green it would be to weaken a check,
which is what happened to `test_refbands` once already. If a finding turns out
to be wrong, the instruction there is to delete the whole function and write
down why — not to narrow it until it passes.
