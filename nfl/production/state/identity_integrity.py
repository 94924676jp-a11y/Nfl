"""Canonical identity invariants. Owned by the state layer, not the gate.

One invariant today: no canonical player id may appear twice in the
population a slate is governed over. It lives here because the gsis_id axis
is the state layer's -- the same axis `player_universe` classifies on and
`PregameSlateState` is keyed by -- and a duplicate on it silently doubles a
player's opportunity, his exposure and his conflict rows at once.
"""
from __future__ import annotations

import collections
import pathlib
import sys
from typing import Any, Dict, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.integrity import contract as IC                   # noqa: E402

SPEC_VERSION = 'nfl-identity-integrity-0'
PRODUCER = 'state.identity_integrity.duplicate_player_identity'
C_DUPLICATE_IDENTITY = 'DUPLICATE_PLAYER_IDENTITY'


def duplicate_player_identity(population: Sequence[Any], *,
                              slate_key: str = None,
                              information_cut: str = None,
                              source_artifacts: Dict[str, str] = None,
                              what: str = 'player') -> IC.IntegrityReport:
    """No canonical id twice in the governed population.

    `population` is anything with `.gsis_id` -- PlayerState objects when the
    check runs live, saved dossiers when a verdict is re-derived from an
    artifact. Both are keyed on the same canonical axis, which is what makes
    one producer correct for both.

    AN EMPTY POPULATION IS NOT A PASS. It is NOT_APPLICABLE with a reason,
    because a check that ran over nobody proves nothing and a report that
    called it CHECKED_AND_PASSING would be the hole this module closes.
    """
    ids = [getattr(p, 'gsis_id', None) for p in population]
    named = [i for i in ids if i]
    if not named:
        return IC.not_applicable(
            C_DUPLICATE_IDENTITY, owner=IC.OWNER_STATE, producer=PRODUCER,
            version=SPEC_VERSION,
            why=f'the governed population carries no canonical id at all '
                f'({len(ids)} {what}(s) supplied), so there is nothing to '
                f'check for duplication. An empty check is not a passing '
                f'one.',
            subject_kind=what, n_subjects_supplied=len(ids),
            n_with_canonical_id=len(named))
    counts = collections.Counter(named)
    dupes = {k: v for k, v in counts.items() if v > 1}
    findings = [
        IC.IntegrityFinding(
            code=C_DUPLICATE_IDENTITY, subject=pid, subject_kind='player',
            severity=IC.BLOCKING, owner=IC.OWNER_STATE,
            detail=f'canonical id {pid} appears {n} times in the governed '
                   f'{what} population. Every number attached to him -- '
                   f'opportunity, projection, exposure, conflict rows -- is '
                   f'counted {n} times, and nothing downstream can tell '
                   f'which row is which.',
            producer=PRODUCER, producer_version=SPEC_VERSION,
            evidence={'occurrences': n, 'population': what,
                      'population_size': len(ids)},
            source_artifacts=dict(source_artifacts or {}),
            information_cut=information_cut)
        for pid, n in sorted(dupes.items())]
    return IC.finding_report(
        C_DUPLICATE_IDENTITY, owner=IC.OWNER_STATE, producer=PRODUCER,
        version=SPEC_VERSION, findings=findings, n_checked=len(named),
        detail=f'{len(named)} canonical id(s) over {len(ids)} {what}(s); '
               f'{len(dupes)} duplicated',
        source_artifacts=source_artifacts, information_cut=information_cut,
        slate_key=slate_key)
