"""RBDEP step 1: reproduce the B11 decomposition before changing anything.

Nothing here touches the ablation. It exists so that the harness is known to be
sound before it is used to score a comparison, and so that the four numbers
B11 rests on are attached to the artifact they were computed from.

    python3.12 nfl/research/rbdep/run_rbdep_baseline.py [PATH_TO_PAYLOAD.pkl]

The production payload is an ephemeral rehearsal artifact and is not in the
repository. If it is not supplied the reproduction of the production half is
recorded BLOCKED[DEPENDENCY] with the exact filename needed -- not skipped, and
not reported as agreement.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import rbdep_lib as L                                             # noqa: E402
import p4c_build as CB                                            # noqa: E402
from sportsplatform.governance.outcome import (                   # noqa: E402
    Cause, Outcome, State)

B11_QUOTED = {'within_counts': +0.081, 'within_shares': -0.179,
              'between_counts_median': +0.113, 'between_counts_p_gt_0': 0.68,
              'realised_between_counts': -0.329,
              'team_volume_variance_fraction': 0.287}


def production_half(path):
    if not path or not os.path.exists(path):
        return Outcome.blocked(
            'RBDEP_PRODUCTION_PAYLOAD_ABSENT',
            'the B11 model figures were computed on a 2026 week-1 rehearsal '
            'payload holding per-game carry draws and team_carries draws. It '
            'is ephemeral and not in this repository. Supply its path as '
            'argv[1] to reproduce that half.',
            cause=Cause.DEPENDENCY, looked_for=path)
    D = pickle_load(path)
    rb1, rb2, V = [], [], []
    for g in sorted(D):
        C = D[g]['draws']['carries']
        tt = np.array(D[g]['index']['rb_team'])
        for t in D[g]['index']['teams']:
            Z = C[tt == t]
            if Z.shape[0] < 2:
                continue
            o = np.argsort(-Z.mean(1))
            rb1.append(Z[o[0]])
            rb2.append(Z[o[1]])
            V.append(D[g]['team_draws'][t]['team_carries'])
    if len(rb1) < 2:
        return Outcome.blocked(
            'RBDEP_PRODUCTION_PAYLOAD_TOO_THIN',
            f'{len(rb1)} team-games carried two ranked backs', cause=Cause.DATA)
    N1 = np.stack(rb1).astype(float)
    N2 = np.stack(rb2).astype(float)
    T = np.stack(V).astype(float)
    d = L.dependence(N1, N2, T,
                     np.zeros(len(rb1)), np.zeros(len(rb1)),
                     np.zeros(len(rb1)))
    for k in ('realised_between_team_game_counts',
              'realised_between_team_game_shares'):
        d[k] = None            # this payload is a FORECAST; it has no outcome
    d['rank_rule'] = 'model predicted mean (B11 rule, NOT outcome-free-prior)'
    d['source'] = path
    return Outcome.ok('RBDEP_PRODUCTION_HALF_REPRODUCED', value=d, **{
        'n_team_games': d['n_team_games']})


def pickle_load(p):
    import pickle
    with open(p, 'rb') as fh:
        return pickle.load(fh)


def main():
    payload = sys.argv[1] if len(sys.argv) > 1 else None
    inp = L.load_inputs()
    if inp.state is not State.PASS:
        print(inp.code, inp.detail)
        json.dump({'inputs': inp.as_dict()},
                  open(f'{HERE}/rbdep_baseline.json', 'w'), indent=1)
        return 2
    rows, vol = inp.value
    seas = L.assert_no_future_season(rows)
    if seas.state is not State.PASS:
        print(seas.code, seas.detail)
        return 2
    pa = CB.appearance(rows)
    sub = CB.prepare_class(rows, L.CLS)
    pc = L.prior_week_carries(rows)

    out = {'inputs': inp.as_dict(), 'seasons': seas.as_dict(),
           'b11_quoted': B11_QUOTED, 'historical_half': {}}
    for rank_rule in ('prior_weeks', 'model_predicted_mean'):
        N1, N2, T, y1, y2, Ts = [], [], [], [], [], []
        for ev in L.EVAL:
            store = vol[('team_carries', ev)]
            par = CB.fit_params(sub, L.CLS, ev, rows)
            te = L.eligible_rows(sub, ev, pa, store)
            sim = L.simulate(te, par, pa, store, 'INC', 1.0, L.M_DRAWS)
            starts, counts = sim['starts'], sim['counts']
            y = np.array([r['y_carries'] for r in te], float)
            tstar = store['realized'][
                np.array([store['index'][(r['team'], r['ord'])]
                          for r in te], dtype=np.int64)[starts]].astype(float)
            for gi in range(len(starts)):
                s = int(starts[gi])
                e = s + int(counts[gi])
                if e - s < 2:
                    continue
                if rank_rule == 'prior_weeks':
                    pr = L.rank_two(te, s, e, pc)
                    if pr is None:
                        continue
                    i1, i2 = pr
                else:
                    o = np.argsort(-sim['draws'][s:e].mean(1))
                    i1, i2 = s + int(o[0]), s + int(o[1])
                N1.append(sim['draws'][i1])
                N2.append(sim['draws'][i2])
                T.append(sim['T'][gi])
                y1.append(y[i1])
                y2.append(y[i2])
                Ts.append(tstar[gi])
        d = L.dependence(np.stack(N1), np.stack(N2), np.stack(T),
                         np.array(y1), np.array(y2), np.array(Ts))
        d['rank_rule'] = rank_rule
        out['historical_half'][rank_rule] = d
        print(f'\nHISTORICAL frame, rank = {rank_rule}, '
              f'{d["n_team_games"]} team-games')
        print(f'  LIKE-FOR-LIKE between team-game, counts   median r '
              f'{d["LIKE_FOR_LIKE_between_team_game_counts"]["median"]:+.4f}  '
              f'P(r>0) '
              f'{d["LIKE_FOR_LIKE_between_team_game_counts"]["p_gt_zero"]:.3f}')
        print(f'  realised between team-game, counts               r '
              f'{d["realised_between_team_game_counts"]:+.4f}   '
              f'[B11 quotes {B11_QUOTED["realised_between_counts"]:+.4f}]')
        print(f'  NOT COMPARABLE within team-game across draws     r '
              f'{d["NOT_COMPARABLE_within_team_game_across_draws_counts"]:+.4f}'
              f'   [B11 quotes {B11_QUOTED["within_counts"]:+.4f}]')
        print(f'  team-volume variance fraction of RB1              '
              f'{d["team_volume_variance_fraction_of_RB1"]:.4f}   '
              f'[B11 quotes {B11_QUOTED["team_volume_variance_fraction"]:.3f}]')

    ph = production_half(payload)
    # `Outcome.as_dict()` carries state/code/detail/evidence and NOT `value`,
    # so recording only that would have written a file claiming a reproduction
    # and containing none of it. The measurement is stored explicitly.
    out['production_half'] = {
        'outcome': ph.as_dict(),
        'measured': ph.value if ph.state is State.PASS else None}
    if ph.state is State.PASS:
        d = ph.value
        print(f'\nPRODUCTION frame ({d["n_team_games"]} team-games, B11 rank '
              f'rule)')
        print(f'  NOT COMPARABLE within team-game counts  r '
              f'{d["NOT_COMPARABLE_within_team_game_across_draws_counts"]:+.4f}'
              f'   [B11 {B11_QUOTED["within_counts"]:+.4f}]')
        print(f'  NOT COMPARABLE within team-game shares  r '
              f'{d["NOT_COMPARABLE_within_team_game_across_draws_shares"]:+.4f}'
              f'   [B11 {B11_QUOTED["within_shares"]:+.4f}]')
        b = d['LIKE_FOR_LIKE_between_team_game_counts']
        print(f'  LIKE-FOR-LIKE between team-game counts  median '
              f'{b["median"]:+.4f}  P(r>0) {b["p_gt_zero"]:.3f}   '
              f'[B11 {B11_QUOTED["between_counts_median"]:+.4f} / '
              f'{B11_QUOTED["between_counts_p_gt_0"]:.2f}]')
        print(f'  corr of predictive MEANS (forbidden)    '
              f'{d["FORBIDDEN_corr_of_predictive_means"]:+.4f}')
    else:
        print(f'\nPRODUCTION frame: {ph.state.value}[{ph.code}] {ph.detail}')

    with open(f'{HERE}/rbdep_baseline.json', 'w') as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f'\n-> {HERE}/rbdep_baseline.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
