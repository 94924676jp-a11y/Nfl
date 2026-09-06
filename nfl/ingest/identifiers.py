"""Identifier mapping with a named refusal. G0A item 9.

WHY A NAMED FAILURE AND NOT AN INNER JOIN

`snap_counts` is keyed on `pfr_player_id`; everything else is keyed on `gsis_id`.
`players.csv` is a clean injective crosswalk (22,653 entries, 0 duplicates) and
the join succeeds at 99.8422%. The 0.16% is the dangerous part.

Measured on the 42 unmapped 2024 snap rows, which resolve to 6 players: a
name-based fallback would recover 2 correctly, **silently mis-join 2**, and fail
2. "Cody White" is ambiguous; "Rodney Williams" collides with a 2001 player.

So the fallback is not a convenience with a small error rate -- it is a source of
wrong rows that look right. This module refuses it. An unmapped id is a named
FAIL that keeps the row visible; it is never dropped (Class C2: the alias table
existed and was simply never applied) and never guessed.
"""
from __future__ import annotations

import csv
import pathlib
import sys
from typing import Mapping, Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402


class Crosswalk:
    """pfr_id -> gsis_id, built from players.csv and nothing else."""

    def __init__(self, mapping: Mapping[str, str], source_sha256: str = ''):
        self._m = dict(mapping)
        self.source_sha256 = source_sha256

    def __len__(self) -> int:
        return len(self._m)

    @classmethod
    def from_csv(cls, path, pfr_col: str = 'pfr_id',
                 gsis_col: str = 'gsis_id', source_sha256: str = '') -> Outcome:
        p = pathlib.Path(path)
        if not p.exists():
            return Outcome.blocked(
                'CROSSWALK_FILE_MISSING', f'{p} does not exist.',
                cause=Cause.DEPENDENCY, path=str(p))
        m, dupes = {}, []
        with open(p, newline='') as fh:
            rdr = csv.DictReader(fh)
            fields = rdr.fieldnames or []
            missing = [c for c in (pfr_col, gsis_col) if c not in fields]
            if missing:
                # BOTH columns are checked. Validating only pfr_col reported a
                # renamed gsis column as CROSSWALK_EMPTY -- "parsed 0 usable
                # pairs" -- which sends an operator to the data when the defect
                # is in the file's schema.
                return Outcome.fail(
                    'CROSSWALK_SCHEMA_UNEXPECTED',
                    f'{p}: missing column(s) {missing}. Field names are read '
                    f'from the schema, never guessed.',
                    missing=missing, available=fields[:25])
            for row in rdr:
                a, b = (row.get(pfr_col) or '').strip(), (row.get(gsis_col) or '').strip()
                if not a or not b:
                    continue
                if a in m and m[a] != b:
                    dupes.append(a)
                m[a] = b
        if not m:
            return Outcome.fail(
                'CROSSWALK_EMPTY',
                f'{p}: parsed 0 usable pairs. An empty crosswalk would map '
                f'nothing and refuse everything, which looks like a data '
                f'problem downstream instead of a loader problem here.')
        if dupes:
            return Outcome.fail(
                'CROSSWALK_NOT_WELL_DEFINED',
                f'{p}: {len(dupes)} pfr ids map to more than one gsis id, e.g. '
                f'{sorted(set(dupes))[:5]}. The mapping is not a function.',
                n_dupes=len(set(dupes)))
        # Injectivity is the OTHER direction and was previously unchecked, so a
        # crosswalk merging two players into one gsis_id loaded as PASS with the
        # word "injective" in its detail. That silently merges two players' snap
        # rows: a wrong row that looks right, which is what this module exists to
        # prevent.
        rev: dict = {}
        collisions: dict = {}
        for a, b in m.items():
            if b in rev:
                collisions.setdefault(b, [rev[b]]).append(a)
            else:
                rev[b] = a
        if collisions:
            return Outcome.fail(
                'CROSSWALK_NOT_INJECTIVE',
                f'{p}: {len(collisions)} gsis ids are claimed by more than one '
                f'pfr id, e.g. '
                f'{ {k: v for k, v in list(collisions.items())[:3]} }. Using it '
                f'would merge distinct players into one.',
                n_collisions=len(collisions))
        return Outcome.ok('CROSSWALK_LOADED', value=cls(m, source_sha256),
                          detail=f'{p.name}: {len(m)} pfr->gsis pairs, injective.',
                          n_pairs=len(m))

    def map_pfr_id(self, pfr_id: Optional[str], *, context: str = '') -> Outcome:
        """The only permitted way to get a gsis_id from a pfr_id."""
        if pfr_id is None or not str(pfr_id).strip():
            return Outcome.fail(
                'IDENTIFIER_ABSENT',
                f'no pfr_player_id supplied{f" ({context})" if context else ""}. '
                f'Absent and unmapped are different defects.',
                context=context)
        key = str(pfr_id).strip()
        if key not in self._m:
            return Outcome.fail(
                'PFR_ID_UNMAPPED',
                f'{key!r} is not in the crosswalk'
                f'{f" ({context})" if context else ""}. The row is NOT dropped '
                f'and a name-based fallback is NOT attempted: measured on the '
                f'six real unmapped players, a name fallback recovers 2, '
                f'silently mis-joins 2, and fails 2.',
                pfr_player_id=key, context=context,
                crosswalk_size=len(self._m))
        return Outcome.ok('IDENTIFIER_MAPPED', value=self._m[key],
                          detail=f'{key} -> {self._m[key]}',
                          pfr_player_id=key)

    def map_by_name(self, *_a, **_k) -> Outcome:
        """Deliberately refuses. Present so the absence is explicit rather than
        an omission somebody helpfully fills in later."""
        return Outcome.blocked(
            'NAME_FALLBACK_REFUSED',
            'Name-based identifier matching is refused by design. Measured: of '
            'six real unmapped players it recovers 2, SILENTLY MIS-JOINS 2, and '
            'fails 2. A wrong row that looks right is worse than a named '
            'refusal. Close the gap with a crosswalk entry, not a heuristic.',
            cause=Cause.GOVERNANCE)
