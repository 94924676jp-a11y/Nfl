#!/usr/bin/env python3.12
"""SC-COH-1 held-out measurement harness: the ACTUAL joint structure of NFL team-games against the joint
structure the Showdown simulator draws for the same games.

    python3.12 nfl/research/coherence/sc_coh_1_measure.py            # incumbent only
    python3.12 nfl/research/coherence/sc_coh_1_measure.py --candidate  # + the shadow candidate

LAYER: RESEARCH / SHADOW_ONLY. Reads committed nflverse play-by-play (nfl/research/postgame/pbp_*.csv.gz), the
committed 2025 snap counts and player crosswalk (nfl/postgame/raw/role_audit_history/), and the incumbent model's
committed inputs through nfl/sim/game.py:Model.load(). Writes ONLY nfl/research/coherence/SC_COH_1_MEASUREMENT.json.
Changes no production file, no forecast, no draw artifact.

DESIGN, DECLARED BEFORE ANY NUMBER WAS READ

  Evaluation games   2025 regular season, weeks 2-18 (week 1 has no season-to-date prior). HELD OUT: no quantity
                     fitted by THIS harness or by the candidate uses a 2025 row. (The INCUMBENT's own inputs --
                     SHARED_STATE 2000-2026, EFFICIENCY from PLAYER_GAME 2021-2026 -- did see 2025; that flatters the
                     incumbent, and is reported, not repaired.)
  Unit               team-game (two per game). Bootstrap resamples GAMES (both team rows together); a week-blocked
                     bootstrap is reported for every gap as a sensitivity, because games in one week share a date.
  Pregame inputs     (identical for history roles, the incumbent replay and the candidate)
                     pool    = players with offense_snaps > 0 in the game (2025 snap counts) at QB/RB/FB/WR/TE. This
                               is an ACTIVE-LIST proxy; it conditions on appearance, as production does once inactives
                               are known, and it is the same set on all three sides.
                     shares  = season-to-date (weeks < W, same club) targets / carries / pass attempts, renormalised
                               over the pool, exactly as nfl/tools/showdown_draws.py:_shares renormalises the projection.
                     TD share= opportunity share (targets for receiving TDs, carries for rushing TDs) -- the precedent
                               declared in nfl/sim/validate_correlations.py. Production uses proj_v1 TD expectations.
                     lines   = nflverse total_line / spread_line (spread positive = home favoured). Production's
                               Showdown arm is FOOTBALL_ONLY (football_points centre) -- a declared difference.
  Roles              QB  = pool QB with most prior pass attempts (fallback: most offense snaps -- declared)
                     WR1, WR2 = pool WRs by prior targets; TE1 = pool TE by prior targets; RB1 = pool RB/FB by prior
                     carries. Never ranked on in-game volume (that would condition on the outcome).
  DK core            0.04 pass yd + 4 pass TD + 0.1 rush yd + 6 rush TD + 0.1 rec yd + 1 rec + 6 rec TD.
                     No yardage bonuses, no INT, no fumbles: the incumbent simulate_game draws neither INT nor fumbles,
                     so they are left out of BOTH sides rather than compared against a zero.
  DST DK             DK tier(opponent final points) + 1 sack + 2 INT + 2 fumble recovery + 6 def/return TD + 2 safety
                     (blocked kicks omitted on the history side; the incumbent's DST_MODEL does not draw them either).
  Incumbent replay   nfl/sim/game.py:simulate_game in its default modes (CLUB_TOTAL_IMPOSED, DIRICHLET), the market-
                     line arm, no projection centring and no efficiency_worlds post-step. Both of those are on the live
                     Showdown path (nfl/tools/showdown_slate_run.py:76,90) and are NOT replayed; efficiency_worlds is
                     audited separately on the archived ATL@NO worlds because it rescales yards per player.

NOTHING HERE IS A VERDICT. Gaps are reported with intervals; no equivalence margin was predeclared, so no statistic
is called "matched", "closed" or "correct".
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import json
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'SC_COH_1_MEASUREMENT.json'
PBP_DIR = _REPO / 'nfl/research/postgame'
RAW = _REPO / 'nfl/postgame/raw/role_audit_history'
SNAPS = {2024: RAW / 'snap_counts_2024.a2aa58efe093f8aa.csv.gz', 2025: RAW / 'snap_counts_2025.3fc2deb0e9ad86d3.csv.gz'}
CROSSWALK = RAW / 'players_crosswalk.bea61fc25c863150.csv.gz'

EVAL_SEASON = 2025
FIT_SEASONS = (2021, 2022, 2023, 2024)
MAX_FIT_SEASON = 2024
FIRST_EVAL_WEEK = 2
N_BOOT = 1000
BOOT_SEED = 20261007
N_WORLDS = 400          # worlds per replayed game; MC error on a pooled correlation is ~1/sqrt(G*K), far below the
SIM_SEED = 20261007     # between-game bootstrap spread, which is what the intervals report
SKILL = ('QB', 'RB', 'WR', 'TE')
POS_MAP = {'QB': 'QB', 'RB': 'RB', 'HB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE'}
CATCH_RATE_FALLBACK = {'WR': 0.63, 'TE': 0.70, 'RB': 0.75}   # same fallback as nfl/tools/showdown_draws.py:CATCH_RATE

PBP_COLS = ['game_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'home_team', 'away_team', 'play_type',
            'passer_player_id', 'receiver_player_id', 'rusher_player_id', 'passing_yards', 'receiving_yards',
            'rushing_yards', 'complete_pass', 'pass_attempt', 'sack', 'pass_touchdown', 'rush_touchdown',
            'interception', 'fumble_lost', 'td_team', 'safety', 'two_point_attempt', 'home_score', 'away_score',
            'total_line', 'spread_line']


class CoherenceInputError(RuntimeError):
    """A named refusal. `code` is the machine-readable reason; an empty or partial input is never a result."""

    def __init__(self, code, detail=''):
        super().__init__(f'{code}: {detail}')
        self.code = code


def _require(ok, code, detail=''):
    if not ok:
        raise CoherenceInputError(code, detail)


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def pbp_path(season):
    c = sorted(PBP_DIR.glob(f'pbp_{season}.*.csv.gz'))
    _require(len(c) == 1, 'SC_COH_1_PBP_AMBIGUOUS', f'season {season}: {[p.name for p in c]}')
    return c[0]


@functools.lru_cache(maxsize=None)
def load_pbp(season: int) -> pd.DataFrame:
    df = pd.read_csv(pbp_path(season), usecols=lambda c: c in PBP_COLS, low_memory=False)
    df = df[df.season_type == 'REG'].copy()
    _require(len(df) > 1000, 'SC_COH_1_EMPTY_INPUT', f'pbp {season} has {len(df)} REG rows')
    _require(set(PBP_COLS) <= set(df.columns), 'SC_COH_1_SCHEMA', f'missing {set(PBP_COLS) - set(df.columns)}')
    _require(int(df.season.min()) == int(df.season.max()) == season, 'SC_COH_1_SEASON_MISMATCH',
             f'file for {season} carries seasons {sorted(df.season.unique())}')
    return df


def offensive_plays(df: pd.DataFrame) -> pd.DataFrame:
    """Scrimmage plays only (pass / run, no two-point tries). Sacks are kept with att = 0 (DK does not charge the
    passer for sack yards and nothing is credited). One row per play."""
    _require(len(df) > 0, 'SC_COH_1_EMPTY_INPUT', 'no play-by-play rows')
    f = df[df.play_type.isin(['pass', 'run']) & (df.two_point_attempt.fillna(0) != 1)].copy()
    _require(len(f) > 0, 'SC_COH_1_EMPTY_INPUT', 'no scrimmage plays')
    for c in ('passing_yards', 'receiving_yards', 'rushing_yards', 'complete_pass', 'pass_attempt', 'sack',
              'pass_touchdown', 'rush_touchdown', 'interception'):
        f[c] = f[c].fillna(0).astype(float)
    is_pass = f.play_type == 'pass'
    out = pd.DataFrame({
        'game_id': f.game_id, 'season': f.season.astype(int), 'week': f.week.astype(int), 'team': f.posteam,
        'kind': np.where(is_pass, 'pass', 'run'),
        'passer': f.passer_player_id.where(is_pass), 'receiver': f.receiver_player_id.where(is_pass),
        'rusher': f.rusher_player_id.where(~is_pass),
        'att': (is_pass & (f.sack == 0) & (f.pass_attempt == 1)).astype(int),
        'cmp': (is_pass & (f.complete_pass == 1)).astype(int),
        'pyds': np.where(is_pass, f.passing_yards, 0.0),
        'recyds': np.where(is_pass, f.receiving_yards, 0.0),
        'ptd': np.where(is_pass, f.pass_touchdown, 0.0).astype(int),
        'rushyds': np.where(~is_pass, f.rushing_yards, 0.0),
        'rtd': np.where(~is_pass, f.rush_touchdown, 0.0).astype(int),
    })
    return out.reset_index(drop=True)


def finals(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby('game_id').agg(season=('season', 'first'), week=('week', 'first'), home=('home_team', 'first'),
                                  away=('away_team', 'first'), hs=('home_score', 'max'), as_=('away_score', 'max'),
                                  total_line=('total_line', 'first'), spread_line=('spread_line', 'first'))
    g = g.reset_index()
    _require(len(g) > 0 and g[['hs', 'as_', 'total_line', 'spread_line']].notna().all().all(),
             'SC_COH_1_FINALS_INCOMPLETE', 'a game lacks a final score or a line')
    return g


def player_games(plays: pd.DataFrame) -> pd.DataFrame:
    """Per (game, team, player): the ten simulator stat fields plus DK core."""
    p = plays
    parts = [
        pd.DataFrame({'game_id': p.game_id, 'season': p.season, 'week': p.week, 'team': p.team, 'pid': p.passer,
                      'pass_att': p.att, 'pass_yards': p.pyds, 'pass_td': p.ptd}).dropna(subset=['pid']),
        pd.DataFrame({'game_id': p.game_id, 'season': p.season, 'week': p.week, 'team': p.team, 'pid': p.receiver,
                      'targets': 1, 'receptions': p.cmp, 'rec_yards': p.recyds, 'rec_td': p.ptd}
                     ).dropna(subset=['pid']),
        pd.DataFrame({'game_id': p.game_id, 'season': p.season, 'week': p.week, 'team': p.team, 'pid': p.rusher,
                      'carries': 1, 'rush_yards': p.rushyds, 'rush_td': p.rtd}).dropna(subset=['pid']),
    ]
    pg = pd.concat(parts, ignore_index=True).fillna(0)
    pg = pg.groupby(['game_id', 'season', 'week', 'team', 'pid'], as_index=False).sum(numeric_only=True)
    for c in ('pass_att', 'pass_yards', 'pass_td', 'targets', 'receptions', 'rec_yards', 'rec_td', 'carries',
              'rush_yards', 'rush_td'):
        if c not in pg:
            pg[c] = 0.0
    pg['dk'] = dk_core(pg)
    return pg


def dk_core(x) -> np.ndarray:
    return (0.04 * x['pass_yards'] + 4 * x['pass_td'] + 0.1 * x['rush_yards'] + 6 * x['rush_td']
            + 0.1 * x['rec_yards'] + x['receptions'] + 6 * x['rec_td'])


def dst_tier(points_allowed):
    from nfl.sim import dst as dst_mod
    return np.array([dst_mod.tier(float(v)) for v in np.atleast_1d(points_allowed)])


def dst_games(df: pd.DataFrame, fin: pd.DataFrame) -> pd.DataFrame:
    """Per (game, defence): sacks, INT, fumble recoveries on scrimmage plays, non-offensive TDs, safeties, DK."""
    f = df.copy()
    for c in ('sack', 'interception', 'fumble_lost', 'safety', 'pass_touchdown', 'rush_touchdown'):
        f[c] = f[c].fillna(0)
    scr = f.play_type.isin(['pass', 'run'])
    rows = []
    gb = {
        'sacks': f[scr & (f.sack == 1)].groupby(['game_id', 'defteam']).size(),
        'ints': f[scr & (f.interception == 1)].groupby(['game_id', 'defteam']).size(),
        'fumrec': f[scr & (f.fumble_lost == 1)].groupby(['game_id', 'defteam']).size(),
        'safeties': f[f.safety == 1].groupby(['game_id', 'defteam']).size(),
        'dtd': f[f.td_team.notna() & (f.pass_touchdown == 0) & (f.rush_touchdown == 0)].groupby(
            ['game_id', 'td_team']).size().rename_axis(['game_id', 'defteam']),
    }
    for _, g in fin.iterrows():
        for team, opp_pts in ((g.home, g.as_), (g.away, g.hs)):
            r = {'game_id': g.game_id, 'team': team, 'pts_allowed': float(opp_pts)}
            for k, s in gb.items():
                r[k] = float(s.get((g.game_id, team), 0))
            rows.append(r)
    d = pd.DataFrame(rows)
    d['dst_dk'] = (dst_tier(d.pts_allowed.to_numpy()) + d.sacks + 2 * d.ints + 2 * d.fumrec + 6 * d.dtd
                   + 2 * d.safeties)
    return d


@functools.lru_cache(maxsize=None)
def crosswalk() -> pd.DataFrame:
    c = pd.read_csv(CROSSWALK)
    _require(len(c) > 1000, 'SC_COH_1_EMPTY_INPUT', 'player crosswalk empty')
    return c


def snap_pool(season: int) -> pd.DataFrame:
    """(game_id, team, gsis, pos, snaps) for skill players with offense_snaps > 0."""
    _require(season in SNAPS, 'SC_COH_1_NO_SNAPS', f'no committed snap counts for {season}')
    s = pd.read_csv(SNAPS[season])
    s = s[(s.game_type == 'REG') & (s.offense_snaps > 0)].copy()
    s['pos'] = s.position.map(POS_MAP)
    s = s[s.pos.notna()]
    c = crosswalk()[['pfr_id', 'gsis_id']]
    s = s.merge(c, left_on='pfr_player_id', right_on='pfr_id', how='inner')
    _require(len(s) > 0, 'SC_COH_1_EMPTY_INPUT', f'snap pool {season} empty after the crosswalk')
    return s[['game_id', 'team', 'gsis_id', 'pos', 'offense_snaps']].rename(columns={'gsis_id': 'pid'})


def pregame_pools(season: int, pg: pd.DataFrame, pool: pd.DataFrame, first_week: int = FIRST_EVAL_WEEK) -> dict:
    """{(game_id, team): {'players': [...], 'roles': {...}}} built ONLY from weeks < W of the same season and club."""
    _require(len(pg) > 0 and len(pool) > 0, 'SC_COH_1_EMPTY_INPUT', 'player-game or pool empty')
    wk = pg[['game_id', 'week']].drop_duplicates().set_index('game_id').week.to_dict()
    pool = pool[pool.game_id.map(lambda g: wk.get(g, 0) >= first_week)]
    tot = pg.sort_values('week')
    out = {}
    for (gid, team), x in pool.groupby(['game_id', 'team']):
        w = wk[gid]
        prior = tot[(tot.team == team) & (tot.week < w)]
        _require(prior.week.max() < w if len(prior) else True, 'SC_COH_1_PRIOR_LEAK', f'{gid} {team}')
        pr = prior.groupby('pid')[['targets', 'carries', 'pass_att', 'receptions']].sum()
        players = []
        for _, r in x.iterrows():
            a = pr.loc[r.pid] if r.pid in pr.index else None
            tg = float(a.targets) if a is not None else 0.0
            players.append({'pid': r.pid, 'pos': r.pos, 'snaps': float(r.offense_snaps),
                            'prior_targets': tg, 'prior_carries': float(a.carries) if a is not None else 0.0,
                            'prior_pass_att': float(a.pass_att) if a is not None else 0.0,
                            'catch_rate': (float(a.receptions) / tg) if tg > 0 else CATCH_RATE_FALLBACK.get(r.pos, 0.65)})
        T = sum(p['prior_targets'] for p in players if p['pos'] != 'QB')
        C = sum(p['prior_carries'] for p in players)
        A = sum(p['prior_pass_att'] for p in players if p['pos'] == 'QB')
        qbs = [p for p in players if p['pos'] == 'QB']
        if T <= 0 or C <= 0 or not qbs:
            continue
        if A <= 0:     # no pool QB has a prior attempt: the snap leader is the starter (declared fallback)
            top = max(qbs, key=lambda p: p['snaps'])
            for p in qbs:
                p['prior_pass_att'] = 1.0 if p is top else 0.0
            A = 1.0
        for p in players:
            p['target_share'] = p['prior_targets'] / T if p['pos'] != 'QB' else 0.0
            p['carry_share'] = p['prior_carries'] / C
            p['pass_att_share'] = p['prior_pass_att'] / A if p['pos'] == 'QB' else 0.0
        rank = lambda pos, key: sorted([p for p in players if p['pos'] == pos and p[key] > 0],
                                       key=lambda p: (-p[key], p['pid']))
        qb = max(qbs, key=lambda p: (p['prior_pass_att'], p['snaps']))
        wr, te, rb = rank('WR', 'prior_targets'), rank('TE', 'prior_targets'), rank('RB', 'prior_carries')
        roles = {'QB': qb['pid'], 'WR1': wr[0]['pid'] if len(wr) > 0 else None,
                 'WR2': wr[1]['pid'] if len(wr) > 1 else None, 'TE1': te[0]['pid'] if te else None,
                 'RB1': rb[0]['pid'] if rb else None}
        out[(gid, team)] = {'players': players, 'roles': roles, 'week': w}
    _require(len(out) > 0, 'SC_COH_1_EMPTY_INPUT', 'no club-game has a usable pregame pool')
    return out


# ============================================================================== the measured units
UNIT_COLS = ('pts', 'off_td', 'yards', 'pass_yds', 'pass_td', 'off_dk', 'QB', 'WR1', 'WR2', 'TE1', 'RB1', 'DST')


def history_units(season: int = EVAL_SEASON):
    """Actual team-game rows for the evaluation games, roles from pregame pools. Returns (units, pools, fin)."""
    df = load_pbp(season)
    plays = offensive_plays(df)
    fin = finals(df)
    pg = player_games(plays)
    pools = pregame_pools(season, pg, snap_pool(season))
    dst = dst_games(df, fin).set_index(['game_id', 'team'])
    team = plays.groupby(['game_id', 'team']).agg(pass_yds=('pyds', 'sum'), rush_yds=('rushyds', 'sum'),
                                                  pass_td=('ptd', 'sum'), rush_td=('rtd', 'sum'))
    pgi = pg.set_index(['game_id', 'team', 'pid']).dk
    tdk = pg.groupby(['game_id', 'team']).dk.sum()
    rows = []
    for _, g in fin.iterrows():
        keys = [(g.game_id, g.home), (g.game_id, g.away)]
        if not all(k in pools for k in keys):
            continue
        for (gid, t), pts in zip(keys, (g.hs, g.as_)):
            tm = team.loc[(gid, t)]
            r = {'game_id': gid, 'week': int(g.week), 'team': t, 'pts': float(pts),
                 'off_td': float(tm.pass_td + tm.rush_td), 'yards': float(tm.pass_yds + tm.rush_yds),
                 'pass_yds': float(tm.pass_yds), 'pass_td': float(tm.pass_td), 'off_dk': float(tdk.loc[(gid, t)]),
                 'DST': float(dst.loc[(gid, t)].dst_dk)}
            for role, pid in pools[(gid, t)]['roles'].items():
                r[role] = float(pgi.get((gid, t, pid), 0.0)) if pid else np.nan
            rows.append(r)
    u = pd.DataFrame(rows)
    _require(len(u) > 0, 'SC_COH_1_EMPTY_INPUT', 'no evaluation team-games')
    return add_opponent(u), pools, fin


def add_opponent(u: pd.DataFrame) -> pd.DataFrame:
    """Attach the opponent's columns to each row (same game, and for simulated rows the same world)."""
    key = ['game_id'] + (['world'] if 'world' in u.columns else [])
    o = u[key + ['team', 'pts', 'off_dk', 'QB', 'DST']].rename(
        columns={'team': 'opp', 'pts': 'opp_pts', 'off_dk': 'opp_off_dk', 'QB': 'opp_QB', 'DST': 'opp_DST'})
    m = u.merge(o, on=key)
    m = m[m.team != m.opp].reset_index(drop=True)
    _require(len(m) == len(u), 'SC_COH_1_OPPONENT_JOIN', f'{len(u)} rows became {len(m)}')
    return m


# ============================================================================== simulator replays
def game_spec(g, pools) -> dict:
    """The incumbent's game spec, from the SAME pregame pool the history roles use."""
    clubs = []
    for t in (g.home, g.away):
        ps = []
        for p in pools[(g.game_id, t)]['players']:
            ps.append({'id': p['pid'], 'position': p['pos'], 'target_share': p['target_share'],
                       'carry_share': p['carry_share'], 'pass_att_share': p['pass_att_share'],
                       'pass_td_share': p['target_share'], 'rush_td_share': p['carry_share'] if p['pos'] in ('RB', 'QB') else 0.0,
                       'catch_rate': p['catch_rate'], 'slot': 'OTHER'})
        clubs.append({'club': t, 'players': ps, 'dst_id': f'DST|{t}'})
    return {'total_line': float(g.total_line), 'home_spread': float(g.spread_line), 'clubs': clubs}


def incumbent_draws(model, spec, n_sims, seed) -> dict:
    """Run nfl/sim/game.py:simulate_game and return a provider-neutral world dict."""
    from nfl.sim import game as sim_game
    o = sim_game.simulate_game(model, spec, n_sims=n_sims, seed=seed, retain_stats=True)
    _require(o.state.value == 'PASS', 'SC_COH_1_INCUMBENT_REFUSED', f'{o.code} {o.detail}')
    v = o.value
    return {'stat_draws': v['stat_draws'], 'dst': {c['club']: v['draws'][c['dst_id']] for c in spec['clubs']},
            'club_points': {c: [w[0] for w in v['club_scoring_worlds'][c]] for c in v['club_scoring_worlds']},
            'club_td': {c: [w[1] for w in v['club_scoring_worlds'][c]] for c in v['club_scoring_worlds']}}


STAT_IX = {f: i for i, f in enumerate(('pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td',
                                         'targets', 'receptions', 'rec_yards', 'rec_td'))}


def sim_units(provider, fin, pools, n_worlds=N_WORLDS, seed=SIM_SEED, audit=None):
    """Replay every evaluation game through `provider(spec, n, seed)`; one row per (game, world, team)."""
    rows = []
    games = [g for _, g in fin.iterrows() if (g.game_id, g.home) in pools and (g.game_id, g.away) in pools]
    _require(len(games) > 0, 'SC_COH_1_EMPTY_INPUT', 'no replayable games')
    for gi, g in enumerate(games):
        spec = game_spec(g, pools)
        w = provider(spec, n_worlds, seed + gi)
        sd = {k: np.asarray(v, float) for k, v in w['stat_draws'].items()}
        _require(len(sd) > 0, 'SC_COH_1_EMPTY_DRAWS', g.game_id)
        if audit is not None:
            audit_worlds(spec, sd, w, audit)
        for c in spec['clubs']:
            t = c['club']
            ids = [p['id'] for p in c['players'] if p['id'] in sd]
            S = np.stack([sd[i] for i in ids])                      # player x world x field
            dk = (0.04 * S[..., 1] + 4 * S[..., 2] + 0.1 * S[..., 4] + 6 * S[..., 5] + 0.1 * S[..., 8]
                  + S[..., 7] + 6 * S[..., 9])
            pass_yds = S[..., 1].sum(0)
            col = {i: dk[j] for j, i in enumerate(ids)}
            roles = pools[(g.game_id, t)]['roles']
            df = pd.DataFrame({'game_id': g.game_id, 'week': int(g.week), 'world': np.arange(n_worlds), 'team': t,
                               'pts': np.asarray(w['club_points'][t], float), 'off_td': np.asarray(w['club_td'][t], float),
                               'yards': pass_yds + S[..., 4].sum(0), 'pass_yds': pass_yds,
                               'pass_td': S[..., 2].sum(0), 'off_dk': dk.sum(0),
                               'DST': np.asarray(w['dst'][t], float)})
            for role, pid in roles.items():
                df[role] = col[pid] if (pid and pid in col) else np.nan
            rows.append(df)
    return add_opponent(pd.concat(rows, ignore_index=True))


def audit_worlds(spec, sd, w, acc):
    """Football accounting identities, per world per club. Counts violations; never repairs them."""
    for c in spec['clubs']:
        ids = [p['id'] for p in c['players'] if p['id'] in sd]
        S = np.stack([sd[i] for i in ids])
        n = S.shape[1]
        qb = np.array([p['position'] == 'QB' for p in c['players'] if p['id'] in sd])
        acc['club_worlds'] = acc.get('club_worlds', 0) + n
        acc['player_worlds'] = acc.get('player_worlds', 0) + S.shape[0] * n
        add = lambda k, v: acc.__setitem__(k, acc.get(k, 0) + int(v))
        add('pass_yards_ne_sum_rec_yards', (np.abs(S[qb, :, 1].sum(0) - S[~qb, :, 8].sum(0)) > 0.5).sum())
        add('pass_td_ne_sum_rec_td', (S[qb, :, 2].sum(0) != S[~qb, :, 9].sum(0)).sum())
        add('player_rec_td_gt_receptions', (S[..., 9] > S[..., 7]).sum())
        add('player_rec_yards_without_reception', ((np.abs(S[..., 8]) > 0.5) & (S[..., 7] == 0)).sum())
        add('player_receptions_gt_targets', (S[..., 7] > S[..., 6]).sum())
        add('player_rush_td_gt_carries', (S[..., 5] > S[..., 3]).sum())
        td = np.asarray(w['club_td'][c['club']], float)
        pts = np.asarray(w['club_points'][c['club']], float)
        add('team_td_ne_pass_plus_rush_td', (td != S[qb, :, 2].sum(0) + S[..., 5].sum(0)).sum())
        add('team_points_lt_6_x_off_td', (pts + 1e-9 < 6 * td).sum())
        add('team_points_not_integer', (np.abs(pts - np.round(pts)) > 1e-6).sum())


# ============================================================================== statistics and bootstrap
STATS = [
    # name, x, y, kind, meaning
    ('team_dk_vs_team_points', 'off_dk', 'pts', 'corr', 'corr(team offensive DK core, team points)'),
    ('team_dk_vs_team_off_td', 'off_dk', 'off_td', 'corr', 'corr(team offensive DK core, team offensive TDs)'),
    ('yards_per_extra_td', 'off_td', 'yards', 'slope', 'OLS slope of team scrimmage yards on team offensive TDs'),
    ('pass_yards_vs_pass_td', 'pass_yds', 'pass_td', 'corr', 'corr(team passing yards, team passing TDs)'),
    ('qb_wr1', 'QB', 'WR1', 'corr', 'QB vs WR1 DK'),
    ('qb_wr2', 'QB', 'WR2', 'corr', 'QB vs WR2 DK'),
    ('qb_te1', 'QB', 'TE1', 'corr', 'QB vs TE1 DK'),
    ('wr1_wr2', 'WR1', 'WR2', 'corr', 'WR1 vs WR2 DK'),
    ('qb_rb1', 'QB', 'RB1', 'corr', 'QB vs RB1 DK'),
    ('rb1_own_dst', 'RB1', 'DST', 'corr', 'RB1 vs own DST DK'),
    ('rb1_opp_qb', 'RB1', 'opp_QB', 'corr', 'RB1 vs opposing QB DK'),
    ('qb_opp_qb', 'QB', 'opp_QB', 'corr', 'QB vs opposing QB DK (each game counted in both orientations)'),
    ('qb_opp_dst', 'QB', 'opp_DST', 'corr', 'QB vs opposing DST DK'),
    ('team_dk_vs_opp_team_dk', 'off_dk', 'opp_off_dk', 'corr', 'team offensive DK vs opponent offensive DK'),
    ('team_points_vs_opp_points', 'pts', 'opp_pts', 'corr', 'team points vs opponent points'),
]


def suffstats(u: pd.DataFrame, x: str, y: str, games: list) -> np.ndarray:
    """Per-game sufficient statistics (n, sx, sy, sxx, syy, sxy) over rows where both are present."""
    d = u[['game_id', x, y]].dropna()
    d = d.assign(xx=d[x] * d[x], yy=d[y] * d[y], xy=d[x] * d[y])
    s = d.groupby('game_id').agg(n=(x, 'size'), sx=(x, 'sum'), sy=(y, 'sum'), sxx=('xx', 'sum'), syy=('yy', 'sum'),
                                 sxy=('xy', 'sum'))
    return s.reindex(games).fillna(0.0).to_numpy(float)


def _stat(T: np.ndarray, kind: str) -> np.ndarray:
    n, sx, sy, sxx, syy, sxy = (T[..., i] for i in range(6))
    with np.errstate(invalid='ignore', divide='ignore'):
        cxy = sxy / n - sx * sy / n ** 2
        vx = sxx / n - (sx / n) ** 2
        vy = syy / n - (sy / n) ** 2
        return cxy / np.sqrt(vx * vy) if kind == 'corr' else cxy / vx


def boot_counts(games: list, weeks: dict, block: str, rng) -> np.ndarray:
    G = len(games)
    if block == 'game':
        return rng.multinomial(G, np.full(G, 1.0 / G), size=N_BOOT).astype(float)
    wk = sorted(set(weeks[g] for g in games))
    W = rng.multinomial(len(wk), np.full(len(wk), 1.0 / len(wk)), size=N_BOOT).astype(float)
    ix = np.array([wk.index(weeks[g]) for g in games])
    return W[:, ix]


def _ci(v):
    v = v[np.isfinite(v)]
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)] if len(v) else None


def compare(hist: pd.DataFrame, sims: dict) -> dict:
    """Point estimate + game-blocked CI for history and each simulator; paired gap CIs (game and week blocks)."""
    games = sorted(set(hist.game_id))
    weeks = hist.groupby('game_id').week.first().to_dict()
    rng = np.random.default_rng(BOOT_SEED)
    C = {'game': boot_counts(games, weeks, 'game', rng), 'week': boot_counts(games, weeks, 'week', rng)}
    out = {}
    for name, x, y, kind, meaning in STATS:
        H = suffstats(hist, x, y, games)
        row = {'meaning': meaning, 'kind': kind, 'history': {
            'value': round(float(_stat(H.sum(0), kind)), 4), 'n_team_games': int(H[:, 0].sum()),
            'n_games': int((H[:, 0] > 0).sum()), 'ci95_game_block': _ci(_stat(C['game'] @ H, kind))}}
        for sname, su in sims.items():
            S = suffstats(su, x, y, games)
            r = {'value': round(float(_stat(S.sum(0), kind)), 4), 'n_rows': int(S[:, 0].sum()),
                 'ci95_game_block': _ci(_stat(C['game'] @ S, kind))}
            for b in ('game', 'week'):
                r[f'gap_sim_minus_history_ci95_{b}_block'] = _ci(_stat(C[b] @ S, kind) - _stat(C[b] @ H, kind))
            r['gap_sim_minus_history'] = round(r['value'] - row['history']['value'], 4)
            lo, hi = r['gap_sim_minus_history_ci95_game_block']
            r['gap_interval_excludes_zero_game_block'] = bool(lo > 0 or hi < 0)
            row[sname] = r
        out[name] = row
    return out


# ============================================================================== marginal guard
def marginal_guard(hist: pd.DataFrame, sims: dict) -> dict:
    """Coherence must not be bought with worse marginals: per-role mean DK and team points mean vs actual."""
    games = sorted(set(hist.game_id))
    rng = np.random.default_rng(BOOT_SEED + 1)
    Cg = boot_counts(games, None, 'game', rng)
    gi = {g: i for i, g in enumerate(games)}
    out = {}
    for col in ('pts', 'off_dk', 'QB', 'WR1', 'WR2', 'TE1', 'RB1', 'DST'):
        h = hist[['game_id', 'team', col]].dropna()
        res = {'n_team_games': int(len(h))}
        errs = {}
        for sname, su in sims.items():
            g = su.groupby(['game_id', 'team'])[col]
            m = g.mean().rename('mean')
            lo, hi = g.quantile(0.1).rename('p10'), g.quantile(0.9).rename('p90')
            j = h.join(pd.concat([m, lo, hi], axis=1), on=['game_id', 'team']).dropna()
            ae = (j['mean'] - j[col]).abs()
            per_game = np.zeros(len(games)); cnt = np.zeros(len(games))
            np.add.at(per_game, j.game_id.map(gi).to_numpy(), ae.to_numpy()); np.add.at(cnt, j.game_id.map(gi).to_numpy(), 1)
            errs[sname] = (per_game, cnt)
            res[sname] = {'mae_of_mean': round(float(ae.mean()), 3),
                          'pearson_r_mean_vs_actual': round(float(np.corrcoef(j['mean'], j[col])[0, 1]), 4),
                          'bias_mean_minus_actual': round(float((j['mean'] - j[col]).mean()), 3),
                          'coverage_p10_p90': round(float(((j[col] >= j.p10) & (j[col] <= j.p90)).mean()), 4),
                          'coverage_nominal': 0.8}
        if 'incumbent' in errs and 'candidate' in errs:
            (a, n1), (b, n2) = errs['candidate'], errs['incumbent']
            d = (Cg @ a) / (Cg @ n1) - (Cg @ b) / (Cg @ n2)
            res['mae_candidate_minus_incumbent_ci95_game_block'] = _ci(d)
        out[col] = res
    return out


# ============================================================================== archived live worlds (n = 1 game)
def archived_worlds_audit() -> dict:
    """Accounting identities on the archived ATL@NO Showdown worlds -- AFTER the efficiency_worlds step.
    n = 1 game, descriptive only. PIT@CLE / PHI@CHI worlds are not present in this checkout."""
    base = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
    p = next(base.glob('SHOWDOWN_*_WORLDS.npz'), None)
    sal = _REPO / 'nfl/dfs/salaries'
    res = {'searched': 'nfl/dfs/salaries/**/SHOWDOWN_*_WORLDS.npz'}
    for tag in ('PIT_CLE', 'PHI_CHI'):
        hits = sorted(str(q.relative_to(_REPO)) for q in sal.rglob(f'SHOWDOWN_{tag}*_WORLDS.npz'))
        res[f'{tag}_WORLDS'] = hits or 'NOT_PRESENT_IN_CHECKOUT'
    if p is None:
        res['ATL_NO'] = 'NOT_PRESENT_IN_CHECKOUT'
        return res
    z = np.load(p)
    stats, meta = z['stats'].astype(float), json.loads(bytes(z['meta']).decode())
    F = {f: i for i, f in enumerate(meta['fields'])}
    for f in meta['yard_fields']:
        stats[..., F[f]] /= meta['yard_scale']
    keys = meta['keys']
    teams = sorted({k.split('|')[1] for k in keys})
    out = {'file': str(p.relative_to(_REPO)), 'sha256': _sha(p), 'n_worlds': int(stats.shape[1]), 'per_club': {}}
    for t in teams:
        ix = [i for i, k in enumerate(keys) if k.endswith('|' + t)]
        S = stats[ix]
        qb = S[..., F['pass_att']].sum(1) > 0
        d = S[qb, :, F['pass_yards']].sum(0) - S[~qb, :, F['rec_yards']].sum(0)
        out['per_club'][t] = {
            'worlds_pass_yards_ne_sum_rec_yards_gt_1yd': round(float((np.abs(d) > 1.0).mean()), 4),
            'mean_abs_gap_pass_minus_rec_yards': round(float(np.abs(d).mean()), 2),
            'worlds_pass_td_ne_sum_rec_td': round(float((S[qb, :, F['pass_td']].sum(0) != S[~qb, :, F['rec_td']].sum(0)).mean()), 4),
            'player_worlds_rec_td_gt_receptions': int((S[..., F['rec_td']] > S[..., F['receptions']]).sum()),
            'player_worlds_rec_yards_without_reception': int(((np.abs(S[..., F['rec_yards']]) > 0.5)
                                                               & (S[..., F['receptions']] == 0)).sum()),
            'player_worlds': int(S.shape[0] * S.shape[1])}
    res['ATL_NO'] = out
    res['NOTE'] = 'n = 1 game; descriptive. Shows what the live post-step does to the identities, estimates nothing.'
    return res


# ============================================================================== k sensitivity (reported, never selected)
K_SENSITIVITY = (0.5, 2.0)     # half and double the declared sqrt(n) rule
K_SENS_WORLDS = 200


def k_sensitivity(CAND, lib, conc, hist, fin, pools) -> dict:
    """The candidate's gaps at half and double the declared k. A SENSITIVITY: the declared k is the only one used
    for the candidate's headline, and no k is chosen on these numbers."""
    import copy
    out = {}
    for f in K_SENSITIVITY:
        L = copy.copy(lib)
        L.k = max(2, int(round(lib.k * f)))
        su = sim_units(lambda s, n, sd: CAND.simulate(L, conc, s, n, sd), fin, pools, K_SENS_WORLDS)
        c = compare(hist, {'candidate': su})
        out[f'k={L.k}'] = {k: {'value': r['candidate']['value'], 'gap': r['candidate']['gap_sim_minus_history'],
                               'gap_ci95_game_block': r['candidate']['gap_sim_minus_history_ci95_game_block']}
                           for k, r in c.items()}
    out['NOTE'] = f'{K_SENS_WORLDS} worlds per game; sensitivity only, the declared k = {lib.k} is the headline'
    return out


# ============================================================================== run
def run(with_candidate: bool = False, n_worlds: int = N_WORLDS) -> dict:
    from nfl.sim import game as sim_game
    hist, pools, fin = history_units(EVAL_SEASON)
    mo = sim_game.Model.load()
    _require(mo.state.value == 'PASS', 'SC_COH_1_INCUMBENT_MODEL_ABSENT', mo.code)
    model = mo.value
    acc_inc = {}
    sims = {'incumbent': sim_units(lambda s, n, sd: incumbent_draws(model, s, n, sd), fin, pools, n_worlds,
                                   audit=acc_inc)}
    cand_meta, acc_cand = None, None
    if with_candidate:
        from nfl.research.coherence import sc_coh_1_candidate as CAND
        lib = CAND.build_library(FIT_SEASONS)
        conc = CAND.estimate_share_concentration(FIT_SEASONS)
        acc_cand = {}
        sims['candidate'] = sim_units(lambda s, n, sd: CAND.simulate(lib, conc, s, n, sd), fin, pools, n_worlds,
                                      audit=acc_cand)
        cand_meta = {'library': lib.describe(), 'share_concentration': conc,
                     'k_sensitivity': k_sensitivity(CAND, lib, conc, hist, fin, pools)}
    cmp_ = compare(hist, sims)
    doc = {
        'ARTIFACT': 'SC_COH_1_MEASUREMENT', 'STATUS': 'SHADOW_ONLY', 'LAYER': 'RESEARCH',
        'evaluation': {'season': EVAL_SEASON, 'weeks': f'{FIRST_EVAL_WEEK}-18', 'n_games': int(hist.game_id.nunique()),
                       'n_team_games': int(len(hist)), 'n_worlds_per_game': n_worlds, 'sim_seed': SIM_SEED,
                       'n_boot': N_BOOT, 'boot_seed': BOOT_SEED},
        'sources': {'pbp_eval': {'file': str(pbp_path(EVAL_SEASON).relative_to(_REPO)), 'sha256': _sha(pbp_path(EVAL_SEASON))},
                    'snaps_eval': {'file': str(SNAPS[EVAL_SEASON].relative_to(_REPO)), 'sha256': _sha(SNAPS[EVAL_SEASON])},
                    'crosswalk': {'file': str(CROSSWALK.relative_to(_REPO)), 'sha256': _sha(CROSSWALK)},
                    'incumbent_inputs': {str(p.relative_to(_REPO)): _sha(p) for p in
                                         (sim_game.SS, sim_game.EFF, sim_game.VC, sim_game.USAGE)
                                         if p.exists()}},
        'INCUMBENT_HELDOUT_CAVEAT': ('the incumbent inputs SHARED_STATE (2000-2026) and EFFICIENCY (PLAYER_GAME '
                                     '2021-2026) include 2025 games, so the incumbent is NOT out of sample on these '
                                     'games; any gap is measured despite that advantage'),
        'statistics': cmp_,
        'marginal_guard': marginal_guard(hist, sims),
        'accounting_audit_incumbent_replay': acc_inc,
        'accounting_audit_candidate_replay': acc_cand,
        'archived_live_worlds_audit': archived_worlds_audit(),
        'candidate': cand_meta,
        'written_at': dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(doc, indent=1, default=float))
    write_status(doc)
    return doc


STATUS = HERE / 'SC_COH_1_STATUS.json'

#: Where the live Showdown path generates team volume, yards and touchdowns, and what is drawn independently of
#: what. Read from the code (line numbers at the time of writing); every entry was opened, not inferred.
ROOT_CAUSE_MAP = [
    {'where': 'nfl/tools/showdown_slate_run.py:76', 'what': 'live Showdown entry: showdown_draws.build(volume_centre='
     'PROJECTION) -> nfl/sim/game.py:simulate_game_centred -> simulate_game (CLUB_TOTAL_IMPOSED, DIRICHLET defaults)'},
    {'where': 'nfl/tools/showdown_draws.py:64-121 (_shares)', 'what': 'per-player shares = projected volume / club '
     'projected volume; TD shares = projected rec_td / rush_td over the club (lines 110-111). Fixed per game, not per world.'},
    {'where': 'nfl/sim/game.py:301-304', 'what': 'GAME STATE: total = centre + empirical total residual, margin = '
     'centre + empirical margin residual, drawn INDEPENDENTLY of each other (measured corr 0.025); club points = '
     '(total +/- margin)/2. Not integers and not built from scores.'},
    {'where': 'nfl/sim/game.py:321-326 -> nfl/sim/dst.py:241-252', 'what': 'DST = tier(opponent points) + an empirical '
     '(sacks, takeaways, def TD, safety) tuple drawn from the points-allowed band -- independent of the opponent\'s '
     'drawn pass attempts, yards and TDs given points.'},
    {'where': 'nfl/sim/game.py:341-352', 'what': 'VOLUME: plays and pass share = linear in own points and margin + two '
     'INDEPENDENT Gaussian residuals; pass/rush attempts = plays x share. Volume depends on points only through these '
     'slopes (plays +0.20 per own point).'},
    {'where': 'nfl/sim/game.py:360-361', 'what': 'TOUCHDOWNS: td = round((points - 7.51 - N(0, 4.52)) / 6.32). Derived '
     'from points with its OWN noise, independent of volume and yards; can exceed points/6 (measured below).'},
    {'where': 'nfl/sim/game.py:363-366, 431-432', 'what': 'YARDS: club yards = attempts x a yards-per-attempt (carry) '
     'drawn from the empirical club-game distribution INDEPENDENTLY of points, TDs and the opponent. This is the root '
     'cause of yards-per-extra-TD ~3 against ~35 in history and corr(pass yards, pass TD) ~0 against ~0.49.'},
    {'where': 'nfl/sim/game.py:412-420', 'what': 'VOLUME ALLOCATION: QB attempts, targets and carries Dirichlet-'
     'multinomial over the fixed shares (sums exact).'},
    {'where': 'nfl/sim/game.py:471-474', 'what': 'YARDS ALLOCATION: club passing yards Dirichlet-split over QBs and, '
     'SEPARATELY, over receivers in proportion to targets (not receptions); a receiver with 0 receptions can get yards.'},
    {'where': 'nfl/sim/game.py:483-485', 'what': 'TD TYPE: passing TDs ~ Binomial(td, 0.6156), a fixed rate independent '
     'of that world\'s passing yards and attempts.'},
    {'where': 'nfl/sim/game.py:486-490', 'what': 'TD ALLOCATION: receiving and rushing TDs allocated over players by the '
     'FIXED pregame TD shares, independent of that world\'s targets, receptions, carries and yards -> rec TD > '
     'receptions and rush TD > carries occur.'},
    {'where': 'nfl/sim/game.py:515', 'what': 'RECEPTIONS: Binomial(targets, catch_rate), drawn AFTER and independently '
     'of the receiver\'s yards and TDs.'},
    {'where': 'nfl/tools/classic_slate_run.py:106-129 (efficiency_worlds, called at showdown_slate_run.py:90)',
     'what': 'POST-STEP on the live path: each player\'s yards multiplied by HIS OWN factor (projection yds/opp over '
     'simulated yds/opp), so QB passing yards stop equalling the sum of receiving yards; INTs drawn Binomial per '
     'attempt independently of everything (line 126).'},
    {'where': 'nfl/tools/showdown_slate_run.py:95 (anchor_means)', 'what': 'DST draws multiplicatively rescaled onto the '
     'point projection after the world is drawn.'},
    {'where': 'nfl/tools/kicker_world.py:204-224', 'what': 'KICKER from the same world\'s (points, offensive TDs) by '
     'identity; inherits the points/TD incoherence (remainder = points - 6 td - XP can be negative, line 211).'},
]


def write_status(doc: dict) -> dict:
    """SC_COH_1_STATUS.json, composed from the measurement artifact so no number is retyped by hand."""
    st = doc['statistics']
    has_c = doc.get('candidate') is not None

    def row(k):
        r = st[k]
        out = {'history_2025': r['history'], 'incumbent': {x: r['incumbent'][x] for x in (
            'value', 'gap_sim_minus_history', 'gap_sim_minus_history_ci95_game_block',
            'gap_sim_minus_history_ci95_week_block', 'gap_interval_excludes_zero_game_block')}}
        if has_c:
            out['candidate'] = {x: r['candidate'][x] for x in out['incumbent']}
        return out
    team_keys = ('team_dk_vs_team_points', 'team_dk_vs_team_off_td', 'yards_per_extra_td', 'pass_yards_vs_pass_td')
    cand_result = 'NOT_YET_MEASURED (run with --candidate)'
    if has_c:
        closed = [k for k in st if st[k]['incumbent']['gap_interval_excludes_zero_game_block']
                  and not st[k]['candidate']['gap_interval_excludes_zero_game_block']]
        opened = [k for k in st if st[k]['candidate']['gap_interval_excludes_zero_game_block']
                  and not st[k]['incumbent']['gap_interval_excludes_zero_game_block']]
        both = [k for k in st if st[k]['candidate']['gap_interval_excludes_zero_game_block']
                and st[k]['incumbent']['gap_interval_excludes_zero_game_block']]
        cand_result = {
            'name': 'ANALOGUE_GAME_PLAY_LIBRARY_HIERARCHICAL_ALLOCATION',
            'module': 'nfl/research/coherence/sc_coh_1_candidate.py',
            'fitted_on': doc['candidate']['library']['seasons'], 'share_concentration': doc['candidate']['share_concentration'],
            'library': doc['candidate']['library'],
            'heldout_measured_on': f"{doc['evaluation']['season']} weeks {doc['evaluation']['weeks']}",
            'incumbent_gap_interval_excludes_zero_candidate_does_not': closed,
            'candidate_gap_interval_excludes_zero_incumbent_does_not': opened,
            'both_gap_intervals_exclude_zero': both,
            'READING': ('an interval that includes zero is NOT a match: no equivalence margin was predeclared, so '
                        'these lists say where a gap is or is not detectable at n = 256 games, nothing more. The '
                        'team-level agreement is close to mechanical -- the candidate draws real 2021-2024 team-games '
                        '-- so what the held-out season tests there is whether that structure transfers to 2025.'),
            'accounting_audit_on_replay': doc['accounting_audit_candidate_replay'],
            'marginal_guard': doc['marginal_guard'],
            'k_sensitivity': doc['candidate']['k_sensitivity'],
        }
    s = {
        'ARTIFACT': 'SC_COH_1_STATUS', 'STATUS': 'SHADOW_ONLY',
        'AUDIT_LADDER': {'reached': ['IMPLEMENTED', 'SUCCESS_TESTED', 'REFUSAL_TESTED', 'ADVERSARIAL_TESTED'],
                         'NOT': ['ON_EXECUTION_PATH', 'PROSPECTIVELY_VALIDATED', 'PROMOTED'],
                         'tests': 'nfl/tests/test_sc_coh_1.py'},
        'NOT_READY_FOR_NEXT_SLATE': ('shadow research only. Held-out evidence is one retrospective season with '
                                     'oracle-ish pregame inputs (snap-count active pool, prior-week shares, market '
                                     'lines); no prospective game, no production-path integration, no promotion '
                                     'decision has been made.'),
        'root_cause_map': ROOT_CAUSE_MAP,
        'measurement': {'artifact': str(OUT.relative_to(_REPO)), 'harness': 'nfl/research/coherence/sc_coh_1_measure.py',
                        'evaluation': doc['evaluation'], 'INCUMBENT_HELDOUT_CAVEAT': doc['INCUMBENT_HELDOUT_CAVEAT'],
                        'team_level': {k: row(k) for k in team_keys},
                        'pairs': {k: row(k) for k in st if k not in team_keys},
                        'accounting_audit_incumbent_replay': doc['accounting_audit_incumbent_replay'],
                        'archived_live_worlds_audit': doc['archived_live_worlds_audit']},
        'candidate_result': cand_result,
        'written_at': doc['written_at'],
    }
    STATUS.write_text(json.dumps(s, indent=1, default=float))
    return s


def _table(doc):
    lines = []
    for k, r in doc['statistics'].items():
        h = r['history']
        s = f"{k:26s} hist {h['value']:+8.3f} {h['ci95_game_block']}"
        for sn in ('incumbent', 'candidate'):
            if sn in r:
                v = r[sn]
                s += f" | {sn[:4]} {v['value']:+8.3f} gap {v['gap_sim_minus_history']:+7.3f} {v['gap_sim_minus_history_ci95_game_block']}"
        lines.append(s)
    return '\n'.join(lines)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', action='store_true')
    ap.add_argument('--n-worlds', type=int, default=N_WORLDS)
    a = ap.parse_args()
    d = run(a.candidate, a.n_worlds)
    print(OUT.relative_to(_REPO))
    print(json.dumps(d['evaluation']))
    print(_table(d))
    print(json.dumps({'incumbent_audit': d['accounting_audit_incumbent_replay'],
                      'candidate_audit': d['accounting_audit_candidate_replay']}, indent=1))
    print(json.dumps(d['marginal_guard'], indent=1)[:3000])
