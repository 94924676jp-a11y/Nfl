"""D24 closes here: the scheduler cannot silently fall back to `main`.

THE STATE THIS REPLACES. `.github/workflows/nfl-capture.yml` used
`actions/checkout@v4` with no `ref:`. A `schedule:` trigger checks out the
DEFAULT branch, and measured against that branch on 2026-09-15:

    nfl/capture/payload_contract.py        ABSENT
    nfl/capture/persisted_provenance.py    ABSENT
    nfl/capture/evidence_layers.py         ABSENT
    plus three modules at older revisions

Three modules did not exist. D20's row_container, D22's payload contracts and
D24's own persisted-digest guard were all absent from the only code that
actually captures, while their tests passed on the development branch. That is
how 928 of 932 reduce rows came to carry no persisted digest under a test
asserting the population was "closed by construction".

WHAT MUST NOW HOLD

  1. the capture workflow names an explicit governed ref -- never the implicit
     default branch
  2. it records the RESOLVED commit, because a mutable branch name is not
     provenance
  3. it fails closed, BEFORE fetching anything, unless the running surface and
     the executed commit match the approved release
  4. the allowlist cannot carry a forecasting change to production
  5. the approved release records a complete, absence-aware surface digest

Sections A-E are those five. Section F is the bypass proof: strip the ref and
the fallback becomes possible again, so the pin is what is doing the work.

Run standalone:  python3.12 nfl/tests/test_capture_prod_deployment.py
"""
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import capture_identity as CI                     # noqa: E402
from nfl.tools import capture_release as CR                        # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github' / 'workflows'
CAPTURE_WORKFLOWS = ('nfl-capture.yml', 'nfl-t90.yml')


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


def _checkout_steps(text):
    """Every actions/checkout step, with the block that follows it."""
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        # A STEP, NOT PROSE THAT MENTIONS ONE. The first cut matched any line
        # containing 'actions/checkout' and so matched this file's own
        # explanatory comments, reporting a checkout with no ref that does not
        # exist. Fourth time today a string search has matched a comment;
        # require the step syntax.
        s = ln.strip()
        if s.startswith('#') or not s.startswith('- uses:'):
            continue
        if 'actions/checkout' not in s:
            continue
        indent = len(ln) - len(ln.lstrip())
        block = [ln]
        for nxt in lines[i + 1:]:
            if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent \
                    and not nxt.lstrip().startswith(('with:', 'ref:', '-')):
                break
            if nxt.strip().startswith('- ') and \
                    (len(nxt) - len(nxt.lstrip())) <= indent:
                break
            block.append(nxt)
        out.append('\n'.join(block))
    return out


# --------------------------------------------------------------------------
def test_a_the_capture_workflow_names_an_explicit_ref():
    print('\nA. no implicit default-branch checkout on a capture workflow')
    seen = 0
    for name in CAPTURE_WORKFLOWS:
        p = WORKFLOWS / name
        if not p.exists():
            not_executed(f'  {name}', 'workflow absent')
            continue
        text = p.read_text()
        if 'schedule:' not in text:
            not_executed(f'  {name}', 'not schedule-triggered')
            continue
        seen += 1
        steps = _checkout_steps(text)
        check(f'  {name} has a checkout step', bool(steps))
        for blk in steps:
            # A SCHEDULE TRIGGER TAKES THE DEFAULT BRANCH WHEN ref: IS ABSENT.
            # That is the whole defect, so absence is the thing under test.
            check(f'  {name}: every checkout names an explicit ref',
                  re.search(r'^\s*ref:\s*\S+', blk, re.M) is not None,
                  'a checkout with no ref on a scheduled workflow silently '
                  'runs whatever is on the default branch')
            m = re.search(r'^\s*ref:\s*(\S+)', blk, re.M)
            if m:
                check(f'    and it is the governed branch, not main',
                      m.group(1) not in ('main', 'master',
                                         '${{ github.ref }}'),
                      f'ref: {m.group(1)}')
    if not seen:
        not_executed('no scheduled capture workflow found',
                     'nothing to protect')


def test_b_the_resolved_commit_is_recorded():
    print('\nB. a branch name is not provenance -- the commit is recorded')
    p = WORKFLOWS / 'nfl-capture.yml'
    if not p.exists():
        not_executed('nfl-capture.yml absent', 'nothing to check')
        return
    t = p.read_text()
    check('the workflow resolves HEAD to a commit',
          'rev-parse HEAD' in t,
          'ref: capture-prod says which branch, not which commit, and the '
          'branch moves')
    check('  and exports it for later steps',
          'executed_sha' in t, 'the resolved sha must be usable downstream')
    check('  and the executor check consumes it',
          '--executed-sha' in t and '--check-executor' in t)


def test_c_the_job_fails_closed_before_fetching():
    print('\nC. the surface is checked BEFORE anything is fetched')
    p = WORKFLOWS / 'nfl-capture.yml'
    if not p.exists():
        not_executed('nfl-capture.yml absent', 'nothing to check')
        return
    t = p.read_text()
    i_check = t.find('--check-executor')
    i_capture = t.find('capture_vintage.py')
    check('both the executor check and the capture are present',
          i_check > 0 and i_capture > 0)
    # A JOB THAT DISCOVERS AFTERWARDS THAT IT RAN THE WRONG CODE HAS ALREADY
    # WRITTEN ROWS NOBODY CAN ATTRIBUTE.
    check('  and the check comes FIRST', i_check < i_capture,
          f'check at {i_check}, capture at {i_capture}')


def test_d_the_allowlist_cannot_carry_a_forecasting_change():
    print('\nD. promotion is allowlisted')
    for path, want in (
            ('nfl/capture/payload_contract.py', True),
            ('nfl/tools/capture_vintage.py', True),
            ('nfl/tools/capture_release.py', True),
            ('.github/workflows/nfl-capture.yml', True),
            ('nfl/production/run_forecast.py', False),
            ('nfl/production/nonqb/layers.py', False),
            ('nfl/research/q9/hurdle.py', False),
            ('nfl/prospective/q9shadow/seal.py', False),
            ('nfl/product/quality_gates.py', False)):
        check(f'  {path} allowed={want}',
              CR.path_is_allowed(path) is want)
    # PATH TRAVERSAL. The first cut of this allowlist passed
    # nfl/capture/../production/layers.py: it startswith an allowed prefix and
    # the literal nfl/production/ the deny list looks for is not in the string.
    for evil in ('nfl/capture/../production/layers.py',
                 '../outside.py', '/etc/passwd', ''):
        check(f'  traversal refused: {evil!r}',
              CR.path_is_allowed(evil) is False)
    o = CR.assert_allowlisted(['nfl/capture/ok.py',
                               'nfl/production/run_forecast.py'])
    check('  a seeded model path refuses by name',
          o.code == 'CAPTURE_RELEASE_CARRIES_NON_CAPTURE_PATHS', o.code)
    check('    and names what it rejected',
          o.evidence['rejected'] == ['nfl/production/run_forecast.py'])


def test_e_the_approved_release_is_complete_and_enforceable():
    print('\nE. the approved release, and what it refuses')
    rel = CR.approved_release()
    if rel is None:
        check('an approved capture release is published', False,
              'CAPTURE_RELEASES.jsonl has no published release, so the '
              'executor check has nothing to enforce')
        return
    for k in ('capture_release_id', 'capture_code_sha', 'capture_surface',
              'resolved_source_sha', 'parser_version',
              'source_contract_version', 'changed_paths'):
        check(f'  release records {k}', rel.get(k) is not None, str(k))
    check('  source_contract_version is declared, not "unknown"',
          'unknown' not in str(rel.get('source_contract_version')),
          str(rel.get('source_contract_version')))
    check('  the surface digest covers every surface file',
          set(rel['capture_surface']) == set(CI.CAPTURE_SURFACE))
    check('  and every promoted path was allowlisted',
          CR.assert_allowlisted(rel['changed_paths']).state.name == 'PASS')

    good = CR.assert_executor_matches_release(rel, rel['resolved_source_sha'])
    check('  this tree matches the approved release',
          good.code == 'CAPTURE_EXECUTOR_MATCHES_RELEASE',
          f'{good.code} {good.detail[:120]}')
    bad = CR.assert_executor_matches_release(rel, 'de' * 32)
    check('  a different executed commit REFUSES',
          bad.code == 'CAPTURE_EXECUTOR_COMMIT_MISMATCH', bad.code)
    none = CR.assert_executor_matches_release(None)
    check('  and no release at all REFUSES rather than proceeding',
          none.code == 'NO_APPROVED_CAPTURE_RELEASE', none.code)

    # A SURFACE THAT LOST A MODULE IS NOT MERELY DIFFERENT.
    seeded = dict(rel)
    seeded['capture_code_sha'] = 'f' * 64
    s = CR.assert_executor_matches_release(seeded,
                                           rel['resolved_source_sha'])
    check('  a mismatched surface REFUSES',
          s.code == 'CAPTURE_EXECUTOR_SURFACE_MISMATCH', s.code)


def test_f_the_pin_is_what_is_doing_the_work():
    """Strip the ref and the fallback becomes possible again."""
    print('\nF. bypass -- remove the ref and the defect returns')
    p = WORKFLOWS / 'nfl-capture.yml'
    if not p.exists():
        not_executed('nfl-capture.yml absent', 'nothing to bypass')
        return
    live = p.read_text()
    stripped = re.sub(r'^\s*ref:\s*capture-prod\s*$', '', live, flags=re.M)
    blocks_live = _checkout_steps(live)
    blocks_stub = _checkout_steps(stripped)
    check('with the ref present, every checkout names one',
          all(re.search(r'^\s*ref:\s*\S+', b, re.M) for b in blocks_live))
    check('  with it stripped, at least one does not',
          any(not re.search(r'^\s*ref:\s*\S+', b, re.M) for b in blocks_stub),
          'if this fails the pin is not what section A is measuring')
    check('  and the live file on disk is unchanged',
          p.read_text() == live)


if __name__ == '__main__':
    test_a_the_capture_workflow_names_an_explicit_ref()
    test_b_the_resolved_commit_is_recorded()
    test_c_the_job_fails_closed_before_fetching()
    test_d_the_allowlist_cannot_carry_a_forecasting_change()
    test_e_the_approved_release_is_complete_and_enforceable()
    test_f_the_pin_is_what_is_doing_the_work()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
