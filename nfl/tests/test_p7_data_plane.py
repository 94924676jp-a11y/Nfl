#!/usr/bin/env python3.12
"""P7 data plane: bitemporal assertions, freshness, and the leak findings.

READ THIS BEFORE READING THE TALLY.

THIS FILE IS EXPECTED TO REPORT FAILURES AND THEY ARE NOT BREAKAGE.

Sections C1 and C2 are FAILING TESTS FOR MEASURED DEFECTS in modules P7 does
not own. They were written to fail. A green tally here would mean the defects
had been repaired by their owners, not that this file was wrong. Per the
project's first governing rule -- the goal is not a green checklist, it is to
make a false green hard to produce -- they are asserted rather than described.

    C1  CONFIRMED LEAK. `nfl/production/run_forecast.py:501` calls
        `qb_allocation.allocate(...)` with neither `kickoff_utc` nor
        `written_at`. `allocate` guards its depth chart with
            for label, bound in (('kickoff', kickoff_utc),
                                 ('written_at', written_at)):
                if bound and got and str(got) >= str(bound):
        so with both bounds None the guard body is unreachable and the run
        consumes whatever `captured_depth_chart()` globbed. Measured
        2026-09-15: that is `depth_charts.f66f0c2583dba463.reduced.csv.gz`,
        vendor publication instant 2026-09-14T13:53:31Z, which postdates 15 of
        the 16 week-1 kickoffs. Section C1b proves the guard is CORRECT when a
        caller arms it, so the defect is the wiring and not the check.

    C2  POSSIBLE LEAK / CONFIRMED ATTRIBUTION FAILURE.
        `nfl/production/team_volume_v1.coaches()` -- its own docstring: "a
        load-bearing prediction-time input" -- selects with
        `sorted(glob.glob(...))[-1]`, which is lexicographic sha order, not a
        clock and not even newest. Measured: it reads
        `schedules.fcaa2bb1adac5d67.csv.gz`, one of 48 of the 134 schedule
        blobs on disk that appear in NO manifest row. It therefore has no
        retrieval instant and cannot be placed against any cut. The columns it
        reads (team, coach) are not realised outcomes, so no post-kickoff
        CONTENT has been demonstrated to reach a forecast through it; the
        mechanism is unbounded and the file is unattributable.

Everything else in this file is expected to pass.

Run standalone:  python3.12 nfl/tests/test_p7_data_plane.py
"""
import ast
import datetime as dt
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.capture import bitemporal as BT                       # noqa: E402
from nfl.capture import coverage as COV                        # noqa: E402
from nfl.capture import freshness as FR                        # noqa: E402
from nfl.capture import registry as REG                        # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'

PASSED = FAILED = 0


def check(label, cond, extra=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'\n       {extra}' if extra else ''))


def _manifest_rows():
    if not MANIFEST.exists():
        return []
    return [json.loads(l) for l in MANIFEST.read_text().splitlines()
            if l.strip()]


# =====================================================================
# A. BITEMPORAL ASSERTIONS
# =====================================================================
def test_a_both_axes_are_required_and_distinguished():
    print('\nA. a fact carries when it was true AND when we learned it')
    ok = BT.Fact(subject='x', source='injuries',
                 learned_at='2026-09-08T16:06:25+00:00',
                 valid_from='2026-09-08T15:00:00+00:00')
    check('a fact with both axes passes', BT.assert_bitemporal(ok).state is State.PASS)

    none = BT.Fact(subject='x', source='injuries', learned_at=None)
    o = BT.assert_bitemporal(none)
    check('no transaction time is a FAIL, not a default',
          o.state is State.FAIL and o.code == 'NO_TRANSACTION_TIME', o.code)

    novalid = BT.Fact(subject='x', source='injuries',
                      learned_at='2026-09-08T16:06:25+00:00')
    o = BT.assert_bitemporal(novalid)
    check('no VALID time is DEFERRED, not FAIL -- a documented ceiling is not '
          'a broken record',
          o.state is State.DEFERRED and o.code == 'NO_VALID_TIME', o.code)

    impossible = BT.Fact(subject='x', source='injuries',
                         learned_at='2026-09-01T00:00:00+00:00',
                         valid_from='2026-09-08T00:00:00+00:00')
    o = BT.assert_bitemporal(impossible)
    check('learning a fact before it was true is refused by name',
          o.state is State.FAIL and o.code == 'LEARNED_BEFORE_VALID', o.code)


def test_a2_a_forecast_may_only_read_what_it_had_learned():
    print('\nA2. THE RULE: learned_at strictly before the cut')
    f = BT.Fact(subject='x', source='injuries',
                learned_at='2026-09-10T05:05:18+00:00')
    ko_ne_sea = '2026-09-10T00:20:00+00:00'
    o = BT.readable_at(f, ko_ne_sea)
    check('the capture that first carried report_status for NE@SEA is refused '
          'at that kickoff',
          o.state is State.FAIL and o.code == 'LEARNED_AFTER_CUT', o.code)
    check('and the refusal says how late it was',
          abs(o.evidence.get('lag_seconds', 0) - 17118.0) < 2.0,
          str(o.evidence.get('lag_seconds')))

    o2 = BT.readable_at(f, '2026-09-13T17:00:00+00:00')
    check('the same fact is readable for a Sunday kickoff three days later',
          o2.state is State.PASS and o2.code == 'READABLE_AT_CUT', o2.code)

    o3 = BT.readable_at(f, None)
    check('no cut refuses -- no cut is not an open cut',
          o3.state is State.BLOCKED
          and o3.code == 'BITEMPORAL_CUT_UNRESOLVED', o3.code)

    same = BT.readable_at(
        BT.Fact(subject='x', source='injuries',
                learned_at='2026-09-13T17:00:00+00:00'),
        '2026-09-13T17:00:00+00:00')
    check('learned AT the cut is not learned BEFORE it',
          same.state is State.FAIL, same.code)


def test_a3_a_daily_stamp_may_not_certify_an_intraday_kickoff():
    print('\nA3. the granularity trap')
    day = BT.Fact(subject='chart', source='depth_charts',
                  learned_at='2026-09-13',
                  learned_at_authority='vendor dt, daily')
    check('a bare date is recognised as DATE granularity',
          day.learned_granularity is BT.Granularity.DATE)
    o = BT.readable_at(day, '2026-09-13T17:00:00+00:00')
    check('a chart stamped with the game day cannot certify a kickoff that '
          'day -- refused, not read as midnight',
          o.state is State.BLOCKED
          and o.code == 'LEARNED_TIME_GRANULARITY_TOO_COARSE', o.code)
    o2 = BT.readable_at(day, '2026-09-15T00:15:00+00:00')
    check('the same stamp IS lawful once the whole day has closed',
          o2.state is State.PASS
          and o2.evidence.get('bound_used') == 'end of the learned DAY', o2.code)

    naive_string_comparison = str('2026-09-13') >= str(
        '2026-09-13T17:00:00+00:00')
    check('and the string comparison the existing depth-chart guard uses '
          'would have PASSED it -- which is why this is a module',
          naive_string_comparison is False,
          'if this ever becomes True the guard changed shape')


def test_a4_the_gate_refuses_an_empty_fact_set():
    print('\nA4. an empty check is not a clean check')
    o = BT.assert_forecast_reads_only_learned_before_cut([], '2026-09-13T17:00:00Z')
    check('an empty fact set is BLOCKED, never a vacuous PASS',
          o.state is State.BLOCKED and o.code == 'NO_FACTS_TO_JUDGE', o.code)


def test_a5_the_gate_fires_on_the_real_manifest():
    print('\nA5. the gate, on the real injuries series')
    facts = BT.facts_from_manifest(manifest_path=MANIFEST, source='injuries')
    check('the manifest yields injuries facts at all', len(facts) > 0,
          f'n={len(facts)}')
    o = BT.assert_forecast_reads_only_learned_before_cut(
        facts, '2026-09-10T00:20:00+00:00')
    check('handing every injuries capture to a NE@SEA-cut forecast is refused',
          o.state is State.FAIL
          and o.code == 'FORECAST_READS_FACT_LEARNED_AFTER_CUT', o.code)
    check('and it counts the violations rather than naming only the first',
          o.evidence.get('n_violations', 0) > 1,
          str(o.evidence.get('n_violations')))
    early = [f for f in facts
             if BT.readable_at(f, '2026-09-10T00:20:00+00:00').state is State.PASS]
    o2 = BT.assert_forecast_reads_only_learned_before_cut(
        early, '2026-09-10T00:20:00+00:00')
    check('the lawful subset passes the same gate',
          o2.state is State.PASS, o2.code)


# =====================================================================
# B. FRESHNESS
# =====================================================================
def test_b_the_budget_is_derived_and_never_invented():
    print('\nB. staleness budgets come from schedule.WINDOWS, not from here')
    b, why = FR.budget('official_inactives')
    check('an inactives-serving source gets the 80-minute inactives window',
          b == dt.timedelta(minutes=80), f'{b} / {why}')
    check('and it says where the number came from',
          'schedule.WINDOWS' in why, why)
    b2, why2 = FR.budget('injuries')
    check('a source that serves no kind gets NO budget, not a default',
          b2 is None and 'serves no capture kind' in why2, why2)
    b3, why3 = FR.budget('snap_counts')
    check('a watch-only source gets no budget either', b3 is None, why3)
    src = (_REPO / 'nfl' / 'capture' / 'freshness.py').read_text()
    check('and the module declares no hour or day constant of its own',
          'timedelta(hours=' not in src and 'timedelta(days=' not in src,
          'a literal duration in freshness.py would be a silent constant')


def test_b2_the_monitor_at_den_kc_measures_arrival_not_content():
    """WAS: "the halted executor shows up as STALE at DEN@KC". Both halves of
    that name were wrong, and the correction is the point of this test now.

    TASK ZERO established the executor was never halted -- that reading came
    from a stale remote-tracking ref. Real main captured through
    2026-09-15T13:06:52Z, and the last official_inactives capture before the
    DEN@KC window closed landed at 23:59:37Z. So the monitor reads FRESH, age
    6.9 minutes at kickoff, and it is RIGHT about what it measures.

    AND THE BYTES WERE EMPTY. Every one of those captures is the
    "Please check back soon for NFL Inactive Reports for this Season" page --
    D20. So this source is simultaneously FRESH and carrying nothing, which is
    D20's shape at the freshness layer: staleness is a FETCH_SUCCESS question
    (did bytes arrive recently) and says nothing about STRUCTURAL_VALIDITY (are
    there rows in them). See nfl/capture/evidence_layers.py.

    This test now pins that distinction rather than asserting the old premise.
    """
    print('\nB2. the monitor against the DEN@KC kickoff')
    row = FR.source_staleness('official_inactives', '2026-09-15T00:15:00+00:00',
                              manifest_path=MANIFEST)
    check('official_inactives reads FRESH at the DEN@KC kickoff -- the '
          'executor was never halted',
          row['verdict'] == FR.FRESH, str(row.get('verdict')))
    check('and the age is reported in the row, not just the verdict',
          row.get('age_minutes') is not None, str(row.get('age_minutes')))
    check('  FRESH here means bytes arrived recently and NOTHING about whether '
          'they carry rows -- those captures are all D20 empty pages',
          True)
    row2 = FR.source_staleness('official_transactions',
                               '2026-09-15T00:15:00+00:00',
                               manifest_path=MANIFEST)
    check('a source that has never been captured is NEVER_CAPTURED, which is '
          'not stale and not covered',
          row2['verdict'] == FR.NEVER, str(row2.get('verdict')))
    row3 = FR.source_staleness('snap_counts', '2026-09-15T00:15:00+00:00',
                               manifest_path=MANIFEST)
    check('a watch-only source is not graded against a kickoff at all',
          row3['verdict'] == FR.WATCH_ONLY, str(row3.get('verdict')))


def test_b3_the_monitor_refuses_an_empty_page_and_keeps_a_closed_vocabulary():
    print('\nB3. the monitor page')
    o = FR.monitor({}, manifest_path=MANIFEST)
    check('no kickoffs is BLOCKED, never an empty clean report',
          o.state is State.BLOCKED
          and o.code == 'NO_KICKOFFS_TO_MEASURE_AGAINST', o.code)
    ko = FR.kickoffs_from_week_plan(2026, 1)
    check('week-1 kickoffs resolve from the captured plan',
          ko.state is State.PASS and len(ko.value) == 16,
          f'{ko.code} n={len(ko.value) if ko.state is State.PASS else 0}')
    rep = FR.monitor(ko.value, manifest_path=MANIFEST)
    check('the page computes', rep.state is State.PASS, rep.code)
    check('every verdict is inside the closed vocabulary',
          all(r['verdict'] in FR.VERDICTS for r in rep.value))
    check('and STALE rows are findings the page still returns PASS for',
          rep.evidence['verdict_counts'].get(FR.STALE, 0) > 0,
          str(rep.evidence['verdict_counts']))


# =====================================================================
# C. THE LEAK FINDINGS.  C1 AND C2 ARE WRITTEN TO FAIL. SEE THE HEADER.
# =====================================================================
def _call_keywords(path, attr_chain):
    """Keyword names on every call to `attr_chain` in `path`."""
    tree = ast.parse(pathlib.Path(path).read_text())
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        parts, f = [], node.func
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
        if '.'.join(reversed(parts)).endswith(attr_chain):
            out.append((node.lineno, {k.arg for k in node.keywords}))
    return out


def test_c1_CONFIRMED_LEAK_depth_chart_guard_is_disarmed_by_its_caller():
    print('\nC1. CONFIRMED LEAK -- the depth-chart chronology guard never runs')
    calls = _call_keywords(_REPO / 'nfl' / 'production' / 'run_forecast.py',
                           'QA.allocate')
    check('run_forecast still calls QA.allocate', len(calls) >= 1,
          'if this fails the call moved and this finding needs re-measuring')
    for lineno, kw in calls:
        check(f'run_forecast.py:{lineno} arms the depth-chart chronology '
              f'guard by passing kickoff_utc or written_at',
              bool(kw & {'kickoff_utc', 'written_at'}),
              f'keywords passed: {sorted(kw)}. With both bounds None the '
              f'guard at qb_allocation.py:477 is `if bound and got and ...`, '
              f'so its body is unreachable and the run consumes the globbed '
              f'depth chart with no cut.')
    calls2 = _call_keywords(
        _REPO / 'nfl' / 'production' / 'nonqb' / 'engine_rehearsal.py',
        'QA.allocate')
    for lineno, kw in calls2:
        check(f'engine_rehearsal.py:{lineno} arms the same guard',
              bool(kw & {'kickoff_utc', 'written_at'}),
              f'keywords passed: {sorted(kw)}')


def test_c1b_the_guard_ITSELF_is_correct_when_a_caller_arms_it():
    print('\nC1b. the check is right; the wiring is the defect')
    from nfl.production.nonqb import qb_allocation as QA
    dc = QA.captured_depth_chart()
    check('a depth chart is globbed with no clock and no as_of at all',
          dc.state is State.PASS, dc.code)
    got = dc.evidence.get('retrieved_at')
    check('its evidence key is called retrieved_at but carries the VENDOR dt, '
          'not our retrieval instant -- a misnamed clock another reader will '
          'misuse',
          got is not None and str(got).startswith('2026-'), str(got))
    fired = bool(got) and str(got) >= str('2026-09-13T17:00:00+00:00')
    check('armed with a Sunday week-1 kickoff the guard WOULD refuse this '
          'chart', fired,
          f'dt={got} vs kickoff 2026-09-13T17:00:00+00:00')
    unarmed = [bool(b) and bool(got) and str(got) >= str(b)
               for b in (None, None)]
    check('and with both bounds None -- exactly what run_forecast passes -- '
          'it refuses nothing', not any(unarmed))


def test_c2_POSSIBLE_LEAK_a_prediction_time_input_reads_an_orphan_blob():
    print('\nC2. POSSIBLE LEAK -- an unattributable schedule blob')
    from nfl.production import team_volume_v1 as TV
    o = TV.coaches(2026, 1)
    check('coaches() resolves', o.state is State.PASS, o.code)
    snap = o.evidence.get('snapshot')
    blobs = {pathlib.Path((r.get('value') or {}).get('blob') or '').name
             for r in _manifest_rows()}
    check(f'the blob coaches() read ({snap}) has a manifest row, so it can be '
          f'placed against a cut',
          snap in blobs,
          f'{snap} appears in NO manifest row: no retrieved_at, no '
          f'provenance, no content attribution. 48 of 134 schedules blobs on '
          f'disk are in this state.')


def test_c3_REPAIRED_the_week_plan_no_longer_orders_by_filesystem_mtime():
    print('\nC3. REPAIRED by P7 -- coverage.load_week_plan')
    src = (_REPO / 'nfl' / 'capture' / 'coverage.py').read_text()
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree)
           if isinstance(n, ast.FunctionDef)}
    lwp = ast.dump(fns['load_week_plan'])
    check('load_week_plan itself no longer touches filesystem mtime',
          'st_mtime' not in lwp)
    nodes = [n for n in ast.walk(fns['_schedule_snapshots'])
             if isinstance(n, ast.Attribute) and n.attr == 'st_mtime']
    check('mtime survives as exactly one expression, the named fallback',
          len(nodes) == 1, f'{len(nodes)} st_mtime attribute nodes')
    o = COV.load_week_plan(2026, 1, manifest_path=MANIFEST)
    order = o.evidence.get('snapshot_order') or {}
    check('the plan is ordered on manifest transaction time',
          order.get('basis') == 'MANIFEST_RETRIEVED_AT', str(order.get('basis')))
    check('and it counts the orphan blobs rather than hiding them',
          order.get('n_orphan', 0) > 0, str(order.get('n_orphan')))
    check('the chosen snapshot is manifest-attributed',
          o.evidence.get('snapshot') in {
              pathlib.Path((r.get('value') or {}).get('blob') or '').name
              for r in _manifest_rows()}, str(o.evidence.get('snapshot')))
    bounded = COV.load_week_plan(2026, 1, manifest_path=MANIFEST,
                                 as_of='2026-09-08T00:00:00Z')
    check('an as_of bound selects an EARLIER snapshot, so the bound is real',
          bounded.evidence.get('snapshot') != o.evidence.get('snapshot'),
          f"{bounded.evidence.get('snapshot')} vs {o.evidence.get('snapshot')}")


# =====================================================================
# D. PART C -- IMMUTABLE PROSPECTIVE CAPTURE
# =====================================================================
def test_d_the_den_kc_inactives_window_is_still_empty():
    print('\nD. the DEN@KC inactives window closed unfilled and stays that way')
    lo = dt.datetime(2026, 9, 14, 22, 45, tzinfo=dt.timezone.utc)
    hi = dt.datetime(2026, 9, 15, 0, 5, tzinfo=dt.timezone.utc)
    inside = []
    for r in _manifest_rows():
        v = r.get('value') or {}
        t = v.get('retrieved_at') or (v.get('provenance') or {}).get(
            'retrieved_at')
        p = BT.parse(t)
        if p is not None and lo <= p <= hi:
            inside.append((r.get('source'), r.get('state'), t))
    # WAS: "zero manifest rows carry a retrieved_at inside the window".
    # FALSE. Eight official_inactives captures landed inside it, each declared
    # before its fetch, window-anchored, from the GitHub Actions workflow. The
    # window was ATTEMPTED and the source had nothing -- see D20. Asserting
    # zero attempts was asserting a stale premise, and it passed for four days.
    inside_inact = [r for r in inside if r[0] == 'official_inactives']
    check('the window was attempted -- captures DID land inside it',
          len(inside_inact) >= 8, f'{len(inside_inact)} found')
    check('  and they all passed the fetch layer',
          all(st == 'PASS' for _s, st, _t in inside_inact),
          str({st for _s, st, _t in inside_inact}))
    cov = COV.coverage(2026, 1, manifest_path=MANIFEST,
                       now=dt.datetime(2026, 9, 15, 12, tzinfo=dt.timezone.utc),
                       verify_artifacts=False)
    missed = [m for m in cov.evidence['missed_detail']
              if m['game_id'] == '2026_01_DEN_KC' and m['kind'] == 'inactives']
    check('the DEN@KC inactives target is still recorded MISSED',
          len(missed) == 1, str(len(missed)))
    check('with the window this brief names', missed and
          missed[0]['window_start_utc'].startswith('2026-09-14T22:45')
          and missed[0]['window_end_utc'].startswith('2026-09-15T00:05'),
          str(missed[0] if missed else None))
    # WAS 15 / 48. Two corrections compound, and both are corrections rather
    # than improvements: reconciliation with main brought 289 commits of
    # capture evidence this branch did not hold, and D20's repair then withdrew
    # credit from 15 inactives targets covered only by an empty landing page.
    # See nfl/research/v4/D20_COVERAGE_CORRECTION.md.
    check('the week tally is covered 28 / missed 35',
          (cov.evidence['covered'], cov.evidence['missed']) == (28, 35),
          f"{cov.evidence['covered']} / {cov.evidence['missed']}")


# =====================================================================
# E. P0 SCAN -- FORBIDDEN PREDICTIVE INPUTS
# =====================================================================
FORBIDDEN_TOKENS = ('hardrock', 'hard_rock', 'fantasycruncher',
                    'fantasy_cruncher', 'fantasypros')

# Modules the forecast actually runs through. Not every file in the tree: a
# grep over the whole repository would be tripped by the comparator tools,
# which are downstream of every seal and are allowed to name a book.
FORECAST_PATH = (
    'nfl/production/run_forecast.py',
    'nfl/production/nonqb/football_engine.py',
    'nfl/production/nonqb/layers.py',
    'nfl/production/nonqb/qb_allocation.py',
    'nfl/production/nonqb/readiness.py',
    'nfl/production/nonqb/inputs.py',
    'nfl/production/nonqb/vintage_selector.py',
    'nfl/production/team_volume_v1.py',
    'nfl/production/eligibility_gate.py',
    'nfl/capture/registry.py',
    'nfl/capture/coverage.py',
    'nfl/capture/availability.py',
    'nfl/capture/schedule.py',
    'nfl/capture/bitemporal.py',
    'nfl/capture/freshness.py',
)


# `registry.py` NAMES the book, in the DELIVERED table, in order to declare it
# forbidden. A scan that cannot tell a prohibition from a wiring would force
# the prohibition to be deleted to stay green, which is backwards.
_NAMING_IS_A_PROHIBITION = {'nfl/capture/registry.py'}

# Market and outcome columns. Naming one in a forecast-path module is the leak;
# naming the vendor is not, by itself.
MARKET_COLUMNS = ('over_odds', 'under_odds', 'spread_line', 'total_line',
                  'moneyline', 'no_vig', 'novig', 'closing_line')


def _columns_actually_read(path):
    """Column names this module READS, not ones it merely discusses.

    A substring scan cannot tell a reader from a written-down ceiling.
    `vintage_selector.FAMILIES['schedules']['ceiling']` names `spread_line` and
    `total_line` precisely to record that the committed blob carries them and
    that nothing reads them, and `coverage.load_week_plan` now says the same
    thing in its docstring. A scan that flagged those would push both toward
    deleting the warning to stay green.

    So this looks for a string used as a SUBSCRIPT KEY or as the argument of a
    `.get(...)` -- the two shapes a csv.DictReader row is read through.
    """
    out = set()
    tree = ast.parse(pathlib.Path(path).read_text())
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and isinstance(n.slice.value, str):
            out.add(n.slice.value.lower())
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'get' and n.args \
                and isinstance(n.args[0], ast.Constant) \
                and isinstance(n.args[0].value, str):
            out.add(n.args[0].value.lower())
    return out


def test_e_no_book_or_external_projection_is_wired_as_a_predictive_input():
    print('\nE. P0 scan -- Hard Rock and external projections')
    name_hits, col_hits = [], []
    for rel in FORECAST_PATH:
        p = _REPO / rel
        if not p.exists():
            continue
        low = p.read_text().lower()
        for tok in FORBIDDEN_TOKENS:
            if tok in low and rel not in _NAMING_IS_A_PROHIBITION:
                name_hits.append((rel, tok))
        for col in _columns_actually_read(p):
            if col in MARKET_COLUMNS:
                col_hits.append((rel, col))
    check('no forecast-path module names a sportsbook or an external '
          'projection vendor, except where it declares it forbidden',
          not name_hits, str(name_hits))
    check('and no forecast-path module names a market or odds column',
          not col_hits, str(col_hits))
    check('the prohibition it is exempted for is real',
          REG.forecast_eligible('hardrock_market_snapshot').code
          == 'DELIVERED_SOURCE_FORBIDDEN_AS_PREDICTIVE_INPUT')
    # And the stored Hard Rock snapshot must stay out of the import graph.
    readers = []
    for p in sorted((_REPO / 'nfl').rglob('*.py')):
        rel = str(p.relative_to(_REPO))
        if rel.startswith('nfl/tests/'):
            continue
        if 'hardrock_market_snapshot' in p.read_text():
            readers.append(rel)
    allowed = {'nfl/product/market_cdf.py', 'nfl/tools/market_comparison.py',
               'nfl/research/market_outcome_audit.py',
               'nfl/capture/registry.py'}
    check('the stored Hard Rock snapshot is named only by the downstream '
          'comparator modules and the declaration that forbids it',
          set(readers) <= allowed,
          f'unexpected readers: {sorted(set(readers) - allowed)}')


def test_e2_the_registry_does_not_yet_declare_every_stored_source():
    print('\nE2. registry completeness against the manifest')
    stored = {r.get('source') for r in _manifest_rows() if r.get('source')}
    undeclared = sorted(stored - REG.declared_sources())
    check('every source with a stored capture is declared somewhere',
          not undeclared,
          f'{undeclared} have manifest rows and no declaration at all.')
    fetched_only = sorted(stored - set(REG.BY_NAME))
    check('the two delivered sources are declared OUTSIDE the fetch registry, '
          'so no capture obligation is manufactured for an artifact with no '
          'endpoint',
          fetched_only == ['hardrock_market_snapshot',
                           'official_status_evidence'], str(fetched_only))
    o = REG.forecast_eligible('hardrock_market_snapshot')
    check('the book snapshot is declared FORBIDDEN as a predictive input',
          o.state is State.BLOCKED
          and o.code == 'DELIVERED_SOURCE_FORBIDDEN_AS_PREDICTIVE_INPUT',
          o.code)
    o2 = REG.forecast_eligible('injuries')
    check('and a FETCHED source refuses to answer the same question, because '
          'for it eligibility is a property of the cut',
          o2.state is State.DEFERRED
          and o2.code == 'ELIGIBILITY_IS_A_PROPERTY_OF_THE_CUT', o2.code)


if __name__ == '__main__':
    test_a_both_axes_are_required_and_distinguished()
    test_a2_a_forecast_may_only_read_what_it_had_learned()
    test_a3_a_daily_stamp_may_not_certify_an_intraday_kickoff()
    test_a4_the_gate_refuses_an_empty_fact_set()
    test_a5_the_gate_fires_on_the_real_manifest()
    test_b_the_budget_is_derived_and_never_invented()
    test_b2_the_monitor_at_den_kc_measures_arrival_not_content()
    test_b3_the_monitor_refuses_an_empty_page_and_keeps_a_closed_vocabulary()
    test_c1_CONFIRMED_LEAK_depth_chart_guard_is_disarmed_by_its_caller()
    test_c1b_the_guard_ITSELF_is_correct_when_a_caller_arms_it()
    test_c2_POSSIBLE_LEAK_a_prediction_time_input_reads_an_orphan_blob()
    test_c3_REPAIRED_the_week_plan_no_longer_orders_by_filesystem_mtime()
    test_d_the_den_kc_inactives_window_is_still_empty()
    test_e_no_book_or_external_projection_is_wired_as_a_predictive_input()
    test_e2_the_registry_does_not_yet_declare_every_stored_source()
    print(f'\n{PASSED} passed, {FAILED} failed')
    print('Sections C1 and C2 are WRITTEN TO FAIL against measured defects '
          'in modules P7 does not own. See the module docstring. Expected '
          'today: 3 failures -- 2 in C1, 1 in C2.')
    sys.exit(1 if FAILED else 0)
