# Postmortem — DET @ BUF Showdown portfolio, 2026-09-17

**Failure class:** `KNOWN_MODEL_DEFECT_AMPLIFIED_BY_OPTIMIZER`

Not a projection error. A projection error is a number being wrong. This is a
number being wrong **in a way already written down in this repository**, then
consumed by a stage that had no way to read what was written. Every ingredient
was present before the portfolio was built.

## 1. Measured exposure, both portfolios

Counted from the delivered files, not quoted. Fixtures preserved at
`nfl/research/dfs/DET_BUF_2026W2/`.

| player | tag | delivered: any | CPT | alternate: any | CPT |
|---|---|---:|---:|---:|---:|
| Jahmyr Gibbs | `MODEL_SUPPORTED` | 100.0% | 15.0% | 85.0% | 22.5% |
| Josh Allen | `MODEL_SUPPORTED` | 97.5% | 15.0% | 80.0% | 15.0% |
| Amon-Ra St. Brown | `MODEL_SUPPORTED` | 75.0% | 15.0% | 82.5% | 20.0% |
| **Ray Davis** | **`ROLE_STATE_CONCERN`** | **72.5%** | **15.0%** | 37.5% | 0.0% |
| **Khalil Shakir** | **`ROLE_STATE_CONCERN`** | **57.5%** | **15.0%** | 67.5% | 7.5% |
| **Frank Gore Jr.** | **`ROLE_STATE_CONCERN`** | **55.0%** | 0.0% | 32.5% | 0.0% |
| Sam LaPorta | `MODEL_SUPPORTED` | 35.0% | 10.0% | 35.0% | 5.0% |
| Jared Goff | `MODEL_SUPPORTED` | 35.0% | 12.5% | 75.0% | 20.0% |
| Tyler Bass / Jake Bates | `MODEL_SUPPORTED` | 22.5% each | — | 0.0% | 0.0% |
| Jameson Williams | `MODEL_SUPPORTED` | 7.5% | 0.0% | 17.5% | 10.0% |
| **James Cook** | **`ROLE_STATE_CONCERN`** | **0.0%** | 0.0% | **0.0%** | 0.0% |

Your figures reproduce exactly. Three corrections the measurement adds:

**(a) There were three violators, not two.** Khalil Shakir at 57.5% carries the
same `ROLE_STATE_CONCERN` tag for the same reason, and neither of us named him.
I found him only because the guard's test refused a portfolio in which I had
overridden the two backs I expected.

**(b) James Cook is 0% in BOTH portfolios.** The alternate did not avoid the
defect on the Cook side either. The Buffalo backfield was mispriced in both
directions and both portfolios took the same side of it.

**(c) The alternate portfolio also exceeds the policy.** Ray Davis 37.5% and
Shakir 67.5% are both over a 35% cap. It **diluted** the defect rather than
governing it. That is a real improvement in degree and it is not a difference
in kind, and the regression test asserts both files fail.

## 2. Why Frank Gore Jr. reached 55% — the explicit explanation you asked for

Not salary relief alone. Four causes, in order of size:

1. **The objective was mean DK points and nothing else.** No ceiling, no
   correlation, no ownership, no variance. Under pure mean-maximisation a
   cheap player with any non-zero projection is close to free: at $400 he cost
   0.8% of the cap and returned 4.24 projected points.
2. **Points per dollar was extreme and unexamined.** 4.24 / $400 is 10.6 points
   per $1,000 against roughly 1.8 for Gibbs. A mean-maximiser will take that
   trade every time it is offered, and it was offered in every lineup.
3. **He inherits the same defect as Davis.** His projection is not independent
   evidence — it comes from the same flattened Buffalo backfield split that
   inflated Davis. Two correlated symptoms of one defect entered as two
   separate opportunities.
4. **Excluding DST removed the alternative punts.** With both DSTs out (the
   model does not produce them), the cheap tier collapsed to Gore, the two
   kickers, and low-target tight ends. The uniqueness requirement then forced
   repeated use of a thin punt pool.

High punt exposure is not wrong in itself. **This** punt exposure is wrong
because the punt's projection came from the defective layer, and nothing
checked that.

## 3. Captain distribution — mechanically forced, confirmed

Six captains at exactly 15.0% each is not a coincidence and not a ceiling
judgement. The generator held `capct[ck] >= 6` against 40 lineups: 6/40 =
15.0%. The cap bound for six different captains simultaneously, so the
"diversification" was a counting rule, not an argument about who is most
likely to finish first.

It was **not** ceiling-driven and **not** first-place-probability driven.
Mean DK ordered the captain candidates; the counter spread them. A correct
Showdown captain rule works off P(finish first | captain) or ceiling mass, and
8,000 draws were sitting right there, unused for this purpose.

## 4. What is now built

| component | file | state |
|---|---|---|
| Confidence tag vocabulary and policy | `nfl/production/dfs/projection_confidence.py` | built |
| Exposure audit and authorization gate | `nfl/production/dfs/portfolio_guard.py` | built |
| Regression test | `nfl/tests/test_dfs_portfolio_guard.py` | 26 checks, 0 failed |
| Both portfolios as fixtures | `nfl/research/dfs/DET_BUF_2026W2/` | preserved |

The authorization rule, enforced rather than described:

```
PORTFOLIO_MAY_NOT_BE_AUTHORIZED_IF_HIGH_EXPOSURE_IS_DRIVEN_BY_A_KNOWN_MODEL_DEFECT
```

Declared caps. `ROLE_STATE_CONCERN`: 35% any slot, 10% captain — the captain
cap is tighter because a captain is 1.5× points and 1.5× salary, the single
largest bet a lineup makes, and the least trustworthy projection should be the
least likely to carry it. `DATA_STATE_CONCERN`: 25% / 5%.
`KNOWN_INACTIVE_STALE`, `IDENTITY_UNRESOLVED`, `UNSUPPORTED`: blocked outright.

**These caps are declared, not fitted.** There is no dataset here that could
fit them, and a cap reverse-engineered from one night's result would be the
same mistake wearing a different hat. They bound the damage; they are meant to
be replaced by evidence.

**Four properties the test pins down.** An untagged player is a refusal, not a
silent default to trusted — defaulting to trusted is precisely how this
happened. A blocked player cannot appear at any exposure. An override must
carry an evidence string; an empty one is refused by name. And a control
portfolio inside the caps is authorized, so the guard is not simply refusing
everything.

## 5. What is NOT built, and is not pretended

- **Ownership / field model** — absent. No leverage reasoning is possible
  without it, and duplication risk cannot be estimated.
- **Contest simulator / payout model** — absent. Nothing here optimises for
  first place rather than for mean.
- **Ceiling-driven captain selection** — absent. The draws support it; no code
  uses them that way yet.
- **Scenario / game-script buckets** — absent.
- **Correlation-aware construction** — absent. Lineups were assembled from
  marginal means with the joint structure sitting unused in the same file.

## 6. The professional-DFS research package

**BLOCKED, cause NETWORK.** The open web is refused at CONNECT by this
environment's policy (`www.espn.com`, every non-GitHub host tested). I am not
going to write a "research package" on how professional Showdown players
handle uncertainty out of recollection and present it as research — that would
be the same failure as tonight in a different medium: an unsourced number
treated as trustworthy because nothing flagged it.

Assigned to an agent with egress as **OUT-021**, with the ten questions
carried verbatim.

What can be said without research, because it follows from what is already
here: the ten questions divide into three that are **governance** (caps,
overrides, blocked players) and are now built; four that need an **ownership
and field model** (leverage, duplication, contrarian allocation, projected
ownership) and cannot be answered without one; and three that need a
**contest-payout simulator** (core vs contrarian split, first-place captain
logic, distinguishing projection error from intentional leverage). The
architecture already names all three layers. None of them existed tonight.

## 7. The lesson, stated so it survives

The optimizer did exactly what the numbers told it to do. **The numbers already
carried a recorded defect, and there was no channel through which they could
say so.** Every downstream stage treated a mean as a mean.

That is a governance problem, not a projection problem, and it is the same
shape as every other failure this project has had: a step returned something,
and the next step read it as trustworthy because nothing said otherwise.

**V2 NOT YET EARNED**
