#!/usr/bin/env python3.12
"""OPP-ADJUST-1: build point-in-time frame (features, incumbents, targets). Read-only on /home/user/nfl.
Writes frame_*.pkl into this scratch dir. See PREREGISTRATION_OPP_ADJUST_1.md."""
import glob, json, pathlib, sys, collections, pickle
import numpy as np, pandas as pd

NFL = pathlib.Path('/home/user/nfl')
OUT = pathlib.Path(__file__).resolve().parent
PRIOR_GAMES = 4.0
FORBIDDEN = {'spread_line', 'total_line', 'vegas_wp', 'vegas_home_wp', 'club_spread', 'implied_total',
             'opponent_implied_total', 'moneyline', 'spread_line_raw', 'home_wp', 'away_wp', 'wp',
             'vegas_home_wpa', 'vegas_wpa'}
PBP_COLS = ['game_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'pass', 'rush',
            'sack', 'qb_hit', 'qb_kneel', 'qb_spike', 'two_point_attempt', 'yards_gained', 'epa']
assert not FORBIDDEN & set(PBP_COLS)
PBP_FILES = {s: glob.glob(str(NFL / f'nfl/research/postgame/pbp_{s}.*.csv.gz')) for s in range(2021, 2026)}
PBP_FILES[2026] = [str(NFL / 'nfl/research/postgame/pbp_2026.2b3e9f2c6f92123f.csv.gz')]
TG_FIELDS = ['club', 'opponent', 'game_id', 'season', 'week', 'is_home', 'points', 'pass_attempts',
             'rush_attempts', 'starting_qb_id']


def load_pbp():
    frames = []
    for s, fs in sorted(PBP_FILES.items()):
        assert len(fs) == 1, (s, fs)
        df = pd.read_csv(fs[0], usecols=PBP_COLS, low_memory=False)
        assert not FORBIDDEN & set(df.columns)
        df = df[df.season_type == 'REG']
        if s == 2026:
            df = df[df.week <= 4]
        frames.append(df)
    p = pd.concat(frames, ignore_index=True)
    assert not ((p.season == 2026) & (p.week >= 5)).any()
    p = p[p.play_type.isin(['pass', 'run']) & (p.qb_kneel.fillna(0) == 0) & (p.qb_spike.fillna(0) == 0)
          & (p.two_point_attempt.fillna(0) == 0) & p.epa.notna() & p.posteam.notna() & p.defteam.notna()]
    p = p.copy()
    p['drop'] = (p['pass'].fillna(0) == 1).astype(int)
    p['rsh'] = 1 - p['drop']
    p['press'] = (((p.sack.fillna(0) == 1) | (p.qb_hit.fillna(0) == 1)) & (p['drop'] == 1)).astype(int)
    p['expl'] = (((p['drop'] == 1) & (p.yards_gained >= 20)) | ((p['rsh'] == 1) & (p.yards_gained >= 10))).astype(int)
    p['epa_drop'] = p.epa * p['drop']
    p['epa_rsh'] = p.epa * p['rsh']
    p['one'] = 1
    return p


def load_tg():
    a = json.loads((NFL / 'nfl/warehouse/TEAM_GAME.json').read_text())
    rows = a['rows'] if isinstance(a['rows'], list) else list(a['rows'].values())
    t = pd.DataFrame([{k: r.get(k) for k in TG_FIELDS} for r in rows])
    assert not FORBIDDEN & set(t.columns)
    t = t[(t.season >= 2020) & (t.week <= 18)]
    t = t[~((t.season == 2026) & (t.week >= 5))]
    for c in ('points', 'pass_attempts', 'rush_attempts'):
        t[c] = pd.to_numeric(t[c], errors='coerce')   # era sentinels -> NaN, never 0
    t = t[t.points.notna()].copy()
    opp = t[['game_id', 'club', 'points']].rename(columns={'club': 'opponent', 'points': 'points_allowed'})
    t = t.merge(opp, on=['game_id', 'opponent'], how='left')
    return t.reset_index(drop=True)


# ---------- generic unit-game aggregates: (season, week, unit) -> {var: (N, D)} ----------
VARS_PBP = {  # var: (numerator col, denominator col, unit side)
    'D1': ('epa', 'one', 'defteam'), 'D2': ('epa_drop', 'drop', 'defteam'), 'D3': ('epa_rsh', 'rsh', 'defteam'),
    'D4': ('press', 'drop', 'defteam'), 'D5': ('expl', 'one', 'defteam'), 'OWNP': ('press', 'drop', 'posteam'),
}


def unit_games(p, tg):
    out = {}
    for v, (n, d, side) in VARS_PBP.items():
        g = p.groupby(['season', 'week', side])[[n, d]].sum().reset_index()
        g.columns = ['season', 'week', 'unit', 'N', 'D']
        out[v] = g
    g6 = tg[['season', 'week', 'club', 'points']].copy(); g6['D'] = 1.0
    g6.columns = ['season', 'week', 'unit', 'N', 'D']; out['D6'] = g6          # opponent offence (unit=scorer)
    g7 = tg[['season', 'week', 'club', 'points_allowed']].dropna().copy(); g7['D'] = 1.0
    g7.columns = ['season', 'week', 'unit', 'N', 'D']; out['D7'] = g7          # opponent defence (unit=allower)
    return out


class PIT:
    """Point-in-time components for one variable. Uses only rows with (season, week) < (S, W)."""

    def __init__(self, ug):
        self.by = collections.defaultdict(list)   # (unit, season) -> list of (week, N, D)
        self.lg = collections.defaultdict(list)   # season -> list of (week, N, D)
        self._lc = {}
        for s, w, u, n, d in ug[['season', 'week', 'unit', 'N', 'D']].itertuples(index=False):
            self.by[(u, int(s))].append((int(w), float(n), float(d)))
            self.lg[int(s)].append((int(w), float(n), float(d)))

    def comps(self, unit, S, W):
        cur = [x for x in self.by.get((unit, S), []) if x[0] < W]
        prv = self.by.get((unit, S - 1), [])
        wp = PRIOR_GAMES / len(prv) if prv else 0.0
        N = sum(x[1] for x in cur) + wp * sum(x[1] for x in prv)
        D = sum(x[2] for x in cur) + wp * sum(x[2] for x in prv)
        key = (S, W)
        if key not in self._lc:
            pool = [x for x in self.lg.get(S, []) if x[0] < W] + self.lg.get(S - 1, [])
            if not pool:
                self._lc[key] = (None, None)
            else:
                LN = sum(x[1] for x in pool); LD = sum(x[2] for x in pool)
                self._lc[key] = (LN / LD if LD else None, LD / len(pool))
        mu, m = self._lc[key]
        return N, D, mu, m


def shrunk(N, D, mu, m, k):
    if mu is None:
        return 0.0
    return (N + k * m * mu) / (D + k * m) - mu


def estimate_k(ug, seasons):
    """Split-half method of moments on training seasons only. Returns (k, tau2, sigma2) or (None,...)."""
    covs, within = [], []
    for s in seasons:
        sub = ug[ug.season == s]
        odd, even = [], []
        for u, g in sub.groupby('unit'):
            g = g.sort_values('week')
            r = (g.N / g.D).replace([np.inf, -np.inf], np.nan).dropna()
            if len(r) >= 4:
                within.append(r.var(ddof=1))
            go, ge = g.iloc[0::2], g.iloc[1::2]
            if go.D.sum() > 0 and ge.D.sum() > 0:
                odd.append(go.N.sum() / go.D.sum()); even.append(ge.N.sum() / ge.D.sum())
        if len(odd) > 5:
            covs.append(np.cov(odd, even, ddof=1)[0, 1])
    tau2 = float(np.mean(covs)); sigma2 = float(np.mean(within))
    if tau2 <= 0:
        return None, tau2, sigma2
    return float(np.clip(sigma2 / tau2, 1, 200)), tau2, sigma2


def incumbent(table, unit, S, W):
    """football_points.expected_points logic applied to any per-game series. table: (unit,S)->{W: y}."""
    cur = {w: y for w, y in table.get((unit, S), {}).items() if w < W}
    prv = table.get((unit, S - 1), {})
    pc = np.mean(list(cur.values())) if cur else None
    pp = np.mean(list(prv.values())) if prv else None
    if pc is None and pp is None:
        return np.nan
    if pp is None:
        return pc
    if pc is None:
        return pp
    return (pc * len(cur) + pp * PRIOR_GAMES) / (len(cur) + PRIOR_GAMES)


def series_table(df, unit_col, ycol):
    t = collections.defaultdict(dict)
    for u, s, w, y in df[[unit_col, 'season', 'week', ycol]].itertuples(index=False):
        if pd.notna(y):
            t[(u, int(s))][int(w)] = float(y)
    return t


def qb_subset(tg):
    lab = {}
    for c, g in tg.sort_values(['season', 'week']).groupby('club'):
        qbs = list(g.starting_qb_id); keys = list(zip(g.game_id))
        for i, gid in enumerate(g.game_id):
            if i < 3 or not qbs[i] or any(not q for q in qbs[i - 3:i]):
                lab[(gid, c)] = 'UNLABELLED'
            else:
                lab[(gid, c)] = 'STABLE' if all(q == qbs[i] for q in qbs[i - 3:i]) else 'QB_CHANGE'
    return lab


def main():
    p = load_pbp(); tg = load_tg()
    ug = unit_games(p, tg)
    pits = {v: PIT(g) for v, g in ug.items()}
    club = tg[tg.season >= 2021].copy()
    # components for opponent features (unit = opponent) and own pass protection (unit = club)
    comp_rows = []
    for r in club.itertuples(index=False):
        S, W = int(r.season), int(r.week)
        rec = {'game_id': r.game_id, 'club': r.club}
        for v in ('D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'):
            rec[v] = pits[v].comps(r.opponent, S, W)
        rec['OWNP'] = pits['OWNP'].comps(r.club, S, W)
        comp_rows.append(rec)
    comps = pd.DataFrame(comp_rows)
    club = club.merge(comps, on=['game_id', 'club'])
    for y in ('points', 'pass_attempts', 'rush_attempts'):
        tab = series_table(tg, 'club', y)
        club['inc_' + y] = [incumbent(tab, c, int(s), int(w)) for c, s, w in club[['club', 'season', 'week']].itertuples(index=False)]
    lab = qb_subset(tg)
    club['subset'] = [lab[(g, c)] for g, c in club[['game_id', 'club']].itertuples(index=False)]
    # ---- truncation self-test: recompute from data strictly before (S,W) only ----
    rng = np.random.default_rng(7)
    idx = rng.choice(len(club), 60, replace=False)
    mism = 0
    for i in idx:
        r = club.iloc[i]; S, W = int(r.season), int(r.week)
        for v in ('D2', 'D4', 'D6', 'D7'):
            g = ug[v]; trunc = g[(g.season < S) | ((g.season == S) & (g.week < W))]
            a = PIT(trunc).comps(r.opponent, S, W); b = r[v]
            if not all((x is None and y is None) or (x is not None and y is not None and abs(x - y) < 1e-9) for x, y in zip(a, b)):
                mism += 1
        trunc_tg = tg[(tg.season < S) | ((tg.season == S) & (tg.week < W))]
        ip = incumbent(series_table(trunc_tg, 'club', 'points'), r.club, S, W)
        if not (np.isnan(ip) and np.isnan(r.inc_points)) and abs(ip - r.inc_points) > 1e-9:
            mism += 1
    print('truncation self-test mismatches:', mism)
    assert mism == 0
    # ---- player / position-group fantasy frame (2021-2025) ----
    pg = json.loads((NFL / 'nfl/warehouse/PLAYER_GAME.json').read_text())['rows']
    pg = pg if isinstance(pg, list) else list(pg.values())
    pgd = pd.DataFrame([{k: r.get(k) for k in ('player_id', 'club', 'opponent', 'game_id', 'season', 'week',
                                               'dk_points_current_rules')} for r in pg])
    pgd['week'] = pgd.week.astype(int); pgd = pgd[(pgd.season >= 2021) & (pgd.season <= 2025)]
    rh = json.loads((NFL / 'nfl/warehouse/ROLE_HISTORY.json').read_text())['rows']
    rh = rh if isinstance(rh, list) else list(rh.values())
    pos = pd.DataFrame([(r['player_id'], r['position']) for r in rh], columns=['player_id', 'pos'])
    pos = pos.groupby('player_id').pos.agg(lambda s: s.value_counts().index[0])
    # Amendment A1: nflverse players crosswalk first, ROLE_HISTORY fallback
    xw = pd.read_csv(NFL / 'nfl/postgame/raw/role_audit_history/players_crosswalk.bea61fc25c863150.csv.gz')
    xw = xw.drop_duplicates('gsis_id').set_index('gsis_id').position.replace({'FB': 'RB'})
    pgd['pos'] = pgd.player_id.map(xw).fillna(pgd.player_id.map(pos))
    print('player-game rows', len(pgd), 'position unknown share', round(pgd.pos.isna().mean(), 4),
          'dk unknown', pgd.dk_points_current_rules.isna().sum())
    pgd = pgd[pgd.pos.isin(['QB', 'RB', 'WR', 'TE'])]
    grp = pgd.groupby(['game_id', 'club', 'season', 'week', 'pos']).dk_points_current_rules.sum().unstack('pos')
    grp = grp.reset_index()
    nmiss = grp[['QB', 'RB', 'WR', 'TE']].isna().sum().to_dict(); print('group missing (set 0):', nmiss)
    grp[['QB', 'RB', 'WR', 'TE']] = grp[['QB', 'RB', 'WR', 'TE']].fillna(0.0)
    for P in ('QB', 'RB', 'WR', 'TE'):
        tab = series_table(grp, 'club', P)
        grp['inc_' + P] = [incumbent(tab, c, int(s), int(w)) for c, s, w in grp[['club', 'season', 'week']].itertuples(index=False)]
    ptab = series_table(pgd, 'player_id', 'dk_points_current_rules')
    pgd['inc_player'] = [incumbent(ptab, u, int(s), int(w)) for u, s, w in pgd[['player_id', 'season', 'week']].itertuples(index=False)]
    with open(OUT / 'frame.pkl', 'wb') as fh:
        pickle.dump({'club': club, 'grp': grp, 'pgd': pgd, 'ug': ug, 'tg': tg}, fh)
    print('club rows', len(club), club.groupby('season').size().to_dict())
    print('subset counts', club.groupby(['season', 'subset']).size().unstack().to_dict())


if __name__ == '__main__':
    main()
