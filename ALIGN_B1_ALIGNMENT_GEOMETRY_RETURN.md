# ALIGN-B1 — PRE-SNAP ALIGNMENT IDENTIFIABILITY PROTOTYPE

**Date** 2026-09-08 · **Repo** `94924676jp-a11y/Nfl` · **Branch** `main`
**Freeze** `nfl/research/alignb1/FREEZE.json`, HEAD `f82d5da`
**Pre-registration** `nfl/research/alignb1/predeclaration_alignb1.md`, sha256
`e8260091a125a5ecdc60cc8e153fb6fbbc5075594188d6ba84b647dd17ccfd62` — taxonomy,
geometry, thresholds, metrics and viability bar all fixed **before** any code
was written.

## DECISION: `DATA_INSUFFICIENT`

**No player coordinate data of any kind exists in this environment, and this
executor cannot fetch any.** Measured, not assumed: `kaggle.com` returns `000`
(no connection) and `github.com` releases return `403` at the egress proxy —
consistent with the project's standing record that the local executor has no
egress while the GitHub Actions executor does.

So §D–§G could not be executed against real tracking data. What **was**
delivered is everything that does not require it: the frozen taxonomy, the
deterministic classifier built to it, an abstention mechanism with
machine-readable causes, a code-level validation, the expansion assessment, and
an exact, actionable data request.

**Nothing here authorizes production or commercial use of NFL video, tracking
data, Big Data Bowl data, or FTN data. No FTN label was used, for anything.**

---

## 1. What was delivered

| §  | item | status |
|---|---|---|
| A | freeze of HEAD, code and predeclaration hashes | **done** |
| B | six-class taxonomy, geometrically defined before fitting | **done** |
| C | independent source audit, with the licence position stated | **done — and it is the blocker** |
| D | deterministic rule-based classifier | **built** |
| E | ground-truth protocol | **specified, not executed** |
| F | validation on real plays | **BLOCKED — no data** |
| G | viability thresholds vs measured accuracy | **BLOCKED — nothing measured** |
| H | expansion assessment | **done** |

---

## 2. Taxonomy and geometry (§B), fixed before any result

Six classes: `WIDE`, `SLOT`, `INLINE_TE`, `DETACHED_TE`, `BACKFIELD`,
`AMBIGUOUS`. Rules applied in order, on the last stable pre-snap frame:

| # | condition | class |
|---|---|---|
| 1 | `depth ≥ 1.5` and `gap ≤ 3.0` | `BACKFIELD` |
| 2 | `depth ≤ 1.0` and `gap ≤ 1.5` | `INLINE_TE` |
| 3 | `1.5 < gap ≤ 6.0` | `DETACHED_TE` |
| 4 | `gap > 6.0` and someone outside him | `SLOT` |
| 5 | `gap > 6.0` and nobody outside him | `WIDE` |
| 6 | otherwise | `AMBIGUOUS` |

where `gap` is lateral distance to the nearest tackle on the player's side and
`depth` is distance behind the line of scrimmage.

**`AMBIGUOUS` is a first-class outcome, not a failure.** A classifier that never
abstains cannot route hard cases to review, which §F requires. Forced
abstention, each with a machine-readable cause:

`NO_STABLE_FRAME` · `OL_NOT_IDENTIFIABLE` · `BUNCH_OR_STACK` · `IN_MOTION` ·
`NULL_COORDINATE` · `NO_RULE_MATCHED`

Two of those are worth calling out. With fewer than five identifiable linemen
the classifier **refuses** rather than guessing a tackle position — guessing
would fabricate the very reference the whole taxonomy is measured against. And
a player within 1.5 yards of a same-side teammate abstains, because "who is
outside whom" is exactly what decides `SLOT` vs `WIDE` and it is unstable in a
bunch.

---

## 3. The audit, and the licence position (§C)

| candidate | present here? | licence position |
|---|---|---|
| NFL Big Data Bowl / Next Gen Stats tracking | **no** | Kaggle competition terms. **Not verifiable from here** — no egress. Research/competition permission must never be read as production or commercial permission, and this return does not read it that way. |
| nflverse tracking release | **does not exist** | nflverse publishes play-by-play, participation, rosters, depth charts — **no player coordinates** |
| local repo / container | **no coordinate data of any kind** | — |

The `nflverse-data` checkout present in this container is the **repository of R
build scripts**, not data.

**I did not download anything, and I could not have.** I am also not asserting
what the Big Data Bowl licence permits — I have not read it, and a claim about
licence terms sourced from memory is exactly the kind of thing this project
treats as unverified recall.

---

## 4. What was validated, and what that does and does not mean

`nfl/tests/test_align_geometry.py` — **29 checks, 0 failing**, against
formations whose coordinates I wrote by hand from the football definitions:

- 11 personnel resolves correctly: two `WIDE`, one `SLOT`, an `INLINE_TE` at
  1.33 yards off the tackle, a `BACKFIELD` at 7 yards' depth;
- a TE flexed 3.33 yards off the tackle is `DETACHED_TE`, neither inline nor
  slot;
- a back split out is judged **by geometry, not by his roster position** —
  `SLOT` with a receiver outside him, `WIDE` with nobody outside;
- every abstention path fires with the right cause;
- the accept/review split reports its rate rather than implying it;
- **every threshold in the code matches the sealed pre-registration**, checked
  by reading that file.

**This proves the module implements the declared rules. It is not evidence
about real-world accuracy and must not be quoted as such.** No real alignment
was classified. Reporting these 29 checks as an accuracy figure would be the
"something returned, therefore it worked" defect this project keeps finding.

One assertion of mine was wrong and the code was right: I initially expected a
back split to y=8 to be `WIDE`, but a receiver at y=4 was still outside him, so
`SLOT` was correct football. The test now asserts both cases, which is stronger
than what I first wrote.

---

## 5. Viability (§G) — nothing measured, so nothing claimed

| threshold | result |
|---|---|
| ≥ 95% accuracy on auto-accepted labels | **NOT MEASURED** |
| ≤ 15% manual-review rate | **NOT MEASURED** |
| no systematic per-class/position failure | **NOT MEASURED** |

I will not estimate these. An accuracy number produced without data would be
fiction, and the abstention rate in particular is an empirical property of real
formations — bunch sets, condensed splits and motion are precisely the cases my
constructed tests cannot tell me the frequency of.

---

## 6. Expansion (§H) — assessed, not implemented

| primitive | same representation? | additional need | difficulty |
|---|---|---|---|
| **motion** | yes | the pre-snap frame *sequence*, which the classifier already scans | **low** |
| **matchup proximity** | yes | defensive coordinates in the same frames; nearest-defender over time | low–medium |
| route participation | yes | post-snap frames plus a release criterion | medium |
| pass protection / release | yes | the complement of the above | medium |

Worth stating plainly: **route participation is the least valuable of the
four**, despite being technically feasible. FTN-S1 measured it at ~0.6% of our
residual error, and building it ourselves would not change that. The cheap
expansions are motion and matchup proximity — and matchup is the one FTN-S2
could not resolve, so a coordinate-based version of it would answer a live
question rather than a settled one.

---

## 7. Exactly what would unblock this

One dataset, of the following shape, for any set of NFL plays:

- **per-frame player coordinates** (`x`, `y`) at ≥ 10 Hz through the snap;
- **stable player identifiers** joinable to `gsis_id`, or a name/jersey/team
  key that resolves to one without fuzzy matching;
- **the ball position or line of scrimmage** per play;
- **a snap event marker**, so the last stable pre-snap frame is findable;
- **position or an offense/defense flag** sufficient to identify the five
  linemen;
- and, for §E, **a formation or alignment field** — otherwise ground truth
  needs a manual labelling pass against the frozen §2 definitions.

Big Data Bowl releases carry all of these except, in most years, an alignment
label. **Two to three games would be enough for a first read** on accuracy and
abstention rate; a full season is not needed to answer "does this geometry
work".

**The blocker is access from an executor with egress, not effort.** The
classifier is written and tested. If the data reaches the repository, §F and §G
run against it without further design work.

---

## 8. On the parallel licensing question

I have no view to offer on who will license raw video or tracking with
automated-analysis rights — that requires outbound research this executor
cannot do, and answering it from recall would be the same unverified-recall
error I flagged in §3. It is correctly Perplexity's half.

What I can say from inside the repo is that your framing is the right one to
test: **the licence question and the technical question are separable, and the
technical half is the cheaper one to settle first.** If coordinates can be
licensed at all, this prototype says what we would then need to prove before
depending on them — and that proof needs two or three games, not a season.

---

## 9. Explicit restatements

- **No FTN data was used** — not as labels, training truth, thresholds, or
  tie-breaks. The sample stayed sealed for this packet.
- **No production or commercial authorization** is implied for NFL video,
  tracking data, Big Data Bowl data or FTN data. Research permission is not
  production permission.
- **No machine-learned model was built** — §7 of the pre-registration requires
  the rule-based baseline to be measured first, and it has not been measured,
  so nothing further was attempted.
- **Nothing promoted, no production model touched.** G0A remains 11/12. NFL-1
  remains NOT AUTHORIZED.

**THEN STOP.**

## 10. Canonical suite

    modules 35   test functions 359   checks 2130
    FAILING CHECKS 0   RAISED 0
    SUITE PASS

Up from 34 / 352 / 2,101 — one module added, 29 checks.

### Files

| path | what |
|---|---|
| `nfl/research/alignb1/predeclaration_alignb1.md` | taxonomy and thresholds, sealed first |
| `nfl/research/alignb1/FREEZE.json` | HEAD, hashes, measured egress state |
| `nfl/research/alignb1/align_geometry.py` | the rule-based classifier |
| `nfl/research/alignb1/expansion_assessment.json` | §H |
| `nfl/tests/test_align_geometry.py` | 29 checks against constructed formations |
