"""FROZEN COPY of review/dossier.py at commit f43c30e. DO NOT EDIT.

This is the accepted pre-migration dossier builder, kept so that the migrated
one can be proved to produce the same dossiers rather than merely plausible
ones. It is a separate artifact from the live module for the same reason
`dfs/classic/reference.py` is: a change to one must not be able to be
silently a change to both.

Its SPEC_VERSION is rewritten so an artifact can never be confused about
which builder wrote it.
"""

from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import evidence as EV                   # noqa: E402
from nfl.production.universe import depth_role as DR               # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'player-pregame-dossier-reference-f43c30e'

#: Axes every dossier carries, in the order a reader should read them. Naming
#: them here rather than letting each builder emit its own set is what makes
#: two dossiers from different weeks comparable.
AXIS_ORDER = (
    'roster_status', 'official_availability', 'injury_designation',
    'offensive_depth_rank', 'special_teams_role', 'room',
    'role', 'role_support',
    'current_season_snap_share', 'current_season_snap_games',
    'special_teams_snap_share',
    'carries', 'targets', 'carry_share', 'target_share',
    'routes', 'routes_per_dropback', 'pass_block_snaps', 'run_block_snaps',
    'personnel_11', 'personnel_12', 'personnel_13', 'personnel_21',
    'alignment_slot_outside',
    'vacated_opportunity', 'opportunity_attribution',
    'coach_news', 'transactions',
)

#: Metrics pulled out of the draw store for the projection decomposition, as
#: (layer/metric, component name). Each one is a quantity the football model
#: actually emitted, not a derived summary.
PROJECTION_METRICS = (
    ('rushing/carries', 'carries'),
    ('rushing/rushing_yards', 'rushing_yards'),
    ('rushing/rushing_td', 'rushing_td'),
    ('receiving/targets', 'targets'),
    ('receiving/receptions', 'receptions'),
    ('receiving/receiving_yards', 'receiving_yards'),
    ('receiving/receiving_td', 'receiving_td'),
    ('qb/att', 'pass_attempts'),
    ('qb/pyds', 'passing_yards'),
    ('qb/ptd', 'passing_td'),
    ('qb/int', 'interceptions'),
    ('qb/rush_opp', 'qb_rush_opportunities'),
    ('dk_scoring/dk_points', 'dk_points'),
)

#: The DK points array is the one every downstream consumer reads, so it gets
#: its own name and its absence is a stated fact rather than a missing key.
HEADLINE_METRIC = 'dk_points'


def _f(v, default=None):
    try:
        if v is None or v == '':
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=None):
    f = _f(v)
    return default if f is None else int(f)


def _summ(vec) -> Dict[str, float]:
    """Mean, sd and the quantiles a reader actually quotes, from draws."""
    import numpy as np
    a = np.asarray(vec, dtype=float)
    if a.size == 0:
        return {}
    q = np.percentile(a, [5, 25, 50, 75, 95])
    return {'mean': float(a.mean()), 'sd': float(a.std(ddof=1)) if a.size > 1
            else 0.0,
            'p05': float(q[0]), 'p25': float(q[1]), 'p50': float(q[2]),
            'p75': float(q[3]), 'p95': float(q[4]),
            'p_zero': float((a <= 0).mean()), 'n_draws': int(a.size)}


# --------------------------------------------------------------------------
# reading the sealed draw artifact
# --------------------------------------------------------------------------
def read_projection(draws_dir) -> Outcome:
    """Per-player per-metric summaries out of a sealed draw artifact.

    Returns the digests of both files alongside the numbers, so a dossier
    quoting a projection also carries proof of which artifact it read. A
    directory with no manifest is BLOCKED, never an empty projection.
    """
    d = pathlib.Path(draws_dir)
    man_p, npz_p = d / 'player_draws_manifest.json', d / 'player_draws.npz'
    for p in (man_p, npz_p):
        if not p.exists():
            return Outcome.blocked(
                'DRAW_ARTIFACT_ABSENT',
                f'{p} does not exist, so no projection can be decomposed. '
                f'An absent artifact is not a projection of zero.',
                cause=Cause.DATA)
    man = json.loads(man_p.read_text())
    digests = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (man_p, npz_p)}

    import numpy as np
    arrays: Dict[str, Any] = {}
    with np.load(npz_p) as z:
        for k in z.files:
            arrays[k.replace('__', '/', 1)] = np.asarray(z[k])

    per_player: Dict[str, Dict[str, Dict[str, float]]] = (
        collections.defaultdict(dict))
    metrics_present, metrics_absent = [], []
    for key, comp in PROJECTION_METRICS:
        layer = key.split('/', 1)[0]
        lay = man.get('layers', {}).get(layer)
        M = arrays.get(key)
        if lay is None or M is None:
            metrics_absent.append(key)
            continue
        ids = lay.get('row_ids') or []
        if len(ids) != M.shape[0]:
            return Outcome.fail(
                'DRAW_ROW_AXIS_DISAGREES_WITH_MANIFEST',
                f'{key} has {M.shape[0]} rows but the manifest names '
                f'{len(ids)} row_ids for layer {layer}. Reading a projection '
                f'off a misaligned axis attributes one player\'s draws to '
                f'another, which is the worst defect this file could have.',
                value={'layer': layer, 'metric': key})
        metrics_present.append(key)
        for i, pid in enumerate(ids):
            per_player[pid][comp] = _summ(M[i])

    if not per_player:
        return Outcome.fail(
            'DRAW_ARTIFACT_CARRIES_NO_KNOWN_METRIC',
            f'none of the {len(PROJECTION_METRICS)} declared projection '
            f'metrics is present in {d}. Reporting an empty decomposition as '
            f'success is the failure mode this project pays for most.',
            value={'arrays_found': sorted(arrays)[:20]})

    return Outcome.ok(
        'PROJECTION_READ',
        {'per_player': dict(per_player), 'digests': digests,
         'run_id': man.get('run_id'), 'game_id': man.get('game_id'),
         'n_draws': man.get('n_draws'),
         'metrics_present': metrics_present,
         'metrics_absent': metrics_absent,
         'row_teams': {lid: man['layers'][lid].get('row_teams')
                       for lid in man.get('layers', {})}},
        detail=f'{len(per_player)} players, {len(metrics_present)} metrics')


# --------------------------------------------------------------------------
# the dossier
# --------------------------------------------------------------------------
@dataclass
class PlayerPregameDossier:
    gsis_id: str
    display_name: Optional[str]
    team: Optional[str]
    opponent: Optional[str]
    game_id: Optional[str]
    season: Optional[int]
    week: Optional[int]
    information_cut: Optional[str]
    support_state: Optional[str]
    axes: Dict[str, EV.Axis] = field(default_factory=dict)
    projection: Dict[str, EV.ProjectionComponent] = field(default_factory=dict)
    projection_source: Dict[str, Any] = field(default_factory=dict)
    uncertainty_state: str = EV.EVIDENCE_SUFFICIENT
    uncertainty_why: List[str] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)

    # -- reading helpers used by the audit and escalation stages ------------
    def axis(self, name: str) -> EV.Axis:
        return self.axes.get(name, EV.unavailable(name))

    def value(self, name: str):
        return self.axis(name).value

    def mean(self, component: str) -> Optional[float]:
        c = self.projection.get(component)
        return None if c is None else c.value

    @property
    def headline(self) -> Optional[float]:
        return self.mean(HEADLINE_METRIC)

    @property
    def current_game_evidence_grades(self) -> List[str]:
        return [self.axis(a).grade for a in
                ('official_availability', 'role', 'current_season_snap_share')]

    @property
    def unavailable_axes(self) -> List[str]:
        return [a for a in AXIS_ORDER
                if self.axis(a).grade == EV.UNAVAILABLE]

    def as_dict(self) -> Dict[str, Any]:
        return {
            'spec_version': SPEC_VERSION,
            'gsis_id': self.gsis_id, 'display_name': self.display_name,
            'team': self.team, 'opponent': self.opponent,
            'game_id': self.game_id, 'season': self.season, 'week': self.week,
            'information_cut': self.information_cut,
            'support_state': self.support_state,
            'uncertainty_state': self.uncertainty_state,
            'uncertainty_why': self.uncertainty_why,
            'axes': {a: self.axis(a).as_dict() for a in AXIS_ORDER},
            'projection': {k: v.as_dict()
                           for k, v in sorted(self.projection.items())},
            'projection_source': self.projection_source,
            'conflicts': self.conflicts,
        }


def _availability_axis(u: Dict[str, Any], have_inactives: bool,
                       is_inactive: bool) -> EV.Axis:
    """Official availability, or the honest absence of it.

    `officially_inactive` False means one of two very different things and
    this is the function that refuses to conflate them: with a declaration in
    hand it means DECLARED ACTIVE; without one it means NOT DECLARED, which
    is not evidence of activity.
    """
    if is_inactive:
        return EV.Axis('official_availability', 'INACTIVE', EV.DECLARED,
                       source='official inactive declaration',
                       observed_at=u.get('information_cut'))
    if have_inactives:
        return EV.Axis('official_availability', 'ACTIVE', EV.DECLARED,
                       source='official inactive declaration, by exclusion '
                              'within a complete board',
                       observed_at=u.get('information_cut'),
                       note='the board is complete for this game, so absence '
                            'from it is a positive statement. Without a '
                            'complete board this axis would read NOT_DECLARED')
    return EV.Axis('official_availability', 'NOT_DECLARED', EV.UNAVAILABLE,
                   note='no official inactive board was supplied for this '
                        'game. ACTIVE must not be inferred from omission.')


def build_dossiers(*, universe_rows: Sequence[dict],
                   role_rows: Sequence[dict] = (),
                   snap_rows: Sequence[dict] = (),
                   usage_rows: Sequence[dict] = (),
                   projection: Optional[dict] = None,
                   inactive_ids=None,
                   vacated: Optional[Dict[str, dict]] = None,
                   opportunity_attribution: Optional[Dict[str, dict]] = None,
                   information_cut: Optional[str] = None) -> Outcome:
    """A dossier for EVERY player in the universe, not only the projected ones.

    Coverage is the point. A player the model did not emit is exactly the
    player a reviewer needs to see, because "we have no number for him" is a
    finding and an empty row is not.
    """
    if not universe_rows:
        return Outcome.blocked(
            'UNIVERSE_EMPTY',
            'no universe rows were supplied, so there is nobody to review. '
            'An empty review is not a completed review.', cause=Cause.DATA)

    inactive_ids = set(inactive_ids or ())
    have_inactives = bool(inactive_ids)
    proj = (projection or {}).get('per_player', {})
    vacated = vacated or {}

    role_by_id = {r.get('gsis_id'): r for r in role_rows if r.get('gsis_id')}

    # Measured participation, by pfr_id, from strictly earlier weeks.
    snaps = collections.defaultdict(list)
    for s in snap_rows:
        if s.get('pfr_player_id'):
            snaps[s['pfr_player_id']].append(s)

    # The usage panel arrives keyed (week, club, player) from
    # `usage_vintage.usage_season`, or as a flat sequence. Both are accepted
    # and the player key is read under either of its two spellings, because
    # guessing a field name is how an export once wrote 7,926 blank rows.
    usage_seq = (list(usage_rows.values()) if isinstance(usage_rows, dict)
                 else list(usage_rows or ()))
    usage = collections.defaultdict(lambda: collections.Counter())
    for u in usage_seq:
        pid = u.get('gsis_id') or u.get('player_id')
        if not pid:
            continue
        for k in ('carries', 'targets'):
            v = _f(u.get(k))
            if v is not None:
                usage[pid][k] += v

    out: List[PlayerPregameDossier] = []
    for u in universe_rows:
        pid = u.get('gsis_id') or ''
        r = role_by_id.get(pid, {})
        rev = r.get('evidence', {}) if isinstance(r.get('evidence'), dict) \
            else {}
        d = PlayerPregameDossier(
            gsis_id=pid, display_name=u.get('display_name'),
            team=u.get('team'), opponent=u.get('opponent'),
            game_id=u.get('game_id'), season=u.get('season'),
            week=u.get('week'),
            information_cut=information_cut or u.get('information_cut'),
            support_state=u.get('support_state'))

        A = d.axes
        A['roster_status'] = EV.Axis(
            'roster_status', u.get('roster_status'),
            EV.DECLARED if u.get('roster_status') else EV.UNAVAILABLE,
            source='weekly_rosters vintage',
            observed_at=u.get('information_cut'))
        # The declaration set the caller handed us and the field the
        # universe builder stamped must agree; either one saying INACTIVE is
        # enough, because the failure worth preventing is a player read as
        # available when some source said he is not.
        A['official_availability'] = _availability_axis(
            u, have_inactives,
            bool(u.get('officially_inactive')) or pid in inactive_ids)

        inj = (u.get('injury_report_status'), u.get('injury_practice_status'))
        A['injury_designation'] = EV.Axis(
            'injury_designation',
            {'report': inj[0], 'practice': inj[1]},
            EV.DECLARED if any(inj) else EV.UNAVAILABLE,
            source='injuries vintage',
            note=None if any(inj) else 'no designation was published for this '
                                       'player; that is not a clean bill')

        # DEPTH: two axes, and they never merge. `offensive_depth_state` is
        # carried so a reader can tell "listed nowhere offensive" from
        # "listed only on a return unit".
        odr = u.get('offensive_depth_rank')
        A['offensive_depth_rank'] = EV.Axis(
            'offensive_depth_rank', odr,
            EV.DECLARED if odr is not None else EV.UNAVAILABLE,
            source='depth_charts vintage, typed through depth_role',
            observed_at=u.get('depth_dt'),
            note=u.get('offensive_depth_state'))
        st = u.get('special_teams_role')
        A['special_teams_role'] = EV.Axis(
            'special_teams_role', st,
            EV.DECLARED if st else EV.UNAVAILABLE,
            source='depth_charts vintage, special-teams groups only',
            observed_at=u.get('depth_dt'),
            note='a special-teams listing informs no offensive room and must '
                 'never be read as one')

        # A room comes from position, which the roster states directly. So
        # it is derived here rather than borrowed from role_state: when
        # role_state REFUSES a player, the audit still has to know which room
        # his projection landed in, and that is exactly the player worth
        # checking. Falling back to role_state's value when it has one keeps
        # the two in agreement where both exist.
        room = r.get('room') or RS.POSITION_ROOM.get(
            (u.get('roster_position') or '').strip().upper())
        A['room'] = EV.Axis('room', room,
                            EV.DECLARED if room else EV.UNAVAILABLE,
                            source='roster_position -> POSITION_ROOM',
                            note=None if r.get('room') else
                            'derived from roster_position; role_state '
                            'supplied no row for this player')
        A['role'] = EV.Axis(
            'role', r.get('role'),
            EV.MEASURED if r.get('role_support') == 'ROLE_SUPPORTED'
            else (EV.PRIOR if r.get('role') else EV.UNAVAILABLE),
            source='role_state.assign', note=r.get('role_why'))
        A['role_support'] = EV.Axis(
            'role_support', r.get('role_support'),
            EV.MEASURED if r.get('role_support') else EV.UNAVAILABLE,
            note='; '.join(r.get('role_unsupported_why') or []) or None)

        # MEASURED participation. Offensive and special-teams shares are
        # separate numbers because they answer separate questions.
        mine = snaps.get(u.get('pfr_id') or '__none__', [])
        offp = [_f(s.get('offense_pct')) for s in mine]
        offp = [x for x in offp if x is not None]
        stp = [_f(s.get('st_pct')) for s in mine]
        stp = [x for x in stp if x is not None]
        A['current_season_snap_share'] = EV.Axis(
            'current_season_snap_share',
            (sum(offp) / len(offp)) if offp else None,
            EV.MEASURED if offp else EV.COLD_START,
            source='PFR snap counts, weeks strictly before this one',
            window=f'{len(offp)} game(s)',
            note=None if offp else 'no offensive snap has been measured for '
                                   'this player this season')
        A['current_season_snap_games'] = EV.Axis(
            'current_season_snap_games', len(offp),
            EV.MEASURED if mine else EV.COLD_START,
            source='PFR snap counts')
        A['special_teams_snap_share'] = EV.Axis(
            'special_teams_snap_share',
            (sum(stp) / len(stp)) if stp else None,
            EV.MEASURED if stp else EV.COLD_START,
            source='PFR snap counts, st_pct',
            note='kept apart from the offensive share on purpose')

        cu = rev.get('current_season_usage', {}) if rev else {}
        for k in ('carries', 'targets'):
            v = cu.get(k, usage.get(pid, {}).get(k))
            A[k] = EV.Axis(
                k, _f(v),
                EV.MEASURED if v not in (None, '') else EV.COLD_START,
                source='lawful play-by-play usage panel, prior weeks')
        for k in ('carry_share', 'target_share'):
            v = cu.get(k)
            A[k] = EV.Axis(k, _f(v),
                           EV.MEASURED if v is not None else EV.COLD_START,
                           source='lawful play-by-play usage panel, prior '
                                  'weeks, club of record '
                                  f'{cu.get("club_of_record")}')

        # STAGE-6 ATTRIBUTION, read rather than reconstructed. The audit used
        # to say an inversion was "not supported by any axis the review can
        # read" while the supporting axis -- the prior-season share -- was one
        # it could not see. This is that axis, emitted by the layer that used
        # it.
        att = (opportunity_attribution or {}).get(pid)
        A['opportunity_attribution'] = EV.Axis(
            'opportunity_attribution', att,
            EV.MEASURED if att else EV.UNAVAILABLE,
            source='opportunity_centre (Stage 6)',
            note=None if att else 'this run emitted no Stage-6 attribution; '
                                  'the audit must then say so rather than '
                                  'claiming no axis supports a projection')

        vac = vacated.get(pid)
        A['vacated_opportunity'] = EV.Axis(
            'vacated_opportunity', vac,
            EV.REDISTRIBUTED if vac else EV.UNAVAILABLE,
            source='post-inactives redistribution accounting',
            note='opportunity assigned because a teammate is unavailable. It '
                 'is not something this player has been measured doing.'
            if vac else 'no redistribution record was supplied for this '
                        'player; that is not the same as none occurring')

        for name in ('routes', 'routes_per_dropback', 'pass_block_snaps',
                     'run_block_snaps', 'personnel_11', 'personnel_12',
                     'personnel_13', 'personnel_21',
                     'alignment_slot_outside', 'coach_news', 'transactions'):
            A[name] = EV.unavailable(name)

        # PROJECTION DECOMPOSITION, graded by what produced it.
        p = proj.get(pid)
        if p:
            for comp, summ in sorted(p.items()):
                grade = EV.MEASURED
                derived = ['role_state', 'usage_panel', 'team_volume']
                if A['role'].grade != EV.MEASURED:
                    grade = EV.PRIOR
                if A['current_season_snap_share'].grade == EV.COLD_START:
                    grade = EV.COLD_START
                    derived = ['position prior', 'depth listing',
                               'team_volume']
                if vac:
                    grade = EV.REDISTRIBUTED
                    derived = derived + ['vacated_opportunity']
                d.projection[comp] = EV.ProjectionComponent(
                    component=comp, value=summ.get('mean'), grade=grade,
                    derived_from=derived,
                    note=json.dumps({k: round(v, 4) for k, v in summ.items()
                                     if k != 'n_draws'}, sort_keys=True))
            d.projection_source = {
                'run_id': (projection or {}).get('run_id'),
                'digests': (projection or {}).get('digests'),
                'n_draws': (projection or {}).get('n_draws'),
                'metrics_absent': (projection or {}).get('metrics_absent'),
            }
        else:
            d.projection_source = {
                'state': 'NOT_EMITTED',
                'why': 'the model wrote no draws for this player. That is a '
                       'reviewable fact, not a projection of zero.',
                'run_id': (projection or {}).get('run_id'),
            }

        d.uncertainty_state, d.uncertainty_why = _uncertainty(d)
        out.append(d)

    by_state = collections.Counter(x.uncertainty_state for x in out)
    return Outcome.ok(
        'DOSSIERS_BUILT',
        {'dossiers': out, 'n': len(out),
         'by_uncertainty_state': dict(by_state),
         'n_with_projection': sum(1 for x in out if x.projection),
         'unavailable_sources': sorted(EV.UNAVAILABLE_SOURCES)},
        detail=f'{len(out)} dossiers, '
               f'{sum(1 for x in out if x.projection)} with a projection')


def _uncertainty(d: PlayerPregameDossier):
    """Which named uncertainty state this player's evidence supports.

    Ordered most severe first. The states are the ones `evidence` declares;
    no new state is invented here, because a state that exists in one module
    and not the registry is a state nobody downstream can handle.
    """
    why: List[str] = []
    snap = d.axis('current_season_snap_share')
    role = d.axis('role')
    odr = d.axis('offensive_depth_rank')

    if snap.grade == EV.COLD_START and role.grade != EV.MEASURED:
        why.append('no offensive snap measured this season and the role is '
                   'not supported by measured participation')
        return EV.CURRENT_ROLE_COLD_START, why
    if odr.grade == EV.UNAVAILABLE and d.axis('special_teams_role').value:
        why.append('listed only on a special-teams unit, so no offensive '
                   'depth rank exists for him')
        return EV.OFFENSIVE_DEPTH_UNKNOWN, why
    if role.value in (None, 'ROLE_UNCERTAIN') or \
            d.axis('role_support').value == 'ROLE_UNSUPPORTED':
        why.append('role_state could not support a current-game role')
        return EV.CURRENT_GAME_ROLE_UNCERTAIN, why
    if snap.grade != EV.MEASURED and any(
            c.grade in (EV.PRIOR, EV.HISTORICAL) for c in
            d.projection.values()):
        why.append('the projection rests on a prior rather than on measured '
                   'current-season participation')
        return EV.HISTORICAL_PRIOR_DOMINANT, why
    return EV.EVIDENCE_SUFFICIENT, why
