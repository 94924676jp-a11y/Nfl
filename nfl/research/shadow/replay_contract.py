"""Three replay modes, and a rule that a clock cannot enforce.

D23. `information_set.build(kickoff, observed_before=written_at)` selects the
latest observation of each source before the consumed clock. That is correct,
and it is not reproducible, because the manifest is APPEND-ONLY and can later
acquire rows whose timestamps ALSO satisfy that cutoff. Measured on
2024_01_ARI_BUF at written_at 2026-09-12T12:00:00Z: two runs, ten differing
partitions across five sources, and every pick lawful. The newer blob simply
did not exist in this branch's manifest when the seal was written -- 0 rows at
382556b, 0 at the common ancestor, 3 on main.

    A CLOCK BOUNDS SELECTION. IT DOES NOT DETERMINE IT.

What determines it is the manifest's CONTENT, and the content grows. So a
re-run at the same clock is not a replay; it is a new forecast wearing an old
timestamp. The seal already records the answer -- `consumed_partition_ids` --
and until now nothing could consume it.

THE THREE MODES, AND WHY THEY MUST NOT SHARE A NAME

  ORIGINAL_REPLAY            Reproduce a sealed forecast EXACTLY. Consumes the
                             recorded partitions and nothing else. Selection is
                             never re-run. A missing partition REFUSES; it is
                             never substituted, because substituting a
                             different lawful blob produces a different
                             forecast that claims to be the original one.

  RETROSPECTIVE_RECONSTRUCTION
                             What the forecast WOULD have consumed had we then
                             held everything we now know was lawful at that
                             clock. Legitimate and often more informative -- and
                             it is NOT the original forecast, so it may never be
                             scored as though the original had produced it.

  NEW_CANDIDATE_BACKTEST     A new candidate over a historical window. Neither
                             of the above: nothing is being reproduced.

Collapsing the first two is the specific error this module exists to prevent,
and it is an easy one to make because they agree whenever the manifest has not
grown -- which is exactly when nobody is looking.

WHAT THIS MODULE DOES NOT DO. It does not alter a seal, re-run a model, or
decide which mode a caller wanted. It resolves recorded partition ids into the
same descriptor shape `information_set.build` returns, so an ORIGINAL_REPLAY
can be fed the inputs it is supposed to have.
"""
from __future__ import annotations

import hashlib
import os
import pathlib

from nfl.research.shadow import information_set as ISET

SPEC_VERSION = 'replay_contract/1.0.0'

ORIGINAL_REPLAY = 'ORIGINAL_REPLAY'
RETROSPECTIVE_RECONSTRUCTION = 'RETROSPECTIVE_RECONSTRUCTION'
NEW_CANDIDATE_BACKTEST = 'NEW_CANDIDATE_BACKTEST'
MODES = (ORIGINAL_REPLAY, RETROSPECTIVE_RECONSTRUCTION, NEW_CANDIDATE_BACKTEST)

#: Modes that must consume a recorded input set rather than re-select one.
PINNED_MODES = (ORIGINAL_REPLAY,)

_REPO = pathlib.Path(__file__).resolve().parents[3]


class ReplayRefusal(Exception):
    """A named refusal. Never downgraded to a substitution."""

    def __init__(self, code, detail, **evidence):
        super().__init__(f'{code}: {detail}')
        self.code = code
        self.detail = detail
        self.evidence = evidence


def parse_partition_id(pid: str):
    """`source@sha16` -> (source, sha16). Raises rather than guessing."""
    if not isinstance(pid, str) or '@' not in pid:
        raise ReplayRefusal(
            'PARTITION_ID_MALFORMED',
            f'{pid!r} is not of the form source@sha16', partition_id=pid)
    source, _, addr = pid.partition('@')
    if not source or len(addr) < 8:
        raise ReplayRefusal(
            'PARTITION_ID_MALFORMED',
            f'{pid!r} parses to source={source!r} addr={addr!r}',
            partition_id=pid)
    return source, addr


def build_from_partition_ids(consumed_partition_ids, kickoff_utc):
    """The information set a sealed forecast ACTUALLY consumed.

    `kickoff_utc` is used only to report hours_before_kickoff, matching what
    `information_set.build` puts in the descriptor. It does NOT filter: a
    partition the forecast recorded is a partition the forecast consumed, and
    re-litigating its lawfulness here would be second-guessing a seal.

    Every partition is verified before use: the content hash must be present in
    the manifest under that source, and the on-disk blob must exist. Anything
    missing REFUSES by name.
    """
    ids = list(consumed_partition_ids or [])
    if not ids:
        raise ReplayRefusal(
            'NO_RECORDED_PARTITIONS',
            'an ORIGINAL_REPLAY needs the seal\'s consumed_partition_ids; an '
            'empty list is not an empty input set, it is a missing record')

    # Index the manifest ONCE by (source, sha16). first_observation keys on the
    # exact content, which is what a partition id addresses.
    by_addr = {}
    for (source, sha256), obs in ISET.first_observation().items():
        by_addr.setdefault((source, sha256[:16]), obs)

    ko = ISET._parse(kickoff_utc)
    chosen, missing, unverifiable = {}, [], []
    for pid in ids:
        source, addr = parse_partition_id(pid)
        obs = by_addr.get((source, addr[:16]))
        if obs is None:
            missing.append({'partition_id': pid, 'why': 'NOT_IN_MANIFEST'})
            continue
        blob = ISET.blob_for(source, obs['sha256'])
        if blob is None:
            missing.append({'partition_id': pid, 'why': 'BLOB_ABSENT_ON_DISK',
                            'sha256': obs['sha256']})
            continue
        rec = {
            'source': source,
            'sha256': obs['sha256'],
            'observed_at': obs['observed_at'].isoformat().replace(
                '+00:00', 'Z'),
            'observed_basis': obs['observed_basis'],
            'capture_id': obs['capture_id'],
            'blob': os.path.relpath(blob, _REPO),
            'blob_sha256': hashlib.sha256(blob.read_bytes()).hexdigest(),
            'hours_before_kickoff': round(
                (ko - obs['observed_at']).total_seconds() / 3600.0, 3),
            'pinned_by': 'consumed_partition_ids',
        }
        rec['blob_is_derived'] = rec['blob_sha256'] != rec['sha256']
        chosen[source] = rec

    if missing:
        # A MISSING PARTITION IS A REFUSAL, NOT A PROMPT TO LOOK FOR ANOTHER.
        # Substituting the nearest lawful blob would produce a different
        # forecast and present it as the original, which is the whole of D23
        # committed on purpose.
        raise ReplayRefusal(
            'ORIGINAL_PARTITION_UNAVAILABLE',
            f'{len(missing)} of {len(ids)} recorded partition(s) cannot be '
            f'resolved: {missing[:4]}. An ORIGINAL_REPLAY consumes exactly '
            f'what was consumed or it does not run.',
            missing=missing, n_requested=len(ids))

    return {'sources': chosen, 'absent': [],
            'mode': ORIGINAL_REPLAY,
            'pinned': True,
            'spec_version': SPEC_VERSION,
            'n_partitions': len(chosen),
            'unverifiable': unverifiable}


def build_for_mode(mode, *, kickoff_utc, written_at=None,
                   consumed_partition_ids=None, sources=None):
    """One entry point that cannot be called without saying which mode.

    The mode is REQUIRED and unvalidated modes refuse. A default would be
    chosen wrongly exactly once and then inherited everywhere.
    """
    if mode not in MODES:
        raise ReplayRefusal('REPLAY_MODE_UNKNOWN',
                            f'{mode!r} is not one of {MODES}', mode=mode)
    if mode in PINNED_MODES:
        if consumed_partition_ids is None:
            raise ReplayRefusal(
                'PINNED_MODE_WITHOUT_RECORDED_PARTITIONS',
                f'{mode} must be given the seal\'s consumed_partition_ids. '
                f'Re-running selection at the same clock is a NEW FORECAST, '
                f'not a replay -- see D23.', mode=mode)
        iset = build_from_partition_ids(consumed_partition_ids, kickoff_utc)
        return iset
    # The unpinned modes re-select, which is what they are FOR, and they say so
    # in the descriptor so a reader never has to infer it.
    if written_at is None:
        raise ReplayRefusal(
            'UNPINNED_MODE_WITHOUT_CLOCK',
            f'{mode} re-runs selection and therefore needs the clock to bound '
            f'it', mode=mode)
    iset = ISET.build(kickoff_utc, sources=sources, observed_before=written_at)
    iset = dict(iset)
    iset['mode'] = mode
    iset['pinned'] = False
    iset['spec_version'] = SPEC_VERSION
    return iset


def partition_ids_of(iset) -> list:
    """The partition ids an information set represents, in a stable order."""
    return sorted(f'{s}@{r["sha256"][:16]}'
                  for s, r in (iset.get('sources') or {}).items())
