#!/usr/bin/env python3.12
"""ATL@NO postgame item 5 -- football-world coherence RE-MEASURE: history vs simulator vs the actual game.

    python3.12 nfl/postgame/showdown_atl_no_coherence.py

LAYER: POSTGAME_DIAGNOSIS. Reads the sealed v2 worlds (RW_INACTIVES_CHARTFIX), the 2021-25 nflverse pbp and the
preserved 2026 pbp. Writes ATL_NO_COHERENCE_REMEASURE.json. Nothing here changes the simulator or any forecast.

WHY A RE-MEASURE AND NOT A REPEAT. The prelock DEFECT-COHERENCE number (sim 0.55 vs history 0.811) compared two
quantities that were not built the same way: the simulator side summed player DK points (with yardage bonuses) and
the history side summed play-level DK core (no bonuses) pooled over every team-game, so between-team and
between-season differences in offence level were part of the history target and absent from a single-matchup sim.
Here ONE definition is applied to all three sources:

  DK core = 0.04 pass yd + 4 pass TD - 1 INT + 0.1 rush yd + 6 rush TD + 0.1 rec yd + 1 rec + 6 rec TD
            (no yardage bonuses; fumbles excluded because the simulator does not draw them)
  team offensive TDs = rushing TDs + receiving TDs; team points = final score

and history is reported both RAW (pooled, what the prelock target was) and WITHIN team-season (team-season means
removed from both variables), which is the like-for-like target for one fixed matchup.

ROLES are defined from information available BEFORE the game (rule: defects against predictions, never outcomes):
history ranks receivers by season-to-date targets in prior weeks (any position) and rushers by prior carries; the
simulator ranks by its own projected means; the actual game ranks by 2026 weeks 1-3. Ranking by in-game targets
would condition on the outcome and inflate every pair correlation, so it is not used.

ONE GAME CANNOT ESTIMATE A CORRELATION. For the actual game the report places the realised pair (team TDs, team
offensive DK) inside the simulator's conditional distribution and inside history's, which is a single observation
and is labelled n = 1 everywhere. Nothing here is fitted to ATL@NO.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import kicker_world as KW  # noqa: E402
from nfl.market import atl_no_prop_shadow as PS  # noqa: E402

GAME = '2026_04_ATL_NO'
SD = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
RAW = _REPO / 'nfl/postgame/raw/showdown_atl_no_2026W4'
COLS = ['game_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'home_team', 'away_team', 'total_home_score',
        'total_away_score', 'passer_player_id', 'receiver_player_id', 'rusher_player_id', 'kicker_player_id',
        'passing_yards', 'receiving_yards', 'rushing_yards', 'complete_pass', 'pass_attempt', 'sack', 'pass_touchdown',
        'rush_touchdown', 'interception', 'field_goal_result', 'kick_distance', 'extra_point_result', 'play_type']
N_BOOT = 1000
BOOT_SEED = 20261006


class CoherenceError(RuntimeError):
    pass


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _load(paths):
    frames = []
    for p in paths:
        df = pd.read_csv(p, usecols=lambda c: c in COLS, low_memory=False)
        frames.append(df[df.season_type == 'REG'])
    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        raise CoherenceError('PBP_EMPTY')
    return df


def player_games(df):
    """Per (game, team, player) DK core plus targets/carries; per (game, team) totals, points and kicker DK."""
    f = df.copy()
    num = ['passing_yards', 'receiving_yards', 'rushing_yards', 'complete_pass', 'pass_touchdown', 'rush_touchdown',
           'interception', 'kick_distance']
    f[num] = f[num].fillna(0)
    rows = []
    p = f[f.passer_player_id.notna()]
    rows.append(pd.DataFrame({'game_id': p.game_id, 'season': p.season, 'week': p.week, 'team': p.posteam,
                              'pid': p.passer_player_id, 'dk': 0.04 * p.passing_yards + 4 * p.pass_touchdown - p.interception,
                              'att': (p.pass_attempt.fillna(0) - p.sack.fillna(0)).clip(lower=0), 'tgt': 0, 'car': 0, 'td': 0, 'ptd': 0}))
    r = f[f.receiver_player_id.notna()]
    rows.append(pd.DataFrame({'game_id': r.game_id, 'season': r.season, 'week': r.week, 'team': r.posteam,
                              'pid': r.receiver_player_id,
                              'dk': 0.1 * r.receiving_yards + r.complete_pass + 6 * r.pass_touchdown,
                              'att': 0, 'tgt': 1, 'car': 0, 'td': r.pass_touchdown, 'ptd': r.pass_touchdown}))
    u = f[f.rusher_player_id.notna()]
    rows.append(pd.DataFrame({'game_id': u.game_id, 'season': u.season, 'week': u.week, 'team': u.posteam,
                              'pid': u.rusher_player_id, 'dk': 0.1 * u.rushing_yards + 6 * u.rush_touchdown,
                              'att': 0, 'tgt': 0, 'car': (u.play_type == 'run').astype(int), 'td': u.rush_touchdown, 'ptd': 0}))
    pg = pd.concat(rows).groupby(['game_id', 'season', 'week', 'team', 'pid'], as_index=False).sum(numeric_only=True)
    tg = pg.groupby(['game_id', 'season', 'week', 'team'], as_index=False).agg(off_dk=('dk', 'sum'), td=('td', 'sum'), ptd=('ptd', 'sum'))
    fin = f.groupby('game_id').agg(home=('home_team', 'first'), away=('away_team', 'first'),
                                  hs=('total_home_score', 'max'), as_=('total_away_score', 'max')).reset_index()
    tg = tg.merge(fin, on='game_id')
    tg['pts'] = np.where(tg.team == tg.home, tg.hs, tg.as_)
    k = f[f.kicker_player_id.notna()].copy()
    fg = k.field_goal_result == 'made'
    k['kdk'] = np.where(fg, np.select([k.kick_distance >= 50, k.kick_distance >= 40], [5, 4], 3), 0) \
        + (k.extra_point_result == 'good').astype(int)
    kd = k.groupby(['game_id', 'posteam'], as_index=False).kdk.sum().rename(columns={'posteam': 'team'})
    tg = tg.merge(kd, on=['game_id', 'team'], how='left').fillna({'kdk': 0})
    return pg, tg


def pregame_roles(pg):
    """QB = the team's top passer in the game (starter); receivers ranked by PRIOR-week season-to-date targets, RB1 by
    prior carries. Week-1 games and players with no prior history have no role and are dropped."""
    pg = pg.sort_values(['season', 'team', 'pid', 'week'])
    g = pg.groupby(['season', 'team', 'pid'])
    pg['prior_tgt'] = g.tgt.cumsum() - pg.tgt
    pg['prior_car'] = g.car.cumsum() - pg.car
    out = {}
    for (gid, team), x in pg.groupby(['game_id', 'team']):
        qb = x.sort_values('att', ascending=False).iloc[0]
        if qb.att < 10:
            continue
        rec = x[(x.pid != qb.pid) & (x.prior_tgt > 0)].sort_values('prior_tgt', ascending=False)
        rb = x[(x.pid != qb.pid) & (x.prior_car > 0)].sort_values('prior_car', ascending=False)
        if len(rec) < 3 or rb.empty:
            continue
        out[(gid, team)] = {'QB': qb.dk, 'TGT1': rec.iloc[0].dk, 'TGT2': rec.iloc[1].dk, 'TGT3': rec.iloc[2].dk,
                            'RB1': rb.iloc[0].dk, 'season': qb.season}
    return out


def _corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return None if a.std() == 0 or b.std() == 0 else float(np.corrcoef(a, b)[0, 1])


def _boot(df, fn, cluster='game_id'):
    rng = np.random.default_rng(BOOT_SEED)
    ids = df[cluster].unique()
    idx = {g: i for g, i in df.groupby(cluster).indices.items()}
    vals = []
    for _ in range(N_BOOT):
        take = np.concatenate([idx[g] for g in rng.choice(ids, size=len(ids))])
        v = fn(df.iloc[take])
        if v is not None:
            vals.append(v)
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def _demean(df, cols, by):
    d = df.copy()
    for c in cols:
        d[c] = d[c] - d.groupby(by)[c].transform('mean')
    return d


PAIRS = [('QB', 'TGT1'), ('QB', 'TGT2'), ('QB', 'TGT3'), ('TGT1', 'TGT2'), ('QB', 'RB1'), ('QB', 'OPP_TGT1'),
         ('TGT1', 'OPP_TGT1')]


def history():
    df = _load(KW._pbp_paths().values())
    pg, tg = player_games(df)
    tg['team_season'] = tg.season.astype(str) + tg.team
    team = {}
    for name, (a, b) in {'td_vs_off_dk': ('td', 'off_dk'), 'points_vs_off_dk': ('pts', 'off_dk'),
                         'kicker_dk_vs_off_dk': ('kdk', 'off_dk'), 'kicker_dk_vs_points': ('kdk', 'pts')}.items():
        dm = _demean(tg, [a, b], 'team_season')
        team[name] = {'raw': round(_corr(tg[a], tg[b]), 3), 'raw_ci95': _boot(tg, lambda x: _corr(x[a], x[b])),
                      'within_team_season': round(_corr(dm[a], dm[b]), 3),
                      'within_team_season_ci95': _boot(dm, lambda x: _corr(x[a], x[b]))}
    tg['yard_dk'] = tg.off_dk - 6 * tg.td - 4 * tg.ptd
    dm = _demean(tg, ['yard_dk', 'td'], 'team_season')
    team['yardage_dk_per_td_slope'] = {'raw': round(float(np.polyfit(tg.td, tg.yard_dk, 1)[0]), 2),
                                       'within_team_season': round(float(np.polyfit(dm.td, dm.yard_dk, 1)[0]), 2),
                                       'within_team_season_ci95': _boot(dm, lambda x: float(np.polyfit(x.td, x.yard_dk, 1)[0])),
                                       'MEANING': 'DK from yards and receptions (TD points removed) per extra offensive TD'}
    R = pregame_roles(pg)
    rows = []
    for (gid, t), r in R.items():
        opp = [k for k in R if k[0] == gid and k[1] != t]
        if not opp:
            continue
        rows.append({'game_id': gid, 'team': t, 'team_season': f"{r['season']}{t}",
                     **{k: r[k] for k in ('QB', 'TGT1', 'TGT2', 'TGT3', 'RB1')}, 'OPP_TGT1': R[opp[0]]['TGT1']})
    pr = pd.DataFrame(rows)
    pairs = {}
    for a, b in PAIRS:
        dm = _demean(pr, [a, b], 'team_season')
        pairs[f'{a}-{b}'] = {'raw': round(_corr(pr[a], pr[b]), 3), 'raw_ci95': _boot(pr, lambda x: _corr(x[a], x[b])),
                             'within_team_season': round(_corr(dm[a], dm[b]), 3)}
    # conditional reference for the actual-game placement: off_dk given td (raw, all team-games)
    cond = {int(k): v.off_dk.to_numpy() for k, v in tg.groupby('td')}
    return {'team_games': int(len(tg)), 'role_team_games': int(len(pr)), 'team': team, 'pairs': pairs}, cond, tg


def simulator():
    stats, _pts, meta = PS.CR.load_worlds(next(SD.glob('SHOWDOWN_*_WORLDS.npz')))
    F = {f: i for i, f in enumerate(meta['fields'])}
    ys = meta['yard_scale']
    keys = list(meta['keys'])
    g = lambda i, f: stats[i, :, F[f]] / (ys if f in meta['yard_fields'] else 1)
    dk, tgt, car, att, td, team_of, tdpts = {}, {}, {}, {}, {}, {}, {}
    for i, k in enumerate(keys):
        dk[k] = (0.04 * g(i, 'pass_yards') + 4 * g(i, 'pass_td') - g(i, 'interceptions') + 0.1 * g(i, 'rush_yards')
                 + 6 * g(i, 'rush_td') + 0.1 * g(i, 'rec_yards') + g(i, 'receptions') + 6 * g(i, 'rec_td'))
        tgt[k], car[k], att[k] = g(i, 'targets').mean(), g(i, 'carries').mean(), g(i, 'pass_att').mean()
        td[k] = g(i, 'rush_td') + g(i, 'rec_td')
        tdpts[k] = 6 * g(i, 'rush_td') + 6 * g(i, 'rec_td') + 4 * g(i, 'pass_td')
        team_of[k] = k.split('|')[1]
    d = json.loads(next(SD.glob('SHOWDOWN_*_DRAWS.json')).read_text())
    wp = np.asarray(d['world_points']['points'], float)
    col = {d['world_points']['home']: 0, d['world_points']['away']: 1}
    # world alignment check: the DRAWS DK series and the WORLDS stat lines must be the same worlds
    qb = max((k for k in keys if team_of[k] == 'NO'), key=lambda k: att[k])
    align = _corr(dk[qb], np.asarray(d['draws'][qb], float))
    if align is None or align < 0.95:
        raise CoherenceError(f'WORLD_ALIGNMENT_FAILED {qb} r={align}')
    teams = sorted(col)
    team, roles, per_world = {}, {}, {}
    for t in teams:
        ks = [k for k in keys if team_of[k] == t]
        off = sum(dk[k] for k in ks)
        tds = sum(td[k] for k in ks)
        kick = next((k for k in d.get('kickers', {}) if k.endswith('|' + t) and k in d['draws']), None)
        kdk = None if kick is None else np.asarray(d['draws'][kick], float)
        q = max(ks, key=lambda k: att[k])
        rec = sorted((k for k in ks if k != q), key=lambda k: -tgt[k])
        rb = max((k for k in ks if k != q), key=lambda k: car[k])
        roles[t] = {'QB': q, 'TGT1': rec[0], 'TGT2': rec[1], 'TGT3': rec[2], 'RB1': rb, 'K': kick}
        per_world[t] = {'off_dk': off, 'td': tds, 'pts': wp[:, col[t]]}
        team[t] = {'td_vs_off_dk': round(_corr(tds, off), 3), 'points_vs_off_dk': round(_corr(wp[:, col[t]], off), 3),
                   'yardage_dk_per_td_slope': round(float(np.polyfit(tds, off - sum(tdpts[k] for k in ks), 1)[0]), 2),
                   'kicker_dk_vs_off_dk': None if kdk is None else round(_corr(kdk, off), 3),
                   'kicker_dk_vs_points': None if kdk is None else round(_corr(kdk, wp[:, col[t]]), 3),
                   **({} if kdk is not None else {'kicker': 'NOT_IN_DRAWS (kicker not in the DK player pool draws)'})}
    pairs = {}
    for t in teams:
        o = [x for x in teams if x != t][0]
        r = roles[t]
        val = lambda role: dk[roles[o]['TGT1']] if role == 'OPP_TGT1' else dk[r[role]]
        pairs[t] = {f'{a}-{b}': round(_corr(val(a), val(b)), 3) for a, b in PAIRS}
    return {'team': team, 'pairs': pairs, 'roles': roles, 'world_alignment_r': round(align, 4),
            'n_worlds': int(stats.shape[1])}, per_world


def actual():
    p26 = sorted(RAW.glob('NFLVERSE_PBP_2026.*.csv.gz'))
    if len(p26) != 1:
        raise CoherenceError(f'PBP_2026_AMBIGUOUS {p26}')
    df = _load(p26)
    df = df[df.week <= 4]
    pg, tg = player_games(df)
    R = pregame_roles(pg)
    g = tg[tg.game_id == GAME]
    if len(g) != 2:
        raise CoherenceError(f'ACTUAL_GAME_MISSING {GAME} rows={len(g)}')
    out = {}
    for _, r in g.iterrows():
        out[r.team] = {'off_dk': round(float(r.off_dk), 2), 'td': int(r.td), 'pts': int(r.pts), 'kicker_dk': int(r.kdk),
                       'roles_dk': {k: round(float(v), 2) for k, v in R.get((GAME, r.team), {}).items() if k != 'season'}}
    return out, p26[0]


def place(act, per_world, cond):
    out = {}
    for t, a in act.items():
        w = per_world[t]
        same = w['off_dk'][w['td'] == a['td']]
        h = cond.get(a['td'], np.array([]))
        out[t] = {'actual_td': a['td'], 'actual_off_dk': a['off_dk'],
                  'sim_marginal_pct_off_dk': round(float((w['off_dk'] <= a['off_dk']).mean()), 3),
                  'sim_marginal_pct_td': round(float((w['td'] <= a['td']).mean()), 3),
                  'sim_worlds_with_actual_td': int(len(same)),
                  'sim_conditional_off_dk_given_td': None if len(same) < 20 else {
                      'mean': round(float(same.mean()), 2), 'sd': round(float(same.std()), 2),
                      'pct_of_actual': round(float((same <= a['off_dk']).mean()), 3)},
                  'history_conditional_off_dk_given_td': None if len(h) < 20 else {
                      'n': int(len(h)), 'mean': round(float(h.mean()), 2), 'sd': round(float(h.std()), 2),
                      'pct_of_actual': round(float((h <= a['off_dk']).mean()), 3)},
                  'sim_unconditional_off_dk': {'mean': round(float(w['off_dk'].mean()), 2),
                                               'sd': round(float(w['off_dk'].std()), 2)},
                  'NOTE': 'n = 1 team-game; a placement, not an estimate'}
    return out


def run():
    hist, cond, _tg = history()
    sim, per_world = simulator()
    act, p26 = actual()
    for t in act:
        if t not in per_world:
            raise CoherenceError(f'TEAM_MISMATCH {t}')
    # sim conditional spread vs history conditional spread at matching TD counts (the defect, measured directly)
    spread = {}
    for t, w in per_world.items():
        rows = []
        for k in range(0, 7):
            s = w['off_dk'][w['td'] == k]
            h = cond.get(k, np.array([]))
            if len(s) >= 50 and len(h) >= 50:
                rows.append({'td': k, 'sim_n': int(len(s)), 'sim_sd': round(float(s.std()), 2),
                             'sim_mean': round(float(s.mean()), 2), 'hist_n': int(len(h)),
                             'hist_sd': round(float(h.std()), 2), 'hist_mean': round(float(h.mean()), 2)})
        spread[t] = rows
    hs = hist['team']['td_vs_off_dk']
    sims = [sim['team'][t]['td_vs_off_dk'] for t in sim['team']]
    lo, hi = hs['within_team_season_ci95']
    verdict = ('DEFECT_CONFIRMED_LIKE_FOR_LIKE' if max(sims) < lo else
               'DEFECT_NOT_CONFIRMED_LIKE_FOR_LIKE' if lo <= min(sims) else 'MIXED_BY_TEAM')
    doc = {'ARTIFACT': 'ATL_NO_COHERENCE_REMEASURE', 'LAYER': 'POSTGAME_DIAGNOSIS', 'game': GAME,
           'definition': {'dk_core': '0.04 pass yd + 4 pass TD - INT + 0.1 rush yd + 6 rush TD + 0.1 rec yd + rec + 6 rec TD',
                          'excluded': 'yardage bonuses; fumbles (not simulated)', 'team_td': 'rush TD + rec TD',
                          'roles': 'pregame: prior-week season-to-date targets / carries (history, actual); projected means (sim)'},
           'sources': {'history_pbp': {str(s): str(p.relative_to(_REPO)) for s, p in KW._pbp_paths().items()},
                       'actual_pbp': {'file': str(p26.relative_to(_REPO)), 'sha256': _sha(p26)},
                       'sim_worlds': {'dir': str(SD.relative_to(_REPO)),
                                      'worlds_sha256': _sha(next(SD.glob('SHOWDOWN_*_WORLDS.npz')))}},
           'history_2021_2025': hist, 'simulator_v2': sim, 'actual_atl_no': act,
           'actual_placement': place(act, per_world, cond),
           'conditional_spread_off_dk_given_td': spread,
           'VERDICT_TEAM_TD_VS_OFF_DK': verdict,
           'VERDICT_RULE': ('like-for-like target = history WITHIN team-season (one fixed matchup carries no between-team '
                            'variation); defect confirmed only if every simulated team sits below that target\'s lower '
                            '95% bound (game-clustered bootstrap, 1000 resamples)'),
           'NOT_FITTED_TO_ATL_NO': True, 'NOT_A_FORECAST_INPUT': True,
           'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / 'ATL_NO_COHERENCE_REMEASURE.json'
    p.write_text(json.dumps(doc, indent=1, default=float))
    return p, doc


if __name__ == '__main__':
    p, doc = run()
    print(p)
    print(json.dumps({k: doc[k] for k in ('history_2021_2025', 'simulator_v2', 'actual_atl_no', 'actual_placement',
                                          'conditional_spread_off_dk_given_td', 'VERDICT_TEAM_TD_VS_OFF_DK')},
                     indent=1, default=float)[:9000])
