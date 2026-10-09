"""QBCTX shadow candidate: team volume, pass rate, QB rushing and teammate shares CONDITIONED ON THE
KNOWN PREGAME STARTER, by hierarchical partial pooling. SHADOW RESEARCH ONLY -- nothing in production
reads this module and it changes no production behaviour.

Root cause it answers: docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md (proj_v1.team_volume has no QB
argument; QB rushing uses a generic cohort prior; starts and relief are pooled).

=====================================================================================================
PREDECLARATION -- written 2026-10-09 BEFORE any evaluation number was computed. Not to be edited after
results exist; any later change is appended below as a dated AMENDMENT and the original text stays.
=====================================================================================================

P1. STARTER RULE. The starter of a team-game is the passer with the most dropbacks (nflverse
    qb_dropback == 1, attributed by the `id` column, regular season, two-point tries excluded). Ties
    break on pass attempts, then on player id (deterministic). A team-game whose leader had < 60% of
    the club's dropbacks is flagged SPLIT. In the evaluation the starter so identified is treated as
    the KNOWN PREGAME STARTER (identity oracle, as in the brief); volume is not an oracle.

P2. QUANTITIES. (a) team dropbacks [primary volume quantity; pass attempts excluding sacks are
    reported as a secondary quantity with no acceptance bar]; (b) team pass rate =
    dropbacks / (dropbacks + designed runs); (c) starter QB rush attempts = his designed runs +
    his scrambles (kneels excluded); (d) teammate target shares -- REPORT ONLY, no bar.

P3. ARMS. INCUMBENT = the same quantities with no QB argument, mirroring proj_v1.team_volume (current
    season club mean blended with the prior-season club mean at TEAM_VOLUME_PRIOR_GAMES pseudo-games,
    read from proj_v1's own source) and proj_v1._combine for QB carries (QB's pooled carry share over
    every game he appeared in, starts and relief together, blended with his own prior-season pooled
    share or a generic all-QB cohort share, prior weight capped at PRIOR_WEIGHT_CAP). CANDIDATE = the
    incumbent club baseline PLUS a QB-specific deviation estimated from that QB's prior games (starts
    at weight 1; relief appearances as separate, down-weighted evidence), shrunk toward a population
    prior by empirical Bayes; QB rushing = his per-dropback rush rate from all prior games, all clubs,
    shrunk toward a position prior estimated from data. The declared treatment is the QB term; the
    club baseline is identical in both arms.

P4. POINT IN TIME. A forecast for a game dated D reads only games dated strictly before D. Asserted
    in code (PointInTimeViolation). Population priors for evaluation season S are fitted on seasons
    < S only (forward chained): S=2024 fits on <=2023, S=2025 on <=2024, the 2026 prospective run on
    <=2025.

P5. EVALUATION SEASONS 2024 and 2025, regular season, every team-game (two rows per game, one per
    club). Subsets:
      QB-CHANGE = the starter differs from the club's dominant starter of its prior window, where the
                  prior window is the club's last 8 games (crossing seasons) and the dominant starter
                  is the QB with the most dropbacks in that window;
      STABLE    = the starter equals that dominant starter.
    The PRIMARY analysis includes every team-game (SPLIT included: excluding them would condition on
    an outcome). A SENSITIVITY analysis excludes SPLIT team-games. Both are reported.

P6. METRICS per arm, subset and quantity: n, MAE, RMSE, mean error (bias, defined forecast minus
    actual). Paired cluster bootstrap of the MAE difference (candidate minus incumbent): resample
    team-season clusters with replacement within the subset, B = 4000, seed 20261009, 95% percentile
    interval.

P7. ACCEPTANCE, applied separately to each of (a) dropbacks, (b) pass rate, (c) QB rush attempts:
      PASS iff  [QB-CHANGE: MAE difference 95% CI upper bound < 0]
           AND  [STABLE:    MAE difference 95% CI upper bound <= +0.02 x incumbent STABLE MAE].
    The OVERALL candidate passes only if all three quantities pass. Pass attempts (secondary) and
    teammate shares (d) carry no bar. The bar is not loosened after results exist; a failure is
    reported as a failure.

P8. PROSPECTIVE 2026 weeks 1-5 are DESCRIPTIVE ONLY (n is tiny, and nothing is tuned to TB@DAL or to
    any 2026 game). Week 5 2026 forecasts are produced for the 16 Sunday-early clubs with the
    starters listed in WEEK5_QB_REGIME_BOARD.json.
=====================================================================================================

AMENDMENT A1 -- 2026-10-09, made AFTER fitting the population priors and BEFORE computing any
evaluation metric (no MAE, CI or verdict had been computed). P1, P2, P4-P8 and the bar are unchanged.

  What was found. The first implementation took the QB deviation as the mean residual (club actual
  minus club baseline) over the QB's starts. For a club's regular starter the baseline is built from
  his own games, so that residual is ~0 by construction; pooling those with genuine contrasts made
  the between-QB variance tiny (dropbacks: tau2 ~ 0.8-1.4 against sigma2 ~ 67, i.e. one start would
  move the forecast by 1-2% of its observed deviation). That is a parametrisation defect, not
  evidence: it measures "a QB against himself".

  What replaces it (a derivation, no new constant). Let the baseline be B = sum_g w_g y_g with the
  proj_v1 blend weights w_g, and let y_g carry sum_Q f_Qg theta_Q, with f_Qg the QB's dropback share
  in game g. Then for QB q the residual satisfies E[r_g] = (f_qg - c_q,g) * Delta_q, where
  c_q,g = sum_h w_h f_qh is q's share of the baseline's composition and Delta_q = theta_q minus
  the others in that club's composition. So every club-game observes Delta_q with exposure
  a = f - c: a start under a baseline built from other QBs has a ~ 1; a regular starter's start has
  a ~ 0 (no information, correctly); a relief cameo has a small positive a; a game the regular
  starter MISSED has a = -c (it is evidence about him too). Model r = a*Delta_q + e, e ~ N(0, s2),
  Delta_q ~ N(MU0 = 0, tau2). tau2 and s2 are estimated per fit window by profile maximum
  likelihood over QB starts (closed form per QB by Sherman-Morrison); the forecast adds
  (S_START - c_q,target) * E[Delta_q | his prior rows], every prior row (start, relief, absent)
  entering through its own exposure a. This supersedes the RELIEF_WEIGHT_TEAM = f^2 rule, which is
  the special case c = 0. QB rushing and teammate shares are unchanged.
=====================================================================================================
"""
from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import sys

import numpy as np
import pandas as pd

_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
PBP_HIST = sorted((_REPO / 'nfl/research/postgame').glob('pbp_202[1-5].*.csv.gz'))
PBP_2026 = sorted((_REPO / 'nfl/dfs/salaries/raw/classic_early_2026W5').glob('NFLVERSE_PBP_2026.*.csv.gz'))
ROSTER_2026 = sorted((_REPO / 'nfl/dfs/salaries/raw/classic_early_2026W5').glob(
    'NFLVERSE_ROSTER_WEEKLY_2026.*.csv.gz'))
BOARD = _REPO / 'nfl/dfs/salaries/classic_early_2026W5/WEEK5_QB_REGIME_BOARD.json'
PROJ_V1 = _REPO / 'nfl/tools/proj_v1.py'
OUT_EVAL = _HERE / 'QBCTX_SHADOW_EVAL.json'
OUT_W5 = _HERE / 'QBCTX_W5_2026_FORECASTS.json'

ARM = 'QBCTX_2026_10_ROLE_SHADOW'
LABEL = 'SHADOW_RESEARCH_NOT_PRODUCTION'


# ----------------------------------------------------------------------------------- named errors
class QbctxError(RuntimeError):
    """Base class. Every stage raises a NAMED error rather than returning an empty or partial result."""


class EmptyInputError(QbctxError):
    pass


class SchemaError(QbctxError):
    pass


class PointInTimeViolation(QbctxError):
    """A forecast was handed a game dated on or after the forecast date."""


class StarterResolutionError(QbctxError):
    pass


# -------------------------------------------------------------------------------------- constants
def proj_v1_constant(name: str):
    """Read a module-level literal from proj_v1's SOURCE, without importing it (importing proj_v1
    pulls in the production market layer). Reading the source keeps the incumbent in step with the
    production value rather than copying a number that could drift."""
    tree = ast.parse(PROJ_V1.read_text(encoding='utf-8'))
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        for t in targets:
            if isinstance(t, ast.Name) and t.id == name:
                return ast.literal_eval(node.value)
    raise SchemaError(f'proj_v1 defines no module-level literal {name!r}')


TEAM_VOLUME_PRIOR_GAMES = float(proj_v1_constant('TEAM_VOLUME_PRIOR_GAMES'))
PRIOR_WEIGHT_CAP = float(proj_v1_constant('PRIOR_WEIGHT_CAP'))
SPLIT_THRESHOLD = 0.60
DOMINANT_WINDOW = 8
TEAMMATE_WINDOW = 8
MU0 = 0.0
EVAL_SEASONS = (2024, 2025)
BOOT_B = 4000
BOOT_SEED = 20261009
CI_LEVEL = 0.95
NONINF_FRAC = 0.02
INTERVAL_LEVEL = 0.80
W5_CUTOFF = '2026-10-11'

CONSTANTS_PROVENANCE = {
    'TEAM_VOLUME_PRIOR_GAMES': (TEAM_VOLUME_PRIOR_GAMES, 'READ from nfl/tools/proj_v1.py source (production '
                                'DECLARED pseudo-games). Used identically in both arms, so the club baseline is '
                                'the incumbent\'s and is not part of the treatment.'),
    'PRIOR_WEIGHT_CAP': (PRIOR_WEIGHT_CAP, 'READ from nfl/tools/proj_v1.py source. Incumbent QB-carry blend only.'),
    'SPLIT_THRESHOLD': (SPLIT_THRESHOLD, 'SPECIFIED by the task brief (flag games whose dropback leader had < 60%). '
                        'A labelling threshold: it never changes a forecast; it only defines the sensitivity subset.'),
    'DOMINANT_WINDOW': (DOMINANT_WINDOW, 'SPECIFIED by the task brief ("e.g. last 8 club games"). Defines the '
                        'QB-CHANGE / STABLE subsets only; not a model input.'),
    'TEAMMATE_WINDOW': (TEAMMATE_WINDOW, 'DOCUMENTED PRIOR: same 8-game window as the subset definition, for the '
                        'report-only teammate shares. Not tuned.'),
    'MU0': (MU0, 'DOCUMENTED PRIOR, owner ruling 2026-10-08: no universal backup-QB penalty. The population mean of '
            'the QB deviation is fixed at 0 so the treatment is QB-SPECIFIC only; the empirical mean is reported '
            'as a diagnostic and is NOT used.'),
    'EXPOSURE_A': ('f - c', 'DERIVED (amendment A1): a club-game observes the QB contrast Delta_q with exposure '
                   'a = (his dropback share f) - (his share c of the baseline composition). Starts, relief and '
                   'missed games all enter through a; supersedes the original f^2 relief rule (the case c = 0).'),
    'RELIEF_WEIGHT_RUSH': ('estimated', 'ESTIMATED per fit window: inverse-variance ratio s2_start / s2_relief of '
                           'per-dropback rush-rate noise about the QB\'s start rate, capped at 1 (DOCUMENTED PRIOR: '
                           'a relief appearance never outweighs a start).'),
    'TAU2 / SIGMA2 (volume, pass rate, pass attempts)': ('estimated', 'ESTIMATED per fit window by profile maximum '
                                                          'likelihood of r = a*Delta_q + e over QB starts (A1); the '
                                                          'likelihood is maximised over a log grid of tau2/s2 whose '
                                                          'resolution is computational, not a model constant.'),
    'P0 / TAU2 / S2 (rush rate)': ('estimated', 'ESTIMATED per fit window: pooled position rate, between-QB variance '
                                   'by weighted method of moments, overdispersed within-QB noise.'),
    'S_START': ('estimated', 'ESTIMATED per fit window: mean starter share of club dropbacks over all starts.'),
    'COHORT_CARRY_SHARE': ('estimated', 'ESTIMATED per fit window: pooled QB carry share over all QB appearances '
                           '(approximates proj_v1 ARCHETYPE cohort prior; see INCUMBENT_APPROXIMATION).'),
    'TEAMMATE TAU2 / S2': ('estimated', 'ESTIMATED per fit window by method of moments on (dominant-QB minus '
                           'other-QB) share contrasts within player-club-seasons.'),
    'EVAL_SEASONS': (EVAL_SEASONS, 'SPECIFIED by the task brief.'),
    'BOOT_B / BOOT_SEED': ((BOOT_B, BOOT_SEED), 'PREDECLARED (P6). Seed is the predeclaration date.'),
    'CI_LEVEL': (CI_LEVEL, 'SPECIFIED by the task brief.'),
    'NONINF_FRAC': (NONINF_FRAC, 'SPECIFIED by the task brief (+2% of incumbent STABLE MAE).'),
    'INTERVAL_LEVEL': (INTERVAL_LEVEL, 'DOCUMENTED reporting choice for Week 5 intervals (empirical out-of-sample '
                       'error quantiles 10/90 from 2024-2025). Changes no point forecast.'),
    'W5_CUTOFF': (W5_CUTOFF, 'Sunday 2026-10-11 kickoff date from WEEK5_QB_REGIME_BOARD.json meta.kickoff_utc.'),
}

INCUMBENT_APPROXIMATION = (
    'Team volume: proj_v1.team_volume formula exactly (current-season club mean blended with prior-season club '
    'mean at TEAM_VOLUME_PRIOR_GAMES pseudo-games), MINUS the market-response adjustment (the FOOTBALL_ONLY arm '
    'path; no historical lines are joined here). Pass rate: blended dropbacks / (blended dropbacks + blended '
    'designed runs). QB carries: proj_v1._combine of (prior = the QB\'s own pooled carry share over all PRIOR '
    'seasons, every role, weight = his prior-season appearances capped at PRIOR_WEIGHT_CAP; or, with no prior-'
    'season appearance, the all-QB cohort share at weight PRIOR_WEIGHT_CAP) and (current = his pooled carry share '
    'over every current-season game he appeared in, starts and relief together, weight = those games), times the '
    'blended club carries. NOT mirrored: player_prior recency decay and role-similarity weighting, the six-tier '
    'ladder (approximated by own-history-else-cohort), allocate_opportunity renormalisation across the roster, '
    'the depth-rank appearance discount (the starter is known, so rank 1 applies no discount in proj_v1 either), '
    'and the market response.')

COLS = ['game_id', 'play_id', 'season', 'week', 'season_type', 'game_date', 'posteam', 'play_type', 'pass',
        'rush', 'qb_dropback', 'qb_scramble', 'sack', 'pass_attempt', 'two_point_attempt', 'id',
        'rusher_player_id', 'receiver_player_id', 'passer_player_name', 'name', 'receiver_player_name',
        'rusher_player_name']
VOL_Q = ('dropbacks', 'pass_att', 'pass_rate')


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------ load
def load_plays(paths) -> pd.DataFrame:
    """Regular-season scrimmage plays with the flags this module uses. Raises on empty or bad schema."""
    paths = list(paths)
    if not paths:
        raise EmptyInputError('no play-by-play paths given')
    frames = []
    for p in paths:
        d = pd.read_csv(p, usecols=lambda c: c in COLS, low_memory=False)
        missing = sorted(set(COLS) - set(d.columns))
        if missing:
            raise SchemaError(f'{p}: missing columns {missing}')
        if d.empty:
            raise EmptyInputError(f'{p}: zero rows')
        frames.append(d)
    d = pd.concat(frames, ignore_index=True).drop_duplicates(['game_id', 'play_id'])
    d = d[(d['season_type'] == 'REG') & d['play_type'].isin(['pass', 'run'])
          & (d['two_point_attempt'].fillna(0) != 1) & d['posteam'].notna()]
    if d.empty:
        raise EmptyInputError('no regular-season scrimmage plays after filtering')
    db = d['qb_dropback'].fillna(0) == 1
    designed = (d['rush'].fillna(0) == 1) & ~db
    scramble = db & (d['qb_scramble'].fillna(0) == 1)
    passatt = (d['play_type'] == 'pass') & (d['pass_attempt'].fillna(0) == 1) & (d['sack'].fillna(0) != 1)
    return pd.DataFrame({
        'game_id': d['game_id'].astype(str), 'season': d['season'].astype(int), 'week': d['week'].astype(int),
        'date': d['game_date'].astype(str), 'club': d['posteam'].astype(str),
        'db': db.astype(int), 'designed': designed.astype(int), 'scramble': scramble.astype(int),
        'passatt': passatt.astype(int),
        'qb': d['id'].where(db), 'qb_name': d['passer_player_name'].fillna(d['name']).where(db),
        'rusher': d['rusher_player_id'].where(designed),
        'receiver': d['receiver_player_id'].where(passatt),
        'receiver_name': d['receiver_player_name'].where(passatt),
        'rusher_name': d['rusher_player_name'].where(designed),
    })


def player_names(plays: pd.DataFrame) -> dict:
    """gsis id -> nflverse abbreviated name, for labelling outputs only (never a model input)."""
    out = {}
    for idc, nc in (('rusher', 'rusher_name'), ('receiver', 'receiver_name'), ('qb', 'qb_name')):
        s = plays[[idc, nc]].dropna().drop_duplicates(idc)
        out.update(dict(zip(s[idc], s[nc])))
    return out


# ------------------------------------------------------------------------------------ team games
def starter_of(qb_rows: pd.DataFrame) -> pd.DataFrame:
    """P1 starter rule over a per-(game, club, qb) frame with columns dropbacks, pass_att, qb.
    Returns one row per (game_id, club): starter, starter_share, split."""
    if qb_rows.empty:
        raise EmptyInputError('no QB rows to resolve a starter from')
    tot = qb_rows.groupby(['game_id', 'club'])['dropbacks'].transform('sum')
    r = qb_rows.assign(_share=qb_rows['dropbacks'] / tot)
    r = r.sort_values(['game_id', 'club', 'dropbacks', 'pass_att', 'qb'],
                      ascending=[True, True, False, False, True])
    s = r.groupby(['game_id', 'club'], as_index=False).first()
    return pd.DataFrame({'game_id': s['game_id'], 'club': s['club'], 'starter': s['qb'],
                         'starter_share': s['_share'], 'split': s['_share'] < SPLIT_THRESHOLD})


def build_tables(plays: pd.DataFrame) -> dict:
    """Team-game, QB-game, receiver-game and residual tables. Every table carries `date` for the PIT guard."""
    keys = ['game_id', 'club']
    g = plays.groupby(keys)
    tg = g.agg(season=('season', 'first'), week=('week', 'first'), date=('date', 'first'),
               dropbacks=('db', 'sum'), pass_att=('passatt', 'sum'), designed=('designed', 'sum'),
               scrambles=('scramble', 'sum'), targets=('receiver', 'count')).reset_index()
    tg['carries'] = tg['designed'] + tg['scrambles']
    tg['plays'] = tg['dropbacks'] + tg['designed']
    tg['pass_rate'] = tg['dropbacks'] / tg['plays']
    dbp = plays[plays['db'] == 1]
    qbg = dbp.groupby(keys + ['qb']).agg(dropbacks=('db', 'sum'), pass_att=('passatt', 'sum'),
                                         scrambles=('scramble', 'sum'),
                                         qb_name=('qb_name', 'first')).reset_index()
    des = plays[plays['designed'] == 1].groupby(keys + ['rusher']).size().rename('designed_by').reset_index()
    qbg = qbg.merge(des.rename(columns={'rusher': 'qb'}), on=keys + ['qb'], how='left')
    qbg['designed_by'] = qbg['designed_by'].fillna(0).astype(int)
    qbg['rush'] = qbg['designed_by'] + qbg['scrambles']
    st = starter_of(qbg)
    tg = tg.merge(st, on=keys, how='left')
    if tg['starter'].isna().any():
        raise StarterResolutionError(f'{int(tg["starter"].isna().sum())} team-games have no dropback at all')
    qbg = qbg.merge(tg[keys + ['season', 'week', 'date', 'starter', 'dropbacks', 'carries']]
                    .rename(columns={'dropbacks': 'team_db', 'carries': 'team_carries'}), on=keys)
    qbg['f'] = qbg['dropbacks'] / qbg['team_db']
    qbg['role'] = np.where(qbg['qb'] == qbg['starter'], 'START', 'RELIEF')
    srush = qbg[qbg['role'] == 'START'][keys + ['rush']].rename(columns={'rush': 'starter_rush'})
    tg = tg.merge(srush, on=keys, how='left')
    # receiver-games: targets, plus designed carries by non-QBs, for the "active" proxy
    tgt = plays[plays['receiver'].notna()].groupby(keys + ['receiver']).size().rename('tgt').reset_index()
    tgt = tgt.rename(columns={'receiver': 'player'})
    car = plays[plays['designed'] == 1].groupby(keys + ['rusher']).size().rename('car').reset_index()
    car = car.rename(columns={'rusher': 'player'})
    rec = tgt.merge(car, on=keys + ['player'], how='outer').fillna({'tgt': 0, 'car': 0})
    rec = rec[~rec['player'].isin(set(qbg['qb']))]
    rec = rec.merge(tg[keys + ['season', 'date', 'starter', 'targets']], on=keys)
    rec['share'] = (rec['tgt'] / rec['targets'].where(rec['targets'] > 0)).astype(float)
    tg = tg.sort_values(['club', 'date', 'game_id']).reset_index(drop=True)
    for name, t in (('team-game', tg), ('qb-game', qbg), ('receiver-game', rec)):
        if t.empty:
            raise EmptyInputError(f'{name} table is empty')
    tables = {'tg': tg, 'qbg': qbg, 'rec': rec}
    tables['resid'] = residual_rows(tables)
    return tables


# --------------------------------------------------------------------------- point-in-time guard
def assert_point_in_time(hist: dict, cutoff: str) -> None:
    """Every table handed to a forecast must hold only games dated strictly before `cutoff`."""
    for name, t in hist.items():
        if len(t) and str(t['date'].max()) >= cutoff:
            raise PointInTimeViolation(
                f'{name}: holds a game dated {t["date"].max()} for a forecast dated {cutoff}')


def history_before(tables: dict, cutoff: str) -> dict:
    return {k: v[v['date'] < cutoff] for k, v in tables.items()}


# -------------------------------------------------------------------------------- club baseline
BASE_FIELDS = ('dropbacks', 'pass_att', 'designed', 'carries', 'targets')


def blend(cur_vals, prv_vals, prior_games=None):
    """proj_v1.team_volume's blend for one field: current mean weighted by its game count, prior-season
    mean weighted by TEAM_VOLUME_PRIOR_GAMES pseudo-games."""
    wp_decl = TEAM_VOLUME_PRIOR_GAMES if prior_games is None else prior_games
    n_cur, n_prv = len(cur_vals), len(prv_vals)
    per_cur = (sum(cur_vals) / n_cur) if n_cur else None
    per_prv = (sum(prv_vals) / n_prv) if n_prv else None
    if per_cur is None:
        return per_prv
    if per_prv is None:
        return per_cur
    wc, wp = float(n_cur), (wp_decl if n_prv else 0.0)
    return (wc * per_cur + wp * per_prv) / (wc + wp)


def club_baseline(club_hist: pd.DataFrame, season: int):
    """The incumbent club baseline from that club's games already filtered to before the cutoff.
    Also returns the per-game weight each game carries in the blend (`weights`, game_id -> w), which
    the composition c of amendment A1 is computed from."""
    cur = club_hist[club_hist['season'] == season]
    prv = club_hist[club_hist['season'] == season - 1]
    if cur.empty and prv.empty:
        return None
    b = {f: blend(list(cur[f]), list(prv[f])) for f in BASE_FIELDS}
    b['pass_rate'] = b['dropbacks'] / (b['dropbacks'] + b['designed'])
    nc, npv = len(cur), len(prv)
    wp = TEAM_VOLUME_PRIOR_GAMES if npv else 0.0
    w = {}
    for gid in cur['game_id']:
        w[gid] = 1.0 / (nc + wp)
    for gid in prv['game_id']:
        w[gid] = (wp / (nc + wp) / npv) if nc else 1.0 / npv
    b['n_cur'], b['n_prv'], b['weights'] = nc, npv, w
    return b


def composition(weights: dict, qbg_club: pd.DataFrame) -> dict:
    """c_Q = sum_g w_g f_Qg: each QB's share of the baseline, from the blend weights and dropback shares."""
    if not weights:
        return {}
    q = qbg_club[qbg_club['game_id'].isin(weights)]
    c = (q['game_id'].map(weights) * q['f']).groupby(q['qb']).sum()
    return {k: float(v) for k, v in c.items()}


def residual_rows(tables: dict) -> pd.DataFrame:
    """Per (club-game, QB): the club's actual minus the club's point-in-time baseline, with the QB's
    exposure a = f - c (amendment A1). A QB enters a game's rows if he appeared in it OR is part of the
    baseline composition (role ABSENT, f = 0).
    RESIDUAL UNIVERSE: only team-games whose baseline carries a prior-season component (n_prv > 0), so
    the residuals the priors are fitted on have the same baseline structure as every evaluation
    forecast. 2021 therefore serves as prior-season support for 2022 and produces no residual itself."""
    tg, qbg = tables['tg'], tables['qbg']
    rows = []
    for club, ct in tg.groupby('club', sort=False):
        ct = ct.sort_values(['date', 'game_id'])
        qc = qbg[qbg['club'] == club]
        by_game = {gid: grp for gid, grp in qc.groupby('game_id')}
        for i in range(len(ct)):
            row = ct.iloc[i]
            b = club_baseline(ct.iloc[:i], int(row['season']))
            if b is None or b['n_prv'] == 0:
                continue
            comp = composition(b['weights'], qc)
            here = by_game.get(row['game_id'])
            fmap = dict(zip(here['qb'], here['f'])) if here is not None else {}
            for qb in set(fmap) | set(comp):
                f, c = float(fmap.get(qb, 0.0)), float(comp.get(qb, 0.0))
                role = ('START' if qb == row['starter'] else 'RELIEF') if qb in fmap else 'ABSENT'
                rows.append({'game_id': row['game_id'], 'club': club, 'qb': qb, 'season': int(row['season']),
                             'date': row['date'], 'f': f, 'c': c, 'a': f - c, 'role': role,
                             **{f'r_{q}': float(row[q]) - b[q] for q in VOL_Q}})
    r = pd.DataFrame(rows)
    if r.empty:
        raise EmptyInputError('no residual rows: no team-game has a prior-season baseline')
    return r


# ---------------------------------------------------------------------------- empirical Bayes fit
#: ratio tau2/s2 searched by profile likelihood. 0 plus a log grid; the resolution is computational.
LAMBDA_GRID = np.concatenate([[0.0], np.logspace(-6, 2, 1601)])


def fit_exposure_model(qb, a, r) -> dict:
    """Profile ML for r_i = a_i * Delta_q + e_i, e ~ N(0, s2), Delta_q ~ N(0, tau2) (amendment A1).
    Per QB, cov = s2 (I + lam a a'), so by Sherman-Morrison the quadratic form is
    r'r - lam (a'r)^2 / (1 + lam a'a) and the log-determinant is log(1 + lam a'a)."""
    df = pd.DataFrame({'qb': list(qb), 'a': list(a), 'r': list(r)}).dropna()
    N, Q = len(df), df['qb'].nunique()
    if N <= Q or Q < 2:
        raise EmptyInputError(f'exposure model needs N > Q >= 2 (N={N}, Q={Q})')
    g = df.assign(aa=df['a'] ** 2, ar=df['a'] * df['r'], rr=df['r'] ** 2).groupby('qb')
    S, T, R = g['aa'].sum().values, g['ar'].sum().values, g['rr'].sum().values
    lam = LAMBDA_GRID[:, None]
    s2 = (R.sum() - (lam * T ** 2 / (1 + lam * S)).sum(1, keepdims=True)) / N
    ll = (-N / 2 * np.log(s2) - 0.5 * np.log1p(lam * S).sum(1, keepdims=True)).ravel()
    i = int(np.argmax(ll))
    l_best, s2_best = float(LAMBDA_GRID[i]), float(s2.ravel()[i])
    big = df[df['a'].abs() > 0.5]
    return {'tau2': l_best * s2_best, 'sigma2': s2_best, 'lambda_tau2_over_s2': l_best,
            'lambda_at_grid_edge': bool(i == len(LAMBDA_GRID) - 1),
            'loglik_best': float(ll[i]), 'loglik_tau2_zero': float(ll[0]),
            'lr_stat_vs_tau2_zero': float(2 * (ll[i] - ll[0])),
            'n_starts': int(N), 'n_qbs': int(Q), 'n_starts_abs_a_gt_half': int(len(big)),
            'mean_r_over_a_where_abs_a_gt_half_DIAGNOSTIC_NOT_USED':
                (float((big['r'] / big['a']).mean()) if len(big) else None),
            'mean_r_all_starts_DIAGNOSTIC_NOT_USED': float(df['r'].mean())}


def fit_priors(tables: dict, season: int) -> dict:
    """Population priors for forecasting season `season`, from seasons strictly before it."""
    res = tables['resid']
    res = res[res['season'] < season]
    starts = res[res['role'] == 'START']
    vol = {q: fit_exposure_model(starts['qb'], starts['a'], starts[f'r_{q}']) for q in VOL_Q}
    qbg = tables['qbg']
    qbg = qbg[qbg['season'] < season]
    st = qbg[qbg['role'] == 'START']
    x_q, n_q = st.groupby('qb')['rush'].sum(), st.groupby('qb')['dropbacks'].sum()
    p_q = x_q / n_q
    p0 = float(x_q.sum() / n_q.sum())
    rate_i = st['rush'] / st['dropbacks']
    s2 = float((st['dropbacks'] * (rate_i - st['qb'].map(p_q)) ** 2).sum() / (len(st) - len(p_q)))
    Ndb = float(n_q.sum())
    tau2_r = max(0.0, float(((n_q * (p_q - p0) ** 2).sum() - (len(p_q) - 1) * s2)
                            / (Ndb - (n_q ** 2).sum() / Ndb)))
    rel = qbg[(qbg['role'] == 'RELIEF') & qbg['qb'].isin(p_q.index)]
    if rel.empty:
        raise EmptyInputError('no relief appearances to estimate the relief rush weight')
    s2_rel = float((rel['dropbacks'] * (rel['rush'] / rel['dropbacks'] - rel['qb'].map(p_q)) ** 2).sum()
                   / len(rel))
    w_rel = min(1.0, s2 / s2_rel)
    tgf = tables['tg'][tables['tg']['season'] < season]
    return {'season': season, 'fit_seasons': sorted(int(s) for s in tgf['season'].unique()),
            'residual_fit_seasons': sorted(int(s) for s in starts['season'].unique()),
            'volume': vol,
            'rush': {'p0': p0, 'tau2': tau2_r, 'tau_sd': float(np.sqrt(tau2_r)), 's2_per_dropback': s2,
                     's2_relief_per_dropback': s2_rel, 'relief_weight': w_rel,
                     'relief_weight_uncapped': s2 / s2_rel, 'n_qbs': int(len(p_q)),
                     'n_start_games': int(len(st)), 'n_relief_games': int(len(rel))},
            's_start': float(tgf['starter_share'].mean()),
            'cohort_carry_share': float(qbg['rush'].sum() / qbg['team_carries'].sum()),
            'teammate': fit_teammate_prior(tables, season)}


def fit_teammate_prior(tables: dict, season: int) -> dict:
    """Between-player variance of the share difference (with the club-season's dominant starter minus
    with any other starter) against its sampling noise. Method of moments, fit seasons only."""
    rec = tables['rec']
    rec = rec[(rec['season'] < season) & ((rec['tgt'] > 0) | (rec['car'] > 0)) & rec['share'].notna()]
    qbg = tables['qbg']
    qbg = qbg[qbg['season'] < season]
    dom = (qbg.groupby(['club', 'season', 'qb'])['dropbacks'].sum().reset_index()
           .sort_values('dropbacks', ascending=False).drop_duplicates(['club', 'season'])
           .rename(columns={'qb': 'dom'})[['club', 'season', 'dom']])
    r = rec.merge(dom, on=['club', 'season'])
    r['with_dom'] = r['starter'] == r['dom']
    keys = ['player', 'club', 'season', 'with_dom']
    m = r.groupby(keys)['share'].transform('mean')
    grp = r.groupby(keys)['share']
    gmean, gn = grp.mean(), grp.size()
    s2 = float(((r['share'] - m) ** 2).sum() / (len(r) - len(gmean)))
    mm, nn = gmean.unstack('with_dom'), gn.unstack('with_dom')
    ok = mm[True].notna() & mm[False].notna()
    d = (mm[True] - mm[False])[ok]
    noise = s2 * (1.0 / nn[True][ok] + 1.0 / nn[False][ok])
    tau2 = max(0.0, float((d ** 2).mean() - noise.mean()))
    return {'tau2': tau2, 's2_per_game': s2, 'n_contrasts': int(ok.sum())}


# ------------------------------------------------------------------------------------- forecast
def _combine(prior_value, prior_n, cur_value, cur_n, cap):
    """proj_v1._combine, reimplemented (importing proj_v1 would load the production market layer)."""
    pn = min(float(prior_n or 0.0), float(cap))
    cn = float(cur_n or 0.0)
    if prior_value is None and cur_value is None:
        return None
    if prior_value is None:
        return cur_value
    if cur_value is None or cn <= 0:
        return prior_value
    return (pn * prior_value + cn * cur_value) / (pn + cn)


def forecast(tables: dict, priors: dict, club: str, season: int, cutoff: str, starter: str) -> dict:
    """Forecast one team-game dated `cutoff` for `club` with known `starter`. Reads only earlier games."""
    return forecast_from_history(history_before(tables, cutoff), priors, club, season, cutoff, starter)


def forecast_from_history(hist: dict, priors: dict, club: str, season: int, cutoff: str, starter: str) -> dict:
    assert_point_in_time(hist, cutoff)
    if priors['season'] != season or max(priors['fit_seasons']) >= season:
        raise PointInTimeViolation(f'priors fitted for {priors["season"]} on {priors["fit_seasons"]} used for '
                                   f'season {season}')
    tg, qbg, res, rec = hist['tg'], hist['qbg'], hist['resid'], hist['rec']
    ct = tg[tg['club'] == club].sort_values(['date', 'game_id'])
    b = club_baseline(ct, season)
    if b is None:
        raise EmptyInputError(f'{club}: no club history before {cutoff}')
    out = {'club': club, 'season': season, 'cutoff': cutoff, 'starter': starter,
           'baseline_games': {'current_season': b['n_cur'], 'prior_season': b['n_prv']}}
    # subset: dominant starter of the club's last DOMINANT_WINDOW games
    last = ct.tail(DOMINANT_WINDOW)['game_id']
    w = qbg[(qbg['club'] == club) & qbg['game_id'].isin(last)]
    dom = w.groupby('qb')['dropbacks'].sum().sort_values(ascending=False)
    out['dominant_starter'] = dom.index[0] if len(dom) else None
    out['subset'] = 'STABLE' if out['dominant_starter'] == starter else 'QB_CHANGE'
    # --- team volume: incumbent baseline + (S_START - c) x shrunk QB contrast (amendment A1)
    mine = res[res['qb'] == starter]
    c_t = composition(b['weights'], qbg[qbg['club'] == club]).get(starter, 0.0)
    a_t = priors['s_start'] - c_t
    S = float((mine['a'] ** 2).sum())
    out['qb_evidence'] = {'starts': int((mine['role'] == 'START').sum()),
                          'relief': int((mine['role'] == 'RELIEF').sum()),
                          'absent_from_baseline_games': int((mine['role'] == 'ABSENT').sum()),
                          'exposure_info_sum_a2': S, 'baseline_composition_c': float(c_t),
                          'target_exposure_a': float(a_t)}
    inc, cand, dev = {}, {}, {}
    for q in VOL_Q:
        pr = priors['volume'][q]
        lam, s2 = pr['lambda_tau2_over_s2'], pr['sigma2']
        T = float((mine['a'] * mine[f'r_{q}']).sum())
        shrink = lam * S / (1 + lam * S)
        contrast = MU0 + lam * (T - MU0 * S) / (1 + lam * S)   # posterior mean of Delta_q
        d = a_t * contrast
        dev[q] = {'raw_contrast': (T / S if S > 0 else None), 'shrink': float(shrink),
                  'posterior_contrast': float(contrast),
                  'posterior_contrast_sd': float(np.sqrt(s2 * lam / (1 + lam * S))),
                  'delta_applied': float(d)}
        inc[q] = float(b[q])
        cand[q] = float(b[q] + d)
    cand['pass_rate'] = float(min(1.0, max(0.0, cand['pass_rate'])))
    # --- QB rushing, candidate: per-dropback rate, all prior games, all clubs, shrunk to position prior
    rp = priors['rush']
    qg = qbg[qbg['qb'] == starter]
    qs, qr = qg[qg['role'] == 'START'], qg[qg['role'] == 'RELIEF']
    x = qs['rush'].sum() + rp['relief_weight'] * qr['rush'].sum()
    n = qs['dropbacks'].sum() + rp['relief_weight'] * qr['dropbacks'].sum()
    if n > 0 and rp['tau2'] > 0:
        bs = n * rp['tau2'] / (n * rp['tau2'] + rp['s2_per_dropback'])
        rate = rp['p0'] + bs * (x / n - rp['p0'])
    else:
        bs, rate = 0.0, rp['p0']
    cand['qb_rush'] = float(rate * cand['dropbacks'] * priors['s_start'])
    out['rush_evidence'] = {'start_games': int(len(qs)), 'relief_games': int(len(qr)),
                            'start_rush': int(qs['rush'].sum()), 'start_dropbacks': int(qs['dropbacks'].sum()),
                            'relief_rush': int(qr['rush'].sum()), 'relief_dropbacks': int(qr['dropbacks'].sum()),
                            'raw_rate': (float(x / n) if n > 0 else None), 'shrink': float(bs),
                            'rate': float(rate), 'position_prior_p0': rp['p0']}
    # --- QB rushing, incumbent: proj_v1 carry-share blend, starts and relief pooled
    prv = qg[qg['season'] < season]
    cur = qg[qg['season'] == season]
    if len(prv) and prv['team_carries'].sum() > 0:
        p_val, p_n, tier = float(prv['rush'].sum() / prv['team_carries'].sum()), len(prv), 'PLAYER_OWN_POOLED'
    else:
        p_val, p_n, tier = priors['cohort_carry_share'], PRIOR_WEIGHT_CAP, 'COHORT'
    c_val = (float(cur['rush'].sum() / cur['team_carries'].sum())
             if len(cur) and cur['team_carries'].sum() > 0 else None)
    share = _combine(p_val, p_n, c_val, len(cur), PRIOR_WEIGHT_CAP)
    inc['qb_rush'] = float(share * b['carries'])
    out['incumbent_rush_basis'] = {'prior_tier': tier, 'prior_share': p_val, 'prior_n': float(p_n),
                                   'current_share_pooled_all_roles': c_val, 'current_n': int(len(cur)),
                                   'combined_carry_share': float(share), 'club_carries': float(b['carries'])}
    out['incumbent'], out['candidate'], out['qb_deviation'] = inc, cand, dev
    out['teammates'] = teammate_shares(ct, rec, priors['teammate'], season, starter)
    return out


def teammate_shares(ct: pd.DataFrame, rec: pd.DataFrame, tm: dict, season: int, starter: str) -> list:
    """REPORT ONLY. Incumbent = mean share over the club's last TEAMMATE_WINDOW games in which the player
    was active (>= 1 target or designed carry: a proxy, no snap data is joined). Candidate = incumbent
    plus the shrunk (with this QB minus with other QBs) difference over the current and prior season,
    scaled by the fraction of the incumbent window NOT already started by this QB."""
    if ct.empty:
        return []
    club = ct['club'].iloc[0]
    last = set(ct.tail(TEAMMATE_WINDOW)['game_id'])
    r = rec[(rec['club'] == club) & ((rec['tgt'] > 0) | (rec['car'] > 0)) & rec['share'].notna()]
    r8 = r[r['game_id'].isin(last)]
    out = []
    for p, pr in r8.groupby('player'):
        if pr['tgt'].sum() <= 0:
            continue
        inc = float(pr['share'].mean())
        frac_q = float((pr['starter'] == starter).mean())
        h = r[(r['player'] == p) & r['season'].isin([season, season - 1])]
        w1, w0 = h[h['starter'] == starter]['share'], h[h['starter'] != starter]['share']
        d, sh = 0.0, 0.0
        if len(w1) and len(w0) and tm['tau2'] > 0:
            sh = tm['tau2'] / (tm['tau2'] + tm['s2_per_game'] * (1 / len(w1) + 1 / len(w0)))
            d = sh * float(w1.mean() - w0.mean())
        out.append({'player': p, 'incumbent_share': inc,
                    'candidate_share': float(min(1.0, max(0.0, inc + (1 - frac_q) * d))),
                    'games_with_qb': int(len(w1)), 'games_other_qb': int(len(w0)),
                    'share_with_qb_raw': (float(w1.mean()) if len(w1) else None),
                    'share_other_qb_raw': (float(w0.mean()) if len(w0) else None), 'shrink': float(sh)})
    return sorted(out, key=lambda z: -z['incumbent_share'])


# ------------------------------------------------------------------------------------ evaluation
#: quantity -> team-game column holding the realised value
ACTUAL_COL = {'dropbacks': 'dropbacks', 'pass_rate': 'pass_rate', 'qb_rush': 'starter_rush',
              'pass_att': 'pass_att'}
PRIMARY = ('dropbacks', 'pass_rate', 'qb_rush')
SECONDARY = ('pass_att',)


def run_forecasts(tables: dict, priors_by_season: dict, seasons) -> tuple:
    """Forecast every regular-season team-game of `seasons`. Returns (game rows, teammate rows)."""
    tg, rec = tables['tg'], tables['rec']
    rows, tm_rows = [], []
    for S in seasons:
        pri = priors_by_season[S]
        sel = tg[tg['season'] == S]
        if sel.empty:
            raise EmptyInputError(f'no team-games in season {S}')
        for g in sel.itertuples(index=False):
            f = forecast(tables, pri, g.club, S, g.date, g.starter)
            row = {'game_id': g.game_id, 'club': g.club, 'season': S, 'week': int(g.week), 'date': g.date,
                   'starter': g.starter, 'starter_share': float(g.starter_share), 'split': bool(g.split),
                   'subset': f['subset'], 'dominant_starter': f['dominant_starter'], 'cluster': f'{g.club}-{S}',
                   'qb_starts_prior': f['qb_evidence']['starts'], 'qb_relief_prior': f['qb_evidence']['relief']}
            for q, col in ACTUAL_COL.items():
                row[f'act_{q}'] = float(getattr(g, col))
                row[f'inc_{q}'] = f['incumbent'][q]
                row[f'cand_{q}'] = f['candidate'][q]
            rows.append(row)
            act = rec[(rec['game_id'] == g.game_id) & (rec['club'] == g.club)
                      & ((rec['tgt'] > 0) | (rec['car'] > 0))].set_index('player')['share']
            for t in f['teammates']:
                if t['player'] in act.index:   # OUTCOME-CONDITIONED set: player active in the game
                    tm_rows.append({'game_id': g.game_id, 'club': g.club, 'season': S, 'subset': f['subset'],
                                    'cluster': f'{g.club}-{S}', 'player': t['player'],
                                    'act': float(act[t['player']]), 'inc': t['incumbent_share'],
                                    'cand': t['candidate_share']})
    return pd.DataFrame(rows), pd.DataFrame(tm_rows)


def cluster_boot_mae_diff(err_c, err_i, clusters, B=BOOT_B, seed=BOOT_SEED, level=CI_LEVEL):
    """Paired cluster bootstrap of MAE(candidate) - MAE(incumbent), clusters resampled with replacement."""
    err_c, err_i = np.abs(np.asarray(err_c, float)), np.abs(np.asarray(err_i, float))
    if len(err_c) == 0:
        raise EmptyInputError('bootstrap on an empty subset')
    uniq, inv = np.unique(np.asarray(clusters), return_inverse=True)
    sc, si = np.bincount(inv, err_c), np.bincount(inv, err_i)
    nn = np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(B, len(uniq)))
    diff = (sc[idx].sum(1) - si[idx].sum(1)) / nn[idx].sum(1)
    a = (1 - level) / 2
    return {'point': float(err_c.mean() - err_i.mean()), 'ci_lo': float(np.quantile(diff, a)),
            'ci_hi': float(np.quantile(diff, 1 - a)), 'n_clusters': int(len(uniq)), 'B': B, 'seed': seed}


def _arm(e):
    e = np.asarray(e, float)
    return {'mae': float(np.abs(e).mean()), 'rmse': float(np.sqrt((e ** 2).mean())),
            'bias_forecast_minus_actual': float(e.mean())}


def subset_metrics(df: pd.DataFrame, quantities) -> dict:
    out = {}
    for q in quantities:
        ec = df[f'cand_{q}'] - df[f'act_{q}']
        ei = df[f'inc_{q}'] - df[f'act_{q}']
        out[q] = {'n_team_games': int(len(df)), 'incumbent': _arm(ei), 'candidate': _arm(ec),
                  'rmse_diff_cand_minus_inc': float(_arm(ec)['rmse'] - _arm(ei)['rmse']),
                  'mae_diff_cand_minus_inc': cluster_boot_mae_diff(ec, ei, df['cluster'])}
    return out


def verdict(change: dict, stable: dict) -> dict:
    """P7, applied per quantity. Recomputable from the stored numbers alone."""
    out = {}
    for q in PRIMARY:
        c, s = change[q]['mae_diff_cand_minus_inc'], stable[q]['mae_diff_cand_minus_inc']
        margin = NONINF_FRAC * stable[q]['incumbent']['mae']
        ok_c, ok_s = c['ci_hi'] < 0, s['ci_hi'] <= margin
        out[q] = {'qb_change_improves': bool(ok_c), 'qb_change_ci_hi': c['ci_hi'],
                  'stable_noninferior': bool(ok_s), 'stable_ci_hi': s['ci_hi'], 'stable_margin': margin,
                  'PASS': bool(ok_c and ok_s)}
    out['OVERALL_PASS'] = bool(all(out[q]['PASS'] for q in PRIMARY))
    return out


def evaluate(df: pd.DataFrame, tm: pd.DataFrame) -> dict:
    q_all = PRIMARY + SECONDARY
    res = {}
    for label, frame in (('PRIMARY_ALL_TEAM_GAMES', df), ('SENSITIVITY_EXCLUDING_SPLIT', df[~df['split']])):
        ch, st = frame[frame['subset'] == 'QB_CHANGE'], frame[frame['subset'] == 'STABLE']
        mc, ms = subset_metrics(ch, q_all), subset_metrics(st, q_all)
        res[label] = {'QB_CHANGE': mc, 'STABLE': ms, 'verdict': verdict(mc, ms)}
    res['BY_SEASON_DESCRIPTIVE'] = {
        str(S): {sub: subset_metrics(df[(df['season'] == S) & (df['subset'] == sub)], PRIMARY)
                 for sub in ('QB_CHANGE', 'STABLE')} for S in sorted(df['season'].unique())}
    tmres = {}
    for sub in ('QB_CHANGE', 'STABLE'):
        t = tm[tm['subset'] == sub]
        ec, ei = t['cand'] - t['act'], t['inc'] - t['act']
        tmres[sub] = {'n_player_games': int(len(t)), 'incumbent': _arm(ei), 'candidate': _arm(ec),
                      'mae_diff_cand_minus_inc': cluster_boot_mae_diff(ec, ei, t['cluster'])}
    tmres['CAVEAT'] = ('REPORT ONLY, no bar. Player set is OUTCOME-CONDITIONED (players active in the game, '
                       'active = >= 1 target or designed carry); identical set for both arms, so the paired '
                       'difference is interpretable but the levels are not deployable error rates.')
    res['TEAMMATE_TARGET_SHARES_REPORT_ONLY'] = tmres
    return res


def error_quantiles(df: pd.DataFrame) -> dict:
    """Empirical out-of-sample (actual - forecast) quantiles, per arm x subset x quantity, for intervals."""
    a = (1 - INTERVAL_LEVEL) / 2
    out = {}
    for sub in ('QB_CHANGE', 'STABLE'):
        t = df[df['subset'] == sub]
        for arm in ('inc', 'cand'):
            for q in PRIMARY + SECONDARY:
                e = t[f'act_{q}'] - t[f'{arm}_{q}']
                out[(sub, arm, q)] = (float(np.quantile(e, a)), float(np.quantile(e, 1 - a)), int(len(e)))
    return out


# ------------------------------------------------------------------------------------- 2026 runs
def resolve_board_starters(board: dict, roster: pd.DataFrame) -> dict:
    """Listed starter full name -> gsis id via the 2026 weekly roster (club and QB position must match)."""
    out = {}
    r = roster[roster['position'] == 'QB']
    for club, v in board['QB_REGIME_BOARD'].items():
        name = v.get('listed_starter_nflverse_schedule')
        hit = r[(r['team'] == club) & (r['full_name'] == name)]['gsis_id'].dropna().unique()
        if len(hit) != 1:
            raise StarterResolutionError(f'{club}: listed starter {name!r} resolves to {list(hit)}')
        out[club] = {'name': name, 'gsis_id': str(hit[0]), 'board_flags': v.get('flags', []),
                     'board_dominant_passer': v.get('dominant_passer')}
    if len(out) != 16:
        raise StarterResolutionError(f'expected 16 slate clubs, resolved {len(out)}')
    return out


def _r(x, k=3):
    return None if x is None else round(float(x), k)


def labelled_teammates(f: dict, names: dict, k: int) -> list:
    return [{'name': names.get(t['player']), **{kk: (_r(v, 4) if isinstance(v, float) else v)
                                               for kk, v in t.items()}} for t in f['teammates'][:k]]


def w5_row(f: dict, eq: dict, name: str, names: dict) -> dict:
    sub = f['subset']
    row = {'club': f['club'], 'starter': name, 'starter_gsis_id': f['starter'],
           'dominant_starter_prior_8': f['dominant_starter'], 'subset': sub,
           'qb_evidence': f['qb_evidence'],
           'rush_evidence': f['rush_evidence'], 'incumbent_rush_basis': f['incumbent_rush_basis'],
           'qb_deviation': f['qb_deviation'], 'baseline_games': f['baseline_games']}
    for q in PRIMARY + SECONDARY:
        for arm, key in (('incumbent', 'inc'), ('candidate', 'cand')):
            v = f[arm][q]
            lo, hi, n = eq[(sub, key, q)]
            lo_v = max(0.0, v + lo)
            hi_v = v + hi if q != 'pass_rate' else min(1.0, v + hi)
            row.setdefault(q, {})[arm] = {'point': _r(v, 4), f'interval_{int(INTERVAL_LEVEL * 100)}': [
                _r(lo_v, 4), _r(hi_v, 4)], 'interval_basis_n': n}
    row['teammate_target_shares_REPORT_ONLY'] = labelled_teammates(f, names, 8)
    return row


def main(argv=None) -> int:
    paths = PBP_HIST + PBP_2026
    if len(PBP_HIST) != 5 or len(PBP_2026) != 1:
        raise EmptyInputError(f'expected 5 historical + 1 2026 play-by-play files, found {len(PBP_HIST)} + '
                              f'{len(PBP_2026)}')
    plays = load_plays(paths)
    tables = build_tables(plays)
    priors = {S: fit_priors(tables, S) for S in (*EVAL_SEASONS, 2026)}
    df, tm = run_forecasts(tables, priors, EVAL_SEASONS)
    ev = evaluate(df, tm)
    eq = error_quantiles(df)
    names = player_names(plays)
    # prospective 2026, descriptive
    d26, tm26 = run_forecasts(tables, priors, (2026,))
    desc26 = {sub: {q: {'n': int((d26['subset'] == sub).sum()),
                        'incumbent_mae': _r((d26[d26['subset'] == sub][f'inc_{q}']
                                             - d26[d26['subset'] == sub][f'act_{q}']).abs().mean(), 4),
                        'candidate_mae': _r((d26[d26['subset'] == sub][f'cand_{q}']
                                             - d26[d26['subset'] == sub][f'act_{q}']).abs().mean(), 4)}
                    for q in PRIMARY + SECONDARY} for sub in ('QB_CHANGE', 'STABLE')}
    tb = d26[(d26['club'] == 'TB') & (d26['week'].isin([4, 5]))]
    tb_rows = [{'game_id': r.game_id, 'week': int(r.week), 'starter': names.get(r.starter, r.starter),
                'subset': r.subset, 'dominant_starter_prior_8': names.get(r.dominant_starter, r.dominant_starter),
                'qb_prior_starts': int(r.qb_starts_prior), 'qb_prior_relief': int(r.qb_relief_prior),
                **{q: {'actual': _r(getattr(r, f'act_{q}'), 4), 'incumbent': _r(getattr(r, f'inc_{q}'), 4),
                       'candidate': _r(getattr(r, f'cand_{q}'), 4)} for q in PRIMARY + SECONDARY}}
               for r in tb.itertuples(index=False)]
    tb_detail = {}
    for r in tb.itertuples(index=False):
        f = forecast(tables, priors[2026], 'TB', 2026, r.date, r.starter)
        tb_detail[r.game_id] = {'qb_evidence': f['qb_evidence'], 'qb_deviation': f['qb_deviation'],
                                'rush_evidence': f['rush_evidence'],
                                'incumbent_rush_basis': f['incumbent_rush_basis'],
                                'teammates_REPORT_ONLY': labelled_teammates(f, names, 6)}
    # week 5 Sunday-early forecasts
    board = json.loads(BOARD.read_text())
    roster = pd.read_csv(ROSTER_2026[0], low_memory=False)
    starters = resolve_board_starters(board, roster)
    w5 = {}
    for club, s in sorted(starters.items()):
        f = forecast(tables, priors[2026], club, 2026, W5_CUTOFF, s['gsis_id'])
        row = w5_row(f, eq, s['name'], names)
        row['dominant_starter_prior_8_name'] = names.get(f['dominant_starter'], f['dominant_starter'])
        row['board_flags'] = s['board_flags']
        w5[club] = row
    inputs = {str(p.relative_to(_REPO)): sha256(p) for p in paths + [BOARD, ROSTER_2026[0], PROJ_V1]}
    fp = {'arm': ARM, 'label': LABEL, 'module_sha256': sha256(__file__), 'inputs_sha256': inputs,
          'boot': {'B': BOOT_B, 'seed': BOOT_SEED}, 'python': sys.version.split()[0],
          'numpy': np.__version__, 'pandas': pd.__version__}
    n_split = int(df['split'].sum())
    eval_art = {
        'artifact': 'QBCTX_SHADOW_EVAL', 'label': LABEL, 'fingerprint': fp,
        'predeclaration': ('module docstring P1-P8, committed alone before any result (commit dd440398); '
                           'amendment A1 (exposure model) made after the prior fit and before any evaluation '
                           'metric, recorded in the docstring'),
        'HEADLINE_VERDICT_PRIMARY': ev['PRIMARY_ALL_TEAM_GAMES']['verdict'],
        'starter_rule': 'most dropbacks (qb_dropback, `id`), ties: pass attempts then id; SPLIT if leader < 60%',
        'definitions': {
            'dropbacks': 'qb_dropback == 1 (pass attempts + sacks + scrambles), REG, two-point tries excluded',
            'pass_att': 'play_type pass, pass_attempt == 1, not a sack',
            'pass_rate': 'dropbacks / (dropbacks + designed runs)',
            'qb_rush': ('starter designed runs + scrambles; KNEELS EXCLUDED. So TB 2026 W5 Daniels counts 5 here '
                        '(5 scrambles) against 7 in the brief, which counted his 2 kneel-downs.'),
            'bias': 'forecast minus actual'},
        'incumbent_approximation': INCUMBENT_APPROXIMATION,
        'constants_provenance': {k: {'value': (v[0] if not isinstance(v[0], tuple) else list(v[0])),
                                     'provenance': v[1]} for k, v in CONSTANTS_PROVENANCE.items()},
        'priors_by_forecast_season': {str(k): v for k, v in priors.items()},
        'n_team_games': {'total': int(len(df)), 'QB_CHANGE': int((df['subset'] == 'QB_CHANGE').sum()),
                         'STABLE': int((df['subset'] == 'STABLE').sum()), 'SPLIT': n_split,
                         'QB_CHANGE_SPLIT': int((df['split'] & (df['subset'] == 'QB_CHANGE')).sum())},
        'evaluation': ev,
        'prospective_2026_descriptive': {
            'NOTE': 'DESCRIPTIVE ONLY (P8). Priors fitted on 2021-2025. Nothing tuned to any 2026 game.',
            'weeks': sorted(int(w) for w in d26['week'].unique()), 'by_subset': desc26,
            'TB_weeks_4_5': tb_rows, 'TB_weeks_4_5_detail': tb_detail},
    }
    OUT_EVAL.write_text(json.dumps(eval_art, indent=1, default=str) + '\n')
    w5_art = {'artifact': 'QBCTX_W5_2026_FORECASTS', 'label': LABEL, 'fingerprint': fp, 'cutoff': W5_CUTOFF,
              'NOTE': ('SHADOW forecasts. Intervals are 80% empirical out-of-sample error quantiles from 2024-2025 '
                       'for the same arm and subset; they do not condition on this club. Teammate shares are '
                       'REPORT ONLY and carry no injury filter.'),
              'clubs': w5}
    OUT_W5.write_text(json.dumps(w5_art, indent=1, default=str) + '\n')
    v = ev['PRIMARY_ALL_TEAM_GAMES']['verdict']
    print(json.dumps({'n': eval_art['n_team_games'], 'verdict': v}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
