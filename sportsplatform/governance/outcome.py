"""The explicit-state primitive. Rule 001 made executable.

Every V7 defect found on 2026-09-01 was one failure: something returned
nothing, or something partial, and the caller read it as success. Eight of
them, in eight different modules, written by different people at different
times. That is not a discipline problem that more review would have caught --
it is what happens when "returned without raising" is allowed to mean "worked".

So V8 has no bare returns on any stage boundary. A stage returns an Outcome,
an Outcome always carries a named code, and there is no way to spell "it went
fine" without saying which of the five states it is.

    PASS            it worked, and here is the value
    FAIL            it did not work, and this is why
    BLOCKED         it could not run, and this is what is missing
    DEFERRED        not yet, and it remains OWED until something closes it
    NOT_APPLICABLE  there was nothing here to do, and this is why that is fine

DEFERRED is the one people leave out, and leaving it out is what made V7's
first live batch abort: "lineups have not posted yet" was filed as a bug
because there was no state for "not yet". A deferral is not a quiet failure --
it is a debt, and V8 tracks it as one.

NOT_APPLICABLE is the other trap. It is the honest answer to "no games today",
and it is also the most attractive lie for a stage that has broken. It is
therefore the only state that requires evidence for WHY nothing applied.
"""
from __future__ import annotations

import dataclasses
import enum
import json
from typing import Any, Mapping


class SilentSuccess(RuntimeError):
    """Raised when something tries to pass off an absence as a result."""


class OutcomeError(RuntimeError):
    """Raised when an Outcome is malformed or unwrapped wrongly."""


class State(str, enum.Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    BLOCKED = 'BLOCKED'
    DEFERRED = 'DEFERRED'
    NOT_APPLICABLE = 'NOT_APPLICABLE'

    @property
    def is_terminal(self) -> bool:
        """DEFERRED is the only state that leaves work outstanding."""
        return self is not State.DEFERRED


class Cause(str, enum.Enum):
    """WHY a thing is BLOCKED. A subtype, deliberately not a sixth state.

    Part 2 of the 2026-09-02 reconciliation asked whether BLOCKED needs a reason
    field or a new top-level state. Reason field, for one reason that decides it:
    every one of these means the same thing to a caller -- the work did not run
    and produced no verdict. Splitting that into separate states would make every
    consumer learn a second vocabulary to express one concept, which is the
    "two competing state systems" outcome the reconciliation exists to prevent.

    What the subtype buys is the distinction that actually matters and that a
    single BLOCKED cannot make: a NETWORK block is not evidence about the model,
    and an ENVIRONMENT block is not evidence about the code. run_suite.py
    currently recovers that distinction by grepping stderr for
    'fetch failed after 3 attempts', which works until an error message is
    reworded. A declared cause is the structured version of that string match.

    NETWORK      egress refused, DNS, timeout, proxy. Says nothing about us.
    ENVIRONMENT  interpreter, platform, missing binary. Same commit, different box.
    DEPENDENCY   an upstream stage did not produce what this one needs.
    DATA         the input exists but is empty, malformed, or out of contract.
    GOVERNANCE   a rule refused it. The only cause that is a decision, not a defect.
    """

    NETWORK = 'NETWORK'
    ENVIRONMENT = 'ENVIRONMENT'
    DEPENDENCY = 'DEPENDENCY'
    DATA = 'DATA'
    GOVERNANCE = 'GOVERNANCE'


_SENTINEL = object()


@dataclasses.dataclass(frozen=True)
class Outcome:
    """A result that cannot be mistaken for an absence.

    `code` is mandatory and is never a free-text sentence. It is the stable
    name a reader greps for and a config declares; the sentence goes in
    `detail`. V7 proved the difference matters: a refusal whose code was
    reused for two different causes sent an operator to the wrong place.
    """
    state: State
    code: str
    detail: str = ''
    evidence: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    value: Any = None

    def __post_init__(self):
        if not isinstance(self.state, State):
            raise OutcomeError(f'OUTCOME_STATE_INVALID: {self.state!r}')
        if not self.code or not isinstance(self.code, str):
            raise OutcomeError(
                f'OUTCOME_CODE_MISSING: a {self.state.value} with no code is '
                f'an unnamed result, which is what this class exists to '
                f'prevent.')
        if self.code != self.code.upper() or ' ' in self.code:
            raise OutcomeError(
                f'OUTCOME_CODE_MALFORMED: {self.code!r} must be an UPPER_SNAKE '
                f'name, not a sentence. The sentence belongs in detail.')
        if self.state is State.NOT_APPLICABLE and not self.detail:
            raise OutcomeError(
                'NOT_APPLICABLE_UNEXPLAINED: "nothing to do here" is the most '
                'attractive thing for a broken stage to claim, so it is the '
                'one state that must say why nothing applied.')

    # -- constructors, one per state, so the state is always chosen on purpose
    @classmethod
    def ok(cls, code: str, value: Any = _SENTINEL, detail: str = '',
           **evidence) -> 'Outcome':
        if value is _SENTINEL:
            raise OutcomeError(
                f'PASS_WITHOUT_VALUE: {code} claims success but carries no '
                f'value. If there is genuinely nothing to return, the state is '
                f'NOT_APPLICABLE with a reason, not PASS.')
        return cls(State.PASS, code, detail, evidence, value)

    @classmethod
    def fail(cls, code: str, detail: str, **evidence) -> 'Outcome':
        return cls(State.FAIL, code, detail, evidence)

    @classmethod
    def blocked(cls, code: str, detail: str, *, cause: 'Cause',
                **evidence) -> 'Outcome':
        """BLOCKED, and it must say why.

        `cause` is keyword-only with NO default. A default would be picked once
        by whoever wrote the line and then be wrong everywhere else, and the
        specific wrong answer that matters is a network refusal recorded as a
        result about the model.
        """
        if not isinstance(cause, Cause):
            raise OutcomeError(
                f'BLOCKED_CAUSE_UNDECLARED: {code} was blocked without a '
                f'declared Cause (got {cause!r}). Choose from '
                f'{[c.value for c in Cause]}. "Blocked" alone cannot tell a '
                f'reader whether the model failed, the box failed, or a rule '
                f'refused -- and those have opposite consequences.')
        ev = dict(evidence)
        ev['cause'] = cause.value
        return cls(State.BLOCKED, code, detail, ev)

    @classmethod
    def deferred(cls, code: str, detail: str, owed: Any = None,
                 **evidence) -> 'Outcome':
        ev = dict(evidence)
        ev['owed'] = owed
        return cls(State.DEFERRED, code, detail, ev)

    @classmethod
    def not_applicable(cls, code: str, detail: str, **evidence) -> 'Outcome':
        return cls(State.NOT_APPLICABLE, code, detail, evidence)

    # -- reading it
    def __bool__(self):
        raise OutcomeError(
            f'OUTCOME_TRUTHINESS: refusing to let {self.code} be tested as a '
            f'boolean. `if result:` is exactly how a FAIL becomes a silent '
            f'success. Test `result.state is State.PASS` explicitly.')

    def unwrap(self) -> Any:
        """The value, or a raise naming the state. Never a default."""
        if self.state is not State.PASS:
            raise SilentSuccess(
                f'{self.code}: cannot unwrap a {self.state.value}. '
                f'{self.detail}')
        return self.value

    def as_dict(self) -> dict:
        return {'state': self.state.value, 'code': self.code,
                'detail': self.detail, 'evidence': dict(self.evidence)}

    def __str__(self):
        return f'{self.state.value}[{self.code}] {self.detail}'.strip()


# ---------------------------------------------------------------------------
def explicit(value: Any, code: str, what: str, *,
             allow_empty: bool = False) -> Outcome:
    """Turn a raw value into a state, refusing anything indistinguishable
    from an absence.

    `allow_empty` exists because a numeric 0 is a legitimate measurement while
    an empty container is an absence wearing a result's costume -- V7 already
    learned that one: before it was fixed, a stage could record 400 empty lists
    and close at 100% coverage. Passing allow_empty=True is a claim that the
    caller has thought about which of those this is.
    """
    if value is None:
        return Outcome.blocked(
            code, f'{what} returned None, which cannot be distinguished from '
                  f'a failure that did not raise.', cause=Cause.DATA)
    if not allow_empty and not isinstance(value, (int, float, bool)):
        try:
            if len(value) == 0:
                return Outcome.blocked(
                    code, f'{what} returned an empty {type(value).__name__}. '
                          f'An empty container is an absence, not a result. If '
                          f'emptiness is the real answer here, say so with '
                          f'NOT_APPLICABLE and a reason.', cause=Cause.DATA)
        except TypeError:
            pass
    return Outcome.ok(code, value, detail=f'{what} produced a value')


def neither_result_nor_error(payload: Mapping, code: str,
                             what: str) -> Outcome | None:
    """Catch the shape that ate 39 research fetches.

    v7's f1/f2/f5/q1/q3.json each held entries with `content: None` AND
    `error: None` -- calls that returned nothing, reported nothing, and were
    written to disk as though they had worked. Any envelope with a result slot
    and an error slot can produce that shape, so it gets its own check.
    """
    has_result = payload.get('content') is not None or \
        payload.get('result') is not None or payload.get('data') is not None
    has_error = payload.get('error') is not None
    if not has_result and not has_error:
        return Outcome.blocked(
            code, f'{what} returned neither a result nor an error. That is not '
                  f'an empty answer, it is an unreported failure, and writing '
                  f'it down as data is how it survives.',
            cause=Cause.DATA, keys=sorted(payload))
    return None


def require(outcome: Outcome) -> Any:
    """Unwrap, or raise. The only sanctioned way to consume a stage result."""
    if not isinstance(outcome, Outcome):
        raise SilentSuccess(
            f'STAGE_RETURNED_BARE_VALUE: expected an Outcome, got '
            f'{type(outcome).__name__}. A stage that returns a bare value has '
            f'no way to say BLOCKED or DEFERRED, so every absence it meets '
            f'will be read as success.')
    return outcome.unwrap()


def combine(outcomes: Mapping[str, Outcome], code: str) -> Outcome:
    """Roll several stage results into one, worst-first and never averaged.

    Order is deliberate: any FAIL or BLOCKED dominates, then DEFERRED, and only
    an all-clear reads as PASS. Nothing is summarised away -- the whole census
    rides in the evidence so a reader can see which stage produced which state
    rather than trusting the rollup.
    """
    if not outcomes:
        return Outcome.blocked(
            code, 'nothing to combine; an empty census is not an all-clear.',
            cause=Cause.DEPENDENCY)
    census = {k: o.state.value for k, o in outcomes.items()}
    bad = {k: o for k, o in outcomes.items()
           if o.state in (State.FAIL, State.BLOCKED)}
    if bad:
        first = sorted(bad)[0]
        return Outcome(bad[first].state, code,
                       f'{len(bad)} of {len(outcomes)} did not pass: '
                       f'{sorted(bad)}', {'census': census})
    owed = {k: o for k, o in outcomes.items() if o.state is State.DEFERRED}
    if owed:
        return Outcome.deferred(
            code, f'{len(owed)} of {len(outcomes)} deferred and still owed: '
                  f'{sorted(owed)}', owed=sorted(owed), census=census)
    return Outcome.ok(code, census, detail=f'all {len(outcomes)} accounted for',
                      census=census)
