"""Two ledgers, one derived state, and the refusals that keep them honest.

The property under test is the owner's rule of 2026-09-25: an open approval
parks its own branch and nothing else. `global_stop_required` must be false
while any authorized work remains, and it must be computed rather than
asserted.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.governance import ledgers as L                        # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def raised(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                      # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


def _row(**kw):
    base = dict(id='X-1', date_discovered='2026-09-25', subsystem='s',
                severity='HIGH', defect='d', reproduction='r', affected='a',
                impact='i', next_action='n', owner_approval_needed=False,
                blocked_by=None, status=L.OPEN, fix_commit=None,
                verification_test=None, prospective_validation_needed=False,
                scheduler_tier='T3_PRODUCTION_CORRECTNESS',
                execution_lineage=None, execution_evidence=None)
    base.update(kw)
    return base


def test_A_an_open_approval_parks_one_branch_only():
    print('\nA. the rule this whole file exists for')
    rows = [_row(id='D-1'), _row(id='D-2'),
            _row(id='D-3', status=L.WAITING_OWNER, owner_approval_needed=True,
                 blocked_by='APPROVAL-001')]
    s = L.autonomy_state(rows, apps=[])
    check('waiting work is counted', s['waiting_owner_count'] == 1, s)
    check('and does not reduce the authorized queue',
          s['valid_next_actions'] == 2, s)
    check('global_stop_required is FALSE with work remaining',
          s['global_stop_required'] is False, s)
    check('next_action skips the parked row', s['next_action'] in ('D-1', 'D-2'),
          s['next_action'])


def test_B_stop_only_when_nothing_is_authorized():
    print('\nB. and it must be able to say why')
    rows = [_row(id='D-1', status=L.WAITING_OWNER, owner_approval_needed=True,
                 blocked_by='APPROVAL-001')]
    s = L.autonomy_state(rows, apps=[])
    check('a queue of only parked work DOES stop',
          s['global_stop_required'] is True, s)
    check('and names the reason',
          any('owner decision' in r for r in s['global_stop_reasons']),
          s['global_stop_reasons'])
    ext = [_row(id='D-1', status=L.EXTERNAL_BLOCKED)]
    s2 = L.autonomy_state(ext, apps=[])
    check('an externally blocked queue stops with its own reason',
          s2['global_stop_required'] and
          any('external' in r for r in s2['global_stop_reasons']),
          s2['global_stop_reasons'])
    check('an empty ledger stops and says so',
          L.autonomy_state([], apps=[])['global_stop_reasons']
          == ['no valid next action remains'])


def test_C_severity_order_and_approval_exclusion():
    print('\nC. what "next" means')
    rows = [_row(id='D-low', severity='LOW'),
            _row(id='D-crit', severity='CRITICAL'),
            _row(id='D-med', severity='MEDIUM'),
            _row(id='D-appr', severity='CRITICAL',
                 owner_approval_needed=True, blocked_by='APPROVAL-001')]
    order = [d['id'] for d in L.actionable(rows)]
    check('severity orders the queue', order == ['D-crit', 'D-med', 'D-low'],
          order)
    check('a CRITICAL needing approval is not offered as next',
          'D-appr' not in order, order)


def test_D_closure_requires_evidence():
    print('\nD. a row closes on proof, not on belief')
    ok, d = raised(L.LedgerError,
                   lambda: L.close('D-1', fix_commit='', verification_test='',
                                   status=L.VERIFIED),
                   'needs both a fix_commit and a verification_test')
    check('VERIFIED without commit and test is refused', ok, d)
    ok2, d2 = raised(L.LedgerError,
                     lambda: L.close('D-1', fix_commit='abc',
                                     verification_test='t', status=L.OPEN),
                     'not a closing status')
    check('OPEN is not a closing status', ok2, d2)


def test_E_rows_that_would_make_the_ledger_lie():
    print('\nE. refusals on the write path')
    for label, kw, needle in (
            ('a defect with no reproduction', dict(reproduction=''),
             'rumour'),
            ('owner_approval_needed with no blocked_by',
             dict(owner_approval_needed=True), 'Name the APPROVAL id'),
            ('WAITING_OWNER with no blocked_by',
             dict(status=L.WAITING_OWNER), 'WAITING_OWNER with no blocked_by'),
            ('an unknown severity', dict(severity='SPICY'), 'severity'),
            ('an unknown status', dict(status='NEARLY'), 'unknown status')):
        ok, d = raised(L.LedgerError,
                       lambda kw=kw: L.add_defect(**_row(**kw)), needle)
        check(label + ' is refused', ok, d)
    ok, d = raised(L.LedgerError,
                   lambda: L.add_defect(id='Y', date_discovered='x'),
                   'missing')
    check('a partial row is refused rather than defaulted', ok, d)


def test_F_an_approval_the_owner_cannot_act_on_is_refused():
    print('\nF. a request with one option is a notification')
    base = dict(id='A-T', date_raised='2026-09-25', decision_required='d',
                why_owner_approval='w', options=['only one'],
                recommended_default='r', if_approved='y', if_not_approved='n',
                work_that_continues_regardless='lots', urgency='WHENEVER',
                deadline=None, irreversible_if_missed=False,
                requesting_task='D-1', status=L.RAISED,
                owner_decision=None, decision_timestamp=None,
                resulting_commit=None, last_escalated_at=None,
                blocked_ids_at_last_escalation=[])
    ok, d = raised(L.LedgerError, lambda: L.raise_approval(**base),
                   'at least two options')
    check('one option is refused', ok, d)
    b2 = dict(base, options=['a', 'b'], work_that_continues_regardless='')
    ok2, d2 = raised(L.LedgerError, lambda: L.raise_approval(**b2),
                     'name what continues regardless')
    check('and so is omitting what continues regardless', ok2, d2)


def test_G_escalation_is_event_driven():
    print('\nG. "still open" is not a reason to ping')
    rows = [_row(id='D-1'),
            _row(id='D-2', status=L.WAITING_OWNER, owner_approval_needed=True,
                 blocked_by='A-1')]
    a = dict(id='A-1', status=L.RAISED, urgency='WHENEVER', deadline=None,
             irreversible_if_missed=False,
             last_escalated_at=None, blocked_ids_at_last_escalation=[])
    # SUPERSEDED 2026-09-25. Creating an approval used to be an announcement
    # ('first raise') and accumulating blocked work used to earn a second
    # mention. Under the non-blocking policy neither interrupts: an approval
    # is queued, and what matters is only whether OTHER work remains.
    check('creating an approval is not an announcement',
          L.should_escalate(a, rows) is None, L.should_escalate(a, rows))
    a2 = dict(a, last_escalated_at='2026-09-25T00:00:00+00:00',
              blocked_ids_at_last_escalation=['D-2'])
    check('and it stays quiet', L.should_escalate(a2, rows) is None,
          L.should_escalate(a2, rows))
    rows3 = rows + [_row(id='D-3', status=L.WAITING_OWNER,
                         owner_approval_needed=True, blocked_by='A-1')]
    check('more blocked work does not interrupt while other work runs',
          L.should_escalate(a2, rows3) is None,
          L.should_escalate(a2, rows3))
    only_parked = [d for d in rows3 if d['id'] != 'D-1']
    r2 = L.should_escalate(a2, only_parked)
    check('becoming the last blocker earns one',
          r2 is not None and 'last thing standing' in r2, r2)
    # SUPERSEDED 2026-09-25. Urgency alone used to escalate. Under the
    # non-blocking policy an approval may be BLOCKING_NOW and still wait,
    # because what matters is whether OTHER work remains, not how the
    # approval was labelled.
    r3 = L.should_escalate(dict(a2, urgency='BLOCKING_NOW'), rows)
    check('urgency alone no longer interrupts while work remains',
          r3 is None, r3)
    check('a decided approval never escalates',
          L.should_escalate(dict(a2, status=L.APPROVED), rows3) is None)


def test_H_the_live_ledger_is_not_stopped():
    print('\nH. the real files, right now')
    s = L.autonomy_state()
    check('the live ledger has authorized work',
          s['valid_next_actions'] > 0, s['valid_next_actions'])
    check('and is therefore not globally stopped',
          s['global_stop_required'] is False, s)
    check('every parked row names its approval',
          all(d.get('blocked_by') for d in L.defects()
              if d['status'] == L.WAITING_OWNER))
    check('every VERIFIED row carries a commit and a test',
          all(d.get('fix_commit') and d.get('verification_test')
              for d in L.defects() if d['status'] == L.VERIFIED))


def test_I_the_scheduler_puts_operating_risk_above_correctness():
    print('\nI. a dark feed outranks a refactor')
    rows = [_row(id='D-crit', severity='CRITICAL',
                 scheduler_tier='T3_PRODUCTION_CORRECTNESS',
                execution_lineage=None, execution_evidence=None),
            _row(id='D-risk', severity='MEDIUM',
                 status=L.OPERATING_RISK_ACTIVE,
                 scheduler_tier='T2_OPERATING_RISK'),
            _row(id='D-gov', severity='LOW',
                 scheduler_tier='T1_SAFETY_GOVERNANCE'),
            _row(id='D-rnd', severity='CRITICAL',
                 scheduler_tier='T5_PREDICTIVE_RND')]
    order = [d['id'] for d in L.actionable(rows)]
    check('tier beats severity', order == ['D-gov', 'D-risk', 'D-crit', 'D-rnd'],
          order)
    check('an OPERATING_RISK_ACTIVE row is actionable, not parked',
          'D-risk' in order, order)


def test_J_an_undeclared_tier_is_refused():
    print('\nJ. tier is declared, never inferred')
    ok, d = raised(L.LedgerError,
                   lambda: L.add_defect(**_row(id='Z-1', scheduler_tier=None)),
                   'Declare it')
    check('a row with no tier is refused', ok, d)
    ok2, d2 = raised(L.LedgerError,
                     lambda: L.add_defect(**_row(id='Z-2',
                                                 scheduler_tier='T9_VIBES')),
                     'not in')
    check('and so is an invented tier', ok2, d2)


def test_K_breadth_is_reported_not_just_count():
    print('\nK. twenty-one tasks in one subsystem is not room to work')
    narrow = [_row(id=f'D-{i}', subsystem='dfs') for i in range(5)]
    s = L.autonomy_state(narrow, apps=[])
    check('five tasks in one subsystem report one workstream',
          s['independent_workstreams'] == 1, s['workstreams'])
    check('while the count still reads five', s['valid_next_actions'] == 5)
    wide = [_row(id=f'D-{i}', subsystem=f'sub{i}') for i in range(5)]
    check('five subsystems report five',
          L.autonomy_state(wide, apps=[])['independent_workstreams'] == 5)


def test_L_the_live_state_has_breadth_and_named_risk():
    print('\nL. the real files')
    s = L.autonomy_state()
    check('more than one independent workstream',
          s['independent_workstreams'] > 1, s['independent_workstreams'])
    check('operating risks are named', len(s['operating_risk_active']) >= 1,
          s['operating_risk_active'])
    check('no row is parked on an approval that was already decided',
          s['stale_owner_blocks'] == [], s['stale_owner_blocks'])
    check('owner_blocked_branches does not exceed the open approvals',
          s['owner_blocked_branches'] <= len(s['open_approvals']),
          (s['owner_blocked_branches'], s['open_approvals']))
    check('the next action is the highest tier present',
          s['next_tier'] == L.actionable()[0]['scheduler_tier'])


def test_M_a_repair_is_not_verified_where_it_does_not_run():
    print('\nM. DEF-047 had thirteen green checks and a dead board')
    ok, d = raised(L.LedgerError,
                   lambda: L.close('DEF-052', fix_commit='abc',
                                   verification_test='t'),
                   'needs an execution_lineage')
    check('VERIFIED without an execution lineage is refused', ok, d)
    check('FIX_IMPLEMENTED is actionable, not closed',
          L.FIX_IMPLEMENTED in L._ACTIONABLE)
    check('so is FIX_DEPLOYED', L.FIX_DEPLOYED in L._ACTIONABLE)
    check('and FIX_EXECUTED', L.FIX_EXECUTED in L._ACTIONABLE)
    check('none of the three is terminal',
          not ({L.FIX_IMPLEMENTED, L.FIX_DEPLOYED, L.FIX_EXECUTED}
               & L._TERMINAL))


def test_N_every_verified_row_names_where_it_ran():
    print('\nN. the live ledger under the new rule')
    bad = [d['id'] for d in L.defects() if d['status'] == L.VERIFIED
           and not (d.get('execution_lineage') and d.get('execution_evidence'))]
    check('no VERIFIED row lacks an execution lineage and evidence',
          not bad, bad)
    d47 = [d for d in L.defects() if d['id'] == 'DEF-047']
    if d47:
        check('DEF-047 has not reached VERIFIED without a real run',
              d47[0]['status'] in (L.FIX_IMPLEMENTED, L.FIX_DEPLOYED,
                                   L.FIX_EXECUTED), d47[0]['status'])


def test_O_an_open_approval_never_demands_an_interruption():
    print('\nO. approvals are queued, not announced')
    rows = [_row(id=f'D-{i}') for i in range(5)] + [
        _row(id='D-blocked', status=L.WAITING_OWNER,
             owner_approval_needed=True, blocked_by='A-1')]
    app = dict(id='A-1', status=L.RAISED, urgency='BLOCKING_NOW',
               deadline=None, irreversible_if_missed=False,
               last_escalated_at=None, blocked_ids_at_last_escalation=[])
    s = L.autonomy_state(rows, apps=[app])
    check('runnable_now is reported', s['runnable_now'] == 5, s['runnable_now'])
    check('owner_interrupt_required is FALSE with work remaining',
          s['owner_interrupt_required'] is False, s)
    check('and carries no reason', s['owner_interrupt_reason'] is None)
    check('even at BLOCKING_NOW urgency',
          L.should_escalate(app, rows) is None, L.should_escalate(app, rows))
    check('the raise itself is not an escalation', s['escalations_due'] == [],
          s['escalations_due'])


def test_P_the_controlling_question_is_runnable_not_waiting():
    print('\nP. runnable_now == 0 AND waiting_owner > 0')
    only_parked = [_row(id='D-1', status=L.WAITING_OWNER,
                        owner_approval_needed=True, blocked_by='A-1')]
    app = dict(id='A-1', status=L.RAISED, urgency='WHENEVER', deadline=None,
               irreversible_if_missed=False, last_escalated_at=None,
               blocked_ids_at_last_escalation=[])
    s = L.autonomy_state(only_parked, apps=[app])
    check('with nothing runnable it DOES stop',
          s['global_stop_required'] is True and s['runnable_now'] == 0, s)
    check('and only then demands an interruption',
          s['owner_interrupt_required'] is True)
    check('naming why', bool(s['owner_interrupt_reason']),
          s['owner_interrupt_reason'])
    check('the approval becomes the last thing standing',
          L.should_escalate(app, only_parked)
          == 'it is the last thing standing: no authorized work remains')


def test_Q_an_imminent_irreversible_deadline_may_interrupt():
    print('\nQ. the one time-based exception, and its two conditions')
    rows = [_row(id='D-1')]
    soon = (dt_now() + __import__('datetime').timedelta(hours=3)).isoformat()
    far = (dt_now() + __import__('datetime').timedelta(days=40)).isoformat()
    mk = lambda **k: dict(dict(id='A-1', status=L.RAISED, urgency='DATED',
                               deadline=soon, irreversible_if_missed=True,
                               last_escalated_at=None,
                               blocked_ids_at_last_escalation=[]), **k)
    r = L.should_escalate(mk(), rows)
    check('imminent AND irreversible interrupts', r and 'deadline in' in r, r)
    check('imminent but reversible does NOT',
          L.should_escalate(mk(irreversible_if_missed=False), rows) is None)
    check('irreversible but distant does NOT',
          L.should_escalate(mk(deadline=far), rows) is None)


def dt_now():
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc)


def test_R_the_live_state_under_the_new_policy():
    print('\nR. the real ledger right now')
    s = L.autonomy_state()
    check('there is runnable work', s['runnable_now'] > 0, s['runnable_now'])
    check('open approvals do not demand an interruption',
          s['owner_interrupt_required'] is False,
          (s['open_approvals'], s['owner_interrupt_reason']))
    check('waiting_owner is a list of ids, not just a count',
          isinstance(s['waiting_owner'], list), type(s['waiting_owner']))
    check('waiting_external is reported separately',
          isinstance(s['waiting_external'], list))
    check('and breadth is still reported',
          s['independent_workstreams'] > 1, s['independent_workstreams'])


# ---------------------------------------------------------------------------
# amend_defect: withdrawing a claim without destroying the evidence it was made
#
# This exists because DEF-047 was recorded FIX_DEPLOYED when nothing was
# deployed -- the board pin sat on a branch no scheduled run reads. A status is
# a claim, and a claim that turns out to be false has to be withdrawable. But
# quietly rewriting the row would erase the fact it was ever overclaimed, which
# is the failure the owner named directly: do not fix a defect in a way that
# destroys the ability to prove it existed.
# ---------------------------------------------------------------------------

import contextlib                                              # noqa: E402
import tempfile                                                # noqa: E402


@contextlib.contextmanager
def _isolated_log(rows=()):
    """Point the ledger at a scratch file. These tests WRITE."""
    original = L.DEFECT_LOG
    with tempfile.TemporaryDirectory() as d:
        L.DEFECT_LOG = pathlib.Path(d) / 'DEFECT_LOG.jsonl'
        L.DEFECT_LOG.write_text(''.join(L.json.dumps(r) + '\n' for r in rows))
        try:
            yield
        finally:
            L.DEFECT_LOG = original


def _defect_row(**kw):
    base = {f: '' for f in L.DEFECT_FIELDS}
    base.update(id='DEF-TEST', date_discovered='2026-09-25', subsystem='s',
                severity='HIGH', defect='d', reproduction='r', affected='a',
                impact='i', next_action='n', owner_approval_needed=False,
                blocked_by='', status=L.FIX_DEPLOYED, fix_commit='',
                verification_test='t', prospective_validation_needed=False,
                scheduler_tier='T2_OPERATING_RISK')
    base.update(kw)
    return base


def test_amend_defect_demotes_and_keeps_the_history():
    with _isolated_log([_defect_row()]):
        r = L.amend_defect('DEF-TEST', reason='not actually deployed',
                           status=L.FIX_IMPLEMENTED)
        check('status demoted', r['status'] == L.FIX_IMPLEMENTED, r['status'])
        check('one amendment recorded', len(r.get('amendments', [])) == 1)
        a = r['amendments'][0]
        check('amendment keeps the prior value',
              a['before']['status'] == L.FIX_DEPLOYED, a['before'])
        check('amendment keeps the reason',
              'not actually deployed' in a['reason'])
        check('amendment is timestamped', a['at'].endswith('Z'), a['at'])
        check('the demotion survives a reread',
              [d for d in L.defects() if d['id'] == 'DEF-TEST'
               ][0]['status'] == L.FIX_IMPLEMENTED)


def test_amend_defect_refuses_an_unreasoned_change():
    """A status that changes with no recorded cause is indistinguishable from
    one that was never checked."""
    with _isolated_log([_defect_row()]):
        for bad in ('', '   ', None):
            ok, why = raised(L.LedgerError,
                             lambda b=bad: L.amend_defect('DEF-TEST', reason=b,
                                                          status=L.OPEN),
                             'reason')
            check(f'refuses reason={bad!r}', ok, why)


def test_amend_defect_cannot_reach_verified():
    """VERIFIED demands a commit, a test and the execution lineage. If an
    amendment could grant it, it would be a way around close()."""
    with _isolated_log([_defect_row()]):
        ok, why = raised(L.LedgerError,
                         lambda: L.amend_defect('DEF-TEST', reason='r',
                                                status=L.VERIFIED),
                         'close()')
        check('refuses VERIFIED by amendment', ok, why)


def test_amend_defect_refuses_a_lifecycle_jump():
    """Each step of IMPLEMENTED -> DEPLOYED -> EXECUTED needs its own evidence.
    Skipping one is how a fix that never shipped gets called executed."""
    with _isolated_log([_defect_row(status=L.OPEN)]):
        ok, why = raised(L.LedgerError,
                         lambda: L.amend_defect('DEF-TEST', reason='r',
                                                status=L.FIX_EXECUTED),
                         'cannot jump')
        check('refuses OPEN -> FIX_EXECUTED', ok, why)
    with _isolated_log([_defect_row(status=L.FIX_IMPLEMENTED)]):
        r = L.amend_defect('DEF-TEST', reason='a run checked out the pinned ref',
                           status=L.FIX_DEPLOYED)
        check('allows the single adjacent step', r['status'] == L.FIX_DEPLOYED)


def test_amend_defect_refuses_unknown_fields_and_unknown_ids():
    with _isolated_log([_defect_row()]):
        ok, why = raised(L.LedgerError,
                         lambda: L.amend_defect('DEF-TEST', reason='r',
                                                stauts=L.OPEN), 'unknown field')
        check('a misspelled field is refused, not silently added', ok, why)
        ok, why = raised(L.LedgerError,
                         lambda: L.amend_defect('DEF-NOPE', reason='r',
                                                status=L.OPEN), 'no such defect')
        check('an unknown id is refused', ok, why)


def test_amend_defect_does_not_disturb_its_neighbours():
    """The whole file is rewritten, so prove the other rows come back intact."""
    rows = [_defect_row(id='DEF-A', status=L.OPEN),
            _defect_row(id='DEF-B', status=L.FIX_DEPLOYED, defect='keep me'),
            _defect_row(id='DEF-C', status=L.IN_PROGRESS)]
    with _isolated_log(rows):
        L.amend_defect('DEF-B', reason='r', status=L.FIX_IMPLEMENTED)
        after = {d['id']: d for d in L.defects()}
        check('no row lost', sorted(after) == ['DEF-A', 'DEF-B', 'DEF-C'],
              sorted(after))
        check('DEF-A untouched', after['DEF-A']['status'] == L.OPEN)
        check('DEF-C untouched', after['DEF-C']['status'] == L.IN_PROGRESS)
        check('amended row keeps its other fields',
              after['DEF-B']['defect'] == 'keep me')
        check('neighbours gain no amendment history',
              'amendments' not in after['DEF-A'])
