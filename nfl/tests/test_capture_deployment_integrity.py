"""D24. The code that captures must be the code we validated.

THE FINDING, MEASURED AGAINST origin/main ON 2026-09-15

`.github/workflows/nfl-capture.yml` uses `actions/checkout@v4` with NO `ref:`.
A `schedule:` trigger checks out the DEFAULT branch. So every scheduled capture
runs main's copy of the capture surface, and main's copy is this:

    nfl/capture/payload_contract.py        ABSENT
    nfl/capture/persisted_provenance.py    ABSENT
    nfl/capture/evidence_layers.py         ABSENT
    nfl/tools/capture_vintage.py           differs
    nfl/capture/registry.py                differs
    nfl/capture/coverage.py                differs

Three modules do not exist there. That is not older logic, it is MISSING logic:
every check they perform is simply not happening on the only path that actually
captures. D20's row_container, D22's payload contracts and D24's own
persisted-digest guard are all absent from production while passing on this
branch -- which is how 928 of 932 reduce rows came to carry no persisted digest
while a test asserted the population was "closed by construction".

Section D FAILS ON PURPOSE while that remains true. It is the deployment state,
not a defect in this file, and it must not be made green by relaxing it.

Run standalone:  python3.12 nfl/tests/test_capture_deployment_integrity.py
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import capture_identity as CI                     # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github' / 'workflows' / 'nfl-capture.yml'


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  NOT_EXECUTED {label}  {why}')


def _ref_surface(ref):
    """The capture surface as it exists at a git ref, without touching the tree."""
    out = {}
    for rel in CI.CAPTURE_SURFACE:
        r = subprocess.run(['git', 'show', f'{ref}:{rel}'],
                           capture_output=True, cwd=ROOT)
        out[rel] = (hashlib.sha256(r.stdout).hexdigest()
                    if r.returncode == 0 else None)
    return out


# --------------------------------------------------------------------------
def test_a_the_identity_is_computable_and_absence_aware():
    print('\nA. the capture identity')
    surf = CI.surface()
    check('every surface file is accounted for',
          set(surf) == set(CI.CAPTURE_SURFACE), str(sorted(surf)))
    check('  and an ABSENT file is None, not a hash of nothing',
          all(v is None or len(v) == 64 for v in surf.values()))
    # THE EMPTY-STRING TRAP. hashlib.sha256(b'').hexdigest() starts
    # e3b0c44298fc1c14, and a missing module hashed that way is
    # indistinguishable from an empty one. On main three modules ARE missing and
    # that is the finding, so absence must not be flattened into a digest.
    empty = hashlib.sha256(b'').hexdigest()
    check('  and no surface entry is the empty-string digest',
          empty not in set(v for v in surf.values() if v),
          'absence flattened into a hash is how "missing" reads as "different"')
    ident = CI.identity()
    for k in ('capture_code_sha', 'workflow_sha', 'workflow_ref',
              'parser_version', 'source_contract_version'):
        check(f'  identity carries {k}', k in ident, str(sorted(ident)))
    check('  and absent environment values stay None rather than invented',
          ident['workflow_sha'] is None or isinstance(ident['workflow_sha'], str))


def test_b_the_validated_contract_exists_and_matches_this_tree():
    print('\nB. this tree matches its own validated contract')
    v = CI.validated()
    if v is None:
        check('a validated capture contract is recorded', False,
              'VALIDATED_CAPTURE_CONTRACT.json absent -- drift cannot be '
              'measured, which is NOT the same as no drift')
        return
    d = CI.drift()
    check('the running surface matches the validated contract',
          d['verdict'] == 'MATCHES', json.dumps(d)[:200])


def test_c_the_drift_detector_fires_on_a_seeded_regression():
    """A guard that has never refused anything is a convention, not a control."""
    print('\nC. seeded drift is detected, and absence is worse than difference')
    v = CI.validated()
    if v is None:
        not_executed('no contract', 'nothing to seed against')
        return
    real = CI.surface()

    seeded_diff = dict(real)
    seeded_diff['nfl/capture/registry.py'] = 'f' * 64
    orig = CI.surface
    try:
        CI.surface = lambda: seeded_diff
        d = CI.drift(v)
        check('a changed module reads SURFACE_DIFFERS',
              d['verdict'] == 'SURFACE_DIFFERS', str(d['verdict']))
        check('  and names which module',
              'nfl/capture/registry.py' in d['differing'], str(d['differing']))

        seeded_absent = dict(real)
        seeded_absent['nfl/capture/payload_contract.py'] = None
        CI.surface = lambda: seeded_absent
        d2 = CI.drift(v)
        check('a MISSING module reads SURFACE_FILES_ABSENT, a distinct verdict',
              d2['verdict'] == 'SURFACE_FILES_ABSENT', str(d2['verdict']))
        check('  because missing logic is not old logic',
              d2['verdict'] != d['verdict'])
    finally:
        CI.surface = orig
    check('  and the real surface is restored', CI.surface is orig)


def test_d_BUG_the_scheduled_capture_path_runs_unvalidated_code():
    """FAILS ON PURPOSE. This is the deployment state, not a test defect."""
    print('\nD. BUG -- what the scheduled capture path actually runs')
    if not WORKFLOW.exists():
        not_executed('nfl-capture.yml absent', 'cannot audit the trigger')
        return
    wf = WORKFLOW.read_text()
    check('the capture workflow is schedule-triggered',
          'schedule:' in wf and 'cron:' in wf)

    # REWRITTEN 2026-09-15, AND THE OLD VERSION SAID TO DO THIS. It asserted
    # `'ref:' not in wf` -- that is, it asserted THE BUG EXISTS, so pinning the
    # ref broke the check that was watching for the pin. Its own failure
    # message read "if a ref: appeared this check needs rewriting, not
    # deleting". A check should assert what must HOLD; then fixing the defect
    # turns it green instead of red.
    #
    # AND IT MUST READ THE DEFAULT BRANCH, NOT THIS ONE. The working tree is
    # not what the scheduler runs. A pin present here and absent on the default
    # branch is exactly D24: a repair on the branch that does not run.
    r = subprocess.run(['git', 'rev-parse', '--verify', 'origin/main'],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        not_executed('origin/main not fetched',
                     'cannot compare the deployed surface; run git fetch')
        return
    for name in ('nfl-capture.yml', 'nfl-t90.yml'):
        shown = subprocess.run(
            ['git', 'show', f'origin/main:.github/workflows/{name}'],
            capture_output=True, text=True, cwd=ROOT)
        if shown.returncode != 0:
            check(f'{name} exists on the default branch', False, 'absent')
            continue
        try:
            import yaml
            doc = yaml.safe_load(shown.stdout)
        except Exception:                                        # noqa: BLE001
            not_executed(f'{name} parsed from origin/main', 'no yaml parser')
            continue
        # Structural: a `ref:` inside a comment is not a checkout step.
        refs = []
        for job in ((doc or {}).get('jobs') or {}).values():
            for s in (job.get('steps') or []):
                if isinstance(s, dict) and 'checkout' in str(s.get('uses') or ''):
                    v = (s.get('with') or {}).get('ref')
                    if isinstance(v, str):
                        m = re.fullmatch(r'\$\{\{\s*env\.(\w+)\s*\}\}',
                                         v.strip())
                        if m:
                            v = ((doc.get('env') or {}).get(m.group(1)))
                    refs.append(v)
        check(f'the default-branch {name} pins an explicit governed ref',
              bool(refs) and all(rf == 'capture-prod' for rf in refs),
              f'{refs} -- a schedule trigger with no ref checks out the '
              f'DEFAULT branch, which on 2026-09-15 was missing three capture '
              f'modules outright')
    v = CI.validated()
    if v is None:
        not_executed('no validated contract', 'nothing to compare against')
        return
    # MEASURE THE BRANCH THAT ACTUALLY RUNS, WHICH IS NO LONGER THIS ONE.
    # This read origin/main's capture surface and called that "what the
    # scheduler runs". Before D24 that was right, because a ref-less checkout
    # took the default branch. After D24 it is wrong BY DESIGN: the default
    # branch carries the workflow DEFINITIONS and capture-prod carries the
    # SURFACE, so measuring main's surface reports three modules missing from a
    # branch that is not supposed to have them, and would go on reporting it
    # forever while production was correct.
    #
    # So: follow the pointer instead of assuming where it points. Resolve the
    # ref out of the default-branch definition, then measure THAT. If anyone
    # unpins the ref, this falls back to the default branch and goes red again,
    # which is the behaviour worth keeping.
    executed_ref = 'origin/main'
    for _n in ('nfl-capture.yml', 'nfl-t90.yml'):
        _shown = subprocess.run(
            ['git', 'show', f'origin/main:.github/workflows/{_n}'],
            capture_output=True, text=True, cwd=ROOT)
        if _shown.returncode != 0:
            continue
        try:
            import yaml
            _doc = yaml.safe_load(_shown.stdout)
        except Exception:                                        # noqa: BLE001
            continue
        for _job in ((_doc or {}).get('jobs') or {}).values():
            for _s in (_job.get('steps') or []):
                if not isinstance(_s, dict):
                    continue
                if 'checkout' not in str(_s.get('uses') or ''):
                    continue
                _v = (_s.get('with') or {}).get('ref')
                if not isinstance(_v, str):
                    continue
                _m = re.fullmatch(r'\$\{\{\s*env\.(\w+)\s*\}\}', _v.strip())
                if _m:
                    _v = ((_doc.get('env') or {}).get(_m.group(1)) or _v)
                if _v and _v != 'origin/main':
                    executed_ref = f'origin/{_v}'
    print(f'       the scheduler checks out: {executed_ref}')
    main_surface = _ref_surface(executed_ref)
    orig = CI.surface
    try:
        CI.surface = lambda: main_surface
        d = CI.drift(v)
    finally:
        CI.surface = orig
    print(f"       origin/main verdict: {d['verdict']}")
    print(f"       absent on main     : {d.get('absent')}")
    print(f"       differing on main  : {d.get('differing')}")
    # BUG: the branch the scheduler checks out does not carry the validated
    # capture implementation.
    check(f'the branch the scheduler checks out ({executed_ref}) runs the '
          f'VALIDATED capture implementation',
          d['verdict'] == 'MATCHES',
          f"CAPTURE_DEPLOYMENT_DRIFT: {d.get('detail')} Until this is green, "
          f"every scheduled capture writes rows produced by code that was "
          f"never validated, and a passing test on this branch says nothing "
          f"about production.")


def test_e_the_contract_cannot_be_written_by_a_capture_run():
    """A guard that can certify itself is not a guard."""
    print('\nE. the contract is a governed artifact, not a capture output')
    cap = (ROOT / 'nfl' / 'tools' / 'capture_vintage.py').read_text()
    check('capture_vintage does not write the validated contract',
          'write_contract' not in cap and 'VALIDATED_CAPTURE_CONTRACT' not in cap,
          'a capture run that can stamp its own code as validated is marking '
          'its own homework')
    src = (ROOT / 'nfl' / 'capture' / 'capture_identity.py').read_text()
    check('  and write_contract is separate from identity()',
          'def write_contract' in src and 'def identity' in src)


if __name__ == '__main__':
    test_a_the_identity_is_computable_and_absence_aware()
    test_b_the_validated_contract_exists_and_matches_this_tree()
    test_c_the_drift_detector_fires_on_a_seeded_regression()
    test_d_BUG_the_scheduled_capture_path_runs_unvalidated_code()
    test_e_the_contract_cannot_be_written_by_a_capture_run()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
