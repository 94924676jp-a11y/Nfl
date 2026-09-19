# Full-slate DFS: what exists, what is missing, and the order to build it

**No 150-max optimizer is authorized and none is built.** This document exists
to answer the prior question the directive asks first: what components already
exist, and what are actually missing.

## 1. The decomposition, preserved as the packet states it

```
football worlds → site scoring → salary/universe → candidate lineups
   → field model → duplication → contest payout simulation → lineup EV
   → portfolio optimization
```

Each arrow is a place a wrong answer can enter without the next stage
noticing. The order below follows it.

## 2. Gap map, measured against HEAD `e6eeed5`

| Component | State | Evidence |
|---|---|---|
| **Football worlds** (per-player joint draws) | **EXISTS, single-game only** | The sealed DET @ BUF board carries 8,000 worlds. There is no full-slate world generator: no path builds all ~26 games of a main slate into one joint object |
| **DK scoring adapter** | **EXISTS, certified** | `nfl/dfs/scoring/draftkings.py`, `VERIFIED_AGAINST_ENGINE` |
| **FD scoring adapter** | **EXISTS, relayed provenance** | `nfl/dfs/scoring/fanduel.py`, `VERIFIED_RULE_VALUE_RELAYED_SOURCE`. Not upgraded |
| **Shared scoring interface** | **MISSING — new finding** | The two adapters do not share a key schema; a caller written against one raises `KeyError` on the other. See `FULLSLATE_ADJUDICATION.md` §3 |
| **DST scoring** | **ABSENT ENTIRELY** | `statline.NOT_SIMULATED`: "the engine produces no team-defence outputs at all". Blocks five of the packet's claims and any lineup that must field a defence |
| **Kicker scoring** | **EXISTS** | `score_kicker` on both adapters, distance-bucketed |
| **DK Showdown legality** | **EXISTS, repaired** | Team-coverage enforced as a DP dimension |
| **DK/FD Classic site contracts** | **MISSING, and BLOCKED** | See §3 |
| **Roster universe (full slate)** | **MISSING** | The Showdown universe contract covers one game |
| **Legal full-slate solver** | **MISSING** | No Classic-rules solver of any kind |
| **Dependence diagnostics** | **EXISTS as of this work** | `reproduce_external_panel.py`: ex-ante and realized correlations, joint-tail lift, stack p95 inflation, DK/FD comparison |
| **Right-tailed player distributions** | **PARTIAL** | The engine produces draws; no tail-calibration evidence exists for them at the player level |
| **Ownership model** | **MISSING** | No ownership data of any kind |
| **Field generator** | **MISSING** | |
| **Salary-remaining distribution** | **MISSING** | |
| **Stacking-distribution model** | **MISSING** | |
| **Duplication model** | **MISSING** | |
| **Payout engine** | **MISSING** | |
| **Lineup EV / portfolio objective** | **MISSING** | |

**Eleven of nineteen components are absent.** The packet's own §24 assessment —
"the DFS layer above the scoring adapter is essentially absent" — reproduces.

## 3. Site contracts: specified, and blocked on verification

The directive requires DK and FD Classic rules to be **independently verified**
against the operators' own rules pages and encoded as machine-readable
contracts. **This executor has no network** — the egress proxy returns 403 on
every outbound request, a standing declaration in `nfl/STATE_DECLARATIONS.md`.

Encoding the rules from recollection is exactly what the FanDuel episode
already cost, and the standing rule is that a relayed value keeps relayed
provenance. **So no site contract is written in this pass.** Writing one from
memory and labelling it verified would be the defect this project audits for.

What is prepared instead: the contract's required field list, so that when the
bytes arrive the encoding is mechanical and its provenance is unambiguous.

**DraftKings Classic** — positions and count; salary cap; FLEX eligibility;
minimum games represented; minimum teams represented; full scoring including
DST tiers and the points-allowed ladder; late-swap behaviour.

**FanDuel Classic** — positions and count; salary cap; FLEX eligibility;
minimum teams; **maximum players per team**; full scoring including the
half-point reception and the larger fumble penalty; late-swap behaviour.

**Neither site's rules may be inferred from the other.** The packet's own
measurement is the reason this matters structurally rather than cosmetically:
the *correlation* structure is shared (max difference 0.0153), so one world
generator serves both, but the *roster rules* are where the sites genuinely
diverge, and that is precisely the part that cannot be copied across.

Brute-force legality fixtures for both sites are specified and will be written
against the contracts, not before them — a fixture that encodes a rule nobody
verified tests the fixture.

Requested in `docs/AGENT_OUTBOX.md`.

## 4. Roadmap, dependency-ordered

### Stage A — before any full-slate optimizer

| # | Item | Blocked by |
|---|---|---|
| A1 | Certified DK and FD Classic site contracts | **network verification** — assigned |
| A2 | Shared scoring interface across the two adapters | nothing |
| A3 | DST scoring adapter, or an explicit decision to exclude DST from scope | A1 (tiers are site rules) |
| A4 | Complete roster universe for a full slate | A1 |
| A5 | DK/FD scoring equivalence tests on a common stat line | A2 |
| A6 | Legal full-slate solver with brute-force fixtures both sites | A1, A4 |
| A7 | Full-slate football-world generator (all games jointly) | nothing — this is football work, and it is the real dependency |
| A8 | Player-level right-tail calibration evidence | A7 |

**A7 is the gating item and it is football, not DFS.** Every DFS component
above the scoring adapter consumes a joint full-slate world object that does
not exist. Building field models before it would be building on nothing.

### Stage B — before contest-EV optimization

Ownership model · full-lineup field generator · salary-remaining distribution ·
stacking-distribution model · duplication model · payout engine.

**Every one of these needs contest data this repository does not have**, and
none of it is football data. It cannot be derived from play-by-play, and it
must never flow backward into football prediction.

### Stage C — before 150-max authorization

Calibrated field simulation · candidate-lineup EV · portfolio-level objective ·
overlap and correlation control · **exposure logic earned from the objective
rather than imposed as caps** · prospective contest validation.

## 5. Constants that may not be hardcoded

Forbidden as literals anywhere in production, per the directive and repeated
here because a list in a chat message is not a control:

QB exposure caps · stack percentages · bring-back percentages · salary-left
thresholds · ownership-product thresholds · boom thresholds · pairwise
correlation coefficients · RB+DST rules · duplication percentages.

Each is a field behaviour or a hypothesis to estimate. The packet's own
correlation table is **the strongest temptation here** and is explicitly
included in the ban: its numbers are measurements of two seasons under one
labelling scheme, our reproduction disagrees with several of them, and
freezing any of them into a simulator would import both the sampling error and
the labelling choice.

## 6. What this work did not do

Build an optimizer. Implement a field model. Write a site contract from
memory. Change the simulator. Hardcode a coefficient.

**V2 NOT YET EARNED**
