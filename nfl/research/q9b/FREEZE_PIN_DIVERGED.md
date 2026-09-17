# The Q9 prospective freeze pins a `layers.py` that is no longer in the tree

**Found by `nfl/tests/test_qb_eligibility_den_kc.py::test_q9_frozen_layers_are
_untouched`, which has been failing and telling the truth.** Recorded
2026-09-17.

## The measurement

`nfl/research/q9b/Q9_PROSPECTIVE_FREEZE.json` declares, inside
`candidate_identity.module_source_sha16`:

```
"nfl.production.nonqb.layers": "481f005f682cd721"
```

Measured `sha256[:16]` of `nfl/production/nonqb/layers.py` by commit:

| commit | sha16 | matches the pin |
|---|---|---|
| `8e58650` Repair 4 | **481f005f682cd721** | **YES** |
| `16d3c45` SC2 | f5f4bde081d54da6 | no |
| `8801225` week-1 rows help R8 | 419ea433cba65dab | no |
| `137a257` support kinds | 419ea433cba65dab | no |
| `638af4f` QY1 | b081a5b2fa45be25 | no |

## Who moved it, and it was not QY1

The pin broke at **`16d3c45`, the SC2 interception reservation**, which added
the reservation branch to `receiving_conversion`. It was already broken at
`137a257`, the parent of the QY1 commit. QY1 changed the file again, from
`419ea433cba65dab` to `b081a5b2fa45be25`, and that is the third distinct
value since the freeze — but the divergence predates it by two commits.

Stating this precisely matters because the failing check names the file, and a
reader arriving at it after the QY1 commit would reasonably conclude QY1 broke
a seal. It did not. It widened an existing divergence.

## Q9 IS reproducible, and that is the important distinction

The frozen blob **exists in this repository**: every commit touching the path
was hashed, and `8e58650` carries `481f005f682cd721` exactly. So Q9's frozen
candidate identity can be reconstructed by checkout.

That is a materially different state from an unrecoverable freeze, and the two
must not be collapsed:

| claim | status |
|---|---|
| The freeze names a specific `layers.py` | YES |
| That exact file exists and is retrievable | **YES**, at `8e58650` |
| The current working tree matches it | **NO** |
| Q9 can be re-run as frozen | **YES**, from `8e58650`, not from HEAD |

## What must NOT happen

**Do not update the pin.** Moving `481f005f682cd721` to the current hash would
convert a true failing check into a passing one without changing a single fact
about the frozen candidate, and it would destroy the only record of which
`layers.py` Q9's numbers came from. The check stays failing. A freeze whose
pin is edited to match whatever the tree holds today is not a freeze.

**Do not revert `layers.py` to the pinned version either.** SC2 and QY1 are
separate candidates with their own identities; the freeze governs Q9's
reproduction, not the file's future.

## What the pin actually means from here

`module_source_sha16` is a **reproduction instruction**, not a working-tree
invariant. Any Q9 re-run must check out `8e58650` for that module. The failing
test is the standing reminder that HEAD is not that commit.

The owed work, if anyone wants the check green honestly: make the pin's
assertion read "the pinned blob is retrievable from git" rather than "the
working tree equals the pin". That is a change to what the test claims and it
needs its own decision, so it is recorded here rather than made quietly.

**V2 NOT YET EARNED**
