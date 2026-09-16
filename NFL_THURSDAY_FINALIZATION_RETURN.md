# Thursday finalization — what was asked, what was done, what was not

Branch `claude/nfl-greenfield-architecture-stsxmk`. Every number below is
measured from the artifact named beside it.

---

## 1. P3/P4/P5 are inside the governed pipeline

**Done.** Rushing yards, kicker outcomes and DraftKings points were being
assembled by a script that read the sealed npz afterwards and wrote its own
board. That board had no run identity, no provenance bundle and no
publication state. It is gone.

One forecast execution now seals passing, rushing, receiving, kicking and
scoring on one draw index. Sealed run `e58206e3e8473dc1`, 1000 draws:

| Layer | Rows | Metrics |
|---|---|---|
| `qb` | 4 | att cmp db int ptd pyds rtd rush_opp ryds sacks scr |
| `receiving` | 26 | targets receptions receiving_yards receiving_td |
| `rushing` | 7 | carries rushing_td **rushing_yards** |
| `kicking` | 2 | fga fgm xpa xpm, five distance bands attempted and made, offensive_td, dk_points |
| `gadget_rush` | 24 | kneel wr te |
| `dk_scoring` | 30 | dk_points |
| `rush_category` / `rush_player_pool` / `team_volume` | 2 each | the full rush partition and the team budget |

The coupling is proved, not asserted: the kicking layer's `offensive_td`
equals that team's own sealed touchdowns to **max |diff| 0.0 over 1000
draws**, and every DK total reproduces from the events sealed beside it to
**0.0**. `test_wired_product.py` 37 passed, 0 failed, 1 NOT_EXECUTED.

The one NOT_EXECUTED is honest: no player on this board rushes from both the
qb and rushing layers, so the summing branch did not run and is reported as
not run rather than green.

### Four defects found on the way

- **The kicker was named by hand for two clubs.** Now resolved from the
  roster capture through the graded participation classes, refused rather
  than guessed when a club has no unique game-roster kicker. The join moved
  from the printed `T.Bass` to `gsis_id`; an unmatched kicker had been
  falling back to league rates silently.
- **`kicking.simulate` drew extra points twice** — once to score its own DK
  total, once for the vector it returned — so the published `xpm` was not the
  one behind the published points. It now draws once and scores nothing;
  `dk_scoring` owns every point value and an unrecognised distance band
  raises instead of quietly scoring zero.
- **The slate runner's dry-run branch reported `EXECUTED`** beside "nothing
  was computed or sealed", and set no completeness — so `CP.summarise` raised
  `KeyError` and killed the whole slate. Now `PLANNED_NOT_EXECUTED_DRY_RUN`,
  counted separately in the summary.
- **Reuse ignored the code.** A slate run after a model change reused a board
  that model never produced and called it `REUSED`. Code version is now part
  of the reuse key, and a run that cannot resolve its own code identity does
  not get to reuse — unknown is not unchanged.

**There is no week-2 roster capture**, so the kicker is carried forward from
week 1. The artifact says
`CARRIED_FORWARD_FROM_WEEK_1_NO_CAPTURE_FOR_WEEK_2` beside the name, with the
participation class and whether the make rates are his own or the league's.

---

## 2. The 22,821 dropped historical carries

**Done, and they were not random.** Resolving rusher position from the 2026
roster alone dropped carries whose rusher has left the league:

| Season | Dropped |
|---|---|
| 2021 | 9,009 |
| 2022 | 6,744 |
| 2023 | 4,211 |
| 2024 | 2,232 |
| 2025 | 625 |

That gradient is the defect stating itself. 20,030 of the 22,821 are running
backs, across all 32 teams and 311 distinct rushers. By position: RB 20,030,
QB 1,736, WR 997, TE 25, P 12, DB 11, LB 10.

**Effect on the stratified control:**

| Stratum | Retained (roster-only) | Combined | Δ mean | In SE of the retained mean |
|---|---|---|---|---|
| RB | 4.3896, n 42,061 | **4.2902, n 62,044** | −0.0983 | **−3.22** |
| NON_RB | 4.6693, n 12,580 | **4.5809, n 15,418** | −0.0923 | −1.58 |

Both strata were biased **up**. `p_stuff` and `p_exp` move by under 0.005, so
the shape survived and the level did not.

**Resolved from historical evidence, not a wider 2026 roster.** `panel_p3`
carries gsis_id and position for 2020–2025 and resolves all 22,821 — it knows
what the player was in the season he took the carry. Where both bridges speak
they disagree on 6 rushers of 1,102, worth 49 carries; the panel wins, because
the position governing a 2021 carry is the position he played in 2021.

`SURVIVORSHIP_AUDIT.json` carries the full breakdown.
`test_rushing_survivorship.py` 15/0 — it reproduces the roster-only bridge
first and asserts it still drops carries, so the fix is measured against a
live defect.

---

## 3. Unnamed football mass

**Done where identity exists, and deliberately not done where it does not.**

Before: BUF kneel 1.560 + wr 0.478 + te 0.058 + fringe 0.431 + unmodelled-back
pool 0.344 = **9.54%** of 30.08 carries belonging to nobody. DET **6.00%**.

Measured pre-cutoff, who actually takes them:

| Category | Carries | Finding |
|---|---|---|
| kneel | 2,212 | **100.0%** taken by a quarterback, 83.2% by the game's own primary passer |
| wr | 2,685 | busiest receiver takes a **median 100%**, mean 91.7%, of a team-game |
| te | 203 | 99.0% concentrated the same way |
| fringe | 132 | 28 DB, 26 P, 12 LB, 1 K, and 65 from 11 rushers with no position in any source held |

So three are allocated and fringe is not. **Unnamed mass 7.80% → 2.13%**, and
what remains is fringe plus the unmodelled-back pool, both unnamed on purpose:
their owners are punters and defensive backs who are on no offensive board,
and naming the pool would mean inventing the running back it exists to
represent.

All six team-by-category allocations conserve **exactly, 1000/1000 draws**,
in integers, and a kneel only ever goes to a quarterback.

### The coefficient, and the criterion I threw away

Weights are own prior carries + alpha. I first fitted alpha by matching the
mean top-share and it returned the smallest value on the grid every time —
because that statistic is **monotone in alpha**, and alpha = 0 asserts a
player with no prior carry can never take one. The moment-match hid exactly
the failure it should have punished. **Withdrawn, and recorded as withdrawn.**

Refitted by forward-scored log-loss of the actual owner: **wr 0.75** (1.2612
over 2,685 carries), **te 0.10** (0.7411 over 203). Both interior to the grid
[0.02, 5.0]; zero carries went to an owner outside the pool. Kneels are not
fitted — they go to the quarterback with the most dropbacks in that draw,
which reproduces the 83.2% rate as a consequence rather than a coefficient.

The allocation comes out slightly **less** concentrated than reality (0.873
against 0.917 for wr). Reported, not closed.

This changes what the board closes over, so it is **`V1_CANDIDATE_R9_W1P_G`**
with its own component and flag. R9_W1P is untouched and its sealed board
carries no gadget layer; the test asserts both. **Nothing is promoted.**
`test_gadget_rush.py` 36/0.

### What it does not do, stated because a reader would otherwise find it

It deals the **carry**, not the **yard**. A kneel, a jet sweep and a tight-end
run have a named owner and contribute nothing to his rushing yards. Measured:
a kneel is −1.0922 yards, a wr carry +5.5423, a te carry +2.7044. On this
board that is about **−1.64 rushing yards missing from Josh Allen** and
**+1.55 from Amon-Ra St. Brown**. Not closed here: a wr carry is a different
distribution from an RB carry (mean 5.54 vs 4.29, far heavier tail), so
routing it through the RB pool would be worse than leaving it out. It needs
its own stratum, which is another candidate.

---

## 4. Convergence and MCSE

**The predeclared criterion is not met at any draw count on the grid, and the
criterion is the binding constraint rather than the draw count.**
`DRAW_COUNT_PREDECLARATION.md` was written before the sweep ran;
`DRAW_COUNT_RESULT.md` carries the full tables.

| n | failing | binding quantity | MCSE vs tol |
|---|---|---|---|
| 1,000 | 778 | `qb/pyds@00-0034577` | 1.5808 vs 0.1246 |
| 2,000 | 590 | `kicking/made_FG50+.p75` | 0.1147 vs 0.0050 |
| 4,000 | 407 | `receiving/receptions.p90` | 0.1243 vs 0.0200 |
| 8,000 | 284 | `receiving/receptions.p75` | 0.1141 vs 0.0200 |
| 16,000 | 170 | `receiving/receptions.p75` | **0.1141** vs 0.0200 |

**Read the last two rows together.** Doubling the draws moved the binding
MCSE by **0.0000**. Its variability is discreteness, not Monte Carlo noise:
the quantile of a count supported on a handful of integers is a step function
and no `n` converges it.

Underneath, three classes separate cleanly:

- **Probabilities clear at 8,000** and stay clear — 148 failing at 1,000 down
  to 0.
- **Means fail only on low-usage players.** Not one failing mean at 16,000
  has a value of 50 or more; every headline number clears. What fails is a
  1%-relative tolerance on a 3.5-yard mean. Ratios 1.3–2.6, so ~110,000 draws
  would clear them.
- **Quantiles** are the unreachable class, for the reason above.

I did not extend the grid or relax a tolerance to make a point pass. What a
corrected predeclaration must say is written down for the next one and is not
applied retroactively.

**Separately, and a smaller claim:** at 1,000 draws a headline DK projection
carries 0.265 points of Monte Carlo error; at 8,000, 0.095. That is what the
draw count buys. It is not a convergence claim.

---

## 5. Gibbs and Cook, decomposed

Full table in `nfl/production/PROJECTION_DECOMPOSITION_DET_BUF.md`.

**Gibbs 23.37 carries / 98.9 yards.** Detroit's 29.21-carry budget →
quarterbacks take 7.19% → RB category 90.1% → Gibbs 88.8% of it against Sione
Vaki's 10.0% → 4.2303 realised yards per carry against a pool mean of 4.2902.

**Cook 10.56 / 44.4.** Buffalo's budget is **larger** at 30.08, but Josh
Allen takes **23.24%** of it against Goff's 7.20%, and Cook then takes 47.7%
of a four-back room where Gibbs takes 88.8% of a two-back one. Two separate
causes, and neither number is strange once they are separated.

### The one number that deserves a second look, and it is not a usage number

Cook's P(zero carries) is **0.175**, and **0.171** of that is worlds where he
does not play at all. Conditional on appearing he takes a carry 99.3% of the
time.

Queried directly, the frozen P3 appearance mechanism returns:

| Player | P(appear) |
|---|---|
| **James Cook (BUF, RB1)** | **0.7138** |
| Ray Davis (BUF, RB2) | 0.9733 |
| Jahmyr Gibbs (DET, RB1) | 0.9596 |

Buffalo's starter is rated below his own backup. Two facts locate it: Cook's
0.7138 is essentially the **training base rate, 0.6936** — the model is
returning roughly what it returns for an unknown player rather than judging
him — and **`n_with_an_injuries_row` is 0** for all three while 182 injury
rows exist for 2026, so two of five feature groups contribute nothing.

The leading hypothesis, that Cook's 2-snap week-18 rest game reads as
near-absence to a snap-weighted history, is **UNCONFIRMED**: reading the
feature row needs the appearance frame under a configured state root, which
this pass did not run.

**No projection was changed.** A number that looks unusual is not thereby
wrong, and Cook missing time is a real possibility the board is entitled to
carry. What is worth fixing is the reason — if the model sits at its base
rate because no injury row reached it, the repair is the **injury join**, and
it would move many players, not one. That is now the top-ranked lever on this
board.

---

## The complete board — sealed run `e58206e3e8473dc1`, 1000 draws

32 players, both kickers, DraftKings points at p10/p50/p90. This is the
artifact, not an assembly of it.

| Player | Tm | Pos | DK p10/50/90 | mean | projected line |
|---|---|---|---|---|---|
| Jahmyr Gibbs | DET | RB | 10 / 22 / 36 | 22.80 | 23.4 car / 99 rush yds; 4.3 tgt / 3.5 rec / 27 yds |
| Josh Allen | BUF | QB | 10 / 20 / 35 | 21.54 | 233 pass yds, 1.45 pass TD, 33 rush yds |
| Jared Goff | DET | QB | 8 / 17 / 29 | 17.62 | 255 pass yds, 1.55 pass TD, 5 rush yds |
| Amon-Ra St. Brown | DET | WR | 5 / 15 / 32 | 17.19 | 8.6 tgt / 6.3 rec / 73 yds |
| Khalil Shakir | BUF | WR | 1 / 8 / 22 | 10.03 | 4.9 tgt / 3.6 rec / 43 yds |
| Jameson Williams | DET | WR | 0 / 8 / 22 | 9.86 | 5.1 tgt / 3.1 rec / 50 yds |
| James Cook | BUF | RB | 0 / 8 / 19 | 9.21 | 10.6 car / 44 rush yds; 1.6 tgt / 1.3 rec / 11 yds |
| Sam LaPorta | DET | TE | 2 / 7 / 18 | 8.87 | 4.5 tgt / 3.4 rec / 38 yds |
| Jake Bates | DET | K | 3 / 8 / 14 | 8.11 | 1.92 FGA / 1.64 FGM / 2.20 XPM |
| Tyler Bass | BUF | K | 3 / 8 / 14 | 7.94 | 1.85 FGA / 1.56 FGM / 2.30 XPM |
| DJ Moore | BUF | WR | 0 / 5 / 15 | 6.41 | 3.6 tgt / 2.3 rec / 31 yds |
| Ty Johnson | BUF | RB | 0 / 4 / 14 | 5.83 | 4.1 car / 18 rush yds; 2.1 tgt / 1.4 rec / 15 yds |
| Dalton Kincaid | BUF | TE | 0 / 4 / 14 | 5.67 | 3.1 tgt / 2.3 rec / 24 yds |
| Ray Davis | BUF | RB | 0 / 4 / 13 | 5.53 | 4.8 car / 21 rush yds; 1.2 tgt / 1.0 rec / 11 yds |
| Keon Coleman | BUF | WR | 0 / 3 / 14 | 5.34 | 3.0 tgt / 1.7 rec / 25 yds |
| Dawson Knox | BUF | TE | 0 / 3 / 12 | 5.00 | 2.8 tgt / 1.9 rec / 22 yds |
| Josh Palmer | BUF | WR | 0 / 2 / 11 | 4.08 | 2.2 tgt / 1.5 rec / 19 yds |
| Brock Wright | DET | TE | 0 / 2 / 11 | 3.96 | 2.2 tgt / 1.7 rec / 15 yds |
| Sione Vaki | DET | RB | 0 / 1 / 9 | 3.22 | 2.6 car / 12 rush yds; 0.7 tgt / 0.6 rec / 7 yds |
| Isaac TeSlaa | DET | WR | 0 / 0 / 9 | 3.14 | 1.8 tgt / 1.1 rec / 15 yds |
| Tay Martin | DET | WR | 0 / 0 / 11 | 3.11 | 1.3 tgt / 0.9 rec / 17 yds |
| Jackson Hawes | BUF | TE | 0 / 0 / 8 | 2.78 | 1.3 tgt / 1.0 rec / 12 yds |
| Skyler Bell | BUF | WR | 0 / 0 / 9 | 2.75 | 1.7 tgt / 1.0 rec / 12 yds |
| Greg Dortch | BUF | WR | 0 / 0 / 9 | 2.42 | 1.3 tgt / 1.0 rec / 10 yds |
| Tyler Conklin | DET | TE | 0 / 0 / 8 | 2.38 | 1.4 tgt / 1.0 rec / 9 yds |
| Frank Gore Jr. | BUF | RB | 0 / 0 / 8 | 2.24 | 2.3 car / 10 rush yds; 0.6 tgt / 0.4 rec / 3 yds |
| Tom Kennedy | DET | WR | 0 / 0 / 8 | 2.07 | 1.2 tgt / 0.7 rec / 9 yds |
| Keleki Latu | BUF | TE | 0 / 0 / 6 | 1.99 | 1.0 tgt / 0.8 rec / 8 yds |
| Jackson Meeks | DET | TE | 0 / 0 / 5 | 1.63 | 0.9 tgt / 0.6 rec / 7 yds |
| Joshua Dobbs | DET | QB | 0 / 0 / 1 | 1.08 | 12 pass yds, 0.08 pass TD, 2 rush yds |
| Kyle Allen | BUF | QB | 0 / 0 / 1 | 0.81 | 12 pass yds, 0.06 pass TD, 1 rush yds |
| Jacob Saylors | DET | RB | 0 / 0 / 0 | 0.00 | 0.0 car / 0 rush yds; 0.0 tgt / 0.0 rec / 0 yds |

---

## 6. External universe reconciliation — FanDuel DET-BUF template

All 45 rows accounted for; the buckets are asserted to sum. Salary, FPPG,
tier and the MVP multiplier are read and **discarded in code**. The injury
indicator is carried as attributed information, never as a declaration.

| bucket | n |
|---|---|
| in the opportunity pool | 32 |
| excluded (practice squad / reserve) | 11 |
| defence units, out of scope | 2 |
| not found internally | **0** |

### What it caught — three players we should not have been paying

| Player | Tm | Class | Gadget carries/game |
|---|---|---|---|
| Tyrell Shavers | BUF | RESERVE | 0.039 |
| Trent Sherfield | BUF | PRACTICE_SQUAD | 0.036 |
| Lucky Jackson | DET | PRACTICE_SQUAD | 0.004 |

`gadget_rush.pool` selected on **position alone**. Every other layer already
honoured the rule: receiving, rushing, qb and dk_scoring carried zero
non-game-roster rows. The pool now classifies; players off the game roster
are **held with their class recorded**, and UNKNOWN is held too rather than
resolved by default in either direction. Gadget rows 24 to 21, conservation
still exact 1000/1000.

### Two of my own matcher bugs, found the same way

It first reported Buffalo's **starting running back as missing internally**:
`_norm` stripped suffixes by ordered substring replace with `' ii'` before
`' iii'`, so "James Cook III" folded to `james cooki`. And "Joshua Palmer" is
"Josh Palmer", which no folding of the full string makes equal. Suffixes now
strip as whole trailing tokens longest-first, with a
`(surname, club, position)` fallback that **refuses** an ambiguous key rather
than picking — two Allens quarterback in this game.

### Two findings left standing, both information rather than defects

**Ty Johnson** — the file marks him Questionable (Hamstring). We carry
`ACTIVE_ROSTER_EXPECTED` from the week-1 capture and give him 4.1 carries and
2.1 targets, because **no 2026 week-2 injury row reaches this engine at all**.
Not silently applied. It is the same gap the decomposition ranked as the top
lever.

**Jackson Meeks** — the file says WR, our roster capture says TE with
`depth_chart_position` TE and status ACT. The roster governs, so he stays in
the TE gadget pool. Recorded because it changes which pool his carries are
drawn from.

Nothing was excluded on FanDuel's authority: every exclusion cites a
participation class from our own roster capture.

### Full row-by-row table

| FanDuel player | FD team | FD pos | internal identity | internal roster state | simulation eligibility | expected role state | reason if excluded |
|---|---|---|---|---|---|---|---|
| Tyler Bass | BUF | K | 00-0036162 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | SECONDARY_UNIVERSE | — |
| Josh Allen | BUF | QB | 00-0034857 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Kyle Allen | BUF | QB | 00-0034577 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Frank Gore Jr. | BUF | RB | 00-0039471 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| James Cook III | BUF | RB | 00-0037248 (James Cook) | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Ray Davis | BUF | RB | 00-0039875 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Ty Johnson | BUF | RB | 00-0035537 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Dalton Kincaid | BUF | TE | 00-0038933 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Dawson Knox | BUF | TE | 00-0035689 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Jackson Hawes | BUF | TE | 00-0040194 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Keleki Latu | BUF | TE | 00-0040363 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| DJ Moore | BUF | WR | 00-0034827 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Greg Dortch | BUF | WR | 00-0035500 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Joshua Palmer | BUF | WR | 00-0036988 (Josh Palmer) | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Keon Coleman | BUF | WR | 00-0039901 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Khalil Shakir | BUF | WR | 00-0037261 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Skyler Bell | BUF | WR | 00-0041443 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Jake Bates | DET | K | 00-0039172 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | SECONDARY_UNIVERSE | — |
| Jared Goff | DET | QB | 00-0033106 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Joshua Dobbs | DET | QB | 00-0033949 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Jacob Saylors | DET | RB | 00-0038896 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Jahmyr Gibbs | DET | RB | 00-0039139 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Sione Vaki | DET | RB | 00-0039364 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Brock Wright | DET | TE | 00-0036754 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Sam LaPorta | DET | TE | 00-0039065 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Tyler Conklin | DET | TE | 00-0034270 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Amon-Ra St. Brown | DET | WR | 00-0036963 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Isaac TeSlaa | DET | WR | 00-0040669 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Jackson Meeks | DET | WR | 00-0040390 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Jameson Williams | DET | WR | 00-0037240 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Tay Martin | DET | WR | 00-0037524 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Tom Kennedy | DET | WR | 00-0035544 | ACTIVE_ROSTER_EXPECTED | IN_OPPORTUNITY_POOL | DISPLAYED | — |
| Shane Buechele | BUF | QB | 00-0036679 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Ja'Mori Maclin | BUF | WR | 00-0041272 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Stephen Gosnell | BUF | WR | 00-0040361 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Trent Sherfield Sr. | BUF | WR | 00-0034487 (Trent Sherfield) | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Luke Altmyer | DET | QB | 00-0041453 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Isiah Pacheco | DET | RB | 00-0037197 | RESERVE | EXCLUDED | NOT_IN_UNIVERSE | participation class RESERVE; NOT_GAME_ROSTER |
| Jabari Small | DET | RB | 00-0039652 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Thomas Gordon | DET | TE | 00-0040697 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Dominic Lovett | DET | WR | 00-0040241 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Kendrick Law | DET | WR | 00-0041446 | RESERVE | EXCLUDED | NOT_IN_UNIVERSE | participation class RESERVE; NOT_GAME_ROSTER |
| Lucky Jackson | DET | WR | 00-0038181 | PRACTICE_SQUAD | EXCLUDED | NOT_IN_UNIVERSE | participation class PRACTICE_SQUAD; NOT_GAME_ROSTER |
| Buffalo Bills | BUF | D | — | TEAM_UNIT | NOT_MODELLED | OUT_OF_SCOPE | a defence/special-teams unit is not a player and this engine models no defensive scoring at all |
| Detroit Lions | DET | D | — | TEAM_UNIT | NOT_MODELLED | OUT_OF_SCOPE | a defence/special-teams unit is not a player and this engine models no defensive scoring at all |

---

## Standing constraints, honoured

- No sportsbook, FantasyCruncher or external projection was used as a
  predictive input. The kicker screenshots were used for schema only.
- Every existing seal is byte-identical. No frozen arm was edited: every
  closure change took a new candidate identity.
- The suite and sweep results are reported as measured, including what
  did not clear.
- **Nothing is promoted.**
