"""IMPLEMENTED != EXECUTED != TESTED != PROSPECTIVELY VALIDATED != PROMOTED.

WHAT THIS MODULE ASSERTS
========================
1. THE FIVE RUNGS ARE ESTABLISHED SEPARATELY. A module existing proves
   nothing; the trace reads each rung from a different source and never infers
   one from another.
2. A STAGE THAT DID NOT RUN IS NOT MARKED EXECUTED. feature_build is DEFERRED
   in the real run and must read NO.
3. MATCHING ON A SUCCESS CODE IS NOT THE SAME AS EXERCISING A REFUSAL. This
   is the distinction that makes the TESTED rung worth anything: a passing
   stage records no refusal code, so the only token available is its success
   code, and finding a test that names TEAM_ENVIRONMENT_OK shows the happy
   path ran -- not that the branch which stops a bad run has ever fired. The
   trace separates the two counts and says so.
4. A STAGE WITH NO TEST NAMING ITS CODE IS REPORTED, NOT ASSUMED WORKING.
5. THE TRACE STATES ITS OWN WEAKNESS: it is a text search over the test tree,
   not a coverage measurement, and a code mentioned in a comment would count.
6. A RUN WHOSE RECORDS CANNOT BE READ RAISES rather than producing an empty
   trace that looks like a clean one.
"""
import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.tools.trace_execution_path import TraceError, trace  # noqa: E402

PASSED = FAILED = BLOCKED = 0
RUN = pathlib.Path(_ROOT) / 'nfl' / 'research' / 'unsealed' / \
    '2026_03_ATL_GB' / '2fc4e9599f0889f1'


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def test_the_five_rungs_are_established_separately():
    if not RUN.is_dir():
        return blocked('ladder', f'{RUN} absent')
    t = trace(RUN)
    for rung in ('IMPLEMENTED', 'EXECUTED', 'TESTED',
                 'PROSPECTIVELY_VALIDATED', 'PROMOTED'):
        chk(f'{rung} is reported', rung in t['ladder'])
    chk('PROMOTED comes from the publication state, not from EXECUTED',
        t['ladder']['PROMOTED'] == str((t['publication'] or {}).get('state')))
    chk('and this run is not promoted',
        t['ladder']['PROMOTED'] == 'BLOCKED', t['ladder']['PROMOTED'])
    chk('executing every stage did not make it validated',
        t['ladder']['PROSPECTIVELY_VALIDATED'] in ('None', 'NOT_ESTABLISHED'),
        t['ladder']['PROSPECTIVELY_VALIDATED'])


def test_a_stage_that_did_not_run_is_not_executed():
    if not RUN.is_dir():
        return blocked('executed flag', f'{RUN} absent')
    t = trace(RUN)
    by = {r['stage']: r for r in t['stages']}
    fb = by.get('feature_build')
    chk('feature_build is present in the trace', fb is not None)
    chk('it is DEFERRED', fb['state'] == 'DEFERRED', str(fb['state']))
    chk('and is NOT marked executed', fb['executed'] is False)
    chk('the counts agree',
        t['n_executed'] + t['n_not_executed'] == t['n_stages'])
    chk('13 of 14 ran', (t['n_executed'], t['n_stages']) == (13, 14),
        f"{t['n_executed']}/{t['n_stages']}")


def test_success_code_matching_is_not_refusal_coverage():
    if not RUN.is_dir():
        return blocked('code kind', f'{RUN} absent')
    t = trace(RUN)
    kinds = {r['stage']: r['code_kind'] for r in t['stages']}
    chk('a BLOCKED stage carries a real refusal code',
        kinds['artifact_sealing'] == 'REFUSAL_CODE', kinds['artifact_sealing'])
    chk('a PASSing stage offers only a success code',
        kinds['qb_layer'] == 'SUCCESS_CODE_ONLY', kinds['qb_layer'])
    chk('the two are counted separately',
        'tested_on_success_code_only' in t)
    chk('and most matches are success-code only',
        len(t['tested_on_success_code_only']) >= 8,
        str(len(t['tested_on_success_code_only'])))
    qb = next(r for r in t['stages'] if r['stage'] == 'qb_layer')
    chk('the basis says the refusal branch is not thereby shown to fire',
        'refusal branch is NOT thereby shown to fire' in qb['tested_basis'])


def test_a_stage_with_no_test_is_reported_not_assumed():
    if not RUN.is_dir():
        return blocked('untested', f'{RUN} absent')
    t = trace(RUN)
    chk('untested stages are listed', isinstance(t['untested_stages'], list))
    chk('and the real run has some',
        len(t['untested_stages']) >= 1, str(t['untested_stages']))
    for r in t['stages']:
        if not r['tested']:
            chk(f"{r['stage']} says no test names its code",
                'NO test file names' in r['tested_basis'])
            chk(f"{r['stage']} does not claim it is broken",
                'weaker than saying' in r['tested_basis'])
            break


def test_the_trace_states_its_own_weakness():
    if not RUN.is_dir():
        return blocked('self-limits', f'{RUN} absent')
    t = trace(RUN)
    chk('the TESTED rung calls itself a text search',
        'not a coverage measurement' in t['ladder']['TESTED'])
    chk('and reports how many were real refusal codes',
        'REFUSAL code' in t['ladder']['TESTED'])


def test_evidence_and_wiring_are_carried():
    if not RUN.is_dir():
        return blocked('evidence', f'{RUN} absent')
    t = trace(RUN)
    chk('every frozen family is carried with its hash',
        len(t['evidence_families']) == 7
        and all(v['sha256'] for v in t['evidence_families'].values()),
        str(len(t['evidence_families'])))
    chk('the cutoff is carried', t['cutoff_utc'] == '2026-09-24T15:30:00Z')
    chk('the code commit is carried', bool(t['code_commit']))
    stages = t['stages']
    chk('each stage names its next consumer',
        all(r['next_consumer'] for r in stages[:-1]))
    chk('and the last has none', stages[-1]['next_consumer'] is None)
    cv = stages[0]
    chk('capture_validation records the families it consumed',
        len(cv['input_families']) >= 4, str(cv['input_families']))


def test_an_unreadable_run_raises():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            trace(tmp)
            chk('an empty run directory raises', False, 'it returned')
        except TraceError as e:
            chk('an empty run directory raises', 'is missing' in str(e))
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        (d / 'run_status.json').write_text(json.dumps({'stages': []}))
        (d / 'RUN_INPUT_CONTRACT.json').write_text(json.dumps({'entries': {}}))
        try:
            trace(d)
            chk('a run with no stages raises', False, 'it returned')
        except TraceError as e:
            chk('a run with no stages raises', 'no stages' in str(e))


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
