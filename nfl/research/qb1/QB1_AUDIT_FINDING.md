# QB1 — definition audit. Decomposition NOT run.

**Status: `BASELINED` (audit only).** The QB oracle decomposition of Stage 4 was
**not run** in this session and is recorded as open in
`nfl/TECHNICAL_DEBT_REGISTRY.json` as `DEBT-QB-LAYER`. What follows is the
definition audit §4.1 requires, which is the part that had to come first and
which changes how any later decomposition must be built.

Measured over 2022–2025, REG, non-two-point, `play_type != no_play`.

## The trap, confirmed and quantified

**`pass_attempt` includes sacks — 5,308 of 5,308.** It also includes spikes —
278 of 278. So the intuitive identity is wrong:

| | |
|---|---|
| **WRONG** | `attempts = dropbacks − sacks − scrambles` |
| **RIGHT** | `dropbacks = pass_attempts + scrambles − spikes` |

The wrong form is off by **5,586 plays over four seasons**.

| quantity | count |
|---|---|
| dropbacks | 80,753 |
| pass attempts | 76,941 *(includes 5,308 sacks, 278 spikes)* |
| scrambles | 4,091 |
| spikes | 278 |
| completions | 46,259 |
| interceptions | 1,615 |
| designed rushes | 54,572 |

`76,941 + 4,091 − 278 = 80,754` against 80,753 dropbacks.

**Residual: exactly one play, and it is named rather than absorbed.**
`2025_03_LA_PHI` play 3600 — a **blocked field goal** carrying an
attempt/scramble flag without a dropback flag. Upstream mislabelling, left
visible.

## Passer identity on scrambles

**Every sack carries a `passer_player_id` (5,308 of 5,308). No scramble does.**
4,091 dropbacks lack a passer id — exactly the scramble count. A scramble is
charged to the **rusher**; 4,091 of 4,091 carry `rusher_player_id`.

This preserves and sharpens the project's standing warning. Attributing a
scramble to the passer produced a structurally-zero column in this repository
once already, and a baseline that "predicted" it with MAE 0.0000.

## What a Stage 4 decomposition must therefore do

1. Derive attempts from `pass_attempt` **minus** sacks and spikes, never from
   dropbacks minus sacks.
2. Keep designed rush and scramble separate, and charge scrambles to the rusher.
3. Exclude kneels (1,689) and spikes from every opportunity denominator.
4. Reconcile team pass attempts and sacks against the QB layer using
   `nfl.accounting.invariants.QB_DROPBACK_IDENTITY`, whose residual is one
   named play.

None of this is a result about QB forecasting. **The QB layer is audited, not
decomposed**, and no claim about where QB uncertainty lives is made here.
