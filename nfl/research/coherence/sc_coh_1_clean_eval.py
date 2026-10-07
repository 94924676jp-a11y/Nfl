#!/usr/bin/env python3.12
"""SC-COH-1 CLEAN comparison: incumbent vs analogue-library candidate on FOOTBALL-ONLY, POINT-IN-TIME inputs,
everything fitted <= 2024, pre-registered before any 2025 score.

    python3.12 nfl/research/coherence/sc_coh_1_clean_eval.py freeze          # <= 2024 only; writes FROZEN
    python3.12 nfl/research/coherence/sc_coh_1_clean_eval.py lock            # hashes the prereg + FROZEN
    python3.12 nfl/research/coherence/sc_coh_1_clean_eval.py run --phase development
    python3.12 nfl/research/coherence/sc_coh_1_clean_eval.py run --phase confirmation    # ONE read only

LAYER: RESEARCH / SHADOW_ONLY. Imports production modules read-only (nfl/sim/game.py, nfl/sim/football_points.py,
nfl/sim/variance_components.py, nfl/sim/usage.py, nfl/sim/dst.py, nfl/tools/classic_slate_run.py,
nfl/tools/dst_model.py, nfl/warehouse/stats.py) and calls their PURE functions on inputs this module loads itself.
It never calls a production build() and writes ONLY files under nfl/research/coherence/ whose names start with
SC_COH_1_CLEAN_.

WHY THIS EXISTS. The first SC-COH-1 pass (sc_coh_1_measure.py / sc_coh_1_candidate.py, SC_COH_1_MEASUREMENT.json)
is DEVELOPMENT EVIDENCE ONLY for three verified reasons:
  (1) the candidate chose analogue games by nearest SPORTSBOOK total_line / spread_line -- market information may
      never enter the proprietary forecast, so that candidate is ineligible for production;
  (2) the evaluation pool was players with offense_snaps > 0 IN THE EVALUATED GAME -- outcome-derived;
  (3) the incumbent's inputs (SHARED_STATE 2000-2026, EFFICIENCY 2021-2026, ...) include 2025, and it was replayed
      on market lines rather than production's FOOTBALL_ONLY arm.
This module repairs all three:
  * SCORING CENTRE = production's own FOOTBALL_ONLY centre, nfl/sim/football_points.expected_points (own-offence
    blend, current season weeks < W + prior season at 4 pseudo-games), computed from a TEAM_GAME table this module
    loads through a column WHITELIST (points / season / week / club / home flag only). Residuals around it are
    re-measured by football_points' own procedure through 2024 instead of 2025.
  * INCUMBENT = nfl/sim/game.py:simulate_game_centred (production's Showdown call) on a Model whose every fitted
    input (volume response, scoring, efficiency, concentrations, teammate concentration, DST bands) is REFITTED by
    the production procedures on <= 2024 rows, then classic_slate_run.efficiency_worlds, then anchor_means (DST),
    the live transform order.
  * CANDIDATE = the analogue-game play library, neighbours chosen on the SAME football centre (total, home margin),
    library 2021-2024, share concentration re-estimated on 2024 with POINT-IN-TIME pools.
  * POOL = players who recorded a target, carry or pass attempt for the club in an EARLIER week of the same season.
    No snap or outcome of the evaluated game enters it. Official actives / inactives are NOT_IDENTIFIABLE from
    committed data (request: docs/AGENT_OUTBOX.md, 2026-10-07 nflverse weekly rosters and inactives).
Every input source passes guard_no_market(); every fit filters season <= CUTOFF; the 2025 season can be read only
after verify_prereg() has matched docs/NFL_SC_COH_1_CLEAN_EVAL_PREREGISTRATION.md to its lock.

NOTHING HERE IS A VERDICT ON PRODUCTION. Labels are those the pre-registration defines; "matched", "validated",
"correct" and "unbiased" are never written by this module.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import functools
import hashlib
import json
import math
import pathlib
import re
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.coherence import sc_coh_1_candidate as C  # noqa: E402  (pure helpers only)
from nfl.research.coherence import sc_coh_1_measure as M  # noqa: E402  (pure helpers only)

HERE = pathlib.Path(__file__).resolve().parent
PREREG = _REPO / 'docs/NFL_SC_COH_1_CLEAN_EVAL_PREREGISTRATION.md'
FROZEN = HERE / 'SC_COH_1_CLEAN_FROZEN.json'
LOCK = HERE / 'SC_COH_1_CLEAN_PREREG_LOCK.json'
OUT = HERE / 'SC_COH_1_CLEAN_EVAL.json'
TG_PATH = _REPO / 'nfl/warehouse/TEAM_GAME.json'
PG_PATH = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
RH_PATH = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'

# ------------------------------------------------------------------------------------------------ frozen design
CUTOFF = 2024                       # nothing after this season is fitted
EVAL_SEASON = 2025
DEV_WEEKS = tuple(range(2, 10))     # development: pipeline debugging only; no model choice is made on it
CONF_WEEKS = tuple(range(10, 19))   # confirmation: read once, after everything is frozen
LIB_SEASONS = (2021, 2022, 2023, 2024)
CONC_SEASON = 2024
SCALE_SEASON = 2024                 # normalisation scales and tail thresholds
MARGIN_SEASONS = (2021, 2022, 2023, 2024)
FP_FIRST_FIT_SEASON = 2001          # == football_points.FIRST_FIT_SEASON
N_WORLDS = 400
SIM_SEED = 20261008
N_BOOT = 2000
BOOT_SEED = 20261009
PIT_SEED = 20261010
PIT_BINS = 10
NI_RATIO_MARGIN = 1.02              # candidate mean score at most 2% worse than incumbent (declared value judgement)
LEVELS = (0.5, 0.8, 0.9)
VS_P = 0.5
POOL_MODES = ('SEASON_TO_DATE', 'LAST_GAME')
PRIMARY_POOL = 'SEASON_TO_DATE'
VARIANTS = ('INCUMBENT_PROD', 'INCUMBENT_RAW', 'CANDIDATE_RAW', 'CANDIDATE_POST')
PRIMARY_PAIR = ('CANDIDATE_RAW', 'INCUMBENT_PROD')
ROLES = ('QB', 'RB1', 'WR1', 'WR2', 'TE1')
STAT_FIELDS = ('pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td',
               'targets', 'receptions', 'rec_yards', 'rec_td')
SX = {f: i for i, f in enumerate(STAT_FIELDS)}

#: A column or key is MARKET-DERIVED if its lower-cased name contains any of these tokens. Deliberately broad:
#: a false refusal is a visible error, a false admission is a silent contamination.
MARKET_TOKENS = ('line', 'odds', 'moneyline', 'implied', 'spread', 'vegas', 'vig', 'juice', 'price',
                 'sportsbook', 'book', 'market', 'wager', 'bet')
#: Whitelists: the ONLY columns each source may contribute.
PBP_CLEAN_COLS = ['game_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'home_team', 'away_team',
                  'play_type', 'passer_player_id', 'receiver_player_id', 'rusher_player_id', 'passing_yards',
                  'receiving_yards', 'rushing_yards', 'complete_pass', 'pass_attempt', 'sack', 'pass_touchdown',
                  'rush_touchdown', 'interception', 'fumble_lost', 'td_team', 'safety', 'two_point_attempt',
                  'home_score', 'away_score', 'touchdown', 'return_touchdown']
TG_FIELDS = ('game_id', 'club', 'opponent', 'season', 'week', 'is_home', 'points', 'points_allowed',
             'pass_attempts', 'rush_attempts', 'targets', 'offensive_td', 'margin', 'sacks', 'turnovers')
PG_FIELDS = ('player_id', 'club', 'game_id', 'season', 'week', 'targets', 'receiving_yards', 'carries',
             'rushing_yards', 'pass_attempts', 'passing_yards')
RH_FIELDS = ('player_id', 'season', 'week', 'position', 'measure', 'depth_rank')


#: Every change to this harness made AFTER the pre-registration lock, with its reason. A change that is not a bug
#: fix (a new metric, a different pool, a tuned constant) is not allowed here at all; it needs a new registration.
DEVIATIONS: list = [
    {'when': '2026-10-07, after the lock, during the FIRST confirmation attempt',
     'what': ('the first confirmation run crashed (ValueError in conservation(): ragged draw arrays) before writing '
              'anything; no confirmation metric was written to disk or displayed. Cause: a player who appeared '
              'earlier in the season for BOTH clubs of a game (a mid-season trade between opponents) was keyed by his '
              'player id alone, so the two clubs\' draws for him merged. No development game had such a player, so '
              'the development numbers were unaffected.'),
     'fix': ('draws are keyed by "<player id>|<club>" (game_spec), and actual stats / efficiency rows are looked up '
             'by (club, player id). A bug fix only: no model, pool, metric, margin or seed changed.'),
     'procedure': ('per the registration, development was re-run with the fixed code (same seeds; its numbers must '
                   'reproduce), then confirmation was run once with that code. Every confirmation attempt is now '
                   'recorded in confirmation_attempts before any 2025 week >= 10 row is read.')},
]


#: The one confirmation attempt made before attempt logging existed (see DEVIATIONS[0]).
PRE_LOGGING_ATTEMPT = {'started_at': 'after 2026-10-07T07:24:20Z (development run 1 finished)',
                       'finished_at': '2026-10-07T07:28:52Z (crash; log mtime)', 'status': 'CRASHED_NOTHING_WRITTEN',
                       'code_sha256': 'a1fbf3eeb4bdfef9e1fccc267433de8f1a76491e705715ec90bb382fe12d4046',
                       'note': 'ValueError in conservation(); see DEVIATIONS[0]'}


class CleanEvalError(RuntimeError):
    """A named refusal. An empty, partial or contaminated input is never a result."""

    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}')
        self.code = code


def _require(ok, code, detail=''):
    if not ok:
        raise CleanEvalError(code, detail)


def _sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _sha(p):
    return _sha_bytes(pathlib.Path(p).read_bytes())


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), default=float).encode()


# ================================================================================================ guards
def is_market_name(name) -> bool:
    n = str(name).lower()
    return any(t in n for t in MARKET_TOKENS)


def guard_no_market(obj, where: str):
    """Refuse SC_COH_1_CLEAN_MARKET_INPUT if any column / key of `obj` is market-derived.
    DataFrame: columns. dict-of-rows or list-of-dicts: every row's keys. dict: its keys (recursively one level)."""
    names = set()
    if isinstance(obj, pd.DataFrame):
        names |= set(obj.columns)
    elif isinstance(obj, dict):
        names |= set(obj)
        for v in obj.values():
            if isinstance(v, dict):
                names |= set(v)
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                for r in v:
                    names |= set(r)
    elif isinstance(obj, (list, tuple)):
        for r in obj:
            if isinstance(r, dict):
                names |= set(r)
    bad = sorted(str(n) for n in names if is_market_name(n))
    _require(not bad, 'SC_COH_1_CLEAN_MARKET_INPUT', f'{where}: market-derived field(s) {bad}')
    return obj


#: The 2025 evaluation season is unreadable until verify_prereg() opens this gate with the phase's week limit.
_GATE = {'open': False, 'max_week': 0, 'phase': None}


def _season_allowed(season: int, where: str):
    if season <= CUTOFF:
        return
    _require(_GATE['open'] and season == EVAL_SEASON, 'SC_COH_1_CLEAN_EVAL_SEASON_LOCKED',
             f'{where}: season {season} read before the pre-registration was verified (or not the eval season)')


# ================================================================================================ loaders
@functools.lru_cache(maxsize=None)
def _pbp_raw(season: int) -> pd.DataFrame:
    df = pd.read_csv(M.pbp_path(season), usecols=lambda c: c in PBP_CLEAN_COLS, low_memory=False)
    return df


def load_pbp_clean(season: int) -> pd.DataFrame:
    """REG-season play-by-play, whitelisted columns only. 2025 only through the gate, truncated to its week limit."""
    _season_allowed(season, f'pbp {season}')
    df = _pbp_raw(season)
    _require(set(PBP_CLEAN_COLS) <= set(df.columns), 'SC_COH_1_CLEAN_SCHEMA',
             f'pbp {season} lacks {sorted(set(PBP_CLEAN_COLS) - set(df.columns))}')
    df = df[df.season_type == 'REG'].copy()
    if season > CUTOFF:
        df = df[df.week <= _GATE['max_week']].copy()
    guard_no_market(df, f'pbp {season}')
    _require(len(df) > 500, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'pbp {season} has {len(df)} REG rows')
    _require(int(df.season.min()) == int(df.season.max()) == season, 'SC_COH_1_CLEAN_SEASON_MISMATCH',
             f'pbp file for {season} carries {sorted(df.season.unique())}')
    return df


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def whitelist_rows(rows, fields) -> list:
    """Project every row onto `fields`. Whatever else a row carries (total_line, club_spread, implied_total,
    moneyline ...) is dropped here, before anything can read it."""
    _require(not any(is_market_name(f) for f in fields), 'SC_COH_1_CLEAN_MARKET_INPUT', f'whitelist {fields}')
    return [{k: r.get(k) for k in fields} for r in rows]


@functools.lru_cache(maxsize=None)
def _tg_raw():
    a = json.loads(TG_PATH.read_text())
    rows = a['rows'] if isinstance(a['rows'], list) else list(a['rows'].values())
    return tuple(whitelist_rows(rows, TG_FIELDS))


def load_team_game() -> list:
    """TEAM_GAME club-game rows, whitelisted fields only (no total_line / club_spread / implied / moneyline).
    Seasons <= CUTOFF, plus 2025 rows at weeks <= the gate's limit once the gate is open."""
    out = []
    for r in _tg_raw():
        s = r.get('season')
        if s is None or r.get('week') is None:
            continue
        s, w = int(s), int(r['week'])
        if s > CUTOFF and not (_GATE['open'] and s == EVAL_SEASON and w <= _GATE['max_week']):
            continue
        out.append(dict(r))
    guard_no_market(out, 'TEAM_GAME')
    _require(len(out) > 1000, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'TEAM_GAME has {len(out)} usable rows')
    return out


@functools.lru_cache(maxsize=None)
def _rows_of(path):
    a = json.loads(pathlib.Path(path).read_text())
    return a['rows'] if isinstance(a['rows'], list) else list(a['rows'].values())


def load_player_game() -> list:
    out = whitelist_rows([r for r in _rows_of(str(PG_PATH)) if r.get('season') is not None
                          and int(r['season']) <= CUTOFF], PG_FIELDS)
    guard_no_market(out, 'PLAYER_GAME')
    _require(len(out) > 1000, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'PLAYER_GAME has {len(out)} rows <= {CUTOFF}')
    return out


def load_role_history() -> list:
    out = whitelist_rows([r for r in _rows_of(str(RH_PATH)) if r.get('season') is not None
                          and int(r['season']) <= CUTOFF], RH_FIELDS)
    guard_no_market(out, 'ROLE_HISTORY')
    _require(len(out) > 1000, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'ROLE_HISTORY has {len(out)} rows <= {CUTOFF}')
    return out


def _fit_rows(rows):
    """Every fit sees season <= CUTOFF only, whatever it is handed. This is what makes 2025 removal a no-op."""
    return [r for r in rows if r.get('season') is not None and int(r['season']) <= CUTOFF]


# ================================================================================================ football centre
def points_table(tg_rows) -> dict:
    """{club: {season: {week: points}}} -- football_points.club_points_table on whitelisted rows."""
    from nfl.sim import football_points as FP
    guard_no_market(tg_rows, 'points_table')
    rows = [r for r in tg_rows if r.get('points') is not None and r.get('club')]
    _require(len(rows) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', 'no points rows for the football centre')
    return FP.club_points_table(rows)


def football_centre(table, home, away, season, week):
    """Production's FOOTBALL_ONLY centre (football_points.centre_for_game), point-in-time by construction:
    expected_points reads weeks < `week` of `season` and the whole of `season - 1`."""
    from nfl.sim import football_points as FP
    return FP.centre_for_game(home, away, season, week, table=table)


def fit_football_residuals(tg_rows) -> dict:
    """football_points.build()'s residual procedure with THROUGH_SEASON = CUTOFF. Never writes FOOTBALL_POINTS."""
    from nfl.sim import football_points as FP
    rows = [r for r in _fit_rows(tg_rows) if r.get('points') is not None]
    guard_no_market(rows, 'fit_football_residuals')
    table = points_table(rows)
    games = collections.defaultdict(dict)
    for r in rows:
        games[r['game_id']][r['club']] = r
    tot, mar, pa = [], [], []
    for gid, sides in games.items():
        if len(sides) != 2:
            continue
        a, b = sides.values()
        if a.get('is_home') is None or int(a['season']) < FP_FIRST_FIT_SEASON:
            continue
        home, away = (a, b) if a['is_home'] else (b, a)
        eh, _ = FP.expected_points(table, home['club'], int(home['season']), int(home['week']))
        ea, _ = FP.expected_points(table, away['club'], int(away['season']), int(away['week']))
        if eh is None or ea is None:
            continue
        tot.append((home['points'] + away['points']) - (eh + ea))
        mar.append((home['points'] - away['points']) - (eh - ea))
        for side, opp_e in ((home, ea), (away, eh)):
            if _num(side.get('points_allowed')) is not None:
                pa.append(float(side['points_allowed']) - opp_e)
    _require(len(tot) >= 1000, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'{len(tot)} games for football residuals')
    return {'fit_seasons': [FP_FIRST_FIT_SEASON, CUTOFF], 'n_games': len(tot),
            'total_res': sorted(round(x, 3) for x in tot), 'margin_res': sorted(round(x, 3) for x in mar),
            'pa_res': sorted(round(x, 3) for x in pa),
            'total_sd': round(float(np.std(tot)), 4), 'margin_sd': round(float(np.std(mar)), 4),
            'margin_mean_home_field': round(float(np.mean(mar)), 4), 'pa_sd': round(float(np.std(pa)), 4)}


# ================================================================================================ incumbent refit
def fit_shared_state(tg_rows) -> dict:
    """shared_state.build()'s plays/pass-share, realised-volume and scoring regressions on <= CUTOFF rows.
    DECLARED DIFFERENCE: production keeps a club-game only if it also carries total_line and club_spread; the clean
    refit cannot read those columns, so that market-availability filter is dropped."""
    from nfl.warehouse import stats
    rows = _fit_rows(tg_rows)
    guard_no_market(rows, 'fit_shared_state')
    v = []
    for r in rows:
        pa_, ra_, pts, mg = (_num(r.get(k)) for k in ('pass_attempts', 'rush_attempts', 'points', 'margin'))
        if None in (pa_, ra_, pts, mg) or pa_ + ra_ <= 0:
            continue
        v.append({'game_id': r['game_id'], 'pass_attempts': pa_, 'rush_attempts': ra_, 'points': pts,
                  'margin': mg, 'plays': pa_ + ra_, 'pass_share': pa_ / (pa_ + ra_)})
    _require(len(v) >= 400, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'{len(v)} club-games for the volume response')

    def fit(rs, y, xs):
        o = stats.ols(rs, y, xs, cluster='game_id')
        _require(o['state'] == 'FITTED', 'SC_COH_1_CLEAN_FIT_FAILED', f'{y}: {o.get("reason")}')
        return o
    plays_form, realised = {}, {}
    for y in ('plays', 'pass_share'):
        o = fit(v, y, ['points', 'margin'])
        plays_form[y] = {'intercept': round(o['coef']['intercept'], 5), 'per_own_point': round(o['coef']['points'], 6),
                         'per_margin_point': round(o['coef']['margin'], 6), 'residual_sd': round(o['rmse'], 5),
                         'n': o['n']}
    for y in ('pass_attempts', 'rush_attempts'):
        o = fit(v, y, ['points', 'margin'])
        realised[y] = {'intercept': round(o['coef']['intercept'], 4), 'per_own_point': round(o['coef']['points'], 4),
                       'per_margin_point': round(o['coef']['margin'], 4), 'residual_sd': round(o['rmse'], 4),
                       'n': o['n']}
    td = [{'game_id': r['game_id'], 'points': float(r['points']), 'td': float(r['offensive_td'])}
          for r in rows if _num(r.get('offensive_td')) is not None and _num(r.get('points')) is not None]
    o = fit(td, 'points', ['td'])
    scoring = {'points_per_offensive_td': round(o['coef']['td'], 4),
               'points_not_from_offensive_td': round(o['coef']['intercept'], 4), 'residual_sd': round(o['rmse'], 4),
               'n': o['n']}
    seasons = sorted({int(r['season']) for r in rows if _num(r.get('pass_attempts')) is not None})
    return {'plays_form': plays_form, 'realised': realised, 'scoring': scoring,
            'volume_seasons': [min(seasons), max(seasons)]}


def fit_efficiency(pg_rows) -> dict:
    """game.fit_efficiency()'s club-game yards per attempt / per carry on <= CUTOFF rows. Never writes EFFICIENCY."""
    rows = _fit_rows(pg_rows)
    agg = collections.defaultdict(lambda: {'att': 0.0, 'pyd': 0.0, 'car': 0.0, 'ryd': 0.0})
    for r in rows:
        a = agg[(r['game_id'], r['club'])]
        for src, d in (('pass_attempts', 'att'), ('passing_yards', 'pyd'), ('carries', 'car'), ('rushing_yards', 'ryd')):
            x = _num(r.get(src))
            if x is not None:
                a[d] += x
    ypa = sorted(round(a['pyd'] / a['att'], 4) for a in agg.values() if a['att'] >= 15)
    ypc = sorted(round(a['ryd'] / a['car'], 4) for a in agg.values() if a['car'] >= 10)
    _require(len(ypa) >= 200 and len(ypc) >= 200, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'{len(ypa)} / {len(ypc)} club-games')
    seasons = sorted({int(r['season']) for r in rows})
    return {'ypa': ypa, 'ypc': ypc, 'seasons': [min(seasons), max(seasons)]}


def fit_variance_components(pg_rows) -> dict:
    """variance_components.build()'s loops, calling its own _estimate and share_dispersion, on <= CUTOFF rows."""
    from nfl.sim import variance_components as VC
    rows = _fit_rows(pg_rows)
    club = collections.defaultdict(list)
    for r in rows:
        club[(r['game_id'], r['club'])].append(r)
    rec, rush = [], []
    for ps in club.values():
        ct = sum(_num(p.get('targets')) or 0.0 for p in ps)
        cy = sum(_num(p.get('receiving_yards')) or 0.0 for p in ps)
        cc = sum(_num(p.get('carries')) or 0.0 for p in ps)
        cry = sum(_num(p.get('rushing_yards')) or 0.0 for p in ps)
        if ct >= VC.MIN_CLUB_OPP and cy > 0:
            for p in ps:
                t, y = _num(p.get('targets')), _num(p.get('receiving_yards'))
                if t is not None and y is not None and t >= VC.MIN_OPP:
                    rec.append((t / ct, y / cy))
        if cc >= VC.MIN_CLUB_OPP and cry > 0:
            for p in ps:
                c, y = _num(p.get('carries')), _num(p.get('rushing_yards'))
                if c is not None and y is not None and c >= VC.MIN_OPP:
                    rush.append((c / cc, y / cry))
    out = {'receiving': VC._estimate(rec), 'rushing': VC._estimate(rush, seed=43),
           'share_dispersion_targets': VC.share_dispersion(club, 'targets'),
           'share_dispersion_carries': VC.share_dispersion(club, 'carries')}
    _require(out['receiving'].get('state') == 'ESTIMATED' and out['rushing'].get('state') == 'ESTIMATED',
             'SC_COH_1_CLEAN_FIT_FAILED', f"VC: {out['receiving'].get('state')} / {out['rushing'].get('state')}")
    return out


def fit_usage(pg_rows, rh_rows) -> dict:
    """usage.build()'s teammate_backs decomposition (the only USAGE quantity the default incumbent reads)."""
    from nfl.sim import usage as U
    rank = {}
    for r in _fit_rows(rh_rows):
        if U.RANK_MEASURE.get(r.get('position')) != r.get('measure'):
            continue
        if _num(r.get('depth_rank')) is not None:
            rank[(int(r['season']), int(r['week']), r['player_id'])] = (r['position'], int(r['depth_rank']))
    by = collections.defaultdict(list)
    for r in _fit_rows(pg_rows):
        by[(r['game_id'], r['club'])].append(r)
    tb = U._teammate_decomposition(list(by.values()), rank, 'RB', 'carries', 10)
    _require(tb.get('state') == 'MEASURED', 'SC_COH_1_CLEAN_FIT_FAILED', f'teammate_backs {tb.get("state")}')
    return {'teammate_backs': tb}


def defensive_scores(seasons) -> dict:
    """{(game_id, defteam): {'def_td': n, 'safety': n}} from clean pbp, dst.build()'s definitions."""
    out = collections.defaultdict(collections.Counter)
    for s in seasons:
        df = load_pbp_clean(s)
        td = df[(df.touchdown.fillna(0) == 1) & df.td_team.notna() & (df.td_team == df.defteam)]
        for (g, d), n in td.groupby(['game_id', 'defteam']).size().items():
            out[(g, d)]['def_td'] += int(n)
        sf = df[df.safety.fillna(0) == 1]
        for (g, d), n in sf.groupby(['game_id', 'defteam']).size().items():
            out[(g, d)]['safety'] += int(n)
    return out


def fit_dst_bands(tg_rows) -> dict:
    """dst.build()'s points-allowed bands of (sacks, takeaways, def TD, safety) tuples on <= CUTOFF rows; def TD and
    safeties from clean pbp 2021-CUTOFF (production reads 2021-2026)."""
    from nfl.sim import dst as D
    rows = _fit_rows(tg_rows)
    ev = defensive_scores(tuple(s for s in D.PBP_SEASONS if s <= CUTOFF))
    by = {(r['game_id'], r['club']): r for r in rows}
    obs = collections.defaultdict(list)
    for (gid, club), r in by.items():
        o = by.get((gid, r.get('opponent')))
        if o is None or any(_num(o.get(k)) is None for k in ('sacks', 'turnovers', 'points')):
            continue
        pa_ = float(o['points'])
        e = ev.get((gid, club), {})
        for lo, hi in D.CONDITIONING_BANDS:
            if lo <= pa_ < hi:
                obs[(lo, hi)].append([float(o['sacks']), float(o['turnovers']), float(e.get('def_td', 0)),
                                      float(e.get('safety', 0))])
                break
    thin = {f'{lo}-{hi}': len(v) for (lo, hi), v in obs.items() if len(v) < D.MIN_PER_BAND}
    _require(obs and not thin, 'SC_COH_1_CLEAN_FIT_FAILED', f'DST bands thin {thin}')
    return {'bands': {f'{lo}-{hi}': {'n': len(v), 'empirical_tuples': v} for (lo, hi), v in sorted(obs.items())},
            'sack_points': D.SACK_POINTS, 'takeaway_points': D.TAKEAWAY_POINTS,
            'defensive_td_points': D.DEFENSIVE_TD_POINTS, 'safety_points': D.SAFETY_POINTS}


def fit_int_rate() -> dict:
    """League interceptions per pass attempt, 2021-CUTOFF clean pbp (proj_v1.int_rate measures the same through
    2025 on its panel)."""
    a = i = 0
    for s in LIB_SEASONS:
        p = M.offensive_plays(load_pbp_clean(s))
        df = load_pbp_clean(s)
        a += int(p.att.sum())
        i += int(df[(df.play_type == 'pass') & (df.interception.fillna(0) == 1)].shape[0])
    _require(a > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', 'no pass attempts for the INT rate')
    return {'int_per_attempt': round(i / a, 6), 'attempts': a, 'interceptions': i, 'seasons': list(LIB_SEASONS)}


def build_incumbent_model(fits: dict):
    """nfl/sim/game.py:Model built from REFITTED <= CUTOFF dicts, scoring residuals = the football centre's."""
    from nfl.sim import game as G, dst as D
    fr = fits['football_residuals']
    ss = fits['shared_state']
    shared = {'environment': {'total_residual': {'sd': fr['total_sd']}, 'margin_residual': {'sd': fr['margin_sd']}},
              'empirical_residuals': {'total': fr['total_res'], 'margin': fr['margin_res']},
              'volume_response_to_realised_game': ss['realised'],
              'volume_response_plays_and_pass_share': ss['plays_form'], 'scoring': ss['scoring']}
    eff = {'yards_per_pass_attempt': {'empirical': fits['efficiency']['ypa']},
           'yards_per_carry': {'empirical': fits['efficiency']['ypc']}}
    m = G.Model(shared, eff).attach_concentration(fits['variance_components'])
    m.dst = D.DstModel(fits['dst_bands'])
    m.attach_usage(fits['usage'])
    m.total_res = list(fr['total_res'])
    m.margin_res = list(fr['margin_res'])
    return m


# ================================================================================================ season data
def season_frames(season: int) -> dict:
    """Offensive plays, player-games, finals (no lines), DST rows and schedule for one season (clean pbp)."""
    df = load_pbp_clean(season)
    plays = M.offensive_plays(df)
    pg = M.player_games(plays)
    fin = (df.groupby('game_id').agg(season=('season', 'first'), week=('week', 'first'), home=('home_team', 'first'),
                                     away=('away_team', 'first'), hs=('home_score', 'max'), as_=('away_score', 'max'))
           .reset_index())
    _require(len(fin) > 0 and fin[['hs', 'as_']].notna().all().all(), 'SC_COH_1_CLEAN_FINALS_INCOMPLETE', str(season))
    dst = M.dst_games(df, fin)
    pos_of = C._pos_of()
    it = df[(df.play_type == 'pass') & (df.interception.fillna(0) == 1) & (df.two_point_attempt.fillna(0) != 1)]
    it = it[it.passer_player_id.map(lambda x: pos_of.get(x) == 'QB')]
    ints = it.groupby(['game_id', 'posteam']).size().to_dict()      # QB interceptions thrown, per (game, offence)
    sched = fin[['game_id', 'week', 'home', 'away']].copy()
    for x in (plays, pg, fin, dst):
        guard_no_market(x, f'season_frames {season}')
    return {'df': df, 'plays': plays, 'pg': pg, 'fin': fin, 'dst': dst, 'ints': ints, 'sched': sched}


# ================================================================================================ point-in-time pools
def build_pools(pg: pd.DataFrame, sched: pd.DataFrame, mode: str = PRIMARY_POOL, first_week: int = 2,
                weeks=None, prev_pg: pd.DataFrame = None) -> tuple:
    """{(game_id, club): pool} from rows of weeks < W only. Returns (pools, exclusions).

    pool  = skill players (crosswalk QB / RB / FB / WR / TE) with >= 1 target, carry or pass attempt for this club
            in an earlier week of this season (SEASON_TO_DATE), or in the club's most recent earlier game (LAST_GAME).
    shares= season-to-date targets / carries / pass attempts over the pool, renormalised (showdown_draws._shares).
    roles = QB by prior pass attempts; WR1/WR2/TE1 by prior targets; RB1 by prior carries (ties: player id).
    eff   = conditional yards per opportunity for the efficiency step: (this season weeks < W + previous season,
            any club) yards over opportunities -- pooled ratio, no constant.
    """
    _require(mode in POOL_MODES, 'SC_COH_1_CLEAN_POOL_MODE', mode)
    guard_no_market(pg, 'build_pools.pg')
    guard_no_market(sched, 'build_pools.sched')
    _require(len(pg) > 0 and len(sched) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', 'player-game or schedule empty')
    pos_of = C._pos_of()
    cols = ['targets', 'carries', 'pass_att', 'receptions', 'rec_yards', 'rush_yards', 'pass_yards']
    prev = (prev_pg.groupby('pid')[cols].sum() if prev_pg is not None and len(prev_pg) else None)
    pools, excl = {}, []
    for g in sched.itertuples(index=False):
        W = int(g.week)
        if W < first_week or (weeks is not None and W not in weeks):
            continue
        for club in (g.home, g.away):
            prior = pg[(pg.team == club) & (pg.week < W)]
            _require(len(prior) == 0 or int(prior.week.max()) < W, 'SC_COH_1_CLEAN_PRIOR_LEAK', f'{g.game_id} {club}')
            if len(prior) == 0:
                excl.append({'game_id': g.game_id, 'club': club, 'reason': 'NO_PRIOR_GAME'})
                continue
            tot = prior.groupby('pid')[cols].sum()
            members = tot.index if mode == 'SEASON_TO_DATE' else prior[prior.week == prior.week.max()].pid.unique()
            players = []
            for pid in sorted(members):
                pos = pos_of.get(pid)
                if pos not in ('QB', 'RB', 'WR', 'TE'):
                    continue
                a = tot.loc[pid]
                if a.targets + a.carries + a.pass_att <= 0:
                    continue
                pv = prev.loc[pid] if (prev is not None and pid in prev.index) else None
                eff = {'targets': float(a.targets + (pv.targets if pv is not None else 0)),
                       'rec_yards': float(a.rec_yards + (pv.rec_yards if pv is not None else 0)),
                       'carries': float(a.carries + (pv.carries if pv is not None else 0)),
                       'rush_yards': float(a.rush_yards + (pv.rush_yards if pv is not None else 0)),
                       'pass_attempts': float(a.pass_att + (pv.pass_att if pv is not None else 0)),
                       'pass_yards': float(a.pass_yards + (pv.pass_yards if pv is not None else 0))}
                players.append({'pid': pid, 'pos': pos, 'prior_targets': float(a.targets),
                                'prior_carries': float(a.carries), 'prior_pass_att': float(a.pass_att),
                                'catch_rate': (float(a.receptions) / float(a.targets)) if a.targets > 0
                                else M.CATCH_RATE_FALLBACK.get(pos, 0.65), 'eff': eff})
            T = sum(p['prior_targets'] for p in players if p['pos'] != 'QB')
            Cr = sum(p['prior_carries'] for p in players)
            A = sum(p['prior_pass_att'] for p in players if p['pos'] == 'QB')
            why = ('NO_POOL_PASSER' if A <= 0 else 'NO_POOL_TARGETS' if T <= 0 else 'NO_POOL_CARRIES' if Cr <= 0 else None)
            if why:
                excl.append({'game_id': g.game_id, 'club': club, 'reason': why})
                continue
            for p in players:
                p['target_share'] = p['prior_targets'] / T if p['pos'] != 'QB' else 0.0
                p['carry_share'] = p['prior_carries'] / Cr
                p['pass_att_share'] = p['prior_pass_att'] / A if p['pos'] == 'QB' else 0.0
            rank = lambda pos, key: sorted([p for p in players if p['pos'] == pos and p[key] > 0],
                                           key=lambda p: (-p[key], p['pid']))
            qb = rank('QB', 'prior_pass_att')
            wr, te, rb = rank('WR', 'prior_targets'), rank('TE', 'prior_targets'), rank('RB', 'prior_carries')
            roles = {'QB': qb[0]['pid'] if qb else None, 'WR1': wr[0]['pid'] if wr else None,
                     'WR2': wr[1]['pid'] if len(wr) > 1 else None, 'TE1': te[0]['pid'] if te else None,
                     'RB1': rb[0]['pid'] if rb else None}
            pools[(g.game_id, club)] = {'players': players, 'roles': roles, 'week': W}
    return pools, excl


# ================================================================================================ pregame specs
def volume_centre(tg_table: dict, club: str, season: int, week: int):
    """proj_v1.team_volume (FOOTBALL_ONLY branch): current season weeks < W per game, prior season at
    TEAM_VOLUME_PRIOR_GAMES pseudo-games. Fields pass_attempts / rush_attempts / targets from TEAM_GAME."""
    from nfl.tools import proj_v1 as PV
    out = {}
    cur = [r for r in tg_table.get((club, season), []) if int(r['week']) < week]
    prv = tg_table.get((club, season - 1), [])
    for f in ('pass_attempts', 'rush_attempts', 'targets'):
        c = [_num(r.get(f)) for r in cur if _num(r.get(f)) is not None]
        p = [_num(r.get(f)) for r in prv if _num(r.get(f)) is not None]
        pc = sum(c) / len(c) if c else None
        pp = sum(p) / len(p) if p else None
        if pc is None and pp is None:
            return None
        out[f] = pp if pc is None else pc if pp is None else (len(c) * pc + PV.TEAM_VOLUME_PRIOR_GAMES * pp) / (
            len(c) + PV.TEAM_VOLUME_PRIOR_GAMES)
    if out['targets'] > out['pass_attempts']:
        out['targets'] = out['pass_attempts']
    return out


def tg_by_club_season(tg_rows) -> dict:
    d = collections.defaultdict(list)
    for r in tg_rows:
        d[(r['club'], int(r['season']))].append(r)
    return d


def dst_rates_table(season: int, frames: dict, prev_frames: dict) -> dict:
    """Per (club, week): DST event rates blended like nfl/tools/dst_model.club_rates (current season weeks < W,
    prior season at PRIOR_GAMES pseudo-games). Events: sacks, INT, fumble recoveries, def/return TD, safeties."""
    def per_game(fr):
        d = fr['dst'].copy()
        d['week'] = d.game_id.map(fr['sched'].set_index('game_id').week)
        return d
    return {'cur': per_game(frames), 'prv': per_game(prev_frames) if prev_frames else None}


def dst_target(rates, club, week, opp_centre, pa_res):
    """FOOTBALL_ONLY DST point projection (dst_model.project form): blended event rates x DK weights + the
    points-allowed expectation over <= CUTOFF residuals around the opponent's football centre."""
    from nfl.tools import dst_model as DM
    cur = rates['cur'][(rates['cur'].team == club) & (rates['cur'].week < week)]
    prv = rates['prv'][rates['prv'].team == club] if rates['prv'] is not None else cur.iloc[0:0]
    w = {'sacks': 1.0, 'ints': 2.0, 'fumrec': 2.0, 'dtd': 6.0, 'safeties': 2.0}
    ev = 0.0
    for k, wt in w.items():
        pc = cur[k].mean() if len(cur) else None
        pp = prv[k].mean() if len(prv) else None
        if pc is None and pp is None:
            return None
        v = pp if pc is None else pc if pp is None else (len(cur) * pc + DM.PRIOR_GAMES * pp) / (len(cur) + DM.PRIOR_GAMES)
        ev += wt * float(v)
    pa, acct = DM.pa_expectation(opp_centre, {'state': 'MEASURED', 'residuals': pa_res})
    _require(pa is not None, 'SC_COH_1_CLEAN_DST_TARGET', f'{club}: {acct}')
    return ev + pa


def player_key(pid, club):
    return f'{pid}|{club}'


def game_spec(g, pools, centre) -> dict:
    """The simulator's game spec. `total_line` / `home_spread` are nfl/sim/game.py's API key names; they carry the
    FOOTBALL centre and nothing else (checked by assert_spec_football_only)."""
    clubs = []
    for t in (g.home, g.away):
        ps = []
        for p in pools[(g.game_id, t)]['players']:
            # keyed by player AND club: a mid-season trade can put one player in both clubs' pools
            ps.append({'id': player_key(p['pid'], t), 'pid': p['pid'], 'position': p['pos'], 'target_share': p['target_share'],
                       'carry_share': p['carry_share'], 'pass_att_share': p['pass_att_share'],
                       'pass_td_share': p['target_share'],
                       'rush_td_share': p['carry_share'] if p['pos'] in ('RB', 'QB') else 0.0,
                       'catch_rate': p['catch_rate'], 'slot': 'OTHER'})
        clubs.append({'club': t, 'players': ps, 'dst_id': f'DST|{t}'})
    spec = {'total_line': float(centre['total']), 'home_spread': float(centre['home_margin']),
            'fc_total': float(centre['total']), 'fc_margin': float(centre['home_margin']),
            'scoring_basis': centre['BASIS'], 'clubs': clubs}
    assert_spec_football_only(spec)
    return spec


def _check_spec_nonempty(spec, n):
    _require(n > 0 and len(spec.get('clubs') or []) == 2, 'SC_COH_1_CLEAN_EMPTY_INPUT', 'need two clubs and n > 0')
    for c in spec['clubs']:
        _require(len(c.get('players') or []) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', f"{c.get('club')} has no players")
        _require(any(p['position'] == 'QB' and p.get('pass_att_share', 0) > 0 for p in c['players']),
                 'SC_COH_1_CLEAN_EMPTY_INPUT', f"{c.get('club')} has no passer")


def assert_spec_football_only(spec):
    _require(spec.get('scoring_basis') == 'FOOTBALL_ONLY_OWN_OFFENCE_BLEND', 'SC_COH_1_CLEAN_SPEC_NOT_FOOTBALL',
             f"basis {spec.get('scoring_basis')}")
    _require(spec['total_line'] == spec['fc_total'] and spec['home_spread'] == spec['fc_margin'],
             'SC_COH_1_CLEAN_SPEC_NOT_FOOTBALL', 'simulator centre differs from the football centre')
    extra = sorted(k for k in spec if is_market_name(k) and k not in ('total_line', 'home_spread'))
    _require(not extra, 'SC_COH_1_CLEAN_MARKET_INPUT', f'spec carries {extra}')
    for c in spec['clubs']:
        guard_no_market(c['players'], f"spec {c['club']}")


# ================================================================================================ candidate (clean)
class CleanLibrary:
    """Analogue games keyed on the FOOTBALL centre (total, home margin) computed point-in-time for each library
    game; the play content is sc_coh_1_candidate._club_plays (unchanged)."""

    def __init__(self, games, seasons):
        _require(len(games) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', 'library has no games')
        self.games, self.seasons = games, tuple(seasons)
        self.max_season = max(g['season'] for g in games)
        _require(self.max_season <= CUTOFF, 'SC_COH_1_CLEAN_HELDOUT_LEAK', f'library season {self.max_season}')
        for g in games:
            _require(not any(is_market_name(k) for k in g), 'SC_COH_1_CLEAN_MARKET_INPUT', f"library game {g['game_id']}")
        X = np.array([[g['fc_total'], g['fc_margin']] for g in games], float)
        self.scale = X.std(0, ddof=1)
        _require(np.all(self.scale > 0), 'SC_COH_1_CLEAN_DEGENERATE_CENTRE', str(self.scale))
        self.X = X / self.scale
        self.k = int(round(math.sqrt(len(games))))

    def neighbours(self, fc_total, fc_margin):
        d = np.hypot(self.X[:, 0] - fc_total / self.scale[0], self.X[:, 1] - fc_margin / self.scale[1])
        return np.argsort(d, kind='stable')[:self.k]

    def describe(self):
        return {'n_games': len(self.games), 'seasons': list(self.seasons), 'max_season': int(self.max_season),
                'k_neighbours': self.k, 'K_RULE': 'round(sqrt(n_games)), declared prior (as the original candidate)',
                'distance': 'Euclidean on (football total centre, football home-margin centre), each / library SD',
                'centre_scale_sd': [round(float(v), 4) for v in self.scale]}


def build_clean_library(seasons, tg_rows) -> CleanLibrary:
    seasons = tuple(int(s) for s in seasons)
    _require(seasons and max(seasons) <= CUTOFF, 'SC_COH_1_CLEAN_HELDOUT_LEAK', f'library seasons {seasons}')
    table = points_table(_fit_rows(tg_rows))
    pos_of = C._pos_of()
    games = []
    for s in seasons:
        fr = season_frames(s)
        dst = fr['dst'].set_index(['game_id', 'team'])
        byc = {k: v for k, v in fr['plays'].groupby(['game_id', 'team'])}
        for g in fr['fin'].itertuples(index=False):
            if (g.game_id, g.home) not in byc or (g.game_id, g.away) not in byc:
                continue
            c = football_centre(table, g.home, g.away, int(g.season), int(g.week))
            if c is None:
                continue
            clubs = {}
            for side, t, pts in (('home', g.home, g.hs), ('away', g.away, g.as_)):
                cp = C._club_plays(byc[(g.game_id, t)], pos_of)
                d = dst.loc[(g.game_id, t)]
                cp.update({'points': float(pts), 'dst': (float(d.sacks), float(d.ints), float(d.fumrec), float(d.dtd),
                                                         float(d.safeties))})
                clubs[side] = cp
            games.append({'game_id': g.game_id, 'season': int(g.season), 'fc_total': float(c['total']),
                          'fc_margin': float(c['home_margin']), 'home': clubs['home'], 'away': clubs['away']})
    return CleanLibrary(games, seasons)


def estimate_concentration(frames_2024: dict) -> dict:
    """Dirichlet-multinomial concentration of per-game targets / carries around point-in-time pregame shares,
    2024 weeks 2-18 (the original candidate's method, with the outcome-derived snap pool replaced)."""
    pools, _ = build_pools(frames_2024['pg'], frames_2024['sched'], PRIMARY_POOL)
    act = frames_2024['pg'].set_index(['game_id', 'team', 'pid'])
    tot = frames_2024['plays'].groupby(['game_id', 'team']).agg(T=('receiver', lambda x: x.notna().sum()),
                                                                 Cn=('rusher', lambda x: x.notna().sum()))
    tr, cr = [], []
    for (gid, team), pool in pools.items():
        if (gid, team) not in tot.index:
            continue
        T, Cn = tot.loc[(gid, team)]
        for p in pool['players']:
            a = act.loc[(gid, team, p['pid'])] if (gid, team, p['pid']) in act.index else None
            if p['target_share'] > 0 and p['pos'] != 'QB':
                tr.append((T, p['target_share'], float(a.targets) if a is not None else 0.0))
            if p['carry_share'] > 0:
                cr.append((Cn, p['carry_share'], float(a.carries) if a is not None else 0.0))
    _require(len(tr) > 100 and len(cr) > 100, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'{len(tr)} / {len(cr)} rows')
    return {'season': CONC_SEASON, 'pool': PRIMARY_POOL, 'targets': C._mom_alpha(tr), 'carries': C._mom_alpha(cr)}


def simulate_candidate(lib: CleanLibrary, conc: dict, spec: dict, n: int, seed: int) -> dict:
    """sc_coh_1_candidate.simulate with neighbours on the football centre. Returns the provider-neutral world."""
    _check_spec_nonempty(spec, n)
    _require(isinstance(lib, CleanLibrary) and lib.max_season <= CUTOFF, 'SC_COH_1_CLEAN_HELDOUT_LEAK', 'library')
    assert_spec_football_only(spec)
    rng = np.random.default_rng(seed)
    nb = lib.neighbours(spec['fc_total'], spec['fc_margin'])
    home, away = spec['clubs']
    out = {'players': {p['id']: np.zeros((n, 10)) for c in spec['clubs'] for p in c['players']}, 'ints': None,
           'club_points': {c['club']: np.zeros(n) for c in spec['clubs']},
           'club_td': {c['club']: np.zeros(n) for c in spec['clubs']},
           'dst_dk': {c['club']: np.zeros(n) for c in spec['clubs']},
           'dst_comp': {c['club']: np.zeros((n, 4)) for c in spec['clubs']}}
    picks = nb[rng.integers(0, len(nb), size=n)]
    for w, gi in enumerate(picks):
        g = lib.games[gi]
        for c, side, oside in ((home, 'home', 'away'), (away, 'away', 'home')):
            ana = g[side]
            S, td, p = C._club_world(c, ana, conc, rng)
            isqb = np.array([q['position'] == 'QB' for q in c['players']])
            C.verify(S, isqb, td, p, ana)
            for i, q in enumerate(c['players']):
                out['players'][q['id']][w] = S[i]
            out['club_points'][c['club']][w], out['club_td'][c['club']][w] = p, td
            sk, it, fr, dtd, sf = ana['dst']
            out['dst_comp'][c['club']][w] = (sk, it + fr, dtd, sf)
            out['dst_dk'][c['club']][w] = M.dst_tier(g[oside]['points'])[0] + sk + 2 * it + 2 * fr + 6 * dtd + 2 * sf
    out['neighbours'] = [lib.games[i]['game_id'] for i in nb]
    return out


# ================================================================================================ incumbent
def simulate_incumbent(model, spec: dict, vol: dict, n: int, seed: int) -> dict:
    """nfl/sim/game.py:simulate_game_centred, exactly production's showdown_draws call (n_calib = n_sims)."""
    from nfl.sim import game as G
    assert_spec_football_only(spec)
    _check_spec_nonempty(spec, n)
    o = G.simulate_game_centred(model, spec, vol, n_sims=n, seed=seed, n_calib=n)
    if o.state.value != 'PASS':
        raise CleanEvalError('SC_COH_1_CLEAN_INCUMBENT_REFUSED', f'{o.code} {o.detail}')
    v = o.value
    out = {'players': {k: np.asarray(x, float) for k, x in v['stat_draws'].items()}, 'ints': None,
           'club_points': {c: np.array([w[0] for w in x]) for c, x in v['club_scoring_worlds'].items()},
           'club_td': {c: np.array([w[1] for w in x], float) for c, x in v['club_scoring_worlds'].items()},
           'dst_dk': {c['club']: np.asarray(v['draws'][c['dst_id']], float) for c in spec['clubs']},
           'dst_comp': {c['club']: np.asarray(v['dst_components'][c['dst_id']], float) for c in spec['clubs']},
           'raw_stat_draws': v['stat_draws']}
    for c in spec['clubs']:
        for p in c['players']:
            _require(p['id'] in out['players'], 'SC_COH_1_CLEAN_EMPTY_DRAWS', f"{p['id']} has no draws")
    return out


# ================================================================================================ transforms
def stage_efficiency(world: dict, pools_game: dict, int_rate: float, seed: int) -> dict:
    """classic_slate_run.efficiency_worlds, the live post-step, with rows_by_key built from the pregame pool.
    pools_game = {club: pool}."""
    from nfl.tools import classic_slate_run as CR
    rows_by_key = {player_key(p['pid'], club): {'conditional_volume': p['eff']}
                   for club, pool in pools_game.items() for p in pool['players']}
    sd = {k: [tuple(r) for r in v] for k, v in world['players'].items()}
    _dk, worlds, acct = CR.efficiency_worlds(sd, rows_by_key, float(int_rate), seed)
    out = dict(world)
    out['players'] = {k: np.asarray([w[:10] for w in v], float) for k, v in worlds.items()}
    out['ints'] = {k: np.asarray([w[10] for w in v], float) for k, v in worlds.items()}
    out['efficiency_factors'] = acct['factors']
    return out


def stage_dst_anchor(world: dict, targets: dict) -> dict:
    """classic_slate_run.anchor_means on the DST draws (showdown_slate_run.py:95)."""
    from nfl.tools import classic_slate_run as CR
    d = {c: list(v) for c, v in world['dst_dk'].items()}
    new, acct = CR.anchor_means(d, {c: t for c, t in targets.items() if t is not None})
    out = dict(world)
    out['dst_dk'] = {c: np.asarray(v, float) for c, v in new.items()}
    out['dst_anchor'] = acct
    return out


# ================================================================================================ conservation
CONSERVATION_CHECKS = (
    'player_rec_yards_without_reception', 'player_rec_td_without_reception', 'player_rec_td_gt_receptions',
    'player_receptions_gt_targets', 'player_rush_td_without_carry', 'player_rush_td_gt_carries',
    'player_rush_yards_without_carry', 'player_pass_yards_without_attempt',
    'club_team_td_ne_pass_td_plus_rush_td', 'club_qb_pass_yards_ne_sum_rec_yards', 'club_qb_pass_td_ne_sum_rec_td',
    'club_points_lt_6_x_off_td', 'club_kicker_remainder_negative_if_every_xp_good', 'club_points_not_integer',
    'club_dst_dk_ne_tier_plus_components', 'club_opp_qb_ints_gt_dst_takeaways')
NOT_REPRESENTED = {
    'dst_sacks_vs_opponent_sack_events': ('neither simulator writes sacks into the offence stat line (STAT_FIELDS has '
                                          'no sacks), so a defence sack cannot be reconciled with an opponent event '
                                          'in the draws: NOT_IDENTIFIABLE_IN_DRAWS for both providers'),
    'other_offensive_td_types': ('declared: team offensive TD = passing TD + rushing TD; fumble-return and '
                                 'other non-scrimmage TDs belong to the DST and are not offensive TDs')}


def conservation(spec: dict, world: dict, acc: collections.Counter):
    """Count every impossibility in one world-set. Never repairs. Units: player-worlds / club-worlds."""
    from nfl.sim import dst as D
    tier = np.vectorize(D.tier)
    clubs = [c['club'] for c in spec['clubs']]
    for c, oc in ((spec['clubs'][0], spec['clubs'][1]), (spec['clubs'][1], spec['clubs'][0])):
        ids = [p['id'] for p in c['players']]
        S = np.stack([world['players'][i] for i in ids])          # player x world x field
        n = S.shape[1]
        qb = np.array([p['position'] == 'QB' for p in c['players']])
        acc['player_worlds'] += S.shape[0] * n
        acc['club_worlds'] += n
        rec, tg, ry, rtd = S[..., SX['receptions']], S[..., SX['targets']], S[..., SX['rec_yards']], S[..., SX['rec_td']]
        car, rshy, rshtd = S[..., SX['carries']], S[..., SX['rush_yards']], S[..., SX['rush_td']]
        acc['player_rec_yards_without_reception'] += int(((np.abs(ry) > 0.5) & (rec == 0)).sum())
        acc['player_rec_td_without_reception'] += int(((rtd > 0) & (rec == 0)).sum())
        acc['player_rec_td_gt_receptions'] += int((rtd > rec).sum())
        acc['player_receptions_gt_targets'] += int((rec > tg).sum())
        acc['player_rush_td_without_carry'] += int(((rshtd > 0) & (car == 0)).sum())
        acc['player_rush_td_gt_carries'] += int((rshtd > car).sum())
        acc['player_rush_yards_without_carry'] += int(((np.abs(rshy) > 0.5) & (car == 0)).sum())
        acc['player_pass_yards_without_attempt'] += int(((np.abs(S[..., SX['pass_yards']]) > 0.5)
                                                         & (S[..., SX['pass_att']] == 0)).sum())
        td = np.asarray(world['club_td'][c['club']], float)
        pts = np.asarray(world['club_points'][c['club']], float)
        ptd = S[qb, :, SX['pass_td']].sum(0)
        acc['club_team_td_ne_pass_td_plus_rush_td'] += int((td != ptd + rshtd.sum(0)).sum())
        acc['club_qb_pass_yards_ne_sum_rec_yards'] += int((np.abs(S[qb, :, SX['pass_yards']].sum(0)
                                                                  - ry[~qb].sum(0)) > 0.5).sum())
        acc['club_qb_pass_td_ne_sum_rec_td'] += int((ptd != rtd[~qb].sum(0)).sum())
        acc['club_points_lt_6_x_off_td'] += int((pts + 1e-9 < 6 * td).sum())
        acc['club_kicker_remainder_negative_if_every_xp_good'] += int((pts + 1e-9 < 7 * td).sum())
        acc['club_points_not_integer'] += int((np.abs(pts - np.round(pts)) > 1e-6).sum())
        comp = np.asarray(world['dst_comp'][c['club']], float)
        opp_pts = np.asarray(world['club_points'][oc['club']], float)
        want = tier(opp_pts) + comp[:, 0] + 2 * comp[:, 1] + 6 * comp[:, 2] + 2 * comp[:, 3]
        acc['club_dst_dk_ne_tier_plus_components'] += int((np.abs(np.asarray(world['dst_dk'][c['club']]) - want)
                                                           > 1e-6).sum())
        if world.get('ints') is not None:
            oqb = [p['id'] for p in oc['players'] if p['position'] == 'QB']
            oi = np.stack([world['ints'][i] for i in oqb]).sum(0) if oqb else np.zeros(n)
            acc['club_opp_qb_ints_gt_dst_takeaways'] += int((oi > comp[:, 1] + 1e-9).sum())
            acc['ints_present_club_worlds'] += n
    _ = clubs
    return acc


def history_conservation(frames: dict, games: list, acc: collections.Counter):
    """The same counters on the ACTUAL club-games (outcomes; scoring-side only). Laterals and official-stat
    conventions are what history is allowed to show; the counts are the baseline the simulators are read against."""
    pl = frames['plays']
    pg = frames['pg'].set_index(['game_id', 'team'])
    fin = frames['fin'].set_index('game_id')
    dst = frames['dst'].set_index(['game_id', 'team'])
    for gid in games:
        g = fin.loc[gid]
        for t, o, pts in ((g.home, g.away, g.hs), (g.away, g.home, g.as_)):
            x = pg.loc[(gid, t)] if (gid, t) in pg.index else None
            if x is None:
                continue
            x = x.reset_index() if isinstance(x, pd.DataFrame) else x.to_frame().T
            acc['club_games'] += 1
            acc['player_games'] += len(x)
            acc['player_rec_yards_without_reception'] += int(((x.rec_yards.abs() > 0.5) & (x.receptions == 0)).sum())
            acc['player_rec_td_without_reception'] += int(((x.rec_td > 0) & (x.receptions == 0)).sum())
            acc['player_rec_td_gt_receptions'] += int((x.rec_td > x.receptions).sum())
            acc['player_rush_td_without_carry'] += int(((x.rush_td > 0) & (x.carries == 0)).sum())
            p = pl[(pl.game_id == gid) & (pl.team == t)]
            ptd, rtd = int(p.ptd.sum()), int(p.rtd.sum())
            acc['club_qb_pass_yards_ne_sum_rec_yards'] += int(abs(p.pyds.sum() - p.recyds.sum()) > 0.5)
            acc['club_points_lt_6_x_off_td'] += int(pts < 6 * (ptd + rtd))
            acc['club_kicker_remainder_negative_if_every_xp_good'] += int(pts < 7 * (ptd + rtd))
            d = dst.loc[(gid, t)]
            oi = frames['ints'].get((gid, o), 0)
            acc['club_opp_qb_ints_gt_dst_takeaways'] += int(oi > d.ints + d.fumrec)
    return acc


# ================================================================================================ scoring rules
def crps_draws(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """CRPS from an ensemble, rows = units: mean|X - y| - 0.5 mean|X - X'| (all M^2 pairs, the plain estimator)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    M_ = X.shape[1]
    t1 = np.abs(X - y[:, None]).mean(1)
    Xs = np.sort(X, 1)
    w = 2 * np.arange(1, M_ + 1) - M_ - 1
    t2 = 2.0 * (Xs * w).sum(1) / (M_ * M_)
    return t1 - 0.5 * t2


def is_integral(X) -> bool:
    X = np.asarray(X, float)
    return bool(np.all(np.abs(X - np.round(X)) < 1e-9))


def count_log_score(X: np.ndarray, y: np.ndarray):
    """-log p_hat(y), p_hat = max(count(y), 0.5) / M (half-draw floor, declared). Returns (scores, n_floored)."""
    X = np.asarray(X, float)
    cnt = (np.abs(X - np.asarray(y, float)[:, None]) < 1e-9).sum(1).astype(float)
    fl = cnt < 0.5
    return -np.log(np.maximum(cnt, 0.5) / X.shape[1]), fl


def randomized_pit(X: np.ndarray, y: np.ndarray, rng) -> np.ndarray:
    X = np.asarray(X, float)
    y = np.asarray(y, float)[:, None]
    lo = (X < y - 1e-9).mean(1)
    hi = (X <= y + 1e-9).mean(1)
    return lo + rng.random(len(lo)) * (hi - lo)


def central_coverage(X: np.ndarray, y: np.ndarray, level: float) -> np.ndarray:
    a = (1 - level) / 2
    lo = np.quantile(X, a, axis=1, method='inverted_cdf')
    hi = np.quantile(X, 1 - a, axis=1, method='inverted_cdf')
    return ((y >= lo - 1e-9) & (y <= hi + 1e-9)).astype(float)


def energy_score(X: np.ndarray, y: np.ndarray) -> float:
    """X: (M, d) ensemble, y: (d,). ES = E||X - y|| - 0.5 E||X - X'||."""
    t1 = np.linalg.norm(X - y, axis=1).mean()
    D = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
    return float(t1 - 0.5 * D.mean())


def variogram_score(X: np.ndarray, y: np.ndarray, p: float = VS_P) -> float:
    """VS_p with unit weights over all i < j pairs."""
    d = X.shape[1]
    iu = np.triu_indices(d, 1)
    ey = np.abs(y[iu[0]] - y[iu[1]]) ** p
    ex = (np.abs(X[:, iu[0]] - X[:, iu[1]]) ** p).mean(0)
    return float(((ey - ex) ** 2).sum())


# ================================================================================================ units
def dk_core_arr(S):
    return (0.04 * S[..., SX['pass_yards']] + 4 * S[..., SX['pass_td']] + 0.1 * S[..., SX['rush_yards']]
            + 6 * S[..., SX['rush_td']] + 0.1 * S[..., SX['rec_yards']] + S[..., SX['receptions']]
            + 6 * S[..., SX['rec_td']])


PLAYER_VARS = {   # name: (function of the 10-field stat array, positions it is scored for)
    'dk': (dk_core_arr, None),
    'receptions': (lambda S: S[..., SX['receptions']], ('RB', 'WR', 'TE')),
    'targets': (lambda S: S[..., SX['targets']], ('RB', 'WR', 'TE')),
    'rec_yards': (lambda S: S[..., SX['rec_yards']], ('RB', 'WR', 'TE')),
    'carries': (lambda S: S[..., SX['carries']], None),
    'rush_yards': (lambda S: S[..., SX['rush_yards']], None),
    'scrimmage_td': (lambda S: S[..., SX['rush_td']] + S[..., SX['rec_td']], None),
    'pass_yards': (lambda S: S[..., SX['pass_yards']], ('QB',)),
    'pass_td': (lambda S: S[..., SX['pass_td']], ('QB',)),
}
CLUB_VARS = ('team_points', 'team_off_td', 'team_pass_yards', 'team_rush_yards', 'dst_dk')


def actual_stat_row(pgi, gid, club, pid):
    if (gid, club, pid) in pgi.index:
        r = pgi.loc[(gid, club, pid)]
        return np.array([float(r[f]) for f in ('pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td',
                                               'targets', 'receptions', 'rec_yards', 'rec_td')])
    return np.zeros(10)


def club_actuals(frames, gid, club, opp):
    pl = frames['plays']
    p = pl[(pl.game_id == gid) & (pl.team == club)]
    fin = frames['fin'].set_index('game_id').loc[gid]
    pts = float(fin.hs if club == fin.home else fin.as_)
    d = frames['dst'].set_index(['game_id', 'team']).loc[(gid, club)]
    return {'team_points': pts, 'team_off_td': float(p.ptd.sum() + p.rtd.sum()), 'team_pass_yards': float(p.pyds.sum()),
            'team_rush_yards': float(p.rushyds.sum()), 'dst_dk': float(d.dst_dk)}


def club_sim(world, spec_club):
    S = np.stack([world['players'][p['id']] for p in spec_club['players']])
    qb = np.array([p['position'] == 'QB' for p in spec_club['players']])
    c = spec_club['club']
    return {'team_points': np.asarray(world['club_points'][c], float), 'team_off_td': np.asarray(world['club_td'][c], float),
            'team_pass_yards': S[qb, :, SX['pass_yards']].sum(0), 'team_rush_yards': S[:, :, SX['rush_yards']].sum(0),
            'dst_dk': np.asarray(world['dst_dk'][c], float)}


# ================================================================================================ freeze (<= 2024)
def history_role_rows(frames, pools, weeks=None):
    """Actual per club-game rows (team points, DK core per role, coherence columns) on pregame roles."""
    pgi = frames['pg'].set_index(['game_id', 'team', 'pid'])
    tdk = frames['pg'].groupby(['game_id', 'team']).dk.sum()
    team = frames['plays'].groupby(['game_id', 'team']).agg(pass_yds=('pyds', 'sum'), rush_yds=('rushyds', 'sum'),
                                                            pass_td=('ptd', 'sum'), rush_td=('rtd', 'sum'))
    dst = frames['dst'].set_index(['game_id', 'team'])
    rows = []
    for g in frames['fin'].itertuples(index=False):
        if weeks is not None and int(g.week) not in weeks:
            continue
        keys = [(g.game_id, g.home), (g.game_id, g.away)]
        if not all(k in pools for k in keys):
            continue
        for (gid, t), pts in zip(keys, (g.hs, g.as_)):
            tm = team.loc[(gid, t)]
            r = {'game_id': gid, 'week': int(g.week), 'team': t, 'pts': float(pts),
                 'off_td': float(tm.pass_td + tm.rush_td), 'yards': float(tm.pass_yds + tm.rush_yds),
                 'pass_yds': float(tm.pass_yds), 'pass_td': float(tm.pass_td), 'off_dk': float(tdk.get((gid, t), 0.0)),
                 'DST': float(dst.loc[(gid, t)].dst_dk)}
            for role, pid in pools[(gid, t)]['roles'].items():
                r[role] = float(dk_core_arr(actual_stat_row(pgi, gid, t, pid))) if pid else np.nan
            rows.append(r)
    u = pd.DataFrame(rows)
    _require(len(u) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', 'no history club-games')
    return M.add_opponent(u)


def coherence_values(units: pd.DataFrame) -> dict:
    games = sorted(set(units.game_id))
    return {name: float(M._stat(M.suffstats(units, x, y, games).sum(0), kind)) for name, x, y, kind, _ in M.STATS}


def freeze() -> dict:
    """Everything fitted or fixed from <= 2024. Refuses to run with the evaluation gate open."""
    _require(not _GATE['open'], 'SC_COH_1_CLEAN_GATE_OPEN', 'freeze must not run with 2025 readable')
    tg, pgr, rh = load_team_game(), load_player_game(), load_role_history()
    fits = {'football_residuals': fit_football_residuals(tg), 'shared_state': fit_shared_state(tg),
            'efficiency': fit_efficiency(pgr), 'variance_components': fit_variance_components(pgr),
            'usage': fit_usage(pgr, rh), 'dst_bands': fit_dst_bands(tg), 'int_rate': fit_int_rate()}
    frames = {s: season_frames(s) for s in MARGIN_SEASONS}
    conc = estimate_concentration(frames[CONC_SEASON])
    lib = build_clean_library(LIB_SEASONS, tg)
    # normalisation scales, tail thresholds (SCALE_SEASON), equivalence margins (season-to-season drift)
    coh, scale = {}, {}
    for s in MARGIN_SEASONS:
        pools, _ = build_pools(frames[s]['pg'], frames[s]['sched'], PRIMARY_POOL,
                               prev_pg=frames[s - 1]['pg'] if s - 1 in frames else None)
        u = history_role_rows(frames[s], pools)
        coh[s] = coherence_values(u)
        if s == SCALE_SEASON:
            pgi = frames[s]['pg'].set_index(['game_id', 'team', 'pid'])
            for col in ('pts', 'off_td') + ROLES:
                v = u[col].dropna().to_numpy(float)
                scale[col] = {'sd': round(float(v.std(ddof=1)), 4), 'p90': round(float(np.quantile(v, 0.9)), 4),
                              'n': int(len(v))}
            # player-variable SDs over the 2024 scoring set (pool players, actual 0 when absent)
            pv = collections.defaultdict(list)
            cv = collections.defaultdict(list)
            for (gid, t), pool in pools.items():
                for p in pool['players']:
                    a = actual_stat_row(pgi, gid, t, p['pid'])
                    for name, (fn, poss) in PLAYER_VARS.items():
                        if poss is None or p['pos'] in poss:
                            pv[name].append(float(fn(a)))
                opp = None
                ca = club_actuals(frames[s], gid, t, opp)
                for k, v in ca.items():
                    cv[k].append(v)
            scale['player_vars_sd'] = {k: round(float(np.std(v, ddof=1)), 4) for k, v in pv.items()}
            scale['club_vars_sd'] = {k: round(float(np.std(v, ddof=1)), 4) for k, v in cv.items()}
    margins = {}
    for name in coh[MARGIN_SEASONS[0]]:
        d = [abs(coh[b][name] - coh[a][name]) for a, b in zip(MARGIN_SEASONS, MARGIN_SEASONS[1:])]
        margins[name] = {'margin': round(float(max(d)), 4), 'season_values': {s: round(coh[s][name], 4) for s in coh},
                         'consecutive_abs_deltas': [round(x, 4) for x in d]}
    fit_summary = {k: _summarise_fit(k, v) for k, v in fits.items()}
    doc = {'ARTIFACT': 'SC_COH_1_CLEAN_FROZEN', 'STATUS': 'SHADOW_ONLY', 'cutoff': CUTOFF,
           'READ_NO_2025_ROW': True,
           'fits_sha256': _sha_bytes(_canon(fits)), 'concentration': conc, 'library': lib.describe(),
           'library_sha256': _sha_bytes(_canon([[g['game_id'], g['fc_total'], g['fc_margin']] for g in lib.games])),
           'fit_summary': fit_summary, 'scales': scale, 'equivalence_margins': margins,
           'design': design_constants(), 'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    FROZEN.write_text(json.dumps(doc, indent=1, default=float))
    return doc


def _summarise_fit(k, v):
    if k == 'football_residuals':
        return {x: v[x] for x in v if x not in ('total_res', 'margin_res', 'pa_res')}
    if k == 'efficiency':
        return {'n_ypa': len(v['ypa']), 'n_ypc': len(v['ypc']), 'mean_ypa': round(float(np.mean(v['ypa'])), 4),
                'mean_ypc': round(float(np.mean(v['ypc'])), 4), 'seasons': v['seasons']}
    if k == 'variance_components':
        return {x: {kk: vv for kk, vv in v[x].items() if kk in ('state', 'concentration', 'n_observations',
                                                                 'n_player_seasons', 'overdispersion_ratio')} for x in v}
    if k == 'usage':
        return {'teammate_backs_implied_dirichlet_concentration': v['teammate_backs']['implied_dirichlet_concentration'],
                'n_club_games': v['teammate_backs']['n_club_games']}
    if k == 'dst_bands':
        return {b: x['n'] for b, x in v['bands'].items()}
    return v


def design_constants():
    return {'CUTOFF': CUTOFF, 'EVAL_SEASON': EVAL_SEASON, 'DEV_WEEKS': list(DEV_WEEKS), 'CONF_WEEKS': list(CONF_WEEKS),
            'LIB_SEASONS': list(LIB_SEASONS), 'CONC_SEASON': CONC_SEASON, 'SCALE_SEASON': SCALE_SEASON,
            'MARGIN_SEASONS': list(MARGIN_SEASONS), 'N_WORLDS': N_WORLDS, 'SIM_SEED': SIM_SEED, 'N_BOOT': N_BOOT,
            'BOOT_SEED': BOOT_SEED, 'PIT_SEED': PIT_SEED, 'PIT_BINS': PIT_BINS, 'NI_RATIO_MARGIN': NI_RATIO_MARGIN,
            'LEVELS': list(LEVELS), 'VS_P': VS_P, 'POOL_MODES': list(POOL_MODES), 'PRIMARY_POOL': PRIMARY_POOL,
            'VARIANTS': list(VARIANTS), 'PRIMARY_PAIR': list(PRIMARY_PAIR), 'ROLES': list(ROLES),
            'PLAYER_VARS': list(PLAYER_VARS), 'CLUB_VARS': list(CLUB_VARS)}


# ================================================================================================ prereg lock
def lock() -> dict:
    _require(PREREG.exists(), 'SC_COH_1_CLEAN_PREREG_ABSENT', str(PREREG))
    _require(FROZEN.exists(), 'SC_COH_1_CLEAN_FROZEN_ABSENT', str(FROZEN))
    if OUT.exists():
        prior = json.loads(OUT.read_text())
        _require(not prior.get('phases'), 'SC_COH_1_CLEAN_ALREADY_SCORED',
                 'a phase has been scored under the current lock; re-locking would re-register after reading data')
    doc = {'ARTIFACT': 'SC_COH_1_CLEAN_PREREG_LOCK', 'prereg': str(PREREG.relative_to(_REPO)),
           'prereg_sha256': _sha(PREREG), 'frozen': str(FROZEN.relative_to(_REPO)), 'frozen_sha256': _sha(FROZEN),
           'locked_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    LOCK.write_text(json.dumps(doc, indent=1))
    return doc


def verify_prereg(prereg=PREREG, lock_path=LOCK, frozen=FROZEN) -> dict:
    """Refuse unless the pre-registration and the frozen file are byte-identical to what was locked."""
    _require(pathlib.Path(lock_path).exists(), 'SC_COH_1_CLEAN_PREREG_NOT_LOCKED', str(lock_path))
    lk = json.loads(pathlib.Path(lock_path).read_text())
    _require(pathlib.Path(prereg).exists(), 'SC_COH_1_CLEAN_PREREG_ABSENT', str(prereg))
    got = _sha(prereg)
    _require(got == lk['prereg_sha256'], 'SC_COH_1_CLEAN_PREREG_CHANGED',
             f'pre-registration sha256 {got} != locked {lk["prereg_sha256"]}')
    gotf = _sha(frozen)
    _require(gotf == lk['frozen_sha256'], 'SC_COH_1_CLEAN_FROZEN_CHANGED', f'frozen sha256 {gotf} != locked')
    return lk


# ================================================================================================ scoring run
def _boot_weights(games, weeks, rng):
    G_ = len(games)
    Wg = rng.multinomial(G_, np.full(G_, 1.0 / G_), size=N_BOOT).astype(float)
    wk = sorted(set(weeks[g] for g in games))
    Wk = rng.multinomial(len(wk), np.full(len(wk), 1.0 / len(wk)), size=N_BOOT).astype(float)
    ix = np.array([wk.index(weeks[g]) for g in games])
    return {'game': Wg, 'week': Wk[:, ix]}


def _ci(v, lo=2.5, hi=97.5):
    v = v[np.isfinite(v)]
    return [round(float(np.percentile(v, lo)), 5), round(float(np.percentile(v, hi)), 5)] if len(v) else None


def summarise_metric(per_game: dict, games, weeks, Wb, a='CANDIDATE_RAW', b='INCUMBENT_PROD', orientation='lower'):
    """per_game[variant] = (sum array [G], count array [G]). Ratio-of-sums means, paired diff and ratio CIs."""
    gi = {g: i for i, g in enumerate(games)}
    out = {}
    means = {}
    for v, (s, n) in per_game.items():
        tot = n.sum()
        if tot <= 0:
            continue
        means[v] = float(s.sum() / tot)
        with np.errstate(divide='ignore', invalid='ignore'):
            out[v] = {'mean': round(means[v], 5), 'n_units': int(tot), 'n_games': int((n > 0).sum()),
                      'ci95_game_block': _ci((Wb['game'] @ s) / (Wb['game'] @ n)),
                      'ci95_week_block': _ci((Wb['week'] @ s) / (Wb['week'] @ n))}
    if a in per_game and b in per_game and a in means and b in means:
        (sa, na), (sb, nb) = per_game[a], per_game[b]
        _require(np.array_equal(na, nb), 'SC_COH_1_CLEAN_UNPAIRED', 'paired comparison over different unit sets')
        r = {'diff': round(means[a] - means[b], 5), 'ratio': round(means[a] / means[b], 5) if means[b] else None}
        for blk in ('game', 'week'):
            with np.errstate(divide='ignore', invalid='ignore'):
                ma, mb = (Wb[blk] @ sa) / (Wb[blk] @ na), (Wb[blk] @ sb) / (Wb[blk] @ nb)
                r[f'diff_ci95_{blk}_block'] = _ci(ma - mb)
                r[f'ratio_ci95_{blk}_block'] = _ci(ma / mb) if means[b] else None
        out[f'{a}_vs_{b}'] = r
    _ = gi, orientation
    return out


def dry_run_in_sample(season: int = CUTOFF, weeks=(10, 11), n_worlds: int = 60, limit_games: int = 4,
                      pool_mode: str = PRIMARY_POOL) -> dict:
    """PIPELINE SMOKE TEST on an IN-SAMPLE season (<= CUTOFF, gate closed). Its numbers are NOT evidence of anything
    (the season is inside every fit) and are never written to the output artifact."""
    _require(season <= CUTOFF and not _GATE['open'], 'SC_COH_1_CLEAN_DRY_RUN_NOT_IN_SAMPLE', str(season))
    frozen = json.loads(FROZEN.read_text())
    tg, pgr, rh = load_team_game(), load_player_game(), load_role_history()
    fits = {'football_residuals': fit_football_residuals(tg), 'shared_state': fit_shared_state(tg),
            'efficiency': fit_efficiency(pgr), 'variance_components': fit_variance_components(pgr),
            'usage': fit_usage(pgr, rh), 'dst_bands': fit_dst_bands(tg), 'int_rate': fit_int_rate()}
    lib = build_clean_library(LIB_SEASONS, tg)
    fr, fp_ = season_frames(season), season_frames(season - 1)
    conc = estimate_concentration(season_frames(CONC_SEASON))
    return score_pool(pool_mode, tuple(weeks), fr, fp_, tg_by_club_season(tg), points_table(tg),
                      dst_rates_table(season, fr, fp_), build_incumbent_model(fits), lib, conc, fits, frozen,
                      n_worlds, limit_games, season=season)


def check_phase_preconditions(phase, phases, code_sha, n_worlds, limit_games, pool_modes):
    """Confirmation is read ONCE, only after a development run of the SAME code, only as registered."""
    _require(phase in ('development', 'confirmation'), 'SC_COH_1_CLEAN_PHASE', phase)
    _require('confirmation' not in phases, 'SC_COH_1_CLEAN_CONFIRMATION_ALREADY_READ',
             'the confirmation weeks have been scored once; no further scoring of either phase is allowed')
    if phase == 'confirmation':
        _require('development' in phases, 'SC_COH_1_CLEAN_NO_DEVELOPMENT_RUN', 'run development first')
        _require(phases['development']['code_sha256'] == code_sha, 'SC_COH_1_CLEAN_CODE_CHANGED_SINCE_DEVELOPMENT',
                 'the harness changed after the last development run; re-run development before confirmation')
        _require(n_worlds == N_WORLDS and limit_games is None and tuple(pool_modes) == POOL_MODES,
                 'SC_COH_1_CLEAN_CONFIRMATION_NOT_AS_REGISTERED', 'confirmation runs only the registered design')
    return True


def run_phase(phase: str, n_worlds: int = N_WORLDS, pool_modes=POOL_MODES, limit_games: int = None) -> dict:
    _require(phase in ('development', 'confirmation'), 'SC_COH_1_CLEAN_PHASE', phase)
    lk = verify_prereg()
    frozen = json.loads(FROZEN.read_text())
    code_sha = _sha(__file__)
    prior = json.loads(OUT.read_text()) if OUT.exists() else {}
    phases = prior.get('phases') or {}
    check_phase_preconditions(phase, phases, code_sha, n_worlds, limit_games, pool_modes)
    # recompute the <= 2024 fits with the gate CLOSED and require them identical to the frozen ones
    tg0, pgr, rh = load_team_game(), load_player_game(), load_role_history()
    fits = {'football_residuals': fit_football_residuals(tg0), 'shared_state': fit_shared_state(tg0),
            'efficiency': fit_efficiency(pgr), 'variance_components': fit_variance_components(pgr),
            'usage': fit_usage(pgr, rh), 'dst_bands': fit_dst_bands(tg0), 'int_rate': fit_int_rate()}
    _require(_sha_bytes(_canon(fits)) == frozen['fits_sha256'], 'SC_COH_1_CLEAN_FITS_NOT_REPRODUCED',
             'the <= 2024 refits differ from the frozen ones')
    lib = build_clean_library(LIB_SEASONS, tg0)
    _require(lib.describe() == frozen['library'], 'SC_COH_1_CLEAN_FITS_NOT_REPRODUCED', 'library differs')
    f2024 = season_frames(CUTOFF)
    conc = estimate_concentration(f2024)
    _require(_canon(conc) == _canon(frozen['concentration']), 'SC_COH_1_CLEAN_FITS_NOT_REPRODUCED', 'concentration')
    model = build_incumbent_model(fits)
    attempts = list(phases.get('confirmation_attempts') or [PRE_LOGGING_ATTEMPT])
    if phase == 'confirmation':
        # recorded BEFORE any confirmation row is read, so a crashed attempt can never vanish
        attempts.append({'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'code_sha256': code_sha,
                         'status': 'STARTED'})
        phases['confirmation_attempts'] = attempts
        OUT.write_text(json.dumps(compose_output(prior, phases, frozen, lk), indent=1, default=float))
    # ---------------------------------------------------------------- open the gate for this phase only
    weeks = DEV_WEEKS if phase == 'development' else CONF_WEEKS
    _GATE.update(open=True, max_week=max(weeks), phase=phase)
    _pbp_raw.cache_clear()
    try:
        tg = load_team_game()
        table = points_table(tg)
        tgc = tg_by_club_season(tg)
        fr = season_frames(EVAL_SEASON)
        rates = dst_rates_table(EVAL_SEASON, fr, f2024)
        res = {'phase': phase, 'weeks': list(weeks), 'prereg_sha256': lk['prereg_sha256'],
               'frozen_sha256': lk['frozen_sha256'], 'code_sha256': code_sha, 'n_worlds': n_worlds,
               'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'pools': {}}
        for mode in pool_modes:
            res['pools'][mode] = score_pool(mode, weeks, fr, f2024, tgc, table, rates, model, lib, conc, fits,
                                            frozen, n_worlds, limit_games)
        res['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    finally:
        _GATE.update(open=False, max_week=0, phase=None)
        _pbp_raw.cache_clear()
    if phase == 'development':
        res['development_run_number'] = int((phases.get('development') or {}).get('development_run_number', 0)) + 1
    else:
        attempts[-1]['status'] = 'COMPLETED'
        attempts[-1]['finished_at'] = res['finished_at']
        res['attempt_number'] = len(attempts)
    phases[phase] = res
    doc = compose_output(prior, phases, frozen, lk)
    OUT.write_text(json.dumps(doc, indent=1, default=float))
    return doc


def score_pool(mode, weeks, fr, f2024, tgc, table, rates, model, lib, conc, fits, frozen, n_worlds, limit_games,
               season=EVAL_SEASON):
    from nfl.sim import game as _G  # noqa: F401  (import check: the incumbent exists)
    pools, excl = build_pools(fr['pg'], fr['sched'], mode, weeks=set(weeks), prev_pg=f2024['pg'])
    pgi = fr['pg'].set_index(['game_id', 'team', 'pid'])
    sc = frozen['scales']
    vec_sd = np.array([sc['pts']['sd'], sc['pts']['sd']] + [sc[r]['sd'] for r in ROLES] * 2)
    events = {'team_pts_ge_p90': ('pts', sc['pts']['p90']), 'team_off_td_ge_p90': ('off_td', sc['off_td']['p90']),
              **{f'{r}_dk_ge_p90': (r, sc[r]['p90']) for r in ROLES}}
    games = []
    for g in fr['sched'].sort_values('game_id').itertuples(index=False):
        if int(g.week) in weeks and (g.game_id, g.home) in pools and (g.game_id, g.away) in pools:
            games.append(g)
    game_excl = sorted({e['game_id'] for e in excl})
    if limit_games:
        games = games[:limit_games]
    _require(len(games) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'{mode}: no scorable game in weeks {weeks}')
    unit_rows = []                     # (variant, game, week, var, crps, ls, ls_valid, floored, pit, c50, c80, c90)
    joint_rows = []                    # (variant, game, week, es, vs, n_dims)
    brier_rows = []                    # (variant, game, week, event, brier)
    cons = {v: collections.defaultdict(collections.Counter) for v in ('INCUMBENT', 'CANDIDATE')}
    coh_ss = {v: {} for v in VARIANTS + ('HISTORY',)}
    oop = collections.Counter()
    refused = []
    rng_pit = np.random.default_rng(PIT_SEED)
    hist_cons = collections.Counter()
    for gi, g in enumerate(games):
        c = football_centre(table, g.home, g.away, season, int(g.week))
        if c is None:
            refused.append({'game_id': g.game_id, 'reason': 'NO_FOOTBALL_CENTRE'})
            continue
        spec = game_spec(g, pools, c)
        vol = {t: volume_centre(tgc, t, season, int(g.week)) for t in (g.home, g.away)}
        if any(v is None for v in vol.values()):
            refused.append({'game_id': g.game_id, 'reason': 'NO_VOLUME_CENTRE'})
            continue
        seed = SIM_SEED + gi
        try:
            inc0 = simulate_incumbent(model, spec, vol, n_worlds, seed)
        except CleanEvalError as e:
            refused.append({'game_id': g.game_id, 'reason': e.code, 'detail': str(e)[:200]})
            continue
        cand0 = simulate_candidate(lib, conc, spec, n_worlds, seed)
        pg2 = {g.home: pools[(g.game_id, g.home)], g.away: pools[(g.game_id, g.away)]}
        opp_c = {g.home: c['away_expected'], g.away: c['home_expected']}
        dtg = {t: dst_target(rates, t, int(g.week), opp_c[t], fits['football_residuals']['pa_res'])
               for t in (g.home, g.away)}
        inc1 = stage_efficiency(inc0, pg2, fits['int_rate']['int_per_attempt'], seed + 99)
        inc2 = stage_dst_anchor(inc1, dtg)
        cand1 = stage_efficiency(cand0, pg2, fits['int_rate']['int_per_attempt'], seed + 99)
        cand2 = stage_dst_anchor(cand1, dtg)
        for who, stages in (('INCUMBENT', (('S0_raw_simulator', inc0), ('S1_after_efficiency_worlds', inc1),
                                           ('S2_after_dst_anchor', inc2))),
                            ('CANDIDATE', (('S0_raw_library', cand0), ('S1_after_efficiency_worlds', cand1),
                                           ('S2_after_dst_anchor', cand2)))):
            for sname, w in stages:
                conservation(spec, w, cons[who][sname])
        history_conservation(fr, [g.game_id], hist_cons)
        variants = {'INCUMBENT_PROD': inc2, 'INCUMBENT_RAW': inc0, 'CANDIDATE_RAW': cand0, 'CANDIDATE_POST': cand2}
        # ---- actuals
        act_club = {t: club_actuals(fr, g.game_id, t, None) for t in (g.home, g.away)}
        played = fr['pg'][fr['pg'].game_id == g.game_id]
        for t in (g.home, g.away):
            inpool = {p['pid'] for p in pools[(g.game_id, t)]['players']}
            x = played[(played.team == t)]
            out_ = x[~x.pid.isin(inpool)]
            oop['club_games'] += 1
            oop['players_played'] += len(x)
            oop['players_played_not_in_pool'] += len(out_)
            oop['dk_core_of_players_not_in_pool'] += float(out_.dk.sum())
            oop['dk_core_all_players'] += float(x.dk.sum())
            oop['pool_players'] += len(inpool)
            oop['pool_players_no_recorded_play'] += len(inpool - set(x.pid))
        yv = []
        for t in (g.home, g.away):
            yv.append(act_club[t]['team_points'])
        role_ids = []
        for t in (g.home, g.away):
            for r in ROLES:
                pid = pools[(g.game_id, t)]['roles'][r]
                role_ids.append((t, pid))
        vec_ok = all(pid is not None for _, pid in role_ids)
        if vec_ok:
            for t, pid in role_ids:
                yv.append(float(dk_core_arr(actual_stat_row(pgi, g.game_id, t, pid))))
        yv = np.array(yv) / vec_sd if vec_ok else None
        hist_unit = _history_unit_rows(fr, g, pools, pgi, act_club)
        _acc_coh(coh_ss['HISTORY'], hist_unit, g.game_id)
        for vname, w in variants.items():
            for sc_ in spec['clubs']:
                t = sc_['club']
                sims = club_sim(w, sc_)
                for var in CLUB_VARS:
                    unit_rows.append(_score_unit(vname, g, 'club_' + var, sims[var][None, :],
                                                 np.array([act_club[t][var]]), rng_pit))
                for p in sc_['players']:
                    S = w['players'][p['id']]
                    a = actual_stat_row(pgi, g.game_id, t, p['pid'])
                    for var, (fn, poss) in PLAYER_VARS.items():
                        if poss is not None and p['position'] not in poss:
                            continue
                        unit_rows.append(_score_unit(vname, g, 'player_' + var, fn(S)[None, :],
                                                     np.array([float(fn(a))]), rng_pit))
            # joint vector
            sim_units_ = _sim_unit_rows(w, spec, pools, g)
            _acc_coh(coh_ss[vname], sim_units_, g.game_id)
            if vec_ok:
                cols = [np.asarray(w['club_points'][g.home], float), np.asarray(w['club_points'][g.away], float)]
                for t, pid in role_ids:
                    cols.append(dk_core_arr(w['players'][player_key(pid, t)]))
                X = np.stack(cols, 1) / vec_sd
                joint_rows.append((vname, g.game_id, int(g.week), energy_score(X, yv), variogram_score(X, yv), X.shape[1]))
            for ev, (col, thr) in events.items():
                for t in (g.home, g.away):
                    if col == 'pts':
                        s, y = np.asarray(w['club_points'][t], float), act_club[t]['team_points']
                    elif col == 'off_td':
                        s, y = np.asarray(w['club_td'][t], float), act_club[t]['team_off_td']
                    else:
                        pid = pools[(g.game_id, t)]['roles'][col]
                        if pid is None:
                            continue
                        s = dk_core_arr(w['players'][player_key(pid, t)])
                        y = float(dk_core_arr(actual_stat_row(pgi, g.game_id, t, pid)))
                    pr = float((s >= thr - 1e-9).mean())
                    brier_rows.append((vname, g.game_id, int(g.week), ev, (pr - float(y >= thr - 1e-9)) ** 2))
    return summarise_pool(mode, games, refused, excl, game_excl, unit_rows, joint_rows, brier_rows, cons, hist_cons,
                          coh_ss, oop, frozen, pools)


def _score_unit(vname, g, var, X, y, rng):
    crps = float(crps_draws(X, y)[0])
    valid = is_integral(X) and is_integral(y)
    if valid:
        ls, fl = count_log_score(X, y)
        ls, fl = float(ls[0]), bool(fl[0])
    else:
        ls, fl = np.nan, False
    pit = float(randomized_pit(X, y, rng)[0])
    cov = [float(central_coverage(X, y, lv)[0]) for lv in LEVELS]
    return (vname, g.game_id, int(g.week), var, crps, ls, valid, fl, pit, *cov)


def _history_unit_rows(fr, g, pools, pgi, act_club):
    rows = []
    tdk = fr['pg'][fr['pg'].game_id == g.game_id].groupby('team').dk.sum()
    for t in (g.home, g.away):
        a = act_club[t]
        r = {'game_id': g.game_id, 'week': int(g.week), 'team': t, 'pts': a['team_points'], 'off_td': a['team_off_td'],
             'yards': a['team_pass_yards'] + a['team_rush_yards'], 'pass_yds': a['team_pass_yards'],
             'pass_td': float(fr['plays'][(fr['plays'].game_id == g.game_id) & (fr['plays'].team == t)].ptd.sum()),
             'off_dk': float(tdk.get(t, 0.0)), 'DST': a['dst_dk']}
        for role, pid in pools[(g.game_id, t)]['roles'].items():
            r[role] = float(dk_core_arr(actual_stat_row(pgi, g.game_id, t, pid))) if pid else np.nan
        rows.append(r)
    return M.add_opponent(pd.DataFrame(rows))


def _sim_unit_rows(w, spec, pools, g):
    rows = []
    n = len(next(iter(w['club_points'].values())))
    for sc_ in spec['clubs']:
        t = sc_['club']
        S = np.stack([w['players'][p['id']] for p in sc_['players']])
        qb = np.array([p['position'] == 'QB' for p in sc_['players']])
        dk = dk_core_arr(S)
        col = {p['id']: dk[j] for j, p in enumerate(sc_['players'])}
        pyd = S[qb, :, SX['pass_yards']].sum(0)
        df = pd.DataFrame({'game_id': g.game_id, 'week': int(g.week), 'world': np.arange(n), 'team': t,
                           'pts': np.asarray(w['club_points'][t], float), 'off_td': np.asarray(w['club_td'][t], float),
                           'yards': pyd + S[:, :, SX['rush_yards']].sum(0), 'pass_yds': pyd,
                           'pass_td': S[qb, :, SX['pass_td']].sum(0), 'off_dk': dk.sum(0),
                           'DST': np.asarray(w['dst_dk'][t], float)})
        for role, pid in pools[(g.game_id, t)]['roles'].items():
            df[role] = col[player_key(pid, t)] if pid else np.nan
        rows.append(df)
    return M.add_opponent(pd.concat(rows, ignore_index=True))


def _acc_coh(store, units, gid):
    for name, x, y, kind, _ in M.STATS:
        store.setdefault(name, {})[gid] = M.suffstats(units, x, y, [gid])[0]


def summarise_pool(mode, games, refused, excl, game_excl, unit_rows, joint_rows, brier_rows, cons, hist_cons, coh_ss,
                   oop, frozen, pools):
    ref_ids = {r['game_id'] for r in refused}
    gl = [g.game_id for g in games if g.game_id not in ref_ids]
    _require(len(gl) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', f'{mode}: every game refused')
    weeks = {g.game_id: int(g.week) for g in games}
    Wb = _boot_weights(gl, weeks, np.random.default_rng(BOOT_SEED))
    gi = {g: i for i, g in enumerate(gl)}
    U = pd.DataFrame(unit_rows, columns=['variant', 'game_id', 'week', 'var', 'crps', 'ls', 'ls_valid', 'floored',
                                         'pit', 'c50', 'c80', 'c90'])
    _require(len(U) > 0, 'SC_COH_1_CLEAN_EMPTY_INPUT', 'no scored units')

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
    pairs = (PRIMARY_PAIR, ('CANDIDATE_RAW', 'INCUMBENT_RAW'), ('CANDIDATE_POST', 'INCUMBENT_PROD'))
    for var, x in U.groupby('var'):
        r = {'crps': {}, 'coverage': {}, 'pit': {}, 'log_score': {}}
        for a, b in pairs:
            r['crps'].update(summarise_metric(per_game(x, 'crps'), gl, weeks, Wb, a, b))
        for lv, col in zip(LEVELS, ('c50', 'c80', 'c90')):
            r['coverage'][str(lv)] = {v: z for v, z in summarise_metric(per_game(x, col), gl, weeks, Wb, *PRIMARY_PAIR)
                                      .items()}
        for v, z in x.groupby('variant'):
            h = np.histogram(z.pit.to_numpy(), bins=PIT_BINS, range=(0, 1))[0]
            r['pit'][v] = {'histogram': h.tolist(), 'n': int(h.sum()),
                           'sum_abs_bin_dev_from_uniform': round(float(np.abs(h / h.sum() - 1 / PIT_BINS).sum()), 4)}
        valid_all = x.groupby(['game_id', 'week', 'var']).ls_valid  # noqa: F841
        lsv = {v: bool(z.ls_valid.all()) for v, z in x.groupby('variant')}
        r['log_score']['support_valid'] = lsv
        lsx = x[x.variant.isin([v for v, ok in lsv.items() if ok])]
        if len(lsx):
            for a, b in pairs:
                if lsv.get(a) and lsv.get(b):
                    r['log_score'].update(summarise_metric(per_game(lsx, 'ls'), gl, weeks, Wb, a, b))
            r['log_score']['n_floored'] = {v: int(z.floored.sum()) for v, z in lsx.groupby('variant')}
            r['log_score']['FLOOR_RULE'] = 'p_hat = max(count, 0.5) / M (half-draw floor)'
        marg[var] = r
    J = pd.DataFrame(joint_rows, columns=['variant', 'game_id', 'week', 'es', 'vs', 'd'])
    joint = {}
    if len(J):
        for col in ('es', 'vs'):
            joint[col] = {}
            for a, b in pairs:
                joint[col].update(summarise_metric(per_game(J, col), gl, weeks, Wb, a, b))
    B = pd.DataFrame(brier_rows, columns=['variant', 'game_id', 'week', 'event', 'brier'])
    brier = {}
    for ev, x in B.groupby('event'):
        brier[ev] = {}
        for a, b in pairs:
            brier[ev].update(summarise_metric(per_game(x, 'brier'), gl, weeks, Wb, a, b))
    coh = coherence_summary(coh_ss, gl, Wb, frozen['equivalence_margins'])
    cons_out = {who: {s: dict(c) for s, c in st.items()} for who, st in cons.items()}
    decision = primary_decision(joint, marg)
    return {'pool_mode': mode, 'n_games_scored': len(gl), 'games_refused': refused,
            'club_games_excluded_missing_input': excl, 'games_excluded_missing_input': game_excl,
            'out_of_pool_account': dict(oop), 'marginal': marg, 'joint': joint, 'brier_tail_events': brier,
            'coherence_vs_history': coh, 'conservation_counts_per_stage': cons_out,
            'conservation_history_baseline': dict(hist_cons), 'conservation_not_represented': NOT_REPRESENTED,
            'primary_decision': decision}


def coherence_summary(ss, games, Wb, margins):
    out = {}
    for name, x, y, kind, meaning in M.STATS:
        H = np.stack([ss['HISTORY'][name][g] for g in games])
        hv = float(M._stat(H.sum(0), kind))
        row = {'meaning': meaning, 'history': round(hv, 4), 'equivalence_margin': margins[name]['margin']}
        for v in VARIANTS:
            S = np.stack([ss[v][name][g] for g in games])
            sv = float(M._stat(S.sum(0), kind))
            gap = sv - hv
            r = {'value': round(sv, 4), 'gap': round(gap, 4)}
            inside = True
            for blk in ('game', 'week'):
                d = M._stat(Wb[blk] @ S, kind) - M._stat(Wb[blk] @ H, kind)
                r[f'gap_ci95_{blk}_block'] = _ci(d)
                c90 = _ci(d, 5, 95)
                r[f'gap_ci90_{blk}_block'] = c90
                m = margins[name]['margin']
                inside = inside and c90 is not None and (-m < c90[0]) and (c90[1] < m)
            r['label'] = 'WITHIN_PREDECLARED_EQUIVALENCE_MARGIN_TOST' if inside else 'NOT_SHOWN_EQUIVALENT'
            row[v] = r
        out[name] = row
    return out


def primary_decision(joint, marg):
    """Pre-registered conjunctive rule (P1-P4), read off both blocking schemes. Labels only; nothing is promoted."""
    a, b = PRIMARY_PAIR
    key = f'{a}_vs_{b}'
    res = {}

    def upper(r, blk):
        c = r.get(f'ratio_ci95_{blk}_block') if r else None
        return c[1] if c else None
    for name, r, kind in (('P1_energy_score', (joint.get('es') or {}).get(key), 'superior'),
                          ('P2_variogram_score', (joint.get('vs') or {}).get(key), 'superior'),
                          ('P3_team_points_crps', marg.get('club_team_points', {}).get('crps', {}).get(key), 'noninferior'),
                          ('P4_player_dk_crps', marg.get('player_dk', {}).get('crps', {}).get(key), 'noninferior')):
        ups = [upper(r, blk) for blk in ('game', 'week')]
        thr = 1.0 if kind == 'superior' else NI_RATIO_MARGIN
        ok = all(u is not None and u < thr for u in ups)
        res[name] = {'test': kind, 'ratio': (r or {}).get('ratio'), 'ratio_upper95_game_block': ups[0],
                     'ratio_upper95_week_block': ups[1], 'threshold': thr, 'passed': ok}
    res['ALL_FOUR_PASSED'] = all(v['passed'] for v in res.values() if isinstance(v, dict))
    res['READING'] = ('a conjunctive rule (every component must pass at a two-sided 95% bootstrap interval under BOTH '
                      'game- and week-blocked resampling), so no multiplicity adjustment is needed for the joint claim. '
                      'Passing is a SHADOW label; it promotes nothing.')
    return res


# ================================================================================================ output
def contamination_audit():
    """Every input of the incumbent and the candidate in the clean path."""
    A = []

    def row(side, name, source, cutoff, market, outcome, pit, note=''):
        A.append({'side': side, 'input': name, 'source': source, 'cutoff': cutoff, 'market_derived': market,
                  'outcome_derived': outcome, 'point_in_time': pit, 'note': note})
    row('BOTH', 'scoring centre (total, home margin, club expected points)',
        'nfl/sim/football_points.expected_points on TEAM_GAME points (whitelisted fields)',
        'eval season weeks < W + prior season', 'NO', 'prior-game outcomes only', 'YES',
        "production's FOOTBALL_ONLY centre function, unchanged")
    row('INCUMBENT', 'total / margin residual sets', 'football_points.build procedure re-run', '2001-2024', 'NO',
        'YES (<= 2024 fit)', 'YES', 'production FOOTBALL_POINTS.json fits 2001-2025; refitted, not read')
    row('INCUMBENT', 'plays / pass-share volume response, realised volume', 'shared_state.build procedure (stats.ols)',
        '<= 2024 (TEAM_GAME 2021-2024 have volume)', 'NO', 'YES (<= 2024 fit)', 'YES',
        'production SHARED_STATE fits 2000-2026 and keeps only club-games with market lines; refit drops that filter')
    row('INCUMBENT', 'points per offensive TD + remainder (TD inversion)', 'shared_state.build scoring regression',
        '<= 2024', 'NO', 'YES (<= 2024 fit)', 'YES')
    row('INCUMBENT', 'empirical club-game YPA / YPC', 'game.fit_efficiency procedure on PLAYER_GAME', '2021-2024', 'NO',
        'YES (<= 2024 fit)', 'YES', 'production EFFICIENCY 2021-2026; refitted')
    row('INCUMBENT', 'yards-share and opportunity-share concentrations', 'variance_components._estimate / '
        'share_dispersion on PLAYER_GAME', '2021-2024', 'NO', 'YES (<= 2024 fit)', 'YES')
    row('INCUMBENT', 'teammate-backs Dirichlet concentration', 'usage._teammate_decomposition on PLAYER_GAME + '
        'ROLE_HISTORY ranks', '2021-2024', 'NO', 'YES (<= 2024 fit)', 'YES')
    row('INCUMBENT', 'DST points-allowed bands', 'dst.build procedure (TEAM_GAME sacks/turnovers + pbp def TD/safety)',
        '<= 2024 (def TD 2021-2024)', 'NO', 'YES (<= 2024 fit)', 'YES')
    row('INCUMBENT', 'club volume centre (pass att, rush att, targets)', 'proj_v1.team_volume FOOTBALL_ONLY blend '
        'replicated on TEAM_GAME', 'eval season weeks < W + prior season', 'NO', 'prior-game outcomes only', 'YES')
    row('INCUMBENT', 'player efficiency centre (efficiency_worlds)', 'player yards / opportunities, weeks < W + 2024',
        'eval season weeks < W + 2024', 'NO', 'prior-game outcomes only', 'YES',
        'production uses proj_v1 conditional_volume; declared approximation')
    row('INCUMBENT', 'interception rate (efficiency_worlds)', 'clean pbp INT / attempts', '2021-2024', 'NO',
        'YES (<= 2024 fit)', 'YES')
    row('INCUMBENT', 'DST anchor target', 'dst_model.project form: blended event rates + pa_expectation around the '
        'opponent football centre with <= 2024 points-allowed residuals', 'eval weeks < W + 2024', 'NO',
        'prior-game outcomes only', 'YES')
    row('BOTH', 'player pool, shares, roles, catch rates', 'clean pbp player-games of the eval season',
        'eval season weeks < W', 'NO', 'prior-game outcomes only; NO evaluated-game row', 'YES',
        'official actives / inactives NOT_IDENTIFIABLE_FROM_CURRENT_DATA')
    row('BOTH', 'player positions', 'players_crosswalk (static)', 'static file', 'NO', 'NO', 'APPROXIMATELY',
        'crosswalk position is a current label, not a dated one')
    row('CANDIDATE', 'analogue play library', 'clean pbp 2021-2024 plays, finals, DST events', '2021-2024', 'NO',
        'YES (<= 2024 library)', 'YES')
    row('CANDIDATE', 'analogue distance (football total, home margin) + scale', 'football_points.expected_points per '
        'library game, point-in-time', '2020-2024', 'NO', 'prior-game outcomes only', 'YES',
        'replaces total_line / spread_line of the original candidate')
    row('CANDIDATE', 'target / carry Dirichlet concentration', 'method of moments on 2024 with point-in-time pools',
        '2024', 'NO', 'YES (<= 2024 fit)', 'YES', 'replaces the snap-count (outcome-derived) pool')
    row('CANDIDATE', 'k neighbours', 'round(sqrt(n_library_games))', 'declared prior', 'NO', 'NO', 'YES')
    return A


def compose_output(prior, phases, frozen, lk):
    return {
        'ARTIFACT': 'SC_COH_1_CLEAN_EVAL', 'STATUS': 'SHADOW_ONLY', 'LAYER': 'RESEARCH',
        'EVIDENCE_CLASS': {
            'development (2025 weeks 2-9)': 'DEVELOPMENT_EVIDENCE: clean inputs, but read before confirmation',
            'confirmation (2025 weeks 10-18)': ('RETROSPECTIVE_CONFIRMATORY_SHADOW: one read after freezing; still a '
                                                'past season, not prospective, and the incumbent replay is not the '
                                                'full live path (see differences_from_live_path)'),
            'coherence labels': 'equivalence only where a predeclared margin and a TOST (90% CI inside) are met'},
        'AUDIT_LADDER': {'reached': ['IMPLEMENTED', 'SUCCESS_TESTED', 'REFUSAL_TESTED', 'ADVERSARIAL_TESTED'],
                         'NOT': ['ON_EXECUTION_PATH', 'PROSPECTIVELY_VALIDATED', 'PROMOTED'],
                         'tests': 'nfl/tests/test_sc_coh_1_clean.py'},
        'NOT_READY_FOR_NEXT_SLATE': ('nothing here is on the production path; the candidate is shadow research '
                                     'and no promotion decision exists'),
        'prereg': {'path': lk['prereg'], 'sha256': lk['prereg_sha256'], 'locked_at': lk['locked_at']},
        'frozen': {'path': lk['frozen'], 'sha256': lk['frozen_sha256'], 'fits_sha256': frozen['fits_sha256'],
                   'library': frozen['library'], 'concentration': frozen['concentration'],
                   'scales': frozen['scales'], 'equivalence_margins': frozen['equivalence_margins']},
        'contamination_audit': contamination_audit(),
        'cannot_be_made_clean': {
            'official_actives_and_inactives': 'NOT_IDENTIFIABLE_FROM_CURRENT_DATA (docs/AGENT_OUTBOX.md 2026-10-07 '
                                              'request for nflverse 2024-2025 weekly rosters and inactives)',
            'proj_v1_player_projections': ('not replayable for historical games (needs dated role state / slate '
                                           'files); replaced by season-to-date shares and opportunity-share TD shares '
                                           'for BOTH providers'),
            'incumbent_inputs_not_cut': 'NONE: every fitted incumbent input was refitted <= 2024 (see audit)'},
        'differences_from_live_path': [
            'shares: season-to-date opportunity shares over a point-in-time pool, not proj_v1 projected volume',
            'TD shares: opportunity shares (validate_correlations precedent), not proj_v1 rec_td / rush_td',
            'efficiency_worlds rows: pooled player yards per opportunity (weeks < W + 2024), not proj_v1 '
            'conditional_volume',
            'DST anchor target: dst_model.project form recomputed from clean pbp, not the proj_v1 DST row',
            'kickers: not simulated or scored (kicker remainder is counted as a conservation check only)',
            'football_sanity gate and role_state: not replayed (they need slate files)',
            'SHARED_STATE refit drops production\'s market-line availability filter',
            'DK scoring: DK core (no bonuses, INT, fumbles) for every provider and the actuals'],
        'SUPERSEDES_AS_EVIDENCE': {
            'artifact': 'nfl/research/coherence/SC_COH_1_MEASUREMENT.json (and SC_COH_1_STATUS.json candidate_result)',
            'reclassified_as': 'DEVELOPMENT_EVIDENCE',
            'reasons': ['market-conditioned candidate: analogues chosen by sportsbook total_line / spread_line '
                        '(sc_coh_1_candidate.py:43,104-111,323), ineligible for production',
                        'outcome-derived pool: offense_snaps > 0 in the evaluated game (sc_coh_1_measure.py:22,226-236)',
                        'incumbent not out of sample (SHARED_STATE 2000-2026, EFFICIENCY 2021-2026) and replayed on '
                        'market lines rather than FOOTBALL_ONLY'],
            'old_artifacts_modified': False},
        'deviations_after_lock': DEVIATIONS,
        'phases': phases,
        'written_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['freeze', 'lock', 'run'])
    ap.add_argument('--phase', choices=['development', 'confirmation'])
    ap.add_argument('--n-worlds', type=int, default=N_WORLDS)
    ap.add_argument('--pool', choices=list(POOL_MODES), action='append')
    ap.add_argument('--limit-games', type=int)
    a = ap.parse_args(argv)
    if a.cmd == 'freeze':
        d = freeze()
        print(FROZEN.relative_to(_REPO), d['fits_sha256'])
        print(json.dumps({'library': d['library'], 'concentration': d['concentration'], 'scales': d['scales'],
                          'margins': {k: v['margin'] for k, v in d['equivalence_margins'].items()},
                          'fit_summary': d['fit_summary']}, indent=1, default=float))
    elif a.cmd == 'lock':
        print(json.dumps(lock(), indent=1))
    else:
        _require(a.phase, 'SC_COH_1_CLEAN_PHASE', '--phase is required')
        d = run_phase(a.phase, a.n_worlds, tuple(a.pool) if a.pool else POOL_MODES, a.limit_games)
        print(OUT.relative_to(_REPO))
        ph = d['phases'][a.phase]
        for mode, r in ph['pools'].items():
            print(mode, 'games', r['n_games_scored'], json.dumps(r['primary_decision'], default=float)[:1500])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
