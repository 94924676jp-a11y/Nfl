# Turning the autonomous runtime on

Everything in this file is a one-time step. After it, the three agents hand
work to each other through the repository and you stop copying text between
chat windows.

**Nothing is armed right now.** `AUTOMATION_POLICY.json` has
`autonomous_operation_enabled: false`, which is the default and the off
switch. Merging this work changes nothing until you do step 3.

---

## Step 1 — add the secrets

**Engineering now runs on your Claude subscription, not metered API billing.**
The engineering worker is the official `anthropics/claude-code-action@v1`,
authenticated with `CLAUDE_CODE_OAUTH_TOKEN`. `ANTHROPIC_API_KEY` is **not
required** and is deliberately never passed to that workflow — a silent
fallback to it would move spending from your subscription to metered billing
with nobody deciding to.

| Secret | Worker | Required? |
|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | engineering (Claude Code Action) | **yes** |
| `OPENAI_API_KEY` | owner / reviewer (`gpt-5.6-sol`) | **yes** |
| `PERPLEXITY_API_KEY` | research (`sonar-pro`) | optional — see below |
| `ANTHROPIC_API_KEY` | the retained raw-API transport | **not needed** |

**Generating the OAuth token.** On a trusted machine with Claude Code logged
into the subscription you intend to use:

```
claude setup-token
```

Add its value in GitHub → Settings → Secrets and variables → Actions → New
repository secret, named exactly `CLAUDE_CODE_OAUTH_TOKEN`. Do not paste it
into a chat, a file, or a prompt.

**Perplexity stays optional.** It is only used by `RES-*` tasks. Without it,
`ENG-001` and its owner review run normally; the first research task will
refuse by name rather than silently routing to another model.

<details>
<summary>Superseded: the original three-API-key setup</summary>

## Step 1 (old) — add three secrets

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

</details>

## Step 2 — confirm the models are available on *your* accounts

`coordination/orchestrator/MODELS.json` names one model per worker. The ids
and their parameter rules were **verified against provider documentation on
2026-09-23** and each entry carries its evidence inline:

| Worker | Transport | Model | Notes |
|---|---|---|---|
| engineering | `CLAUDE_CODE_ACTION` | chosen by the subscription | no model id is pinned — pinning one would be a second source of truth against what the token is entitled to |
| owner | `OPENAI_API` | `gpt-5.6-sol` | sends `max_completion_tokens` + `response_format`; **must not** send `temperature` or `max_tokens` |
| research | `PERPLEXITY_API` | `sonar-pro` | sends `max_tokens`, `temperature` |
| *(retained)* | `ANTHROPIC_API` | `claude-opus-5` | inactive; kept so a Claude Code failure can be told apart from an orchestration failure |

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

**Two fields in `coordination/AUTOMATION_POLICY.json`, on the automation
branch. Together they are the only authority to spend money.**

```json
"autonomous_operation_enabled": true,
"execution_mode": "LIVE"
```

Commit and push, then start a pass from the Actions tab.

### Why the authority lives there and not in the event

A `repository_dispatch` payload can be opened by anyone who can reach the
repository's API. If a payload could say `mode=LIVE`, that is who decides what
you spend. So the payload carries **no mode at all** — not downgraded,
ignored — and the dispatcher resolves the mode *after* checkout by reading
these two protected fields. `.github/workflows/` and
`AUTOMATION_POLICY.json` are both in `PROTECTED_PATHS`, so no autonomous
worker can edit either the decision or the file it reads.

The decision, in full:

| `autonomous_operation_enabled` | `execution_mode` | Request | Effective |
|---|---|---|---|
| true | `LIVE` | LIVE | **LIVE** |
| true | `LIVE` | continuation | **LIVE** — survives with no human action |
| true | `LIVE` | MOCK | MOCK — a request may restrict |
| true | `MOCK` | LIVE | MOCK, and a human LIVE start is **refused by name** |
| false | `LIVE` | anything | MOCK — one field is not enough |
| false | any | continuation | MOCK, and the pass stops before any worker |
| — | absent/malformed | anything | refused: an absent field is never the permissive case |

It is enforced **twice, independently**: the dispatcher on `main` derives the
mode from the policy, and the orchestrator re-derives it in-process
(`providers.resolve_mode`) before any provider call. Bypassing the workflow
does not bypass the control.

### Demonstrated, 2026-09-23

**The refusal, at repository level.** A human asked for `LIVE` against the
disarmed policy —
[run 35820292738](https://github.com/94924676jp-a11y/Nfl/actions/runs/35820292738):

```
policy: autonomous_operation_enabled=no execution_mode=MOCK
##[error]LIVE_NOT_AUTHORIZED: the protected policy says
##[error]autonomous_operation_enabled=no and execution_mode=MOCK.
```

The `Orchestrate` step was **skipped**. The run never reached the
orchestrator, let alone a provider.

**LIVE semantics across three passes**, with `providers.SPY` recording what
each pass *would* have sent, under an armed policy and with no payload
supplying anything:

```
pass 1  WOULD CALL ANTHROPIC claude-opus-5 LIVE  [max_tokens, model, system]
pass 2  WOULD CALL OPENAI    gpt-5.6-sol   LIVE  [max_completion_tokens, model, response_format]
pass 3  WOULD CALL ANTHROPIC claude-opus-5 LIVE  [max_tokens, model, system]
```

**What is *not* yet demonstrated on GitHub**, and cannot be without spending:
a LIVE continuation chain running on real runners. That needs the policy armed
and real keys present, which is step 3 of this document. The three things
separately proven — the event chain runs unattended on real runners, LIVE
persists across three passes in-process, and an unarmed policy refuses on a
real runner — are what makes arming it a reasonable next step rather than a
leap.

---

## The two-level design, and the proof it works

```
main (default branch)
└── .github/workflows/agent-orchestrator-dispatch.yml   small, stable, protected

claude/nfl-greenfield-architecture-stsxmk (automation branch)
├── coordination/            queues, returns, decisions, handoff log
├── coordination/orchestrator/   the implementation
└── the engineering work itself
```

**Why the dispatcher has to be on `main`.** GitHub starts a workflow from a
`repository_dispatch` only when the workflow definition exists on the
repository's **default** branch. The orchestrator lives on the automation
branch, so without a dispatcher on `main` the continuation event has nothing
to run — the chain would execute once and stop, silently, looking healthy.

The dispatcher receives the event, validates the branch against a hard-coded
allowlist, checks that branch out, and runs the orchestrator **from that
checkout**. It holds no state, reads no queue and decides nothing. The payload
contributes exactly one thing — which allowlisted ref to check out — and
nothing else it carries is consulted again.

**It is protected infrastructure.** `repository_dispatch` executes the
definition from the default branch, which makes that file the trust boundary
of the whole system. `.github/workflows/` is in `PROTECTED_PATHS`, so
`enforce_protected_paths` refuses any worker diff touching it: an autonomous
worker cannot edit the thing that decides what runs. Two further properties:
the branch name reaches bash through `env` rather than string interpolation,
so a payload value is data and never becomes shell syntax; and a payload may
only **restrict** the mode, never escalate it — a dispatch asking for `LIVE`
is downgraded to `MOCK`, because spending money stays a decision a human makes
by pressing a button.

### Demonstrated at repository level, 2026-09-23

Three real Actions runs. One human trigger, then nothing:

| Pass | Run ID | Event | Started by | What ran |
|---|---|---|---|---|
| 1 | [35818923998](https://github.com/94924676jp-a11y/Nfl/actions/runs/35818923998) | `workflow_dispatch` | a human | `EXECUTE PROOF-1 via ANTHROPIC` |
| 2 | [35818980390](https://github.com/94924676jp-a11y/Nfl/actions/runs/35818980390) | `repository_dispatch` | `github-actions[bot]` | `OWNER_REVIEW PROOF-1 via OPENAI` |
| 3 | [35819031142](https://github.com/94924676jp-a11y/Nfl/actions/runs/35819031142) | `repository_dispatch` | `github-actions[bot]` | `EXECUTE PROOF-2 via ANTHROPIC` |

All three succeeded. Each checked out the automation branch, committed a proof
row to it, and asked for the next pass; pass 1's log records
`continuation for pass 2: {'sent': True, 'code': 'DISPATCH_204'}`. The chain
then **stopped on its own** after pass 3 — exactly two `repository_dispatch`
runs exist, not three.

**`repository_dispatch` with the default `GITHUB_TOKEN` works.** No PAT, no
GitHub App, no organization setting change was needed on this repository. The
rows are committed under `coordination/runs/_proof/`.

## How the loop keeps itself going

**It does not use push events, and an earlier version of this document was
wrong to imply it could.** (The `push` trigger on the automation branch's own
workflow remains useful for a human push; it is not what continues the chain.) GitHub will not start a workflow from a push made
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

**Live.** Same, mode `LIVE` — and it is **refused** unless the protected
policy already authorizes it (see below). After the first pass it is
self-sustaining: each pass asks GitHub for the next with an explicit
`repository_dispatch`, and each continuation re-reads the policy, so LIVE
persists without another click. *(An earlier version of this sentence said
each commit is a push event that starts the next pass. That was wrong twice
over — `GITHUB_TOKEN` pushes do not start workflows, and the continuation
mechanism is `repository_dispatch`.)*

## How to stop autonomy immediately

**Two switches, either of which works on its own, both in the same protected
file:**

```
"autonomous_operation_enabled": false   -> the next pass stops before it
                                           reaches any worker at all
"execution_mode": "MOCK"                -> passes keep running and making
                                           queue transitions, but no paid
                                           provider call is made
```

Use the first to halt the system; the second to keep it working while it
cannot spend. Commit and push either one — every pass re-reads the file before
acting, so the next pass obeys it.

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

**It will not** spend anything unless both protected fields say so — and it
will not, ever, whatever a model or an event payload says:

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
