# NYG@LAR Showdown fixture — the scripts that produced this directory's data

Moved out of `nfl/dfs/showdown/` on 2026-09-25, unchanged apart from one
import. They sit beside the artifacts they wrote:
`NYG_LAR_SHOWDOWN_FIXTURE.json`, `FINAL20_*.json`,
`DKEntries_UPLOAD_NYG_LAR_20.csv`.

**Five of these seven cannot be imported**, because they do their work at
module level with no `if __name__ == '__main__'` guard. Measured 2026-09-25 in
a fresh interpreter:

| Module | Import result |
|---|---|
| `resolve_inactives` | `IndexError` — reads `sys.argv[1]` at module level |
| `run_research_fixture` | `IndexError` — same |
| `cleanup_pool` | `UPSTREAM_RUN_REFUSED` at stage `artifact_sealing` |
| `select_no_tracy` | `UPSTREAM_RUN_REFUSED` — same |
| `select_scale_invariant` | `UPSTREAM_RUN_REFUSED` — same |
| `research_fixture` | clean |
| `build_gpp20` | clean, **and that is the problem** — see below |

They are also pinned to one run, `d90d80c0b4a7f95e`, and three of them carry
`sys.path.insert(0, '/home/user/nfl')` — an absolute path to one machine.

`test_review_enforcement.py` calls three of these "the live selectors". They
are not live. The word there means "the ones used to make that slate's
selections"; they are reachable from no production entry point and pinned to a
historical run.

## `build_gpp20.py` — OBSOLETE, and it imports clean by accident

Its entire input is two files in a session scratch directory:

    pool = json.load(open('/tmp/claude-0/pool.json'))
    D    = np.load('/tmp/claude-0/draws.npy')

Both exist, dated 2026-09-21, which is the only reason the import succeeds. They
are not in version control, not in the evidence bundle, and are gone when the
container is reclaimed. At module level it then runs a 50,000-lineup build.

Kept rather than deleted so the record of what produced this slate stays whole.
Superseded by `nfl/dfs/showdown/optimal_worlds.py`. **Do not run it.**
