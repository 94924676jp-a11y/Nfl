"""PregameSlateState v0. One authoritative football truth for one game.

WHAT THIS SLICE IS AND IS NOT

It is a TYPED BOUNDARY, not a new ingestion path. `build_one_game` delegates
the football work to `player_universe.build`, which is already governed and
already draws every input through `vintage_selector`. What is new is that the
result becomes ONE object with a declared schema, a registry identity, source
hashes and a content hash, so that downstream modules can eventually stop
each rebuilding their own version of "who exists and what is true about him".

It is NOT a rewrite of the chain. No consumer is re-pointed in this slice.
`run_forecast`, the optimizer, the dossier and the board all still read what
they read today, and the equivalence test exists to prove that this object
represents the same football truth they are reading.

THREE THINGS THIS OBJECT REFUSES TO DO

1. UNAVAILABLE NEVER BECOMES ZERO. An axis with no evidence carries grade
   UNAVAILABLE and a note saying why. Zero is a measurement.
2. OFFENSIVE AND SPECIAL-TEAMS DEPTH STAY SEPARATE. They are two facts. A
   returner's standing is not an answer to a workload question, and merging
   them is the defect that turned RB1/PR2 into PR2 on the 2026-09-21 capture.
3. NO SPORTSBOOK FIELD ENTERS. The schedules vintage carries `spread_line`,
   `total_line`, `home_moneyline`, `away_moneyline`, `over_odds`,
   `under_odds` and `spread_odds`. GameState reads NONE of them, and
   `FORBIDDEN_SCHEDULE_FIELDS` names them so a future reader has to delete a
   line with a reason attached rather than add one by accident.

AND ONE THING IT REFUSES TO READ EVEN THOUGH IT IS SITTING THERE

`temp` and `wind` in the schedules vintage are REALISED weather. For a
completed game they are filled in, and a pregame state that read them would
be carrying the outcome of the thing it is forecasting. Weather is therefore
an UNAVAILABLE axis here with that reason recorded, not a column read.
"""
from __future__ import annotations

import csv
import dataclasses
import datetime as _dt
import gzip
import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import vintage_selector as VS               # noqa: E402
from nfl.production.review import evidence as EV                      # noqa: E402
from nfl.production.state import registry as FR                       # noqa: E402
from nfl.production.universe import player_universe as PU             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nfl-pregame-slate-state-0'

#: Sportsbook-derived columns in the schedules vintage. Named so that reading
#: one is a deliberate act. The rule is the owner's: sportsbook prices must
#: not become predictive inputs into the football model.
FORBIDDEN_SCHEDULE_FIELDS = (
    'spread_line', 'total_line', 'home_moneyline', 'away_moneyline',
    'home_spread_odds', 'away_spread_odds', 'over_odds', 'under_odds',
    'total', 'result', 'home_score', 'away_score', 'overtime')

#: Realised, not forecast. See the module docstring.
POSTGAME_WEATHER_FIELDS = ('temp', 'wind')

#: Families this builder draws, and whether the RAW blob is the one needed.
#: weekly_rosters is raw because the reduced vintage drops `status`, which is
#: the column roster membership is decided on.
SOURCE_FAMILIES: Tuple[Tuple[str, bool], ...] = (
    ('weekly_rosters', True), ('depth_charts', False),
    ('injuries', False), ('schedules', False))


def _not_supplied(name: str, why: str) -> EV.Axis:
    """An axis this BUILD was not given. Distinct from one the world cannot
    supply: `routes` is unavailable everywhere, whereas a role state simply
    was not handed to this call, and a reader must be able to tell which."""
    return EV.Axis(name=name, value=None, grade=EV.UNAVAILABLE, note=why)


def _declared(name: str, value, src: str, observed_at: str,
              note: str = None) -> EV.Axis:
    """A fact a club or a league feed DECLARED. Never a measurement."""
    return EV.Axis(name=name, value=value, grade=EV.DECLARED, source=src,
                   observed_at=observed_at, note=note)


@dataclass
class PlayerState:
    """Everything true about one player at the information cut."""
    gsis_id: str
    display_name: Optional[str]
    team: Optional[str]
    opponent: Optional[str]
    game_id: str
    #: what he PLAYS
    football_position: EV.Axis = None
    #: what DraftKings will accept him at. A SEPARATE fact.
    dfs_position: EV.Axis = None
    availability: EV.Axis = None
    injury_report_status: EV.Axis = None
    injury_practice_status: EV.Axis = None
    #: two axes, never merged
    offensive_depth: EV.Axis = None
    special_teams_depth: EV.Axis = None
    declared_starter: EV.Axis = None
    #: the governed role output, carried as supplied
    role_state: EV.Axis = None
    current_season_participation: Dict[str, EV.Axis] = field(
        default_factory=dict)
    current_season_opportunity: Dict[str, EV.Axis] = field(
        default_factory=dict)
    historical_participation: Dict[str, EV.Axis] = field(default_factory=dict)
    historical_opportunity: Dict[str, EV.Axis] = field(default_factory=dict)
    #: the universe layer's own verdict, preserved verbatim
    support_state: Optional[str] = None
    support_state_why: Optional[str] = None
    evidence_tier: Optional[int] = None
    roster_status: EV.Axis = None
    depth_listings: List[Dict] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict:
        def ax(a):
            return None if a is None else a.as_dict()
        return {
            'gsis_id': self.gsis_id, 'display_name': self.display_name,
            'team': self.team, 'opponent': self.opponent,
            'game_id': self.game_id,
            'football_position': ax(self.football_position),
            'dfs_position': ax(self.dfs_position),
            'availability': ax(self.availability),
            'injury_report_status': ax(self.injury_report_status),
            'injury_practice_status': ax(self.injury_practice_status),
            'offensive_depth': ax(self.offensive_depth),
            'special_teams_depth': ax(self.special_teams_depth),
            'declared_starter': ax(self.declared_starter),
            'role_state': ax(self.role_state),
            'roster_status': ax(self.roster_status),
            'current_season_participation': {
                k: v.as_dict() for k, v in
                sorted(self.current_season_participation.items())},
            'current_season_opportunity': {
                k: v.as_dict() for k, v in
                sorted(self.current_season_opportunity.items())},
            'historical_participation': {
                k: v.as_dict() for k, v in
                sorted(self.historical_participation.items())},
            'historical_opportunity': {
                k: v.as_dict() for k, v in
                sorted(self.historical_opportunity.items())},
            'support_state': self.support_state,
            'support_state_why': self.support_state_why,
            'evidence_tier': self.evidence_tier,
            'depth_listings': self.depth_listings,
            'extra': self.extra,
        }


@dataclass
class TeamState:
    club: str
    game_id: str
    opponent: str
    is_home: bool
    coach: EV.Axis = None
    player_ids: List[str] = field(default_factory=list)
    current_season_tendencies: Dict[str, EV.Axis] = field(default_factory=dict)
    availability_verdict: Optional[Dict] = None

    def as_dict(self) -> Dict:
        return {
            'club': self.club, 'game_id': self.game_id,
            'opponent': self.opponent, 'is_home': self.is_home,
            'coach': None if self.coach is None else self.coach.as_dict(),
            'n_players': len(self.player_ids),
            'player_ids': sorted(self.player_ids),
            'current_season_tendencies': {
                k: v.as_dict() for k, v in
                sorted(self.current_season_tendencies.items())},
            'availability_verdict': self.availability_verdict,
        }


@dataclass
class GameState:
    game_id: str
    season: int
    week: int
    home: str
    away: str
    kickoff: EV.Axis = None
    venue: EV.Axis = None
    surface: EV.Axis = None
    roof: EV.Axis = None
    weather: EV.Axis = None
    environment: Dict[str, EV.Axis] = field(default_factory=dict)

    def as_dict(self) -> Dict:
        def ax(a):
            return None if a is None else a.as_dict()
        return {'game_id': self.game_id, 'season': self.season,
                'week': self.week, 'home': self.home, 'away': self.away,
                'kickoff': ax(self.kickoff), 'venue': ax(self.venue),
                'surface': ax(self.surface), 'roof': ax(self.roof),
                'weather': ax(self.weather),
                'environment': {k: v.as_dict() for k, v in
                                sorted(self.environment.items())}}


@dataclass
class PregameSlateState:
    state_version: str
    slate_key: str
    season: int
    week: int
    information_cut: str
    registry_identity: str
    registry_name: str
    source_hashes: Dict[str, Dict]
    freshness: Dict
    builder_identity: str
    built_at: str
    games: List[GameState] = field(default_factory=list)
    teams: List[TeamState] = field(default_factory=list)
    players: List[PlayerState] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def body(self) -> Dict:
        """Everything the content hash covers. `built_at` is EXCLUDED: it is
        when the object was written, not what it says, and including it would
        make an identical state hash differently on every rebuild -- which
        would defeat the one thing a content hash is for."""
        return {
            'state_version': self.state_version, 'slate_key': self.slate_key,
            'season': self.season, 'week': self.week,
            'information_cut': self.information_cut,
            'registry_identity': self.registry_identity,
            'registry_name': self.registry_name,
            'source_hashes': self.source_hashes,
            'freshness': self.freshness,
            'builder_identity': self.builder_identity,
            'games': [g.as_dict() for g in self.games],
            'teams': [t.as_dict() for t in self.teams],
            'players': [p.as_dict() for p in
                        sorted(self.players, key=lambda x: x.gsis_id)],
            'notes': self.notes,
        }

    def content_hash(self) -> str:
        blob = json.dumps(self.body(), sort_keys=True,
                          separators=(',', ':')).encode()
        return 'PSS-' + hashlib.sha256(blob).hexdigest()[:16]

    def as_dict(self) -> Dict:
        d = self.body()
        d['built_at'] = self.built_at
        d['state_content_hash'] = self.content_hash()
        d['n_players'] = len(self.players)
        return d

    def player(self, gsis_id: str) -> Optional[PlayerState]:
        return next((p for p in self.players if p.gsis_id == gsis_id), None)


# --------------------------------------------------------------------------
def _rows(blob: str) -> List[Dict]:
    p = _REPO / blob
    op = gzip.open if str(p).endswith('.gz') else open
    with op(p, 'rt', newline='') as f:
        return list(csv.DictReader(f))


def _raw_twin(blob: str) -> str:
    return blob.replace('.reduced.csv.gz', '.raw.csv.gz')


def select_sources(cut: str) -> Outcome:
    """Every family this builder needs, selected AND verified to exist.

    THE DEFECT THIS CATCHES. `vintage_selector` answers "which capture is
    lawful at the cut" and it answers it correctly. It does not answer "are
    the bytes on disk". Eight of the eighteen weekly_rosters captures in this
    checkout have only their REDUCED blob stored, and `player_universe`
    rewrites the selected path to the RAW twin because the reduced vintage
    drops `status`. Selecting one of those eight therefore produces a
    FileNotFoundError from inside an open() -- an unnamed crash where a
    governed refusal belongs. This function turns that into
    SOURCE_BLOB_MISSING before any reading starts.
    """
    sources: Dict[str, Dict] = {}
    missing: List[Dict] = []
    degraded: List[str] = []
    for fam, need_raw in SOURCE_FAMILIES:
        o = VS.select(fam, as_of=cut)
        if o.state.name != 'PASS':
            sources[fam] = {'state': o.state.name, 'code': o.code}
            degraded.append(fam)
            continue
        v = o.value
        want = _raw_twin(v.blob) if need_raw else v.blob
        if not (_REPO / want).exists():
            missing.append({'family': fam, 'selected_blob': v.blob,
                            'needed_blob': want,
                            'retrieved_at': v.retrieved_at})
            continue
        sources[fam] = {
            'state': 'PASS', 'blob': v.blob, 'read_blob': want,
            'content_sha256': v.content_sha256,
            'retrieved_at': v.retrieved_at, 'published_at': v.published_at,
            'capture_id': v.capture_id, 'selection_rule': v.selection_rule,
        }
    if missing:
        return Outcome.fail(
            'SOURCE_BLOB_MISSING',
            f'{len(missing)} selected vintage capture(s) name a blob that is '
            f'not on disk: {missing}. The selector was right about which '
            f'capture is lawful; the bytes are not here. Reading on would '
            f'raise FileNotFoundError from inside an open(), which is an '
            f'unnamed crash where a refusal belongs.',
            missing=missing)
    return Outcome.ok('SOURCES_SELECTED',
                      {'sources': sources, 'degraded': degraded},
                      detail=f'{len(sources)} family(ies); '
                             f'{len(degraded)} unavailable at the cut')


def _game_state(game_id: str, season: int, week: int, cut: str,
                sources: Dict) -> Outcome:
    s = sources.get('schedules') or {}
    if s.get('state') != 'PASS':
        return Outcome.blocked(
            'SCHEDULE_VINTAGE_UNAVAILABLE',
            f'no lawful schedules capture at {cut}, so kickoff, venue, roof '
            f'and surface cannot be stated. Inventing them is the defect.',
            cause=Cause.DATA)
    row = next((r for r in _rows(s['read_blob'])
                if r.get('game_id') == game_id), None)
    if row is None:
        return Outcome.fail(
            'GAME_NOT_IN_SCHEDULE',
            f'{game_id!r} does not appear in the lawful schedules capture. '
            f'A game id that names no game is not a game, and the club codes '
            f'parsed out of it would be fiction.',
            game_id=game_id)
    src = f"{s['read_blob']}#{s['content_sha256'][:12]}"
    obs = s['retrieved_at']
    kick = f"{row.get('gameday')} {row.get('gametime')}".strip()
    return Outcome.ok('GAME_STATE_BUILT', GameState(
        game_id=game_id, season=season, week=week,
        home=row.get('home_team'), away=row.get('away_team'),
        kickoff=_declared('kickoff', kick or None, src, obs),
        venue=_declared('venue', row.get('stadium') or None, src, obs),
        surface=_declared('surface', row.get('surface') or None, src, obs),
        roof=_declared('roof', row.get('roof') or None, src, obs),
        weather=_not_supplied(
            'weather',
            'the schedules vintage carries `temp` and `wind`, but those are '
            'REALISED weather: for a completed game they are filled in, so a '
            'pregame state that read them would carry the outcome of the '
            'thing it is forecasting. No pregame forecast source is wired '
            'in, so this is UNAVAILABLE rather than read.'),
        environment={
            'home_rest': _declared('home_rest', row.get('home_rest') or None,
                                   src, obs),
            'away_rest': _declared('away_rest', row.get('away_rest') or None,
                                   src, obs),
            'div_game': _declared('div_game', row.get('div_game') or None,
                                  src, obs),
        }), detail=f'{game_id} at {row.get("stadium")}')


def build_one_game(season: int, week: int, game_id: str, cut: str, *,
                   emitted_ids=None, inactive_ids=None, removed_ids=None,
                   salary_resolved_ids=None,
                   role_by_id: Dict[str, Any] = None,
                   dfs_position_by_id: Dict[str, str] = None,
                   current_season_by_id: Dict[str, Dict] = None,
                   historical_by_id: Dict[str, Dict] = None,
                   registry: FR.Registry = None,
                   builder_identity: str = None) -> Outcome:
    """The canonical pregame state for ONE game at ONE information cut.

    The football work is `player_universe.build`'s and is not repeated here.
    What this adds is the typed boundary, the registry identity, the verified
    source hashes and the content hash.

    Everything the universe layer does not know -- governed role output, DFS
    position, current-season and historical usage -- is an OPTIONAL argument.
    Not supplying it yields an axis graded UNAVAILABLE with a note saying it
    was not supplied to this build. It never yields a zero, and it never
    yields a quiet omission.
    """
    reg = registry or FR.PREGAME
    role_by_id = dict(role_by_id or {})
    dfs_position_by_id = dict(dfs_position_by_id or {})
    current_season_by_id = dict(current_season_by_id or {})
    historical_by_id = dict(historical_by_id or {})

    src_o = select_sources(cut)
    if src_o.state.name != 'PASS':
        return src_o
    sources = src_o.value['sources']
    degraded = src_o.value['degraded']

    gs_o = _game_state(game_id, season, week, cut, sources)
    if gs_o.state.name != 'PASS':
        return gs_o
    game: GameState = gs_o.value

    uni = PU.build(season, week, game_id, cut,
                   emitted_ids=emitted_ids, inactive_ids=inactive_ids,
                   removed_ids=removed_ids,
                   salary_resolved_ids=salary_resolved_ids)
    if uni.state.name != 'PASS':
        return uni

    ros = sources['weekly_rosters']
    ros_src = f"{ros['read_blob']}#{ros['content_sha256'][:12]}"
    ros_obs = ros['retrieved_at']
    dep = sources.get('depth_charts') or {}
    dep_src = (f"{dep.get('read_blob')}#{(dep.get('content_sha256') or '')[:12]}"
               if dep.get('state') == 'PASS' else None)
    dep_obs = dep.get('retrieved_at')
    inj = sources.get('injuries') or {}
    inj_src = (f"{inj.get('read_blob')}#{(inj.get('content_sha256') or '')[:12]}"
               if inj.get('state') == 'PASS' else None)
    inj_obs = inj.get('retrieved_at')
    have_inactives = inactive_ids is not None

    players: List[PlayerState] = []
    for r in uni.value:
        pid = r['gsis_id']
        off_rank, off_state = r['offensive_depth_rank'], r[
            'offensive_depth_state']
        # DECLARED STARTER is derived from the OFFENSIVE rank only, and when
        # the offensive rank is unknown the answer is UNKNOWN -- not False.
        # "Not listed first" and "we do not know where he is listed" are
        # different claims and only one of them is evidence.
        if off_rank is None:
            starter = _not_supplied(
                'declared_starter',
                f'offensive depth is {off_state}, so whether the club lists '
                f'him first is unknown. Absence of a first-place listing is '
                f'not a declaration that he is not the starter.')
        else:
            starter = _declared('declared_starter', off_rank == 1, dep_src,
                                dep_obs,
                                note=f'offensive depth rank {off_rank}')
        if have_inactives:
            avail = _declared(
                'availability',
                'INACTIVE' if r['officially_inactive'] else 'NOT_ON_INACTIVE_LIST',
                'official_inactives', cut,
                note='NOT_ON_INACTIVE_LIST is not ACTIVE. ACTIVE may not be '
                     'inferred from omission unless the governing source '
                     'permits it.')
        else:
            avail = _not_supplied(
                'availability',
                'no official inactive list was supplied to this build. '
                'Availability is therefore unknown, and it may not be '
                'inferred from roster status or from DraftKings salary '
                'presence.')
        cs = current_season_by_id.get(pid) or {}
        hs = historical_by_id.get(pid) or {}

        def _pack(d: Dict, names: Sequence[str], grade: str,
                  absent_why: str) -> Dict[str, EV.Axis]:
            out = {}
            for n in names:
                spec = reg.get(n)
                if n in d:
                    out[n] = EV.Axis(name=n, value=d[n], grade=grade,
                                     source=spec.source_family if spec else None,
                                     observed_at=cut)
                elif spec is not None and spec.evidence_grade == EV.UNAVAILABLE:
                    out[n] = EV.Axis(name=n, value=None,
                                     grade=EV.UNAVAILABLE, note=spec.note)
                else:
                    out[n] = _not_supplied(n, absent_why)
            return out

        part_names = ('offensive_snaps', 'routes_run')
        opp_names = ('current_season_carries', 'current_season_targets')
        not_given = ('not supplied to this build. PregameSlateState v0 is a '
                     'boundary, not an ingestion path: usage is passed in by '
                     'the caller that already computed it, and an axis '
                     'nobody passed is UNAVAILABLE, never zero.')
        players.append(PlayerState(
            gsis_id=pid, display_name=r['display_name'], team=r['team'],
            opponent=r['opponent'], game_id=game_id,
            football_position=_declared('football_position',
                                        r['roster_position'], ros_src,
                                        ros_obs),
            dfs_position=(
                _declared('dfs_position', dfs_position_by_id[pid],
                          'dk_salaries', cut)
                if pid in dfs_position_by_id else _not_supplied(
                    'dfs_position',
                    'no DraftKings salary export was supplied to this build. '
                    'Its absence says nothing about whether the player is '
                    'available.')),
            availability=avail,
            injury_report_status=(
                _declared('injury_report_status', r['injury_report_status'],
                          inj_src, inj_obs,
                          note='absence of a designation is not a '
                               'declaration of health')
                if inj_src else _not_supplied(
                    'injury_report_status',
                    'no lawful injuries capture at the cut')),
            injury_practice_status=(
                _declared('injury_practice_status',
                          r['injury_practice_status'], inj_src, inj_obs)
                if inj_src else _not_supplied(
                    'injury_practice_status',
                    'no lawful injuries capture at the cut')),
            offensive_depth=EV.Axis(
                name='offensive_depth_rank', value=off_rank,
                grade=EV.DECLARED if off_rank is not None else EV.UNAVAILABLE,
                source=dep_src, observed_at=dep_obs,
                note=f'state {off_state}; a special-teams rank is NOT an '
                     f'answer to this axis'),
            special_teams_depth=EV.Axis(
                name='special_teams_role', value=r['special_teams_role'],
                grade=(EV.DECLARED if r['special_teams_role'] is not None
                       else EV.UNAVAILABLE),
                source=dep_src, observed_at=dep_obs,
                note='informs no offensive workload room'),
            declared_starter=starter,
            role_state=(
                EV.Axis(name='role_state', value=role_by_id[pid],
                        grade=EV.DECLARED, source='universe/role_state',
                        observed_at=cut)
                if pid in role_by_id else _not_supplied(
                    'role_state',
                    'no governed role output was supplied to this build. v0 '
                    'carries role as the existing layer emits it; the '
                    'PlayerRoleProfile ontology is the NEXT migration and is '
                    'deliberately not coupled to this one.')),
            roster_status=_declared('roster_status', r['roster_status'],
                                    ros_src, ros_obs),
            current_season_participation=_pack(
                cs, part_names, EV.MEASURED, not_given),
            current_season_opportunity=_pack(
                cs, opp_names, EV.MEASURED, not_given),
            historical_participation=_pack(
                hs, part_names, EV.HISTORICAL, not_given),
            historical_opportunity=_pack(
                hs, opp_names, EV.HISTORICAL, not_given),
            support_state=r['support_state'],
            support_state_why=r['support_state_why'],
            evidence_tier=r['evidence_tier'],
            depth_listings=r['depth_listings'],
            extra={k: r[k] for k in (
                'football_name', 'roster_depth_chart_position',
                'roster_status_abbr', 'jersey_number', 'years_exp',
                'rookie_year', 'pfr_id', 'espn_id', 'depth_pos_abb',
                'depth_rank', 'depth_dt', 'offensive_depth_state',
                'officially_inactive') if k in r},
        ))

    sched = next((r for r in _rows(sources['schedules']['read_blob'])
                  if r.get('game_id') == game_id), {})
    teams: List[TeamState] = []
    for club in (game.away, game.home):
        coach_col = 'home_coach' if club == game.home else 'away_coach'
        teams.append(TeamState(
            club=club, game_id=game_id,
            opponent=game.home if club == game.away else game.away,
            is_home=club == game.home,
            coach=_declared(
                'coach', sched.get(coach_col) or None,
                f"{sources['schedules']['read_blob']}"
                f"#{sources['schedules']['content_sha256'][:12]}",
                sources['schedules']['retrieved_at']),
            player_ids=[p.gsis_id for p in players if p.team == club],
            current_season_tendencies={
                n: _not_supplied(
                    n, 'team volume is not supplied to this build. v0 is a '
                       'boundary; the team-volume layer stays where it is '
                       'until it is migrated deliberately.')
                for n in ('team_dropbacks', 'team_carries', 'team_targets')},
            availability_verdict={
                'official_inactives_supplied': have_inactives,
                'note': 'without an official inactive list no availability '
                        'claim is made for any player on this club'},
        ))

    fresh = {
        'verdict': 'DEGRADED' if degraded else 'SOURCES_PRESENT',
        'degraded_families': degraded,
        'note': ('a family unavailable at the cut is recorded, not filled '
                 'in. This verdict describes the SOURCES this builder drew; '
                 'it is not the chain-level freshness gate, which stays '
                 'where it is until its consumer is migrated.'),
        'universe_evidence_missing': bool(uni.evidence.get('evidence_missing')),
    }
    state = PregameSlateState(
        state_version=SPEC_VERSION,
        slate_key=game_id, season=season, week=week, information_cut=cut,
        registry_identity=reg.identity(), registry_name=reg.name,
        source_hashes={k: v for k, v in sorted(sources.items())},
        freshness=fresh,
        builder_identity=builder_identity or
        f'{__name__}.build_one_game/{SPEC_VERSION}+{PU.SPEC_VERSION}',
        built_at=_dt.datetime.now(_dt.timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        games=[game], teams=teams, players=players,
        notes=['delegates the football work to player_universe.build; this '
               'object is a typed boundary, not a second ingestion path',
               'no sportsbook field is read: '
               + ', '.join(FORBIDDEN_SCHEDULE_FIELDS),
               'weather is UNAVAILABLE by refusal, not by absence: '
               + ', '.join(POSTGAME_WEATHER_FIELDS)
               + ' in the schedules vintage are realised, not forecast'],
    )
    return Outcome.ok(
        'PREGAME_SLATE_STATE_BUILT', state,
        spec_version=SPEC_VERSION, slate_key=game_id,
        information_cut=cut, n_players=len(players),
        registry_identity=reg.identity(),
        state_content_hash=state.content_hash(),
        degraded_families=degraded,
        detail=f'{len(players)} player(s), {len(teams)} club(s), '
               f'registry {reg.identity()}, '
               f'state {state.content_hash()}')


def write(state: PregameSlateState, path) -> Outcome:
    """Persist and READ BACK. A write nobody verified is a write nobody made."""
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = state.as_dict()
    p.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    try:
        back = json.loads(p.read_text())
    except Exception as e:                                   # pragma: no cover
        return Outcome.fail('STATE_ARTIFACT_UNREADABLE',
                            f'{p} did not read back as JSON: {e}')
    for k in ('state_version', 'information_cut', 'registry_identity',
              'source_hashes', 'state_content_hash', 'freshness'):
        if k not in back:
            return Outcome.fail(
                'STATE_ARTIFACT_INCOMPLETE',
                f'{p} is missing {k!r}, which the artifact contract requires '
                f'for it to be replayable.', missing=k)
    if back['state_content_hash'] != state.content_hash():
        return Outcome.fail(
            'STATE_ARTIFACT_HASH_MISMATCH',
            f'the artifact reads back with a different content hash than the '
            f'state that produced it.',
            wrote=state.content_hash(), read=back['state_content_hash'])
    return Outcome.ok('STATE_ARTIFACT_WRITTEN', str(p),
                      content_hash=state.content_hash(),
                      n_players=len(state.players),
                      detail=f'{p} ({p.stat().st_size} bytes)')
