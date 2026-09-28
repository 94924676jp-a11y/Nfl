# Where each gap stands, with the evidence and the blockers

Every number below was measured in this repository and is reproducible from the named module.
Where something is blocked, the blocker is a data request in `docs/AGENT_OUTBOX.md`, not an
unfinished thought. Nothing here is a recommendation and no wager is implied.

Read the status words strictly. **BUILT** means it runs and is tested. **MEASURED** means a number
exists with an interval. **PARTIAL** means it works and a named part of it does not. **BLOCKED**
means it cannot be done here and says what would unblock it.

## The development order the owner fixed, and what happened

| # | Step | Status | The number that says so |
|---|---|---|---|
| 1 | Historical warehouse from 2000 | BUILT | 13,982 club-games 2000–2026; 27,577 player-games; 17,721 role rows; 945 statistic-seasons in the coverage ledger |
| 2 | V1 complete projections | BUILT | 457 rosterable players, every one with a state; no player silently absent |
| 3 | Forward-chained calibration | BUILT | MAE 4.824, bias +0.012, rank correlation 0.446 on held-out 2024–25 |
| 4 | Optimiser / search quality | BUILT, PROVEN | exact 172.31 against a 171.59 floor; verified against brute force on value and roster |
| 5 | Ownership / field model | PARTIAL | identities exact, generator reproduces its marginals to 0.00079; ownership LEVEL uncalibrated |
| 6 | Joint game simulation | PARTIAL | 7 of 16 pair correlations reproduced inside a predeclared tolerance, 4 inside the measured interval |
| 7 | Contest-aware portfolio | BUILT | P(one entry in the top 1%) 0.4775 → 0.7575, a 1.59× improvement |
| 8 | Real-time automation | BUILT | 14 stages with declared freshness tolerances; the Saturday rule passes |
| 9 | SIM_OPTIMAL | NOT_CLAIMED | deliberately: the field level is uncalibrated and the entry selection is parameter-dependent |

## What is genuinely blocked, and on what

**Archived contest ownership (OUT-040).** Blocks the ownership *level*, duplication, chalk-failure
study, and which specific 48 entries to entER. Does **not** block the method: joint selection beats
independent selection at every field setting tested, by 0.18 to 0.32 absolute.

**Defensive and return touchdowns (OUT-041).** Every defensive projection is a **floor**, and the
understatement sits in the upside tail, which is the part a tournament portfolio is selected on.

**Play-by-play 2000–2020 (OUT-039) and historical rosters (OUT-038).** Play detail before 2021
reads `UNKNOWN_PENDING_ACQUISITION`, never zero.

## The findings a future session should not re-derive

- **Same-club receivers are positively correlated**, +0.170. Cannibalisation does not dominate at
  the WR1/WR2 level; the shared game environment does.
- **Opposing players are positively correlated**: +0.153 for the two quarterbacks, +0.093 for the
  two lead receivers. Shootouts lift both sides.
- **The same-club stack and the bring-back move opposite ways with the total.** Same-club QB~WR1
  falls 0.424 → 0.332 as the total rises; bring-back rises 0.033 → 0.152.
- **Stacking a quarterback with his WR1 doubles the chance both go big**, 2.03× over independence
  (interval 1.83–2.22). Quarterback with his own back shows **no** established lift, 1.07
  (0.89–1.24).
- **Clubs trade passes against runs**: corr(pass attempts, rush attempts) = −0.4255, and −0.3440
  even after points and margin. Two independent attempt regressions imply only −0.1407, which is
  why volume is parameterised as plays and pass share.
- **Losing a lead receiver makes a club pass LESS**, not more (−2.22 attempts, −2.7pp pass rate).
- **The market's implied club total explains r² = 0.156 of actual club scoring.** The simulator
  draws game totals around that line, so our club-level scoring view *is* the market's. Any edge
  has to come from allocation inside a club, not from disagreeing about team totals.
- **Carry shares are far more volatile than target shares**, 2.78× the multinomial variance against
  1.21×. A backfield is not a receiver rotation.

## The open architectural question

Hard reconciliation to a drawn club total makes the split between teammates zero-sum, so the two
backs come out at −0.249 against +0.000 measured, and adding share dispersion made it *worse*
because a Dirichlet moves work between them rather than creating it. Real football expands a club's
carry total when a back's role grows instead of taking carries off his teammate.

No parameter closes that. The next experiment is usage-first allocation with the club total derived
from the players rather than imposed on them, and it needs its own baseline and comparison. Three
other hypotheses for the same defect were tested and refuted first, one of them the hypothesis this
project had itself declared.

## Things that must not be done to make the numbers look better

- No per-pair correlation correction. A correlation produced by a fudge factor is the hand-added
  bonus the design forbids, and it would destroy the only property worth having.
- No external projection as a feature input, ever, by any path.
- No ownership synthesised to unblock a contest decision.
- No defensive touchdown rate invented to lift the defence floor.
- SIM_OPTIMAL stays unclaimed until the field level is calibrated.
