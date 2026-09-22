"""The only way a Classic lineup gets players: through the review gate.

There is no function here that takes a bare list of projections. The pool is
built from a written slate board and a gated draw artifact, and every refusal
the governance layer can raise propagates out of `build_pool` by name:

    PLAYER_REVIEW_NOT_RUN          no review artifact for this slate
    PLAYER_REVIEW_STALE            the review audited a different artifact
    UPSTREAM_RUN_REFUSED           the forecast run itself refused
    OPTIMIZATION_REFUSED_BY_...    the gate returned BLOCKED
    SALARY_ARTIFACT_ABSENT         nothing to price the pool with
    CLASSIC_POOL_NO_ELIGIBLE       everything was filtered out

A player reaches the pool only if he is CLEARED or CLEARED_WITH_WARNING on the
board, has a resolved salary, has a projection, and is not officially
inactive. Each exclusion is COUNTED AND NAMED in the result, because "the pool
is smaller than I expected" must always have an answer.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.classic import optimizer as OPT                        # noqa: E402
from nfl.production.review import gated_projection as GP            # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome        # noqa: E402

SPEC_VERSION = 'dk-nfl-classic-pool-1'

ELIGIBLE_VERDICTS = ('CLEARED', 'CLEARED_WITH_WARNING')

#: Board room -> DK roster position. DST is not a modelled room; it enters
#: only from the salary file and is named as such.
ROOM_TO_POSITION = {'dropbacks': 'QB', 'carries': 'RB', 'targets': 'WR',
                    'kicking': None}


def build_pool(*, board_dir, draws_dir, review_dir,
               dk_positions: Optional[Dict[str, str]] = None,
               dk_ids: Optional[Dict[str, str]] = None,
               allow_warnings: bool = True) -> Outcome:
    """The gate-passed, priced, projected Classic pool.

    `dk_positions` maps gsis_id -> DK position where the board's room is not
    enough to determine it (a pass-catching back is in the targets room but is
    an RB on DraftKings). Supplied by the salary artifact, which is the
    authority on what DraftKings will accept.
    """
    bp = pathlib.Path(board_dir) / 'PLAYER_BOARD.json'
    if not bp.exists():
        return Outcome.blocked(
            'BOARD_ABSENT',
            f'{bp} does not exist. A Classic pool is built from a written '
            f'board, never from projections passed in directly.',
            cause=Cause.DATA)
    board = json.loads(bp.read_text())

    # THE GATE. Not advisory: its refusal is this function's refusal.
    g = GP.load(draws_dir, review_dir, allow_warnings=allow_warnings)
    if g.state.name != 'PASS':
        from nfl.production.review import gate as GATE
        return Outcome.fail(
            g.code,
            f'the Classic pool cannot be built: {g.detail}',
            value={**GATE.payload(g), 'stage': 'classic_pool',
                   'board_dir': str(board_dir)})

    dk_positions = dict(dk_positions or {})
    dk_ids = dict(dk_ids or {})
    excluded: Dict[str, List[str]] = collections.defaultdict(list)
    players: List[OPT.Player] = []

    for r in board.get('rows') or ():
        pid, name = r.get('gsis_id'), r.get('player')
        verdict = r.get('review_verdict')
        if verdict not in ELIGIBLE_VERDICTS:
            excluded[f'review_{verdict}'].append(name)
            continue
        if str(r.get('availability')) == 'INACTIVE':
            excluded['officially_inactive'].append(name)
            continue
        sal = r.get('salary')
        if not isinstance(sal, (int, float)):
            excluded['no_resolved_salary'].append(name)
            continue
        dk = r.get('dk_mean')
        if not isinstance(dk, float):
            excluded['no_projection'].append(name)
            continue
        pos = dk_positions.get(pid) or ROOM_TO_POSITION.get(r.get('position'))
        if pos not in OPT.R.POSITIONS:
            excluded['no_dk_position'].append(name)
            continue
        players.append(OPT.Player(
            gsis_id=pid, name=name, position=pos, team=r.get('team'),
            opponent=r.get('opponent'), salary=int(sal),
            dk_id=dk_ids.get(pid), value=float(dk)))

    if not players:
        return Outcome.fail(
            'CLASSIC_POOL_NO_ELIGIBLE',
            f'no player on the board survived eligibility. Excluded: '
            f'{ {k: len(v) for k, v in excluded.items()} }. An empty pool is '
            f'reported with its reasons, never as "no valid lineups".',
            value={'excluded_counts': {k: len(v)
                                       for k, v in excluded.items()},
                   'excluded': {k: sorted(x for x in v if x)[:25]
                                for k, v in excluded.items()}})

    by_pos = collections.Counter(p.position for p in players)
    short = {pos: n for pos, n in OPT.R.BASE.items()
             if by_pos.get(pos, 0) < n}
    return Outcome.ok(
        'CLASSIC_POOL_BUILT',
        {'players': players, 'n_players': len(players),
         'by_position': dict(by_pos),
         'positions_short_of_a_legal_roster': short,
         'excluded_counts': {k: len(v) for k, v in excluded.items()},
         'excluded': {k: sorted(x for x in v if x)[:40]
                      for k, v in excluded.items()},
         'gate_verdict': g.value.get('verdict'),
         'gate_warnings': g.value.get('warning_count'),
         'draw_digest': g.value.get('draw_digest'),
         'board': str(bp), 'slate_key': board.get('slate_key'),
         'information_cut': board.get('information_cut'),
         'spec_version': SPEC_VERSION},
        detail=f'{len(players)} eligible of '
               f'{len(board.get("rows") or ())} board row(s); '
               f'gate {g.value.get("verdict")}; by position {dict(by_pos)}')
