# coordination

The hub. Three agents and an owner work on this repository and none of them
shares a memory, so the state of the project lives here rather than in a
conversation.

```
coordination/
├── PROJECT_STATE.json      measured state at a named commit
├── OWNER_DECISIONS.md      what the owner ruled, and where it is enforced
├── ENGINEERING_QUEUE.json  claude's queue (no network)
├── RESEARCH_QUEUE.json     the research agent's queue (network)
├── CHATGPT_OUTBOX/         directives out
├── CLAUDE_RETURNS/         engineering returns in
├── PERPLEXITY_RETURNS/     research returns in
└── HANDOFF_LOG.jsonl       append-only, one line per handoff
```

## Four rules, and each one is here because of a specific failure

**1. Measured, not recalled.** Every number in `PROJECT_STATE.json` is
re-derived from the tree at `head_commit`. A state file that drifts is worse
than none, because it reads like evidence. Three times in two days a
classification in this project was wrong because an agent trusted a prior
document instead of the artifact.

**2. Blocked means blocked for everyone.** The engineering agent has no
network. Marking a task blocked on something outside the checkout without
writing the request into `RESEARCH_QUEUE.json` is the error that has already
cost this project real work twice. If it is only blocked for one agent, it is
not blocked — it is assigned.

**3. A state outside the vocabulary is a defect.** `QUEUED`, `ACTIVE`,
`BLOCKED`, `DONE`, `SUPERSEDED`. `nfl/WORK_QUEUE.md` currently carries three
rows reading `DONE (2026-09-20)`, and `agent_state` raises on all three. Do
not repeat that here.

**4. Corrections are appended, never applied silently.** A wrong line in
`HANDOFF_LOG.jsonl` is followed by a `CORRECTION` line naming it. A return
that overturns an earlier return says so in its first section. The struck-
through record is the useful one.

## What this directory is not

It is not a second source of truth about the code. Where this directory and
the repository disagree, **the repository wins** and this directory is the
thing that needs fixing. Governance state lives in
`nfl/production/authorization.py`; integrity registries live in
`nfl/production/review/gate.py`; the red-surface classification lives in
`nfl/research/integrity/RED_TEST_DAG.md`. This directory points at them and
records decisions about them.

**V2 NOT YET EARNED.**
