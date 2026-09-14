"""R5: the active-roster pool. Guards on a repair, not on a preference."""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                 # noqa: E402
from nfl.production import candidate_mode as CM                     # noqa: E402
from nfl.production.nonqb import roster_status as RS                # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def test_v1_candidate_is_an_untouched_control():
    """R5 must be V1 PLUS ONE THING, or the comparison means nothing."""
    v1 = CM.resolve(CM.V1_CANDIDATE).value['flags']
    r5 = CM.resolve(CM.V1_CANDIDATE_R5).value['flags']
    check('V1_CANDIDATE carries no active-roster flag',
          'active_roster_only' not in v1, str(v1))
    check('  R5 sets exactly that one flag and changes nothing else',
          {k: v for k, v in r5.items() if k != 'active_roster_only'} == v1,
          str(r5))
    check('  and R5 is a separate declared identity',
          CM.V1_CANDIDATE_R5 in CM.MODES and
          CM.V1_CANDIDATE_R5 != CM.V1_CANDIDATE)
    # NAMING THE NEXT CANDIDATE AS THE "UNKNOWN" ONE IS A DATED ASSERTION.
    # This read `V1_CANDIDATE_R6`, which was unknown when it was written and
    # became a real mode the moment R6 shipped -- so a test about refusing
    # typos started failing because the project made progress. The durable
    # property is that a name NOT in MODES is refused, whatever the modes are.
    unknown = 'V1_CANDIDATE_' + 'X' * 8
    check('  an unknown configuration is still refused, not defaulted',
          unknown not in CM.MODES
          and CM.resolve(unknown).state is State.FAIL, unknown)


def test_neither_candidate_can_be_called_promoted():
    for m in (CM.V1_CANDIDATE, CM.V1_CANDIDATE_R5):
        o = CM.assert_not_promoted(m, {
            'model_configuration': m, 'promoted': False,
            'prospective_eligible': False, 'eligibility_verdict': m,
            'candidate_components': CM.resolve(m).value['components']})
        check(f'{m} is not promotable', o.state is State.PASS,
              f'{o.code}: {o.detail[:80]}')


def test_the_repair_introduces_no_constant():
    check('R5 declares that it introduces no constant',
          CM.R5_REPAIR['introduces_no_constant'] is True)
    src = open(os.path.join(_ROOT,
                            'nfl/production/nonqb/roster_status.py')).read()
    # The only literals are roster status CODES, not weights or thresholds.
    check('  and its module holds no numeric threshold',
          not any(t in src for t in ('0.1', '0.2', '0.5', '* 1.', '/ 1.')),
          'NUMERIC_CONSTANT_IN_REPAIR')


def test_an_unknown_status_is_kept_not_dropped():
    """Dropping a player the roster does not describe would be the
    forcing-concentration move this repair exists to avoid."""
    players = [{'gsis_id': 'A', 'position': 'WR'},
               {'gsis_id': 'B', 'position': 'WR'},
               {'gsis_id': 'C', 'position': 'WR'}]
    o = RS.active_pool(players, {'A': 'ACT', 'B': 'DEV'})
    check('the active player is kept', o.state is State.PASS)
    kept = {q['gsis_id'] for q in o.value}
    check('  the practice-squad player is dropped', 'B' not in kept, str(kept))
    check('  the UNKNOWN-status player is KEPT', 'C' in kept, str(kept))
    check('  and the artifact counts him',
          o.evidence['n_unknown_status_kept'] == 1)
    check('  and names what was dropped and why',
          o.evidence['dropped_by_status'] == {'DEV': 1}
          and 'practice squad' in o.evidence['dropped_meaning']['DEV'])


def test_an_empty_pool_refuses():
    o = RS.active_pool([{'gsis_id': 'A', 'position': 'WR'}], {'A': 'DEV'})
    check('a pool with nobody left is a refusal, not an allocation of nothing',
          o.state is State.FAIL and o.code == 'ACTIVE_POOL_EMPTY', o.code)


def test_status_is_never_read_from_after_the_cut():
    """A status read from a post-cut capture is not pregame information."""
    o = RS.status_map(2026, 1, ('SF', 'LA'),
                      observed_before='2020-01-01T00:00:00Z')
    check('a cut before every capture refuses by name',
          o.state is not State.PASS
          and o.code in ('ROSTER_STATUS_NO_ELIGIBLE_VINTAGE',
                         'ROSTER_STATUS_UNAVAILABLE'), o.code)
    live = RS.status_map(2026, 1, ('SF', 'LA'),
                         observed_before='2026-09-10T23:00:00Z')
    if live.state is State.PASS:
        check('  a usable vintage reports which capture it read',
              bool(live.evidence.get('source')))
        check('  and when that capture was observed',
              live.evidence.get('observed_at', '') < '2026-09-10T23:00:00Z',
              str(live.evidence.get('observed_at')))
        check('  the ACT class is present and is not the whole roster',
              live.evidence['status_counts'].get('ACT', 0) > 0
              and len(live.evidence['status_counts']) > 1,
              str(live.evidence['status_counts']))
    else:
        check('  status is unavailable and says so by name',
              live.code == 'ROSTER_STATUS_UNAVAILABLE', live.code)


def test_missing_status_refuses_rather_than_silently_running_unfiltered():
    """THE DANGEROUS FAILURE IS A SILENT ONE. If status cannot be read, R5
    must refuse -- running unfiltered under an R5 label would report a repair
    that did not happen."""
    src = open(os.path.join(_ROOT, 'nfl/production/run_forecast.py')).read()
    i = src.index("if fl.get('active_roster_only')")
    # THE WINDOW IS SLICED TO THE BRANCH, NOT TO A CHARACTER COUNT.
    #
    # This read `src[i:i + 900]`, and 900 was only ever the length the branch
    # happened to be. When R2's eligibility gate replaced the status-only
    # filter the branch grew to 2,580 characters, and the two refusal
    # assertions fell off the end of the window -- so the checks FAILED while
    # every line they were looking for was still present and still correct, a
    # few hundred characters further down. A test that reports a repair as
    # missing because the file got longer is measuring the file's length.
    #
    # The end marker is the branch's own last statement. If someone renames
    # it, this raises ValueError rather than silently shrinking back to a
    # window that proves nothing -- which is the failure mode being removed.
    j = src.index("fx['_eligibility_gate_applied'] = True", i)
    window = src[i:j + 40]
    check('the R5 branch returns a fatal on a status refusal',
          "fx['_nonqb'] = {'fatal': st}" in window)
    check('  and on a snapshot refusal',
          "fx['_nonqb'] = {'fatal': snap}" in window)
    check('  and on an empty pool',
          "fx['_nonqb'] = {'fatal': pool}" in window)
    check('  it never falls back to the unfiltered list',
          'except' not in window and 'or players' not in window)
    # THE GATE IS THE MECHANISM, NOT A LABEL ON THE OLD ONE. `active_pool`
    # answers "is he on the active roster" and reads every other adverse
    # determination as silence; the branch must be calling the gate that
    # ranks four authorities, and must build the choice set rather than
    # allocating and zeroing afterwards.
    check('  the branch builds its pool from the eligibility gate',
          'EG.snapshot(' in window and 'EG.choice_set(' in window)
    check('  and no longer from roster status alone',
          'RS.active_pool(nonqb' not in window)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
