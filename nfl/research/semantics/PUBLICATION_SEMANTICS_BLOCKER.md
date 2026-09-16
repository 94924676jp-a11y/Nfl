# BLOCKING: the board mixes two publication semantics across positions

Traced on the sealed 8,000-draw GSVU run,
`c3probe_V1_CANDIDATE_R9_W1P_GSVU/fdb3582f8db5142a`. **Do not seal.**

## The question, answered

**Neither A nor B.** The non-QB board is (A) unconditional, gated by the P3/R8
appearance draw. The QB board is unconditional **with respect to a different
participation event** — the QB room's own starter/exit/replacement state —
which does not consume the appearance model at all.

## 1. In worlds where Josh Allen does not appear, does he get exactly zero?

There is no such event on the QB path: **R8's appearance draw for a
quarterback is never applied.** What exists is "zero dropbacks", which the QB
room produces on its own.

| | |
|---|---|
| R8 `P(appear)` for Josh Allen | **0.8449** |
| implied zero-worlds at 8,000 draws | **1,241** |
| **observed zero-dropback worlds** | **31** (0.0039) |

Within those 31 worlds the gating is **exact**. Maxima, not means:

    qb/db 0.000  qb/att 0.000  qb/cmp 0.000  qb/pyds 0.000  qb/ptd 0.000
    qb/int 0.000 qb/sacks 0.000 qb/rush_opp 0.000 qb/ryds 0.000
    qb/rtd 0.000 qb/scr 0.000  dk_points 0.000

So the conditional structure is clean. **The conditioning event is the wrong
one**, and it is wrong by a factor of 40.

## 2. Who receives BUF QB volume in those worlds?

Kyle Allen, mean **35.710** dropbacks, team total **35.710** — the whole of it,
no leakage, against a BUF overall mean of 36.422. Conservation holds.

## 3. Unconditional or conditional?

| Josh Allen, passing yards | |
|---|---|
| published mean, over all 8,000 worlds | **236.0154** |
| conditional mean over his nonzero-dropback worlds | 236.9335 |
| what it would be if R8 appearance gated him | **199.4094** |

The published figure is unconditional over the QB room's state space. Because
that space assigns only 0.39% to his absence, it is numerically almost
identical to the conditional mean — the two differ by 0.9 yards. **A reader
cannot tell them apart, and that is the problem.** Under the non-QB semantics
the same player would publish 199.4.

## 4. The same check across positions

`P(volume = 0)` against `1 − P(appear)`, GSVU, 8,000 draws:

| player | pos | P(appear) | P(vol=0) | 1−P(appear) | gated? |
|---|---|---|---|---|---|
| James Cook | RB | 0.6299 | 0.3745 | 0.3701 | **yes** |
| Jahmyr Gibbs | RB | 0.9543 | 0.0489 | 0.0457 | **yes** |
| Amon-Ra St. Brown | WR | 0.9881 | 0.0132 | 0.0119 | **yes** |
| Khalil Shakir | WR | 0.8890 | 0.1366 | 0.1110 | **yes** |
| Sam LaPorta | TE | 0.9562 | 0.0691 | 0.0438 | **yes** |
| Greg Dortch | WR | 0.0233 | 0.9816 | 0.9767 | **yes** |
| **Josh Allen** | **QB** | **0.8449** | **0.0039** | **0.1551** | **NO** |
| **Jared Goff** | **QB** | — | **0.0030** | — | **NO** |

For every non-QB, `P(vol = 0) >= 1 - P(appear)`, with the excess being the
ordinary football event "appeared and got no touch" — Brock Wright 0.2759
against 0.0299, Keleki Latu 0.5409 against 0.0746. That is the correct
inequality and it holds on all 25 non-QB rows. **It fails on both starting
quarterbacks, in the other direction.**

James Cook makes the contrast concrete: published carries **9.518**, conditional
on taking a carry **15.217**, and `0.6299 x 15.217 = 9.585`. The non-QB board
publishes the unconditional number. The QB board does not have the same
denominator.

## 5. Is this new?

**No, and it is already named in the repository** —
`qb_accounting.QB_PRIMARY_PASSER_GAP`:

> no model selects which rostered quarterback is the team's primary passer.
> Appearance is not the same question — a backup can appear without taking a
> snap at quarterback — so the P3 appearance mechanism does not answer it.

and `qb_accounting.py:467`: *"Every other position passes through the
appearance layer; the QB does not."*

What is **new here is the consequence for publication**. The existing note
treats it as a volume-conservation concern; R9's starter/exit/replacement state
largely fixed the conservation half (2.62 starters per team became 0.39% zero
worlds). Nobody asked what it does to the **meaning of a published mean**, and
the answer is that the board carries two different conditioning events under
one column heading.

The observation is also correct on its own terms: appearance and
primary-passer selection are genuinely different questions. A quarterback can
dress, take a knee at the end, and appear without throwing. So the repair is
**not** "multiply the QB line by R8's P(appear)". It is to make the QB room's
own participation state consume the appearance evidence, or to declare the QB
column conditional and say so — and either is a mechanism change with its own
identity and its own pre-registration.

## 6. Verdict

**BLOCKING. The board is not sealed.**

Two gates now fail independently:

1. **This one** — publication semantics are not consistent across positions.
2. **Contract 3** — no draw count on the pre-registered grid clears. Failing
   quantities fall 553 → 356 → 194 → 108 → 72 across n = 1,000 → 16,000, and
   the binding quantity at 8,000 and 16,000 is **`qb/pyds` p90 for Josh
   Allen** — the same player and the same layer this defect sits in.

That the convergence gate and the semantics gate bind on the same cell is
worth noticing rather than treating as coincidence: a quantity whose
conditioning event is ambiguous is also the one whose upper tail will not
settle.

V2 NOT YET EARNED.
