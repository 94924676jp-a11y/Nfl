# A1, isolated: GS against GSV

Two arms, 8,000 draws each, same game, same seed, same `written_at`, same code
version, both carrying SC2 so C3 completes. They differ in ONE declared flag:
`availability_feed`.

Both sealed clean: `shared_pass` = `PASS[C3_TARGET_BUDGET_FROM_THROWS]`,
`halted_at` null, components applied A1 A3G C0 **C3** R2 R5 R6 R8 R9 SC1
**SC2**, `not_reached` empty, no `c3_refusal`.

## What A1 actually changes: one player's eligibility, and nothing else

R8 was asked for P(appear) on both pools, same clock, same kickoff.

    coefficients identical (coef_sha256 equal)
    players whose P(appear) moves at all: 1
      Ty Johnson  0.970162  ->  REMOVED FROM THE POOL

**Every other player's appearance probability is bit-identical.** A1 does not
reweight anybody. It removes a player the feed lists OUT -- published
2026-09-14T20:16Z, designation "Out", hamstring, secondary attributed report --
and the existing football mechanisms deal his share.

That is worth stating plainly because the previous comparison could not say it.
G at 1,000 draws against GA at 8,000 differed in the draw count, the appearance
mechanism, the availability evidence, AND whether C3's second half completed.
This differs in one flag.

## Carries: the A1 category multinomial is untouched, the P4C simplex deals

The `rb` category level is IDENTICAL between arms, which is the point -- A1's
partition does not know who is in the pool.

| | GS | GSV | change |
|---|---|---|---|
| BUF `rush_category.rb` mean carries | 22.1195 | 22.1195 | **+0.0000** |
| closure `max abs(sum_i carries_i + pool - rb)` | **0.0** | **0.0** | exact in every draw |

Johnson released **4.3350** mean carries. **4.3350** reappear. Residual zero.

| | GS E[share] | renormalisation predicts | GSV E[share] | pred - actual | GS carries | GSV carries | delta |
|---|---|---|---|---|---|---|---|
| James Cook | 0.477002 | 0.593114 | 0.564251 | +0.028863 | 10.563 | 12.490 | **+1.926** |
| Ray Davis | 0.207457 | 0.257957 | 0.260622 | -0.002665 | 4.560 | 5.740 | **+1.180** |
| Frank Gore Jr. | 0.105610 | 0.131318 | 0.150457 | -0.019139 | 2.337 | 3.340 | **+1.003** |
| unmodelled back pool | 0.014164 | 0.017611 | 0.024670 | -0.007059 | 0.325 | 0.550 | +0.225 |

Johnson's share was 0.195767. The deviations from pure renormalisation are
small -- Cook +0.029, Gore -0.019, Davis -0.003 -- because the P4C weights are
conditional on who appears, so removing a back changes the conditional set
slightly. **Nothing was assigned by hand.**

Against the earlier confounded G-to-GA read, where the same deviations were
+0.078 and -0.097: that gap was the appearance mechanism moving at the same
time, and it is now gone.

## Targets: the same closure on the receiving side

| | GS | GSV | change |
|---|---|---|---|
| BUF named-receiver targets | 30.5609 | 30.5640 | +0.0031 |
| BUF stored `team_targets` | 30.9148 | 30.9148 | **+0.0000** |

Johnson released **2.0086** mean targets; **2.0117** recovered across the
thirteen remaining BUF receivers, the -0.0031 residue coming off the
unmodelled-receiver pool. Largest movers: Shakir +0.392, Moore +0.248, Coleman
+0.243, Knox +0.201, Kincaid +0.155, Cook +0.132.

**No cross-team compensation.** DET's named-receiver targets move +0.0130 on
8,000 draws, which is Monte Carlo noise and not a transfer; DET's backs move
-0.08 and -0.02 carries against Johnson's 4.3350.

## What this does NOT establish

- It is ONE game. A1 is an eligibility rule, not a fitted quantity, so there is
  nothing here to overfit -- but there is also nothing here that generalises.
- The evidence removing Johnson is a SECONDARY ATTRIBUTED REPORT, not an
  official declaration. It outranks nothing; it is simply the only current
  evidence that exists, because every 2026 official injury capture carries
  week 1 only.
- Doubtful and Questionable still move nobody. No calibrated transition exists
  for them and none was fabricated.
- GSP and GSVP were NOT run. They consume the survivorship-filtered week-1
  panel and are disqualified until it is rebuilt --
  `nfl/research/sc2/W1_PANEL_SURVIVORSHIP.md`. **No A2 effect is claimed here,
  clean or otherwise.**

V2 NOT YET EARNED.
