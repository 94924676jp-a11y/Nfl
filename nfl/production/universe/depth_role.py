"""Typed depth-chart roles. A rank may only inform the room it was ranked in.

THE DEFECT CLASS, AND A CORRECTION TO MY OWN EARLIER CLAIM

I reported in commit c182e68 that `role_prior` reads Tyrone Tracy's KR2
listing as RB2 and that this caused the Skattebo/Tracy inversion. **That was
wrong and is retracted here.** Two measurements refute it:

  1. `depth_vintage.daily` already excludes the return groups by construction:
     "`KR`, `PR` and `KOR` are `pos_abb` values in this vendor ... `pos not in
     SKILL` already drops them before any ordering happens. Verified on the
     six persisted blobs: 104 KR rows and 81 PR rows read, 0 reaching a rank."

  2. The live production map, read at tonight's cut, returns
     Skattebo ('RB', 1), Najee Harris ('RB', 2), Singletary ('RB', 3),
     **Tracy ('RB', 4)**. The engine's depth view of that room is correct.

The KR2 and KR3 I saw came from `player_universe`, which reads a different,
coarser depth blob and attaches `depth_pos_abb` unfiltered. That is a real bug
in the candidate universe layer -- mine -- and not the production path.

WHAT IS STILL REAL, MEASURED TONIGHT

The cross-group leak exists; it is simply a different instance. Production
builds its rank map with `dr[k] = v[1]`, keeping the rank and DISCARDING the
position group `v[0]`. `assign_tiers` then groups players by their MODEL
position. Where the two disagree, a rank crosses rooms. On tonight's pool,
3 of 31 ranked players disagree:

    Patrick Ricard   model RB   depth group FB   rank 1
    Harrison Mevis   model K    depth group PK   rank 1
    Dominic Zvada    model K    depth group PK   rank 1

Ricard is the consequential one: a fullback's FB1 becomes a rank-1 anchor
inside the New York running back room, which is the lead back's anchor. The
kicker cases are harmless because a kicking room holds one kicker, but they
are the same defect and are guarded the same way.

THE RULE

A depth rank may inform a positional workload prior only when the depth
position group maps to the same model room. Otherwise the answer is
OFFENSIVE_DEPTH_UNKNOWN -- an explicit state, never a borrowed rank from
another group, and never a silent absence that reads as "unlisted".

Special-teams standing is not destroyed by this: it is returned on its own
axis, so a player can be KR2 on special teams and OFFENSIVE_DEPTH_UNKNOWN at
the same time without either contaminating the other.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

SPEC_VERSION = 'typed-depth-role-1'

OFFENSIVE_DEPTH_UNKNOWN = 'OFFENSIVE_DEPTH_UNKNOWN'

#: Depth-chart position groups that genuinely rank an OFFENSIVE workload
#: room, mapped to the model room they may inform.
OFFENSIVE_DEPTH_GROUPS: Dict[str, str] = {
    'QB': 'QB',
    'RB': 'RB', 'HB': 'RB',
    'FB': 'FB',
    'WR': 'WR',
    'TE': 'TE',
    'PK': 'K', 'K': 'K',
}

#: Groups that are special-teams standing and rank NO offensive room.
SPECIAL_TEAMS_GROUPS = frozenset({'KR', 'PR', 'KOR', 'LS', 'P', 'ST', 'H'})

#: Model positions folded to the room whose rank may inform them. FB is kept
#: DISTINCT from RB: a fullback's FB1 is first among fullbacks, not first
#: among running backs, and collapsing them is the Ricard leak.
MODEL_ROOM: Dict[str, str] = {
    'QB': 'QB', 'RB': 'RB', 'HB': 'RB', 'FB': 'FB',
    'WR': 'WR', 'TE': 'TE', 'K': 'K', 'PK': 'K',
}


def _neg(text: str):
    """Sort a string descending inside an ascending multi-key sort."""
    return tuple(-ord(c) for c in text)


def classify_group(depth_group: Optional[str]) -> str:
    """OFFENSIVE, SPECIAL_TEAMS or UNRECOGNISED for one depth position group."""
    g = (depth_group or '').strip().upper()
    if not g:
        return 'ABSENT'
    if g in OFFENSIVE_DEPTH_GROUPS:
        return 'OFFENSIVE'
    if g in SPECIAL_TEAMS_GROUPS:
        return 'SPECIAL_TEAMS'
    return 'UNRECOGNISED'


def offensive_depth_rank(model_position: Optional[str],
                         depth_group: Optional[str],
                         rank) -> Tuple[Optional[int], str]:
    """The rank this player may carry into his workload room, or an explicit state.

    Returns (rank_or_None, reason). A rank survives only when the depth group
    and the model position resolve to the SAME room. Anything else returns
    None with a named reason, so a caller cannot mistake a refusal for an
    absence and cannot borrow a rank across rooms.
    """
    mp = (model_position or '').strip().upper()
    kind = classify_group(depth_group)
    try:
        r = int(rank)
    except (TypeError, ValueError):
        r = None
    if r is None:
        return None, f'{OFFENSIVE_DEPTH_UNKNOWN}:NO_RANK'
    if kind == 'ABSENT':
        return None, f'{OFFENSIVE_DEPTH_UNKNOWN}:NO_DEPTH_GROUP'
    if kind == 'SPECIAL_TEAMS':
        return None, (f'{OFFENSIVE_DEPTH_UNKNOWN}:SPECIAL_TEAMS_GROUP:'
                      f'{(depth_group or "").upper()}{r}')
    if kind == 'UNRECOGNISED':
        return None, (f'{OFFENSIVE_DEPTH_UNKNOWN}:UNRECOGNISED_GROUP:'
                      f'{(depth_group or "").upper()}')
    want = MODEL_ROOM.get(mp)
    got = OFFENSIVE_DEPTH_GROUPS[(depth_group or '').strip().upper()]
    if want is None:
        return None, f'{OFFENSIVE_DEPTH_UNKNOWN}:MODEL_POSITION_NOT_A_ROOM:{mp}'
    if want != got:
        return None, (f'{OFFENSIVE_DEPTH_UNKNOWN}:GROUP_MISMATCH:'
                      f'depth={got}{r} model={want}')
    return r, f'OFFENSIVE_DEPTH_RANK:{got}{r}'


def special_teams_role(depth_group: Optional[str], rank) -> Optional[str]:
    """The special-teams standing, on its own axis. Never touches a workload room."""
    if classify_group(depth_group) != 'SPECIAL_TEAMS':
        return None
    try:
        return f'{(depth_group or "").strip().upper()}{int(rank)}'
    except (TypeError, ValueError):
        return (depth_group or '').strip().upper() or None


def select_listings(rows, model_position: Optional[str]) -> Dict[str, object]:
    """Pick this player's offensive listing and his special-teams listing.

    ONE ROW PER PLAYER WAS THE DEFECT. A club lists the same man in several
    groups -- RB1 and PR2, WR5 and KR3 and PR1 -- and a collapse to one row
    has to discard all but one of them. Worse, every row in a nflverse depth
    capture carries the SAME `dt`, so a `newest wins` rule never fires and
    the survivor is decided by the order the rows happen to sit in the file.
    Measured on the 2026-09-21 capture: Kyren Williams (RB1 / PR2) survived as
    PR2, Tyrone Tracy Jr. (RB4 / KR2) survived as KR2, Blake Corum (RB2 / KR4)
    as KR4. Each then read OFFENSIVE_DEPTH_UNKNOWN -- correctly, because by
    then the offensive row was gone.

    So nothing is collapsed here. The two axes are selected independently and
    both are returned. Selection within an axis is fully ordered -- newest
    `dt`, then lowest rank, then group name -- so it does not depend on file
    order at all.
    """
    offensive, special, other = [], [], []
    for r in rows or ():
        kind = classify_group(r.get('pos_abb'))
        if kind == 'OFFENSIVE':
            offensive.append(r)
        elif kind == 'SPECIAL_TEAMS':
            special.append(r)
        else:
            other.append(r)

    def _rank(r):
        try:
            return int(r.get('pos_rank'))
        except (TypeError, ValueError):
            return 10 ** 6

    def _pick(cands):
        """Newest capture, then the strongest listing, then the group name.

        Fully ordered on every field, so two runs over the same capture pick
        the same row no matter what order it arrives in. The `dt` tie that
        caused the defect is broken by rank rather than by position in the
        file.
        """
        if not cands:
            return None
        return sorted(cands, key=lambda r: (_neg(r.get('dt') or ''),
                                            _rank(r),
                                            (r.get('pos_abb') or '')))[0]

    # A listing in the player's own room beats a listing in another one: an
    # OL listed LG2 and RG2 stays rankless because neither is a modelled
    # room, while an RB listed RB1 and KR2 keeps RB1.
    want = MODEL_ROOM.get((model_position or '').strip().upper())
    same_room = [r for r in offensive
                 if OFFENSIVE_DEPTH_GROUPS.get(
                     (r.get('pos_abb') or '').strip().upper()) == want]

    return {'offensive_row': _pick(same_room or offensive),
            'special_teams_row': _pick(special),
            'n_rows': len(rows or ()), 'n_offensive': len(offensive),
            'n_special_teams': len(special), 'n_unrecognised': len(other),
            'listings': sorted(
                f'{(r.get("pos_abb") or "?").upper()}{r.get("pos_rank")}'
                for r in (rows or ())),
            'spec_version': SPEC_VERSION}


def guard_rank_map(rank_map: Dict[str, Tuple[str, int]],
                   model_position: Dict[str, str]) -> Dict[str, object]:
    """Filter a {player: (depth_group, rank)} map to same-room ranks only.

    This is the shape production builds at `run_forecast` before calling
    `assign_tiers`, where `dr[k] = v[1]` currently keeps the rank and throws
    the group away. Returns the safe map plus every rank it refused, by name,
    so the refusals are evidence rather than a silent narrowing.
    """
    kept, refused, st = {}, [], {}
    for pid, gr in (rank_map or {}).items():
        try:
            group, rank = gr[0], gr[1]
        except (TypeError, IndexError, KeyError):
            refused.append({'player_id': pid, 'why': 'MALFORMED_RANK_ENTRY'})
            continue
        r, why = offensive_depth_rank(model_position.get(pid), group, rank)
        if r is not None:
            kept[pid] = r
        else:
            refused.append({'player_id': pid, 'depth_group': group,
                            'rank': rank,
                            'model_position': model_position.get(pid),
                            'why': why})
        s = special_teams_role(group, rank)
        if s:
            st[pid] = s
    return {'rank': kept, 'refused': refused, 'special_teams_role': st,
            'spec_version': SPEC_VERSION,
            'n_in': len(rank_map or {}), 'n_kept': len(kept),
            'n_refused': len(refused)}
