# CHATGPT_OUTBOX

**Direction: the coordinating agent writes here. Claude and the research agent
read.**

One file per directive, never appended to. Name it
`YYYY-MM-DD-NN-short-slug.md` so the order is the filename's business and not
a reader's guess.

Each directive states, at minimum:

- **what is authorized** — and, separately, what is explicitly NOT;
- **who owns it** — engineering (no network) or research (network);
- **what must be returned**, as a numbered list;
- **the acceptance principle** in one sentence.

## The rule that matters most here

A directive that authorizes work must also say what it does **not** authorize.
Every large slice in this project that went wrong went wrong by expansion, and
the cheapest place to stop that is the sentence that begins "do not start".

## What does not belong here

An owner ruling. Rulings go to `../OWNER_DECISIONS.md` first, and a directive
references them. A ruling recorded only inside a directive is a ruling nobody
can find six directives later.
