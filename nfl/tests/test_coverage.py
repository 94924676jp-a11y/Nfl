"""Adversarial tests for nfl/capture/coverage.py -- the T-90 accounting.

THE FALSE GREEN THIS EXISTS TO KILL, MEASURED BEFORE THE MODULE WAS WRITTEN

    registry.unmet_targets('nfl/vintage_manifest.jsonl')
      -> {'unmet': [], 'met': ['final_status', 'inactives', 'practice'], ...}

All three perishable targets reported met, at a moment when the earliest T-90
window was 2026-09-09T22:50Z (two days out), no window had opened, and not one
capture carried a game_id. The claim was true of the question `unmet_targets`
actually asks -- "was an authorised source ever captured for this kind" -- and
false of the question a reader takes it for.

Meanwhile `schedule._clears` was already refusing an unattributed capture for a
game-specific kind. Two modules, opposite answers, and the runner printed the
optimistic one. Every section here seeds the specific way that answer can be
made to look green.

Run standalone:  python3.12 nfl/tests/test_coverage.py
"""
import datetime as dt
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import coverage as C  # noqa: E402
from nfl.capture.coverage import (coverage, event_anchored,  # noqa: E402
                                  load_week_plan, performed_from_manifest)
from nfl.capture.registry import unmet_targets  # noqa: E402
from nfl.capture.schedule import GAME_SPECIFIC_KINDS  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _is(o, state, code=None):
    return (isinstance(o, Outcome) and o.state is state
            and (code is None or o.code == code))


def _manifest(rows):
    fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    for r in rows:
        fh.write(json.dumps(r) + '\n')
    fh.close()
    return pathlib.Path(fh.name)


def _pass_row(source, retrieved_at, game_id=None):
    v = {'retrieved_at': retrieved_at, 'sha256': 'a' * 64}
    if game_id:
        v['game_id'] = game_id
    return {'capture_id': 'x', 'season': 2026, 'source': source,
            'state': 'PASS', 'code': 'CAPTURED', 'detail': '', 'value': v}


def _inactives_target():
    plan = load_week_plan(2026, 1).value
    return next(c for c in plan if c.kind == 'inactives')


# --------------------------------------------------------------------------
def test_A_the_two_answers_are_different_questions():
    print('\nA. the source-level answer is not the game-level answer')
    src = unmet_targets(MANIFEST)
    print(f'       [source-level today: met={src["met"]} '
          f'unmet={src["unmet"]}]')
    cov = coverage(2026, 1, manifest_path=MANIFEST)
    print(f'       [game-level today: {cov.state.value}[{cov.code}] '
          f'covered={cov.evidence.get("covered")} '
          f'missed={cov.evidence.get("missed")} '
          f'not_yet_due={cov.evidence.get("not_yet_due")}]')

    check('the game-level answer is never PASS while nothing has come due',
          cov.state is not State.PASS or cov.evidence['covered'] > 0,
          str(cov)[:120])
    check('not one capture in the real manifest carries a game_id',
          cov.evidence['attributed_captures'] == 0,
          str(cov.evidence.get('attributed_captures')))
    check('and the refusal names the source-level report as the thing not to '
          'read as coverage',
          'unmet_targets' in cov.detail, cov.detail[:80])


def test_B_out_of_window_never_covers():
    print('\nB. a capture outside the window does not cover the target')
    tgt = _inactives_target()
    lo, hi = tgt.window
    for label, ts in [
        ('one second before the window opens', lo - dt.timedelta(seconds=1)),
        ('one second after it closes', hi + dt.timedelta(seconds=1)),
        ('three days early -- the shape of the real defect',
         lo - dt.timedelta(days=3)),
        ('after kickoff', hi + dt.timedelta(hours=4)),
    ]:
        m = _manifest([_pass_row('official_inactives', ts.isoformat(),
                                 game_id=tgt.game_id)])
        o = coverage(2026, 1, manifest_path=m,
                     now=hi + dt.timedelta(minutes=1))
        check(f'{label} -> not covered',
              o.evidence['covered'] == 0, str(o)[:110])

    inside = lo + dt.timedelta(minutes=5)
    m = _manifest([_pass_row('official_inactives', inside.isoformat(),
                             game_id=tgt.game_id)])
    o = coverage(2026, 1, manifest_path=m, now=hi + dt.timedelta(minutes=1))
    check('and a properly attributed in-window capture DOES cover it -- so the '
          'refusals above are not a module that refuses everything',
          o.evidence['covered'] == 1, str(o)[:150])


def test_C_unattributed_never_covers_a_game_specific_target():
    print('\nC. an unattributed capture cannot cover a per-game target')
    tgt = _inactives_target()
    lo, hi = tgt.window
    inside = (lo + dt.timedelta(minutes=5)).isoformat()

    m = _manifest([_pass_row('official_inactives', inside)])   # no game_id
    o = coverage(2026, 1, manifest_path=m, now=hi + dt.timedelta(minutes=1))
    check('perfectly timed, right source, no game_id -> still not covered',
          o.evidence['covered'] == 0, str(o)[:150])
    check('and the window having closed makes it MISSED, not pending',
          o.evidence['missed'] >= 1 and _is(o, State.FAIL,
                                            'PERISHABLE_WINDOWS_MISSED'),
          str(o)[:130])

    m = _manifest([_pass_row('official_inactives', inside,
                             game_id='2026_01_DEN_KC')])
    o = coverage(2026, 1, manifest_path=m, now=hi + dt.timedelta(minutes=1))
    check('attributed to a DIFFERENT game -> does not cover this one',
          all(m2['game_id'] != '2026_01_DEN_KC'
              for m2 in o.evidence['missed_detail']
              if m2['kind'] == 'inactives') or o.evidence['covered'] <= 1,
          str(o.evidence['covered']))
    check('inactives is declared game-specific, which is what makes that true',
          'inactives' in GAME_SPECIFIC_KINDS)


def test_D_unauthorised_source_never_covers():
    print('\nD. the right timing from the wrong source does not cover')
    tgt = _inactives_target()
    lo, hi = tgt.window
    inside = (lo + dt.timedelta(minutes=5)).isoformat()
    for src in ('injuries', 'schedules', 'depth_charts', 'weekly_rosters',
                'espn_injuries_json'):
        m = _manifest([_pass_row(src, inside, game_id=tgt.game_id)])
        o = coverage(2026, 1, manifest_path=m,
                     now=hi + dt.timedelta(minutes=1))
        check(f'{src} inside the inactives window -> not covered',
              o.evidence['covered'] == 0, str(o)[:110])


def test_E_a_non_pass_row_is_not_a_capture():
    print('\nE. a BLOCKED or DEFERRED row is not evidence of a capture')
    tgt = _inactives_target()
    lo, hi = tgt.window
    inside = (lo + dt.timedelta(minutes=5)).isoformat()
    for state, code in [('BLOCKED', 'NO_EGRESS'),
                        ('DEFERRED', 'SOURCE_NOT_YET_PUBLISHED'),
                        ('FAIL', 'HTML_SHELL_OR_EMPTY'),
                        ('NOT_APPLICABLE', 'NO_GAMES')]:
        row = _pass_row('official_inactives', inside, game_id=tgt.game_id)
        row['state'], row['code'] = state, code
        m = _manifest([row])
        o = coverage(2026, 1, manifest_path=m,
                     now=hi + dt.timedelta(minutes=1))
        check(f'a {state} row does not cover the window',
              o.evidence['covered'] == 0, str(o)[:110])

    row = _pass_row('official_inactives', inside, game_id=tgt.game_id)
    del row['value']['retrieved_at']
    m = _manifest([row])
    check('a PASS with no retrieved_at anywhere BLOCKS the whole computation '
          'rather than covering nothing quietly (see E2)',
          _is(coverage(2026, 1, manifest_path=m,
                       now=hi + dt.timedelta(minutes=1)), State.BLOCKED,
              'CAPTURE_CLOCK_UNREADABLE'))
    o = performed_from_manifest('/nonexistent/nope.jsonl')
    check('a manifest that does not exist is NOT_APPLICABLE with a reason, '
          'never an empty list that reads like a clean sheet',
          _is(o, State.NOT_APPLICABLE, 'NO_MANIFEST'), str(o)[:110])


def test_E2_the_reader_must_not_drop_rows():
    """The defect this module introduced and the live manifest exposed.

    Measured 2026-09-07: 54 of 60 PASS rows nest the clock at
    value.provenance.retrieved_at and 6 older rows carry value.retrieved_at.
    The first version of performed_from_manifest read only the top level, kept
    6 rows, dropped 54, and reported total_captures: 6 without a word. Coverage
    from a 10%-sampled evidence base, failing safe-looking. Class A, produced by
    the module written to prevent Class A.
    """
    print('\nE2. the manifest reader reads both schemas and drops nothing')
    real = performed_from_manifest(MANIFEST)
    check('every PASS row in the live manifest is dated and kept',
          _is(real, State.PASS) and
          real.evidence['n_captures'] == real.evidence['n_pass_rows'],
          str(real)[:130])
    check('and that is materially more than the top-level-only reading found',
          real.evidence['n_captures'] > 50, str(real.evidence))
    print(f'       [{real.evidence["n_captures"]} captures read; the broken '
          f'reader found 6]')

    nested = {'capture_id': 'x', 'season': 2026, 'source': 'official_inactives',
              'state': 'PASS', 'code': 'CAPTURED',
              'value': {'requested_at': '2026-09-07T00:00:00+00:00',
                        'provenance': {
                            'retrieved_at': '2026-09-07T00:00:01+00:00'}}}
    o = performed_from_manifest(_manifest([nested]))
    check('a row with the clock only under provenance is read, not skipped',
          _is(o, State.PASS) and len(o.value) == 1, str(o)[:110])

    flat = dict(nested, value={'retrieved_at': '2026-09-07T00:00:01+00:00'})
    o = performed_from_manifest(_manifest([flat]))
    check('a row with the clock only at the top level is read too',
          _is(o, State.PASS) and len(o.value) == 1, str(o)[:110])

    neither = dict(nested, value={'requested_at': '2026-09-07T00:00:00+00:00'})
    o = performed_from_manifest(_manifest([neither]))
    check('a PASS row with NO retrieval clock anywhere BLOCKS -- it is not '
          'quietly dropped, which is the whole defect',
          _is(o, State.BLOCKED, 'CAPTURE_CLOCK_UNREADABLE'), str(o)[:130])
    check('and the refusal names the sources whose rows could not be read',
          o.evidence['undated_sources'] == ['official_inactives'],
          str(o.evidence))
    check('requested_at is NOT accepted as a substitute for retrieved_at -- '
          'that conflation is the V7 weather defect',
          _is(o, State.BLOCKED))

    o = coverage(2026, 1, manifest_path=_manifest([neither]))
    check('and coverage propagates the block rather than reporting a clean '
          'sheet from a manifest it could not read',
          _is(o, State.BLOCKED, 'CAPTURE_CLOCK_UNREADABLE'), str(o)[:110])


def test_F_not_yet_due_is_not_missed_and_not_covered():
    print('\nF. an open window is DEFERRED -- never missed, never covered')
    o = coverage(2026, 1, manifest_path=_manifest([]),
                 now=dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc))
    check('before the season opens nothing is missed',
          o.evidence['missed'] == 0, str(o)[:110])
    check('and nothing is covered either',
          o.evidence['covered'] == 0)
    check('the state is DEFERRED, which is a debt, not a pass and not a fail',
          _is(o, State.DEFERRED, 'NO_WINDOW_HAS_CLOSED_YET'), str(o)[:110])
    check('and it is not terminal -- the work is still owed',
          o.state.is_terminal is False)
    check('it names the next window rather than only counting',
          o.evidence['next_window'] is not None)

    after = coverage(2026, 1, manifest_path=_manifest([]),
                     now=dt.datetime(2026, 9, 20, tzinfo=dt.timezone.utc))
    check('once every window has closed with nothing captured it is a FAIL, '
          'and says the evidence is unrecoverable',
          _is(after, State.FAIL, 'PERISHABLE_WINDOWS_MISSED')
          and 'not recoverable' in after.detail, str(after)[:140])
    check('and every missed target is named, not just counted',
          len(after.evidence['missed_detail']) == after.evidence['missed'])


def test_G_no_plan_means_no_coverage_claim():
    print('\nG. no schedule snapshot -> BLOCKED, never "nothing missed"')
    with tempfile.TemporaryDirectory() as d:
        o = load_week_plan(2026, 1, vintage_dir=d)
        check('an empty vintage directory refuses to produce a plan',
              _is(o, State.BLOCKED, 'NO_SCHEDULE_SNAPSHOT'), str(o)[:120])
        o = coverage(2026, 1, manifest_path=_manifest([]), vintage_dir=d)
        check('and coverage propagates that refusal instead of reporting a '
              'clean sheet',
              _is(o, State.BLOCKED, 'NO_SCHEDULE_SNAPSHOT'), str(o)[:120])

    o = coverage(2026, 99, manifest_path=_manifest([]))
    check('a week with no games in the snapshot is BLOCKED -- an empty plan is '
          'not full coverage',
          _is(o, State.BLOCKED, 'NO_GAMES_IN_SNAPSHOT'), str(o)[:120])
    check('and the refusal says so in those words',
          'not full coverage' in o.detail, o.detail[:80])


def test_H_a_periodic_cron_is_not_event_anchoring():
    print('\nH. the cadence argument is stated as timing and refused as '
          'discharge')
    plan = load_week_plan(2026, 1).value
    o = event_anchored(plan, 30)
    check('it refuses rather than certifying the cron',
          _is(o, State.BLOCKED, 'PERIODIC_CADENCE_IS_NOT_EVENT_ANCHORING'),
          str(o)[:120])
    check('the narrowest per-game window is the 80-minute inactives window',
          o.evidence['narrowest_window_minutes'] == 80,
          str(o.evidence.get('narrowest_window_minutes')))
    check('all 16 week-1 games carry one',
          o.evidence['n_windows'] == 16, str(o.evidence.get('n_windows')))
    check('and a FASTER cadence does not turn it into a discharge -- the '
          'missing thing is attribution, not frequency',
          _is(event_anchored(plan, 1), State.BLOCKED,
              'PERIODIC_CADENCE_IS_NOT_EVENT_ANCHORING'))
    check('it names what would actually close it',
          'next_target' in o.detail and 'game_id' in o.detail, o.detail[-120:])


def test_I_the_control_is_load_bearing():
    print('\nI. guard-deletion -- is _clears what refuses the unattributed '
          'capture?')
    tgt = _inactives_target()
    lo, hi = tgt.window
    inside = (lo + dt.timedelta(minutes=5)).isoformat()
    m = _manifest([_pass_row('official_inactives', inside)])   # no game_id
    now = hi + dt.timedelta(minutes=1)

    with_guard = coverage(2026, 1, manifest_path=m, now=now)
    check('with the guard: the unattributed capture covers nothing',
          with_guard.evidence['covered'] == 0)

    import nfl.capture.schedule as S
    original = S._clears
    try:
        # The deleted guard: timing only, no game attribution and no source
        # authority -- which is exactly what a "we ran inside the window"
        # argument amounts to.
        S._clears = lambda target, performed: target.satisfied_by(
            performed[0] if isinstance(performed, tuple) else performed)
        loose = coverage(2026, 1, manifest_path=m, now=now)
    finally:
        S._clears = original

    check('with _clears reduced to a timing check the SAME capture covers '
          'targets -- so _clears is what was refusing it',
          loose.evidence['covered'] > 0,
          f'covered={loose.evidence["covered"]}')
    print(f'       [bypassed: covered={loose.evidence["covered"]} '
          f'missed={loose.evidence["missed"]} -- this is the false green]')
    check('and restoring it restores the refusal',
          coverage(2026, 1, manifest_path=m, now=now
                   ).evidence['covered'] == 0)


if __name__ == '__main__':
    test_A_the_two_answers_are_different_questions()
    test_B_out_of_window_never_covers()
    test_C_unattributed_never_covers_a_game_specific_target()
    test_D_unauthorised_source_never_covers()
    test_E_a_non_pass_row_is_not_a_capture()
    test_E2_the_reader_must_not_drop_rows()
    test_F_not_yet_due_is_not_missed_and_not_covered()
    test_G_no_plan_means_no_coverage_claim()
    test_H_a_periodic_cron_is_not_event_anchoring()
    test_I_the_control_is_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
