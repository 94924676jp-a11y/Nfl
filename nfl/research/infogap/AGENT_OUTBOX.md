# Agent outbox — requests that cannot be executed from this executor

Written 2026-09-08 alongside `RECEIVING_INFORMATION_GAP_RETURN.md`.

Nothing below is marked blocked in the return without appearing here. Blocked
for me is not blocked for the project: each item is **assigned**, not stalled.

## A. Vendor qualification for true routes run — GATED ON OWNER AUTHORISATION (§13)

Do not action this until the owner authorises §13 of the return.

**Constraint that survives authorisation: no contact, no account creation, no
purchase, no money.** Published material only.

Fill, per vendor, with a sourced value or an explicit `NOT PUBLISHED`:

| Field | Why it decides something |
|---|---|
| Publishes a per-player, per-game **routes run count** | If no, the vendor is irrelevant to this question |
| First season of coverage, and completeness by season | Must reach 2022 to be testable on the existing frame |
| In-season delivery cadence and lag after kickoff | Decides prospective usability |
| Point-in-time or restated | A restated file cannot support an as-of study |
| Licence terms for **model use** | Distinct from viewing terms |
| Redistribution terms | Decides whether derived artifacts can be committed |
| Price | Owner's decision input, not mine |

Hosts, all `000` from here (proxy refuses CONNECT), measured 2026-09-08:
`pff.com`, `www.pff.com`, `sportsinfosolutions.com`, `sportsdata.io`,
`nextgenstats.nfl.com`, `stathead.com`.

## B. Enumerate the nflverse-data release index — NOT GATED

`https://api.github.com/repos/nflverse/nflverse-data/releases?per_page=100`
returns a session scope refusal here, so §3 of the return could only probe
assets **by name**. That leaves a real gap: it is a statement about the assets I
could name, not a proof that no other asset exists.

Needed: the full list of release tags and asset names. Specifically resolve the
Next Gen Stats receiving asset — `nextgen_stats/ngs_2025_receiving.csv` and
`nextgen_stats/ngs_receiving.csv` both 404; `nextgen_stats/ngs_receiving.csv.gz`
returns 200 with a `Not Found` body. Its row in §3 is `NOT ESTABLISHED` for this
reason and should be corrected once the index is readable.

## C. Watch for 2026 participation — NOT GATED

Measured 2026-09-08, after the 2026 season opened:

- `pbp_participation/pbp_participation_2026.csv` → **404**
- `snap_counts/snap_counts_2026.csv` → **404**

Until these publish, **no participation-derived feature is available
prospectively**, which includes P itself. Neither file is in the project's
vintage capture set, so nothing is currently accumulating a point-in-time record
for them.

Requested: report the date each first returns 200, and whether it then updates
weekly in-season. Do **not** infer the answer from a final-file `Last-Modified`
— `pbp_participation_2025.csv` reads `10 Feb 2026` and
`pbp_participation_2024.csv` reads `04 Sep 2025`, and both are final writes that
prove nothing about in-season availability in either direction.

## Verified from here, for the record — do not re-request

- `nflverse-data` licence is **CC BY 4.0**, read from `LICENSE.md`.
- Release **assets** are fetchable from this executor (200 after redirect), even
  though the releases **API** is not.
- `pbp_participation` is published and populated for **2016–2025**.
- `pff_id` covers **100%** of the WR/TE/RB frame — 1,126 players, 47,215
  player-games — so a routes join would be deterministic. Identity is not a
  blocker.
