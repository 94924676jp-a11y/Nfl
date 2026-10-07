#!/usr/bin/env python3.12
"""SC-COH-1 shadow candidate: ANALOGUE-GAME PLAY LIBRARY with hierarchical, accounting-exact allocation.

    from nfl.research.coherence import sc_coh_1_candidate as C
    lib = C.build_library(C.FIT_SEASONS); conc = C.estimate_share_concentration(C.FIT_SEASONS)
    worlds = C.simulate(lib, conc, spec, n_sims, seed)     # spec = the incumbent's game spec

STATUS: SHADOW_ONLY. Research code. Not imported by anything on the production path; it reads committed
2021-2024 play-by-play and the 2024 snap counts and nothing else, and writes nothing.

WHY THIS SHAPE (from the SC-COH-1 root-cause map, nfl/research/coherence/SC_COH_1_STATUS.json)

The incumbent (nfl/sim/game.py:simulate_game) draws club points first and derives everything else from them through
SEPARATE draws: touchdowns from points by an inverted regression (game.py:360), yards from an efficiency drawn
independently of points and TDs (game.py:363-366), receptions independently of yards (game.py:515), and receiving
TDs over players independently of who caught anything (game.py:487). Each step is reconciled to its own club total,
so the totals add up, but the totals are not coherent with EACH OTHER and a player's TD is not tied to his catches.
Measured on 2025: about 3 yards per extra offensive TD in the simulator against about 35 in history.

A multiplier cannot fix that and the owner forbids one. The candidate removes the independent draws instead:

  1  GAME STATE = A REAL GAME. Each world draws one historical game (both clubs, 2021-2024) from the k nearest
     neighbours of the target game in (total line, spread) space. Points, plays, yards, TDs, sacks and takeaways of
     both clubs come TOGETHER from that one game, so volume-yards-TD-points coherence and the cross-team structure
     are the historical ones by construction -- nothing is fitted to produce them.
  2  HIERARCHICAL ALLOCATION. The analogue club's PLAYS (not its totals) are handed to the target club's players.
     Volume first: each player's target (carry, attempt) count is Dirichlet-multinomial over his pregame share, with
     a concentration ESTIMATED on 2024. Then the analogue's plays are matched to those slots, position group first
     (a TE-thrown ball goes to a TE slot where one exists), the remainder at random.
  3  ACCOUNTING IS STRUCTURAL. A completion credits its yards and its TD to the passer AND the receiver, so
        QB passing yards == sum of receiving yards, QB passing TDs == sum of receiving TDs, receptions == completions,
        receiving TDs <= receptions, rushing TDs <= carries, team offensive TDs == passing TDs + rushing TDs,
        team points are the analogue's real points (>= 6 x offensive TDs),
     and `verify` checks every one on every world and raises SC_COH_1_IDENTITY_VIOLATED on any miss.
  4  DST from the same analogue: the defence's sacks, INT, fumble recoveries, return TDs and safeties are the
     analogue defence's, and its points allowed are the analogue opponent's points.

CONSTANTS, EACH WITH PROVENANCE (no tuned constant)
  FIT_SEASONS      2021-2024: the play library and the line-distance scale. 2025 is the held-out season.
  k                round(sqrt(N_library_games)) -- the standard k ~ sqrt(n) nearest-neighbour rule of thumb
                   (Loftsgaarden & Quesenberry 1965; Duda, Hart & Stork, Pattern Classification, 2nd ed., sec. 4.4).
                   DECLARED PRIOR, not selected on any outcome.
  distance         Euclidean on (total_line, spread_line), each divided by its library SD (2021-2024).
  alpha_targets,   method-of-moments Dirichlet-multinomial concentration of per-game counts around the PRIOR-WEEK
  alpha_carries    shares, estimated on 2024 weeks 2-18 with the same snap pool the replay uses. Estimated.
  QB attempts      plain multinomial over pass-attempt shares (one starter carries ~all; no concentration is
                   identifiable from s ~ 1). Declared.

KNOWN LIMITS (declared, not hidden)
  - team-level support per game is the k analogue games: a world's club totals take one of k historical values
  - player efficiency within a position group is the analogue's, not the player's (the incumbent's default
    CLUB_TOTAL_IMPOSED mode also uses one club efficiency)
  - laterals: the library credits the passer with the RECEIVER's yards on the ~20 lateral plays per season, so the
    identity is exact; nflverse passing_yards differs from receiving_yards on exactly those plays
  - conditioning is on the two lines only; club identity (pass-heavy offences, pace) enters only through them
"""
from __future__ import annotations

import functools
import math
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.coherence import sc_coh_1_measure as M  # noqa: E402
from nfl.research.coherence.sc_coh_1_measure import CoherenceInputError, _require  # noqa: E402

FIT_SEASONS = M.FIT_SEASONS
MAX_FIT_SEASON = M.MAX_FIT_SEASON
CONC_SEASON = 2024
GROUPS = {'WR': 0, 'TE': 1, 'RB': 2, 'QB': 3, 'ANY': 4}


def _check_fit_seasons(seasons):
    seasons = tuple(int(s) for s in seasons)
    _require(len(seasons) > 0, 'SC_COH_1_EMPTY_INPUT', 'no fit seasons')
    bad = [s for s in seasons if s > MAX_FIT_SEASON]
    _require(not bad, 'SC_COH_1_HELDOUT_LEAK', f'fit seasons {bad} are after {MAX_FIT_SEASON}; 2025 is held out')
    return seasons


@functools.lru_cache(maxsize=None)
def _pos_of():
    c = M.crosswalk()
    return dict(zip(c.gsis_id, c.position.map(lambda p: M.POS_MAP.get(p, 'ANY'))))


class Library:
    """One entry per historical game: lines, and per club (home, away) its plays, points and DST components."""

    def __init__(self, games: list, seasons: tuple):
        _require(len(games) > 0, 'SC_COH_1_EMPTY_INPUT', 'play library has no games')
        self.games = games
        self.seasons = seasons
        self.max_season = max(g['season'] for g in games)
        _require(self.max_season <= MAX_FIT_SEASON, 'SC_COH_1_HELDOUT_LEAK',
                 f'library contains season {self.max_season}')
        X = np.array([[g['total_line'], g['spread_line']] for g in games], float)
        self.scale = X.std(0, ddof=1)
        _require(np.all(self.scale > 0), 'SC_COH_1_DEGENERATE_LINES', f'line SDs {self.scale}')
        self.X = X / self.scale
        self.k = int(round(math.sqrt(len(games))))

    def neighbours(self, total_line, spread):
        d = np.hypot(self.X[:, 0] - total_line / self.scale[0], self.X[:, 1] - spread / self.scale[1])
        return np.argsort(d, kind='stable')[:self.k]

    def describe(self):
        return {'n_games': len(self.games), 'seasons': list(self.seasons), 'max_season': int(self.max_season),
                'k_neighbours': self.k, 'K_RULE': 'round(sqrt(n_games)), declared prior',
                'line_scale_sd': [round(float(v), 4) for v in self.scale]}


def _club_plays(plays: pd.DataFrame, pos_of: dict) -> dict:
    p = plays[plays.kind == 'pass']
    p = p[p.att == 1]
    r = plays[plays.kind == 'run']
    tgt = p.receiver.notna().to_numpy()
    _require(not ((p.ptd == 1) & (p.cmp != 1)).any(), 'SC_COH_1_LIBRARY_INCOHERENT', 'a pass TD without a completion')
    _require(not ((p.cmp == 1) & p.receiver.isna()).any(), 'SC_COH_1_LIBRARY_INCOHERENT', 'a completion without a receiver')
    return {
        'n_att': int(len(p)),
        'tgt_group': np.array([GROUPS[pos_of.get(x, 'ANY')] for x in p.receiver[tgt]], int),
        'tgt_cmp': p.cmp[tgt].to_numpy(int),
        'tgt_yds': np.where(p.cmp[tgt] == 1, p.recyds[tgt], 0.0).astype(float),
        'tgt_td': p.ptd[tgt].to_numpy(int),
        'run_qb': np.array([pos_of.get(x) == 'QB' for x in r.rusher], bool),
        'run_yds': r.rushyds.to_numpy(float), 'run_td': r.rtd.to_numpy(int),
    }


@functools.lru_cache(maxsize=None)
def _library_cached(seasons: tuple) -> Library:
    pos_of = _pos_of()
    games = []
    for s in seasons:
        df = M.load_pbp(s)
        _require(int(df.season.max()) <= MAX_FIT_SEASON, 'SC_COH_1_HELDOUT_LEAK', f'pbp {s} carries a later season')
        plays = M.offensive_plays(df)
        fin = M.finals(df)
        dst = M.dst_games(df, fin).set_index(['game_id', 'team'])
        byc = {k: v for k, v in plays.groupby(['game_id', 'team'])}
        for _, g in fin.iterrows():
            if (g.game_id, g.home) not in byc or (g.game_id, g.away) not in byc:
                continue
            clubs = {}
            for side, t, pts in (('home', g.home, g.hs), ('away', g.away, g.as_)):
                c = _club_plays(byc[(g.game_id, t)], pos_of)
                d = dst.loc[(g.game_id, t)]
                c.update({'points': float(pts), 'dst': (float(d.sacks), float(d.ints), float(d.fumrec),
                                                         float(d.dtd), float(d.safeties))})
                clubs[side] = c
            games.append({'game_id': g.game_id, 'season': int(g.season), 'total_line': float(g.total_line),
                          'spread_line': float(g.spread_line), 'home': clubs['home'], 'away': clubs['away']})
    return Library(games, seasons)


def build_library(seasons=FIT_SEASONS) -> Library:
    return _library_cached(_check_fit_seasons(seasons))


# ============================================================================== concentration (2024 only)
def _mom_alpha(rows):
    """Method-of-moments Dirichlet-multinomial concentration. rows: (T, s, n) per player-game."""
    T, s, n = (np.asarray(x, float) for x in zip(*rows))
    R = float(((n - T * s) ** 2).sum())
    base = T * s * (1 - s)
    f = lambda a: float((base * (T + a) / (1 + a)).sum())
    if R <= f(1e9):
        return {'alpha': None, 'state': 'NO_OVERDISPERSION', 'phi': round(R / float(base.sum()), 4)}
    lo, hi = 1e-6, 1e9
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if f(mid) > R else (lo, mid)
    return {'alpha': round(math.sqrt(lo * hi), 4), 'state': 'ESTIMATED', 'phi': round(R / float(base.sum()), 4),
            'n_player_games': int(len(T))}


@functools.lru_cache(maxsize=None)
def _conc_cached(season: int) -> dict:
    df = M.load_pbp(season)
    plays = M.offensive_plays(df)
    pg = M.player_games(plays)
    pools = M.pregame_pools(season, pg, M.snap_pool(season))
    act = pg.set_index(['game_id', 'team', 'pid'])
    tot = plays.groupby(['game_id', 'team']).agg(T=('receiver', lambda x: x.notna().sum()),
                                                 C=('rusher', lambda x: x.notna().sum()))
    tr, cr = [], []
    for (gid, team), pool in pools.items():
        if (gid, team) not in tot.index:
            continue
        T, C = tot.loc[(gid, team)]
        for p in pool['players']:
            a = act.loc[(gid, team, p['pid'])] if (gid, team, p['pid']) in act.index else None
            if p['target_share'] > 0 and p['pos'] != 'QB':
                tr.append((T, p['target_share'], float(a.targets) if a is not None else 0.0))
            if p['carry_share'] > 0:
                cr.append((C, p['carry_share'], float(a.carries) if a is not None else 0.0))
    _require(len(tr) > 100 and len(cr) > 100, 'SC_COH_1_EMPTY_INPUT', f'{len(tr)} target / {len(cr)} carry rows')
    return {'season': season, 'targets': _mom_alpha(tr), 'carries': _mom_alpha(cr),
            'METHOD': ('E[(n - T s)^2] = T s (1-s) (T + a)/(1 + a), pooled over player-games, solved for a; s = the '
                       'player\'s season-to-date share over weeks < W renormalised over the snap pool, exactly as the '
                       'replay builds it')}


def estimate_share_concentration(seasons=FIT_SEASONS) -> dict:
    seasons = _check_fit_seasons(seasons)
    _require(CONC_SEASON in seasons, 'SC_COH_1_NO_CONC_SEASON', f'{CONC_SEASON} (the only fit season with snap '
                                                               f'counts) is not among {seasons}')
    return _conc_cached(CONC_SEASON)


# ============================================================================== simulation
def _dm_counts(n, shares, alpha, rng):
    s = np.asarray(shares, float)
    out = np.zeros(len(s), int)
    pos = s > 0
    if n <= 0 or not pos.any():
        return out
    w = s[pos] / s[pos].sum()
    if alpha:
        w = rng.dirichlet(alpha * w)
    out[pos] = rng.multinomial(n, w)
    return out


def _match(play_group, slot_owner, slot_group, rng):
    """Assign each play to exactly one slot: same group first, the remainder at random. Returns owner per play."""
    P = len(play_group)
    _require(P == len(slot_owner), 'SC_COH_1_SLOT_MISMATCH', f'{P} plays, {len(slot_owner)} slots')
    owner = np.full(P, -1, int)
    free = np.ones(P, bool)
    pord = rng.permutation(P)
    sord = rng.permutation(P)
    for g in np.unique(play_group):
        pi = pord[play_group[pord] == g]
        si = sord[(slot_group[sord] == g) & free[sord]]
        m = min(len(pi), len(si))
        owner[pi[:m]] = slot_owner[si[:m]]
        free[si[:m]] = False
    left_p = pord[owner[pord] < 0]
    left_s = sord[free[sord]]
    owner[left_p] = slot_owner[left_s]
    return owner


def _club_world(club, ana, conc, rng):
    """One club's stat lines in one world from one analogue club. Returns (S [player x 10], td, points)."""
    ps = club['players']
    n = len(ps)
    S = np.zeros((n, 10))
    pos = np.array([p['position'] for p in ps])
    isqb = pos == 'QB'
    # passing: attempts to QBs, targets to receivers
    qa = _dm_counts(ana['n_att'], [p.get('pass_att_share', 0.0) if q else 0.0 for p, q in zip(ps, isqb)], None, rng)
    _require(qa.sum() == ana['n_att'], 'SC_COH_1_NO_PASSER', f"{club['club']}: no QB with a pass-attempt share")
    passer_of_att = rng.permutation(np.repeat(np.arange(n), qa))
    P = len(ana['tgt_group'])
    tc = _dm_counts(P, [p['target_share'] if not q else 0.0 for p, q in zip(ps, isqb)],
                    conc['targets']['alpha'], rng)
    _require(tc.sum() == P, 'SC_COH_1_NO_RECEIVERS', f"{club['club']}: no receiver with a target share")
    owner = np.repeat(np.arange(n), tc)
    sg = np.array([GROUPS.get(pos[i], 4) for i in owner], int)
    rec = _match(ana['tgt_group'], owner, sg, rng)
    passer = passer_of_att[:P]          # the first P attempts are the targeted ones; order is already random
    np.add.at(S[:, 0], passer_of_att, 1)
    np.add.at(S[:, 1], passer, ana['tgt_yds'])
    np.add.at(S[:, 2], passer, ana['tgt_td'])
    np.add.at(S[:, 6], rec, 1)
    np.add.at(S[:, 7], rec, ana['tgt_cmp'])
    np.add.at(S[:, 8], rec, ana['tgt_yds'])
    np.add.at(S[:, 9], rec, ana['tgt_td'])
    # rushing: carries over everyone, QB runs matched to QB slots first
    R = len(ana['run_yds'])
    cc = _dm_counts(R, [p['carry_share'] for p in ps], conc['carries']['alpha'], rng)
    _require(cc.sum() == R, 'SC_COH_1_NO_RUSHERS', f"{club['club']}: no player with a carry share")
    cown = np.repeat(np.arange(n), cc)
    rusher = _match(ana['run_qb'].astype(int), cown, isqb[cown].astype(int), rng)
    np.add.at(S[:, 3], rusher, 1)
    np.add.at(S[:, 4], rusher, ana['run_yds'])
    np.add.at(S[:, 5], rusher, ana['run_td'])
    td = int(ana['tgt_td'].sum() + ana['run_td'].sum())
    return S, td, ana['points']


def verify(S, isqb, td, points, ana):
    """Every accounting identity, exactly. Raises on the first miss; an identity that usually holds is not one."""
    checks = {
        'pass_yards_eq_sum_rec_yards': abs(S[isqb, 1].sum() - S[~isqb, 8].sum()) < 1e-9,
        'pass_td_eq_sum_rec_td': S[isqb, 2].sum() == S[~isqb, 9].sum(),
        'receptions_eq_completions': S[:, 7].sum() == ana['tgt_cmp'].sum(),
        'targets_le_attempts': S[:, 6].sum() <= S[isqb, 0].sum() == ana['n_att'],
        'rec_td_le_receptions': bool((S[:, 9] <= S[:, 7]).all()),
        'receptions_le_targets': bool((S[:, 7] <= S[:, 6]).all()),
        'rec_yards_only_on_receptions': bool(((np.abs(S[:, 8]) < 1e-9) | (S[:, 7] > 0)).all()),
        'rush_td_le_carries': bool((S[:, 5] <= S[:, 3]).all()),
        'carries_eq_team_rushes': S[:, 3].sum() == len(ana['run_yds']),
        'team_td_eq_pass_plus_rush_td': td == S[isqb, 2].sum() + S[:, 5].sum(),
        'points_ge_6_x_off_td': points >= 6 * td,
        'team_pass_yards_eq_library': abs(S[isqb, 1].sum() - ana['tgt_yds'].sum()) < 1e-9,
        'team_rush_yards_eq_library': abs(S[:, 4].sum() - ana['run_yds'].sum()) < 1e-9,
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise CoherenceInputError('SC_COH_1_IDENTITY_VIOLATED', ', '.join(bad))
    return len(checks)


def simulate(lib: Library, conc: dict, spec: dict, n_sims: int, seed: int) -> dict:
    """Worlds for one game spec, in the same provider-neutral shape the measurement harness reads."""
    _require(isinstance(lib, Library) and lib.max_season <= MAX_FIT_SEASON, 'SC_COH_1_HELDOUT_LEAK',
             'library is not a <=2024 Library')
    _require(n_sims > 0 and len(spec.get('clubs') or []) == 2, 'SC_COH_1_EMPTY_INPUT', 'need two clubs and n_sims > 0')
    for c in spec['clubs']:
        _require(len(c.get('players') or []) > 0, 'SC_COH_1_EMPTY_INPUT', f"{c.get('club')} has no players")
    rng = np.random.default_rng(seed)
    nb = lib.neighbours(spec['total_line'], spec['home_spread'])
    home, away = spec['clubs']
    stat = {p['id']: np.zeros((n_sims, 10)) for c in spec['clubs'] for p in c['players']}
    pts = {home['club']: np.zeros(n_sims), away['club']: np.zeros(n_sims)}
    tds = {home['club']: np.zeros(n_sims), away['club']: np.zeros(n_sims)}
    dst = {home['club']: np.zeros(n_sims), away['club']: np.zeros(n_sims)}
    n_checks = 0
    picks = nb[rng.integers(0, len(nb), size=n_sims)]
    for w, gi in enumerate(picks):
        g = lib.games[gi]
        for c, side, oside in ((home, 'home', 'away'), (away, 'away', 'home')):
            ana = g[side]
            S, td, p = _club_world(c, ana, conc, rng)
            isqb = np.array([q['position'] == 'QB' for q in c['players']])
            n_checks += verify(S, isqb, td, p, ana)
            for i, q in enumerate(c['players']):
                stat[q['id']][w] = S[i]
            pts[c['club']][w], tds[c['club']][w] = p, td
            sk, it, fr, dtd, sf = ana['dst']
            dst[c['club']][w] = (M.dst_tier(g[oside]['points'])[0] + sk + 2 * it + 2 * fr + 6 * dtd + 2 * sf)
    return {'stat_draws': {k: v.tolist() for k, v in stat.items()}, 'dst': {k: v.tolist() for k, v in dst.items()},
            'club_points': {k: v.tolist() for k, v in pts.items()}, 'club_td': {k: v.tolist() for k, v in tds.items()},
            'identity_checks_passed': n_checks, 'neighbours': [lib.games[i]['game_id'] for i in nb]}
