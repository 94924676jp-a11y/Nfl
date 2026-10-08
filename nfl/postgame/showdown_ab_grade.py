#!/usr/bin/env python3.12
"""Grade sealed ATL@NO Showdown portfolios (incumbent vs one-change variants) against the real fields. Read-only.

    python3.12 nfl/postgame/showdown_ab_grade.py LABEL=SCENARIO_DIR [LABEL=SCENARIO_DIR ...] --out GRADE.json

Owner directive 2026-10-08 (historical Showdown A/B before production changes). Every portfolio graded here was
BUILT BEFORE IT WAS SCORED, from sealed prelock worlds. The outcome enters only now, after the portfolio exists.

  actual lineup points  from ATL_NO_POSTGAME_ACTUAL.json (nflverse play-by-play, dk_A) with CPT x1.5, the same
                        scorer that reconciles the live upload to the owner's graded entries 172/172
  exact rank            1 + entries in the archived full field scoring strictly more (DK shares tied ranks)
  field copies          entries in the real field with the identical captain and FLEX set
  payout                ESTIMATE ONLY. The standings export carries no prize table. It uses the conservative curve from
                        the owner's own graded entries (showdown_atl_no_portfolio_study.payout); it is capped at the best
                        observed entry and is NOT_AVAILABLE for the 2-entry contest. No dollar figure here is a payout.
  actual return         only for the portfolio that was actually entered (the owner's recorded winnings)

ONE GAME IS ONE DRAW. A portfolio that happens to hold a lineup with one player's three touchdowns wins this table
whatever its objective was. Counterfactual lineups did not exist in the field, so opponents' behaviour is unchanged.
This is retrospective development evidence on an already-used slate, never held-out validation.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import showdown_atl_no_portfolio_study as ST  # noqa: E402
from nfl.postgame import showdown_atl_no_field_actual as FA  # noqa: E402

PROD = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'


def _lineups(d):
    by = collections.defaultdict(list)
    for r in csv.DictReader(open(pathlib.Path(d) / 'SHOWDOWN_ATL_NO_FINAL_LINEUPS.csv')):
        by[r['contest_id']].append((r['CPT'], tuple(sorted(r[f'FLEX{i}'] for i in range(1, 6))), int(r['salary'])))
    return by


def grade(variants):
    key, pts, cv = ST._names(), ST._actual_points(), ST.curves()
    fees = {c: float(next(x['fee'] for x in csv.DictReader(open(ST.OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv'))
                          if x['contest_id'] == c)) for c in ST.CONTESTS}
    actual_ret = collections.defaultdict(float)
    for x in csv.DictReader(open(ST.OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv')):
        actual_ret[x['contest_id']] += float(x['winnings'])
    field = {}
    for c in ST.CONTESTS:
        ents = FA.load_standings(c)['entries']
        field[c] = {'pts': np.sort(np.array([e['points'] for e in ents]))[::-1],
                    'copies': collections.Counter((e['cpt'], tuple(sorted(e['flex']))) for e in ents), 'n': len(ents)}
    prod = _lineups(PROD)
    out = {}
    for label, d in variants:
        L = _lineups(d)
        res = {}
        for c in ST.CONTESTS:
            lu = L.get(c, [])
            if not lu:
                res[c] = {'n': 0}
                continue
            sc = [round(ST.lineup_score(cp, list(fx), key, pts), 2) for cp, fx, _s in lu]
            rk = [int(1 + np.sum(field[c]['pts'] > s + 0.005)) for s in sc]
            pay = [ST.payout(s, cv[c]) for s in sc]
            est = None if any(p[0] is None for p in pay) else round(sum(p[0] for p in pay), 2)
            cap = collections.Counter(cp for cp, _f, _s in lu)
            flex = collections.Counter(n for _c, fx, _s in lu for n in fx)
            sets = collections.Counter((cp, fx) for cp, fx, _s in lu)
            ps = {(cp, fx) for cp, fx, _s in prod.get(c, [])}
            fee = fees[c] * len(lu)
            res[c] = {'n': len(lu), 'entry_fees': round(fee, 2),
                      'actual_best_points': max(sc), 'actual_median_points': float(np.median(sc)),
                      'exact_best_rank': min(rk), 'exact_median_rank': int(np.median(rk)), 'field_size': field[c]['n'],
                      'exact_top_1pct': sum(r <= 0.01 * field[c]['n'] for r in rk),
                      'exact_top_10pct': sum(r <= 0.10 * field[c]['n'] for r in rk),
                      'ESTIMATED_payout_curve': est, 'ESTIMATED_net': None if est is None else round(est - fee, 2),
                      'ESTIMATED_roi': None if est is None else round(est / fee - 1, 4),
                      'ESTIMATED_cash_count': None if est is None else sum(1 for p in pay if p[0] and p[0] > 0),
                      'payout_flags': sorted({p[1] for p in pay}),
                      'distinct_lineups': len(sets), 'max_self_duplicates': max(sets.values()),
                      'distinct_captains': len(cap), 'captain_exposure': dict(cap.most_common()),
                      'top_flex_exposure': dict(flex.most_common(8)),
                      'max_exposure_share': round(max(flex.values()) / len(lu), 3),
                      'mean_salary': round(float(np.mean([s for *_x, s in lu])), 1),
                      'field_copies_of_our_lineups': sum(field[c]['copies'].get(k, 0) for k in sets),
                      'overlap_with_production': len(set(sets) & ps),
                      'ACTUAL_return_if_this_was_entered': (round(actual_ret[c], 2)
                                                            if pathlib.Path(d).resolve() == PROD.resolve() else None)}
        tot_fee = sum(r.get('entry_fees', 0) for r in res.values())
        ests = [r.get('ESTIMATED_payout_curve') for r in res.values() if r.get('n')]
        res['ALL'] = {'entry_fees': round(tot_fee, 2),
                      'ESTIMATED_payout_curve_excl_2entry': round(sum(e for e in ests if e is not None), 2),
                      'NOTE': 'the 2-entry contest has no payout estimate; the sum covers the other two contests only'}
        out[label] = {'dir': str(d), 'contests': res}
    return {'ARTIFACT': 'SHOWDOWN_AB_GRADE', 'slate': 'ATL_NO_2026W4',
            'EVIDENCE_CLASS': 'RETROSPECTIVE_DEVELOPMENT (ATL@NO already used for development; one game)',
            'PAYOUT': 'ESTIMATE from the conservative owner-entry curve; the prize table is absent', 'variants': out}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('variants', nargs='+')
    ap.add_argument('--out')
    a = ap.parse_args()
    r = grade([tuple(v.split('=', 1)) for v in a.variants])
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(r, indent=1, default=str) + '\n')
    for lab, v in r['variants'].items():
        for c, x in v['contests'].items():
            if c != 'ALL' and x.get('n'):
                print(f"{lab:22s} {c} n{x['n']:4} best {x['actual_best_points']:7.2f} rank {x['exact_best_rank']:6} "
                      f"top1% {x['exact_top_1pct']:2} est {x['ESTIMATED_payout_curve']} overlap {x['overlap_with_production']} "
                      f"actual {x['ACTUAL_return_if_this_was_entered']}")
