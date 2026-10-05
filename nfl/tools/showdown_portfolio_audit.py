#!/usr/bin/env python3.12
"""Post-build audits of a staged Showdown scenario: the relaxation ladder and zero-point fillers.

    python3.12 nfl/tools/showdown_portfolio_audit.py EXPORT SCENARIO_DIR

Rebuilds the candidate pool's per-world first-place-proxy hits from the scenario's OWN frozen draws and
CANDIDATES.csv (no football is recomputed), then:

RELAXATION AUDIT, per contest: what each ladder rung builds, every player above the ORIGINAL level-0 cap
with his final exposure, the original and relaxed caps, which lineups exceed level-0 rules (player cap,
captain cap, overlap) and whether they cluster by captain / team split / salary band, and the effective
hypothesis count at the last rung that could not fill versus the final.

ZERO-POINT-FILLER AUDIT: every player whose simulated score is zero in every world (a long snapper, a
practice-squad body) is classified ZERO_POINT_FILLER. For each lineup that rosters one: contest, captain,
lineup, salary, proxy rate, the expensive players his salary unlocks, and the best realistic alternative
(same captain, most shared players, no filler) with the utility difference.
"""
from __future__ import annotations

import collections
import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_portfolio as SP  # noqa: E402


def rebuild(export, sd):
    sd = pathlib.Path(sd)
    scen = json.loads((sd / 'SCENARIO.json').read_text())
    draws_path = next(sd.glob('SHOWDOWN_*_DRAWS.json'))
    L = SP.load(export, draws_path, scen['absent_in_state']).value
    rows = SP.players_table(L['slate'], L['absent'], L['draws'])
    by = {r['key']: r for r in rows}
    name_to_key = {}
    for r in rows:
        if r['name'] in name_to_key:
            raise SystemExit(f"AMBIGUOUS_NAME {r['name']}")
        name_to_key[r['name']] = r['key']
    cands = []
    for r in csv.DictReader(open(next(sd.glob('SHOWDOWN_*_CANDIDATES.csv')))):
        cands.append((name_to_key[r['captain']], tuple(sorted(name_to_key[n] for n in r['flex'].split(' / ')))))
    M = SP.score_matrix(cands, by)
    opt = SP.world_optimum(rows).value['opt']
    hit = M >= ((1.0 - SP.BAND) * opt)[None, :]
    idx = {c: i for i, c in enumerate(cands)}
    finals = collections.defaultdict(list)
    for r in csv.DictReader(open(next(sd.glob('SHOWDOWN_*_FINAL_LINEUPS.csv')))):
        c = (name_to_key[r['CPT']], tuple(sorted(name_to_key[r[f'FLEX{i}']] for i in range(1, 6))))
        finals[r['contest_id']].append(idx[c])
    return {'sd': sd, 'L': L, 'rows': rows, 'by': by, 'cands': cands, 'M': M, 'opt': opt, 'hit': hit, 'finals': finals,
            'cand_rows': [{'first_place_proxy': float(h.mean()), 'structural_duplication_index': 0} for h in hit]}


def relaxation_audit(R):
    by, cands, hit = R['by'], R['cands'], R['hit']
    seats_of = [[c] + list(f) for c, f in cands]
    n_w = hit.shape[1]
    cr = R['cand_rows']
    out = {}
    for cid, chosen in R['finals'].items():
        n = len(chosen)
        rungs = []
        for rung in SP.LADDER:
            P = SP.select(hit, cr, seats_of, n, n_w, rung)
            d = SP.diversification(hit.astype(float), seats_of, P['chosen'])
            rungs.append({'level': rung['level'], 'caps': P['caps'], 'built': len(P['chosen']), 'needed': n,
                          'EFFECTIVE_HYPOTHESIS_COUNT': d.get('EFFECTIVE_HYPOTHESIS_COUNT')})
            if P['short'] == 0:
                break
        cap0 = rungs[0]['caps']
        exp = collections.Counter(k for i in chosen for k in seats_of[i])
        cexp = collections.Counter(seats_of[i][0] for i in chosen)
        over_p = {by[k]['name']: {'n': v, 'final_pct': round(100 * v / n, 1), 'orig_cap_n': cap0['player'],
                                  'orig_cap_pct': round(100 * cap0['player'] / n, 1)}
                  for k, v in exp.items() if v > cap0['player']}
        over_c = {by[k]['name']: {'n': v, 'final_pct': round(100 * v / n, 1), 'orig_cap_n': cap0['captain']}
                  for k, v in cexp.items() if v > cap0['captain']}
        # lineups that EXIST ONLY BECAUSE OF RELAXATION: in the final portfolio but not in the level-0 build
        affected = []
        sets = [set(seats_of[i]) for i in chosen]
        over_keys = {k for k, v in exp.items() if v > cap0['player']}
        level0 = set(SP.select(hit, cr, seats_of, n, n_w, SP.LADDER[0])['chosen'])
        for j, i in enumerate(chosen):
            ov = max((len(sets[j] & sets[t]) for t in range(len(chosen)) if t != j), default=0)
            if i not in level0:
                c, f = cands[i]
                sal = by[c]['cpt_salary'] + sum(by[k]['salary'] for k in f)
                teams = collections.Counter(by[k]['team'] for k in seats_of[i])
                affected.append({'captain': by[c]['name'], 'max_overlap': ov,
                                 'over_cap_players': [by[k]['name'] for k in set(seats_of[i]) & over_keys],
                                 'split': '-'.join(f"{teams.get(t, 0)}" for t in (R['L']['slate']['away'], R['L']['slate']['home'])),
                                 'salary': sal, 'proxy': round(float(hit[i].mean()), 4)})
        cl = {'by_captain': dict(collections.Counter(a['captain'] for a in affected).most_common()),
              'by_split': dict(collections.Counter(a['split'] for a in affected).most_common()),
              'by_salary_band': dict(collections.Counter(next(b for b, lo, hi in SP.SALARY_BANDS if lo <= a['salary'] <= hi)
                                                         for a in affected).most_common())}
        why = (f"level 0 built {rungs[0]['built']}/{n}: under a {cap0['player']}-entry player cap, a "
               f"{cap0['captain']}-entry captain cap and at most {cap0['overlap']} shared players, the lawful pool "
               f"near the top-tail runs out of lineups that avoid the core (" +
               ', '.join(sorted(over_p, key=lambda x: -over_p[x]['n'])[:4]) + ')')
        out[cid] = {'n_entries': n, 'rungs': rungs, 'players_above_original_cap': over_p,
                    'captains_above_original_cap': over_c, 'n_lineups_breaking_level0_rules': len(affected),
                    'affected_clusters': cl, 'WHY_RELAXATION_WAS_NEEDED': why,
                    'EFFECTIVE_HYPOTHESIS_COUNT_last_unfilled_rung': (rungs[-2]['EFFECTIVE_HYPOTHESIS_COUNT']
                                                                       if len(rungs) > 1 else None),
                    'EFFECTIVE_HYPOTHESIS_COUNT_final': rungs[-1]['EFFECTIVE_HYPOTHESIS_COUNT'],
                    'affected_lineups': affected}
    return out


NO_OFFENSIVE_ROLE_POSITIONS = ('LS', 'P')     # roster positions with no offensive snap


def roster_positions():
    import glob
    p = sorted(glob.glob(str(_REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/roster_weekly_*.csv')))
    if not p:
        return {}
    return {r['gsis_id']: r['position'] for r in csv.DictReader(open(p[-1])) if r['week'] == '4'}


def filler_audit(R):
    by, cands, hit, M = R['by'], R['cands'], R['hit'], R['M']
    # ZERO_POINT_FILLER: a DK row with no offensive role on the club's own roster (long snapper, punter),
    # or one whose simulated score is zero in every world. The allocator leaves every row a sliver of
    # volume; a role-less player's sliver is a model artifact, not upside.
    st = json.loads(next(pathlib.Path(R['sd']).glob('SHOWDOWN_*_STATE.json')).read_text())['players']
    gs = {f"{v['name']}|{v['team']}": v.get('gsis_id') for v in st.values()}
    rp = roster_positions()
    zero = {k for k, r in by.items() if r['has_draws'] and not r['absent']
            and (float(np.max(np.abs(r['draws']))) == 0.0 or rp.get(gs.get(k)) in NO_OFFENSIVE_ROLE_POSITIONS)}
    seats_of = [[c] + list(f) for c, f in cands]
    out = {'ZERO_POINT_FILLERS': sorted(by[k]['name'] for k in zero), 'lineups': []}
    for cid, chosen in R['finals'].items():
        for i in chosen:
            fill = set(seats_of[i]) & zero
            if not fill:
                continue
            c, f = cands[i]
            sal = by[c]['cpt_salary'] + sum(by[k]['salary'] for k in f)
            # best realistic alternative: same captain, no filler, most shared players, then best proxy
            alts = [j for j, (cc, ff) in enumerate(cands) if cc == c and not (set(seats_of[j]) & zero)]
            alts.sort(key=lambda j: (-len(set(seats_of[j]) & set(seats_of[i])), -hit[j].mean()))
            best = alts[0] if alts else None
            best_any = max(alts, key=lambda j: hit[j].mean()) if alts else None
            rec = {'contest': cid, 'captain': by[c]['name'],
                   'lineup': [by[k]['name'] for k in seats_of[i]], 'salary': sal,
                   'fillers': [by[k]['name'] for k in fill],
                   'proxy_rate': round(float(hit[i].mean()), 4), 'mean': round(float(M[i].mean()), 2),
                   'filler_p_scores': {by[k]['name']: round(float((by[k]['draws'] > 0).mean()), 4) for k in fill},
                   'filler_roster_position': {by[k]['name']: rp.get(gs.get(k)) for k in fill},
                   'salary_unlocks': sorted((by[k]['name'] for k in f if by[k]['salary'] >= 7000), key=str),
                   'best_alternative_same_captain_most_shared': None if best is None else {
                       'lineup': [by[k]['name'] for k in seats_of[best]], 'shared': len(set(seats_of[best]) & set(seats_of[i])),
                       'proxy_rate': round(float(hit[best].mean()), 4), 'mean': round(float(M[best].mean()), 2)},
                   'best_alternative_same_captain_by_proxy': None if best_any is None else {
                       'lineup': [by[k]['name'] for k in seats_of[best_any]],
                       'proxy_rate': round(float(hit[best_any].mean()), 4), 'mean': round(float(M[best_any].mean()), 2)}}
            if best_any is not None:
                rec['proxy_advantage_over_best_alternative'] = round(float(hit[i].mean() - hit[best_any].mean()), 4)
            out['lineups'].append(rec)
    out['counts_by_contest'] = dict(collections.Counter(r['contest'] for r in out['lineups']))
    return out


def run(export, sd):
    R = rebuild(export, sd)
    doc = {'ARTIFACT': 'SHOWDOWN_PORTFOLIO_AUDIT', 'scenario_dir': str(sd),
           'relaxation': relaxation_audit(R), 'zero_point_fillers': filler_audit(R)}
    pre = next(pathlib.Path(sd).glob('SHOWDOWN_*_AUDIT.json')).name.replace('_AUDIT.json', '')
    p = pathlib.Path(sd) / f'{pre}_RELAXATION_AND_FILLER_AUDIT.json'
    p.write_text(json.dumps(doc, indent=1, default=str))
    return p, doc


if __name__ == '__main__':
    p, d = run(sys.argv[1], sys.argv[2])
    print(p)
