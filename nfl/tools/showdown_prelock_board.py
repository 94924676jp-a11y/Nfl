#!/usr/bin/env python3.12
"""Final PRE-LOCK board for a staged Showdown scenario. Reads artifacts; recomputes no football.

    python3.12 nfl/tools/showdown_prelock_board.py EXPORT SCENARIO_DIR

Sections (owner pre-lock directive 2026-10-05, item 6):
  FOOTBALL   active state, starters, roles, projections, the simulator's football sanity block
  PORTFOLIO  exposures, distinct captains, effective hypotheses, overlap, relaxation in full (not a level
             number), swap polish, the 2-entry lineups with every LOW_OPPORTUNITY / ZERO_POINT slot labelled
             SALARY_RELIEF beside the best realistic alternative and the objective / mean-points difference
  FIELD      SHADOW ownership and duplication from BOTH field projections (FC_ONLY and MEAN_OF_FC_AND_OURS)
             side by side, neither promoted; salary left; team-split distribution
  EXTERNAL   FC comparison, video claims, Hard Rock (only after the football freeze; not captured here)
  FILES      the three per-contest DK upload CSVs, sha256, independent verifier result

READY is printed only when the official inactive list is in the scenario, the football sanity block
passed, every contest is filled and the independent verifier reports zero violations. Nothing is submitted.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_portfolio as SP, showdown_portfolio_audit as PA  # noqa: E402

TWO_ENTRY = '196285161'
SHADOW_SOURCES = ('FC_ONLY', 'BLEND')


def _one(sd, pat):
    ps = sorted(sd.glob(pat))
    if len(ps) != 1:
        raise SystemExit(f'EXPECTED_ONE {pat}: {[p.name for p in ps]}')
    return ps[0]


def football(sd, scen):
    proj = list(csv.DictReader(open(_one(sd, 'SHOWDOWN_*_PROJECTIONS.csv'))))
    draws = json.loads(_one(sd, 'SHOWDOWN_*_DRAWS.json').read_text())
    states = collections.Counter(r['state'] for r in proj)
    rows = [{k: r[k] for k in ('player', 'team', 'pos', 'salary', 'state', 'availability', 'designation',
                               'depth_rank', 'pass_att', 'carries', 'targets', 'sim_mean', 'p90', 'p_zero',
                               'role_data')}
            for r in sorted(proj, key=lambda r: -float(r['sim_mean'] or 0)) if r['sim_mean'] and float(r['sim_mean']) >= 1.0]
    return {'scenario': scen['scenario'], 'official_inactives': scen.get('official_inactives'),
            'designations': scen.get('designations'), 'absent_in_state': scen.get('absent_in_state'),
            'confirmed_starters': scen.get('confirmed_starters'), 'starter_tier': scen.get('starter_tier'),
            'state_counts': dict(states), 'football_sanity': draws.get('football_sanity'),
            'n_sims': draws.get('n_sims'), 'seed': draws.get('seed'),
            'projection_sha256': draws.get('projection_sha256'), 'state_sha256': draws.get('state_sha256'),
            'players_mean_ge_1pt': rows}


def portfolio(export, sd, R, audit, relax):
    by, cands, hit, M = R['by'], R['cands'], R['hit'], R['M']
    seats = [[c] + list(f) for c, f in cands]
    zpf = relax['zero_point_fillers']
    relief_names = set(zpf['ZERO_POINT_FILLERS']) | set(zpf.get('LOW_OPPORTUNITY_SALARY_RELIEF', []))
    out = {}
    for cid, chosen in R['finals'].items():
        P = audit['portfolios'][cid]
        n = len(chosen)
        exp = collections.Counter(k for i in chosen for k in seats[i])
        cexp = collections.Counter(seats[i][0] for i in chosen)
        sets = [set(seats[i]) for i in chosen]
        overlaps = [len(sets[a] & sets[b]) for a in range(n) for b in range(a + 1, n)]
        rx = relax['relaxation'][cid]
        c = {'n': n, 'objective': P['objective'], 'proxy_coverage': P['proxy_coverage'],
             'selection_method': P.get('selection_method'), 'polish': P.get('polish'),
             'distinct_captains': len(cexp),
             'captain_exposure_pct': {by[k]['name']: round(100 * v / n, 1) for k, v in cexp.most_common()},
             'player_exposure_pct': {by[k]['name']: round(100 * v / n, 1) for k, v in exp.most_common(15)},
             'effective_hypotheses': audit['portfolio_diversification'][cid].get('EFFECTIVE_HYPOTHESIS_COUNT'),
             'pairwise_shared_players': {'max': max(overlaps, default=0),
                                         'distribution': dict(sorted(collections.Counter(overlaps).items()))},
             'relaxation': {'level_used': P['relaxation_level'], 'rungs': rx['rungs'],
                            'players_above_original_cap': rx['players_above_original_cap'],
                            'captains_above_original_cap': rx['captains_above_original_cap'],
                            'n_lineups_not_in_level0_build': rx['n_lineups_breaking_level0_rules'],
                            'clusters': rx['affected_clusters'], 'why': rx['WHY_RELAXATION_WAS_NEEDED'],
                            'effective_hypotheses_last_unfilled_rung': rx['EFFECTIVE_HYPOTHESIS_COUNT_last_unfilled_rung'],
                            'effective_hypotheses_final_rung': rx['EFFECTIVE_HYPOTHESIS_COUNT_final']},
             'salary_relief_slots': collections.Counter(n_ for r in zpf['lineups'] if r['contest'] == cid
                                                        for n_ in r['fillers'])}
        if n <= 20:
            lines = []
            for i in chosen:
                rec = next((r for r in zpf['lineups'] if r['contest'] == cid and r['lineup'] == [by[k]['name'] for k in seats[i]]), None)
                sal = by[seats[i][0]]['cpt_salary'] + sum(by[k]['salary'] for k in seats[i][1:])
                ln = {'CPT': by[seats[i][0]]['name'], 'FLEX': [by[k]['name'] for k in seats[i][1:]], 'salary': sal,
                      'mean_points': round(float(M[i].mean()), 2), 'first_place_proxy': round(float(hit[i].mean()), 4)}
                if rec:
                    ln['SALARY_RELIEF'] = [{'player': f, 'classification': rec['classification'][f],
                                            'LABEL': 'SALARY RELIEF -- not a football conviction',
                                            'sim_mean': rec['filler_mean'][f], 'p_scores': rec['filler_p_scores'][f],
                                            'proxy_when_he_scores_0': rec['p_first_place_proxy_when_filler_scores_0'][f],
                                            'proxy_when_he_scores': rec['p_first_place_proxy_when_filler_scores_positive'][f]}
                                           for f in rec['fillers']]
                    ln['salary_unlocks'] = rec['salary_unlocks']
                    ln['best_alternative_same_captain_most_shared'] = rec['best_alternative_same_captain_most_shared']
                    ln['best_alternative_same_captain_by_proxy'] = rec['best_alternative_same_captain_by_proxy']
                    if rec.get('best_alternative_same_captain_by_proxy'):
                        ln['proxy_diff_vs_best_alternative'] = rec.get('proxy_advantage_over_best_alternative')
                        ln['mean_points_diff_vs_best_alternative'] = round(
                            ln['mean_points'] - rec['best_alternative_same_captain_by_proxy']['mean'], 2)
                lines.append(ln)
            c['lineups'] = lines
            used = sorted({s['player'] for ln in lines for s in ln.get('SALARY_RELIEF', [])})
            if used:
                c['salary_relief_portfolio_test'] = {
                    'without_these': PA.relief_portfolio_test(R, cid, used),
                    'without_any_low_opportunity_or_filler': PA.relief_portfolio_test(R, cid, sorted(relief_names))}
        out[cid] = c
    return out


def field(sd):
    out = {}
    for src in SHADOW_SOURCES:
        p = sd / f'SHOWDOWN_ATL_NO_SHADOW_BOARD_{src}.json'
        if not p.exists():
            out[src] = 'NOT_BUILT'
            continue
        b = json.loads(p.read_text())
        out[src] = {'label': b['label'], 'VALIDATED': b['VALIDATED'], 'sigma': b['sigma'],
                    'field_projection': b.get('field_projection'), 'anchor_rmse': b.get('anchor_rmse'),
                    'field_size_estimates': b['field_size_estimates'],
                    'contests': {cid: {k: v[k] for k in ('pred_dupes_exact', 'pred_dupes_product', 'geomean_ownership_median',
                                                         'lineups_with_player_absent_from_shadow_field',
                                                         'salary_left', 'team_split_away_home',
                                                         'shadow_portfolio_comparison')}
                                       | {'leverage_top12': v['leverage'][:12],
                                          'two_entry_lineups': v['lineups'] if cid == TWO_ENTRY else None}
                                 for cid, v in b['contests'].items()}}
    out['PROMOTION_STATUS'] = ('NOT_PROMOTED. Both field projections are EXTERNAL_RESEARCH_SHADOW and UNVALIDATED; '
                               'the blend fits five unverified anchors better, which is not validation. Neither '
                               'feeds the football or the production portfolio.')
    return out


def external(sd):
    fc = list(csv.DictReader(open(_one(sd, 'SHOWDOWN_*_FC_COMPARISON.csv'))))
    fc.sort(key=lambda r: -abs(float(r['diff_ours_minus_fc'] or 0)))
    cl = list(csv.DictReader(open(_one(sd, 'SHOWDOWN_*_EXTERNAL_VIDEO_CLAIMS.csv'))))
    return {'fc_comparison_largest_gaps': [{k: r[k] for k in ('player', 'team', 'pos', 'our_mean', 'fc_flex',
                                                              'diff_ours_minus_fc', 'triage', 'our_role')} for r in fc[:12]],
            'FC_IS_NOT_AN_INPUT': True,
            'video_claims': [{k: r[k] for k in ('claim_id', 'player', 'claim', 'their_number', 'our_number',
                                                 'ours_minus_theirs', 'status')} for r in cl],
            'HARD_ROCK': 'NOT CAPTURED HERE -- only after the football freeze, by the networked agent (docs/AGENT_OUTBOX.md); '
                         'never fed back into the projection; no wager is recommended'}


def files(sd, audit):
    out = {}
    for p in sorted(sd.glob('SHOWDOWN_*_DK_UPLOAD_*.csv')):
        rows = list(csv.reader(open(p)))
        out[p.name] = {'path': str(p.resolve().relative_to(_REPO)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                       'lineup_rows': len(rows) - 1}
    ver = audit['upload_verification']
    return {'uploads': out, 'verifier': ver if not isinstance(ver, dict) else
            {k: ver.get(k) for k in ('state', 'code', 'n_rows', 'violations') if k in ver} or ver}


def run(export, sd):
    sd = pathlib.Path(sd)
    scen = json.loads((sd / 'SCENARIO.json').read_text())
    audit = json.loads(PA._prod_audit(sd).read_text())
    relax = json.loads(_one(sd, 'SHOWDOWN_*_RELAXATION_AND_FILLER_AUDIT.json').read_text())
    R = PA.rebuild(export, sd)
    fb = football(sd, scen)
    pf = portfolio(export, sd, R, audit, relax)
    fl = files(sd, audit)
    ver = audit['upload_verification']
    n_viol = len(ver.get('violations', [])) if isinstance(ver, dict) else None
    filled = all(v['n_built'] == v['n_entries'] for v in audit['portfolios'].values())
    sanity = (fb['football_sanity'] or {}).get('state') if isinstance(fb['football_sanity'], dict) else fb['football_sanity']
    blockers = []
    if not scen.get('official_inactives'):
        blockers.append('OFFICIAL_INACTIVES_NOT_INCORPORATED')
    if sanity != 'PASS':
        blockers.append(f'FOOTBALL_SANITY={sanity}')
    if not filled:
        blockers.append('FINAL_LINEUPS != PAID_ENTRIES')
    if n_viol != 0:
        blockers.append(f'VERIFIER_VIOLATIONS={n_viol}')
    board = {'ARTIFACT': 'SHOWDOWN_PRELOCK_BOARD', 'scenario': scen['scenario'],
             'STATUS': 'READY' if not blockers else 'NOT_READY', 'BLOCKERS': blockers,
             'FOOTBALL': fb, 'PORTFOLIO': pf, 'FIELD': field(sd), 'EXTERNAL': external(sd), 'FILES': fl,
             'NOT_SUBMITTED': 'nothing here enters a contest or uploads to DraftKings; PROJECTION_SYSTEM_STATE '
                              'NOT_VALIDATED; no wager is recommended'}
    p = sd / 'SHOWDOWN_ATL_NO_PRELOCK_BOARD.json'
    p.write_text(json.dumps(board, indent=1, default=str))
    (sd / 'SHOWDOWN_ATL_NO_PRELOCK_BOARD.md').write_text(markdown(board))
    return p, board


def markdown(b):
    L = [f"# ATL @ NO Showdown -- PRE-LOCK board ({b['scenario']})", '',
         f"**{b['STATUS']}**" + (f" -- blockers: {', '.join(b['BLOCKERS'])}" if b['BLOCKERS'] else ''), '',
         '## FOOTBALL', f"- official inactives: `{b['FOOTBALL']['official_inactives'] or 'NOT YET INCORPORATED'}`",
         f"- starters: `{b['FOOTBALL']['confirmed_starters']}` ({b['FOOTBALL']['starter_tier']})",
         f"- state counts: `{b['FOOTBALL']['state_counts']}`",
         f"- football sanity: `{json.dumps(b['FOOTBALL']['football_sanity'], default=str)[:600]}`", '',
         '| player | team | pos | salary | state | availability | desig | depth | mean | p90 | P(0) |', '|' + '---|' * 11]
    for r in b['FOOTBALL']['players_mean_ge_1pt']:
        L.append(f"| {r['player']} | {r['team']} | {r['pos']} | {r['salary']} | {r['state']} | {r['availability']} | "
                 f"{r['designation']} | {r['depth_rank']} | {r['sim_mean']} | {r['p90']} | {r['p_zero']} |")
    L += ['', '## PORTFOLIO']
    for cid, c in b['PORTFOLIO'].items():
        rx = c['relaxation']
        L += [f"### {cid} ({c['n']} entries)",
              f"- objective `{c['objective']}`; proxy coverage {c['proxy_coverage']}; method {c['selection_method']}; polish `{c['polish']}`",
              f"- distinct captains {c['distinct_captains']}; effective hypotheses {c['effective_hypotheses']}; "
              f"shared players between pairs `{c['pairwise_shared_players']}`",
              f"- captain exposure `{c['captain_exposure_pct']}`", f"- player exposure `{c['player_exposure_pct']}`",
              f"- RELAXATION: level {rx['level_used']}; rungs " + '; '.join(
                  f"L{r['level']} caps {r['caps']} built {r['built']}/{r['needed']} EHC {r['EFFECTIVE_HYPOTHESIS_COUNT']}"
                  for r in rx['rungs']),
              f"  - above the original cap: `{rx['players_above_original_cap']}`; captains `{rx['captains_above_original_cap']}`",
              f"  - lineups not in the level-0 build: {rx['n_lineups_not_in_level0_build']}; clusters `{rx['clusters']}`",
              f"  - why: {rx['why']}",
              f"  - effective hypotheses (rungs are GREEDY rebuilds, before the swap polish): last unfilled rung "
              f"{rx['effective_hypotheses_last_unfilled_rung']} -> filled rung {rx['effective_hypotheses_final_rung']}; "
              f"final polished portfolio {c['effective_hypotheses']}",
              f"- salary-relief slots used: `{dict(c['salary_relief_slots'])}`"]
        if cid == TWO_ENTRY or c['n'] <= 2:
            for ln in c.get('lineups', []):
                L.append(f"- **CPT {ln['CPT']}** + {', '.join(ln['FLEX'])} -- ${ln['salary']}, mean {ln['mean_points']}, proxy {ln['first_place_proxy']}")
                for s in ln.get('SALARY_RELIEF', []):
                    L.append(f"  - **{s['player']}: {s['LABEL']}** ({s['classification']}; mean {s['sim_mean']}, scores in "
                             f"{s['p_scores']:.0%} of worlds; proxy {s['proxy_when_he_scores_0']} when he scores 0 vs "
                             f"{s['proxy_when_he_scores']} when he scores); unlocks {ln['salary_unlocks']}")
                if ln.get('best_alternative_same_captain_by_proxy'):
                    a = ln['best_alternative_same_captain_by_proxy']
                    L.append(f"  - best realistic alternative without him: {a['lineup']} (proxy {a['proxy_rate']}, mean {a['mean']}); "
                             f"difference proxy {ln['proxy_diff_vs_best_alternative']:+}, mean points {ln['mean_points_diff_vs_best_alternative']:+}")
            t = c.get('salary_relief_portfolio_test')
            if t:
                for lab, v in t.items():
                    L.append(f"  - portfolio test {lab} {v['banned']}: objective {v['objective_diff']:+}, coverage "
                             f"{v['coverage_diff_pts']:+} pts (SE {v['binomial_se_pts']}), mean points {v['mean_points_diff']:+}; "
                             f"alternative lineups {v['without_banned']['lineups']}")
    L += ['', '## FIELD (EXTERNAL_RESEARCH_SHADOW, UNVALIDATED)', f"- {b['FIELD']['PROMOTION_STATUS']}"]
    for src in SHADOW_SOURCES:
        f = b['FIELD'].get(src)
        if not isinstance(f, dict):
            L.append(f"- {src}: {f}")
            continue
        L.append(f"### {src} (sigma {f['sigma']}, anchor RMSE {f['anchor_rmse']})")
        for cid, v in f['contests'].items():
            if v.get('lineups_with_player_absent_from_shadow_field'):
                L.append(f"- {cid}: **{v['lineups_with_player_absent_from_shadow_field']} lineup(s) contain a player this "
                         f"shadow field never rosters -- their dupe estimates are UNDERSTATED, not evidence of uniqueness**")
            L.append(f"- {cid}: dupes exact `{v['pred_dupes_exact']}` product `{v['pred_dupes_product']}`; salary left "
                     f"`{v['salary_left']}`; split `{v['team_split_away_home']}`")
        L.append('  - CPT/FLEX ownership (150): ' + '; '.join(
            f"{e['player']} {e['shadow_cpt']}/{e['shadow_flex']}" for e in f['contests'].get('196285137', {}).get('leverage_top12', [])))
    L += ['', '## EXTERNAL', f"- Hard Rock: {b['EXTERNAL']['HARD_ROCK']}", '- FC comparison (largest gaps; FC is never an input):']
    for r in b['EXTERNAL']['fc_comparison_largest_gaps']:
        L.append(f"  - {r['player']} ({r['team']} {r['pos']}): ours {r['our_mean']} vs FC {r['fc_flex']} ({r['triage']})")
    L.append(f"- video claims compared: {len(b['EXTERNAL']['video_claims'])} (UNVERIFIED_EXTERNAL)")
    L += ['', '## FILES']
    for n, v in b['FILES']['uploads'].items():
        L.append(f"- `{v['path']}` -- {v['lineup_rows']} rows, sha256 `{v['sha256']}`")
    L += [f"- verifier: `{json.dumps(b['FILES']['verifier'], default=str)[:400]}`", '', b['NOT_SUBMITTED']]
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    p, b = run(sys.argv[1], sys.argv[2])
    print(p, b['STATUS'], b['BLOCKERS'])
