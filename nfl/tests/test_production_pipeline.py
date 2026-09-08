"""Production pipeline tests: the ten dry-run cases and the guards.

THE ADVERSARIAL CASES MUST FAIL, and fail with the RIGHT code. A pipeline that
refuses for the wrong reason is not safer than one that does not refuse.
"""
import argparse, json, os, pathlib, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production import run_forecast as RUN                    # noqa: E402
from nfl.production import authorization as AUTH                  # noqa: E402
from nfl.production import refusal as RF                          # noqa: E402
from nfl.production import pipeline as PL                         # noqa: E402
from nfl.production import joint as JT                            # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing         # noqa: E402
import numpy as np                                                # noqa: E402

PASSED = FAILED = 0
TMP = pathlib.Path(tempfile.mkdtemp())


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1; print(f'  ok   {label}')
    else:
        FAILED += 1; print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


def args(**over):
    d = dict(season=2026, week=1, game_id='2026_01_NE_SEA', arm='A',
             written_at='2026-09-09T22:00:00Z', out_dir=str(TMP),
             seed=20260908, dry_run=True, fixtures=None)
    d.update(over)
    return argparse.Namespace(**d)


def fx(**over):
    f = {
        'kickoff_utc': '2026-09-10T00:20:00Z',
        'source_hashes': {
            'official_inactives': {'sha256': 'a' * 64,
                                   'retrieved_at': '2026-09-09T21:00:00Z'},
            'schedules': {'sha256': 'b' * 64,
                          'retrieved_at': '2026-09-09T20:00:00Z'}},
        'players': [{'gsis_id': '00-0000001'}, {'gsis_id': '00-0000002'}],
        'team_ids': ['NE', 'SEA'],
        'distributions': {'00-0000001': {'targets': {'mean': 5.0}}},
    }
    f.update(over)
    return f


def run(a=None, f=None):
    return RUN.build(a or args(), f or fx())


# ==========================================================================
def test_1_normal_complete_run():
    print('\n1. a normal complete game')
    s = run()
    check('the run SEALS', s['status'] == 'SEALED', s['status'])
    check('  all fourteen stages executed',
          len(s['stages']) == len(PL.STAGES), len(s['stages']))
    check('  no refusals', s['n_refusals'] == 0, s['refusals'])
    check('  it is tagged as a dry run', s['dry_run'] is True)
    check('  and explicitly NOT prospective evidence',
          s['prospective_eligible'] is False)
    check('  publication is REFUSED even on a clean run',
          s['publication']['code'] == 'NFL1_NOT_AUTHORIZED',
          s['publication']['code'])
    p = TMP / s['run_id'] / 'forecast_artifact.json'
    check('  an immutable artifact was written', p.exists())
    check('  and a run status was persisted',
          (TMP / s['run_id'] / 'run_status.json').exists())


def test_2_qb_change():
    print('\n2. a game with a QB change')
    s = run(f=fx(players=[{'gsis_id': '00-0000001'}, {'gsis_id': '00-0000009'}],
                 qb={'starter_changed': True}))
    check('a QB change does not break the run', s['status'] == 'SEALED',
          s['status'])
    # The QB stage is no longer an audit-only placeholder. It carries the V1
    # spec, and the distinction the packet insists on -- baseline SELECTION
    # rather than model PROMOTION -- lives in the spec name and the return,
    # not in a stage string.
    from nfl.production import qb_v1 as _Q
    check('  and the QB stage records the real V1 spec version',
          any(r['spec_version'] == _Q.SPEC_VERSION
              for r in s['stages'] if r['stage'] == 'qb_layer'),
          [r['spec_version'] for r in s['stages'] if r['stage'] == 'qb_layer'])


def test_3_to_10_adversarial():
    print('\n3-10. the adversarial cases must fail, with the RIGHT code')
    cases = [
        ('3 player missing identity', fx(players=[{'name': 'X'}]),
         args(), 'IDENTITY_UNRESOLVED'),
        ('4 source timestamp too late',
         fx(source_hashes={'official_inactives':
                           {'sha256': 'a' * 64,
                            'retrieved_at': '2026-09-09T23:00:00Z'}}),
         args(), 'SOURCE_TOO_LATE'),
        ('5 missing raw artifact', fx(source_hashes={}), args(),
         'SOURCE_MISSING'),
        ('6 changed schema',
         fx(source_hashes={'official_inactives':
                           {'sha256': 'a' * 64, 'schema_ok': False,
                            'retrieved_at': '2026-09-09T21:00:00Z'}}),
         args(), 'SCHEMA_DRIFT'),
        ('7 incomplete player set', fx(players=[]), args(),
         'IDENTITY_UNRESOLVED'),
        ('8 joint reconciliation failure', fx(joint_fails=True), args(),
         'JOINT_RECONCILIATION_FAILURE'),
        ('9 arm A consuming 2026 outcomes',
         fx(consumes_2026_outcomes=True), args(arm='A'), 'ARM_RULE_VIOLATION'),
        ('10a artifact sealing failure', fx(sealing_fails=True), args(),
         'ARTIFACT_SEALING_FAILURE'),
        ('extra: raw hash mismatch',
         fx(source_hashes={'official_inactives':
                           {'sha256': 'a' * 64, 'expected_sha256': 'b' * 64,
                            'retrieved_at': '2026-09-09T21:00:00Z'}}),
         args(), 'RAW_HASH_MISMATCH'),
        ('extra: unauthorized input',
         fx(source_hashes={'some_vendor_feed':
                           {'sha256': 'a' * 64,
                            'retrieved_at': '2026-09-09T21:00:00Z'}}),
         args(), 'UNAUTHORIZED_INPUT'),
        ('extra: cold-start violation', fx(cold_start_identity_mismatch=True),
         args(), 'COLD_START_VIOLATION'),
        ('extra: model artifact missing', fx(participation_missing=True),
         args(), 'MODEL_ARTIFACT_MISSING'),
        ('extra: model hash mismatch', fx(td_hash_mismatch=True), args(),
         'MODEL_HASH_MISMATCH'),
        ('extra: stage not implemented', fx(qb_not_implemented=True), args(),
         'STAGE_NOT_IMPLEMENTED'),
        ('extra: incomplete accounting', fx(accounting_fails=True), args(),
         'INCOMPLETE_PLAYER_ACCOUNTING'),
        ('extra: written after kickoff',
         fx(kickoff_utc='2026-09-09T21:00:00Z'), args(),
         'SOURCE_CHRONOLOGY_FAILURE'),
    ]
    for name, f, a, want in cases:
        s = RUN.build(a, f)
        got = [r['refusal_code'] for r in s['stages'] if r['refusal_code']]
        check(f'{name} -> REFUSED with {want}',
              s['status'] == 'REFUSED' and want in got, f'{s["status"]} {got}')
        check(f'   and the refusal is persisted',
              (TMP / s['run_id'] / 'refusals.jsonl').exists())


def test_10b_artifact_rewrite_attempt():
    print('\n10b. an artifact rewrite attempt')
    from nfl.prospective import artifact as ART
    s = run()
    p = TMP / s['run_id'] / 'forecast_artifact.json'
    before = json.loads(p.read_text())
    after = dict(before, spec_hash='TAMPERED')
    o = ART.assert_not_mutated(before, after)
    check('rewriting a sealed artifact in place is REFUSED',
          o.state is State.FAIL and o.code == 'ARTIFACT_MUTATED', o.code)
    o2 = ART.assert_not_mutated(before, dict(
        after, written_at='2026-09-09T22:30:00Z',
        supersedes=ART.artifact_id(before)))
    check('  and the only lawful correction is a NEW artifact that supersedes',
          o2.state is State.PASS, o2.code)


def test_11_determinism_and_execution_identity():
    print('\n11. idempotency and execution identity')
    a, f = args(), fx()
    s1 = RUN.build(a, f)
    s2 = RUN.build(a, f)
    check('the same inputs give the same run_id', s1['run_id'] == s2['run_id'])
    check('  and the same execution identity',
          s1['execution_identity'] == s2['execution_identity'])
    p = TMP / s1['run_id'] / 'forecast_artifact.json'
    a1 = json.loads(p.read_text())
    s3 = RUN.build(a, f)
    a2 = json.loads((TMP / s3['run_id'] / 'forecast_artifact.json').read_text())
    check('  and a bit-identical artifact',
          json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True))
    f2 = fx()
    f2['source_hashes']['official_inactives']['sha256'] = 'c' * 64
    s4 = RUN.build(a, f2)
    check('changing ONE input hash changes the execution identity',
          s4['execution_identity'] != s1['execution_identity'])
    check('  and the run_id with it', s4['run_id'] != s1['run_id'])
    s5 = RUN.build(args(arm='B'), f)
    check('changing the ARM changes the execution identity',
          s5['execution_identity'] != s1['execution_identity'])
    s6 = RUN.build(args(seed=1), f)
    check('changing the SEED changes it too',
          s6['execution_identity'] != s1['execution_identity'])


def test_12_no_postgame_input_and_scoring_isolation():
    print('\n12. leakage and scoring isolation')
    o = PL.assert_no_postgame_inputs('feature_build', ['h_ewma', 'rec_td'])
    check('a stage declaring a postgame field is refused',
          o.state is State.FAIL and o.code == 'POSTGAME_INPUT_DECLARED', o.code)
    src = pathlib.Path(RUN.__file__).read_text()
    check('the entrypoint does not import the scoring engine as an input',
          'from nfl.scoring' not in src)
    s = run()
    sc = [r for r in s['stages'] if r['stage'] == 'scoring'][0]
    check('  and the scoring stage declares only draws as input',
          sc['state'] == 'PASS')
    check('written_at has NO wall-clock default -- it is a required argument',
          '--written-at' in src and 'required=True' in src)


def test_13_joint_production_baseline():
    print('\n13. the joint production baseline')
    D = np.array([[3., 4.], [2., 1.]]); T = np.array([10., 10.])
    o = JT.reconcile_team_total(D, T)
    check('team totals reconcile PER DRAW',
          np.allclose(o.value.sum(0), T), o.value.sum(0))
    check('  and the marginal shift it caused is MEASURED, not assumed absent',
          'marginal_mean_shift' in o.evidence)
    o2 = JT.enforce_possible({'receptions': np.array([9., 1.]),
                              'targets': np.array([5., 4.])})
    check('impossible combinations are corrected and COUNTED',
          o2.evidence['n_corrected'] == 1
          and o2.value['receptions'][0] == 5.0)
    o3 = JT.couple_through_volume(np.array([[.3, .4], [.2, .1]]),
                                  np.array([30., 40.]))
    check('players are coupled through a shared team volume per draw',
          np.allclose(o3.value, [[9., 16.], [6., 4.]]))
    check('unsupported dependence is left NEUTRAL and named',
          len(JT.NEUTRAL_COUPLINGS) >= 3
          and any('2024' in x for x in JT.NEUTRAL_COUPLINGS))
    o4 = JT.reconcile_team_total(np.array([[1.]]), np.array([1., 2.]))
    check('a shape mismatch is refused, not broadcast', o4.state is State.FAIL)


def test_14_authorization_guard():
    print('\n14. the authorization gate')
    o = AUTH.may_publish()
    check('publication is REFUSED while NFL-1 is NOT AUTHORIZED',
          o.state is State.BLOCKED and o.code == 'NFL1_NOT_AUTHORIZED', o.code)
    check('  and the gate state it read is G0A 11/12',
          AUTH.gate_state()['G0A'] == '11/12', AUTH.gate_state())
    check('computing is still allowed', AUTH.may_compute().state is State.PASS)
    o2 = RF.refuse('MADE_UP_CODE', 'x', 'y', 'r')
    check('an undeclared refusal code is refused -- it could not be audited',
          o2.state is State.FAIL and o2.code == 'UNKNOWN_REFUSAL_CODE', o2.code)
    # This asserted a magic number (17) and broke the moment a genuinely new
    # refusal was added. The property worth protecting is not the COUNT -- it
    # is that every code the production path actually raises is declared, so
    # every refusal can be audited. That is checked directly now, by reading
    # the source.
    import re as _re
    _src = ''
    for _f in ('run_forecast.py', 'pipeline.py', 'qb_v1.py',
               'qb_accounting.py', 'joint.py'):
        _p = pathlib.Path(RF.__file__).with_name(_f)
        if _p.exists():
            _src += _p.read_text()
    _used = set(_re.findall(r"refuse\(\s*'([A-Z0-9_]+)'", _src))
    _undeclared = sorted(_used - set(RF.REFUSALS))
    check('every refusal code raised in the production path is declared',
          not _undeclared, str(_undeclared))
    check('  and the registry is non-trivial', len(RF.REFUSALS) >= 17,
          len(RF.REFUSALS))


def test_15_guard_deletions():
    print('\n15. guard-deletion proofs')

    def run_auth():
        return AUTH.may_publish()
    assert_guard_is_load_bearing(
        run=run_auth, module_path='nfl.production.authorization',
        attr='may_publish',
        caught=lambda o: o.state is State.BLOCKED,
        returns=Outcome.ok('STUB', value='AUTHORIZED'))
    check('G1 may_publish is load-bearing -- bypassed, an unauthorized run '
          'reports publishable', True)

    def run_chrono():
        return RUN.build(args(), fx(source_hashes={
            'official_inactives': {'sha256': 'a' * 64,
                                   'retrieved_at': '2026-09-09T23:59:00Z'}}))
    assert_guard_is_load_bearing(
        run=run_chrono, module_path='nfl.production.refusal', attr='refuse',
        caught=lambda s: s['status'] == 'REFUSED',
        returns=Outcome.ok('STUB', value=None))
    check('G2 refusal.refuse is load-bearing -- bypassed, a source retrieved '
          'after written_at flows straight through to a sealed artifact', True)


if __name__ == '__main__':
    test_1_normal_complete_run()
    test_2_qb_change()
    test_3_to_10_adversarial()
    test_10b_artifact_rewrite_attempt()
    test_11_determinism_and_execution_identity()
    test_12_no_postgame_input_and_scoring_isolation()
    test_13_joint_production_baseline()
    test_14_authorization_guard()
    test_15_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
