# D20 coverage correction and supersession record

Week 1, 2026. Written 2026-09-15 at HEAD `a805b5a`. Nothing historical is edited
in place; this record supersedes the figure, it does not rewrite the artifacts
that carried it.

---

## 1. The correction

| | covered | missed | of |
|---|---:|---:|---:|
| **Superseded** — empty landing pages credited | **43** | 20 | 63 |
| **Corrected** — D20 substance check applied | **28** | 35 | 63 |

Reproduce either figure:

```
python3.12 -c "import sys; sys.path.insert(0,'.');
from nfl.capture import coverage as C;
print(C.coverage(2026,1,manifest_path='nfl/vintage_manifest.jsonl').evidence)"
```

The superseded figure is recovered by stubbing `coverage._has_declared_rows` to
always permit, which is exactly the pre-D20 behaviour.

## 2. Affected targets — all 15, and nothing else

Every target that moved is an `inactives` target. No other kind moved in either
direction; `missed -> covered` is empty.

| game | target | was | now |
|---|---|---|---|
| 2026_01_ARI_LAC | inactives | covered | missed |
| 2026_01_ATL_PIT | inactives | covered | missed |
| 2026_01_BAL_IND | inactives | covered | missed |
| 2026_01_BUF_HOU | inactives | covered | missed |
| 2026_01_CHI_CAR | inactives | covered | missed |
| 2026_01_CLE_JAX | inactives | covered | missed |
| 2026_01_DAL_NYG | inactives | covered | missed |
| 2026_01_DEN_KC  | inactives | covered | missed |
| 2026_01_GB_MIN  | inactives | covered | missed |
| 2026_01_MIA_LV  | inactives | covered | missed |
| 2026_01_NO_DET  | inactives | covered | missed |
| 2026_01_NYJ_TEN | inactives | covered | missed |
| 2026_01_SF_LA   | inactives | covered | missed |
| 2026_01_TB_CIN  | inactives | covered | missed |
| 2026_01_WAS_PHI | inactives | covered | missed |

## 3. What 28/63 does and does not mean

**28/63 is the truthful state of the GOVERNED CAPTURE ROUTE.** It is not the
same as "we do not know who was inactive", and reading it that way would be a
second error in the opposite direction.

Of the 35 misses:

- **13 hold real, game-anchored inactives bytes that the ledger refuses to
  credit**, and the refusal is correct: they arrived through the delivered route
  under a schema carrying no declaration block, so they cannot discharge a
  capture obligation. The mapping is exact — the 13 games with
  `missed_with_uncredited_evidence` are precisely the 13 games holding an
  `INACTIVES_INGESTION.json`, with no game on either side unmatched.
- **22 have nothing at all.** Among them are the only two Week-1 games with no
  inactives knowledge of any kind: `2026_01_DAL_NYG` and `2026_01_DEN_KC`.

So the honest three-line summary is: the capture network discharged 28 of 63
obligations; the project additionally *knows* the inactives for 13 more through
a route that is deliberately not a discharge; and for 2 games it knows nothing.

## 4. The critical question, answered explicitly

> Did any prediction use these empty inactive captures, or was the corruption
> limited to capture/coverage reporting?

**The corruption was limited to capture-state and coverage reporting. No
prediction consumed a false inactive list, and no board derived a value from an
empty page.** Four independent checks, each reproducible:

**(a) Every real inactives ingestion came from a per-game article, not the
landing page.** All 13 `INACTIVES_INGESTION.json` records carry
`provenance.kind = EXTERNAL_AUTHORITATIVE_DELIVERY` and an
`official_source_url` under `nfl.com/news/...` — twelve from
`inactive-reports-sunday-week-1-2026-nfl-season`, one from
`australia-game-inactives-san-francisco-49ers-at-los-angeles-rams`. Zero cite
`/inactives/`.

**(b) The project already knew, and wrote it down.** `2026_01_SF_LA`'s ingestion
record carries a field named `what_this_is_not` reading, verbatim:

> "This is NOT a capture of nfl.com, and these names were NOT verified against
> the generic /inactives/ page, which is a placeholder carrying no list and is
> the wrong document."

Dated 2026-09-10. **The fact was known five days before D20 was found.** What
failed was not discovery — it was propagation: the knowledge sat in one game's
provenance block and never reached the registry, the capture guard, or the
coverage reader. That is the finding worth carrying forward from this record.

**(c) Pre-inactives boards derive nothing from the empty page.** Taking
`2026_01_ARI_LAC/pre_inactives_V1_CANDIDATE_R8/16add7fc0320a7c3`: the empty blob
`official_inactives.67511bb2cfc1e9f3` appears only under
`information_set.sources.official_inactives`, an honest record of what was on
hand, stamped `hours_before_kickoff: 67.684` — nearly three days out, when no
inactives list could exist anywhere. The board carries **no**
`qb_inactive_ownership`, and no key whose name contains "inactive" outside that
provenance block.

**(d) Post-inactives boards use the article blob and carry the real ownership.**
The matching `post_inactives_V1_CANDIDATE_R8/797eed72f07fbd9b` cites
`official_inactives.423d0c34811cd6d6` — 904,360 bytes, no empty-state marker —
and carries `qb_inactive_ownership` with
`official_inactive_evidence_ingested: true` and a genuinely excluded quarterback
(`ARI: 00-0041561`).

### Where the empty page DID reach, and it is not nothing

**83 artifacts name an empty landing-page blob in their information set or
consumed partitions**, including production boards under
`nfl/product/boards/2026_01_SF_LA/`, every `pre_inactives_*` research board, and
the four Q9 shadow dry-run `SEALED_FORECAST.json` files.

This is provenance, not input — but it is not harmless, because a consumed
partition enters the **identity fingerprint**. Two consequences, both open:

1. A forecast's identity is partly determined by a document that contained
   nothing. Re-running it requires that exact empty page.
2. It makes "which inputs did this forecast actually use" unanswerable from the
   partition list alone, which is the question the partition list exists to
   answer.

Neither changes a number. Both are recorded here rather than repaired, because
repairing them means re-sealing forecasts, and a seal is not edited to make a
later tree tidy.

## 5. Did any candidate or model consume the false evidence?

**No candidate's coefficients, priors or draws were affected.** The empty page
never produced a player identifier, so nothing downstream could have used one.
The eligibility gate's own distinction protected this: `official_inactive_ids`
of `None` means "no list was available" and is recorded as such, and is not the
same as `()`, which asserts a list exists and is empty. Pre-inactives boards got
`None`. The gate never saw a false empty list.

## 6. What is superseded, and what is not

**Superseded:** any statement of Week-1 coverage as 43/63, 15/48, or any figure
crediting `official_inactives` landing-page captures.

**NOT superseded, and NOT edited:**

- The 374 manifest rows. They remain `state: PASS` with their original
  `n_data_rows`. Capture evidence is append-only.
- Every board, seal and dry-run artifact listed in §4. None re-sealed, none
  re-labelled.
- **The Week-1 DEN@KC inactives miss.** It remains a miss. Eight lawful
  in-window captures were made and the source had nothing; that is a different
  diagnosis, not a different outcome.

## 7. Reproducing this record

Every figure above is recomputed from `nfl/vintage_manifest.jsonl` and the
artifacts named. The 15/13/22 partition is asserted in
`nfl/tests/test_capture_obligations.py` section on coverage counts, and the
capture-layer behaviour in `nfl/tests/test_inactives_substance.py`. D20 itself
is recorded in `nfl/research/live/OPEN_DEFECTS.json`.
