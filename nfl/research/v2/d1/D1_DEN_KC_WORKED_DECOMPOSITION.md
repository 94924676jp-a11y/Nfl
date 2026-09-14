# D1 — WORKED DECOMPOSITION, DEN @ KC, sealed run `f91342d6787a66a1`

Board `nfl/research/live/2026_01_DEN_KC/PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1`,
1,000 draws, commit `9c3c29a8…+src1[b6dfb3faf23af1d5]`, model configuration
`V1_CANDIDATE_R8`. Machine-readable form:
`nfl/research/v2/d1/D1_DEN_KC_DECOMPOSITION.json`. Schema:
`D1_DECOMPOSITION_SCHEMA.md`. **No model was changed to produce this.**

19 players, 28 chains: 6 QB_PASSING, 6 QB_RUSHING, 3 RB_RUSHING, 13 RECEIVING.

---

## 1. THE THREE WORKED NUMBERS — REPRODUCED

| player | metric | uncond | P(zero) | conditional | ratio |
|---|---|--:|--:|--:|--:|
| Mahomes KC | pass yards | **144.015566** | 0.412 / 0.413 | **244.924432** | **1.70068** |
| Nix DEN | pass yards | **202.354389** | 0.048 / 0.049 | **212.557131** | **1.05042** |
| KC RB1 | carries | **10.918275** | **0.150** | **12.845029** | **1.176471** |

All three reproduce. Two decimals of the brief's table match exactly.

**One correction, and it is about which zero.** The brief gives Mahomes
P(zero) = 0.413 and says the ratio 1.70 is exactly 1/(1−0.413). 1/(1−0.413) =
**1.703578**. The measured ratio E[Y | participates] / E[Y] is **1.700680**,
which is exactly 1/(1−**0.412**).

The two probabilities are different events:

* **P(zero opportunity / non-participation) = 0.412** — `qb__db == 0`, 412
  draws in which Mahomes takes no dropback at all.
* **P(zero outcome) = 0.413** — `qb__pyds == 0`, 413 draws. One extra draw:
  Mahomes took a dropback and finished with zero passing yards.

`E[Y] = P(participates) · E[Y | participates]` closes **only** against the
first. Nix is the same shape: 0.048 against 0.049, one draw apart. Both
probabilities are persisted on every row, together with
`one_over_one_minus_p_zero_opportunity` and
`one_over_one_minus_p_zero_outcome`, so the near-miss is visible instead of
absorbed. At two decimals the brief's table is right; the identity as stated is
off by one draw in a thousand, and the schema is built so nobody has to
rediscover which.

**A second, larger version of the same distinction, found on the backups.** For
Mahomes and Nix the zero-attempt set and the non-participation set are
identical, so the identity also happens to close against `P(att == 0)`. For the
four backup quarterbacks it does not: they have draws with a dropback and no
attempt — sacked, or scrambled.

| QB | dropback draws with no pass attempt | 1/(1−P(zero att)) | measured ratio |
|---|--:|--:|--:|
| DEN QB2 | 14 | 5.464481 | **5.076142** |
| DEN QB3 | 13 | 5.102041 | **4.784689** |
| KC QB2 | 6 | 1.858736 | **1.838235** |
| KC QB3 | 2 | 1.727116 | **1.721170** |
| Mahomes, Nix | 0 | — | closes both ways |

The field `p_zero_opportunity_equals_non_participation` records this per row.

---

## 2. TEAM CHAIN

| quantity | DEN | KC | evidence |
|---|--:|--:|---|
| team plays (offensive snaps) | 65.412 | 67.697 | MEASURED |
| team dropbacks | 37.185768 | 41.467890 | MEASURED |
| team carries | 27.551364 | 25.244857 | MEASURED |
| dropback rate | 0.568485 | 0.612551 | DIVIDED |
| plays − (dropbacks + carries) | **+0.674867** | **+0.984253** | DIFFERENCED |
| Σ QB dropbacks | 37.223 | 41.492 | MEASURED, closes |
| designed rush budget | 25.082 | 21.866 | DIFFERENCED |
| Σ modelled targets | **layer absent** | 33.497 | SUMMED |
| QB attempts | 33.236 | 35.406 | MEASURED |
| stored `team_targets` | 33.749483 | 28.703538 | MEASURED — **not the denominator** |

The residual is real and is reported rather than hidden: the three team levels
are separate draw streams and do not close to each other by construction.

**Per-draw identities that actually hold (checked on every cell):**

* `db == att + sacks + scr` — worst deviation **0**, all 6,000 QB cells.
* `Σ qb__db == rint(team_dropbacks_part)` per team — worst deviation **0**.
* KC `Σ receptions == Σ QB completions` — worst deviation **0**.
* KC `Σ receiving yards == Σ QB passing yards` — worst deviation **0**.
* KC `Σ modelled RB carries ≤ designed rush budget` — holds to **1e-5** and
  **not exactly**: worst excess **2.328e-06** on a budget of 25, on 183 draws
  sitting at the boundary. That is one part in 2²³, the signature of a float32
  round trip upstream of a float64 array, not of an allocation that overflows.
  Reported as inexact, because calling it exact would be false and calling it a
  violation would read a storage artefact as a modelling one.

---

## 3. THE DENOMINATOR, MEASURED (WS09 J-12, confirmed)

KC stored `team_volume__team_targets` = **28.703538**. The allocator's actual
denominator, Σ of the 13 modelled players' targets, = **33.497**. QB attempts =
**35.406**.

Using the stored value inflates every receiver's share by the same factor
**1.1670**:

| player | share of the modelled pool | share against the stored total (WRONG) |
|---|--:|--:|
| KC WR1 | 0.253515 | 0.295852 |
| KC TE1 | 0.197540 | 0.230529 |
| KC WR2 | 0.116428 | 0.135872 |
| KC RB1 | 0.073201 | 0.085425 |

Both are persisted on every receiving row, the second explicitly labelled
WRONG, so the size of the error is visible rather than merely asserted.

**Where the missing attempts go.** `QB attempts − Σ modelled targets` has mean
**1.909**, minimum **0**, maximum **23** — never negative. Every modelled
target sits inside an attempt; about 5.4% of attempts reach no modelled
receiver. Note the asymmetry this creates and that it is exactly what C3
predicts: *completions* reconcile to the receiving layer to the last cell,
while *attempts* do not. Incompletions can leave the modelled set; completions
cannot.

---

## 4. DEN HAS NO RECEIVING AND NO RUSHING LAYER

```
DEN.receiving = { state: ABSENT_TEAM_DEFERRED, n_rows: 0,
                  code: "APPEARANCE_TEAM_DEFERRED" }
DEN.rushing   = { state: ABSENT_TEAM_DEFERRED, n_rows: 0,
                  code: "APPEARANCE_TEAM_DEFERRED" }
```

with the board's own sentence carried alongside: DEN is
`INJURY_REPORT_INCOMPLETE`, 14 players carry no appearance estimate and no
projection, and *a team with no filed report is not a team with no injuries*.
DEN's team chain therefore carries no target denominator and no conservation
identities at all — those keys are `null` and absent, not zero. No DEN player
is given a receiving or rushing chain. A test fails the suite if one appears.

---

## 5. WHAT IS MEASURED AND WHAT IS A RATIO COMPUTED BACKWARDS

**Measured per draw (11 of 28 chain-link kinds):** team plays, team dropbacks,
team carries, QB dropbacks, attempts, completions, passing yards, QB rush
opportunities and rushing yards, targets, receptions, receiving yards, carries,
stored team targets — plus the five per-draw identities in §2.

**Derived by summation:** the target denominator, Σ QB dropbacks per team, the
modelled RB pool.

**Derived by subtraction:** the play residual, the designed rush budget, the
unallocated attempts.

**Derived by division — no independent evidence about the rate:** dropback
rate, QB share of dropbacks, completion rate, yards per completion, target
share (both denominators), catch probability, yards per reception, RB share
(both denominators), QB yards per rush opportunity.

That last group is where every tempting "finding" lives. KC WR1's catch
probability of 0.736 and 11.80 yards per reception are not measurements of a
catch rate or a depth profile; they are `Σ receptions / Σ targets` and
`Σ yards / Σ receptions` from arrays the engine emitted, and they would
reproduce themselves identically under any conversion layer whatsoever. A test
asserts that every link whose name contains a share, rate, probability or "per"
is graded `DERIVED_BY_DIVISION`.

---

## 6. THE FOUR LINKS THE ENGINE CANNOT SUPPLY

| link | code | stand-in | direction of the error |
|---|---|---|---|
| dropbacks → **routes run** | `NO_ROUTES_LAYER` | pass-snap participation, **named as a proxy, value null** | upper bound on routes, gap unbounded (`layers.py:272`) |
| carries → **rushing yards** (RB/WR/TE) | `RUSHING_CONVERSION_CONTROL_UNDEFINED` | **none, deliberately** | `carries × YPC` is the board's *prohibited* implementation |
| **P(participates)** for every non-QB | not persisted | `P ≥ 1 − P(no modelled opportunity)` | lower bound; conditionals on it are upper bounds |
| designed budget → **RB category budget** | `RB_CATEGORY_BUDGET_NOT_PERSISTED` | Σ modelled RB carries | lower bound; misses rb-category carries on unmodelled backs |

**Why the routes stand-in is honest as handled.** The only way to put a number
on it from this artifact is to back a route count out of targets — which
re-derives the target share the route link is supposed to explain, and would
then be quoted as though it explained it. So the proxy is named and left null.

**Why rushing yards gets no stand-in at all.** A diagnostic that helpfully
filled in `carries × yards-per-carry` would be a model change wearing a
diagnostic's clothes, and it is the specific product the board forbids. The
chain terminates at carries; `e_outcome` is `null`; a test asserts no
yards-per-carry link exists anywhere in the artifact.

**One asymmetry worth naming.** The same board converts rush opportunities to
yards for a *quarterback* (`qb__ryds`, MEASURED, Mahomes 12.91 yards on 1.73
opportunities) and declares the same conversion ungoverned for a *running back*.
`QB_RUSHING` chains are persisted so that asymmetry is on the record.

---

## 7. THE CARRIES ARE NOT COUNTS

`rushing__carries` is float64 and non-integer in **795 of 1,000** cells for
KC RB1 (604 and 783 for RB3 and RB2). These are allocated carry *mass* under
the P4C simplex, not integer carries. Any threshold read off them — the board
prints "9.5+ at 0.575" — is being read off a continuous quantity, not a count.
The count of non-integer cells is persisted on the carries link.

---

## 8. PARTICIPATION, ROW BY ROW

`P(participates)` is a number for all six quarterbacks (0.952, 0.588, 0.581,
0.544, 0.209, 0.197) and `null` for all 13 non-quarterbacks, with a lower bound
in its place:

| player | P(participates) ≥ | P(zero opportunity) |
|---|--:|--:|
| KC WR1 | 0.981 | 0.019 |
| KC TE1 | 0.990 | 0.010 |
| KC RB1 | 0.854 | 0.150 (carries) / 0.275 (targets) |
| KC WR2 | 0.814 | 0.186 |
| KC TE3 | 0.190 | 0.810 |

The bound is the union of that player's modelled opportunities across layers.
RB1's 0.854 against a carry-zero rate of 0.150 is the gap the artifact cannot
close: in 4 of 1,000 draws he draws no carry but does draw a target, and
nothing in the file says whether the other 146 are absences or empty
appearances.
