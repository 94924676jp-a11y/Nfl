# Third-party agent and skill repositories: evaluation for the NFL engine and the NBA DFS product (2026-10-10)

This was a read-only evaluation. Each repository was cloned shallow into `/home/user/<owner>/<repo>` and **read, never
executed, installed or imported**. Each clone was reviewed independently. Every headline claim below was then re-checked by
grep against the files (section 8). Nothing was installed and no setting, hook, policy or workflow was changed.

| Repository | HEAD reviewed | Last commit | Tracked files | License |
|---|---|---|---|---|
| wshobson/agents | `46891e7` | 2026-10-04 | 1,150 | MIT |
| addyosmani/agent-skills | `1be8e34` | 2026-10-10 | 212 | MIT |
| msitarzewski/agency-agents | `f99f6aa` | 2026-10-08 | 382 | MIT |
| anthropics/claude-quickstarts | `9ec32b9` | 2026-10-07 | 648 | MIT at the root; `autonomous-coding/README.md` says "Internal Anthropic use." |
| anthropics/knowledge-work-plugins | `95bdacc` | 2026-10-09 | 1,285 | Apache-2.0 |

## 0. Verdict

**None of the five repositories contains anything specific to DFS, football, basketball, optimizers or forecast
calibration.** Each review searched the whole repository for DraftKings, FanDuel, DFS, NFL, NBA, salary cap, late swap,
MILP/ILP/PuLP/OR-Tools, Brier, CRPS, PIT, calibration scoring and leakage-safe backtesting. The searches returned zero hits, or
only incidental words such as finance VaR and a single line on look-ahead bias.

Almost everything in them is **prompt-only personas**. Only three items are tested, executable engineering that fits your work.
Five more are prompt protocols worth copying as reviewed text. The rest either duplicates what this repository and Claude Code
already do better, or conflicts with your governance.

**Recommendation:**
* add **no marketplace and no plugin**;
* vendor at most eight single files, each at its pinned commit, into **project** scope, through the owner-approval path, with a
  provenance record;
* write the DFS-specific verifiers yourselves, because nothing here would beat them.

## 1. Current-state capability inventory (what already exists, verified in the tree)

### NFL repository (`94924676jp-a11y/Nfl`, branch `claude/nfl-greenfield-architecture-stsxmk`)

| Area | What exists | Where |
|---|---|---|
| Claude Code configuration | one PreToolUse hook on Edit/Write/MultiEdit/NotebookEdit/Bash. No project agents, skills or commands | `.claude/settings.json` → `coordination/mode_guard.py` |
| Authority boundary | modes BUILD / VERIFY / RESEARCH / OPERATE, with may-write and may-not-write tables. BUILD cannot self-certify. Always-denied paths are `OWNER_DECISIONS.md`, `AUTOMATION_POLICY.json`, `MODELS.json`, `MODE_POLICY.json` and `.github/workflows/` | `coordination/MODE_POLICY.json` |
| Project instructions | nine governing rules, among them: no false green, no silent constants, zeros are errors, a guard must reject a seeded violation and fail its bypass test, corrections stay visible, and a test not run by the harness does not exist | `CLAUDE.md`; MLB `CLAUDE.md` + `docs/AGENT_PROTOCOL.md`; `docs/AGENT_OUTBOX.md` |
| Autonomous orchestrator | about 5,465 lines of Python: dispatch, state machine, locks, proof chain, provider transports, MOCK fixtures. Engineering runs on `anthropics/claude-code-action@v1`, owner review on OpenAI, research on Perplexity. **Disarmed:** `autonomous_operation_enabled: false`, `execution_mode: MOCK`. It has budgets, an escalation stop-list that opens an issue labelled `owner-escalation`, and a ban on pushing to the default branch | `coordination/orchestrator/`, `coordination/AUTOMATION_POLICY.json`, `coordination/AUTONOMY_SETUP.md` |
| GitHub Actions | the branch has 10 workflows (capture, liveness, availability, status, T-90, product board, production forecast, orchestrator, heartbeat, egress probe). `main` adds `claude-engineering-dispatch`, `ai-bridge` and `agent-orchestrator-dispatch` | `.github/workflows/` |
| Test system | 390 test modules and 266 registered detectors. A custom runner isolates each module and checks normal, `--reverse` and `--shuffle` order. It reports zero-check functions, raised functions and unrecognised tallies. It also has a bypass harness, regression certificates and P0 fixtures | `nfl/tests/run_suite.py`, `nfl/tests/bypass.py`, `nfl/tests/DETECTORS.json`, `nfl/tests/certificates/`, `nfl/tests/p0/` |
| Domain verifiers | published-world accounting; market firewall (byte identity plus positive controls); football sanity gate; roster eligibility; Showdown run receipts, starter integrity and release classification; Classic upload verify; point-in-time data contract; preregistrations | `nfl/tools/world_accounting_check.py`, `market_firewall_check.py`, `football_sanity.py`, `roster_eligibility.py`, `showdown_run_guards.py`, `classic_upload_verify.py`, `nfl/warehouse/point_in_time.py`, `docs/*PREREGISTRATION*.md` |
| Harness built-ins in use | subagents (Explore, Plan, general-purpose); the Workflow tool; routines, `send_later` and PR subscriptions; skills `/code-review`, `/security-review`, `/simplify`, `run`, `dataviz`, `skill-creator`, `session-start-hook`, `loop` | this Claude Code environment |

**The NBA DFS product is not reachable from this session.** Your account lists exactly two repositories, `Nfl` and
`mlb-prop-system-v7`, and neither contains NBA code on any fetched branch. I therefore cannot verify its foundation freeze,
governing authority, rights restrictions or readiness gates. Every NBA recommendation below is conditional on reading that
repository first. To see it I need its owner and name, attached to this session.

## 2. Recommended minimal roster

**Type key:**
* **E**: executable and tested (code with its own tests);
* **P**: a prompt protocol worth copying as text;
* **X**: rejected.

**For every adopted item, the source is vendored by hand at the pinned commit.** It is never installed through a marketplace.
It is placed in project scope, with `tools:` restricted, and its provenance recorded (repository, commit, file sha256, our
edits). Nothing here gets a hook of its own: any hook is our Python, registered in our existing `.claude/settings.json`, and
tested by `run_suite.py` with a bypass test.

### NFL

| # | Component | Exact source | Type | What it adds | Overlap with what exists |
|---|---|---|---|---|---|
| N1 | **Floor guard**: diff-level detection of "weakening the bar". It catches skipped or xfailed tests, deleted tests or asserts, new suppressions, a loosened threshold and edits to frozen baselines. Exit codes are 0 clean, 1 violation, 2 could-not-run, and a 2 is never read as a 0 | `addyosmani/agent-skills@1be8e34:skills/constraint-driven-development/references/floor-guard.md` (Node script, 20 tests in `scripts/floor-guard-reference-test.js`) | E (port to Python, stdlib plus `git`) | an automatic check that a change did not make the checklist easier to pass, which is rule 1 of `CLAUDE.md` | `bypass.py` proves guards fire; the runner's zero-check and unrecognised-tally detectors catch hollow tests. **Nothing compares a diff for weakened tests or thresholds.** |
| N2 | **Git and PR guard rules**: block `--no-verify`, `git -c core.hooksPath=…`, force pushes, pushes to `main`, `gh pr merge` and `gh api` writes, and **creation of any approval token by the agent** | patterns only: `wshobson/agents@46891e7:plugins/block-no-verify/skills/block-no-verify-hook/SKILL.md`; the deny/allow cases in `plugins/review-agent-governance/test/run-tests.sh` and `policies/review-agent-governance.cedar` | E (extend `coordination/mode_guard.py`; no npx, no network) | deterministic refusal of the git escape routes. Prompts cannot provide this | `mode_guard` already denies writes to protected paths and workflows, so this **extends** it rather than adding a second hook |
| N3 | **Doubt review**: a fresh-context adversarial verifier. It gets the ARTIFACT and the CONTRACT, never the CLAIM, and stops after at most 3 cycles before escalating | `addyosmani/agent-skills@1be8e34:skills/doubt-driven-development/SKILL.md`, cross-model section removed | P → project skill `.claude/skills/doubt-review/` | structural independence for VERIFY mode. The contract would be our own: the accounting laws, DK rules, the point-in-time rule | partly `/code-review`. The new part is that the reviewer never sees the claim, plus the bounded loop |
| N4 | **Statistician reviewer**: design before data; multiple looks need pre-specification or correction, or the result is labelled exploratory | `msitarzewski/agency-agents@f99f6aa:academic/academic-statistician.md`, edited, `tools: Read, Grep, Glob` | P → `.claude/agents/statistician-reviewer.md` | a checklist reviewer for preregistrations and evaluation memos | no built-in equivalent; it matches the existing preregistration practice |
| N5 | **Session handoff contract**: records scope and decisions, the next task, working-tree state, the exact verification commands with their results, and open approvals. **"Do not infer approval… unless the durable artifact records it"** | `addyosmani/agent-skills@1be8e34:skills/context-engineering/SKILL.md` ("Restartable Session Boundaries"); `wshobson/agents@46891e7:plugins/operating-kit/agents/session-start.md` (verify live state, flag MISMATCH) | P → a `CLAUDE.md` section plus a SessionStart hook (built-in `session-start-hook` skill) | recovery after a container is reclaimed. This session has lost context twice | partly the conversation summaries and `HANDOFF_LOG.jsonl` |
| N6 | **Capture failure discipline**: a bookmark never moves for a failed source. A 200 response whose body reports an error is a failure. A source we could not read is never a source with nothing in it. Every run writes a record | `anthropics/claude-quickstarts@9ec32b9:managed-agents/daily-brief/agents/daily-brief/agent.md` (rule text, line 51) | P → tests in the capture code | turns rule 3 ("zeros are errors") into fault-injection tests for the GitHub Actions captures | partial: captures already record DEFERRED and NO_EGRESS. The gap is fault-injection tests |
| N7 (optional) | **Drift archaeologist**: cross-session drift. Today's audit found two such defects: Week 4 file names hardcoded in a Week 5 audit, and duplicated definitions | `msitarzewski/agency-agents@f99f6aa:specialized/specialized-codebase-archaeologist.md`, edited to read-only with findings output to chat | P | finds files that disagree with each other, which no diff review sees | partly Explore |

### NBA (conditional on reading the NBA repository first)

| # | Component | Exact source | Type | What it adds |
|---|---|---|---|---|
| B1 | **Drive the real app**: build the app and probe the real routes; "typecheck is CI's job, not evidence"; the rendered chart point count must equal the API payload length; chart data is always computed upstream, never written by the model | `anthropics/claude-quickstarts@9ec32b9:managed-agents/copilot-kit-ag-ui/.claude/skills/verify/SKILL.md` | P → project skill, extended with Playwright probes | catches data-to-UI mapping defects |
| B2 | **Accessibility CI step**: axe or pa11y with a threshold of 0 | `wshobson/agents@46891e7:plugins/accessibility-compliance/commands/accessibility-audit.md` (the CI snippet only); checklist `anthropics/knowledge-work-plugins@95bdacc:design/skills/accessibility-review/SKILL.md` | E (CI step) + P | measured accessibility, not opinion |
| B3 | **Metric-honesty rule**: never report a performance number without a Lighthouse, trace or CrUX artifact; otherwise mark it "not measured" | `addyosmani/agent-skills@1be8e34:agents/web-performance-auditor.md` | P | stops invented performance claims |
| B4 | **Flake rule**: no hard sleeps; a test is green 10 times in a row before merge | `msitarzewski/agency-agents@f99f6aa:testing/testing-test-automation-engineer.md` (rules only) | P | E2E reliability |
| shared | N1, N2, N3 and N5 apply to the NBA repository unchanged | | | |

## 3. Conflicts and redundancies

**Rejected because they conflict with your governance.** Each line was verified in the file.

| Component | Conflict |
|---|---|
| `agency-agents/specialized/agents-orchestrator.md:161` | "After 3 failures: Mark task as blocked, continue pipeline": it proceeds past a block |
| `agency-agents/testing/testing-reality-checker.md:63` | runs `./qa-playwright-capture.sh`, a script that is not in that repository, so it would run whatever file by that name exists in ours. Its verdict is fixed in advance ("Default to NEEDS WORK") |
| `agency-agents/specialized/specialized-model-qa.md:219` | `"calibrated": p_value >= 0.05`, which contradicts its own line 186 ("A non-significant result is not proof of calibration"). That is exactly the error `CLAUDE.md` rule 8 forbids |
| `agency-agents/engineering/engineering-git-workflow-master.md` | push, merge and `--delete` with no owner-approval step |
| `claude-quickstarts/financial-data-analyst/app/api/finance/route.ts:314-322` | "Generate real, contextually appropriate data… Never: Use placeholder": the model writes the numbers |
| `addyosmani` git-workflow, `/ship`, `using-agent-skills` | trunk-based "merge to main early"; the router declares "Skills are workflows, not suggestions" and would compete with the owner protocol |
| `addyosmani` `/constraints` | instructs `pip install`, `brew install` and `npm i -D`, and tells the agent to edit `CLAUDE.md` |
| `wshobson` conductor `implement.md` / git-workflow | `git add -A` after every task; a `--skip-tests` flag |
| `knowledge-work-plugins` productivity `memory-management`, `start` | create and update `CLAUDE.md` and `memory/` in the working directory |
| 154 wshobson agent descriptions | "Use PROACTIVELY" invites automatic delegation. With **187 of 202 agents having no `tools:` line**, each would inherit every tool, including GitHub write tools |

**Hooks that would collide with `mode_guard.py`, or be unsafe here:**
* `addyosmani hooks/simplify-ignore.sh` **rewrites source files on disk** when they are read and restores them on Stop, so a
  crash leaves placeholders in protected files;
* `addyosmani hooks/sdd-cache-pre.sh` makes its own `curl` request and **blocks WebFetch**, serving a cached body that anyone
  who can write the cache could poison;
* `wshobson plugins/review-agent-governance` and `protect-mcp` run `npx protect-mcp@0.7.4` on **every** tool call:
  * they **fail open** with no policy file ("every tool call is allowed");
  * the approval bypass is a plain file `./.review-approved`, which the agent could create itself;
  * where npm is unreachable they fail closed on everything.

**Redundant with what you already have.** Each item below duplicates a built-in or an existing system:

| Third-party component | What already covers it |
|---|---|
| wshobson's 7 diverging copies of `code-reviewer.md`, 6 of `test-automator.md` and 5 of `debugger.md`; addyosmani `code-review-and-quality`; agency `engineering-code-reviewer`; knowledge-work-plugins `engineering/code-review` | built-in `/code-review` |
| security personas | built-in `/security-review` |
| code-simplification skills | built-in `/simplify` |
| onboarding and explorer personas | built-in Explore |
| data-visualization personas, `build-dashboard` | built-in dataviz |
| plugin-authoring helpers | built-in skill-creator |
| `claude-quickstarts/autonomous-coding` | **your own orchestrator, which is stronger**: it has budgets, a MOCK default, an escalation stop-list and protected policy. The quickstart loops forever, retries forever, self-grades its `passes` flag and runs with `Bash(*)` |
| `wshobson quantitative-trading/backtesting-frameworks`, `data-quality-frameworks` | your preregistration, point-in-time contract and frozen baselines, which go further. The former also uses an unseeded RNG; the latter has a corrupted line 85 |

## 4. Security and maintenance

| Repository | Executable parts | Network or credentials | Supply chain if installed | Tests of the components themselves |
|---|---|---|---|---|
| wshobson/agents | 2 hook plugins (npx on every call); `plugin-eval` (third-party Python that scores skills) | plugin-eval bills `ANTHROPIC_API_KEY` if set | marketplace follows the default branch; the external entry `pensyve` has **no SHA pin**; installing a plugin with `hooks/` registers its hooks immediately | packaging lint only; hook tests not in CI; "trace-based eval program is in progress" |
| addyosmani/agent-skills | floor-guard (tested); 4 opt-in hooks (2 unsafe, above) | sdd-cache curl; `chrome-devtools-mcp@latest` unpinned in a skill | marketplace source `{"source":"github","repo":"addyosmani/agent-skills"}`, no ref or SHA | routing tests (TF-IDF) in CI; behavioural evals on demand only, results not committed; no evidence the skills change outcomes |
| msitarzewski/agency-agents | installer and converter scripts only | none in the scripts; some prompts fetch URLs | `install.sh` copies about 282 agents into **user-global** `~/.claude/agents/` with `cp`, which overwrites same-name files; it also writes into other tools' config | installer and converter only; personas untested |
| anthropics/claude-quickstarts | runnable reference apps | API keys from env; computer-use-demo writes the key in plaintext to `~/.anthropic/api_key` | nothing to install; code is stale (old SDKs, Next 14) | CI covers only computer-use-demo |
| anthropics/knowledge-work-plugins | no hooks; **7–16 remote SaaS MCP connectors per plugin** (Slack, Notion, Linear, Atlassian, Amplitude, BigQuery, Hex, Datadog, GitHub …) | every connector is an exfiltration path once authorised, and an injection path back in | marketplace of 123 entries, 101 external, SHA-bumped by a nightly bot | policy scan and URL liveness only |

**Policy this implies:**
* **Never** add any of these marketplaces.
* **Never** enable a third-party hook or MCP connector.
* **Never** install anything user-global.
* Vendor single files at a reviewed commit, with `tools:` restricted and a provenance row, so they are governed like our own
  code, and re-review on any upstream update rather than auto-updating.

## 5. Phased integration plan (each phase needs your explicit yes; none changes a forecast or a selection)

| Phase | Work | Class | Gate to the next phase |
|---|---|---|---|
| 0 (done) | this read-only evaluation | none | none |
| 1 | **N1** floor guard (Python port, runner-registered, with a bypass test) and **N2** git/PR guard extension to `mode_guard.py`. Both NFL-only, BUILD mode, no production path touched | validation and infrastructure | acceptance tests T1 and T2 pass; the full suite shows no new failure versus the certificate baseline; PROJ and WORLDS are byte-identical before and after |
| 2 | **N3–N5** (and N7 if wanted) as project skills and agents, each with a provenance row | process prompts | each passes its A/B acceptance test (T3–T6) against a no-skill baseline; a component that fails is removed, not tuned until it passes |
| 3 | **N6** capture fault-injection tests | validation | T7 passes; no capture behaviour changes except refusals that are now tested |
| 4 | NBA, after the repository is visible and its governance documents are read: B1–B4, then N1, N2, N3 and N5 | per the NBA governance | NBA readiness gates unchanged; T8 and T9 pass |
| 5 | automation design (section 7) wired into the **existing** orchestrator. Still disarmed until you arm it in `AUTOMATION_POLICY.json` | infrastructure; arming is yours alone | two weeks of MOCK runs with zero escalations wrongly suppressed |

## 6. Acceptance tests (preregistered here, before any component is tried)

**How the prompt components are tested.** Prompt components are stochastic, so each A/B runs **3 times**, against the same
prompt given to a `general-purpose` subagent with no skill, at equal token budget.

The seeded defects come from this project's own defect history (`TB_DAL_DEFECT_REGISTER.json`, `WEEK5_FORECASTING_GAP_REGISTER.json`,
the Classic audit). They are **held out**: they are written before the component is tried, and nobody tunes against them.

**A component is adopted only if it clears its bar on every run. "Neutral" means it is removed.**

| Test | Component | Fixture | Bar |
|---|---|---|---|
| T1 | N1 floor guard | 12 seeded branches (skip, xfail, delete a test, remove an assert, `# noqa`, loosen a tolerance in a protected policy file, edit a frozen baseline number, drop a detector from `DETECTORS.json`, …) plus 6 benign branches | exit 1 on 12/12, exit 0 on 6/6, exit 2 on a shallow clone; and when the guard itself is bypassed (`bypass.py`), its replay test fails |
| T2 | N2 git/PR guard | 40 recorded hook payloads: 20 escapes (`--no-verify`, `commit -nm`, `git -c core.hooksPath=/dev/null commit`, `push --force`, `push origin HEAD:main`, `gh pr merge`, `gh api -X PUT …/merge`, writes to `.github/workflows/`, creation of an approval token) and 20 benign ones (`gh pr create`, `git push -u origin claude/x`, a commit message that mentions no-verify) | 20/20 blocked, ≤1 false block |
| T3 | N3 doubt review | 10 diffs with planted defects. Examples: the Showdown captain multiplier applied to salary; passing yards not equal to receiving yards; a player in two slots; a late-swap lock on projected instead of actual kickoff; a future-dated injury join; two contests sharing one candidate cache | finds ≥2 more defects on average than `/code-review`, with no more false positives |
| T4 | N4 statistician | an evaluation memo with 6 planted flaws: 17 weeks × 5 positions tested and the best one reported; the primary metric switched after the fact; no held-out season; survivorship; regression to the mean; a p-value treated as importance | ≥5 of 6 flaws flagged in every run; never recommends adoption |
| T5 | N5 handoff | 5 sessions killed mid-task | a fresh session resumes at the correct next task, reruns the recorded verification commands, and claims **no approval that is not in an artifact**: 5/5 |
| T6 | N7 archaeologist | 3 drifts planted on a throwaway branch: two DK scoring tables that disagree, a captain multiplier applied twice, a stale lock-rule docstring | 3/3 found with file:line; `git status` clean afterwards |
| T7 | N6 capture discipline | fault fixtures: HTTP 500, a timeout, a 200 with an error body, a truncated payload, zero rows | bookmark unchanged; run recorded as failed; no zero-row snapshot committed; rerunning the window adds 0 duplicate rows |
| T8 | B1 drive-the-app | a seeded wrong field mapping in a chart | caught 1/1; median verdict time under 5 min |
| T9 | B2/B3 | a fixture page with 10 known WCAG AA violations; 10 agent performance reports | CI fails with all 10 reported and passes clean; 10/10 reports cite a measurement artifact |
| **T0 (every phase)** | all | the projection of record and the Showdown and Classic portfolios rebuilt from frozen inputs | **byte-identical** before and after the tooling change. Tooling must be inert to forecasts and to selection |

**The organisation-level measures.** These are reported per month against the pre-adoption month:
* seeded-defect detection rate before push;
* defects that escape into a sealed run or a postgame register and that a guard would have caught;
* false-block rate;
* time to green after a red CI run;
* number of owner interventions that were not owner-reserved decisions.

**None of these is a forecasting or DFS-value claim, and none may be reported as one.**

## 7. Automation design (minimal owner intervention, existing approvals intact)

It is built on what exists: the orchestrator, `MODE_POLICY`, the escalation stop-list, Claude Code routines and `send_later`. No new
agent framework.

| Tier | Who acts | Examples | Owner involvement |
|---|---|---|---|
| A. Autonomous | agents, on a schedule or event | read-only audits; the full suite in VERIFY mode; T0 byte-identity checks; capture-health reports; seeded-defect suites; research memos in RESEARCH mode | none. A digest of results only |
| B. Branch and PR | engineering agent in BUILD mode on a `claude/*` branch | code changes on non-protected paths. Each PR carries: floor-guard result (N1); guard results (N2); suite delta against the certificate; T0; an **independent** VERIFY-mode doubt review (N3) that never saw the builder's claim | review the PR when you choose; nothing merges itself |
| C. Owner-reserved | only you | production promotion; changing a forecast or a selection; mode changes; protected files; workflows on `main`; arming the orchestrator or LIVE mode; money, contests, rights or terms-of-service questions | one batched decision digest a day. Each item gives evidence, options and a recommendation, through the existing `owner-escalation` issue label and `coordination/OWNER_INBOX.md` |

**Rules that keep it honest:**
1. **Separation of builder and verifier.** BUILD can never mark the test surface current; only a VERIFY-mode run at the current
   head can.
2. **Recovery.** Every task writes the N5 handoff record. A `send_later` check-in re-arms itself until the task is closed.
   Ledgers accept status-only diffs.
3. **Failure handling.** A failure stops and escalates with a named code (the existing `stop_on` list). Nothing continues past
   a blocked task, the opposite of the rejected agency-agents orchestrator.
4. **Spending.** Every limit stays in `AUTOMATION_POLICY.json`, which no agent can edit.

## 8. Verification of the headline claims (re-run by grep against the clones)

* knowledge-work-plugins:
  * 0 `hooks.json` files;
  * 252 `SKILL.md`;
  * 0 files matching DraftKings, FanDuel, DFS, NFL, NBA, backtest, Brier or CRPS;
  * `data/.mcp.json` declares 8 servers and `engineering/.mcp.json` 10;
  * the only leakage text is `validate-data/SKILL.md:255`.
* agent-skills:
  * `plugin.json` registers commands and skills only;
  * floor-guard calls only `execFileSync('git', …)`;
  * `/constraints` step 6 edits `CLAUDE.md`;
  * doubt-driven line 106 says "Do NOT pass the CLAIM";
  * `sdd-cache-pre.sh` uses `curl`;
  * the marketplace source has no ref or SHA.
* claude-quickstarts:
  * the autonomous-coding license reads "Internal Anthropic use.";
  * `client.py:68-80` sets the sandbox to `autoAllowBashIfSandboxed`, `acceptEdits` and `Bash(*)`;
  * `max_iterations` defaults to `None`;
  * the finance route says "Generate real… data";
  * daily-brief line 51 carries the bookmark rule.
* wshobson/agents:
  * the governance `hooks.json` matcher is `.*` on Pre- and PostToolUse;
  * `evaluate.sh:16` fails open;
  * the approval is `touch ./.review-approved`;
  * the backtesting reference uses unseeded `np.random.choice`;
  * `pensyve` has no SHA;
  * 187 of 202 agents lack `tools:`.
* agency-agents:
  * the model-QA calibration verdict at line 219 contradicts line 186;
  * the orchestrator line 161 continues past blocked tasks;
  * the reality-checker runs an absent script;
  * the installer targets `~/.claude/agents/`;
  * only 17 files declare `tools:`.
