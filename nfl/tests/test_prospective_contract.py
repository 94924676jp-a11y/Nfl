"""Tests for the prospective forecast contract, registries and NFL-1 guard.

These are the controls that stand between mined 2022-2025 evidence and a
promotion decision. They are tested as REFUSALS.
"""
import json, os, pathlib, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.prospective import artifact as A                         # noqa: E402
from nfl.prospective import registries as R                       # noqa: E402
from nfl.prospective import nfl1_readiness as N                   # noqa: E402
from nfl.tests.bypass import assert_guard_is_load_bearing         # noqa: E402

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1; print(f'  ok   {label}')
    else:
        FAILED += 1; print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


def art(**over):
    a = dict(game_id='2026_01_NE_SEA', kickoff_utc='2026-09-10T00:20:00Z',
             written_at='2026-09-09T22:00:00Z',
             source_captures=[dict(source='official_inactives', sha256='a' * 64,
                                   retrieved_at='2026-09-09T21:00:00Z')],
             model_arm='A', spec_hash='s' * 16, code_commit='c' * 40,
             seed_protocol='per-row', feature_set_hash='f' * 16,
             eligibility_verdict='PASS', player_ids=['p1'],
             team_ids=['NE', 'SEA'], distributions={'p1': {}},
             completeness='COMPLETE', contract_version=A.CONTRACT_VERSION)
    a.update(over)
    return a


def test_a_the_ordering_gate():
    print('\nA. retrieved_at <= written_at < kickoff')
    check('a well-formed artifact validates',
          A.validate(art()).state is State.PASS)
    o = A.validate(art(written_at='2026-09-10T00:20:00Z'))
    check('written AT kickoff is refused -- there is no grace period',
          o.state is State.FAIL and o.code == 'WRITTEN_AFTER_KICKOFF', o.code)
    o = A.validate(art(written_at='2026-09-10T01:00:00Z'))
    check('written after kickoff is refused', o.state is State.FAIL, o.code)
    o = A.validate(art(source_captures=[dict(source='inj', sha256='a' * 64,
                                             retrieved_at='2026-09-09T23:00:00Z')]))
    check('an input retrieved AFTER the forecast is false provenance and is '
          'refused',
          o.state is State.FAIL and o.code == 'INPUT_RETRIEVED_AFTER_FORECAST',
          o.code)
    o = A.validate(art(source_captures=[dict(source='inj',
                                             retrieved_at='2026-09-09T21:00:00Z')]))
    check('a capture with no sha256 is an unverifiable input and is refused',
          o.state is State.FAIL and o.code == 'CAPTURE_WITHOUT_EVIDENCE', o.code)
    o = A.validate(art(source_captures=[]))
    check('no captures at all is refused', o.state is State.FAIL, o.code)


def test_b_required_fields_and_arms():
    print('\nB. completeness and arm labelling')
    for f in ('spec_hash', 'code_commit', 'feature_set_hash', 'seed_protocol',
              'eligibility_verdict'):
        o = A.validate(art(**{f: None}))
        check(f'an artifact missing {f} is refused',
              o.state is State.FAIL and o.code == 'ARTIFACT_INCOMPLETE', o.code)
    o = A.validate(art(model_arm='D'))
    check('an unknown arm is refused -- an unlabelled forecast cannot be kept '
          'out of the wrong pool', o.state is State.FAIL, o.code)
    o = A.assert_arms_not_pooled([art(model_arm='A'), art(model_arm='B')])
    check('pooling arm A with arm B is REFUSED',
          o.state is State.FAIL and o.code == 'ARMS_POOLED', o.code)
    o = A.assert_arms_not_pooled([art(model_arm='C'), art(model_arm='C')])
    check('  a single arm is fine', o.state is State.PASS, o.code)
    check('arm A may consume no 2026 outcome at all',
          A.ARMS['A']['may_consume_2026_outcomes'] is False)
    check('  and arm C is documented as the weakest evidentiary status',
          'WEAKEST' in A.ARMS['C']['note'].upper())


def test_c_immutability():
    print('\nC. an artifact is immutable after written_at')
    a = art()
    check('an unchanged artifact is unchanged',
          A.assert_not_mutated(a, dict(a)).state is State.PASS)
    o = A.assert_not_mutated(a, art(spec_hash='z' * 16))
    check('editing it in place is REFUSED',
          o.state is State.FAIL and o.code == 'ARTIFACT_MUTATED', o.code)
    o = A.assert_not_mutated(a, art(spec_hash='z' * 16,
                                    written_at='2026-09-09T22:30:00Z',
                                    supersedes=A.artifact_id(a)))
    check('a NEW artifact naming what it supersedes is the lawful correction',
          o.state is State.PASS and o.code == 'ARTIFACT_SUPERSEDED', o.code)
    o = A.assert_not_mutated(a, art(spec_hash='z' * 16,
                                    supersedes=A.artifact_id(a)))
    check('  but reusing the ORIGINAL written_at is still a mutation',
          o.state is State.FAIL, o.code)


def test_d_benchmark_registry():
    print('\nD. benchmarks: projections are never training labels')
    b = R.BY_NAME['professional_projection_consensus']
    check('a professional projection is registered as benchmark-only',
          b.may_be_training_label is False)
    check('  and as having NO point-in-time capture',
          b.point_in_time_available is False)
    o = R.check_benchmark('professional_projection_consensus')
    check('  so it is DEFERRED as unavailable rather than quietly used',
          o.state is State.DEFERRED
          and o.code == 'BENCHMARK_UNAVAILABLE_PIT', o.code)
    import dataclasses as dc
    R.BY_NAME['_seed'] = dc.replace(b, name='_seed', captured_at='2026-01-01')
    try:
        o2 = R.check_benchmark('_seed')
        check('a final file given a captured_at is caught as a BACKFILL',
              o2.state is State.FAIL and o2.code == 'BACKFILLED_BENCHMARK', o2.code)
        R.BY_NAME['_seed2'] = dc.replace(b, name='_seed2',
                                         may_be_training_label=True)
        o3 = R.check_benchmark('_seed2')
        check('a projection marked as a training label is REFUSED',
              o3.state is State.FAIL
              and o3.code == 'PROJECTION_AS_TRAINING_LABEL', o3.code)
    finally:
        R.BY_NAME.pop('_seed', None); R.BY_NAME.pop('_seed2', None)
    for n in ('position_pool_mean', 'p4c_carry_allocation', 'ABC_MPR'):
        check(f'  {n} is registered and eligible',
              R.check_benchmark(n).state is State.PASS)


def test_e_candidate_registry():
    print('\nE. candidates: nothing promotes on mined data')
    for n, c in R.CANDIDATES.items():
        check(f'{n} is NOT promoted', c['promoted'] is False)
        check(f'  and may not promote on 2022-2025',
              c['may_promote_on_2022_2025'] is False)
        check(f'  and the registry check passes',
              R.check_candidate(n).state is State.PASS)
    check('ABC_MPR is the frozen prospective candidate',
          R.CANDIDATES['ABC_MPR']['status'] == 'FROZEN PROSPECTIVE CANDIDATE')
    check('ewma_hl1 is development-only and NOT frozen prospective',
          R.CANDIDATES['participation_ewma_hl1']['frozen_prospective'] is False)
    seeded = dict(R.CANDIDATES['ABC_MPR']); seeded['promoted'] = True
    R.CANDIDATES['_seed'] = seeded
    try:
        o = R.check_candidate('_seed')
        check('a candidate marked promoted by a registry edit is REFUSED -- '
              'promotion is an owner decision',
              o.state is State.FAIL
              and o.code == 'CANDIDATE_MARKED_PROMOTED', o.code)
        s2 = dict(R.CANDIDATES['ABC_MPR']); s2['may_promote_on_2022_2025'] = True
        R.CANDIDATES['_seed2'] = s2
        o2 = R.check_candidate('_seed2')
        check('  as is one declaring a mined-data promotion path',
              o2.state is State.FAIL
              and o2.code == 'MINED_DATA_PROMOTION_PATH', o2.code)
    finally:
        R.CANDIDATES.pop('_seed', None); R.CANDIDATES.pop('_seed2', None)


def test_f_nfl1_cannot_authorize_itself():
    print('\nF. NFL-1 -- the answer to question 8 must be NO')
    for basis in ('TESTS_PASSED', 'G0A_COMPLETE', 'SUITE_GREEN', None,
                  'CHECKLIST_DISCHARGED'):
        o = N.assert_no_auto_authorization(
            {'from': 'NOT AUTHORIZED', 'to': 'AUTHORIZED', 'basis': basis})
        check(f'basis {basis!r} cannot authorize NFL-1',
              o.state is State.FAIL
              and o.code == 'NFL1_AUTO_AUTHORIZATION_ATTEMPTED', o.code)
    o = N.assert_no_auto_authorization(
        {'from': 'NOT AUTHORIZED', 'to': 'AUTHORIZED',
         'basis': 'OWNER_DECISION', 'owner_decision_id': 'D-1'})
    check('only an explicit owner decision can', o.state is State.PASS, o.code)
    o = N.assert_no_auto_authorization(
        {'from': 'NOT AUTHORIZED', 'to': 'AUTHORIZED',
         'basis': 'OWNER_DECISION'})
    check('  and it must name the decision, not just claim one',
          o.state is State.FAIL, o.code)
    r = N.report()
    check('the readiness report answers question 8 with NO',
          r['q8_can_code_authorize_nfl1_without_owner'] == 'NO')
    check('  and reports G0A 11/12 from the structured state',
          r['current_gates']['G0A'] == '11/12', r['current_gates'])
    check('  and NFL-1 NOT AUTHORIZED',
          r['current_gates']['NFL_1'] == 'NOT AUTHORIZED')
    check('  and names the discharging event and its window',
          r['q5_discharging_event']['game'] == 'NE @ SEA'
          and '22:50' in r['q5_discharging_event']['acceptance_window_utc'])
    check('  and lists failure modes that would leave it undischarged',
          len(r['q6_failure_modes']) >= 4)


def test_g_no_artifact_claims_g0a_complete():
    print('\nG. no artifact asserts G0A is complete')
    o = N.assert_no_artifact_claims_12_of_12()
    check('the repository asserts no 12/12', o.state is State.PASS,
          str(o.evidence.get('examples'))[:200] if o.state is not State.PASS else '')
    # and the scan is not vacuous
    p = pathlib.Path(N._REPO) / 'nfl' / '_seeded_claim_test.md'
    p.write_text('G0A is 12/12.\n')
    try:
        o2 = N.assert_no_artifact_claims_12_of_12()
        check('  a seeded assertion IS caught, so the scan is not vacuous',
              o2.state is State.FAIL, o2.code)
    finally:
        p.unlink()
    check('  and the repository is clean again',
          N.assert_no_artifact_claims_12_of_12().state is State.PASS)
    # a REQUIREMENT is not a claim -- the first version of this guard cried wolf
    p.write_text('The gate requires 12/12 and G0A is 11/12.\n')
    try:
        o3 = N.assert_no_artifact_claims_12_of_12()
        check('  "the gate requires 12/12" is NOT flagged -- a guard that '
              'fires on every run is ignored', o3.state is State.PASS, o3.code)
    finally:
        p.unlink()


def test_h_guard_deletions():
    print('\nH. guard-deletion proofs')

    def run_auto():
        return N.assert_no_auto_authorization(
            {'from': 'NOT AUTHORIZED', 'to': 'AUTHORIZED',
             'basis': 'TESTS_PASSED'})
    assert_guard_is_load_bearing(
        run=run_auto, module_path='nfl.prospective.nfl1_readiness',
        attr='assert_no_auto_authorization',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value='AUTHORIZED'))
    check('H1 assert_no_auto_authorization is load-bearing -- bypassed, a '
          'passing test authorizes NFL-1', True)

    def run_pool():
        return A.assert_arms_not_pooled([art(model_arm='A'), art(model_arm='C')])
    assert_guard_is_load_bearing(
        run=run_pool, module_path='nfl.prospective.artifact',
        attr='assert_arms_not_pooled',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value='A'))
    check('H2 assert_arms_not_pooled is load-bearing -- bypassed, arm A and '
          'arm C are scored together', True)

    def run_late():
        return A.validate(art(written_at='2026-09-10T02:00:00Z'))
    assert_guard_is_load_bearing(
        run=run_late, module_path='nfl.prospective.artifact', attr='validate',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value={}))
    check('H3 artifact.validate is load-bearing -- bypassed, a forecast '
          'written after kickoff is accepted', True)


if __name__ == '__main__':
    test_a_the_ordering_gate()
    test_b_required_fields_and_arms()
    test_c_immutability()
    test_d_benchmark_registry()
    test_e_candidate_registry()
    test_f_nfl1_cannot_authorize_itself()
    test_g_no_artifact_claims_g0a_complete()
    test_h_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
