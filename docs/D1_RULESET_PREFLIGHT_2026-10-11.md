# D-1 pre-flight: GitHub rulesets for `main`, `capture-prod` and the shared branch

Owner decision 2026-10-11: D-1 approved **with pre-flight validation; nothing is applied until the final
configuration below is approved.** Status: **NOT APPLIED.** Every fact below was read from the GitHub API or the
workflow files on `main` on 2026-10-11.

## 1. What the pre-flight found (three findings change the plan)

**F1. Four scheduled workflows write to the protected branches directly.** Requiring pull requests as written would
stop them.

| Workflow (copy on `main`; schedules run only from `main`) | Writes to | Active? | How it writes |
|---|---|---|---|
| `nfl-availability.yml` | **`main`** | **yes**: twice daily, last commit 2026-10-10 21:47Z (51 of the last 100 `main` commits) | `git pull --rebase` then `git push origin HEAD:main`, as `GITHUB_TOKEN` |
| `nfl-capture.yml` | **`capture-prod`** | **yes**: every 30 min, last commit 2026-10-11 00:08Z (100 of the last 100) | same pattern, `GITHUB_TOKEN` |
| `nfl-status.yml` | **`main`** | dormant (the copy on `main` has September cron dates) | same pattern |
| `nfl-t90.yml` | `capture-prod` | dormant (September cron dates on `main`) | same pattern |
| `nfl-product-board.yml` | shared branch | no recent commits | fast-forward push |
| `agent-orchestrator-dispatch.yml` | shared branch only (hard allowlist of one branch) | on dispatch | fast-forward push |
| `claude-engineering-dispatch.yml`, `ai-bridge.yml` | shared branch (`AUTOMATION_BRANCH`) | on dispatch | Claude Code Action with `GITHUB_TOKEN`; `claude-engineering-dispatch` has `contents: write` |
| `agent-orchestrator-heartbeat`, `egress-probe`, `nfl-production-forecast`, `nfl-capture-liveness` | nothing | | read-only |

- No workflow force-pushes or deletes a branch.
- No workflow runs on `pull_request`, so **there are no status checks to require today**.
- There is no `CODEOWNERS` file.
- The `[bot]` names (`nfl-capture[bot]`, `nfl-availability[bot]`, `nfl-product[bot]`) are only git author labels.
  Every push authenticates as **GitHub Actions** (app id 15368, shown as `github-actions[bot]` in the push events).

**F2. Agent sessions act as the owner's account.**
- Push events from agent sessions are attributed to `94924676jp-a11y`, and this session's credential has
  `admin: true` on the repository.
- A rule GitHub enforces cannot tell an agent from the owner. A pull-request rule therefore stops a direct push, but
  an agent can still open **and merge** a PR as the owner.
- Required approvals are not usable either: GitHub never lets the author approve their own PR, and every PR here is
  authored by the owner's account, so the owner could not merge anything.
- An admin credential can also edit or disable a ruleset, so a ruleset cannot defend against a session that decides
  to remove it. Phase 1's git_guard reports `gh api .../rulesets` writes as PROTECTED_PUSH, but only reports.

**F3. Plan and capability.**
- The repository is **public** and **user-owned**, so rulesets and branch protection are available on the free plan.
- `evaluate` (dry-run) enforcement is an Enterprise feature, so **every ruleset here is `active` or `disabled`**.
- Not readable through this session's proxy (owner to confirm in Settings): Actions settings, the collaborator list,
  deploy keys, and the installed GitHub Apps.

## 2. Proposed configuration, staged so that nothing breaks

### Stage 1: RS-1 "no history rewrite" — ready to apply; breaks nothing measured

```json
{
  "name": "nfl-no-history-rewrite",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": [
    "refs/heads/main",
    "refs/heads/capture-prod",
    "refs/heads/claude/nfl-greenfield-architecture-stsxmk",
    "refs/heads/ruleset-canary/no-rewrite"
  ], "exclude": []}},
  "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}],
  "bypass_actors": []
}
```

- **What it stops:** force pushes and deletion of the three branches, by anyone: agents, Actions and the owner's
  credential alike. There is no bypass.
- **Workflows affected:** none. Every writer rebases and fast-forwards.
- **Agent work affected:** none. Agents may not force-push to the shared branch anyway.
- **`ruleset-canary/no-rewrite`** exists only to verify the rule (section 4). It is removed from the list afterwards.

### Stage 2: RS-2 "`main` only through a pull request" — needs one prerequisite first

```json
{
  "name": "nfl-main-via-pull-request",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
  "rules": [{"type": "pull_request", "parameters": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": true,
    "require_code_owner_review": false,
    "require_last_push_approval": false,
    "required_review_thread_resolution": false
  }}],
  "bypass_actors": []
}
```

- **Prerequisite P-1 (owner-approved workflow change):** move `nfl-availability.yml`'s commits off `main`, to
  `capture-prod` like the other capture writers, and do the same for `nfl-status.yml` before it is re-armed.
  Applying RS-2 without P-1 stops the availability watch at its next run. That fails visibly, but it is still a gap
  in capture.
- **Why there is no GitHub Actions bypass:** a bypass for app 15368 would also let the Claude Code Action workflows
  (`contents: write`) push to `main`. That is the broad bypass the owner ruled out.
- **Approvals are 0** because of F2. With one shared identity, an approval requirement would only lock the owner out.
  The rule's value is that every change to `main` becomes a visible, reviewable PR, not a silent push.

### Stage 3: `capture-prod` — the requested PR rule conflicts with how capture works

`capture-prod` is the data-capture branch, written every 30 minutes by `nfl-capture.yml`. Requiring PRs on it stops
capture unless GitHub Actions bypasses the rule. Options:

| Option | Rule on `capture-prod` | Effect | Recommendation |
|---|---|---|---|
| **A** | RS-1 only (no rewrite, no delete) | Capture continues. Agents could still push new commits. | **Recommended now** |
| B | RS-3: `{"type": "update"}` (restrict updates) with bypass `{"actor_type": "Integration", "actor_id": 15368, "bypass_mode": "always"}` | Only GitHub Actions can update `capture-prod`; agent sessions and the owner's credential cannot. The Claude Code Action workflows could, through the same app. | Optional. GitHub may refuse an Integration bypass for this app on a user-owned repository; verify at apply time and fall back to A. |
| C | Require PRs on `capture-prod` | Stops capture | Not recommended |

### Stage 4 (owner decision, outside this repository): a separate identity for agents

This is the only change that makes "an agent cannot merge to `main`" true. Agents would push with a credential that
has **write but not admin**: a GitHub App, or a dedicated machine account with a fine-grained token. RS-2 would then
require **one approval from the owner**, with no bypass for that identity. Until then, server-side rules stop
rewrites and silent pushes; they do not stop an agent that deliberately merges.

## 3. Emergency recovery

- **Owner, web:** Settings -> Rules -> Rulesets -> select the ruleset -> Enforcement: **Disabled** (or Delete).
  This takes effect immediately. Rulesets never restrict who may edit rulesets, so the owner cannot be locked out.
- **Owner, API:** `gh api -X PUT repos/94924676jp-a11y/nfl/rulesets/<id> -f enforcement=disabled`.
- **If capture stops after Stage 2 or 3:** `nfl-capture-liveness.yml` reports missing evidence within 60 minutes
  (two baseline ticks). Disable the ruleset, then re-run the capture workflow.
- **If a legitimate force push is ever needed:** disable RS-1, push, and re-enable. Every rewrite then leaves an
  audit trail in the ruleset history.

## 4. Verification after activation (each step must be observed, not assumed)

1. `gh api repos/94924676jp-a11y/nfl/rulesets` lists the ruleset with `enforcement: active`.
2. Canary:
   - push `ruleset-canary/no-rewrite` at any commit;
   - attempt `git push --force` of an older commit to it -> must be **rejected**;
   - attempt `git push origin :ruleset-canary/no-rewrite` -> must be **rejected**;
   - then remove the canary from the include list and delete the branch.
3. The next `nfl-capture` run (within 30 minutes) commits to `capture-prod`, and the next `nfl-availability` run
   commits to `main` (Stage 1 only).
4. For Stage 2, after P-1:
   - a direct `git push origin HEAD:main` from an agent session is **rejected**;
   - a PR to `main` can be opened and merged by the owner.

## 5. What needs the owner's approval to proceed

| ID | Action | Breaks anything? |
|---|---|---|
| D-1a | Apply **RS-1** exactly as above, then run the section 4 checks | No (measured) |
| D-1b | Approve **P-1** (move availability/status writes off `main`), then apply **RS-2** | Not after P-1 |
| D-1c | `capture-prod`: option **A** (recommended) or B | A: no |
| D-1d | Stage 4: a separate, non-admin identity for agents | Requires owner setup outside the repository |
