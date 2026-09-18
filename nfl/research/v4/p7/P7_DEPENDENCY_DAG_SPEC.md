# P7 — dependency DAG and incremental recomputation: SPECIFICATION

## STATUS, amended 2026-09-18 (P6)

**Phase 1 of §6 is now implemented**, in `nfl/production/pipeline.py` — inside
the existing orchestrator rather than beside it. Implemented: the four node
types of §2, the declared edges of §3 with `fields` enumerated, the §4
reachability invariant (`DAG.reachable_vintages`, `DAG.max_learned_at`,
`DAG.assert_cut_lawful`), the §5 identity
`H(spec_version, code_identity, sorted(input identities), declared_fields)`
and both of §5's non-optional caching rules, and the §6 Phase 1 AST audit
(`audit_declared_reads`). Tests: `nfl/tests/test_p7_dag.py`. Generated
inventory: `P7_DECLARED_READS.json`, which answers "who reads
`depth_charts`?" without a grep.

**Phase 2 and Phase 3 are NOT implemented and nothing below should be read as
claiming they are.** Every read in the declared edge set still happens by
globbing a directory. What changed is that the read is declared, so an
undeclared one fails a test — a bound on who reads what, not a capability
gate. The cut check is registered in a real run and RECORDED rather than
enforced; `Pipeline.register_captures` states why, and what would make it a
halt.

The audit's own findings on first run, kept here because they are facts about
the tree rather than about this document: three reads take their file name
from a manifest row at run time and are declared by `(module, function)` in
`RUNTIME_KEYED_READS` instead of by source; and the
`delivered_injury_evidence` blob family lives in `nfl/vintage/` while
appearing in neither `registry.REGISTRY` nor `registry.DELIVERED`, so no
source name exists to declare an edge to it. That second one is a capture-layer
gap and was reported, not repaired.

---

**The sentence below was true when this file was written and is now superseded
by the status block above.** It is left standing rather than deleted, because
rewriting a document to match a later state is how a reader loses the ability
to tell what was known when.

**Nothing in this file is implemented.** It is a specification, written because
the brief asked for a spec rather than a half-built implementation, and because
a spec presented as an implementation is the exact false green this project is
auditing itself for. If you are looking for code, there is none for this.

What *is* implemented from Part B is in `P7_DATA_PLANE.md` section 3:
`nfl/capture/bitemporal.py` and `nfl/capture/freshness.py`. Everything below
this line is design.

---

## 1. Why a DAG, stated as the defect it would have caught

The repaired `board.depth_rank` call and the still-open
`qb_allocation.captured_depth_chart` call are the same defect: a consumer
reaches a source directly, by globbing a directory, with no declaration that it
consumes that source at all. Nothing in the repository can answer "who reads
`depth_charts`?" except a grep, and a grep found `board.py` after the leak had
been running for the life of the corpus.

A dependency DAG is the artifact that makes that question answerable by
construction. Its value is **not** recomputation speed. It is that a consumer
which is not in the DAG cannot get bytes, so adding a reader is a declaration,
not a glob.

## 2. Node types

Four, and the distinctions are the ones the existing modules already pay for.

**`SourceNode`** — one entry in `registry.REGISTRY` or `registry.DELIVERED`.
Identity: the source name. Has no inputs. Its output is a set of
`bitemporal.Fact`s, one per capture, keyed by content hash.

**`VintageNode`** — one `(source, content_sha256)` pair: specific bytes, with
the transaction time at which they were first observed. This is the unit
`vintage_selector.candidates` already collapses recaptures down to, and the
reason it must be a node rather than an edge label is that the *same* bytes seen
twice are one vintage, not two, and everything downstream must agree on that.

**`DerivedNode`** — anything computed from vintages and from other derived
nodes: the denominator panel, `role_prior`, `coach_prior`, the QB fit, the
appearance frame. Carries a `spec_version` and the code identity of the function
that produced it.

**`ForecastNode`** — one sealed board. Its distinguishing property is that it
carries a **cut**, and that cut is what every read beneath it is judged against.

## 3. Edges

An edge is a declared read: `(consumer, producer, fields, why)`. Three
requirements, each of which exists because its absence has already cost
something here.

1. **`fields` is mandatory and enumerated.** Not "reads schedules" but "reads
   `season, week, game_type, gameday, gametime, home_team, away_team`". The
   `schedules` blob carries 46 columns including `result`, `home_score`,
   `spread_line` and `total_line`. Today the guard against reading those is that
   nobody does, which is a weaker guarantee than a bound and cannot be checked
   without re-reading every consumer.

2. **An edge into a `ForecastNode` subtree is judged by `bitemporal.readable_at`,
   not by the declaration.** A declared edge says a read is *permitted in
   principle*; only the cut says it is lawful *on this run*. Collapsing the two
   is how "the source is allowed" becomes "this capture is allowed".

3. **There is no implicit edge.** A module that reads bytes it has not declared
   should not be able to. See §6.

## 4. The invariant worth having

> For every `ForecastNode` F with cut C, every `VintageNode` reachable from F
> has `learned_at < C`, and every `DerivedNode` reachable from F was computed
> from a set of vintages all of which satisfy that.

The second clause is the one that is easy to lose. A derived artifact computed
once and cached — the denominator panel, a fitted coefficient — inherits the
transaction time of the **latest** vintage that went into it, not of the run
that reads it. A panel built on Monday from a Sunday-evening capture is not
lawful for a Sunday-afternoon forecast, however old the *forecast* thinks the
panel is. So a `DerivedNode` stores `max(learned_at)` over its inputs and is
itself subject to `readable_at`.

`bitemporal.assert_forecast_reads_only_learned_before_cut` already implements
the check for a flat list of facts. What it lacks is the reachability: today the
caller has to know which facts to hand it, which is exactly the knowledge the
DAG would hold.

## 5. Incremental recomputation

Content-addressed, and nothing more clever than that.

Each node's identity is `H(spec_version, code_identity, sorted(input identities),
declared_fields)`. A node is recomputed when its identity changes and not
otherwise. This is deliberately *not* a staleness heuristic and not a timestamp
comparison: `nfl/identity/code_identity.py` already computes code identity, and
the repository already learned in Phase 9 that a staging path keyed on anything
but content is a leak waiting to happen.

Two rules that are not optional:

- **A recomputation that changes a node's identity may not reuse the old
  artifact's name.** Superseding in place is how a reader ends up unable to say
  which bytes produced a number.
- **A cache hit may not be restamped.** `availability.py` already has a test for
  this exact failure (`test_f3_cache_hit_does_not_restamp`), inherited from the
  V7 weather defect where one clock was substituted for another and a stale
  artifact certified as fresh.

## 6. How it gets enforced without a rewrite

The honest constraint: most consumers are frozen or owned by other agents, and a
DAG that requires editing every reader will not be adopted. So the enforcement
path is the one the clock repair already used — put it upstream of the frozen
module.

**Phase 1 (cheap, and the only part I would build next).** A declaration-only
DAG: a module that states the edges, plus a test that walks the AST of every
production module for direct `glob`/`open` against `nfl/vintage` and
`nfl_vintage/raw` and fails on any read not declared as an edge. That test alone
would have caught `board.depth_rank`, `qb_allocation.captured_depth_chart`,
`team_volume_v1.coaches` and `coverage.load_week_plan` — all four of this audit's
glob-shaped findings — and it requires editing no consumer.

**Phase 2.** A `read(node, cut)` accessor that returns bytes only for declared
edges and only when `bitemporal.readable_at` passes, with the existing globs
rewritten to call it one at a time, each behind its owner's own test.

**Phase 3.** Content-addressed recomputation, once Phase 2 means the input set
of every derived artifact is actually known.

I am specifying Phase 1 as the next piece of work and explicitly **not**
claiming any of the three is started.

## 7. What this spec does not cover

`RAW_CAPTURE_STORE`, `PLAYER_STATE` and `GAME_STATE` from the Part B list. They
need a schema decision I do not have evidence for tonight — in particular
whether `PLAYER_STATE` is keyed by `(player, as_of)` or by `(player, week,
learned_at)`, which is the same bitemporal question one level up and should be
answered against real consumers rather than in the abstract.
