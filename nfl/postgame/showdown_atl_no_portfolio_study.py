#!/usr/bin/env python3.12
"""ATL@NO postgame item 8 -- portfolio construction study (decision layer only; contests kept separate).

    python3.12 nfl/postgame/showdown_atl_no_portfolio_study.py

LAYER: POSTGAME_DIAGNOSIS. Reads sealed prelock portfolios and candidates; writes ATL_NO_PORTFOLIO_STUDY.json.

WHAT THIS CAN AND CANNOT SAY. Every variant below was BUILT BEFORE LOCK from sealed worlds; none is built now from
outcomes. They are scored on the one realised game. One game is one draw: a portfolio that happened to hold the
lineup with Brian Robinson Jr.'s three touchdowns wins this table whatever its objective was. This is a
COUNTERFACTUAL LEDGER, not a test of objectives, and it promotes nothing.

PAYOUT CURVE. There are no ATL@NO full-field standings in the repository. The owner's own graded entries give
(points, place, winnings) pairs for each contest (150 in the 150-max, 20 in the 20-max, 2 in the 2-entry). A
variant lineup's place is interpolated monotonically in log(place) from those pairs, and its payout is the winnings
of the nearest observed entry at that place OR WORSE (conservative). Above the owner's best observed score the
payout is CAPPED at the best observed payout and flagged; below the lowest it is 0. The 2-entry contest's two
points cannot support a curve, so its payout is NOT_AVAILABLE.

VARIANTS (all prelock): V2_FINAL (the live upload), V1 (pre-TE-order fix), RW_CRN (CRN control), FANT_OUT and BASE
(earlier availability states, polished) and their _GREEDY_V3_SNAPSHOT (greedy before swap polish), OFFICIAL_DRYRUN;
and two ABLATIONS from the v2 sealed candidate pool, chosen by a per-lineup rule with no portfolio objective:
TOP_MEAN (highest simulated mean) and TOP_PROXY (highest first-place proxy). Ablations isolate what the portfolio
objective adds over ranking lineups one at a time -- in the prelock worlds (where the objective is defined) and
on the realised game (where it is one draw).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

ATL = _REPO / 'nfl/dfs/salaries/showdown_atl_no'
V2 = ATL / 'RW_INACTIVES_CHARTFIX'
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
CONTESTS = {'196285137': 150, '196285160': 20, '196285161': 2}
VARIANTS = ['RW_INACTIVES_CHARTFIX', 'RW_INACTIVES', 'RW_CRN', 'FANT_OUT', 'FANT_OUT/_GREEDY_V3_SNAPSHOT', 'BASE',
            'BASE/_GREEDY_V3_SNAPSHOT', 'OFFICIAL_DRYRUN']
LABEL = {'RW_INACTIVES_CHARTFIX': 'V2_FINAL_LIVE', 'RW_INACTIVES': 'V1'}


class StudyError(RuntimeError):
    pass


def _names():
    proj = list(csv.DictReader(open(next(V2.glob('SHOWDOWN_*_PROJECTIONS.csv')))))
    m = {}
    for r in proj:
        if r['player'] in m:
            raise StudyError(f'AMBIGUOUS_NAME {r["player"]}')
        m[r['player']] = f"{r['player']}|{r['team']}"
    return m


def _actual_points():
    a = json.loads((OUT / 'ATL_NO_POSTGAME_ACTUAL.json').read_text())['player_actuals']
    return {k: float(v['dk_A']) for k, v in a.items()}


def lineup_score(cpt, flex, key, pts):
    miss = [n for n in [cpt, *flex] if key.get(n) is None]
    if miss:
        raise StudyError(f'UNMAPPED_PLAYERS {miss}')
    return 1.5 * pts.get(key[cpt], 0.0) + sum(pts.get(key[n], 0.0) for n in flex)


def curves():
    rows = list(csv.DictReader(open(OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv')))
    out = {}
    for c in CONTESTS:
        r = sorted(((float(x['dk_points']), int(x['place']), float(x['winnings'])) for x in rows if x['contest_id'] == c),
                   key=lambda t: -t[0])
        if not r:
            raise StudyError(f'NO_OWNER_ENTRIES {c}')
        cash = [t for t in r if t[2] > 0]
        out[c] = {'pairs': r, 'n': len(r), 'best_points': r[0][0], 'best_payout': r[0][2],
                  'cash_line_points_lo': min((t[0] for t in cash), default=None),
                  'field': int(next(x['field'] for x in rows if x['contest_id'] == c))}
    return out


def payout(score, cv):
    pr = cv['pairs']
    if cv['n'] < 5:
        return None, 'NOT_AVAILABLE_TOO_FEW_POINTS'
    if score >= pr[0][0]:
        return pr[0][2], ('AT_BEST_OBSERVED' if score == pr[0][0] else 'TOP_CAPPED')
    if score < pr[-1][0]:
        return 0.0, 'BELOW_LOWEST_OBSERVED'
    pts = np.array([t[0] for t in pr][::-1])
    lp = np.log(np.array([t[1] for t in pr][::-1], dtype=float))
    place = float(np.exp(np.interp(score, pts, lp)))
    worse = [t for t in pr if t[1] >= place]
    return (min(worse, key=lambda t: t[1])[2] if worse else 0.0), 'INTERPOLATED'


def load_variant(d):
    p = ATL / d / 'SHOWDOWN_ATL_NO_FINAL_LINEUPS.csv'
    rows = list(csv.DictReader(open(p)))
    by = {c: [] for c in CONTESTS}
    for r in rows:
        by[r['contest_id']].append((r['CPT'], [r[f'FLEX{i}'] for i in range(1, 6)],
                                    float(r['mean']), float(r['first_place_proxy'])))
    for c, n in CONTESTS.items():
        if len(by[c]) != n:
            raise StudyError(f'VARIANT_COUNT {d} {c} {len(by[c])} != {n}')
    return by


def ablations():
    rows = list(csv.DictReader(open(V2 / 'SHOWDOWN_ATL_NO_CANDIDATES.csv')))
    if len(rows) < 150:
        raise StudyError('CANDIDATES_TOO_FEW')
    mk = lambda r: (r['captain'], r['flex'].split(' / '), float(r['mean']), float(r['first_place_proxy']))
    out = {}
    for name, col in (('ABLATION_TOP_MEAN', 'mean'), ('ABLATION_TOP_PROXY', 'first_place_proxy')):
        s = sorted(rows, key=lambda r: -float(r[col]))
        out[name] = {c: [mk(r) for r in s[:n]] for c, n in CONTESTS.items()}
    return out


def _prelock_hits(lineups, key):
    """Prelock objective quantities on the sealed v2 worlds: P(at least one lineup reaches the first-place proxy)."""
    d = json.loads(next(V2.glob('SHOWDOWN_*_2026W4_DRAWS.json')).read_text())
    draws = {k: np.asarray(v, float) for k, v in d['draws'].items()}
    S = np.array([1.5 * draws[key[c]] + sum(draws[key[n]] for n in f) for c, f, *_ in lineups])
    opt = None
    p = V2 / 'SHOWDOWN_ATL_NO_AUDIT.json'
    if p.exists():
        a = json.loads(p.read_text())
        opt = a.get('world_optimum') or (a.get('AUDIT') or {}).get('world_optimum')
    return S, opt


def run():
    key, pts, cv = _names(), _actual_points(), curves()
    variants = {LABEL.get(d, d): load_variant(d) for d in VARIANTS}
    variants.update(ablations())
    # reconciliation: V2_FINAL realised scores must equal the DK-graded owner entries exactly
    live = sorted(round(lineup_score(c, f, key, pts), 2) for cid in CONTESTS for c, f, *_ in variants['V2_FINAL_LIVE'][cid])
    graded = sorted(round(float(x['dk_points']), 2) for x in csv.DictReader(open(OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv')))
    if live != graded:
        raise StudyError('V2_FINAL_DOES_NOT_RECONCILE_WITH_GRADED_ENTRIES')
    fees = {c: float(next(x['fee'] for x in csv.DictReader(open(OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv')) if x['contest_id'] == c))
            for c in CONTESTS}
    table = {}
    for name, by in variants.items():
        table[name] = {}
        for c, L in by.items():
            sc = np.array([lineup_score(cp, f, key, pts) for cp, f, *_ in L])
            pay = [payout(s, cv[c]) for s in sc]
            paid = [p for p, _ in pay]
            flags = sorted({f for _, f in pay})
            tot = None if any(p is None for p in paid) else round(float(sum(paid)), 2)
            best = float(sc.max())
            table[name][c] = {
                'n': len(L), 'prelock_mean_of_means': round(float(np.mean([x[2] for x in L])), 2),
                'prelock_mean_proxy': round(float(np.mean([x[3] for x in L])), 4),
                'actual_best': round(best, 2), 'actual_mean': round(float(sc.mean()), 2),
                'actual_median': round(float(np.median(sc)), 2),
                'n_ge_owner_best_observed': int((sc >= cv[c]['best_points']).sum()),
                'n_cashing_est': None if cv[c]['cash_line_points_lo'] is None else int((sc >= cv[c]['cash_line_points_lo']).sum()),
                'est_payout': tot, 'est_roi': None if tot is None else round(tot / (fees[c] * len(L)) - 1, 4),
                'payout_from_best_lineup_share': (None if not tot else
                                                  round(max(paid) / tot, 3)),
                'payout_flags': flags,
                'distinct_lineups': len({(cp, tuple(sorted(f))) for cp, f, *_ in L}),
                'distinct_captains': len({cp for cp, *_ in L})}
    # prelock-world comparison of the objective (where it is defined): P(any lineup >= p95 of the v2 lineup pool)
    prelock = {}
    for c, n in CONTESTS.items():
        S_all = {}
        for name in ('V2_FINAL_LIVE', 'ABLATION_TOP_MEAN', 'ABLATION_TOP_PROXY', 'V1'):
            S, _ = _prelock_hits(variants[name][c], key)
            S_all[name] = S
        thr = float(np.percentile(np.concatenate([S_all['V2_FINAL_LIVE'].max(axis=0)]), 50))
        for name, S in S_all.items():
            prelock.setdefault(name, {})[c] = {
                'E_best_lineup_score': round(float(S.max(axis=0).mean()), 2),
                'p_best_ge_v2_median_best': round(float((S.max(axis=0) >= thr).mean()), 4),
                'E_top_score_p95_world': round(float(np.percentile(S.max(axis=0), 95)), 2)}
    actual_return = {c: round(sum(float(x['winnings']) for x in csv.DictReader(open(OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv'))
                                  if x['contest_id'] == c), 2) for c in CONTESTS}
    curve_check = {c: {'actual_return': actual_return[c], 'curve_estimate_for_live': table['V2_FINAL_LIVE'][c]['est_payout']}
                   for c in CONTESTS}
    near_top = {n: {c: round(by[c]['actual_best'] - cv[c]['best_points'], 2) for c in CONTESTS} for n, by in table.items()}
    doc = {'ARTIFACT': 'ATL_NO_PORTFOLIO_STUDY', 'LAYER': 'POSTGAME_DIAGNOSIS',
           'STATUS': 'COUNTERFACTUAL_LEDGER -- ONE GAME, NOT A TEST OF OBJECTIVES, PROMOTES NOTHING',
           'payout_curves': {c: {k: v for k, v in cv[c].items() if k != 'pairs'} for c in CONTESTS},
           'reconciliation': 'V2_FINAL_LIVE realised scores equal the 172 DK-graded owner entries exactly',
           'curve_validation_on_live_portfolio': curve_check,
           'best_lineup_minus_owner_best_observed': near_top,
           'CURVE_LIMIT': ('the curve has one observed point above 130 points (the 6th-place lineup at 142.54); a variant whose '
                           'best lineup lands just below it is assigned the next observed (much lower) payout. V1\'s best '
                           'scored 142.45, 0.09 below the live 6th-place lineup: in a 237,812 field that is a top-10 finish, '
                           'so V1 and V2 were each one lineup from the same result. Read est_payout above 130 points as a '
                           'floor, never as a ranking of variants.'),
           'realised_by_variant': table,
           'prelock_worlds_by_variant': prelock,
           'PRELOCK_METRIC_NOTE': ('computed on the sealed v2 worlds for every variant (V1 lineups re-scored in the v2 '
                                   'worlds); p_best_ge_v2_median_best uses the median of V2_FINAL best-lineup score as '
                                   'the bar. In-sample for V2 (its own worlds) -- the held-out-seed comparison is '
                                   'HOLDOUT_SEED2/HOLDOUT_PORTFOLIO_COMPARISON.json'),
           'CONTESTS_SEPARATE': True,
           'SUCCESSOR_OBJECTIVES_HISTORICAL_TEST': (
               'NOT RUNNABLE YET, and not faked. A historical objective test needs, per archived slate, PRE-KICKOFF sealed '
               'worlds plus full-field standings. Inventory: PIT@CLE has standings and worlds, but the worlds were sealed '
               'AFTER kickoff (forecast_artifact prospective_eligible false, "DESCRIPTIVE ONLY") under an older model; '
               'PHI@CHI has standings and no worlds and no salary file; ATL@NO has pre-kickoff worlds and no standings. '
               'So zero slates meet the bar. Declared successors to score as slates accrue: (O1) dupe-adjusted proxy -- '
               'each hit weighted by 1 / (1 + E[copies]) under the count-scale dupe model (S2 successor); (O2) top-1% '
               'proxy in place of first place, with the field score distribution from the standings-derived shape prior; '
               '(O3) current E[min(hits, m)] unchanged as control. Scored per contest, never pooled across contest sizes.'),
           'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    p = OUT / 'ATL_NO_PORTFOLIO_STUDY.json'
    p.write_text(json.dumps(doc, indent=1, default=float))
    return p, doc


if __name__ == '__main__':
    p, doc = run()
    print(p)
    for name, by in doc['realised_by_variant'].items():
        print(name)
        for c, r in by.items():
            print(f"  {c} n{r['n']:4} best {r['actual_best']:7.2f} med {r['actual_median']:6.2f} payout {r['est_payout']} "
                  f"roi {r['est_roi']} best-share {r['payout_from_best_lineup_share']} flags {r['payout_flags']} "
                  f"distinct {r['distinct_lineups']} cpts {r['distinct_captains']}")
    print(json.dumps(doc['prelock_worlds_by_variant'], indent=0))
