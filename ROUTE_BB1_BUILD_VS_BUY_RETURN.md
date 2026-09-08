# ROUTE-BB1 — CLEAN-ROOM ROUTE PARTICIPATION, BUILD vs BUY

**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`
**Pre-registration** `nfl/research/rbb1/predeclaration_rbb1.md`, sha256
`8d7383bf7f2a7a909f501d9395abf365becb05cdd9d3f243287aa3daa0bc5512`, committed
before any result existed.
**Addendum** `nfl/research/rbb1/addendum_rbb1_defects.md`, committed before the
corrected run.

## DECISION: `DATA_BLOCKED_BUY_CANDIDATE`
## §G: `CONTRACT_GATED` — the FTN sample was NOT unblinded

**FTN sample sealed at** `56fc32e21cb130c1e14a8b3817f0c43491b310e69cfd4663b5bbd5d973ccffa4`
(1,862,143 bytes), hashed before any work and **not used**. No FTN observation
entered any input, label, feature, threshold or selection decision.

G0A remains 11/12. NFL-1 remains NOT AUTHORIZED. No production model was
touched. Nothing was promoted. No FTN system was accessed or scraped.

---

## 1. The short answer

**No — not from anything we can legally reach today.** The specific primitive
you identified (*did this player run a route, or stay in and block?*) is not
present, derivable, or reliably inferable from any unrestricted source
available to this project. That is a **verified** finding, not a guess, and it
was found independently by two workers before this packet.

But the more useful result is the second one, and it changes how the $5,000
should be judged:

**A route denominator is worth exactly nothing unless it varies from game to
game.** I predicted this algebraically in the pre-registration and then
measured it: a route participation rate that depends only on position cancels
out of the architecture completely. Measured gain **+0.0074 CRPS**
[+0.0060, +0.0087] — very slightly *worse* than doing nothing, from rounding.

So "routes run" is not automatically better than "pass snaps". It is better
only to the extent that it tells us something *new about this particular
player in this particular game*. That is the thing to buy, and it is the thing
to test before buying.

---

## 2. Source inventory and licensing (§B)

Every source the project holds or can reach, classified. **No FTN-derived
observation entered this audit.**

| source | routes? | licensing | usable prospectively | notes |
|---|---|---|---|---|
| `pbp_participation` (nflverse) | **proxy only** | free, unrestricted | yes 2016–2025, **404 for 2026** | `offense_players` gives who was on the field per play. This is the closest thing to routes and it is *not* routes. |
| `pbp` (nflverse play-by-play) | no | free | yes | targets, air yards, sacks, scrambles |
| `participation.route` | **NO — see §3** | free | n/a | the *targeted* receiver's route, one scalar per play |
| `participation.ngs_air_yards` | no | free | no | **SOURCE EMPTY** — 0 non-null of 45,919 |
| `snap_counts` | no | free | yes | game-level totals, no play detail |
| `depth_charts` | no | free | yes | pre-play role hint only |
| `weekly_rosters` | no | free | **`status` forbidden** as prediction-time eligibility | |
| `official_injury_report`, `official_inactives` | no | free | yes | availability, not usage |
| PFF / Sports Info Solutions | yes | **paid, restricted** | — | not licensed; out of scope |
| **FTN** | yes | **draft contract, unsigned** | — | §7 |

**Availability caveat, stated plainly:** this container has **no egress** and
`pbp_participation` is registered `watch_only` and is never fetched here, so I
could not re-measure the play-level fields today. The findings in §3 are the
project's own **VERIFIED** measurements from `W4_RECEIVER_OPPORTUNITY.md`,
taken when the file was reachable, with the measurement code and counts
recorded. I am reporting prior verified measurements, not fresh ones, and
saying so.

What I *did* measure directly: `panel_p3.csv.gz`, 57,670 player-games
2020–2025, of which **33,952** are WR/TE/RB with `pass_snaps ≥ 1`.

---

## 3. Identifiability (§C) — the negative finding, and it is solid

**`participation.route` cannot support routes run.** Measured on 45,919 rows:

- **14 distinct values**, one scalar per play; **zero rows contain a `;`** — it
  is not a delimited per-player list.
- **26,809 of 45,919 are empty.** Of the 19,110 non-empty, **18,006** are
  `pass_attempt == 1` and **17,611** carry a `receiver_player_id`.
- Mean air yards conditioned on the label separates by **28 yards** (GO +24.86
  → SCREEN −3.18). If it described the *play* rather than the *target*, it
  could not.

It is the route of the **targeted** receiver. Conditioning on it means
conditioning on the outcome.

**What does exist, and it is genuinely strong:** `offense_players` is a
positionally-aligned gsis_id list; `n_offense == 11` on 45,906 of 45,919 rows;
and on **17,013 of 17,013** regular-season targets the targeted receiver was
present. Zero missingness on pass plays.

That gives `pass_snaps` — *the player was on the field for a team dropback*.
It is an **upper bound** on route participation. The gap between it and true
routes is **pass protection and chip responsibility**: near-zero for WRs,
moderate for TEs, large for RBs.

### Classification, per position

| position | `route_run` identifiability | why |
|---|---|---|
| **WR** | `PROBABILISTICALLY_INFERABLE` (weakly) — level only | almost always runs a route; the level is knowable, the *variation* is not |
| **TE** | `NOT_IDENTIFIABLE` | block-vs-release is exactly what is unobserved |
| **RB** | `NOT_IDENTIFIABLE` | pass protection is the dominant alternative assignment and is invisible |

**Nothing is `DIRECTLY_OBSERVED` or `DETERMINISTICALLY_DERIVABLE`.** Per §D I
did not force an estimator, because the information to fit or score one does
not exist — there are no labels, so an estimator's accuracy would be
unmeasurable by construction.

---

## 4. The experiment that works without labels (§D–§F)

Since no route label exists, I could not fit an estimator and measure it. So
the experiment runs the other way, and asks the question the purchase decision
actually turns on:

> **If route knowledge explained a fraction ρ of the error our current
> architecture makes, what would that be worth?**

`CONTROL` — accepted architecture, `pass_snaps → targets per pass snap`.
`ORACLE-ρ` — route denominator that closes fraction ρ of the control's residual.
Frame: 22,348 WR/TE/RB player-games, 2022–2025, walk-forward, prior-only.
Game-clustered bootstrap, 400 resamples.

| ρ | control CRPS | oracle CRPS | gain | gain % | 95% CI | accounting violations | constrained gain % |
|---|---|---|---|---|---|---|---|
| **0.00** | 0.86268 | 0.87020 | −0.0075 | **−0.87%** | [−0.0089, −0.0060] | 0.0% | −0.87% |
| 0.05 | 0.86268 | 0.82193 | +0.0408 | +4.72% | [+0.0394, +0.0423] | 1.0% | +4.78% |
| 0.10 | 0.86268 | 0.77390 | +0.0888 | +10.29% | [+0.0869, +0.0907] | 3.0% | +10.08% |
| 0.20 | 0.86268 | 0.68437 | +0.1783 | +20.67% | [+0.1750, +0.1816] | 8.0% | +18.92% |
| 0.30 | 0.86268 | 0.59924 | +0.2635 | +30.54% | [+0.2588, +0.2681] | 11.7% | +26.64% |
| 0.50 | 0.86268 | 0.45407 | +0.4086 | +47.37% | [+0.4015, +0.4156] | 17.1% | +38.69% |

**The ρ = 0 row is the placebo and it is the most important row in the table.**
A route denominator with a position-constant rate — real routes, correct
levels, no game-to-game information — is worth **−0.87%**. Not zero because of
integer rounding; certainly not positive. This is the pre-registered claim,
confirmed by measurement rather than asserted.

Above that, the gain is close to linear: **roughly 0.95 × ρ in CRPS percent.**

### The hard ceiling from football accounting

Route knowledge changes *only the denominator*, and routes can never exceed the
dropbacks a player was on the field for. So the achievable predicted mean is
bounded to `[0, pass_snaps × targets-per-route]`. Computing the best feasible
value per player-game:

| | ρ_max | rows unreachable even at routes = pass_snaps |
|---|---|---|
| **pooled** | **0.756** | 23.9% |
| WR | 0.636 | 36.3% |
| TE | 0.813 | 21.7% |
| RB | 0.969 | 5.6% |

**Read this correctly.** It is an upper bound on an upper bound — it asks what
a denominator chosen *with hindsight* could achieve, which no dataset can do.
Its only use is as a necessary condition, and the answer is that **accounting
does not rule route value out.** The ceiling is high; the binding unknown is
elsewhere.

---

## 5. What is actually blocking the decision

Everything above prices the information. None of it measures **how much route
information FTN actually carries** — that is ρ, and ρ cannot be estimated
without route labels.

That is the whole blockage, and it is clean:

- ρ = 0.05 would be worth ~4.7% target CRPS. ρ = 0.20 would be worth ~20%.
- ρ is unmeasured and **unmeasurable from any source we can legally reach.**
- The one sample that could estimate it is contract-gated (§7).

**This is why the classification is `DATA_BLOCKED_BUY_CANDIDATE` and not
`BUILD`.** We cannot build the primitive; we also cannot yet say the primitive
is worth $5,000. Those are different statements and both are true.

---

## 6. Accounting (§E)

| check | result |
|---|---|
| routes < 0 | **0** of 33,952 |
| routes > pass_snaps | **0** of 33,952 (holds by construction, `p ≤ 1`) |
| rate clipped at p = 1 | **4,389** — counted and reported, not hidden |
| per-row draw SD | **1.437** (asserted > 0; see §8) |
| CRPS ≠ MAE | asserted (0.8627 vs 1.2682) |
| accounting violations in the ρ sweep | reported per ρ, **never clipped silently**; constrained and unconstrained gains reported side by side |

---

## 7. §G — CONTRACT_GATED. The sample was not unblinded.

I read the contract in full before touching the sample beyond its hash. The
gate fails, for four independent reasons:

1. **The agreement is a DRAFT and is UNSIGNED.** Both signature blocks are
   blank, both date lines are blank, and the counterparty is the placeholder
   `[business name]`. No agreement is in force.
2. **§6.1 grants a licence to "Client"** — a party under an executed
   agreement. We are not a Client.
3. **§5.2** restricts API data to "Client's property" with access limited to
   authorized personnel and not shared with third parties.
4. **There is no evaluation, trial, sample or pre-contract clause anywhere in
   the document.** The agreement is silent on materials supplied before
   execution, so it grants nothing covering this file.

Your own instruction was that if permitted use is unclear, do not perform §G
and mark it `CONTRACT_GATED`. It is not merely unclear — the only grant present
is conditioned on being a Client, and we are not one. **So §G was not
performed. No precision, recall, F1, confusion matrix or route-count error was
computed.**

**What I did read, and why:** the file is named `participation_1.json`, and
nflverse publishes a dataset called `participation`. I could not classify a
source without identifying it, so I read the envelope only — top-level keys
(`event`, `plays`), and the event block, which identifies FTN's own API schema
(their internal `event.id 30351`, `league.id 3`, `participants [125,126]` — not
nflverse `game_id`/`gsis_id` format), DAL@PHI, 2025-09-04, 156 plays. I then
stopped. **I did not read a single play record and did not look at the role
taxonomy.** That was the minimum to establish provenance and nothing more.

**This is the cheapest unblocking step available to you**, and it is a
commercial question rather than a technical one: ask FTN for written permission
to use the sample for internal evaluation, or for a short trial. One game is
diagnostic rather than confirmatory — but as you said, 95% agreement and 65%
agreement should lead to very different decisions, and right now we have
neither number.

---

## 8. Three defects in my own work, found and fixed

Recorded in `addendum_rbb1_defects.md`, committed **before** the corrected run.

The first run reported that a position-constant route rate — a denominator
carrying **no information at all** — improved CRPS by −0.0599 with a
comfortably significant interval. **A placebo returning a result is a defect,
not a discovery**, so I did not report it and went looking for the cause.

1. **Zero dispersion.** `rng.binomial(n, rate)` was called without `size=m`,
   returning a scalar that numpy broadcast across all 400 draw columns. Every
   row was a point mass — mean per-row SD **0.000**, and reported CRPS equalled
   reported MAE to four decimals, which is the tell. **This is the third time
   in this project a distribution has been replaced by a point** (R1 by
   substitution, QB2 by rounding, here by a missing keyword). The recurrence is
   worth more than the instance; the corrected run now *asserts* SD > 0 and
   CRPS ≠ MAE so it cannot recur silently.
2. **The shrinkage prior was in the wrong units.** It is a rate *per unit of
   denominator*, and the same constant was used for pass-snaps and for routes.
   Those are different units, so the level failed to cancel and point
   predictions differed by **1.52 targets** between arms that should have been
   identical.
3. **The original necessity curve measured the wrong thing.** An injected route
   rate has no causal connection to the real observed targets, so raising its
   dispersion only corrupts the denominator — the oracle got *worse* the more
   it "knew", running from −0.060 to **+0.084**. Redesigned to sweep ρ, which
   is decision-relevant and needs no labels.

---

## 9. Limitations

- **No fresh play-level measurement.** No egress here; §3 relies on the
  project's own prior VERIFIED measurements rather than a re-run today.
- **ρ is not measured.** It cannot be, without labels. Every number in §4
  prices information; none measures how much FTN has.
- **The ceiling is a bound on a bound**, not an achievable target.
- **The route participation levels** (WR 0.90, TE 0.70, RB 0.40) are assumed,
  not fitted — there is nothing to fit them to. They set the *level*, and §4
  shows the level cancels, so the conclusions do not rest on them. The ceiling
  in §4 does depend on them and would move if they are wrong.
- **One game is not validation**, even if §7 were ungated.
- All of this is **EXPLORATORY**. Nothing is promoted.

---

## 10. Recommendation

**Do not buy yet, and do not start building a route estimator.** Building one
is not blocked by engineering effort — it is blocked by the absence of any
label to fit or score against, which no amount of work here removes.

In order:

1. **Ask FTN for written permission to evaluate the sample** (or a short
   trial). This is a one-email commercial step and it converts the single
   unmeasured quantity into a measured one. Until then §G stays gated.
2. **When permission exists, measure ρ** — not precision or F1. The decision
   turns on how much of *our* residual error route data explains, and §4 is
   already built to convert that into CRPS.
3. **Then decide against the curve**: ρ ≈ 0.05 buys ~4.7%; ρ ≈ 0.20 buys ~20%.
   You would be setting your own threshold for what a percentage point of
   target CRPS is worth, which is a judgement about the project, not about FTN.

On your framing that owning the capability would beat renting the data: I
agree in principle, and it does not apply here. Route participation is a
**charting** product — a human or model watching each play and recording an
assignment. We cannot derive it from box-score or participation feeds because
the information was never recorded in them. Owning it would mean building a
charting operation, which is a different business, not a data pipeline.

**One thing worth saying plainly:** the most valuable result here may be the
placebo row. Had this experiment been run carelessly, a route denominator with
no information in it would have "improved" CRPS by 0.06 and looked like a
reason to spend $5,000. It took three of my own defects being found for that
number to go away.

---

## 11. Next experiment — only if §7 is ungated

`ROUTE-BB2`, and only then: with permitted use, measure ρ on the one game,
report it with its (wide, one-game) uncertainty, and convert it through §4's
curve. If permission is refused, there is no further technical work to do and
the decision becomes a commercial judgement under acknowledged uncertainty.

**THEN STOP** — as instructed, and this did not delay the production or T−90
work, which is untouched.

---

### Files

| path | what |
|---|---|
| `nfl/research/rbb1/predeclaration_rbb1.md` | pre-registration, hashed before results |
| `nfl/research/rbb1/addendum_rbb1_defects.md` | three defects, recorded before the repair |
| `nfl/research/rbb1/rbb1_lib.py` | frame, arms, ρ sweep, clustered bootstrap |
| `nfl/research/rbb1/run_rbb1.py` | the experiment |
| `nfl/research/rbb1/rbb1_results.json` | every number in this return |
| `nfl/research/rbb1/rbb1_ceiling.json` | the accounting ceiling |
