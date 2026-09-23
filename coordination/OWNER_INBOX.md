# OWNER_INBOX — the paste-once fallback

**This is a fallback, not the steady state.** The intended flow is
repository-native: the owner (or ChatGPT on the owner's behalf) writes a file
into `CHATGPT_OUTBOX/` and Claude reads it. This file exists for the case
where the writing side has read access but not write access, and a directive
has to be pasted in once by hand.

## Contract

1. **Append. Never edit above.** A directive already in this file is a
   historical record. Claude will not silently rewrite one, and
   `validate_coordination.py` treats a vanished directive ID the way it
   treats a vanished owner decision.
2. **Every directive gets an ID** on its heading line: `## OD-NNN · short
   title`. IDs are monotonic and never reused.
3. **Claude ingests, it does not authorize.** On reading a new directive,
   Claude converts it into the correct artifact — a queue task, an
   `OWNER_DECISIONS.md` entry, or a file in `CHATGPT_OUTBOX/` — records the
   directive ID in `HANDOFF_LOG.jsonl`, and marks the heading `[INGESTED
   <commit>]`. **Creating a queue row is not authorizing it**: a new task
   arrives `authorized=false`, and only an explicit owner authorization in
   the directive text sets it true.
4. **An owner decision is only created or changed by a directive that says
   so.** Claude does not infer a ruling from a task description.

## Template

```
## OD-007 · short title

AUTHORIZE: ENG-004            (optional; omit and the task stays unauthorized)
DECISION: D-12 <one-line ruling>   (optional; creates an OWNER_DECISIONS entry)
QUEUE: ENG-013 <title>        (optional; creates a DRAFT task)

<body — objective, acceptance tests, what is explicitly NOT authorized>
```

The line that matters most is the one naming what is **not** authorized.
Every large slice in this project that went wrong went wrong by expansion.

## Ingested directives

*(none yet — the repository-native path has been available for every
directive so far)*
