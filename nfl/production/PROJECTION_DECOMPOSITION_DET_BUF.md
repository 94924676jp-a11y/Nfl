# Where Gibbs' and Cook's numbers come from

Run `690f6d51924121f7`, digest `ad207096a9ed413f`, candidate
`V1_CANDIDATE_R9_W1P_G`, 1,000 draws, DET at BUF, 2026 week 2. Every figure
below is measured from that sealed artifact, not recalled.

**This supersedes the first version of this file, which cited run
`caa597a936ea45d4`.** That run was built before the tag-seeded RNG streams
were made stable across processes, so its rushing yards were not re-derivable
from its own seed and the run has been replaced rather than quoted. Every
COUNT is identical between the two -- the defect touched only quantities
drawn through a tag-seeded stream. The yards moved: Gibbs 101.0 to 98.9, Cook
45.7 to 44.4. The numbers here are reproducible; those were not.

Nothing here is a proposal to change a projection. The point is that a reader
should be able to follow a number from the team budget down to the yard, and
say which step is carrying an assumption.

## Jahmyr Gibbs — 23.37 carries, 98.9 rushing yards

| Step | Quantity | Where it comes from |
|---|---|---|
| 1 | Team rush budget **29.21** (sd 6.95, p10 20, p90 38) | D1 team-volume forecast, integerised. **Historical prior**, with the standing warning `team_volume_is_near_unforecastable` |
| 2 | Detroit's quarterbacks take **7.20%** — scrambles 0.90, designed 0.56, kneels 0.64 | A1 multinomial over the rush-play budget, **historical prior** per team. Goff is not a rushing quarterback and the split says so |
| 2 | WR gadget 0.58, TE gadget 0.04, fringe 0.16 | **Historical prior**, now allocated to named players (R9_W1P_G) |
| 2 | **RB category 26.32 = 90.1% of the team** | residual of the same multinomial. Closes exactly, 1000/1000 draws |
| 3 | Gibbs takes **88.8%** of the RB category | P4C simplex. **Depth-role state** (RB1) and **2026 week-1 evidence** (57 snaps, 29 carries). Sione Vaki 10.0%, unmodelled pool 1.2% |
| 4 | **23.37 carries** (sd 7.88, p10 13, p50 24, p90 33) | steps 1–3 compounded |
| 5 | **98.9 yards** (p10 47, p50 94, p90 155) | emp_tilt system A, RB stratum, **every carry drawn individually**. Realised 4.2303 yd/carry against a pool mean of 4.2902 |

Gibbs' P(zero carries) is **0.008**, and 0.007 of that is worlds where he is
absent from the game entirely.

## James Cook — 10.56 carries, 44.4 rushing yards

| Step | Quantity | Where it comes from |
|---|---|---|
| 1 | Team rush budget **30.08** (sd 6.87, p10 21, p90 38) | D1, **historical prior**. Buffalo's is slightly LARGER than Detroit's |
| 2 | Buffalo's quarterbacks take **23.24%** — scrambles 2.53, designed 2.90, kneels 1.56 | A1, **historical prior**. This is Josh Allen and it is football-correct |
| 2 | WR gadget 0.48, TE gadget 0.06, fringe 0.43 | **historical prior**, allocated |
| 2 | **RB category 22.12 = 73.5% of the team** | residual. Sixteen points of team share below Detroit's, entirely because of the quarterback |
| 3 | Cook takes **47.7%** of the RB category | P4C simplex. **Depth-role state** (RB1) and **2026 week-1 evidence** (42 snaps, 13 carries). Ray Davis 21.9%, Ty Johnson 18.4%, Frank Gore Jr. 10.4%, pool 1.6% — a four-back room against Detroit's two |
| 4 | **10.56 carries** (sd 7.70, p10 0, p50 10, p90 20) | steps 1–3 compounded |
| 5 | **44.4 yards** (p10 0, p50 40, p90 93) | same conversion. Realised 4.2067 yd/carry |

## The one number on this board that deserves a second look

**Cook's P(zero carries) is 0.175, and 0.171 of it is "absent from the
game".** Detroit's RB1 gets 0.007. Conditional on appearing, Cook takes a
carry in 99.3% of worlds — so this is not a usage question, it is an
availability one.

Queried directly, the frozen P3 appearance mechanism
(`appearance-p3-logistic-frozen`, coef `8734c5a31201f772`, trained 2020–2025
on 83,144 rows) returns:

| Player | P(appear) |
|---|---|
| James Cook (BUF, RB1) | **0.7138** |
| Ray Davis (BUF, RB2) | 0.8781 |
| Jahmyr Gibbs (DET, RB1) | 0.9596 |

Buffalo's starter is rated less likely to play than his own backup. Two facts
locate it:

1. **Cook's 0.7138 is essentially the training base rate, 0.6936.** The model
   is not making a player-specific judgement about him; it is returning
   roughly what it returns for an unknown player.
2. **`n_with_an_injuries_row` is 0 for all three**, while 182 injury rows
   exist for 2026. No injury evidence reached any of them, so the
   `practice_progression` and `teammate_availability` feature groups are
   contributing nothing, and the mechanism is running on absence history
   alone.

Cook played 2026 week 1 (42 snaps, 13 carries) and 2025 week 18 — but week 18
was a 2-snap rest game, which is the kind of row a snap-weighted absence
history reads as near-absence. **That is the leading hypothesis and it is NOT
confirmed here**: reading the feature row requires the appearance frame under
a configured state root, which this pass did not run. It is recorded as
unconfirmed rather than asserted.

**No projection is changed on the strength of this.** A number that looks
unusual is not thereby wrong, and Cook missing time is a real possibility
that the board is entitled to carry. What is worth fixing is the *reason*:
if the model is at its base rate because no injury row reached it, then the
fix is the injury join, not the projection — and it would move several
players, not one.

## What each step would take to improve, ranked by how much it moves

1. **The appearance/injury join.** It is the largest single lever on this
   board and it currently contributes nothing. 182 injury rows exist and zero
   reached these players.
2. **The team rush budget**, which carries `team_volume_is_near_unforecastable`
   on its own warning list. Its sd of ~6.9 carries on a mean of ~29.5 is the
   dominant variance in step 1.
3. **The RB-room split**, which is the difference between an 88.8% share and
   a 47.7% one and rests on one game of 2026 evidence plus a depth chart.
4. **The per-carry conversion**, which is the best-evidenced step here:
   62,044 RB carries, survivorship removed, and the only one of the five with
   a measured sensitivity attached to it.

## What this decomposition does not establish

It shows where each number comes from. It does not show that any of them is
right. Every step is a **historical prior conditioned on a depth chart and
one game of current-season evidence**, and none of it has been scored against
a 2026 week-2 outcome, because that game has not been played.
