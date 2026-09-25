"""One reader for the manifest, so 21 consumers never learn what a shard is.

APPROVAL-002, granted 2026-09-25 with eight constraints. The live lineage is
69.69 MB over 8,951 records on `capture-prod` and grows every thirty minutes;
GitHub rejects a push at 100 MB.

THE CONSTRAINT THAT SHAPES EVERYTHING HERE

Of the 54 modules that read this file, **21 both scan the whole thing and depend
on ordering or on a last-match-wins rule**. Split the file naively and those
answers change with no error raised, which is this repository's most expensive
failure class arriving through the back door of a storage change. So the loader
comes first and the storage changes last:

    records()  ->  the same sequence, in the same order, whether it is reading
                   one monolith or twelve shards.

A consumer migrated behind `records()` cannot tell the difference, which is the
point. Teaching each consumer its own traversal is how twenty-one different
ideas of "newest" get invented.

BYTES, NOT OBJECTS

Shards are written by copying the ORIGINAL LINE, never by re-serialising a
parsed record. `json.dumps` of a round-tripped dict is not the same bytes: key
order, separators and unicode escaping all move, and any digest taken over a
manifest line would break. `raw` carries the exact line and `record()` parses it
on demand, so provenance fields are preserved rather than recomputed -- which
constraint 2 requires in as many words.

WHAT THIS MODULE WILL NOT DO

It will not delete a record, rewrite history to reduce size, or reorder
anything. `build_shards` writes a new tree and leaves the source untouched, so
the migration is reversible until `equivalence` passes -- constraints 6 and 7.

LIMITS
  A source-text and record-level heuristic where it inspects records; the
  equivalence proof itself is exact and byte-level. It does not know whether a
  consumer's ordering assumption is correct, only whether sharding changed it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SPEC_VERSION = 'manifest-store/1.0.0'

#: The default monolith, relative to the repository root.
MONOLITH = Path('nfl/vintage_manifest.jsonl')

#: Where shards live. A sibling directory, so the monolith stays put.
SHARD_DIR = Path('nfl/vintage_manifest')

#: The index a shard tree carries so a reader can restore order without
#: guessing from filenames.
INDEX_NAME = 'SHARD_INDEX.json'


class ManifestError(RuntimeError):
    """The store would have changed what a consumer reads."""


def _lines(path: Path):
    """Every non-blank line, verbatim, in file order."""
    with Path(path).open('r', encoding='utf-8') as fh:
        for line in fh:
            if line.strip():
                yield line.rstrip('\n')


#: DAILY, AND THE MEASUREMENT THAT CHOSE IT.
#:
#: The approval named monthly shards "acceptable if your evidence shows they
#: retain the required ordering semantics". They do retain ordering -- proven
#: byte-exact over all 8,951 live records -- and they do not solve the problem,
#: because every record in the live lineage is 2026-09, so monthly yields ONE
#: shard of 69.69 MB. Measured over the same records:
#:
#:     key      shards   largest   headroom to 100 MB
#:     month         1   69.69 MB                0.4x
#:     week          4   26.48 MB                2.8x
#:     day          19    7.94 MB               11.6x
#:
#: Daily is chosen for a property the table only hints at: a day's shard is
#: BOUNDED BY ONE DAY'S CAPTURE TRAFFIC AND THEN CLOSES FOREVER. A month's
#: shard grows all month, so the largest file is always the current one and the
#: limit is approached again every cycle. With daily keys the only growing file
#: is today's, and it is a few megabytes.
SHARD_KEY_MODE = 'day'


def shard_key(raw: str, mode: str = None) -> str:
    """The shard a record belongs to, derived from `capture_id`.

    Derived from the capture id rather than from any field a later process
    might recompute -- constraint 2 forbids recomputing historical provenance.
    A record whose id is missing or unparseable goes to UNDATED rather than
    being dropped or guessed into a neighbouring period.
    """
    mode = mode or SHARD_KEY_MODE
    try:
        cid = json.loads(raw).get('capture_id') or ''
    except ValueError:
        return 'UNDATED'
    if len(cid) >= 8 and cid[:8].isdigit():
        if mode == 'month':
            return f'{cid[:4]}-{cid[4:6]}'
        if mode == 'day':
            return f'{cid[:4]}-{cid[4:6]}-{cid[6:8]}'
    return 'UNDATED'


def records(source=None, *, parse: bool = True):
    """The manifest as one ordered sequence, monolith or shards alike.

    THIS IS THE WHOLE CONTRACT. Order is append order, which for the monolith is
    file order and for a shard tree is the index's order followed by file order
    within each shard. A consumer that reads this sees one thing.
    """
    src = Path(source) if source else MONOLITH
    if src.is_dir():
        idx = json.loads((src / INDEX_NAME).read_text())
        # A K-WAY MERGE ON THE RECORDED ORDER, NOT SHARD-THEN-CONCATENATE.
        #
        # Concatenating shards reproduces append order ONLY when the source is
        # already sorted by shard key. The live manifest happens to be
        # chronological, so the first version of this passed against it and was
        # wrong: on a log where 09-08 appears between two 09-07 records,
        # reading shard by shard silently reorders them. Twenty-one consumers
        # depend on order, which is the whole reason this loader exists, so the
        # index carries the shard each record came from, in source position,
        # and the reader walks that.
        cursors = {sh['key']: _lines(src / sh['file'])
                   for sh in idx['shards']}
        for key in idx['order']:
            raw = next(cursors[key])
            yield json.loads(raw) if parse else raw
        return
    for raw in _lines(src):
        yield json.loads(raw) if parse else raw


def digest(source=None) -> str:
    """A digest over the ordered raw lines. Equal iff a consumer sees the same."""
    h = hashlib.sha256()
    h.update(SPEC_VERSION.encode())
    for raw in records(source, parse=False):
        h.update(b'\x00')
        h.update(raw.encode('utf-8'))
    return h.hexdigest()


def build_shards(source=None, dest=None, mode: str = None) -> dict:
    """Write a shard tree from the monolith. The source is never touched.

    Records are appended to their shard IN SOURCE ORDER and the index records
    the order shards must be read back in, so a month that first appears late in
    the file does not jump to the front on the way out.
    """
    src = Path(source) if source else MONOLITH
    dst = Path(dest) if dest else SHARD_DIR
    if dst.exists() and any(dst.iterdir()):
        raise ManifestError(
            f'{dst} is not empty. Building over an existing shard tree could '
            f'interleave two migrations; remove it deliberately or choose '
            f'another destination.')
    dst.mkdir(parents=True, exist_ok=True)
    shard_order, handles, counts, positions = [], {}, {}, []
    try:
        for raw in _lines(src):
            key = shard_key(raw, mode)
            positions.append(key)
            if key not in handles:
                shard_order.append(key)
                handles[key] = (dst / f'{key}.jsonl').open('w',
                                                           encoding='utf-8')
                counts[key] = 0
            handles[key].write(raw + '\n')
            counts[key] += 1
    finally:
        for fh in handles.values():
            fh.close()
    index = {
        'spec_version': SPEC_VERSION,
        'shard_key_mode': mode or SHARD_KEY_MODE,
        'source_digest': digest(src),
        'n_records': sum(counts.values()),
        'shards': [{'key': k, 'file': f'{k}.jsonl', 'n_records': counts[k]}
                   for k in shard_order],
        # One shard key per record, in SOURCE POSITION. This is what makes the
        # read a merge rather than a concatenation. At 8,951 records it is a
        # few hundred kilobytes against a 69 MB payload.
        'order': positions,
    }
    (dst / INDEX_NAME).write_text(json.dumps(index, indent=1) + '\n')
    return index


def equivalence(source=None, shards=None) -> dict:
    """Prove a consumer reading the shards sees exactly what it saw before.

    Three separate claims, because each can fail without the others:
      * the same number of records
      * the same lines, in the same order, byte for byte
      * the same digest
    """
    src = Path(source) if source else MONOLITH
    dst = Path(shards) if shards else SHARD_DIR
    a = list(records(src, parse=False))
    b = list(records(dst, parse=False))
    first_diff = None
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            first_diff = i
            break
    if first_diff is None and len(a) != len(b):
        first_diff = min(len(a), len(b))
    da, db = digest(src), digest(dst)
    return {
        'spec_version': SPEC_VERSION,
        'n_source': len(a), 'n_shards': len(b),
        'counts_match': len(a) == len(b),
        'order_and_bytes_match': first_diff is None,
        'first_difference_index': first_diff,
        'source_digest': da, 'shard_digest': db,
        'digests_match': da == db,
        'equivalent': len(a) == len(b) and first_diff is None and da == db,
    }


def assert_equivalent(report: dict) -> dict:
    if not report['equivalent']:
        bits = []
        if not report['counts_match']:
            bits.append(f"{report['n_source']} records became "
                        f"{report['n_shards']}")
        if not report['order_and_bytes_match']:
            bits.append(f"records diverge at index "
                        f"{report['first_difference_index']}")
        if not report['digests_match']:
            bits.append('digests differ')
        raise ManifestError(
            'SHARD_NOT_EQUIVALENT: ' + '; '.join(bits)
            + '. The live writer must not be switched.')
    return report
