#!/usr/bin/env python3.12
"""Showdown complete-lineup duplication research -- DEFECT-DUPE-UNDERESTIMATE. SHADOW_ONLY.

    python3.12 nfl/field/showdown_dupe_research.py            # diagnosis + model ladder + leave-one-slate-out

Pre-registration: docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md (committed 2318d267 before this ran). Evidence:
nfl/postgame/showdown_atl_no_2026W4/evidence/DEFECT_DUPE_UNDERESTIMATE.json. Outputs go to nfl/postgame/dupe_research/.
Nothing here is a football input, changes a production lineup, or touches the portfolio objective.

THE UNIVERSE. For each contest, every lineup of 1 CPT + 5 distinct FLEX drawn from its 32 most-entered players,
with both teams represented (DK rule) and salary <= $50,000 where salaries exist. Scoring on this universe includes
the lineups nobody played (0 copies), which removes the truncation that biased the observed-only analysis.

THE MODELS (simplest first; ids as pre-registered). B0 independence (current E1); B0n renormalised B0; B5 B0 x one
constant; B6 B0 x salary-bucket constants; B1 maximum entropy subject to the exact slot marginals on the feasible
universe; B2 + salary-left; B3 + construction; B3S B1 + construction only (salary-free, all slates); B4 B3 + FC
optimizer term; B7 Poisson regression of copies on the universe. B1-B4 / B3S are exponential families
q(L) = exp(a[cpt] + sum b[flex] + theta . F(L)) / Z: a, b always solved to the contest's own slot marginals (the
ownership INPUT); theta fitted only on OTHER slates by maximum likelihood, a and b profiled.

FC projections are used only as a description of what the field's optimizers see, never as a football input.
"""
from __future__ import annotations

import ast
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_history_calibration as HC  # noqa: E402

OUT = _REPO / 'nfl/postgame/dupe_research'
K_PLAYERS = 32
CAP = 50000
ATL_EXPORT = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv'
ATL_FC = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/THIRDPARTY_FC_showdown_ATL_NO_2026W4_CONTEXT_ONLY.4939e14fc826ab4c.csv'
SAL_EDGES = ((0, 0), (100, 500), (600, 900), (1000, 1900), (2000, 10 ** 9))
SAL_NAMES = ('0', '100-500', '600-900', '1000-1900', '2000+')
PRED_BINS = (0, 0.1, 1, 3, 10, 30, 100, math.inf)
TOP_ACTUAL = 50
TOP_PRED = 1000
TOP_FC = 150
SLATE_IDS = ('PIT_CLE', 'PHI_CHI', 'ATL_NO_160', 'ATL_NO_137', 'ATL_NO_161')
TRAIN_OF = {'PIT_CLE': 'PIT_CLE', 'PHI_CHI': 'PHI_CHI', 'ATL_NO_160': 'ATL_NO', 'ATL_NO_137': 'ATL_NO', 'ATL_NO_161': 'ATL_NO'}
TRAINING_CONTEST = {'PIT_CLE': 'PIT_CLE', 'PHI_CHI': 'PHI_CHI', 'ATL_NO': 'ATL_NO_160'}


class DupeResearchError(RuntimeError):
    pass


def need(c, code, detail=''):
    if not c:
        raise DupeResearchError(f'{code}: {detail}')


# ------------------------------------------------------------------------------------------------- slates
def _fc(path):
    rows = list(csv.reader(open(path, newline='', encoding='utf-8-sig')))
    hdr = next(i for i, r in enumerate(rows) if 'Player' in r and 'FC Proj' in r)
    H = {h: j for j, h in enumerate(rows[hdr])}
    out = {}
    for r in rows[hdr + 1:]:
        if len(r) > H['FC Proj'] and r[H['Player']] and r[H['Pos']] != 'CPTN':
            try:
                out[r[H['Player']]] = float(r[H['FC Proj']])
            except ValueError:
                pass
    need(out, 'FC_EMPTY', str(path))
    return out


def _pool_meta(export):
    from nfl.tools import showdown_to_portfolio as S
    ing = S.s1_ingest(export)
    need(ing.state.value == 'PASS', 'EXPORT_INGEST', ing.detail)
    si = S.s2_slate_identity(ing.value['pool'])
    need(si.state.value == 'PASS', 'SLATE_IDENTITY', si.detail)
    meta = {}
    for v in si.value['players'].values():
        need(v['name'] not in meta, 'POOL_NAME_NOT_UNIQUE', v['name'])
        meta[v['name']] = {'team': v['dk_team'], 'position': v['position'], 'flex_salary': v['flex']['salary'],
                           'cpt_salary': v['cpt']['salary']}
    return meta


def load_slates():
    sl = {}
    for c in HC.CONTESTS:
        R = HC.load_raw(c)
        names = {e['cpt'] for e in R['entries']} | {f for e in R['entries'] for f in e['flex']}
        if c['metadata'] == 'DK_POOL':
            meta, _slate, _ = HC.pit_metadata()
            fc = _fc(HC.PIT_FC)
        else:
            meta, _ = HC.phi_metadata(names, c['roster_week'])
            fc = None
        sl[c['label']] = {'id': c['label'], 'contest_id': c['contest_id'], 'size': '20-max',
                          'entries': [{'cpt': e['cpt'], 'flex': e['flex'], 'user': e['user']} for e in R['entries']],
                          'meta': meta, 'fc': fc, 'raw_sha256': R['sha256'], 'has_salary': c['metadata'] == 'DK_POOL'}
    from nfl.postgame import showdown_atl_no_field_actual as FA
    meta, fc = _pool_meta(ATL_EXPORT), _fc(ATL_FC)
    for cid, sid, size in (('196285160', 'ATL_NO_160', '20-max'), ('196285137', 'ATL_NO_137', '150-max'),
                           ('196285161', 'ATL_NO_161', '2-entry')):
        S_ = FA.load_standings(cid)
        sl[sid] = {'id': sid, 'contest_id': cid, 'size': size,
                   'entries': [{'cpt': e['cpt'], 'flex': e['flex'], 'user': e['user'], 'entry_id': e['entry_id']}
                               for e in S_['entries']],
                   'meta': meta, 'fc': fc, 'raw_sha256': S_['rec']['sha256'], 'has_salary': True}
    for s in sl.values():
        need(s['entries'], 'NO_ENTRIES', s['id'])
    return sl


# ---------------------------------------------------------------------------------------------- universe
_COMBOS = np.array(list(itertools.combinations(range(K_PLAYERS), 5)), dtype=np.int8)


def _code(cpt, flex_sorted):
    code = cpt.astype(np.int64)
    for k in range(5):
        code = code * K_PLAYERS + flex_sorted[:, k].astype(np.int64)
    return code


def universe_from_players(sid, players, meta, fc, has_salary):
    """The feasible lineup universe over `players` (structure and features only; no counts)."""
    need(len(players) == K_PLAYERS, 'TOO_FEW_PLAYERS', sid)
    team_names = sorted({meta[p]['team'] for p in players if meta.get(p, {}).get('team')})
    need(len(team_names) == 2, 'TEAMS', f"{sid} {team_names}")
    team = np.array([team_names.index(meta[p]['team']) if meta.get(p, {}).get('team') else -1 for p in players])
    pos = [meta.get(p, {}).get('position', 'UNMAPPED') for p in players]
    unm = [p for i, p in enumerate(players) if pos[i] == 'UNMAPPED' or team[i] < 0]
    need(not unm, 'UNMAPPED_PLAYERS_IN_UNIVERSE', f"{sid} {unm}")
    cs, fs = [], []
    for c in range(K_PLAYERS):
        m = ~np.any(_COMBOS == c, axis=1)
        fs.append(_COMBOS[m])
        cs.append(np.full(int(m.sum()), c, dtype=np.int8))
    cpt, flex = np.concatenate(cs), np.concatenate(fs)
    n0 = np.concatenate([team[cpt][:, None], team[flex]], axis=1).sum(axis=1)
    feas = (n0 > 0) & (n0 < 6)
    sal_left = None
    if has_salary:
        fsal = np.array([meta[p]['flex_salary'] for p in players])
        csal = np.array([meta[p]['cpt_salary'] for p in players])
        used = csal[cpt] + fsal[flex].sum(axis=1)
        feas &= used <= CAP
        sal_left = CAP - used
    cpt, flex, n0 = cpt[feas], flex[feas], n0[feas]
    if sal_left is not None:
        sal_left = sal_left[feas]
    code = _code(cpt, flex)
    order = np.argsort(code)
    cpt, flex, n0, code = cpt[order], flex[order], n0[order], code[order]
    if sal_left is not None:
        sal_left = sal_left[order]
    is_qb = np.array([q == 'QB' for q in pos])
    is_pc = np.array([q in ('WR', 'TE') for q in pos])
    is_kd = np.array([q in ('K', 'DST') for q in pos])
    stack = is_pc[cpt] & np.any(is_qb[flex] & (team[flex] == team[cpt][:, None]), axis=1)
    nqb = is_qb[cpt].astype(int) + is_qb[flex].sum(axis=1)
    big = np.maximum(n0, 6 - n0)
    feats = {'stack_cpt_pc_own_qb': stack.astype(float), 'both_qbs': (nqb >= 2).astype(float),
             'split_5_1': (big == 5).astype(float), 'split_4_2': (big == 4).astype(float),
             'any_k_dst': (is_kd[cpt] | np.any(is_kd[flex], axis=1)).astype(float)}
    if sal_left is not None:
        b = np.zeros(len(sal_left), dtype=np.int8)
        for i, (lo, hi) in enumerate(SAL_EDGES):
            b[(sal_left >= lo) & (sal_left <= hi)] = i
        for i in range(4):
            feats[f'sal_{SAL_NAMES[i]}'] = (b == i).astype(float)
    proj = None
    if fc is not None:
        fcv = np.array([fc.get(p, 0.0) for p in players])
        proj = 1.5 * fcv[cpt] + fcv[flex].sum(axis=1)
        feats['fc_gap_pts'] = proj - proj.max()
        top = np.zeros(len(proj))
        top[np.argsort(-proj)[:100]] = 1.0
        feats['fc_top100'] = top
    return {'id': sid, 'players': players, 'pos': pos, 'team': team, 'cpt': cpt, 'flex': flex, 'code': code,
            'feats': feats, 'sal_left': sal_left, 'proj': proj, 'has_salary': has_salary, 'has_fc': fc is not None}


def locate(U, cpt_name, flex_names):
    """Row of a named lineup in U, or None."""
    pidx = {p: i for i, p in enumerate(U['players'])}
    ids = [pidx.get(cpt_name)] + [pidx.get(x) for x in flex_names]
    if None in ids:
        return None
    c = _code(np.array([ids[0]], dtype=np.int8), np.sort(np.array(ids[1:], dtype=np.int8))[None, :])[0]
    loc = int(np.searchsorted(U['code'], c))
    return loc if loc < len(U['code']) and U['code'][loc] == c else None


def forecast_universe(sid, cpt_share, flex_share, meta, fc, N):
    """A universe from FORECAST slot ownership only (no entries): the 32 players with the largest forecast total
    ownership; targets are the forecast shares renormalised inside the universe. Used for prelock-knowable fields."""
    tot = {p: cpt_share.get(p, 0.0) + flex_share.get(p, 0.0) for p in set(cpt_share) | set(flex_share)}
    players = sorted(tot, key=lambda p: -tot[p])[:K_PLAYERS]
    U = universe_from_players(sid, players, meta, fc, all(meta[p].get('flex_salary') for p in players))
    c = np.array([cpt_share.get(p, 0.0) for p in players])
    f = np.array([flex_share.get(p, 0.0) for p in players])
    U.update({'N': N, 'n_in': float(N), 'counts': np.zeros(len(U['cpt'])), 'coverage': None,
              'c_sh': c, 'f_sh': f, 't_c': c / c.sum(), 't_f': np.clip(5 * f / f.sum(), 0, 1 - 1e-6)})
    return U


def build_universe(s):
    ent = s['entries']
    app = collections.Counter()
    for e in ent:
        app[e['cpt']] += 1
        for x in e['flex']:
            app[x] += 1
    players = [p for p, _ in app.most_common(K_PLAYERS)]
    U = universe_from_players(s['id'], players, s['meta'], s['fc'], s['has_salary'])
    pidx = {p: i for i, p in enumerate(players)}
    code = U['code']
    e_code, users = [], []
    for e in ent:
        ids = [pidx.get(e['cpt'])] + [pidx.get(x) for x in e['flex']]
        if None in ids:
            continue
        f = np.sort(np.array(ids[1:], dtype=np.int8))
        e_code.append(_code(np.array([ids[0]], dtype=np.int8), f[None, :])[0])
        users.append(e['user'])
    e_code = np.array(e_code, dtype=np.int64)
    loc = np.searchsorted(code, e_code)
    ok = (loc < len(code)) & (code[np.minimum(loc, len(code) - 1)] == e_code)
    need(ok.mean() > 0.999, 'ENTRIES_OUTSIDE_FEASIBLE_SET', f"{s['id']} {1 - ok.mean():.4f}")
    counts = np.bincount(loc[ok], minlength=len(code)).astype(float)
    N = len(ent)
    c_all = collections.Counter(e['cpt'] for e in ent)
    f_all = collections.Counter(x for e in ent for x in e['flex'])
    n_in = counts.sum()
    by_line_users = collections.defaultdict(collections.Counter)
    for l_, u in zip(loc[ok], np.array(users)[ok]):
        by_line_users[int(l_)][u] += 1
    U.update({'contest_id': s['contest_id'], 'size': s['size'], 'counts': counts, 'N': N, 'n_in': float(n_in),
              'coverage': float(n_in / N),
              'c_sh': np.array([c_all[p] / N for p in players]), 'f_sh': np.array([f_all[p] / N for p in players]),
              't_c': np.bincount(U['cpt'], weights=counts, minlength=K_PLAYERS) / n_in,
              't_f': sum(np.bincount(U['flex'][:, k], weights=counts, minlength=K_PLAYERS) for k in range(5)) / n_in,
              'dup_entries': int(sum(sum(v.values()) - 1 for v in by_line_users.values())),
              'self_dup_entries': int(sum(sum(n - 1 for n in v.values()) for v in by_line_users.values())),
              'raw_sha256': s['raw_sha256']})
    return U


# ------------------------------------------------------------------------------------------------ models
def logE1(U, c_sh=None, f_sh=None):
    c_sh = U['c_sh'] if c_sh is None else c_sh
    f_sh = U['f_sh'] if f_sh is None else f_sh
    with np.errstate(divide='ignore'):
        lc, lf = np.log(c_sh), np.log(f_sh)
    return np.log(U['N']) + lc[U['cpt']] + lf[U['flex']].sum(axis=1)


def _F(U, names):
    return np.column_stack([U['feats'][n] for n in names]) if names else np.zeros((len(U['cpt']), 0))


def _cols(U):
    if '_fc' not in U:
        U['_fc'] = [np.ascontiguousarray(U['flex'][:, k]).astype(np.int64) for k in range(5)]
        U['_cc'] = U['cpt'].astype(np.int64)
    return U['_cc'], U['_fc']


def _stats(U, a, b, th, F):
    """log Z, sufficient-statistic means and the full covariance (Hessian of log Z) of the exponential family
    q(L) = exp(a[cpt] + sum_k b[flex_k] + F th) / Z over the universe. CPT one-hot (32), FLEX indicators (32), F."""
    cc, fc = _cols(U)
    K = K_PLAYERS
    s = a[cc] + b[fc[0]] + b[fc[1]] + b[fc[2]] + b[fc[3]] + b[fc[4]]
    if F.shape[1]:
        s = s + F @ th
    mx = s.max()
    w = np.exp(s - mx)
    Z = w.sum()
    q = w / Z
    logZ = math.log(Z) + mx
    m_c = np.bincount(cc, weights=q, minlength=K)
    m_f = sum(np.bincount(f, weights=q, minlength=K) for f in fc)
    P_cf = sum(np.bincount(cc * K + f, weights=q, minlength=K * K) for f in fc).reshape(K, K)
    P_ff = np.zeros((K, K))
    for i in range(5):
        for j in range(i + 1, 5):
            P_ff += np.bincount(fc[i] * K + fc[j], weights=q, minlength=K * K).reshape(K, K)
    P_ff = P_ff + P_ff.T + np.diag(m_f)
    d = F.shape[1]
    n = 2 * K + d
    H = np.zeros((n, n))
    H[:K, :K] = np.diag(m_c) - np.outer(m_c, m_c)
    H[:K, K:2 * K] = P_cf - np.outer(m_c, m_f)
    H[K:2 * K, K:2 * K] = P_ff - np.outer(m_f, m_f)
    E_F = q @ F if d else np.zeros(0)
    if d:
        qF = F * q[:, None]
        G_c = np.stack([np.bincount(cc, weights=qF[:, j], minlength=K) for j in range(d)], axis=1)
        G_f = np.stack([sum(np.bincount(f, weights=qF[:, j], minlength=K) for f in fc) for j in range(d)], axis=1)
        H[:K, 2 * K:] = G_c - np.outer(m_c, E_F)
        H[K:2 * K, 2 * K:] = G_f - np.outer(m_f, E_F)
        H[2 * K:, 2 * K:] = qF.T @ F - np.outer(E_F, E_F)
    H = np.triu(H) + np.triu(H, 1).T
    return logZ, m_c, m_f, E_F, H, q


def _expfam(Us, names, theta_fixed=None, iters=40, tol=2e-6):
    """Joint maximum likelihood over one or more contests: per-contest a, b (always matched to that contest's own
    marginals at the optimum) and, unless theta_fixed is given, a shared theta. Convex; Newton with backtracking.
    Players with a zero target in a slot are pinned at -50 in that slot."""
    K = K_PLAYERS
    d = len(names)
    Fs = [_F(U, names) for U in Us]
    Eo = [(U['counts'] @ F) / U['n_in'] if d else np.zeros(0) for U, F in zip(Us, Fs)]
    st = []
    for U in Us:
        with np.errstate(divide='ignore'):
            a0, b0 = np.log(U['t_c']), np.log(np.clip(U['t_f'], 0, 1 - 1e-9) / np.clip(1 - U['t_f'], 1e-9, 1))
        live = np.concatenate([U['t_c'] > 0, U['t_f'] > 0])
        a0[~live[:K]], b0[~live[K:]] = -50.0, -50.0
        if '_ab' in U:
            a0, b0 = U['_ab'][0].copy(), U['_ab'][1].copy()
        st.append({'a': a0, 'b': b0, 'live': live})
    th = np.zeros(d) if theta_fixed is None else np.asarray(theta_fixed, float)
    free_th = theta_fixed is None and d > 0

    def evaluate(states, th):
        ll, out = 0.0, []
        for U, F, e, x in zip(Us, Fs, Eo, states):
            logZ, m_c, m_f, E_F, H, q = _stats(U, x['a'], x['b'], th, F)
            la = x['a'][x['live'][:K]] @ U['t_c'][x['live'][:K]] + x['b'][x['live'][K:]] @ U['t_f'][x['live'][K:]]
            ll += U['n_in'] * (la + (th @ e if d else 0.0) - logZ)
            out.append((m_c, m_f, E_F, H, q))
        return ll, out

    ll, res = evaluate(st, th)
    for it in range(iters):
        blocks, grads = [], []
        n_free = [int(x['live'].sum()) for x in st]
        tot = sum(n_free) + (d if free_th else 0)
        Hb = np.zeros((tot, tot))
        g = np.zeros(tot)
        off = 0
        gmax = 0.0
        for U, x, e, (m_c, m_f, E_F, H, q) in zip(Us, st, Eo, res):
            L = x['live']
            gi = np.concatenate([U['t_c'] - m_c, U['t_f'] - m_f])[L]
            gmax = max(gmax, float(np.max(np.abs(gi))))
            Hi = H[:2 * K, :2 * K][np.ix_(L, L)]
            nf = int(L.sum())
            Hb[off:off + nf, off:off + nf] = U['n_in'] * Hi
            g[off:off + nf] = U['n_in'] * gi
            if free_th:
                C = H[:2 * K, 2 * K:][L]
                Hb[off:off + nf, -d:] = U['n_in'] * C
                Hb[-d:, off:off + nf] = U['n_in'] * C.T
                Hb[-d:, -d:] += U['n_in'] * H[2 * K:, 2 * K:]
                g[-d:] += U['n_in'] * (e - E_F)
                gmax = max(gmax, float(np.max(np.abs(e - E_F))))
            off += nf
        if gmax < tol:
            break
        ridge = 1e-9 * max(1.0, np.trace(Hb) / len(Hb))
        step = np.linalg.solve(Hb + ridge * np.eye(len(Hb)), g)
        t = 1.0
        while True:
            new_st, off = [], 0
            for x in st:
                L = x['live']
                v = np.concatenate([x['a'], x['b']])
                nf = int(L.sum())
                v[L] = v[L] + t * step[off:off + nf]
                off += nf
                new_st.append({'a': v[:K], 'b': v[K:], 'live': L})
            new_th = th + t * step[-d:] if free_th else th
            ll2, res2 = evaluate(new_st, new_th)
            if ll2 >= ll - 1e-7 * abs(ll) or t < 1e-4:
                break
            t /= 2
        st, th, ll, res = new_st, new_th, ll2, res2
    need(gmax < 1e-4, 'EXPFAM_NOT_CONVERGED', f"{[U['id'] for U in Us]} {names} gmax {gmax:.2e}")
    for U, x in zip(Us, st):
        U['_ab'] = (x['a'], x['b'])
    return th, [np.log(np.maximum(r[4], 1e-300)) for r in res], {'iters': it + 1, 'max_abs_grad': gmax, 'loglik': round(ll, 2)}


def maxent_fit_marginals(U, theta, names):
    """a, b solved to U's own slot marginals with theta fixed; returns log q over the universe."""
    _, lqs, info = _expfam([U], names, theta_fixed=np.asarray(theta, float) if names else None)
    return lqs[0], info


def maxent_train(Us, names):
    """theta by joint maximum likelihood over the training contests (their a, b free)."""
    if not names:
        return np.zeros(0), {'iters': 0}
    th, _, info = _expfam(Us, names)
    return th, info


def poisson_train(Us, names):
    """B7: Poisson GLM over every universe row of the training contests (zeros included). IRLS."""
    X = np.concatenate([np.column_stack([np.ones(len(U['cpt'])), np.maximum(logE1(U), -40), _F(U, names)]) for U in Us])
    y = np.concatenate([U['counts'] for U in Us])
    beta = np.zeros(X.shape[1])
    beta[0] = math.log(max(y.mean(), 1e-9))
    for _ in range(60):
        eta = np.clip(X @ beta, -50, 20)
        mu = np.exp(eta)
        z = eta + (y - mu) / np.maximum(mu, 1e-12)
        W = mu
        new = np.linalg.solve(X.T @ (W[:, None] * X) + 1e-8 * np.eye(X.shape[1]), X.T @ (W * z))
        if np.max(np.abs(new - beta)) < 1e-8:
            beta = new
            break
        beta = new
    return beta


def predictions(U, train_Us, names_all):
    """Every pre-registered model's predicted copies on U (test), fitted on train_Us only."""
    P, info = {}, {}
    lE = logE1(U)
    e1 = np.exp(lE)
    P['B0'] = e1
    P['B0n'] = e1 * U['n_in'] / e1.sum()
    k = sum(T['counts'].sum() for T in train_Us) / sum(np.exp(logE1(T)).sum() for T in train_Us)
    P['B5'] = e1 * k
    info['B5_k'] = round(float(k), 4)
    sal_ok = U['has_salary'] and all(T['has_salary'] for T in train_Us)
    fc_ok = U['has_fc'] and all(T['has_fc'] for T in train_Us)
    if sal_ok:
        ks = []
        for i in range(5):
            num = sum(T['counts'][_bucket(T) == i].sum() for T in train_Us)
            den = sum(np.exp(logE1(T))[_bucket(T) == i].sum() for T in train_Us)
            ks.append(num / den if den > 0 else 1.0)
        P['B6'] = e1 * np.array(ks)[_bucket(U)]
        info['B6_k'] = [round(float(x), 4) for x in ks]
    sets = {'B1': [], 'B3S': names_all['construction']}
    if sal_ok:
        sets['B2'] = names_all['salary']
        sets['B3'] = names_all['salary'] + names_all['construction']
        if fc_ok:
            sets['B4'] = names_all['salary'] + names_all['construction'] + names_all['fc']
    for m, names in sets.items():
        theta, tinfo = maxent_train(train_Us, names)
        lq, minfo = maxent_fit_marginals(U, theta, names)
        P[m] = np.exp(lq) * U['n_in']
        info[m] = {'theta': dict(zip(names, [round(float(x), 4) for x in theta])), 'train': tinfo, 'test_marginals': minfo}
    if sal_ok and fc_ok:
        names = names_all['salary'] + names_all['construction'] + names_all['fc']
        beta = poisson_train(train_Us, names)
        X = np.column_stack([np.ones(len(U['cpt'])), np.maximum(lE, -40), _F(U, names)])
        P['B7'] = np.exp(np.clip(X @ beta, -50, 20))
        info['B7_beta'] = dict(zip(['intercept', 'logE1'] + names, [round(float(x), 4) for x in beta]))
    return P, info


def _bucket(U):
    b = np.zeros(len(U['sal_left']), dtype=np.int8)
    for i, (lo, hi) in enumerate(SAL_EDGES):
        b[(U['sal_left'] >= lo) & (U['sal_left'] <= hi)] = i
    return b


# ----------------------------------------------------------------------------------------------- metrics
def metrics(U, pred, extra_sets=None):
    a = U['counts']
    q = pred / pred.sum()
    with np.errstate(divide='ignore'):
        lq = np.log(q)
    logscore = float((a[a > 0] @ lq[a > 0]) / a.sum())
    cal = []
    for lo, hi in zip(PRED_BINS[:-1], PRED_BINS[1:]):
        m = (pred >= lo) & (pred < hi)
        cal.append({'bin': f'[{lo},{hi})', 'n_lineups': int(m.sum()), 'pred': round(float(pred[m].sum()), 1),
                    'actual': int(a[m].sum())})
    ta = np.argsort(-a)[:TOP_ACTUAL]
    tp = np.argsort(-pred)[:TOP_PRED]
    out = {'log_score_per_entry': round(logscore, 4), 'total_pred': round(float(pred.sum()), 1), 'total_actual': int(a.sum()),
           'calibration_bins': cal,
           'top50_actual_median_abs_log_ratio': round(float(np.median(np.abs(np.log((pred[ta] + 1) / (a[ta] + 1))))), 4),
           'top50_actual_sum_pred_vs_actual': [round(float(pred[ta].sum()), 1), int(a[ta].sum())],
           'top1000_pred_actual_over_pred': round(float(a[tp].sum() / pred[tp].sum()), 4)}
    if U['proj'] is not None:
        tf = np.argsort(-U['proj'])[:TOP_FC]
        out['fc_top150_actual_over_pred'] = round(float(a[tf].sum() / pred[tf].sum()), 4)
        out['fc_top150_actual_pred'] = [int(a[tf].sum()), round(float(pred[tf].sum()), 1)]
    for name, rows in (extra_sets or {}).items():
        out[f'{name}_actual_over_pred'] = round(float(a[rows].sum() / max(pred[rows].sum(), 1e-9)), 4)
        out[f'{name}_actual_pred'] = [int(a[rows].sum()), round(float(pred[rows].sum()), 1)]
    by = {}
    if U['sal_left'] is not None:
        b = _bucket(U)
        by['salary_left'] = {SAL_NAMES[i]: _ratio(a, pred, b == i) for i in range(5)}
    cp = np.array(U['pos'])[U['cpt']]
    by['captain_position'] = {p: _ratio(a, pred, cp == p) for p in sorted(set(cp))}
    out['by'] = by
    return out


def _ratio(a, pred, m):
    return {'actual': int(a[m].sum()), 'pred': round(float(pred[m].sum()), 1),
            'actual_over_pred': round(float(a[m].sum() / pred[m].sum()), 4) if pred[m].sum() > 0 else None}


# --------------------------------------------------------------------------------------------- diagnosis
def diagnose(U):
    """Root-cause decomposition with ORACLE ownership, descriptive (no fitting across slates)."""
    a = U['counts']
    e1 = np.exp(logE1(U))
    lq1, _ = maxent_fit_marginals(U, [], [])
    b1 = np.exp(lq1) * U['n_in']
    obs = a > 0
    d = {'contest': U['id'], 'size': U['size'], 'N_filled': U['N'], 'coverage_in_universe': round(U['coverage'], 4),
         'n_feasible_lineups': int(len(a)), 'n_played_lineups': int(obs.sum()),
         'duplicate_entries': U['dup_entries'],
         'self_duplicate_share_of_duplicate_entries': round(U['self_dup_entries'] / max(U['dup_entries'], 1), 4),
         'E1_mass_on_feasible_universe': round(float(e1.sum() / U['n_in']), 4),
         'MEANING_E1_mass': ('sum of independent-product copies (N x CPT share x product of FLEX shares) over the LEGAL '
                             'lineups, divided by the entries there. E1 is not a normalised distribution: a value above 1 '
                             'means it predicts more copies in total than there are entries, so where it still under-predicts '
                             'the popular lineups its error is SHAPE (too flat), not missing mass'),
    }
    tp = np.argsort(-a)[:200]
    d['top200_actual'] = {'actual': int(a[tp].sum()), 'E1': round(float(e1[tp].sum()), 1), 'B1_maxent': round(float(b1[tp].sum()), 1)}
    groups = {}
    groups['stack_cpt_pc_own_qb'] = U['feats']['stack_cpt_pc_own_qb'] > 0
    groups['both_qbs'] = U['feats']['both_qbs'] > 0
    groups['any_k_dst'] = U['feats']['any_k_dst'] > 0
    big = np.where(U['feats']['split_5_1'] > 0, '5-1', np.where(U['feats']['split_4_2'] > 0, '4-2', '3-3'))
    for sp in ('5-1', '4-2', '3-3'):
        groups[f'split_{sp}'] = big == sp
    if U['sal_left'] is not None:
        b = _bucket(U)
        for i in range(5):
            groups[f'salary_left_{SAL_NAMES[i]}'] = b == i
    if U['proj'] is not None:
        rk = np.empty(len(a), dtype=np.int64)
        rk[np.argsort(-U['proj'])] = np.arange(len(a))
        groups['fc_rank_1_100'] = rk < 100
        groups['fc_rank_101_1000'] = (rk >= 100) & (rk < 1000)
        groups['fc_rank_1001_10000'] = (rk >= 1000) & (rk < 10000)
        groups['fc_rank_10001_plus'] = rk >= 10000
    cp = np.array(U['pos'])[U['cpt']]
    for p in sorted(set(cp)):
        groups[f'captain_{p}'] = cp == p
    d['actual_over_maxent_by_group'] = {g: {'actual': int(a[m].sum()), 'B1_maxent': round(float(b1[m].sum()), 1),
                                            'E1': round(float(e1[m].sum()), 1),
                                            'actual_over_B1': round(float(a[m].sum() / b1[m].sum()), 3) if b1[m].sum() else None}
                                        for g, m in groups.items()}
    # pair co-selection lift under maxent (FLEX-FLEX and CPT-FLEX), top pairs
    q1 = b1 / b1.sum()
    seats = np.concatenate([U['cpt'][:, None], U['flex']], axis=1).astype(np.int64)
    KK = K_PLAYERS * K_PLAYERS
    pa = np.zeros(KK)
    pq = np.zeros(KK)
    wa = a / a.sum()
    for i in range(6):
        for j in range(i + 1, 6):
            ix = seats[:, i] * K_PLAYERS + seats[:, j]
            pa += np.bincount(ix, weights=wa, minlength=KK)
            pq += np.bincount(ix, weights=q1, minlength=KK)
    pa, pq = pa.reshape(K_PLAYERS, K_PLAYERS), pq.reshape(K_PLAYERS, K_PLAYERS)
    pa, pq = pa + pa.T, pq + pq.T
    lifts = []
    for i in range(K_PLAYERS):
        for j in range(i + 1, K_PLAYERS):
            if pq[i, j] > 0.02:
                lifts.append((U['players'][i], U['players'][j], round(float(pa[i, j] / pq[i, j]), 3), round(float(pa[i, j]), 4)))
    lifts.sort(key=lambda t: -abs(math.log(t[2])))
    d['pair_lift_vs_maxent_top'] = [{'pair': [x, y], 'lift': l, 'actual_pair_rate': r} for x, y, l, r in lifts[:12]]
    lv = np.array([math.log(t[2]) for t in lifts]) if lifts else np.zeros(1)
    d['pair_lift_abs_log_median'] = round(float(np.median(np.abs(lv))), 4)
    return d


# --------------------------------------------------------------------------------------------------- run
def run():
    OUT.mkdir(parents=True, exist_ok=True)
    sl = load_slates()
    U = {k: build_universe(v) for k, v in sl.items()}
    names_all = {'construction': ['stack_cpt_pc_own_qb', 'both_qbs', 'split_5_1', 'split_4_2', 'any_k_dst'],
                 'salary': [f'sal_{n}' for n in SAL_NAMES[:4]], 'fc': ['fc_gap_pts', 'fc_top100']}
    diag = {}
    for k, u in U.items():
        diag[k] = diagnose(u)
        (OUT / 'DUPE_RESEARCH_PARTIAL.json').write_text(json.dumps({'diagnosis': diag}, indent=1, default=float))
    folds = {}
    for test in SLATE_IDS:
        slate = TRAIN_OF[test]
        train = [U[TRAINING_CONTEST[s]] for s in ('PIT_CLE', 'PHI_CHI', 'ATL_NO') if s != slate]
        P, info = predictions(U[test], train, names_all)
        # salary/FC models need every training slate to have salary/FC: retrain on the subset that does
        if U[test]['has_salary'] and 'B2' not in P:
            sub = [T for T in train if T['has_salary'] and T['has_fc']]
            if sub:
                P2, info2 = predictions(U[test], sub, names_all)
                for m in ('B6', 'B2', 'B3', 'B4', 'B7'):
                    if m in P2:
                        P[m] = P2[m]
                        info[m] = info2.get(m, info2.get(f'{m}_k', info2.get(f'{m}_beta')))
                info['salary_models_trained_on'] = [T['id'] for T in sub]
        extra = {}
        owner_rows = owner_lineup_rows(U[test], sl[test])
        if owner_rows is not None:
            extra['owner_lineups'] = owner_rows
        folds[test] = {'train': [T['id'] for T in train], 'models': {m: metrics(U[test], p, extra) for m, p in P.items()},
                       'fit_info': info}
        (OUT / 'DUPE_RESEARCH_PARTIAL.json').write_text(json.dumps({'diagnosis': diag, 'folds': folds}, indent=1, default=float))
    # candidate bars (pre-registered section 5)
    bars = candidate_bars(folds)
    doc = {'ARTIFACT': 'SHOWDOWN_DUPE_RESEARCH', 'STATUS': 'SHADOW_ONLY -- EXPLORATORY (ATL@NO is development data)',
           'prereg': 'docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md (2318d267)',
           'universe': {k: {'players': K_PLAYERS, 'feasible_lineups': int(len(u['cpt'])), 'coverage': round(u['coverage'], 4),
                            'has_salary': u['has_salary'], 'has_fc': u['has_fc'], 'raw_sha256': u['raw_sha256']}
                        for k, u in U.items()},
           'diagnosis': diag, 'folds': folds, 'candidate_bars': bars,
           'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    p = OUT / 'DUPE_RESEARCH.json'
    p.write_text(json.dumps(doc, indent=1, default=float))
    write_tables(folds)
    return p, doc, U, sl


def owner_lineup_rows(U, s):
    if not s['id'].startswith('ATL_NO'):
        return None
    g = [r for r in csv.DictReader(open(_REPO / 'nfl/postgame/showdown_atl_no_2026W4/ATL_NO_OWNER_ENTRIES_GRADED.csv'))
         if r['contest_id'] == s['contest_id']]
    pidx = {p: i for i, p in enumerate(U['players'])}
    rows = []
    for r in g:
        ids = [pidx.get(r['captain'].split('|')[0])] + [pidx.get(x.split('|')[0]) for x in ast.literal_eval(r['flex'])]
        if None in ids:
            continue
        f = np.sort(np.array(ids[1:], dtype=np.int8))
        c = _code(np.array([ids[0]], dtype=np.int8), f[None, :])[0]
        loc = int(np.searchsorted(U['code'], c))
        if loc < len(U['code']) and U['code'][loc] == c:
            rows.append(loc)
    return np.array(sorted(set(rows)), dtype=np.int64)


def candidate_bars(folds):
    res = {}
    models = sorted({m for f in folds.values() for m in f['models']})
    for m in models:
        rows, ok = [], True
        avail = [t for t, f in folds.items() if m in f['models']]
        for t in avail:
            M = folds[t]['models']
            r = M[m]
            c1 = r['log_score_per_entry'] > M['B0n']['log_score_per_entry'] and r['log_score_per_entry'] > M['B1']['log_score_per_entry']
            c2 = 1 / 1.5 <= r['top1000_pred_actual_over_pred'] <= 1.5
            opt = r.get('fc_top150_actual_over_pred')
            c3 = None if opt is None else 1 / 1.5 <= opt <= 1.5
            b5 = M['B5']
            dist = lambda x: abs(math.log(x)) if x else math.inf
            c4 = dist(r['top1000_pred_actual_over_pred']) < dist(b5['top1000_pred_actual_over_pred']) and (
                opt is None or dist(opt) < dist(b5.get('fc_top150_actual_over_pred')))
            passed = c1 and c2 and (c3 in (None, True)) and c4
            ok &= passed
            rows.append({'fold': t, 'logscore_beats_B0n_and_B1': c1, 'top1000_within_1.5x': c2, 'fc_top150_within_1.5x': c3,
                         'beats_B5': c4, 'PASS': passed})
        res[m] = {'folds_available': avail, 'per_fold': rows,
                  'VERDICT': 'CANDIDATE (still SHADOW_ONLY)' if ok and m not in ('B0', 'B0n', 'B1') else
                             ('BASELINE' if m in ('B0', 'B0n', 'B1') else 'NOT_A_CANDIDATE')}
    return res


def write_tables(folds):
    with open(OUT / 'DUPE_CALIBRATION_TABLE.csv', 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['held_out_contest', 'model', 'log_score_per_entry', 'total_pred', 'total_actual', 'top1000_actual_over_pred',
                    'fc_top150_actual_over_pred', 'owner_lineups_actual_over_pred', 'top50_actual_median_abs_log_ratio']
                   + [f'bin_{b}_pred/actual' for b in ('0-0.1', '0.1-1', '1-3', '3-10', '10-30', '30-100', '100+')])
        for t, f in folds.items():
            for m, r in f['models'].items():
                w.writerow([t, m, r['log_score_per_entry'], r['total_pred'], r['total_actual'], r['top1000_pred_actual_over_pred'],
                            r.get('fc_top150_actual_over_pred'), r.get('owner_lineups_actual_over_pred'),
                            r['top50_actual_median_abs_log_ratio']] + [f"{c['pred']}/{c['actual']}" for c in r['calibration_bins']])


if __name__ == '__main__':
    p, doc, _U, _sl = run()
    print(p)
    for k, d in doc['diagnosis'].items():
        print(k, {x: d[x] for x in ('coverage_in_universe', 'n_feasible_lineups', 'self_duplicate_share_of_duplicate_entries',
                                    'E1_mass_on_feasible_universe', 'top200_actual')})
    for t, f in doc['folds'].items():
        print('FOLD', t, 'train', f['train'])
        for m, r in f['models'].items():
            print(f"  {m:4} ls {r['log_score_per_entry']:8.4f} top1000 a/p {r['top1000_pred_actual_over_pred']:7.3f} "
                  f"fc150 {r.get('fc_top150_actual_over_pred')} owner {r.get('owner_lineups_actual_over_pred')} "
                  f"top50 mal {r['top50_actual_median_abs_log_ratio']}")
    for m, v in doc['candidate_bars'].items():
        print(m, v['VERDICT'], [(x['fold'], x['PASS']) for x in v['per_fold']])
