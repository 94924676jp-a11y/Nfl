# Storing a DraftKings contest — the manual procedure

This is the operating procedure for the owner. It is written for a person with
a browser and a downloads folder, not for a scheduler. **Nothing in this
package logs in to DraftKings, browses it, scrapes it, or downloads anything.**
Acquisition is manual by design; see "Why manual" at the end.

The acceptance standard the whole package exists to meet:

> A DraftKings contest file captured today must remain a verifiable,
> reproducible research artifact years from now without requiring DraftKings
> to still host it.

That is only achievable if the capture happens **while the file still exists**,
and if what we store is the operator's bytes rather than our reading of them.

---

## 0. The clock, and why this is urgent

DraftKings **GameCenter** contest exports are a *perishable* first-party
source. The working assumption for this project is that a completed contest's
standings export remains downloadable for roughly **ten days** after the
contest ends, after which the contest page is no longer reachable and the
field is gone for good from the first-party source.

**That ten-day window is recorded in
`nfl/dfs/history/capability.py` at `PRACTITIONER_REPORT` confidence, not as a
verified fact.** It comes from the owner's research brief, not from a
DraftKings service-level statement we hold. Treat it as a deadline to beat, not
a guarantee to rely on: if the real window is shorter, the only thing that
protects the data is having captured it earlier.

Practical rule: **capture within 48 hours of the contest ending.** Do not
batch a week's contests until the following Friday.

A file we failed to download is not recoverable by any amount of later work.
A file we downloaded and described badly is recoverable at leisure, because
the bytes are still here.

---

## 1. What to download, per contest

Get as many of these as the site offers. Each maps to a declared
`artifact_type` in `nfl/dfs/history/contracts.py`:

| What it is | `artifact_type` | Where it comes from |
|---|---|---|
| The **salary file** for the draft group (`DKSalaries.csv`) | `SALARY_FILE` | The lobby / draft-group export |
| The contest standings export — every entry, its lineup, its points | `CONTEST_STANDINGS` | **GameCenter**, after the contest completes |
| Anything describing the contest itself | `CONTEST_METADATA` | Contest page, lobby detail |
| The prize / **payout** table | `PAYOUT_STRUCTURE` | Contest page |
| Your own entries, if you entered | `ENTRY_FILE` | My Contests export |
| Anything else worth keeping | `OTHER` | — |

The **salary file is the one with the earliest expiry pressure and the one
most often skipped**, because it is available before the contest and feels
like it will always be there. It will not. Download it on slate day. Without
it, the standings export's player names cannot be tied to salaries, positions
or a draft group, and a large part of the archive's later value is gone.

**Do not rename, re-save, re-encode, or open-and-save these files in a
spreadsheet program before ingesting them.** Excel will rewrite line endings,
strip leading zeros from identifiers, and reformat timestamps. That changes
the bytes, and the bytes are the evidence. Ingest first; look at them
afterwards, from a copy.

---

## 2. What to write down while you still have the page open

The archive never fabricates a value the source did not supply — a
manufactured contest id would look exactly like a real one to a reader in
2029. So anything the file itself does not carry has to be recorded by hand,
**now**, from the page in front of you:

- **contest id** — the operator's own identifier, as DraftKings shows it.
  This is the single most valuable field. Without it, the contest gets a
  content-derived key (`DRAFTKINGS:NFL:NO_CONTEST_ID:<hash>`) which is stable
  and honest but cannot be matched against anyone else's records.
- `draft_group_id`, if shown.
- `contest_name`, exactly as written.
- **field size** — the contest's own declared maximum entries. This is what
  makes completeness checkable at all: `store.assert_completeness` returns
  `COMPLETE` only when the number of entries held and the declared field size
  both exist and agree. If you do not record the field size, the capture is
  permanently `COMPLETENESS_UNKNOWN`, and no later work can upgrade it.
- `entry_fee`, `entry_limit`, `contest_type` (GPP, double-up, …),
  `slate_type` (`CLASSIC` or `SHOWDOWN`), `start_time_utc`.
- `season` and `week`.
- The **payout** structure if it is on the page and not in a file — capture it
  as a screenshot or text file and store it as `PAYOUT_STRUCTURE` with
  `confidence=PRACTITIONER_REPORT`, rather than not at all.

Write these into the ingestion call below. Anything you genuinely do not know
stays `None`. **`None` is a correct answer; a guess is not.** The contracts are
built so that an absent field is visible as absent forever, and there is no
penalty for leaving one blank other than the work it makes later.

---

## 3. Which snapshot is this?

An NFL Classic slate has **late swap**, so "ownership" is not one number. The
same athlete has a different field share before the early games lock than
after. Every capture therefore declares a `snapshot_type`:

| `snapshot_type` | Meaning |
|---|---|
| `POST_INITIAL_LOCK` | Field as it stood when the first game of the slate locked |
| `INTERMEDIATE` | Any capture between initial lock and final settlement |
| `FINAL` | Field after all games have locked and the contest has settled |
| `SNAPSHOT_UNKNOWN` | You do not know — the default, and never upgraded by inference |

A GameCenter standings export pulled after the contest completes is `FINAL`.
Mark it `FINAL` only if you know it was pulled after settlement. If you are
unsure, leave it `SNAPSHOT_UNKNOWN`; an honest unknown is cheap and a wrong
`FINAL` silently corrupts every later comparison between snapshots.

Multiple snapshots of the same contest are expected and supported. Each is
stored as its own raw artifact with its own hash and its own `snapshot_type`;
they do not overwrite each other.

---

## 4. Ingest

From the repository root, with `python3.12`. Adapt the identity block to the
contest you are storing.

```python
import pathlib
from nfl.dfs.history import contracts as C, store as S, gamecenter as G

contest = C.DFSContestIdentity(
    contest_id='183492057',              # from the page; None if truly absent
    draft_group_id='97421',
    contest_name='NFL $100K Play-Action [$20K to 1st]',
    contest_type='GPP',
    slate_type='CLASSIC',
    entry_limit=20,
    field_size=58823,                    # the contest's DECLARED field size
    entry_fee=2.0,
    start_time_utc='2026-09-21T17:00:00Z',
    season=2026, week=3)

arts = []

# The salary file, stored as bytes, uninterpreted.
raw = pathlib.Path('~/Downloads/DKSalaries.csv').expanduser().read_bytes()
out = S.store_raw(raw, contest=contest, artifact_type=C.SALARY_FILE,
                  original_filename='DKSalaries.csv',
                  snapshot_type=C.SNAPSHOT_UNKNOWN,
                  confidence=C.VERIFIED_PRIMARY)
assert out.state.name == 'PASS', (out.code, out.detail)
arts.append(out.value)

# The GameCenter standings export.
raw = pathlib.Path('~/Downloads/contest-standings-183492057.csv') \
    .expanduser().read_bytes()

# Parse AFTER, only to describe the bytes. The parse never gates the store.
p = G.parse(raw, contest=contest, snapshot_type=C.FINAL)
parsed = p.value if p.state.name == 'PASS' else {}
n_entries = len(parsed.get('entries', [])) if parsed else None

out = S.store_raw(raw, contest=contest, artifact_type=C.CONTEST_STANDINGS,
                  original_filename='contest-standings-183492057.csv',
                  snapshot_type=C.FINAL,
                  schema_fingerprint=parsed.get('schema_fingerprint'),
                  row_count=n_entries,
                  parser_version=G.SPEC_VERSION if parsed else None,
                  confidence=C.VERIFIED_PRIMARY)
assert out.state.name == 'PASS', (out.code, out.detail)
arts.append(out.value)

comp = S.assert_completeness(n_entries_held=n_entries or 0,
                             declared_field_size=contest.field_size)

man = C.DFSContestManifest(
    contest=contest, artifacts=arts,
    snapshot_type=C.FINAL,
    completeness=comp['completeness'], completeness_why=comp['why'],
    information_cut='2026-09-22T14:00:00Z',
    notes=['downloaded manually by the owner from GameCenter'])

w = S.write_manifest(man)
print(w.code, w.detail)
```

**Store the bytes even if the parse refuses.** `store_raw` and `G.parse` are
deliberately independent: a refusal such as `GAMECENTER_ENTRY_TABLE_NOT_FOUND`
means our column guesses do not match this file, which is a parser problem we
can fix next year from the stored bytes. It is not a reason to discard the
file. If the parse refuses, store the raw artifact with `row_count=None` and
`parser_version=None`, put the refusal code in `note`, and move on.

---

## 5. Verify, before you close the terminal

```python
from nfl.dfs.history import store as S, contracts as C
out = S.rehydrate(S.contest_dir(contest))
print(out.code, out.detail)
```

`rehydrate` re-reads the manifest and re-hashes **every** raw file it lists.
Anything other than a `PASS` means the capture is not trustworthy and must be
redone while the source still exists. A capture you did not verify is not a
record — it is a hope.

Then commit. The archive lives in git under `nfl/dfs_history/`; a file on a
laptop is not an archive.

---

## 6. After ingestion — derivation is a separate, repeatable act

Nothing in step 4 computes ownership. Derivation happens later, any number of
times, from the stored bytes:

- `derive.operator_ownership(...)` reads DraftKings' own `% Drafted` column and
  labels it `OPERATOR_PUBLISHED`.
- `derive.derived_ownership(...)` counts the entries we actually hold and
  labels it `DERIVED_FROM_FIELD`.
- `derive.compare_ownership(...)` places the two side by side.

These are **never merged into one number.** The operator's published figure and
our count of a possibly-partial field are different measurements of different
populations, and a capture that is `INCOMPLETE` or `COMPLETENESS_UNKNOWN`
makes the derived figure a lower bound on a denominator we do not know.

`derive.duplication(...)` counts how many entries share a lineup. For
**Showdown**, the Captain slot is position-sensitive: the same six athletes
with a different Captain are a **different** lineup and must not be collapsed
into one. `canonical_roster` distinguishes the `CPT` slot for exactly this
reason.

---

## 7. Why manual, and what is deliberately absent

This package contains no browser automation, no scraping, no login or session
handling, no CAPTCHA handling, and no unattended DraftKings downloading, and
none is to be added under this workstream. `capability.DRAFTKINGS_GAMECENTER`
records `automated_acquisition_built = False` at `VERIFIED_PRIMARY`
confidence — the one claim in that record we can verify absolutely, because it
is a claim about our own repository.

The priority is preserving data safely, not automating site interaction.

## 8. What this archive must never do

This package is **isolated from football forecasting**. Ownership, `% Drafted`,
field composition, duplication, payout structure, salary and contest metadata
are DFS-structure facts. They must not flow backward into player projections,
team volume, role, efficiency, appearance, game simulation, or touchdown
probability. `nfl/tests/test_dfs_history.py` asserts the absence of that import
path structurally, so the isolation is checked rather than promised.
