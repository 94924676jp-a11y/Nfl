# Simulation Query Capability — Specification (sim-query-1)

Tool: `nfl/tools/sim_query.py`. Tests: `nfl/tests/test_sim_query.py`. Branch `claude/sim-query-research`, commit `d0b5a8fd`.
Demonstration: `SIM_QUERY_TB_DAL_DEMO.json`, in the same directory as this file.

## 1. Purpose

This is a read-only way to ask questions of our own stored simulation worlds, similar to a DFS vendor's "Ask the Sims" tool, with one difference: **every number is counted from worlds we stored.** Examples: "In what share of worlds does Jalon Daniels rush for 50+?", "How is Lamb's DK distributed in the worlds where Prescott busts?", "How often is Lamb the captain of the best lineup in our pool?"

The tool never invents a probability. It never calls a language model and never reads a sportsbook price. It writes nothing except an optional `--out` JSON, and that file may not be one of its inputs. Betting use is out of scope.

## 2. Data contract

| Input | Format | Checked on load |
|---|---|---|
| Worlds | `WORLDS_NPZ_V1`, written by `classic_slate_run._write_worlds`. `showdown_slate_run.py` and `nfl/sim/event_consistent_worlds.py` call the same writer, so Classic, Showdown and the shadow worlds all share it. It holds `stats` int16 [player, world, field] with yards stored in tenths (`meta.yard_scale`), `points` float32 [game, world, (home, away)], and `meta` (JSON bytes: keys, fields, yard_scale, yard_fields, games, projection_sha256). | The file must contain exactly these three arrays, with the stated dtypes and shapes. Keys must be unique `Name|CLUB` strings, and the worlds must not be empty. A file with one game is laid out as SHOWDOWN; a file with more than one game is CLASSIC. |
| DK draws (optional) | `DRAWS.json` → `draws: {key: [DK per world]}` | `n_sims` must agree, every list must be n_worlds long, and `projection_sha256` must equal the worlds' value. DK points recomputed from the stored stat lines must match the stored draws in at least 0.99 of player-world cells, which rules out a different world order. Measured agreement: 1.0 on OFFICIAL and on SHADOW. |
| Candidate pool (Showdown) | CSV with `captain` and `flex` columns (`A / B / C / D / E`) | Each row needs one captain and 5 distinct flex players. Every name must resolve to exactly one key in the draws. |

**Refused by name:** the `showdown_draws.py` `*_STATS.npz` sidecar raises `UNSUPPORTED_WORLDS_FORMAT`. Any other file raises `UNKNOWN_WORLDS_FORMAT`.

**Model label.** The label is PRODUCTION, RESEARCH or SHADOW. It is either passed in or inferred from the artifact's own marker (draws `ARM` / `SHADOW_ONLY`) or, failing that, from the path. If no label can be inferred the load fails with `LABEL_UNRESOLVED`; it is never guessed. A shadow-marked artifact passed as PRODUCTION raises `LABEL_CONFLICT`.

**Provenance on every answer:** absolute paths; sha256 of the worlds and draws files; n_worlds; format and the writer that produced it; layout; games; model label and where it came from; the worlds' projection_sha256 and the draws' projection_sha256; the draws-to-stats alignment measurement; and a check against the run receipt (`RUN_RECEIPT.json`). For TB@DAL OFFICIAL the receipt check reads MATCH.

## 3. Query grammar

The grammar is closed and parsed by recursive descent. Nothing is passed to eval, exec or compile; a test checks the module source for this. Keywords are case-insensitive.

```
query := P(pred) | P(pred | given) | COUNT(pred) | JOINT(pred, pred)
       | MEAN(value [| given]) | QUANTILES(value [, q ...] [| given]) | CORR(value, value [| given])
pred  := pred OR pred | pred AND pred | NOT pred | ( pred ) | value OP value | wins['CLUB'] | tie['CLUB']
OP    := >= > <= < == !=
value := NUMBER | FIELD['Name|CLUB' or 'Name'] | points['CLUB'] | opp_points['CLUB'] | margin['CLUB'] | total['CLUB' or 'GAME_ID']
FIELD := pass_att | pass_yards | pass_td | carries | rush_yards | rush_td | targets | receptions
       | rec_yards | rec_td | interceptions | any_td (= rush_td + rec_td) | dk_points (dk)
```

- `margin['DAL']` is DAL's points minus its opponent's points in the same world.
- `wins` means strictly more points than the opponent. `tie` means equal points.

**Showdown optimal-lineup frequency** (`--optimal CANDIDATES.csv` or `optimal_frequency()`):

- In each world, every candidate is scored as 1.5 × CPT DK + the sum of FLEX DK.
- The highest-scoring candidate wins the world. Exact ties split the credit equally.
- Each player's share is reported separately as CPT and as FLEX.
- "Optimal" means **optimal among the supplied pool**, not among all legal lineups.

**CLI:**

```
python3.12 nfl/tools/sim_query.py WORLDS.npz --draws DRAWS.json \
    --query "P(rush_yards['Jalon Daniels|TB'] >= 50)" \
    --side-by-side SHADOW_WORLDS.npz SHADOW_DRAWS.json \
    --optimal CANDIDATES.csv --out ANSWERS.json
```

If any answer is refused, the CLI exits 2.

## 4. Guarantees

1. **No invented numbers.** Every value is a count of worlds, or an order statistic or moment over worlds. There is no model, prior, smoothing or fallback anywhere in the path.
2. **Every answer carries:**
   - `value`
   - `n_worlds`
   - `numerator` and `denominator` (also `n_matching`)
   - an SE with its method stated (below)
   - the normalised query text, with keys resolved, which can be re-asked verbatim
   - provenance
3. **SE methods:**

   | Answer | SE method |
   |---|---|
   | Probabilities | Binomial √(p(1−p)/denominator), plus a Wilson 95% interval. This matters at p = 0 or p = 1, where the binomial SE is 0 but the Wilson upper bound is not. |
   | Quantiles | A distribution-free order-statistic 95% interval (binomial ranks); SE = half-width / 1.96. Deterministic, no resampling. |
   | Means | sd/√n |
   | Correlation | SE = (1−r²)/√(n−3), with a Fisher-z interval |

   Worlds are treated as independent draws.
4. **Refusals instead of numbers:**

   | Code | When |
   |---|---|
   | `INSUFFICIENT_WORLDS` | The denominator is below 50 (`MIN_CONDITIONING_WORLDS`, a declared floor: at n = 50 the SE near p = 0.5 is 0.071). No value is returned. |
   | `PLAYER_AMBIGUOUS` / `PLAYER_NOT_FOUND` | A name does not match exactly one key after case and punctuation normalisation. The error lists candidates. There is no fuzzy matching. |
   | `NOT_IN_WORLDS` | The quantity is not stored: first TD, TD order, snaps, longest play, fumbles, per-half scores, and so on. Also raised when a DST or kicker is asked for a stat line. Never approximated. |
   | `UNKNOWN_FIELD` | A typo or unknown field name. |
   | `DRAWS_NOT_LOADED` | DK points are asked for without a DRAWS.json. |
   | `ZERO_VARIANCE` | A correlation involves a constant series. The answer is undefined, not 0. |
   | `SHOWDOWN_ONLY` | Optimal-lineup frequency is asked of a Classic worldset. |
   | `OUTPUT_REFUSED` | `--out` points at an input file. |

5. **Side by side.** The same query can be asked of the PRODUCTION and SHADOW worlds together (`--side-by-side`, `ask_side_by_side`). If one arm refuses, the refusal is recorded with that arm's label, not dropped.

## 5. Validation

**How the answers are tested** (`nfl/tests/test_sim_query.py`, 15 functions, 90 checks, `run_suite.py --modules test_sim_query` → SUITE PASS, 0 failing):

- The synthetic worlds are written by the **production writer** (`_write_worlds`), so the format under test is the format that is published.
- Expected counts are known by construction. Tests cover:
  - exact probabilities, conditional probabilities and SEs
  - AND / OR / NOT and operator precedence
  - JOINT cells
  - quantiles, means and correlation, each against a direct numpy recount
  - wins / tie / loss partitioning every world
  - margin and total
- Refusal tests: INSUFFICIENT_WORLDS (including 0/0), ambiguous and misspelt names, NOT_IN_WORLDS, unknown and unsupported formats, shuffled draws (misaligned), projection mismatch, label inference and conflict, a closed parser, and the CLI's read-only and exit-code rules.
- Optimal-lineup frequency is checked against an independent brute-force recount, world by world.
- Real data: the committed TB@DAL OFFICIAL worlds are reloaded and `P(Daniels rush ≥ 50)` and `P(DAL margin ≥ 20)` are recounted directly from the raw int16/float32 arrays. If those files are absent the test records BLOCKED, never a pass.
- Cross-check: on OFFICIAL, the per-candidate optimal counts match the R1 CSV's own `n_worlds_optimal` for 5,358 of 5,387 candidates (both total 2,000). Why the rest differ was not investigated beyond noting that 14 worlds have exact ties; the CSV may also count optimality over a different pool. The difference is reported, not repaired.

**What validation does *not* establish.** Calibration of the worlds is a separate question, and this tool does not answer it. A query answer is only as good as the worlds it counts. If the worlds are wrong, the answer is an exact count of wrong worlds. Known defects of the TB@DAL worlds:

- **D-01: lower-tail volatility is under-stated.** Bust probabilities and low quantiles (for example, Lamb's DK given a Prescott bust) are likely too optimistic. The tool counts the tail faithfully but cannot repair it.
- **D-05: event accounting is inconsistent in the incumbent (PRODUCTION) worlds.** Club points are a centred continuous draw, not event sums, so player TDs and the scoreboard can disagree within a world. Questions that mix the two (for example, any-TD AND margin) are exposed to this. This is why the **shadow event-consistent worlds** (integer, event-summed scores; `ARM = EVENT_CONSISTENT_SHADOW`, research only, used by no production path) are queryable side by side. Where the two arms differ, that difference measures how sensitive the answer is to D-05; it does not show which arm is right.

## 6. Out of scope

- Betting, pricing, and any comparison with sportsbook lines.
- Fitting, smoothing or extrapolating beyond the stored worlds, including questions about quantities the worlds do not carry.
- Natural-language input; there is no LLM. Queries must be written in the grammar.
- Lineup construction or optimisation. The tool only scores a pool someone else supplied.
- Any judgement that the worlds are calibrated, accurate or "correct".
- Writing to, repairing or re-simulating any artifact.
