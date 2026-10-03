"""OWNER RULE 1 (2026-10-02): nothing measured cannot PASS -- DFS, postgame, truth, schema,
governance and coordination sites.

"No consequential validator, gate, audit, reconciliation, readiness check, or comparison may
return PASS/SUCCESS/READY when its required measured input is empty, absent, unparsed,
zero-count, or otherwise non-evidentiary. The failure state must distinguish
EMPTY_INPUT / NOT_EXECUTED / INCOMPLETE from a true FAIL."

Every row below is one repaired site. Each carries a POSITIVE CONTROL (an input known to violate
the rule, which must now be refused with one of the three non-evidentiary causes, never PASS and
never a plain FAIL) and a NEGATIVE CONTROL (a minimal valid, non-empty input which must still
pass, or must fail for its own true reason). A detector without a demonstrated trip case is not
validated, so every positive control also records itself through `nfl.tests._controls.observe`
(OWNER RULE 2). The coordination rows run on TEMP COPIES of the queue, decision and log files,
never on the live ones.

The authoritative runner is
`python3.12 nfl/tests/run_suite.py --modules test_non_evidentiary_refusal_dfs_gov`.
"""
from __future__ import annotations

import copy
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
    NON_EVIDENTIARY, Cause, Outcome, State)
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


def refused_dict(d) -> bool:
    """The dict-returning shape of the same refusal: a named non-PASS state and a cause."""
    return (isinstance(d, dict) and d.get('state') not in (None, 'PASS', 'FAIL')
            and d.get('cause') in NE_CAUSES)


def _desc(o):
    if isinstance(o, Outcome):
        return f'{o.state.value}[{o.code}] cause={(o.evidence or {}).get("cause")}'
    return repr(o)[:160]


# ---------------------------------------------------------------- dfs history store
def test_01_dfs_completeness_of_nothing_held():
    print('\n1. dfs.history.store.assert_completeness')
    from nfl.dfs.history import store as ST, contracts as C
    d = ST.assert_completeness(n_entries_held=0, declared_field_size=0)
    observe('nfl.dfs.history.store:assert_completeness:DFS_COMPLETENESS_NOT_EXECUTED', d)
    check('positive control: 0 held against a declared field of 0 is NOT COMPLETE',
          d['completeness'] == C.COMPLETENESS_UNKNOWN and refused_dict(d)
          and d['state'] == 'DFS_COMPLETENESS_NOT_EXECUTED', str(d)[:200])
    d = ST.assert_completeness(n_entries_held=0, declared_field_size=None)
    check('  0 held with no declaration is the same refusal, not a mere UNKNOWN',
          refused_dict(d) and d['n_entries_held'] == 0, str(d)[:200])
    d = ST.assert_completeness(n_entries_held=4, declared_field_size=4)
    check('  negative control: 4 held against a declared 4 is COMPLETE',
          d['completeness'] == C.COMPLETE and 'cause' not in d, str(d)[:200])
    d = ST.assert_completeness(n_entries_held=2, declared_field_size=4)
    check('  and 2 against 4 is a TRUE INCOMPLETE, distinct from the empty refusal',
          d['completeness'] == C.INCOMPLETE and 'cause' not in d, str(d)[:200])


def test_02_dfs_archive_with_no_artifacts_to_rehash():
    print('\n2. dfs.history.store.rehydrate')
    from nfl.dfs.history import store as ST
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / ST.MANIFEST_NAME
        p.write_text(json.dumps({'artifacts': [], 'contest_key': 'DK:TEST',
                                 'manifest_hash': 'x'}))
        o = ST.rehydrate(p)
        observe('nfl.dfs.history.store:rehydrate:DFS_ARCHIVE_VERIFIED_EMPTY_INPUT', o)
        check('positive control: a manifest naming zero artifacts is refused, not VERIFIED',
              refused(o) and o.code == 'DFS_ARCHIVE_VERIFIED_EMPTY_INPUT'
              and o.evidence['n_measured'] == 0, _desc(o))
        raw = b'rank,entry\n1,a\n'
        f = pathlib.Path(td) / 'raw.csv'
        f.write_bytes(raw)
        p.write_text(json.dumps({
            'artifacts': [{'artifact_type': 'CONTEST_STANDINGS', 'stored_path': str(f),
                           'raw_sha256': hashlib.sha256(raw).hexdigest()}],
            'contest_key': 'DK:TEST', 'manifest_hash': 'x'}))
        o = ST.rehydrate(p)
        check('  negative control: one artifact that still hashes is VERIFIED with n_measured=1',
              o.state is State.PASS and o.evidence['n_measured'] == 1
              and o.value['n_verified'] == 1, _desc(o))
        f.write_bytes(raw + b'2,b\n')
        o = ST.rehydrate(p)
        check('  and a changed file is a TRUE FAIL, distinct from the empty refusal',
              o.state is State.FAIL and o.code == 'DFS_ARCHIVE_NOT_VERIFIABLE'
              and not o.non_evidentiary, _desc(o))


# ---------------------------------------------------------------- identity crosswalk
def test_03_crosswalk_gate_over_zero_entries():
    print('\n3. dfs.identity_crosswalk.assert_complete')
    from nfl.dfs import identity_crosswalk as IC
    got = None
    try:
        IC.assert_complete({'counts': {}, 'entries': []})
    except IC.CrosswalkError as e:
        got = e
    observe('nfl.dfs.identity_crosswalk:assert_complete:CROSSWALK_EMPTY_INPUT', got)
    check('positive control: an artifact with no entries raises CROSSWALK_EMPTY_INPUT, '
          'it does not return None (PASS)', got is not None
          and got.code == 'CROSSWALK_EMPTY_INPUT' and got.cause == 'EMPTY_INPUT', repr(got)[:160])
    one = {'counts': {'EXACT_WITHIN_TEAM': 1},
           'entries': [{'dk_name': 'A', 'resolution': 'EXACT_WITHIN_TEAM', 'gsis_id': '00-1'}]}
    check('  negative control: one resolved entry passes the gate (returns None)',
          IC.assert_complete(one) is None)
    bad = {'counts': {'UNRESOLVED_NO_MATCH': 1},
           'entries': [{'dk_name': 'A', 'resolution': 'UNRESOLVED_NO_MATCH', 'gsis_id': None}]}
    try:
        IC.assert_complete(bad)
        check('  and an unresolved entry is a TRUE refusal', False, 'it passed')
    except IC.CrosswalkError as e:
        check('  and an unresolved entry is a TRUE refusal, distinct from the empty one',
              e.code == 'CROSSWALK_INCOMPLETE' and e.cause not in NE_CAUSES, repr(e)[:120])


# ---------------------------------------------------------------- post-inactives package gates
def _run(stats, game_id='2026_02_DET_BUF', manifest=None):
    return {'game_id': game_id, 'stats': dict.fromkeys(stats, {}),
            'manifest': manifest or {'layers': {}}}


def _man(dk_rows, foot_rows):
    from nfl.dfs.salaries import build_postinactives_package as B
    layers = {'dk_scoring': {'row_ids': list(dk_rows), 'row_axis': 'gsis_id',
                             'metrics': ['dk_points']}}
    for ln in B.PLAYER_LAYERS:
        layers.setdefault(ln, {'row_ids': list(foot_rows),
                               'row_axis': 'gsis_id', 'metrics': ['yards']})
    return {'layers': layers}


def test_04_shared_draws_gate_over_no_dk_rows():
    print('\n4. build_postinactives_package.assert_shared_draws')
    from nfl.dfs.salaries import build_postinactives_package as B
    d = B.assert_shared_draws([])
    observe('nfl.dfs.salaries.build_postinactives_package:assert_shared_draws:DK_SHARED_DRAWS_EMPTY_INPUT', d)
    check('positive control: zero runs is refused, not "outputs share identical draws"',
          refused_dict(d) and d['code'] == 'DK_SHARED_DRAWS_EMPTY_INPUT'
          and d['n_dk_rows_checked'] == 0, str(d)[:200])
    d = B.assert_shared_draws([_run([], manifest=_man([], ['00-2']))])
    check('  a run whose DK-bearing layers carry no row_ids is the same refusal',
          refused_dict(d) and d['n_runs'] == 1 and d['n_dk_rows_checked'] == 0, str(d)[:200])
    d = B.assert_shared_draws([_run([], manifest=_man(['00-1', '00-2'], ['00-1', '00-2']))])
    check('  negative control: two backed DK rows PASS with n_dk_rows_checked=2',
          d['state'] == 'PASS' and d['n_dk_rows_checked'] == 2, str(d)[:200])
    d = B.assert_shared_draws([_run([], manifest=_man(['00-1', '00-2'], ['00-2']))])
    check('  and an unbacked DK row is a TRUE FAIL', d['state'] == 'FAIL'
          and d['code'] == 'DK_ROWS_NOT_BACKED_BY_FOOTBALL_DRAWS', str(d)[:200])


def test_05_inactive_gate_over_no_emitted_rows_or_unparsed_clubs():
    print('\n5. build_postinactives_package.assert_no_inactive_in_playable')
    from nfl.dfs.salaries import build_postinactives_package as B
    d = B.assert_no_inactive_in_playable([], {'BUF': ['00-1']}, {})
    observe('nfl.dfs.salaries.build_postinactives_package:assert_no_inactive_in_playable:INACTIVE_GATE_EMPTY_INPUT', d)
    check('positive control (empty): zero runs is refused, not "0 inactive players in board"',
          refused_dict(d) and d['code'] == 'INACTIVE_GATE_EMPTY_INPUT'
          and d['n_emitted_player_rows'] == 0, str(d)[:200])
    d = B.assert_no_inactive_in_playable([_run([])], {'BUF': ['00-1']}, {})
    check('  a run that emitted no player row is the same refusal',
          refused_dict(d) and d['n_runs'] == 1, str(d)[:200])
    d = B.assert_no_inactive_in_playable([_run(['00-1'], game_id='garbage')], {'BUF': ['00-1']}, {})
    observe('nfl.dfs.salaries.build_postinactives_package:assert_no_inactive_in_playable:INACTIVE_GATE_CLUBS_UNPARSED', d)
    check('positive control (unparsed): a game_id with no clubs is INCOMPLETE, not PASS',
          refused_dict(d) and d['cause'] == 'INCOMPLETE'
          and d['code'] == 'INACTIVE_GATE_CLUBS_UNPARSED'
          and d['unparsed_game_ids'] == ['garbage'], str(d)[:200])
    d = B.assert_no_inactive_in_playable([_run(['00-2'])], {'BUF': ['00-1']}, {})
    check('  negative control: one emitted row, one id checked, none survived -> PASS',
          d['state'] == 'PASS' and d['n_inactive_ids_checked'] == 1
          and d['n_emitted_player_rows'] == 1, str(d)[:200])
    d = B.assert_no_inactive_in_playable([_run(['00-1'])], {'BUF': ['00-1']}, {})
    check('  and a surviving inactive is a TRUE FAIL', d['state'] == 'FAIL'
          and d['code'] == 'OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD', str(d)[:200])
    d = B.assert_no_inactive_in_playable([_run(['00-1'])], {}, {})
    check('  and no declarations at all stays NOT_CERTIFIED (its own, older refusal)',
          d['state'] == 'NOT_CERTIFIED', str(d)[:200])


# ---------------------------------------------------------------- post-inactives board
def test_06_board_audit_over_zero_rows():
    print('\n6. postinactives_board.assert_no_inactive_survived')
    from nfl.dfs.salaries import postinactives_board as PB
    o = PB.assert_no_inactive_survived([], ['00-1'], evidence={'declared': 1})
    observe('nfl.dfs.salaries.postinactives_board:assert_no_inactive_survived:INACTIVE_AUDIT_EMPTY_INPUT', o)
    check('positive control: an empty board is refused, not "0 inactive players in board"',
          refused(o) and o.code == 'INACTIVE_AUDIT_EMPTY_INPUT'
          and o.evidence['n_rows'] == 0, _desc(o))
    o = PB.assert_no_inactive_survived(None, ['00-1'], evidence={'declared': 1})
    check('  rows=None is the same refusal, not a crash', refused(o), _desc(o))
    rows = [{'gsis_id': '00-2', 'player': 'B', 'dk_points_mean': 9.1}]
    o = PB.assert_no_inactive_survived(rows, ['00-1'], evidence={'declared': 1})
    check('  negative control: one playable row, one inactive id, no survivor -> PASS',
          o.state is State.PASS and o.value['n_rows'] == 1, _desc(o))
    rows = [{'gsis_id': '00-1', 'player': 'A', 'dk_points_mean': 9.1}]
    o = PB.assert_no_inactive_survived(rows, ['00-1'], evidence={'declared': 1})
    check('  and a survivor is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD', _desc(o))
    o = PB.assert_no_inactive_survived(rows, ['00-1'], evidence=None)
    check('  and no evidence stays BLOCKED/DATA (its own, older refusal)',
          o.state is State.BLOCKED and o.evidence['cause'] == 'DATA', _desc(o))


# ---------------------------------------------------------------- postgame
def test_07_join_provenance_tally_over_no_graded_rows():
    print('\n7. postgame.join_provenance.audit_rows')
    from nfl.postgame import join_provenance as JP
    d = JP.audit_rows([])
    observe('nfl.postgame.join_provenance:audit_rows:JOIN_PROVENANCE_AUDIT_NOT_EXECUTED', d)
    check('positive control: no rows -> clean is None, state NOT_EXECUTED, cause EMPTY_INPUT',
          refused_dict(d) and d['clean'] is None and d['n_graded'] == 0, str(d)[:200])
    d = JP.audit_rows([{'player': 'A', 'stats': {'dk_points': {'state': 'UNSCORABLE'}}}])
    check('  rows none of which are GRADED is the same refusal, with n_rows carried',
          refused_dict(d) and d['n_rows'] == 1 and d['n_graded'] == 0, str(d)[:200])
    row = {'player': 'A', 'stats': {'dk_points': {'state': 'GRADED', 'actual': 8.2}},
           'join_provenance': JP.stamp(JP.MATCHED_BY_IDENTITY, key='00-1')}
    d = JP.audit_rows([row])
    check('  negative control: one graded, stamped row is MEASURED and clean is True',
          d['state'] == 'JOIN_PROVENANCE_AUDIT_MEASURED' and d['clean'] is True
          and d['n_graded'] == 1, str(d)[:200])
    anon = {'player': 'B', 'stats': {'dk_points': {'state': 'GRADED', 'actual': 0.0}}}
    d = JP.audit_rows([anon])
    check('  and an anonymous graded zero is a TRUE clean=False, not the empty refusal',
          d['clean'] is False and d['anonymous'] == ['B'] and 'cause' not in d, str(d)[:200])


def test_08_ledger_audit_over_no_blocks():
    print('\n8. postgame.ledger.audit')
    from nfl.postgame import ledger as LG
    with tempfile.TemporaryDirectory() as td:
        L = pathlib.Path(td) / 'LEDGER.jsonl'
        o = LG.audit(L)
        observe('nfl.postgame.ledger:audit:LEDGER_AUDIT_CLEAN_EMPTY_INPUT', o)
        check('positive control: no ledger file is refused, not CLEAN', refused(o)
              and o.code == 'LEDGER_AUDIT_CLEAN_EMPTY_INPUT'
              and o.evidence['path_exists'] is False, _desc(o))
        L.write_text('')
        o = LG.audit(L)
        check('  an existing ledger with zero blocks is the same refusal',
              refused(o) and o.evidence['n_blocks'] == 0 and o.evidence['path_exists'] is True,
              _desc(o))
        r = LG.register(block_id='X', game_id='g', forecast_identity='f', sealed_inputs={},
                        scope={'declared_before_outcome': True}, path=L)
        check('  (one registration appended)', r.state is State.PASS, _desc(r))
        o = LG.audit(L)
        check('  negative control: one registered block audits CLEAN with n_measured=1',
              o.state is State.PASS and o.evidence['n_measured'] == 1
              and o.evidence['awaiting'] == ['X'], _desc(o))
        with open(L, 'a') as fh:
            fh.write(json.dumps({'block_id': 'Y', 'status': 'GRADED'}) + '\n')
        o = LG.audit(L)
        check('  and a malformed block is a TRUE FAIL', o.state is State.FAIL
              and o.code == 'LEDGER_MALFORMED' and not o.non_evidentiary, _desc(o))


# ---------------------------------------------------------------- truth: pinned run input
def test_09_run_input_verify_with_no_entries():
    print('\n9. truth.run_input.verify / assert_consumable')
    from nfl.truth import run_input as RI
    pinned = {'cutoff_utc': '2026-09-24T15:30:00Z', 'entries': {},
              'required_families': list(RI.REQUIRED_FAMILIES)}
    rep = RI.verify(pinned, root=_REPO)
    observe('nfl.truth.run_input:verify:RUN_INPUT_VERIFY_NOT_EXECUTED', rep)
    check('positive control: a pinned set with no entries -> ok is None, NOT_EXECUTED, EMPTY_INPUT',
          refused_dict(rep) and rep['ok'] is None and rep['n_families_verified'] == 0,
          str(rep)[:200])
    got = None
    try:
        RI.assert_consumable(pinned, rep)
    except RI.RunInputRefusal as e:
        got = e
    observe('nfl.truth.run_input:assert_consumable:PINNED_EVIDENCE_NOT_VERIFIED', got)
    check('  and assert_consumable names it NOT_VERIFIED rather than "failed verification: {}"',
          got is not None and got.code == 'PINNED_EVIDENCE_NOT_VERIFIED', repr(got)[:160])
    with tempfile.TemporaryDirectory() as td:
        blob = 'schedules.aa.csv.gz'
        raw = b'\x1f\x8b\x08\x00' + b'\x00' * 16
        (pathlib.Path(td) / blob).write_bytes(raw)
        one = {'cutoff_utc': '2026-09-24T15:30:00Z',
               'required_families': ['schedules'],
               'entries': {'schedules': {'blob': blob,
                                         'blob_file_sha256': hashlib.sha256(raw).hexdigest(),
                                         'retrieved_at': '2026-09-24T12:00:00Z'}}}
        rep = RI.verify(one, root=pathlib.Path(td))
        check('  negative control: one pinned family is verified to a named verdict and ok is a bool',
              rep['verdicts'].get('schedules') in (RI.FRESH, RI.STALE, RI.AGE_NOT_BOUNDED)
              and isinstance(rep['ok'], bool) and 'cause' not in rep, str(rep)[:200])
        one['entries']['schedules']['blob_file_sha256'] = 'deadbeef' * 8
        rep = RI.verify(one, root=pathlib.Path(td))
        check('  and a wrong hash is a TRUE HASH_MISMATCH with ok False',
              rep['verdicts']['schedules'] == RI.HASH_MISMATCH and rep['ok'] is False,
              str(rep['verdicts']))


# ---------------------------------------------------------------- schema
def _trace():
    from nfl.schema import player_draw as PD
    return {'execution_id': 'e1', 'model_arm': 'A', 'spec_hash': 'a' * 8,
            'code_commit': 'c' * 8, 'input_capture_hashes': ['h1'],
            'written_at': '2026-09-08T00:00:00+00:00', 'game_id': 'g1',
            'player_id': 'p1', 'seed': 1, 'schema_version': PD.SCHEMA_VERSION}


def test_10_draw_set_with_zero_draws():
    print('\n10. schema.player_draw.validate')
    from nfl.schema import player_draw as PD
    empty = {k: np.zeros(0) for k in PD.WR_TE_FIELDS}
    o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 0, empty, _trace()))
    observe('nfl.schema.player_draw:validate:DRAW_SET_EMPTY_INPUT', o)
    check('positive control: n_draws=0 with zero-length arrays is refused, not DRAW_SET_VALID',
          refused(o) and o.code == 'DRAW_SET_EMPTY_INPUT', _desc(o))
    s = {'appeared': np.ones(5), 'pass_snaps': np.full(5, 30.0),
         'targets': np.array([5, 6, 4, 7, 5], float),
         'receptions': np.array([3, 4, 2, 5, 3], float),
         'rec_yards': np.array([40, 55, 12, 88, 31], float),
         'rec_td': np.array([0, 1, 0, 1, 0], float)}
    o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s, _trace()))
    check('  negative control: five coherent draws are VALID with n_measured=5',
          o.state is State.PASS and o.code == 'DRAW_SET_VALID'
          and o.evidence['n_measured'] == 5, _desc(o))
    s2 = dict(s)
    s2['receptions'] = np.array([9, 4, 2, 5, 3], float)
    o = PD.validate(PD.DrawSet('p1', 'WR', 'g1', 5, s2, _trace()))
    check('  and an impossible draw is a TRUE FAIL', o.state is State.FAIL
          and o.code == 'DRAW_ORDERING_VIOLATED', _desc(o))


# ---------------------------------------------------------------- governance: commit claim
def _git(repo, *a):
    return subprocess.run(['git', *a], cwd=repo, capture_output=True, text=True)


def test_11_staging_claim_with_nothing_expected():
    print('\n11. governance.commit_claim.verify_staged')
    from sportsplatform.governance import commit_claim as CC
    with tempfile.TemporaryDirectory() as td:
        r = pathlib.Path(td)
        _git(r, 'init', '-q')
        _git(r, 'config', 'user.email', 'x@y')
        _git(r, 'config', 'user.name', 'x')
        o = CC.verify_staged([], repo=r)
        observe('sportsplatform.governance.commit_claim:verify_staged:COMMIT_CLAIM_VERIFIED_EMPTY_INPUT', o)
        check('positive control: expecting no paths verifies nothing and is refused',
              refused(o) and o.code == 'COMMIT_CLAIM_VERIFIED_EMPTY_INPUT'
              and o.evidence['n_measured'] == 0, _desc(o))
        (r / 'a.py').write_text('x = 1\n')
        _git(r, 'add', 'a.py')
        o = CC.verify_staged(['a.py'], repo=r)
        check('  negative control: one expected path that is staged VERIFIES with n_measured=1',
              o.state is State.PASS and o.code == CC.CODE_OK
              and o.evidence['n_measured'] == 1, _desc(o))
        o = CC.verify_staged(['a.py', 'missing.py'], repo=r)
        check('  and an unstaged expected path is a TRUE FAIL', o.state is State.FAIL
              and o.evidence['reason'] == CC.NOT_STAGED and not o.non_evidentiary, _desc(o))


# ---------------------------------------------------------------- governance: assumptions
def _assumption(**kw):
    from sportsplatform.governance import assumption as AS
    base = dict(id='A1', claim='c', estimand='e', population='p', test='t',
                falsifier='f', downstream_dependencies=('consumer',),
                criticality=AS.CRITICAL, status=AS.DECLARED, evidence={})
    base.update(kw)
    return AS.Assumption(**base)


def test_12_promotion_verdict_over_no_assumptions_or_no_evidence():
    print('\n12. governance.assumption.assert_promotable')
    from sportsplatform.governance import assumption as AS
    o = AS.assert_promotable([_assumption()], consumer='nobody_names_me')
    observe('sportsplatform.governance.assumption:assert_promotable:PROMOTION_VERDICT_EMPTY_INPUT', o)
    check('positive control (nothing selected): a consumer no assumption names is refused, '
          'not NOT_BLOCKED', refused(o) and o.code == AS.CODE_EMPTY
          and o.evidence['n_assumptions'] == 0, _desc(o))
    o = AS.assert_promotable([], consumer='consumer')
    check('  an empty registry is the same refusal', refused(o) and o.code == AS.CODE_EMPTY,
          _desc(o))
    o = AS.assert_promotable([_assumption(status=AS.SUPPORTED, evidence={})], consumer='consumer')
    observe('sportsplatform.governance.assumption:assert_promotable:PROMOTION_VERDICT_UNEVIDENCED_ASSUMPTION', o)
    check('positive control (empty evidence): a SUPPORTED record with no evidence cannot clear '
          'promotion', refused(o) and o.code == AS.CODE_UNEVIDENCED
          and o.evidence['unevidenced'] == ['A1'], _desc(o))
    o = AS.assert_promotable([_assumption(status=AS.SUPPORTED, evidence={'n': 9})],
                             consumer='consumer')
    check('  negative control: one evidenced SUPPORTED CRITICAL assumption -> NOT_BLOCKED',
          o.state is State.PASS and o.code == 'PROMOTION_NOT_BLOCKED_BY_ASSUMPTIONS'
          and o.evidence['n_assumptions'] == 1, _desc(o))
    o = AS.assert_promotable([_assumption(status=AS.FALSIFIED, evidence={'n': 9})],
                             consumer='consumer')
    check('  and a falsified CRITICAL is a TRUE FAIL, distinct from the empty refusals',
          o.state is State.FAIL and o.code == AS.CODE_BLOCKED and not o.non_evidentiary,
          _desc(o))
    o = AS.assert_promotable([_assumption()], consumer='consumer', require_tested=True)
    check('  and an untested CRITICAL under require_tested is its own TRUE FAIL',
          o.state is State.FAIL and o.code == AS.CODE_UNTESTED, _desc(o))


# ---------------------------------------------------------------- coordination (temp copies only)
_SCHEMA_ROW = {'kind': 'SCHEMA', 'note': 'temp copy for a rule-1 control'}
_EVENT_ROW = {'timestamp': '2026-10-02T00:00:00Z', 'actor': 'test', 'task_id': 'ENG-T1',
              'from_status': 'DRAFT', 'to_status': 'AUTHORIZED'}


def _task(tid, **over):
    t = {'task_id': tid, 'title': 't', 'status': 'AUTHORIZED', 'priority': 1,
         'authorized': True, 'depends_on': [], 'objective': 'o',
         'acceptance_tests': ['it is done'], 'created_by': 'owner',
         'result_path': None, 'commit_sha': None}
    t.update(over)
    return t


def _coord_sandbox(td, *, eng_tasks, log_rows):
    """A temp coordination directory: never the live files."""
    here = pathlib.Path(td)
    for name, tasks in (('ENGINEERING_QUEUE.json', eng_tasks),
                        ('RESEARCH_QUEUE.json', [_task('RES-T1')])):
        (here / name).write_text(json.dumps({'tasks': tasks, 'exclusive_active': True}))
    (here / 'OWNER_DECISIONS.md').write_text('# d\n\n## D-01 temp\n\ntext\n')
    (here / 'HANDOFF_LOG.jsonl').write_text(
        ''.join(json.dumps(r) + '\n' for r in log_rows))
    return here


def _validate_in(here):
    import coordination.validate_coordination as VC
    saved = (VC.HERE, VC.REPO)
    VC.HERE, VC.REPO = here, here
    VC.reset()
    try:
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = VC.main()
        return rc, [c for c, _ in VC._v], buf.getvalue()
    finally:
        VC.HERE, VC.REPO = saved
        VC.reset()


def test_13_coordination_validator_refuses_empty_acceptance_tests():
    print('\n13. coordination.validate_coordination.check_queue (temp copy)')
    with tempfile.TemporaryDirectory() as td:
        here = _coord_sandbox(td, eng_tasks=[_task('ENG-T1', acceptance_tests=[])],
                              log_rows=[_SCHEMA_ROW, _EVENT_ROW])
        rc, codes, out = _validate_in(here)
        observe('coordination.validate_coordination:check_queue:ACCEPTANCE_TESTS_EMPTY_INPUT',
                'ACCEPTANCE_TESTS_EMPTY_INPUT' if 'ACCEPTANCE_TESTS_EMPTY_INPUT' in codes
                else 'COORDINATION_VALID')
        check('positive control: a task with acceptance_tests=[] is refused by name, exit 1',
              rc == 1 and 'ACCEPTANCE_TESTS_EMPTY_INPUT' in codes
              and 'COORDINATION_VALID' not in out, f'rc={rc} {codes} {out[-200:]}')
        here = _coord_sandbox(td, eng_tasks=[_task('ENG-T1', acceptance_tests='done')],
                              log_rows=[_SCHEMA_ROW, _EVENT_ROW])
        rc, codes, out = _validate_in(here)
        check('  a non-list acceptance set is the same refusal',
              rc == 1 and 'ACCEPTANCE_TESTS_EMPTY_INPUT' in codes, f'{codes}')
        here = _coord_sandbox(td, eng_tasks=[_task('ENG-T1')], log_rows=[_SCHEMA_ROW, _EVENT_ROW])
        rc, codes, out = _validate_in(here)
        check('  negative control: one acceptance test, one log event -> COORDINATION_VALID, exit 0',
              rc == 0 and not codes and 'COORDINATION_VALID' in out
              and '2 task(s)' in out and '1 event(s)' in out, f'rc={rc} {codes} {out[-200:]}')
        here = _coord_sandbox(td, eng_tasks=[_task('ENG-T1', status='ACTIVE', authorized=False)],
                              log_rows=[_SCHEMA_ROW, _EVENT_ROW])
        rc, codes, out = _validate_in(here)
        check('  and an unauthorized ACTIVE task is a TRUE violation, distinct from the empty one',
              rc == 1 and 'UNAUTHORIZED_TASK_ACTIVE' in codes
              and 'ACCEPTANCE_TESTS_EMPTY_INPUT' not in codes, f'{codes}')


def test_14_coordination_validator_refuses_an_empty_handoff_log():
    print('\n14. coordination.validate_coordination.check_log (temp copy)')
    with tempfile.TemporaryDirectory() as td:
        here = _coord_sandbox(td, eng_tasks=[_task('ENG-T1')], log_rows=[])
        rc, codes, out = _validate_in(here)
        observe('coordination.validate_coordination:check_log:LOG_EMPTY_INPUT',
                'LOG_EMPTY_INPUT' if 'LOG_EMPTY_INPUT' in codes else 'COORDINATION_VALID')
        check('positive control: a HANDOFF_LOG.jsonl with no rows is refused by name, exit 1',
              rc == 1 and 'LOG_EMPTY_INPUT' in codes and 'COORDINATION_VALID' not in out,
              f'rc={rc} {codes} {out[-200:]}')
        (here / 'HANDOFF_LOG.jsonl').write_text('\n\n')
        rc, codes, out = _validate_in(here)
        check('  whitespace-only is the same refusal', rc == 1 and 'LOG_EMPTY_INPUT' in codes,
              f'{codes}')
        here = _coord_sandbox(td, eng_tasks=[_task('ENG-T1')], log_rows=[_SCHEMA_ROW])
        rc, codes, out = _validate_in(here)
        check('  negative control: a parsed SCHEMA row with 0 events is VALID and says 0 event(s)',
              rc == 0 and not codes and '1 log row(s) of which 0 event(s)' in out,
              f'rc={rc} {codes} {out[-200:]}')
        here = _coord_sandbox(td, eng_tasks=[_task('ENG-T1')],
                              log_rows=[_SCHEMA_ROW, {'actor': 'x'}])
        rc, codes, out = _validate_in(here)
        check('  and a row missing its fields is a TRUE violation, distinct from the empty one',
              rc == 1 and 'LOG_FIELD_MISSING' in codes and 'LOG_EMPTY_INPUT' not in codes,
              f'{codes}')


def test_15_refresh_state_writes_null_not_a_default_for_an_unmeasured_gate():
    print('\n15. coordination.refresh_state.governance_fields / apply (temp copy of the state)')
    import coordination.refresh_state as RS
    import ast
    tree = ast.parse(pathlib.Path(RS.__file__).read_text())
    literal_defaults = [v.value for n in ast.walk(tree) if isinstance(n, ast.BoolOp)
                        for v in n.values if isinstance(v, ast.Constant)
                        and v.value in ('11/12', 'NOT AUTHORIZED')]
    check('no `or <literal>` default remains in the source for a gate reading',
          not literal_defaults, str(literal_defaults))
    g = RS.governance_fields(Outcome.blocked('NFL1_NOT_AUTHORIZED', 'd', cause=Cause.GOVERNANCE))
    observe('coordination.refresh_state:governance_fields:GOVERNANCE_GATES_NOT_MEASURED', g)
    check('positive control: an outcome carrying no gates reads G0A/NFL_1 as None with a '
          'measurement error each, never 11/12 or NOT AUTHORIZED',
          g['state'] == 'GOVERNANCE_GATES_NOT_MEASURED'
          and g['fields']['G0A'] is None and g['fields']['NFL_1'] is None
          and set(g['errors']) == {'governance_G0A_error', 'governance_NFL_1_error'}
          and all('NOT_MEASURED' in v for v in g['errors'].values()), str(g)[:240])
    g = RS.governance_fields(Outcome.blocked(
        'NFL1_NOT_AUTHORIZED', 'd', cause=Cause.GOVERNANCE,
        gates={'G0A': '11/12', 'NFL_1': 'NOT AUTHORIZED'}))
    check('  negative control: an outcome carrying both gates is MEASURED with no error',
          g['state'] == 'GOVERNANCE_MEASURED' and g['fields']['G0A'] == '11/12'
          and g['fields']['NFL_1'] == 'NOT AUTHORIZED' and not g['errors'], str(g)[:240])
    # apply() on a COPY of the live state: every key survives, the gate goes null, and the
    # error lands in measurement_errors.
    live = json.loads(RS.STATE.read_text())
    doc = copy.deepcopy(live)
    m = {'head_commit': 'abc', 'branch': 'b', 'written_at_utc': 't',
         'governance': {'may_publish': 'BLOCKED', 'may_publish_code': 'X',
                        'G0A': None, 'NFL_1': None},
         'governance_G0A_error': 'NOT_MEASURED: no gates.G0A reading',
         'governance_NFL_1_error': 'NOT_MEASURED: no gates.NFL_1 reading'}
    RS.apply(doc, m)
    check('  apply() keeps every existing key of the state',
          set(live) <= set(doc) and set(live['governance']) <= set(doc['governance']),
          str(sorted(set(live) - set(doc))))
    check('  and writes the unmeasured gates as null, not as the old values',
          doc['governance']['G0A'] is None and doc['governance']['NFL_1'] is None,
          str(doc['governance']))
    check('  and names what was not measured under measurement_errors',
          set(doc.get('measurement_errors') or {}) == {'governance_G0A_error',
                                                       'governance_NFL_1_error'},
          str(doc.get('measurement_errors')))
    check('  the live PROJECT_STATE.json was not written by this test',
          json.loads(RS.STATE.read_text()) == live)


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
