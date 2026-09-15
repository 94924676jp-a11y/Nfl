# Does every capture family require substance, or only absence-of-known-badness?

Item 4 of the 2026-09-15 directive: generalise the D20/D22 lesson across every
source family that decides `PASS / DEFERRED / FAIL / BLOCKED`. Audited at HEAD
`0914801`.

**Headline: the registry family had the hole and it is closed (D20, D22). The
other three families were audited and are sound. No new defect was found, and
two apparent findings turned out to be artifacts of my own test harness — both
recorded below, because that is exactly the failure mode this audit exists to
catch.**

---

## 1. The families

`grep -l` over everything that constructs an `Outcome` on a capture path gives
four families, not one:

| family | module | decides on |
|---|---|---|
| **registry / vintage** | `nfl/tools/capture_vintage.py` + `nfl/capture/registry.py` | html, json, csv fetched from a declared URL |
| **availability watch** | `nfl/capture/availability.py` | csv assets polled for existence and schema drift |
| **delivered** | `nfl/capture/delivered_injuries.py` | packages handed over by the networked agent |
| **live game evidence** | `nfl/capture/live_game_evidence.py` | in-game observations |

Only the first was covered by D20 and D22. The rest are audited here.

## 2. Registry / vintage — the hole, and it is closed

| content kind | what decided PASS before | what decides it now |
|---|---|---|
| html | a count of one marker word, which appeared 41 times in page chrome | `row_container` — the shape the rows live in |
| json | `len(list)` or list-lengths-plus-scalars, i.e. the envelope: 35 against 800 real entries, **and still 35 when emptied** | `payload_path` — entities at a declared path |
| csv | `len(nonblank lines) - 1`, which never looks at a column | `required_columns` present **and populated**, plus `substantive_any_of` |

Positive control: all 428 espn blobs, all 296 csv blobs, all 354 injury-report
blobs still pass. Negative control: six seeded emptiness cases all refused,
including the one the old check provably could not see. Bypass: stripping each
declaration makes the seeded violation pass again.

**Three sources have no contract and cannot get one here** —
`official_transactions`, `pbp_participation`, `snap_counts`, all with zero
committed blobs. Their schema cannot be READ, and inventing plausible column
names would be the 7,926-row defect committed on purpose. Reported
`NOT_EXECUTED`, which is not a pass, and filed as **OUT-017**.

## 3. Availability watch — sound, and I was wrong twice about it

My first reading was that `assert_body_is_data` is a **negative list**: it
refuses HTML, refuses a body that is literally `not found`, refuses zero bytes,
and then returns `BODY_LOOKS_LIKE_DATA`. "Looks like" is not "is", and
enumerating known-bad shapes rather than requiring a known-good one is precisely
the D20 shape one level up.

That reading is correct about that one function and **wrong about the family**,
because it is not the whole gate. Run end to end on `pbp_participation`:

| seeded body | verdict |
|---|---|
| accepted header, **zero data rows** | `FAIL / HEADER_ONLY_PAYLOAD` |
| `error: service unavailable` | `FAIL / HEADER_ONLY_PAYLOAD` |
| accepted header + one good row | `PASS`, `n_rows=1` |
| header + a ragged row | `FAIL / CSV_RAGGED_ROWS` |
| header + an unterminated quote | `FAIL / CSV_RAGGED_ROWS` |

`schema_fingerprint` requires `rows >= 1` and requires the body to parse to a
rectangle; `assert_schema_accepted` fails closed on any header this project has
not already accepted, and its docstring explicitly refuses to let "the bits we
use are still there" soften the verdict. The unterminated-quote case is
particularly good: Python's csv reader does not raise on it, it swallows the
rest of the file into one tidy-looking field, and the ragged check is what
catches it.

**Two near-misses of mine, recorded because they are the same class as the
defects being hunted.** First I tested `assert_body_is_data` and
`assert_schema_accepted` in isolation, saw both pass on a header-only body, and
was about to report a hole — the row gate lives in a third function I had not
called. Then I called that third function with a `str` where it takes `bytes`,
got `PAYLOAD_UNDECODABLE` on all five cases including the healthy one, and would
have reported the guard as broken. **A test harness that produces a uniform
verdict across cases designed to differ is reporting on itself, not on the
code** — the tell was that the good row failed too.

## 4. Delivered packages — integrity, and that is what it claims

`delivered_injuries` verifies that every declared file exists, hashes to its
declared digest, and round-trips out of the stored blob
(`DELIVERED_PACKAGE_HASH_MISMATCH`, `DELIVERED_RAW_ROUNDTRIP_FAILED`). That is
an **integrity** check, not a substance check, and it does not claim otherwise.

Substance for this family is enforced downstream at identity resolution
(`DELIVERED_IDENTITY_AMBIGUOUS` and the roster-index join), and empirically the
18 delivered captures in the store carry real inactive lists — they are the only
genuine ones in the repository. **The family is not holed, but the separation is
worth stating: a hash proves a byte is the byte we were given. It says nothing
about whether that byte is a football player.** That sentence is the whole of
D20 and it applies here too, even though nothing has gone wrong yet.

## 5. Live game evidence — out of scope for pregame, audited anyway

Fails on missing required fields and on unparseable payloads. It cannot
discharge a pregame obligation and does not claim to. No pregame-relevant
substance decision passes through it.

## 6. The generalisation, stated once

A capture check answers one of three questions, and the project's expensive
defects have all come from reading one as another:

| layer | question | what it cannot tell you |
|---|---|---|
| `FETCH_SUCCESS` | did bytes arrive, intact, in the window, under a basis that can discharge | whether there is anything in them |
| `STRUCTURAL_VALIDITY` | do the bytes contain the entities they are supposed to contain | whether those entities are about this game |
| `PREDICTIVE_ELIGIBILITY` | may this evidence discharge THIS obligation for THIS game | whether the model should believe it |

Formalised in `nfl/capture/evidence_layers.py`, monotone, with a verdict naming
the **first** layer that failed. `None` means NOT ASKED and never counts as a
yes; `may_discharge` requires all three True, and two-of-three is asserted
insufficient.

## 7. What this audit did not do

- It did not test the three contract-less sources, because they have no
  payload. `NOT_EXECUTED` stands until OUT-017 returns a sample.
- It did not audit non-capture families — the product gates, the scoring path,
  the board publisher. The same question applies to them and has not been asked.
- It found no new defect. **That is a result, not a lack of one**, and it is
  reported as such rather than padded.
