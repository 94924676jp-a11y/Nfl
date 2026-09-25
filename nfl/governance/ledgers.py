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

#: Statuses from which no further work can be pulled.
_TERMINAL = frozenset({VERIFIED, WONT_FIX})
#: Statuses that are open work Claude may act on right now.
_ACTIONABLE = frozenset({OPEN, IN_PROGRESS})
#: Statuses that are open and NOT actionable.
_PARKED = frozenset({WAITING_OWNER, EXTERNAL_BLOCKED})

RAISED = 'RAISED'
APPROVED = 'APPROVED'
REJECTED = 'REJECTED'
WITHDRAWN = 'WITHDRAWN'

SEVERITIES = ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
URGENCIES = ('BLOCKING_NOW', 'DATED', 'WHENEVER')

DEFECT_FIELDS = (
    'id', 'date_discovered', 'subsystem', 'severity', 'defect',
    'reproduction', 'affected', 'impact', 'next_action',
    'owner_approval_needed', 'blocked_by', 'status', 'fix_commit',
    'verification_test', 'prospective_validation_needed')

APPROVAL_FIELDS = (
    'id', 'date_raised', 'decision_required', 'why_owner_approval',
    'options', 'recommended_default', 'if_approved', 'if_not_approved',
    'work_that_continues_regardless', 'urgency', 'deadline',
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


def close(defect_id: str, *, fix_commit: str, verification_test: str,
          status: str = VERIFIED) -> dict:
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
    rows = defects()
    for r in rows:
        if r['id'] == defect_id:
            r.update(status=status, fix_commit=fix_commit,
                     verification_test=verification_test)
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


def decide(approval_id: str, *, decision: str, resulting_commit=None) -> dict:
    if decision not in (APPROVED, REJECTED, WITHDRAWN):
        raise LedgerError(f'{decision!r} is not a decision')
    rows = approvals()
    for r in rows:
        if r['id'] == approval_id:
            r.update(status=decision, owner_decision=decision,
                     decision_timestamp=_now(),
                     resulting_commit=resulting_commit)
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
    """Open work needing no owner decision, severity-ordered."""
    rows = defects() if rows is None else rows
    live = [d for d in rows if d['status'] in _ACTIONABLE
            and not d.get('owner_approval_needed')]
    return sorted(live, key=lambda d: (SEVERITIES.index(d['severity']),
                                       d['id']))


def next_action(rows=None) -> dict | None:
    a = actionable(rows)
    return a[0] if a else None


def should_escalate(approval: dict, rows=None) -> str | None:
    """A REASON to interrupt the owner again, or None.

    Announced once when raised. After that, only four things earn a second
    mention, and "it is still open" is not one of them.
    """
    if approval['status'] != RAISED:
        return None
    if not approval.get('last_escalated_at'):
        return 'first raise'
    rows = defects() if rows is None else rows
    # ORDER MATTERS AND IS BY CONSEQUENCE, NOT BY CONVENIENCE. Several of
    # these are true at once in the case that matters most: an approval that
    # has accumulated blocked work until nothing else can proceed satisfies
    # both the third rule and the first. Reporting "more work is blocked"
    # there would bury the fact that the project has actually stopped, so the
    # strongest reason is checked first.
    if not actionable(rows):
        return 'it is the last thing standing'
    if approval.get('urgency') == 'BLOCKING_NOW':
        return 'urgency is BLOCKING_NOW'
    if approval.get('deadline'):
        try:
            d = dt.datetime.fromisoformat(approval['deadline'])
            if d.tzinfo is None:
                d = d.replace(tzinfo=dt.timezone.utc)
            days = (d - dt.datetime.now(dt.timezone.utc)).days
            if days <= 7:
                return f'deadline in {days} day(s)'
        except ValueError:
            pass
    now_blocked = blocked_by(approval['id'], rows)
    was = approval.get('blocked_ids_at_last_escalation') or []
    if len(now_blocked) > len(was):
        return (f'more work is now blocked by it: {len(was)} -> '
                f'{len(now_blocked)}')
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
    state = {
        'spec_version': SPEC_VERSION,
        'generated_utc': _now(),
        'active_work_count': len([d for d in rows
                                  if d['status'] in _ACTIONABLE]),
        'valid_next_actions': len(act),
        'waiting_owner_count': len(waiting),
        'external_blocked_count': len(external),
        'open_approvals': [a['id'] for a in open_apps],
        'verified_count': len([d for d in rows if d['status'] == VERIFIED]),
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
    return state


def write_state(path: Path = AUTONOMY_STATE) -> dict:
    s = autonomy_state()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s, indent=1, sort_keys=True) + '\n')
    return s
