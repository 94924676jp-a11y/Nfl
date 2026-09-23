# PERPLEXITY_RETURNS

**Direction: the research agent writes here. Everyone reads.**

One file per return, named `YYYY-MM-DD-NN-short-slug.md`.

## Raw bytes come with the return, not instead of it

A research return that cannot be traced to bytes is a summary. Where the task
was to acquire something, the acquired artifact lands in the repository with
its sha256, its source URL and its retrieval time, and the return says where.

## Confidence is declared, per claim

Using the vocabulary already in `nfl/dfs/history/contracts.py`:

`VERIFIED_PRIMARY` · `VERIFIED_INDEPENDENTLY` · `PROVIDER_CLAIM` ·
`PRACTITIONER_REPORT` · `COMMUNITY_REPORT` · `UNKNOWN`

**`UNKNOWN` is a real answer and stays one.** A provider's statement about its
own product is `PROVIDER_CLAIM`, which is one rung above recollection and is
not verification. This distinction has already changed a decision once: four
DraftKings claims moved from `PRACTITIONER_REPORT` to `PROVIDER_CLAIM` when
the operator's own support articles arrived, and none moved to
`VERIFIED_PRIMARY`, because nobody here has yet read a real export.

## Do not over-label

A number carried through three documents without a computation behind it is
not a verified fact. One such number reached this project as a "VERIFIED FACT
(project computation)" and had no locatable computation at all; it is now
recorded UNVERIFIED in `nfl/production/dependence.py`. Say what was read, and
where.

## Timestamps are distinct facts

`retrieved_at_utc`, `first_observed_at_utc`, `stated_as_of`,
`source_published_at`, `model_initialized_at`, `forecast_valid_at`. Never
substitute one for another, and never fill a missing publication time from a
game date, a document's "as of" line, or the moment you fetched it. NULL is
correct.
