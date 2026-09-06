"""Adversarial replay tests for nfl/ingest/allowlist.py -- G0A items 6 and 7.

Written by an agent that did NOT write the module, against the standard in
Owner Directive 3 §8: "A guard is not demonstrated merely because compliant data
passes it. It must reject a seeded violation, and critical guards must
demonstrate that removing/bypassing the guard causes the replay test to fail."

Every section is seeded from a measurement in a committed artifact, not from an
invented case:

  A  compliant read                W1 §5: the pbp columns nobody flagged.
  B  MARKET                        W1 §5.1: the 8 schedules market columns are
                                   re-stamped onto all 49,492 pbp rows, so
                                   "I only read pbp" ingests the closing line
                                   49,492 times. CLAUDE.md rule 1.
  C  OUTCOME / POSTHOC / MODEL     W1 §5.2-5.3: distinct codes, because a code
                                   reused for two causes sends an operator to
                                   the wrong place (outcome.py docstring).
  D  weekly_rosters.status         W1 §5.2 VERIFIED: ACT -> 0.9715 snap rate,
                                   INA -> 0 of 3,438. The measured post-hoc trap.
  E  the purpose distinction       Directive 3 §7: archival material may remain
                                   quarantined; ARCHIVE and DESCRIPTIVE must
                                   still pass, or the module is just a delete.
  F  unregistered source           Class A: undeclared is not thereby clean.
  G  empty column set              Class A: an empty read is a missing read, not
                                   a permitted one. MLB shipped 7,926 rows with
                                   every meaningful column blank.
  H  completeness census           Class C (declaration drift): the same rule in
                                   two places, disagreeing, with nothing
                                   comparing them. THIS SECTION FAILS TODAY --
                                   see the DEFECT-Q labels.
  I  load-bearing                  Class E: assert_batch_games_are_new passed on
                                   every input it was ever given. A test that
                                   would still pass with the guard deleted is
                                   testing nothing.

Run standalone:  python3.12 nfl/tests/test_quarantine.py
"""
import pathlib
import re
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import importlib  # noqa: E402

from nfl.ingest.allowlist import (QUARANTINE, Category, Purpose,  # noqa: E402
                                  assert_columns_allowed,
                                  forecast_safe_columns, quarantined_columns)
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


# --- the authorities this test checks the module against --------------------
# Transcribed from nfl/research/W1_DATA_PROVENANCE.md, which is committed and
# marks each list `VERIFIED`. The test also asserts each name still appears in
# that file, so a change on either side shows up here rather than silently.
W1_PATH = _REPO / 'nfl' / 'research' / 'W1_DATA_PROVENANCE.md'

# W1 §5.1, line 639: "VERIFIED: 8 columns, 285/285 populated for 2024 -- and
# 112/272 already populated for the unplayed 2026 season."
W1_SCHEDULES_MARKET = (
    'away_moneyline', 'home_moneyline', 'spread_line', 'away_spread_odds',
    'home_spread_odds', 'total_line', 'under_odds', 'over_odds',
)

# W1 §5.2: everything in `schedules` that leaks, other than the market columns.
W1_SCHEDULES_OUTCOME = ('away_score', 'home_score', 'result', 'total', 'overtime')
W1_SCHEDULES_POSTHOC = (
    'away_qb_id', 'home_qb_id', 'away_qb_name', 'home_qb_name',   # 0/272 in 2026
    'referee',                                                    # 0/272 in 2026
    'temp', 'wind',            # observed game-time conditions, not a forecast
    'gsis', 'nfl_detail_id', 'pff', 'ftn',   # presence discloses it was played
)

# W1 §5.3, lines 675-681: "VERIFIED: 31 columns in pbp are outputs of fitted
# models". Enumerated here so a quarantine that lost an entry is visible.
W1_PBP_MODEL_DERIVED = (
    'no_score_prob', 'opp_fg_prob', 'opp_safety_prob', 'opp_td_prob', 'fg_prob',
    'safety_prob', 'td_prob', 'extra_point_prob', 'two_point_conversion_prob',
    'ep', 'epa', 'air_epa', 'yac_epa', 'comp_air_epa', 'comp_yac_epa', 'wp',
    'def_wp', 'home_wp', 'away_wp', 'wpa', 'cp', 'cpoe', 'success', 'qb_epa',
    'xyac_epa', 'xyac_mean_yardage', 'xyac_median_yardage', 'xyac_success',
    'xyac_fd', 'xpass', 'pass_oe',
)

# Real pbp columns that are NOT quarantined and are the intended feature space.
CLEAN_PBP = ('game_id', 'play_id', 'posteam', 'defteam', 'down', 'ydstogo',
             'yardline_100', 'qb_dropback', 'air_yards', 'yards_gained')


def _is(o, state, code):
    return isinstance(o, Outcome) and o.state is state and o.code == code


# ---------------------------------------------------------------------------
def test_compliant_read_passes():
    print('\nA. a compliant FORECAST read is allowed, and says so with a value')
    o = assert_columns_allowed('pbp', CLEAN_PBP, Purpose.FORECAST)
    check('clean pbp columns clear FORECAST', _is(o, State.PASS, 'COLUMNS_ALLOWED'),
          str(o))
    check('and the PASS carries the columns, not a bare True',
          o.state is State.PASS and list(o.value) == list(CLEAN_PBP), repr(o.value))
    check('a compliant schedules read also passes',
          _is(assert_columns_allowed('schedules', ['game_id', 'week', 'roof'],
                                     Purpose.FORECAST),
              State.PASS, 'COLUMNS_ALLOWED'))
    # Guarding against the inverse defect: a guard that refuses everything is
    # not a working guard either, it is an outage.
    check('injuries and depth_charts are registered and pass clean columns',
          _is(assert_columns_allowed('injuries', ['gsis_id', 'report_status'],
                                     Purpose.FORECAST), State.PASS,
              'COLUMNS_ALLOWED')
          and _is(assert_columns_allowed('depth_charts',
                                         ['gsis_id', 'pos_rank'],
                                         Purpose.FORECAST), State.PASS,
                  'COLUMNS_ALLOWED'))


def test_market_column_reaching_a_forecast_is_refused():
    print('\nB. SEEDED VIOLATION -- the sportsbook inside the "neutral" feed')
    for src, col in (('pbp', 'spread_line'), ('pbp', 'total_line'),
                     ('pbp', 'vegas_wp'), ('schedules', 'away_moneyline'),
                     ('schedules', 'over_odds')):
        o = assert_columns_allowed(src, [*CLEAN_PBP[:3], col], Purpose.FORECAST)
        check(f'{src}.{col} refused MARKET_COLUMN_ACCESS',
              _is(o, State.FAIL, 'MARKET_COLUMN_ACCESS'), str(o))
    o = assert_columns_allowed('pbp', ['spread_line', 'down'], Purpose.FORECAST)
    check('the refusal names the offending column, not just a count',
          o.evidence.get('columns') == ['spread_line'], str(o.evidence))
    check('and cites the rule rather than only the code',
          'rule 1' in o.detail, o.detail[:80])
    check('a FAIL cannot be read as truthy by `if result:`',
          _raises_truthiness(o))


def _raises_truthiness(o):
    try:
        bool(o)
        return False
    except Exception:
        return True


def test_each_leak_class_gets_its_own_code():
    print('\nC. SEEDED VIOLATIONS -- outcome, post-hoc and model-derived are '
          'distinguishable without reading English')
    cases = (('pbp', 'result', 'OUTCOME_COLUMN_ACCESS'),
             ('pbp', 'home_score', 'OUTCOME_COLUMN_ACCESS'),
             ('schedules', 'away_qb_id', 'POSTHOC_COLUMN_ACCESS'),
             ('pbp', 'epa', 'MODEL_DERIVED_COLUMN_ACCESS'),
             ('pbp', 'cpoe', 'MODEL_DERIVED_COLUMN_ACCESS'),
             ('pbp', 'xpass', 'MODEL_DERIVED_COLUMN_ACCESS'))
    for src, col, code in cases:
        o = assert_columns_allowed(src, ['down', col], Purpose.FORECAST)
        check(f'{src}.{col} -> {code}', _is(o, State.FAIL, code), str(o))
    codes = {c for _, _, c in cases}
    check('the four classes have four distinct codes',
          len(codes | {'MARKET_COLUMN_ACCESS'}) == 4, str(codes))

    print('     -- and a request violating several classes reports all of them')
    o = assert_columns_allowed('pbp', ['spread_line', 'result', 'epa', 'down'],
                               Purpose.FORECAST)
    check('the most serious class leads the code',
          _is(o, State.FAIL, 'MARKET_COLUMN_ACCESS'), str(o))
    av = o.evidence.get('all_violations', {})
    check('while every other violated class survives in the evidence',
          av.get('OUTCOME') == ['result'] and av.get('MODEL_DERIVED') == ['epa'],
          str(av))


def test_weekly_rosters_status_specifically():
    print('\nD. SEEDED VIOLATION -- weekly_rosters.status, the measured trap '
          '(ACT -> 0.9715 snap rate, INA -> 0 of 3,438)')
    o = assert_columns_allowed('weekly_rosters', ['gsis_id', 'week', 'status'],
                               Purpose.FORECAST)
    check('status is refused POSTHOC_COLUMN_ACCESS',
          _is(o, State.FAIL, 'POSTHOC_COLUMN_ACCESS'), str(o))
    check('and the other roster columns are not collaterally condemned',
          o.evidence.get('columns') == ['status'], str(o.evidence))
    check('status alone is refused too (not only in company)',
          _is(assert_columns_allowed('weekly_rosters', ['status'],
                                     Purpose.FORECAST),
              State.FAIL, 'POSTHOC_COLUMN_ACCESS'))
    check('a roster read without status is allowed -- the debt blocks exactly '
          'what it should',
          _is(assert_columns_allowed('weekly_rosters',
                                     ['gsis_id', 'week', 'team'],
                                     Purpose.FORECAST),
              State.PASS, 'COLUMNS_ALLOWED'))


def test_the_purpose_distinction_is_the_point():
    print('\nE. the SAME columns are allowed under ARCHIVE and DESCRIPTIVE '
          '(Directive 3 §7) -- a quarantine is a boundary, not a delete')
    worst = ['spread_line', 'result', 'epa', 'away_qb_id', 'total_line']
    for purpose in (Purpose.ARCHIVE, Purpose.DESCRIPTIVE):
        for src in ('pbp', 'schedules'):
            o = assert_columns_allowed(src, worst, purpose)
            check(f'{src} under {purpose.value} passes everything',
                  _is(o, State.PASS, 'COLUMNS_ALLOWED'), str(o))
            check(f'{src} under {purpose.value} drops nothing',
                  o.state is State.PASS and list(o.value) == worst,
                  repr(o.value))
    check('weekly_rosters.status is archivable',
          _is(assert_columns_allowed('weekly_rosters', ['status'],
                                     Purpose.ARCHIVE),
              State.PASS, 'COLUMNS_ALLOWED'))
    check('and the same call under FORECAST still refuses -- the purpose, not '
          'the column, is what changed',
          _is(assert_columns_allowed('weekly_rosters', ['status'],
                                     Purpose.FORECAST),
              State.FAIL, 'POSTHOC_COLUMN_ACCESS'))
    check('the recorded purpose rides in the evidence, so an audit can tell '
          'which one was claimed',
          assert_columns_allowed('pbp', ['spread_line'], Purpose.ARCHIVE
                                 ).evidence.get('purpose') == 'ARCHIVE')


def test_an_unregistered_source_is_not_thereby_clean():
    print('\nF. SEEDED VIOLATION -- a source with no declaration')
    for src in ('no_such_source', 'nflverse_pbp_v2', 'player_stats_2099', ''):
        o = assert_columns_allowed(src, ['anything'], Purpose.FORECAST)
        check(f'{src!r} BLOCKED/SOURCE_NOT_REGISTERED',
              _is(o, State.BLOCKED, 'SOURCE_NOT_REGISTERED'), str(o))
    o = assert_columns_allowed('no_such_source', ['x'], Purpose.FORECAST)
    check('the block declares a GOVERNANCE cause, not a data or network one',
          o.evidence.get('cause') == 'GOVERNANCE', str(o.evidence))
    check('and it says undeclared is not clean',
          'not thereby clean' in o.detail, o.detail[:90])


def test_an_empty_column_list_is_a_failure():
    print('\nG. SEEDED VIOLATION -- the empty read (Class A)')
    for empty in ([], (), iter(()), set()):
        o = assert_columns_allowed('pbp', empty, Purpose.FORECAST)
        check(f'{type(empty).__name__} column set -> FAIL/EMPTY_COLUMN_SET',
              _is(o, State.FAIL, 'EMPTY_COLUMN_SET'), str(o))
    check('an empty read is refused under ARCHIVE too -- emptiness is not a '
          'purpose-dependent property',
          _is(assert_columns_allowed('pbp', [], Purpose.ARCHIVE),
              State.FAIL, 'EMPTY_COLUMN_SET'))
    check('an empty read on an UNREGISTERED source still fails rather than '
          'passing vacuously',
          assert_columns_allowed('made_up_source', [], Purpose.FORECAST
                                 ).state is State.FAIL)


def test_the_quarantine_map_is_complete():
    print('\nH. CENSUS -- every column the committed provenance audit marked as '
          'leaking must be in the map (Class C, declaration drift)')
    w1 = W1_PATH.read_text() if W1_PATH.exists() else ''
    check('the provenance audit this census is measured against exists',
          len(w1) > 10000, f'{W1_PATH} is {len(w1)} bytes')

    sch = QUARANTINE['schedules']
    missing_mkt = [c for c in W1_SCHEDULES_MARKET
                   if sch.get(c) is not Category.MARKET]
    check('all 8 W1-VERIFIED schedules market columns are quarantined as MARKET',
          not missing_mkt, f'missing/miscategorised: {missing_mkt}')
    check('and there are exactly 8 -- no silent widening either',
          sum(1 for v in sch.values() if v is Category.MARKET) == 8,
          str(sorted(c for c, v in sch.items() if v is Category.MARKET)))
    check('every one of them still appears in W1 as a market column',
          all(c in w1 for c in W1_SCHEDULES_MARKET))

    missing_out = [c for c in W1_SCHEDULES_OUTCOME
                   if sch.get(c) is not Category.OUTCOME]
    check('all 5 W1 schedules outcome columns are quarantined as OUTCOME',
          not missing_out, f'missing: {missing_out}')

    pbp = QUARANTINE['pbp']
    missing_mkt_pbp = [c for c in ('spread_line', 'total_line', 'vegas_wp',
                                   'vegas_wpa', 'vegas_home_wp')
                       if pbp.get(c) is not Category.MARKET]
    check('the market columns re-stamped onto all 49,492 pbp rows are '
          'quarantined in pbp as well as in schedules',
          not missing_mkt_pbp, f'missing: {missing_mkt_pbp}')

    # ---- the two failing checks. Reported, not worked around. --------------
    missing_model = [c for c in W1_PBP_MODEL_DERIVED
                     if pbp.get(c) is not Category.MODEL_DERIVED]
    gate = {c: assert_columns_allowed('pbp', [c], Purpose.FORECAST).state.value
            for c in missing_model}
    check('DEFECT-Q1  all 31 W1 §5.3 VERIFIED model-derived pbp columns are '
          'quarantined',
          not missing_model,
          f'{len(missing_model)} NOT quarantined: {missing_model}. The gate '
          f'itself clears every one of them for FORECAST use today: {gate}. '
          f'qb_epa is availability 1.0000 on dropbacks (W2 line 122) and is '
          f'exactly what a QB model reaches for.')

    src = (_REPO / 'nfl' / 'ingest' / 'allowlist.py').read_text()
    m = re.search(r'All (\d+) fitted columns', src)
    claimed = int(m.group(1)) if m else -1
    actual = sum(1 for v in pbp.values() if v is Category.MODEL_DERIVED)
    from nfl.ingest.allowlist import N_QUARANTINED_MODEL_DERIVED
    import inspect as _inspect
    import nfl.ingest.allowlist as _al
    _src = _inspect.getsource(_al)
    _prose_counts = re.findall(r'[Aa]ll (\d+) fitted columns', _src)
    check('DEFECT-Q2  the count is no longer written in prose at all',
          not _prose_counts,
          f'prose still claims a count of {_prose_counts}. An earlier version '
          f'said "all 45" over a tuple of 41 while W1 said 31 -- three copies, '
          f'three numbers, nothing comparing them (Class C).')
    check('DEFECT-Q2  the derived constant tracks the map it is derived from',
          N_QUARANTINED_MODEL_DERIVED == len(_al._PBP_MODEL),
          f'{N_QUARANTINED_MODEL_DERIVED} vs {len(_al._PBP_MODEL)}')

    missing_ph = [c for c in W1_SCHEDULES_POSTHOC
                  if sch.get(c) is not Category.POSTHOC]
    gate_ph = {c: assert_columns_allowed('schedules', [c],
                                         Purpose.FORECAST).state.value
               for c in missing_ph}
    check('DEFECT-Q3  every W1 §5.2 schedules post-hoc column is quarantined',
          not missing_ph,
          f'{len(missing_ph)} NOT quarantined: {missing_ph}, and the gate '
          f'clears each for FORECAST use: {gate_ph}. W1 measures every one at '
          f'0/272 for the unplayed 2026 season, and calls temp/wind "observed '
          f'game-time conditions, not a forecast" -- a totals model would take '
          f'them straight from the archive.')


def test_helpers_do_not_open_a_side_door():
    print('\nH2. the convenience helpers must not be weaker than the gate')
    check('quarantined_columns returns a copy -- mutating it cannot edit the '
          'quarantine',
          _mutation_is_contained())
    safe = forecast_safe_columns('pbp', ['down', 'spread_line', 'epa', 'ydstogo'])
    check('forecast_safe_columns filters a registered source',
          safe == ['down', 'ydstogo'], str(safe))
    # DEFECT-Q4, now fixed: the sibling helper used QUARANTINE.get(source, {})
    # and returned every column of an unregistered source -- spread_line
    # included -- as forecast-safe, silently contradicting the gate, which
    # BLOCKS the same case. It now refuses. Refusing is stronger than filtering:
    # a caller cannot mistake a raise for an empty quarantine.
    leaked = None
    try:
        leaked = forecast_safe_columns('no_such_source',
                                       ['spread_line', 'total_line', 'x'])
        refused = False
    except KeyError:
        refused = True
    check('DEFECT-Q4  forecast_safe_columns treats an UNREGISTERED source the '
          'same way the gate does (as undeclared, not as clean)',
          refused,
          f'it returned {leaked} as forecast-safe. assert_columns_allowed '
          f'BLOCKS the same source with SOURCE_NOT_REGISTERED; a sibling that '
          f'silently declares every column safe -- including the closing line '
          f'-- is two functions in one module giving opposite answers.')


def _mutation_is_contained():
    got = quarantined_columns('pbp')
    got.pop('spread_line', None)
    got['down'] = Category.MARKET
    return (QUARANTINE['pbp'].get('spread_line') is Category.MARKET
            and 'down' not in QUARANTINE['pbp'])


def test_the_quarantine_is_load_bearing():
    print('\nI. LOAD-BEARING -- bypass the guard and these detections must '
          'disappear (Directive 3 §8, Class E)')

    def run_market():
        m = importlib.import_module('nfl.ingest.allowlist')
        return m.assert_columns_allowed('pbp', ['down', 'spread_line'],
                                        m.Purpose.FORECAST)

    def run_status():
        m = importlib.import_module('nfl.ingest.allowlist')
        return m.assert_columns_allowed('weekly_rosters', ['status'],
                                        m.Purpose.FORECAST)

    # 1. the gate function itself replaced by a permissive stub.
    _load_bearing(
        'the market refusal comes from assert_columns_allowed',
        run=run_market, attr='assert_columns_allowed',
        caught=lambda o: _is(o, State.FAIL, 'MARKET_COLUMN_ACCESS'),
        returns=Outcome.ok('STUB_ALLOWED', value=['down', 'spread_line']))

    # 2. the DATA, not just the function: drop the pbp entries and the same
    #    call must stop refusing. This is what proves the map earns its place.
    _load_bearing(
        'and from the pbp entries in QUARANTINE, not from the code shape',
        run=run_market, attr='QUARANTINE',
        caught=lambda o: _is(o, State.FAIL, 'MARKET_COLUMN_ACCESS'),
        replacement={'pbp': {}})

    # 3. same, for the one column with a measured leak rate behind it.
    _load_bearing(
        'the weekly_rosters.status refusal comes from its quarantine entry',
        run=run_status, attr='QUARANTINE',
        caught=lambda o: _is(o, State.FAIL, 'POSTHOC_COLUMN_ACCESS'),
        replacement={'weekly_rosters': {}})


def _load_bearing(label, *, run, attr, caught, returns=None, replacement=None):
    try:
        assert_guard_is_load_bearing(run=run, module_path='nfl.ingest.allowlist',
                                     attr=attr, caught=caught, returns=returns,
                                     replacement=replacement)
        check(label, True)
    except AssertionError as exc:
        check(label, False, str(exc)[:200])


if __name__ == '__main__':
    test_compliant_read_passes()
    test_market_column_reaching_a_forecast_is_refused()
    test_each_leak_class_gets_its_own_code()
    test_weekly_rosters_status_specifically()
    test_the_purpose_distinction_is_the_point()
    test_an_unregistered_source_is_not_thereby_clean()
    test_an_empty_column_list_is_a_failure()
    test_the_quarantine_map_is_complete()
    test_helpers_do_not_open_a_side_door()
    test_the_quarantine_is_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
