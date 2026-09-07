# Task report — volatility-test debt (Part I) and P4E RB allocation research (Part II)

Date 2026-09-07. Branch `main` of `94924676jp-a11y/nfl`, local commits only
(this session's GitHub scope is `mlb-prop-system-v7`, which holds the NFL
tombstone; every NFL commit in this session has been local).

Directive: close the `test_volatility.py` debt with none of the five forbidden
shortcuts, then — only if the suite is green — run P4E on RB carry share,
allocation and competition, against a pre-declared eight-rule promotion
standard. **Commit and stop.**

**Headline: no promotion.** P4C system C is retained. P4E is reported as
negative research under `predeclaration_p4e.md` section 12, and the reason is
specific rather than a shrug — the best pre-declared candidate improves pooled
carry CRPS by 0.0197 (1.0%), which is 1.94% of the allocation error the
oracle says is available, against a pre-declared bar of 5%. The work also
found and fixed three real defects, two of them in my own harness.

---

## Part I — the volatility-test debt

Closed and already committed as `95d2fe7`. Recapped here only because Part II
was gated on it.

The failing assertion compared a count of substantive-difference groups against
a count of raw captures via a ratio. That ratio is a property of today's data,
not of the algorithm, so every permitted repair would have been one of the five
forbidden moves. **The assertion was withdrawn and replaced by the invariant it
was reaching for** — `len(subs) <= len(raws)`, which holds for any input — and
eight named invariants (N1–N8) were added to test what the ratio was standing
in for.

- `test_volatility.py`: **77 passed, 0 failed**.
- `git diff --stat -- nfl/capture/` is empty: **no production defect was found
  and the volatility algorithm was not modified.**
- The differences the old assertion tripped on were read and are genuine
  editorial page copy inside the embedded broadcast blob ("Week 1 NFL **action**
  at" → "Week 1 NFL at"; "NFL Week 3" → "Week 1"), not a masking failure.

Two errors of mine along the way, both fixed: the N-tests were first appended
*after* the `if __name__` block, so they never ran; and a byte-level
`SequenceMatcher` over 200KB pages hung the suite and was rewritten line-wise.

**Suite state before Part II, re-measured today, not quoted from Part I:**

| location | modules | assertions | failed |
|---|---|---|---|
| `nfl/tests/` | 17 | 1,230 | 0 |
| `sportsplatform/governance/` | 3 | 93 | 0 |
| **total** | **20** | **1,323** | **0** |

Every module exited 0. Required state met.

---

## Part II — P4E

Pre-declaration committed as `3716f5a` **before** any candidate number existed.
Artifacts under `nfl/research/p4e/`.

### 1. The baseline gate, and the defect it exposed in my own harness

The directive's hard gate: *"Reproduce its published metrics exactly. If it does
not reproduce, STOP."*

It did not reproduce. `|diff|` was 3.18e-06 to 1.82e-05 against a 1e-9 gate. I
stopped and diagnosed it rather than loosening it, and **the defect was mine.**

- Chunk-size hypothesis (p4c_lib 2000 vs p5a_lib 1500) — **wrong**; the two
  scorers give identical values here.
- Literal replication of `run_p4c.py`'s carries/system-C path alongside P4E's,
  in one process, comparing every intermediate: `y`, `C`, `p_app`, `Ad`, `T`,
  `W`, `avail`, `S`, `Y` all **bit-identical**. P4E was not the deviant.
- Re-executed `run_p4c.py` unmodified in an isolated copy. The rerun's
  `p4c_results.json` is **byte-identical** to the published one (sha256
  `5d8d34c2…`), 1,152 scalar metrics compared, 1,152 bit-identical, 329s
  against the original 336s. **P4C is bit-reproducible.**
- Cause: `p4e_build.PUBLISHED` was a hardcoded literal, and the literal was
  wrong. It agreed with the artifact to **four** decimal places — the precision
  printed in `run_p4c.log`, and the precision quoted in my own pre-declaration
  §3 — and disagreed beyond it. **I had transcribed it off a log line instead of
  reading the artifact.** A gate asserting against a number nobody read is not a
  gate.

Remedy: `PUBLISHED` now reads `p4c_results.json` at run time and records its
sha256, which the run prints. Gate result:

```
2022: P4E 1.929561163321  published 1.929561163321  |diff| 0.00e+00
2023: P4E 1.997281732179  published 1.997281732179  |diff| 0.00e+00
2024: P4E 2.110274841595  published 2.110274841595  |diff| 0.00e+00
2025: P4E 2.054493485112  published 2.054493485112  |diff| 0.00e+00
```

Recorded in `baseline_reproduction.json`. This is a Class A failure in the
project's own vocabulary — a number that was never read being reported as
though it had been — and it is worth saying plainly that it was caught by the
gate doing its job, four hours after I wrote the gate wrong.

### 2. A real outcome leak in a candidate feature, found before any judgement

The first ladder run had block C improving pooled carry CRPS by 25.9% and
`E_ABC` by 37.0%. An allocation-only change cannot plausibly recover that, so I
read the feature instead of the result. `g_teammate_share_sum` was
`(previous team-game's total RB carry share) − (the CURRENT game's own realised
share)`. The current outcome entered the ridge design linearly.

Fixed: the player's **own previous-game** share is subtracted. The contaminated
numbers are preserved in `p4e_leak_incident.json` as an incident and are **not
results**. The same defect is replayed as guard-deletion proof GD2 below.

### 3. A chronology defect the audit found, in the panel's own shape

`run_p4e_audit.py` tests "prior-only" mechanically rather than asserting it:
blank every outcome field on every row at ordinal ≥ k, rebuild the whole feature
set, and require the features at ordinal == k to be bit-identical. First run:
**LEAKING**, 1–14 values per probe.

Cause: **343 player-ordinal pairs in this panel carry two rows** — a player who
changed team mid-week appears once for each team in the same week. Taking a
player's history as "everything processed so far" let the second row read the
first. Same week, so not future information, but not *strictly prior* either.

Fixed with a `bisect` prefix cut on ordinals. Audit re-run:

```
ord >= 202110: 10303 blanked, 3538 values compared, CLEAN
ord >= 202301:  6689 blanked, 4843 values compared, CLEAN
ord >= 202410:  3230 blanked, 3045 values compared, CLEAN
ord >= 202516:   355 blanked, 3393 values compared, CLEAN
verdict: CLEAN
```

Every number below is from the post-fix run.

### 4. The four accepted observations — what they turned out to be

**Observation 3 (low-history over-allocation) is not a prior problem. It is
zero-rectification in P4C's weight construction.** P4C builds
`W = clip(C + residual, 0, 1)`. Clipping at zero is asymmetric, so `E[W] > C`
whenever `C` is small relative to the residual spread — which is exactly the
players with the least history. Measured, with nothing fitted:

| prior carries | centre C | E[W] | inflation |
|---|---|---|---|
| <10 | 0.0378–0.0583 | 0.0840–0.0945 | **+62% to +123%** |
| 10–24 | 0.0773–0.1001 | 0.1084–0.1303 | +28% to +40% |
| 25–49 | 0.1172–0.1548 | 0.1386–0.1747 | +11% to +18% |
| 50–99 | 0.1608–0.1896 | 0.1729–0.2010 | +6% to +10% |
| 100+ | 0.3601–0.3714 | 0.3623–0.3747 | **+0.1% to +1.0%** |

This answers §7's question directly, and the answer is none of the five options
it offered: the prior is not too diffuse, too generous, insufficiently
hierarchical, or misconditioned. **The estimator stops being mean-unbiased at
small `C`, and the loss is spread over the whole backfield by the
reconciliation.** §14's second bullet applies and is hereby said: the
over-allocation is a consequence of the weight construction, not of the prior.

The low-history cohort is also **not one population**. Labelling by outcome
(labels only — never modelled):

| bucket | n | C_pre | p_app | pred | real | bias |
|---|---|---|---|---|---|---|
| fringe non-appearance | 809 | 0.075 | 0.443 | 1.10 | 0.00 | **+1.10** |
| veteran, low recent usage | 753 | 0.025 | 0.766 | 1.42 | 0.85 | +0.58 |
| low-history other | 240 | 0.099 | 0.739 | 2.38 | 1.45 | +0.93 |
| returning from absence | 148 | 0.077 | 0.473 | 1.40 | 2.61 | **−1.21** |
| true emerging | 134 | 0.185 | 0.758 | 3.95 | 9.14 | **−5.20** |

The bias is **not one-signed**. Mass goes to fringe non-appearers and is
withheld from emerging backs. A blanket `<25 carries` penalty would make the
emerging cases worse — which is what the directive forbade on principle, and
the data agrees with the principle.

Observations 1 and 2 reproduce: realised RB1↔RB2 share correlation −0.552 to
−0.667, simulated −0.479 to −0.539.

### 5. The candidate ladder

Only the pre-reconciliation weight's **centre** changes: a ridge fit on
prior-only features replaces P4C's EWMA-with-position-prior. Appearance model,
team-volume draw, reconciliation, residual mass and joint draw identity are
imported unchanged, and the same rng seed is used, so every rung is a paired
comparison on the same draw sequence. Ridge penalty chosen on an inner
validation season inside the training block; the additive residual pool is
collected **out of fold** by expanding-window replay inside the training block,
because a fitted centre's in-sample residuals would hand the candidate a
predictive spread it has not earned.

Carry CRPS, lower is better. Bold beats the control.

| rung | 2022 | 2023 | 2024 | 2025 | pooled | Δ vs P4C | seasons better | Shapley recovered |
|---|---|---|---|---|---|---|---|---|
| **P4C** (control) | 1.9296 | 1.9973 | 2.1103 | 2.0545 | 2.0206 | — | — | — |
| E_0 (learned centre, no blocks) | 1.9468 | 1.9974 | 2.1191 | 2.0698 | 2.0311 | +0.0105 | 0/4 | −1.03% |
| E_A history depth | 1.9486 | 1.9961 | 2.1123 | 2.0611 | 2.0274 | +0.0068 | 1/4 | −0.67% |
| E_B hierarchy | 1.9311 | 1.9706 | **2.1043** | **2.0474** | **2.0112** | −0.0094 | 3/4 | +0.93% |
| E_C competition | 1.9327 | 1.9688 | **2.1027** | **2.0472** | **2.0108** | −0.0099 | 3/4 | +0.97% |
| E_D role change | 1.9435 | 1.9877 | 2.1141 | 2.0637 | 2.0234 | +0.0028 | 2/4 | −0.28% |
| E_E carry/snap | 1.9464 | 1.9967 | 2.1178 | 2.0690 | 2.0307 | +0.0101 | 0/4 | −0.99% |
| E_AB | 1.9324 | 1.9704 | **2.0962** | **2.0414** | **2.0082** | −0.0124 | 3/4 | +1.22% |
| **E_ABC (best)** | 1.9300 | **1.9544** | **2.0899** | **2.0378** | **2.0009** | **−0.0197** | **3/4** | **+1.94%** |
| E_ABCD | 1.9309 | 1.9553 | 2.0989 | 2.0431 | 2.0049 | −0.0157 | 3/4 | +1.55% |
| E_ABCDE | 1.9318 | 1.9571 | 2.0898 | 2.0427 | 2.0051 | −0.0155 | 3/4 | +1.53% |

`E_ABC` paired block bootstrap, clustered by team-game: pooled 95%
[−0.0268, −0.0119]; 2023 [−0.0577, −0.0270]; 2024 [−0.0382, −0.0028]; 2025
[−0.0321, −0.0028]; **2022 [−0.0147, +0.0144], which spans zero.** The gain is
real and it is small, and it is not present in every season.

Reading the blocks: **hierarchy (B) and competition (C) carry essentially all
of it**; history depth (A), role change (D) and carry/snap (E) contribute
nothing or hurt on their own, and D and E subtract when added on top. A learned
centre with no blocks (`E_0`) is *worse* than the EWMA — the ridge does not beat
the incumbent at the incumbent's own job, it only adds where the incumbent has
no channel at all.

Two rungs departed from the pre-declaration and are labelled: **`E_0` was
added**, because without it `E_A` conflates "a learned centre" with "block A";
and **block C was completed** to the contents §5 actually lists for it
(teammates' appearance behaviour, teammates' history depth, a competitor count),
which the first implementation was missing.

### 6. The eight-rule promotion standard, applied verbatim

`E_ABC`, the best pre-declared candidate:

| rule | result | value |
|---|---|---|
| 1 beats pooled carry CRPS | **PASS** | −0.0197 |
| 2 majority of seasons (≥3/4) | **PASS** | 3/4 |
| 3 PIT not damaged (≤+25% rel., < 27.877) | **PASS** | 23.79 vs 22.47, +5.9% |
| 4 low-history over-allocation materially improved | **FAIL** | bias **+0.501** vs control **+0.327** |
| 5 competition realism not worsened | PASS | closer to realised in 3 of 4 seasons |
| 6 survives role-change cohorts | **PASS** | role_change ΔCRPS +0.001, −0.049, −0.042, −0.036 |
| 7 survives adversarial | **PASS** | 0 FAIL, 2 guard-deletion proofs firing |
| 8 recovers ≥5% of allocation Shapley | **FAIL** | **1.94%** |
| | **6/8 → NO PROMOTION** | |

Rule 4 fails in the **wrong direction**: better share features make the
low-history over-allocation *worse*, not better (+0.501 against +0.327). That is
the single most informative number in this return. It says the missing signal is
not in the features at all — consistent with the rectification finding above.

### 7. Exploratory: what the rectification finding is worth

Not on the pre-declared ladder, therefore **not promotable under this
pre-declaration whatever it scores**, and reported as exploratory.

`mean_preserving` solves `delta_i` in `mean_m clip(C_i + eps_im − delta_i, 0, 1)
= C_i` by bisection. Nothing is fitted, no outcome is read, no constant is
introduced.

| rung | pooled CRPS | Δ vs P4C | seasons better | Shapley recovered | pooled rPIT | low-history bias |
|---|---|---|---|---|---|---|
| P4C | 2.0206 | — | — | — | 22.5 | +0.327 |
| X_mpr (control centre + MPR) | 2.0132 | −0.0074 | 3/4 | +0.73% | — | — |
| E_ABC | 2.0009 | −0.0197 | 3/4 | +1.94% | 23.8 | +0.501 |
| **X_ABC_mpr** | **1.9831** | **−0.0376** | **4/4** | **+3.70%** | **11.2** | **+0.120** |

`X_ABC_mpr` scores 6/8 on the same rules (rule 6 not computed; **rule 8 still
fails at 3.70%**). It is better than `E_ABC` on every axis that matters —
all four seasons, the low-history defect nearly closed, PIT halved, and RB1↔RB2
dependence closer to the realised value in all four seasons — and it still does
not clear the bar I set. That is the bar working.

**It is the obvious content of the next pre-registration, and it is not
promoted here.**

### 8. Adversarial results

`p4e_adversarial.json`, eval season 2024, clean `E_ABC` CRPS 2.0897, materiality
threshold 0.010 CRPS. **13 probes: 9 PASS, 4 UNRESOLVED, 0 FAIL.**

| probe | state | seeded CRPS | gain |
|---|---|---|---|
| future carry share | PASS | 2.0328 | 0.0569 |
| current-game realised carries | PASS | 1.4168 | 0.6729 |
| current-game realised snaps | PASS | 1.6867 | 0.4030 |
| postgame roster status (weak) | **UNRESOLVED** | 2.0897 | 0.0000 |
| postgame roster status (well-posed) | PASS | 1.7594 | 0.3303 |
| future teammate availability | PASS | 2.0722 | 0.0175 |
| current-game RB rank | PASS | 1.6605 | 0.4292 |
| evaluation-season fitted prior | **UNRESOLVED** | 2.0877 | 0.0021 |
| forbidden-identifier scan | PASS | — | 0 hits |
| GD1 delete `season < ev` guard | **UNRESOLVED** | 2.0879 | 0.0018 |
| GD2 restore the real leak | PASS | 1.3130 | 0.7767 |
| GD3 seed a forbidden identifier | PASS | — | scan fires |
| GD4 delete out-of-fold pool guard | **UNRESOLVED** | 2.0958 | −0.0061 |

The weak postgame-status probe returning **exactly** 0.0000 is degenerate, not
safe: the fit is conditional on appearance, so the seeded column is constant on
the training set and can carry no coefficient. It is re-posed rather than
reported as a pass — the same correction pattern as P4C probe 2 and P4D probe 6.

GD1 and GD4 are marked UNRESOLVED, not PASS and not FAIL. The guards are in
place and required, but deleting them does not move CRPS materially, so these
proofs do not establish that they are load-bearing. **No threshold was lowered
to make them pass.** GD2 and GD3 do fire, which satisfies §13's "at least two
guard-deletion proofs".

The forbidden-identifier scan itself had to be repaired: its first version
matched substrings and flagged `p4e_fit.py` for the phrase "expanding-window" —
`wind` inside `window`. It now matches identifier tokens and skips docstrings. A
guard that cries wolf on its own prose teaches you to ignore it.

### 9. Negative findings, stated as findings

1. **The available pregame information does not contain the missing allocation
   signal at the size that matters.** Best pre-declared candidate: 1.94% of the
   allocation oracle gap, against a 5% bar.
2. **A learned centre does not beat the EWMA at the EWMA's own job.** `E_0` is
   worse than the control. All of the gain comes from B and C, which are
   channels the incumbent has no representation for at all.
3. **History depth (A), role change (D) and carry/snap (E) contribute nothing.**
   Block E's failure survives a sensitivity: `g_snap_per_carry` had a scale
   defect (range 0 to 114,199.9, an unbounded denominator), and re-running with
   a bounded log ratio still gives E_E +0.0087 against the control, 1/4 seasons.
   The block genuinely does not help; my scaling was not the reason.
4. **The low-history over-allocation is caused by the weight construction, not
   the prior**, and better features make it worse.
5. **Negative RB1↔RB2 dependence already emerges** from the reconciliation
   (−0.48 to −0.54 against a realised −0.55 to −0.67) and no term was added to
   manufacture it.

### 10. Remaining debts

1. **The 2022 season is not distinguishable** for the best candidate (95% CI
   spans zero). Pooling would hide that; it is stated instead.
2. **Rule 5 has no pre-declared margin.** I scored "does not worsen" as *at
   least half the seasons no further from the realised value*. That reading was
   chosen after seeing the numbers and is a debt, not a threshold.
3. **The simulated and realised dependence figures are different
   populations** — across draws within a team-game versus across team-games.
   Both are reported and neither is differenced against the other.
4. **The oracle recovery is a ratio, not a re-derivation.** §11 asks for the
   allocation Shapley component recomputed under the candidate; what is reported
   is the CRPS gain over the P4C-CARRY component. With no promotion the
   distinction does not change the decision, but it is not what §11 asked for.
5. **Four adversarial probes are UNRESOLVED.** They have not shown they could
   catch the leak they name.
6. **These four evaluation seasons have now selected the P4C-CARRY
   decomposition, P5A's ordering, and this ladder.** They are development data.
   Nothing here is confirmatory, and the rectification result in particular
   needs untouched games before it means anything.

---

## Constraints honoured

NFL-1 not authorized and not touched. G0A not modified and not self-promoted
(still 11/12). T−90 capture not modified. No 2026 outcomes consumed. No
sportsbook markets ingested. No receiving or rushing efficiency, no touchdowns,
no fantasy points, no joint simulator, no DFS, no lineup optimisation, no wager
recommended, no parlay mentioned. `weekly_rosters.status` not used and asserted
absent by static scan. No present-week depth-chart state. No market-derived or
observed-weather features. No fuzzy name matching. Frozen 2026 artifacts
untouched. No Grade-B ESPN/Wayback material and no 2025 nflverse injury final
file as PIT evidence.

---

## OWNER DECISION REQUIRED

1. **Accept the no-promotion outcome?** P4C system C is retained. The
   alternative would be relaxing rule 8's 5% bar, which I am not going to
   propose — 1.94% of the available allocation error is not the improvement this
   project is looking for, and the bar was set before the number existed.
2. **Authorise a P4F pre-registration on mean-preserving rectification?** It is
   an unbiasedness repair to the estimator rather than a new model: no fitted
   constant, no outcome read. Exploratory numbers are −0.0376 pooled, 4/4
   seasons, low-history bias +0.327 → +0.120, PIT 22.5 → 11.2, and it **still
   misses the 5% bar at 3.70%**, so the honest question is whether a 3.7%
   recovery that fixes a named defect is worth a promotion rule the current
   standard would refuse.
3. **Rule 5's margin needs fixing in whichever pre-registration comes next**, so
   the reading is not made after the fact again.
4. **Confirm that a fitted `PUBLISHED` constant is now a class of defect this
   project names.** It behaved exactly like the Class A failures in the MLB
   governance file — a number reported as read that was never read — and the
   cheap general fix is that any gate must load its comparison value from the
   artifact and hash it.
