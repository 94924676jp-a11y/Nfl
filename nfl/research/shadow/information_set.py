"""The latest LEGITIMATE pre-kickoff information set for one game.

SHADOW EVALUATION ONLY. This module reads nothing but the vintage capture
manifest and the blobs it names, and it selects by OBSERVATION TIME, never by
size, recency on disk, or row count.

WHY SELECTION BY OBSERVATION TIME AND NOT BY ROW COUNT

The rehearsal slate driver picks the roster vintage with the MOST week-1 rows
(`rehearsal/run_slate.py:roster`). For 2026_01_NE_SEA that resolves to
`weekly_rosters.0b005c45d924a541`, first observed 2026-09-10T05:05:18Z --
FOUR HOURS AFTER the 00:20Z kickoff. A bigger file is not a pre-kickoff file.
That driver is a rehearsal harness rather than the forecasting architecture, so
this module does not change it; it refuses to inherit the defect.

THE OBSERVATION BOUND

Only the 2026-09-06 captures carry an explicit `retrieved_at`. Every later row
carries a `capture_id` that IS a UTC instant. A blob observed in capture C was
retrieved at or before C, so the EARLIEST capture_id in which a content hash
appears is a sound upper bound on when that content became available, and it is
the bound used here. It can only ever be conservative -- it never claims content
was available earlier than it was.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
_VINTAGE = _REPO / 'nfl' / 'vintage'


class InformationSetError(RuntimeError):
    """Named, because a silent empty information set is the project's most
    expensive recurring defect."""


def _capture_instant(capture_id: str) -> _dt.datetime:
    return _dt.datetime.strptime(capture_id, '%Y%m%dT%H%M%SZ').replace(
        tzinfo=_dt.timezone.utc)


def _parse(ts) -> _dt.datetime:
    d = _dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def observations() -> list:
    """Every PASS capture row, with the tightest defensible observation time."""
    if not _MANIFEST.exists():
        raise InformationSetError(
            f'MANIFEST_ABSENT: {_MANIFEST} does not exist')
    out = []
    for line in _MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get('state') != 'PASS':
            continue
        val = row.get('value') or {}
        sha = val.get('sha256')
        if not sha:
            continue
        explicit = val.get('retrieved_at')
        out.append({
            'source': row['source'],
            'sha256': sha,
            'capture_id': row['capture_id'],
            'observed_at': (_parse(explicit) if explicit
                            else _capture_instant(row['capture_id'])),
            'observed_basis': 'retrieved_at' if explicit else 'capture_id',
            'n_bytes': val.get('n_bytes'),
        })
    if not out:
        raise InformationSetError(
            'MANIFEST_HAS_NO_PASS_ROWS: nothing to build an information set '
            'from')
    return out


def first_observation() -> dict:
    """(source, sha256) -> earliest observation of that exact content."""
    first = {}
    for o in observations():
        k = (o['source'], o['sha256'])
        if k not in first or o['observed_at'] < first[k]['observed_at']:
            first[k] = o
    return first


def blob_for(source: str, sha256: str):
    """The on-disk artifact for a content hash, or None. Never guessed."""
    stem = f'{source}.{sha256[:16]}.'
    hits = sorted(p for p in _VINTAGE.glob(stem + '*'))
    return hits[0] if hits else None


def build(kickoff_utc, sources=None) -> dict:
    """The latest pre-kickoff observation of each source.

    Returns a descriptor carrying, per source, the content hash, the
    observation time, the observation basis, the on-disk blob, and the blob's
    OWN recomputed sha256. Sources with no pre-kickoff observation are listed
    under `absent` rather than dropped: an information set that silently omits
    what it could not obtain is the same defect as a stage that reports success
    on an empty read.
    """
    ko = _parse(kickoff_utc)
    latest = {}
    for o in first_observation().values():
        if o['observed_at'] >= ko:
            continue
        s = o['source']
        if s not in latest or o['observed_at'] > latest[s]['observed_at']:
            latest[s] = o

    # THE DEFAULT SOURCE LIST COMES FROM THE REGISTRY, NOT FROM WHAT HAPPENED
    # TO SUCCEED. Deriving it from the observations would make a source that
    # never returned a single usable capture vanish from `absent` entirely,
    # and an information set that cannot name what it is missing is the
    # absence-read-as-success defect wearing a different hat.
    from nfl.capture import registry as _REG
    wanted = sorted(sources) if sources else sorted(_REG.BY_NAME)

    chosen, absent = {}, []
    for s in wanted:
        o = latest.get(s)
        if o is None:
            absent.append(s)
            continue
        blob = blob_for(s, o['sha256'])
        rec = {
            'source': s,
            'sha256': o['sha256'],
            'observed_at': o['observed_at'].isoformat().replace(
                '+00:00', 'Z'),
            'observed_basis': o['observed_basis'],
            'capture_id': o['capture_id'],
            'blob': os.path.relpath(blob, _REPO) if blob else None,
            'blob_sha256': None,
            'hours_before_kickoff': round(
                (ko - o['observed_at']).total_seconds() / 3600.0, 3),
        }
        if blob is not None:
            # `sha256` is the hash of the RAW download recorded at capture
            # time; `blob_sha256` is the hash of what is stored here, which for
            # several sources is a gzipped and column-reduced derivative. They
            # are DIFFERENT QUANTITIES and are expected to differ. Both are
            # carried so a reader never has to guess which one a later check
            # compared against.
            rec['blob_sha256'] = hashlib.sha256(blob.read_bytes()).hexdigest()
            rec['blob_is_derived'] = rec['blob_sha256'] != rec['sha256']
        chosen[s] = rec

    if not chosen:
        raise InformationSetError(
            'INFORMATION_SET_EMPTY: no source had any observation strictly '
            f'before kickoff {kickoff_utc}')

    return {
        'kickoff_utc': ko.isoformat().replace('+00:00', 'Z'),
        'selection_rule': 'latest content observed strictly before kickoff; '
                          'observation time is retrieved_at when recorded and '
                          'the earliest capture_id carrying the hash otherwise',
        'sources': chosen,
        'absent': absent,
        'newest_observation': max(r['observed_at'] for r in chosen.values()),
        'oldest_observation': min(r['observed_at'] for r in chosen.values()),
    }
