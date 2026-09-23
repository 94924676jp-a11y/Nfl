# Turning the autonomous runtime on

Everything in this file is a one-time step. After it, the three agents hand
work to each other through the repository and you stop copying text between
chat windows.

**Nothing is armed right now.** `AUTOMATION_POLICY.json` has
`autonomous_operation_enabled: false`, which is the default and the off
switch. Merging this work changes nothing until you do step 3.

---

## Step 1 — add three secrets

GitHub repository → **Settings** → **Secrets and variables** → **Actions** →
*New repository secret*. Add these three names:

| Secret name | Which worker it pays for |
|---|---|
| `OPENAI_API_KEY` | the owner / review worker |
| `ANTHROPIC_API_KEY` | the engineering worker |
| `PERPLEXITY_API_KEY` | the research worker |

**Do not paste a key into a chat window, a source file, or this document.**
Nothing in the runtime reads a key from anywhere but the environment, and a
missing key stops the loop with `SECRET_MISSING` rather than falling back to
anything. That last part is deliberate: a mock standing in for a call you
believed you were making would produce a fabricated result that looks exactly
like a real one.

You can add only some of them. A worker whose key is absent stops the loop the
first time it is needed, and the other two keep working until then.

## Step 2 — confirm the three models are available on *your* accounts

`coordination/orchestrator/MODELS.json` names one model per worker. The ids
and their parameter rules were **verified against provider documentation on
2026-09-23** and each entry carries its evidence inline:

| Worker | Model | Endpoint | Sends | Must NOT send |
|---|---|---|---|---|
| owner | `gpt-5.6-sol` | `/v1/chat/completions` | `max_completion_tokens`, `response_format` | `temperature`, `max_tokens` |
| engineering | `claude-opus-5` | `/v1/messages` | `max_tokens`, `system` | `temperature`, `top_p`, `top_k` |
| research | `sonar-pro` | `/v1/chat/completions` | `max_tokens`, `temperature` | — |

**The "must not send" column is not style, it is the difference between
working and a guaranteed 400.** Both current flagship reasoning models reject
sampling parameters rather than ignoring them — `claude-opus-5` removed
`temperature`/`top_p`/`top_k`, and `gpt-5.6-sol` answers `Unsupported value:
'temperature' does not support 0 with this model. Only the default (1) value
is supported.` An earlier version of this runtime hard-coded `temperature: 0`
for all three providers, which would have failed on the very first live call
while the entire mocked suite stayed green. `test_orchestrator::test_p` now
asserts each body.

What is **not** verifiable from this checkout is whether *your* accounts and
tiers can reach these models. That is the one-time check: open each provider's
model list and confirm. A wrong id fails loudly — a named `API_HTTP_404` with
the provider's own message preserved under `coordination/runs/` — and never
silently falls back.

## Step 3 — arm it

Edit `coordination/AUTOMATION_POLICY.json`:

```json
"autonomous_operation_enabled": true
```

Commit and push. That push is itself an event the orchestrator listens for, so
the first pass starts from it.

---

## How the loop keeps itself going

**It does not use push events, and an earlier version of this document was
wrong to imply it could.** GitHub will not start a workflow from a push made
with `GITHUB_TOKEN` — that is documented behaviour, designed to stop workflows
recursing. The chain would have run exactly once and stopped, silently,
looking healthy.

Continuation is an explicit **`repository_dispatch`** instead, which is one of
the two documented exceptions that *do* create a run from `GITHUB_TOKEN`:

```
pass N  →  one governed transition  →  commit + push
        →  re-read state: is another transition eligible?
        →  if yes: POST /repos/{owner}/{repo}/dispatches
                   event_type: agent-orchestrator-continue
        →  exit
                    ↓
pass N+1 starts from a fresh checkout and re-reads everything
```

This is better than the accident it replaces. Continuation is now a decision
with a budget, a log row and a stated reason — not a side effect of having
written a file.

**The payload carries branch, run id, observed head, chain depth and a reason
string. Nothing else.** No task record, no queue fragment, no decision. The
next pass re-reads all state from the repository and trusts nothing that
arrived with the event; `test_orchestrator::test_m` asserts every payload
value is a flat scalar.

A pass does **not** ask for a successor when it committed nothing, when its
worker failed, when no further transition is eligible, when the continuation
budget is spent, or when autonomy was switched off while it was running.

The `push` trigger is kept for the one thing it can still do: wake the
orchestrator when **a human** pushes coordination state. A human push is not a
`GITHUB_TOKEN` push, so it does start a run.

### If the dispatch is refused with 403

The workflow grants `contents: write` **and** `actions: write`; both are
needed for `GITHUB_TOKEN` to create a repository dispatch. If your
organization forces read-only workflow permissions, that grant is overridden
and the POST returns 403 — `request_continuation` says exactly this in its own
error. In that case, in order of preference:

1. Settings → Actions → General → Workflow permissions → **Read and write**.
2. A **GitHub App installation token** with `contents: write` + `actions:
   write`, exposed to the workflow as `GH_TOKEN`. The runtime already reads
   `GH_TOKEN` as a fallback, so this is a secret plus one `env:` line.
3. A user PAT — **last resort**, because it binds the automation to one
   person's identity and carries their whole account's scope.

Nothing here requires a PAT.

## How to start autonomy

Three ways, in increasing order of commitment:

**Dry run, free.** Actions → *agent-orchestrator* → *Run workflow* →
mode `MOCK`, plan_only `true`. This decides what it would do and prints it. It
spends nothing and writes nothing.

**Mock end to end, free.** Same, plan_only `false`, mode `MOCK`. The whole
state machine runs against fixtures: queue transitions, commits, returns and
handoff log entries are all real, and no provider is called. This is worth
doing once on the real queue before spending anything.

**Live.** Same, mode `LIVE`. Real API calls. After the first pass it is
self-sustaining: each commit the orchestrator makes is a push event on a
watched path, which starts the next pass.

## How to stop autonomy immediately

**The one that always works:**

```
edit coordination/AUTOMATION_POLICY.json -> "autonomous_operation_enabled": false
git commit && git push
```

Every pass re-reads that file before doing anything, so the next pass stops. A
pass already running finishes its current transition and stops — it will not
be left half-written.

**Faster, if a run is in flight right now:** Actions → the running
*agent-orchestrator* → *Cancel workflow*. Then still set the flag, or the next
push will start another.

**The heaviest hammer:** Actions → *agent-orchestrator* → **Disable workflow**.
Nothing can trigger it at all until you re-enable it.

You do not need to revoke the API keys to stop the loop, and revoking them is
not the fastest route — a pass with no key stops on `SECRET_MISSING` anyway,
but it stops *after* deciding to call, having already spent the pass.

---

## What it will and will not do without asking you

**It will**, on its own: route an authorized engineering task to the
engineering worker, route an authorized research task to the research worker,
have the owner worker review what comes back, accept or return or block it,
authorize the next task *that you already drafted*, commit every step, and
carry on.

**It will not**, ever, whatever a model says:

- promote Q9, or change its promotion state
- authorize NFL-1
- declare V2 earned
- remove or weaken an owner decision, or edit `OWNER_DECISIONS.md` at all
- make sportsbook information a predictive input
- treat `UNKNOWN` evidence as passing
- set the weekly exposure cap, or enable real money
- execute a task **it** invented — a task created by the owner worker arrives
  `DRAFT` and unauthorized, and waits for you

That last one is the hinge. A worker that could create a task and authorize it
in the same step would be authorizing itself, and every other limit would
become advisory.

## What will stop it and ask you

Each of these halts the loop and writes a file under
`coordination/ESCALATIONS/`, and the workflow opens an issue labelled
`owner-escalation`:

`OWNER_DECISION_REQUIRED` · `RIGHTS_DECISION_REQUIRED` · `PURCHASE_REQUIRED` ·
`SECRET_MISSING` · `GOVERNANCE_CONFLICT` · `UNKNOWN_BLOCKING_EVIDENCE` ·
`COST_LIMIT_REACHED` · `REPEATED_AGENT_FAILURE` ·
`DESTRUCTIVE_ACTION_REQUIRED` · `STATE_CONTRADICTORY`

**None of them is retried automatically.** Six of them are never retried even
manually until you change something in the repository. The point is that the
system stops spending tokens trying to reason its way past a decision that is
yours.

Two more stops are benign and are not escalations: `NOTHING_AUTHORIZED` means
the loop reached the end of the work you authorized, and
`TRANSITION_BUDGET_SPENT` means a pass hit its per-invocation cap and left the
rest for the next event.

## What it costs, and how to change that

`coordination/AUTOMATION_POLICY.json`, deliberately conservative:

| Limit | Default | What it bounds |
|---|---|---|
| `max_transitions_per_invocation` | 3 | steps in one pass |
| `max_continuations_per_hour` | 8 | links in the dispatch chain, counted from the committed log — never from the payload, because the payload's sender is the thing being bounded |
| `max_runs_per_hour` | 6 | passes per hour, counted from the committed log |
| `max_openai_calls_per_task` | 2 | review rounds per task |
| `max_anthropic_calls_per_task` | 2 | implementation attempts |
| `max_perplexity_calls_per_task` | 2 | research attempts |
| `max_retries_per_task` | 1 | one more go after a failure |
| `max_task_runtime_seconds` | 1800 | a single task's tests |
| `max_total_tokens_per_invocation` | 400000 | tokens in one pass |

Raise them once you have watched it run. A limit that was never reached costs
nothing; a limit discovered by a bill is the expensive way to learn where it
should have been.

Every call is logged whether it succeeded or not. `coordination/runs/<run_id>/`
holds the request, the raw response, and metadata carrying provider, model,
timestamp, task, request and response hashes, token usage, and the repository
HEAD before and after.

## Where the branch rules are

`branch_policy` in the same file. It currently points at
`claude/nfl-greenfield-architecture-stsxmk`, refuses to push to `main`,
`master` or `capture-prod`, and does not yet require a branch per task.
`require_task_branch: true` tightens that when you want it; `dispatch.py`
already emits the branch name it would use.

---

## If something looks wrong

Read in this order. The first three cost nothing.

1. `python3.12 coordination/validate_coordination.py` — is the state even
   consistent?
2. `python3.12 coordination/orchestrator/main.py --plan` — what does it think
   it should do next, and why?
3. `coordination/HANDOFF_LOG.jsonl` — every transition, in order.
4. `coordination/runs/<run_id>/metadata.json` — what a specific call actually
   did, including what the provider said when it failed.

**The raw responses under `coordination/runs/` are evidence, not state.** The
queues and `PROJECT_STATE.json` are canonical. If they ever disagree, the
queues are right and a run record is just what some model said at the time.

---

**V2 NOT YET EARNED.**
