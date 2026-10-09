"""Compose INTEGRATION_EVALUATION_2026-10-09.{json,md} from the measurement files in EVAL_WORK.
Numbers are read from the measurement JSONs, never retyped; verdict text is the evaluator's judgement and says so."""
import json, os, pathlib, subprocess, sys, platform
REPO = pathlib.Path(__file__).resolve().parents[4]
W = pathlib.Path(os.environ['EVAL_WORK'])
OUT = REPO / 'nfl/research/accounting_repair'
M = json.loads((W / 'MEASUREMENTS.json').read_text())
DS = json.loads((W / 'DISPERSION.json').read_text())
L = json.loads((W / 'LINEUPS.json').read_text())
BUILD_LOGS = {k: (W.parent / f'log_pf_{k}.txt') for k in ('control', 'repaired', 'hybrid')}
git = lambda *a: subprocess.run(['git', *a], cwd=REPO, capture_output=True, text=True).stdout.strip()
P = M['pooled']; S = M['slates']; T, A = S['TB_DAL_2026W5'], S['ATL_NO_2026W4']
pop = lambda s, p, a: s['calibration']['populations'][p][a]
def cal_row(src, p, a):
    v = src[p][a] if 'calibration' not in src else pop(src, p, a)
    return {k: v[k] for k in ('n', 'mean_crps', 'mean_error', 'coverage_50', 'coverage_80', 'coverage_90', 'pit_mean', 'pit_deciles')}
calib = {}
for name, src in (('TB_DAL_2026W5', T), ('ATL_NO_2026W4', A), ('POOLED', P)):
    calib[name] = {}
    for p in ('ALL_DRAWN', 'INC_MEAN_GE_1', 'SKILL_INC_MEAN_GE_1', 'DST_AND_K'):
        calib[name][p] = {a: cal_row(src, p, a) for a in ('inc', 'rep_qb', 'rep_rec')}
        k = src[p] if name == 'POOLED' else src['calibration']['populations'][p]
        calib[name][p]['paired_crps_rep_qb_minus_inc'] = k['paired_crps_rep_qb_minus_inc']
        calib[name][p]['paired_crps_rep_rec_minus_inc'] = k['paired_crps_rep_rec_minus_inc']
calib['POOLED_BY_POSITION'] = P['by_position']
disp = DS['summary']
drift = {t: {a: {'by_position': s['mean_drift'][a]['by_position'], 'n_players': s['mean_drift'][a]['n_players'],
                 'n_abs_drift_gt_2_paired_se': s['mean_drift'][a]['n_abs_drift_gt_2se'],
                 'n_abs_drift_gt_0p5_dk': s['mean_drift'][a]['n_abs_drift_gt_0p5_dk'],
                 'top8': s['mean_drift'][a]['players'][:8]} for a in ('rep_qb', 'rep_rec')} for t, s in S.items()}
dst = {t: {k: {'projection_dk': v['projection_dk'], 'actual_dk_HINDSIGHT': v['actual_dk'],
               'projection_event_items': v['projection_event_items'],
               **{a: {kk: v[a][kk] for kk in ('mean', 'sd', 'p5', 'p50', 'p95', 'share_non_integer',
                                                'share_dk_ne_own_components_and_points_allowed', 'points_allowed_mean',
                                                'history_conditional_mean_given_this_arms_points_allowed', 'history_resampled',
                                                'ks_vs_history_resampled', 'component_means')} for a in ('inc', 'rep_qb')},
               'club_form_history': s['dst_club_form_history'][k]} for k, v in s['dst'].items()} for t, s in S.items()}
games = {t: s['game_outcomes'] for t, s in S.items()}
lu = L['contests']
logs = {k: (p.read_text().strip().splitlines()[-1] if p.exists() else None) for k, p in BUILD_LOGS.items()}
c = lambda t, d, a: dst[t][d]['club_form_history']['CLUB_ADJUSTED_BENCHMARK']
verd = {
 'a_distributional_calibration': {
   'verdict': 'DAMAGE_DETECTED',
   'basis': 'historical dispersion benchmark (receivers); the outcome-based comparison has no power and detects nothing either way',
   'measured': {
     'outcome_based_pooled_inc_mean_ge_1': calib['POOLED']['INC_MEAN_GE_1'],
     'outcome_based_pooled_skill': calib['POOLED']['SKILL_INC_MEAN_GE_1'],
     'outcome_based_pooled_dst_and_k': calib['POOLED']['DST_AND_K'],
     'receiver_dk_sd_over_history_within_player_season_sd_matched_mean': {a: disp[f'REC:{a}'] for a in ('inc', 'rep_qb', 'rep_rec')},
     'rb_dk_sd_over_history': {a: disp[f'RB:{a}'] for a in ('inc', 'rep_qb', 'rep_rec')},
     'qb_dk_sd_over_history': {a: disp[f'QB:{a}'] for a in ('inc', 'rep_qb', 'rep_rec')},
     'receiver_corr_receptions_rec_yards_minus_history': {a: disp[f'REC:{a}:cy'] for a in ('inc', 'rep_qb', 'rep_rec')},
     'receiver_corr_receptions_rec_td_minus_history': {a: disp[f'REC:{a}:ct'] for a in ('inc', 'rep_qb', 'rep_rec')},
     'history_bins': DS['history_bins'], 'benchmark_note': DS['NOTE']},
   'reading': ('Outcome-based: n = 79 player-games from 2 games (44 with incumbent mean >= 1 DK). Central-interval coverage rises '
               'under the repair and CRPS is worse in both games overall, better in both games for skill players and worse in both '
               'for DST (4 DST-games). With two game clusters none of this separates from noise; nothing here may be read as '
               '"calibrated". Against history: every skill player\'s DK distribution is wider in the repaired arm, and for receivers '
               'the repaired SD exceeds the historical within-player-season SD at matched mean -- itself an UPPER benchmark for a '
               'conditional single-game SD -- in most cases, where the incumbent sat below it. The repair also moves the '
               'receptions-yards and receptions-TD correlations most of the way to their historical values. Coherence improved; '
               'receiver dispersion now looks too wide.')},
 'b_projection_means': {
   'verdict': 'DAMAGE_DETECTED',
   'basis': 'paired mean drift on identical raw worlds; skill-player means are not preserved',
   'measured': drift,
   'reading': ('Skill-player means move by up to about 2 DK per player, and which players move depends on the declared passing '
               'anchor: the projection does not close its own club passing game (QB yards vs the receivers\' sum), so one side '
               'must move under either anchor. Rushing TDs the raw simulator had dropped into its unallocated bucket are now on '
               'player lines, raising RB/WR means. These are real changes to downstream projections that no outcome data here '
               'can adjudicate. The DST drift is the exception: see the DST section, where the incumbent is the defect.')},
 'c_lineup_selection': {
   'verdict': 'NOT_MEASURABLE',
   'basis': 'one game; lineup quality cannot be measured. The CHANGE is measured and is large',
   'measured': {'control_rebuild_on_incumbent_draws_byte_identical_to_R1': L['control_rebuild_on_incumbent_draws_byte_identical_to_R1'],
                'contests': lu, 'build_log_last_lines': logs},
   'reading': ('Harness validated: the incumbent draws rebuild R1 byte for byte. On repaired worlds only a small share of R1 lineups '
               'survive; DAL DST exposure is the largest single change. A diagnostic build with the incumbent DST draws restored '
               'still replaces most R1 lineups, so the skill-world changes alone move the portfolio; no seed-only overlap baseline '
               'was measured, so the replacement share cannot be judged against selection noise. Each portfolio scores better on '
               'its own worlds, as an optimiser must. Realised totals are one game, hindsight only.')},
 'd_valid_game_outcomes': {
   'verdict': 'DAMAGE_DETECTED',
   'basis': 'world-level club scores vs 2021-2025 regular-season final scores (pbp)',
   'measured': {'slates': games, 'history_2021_2025_REG': M['history']['games']},
   'reading': ('Impossible scores are eliminated: the incumbent\'s club scores are non-integers in ~98% of club-worlds and fall '
               'strictly between 0 and 2 in 0.6-1.6%; the repaired arm has none, and its points equal the event sums exactly '
               '(max gap 0.0) on both slates. But the repair introduces ties at 1.8% and 3.7% of worlds against 0.29% of historical '
               'final scores (overtime is not represented), still under-produces 3- and 7-point margins (8-11% vs 22.4%), and raises '
               'total-points dispersion relative to the drawn total. Ties do not score in DK, so the DFS cost is small; as a '
               'game-outcome model it is a defect.')},
}
dst_verdict = {
  'question': 'which arm\'s DST distribution is closer to history',
  'answer': 'REPAIRED (both anchors share DST draws)',
  'measured': dst,
  'history_dst_2021_2025': M['history']['dst'],
  'reading': ('Historical DK DST scores are integers in 100% of 2,718 club-games; the incumbent\'s DST draws are non-integers in '
              '92-98% of worlds because a multiplicative anchor (TB@DAL: DAL x0.5085, TB x1.1867, from the original report) rescales DK '
              'points after scoring. Conditioned on each arm\'s own points-allowed draws, the repaired DST distribution matches the '
              'history-resampled one (KS 0.015-0.048) where the incumbent does not (0.09-0.37); that part is close to true by '
              'construction, since the simulator\'s DST tuples are resampled history, and the club-adjusted benchmark below is '
              'league-conditional plus a club residual, so the repaired arm\'s gap to it is just that residual. The non-circular '
              'content is the size of the club residual: measured on each club\'s own 2025 + 2026 pre-lock games it is '
              + ', '.join(f"{k.split('|')[1]} {v['club_form_history']['CLUB_ADJUSTED_BENCHMARK']['club_residual']:+.2f}" for s_ in dst.values() for k, v in s_.items())
              + ' DK (SE about 1), while the incumbent (= the DST projection) departs from the league-conditional expectation by '
              + ', '.join(f"{k.split('|')[1]} {v['inc']['mean'] - v['rep_qb']['history_conditional_mean_given_this_arms_points_allowed']:+.2f}" for s_ in dst.values() for k, v in s_.items())
              + ' DK. The clubs\' own history does not support departures that large (DAL, NO) or of that sign (ATL, NO). So the incumbent '
              'DST step is the defect. The repaired arm still uses league-average tuples and '
              'drops the club-specific rates the DST projection carries; the right fix is club-adjusted COMPONENT draws, scored '
              'once, not a rescale of DK. The four realised DST scores (1, 7, 4, -3) favour the incumbent\'s lower numbers; n = 4, '
              'hindsight only.')}
defects = [
 {'id': 'ECW-D1', 'what': 'no overtime: event-sum club points tie in 1.8% (TB@DAL) and 3.7% (ATL@NO) of worlds vs 0.29% of 2021-2025 final scores',
  'severity': 'game-outcome validity; small DFS cost'},
 {'id': 'ECW-D2', 'what': 'defensive/return TD and safety points (0.65-0.89 per club-game) are added ON TOP of a drawn remainder the kicker '
  'only partly consumes; club points rise by +0.10 to +0.59 per club vs the drawn total, and total SD rises by 0.5-0.8',
  'severity': 'mean and dispersion of club scoring; feeds DST points allowed'},
 {'id': 'ECW-D3', 'what': 'margins of 3 or 7 occur in 8.3% / 11.0% of worlds vs 22.4% in history: the FG count is a rounded share of a '
  'continuous remainder, not a drive outcome', 'severity': 'game-outcome shape'},
 {'id': 'ECW-D4', 'what': 'receiver DK distributions widen (every skill player, median SD ratio 1.11-1.13) and exceed the historical '
  'within-player SD benchmark for most receivers. Probably partly unmasking, not created: the incumbent\'s near-zero catch-TD '
  'correlation offset the raw simulator\'s wide yards-per-catch (CV, TB@DAL receivers with >2 catches: 0.82 incumbent, 0.72 repaired, '
  '0.53 median in 2021-2025 history)', 'severity': 'calibration risk; blocks promotion until measured on more slates'},
 {'id': 'ECW-D5', 'what': 'DST tuples are drawn in the band of the CONTINUOUS points allowed and scored on the event-sum points; the '
  'band differs in 372-498 of 2,000 worlds per DST', 'severity': 'named by the module; measured here'},
 {'id': 'ECW-D6', 'what': 'DST uses league-average conditional tuples, discarding the club-specific event rates in the DST projection',
  'severity': 'DST mean; needs club-adjusted components'},
 {'id': 'ECW-D7', 'what': 'the club passing anchor is a free choice that moves skill means by up to ~2 DK (London +2.09 under QB anchor, '
  'Penix -2.02 under receiver anchor), because the projection itself does not close the passing game', 'severity': 'owner decision'},
 {'id': 'ECW-D8', 'what': 'the shadow runner does not record whether a point-in-time manifest was active. ATL@NO reproduces only under '
  'NFL_PIT_MANIFEST (without it the kickers differ by up to 8 DK and the runner refuses); the repaired arm\'s kicker inputs '
  'come from whatever data is live', 'severity': 'provenance; fail-closed today via the reproduction check'},
]
slates = {
 'evaluated': {
  'TB_DAL_2026W5': {'scenario': 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL', 'reproduced': 'max |DK diff| 0.0 over 49 players, live data',
                    'repaired_outputs': 'nfl/research/accounting_repair/TB_DAL_2026W5 (re-run in scratch: byte-identical)',
                    'actuals': 'git show be87cb0d:nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json (player_actuals dk_A)'},
  'ATL_NO_2026W4': {'scenario': 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX (the production upload 8f4d9a77)',
                    'reproduced': ('max |DK diff| 0.0 over 30 players ONLY with NFL_PIT_MANIFEST=nfl/warehouse/pit_manifests/'
                                   'PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json (cutoff 2026-10-05T23:47:26Z). Without it the '
                                   'runner refuses INCUMBENT_NOT_REPRODUCED (max |DK diff| 8.0): both kickers differ, because the live '
                                   'pbp capture 2b3e9f2c holds week 4, the game itself (docs/SHOWDOWN_BASELINE_REPRODUCTION.md F3)'),
                    'repaired_outputs': 'nfl/research/accounting_repair/ATL_NO_2026W4 (two builds byte-identical)',
                    'actuals': 'nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json (player_actuals dk_A; dk_B differs only for Daniel Carlson, 6 vs 5)'}},
 'skipped': {
  'PIT_CLE_2026W4': ('nfl/dfs/salaries/SHOWDOWN_TONIGHT_{PROJ,STATE,DRAWS}.json is an earlier pipeline: the DRAWS carry no tag, '
                     'projection_sha256 or state_sha256 (the runner refuses at its first check), the PROJ has no int_rate (the '
                     'incumbent efficiency step cannot run), and showdown_draws.build on those inputs with the published seed '
                     '20261001 reproduces 0 of 45 players (worst |DK diff| 50.5). No PIT manifest exists for it, and the live pbp '
                     'holds the game. The nfl/research/showdown_live/2026_04_PIT_CLE artifacts are post-kickoff rebuilds '
                     '("sealed after kickoff: DESCRIPTIVE ONLY") with no PROJ/STATE.'),
  'PHI_CHI': 'only DK contest standings exist (nfl/postgame/raw/showdown_history/196036243_PHI_CHI); no frozen pregame projection, state or draws anywhere in the repository.'},
}
unmet = [
 'End-to-end regression via nfl/tests/run_suite.py of every module that consumes worlds (showdown_portfolio, world_accounting_check, '
 'postgame graders, classic_slate_run) with the arm wired in -- NOT RUN here; only nfl/tests/test_event_consistent_worlds.py was run (74 passed).',
 'Classic integration via nfl/tools/classic_slate_run.py -- NOT ATTEMPTED; the arm is Showdown-only.',
 'Owner decision on the club passing anchor (QB vs receiver side), and on whether DST means should follow the DST projection or the simulator events.',
 'Club-adjusted DST component draws (replace the multiplicative DK anchor in BOTH arms) and a re-measurement against history.',
 'Overtime (or an explicit tie-break) in event-sum club points, and a re-check of 3/7 margin frequencies.',
 'Resolve the double-count of defensive/return TD and safety points against the drawn remainder (ECW-D2).',
 'Receiver dispersion re-measured on more slates and against a conditional (not within-season) benchmark (ECW-D4).',
 'A forward-chained, pre-registered evaluation on new slates with point-in-time manifests; two development games cannot establish an improvement.',
 'Runner records the active PIT manifest seal in its report (ECW-D8).',
 'A seed-only lineup-overlap baseline, so a lineup-replacement share can be read against selection noise.',
]
doc = {'ARTIFACT': 'ACCOUNTING_REPAIR_INTEGRATION_EVALUATION', 'date': '2026-10-09', 'SHADOW_ONLY': 'nothing promoted or wired into production',
       'branch': git('rev-parse', '--abbrev-ref', 'HEAD'), 'evaluated_at_commit': git('rev-parse', 'HEAD'),
       'interpreter': f'python{platform.python_version()}', 'n_worlds_per_slate': 2000,
       'POWER': ('two games, 79 player-games (44 with incumbent mean >= 1 DK), 4 DST-games. Development data, exploratory only; per-game '
                 'values are the evidence, and no word like calibrated, unbiased or correct applies'),
       'slates': slates, 'verdicts': verd, 'dst_which_arm_is_closer_to_history': dst_verdict, 'defects_in_the_repair': defects,
       'promotion_requirements_unmet': unmet,
       'calibration_tables': calib,
       'reproduce': {
         'atl_repaired': 'NFL_PIT_MANIFEST=nfl/warehouse/pit_manifests/PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json python3.12 nfl/research/accounting_repair/run_event_consistent_shadow.py nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX nfl/research/accounting_repair/ATL_NO_2026W4',
         'history': 'EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/hist.py <dir>/hist.json',
         'measurements': 'EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/evaluate.py <dir>/MEASUREMENTS.json',
         'dispersion': 'EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/dispersion.py <dir>/DISPERSION.json',
         'portfolios': 'python3.12 nfl/research/accounting_repair/integration_eval/build_portfolio.py <DRAWS.json> <out_dir>   (incumbent / repaired / hybrid DRAWS)',
         'lineups': 'EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/lineups.py <repaired_pf> <control_pf> <dir>/LINEUPS.json <hybrid_pf>',
         'compose': 'EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/compose.py',
         'all with': 'PYTHONPATH=<numpy/pandas site>; never -I'}}
(OUT / 'INTEGRATION_EVALUATION_2026-10-09.json').write_text(json.dumps(doc, indent=1, default=str) + '\n')
print('json written', len(json.dumps(doc)))


# ---------------------------------------------------------------- markdown
def f(x, n=3):
    return '' if x is None else (f'{x:+.{n}f}' if isinstance(x, float) and n < 0 else (f'{x:.{n}f}' if isinstance(x, float) else str(x)))
AR = {'inc': 'incumbent', 'rep_qb': 'repaired, QB anchor', 'rep_rec': 'repaired, receiver anchor'}
md = ['# Accounting repair: integration evaluation, 2026-10-09', '',
      f"SHADOW ONLY. Nothing is promoted or wired into production. Branch `{doc['branch']}`, evaluated at `{doc['evaluated_at_commit'][:8]}`, "
      f"{doc['interpreter']}, 2,000 worlds per slate. Machine-readable twin: `INTEGRATION_EVALUATION_2026-10-09.json`.", '',
      f"**Power.** {doc['POWER']}.", '',
      '## Verdicts', '', '| question | verdict | basis |', '|---|---|---|']
for k, v in verd.items():
    md.append(f"| {k.replace('_', ' ', 1)} | **{v['verdict']}** | {v['basis']} |")
md += ['', f"DST: which arm is closer to history? **{dst_verdict['answer']}**.", '',
       '## Slates', '']
for t_, v in slates['evaluated'].items():
    md.append(f"- **{t_}** evaluated. Scenario `{v['scenario']}`. Reproduction: {v['reproduced']}. Actuals: {v['actuals']}.")
for t_, v in slates['skipped'].items():
    md.append(f"- **{t_}** skipped: {v}")
md += ['', '## (a) Distributional calibration', '', verd['a_distributional_calibration']['reading'], '',
       'Outcome-based, per player DK (FLEX). CRPS is the exact empirical CRPS from the 2,000 draws; PIT is the mid-PIT; coverage uses '
       'empirical central quantiles. Paired differences are repaired minus incumbent on the same players (negative = repaired better).', '',
       '| slate | population | arm | n | mean CRPS | mean error | cov 50 | cov 80 | cov 90 | PIT mean | PIT deciles |', '|---|---|---|---|---|---|---|---|---|---|---|']
for t_ in ('TB_DAL_2026W5', 'ATL_NO_2026W4', 'POOLED'):
    for p_ in ('INC_MEAN_GE_1', 'SKILL_INC_MEAN_GE_1', 'DST_AND_K', 'ALL_DRAWN'):
        for a in ('inc', 'rep_qb', 'rep_rec'):
            r = calib[t_][p_][a]
            md.append(f"| {t_} | {p_} | {AR[a]} | {r['n']} | {r['mean_crps']:.3f} | {r['mean_error']:+.3f} | {r['coverage_50']:.2f} | "
                      f"{r['coverage_80']:.2f} | {r['coverage_90']:.2f} | {r['pit_mean']:.3f} | {' '.join(map(str, r['pit_deciles']))} |")
md += ['', 'Paired CRPS difference, repaired minus incumbent, mean per player:', '',
       '| population | anchor | TB@DAL | ATL@NO | pooled |', '|---|---|---|---|---|']
for p_ in ('INC_MEAN_GE_1', 'SKILL_INC_MEAN_GE_1', 'DST_AND_K', 'ALL_DRAWN'):
    for b, nm in (('rep_qb', 'QB'), ('rep_rec', 'receiver')):
        g = calib['POOLED'][p_][f'paired_crps_{b}_minus_inc']
        md.append(f"| {p_} | {nm} | {g['per_game_mean_diff']['TB_DAL_2026W5']:+.4f} | {g['per_game_mean_diff']['ATL_NO_2026W4']:+.4f} | {g['pooled_mean_diff']:+.4f} |")
md += ['', 'Within one game a player-level bootstrap interval is anti-conservative (players share one game script); the JSON carries it with '
       'that caveat. With two game clusters a cluster bootstrap is meaningless and is not reported.', '',
       'Mean error (simulated mean minus actual) and CRPS by position, pooled:', '', '| pos | n | incumbent err | repaired QB err | incumbent CRPS | repaired QB CRPS |', '|---|---|---|---|---|---|']
for p_, v in calib['POOLED_BY_POSITION'].items():
    md.append(f"| {p_} | {v['n']} | {v['inc']['mean_error']:+.3f} | {v['rep_qb']['mean_error']:+.3f} | {v['inc']['mean_crps']:.3f} | {v['rep_qb']['mean_crps']:.3f} |")
md += ['', 'Against history (2021-2025 `nfl/warehouse/PLAYER_GAME.json`, DK current rules, player-seasons with >= 8 games). ' + DS['NOTE'] + '.', '',
       '| group | arm | n players | median SD / history SD | share above 1 | corr(rec, rec yds) minus history | corr(rec, rec TD) minus history |', '|---|---|---|---|---|---|---|']
for g in ('REC', 'RB', 'QB'):
    for a in ('inc', 'rep_qb', 'rep_rec'):
        s = disp[f'{g}:{a}']; cy = disp.get(f'{g}:{a}:cy'); ct = disp.get(f'{g}:{a}:ct')
        md.append(f"| {g} | {AR[a]} | {s['n_players']} | {s['median']:.3f} | {s['share_above_1']:.2f} | "
                  f"{'' if not cy else format(cy['median'], '+.3f')} | {'' if not ct else format(ct['median'], '+.3f')} |")
md += ['', '## (b) Projection means', '', verd['b_projection_means']['reading'], '',
       '| slate | anchor | players | abs drift > 2 paired SE | abs drift > 0.5 DK | by position: sum of drift (paired SE) |', '|---|---|---|---|---|---|']
for t_, v in drift.items():
    for a, d in v.items():
        bp = '; '.join(f"{p_} {x['sum_drift']:+.2f} ({x['paired_se_of_sum']:.2f})" for p_, x in d['by_position'].items())
        md.append(f"| {t_} | {AR[a]} | {d['n_players']} | {d['n_abs_drift_gt_2_paired_se']} | {d['n_abs_drift_gt_0p5_dk']} | {bp} |")
md += ['', 'Largest per-player drifts (repaired minus incumbent, paired SE):', '']
for t_, v in drift.items():
    for a, d in v.items():
        md.append(f"- {t_}, {AR[a]}: " + ', '.join(f"{x['player']} {x['drift']:+.2f} ({x['paired_se']:.2f})" for x in d['top8'][:6]))
md += ['', '## DST: which arm is the defect', '', dst_verdict['reading'], '',
       'History 2021-2025 REG, all clubs: mean DK DST ' + f"{M['history']['dst']['mean_dk_pa_all']:.2f} (SD {M['history']['dst']['sd']:.2f}), "
       f"integer share {M['history']['dst']['share_integer']:.0%}, n = {M['history']['dst']['n_club_games']}. Scoring: sack 1, INT 2, fumble recovery 2, "
       'safety 2, def/ST TD 6, blocked kick 2, points-allowed bands 0:+10, 1-6:+7, 7-13:+4, 14-20:+1, 21-27:0, 28-34:-1, 35+:-4 (points allowed = opponent '
       'final score; excluding opponent TDs scored against the offence moves the mean by ' + f"{M['history']['dst']['mean_dk_pa_excl_def_td_vs_offence'] - M['history']['dst']['mean_dk_pa_all']:+.2f}).", '',
       '| DST | projection | incumbent mean (SD) | repaired mean (SD) | incumbent non-integer | KS vs history-resampled inc / rep | club-adjusted benchmark (SE) | gap inc / rep | actual (hindsight) |',
       '|---|---|---|---|---|---|---|---|---|']
for t_, v in dst.items():
    for k, x in v.items():
        b = x['club_form_history']['CLUB_ADJUSTED_BENCHMARK']
        md.append(f"| {k} ({t_}) | {x['projection_dk']:.2f} | {x['inc']['mean']:.2f} ({x['inc']['sd']:.2f}) | {x['rep_qb']['mean']:.2f} ({x['rep_qb']['sd']:.2f}) | "
                  f"{x['inc']['share_non_integer']:.0%} | {x['inc']['ks_vs_history_resampled']:.3f} / {x['rep_qb']['ks_vs_history_resampled']:.3f} | "
                  f"{b['benchmark_mean']:.2f} ({b['approx_se']:.2f}) | {b['abs_gap_incumbent']:.2f} / {b['abs_gap_repaired']:.2f} | {x['actual_dk_HINDSIGHT']} |")
md += ['', 'Benchmark definition: ' + next(iter(next(iter(dst.values())).values()))['club_form_history']['CLUB_ADJUSTED_BENCHMARK']['DEFINITION'] + '.', '',
       '## (c) Lineup selection (TB@DAL)', '', verd['c_lineup_selection']['reading'], '',
       f"Control: rebuilding on the incumbent draws reproduces R1 byte for byte: {all(L['control_rebuild_on_incumbent_draws_byte_identical_to_R1'].values())} (7 files).", '',
       '| contest | lineups | R1 lineups kept by the repaired build | kept by the diagnostic build (incumbent DST) | DAL DST exposure R1 -> repaired -> diagnostic |', '|---|---|---|---|---|']
for cid, v in lu.items():
    dx = next((r for r in v['player_exposure_changes_top10'] if r['player'] == 'Cowboys|DAL'), None)
    h = v.get('attribution_hybrid') or {}
    md.append(f"| {cid} | {v['n_R1']} | {v['identical_lineups_shared']} ({v['share_of_R1_kept']:.0%}) | {h.get('hybrid_vs_R1')} | "
              f"{'' if not dx else f'{dx[chr(82)+chr(49)]:.3f} -> {dx[chr(114)+chr(101)+chr(98)+chr(117)+chr(105)+chr(108)+chr(116)]:.3f}'} -> {(h.get('dst_exposure_hybrid') or {}).get('Cowboys|DAL')} |")
md += ['', 'Cross-evaluation, all 190 entries: expected best lineup per world (mean lineup mean), scored on each world set; realised = one game, hindsight:', '',
       '| portfolio | on incumbent worlds | on repaired QB-anchor worlds | on repaired receiver-anchor worlds | realised best / mean |', '|---|---|---|---|---|']
for p_, x in lu['ALL']['cross_evaluation'].items():
    r = lu['ALL']['realised_actuals_HINDSIGHT_ONE_GAME'][p_]
    md.append(f"| {p_} | " + ' | '.join(f"{x[w]['expected_best_lineup_per_world']:.2f} ({x[w]['mean_lineup_mean']:.2f})" for w in ('incumbent', 'repaired_qb_anchor', 'repaired_receiver_anchor'))
              + f" | {r['best']:.2f} / {r['mean']:.2f} |")
md += ['', 'Largest player exposure changes, all contests (R1 -> repaired): ' + ', '.join(f"{r['player']} {r['R1']:.3f} -> {r['rebuilt']:.3f}" for r in lu['ALL']['player_exposure_changes_top10'][:6]) + '.', '',
       'Build log, last line: ' + '; '.join(f"{k}: `{v}`" for k, v in logs.items()), '',
       '## (d) Valid game outcomes', '', verd['d_valid_game_outcomes']['reading'], '',
       '| source | worlds | club score non-integer | club score in (0, 2) | club score 0 | ties | margin 3 or 7 | total mean | total SD | total p5 / p95 | points == event sum (max gap) |',
       '|---|---|---|---|---|---|---|---|---|---|---|']
hg = M['history']['games']
md.append(f"| history 2021-2025 REG | {hg['n_games']} games | {hg['share_non_integer_club_score']:.3f} | {hg['share_club_score_in_open_interval_0_2_excl_0']:.4f} | {hg['share_club_score_zero']:.4f} | {hg['share_ties']:.4f} | {hg['share_margin_3_or_7']:.3f} | {hg['total_mean']:.2f} | {hg['total_sd']:.2f} | {hg['total_p5']:.0f} / {hg['total_p95']:.0f} | |")
for t_, g in games.items():
    for a in ('inc', 'rep_qb'):
        x = g[a]
        md.append(f"| {t_} {AR[a]} | {x['n_worlds']} | {x['share_non_integer_club_score']:.3f} | {x['share_club_score_in_open_interval_0_2_excl_0']:.4f} | {x['share_club_score_zero']:.4f} | "
                  f"{x['share_ties']:.4f} | {x['share_margin_3_or_7']:.3f} | {x['total_mean']:.2f} | {x['total_sd']:.2f} | {x['total_p5']:.1f} / {x['total_p95']:.1f} | "
                  f"{x.get('points_eq_event_sum_max_abs_gap', 'n/a (continuous draw)')} |")
    md.append(f"| {t_} actual | 1 game | | | | | | {sum(g['actual'].values())} | | | |")
md += ['', 'History is unconditional (all games); a single slate\'s conditional distribution should be narrower, so a totals SD above the '
       'historical 13.65 is wider than history, not merely different. Both arms exceed it; the repaired arm by more. The receiver-anchor arm has the same club points as the QB-anchor arm.', '',
       '## Defects found in the repair itself', '']
for d in defects:
    md.append(f"- **{d['id']}** {d['what']}. ({d['severity']})")
md += ['', '## Promotion requirements still unmet', '']
md += [f'- {u}' for u in unmet]
md += ['', '## Reproduce', '']
md += [f"- {k}: `{v}`" for k, v in doc['reproduce'].items()]
(OUT / 'INTEGRATION_EVALUATION_2026-10-09.md').write_text('\n'.join(md) + '\n')
print('md written')
