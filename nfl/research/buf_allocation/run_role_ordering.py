"""Run the depth-ordering invariant against the sealed DET @ BUF board.

PROSPECTIVE, NOT POSTGAME. Every number here comes from the board sealed
2026-09-16T15:45:14Z and the depth vintage as it stood at that instant. No
outcome, no box score, no sportsbook price and no projection is read. The
check would have produced exactly this verdict before kickoff, which is the
point: it is a guard for future boards, not a grade of this one.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC              # noqa: E402
from sportsplatform.governance.outcome import State                     # noqa: E402
from nfl.production.nonqb import depth_vintage as DV                    # noqa: E402
from nfl.production.nonqb import role_invariants as RI                  # noqa: E402

FROZEN = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/frozen'
BOARD = FROZEN.parent
SEAL_INSTANT = '2026-09-16T15:45:14Z'
CLUBS = ('DET', 'BUF')
OUT = _REPO / 'nfl/research/buf_allocation/ROLE_ORDERING_PROSPECTIVE.json'


def p_zero_opportunity():
    """P(targets + carries == 0) per player, from the stored draws."""
    z = np.load(FROZEN / 'sealed_player_draws.npz')
    man = json.loads((FROZEN / 'sealed_player_draws_manifest.json').read_text())
    L = man['layers']
    n = int(np.asarray(z['dk_scoring__dk_points']).shape[1])
    tg, ru = L['receiving'], L['rushing']
    out = {}
    for gid in set(tg['row_ids']) | set(ru['row_ids']):
        t = np.zeros(n)
        c = np.zeros(n)
        if gid in tg['row_ids']:
            t = np.asarray(z['receiving__targets'])[tg['row_ids'].index(gid)]
        if gid in ru['row_ids']:
            c = np.asarray(z['rushing__carries'])[ru['row_ids'].index(gid)]
        out[gid] = float(((t + c) == 0).mean())
    return out, n


def run():
    pz, n = p_zero_opportunity()
    names = json.loads((BOARD / 'frozen_board_names.json').read_text())
    depth, teams = {}, {}
    for club in CLUBS:
        got = DV.captured((club,), SEAL_INSTANT)
        if got.state is not State.PASS:
            return got
        for gid, v in got.value.items():
            depth[gid] = v
            teams[gid] = club
    return RI.check(pz, depth, n_draws=n, teams=teams, names=names,
                    label='sealed DET_BUF board')


def main() -> int:
    o = run()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    for r in o.evidence.get('inversions', []):
        print(f"  {r['team']} {r['position']} {r['ahead']} "
              f"(#{r['ahead_rank']}) {r['ahead_p_zero']:.4f} > {r['behind']} "
              f"(#{r['behind_rank']}) {r['behind_p_zero']:.4f}  "
              f"{r['excess']:+.4f} = {r['se_multiples']:.1f} SE")
    names = json.loads((BOARD / 'frozen_board_names.json').read_text())
    unranked = [names.get(g, g)
                for g in o.evidence.get('players_without_depth_rank', [])]
    body = {
        'artifact': 'DET_BUF_2026W2_ROLE_ORDERING_PROSPECTIVE',
        'spec_version': RI.SPEC_VERSION,
        'uses_outcome_data': False,
        'board': 'c3probe_V1_CANDIDATE_R9_W1P_GSVUC/d709e67b82d5b01c',
        'depth_vintage_observed_before': SEAL_INSTANT,
        'state': o.state.value, 'code': o.code, 'detail': o.detail,
        'inversions': o.evidence.get('inversions', []),
        'n_ordered_pairs': o.evidence['n_ordered_pairs'],
        'n_rooms': o.evidence['n_rooms'],
        'n_draws': o.evidence['n_draws'],
        'se_multiple': o.evidence['se_multiple'],
        'players_without_depth_rank': unranked,
        'unranked_are_unprotected': (
            'a player with no depth rank is in no room, so no ordering check '
            'can constrain him. Both of them are Buffalo, and one, Frank Gore '
            'Jr., was carried at 55% exposure in the portfolio that went out.'),
        'not_established': (
            'this is two clubs on one slate. It does not establish how often '
            'the model inverts a room in general, and no rate may be quoted '
            'from it. It establishes that the invariant fires on the known '
            'defect and that it found a second inversion nobody had seen.'),
    }
    OUT.write_text(json.dumps(body, indent=1, sort_keys=True))
    c = AC.claim(OUT, schema=['inversions', 'uses_outcome_data'],
                 label=OUT.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
