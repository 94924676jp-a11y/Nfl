"""One saved dossier per player per slate. Built before projections are
approved, kept afterwards so the number can be explained three weeks later.

WHAT A DOSSIER IS FOR

The question this artifact exists to answer is "why did the model have this
guy at 14.8?", asked long after the run directory has stopped being fresh in
anyone's memory. So the dossier does not store a conclusion. It stores the
evidence that was available at the information cut, graded, with the axes
that were NOT available named out loud, and the projection decomposed into
the components that produced it.

WHERE ITS FOOTBALL FACTS COME FROM, SINCE THE MIGRATION

Every football fact in a dossier now arrives from `PregameSlateState`. The
dossier no longer decides which room a player is in, no longer averages his
snap percentages, no longer reads a roster field and no longer interprets a
depth listing. Those are statements about football and they belong to the
state layer; this module's job is to EXPLAIN the state, not to be a second
place that computes it.

What remains this module's own work: the projection decomposition, the
simulation metadata, the uncertainty classification, and the human-readable
axis set that makes two dossiers from different weeks comparable.

The axis `source` and `note` strings below are this module's descriptive
labels and are deliberately stable. The upstream provenance -- the blob, its
hash, when it was retrieved, what grade the state gave it -- is carried
separately and completely in `evidence_provenance`, so nothing is flattened.

THE ORDER IS FIXED AND THE STAGES DO NOT MERGE

    raw evidence -> dossier -> reconciliation -> role/opportunity state
    -> projection -> simulation -> projection audit -> optimizer

This module owns the second stage and reads the others. It does not compute a
projection, it does not assign a role, and it does not decide anything about a
lineup. It reads what those stages produced and records what each one rested
on. A stage that graded its own evidence would be marking its own homework.

WHAT IT REFUSES TO DO

  * It never infers availability from omission. A player absent from the DK
    salary file, or absent from the snap file, or absent from the depth chart,
    reads ABSENT on that axis and nothing else follows from it.
  * It never lets special-teams depth touch an offensive room. The two come
    from `depth_role` as separate fields and are carried separately here.
  * It never turns a missing source into a zero. Routes, pass-block snaps and
    personnel groupings are UNAVAILABLE for 2026 and every dossier says so on
    every player, whether or not anyone would have looked.
  * It never admits a sportsbook price, an external projection, an ownership
    estimate or an optimizer metric as evidence about football. Those may be
    attached later, by the escalation stage, under a name that says they are
    review-only.
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
from nfl.production.state import availability as AV               # noqa: E402
from nfl.production.state import slate_state as SS                 # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'player-pregame-dossier-1'

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
    #: The upstream PregameSlateState axis behind each football axis above:
    #: its grade, the blob and hash it came from, when it was retrieved. The
    #: axes themselves keep this module's stable descriptive labels, so this
    #: is where the canonical provenance is preserved rather than flattened.
    evidence_provenance: Dict[str, Any] = field(default_factory=dict)
    #: Identity of the state this dossier explains.
    state_identity: Dict[str, Any] = field(default_factory=dict)
    #: The PlayerState this dossier was built from. NOT serialised -- an
    #: artifact would then carry the same football facts twice, under two
    #: vocabularies, which is precisely the duplication this migration is
    #: removing. It is here so that a reader of a dossier can reach the
    #: AUTHORITATIVE football truth rather than this module's relabelled
    #: copy of it, which is what the audit now does.
    player_state: Any = None

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
            'evidence_provenance': self.evidence_provenance,
            'state_identity': self.state_identity,
        }

    def football_body(self, exclude_axes: Sequence[str] = ()
                      ) -> Dict[str, Any]:
        """Everything a dossier SAYS about football, without the canonical
        metadata the migration added. This is the thing two builders have to
        agree on exactly; `evidence_provenance` and `state_identity` are new
        and have no counterpart in the pre-migration builder, so comparing
        them would be comparing something to nothing."""
        d = self.as_dict()
        for k in ('evidence_provenance', 'state_identity'):
            d.pop(k, None)
        d['spec_version'] = 'COMPARED_WITHOUT_SPEC_VERSION'
        for a in exclude_axes:
            d['axes'].pop(a, None)
        return d

    def football_hash(self, exclude_axes: Sequence[str] = ()) -> str:
        """`exclude_axes` is for comparing across a DECLARED semantic change.
        Naming the axis at the call site is the point: a caller has to say
        which field it is choosing not to compare, and why, rather than a
        difference going unnoticed."""
        return hashlib.sha256(json.dumps(
            self.football_body(exclude_axes), sort_keys=True,
            separators=(',', ':'), default=str).encode()).hexdigest()[:16]


#: dossier axis -> the PregameSlateState axis it is built from. This is the
#: whole football surface the dossier consumes, in one place, so "what does
#: the dossier get from canonical state" is a list rather than an audit.
STATE_AXIS_SOURCE = {
    'roster_status': 'roster_status',
    'official_availability': 'availability',
    'injury_designation': 'injury_report_status',
    'offensive_depth_rank': 'offensive_depth',
    'special_teams_role': 'special_teams_depth',
    'room': 'room',
    'role': 'role_state',
    'role_support': 'role_state',
    'current_season_snap_share': 'current_season_participation.'
                                 'offensive_snap_share',
    'current_season_snap_games': 'current_season_participation.'
                                 'offensive_snap_games',
    'special_teams_snap_share': 'current_season_participation.'
                                'special_teams_snap_share',
    'carries': 'current_season_opportunity.current_season_carries',
    'targets': 'current_season_opportunity.current_season_targets',
    'carry_share': 'current_season_opportunity.carry_share',
    'target_share': 'current_season_opportunity.target_share',
}


#: The ONE place this module renames a canonical availability state, and the
#: only reason it does: `audit.py`, `player_board.py` and `dfs/classic/pool.py`
#: all key on the literal 'INACTIVE'. Renaming it here would be a silent
#: behavioural change in three consumers this slice may not touch. Every other
#: state passes through under its canonical name.
AVAILABILITY_ALIAS = {AV.OFFICIAL_INACTIVE: 'INACTIVE'}


def _availability_axis(state_axis: EV.Axis) -> EV.Axis:
    """Official availability, taken from the canonical state and not re-decided.

    WHAT CHANGED AND WHY. This function used to answer ACTIVE for any player
    who was not on the inactive list, whenever a non-empty `inactive_ids` set
    had been supplied. Two errors were stacked there. It read a container's
    shape as proof that both clubs had published; and even with both clubs
    published, ACTIVE does not follow. `nonqb/inactives.py` settled the second
    one under an owner ruling of 2026-09-10: the publication asserts who is
    OUT, and its complement holds players who will dress alongside
    practice-squad members who were never going to.

    So this function now RELABELS what `state/availability.py` decided. It
    makes no availability judgement of its own, and the ACTIVE value it used
    to emit is no longer reachable from any evidence this checkout holds.
    """
    if state_axis is None:
        return EV.Axis('official_availability', AV.UNKNOWN, EV.UNAVAILABLE,
                       note='no availability axis was present on the '
                            'canonical state')
    v = state_axis.value
    return EV.Axis('official_availability',
                   AVAILABILITY_ALIAS.get(v, v),
                   state_axis.grade, source=state_axis.source,
                   observed_at=state_axis.observed_at,
                   note=state_axis.note)


def build_dossiers(*, universe_rows: Sequence[dict],
                   role_rows: Sequence[dict] = (),
                   snap_rows: Sequence[dict] = (),
                   usage_rows: Sequence[dict] = (),
                   projection: Optional[dict] = None,
                   inactive_ids=None,
                   vacated: Optional[Dict[str, dict]] = None,
                   opportunity_attribution: Optional[Dict[str, dict]] = None,
                   information_cut: Optional[str] = None) -> Outcome:
    """COMPATIBILITY SHIM. The old call path, on the new implementation.

    It wraps the rows it is given into a PregameSlateState and hands that to
    `build_from_state`. There is exactly one dossier implementation; this
    function only reaches it by a different door, and the door is temporary.
    Callers should migrate to `build_from_state`.
    """
    st = SS.state_from_legacy_rows(
        universe_rows, role_rows=role_rows, snap_rows=snap_rows,
        usage_rows=usage_rows, inactive_ids=inactive_ids,
        information_cut=information_cut)
    if st.state.name != 'PASS':
        return st
    return build_from_state(
        st.value, projection=projection, vacated=vacated,
        opportunity_attribution=opportunity_attribution,
        information_cut=information_cut,
        legacy_rows_by_id={r.get('gsis_id'): r for r in universe_rows})


def build_from_state(state, *, projection: Optional[dict] = None,
                     vacated: Optional[Dict[str, dict]] = None,
                     opportunity_attribution: Optional[Dict[str, dict]] = None,
                     information_cut: Optional[str] = None,
                     legacy_rows_by_id: Optional[Dict[str, dict]] = None
                     ) -> Outcome:
    """A dossier for EVERY player in the canonical state.

    Coverage is the point. A player the model did not emit is exactly the
    player a reviewer needs to see, because "we have no number for him" is a
    finding and an empty row is not.

    `legacy_rows_by_id` supplies only `season` and `week`, which
    PregameSlateState carries at the top level and not per player. It is a
    convenience for the shim and nothing football-bearing is read from it.
    """
    if state is None or not state.players:
        return Outcome.blocked(
            'UNIVERSE_EMPTY',
            'the canonical state carries no players, so there is nobody to '
            'review. An empty review is not a completed review.',
            cause=Cause.DATA)

    proj = (projection or {}).get('per_player', {})
    vacated = vacated or {}
    legacy_rows_by_id = legacy_rows_by_id or {}
    cut = information_cut or state.information_cut

    out: List[PlayerPregameDossier] = []
    for ps in state.players:
        pid = ps.gsis_id
        lr = legacy_rows_by_id.get(pid, {})
        role = ps.role_state.value if isinstance(ps.role_state.value,
                                                 dict) else {}
        d = PlayerPregameDossier(
            gsis_id=pid, display_name=ps.display_name, team=ps.team,
            opponent=ps.opponent, game_id=ps.game_id,
            season=lr.get('season', state.season),
            week=lr.get('week', state.week),
            information_cut=cut, support_state=ps.support_state,
            player_state=ps)

        A = d.axes
        A['roster_status'] = EV.Axis(
            'roster_status', ps.roster_status.value,
            EV.DECLARED if ps.roster_status.value else EV.UNAVAILABLE,
            source='weekly_rosters vintage', observed_at=cut)
        A['official_availability'] = _availability_axis(ps.availability)

        inj = (ps.injury_report_status.value, ps.injury_practice_status.value)
        A['injury_designation'] = EV.Axis(
            'injury_designation', {'report': inj[0], 'practice': inj[1]},
            EV.DECLARED if any(inj) else EV.UNAVAILABLE,
            source='injuries vintage',
            note=None if any(inj) else 'no designation was published for this '
                                       'player; that is not a clean bill')

        # DEPTH: two axes, and they never merge. The state keeps them apart;
        # this module only relabels them.
        odr = ps.offensive_depth.value
        A['offensive_depth_rank'] = EV.Axis(
            'offensive_depth_rank', odr,
            EV.DECLARED if odr is not None else EV.UNAVAILABLE,
            source='depth_charts vintage, typed through depth_role',
            observed_at=ps.extra.get('depth_dt'),
            note=ps.extra.get('offensive_depth_state'))
        st_role = ps.special_teams_depth.value
        A['special_teams_role'] = EV.Axis(
            'special_teams_role', st_role,
            EV.DECLARED if st_role else EV.UNAVAILABLE,
            source='depth_charts vintage, special-teams groups only',
            observed_at=ps.extra.get('depth_dt'),
            note='a special-teams listing informs no offensive room and must '
                 'never be read as one')

        # ROOM comes from the state now. This module used to derive it from
        # the roster position, which made it a second place that decided what
        # a player is.
        room_from_role = ps.room.source == 'role_state'
        A['room'] = EV.Axis(
            'room', ps.room.value,
            EV.DECLARED if ps.room.value else EV.UNAVAILABLE,
            source='roster_position -> POSITION_ROOM',
            note=None if room_from_role else
            'derived from roster_position; role_state supplied no row for '
            'this player')
        A['role'] = EV.Axis(
            'role', role.get('role'),
            EV.MEASURED if role.get('role_support') == 'ROLE_SUPPORTED'
            else (EV.PRIOR if role.get('role') else EV.UNAVAILABLE),
            source='role_state.assign', note=role.get('role_why'))
        A['role_support'] = EV.Axis(
            'role_support', role.get('role_support'),
            EV.MEASURED if role.get('role_support') else EV.UNAVAILABLE,
            note='; '.join(role.get('role_unsupported_why') or []) or None)

        # MEASURED participation, averaged by the state layer.
        part = ps.current_season_participation
        share = part['offensive_snap_share'].value
        games_axis = part['offensive_snap_games']
        games = games_axis.value or 0
        st_share = part['special_teams_snap_share'].value
        A['current_season_snap_share'] = EV.Axis(
            'current_season_snap_share', share,
            EV.MEASURED if share is not None else EV.COLD_START,
            source='PFR snap counts, weeks strictly before this one',
            window=f'{games} game(s)',
            note=None if share is not None else
            'no offensive snap has been measured for this player this season')
        A['current_season_snap_games'] = EV.Axis(
            'current_season_snap_games', games,
            EV.MEASURED if games_axis.grade == EV.MEASURED else EV.COLD_START,
            source='PFR snap counts')
        A['special_teams_snap_share'] = EV.Axis(
            'special_teams_snap_share', st_share,
            EV.MEASURED if st_share is not None else EV.COLD_START,
            source='PFR snap counts, st_pct',
            note='kept apart from the offensive share on purpose')

        opp = ps.current_season_opportunity
        for k, canon in (('carries', 'current_season_carries'),
                         ('targets', 'current_season_targets')):
            v = opp[canon].value
            A[k] = EV.Axis(k, v,
                           EV.MEASURED if v not in (None, '') else
                           EV.COLD_START,
                           source='lawful play-by-play usage panel, prior '
                                  'weeks')
        cor = opp['club_of_record'].value
        for k in ('carry_share', 'target_share'):
            v = opp[k].value
            A[k] = EV.Axis(k, v,
                           EV.MEASURED if v is not None else EV.COLD_START,
                           source='lawful play-by-play usage panel, prior '
                                  f'weeks, club of record {cor}')

        # STAGE-6 ATTRIBUTION, read rather than reconstructed. Still passed
        # in: Stage 6 is not migrated in this slice.
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

        # CANONICAL PROVENANCE, kept rather than flattened. Every football
        # axis above says which state axis produced it, with that axis's own
        # grade, source and observation time.
        d.evidence_provenance = {
            k: _upstream(ps, path) for k, path in
            sorted(STATE_AXIS_SOURCE.items())}
        d.state_identity = {
            'state_version': state.state_version,
            'registry_identity': state.registry_identity,
            'information_cut': state.information_cut,
            'builder_identity': state.builder_identity,
            'freshness_verdict': (state.freshness or {}).get('verdict'),
            'source_hashes': {
                f: (v or {}).get('content_sha256')
                for f, v in (state.source_hashes or {}).items()},
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


def _upstream(ps, path: str) -> Dict[str, Any]:
    """The state axis behind a dossier axis, as it stands in the state."""
    cur = ps
    for part in path.split('.'):
        cur = (cur.get(part) if isinstance(cur, dict)
               else getattr(cur, part, None))
        if cur is None:
            return {'state_axis': path, 'present': False}
    d = cur.as_dict() if isinstance(cur, EV.Axis) else {'value': cur}
    d['state_axis'] = path
    d['present'] = True
    # The role blob is the whole governed role row and is quoted in the axes
    # above; repeating it here would double the artifact for no new fact.
    if path == 'role_state' and isinstance(d.get('value'), dict):
        d['value'] = sorted(d['value'])
    return d


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
