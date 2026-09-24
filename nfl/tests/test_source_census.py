"""Shape detection that would have caught the ESPN cap on day one.

WHAT THIS MODULE ASSERTS
========================
1. A ONE-VALUED COUNT DISTRIBUTION OVER MANY CAPTURES IS FLAGGED. This is the
   whole detector and it needs no knowledge of any endpoint: a count that
   never varies across many captures of a changing world is a property of the
   container, not of the world. ESPN returned exactly 25 per club in 20,736
   of 20,736 club-entries across 648 captures while declaring success.
2. INVARIANCE IS NOT ASKED TOO EARLY. Two captures minutes apart agreeing is
   the expected behaviour of any feed, so below the declared floor the
   completeness axis is NOT_ESTABLISHED rather than either PASS or PARTIAL.
3. A VARYING FEED IS NOT FLAGGED. The detector must not fire on healthy data
   or it teaches people to ignore it.
4. AN EMPTY CENSUS RAISES and an all-zero feed is an error, not a measurement.
5. SCHEMA DRIFT AND COVERAGE GAPS ARE SEPARATE FINDINGS from truncation,
   because they call for different actions.
6. NO FINDINGS IS NOT A CLEAN BILL OF HEALTH, and the report says so itself.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import source_census as SC  # noqa: E402

PASSED = FAILED = BLOCKED = 0


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _capped(n_captures, n_entities=32, cap=25):
    return [{'capture_id': f'c{i}',
             'per_entity': {f'e{j}': cap for j in range(n_entities)},
             'schema': ['a', 'b']}
            for i in range(n_captures)]


def _varying(n_captures, n_entities=32):
    return [{'capture_id': f'c{i}',
             'per_entity': {f'e{j}': 3 + ((i * 7 + j) % 11)
                            for j in range(n_entities)},
             'schema': ['a', 'b']}
            for i in range(n_captures)]


def _codes(rep):
    return {f['code'] for f in rep['findings']}


def test_a_one_valued_count_distribution_is_flagged():
    rep = SC.census(_capped(60))
    chk('exactly one distinct per-entity count is observed',
        list(rep['distinct_per_entity_counts']) == [25],
        str(rep['distinct_per_entity_counts']))
    chk('invariance is reported', SC.ENTITY_COUNT_INVARIANT in _codes(rep))
    chk('and it is called suspected truncation',
        SC.SUSPECTED_TRUNCATION in _codes(rep))
    trunc = next(f for f in rep['findings']
                 if f['code'] == SC.SUSPECTED_TRUNCATION)
    chk('naming the suspected page size', trunc['page_size_suspected'] == 25)
    chk('and refusing the absence-is-absence reading',
        'not evidence of absence in the world' in trunc['detail'])
    axis = SC.completeness_axis(rep)
    chk('the completeness axis becomes PARTIAL', axis['state'] == 'PARTIAL')
    chk('carrying COVERAGE_NOT_ESTABLISHED',
        'COVERAGE_NOT_ESTABLISHED' in axis['detail'])


def test_invariance_is_not_asked_too_early():
    few = SC.census(_capped(SC.MIN_CAPTURES_FOR_INVARIANCE - 1))
    chk('below the floor, truncation is NOT asserted',
        SC.SUSPECTED_TRUNCATION not in _codes(few))
    axis = SC.completeness_axis(few)
    chk('and completeness is NOT_ESTABLISHED, not PASS',
        axis['state'] == 'NOT_ESTABLISHED', axis['state'])
    chk('the reason names the floor',
        str(SC.MIN_CAPTURES_FOR_INVARIANCE) in axis['detail'])
    at = SC.census(_capped(SC.MIN_CAPTURES_FOR_INVARIANCE))
    chk('exactly at the floor it IS asserted',
        SC.SUSPECTED_TRUNCATION in _codes(at))


def test_a_varying_feed_is_not_flagged():
    rep = SC.census(_varying(60))
    chk('no truncation finding on healthy data',
        SC.SUSPECTED_TRUNCATION not in _codes(rep), str(_codes(rep)))
    chk('no invariance finding either',
        SC.ENTITY_COUNT_INVARIANT not in _codes(rep))
    chk('completeness passes', SC.completeness_axis(rep)['state'] == 'PASS')
    chk('many distinct counts are observed',
        len(rep['distinct_per_entity_counts']) > 5)


def test_empty_and_zero_are_errors_not_measurements():
    try:
        SC.census([])
        chk('an empty census raises', False, 'it returned')
    except SC.CensusError as e:
        chk('an empty census raises',
            'not a clean bill of health' in str(e))
    zero = SC.census([{'capture_id': f'c{i}',
                       'per_entity': {'e0': 0, 'e1': 0}} for i in range(20)])
    chk('an all-zero feed is flagged', SC.EMPTY_CAPTURE in _codes(zero))
    chk('and its completeness FAILS',
        SC.completeness_axis(zero)['state'] == 'FAIL')


def test_schema_drift_and_coverage_gaps_are_separate_findings():
    obs = _varying(20)
    obs[-1]['schema'] = ['a', 'b', 'c']
    rep = SC.census(obs)
    chk('schema drift is its own finding', SC.SCHEMA_DRIFT in _codes(rep))
    chk('and is not confused with truncation',
        SC.SUSPECTED_TRUNCATION not in _codes(rep))

    obs2 = _varying(20)
    obs2[-1]['per_entity'].pop('e0')
    rep2 = SC.census(obs2)
    chk('a capture missing an entity is flagged',
        SC.ENTITY_COVERAGE_DROP in _codes(rep2))
    chk('reporting the per-capture entity range',
        len(rep2['entities_per_capture']) > 1)


def test_no_findings_is_not_a_clean_bill_of_health():
    rep = SC.census(_varying(60))
    chk('the state is NO_FINDINGS', rep['state'] == 'NO_FINDINGS')
    chk('and the report says so in its own words',
        'rather than that the feed is complete' in rep['reading'])


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
