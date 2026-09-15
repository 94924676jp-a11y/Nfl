"""P3: the blast radius of the R11 rush composition, before against after.

WHAT A BLAST RADIUS IS FOR. A repair that closes its own defect and moves
something else is two results, and reporting only the first is how a fix
acquires a silent side effect. This reports the quantities most likely to move
-- carry means per club, the category partition, the touchdown containment --
next to the ones the repair targets, so both are read together.

    python3.12 nfl/research/v4/p3/p3_blast.py <before_dir> <after_dir>

It compares TWO SEALED BOARDS and nothing else. It does not rerun either, it
does not score either against an outcome, and there is no realized DEN@KC
result in this repository to score against: the newest 2026 play-by-play
capture predates the 2026-09-15T00:15Z kickoff and holds zero DEN or KC rows.
No realized carry count is a target here.

DECLARED TREATMENT. The two boards differ in `model_configuration` and in
nothing else the caller controls -- same game, same cutoff, same draw count,
same seed. Any OTHER difference in their execution identity is a defect in the
comparison, so the identities are printed side by side and a reader is told to
check them rather than being told they match.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))

from nfl.research.v4.p3.p3_measure import measure_board            # noqa: E402

FIELDS = ('rb_only_excess', 'qb_only_excess', 'rb_plus_qb_excess')


def _identity(d) -> dict:
    d = pathlib.Path(d)
    a = json.loads((d / 'forecast_artifact.json').read_text())
    b = json.loads((d / 'board.json').read_text())
    return {'run_id': b.get('run_id'),
            'model_configuration': a.get('model_configuration'),
            'game_id': a.get('game_id'),
            'kickoff_utc': a.get('kickoff_utc'),
            'written_at': a.get('written_at'),
            'n_draws': b.get('n_draws'),
            'components_applied': a.get('candidate_components_applied'),
            'code_commit': a.get('code_commit'),
            'spec_hash': a.get('spec_hash')}


def _player_carries(d):
    """{team: {gsis_id: mean carries}} -- the cells a reader would notice."""
    d = pathlib.Path(d)
    z = np.load(d / 'player_draws.npz')
    man = json.loads((d / 'player_draws_manifest.json').read_text())
    board = json.loads((d / 'board.json').read_text())
    team_of = {p['gsis_id']: p.get('team') for p in (board.get('players') or [])}
    ids = (man['layers'].get('rushing') or {}).get('row_ids') or []
    out = {}
    for i, g in enumerate(ids):
        out.setdefault(team_of.get(g), {})[g] = float(
            z['rushing__carries'][i].mean())
    return out


def main(argv) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    before, after = argv[1], argv[2]
    ib, ia = _identity(before), _identity(after)
    print('EXECUTION IDENTITY -- read both columns; a difference outside '
          '`model_configuration`, `run_id`, `written_at`, `code_commit` and '
          '`spec_hash` is a defect in this comparison, not a result.')
    for k in sorted(set(ib) | set(ia)):
        mark = ' ' if ib.get(k) == ia.get(k) else '*'
        print(f'  {mark} {k:<24} {str(ib.get(k))[:38]:<40} '
              f'{str(ia.get(k))[:38]}')
    mb, ma = measure_board(before), measure_board(after)
    print('\nCONTAINMENT, DECOMPOSED  (gate tolerance 0.5 carries)')
    for t in sorted(set(mb['teams']) & set(ma['teams'])):
        print(f'  {t}')
        for f in FIELDS:
            b, a = mb['teams'][t][f], ma['teams'][t][f]
            print(f'    {f:<20} over-gate {b["n_over"]:>4} -> {a["n_over"]:<4}'
                  f'   any-positive {b["n_positive"]:>4} -> '
                  f'{a["n_positive"]:<4}   max {b["max"]:+.4f} -> '
                  f'{a["max"]:+.4f}')
        for f in ('partition_declared_abs_max', 'partition_naive_abs_max',
                  'rb_category_split_abs_max'):
            if f in mb['teams'][t] and f in ma['teams'][t]:
                print(f'    {f:<20} {mb["teams"][t][f]:.4f} -> '
                      f'{ma["teams"][t][f]:.4f}')
        for f in ('rushing_td_exceeds_carries_cells',):
            if f in mb['teams'][t] and f in ma['teams'][t]:
                print(f'    {f:<20} {mb["teams"][t][f]} -> '
                      f'{ma["teams"][t][f]}')
        db, da = (mb['teams'][t].get('designed_qb_two_answers'),
                  ma['teams'][t].get('designed_qb_two_answers'))
        if db and da:
            print(f'    designed_qb          {db["state"]} -> {da["state"]}'
                  f'   cells disagreeing {db["cells_disagreeing"]} -> '
                  f'{da["cells_disagreeing"]}')
        print(f'    level mean           {mb["teams"][t]["level_mean"]:.4f} -> '
              f'{ma["teams"][t]["level_mean"]:.4f}   integer '
              f'{mb["teams"][t]["level_is_integer"]} -> '
              f'{ma["teams"][t]["level_is_integer"]}')
        print(f'    team carry mean      backs '
              f'{mb["teams"][t]["rb_mean"]:.4f} -> '
              f'{ma["teams"][t]["rb_mean"]:.4f}   QB rush '
              f'{mb["teams"][t]["qb_rush_opp_mean"]:.4f} -> '
              f'{ma["teams"][t]["qb_rush_opp_mean"]:.4f}   scrambles '
              f'{mb["teams"][t]["scrambles_mean"]:.4f} -> '
              f'{ma["teams"][t]["scrambles_mean"]:.4f}')
    pb, pa = _player_carries(before), _player_carries(after)
    print('\nPER-PLAYER CARRY MEANS  (every named back, both boards)')
    for t in sorted(set(pb) | set(pa)):
        for g in sorted(set(pb.get(t, {})) | set(pa.get(t, {}))):
            b, a = pb.get(t, {}).get(g), pa.get(t, {}).get(g)
            d = (f'{a - b:+.4f}' if b is not None and a is not None
                 else 'ROW PRESENT ON ONE BOARD ONLY')
            print(f'  {t} {g}  {"--" if b is None else f"{b:8.4f}"} -> '
                  f'{"--" if a is None else f"{a:8.4f}"}   {d}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
