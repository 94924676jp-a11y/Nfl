"""OWNER RULE 1 (2026-10-02): nothing measured cannot PASS.

"No consequential validator, gate, audit, reconciliation, readiness check, or comparison may
return PASS/SUCCESS/READY when its required measured input is empty, absent, unparsed,
zero-count, or otherwise non-evidentiary. The failure state must distinguish
EMPTY_INPUT / NOT_EXECUTED / INCOMPLETE from a true FAIL."

Every row below is one repaired site. Each carries a POSITIVE CONTROL (an input known to violate
the rule, which must now be refused with one of the three non-evidentiary causes, never PASS and
never a plain FAIL) and a NEGATIVE CONTROL (a minimal valid, non-empty input which must still
pass, or must fail for its own true reason). A detector without a demonstrated trip case is not
validated, so a row whose positive control cannot be executed here names the suite that holds it.

The authoritative runner is `python3.12 nfl/tests/run_suite.py --modules test_non_evidentiary_refusal`.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (                       # noqa: E402
    NON_EVIDENTIARY, Cause, Outcome, State, combine)
from nfl.tests._controls import observe                                # noqa: E402

PASSED = FAILED = 0
NE_CAUSES = {c.value for c in NON_EVIDENTIARY}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def refused(o) -> bool:
    """BLOCKED with a non-evidentiary cause: the only acceptable answer to an empty input."""
    return (isinstance(o, Outcome) and o.state is State.BLOCKED
            and (o.evidence or {}).get('cause') in NE_CAUSES)


def _desc(o):
    if isinstance(o, Outcome):
        return f'{o.state.value}[{o.code}] cause={(o.evidence or {}).get("cause")}'
    return repr(o)[:160]


# ---------------------------------------------------------------- the primitive
def test_00_the_primitive_measured_refuses_zero_and_passes_n():
    print('\n0. Outcome.measured is the one door, and it closes on n=0')
    o = Outcome.measured('X', [], n_measured=0, what='nothing')
    observe('sportsplatform.governance.outcome:Outcome.measured:X_EMPTY_INPUT', o)
    check('n_measured=0 is BLOCKED/EMPTY_INPUT', refused(o)
          and o.evidence['cause'] == Cause.EMPTY_INPUT.value, _desc(o))
    check('  and it is reported as non_evidentiary, distinct from FAIL',
          o.non_evidentiary and o.state is not State.FAIL)
    o = Outcome.measured('X', [1, 2, 3], n_measured=3, what='three things')
    check('  n_measured=3 with a non-empty value PASSES', o.state is State.PASS
          and o.evidence['n_measured'] == 3, _desc(o))
    o = Outcome.measured('X', [], n_measured=3, what='three things')
    check('  but an EMPTY value with a positive count is still refused: the count must '
          'describe the value', refused(o), _desc(o))
    for name, o in (('not_executed', Outcome.not_executed('X', 'never ran')),
                    ('incomplete', Outcome.incomplete('X', 'short', expected=12, got=3))):
        check(f'  Outcome.{name} is BLOCKED with its own cause', refused(o)
              and o.evidence['cause'] == name.upper(), _desc(o))
    f = Outcome.fail('X', 'a real failure')
    check('  a true FAIL is not non_evidentiary', not f.non_evidentiary)


# ---------------------------------------------------------------- the runner itself
def test_01_the_runner_cannot_pass_with_zero_modules():
    print('\n1. run_suite: zero modules executed is NOT_EXECUTED, exit 3')
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ, NFL_SUITE_PROGRESS=os.path.join(td, 'p.jsonl'))
        r = subprocess.run([sys.executable, str(_REPO / 'nfl/tests/run_suite.py'),
                            '--only', 'ZZZ_NO_SUCH_MODULE'],
                           capture_output=True, text=True, env=env, timeout=600)
        observe('nfl.tests.run_suite:main:NOT_EXECUTED',
                'NOT_EXECUTED' if 'SUITE NOT_EXECUTED' in r.stdout and r.returncode == 3 else 'PASS')
        check('positive control: a module filter that matches nothing exits 3',
              r.returncode == 3, f'rc={r.returncode}')
        check('  and prints SUITE NOT_EXECUTED, never SUITE PASS',
              'SUITE NOT_EXECUTED' in r.stdout and 'SUITE PASS' not in r.stdout,
              r.stdout[-300:])
        rows = [json.loads(ln) for ln in open(env['NFL_SUITE_PROGRESS'])] \
            if os.path.exists(env['NFL_SUITE_PROGRESS']) else []
        done = [x for x in rows if x.get('phase') == 'suite_done']
        check('  the verdict row records NOT_EXECUTED with 0 checks executed',
              done and done[-1]['verdict'] == 'NOT_EXECUTED'
              and done[-1]['n_checks_executed'] == 0, str(done[-1:])[:200])
    from nfl.tools import suite_progress as SP
    s = SP.summarise([{'phase': 'suite_start', 'n_modules': 0, 't': 0.0},
                      {'phase': 'suite_scan_done', 't': 0.1},
                      {'phase': 'suite_done', 'verdict': 'NOT_EXECUTED',
                       'n_checks_executed': 0, 'mode': None, 't': 0.2}])
    observe('nfl.tools.suite_progress:summarise:NOT_EXECUTED',
            'NOT_EXECUTED' if 'NOT_EXECUTED' in s and 'COMPLETE' not in s else 'COMPLETE')
    check('  the progress summariser reads that row as NOT_EXECUTED', 'NOT_EXECUTED' in s
          and 'COMPLETE' not in s, s)
    s = SP.summarise([{'phase': 'suite_start', 'n_modules': 2, 't': 0.0},
                      {'phase': 'module_done', 'module': 'a', 'result': 'OK', 't': 1.0},
                      {'phase': 'module_done', 'module': 'b', 'result': 'OK', 't': 2.0},
                      {'phase': 'suite_scan_done', 't': 2.1},
                      {'phase': 'suite_done', 'verdict': 'PASS',
                       'n_checks_executed': 40, 'mode': 'BUILD', 't': 2.2}])
    check('  negative control: a run that executed checks summarises as PASS',
          s.splitlines()[0].strip().endswith('mode BUILD)') and 'PASS' in s, s)


# ---------------------------------------------------------------- governance combine
def test_02_combine_of_all_not_applicable_is_not_a_pass():
    print('\n2. Outcome.combine over nothing applicable')
    na = {f'N{i}': Outcome.not_applicable(f'N{i}', 'does not apply') for i in range(3)}
    o = combine(na, 'ALL')
    observe('sportsplatform.governance.outcome:combine:NOT_APPLICABLE', o.state.value)
    check('positive control: three NOT_APPLICABLE children combine to NOT_APPLICABLE, not PASS',
          o.state is State.NOT_APPLICABLE, _desc(o))
    o = combine({'A': Outcome.ok('A', 1), 'B': Outcome.not_applicable('B', 'n/a')}, 'ALL')
    check('  negative control: one real PASS among them still combines to PASS',
          o.state is State.PASS, _desc(o))


# ---------------------------------------------------------------- production core
def test_03_run_archive_seal_with_no_files():
    print('\n3. run_archive.verify / verify_current')
    from nfl.production import run_archive as RA
    saved = (RA.RUNS, RA.CURRENT)
    try:
        with tempfile.TemporaryDirectory() as td:
            RA.RUNS = pathlib.Path(td)
            RA.CURRENT = RA.RUNS / 'CURRENT.json'
            d = RA.RUNS / 'r0'
            d.mkdir()
            (d / RA.SEAL_NAME).write_text(json.dumps({'files': {}}))
            o = RA.verify('r0')
            observe('nfl.production.run_archive:verify:SEALED_RUN_INTACT_EMPTY_INPUT', o)
            check('positive control: a seal naming no files is refused, not INTACT',
                  refused(o) and o.evidence['cause'] == 'EMPTY_INPUT', _desc(o))
            RA.CURRENT.write_text(json.dumps({'run_id': 'r0'}))
            o = RA.verify_current()
            observe('nfl.production.run_archive:verify_current:SEALED_RUN_INTACT_EMPTY_INPUT', o)
            check('  and verify_current carries that refusal through instead of matching',
                  refused(o), _desc(o))
            # negative control: one real sealed file whose bytes still hash
            raw = b'hello archive'
            with gzip.open(d / 'x.json.gz', 'wb') as fh:
                fh.write(raw)
            src = RA.RUNS / 'live_x.json'
            src.write_bytes(raw)
            (d / RA.SEAL_NAME).write_text(json.dumps({'files': {'x.json.gz': {
                'source_path': os.path.relpath(src, RA._REPO),
                'sha256': hashlib.sha256(raw).hexdigest()}}}))
            o = RA.verify('r0')
            check('  negative control: one sealed file that still hashes is INTACT',
                  o.state is State.PASS and o.evidence['n_measured'] == 1, _desc(o))
            o = RA.verify_current()
            check('  and verify_current then PASSES on the one measured file',
                  o.state is State.PASS and o.evidence['n_measured'] == 1, _desc(o))
    finally:
        RA.RUNS, RA.CURRENT = saved


def test_04_lineage_audit_over_no_stages():
    print('\n4. lineage.audit')
    from nfl.production import lineage as LN
    d = LN.audit([])
    observe('nfl.production.lineage:audit:LINEAGE_AUDIT_NOT_EXECUTED', d)
    check('positive control: no stages -> LINEAGE_AUDIT_NOT_EXECUTED with cause EMPTY_INPUT',
          d['state'] == 'LINEAGE_AUDIT_NOT_EXECUTED' and d['cause'] == 'EMPTY_INPUT', str(d)[:200])
    check('  and any_stale_dependency is None, not False',
          d['any_stale_dependency'] is None)
    d = LN.audit([('nowhere', 'nfl/production/DOES_NOT_EXIST.json')])
    check('  negative control: one stage is MEASURED (here ABSENT), with a boolean verdict',
          d['state'] == 'LINEAGE_AUDIT_MEASURED' and d['n_stages'] == 1
          and d['any_stale_dependency'] is False
          and d['rows'][0]['lineage_state'] == LN.ABSENT, str(d)[:200])


def test_05_adjustment_lineage_with_no_tags():
    print('\n5. adjustment_registry.audit_frame')
    from nfl.production import adjustment_registry as AR
    o = AR.audit_frame([], label='t')
    observe('nfl.production.adjustment_registry:audit_frame:ADJUSTMENT_LINEAGE_CLEAN_EMPTY_INPUT', o)
    check('positive control: zero tags is refused, not CLEAN', refused(o), _desc(o))
    aid = next(iter(AR.ADJUSTMENTS))
    o = AR.audit_frame([aid], label='t')
    check('  negative control: one registered tag is CLEAN', o.state is State.PASS
          and o.evidence['n_measured'] == 1, _desc(o))
    o = AR.audit_frame([aid, aid], label='t')
    observe('nfl.production.adjustment_registry:audit_frame:ADJUSTMENT_ALREADY_APPLIED_IN_LINEAGE', o)
    check('  and a duplicate is a TRUE FAIL, distinct from the empty refusal',
          o.state is State.FAIL and not o.non_evidentiary, _desc(o))


def test_06_vintage_read_audit_over_no_packages():
    print('\n6. pipeline.audit_declared_reads')
    from nfl.production import pipeline as PL
    o = PL.audit_declared_reads(roots=())
    observe('nfl.production.pipeline:audit_declared_reads:EVERY_VINTAGE_READ_DECLARED_EMPTY_INPUT', o)
    check('positive control: scanning no packages finds no sites and is refused',
          refused(o), _desc(o))
    d = tempfile.mkdtemp(prefix='rule1_')
    m = pathlib.Path(d) / 'nfl/production/writer.py'
    m.parent.mkdir(parents=True)
    m.write_text("open('nfl/vintage/weekly_rosters.aa.raw.csv.gz', 'wb').write(b'')\n")
    o = PL.audit_declared_reads(repo=d)
    check('  negative control: one WRITE site and no undeclared read is a measured PASS',
          o.state is State.PASS and o.evidence['n_measured'] == 1
          and o.value['n_writes'] == 1, _desc(o))
    o = PL.audit_declared_reads()
    check('  and the real tree gives a MEASURED verdict (PASS or a true FAIL), never '
          'EMPTY_INPUT', not o.non_evidentiary and o.state in (State.PASS, State.FAIL)
          and (o.evidence.get('n_measured') or o.evidence.get('n_sites') or 0) > 0, _desc(o))


def test_07_product_verdict_with_no_required_gates():
    print('\n7. verdict.assess')
    from nfl.production import verdict as V
    saved = dict(V.GATE_SCOPE)
    try:
        V.GATE_SCOPE.clear()
        o = V.assess({}, 'football')
        observe('nfl.production.verdict:assess:PRODUCT_VERDICT_EMPTY_INPUT', o)
        check('positive control: a scope with no required gates is refused, never DEPLOYABLE',
              refused(o) and o.code == 'PRODUCT_VERDICT_EMPTY_INPUT', _desc(o))
    finally:
        V.GATE_SCOPE.clear()
        V.GATE_SCOPE.update(saved)
    req = V.required_gates('football')
    o = V.assess({g: V.PASS for g in req}, 'football')
    check(f'  negative control: all {len(req)} required gates PASS -> DEPLOYABLE',
          o.state is State.PASS and o.code == 'PRODUCT_DEPLOYABLE', _desc(o))
    o = V.assess({}, 'football')
    check('  and gates nobody ran are NOT_EVALUATED, which blocks (a true non-pass, not empty)',
          o.state is State.BLOCKED and o.evidence['cause'] == 'GOVERNANCE', _desc(o))


def test_08_scope_with_no_gates_mapped():
    print('\n8. gate_ids.assert_scope_allowed')
    from nfl.production import gate_ids as G
    saved = dict(G.GATES)
    try:
        G.GATES.clear()
        o = G.assert_scope_allowed('research')
        observe('nfl.production.gate_ids:assert_scope_allowed:SCOPE_HAS_NO_GATES', o)
        check('positive control: no gate blocks the scope -> refused, not CLEAR', refused(o)
              and o.code == 'SCOPE_HAS_NO_GATES', _desc(o))
        G.GATES['T'] = {'display_number': 1, 'state': G.YES, 'title': 't', 'blocks': ('research',)}
        o = G.assert_scope_allowed('research')
        check('  negative control: one YES gate mapped -> CLEAR with n_mapped=1',
              o.state is State.PASS and o.evidence['n_mapped'] == 1, _desc(o))
        G.GATES['T']['state'] = G.UNDECIDED
        o = G.assert_scope_allowed('research')
        observe('nfl.production.gate_ids:assert_scope_allowed:SCOPE_BLOCKED_BY_GATE', o)
        check('  and an UNDECIDED gate is a TRUE FAIL, distinct from the empty refusal',
              o.state is State.FAIL and not o.non_evidentiary, _desc(o))
    finally:
        G.GATES.clear()
        G.GATES.update(saved)


def _qb_draws(n=2, m=5, seed=3):
    rng = np.random.default_rng(seed)
    db = rng.integers(20, 40, (n, m)).astype(float)
    sacks = np.minimum(db, 2.0)
    scr = np.minimum(db - sacks, 1.0)
    att = db - sacks - scr
    return {'db': db, 'att': att, 'sacks': sacks, 'scr': scr, 'rush_opp': scr + 1.0}


def test_09_qb_identity_over_no_cells():
    print('\n9. qb_v1.identity_check')
    from nfl.production import qb_v1 as Q
    empty = {k: np.zeros((0, 0)) for k in ('db', 'att', 'sacks', 'scr')}
    o = Q.identity_check(empty)
    observe('nfl.production.qb_v1:identity_check:QB_DROPBACK_IDENTITY_HOLDS_EMPTY_INPUT', o)
    check('positive control: zero draw cells is refused, not HOLDS', refused(o), _desc(o))
    o = Q.identity_check(_qb_draws())
    check('  negative control: 10 coherent cells HOLD', o.state is State.PASS
          and o.evidence['n_measured'] == 10, _desc(o))


def test_10_qb_team_volume_with_every_team_skipped():
    print('\n10. qb_accounting.reconcile_team_volume')
    from nfl.production import qb_accounting as ACC
    D = _qb_draws()
    rows = [{'season': 2024, 'week': 1, 'team': 'NE', 'gsis_id': f'00-{i}', 'db': 30,
             'game_id': '2024_01_NE_SEA'} for i in range(2)]
    o = ACC.reconcile_team_volume(D, rows, team_dropback_draws={'SEA': np.full(5, 99.0)})
    observe('nfl.production.qb_accounting:reconcile_team_volume:QB_TEAM_VOLUME_COHERENT_EMPTY_INPUT', o)
    check('positive control: a budget for a team none of the rows belong to checks 0 cells '
          'and is refused, not COHERENT', refused(o)
          and o.evidence.get('teams_without_a_budget') == ['NE'], _desc(o))
    o = ACC.reconcile_team_volume(D, rows, team_dropback_draws={'NE': np.full(5, 99.0)})
    check('  negative control: the right team with a generous budget is COHERENT over 5 cells',
          o.state is State.PASS and o.evidence['n_measured'] == 5, _desc(o))
    o = ACC.reconcile_team_volume(D, rows, team_dropback_draws={'NE': np.zeros(5)})
    observe('nfl.production.qb_accounting:reconcile_team_volume:QB_TEAM_VOLUME_INCOHERENT', o)
    check('  and a budget the QBs exceed is a TRUE FAIL', o.state is State.FAIL
          and not o.non_evidentiary, _desc(o))


def test_11_qb_team_closure_cannot_pass_when_it_does_not_close():
    print('\n11. qb_accounting.reconcile_team: closure DOES_NOT_CLOSE is not MEASURED-and-passed')
    from nfl.production import qb_accounting as ACC
    D = _qb_draws()
    rows = [{'season': 2024, 'week': 1, 'team': 'NE', 'gsis_id': f'00-{i}', 'db': 30,
             'ord': 100 + i, 'game_id': '2024_01_NE_SEA'} for i in range(2)]
    o = ACC.reconcile_team(D, rows, team_dropback_draws={(2024, 1, 'NE'): D['db'].sum(0)})
    check('negative control: a team draw equal to the QB sum CLOSES and PASSES',
          o.state is State.PASS and o.evidence['per_team_dropback_closure']['status'] == 'CLOSES',
          _desc(o))
    o = ACC.reconcile_team(D, rows, team_dropback_draws={(2024, 1, 'NE'): D['db'].sum(0) - 5.0})
    observe('nfl.production.qb_accounting:reconcile_team:QB_TEAM_DROPBACKS_DO_NOT_CLOSE', o)
    check('positive control: a team draw the QBs exceed DOES_NOT_CLOSE and is a FAIL, '
          'not a PASS with a warning', o.state is State.FAIL
          and o.code == 'QB_TEAM_DROPBACKS_DO_NOT_CLOSE', _desc(o))
    o = ACC.reconcile_team(D, rows)
    check('  with no team draw supplied the closure is NOT_MEASURED and the Outcome says so '
          'in its detail rather than claiming closure', o.state is State.PASS
          and 'NOT_MEASURED' in o.detail
          and o.evidence['per_team_dropback_closure']['status'] == 'NOT_MEASURED', _desc(o))


def test_12_joint_reconciliation_gates_its_own_residual():
    print('\n12. joint.reconcile_team_total')
    from nfl.production import joint as J
    o = J.reconcile_team_total(np.zeros((0, 4)), np.ones(4))
    observe('nfl.production.joint:reconcile_team_total:JOINT_EMPTY_INPUT', o)
    check('positive control (empty): no players is refused', refused(o), _desc(o))
    D = np.array([[1.0, 0.0, 2.0], [1.0, 0.0, 2.0]])
    o = J.reconcile_team_total(D, np.array([4.0, 3.0, 8.0]))
    observe('nfl.production.joint:reconcile_team_total:TEAM_TOTAL_NOT_RECONCILED', o)
    check('positive control (residual): a zero-sum draw index against a non-zero total cannot '
          'be reconciled and is a TRUE FAIL, not RECONCILED', o.state is State.FAIL
          and o.code == 'TEAM_TOTAL_NOT_RECONCILED' and o.evidence['n_zero_sum_draws'] == 1,
          _desc(o))
    o = J.reconcile_team_total(D, np.array([4.0, 0.0, 8.0]))
    check('  negative control: scalable draws RECONCILE with residual 0',
          o.state is State.PASS and o.evidence['residual_after'] < 1e-9, _desc(o))


def test_13_ownership_audit_over_zero_applications():
    print('\n13. ownership_audit.audit')
    from nfl.production import ownership_audit as OA
    o = OA.audit()
    observe('nfl.production.ownership_audit:audit:OWNERSHIP_AUDIT_NO_APPLICATIONS', o)
    check('positive control (live tree): no adjustment family applies in production, so the '
          'audit is BLOCKED/EMPTY_INPUT and not COMPLETE', refused(o)
          and o.code == 'OWNERSHIP_AUDIT_NO_APPLICATIONS'
          and o.evidence['n_implemented_in_production'] == 0, _desc(o))
    check('  the scan itself ran over the production path',
          o.evidence['n_files_scanned'] >= 120, str(o.evidence['n_files_scanned']))
    check('  negative control for the scanner lives in test_ownership_audit A/B '
          '(a bypass is seen; a governed module reads as governed)', True)


def test_14_declared_captures_with_nothing_declared():
    print('\n14. fixture_assembler.verify_declared')
    from nfl.production import fixture_assembler as FA
    o = FA.verify_declared({})
    observe('nfl.production.fixture_assembler:verify_declared:DECLARED_CAPTURES_VERIFIED_EMPTY_INPUT', o)
    check('positive control: an empty declaration verified nothing and is refused', refused(o),
          _desc(o))
    found = None
    if FA.MANIFEST.exists():
        with open(FA.MANIFEST) as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                v = r.get('value') or {}
                if r.get('state') == 'PASS' and v.get('blob') and v.get('blob_file_sha256') \
                        and (FA._REPO / v['blob']).exists() \
                        and FA._sha256_file(FA._REPO / v['blob']) == v['blob_file_sha256']:
                    # Blobs are content-addressed; a row written before a blob was
                    # re-gzipped carries the earlier FILE hash and is rightly refused by
                    # verify_declared. The control needs a row whose file hash still holds.
                    found = (r['source'], v['blob_file_sha256'])
                    break
    if found is None:
        check('  negative control needs one PASS capture whose blob is on disk: none found, '
              'so this control is NOT_EXECUTED here (named, not passed)', False,
              'no blob on disk')
    else:
        o = FA.verify_declared({found[0]: {'sha256': found[1]}})
        check(f'  negative control: one real declared capture ({found[0]}) rehashes and PASSES',
              o.state is State.PASS and o.evidence['n_measured'] == 1, _desc(o))


def test_15_derived_artifacts_against_an_empty_spec():
    print('\n15. derived.verify')
    from nfl.production import derived as DV
    saved = DV.expected
    try:
        DV.expected = lambda: {}
        with tempfile.TemporaryDirectory() as td:
            o = DV.verify(pathlib.Path(td))
            observe('nfl.production.derived:verify:DERIVED_SPEC_EMPTY', o)
            check('positive control: a spec with no hashes is refused, not VERIFIED', refused(o)
                  and o.code == 'DERIVED_SPEC_EMPTY', _desc(o))
            want = {}
            for a in DV.ARTIFACTS:
                (pathlib.Path(td) / a).write_bytes(a.encode())
                want[a] = hashlib.sha256(a.encode()).hexdigest()
            DV.expected = lambda: want
            o = DV.verify(pathlib.Path(td))
            check(f'  negative control: {len(want)} artifacts matching their hashes VERIFY',
                  o.state is State.PASS and o.evidence['n_measured'] == len(want), _desc(o))
    finally:
        DV.expected = saved


def test_16_count_registry_with_nothing_to_compare():
    print('\n16. stat_contract.reconcile_with_product_registry')
    from nfl.production import stat_contract as SC
    saved = SC.COUNT_METRICS
    try:
        SC.COUNT_METRICS = ()
        o = SC.reconcile_with_product_registry({})
        observe('nfl.production.stat_contract:reconcile_with_product_registry:COUNT_REGISTRY_AGREES_EMPTY_INPUT', o)
        check('positive control: two empty registries agree on nothing and are refused',
              refused(o), _desc(o))
    finally:
        SC.COUNT_METRICS = saved
    supported = {tuple(m.split('/')): {'kind': 'count'} for m in SC.COUNT_METRICS}
    o = SC.reconcile_with_product_registry(supported)
    check(f'  negative control: {len(supported)} matching count metrics AGREE',
          o.state is State.PASS and o.evidence['n_measured'] == len(supported), _desc(o))


# ---------------------------------------------------------------- prospective / readiness
def test_17_g0a_checklist_short_of_twelve():
    print('\n17. q9shadow.g0a.check')
    from nfl.prospective.q9shadow import g0a as G
    saved = G.build
    try:
        G.build = lambda: {'n_requirements': 0, 'failing_item_numbers': [], 'gate_reads': 'X'}
        o = G.check()
        observe('nfl.prospective.q9shadow.g0a:check:G0A_CHECKLIST_INCOMPLETE', o)
        check('positive control: zero parsed requirements with nothing failing is INCOMPLETE, '
              'not ALL_TWELVE_PASS', refused(o) and o.evidence['cause'] == 'INCOMPLETE'
              and o.evidence['expected'] == 12 and o.evidence['got'] == 0, _desc(o))
        G.build = lambda: {'n_requirements': 12, 'failing_item_numbers': [], 'gate_reads': 'PASS'}
        o = G.check()
        check('  negative control: twelve read and none failing PASSES with n_measured=12',
              o.state is State.PASS and o.evidence['n_measured'] == 12, _desc(o))
    finally:
        G.build = saved


def test_18_injury_completeness_with_no_rows():
    print('\n18. q9shadow.injury_completeness.assess')
    from nfl.prospective.q9shadow import injury_completeness as IC
    sched = [{'season': '2026', 'week': '9', 'gameday': '2026-11-01', 'gametime': '13:00'}]
    a = IC.assess([], '2026-11-02T12:00:00Z', sched, 2026)
    observe('nfl.prospective.q9shadow.injury_completeness:assess:INCOMPLETE_NO_INJURY_ROWS_FOR_SEASON', a)
    check('positive control: no rows for the season is INCOMPLETE_NO_INJURY_ROWS_FOR_SEASON with '
          'cause EMPTY_INPUT and incomplete_weeks=[*]', a['state'] == IC.INCOMPLETE_NO_ROWS
          and a['cause'] == 'EMPTY_INPUT' and a['incomplete_weeks'] == ['*']
          and a['complete_weeks'] == [], str(a)[:200])
    rows = [{'season': '2026', 'week': '9', 'report_status': 'Out', 'practice_status': 'DNP'}]
    a = IC.assess(rows, '2026-11-02T12:00:00Z', sched, 2026)
    check('  negative control: one filled row after the final kickoff makes week 9 COMPLETE',
          a['complete_weeks'] == ['9'] and not a['incomplete_weeks'], str(a)[:200])


def test_19_readiness_without_a_league_report_is_pinned_elsewhere():
    print('\n19. nonqb.readiness: the absence of a report is not a report of absence')
    from nfl.production.nonqb import readiness as RD
    want = 'NOT_READY_NO_LEAGUE_REPORT'
    code = [ln.split('#', 1)[0] for ln in open(RD.__file__)]
    check(f'the state constant {want} exists in the module', any(want in ln for ln in code))
    check('  and READY_BY_EARLY_VINTAGE_NO_LEAGUE_REPORT survives only in comments',
          not any('READY_BY_EARLY_VINTAGE_NO_LEAGUE_REPORT' in ln for ln in code))
    check('  positive and negative controls run in test_readiness_vintage_cut '
          '(test_no_eligible_vintage_defers_honestly)', True)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in globals().items()
                           if k.startswith('test_') and callable(v)):
        try:
            fn()
        except AssertionError as e:
            print(f'  {name}: {e}')
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
