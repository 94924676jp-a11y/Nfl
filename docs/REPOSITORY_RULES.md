# Repository rules

Governing rules that apply across the whole tree, each with the case that
caused it and the module that enforces it.

## Repository rule — an artifact is claimed by verifying the file

**Refusal:** `ARTIFACT_CLAIM_WITHOUT_VERIFIED_FILE`
**Module:** `sportsplatform/governance/artifact_claim.py`
**Test:** `nfl/tests/test_artifact_claim.py`

Any command or task that reports an artifact as created must establish all
five of these, from the filesystem:

1. the file exists on disk;
2. its size is greater than zero;
3. the expected schema or header is present;
4. any hash is computed from the actual file bytes;
5. the path reported to the caller is the path that was verified.

**Do not infer artifact existence from printed output or a successful-looking
terminal snippet.**

### Why, with the case that caused it

On 2026-09-18 `nfl/dfs/scoring/dual_board.py` was run as
`python3.12 ... | head -22`. The table printed, `head` closed the pipe, the
process took SIGPIPE, and it died before `out.write_text(...)`. The file was
never created, and the commit message that followed described it anyway.

`print()` writes to a buffer, and whether that buffer reaches a terminal has
nothing to do with whether a later write happened. Under a pipe, stdout is
flushed *earlier* than a file write that appears *after* it in the source — so
"it printed the path, so it must have written the file" is not merely weak
reasoning, it is backwards.

### How to comply

```python
from sportsplatform.governance import artifact_claim as AC

out.write_text(json.dumps(...))
c = AC.claim(out, schema=['rows', 'evidence'], label=out.name)
if c.state is not State.PASS:
    return 1
```

`claim()` prints a line produced *by* the verification — `VERIFIED <path> (N
bytes, sha256 ...)` — so a generator cannot announce a success it did not have.
`claim_or_raise()` is the same with a non-zero exit.

### Already applied

`dual_board.py`, `captain_metrics.py`, `optimal_worlds.py`, `scenarios.py`,
`correlation.py`, `ownership_audit.py`. A test asserts each of them claims its
output and that none still prints a bare `wrote <path>`.
