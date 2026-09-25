"""Two ledgers and one derived state, so "unresolved" stops meaning "stop".

THE CONFUSION THIS EXISTS TO END

Owner ruling 2026-09-25: *"'there is an unresolved issue' and 'Claude must
stop' are too easy to conflate."* They had been conflated repeatedly -- reaching
one approval gate and treating the project as paused, then reporting the same
open approval at every check-in.

So there are two ledgers with different powers, and a third file that is
DERIVED FROM THEM AND NEVER HAND-EDITED.

    DEFECT_LOG              ordinary work. Bugs, missing tests, partial joins,
                            stale fixtures, research. Never stops anything.
    OWNER_APPROVAL_QUEUE    only what genuinely needs the owner: governance
                            changes, irreversible actions, policy promotions,
                            rights, purchases, secrets. Stops ONE BRANCH.
    AUTONOMY_STATE.json     counts, and `global_stop_required`, computed.

THE FIELD THAT MATTERS IS `global_stop_required`, AND IT IS ALMOST NEVER TRUE

It is true only when every remaining task is waiting on an owner decision or an
external dependency -- that is, when there is literally nothing authorized left.
It is computed by counting, so it cannot be asserted out of pessimism, and
`autonomy_state` refuses to report a stop it cannot name a reason for.

CLOSURE REQUIRES EVIDENCE

`close()` refuses a defect that has no verification test and no fix commit.
"Fixed" with nothing proving it is how a repair register fills with claims. The
owner's rule is that a row closes only after evidence proves closure, and this
is that rule as a function that raises.

ESCALATION IS EVENT-DRIVEN

An approval is announced once. `should_escalate` returns a REASON or None, and
the reasons are: urgency rose, a deadline is near, more work became blocked by
it, or it became the last thing standing. Absent one of those, a raised
approval waits in the queue silently. Repeating it every check-in is how an
owner learns to skim.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

SPEC_VERSION = 'governance-ledgers/1.0.0'

_HERE = Path(__file__).resolve().parent
DEFECT_LOG = _HERE / 'DEFECT_LOG.jsonl'
APPROVAL_QUEUE = _HERE / 'OWNER_APPROVAL_QUEUE.jsonl'
AUTONOMY_STATE = _HERE / 'AUTONOMY_STATE.json'

# ---- vocabularies ---------------------------------------------------------
OPEN = 'OPEN'
IN_PROGRESS = 'IN_PROGRESS'
WAITING_OWNER = 'WAITING_OWNER'
EXTERNAL_BLOCKED = 'EXTERNAL_BLOCKED'
VERIFIED = 'VERIFIED'
WONT_FIX = 'WONT_FIX'

#: An active operational risk. NOT owner-blocking and NOT merely open: it can
#: impair the NEXT game-day cycle if left alone, so the scheduler must reach it
#: before any research item. A dark capture source is the archetype.
OPERATING_RISK_ACTIVE = 'OPERATING_RISK_ACTIVE'

#: THE REPAIR LIFECYCLE. Owner ruling 2026-09-25, after DEF-047.
#:
#: refresh_boards.py had a correct fix, a passing test and thirteen green
#: checks, on a branch the scheduled workflow does not check out. The board
#: had been dead since week 1 either way. A repair that never reaches the
#: executing lineage is operationally identical to no repair, so 'fixed' is
#: not one state.
#:
#:   FIX_IMPLEMENTED   the code is right and tested, somewhere.
#:   FIX_DEPLOYED      it exists on the lineage the affected workflow reads.
#:   FIX_EXECUTED      that workflow actually ran it.
#:   VERIFIED          the run produced the expected artifact, and the old
#:                     broken path is regression-tested.
#:
#: Each is a separate claim about a separate fact, and only the last closes
#: a row.
FIX_IMPLEMENTED = 'FIX_IMPLEMENTED'
FIX_DEPLOYED = 'FIX_DEPLOYED'
FIX_EXECUTED = 'FIX_EXECUTED'


#: Statuses from which no further work can be pulled.
_TERMINAL = frozenset({VERIFIED, WONT_FIX})
#: Statuses that are open work Claude may act on right now.
_ACTIONABLE = frozenset({OPEN, IN_PROGRESS, OPERATING_RISK_ACTIVE,
                         FIX_IMPLEMENTED, FIX_DEPLOYED, FIX_EXECUTED})
#: Statuses that are open and NOT actionable.
_PARKED = frozenset({WAITING_OWNER, EXTERNAL_BLOCKED})

RAISED = 'RAISED'
APPROVED = 'APPROVED'
REJECTED = 'REJECTED'
WITHDRAWN = 'WITHDRAWN'

#: OWNER APPROVALS ARE NON-BLOCKING BY DEFAULT. Owner directive 2026-09-25.
#:
#: The previous version raised an approval and then told the owner about it,
#: which made "an approval exists" an interruption event. Three approvals had
#: accumulated while twenty-six tasks were runnable, and the owner was being
#: addressed at every one.
#:
#: The controlling question is no longer `waiting_owner_count > 0`. It is
#: `runnable_now == 0 AND waiting_owner_count > 0`. An open approval parks its
#: own branch and nothing else, and may never on its own set
#: `owner_interrupt_required`.
#:
#: Hours before a deadline within which an approval may interrupt -- and only
#: when missing it is irreversible or takes production down.
IMMINENT_H = 24.0

SEVERITIES = ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')

#: THE SCHEDULER, IN THE OWNER'S ORDER (2026-09-25). A DECLARED FIELD, NOT AN
#: INFERENCE.
#:
#: Tier could be guessed from subsystem and severity, and guessing would be
#: wrong in the one case that matters: a MEDIUM defect in a capture feed that
#: goes dark before a slate outranks a CRITICAL refactor. The taxonomy is the
#: owner's, so each row states its tier and the ledger refuses a row that does
#: not.
#:
#: The purpose is to stop the failure mode where a low-priority research item
#: gets cheerful attention while a capture source is still dark.
TIERS = (
    'T1_SAFETY_GOVERNANCE',      # a refused state could reach a product
    'T2_OPERATING_RISK',         # impairs the next slate if left alone
    'T3_PRODUCTION_CORRECTNESS',  # wrong answers on the production path
    'T4_AUDIT_COMPLETION',       # the audit is not finished
    'T5_PREDICTIVE_RND',         # might make forecasts better
    'T6_PRODUCT',                # might make the product better
    'T7_CLEANUP',                # tidiness
)
URGENCIES = ('BLOCKING_NOW', 'DATED', 'WHENEVER')

DEFECT_FIELDS = (
    'id', 'date_discovered', 'subsystem', 'severity', 'defect',
    'reproduction', 'affected', 'impact', 'next_action',
    'owner_approval_needed', 'blocked_by', 'status', 'fix_commit',
    'verification_test', 'prospective_validation_needed', 'scheduler_tier')

APPROVAL_FIELDS = (
    'id', 'date_raised', 'decision_required', 'why_owner_approval',
    'options', 'recommended_default', 'if_approved', 'if_not_approved',
    'work_that_continues_regardless', 'urgency', 'deadline',
    'irreversible_if_missed',
    'requesting_task', 'status', 'owner_decision', 'decision_timestamp',
    'resulting_commit', 'last_escalated_at', 'blocked_ids_at_last_escalation')


class LedgerError(RuntimeError):
    """A row that would make the ledger lie."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _read(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _write(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n'
                            for r in rows))


def defects() -> list:
    return _read(DEFECT_LOG)


def approvals() -> list:
    return _read(APPROVAL_QUEUE)


# ---- writing --------------------------------------------------------------
def add_defect(**row) -> dict:
    """Append a defect. Refuses a row that cannot be acted on or audited."""
    missing = [f for f in DEFECT_FIELDS if f not in row]
    if missing:
        raise LedgerError(f'defect is missing {missing}. Every field is '
                          f'required; an unknown one is written as null, so '
                          f'that "nobody checked" is visible rather than absent.')
    if row.get('scheduler_tier') not in TIERS:
        raise LedgerError(
            f'{row.get("id")}: scheduler_tier {row.get("scheduler_tier")!r} '
            f'not in {TIERS}. Declare it; a tier inferred from severity puts a '
            f'dark capture feed behind a refactor.')
    if row['severity'] not in SEVERITIES:
        raise LedgerError(f'severity {row["severity"]!r} not in {SEVERITIES}')
    if row['status'] not in (_ACTIONABLE | _PARKED | _TERMINAL):
        raise LedgerError(f'unknown status {row["status"]!r}')
    if not row.get('reproduction'):
        raise LedgerError(
            f'{row["id"]}: no reproduction. A defect nobody can reproduce is a '
            f'rumour, and this register is not for rumours.')
    if row['owner_approval_needed'] and not row.get('blocked_by'):
        raise LedgerError(
            f'{row["id"]}: owner_approval_needed is true with no blocked_by. '
            f'Name the APPROVAL id, or the row parks forever with nobody able '
            f'to tell what would unpark it.')
    if row['status'] == WAITING_OWNER and not row.get('blocked_by'):
        raise LedgerError(f'{row["id"]}: WAITING_OWNER with no blocked_by')
    ids = {d['id'] for d in defects()}
    if row['id'] in ids:
        raise LedgerError(f'{row["id"]} already exists')
    rows = defects() + [dict(row)]
    _write(DEFECT_LOG, rows)
    return row


_LIFECYCLE_RANK = {OPEN: 0, IN_PROGRESS: 1, OPERATING_RISK_ACTIVE: 1,
                   WAITING_OWNER: 1, EXTERNAL_BLOCKED: 1,
                   FIX_IMPLEMENTED: 2, FIX_DEPLOYED: 3, FIX_EXECUTED: 4,
                   VERIFIED: 5}


def amend_defect(defect_id: str, *, reason: str, **changes) -> dict:
    """Correct a row that was recorded wrongly, keeping proof it was.

    Demotion is the case this exists for. A status is a claim, and a claim
    that turns out to be false has to be withdrawable -- but silently
    rewriting the row would destroy the evidence it was ever overclaimed,
    which is exactly the thing the owner told us not to do when fixing
    defects. So every amendment appends to `amendments` with its reason, and
    the row carries its own history.

    It cannot be used to promote a row to VERIFIED: that still goes through
    close(), which demands a commit, a test, and the execution lineage. An
    amendment may lower a status, or raise it no further than FIX_EXECUTED.
    """
    if not reason or not reason.strip():
        raise LedgerError(f'{defect_id}: an amendment needs a reason. A status '
                          f'that changes with no recorded cause is indistinguishable '
                          f'from one that was never checked.')
    if changes.get('status') == VERIFIED:
        raise LedgerError(f'{defect_id}: amend_defect cannot mark VERIFIED. '
                          f'Use close(), which requires the execution lineage.')
    bad = set(changes) - set(DEFECT_FIELDS) - {'execution_lineage', 'execution_evidence'}
    if bad:
        raise LedgerError(f'{defect_id}: unknown field(s) {sorted(bad)}')
    rows = defects()
    for r in rows:
        if r['id'] != defect_id:
            continue
        before = {k: r.get(k) for k in changes}
        if 'status' in changes:
            old, newst = r.get('status'), changes['status']
            if newst not in _LIFECYCLE_RANK:
                raise LedgerError(f'{defect_id}: {newst!r} is not a lifecycle status')
            if _LIFECYCLE_RANK.get(newst, 0) > _LIFECYCLE_RANK.get(old, 0) + 1:
                raise LedgerError(
                    f'{defect_id}: cannot jump {old} -> {newst} by amendment. '
                    f'Each lifecycle step needs its own evidence.')
        r.setdefault('amendments', []).append(
            {'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'reason': reason, 'before': before, 'after': dict(changes)})
        r.update(changes)
        _write(DEFECT_LOG, rows)
        return r
    raise LedgerError(f'{defect_id}: no such defect')


def close(defect_id: str, *, fix_commit: str, verification_test: str,
          status: str = VERIFIED, execution_lineage: str = None,
          execution_evidence: str = None) -> dict:
    """Close a defect. Refuses without both a commit and a test.

    The owner's rule is that a row closes only after evidence proves closure.
    Without this the register slowly becomes a list of things somebody believed
    they had fixed.
    """
    if status not in _TERMINAL:
        raise LedgerError(f'{status!r} is not a closing status')
    if status == VERIFIED and not (fix_commit and verification_test):
        raise LedgerError(
            f'{defect_id}: VERIFIED needs both a fix_commit and a '
            f'verification_test. Use WONT_FIX with a reason if it is not '
            f'being fixed, but do not close it as done with nothing proving it.')
    if status == VERIFIED and not (execution_lineage and execution_evidence):
        raise LedgerError(
            f'{defect_id}: VERIFIED needs an execution_lineage and the '
            f'evidence the repair ran THERE. A passing test on a branch the '
            f'affected workflow does not read is FIX_IMPLEMENTED. DEF-047 '
            f'had thirteen green checks on a branch nothing executes while '
            f'the board stayed dead.')
    rows = defects()
    for r in rows:
        if r['id'] == defect_id:
            r.update(status=status, fix_commit=fix_commit,
                     verification_test=verification_test,
                     execution_lineage=execution_lineage,
                     execution_evidence=execution_evidence)
            _write(DEFECT_LOG, rows)
            return r
    raise LedgerError(f'{defect_id} not in the defect log')


def raise_approval(**row) -> dict:
    """Append an approval request. Refuses one the owner cannot act on."""
    missing = [f for f in APPROVAL_FIELDS if f not in row]
    if missing:
        raise LedgerError(f'approval is missing {missing}')
    if row['urgency'] not in URGENCIES:
        raise LedgerError(f'urgency {row["urgency"]!r} not in {URGENCIES}')
    if not row.get('options') or len(row['options']) < 2:
        raise LedgerError(
            f'{row["id"]}: an approval needs at least two options. A request '
            f'with one option is a notification pretending to be a decision.')
    if not row.get('work_that_continues_regardless'):
        raise LedgerError(
            f'{row["id"]}: name what continues regardless. Every approval '
            f'raised without it invites the reading that everything stops.')
    if row['id'] in {a['id'] for a in approvals()}:
        raise LedgerError(f'{row["id"]} already exists')
    _write(APPROVAL_QUEUE, approvals() + [dict(row)])
    return row


def decide(approval_id: str, *, decision: str, resulting_commit=None,
           note=None) -> dict:
    """Record the owner's verdict, and what it actually said.

    `decision` is one of three words. `note` is why, in the owner's terms,
    plus any condition attached to it -- an approval of one option and not
    another, a scope limit, a thing deliberately deferred. Without it the
    ledger keeps the word APPROVED and forgets that LIVE was excluded, which
    is exactly the detail a later reader would need and could not recover.
    """
    if decision not in (APPROVED, REJECTED, WITHDRAWN):
        raise LedgerError(f'{decision!r} is not a decision')
    rows = approvals()
    for r in rows:
        if r['id'] == approval_id:
            r.update(status=decision, owner_decision=decision,
                     decision_timestamp=_now(),
                     resulting_commit=resulting_commit,
                     decision_note=(note or ''))
            _write(APPROVAL_QUEUE, rows)
            return r
    raise LedgerError(f'{approval_id} not in the approval queue')


# ---- reading --------------------------------------------------------------
def blocked_by(approval_id: str, rows=None) -> list:
    rows = defects() if rows is None else rows
    return sorted(d['id'] for d in rows
                  if d.get('blocked_by') == approval_id
                  and d['status'] not in _TERMINAL)


def actionable(rows=None) -> list:
    """Open work needing no owner decision, in scheduler order.

    Tier first, severity second. An OPERATING_RISK_ACTIVE row in T2 therefore
    outranks a CRITICAL in T3, which is the whole reason the tier exists.
    """
    rows = defects() if rows is None else rows
    live = [d for d in rows if d['status'] in _ACTIONABLE
            and not d.get('owner_approval_needed')]
    return sorted(live, key=lambda d: (
        TIERS.index(d['scheduler_tier']) if d.get('scheduler_tier') in TIERS
        else len(TIERS),
        SEVERITIES.index(d['severity']), d['id']))


def workstreams(rows=None) -> dict:
    """subsystem -> count, over actionable work only.

    WHY BREADTH AND NOT JUST A COUNT. Owner ruling 2026-09-25: twenty-one tasks
    could all sit in one subsystem, in which case one bad assumption about that
    subsystem stalls everything and the count was never evidence of room to
    work. Distinct subsystems is a crude proxy for independent branches and is
    honest about being one -- two rows in `capture` may still share a cause.
    """
    rows = actionable(rows)
    out = {}
    for d in rows:
        out[d['subsystem']] = out.get(d['subsystem'], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def next_action(rows=None) -> dict | None:
    a = actionable(rows)
    return a[0] if a else None


def should_escalate(approval: dict, rows=None) -> str | None:
    """A REASON to interrupt the owner, or None. Raising one is NOT a reason.

    Under the 2026-09-25 directive an approval is queued, not announced. The
    only things that earn an interruption are the narrow set below, and "it was
    created" and "it is still open" are neither.
    """
    if approval['status'] != RAISED:
        return None
    rows = defects() if rows is None else rows
    if not actionable(rows):
        return 'it is the last thing standing: no authorized work remains'
    if approval.get('irreversible_if_missed') and approval.get('deadline'):
        try:
            d = dt.datetime.fromisoformat(str(approval['deadline']))
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            hours = (d - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600
            if hours <= IMMINENT_H:
                return (f'deadline in {hours:.0f}h and missing it is '
                        f'irreversible or takes production down')
        except ValueError:
            pass
    return None


def autonomy_state(rows=None, apps=None) -> dict:
    """The derived summary. `global_stop_required` is computed, never asserted."""
    rows = defects() if rows is None else rows
    apps = approvals() if apps is None else apps
    act = actionable(rows)
    waiting = [d for d in rows if d['status'] == WAITING_OWNER]
    external = [d for d in rows if d['status'] == EXTERNAL_BLOCKED]
    open_apps = [a for a in apps if a['status'] == RAISED]
    reasons = []
    if not act:
        if waiting:
            reasons.append('every remaining task waits on an owner decision')
        if external:
            reasons.append('every remaining task waits on an external '
                           'dependency')
        if not waiting and not external:
            reasons.append('no valid next action remains')
    # A ROW PARKED ON A DECIDED APPROVAL IS AUTHORIZED WORK IN HIDING.
    # Found 2026-09-25 by a test: APPROVAL-002 was approved and DEF-040 stayed
    # WAITING_OWNER, so the scheduler could not see work the owner had already
    # cleared. That is the exact failure this whole separation exists to
    # prevent, occurring inside it.
    decided = {a['id'] for a in apps if a['status'] != RAISED}
    stale_blocks = sorted(d['id'] for d in rows
                          if d['status'] == WAITING_OWNER
                          and d.get('blocked_by') in decided)
    ws = workstreams(rows)
    risks = [d['id'] for d in rows if d['status'] == OPERATING_RISK_ACTIVE]
    state = {
        'spec_version': SPEC_VERSION,
        'generated_utc': _now(),
        'active_work_count': len([d for d in rows
                                  if d['status'] in _ACTIONABLE]),
        'valid_next_actions': len(act),
        'independent_workstreams': len(ws),
        'workstreams': ws,
        'owner_blocked_branches': len({d['blocked_by'] for d in rows
                                       if d['status'] == WAITING_OWNER
                                       and d.get('blocked_by')}),
        'operating_risk_active': risks,
        'stale_owner_blocks': stale_blocks,
        'next_tier': (act[0]['scheduler_tier'] if act else None),
        'waiting_owner_count': len(waiting),
        'external_blocked_count': len(external),
        'open_approvals': [a['id'] for a in open_apps],
        'verified_count': len([d for d in rows if d['status'] == VERIFIED]),
        'runnable_now': len(act),
        'waiting_owner': [d['id'] for d in waiting],
        'waiting_external': [d['id'] for d in external],
        'global_stop_required': bool(reasons),
        'global_stop_reasons': reasons,
        'next_action': (act[0]['id'] if act else None),
        'escalations_due': [
            {'id': a['id'], 'reason': r}
            for a in open_apps
            for r in [should_escalate(a, rows)] if r],
        'reading': (
            'global_stop_required is computed from counts. An open approval '
            'parks its own branch and nothing else; if valid_next_actions is '
            'above zero there is authorized work and stopping is a choice, '
            'not a state.'),
    }
    if state['global_stop_required'] and not state['global_stop_reasons']:
        raise LedgerError('refusing to report a stop with no named reason')
    # OWNER_INTERRUPT_REQUIRED DEFAULTS TO FALSE AND AN OPEN APPROVAL NEVER
    # SETS IT. It is true only when the project genuinely cannot proceed, or
    # when a deadline is imminent AND missing it is irreversible.
    esc = state['escalations_due']
    state['owner_interrupt_required'] = bool(
        state['global_stop_required'] or esc)
    state['owner_interrupt_reason'] = (
        '; '.join(state['global_stop_reasons'])
        or '; '.join(f"{e['id']}: {e['reason']}" for e in esc)
        or None)
    if state['owner_interrupt_required'] and not \
            state['owner_interrupt_reason']:
        raise LedgerError(
            'refusing to demand an interruption with no named reason')
    return state


def write_state(path: Path = AUTONOMY_STATE) -> dict:
    s = autonomy_state()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s, indent=1, sort_keys=True) + '\n')
    return s
