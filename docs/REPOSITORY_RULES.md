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

---

## Repository rule — a commit is claimed by reading git

**Refusal:** `COMMIT_CLAIM_WITHOUT_VERIFIED_GIT_STATE`
**Module:** `sportsplatform/governance/commit_claim.py`
**Test:** `nfl/tests/test_commit_claim.py`

The companion to `artifact_claim`. Any workflow reporting "committed `<sha>`"
or "pushed `<sha>`" must verify from git state, not from a command appearing to
work:

1. the expected commit exists;
2. the reported sha is the commit that was verified;
3. the intended files are actually in that commit;
4. working-tree state is reported **separately** and is not folded into the
   verdict;
5. push success is a different question from commit success;
6. suppressed stderr is never evidence of success.

### Why, with the case that caused it

Minutes after the `artifact_claim` rule was written, this ran:

```
git add sportsplatform/... nfl/tests/... COMMANDS.md 2>/dev/null; git commit ...
```

`COMMANDS.md` exists in the MLB repository and not this one. **`git add` is
atomic over its pathspecs** — one unknown path staged *zero* files, not
everything else — and its stderr went to `/dev/null`. The commit then reported
"no changes added to commit", which is easy to skim past.

Three properties of git conspire, each individually reasonable:

- `git add` is atomic, so a nine-of-ten-correct command is not nine-tenths
  successful;
- `git commit` with nothing staged exits non-zero, but in a `;`-chained line
  the earlier failure is already invisible;
- **`git push` on an unchanged branch prints "Everything up-to-date" and exits
  zero** — a push that pushed nothing is indistinguishable from one that did,
  by exit status alone.

### How to comply

```python
from sportsplatform.governance import commit_claim as CC

CC.verify_staged(paths, repo=repo)                 # before committing
CC.claim(branch, sha='HEAD', expect_paths=paths)   # commit then push, apart
```

`CC.run()` returns a refusal carrying the exit status and stderr text, so
`2>/dev/null` is not available as a way to make a broken git call look fine.

STAGED is not COMMITTED and COMMITTED is not PUSHED. The module refuses to
collapse them.
