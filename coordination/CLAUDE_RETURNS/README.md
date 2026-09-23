# CLAUDE_RETURNS

## Direction of travel

This is the one diagram all three READMEs carry, written the same way in each,
so that no reader has to reconstruct it from two halves.

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

In words, and these five sentences are the contract:

1. The ChatGPT owner layer writes directives to `coordination/CHATGPT_OUTBOX/`.
2. Claude reads those directives.
3. Claude writes returns to `coordination/CLAUDE_RETURNS/`.
4. Perplexity writes returns to `coordination/PERPLEXITY_RETURNS/`.
5. ChatGPT reads both return directories.

**Claude writes here and reads `../CHATGPT_OUTBOX/`.** Those are its only two
directions. It may also read `../PERPLEXITY_RETURNS/` as evidence — see that
directory's README for the hard limit on what reading it permits.

**The engineering agent writes here. One file per task, named
`<task_id>.md`** — `ENG-001.md`, not a date, because the queue record points
at it by `result_path` and `validate_coordination.py` refuses a return that
sits anywhere else.

A return must contain all eight of these sections. `claude_finalize.py`
refuses a return that is missing any of them:

1. **work performed**
2. **evidence** — measured in the checkout, not quoted from an earlier document
3. **tests** — with counts, through `run_suite`
4. **failures** — including ones the work did not fix
5. **changed files**
6. **commit SHA**
7. **blockers**
8. **recommended next action**

Then update the task record: `status`, `result_path`, `commit_sha`, and one
line appended to `../HANDOFF_LOG.jsonl`.

## Finalizing, and the one thing the finalizer will not do

`python3.12 coordination/claude_finalize.py <task_id> <commit_sha>` checks
that the commit resolves in this repository, that the return file exists at
the contract path, that it is not a stub, that all eight sections are named,
and that it cites the sha. It then moves the task from `ACTIVE` to
`RETURNED`.

**It does not mark the task COMPLETE.** Only the owner layer does that. An
agent that can both do the work and declare it accepted is grading its own
exam, and this project has already paid for that once — four test modules
were filed as green because direct invocation exited 0 without running
anything.

## Two standards this project enforces

> Zeros and empties are errors, not results. Never report that a step
> succeeded unless it ran and you read the output.

> `run_suite` is the authoritative execution path. A zero exit code from
> direct module invocation is not a test result.

The second is here because an agent read silence as green and filed four
wrong classifications from it. The correction is in the log; so is the rule.

## Corrections

A return that overturns an earlier one says so in its first section, names the
earlier commit, and does not quietly edit the record. Struck-through text
beats a clean file that lost the mistake.

**V2 NOT YET EARNED.**
