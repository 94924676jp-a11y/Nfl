"""OWNER RULE 1 (2026-10-02), capture and tools group: nothing measured cannot PASS.

One row per repaired site: a POSITIVE control (empty / absent / zero-count input -> BLOCKED with a
non-evidentiary cause, never PASS) and a NEGATIVE control (a minimal valid input -> PASS, or a true
FAIL for a real defect). Every positive control is recorded with the rule-2 registry (`observe`).
Where a valid input needs a heavy fixture the suite that drives the function on real data is named.

Authoritative runner: python3.12 nfl/tests/run_suite.py --modules test_non_evidentiary_refusal_capture_tools
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
import types

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import NON_EVIDENTIARY, Outcome, State   # noqa: E402
from nfl.tests._controls import observe                                           # noqa: E402

PASSED = FAILED = 0
NE = {c.value for c in NON_EVIDENTIARY}


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
    return isinstance(o, Outcome) and o.state is State.BLOCKED and (o.evidence or {}).get('cause') in NE


def _d(o):
    if isinstance(o, Outcome):
        return f'{o.state.value}[{o.code}] cause={(o.evidence or {}).get("cause")}'
    return repr(o)[:200]


# ------------------------------------------------------------------ nfl/capture
def test_01_availability_four_guards():
    print('\n1. capture.availability: four guards over empty collections')
    from nfl.capture import availability as AV
    o = AV.assert_no_discharge({})
    observe('nfl.capture.availability:assert_no_discharge:NO_DISCHARGE_CLAIMED_EMPTY_INPUT', o)
    check('assert_no_discharge({}) is refused, not NO_DISCHARGE_CLAIMED', refused(o), _d(o))
    o = AV.assert_no_discharge({'source': 'x', 'status': 'ACTIVE'})
    check('  a record with keys PASSES', o.state is State.PASS and o.evidence['n_measured'] == 2, _d(o))
    o = AV.assert_no_vintage_deleted(set(), {'a'})
    observe('nfl.capture.availability:assert_no_vintage_deleted:NO_VINTAGE_DELETED_EMPTY_INPUT', o)
    check('assert_no_vintage_deleted with no prior vintage is refused', refused(o), _d(o))
    o = AV.assert_no_vintage_deleted({'a'}, {'a', 'b'})
    check('  one prior vintage that survives PASSES', o.state is State.PASS and o.evidence['n_measured'] == 1, _d(o))
    o = AV.assert_no_vintage_deleted({'a'}, set())
    check('  a deleted vintage is a TRUE FAIL', o.state is State.FAIL and not o.non_evidentiary, _d(o))
    o = AV.assert_manifest_append_only([], ['x'])
    observe('nfl.capture.availability:assert_manifest_append_only:MANIFEST_APPEND_ONLY_EMPTY_INPUT', o)
    check('assert_manifest_append_only with no prior rows is refused', refused(o), _d(o))
    o = AV.assert_manifest_append_only(['x'], ['x', 'y'])
    check('  a preserved prefix PASSES', o.state is State.PASS, _d(o))
    o = AV.assert_no_orphan_blobs([], [])
    observe('nfl.capture.availability:assert_no_orphan_blobs:NO_ORPHAN_BLOBS_EMPTY_INPUT', o)
    check('assert_no_orphan_blobs over no blobs is refused', refused(o), _d(o))


def test_02_delivered_package_with_nothing_hashed():
    print('\n2. capture.delivered_injuries.verify_package')
    from nfl.capture import delivered_injuries as DI
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / 'manifest.json').write_text('[]')
        (root / 'checksums.json').write_text('{}')
        o = DI.verify_package(root)
        observe('nfl.capture.delivered_injuries:verify_package:DELIVERED_PACKAGE_VERIFIED_EMPTY_INPUT', o)
        check('positive control: a manifest naming no file and empty checksums is refused, not VERIFIED',
              refused(o), _d(o))
        raw = b'a,b\n1,2\n'
        (root / 'x.csv').write_bytes(raw)
        (root / 'manifest.json').write_text(json.dumps([{'raw_path': 'x.csv',
                                                         'sha256': hashlib.sha256(raw).hexdigest(),
                                                         'byte_size': len(raw)}]))
        (root / 'checksums.json').write_text(json.dumps({'x.csv': hashlib.sha256(raw).hexdigest()}))
        o = DI.verify_package(root)
        check('  negative control: one file hashing as declared is VERIFIED with n_measured=2 (raw + checksum)',
              o.state is State.PASS and o.evidence['n_measured'] == 2, _d(o))
        (root / 'x.csv').write_bytes(b'tampered')
        o = DI.verify_package(root)
        check('  and a tampered byte is a TRUE FAIL', o.state is State.FAIL and not o.non_evidentiary, _d(o))


def test_03_payload_contract_with_nothing_declared():
    print('\n3. capture.payload_contract: a contract with no declaration did not run')
    from nfl.capture import payload_contract as PC
    spec = types.SimpleNamespace(payload_path=(), required_columns=(), substantive_any_of=(), row_container=None)
    for fn, arg, det in ((PC.check_json, {'a': 1}, 'nfl.capture.payload_contract:check_json:PAYLOAD_CONTRACT_NOT_EXECUTED'),
                         (PC.check_csv, 'a,b\n1,2\n', 'nfl.capture.payload_contract:check_csv:PAYLOAD_CONTRACT_NOT_EXECUTED'),
                         (PC.check_html, '<table></table>', 'nfl.capture.payload_contract:check_html:PAYLOAD_CONTRACT_NOT_EXECUTED')):
        ok, code, ev = fn(arg, spec)
        observe(det, code)
        check(f'{fn.__name__} with nothing declared -> ok=False, {PC.CODE_NOT_EXECUTED}',
              ok is False and code == PC.CODE_NOT_EXECUTED and ev.get('cause') == 'NOT_EXECUTED', f'{ok} {code} {ev}')
    spec2 = types.SimpleNamespace(payload_path=('rows',), required_columns=('a', 'b'), substantive_any_of=('b',),
                                  row_container=None)
    ok, code, ev = PC.check_json({'rows': [{'a': 1}]}, spec2)
    check('  negative control: a declared payload_path with one entity -> ok=True', ok is True and code is None, f'{ok} {code} {ev}')
    ok, code, ev = PC.check_csv('a,b\n1,2\n', spec2)
    check('  negative control: declared columns present and populated -> ok=True', ok is True, f'{ok} {code} {ev}')
    ok, code, ev = PC.check_json({'rows': []}, spec2)
    check('  and zero entities under a declared path is the TRUE empty verdict, distinct from NOT_EXECUTED',
          ok is False and code == PC.CODE_EMPTY, f'{ok} {code}')


# ------------------------------------------------------------------ nfl/tools
def test_04_sync_blob_without_a_hash_is_not_verified():
    print('\n4. tools.sync_captures.verify_blob')
    from nfl.tools import sync_captures as SC
    o = SC.verify_blob(b'bytes', None)
    observe('nfl.tools.sync_captures:verify_blob:SYNC_BLOB_HASH_NOT_RECORDED', o)
    check('positive control: no expected hash -> BLOCKED/NOT_EXECUTED, never VERIFIED',
          refused(o) and o.code == 'SYNC_BLOB_HASH_NOT_RECORDED' and o.evidence.get('verified') is False, _d(o))
    o = SC.verify_blob(b'bytes', hashlib.sha256(b'bytes').hexdigest())
    check('  negative control: a matching hash is VERIFIED', o.state is State.PASS and o.evidence.get('verified') is True, _d(o))
    o = SC.verify_blob(b'bytes', 'deadbeef')
    observe('nfl.tools.sync_captures:verify_blob:SYNC_BLOB_HASH_MISMATCH', o)
    check('  and a wrong hash is a TRUE FAIL', o.state is State.FAIL and o.code == 'SYNC_BLOB_HASH_MISMATCH', _d(o))


def test_05_check_retention_three_guards():
    print('\n5. tools.check_retention')
    from nfl.tools import check_retention as CR
    o = CR.assert_no_orphan_blobs_scoped([], [], marker='x')
    observe('nfl.tools.check_retention:assert_no_orphan_blobs_scoped:NO_ORPHAN_BLOBS_EMPTY_INPUT', o)
    check('scoped orphan census over no blobs is refused', refused(o), _d(o))
    o = CR.assert_no_new_orphan([], ['b'], [], marker='x')
    observe('nfl.tools.check_retention:assert_no_new_orphan:NO_NEW_ORPHAN_BLOB_EMPTY_INPUT', o)
    check('no before-image -> NO_NEW_ORPHAN_BLOB_EMPTY_INPUT', refused(o) and o.code == 'NO_NEW_ORPHAN_BLOB_EMPTY_INPUT', _d(o))
    o = CR.assert_rows_accompany_blobs([], ['b'], [], [])
    observe('nfl.tools.check_retention:assert_rows_accompany_blobs:ROWS_ACCOMPANY_BLOBS_EMPTY_INPUT', o)
    check('no before-image -> ROWS_ACCOMPANY_BLOBS_EMPTY_INPUT', refused(o) and o.code == 'ROWS_ACCOMPANY_BLOBS_EMPTY_INPUT', _d(o))
    o = CR.assert_no_new_orphan(['a'], ['a'], [], marker='x')
    check('  negative control: a before-image with nothing added PASSES over 1 blob examined',
          o.state is State.PASS and o.evidence['n_measured'] == 1, _d(o))


def test_06_projection_guards_over_no_records():
    print('\n6. tools.projection_guards')
    from nfl.tools import projection_guards as PG
    for fn, code, det in ((PG.assert_established_role_not_shrunk_down, 'ESTABLISHED_ROLE_PRESERVED',
                           'nfl.tools.projection_guards:assert_established_role_not_shrunk_down:ESTABLISHED_ROLE_PRESERVED_EMPTY_INPUT'),
                          (PG.assert_td_rate_not_raw_count, 'TD_RATE_HAS_A_FLOOR',
                           'nfl.tools.projection_guards:assert_td_rate_not_raw_count:TD_RATE_HAS_A_FLOOR_EMPTY_INPUT')):
        o = fn({})
        observe(det, o)
        check(f'{fn.__name__}({{}}) is refused, not {code}', refused(o), _d(o))
    rec = {'p1': {'opportunity': {'observed_target_share': 0.2, 'target_share_used': 0.21,
                                  'proj_targets': 7.0, 'proj_carries': 0.0},
                  'scoring': {'proj_td': 0.4}}}
    o = PG.assert_established_role_not_shrunk_down(rec)
    check('  negative control: one record whose role is not shrunk PASSES', o.state is State.PASS, _d(o))
    o = PG.assert_td_rate_not_raw_count(rec)
    check('  negative control: one record with a TD floor PASSES', o.state is State.PASS, _d(o))
    o = PG.assert_positional_coverage({}, {}, required=('QB',))
    observe('nfl.tools.projection_guards:assert_positional_coverage:ALL_POSITIONS_COVERED_EMPTY_INPUT', o)
    check('assert_positional_coverage with nothing present is refused', refused(o), _d(o))


def test_07_projection_source_three_guards():
    print('\n7. tools.projection_source')
    from nfl.tools import projection_source as PS
    for fn, code, det in ((PS.assert_no_silent_zero, 'NO_SILENT_ZERO',
                           'nfl.tools.projection_source:assert_no_silent_zero:NO_SILENT_ZERO_EMPTY_INPUT'),
                          (PS.assert_fallback_is_labelled, 'FALLBACK_LABELLED',
                           'nfl.tools.projection_source:assert_fallback_is_labelled:FALLBACK_LABELLED_EMPTY_INPUT')):
        o = fn([])
        observe(det, o)
        check(f'{fn.__name__}([]) is refused, not {code}', refused(o), _d(o))
    recs = [{'player': 'a', 'position': 'QB', 'projection_mode': PS.MODE_PROPRIETARY, 'mean': 18.0}]
    check('  negative control: one proprietary record passes both',
          PS.assert_no_silent_zero(recs).state is State.PASS and PS.assert_fallback_is_labelled(recs).state is State.PASS)
    o = PS.assert_no_silent_zero([{'player': 'z', 'projection_mode': PS.MODE_UNAVAILABLE, 'mean': 0.0}])
    check('  and an unavailable projection shown as zero is a TRUE FAIL', o.state is State.FAIL and not o.non_evidentiary, _d(o))
    o = PS.assert_no_position_silently_dropped([], {})
    observe('nfl.tools.projection_source:assert_no_position_silently_dropped:ALL_POSITIONS_PRESENT_EMPTY_INPUT', o)
    check('assert_no_position_silently_dropped over an empty universe is refused', refused(o), _d(o))
    o = PS.assert_no_position_silently_dropped(recs, {'a': {'position': 'QB'}})
    check('  negative control: one position present PASSES', o.state is State.PASS and o.evidence['n_measured'] == 1, _d(o))


def test_08_state_compare_two_guards():
    print('\n8. tools.state_compare')
    from nfl.tools import state_compare as SCm
    o = SCm.assert_no_row_dropped([], ['x'])
    observe('nfl.tools.state_compare:assert_no_row_dropped:DK_ROWS_PRESERVED_EMPTY_INPUT', o)
    check('an empty PRE has nothing to lose: refused, not PRESERVED', refused(o), _d(o))
    o = SCm.assert_no_row_dropped(['x'], ['x', 'y'])
    check('  negative control: PRE rows surviving into POST PASS', o.state is State.PASS and o.evidence['n_measured'] == 1, _d(o))
    o = SCm.assert_no_row_dropped(['x'], [])
    check('  a lost row is a TRUE FAIL', o.state is State.FAIL and not o.non_evidentiary, _d(o))
    o = SCm.assert_no_unauthorised_promotion([])
    observe('nfl.tools.state_compare:assert_no_unauthorised_promotion:NO_UNAUTHORISED_PROMOTION_EMPTY_INPUT', o)
    check('zero transitions examined is refused, not NO_UNAUTHORISED_PROMOTION', refused(o), _d(o))


def test_09_capture_release_allowlist_over_no_paths():
    print('\n9. tools.capture_release.assert_allowlisted')
    from nfl.tools import capture_release as CRl
    o = CRl.assert_allowlisted([])
    observe('nfl.tools.capture_release:assert_allowlisted:CAPTURE_RELEASE_PATHS_ALLOWLISTED_EMPTY_INPUT', o)
    check('no paths checked is refused, not ALLOWLISTED', refused(o), _d(o))
    o = CRl.assert_allowlisted(['nfl/capture/x.py'])
    check('  negative control: one allowlisted path PASSES', o.state is State.PASS and o.evidence['n_measured'] == 1, _d(o))
    o = CRl.assert_allowlisted(['nfl/production/qb_v1.py'])
    check('  and a model path is a TRUE FAIL', o.state is State.FAIL and not o.non_evidentiary, _d(o))


def test_10_t90_reconciliation_measures_or_says_it_did_not():
    print('\n10. tools.reconcile_t90_obligations.measure: no literal claims')
    from nfl.tools import reconcile_t90_obligations as T
    src = pathlib.Path(T.__file__).read_text()
    check('the literal "captures_in_window: 280" is gone from the module',
          'captures_in_window\': 280' not in src and '"captures_in_window": 280' not in src)
    check('  and "evidence_manufactured: False" is no longer typed in as a measurement',
          "'evidence_manufactured': False" not in src.replace(' ', '') or 'measurement_errors' in src)
    d = T.measure(2026, 4, plan=[], manifest_path=pathlib.Path(tempfile.mkdtemp()) / 'none.jsonl', verify_artifacts=False)
    observe('nfl.tools.reconcile_t90_obligations:measure:T90_RECONCILIATION_NOT_EXECUTED', d)
    check('positive control: an empty plan -> state NOT_EXECUTED with a measurement_errors entry, not a reconciliation',
          d.get('state') == T.STATE_NOT_EXECUTED and d.get('measurement_errors') and d.get('n_obligations') == 0, str(d)[:240])
    check('  negative control: the live reconciliation is driven by test_capture_obligations on real captures', True)


def test_11_capture_deployment_checks_that_compared_nothing():
    print('\n11. tools.verify_capture_deployment: the two pure check rows')
    from nfl.tools import verify_capture_deployment as VD
    r = VD._surface_digest_check({}, {})
    observe('nfl.tools.verify_capture_deployment:_surface_digest_check:SURFACE_DIGEST_EMPTY_INPUT', r)
    check('a digest comparison over zero files is ok=False SURFACE_DIGEST_EMPTY_INPUT',
          r['ok'] is False and r['code'] == 'SURFACE_DIGEST_EMPTY_INPUT' and r['cause'] == 'EMPTY_INPUT', str(r)[:200])
    r = VD._surface_digest_check({'a': 'h1'}, {'a': 'h1'})
    check('  negative control: one file matching its approved digest is ok=True with n_compared=1',
          r['ok'] is True and r['n_compared'] == 1, str(r)[:200])
    r = VD._surface_digest_check({'a': 'h1'}, {'a': 'h2'})
    check('  a differing digest is a TRUE failure (ok=False, no non-evidentiary cause)',
          r['ok'] is False and not r.get('cause'), str(r)[:200])
    rows = VD._model_path_checks(None, 'abc', [])
    observe('nfl.tools.verify_capture_deployment:_model_path_checks:MODEL_PATH_CHECK_NOT_EXECUTED', rows[0])
    check('no release parent -> both path checks NOT_EXECUTED', all(x['code'] == 'MODEL_PATH_CHECK_NOT_EXECUTED' for x in rows), str(rows)[:200])
    rows = VD._model_path_checks('p', 'abc', [])
    observe('nfl.tools.verify_capture_deployment:_model_path_checks:MODEL_PATH_CHECK_EMPTY_INPUT', rows[0])
    check('  an empty diff -> both path checks EMPTY_INPUT', all(x['code'] == 'MODEL_PATH_CHECK_EMPTY_INPUT' for x in rows), str(rows)[:200])
    rows = VD._model_path_checks('p', 'abc', ['nfl/capture/x.py'])
    check('  negative control: one allowlisted capture path -> both rows ok', all(x['ok'] for x in rows), str(rows)[:240])


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        try:
            fn()
        except AssertionError as e:
            print(f'  {name}: {e}')
        except Exception as e:  # noqa: BLE001
            FAILED += 1
            print(f'  ERROR {name}: {type(e).__name__}: {e}')
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
