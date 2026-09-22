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
board, has a resolved salary, has a projection, and CANONICAL FOOTBALL STATE
does not say he will not play.

ELIGIBILITY IS A CANONICAL QUESTION, NOT A STRING COMPARISON

This module used to exclude on `availability == 'INACTIVE'`. That was correct
when the vocabulary held two values and became a LIVE DEFECT the moment the
availability slice made INJURY_OUT reachable: a player his club had declared
OUT passed the test, because the string was not the string. It now asks
`AV.will_not_play`, which is the canonical membership test and is tied to
`AV.WILL_NOT_PLAY` rather than to a literal copied here. QUESTIONABLE,
DOUBTFUL, NOT_ON_INACTIVE_LIST and UNKNOWN are none of them will-not-play.

EVERY REMOVAL IS RECORDED, AND GOVERNANCE IS KEPT APART FROM STRATEGY

A count is not an answer. `nfl/dfs/exclusion.py` carries a typed ledger in
which a player removed because his club declared him out is a GOVERNANCE
exclusion -- he may not enter -- and one removed by a projection cutoff is a
STRATEGY exclusion -- he could enter and was not used. Reporting both as
"excluded: 6" loses the only distinction that matters.

PREVENTION IS NOT PROOF

Excluding him is the preventive mechanism. `dfs/eligibility_integrity.py` is
the detective one: after the pool is built it compares canonical availability
against the populations that actually exist, and this function REFUSES on a
finding. A prevention nobody verifies is a prevention nobody can trust.
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

from nfl.dfs import eligibility_integrity as EI                     # noqa: E402
from nfl.dfs import exclusion as EX                                 # noqa: E402
from nfl.dfs.classic import optimizer as OPT                        # noqa: E402
from nfl.production.integrity import contract as IC                 # noqa: E402
from nfl.production.review import gated_projection as GP            # noqa: E402
from nfl.production.state import availability as AV                 # noqa: E402
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
    ledger = EX.ExclusionLedger()
    state_identity = board.get('run_identity') or board.get('state_identity')
    players: List[OPT.Player] = []

    def drop(r, bucket, reason, detail=None):
        excluded[bucket].append(r.get('player'))
        ledger.add(gsis_id=r.get('gsis_id'), name=r.get('player'),
                   team=r.get('team'), reason=reason,
                   excluded_from=EX.FROM_OPTIMIZER,
                   availability=r.get('availability'),
                   evidence_grade=r.get('evidence_grade'),
                   state_identity=state_identity, detail=detail)

    for r in board.get('rows') or ():
        pid, name = r.get('gsis_id'), r.get('player')
        verdict = r.get('review_verdict')
        if verdict not in ELIGIBLE_VERDICTS:
            drop(r, f'review_{verdict}', EX.BLOCKED_BY_REVIEW,
                 f'review verdict {verdict}')
            continue
        # CANONICAL, not a literal. See the module docstring.
        if AV.will_not_play(r.get('availability')):
            drop(r, 'will_not_play', EX.WILL_NOT_PLAY,
                 f'canonical availability '
                 f'{AV.canonical(r.get("availability"))} asserts he will not '
                 f'take the field')
            continue
        if not pid:
            drop(r, 'identity_unresolved', EX.IDENTITY_UNRESOLVED,
                 'the board row carries no canonical id, so nothing in a '
                 'lineup could be attributed to this person')
            continue
        sal = r.get('salary')
        if not isinstance(sal, (int, float)):
            drop(r, 'no_resolved_salary', EX.NO_RESOLVED_SALARY)
            continue
        dk = r.get('dk_mean')
        if not isinstance(dk, float):
            drop(r, 'no_projection', EX.NO_PROJECTION)
            continue
        pos = dk_positions.get(pid) or ROOM_TO_POSITION.get(r.get('position'))
        if pos not in OPT.R.POSITIONS:
            drop(r, 'no_dk_position', EX.NO_DK_POSITION,
                 f'board room {r.get("position")!r} and DK position '
                 f'{dk_positions.get(pid)!r}')
            continue
        players.append(OPT.Player(
            gsis_id=pid, name=name, position=pos, team=r.get('team'),
            opponent=r.get('opponent'), salary=int(sal),
            dk_id=dk_ids.get(pid), value=float(dk)))

    # DETECTION, after prevention. The boundary that built the populations
    # proves its own handoff, and a failure here refuses the pool rather
    # than being reported alongside it.
    gv = GP.payload(g) if hasattr(GP, 'payload') else (g.value or {})
    integrity = EI.will_not_play_in_dfs_populations(
        board_rows=board.get('rows') or (),
        pool_players=players,
        simulation_layers=(g.value or {}).get('layers'),
        simulation_arrays=(g.value or {}).get('arrays'),
        slate_key=board.get('slate_key'),
        information_cut=board.get('information_cut'),
        source_artifacts={'player_draws.npz':
                          (g.value or {}).get('draw_digest') or ''})
    if integrity.findings:
        return Outcome.fail(
            EI.C_INACTIVE_IN_POOL,
            f'{len(integrity.findings)} player(s) the canonical football '
            f'state says will not play survived into a governed DFS '
            f'population. The pool is refused rather than returned with a '
            f'warning: a lineup built from it could roster a man who is not '
            f'playing.',
            value={'integrity': integrity.as_dict(),
                   'exclusions': ledger.as_dict(),
                   'stage': 'classic_pool'})

    if not players:
        return Outcome.fail(
            'CLASSIC_POOL_NO_ELIGIBLE',
            f'no player on the board survived eligibility. Excluded: '
            f'{ {k: len(v) for k, v in excluded.items()} }. An empty pool is '
            f'reported with its reasons, never as "no valid lineups".',
            value={'excluded_counts': {k: len(v)
                                       for k, v in excluded.items()},
                   'excluded': {k: sorted(x for x in v if x)[:25]
                                for k, v in excluded.items()},
                   'exclusions': ledger.as_dict(),
                   'integrity': integrity.as_dict()})

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
         'exclusions': ledger.as_dict(),
         'integrity': integrity.as_dict(),
         'integrity_coverage': {
             EI.C_INACTIVE_IN_POOL:
                 integrity.state_of(EI.C_INACTIVE_IN_POOL)},
         'gate_verdict': g.value.get('verdict'),
         'gate_warnings': g.value.get('warning_count'),
         'draw_digest': g.value.get('draw_digest'),
         'board': str(bp), 'slate_key': board.get('slate_key'),
         'information_cut': board.get('information_cut'),
         'spec_version': SPEC_VERSION},
        detail=f'{len(players)} eligible of '
               f'{len(board.get("rows") or ())} board row(s); '
               f'gate {g.value.get("verdict")}; by position {dict(by_pos)}')
