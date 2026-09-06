"""Adversarial replay tests for nfl/ingest/identifiers.py and eligibility.py --
G0A item 9 and Directive 3 §6.

Written by an agent that did NOT write the modules. Owner Directive 3 §8: a
guard is not demonstrated by compliant data passing it; it must reject a seeded
violation, and a critical guard must fail its replay test when bypassed.

Seeded from the measurements in the modules' own docstrings and in
nfl/research/W1_DATA_PROVENANCE.md:

  A  the join that works           99.8422% of snap rows map cleanly. A refusal
                                   module that refuses everything is an outage,
                                   not a guard, so the positive case is tested
                                   first.
  B  PFR_ID_UNMAPPED               the 0.16%: 42 unmapped 2024 snap rows over 6
                                   players. The row is kept and named. Class C2
                                   is the opposite failure -- the alias table
                                   existed and was simply never applied, and
                                   three games vanished.
  C  IDENTIFIER_ABSENT             absent and unmapped are different defects.
  D  NAME_FALLBACK_REFUSED         measured on those 6 players a name fallback
                                   recovers 2, SILENTLY MIS-JOINS 2, fails 2.
                                   "Cody White" is ambiguous; "Rodney Williams"
                                   collides with a 2001 player. The refusal must
                                   hold for every input, including the ones it
                                   would have got right.
  E  crosswalk load                empty, non-injective and wrong-schema files
                                   are loader problems and must not be handed
                                   downstream as data problems.
  F  DEFECT SECTION -- FAILS TODAY. Two holes in the load-time checks.
  G  eligibility debt              BLOCKED by default; the NFL-1 team baseline
                                   consumes prior-season final scores only
                                   (C3 §3 policy table) and is correctly outside
                                   the debt. The debt must block exactly what it
                                   should and nothing else.
  H  DEFECT -- the debt's escape hatch accepts the quarantined post-hoc field.
  I  load-bearing                  Class E.

Run standalone:  python3.12 nfl/tests/test_identifier_mapping.py
"""
import importlib
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.ingest import eligibility as E  # noqa: E402
from nfl.ingest.identifiers import Crosswalk  # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing  # noqa: E402
from sportsplatform.governance.outcome import (Outcome, SilentSuccess,  # noqa: E402
                                   State)

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


# The six real unmapped players, from the identifiers.py docstring and W1.
UNMAPPED_SIX = ('WhitCo01', 'WillRo05', 'JohnTy07', 'SmitDa11', 'BrowJa14',
                'DaviMi03')
N_SNAP_ROWS = 26616          # 42 unmapped of 26,616 is the measured 99.8422%
N_UNMAPPED_ROWS = 42

KNOWN = {f'PlayA{i:03d}': f'00-00{30000 + i}' for i in range(100)}


def _csv(tmp, name, text):
    p = pathlib.Path(tmp) / name
    p.write_text(text)
    return p


# ---------------------------------------------------------------------------
def test_the_join_that_works():
    print('\nA. a known pfr_id maps, and the PASS carries the gsis_id')
    cw = Crosswalk(KNOWN)
    o = cw.map_pfr_id('PlayA007')
    check('a known id maps', _is(o, State.PASS, 'IDENTIFIER_MAPPED'), str(o))
    check('and the value is the gsis_id, not a bare True',
          o.value == KNOWN['PlayA007'], repr(o.value))
    check('whitespace around a real id is stripped, not treated as unmapped',
          Crosswalk(KNOWN).map_pfr_id('  PlayA007 ').value == KNOWN['PlayA007'])
    check('unwrap returns the id on a PASS',
          o.unwrap() == KNOWN['PlayA007'])
    check('the crosswalk knows its own size, so an empty one is visible',
          len(cw) == 100)


def test_unmapped_is_named_never_dropped_never_guessed():
    print('\nB. SEEDED VIOLATION -- 42 unmapped snap rows over 6 players '
          '(measured join rate 99.8422%)')
    cw = Crosswalk(KNOWN)
    o = cw.map_pfr_id('WhitCo01', context='snap_counts 2024 wk3')
    check('an unmapped id is FAIL/PFR_ID_UNMAPPED',
          _is(o, State.FAIL, 'PFR_ID_UNMAPPED'), str(o))
    check('the row is NOT dropped -- the id rides in the evidence',
          o.evidence.get('pfr_player_id') == 'WhitCo01', str(o.evidence))
    check('the caller context is preserved, so the row is findable',
          o.evidence.get('context') == 'snap_counts 2024 wk3', str(o.evidence))
    check('it is NOT guessed -- no gsis_id is returned',
          o.value is None, repr(o.value))
    check('and consuming it raises rather than yielding a default',
          _unwrap_raises(o))
    check('the refusal states the measured cost of the alternative',
          'mis-joins 2' in o.detail.lower(), o.detail[-90:])

    print('     -- replayed over the whole measured file shape')
    rows = []
    for i in range(N_SNAP_ROWS):
        if i < N_UNMAPPED_ROWS:
            rows.append(UNMAPPED_SIX[i % 6])
        else:
            rows.append(f'PlayA{i % 100:03d}')
    outs = [cw.map_pfr_id(r) for r in rows]
    mapped = [o for o in outs if o.state is State.PASS]
    unmapped = [o for o in outs if _is(o, State.FAIL, 'PFR_ID_UNMAPPED')]
    check('every row produces an outcome -- nothing vanishes on the way '
          'through (Class C2: three games once did)',
          len(mapped) + len(unmapped) == N_SNAP_ROWS,
          f'{len(mapped)} + {len(unmapped)} != {N_SNAP_ROWS}')
    check('exactly the 42 unmapped rows are refused',
          len(unmapped) == N_UNMAPPED_ROWS, str(len(unmapped)))
    check('and they resolve to exactly 6 distinct players, each named',
          {o.evidence['pfr_player_id'] for o in unmapped} == set(UNMAPPED_SIX))
    check('the observed join rate reproduces the measured 99.8422%',
          abs(len(mapped) / N_SNAP_ROWS - 0.998422) < 1e-6,
          f'{len(mapped) / N_SNAP_ROWS:.6f}')


def _unwrap_raises(o):
    try:
        o.unwrap()
        return False
    except SilentSuccess:
        return True


def test_absent_is_a_different_defect_from_unmapped():
    print('\nC. SEEDED VIOLATION -- no identifier at all')
    cw = Crosswalk(KNOWN)
    for absent in (None, '', '   ', '\t'):
        o = cw.map_pfr_id(absent)
        check(f'{absent!r} -> FAIL/IDENTIFIER_ABSENT',
              _is(o, State.FAIL, 'IDENTIFIER_ABSENT'), str(o))
    check('absent and unmapped do not share a code',
          cw.map_pfr_id(None).code != cw.map_pfr_id('WhitCo01').code)
    check('and the module says why they are kept apart',
          'different defects' in cw.map_pfr_id(None).detail)


def test_name_fallback_is_refused_always():
    print('\nD. SEEDED VIOLATION -- the helpful name fallback (recovers 2, '
          'MIS-JOINS 2, fails 2)')
    cw = Crosswalk(KNOWN)
    calls = (('Cody White',), ('Rodney Williams', 'WAS', 2024), (),
             ('an unambiguous name nobody shares',))
    for args in calls:
        o = cw.map_by_name(*args)
        check(f'map_by_name{args!r} refuses',
              _is(o, State.BLOCKED, 'NAME_FALLBACK_REFUSED'), str(o))
    o = cw.map_by_name(name='Cody White', season=2024, team='PIT')
    check('keyword calls are refused too -- there is no arrangement of '
          'arguments that gets a name matched',
          _is(o, State.BLOCKED, 'NAME_FALLBACK_REFUSED'), str(o))
    check('the refusal is GOVERNANCE, not a missing dependency: it is a '
          'decision, not a defect',
          o.evidence.get('cause') == 'GOVERNANCE', str(o.evidence))
    check('no value is produced even by accident',
          o.value is None and _unwrap_raises(o))
    check('and it names the fix -- a crosswalk entry, not a heuristic',
          'crosswalk entry' in o.detail, o.detail[-80:])
    check('it refuses even for a name that WOULD have matched, because the '
          'caller cannot tell which case they are in',
          _is(cw.map_by_name('PlayA007'), State.BLOCKED,
              'NAME_FALLBACK_REFUSED'))


def test_crosswalk_load_refuses_bad_files():
    print('\nE. SEEDED VIOLATIONS -- what a crosswalk file must not be')
    with tempfile.TemporaryDirectory() as tmp:
        good = _csv(tmp, 'good.csv',
                    'pfr_id,gsis_id,display_name\n'
                    'PlayA001,00-0030001,A One\nPlayA002,00-0030002,A Two\n')
        o = Crosswalk.from_csv(good)
        check('a clean injective file loads',
              _is(o, State.PASS, 'CROSSWALK_LOADED'), str(o))
        check('and the loaded object maps',
              o.value.map_pfr_id('PlayA002').value == '00-0030002')
        check('the pair count is reported so an unexpectedly small file shows',
              o.evidence.get('n_pairs') == 2, str(o.evidence))

        dup = _csv(tmp, 'dup.csv',
                   'pfr_id,gsis_id\nPlayA001,00-0030001\nPlayA001,00-0099999\n')
        o = Crosswalk.from_csv(dup)
        check('one pfr id with two gsis ids is FAIL/CROSSWALK_NOT_WELL_DEFINED',
              _is(o, State.FAIL, 'CROSSWALK_NOT_WELL_DEFINED'), str(o))
        check('and no crosswalk object escapes the failure',
              o.value is None and _unwrap_raises(o))

        empty = _csv(tmp, 'empty.csv', 'pfr_id,gsis_id\n')
        check('a header-only file is FAIL/CROSSWALK_EMPTY -- a loader problem, '
              'named here rather than surfacing as 22,653 unmapped rows later',
              _is(Crosswalk.from_csv(empty), State.FAIL, 'CROSSWALK_EMPTY'))

        blanks = _csv(tmp, 'blanks.csv', 'pfr_id,gsis_id\n,\n , \n')
        check('a file of blank pairs is empty too, not silently 2 entries',
              _is(Crosswalk.from_csv(blanks), State.FAIL, 'CROSSWALK_EMPTY'))

        wrong = _csv(tmp, 'wrong.csv', 'player_id,nfl_id\nx,1\n')
        o = Crosswalk.from_csv(wrong)
        check('a file with the wrong schema is FAIL/CROSSWALK_SCHEMA_UNEXPECTED',
              _is(o, State.FAIL, 'CROSSWALK_SCHEMA_UNEXPECTED'), str(o))
        check('and it lists the field names it did find, so nobody guesses',
              'player_id' in (o.evidence.get('available') or []),
              str(o.evidence))

        missing = pathlib.Path(tmp) / 'nope.csv'
        o = Crosswalk.from_csv(missing)
        check('a missing file is BLOCKED/CROSSWALK_FILE_MISSING with a '
              'DEPENDENCY cause -- not a claim about the data',
              _is(o, State.BLOCKED, 'CROSSWALK_FILE_MISSING')
              and o.evidence.get('cause') == 'DEPENDENCY', str(o))

        same = _csv(tmp, 'same.csv',
                    'pfr_id,gsis_id\nPlayA001,00-0030001\nPlayA001,00-0030001\n')
        check('the same pair listed twice is NOT a conflict -- the check is '
              'about disagreement, not repetition',
              _is(Crosswalk.from_csv(same), State.PASS, 'CROSSWALK_LOADED'))


def test_crosswalk_load_defects():
    print('\nF. DEFECT SECTION -- two things the load-time checks let through')
    with tempfile.TemporaryDirectory() as tmp:
        # Injective means distinct keys map to distinct values. The check only
        # tests well-definedness (one key, one value). Two pfr ids landing on
        # one gsis id merges two players' snap rows onto one player -- the exact
        # "wrong row that looks right" this module exists to prevent.
        collide = _csv(tmp, 'collide.csv',
                       'pfr_id,gsis_id\n'
                       'WhitCo01,00-0035000\nWhitCo02,00-0035000\n'
                       'PlayA001,00-0030001\n')
        o = Crosswalk.from_csv(collide)
        check('DEFECT-I1  two pfr ids mapping to ONE gsis id is refused at load',
              _is(o, State.FAIL, 'CROSSWALK_NOT_INJECTIVE'),
              f'got {o.state.value}/{o.code} and the detail claims '
              f'"injective". Both ids resolve, to the same player: a silent '
              f'many-to-one merge of two players\' rows. The load check tests '
              f'that each key has one value, which is well-definedness, not '
              'FIXED: well-definedness (one key, one value) and injectivity '
              '(one value, one key) are now separate checks with separate '
              'codes. Two pfr ids resolving to one gsis id would have merged '
              'two players\' snap rows silently.')

        # A file with pfr_id but no gsis_id has the wrong schema. It is reported
        # as a data emptiness, which is the direction CROSSWALK_EMPTY's own text
        # says it is trying to avoid pointing an operator in.
        nogsis = _csv(tmp, 'nogsis.csv', 'pfr_id,player_name\nPlayA001,A One\n')
        o = Crosswalk.from_csv(nogsis)
        check('DEFECT-I2  a file missing the gsis column is '
              'CROSSWALK_SCHEMA_UNEXPECTED, not CROSSWALK_EMPTY',
              o.code == 'CROSSWALK_SCHEMA_UNEXPECTED',
              f'got {o.code}. Only pfr_col is checked against the header; '
              f'gsis_col is not, so a schema change upstream is reported as '
              f'"parsed 0 usable pairs" and sends the operator to look at the '
              f'data. outcome.py: "a refusal whose code was reused for two '
              f'different causes sent an operator to the wrong place".')


def test_the_eligibility_debt():
    print('\nG. the prediction-time eligibility debt (Directive 3 §6)')
    o = E.require_prediction_time_eligibility('qb_passing_yards_model')
    check('by default it is BLOCKED/PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE',
          _is(o, State.BLOCKED, 'PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE'),
          str(o))
    check('the cause is DEPENDENCY -- the input does not exist yet; nothing is '
          'broken and nothing is refused by rule',
          o.evidence.get('cause') == 'DEPENDENCY', str(o.evidence))
    check('the component that needs it is named',
          o.evidence.get('component') == 'qb_passing_yards_model')
    check('the closing sources are enumerated, so the debt names its own '
          'discharge condition',
          len(o.evidence.get('closing_sources') or []) == 3,
          str(o.evidence.get('closing_sources')))
    check('and the refusal states the measurement that disqualifies the '
          'tempting substitute',
          '3,438' in o.detail and 'depth' in o.detail, o.detail[:120])
    check('no value escapes a BLOCKED debt',
          o.value is None and _unwrap_raises(o))

    print('     -- and it blocks exactly what it should, nothing else')
    check('the NFL-1 team baseline is outside the debt (C3 §3: prior-season '
          'final scores are its only input)',
          E.component_needs_eligibility('nfl1_coldstart_team_baseline') is False)
    for needs in ('qb_passing_yards_model', 'wr_receptions', 'anything_else',
                  '', 'nfl1_coldstart_team_baseline '):
        check(f'{needs!r} still needs eligibility (fail-closed on an unknown '
              f'or mistyped component)',
              E.component_needs_eligibility(needs) is True)
    check('a genuine prediction-time source discharges the debt',
          _is(E.require_prediction_time_eligibility(
                  'qb_passing_yards_model', True,
                  'official inactives feed (~90 min pre-kickoff; resolves Questionable to 0/1)'),
              State.PASS, 'PREDICTION_TIME_ELIGIBILITY_AVAILABLE'))
    check('claiming availability without naming the source does not',
          _is(E.require_prediction_time_eligibility('m', True, ''),
              State.BLOCKED, 'PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE'))


def test_the_debt_escape_hatch():
    print('\nH. DEFECT SECTION -- what the debt accepts as a "source"')
    o = E.require_prediction_time_eligibility(
        'qb_passing_yards_model', True, 'weekly_rosters.status')
    check('DEFECT-I3  the quarantined post-hoc field cannot be declared as the '
          'prediction-time eligibility source',
          o.state is not State.PASS,
          f'got {o.state.value}/{o.code} -- the debt is discharged by any '
          f'non-empty string, including the exact field the module\'s own '
          f'docstring quarantines (INA -> 0 snaps of 3,438). CLOSING_SOURCES '
          f'is declared and is not consulted. Directive 3 §6 forbids the '
          f'substitution, and this is the one line where it is available.')
    o2 = E.require_prediction_time_eligibility('m', True, 'a plausible guess')
    check('DEFECT-I3b  an arbitrary string is not accepted either',
          o2.state is not State.PASS,
          f'got {o2.state.value} for source_name={"a plausible guess"!r}. '
          f'Nothing checks the name against CLOSING_SOURCES, and nothing '
          f'records provenance for the claim.')


def test_the_refusals_are_load_bearing():
    print('\nI. LOAD-BEARING -- bypass the guard and the refusals must '
          'disappear (Directive 3 §8, Class E)')

    class NameGuessingCrosswalk:
        """What somebody helpfully adds later. It recovers 2 of 6 and
        mis-joins 2, and every test that does not check for it still passes."""

        def __init__(self, mapping, *a, **k):
            self._m = dict(mapping)

        def map_pfr_id(self, pfr_id, *, context=''):
            return Outcome.ok('IDENTIFIER_MAPPED', value='00-0099999',
                              detail=f'{pfr_id} matched by name')

    def run_unmapped():
        m = importlib.import_module('nfl.ingest.identifiers')
        return m.Crosswalk(KNOWN).map_pfr_id('WhitCo01')

    def run_eligibility():
        m = importlib.import_module('nfl.ingest.eligibility')
        return m.require_prediction_time_eligibility('qb_passing_yards_model')

    _load_bearing('the unmapped refusal comes from Crosswalk, not from the '
                  'shape of the test',
                  module_path='nfl.ingest.identifiers', attr='Crosswalk',
                  run=run_unmapped,
                  caught=lambda o: _is(o, State.FAIL, 'PFR_ID_UNMAPPED'),
                  replacement=NameGuessingCrosswalk)

    _load_bearing('the eligibility debt comes from '
                  'require_prediction_time_eligibility',
                  module_path='nfl.ingest.eligibility',
                  attr='require_prediction_time_eligibility',
                  run=run_eligibility,
                  caught=lambda o: _is(
                      o, State.BLOCKED,
                      'PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE'),
                  returns=Outcome.ok('PREDICTION_TIME_ELIGIBILITY_AVAILABLE',
                                     value='depth chart rank'))


def _load_bearing(label, *, run, module_path, attr, caught, returns=None,
                  replacement=None):
    try:
        assert_guard_is_load_bearing(run=run, module_path=module_path,
                                     attr=attr, caught=caught, returns=returns,
                                     replacement=replacement)
        check(label, True)
    except AssertionError as exc:
        check(label, False, str(exc)[:200])


if __name__ == '__main__':
    test_the_join_that_works()
    test_unmapped_is_named_never_dropped_never_guessed()
    test_absent_is_a_different_defect_from_unmapped()
    test_name_fallback_is_refused_always()
    test_crosswalk_load_refuses_bad_files()
    test_crosswalk_load_defects()
    test_the_eligibility_debt()
    test_the_debt_escape_hatch()
    test_the_refusals_are_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
