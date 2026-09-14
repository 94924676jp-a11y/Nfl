"""U1 trial build: the rush-accounting repair, with and without its wiring.

WHY A HARNESS AND NOT A PRODUCTION EDIT. The repair itself lives in
`rushing_a1.allocate(qb_designed_rush=...)`, which U1 owns. The two lines that
FEED it live in `nfl/production/run_forecast.py`, which U1 does not own -- three
agents are editing this tree concurrently. So the wiring is applied here, at
research scope, exactly as it would read in production, and the production
patch is quoted verbatim in U1_RUSH_ACCOUNTING.md for its owner to apply.

    python3.12 nfl/research/v2/u1/u1_build.py baseline  <cut> <out> <draws>
    python3.12 nfl/research/v2/u1/u1_build.py wired     <cut> <out> <draws>

`baseline` patches nothing and must reproduce the sealed R9 board. `wired`
applies the two feed lines:

    1. SC1 couples the carry level against `rush_opp`, not against `scr`.
       A designed quarterback run is a team carry exactly as a scramble is,
       so the weaker bound was letting `rush_opp > team_carries` through --
       1 of 1,000 Kansas City draws on the sealed R9 board.
    2. `allocate` is given the QB layer's designed-rush count, so it stops
       drawing a second answer to that quantity.

Nothing is clipped, nothing is renormalised, nothing is fitted.
"""
from __future__ import annotations

import sys

sys.path.insert(0, '/home/user/nfl')

import numpy as np                                               # noqa: E402

from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.production.nonqb import football_engine as FE           # noqa: E402
from nfl.production.nonqb import rushing_a1 as RA1               # noqa: E402
from nfl.production.nonqb import scramble_coherence as SC1       # noqa: E402

GAME = '2026_01_DEN_KC'
_QB = {}


def _team_vectors():
    """{team: (scr, rush_opp)} from the QB object this run actually built."""
    qb = _QB.get('qb')
    if qb is None:
        raise RuntimeError(
            'the QB object was never captured, so the wiring cannot be '
            'applied. Refused rather than falling back to the unwired call, '
            'which would silently produce a baseline board under the wired '
            'label.')
    out = {}
    for t, rows in qb['index_by_team'].items():
        if not rows:
            continue
        scr = np.stack([np.asarray(qb['draws']['scr'][i], float)
                        for i in rows]).sum(0)
        ro = np.stack([np.asarray(qb['draws']['rush_opp'][i], float)
                       for i in rows]).sum(0)
        out[t] = (scr, ro)
    return out


def wire():
    _r2 = FE.apply_r2_level

    def apply_r2_level(qb, alloc, tv, teams):
        o = _r2(qb, alloc, tv, teams)
        if o.state is State.PASS:
            _QB['qb'] = o.value
        return o

    FE.apply_r2_level = apply_r2_level

    _couple = SC1.couple

    def couple(scrambles, carries):
        # THE BOUND THAT WAS TOO WEAK. `couple` is generic in its first
        # argument -- it is a per-draw lower bound on carries -- so the team
        # is identified by matching the vector it was handed, and the bound
        # is raised from scrambles to the QB's whole rush opportunity.
        s = np.asarray(scrambles, float)
        for t, (scr, ro) in _team_vectors().items():
            if scr.shape == s.shape and np.array_equal(scr, s):
                return _couple(ro, carries)
        raise RuntimeError(
            'SC1.couple was handed a scramble vector matching no team in the '
            'captured QB object. Refused rather than passed through: a '
            'silent pass-through here would publish a partially wired board.')

    SC1.couple = couple

    _allocate = RA1.allocate

    def allocate(season, week, teams, team_carries_draws, scramble_draws,
                 **kw):
        v = _team_vectors()
        kw['qb_designed_rush'] = {t: (v[t][1] - v[t][0]) for t in teams
                                  if t in v}
        return _allocate(season, week, teams, team_carries_draws,
                         scramble_draws, **kw)

    RA1.allocate = allocate


def main(argv):
    mode, cut, out = argv[1], argv[2], argv[3]
    draws = int(argv[4]) if len(argv) > 4 else 1000
    cfg = argv[5] if len(argv) > 5 else 'V1_CANDIDATE_R9'
    if mode not in ('baseline', 'wired'):
        raise SystemExit(f'mode must be baseline|wired, not {mode!r}')
    if mode == 'wired':
        wire()
    from nfl.tools import make_board as MB
    summary, board, run_dir = MB.build_one(
        2026, 1, GAME, cut, out, draws=draws, seed=20260908,
        model_configuration=cfg, dry_run=False)
    print(f'mode              {mode}')
    print(f'status            {summary.get("status")}')
    print(f'run_id            {summary.get("run_id")}')
    print(f'prospective_elig  {summary.get("prospective_eligible")}')
    print(f'run_dir           {run_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
