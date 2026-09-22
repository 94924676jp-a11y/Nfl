"""FROZEN COPY of review/audit.py at commit 5edfc6b. DO NOT EDIT.

The accepted pre-migration audit, kept so the migrated one can be proved to
produce the same conflict set rather than a plausible one. A separate
artifact for the same reason `dfs/classic/reference.py` and
`review/dossier_reference.py` are: a change to one must not be able to be
silently a change to both.
"""

from __future__ import annotations

import collections
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import evidence as EV                   # noqa: E402
from nfl.production.review import dossier as DOS                   # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'projection-audit-reference-5edfc6b'

BLOCKING, REVIEW, NOTE = 'BLOCKING', 'REVIEW', 'NOTE'

# --- conflict codes -------------------------------------------------------
C_INACTIVE_OWNS_OPPORTUNITY = 'INACTIVE_PLAYER_OWNS_OPPORTUNITY'
C_DECLARED_STARTER_ZERO = 'DECLARED_STARTER_PROJECTED_AT_ZERO'
C_UNSUPPORTED_ROLE_PUBLISHED = 'UNSUPPORTED_ROLE_PUBLISHED'
C_COLD_START_MATERIAL = 'COLD_START_CARRIES_MATERIAL_PROJECTION'
C_ST_ONLY_OFFENSIVE_LOAD = 'SPECIAL_TEAMS_ONLY_PLAYER_CARRIES_OFFENSIVE_LOAD'
C_ROOM_ORDER_INVERTED = 'ROOM_OPPORTUNITY_ORDER_INVERTS_ROLE_ORDER'
C_RECEIVING_ROLE_ON_SNAPS_ONLY = 'RECEIVING_ROLE_RESTS_ON_RAW_SNAPS_ONLY'
C_NOT_EMITTED = 'ACTIVE_PLAYER_NOT_EMITTED_BY_MODEL'
C_REDISTRIBUTION_DOMINATES = 'REDISTRIBUTED_OPPORTUNITY_DOMINATES_MEASURED'
C_INVERSION_ON_STALE_SEASON = 'ROOM_ORDER_INVERSION_RESTS_ON_A_PRIOR_SEASON'

CONFLICTS = (C_INACTIVE_OWNS_OPPORTUNITY, C_DECLARED_STARTER_ZERO,
             C_UNSUPPORTED_ROLE_PUBLISHED, C_COLD_START_MATERIAL,
             C_ST_ONLY_OFFENSIVE_LOAD, C_ROOM_ORDER_INVERTED,
             C_RECEIVING_ROLE_ON_SNAPS_ONLY, C_NOT_EMITTED,
             C_REDISTRIBUTION_DOMINATES, C_INVERSION_ON_STALE_SEASON)

#: Opportunity metrics by room. A "material" projection means opportunity,
#: not fantasy points, because points are a scoring convention and carries
#: are football.
ROOM_OPPORTUNITY = {
    'carries': 'carries',
    'targets': 'targets',
    'dropbacks': 'pass_attempts',
}

#: The audit thresholds are REVIEW-CAPACITY choices, not fitted constants.
#: `material_opportunity` is the point below which a disagreement cannot
#: change any lineup, so flagging it would only add noise. It is stated here
#: and passed in so a caller can see it; it is not estimated from anything
#: and must never be tuned against an outcome.
DEFAULT_MATERIAL_OPPORTUNITY = 1.0
MATERIAL_OPPORTUNITY_PROVENANCE = (
    'DECLARED REVIEW-CAPACITY CHOICE, NOT MEASURED. One expected opportunity '
    'per game is the smallest quantity that can move a DK lineup at all. It '
    'is not calibrated, has no empirical support behind it, and must not be '
    'adjusted to make a slate pass.')


def _conf(code: str, severity: str, d, detail: str, **ev) -> Dict[str, Any]:
    return {'code': code, 'severity': severity, 'gsis_id': d.gsis_id,
            'display_name': d.display_name, 'team': d.team,
            'detail': detail, 'evidence': ev}


def _opportunity(d) -> float:
    """Total expected offensive opportunity, summed over rooms."""
    return sum(d.mean(m) or 0.0 for m in
               ('carries', 'targets', 'pass_attempts'))


def audit(dossiers: Sequence[DOS.PlayerPregameDossier], *,
          material_opportunity: float = DEFAULT_MATERIAL_OPPORTUNITY,
          publishable_ids=None) -> Outcome:
    """Every disagreement between a published number and its own evidence."""
    if not dossiers:
        return Outcome.blocked(
            'NOTHING_TO_AUDIT',
            'no dossiers were supplied. An audit over an empty set is not a '
            'clean audit.', cause=Cause.DATA)

    publishable = (None if publishable_ids is None else set(publishable_ids))
    conflicts: List[Dict[str, Any]] = []

    for d in dossiers:
        opp = _opportunity(d)
        avail = d.axis('official_availability')
        snap = d.axis('current_season_snap_share')
        role = d.axis('role')

        if avail.value == 'INACTIVE' and opp > 0:
            conflicts.append(_conf(
                C_INACTIVE_OWNS_OPPORTUNITY, BLOCKING, d,
                f'officially inactive, yet the model gives him {opp:.3f} '
                f'expected opportunities. An inactive player owns nothing.',
                opportunity=opp))

        if d.projection and role.value == 'STARTER' and \
                avail.value != 'INACTIVE' and opp < material_opportunity:
            conflicts.append(_conf(
                C_DECLARED_STARTER_ZERO, REVIEW, d,
                f'role_state calls him a STARTER and he is not declared out, '
                f'yet total expected opportunity is {opp:.3f}.',
                opportunity=opp, role_why=role.note))

        if d.projection and opp >= material_opportunity and \
                d.axis('role_support').value == 'ROLE_UNSUPPORTED':
            conflicts.append(_conf(
                C_UNSUPPORTED_ROLE_PUBLISHED, BLOCKING, d,
                f'{opp:.3f} expected opportunities published on a role '
                f'role_state itself refused to support.',
                opportunity=opp, why=d.axis('role_support').note))

        if d.projection and opp >= material_opportunity and \
                snap.grade == EV.COLD_START:
            conflicts.append(_conf(
                C_COLD_START_MATERIAL, REVIEW, d,
                f'{opp:.3f} expected opportunities for a player with no '
                f'measured offensive snap this season. The number comes from '
                f'a prior, and the prior is what should be reviewed.',
                opportunity=opp,
                uncertainty_state=d.uncertainty_state))

        if d.projection and opp >= material_opportunity and \
                d.axis('offensive_depth_rank').grade == EV.UNAVAILABLE and \
                d.axis('special_teams_role').value:
            conflicts.append(_conf(
                C_ST_ONLY_OFFENSIVE_LOAD, BLOCKING, d,
                f'listed only as {d.axis("special_teams_role").value} with no '
                f'offensive depth rank, yet carrying {opp:.3f} expected '
                f'offensive opportunities. Special-teams standing must never '
                f'become offensive workload.',
                opportunity=opp,
                special_teams_role=d.axis('special_teams_role').value))

        if publishable is not None and d.gsis_id in publishable and \
                not d.projection:
            conflicts.append(_conf(
                C_NOT_EMITTED, BLOCKING, d,
                'this player is in the publishable population and the model '
                'emitted no draws for him. Silence is not a forecast.',
                support_state=d.support_state))

        vac = d.axis('vacated_opportunity')
        if vac.grade == EV.REDISTRIBUTED and opp >= material_opportunity:
            measured = (d.mean('carries') or 0.0) + (d.mean('targets') or 0.0)
            conflicts.append(_conf(
                C_REDISTRIBUTION_DOMINATES, REVIEW, d,
                f'{opp:.3f} expected opportunities of which a redistributed '
                f'share is recorded. Redistributed opportunity is assigned, '
                f'not observed, and a projection resting mostly on it is a '
                f'claim about a teammate\'s absence.',
                opportunity=opp, measured_component=measured,
                vacated=vac.value))

        # Receiving roles rest on raw snaps because routes do not exist for
        # 2026. Named on every receiver rather than silently assumed away.
        if d.projection and (d.mean('targets') or 0.0) >= \
                material_opportunity and \
                d.axis('routes').grade == EV.UNAVAILABLE:
            conflicts.append(_conf(
                C_RECEIVING_ROLE_ON_SNAPS_ONLY, NOTE, d,
                f'{d.mean("targets"):.3f} expected targets on a role measured '
                f'by raw offensive snaps. Routes are the correct denominator '
                f'and are UNAVAILABLE for 2026, so this role has not been '
                f'examined on the axis that would settle it.',
                targets=d.mean('targets'),
                why=EV.UNAVAILABLE_SOURCES['routes']))

    conflicts += _room_order_conflicts(dossiers, material_opportunity)

    by_sev = collections.Counter(c['severity'] for c in conflicts)
    by_code = collections.Counter(c['code'] for c in conflicts)
    value = {
        'conflicts': conflicts,
        'n_conflicts': len(conflicts),
        'by_severity': dict(by_sev), 'by_code': dict(by_code),
        'n_blocking': by_sev.get(BLOCKING, 0),
        'n_audited': len(dossiers),
        'material_opportunity': material_opportunity,
        'material_opportunity_provenance': MATERIAL_OPPORTUNITY_PROVENANCE,
    }
    if by_sev.get(BLOCKING):
        return Outcome.fail(
            'PROJECTION_AUDIT_BLOCKING_CONFLICTS',
            f'{by_sev[BLOCKING]} blocking conflict(s) across '
            f'{len(dossiers)} audited players: '
            f'{sorted(set(c["code"] for c in conflicts if c["severity"] == BLOCKING))}',
            value=value)
    return Outcome.ok(
        'PROJECTION_AUDIT_CLEAN_OF_BLOCKING_CONFLICTS', value,
        detail=f'{len(conflicts)} conflict(s), none blocking, over '
               f'{len(dossiers)} players')


def _room_order_conflicts(dossiers, material_opportunity) -> List[Dict]:
    """Where the opportunity order inverts the role order inside one room.

    This is the generalised form of the defect found on the NYG backfield: a
    back the club lists fourth out-carrying the back it lists first. The check
    does NOT assert that depth order must be obeyed -- clubs are wrong about
    their own backfields all the time, and a measured usage share is better
    evidence than a listing. It asserts something narrower and defensible:
    when the model inverts the listing, SOMETHING must justify the inversion,
    and if the higher-projected player's own evidence is weaker on every axis
    then nothing does.
    """
    out: List[Dict[str, Any]] = []
    byroom = collections.defaultdict(list)
    for d in dossiers:
        room, rank = d.axis('room').value, d.axis('offensive_depth_rank').value
        if room and rank is not None:
            byroom[(d.team, room)].append(d)

    for (team, room), members in sorted(byroom.items(),
                                        key=lambda kv: (kv[0][0] or '',
                                                        kv[0][1] or '')):
        metric = ROOM_OPPORTUNITY.get(room)
        if metric is None or len(members) < 2:
            continue
        active = [d for d in members
                  if d.axis('official_availability').value != 'INACTIVE'
                  and d.projection]
        for hi in active:
            for lo in active:
                rank_hi = hi.axis('offensive_depth_rank').value
                rank_lo = lo.axis('offensive_depth_rank').value
                if rank_hi is None or rank_lo is None or rank_hi <= rank_lo:
                    continue
                o_hi = hi.mean(metric) or 0.0
                o_lo = lo.mean(metric) or 0.0
                if o_hi <= o_lo or o_hi < material_opportunity:
                    continue
                # An inversion is only a conflict when the deeper-listed
                # player has no better evidence on the measured axes either.
                m_hi = hi.axis('current_season_snap_share').value or 0.0
                m_lo = lo.axis('current_season_snap_share').value or 0.0
                u_hi = hi.value(metric.split('_')[0] if metric != 'pass_attempts'
                                else 'carries') or 0.0
                u_lo = lo.value(metric.split('_')[0] if metric != 'pass_attempts'
                                else 'carries') or 0.0
                if m_hi > m_lo or u_hi > u_lo:
                    continue
                # An inversion can only be called unsupported when there was
                # something to read. With neither player measured on snaps
                # nor on prior usage, "no axis supports it" is vacuous -- no
                # axis contradicts it either, and both men are already
                # covered by COLD_START_CARRIES_MATERIAL_PROJECTION. Firing
                # here would manufacture a finding out of two absences.
                readable = [ax for ax, a, b in (
                    ('snap_share',
                     hi.axis('current_season_snap_share').grade,
                     lo.axis('current_season_snap_share').grade),
                    ('prior_usage',
                     hi.axis('carries').grade, lo.axis('carries').grade))
                    if EV.MEASURED in (a, b)]
                if not readable:
                    continue
                # WHAT DOES THE GENERATOR SAY IT USED? Stage 6 emits its own
                # decomposition, and reading it is the difference between
                # "nothing supports this" and "something does, and it is
                # older than the evidence that disagrees". Those are
                # different findings and only one of them is a defect.
                att_hi = hi.value('opportunity_attribution') or {}
                contrib = att_hi.get('contributions') or {}
                stale_tier = max(
                    (k for k in ('PRIOR_SEASON_MEASURED', 'CAREER_HISTORY')
                     if contrib.get(k)),
                    key=lambda k: contrib.get(k, 0.0), default=None)
                cur = contrib.get('CURRENT_SEASON_MEASURED', 0.0)
                if stale_tier and contrib[stale_tier] > cur:
                    out.append(_conf(
                        C_INVERSION_ON_STALE_SEASON, REVIEW, hi,
                        f'listed {room} rank {rank_hi} and projected '
                        f'{o_hi:.3f} {metric} ahead of '
                        f'{lo.display_name} at rank {rank_lo} on '
                        f'{o_lo:.3f}, measuring no higher on any '
                        f'CURRENT-season axis. Stage 6 says the projection '
                        f'rests on {stale_tier} '
                        f'({contrib[stale_tier]:.4f}) over current-season '
                        f'evidence ({cur:.4f}). Something DOES support the '
                        f'inversion -- it is just older than the evidence '
                        f'that contradicts it.',
                        room=room, metric=metric, team=team,
                        axes_readable=readable,
                        dominant_tier=stale_tier,
                        contributions=contrib,
                        higher={'gsis_id': hi.gsis_id, 'rank': rank_hi,
                                metric: o_hi, 'snap_share': m_hi,
                                'prior_usage': u_hi},
                        lower={'gsis_id': lo.gsis_id,
                               'display_name': lo.display_name,
                               'rank': rank_lo, metric: o_lo,
                               'snap_share': m_lo, 'prior_usage': u_lo}))
                    continue
                out.append(_conf(
                    C_ROOM_ORDER_INVERTED, REVIEW, hi,
                    f'listed {room} rank {rank_hi} and projected '
                    f'{o_hi:.3f} {metric}, ahead of '
                    f'{lo.display_name} at rank {rank_lo} on {o_lo:.3f} -- '
                    f'while also measuring no higher on snap share '
                    f'({m_hi:.4f} vs {m_lo:.4f}) or on prior usage '
                    f'({u_hi:.3f} vs {u_lo:.3f}). '
                    + ('Stage 6 emitted no attribution for him, so the '
                       'review cannot say what it rests on.'
                       if not att_hi else
                       'Stage 6\'s own decomposition names no tier that '
                       'outweighs his current-season evidence either.'),
                    room=room, metric=metric, team=team,
                    axes_readable=readable,
                    higher={'gsis_id': hi.gsis_id, 'rank': rank_hi,
                            metric: o_hi, 'snap_share': m_hi,
                            'prior_usage': u_hi},
                    lower={'gsis_id': lo.gsis_id,
                           'display_name': lo.display_name,
                           'rank': rank_lo, metric: o_lo,
                           'snap_share': m_lo, 'prior_usage': u_lo}))
    return out
