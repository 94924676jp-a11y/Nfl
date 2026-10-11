# RS-1 `nfl-no-history-rewrite`: independent pre-activation check

- **Reviewer:** independent agent session, read-only. Only GET requests were made. No ruleset, branch, setting, credential or workflow was created, changed or deleted.
- **Time:** 2026-10-11, 03:27Z to 03:34Z.
- **Repository:** `94924676jp-a11y/Nfl`. The API returns `full_name` "94924676jp-a11y/Nfl", and the lowercase `nfl` resolves to the same repository.
- **Proposal reviewed:** `docs/D1_RULESET_PREFLIGHT_2026-10-11.md` at commit `c3930604748b` on `claude/d1-ruleset-preflight`. Only RS-1 was in scope.
- **Local clone `/home/user/nfl`:** the only command that touched it was `git fetch origin claude/d1-ruleset-preflight`, which updated `FETCH_HEAD` only. The working tree is clean. `origin/main` is still the stale `f2b89b6`, so every workflow file was read from the live tip SHAs reported by `ls-remote`.
- **Raw outputs** are saved under `/tmp/claude-0/d1verify/raw/` (API JSON, events, activity) and `/tmp/claude-0/d1verify/wf/<branch>/` (workflow files).
- **GitHub docs:** `docs.github.com` was blocked by the proxy (`CONNECT tunnel failed, response 403`). I read the same docs from their source instead: the `github/docs` repository (`main` branch, fetched 2026-10-11) through raw.githubusercontent.com, saved in `/tmp/claude-0/d1verify/docsrc/`, plus GitHub's official OpenAPI description from `github/rest-api-description`. The source file paths and published URLs are given below.

## Verdicts

| # | Item | Verdict |
|---|---|---|
| 1 | Exact targeting | **PASS** |
| 2 | Rule behaviour (docs) | **PASS**. Two sub-points are inferences, marked below |
| 3 | Current workflows | **PASS**: RS-1 breaks none |
| 4 | Other writers | **PASS** (window caveat below) |
| 5 | Permissions / current state | **PASS** for what is readable; 13 endpoints are **UNVERIFIED-OWNER-MUST-CHECK** |
| 6 | Recovery paths | **PASS**. One claim in the proposal is wrong for this plan (ruleset history) |
| 7 | Canary procedure | **PASS, with fixes required to the procedure** (safe to run; as written it can give a false pass) |

**Recommendation: READY TO ACTIVATE.** Apply RS-1 exactly as specified, but only with the corrected canary and post-check procedure in section 7. Nothing blocks activation. The items the owner must check (section 5) cannot make RS-1 break a workflow; at worst they reveal another writer that RS-1 would correctly refuse.

---

## 1. Exact targeting: PASS

`git ls-remote --heads origin` at 03:33:38Z:
```
49d2f75c6f19...  refs/heads/capture-prod
c3930604748b...  refs/heads/claude/d1-ruleset-preflight
75a6125d3a2b...  refs/heads/claude/h1-top-of-board-prereg
0c5bf600f3f2...  refs/heads/claude/nfl-greenfield-architecture-stsxmk
477a2b73edce...  refs/heads/claude/phase1-guards-report-only
b178b63e76cf...  refs/heads/main
```
The six branch names from `gh api repos/94924676jp-a11y/nfl/branches?per_page=100` agree, and all six show `protected: false`. There are no tags: `git ls-remote --tags origin` gives 0 and `gh api .../tags` returns `[]`.

**Matching the include list.** I checked each include string against every live ref with case-sensitive `fnmatchcase` (`/tmp/claude-0/d1verify/raw` session output):
```
metachars in patterns: []
refs/heads/capture-prod                              -> ['refs/heads/capture-prod']
refs/heads/claude/d1-ruleset-preflight               -> []
refs/heads/claude/h1-top-of-board-prereg             -> []
refs/heads/claude/nfl-greenfield-architecture-stsxmk -> ['refs/heads/claude/nfl-greenfield-architecture-stsxmk']
refs/heads/claude/phase1-guards-report-only          -> []
refs/heads/main                                      -> ['refs/heads/main']
```
- None of the include strings contains a wildcard or character-class metacharacter (`* ? [ ] { } \`). Each one is a literal and can match only its own ref.
- The spelling and case match `ls-remote` byte for byte.
- Exactly the three intended branches match, plus the canary. Nothing else matches.
- The three other `claude/*` branches are not covered. That is correct for this proposal.

**How GitHub matches `ref_name` (from the docs).**
- The OpenAPI schema `repository-ruleset-conditions.ref_name.include` says: *"Array of ref names or patterns to include. One of these patterns must match for the condition to pass. Also accepts `~DEFAULT_BRANCH` to include the default branch or `~ALL` to include all branches."* The OpenAPI's own `POST /repos/{owner}/{repo}/rulesets` example uses the same `"refs/heads/main"` form as the proposal.
- `data/reusables/repositories/about-fnmatch.md` says: *"Because GitHub uses the `File::FNM_PATHNAME` flag for the `File.fnmatch` syntax, the `*` wildcard does not match directory separators (`/`). For example, `qa/*` will match all branches beginning with `qa/` and containing a single slash..."* Published at https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#using-fnmatch-syntax
- **If patterns had been used instead:** `refs/heads/claude/*` would also cover the three other `claude/` branches, and `~ALL` would cover every branch. Neither is used, so the include list is exact.
- `~DEFAULT_BRANCH` is not used. A literal `refs/heads/main` would not follow a rename of the default branch, but RS-1 itself blocks that rename (see item 2), so this is consistent.

**The canary does not exist yet, and it will be covered.**
- `gh api .../branches/ruleset-canary%2Fno-rewrite` returns `404 Branch not found`.
- `gh api .../git/matching-refs/heads/ruleset-canary` returns `[]`.
- No branch is named exactly `ruleset-canary`. Such a branch would make the `/no-rewrite` name impossible to create.
- RS-1 has no `creation` rule, so creating the canary is allowed after activation. Once it exists, it is covered by its literal include string.
- `gh api .../rules/branches/ruleset-canary/no-rewrite` works for a branch that does not exist (it returns `[]` today), so after activation it gives a read-only check that the canary is covered before anyone pushes it.

## 2. Rule behaviour: PASS

| Question | Answer | Evidence |
|---|---|---|
| What `deletion` blocks | Deleting the matching ref by anyone without bypass, whatever the route: `git push :ref` or `--delete`, the web UI, or the REST `DELETE .../git/refs/heads/...` | Docs: *"Restrict deletions: If selected, only users with bypass permissions can delete branches or tags whose name matches the pattern you specify."* OpenAPI `repository-rule-deletion`: *"Only allow users with bypass permissions to delete matching refs."* (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#restrict-deletions). Rules are enforced on the server, so every route that updates a ref goes through them. That last step is an inference. |
| What `non_fast_forward` blocks | Any update that moves the ref to a commit that is not a descendant of its current tip | OpenAPI `repository-rule-non-fast-forward`: *"Prevent users with push access from force pushing to refs."* Docs: *"You can prevent users from force pushing to the targeted branches or tags."* |
| `--force-with-lease` | **Blocked** whenever the update is non-fast-forward. The lease is checked only by the client; the server sees an ordinary ref rewind. A lease push that happens to be fast-forward is allowed. | Follows from git semantics and the rule text (inference) |
| Rebase locally, then a fast-forward push (`git pull --rebase` then `git push`) | **Allowed.** The pushed tip descends from the remote tip. This is exactly what every workflow writer does (item 3). | Rule text |
| PR merges (merge, squash, rebase-merge) into a target branch | **Allowed.** Each one adds commits on top of the base tip. RS-1 has no `pull_request` rule. | Rule text (inference). The repository has merge, squash and rebase-merge all enabled. |
| "Update branch" on a PR | Merge-commit update: allowed. **"Update with rebase": blocked when the PR's head is one of the three branches**, because it rewrites the head. | `content/pull-requests/how-tos/create-pull-requests/keeping-your-pull-request-in-sync-with-the-base-branch.md`: *"You may not be able to use the `Update branch` button if the HEAD branch of your pull request is a protected branch."* (https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/keeping-your-pull-request-in-sync-with-the-base-branch). Today the only open PR is #3, whose head `claude/phase1-guards-report-only` is not covered. |
| Renaming the default branch | **Blocked** for everyone (no bypass) | Docs: *"If force pushes are blocked, organization owners or repository administrators will be unable to change or rename the default branch unless they are authorized to bypass the ruleset."* |
| Renaming any of the three branches | Probably blocked, because a rename deletes the old ref | Inference only, **UNVERIFIED**. The owner should not plan a rename without disabling RS-1 first. |
| Tag pushes | **Not affected.** `target: "branch"`, and the repository has 0 tags. | OpenAPI `target` enum `branch`/`tag`/`push` |
| Auto-delete of the head branch after merge | Would be blocked for a covered head branch. The setting is off (`delete_branch_on_merge: False`). | `gh api repos/94924676jp-a11y/nfl` |
| Does `bypass_actors: []` bind admins and the owner? | **Yes.** Rulesets have no built-in admin exemption; bypass exists only for actors on the list, and the list is empty. This differs from classic branch protection, where admins are exempt unless "include administrators" is set. | `rulesets-bypass-step.md`: repository admins are listed as *"eligible for bypass access"*, meaning they must be added explicitly. `about-rulesets.md` gives the example *"blocks force pushes for all users except repository administrators"* as something you configure. OpenAPI `bypass_actor`: `OrganizationAdmin` *"is not applicable for personal repositories."* **Confirm after activation:** `GET rulesets/{id}` must return `current_user_can_bypass: "never"`. The OpenAPI enum is `always`/`pull_requests_only`/`never`/`exempt`. |
| `evaluate` mode on this plan | **Not available** (user-owned public repository, GitHub Free) | OpenAPI `repository-rule-enforcement`: *"`evaluate` is only available with GitHub Enterprise."* `data/features/repo-rules-enterprise.yml` lists `ghec`/`ghes` only, with no `fpt`, and the "Evaluate" bullet in `rulesets-about-enforcement-statuses.md` sits inside `{% ifversion repo-rules-enterprise %}`. |
| Are rulesets available at all? | Yes | `data/reusables/gated-features/repo-rules.md`: *"Rulesets are available in public repositories with GitHub Free..."*. Repo: `visibility: public`, `owner.type: User`. |

## 3. Current workflows: PASS (RS-1 breaks none)

**Branch tips read:** main `b178b63e`, capture-prod `49d2f75c`, shared branch `0c5bf600`. Full history is present (`--is-shallow-repository` is false; 2,335 commits reachable from the six tips).

**Registered workflows.** `gh api .../actions/workflows` lists 12 workflows, all `active`, including `agent-orchestrator.yml` (id 364776026), which exists only on the shared branch.

**What triggers a run.** Schedules run only from `main`. The only `push` trigger in any version of any workflow anywhere in history is the one below. I scanned 44 workflow blob versions with `git log --format=%H <6 tips> -- .github/workflows`.
```
agent-orchestrator.yml (4 historical versions, all identical in this respect):
  push:
    branches: [claude/nfl-greenfield-architecture-stsxmk]
    paths: [coordination/...]
```
No workflow has a `create`, `delete`, `pull_request` or `pull_request_target` trigger in any version.

**How each workflow writes** (the copies on `main` are the ones that run, except `agent-orchestrator.yml`, which runs from the shared branch):

| Workflow | Trigger | Writes to | Push code (quoted) | Rewrites or deletes? |
|---|---|---|---|---|
| nfl-availability | cron `17 6,18 * * *` + dispatch | **main** | `git pull --rebase --autostash origin main` / `git push origin HEAD:main` | no |
| nfl-capture | cron `*/30` + dispatch | **capture-prod** (`CAPTURE_BRANCH`) | `git pull --rebase --autostash origin "$CAPTURE_BRANCH"` / `git push origin HEAD:"$CAPTURE_BRANCH"` (comment: "Rebase rather than force") | no |
| nfl-status | September-only cron (dormant) + dispatch | **main** | `pull --rebase` / `git push origin HEAD:main` | no |
| nfl-t90 | September-only cron (dormant) + dispatch | capture-prod | `pull --rebase` / `git push origin HEAD:"$CAPTURE_BRANCH"` | no |
| nfl-product-board | cron `7,27,47` + dispatch | shared branch (`BOARD_BRANCH`) | 4 tries of `git pull --rebase --autostash` and `git push origin HEAD:"$BOARD_BRANCH"` ("Rebase, never force") | no |
| agent-orchestrator-dispatch | repository_dispatch + dispatch | shared branch (allowlist `ALLOWED=( "claude/nfl-greenfield-architecture-stsxmk" )`) | `git pull --rebase` then `git push origin "HEAD:<branch>"`. It runs `coordination/orchestrator/main.py`, whose `github_runtime.commit_and_push` uses `('git','push','-u','origin',br)` and refuses branches listed as protected. | no |
| agent-orchestrator (shared branch only) | push to the shared branch (`coordination/**` paths) + dispatch | shared branch (`github.ref_name`) | `git pull --rebase origin <ref>` / `git push origin <ref>` | no |
| claude-engineering-dispatch | dispatch | shared branch (constant) | `anthropics/claude-code-action@v1` with `GITHUB_TOKEN`, `--permission-mode acceptEdits`; commit through `ingest_engineering_return.py`, then plain push via `commit_and_push`. Its `reset --hard HEAD` is local to the runner only. | no |
| ai-bridge | issues opened | nothing directly (`contents: read`; Claude limited to `Read,Grep,Glob`; dispatches the engineering workflow) | none | no |
| agent-orchestrator-heartbeat, egress-probe, nfl-production-forecast, nfl-capture-liveness | | nothing (`contents: read`) | none | no |

**Searches for history-rewriting commands found nothing.** I searched `*.py`, `*.sh` and `*.yml` on all three tips for `push --force` / `-f` / `--delete` / `--mirror`, `+refspec`, `force-with-lease`, `git/refs`, `update-ref`, `branch -D`, `reset --hard` and `push origin :`. The only hits are the plain pushes above, test fixtures, and the local `reset --hard HEAD`.
- No `peter-evans/create-pull-request`, `stefanzweifel/git-auto-commit-action` or `gh api -X DELETE` appears anywhere.
- The only third-party write action is `claude-code-action`. If a model step inside it ever attempted a force-push, RS-1 would correctly reject it.
- No doc or runbook on main or the shared branch tells anyone to force-push.

**Conclusion.** Every writer creates new commits and fast-forwards. A race that loses still fails as non-fast-forward today, before any ruleset exists. RS-1 changes nothing for any workflow.

**Observed cadence (not caused by RS-1, but it affects the post-check).** `gh api .../actions/workflows/351879797/runs`: nfl-capture is scheduled `*/30` but actually ran at 2026-10-11T00:05Z, then 10-10 20:57Z, 17:33Z, 12:48Z, 06:07Z. That is every 3 to 6 hours, all `success`. nfl-availability ran at 21:47Z and 12:36Z, hours away from its cron. Capture also commits only when it captured something new: the capture-prod tip is still `49d2f75` from 00:08Z.

## 4. Other writers: PASS

**Events API.** `gh api repos/94924676jp-a11y/nfl/events?per_page=100`, pages 1 to 3. Page 4 returned `HTTP 422 pagination is limited`. That gives 300 events from 2026-09-29T13:43:50Z to 2026-10-11T03:28:22Z.
```
160 PushEvent  94924676jp-a11y      refs/heads/claude/nfl-greenfield-architecture-stsxmk
115 PushEvent  github-actions[bot]  refs/heads/capture-prod
 22 PushEvent  github-actions[bot]  refs/heads/main
  1 PushEvent  github-actions[bot]  refs/heads/claude/nfl-greenfield-architecture-stsxmk   (454a91dc, author agent-orchestrator, "[orchestrator-skip]")
  1 PushEvent  94924676jp-a11y      refs/heads/claude/h1-top-of-board-prereg
  1 PullRequestEvent 94924676jp-a11y opened #3 phase1-guards-report-only -> nfl-greenfield-architecture-stsxmk
```
- The PushEvent payload now carries only `ref, before, head, push_id, repository_id`. There are no `forced`, `size` or `distinct_size` fields.
- So I tested each push by ancestry instead (`git merge-base --is-ancestor before head`): **299 of 299 are fast-forward, 0 non-fast-forward, 0 objects missing.**
- The Events feed is incomplete: it holds no CreateEvent even though branches were created today. I therefore also read the Activity API.

**Activity API** (`gh api repos/.../activity?activity_type=...`):
```
force_push      n=2  2026-09-09T04:49:16Z 94924676jp-a11y refs/heads/claude/nfl-greenfield-architecture-stsxmk d983b47b84 -> eb284d598e
                     2026-09-08T13:34:07Z 94924676jp-a11y refs/heads/claude/nfl-greenfield-architecture-stsxmk 88d1e81e3e -> 3bd264e123
branch_deletion n=0
branch_creation n=6  main 2026-09-06, shared branch 2026-09-08, capture-prod 2026-09-15, phase1-guards / d1-ruleset-preflight / h1-top-of-board-prereg 2026-10-11 (all 94924676jp-a11y)
```
- **Force pushes:** there have been two in the repository's history. Both were on the shared branch, by the owner's account (agent sessions), more than a month ago, and none since. RS-1 would now refuse these. That is the intended effect, but it contradicts the proposal's "Agents may not force-push to the shared branch anyway", which is a policy, not a measured fact.
- **Deletions:** no branch has ever been deleted.
- **Actors:** only `94924676jp-a11y` and `github-actions[bot]` appear. No third actor shows up in either feed.

## 5. Permissions and current state: PASS, with items the owner must check

**Readable through this session:**
- **Repository:** `gh api repos/94924676jp-a11y/nfl` returns `visibility public`, `private False`, `owner 94924676jp-a11y type User id 323666670`, `default_branch main`, `permissions {admin: True, maintain: True, push: True, triage: True, pull: True}`, `delete_branch_on_merge False`, `allow_update_branch False`.
- **User:** `gh api user` returns login `94924676jp-a11y`, id 323666670, type User. The session acts as the owner's own account, with admin.
- **Rulesets:** `gh api repos/.../rulesets?includes_parents=true` returns `[]`. No ruleset exists, so nothing could combine with RS-1.
- **Active rules per branch:** `gh api repos/.../rules/branches/{main,capture-prod,claude/nfl-greenfield-architecture-stsxmk,ruleset-canary/no-rewrite}` returns `[]` for each of the four.
- **Classic protection:** `/branches` reports `protected: false` for all six branches. The direct `/branches/*/protection` read is blocked (see below), but `protected: false` already shows there is no classic protection.

**Blocked endpoints. Each is UNVERIFIED-OWNER-MUST-CHECK:**

| Endpoint | Response |
|---|---|
| `branches/{b}/protection` (all three) | 403 "Resource not accessible by integration" (covered indirectly by `protected: false`) |
| `actions/permissions`, `actions/permissions/workflow`, `actions/secrets`, `actions/variables` | 403 "Access to this GitHub Actions path is not permitted through this proxy" |
| `collaborators`, `invitations`, `keys` (deploy keys), `hooks`, `environments`, `autolinks` | 403 "not permitted through this proxy" |
| `teams` | 403 "Resource not accessible by integration" |
| `rulesets/rule-suites` (Rule Insights API) | 403 "Resource not accessible by integration" |
| `installation` | 401 "A JSON web token could not be decoded" |
| `user/installations` (installed GitHub Apps) | 403 "sessions are bound to their configured repositories" |
| `docs.github.com` | Proxy 403. I used the `github/docs` source instead. |

**What the owner should check in Settings:**
- Collaborators.
- Deploy keys, and whether any has write access.
- Installed GitHub Apps with write access.
- Actions → Workflow permissions.

These matter only for this reason: a writer I cannot see that relies on force-push or delete would start failing. The full-history Activity API shows no such writer, since every force push and deletion ever made is listed above.

## 6. Recovery paths: PASS (one correction needed)

**Who can edit rulesets.** `data/reusables/repositories/repo-rules-permissions.md`: *"People with admin access to a repository, or a custom role with the 'edit repository rules' permission, can create, edit, and delete rulesets for a repository."* None of the available rule types restricts editing rulesets (`available-rules-for-rulesets.md` lists every rule). RS-1 cannot lock the owner out of editing it.

**Disabling or deleting in the web UI.** The steps are in `about-editing-rulesets.md`, `edit-ruleset-steps.md` and `delete-ruleset-steps.md`, published at https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository
- Settings → "Code, planning, and automation" → **Rules → Rulesets** → click the ruleset → change Enforcement to **Disabled** → **Save changes**. The docs say: *"You can also edit a ruleset to change its status, such as if you want to enable or temporarily disable a ruleset."*
- To delete: the same page → `...` menu → **Delete ruleset**.

**Disabling or deleting through the API.** From the OpenAPI:
- `PUT /repos/{owner}/{repo}/rulesets/{ruleset_id}` has no required body fields, so `gh api -X PUT repos/94924676jp-a11y/nfl/rulesets/<id> -f enforcement=disabled` is a valid request.
- `DELETE /repos/{owner}/{repo}/rulesets/{ruleset_id}` deletes it.
- `PUT` **replaces** `conditions` and `rules` whenever they are sent, so a PUT that edits the include list must send all of it (see item 7).

**If the canary gets stuck.** A canary that cannot be deleted is harmless and can simply stay.
- To remove it: PUT the conditions with the three remaining refs, confirm `rules/branches/ruleset-canary/no-rewrite` returns `[]`, then delete the branch.
- Worst case: disable RS-1, delete the canary, re-enable RS-1.
- Every failure mode here leaves the rules too loose. None of them locks anyone out.

**Corrections to the proposal's section 3** (not blocking for RS-1):
1. *"Every rewrite then leaves an audit trail in the ruleset history"* is **not true on this plan.** Ruleset history is gated by `repo-rules-history`, whose `data/features/repo-rules-history.yml` lists only `ghec: '*'` and `ghes: '>=3.19'`, with no free tier. The audit trail on this plan is Rule Insights (Settings → Rules → Insights) and the owner's security log.
2. *"`nfl-capture-liveness.yml` reports missing evidence within 60 minutes"* is **not true today.** The file is absent from `main` (`git ls-tree b178b63e .github/workflows` does not list it), and it is not among the 12 registered workflows, so its schedule never runs. This affects the Stage 2/3 recovery plan, not RS-1.

## 7. Canary procedure: PASS with fixes

**Safety.**
- Pushing `ruleset-canary/no-rewrite` triggers no workflow at any commit in the repository's history. The only `push` trigger in any version is filtered to `branches: [claude/nfl-greenfield-architecture-stsxmk]`, and no workflow has a `create` trigger.
- No workflow writes to or reads from the canary.
- Creating the canary is allowed under RS-1, because there is no `creation` rule.

**Defects in the procedure as written:**
- **D1. It can pass falsely.** A rejection proves the rule only if it comes from GitHub. An agent session's local git guard or proxy could refuse the force-push first, and nothing currently tells the two apart. Fix: add a positive control, and require GitHub's server-side rejection text.
- **D2. "At any commit" is too loose.** Fix: pin the canary to an explicit commit `T` with a known parent. Use the current `main` tip, which has no push-triggered workflows at all.
- **D3. The order and form of the cleanup are unspecified.** A PUT that sends a partial include list silently drops protected branches. Fix: PUT the full three-ref list first, verify it, and only then delete the branch.
- **D4. Step 3's timing is wrong.** The step says "the next nfl-capture run (within 30 minutes) commits to capture-prod". Measured runs are 3 to 6 hours apart, and a run with nothing new makes no commit. Fix: judge each run by its conclusion and push step, not by the arrival of a commit.
- **D5. No test shows that normal pushes still work under RS-1.** Fix: add a fast-forward positive control.

**Corrected procedure.** All writes are performed by the owner.
```
0. (optional positive control, BEFORE activation) push canary at T = current main tip;
   git push --force origin T~1:refs/heads/ruleset-canary/no-rewrite   -> must SUCCEED
   (proves this credential/path can force-push at all); then push T back.
1. POST the RS-1 JSON exactly as in the proposal; record <id>.
2. gh api repos/94924676jp-a11y/nfl/rulesets/<id>  -> enforcement "active", include == the 4 refs
   exactly, rules == [deletion, non_fast_forward], bypass_actors == [], current_user_can_bypass == "never".
   gh api repos/.../rules/branches/<b> for main, capture-prod, the shared branch, ruleset-canary/no-rewrite
   -> each lists deletion + non_fast_forward with ruleset_id <id>.
3. (if 0 was skipped) git push origin T:refs/heads/ruleset-canary/no-rewrite  -> succeeds (creation allowed).
4. git push --force origin T~1:refs/heads/ruleset-canary/no-rewrite  -> REJECTED with a server-side
   "remote: ... GH013: Repository rule violations ... Cannot force-push to this branch"
   (expected wording from memory, not doc-verified); git ls-remote shows the canary still at T.
5. git push --force-with-lease=refs/heads/ruleset-canary/no-rewrite:T origin T~1:refs/heads/ruleset-canary/no-rewrite
   -> REJECTED; tip still T.
6. git push origin --delete ruleset-canary/no-rewrite  -> REJECTED ("Cannot delete this branch"); ls-remote still lists it.
7. Fast-forward positive control: C=$(git commit-tree -p T -m canary-ff T^{tree});
   git push origin $C:refs/heads/ruleset-canary/no-rewrite -> SUCCEEDS.
8. Settings -> Rules -> Insights shows the failed attempts from 4-6 (this is the audit trail on this plan).
9. PUT /rulesets/<id> with conditions.ref_name.include = the full three refs, exclude = [];
   re-run step 2: include == 3 refs, rules/branches/ruleset-canary/no-rewrite == [], main/capture-prod/shared
   still list both rules. Only then: git push origin --delete ruleset-canary/no-rewrite -> succeeds.
10. Post-check writers by run, not by commit: the next scheduled nfl-capture and nfl-availability runs
    (may be hours apart) conclude success with no push rejection in the commit step; the next
    orchestrator/product-board pass to the shared branch likewise. Optionally the owner dispatches
    nfl-capture once to get a prompt observation.
```

## Recommendation

**READY TO ACTIVATE.** The RS-1 JSON is correct as written. Nothing blocks activation.

Conditions for doing it:
- Run the corrected section 7 procedure instead of the proposal's section 4 step 2. It has a positive control, a pinned commit, the full include list in the PUT, and the cleanup in the right order.
- Do not rely on ruleset history or on `nfl-capture-liveness` for recovery or monitoring (section 6 corrections).
- The owner checks the section 5 Settings items whenever convenient. They are not prerequisites.
