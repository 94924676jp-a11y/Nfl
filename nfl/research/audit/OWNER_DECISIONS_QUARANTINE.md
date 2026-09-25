# OWNER_DECISION_REQUIRED — quarantined items

Owner ruling 2026-09-25: *"Owner decisions block only the dependent branch of
work, not the project."* Each item below names what it blocks and, more
importantly, what it does **not**. Work continues everywhere else.

---

## OD-1 · Promote `unavailable_owns_nothing` from DIAGNOSTIC to HARD

**Decision required.** Whether a player the run itself declared unavailable
holding non-zero opportunity should stop a product build, or remain a reported
diagnostic.

**Why it matters.** On 2026-09-24 Jayden Reed was declared OUT and held 0.241 of
the WR gadget draws. As DIAGNOSTIC that is reported and the build continues.

**Blocked by it:** nothing but the severity of this one gate.

**NOT blocked:** the enforcement machinery is built, tested and live
(`nfl/dfs/gate_enforcement.py`). `SEVERITY` is a declared table and the module
enforces whatever it says, so the promotion is a one-line change whenever the
ruling comes. Every other gate already enforces. Twelve refusal-path tests pass
under the current table and will pass under the promoted one.

**Status:** QUARANTINED, not waiting.

---

## OD-2 · Shard `vintage_manifest.jsonl`

**Decision required.** Whether to split the manifest, and on what key.

**Why it matters.** 53.55 MB over 6,757 records, +0.81 MB/day measured over 4
commits-days. Past GitHub's 50 MB advisory; the 100 MB hard rejection lands near
**2026-11-21** at that rate. When it fires, every push stops.

**Blocked by it:** the migration itself, and only that.

**NOT blocked, and now done:** the consumer census the decision needs.
`nfl/tools/manifest_consumer_census.py`, measured at HEAD:

| | count |
|---|---|
| Files mentioning the manifest | 54 (29 production, 2 research, 24 tests) |
| **Would require an edit to shard** (non-test, not parameterised) | **21** |
| **Answer could change silently** (scans whole file AND depends on order) | **21** |
| Already parameterised — a shard-aware loader can be passed in | 9 |

The second row is the one that decides the strategy. Twenty-one modules both
scan the whole file and depend on ordering or on a last-match-wins rule. Split
the file and those answers can change **with no error raised**, which is the
repository's most expensive failure class arriving through the back door of a
storage change.

That argues for a shard-aware loader behind the existing path, rather than a
rename that forces 21 edits at once. It is evidence for the decision, not the
decision.

**Still to do before migrating, none of it owner-gated:** round-trip equality
tests per consumer, and converting the 21 hardcoded readers to accept a path.

**Status:** QUARANTINED, evidence complete, migration not started.

---

## OD-3 · Availability enum with `NOT_ESTABLISHED` as the default

**Decision required.** This one changes model behaviour: players currently
implicitly available become `NOT_ESTABLISHED`, which moves allocation.

**Why it matters.** `ACTIVE_FOR_GAME` / `OFFICIAL_INACTIVE` /
`RESERVE_EXEMPT_SUSPENDED_OTHER` / `NOT_ESTABLISHED` exists in no production
module. `grep` finds `OFFICIAL_INACTIVE` only under `nfl/research/`. The Josh
Jacobs distinction is enforced nowhere.

**Blocked by it:** the enum landing in `availability_feed.states()`, and the
forward-chained evaluation that a behaviour change requires.

**NOT blocked:** naming the states, writing the refusal tests against a fixture,
and the eligibility plumbing in `player_universe.build()`, which already takes
an explicit `eligible` set and refuses to default it to "everyone priced".

**Status:** QUARANTINED. Raised here rather than assumed, because a behaviour
change is exactly what the operating rule says not to take unilaterally.
