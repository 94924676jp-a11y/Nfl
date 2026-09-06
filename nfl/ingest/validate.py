"""Denominator-aware non-null validation. G0A item 8.

THE DEFECT THIS PREVENTS, AND THE OPPOSITE DEFECT IT MUST NOT CAUSE

Forward: a column existing is not a column carrying values. Measured on the real
files 2026-09-06 -- `participation.ngs_air_yards` is present in the header and
holds 0 non-null values across all 45,919 rows; `advstats.receiving_broken_tackles`
is 100% null. MLB's analogue shipped an export of 7,926 rows with every
meaningful column blank. Reading a header as availability is Failure Taxonomy
Class A.

Reverse, and this is the half a naive version gets wrong: a column may be blank
precisely where it is undefined, and that is correct data. `defense_coverage_type`
is 51.2% blank across the whole participation file but **0.23% blank on the
dropback denominator** -- the blanks are run plays, where a coverage shell does
not exist. Discarding it on the file-wide number would be Class A in mirror
image: a correctly-scoped NULL read as data loss.

So a non-null floor is meaningless without the denominator it is measured on, and
this module refuses to check one without the other.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from typing import Callable, Iterable, Mapping, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, combine  # noqa: E402

NULLISH = ('', 'na', 'nan', 'none', 'null', 'n/a')


def is_null(v) -> bool:
    """True for every spelling of absence this data actually uses.

    The float NaN case is not hypothetical and is why this function exists in
    this form: `pandas.read_csv(...).to_dict('records')` yields `float('nan')`
    for a blank numeric cell, and the measurements that motivated this whole
    module (`ngs_air_yards`, 0 non-null of 45,919) were taken through pandas
    with `.notna()`. A string-only check reports that column as 1.0 non-null --
    it passes the guard on the exact input the guard was built for.
    """
    if v is None:
        return True
    # NaN is the only value that is not equal to itself. Checked before the
    # string branch because a NaN is not a str and would otherwise fall through.
    if isinstance(v, float) and v != v:
        return True
    if isinstance(v, str):
        return v.strip().lower() in NULLISH
    return False


@dataclasses.dataclass(frozen=True)
class DenominatorSpec:
    """A non-null expectation, and the population it is expected on.

    `denominator` is REQUIRED and has no default. That is deliberate: a default
    of "all rows" is the wrong answer for every correctly-scoped optional field,
    and it would be chosen once by whoever wrote the line and be wrong
    everywhere else.
    """
    column: str
    denominator_name: str
    denominator: Callable[[Mapping], bool]
    min_nonnull: float = 0.99

    def __post_init__(self):
        if not 0.0 < self.min_nonnull <= 1.0:
            raise ValueError(
                f'{self.column}: min_nonnull must be in (0, 1]; got '
                f'{self.min_nonnull}. A floor of 0 permits an empty column, '
                f'which is the condition this class exists to detect.')


ALL_ROWS = ('all_rows', lambda r: True)


def validate_column(rows: Sequence[Mapping], spec: DenominatorSpec) -> Outcome:
    """Check one column against its own denominator."""
    rows = list(rows)
    if not rows:
        return Outcome.fail(
            'VALIDATION_INPUT_EMPTY',
            f'{spec.column}: no rows supplied. Validating an empty frame would '
            f'report a vacuous pass, which is the failure being guarded.',
            column=spec.column)

    if spec.column not in rows[0]:
        return Outcome.fail(
            'COLUMN_ABSENT',
            f'{spec.column} is not present in the frame at all. Absent and '
            f'empty are different defects and get different codes.',
            column=spec.column, available=sorted(rows[0].keys())[:20])

    denom = [r for r in rows if spec.denominator(r)]
    if not denom:
        # Cannot conclude anything. Explicitly not a pass, explicitly not a fail
        # about the column -- the denominator itself did not materialise.
        return Outcome.blocked(
            'DENOMINATOR_EMPTY',
            f'{spec.column}: the denominator {spec.denominator_name!r} selected '
            f'0 of {len(rows)} rows, so the non-null fraction is undefined. '
            f'This says nothing about the column.',
            cause=Cause.DATA, column=spec.column,
            denominator=spec.denominator_name, n_rows=len(rows))

    nonnull = sum(1 for r in denom if not is_null(r.get(spec.column)))
    frac = nonnull / len(denom)
    ev = dict(column=spec.column, denominator=spec.denominator_name,
              n_denominator=len(denom), n_nonnull=nonnull,
              nonnull_fraction=round(frac, 6), floor=spec.min_nonnull,
              n_rows_total=len(rows))

    if nonnull == 0:
        return Outcome.fail(
            'COLUMN_EMPTY_ON_DENOMINATOR',
            f'{spec.column}: 0 non-null of {len(denom)} rows on its own '
            f'denominator {spec.denominator_name!r}. The column exists and '
            f'carries nothing. REJECTED -- SOURCE EMPTY.', **ev)

    if frac < spec.min_nonnull:
        return Outcome.fail(
            'COLUMN_BELOW_NONNULL_FLOOR',
            f'{spec.column}: {frac:.4f} non-null on {spec.denominator_name!r}, '
            f'below the declared floor {spec.min_nonnull}. Aggregating it would '
            f'under-count by {(1 - frac) * 100:.1f}% and look plausible.', **ev)

    return Outcome.ok('COLUMN_NONNULL_OK', value=frac,
                      detail=f'{spec.column}: {frac:.4f} non-null on '
                             f'{spec.denominator_name!r} '
                             f'(n={len(denom)}), floor {spec.min_nonnull}.',
                      **ev)


def validate_frame(rows: Sequence[Mapping],
                   specs: Iterable[DenominatorSpec]) -> Outcome:
    """All specs. Reports every failure, not just the first -- a caller that
    fixes one column at a time re-runs the pipeline once per defect."""
    specs = list(specs)
    if not specs:
        return Outcome.fail(
            'NO_SPECS_DECLARED',
            'validate_frame called with no specs. A frame nobody declared '
            'expectations for has not been validated; it has been waved '
            'through.')
    results = {s.column: validate_column(rows, s) for s in specs}
    # combine() preserves the distinction a hand-rolled rollup destroys: a
    # DENOMINATOR_EMPTY is BLOCKED (we could not tell) and must not arrive at the
    # caller wearing the same state as a column that is genuinely empty.
    return combine(results, 'FRAME_VALIDATION')


# Specs seeded from real measured defects, not from imagination. Each cites the
# figure that put it here.
PARTICIPATION_SPECS = (
    # 0 non-null of 45,919 -- the whole reason this module exists.
    DenominatorSpec('ngs_air_yards', *ALL_ROWS),
    # 51.2% blank file-wide, 0.23% blank on dropbacks. Correct data, wrongly
    # scoped is what breaks it.
    DenominatorSpec('defense_coverage_type', 'dropbacks',
                    lambda r: str(r.get('n_offense', '')).strip() != ''
                    and str(r.get('route', '')).strip() != '',
                    min_nonnull=0.90),
)
