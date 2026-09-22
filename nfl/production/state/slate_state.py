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
from nfl.production.state import availability as AV                   # noqa: E402
from nfl.production.state import registry as FR                       # noqa: E402
from nfl.production.universe import player_universe as PU             # noqa: E402
from nfl.production.universe import role_state as RS                  # noqa: E402
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


#: The participation axes a PlayerState carries. Named here so every builder
#: emits the same set and a reader can tell an axis that was not supplied
#: from one nobody thought of.
PARTICIPATION_AXES = ('offensive_snaps', 'offensive_snap_share',
                      'offensive_snap_games', 'special_teams_snap_share',
                      'routes_run')
OPPORTUNITY_AXES = ('current_season_carries', 'current_season_targets',
                    'carry_share', 'target_share', 'club_of_record')

#: What a caller that supplied nothing is told. Distinct from UNAVAILABLE in
#: the world.
NOT_GIVEN = ('not supplied to this build. PregameSlateState is a boundary, '
             'not an ingestion path: usage is passed in by the caller that '
             'computed it, and an axis nobody passed is UNAVAILABLE, never '
             'zero.')


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
    #: which workload room the player's position puts him in. Football state,
    #: so it lives here. It used to be derived inside the dossier, which made
    #: the dossier a second place that decided what a player is.
    room: EV.Axis = None
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
            'room': ax(self.room),
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
def _f(v, default=None):
    """A float, or the default. Never a zero standing in for a blank."""
    try:
        if v is None or v == '':
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


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


@dataclass
class _SourceCtx:
    """Where each axis's bytes came from, as an axis `source` string.

    ONE place builds a PlayerState. This carries the difference between the
    two ways of reaching it: `from_verified` when the vintage store was read
    through the selector, `legacy` when a caller handed over rows it had
    already built. The second exists only so the old dossier call path keeps
    working during the migration, and it says so in every axis it stamps.
    """
    roster: Optional[str]
    roster_obs: Optional[str]
    depth: Optional[str]
    depth_obs: Optional[str]
    injury: Optional[str]
    injury_obs: Optional[str]
    #: What is actually known about the official inactive declaration. A
    #: STRUCTURE, never a boolean derived from a container's shape -- that
    #: substitution is the defect this field exists to make impossible.
    inactive_evidence: 'AV.InactiveEvidence'
    verified: bool

    @staticmethod
    def from_verified(sources: Dict, cut: str, *,
                      inactive_evidence) -> '_SourceCtx':
        def tag(fam):
            d = sources.get(fam) or {}
            if d.get('state') != 'PASS':
                return None, None
            return (f"{d['read_blob']}#{d['content_sha256'][:12]}",
                    d['retrieved_at'])
        r, ro = tag('weekly_rosters')
        dp, do = tag('depth_charts')
        ij, io = tag('injuries')
        return _SourceCtx(r, ro, dp, do, ij, io, inactive_evidence, True)

    @staticmethod
    def legacy(cut: str, *, inactive_evidence) -> '_SourceCtx':
        m = ('supplied as already-built universe rows by the legacy call '
             'path; no vintage capture was read or hashed by this builder')
        return _SourceCtx(m, cut, m, cut, m, cut, inactive_evidence, False)


def participation_from_snaps(snap_rows: Sequence[dict]) -> Dict[str, Any]:
    """Offensive and special-teams participation from PFR snap rows.

    MOVED HERE FROM THE DOSSIER. Averaging a player's snap percentages is a
    statement about football, so it belongs to the state layer; the dossier's
    job is to explain the number, not to be a second place that computes it.
    The two shares stay separate because they answer separate questions.
    """
    off = [x for x in (_f(r.get('offense_pct')) for r in snap_rows)
           if x is not None]
    st = [x for x in (_f(r.get('st_pct')) for r in snap_rows) if x is not None]
    # A KEY IS OMITTED RATHER THAN SET TO NONE OR ZERO. That is what carries
    # the difference between "measured at 0%" and "never measured", and the
    # state layer turns an omitted key into an UNAVAILABLE axis. Note that
    # `offensive_snap_games` is present whenever ANY snap row exists, even if
    # none of them carried an offensive percentage: the player was seen, and
    # that is a different fact from not being seen.
    out: Dict[str, Any] = {}
    if off:
        out['offensive_snap_share'] = sum(off) / len(off)
    if snap_rows:
        out['offensive_snap_games'] = len(off)
    if st:
        out['special_teams_snap_share'] = sum(st) / len(st)
    return out


def opportunity_from_usage(role_evidence: Dict[str, Any],
                           usage_totals: Dict[str, float]) -> Dict[str, Any]:
    """Current-season opportunity, preferring what the role layer measured.

    MOVED HERE FROM THE DOSSIER, for the same reason. `role_evidence` is the
    `current_season_usage` block role_state emitted; `usage_totals` is the
    fallback summed from the usage panel. Shares come from the role layer
    only, because a share without the denominator it was taken against is not
    a measurement and this function has no denominator.
    """
    cu = role_evidence or {}
    out: Dict[str, Any] = {}
    for k, name in (('carries', 'current_season_carries'),
                    ('targets', 'current_season_targets')):
        v = cu.get(k, (usage_totals or {}).get(k))
        if v not in (None, ''):
            out[name] = _f(v)
    for k in ('carry_share', 'target_share'):
        if cu.get(k) is not None:
            out[k] = _f(cu.get(k))
    if cu.get('club_of_record') is not None:
        out['club_of_record'] = cu.get('club_of_record')
    return out


def _pack(d: Dict, names: Sequence[str], grade: str, cut: str,
          reg: FR.Registry, absent_why: str) -> Dict[str, EV.Axis]:
    """Named axes, every one present, none of them a zero by default."""
    out: Dict[str, EV.Axis] = {}
    for n in names:
        spec = reg.get(n)
        if n in d:
            out[n] = EV.Axis(name=n, value=d[n], grade=grade,
                             source=spec.source_family if spec else None,
                             observed_at=cut)
        elif spec is not None and spec.evidence_grade == EV.UNAVAILABLE:
            out[n] = EV.Axis(name=n, value=None, grade=EV.UNAVAILABLE,
                             note=spec.note)
        else:
            out[n] = _not_supplied(n, absent_why)
    return out


def player_states(universe_rows: Sequence[dict], *, cut: str, game_id: str,
                  ctx: _SourceCtx, registry: FR.Registry,
                  role_by_id: Dict[str, Any] = None,
                  dfs_position_by_id: Dict[str, str] = None,
                  current_season_by_id: Dict[str, Dict] = None,
                  historical_by_id: Dict[str, Dict] = None
                  ) -> List[PlayerState]:
    """THE one place a PlayerState is constructed. Both entry points use it.

    Every row field is read with `.get`. The governed universe always emits
    the full key set, but the compatibility shim must accept exactly what the
    pre-migration dossier accepted, and that was partial rows -- a caller
    handing over four keys is a caller this must not start crashing on.
    """
    reg = registry
    role_by_id = role_by_id or {}
    dfs_position_by_id = dfs_position_by_id or {}
    current_season_by_id = current_season_by_id or {}
    historical_by_id = historical_by_id or {}
    out: List[PlayerState] = []
    for r in universe_rows:
        pid = r.get('gsis_id')
        off_rank = r.get('offensive_depth_rank')
        off_state = r.get('offensive_depth_state')
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
            starter = _declared('declared_starter', off_rank == 1, ctx.depth,
                                ctx.depth_obs,
                                note=f'offensive depth rank {off_rank}')
        # AVAILABILITY IS DECIDED IN ONE PLACE and it is not here. The rules
        # -- what the inactive publication does and does not assert, what an
        # injury designation adds, and why GAME_ACTIVE is unreachable from
        # any source in this checkout -- live in `state/availability.py`.
        avail = AV.classify(
            pid, evidence=ctx.inactive_evidence,
            injury_report_status=r.get('injury_report_status'),
            already_flagged_inactive=bool(r.get('officially_inactive')))
        role = role_by_id.get(pid)
        # ROOM. Position states it; the role layer's own room is preferred
        # when it has one, so the two agree wherever both exist. This lived
        # in the dossier and does not any more: which room a player is in is
        # football state, not an explanation of football state.
        room_v = (role or {}).get('room') if isinstance(role, dict) else None
        from_role = room_v is not None
        if room_v is None:
            room_v = RS.POSITION_ROOM.get(
                (r.get('roster_position') or '').strip().upper())
        room = EV.Axis(
            'room', room_v, EV.DECLARED if room_v else EV.UNAVAILABLE,
            source='role_state' if from_role
            else 'roster football_position -> POSITION_ROOM',
            observed_at=cut,
            note=None if from_role else 'derived from the roster position; '
                                        'the role layer supplied no row for '
                                        'this player')
        cs = dict(current_season_by_id.get(pid) or {})
        hs = dict(historical_by_id.get(pid) or {})
        out.append(PlayerState(
            gsis_id=pid, display_name=r.get('display_name'), team=r.get('team'),
            opponent=r.get('opponent'), game_id=game_id,
            football_position=_declared('football_position',
                                        r.get('roster_position'), ctx.roster,
                                        ctx.roster_obs),
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
                _declared('injury_report_status', r.get('injury_report_status'),
                          ctx.injury, ctx.injury_obs,
                          note='absence of a designation is not a '
                               'declaration of health')
                if ctx.injury else _not_supplied(
                    'injury_report_status',
                    'no lawful injuries capture at the cut')),
            injury_practice_status=(
                _declared('injury_practice_status',
                          r.get('injury_practice_status'), ctx.injury,
                          ctx.injury_obs)
                if ctx.injury else _not_supplied(
                    'injury_practice_status',
                    'no lawful injuries capture at the cut')),
            offensive_depth=EV.Axis(
                name='offensive_depth_rank', value=off_rank,
                grade=EV.DECLARED if off_rank is not None else EV.UNAVAILABLE,
                source=ctx.depth, observed_at=r.get('depth_dt'),
                note=f'state {off_state}; a special-teams rank is NOT an '
                     f'answer to this axis'),
            special_teams_depth=EV.Axis(
                name='special_teams_role', value=r.get('special_teams_role'),
                grade=(EV.DECLARED if r.get('special_teams_role') is not None
                       else EV.UNAVAILABLE),
                source=ctx.depth, observed_at=r.get('depth_dt'),
                note='informs no offensive workload room'),
            declared_starter=starter,
            room=room,
            role_state=(
                EV.Axis(name='role_state', value=role, grade=EV.DECLARED,
                        source='universe/role_state', observed_at=cut)
                if role is not None else _not_supplied(
                    'role_state',
                    'no governed role output was supplied to this build. v0 '
                    'carries role as the existing layer emits it; the '
                    'PlayerRoleProfile ontology is the NEXT migration and is '
                    'deliberately not coupled to this one.')),
            roster_status=_declared('roster_status', r.get('roster_status'),
                                    ctx.roster, ctx.roster_obs),
            current_season_participation=_pack(
                cs, PARTICIPATION_AXES, EV.MEASURED, cut, reg, NOT_GIVEN),
            current_season_opportunity=_pack(
                cs, OPPORTUNITY_AXES, EV.MEASURED, cut, reg, NOT_GIVEN),
            historical_participation=_pack(
                hs, PARTICIPATION_AXES, EV.HISTORICAL, cut, reg, NOT_GIVEN),
            historical_opportunity=_pack(
                hs, OPPORTUNITY_AXES, EV.HISTORICAL, cut, reg, NOT_GIVEN),
            support_state=r.get('support_state'),
            support_state_why=r.get('support_state_why'),
            evidence_tier=r.get('evidence_tier'),
            depth_listings=r.get('depth_listings') or [],
            extra={k: r[k] for k in (
                'football_name', 'roster_depth_chart_position',
                'roster_status_abbr', 'jersey_number', 'years_exp',
                'rookie_year', 'pfr_id', 'espn_id', 'depth_pos_abb',
                'depth_rank', 'depth_dt', 'offensive_depth_state',
                'officially_inactive') if k in r},
        ))
    return out


def build_one_game(season: int, week: int, game_id: str, cut: str, *,
                   emitted_ids=None, inactive_ids=None, removed_ids=None,
                   inactive_evidence=None,
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

    # `inactive_ids` alone becomes PARTIAL evidence, whatever its size.
    # Claiming COMPLETE requires passing `inactive_evidence` built from the
    # inactives layer, which decides completeness from both clubs having
    # published rather than from a set being non-empty.
    inev = inactive_evidence or (
        AV.InactiveEvidence.from_ids(inactive_ids, game_id=game_id,
                                     clubs=(game.away, game.home),
                                     retrieved_at=cut)
        if inactive_ids is not None
        else AV.InactiveEvidence.absent(game_id))
    have_inactives = inev.usable
    ctx = _SourceCtx.from_verified(sources, cut, inactive_evidence=inev)
    players = player_states(
        uni.value, cut=cut, game_id=game_id, ctx=ctx, registry=reg,
        role_by_id=role_by_id, dfs_position_by_id=dfs_position_by_id,
        current_season_by_id=current_season_by_id,
        historical_by_id=historical_by_id)

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
                'completeness_verdict': inev.completeness_verdict,
                'clubs_declared': list(inev.clubs_declared),
                'source': inev.source, 'retrieved_at': inev.retrieved_at,
                'content_hash': inev.content_hash,
                'why': inev.why,
                'note': 'COMPLETE establishes who is OUT. It does not '
                        'establish who is dressing, and no state here '
                        'reaches GAME_ACTIVE. ' +
                        AV.WHY_GAME_ACTIVE_IS_UNREACHABLE},
        ))

    fresh = {
        'verdict': 'DEGRADED' if degraded else 'SOURCES_PRESENT',
        'degraded_families': degraded,
        'note': ('a family unavailable at the cut is recorded, not filled '
                 'in. This verdict describes the SOURCES this builder drew; '
                 'it is not the chain-level freshness gate, which stays '
                 'where it is until its consumer is migrated.'),
        'universe_evidence_missing': bool(uni.evidence.get('evidence_missing')),
        'inactive_completeness': inev.completeness_verdict,
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


def state_from_legacy_rows(universe_rows: Sequence[dict], *,
                           role_rows: Sequence[dict] = (),
                           snap_rows: Sequence[dict] = (),
                           usage_rows=(),
                           inactive_ids=None,
                           inactive_evidence=None,
                           information_cut: str = None,
                           registry: FR.Registry = None) -> Outcome:
    """A PregameSlateState from rows a caller ALREADY built.

    THIS IS A MIGRATION SHIM AND IT SAYS SO IN ITS OWN ARTIFACT. It reads no
    vintage capture, so it can record no source hash and its freshness
    verdict is SOURCES_NOT_RECORDED. It exists so the old dossier call path
    keeps working while its callers are migrated one at a time, and so that
    there is exactly ONE implementation of a PlayerState rather than two.

    `have_inactives` follows the legacy rule -- a NON-EMPTY set means a board
    was supplied -- because reproducing that path is the whole point of this
    function. `build_one_game` uses the stricter `is not None`, and the
    difference is visible only for an empty set.
    """
    if not universe_rows:
        return Outcome.blocked(
            'UNIVERSE_EMPTY',
            'no universe rows were supplied, so there is no state to build. '
            'An empty state is not a state.', cause=Cause.DATA)
    reg = registry or FR.PREGAME
    inactive_ids = set(inactive_ids or ())
    cut = information_cut or (universe_rows[0] or {}).get('information_cut')
    game_id = (universe_rows[0] or {}).get('game_id')

    role_by_id = {r.get('gsis_id'): r for r in role_rows if r.get('gsis_id')}

    snaps: Dict[str, List[dict]] = {}
    for r in snap_rows or ():
        if r.get('pfr_player_id'):
            snaps.setdefault(r['pfr_player_id'], []).append(r)

    # The usage panel arrives keyed (week, club, player) from
    # `usage_vintage.usage_season`, or as a flat sequence. Both are accepted
    # and the player key is read under either spelling, because guessing a
    # field name is how an export once wrote 7,926 blank rows.
    seq = (list(usage_rows.values()) if isinstance(usage_rows, dict)
           else list(usage_rows or ()))
    totals: Dict[str, Dict[str, float]] = {}
    for u in seq:
        pid = u.get('gsis_id') or u.get('player_id')
        if not pid:
            continue
        t = totals.setdefault(pid, {})
        for k in ('carries', 'targets'):
            v = _f(u.get(k))
            if v is not None:
                t[k] = t.get(k, 0.0) + v

    rows, current = [], {}
    for u in universe_rows:
        pid = u.get('gsis_id') or ''
        r = dict(u)
        # The declaration set the caller handed over and the field the
        # universe builder stamped must agree; either one saying INACTIVE is
        # enough, because the failure worth preventing is a player read as
        # available when some source said he is not.
        r['officially_inactive'] = (bool(u.get('officially_inactive'))
                                    or pid in inactive_ids)
        r.setdefault('gsis_id', pid)
        rows.append(r)
        role = role_by_id.get(pid, {})
        rev = role.get('evidence') if isinstance(role.get('evidence'),
                                                 dict) else {}
        d = participation_from_snaps(snaps.get(u.get('pfr_id') or '', []))
        d.update(opportunity_from_usage(
            (rev or {}).get('current_season_usage', {}), totals.get(pid, {})))
        current[pid] = d

    inev = inactive_evidence or (
        AV.InactiveEvidence.from_ids(inactive_ids, game_id=game_id,
                                     retrieved_at=cut)
        if inactive_ids else AV.InactiveEvidence.absent(game_id))
    ctx = _SourceCtx.legacy(cut, inactive_evidence=inev)
    players = player_states(rows, cut=cut, game_id=game_id, ctx=ctx,
                            registry=reg, role_by_id=role_by_id,
                            current_season_by_id=current)
    state = PregameSlateState(
        state_version=SPEC_VERSION, slate_key=game_id or 'UNKNOWN_GAME',
        season=(universe_rows[0] or {}).get('season'),
        week=(universe_rows[0] or {}).get('week'),
        information_cut=cut, registry_identity=reg.identity(),
        registry_name=reg.name,
        source_hashes={},
        freshness={'verdict': 'SOURCES_NOT_RECORDED',
                   'degraded_families': [],
                   'inactive_completeness': inev.completeness_verdict,
                   'note': 'built from rows supplied by a caller, not from '
                           'the vintage store. No capture was selected, so '
                           'no content hash can be claimed. This is a '
                           'migration shim, not a governed state.'},
        builder_identity=f'{__name__}.state_from_legacy_rows/{SPEC_VERSION}',
        built_at=_dt.datetime.now(_dt.timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        games=[], teams=[], players=players,
        notes=['MIGRATION SHIM: no vintage capture was read and no source '
               'hash is recorded'])
    return Outcome.ok(
        'PREGAME_SLATE_STATE_FROM_LEGACY_ROWS', state,
        spec_version=SPEC_VERSION, n_players=len(players),
        registry_identity=reg.identity(),
        detail=f'{len(players)} player(s) wrapped from supplied rows; no '
               f'source hashes, verdict SOURCES_NOT_RECORDED')


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
