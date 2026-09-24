# ATL @ GB inactives — SECONDARY report, owner relay

**Received:** 2026-09-24 ~23:09Z (screenshot clock 7:08 PM ET).
**Source:** RotoWire, relayed by the owner as a screenshot.
**Classification: `SECONDARY_REPORT`. NOT `OFFICIAL_GAMEDAY_INACTIVE`.**

## Why this is not ingested through the governed path

`nfl/tools/ingest_inactives.py` states in its own docstring that it "will not
accept a reporter's summary" and that `--bytes` must be the authoritative
document. This is a reporter's summary, delivered as an image, with no
preserved bytes, no publisher timestamp in machine form, and no hash. Feeding
it into the governed chain would make a secondary report wear an official
label, which is the exact laundering this repository exists to prevent.

It is recorded here instead, with its provenance stated, and it is used for
research and for the owner's own decision — which is what a secondary source
is for.

Seven-axis classification:

| axis | state | note |
|---|---|---|
| transport | NOT_APPLICABLE | relayed by hand, not fetched |
| content | PASS | names are legible and position-tagged |
| completeness | NOT_ESTABLISHED | no way to confirm the list is whole |
| attribution | PASS | the page names ATL @ GB, Thu 8:15 PM ET |
| freshness | PASS | ~66 minutes before kickoff, inside the filing window |
| eligibility | RESTRICTED | secondary; may inform research, may not set `OFFICIAL_GAMEDAY_INACTIVE` |
| consumption | NOT_ESTABLISHED | not fed to the governed engine |

## What it reports

**ATL inactive:** M. DeWalt (CB), S. Ebukam (LB), R. Longerbeam (CB),
E. Onianwa (OG), **Cooper Rush (QB)**, **Jack Strand (QB)**.

**GB inactive:** Z. Bako-Bewele (OT), Aaron Banks (OG), W. Brinson (DT),
A. Campbell (DT), **Jayden Reed (WR)**.

**Starters named:** ATL **QB M. Penix**, RB B. Robinson, WR Drake London,
WR Jahan Dotson, WR O. Zaccheaus, TE Kyle Pitts, K Nick Folk.
GB QB Jordan Love, RB M. Lloyd, WR C. Watson, WR M. Golden, WR Skyy Moore,
TE Tucker Kraft, K Trey Smack.

Conditions: 62°F, 5 mph ESE, 0% precipitation. Market (downstream only, never
a predictive input): GB -4.5, total 43.5.

## The two findings that matter

### 1. The model had Atlanta's quarterback backwards

The pinned run gave **Cooper Rush** a 0.657 probability of modelled
opportunity and had him leading Atlanta in attempts in 62.6% of simulated
worlds, against **Michael Penix Jr.** at 0.327 and 28.6%. The report says Rush
is inactive and Penix starts.

So the model's central QB call was not merely uncertain, it was inverted. That
is a substantive miss and it is recorded as one.

**My recorded prediction did not fire, and I am not claiming it did.** It read:
"If ATL's list rules out Penix and/or Tua, Cooper Rush's P(plays) should rise
toward 1.0." The antecedent did not occur — the inverse did. The prediction
was falsifiable and untriggered, which is a weaker outcome than either
confirmation or refutation, and it must not be reported as a hit.

What remains testable, and is the more important half: **Penix's conditional
mean given he plays is 14.16 DK points against an unconditional 4.63.** If the
post-inactive rerun moves him toward 14 and Rush to zero, the availability
evidence is reaching the allocation. If it does not, that is a wiring defect,
and that part of the prediction stands exactly as written.

### 2. Jayden Reed is confirmed inactive, and the gadget defect is now live

Reed was already declared OUT in the run's own truth snapshot, and today's
`unavailable_owns_nothing` invariant found him holding **the largest WR gadget
share in the game at 0.241 of draws, up to 8 carries**, because the gadget
pool filters on roster class and never consults availability.

This report confirms he is inactive. The defect is no longer a hypothetical
about a designation that might reverse: an officially inactive receiver holds
football mass in the current artifact. The repair is unchanged and still
unmade pending the owner's view; what has changed is that the case is now
concrete rather than illustrative.

## What is still owed

The official NFL filing, with preserved bytes, remains the artifact the
governed path needs and the outbox request stands. This relay is a
cross-check, and a useful one — the Week 2 Thursday operator relay in our own
capture history noted that the official list "matches the secondary RotoWire
list previously captured", so the two have agreed before. Agreeing before is
not the same as being authoritative now.
