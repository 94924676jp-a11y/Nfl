"""RESEARCH ARM TIE-1 (not production): a tie in the supplied depth order is not broken by an identifier.
Tied players share the competition rank (1, 1, 3); the existing one-ALPHA-per-room rule then picks the ALPHA by
observed share. Tie handling ONLY (absent-rank fix not included, so this is one change against the incumbent). Applied as a process-local patch of role_state._position_scoped_ranks."""
from nfl.tools import role_state as RS


def _ranks_tie_aware(players):
    buckets = {}
    for dk_id, row in players.items():
        r = row.get('depth_rank')
        if isinstance(r, int):
            buckets.setdefault((row.get('team'), row.get('position')), []).append((r, dk_id))
    scoped = {}
    for rows in buckets.values():
        rows.sort()
        for i, (r, dk_id) in enumerate(rows, start=1):
            first = next(j for j, (rr, _) in enumerate(rows, start=1) if rr == r)
            scoped[dk_id] = first
    return scoped


RS._position_scoped_ranks = _ranks_tie_aware
