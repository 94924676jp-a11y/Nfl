"""Research arms for the depth-rank tie and rank-ceiling semantics (process-local patches; never production).

A1_ORDER   one total order inside a room instead of the minimum of two orderings: rank = sorted by (min rank, the
           rank that came from the club's captured chart first, usage rank, observed share desc, id). A tie between a
           chart-1 and a usage-1 player is broken by the chart, as measured best in 2026 W2-W4 (28 of 47 tied rooms picked
           the realised room leader, against 18 for id order and 11 for usage).
A2_FORMATION  A1 plus a position-aware ceiling from the formation role_state's own comments declare (three WRs start,
           one RB, one TE): a WR's ceiling is read at effective rank max(1, rank - 2), so WR2 and WR3 are starters with the
           DEPTH_RANK_1 ceiling and the existing one-ALPHA-per-room rule orders them; RB/TE unchanged.
"""
import inspect, os
from nfl.tools import role_state as RS

STARTERS = {'WR': 3, 'RB': 1, 'TE': 1, 'QB': 1}


def _chart_first_key(row, dk_id):
    r, u = row.get('depth_rank'), row.get('depth_usage_rank')
    chart_derived = (u is None) or (isinstance(u, int) and r < u)
    share = (((row.get('observed_2026') or {}).get('combined') or {}).get('target_share') or 0)
    return (r, 0 if chart_derived else 1, u if isinstance(u, int) else 99, -share, dk_id)


def ranks_total_order(players):
    buckets = {}
    for dk_id, row in players.items():
        if (row.get('current_availability') or {}).get('status') in RS.AV.ABSENT_STATUSES:
            continue
        if isinstance(row.get('depth_rank'), int):
            buckets.setdefault((row.get('team'), row.get('position')), []).append(dk_id)
    out = {}
    for ids in buckets.values():
        ids.sort(key=lambda k: _chart_first_key(players[k], k))
        for i, k in enumerate(ids, 1):
            out[k] = i
    return out


def _ceiling_rank(rank, pos):
    return max(1, rank - (STARTERS.get(pos, 1) - 1))


def apply(arm):
    if arm in ('A1_ORDER', 'A2_FORMATION'):
        RS._position_scoped_ranks = ranks_total_order
    if arm == 'A2_FORMATION':
        src = inspect.getsource(RS.assign)
        old = ("key = ('DEPTH_RANK_1' if rank == 1 else 'DEPTH_RANK_2' if rank == 2\n"
               "                   else 'DEPTH_RANK_3' if rank == 3 else 'DEPTH_RANK_4_PLUS')")
        assert src.count(old) == 1, 'assign source changed; refuse to patch blindly'
        new = ("erank = _ceiling_rank(rank, pos)\n"
               "            key = ('DEPTH_RANK_1' if erank == 1 else 'DEPTH_RANK_2' if erank == 2\n"
               "                   else 'DEPTH_RANK_3' if erank == 3 else 'DEPTH_RANK_4_PLUS')")
        RS.__dict__['_ceiling_rank'] = _ceiling_rank
        exec(compile(src.replace(old, new), RS.__file__, 'exec'), RS.__dict__)
    return arm


# A3_APPEARANCE: one change against the incumbent, independent of A1/A2. The allocator's P(plays) for an
# allocation rank is a CLUB-SLOT rate (share of club-weeks with at least r players recording the measure). For a
# rank >= 2 player who recorded a measure in every 2026 week before the slate (up to the last 3), use instead the
# measured rate at which such a player appears again, 2021-2025 only (APPEARANCE_CHECK_THROUGH2025.json), when it is
# higher. Rank 1 is unchanged. The table is measured, not fitted to any replayed week.
A3_TABLE = {'RB': {2: 0.798, 3: 0.752, 4: 0.5}, 'WR': {2: 0.83, 3: 0.777, 4: 0.673, 5: 0.673, 6: 0.6},
            'TE': {2: 0.706, 3: 0.672}}


def apply_a3():
    from nfl.tools import proj_v1 as PV
    src = inspect.getsource(PV.allocate_opportunity)
    old = ("                appear[i] = row.get('appearance_rate')\n"
           "                if appear[i] is None:\n"
           "                    appear[i] = 0.0 if beyond else 1.0\n")
    assert src.count(old) == 1, 'allocate_opportunity source changed; refuse to patch blindly'
    new = old + ("                if pos in _A3_TABLE and rank >= 2:\n"
                 "                    _cn = crows[i].get('current_season_weeks') or 0\n"
                 "                    if _cn > 0 and _cn >= min(3, SLATE_WEEK - 1):\n"
                 "                        _m = _A3_TABLE[pos].get(min(rank, max(_A3_TABLE[pos])))\n"
                 "                        if _m is not None and _m > (appear[i] or 0.0):\n"
                 "                            appear[i] = _m\n")
    PV.__dict__['_A3_TABLE'] = A3_TABLE
    exec(compile(src.replace(old, new), PV.__file__, 'exec'), PV.__dict__)


_apply_base = apply
def apply(arm):
    if arm == 'A3_APPEARANCE':
        apply_a3(); return arm
    return _apply_base(arm)
