"""A governed assumption: a claim the model makes that could be wrong.

WHY AN OBJECT AND NOT A COMMENT

Every model carries assumptions. The ones that hurt are not the ones nobody
thought of -- they are the ones somebody wrote down in a docstring, nobody
attached a measurement to, and everybody downstream then relied on. CS2's
`p_appears` reaching exactly 1.0 was written down the hour it was built. It
was still a sentence in a module, and a sentence cannot block a promotion.

An assumption here is a record with a TESTABLE claim, a POPULATION the claim
is about, a FALSIFIER stated before the test runs, and a list of what breaks
if it is false. Its status may only move on recorded evidence.

THE FIELDS, AND WHY EACH IS REQUIRED

  claim                   what is being asserted, in one sentence, in the
                          indicative. "Appearance certainty is real" is not a
                          claim; "a player with a perfect prior-season
                          appearance record appears with probability 1" is.
  estimand                the quantity that would settle it, written as a
                          probability or an expectation over a named
                          conditioning set. Without this, two people measure
                          two different things and both feel vindicated.
  population              who and when. A claim true of starters and false of
                          the roster is not "mostly true"; it is a claim about
                          starters.
  evidence                what has actually been measured, with sample sizes.
                          Empty until something runs.
  test                    the executable that produces `evidence`. A dotted
                          path, so the claim cannot drift from its check.
  uncertainty             the interval or the reason there is none. An
                          estimate without one invites a story.
  falsifier               WRITTEN BEFORE THE TEST. The condition under which
                          this assumption is wrong. A falsifier chosen after
                          seeing the result is not a falsifier.
  status                  DECLARED -> SUPPORTED | FALSIFIED | UNTESTABLE,
                          and only on recorded evidence.
  downstream_dependencies what consumes it. This is what makes a falsified
                          assumption actionable rather than interesting.
  criticality             CRITICAL blocks production when falsified. MATERIAL
                          warns. MINOR records.

WHAT THIS MODULE REFUSES TO DO

It does not repair a model, clip a value, or choose a floor. A falsified
assumption BLOCKS a promotion and leaves the model output exactly as it was,
because silently correcting an output on the strength of an audit is how a
number nobody can reproduce enters the pipeline.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402

SPEC_VERSION = 'governed-assumption-1'

DECLARED = 'DECLARED'
SUPPORTED = 'SUPPORTED'
FALSIFIED = 'FALSIFIED'
UNTESTABLE = 'UNTESTABLE'
WITHDRAWN = 'WITHDRAWN'
STATUSES = (DECLARED, SUPPORTED, FALSIFIED, UNTESTABLE, WITHDRAWN)

#: A status may only move along these edges, and only with evidence attached.
TRANSITIONS = {
    DECLARED: (SUPPORTED, FALSIFIED, UNTESTABLE, WITHDRAWN),
    SUPPORTED: (FALSIFIED, WITHDRAWN),
    FALSIFIED: (SUPPORTED, WITHDRAWN),
    UNTESTABLE: (SUPPORTED, FALSIFIED, WITHDRAWN),
    WITHDRAWN: (),
}

CRITICAL = 'CRITICAL'
MATERIAL = 'MATERIAL'
MINOR = 'MINOR'
CRITICALITIES = (CRITICAL, MATERIAL, MINOR)

CODE_INVALID = 'ASSUMPTION_RECORD_INVALID'
CODE_BLOCKED = 'PROMOTION_BLOCKED_BY_FALSIFIED_ASSUMPTION'
CODE_UNTESTED = 'PROMOTION_BLOCKED_BY_UNTESTED_CRITICAL_ASSUMPTION'
CODE_BAD_MOVE = 'ASSUMPTION_STATUS_MOVE_REFUSED'

#: Fields that must be present and non-empty on every record.
REQUIRED = ('id', 'claim', 'estimand', 'population', 'test', 'falsifier',
            'status', 'criticality', 'downstream_dependencies')


@dataclasses.dataclass(frozen=True)
class Assumption:
    id: str
    claim: str
    estimand: str
    population: str
    test: str
    falsifier: str
    downstream_dependencies: tuple
    criticality: str = MATERIAL
    status: str = DECLARED
    evidence: dict = dataclasses.field(default_factory=dict)
    uncertainty: str = ''
    declared_at_utc: str = ''
    notes: str = ''

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d['downstream_dependencies'] = list(self.downstream_dependencies)
        d['spec_version'] = SPEC_VERSION
        return d


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def validate(a: Assumption) -> Outcome:
    """Every required field present, non-empty, and in its vocabulary."""
    d = a.to_dict()
    missing = [k for k in REQUIRED
               if not d.get(k) or (isinstance(d[k], str) and not d[k].strip())]
    bad = []
    if a.status not in STATUSES:
        bad.append(f'status {a.status!r}')
    if a.criticality not in CRITICALITIES:
        bad.append(f'criticality {a.criticality!r}')
    if a.status in (SUPPORTED, FALSIFIED) and not a.evidence:
        bad.append(f'status {a.status} with no evidence attached')
    if not a.downstream_dependencies:
        bad.append('no downstream_dependencies: an assumption nothing '
                   'depends on cannot be acted on when it fails')
    ev = {'spec_version': SPEC_VERSION, 'assumption': a.id,
          'missing_fields': missing, 'invalid': bad}
    if missing or bad:
        return Outcome.fail(
            CODE_INVALID,
            f'{a.id}: {len(missing)} missing field(s) {missing}; '
            f'{len(bad)} invalid {bad}',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok('ASSUMPTION_RECORD_VALID', value=d,
                      detail=f'{a.id}: {a.status}, {a.criticality}', **ev)


def settle(a: Assumption, *, status, evidence, uncertainty='') -> Outcome:
    """Move an assumption's status. Only on a legal edge, only with evidence.

    The falsifier is NOT re-read here and cannot be edited by this call. It was
    written before the test; a falsifier that moves with the result is a
    decoration.
    """
    if status not in STATUSES:
        return Outcome.fail(CODE_BAD_MOVE, f'{status!r} is not a status',
                            cause=Cause.GOVERNANCE, known=list(STATUSES))
    if status not in TRANSITIONS[a.status]:
        return Outcome.fail(
            CODE_BAD_MOVE,
            f'{a.id}: {a.status} -> {status} is not a legal move. Legal from '
            f'{a.status}: {list(TRANSITIONS[a.status])}.',
            cause=Cause.GOVERNANCE, assumption=a.id,
            current=a.status, requested=status)
    if status in (SUPPORTED, FALSIFIED) and not evidence:
        return Outcome.fail(
            CODE_BAD_MOVE,
            f'{a.id}: moving to {status} needs evidence. A status that can '
            f'move without a measurement is an opinion.',
            cause=Cause.GOVERNANCE, assumption=a.id)
    moved = dataclasses.replace(a, status=status, evidence=dict(evidence),
                                uncertainty=uncertainty or a.uncertainty)
    v = validate(moved)
    if v.state is not State.PASS:
        return v
    return Outcome.ok(
        'ASSUMPTION_SETTLED', value=moved,
        detail=f'{a.id}: {a.status} -> {status}',
        spec_version=SPEC_VERSION, assumption=a.id,
        previous=a.status, status=status,
        falsifier_unchanged=moved.falsifier == a.falsifier,
        settled_at_utc=_now())


def assert_promotable(assumptions, *, consumer, require_tested=True) -> Outcome:
    """May `consumer` be promoted, given the assumptions it depends on?

    A CRITICAL assumption that is FALSIFIED blocks. A CRITICAL assumption that
    is still DECLARED also blocks when `require_tested` -- an untested
    assumption is not a passed one, and this project has spent a day on
    exactly that distinction.

    NOTHING IS REWRITTEN. This returns a verdict about promotion. It does not
    touch a projection, clip a probability or alter a stored artifact.
    """
    mine = [a for a in assumptions
            if consumer in a.downstream_dependencies]
    falsified = [a for a in mine
                 if a.status == FALSIFIED and a.criticality == CRITICAL]
    untested = [a for a in mine
                if a.status == DECLARED and a.criticality == CRITICAL]
    warn = [a for a in mine
            if a.status == FALSIFIED and a.criticality == MATERIAL]
    ev = {'spec_version': SPEC_VERSION, 'consumer': consumer,
          'n_assumptions': len(mine),
          'falsified_critical': [a.id for a in falsified],
          'untested_critical': [a.id for a in untested],
          'falsified_material': [a.id for a in warn],
          'nothing_is_rewritten': (
              'this is a verdict about promotion. No projection, probability '
              'or stored artifact is touched by it.')}
    if falsified:
        return Outcome.fail(
            CODE_BLOCKED,
            f'{consumer}: {len(falsified)} CRITICAL assumption(s) falsified — '
            f'{[a.id for a in falsified]}. The model output is unchanged and '
            f'stays quotable as what it is; what is refused is promotion.',
            cause=Cause.GOVERNANCE, **ev)
    if require_tested and untested:
        return Outcome.fail(
            CODE_UNTESTED,
            f'{consumer}: {len(untested)} CRITICAL assumption(s) still '
            f'DECLARED — {[a.id for a in untested]}. Untested is not passed.',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok(
        'PROMOTION_NOT_BLOCKED_BY_ASSUMPTIONS', value=[a.id for a in mine],
        detail=f'{consumer}: {len(mine)} assumption(s), '
               f'{len(warn)} falsified at MATERIAL (warning, not a block)',
        **ev)
