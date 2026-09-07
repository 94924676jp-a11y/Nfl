"""P4 §PROE: rebuild xPass from primitives, fitted only on prior seasons.

WHY REBUILD RATHER THAN USE nflfastR's COLUMN

`xpass` and `pass_oe` ship in the pbp file. Their fitting window is not
documented in the artifact, so a model fitted on 2016-2024 would make the 2024
column partly a function of 2024 -- which is exactly the leakage the directive
forbids. They are quarantined and not read.

THE RECONSTRUCTION, AND WHAT MAKES IT SAFE

xPass_hat = P(dropback | down, ydstogo, yardline, score differential, seconds
remaining, half, timeouts), logistic, fitted on seasons STRICTLY BEFORE the
evaluation season. PROE for a team-game is then
    (realised dropbacks - sum of xPass_hat over that game's plays) / plays
which is a property of that game, used only as a FEATURE for later games.

Two separate leakage questions, kept apart:
  1. does the xPass MODEL see the evaluation season?  No -- fitted on prior only.
  2. does a team-game's PROE feature see its own game?  No -- lagged by
     attach_history, same as every other feature.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p4lib as L

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    plays = np.load(f'{HERE}/play_state.npy', allow_pickle=True)
    seasons = plays[:, 0].astype(int)
    print(f'play-state rows: {len(plays)}  seasons {seasons.min()}-{seasons.max()}')

    out = {}
    proe_by_game = {}
    for ev in L.EVAL:
        tr = plays[seasons < ev]
        te = plays[seasons <= ev]                  # need PROE for all prior too
        Xtr = np.array([L.xpass_features(int(p[3]), float(p[4]), float(p[5]),
                                         float(p[6]), float(p[7]), int(p[8]),
                                         int(p[9])) for p in tr])
        ytr = tr[:, 10].astype(float)
        m = L.fit_logistic(Xtr, ytr, l2=1.0, iters=400)
        Xte = np.array([L.xpass_features(int(p[3]), float(p[4]), float(p[5]),
                                         float(p[6]), float(p[7]), int(p[8]),
                                         int(p[9])) for p in te])
        p_hat = L.pred_logistic(m, Xte)
        yte = te[:, 10].astype(float)
        # in-sample-of-the-model diagnostics on the TRAINING seasons only
        ptr = L.pred_logistic(m, Xtr)
        brier_tr = float(np.mean((ptr - ytr) ** 2))
        # aggregate to team-games
        agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
        for row, ph, yy in zip(te, p_hat, yte):
            k = (int(row[0]), int(row[1]), str(row[2]))
            g = agg[k]
            g[0] += ph; g[1] += yy; g[2] += 1
        for k, (xp, act, n) in agg.items():
            if n >= 20:
                proe_by_game.setdefault(ev, {})[k] = {
                    'xpass_rate': xp / n, 'act_rate': act / n,
                    'proe': (act - xp) / n, 'n_plays': n}
        out[ev] = {'n_train_plays': len(tr), 'train_brier': brier_tr,
                   'train_base_rate': float(ytr.mean()),
                   'n_team_games': len(proe_by_game[ev])}
        print(f' {ev}: fitted on {len(tr):,} prior plays '
              f'(base rate {ytr.mean():.4f}, train Brier {brier_tr:.4f}) '
              f'-> PROE for {len(proe_by_game[ev]):,} team-games')

    # reliability of PROE, using the 2025 model (widest training window)
    ev = L.EVAL[-1]
    tbl = proe_by_game[ev]
    byteam = collections.defaultdict(list)
    for (s, w, t), v in sorted(tbl.items()):
        byteam[t].append((s, w, v['proe'], v['act_rate']))
    def split_half_r(seq_key):
        a, b = [], []
        for t, seq in byteam.items():
            vals = [x[seq_key] for x in seq]
            if len(vals) < 16:
                continue
            a.append(float(np.mean(vals[0::2]))); b.append(float(np.mean(vals[1::2])))
        return float(np.corrcoef(a, b)[0, 1]), len(a)
    def week_to_week_r(seq_key):
        x, y = [], []
        for t, seq in byteam.items():
            for i in range(len(seq) - 1):
                if seq[i][0] == seq[i + 1][0]:
                    x.append(seq[i][seq_key]); y.append(seq[i + 1][seq_key])
        return float(np.corrcoef(x, y)[0, 1]), len(x)
    def yoy_r(seq_key):
        byts = collections.defaultdict(list)
        for t, seq in byteam.items():
            s2 = collections.defaultdict(list)
            for s, w, pr, ar in seq:
                s2[s].append(pr if seq_key == 2 else ar)
            for s in s2:
                byts[(t, s)] = float(np.mean(s2[s]))
        x, y = [], []
        for (t, s), v in byts.items():
            if (t, s + 1) in byts:
                x.append(v); y.append(byts[(t, s + 1)])
        return float(np.corrcoef(x, y)[0, 1]), len(x)

    rel = {
        'proe_split_half_r': split_half_r(2),
        'proe_week_to_week_r': week_to_week_r(2),
        'proe_year_over_year_r': yoy_r(2),
        'raw_pass_rate_split_half_r': split_half_r(3),
        'raw_pass_rate_week_to_week_r': week_to_week_r(3),
        'raw_pass_rate_year_over_year_r': yoy_r(3),
    }
    print('\nreliability (PROE vs raw pass rate):')
    for k, (r, n) in rel.items():
        print(f'  {k:<34} r={r:+.4f}  n={n}')

    json.dump({'fits': out, 'reliability': {k: {'r': v[0], 'n': v[1]}
                                            for k, v in rel.items()}},
              open(f'{HERE}/proe_fit.json', 'w'), indent=1, default=float)
    # persist PROE per team-game using each evaluation season's own model
    flat = {}
    for ev, tbl in proe_by_game.items():
        for k, v in tbl.items():
            flat[f'{ev}|{k[0]}|{k[1]}|{k[2]}'] = v
    json.dump(flat, open(f'{HERE}/proe_by_game.json', 'w'))
    print(f'\nwrote proe_by_game.json: {len(flat)} (eval-season, team-game) entries')


if __name__ == '__main__':
    main()
