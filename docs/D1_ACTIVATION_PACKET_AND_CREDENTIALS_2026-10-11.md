# D-1 follow-up, 2026-10-11: RS-1 activation packet and agent-credential separation (nothing applied)

## Part A. RS-1: evidence for the activation decision

An independent reviewer verified RS-1 using only read (GET) requests. Full report, with every command, its output
and each documentation quote: `D1_RS1_INDEPENDENT_VERIFICATION.md` (copied beside this file).

| item | verdict | key evidence |
|---|---|---|
| Exact branch targeting | PASS | The remote has 6 branches. The four include strings are literals with no wildcard characters. Exactly `main`, `capture-prod`, `claude/nfl-greenfield-architecture-stsxmk` and the canary match. The canary does not exist yet (404). |
| Rule behaviour | PASS | `deletion` + `non_fast_forward` block deletion and any rewind, `--force-with-lease` included, for everyone, admins included (no bypass list). Fast-forward pushes, rebase-then-push and every PR merge style still work. Tags are unaffected. `evaluate` mode is Enterprise-only. |
| Current workflows | PASS, none breaks | Workflow files on all three tips were read. Every writer runs `git pull --rebase` then a plain push. There is no force push, `+refspec`, `:branch` or ref-delete API call. |
| Other writers | PASS | 300 events from 2026-09-29 to 2026-10-11 come only from the owner account and `github-actions[bot]`; all 299 pushes were fast-forward. The repository's whole history holds 2 force pushes (shared branch, 2026-09-08 and 09-09) and no branch deletion. |
| Permissions | PASS, 13 endpoints unverifiable | Public, user-owned repository; the session has admin; there are no rulesets or branch protection today. Collaborators, deploy keys, installed Apps and Actions settings are blocked to this session: **the owner checks these.** |
| Recovery | PASS, with 2 corrections to my proposal | An admin can always disable or delete a ruleset, so lock-out is impossible. **Corrections:** "ruleset history" does not exist on this plan (the audit trail is Rule Insights), and `nfl-capture-liveness.yml` is not on `main`, so it never runs and cannot raise an alarm. |
| Canary | PASS once fixed | The original steps could pass falsely and had the cleanup out of order. The corrected procedure is below. |

**Decision presented: READY TO ACTIVATE RS-1 exactly as specified, using the corrected procedure below.**

- I have not activated it. Activation is the owner's write, made with the owner's credential.
- Nothing else is proposed: no RS-2, nothing on `capture-prod` beyond RS-1, no other branch, no credential change.

### Corrected activation and canary procedure (every write is the owner's)

```text
T = current main tip (record the sha; main has no push-triggered workflow)

 0. Optional positive control, before activation: push canary at T, force-push T~1 to it (must SUCCEED), push T back.
 1. POST the RS-1 JSON exactly as in docs/D1_RULESET_PREFLIGHT_2026-10-11.md; record <id>.
 2. GET rulesets/<id>: enforcement "active", include == the 4 refs exactly, rules == [deletion, non_fast_forward],
    bypass_actors == [], current_user_can_bypass == "never".
    GET rules/branches/<b> for each of the 4: lists both rules with ruleset_id <id>.
 3. (if 0 was skipped) push canary at T: succeeds.
 4. Force-push T~1 to the canary: REJECTED by GitHub (server-side "GH013 ... repository rule violations").
    ls-remote: canary still at T.
 5. --force-with-lease rewind to T~1: REJECTED; tip still T.
 6. Delete the canary: REJECTED; still listed.
 7. Fast-forward control: a commit on top of T pushed to the canary: SUCCEEDS.
 8. Settings -> Rules -> Insights shows the refused attempts from 4-6.
 9. PUT rulesets/<id> with include = the three real refs, in full. Re-check step 2: 3 refs, canary uncovered,
    the three branches still list both rules. Only then delete the canary branch: succeeds.
10. Judge each writer by run conclusion, not by whether a commit arrived:
    - nfl-capture and nfl-availability runs are hours apart, and a run with nothing new commits nothing;
    - the next shared-branch writer (orchestrator or product board) completes normally.
```

A finding from this check, separate from RS-1: **capture liveness is not monitored at all.** The liveness workflow
exists only off `main`, so scheduled runs never execute it. Registering it on `main` would be a workflow change,
and workflows are owner-only. It is listed as a decision, not done.

## Part B. Separating agent credentials from the owner's administrator credential (investigation only)

### What is true today (measured)

- Agent sessions reach GitHub through the Claude GitHub connection as **the owner's own account**
  (`gh api user` -> `94924676jp-a11y`; repository permission `admin: true`).
- Push events from agent sessions are attributed to that account.
- GitHub cannot distinguish agent from owner. So an agent can:
  - merge pull requests;
  - edit or delete rulesets;
  - change settings.

  An approval rule cannot help either: GitHub never lets the author approve their own PR, and every PR here is
  authored by the owner's account.
- GitHub Actions workflows authenticate as the GitHub Actions app via `GITHUB_TOKEN`, with per-workflow
  `permissions:`. Two of them run the Claude Code Action with `contents: write`, using `CLAUDE_CODE_OAUTH_TOKEN`
  for the model and `GITHUB_TOKEN` for git.

### What agents need, and what they must not have (least privilege)

| capability | agent sessions need it? | today |
|---|---|---|
| read the repository | yes | yes |
| push to `claude/*` branches | yes | yes |
| open and update pull requests, comment | yes | yes |
| read Actions run results | yes | partly (some paths are blocked by the proxy) |
| push directly to `main` / `capture-prod` | **no** | yes (no rule yet; RS-1 stops rewrites only) |
| merge pull requests | **no** | yes |
| approve pull requests | **no** (an approval must be the owner's) | cannot approve its own, but could approve anyone else's |
| edit rulesets, branch protection or repository settings | **no** | yes (admin) |
| read or write secrets and Actions settings | **no** | blocked by the proxy, not by permission |

### Options (none applied; each is an owner decision)

| option | what changes | separation achieved | cost and unknowns |
|---|---|---|---|
| **1. Machine account as a collaborator** (recommended to investigate first) | Create a GitHub account for agents and invite it as a collaborator. On a personal repository a collaborator gets **write, never admin**. Agent sessions connect to GitHub as that account. | Agents cannot merge to `main` once RS-2 requires a PR with **1 approval**, because an agent-authored PR needs the owner's approval. Agents cannot edit rulesets or settings. | **Unverified:** how this environment binds the GitHub identity. The documented route is to connect GitHub at claude.ai/connect-github, which is tied to the claude.ai login, so agent sessions may need their own claude.ai seat linked to the machine account. A personal repository cannot restrict a collaborator to `claude/*` branches, so a ruleset would carry the branch restriction. |
| 2. Move the repository to a free organization | Organization roles (Write, Maintain), teams, and organization-level rulesets | Finer roles and branch restrictions per team or App | A larger change: repository URL, Actions secrets and integrations all move; the history is preserved |
| 3. A dedicated GitHub App for agent git operations | An App with `contents: write`, `pull_requests: write`, no `administration` | Clean least privilege, auditable as the App's identity | **Unverified:** whether this environment can use an App token in place of its connection. The token would live in an environment secret (handled through the environment's secret settings), and its expiry and rotation need a design. |
| 4. Keep the owner identity; rely on RS-1 plus report-only guards | nothing | Only rewrites and deletions are prevented. Merging, ruleset edits and settings changes stay possible for agents. | No cost. This is the residual risk today. |

### Authorization boundaries once separated (to be enforced server-side, not by agent behaviour)

1. `main` (and later `capture-prod`): changes only by PR, **with 1 approving review from the owner**, and no
   bypass for the agent identity.
2. A `CODEOWNERS` file naming the owner for `coordination/OWNER_DECISIONS.md`, the protected policies,
   `.github/workflows/`, `.claude/settings.json` and the guard files, with "require code owner review". The
   guard-file protection (D-2) then becomes real.
3. The agent identity has no admin role, so it cannot edit rulesets, settings or secrets.
4. Actions keeps `GITHUB_TOKEN` with per-workflow minimum `permissions:`. Any Actions identity that may write to
   `main` would be a separately reviewed exception.

**Required before any change:** the owner chooses an option; the binding of the GitHub identity in this
environment is verified for that option; and a rollback plan is written (re-connecting the owner account restores
today's behaviour). No credential or permission has been changed.
