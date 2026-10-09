"""Read-only Week 5 Classic world-correctness audit. Writes only into this scratchpad directory."""
import json, math, pathlib, collections
import numpy as np

D = pathlib.Path('/home/user/nfl/nfl/dfs/salaries/runs/w5_final/RESEARCH_STATE_2026W5')
OUT = pathlib.Path(__file__).resolve().parent
proj = json.loads((D / 'PROJ.json').read_text())
state = json.loads((D / 'STATE.json').read_text())
role = json.loads((D / 'ROLE_STATE.json').read_text())
draws_doc = json.loads((D / 'DRAWS.json').read_text())
z = np.load(D / 'WORLDS.npz', allow_pickle=False)
meta = json.loads(bytes(z['meta']).decode())
S = z['stats'].astype('float64')
F = {f: i for i, f in enumerate(meta['fields'])}
for f in meta['yard_fields']:
    S[:, :, F[f]] /= meta['yard_scale']
PTS = z['points'].astype('float64')
keys = meta['keys']
kidx = {k: i for i, k in enumerate(keys)}
clubk = np.array([k.rsplit('|', 1)[1] for k in keys])
NW = S.shape[1]
DR = draws_doc['draws']
rows = {f"{r['name']}|{r['team']}": r for r in proj['rows'].values()}
splay = {f"{p['name']}|{p['team']}": p for p in state['players'].values()}
res = {'ARTIFACT': 'WEEK5_WORLD_CORRECTNESS_AUDIT', 'inputs': str(D), 'n_worlds': NW,
       'input_sha256_match': {'projection_sha256_in_draws': draws_doc['projection_sha256'],
                              'state_sha256_in_draws': draws_doc['state_sha256']}}

# ---------------- 1. projection vs simulated mean; participation ----------------
def pplays(r):
    """P(plays) on the player's own primary field: pass_attempts for a QB, else the larger of targets/carries.
    (Skill players carry pass_attempts=1.0 as a placeholder, so a max over all fields would read 1.0.)"""
    pb = r.get('p_plays_by_field') or {}
    if r.get('position') == 'QB':
        v = pb.get('pass_attempts')
        return v if isinstance(v, (int, float)) else None
    vals = [pb.get(f) for f in ('targets', 'carries') if isinstance(pb.get(f), (int, float))]
    return max(vals) if vals else None

per = []
for k, v in DR.items():
    a = np.asarray(v, float)
    r = rows.get(k)
    if r is None:
        per.append({'key': k, 'error': 'NO_PROJECTION_ROW'}); continue
    m, sd = a.mean(), a.std(ddof=1)
    se = sd / math.sqrt(len(a))
    pj = r['dk_points']; ip = r.get('dk_points_if_plays')
    gap = m - pj
    rec = {'key': k, 'pos': r['position'], 'proj_dk_uncond': round(pj, 3), 'dk_if_plays': ip,
           'sim_mean': round(m, 3), 'mc_se': round(se, 3), 'gap_sim_minus_proj': round(gap, 3),
           'gap_in_se': round(gap / se, 2) if se > 1e-6 else None,
           'p_plays_max_field': pplays(r), 'p_plays_by_field': r.get('p_plays_by_field'),
           'ratio_uncond_over_if_plays': round(pj / ip, 4) if ip else None,
           'nan_cells': int(np.isnan(a).sum()), 'min_dk': round(float(np.nanmin(a)), 2)}
    rec['flag_gap'] = bool(abs(gap) > 0.5 or (se > 1e-6 and abs(gap) > 3 * se))
    if k in kidx:
        s = S[kidx[k]]
        opp = s[:, [F['pass_att'], F['carries'], F['targets']]].sum(1)
        rec['share_zero_opportunity_worlds'] = round(float((opp == 0).mean()), 4)
        rec['share_all_zero_statline'] = round(float((np.abs(s).sum(1) == 0).mean()), 4)
        rec['share_dk_exact_zero'] = round(float((a == 0).mean()), 4)
        pp = rec['p_plays_max_field']
        rec['one_minus_p_plays'] = round(1 - pp, 4) if pp is not None else None
        # mean conditional on having >=1 opportunity, vs dk_if_plays
        if (opp > 0).sum() >= 50:
            rec['sim_mean_given_opportunity'] = round(float(a[opp > 0].mean()), 3)
        obs = (splay.get(k) or {}).get('observed_2026') or {}
        rec['observed_weeks_played_2026'] = obs.get('weeks_played')
    per.append(rec)
res['players'] = per
skill = [p for p in per if p.get('pos') != 'DST' and 'error' not in p]
flags = [p for p in per if p.get('flag_gap')]
# participation: is there an explicit appearance (zero-participation) process?
pp_lt1 = [p for p in skill if p['p_plays_max_field'] is not None and p['p_plays_max_field'] < 0.999]
part = []
for p in pp_lt1:
    part.append({k: p.get(k) for k in ('key', 'pos', 'p_plays_max_field', 'one_minus_p_plays',
                                       'share_zero_opportunity_worlds', 'share_dk_exact_zero',
                                       'proj_dk_uncond', 'dk_if_plays', 'sim_mean', 'sim_mean_given_opportunity',
                                       'observed_weeks_played_2026')})
part.sort(key=lambda x: -(x['dk_if_plays'] or 0))
zero_excess = [x['share_zero_opportunity_worlds'] - x['one_minus_p_plays'] for x in part]
res['section1'] = {
    'n_players': len(per), 'n_skill': len(skill),
    'n_flag_gap_gt_0p5_or_3se': len(flags),
    'n_flag_gap_gt_0p5': sum(abs(p['gap_sim_minus_proj']) > 0.5 for p in per if 'error' not in p),
    'n_flag_gap_gt_3se': sum(p['gap_in_se'] is not None and abs(p['gap_in_se']) > 3 for p in per if 'error' not in p),
    'flagged': sorted([{k: p[k] for k in ('key', 'pos', 'proj_dk_uncond', 'dk_if_plays', 'sim_mean', 'mc_se',
                                           'gap_sim_minus_proj', 'gap_in_se')} for p in flags],
                      key=lambda x: -abs(x['gap_sim_minus_proj'])),
    'max_abs_gap': max(abs(p['gap_sim_minus_proj']) for p in per if 'error' not in p),
    'mean_gap_skill': round(float(np.mean([p['gap_sim_minus_proj'] for p in skill])), 4),
    'n_p_plays_lt_1': len(pp_lt1),
    'participation_rows_p_plays_lt_1': part,
    'zero_opportunity_share_minus_one_minus_p_plays': {
        'mean': round(float(np.mean(zero_excess)), 4) if zero_excess else None,
        'min': round(float(np.min(zero_excess)), 4) if zero_excess else None,
        'max': round(float(np.max(zero_excess)), 4) if zero_excess else None},
    'starters_p_plays_1_any_zero_worlds': sorted(
        [{'key': p['key'], 'share_zero_opportunity_worlds': p['share_zero_opportunity_worlds']}
         for p in skill if p['p_plays_max_field'] and p['p_plays_max_field'] >= 0.999
         and p['share_zero_opportunity_worlds'] > 0 and p['proj_dk_uncond'] >= 8],
        key=lambda x: -x['share_zero_opportunity_worlds'])[:20],
}

# ---------------- 2. world accounting ----------------
acc = {}
games = meta['games']
dst_key = {k.rsplit('|', 1)[1]: k for k in DR if k.split('|')[0].endswith('DST')}
for gi, g in enumerate(games):
    for c, opp, col in ((g['home'], g['away'], 0), (g['away'], g['home'], 1)):
        m = clubk == c
        Sc = S[m]
        py = Sc[:, :, F['pass_yards']].sum(0); ry = Sc[:, :, F['rec_yards']].sum(0)
        d = ry - py
        tol = 0.05 * m.sum()
        ptd = Sc[:, :, F['pass_td']].sum(0); rtd_rec = Sc[:, :, F['rec_td']].sum(0)
        rushtd = Sc[:, :, F['rush_td']].sum(0)
        rec_gt_tgt = (Sc[:, :, F['receptions']] > Sc[:, :, F['targets']]).any(0)
        yds_nocatch_cells = ((np.abs(Sc[:, :, F['rec_yards']]) > 0.05) & (Sc[:, :, F['receptions']] == 0))
        rtd_nocatch = (Sc[:, :, F['rec_td']] > 0) & (Sc[:, :, F['receptions']] == 0)
        rushtd_gt_car = (Sc[:, :, F['rush_td']] > Sc[:, :, F['carries']])
        tgt_gt_att = Sc[:, :, F['targets']].sum(0) > Sc[:, :, F['pass_att']].sum(0)
        pts = PTS[gi, :, col]
        otd = ptd + rushtd
        ints = Sc[:, :, F['interceptions']].sum(0)
        rec = {
            'opponent': opp,
            'REC_YDS_EQ_PASS_YDS_viol_worlds': int((np.abs(d) > tol).sum()),
            'rec_minus_pass_yards_mean': round(float(d.mean()), 2),
            'rec_minus_pass_yards_p05_p95': [round(float(np.percentile(d, 5)), 1), round(float(np.percentile(d, 95)), 1)],
            'qb_pass_yards_mean': round(float(py.mean()), 1), 'club_rec_yards_mean': round(float(ry.mean()), 1),
            'PASS_TD_EQ_REC_TD_viol_worlds': int((ptd != rtd_rec).sum()),
            'REC_LE_TARGETS_viol_worlds': int(rec_gt_tgt.sum()),
            'TARGETS_LE_ATTEMPTS_viol_worlds': int(tgt_gt_att.sum()),
            'REC_YDS_WITHOUT_RECEPTION_viol_worlds': int(yds_nocatch_cells.any(0).sum()),
            'REC_YDS_WITHOUT_RECEPTION_player_cells': int(yds_nocatch_cells.sum()),
            'REC_TD_WITHOUT_RECEPTION_viol_worlds': int(rtd_nocatch.any(0).sum()),
            'REC_TD_WITHOUT_RECEPTION_player_cells': int(rtd_nocatch.sum()),
            'RUSH_TD_LE_CARRIES_viol_worlds': int(rushtd_gt_car.any(0).sum()),
            'RUSH_TD_LE_CARRIES_player_cells': int(rushtd_gt_car.sum()),
            'POINTS_GE_6xOFF_TD_viol_worlds': int((pts + 1e-9 < 6 * otd).sum()),
            'points_minus_6xTD_min': round(float((pts - 6 * otd).min()), 2),
            'club_points_noninteger_share': round(float((np.abs(pts - np.rint(pts)) > 1e-6).mean()), 4),
            'club_points_mean': round(float(pts.mean()), 2),
            'impossible_point_totals_1_share': round(float((np.rint(pts) == 1).mean()), 4),
            'club_ints_thrown_mean': round(float(ints.mean()), 3),
        }
        dk = dst_key.get(opp)
        if dk:
            dd = np.asarray(DR[dk], float)
            rec['opp_dst'] = dk
            # DK DST floor given k INTs: sacks/FR/TD >= 0, PA bucket >= -4 => DST >= 2k - 4 (before any scaling)
            rec['INT_VS_OPP_DST_floor_viol_worlds'] = int((dd + 1e-9 < 2 * ints - 4).sum())
            rec['corr_opp_dst_dk_with_ints_thrown'] = round(float(np.corrcoef(dd, ints)[0, 1]), 3) if ints.std() > 0 else None
            rec['corr_opp_dst_dk_with_club_points'] = round(float(np.corrcoef(dd, pts)[0, 1]), 3)
        acc[c] = rec
tot = collections.Counter()
for c, r in acc.items():
    for k, v in r.items():
        if k.endswith('_viol_worlds'):
            tot[k] += v
res['section2_accounting_by_club'] = acc
res['section2_totals_club_worlds'] = {'of_club_worlds': 16 * NW, **dict(tot)}
ties = {g['game_id']: round(float((np.rint(PTS[i, :, 0]) == np.rint(PTS[i, :, 1])).mean()), 4) for i, g in enumerate(games)}
res['section2_game_tie_share'] = ties
res['section2_checker_note'] = ('nfl/tools/world_accounting_check.py globs *_WORLDS.npz/*_DRAWS.json; run read-only via '
                                'symlinks with those names (checker_raw.json). DRAWS.json carries no dst_components, so '
                                'the checker skips INT_LE_OPP_TAKEAWAYS; replaced here by a DK-floor and a correlation test.')

# ---------------- 3. DST and K ----------------
dst = {}
for c, k in sorted(dst_key.items()):
    a = np.asarray(DR[k], float)
    nonint = np.abs(a - np.rint(a)) > 1e-6
    dst[k] = {'proj': rows[k]['dk_points'], 'sim_mean': round(float(a.mean()), 3),
              'noninteger_share': round(float(nonint.mean()), 4),
              'min': round(float(a.min()), 2), 'p05': round(float(np.percentile(a, 5)), 2),
              'p50': round(float(np.percentile(a, 50)), 2), 'p95': round(float(np.percentile(a, 95)), 2),
              'max': round(float(a.max()), 2), 'sd': round(float(a.std(ddof=1)), 3),
              'below_minus4_share': round(float((a < -4 - 1e-9).mean()), 4),
              'anchor_factor': draws_doc['player_mean_anchor']['dst_multiplicative']['factors'][k]['factor'],
              'n_distinct_values': int(len(np.unique(np.round(a, 4))))}
allst = np.concatenate([np.asarray(DR[k], float) for k in dst_key.values()])
res['section3_dst'] = {'by_unit': dst,
                       'pooled_noninteger_share': round(float((np.abs(allst - np.rint(allst)) > 1e-6).mean()), 4),
                       'pooled_min': round(float(allst.min()), 2), 'pooled_max': round(float(allst.max()), 2),
                       'DK_DST_RULE': 'DK DST scoring is integer-valued (sack 1, INT 2, FR 2, TD 6, safety 2, block 2, PA buckets 10/7/4/1/0/-1/-4); floor -4 absent negative-yardage rules',
                       'anchor': 'DST draws are multiplied by target/raw_mean (classic_slate_run.anchor_means); any factor != 1 makes integer draws non-integer and scales the PA penalty too'}
pos = collections.Counter(r['position'] for r in rows.values())
res['section3_kicker'] = {'K_rows_in_projection': pos.get('K', 0), 'positions_present': dict(pos),
                          'finding': 'NO KICKER OUTPUT EXISTS: DraftKings NFL Classic has no K slot and the universe carries none; field goals are not represented as events, club points are a continuous centred draw'}
neg = []
for p in skill:
    a = np.asarray(DR[p['key']], float)
    s = S[kidx[p['key']]]
    ints = s[:, F['interceptions']]
    # floor from DK rules given this stat line: -ints, negative rush/rec yards; fumbles are NOT modelled
    if (a < -1e-9).any():
        neg.append({'key': p['key'], 'n_negative_worlds': int((a < -1e-9).sum()), 'min': round(float(a.min()), 2),
                    'negative_explained_by_ints_or_neg_yards': bool(np.all(
                        (ints[a < 0] > 0) | (s[a < 0, F['rush_yards']] < 0) | (s[a < 0, F['rec_yards']] < 0)))})
res['section3_impossible_values'] = {
    'nan_cells_total': int(sum(p['nan_cells'] for p in per if 'error' not in p)),
    'skill_players_with_negative_worlds': len(neg),
    'all_negatives_explained': all(x['negative_explained_by_ints_or_neg_yards'] for x in neg),
    'negatives': sorted(neg, key=lambda x: x['min'])[:15],
    'fumbles_modelled': False,
    'fumbles_note': 'proj dk_line_items and classic_slate_run.dk_from_stats carry no fumble_lost term although CONSTANTS_PROVENANCE.DK lists fumble_lost -1; every skill player mean omits fumbles',
    'skill_noninteger_receptions_or_tds': int(sum(int((np.abs(S[:, :, F[f]] - np.rint(S[:, :, F[f]])) > 1e-9).sum())
                                                  for f in ('receptions', 'targets', 'carries', 'rec_td', 'rush_td', 'pass_td', 'pass_att'))),
    'max_receptions': int(S[:, :, F['receptions']].max()), 'max_rec_yards': float(S[:, :, F['rec_yards']].max()),
    'max_rush_yards': float(S[:, :, F['rush_yards']].max()), 'max_pass_yards': float(S[:, :, F['pass_yards']].max()),
    'min_rush_yards': float(S[:, :, F['rush_yards']].min()), 'min_rec_yards': float(S[:, :, F['rec_yards']].min()),
}

# ---------------- 4. distributions, top 40 skill ----------------
dud = json.loads(pathlib.Path('/home/user/nfl/nfl/research/tail_calibration/STAR_DUD_RATE_2021_2025.json').read_text())['empirical']
def emp(mean, pos):
    b = '20-1e+09' if mean >= 20 else '15-20' if mean >= 15 else '10-15' if mean >= 10 else None
    if b is None:
        return None, None
    k = f'{b}|{pos}' if f'{b}|{pos}' in dud else f'{b}|ALL'
    return k, dud[k]
top = sorted(skill, key=lambda p: -p['proj_dk_uncond'])[:40]
dist = []
for p in top:
    a = np.asarray(DR[p['key']], float)
    q = np.percentile(a, [10, 50, 90])
    plt5 = float((a < 5).mean())
    se = math.sqrt(plt5 * (1 - plt5) / len(a)) if 0 < plt5 < 1 else math.sqrt(0.25 / len(a)) * 0  # binomial
    ek, e = emp(p['proj_dk_uncond'], p['pos'])
    rec = {'key': p['key'], 'pos': p['pos'], 'proj': p['proj_dk_uncond'], 'sim_mean': p['sim_mean'],
           'p10': round(q[0], 2), 'p50': round(q[1], 2), 'p90': round(q[2], 2), 'sd': round(float(a.std(ddof=1)), 2),
           'cv': round(float(a.std(ddof=1) / a.mean()), 3), 'P_dk_lt5': round(plt5, 4),
           'P_dk_lt_quarter_mean': round(float((a < 0.25 * a.mean()).mean()), 4),
           'empirical_bin': ek, 'empirical_p_lt5': e['p_lt5'] if e else None,
           'empirical_p_lt5_ci95': e['p_lt5_cluster_boot_95'] if e else None,
           'empirical_p_lt_quarter_mean': e['p_lt_quarter_mean'] if e else None}
    if e:
        rec['shortfall_pp'] = round(100 * (e['p_lt5'] - plt5), 2)
        rec['ratio_empirical_over_sim'] = round(e['p_lt5'] / plt5, 2) if plt5 > 0 else 'INF (0 sim worlds < 5)'
        rec['sim_below_empirical_ci_lower'] = plt5 < e['p_lt5_cluster_boot_95'][0]
    dist.append(rec)
stars = [r for r in dist if r['proj'] >= 20]
star_wr = [r for r in stars if r['pos'] == 'WR']
b1520 = [r for r in dist if 15 <= r['proj'] < 20]
res['section4_distributions_top40'] = dist
res['section4_summary'] = {
    'reference': 'nfl/research/tail_calibration/STAR_DUD_RATE_2021_2025.json empirical["20-1e+09|WR"].p_lt5 = 0.0657 (n=350 games, 70 player-seasons, cluster-boot 95% [0.0401, 0.0949]); 20+|ALL 0.0492; bins are on realised season ppg, here applied to projected mean (proxy)',
    'n_proj_ge20': len(stars), 'stars': [(r['key'], r['proj'], r['P_dk_lt5']) for r in stars],
    'mean_sim_P_lt5_proj_ge20': round(float(np.mean([r['P_dk_lt5'] for r in stars])), 4) if stars else None,
    'mean_sim_P_lt5_proj_15_20': round(float(np.mean([r['P_dk_lt5'] for r in b1520])), 4) if b1520 else None,
    'mean_empirical_P_lt5_proj_15_20_bins': round(float(np.mean([r['empirical_p_lt5'] for r in b1520])), 4) if b1520 else None,
    'n_top40_below_empirical_ci_lower': sum(1 for r in dist if r.get('sim_below_empirical_ci_lower')),
    'n_top40_with_empirical_bin': sum(1 for r in dist if r.get('empirical_bin')),
    'shortfall_vs_6p6pct_for_wr_ge20_pp': [(r['key'], round(6.57 - 100 * r['P_dk_lt5'], 2)) for r in star_wr],
}

# ---------------- 5. inputs for optimizer-effect section ----------------
eff = draws_doc['player_mean_anchor']['efficiency']['factors']
def club_players(c, posset=('WR', 'TE', 'RB')):
    return sorted([p for p in skill if p['key'].endswith('|' + c) and p['pos'] in posset],
                  key=lambda p: -p['proj_dk_uncond'])
qbinfo = {}
for c in ('CHI', 'WAS'):
    qbs = sorted([p for p in skill if p['key'].endswith('|' + c) and p['pos'] == 'QB'], key=lambda p: -p['proj_dk_uncond'])
    qbinfo[c] = {'qbs': [(p['key'], p['proj_dk_uncond'], p['dk_if_plays'], p['p_plays_max_field']) for p in qbs],
                 'top_receivers': [(p['key'], p['proj_dk_uncond']) for p in club_players(c)[:6]]}
    # correlation of top receivers with QB1 DK in the worlds
    q1 = np.asarray(DR[qbs[0]['key']], float)
    qbinfo[c]['corr_with_qb1'] = {p['key']: round(float(np.corrcoef(q1, np.asarray(DR[p['key']], float))[0, 1]), 3)
                                  for p in club_players(c)[:5]}
res['section5_inputs'] = {
    'qb_identity_clubs': qbinfo,
    'club_receiving_inflation_vs_qb_yards': sorted([(c, r['rec_minus_pass_yards_mean']) for c, r in acc.items()],
                                                  key=lambda x: -abs(x[1])),
    'largest_rec_yard_factors': sorted([(k, v['rec_yards']) for k, v in eff.items() if v['rec_yards'] != 1.0],
                                       key=lambda x: -abs(math.log(x[1])))[:15],
    'residual_gap_abs_max_after_efficiency': draws_doc['player_mean_anchor'].get('residual_gap_abs_max'),
}
# W5-G16 most affected: low p_plays yet played every week
g16 = [x for x in part if (x['observed_weeks_played_2026'] or 0) >= 3 and x['p_plays_max_field'] < 0.8]
g16.sort(key=lambda x: -((x['dk_if_plays'] or 0) * (1 - x['p_plays_max_field'])))
res['section5_inputs']['W5_G16_backups_played_3plus_weeks_p_plays_lt_0p8'] = g16[:15]

(OUT / 'WEEK5_WORLD_CORRECTNESS_AUDIT.raw.json').write_text(json.dumps(res, indent=1, default=float))
print(json.dumps({k: res[k] for k in ('section1',)}, default=float)[:6000])
