"""Adversarial replay tests for nfl/ingest/validate.py -- G0A item 8.

Written by an agent that did NOT write the module. Owner Directive 3 §8: a
guard is not demonstrated by compliant data passing it.

The module exists to catch two defects that are mirror images of each other, and
a test suite that only seeds the first would license the second. Both halves are
seeded from measurements on the real files (2026-09-06), not from invention:

  B  FORWARD defect (Class A, absence read as success)
     `participation.ngs_air_yards` is in the header and holds 0 non-null values
     across all 45,919 rows. W2 line 128 records availability 0.0000. A header
     read as availability is how MLB shipped 7,926 rows with every meaningful
     column blank.

  C  REVERSE defect (Class A in mirror image)
     `defense_coverage_type` is 51.2% blank file-wide and 0.23% blank on the
     dropback denominator -- the blanks are run plays, where a coverage shell
     does not exist. Discarding it on the file-wide number would throw away
     correct data. So the SAME column must fail on ALL_ROWS and pass on its own
     denominator, and this suite asserts both directions on one frame.

  D  below floor, not empty       `def_yards_allowed`, 39.7% missing while its
                                  siblings are 0% (W6). A different code from
                                  empty, because it needs a different decision.
  E  absent, not empty            two defects, two codes.
  F  empty denominator            BLOCKED, and it must say it concludes nothing
                                  about the column.
  G/H empty frame, no specs       a vacuous pass is the failure being guarded.
  I  the floor itself             min_nonnull=0 would permit an empty column.
  J  the shipped specs            a spec nobody exercises is a spec nobody has
                                  checked.
  K  DEFECT SECTION -- FAILS TODAY. The null predicate does not recognise the
     null value the motivating measurement was made with.
  L  load-bearing                 Class E: assert_batch_games_are_new passed on
                                  every input it was ever given.

Run standalone:  python3.12 nfl/tests/test_denominator_validation.py
"""
import importlib
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.ingest.validate import (ALL_ROWS, PARTICIPATION_SPECS,  # noqa: E402
                                 DenominatorSpec, is_null, validate_column,
                                 validate_frame)
from nfl.tests.bypass import assert_guard_is_load_bearing  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _is(o, state, code):
    return isinstance(o, Outcome) and o.state is state and o.code == code


# --- frames shaped like the real measurements -------------------------------
N_PARTICIPATION = 45919          # real row count of the 2024 participation file


def frame_empty_column(n=N_PARTICIPATION):
    """ngs_air_yards: present in the header, 0 non-null of 45,919."""
    return [{'play_id': i, 'qb_dropback': 1 if i % 2 else 0,
             'ngs_air_yards': ''} for i in range(n)]


def frame_coverage_type(n=10000, n_dropbacks=4891, blank_on_dropbacks=11):
    """defense_coverage_type: 51.2% blank file-wide, 0.23% blank on dropbacks.

    4880 non-null of 10000 = 0.4880 file-wide (51.2% blank);
    4880 non-null of 4891 dropbacks = 0.99775 (0.225% blank).
    Blank on a run play is CORRECT DATA -- there is no coverage shell.
    """
    rows = []
    for i in range(n):
        drop = i < n_dropbacks
        if drop:
            blank = i < blank_on_dropbacks
            rows.append({'play_id': i, 'qb_dropback': 1,
                         'defense_coverage_type': '' if blank else 'COVER_3'})
        else:
            rows.append({'play_id': i, 'qb_dropback': 0,
                         'defense_coverage_type': ''})
    return rows


def frame_below_floor(n=1000, missing=397):
    """def_yards_allowed: 39.7% missing while its siblings are 0%."""
    return [{'team': f't{i % 32}',
             'def_yards_allowed': None if i < missing else 300 + i % 50,
             'def_points_allowed': 20 + i % 14} for i in range(n)]


DROPBACKS = ('dropbacks', lambda r: r.get('qb_dropback') == 1)


# ---------------------------------------------------------------------------
def test_a_populated_column_passes_on_its_denominator():
    print('\nA. compliant input passes, and the PASS carries the measurement')
    rows = frame_coverage_type()
    o = validate_column(rows, DenominatorSpec('defense_coverage_type',
                                              *DROPBACKS, min_nonnull=0.90))
    check('a well-populated column on its own denominator passes',
          _is(o, State.PASS, 'COLUMN_NONNULL_OK'), str(o))
    ev = o.evidence
    check('the denominator size is reported, not just the fraction',
          ev.get('n_denominator') == 4891 and ev.get('n_nonnull') == 4880,
          str(ev))
    check('and the total row count too, so the scoping is auditable',
          ev.get('n_rows_total') == 10000, str(ev))
    check('the PASS value is the measured fraction, not a bare True',
          isinstance(o.value, float) and abs(o.value - 0.99775) < 1e-4,
          repr(o.value))


def test_forward_defect_present_but_empty():
    print('\nB. SEEDED VIOLATION -- ngs_air_yards: in the header, 0 non-null '
          'of 45,919')
    rows = frame_empty_column()
    o = validate_column(rows, DenominatorSpec('ngs_air_yards', *ALL_ROWS))
    check('an all-blank column is COLUMN_EMPTY_ON_DENOMINATOR',
          _is(o, State.FAIL, 'COLUMN_EMPTY_ON_DENOMINATOR'), str(o))
    check('the refusal reports the real denominator it was measured on',
          o.evidence.get('n_denominator') == N_PARTICIPATION, str(o.evidence))
    check('empty is NOT reported as "below floor" -- the two need different '
          'decisions',
          o.code != 'COLUMN_BELOW_NONNULL_FLOOR')
    check('and it is refused on a scoped denominator too, not only file-wide',
          _is(validate_column(rows, DenominatorSpec('ngs_air_yards', *DROPBACKS)),
              State.FAIL, 'COLUMN_EMPTY_ON_DENOMINATOR'))
    for nullish in ('', 'NA', 'NaN', 'None', 'null', '  ', None):
        frame = [{'x': nullish} for _ in range(50)]
        check(f'{nullish!r} counts as null',
              _is(validate_column(frame, DenominatorSpec('x', *ALL_ROWS)),
                  State.FAIL, 'COLUMN_EMPTY_ON_DENOMINATOR'))


def test_reverse_defect_correctly_scoped_blanks():
    print('\nC. THE MIRROR IMAGE -- defense_coverage_type, 51.2% blank '
          'file-wide, 0.23% blank on dropbacks. One frame, two verdicts.')
    rows = frame_coverage_type()
    file_wide = validate_column(rows, DenominatorSpec('defense_coverage_type',
                                                      *ALL_ROWS,
                                                      min_nonnull=0.90))
    check('on ALL_ROWS the column FAILS (0.488 non-null against a 0.90 floor)',
          _is(file_wide, State.FAIL, 'COLUMN_BELOW_NONNULL_FLOOR'),
          str(file_wide))
    check('and the file-wide number reproduces the measured 51.2% blank',
          abs(file_wide.evidence.get('nonnull_fraction', 0) - 0.488) < 1e-6,
          str(file_wide.evidence))

    scoped = validate_column(rows, DenominatorSpec('defense_coverage_type',
                                                   *DROPBACKS,
                                                   min_nonnull=0.90))
    check('on the CORRECT denominator the same column on the same frame PASSES',
          _is(scoped, State.PASS, 'COLUMN_NONNULL_OK'), str(scoped))
    check('and reproduces the measured 0.23% blank on dropbacks',
          abs((1 - scoped.evidence['nonnull_fraction']) - 0.00225) < 1e-4,
          str(scoped.evidence))
    check('the two verdicts differ only in the declared denominator -- that is '
          'the whole claim of the module',
          file_wide.state is State.FAIL and scoped.state is State.PASS
          and file_wide.evidence['column'] == scoped.evidence['column'])

    print('     -- and the denominator cannot be defaulted away')
    try:
        DenominatorSpec('defense_coverage_type')          # type: ignore[call-arg]
        check('a spec without a denominator is refused', False,
              'it was constructed; "all rows" became a silent default')
    except TypeError:
        check('a spec without a denominator is refused', True)


def test_below_floor_is_not_empty():
    print('\nD. SEEDED VIOLATION -- def_yards_allowed, 39.7% missing while its '
          'siblings are 0%')
    rows = frame_below_floor()
    o = validate_column(rows, DenominatorSpec('def_yards_allowed', *ALL_ROWS))
    check('a partially-populated column is COLUMN_BELOW_NONNULL_FLOOR',
          _is(o, State.FAIL, 'COLUMN_BELOW_NONNULL_FLOOR'), str(o))
    check('it is not reported as empty -- it holds 603 real values',
          o.evidence.get('n_nonnull') == 603, str(o.evidence))
    check('and the refusal quantifies the damage aggregating it would do',
          '39.7%' in o.detail, o.detail[-60:])
    check('the sibling column at 0% missing passes on the same frame',
          _is(validate_column(rows, DenominatorSpec('def_points_allowed',
                                                    *ALL_ROWS)),
              State.PASS, 'COLUMN_NONNULL_OK'))
    check('a column just above its declared floor passes, so the floor is a '
          'threshold and not a mood',
          _is(validate_column(rows, DenominatorSpec('def_yards_allowed',
                                                    *ALL_ROWS,
                                                    min_nonnull=0.60)),
              State.PASS, 'COLUMN_NONNULL_OK'))


def test_absent_is_not_empty():
    print('\nE. SEEDED VIOLATION -- an absent column')
    rows = frame_below_floor()
    o = validate_column(rows, DenominatorSpec('ngs_air_yards', *ALL_ROWS))
    check('an absent column is COLUMN_ABSENT, not COLUMN_EMPTY',
          _is(o, State.FAIL, 'COLUMN_ABSENT'), str(o))
    check('and the refusal shows what the frame actually holds, so a typo is '
          'diagnosable',
          'def_yards_allowed' in (o.evidence.get('available') or []),
          str(o.evidence)[:120])
    ragged = [{'a': 1}] + [{'a': 1, 'late_column': 5} for _ in range(99)]
    check('a ragged frame whose column appears only after row 0 does not '
          'silently pass',
          validate_column(ragged, DenominatorSpec('late_column', *ALL_ROWS)
                          ).state is State.FAIL)


def test_empty_denominator_concludes_nothing():
    print('\nF. SEEDED VIOLATION -- the denominator itself did not materialise')
    rows = [{'play_id': i, 'qb_dropback': 0, 'defense_coverage_type': 'COVER_3'}
            for i in range(500)]
    o = validate_column(rows, DenominatorSpec('defense_coverage_type',
                                              *DROPBACKS))
    check('0 rows in the denominator is BLOCKED/DENOMINATOR_EMPTY',
          _is(o, State.BLOCKED, 'DENOMINATOR_EMPTY'), str(o))
    check('the cause is declared DATA -- not a rule, not the network',
          o.evidence.get('cause') == 'DATA', str(o.evidence))
    check('and it says explicitly that it concludes nothing about the column',
          'says nothing about the column' in o.detail, o.detail[-70:])
    check('it is neither a pass nor a verdict on the column',
          o.state not in (State.PASS, State.FAIL))
    check('the denominator that failed to select is named',
          o.evidence.get('denominator') == 'dropbacks', str(o.evidence))


def test_an_empty_frame_is_a_failure():
    print('\nG. SEEDED VIOLATION -- validating nothing (Class A)')
    for empty in ([], ()):
        o = validate_column(empty, DenominatorSpec('anything', *ALL_ROWS))
        check(f'{type(empty).__name__} frame -> FAIL/VALIDATION_INPUT_EMPTY',
              _is(o, State.FAIL, 'VALIDATION_INPUT_EMPTY'), str(o))
    o = validate_frame([], PARTICIPATION_SPECS)
    check('validate_frame on an empty frame does not report a vacuous pass',
          o.state is State.FAIL, str(o))
    inner = dict(o.evidence.get('census') or {})
    check('and every column is individually recorded as unvalidated',
          set(inner.values()) == {'FAIL'} and len(inner) == 2, str(inner))


def test_frame_level_reporting():
    print('\nH. validate_frame: no specs is a failure, and one call reports '
          'every defect')
    check('no specs -> FAIL/NO_SPECS_DECLARED',
          _is(validate_frame(frame_below_floor(), []), State.FAIL,
              'NO_SPECS_DECLARED'))
    check('an empty generator of specs is caught too, not consumed silently',
          _is(validate_frame(frame_below_floor(), (s for s in ())), State.FAIL,
              'NO_SPECS_DECLARED'))

    rows = [dict(a='', b=1, c='x' if i % 2 else '') for i in range(100)]
    o = validate_frame(rows, [DenominatorSpec('a', *ALL_ROWS),
                              DenominatorSpec('b', *ALL_ROWS),
                              DenominatorSpec('c', *ALL_ROWS),
                              DenominatorSpec('missing', *ALL_ROWS)])
    # DEFECT-V3, now fixed: validate_frame rolls up with
    # sportsplatform.governance.outcome.combine(), so a BLOCKED denominator no longer
    # arrives wearing the same state as a genuinely empty column. combine()
    # reports a full census rather than a failures-only map.
    check('a frame with several defects fails',
          _is(o, State.FAIL, 'FRAME_VALIDATION'), str(o))
    census = o.evidence['census']
    check('and reports every column at once, by column and by state',
          census == {'a': 'FAIL', 'b': 'PASS', 'c': 'FAIL',
                     'missing': 'FAIL'}, str(census))
    check('the columns that passed are named too, so a reader can see the '
          'scope of what was checked -- nothing is summarised away',
          census.get('b') == 'PASS', str(census))
    good = validate_frame(rows, [DenominatorSpec('b', *ALL_ROWS)])
    check('an all-clear frame reads PASS/FRAME_VALIDATED',
          _is(good, State.PASS, 'FRAME_VALIDATION'), str(good))

    # A BLOCKED denominator is not a verdict about the column, and the frame
    # rollup should not turn it into one. combine() in sportsplatform.governance.outcome
    # exists to do exactly this worst-first without flattening the state.
    blocked_rows = [{'qb_dropback': 0, 'defense_coverage_type': 'COVER_3'}
                    for _ in range(100)]
    ro = validate_frame(blocked_rows,
                        [DenominatorSpec('defense_coverage_type', *DROPBACKS)])
    check('DEFECT-V3 (low severity)  a BLOCKED denominator is not re-reported '
          'as a frame-level FAIL',
          ro.state is State.BLOCKED,
          f'got {ro.state.value}/{ro.code}. The inner DENOMINATOR_EMPTY block '
          f'survives in evidence["census"], so nothing is lost, but at the '
          f'frame boundary a DATA block and a model verdict become the same '
          f'state -- the exact distinction Cause was added to preserve. '
          f'One-line fix: roll up with combine().')


def test_the_floor_cannot_permit_an_empty_column():
    print('\nI. the floor is itself guarded -- min_nonnull=0 would license the '
          'condition the class exists to detect')
    for bad in (0.0, -0.1, 1.1, 2):
        try:
            DenominatorSpec('x', *ALL_ROWS, min_nonnull=bad)
            check(f'min_nonnull={bad} refused', False, 'it was accepted')
        except ValueError as exc:
            check(f'min_nonnull={bad} refused', 'min_nonnull' in str(exc))
    check('min_nonnull=1.0 (every row) is legal',
          DenominatorSpec('x', *ALL_ROWS, min_nonnull=1.0).min_nonnull == 1.0)
    check('a spec is frozen, so a caller cannot loosen a floor after the fact',
          _spec_is_frozen())


def _spec_is_frozen():
    s = DenominatorSpec('x', *ALL_ROWS)
    try:
        s.min_nonnull = 0.01          # type: ignore[misc]
        return False
    except Exception:
        return True


def test_the_shipped_specs_actually_run():
    print('\nJ. the specs the module ships are exercised, not just declared')
    check('two specs are shipped', len(PARTICIPATION_SPECS) == 2,
          str([s.column for s in PARTICIPATION_SPECS]))
    check('and neither defaults its denominator to all rows by accident',
          [s.denominator_name for s in PARTICIPATION_SPECS]
          == ['all_rows', 'dropbacks'],
          str([s.denominator_name for s in PARTICIPATION_SPECS]))
    # A frame in the shape the real participation file has: ngs_air_yards empty,
    # coverage type present on dropbacks only.
    rows = []
    for i in range(2000):
        drop = i % 2 == 0
        rows.append({'ngs_air_yards': '',
                     'n_offense': '11' if drop else '',
                     'route': 'GO' if drop else '',
                     'defense_coverage_type': 'COVER_3' if drop else ''})
    o = validate_frame(rows, PARTICIPATION_SPECS)
    check('the shipped specs refuse the real file shape',
          _is(o, State.FAIL, 'FRAME_VALIDATION'), str(o))
    codes = dict(o.evidence['census'])
    check('and they refuse it for ngs_air_yards ALONE -- the correctly-scoped '
          'coverage column is not condemned with it',
          codes == {'ngs_air_yards': 'FAIL',
                    'defense_coverage_type': 'PASS'}, str(codes))


def test_the_null_predicate_recognises_real_nulls():
    print('\nK. DEFECT SECTION -- what a null actually looks like on the path '
          'this module guards')
    # W1/W2 measured availability with pandas .notna(). A blank numeric cell
    # read by pandas and handed on as records is float("nan"), NOT "" --
    # verified 2026-09-06 with pandas 3.0.5:
    #     pd.read_csv(...).to_dict('records') -> {'ngs_air_yards': nan}
    nan = float('nan')
    check('DEFECT-V1  float("nan") is recognised as null',
          is_null(nan) is True,
          'is_null(float("nan")) is False. NULLISH holds the CSV spellings '
          '("", "NA", "NaN", "None", "null") but not the float, and not the '
          'lowercase string "nan" that str(float("nan")) produces.')

    rows = [{'play_id': i, 'ngs_air_yards': nan} for i in range(N_PARTICIPATION)]
    o = validate_column(rows, DenominatorSpec('ngs_air_yards', *ALL_ROWS))
    check('DEFECT-V2  the exact motivating case -- ngs_air_yards, 0 non-null '
          'of 45,919 -- is caught when the frame comes from pandas',
          _is(o, State.FAIL, 'COLUMN_EMPTY_ON_DENOMINATOR'),
          f'got {o.state.value}/{o.code} reporting '
          f'{o.evidence.get("nonnull_fraction")} non-null. Every value is NaN '
          f'and the module reports the column full. The one measurement this '
          f'module was built to reproduce passes it, if the reader is pandas.')

    check('the CSV spellings it does handle still work, so the fix is an '
          'addition and not a rewrite',
          all(is_null(v) for v in ('', 'NA', 'NaN', 'None', 'null', '   ', None)))
    check('and a real 0 is NOT null -- a numeric zero is a measurement',
          is_null(0) is False and is_null(0.0) is False)


def test_the_validation_is_load_bearing():
    print('\nL. LOAD-BEARING -- bypass the guard and the detections must '
          'disappear (Directive 3 §8, Class E)')
    empty_rows = frame_empty_column(n=500)
    bad_rows = [{'a': ''} for _ in range(200)]

    def run_column():
        m = importlib.import_module('nfl.ingest.validate')
        return m.validate_column(empty_rows,
                                 m.DenominatorSpec('ngs_air_yards', *m.ALL_ROWS))

    def run_frame():
        m = importlib.import_module('nfl.ingest.validate')
        return m.validate_frame(bad_rows,
                                [m.DenominatorSpec('a', *m.ALL_ROWS)])

    _load_bearing('the empty-column detection comes from is_null',
                  run=run_column, attr='is_null',
                  caught=lambda o: _is(o, State.FAIL,
                                       'COLUMN_EMPTY_ON_DENOMINATOR'),
                  replacement=lambda v: False)

    _load_bearing('and the frame verdict comes from validate_column, not from '
                  'the rollup',
                  run=run_frame, attr='validate_column',
                  caught=lambda o: _is(o, State.FAIL, 'FRAME_VALIDATION'),
                  returns=Outcome.ok('COLUMN_NONNULL_OK', value=1.0))


def _load_bearing(label, *, run, attr, caught, returns=None, replacement=None):
    try:
        assert_guard_is_load_bearing(run=run, module_path='nfl.ingest.validate',
                                     attr=attr, caught=caught, returns=returns,
                                     replacement=replacement)
        check(label, True)
    except AssertionError as exc:
        check(label, False, str(exc)[:200])


if __name__ == '__main__':
    test_a_populated_column_passes_on_its_denominator()
    test_forward_defect_present_but_empty()
    test_reverse_defect_correctly_scoped_blanks()
    test_below_floor_is_not_empty()
    test_absent_is_not_empty()
    test_empty_denominator_concludes_nothing()
    test_an_empty_frame_is_a_failure()
    test_frame_level_reporting()
    test_the_floor_cannot_permit_an_empty_column()
    test_the_shipped_specs_actually_run()
    test_the_null_predicate_recognises_real_nulls()
    test_the_validation_is_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
