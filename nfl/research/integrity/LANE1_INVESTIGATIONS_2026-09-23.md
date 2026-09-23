# Three investigations, and one classification I got wrong

Owner priorities 1, 3 and 4 of 2026-09-23. **No repair is made here.** Every
number below was re-derived in this checkout rather than quoted.

---

## PRIORITY 1 — The Q9 frozen identity mismatch

### Verdict: `POST_FREEZE_DEPENDENCY_DRIFT`

With a refinement that changes what an owner should do about it: **the frozen
blob is still retrievable from git, so Q9 remains reproducible by checkout.**
Only the working tree has moved.

### The five determinations

**1. The exact commit where `layers.py` diverged.**
`Q9_PROSPECTIVE_FREEZE.json` was created at **`6490c67`** ("Q9B:
promotion-readiness audit"), and `layers.py` at that commit hashes to
`481f005f682cd721` — the pinned value, exactly. Five commits have touched the
file since:

| commit | sha16 | subject |
|---|---|---|
| `6490c67` | **481f005f682cd721** | the freeze itself |
| `45f0ff4` | d232175a6d485a2c | the board is one sealed forecast again |
| `db5bdb2` | 6c99b94c5f4ad51e | wire A1 and A2 |
| `16d3c45` | f5f4bde081d54da6 | SC2 interception reservation |
| `8801225` | 419ea433cba65dab | week-1 rows help R8 |
| `638af4f` | **b081a5b2fa45be25** | QY1 |
| HEAD | b081a5b2fa45be25 | unchanged since QY1 |

**This corrects the existing record.** `nfl/research/q9b/FREEZE_PIN_DIVERGED.md`
(2026-09-17) states the pin broke at `16d3c45` (SC2). It did not. It broke two
commits earlier, at **`45f0ff4`**, and `db5bdb2` moved it again before SC2.
That document's table omits both. The divergence is **five** changes deep, not
three. The rest of that document's reasoning stands and is confirmed.

**2. Did the frozen candidate originally reference different bytes?** No. The
pin was correct when written: the freeze artifact and the working tree agreed
at `6490c67`.

**3. Did the identity computation include this file exactly as asserted?**
Yes — same computation on both sides, `sha256(file)[:16]`. The test hardcodes
`Q9_LAYERS_SHA16 = '481f005f682cd721'` at `test_qb_eligibility_den_kc.py:53`
rather than reading `Q9_PROSPECTIVE_FREEZE.json`, so one fact exists in two
places. Minor, and worth fixing when the contract is revisited.

**4. Did a post-freeze code change alter a sealed candidate dependency?**
Yes, five times, by four distinct authors of change. None of them is the
culprit a reader would name: the failing check surfaces after QY1, and QY1 is
the *last* of five, not the first.

**5. Is the test contract stale?** **Partly, and this is the crux.** The check
asserts WORKING-TREE EQUALITY. The pin's actual meaning is a REPRODUCTION
INSTRUCTION: it says which `layers.py` Q9's numbers came from. Those are
different claims, and only one of them is violated.

| claim | status |
|---|---|
| the freeze names a specific `layers.py` | YES |
| that exact file is retrievable | **YES, at `6490c67`** |
| the working tree matches it | NO |
| Q9 can be re-run as frozen | **YES**, from `6490c67`, not from HEAD |

### What must not happen

Do not move the pin to the current hash: that converts a true failing check
into a passing one without changing a single fact, and destroys the only
record of which `layers.py` produced Q9's numbers. Do not revert `layers.py`
either — SC2 and QY1 are separate candidates with their own identities.

The honest green, if one is wanted, is to change what the test CLAIMS: assert
that the pinned blob is retrievable from git rather than that the working tree
equals it. That is a change to a governance contract and needs its own
decision. **Not taken here.**

---

## PRIORITY 3 — The two DET-BUF runs with no `board.json`

### Verdict: `EXPECTED_GOVERNANCE_FAILURE` + `TEST_BUG`. **I classified this wrong yesterday.**

`RED_TEST_CLASSIFICATION.md` called it `MISSING_ARTIFACT` and asked whether a
publication step had failed. That was wrong, and the evidence was in the run's
own status file. Correcting it changes what an owner should do: nothing needs
recovering, and the test contract needs fixing.

**Run 1 — `post_inactives_V1_CANDIDATE/fced077d0db6ab41`.** Its
`run_status.json` reads:

```
status: REFUSED,  n_refusals: 1
first_failure: artifact_sealing / ARTIFACT_SEALING_FAILURE
  HARD_INVARIANT_FAILED: current_season_input_freshness =
  BLOCKED[CURRENT_SEASON_INPUT_STALE] -- 3 registered current-season
  input(s) refuse: ['denom_panel', 'panel_p3', 'team_volume_history']
```

**The run refused at sealing, so it never reached board generation.** There is
no missing file. There is a refusal that worked.

**Run 2 — `post_inactives_V1_CANDIDATE_R9_W1P_GA_OFFICIAL`.** Not a run
directory at all. It holds `ARTIFACT.json`, `ZERO_DELTA.json` and
`player_draws.npz`, and its own `WHAT_THIS_IS_NOT` field says:

> "NOT a rerun. The governed post-inactives tournament REFUSED at step 6...
> This artifact is therefore CORRECT about who gets zero and INCOMPLETE about
> who gets what he was holding. **Reporting it as a full post-inactives board
> would be the false green this project exists to refuse.**"

It is a derived zero-delta draws artifact that explicitly declares it is not a
board.

### The actual defect

The discovery contract treats *"a directory under `live/` containing
`player_draws.npz`"* as *"a sealed board"*, then fails when `board.json` is
absent. Both directories are correctly not boards, and both say so in machine-
readable form — `run_status.json.status == 'REFUSED'` and
`ARTIFACT.json.artifact == 'POST_INACTIVES_BOARD_DRAWS'`.

**Are these runs valid for replay or governance?** Run 1: no, and it says so —
a refused run is evidence of a refusal, not of a forecast. Run 2: valid only
as what it claims to be, a zero-delta over a named source run, never as a
board.

**Disposition:** `sealed_index` / the census should read the declared status
and exclude or classify, not fail. Five red modules ride on this one contract.

---

## PRIORITY 4 — The non-integer carry defect, 243,766 -> 271,691

### Verdict: `additional artifacts entering the corpus`. Not new corruption, not changed semantics.

Re-measured across every sealed draw artifact in this checkout:

| | |
|---|---|
| runs discovered | 114 |
| runs carrying a `rushing/carries` layer | **45** (69 carry none) |
| carry cells | 543,000 |
| non-integer cells | **271,691** |
| fence held at | 243,766 |
| delta | **+27,925** |
| runs with zero non-integer cells | **6** |
| runs with non-integer cells | **39** |

### The decisive split

**Every one of the 39 affected runs is a 2026 WEEK 1 slate. Zero are week 2.**

```
by season_week:  {'2026_01': 271691}
2026_01_DAL_NYG 102,759   2026_01_NO_DET   27,440
2026_01_SF_LA    52,027   2026_01_ATL_PIT   7,908
2026_01_ARI_LAC  41,715   2026_01_BAL_IND   4,327
2026_01_TB_CIN   33,333   2026_01_DEN_KC    2,182
```

And every clean run is post-repair:

```
2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R9/96954efc523bd7d3
2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R9/d1e2727743c93990
2026_02_DET_BUF/post_inactives_V1_CANDIDATE_R9_W1P_GA_OFFICIAL
2026_02_DET_BUF/pre_inactives_V1_CANDIDATE_R9_W1P/81db92580ac3d872
2026_02_DET_BUF/pre_inactives_V1_CANDIDATE_R9_W1P_G/e58206e3e8473dc1
2026_02_DET_BUF/pre_inactives_V1_CANDIDATE_R9_W1P_GA/117a78668a0b7a0e
```

The two DEN-KC R9 rebuilds are exactly the runs the fence comment already
named as contributing zero. All four week-2 artifacts are clean.

### Which of the four candidate causes

- **Additional artifacts entering the corpus — YES.** The scan widened from
  109 runs / 433,000 cells to 114 / 543,000. The +27,925 is five
  previously-unscanned pre-repair week-1 boards. The test file predicted this
  in its own comment before the count was taken.
- **Wider test coverage — YES, and it is a fix, not a regression.**
  `test_p6_false_greens` records `ONE_LEVEL_GLOB_NARROWS_THE_FRAME: 107 of
  124` — the discovery glob was missing boards. Finding more of them is the
  point.
- **Newly generated corruption — NO.** Every board built after the counts
  repair has zero non-integer carry cells. A carry is dealt as a count now, so
  it cannot arrive fractional, and the measurement agrees.
- **Changed counting semantics — NO.** Same predicate
  (`|a - rint(a)| > 0`), same layer, same producer version across all 114
  runs: `draw_artifact_version = nfl-draw-artifact-1` for every affected cell.

### Disposition

The fence is doing its job and should stay at 243,766 until the five
unmigrated week-1 boards are dealt with. Absorbing +27,925 into the baseline
would convert newly discovered defective cells into "the expected number".
**The repair is to the boards, not to the fence.**

---

**V2 NOT YET EARNED.**
