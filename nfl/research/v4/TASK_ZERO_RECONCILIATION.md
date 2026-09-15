# TASK ZERO — repository reconciliation with `main`

Completed 2026-09-15. Everything below was read out of the repository. Where a
figure is unverified it says so.

---

## 1. Branch ancestry and final working HEAD

| | commit | committed | what it is |
|---|---|---|---|
| **Common ancestor** | `1034e272c5b69a3ade6585ecab48094d27eb31a9` | 2026-09-11T00:44:04Z | `NFL T-90 anchored capture 20260911T004357Z` |
| **`main` tip** | `619a00bde2b8c93b93905ae32ca5537659786b75` | 2026-09-15T13:06:52Z | `NFL vintage capture 20260915T130638Z` |
| **Dev tip before merge** | `382556bb14eccf8e0fd26976c670ffd77d214e30` | 2026-09-15T12:37:22Z | morning report |
| **Merge commit** | `2c0c36b0dd8a7ca69988b70a94c0f7b2fe3c1bb2` | 2026-09-15 | this reconciliation |

**Final working HEAD: `claude/nfl-greenfield-architecture-stsxmk` at the merge
commit and its successors.** `main` is now fully contained in this branch's
history. Divergence since the ancestor was 289 commits on `main` against 87 on
dev.

### A correction that has to lead, because it invalidated four days of planning

I reported earlier in this branch that **`main` stopped capturing on 2026-09-11**.
That was false. It came from a stale remote-tracking ref (`6d156196`) that I read
as the branch tip without fetching. Real `main` never stopped: it captured
continuously through 2026-09-15T13:06:52Z, which is the last commit listed above.
Every downstream inference I drew from "the capture network is down" was drawn
from a ref, not from the network.

---

## 2. Classification of the 289 commits

The directive asked for five buckets. Only one is occupied.

| class | count | files |
|---|---:|---|
| immutable / raw capture evidence | **289** | `nfl/vintage/*`, `nfl/availability_raw/*` |
| capture manifests | included above | `nfl/vintage_manifest.jsonl`, `nfl/availability_manifest.jsonl` |
| source / registry / workflow code | **0** | — |
| model / production code | **0** | — |
| research only | **0** | — |

`git diff --name-only 1034e272 619a00bd` filtered of `nfl/vintage/` and
`nfl/availability*` returns **the empty set**. `main` is a pure capture branch.
There was no code to reconcile and no model behaviour could have changed.

Staged into the merge: 947 added files, 2 modified (the two manifests).

---

## 3. Conflicts and how each was resolved

16 conflicts.

**Fifteen gzip blobs.** Same logical capture, different compression framing.
Each pair was decompressed and hashed: **all fifteen are byte-identical after
inflation.** `--ours` was taken, with no content loss. Taking either side was
equivalent; the check is what makes that statement true rather than hopeful.

**One manifest, `nfl/vintage_manifest.jsonl`.** Resolved by the append-only rule
as a union, not a pick:

```
base 1391  +  main-only 2800  +  dev-only 301  =  4492 lines
```

All 4492 parse as JSON. `nfl/availability_manifest.jsonl`: 24/24 parse. **No
capture history was rewritten, reordered or dropped** — the requirement the
directive placed on this step.

---

## 4. Raw hashes and manifest references after reconciliation

Verified against `value.sha256`, honouring `value.sha256_is_of`:

| result | count |
|---|---:|
| verified (hash is of uncompressed bytes, blob is gzip) | **1368** |
| `.reduced.` blobs, hash is of pre-reduction upstream — by design | 20 |
| **mismatches** | **0** |
| manifest rows naming a path absent from the checkout | 6 |

The 6 absent paths are **byte-identical in the ancestor, on `main`, and on dev**,
so they predate this merge and were not caused by it. Three resolve once the
later `.gz` spelling is applied. Three are the earliest capture's `raw/*` paths;
of those, two have their upstream content address preserved by a surviving
`.reduced.csv.gz`, and one — `raw/schedules.c563178ace7c6637.csv` — has no
surviving blob anywhere in the tree. That one is a real, small, pre-existing gap.
It is recorded here rather than repaired, because inventing a provenance for it
is exactly what the owner ruling on orphan blobs forbids.

---

## 5. Forecast seals

**121 of 121 boards carrying a `board.json` recompute their recorded
`draws_sha256`. Zero seals broken. Zero boards re-sealed.**

| | boards |
|---|---:|
| hash recomputes over **raw** bytes (`player_draws.npz`) | 116 |
| hash recomputes over **decompressed** bytes (`player_draws.npz.gz`) | 5 |
| governing namespaces | 109 |
| declared `REPLAY_C1` replay namespace | 12 |

The 5 are not an anomaly and not a repair. An earlier pass of this check
reported "104 of 109 recompute" because it hashed raw bytes for every board; the
five `.npz.gz` boards record the hash over the inflated array. **The checker was
wrong, not the seals.** Encoding-aware recomputation resolves all five with no
change to any stored artifact.

---

## 6. The eleven in-window inactives captures — classified, and it is bad news

The directive asked for a three-way classification: *source/executor now
operational for future games*, *historically valid in-window capture*, or
*post-window/postgame forensic retrieval* — noting the latter two are not
interchangeable.

**The honest answer is a fourth category the directive did not anticipate:
provenance-lawful and substantively empty.**

Counts, corrected. It is **8**, not 11. I had counted every capture timestamped
before the 00:15:00Z kickoff; eligibility is stricter than that, and correctly
so. Of the 12 captures in that looser span, **four are refused by two distinct
mechanisms, and both are the eligibility layer doing its job**:

| capture | retrieved | why not eligible |
|---|---|---|
| `20260914T230509Z` | 23:05:11 | `BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP` |
| `20260914T233421Z` | 23:34:23 | `BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP` |
| `20260915T000520Z` | 00:05:22 | no DEN@KC target declared — past `window_end` 00:05:00 |
| `20260915T000803Z` | 00:08:05 | no DEN@KC target declared — past `window_end` 00:05:00 |

The first two landed inside the window but were background sweeps rather than
window-anchored runs, and a sweep's basis may not discharge an obligation. The
second two were taken after the window closed, so the scheduler had already
dropped the target. **This is worth stating plainly: the eligibility layer
discriminates correctly at every level it inspects.** It separates anchored runs
from sweeps, and it enforces the window boundary to the second. It simply never
inspects whether the bytes contain a football player. That is what makes D20 a
content-layer defect and not a provenance one.

The 8 that pass eligibility cleanly:

`20260914T225240Z`, `230328Z`, `231657Z`, `232654Z`, `233515Z`, `234455Z`,
`235244Z`, `235935Z`.

**On provenance they are impeccable.** Each has
`execution_target.declared_before_fetch: true`, basis
`SCHEDULED_WINDOW_ANCHORED`, executor = GitHub Actions workflow
*"NFL T-90 anchored capture"* on `refs/heads/main`, and a `retrieved_at` inside
the declared window `2026-09-14T22:45:00Z .. 2026-09-15T00:05:00Z`, all before
the 00:15:00Z kickoff. Each passes `discharge_eligibility` for
`2026_01_DEN_KC` kind `inactives` with `refusals: []`.

**On content they are empty.** Every one of them stored
`https://www.nfl.com/inactives/` showing its own empty-state text —
*"Please check back soon for NFL Inactive Reports for this Season"* — with zero
`<table>` and zero `<tr>`. So did the 29 sweeps taken after kickoff, including
ones 13 hours after the game ended.

So the classification is: **historically valid in-window capture of a page that
contained no inactive players.** The executor is operational. The obligation is
not discharged. Both are true and neither substitutes for the other.

This is recorded as **D20**, replayed by
`nfl/tests/test_inactives_substance.py`, and handed to the networked agent as
**OUT-016**. Its blast radius is **374 captures over nine days**, not 8 —
the entire `official_inactives` corpus since 2026-09-07 is the same empty page.

**The Week-1 miss remains a miss.** `d1e2727743c93990` was sealed without
`official_inactive_ids` and stays that way. What changes is only the diagnosis:
the obligation was attempted, lawfully, eight times, and the source had nothing.

---

## 7. Three claims I made about this window, in order, and why each was wrong

This belongs in the record because the pattern is the point, not the individual
errors.

1. **"The window closed unfilled with zero attempts."** False. Eight lawful
   attempts. I had read this branch's manifest and treated it as the repository.
2. **"`main` carries in-window PASS captures, so the window was filled."** False.
   They are empty. **I committed this one** — it is in the body of `2c0c36b`,
   written before I decompressed a single blob. I had read the manifest rows
   describing the captures and treated them as the captures.
3. **"The blast radius is 37 captures in the 09-14/15 window."** False. It is
   374 over nine days. Section C of the replay test counted them and corrected me.

Each correction came from looking exactly one layer deeper than the previous
claim had: branch → repository, manifest row → blob, window → corpus. **Every one
of the three is the project's canonical defect class** — *a step that returned
nothing, or something partial, was read as success* — with me in the role of the
step. The manifest said `PASS` 374 times and I believed it twice.

`2c0c36b`'s message is left standing with its error intact rather than amended.
Historical evidence is not altered to make the current tree green, and that
applies to my own commit messages.

---

## 8. Metadata repair made in passing

`nfl/research/live/OPEN_DEFECTS.json` carried `n_defects: 18` against 19 entries
in `defects`. Appending D20 set both to 20. Flagging it because silently
correcting a counter is how a discrepancy stops being investigable — the
off-by-one predates D20 and its cause was not diagnosed.

---

## 9. What Task Zero does NOT establish

- **Week-2 capture readiness is not re-evaluated here.** The executor runs and
  the inactives source is broken; those are separate questions and the second one
  blocks the first for any game whose board depends on an inactives gate.
- **No model behaviour was verified or changed.** `main` carried no code.
- **The suite result is not in this document.** It was still running when this
  was written. A result that has not been read is not a result.
