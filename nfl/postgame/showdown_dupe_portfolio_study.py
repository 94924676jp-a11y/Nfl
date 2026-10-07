#!/usr/bin/env python3.12
"""Duplication-aware portfolio objectives on the FROZEN ATL@NO worlds -- pre-registration section 6. SHADOW_ONLY.

    python3.12 nfl/postgame/showdown_dupe_portfolio_study.py [--field-model B3]

Selection on the sealed v2 worlds (seed 20261005); evaluation on the held-out worlds (HOLDOUT_SEED2, seed 20261006).
Contests kept separate (150-max / 20-max / 2-entry). Nothing here changes a production lineup or the objective.

FIELDS (who we are competing against, and how many copies of each candidate exist)
  F-oracle  the realised field composition of that contest, the owner's own entries removed. An upper bound on what a
            perfect duplication model could know; not knowable before lock.
  F-model   a field from a duplication model whose structural parameters were fitted on PIT@CLE only (the archived
            slate that existed before ATL@NO) and whose ownership is the FROZEN prelock BLEND forecast. Knowable before
            lock. Expected copies = N q(L); the field's score distribution is one multinomial draw of N entries.

PAYOUT: ASSUMED prize curve (two power-law segments, floored at the minimum cash) fitted to the owner's 150-max cash
points, the 6th-place tie-group average ($87.50 over places 6-125) and the $100K pool; the 20-max and 2-entry reuse
the shape by rank fraction, rescaled to their pools ($10K / $5K) and minimum cash (2 x fee). DK's tie rule: a lineup
with k identical entries splits the prizes of the k places it occupies. Self-competition between our own entries is
ignored (stated approximation; our 150 entries are 0.06% of the 150-max field).

OBJECTIVES  O0 frozen production portfolio | O0R re-implementation of the production objective E[min(hits, m)] with no
            exposure ladder (isolates the objective from the ladder) | O1 expected split-payout value | O2 production
            objective with each hit divided by (1 + predicted copies) | O3 expected payout with copies ignored.
The realised ATL@NO result is reported as one draw and is never used to choose anything.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_dupe_research as DR  # noqa: E402
from nfl.tools import showdown_portfolio as SP  # noqa: E402
from nfl.tools import showdown_portfolio_audit as PA  # noqa: E402

ATL = _REPO / 'nfl/dfs/salaries/showdown_atl_no'
V2 = ATL / 'RW_INACTIVES_CHARTFIX'
HOLD = ATL / 'HOLDOUT_SEED2'
OUT = _REPO / 'nfl/postgame/dupe_research'
CONTESTS = {'196285137': {'n': 150, 'fee': 0.50, 'pool': 100000.0, 'paid': 49940, 'minc': 1.00, 'N': 237812},
            '196285160': {'n': 20, 'fee': 0.25, 'pool': 10000.0, 'paid': 11410, 'minc': 0.50, 'N': 47562},
            '196285161': {'n': 2, 'fee': 0.10, 'pool': 5000.0, 'paid': 14240, 'minc': 0.20, 'N': 59453}}
FIELD_SEED = 20261007


class PortfolioStudyError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------- payout
def _shape_150():
    mid = [(458, 8.0), (616, 5.47), (2144, 3.0), (2565, 3.0), (4216, 2.0), (6587, 2.0), (10205, 1.5), (12499, 1.5),
           (15827, 1.5), (21608, 1.0)]
    b, a = np.polyfit(np.log([p for p, _ in mid]), np.log([w for _, w in mid]), 1)
    a2, al2 = math.exp(a), -b
    c = CONTESTS['196285137']
    r = np.arange(1, c['paid'] + 1, dtype=float)
    best = None
    for r0 in range(20, 460, 2):
        for al1 in np.linspace(0.5, 3.0, 251):
            A1 = a2 * r0 ** (-al2) * r0 ** al1
            p = np.maximum(np.where(r < r0, A1 * r ** (-al1), a2 * r ** (-al2)), c['minc'])
            e = abs(p.sum() - c['pool']) / c['pool'] + abs(p[5:125].mean() - 87.5) / 87.5
            if best is None or e < best[0]:
                best = (e, r0, al1, A1)
    e, r0, al1, A1 = best
    return {'r0': r0, 'alpha_top': float(al1), 'A_top': float(A1), 'alpha_mid': float(al2), 'A_mid': float(a2),
            'fit_err': float(e)}


def prize_curves():
    sh = _shape_150()
    base = CONTESTS['196285137']
    out = {}
    for cid, c in CONTESTS.items():
        r = np.arange(1, c['paid'] + 1, dtype=float)
        rr = r * base['N'] / c['N']           # same shape by rank fraction
        raw = np.where(rr < sh['r0'], sh['A_top'] * rr ** (-sh['alpha_top']), sh['A_mid'] * rr ** (-sh['alpha_mid']))
        lo, hi = 1e-6, 1e6
        for _ in range(100):
            k = math.sqrt(lo * hi)
            if np.maximum(k * raw, c['minc']).sum() > c['pool']:
                hi = k
            else:
                lo = k
        prize = np.maximum(k * raw, c['minc'])
        cum = np.concatenate([[0.0], np.cumsum(prize)])
        out[cid] = {'prize': prize, 'cum': cum, 'top': float(prize[0]), 'pool_check': float(prize.sum())}
    return out, sh


def split_payout(rank, k, cum):
    """Average prize over places rank .. rank + k - 1 (k may be fractional); 0 beyond the paid places."""
    P = len(cum) - 1
    lo = np.clip(rank - 1, 0, P)
    hi = np.clip(rank - 1 + k, 0, P)
    ilo, ihi = np.floor(lo).astype(int), np.floor(hi).astype(int)
    prize = np.diff(cum)
    v_hi = cum[np.minimum(ihi, P)] + (hi - ihi) * prize[np.minimum(ihi, P - 1)] * (ihi < P)
    v_lo = cum[np.minimum(ilo, P)] + (lo - ilo) * prize[np.minimum(ilo, P - 1)] * (ilo < P)
    return (v_hi - v_lo) / k


# ----------------------------------------------------------------------------------------------- worlds
def worlds(draws_dir, R):
    """(by-key draws, world optimum, candidate score matrix) for the sealed candidates on a draws file."""
    sc = json.loads((V2 / 'SCENARIO.json').read_text())
    L = SP.load(_REPO / sc['export'], next(draws_dir.glob('SHOWDOWN_*_DRAWS.json')), sc['absent_in_state']).value
    rows = SP.players_table(L['slate'], L['absent'], L['draws'])
    by = {r['key']: r for r in rows}
    opt = SP.world_optimum(rows).value['opt']
    M = SP.score_matrix(R['cands'], by)
    return by, np.asarray(opt, float), M


def field_scores(lineups, weights, by, chunk=200):
    """Per world: field scores sorted descending with cumulative weights (for rank lookups)."""
    keys = list(by)
    kix = {k: i for i, k in enumerate(keys)}
    n_w = max(len(np.atleast_1d(by[k]['draws'])) for k in keys if by[k].get('draws') is not None)
    # an absent (inactive) player carries no draws: he scores 0 in every world
    D = np.stack([np.asarray(by[k]['draws'], np.float32) if by[k].get('draws') is not None
                  and len(np.atleast_1d(by[k]['draws'])) == n_w else np.zeros(n_w, np.float32) for k in keys])
    C = np.array([kix[c] for c, _ in lineups])
    Fm = np.array([[kix[x] for x in f] for _, f in lineups])
    W = np.asarray(weights, float)
    n_w = D.shape[1]
    out = []
    for s in range(0, n_w, chunk):
        d = D[:, s:s + chunk]
        S = 1.5 * d[C] + d[Fm].sum(axis=1)
        for j in range(S.shape[1]):
            o = np.argsort(-S[:, j])
            out.append((S[o, j], np.cumsum(W[o])))
    return out


def rank_in_field(scores, fs):
    """rank = 1 + field weight strictly above (2-decimal tolerance), for a candidate score matrix (cands x worlds)."""
    R = np.empty_like(scores)
    for w, (s_desc, cw) in enumerate(fs):
        idx = np.searchsorted(-s_desc, -(scores[:, w] + 0.005), side='left')
        R[:, w] = 1 + np.where(idx > 0, cw[np.maximum(idx - 1, 0)], 0.0)
    return R


# --------------------------------------------------------------------------------------------- objectives
def greedy_cover(H, n, m, weights=None):
    """Greedy for E_w[min(sum_c w_c h_cw, m)] -- the production objective's form (no exposure ladder)."""
    Hw = H * (1.0 if weights is None else weights[:, None])
    depth = np.zeros(H.shape[1])
    chosen = []
    avail = np.ones(H.shape[0], bool)
    for _ in range(n):
        gain = np.minimum(depth[None, :] + Hw, m).mean(axis=1) - np.minimum(depth, m).mean()
        gain[~avail] = -np.inf
        i = int(np.argmax(gain))
        chosen.append(i)
        avail[i] = False
        depth += Hw[i]
    return chosen


def evaluate(chosen, Pay, M, H, copies, fee, cpts):
    sel = np.array(chosen)
    tot = Pay[sel].sum(axis=0)
    return {'E_payout': round(float(tot.mean()), 3), 'roi': round(float(tot.mean() / (fee * len(sel)) - 1), 4),
            'p_any_hit': round(float((H[sel].sum(axis=0) > 0).mean()), 4),
            'E_best_score': round(float(M[sel].max(axis=0).mean()), 2),
            'mean_lineup_projection': round(float(M[sel].mean()), 2),
            'mean_predicted_copies': round(float(np.mean(copies[sel])), 2),
            'distinct_captains': len({cpts[i] for i in sel})}


def run(field_model):
    R = PA.rebuild(_REPO / json.loads((V2 / 'SCENARIO.json').read_text())['export'], V2)
    cands = R['cands']
    curves, shape = prize_curves()
    byA, optA, MA = R['by'], np.asarray(R['opt'], float), R['M']
    byB, optB, MB = worlds(HOLD, R)
    HA = MA >= (1 - SP.BAND) * optA[None, :]
    HB = MB >= (1 - SP.BAND) * optB[None, :]
    name_of = {k: v['name'] for k, v in byA.items()}
    key_of = {v: k for k, v in name_of.items()}
    cpts = [name_of[c] for c, _ in cands]
    from nfl.postgame import showdown_atl_no_field_actual as FA
    owner = list(csv.DictReader(open(_REPO / 'nfl/postgame/showdown_atl_no_2026W4/ATL_NO_OWNER_ENTRIES_GRADED.csv')))
    fm = field_model_universe(field_model)
    doc = {'ARTIFACT': 'SHOWDOWN_DUPE_PORTFOLIO_STUDY', 'STATUS': 'SHADOW_ONLY -- EXPLORATORY',
           'prize_curve_shape': shape, 'prize_curves': {c: {'top_prize': round(v['top'], 1), 'pool': round(v['pool_check'], 1)}
                                                     for c, v in curves.items()},
           'field_model': fm['spec'], 'contests': {}}
    for cid, c in CONTESTS.items():
        S_ = FA.load_standings(cid)
        mine = {r['entry_id'] for r in owner if r['contest_id'] == cid}
        cnt = collections.Counter((key_of[e['cpt']], tuple(sorted(key_of[x] for x in e['flex'])))
                                  for e in S_['entries'] if e['entry_id'] not in mine)
        fields = {'F_oracle': (list(cnt), [cnt[k] for k in cnt], np.array([cnt.get((cc, tuple(sorted(f))), 0) for cc, f in cands], float))}
        lin, wts, cop = model_field(fm, cid, c['N'] - len(mine), key_of, cands)
        fields['F_model'] = (lin, wts, cop)
        res = {'n': c['n'], 'fields': {}}
        for fname, (lin, wts, cop) in fields.items():
            fsA, fsB = field_scores(lin, wts, byA), field_scores(lin, wts, byB)
            rkA, rkB = rank_in_field(MA, fsA), rank_in_field(MB, fsB)
            k = 1.0 + cop[:, None]
            payA, payB = split_payout(rkA, k, curves[cid]['cum']), split_payout(rkB, k, curves[cid]['cum'])
            nosA = split_payout(rkA, np.ones_like(k), curves[cid]['cum'])
            m = SP.depth_m(c['n'])
            frozen = R['finals'][cid]
            ports = {'O0_production_frozen': list(frozen),
                     'O0R_objective_no_ladder': greedy_cover(HA, c['n'], m),
                     'O1_ev_split': list(np.argsort(-payA.mean(axis=1))[:c['n']]),
                     'O2_hits_over_1_plus_copies': greedy_cover(HA, c['n'], m, 1.0 / (1.0 + cop)),
                     'O3_ev_ignoring_copies': list(np.argsort(-nosA.mean(axis=1))[:c['n']])}
            ev = {}
            for o, ch in ports.items():
                ev[o] = {'selection_worlds_seed_20261005': evaluate(ch, payA, MA, HA, cop, c['fee'], cpts),
                         'HELD_OUT_worlds_seed_20261006': evaluate(ch, payB, MB, HB, cop, c['fee'], cpts),
                         'overlap_with_production': len(set(ch) & set(frozen))}
            res['fields'][fname] = {'objectives': ev,
                                    'payout_decomposition_held_out': decompose(payB, MB, cop, ports)}
        res['realised_one_draw'] = realised(ports, cands, name_of, cid, curves, cnt, c)
        doc['contests'][cid] = res
    doc['written_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / 'DUPE_PORTFOLIO_STUDY.json'
    p.write_text(json.dumps(doc, indent=1, default=float))
    return p, doc


def decompose(Pay, M, cop, ports):
    """Separate strength, duplication and split value per objective (held-out worlds)."""
    out = {}
    for o, ch in ports.items():
        sel = np.array(ch)
        out[o] = {'mean_projection': round(float(M[sel].mean()), 2), 'mean_copies': round(float(cop[sel].mean()), 2),
                  'median_copies': float(np.median(cop[sel])),
                  'E_split_payout_per_lineup': round(float(Pay[sel].mean()), 4)}
    return out


def realised(ports, cands, name_of, cid, curves, cnt_oracle, c):
    """One draw: each objective's lineups scored on the actual game, placed in the real field (exact rank), paid on the
    ASSUMED curve with the REAL tie counts. Reported, never used to choose."""
    act = json.loads((_REPO / 'nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json').read_text())['player_actuals']
    pts = {k: float(v['dk_A']) for k, v in act.items()}
    sc = np.array([1.5 * pts.get(cc, 0.0) + sum(pts.get(x, 0.0) for x in f) for cc, f in cands])
    field = np.array([1.5 * pts.get(cc, 0.0) + sum(pts.get(x, 0.0) for x in f) for cc, f in cnt_oracle])
    w = np.array([cnt_oracle[k] for k in cnt_oracle], float)
    o = np.argsort(-field)
    fs = [(field[o], np.cumsum(w[o]))]
    rk = rank_in_field(sc[:, None], fs)[:, 0]
    cop = np.array([cnt_oracle.get((cc, tuple(sorted(f))), 0) for cc, f in cands], float)
    pay = split_payout(rk, 1 + cop, curves[cid]['cum'])
    return {o_: {'assumed_curve_payout': round(float(pay[ch].sum()), 2), 'best_rank': int(rk[ch].min()),
                 'roi': round(float(pay[ch].sum() / (c['fee'] * len(ch)) - 1), 4)} for o_, ch in ports.items()}


# ------------------------------------------------------------------------------------------- field model
def field_model_universe(name):
    """Structural parameters fitted on PIT@CLE ONLY (prelock-available); applied to the frozen BLEND ownership."""
    feats = {'B1': [], 'B3S': ['stack_cpt_pc_own_qb', 'both_qbs', 'split_5_1', 'split_4_2', 'any_k_dst'],
             'B2': [f'sal_{n}' for n in DR.SAL_NAMES[:4]]}
    feats['B3'] = feats['B2'] + feats['B3S']
    feats['B4'] = feats['B3'] + ['fc_gap_pts', 'fc_top100']
    names = feats[name]
    sl = DR.load_slates()
    Upit = DR.build_universe(sl['PIT_CLE'])
    theta, info = DR.maxent_train([Upit], names)
    blend = {r['player']: r for r in csv.DictReader(open(ATL / 'SHADOW_RW_INACTIVES_CHARTFIX_BLEND/SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv'))}
    cpt = {p: float(r['shadow_cpt_own_pct']) / 100 for p, r in blend.items()}
    flx = {p: float(r['shadow_flex_own_pct']) / 100 for p, r in blend.items()}
    meta = sl['ATL_NO_160']['meta']
    fc = sl['ATL_NO_160']['fc'] if 'fc_gap_pts' in names else None
    del Upit
    U = DR.forecast_universe('ATL_NO_FORECAST', cpt, flx, meta, fc, 1)
    lq, minfo = DR.maxent_fit_marginals(U, theta, names)
    return {'U': U, 'q': np.exp(lq), 'spec': {'model': name, 'theta_fitted_on': 'PIT_CLE only',
                                             'theta': dict(zip(names, [round(float(x), 4) for x in theta])),
                                             'ownership': 'FROZEN prelock BLEND (SHADOW_RW_INACTIVES_CHARTFIX_BLEND)',
                                             'train': info, 'marginals': minfo}}


def model_field(fm, cid, N, key_of, cands):
    U, q = fm['U'], fm['q']
    rng = np.random.default_rng(FIELD_SEED + int(cid) % 1000)
    draw = rng.multinomial(N, q)
    nz = np.flatnonzero(draw)
    P = U['players']
    lin = [(key_of[P[U['cpt'][i]]], tuple(sorted(key_of[P[j]] for j in U['flex'][i]))) for i in nz]
    cop = []
    for cc, f in cands:
        loc = DR.locate(U, _name(cc), [_name(x) for x in f])
        cop.append(0.0 if loc is None else float(N * q[loc]))
    return lin, list(draw[nz].astype(float)), np.array(cop)


def _name(key):
    return key.split('|')[0]


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--field-model', default='B3')
    a = ap.parse_args()
    p, doc = run(a.field_model)
    print(p)
    print(json.dumps({'shape': doc['prize_curve_shape'], 'curves': doc['prize_curves'], 'field_model': doc['field_model']['theta']}))
    for cid, c in doc['contests'].items():
        print('CONTEST', cid)
        for f, r in c['fields'].items():
            for o, e in r['objectives'].items():
                h = e['HELD_OUT_worlds_seed_20261006']
                print(f"  {f:8} {o:28} heldout E$ {h['E_payout']:8.3f} roi {h['roi']:7.3f} hit {h['p_any_hit']:.3f} "
                      f"best {h['E_best_score']:6.1f} copies {h['mean_predicted_copies']:7.2f} cpts {h['distinct_captains']} "
                      f"overlap {e['overlap_with_production']}")
        print('  realised', c['realised_one_draw'])
