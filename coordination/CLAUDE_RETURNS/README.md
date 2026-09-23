# CLAUDE_RETURNS

**Direction: the engineering agent writes here. Everyone reads.**

One file per return, named `YYYY-MM-DD-NN-short-slug.md`, matching the
directive it answers.

A return is not a summary of effort. It answers the directive's numbered list,
in order, and it carries:

- **commit SHAs** — a claim with no sha is a claim;
- **measured numbers**, re-derived in the checkout, not quoted from an earlier
  document;
- **what was NOT done**, named, with the reason;
- **anything the return contradicts**, including the agent's own earlier
  returns.

## The standard this project actually enforces

> Zeros and empties are errors, not results. Never report that a step
> succeeded unless it ran and you read the output.

And, since 2026-09-23:

> `run_suite` is the authoritative execution path. A zero exit code from
> direct module invocation is not a test result.

That second one is here because an agent read silence as green and filed four
wrong classifications from it. The correction is in the log; so is this rule.

## Corrections

A return that corrects an earlier return says so in its first section, names
the earlier commit, and does not quietly edit the record. Struck-through text
beats a clean file that lost the mistake.
