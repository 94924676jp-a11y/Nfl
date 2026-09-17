"""Stable identifiers for the gates, because a number is not a name.

WHY THIS EXISTS

"Gate 11" has referred to two different things across returns -- the adjustment
registry in one and in-season pressure data in another -- because the gate
table was numbered by position and the position moved. A reader who checks a
claim against the wrong gate is not being careless; they are being given an
ambiguous reference.

Numbers are kept, as DISPLAY METADATA only. The identifier is the name.

READINESS IS NOT ONE BIT, AND THE COMPOSITE WAS A FALSE GREEN

`WEEK2_OAS1_FIT_READY_TO_EXECUTE = YES` was reported while `fit_week2.py`
refused to run and contained no fitting body. Every part of that claim was
true except the part a reader would act on. The composite is withdrawn and
replaced by four states that cannot be collapsed:

  WEEK2_OAS1_FIT_SPEC_READY      the frozen spec is complete and committed
  WEEK2_OAS1_PREFLIGHT_READY     every identity and governance check passes
  WEEK2_OAS1_FIT_EXECUTABLE      an implementation exists and can actually run
  WEEK2_OAS1_DOWNSTREAM_LAWFUL   the result may reach a production consumer

SPEC_READY and PREFLIGHT_READY being YES says nothing about EXECUTABLE, and
EXECUTABLE says nothing about DOWNSTREAM_LAWFUL. That is the whole point.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'nfl-gate-ids-1'

YES = 'YES'
NO = 'NO'
UNDECIDED = 'UNDECIDED'
NOT_EVALUATED = 'NOT_EVALUATED'

#: Scopes a gate can block. A gate may be non-blocking in one and hard in
#: another; LICENSING_CLEARANCE is exactly that case.
RESEARCH = 'research'
PRODUCTION = 'production'
COMMERCIAL = 'commercial'
SCOPES = (RESEARCH, PRODUCTION, COMMERCIAL)

#: `display_number` is where the old numbering lives. It is for humans reading
#: an older return and nothing reads it as an identity.
GATES = {
    'PBP_CAPTURE_GOVERNED': {
        'display_number': 1, 'state': YES,
        'title': 'governed pbp capture with at least one hashed 2026 capture',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'EPA_TARGET_ONLY_EXEMPTION': {
        'display_number': 2, 'state': YES,
        'title': 'epa admitted as an OAS1 regression target only',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'PRIOR_SEASON_FIT': {
        'display_number': 3, 'state': YES,
        'title': 'a prior-season OAS1 fit supplying theta_prev',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'BASELINE_CHAIN_FORWARD_CLEAN': {
        'display_number': 4, 'state': YES,
        'title': 'B0-B5 implemented and forward-chain-clean',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'PREREGISTRATION_COMMITTED': {
        'display_number': 5, 'state': YES,
        'title': 'pre-declaration committed before any fitted number exists',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'TEAM_NORMALIZATION_TOTAL': {
        'display_number': 6, 'state': YES,
        'title': 'every observed club code resolves, total over the frame',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'EVALUATOR_CONTINUOUS_SCORERS': {
        'display_number': 7, 'state': YES,
        'title': 'MAE, RMSE and CRPS available for a continuous target',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'SINGLE_ADJUSTMENT_OWNERSHIP': {
        'display_number': 8, 'state': NO,
        'title': 'every applied adjustment routed through adjustment_registry',
        'blocks': (PRODUCTION, COMMERCIAL),
        'note': 'NOT blocking for research. The registry exists and refuses '
                'double application; what is unproven is that the whole '
                'pipeline goes through it. ownership_audit reports the '
                'current state and no production module calls the registry '
                'at all, because no production module applies any of the nine '
                'adjustments.',
    },
    'CURRENT_SEASON_FRESHNESS': {
        'display_number': 9, 'state': YES,
        'title': 'current-season input freshness registered and blocking',
        'blocks': (PRODUCTION, COMMERCIAL),
    },
    'PBP_2026_FIELDS': {
        'display_number': 10, 'state': YES,
        'title': '2026 pbp available with the required fields',
        'blocks': (RESEARCH, PRODUCTION, COMMERCIAL),
    },
    'IN_SEASON_PRESSURE_DATA': {
        'display_number': 11, 'state': NO,
        'title': 'true pressure rate available during the season',
        'blocks': (),
        'note': 'was_pressure is 404 for 2026 and publishes after the '
                'postseason. Not required for V1 and not a research-fit gate. '
                'Registered as ol_pass_protection_v1, status NOT_AVAILABLE.',
    },
    'LICENSING_CLEARANCE': {
        'display_number': 12, 'state': UNDECIDED,
        'title': 'commercial-use rights over the consumed sources',
        'blocks': (PRODUCTION, COMMERCIAL),
        'note': 'NON-BLOCKING for internal research, which is the declared '
                'scope of everything built so far. HARD for any production or '
                'commercial downstream path. It is an owner decision and it '
                'is UNDECIDED; it may not be read as YES, and an UNDECIDED '
                'gate blocks the scopes it lists exactly as a NO would.',
    },
}

#: The gates a Week-2 OAS1 RESEARCH fit must clear. Named, not numbered.
RESEARCH_FIT_GATES = tuple(
    g for g, v in GATES.items() if RESEARCH in v['blocks'])

READINESS = {
    'WEEK2_OAS1_FIT_SPEC_READY': {
        'state': YES,
        'means': 'the frozen config, the pre-registration and the hurdles are '
                 'committed and complete.',
    },
    'WEEK2_OAS1_PREFLIGHT_READY': {
        'state': YES,
        'means': 'every identity and governance check in fit_week2.preflight '
                 'passes against the frozen config.',
    },
    'WEEK2_OAS1_FIT_EXECUTABLE': {
        'state': NO,
        'means': 'an implementation exists that can actually produce the '
                 'candidate. Set only when the fitting body is implemented '
                 'and passes dry-run and tests.',
        'why_not': 'set by this module, not by prose. See fit_week2.',
    },
    'WEEK2_OAS1_DOWNSTREAM_LAWFUL': {
        'state': NO,
        'means': 'a production consumer may read the fitted result. Enforced '
                 'by adjustment_registry, which refuses both opponent ids '
                 'under the production purpose.',
    },
    'COLD_START_VALIDATION': {
        'state': NOT_EVALUATED,
        'means': 'zero cold-start plays in both classes -- every club appears '
                 'in the prior season. The stratum is EMPTY, and an empty '
                 'stratum is not a passing one.',
    },
}

#: The withdrawn composite, kept so a reader meeting it in an older return can
#: find out what happened to it rather than assuming it still holds.
WITHDRAWN = {
    'WEEK2_OAS1_FIT_READY_TO_EXECUTE': {
        'withdrawn_on': '2026-09-17',
        'reason': 'reported YES while fit_week2.py refused to run and '
                  'contained no fitting body. "Ready to execute" is the one '
                  'reading a person would act on, and it was the one part '
                  'that was false. Replaced by WEEK2_OAS1_FIT_SPEC_READY, '
                  'WEEK2_OAS1_PREFLIGHT_READY and WEEK2_OAS1_FIT_EXECUTABLE.',
    },
}


def get(gate_id: str) -> Outcome:
    g = GATES.get(gate_id)
    if g is None:
        return Outcome.fail(
            'UNKNOWN_GATE_ID',
            f'{gate_id!r} is not a declared gate. Gates are referenced by '
            f'name; a bare number is not an identity.',
            cause=Cause.GOVERNANCE, known=sorted(GATES))
    return Outcome.ok('GATE_DECLARED', value=dict(g),
                      detail=f'{gate_id}: {g["state"]} -- {g["title"]}',
                      gate_id=gate_id, **{k: v for k, v in g.items()
                                          if k != 'title'})


def assert_scope_allowed(scope: str) -> Outcome:
    """Which gates block this scope right now, and are any of them not YES?"""
    if scope not in SCOPES:
        return Outcome.fail('UNKNOWN_SCOPE', f'{scope!r} is not one of '
                                             f'{list(SCOPES)}',
                            cause=Cause.GOVERNANCE)
    blocking = {g: v['state'] for g, v in GATES.items()
                if scope in v['blocks'] and v['state'] != YES}
    ev = {'spec_version': SPEC_VERSION, 'scope': scope,
          'blocking_gates': dict(sorted(blocking.items())),
          'n_blocking': len(blocking)}
    if blocking:
        return Outcome.fail(
            'SCOPE_BLOCKED_BY_GATE',
            f'{scope}: {sorted(blocking)} are not {YES}. An {UNDECIDED} gate '
            f'blocks exactly as a {NO} does -- it is an open question, not a '
            f'quiet pass.', cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok('SCOPE_GATES_CLEAR', value=scope,
                      detail=f'{scope}: every gate that blocks it is {YES}',
                      **ev)


def readiness(name: str) -> Outcome:
    r = READINESS.get(name)
    if r is None:
        w = WITHDRAWN.get(name)
        if w:
            return Outcome.fail(
                'READINESS_STATE_WITHDRAWN',
                f'{name!r} was withdrawn on {w["withdrawn_on"]}: '
                f'{w["reason"]}', cause=Cause.GOVERNANCE, **w)
        return Outcome.fail('UNKNOWN_READINESS_STATE', f'{name!r}',
                            cause=Cause.GOVERNANCE, known=sorted(READINESS))
    return Outcome.ok('READINESS_STATE', value=r['state'],
                      detail=f'{name} = {r["state"]}', name=name, **r)


def main() -> int:
    print(f'GATES ({SPEC_VERSION})')
    w = max(len(g) for g in GATES)
    for g, v in GATES.items():
        print(f'  [{v["display_number"]:>2}] {g:<30s} {v["state"]:<9s} '
              f'blocks={",".join(v["blocks"]) or "-"}')
    print('\nRESEARCH-FIT GATES: '
          f'{sum(1 for g in RESEARCH_FIT_GATES if GATES[g]["state"] == YES)}'
          f'/{len(RESEARCH_FIT_GATES)} YES')
    for scope in SCOPES:
        o = assert_scope_allowed(scope)
        print(f'  {scope:<11s} {o.state.value:<5s} {o.code} '
              f'{o.evidence["blocking_gates"] or ""}')
    print('\nREADINESS')
    for n in READINESS:
        print(f'  {n:<32s} {READINESS[n]["state"]}')
    for n in WITHDRAWN:
        print(f'  {n:<32s} WITHDRAWN')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
