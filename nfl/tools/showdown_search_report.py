#!/usr/bin/env python3.12
"""Measured lineup-search and selection counts for one built Showdown portfolio. Read-only.

    python3.12 nfl/tools/showdown_search_report.py BUILD_DIR SCENARIO_DIR [--out REPORT.json]

Owner directive 2026-10-09: report EXACT search and evaluation counts, and never confuse 2,000 simulated games with
2,000 evaluated lineups. Every number here is counted from the build's own files:

  universe     DK pool rows; eligible people (the build's eligible set); every captain x 5-flex combination; how many
               of those are legal (salary cap 50,000 with the captain at 1.5x salary, both clubs present) -- exact,
               by vectorised enumeration over the eligible set
  generated    candidates by generator (exact / near-optimal per-world solves; forced-captain solves), and how many
               distinct lineups survive de-duplication (the CANDIDATES.csv the selector read)
  scored       candidates x simulated worlds = score-matrix cells actually evaluated
  selected     per contest: entries, distinct lineups, relaxation level and final caps
  rejected     for every candidate whose own first-place proxy beats the weakest selected lineup of a contest but which
               was not selected: the binding reason against the final portfolio -- PLAYER_CAP, CAPTAIN_CAP, OVERLAP, or
               MARGINAL (legal, but adding it raised the objective less than the lineup chosen). This is a post-hoc
               reconstruction against the FINAL portfolio, labelled as such; the greedy selector does not log rejections.
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
CAP = 50000


def legal_count(players):
    """Exact count of legal Showdown lineups over `players` (dicts with salary, cpt_salary, team)."""
    n = len(players)
    sal = np.array([p['salary'] for p in players], dtype=np.int64)
    csal = np.array([p['cpt_salary'] for p in players], dtype=np.int64)
    team = np.array([p['team'] for p in players])
    total, legal = 0, 0
    for c in range(n):
        others = np.array([i for i in range(n) if i != c])
        comb = np.array(list(itertools.combinations(range(len(others)), 5)))
        idx = others[comb]
        s = csal[c] + sal[idx].sum(1)
        two = (team[idx] != team[c]).any(1)
        total += len(idx)
        legal += int(((s <= CAP) & two).sum())
    return total, legal


def run(build_dir, scenario_dir):
    bd, sd = pathlib.Path(build_dir), pathlib.Path(scenario_dir)
    audit = json.loads(next(bd.glob('SHOWDOWN_*_AUDIT.json')).read_text())
    state = json.loads(next(sd.glob('SHOWDOWN_*_STATE.json')).read_text())
    cands = list(csv.DictReader(open(next(bd.glob('SHOWDOWN_*_CANDIDATES.csv')))))
    final = list(csv.DictReader(open(next(bd.glob('SHOWDOWN_*_FINAL_LINEUPS.csv')))))
    n_worlds = int(audit['n_worlds'])
    # eligible = the names appearing in any candidate (the selector's universe); cross-checked against audit n_eligible
    names = {c['captain'] for c in cands} | {x.strip() for c in cands for x in c['flex'].split(' / ')}
    pl = [v for v in state['players'].values() if v['name'] in names]
    tot, leg = legal_count(pl)
    by_src = collections.Counter(c['source'] for c in cands)
    key = lambda cpt, flex: (cpt, tuple(sorted(flex)))  # noqa: E731
    cand_by_key = {key(c['captain'], [x.strip() for x in c['flex'].split(' / ')]): c for c in cands}
    out = {'ARTIFACT': 'SHOWDOWN_SEARCH_REPORT', 'build_dir': str(bd), 'n_worlds': n_worlds,
           'universe': {'dk_pool_rows': audit.get('roster_completeness', {}).get('n_dk_rows'),
                        'eligible_people_in_candidates': len(pl), 'audit_n_eligible': audit.get('n_eligible'),
                        'captain_x_5flex_combinations': tot, 'legal_lineups_exact': leg,
                        'combinations_formula': f'{len(pl)} x C({len(pl) - 1},5) = {len(pl) * math.comb(len(pl) - 1, 5)}'},
           'generated': {'by_generator': dict(by_src), 'distinct_candidates_read_by_selector': len(cands),
                         'share_of_legal_universe': round(len(cands) / leg, 6)},
           'scored': {'candidates': len(cands), 'worlds': n_worlds, 'score_matrix_cells': len(cands) * n_worlds,
                      'NOTE': 'every candidate is scored in every world; 2,000 is the number of simulated games, not lineups'},
           'contests': {}}
    proxy = {k: float(c['first_place_proxy']) for k, c in cand_by_key.items()}
    for cid in sorted({r['contest_id'] for r in final}):
        F = [r for r in final if r['contest_id'] == cid]
        P = audit['portfolios'][cid]
        caps = P['relaxation_log'][-1]['caps']
        chosen = [key(r['CPT'], [r[f'FLEX{i}'] for i in range(1, 6)]) for r in F]
        n = len(F)
        expo, cexpo = collections.Counter(), collections.Counter()
        for c, f in chosen:
            cexpo[c] += 1
            for x in (c, *f):
                expo[x] += 1
        weakest = min(proxy.get(k, 0.0) for k in chosen)
        reasons = collections.Counter()
        examples = {}
        for k, pr in proxy.items():
            if k in set(chosen) or pr <= weakest:
                continue
            c, f = k
            lineup = {c, *f}
            if any(expo[x] + 1 > caps['player'] for x in lineup):
                r = 'PLAYER_CAP'
            elif cexpo[c] + 1 > caps['captain']:
                r = 'CAPTAIN_CAP'
            elif any(len(lineup & {cc, *ff}) > caps['overlap'] for cc, ff in chosen):
                r = 'OVERLAP'
            else:
                r = 'MARGINAL'
            reasons[r] += 1
            examples.setdefault(r, []).append({'captain': c, 'flex': list(f), 'first_place_proxy': pr})
        at_cap = sorted(p for p, v in expo.items() if v >= caps['player'])
        out['contests'][cid] = {
            'entries': n, 'distinct_selected': len(set(chosen)), 'relaxation_level': P['relaxation_level'], 'final_caps': caps,
            'selection_method': P.get('selection_method'), 'objective': 'greedy max E_w[min(hits, m)], hit = score >= 0.9 x world optimum',
            'depth_m': 1 if n >= 100 or n <= 2 else 2,
            'players_at_player_cap': at_cap,
            'candidates_with_higher_own_proxy_than_weakest_selected_but_not_selected': sum(reasons.values()),
            'binding_reason_post_hoc': dict(reasons),
            'examples': {r: sorted(v, key=lambda x: -x['first_place_proxy'])[:3] for r, v in examples.items()},
            'NOTE': 'rejection reasons reconstructed against the FINAL portfolio; the greedy selector does not log them'}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('build_dir')
    ap.add_argument('scenario_dir')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    doc = run(a.build_dir, a.scenario_dir)
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(doc, indent=1) + '\n')
    print(json.dumps({k: doc[k] for k in ('universe', 'generated', 'scored')}, indent=1))
    for cid, c in doc['contests'].items():
        print(cid, {k: c[k] for k in ('entries', 'distinct_selected', 'relaxation_level', 'final_caps', 'players_at_player_cap',
                                       'candidates_with_higher_own_proxy_than_weakest_selected_but_not_selected', 'binding_reason_post_hoc')})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
