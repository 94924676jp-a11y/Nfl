# CS2 stage 2 — current non-QB role state, fitted out of sample

`nfl/production/nonqb/cs2_state.py`, spec `nonqb-current-season-role-state-1`,
under amendment `B1`. **Nothing is fitted to DET @ BUF, and 2026 is excluded
from the chain entirely.**

## What was missing

CS1 is `current-season-qb-panel-1` — a quarterback panel by construction — so
2026 week-1 receiving and rushing usage never reached role allocation for RB,
WR or TE. Stage 1 measured that usage. Stage 2 turns it into state.

## Two quantities, never one

```
p_appears        = (kappa_a * a0 + appeared)     / (kappa_a + n_weeks)
share | appears  = (kappa_s * s0 + opportunity)  normalised over the room
```

Posterior means under a Beta prior on appearance and a Dirichlet prior on the
room split. The P2 diagnostic is the argument for keeping them apart: James
Cook's unconditional carry share of 0.454 averaged a defensible conditional
share (0.692) against an indefensible absence mass, and one number hid which
of the two was wrong.

## The forward chain

2022–2025, weeks 2–18, predicting week W from weeks 1..W-1 of season S plus
all of S−1. **136 folds.** Ordinal guard an assertion, **0 violations**.
Scored on opportunity, never yards.

| arm | appearance Brier | allocation log-loss |
|---|---:|---:|
| **CS2 best** (`kappa_a=1`, `kappa_s=25`) | **0.15178** | **9.61079** |
| `PRIOR_ONLY` (prior season alone) | 0.23650 | 11.54271 |
| `UNIFORM` (no information) | 0.36019 | 13.22136 |

CS2 beats `PRIOR_ONLY` on both scores and `PRIOR_ONLY` beats `UNIFORM` on
both, which is the ordering that has to hold for any of this to be evidence.

**The two hyperparameters are separable, and the selection uses that.**
`kappa_s` cannot move an appearance score and `kappa_a` cannot move an
allocation score — visible in the table, where Brier is identical down every
`kappa_a=1` row. That is algebra, not a convenience.

## The Buffalo re-diagnostic

`CS2_REDIAGNOSTIC.json`. Prior strengths **read** from the chain, not chosen
here. Conditioning: BUF 2026 week 1 only, `as_of` the seal instant.

| player | sealed P(0 opp) | CS2 P(0 opp) | sealed share | CS2 share \| appears | wk-1 carries |
|---|---:|---:|---:|---:|---:|
| James Cook | 0.3719 | **0.0000** | 0.454 | 0.4684 | 13 |
| Ray Davis | 0.1801 | **0.2368** | 0.331 | 0.0580 | 1 |
| Frank Gore Jr. | 0.3970 | 0.5000 | 0.215 | 0.0601 | 1 |

**Verdict: `INVERSION_RESOLVED`.** The RB1 is no longer absent more often than
his backup. Nothing was written back — CS2 is a state layer and no projection,
board or sealed artifact was modified.

**No monotonicity was imposed to get this.** `test_E` builds a room where the
backup genuinely appears in more weeks and asserts CS2 says so. The ordering
changed because the evidence changed it.

## The limitation that blocks production, stated plainly

**`CS2_APPEARANCE_SATURATES_AT_ONE`.** Cook's CS2 `P(zero opportunity)` is
*exactly* 0.0000 — the model saying he cannot miss. That is not a plausible
football state. A Beta posterior mean saturates for a man who has never missed
and for one who has never played, and on the 2026 week-1 carries room that is
**13 rows at exactly 1.0 and 77 at exactly 0.0, of 196**, with 103 prior
fallbacks.

Nothing is clipped. A floor is a modelling choice with a number in it and
belongs in a preregistration, not in the diagnostic that noticed it was
needed. **Until that is declared, stage 2 does not reach production
allocation.**

The forward-chain result is unaffected by this: a Brier score penalises a
saturated probability at full weight when it is wrong, and CS2 still won
decisively over 136 folds.

## What one week cannot do

The 2026 conditioning set is a single week. Every 2026 number above is a
one-week update of a prior-season prior, and its uncertainty is not small. The
chain's 136 folds carry the evidence; the Buffalo table is a diagnostic
reading, not a measurement of CS2's quality.

**V2 NOT YET EARNED**
