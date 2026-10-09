"""Integration evaluation of the event-consistent shadow arm. Reads published/repaired draws and realised actuals;
writes one JSON of measurements. argv: out_json"""
import json, sys, pathlib, hashlib
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[4]
SCR = pathlib.Path(__import__('os').environ['EVAL_WORK'])   # scratch work dir (intermediates); required
sys.path.insert(0, str(REPO))
from nfl.tools import classic_slate_run as CR  # noqa
from nfl.sim import dst as dst_mod  # noqa

def _tb_actuals(work):
    """The TB@DAL postgame grading, read from the commit that added it (not on this branch)."""
    p = work / 'tbdal_post.json'
    if not p.exists():
        import subprocess
        p.write_bytes(subprocess.run(['git', 'show', 'be87cb0d:nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json'],
                                     cwd=REPO, capture_output=True, check=True).stdout)
    return p

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def rel(p):
    p = pathlib.Path(p)
    try: return str(p.resolve().relative_to(REPO))
    except ValueError: return str(p)

SLATES = {
    'TB_DAL_2026W5': {
        'inc': REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json',
        'proj': REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_PROJ.json',
        'rep_qb': REPO / 'nfl/research/accounting_repair/TB_DAL_2026W5/EVENT_CONSISTENT/SHOWDOWN_TB_DAL_2026W5_DRAWS.json',
        'rep_rec': REPO / 'nfl/research/accounting_repair/TB_DAL_2026W5/EVENT_CONSISTENT_RECEIVER_ANCHOR/SHOWDOWN_TB_DAL_2026W5_DRAWS.json',
        'act': _tb_actuals(SCR), 'act_src': 'git show be87cb0d:nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json',
        'hist_club_form': '2026_W1_4'},
    'ATL_NO_2026W4': {
        'inc': REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_DRAWS.json',
        'proj': REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_PROJ.json',
        'rep_qb': REPO / 'nfl/research/accounting_repair/ATL_NO_2026W4/EVENT_CONSISTENT/SHOWDOWN_ATL_NO_2026W4_DRAWS.json',
        'rep_rec': REPO / 'nfl/research/accounting_repair/ATL_NO_2026W4/EVENT_CONSISTENT_RECEIVER_ANCHOR/SHOWDOWN_ATL_NO_2026W4_DRAWS.json',
        'act': REPO / 'nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json',
        'act_src': 'nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json', 'hist_club_form': '2026_W1_3'},
}
ARMS = ('inc', 'rep_qb', 'rep_rec')
LEVELS = (0.5, 0.8, 0.9)

def crps(x, y):
    x = np.sort(x); n = len(x)
    i = np.arange(1, n + 1)
    e_xx = 2.0 * np.sum((2 * i - n - 1) * x) / (n * n)       # E|X-X'| over all ordered pairs (V-statistic)
    return float(np.mean(np.abs(x - y)) - 0.5 * e_xx)

def mid_pit(x, y):
    return float(np.mean(x < y) + 0.5 * np.mean(x == y))

def cover(x, y, c):
    lo, hi = np.quantile(x, [(1 - c) / 2, (1 + c) / 2])
    return bool(lo - 1e-9 <= y <= hi + 1e-9)

def player_metrics(x, y):
    return {'mean': float(x.mean()), 'sd': float(x.std()), 'err': float(x.mean() - y), 'crps': crps(x, y),
            'pit': mid_pit(x, y), **{f'cov{int(c*100)}': cover(x, y, c) for c in LEVELS}}

def summarise(rows, arm):
    if not rows: return None
    m = [r[arm] for r in rows]
    pits = np.array([v['pit'] for v in m])
    return {'n': len(rows), 'mean_crps': round(float(np.mean([v['crps'] for v in m])), 4),
            'mean_error': round(float(np.mean([v['err'] for v in m])), 4),
            'mae_of_mean': round(float(np.mean([abs(v['err']) for v in m])), 4),
            **{f'coverage_{int(c*100)}': round(float(np.mean([v[f'cov{int(c*100)}'] for v in m])), 4) for c in LEVELS},
            'pit_mean': round(float(pits.mean()), 4),
            'pit_deciles': np.histogram(pits, bins=np.linspace(0, 1, 11))[0].tolist()}

def boot_diff(rows, a, b, n_boot=4000, seed=7):
    d = np.array([r[b]['crps'] - r[a]['crps'] for r in rows])
    rng = np.random.default_rng(seed)
    bs = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    return {'mean_paired_crps_diff': round(float(d.mean()), 4), 'player_bootstrap_95': [round(float(q), 4) for q in np.quantile(bs, [.025, .975])],
            'n_players_better': int((d < 0).sum()), 'n_players_worse': int((d > 0).sum()), 'n_equal': int((d == 0).sum()),
            'CAVEAT': 'player-level bootstrap inside one game ignores within-game correlation (players share one game script); anti-conservative'}

def club_points_stats(pts):
    pts = np.asarray(pts, float)       # (n, 2) home, away
    flat = pts.ravel(); tot = pts.sum(1); mar = pts[:, 0] - pts[:, 1]
    return {'n_worlds': int(len(pts)), 'share_club_score_eq_1': round(float(np.mean(np.isclose(flat, 1.0))), 5),
            'share_club_score_in_open_interval_0_2_excl_0': round(float(np.mean((flat > 1e-9) & (flat < 2 - 1e-9))), 5),
            'share_non_integer_club_score': round(float(np.mean(np.abs(flat - np.round(flat)) > 1e-6)), 5),
            'share_club_score_zero': round(float(np.mean(np.isclose(flat, 0.0))), 5),
            'share_ties': round(float(np.mean(np.isclose(pts[:, 0], pts[:, 1]))), 5),
            'share_margin_3_or_7': round(float(np.mean(np.isin(np.round(np.abs(mar), 6), [3.0, 7.0]))), 5),
            'home_mean': round(float(pts[:, 0].mean()), 3), 'away_mean': round(float(pts[:, 1].mean()), 3),
            'total_mean': round(float(tot.mean()), 3), 'total_sd': round(float(tot.std()), 3),
            'total_p5': round(float(np.quantile(tot, .05)), 3), 'total_p95': round(float(np.quantile(tot, .95)), 3),
            'club_sd': round(float(flat.std()), 3), 'abs_margin_mean': round(float(np.abs(mar).mean()), 3)}

hist = json.loads((SCR / 'hist.json').read_text())
HY = ['2021', '2022', '2023', '2024', '2025']
H = [r for y in HY for r in hist[y]['club_games']]
HG = [g for y in HY for g in hist[y]['games']]
hpts = np.array([[g['hs'], g['as']] for g in HG], float)
hist_games = club_points_stats(hpts)
hist_games['n_games'] = len(HG)
# historical DST: unconditional and by points-allowed band (DK tier bands and simulator conditioning bands)
hdk = np.array([r['dk_pa_all'] for r in H], float); hpa = np.array([r['pa'] for r in H], float)
hdk_x = np.array([r['dk_pa_excl'] for r in H], float); hdk_nb = np.array([r['dk_no_blk_pa_all'] for r in H], float)
DKB = ((0, 1), (1, 7), (7, 14), (14, 21), (21, 28), (28, 35), (35, 999))
def band_of(p, bands):
    for lo, hi in bands:
        if lo <= p < hi: return f'{lo}-{hi}'
    return f'{bands[-1][0]}-{bands[-1][1]}'
def qs(v): return {f'p{q}': round(float(np.quantile(v, q / 100)), 3) for q in (5, 25, 50, 75, 95)}
hist_dst = {'n_club_games': len(H), 'seasons': HY, 'mean_dk_pa_all': round(float(hdk.mean()), 4), 'sd': round(float(hdk.std()), 4),
            'mean_dk_pa_excl_def_td_vs_offence': round(float(hdk_x.mean()), 4),
            'mean_dk_without_blocked_kicks': round(float(hdk_nb.mean()), 4),
            'share_integer': float(np.mean(np.isclose(hdk, np.round(hdk)))), **qs(hdk),
            'component_means': {k: round(float(np.mean([r[k] for r in H])), 4) for k in ('sack', 'int', 'fr', 'safety', 'dst_td', 'blk', 'pa')},
            'by_dk_band': {}, 'by_sim_band': {}}
for bands, key in ((DKB, 'by_dk_band'), (dst_mod.CONDITIONING_BANDS, 'by_sim_band')):
    for lo, hi in bands:
        m = (hpa >= lo) & (hpa < hi)
        hist_dst[key][f'{lo}-{hi}'] = {'n': int(m.sum()), 'mean_dk': round(float(hdk[m].mean()), 4) if m.any() else None,
                                       'mean_dk_no_blk': round(float(hdk_nb[m].mean()), 4) if m.any() else None}
def hist_cond_mean(pa_draws, bands=dst_mod.CONDITIONING_BANDS, field=hdk_nb):
    """E_hist[DST DK | the opponent-points band] averaged over an arm's own points-allowed draws."""
    lut = {}
    for lo, hi in bands:
        m = (hpa >= lo) & (hpa < hi); lut[(lo, hi)] = float(field[m].mean())
    out = []
    for p in pa_draws:
        for lo, hi in bands:
            if lo <= p < hi: out.append(lut[(lo, hi)]); break
        else: out.append(lut[bands[-1]])
    return float(np.mean(out))

def ks(a, b):
    a, b = np.sort(a), np.sort(b); grid = np.union1d(a, b)
    return float(np.max(np.abs(np.searchsorted(a, grid, 'right') / len(a) - np.searchsorted(b, grid, 'right') / len(b))))

def hist_resample_dist(pa_draws, field=hdk_nb, bands=dst_mod.CONDITIONING_BANDS, seed=11):
    """A history-implied DST DK distribution for an arm: for each world, a random historical club-game drawn from
    the same opponent-points band (simulator conditioning bands)."""
    rng = np.random.default_rng(seed); pools = {}
    for lo, hi in bands:
        pools[(lo, hi)] = field[(hpa >= lo) & (hpa < hi)]
    out = []
    for p in pa_draws:
        for lo, hi in bands:
            if lo <= p < hi: pool = pools[(lo, hi)]; break
        else: pool = pools[bands[-1]]
        out.append(pool[rng.integers(0, len(pool))])
    return np.array(out)

result = {'ARTIFACT': 'ACCOUNTING_REPAIR_INTEGRATION_MEASUREMENTS', 'slates': {}, 'history': {'games': hist_games, 'dst': hist_dst,
          'pbp_files': {y: hist[y]['file'] for y in hist}}}
pooled_rows = []
for tag, cfg in SLATES.items():
    docs = {a: json.loads(pathlib.Path(cfg[a]).read_text()) for a in ARMS}
    proj = json.loads(pathlib.Path(cfg['proj']).read_text())
    prow = {f"{r['name']}|{r['team']}": r for r in proj['rows'].values()}
    act_doc = json.loads(pathlib.Path(cfg['act']).read_text())
    acts = act_doc['player_actuals']
    keys = sorted(docs['inc']['draws'])
    assert all(set(docs[a]['draws']) == set(keys) for a in ARMS), 'player sets differ between arms'
    D = {a: {k: np.asarray(docs[a]['draws'][k], float) for k in keys} for a in ARMS}
    n_w = len(D['inc'][keys[0]])
    rows = []
    for k in keys:
        if k not in acts: continue
        y = float(acts[k]['dk_A'])
        pos = (prow.get(k) or {}).get('position') or acts[k].get('pos')
        r = {'slate': tag, 'player': k, 'pos': pos, 'actual': y, 'proj_dk': (prow.get(k) or {}).get('dk_points'),
             'zero_basis': (acts[k].get('join_provenance') or {}).get('zero_basis')}
        for a in ARMS: r[a] = player_metrics(D[a][k], y)
        rows.append(r)
    active = [r for r in rows if r['inc']['mean'] >= 1.0]
    cal = {'n_players_with_actuals': len(rows), 'n_players_inc_mean_ge_1': len(active), 'populations': {}}
    skill = [r for r in active if r['pos'] in ('QB', 'RB', 'WR', 'TE')]
    dstk = [r for r in rows if r['pos'] in ('DST', 'K')]
    for popname, pop in (('ALL_DRAWN', rows), ('INC_MEAN_GE_1', active), ('SKILL_INC_MEAN_GE_1', skill), ('DST_AND_K', dstk)):
        cal['populations'][popname] = {a: summarise(pop, a) for a in ARMS}
        cal['populations'][popname]['paired_crps_rep_qb_minus_inc'] = boot_diff(pop, 'inc', 'rep_qb')
        cal['populations'][popname]['paired_crps_rep_rec_minus_inc'] = boot_diff(pop, 'inc', 'rep_rec')
    bypos = {}
    for p in sorted({r['pos'] for r in rows}):
        pr = [r for r in rows if r['pos'] == p]
        bypos[p] = {'n': len(pr), **{a: {'mean_error': round(float(np.mean([r[a]['err'] for r in pr])), 4),
                                         'mean_crps': round(float(np.mean([r[a]['crps'] for r in pr])), 4)} for a in ARMS}}
    cal['by_position'] = bypos
    cal['per_player'] = [{'player': r['player'], 'pos': r['pos'], 'actual': r['actual'],
                          **{a: {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in r[a].items()} for a in ARMS}}
                         for r in rows]
    pooled_rows += rows
    # ---- projection means
    drift = {}
    for a in ('rep_qb', 'rep_rec'):
        pl = []
        for k in keys:
            d = D[a][k] - D['inc'][k]
            pl.append({'player': k, 'pos': (prow.get(k) or {}).get('position'), 'proj_dk': (prow.get(k) or {}).get('dk_points'),
                       'inc_mean': round(float(D['inc'][k].mean()), 4), 'rep_mean': round(float(D[a][k].mean()), 4),
                       'drift': round(float(d.mean()), 4), 'paired_se': round(float(d.std() / np.sqrt(len(d))), 4)})
        pl.sort(key=lambda r: -abs(r['drift']))
        pos_tot = {}
        for p in sorted({r['pos'] for r in pl if r['pos']}):
            sel = [r for r in pl if r['pos'] == p]
            dd = sum(D[a][r['player']] - D['inc'][r['player']] for r in sel)
            pos_tot[p] = {'n_players': len(sel), 'sum_drift': round(float(dd.mean()), 4), 'paired_se_of_sum': round(float(dd.std() / np.sqrt(len(dd))), 4),
                          'mean_abs_player_drift': round(float(np.mean([abs(r['drift']) for r in sel])), 4)}
        n_sig = sum(1 for r in pl if r['paired_se'] > 0 and abs(r['drift']) > 2 * r['paired_se'])
        drift[a] = {'players': pl, 'by_position': pos_tot, 'n_players': len(pl), 'n_abs_drift_gt_2se': n_sig,
                    'n_abs_drift_gt_0p5_dk': sum(1 for r in pl if abs(r['drift']) > 0.5)}
    # ---- DST
    home, away = docs['inc']['world_points']['home'], docs['inc']['world_points']['away']
    dst = {}
    for a in ARMS:
        wp = np.asarray(docs[a]['world_points']['points'], float)
        for k in keys:
            if (prow.get(k) or {}).get('position') != 'DST': continue
            club = k.rsplit('|', 1)[1]
            pa = wp[:, 1] if club == home else wp[:, 0]
            x = D[a][k]
            comp = np.asarray(docs[a]['dst_components'][k], float)
            recomputed = np.array([dst_mod.tier(p) for p in pa]) + comp[:, 0] + 2 * comp[:, 1] + 6 * comp[:, 2] + 2 * comp[:, 3]
            hr = hist_resample_dist(pa)
            e = dst.setdefault(k, {'projection_dk': (prow.get(k) or {}).get('dk_points'),
                                   'projection_event_items': ((prow.get(k) or {}).get('dst') or {}).get('event_items'),
                                   'actual_dk': acts.get(k, {}).get('dk_A')})
            e[a] = {'mean': round(float(x.mean()), 4), 'sd': round(float(x.std()), 4), **qs(x),
                    'share_non_integer': round(float(np.mean(np.abs(x - np.round(x)) > 1e-6)), 4),
                    'share_dk_ne_own_components_and_points_allowed': round(float(np.mean(np.abs(x - recomputed) > 1e-3)), 4),
                    'points_allowed_mean': round(float(pa.mean()), 3),
                    'history_conditional_mean_given_this_arms_points_allowed': round(hist_cond_mean(pa), 4),
                    'history_resampled': {'mean': round(float(hr.mean()), 4), 'sd': round(float(hr.std()), 4), **qs(hr)},
                    'ks_vs_history_resampled': round(ks(x, hr), 4),
                    'ks_vs_history_unconditional': round(ks(x, hdk_nb), 4),
                    'component_means': {'sacks': round(float(comp[:, 0].mean()), 4), 'takeaways': round(float(comp[:, 1].mean()), 4),
                                        'def_td': round(float(comp[:, 2].mean()), 4), 'safety': round(float(comp[:, 3].mean()), 4)}}
    # club-specific recent DST form, from pre-lock pbp
    form = {}
    for k in dst:
        club = k.rsplit('|', 1)[1]
        g25 = [r for r in hist['2025']['club_games'] if r['club'] == club]
        g26 = [r for r in hist[cfg['hist_club_form']]['club_games'] if r['club'] == club]
        allg = g25 + g26
        v = np.array([r['dk_pa_all'] for r in allg], float)
        form[k] = {'n_games_2025_plus_2026_prelock': len(allg), 'mean_dk': round(float(v.mean()), 3), 'se': round(float(v.std(ddof=1) / np.sqrt(len(v))), 3),
                   'mean_sacks': round(float(np.mean([r['sack'] for r in allg])), 3),
                   'mean_takeaways': round(float(np.mean([r['int'] + r['fr'] for r in allg])), 3),
                   'mean_points_allowed': round(float(np.mean([r['pa'] for r in allg])), 3),
                   'history_conditional_mean_given_own_pa': round(hist_cond_mean([r['pa'] for r in allg]), 3),
                   'pbp_2026_file': hist[cfg['hist_club_form']]['file']}
        resid = form[k]['mean_dk'] - form[k]['history_conditional_mean_given_own_pa']
        bench = dst[k]['rep_qb']['history_conditional_mean_given_this_arms_points_allowed'] + resid
        form[k]['CLUB_ADJUSTED_BENCHMARK'] = {
            'DEFINITION': ('league E[DST DK | opponent-points band] over the repaired arm\'s own points-allowed draws, plus the club\'s '
                           'unshrunk residual (own 2025+2026-prelock mean DK minus league-conditional mean at its own points allowed). '
                           'Declared for this evaluation; no coefficient fitted; SE is roughly the residual SE'),
            'club_residual': round(resid, 3), 'benchmark_mean': round(bench, 3), 'approx_se': form[k]['se'],
            'abs_gap_incumbent': round(abs(dst[k]['inc']['mean'] - bench), 3), 'abs_gap_repaired': round(abs(dst[k]['rep_qb']['mean'] - bench), 3)}
    # ---- game outcomes
    games = {}
    for a in ARMS:
        wp = np.asarray(docs[a]['world_points']['points'], float)
        games[a] = club_points_stats(wp)
        if a != 'inc':
            ev = docs[a]['scoring_events']
            ok = True; worst = 0.0
            for col, c in ((0, home), (1, away)):
                e = {f: np.asarray(v, float) for f, v in ev[c].items()}
                s = 6 * (e['off_td'] + e['def_td']) + e['xp_made'] + 2 * e['tp_made'] + 3 * e['fg_made'] + 2 * e['safety']
                worst = max(worst, float(np.max(np.abs(wp[:, col] - s))))
            games[a]['points_eq_event_sum_max_abs_gap'] = worst
        if a == 'inc':
            games[a]['corr_with_drawn'] = 1.0
        else:
            w0 = np.asarray(docs['inc']['world_points']['points'], float)
            games[a]['corr_total_with_incumbent_drawn_total'] = round(float(np.corrcoef(wp.sum(1), w0.sum(1))[0, 1]), 4)
            games[a]['corr_margin_with_incumbent_drawn_margin'] = round(float(np.corrcoef(wp[:, 0] - wp[:, 1], w0[:, 0] - w0[:, 1])[0, 1]), 4)
            games[a]['mean_shift_total_vs_incumbent'] = round(float(wp.sum(1).mean() - w0.sum(1).mean()), 3)
    games['actual'] = act_doc['final_score']
    result['slates'][tag] = {'inputs': {a: {'path': rel(cfg[a]), 'sha256': sha(cfg[a])} for a in ARMS} |
                             {'actuals': {'path': cfg['act_src'], 'sha256': sha(cfg['act'])}, 'projection': {'path': rel(cfg['proj']), 'sha256': sha(cfg['proj'])}},
                             'n_worlds': n_w, 'home': home, 'away': away, 'calibration': cal, 'mean_drift': drift, 'dst': dst,
                             'dst_club_form_history': form, 'game_outcomes': games}
# pooled
act_pool = [r for r in pooled_rows if r['inc']['mean'] >= 1.0]
skill_pool = [r for r in act_pool if r['pos'] in ('QB', 'RB', 'WR', 'TE')]
dstk_pool = [r for r in pooled_rows if r['pos'] in ('DST', 'K')]
pool = {}
for popname, pop in (('ALL_DRAWN', pooled_rows), ('INC_MEAN_GE_1', act_pool), ('SKILL_INC_MEAN_GE_1', skill_pool), ('DST_AND_K', dstk_pool)):
    pool[popname] = {a: summarise(pop, a) for a in ARMS}
    for b in ('rep_qb', 'rep_rec'):
        per_game = {}
        for tag in SLATES:
            pr = [r for r in pop if r['slate'] == tag]
            per_game[tag] = round(float(np.mean([r[b]['crps'] - r['inc']['crps'] for r in pr])), 4)
        pool[popname][f'paired_crps_{b}_minus_inc'] = {'per_game_mean_diff': per_game,
            'pooled_mean_diff': round(float(np.mean([r[b]['crps'] - r['inc']['crps'] for r in pop])), 4),
            'n_games': len(SLATES), 'CLUSTER_NOTE': 'two game clusters: a cluster bootstrap over 2 games has 3 distinct resamples and is not reported; per-game values are the evidence'}
pool['by_position'] = {}
for p in sorted({r['pos'] for r in pooled_rows}):
    pr = [r for r in pooled_rows if r['pos'] == p]
    pool['by_position'][p] = {'n': len(pr), **{a: {'mean_error': round(float(np.mean([r[a]['err'] for r in pr])), 4),
                                                   'mean_crps': round(float(np.mean([r[a]['crps'] for r in pr])), 4)} for a in ARMS}}
result['pooled'] = pool
pathlib.Path(sys.argv[1]).write_text(json.dumps(result, indent=1, default=str))
print('written')
