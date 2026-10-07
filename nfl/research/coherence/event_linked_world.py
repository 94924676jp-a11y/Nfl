#!/usr/bin/env python3.12
"""EVENT-LINKED football worlds: a SHADOW_ONLY replacement for the live post-steps that break accounting.

    python3.12 nfl/research/coherence/event_linked_world.py freeze      # <= 2024 only; writes EVENT_LINKED_FROZEN.json
    python3.12 nfl/research/coherence/event_linked_world.py lock        # hashes the pre-registration + frozen file
    python3.12 nfl/research/coherence/event_linked_world.py dry-run     # in-sample 2024 smoke; nothing written
    python3.12 nfl/research/coherence/event_linked_world.py run --phase development      # 2025 (DEVELOPMENT ONLY)
    python3.12 nfl/research/coherence/event_linked_world.py run --phase confirmation     # 2026 weeks 2-3, ONE read

LAYER: RESEARCH / SHADOW_ONLY. It imports production modules read-only (nfl/sim/game.py, nfl/sim/dst.py,
nfl/tools/classic_slate_run.py, nfl/tools/kicker_world.py, nfl/tools/dst_model.py) and the SC-COH-1 clean harness's
football-only, point-in-time, market-free machinery (sc_coh_1_clean_eval.py). It writes ONLY files under
nfl/research/coherence/ whose names start with EVENT_LINKED_.

WHAT IS BROKEN IN THE LIVE PATH (root causes, verified by reading the code; counts from SC_COH_1_CLEAN_EVAL.json)
  R1 nfl/tools/classic_slate_run.py:106-124 efficiency_worlds: each player's pass, rush and receiving yards are
     multiplied by HIS OWN factor (projected yards per opportunity / simulated yards per opportunity, line 113). The
     passer's factor and every receiver's factor are computed and applied independently, so after the step the
     passer's yards are no longer the sum of the yards his receivers caught: QB pass yards != sum of receiving
     yards in 106,879 of 108,800 club-worlds (0 before the step).
  R2 nfl/tools/classic_slate_run.py:125-126: interceptions are drawn Binomial(world attempts, int_rate) per QB,
     independently of the DST draws, which already fixed each defence's takeaways (nfl/sim/game.py:323 via
     nfl/sim/dst.py:241-253). Opposing-QB INTs > DST takeaways in 25,965 club-worlds.
  R3 nfl/tools/showdown_slate_run.py:94-95 (and classic_slate_run.py:276-277) call anchor_means
     (classic_slate_run.py:133-153), which multiplies every DST DK draw by target/mean (line 150) without touching
     the components it was built from (sacks, takeaways, TDs, safeties, tier), so DST DK != tier + components in
     104,113 club-worlds (0 before).
  R4 (raw draw, nfl/sim/game.py) receptions are Binomial(targets, catch rate) (line 515) drawn independently of the
     receiving yards, which are a Dirichlet split of club passing yards over TARGETS (line 472), and of the receiving
     TDs, which are allocated over target shares (lines 487-488): receiving yards without a reception 103,757
     player-worlds, receiving TDs > receptions 28,733. Rushing TDs are allocated over rush_td_share (489-490) with
     the remainder in an unattributed ghost bucket: TD > carries 6,960; team TD != pass TD + rush TD 3,633. Club
     points are a continuous draw (lines 301-316) and offensive TDs an inversion of them (360-361), so points are
     never an event sum (107,308 non-integer) and fall below 6 x TD in 3,773 worlds. Sacks are not drawn as events
     at all; the DST sack count cannot be reconciled with any offence.
  R5 nfl/tools/kicker_world.py:204-212 derives the kicker from the world's (points, TD) by a remainder identity, so
     the kicker reconciles only with a points total that is itself not an event sum (remainder < 0 in 15,319).

THE REPLACEMENT (one change at a time: the incumbent's VOLUME engine is kept, its accounting is re-expressed)
  EL_S0  every club-world becomes an EVENT LEDGER built from the incumbent's own raw draw: its pass attempts per QB,
         targets, receptions, throwaways, carries, passing yards and TD count are kept; each attempt is one event
         (passer, intended receiver or throwaway, complete flag, yards, TD flag); each carry one event (rusher,
         yards, TD flag). Yards and TDs that the incumbent placed on a player with no reception / carry are moved to
         a teammate who has one (proportionally to their own yards; TDs by TD share, then uniformly), so the club
         totals are preserved and every identity holds on the ledger. Sacks, interceptions and fumbles lost are
         events on the OFFENCE's ledger whose counts are the opposing DST's incumbent draw (dst.py's empirical joint
         tuple, conditioned on the same world's points) -- so the DST's sacks / INTs / fumble recoveries ARE the
         offence's events. Defensive (takeaway-return) and return TDs and safeties are scoreboard events of the
         defending club. Tries follow every TD; FGs follow kicker_world's measured remainder rule on the world's
         latent points; team points are the EVENT SUM 6*TD + XP + 2*2pt + 3*FG + 2*safety, exactly.
  EL_S1  efficiency per EVENT: each completion's yards are multiplied by the receiver's factor (the production
         formula, classic_slate_run.py:113, MIN_SIM_OPPORTUNITIES = 30), each carry's by the rusher's factor. The
         passer's yards are the sum of the same scaled events, so passer and receiver move identically. No INT redraw.
  EL_S2  DST level on event RATES, never on the post-draw total: per defence, the production anchor target's own
         inputs (dst_model.club_rates blend: weeks < W + prior season at PRIOR_GAMES pseudo-games) divided by the
         league's same blend give one intensity multiplier per event type; counts are thinned (m <= 1, Binomial) or
         superposed (m > 1, + Poisson((m - 1) x the band's mean)) and the defensive events are re-placed on the
         ledger. Points, points allowed (DK_PA_v1), tier and DST DK are recomputed from events.
  EL_S3  DK scoring, applied only after every invariant holds.

Every coefficient is a 2021-2024 measurement (EVENT_LINKED_FROZEN.json) or a declared production constant; nothing
is tuned. NOTHING HERE IS A VERDICT ON PRODUCTION. "validated", "correct" and "unbiased" are never written by it.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import functools
import hashlib
import json
import pathlib
import random
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.coherence import invariants as INV  # noqa: E402
from nfl.research.coherence import sc_coh_1_candidate as C  # noqa: E402  (pure helpers only)
from nfl.research.coherence import sc_coh_1_clean_eval as CE  # noqa: E402  (clean machinery, pure functions)
from nfl.research.coherence import sc_coh_1_measure as M  # noqa: E402  (pure helpers only)

HERE = pathlib.Path(__file__).resolve().parent
PREREG = _REPO / 'docs/NFL_COHERENCE_REPAIR_PREREGISTRATION.md'
FROZEN = HERE / 'EVENT_LINKED_FROZEN.json'
LOCK = HERE / 'EVENT_LINKED_PREREG_LOCK.json'
OUT = HERE / 'EVENT_LINKED_WORLD.json'

# ------------------------------------------------------------------------------------------------ frozen design
CUTOFF = 2024
FIT_SEASONS = (2021, 2022, 2023, 2024)
DEV_SEASON = 2025                    # read 3+ times by earlier work: DEVELOPMENT ONLY
DEV_WEEKS = tuple(range(2, 19))
CONF_SEASON = 2026
CONF_WEEKS = (2, 3)                  # week 1 has no earlier week for a point-in-time pool; week 4 has no pbp
CONF_PBP = 'nfl/research/postgame/pbp_2026.79b02496d26004ee.csv.gz'
CONF_PBP_SHA256 = '79b02496d26004eec350c9e671bcc92ba5cb2587e4fc6af22ada51d9513d89ac'
N_WORLDS = 400
SIM_SEED = 20261008                  # == SC-COH-1 clean harness: the incumbent sees the same seeds
EL_SEED_OFFSET = 7
S2_SEED_OFFSET = 11
KICKER_SEED_OFFSET = 13
N_BOOT = CE.N_BOOT
BOOT_SEED = CE.BOOT_SEED
PIT_SEED = CE.PIT_SEED
NI_RATIO_MARGIN = 1.02               # reused from the SC-COH-1 registration: a DECLARED VALUE JUDGEMENT
POOL = CE.PRIMARY_POOL
VARIANTS = ('INCUMBENT_PROD', 'INCUMBENT_RAW', 'EVENT_LINKED', 'EVENT_LINKED_RAW')
PRIMARY_PAIR = ('EVENT_LINKED', 'INCUMBENT_PROD')
PAIRS = (PRIMARY_PAIR, ('EVENT_LINKED_RAW', 'INCUMBENT_RAW'), ('EVENT_LINKED', 'INCUMBENT_RAW'))
STAGES = INV.STAGE_NAMES
MIN_SIM_OPPORTUNITIES = 30           # == classic_slate_run.MIN_SIM_OPPORTUNITIES (asserted)
FG_BANDS = (('fg_0_39', 0, 40), ('fg_40_49', 40, 50), ('fg_50_plus', 50, 10 ** 6))

#: Extra columns this module reads beyond the clean whitelist (kicking, tries, sack yards, laterals, ordering).
EL_EXTRA_COLS = ['play_id', 'extra_point_attempt', 'extra_point_result', 'two_point_conv_result',
                 'field_goal_attempt', 'field_goal_result', 'kick_distance', 'yards_gained',
                 'lateral_receiving_yards', 'lateral_rushing_yards']
EL_PBP_COLS = list(dict.fromkeys(CE.PBP_CLEAN_COLS + EL_EXTRA_COLS))

DEVIATIONS: list = []


class ELError(RuntimeError):
    """A named refusal. An empty, partial or contaminated input is never a result."""

    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}')
        self.code = code


def _require(ok, code, detail=''):
    if not ok:
        raise ELError(code, detail)


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), default=float).encode()


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ================================================================================================ guards
def guard_no_market(obj, where):
    """EL_MARKET_INPUT if any column / key of `obj` (frame, dict, rows) carries a market token (CE.MARKET_TOKENS)."""
    try:
        CE.guard_no_market(obj, where)
    except CE.CleanEvalError as e:
        raise ELError('EL_MARKET_INPUT', str(e)) from None
    return obj


def guard_spec(spec):
    """The simulator's API keys total_line / home_spread must carry the football centre and nothing else."""
    try:
        CE.assert_spec_football_only(spec)
    except CE.CleanEvalError as e:
        raise ELError('EL_MARKET_INPUT' if 'MARKET' in e.code else 'EL_SPEC_NOT_FOOTBALL', str(e)) from None
    return spec


#: Which seasons may be read, opened by run_phase() only after the registration is verified.
_GATE = {'phase': None, 'limits': {}}


def _season_limit(season):
    if season <= CUTOFF:
        return 99
    lim = _GATE['limits'].get(season)
    _require(lim is not None, 'EL_SEASON_LOCKED',
             f'season {season} is not readable in phase {_GATE["phase"]!r} (registration not verified, or not '
             f'this phase\'s season)')
    return lim


@functools.lru_cache(maxsize=None)
def _pbp_file(path):
    return pd.read_csv(_REPO / path if not pathlib.Path(path).is_absolute() else path,
                       usecols=lambda c: c in EL_PBP_COLS, low_memory=False)


def pbp_path(season):
    if season == CONF_SEASON:
        return CONF_PBP
    return str(M.pbp_path(season).relative_to(_REPO))


def load_pbp(season):
    """REG-season play-by-play, whitelisted columns only, gated by season, truncated to the phase's week limit.
    2026 is read only from the pinned capture CONF_PBP whose sha256 must match CONF_PBP_SHA256."""
    lim = _season_limit(season)
    path = pbp_path(season)
    if season == CONF_SEASON:
        got = _sha(_REPO / path)
        _require(got == CONF_PBP_SHA256, 'EL_CONFIRMATION_FILE_CHANGED', f'{path} sha256 {got}')
    df = _pbp_file(path)
    _require(set(EL_PBP_COLS) <= set(df.columns), 'EL_SCHEMA', f'pbp {season} lacks {set(EL_PBP_COLS) - set(df.columns)}')
    df = df[(df.season_type == 'REG') & (df.week <= lim)].copy()
    guard_no_market(df, f'pbp {season}')
    _require(len(df) > 500, 'EL_EMPTY_INPUT', f'pbp {season} has {len(df)} REG rows at weeks <= {lim}')
    _require(int(df.season.min()) == int(df.season.max()) == season, 'EL_SEASON_MISMATCH', f'pbp {season}')
    return df.sort_values(['game_id', 'play_id'], kind='stable').reset_index(drop=True)


def load_team_game():
    """TEAM_GAME through the clean whitelist (no line / spread / implied / moneyline), gated by season and week."""
    out = []
    for r in CE._tg_raw():
        s, w = r.get('season'), r.get('week')
        if s is None or w is None:
            continue
        s, w = int(s), int(w)
        if s > CUTOFF:
            lim = _GATE['limits'].get(s)
            if lim is None or w > lim:
                continue
        out.append(dict(r))
    guard_no_market(out, 'TEAM_GAME')
    _require(len(out) > 1000, 'EL_EMPTY_INPUT', f'TEAM_GAME has {len(out)} usable rows')
    return out


# ================================================================================================ season frames
def scoring_events(df):
    """Per (game_id, club): typed touchdowns, tries by the type of the TD they followed, FGs by band, safeties.

    TD types (by play): OFF = pass/rush TD by the offence; OFF_OTHER = other offensive-play TD by the offence
    (offensive fumble recovery); DEF = a TD by the defending club on a scrimmage play (takeaway return); ST = every
    other TD (kick / punt / blocked-kick return), credited to td_team. A try is typed by the last TD before it."""
    f = df.copy()
    for c in ('touchdown', 'pass_touchdown', 'rush_touchdown', 'safety', 'extra_point_attempt', 'two_point_attempt',
              'field_goal_attempt'):
        f[c] = f[c].fillna(0)
    scr = f.play_type.isin(['pass', 'run']) & (f.two_point_attempt != 1)
    td = (f.touchdown == 1) & f.td_team.notna() & (f.extra_point_attempt != 1) & (f.two_point_attempt != 1)
    typ = np.select([td & scr & (f.td_team == f.posteam) & ((f.pass_touchdown == 1) | (f.rush_touchdown == 1)),
                     td & scr & (f.td_team == f.posteam), td & scr & (f.td_team == f.defteam), td],
                    ['OFF', 'OFF_OTHER', 'DEF', 'ST'], default='')
    f['td_type'] = typ
    f['last_td'] = pd.Series(np.where(typ != '', typ, None), index=f.index).groupby(f.game_id).ffill()
    rows = collections.defaultdict(collections.Counter)
    for (g, t, k), n in f[td].groupby(['game_id', 'td_team', 'td_type']).size().items():
        rows[(g, t)][f'td_{k}'] += int(n)
    tries = f[(f.extra_point_attempt == 1) | (f.two_point_attempt == 1)]
    for r in tries.itertuples(index=False):
        k = r.last_td if isinstance(r.last_td, str) else 'OFF'
        grp = 'off' if k in ('OFF', 'OFF_OTHER') else k.lower()
        c = rows[(r.game_id, r.posteam)]
        if r.extra_point_attempt == 1:
            c[f'xp_att_{grp}'] += 1
            c[f'xp_made_{grp}'] += int(r.extra_point_result == 'good')
        else:
            c[f'tp_att_{grp}'] += 1
            c[f'tp_made_{grp}'] += int(r.two_point_conv_result == 'success')
    fg = f[(f.field_goal_attempt == 1)]
    for r in fg.itertuples(index=False):
        d = float(r.kick_distance) if r.kick_distance == r.kick_distance else 0.0
        b = next(name for name, lo, hi in FG_BANDS if lo <= d < hi)
        c = rows[(r.game_id, r.posteam)]
        c[f'{b}_att'] += 1
        if r.field_goal_result == 'made':
            c[f'{b}_made'] += 1
            c['fg_made'] += 1
    for (g, t), n in f[f.safety == 1].groupby(['game_id', 'defteam']).size().items():
        rows[(g, t)]['safeties'] += int(n)
    lat = f[(f.lateral_receiving_yards.fillna(0) != 0) | (f.lateral_rushing_yards.fillna(0) != 0)]
    for (g, t), n in lat.groupby(['game_id', 'posteam']).size().items():
        rows[(g, t)]['lateral_plays'] += int(n)
    return rows


def season_frames(season):
    """sc_coh_1_clean_eval.season_frames on this module's gated loader, plus typed scoring events."""
    df = load_pbp(season)
    plays = M.offensive_plays(df)
    pg = M.player_games(plays)
    fin = (df.groupby('game_id').agg(season=('season', 'first'), week=('week', 'first'), home=('home_team', 'first'),
                                     away=('away_team', 'first'), hs=('home_score', 'max'), as_=('away_score', 'max'))
           .reset_index())
    _require(len(fin) > 0 and fin[['hs', 'as_']].notna().all().all(), 'EL_FINALS_INCOMPLETE', str(season))
    dst = M.dst_games(df, fin)
    pos_of = C._pos_of()
    it = df[(df.play_type == 'pass') & (df.interception.fillna(0) == 1) & (df.two_point_attempt.fillna(0) != 1)]
    it = it[it.passer_player_id.map(lambda x: pos_of.get(x) == 'QB')]
    ints = it.groupby(['game_id', 'posteam']).size().to_dict()
    sched = fin[['game_id', 'week', 'home', 'away']].copy()
    for x in (plays, pg, fin, dst):
        guard_no_market(x, f'season_frames {season}')
    return {'df': df, 'plays': plays, 'pg': pg, 'fin': fin, 'dst': dst, 'ints': ints, 'sched': sched,
            'scoring': scoring_events(df)}


# ================================================================================================ <= 2024 rates
def measure_event_rates(seasons=FIT_SEASONS):
    """Every new coefficient of the event-linked world, measured on 2021-2024 REG play-by-play."""
    _require(max(seasons) <= CUTOFF, 'EL_HELDOUT_LEAK', f'event rates from {seasons}')
    a = collections.Counter()
    sack_yards, fl_loc = [], collections.Counter()
    kick = collections.Counter()
    band = collections.Counter()
    hist = collections.Counter()
    for s in seasons:
        df = load_pbp(s)
        f = df.copy()
        for c in ('sack', 'interception', 'fumble_lost', 'complete_pass', 'two_point_attempt', 'touchdown'):
            f[c] = f[c].fillna(0)
        scr = f.play_type.isin(['pass', 'run']) & (f.two_point_attempt != 1)
        a['int'] += int((scr & (f.interception == 1)).sum())
        fl = scr & (f.fumble_lost == 1) & (f.interception == 0)
        a['fumble_lost'] += int(fl.sum())
        loc = np.select([f.sack == 1, f.complete_pass == 1, f.play_type == 'run'], ['sack', 'reception', 'carry'],
                        default='other')
        for k, n in collections.Counter(loc[fl.to_numpy()]).items():
            fl_loc[k] += int(n)
        sy = f[scr & (f.sack == 1)].yards_gained.fillna(0).to_numpy(float)
        sack_yards.extend(np.maximum(0.0, -sy).round(0).tolist())
        dtd = (f.touchdown == 1) & f.td_team.notna() & (f.td_team == f.defteam)
        a['dst_td_all'] += int(dtd.sum())
        a['dst_td_takeaway_return'] += int((dtd & scr).sum())
        sc = scoring_events(df)
        fin = df.groupby('game_id').agg(home=('home_team', 'first'), away=('away_team', 'first'),
                                        hs=('home_score', 'max'), as_=('away_score', 'max'))
        for g, r in fin.iterrows():
            for t, pts in ((r.home, r.hs), (r.away, r.as_)):
                c = sc.get((g, t), collections.Counter())
                kick['club_games'] += 1
                kick['points'] += float(pts)
                for k, v in c.items():
                    kick[k] += v
                tds = sum(c.get(f'td_{k}', 0) for k in ('OFF', 'OFF_OTHER', 'DEF', 'ST'))
                conv = sum(c.get(f'xp_made_{g_}', 0) + 2 * c.get(f'tp_made_{g_}', 0) for g_ in ('off', 'def', 'st'))
                ident = 6 * tds + conv + 3 * c.get('fg_made', 0) + 2 * c.get('safeties', 0)
                hist['club_games'] += 1
                hist['points_ne_event_sum'] += int(abs(ident - float(pts)) > 1e-9)
                hist['club_games_with_lateral_plays'] += int(c.get('lateral_plays', 0) > 0)
        for name, lo, hi in FG_BANDS:
            band[f'{name}_att'] += sum(v.get(f'{name}_att', 0) for v in sc.values())
            band[f'{name}_made'] += sum(v.get(f'{name}_made', 0) for v in sc.values())
    _require(a['int'] > 0 and a['fumble_lost'] > 0 and len(sack_yards) > 100 and kick['club_games'] > 1000,
             'EL_EMPTY_INPUT', f'event rate inputs {dict(a)} sacks {len(sack_yards)}')
    k3 = sum(fl_loc[x] for x in ('carry', 'reception', 'sack'))
    all_td = sum(kick[f'td_{k}'] for k in ('OFF', 'OFF_OTHER', 'DEF', 'ST'))
    tp_att = sum(kick[f'tp_att_{g}'] for g in ('off', 'def', 'st'))
    tp_made = sum(kick[f'tp_made_{g}'] for g in ('off', 'def', 'st'))
    xp_att = sum(kick[f'xp_att_{g}'] for g in ('off', 'def', 'st'))
    xp_made = sum(kick[f'xp_made_{g}'] for g in ('off', 'def', 'st'))
    off_td = kick['td_OFF'] + kick['td_OFF_OTHER']
    rem_off = kick['points'] - 6 * off_td - kick['xp_made_off'] - 2 * kick['tp_made_off']
    made = sum(band[f'{b}_made'] for b, _, _ in FG_BANDS)
    out = {
        'seasons': list(seasons),
        'p_int_of_takeaway': round(a['int'] / (a['int'] + a['fumble_lost']), 6),
        'takeaway_counts': {'int': a['int'], 'fumble_lost': a['fumble_lost']},
        'fumble_location_share': {k: round(fl_loc[k] / k3, 6) for k in ('carry', 'reception', 'sack')},
        'fumble_location_counts': dict(fl_loc),
        'FUMBLE_OTHER_RULE': 'fumbles lost on other scrimmage plays (aborted snaps etc.) are excluded from the '
                             'location shares and reported in fumble_location_counts',
        'sack_yards_lost_empirical': sorted(int(x) for x in sack_yards),
        'sack_yards_lost_mean': round(float(np.mean(sack_yards)), 4),
        'p_dst_td_is_takeaway_return': round(a['dst_td_takeaway_return'] / a['dst_td_all'], 6),
        'dst_td_counts': {'all_td_team_eq_defteam': a['dst_td_all'], 'on_scrimmage_plays': a['dst_td_takeaway_return']},
        'kicker': {'try_rate_2pt_per_td': round(tp_att / all_td, 6), 'two_pt_success': round(tp_made / tp_att, 6),
                   'pat_make_rate': round(xp_made / xp_att, 6),
                   'fg_share': round(3 * kick['fg_made'] / rem_off, 6),
                   'FG_SHARE_DEFINITION': ('3 x FG made / (points - 6 x offensive TD - XP made after offensive TDs - '
                                           '2 x 2pt made after offensive TDs): kicker_world.measure\'s remainder rule '
                                           'with tries typed by the TD they followed'),
                   'made_band_mix': {b: round(band[f'{b}_made'] / made, 6) for b, _, _ in FG_BANDS},
                   'band_make_rate': {b: round(band[f'{b}_made'] / band[f'{b}_att'], 6) for b, _, _ in FG_BANDS},
                   'counts': {'club_games': kick['club_games'], 'all_td': all_td, 'off_td': off_td,
                              'tp_att': tp_att, 'tp_made': tp_made, 'xp_att': xp_att, 'xp_made': xp_made,
                              'fg_made': kick['fg_made'], 'points': kick['points']}},
        'history_accounting_2021_2024': dict(hist),
    }
    return out


# ================================================================================================ freeze / lock
def _clean_frozen_verified():
    """The SC-COH-1 clean frozen fits are reused; they must still match the clean lock byte for byte."""
    try:
        lk = CE.verify_prereg()
    except CE.CleanEvalError as e:
        raise ELError('EL_CLEAN_FROZEN_CHANGED', str(e)) from None
    return lk


def compute_fits():
    """The incumbent's <= 2024 refits (clean harness procedures), required identical to the clean frozen hash."""
    _require(not _GATE['limits'], 'EL_GATE_OPEN', 'fits must be computed with every later season closed')
    tg, pgr, rh = CE.load_team_game(), CE.load_player_game(), CE.load_role_history()
    fits = {'football_residuals': CE.fit_football_residuals(tg), 'shared_state': CE.fit_shared_state(tg),
            'efficiency': CE.fit_efficiency(pgr), 'variance_components': CE.fit_variance_components(pgr),
            'usage': CE.fit_usage(pgr, rh), 'dst_bands': CE.fit_dst_bands(tg), 'int_rate': CE.fit_int_rate()}
    cf = json.loads(CE.FROZEN.read_text())
    got = hashlib.sha256(_canon(fits)).hexdigest()
    _require(got == cf['fits_sha256'], 'EL_FITS_NOT_REPRODUCED', f'incumbent refits {got} != clean {cf["fits_sha256"]}')
    return fits


def band_means(dst_bands):
    """Per points-allowed band: mean (sacks, takeaways, D/ST TD, safeties) of the <= 2024 empirical tuples."""
    out = {}
    for k, v in dst_bands['bands'].items():
        a = np.asarray(v['empirical_tuples'], float)
        out[k] = [round(float(x), 6) for x in a.mean(0)]
    return out


def freeze():
    _require(not _GATE['limits'], 'EL_GATE_OPEN', 'freeze must not run with 2025 / 2026 readable')
    lk = _clean_frozen_verified()
    fits = compute_fits()
    rates = measure_event_rates()
    doc = {'ARTIFACT': 'EVENT_LINKED_FROZEN', 'STATUS': 'SHADOW_ONLY', 'cutoff': CUTOFF, 'READ_NO_2025_OR_2026_ROW': True,
           'clean_frozen': {'path': lk['frozen'], 'sha256': lk['frozen_sha256'],
                            'fits_sha256': json.loads(CE.FROZEN.read_text())['fits_sha256']},
           'event_rates': rates, 'dst_band_means': band_means(fits['dst_bands']),
           'design': design_constants(), 'written_at': _now()}
    doc['event_rates_sha256'] = hashlib.sha256(_canon(rates)).hexdigest()
    FROZEN.write_text(json.dumps(doc, indent=1, default=float))
    return doc


def design_constants():
    return {'CUTOFF': CUTOFF, 'FIT_SEASONS': list(FIT_SEASONS), 'DEV_SEASON': DEV_SEASON, 'DEV_WEEKS': list(DEV_WEEKS),
            'CONF_SEASON': CONF_SEASON, 'CONF_WEEKS': list(CONF_WEEKS), 'CONF_PBP': CONF_PBP,
            'CONF_PBP_SHA256': CONF_PBP_SHA256, 'N_WORLDS': N_WORLDS, 'SIM_SEED': SIM_SEED,
            'EL_SEED_OFFSET': EL_SEED_OFFSET, 'S2_SEED_OFFSET': S2_SEED_OFFSET, 'KICKER_SEED_OFFSET': KICKER_SEED_OFFSET,
            'N_BOOT': N_BOOT, 'BOOT_SEED': BOOT_SEED, 'PIT_SEED': PIT_SEED, 'NI_RATIO_MARGIN': NI_RATIO_MARGIN,
            'POOL': POOL, 'VARIANTS': list(VARIANTS), 'PRIMARY_PAIR': list(PRIMARY_PAIR),
            'PAIRS': [list(p) for p in PAIRS], 'STAGES': list(STAGES), 'MIN_SIM_OPPORTUNITIES': MIN_SIM_OPPORTUNITIES,
            'INVARIANTS': list(INV.INVARIANTS)}


def lock():
    _require(PREREG.exists(), 'EL_PREREG_ABSENT', str(PREREG))
    _require(FROZEN.exists(), 'EL_FROZEN_ABSENT', str(FROZEN))
    if OUT.exists():
        prior = json.loads(OUT.read_text())
        _require(not prior.get('phases'), 'EL_ALREADY_SCORED',
                 'a phase has been scored under the current lock; re-locking would re-register after reading data')
    doc = {'ARTIFACT': 'EVENT_LINKED_PREREG_LOCK', 'prereg': str(PREREG.relative_to(_REPO)), 'prereg_sha256': _sha(PREREG),
           'frozen': str(FROZEN.relative_to(_REPO)), 'frozen_sha256': _sha(FROZEN),
           'clean_frozen_sha256': _sha(CE.FROZEN), 'locked_at': _now()}
    LOCK.write_text(json.dumps(doc, indent=1))
    return doc


def verify_prereg(prereg=PREREG, lock_path=LOCK, frozen=FROZEN):
    """Refuse unless the pre-registration and both frozen files are byte-identical to what was locked."""
    _require(pathlib.Path(lock_path).exists(), 'EL_PREREG_NOT_LOCKED', str(lock_path))
    lk = json.loads(pathlib.Path(lock_path).read_text())
    _require(pathlib.Path(prereg).exists(), 'EL_PREREG_ABSENT', str(prereg))
    got = _sha(prereg)
    _require(got == lk['prereg_sha256'], 'EL_PREREG_CHANGED', f'pre-registration sha256 {got} != locked {lk["prereg_sha256"]}')
    _require(_sha(frozen) == lk['frozen_sha256'], 'EL_FROZEN_CHANGED', 'EVENT_LINKED_FROZEN.json changed since the lock')
    _require(_sha(CE.FROZEN) == lk['clean_frozen_sha256'], 'EL_CLEAN_FROZEN_CHANGED', 'clean frozen file changed')
    return lk


# ================================================================================================ incumbent
def simulate_incumbent(model, spec, vol, n, seed):
    """nfl/sim/game.py:simulate_game_centred exactly as the clean harness calls it (production's Showdown call),
    retaining club_worlds (pass att, rush att, targets, throwaways) and the raw DK draws."""
    from nfl.sim import game as G
    guard_spec(spec)
    try:
        CE._check_spec_nonempty(spec, n)
    except CE.CleanEvalError as e:
        raise ELError('EL_EMPTY_INPUT', str(e)) from None
    o = G.simulate_game_centred(model, spec, vol, n_sims=n, seed=seed, n_calib=n)
    if o.state.value != 'PASS':
        raise ELError('EL_INCUMBENT_REFUSED', f'{o.code} {o.detail}')
    v = o.value
    out = {'players': {k: np.asarray(x, float) for k, x in v['stat_draws'].items()}, 'ints': None,
           'club_points': {c: np.array([w[0] for w in x]) for c, x in v['club_scoring_worlds'].items()},
           'club_td': {c: np.array([w[1] for w in x], float) for c, x in v['club_scoring_worlds'].items()},
           'dst_dk': {c['club']: np.asarray(v['draws'][c['dst_id']], float) for c in spec['clubs']},
           'dst_comp': {c['club']: np.asarray(v['dst_components'][c['dst_id']], float) for c in spec['clubs']},
           'club_worlds': {c: np.asarray(x, float) for c, x in v['club_worlds'].items()},
           'raw_dk': {p['id']: np.asarray(v['draws'][p['id']], float) for c in spec['clubs'] for p in c['players']}}
    for c in spec['clubs']:
        for p in c['players']:
            _require(p['id'] in out['players'], 'EL_EMPTY_DRAWS', f"{p['id']} has no draws")
    return out


def _stat10_to_pf(S10, ints=None):
    """(P, n, 10) incumbent stat lines -> (P, n, len(PF)) with NaN for every field the incumbent does not draw."""
    P_, n = S10.shape[:2]
    S = np.full((P_, n, len(INV.PF)), np.nan)
    for i, f in enumerate(CE.STAT_FIELDS):
        S[..., INV.PX[f]] = S10[..., i]
    if ints is not None:
        S[..., INV.PX['ints']] = ints
    return S


def incumbent_kicker(points, td, kicker_rates, seed):
    """The production Showdown kicker step (nfl/tools/kicker_world.draw) on the incumbent's world, with the
    2021-2024 rates (kicker_world.measure reads 2021-2025, so its rates are not used here)."""
    from nfl.tools import kicker_world as KW
    rng = random.Random(seed)
    rates = {'try_rate_2pt': kicker_rates['try_rate_2pt_per_td'], 'two_pt_success': kicker_rates['two_pt_success'],
             'pat_make_rate': kicker_rates['pat_make_rate'], 'fg_share': kicker_rates['fg_share']}
    mix = {'made_mix': dict(kicker_rates['made_band_mix']), 'make_rate': dict(kicker_rates['band_make_rate'])}
    rows = collections.defaultdict(list)
    for p, t in zip(points, td):
        dk, d = KW.draw(float(p), float(t), mix, rates, rng)
        rows['dk'].append(dk)
        rows['xp_att'].append(d['xp_att'])
        rows['xp_made'].append(d['xp_made'])
        rows['fg_made'].append(d['fg_made'])
        rows['tp_att'].append(float(t) - d['xp_att'])
        for b, _, _ in FG_BANDS:
            rows[b].append(d[f'{b}_made'])
    return {k: np.asarray(v, float) for k, v in rows.items()}


def incumbent_bundle(world, spec, stage, kicker, dk_mode):
    """A provider-neutral bundle of one incumbent stage. dk_mode: 'raw' (simulator's own DK), 'classic' (the
    efficiency step's dk_from_stats), None."""
    clubs = {}
    order = [c['club'] for c in spec['clubs']]
    n = len(world['club_points'][order[0]])
    for c, oc in ((spec['clubs'][0], spec['clubs'][1]), (spec['clubs'][1], spec['clubs'][0])):
        t, o = c['club'], oc['club']
        ids = [p['id'] for p in c['players']]
        S10 = np.stack([world['players'][i] for i in ids])
        ints = np.stack([world['ints'][i] for i in ids]) if world.get('ints') is not None else None
        S = _stat10_to_pf(S10, ints)
        cw = world['club_worlds'][t]
        comp = np.asarray(world['dst_comp'][t], float)
        opts = np.asarray(world['club_points'][o], float)
        team = {'points': np.asarray(world['club_points'][t], float), 'off_td': np.asarray(world['club_td'][t], float),
                'pass_att': cw[:, 0], 'rush_att': cw[:, 1], 'throwaways': cw[:, 3]}
        dst = {'sacks': comp[:, 0], 'takeaways': comp[:, 1], 'dst_td': comp[:, 2], 'safeties': comp[:, 3],
               'pa': opts, 'tier': INV.dk_tier(opts), 'dk': np.asarray(world['dst_dk'][t], float)}
        dk = None
        if dk_mode == 'raw':
            dk = {'classic': np.stack([world['raw_dk'][i] for i in ids])}
        elif dk_mode == 'classic':
            x = lambda f: S10[..., CE.SX[f]]
            iv = ints if ints is not None else np.zeros_like(x('pass_att'))
            dk = {'classic': _vec_dk_from_stats(S10, iv)}
        clubs[t] = {'ids': ids, 'pos': [p['position'] for p in c['players']], 'S': S, 'team': team, 'dst': dst,
                    'kicker': kicker[t], 'dk': dk}
    return {'provider': 'INCUMBENT', 'stage': stage, 'n': n, 'order': order, 'clubs': clubs, 'ledger': None}


def _vec_dk_from_stats(S10, ints):
    """classic_slate_run.dk_from_stats applied element-wise (the production efficiency step's scoring)."""
    from nfl.tools import classic_slate_run as CR
    f = np.vectorize(CR.dk_from_stats)
    x = [S10[..., i] for i in range(10)]
    return f(*x, ints)


# ================================================================================================ the event ledger
K_PASS, K_SACK, K_RUSH = INV.KIND_PASS, INV.KIND_SACK, INV.KIND_RUSH


def _pos_lists(club_spec):
    pos = [p['position'] for p in club_spec['players']]
    Q = np.array([i for i, x in enumerate(pos) if x == 'QB'], int)
    R = np.array([i for i, x in enumerate(pos) if x != 'QB'], int)
    return pos, Q, R


def _move_orphans(Y, has):
    """Yards on players without the matching event move to teammates with one, proportionally to their own yards
    (or to their event counts when those yards are all zero). Returns (new yards, dropped total)."""
    Y = np.asarray(Y, float).copy()
    orphan = float(Y[~has].sum())
    Y[~has] = 0.0
    if orphan == 0.0:
        return Y, 0.0
    if not has.any():
        return Y, orphan
    base = Y[has].sum()
    if base > 0:
        Y[has] += orphan * Y[has] / base
    else:
        Y[has] += orphan / has.sum()
    return Y, 0.0


def _split(total, k, rng):
    """Split `total` over k events with a flat Dirichlet (declared: within-player yards per event carry no model)."""
    if k <= 0:
        return np.zeros(0)
    if k == 1:
        return np.array([float(total)])
    g = rng.gamma(1.0, 1.0, size=k)
    return float(total) * g / g.sum()


def offense_block(club_spec, S10, cw, club_td, rng, acct):
    """One club's offensive event ledgers, one dict of arrays per world, from the incumbent's raw S0 draw.

    Kept from the incumbent: per-QB attempts, per-receiver targets and receptions, throwaways, per-player carries,
    club passing yards (= sum of QB yards), per-player rushing yards, the passing-TD count and the club TD count."""
    pos, Q, R = _pos_lists(club_spec)
    P_ = len(pos)
    n = S10.shape[1]
    ix = CE.SX
    td_share = np.array([max(0.0, float(p.get('pass_td_share', 0.0))) for p in club_spec['players']])
    worlds = []
    for w in range(n):
        qa = np.rint(S10[Q, w, ix['pass_att']]).astype(int)
        pa = int(qa.sum())
        tgt = np.rint(S10[R, w, ix['targets']]).astype(int)
        rec = np.rint(S10[R, w, ix['receptions']]).astype(int)
        tw = int(round(cw[w, 3]))
        _require(pa == int(round(cw[w, 0])) and int(tgt.sum()) + tw == pa, 'EL_INCUMBENT_VOLUME_NOT_RECONCILED',
                 f"{club_spec['club']} world {w}: QB attempts {pa}, club {cw[w, 0]}, targets {tgt.sum()} + "
                 f'throwaways {tw}')
        passer = rng.permutation(np.repeat(Q, qa)) if pa else np.zeros(0, int)
        recv = rng.permutation(np.concatenate([np.repeat(R, tgt), -np.ones(tw, int)])) if pa else np.zeros(0, int)
        comp = np.zeros(pa, bool)
        for j, r in enumerate(R):
            if rec[j] > 0:
                idx = np.flatnonzero(recv == r)
                comp[rng.choice(idx, rec[j], replace=False)] = True
        cpy = float(S10[Q, w, ix['pass_yards']].sum())
        Y, dropped = _move_orphans(S10[R, w, ix['rec_yards']], rec > 0)
        acct['pass_yards_moved_to_a_catching_teammate'] += float(np.abs(S10[R, w, ix['rec_yards']] - Y).sum()) / 2.0
        if dropped:
            acct['club_worlds_pass_yards_without_any_completion'] += 1
            acct['pass_yards_dropped_no_completion'] += dropped
        yards = np.zeros(pa)
        for j, r in enumerate(R):
            if rec[j] > 0:
                idx = np.flatnonzero(comp & (recv == r))
                yards[idx] = _split(Y[j], len(idx), rng)
        acct['pass_yards_reassociation_abs'] += abs(float(yards.sum()) - (cpy - dropped)) if pa else 0.0
        # ---- passing TDs on completions
        npt = int(round(S10[Q, w, ix['pass_td']].sum()))
        hint = np.minimum(np.rint(S10[R, w, ix['rec_td']]).astype(int), rec)
        td = np.zeros(pa, bool)
        for j, r in enumerate(R):
            if hint[j] > 0:
                idx = np.flatnonzero(comp & (recv == r))
                td[rng.choice(idx, hint[j], replace=False)] = True
        excess = int(td.sum()) - npt
        if excess > 0:
            on = np.flatnonzero(td)
            td[rng.choice(on, excess, replace=False)] = False
        need = npt - int(td.sum())
        leftover_pass = 0
        if need > 0:
            free = np.flatnonzero(comp & ~td)
            k = min(need, len(free))
            if k > 0:
                wts = td_share[recv[free]]
                p_ = wts / wts.sum() if wts.sum() > 0 else None
                td[rng.choice(free, k, replace=False, p=p_)] = True
                acct['pass_td_moved_to_another_completion'] += k
            leftover_pass = need - k
        # ---- carries
        car = np.rint(S10[:, w, ix['carries']]).astype(int)
        _require(int(car.sum()) == int(round(cw[w, 1])), 'EL_INCUMBENT_VOLUME_NOT_RECONCILED',
                 f"{club_spec['club']} world {w}: carries {car.sum()} != rush attempts {cw[w, 1]}")
        rusher = np.repeat(np.arange(P_), car)
        RY, rdropped = _move_orphans(S10[:, w, ix['rush_yards']], car > 0)
        acct['rush_yards_dropped_no_carry'] += rdropped
        ryd = np.zeros(len(rusher))
        for i in range(P_):
            if car[i] > 0:
                idx = np.flatnonzero(rusher == i)
                ryd[idx] = _split(RY[i], len(idx), rng)
        rtd = np.zeros(len(rusher), bool)
        rhint = np.minimum(np.rint(S10[:, w, ix['rush_td']]).astype(int), car)
        for i in range(P_):
            if rhint[i] > 0:
                idx = np.flatnonzero(rusher == i)
                rtd[rng.choice(idx, rhint[i], replace=False)] = True
        n_rush_td = int(round(club_td[w])) - npt
        excess = int(rtd.sum()) - max(0, n_rush_td)
        if excess > 0:
            on = np.flatnonzero(rtd)
            rtd[rng.choice(on, excess, replace=False)] = False
        need = max(0, n_rush_td) - int(rtd.sum()) + leftover_pass
        if need > 0:
            free = np.flatnonzero(~rtd)
            k = min(need, len(free))
            if k > 0:
                rtd[rng.choice(free, k, replace=False)] = True
                acct['rush_td_placed_on_an_unattributed_carry'] += k
            if need - k > 0:
                acct['td_dropped_no_free_event'] += need - k
        acct['pass_td_without_a_free_completion_moved_to_rushing'] += leftover_pass
        worlds.append({'passer': passer, 'receiver': recv, 'complete': comp, 'pyards': yards, 'ptd': td,
                       'rusher': rusher, 'ryards': ryd, 'rtd': rtd, 'qa': qa})
    return {'pos': pos, 'Q': Q, 'R': R, 'P': P_, 'worlds': worlds,
            'pass_att_share': np.array([float(p.get('pass_att_share', 0.0)) for p in club_spec['players']])}


def defense_block(off, counts, opp_dst_td, opp_sf, rates, rng, acct):
    """Defensive events of the OPPONENT's DST on this offence, placed on the offence's ledgers.

    counts: {'sacks': (n,), 'ints': (n,), 'fumbles': (n,)} -- what the opponent's DST takes from THIS offence.
    opp_dst_td / opp_sf: the opponent's D/ST touchdowns and safeties (its scoreboard events).
    Returns per-world placements and the opponent's typed TD counts."""
    n = len(off['worlds'])
    sy = np.asarray(rates['sack_yards_lost_empirical'], float)
    loc = rates['fumble_location_share']
    p_ret = rates['p_dst_td_is_takeaway_return']
    placed = []
    opp_def_td, opp_st_td = np.zeros(n), np.zeros(n)
    Q = off['Q']
    for w in range(n):
        W = off['worlds'][w]
        qa = W['qa']
        if qa.sum() > 0:
            pq = qa / qa.sum()
        else:
            s = off['pass_att_share'][Q]
            pq = s / s.sum() if s.sum() > 0 else np.full(len(Q), 1.0 / len(Q))
        k = int(counts['sacks'][w])
        sk_passer = rng.choice(Q, k, p=pq) if k else np.zeros(0, int)
        sk_yards = -rng.choice(sy, k) if k else np.zeros(0)
        inc = np.flatnonzero(~W['complete'])
        ki = int(counts['ints'][w])
        m = min(ki, len(inc))
        int_idx = rng.choice(inc, m, replace=False) if m else np.zeros(0, int)
        nf = int(counts['fumbles'][w]) + (ki - m)
        acct['ints_converted_to_fumbles_no_incompletion'] += ki - m
        # fumble candidates: carries without TD, completions without TD, sacks
        cand = {'carry': list(np.flatnonzero(~W['rtd'])),
                'reception': list(np.flatnonzero(W['complete'] & ~W['ptd'])),
                'sack': list(range(k))}
        fum = {'carry': [], 'reception': [], 'sack': []}
        for _ in range(nf):
            avail = [c for c in ('carry', 'reception', 'sack') if cand[c]]
            if not avail:
                acct['fumbles_dropped_no_free_event'] += 1
                continue
            p_ = np.array([loc[c] for c in avail])
            c = avail[int(rng.choice(len(avail), p=p_ / p_.sum()))] if p_.sum() > 0 else avail[0]
            j = int(rng.integers(len(cand[c])))
            fum[c].append(cand[c].pop(j))
        # the opponent's D/ST TDs: a takeaway returned for a TD, or a kick / punt / blocked-kick return
        takeaways = [('int', int(i)) for i in int_idx] + [(c, int(i)) for c in fum for i in fum[c]]
        free_ta = list(range(len(takeaways)))
        returned = []
        for _ in range(int(opp_dst_td[w])):
            if free_ta and rng.random() < p_ret:
                returned.append(takeaways[free_ta.pop(int(rng.integers(len(free_ta))))])
                opp_def_td[w] += 1
            else:
                opp_st_td[w] += 1
        placed.append({'sk_passer': sk_passer, 'sk_yards': sk_yards, 'int_idx': np.asarray(int_idx, int),
                       'fum': {c: np.asarray(v, int) for c, v in fum.items()}, 'returned': returned})
    return {'placed': placed, 'opp_def_td': opp_def_td, 'opp_st_td': opp_st_td, 'opp_safeties': np.asarray(opp_sf, float)}


def assemble_ledger(off, dfn):
    """Concatenate one club's per-world offence events and the placed defensive events into one ledger."""
    cols = collections.defaultdict(list)
    for w, (W, Dp) in enumerate(zip(off['worlds'], dfn['placed'])):
        pa, nr, ns = len(W['passer']), len(W['rusher']), len(Dp['sk_passer'])
        it = np.zeros(pa, bool)
        it[Dp['int_idx']] = True
        fp = np.zeros(pa, bool)
        fp[Dp['fum']['reception']] = True
        fr = np.zeros(nr, bool)
        fr[Dp['fum']['carry']] = True
        fs = np.zeros(ns, bool)
        fs[Dp['fum']['sack']] = True
        cols['world'] += [np.full(pa + ns + nr, w)]
        cols['kind'] += [np.full(pa, K_PASS), np.full(ns, K_SACK), np.full(nr, K_RUSH)]
        cols['passer'] += [W['passer'], Dp['sk_passer'], np.full(nr, -1)]
        cols['receiver'] += [W['receiver'], np.full(ns, -1), np.full(nr, -1)]
        cols['rusher'] += [np.full(pa, -1), np.full(ns, -1), W['rusher']]
        cols['complete'] += [W['complete'], np.zeros(ns, bool), np.zeros(nr, bool)]
        cols['yards'] += [np.where(W['complete'], W['pyards'], 0.0), Dp['sk_yards'], W['ryards']]
        cols['td'] += [W['ptd'], np.zeros(ns, bool), W['rtd']]
        cols['int'] += [it, np.zeros(ns, bool), np.zeros(nr, bool)]
        cols['fumble'] += [fp, fs, fr]
        cols['fumbler'] += [np.where(fp, W['receiver'], -1), np.where(fs, Dp['sk_passer'], -1),
                            np.where(fr, W['rusher'], -1)]
    L = {k: np.concatenate(v) if v else np.zeros(0) for k, v in cols.items()}
    for k in ('world', 'kind', 'passer', 'receiver', 'rusher', 'fumbler'):
        L[k] = L[k].astype(int)
    for k in ('complete', 'td', 'int', 'fumble'):
        L[k] = L[k].astype(bool)
    L['yards'] = L['yards'].astype(float)
    return L


def tries(n_td, kr, rng):
    """Tries after n_td touchdowns per world: (xp_att, xp_made, tp_att, tp_made)."""
    n_td = np.asarray(n_td, int)
    tp = rng.binomial(n_td, kr['try_rate_2pt_per_td'])
    tpm = rng.binomial(tp, kr['two_pt_success'])
    xpa = n_td - tp
    xpm = rng.binomial(xpa, kr['pat_make_rate'])
    return xpa, xpm, tp, tpm


def field_goals(latent, off_td, xpm_off, tpm_off, kr, rng):
    """kicker_world.draw's measured remainder rule (nfl/tools/kicker_world.py:211-212) on the world's latent points,
    with the 2021-2024 fg_share; made FGs are split over distance bands by the 2021-2024 league made mix."""
    rem = np.asarray(latent, float) - 6 * off_td - xpm_off - 2 * tpm_off
    fg = np.maximum(0, np.rint(kr['fg_share'] * rem / 3.0)).astype(int)
    mix = np.array([kr['made_band_mix'][b] for b, _, _ in FG_BANDS])
    bands = rng.multinomial(fg, mix / mix.sum())
    return fg, bands, rem


@functools.lru_cache(maxsize=None)
def _frozen():
    _require(FROZEN.exists(), 'EL_FROZEN_ABSENT', str(FROZEN))
    return json.loads(FROZEN.read_text())


def event_rates():
    return _frozen()['event_rates']


class ELState:
    """Everything the event-linked stages carry for one game: offence ledgers, defensive counts and placements,
    fixed offensive tries and FGs, latent points (driver only, never a total)."""

    def __init__(self, spec, inc0, rates, seed):
        _require(inc0 and inc0.get('players') and inc0.get('club_worlds'), 'EL_EMPTY_INPUT', 'no incumbent raw draw')
        spec_ = {'clubs': spec['clubs']}
        guard_no_market(spec_['clubs'][0]['players'], 'EL spec players')
        guard_no_market(spec_['clubs'][1]['players'], 'EL spec players')
        guard_no_market(rates, 'EL event rates')
        self.spec, self.rates = spec_, rates
        self.order = [c['club'] for c in spec['clubs']]
        self.n = len(inc0['club_points'][self.order[0]])
        _require(self.n > 0, 'EL_EMPTY_INPUT', 'zero worlds')
        self.rng = np.random.default_rng(seed)
        self.acct = collections.Counter()
        self.latent = {t: np.asarray(inc0['club_points'][t], float) for t in self.order}
        self.comp = {t: np.asarray(inc0['dst_comp'][t], float) for t in self.order}
        self.off = {}
        for c in spec['clubs']:
            t = c['club']
            S10 = np.stack([inc0['players'][p['id']] for p in c['players']])
            self.off[t] = offense_block(c, S10, inc0['club_worlds'][t], inc0['club_td'][t], self.rng, self.acct)
        kr = rates['kicker']
        self.counts = {}
        for t in self.order:
            sk, ta = self.comp[t][:, 0].astype(int), self.comp[t][:, 1].astype(int)
            ints = self.rng.binomial(ta, rates['p_int_of_takeaway'])
            self.counts[t] = {'sacks': sk, 'ints': ints, 'fumbles': ta - ints,
                              'dst_td': self.comp[t][:, 2].astype(int), 'safeties': self.comp[t][:, 3].astype(int)}
        self.off_tries, self.fg = {}, {}
        for t in self.order:
            otd = self.off_td(t)
            xpa, xpm, tp, tpm = tries(otd, kr, self.rng)
            self.off_tries[t] = (xpa, xpm, tp, tpm)
            fg, bands, rem = field_goals(self.latent[t], otd, xpm, tpm, kr, self.rng)
            self.fg[t] = (fg, bands)
            self.acct['club_worlds_latent_remainder_negative'] += int((rem < 0).sum())
        self.place_defense()

    def off_td(self, t):
        return np.array([int(W['ptd'].sum() + W['rtd'].sum()) for W in self.off[t]['worlds']])

    def place_defense(self):
        """Place every DST's events on the opposing offence and draw the tries after D/ST TDs."""
        self.dfn, self.dst_tries = {}, {}
        for t in self.order:
            o = self.other(t)
            c = self.counts[t]     # t's DST against o's offence
            self.dfn[o] = defense_block(self.off[o], c, c['dst_td'], c['safeties'], self.rates, self.rng, self.acct)
        kr = self.rates['kicker']
        for t in self.order:
            d = self.dfn[self.other(t)]
            self.dst_tries[t] = {'def': tries(d['opp_def_td'], kr, self.rng), 'st': tries(d['opp_st_td'], kr, self.rng)}

    def other(self, t):
        return self.order[1] if t == self.order[0] else self.order[0]

    def bundle(self, stage, scored=False):
        clubs, ledgers = {}, {}
        team = {}
        for t in self.order:
            o = self.other(t)
            off, d_on_t = self.off[t], self.dfn[t]
            L = assemble_ledger(off, d_on_t)
            ledgers[t] = L
            S = INV.ledger_aggregate(L, off['P'], self.n)
            mine = self.dfn[o]            # t's own D/ST scoring sits in the block placed on o's offence
            xpa, xpm, tp, tpm = self.off_tries[t]
            dx = self.dst_tries[t]
            fg, bands = self.fg[t]
            otd = self.off_td(t)
            def_td, st_td, sf = mine['opp_def_td'], mine['opp_st_td'], mine['opp_safeties']
            XPA = xpa + dx['def'][0] + dx['st'][0]
            XPM = xpm + dx['def'][1] + dx['st'][1]
            TPA = tp + dx['def'][2] + dx['st'][2]
            TPM = tpm + dx['def'][3] + dx['st'][3]
            pts = 6 * (otd + def_td + st_td) + XPM + 2 * TPM + 3 * fg + 2 * sf
            sk_t = np.zeros(self.n)
            sky = np.zeros(self.n)
            m = L['kind'] == K_SACK
            np.add.at(sk_t, L['world'][m], 1.0)
            np.add.at(sky, L['world'][m], -L['yards'][m])
            gross = S[..., INV.PX['pass_yards']].sum(0)
            team[t] = {'points': pts.astype(float), 'off_td': otd.astype(float), 'def_td': def_td, 'st_td': st_td,
                       'dst_td': def_td + st_td, 'safeties': sf,
                       'def_td_conv_points': (dx['def'][1] + 2 * dx['def'][3]).astype(float),
                       'pass_att': S[..., INV.PX['pass_att']].sum(0),
                       'rush_att': S[..., INV.PX['carries']].sum(0),
                       'throwaways': np.array([float((W['receiver'] < 0).sum()) for W in off['worlds']]),
                       'sacks_taken': sk_t, 'sack_yards': sky, 'net_pass_yards': gross - sky}
            kick = {'xp_att': XPA.astype(float), 'xp_made': XPM.astype(float), 'tp_att': TPA.astype(float),
                    'tp_made': TPM.astype(float), 'fg_made': fg.astype(float)}
            for j, (b, _, _) in enumerate(FG_BANDS):
                kick[b] = bands[:, j].astype(float)
            kick['dk'] = kick['xp_made'] + sum(INV.FG_BAND_POINTS[b] * kick[b] for b, _, _ in FG_BANDS)
            clubs[t] = {'ids': [p['id'] for p in self.spec['clubs'][self.order.index(t)]['players']],
                        'pos': off['pos'], 'S': S, 'team': team[t], 'kicker': kick, 'dk': None}
        for t in self.order:
            o = self.other(t)
            Lo = ledgers[o]
            cnt = lambda mask: np.bincount(Lo['world'][mask], minlength=self.n).astype(float)
            ints = cnt(Lo['int'])
            fr = cnt(Lo['fumble'])
            pa = team[o]['points'] - 6 * team[o]['def_td'] - team[o]['def_td_conv_points'] - 2 * team[o]['safeties']
            tier = INV.dk_tier(pa)
            dst = {'sacks': cnt(Lo['kind'] == K_SACK), 'ints': ints, 'fum_rec': fr, 'takeaways': ints + fr,
                   'def_td': team[t]['def_td'], 'st_td': team[t]['st_td'], 'dst_td': team[t]['dst_td'],
                   'safeties': team[t]['safeties'], 'pa': pa, 'tier': tier}
            dst['dk'] = (tier + dst['sacks'] + 2 * ints + 2 * fr + 6 * (dst['def_td'] + dst['st_td'])
                         + 2 * dst['safeties'])
            clubs[t]['dst'] = dst
            if scored:
                clubs[t]['dk'] = {'core': INV.dk_core(clubs[t]['S']), 'classic': INV.dk_classic(clubs[t]['S'])}
        return {'provider': 'EVENT_LINKED', 'stage': stage, 'n': self.n, 'order': list(self.order), 'clubs': clubs,
                'ledger': ledgers}

    # ------------------------------------------------------------------ S1: efficiency per event
    def apply_efficiency(self, pools_game):
        """Per-EVENT efficiency: each completion's yards x the receiver's factor, each carry's x the rusher's.
        Factor = classic_slate_run's formula (line 113) on this ledger's own simulated opportunities."""
        b0 = self.bundle('tmp')
        fac = {}
        for ci, t in enumerate(self.order):
            cs = self.spec['clubs'][ci]
            S = b0['clubs'][t]['S']
            pool = {CE.player_key(p['pid'], t): p for p in pools_game[t]['players']}
            fr, fu = np.ones(len(cs['players'])), np.ones(len(cs['players']))
            for i, p in enumerate(cs['players']):
                row = pool.get(p['id'])
                cv = (row or {}).get('eff') or {}
                for fld, opp, arr, src in (('rec_yards', 'targets', fr, 'targets'), ('rush_yards', 'carries', fu, 'carries')):
                    sim_y = float(S[i, :, INV.PX[fld]].sum())
                    sim_o = float(S[i, :, INV.PX[opp]].sum())
                    ty, to = cv.get(fld), cv.get(src)
                    if (isinstance(ty, (int, float)) and isinstance(to, (int, float)) and to > 0 and ty >= 0
                            and sim_o >= MIN_SIM_OPPORTUNITIES and sim_y > 0):
                        arr[i] = (ty / to) / (sim_y / sim_o)
            fac[t] = {'rec': fr, 'rush': fu}
            for W in self.off[t]['worlds']:
                m = W['complete']
                W['pyards'] = np.where(m, W['pyards'] * fr[np.clip(W['receiver'], 0, None)], W['pyards'])
                W['ryards'] = W['ryards'] * fu[W['rusher']] if len(W['rusher']) else W['ryards']
        self.efficiency_factors = {t: {k: [round(float(x), 4) for x in v] for k, v in f.items()} for t, f in fac.items()}
        return self.efficiency_factors

    # ------------------------------------------------------------------ S2: DST level on event rates
    def apply_dst_rates(self, multipliers, band_means_, band_edges, seed):
        """Thin (m <= 1) or superpose (m > 1) each DST event process, then re-place the defensive events.
        multipliers: {dst club: {'sacks', 'ints', 'fumbles', 'dst_td', 'safeties': m}}."""
        rng = np.random.default_rng(seed)
        self.rng = rng
        p_int = self.rates['p_int_of_takeaway']
        for t in self.order:
            o = self.other(t)
            lat_o = self.latent[o]
            bi = np.array([_band_index(x, band_edges) for x in lat_o])
            bm = np.asarray(band_means_, float)[bi]           # (n, 4): sacks, takeaways, dst_td, safeties
            lam = {'sacks': bm[:, 0], 'ints': bm[:, 1] * p_int, 'fumbles': bm[:, 1] * (1 - p_int),
                   'dst_td': bm[:, 2], 'safeties': bm[:, 3]}
            new = {}
            for k, x in self.counts[t].items():
                m = float((multipliers.get(t) or {}).get(k, 1.0))
                x = np.asarray(x, int)
                if m <= 1.0:
                    new[k] = rng.binomial(x, max(0.0, m))
                else:
                    new[k] = x + rng.poisson((m - 1.0) * lam[k])
            self.counts[t] = new
        self.place_defense()
        return {t: dict(multipliers.get(t) or {}) for t in self.order}


def _band_index(points_allowed, edges):
    for i, (lo, hi) in enumerate(edges):
        if lo <= points_allowed < hi:
            return i
    return len(edges) - 1


def band_table(fits):
    """(edges, means) in the order DstModel uses (sorted by lower edge)."""
    items = []
    for k, v in fits['dst_bands']['bands'].items():
        lo, hi = (float(x) for x in k.split('-'))
        items.append((lo, hi, np.asarray(v['empirical_tuples'], float).mean(0)))
    items.sort()
    return [(lo, hi) for lo, hi, _ in items], [m.tolist() for _, _, m in items]


def dst_multipliers(rates_tbl, clubs, week):
    """Per DST club: blended event rate (dst_model.club_rates form: current season weeks < W, prior season at
    PRIOR_GAMES pseudo-games) over the league's same blend. Missing or non-positive -> 1.0, named."""
    from nfl.tools import dst_model as DM
    cur, prv = rates_tbl['cur'], rates_tbl['prv']
    cur = cur[cur.week < week]
    keys = {'sacks': 'sacks', 'ints': 'ints', 'fumbles': 'fumrec', 'dst_td': 'dtd', 'safeties': 'safeties'}
    teams = sorted(set(cur.team) | (set(prv.team) if prv is not None else set()))

    def blend(team, col):
        c = cur[cur.team == team][col]
        p = prv[prv.team == team][col] if prv is not None else c.iloc[0:0]
        pc = float(c.mean()) if len(c) else None
        pp = float(p.mean()) if len(p) else None
        if pc is None and pp is None:
            return None
        return pp if pc is None else pc if pp is None else (len(c) * pc + DM.PRIOR_GAMES * pp) / (len(c) + DM.PRIOR_GAMES)
    out, named = {}, {}
    for k, col in keys.items():
        vals = [v for v in (blend(tm, col) for tm in teams) if v is not None]
        lg = float(np.mean(vals)) if vals else None
        for t in clubs:
            b = blend(t, col)
            if b is None or lg is None or lg <= 0:
                out.setdefault(t, {})[k] = 1.0
                named.setdefault(t, []).append(f'{k}: no rate')
            else:
                out.setdefault(t, {})[k] = b / lg
    return out, named


def el_to_world(b):
    """An EVENT_LINKED bundle in the clean harness's world format (10 stat fields) for its scoring functions."""
    w = {'players': {}, 'club_points': {}, 'club_td': {}, 'dst_dk': {}}
    for t in b['order']:
        cb = b['clubs'][t]
        for i, k in enumerate(cb['ids']):
            w['players'][k] = np.stack([cb['S'][i, :, INV.PX[f]] for f in CE.STAT_FIELDS], 1)
        w['club_points'][t] = cb['team']['points']
        w['club_td'][t] = cb['team']['off_td']
        w['dst_dk'][t] = cb['dst']['dk']
    return w


# ================================================================================================ one game
def game_worlds(model, spec, vol, pools_game, fits, rates, multipliers, band_edges, band_means_, dst_targets, n, seed):
    """Every stage of both providers for one game, and the invariant results per stage."""
    inc0 = simulate_incumbent(model, spec, vol, n, seed)
    inc1 = CE.stage_efficiency(inc0, pools_game, fits['int_rate']['int_per_attempt'], seed + 99)
    inc1['club_worlds'] = inc0['club_worlds']
    inc2 = CE.stage_dst_anchor(inc1, dst_targets)
    kr = rates['kicker']
    kick = {t: incumbent_kicker(inc0['club_points'][t], inc0['club_td'][t], kr, seed + KICKER_SEED_OFFSET + i)
            for i, t in enumerate(c['club'] for c in spec['clubs'])}
    ib = {'S0_raw': incumbent_bundle(inc0, spec, 'S0_raw', kick, 'raw'),
          'S1_after_efficiency': incumbent_bundle(inc1, spec, 'S1_after_efficiency', kick, 'classic'),
          'S2_after_dst': incumbent_bundle(inc2, spec, 'S2_after_dst', kick, 'classic'),
          'S3_after_scoring': incumbent_bundle(inc2, spec, 'S3_after_scoring', kick, 'classic')}
    st = ELState(spec, inc0, rates, seed + EL_SEED_OFFSET)
    eb = {'S0_raw': st.bundle('S0_raw')}
    el_raw_world = el_to_world(eb['S0_raw'])
    st.apply_efficiency(pools_game)
    eb['S1_after_efficiency'] = st.bundle('S1_after_efficiency')
    st.apply_dst_rates(multipliers, band_means_, band_edges, seed + S2_SEED_OFFSET)
    eb['S2_after_dst'] = st.bundle('S2_after_dst')
    eb['S3_after_scoring'] = st.bundle('S3_after_scoring', scored=True)
    inv = {'INCUMBENT': {s: INV.check_bundle(b) for s, b in ib.items()},
           'EVENT_LINKED': {s: INV.check_bundle(b) for s, b in eb.items()}}
    worlds = {'INCUMBENT_PROD': inc2, 'INCUMBENT_RAW': inc0, 'EVENT_LINKED': el_to_world(eb['S3_after_scoring']),
              'EVENT_LINKED_RAW': el_raw_world}
    return worlds, inv, st, eb


# ================================================================================================ scoring panel
CLUB_VARS = CE.CLUB_VARS + ('dst_dk_dkpa',)
PLAYER_VARS = CE.PLAYER_VARS
ROLES = CE.ROLES


def actual_dst_dkpa(frames, gid, club, opp):
    """DST DK under DK_PA_v1 on the ACTUAL game: the opponent's points minus its takeaway-return TDs, the tries after
    them and its safeties; components as sc_coh_1_measure.dst_games counts them."""
    fin = frames['fin'].set_index('game_id').loc[gid]
    opts = float(fin.hs if opp == fin.home else fin.as_)
    so = frames['scoring'].get((gid, opp), collections.Counter())
    pa = opts - 6 * so.get('td_DEF', 0) - so.get('xp_made_def', 0) - 2 * so.get('tp_made_def', 0) - 2 * so.get('safeties', 0)
    d = frames['dst'].set_index(['game_id', 'team']).loc[(gid, club)]
    return float(INV.dk_tier(pa) + d.sacks + 2 * d.ints + 2 * d.fumrec + 6 * d.dtd + 2 * d.safeties)


def score_phase(phase, season, weeks, fr, fprev, tgc, table, rates_tbl, model, fits, rates, n_worlds, limit_games):
    pools, excl = CE.build_pools(fr['pg'], fr['sched'], POOL, weeks=set(weeks), prev_pg=fprev['pg'])
    pgi = fr['pg'].set_index(['game_id', 'team', 'pid'])
    cf = json.loads(CE.FROZEN.read_text())
    sc = cf['scales']
    vec_sd = np.array([sc['pts']['sd'], sc['pts']['sd']] + [sc[r]['sd'] for r in ROLES] * 2)
    events = {'team_pts_ge_p90': ('pts', sc['pts']['p90']), 'team_off_td_ge_p90': ('off_td', sc['off_td']['p90']),
              **{f'{r}_dk_ge_p90': (r, sc[r]['p90']) for r in ROLES}}
    edges, means = band_table(fits)
    games = [g for g in fr['sched'].sort_values('game_id').itertuples(index=False)
             if int(g.week) in weeks and (g.game_id, g.home) in pools and (g.game_id, g.away) in pools]
    if limit_games:
        games = games[:limit_games]
    _require(len(games) > 0, 'EL_EMPTY_INPUT', f'{phase}: no scorable game in weeks {weeks}')
    unit_rows, joint_rows, brier_rows = [], [], []
    inv_acc = {'INCUMBENT': collections.defaultdict(list), 'EVENT_LINKED': collections.defaultdict(list)}
    coh_ss = {v: {} for v in VARIANTS + ('HISTORY',)}
    refused, acct, mult_log = [], collections.Counter(), {}
    eff_gap = collections.defaultdict(list)
    rng_pit = np.random.default_rng(PIT_SEED)
    pa_res = fits['football_residuals']['pa_res']
    for gi, g in enumerate(games):
        c = CE.football_centre(table, g.home, g.away, season, int(g.week))
        if c is None:
            refused.append({'game_id': g.game_id, 'reason': 'NO_FOOTBALL_CENTRE'})
            continue
        spec = CE.game_spec(g, pools, c)
        vol = {t: CE.volume_centre(tgc, t, season, int(g.week)) for t in (g.home, g.away)}
        if any(v is None for v in vol.values()):
            refused.append({'game_id': g.game_id, 'reason': 'NO_VOLUME_CENTRE'})
            continue
        pg2 = {g.home: pools[(g.game_id, g.home)], g.away: pools[(g.game_id, g.away)]}
        opp_c = {g.home: c['away_expected'], g.away: c['home_expected']}
        dtg = {t: CE.dst_target(rates_tbl, t, int(g.week), opp_c[t], pa_res) for t in (g.home, g.away)}
        mult, named = dst_multipliers(rates_tbl, (g.home, g.away), int(g.week))
        mult_log[g.game_id] = {'multipliers': {t: {k: round(v, 4) for k, v in m.items()} for t, m in mult.items()},
                               'left_at_1': named}
        seed = SIM_SEED + gi
        try:
            worlds, inv, st, eb = game_worlds(model, spec, vol, pg2, fits, rates, mult, edges, means, dtg, n_worlds, seed)
        except ELError as e:
            # the incumbent refused the game, or its raw draw cannot be re-expressed as events: refused for BOTH
            if e.code not in ('EL_INCUMBENT_REFUSED', 'EL_INCUMBENT_VOLUME_NOT_RECONCILED'):
                raise
            refused.append({'game_id': g.game_id, 'reason': e.code, 'detail': str(e)[:240]})
            continue
        acct.update(st.acct)
        for who in inv:
            for s_, r in inv[who].items():
                inv_acc[who][s_].append(r)
        # QB centre drift: event-linked QB passing yards vs the QB's own pooled yards per attempt
        for ci, t in enumerate((g.home, g.away)):
            cb = eb['S3_after_scoring']['clubs'][t]
            pool = {CE.player_key(p['pid'], t): p for p in pg2[t]['players']}
            for i, k in enumerate(cb['ids']):
                if cb['pos'][i] != 'QB':
                    continue
                e = pool[k]['eff']
                att = cb['S'][i, :, INV.PX['pass_att']].mean()
                if e['pass_attempts'] > 0 and att >= 10:
                    eff_gap['qb_pass_yards_el_minus_row_ypa_x_att'].append(
                        float(cb['S'][i, :, INV.PX['pass_yards']].mean() - att * e['pass_yards'] / e['pass_attempts']))
        # ---- actuals
        act_club = {t: CE.club_actuals(fr, g.game_id, t, None) for t in (g.home, g.away)}
        for t, o in ((g.home, g.away), (g.away, g.home)):
            act_club[t]['dst_dk_dkpa'] = actual_dst_dkpa(fr, g.game_id, t, o)
        role_ids = [(t, pools[(g.game_id, t)]['roles'][r]) for t in (g.home, g.away) for r in ROLES]
        vec_ok = all(pid is not None for _, pid in role_ids)
        yv = None
        if vec_ok:
            yv = np.array([act_club[g.home]['team_points'], act_club[g.away]['team_points']]
                          + [float(CE.dk_core_arr(CE.actual_stat_row(pgi, g.game_id, t, pid))) for t, pid in role_ids]) / vec_sd
        hist_unit = CE._history_unit_rows(fr, g, pools, pgi, act_club)
        CE._acc_coh(coh_ss['HISTORY'], hist_unit, g.game_id)
        for vname, w in worlds.items():
            for sc_ in spec['clubs']:
                t = sc_['club']
                sims = CE.club_sim(w, sc_)
                sims['dst_dk_dkpa'] = sims['dst_dk']
                for var in CLUB_VARS:
                    unit_rows.append(CE._score_unit(vname, g, 'club_' + var, np.asarray(sims[var], float)[None, :],
                                                    np.array([act_club[t][var]]), rng_pit))
                for p in sc_['players']:
                    S = w['players'][p['id']]
                    a = CE.actual_stat_row(pgi, g.game_id, t, p['pid'])
                    for var, (fn, poss) in PLAYER_VARS.items():
                        if poss is not None and p['position'] not in poss:
                            continue
                        unit_rows.append(CE._score_unit(vname, g, 'player_' + var, fn(S)[None, :],
                                                        np.array([float(fn(a))]), rng_pit))
            CE._acc_coh(coh_ss[vname], CE._sim_unit_rows(w, spec, pools, g), g.game_id)
            if vec_ok:
                cols = [np.asarray(w['club_points'][g.home], float), np.asarray(w['club_points'][g.away], float)]
                cols += [CE.dk_core_arr(w['players'][CE.player_key(pid, t)]) for t, pid in role_ids]
                X = np.stack(cols, 1) / vec_sd
                joint_rows.append((vname, g.game_id, int(g.week), CE.energy_score(X, yv), CE.variogram_score(X, yv),
                                   X.shape[1]))
            for ev, (col, thr) in events.items():
                for t in (g.home, g.away):
                    if col == 'pts':
                        s_, y = np.asarray(w['club_points'][t], float), act_club[t]['team_points']
                    elif col == 'off_td':
                        s_, y = np.asarray(w['club_td'][t], float), act_club[t]['team_off_td']
                    else:
                        pid = pools[(g.game_id, t)]['roles'][col]
                        if pid is None:
                            continue
                        s_ = CE.dk_core_arr(w['players'][CE.player_key(pid, t)])
                        y = float(CE.dk_core_arr(CE.actual_stat_row(pgi, g.game_id, t, pid)))
                    pr = float((s_ >= thr - 1e-9).mean())
                    brier_rows.append((vname, g.game_id, int(g.week), ev, (pr - float(y >= thr - 1e-9)) ** 2))
    return summarise_phase(phase, games, refused, excl, unit_rows, joint_rows, brier_rows, inv_acc, coh_ss,
                           cf['equivalence_margins'], acct, mult_log, eff_gap)


def summarise_phase(phase, games, refused, excl, unit_rows, joint_rows, brier_rows, inv_acc, coh_ss, margins, acct,
                    mult_log, eff_gap):
    ref_ids = {r['game_id'] for r in refused}
    gl = [g.game_id for g in games if g.game_id not in ref_ids]
    _require(len(gl) > 0, 'EL_EMPTY_INPUT', f'{phase}: every game refused')
    weeks = {g.game_id: int(g.week) for g in games}
    Wb = CE._boot_weights(gl, weeks, np.random.default_rng(BOOT_SEED))
    gi = {g: i for i, g in enumerate(gl)}
    U = pd.DataFrame(unit_rows, columns=['variant', 'game_id', 'week', 'var', 'crps', 'ls', 'ls_valid', 'floored',
                                         'pit', 'c50', 'c80', 'c90'])
    _require(len(U) > 0, 'EL_EMPTY_INPUT', 'no scored units')

    def per_game(df, col):
        out = {}
        for v, x in df.groupby('variant'):
            s, n = np.zeros(len(gl)), np.zeros(len(gl))
            ix = x.game_id.map(gi).to_numpy()
            np.add.at(s, ix, x[col].to_numpy(float))
            np.add.at(n, ix, 1.0)
            out[v] = (s, n)
        return out
    marg = {}
    for var, x in U.groupby('var'):
        r = {'crps': {}, 'coverage': {}, 'pit': {}, 'log_score': {}}
        for a, b in PAIRS:
            r['crps'].update(CE.summarise_metric(per_game(x, 'crps'), gl, weeks, Wb, a, b))
        for lv, col in zip(CE.LEVELS, ('c50', 'c80', 'c90')):
            r['coverage'][str(lv)] = CE.summarise_metric(per_game(x, col), gl, weeks, Wb, *PRIMARY_PAIR)
        for v, z in x.groupby('variant'):
            h = np.histogram(z.pit.to_numpy(), bins=CE.PIT_BINS, range=(0, 1))[0]
            r['pit'][v] = {'histogram': h.tolist(), 'n': int(h.sum()),
                           'sum_abs_bin_dev_from_uniform': round(float(np.abs(h / h.sum() - 1 / CE.PIT_BINS).sum()), 4)}
        lsv = {v: bool(z.ls_valid.all()) for v, z in x.groupby('variant')}
        r['log_score']['support_valid'] = lsv
        lsx = x[x.variant.isin([v for v, ok in lsv.items() if ok])]
        if len(lsx):
            for a, b in PAIRS:
                if lsv.get(a) and lsv.get(b):
                    r['log_score'].update(CE.summarise_metric(per_game(lsx, 'ls'), gl, weeks, Wb, a, b))
            r['log_score']['n_floored'] = {v: int(z.floored.sum()) for v, z in lsx.groupby('variant')}
        marg[var] = r
    J = pd.DataFrame(joint_rows, columns=['variant', 'game_id', 'week', 'es', 'vs', 'd'])
    joint = {}
    if len(J):
        for col in ('es', 'vs'):
            joint[col] = {}
            for a, b in PAIRS:
                joint[col].update(CE.summarise_metric(per_game(J, col), gl, weeks, Wb, a, b))
    B = pd.DataFrame(brier_rows, columns=['variant', 'game_id', 'week', 'event', 'brier'])
    brier = {}
    for ev, x in B.groupby('event'):
        brier[ev] = {}
        for a, b in PAIRS:
            brier[ev].update(CE.summarise_metric(per_game(x, 'brier'), gl, weeks, Wb, a, b))
    inv = {who: INV.summarise(st) for who, st in inv_acc.items()}
    decision = primary_decision(inv['EVENT_LINKED'], joint, marg)
    return {'phase': phase, 'n_games_scored': len(gl), 'n_games_considered': len(games), 'games_refused': refused,
            'club_games_excluded_missing_input': excl, 'invariant_counts_per_stage': inv,
            'invariant_totals_per_stage': {who: {s: INV.total_violations(r) for s, r in st.items()} for who, st in inv.items()},
            'event_linked_accounting': dict(acct), 'marginal': marg, 'joint': joint, 'brier_tail_events': brier,
            'coherence_vs_history': coherence_summary(coh_ss, gl, Wb, margins),
            'qb_centre_drift': {k: {'n': len(v), 'mean': round(float(np.mean(v)), 3),
                                    'sd': round(float(np.std(v)), 3)} for k, v in eff_gap.items()},
            'dst_rate_multipliers': mult_log, 'primary_decision': decision}


def coherence_summary(ss, games, Wb, margins):
    out = {}
    for name, x, y, kind, meaning in M.STATS:
        H = np.stack([ss['HISTORY'][name][g] for g in games])
        hv = float(M._stat(H.sum(0), kind))
        row = {'meaning': meaning, 'history': round(hv, 4), 'equivalence_margin': margins[name]['margin']}
        for v in VARIANTS:
            S = np.stack([ss[v][name][g] for g in games])
            sv = float(M._stat(S.sum(0), kind))
            r = {'value': round(sv, 4), 'gap': round(sv - hv, 4)}
            inside = True
            for blk in ('game', 'week'):
                d = M._stat(Wb[blk] @ S, kind) - M._stat(Wb[blk] @ H, kind)
                r[f'gap_ci95_{blk}_block'] = CE._ci(d)
                c90 = CE._ci(d, 5, 95)
                r[f'gap_ci90_{blk}_block'] = c90
                m = margins[name]['margin']
                inside = inside and c90 is not None and (-m < c90[0]) and (c90[1] < m)
            r['label'] = 'WITHIN_PREDECLARED_EQUIVALENCE_MARGIN_TOST' if inside else 'NOT_SHOWN_EQUIVALENT'
            row[v] = r
        out[name] = row
    return out


def required_invariants(stage):
    """Every registered invariant is required of the event-linked world at every stage, except the DK
    recomputations, which exist only once DK is scored (S3)."""
    return [k for k in INV.INVARIANTS if stage == 'S3_after_scoring' or k not in ('S01', 'S02')]


def primary_decision(el_inv, joint, marg):
    """Pre-registered rule: (a) AND (b) AND (c). Labels only; nothing is promoted."""
    a, b = PRIMARY_PAIR
    key = f'{a}_vs_{b}'
    res = {}
    bad, unrep = {}, {}
    for s_ in STAGES:
        st = el_inv.get(s_) or {}
        for k in required_invariants(s_):
            r = st.get(k) or {'state': 'NOT_REPRESENTED'}
            if r['state'] != 'CHECKED':
                unrep.setdefault(s_, []).append(k)
            elif r['violations']:
                bad.setdefault(s_, {})[k] = r['violations']
    res['A_zero_invariant_violations_every_stage'] = {
        'test': 'hard requirement', 'violations': bad, 'required_but_not_checked': unrep,
        'stages_present': [s_ for s_ in STAGES if s_ in el_inv],
        'passed': not bad and not unrep and all(s_ in el_inv for s_ in STAGES)}

    def upper(r, blk):
        c = r.get(f'ratio_ci95_{blk}_block') if r else None
        return c[1] if c else None
    for name, r in (('B1_player_dk_crps', marg.get('player_dk', {}).get('crps', {}).get(key)),
                    ('B2_team_points_crps', marg.get('club_team_points', {}).get('crps', {}).get(key)),
                    ('C1_energy_score', (joint.get('es') or {}).get(key)),
                    ('C2_variogram_score', (joint.get('vs') or {}).get(key))):
        ups = [upper(r, blk) for blk in ('game', 'week')]
        ok = all(u is not None and u < NI_RATIO_MARGIN for u in ups)
        res[name] = {'test': 'non-inferiority', 'ratio': (r or {}).get('ratio'),
                     'ratio_ci95_game_block': (r or {}).get('ratio_ci95_game_block'),
                     'ratio_ci95_week_block': (r or {}).get('ratio_ci95_week_block'),
                     'ratio_upper95_game_block': ups[0], 'ratio_upper95_week_block': ups[1],
                     'margin': NI_RATIO_MARGIN, 'passed': ok}
    res['ALL_PRIMARY_PASSED'] = all(v['passed'] for v in res.values() if isinstance(v, dict))
    res['READING'] = ('conjunctive: (a) zero violations of every registered invariant at every event-linked stage, '
                      '(b) player-DK and team-points CRPS ratio (event-linked / incumbent production stage) upper 95% '
                      'bound < 1.02 under BOTH game- and week-blocked bootstraps, (c) energy and variogram score ratios '
                      'likewise < 1.02. 1.02 is a declared value judgement reused from the SC-COH-1 registration. '
                      'Passing is a SHADOW label; it promotes nothing. Failing to show non-inferiority is not evidence '
                      'of inferiority.')
    return res


# ================================================================================================ phases
def code_sha():
    h = hashlib.sha256()
    for p in (pathlib.Path(__file__), pathlib.Path(INV.__file__)):
        h.update(p.read_bytes())
    return h.hexdigest()


def check_phase_preconditions(phase, phases, csha, n_worlds, limit_games):
    _require(phase in ('development', 'confirmation'), 'EL_PHASE', phase)
    _require('confirmation' not in phases, 'EL_CONFIRMATION_ALREADY_READ',
             'the 2026 confirmation weeks have been scored once; no further scoring of either phase is allowed')
    if phase == 'confirmation':
        _require('development' in phases, 'EL_NO_DEVELOPMENT_RUN', 'run development first')
        _require(phases['development']['code_sha256'] == csha, 'EL_CODE_CHANGED_SINCE_DEVELOPMENT',
                 'the harness changed after the last development run; re-run development before confirmation')
        _require(n_worlds == N_WORLDS and limit_games is None, 'EL_CONFIRMATION_NOT_AS_REGISTERED',
                 'confirmation runs only the registered design')
    return True


def _open_gate(phase):
    _GATE.update(phase=phase, limits={DEV_SEASON: max(DEV_WEEKS)} if phase == 'development'
                 else {DEV_SEASON: 99, CONF_SEASON: max(CONF_WEEKS)})


def _close_gate():
    _GATE.update(phase=None, limits={})


def run_phase(phase, n_worlds=N_WORLDS, limit_games=None):
    lk = verify_prereg()
    _clean_frozen_verified()
    fz = _frozen()
    _require(hashlib.sha256(_canon(fz['event_rates'])).hexdigest() == fz['event_rates_sha256'], 'EL_FROZEN_CHANGED',
             'event rates hash')
    csha = code_sha()
    prior = json.loads(OUT.read_text()) if OUT.exists() else {}
    phases = prior.get('phases') or {}
    check_phase_preconditions(phase, phases, csha, n_worlds, limit_games)
    fits = compute_fits()
    rates = fz['event_rates']
    _require(measure_event_rates() == rates, 'EL_FITS_NOT_REPRODUCED', 'event rates differ from the frozen ones')
    model = CE.build_incumbent_model(fits)
    attempts = list(phases.get('confirmation_attempts') or [])
    if phase == 'confirmation':
        attempts.append({'started_at': _now(), 'code_sha256': csha, 'status': 'STARTED'})
        phases['confirmation_attempts'] = attempts
        OUT.write_text(json.dumps(compose_output(phases, lk), indent=1, default=float))
    season, weeks = (DEV_SEASON, DEV_WEEKS) if phase == 'development' else (CONF_SEASON, CONF_WEEKS)
    _open_gate(phase)
    try:
        tg = load_team_game()
        table = CE.points_table(tg)
        tgc = CE.tg_by_club_season(tg)
        fr = season_frames(season)
        fprev = season_frames(season - 1)
        rates_tbl = CE.dst_rates_table(season, fr, fprev)
        res = {'phase': phase, 'season': season, 'weeks': list(weeks), 'prereg_sha256': lk['prereg_sha256'],
               'frozen_sha256': lk['frozen_sha256'], 'code_sha256': csha, 'n_worlds': n_worlds,
               'limit_games': limit_games, 'started_at': _now()}
        res['result'] = score_phase(phase, season, weeks, fr, fprev, tgc, table, rates_tbl, model, fits, rates,
                                    n_worlds, limit_games)
        res['finished_at'] = _now()
    finally:
        _close_gate()
    if phase == 'development':
        res['development_run_number'] = int((phases.get('development') or {}).get('development_run_number', 0)) + 1
    else:
        attempts[-1]['status'] = 'COMPLETED'
        attempts[-1]['finished_at'] = res['finished_at']
        res['attempt_number'] = len(attempts)
    phases[phase] = res
    doc = compose_output(phases, lk)
    OUT.write_text(json.dumps(doc, indent=1, default=float))
    return doc


def dry_run_in_sample(season=CUTOFF, weeks=(10, 11), n_worlds=40, limit_games=3):
    """PIPELINE SMOKE TEST on an IN-SAMPLE season (<= 2024, gate closed). Not evidence; never written."""
    _require(season <= CUTOFF and not _GATE['limits'], 'EL_DRY_RUN_NOT_IN_SAMPLE', str(season))
    fits = compute_fits()
    rates = _frozen()['event_rates'] if FROZEN.exists() else measure_event_rates()
    model = CE.build_incumbent_model(fits)
    tg = load_team_game()
    fr, fprev = season_frames(season), season_frames(season - 1)
    return score_phase('dry_run', season, tuple(weeks), fr, fprev, CE.tg_by_club_season(tg), CE.points_table(tg),
                       CE.dst_rates_table(season, fr, fprev), model, fits, rates, n_worlds, limit_games)


# ================================================================================================ output
ROOT_CAUSE_MAP = [
    {'id': 'R1', 'where': 'nfl/tools/classic_slate_run.py:106-124 (efficiency_worlds), called at '
                          'showdown_slate_run.py:90 and classic_slate_run.py:273',
     'what': ('per player and per field, f = (projected yards / projected opportunities) / (simulated yards / '
              'simulated opportunities) (line 113); line 124 multiplies the passer\'s pass yards by HIS factor and each '
              'receiver\'s receiving yards by HIS OWN factor, independently'),
     'identity_broken': 'QB passing yards == sum of receiving yards (C01)',
     'why': ('the passer and the receivers are the two ends of the SAME completions, but the step scales the two ends '
             'by unrelated numbers, so the sums can only agree by accident'),
     'measured_clean_eval': 'club_qb_pass_yards_ne_sum_rec_yards 0 at S0 -> 106,879 of 108,800 club-worlds at S1'},
    {'id': 'R2', 'where': 'nfl/tools/classic_slate_run.py:125-126',
     'what': 'interceptions drawn Binomial(round(world pass attempts), int_rate) per QB with a fresh random.Random',
     'identity_broken': 'opposing QB interceptions == DST interceptions (D01; weak form D01W <= takeaways)',
     'why': ('the DST\'s takeaways were already fixed in the same world by nfl/sim/game.py:323 -> dst.py:241-253; '
             'the redraw never reads them, so one football event is counted twice, independently'),
     'measured_clean_eval': 'club_opp_qb_ints_gt_dst_takeaways 25,965 of 108,800'},
    {'id': 'R3', 'where': 'nfl/tools/showdown_slate_run.py:94-95 and classic_slate_run.py:276-277 -> '
                          'classic_slate_run.anchor_means:133-153 (line 150)',
     'what': 'every DST DK draw multiplied by target / simulated mean',
     'identity_broken': 'DST DK == tier(points allowed) + sacks + 2 x takeaways + 6 x TD + 2 x safeties (D10)',
     'why': ('the total is rescaled after the fact while its components (and the opponent\'s points that set the tier) '
             'stay as drawn; a multiplicative change of a sum of integer-weighted events is not a sum of events'),
     'measured_clean_eval': 'club_dst_dk_ne_tier_plus_components 0 at S1 -> 104,113 at S2'},
    {'id': 'R4', 'where': 'nfl/sim/game.py:472 (yards split over targets), 515 (receptions Binomial), 483-490 (TD '
                          'allocation by shares, ghost bucket), 301-316 and 360-361 (continuous points, TD inversion), '
                          'no sack draw anywhere',
     'what': ('receptions, receiving yards and receiving TDs are three independent allocations of the same targets; '
              'rushing TDs are allocated by rush_td_share with an unattributed remainder; points are a continuous '
              'draw and TDs an inversion of it'),
     'identity_broken': 'P02, P03, P04, C05, C06, C07; sacks unreconcilable (D02 not representable)',
     'why': 'the raw simulator reconciles VOLUMES to club totals but never ties yards / TDs to the catch or carry '
            'they happened on, and never builds points from scoring events',
     'measured_clean_eval': ('rec yards without reception 103,757 player-worlds; rec TD > receptions 28,733; rush TD > '
                             'carries 6,960; team TD != pass + rush TD 3,633; points not integer 107,308; points < 6 x '
                             'TD 3,773')},
    {'id': 'R5', 'where': 'nfl/tools/kicker_world.py:204-212',
     'what': 'kicker FG count = round(fg_share x (points - 6 TD - XP - 2 x 2pt) / 3), floored at 0',
     'identity_broken': 'team points == 6 TD + XP + 2 x 2pt + 3 x FG + 2 x safeties (C06)',
     'why': 'the remainder is taken from a continuous points draw that is not an event sum, so it is negative in some '
            'worlds and never closes exactly; the FG count reconciles with nothing',
     'measured_clean_eval': 'club_kicker_remainder_negative_if_every_xp_good 15,319'},
]

DESIGN = {
    'choice': 'TRANSFORMATION of the incumbent\'s raw draw into event ledgers (not a new generator)',
    'why': ('one change at a time. The incumbent\'s volume engine (football centre, plays / pass-share response, '
            'Dirichlet-multinomial shares, volume reconciliation to the projection, the DST\'s empirical joint tuples '
            'conditioned on the same world\'s points) is kept exactly, with the same seeds, so any score difference is '
            'attributable to the accounting repair and its declared re-expressions, not to a different forecaster. '
            'A new generator would confound the two.'),
    'events': {
        'pass attempt': '(world, passer, intended receiver or throwaway, complete, yards if complete, TD flag, INT flag, '
                        'fumble flag + fumbler)',
        'sack': '(world, passer, -yards lost, fumble flag); not a pass attempt',
        'carry': '(world, rusher, yards, TD flag, fumble flag)',
        'scoreboard': 'per club-world: offensive TDs (from the ledger), takeaway-return TDs and return TDs and '
                      'safeties (the club\'s DST tuple), tries after every TD, FGs by band',
    },
    're_expressions_declared': [
        'passer of each attempt: a random permutation of the incumbent\'s per-QB attempt counts',
        'intended receiver: a random permutation of the incumbent\'s per-receiver targets plus throwaways',
        'which of a receiver\'s targets were caught: uniform among them, count = the incumbent\'s receptions',
        'receiving yards of a receiver with zero receptions are moved to catching teammates in proportion to their '
        'own yards (club passing yards preserved); within a receiver, yards are split over his catches by a flat '
        'Dirichlet (no per-catch model is claimed)',
        'receiving TDs: the incumbent\'s count per receiver, capped at his receptions, on random catches; the excess '
        'goes to free catches by pass-TD share; a passing TD with no free catch moves to rushing',
        'rushing: the same rules on carries; the incumbent\'s unattributed (ghost) rushing TDs are placed on free '
        'carries uniformly; a TD with no free event is dropped and counted',
        'sacks / INT / fumbles lost on an offence = the opposing DST\'s incumbent tuple (sacks, takeaways); takeaways '
        'split INT vs fumble by the 2021-2024 share; INT on an incomplete attempt (uniform); fumble location by the '
        '2021-2024 shares (carry / reception / sack), never on a TD play',
        'the defending club\'s D/ST TDs: a takeaway return with the 2021-2024 probability if a free takeaway exists, '
        'else a kick / punt return',
        'tries after every TD (2021-2024 rates per TD); FGs by kicker_world\'s remainder rule on the incumbent\'s '
        'latent points (a driver, never a total); bands by the 2021-2024 league made mix',
    ],
    'efficiency_stage': ('per event, the receiver\'s / rusher\'s production factor; QB passing yards are the sum of the '
                         'scaled completions, so the QB\'s own yards-per-attempt row is NOT applied (it would scale '
                         'the same yards twice); its drift is reported as qb_centre_drift'),
    'dst_stage': ('the post-draw multiplicative anchor is removed. Level enters as event-process intensity: '
                  'm = club blended rate / league blended rate (dst_model.club_rates form, PRIOR_GAMES pseudo-games), '
                  'thinning when m <= 1, superposition of Poisson((m - 1) x band mean) when m > 1, per event type '
                  '(sacks, INT, fumbles lost, D/ST TD, safeties); events re-placed; points, PA, tier and DK recomputed'),
    'scoring_stage': 'DK core (pre-registered panel score) and DK classic computed from the reconciled stat lines only',
    'coefficients': ('2021-2024 measurements in EVENT_LINKED_FROZEN.json, the SC-COH-1 clean <= 2024 refits '
                     '(SC_COH_1_CLEAN_FROZEN.json, hash-verified), and production constants named in code '
                     '(MIN_SIM_OPPORTUNITIES 30, PRIOR_GAMES, DK scoring tables). No constant was chosen on 2025 or 2026.'),
}

CONVENTIONS = {
    'SACK_YARDS': 'sack yards reduce team NET passing yards, not the passer\'s gross passing yards (official stat)',
    'DK_PA_v1': ('DST points allowed = opponent points minus its takeaway-return TDs, their tries and its safeties; '
                 'opponent kick / punt-return TDs count (DraftKings rule text: external-research/.../'
                 'nfl-full-product-research-packet.pplx.md:344; nfl/dfs/salaries/postgame/FINDINGS_2026W4_STANDINGS.md F1)'),
    'ALL_PASSERS': 'passing identities sum over every player with an attempt',
    'TWO_POINT': 'a 2pt conversion is a try, not a TD / target / carry; DK\'s +2 to the player is NOT_REPRESENTED',
    'LATERAL / OFFENSIVE_FUMBLE_RECOVERY_TD': 'history-only exceptions; a simulated world may not claim them',
    'KICKOFF_RETURN_TD_NOT_REPRESENTED': ('dst.build counts D/ST TDs as td_team == defteam, which excludes kickoff '
                                          'returns (posteam is the receiving team on kickoffs); the event-linked world '
                                          'inherits that omission from the incumbent\'s tuples'),
    'BLOCKED_KICK_AND_XP_RETURN_NOT_REPRESENTED': 'DK +2 items for blocked kicks and try returns are not drawn',
}


def contamination_audit():
    A = list(CE.contamination_audit())
    for r in A:
        r['side'] = {'CANDIDATE': 'NOT_USED_HERE (SC-COH-1 candidate)'}.get(r['side'], r['side'])

    def row(name, source, cutoff, market, outcome, pit, note=''):
        A.append({'side': 'EVENT_LINKED', 'input': name, 'source': source, 'cutoff': cutoff, 'market_derived': market,
                  'outcome_derived': outcome, 'point_in_time': pit, 'note': note})
    row('INT share of takeaways, fumble location shares, sack yards, D/ST TD return share',
        'clean pbp (whitelisted columns) 2021-2024', '2021-2024', 'NO', 'YES (<= 2024 fit)', 'YES')
    row('tries per TD, 2pt success, PAT make rate, fg_share, FG band mix', 'clean pbp 2021-2024, kicker_world.measure '
        'definitions with tries typed by TD', '2021-2024', 'NO', 'YES (<= 2024 fit)', 'YES',
        'production KICKER_WORLD.json measures 2021-2025 and is not read')
    row('DST event-rate multipliers', 'sc_coh_1_measure.dst_games per-game events, dst_model blend', 'eval season weeks '
        '< W + prior season', 'NO', 'prior-game outcomes only', 'YES', 'the production DST anchor target\'s own inputs')
    row('band means for superposition', 'the incumbent\'s <= 2024 DST tuples', '2021-2024', 'NO', 'YES (<= 2024 fit)',
        'YES')
    return A


def confirmation_integrity():
    """Was 2026 touched by any SC-COH-1 / coherence harness? Read the sources; report what they say."""
    rep = {}
    for p in sorted(HERE.glob('*.py')):
        if p.name in ('event_linked_world.py', 'invariants.py'):
            continue
        src = p.read_text()
        seasons = sorted({int(x) for x in __import__('re').findall(r'\b(20[12]\d)\b', src) if 2020 <= int(x) <= 2026})
        rep[p.name] = {'mentions_2026': '2026' in src,
                       'eval_or_season_constants': [l.strip()[:120] for l in src.splitlines()
                                                    if __import__('re').match(r'\s*(EVAL_SEASON|CUTOFF|LIB_SEASONS|'
                                                                              r'FIT_SEASONS|SEASONS|PBP_SEASONS)\s*=', l)],
                       'season_literals': seasons}
    return {'harness_sources': rep,
            'READING': ('every earlier coherence harness pins EVAL_SEASON = 2025 and fits <= 2024; 2026 appears only in '
                        'comments and date stamps, never as a season read. 2026 weeks 1-3 HAVE been read by the '
                        'production postgame grading (nfl/research/postgame/week2_*), not by any coherence study; no '
                        'design choice here was made on 2026 outcomes. The production artifacts SHARED_STATE '
                        '(2000-2026) and EFFICIENCY (2021-2026) contain 2026 rows; they are NOT read (<= 2024 refits).'),
            'confirmation_file': {'path': CONF_PBP, 'sha256': CONF_PBP_SHA256, 'weeks_present': [1, 2, 3],
                                  'week_4': 'NO play-by-play capture; TEAM_GAME 2026 week 4 points are null; only a '
                                            'player-week box (nfl/postgame/raw/2026W4) exists, which carries no '
                                            'scoring-event or DST attribution: INSUFFICIENT for this endpoint set'}}


def compose_output(phases, lk):
    fz = _frozen()
    return {
        'ARTIFACT': 'EVENT_LINKED_WORLD', 'STATUS': 'SHADOW_ONLY', 'LAYER': 'RESEARCH',
        'NOT_PROMOTED': 'nothing here is on the production path; no production file was changed',
        'EVIDENCE_CLASS': {
            'development (2025 weeks 2-18)': ('DEVELOPMENT_ONLY: 2025 has been read three or more times by SC-COH-1 '
                                              'work; no claim rests on it'),
            'confirmation (2026 weeks 2-3)': ('RETROSPECTIVE_CONFIRMATORY_SHADOW: read once after the lock; untouched '
                                              'by any coherence harness; small (at most 32 games), past, not '
                                              'prospective'),
        },
        'AUDIT_LADDER': {'reached': ['IMPLEMENTED', 'SUCCESS_TESTED', 'REFUSAL_TESTED', 'ADVERSARIAL_TESTED',
                                     'PRE_REGISTERED_EVALUATION_RUN'],
                         'NOT': ['ON_EXECUTION_PATH', 'PROSPECTIVELY_VALIDATED', 'PROMOTED'],
                         'tests': 'nfl/tests/test_event_linked_world.py'},
        'ROOT_CAUSE_MAP': ROOT_CAUSE_MAP, 'DESIGN': DESIGN, 'DECLARED_CONVENTIONS': CONVENTIONS,
        'INVARIANTS': {k: {'scope': s, 'meaning': m} for k, (s, m) in INV.INVARIANTS.items()},
        'prereg': {'path': lk['prereg'], 'sha256': lk['prereg_sha256'], 'locked_at': lk['locked_at']},
        'frozen': {'path': lk['frozen'], 'sha256': lk['frozen_sha256'], 'clean_frozen_sha256': lk['clean_frozen_sha256'],
                   'event_rates_summary': {k: v for k, v in fz['event_rates'].items() if k != 'sack_yards_lost_empirical'}},
        'contamination_audit': contamination_audit(),
        'confirmation_set_integrity': confirmation_integrity(),
        'deviations_after_lock': DEVIATIONS,
        'phases': phases,
        'WHAT_A_PRODUCTION_CHANGE_WOULD_INVOLVE': WHAT_A_PRODUCTION_CHANGE_WOULD_INVOLVE,
        'LIMITATIONS': LIMITATIONS,
        'written_at': _now(),
    }


WHAT_A_PRODUCTION_CHANGE_WOULD_INVOLVE = {
    'STATUS': 'NOT DONE. Listed so a decision has a concrete scope; nothing here is a recommendation to promote.',
    'steps': [
        'owner decision first: the confirmation set is small and the registration is a shadow label, not a promotion '
        'gate; a prospective (forward-chained 2026 weeks >= 5) shadow run of the same registration would come first',
        'nfl/sim/game.py: emit the event ledger (or call this transform) behind a declared arm so the default '
        'simulate_game is unchanged; the incumbent identities in verify() stay',
        'nfl/tools/classic_slate_run.py:efficiency_worlds: replace per-player independent factors with per-event '
        'factors; remove the Binomial INT redraw (INTs come from the DST-linked ledger)',
        'nfl/tools/showdown_slate_run.py:94-95 and classic_slate_run.py:276-277: remove anchor_means for DST; apply '
        'the club multipliers to event intensities before placement',
        'nfl/tools/kicker_world.py: FGs and tries as ledger events; team points = event sum; kicker DK from events',
        'graders (classic_week.actual_points and the postgame DST grader): DK_PA_v1 points allowed (F1 of '
        'FINDINGS_2026W4_STANDINGS.md)',
        'invariants.check_bundle as a hard stage gate after every step (refuse, never repair)',
        'replace the production artifacts\' 2021-2025 fits with a documented refit cutoff and re-run the suite',
        'a separate registration and a new holdout; this study\'s confirmation weeks may not be reused',
    ],
}

LIMITATIONS = [
    'the confirmation set is 2026 weeks 2-3 only (<= 32 games, minus refusals); intervals are wide and a failure to '
    'show non-inferiority there is a statement about sample size as much as about the model',
    'the replay is the clean harness\'s, not the full live path: season-to-date shares, opportunity-share TD shares, '
    'pooled efficiency rows; no proj_v1, football_sanity or role_state (SC_COH_1_CLEAN_EVAL differences_from_live_path)',
    'INT / fumble / sack events have no effect on drives or on the offence\'s scoring beyond the incumbent tuple\'s '
    'conditioning on the same world\'s points; there is no drive model',
    'within-player yards per catch / carry are a flat Dirichlet split; no per-catch distribution is claimed; '
    'negative-yardage plays are not generated',
    'kickoff-return TDs, blocked kicks, try returns and 2pt player credit are NOT_REPRESENTED (declared)',
    'kickers are not in the scored pools; only their accounting identities are checked',
    'DK core (no bonuses / INT / fumble) is the pre-registered player score, as in SC-COH-1; DK classic is computed '
    'and invariant-checked but not scored',
    'official actives / inactives remain NOT_IDENTIFIABLE_FROM_CURRENT_DATA (docs/AGENT_OUTBOX.md 2026-10-07)',
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['freeze', 'lock', 'dry-run', 'run'])
    ap.add_argument('--phase', choices=['development', 'confirmation'])
    ap.add_argument('--n-worlds', type=int, default=N_WORLDS)
    ap.add_argument('--limit-games', type=int)
    a = ap.parse_args(argv)
    if a.cmd == 'freeze':
        d = freeze()
        print(FROZEN.relative_to(_REPO), d['event_rates_sha256'])
        print(json.dumps({k: v for k, v in d['event_rates'].items() if k != 'sack_yards_lost_empirical'}, indent=1))
    elif a.cmd == 'lock':
        print(json.dumps(lock(), indent=1))
    elif a.cmd == 'dry-run':
        r = dry_run_in_sample(n_worlds=a.n_worlds if a.n_worlds != N_WORLDS else 40, limit_games=a.limit_games or 3)
        print(json.dumps({'n': r['n_games_scored'], 'totals': r['invariant_totals_per_stage'],
                          'decision': r['primary_decision']}, indent=1, default=float)[:6000])
    else:
        _require(a.phase, 'EL_PHASE', '--phase is required')
        d = run_phase(a.phase, a.n_worlds, a.limit_games)
        r = d['phases'][a.phase]['result']
        print(OUT.relative_to(_REPO), 'games', r['n_games_scored'])
        print(json.dumps({'totals': r['invariant_totals_per_stage'], 'decision': r['primary_decision']}, indent=1,
                         default=float)[:6000])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
