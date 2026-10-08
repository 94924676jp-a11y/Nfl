"""Release classification (owner ruling 2026-10-08, modified Option B): showdown_run_guards.release_classification.

The absent QB-conditioned model is a disclosed limitation, not a blocker of a verified substitution; every other gate
stays mandatory; simulation accounting is never relabelled PASS. Includes R9's real blocker list and the real
accounting report written for R9.
"""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import showdown_run_guards as G  # noqa: E402

PASSED = FAILED = 0
QB = "FOOTBALL_MODEL_INCOMPLETE_QB_ENVIRONMENT ['QB_CHANGE_NOT_MODELLED TB:Jalon Daniels share 0.116']"
INC = {'status': 'INCOMPLETE_QB_ENVIRONMENT'}
COMP = {'status': 'COMPLETE_FOR_STARTERS'}
FAIL_ACC = {'status': 'FAIL', 'violated': {'TB:PASS_YDS_EQ_REC_YDS': 1993}}
PASS_ACC = {'status': 'PASS', 'violated': {}}


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print('  ok  ', msg)
    else:
        FAILED += 1
        print('  FAIL', msg)


def test_decisions():
    r = G.release_classification([QB], INC, FAIL_ACC)
    check(r['decision'] == 'PROVISIONAL' and not r['CERTIFIED'],
          'verified Daniels substitution, QB model absent, accounting FAIL -> PROVISIONAL, not certified')
    check(r['statuses']['SIMULATION_ACCOUNTING_VALID'] == 'FAIL', 'accounting FAIL stays FAIL')
    check(r['statuses']['QB_CONDITIONED_FORECAST_VALIDATED'] == 'NOT_VALIDATED', 'QB-conditioned model reported NOT_VALIDATED')
    check(any(x.startswith('SIMULATION_ACCOUNTING_FAIL') for x in r['disclosed_limitations'])
          and QB in r['disclosed_limitations'], 'both limitations are disclosed')
    check(G.release_classification([], COMP, PASS_ACC)['decision'] == 'READY',
          'READY (certified) only when every status passes and no QB change is unmodelled')
    check(G.release_classification([], COMP, FAIL_ACC)['decision'] == 'PROVISIONAL',
          'no QB change but accounting FAIL -> PROVISIONAL (applies to every slate, not only QB changes)')
    check(G.release_classification([], COMP, None)['statuses']['SIMULATION_ACCOUNTING_VALID'] == 'UNVERIFIED'
          and G.release_classification([], COMP, None)['decision'] == 'PROVISIONAL',
          'accounting not measured -> UNVERIFIED, never PASS, never READY')
    check(G.release_classification([], COMP, {'status': 'PASS?'})['statuses']['SIMULATION_ACCOUNTING_VALID'] == 'UNVERIFIED',
          'an unrecognised accounting status is UNVERIFIED')


def test_mandatory_gates_not_waived():
    for b in ('STARTERS_NOT_CONFIRMED (x)', 'INACTIVES_NOT_OFFICIALLY_VERIFIED_OR_PRECOMPUTE_MODE',
              'INPUTS_CHANGED_DURING_RUN [x]', 'UPLOAD_NOT_REPRODUCED a vs b rc=0', 'REPLAY_EXIT_NONZERO rc=17',
              'RUN_RECEIPT_ABSENT', 'CODE_NOT_COMMITTED [x]', 'SCENARIO_STATE_MISMATCH [x]', 'VERIFIER_VIOLATIONS 2',
              'UNCLASSIFIED_PLAYERS [x]', 'BLOCKED_PLAYERS [x]', 'FINAL_BOARD_ABSENT', 'REHEARSAL_NOT_LIVE (x)',
              'PROP_SEAL_FAILED (x)', 'FINAL_VERIFY_AFTER_KICKOFF', 'RUN_CONTEXT_ABSENT (x)'):
        r = G.release_classification([b, QB], INC, PASS_ACC)
        check(r['decision'] == 'NOT_READY' and b in r['mandatory_blockers'], f'{b.split()[0]} stays mandatory')
    r = G.release_classification(["FOOTBALL_MODEL_UNDETERMINED ['x']"], {'status': 'UNDETERMINED'}, PASS_ACC)
    check(r['decision'] == 'NOT_READY', 'a QB-environment check that could not run (UNDETERMINED) still blocks')
    r = G.release_classification([QB], INC, PASS_ACC, substitution_checked=False)
    check(r['decision'] == 'NOT_READY' and r['statuses']['PLAYER_SUBSTITUTION_VALID'] == 'UNVERIFIED',
          'a substitution the starter guard did not check is UNVERIFIED and blocks')
    r = G.release_classification(['SCENARIO_STATE_MISMATCH [STARTING_FLAG Jalon Daniels]', QB], INC, PASS_ACC)
    check(r['statuses']['PLAYER_SUBSTITUTION_VALID'] == 'FAIL', 'a starter-state mismatch fails the substitution')
    r = G.release_classification(['STARTERS_NOT_CONFIRMED (x)'], COMP, PASS_ACC)
    check(r['statuses']['PLAYER_SUBSTITUTION_VALID'] == 'PASS' and r['statuses']['DATA_AND_AVAILABILITY_VALID'] == 'FAIL',
          'unconfirmed starters are a DATA failure, not a substitution failure')


def test_r9_real():
    L = json.loads((_REPO / 'nfl/dfs/salaries/showdown_tb_dal/RUN_LEDGER_PRECOMPUTE_TBQB_DANIELS_R9.json').read_text())
    fv = next(s for s in L['steps'] if s['step'] == 'FINAL_VERIFY')
    acc = json.loads((_REPO / 'nfl/research/accounting/WORLD_ACCOUNTING_TB_DAL_DANIELS_R9.json').read_text())
    a = {'status': 'FAIL' if acc['VIOLATED'] else 'PASS', 'violated': acc['VIOLATED']}
    r = G.release_classification(fv['blockers'], INC, a)
    check(r['decision'] == 'NOT_READY' and r['mandatory_blockers'] == [b for b in fv['blockers'] if b.startswith('STARTERS')],
          'R9 as run (precompute, starters unconfirmed): NOT_READY on exactly STARTERS_NOT_CONFIRMED')
    r = G.release_classification([b for b in fv['blockers'] if not b.startswith('STARTERS')], INC, a)
    check(r['decision'] == 'PROVISIONAL' and r['statuses']['SIMULATION_ACCOUNTING_VALID'] == 'FAIL',
          'R9 with the starter confirmed would be PROVISIONAL, accounting FAIL disclosed')


if __name__ == '__main__':
    for t in (test_decisions, test_mandatory_gates_not_waived, test_r9_real):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
