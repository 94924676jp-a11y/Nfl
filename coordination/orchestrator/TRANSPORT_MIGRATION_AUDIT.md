# Phase 1 audit — what assumes the raw Anthropic API, and what must survive

Written before the migration, from the tree at `1f52c69`, by reading the files
rather than recalling them.

## A. Every site that assumes raw Anthropic HTTP

| Location | Assumption | Disposition |
|---|---|---|
| `providers.py:60` `ENDPOINTS['messages']['anthropic']` | `https://api.anthropic.com/v1/messages` | **kept**, reachable only by the `ANTHROPIC_API` transport |
| `providers.py:68` `SECRET_ENV['anthropic']` | `ANTHROPIC_API_KEY` is *the* engineering credential | **no longer true** — the credential is now per-transport |
| `providers.py:199,213,221,233` | Anthropic request/response/`usage` shape; `x-api-key` + `anthropic-version` headers | **kept**, same scope as above |
| `MODELS.json` `engineering_model.provider: "anthropic"` | provider implies transport | **replaced** by an explicit `transport` field |
| `main.py:40` `WORKER_MODULE[ENGINEER] = anthropic_engineer` | one engineering module, which builds an API prompt and parses an API response | **generalised**: the module still owns the *contract*; the transport owns *delivery* |
| `main._call` | every worker is a synchronous HTTP call inside this process | **the real structural change** — see below |
| `AUTOMATION_POLICY.json` `max_anthropic_calls_per_task` | budget named after a provider | **kept and supplemented** by a transport-neutral reading |

### The one assumption that is not a line of code

`main._call` assumes a worker call is **synchronous and in-process**: build a
prompt, POST, parse, return. The Claude Code Action is neither. It runs as a
*separate GitHub job*, edits the working tree directly, and reports back
through `structured_output` and files on disk.

So `CLAUDE_CODE_ACTION` is not a new branch inside `call_worker`. It is a
different *shape* of execution, and the honest way to express that is a
transport that the orchestrator **delegates to** rather than **calls**. The
orchestrator's job becomes: decide the task, emit a bounded execution packet,
hand off, and later ingest a committed return. That is the same thing it
already does for the owner worker across a `repository_dispatch` boundary, so
the architecture has the shape already.

## B. Boundaries that must survive, and where each is enforced

| Boundary | Enforced at | Survives because |
|---|---|---|
| queue authorization (`authorized` + `AUTHORIZED`) | `state.Snapshot.executable` | the packet is built *from* a dispatched task, never from an input |
| one engineering `ACTIVE` task | `locks.require_exclusive_active` | unchanged; the workflow re-checks it independently |
| protected paths | `locks.enforce_protected_paths` | now applied to the **diff the Action produced**, before any commit |
| task scope | the packet's `forbidden_paths` + post-hoc diff check | instruction *and* mechanical check, as before |
| idempotency | `C.WorkerCall.idempotency_key` | the packet hash replaces the prompt hash; same derivation |
| retry rules | `locks.require_retry_budget`, `C.NEVER_AUTO_RETRY` | unchanged; OAuth failures join `NEVER_AUTO_RETRY` |
| escalation | `contracts.Escalation` | two new codes, mapped into the existing vocabulary |
| run evidence | `github_runtime.write_run` | the packet, the raw `structured_output` and the execution file are all preserved |
| `HANDOFF_LOG` | `github_runtime.append_log` | unchanged |
| return artifact contract | `claude_finalize.REQUIRED_SECTIONS` | unchanged for humans; a machine-readable sibling is **added**, not substituted |
| continuation budget | `locks.require_continuation_budget` | unchanged |
| `repository_dispatch` continuation | dispatcher on `main` | unchanged |
| owner review | `openai_owner` | unchanged, and still the only thing that can mark `COMPLETE` |
| policy kill switches | `providers.resolve_mode` + dispatcher | unchanged, and the Action workflow re-derives them itself |

## C. What this migration must not do

Delete the API transport. It stays, disabled by configuration, because it is
the only transport that has ever been exercised end to end and because the
comparison is the fastest way to diagnose a Claude Code failure. `MODELS.json`
selects between them; nothing else in the runtime chooses.

## D. The default-branch entry point

`.github/workflows/claude-engineering.yml` lived only on this branch and was
therefore **never dispatchable**: a `workflow_dispatch` workflow is only
startable when its definition exists on the repository's default branch. That
is the third time a trigger has been advertised where it could not be
received, and like the other two it was invisible from inside the checkout.

It is **removed from this branch**, not kept alongside a copy on `main`. A
file claiming a trigger it cannot receive is a lie the repository tells, and
two engineering workflows would drift.

The single workflow is `.github/workflows/claude-engineering-dispatch.yml` on
`main`. The reuse that matters is that every decision is made by Python
living **here**, on the automation branch — `validate_engineering_run.py`,
`claude_code_transport.py`, `ingest_engineering_return.py`. The default-branch
file is thin glue, and no project state is duplicated onto it.

**V2 NOT YET EARNED.**
