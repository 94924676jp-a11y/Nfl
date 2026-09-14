"""QB room V2: starter scenario, starter-CONDITIONED share, separate exit hazard.

WHAT WAS WRONG WITH V1, IN ONE SENTENCE

`qb3_lib.allocate` draws the primary passer's IDENTITY and then resamples that
player's share from his cell's UNCONDITIONAL pool -- a pool built over every
depth-charted quarterback in the cell, including the ones who never took a
dropback. The model's own frame says `P(share = 0 | is the primary) = 0.0000`
in all five cells, so the zero was being counted twice: once in the categorical
draw of who, and again inside the pool the winner then resampled from. For the
(rank 1, not previous primary) cell the pool is 47.35% exactly zero, and
0.8357 x 0.4735 = 0.3957 is most of the 0.412 that reached the sealed DEN@KC
board for Patrick Mahomes. Measured in `nfl/research/v2/d5/D5_ZERO_MASS_AUDIT.md`.

WHAT THIS MODULE DOES INSTEAD

    legal QB room
      -> pregame starter-scenario probability          P(this man takes DB #1)
      -> starter-CONDITIONED share distribution        never the unconditional pool
      -> separate exit/replacement hazard              pooled, empirical
      -> integer assignment of team dropbacks
      -> sack / scramble / attempt branch, then completions and yards

THE STRUCTURAL PROPERTY THE REPAIR RESTS ON, STATED SO IT CAN BE CHECKED

The starter is DEFINED as the quarterback who takes his team's first dropback.
A team with N >= 1 dropbacks therefore has a starter holding at least one of
them, so `P(dropbacks = 0 | started) = 0` is an identity of the definition and
not a floor, a clip or a minimum. Nothing in this file sets a probability by
hand. The same identity bounds the replacement: at most N - 1 dropbacks can
follow the starter's first, which is arithmetic, not a tuned cap.

A player's zero mass is now exactly

    P(dropbacks = 0) = P(not the starter) x P(never relieves | not the starter)

and both factors are estimated from the record.

NO FITTED CONSTANTS. Every quantity is an empirical rate or a resampled pool:
cell starter rates, the pooled exit hazard, the post-exit fraction pool, the
reliever-by-rank weights, and a two-stage donor-game resample for the per-
dropback branch. There is no coefficient to tune and no threshold to loosen.

DATA VINTAGE IS RECORDED PER COMPONENT, NOT ONCE FOR THE MODULE, because the
components do not all rest on the same seasons. See `fit()`'s returned
`vintage` block.
"""
from __future__ import annotations

import bisect
import collections
import csv
import glob
import gzip
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'qb-room-v2-starter-scenario-1'
GOVERNANCE = ('CANDIDATE -- successor lineage to QB3, which stays frozen and '
              'unamended. Not promoted, no prospective evidence.')

PBP_DIR = _REPO / 'nfl' / 'research' / 'postgame'
DC_WEEKLY = str(_REPO / 'nfl' / 'research' / 'inputs' / 'dc_%d.csv.gz')
DC_DAILY = _REPO / 'nfl' / 'research' / 'inputs' / 'dc25_daily.csv.gz'
PANEL = _REPO / 'nfl' / 'research' / 'inputs' / 'panel_p3.csv.gz'

# Seasons whose play-by-play is lawful historical support. 2026 is the season
# being forecast and is excluded here by construction rather than by a caller
# remembering to exclude it.
FORBIDDEN_PBP_SEASONS = frozenset({2026})

KINDS = ('sack', 'scramble', 'attempt')


class QbRoomV2Error(RuntimeError):
    """Named failure. An empty read is an error, never an empty result."""


# --------------------------------------------------------------- pbp intake
def pbp_path(season: int) -> str:
    if season in FORBIDDEN_PBP_SEASONS:
        raise QbRoomV2Error(
            f'PBP_SEASON_FORBIDDEN: {season} is the forecast season and may '
            f'not enter a historical frame.')
    fs = sorted(glob.glob(str(PBP_DIR / f'pbp_{season}.*.csv.gz')))
    fs = [f for f in fs if not f.endswith('.provenance.json')]
    if not fs:
        raise QbRoomV2Error(
            f'PBP_SEASON_ABSENT: no pbp_{season}.*.csv.gz in {PBP_DIR}. '
            f'Absent data is a blocked input, not an empty season.')
    if len(fs) > 1:
        raise QbRoomV2Error(
            f'PBP_SEASON_AMBIGUOUS: {len(fs)} blobs for {season}: '
            f'{[os.path.basename(f) for f in fs]}. Refusing to pick one.')
    return fs[0]


def load_pbp(seasons) -> dict:
    """(game_id, posteam) -> the team's ordered dropback sequence.

    A dropback is `qb_dropback == '1'` and decomposes EXACTLY into
    sack + scramble + board attempt. Measured on 2024 REG: 1,314 + 1,062 +
    17,839 = 20,215 = every dropback, no remainder. The board's attempt is
    `pass_attempt & !sack & !qb_spike`; nflverse's `pass_attempt` includes
    sacks, and spikes are not dropbacks at all.

    The dropback's owner is `passer_player_id`, except on a scramble where
    nflverse leaves the passer empty and the quarterback is the rusher.
    """
    out = {}
    for y in sorted(set(int(s) for s in seasons)):
        p = pbp_path(y)
        n_rows = n_db = 0
        for r in csv.DictReader(gzip.open(p, 'rt')):
            n_rows += 1
            if r.get('season_type') != 'REG':
                continue
            if r.get('qb_dropback') != '1':
                continue
            team = r.get('posteam') or ''
            gid = r.get('game_id') or ''
            if not team or not gid:
                continue
            if r.get('sack') == '1':
                kind, pid = 'sack', r.get('passer_player_id') or ''
            elif r.get('qb_scramble') == '1':
                kind, pid = 'scramble', r.get('rusher_player_id') or ''
            else:
                kind, pid = 'attempt', r.get('passer_player_id') or ''
            if not pid:
                continue
            comp = int(r.get('complete_pass') == '1')
            try:
                yds = int(float(r.get('passing_yards') or 0))
            except (TypeError, ValueError):
                yds = 0
            k = (gid, team)
            g = out.get(k)
            if g is None:
                g = out[k] = {'game_id': gid, 'team': team,
                              'season': int(r['season']), 'week': int(r['week']),
                              'date': r.get('game_date') or '', 'db': []}
            g['db'].append((pid, kind, comp, yds if kind == 'attempt' else 0))
            n_db += 1
        if n_db == 0:
            raise QbRoomV2Error(
                f'PBP_SEASON_EMPTY: {os.path.basename(p)} yielded 0 REG '
                f'dropbacks from {n_rows} rows. A zero is an error here.')
    if not out:
        raise QbRoomV2Error('PBP_EMPTY: no team-game carried a dropback.')
    return out


# ------------------------------------------------------------- depth charts
def load_depth_weekly(seasons) -> dict:
    """(season, week, team) -> {gsis_id: best QB rank}. nflverse weekly vendor."""
    out = collections.defaultdict(dict)
    for y in sorted(set(int(s) for s in seasons)):
        p = DC_WEEKLY % y
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(gzip.open(p, 'rt')):
            if r.get('game_type') != 'REG':
                continue
            if (r.get('depth_position') or r.get('position') or '').upper() != 'QB':
                continue
            if not r.get('gsis_id'):
                continue
            try:
                d = int(r['depth_team'])
            except (ValueError, TypeError, KeyError):
                continue
            k = (int(r['season']), int(r['week']),
                 r.get('club_code') or r.get('team'))
            if out[k].get(r['gsis_id'], 99) > d:
                out[k][r['gsis_id']] = d
    if not out:
        raise QbRoomV2Error('DEPTH_WEEKLY_EMPTY: no QB depth row was read.')
    return dict(out)


def load_depth_daily_asof(dates_by_team_game) -> dict:
    """The DAILY vendor, read as of a date STRICTLY BEFORE each game.

    This is the vendor that serves 2026, so a fold built on it is vendor
    matched to serve time. `dates_by_team_game` is {(game_id, team): 'YYYY-MM-DD'}
    and the capture used for a game is the newest whose timestamp is strictly
    earlier than that date -- chronology enforced by `bisect`, not by trust.
    """
    if not DC_DAILY.exists():
        raise QbRoomV2Error(f'DEPTH_DAILY_ABSENT: {DC_DAILY}')
    caps = collections.defaultdict(lambda: collections.defaultdict(dict))
    dts = set()
    for r in csv.DictReader(gzip.open(str(DC_DAILY), 'rt')):
        if (r.get('pos_abb') or '').upper() != 'QB' or not r.get('gsis_id'):
            continue
        try:
            rank = int(r['pos_rank'])
        except (ValueError, TypeError, KeyError):
            continue
        dt = r['dt']
        dts.add(dt)
        cur = caps[dt][r['team']].get(r['gsis_id'])
        if cur is None or rank < cur:
            caps[dt][r['team']][r['gsis_id']] = rank
    if not caps:
        raise QbRoomV2Error('DEPTH_DAILY_EMPTY: no QB row in the daily vendor.')
    order = sorted(dts)
    out = {}
    for key, date in dates_by_team_game.items():
        if not date:
            continue
        i = bisect.bisect_left(order, date)      # STRICTLY earlier
        if i <= 0:
            continue
        room = caps[order[i - 1]].get(key[1])
        if room:
            out[key] = dict(room)
    return out


# -------------------------------------------------- previous primary passer
def previous_primary_from_panel() -> dict:
    """team -> sorted ordinals, and (team, ordinal) -> previous primary pid.

    THE FEATURE IS TAKEN FROM PRODUCTION UNCHANGED, DELIBERATELY. V1 reads the
    previous primary from `panel_p3.dropbacks_as_passer`, a column that EQUALS
    `pass_att_as_passer` in all 57,670 rows and is therefore an attempt count,
    not a dropback count. Rebuilding the feature on true dropbacks would have
    changed the treatment and the comparison in one step. It is kept identical
    so that the only thing that differs between V1 and V2 is the allocator, and
    the disagreement rate between the two definitions is measured and reported
    rather than assumed away.
    """
    if not PANEL.exists():
        raise QbRoomV2Error(f'PANEL_ABSENT: {PANEL}')
    tg = collections.defaultdict(list)
    for r in csv.DictReader(gzip.open(str(PANEL), 'rt')):
        if r['position'] != 'QB':
            continue
        o = int(r['season']) * 100 + int(r['week'])
        try:
            db = int(float(r.get('dropbacks_as_passer') or 0))
        except (TypeError, ValueError):
            db = 0
        tg[(r['team'], o)].append((r['gsis_id'], db))
    if not tg:
        raise QbRoomV2Error('PANEL_NO_QB_ROWS')
    prim, ords = {}, collections.defaultdict(list)
    for (t, o), v in tg.items():
        a = sorted([x for x in v if x[1] >= 1], key=lambda x: -x[1])
        prim[(t, o)] = a[0][0] if a else None
        ords[t].append(o)
    for t in ords:
        ords[t].sort()
    return {'primary': prim, 'ordinals': dict(ords)}


def prev_primary_at(pp, team, ordinal):
    """The primary of this club's last game STRICTLY before `ordinal`."""
    oo = pp['ordinals'].get(team)
    if not oo:
        return None, None
    i = bisect.bisect_left(oo, ordinal)
    if i <= 0:
        return None, None
    po = oo[i - 1]
    return pp['primary'].get((team, po)), po


# --------------------------------------------------------------- the frame
def rank_bucket(rank) -> int:
    r = int(rank)
    return 1 if r == 1 else (2 if r == 2 else 3)


def build_frame(team_games, depth_by_key, pp) -> list:
    """One row per (team-game, depth-charted quarterback), with the realised
    STARTER and FINISHER of that team-game attached.

    The room comes from the depth chart and not from the men who played. A
    frame built on the played rows conditions on having played, which is the
    defect this file exists to remove -- it must not be reintroduced here.
    """
    rows = []
    for key, g in team_games.items():
        room = depth_by_key.get(key)
        if not room:
            continue
        seq = g['db']
        if not seq:
            continue
        o = g['season'] * 100 + g['week']
        prev, prev_ord = prev_primary_at(pp, g['team'], o)
        opener = (prev_ord is not None and (prev_ord // 100) != g['season'])
        counts = collections.Counter(x[0] for x in seq)
        starter, finisher = seq[0][0], seq[-1][0]
        n = len(seq)
        n_post = 0
        for i in range(n - 1, -1, -1):
            if seq[i][0] == starter:
                break
            n_post += 1
        for pid, rank in room.items():
            rows.append({
                'game_id': g['game_id'], 'team': g['team'],
                'season': g['season'], 'week': g['week'], 'ord': o,
                'date': g['date'], 'pid': pid,
                'rank': rank_bucket(rank),
                'was_prev_primary': int(prev is not None and pid == prev),
                'is_opener': int(bool(opener)),
                'prev_primary_known': int(prev is not None),
                'n_db_team': n, 'db': int(counts.get(pid, 0)),
                'is_starter': int(pid == starter),
                'is_finisher': int(pid == finisher),
                'starter_in_room': int(starter in room),
                'n_db_after_starter_last': n_post,
            })
    if not rows:
        raise QbRoomV2Error('FRAME_EMPTY: no charted quarterback joined a '
                            'team-game. An empty frame is an error.')
    return rows


# ------------------------------------------------------------------- fit
def starter_cell(rank, was_prev, is_opener, use_opener=True):
    """The declared cell for the STARTER-SCENARIO probability.

    `is_opener` is in the cell because it is a mixture indicator, not a
    calendar effect, and D5 measured the mixture: the same (rank 1, not the
    previous primary) cell means "an injured or benched starter is still listed
    first" in weeks 2-18, where the realised zero-dropback rate is 0.7174, and
    "a club changed starters over the offseason, or rested week 18" at a season
    boundary, where it is 0.0000 in 128 tries. Pooling them estimates neither.
    It is a pregame-observable feature that production already computes and
    already flags (`qb_allocation.qb3_configuration.week1_specification_defect`
    / `QB3_WEEK1_SEASON_BOUNDARY`); nothing about it is fitted.
    """
    if use_opener:
        return (rank_bucket(rank), int(bool(was_prev)), int(bool(is_opener)))
    return (rank_bucket(rank), int(bool(was_prev)))


def fit(frame, team_games, eval_ordinal, use_opener=True,
        prior='jeffreys') -> dict:
    """Every rate from team-games STRICTLY EARLIER than `eval_ordinal`.

    Returns empirical pools only. There is no coefficient in the return value.
    """
    cut = int(eval_ordinal)
    start_n = collections.defaultdict(lambda: [0, 0])
    used_games = set()
    for r in frame:
        if r['ord'] >= cut:
            continue
        c = starter_cell(r['rank'], r['was_prev_primary'], r['is_opener'],
                         use_opener)
        start_n[c][0] += 1
        start_n[c][1] += r['is_starter']
        used_games.add((r['game_id'], r['team']))

    # RELIEVER IDENTITY BY DEPTH RANK, among the non-starters of a team-game in
    # which somebody relieved. Pooled over openers and in-season alike: the
    # quantity is "given the role changed hands, who took it", and nothing
    # measured says that differs by season boundary.
    rel_n = collections.defaultdict(lambda: [0, 0])
    by_tg = collections.defaultdict(list)
    for r in frame:
        if r['ord'] < cut:
            by_tg[(r['game_id'], r['team'])].append(r)
    for key, rs in by_tg.items():
        st = [x for x in rs if x['is_starter']]
        if not st:
            continue
        others = [x for x in rs if not x['is_starter']]
        if not others or sum(x['db'] for x in others) == 0:
            continue
        top = max(others, key=lambda x: x['db'])
        for x in others:
            rel_n[rank_bucket(x['rank'])][0] += 1
            rel_n[rank_bucket(x['rank'])][1] += int(x is top)

    # THE EXIT / REPLACEMENT HAZARD. Pooled and empirical, and it needs NO
    # depth chart, so it is fitted on every team-game of play-by-play in the
    # window rather than only on the charted subset.
    n_tg = n_exit = 0
    post_pool, cameo_pool, n_rel_pool = [], [], []
    for key, g in team_games.items():
        o = g['season'] * 100 + g['week']
        if o >= cut:
            continue
        seq = g['db']
        if not seq:
            continue
        n = len(seq)
        starter = seq[0][0]
        n_tg += 1
        n_post = 0
        for i in range(n - 1, -1, -1):
            if seq[i][0] == starter:
                break
            n_post += 1
        n_other = sum(1 for x in seq if x[0] != starter)
        if n_post > 0:                              # the starter did not finish
            n_exit += 1
            post_pool.append(n_other / n)
            n_rel_pool.append(len({x[0] for x in seq if x[0] != starter}))
        else:
            cameo_pool.append(n_other / n)

    if n_tg == 0 or not start_n:
        raise QbRoomV2Error(
            f'FIT_EMPTY: nothing earlier than ordinal {cut}. An empty fit is '
            f'not a fit.')

    # THE PER-DROPBACK BRANCH, as a two-stage donor resample. Stage one picks a
    # historical GAME of this quarterback with probability proportional to its
    # dropbacks; stage two draws this draw's dropbacks with replacement from
    # that game's own outcomes. Game-level correlation survives stage one and
    # nothing is fitted in either stage.
    donors = collections.defaultdict(list)
    for key, g in team_games.items():
        o = g['season'] * 100 + g['week']
        if o >= cut:
            continue
        by_pid = collections.defaultdict(list)
        for pid, kind, comp, yds in g['db']:
            by_pid[pid].append((KINDS.index(kind), comp, yds))
        for pid, outs in by_pid.items():
            donors[pid].append(outs)
    league_donor = [o for v in donors.values() for o in v]
    if not league_donor:
        raise QbRoomV2Error('DONOR_POOL_EMPTY')

    # THE PRIOR, AND WHY THERE IS ONE AT ALL.
    #
    # Three opener cells are 0 of n and two are n of n. A raw rate of exactly
    # 0.0000 asserts that a quarterback CANNOT start, and a raw 1.0000 asserts
    # that another cannot fail to; neither is supported by 63 or 90
    # observations, and 'zeros are errors, not results' is a rule of this
    # project. Jeffreys' Beta(1/2, 1/2) is the standard non-informative prior
    # for a binomial proportion -- a DOCUMENTED PRIOR, which is one of the four
    # admissible provenances for a number here, not a fitted constant and not a
    # tuned floor. It is reported alongside the raw empirical rates and the
    # repair does not depend on it: the starter's zero-dropback mass is zero by
    # the definition of starting under either.
    if prior not in ('jeffreys', 'none'):
        raise QbRoomV2Error(f'PRIOR_UNKNOWN: {prior!r}')
    a = 0.5 if prior == 'jeffreys' else 0.0
    p_start = {k: ((v[1] + a) / (v[0] + 2 * a)) for k, v in start_n.items()}
    return {
        'spec_version': SPEC_VERSION,
        'trained_on_ordinals_before': cut,
        'use_opener': bool(use_opener),
        'prior': prior,
        'p_start': p_start,
        'p_start_raw': {k: (v[1] / v[0]) for k, v in start_n.items()},
        'n_start': {k: v[0] for k, v in start_n.items()},
        'k_start': {k: v[1] for k, v in start_n.items()},
        'p_reliever_by_rank': {k: (v[1] / v[0]) for k, v in rel_n.items()},
        'n_reliever_by_rank': {k: v[0] for k, v in rel_n.items()},
        'p_exit': n_exit / n_tg,
        'n_team_games': n_tg,
        'n_exit': n_exit,
        'post_pool': np.asarray(post_pool, float),
        'cameo_pool': np.asarray(cameo_pool, float),
        'n_relievers_pool': np.asarray(n_rel_pool, int),
        'donors': donors,
        'league_donor': league_donor,
        'n_charted_team_games': len(used_games),
    }


# ------------------------------------------------------------- cached fit
_FIT = {}
HISTORICAL_SEASONS = (2021, 2022, 2023, 2024, 2025)


def cache_clear():
    _FIT.clear()


def fit_for_ordinal(ordinal, seasons=HISTORICAL_SEASONS, use_opener=True,
                    prior='jeffreys'):
    """The fit for a forecast ordinal, built once per process.

    VINTAGE IS NOT UNIFORM ACROSS THIS OBJECT AND THE RETURN SAYS SO. The
    starter cells need a depth chart, and the committed weekly depth leaves
    stop at 2024 while 2025 is covered only by the DAILY vendor -- which is the
    vendor that serves 2026, so the 2025 fold is vendor-matched to serve time
    and the 2021-2024 folds are not. The exit hazard, the post-exit pool and
    the per-dropback donor pools need no depth chart at all and are fitted on
    every season of play-by-play in the window.
    """
    key = (int(ordinal), tuple(seasons), bool(use_opener), prior)
    if key in _FIT:
        return _FIT[key]
    tg = load_pbp(seasons)
    pp = previous_primary_from_panel()
    weekly = [y for y in seasons if os.path.exists(DC_WEEKLY % y)]
    dw = load_depth_weekly(weekly) if weekly else {}
    depth = {}
    for k, g in tg.items():
        r = dw.get((g['season'], g['week'], g['team']))
        if r:
            depth[k] = r
    dates = {k: g['date'] for k, g in tg.items() if k not in depth}
    if dates:
        for k, v in load_depth_daily_asof(dates).items():
            depth.setdefault(k, v)
    if not depth:
        raise QbRoomV2Error('DEPTH_JOIN_EMPTY: no team-game carried a QB depth '
                            'chart. An empty join is an error.')
    frame = build_frame(tg, depth, pp)
    par = fit(frame, tg, ordinal, use_opener=use_opener, prior=prior)
    par['vintage'] = {
        'pbp_seasons': list(seasons),
        'depth_weekly_seasons': weekly,
        'depth_daily_used_for_team_games': sum(
            1 for k in depth if k not in {kk for kk in depth
                                          if dw.get((tg[kk]['season'],
                                                     tg[kk]['week'],
                                                     tg[kk]['team']))}),
        'n_charted_team_games': len(depth),
        'previous_primary_feature': 'panel_p3 (attempt-based), as production',
    }
    _FIT[key] = par
    return par


# --------------------------------------------------- stage 0: the legal room
#
# DETERMINISTIC ELIGIBILITY SITS ABOVE THE STARTER SCENARIO, NOT INSIDE IT.
#
# The structure this module implements starts at "legal QB room", and the word
# legal is doing work. If a quarterback an authority has declared cannot play
# is still in the room, he draws starter mass, and the exit/replacement
# mechanism is then asked to explain participation that was never possible --
# a determination laundered into a probability.
#
# The hole R2 found is exactly that shape and it is NOT the one already
# repaired. The pool filter at `run_forecast.py:439` reads ROSTER STATUS
# (ACT/RES/DEV/CUT/EXE) and nothing else, so it removes a quarterback on
# reserve and keeps a quarterback listed `Out` on the injury report, whose
# roster status is `ACT`. R2's phrasing: it "would have kept Tua".
#
# AND A LEARNED FEATURE IS NOT A GATE. `appearance_r8.predict` does take
# `injuries_rows` and `Out` does reach it as a one-hot, but as a soft feature:
# a governing-inactive player (Jack Endries, TB@CIN) carried p_app = 0.9920
# through it. This room must not read that as enforcement, and does not.
#
# So the gate is CONSUMED, not rebuilt: `eligibility_gate.snapshot()` ->
# `choice_set()`, which resolves determination, authority rank, source vintage,
# content hash and a publication-clock `known_from`. Removal happens in the
# choice set, so a removed quarterback has no row in the allocation at all and
# there is no mass to renormalise away afterwards.


def legal_room(season, week, team, qb_players, *, kickoff_utc,
               emergency_qb_ids=(), **gate_kwargs) -> Outcome:
    """The room the starter scenario is allowed to see, and why.

    THE EMERGENCY THIRD QUARTERBACK IS THE ONE RE-ADMISSION, AND IT IS A RULE,
    NOT A JUDGEMENT. A designated emergency third quarterback appears on the
    inactive list and may nonetheless enter the game, so removing him outright
    would make an event the rulebook permits impossible. He is re-admitted with
    `can_start = False`: the rule admits him to the game, not to the opening
    snap. Every re-admission is named on the Outcome. An id is only re-admitted
    if a CALLER supplies it from a source that carries the designation -- this
    function never infers the designation from a depth rank.
    """
    from nfl.production import eligibility_gate as EG
    snap = EG.snapshot(season, week, [team], qb_players,
                       kickoff_utc=kickoff_utc, **gate_kwargs)
    if snap.state is not State.PASS:
        return snap
    cs = EG.choice_set(qb_players, snap)
    if cs.state is not State.PASS:
        return cs
    kept = {q['gsis_id'] for q in cs.value}
    emergency = [q for q in qb_players
                 if q.get('gsis_id') in set(emergency_qb_ids)
                 and q.get('gsis_id') not in kept]
    room = [dict(q, can_start=True, emergency=False) for q in cs.value]
    room += [dict(q, can_start=False, emergency=True) for q in emergency]
    if not room:
        return Outcome.fail(
            'LEGAL_QB_ROOM_EMPTY',
            f'{team}: every quarterback is determined ineligible, so there is '
            f'nobody to hold the team dropback. Refusing rather than leaving '
            f'the share with a man who cannot play.')
    return Outcome.ok(
        'LEGAL_QB_ROOM_OK', value=room, spec_version=SPEC_VERSION, team=team,
        n_in=len(qb_players), n_kept=len(room),
        n_removed_determined_ineligible=cs.evidence[
            'n_removed_determined_ineligible'],
        n_removed_by_pool_rule=cs.evidence['n_removed_by_pool_rule'],
        removed_determined_ineligible=cs.evidence[
            'removed_determined_ineligible'],
        n_emergency_readmitted=len(emergency),
        emergency_readmitted=[q.get('gsis_id') for q in emergency],
        gate_spec_version=cs.evidence.get('spec_version'),
        enforcement=('CHOICE_SET_CONSTRUCTION, consumed from '
                     'nfl.production.eligibility_gate -- not rebuilt here'),
        a_learned_feature_is_not_a_gate=(
            'appearance_r8 takes Out as a soft one-hot and has carried '
            'p_app = 0.9920 for a governing-inactive player. Nothing in this '
            'room reads a learned probability as a determination.'))


# --------------------------------------------------------------- allocation
def _rng(seed, ordinal, team, salt=0):
    return np.random.default_rng(
        [int(seed), int(ordinal),
         int.from_bytes(str(team).encode()[-8:].ljust(8, b'0'), 'little'),
         int(salt)])


def allocate_dropbacks(par, room, team_db_draws, seed=20260908, ordinal=0,
                       team='', is_opener=False) -> dict:
    """Integer dropback counts per quarterback, one column per draw.

    `room` is a list of dicts: {'pid', 'rank', 'was_prev_primary',
    'can_start' (default True), 'emergency' (default False)}.

    THE EMERGENCY THIRD QUARTERBACK IS IN THE ROOM AND CANNOT START. The rule
    admits him to the game; it does not admit him to the opening snap. He is
    therefore given zero starter weight and full reliever weight, which is what
    the rule says, rather than being deleted from the room (which would make
    him impossible) or treated as an ordinary QB3 (which would make him a
    candidate to start).
    """
    n = len(room)
    if n == 0:
        raise QbRoomV2Error('ROOM_EMPTY: a room with no quarterback is not a '
                            'room.')
    V = np.rint(np.asarray(team_db_draws, float)).astype(np.int64)
    if V.min() < 0:
        raise QbRoomV2Error('TEAM_DROPBACKS_NEGATIVE')
    m = V.shape[0]
    rng = _rng(seed, ordinal, team, 0)

    cells = [starter_cell(r['rank'], r.get('was_prev_primary', 0), is_opener,
                          par['use_opener']) for r in room]
    w = np.array([0.0 if r.get('emergency') or not r.get('can_start', True)
                  else par['p_start'].get(c, 0.0)
                  for r, c in zip(room, cells)], float)
    if w.sum() <= 0:
        raise QbRoomV2Error(
            'STARTER_WEIGHTS_EMPTY: no quarterback in this room carries any '
            'starter propensity, so the starting scenario is undefined. '
            'Refusing rather than inventing one.')
    p_start = w / w.sum()
    who = rng.choice(n, size=m, p=p_start)

    # reliever weights: by depth rank, zeroed for whoever started in that draw
    rw = np.array([max(par['p_reliever_by_rank'].get(rank_bucket(r['rank']),
                                                     0.0), 0.0)
                   for r in room], float)
    if rw.sum() <= 0:
        rw = np.ones(n, float)

    exit_u = rng.random(m)
    exits = exit_u < par['p_exit']
    post_f = np.where(
        exits,
        par['post_pool'][rng.integers(0, len(par['post_pool']), m)]
        if len(par['post_pool']) else 0.0,
        par['cameo_pool'][rng.integers(0, len(par['cameo_pool']), m)]
        if len(par['cameo_pool']) else 0.0)

    DB = np.zeros((n, m), np.int64)
    # THE TWO BOUNDS BELOW ARE THE DEFINITION, NOT A CLIP. The starter took
    # dropback #1, so at most N-1 can follow him; and if the role changed hands
    # at all then at least one did.
    post = np.rint(post_f * V).astype(np.int64)
    post = np.minimum(post, np.maximum(V - 1, 0))
    post = np.maximum(post, np.where(exits & (V >= 2), 1, 0))
    post = np.where(V <= 0, 0, post)
    starter_db = V - post

    for i in range(n):
        sel = who == i
        DB[i, sel] += starter_db[sel]

    live = np.where(post > 0)[0]
    if len(live):
        n_rel = (par['n_relievers_pool'][
            rng.integers(0, len(par['n_relievers_pool']), len(live))]
            if len(par['n_relievers_pool']) else np.ones(len(live), int))
        for idx, j in enumerate(live):
            cand = [i for i in range(n) if i != who[j]]
            if not cand:
                DB[who[j], j] += post[j]
                continue
            ww = np.array([rw[i] for i in cand], float)
            if ww.sum() <= 0:
                ww = np.ones(len(cand), float)
            ww = ww / ww.sum()
            k = int(min(max(n_rel[idx], 1), len(cand), post[j]))
            pick = rng.choice(len(cand), size=k, replace=False, p=ww) if k > 1 \
                else np.array([rng.choice(len(cand), p=ww)])
            # integer split of `post` among the picked relievers, largest
            # remainder on a resampled simplex -- counts are generated inside
            # the draw and never rounded from a mean.
            if k == 1:
                DB[cand[pick[0]], j] += post[j]
            else:
                pw = ww[pick] / ww[pick].sum()
                raw = pw * post[j]
                base = np.floor(raw).astype(np.int64)
                rem = post[j] - base.sum()
                if rem > 0:
                    order = np.argsort(-(raw - base))
                    base[order[:rem]] += 1
                for a, b in zip(pick, base):
                    DB[cand[a], j] += int(b)

    dev = int(np.abs(DB.sum(0) - V).max())
    if dev != 0:
        raise QbRoomV2Error(
            f'ALLOCATION_DOES_NOT_CLOSE: worst integer deviation {dev}. '
            f'Closure is the property this layer exists for.')
    return {'db': DB, 'starter_index': who, 'exited': exits,
            'team_dropbacks_int': V, 'p_start': p_start, 'cells': cells}


# ------------------------------------------------- sack / scramble / attempt
def branch_lines(par, room, DB, starter_index, seed=20260908, ordinal=0,
                 team='') -> dict:
    """Per-dropback outcomes for each quarterback, integer-valued in the draw.

    Two-stage donor resample: a historical game of this quarterback is drawn
    with probability proportional to its dropbacks, then this draw's dropbacks
    are drawn with replacement from that game's own outcome list. A player with
    no prior dropback falls back to the league donor pool and the fallback is
    counted, never hidden.
    """
    n, m = DB.shape
    out = {k: np.zeros((n, m), np.int64)
           for k in ('db', 'sacks', 'scrambles', 'att', 'cmp', 'pyds')}
    fallback = []
    for i, r in enumerate(room):
        pool = par['donors'].get(r['pid']) or []
        used_fallback = False
        if not pool:
            pool = par['league_donor']
            used_fallback = True
            fallback.append(r['pid'])
        sizes = np.array([len(g) for g in pool], float)
        pg = sizes / sizes.sum()
        rng = _rng(seed, ordinal, team, 1 + i)
        gsel = rng.choice(len(pool), size=m, p=pg)
        for j in range(m):
            d = int(DB[i, j])
            out['db'][i, j] = d
            if d <= 0:
                continue
            g = pool[gsel[j]]
            pick = rng.integers(0, len(g), d)
            ks = np.array([g[q][0] for q in pick])
            cs = np.array([g[q][1] for q in pick])
            ys = np.array([g[q][2] for q in pick])
            att = ks == KINDS.index('attempt')
            out['sacks'][i, j] = int((ks == KINDS.index('sack')).sum())
            out['scrambles'][i, j] = int((ks == KINDS.index('scramble')).sum())
            out['att'][i, j] = int(att.sum())
            out['cmp'][i, j] = int((cs[att] == 1).sum())
            out['pyds'][i, j] = int(ys[att].sum())
        if used_fallback:
            pass
    out['fallback_pids'] = fallback
    return out


# ------------------------------------------------------------- public entry
def room_forecast(par, room, team_db_draws, seed=20260908, ordinal=0, team='',
                  is_opener=False) -> Outcome:
    """The whole chain for one club. Returns per-player draws and summaries."""
    try:
        al = allocate_dropbacks(par, room, team_db_draws, seed=seed,
                                ordinal=ordinal, team=team,
                                is_opener=is_opener)
        ln = branch_lines(par, room, al['db'], al['starter_index'], seed=seed,
                          ordinal=ordinal, team=team)
    except QbRoomV2Error as e:
        return Outcome.fail('QB_ROOM_V2_REFUSED', str(e))
    n, m = al['db'].shape
    rows = []
    for i, r in enumerate(room):
        db = al['db'][i]
        started = (al['starter_index'] == i)
        rows.append({
            'pid': r['pid'], 'rank': r['rank'],
            'was_prev_primary': int(r.get('was_prev_primary', 0)),
            'emergency': bool(r.get('emergency')),
            'p_start': float(started.mean()),
            'p_zero_dropbacks': float((db == 0).mean()),
            'p_replacement_state': float(((~started) & (db > 0)).mean()),
            'p_exits_while_starting': float((started & al['exited']).mean()),
            'dropbacks': float(db.mean()),
            'attempts': float(ln['att'][i].mean()),
            'completions': float(ln['cmp'][i].mean()),
            'pass_yards': float(ln['pyds'][i].mean()),
            'sacks': float(ln['sacks'][i].mean()),
            'scrambles': float(ln['scrambles'][i].mean()),
            'q': {k: [int(np.quantile(ln[k][i], q)) if k != 'pyds'
                      else int(np.quantile(ln[k][i], q))
                      for q in (0.10, 0.50, 0.90)]
                  for k in ('db', 'att', 'cmp', 'pyds')},
            'conditional_pass_yards': (
                float(ln['pyds'][i][db > 0].mean()) if (db > 0).any() else None),
        })
    return Outcome.ok(
        'QB_ROOM_V2_OK',
        value={'rows': rows, 'draws': {k: v for k, v in ln.items()
                                       if k != 'fallback_pids'},
               'allocation': al},
        spec_version=SPEC_VERSION, governance=GOVERNANCE,
        team=team, n_draws=m, n_qb=n,
        p_exit_used=float(par['p_exit']),
        trained_on_ordinals_before=par['trained_on_ordinals_before'],
        use_opener=bool(par['use_opener']),
        league_donor_fallback_pids=ln['fallback_pids'],
        closure='INTEGER_EXACT')
