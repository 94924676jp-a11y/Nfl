# coordination

The hub. Three agents and an owner work on this repository and none of them
shares a memory, so the state of the project lives here rather than in a
conversation.

```
coordination/
├── PROJECT_STATE.json         measured state at a named commit
├── OWNER_DECISIONS.md         what the owner ruled, and where it is enforced
├── OWNER_INBOX.md             paste-once fallback for a directive
├── GITHUB_FALLBACK.md         the bus when the checkout is not shared
├── ENGINEERING_QUEUE.json     claude's queue (no network)
├── RESEARCH_QUEUE.json        the research agent's queue (network)
├── CHATGPT_OUTBOX/            directives out
├── CLAUDE_RETURNS/            engineering returns in
├── PERPLEXITY_RETURNS/        research returns in
├── HANDOFF_LOG.jsonl          append-only, one line per handoff
├── refresh_state.py           re-measure PROJECT_STATE.json from the tree
├── claude_dispatch.py         hand out exactly one authorized task
├── claude_finalize.py         ACTIVE -> RETURNED, with evidence
└── validate_coordination.py   refuse a malformed or dishonest queue
```

## Direction of travel

```
  ChatGPT (owner layer)  --writes directives-->  coordination/CHATGPT_OUTBOX/
                                                          |
                                                          | Claude reads
                                                          v
                                                    Claude (engineering,
                                                     no network)
                                                          |
                                                          | writes returns
                                                          v
                                                 coordination/CLAUDE_RETURNS/
                                                          |
  Perplexity (research, network) --writes returns--> coordination/PERPLEXITY_RETURNS/
                                                          |
  ChatGPT reads BOTH return directories  <----------------+
```

The same five sentences appear in each of the three subdirectory READMEs.

## Persistent startup rule

**On every Claude Code session, in this order. This is standing, not
per-task, and it does not need to be restated in a directive.**

```
1.  git pull the designated branch
2.  python3.12 coordination/validate_coordination.py
3.  read coordination/PROJECT_STATE.json
4.  read coordination/OWNER_DECISIONS.md
5.  read coordination/ENGINEERING_QUEUE.json
6.  python3.12 coordination/claude_dispatch.py
7.  execute ONLY the task the dispatcher returned
8.  write coordination/CLAUDE_RETURNS/<task_id>.md
9.  python3.12 coordination/claude_finalize.py <task_id> <commit_sha>
10. commit and push
```

Step by step, with the part of each that is not obvious:

1. **Pull.** `git pull origin claude/nfl-greenfield-architecture-stsxmk`.
   Working from a stale checkout is how two agents produce two truths.
2. **Validate.** If validation fails, **stop and report**. Do not start work
   against a queue that cannot be parsed or that contains a contradiction. The
   validator has already refused its own first draft over two real defects.
3. **PROJECT_STATE.json.** If `refresh_state.py --check` reports drift, the
   state file is stale; refresh it before quoting any number out of it.
4. **OWNER_DECISIONS.md.** Read all of it, not the last entry. A decision does
   not expire.
5. **ENGINEERING_QUEUE.json.** Read it even though the dispatcher will also
   read it, so that the dispatcher's answer can be recognised as wrong.
6. **Dispatch.** The dispatcher hands out exactly one task and marks it
   `ACTIVE`. Exit 3 means nothing is authorized; exit 4 means the task record
   has no directive. Both are correct outcomes, not errors to work around.
7. **Execute only that task.** **No freeform next-task selection.** If the
   authorized task turns out to be blocked, the answer is a return that says
   so — not a different task picked up because it looked adjacent. This is the
   single rule most of this directory exists to enforce.
8. **Write the return** at the contract path with all eight sections.
9. **Finalize.** `ACTIVE` becomes `RETURNED`. Not `COMPLETE` — only the owner
   layer closes a task.
10. **Commit and push** to the designated branch.

Where a session cannot reach the repository at all, the owner pastes into
`OWNER_INBOX.md` (see that file) or opens a message on the GitHub bus (see
`GITHUB_FALLBACK.md`). Neither fallback authorizes anything by itself; both
land as an owner directive that the owner layer then writes into a queue.

## Four rules, and each one is here because of a specific failure

**1. Measured, not recalled.** Every number in `PROJECT_STATE.json` is
re-derived from the tree at `head_commit`. A state file that drifts is worse
than none, because it reads like evidence. Three times in two days a
classification in this project was wrong because an agent trusted a prior
document instead of the artifact. `refresh_state.py` exists so that refreshing
is cheaper than guessing, and it merges **only** measured fields — it will not
overwrite an owner's declaration with a measurement.

**2. Blocked means blocked for everyone.** The engineering agent has no
network. Marking a task blocked on something outside the checkout without
writing the request into `RESEARCH_QUEUE.json` is the error that has already
cost this project real work twice. If it is only blocked for one agent, it is
not blocked — it is assigned.

**3. A state outside the vocabulary is a defect.** Queue statuses are `DRAFT`,
`AUTHORIZED`, `ACTIVE`, `BLOCKED`, `RETURNED`, `COMPLETE`, `SUPERSEDED`.
`nfl/WORK_QUEUE.md` currently carries three rows reading `DONE (2026-09-20)`,
and `agent_state` raises on all three. Do not repeat that here.

**4. Corrections are appended, never applied silently.** A wrong line in
`HANDOFF_LOG.jsonl` is followed by a `CORRECTION` line naming it. A return
that overturns an earlier return says so in its first section. The struck-
through record is the useful one.

## Who may change what

| Thing | Who may change it |
|---|---|
| `OWNER_DECISIONS.md` | owner / ChatGPT layer only |
| `authorized`, `status: AUTHORIZED` | owner / ChatGPT layer only |
| `status: COMPLETE` | owner / ChatGPT layer only |
| `status: ACTIVE` | `claude_dispatch.py` |
| `status: RETURNED`, `result_path`, `commit_sha` | `claude_finalize.py` |
| measured fields in `PROJECT_STATE.json` | `refresh_state.py` |
| accepted baseline, Q9 promotion, sealing, model registry | owner only |

Research returns are evidence, never authorization. Claude may read
`PERPLEXITY_RETURNS/` and must not start engineering work on its strength.

## What this directory is not

It is not a second source of truth about the code. Where this directory and
the repository disagree, **the repository wins** and this directory is the
thing that needs fixing. Governance state lives in
`nfl/production/authorization.py`; integrity registries live in
`nfl/production/review/gate.py`; the red-surface classification lives in
`nfl/research/integrity/RED_TEST_DAG.md`. This directory points at them and
records decisions about them.

**V2 NOT YET EARNED.**
