"""P3: the DECOMPOSED rush-accounting measurement, over any sealed board.

WHY DECOMPOSED, AND WHY THAT IS THE WHOLE POINT

The product gate fires `RUSH_ACCOUNTING_FAILURE` on one undecomposed quantity:
`RB carries + QB scrambles + QB designed runs` against the team carry level.
That quantity is the right one to GATE on -- a quarterback run is a team carry
exactly as a running back's is -- but it is the wrong one to REPAIR from,
because it sums two layers and says nothing about which one broke. An earlier
workstream read the fired gate as a defect in A1's multinomial and wrote a fix
for the running-back deal. Decomposed, the running-back deal is sound:

    2026_01_DEN_KC / 96954efc523bd7d3 (V1_CANDIDATE_R9, 1,000 draws)
      RB carries only      DEN 2/1000 max +0.2619   KC 2/1000 max +0.0854
      RB + QB rush opp     DEN 206/1000 max +6.1219 KC 237/1000 max +9.6915

So this script reports FOUR containment series per team and never their sum:
RB-only, QB-only, RB+QB, and the category partition. Run it before and after
any change to the rush path.

    python3.12 nfl/research/v4/p3/p3_measure.py <board_dir> [<board_dir> ...]

A board directory is one holding `player_draws.npz`,
`player_draws_manifest.json` and `board.json`.

WHAT IT DOES NOT DO. It reads sealed arrays and prints. It writes nothing into
a board, it repairs nothing, and it has no tolerance to widen: every count is
reported at its measured size next to the gate's declared 0.5-carry tolerance
so a reader can see both.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

# The product gate's own tolerance, quoted so the two cannot drift apart.
# nfl/product/quality_gates.py GROUNDING['RUSH_OVERALLOCATION_TOLERANCE'].
GATE_TOLERANCE = 0.5
EPS = 1e-9
CATEGORIES = ('kneel', 'designed_qb', 'rb', 'wr', 'te', 'fringe')


def _series(x) -> dict:
    a = np.asarray(x, np.float64).reshape(-1)
    return {'n_draws': int(a.size),
            'n_over': int((a > GATE_TOLERANCE).sum()),
            'n_positive': int((a > EPS).sum()),
            'max': float(a.max()) if a.size else float('nan'),
            'mean': float(a.mean()) if a.size else float('nan')}


def measure_board(board_dir) -> dict:
    """Every containment series this board can support, per team.

    RAISES rather than returning a partial dict when a required array is
    absent. A rush measurement that silently skipped the carry level would
    report "no violations" for a board that has no level to violate.
    """
    d = pathlib.Path(board_dir)
    z = np.load(d / 'player_draws.npz')
    man = json.loads((d / 'player_draws_manifest.json').read_text())
    board = json.loads((d / 'board.json').read_text())
    team_of = {p['gsis_id']: p.get('team') for p in (board.get('players') or [])}
    lay = man['layers']
    for need in ('team_volume', 'qb'):
        if need not in lay:
            raise SystemExit(f'{d}: no {need} layer sealed; nothing to measure')
    tv_rows = {t: i for i, t in enumerate(lay['team_volume']['row_ids'])}
    qb_ids = lay['qb']['row_ids']
    rush_ids = (lay.get('rushing') or {}).get('row_ids') or []
    rc_rows = {t: i for i, t in enumerate(
        (lay.get('rush_category') or {}).get('row_ids') or [])}
    pool_rows = {t: i for i, t in enumerate(
        (lay.get('rush_player_pool') or {}).get('row_ids') or [])}

    out = {'board_dir': str(d), 'run_id': man.get('run_id'),
           'n_draws': int(man.get('n_draws') or 0), 'teams': {}}
    for team in lay['team_volume']['row_ids']:
        lev = z['team_volume__team_carries'][tv_rows[team]].astype(np.float64)
        qi = [i for i, g in enumerate(qb_ids) if team_of.get(g) == team]
        ri = [i for i, g in enumerate(rush_ids) if team_of.get(g) == team]
        zero = np.zeros_like(lev)
        ro = z['qb__rush_opp'][qi].sum(0).astype(np.float64) if qi else zero
        scr = z['qb__scr'][qi].sum(0).astype(np.float64) if qi else zero
        rb = (z['rushing__carries'][ri].sum(0).astype(np.float64)
              if ri else zero)
        rec = {
            'n_named_backs': len(ri), 'n_quarterbacks': len(qi),
            'level_mean': float(lev.mean()),
            'level_is_integer': bool(
                not (np.abs(lev - np.rint(lev)) > EPS).any()),
            # FOUR SERIES, NEVER THEIR SUM.
            'rb_only_excess': _series(rb - lev),
            'qb_only_excess': _series(ro - lev),
            'rb_plus_qb_excess': _series(rb + ro - lev),
            'rb_mean': float(rb.mean()), 'qb_rush_opp_mean': float(ro.mean()),
            'scrambles_mean': float(scr.mean()),
        }
        if team in rc_rows:
            cat = {c: z['rush_category__' + c][rc_rows[team]].astype(
                np.float64) for c in CATEGORIES}
            tot = sum(cat.values())
            # TWO FORMS OF THE PARTITION, because they are different claims.
            #
            # `naive` compares the six categories against the team level and
            # is the comparison that produced the reported 8.4278 / 10.2027
            # non-closure. It omits the scrambles, which A1's ownership graph
            # subtracts from the budget BEFORE partitioning, and it compares
            # an integer partition against a continuous level.
            #
            # `declared` is A1's actual closure: the six categories plus the
            # scrambles equal the INTEGER level A1 partitioned.
            rec['partition_naive_abs_max'] = float(np.abs(tot - lev).max())
            rec['partition_declared_abs_max'] = float(
                np.abs(tot + scr - np.rint(lev)).max())
            rec['partition_declared_cells_open'] = int(
                (np.abs(tot + scr - np.rint(lev)) > EPS).sum())
            dq_a1 = cat['designed_qb']
            dq_qb = ro - scr
            rec['designed_qb_two_answers'] = {
                'a1_rush_category_designed_qb_mean': float(dq_a1.mean()),
                'qb_layer_rush_opp_minus_scr_mean': float(dq_qb.mean()),
                'cells_disagreeing': int((np.abs(dq_a1 - dq_qb) > EPS).sum()),
                'per_draw_difference_min': float((dq_a1 - dq_qb).min()),
                'per_draw_difference_max': float((dq_a1 - dq_qb).max()),
                'state': ('ONE_ANSWER'
                          if not (np.abs(dq_a1 - dq_qb) > EPS).any()
                          else 'TWO_ANSWERS')}
            if team in pool_rows and ri:
                pool = z['rush_player_pool__unmodelled_back_pool'][
                    pool_rows[team]].astype(np.float64)
                rec['rb_category_split_abs_max'] = float(
                    np.abs(cat['rb'] - rb - pool).max())
        if ri:
            rtd = z['rushing__rushing_td'][ri].astype(np.float64)
            car = z['rushing__carries'][ri].astype(np.float64)
            rec['rushing_td_exceeds_carries_cells'] = int((rtd > car + EPS).sum())
        out['teams'][team] = rec
    return out


def _fmt(rec, team) -> str:
    r = rec['teams'][team]
    L = [f'  {team}  level mean {r["level_mean"]:.4f}'
         f'  integer level {r["level_is_integer"]}'
         f'  backs {r["n_named_backs"]}  QBs {r["n_quarterbacks"]}']
    for k in ('rb_only_excess', 'qb_only_excess', 'rb_plus_qb_excess'):
        s = r[k]
        L.append(f'    {k:<20} over-gate {s["n_over"]:>4}/{s["n_draws"]}'
                 f'  any-positive {s["n_positive"]:>4}'
                 f'  max {s["max"]:+.4f}  mean {s["mean"]:+.4f}')
    if 'partition_declared_abs_max' in r:
        L.append(f'    partition declared  max|diff| '
                 f'{r["partition_declared_abs_max"]:.4f}   cells open '
                 f'{r["partition_declared_cells_open"]}'
                 f'   (naive form {r["partition_naive_abs_max"]:.4f})')
        t = r['designed_qb_two_answers']
        L.append(f'    designed_qb         {t["state"]}  A1 '
                 f'{t["a1_rush_category_designed_qb_mean"]:.4f} vs QB layer '
                 f'{t["qb_layer_rush_opp_minus_scr_mean"]:.4f}  disagreeing '
                 f'{t["cells_disagreeing"]}  per-draw ['
                 f'{t["per_draw_difference_min"]:+.0f},'
                 f'{t["per_draw_difference_max"]:+.0f}]')
    if 'rb_category_split_abs_max' in r:
        L.append(f'    rb split            max|rb_cat - backs - pool| '
                 f'{r["rb_category_split_abs_max"]:.4f}')
    if 'rushing_td_exceeds_carries_cells' in r:
        L.append(f'    rushing_td <= carries violations '
                 f'{r["rushing_td_exceeds_carries_cells"]}')
    return '\n'.join(L)


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    everything = []
    for d in argv[1:]:
        rec = measure_board(d)
        print(f'== {rec["board_dir"]}  run_id {rec["run_id"]}  '
              f'draws {rec["n_draws"]}')
        for t in sorted(rec['teams']):
            print(_fmt(rec, t))
        everything.append(rec)
    print()
    print(json.dumps(everything, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
