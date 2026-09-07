"""P4 Q1-Q5: plays, pass tendency, dropbacks, rush volume, coach/QB/opponent.

Every feature is built from games strictly before the row's own (season, week).
The ridge design is assembled per target so an ablation removes a BLOCK rather
than zeroing a column.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p4lib as L

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ['plays', 'dropbacks', 'pass_att_ex_sacks', 'sacks', 'scrambles',
        'rush_att', 'designed_qb_rush', 'nonqb_rush_att', 'pass_rate',
        'neutral_pass_rate', 'early_down_pass_rate', 'sec_per_play', 'proe']
TARGETS = ['plays', 'pass_rate', 'neutral_pass_rate', 'dropbacks',
           'rush_att', 'nonqb_rush_att', 'designed_qb_rush', 'scrambles',
           'sacks']
GROUPS = ['team_history', 'pace', 'pass_tendency', 'proe', 'play_caller',
          'qb', 'opponent', 'recent_form', 'regime_change']


def attach_proe(rows):
    tbl = json.load(open(f'{HERE}/proe_by_game.json'))
    # use the widest-window model (last eval season) for the feature series;
    # the fit for that model saw only seasons < that eval season.
    ev = max(L.EVAL)
    for r in rows:
        k = f'{ev}|{r["season"]}|{r["week"]}|{r["team"]}'
        v = tbl.get(k)
        r['proe'] = v['proe'] if v else None
        r['xpass_rate'] = v['xpass_rate'] if v else None
    return rows


def opp_history(rows):
    """Opponent's own prior-game profile, and what opponents have faced."""
    by = {}
    for r in rows:
        by[(r['season'], r['week'], r['team'])] = r
    faced = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        o = r.get('opponent')
        r['_opp_row'] = None
    for r in rows:
        o = r.get('opponent')
        if not o:
            continue
        faced[o]['plays_faced'].append((r['ord'], r['plays']))
        faced[o]['pass_rate_faced'].append((r['ord'], r['pass_rate']))
    idx = {k: sorted(v) for team, d in faced.items() for k, v in d.items()}
    # rebuild per-opponent prior means
    opp_prior = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in sorted(rows, key=lambda x: x['ord']):
        o = r.get('opponent')
        r['_opp_plays_faced'] = (float(np.mean(opp_prior[o]['pf'][-5:]))
                                 if opp_prior[o]['pf'] else None)
        r['_opp_pass_faced'] = (float(np.mean([x for x in opp_prior[o]['prf'][-5:]
                                               if x is not None]))
                                if [x for x in opp_prior[o]['prf'] if x is not None]
                                else None)
        r['_opp_own_plays'] = (float(np.mean(opp_prior[o]['own'][-5:]))
                               if opp_prior[o]['own'] else None)
    # second pass to fill (needs both directions available chronologically)
    hist = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in sorted(rows, key=lambda x: x['ord']):
        o = r.get('opponent')
        r['_opp_plays_faced'] = (float(np.mean(hist[o]['pf'][-5:]))
                                 if hist[o]['pf'] else None)
        pr = [x for x in hist[o]['prf'][-5:] if x is not None]
        r['_opp_pass_faced'] = float(np.mean(pr)) if pr else None
        r['_opp_own_plays'] = (float(np.mean(hist[o]['own'][-5:]))
                               if hist[o]['own'] else None)
        sp = [x for x in hist[o]['sec'][-5:] if x is not None]
        r['_opp_sec'] = float(np.mean(sp)) if sp else None
    for r in sorted(rows, key=lambda x: x['ord']):
        o = r.get('opponent')
        hist[o]['pf'].append(r['plays'])
        hist[o]['prf'].append(r['pass_rate'])
        hist[r['team']]['own'].append(r['plays'])
        hist[r['team']]['sec'].append(r['sec_per_play'])
    return rows


def feat(r, target, groups, arm_b, lm):
    """Ridge design row. `groups` selects which blocks are present."""
    f = []
    h = r['_h']
    def ew(k, d):
        v = L.ewma(h.get(k) or [])
        return d if v is None else v
    def mn(k, n, d):
        v = (h.get(k) or [])[-n:]
        return float(np.mean(v)) if v else d
    if 'team_history' in groups:
        f += [ew(target, lm), mn(target, 3, lm), mn(target, 5, lm),
              float(np.mean(h.get(target) or [lm]))]
        f.append(1.0 if not h.get(target) else 0.0)
    if 'recent_form' in groups:
        v = h.get(target) or []
        f.append(v[-1] if v else lm)
        f.append(float(np.std(v[-5:])) if len(v) >= 3 else 0.0)
    if 'pace' in groups:
        f += [ew('sec_per_play', 27.0), mn('sec_per_play', 3, 27.0)]
        f.append(ew('plays', 63.0))
    if 'pass_tendency' in groups:
        f += [ew('pass_rate', 0.60), ew('neutral_pass_rate', 0.55),
              ew('early_down_pass_rate', 0.55)]
    if 'proe' in groups:
        f += [ew('proe', 0.0), mn('proe', 3, 0.0)]
    if 'play_caller' in groups:
        ch = r['_ch'].get(target) or []
        f.append(float(np.mean(ch)) if len(ch) >= 8 else lm)
        f.append(1.0 if len(ch) < 8 else 0.0)
    if 'opponent' in groups:
        f += [r.get('_opp_plays_faced') if r.get('_opp_plays_faced') is not None else 63.0,
              r.get('_opp_pass_faced') if r.get('_opp_pass_faced') is not None else 0.60,
              r.get('_opp_own_plays') if r.get('_opp_own_plays') is not None else 63.0,
              r.get('_opp_sec') if r.get('_opp_sec') is not None else 27.0]
    if 'regime_change' in groups:
        prev = r.get('_prev_row')
        f.append(1.0 if (prev and prev.get('coach') != r.get('coach')) else 0.0)
        f.append(float(r.get('rest') or 7) / 14.0)
        f.append(float(r.get('home') or 0))
        f.append(float(r.get('div_game') or 0))
        f.append(1.0 if (r.get('roof') or '') in ('dome', 'closed') else 0.0)
    if 'qb' in groups:
        prev = r.get('_prev_row')
        if arm_b:
            f.append(1.0 if (prev and prev.get('qb_id') != r.get('qb_id')) else 0.0)
            f.append(1.0 if not prev else 0.0)
        else:
            # strict arm: only whether the PRIOR two games changed QB
            p2 = prev.get('_prev_row') if prev else None
            f.append(1.0 if (prev and p2 and p2.get('qb_id') != prev.get('qb_id'))
                     else 0.0)
            f.append(1.0 if not prev else 0.0)
    return f


def main():
    rows = L.load()
    rows = attach_proe(rows)
    rows = L.attach_history(rows, KEYS)
    rows = opp_history(rows)
    rows = L.attach_history(rows, KEYS)      # refresh after proe attach
    print(f'team-games: {len(rows)}  seasons '
          f'{min(r["season"] for r in rows)}-{max(r["season"] for r in rows)}')

    out = {}
    for target in TARGETS:
        out[target] = {}
        for ev in L.EVAL:
            tr = [r for r in rows if r['season'] < ev and r.get(target) is not None]
            te = [r for r in rows if r['season'] == ev and r.get(target) is not None]
            if len(tr) < 300 or len(te) < 100:
                continue
            lm = float(np.mean([r[target] for r in tr]))
            cp = lm
            recs = []
            for r in te:
                b = L.baselines(r, target, lm, cp)
                recs.append({'team': r['team'], 'row': r, 'y': r[target], **b})
            # ridge, full and per-ablation, both QB arms
            for arm_b, arm in ((False, 'A_strict'), (True, 'B_announced')):
                Xtr = [feat(r, target, GROUPS, arm_b, lm) for r in tr]
                ytr = [r[target] for r in tr]
                m = L.fit_ridge(Xtr, ytr, l2=5.0)
                p = L.pred_ridge(m, [feat(r, target, GROUPS, arm_b, lm) for r in te])
                for rec, v in zip(recs, p):
                    rec[f'ridge_{arm}'] = float(v)
            for g in GROUPS:
                keep = [x for x in GROUPS if x != g]
                Xtr = [feat(r, target, keep, True, lm) for r in tr]
                m = L.fit_ridge(Xtr, [r[target] for r in tr], l2=5.0)
                p = L.pred_ridge(m, [feat(r, target, keep, True, lm) for r in te])
                for rec, v in zip(recs, p):
                    rec[f'minus_{g}'] = float(v)
            names = L.BASE_NAMES + ['ridge_A_strict', 'ridge_B_announced'] + \
                [f'minus_{g}' for g in GROUPS]
            per = {n: L.metrics([(x['y'], x[n]) for x in recs]) for n in names}
            best_base = min(L.BASE_NAMES, key=lambda n: per[n]['mae'])
            out[target][ev] = {
                'n': len(recs), 'league_mean_train': lm,
                'per_model': per, 'best_baseline': best_base,
                'ridge_vs_best_base': L.team_block_boot(
                    recs, 'ridge_B_announced', best_base),
                'armB_vs_armA': L.team_block_boot(
                    recs, 'ridge_B_announced', 'ridge_A_strict'),
                'ablation': {g: {'mae': per[f'minus_{g}']['mae'],
                                 'd_mae': per[f'minus_{g}']['mae']
                                 - per['ridge_B_announced']['mae']}
                             for g in GROUPS},
                'subgroups': {},
            }
            def sub(name, pred):
                sel = [x for x in recs if pred(x)]
                if len(sel) >= 60:
                    out[target][ev]['subgroups'][name] = {
                        'n': len(sel),
                        **{n: L.metrics([(x['y'], x[n]) for x in sel])['mae']
                           for n in (best_base, 'ridge_B_announced')}}
            sub('qb_change', lambda x: (x['row'].get('_prev_row') or {}).get('qb_id')
                not in (None, x['row'].get('qb_id')))
            sub('qb_stable', lambda x: (x['row'].get('_prev_row') or {}).get('qb_id')
                == x['row'].get('qb_id'))
            sub('coach_change', lambda x: (x['row'].get('_prev_row') or {}).get('coach')
                not in (None, x['row'].get('coach')))
            sub('coach_stable', lambda x: (x['row'].get('_prev_row') or {}).get('coach')
                == x['row'].get('coach'))
            sub('low_history', lambda x: len(x['row']['_h'].get(target) or []) < 8)
            sub('high_history', lambda x: len(x['row']['_h'].get(target) or []) >= 8)
            out[target][ev]['_recs_keys'] = names
        # Dumped after EVERY target. The first run reached the last
        # target and was then killed by its timeout during the final
        # json.dump, losing all nine results. Incremental writes cost
        # nothing and make that failure mode impossible.
        json.dump(out, open(f'{HERE}/p4_results.json', 'w'), indent=1,
                  default=float)
        print(f'\n=== {target}')
        for ev, d in out[target].items():
            p = d['per_model']
            bb = d['best_baseline']
            b = d['ridge_vs_best_base']
            verdict = ('BEATS' if b and b['hi'] < 0 else 'does NOT beat')
            print(f' {ev} n={d["n"]:4d} best_base={bb}={p[bb]["mae"]:.4f} '
                  f'ridge={p["ridge_B_announced"]["mae"]:.4f} '
                  f'r={p["ridge_B_announced"]["r"]:.3f} '
                  f'| {b["mean"]:+.4f}[{b["lo"]:+.4f},{b["hi"]:+.4f}] {verdict}')
    json.dump(out, open(f'{HERE}/p4_results.json', 'w'), indent=1, default=float)
    print('\nwrote p4_results.json')


if __name__ == '__main__':
    main()
