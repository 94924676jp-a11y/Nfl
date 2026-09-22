"""The canonical feature registry. One place that says what a feature MEANS.

WHAT THIS IS FOR

`nfl/NFL_FEATURE_REGISTRY.md` already records which features earned which
lifecycle status, with the measurements behind each ruling. It is good, and
it is prose: no Python module imports it, so a rejected feature could be
wired into a model tomorrow and nothing would object. This file is the
machine-readable half. It does not replace the document; it imports the
document's vocabulary and makes it enforceable.

WHAT A FeatureSpec ANSWERS

Not "what is the number" -- that is the state object's job. This answers the
questions a reader has to know before the number means anything: where it
came from, what window it covers, what the point-in-time rule is, whether the
chain may run without it, and what happens when it is missing.

FOUR FIELDS HAVE NO DEFAULT AND NEVER WILL

`semantic_definition`, `pit_rule`, `missing_action` and `source_family` are
refused when absent. A default for any of them would be this project's
characteristic defect in registry form: a value nobody chose, read later as a
value somebody did. A feature whose PIT rule is unstated cannot be checked
for leakage, and a feature whose missing action is unstated will be filled
with a zero by whoever needs it most.

NOTHING MAY BE REGISTERED CORE

The document says so and gives the reason: no NFL experiment has run, and the
measured findings behind it were taken on data that has since been inspected.
`register` enforces it rather than trusting a reader to remember.

A REJECTED OR ORACLE FEATURE MAY NOT BE AN INPUT

The document's REJECTED table is a list of things already measured and found
worthless -- plays per game as a team trait (shrunk ICC 0.000), neutral pass
rate as an incremental predictor (forward-chained delta +0.00001), charged
drop rate (r = 0.020). `ffopportunity` expected-points is ORACLE /
NON-DEPLOYABLE: lawful as a bound, unlawful as a forecast input. Registering
either as a model input is refused here, so the ruling survives the person
who remembers it.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import evidence as EV                     # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome         # noqa: E402

SPEC_VERSION = 'nfl-feature-registry-0'

#: How badly the chain needs the feature.
REQUIRED = 'REQUIRED'
DESIRABLE = 'DESIRABLE'
OPTIONAL = 'OPTIONAL'
REQUIRED_LEVELS = (REQUIRED, DESIRABLE, OPTIONAL)

#: What happens when it is not there at the information cut.
REFUSE = 'REFUSE'
WARN_AND_REDUCE_CONFIDENCE = 'WARN_AND_REDUCE_CONFIDENCE'
PROCEED = 'PROCEED'
MISSING_ACTIONS = (REFUSE, WARN_AND_REDUCE_CONFIDENCE, PROCEED)

#: The only lawful way to say "there is no fallback". An empty string would
#: be indistinguishable from a field nobody filled in.
NO_FALLBACK = 'NONE'

#: Imported from nfl/NFL_FEATURE_REGISTRY.md. ORACLE_NON_DEPLOYABLE is that
#: document's own addition: legitimate as a bound, illegitimate as an input.
CORE = 'CORE'
SECONDARY = 'SECONDARY'
EXPERIMENTAL = 'EXPERIMENTAL'
DESCRIPTIVE = 'DESCRIPTIVE'
REJECTED = 'REJECTED'
ORACLE_NON_DEPLOYABLE = 'ORACLE_NON_DEPLOYABLE'
LIFECYCLE = (CORE, SECONDARY, EXPERIMENTAL, DESCRIPTIVE, REJECTED,
             ORACLE_NON_DEPLOYABLE)

#: Statuses that may never be a model input. Not a policy this file invented.
NOT_AN_INPUT = (REJECTED, ORACLE_NON_DEPLOYABLE)

DOC = 'nfl/NFL_FEATURE_REGISTRY.md'


@dataclass(frozen=True)
class FeatureSpec:
    """One modelled feature, fully described.

    `latest_valid_observation` states the newest observation the PIT rule
    admits, in the rule's own units -- "the last completed week before the
    forecast week", not a timestamp. It is what a freshness check compares
    against, and it is separate from `pit_rule` because the rule is prose and
    this is the thing a machine reads.
    """
    name: str
    source_family: str
    semantic_definition: str
    pit_rule: str
    latest_valid_observation: str
    required_level: str
    freshness_sla: str
    missing_action: str
    fallback: str
    evidence_grade: str
    lifecycle_status: str
    licensing: Optional[str] = None
    note: Optional[str] = None
    spec_version: str = SPEC_VERSION

    def as_dict(self) -> Dict:
        return dataclasses.asdict(self)


class Registry:
    """A set of FeatureSpecs with an identity that changes when they do."""

    def __init__(self, name: str):
        self.name = name
        self._specs: Dict[str, FeatureSpec] = {}

    # -- registration ------------------------------------------------------
    def register(self, spec: FeatureSpec) -> Outcome:
        missing = [f for f in ('name', 'source_family', 'semantic_definition',
                               'pit_rule', 'missing_action')
                   if not (getattr(spec, f) or '').strip()]
        if missing:
            return Outcome.fail(
                'FEATURE_SPEC_INCOMPLETE',
                f'{spec.name or "<unnamed>"} is missing {missing}. These four '
                f'have no default: a feature whose PIT rule is unstated '
                f'cannot be checked for leakage, and one whose missing action '
                f'is unstated will be filled with a zero by whoever needs it '
                f'most.',
                feature=spec.name, missing=missing)
        if spec.name in self._specs:
            return Outcome.fail(
                'FEATURE_ALREADY_REGISTERED',
                f'{spec.name} is registered already. Two definitions of one '
                f'feature is the fragmentation this registry exists to end.',
                feature=spec.name)
        for fld, allowed in (('required_level', REQUIRED_LEVELS),
                             ('missing_action', MISSING_ACTIONS),
                             ('lifecycle_status', LIFECYCLE),
                             ('evidence_grade', EV.GRADES)):
            v = getattr(spec, fld)
            if v not in allowed:
                return Outcome.fail(
                    'FEATURE_SPEC_VALUE_NOT_DECLARED',
                    f'{spec.name}.{fld} is {v!r}, which is not one of '
                    f'{allowed}.', feature=spec.name, field=fld, value=v)
        if not (spec.latest_valid_observation or '').strip():
            return Outcome.fail(
                'FEATURE_SPEC_INCOMPLETE',
                f'{spec.name} does not say what its latest valid observation '
                f'is, so no freshness check can be written against it.',
                feature=spec.name, missing=['latest_valid_observation'])
        if not (spec.fallback or '').strip():
            return Outcome.fail(
                'FEATURE_FALLBACK_UNSTATED',
                f'{spec.name} leaves `fallback` blank. Say {NO_FALLBACK!r}. '
                f'A blank is indistinguishable from a field nobody filled '
                f'in, and this is exactly where a silent substitution gets '
                f'made later.', feature=spec.name)
        if spec.lifecycle_status == CORE:
            return Outcome.fail(
                'FEATURE_MAY_NOT_BE_CORE',
                f'{spec.name} was registered CORE. Nothing is CORE and '
                f'nothing can be yet: {DOC} states that no NFL experiment '
                f'has run, and that the measured findings behind it were '
                f'taken on data since inspected. Promotion follows an '
                f'experiment; it is not a label applied in advance.',
                feature=spec.name)
        if (spec.lifecycle_status in NOT_AN_INPUT
                and spec.required_level != OPTIONAL):
            return Outcome.fail(
                'FEATURE_NOT_AN_INPUT',
                f'{spec.name} is {spec.lifecycle_status} in {DOC} and was '
                f'registered at required level {spec.required_level}. A '
                f'measured rejection and an oracle are both unlawful as '
                f'model inputs; only OPTIONAL (diagnostic) use is open.',
                feature=spec.name, lifecycle=spec.lifecycle_status)
        if (spec.evidence_grade == EV.UNAVAILABLE
                and spec.missing_action == PROCEED):
            return Outcome.fail(
                'UNAVAILABLE_MAY_NOT_PROCEED_SILENTLY',
                f'{spec.name} is UNAVAILABLE and its missing action is '
                f'PROCEED, which is how an absence becomes a zero with '
                f'nothing said. Use {WARN_AND_REDUCE_CONFIDENCE} or '
                f'{REFUSE}.', feature=spec.name)
        self._specs[spec.name] = spec
        return Outcome.ok('FEATURE_REGISTERED', value=spec.name,
                          detail=f'{spec.name} from {spec.source_family}')

    def add(self, **kw) -> 'Registry':
        """Register or RAISE. Used at import time, where a bad spec must not
        become a warning nobody reads."""
        o = self.register(FeatureSpec(**kw))
        if o.state.name != 'PASS':
            raise AssertionError(f'{o.code}: {o.detail}')
        return self

    # -- reading -----------------------------------------------------------
    def get(self, name: str) -> Optional[FeatureSpec]:
        return self._specs.get(name)

    def require(self, name: str) -> Outcome:
        s = self._specs.get(name)
        if s is None:
            return Outcome.fail(
                'FEATURE_NOT_REGISTERED',
                f'{name!r} is not in the registry. A model input that '
                f'bypasses the registry has no declared PIT rule, so nothing '
                f'can say whether it leaks.', feature=name)
        return Outcome.ok('FEATURE_FOUND', value=s, detail=name)

    def names(self) -> Tuple[str, ...]:
        return tuple(sorted(self._specs))

    def by_source(self) -> Dict[str, Tuple[str, ...]]:
        out: Dict[str, list] = {}
        for s in self._specs.values():
            out.setdefault(s.source_family, []).append(s.name)
        return {k: tuple(sorted(v)) for k, v in sorted(out.items())}

    def required_names(self) -> Tuple[str, ...]:
        return tuple(sorted(n for n, s in self._specs.items()
                            if s.required_level == REQUIRED))

    def as_dict(self) -> Dict:
        return {'registry': self.name, 'spec_version': SPEC_VERSION,
                'n_features': len(self._specs),
                'features': {n: s.as_dict()
                             for n, s in sorted(self._specs.items())}}

    def identity(self) -> str:
        """Content hash. Changes whenever any spec changes, which is what a
        state artifact records so a replay can tell whether the definitions
        moved under it."""
        blob = json.dumps(self.as_dict(), sort_keys=True,
                          separators=(',', ':')).encode()
        return 'FR-' + hashlib.sha256(blob).hexdigest()[:16]

    def assert_fallbacks_resolve(self) -> Outcome:
        """Every non-NONE fallback must name a registered feature. Checked
        after seeding because a fallback may point forward."""
        bad = {n: s.fallback for n, s in self._specs.items()
               if s.fallback != NO_FALLBACK and s.fallback not in self._specs}
        if bad:
            return Outcome.fail(
                'FEATURE_FALLBACK_UNRESOLVED',
                f'{len(bad)} fallback(s) name a feature that is not '
                f'registered: {bad}. A fallback nobody defined is a silent '
                f'substitution waiting to happen.', unresolved=bad)
        return Outcome.ok('FALLBACKS_RESOLVE', value=len(self._specs),
                          detail=f'{len(self._specs)} feature(s) checked')


# --------------------------------------------------------------------------
# v0 SEED. ONLY features the current production chain already consumes.
#
# Nothing here is aspirational. If the chain does not read it today it is not
# in this list, because a registry padded with features nobody computes
# describes a system that does not exist.
# --------------------------------------------------------------------------
PREGAME = Registry('pregame-state-v0')

_ROSTER_PIT = ('the single lawful weekly_rosters capture at or before the '
               'information cut, selected by vintage_selector; a later '
               'capture is unreachable because it is never selected')

PREGAME.add(
    name='roster_membership', source_family='weekly_rosters',
    semantic_definition='whether this player appears on the club roster for '
                        'this season and week. Membership only: it says '
                        'nothing about whether he will play.',
    pit_rule=_ROSTER_PIT,
    latest_valid_observation='the last roster capture retrieved at or before '
                             'the information cut',
    required_level=REQUIRED, freshness_sla='a capture within the game week',
    missing_action=REFUSE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='nflverse, public',
    note='the RAW blob is required: the reduced vintage drops `status`, '
         'which is the column roster membership is decided on.')
PREGAME.add(
    name='roster_status', source_family='weekly_rosters',
    semantic_definition="the club's own game-day status string (ACT, RES, "
                        'PRA and so on). What the roster SAYS; not an '
                        'inference about availability.',
    pit_rule=_ROSTER_PIT,
    latest_valid_observation='same capture as roster_membership',
    required_level=REQUIRED, freshness_sla='a capture within the game week',
    missing_action=REFUSE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='nflverse, public')
PREGAME.add(
    name='football_position', source_family='weekly_rosters',
    semantic_definition='the position the club lists the player at. What he '
                        'PLAYS. Not what DraftKings will accept him at.',
    pit_rule=_ROSTER_PIT,
    latest_valid_observation='same capture as roster_membership',
    required_level=REQUIRED, freshness_sla='a capture within the game week',
    missing_action=REFUSE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='nflverse, public')
PREGAME.add(
    name='dfs_position', source_family='dk_salaries',
    semantic_definition="DraftKings' own roster position for the player, "
                        'which is the only authority on what slot DK will '
                        'accept him in. A pass-catching back is in the '
                        'targets room and an RB on DraftKings; these are two '
                        'facts and must not be merged.',
    pit_rule='the salary file published for this contest, captured before '
             'lock',
    latest_valid_observation='the contest salary export for this slate',
    required_level=DESIRABLE, freshness_sla='the current contest export',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=DESCRIPTIVE,
    licensing='DraftKings contest export; contest use only',
    note='absence means the player cannot enter a DFS pool. It must never '
         'be read as an availability fact.')
PREGAME.add(
    name='depth_listing', source_family='depth_charts',
    semantic_definition='every group the club lists the player in, each with '
                        'its position abbreviation and rank. ALL listings, '
                        'not one: a club lists the same man in several '
                        'groups at the same timestamp.',
    pit_rule='the single lawful depth_charts capture at or before the cut',
    latest_valid_observation='the last depth capture at or before the cut',
    required_level=DESIRABLE, freshness_sla='a capture within the game week',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='nflverse, public')
PREGAME.add(
    name='offensive_depth_rank', source_family='depth_charts',
    semantic_definition='the rank within the offensive group only. A '
                        'workload question. Special-teams standing is a '
                        'different axis and may not substitute for it.',
    pit_rule='derived from depth_listing at the same cut',
    latest_valid_observation='same capture as depth_listing',
    required_level=DESIRABLE, freshness_sla='a capture within the game week',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='nflverse, public',
    note='OFFENSIVE_DEPTH_UNKNOWN is a state, not a missing value.')
PREGAME.add(
    name='special_teams_role', source_family='depth_charts',
    semantic_definition='standing on a return or kicking unit. Informs NO '
                        'offensive workload room.',
    pit_rule='derived from depth_listing at the same cut',
    latest_valid_observation='same capture as depth_listing',
    required_level=OPTIONAL, freshness_sla='a capture within the game week',
    missing_action=PROCEED, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=DESCRIPTIVE,
    licensing='nflverse, public')
PREGAME.add(
    name='declared_starter', source_family='depth_charts',
    semantic_definition='the club listing the player first in his offensive '
                        'group. A declaration, never a measurement, and it '
                        'is not a promise of snaps.',
    pit_rule='derived from offensive_depth_rank at the same cut',
    latest_valid_observation='same capture as depth_listing',
    required_level=DESIRABLE, freshness_sla='a capture within the game week',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='nflverse, public')
PREGAME.add(
    name='injury_report_status', source_family='injuries',
    semantic_definition='the published game-status designation (OUT, '
                        'DOUBTFUL, QUESTIONABLE and so on) for this season '
                        'and week.',
    pit_rule='the single lawful injuries capture at or before the cut',
    latest_valid_observation='the last injury capture at or before the cut',
    required_level=DESIRABLE, freshness_sla='within 48h of kickoff',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='nflverse, public',
    note='absence of a designation is NOT a declaration of health. It is '
         'absence of a designation.')
PREGAME.add(
    name='injury_practice_status', source_family='injuries',
    semantic_definition='the published practice participation for the week '
                        '(DNP, LIMITED, FULL).',
    pit_rule='the single lawful injuries capture at or before the cut',
    latest_valid_observation='the last injury capture at or before the cut',
    required_level=OPTIONAL, freshness_sla='within 48h of kickoff',
    missing_action=PROCEED, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=DESCRIPTIVE,
    licensing='nflverse, public')
PREGAME.add(
    name='inactive_status', source_family='official_inactives',
    semantic_definition="the club's official pre-kickoff inactive list. The "
                        'only authority that a player will not play.',
    pit_rule='published about 90 minutes before kickoff; lawful only from '
             'its publication time',
    latest_valid_observation='the official inactive publication for this game',
    required_level=DESIRABLE, freshness_sla='published for THIS game',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.DECLARED, lifecycle_status=SECONDARY,
    licensing='club publication',
    note='ACTIVE may NOT be inferred from omission, and DraftKings salary '
         'presence may not stand in for this.')
PREGAME.add(
    name='current_season_carries', source_family='usage_vintage',
    semantic_definition='rush attempts charged to the player in completed '
                        'games of the current season.',
    pit_rule='games completed strictly before the forecast week; a game in '
             'the forecast week is an outcome',
    latest_valid_observation='the last completed week before the forecast '
                             'week',
    required_level=REQUIRED, freshness_sla='the week before the forecast '
                                           'week must be present',
    missing_action=REFUSE, fallback=NO_FALLBACK,
    evidence_grade=EV.MEASURED, lifecycle_status=SECONDARY,
    licensing='nflverse, public')
PREGAME.add(
    name='current_season_targets', source_family='usage_vintage',
    semantic_definition='passes thrown to the player in completed games of '
                        'the current season.',
    pit_rule='games completed strictly before the forecast week',
    latest_valid_observation='the last completed week before the forecast '
                             'week',
    required_level=REQUIRED, freshness_sla='the week before the forecast '
                                           'week must be present',
    missing_action=REFUSE, fallback=NO_FALLBACK,
    evidence_grade=EV.MEASURED, lifecycle_status=SECONDARY,
    licensing='nflverse, public')
PREGAME.add(
    name='offensive_snaps', source_family='snap_counts',
    semantic_definition='offensive snaps played in completed games of the '
                        'current season. A presence denominator, and NOT a '
                        'substitute for routes: a back who stays in to '
                        'block and a receiver who runs a route both count '
                        'one snap.',
    pit_rule='games completed strictly before the forecast week',
    latest_valid_observation='the last completed week before the forecast '
                             'week',
    required_level=DESIRABLE, freshness_sla='the week before the forecast '
                                            'week must be present',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.MEASURED, lifecycle_status=SECONDARY,
    licensing='nflverse / PFR, public')
for _tn, _what in (
        ('team_dropbacks', 'pass attempts plus sacks plus scrambles charged '
                           'to the club'),
        ('team_carries', 'rush attempts charged to the club'),
        ('team_targets', 'passes thrown by the club to a receiver')):
    PREGAME.add(
        name=_tn, source_family='usage_vintage',
        semantic_definition=f'{_what}, in completed games of the current '
                            f'season. The DENOMINATOR a player share is '
                            f'taken against; a share without its denominator '
                            f'is not a measurement.',
        pit_rule='games completed strictly before the forecast week',
        latest_valid_observation='the last completed week before the '
                                 'forecast week',
        required_level=REQUIRED,
        freshness_sla='all 32 clubs present for the week before the forecast '
                      'week',
        missing_action=REFUSE, fallback=NO_FALLBACK,
        evidence_grade=EV.MEASURED, lifecycle_status=SECONDARY,
        licensing='nflverse, public')
PREGAME.add(
    name='routes_run', source_family='pbp_participation',
    semantic_definition='routes run by the player, the correct denominator '
                        'for a receiving role.',
    pit_rule='games completed strictly before the forecast week',
    latest_valid_observation='not obtainable for 2026',
    required_level=DESIRABLE, freshness_sla='not applicable while '
                                            'unavailable',
    missing_action=WARN_AND_REDUCE_CONFIDENCE, fallback=NO_FALLBACK,
    evidence_grade=EV.UNAVAILABLE, lifecycle_status=EXPERIMENTAL,
    licensing='nflverse, public where it exists',
    note=EV.UNAVAILABLE_SOURCES['routes'])

_FALLBACKS = PREGAME.assert_fallbacks_resolve()
if _FALLBACKS.state.name != 'PASS':
    raise AssertionError(f'{_FALLBACKS.code}: {_FALLBACKS.detail}')
