"""The assumption registry. Five entries, one of them measured end to end.

THIS IS v0 AND IT IS DELIBERATELY NARROW. There is no source-code scanner
here, and none is wanted yet. The thing that had to be proved first is that a
SINGLE assumption can be identified, measured, falsified, classified and
governed without a human deciding at each step what the answer should be.
`A1_APPEARANCE_CERTAINTY` is that one. The other four are seeded as DECLARED,
with their falsifiers written and their downstream dependencies named, so that
the next measurement has somewhere to land rather than a schema to invent.

EVERY FALSIFIER HERE WAS WRITTEN BEFORE ITS TEST RAN. That is the only
property of this file that matters. A falsifier added afterwards describes a
result; one written first can be failed.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import assumption as AS                # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402

SPEC_VERSION = 'nfl-assumption-registry-1'

#: Tokens a falsifier must contain to be more than a gesture.
#: Syntactic and admittedly weak; the protection that matters is
#: that the text was committed before its test ran.
CONDITION_WORDS = ('below', 'above', 'excluding', 'differs',
                   'outside', 'indistinguishable', 'departs',
                   'retains', 'is observed', 'lies')

A1 = AS.Assumption(
    id='A1_APPEARANCE_CERTAINTY',
    claim=('A non-QB skill player whose prior-season appearance rate is 1.0, '
           'and who has taken opportunity in every current-season week so '
           'far, will take opportunity in the next week with probability '
           'exactly 1.0.'),
    estimand=('P(carries + targets > 0 in week W | prior-season appearance '
              'rate == 1.0 AND opportunity in every week 1..W-1), estimated '
              'as a pooled binomial rate over the cohort.'),
    population=('non-QB skill players, seasons 2022-2025, weeks 2-18 of the '
                'regular season, conditioned on the club having played that '
                'week. 2026 is excluded: it is the season the state is '
                'applied to.'),
    test='nfl.research.assumptions.cohort_appearance_certainty.measure',
    falsifier=('the cohort appearance rate is below 1.0 by more than Monte '
               'Carlo resolution -- concretely, the upper bound of the 95% '
               'Wilson interval is below 1.0, or any member of the cohort is '
               'observed not appearing. Either alone falsifies it.'),
    downstream_dependencies=(
        'nfl.production.nonqb.cs2_state',
        'nfl.production.nonqb.cs2_state.state',
        'CS2_STAGE2_PRODUCTION_ALLOCATION',
    ),
    criticality=AS.CRITICAL,
    status=AS.DECLARED,
    declared_at_utc='2026-09-18T06:00:00Z',
    notes=('Surfaced by CS2_APPEARANCE_SATURATES_AT_ONE. A Beta posterior '
           'mean is exactly 1.0 for a man who has never missed; on the 2026 '
           'week-1 carries room that was 13 rows of 196 at exactly 1.0 and 77 '
           'at exactly 0.0. The estimator ASSERTS certainty, so the question '
           'is whether football supports certainty.'),
)

A2 = AS.Assumption(
    id='A2_PROPORTIONAL_REDISTRIBUTION',
    claim=("When a player is absent, his opportunity is redistributed to the "
           "rest of his room in proportion to their existing shares."),
    estimand=('E[share_j | i absent] / E[share_j | i present], for every pair '
              '(i, j) in a room, against the proportional prediction '
              'share_j / (1 - share_i). A ratio of 1.0 everywhere supports '
              'proportionality.'),
    population=('rooms in 2022-2025 where exactly one player with a '
                'non-trivial prior share was absent for a week and present '
                'the weeks either side.'),
    test='nfl.research.assumptions.a2_redistribution.run',
    falsifier=('the observed redistribution ratio departs from 1.0 '
               'systematically by role -- specifically, if the nearest '
               'depth-chart neighbour absorbs materially more than his '
               'proportional share, with a cluster-robust interval excluding '
               'proportionality.'),
    downstream_dependencies=(
        'nfl.production.nonqb.rushing_a1',
        'nfl.production.nonqb.shared_pass',
        'CS2_STAGE2_PRODUCTION_ALLOCATION',
    ),
    criticality=AS.CRITICAL,
    status=AS.DECLARED,
    declared_at_utc='2026-09-18T06:00:00Z',
    notes=('Named in P2_DIAGNOSTIC: Ty Johnson was removed as Out and his '
           'share was "dealt among the remaining players by the A1 '
           'multinomial" rather than reassigned by role. Nobody has measured '
           'whether football redistributes that way.'),
)

A3 = AS.Assumption(
    id='A3_ROLE_CONTINUITY_ACROSS_REGIME_CHANGE',
    claim=("A player's role share carries across a regime change -- a new "
           "coordinator, a new starting quarterback, or a mid-season trade -- "
           "so prior-season share remains the right prior."),
    estimand=('the ratio of a player\'s post-change room share to his '
              'pre-change share, against 1.0, within the same season, '
              'compared with the same ratio in matched player-weeks with no '
              'regime change.'),
    population=('2022-2025 player-seasons spanning a declared regime change, '
                'with the change dated from a governed source and never '
                'inferred from the usage it is meant to explain.'),
    test='NOT_YET_WRITTEN',
    falsifier=('the post-change share ratio differs from the matched '
               'no-change ratio with an interval excluding equality. The '
               'continuity assumption is then false for that class of change '
               'and the prior must be conditioned on it.'),
    downstream_dependencies=(
        'nfl.production.nonqb.role_prior',
        'nfl.production.nonqb.cs2_state',
        'nfl.research.oas1.baselines',
    ),
    criticality=AS.MATERIAL,
    status=AS.DECLARED,
    declared_at_utc='2026-09-18T06:00:00Z',
    notes=('CS2 amendment B1 declared the shrinkage target to be the '
           "player's own prior-season share. That choice is only as good as "
           'this assumption, and the two must be tested together rather than '
           'one justifying the other.'),
)

A4 = AS.Assumption(
    id='A4_STATIC_TEAM_VOLUME_SUFFICIENCY',
    claim=('A club\'s game-level offensive volume can be drawn independently '
           'of the opponent\'s and of the evolving score, so a static '
           'team-volume layer is sufficient.'),
    estimand=('the correlation between the two clubs\' offensive volume in '
              'the same game, and the within-game dependence of pass rate on '
              'score state, measured historically and in the sealed worlds '
              'under the same definition.'),
    population='2024-2025 games; sealed DET_BUF worlds for the simulated side.',
    test='nfl.research.coupling.game_offense_coupling.run',
    falsifier=('the simulated club-vs-club coupling lies outside the '
               'historical interval, OR the historical within-game pass rate '
               'depends on score state while the simulator has no score '
               'state to depend on. The second condition alone falsifies '
               'sufficiency.'),
    downstream_dependencies=(
        'nfl.production.nonqb.layers',
        'TEAM_VOLUME_V2',
        'SHARED_GAME_ENVIRONMENT',
    ),
    criticality=AS.CRITICAL,
    status=AS.DECLARED,
    declared_at_utc='2026-09-18T06:00:00Z',
    notes=('Partially measured already: GAME_OFFENSE_COUPLING found '
           'historical coupling indistinguishable from zero and simulated '
           'coupling at -0.131. The SECOND limb of the falsifier is the live '
           'one -- the sealed board emits no score at all, so a score-state '
           'dependence cannot even be expressed. Left DECLARED rather than '
           'settled because only half the estimand has been measured, and '
           'settling on half is the failure this registry exists to stop.'),
)

A5 = AS.Assumption(
    id='A5_TD_CONVERSION_PORTABILITY',
    claim=('A player\'s touchdown conversion rate per opportunity is '
           'portable: it transfers across seasons and across usage levels, '
           'so yardage and touchdowns can be modelled from the same '
           'opportunity draw without a separate red-zone role.'),
    estimand=('the season-over-season correlation of TD per opportunity at '
              'matched opportunity volume, and the residual dependence of TD '
              'rate on red-zone share once total opportunity is controlled.'),
    population=('2022-2025 player-seasons with at least a declared minimum '
                'opportunity count in both seasons; the minimum is a '
                'reporting threshold, declared before the measurement.'),
    test='NOT_YET_WRITTEN',
    falsifier=('season-over-season correlation of TD rate is indistinguishable '
               'from zero at matched volume, OR red-zone share retains '
               'explanatory power after total opportunity is controlled. '
               'Either means TD conversion is not portable and needs its own '
               'role state.'),
    downstream_dependencies=(
        'nfl.production.nonqb.rushing_conversion',
        'nfl.dfs.scoring.statline',
        'PROP_MARKET_ANYTIME_TD',
    ),
    criticality=AS.MATERIAL,
    status=AS.DECLARED,
    declared_at_utc='2026-09-18T06:00:00Z',
    notes=('The engine has no red-zone role per player -- the sealed board '
           'carries team_rz_carries at CLUB level only. If TD conversion is '
           'not portable, every touchdown number in the system rests on a '
           'quantity the model does not represent.'),
)

REGISTRY = (A1, A2, A3, A4, A5)
BY_ID = {a.id: a for a in REGISTRY}


#: Where a MEASURED status lives. The registry DECLARES -- claim, estimand,
#: falsifier, criticality, dependencies -- and those are code, immutable and
#: reviewable in a diff. A status is a MEASUREMENT RESULT, so it lives in the
#: audit artifact and is overlaid at read time. Editing a status by hand in
#: this file would be editing a declaration to match a result.
SETTLEMENTS = _REPO / 'nfl/research/assumptions/ASSUMPTION_AUDIT.json'


def settlements(path=None) -> dict:
    """id -> (status, evidence, uncertainty) from the recorded audit."""
    import json
    p = pathlib.Path(path or SETTLEMENTS)
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text())
    except Exception:                                      # noqa: BLE001
        return {}
    out = {}
    for a in (d.get('registry') or {}).get('assumptions') or []:
        if a.get('id') and a.get('status'):
            out[a['id']] = (a['status'], a.get('evidence') or {},
                            a.get('uncertainty') or '')
    return out


def all_assumptions(path=None):
    """The declared records, with measured statuses overlaid.

    An overlay is applied only along a LEGAL transition edge. A recorded
    status that could not be reached from the declared one is ignored and the
    declaration stands -- a corrupt or hand-edited artifact must not be able
    to promote something by asserting SUPPORTED.
    """
    import dataclasses
    seen = settlements(path)
    out = []
    for a in REGISTRY:
        s = seen.get(a.id)
        if not s or s[0] == a.status:
            out.append(a)
            continue
        status, evidence, unc = s
        if status not in AS.TRANSITIONS.get(a.status, ()):
            out.append(a)
            continue
        if status in (AS.SUPPORTED, AS.FALSIFIED) and not evidence:
            out.append(a)
            continue
        out.append(dataclasses.replace(a, status=status,
                                       evidence=dict(evidence),
                                       uncertainty=unc or a.uncertainty))
    return out


def get(assumption_id: str):
    return BY_ID.get(assumption_id)


def audit() -> Outcome:
    """Every record valid, every id unique, every falsifier non-trivial."""
    bad, ids = [], set()
    for a in REGISTRY:
        v = AS.validate(a)
        if v.state is not State.PASS:
            bad.append({'id': a.id, 'why': v.detail})
        if a.id in ids:
            bad.append({'id': a.id, 'why': 'duplicate id'})
        ids.add(a.id)
        # A falsifier that names no CONDITION is a decoration. This is a
        # weak syntactic screen and it says so: it catches "we will see if
        # it holds", not a subtly circular falsifier. The real protection is
        # that the text was committed before the test ran.
        low = a.falsifier.lower()
        if len(a.falsifier) < 60 or not any(t in low for t in CONDITION_WORDS):
            bad.append({'id': a.id,
                        'why': f'falsifier states no condition '
                               f'({len(a.falsifier)} chars)'})
    by_status = {}
    for a in REGISTRY:
        by_status[a.status] = by_status.get(a.status, 0) + 1
    ev = {'spec_version': SPEC_VERSION, 'n': len(REGISTRY),
          'by_status': by_status,
          'by_criticality': {c: sum(1 for a in REGISTRY
                                    if a.criticality == c)
                             for c in AS.CRITICALITIES},
          'no_source_scanner_yet': (
              'v0 deliberately has no automatic source-code assumption '
              'discovery. One assumption end to end first.'),
          'invalid': bad}
    if bad:
        return Outcome.fail('ASSUMPTION_REGISTRY_INVALID',
                            f'{len(bad)} bad record(s)',
                            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok('ASSUMPTION_REGISTRY_VALID', value=list(REGISTRY),
                      detail=f'{len(REGISTRY)} assumption(s): {by_status}',
                      **ev)
