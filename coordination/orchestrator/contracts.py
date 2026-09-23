#!/usr/bin/env python3.12
"""The vocabulary of the autonomous runtime. Nothing here performs an action.

Every type in this file exists so that a thing that went wrong has a NAME. The
failure mode this runtime is built against is not an agent doing something
dramatic; it is an agent producing nothing and the loop reading that as
success, then spending eight more calls reasoning past it. `sportsplatform`
already has `Outcome` for exactly that reason and this module does not
reimplement it -- it adds the three vocabularies `Outcome` does not carry:
which worker, which escalation, and which decision.

WHY ESCALATION IS AN ENUM AND NOT A BOOLEAN. "Needs a human" is not one state.
A missing secret is fixed in thirty seconds by the owner; a governance conflict
may not be fixable at all; a reserved decision must never be fixed by an agent
however capable it becomes. Collapsing those into `halted: true` throws away
the only information the owner needs in order to act, which is WHAT to do next.
"""
from __future__ import annotations

import dataclasses
import enum
import hashlib
import json


# --------------------------------------------------------------- workers
class Transport(str, enum.Enum):
    """HOW a worker is reached. Orthogonal to WHO the worker is.

    `ANTHROPIC_API` is a synchronous HTTP call inside this process.
    `CLAUDE_CODE_ACTION` is a separate GitHub job that edits the working tree
    and reports through `structured_output`. They are not two branches of one
    function; they are different shapes of execution, and the second is a
    delegation rather than a call.
    """

    ANTHROPIC_API = 'ANTHROPIC_API'
    CLAUDE_CODE_ACTION = 'CLAUDE_CODE_ACTION'
    OPENAI_API = 'OPENAI_API'
    PERPLEXITY_API = 'PERPLEXITY_API'


class Worker(str, enum.Enum):
    """Who is allowed to do what. The authority split is the whole design."""

    OWNER = 'OPENAI'          # review, decide, authorize -- never writes code
    ENGINEER = 'ANTHROPIC'    # writes code for ONE authorized task
    RESEARCH = 'PERPLEXITY'   # reads the outside world -- authorizes nothing


#: Queue file -> the worker that may execute its tasks. A task cannot be routed
#: anywhere else, so a research task can never reach the engineering worker by
#: being mislabelled in a prompt.
ROUTING = {
    'ENGINEERING_QUEUE.json': Worker.ENGINEER,
    'RESEARCH_QUEUE.json': Worker.RESEARCH,
}


# ------------------------------------------------------------ escalation
class Escalation(str, enum.Enum):
    """Why the loop stopped and handed back to the owner.

    Each of these STOPS the loop. None of them is retried automatically, and
    two of them (GOVERNANCE_CONFLICT, OWNER_DECISION_REQUIRED) must not be
    retried even manually without the owner changing something first.
    """

    OWNER_DECISION_REQUIRED = 'OWNER_DECISION_REQUIRED'
    RIGHTS_DECISION_REQUIRED = 'RIGHTS_DECISION_REQUIRED'
    PURCHASE_REQUIRED = 'PURCHASE_REQUIRED'
    SECRET_MISSING = 'SECRET_MISSING'
    GOVERNANCE_CONFLICT = 'GOVERNANCE_CONFLICT'
    UNKNOWN_BLOCKING_EVIDENCE = 'UNKNOWN_BLOCKING_EVIDENCE'
    COST_LIMIT_REACHED = 'COST_LIMIT_REACHED'
    #: A key is present but rejected, or the model id is not one this account
    #: may call. NOT an agent failure: no number of retries fixes an
    #: entitlement, and calling it REPEATED_AGENT_FAILURE would send the owner
    #: looking at the worker instead of at their provider console.
    PROVIDER_ACCESS_DENIED = 'PROVIDER_ACCESS_DENIED'
    #: CLAUDE_CODE_OAUTH_TOKEN is not set. Distinct from SECRET_MISSING so the
    #: owner is sent to `claude setup-token` rather than to an API console.
    CLAUDE_OAUTH_MISSING = 'CLAUDE_OAUTH_MISSING'
    #: The token is present and the Action rejected it -- expired, revoked, or
    #: issued for a different account. Retrying a rejected token is how a
    #: subscription gets locked, so this never auto-retries.
    CLAUDE_OAUTH_REJECTED = 'CLAUDE_OAUTH_REJECTED'
    REPEATED_AGENT_FAILURE = 'REPEATED_AGENT_FAILURE'
    DESTRUCTIVE_ACTION_REQUIRED = 'DESTRUCTIVE_ACTION_REQUIRED'
    STATE_CONTRADICTORY = 'STATE_CONTRADICTORY'
    TRANSITION_BUDGET_SPENT = 'TRANSITION_BUDGET_SPENT'
    NOTHING_AUTHORIZED = 'NOTHING_AUTHORIZED'


#: Escalations that must NEVER be auto-retried, even on a later invocation,
#: until a human changes the repository. A retry here is the loop trying to
#: argue with a decision, which is exactly the token-burn the owner called out.
NEVER_AUTO_RETRY = frozenset({
    Escalation.PROVIDER_ACCESS_DENIED,
    Escalation.CLAUDE_OAUTH_MISSING,
    Escalation.CLAUDE_OAUTH_REJECTED,
    Escalation.OWNER_DECISION_REQUIRED,
    Escalation.RIGHTS_DECISION_REQUIRED,
    Escalation.PURCHASE_REQUIRED,
    Escalation.GOVERNANCE_CONFLICT,
    Escalation.DESTRUCTIVE_ACTION_REQUIRED,
    Escalation.STATE_CONTRADICTORY,
})

#: Escalations that are a clean stop rather than a problem: the loop reached
#: the end of the authorized work. Reported, not alarmed about.
BENIGN = frozenset({Escalation.NOTHING_AUTHORIZED,
                    Escalation.TRANSITION_BUDGET_SPENT})


# ----------------------------------------------------- owner's verdicts
class Verdict(str, enum.Enum):
    """What the owner worker is allowed to conclude about a return."""

    ACCEPT = 'ACCEPT'                    # RETURNED -> COMPLETE
    RETURN_FOR_CORRECTION = 'RETURN_FOR_CORRECTION'   # -> AUTHORIZED again
    BLOCK = 'BLOCK'                      # -> BLOCKED, with a reason
    ESCALATE = 'ESCALATE'                # hand to the human, loop stops


#: Things no worker may do, whatever a model returns and however it is phrased.
#: These are checked MECHANICALLY against the diff and the state, never by
#: asking a model whether it obeyed them. A guard that consists of telling a
#: model not to do something is a convention, not a control.
RESERVED_FOR_HUMAN = (
    'promote Q9',
    'authorize NFL-1',
    'declare V2 earned',
    'remove an owner decision',
    'weaken a governance gate',
    'make sportsbook information predictive',
    'treat UNKNOWN evidence as passing',
    'set the weekly exposure cap',
    'enable real money',
)

#: Repository paths no autonomous worker may modify. The owner worker may
#: PROPOSE a change to these in CHATGPT_OUTBOX; it may not make one.
#: `enforce_protected_paths` in `locks.py` is what actually refuses.
PROTECTED_PATHS = (
    'coordination/OWNER_DECISIONS.md',
    'coordination/AUTOMATION_POLICY.json',
    'coordination/orchestrator/MODELS.json',
    'nfl/production/authorization.py',
    'nfl/production/review/gate.py',
    '.github/workflows/',
)

#: Paths the ENGINEERING worker may never touch, on top of PROTECTED_PATHS.
#: It writes code and tests; it does not write its own queue record or its own
#: marching orders.
ENGINEER_FORBIDDEN_PATHS = (
    'coordination/ENGINEERING_QUEUE.json',
    'coordination/RESEARCH_QUEUE.json',
    'coordination/PROJECT_STATE.json',
    'coordination/CHATGPT_OUTBOX/',
    'coordination/HANDOFF_LOG.jsonl',
)


# ----------------------------------------------------------- structures
@dataclasses.dataclass(frozen=True)
class WorkerCall:
    """One provider call, described BEFORE it is made.

    `idempotency_key` is derived from the content of the request rather than
    from a clock, so the same task in the same repository state produces the
    same key. That is what makes duplicate detection work across two workflow
    runs that raced -- a timestamp would make every retry look new.
    """

    worker: Worker
    model: str
    task_id: str
    prompt_sha256: str
    head_before: str
    attempt: int

    @property
    def idempotency_key(self) -> str:
        body = json.dumps({'w': self.worker.value, 'm': self.model,
                           't': self.task_id, 'p': self.prompt_sha256,
                           'h': self.head_before, 'a': self.attempt},
                          sort_keys=True)
        return hashlib.sha256(body.encode()).hexdigest()[:32]


@dataclasses.dataclass
class WorkerResult:
    """What came back, and whether it is usable. NEVER inferred.

    `ok` is False for an API error, a timeout, a malformed body, an empty body
    and a refusal. There is deliberately no path that turns any of those into
    True, because the single most expensive recurring defect in this project is
    a step that returned nothing being read as a step that succeeded.
    """

    call: WorkerCall
    ok: bool
    code: str
    detail: str = ''
    raw: dict = dataclasses.field(default_factory=dict)
    parsed: dict = dataclasses.field(default_factory=dict)
    usage: dict = dataclasses.field(default_factory=dict)
    escalation: Escalation | None = None

    @classmethod
    def failure(cls, call, code, detail, raw=None, escalation=None):
        return cls(call=call, ok=False, code=code, detail=detail,
                   raw=raw or {}, escalation=escalation)


#: The sections a normalized engineering return must carry. Identical to
#: `claude_finalize.REQUIRED_SECTIONS` and imported from there at runtime so
#: the two cannot drift; repeated here only as documentation of the contract.
ENGINEER_RETURN_SECTIONS = (
    'work performed', 'evidence', 'tests', 'failures', 'changed files',
    'commit sha', 'blockers', 'recommended next action')

#: The sections a normalized research return must carry.
RESEARCH_RETURN_SECTIONS = (
    'findings', 'evidence', 'source list', 'evidence classifications',
    'unresolved questions', 'implications', 'recommended next action')

#: Per-claim confidence vocabulary, shared with `nfl/dfs/history/contracts.py`.
#: UNKNOWN is a real answer and stays one.
EVIDENCE_CLASSES = ('VERIFIED_PRIMARY', 'VERIFIED_INDEPENDENTLY',
                    'PROVIDER_CLAIM', 'PRACTITIONER_REPORT',
                    'COMMUNITY_REPORT', 'UNKNOWN')


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
