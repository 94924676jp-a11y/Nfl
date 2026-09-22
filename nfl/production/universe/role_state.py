"""The candidate role-state engine. A position never implies a workload again.

THE DEFECT THIS EXISTS FOR, MEASURED

Brayden VanSumeren appeared on a Kansas City board with a workload close to a
lead back's. He has 0 of 10 panel rows in the carries class, he took 4% of
Kansas City's offensive snaps in week 1 with 0 carries, and the roster lists
him at linebacker. Nothing in the pipeline objected, because the layer that
assigns opportunity reads a room and a listing and has no way to say "I do not
know what this player is". A cold start with no history defaulted him toward
the room's anchor, and an anchor is a forecast when there is nothing to shrink.

So the failure is not a bad number. It is a MISSING STATE. There was no way to
answer "unknown" and the system answered "starter" instead.

WHAT A ROLE IS HERE, AND WHAT IT IS NOT

A ROOM comes from position. A WR is in the targets room; that is what the word
means and it implies nothing about how much he plays.

A ROLE comes from MEASURED PARTICIPATION. It is how much of the offence a
player was actually on the field for, at THIS club, in weeks strictly before
the one being forecast. A depth listing is corroborating evidence and is never
on its own sufficient: a listing is a club's statement of intent, and this
project has already paid for reading intent as observation.

Therefore a player with no measured participation is ROLE_UNCERTAIN however
high he is listed. That is not a gap in the engine. It is the engine working:
a rookie, a new signing, a converted defender and a camp body are all genuinely
unknown before they play, and the honest output for all four is the same.

THE BOUNDARIES ARE ESTIMATED, NOT CHOSEN

Roles are separated by offensive snap share, and the cut points are the
midpoints between the league-wide MEAN snap share of adjacent depth ranks,
estimated from strictly earlier weeks of the same season. No number in this
file was picked to make a particular player come out a particular way; if the
league is loaded from a different week the boundaries move with it, and the
n behind every cell travels in the artifact so a thin one is visible.

If the league sample cannot be built, the engine REFUSES. There is no fallback
set of constants, because a fallback constant is how a fitted number enters a
project that forbids them.

ROLE_CONFLICT IS A BLOCKING STATE, NOT AN ANNOTATION

When two axes disagree -- listed near the front of a room with no snaps, a
roster position and a depth position in different rooms, usage in a channel
the room does not own -- the player is ROLE_UNSUPPORTED. A consumer may still
see him, count him, and put him in the universe. What it may not do is publish
him as an edge. That is the whole distinction between a system that is missing
a player and a system that is confidently wrong about one.

WHAT THIS MODULE DOES NOT DO

It assigns no workload, no target, no carry, no snap count and no fantasy
point. It reads no sportsbook price, no salary, no ownership figure and no
realised outcome for the game being forecast. It is a candidate layer: it
changes no accepted baseline and promotes nothing.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import depth_role as DR
from nfl.production.universe import support_state as S            # noqa: E402
from sportsplatform.governance.outcome import (                   # noqa: E402
    Cause, Outcome)

SPEC_VERSION = 'nfl-role-state-candidate-1'

# --- the closed set of roles ------------------------------------------------
STARTER = 'STARTER'
PRIMARY_ROTATION = 'PRIMARY_ROTATION'
SECONDARY_ROTATION = 'SECONDARY_ROTATION'
SPECIALIST = 'SPECIALIST'
BACKUP = 'BACKUP'
FULLBACK = 'FULLBACK'
GADGET = 'GADGET'
EMERGENCY = 'EMERGENCY'
ROLE_UNCERTAIN = 'ROLE_UNCERTAIN'

ROLES = (STARTER, PRIMARY_ROTATION, SECONDARY_ROTATION, SPECIALIST,
         BACKUP, FULLBACK, GADGET, EMERGENCY, ROLE_UNCERTAIN)

#: Roles that assert a player is part of the offence's regular operation. Only
#: these may carry a published edge, and only when no conflict is attached.
WORKLOAD_BEARING = (STARTER, PRIMARY_ROTATION, SECONDARY_ROTATION, FULLBACK,
                    GADGET, SPECIALIST)

ROLE_SUPPORTED = 'ROLE_SUPPORTED'
ROLE_UNSUPPORTED = 'ROLE_UNSUPPORTED'

# --- rooms ------------------------------------------------------------------
#: A room is an opportunity channel, named by the positions that compete in it.
#: This is the ONLY thing position is allowed to decide.
ROOM_DROPBACKS = 'dropbacks'
ROOM_CARRIES = 'carries'
ROOM_TARGETS = 'targets'
ROOM_KICKING = 'kicking'
ROOMS = (ROOM_DROPBACKS, ROOM_CARRIES, ROOM_TARGETS, ROOM_KICKING)

POSITION_ROOM = {
    'QB': ROOM_DROPBACKS,
    'RB': ROOM_CARRIES, 'FB': ROOM_CARRIES, 'HB': ROOM_CARRIES,
    'WR': ROOM_TARGETS, 'TE': ROOM_TARGETS,
    'K': ROOM_KICKING, 'PK': ROOM_KICKING,
}

# --- conflict codes ---------------------------------------------------------
C_DEPTH_NO_PARTICIPATION = 'DEPTH_IMPLIES_WORKLOAD_WITHOUT_PARTICIPATION'
C_POSITION_ROOM = 'POSITION_ROOM_DISAGREEMENT'
C_PARTICIPATION_NO_LISTING = 'PARTICIPATION_WITHOUT_LISTING'
C_RANK_COLLISION = 'DEPTH_RANK_COLLISION'
C_INJURY = 'INJURY_CONTRADICTS_ROLE'
C_CHANNEL = 'USAGE_CHANNEL_MISMATCH'
CONFLICTS = (C_DEPTH_NO_PARTICIPATION, C_POSITION_ROOM,
             C_PARTICIPATION_NO_LISTING, C_RANK_COLLISION, C_INJURY,
             C_CHANNEL)

#: Injury designations that contradict a front-of-room role. These are the
#: league's own published words, not a scale this file invented.
INJURY_RULES_OUT = ('Out', 'Doubtful')

#: Evidence axes the engine wants. An axis it cannot obtain is reported by
#: name as UNAVAILABLE and never silently treated as a zero.
AXES = ('depth_listing', 'current_season_snaps', 'current_season_usage',
        'roster_status', 'injury_designation', 'room_competition',
        'tenure', 'prior_season_snaps', 'transactions')

SNAP_GLOB = 'nfl/availability_raw/snap_counts_{season}.*.csv.gz'


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _i(v, default=None):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def load_snaps(season: int, before_week: int) -> Outcome:
    """League-wide offensive snap share from weeks strictly before `before_week`.

    Widest capture wins, which is the same rule `panel_2026w1` uses: several
    partial mirrors of the same file exist and the one with the most rows is
    the one that saw the most games. The week filter is what makes this
    point-in-time -- the week being forecast is never in its own evidence.
    """
    best, best_n, considered = None, -1, []
    for p in sorted(glob.glob(str(_REPO / SNAP_GLOB.format(season=season)))):
        with gzip.open(p, 'rt') as fh:
            rows = list(csv.DictReader(fh))
        considered.append({'blob': pathlib.Path(p).name, 'n_rows': len(rows)})
        if len(rows) > best_n:
            best, best_n = (p, rows), len(rows)
    if best is None:
        return Outcome.blocked(
            'ROLE_SNAPS_NO_CAPTURE',
            f'no snap-count capture for {season} exists in this checkout, so '
            f'no player has measured participation and every role would be '
            f'assigned from a listing alone. That is the defect this engine '
            f'exists to prevent, so it refuses rather than degrading.',
            cause=Cause.DATA, considered=considered)
    path, rows = best
    kept = [r for r in rows if _i(r.get('week')) is not None
            and _i(r.get('week')) < before_week
            and _i(r.get('season')) == season]
    if not kept:
        return Outcome.blocked(
            'ROLE_SNAPS_NO_PRIOR_WEEK',
            f'the widest {season} snap capture ({pathlib.Path(path).name}, '
            f'{len(rows)} rows) carries no week strictly before week '
            f'{before_week}. Week 1 has no in-season participation by '
            f'construction and this engine will not invent one.',
            cause=Cause.DATA, blob=pathlib.Path(path).name,
            considered=considered)
    return Outcome.ok(
        'ROLE_SNAPS_LOADED', value=kept,
        blob=pathlib.Path(path).name, n_rows=len(kept),
        weeks=sorted({_i(r['week']) for r in kept}),
        before_week=before_week, considered=considered,
        detail=f'{len(kept)} snap row(s) from weeks < {before_week}')


def derive_boundaries(snap_rows, depth_by_pfr) -> Outcome:
    """Role boundaries as midpoints between adjacent depth ranks' mean snap share.

    NOTHING HERE IS CHOSEN. For every player with BOTH a measured offensive
    snap share and a depth listing, league-wide, take the mean snap share at
    each listed rank. The boundary separating rank r from rank r+1 is the
    midpoint of those two means. Three boundaries separate the four measured
    role bands.

    The n behind each rank travels out with the boundaries. A rank estimated
    from a handful of players is a thin cell and the caller can see that it is
    thin; it is not silently smoothed away.
    """
    by_rank = collections.defaultdict(list)
    for r in snap_rows:
        pct = _f(r.get('offense_pct'))
        rank = depth_by_pfr.get(r.get('pfr_player_id'))
        if pct is None or rank is None:
            continue
        if POSITION_ROOM.get((r.get('position') or '').upper()) is None:
            continue
        by_rank[min(rank, 4)].append(pct)
    means = {k: statistics.fmean(v) for k, v in by_rank.items() if v}
    ns = {k: len(v) for k, v in by_rank.items()}
    need = (1, 2, 3, 4)
    missing = [r for r in need if r not in means]
    if missing:
        return Outcome.blocked(
            'ROLE_BOUNDARIES_UNDERDETERMINED',
            f'depth rank(s) {missing} have no league-wide player carrying '
            f'both a snap share and a listing, so the midpoint separating '
            f'them cannot be estimated. There is no default set of cut '
            f'points to fall back to and inventing one would be a fitted '
            f'constant.',
            cause=Cause.DATA, rank_means=means, rank_n=ns)
    b = {
        'starter_floor': (means[1] + means[2]) / 2.0,
        'primary_floor': (means[2] + means[3]) / 2.0,
        'secondary_floor': (means[3] + means[4]) / 2.0,
    }
    if not (b['starter_floor'] > b['primary_floor'] > b['secondary_floor']):
        return Outcome.blocked(
            'ROLE_BOUNDARIES_NOT_MONOTONE',
            f'the measured mean snap share is not decreasing in depth rank '
            f'({means}), so the midpoints do not order the bands. The league '
            f'sample does not support a role scale and the engine will not '
            f'impose one.',
            cause=Cause.DATA, rank_means=means, rank_n=ns, boundaries=b)
    return Outcome.ok(
        'ROLE_BOUNDARIES_DERIVED', value=b,
        rank_means=means, rank_n=ns,
        derivation=('midpoint between the league-wide mean offensive snap '
                    'share of adjacent depth ranks, from weeks strictly '
                    'before the forecast week. No cut point is chosen.'),
        detail=f'starter>={b["starter_floor"]:.4f} '
               f'primary>={b["primary_floor"]:.4f} '
               f'secondary>={b["secondary_floor"]:.4f}')


def _band(pct, b):
    if pct >= b['starter_floor']:
        return STARTER
    if pct >= b['primary_floor']:
        return PRIMARY_ROTATION
    if pct >= b['secondary_floor']:
        return SECONDARY_ROTATION
    return BACKUP


def assign(universe_rows, *, season: int, week: int, usage_rows=None,
           inactive_ids=None) -> Outcome:
    """One role row per player expected to play, with every axis it rests on.

    `usage_rows` is the measured current-season usage panel keyed
    (week, team, gsis_id). `inactive_ids` is the official declaration set when
    one exists; without it the EMERGENCY role cannot be established and is
    never assigned, rather than being guessed from an empty set.
    """
    inactive_ids = set(inactive_ids or ())
    have_inactives = bool(inactive_ids)

    snaps_o = load_snaps(season, week)
    if snaps_o.state.name != 'PASS':
        return snaps_o
    snap_rows = snaps_o.value

    # League-wide rank lookup for the boundary estimate. Built from the same
    # universe family (depth charts) but across every club present in the
    # snap file, via each player's own listing where the caller supplied it.
    depth_by_pfr = {}
    for r in universe_rows:
        if r.get('pfr_id') and _i(r.get('depth_rank')) is not None:
            depth_by_pfr[r['pfr_id']] = _i(r['depth_rank'])
    # The two clubs alone are too thin to estimate a league scale, so the
    # listing is taken from the snap file's own position ordering where the
    # universe cannot supply it: within club and position, rank by prior
    # snap share. This is a MEASURED ordering, not a listing, and it is used
    # only to place the boundary, never to assign a player's role.
    byclubpos = collections.defaultdict(list)
    for r in snap_rows:
        pos = (r.get('position') or '').upper()
        if POSITION_ROOM.get(pos) is None:
            continue
        byclubpos[(r.get('team'), pos)].append(r)
    for _k, rs in byclubpos.items():
        rs.sort(key=lambda x: -(_f(x.get('offense_pct')) or 0.0))
        for i, x in enumerate(rs, start=1):
            depth_by_pfr.setdefault(x.get('pfr_player_id'), i)

    bo = derive_boundaries(snap_rows, depth_by_pfr)
    if bo.state.name != 'PASS':
        return bo
    b = bo.value

    # Measured participation for the two clubs' players, by pfr_id.
    part = collections.defaultdict(list)
    for r in snap_rows:
        pct = _f(r.get('offense_pct'))
        if r.get('pfr_player_id') and pct is not None:
            part[r['pfr_player_id']].append(
                {'week': _i(r.get('week')), 'team': r.get('team'),
                 'offense_pct': pct,
                 'offense_snaps': _f(r.get('offense_snaps'), 0.0),
                 'position_in_snap_file': (r.get('position') or '').upper()})

    # Measured usage, aggregated over the observed weeks, per club.
    use = collections.defaultdict(lambda: collections.Counter())
    club_tot = collections.defaultdict(lambda: collections.Counter())
    team_of = {}
    for key, v in (usage_rows or {}).items():
        try:
            _w, team, pid = key
        except (TypeError, ValueError):
            continue
        if _i(_w) is not None and _i(_w) >= week:
            continue                      # never its own week or a later one
        for m in ('carries', 'targets'):
            use[pid][m] += _f(v.get(m), 0.0) or 0.0
            club_tot[team][m] += _f(v.get(m), 0.0) or 0.0
        team_of[pid] = team

    # Room competition and rank collisions, among players expected to play.
    playable = [r for r in universe_rows
                if r.get('support_state') in S.EXPECTED_TO_PLAY]
    room_members = collections.defaultdict(list)
    listing_seen = collections.defaultdict(list)
    for r in playable:
        pos = (r.get('roster_position') or '').upper()
        room = POSITION_ROOM.get(pos)
        if room:
            room_members[(r['team'], room)].append(r)
        # ONLY A SAME-ROOM RANK MAY SPEAK TO A WORKLOAD ROOM. This read the
        # raw listing, so a KR2 return ranking entered the carries room as a
        # rank-2 backfield listing. The typed accessor refuses it by name.
        dpos = (r.get('depth_pos_abb') or '').upper()
        drank = DR.offensive_depth_rank(
            r.get('roster_position'), r.get('depth_pos_abb'),
            r.get('depth_rank'))[0]
        _depth_state = DR.offensive_depth_rank(
            r.get('roster_position'), r.get('depth_pos_abb'),
            r.get('depth_rank'))[1]
        _st_role = DR.special_teams_role(r.get('depth_pos_abb'),
                                         r.get('depth_rank'))
        if dpos and drank is not None:
            listing_seen[(r['team'], dpos, drank)].append(r['gsis_id'])
    collided = {k: v for k, v in listing_seen.items() if len(v) > 1}

    out, conflict_index = [], collections.Counter()
    for r in playable:
        pos = (r.get('roster_position') or '').upper()
        dpos = (r.get('depth_pos_abb') or '').upper() or None
        drank = _i(r.get('depth_rank'))
        room = POSITION_ROOM.get(pos)
        depth_room = POSITION_ROOM.get(dpos) if dpos else None
        pid, pfr = r['gsis_id'], r.get('pfr_id')

        obs = [o for o in part.get(pfr or '~none~', [])
               if o['team'] == r['team']]
        obs_any = part.get(pfr or '~none~', [])
        n_obs = len(obs)
        snap_mean = statistics.fmean([o['offense_pct'] for o in obs]) if obs \
            else None
        snaps_total = sum(o['offense_snaps'] for o in obs)

        u = use.get(pid) or collections.Counter()
        tt = club_tot.get(r['team']) or collections.Counter()
        # A CLUB WITH NO USAGE CAPTURE IS NOT A CLUB WITH NO USAGE. Kansas
        # City's week-1 game is absent from the lawful play-by-play blob while
        # its snap counts are present, so every share below would read None
        # and a consumer could take that for zero. The state is named.
        usage_state = ('MEASURED' if tt['carries'] or tt['targets']
                       else 'CLUB_ABSENT_FROM_USAGE_CAPTURE')
        carry_share = (u['carries'] / tt['carries']) if tt['carries'] else None
        target_share = (u['targets'] / tt['targets']) if tt['targets'] else None

        n_room_active = len(room_members.get((r['team'], room), ())) if room \
            else 0

        # ---- ROLE ---------------------------------------------------------
        # The one rule everything else serves: a role that asserts workload
        # requires MEASURED participation. A listing is never enough.
        why, channel = [], None
        if room == ROOM_KICKING:
            role = SPECIALIST
            why.append('the kicking room is a specialist channel by '
                       'construction, not by measured snap share')
        elif snap_mean is None:
            role = ROLE_UNCERTAIN
            why.append(
                'no measured offensive participation at this club in any '
                'week before this one. A depth listing is a statement of '
                'intent and does not establish a role.')
        else:
            role = _band(snap_mean, b)
            why.append(f'mean offensive snap share {snap_mean:.4f} over '
                       f'{n_obs} observed game(s) against derived floors '
                       f'{b["starter_floor"]:.4f}/{b["primary_floor"]:.4f}/'
                       f'{b["secondary_floor"]:.4f}')
            # A CHANNEL IS AN ANNOTATION AND MAY NEVER PROMOTE A BAND.
            # The first draft of this file relabelled any fullback FULLBACK
            # outright, which took a player measured at 4% of his offence and
            # made him workload-bearing on the strength of his position. That
            # is precisely the rule this module exists to enforce, broken
            # inside the module enforcing it. A channel now refines a band
            # that participation has ALREADY earned, and never creates one.
            if pos == 'FB' or dpos == 'FB':
                channel = 'fullback'
            elif (room == ROOM_TARGETS and carry_share
                  and (target_share or 0.0) < carry_share):
                channel = 'gadget'
            if channel and role in (STARTER, PRIMARY_ROTATION,
                                    SECONDARY_ROTATION):
                role = FULLBACK if channel == 'fullback' else GADGET
                why.append(
                    f'{channel} channel, applied to a band participation '
                    f'already earned ({snap_mean:.4f})')
            elif channel:
                why.append(
                    f'{channel} channel noted, but the measured band is '
                    f'{role} and a channel does not promote one')
        if (role == ROLE_UNCERTAIN and have_inactives and room
                and all(m['gsis_id'] in inactive_ids
                        for m in room_members[(r['team'], room)]
                        if m['gsis_id'] != pid)):
            role = EMERGENCY
            why.append('every other player in his room is officially '
                       'inactive, established from a real declaration set')

        # ---- CONFLICTS ----------------------------------------------------
        conflicts = []
        ranks = sorted(
            v for v in (DR.offensive_depth_rank(
                m.get('roster_position'), m.get('depth_pos_abb'),
                m.get('depth_rank'))[0]
                for m in room_members.get((r['team'], room), ()))
            if v is not None) if room else []
        front = ranks[:max(1, len(ranks) // 2)] if ranks else []
        if (drank is not None and front and drank <= max(front)
                and snap_mean is None):
            conflicts.append({
                'code': C_DEPTH_NO_PARTICIPATION,
                'detail': f'listed {dpos}{drank}, in the front half of a '
                          f'{len(ranks)}-deep listed room, with zero measured '
                          f'offensive snaps at {r["team"]}'})
        if depth_room and room and depth_room != room:
            conflicts.append({
                'code': C_POSITION_ROOM,
                'detail': f'rostered {pos} (room {room}) but listed {dpos} '
                          f'(room {depth_room}); the two axes name different '
                          f'opportunity channels'})
        if drank is None and snap_mean is not None \
                and snap_mean >= b['secondary_floor']:
            conflicts.append({
                'code': C_PARTICIPATION_NO_LISTING,
                'detail': f'measured snap share {snap_mean:.4f} at or above '
                          f'the secondary-rotation floor with no depth '
                          f'listing in the selected chart'})
        if dpos and drank is not None and len(collided.get(
                (r['team'], dpos, drank), ())) > 1:
            conflicts.append({
                'code': C_RANK_COLLISION,
                'detail': f'{len(collided[(r["team"], dpos, drank)])} active '
                          f'players share the listing {dpos}{drank}'})
        if (role in (STARTER, PRIMARY_ROTATION)
                and (r.get('injury_report_status') or '') in INJURY_RULES_OUT):
            conflicts.append({
                'code': C_INJURY,
                'detail': f'role {role} from participation, against a '
                          f'published designation of '
                          f'{r["injury_report_status"]!r}'})
        if (room == ROOM_CARRIES and usage_state == 'MEASURED'
                and target_share and not carry_share):
            conflicts.append({
                'code': C_CHANNEL,
                'detail': f'measured only in the targets channel '
                          f'({target_share:.4f}) while placed in the carries '
                          f'room'})
        for c in conflicts:
            conflict_index[c['code']] += 1

        support = (ROLE_SUPPORTED
                   if role != ROLE_UNCERTAIN and not conflicts
                   else ROLE_UNSUPPORTED)
        unsupported_why = []
        if role == ROLE_UNCERTAIN:
            unsupported_why.append(
                'the role itself is unknown; no participation has been '
                'measured and nothing else may stand in for it')
        unsupported_why += [c['code'] for c in conflicts]

        out.append({
            'game_id': r.get('game_id'), 'season': season, 'week': week,
            'team': r['team'], 'gsis_id': pid,
            'display_name': r.get('display_name'),
            'support_state': r.get('support_state'),
            'room': room, 'room_from': 'roster_position',
            'channel': channel,
            'role': role, 'role_why': why,
            'role_support': support,
            'role_unsupported_why': unsupported_why,
            'conflicts': conflicts,
            'evidence': {
                'depth_listing': {'pos': dpos, 'rank': drank,
                                  'dt': r.get('depth_dt')}
                if dpos else {'state': 'ABSENT'},
                'current_season_snaps': {
                    'n_games_at_this_club': n_obs,
                    'n_games_any_club': len(obs_any),
                    'mean_offense_pct': snap_mean,
                    'total_offense_snaps': snaps_total},
                'current_season_usage': {
                    'carries': u['carries'] or 0.0,
                    'targets': u['targets'] or 0.0,
                    'carry_share': carry_share,
                    'target_share': target_share,
                    'state': usage_state,
                    'club_of_record': team_of.get(pid)},
                'roster_status': r.get('roster_status'),
                'injury_designation': {
                    'report': r.get('injury_report_status'),
                    'practice': r.get('injury_practice_status')},
                'room_competition': {'n_expected_to_play_in_room':
                                     n_room_active},
                'tenure': {'years_exp': r.get('years_exp'),
                           'rookie_year': r.get('rookie_year')},
                'prior_season_snaps': {
                    'state': 'UNAVAILABLE',
                    'why': 'no prior-season snap capture exists in this '
                           'checkout; the axis is named rather than treated '
                           'as a zero'},
                'transactions': {
                    'state': 'UNAVAILABLE',
                    'why': 'no transactions feed is reachable from here; '
                           'assigned, not blocked -- see AGENT_OUTBOX'},
            },
            'information_cut': r.get('information_cut'),
        })

    clubs = sorted({r['team'] for r in playable})
    usage_absent = sorted(c for c in clubs
                          if not (club_tot.get(c) or {}).get('carries')
                          and not (club_tot.get(c) or {}).get('targets'))
    counts = collections.Counter(x['role'] for x in out)
    sup = collections.Counter(x['role_support'] for x in out)
    return Outcome.ok(
        'ROLE_STATE_ASSIGNED', value=out,
        spec_version=SPEC_VERSION, season=season, week=week,
        n_rows=len(out), role_counts=dict(counts),
        support_counts=dict(sup),
        conflict_counts=dict(conflict_index),
        boundaries=b, boundary_evidence=bo.evidence,
        snap_evidence={k: v for k, v in snaps_o.evidence.items()
                       if k != 'value'},
        axes_unavailable=['prior_season_snaps', 'transactions'],
        clubs_absent_from_usage_capture=usage_absent,
        clubs_absent_means=("the club's week is not in the lawful "
                            'play-by-play blob. Its carry and target '
                            'shares are UNMEASURED, not zero, and no share '
                            'is imputed for it.'),
        inactives_supplied=have_inactives,
        detail=f'{len(out)} role row(s); '
               f'{sup.get(ROLE_UNSUPPORTED, 0)} unsupported; '
               f'{sum(conflict_index.values())} conflict(s)')


def downstream_population(universe_rows) -> set:
    """Whom the football model would otherwise give meaningful opportunity to.

    DEFINED WITHOUT REFERENCE TO ROLE, AND THAT IS THE WHOLE POINT. The gate
    below previously took its population from players who were already
    ROLE_SUPPORTED and in a workload-bearing role, then asked whether that
    population was role-supported. It was, necessarily: the answer had been
    used to build the question, and every problematic player had been removed
    from the denominator before the test ran.

    The population is therefore read from the PLAYER UNIVERSE: every player
    the universe expects to play, at a position that competes for offensive
    opportunity. A role-unsupported player cannot leave this set, because
    nothing about his role was consulted to put him in it.
    """
    out = set()
    for r in universe_rows or ():
        if r.get('support_state') not in S.EXPECTED_TO_PLAY:
            continue
        pos = (r.get('roster_position') or '').upper()
        room = POSITION_ROOM.get(pos)
        if room in (ROOM_DROPBACKS, ROOM_CARRIES, ROOM_TARGETS):
            out.add(r['gsis_id'])
    return out


def assert_role_state_supported(role_rows, *, publishable_ids=None,
                                universe_rows=None) -> Outcome:
    """The blocking gate. A ROLE_UNSUPPORTED player may not carry an edge.

    THE POPULATION IS NOT THE CALLER'S TO NARROW. When `universe_rows` is
    given, the set under test is `downstream_population(universe_rows)` --
    everyone the universe expects to play in an opportunity room -- and any
    `publishable_ids` the caller also passes is folded IN rather than used
    instead. A caller cannot shrink the denominator to the players it already
    knows are fine.

    Passing neither leaves nothing to test against, and the gate BLOCKS:
    certifying a board nobody described is the same green-with-nothing-
    underneath failure the coverage gate was corrected for.
    """
    if universe_rows is not None:
        pop = downstream_population(universe_rows)
        publishable_ids = (pop | set(publishable_ids or ())
                           if publishable_ids is not None else pop)
        population_source = 'player_universe.EXPECTED_TO_PLAY_in_a_room'
    else:
        population_source = 'caller_supplied_only'
    unsupported = [r for r in role_rows
                   if r.get('role_support') == ROLE_UNSUPPORTED]
    idx = {r['gsis_id']: r for r in unsupported}
    if publishable_ids is None:
        return Outcome.blocked(
            'NO_PUBLISHABLE_SET_DECLARED',
            f'{len(role_rows)} role row(s) were assigned and '
            f'{len(unsupported)} are unsupported, but neither a player '
            f'universe nor a publishable set was supplied, so there is no '
            f'population to test. A PASS here would certify an unexamined '
            f'board.',
            cause=Cause.GOVERNANCE, n_rows=len(role_rows),
            population_source=population_source,
            n_unsupported=len(unsupported),
            unsupported=[{'gsis_id': r['gsis_id'],
                          'display_name': r.get('display_name'),
                          'team': r['team'], 'role': r['role'],
                          'why': r['role_unsupported_why']}
                         for r in unsupported])
    offenders = [idx[p] for p in sorted(set(publishable_ids)) if p in idx]
    if offenders:
        return Outcome.fail(
            'ROLE_UNSUPPORTED_PLAYER_IN_PUBLISHABLE_SET',
            f'{len(offenders)} player(s) whose role is not established would '
            f'be published as an edge. A player the model cannot place is a '
            f'player the model cannot price, and publishing him anyway is how '
            f'a linebacker acquired a lead back\'s workload.',
            cause=Cause.DATA,
            offending=[{'gsis_id': r['gsis_id'],
                        'display_name': r.get('display_name'),
                        'team': r['team'], 'room': r['room'],
                        'role': r['role'],
                        'why': r['role_unsupported_why'],
                        'conflicts': [c['code'] for c in r['conflicts']]}
                       for r in offenders],
            n_publishable=len(set(publishable_ids)),
            n_in_population=len(set(publishable_ids)),
            population_source=population_source,
            n_unsupported=len(unsupported))
    return Outcome.ok(
        'ROLE_STATE_SUPPORTED_FOR_PUBLISHABLE_SET',
        value={'n_publishable': len(set(publishable_ids)),
               'n_unsupported_withheld': len(unsupported),
               'population_source': population_source},
        certified=True, population_source=population_source,
        withheld=[{'gsis_id': r['gsis_id'],
                   'display_name': r.get('display_name'),
                   'team': r['team'], 'role': r['role'],
                   'why': r['role_unsupported_why']} for r in unsupported],
        detail=f'{len(set(publishable_ids))} publishable player(s), none of '
               f'them role-unsupported; {len(unsupported)} withheld')
