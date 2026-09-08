# ALIGN-B1 PRE-REGISTRATION — pre-snap alignment from geometry

Written and hashed **before** any classifier was written and before any
performance was observed. Research prototype only.

## 0. Standing prohibitions

**No FTN charting is used as a label, as training truth, as a threshold, or as
a selection criterion.** The FTN sample stays sealed for this packet; its
alignment strings were *observed* in FTN-S2 as vendor output and are **not**
used here as ground truth.

Nothing here authorizes production use, commercial use, NFL subscription
video, FTN data, or Big Data Bowl data in production. **Research permission is
not production permission and the two are never elided.**

## 1. Taxonomy — CLOSED, six classes, declared before fitting

| class | football meaning |
|---|---|
| `WIDE` | outermost eligible on his side, split from the formation |
| `SLOT` | eligible with another eligible outside him on the same side, detached from the core |
| `INLINE_TE` | attached to the offensive line, on the line of scrimmage |
| `DETACHED_TE` | off the tackle but still near the core — wing, flexed, tight slot |
| `BACKFIELD` | aligned behind the line inside the tackle box |
| `AMBIGUOUS` | geometry does not decide, or the pre-snap frame is unusable |

`AMBIGUOUS` is a **first-class outcome, not a failure**. A classifier that
never abstains has no way to route hard cases to review, which §F requires.

## 2. Geometric definitions — thresholds fixed NOW

Coordinate frame normalised so the offense advances in `+x`; `y` is lateral,
0–53.33 yards.

    LOS        x of the ball at the frame used
    depth      LOS_x - x_player          (positive = behind the line)
    core       the five offensive linemen; tackles are the outermost two
    gap        |y_player - y_nearest_tackle_on_the_player's_side|
    side       sign(y_player - y_ball)
    n_outside  eligible teammates on the same side further from the ball

Applied **in this order**:

1. `depth >= 1.5` and `gap <= 3.0` → **BACKFIELD**
2. `depth <= 1.0` and `gap <= 1.5` → **INLINE_TE**
3. `1.5 < gap <= 6.0` → **DETACHED_TE**
4. `gap > 6.0` and `n_outside >= 1` → **SLOT**
5. `gap > 6.0` and `n_outside == 0` → **WIDE**
6. otherwise → **AMBIGUOUS**

**Abstention is forced, regardless of the above, when:**

- fewer than 5 offensive linemen are identifiable, so `core` and `gap` are
  undefined;
- the player is within `1.5` yards of another eligible on the same side and
  their `y`-order is therefore unstable (**bunch/stack**);
- the player's lateral speed exceeds `1.0` yd/s in the frame used
  (**motion/shift** — the alignment is not yet set);
- the ball or the player carries a null coordinate.

**These thresholds are frozen. They may not be moved after seeing accuracy.**
If they turn out to be wrong, that is a result to report, not a knob to turn.

## 3. Frame selection

The **last stable pre-snap frame**: the latest frame at or before the snap
event in which no offensive player exceeds 1.0 yd/s lateral speed. If no such
frame exists in the window, every player on the play is `AMBIGUOUS` with cause
`NO_STABLE_FRAME` — the play is not forced into a classification.

## 4. Ground truth — declared before looking for it

Truth must come from the research dataset itself (a formation or alignment
field), or from a manual labelling protocol applied to lawful research inputs
by a labeller working from the frozen §2 definitions.

**FTN labels are not truth here and may not be used as truth**, including as a
tie-break or a spot check.

## 5. Metrics — declared before results

Overall accuracy; per-class precision and recall; the full confusion matrix;
accuracy by roster position (WR/TE/RB); accuracy on bunch/condensed sets;
accuracy under motion/shift; and the abstention rate.

The **accept/review split** is evaluated explicitly: accuracy on the
auto-accepted subset, and the fraction routed to review.

## 6. Viability thresholds — RESEARCH thresholds, fixed now

- ≥ **95%** accuracy on auto-accepted labels
- ≤ **15%** manual-review rate preferred
- **no systematic per-class or per-position failure**

Meeting these authorises **nothing**. They are a research bar, not production
readiness and not a licence.

## 7. Method order

The simplest deterministic rule-based classifier is built and evaluated
**first**. No machine-learned model may be introduced until the rule-based
baseline has been measured and reported.

## 8. Decision vocabulary — exactly one

`ALIGNMENT_GEOMETRY_WORKS` · `ALIGNMENT_GEOMETRY_PARTIAL` ·
`ALIGNMENT_GEOMETRY_FAILS` · `DATA_INSUFFICIENT`
