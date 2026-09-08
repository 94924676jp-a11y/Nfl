"""P recoverability: extended prior-only features on Stage 2's exact frame.

The control is Stage 2's EWMA half-life 2, reached through s2_lib itself rather
than reimplemented, so the identity gate cannot pass by coincidence.

P is PASS-SNAP PARTICIPATION -- an upper bound on route participation, never
routes run.
"""
import bisect, collections, math, os, sys
import numpy as np

S = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
for p in (f'{S}/s2', f'{S}/p4c', f'{S}/p4e'):
    sys.path.insert(0, p)
import s2_lib as SL                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402

POS = SL.POS
EVAL = SL.EVAL
TARGET = SL.TARGET                     # 's_pass_snaps'
HALFLIVES = (1.0, 2.0, 3.0, 5.0, 8.0)
ROLE_UP, ROLE_DOWN = 0.10, -0.10
VACATED_MIN = 0.20


def load():
    rows, sub = SL.load()
    SL.attach(sub)                     # Stage 2's own features, untouched
    return rows, sub


def ewma(vals, hl):
    lam = 0.5 ** (1.0 / hl)
    num = den = 0.0
    w = 1.0
    for v in reversed(vals):
        num += w * v
        den += w
        w *= lam
    return num / den if den > 0 else None


def attach(sub, pa):
    """Blocks A-E, all strictly prior. Stage 2's q_* fields stay untouched."""
    hist = collections.defaultdict(list)
    hist_ord = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        k = bisect.bisect_left(hist_ord[pid], r['ord'])
        past = hist[pid][:k]
        app = [x for x in past if x['appeared'] and x.get(TARGET) is not None]
        v = [x[TARGET] for x in app]
        # --- block A: player role history --------------------------------
        r['p_n'] = len(app)
        r['p_last'] = v[-1] if v else None
        for hl in HALFLIVES:
            r[f'p_ewma{hl:g}'] = ewma(v, hl) if v else None
        r['p_expanding'] = float(np.mean(v)) if v else None
        r['p_var'] = float(np.var(v[-10:])) if len(v) >= 3 else None
        r['p_trend'] = (float(np.mean(v[-3:]) - np.mean(v[-8:-3]))
                        if len(v) >= 8 else None)
        r['p_step'] = (float(np.mean(v[-2:]) - np.mean(v[-4:-2]))
                       if len(v) >= 4 else None)
        r['p_role'] = ('up' if (r['p_step'] is not None and r['p_step'] >= ROLE_UP)
                       else 'down' if (r['p_step'] is not None
                                       and r['p_step'] <= ROLE_DOWN) else 'stable')
        sn = [x['s_snaps'] for x in app if x.get('s_snaps') is not None]
        r['p_snap_prior'] = float(np.mean(sn[-8:])) if sn else None
        r['p_snap_expanding'] = float(np.mean(sn)) if sn else None
        r['p_prev_season'] = (float(np.mean([x[TARGET] for x in app
                                             if x['season'] == r['season'] - 1]))
                              if any(x['season'] == r['season'] - 1 for x in app)
                              else None)
        r['p_prior_role'] = ('starter' if (r['p_snap_prior'] or 0) >= 0.60
                             else 'rotation' if (r['p_snap_prior'] or 0) >= 0.25
                             else 'fringe')
        # --- block B: appearance / availability context -------------------
        r['p_app_prior'] = (float(np.mean([1.0 if x['appeared'] else 0.0
                                           for x in past[-10:]]))
                            if past else None)
        r['p_missed_run'] = 0
        for x in reversed(past):
            if x['appeared']:
                break
            r['p_missed_run'] += 1
        r['p_n_games'] = len(past)
        r['p_stability'] = (float(1.0 / (1.0 + np.std(v[-8:])))
                            if len(v) >= 3 else None)
        hist[pid].append(r)
        hist_ord[pid].append(r['ord'])

    # --- blocks C and D: teammate and team context, previous team-game ----
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
            others = [g for g in grp if g['gsis_id'] != x['gsis_id']]
            ps = [(g.get(TARGET) or 0.0) for g in others]
            r_ = x
            r_['p_mate_P_sum'] = float(sum(ps)) if others else None
            r_['p_mate_P_max'] = float(max(ps)) if ps else None
            tot = float(sum((g.get(TARGET) or 0.0) for g in grp))
            r_['p_team_conc'] = (float(sum(((g.get(TARGET) or 0.0) / tot) ** 2
                                           for g in grp)) if tot > 0 else None)
            r_['p_vacated'] = (float(sum((g.get(TARGET) or 0.0) for g in others
                                         if not g['appeared']))
                               if others else None)
            r_['p_teammate_change'] = (
                'vacated_opportunity'
                if (r_['p_vacated'] or 0.0) >= VACATED_MIN else
                'returning_competitor'
                if any((not g['appeared']) and (g.get('q_n_prior_app') or 0) >= 1
                       for g in others) else 'stable')
            r_['p_mate_step'] = (
                float(np.mean([(g.get('q_step') or 0.0) for g in others]))
                if others else None)
            r_['p_team_dropbacks'] = (
                float(np.mean([(g.get('den') or {}).get('team_dropbacks_part', 0)
                               for g in grp])) if grp else None)
            r_['p_team_n'] = float(len(grp)) if p is not None else None
            r_['p_team_stability'] = (
                float(np.mean([1.0 if g['appeared'] else 0.0 for g in grp]))
                if grp else None)
    return sub


def eligible(r, ev=None):
    return SL.eligible(r, ev)


def metrics(pred, real):
    return SL.metrics(pred, real)
