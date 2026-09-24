# Ticket: the vintage manifest will stop the repository pushing, around 9 Oct

**Raised:** 2026-09-24. **Class:** operational, dated, not a modelling
question. **Decision needed from the owner** before anything is changed,
because the file is the provenance record.

## The number

`nfl/vintage_manifest.jsonl` is **53,549,801 bytes over 6,757 rows**, a mean
of 7,925 bytes per manifest line. GitHub warns above 50 MB and **refuses a
push above 100 MB**. We are past the warning.

Growth, from capture days that ran a full cadence:

| day | rows | bytes |
|---|---|---|
| 2026-09-15 | 450 | 1,897,234 |
| 2026-09-16 | 480 | 3,041,062 |
| 2026-09-17 | 516 | 6,520,205 |
| 2026-09-18 | 480 | 5,859,276 |
| 2026-09-19 | 480 | 5,136,942 |

Mean over the last seven capture days is 3.03 MB/day, but that average is
dragged down by 09-20, 09-21 and 09-24, which ran 123, 10 and 6 rows. On the
five full days above the rate is about 4.5 MB/day.

**So the hard limit arrives between roughly 2026-10-04 and 2026-10-09**, on
the assumption that the normal capture cadence resumes. If it does not resume,
the date slips; it does not go away. When the file crosses 100 MB every push
from every agent fails and the project stops being able to record anything.

## Where the bytes are

Two derived fields are two thirds of the entire file:

| field | bytes | share |
|---|---|---|
| `value.execution_target` | 18,308,154 | **34.2%** |
| `value.discharge_eligibility` | 17,951,290 | **33.5%** |
| `value.header` | 4,303,252 | 8.0% |
| everything else | ~13,000,000 | 24.3% |

Both are per-capture evaluations against **every game in the window**. That is
an O(captures x games) product embedded in an append-only log, so the file
does not grow with captures, it grows with captures times schedule size. The
share is even across sources -- no single feed is the culprit, the shape is.

## Options, with the recommendation first

**(1) Shard the log by month.** `vintage_manifest.2026-09.jsonl` and so on,
with the reader concatenating. **Nothing is discarded**, the audit record
stays complete and byte-identical, and the change is reversible by `cat`. It
does not reduce total bytes, it stops any single file reaching the limit.
This is the standard fix for an append-only log and is the recommendation.

**(2) Stop embedding the two derived fields and store a reference instead.**
Saves 67.7% immediately. But they are derived at capture time from the capture
and the then-current schedule, and recomputing them later is not guaranteed to
reproduce what was actually evaluated *then*. That is precisely the property a
provenance record exists to hold, so this trades the thing the file is for.
Not recommended without an owner ruling.

**(3) Compress to `.jsonl.gz`.** Would work on size and destroy appendability
and diff review. Not recommended.

## What I have not done

I have not changed the file, the writer, or the reader. Sharding a provenance
log is a change to how the project's audit record is stored, and while option
(1) discards nothing it still alters the shape of the record every other agent
reads. That is an owner decision and it is being raised, not taken.

## Why this is on a clock

Unlike most tickets here, this one has a date and the date is soon. If nothing
is decided by early October the failure mode is not a degraded number, it is
that nobody can push. It should be settled while it is a five-minute
mechanical change rather than after it blocks the repository.
