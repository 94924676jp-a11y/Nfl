#!/usr/bin/env python3.12
"""SC-APPEAR-1 replayed THROUGH THE PRODUCTION ALLOCATOR AND VOLUME PATH on held-out 2025. SHADOW_ONLY.

    python3.12 nfl/research/appearance/sc_appear_1_production_path.py

WHY THIS EXISTS. sc_appear_1_forward.py scored SC-APPEAR-1 as a bare probability and, for its MAE half, multiplied
that probability by a PROXY volume (the prior-3-game mean). The owner requires the candidate to be judged through the
path production actually takes: the probability must enter proj_v1.allocate_opportunity at the line where the depth
appearance rate is read, be multiplied into the claim, be normalised against the club total, and come out as the
production expected opportunity (row[field]) and the production conditional volume (build()'s second pass).

WHERE THE APPEARANCE RATE IS CONSUMED (nfl/tools/proj_v1.py, unmodified):
    835   dr = depth[pos]['by_rank']                          the measured table for the position
    844   _deepest = deepest measured rank (fallback for ranks beyond the table)
    856   row = dr.get(f'rank_{rank}') or _deepest            rank = the player's allocator rank in his club group
    879   appear[i] = row.get('appearance_rate')              <-- THE CONSUMPTION POINT
    912   claims = [c * appear[i] ...]                        claim given he plays -> unconditional claim
    916-943 normalised over the club, r[field] = team_total * w_i / sum(w); r['p_plays'][field] = appear[i]
The rank ordering (lines 827-834) depends only on is_predicted_starter, _chart_rank, role_band and the RAW claim,
never on the appearance rate, so the rank each player occupies is the same in both arms.

HOW THE CANDIDATE IS INJECTED WITHOUT EDITING PRODUCTION. Nothing in proj_v1.py is changed or monkeypatched. The
allocator is called once per field with a club-total dict carrying only that field (every other field takes the
allocator's own CLUB_TOTAL_UNKNOWN branch and touches no row), and with a COPY of the production depth table in which
the row at rank r carries the candidate rate for the one player the allocator places at rank r. Ranks deeper than the
measured table are materialised as copies of the deepest row, which is numerically what line 856 already does. With the
candidate switched off the copied table equals production and the outputs are checked to be bit-identical to one
ordinary production call (HOOK_OFF_IDENTITY below). With it switched on, every row is checked after the call: the
allocator's own record must show the intended rank and the intended appearance rate at line 879, else the run is
refused with HOOK_NOT_ON_EXECUTION_PATH.

HARNESS. The per-player claims are built exactly as nfl/tools/forward_chain.project_week builds them (season priors
fitted through 2024, current-season shares and club volume from weeks STRICTLY BEFORE the scored week, the
pass-attempt starter proxy), with the production functions V.project_player and V.allocate_opportunity. Two allocation
universes:
  DRESSED (primary)      the club's dressed QB/RB/WR/TE for that game. This mirrors production, which removes the
                         officially inactive (NOT_PLAYING) before allocating. Dressed = present in nflverse snap counts.
  FORWARD_CHAIN_POOL     forward_chain's own universe: every player with a row for the club in an earlier 2025 week,
                         dressed or not. Sensitivity only; the candidate still applies only to dressed qualifiers.

FIT. Everything fitted is fitted on 2024 and earlier: depth table (depth_shares through=2024), group split
(group_shares through=2024), season priors (through 2024), SC-APPEAR-1 rates (2024 snap counts + panel, via
sc_appear_1_forward.rows_for -- identical rows to the forward test). No 2025 row enters a fit.

DECLARED BAR, verbatim from nfl/postgame/showdown_atl_no_2026W4/ATL_NO_SUCCESSOR_CANDIDATES.json, written before this
module ran: "forward-chained 2025 weeks: unconditional opportunity MAE and zero-opportunity calibration better than
current on held-out weeks by > 2 week-blocked SE, no regression for starters". Operationalised here, before the first
run, as: on QUALIFYING RB/WR/TE player-game-field units (the units the candidate changes) the week-blocked paired
improvement in absolute opportunity error has z > 2 AND the improvement in zero-opportunity Brier has z > 2; on
rank-1 RB/WR/TE units neither is worse by more than 2 week-blocked SE. Structural requirements: club totals conserved
in both arms, non-qualifying appearance probabilities exactly unchanged, hook-off identity exact.

THIS IS RETROSPECTIVE OUT-OF-SAMPLE, NOT PROSPECTIVE. 2025 was not used to fit, but it has now been looked at twice
(forward test and this replay). It is not a sealed holdout for any variant selected after reading these numbers.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import math
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import forward_chain as FC  # noqa: E402
from nfl.tools import player_prior as PP  # noqa: E402
from nfl.tools import proj_v1 as V  # noqa: E402

_F1_PATH = pathlib.Path(__file__).resolve().parent / 'sc_appear_1_forward.py'
_spec = importlib.util.spec_from_file_location('sc_appear_1_forward', _F1_PATH)
F1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F1)

OUT = _REPO / 'nfl/research/appearance/SC_APPEAR_1_PRODUCTION_PATH.json'
FORWARD_TEST = _REPO / 'nfl/research/appearance/SC_APPEAR_1_FORWARD_TEST.json'
PROJ_V1_FILE = _REPO / 'nfl/tools/proj_v1.py'

FIT_SEASON = 2024
TEST_SEASON = 2025
MIN_WEEK = 4
N_PRIOR = 3
SKILL = ('QB', 'RB', 'WR', 'TE')
CAND_FIELDS = (('RB', 'carries'), ('RB', 'targets'), ('WR', 'targets'), ('TE', 'targets'))
ALLOC = (('targets', 'proj_targets'), ('carries', 'proj_rush_attempts'), ('pass_attempts', 'proj_pass_attempts'))
SCORE_FIELDS = {'QB': ('pass_attempts',), 'RB': ('carries', 'targets'), 'WR': ('targets',), 'TE': ('targets',)}
TABLE_FIELD = dict(V.DEPTH_TABLE_FIELD)
EPS = 1e-4


class SCAppearProductionPathError(RuntimeError):
    """Named refusal. `code` is the machine-readable reason."""

    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


# ----------------------------------------------------------------------------------------------- fit (<= 2024)
def fit(panel, pos_of, dressed_fit, through=FIT_SEASON):
    """Every fitted object, from seasons <= `through`. Refuses a fit season that is not held out from 2025."""
    if through >= TEST_SEASON:
        raise SCAppearProductionPathError('FIT_SEASON_NOT_HELD_OUT', f'through={through} >= test season {TEST_SEASON}')
    if not panel or not panel.get('players') or not panel.get('teams'):
        raise SCAppearProductionPathError('EMPTY_PANEL')
    if not dressed_fit:
        raise SCAppearProductionPathError('EMPTY_DRESSED_FIT')
    depth = V.depth_shares(panel, pos_of, through=through)
    groups = V.group_shares(panel, pos_of, through=through)
    try:
        tr = F1.rows_for(panel, pos_of, through, dressed_fit)
    except F1.AppearError as e:
        raise SCAppearProductionPathError('NO_FIT_ROWS', str(e)) from e
    rates, n = {}, {}
    for p_, f in CAND_FIELDS:
        d = tr[(tr.pos == p_) & (tr.field == f) & tr.prior3_all]
        if not len(d):
            raise SCAppearProductionPathError('NO_FIT_ROWS', f'{p_}_{f}')
        rates[(p_, f)] = float(d.y.mean())
        n[(p_, f)] = int(len(d))
    if max(int(s) for s in tr.season.unique()) > through:
        raise SCAppearProductionPathError('FIT_ROWS_AFTER_CUTOFF')
    return {'depth': depth, 'groups': groups, 'rates': rates, 'n_fit_rows': n, 'through': through}


# ------------------------------------------------------------------------------------- held-out season context
def _snap_positions(season):
    prov = json.loads((F1.HIST / 'PROVENANCE.json').read_text())
    f = {x['kind']: _REPO / x['file'] for x in prov['files']}
    cw = pd.read_csv(f['players_crosswalk'])
    s = pd.read_csv(f[f'snap_counts_{season}'])
    s = s[s.game_type == 'REG'].merge(cw[['pfr_id', 'gsis_id']], left_on='pfr_player_id', right_on='pfr_id')
    return {g: grp.position.mode().iloc[0] for g, grp in s.groupby('gsis_id')}


def context(panel, pos_of, season, dressed, snap_pos=None):
    """Position map, season priors (fitted through season-1), club game weeks. Pregame objects only."""
    if not dressed:
        raise SCAppearProductionPathError('EMPTY_DRESSED_TEST')
    snap_pos = snap_pos or {}
    pm, _inferred = FC.positions_for_chain(panel, pos_of)
    posmap, src = {}, {}
    ids = set(panel['players']) | {g for v in dressed.values() for g in v}
    for g in ids:
        if pos_of.get(g):
            posmap[g], src[g] = pos_of.get(g), 'ROSTER'
        elif snap_pos.get(g) in SKILL:
            posmap[g], src[g] = snap_pos[g], 'SNAP_COUNT_LISTED'
        elif pm.get((g, season)):
            posmap[g], src[g] = pm[(g, season)], 'USAGE_INFERRED'
    P = panel['players']
    team_weeks = collections.defaultdict(set)   # sc_appear_1_forward's definition of a club game week
    for g, ss in P.items():
        for w, d in (ss.get(str(season)) or {}).items():
            if d.get('team'):
                team_weeks[d['team']].add(int(w))
    club_games = collections.defaultdict(set)    # weeks the club dressed anybody (snap counts)
    for (team, wk) in dressed:
        club_games[team].add(wk)
    gl = sorted({g for v in dressed.values() for g in v if posmap.get(g) in SKILL}
                | {g for g, ss in P.items() if posmap.get(g) in SKILL and str(season) in ss})
    priors = FC.season_priors(panel, posmap, season, gl)
    return {'season': season, 'panel': panel, 'pos_of': pos_of, 'posmap': posmap, 'pos_src': src,
            'dressed': dressed, 'team_weeks': team_weeks, 'club_games': club_games, 'priors': priors}


def prior3(ctx, gsis, club, week, field):
    """Count of the club's previous N_PRIOR games in which the player recorded >= 1 of `field` (None if < 3 games)."""
    prev = sorted(w for w in ctx['team_weeks'].get(club, ()) if w < week)[-N_PRIOR:]
    if len(prev) < N_PRIOR:
        return None
    ss = (ctx['panel']['players'].get(gsis) or {}).get(str(ctx['season'])) or {}
    return sum(1 for w in prev if ((ss.get(str(w)) or {}).get(field) or 0) > 0)


def starter_proxy(ctx, week):
    """forward_chain.project_week's QB starter proxy (its lines 352-382), pregame only."""
    panel, season, posmap = ctx['panel'], ctx['season'], ctx['posmap']
    qb_att = collections.defaultdict(dict)
    for gsis, seasons in panel['players'].items():
        if posmap.get(gsis) != 'QB':
            continue
        cur = seasons.get(str(season)) or {}
        prv = seasons.get(str(season - 1)) or {}
        for wk, w in cur.items():
            if int(wk) < week and w.get('team'):
                qb_att[w['team']][gsis] = qb_att[w['team']].get(gsis, 0.0) + (w.get('pass_attempts') or 0)
        if not any(int(k) < week for k in cur):
            for wk, w in prv.items():
                if w.get('team'):
                    qb_att[w['team']][gsis] = qb_att[w['team']].get(gsis, 0.0) + 0.25 * (w.get('pass_attempts') or 0)
    return {club: max(d, key=lambda g: d[g]) for club, d in qb_att.items() if d}


def pool_for(ctx, club, week, universe):
    posmap = ctx['posmap']
    if universe == 'DRESSED':
        return sorted(g for g in ctx['dressed'].get((club, week), ()) if posmap.get(g) in SKILL)
    if universe == 'FORWARD_CHAIN_POOL':
        out = []
        for gsis, seasons in ctx['panel']['players'].items():
            if posmap.get(gsis) not in SKILL:
                continue
            ss = seasons.get(str(ctx['season'])) or {}
            last = None
            for wk in sorted((k for k in ss if int(k) < week), key=int):
                if ss[wk].get('team'):
                    last = ss[wk]['team']
            if last == club:
                out.append(gsis)
        return sorted(out)
    raise SCAppearProductionPathError('UNKNOWN_UNIVERSE', universe)


def club_rows(ctx, club, week, pool, starter, depth):
    """Claims for every pool member via the production V.project_player, built as forward_chain does."""
    tv = FC.club_volume_before(ctx['panel'], club, ctx['season'], week, 4.0)
    if not tv:
        return None, []
    rows = []
    for gsis in pool:
        pos = ctx['posmap'][gsis]
        band, prior = ctx['priors'].get(gsis, (None, None))
        prior_used = prior or {'measures': {}, 'tier': 'PRIOR_UNAVAILABLE', 'effective_obs_at_role': 0.0}
        band_used = band or 'FRINGE'
        cur, cur_n = FC.shares_before(ctx['panel'], gsis, club, pos, ctx['season'], week)
        is_start = (starter.get(club) == gsis) if pos == 'QB' else None
        r = V.project_player(ctx['panel'], gsis, pos, band_used, club, tv, {}, cur, cur_n, prior_used,
                             is_predicted_starter=is_start, depth=depth)
        r.update({'gsis': gsis, 'team': club, 'position': pos, 'role_band': band_used,
                  'is_predicted_starter': is_start, '_dk': gsis})
        rows.append(r)
    return tv, rows


# ----------------------------------------------------------------------------------------- the hook (no edit)
def candidate_rate_fn(rates, qualifies):
    """rate_fn(row, field) -> SC-APPEAR-1 rate for a dressed qualifier in a candidate field, else None (= production)."""
    def fn(row, field):
        pos = row.get('position')
        if (pos, field) not in rates:
            return None
        return rates[(pos, field)] if qualifies.get((row.get('_dk'), field)) else None
    return fn


def allocate_with_hook(crows, tv, depth, groups, rate_fn=None, force=None):
    """Run the PRODUCTION allocator with the candidate's appearance rate placed at the line-879 read.

    rate_fn None means hook off: the depth table passed is a copy equal to production and the outputs must equal one
    production call bit for bit. Mutates `crows` exactly as V.allocate_opportunity does.
    """
    probe = copy.deepcopy(crows)
    V.allocate_opportunity(probe, tv, depth, groups, force_appearance_for=force)
    acct = {}
    for field, teamfld in ALLOC:
        if tv.get(teamfld) is None:
            acct[field] = {'state': 'CLUB_TOTAL_UNKNOWN'}
            continue
        dfield = dict(depth)
        intended = {}
        for pos in SKILL:
            base = (depth.get(pos) or {}).get('by_rank') or {}
            if not base:
                continue
            br = {k: dict(v) for k, v in base.items()}
            deepest = base[f'rank_{max(int(k.split("_")[1]) for k in base)}']
            for i, r in enumerate(crows):
                if r['position'] != pos:
                    continue
                a = (probe[i].get('allocation') or {}).get(field) or {}
                rk = a.get('depth_rank_in_group')
                if rk is None:
                    continue
                key = f'rank_{rk}'
                if key not in br:
                    br[key] = dict(deepest)
                rate = rate_fn(r, field) if rate_fn is not None else None
                if rate is not None:
                    br[key]['appearance_rate'] = rate
                intended[i] = (rk, br[key]['appearance_rate'], a.get('rank_beyond_measured_table'))
            dfield[pos] = {**depth[pos], 'by_rank': br}
        acct[field] = V.allocate_opportunity(crows, {teamfld: tv[teamfld]}, dfield, groups,
                                             force_appearance_for=force)[field]
        for i, (rk, ar, beyond) in intended.items():
            a = crows[i]['allocation'][field]
            if a.get('depth_rank_in_group') != rk or a.get('appearance_rate_measured') != ar \
                    or crows[i]['p_plays'][field] != ar:
                raise SCAppearProductionPathError(
                    'HOOK_NOT_ON_EXECUTION_PATH',
                    f'{crows[i].get("_dk")} {field}: rank {a.get("depth_rank_in_group")} vs {rk}, '
                    f'appear {a.get("appearance_rate_measured")} vs {ar}')
            a['rank_beyond_measured_table'] = beyond
    return acct


def conditional_pass(crows, tv, depth, groups, rate_fn=None, hooked=False):
    """proj_v1.build()'s second pass (its lines 1321-1338): one allocation per target with his P(plays) forced to 1."""
    out = {}
    for target in crows:
        work = [{'position': r['position'], 'role_band': r.get('role_band'),
                 'is_predicted_starter': r.get('is_predicted_starter'), 'efficiency': r.get('efficiency'),
                 'rz_intensity': r.get('rz_intensity'), '_claims': dict(r.get('_claims') or {}), '_dk': r['_dk']}
                for r in crows]
        if hooked:
            allocate_with_hook(work, tv, depth, groups, rate_fn=rate_fn, force=target['_dk'])
        else:
            V.allocate_opportunity(work, tv, depth, groups, force_appearance_for=target['_dk'])
        w = next(x for x in work if x['_dk'] == target['_dk'])
        out[target['_dk']] = {f: w.get(f) for f, _ in ALLOC}
    return out


def _snapshot(rows):
    return [{f: (r.get(f), (r.get('p_plays') or {}).get(f), json.dumps((r.get('allocation') or {}).get(f), sort_keys=True))
             for f, _ in ALLOC} for r in rows]


# ------------------------------------------------------------------------------------------------- the replay
def replay(ctx, fitted, universe='DRESSED', weeks=None, clubs=None, identity_check=True):
    """One unit per scored (player, week, field). Raises on an empty result."""
    depth, groups, rates = fitted['depth'], fitted['groups'], fitted['rates']
    season, panel = ctx['season'], ctx['panel']
    all_weeks = sorted({w for (_t, w) in ctx['dressed']})
    weeks = [w for w in (weeks or all_weeks) if w >= MIN_WEEK]
    units, conservation, identity = [], [], {'club_weeks': 0, 'n_values': 0,
                                     'comparison': 'EXACT == on every r[field], p_plays[field] and allocation record'}
    for week in weeks:
        starter = starter_proxy(ctx, week)
        teams = sorted({t for (t, w) in ctx['dressed'] if w == week})
        for club in teams:
            if clubs and club not in clubs:
                continue
            prev = sorted(w for w in ctx['team_weeks'].get(club, ()) if w < week)
            if len(prev) < N_PRIOR:
                continue
            pool = pool_for(ctx, club, week, universe)
            if not pool:
                continue
            tv, crows = club_rows(ctx, club, week, pool, starter, depth)
            if not crows:
                continue
            dressed_now = ctx['dressed'].get((club, week), set())
            qual, p3 = {}, {}
            for r in crows:
                g = r['_dk']
                for f, _ in ALLOC:
                    c = prior3(ctx, g, club, week, f)
                    p3[(g, f)] = c
                    qual[(g, f)] = bool((r['position'], f) in rates and g in dressed_now and c == N_PRIOR)
            fn = candidate_rate_fn(rates, qual)
            cur = copy.deepcopy(crows)
            V.allocate_opportunity(cur, tv, depth, groups)
            cand = copy.deepcopy(crows)
            allocate_with_hook(cand, tv, depth, groups, rate_fn=fn)
            if identity_check:
                off = copy.deepcopy(crows)
                allocate_with_hook(off, tv, depth, groups, rate_fn=None)
                a, b = _snapshot(cur), _snapshot(off)
                if a != b:
                    raise SCAppearProductionPathError('HOOK_OFF_NOT_IDENTICAL', f'{club} {season} wk{week}')
                identity['club_weeks'] += 1
                identity['n_values'] += sum(len(x) for x in a)
            ccur = conditional_pass(crows, tv, depth, groups)
            ccan = conditional_pass(crows, tv, depth, groups, rate_fn=fn, hooked=True)
            for f, teamfld in ALLOC:
                tt = tv.get(teamfld)
                if tt is None:
                    continue
                conservation.append({'week': week, 'club': club, 'field': f, 'club_total': tt,
                                     'sum_current': sum(r.get(f) or 0.0 for r in cur),
                                     'sum_candidate': sum(r.get(f) or 0.0 for r in cand),
                                     'sum_p_current': sum((r.get('p_plays') or {}).get(f, 0.0) for r in cur),
                                     'sum_p_candidate': sum((r.get('p_plays') or {}).get(f, 0.0) for r in cand)})
            prev_game = max((w for w in ctx['club_games'].get(club, ()) if w < week), default=None)
            for rc, rn in zip(cur, cand):
                g, pos = rc['_dk'], rc['position']
                if ctx['pos_src'].get(g) == 'USAGE_INFERRED' or g not in dressed_now:
                    continue   # never score a guessed position; score only dressed players
                ss = (panel['players'].get(g) or {}).get(str(season)) or {}
                now = ss.get(str(week)) or {}
                earlier = [d for w, d in ss.items() if int(w) < week]
                had_opp_before = any(((d.get('targets') or 0) + (d.get('carries') or 0) + (d.get('pass_attempts') or 0)) > 0
                                     for d in earlier)
                had_opp_for_club = any(((d.get('targets') or 0) + (d.get('carries') or 0) + (d.get('pass_attempts') or 0)) > 0
                                       and d.get('team') == club for d in earlier)
                missed_prev = prev_game is not None and g not in ctx['dressed'].get((club, prev_game), set())
                tf = TABLE_FIELD[pos]
                rank_table = ((rc.get('allocation') or {}).get(tf) or {}).get('depth_rank_in_group')
                for f in SCORE_FIELDS[pos]:
                    units.append({
                        'season': season, 'week': week, 'club': club, 'gsis': g, 'pos': pos, 'field': f,
                        'pos_source': ctx['pos_src'].get(g),
                        'rank_table': rank_table,
                        'rank_field': ((rc.get('allocation') or {}).get(f) or {}).get('depth_rank_in_group'),
                        'prior3_count': p3[(g, f)], 'qualifies': qual[(g, f)],
                        'elevation_proxy': bool(missed_prev and not had_opp_before),
                        'returning_proxy': bool(missed_prev and had_opp_for_club),
                        'p_cur': float((rc.get('p_plays') or {}).get(f, 1.0)),
                        'p_cand': float((rn.get('p_plays') or {}).get(f, 1.0)),
                        'e_cur': float(rc.get(f) or 0.0), 'e_cand': float(rn.get(f) or 0.0),
                        'c_cur': float(ccur[g].get(f) or 0.0), 'c_cand': float(ccan[g].get(f) or 0.0),
                        'actual': float(now.get(f) or 0.0)})
    if not units:
        raise SCAppearProductionPathError('NO_SCORED_UNITS', universe)
    df = pd.DataFrame(units)
    if df.actual.isna().any():
        raise SCAppearProductionPathError('ACTUAL_MISSING')
    return df, pd.DataFrame(conservation), identity


# ------------------------------------------------------------------------------------------------- statistics
def _blocked(values, blocks):
    s = pd.Series(np.asarray(values, float)).groupby(np.asarray(blocks)).mean()
    n = len(s)
    se = float(s.std(ddof=1) / math.sqrt(n)) if n > 1 else float('nan')
    m = float(s.mean())
    return {'mean_of_block_means': round(m, 5), 'se': round(se, 5), 'n_blocks': n,
            'z': (round(m / se, 2) if se and se > 0 else None)}


def _pair(cur_loss, cand_loss, d):
    """Improvement = current loss - candidate loss (positive = candidate better), week- and club-blocked."""
    diff = np.asarray(cur_loss) - np.asarray(cand_loss)
    return {'week_blocked': _blocked(diff, d.week.values), 'club_blocked': _blocked(diff, d.club.values)}


def cohort_metrics(d):
    if not len(d):
        return {'n_units': 0, 'state': 'EMPTY_COHORT'}
    y0 = (d.actual.values == 0).astype(float)
    pz_cur, pz_cand = 1 - d.p_cur.values, 1 - d.p_cand.values
    out = {'n_units': int(len(d)), 'n_players': int(d.gsis.nunique()), 'n_weeks': int(d.week.nunique()),
           'mean_actual': round(float(d.actual.mean()), 4)}
    for arm, e, pz, c in (('current', d.e_cur.values, pz_cur, d.c_cur.values),
                          ('candidate', d.e_cand.values, pz_cand, d.c_cand.values)):
        err = e - d.actual.values
        out[arm] = {
            'mean_expected_opportunity': round(float(e.mean()), 4),
            'signed_error_pred_minus_actual': {'pooled': round(float(err.mean()), 4), **_blocked(err, d.week.values)},
            'abs_error': {'pooled': round(float(np.abs(err).mean()), 4), **_blocked(np.abs(err), d.week.values)},
            'predicted_P0': round(float(pz.mean()), 4),
            'zero_mass_error_pred_minus_obs': {'pooled': round(float(pz.mean() - y0.mean()), 4),
                                               **_blocked(pz - y0, d.week.values)},
            'zero_brier': round(float(((np.clip(pz, EPS, 1 - EPS) - y0) ** 2).mean()), 5),
            'conditional_volume_abs_error_if_dressed': round(float(np.abs(c - d.actual.values).mean()), 4)}
    out['observed_zero_share'] = round(float(y0.mean()), 4)
    out['improvement_abs_error'] = _pair(np.abs(d.e_cur - d.actual), np.abs(d.e_cand - d.actual), d)
    out['improvement_zero_brier'] = _pair((np.clip(pz_cur, EPS, 1 - EPS) - y0) ** 2,
                                          (np.clip(pz_cand, EPS, 1 - EPS) - y0) ** 2, d)
    out['improvement_conditional_abs_error'] = _pair(np.abs(d.c_cur - d.actual), np.abs(d.c_cand - d.actual), d)
    out['change_mean_expected_opportunity_cand_minus_cur'] = _blocked(d.e_cand - d.e_cur, d.week.values)
    out['change_mean_p_plays_cand_minus_cur'] = round(float((d.p_cand - d.p_cur).mean()), 5)
    return out


def concordance(df):
    """Pairwise concordance of expected opportunity with actual inside club-week-position, on the table field."""
    rows = []
    for (wk, club, pos), g in df[df.field == df.pos.map(TABLE_FIELD)].groupby(['week', 'club', 'pos']):
        a = g.actual.values
        for arm, col in (('cur', 'e_cur'), ('cand', 'e_cand')):
            p = g[col].values
            num = den = 0.0
            for i in range(len(a)):
                for j in range(i + 1, len(a)):
                    if a[i] == a[j]:
                        continue
                    den += 1
                    s = (p[i] - p[j]) * (a[i] - a[j])
                    num += 1.0 if s > 0 else (0.5 if s == 0 else 0.0)
            rows.append({'week': wk, 'club': club, 'pos': pos, 'arm': arm, 'num': num, 'den': den})
    r = pd.DataFrame(rows)
    out = {}
    for pos in ('ALL',) + SKILL:
        x = r if pos == 'ALL' else r[r.pos == pos]
        if not len(x) or not x.den.sum():
            continue
        wk = x.groupby(['week', 'arm'])[['num', 'den']].sum().reset_index()
        wk['c'] = wk.num / wk.den.replace(0, np.nan)
        pv = wk.pivot(index='week', columns='arm', values='c').dropna()
        out[pos] = {'concordance_current': round(float(x[x.arm == 'cur'].num.sum() / x[x.arm == 'cur'].den.sum()), 4),
                    'concordance_candidate': round(float(x[x.arm == 'cand'].num.sum() / x[x.arm == 'cand'].den.sum()), 4),
                    'n_pairs': int(x[x.arm == 'cur'].den.sum()),
                    'improvement_cand_minus_cur_week_blocked': _blocked(pv['cand'] - pv['cur'], pv.index.values)}
    return out


def reliability(d, col):
    bins = np.minimum((d[col].values * 10).astype(int), 9)
    y = (d.actual.values > 0).astype(float)
    out, ece = [], 0.0
    for b in range(10):
        m = bins == b
        if not m.any():
            continue
        pm, om = float(d[col].values[m].mean()), float(y[m].mean())
        ece += m.sum() / len(d) * abs(pm - om)
        out.append({'bin': f'[{b / 10:.1f},{(b + 1) / 10:.1f})', 'n': int(m.sum()),
                    'mean_predicted_P_ge1': round(pm, 4), 'observed_P_ge1': round(om, 4)})
    return {'bins': out, 'expected_calibration_error': round(ece, 4)}


def suppression(df):
    d = df[df.pos.isin(['RB', 'WR', 'TE'])].copy()
    d['history'] = np.where(d.prior3_count == N_PRIOR, 'ALL_3_PRIOR_GAMES',
                            np.where(d.prior3_count > 0, 'SOME_1_OR_2', 'NONE_0_OF_3'))
    d['rank_group'] = np.where(d.rank_table == 1, 'RANK_1', 'RANK_2_PLUS')
    out = {}
    for (h, rg), g in d.groupby(['history', 'rank_group']):
        dp = g.p_cand - g.p_cur
        y = (g.actual > 0).astype(float)
        out[f'{h}|{rg}'] = {
            'n_units': int(len(g)), 'n_qualifying': int(g.qualifies.sum()),
            'observed_P_ge1': round(float(y.mean()), 4),
            'mean_p_current': round(float(g.p_cur.mean()), 4), 'mean_p_candidate': round(float(g.p_cand.mean()), 4),
            'suppression_gap_obs_minus_pred_current': round(float(y.mean() - g.p_cur.mean()), 4),
            'suppression_gap_obs_minus_pred_candidate': round(float(y.mean() - g.p_cand.mean()), 4),
            'delta_p': {'mean': round(float(dp.mean()), 5), 'max_abs': round(float(dp.abs().max()), 6),
                        'share_raised': round(float((dp > 1e-12).mean()), 4),
                        'share_lowered': round(float((dp < -1e-12).mean()), 4),
                        'share_unchanged': round(float((dp.abs() <= 1e-12).mean()), 4)},
            'mean_expected_opportunity_current': round(float(g.e_cur.mean()), 4),
            'mean_expected_opportunity_candidate': round(float(g.e_cand.mean()), 4),
            'mean_actual_opportunity': round(float(g.actual.mean()), 4)}
    nq = d[~d.qualifies]
    out['NON_QUALIFYING_ALL'] = {'n_units': int(len(nq)),
                                 'max_abs_delta_p': float((nq.p_cand - nq.p_cur).abs().max()) if len(nq) else None,
                                 'mean_delta_expected_opportunity': round(float((nq.e_cand - nq.e_cur).mean()), 5),
                                 'NOTE': ('appearance probability is untouched for every non-qualifier; their expected '
                                          'opportunity still moves because the allocator renormalises the club total')}
    return out


def summarise(df, cons, ident, fitted, label):
    rbwrte = df.pos.isin(['RB', 'WR', 'TE'])
    cohorts = {
        'ALL_RB_WR_TE': rbwrte,
        'QUALIFYING_RB_WR_TE': rbwrte & df.qualifies,
        'NON_QUALIFYING_RB_WR_TE': rbwrte & ~df.qualifies,
        'RANK1_RB_WR_TE': rbwrte & (df.rank_table == 1),
        'RB2_carries': (df.pos == 'RB') & (df.rank_table == 2) & (df.field == 'carries'),
        'RB2_targets': (df.pos == 'RB') & (df.rank_table == 2) & (df.field == 'targets'),
        'WR3_WR4_targets': (df.pos == 'WR') & df.rank_table.isin([3, 4]),
        'TE2_TE3_targets': (df.pos == 'TE') & df.rank_table.isin([2, 3]),
        'BACKUP_QB_pass_attempts': (df.pos == 'QB') & (df.rank_table >= 2),
        'RANK1_QB_pass_attempts': (df.pos == 'QB') & (df.rank_table == 1),
        'ELEVATION_PROXY_RB_WR_TE': rbwrte & df.elevation_proxy,
        'RETURNING_FROM_ABSENCE_PROXY_RB_WR_TE': rbwrte & df.returning_proxy,
    }
    res = {k: cohort_metrics(df[m]) for k, m in cohorts.items()}
    for k in ('RB2_carries', 'RB2_targets', 'WR3_WR4_targets', 'TE2_TE3_targets', 'ELEVATION_PROXY_RB_WR_TE',
              'RETURNING_FROM_ABSENCE_PROXY_RB_WR_TE'):
        if res[k].get('n_units'):
            res[k]['n_qualifying_units'] = int(df[cohorts[k]].qualifies.sum())
    q, r1 = res['QUALIFYING_RB_WR_TE'], res['RANK1_RB_WR_TE']
    qa, qb = q['improvement_abs_error']['week_blocked'], q['improvement_zero_brier']['week_blocked']
    ra, rb = r1['improvement_abs_error']['week_blocked'], r1['improvement_zero_brier']['week_blocked']
    cons_dev_cur = float((cons.sum_current - cons.club_total).abs().max())
    cons_dev_cand = float((cons.sum_candidate - cons.club_total).abs().max())
    nq_dp = float((df[~df.qualifies].p_cand - df[~df.qualifies].p_cur).abs().max())
    bar = {
        'qualifying_abs_error_improvement_z_gt_2': bool(qa['z'] is not None and qa['z'] > 2),
        'qualifying_zero_brier_improvement_z_gt_2': bool(qb['z'] is not None and qb['z'] > 2),
        'rank1_abs_error_not_worse_by_2se': bool(ra['mean_of_block_means'] >= -2 * ra['se']),
        'rank1_zero_brier_not_worse_by_2se': bool(rb['mean_of_block_means'] >= -2 * rb['se']),
        'club_totals_conserved_both_arms': bool(cons_dev_cur < 1e-9 and cons_dev_cand < 1e-9),
        'non_qualifying_p_exactly_unchanged': bool(nq_dp == 0.0),
        'hook_off_identity_exact': (bool(ident['club_weeks'] > 0) if not ident.get('skipped')
                                    else 'NOT_CHECKED_IN_THIS_UNIVERSE')}
    return {
        'universe': label,
        'n_units': int(len(df)), 'n_weeks': int(df.week.nunique()), 'weeks': sorted(int(w) for w in df.week.unique()),
        'n_club_weeks': int(df.groupby(['week', 'club']).ngroups),
        'cohorts': res,
        'suppression_defect': suppression(df),
        'role_ranking_concordance': concordance(df),
        'backup_calibration_rank2plus_RB_WR_TE': {
            'current': reliability(df[rbwrte & (df.rank_table >= 2)], 'p_cur'),
            'candidate': reliability(df[rbwrte & (df.rank_table >= 2)], 'p_cand')},
        'backup_calibration_backup_QB_current_only': reliability(df[(df.pos == 'QB') & (df.rank_table >= 2)], 'p_cur'),
        'conservation': {'n_club_week_fields': int(len(cons)),
                         'max_abs_sum_minus_club_total_current': cons_dev_cur,
                         'max_abs_sum_minus_club_total_candidate': cons_dev_cand,
                         'mean_sum_p_plays_current': round(float(cons.sum_p_current.mean()), 4),
                         'mean_sum_p_plays_candidate': round(float(cons.sum_p_candidate.mean()), 4),
                         'NOTE': ('the allocator normalises weights across the club, so expected opportunity sums to '
                                  'the club total in both arms; the sum of P(plays) is NOT conserved and is reported')},
        'hook_off_identity': ident,
        'DECLARED_BAR_CHECKS': bar,
        'DECLARED_BAR': 'PASS' if all(v is True for v in bar.values() if not isinstance(v, str)) else 'FAIL'}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def run():
    sha_before = _sha(PROJ_V1_FILE)
    po = PP.load_panel()
    if po.state.value != 'PASS':
        raise SCAppearProductionPathError('PANEL', str(po.state))
    panel, pos_of = po.value, PP.position_index()
    fitted = fit(panel, pos_of, F1._dressed(FIT_SEASON))
    recorded = json.loads(FORWARD_TEST.read_text())['sc_appear_1_rates_fit_2024'] if FORWARD_TEST.exists() else {}
    rates_match = {f'{p}_{f}': (round(v, 4) == recorded.get(f'{p}_{f}')) for (p, f), v in fitted['rates'].items()}
    ctx = context(panel, pos_of, TEST_SEASON, F1._dressed(TEST_SEASON), snap_pos=_snap_positions(TEST_SEASON))
    depth_before = json.dumps(fitted['depth'], sort_keys=True)
    df, cons, ident = replay(ctx, fitted, 'DRESSED')
    df2, cons2, ident2 = replay(ctx, fitted, 'FORWARD_CHAIN_POOL', identity_check=False)
    ident2 = {**ident2, 'skipped': True, 'NOTE': 'identity checked in the primary universe; skipped here for run time'}
    if json.dumps(fitted['depth'], sort_keys=True) != depth_before:
        raise SCAppearProductionPathError('PRODUCTION_DEPTH_TABLE_MUTATED')
    sha_after = _sha(PROJ_V1_FILE)
    primary = summarise(df, cons, ident, fitted, 'DRESSED')
    sens = summarise(df2, cons2, ident2, fitted, 'FORWARD_CHAIN_POOL')
    doc = {
        'ARTIFACT': 'SC_APPEAR_1_PRODUCTION_PATH', 'STATUS': 'SHADOW_ONLY', 'candidate': 'SC-APPEAR-1',
        'written_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'EVIDENCE_CLASS': ('RETROSPECTIVE OUT-OF-SAMPLE: fitted on <= 2024, replayed on 2025. Not prospective, and 2025 '
                           'has now been read twice, so it is not a sealed holdout for any variant chosen after this.'),
        'production_path': {
            'file': 'nfl/tools/proj_v1.py', 'sha256_before': sha_before, 'sha256_after': sha_after,
            'production_file_edited': sha_before != sha_after,
            'appearance_rate_consumed_at': 'proj_v1.allocate_opportunity line 879: appear[i] = row.get("appearance_rate")',
            'row_selected_at': 'line 856: row = dr.get(f"rank_{rank}") or _deepest (rank = allocator rank in club group)',
            'rank_order_at': 'lines 827-834: is_predicted_starter, _chart_rank, role_band, raw claim (no appearance term)',
            'enters_expected_opportunity_at': 'line 912 claims *= appear; lines 916-943 normalised; r[field] = team_total * w_i / sum w',
            'zero_mass': ('1 - p_plays[field] (line 942). The claim is a share GIVEN he plays, so P(0 opportunities) is '
                          'carried by P(plays) alone; no consumer in nfl/sim reads p_plays (grep), so this is the '
                          'projection-layer zero mass, not a simulator one'),
            'table_built_at': 'proj_v1.depth_shares line 1467: appearance_rate = share of club-weeks with >= r position players holding any panel row',
            'conditional_volume_at': 'proj_v1.build lines 1321-1338: second allocation per target with force_appearance_for',
            'harness': ('nfl/tools/forward_chain.project_week (lines 306-424) calls V.project_player (406) and '
                        'V.allocate_opportunity (416): it is the production allocator. Claims here are built the same '
                        'way; the allocation universe is the dressed roster (production post-inactives) with '
                        'forward_chain\'s own pool as a sensitivity'),
            'hook': ('no edit and no monkeypatch: per-field allocator calls with a copied depth table whose rank-r row '
                     'carries the candidate rate for the allocator\'s rank-r player; verified after every call')},
        'fit': {'through': fitted['through'],
                'sc_appear_1_rates': {f'{p}_{f}': round(v, 6) for (p, f), v in fitted['rates'].items()},
                'n_fit_units': {f'{p}_{f}': v for (p, f), v in fitted['n_fit_rows'].items()},
                'rates_match_forward_test_artifact': rates_match,
                'depth_table_through_2024_appearance_rates': {
                    p: {k: v['appearance_rate'] for k, v in fitted['depth'][p]['by_rank'].items()} for p in SKILL},
                'depth_table_sha16': hashlib.sha256(depth_before.encode()).hexdigest()[:16]},
        'definitions': {
            'unit': 'one dressed player x scored week x field (QB pass_attempts; RB carries and targets; WR/TE targets)',
            'dressed': 'present in nflverse 2025 REG snap counts for that club-game (offense or special teams)',
            'qualifies': 'dressed AND >= 1 of the field in each of the club\'s previous 3 games (sc_appear_1_forward definition)',
            'actual': 'panel count for that week; a dressed player with no panel row recorded 0 (the panel is built from play-by-play)',
            'expected_opportunity': 'production unconditional r[field] from allocate_opportunity',
            'rank': 'the allocator\'s own depth_rank_in_group on the position\'s table field (RB carries, WR/TE targets, QB pass attempts)',
            'week_blocked_se': 'SE of the 15 per-week means; club-blocked SE also given for paired differences',
            'elevation_proxy': ('PROXY, practice-squad elevations are NOT identifiable for 2025 in the committed data (no '
                                '2025 weekly rosters, transactions or game-day status). Proxy: dressed this week, not '
                                'dressed in the club\'s previous game, and no target/carry/pass attempt anywhere earlier in 2025'),
            'returning_from_absence_proxy': ('dressed this week, not dressed in the club\'s previous game, and >= 1 '
                                             'opportunity for this club earlier in 2025. Cause of absence (injury, '
                                             'suspension, healthy scratch) is not identified')},
        'PRIMARY_DRESSED_UNIVERSE': primary,
        'SENSITIVITY_FORWARD_CHAIN_POOL': {k: sens[k] for k in ('universe', 'n_units', 'n_club_weeks', 'cohorts',
                                                                 'conservation', 'DECLARED_BAR_CHECKS', 'DECLARED_BAR')},
    }
    doc['COHORT_TABLE_COMPACT'] = compact(primary)
    doc['LIMITATIONS'] = LIMITATIONS
    doc['AUDIT_LADDER'] = {
        'reached': 'ADVERSARIAL_TESTED',
        'IMPLEMENTED': 'yes -- research module, production untouched',
        'ON_EXECUTION_PATH': ('yes -- the candidate rate is the value the production allocator reads at proj_v1 line 879, '
                              'checked after every call (HOOK_NOT_ON_EXECUTION_PATH otherwise)'),
        'SUCCESS_TESTED': 'yes -- nfl/tests/test_sc_appear_1_production_path.py (hook-off identity, hook-on reaches the read)',
        'REFUSAL_TESTED': 'yes -- empty panel, empty dressed set, no scored units, fit season not held out',
        'ADVERSARIAL_TESTED': ('yes -- truncating the panel at 2024 leaves every fitted object identical; perturbing '
                               'week >= W data leaves week-W predictions identical; the depth table and proj_v1 '
                               'constants are unmutated'),
        'PROSPECTIVELY_VALIDATED': 'NO -- 2025 is retrospective out-of-sample'}
    doc['PROMOTION_RECOMMENDATION'] = recommendation(doc)
    OUT.write_text(json.dumps(doc, indent=1, default=float))
    return OUT, doc


LIMITATIONS = [
    'DRESSED PROXY LEAKS A LITTLE OUTCOME: "dressed" is presence in snap counts, i.e. >= 1 offensive or special-teams '
    'snap. An officially active player who took no snap is absent from both the pool and the scored set, so observed '
    'zero shares are understated in BOTH arms and the 2024 candidate rates are measured under the same proxy. Live, '
    'the official ACTIVE list would admit those players and the realised rate for qualifiers would be lower. The size '
    'of this effect is not measured here (needs 2024-2025 game-day inactives, not in the committed data).',
    'BACKUP QB COHORT IS DOMINATED BY THAT PROXY: a backup quarterback appears in snap counts essentially only when he '
    'plays, so the observed 0.72 P(>=1 pass attempt) is conditional on taking a snap and is NOT a calibration of the '
    'current model for dressed backups. SC-APPEAR-1 does not apply to QB (RB/WR/TE only); the cohort is reported as '
    'current-model figures only and the two arms are identical on QB pass attempts by construction.',
    'ELEVATIONS: practice-squad elevations are not identifiable for 2025 from committed data; the cohort is a proxy.',
    'RETURNING PLAYERS: absence cause is unknown; by construction none of them qualify (a missed game breaks the '
    '3-game condition), so their appearance probability is unchanged and only renormalisation moves their volume.',
    'RANK-1 QUALIFIERS ARE LOWERED: the candidate replaces a rank-1 P(plays) of 1.0 with the pooled 2024 rate, which '
    'sits below the observed rank-1 qualifier rate; the starter bar still passes because expected opportunity for '
    'starters was over-allocated by the current model, but the zero-mass Brier for rank-1 is slightly worse (within '
    '2 SE).',
    'RESIDUAL SUPPRESSION REMAINS for partially established players (1-2 of 3 prior games) at rank >= 2, whom the '
    'candidate does not touch by design.',
    'HARNESS IS NOT LIVE PRODUCTION: no role state, no captured chart rank, no market response, QB starter proxy from '
    'prior pass attempts. The allocator, its depth table and its conditional pass are production code.',
    'WEEK-BLOCKED SEs rest on 15 blocks; club-blocked SEs are reported alongside and are wider.',
    '2025 HAS NOW BEEN READ TWICE (forward test, this replay). Any variant chosen after this read needs a new holdout.',
]


def compact(primary):
    out = {}
    for k, c in primary['cohorts'].items():
        if not c.get('n_units'):
            out[k] = 'EMPTY'
            continue
        cu, ca = c['current'], c['candidate']
        out[k] = {
            'n_units': c['n_units'], 'n_qualifying_units': c.get('n_qualifying_units'),
            'mean_actual': c['mean_actual'],
            'mean_expected_cur_cand': [cu['mean_expected_opportunity'], ca['mean_expected_opportunity']],
            'signed_error_cur_cand_with_se': [[cu['signed_error_pred_minus_actual']['pooled'], cu['signed_error_pred_minus_actual']['se']],
                                              [ca['signed_error_pred_minus_actual']['pooled'], ca['signed_error_pred_minus_actual']['se']]],
            'abs_error_cur_cand': [cu['abs_error']['pooled'], ca['abs_error']['pooled']],
            'abs_error_improvement_week_blocked': c['improvement_abs_error']['week_blocked'],
            'P0_pred_cur_cand_obs': [cu['predicted_P0'], ca['predicted_P0'], c['observed_zero_share']],
            'zero_mass_error_cur_cand_with_se': [[cu['zero_mass_error_pred_minus_obs']['pooled'], cu['zero_mass_error_pred_minus_obs']['se']],
                                                 [ca['zero_mass_error_pred_minus_obs']['pooled'], ca['zero_mass_error_pred_minus_obs']['se']]],
            'zero_brier_improvement_week_blocked': c['improvement_zero_brier']['week_blocked']}
    return out


def recommendation(doc):
    p = doc['PRIMARY_DRESSED_UNIVERSE']
    c = p['cohorts']
    bar = p['DECLARED_BAR_CHECKS']

    def z(k, m):
        return c[k][m]['week_blocked']['z']
    passed = [k for k, v in bar.items() if v]
    failed = [k for k, v in bar.items() if not v]
    return {
        'STATUS': 'RECOMMENDATION_ONLY -- NOTHING PROMOTED, NO PRODUCTION DEFAULT CHANGED',
        'declared_bar_result_primary': p['DECLARED_BAR'],
        'declared_bar_result_sensitivity': doc['SENSITIVITY_FORWARD_CHAIN_POOL']['DECLARED_BAR'],
        'passed': passed, 'failed': failed,
        'headline_z_week_blocked': {
            'qualifying_abs_error': z('QUALIFYING_RB_WR_TE', 'improvement_abs_error'),
            'qualifying_zero_brier': z('QUALIFYING_RB_WR_TE', 'improvement_zero_brier'),
            'rank1_abs_error': z('RANK1_RB_WR_TE', 'improvement_abs_error'),
            'rank1_zero_brier': z('RANK1_RB_WR_TE', 'improvement_zero_brier'),
            'all_rb_wr_te_abs_error': z('ALL_RB_WR_TE', 'improvement_abs_error'),
            'non_qualifying_abs_error': z('NON_QUALIFYING_RB_WR_TE', 'improvement_abs_error')},
        'remains': [
            'PROSPECTIVE validation: 2025 is retrospective out-of-sample and has now been read twice; a sealed forward '
            'window (2026 weeks scored after a frozen declaration) is the confirmatory test',
            'the dressed condition used snap-count presence (>= 1 snap) as the stand-in for the official ACTIVE list; '
            'production would use the official inactives, which admits active-but-zero-snap players the replay never saw',
            'practice-squad elevations are not identifiable in committed 2025 data; the cohort is a labelled proxy',
            'the candidate also changes rank-1 qualifiers (P(plays) 1.0 -> the 2024 rate); a rank>=2-only variant was '
            'NOT tested and must not be chosen on these 2025 numbers',
            'a production change is its own commit with its own baseline (governing rule 2), plus a proj_v1 '
            'keyword/hook defaulting to current behaviour, and the downstream showdown/classic boards re-run'],
        'what_the_owner_would_be_approving': (
            'replacing, for dressed RB/WR/TE who recorded >= 1 of a field in each of the club\'s previous 3 games, the '
            'depth-rank appearance rate read at proj_v1.allocate_opportunity line 879 with the 2024-measured rate for '
            'that condition (RB carries/targets, WR targets, TE targets); everyone else keeps the depth-rank rate. '
            'Club totals stay conserved, so the change REDISTRIBUTES opportunity inside a club toward established '
            'backups and away from starters and non-qualifiers; it does not add volume.'),
    }


if __name__ == '__main__':
    p, doc = run()
    print(p)
    pr = doc['PRIMARY_DRESSED_UNIVERSE']
    print(json.dumps({'bar': pr['DECLARED_BAR_CHECKS'], 'result': pr['DECLARED_BAR'],
                      'sens': doc['SENSITIVITY_FORWARD_CHAIN_POOL']['DECLARED_BAR'],
                      'identity': pr['hook_off_identity'], 'conservation': pr['conservation']}, indent=1))
