"""Which players get deeper research, and why. IMPACT x DISAGREEMENT x
UNCERTAINTY.

WHY A PRODUCT AND NOT A SUM

A sum lets one large term carry a player onto the deep-research list on its
own. That is exactly wrong for all three terms here. A player nobody can
roster does not need research however uncertain he is. A player whose
evidence is complete and agreed does not need research however large his
projection. A player with no disagreement anywhere does not need research
however uncertain the league is about him. The thing worth a reviewer's hour
is the intersection: he matters, something disagrees, and the evidence is
thin. A product is zero when any factor is zero, which is the behaviour we
want.

WHY THE TIERS ARE RANKS AND NOT THRESHOLDS

A threshold on this score would be a fitted constant with nothing behind it,
and this project logs those as bugs. So the tiers are a CAPACITY ALLOCATION:
the caller states how many players can actually receive deep research on this
slate, and the highest-priority that many get it. That is an honest statement
about a reviewer's day rather than a false statement about football. The one
exception is a blocking conflict, which escalates regardless of capacity,
because a blocking conflict stops the slate either way.

WHERE EXTERNAL NUMBERS ARE ALLOWED, AND WHERE THEY ARE NOT

An external projection or a sportsbook line may raise a player's DISAGREEMENT
term. That is the only thing it may ever do. It is quarantined here, under a
field named so that no reader could mistake it for evidence, and it never
reaches a dossier axis, a role, a share, a team volume or a draw. The rule the
owner set and this module enforces: sportsbook prices must not become
predictive inputs into the football model. Raising a research priority is not
an input to a forecast; changing a number toward a market is.
"""
from __future__ import annotations

import collections
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import audit as AUD                     # noqa: E402
from nfl.production.review import evidence as EV                   # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'player-review-escalation-1'

DEEP_RESEARCH = 'DEEP_RESEARCH'
STANDARD_REVIEW = 'STANDARD_REVIEW'
AUTOMATED_ONLY = 'AUTOMATED_ONLY'
TIERS = (DEEP_RESEARCH, STANDARD_REVIEW, AUTOMATED_ONLY)

#: Severity weights for the disagreement term. These are an ORDERING, stated
#: here so it is auditable, not an estimate of anything. They may be reordered
#: by argument; they may not be tuned against an outcome.
SEVERITY_WEIGHT = {AUD.BLOCKING: 1.0, AUD.REVIEW: 0.6, AUD.NOTE: 0.25}

#: Uncertainty weights, by the named state `evidence` declares. Same status:
#: a declared ordering, not a measurement.
UNCERTAINTY_WEIGHT = {
    EV.CURRENT_ROLE_COLD_START: 1.0,
    EV.OFFENSIVE_DEPTH_UNKNOWN: 0.85,
    EV.CURRENT_GAME_ROLE_UNCERTAIN: 0.7,
    EV.HISTORICAL_PRIOR_DOMINANT: 0.5,
    EV.EVIDENCE_SUFFICIENT: 0.15,
}

WEIGHT_PROVENANCE = (
    'DECLARED ORDERINGS, NOT FITTED. Both weight tables express which of two '
    'situations deserves a reviewer first. Neither was estimated from data, '
    'neither has a confidence interval, and neither may be adjusted to change '
    'which players a slate escalates. If an ordering turns out to be wrong '
    'that is a design change with a written reason, not a tune.')

EXTERNAL_QUARANTINE = (
    'REVIEW_PRIORITY_ONLY_NEVER_A_MODEL_INPUT. An external projection or a '
    'sportsbook price may only raise the priority with which a human looks at '
    'a player. It must never reach a projection, a role, a share, a team '
    'volume, an appearance probability or a draw.')


@dataclass
class PlayerReviewVerdict:
    gsis_id: str
    display_name: Optional[str]
    team: Optional[str]
    tier: str
    priority: float
    impact: float
    disagreement: float
    uncertainty: float
    uncertainty_state: str
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    research_questions: List[str] = field(default_factory=list)
    forced_by_blocking: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            'gsis_id': self.gsis_id, 'display_name': self.display_name,
            'team': self.team, 'tier': self.tier,
            'priority': round(self.priority, 6),
            'factors': {'impact': round(self.impact, 6),
                        'disagreement': round(self.disagreement, 6),
                        'uncertainty': round(self.uncertainty, 6)},
            'uncertainty_state': self.uncertainty_state,
            'forced_by_blocking': self.forced_by_blocking,
            'conflict_codes': sorted({c['code'] for c in self.conflicts}),
            'reasons': self.reasons,
            'research_questions': self.research_questions,
        }


def _impact(d, slate_max: float) -> float:
    """How much this player can move a lineup, as a fraction of the slate's
    largest projection. Scale-free on purpose: a slate the model projects
    uniformly low still ranks its players against each other correctly, which
    the absolute version did not."""
    v = d.headline
    if v is None or slate_max <= 0:
        return 0.0
    return max(0.0, min(1.0, float(v) / slate_max))


def _disagreement(conflicts, external: Optional[Dict[str, float]],
                  severity_weight) -> (float, List[str]):
    reasons: List[str] = []
    w = 0.0
    for c in conflicts:
        cw = severity_weight.get(c['severity'], 0.0)
        w = max(w, cw)
        reasons.append(f'{c["code"]} ({c["severity"]})')
    if external:
        for name, gap in sorted(external.items()):
            g = max(0.0, min(1.0, abs(float(gap))))
            w = max(w, g * severity_weight.get(AUD.REVIEW, 0.6))
            reasons.append(f'external disagreement {name}={gap:+.3f} '
                           f'[{EXTERNAL_QUARANTINE.split(".")[0]}]')
    return min(1.0, w), reasons


def _questions(d, conflicts) -> List[str]:
    """What a deep review of this player would actually have to establish.

    Written as questions rather than instructions because the reviewer may
    find the answer is that the model was right.
    """
    qs: List[str] = []
    codes = {c['code'] for c in conflicts}
    if d.uncertainty_state == EV.CURRENT_ROLE_COLD_START:
        qs.append('no offensive snap has been measured for him this season -- '
                  'what does the projection rest on, and is that prior right '
                  'for this club and this room?')
    if AUD.C_ROOM_ORDER_INVERTED in codes:
        qs.append('the model puts him ahead of a higher-listed teammate on '
                  'opportunity while measuring no higher on any axis -- what '
                  'produces the inversion, and is it downstream of role?')
    if AUD.C_ST_ONLY_OFFENSIVE_LOAD in codes:
        qs.append('his only depth listing is a special-teams unit -- trace '
                  'exactly where offensive opportunity enters for him.')
    if d.axis('routes').grade == EV.UNAVAILABLE and \
            (d.mean('targets') or 0.0) > 0:
        qs.append('his receiving role is measured on raw offensive snaps '
                  'because routes are unavailable -- is there a pass-game '
                  'role here that snaps would hide?')
    if d.axis('vacated_opportunity').grade == EV.REDISTRIBUTED:
        qs.append('part of his opportunity was assigned because a teammate is '
                  'out -- does he in fact play that role, or does someone '
                  'else on the roster?')
    if d.axis('injury_designation').value and \
            any((d.axis('injury_designation').value or {}).values()):
        qs.append('he carries an injury designation -- does the appearance '
                  'and the workload both reflect it?')
    if not qs:
        qs.append('confirm the measured axes still describe his role and that '
                  'nothing has changed since the information cut.')
    return qs


def escalate(dossiers: Sequence[Any], audit_result: Dict[str, Any], *,
             deep_research_capacity: int,
             standard_review_capacity: Optional[int] = None,
             external_disagreement: Optional[Dict[str, Dict[str, float]]] = None,
             severity_weight: Optional[Dict[str, float]] = None,
             uncertainty_weight: Optional[Dict[str, float]] = None) -> Outcome:
    """Rank every player and allocate the reviewer's day.

    `deep_research_capacity` is how many players can genuinely receive deep
    research on this slate. It is a statement about available time. Passing a
    number larger than the population is fine and means everyone gets it.
    """
    if not dossiers:
        return Outcome.blocked(
            'NOTHING_TO_ESCALATE',
            'no dossiers were supplied, so no reviewer allocation can be '
            'made.', cause=Cause.DATA)
    if deep_research_capacity < 0:
        return Outcome.fail(
            'NEGATIVE_REVIEW_CAPACITY',
            f'deep_research_capacity={deep_research_capacity} is not a '
            f'number of players.', value=deep_research_capacity)

    sw = dict(SEVERITY_WEIGHT); sw.update(severity_weight or {})
    uw = dict(UNCERTAINTY_WEIGHT); uw.update(uncertainty_weight or {})
    ext = external_disagreement or {}

    by_player = collections.defaultdict(list)
    for c in audit_result.get('conflicts', []):
        by_player[c.get('gsis_id')].append(c)

    heads = [d.headline for d in dossiers if d.headline is not None]
    slate_max = max(heads) if heads else 0.0

    verdicts: List[PlayerReviewVerdict] = []
    for d in dossiers:
        cs = by_player.get(d.gsis_id, [])
        imp = _impact(d, slate_max)
        dis, reasons = _disagreement(cs, ext.get(d.gsis_id), sw)
        unc = uw.get(d.uncertainty_state, 0.5)
        forced = any(c['severity'] == AUD.BLOCKING for c in cs)
        verdicts.append(PlayerReviewVerdict(
            gsis_id=d.gsis_id, display_name=d.display_name, team=d.team,
            tier=AUTOMATED_ONLY, priority=imp * dis * unc,
            impact=imp, disagreement=dis, uncertainty=unc,
            uncertainty_state=d.uncertainty_state,
            conflicts=cs, reasons=reasons + d.uncertainty_why,
            research_questions=_questions(d, cs),
            forced_by_blocking=forced))

    # Blocking first, then priority, then a stable name tiebreak so two runs
    # over the same slate produce the same list.
    verdicts.sort(key=lambda v: (not v.forced_by_blocking, -v.priority,
                                 v.display_name or '', v.gsis_id))
    std_cap = (len(verdicts) if standard_review_capacity is None
               else standard_review_capacity)
    for i, v in enumerate(verdicts):
        if v.forced_by_blocking or i < deep_research_capacity:
            v.tier = DEEP_RESEARCH
        elif i < deep_research_capacity + std_cap and v.priority > 0:
            v.tier = STANDARD_REVIEW
        else:
            v.tier = AUTOMATED_ONLY

    by_tier = collections.Counter(v.tier for v in verdicts)
    n_forced = sum(1 for v in verdicts if v.forced_by_blocking)
    return Outcome.ok(
        'REVIEW_PRIORITIES_ASSIGNED',
        {'verdicts': verdicts,
         'by_tier': {t: by_tier.get(t, 0) for t in TIERS},
         'n_forced_by_blocking': n_forced,
         'deep_research_capacity': deep_research_capacity,
         'capacity_is_a_time_budget_not_a_threshold': True,
         'weight_provenance': WEIGHT_PROVENANCE,
         'external_disagreement_quarantine': EXTERNAL_QUARANTINE,
         'n_with_external_disagreement': len(ext),
         'slate_max_headline': slate_max},
        detail=f'{by_tier.get(DEEP_RESEARCH, 0)} deep '
               f'({n_forced} forced by a blocking conflict), '
               f'{by_tier.get(STANDARD_REVIEW, 0)} standard, '
               f'{by_tier.get(AUTOMATED_ONLY, 0)} automated')
