# Enforcement boundary: what the Phase 1 guards can and cannot stop

Phase 1, owner priority 3, 2026-10-11. Every row below was measured or read from code in this worktree; nothing is
inferred from a document.

## The one-line answer

**Nothing in Phase 1 is a guarantee.** Both guards are REPORT_ONLY by a code constant, and even if they were armed,
they would classify only the text of a tool call made by a Claude Code session whose project root is this
repository. The only guaranteed protection for `main` and `capture-prod` would be **server-side** branch protection
or rulesets on GitHub. **Measured 2026-10-11: none exists.** `gh api repos/94924676jp-a11y/nfl/branches/<b>` returns
`"protected": false` for `main`, `capture-prod` and `claude/nfl-greenfield-architecture-stsxmk`, and
`gh api repos/94924676jp-a11y/nfl/rulesets` returns `[]`.

## Three layers, kept apart

| Layer | What it is | Can it block? | Who can bypass it |
|---|---|---|---|
| **A. Advisory classification** | `coordination/git_guard.py` and `nfl/tools/floor_guard.py`, both `ENFORCEMENT = 'REPORT_ONLY'` | **No.** git_guard prints nothing to the hook's stdout; floor_guard is not called by anything as a gate. Both pinned by tests. | Not applicable: it records, it does not stop |
| **B. Client-side hook (pre-existing)** | `coordination/mode_guard.py` as a PreToolUse hook in `.claude/settings.json` | Yes: it can deny the tool call **in a session whose project root is this repo** | Any session rooted elsewhere (this one is rooted at `mlb-prop-system-v7`, so no NFL hook runs in it), `disableAllHooks` in any settings layer, a user-level settings file, a script that does the write itself, a human, GitHub Actions, another agent |
| **C. Server-side** | GitHub branch protection / rulesets | Yes, for everyone, including humans with write access and Actions | Repository admins only, and only when "include administrators" is off |
| **C today** | **absent** | **No** | Everyone |

## What layer A sees and does not see

| Path to a protected operation | Seen by git_guard? | Evidence |
|---|---|---|
| Bash tool text: git, gh, redirections, heredocs, `$(...)`, `bash -c`, `eval`, subshells, `cd` | Yes (parsed, not substring-matched) | `nfl/tests/test_git_guard.py` tests 1, 9, 10 |
| Python run inline (`-c`, heredoc), incl. `subprocess.run([...])` and `os.system` | Yes, when its paths and argv are constants or foldable | test 10 (`subprocess.run(['git','push','--force',...])`) |
| Edit / Write / MultiEdit / NotebookEdit | Yes (path; MultiEdit `edits[]` bodies) | tests 1, 10 |
| GitHub MCP tools of any server whose name contains `github` | Yes (matcher `mcp__.*github.*`) | test 8 |
| `python3.12 some_tool.py` that writes or pushes by itself | **No** (the script body is not in the tool call) | documented residual |
| A path computed at run time (`$VAR`, sys.argv, network) | **No** | documented residual |
| `git apply` / `patch` of a file that does not exist when the hook runs | **No** (would also fail to apply) | review fixture write-27 |
| Effects that depend on history (`git merge`, `git reset --hard`, `git stash pop`, `git pull`) | **No** | documented residual |
| A session rooted in another directory | **No hook runs at all** | this session |
| GitHub Actions workflows, other agents, humans, the GitHub web UI | **No** | by construction |

## What layer A records when it cannot run

| Condition | What happens | Evidence |
|---|---|---|
| Branch policy unreadable or corrupt | Falls back to the built-in floor `main`, `master`, `capture-prod`; every force/delete push treated as protected; each record carries `policy_unreadable` | test 4 |
| Hook payload not JSON / not an object / oversized | `GUARD_INPUT_INVALID`, would-decision DENY | tests 3, 10, 11 |
| git_guard missing or fails to import | stderr `NOT_EXECUTED`, `GUARD_IMPORT_FAILED` would-deny record written without importing git_guard | test 9 |
| git_guard raises at run time | `GUARD_ERROR` would-deny record (distinct label) | test 11 |
| An agent-written approval file present | Changes nothing: no file, token or flag is honoured; writing one is itself `SELF_APPROVAL` | test 5 |
| Hooks disabled (`disableAllHooks`) | **Nothing runs, so nothing is recorded.** The write that sets it is recorded if made through a tool call in a hooked session | test 9; residual |

## The pre-existing mode guard's own fail-open behaviour (D1, not changed by Phase 1)

`mode_guard.decide()` returns no decision when no mode is set, when PROJECT_STATE is unreadable, or when it
crashes. Phase 1 deliberately did not change `decide()` (AST-identical to base `0c5bf600`), and test 12 shows the
hook's stdout and exit code are byte-identical to the base on 81 calls in three modes, 11 of which the base denies.
Making the mode guard fail closed changes what blocks legitimate work and is an owner decision (Phase 2 candidate).

## What would make protection guaranteed (owner action; the agent cannot and must not do it)

On GitHub, Settings -> Rules -> Rulesets (or Branches -> Branch protection) for `main` and `capture-prod`:
1. Block force pushes.
2. Block deletion.
3. Require a pull request before merging (the owner as the approving reviewer).
4. Optionally restrict who can push, and include administrators.

For the shared branch `claude/nfl-greenfield-architecture-stsxmk`: block force pushes and deletion only (agents
must still be able to push to it).

These are the only controls in this list that hold against every actor in the table above.
