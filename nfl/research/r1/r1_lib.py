"""R1: target rate conditional on participation. Estimand and prior-only history.

R is taken from Stage 4 UNCHANGED:

    P* = pass_snaps / team_dropbacks        (pass-snap participation)
    W* = target_share x appeared
    R* = W* / P*   where P* > 0, else 0

P is an UPPER BOUND on route participation, never routes run.
"""
import bisect, collections, math, os, sys
import numpy as np

S = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
for p in (f'{S}/p4e', f'{S}/p4c', f'{S}/s2', f'{S}/s4'):
    sys.path.insert(0, p)
import p4c_build as CB                                         # noqa: E402

POS = ('WR', 'TE', 'RB')
EVAL = [2022, 2023, 2024, 2025]
HALFLIVES = (2.0, 3.0, 5.0, 8.0)
P_FLOOR_FEATURE = 0.02          # pre-declared, feature use only
ROLE_UP, ROLE_DOWN = 0.10, -0.10


def load():
    rows = CB.load_panel()
    sub = [r for r in rows if r.get('position') in POS]
    sub.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    for r in sub:
        p = r.get('s_pass_snaps')
        w = (r.get('s_targets') or 0.0) if r['appeared'] else 0.0
        r['P_star'] = None if p is None else float(p)
        r['W_star'] = float(w)
        r['R_star'] = (float(w) / float(p)) if (p is not None and p > 0) else (
            0.0 if p is not None else None)
        r['R_defined'] = bool(r['appeared'] and p is not None and p > 0)
    return rows, sub


def wmean(vals, wts=None):
    if not vals:
        return None
    if wts is None:
        return float(np.mean(vals))
    s = float(np.sum(wts))
    return float(np.dot(vals, wts) / s) if s > 0 else None


def ewma(vals, hl, wts=None):
    lam = 0.5 ** (1.0 / hl)
    num = den = 0.0
    w = 1.0
    n = len(vals)
    for i in range(n - 1, -1, -1):
        ww = w * (wts[i] if wts is not None else 1.0)
        num += ww * vals[i]
        den += ww
        w *= lam
    return num / den if den > 0 else None


def attach(sub, rows_all):
    """Prior-only history. Strictly earlier ORDINALS -- the prefix cut P4E and
    Stage 2 both needed for the mid-week team-change rows."""
    hist = collections.defaultdict(list)
    hist_ord = collections.defaultdict(list)
    pos_sum = collections.defaultdict(float)
    pos_n = collections.defaultdict(int)
    pos_wsum = collections.defaultdict(float)
    pos_wn = collections.defaultdict(float)
    pending = collections.defaultdict(list)
    # team-game aggregates from strictly earlier ordinals
    team_prev = {}
    by_team_ord = collections.defaultdict(list)
    for r in sub:
        by_team_ord[(r['team'], r['ord'])].append(r)
    last_ord = None
    for r in sub:
        if last_ord is not None and r['ord'] != last_ord:
            for p_, vals in pending.items():
                for v, w in vals:
                    pos_sum[p_] += v
                    pos_n[p_] += 1
                    pos_wsum[p_] += v * w
                    pos_wn[p_] += w
            pending.clear()
        last_ord = r['ord']
        pid = r['gsis_id']
        k = bisect.bisect_left(hist_ord[pid], r['ord'])
        past = hist[pid][:k]
        use = [x for x in past if x['R_defined']]
        vals = [x['R_star'] for x in use]
        wts = [x['P_star'] for x in use]
        r['h_n'] = len(use)
        r['h_last'] = vals[-1] if vals else None
        r['h_expanding'] = wmean(vals) if vals else None
        r['h_expanding_w'] = wmean(vals, wts) if vals else None
        for hl in HALFLIVES:
            r[f'h_ewma{hl:g}'] = ewma(vals, hl) if vals else None
            r[f'h_ewma{hl:g}_w'] = ewma(vals, hl, wts) if vals else None
        pv = [(x['R_star'], x['P_star']) for x in use
              if x['season'] == r['season'] - 1]
        r['h_prev_season'] = wmean([a for a, _ in pv]) if pv else None
        r['h_prev_season_w'] = (wmean([a for a, _ in pv], [b for _, b in pv])
                                if pv else None)
        r['h_pos_mean'] = (pos_sum[r['position']] / pos_n[r['position']]
                           if pos_n[r['position']] else None)
        r['h_pos_mean_w'] = (pos_wsum[r['position']] / pos_wn[r['position']]
                             if pos_wn[r['position']] > 0 else None)
        r['h_sd'] = float(np.std(vals[-10:])) if len(vals) >= 3 else None
        r['h_eff_n'] = float(np.sum(wts)) if wts else 0.0
        # participation history (block B), prior-only
        pvals = [x['P_star'] for x in use]
        r['h_P_ewma2'] = ewma(pvals, 2.0) if pvals else None
        r['h_P_last'] = pvals[-1] if pvals else None
        r['h_P_sd'] = float(np.std(pvals[-10:])) if len(pvals) >= 3 else None
        r['h_P_step'] = (float(np.mean(pvals[-2:]) - np.mean(pvals[-4:-2]))
                         if len(pvals) >= 4 else None)
        r['h_role'] = ('up' if (r['h_P_step'] is not None
                                and r['h_P_step'] >= ROLE_UP)
                       else 'down' if (r['h_P_step'] is not None
                                       and r['h_P_step'] <= ROLE_DOWN)
                       else 'stable')
        # history quantity (block A)
        r['h_targets_career'] = float(sum(
            (x.get('y_targets') or 0) for x in past))
        r['h_targets_last8'] = float(sum(
            (x.get('y_targets') or 0) for x in past[-8:]))
        r['h_games'] = len(past)
        r['h_recency'] = (r['ord'] - past[-1]['ord']) if past else None
        hist[pid].append(r)
        hist_ord[pid].append(r['ord'])
        if r['R_defined']:
            pending[r['position']].append((r['R_star'], r['P_star']))

    # team context (block C) and teammate competition (block D), previous
    # team-game only
    by_team = collections.defaultdict(list)
    for r in sub:
        by_team[r['team']].append(r)
    for tm, rs in by_team.items():
        ords = sorted({x['ord'] for x in rs})
        prev = {o: (ords[i - 1] if i else None) for i, o in enumerate(ords)}
        byo = collections.defaultdict(list)
        for x in rs:
            byo[x['ord']].append(x)
        for x in rs:
            p = prev[x['ord']]
            grp = byo.get(p, [])
            shares = sorted(((g.get('s_targets') or 0.0) for g in grp),
                            reverse=True)
            tot = float(sum(shares))
            x['h_team_top_share'] = float(shares[0]) if shares else None
            x['h_team_hhi'] = (float(sum((s / tot) ** 2 for s in shares))
                               if tot > 0 else None)
            x['h_team_conc'] = ('alpha' if (x['h_team_top_share'] or 0) >= 0.30
                                else 'balanced'
                                if (x['h_team_top_share'] or 0) >= 0.20
                                else 'diffuse')
            x['h_team_dropbacks'] = (
                float(np.mean([(g.get('den') or {}).get('team_dropbacks_part', 0)
                               for g in grp])) if grp else None)
            others = [g for g in grp if g['gsis_id'] != x['gsis_id']]
            x['h_mate_P'] = (float(np.mean([(g.get('P_star') or 0.0)
                                            for g in others]))
                             if others else None)
            x['h_mate_S'] = (float(np.mean([(g.get('s_targets') or 0.0)
                                            for g in others]))
                             if others else None)
            x['h_n_mates'] = float(len(others)) if p is not None else None
            x['h_vacated_P'] = (float(sum((g.get('P_star') or 0.0)
                                          for g in others
                                          if not g['appeared']))
                                if others else None)
    return sub


def eligible(r, ev=None):
    if ev is not None and r['season'] != ev:
        return False
    return bool(r['R_defined'] and (r.get('h_n') or 0) >= 1
                and r.get('h_pos_mean') is not None)


def metrics(pred, real):
    p = np.asarray(pred, float)
    y = np.asarray(real, float)
    e = p - y
    sst = ((y - y.mean()) ** 2).sum()
    return {'n': int(len(y)), 'mae': float(np.abs(e).mean()),
            'rmse': float(math.sqrt((e * e).mean())), 'bias': float(e.mean()),
            'r': (float(np.corrcoef(p, y)[0, 1]) if p.std() > 1e-12
                  and y.std() > 1e-12 else None),
            'r2': float(1 - (e * e).sum() / sst) if sst > 0 else None,
            'sd_pred': float(p.std(ddof=1)) if len(p) > 1 else None,
            'sd_actual': float(y.std(ddof=1)) if len(y) > 1 else None,
            'sd_ratio': (float(p.std(ddof=1) / y.std(ddof=1))
                         if len(y) > 1 and y.std(ddof=1) > 1e-12 else None),
            'mean_real': float(y.mean()), 'mean_pred': float(p.mean())}
