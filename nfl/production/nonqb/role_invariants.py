"""Ordering invariants on a room's opportunity, checked on any board.

THE DEFECT THIS EXISTS FOR. In the sealed DET @ BUF board the Buffalo RB1,
James Cook, carried `P(carries = 0) = 0.375` against his backup Ray Davis at
`0.292` -- the starter absent more often than the man behind him, with week-1
usage of 13 carries to 1 and no injury designation on either. Nothing in the
pipeline objected, the optimizer believed the numbers, and a 40-lineup
portfolio went out at 72.5% Ray Davis.

WHAT IS CHECKED, AND WHY IT IS NOT A FITTED THRESHOLD. Within a room -- one
team, one position -- a player listed ahead on the official depth chart may
not carry a HIGHER probability of zero opportunity than a player listed behind
him. That is an ordering constraint on the model's own output. It fits
nothing, tunes nothing, and is indifferent to what any of them actually did.

THE TOLERANCE IS DERIVED, NOT CHOSEN. Two probabilities estimated from the
same N Monte Carlo draws differ by sampling noise alone. The flag fires only
when the inversion exceeds `SE_MULTIPLE` standard errors of the difference,

    se = sqrt(p1(1 - p1)/n + p2(1 - p2)/n)

so a board with few draws raises fewer flags, correctly, and no constant is
invented to make the number come out.

WHAT IT DOES NOT DO. It does not repair an inversion, reallocate a share, or
say which of the two players is wrong -- only that the pair is inconsistent
with the depth chart the model was given. It does not read an outcome, a
sportsbook price or a projection. A player the caller names in `excused` (a
listed starter who is doubtful, say) is reported and not counted as a
violation, and the reason travels with him.
"""
from __future__ import annotations

import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome            # noqa: E402

SPEC_VERSION = 'nonqb-role-ordering-invariant-1'

#: How many Monte Carlo standard errors an inversion must exceed before it is
#: called one. Two, declared in advance: it is the conventional two-sigma
#: reading of a difference of proportions, not a level chosen after seeing
#: which pairs it flags.
SE_MULTIPLE = 2.0

CODE_INVERSION = 'ROLE_APPEARANCE_INVERSION'
CODE_OK = 'ROLE_ORDERING_CONSISTENT'
CODE_INPUT = 'ROLE_ORDERING_INPUT_INCOMPLETE'


def se_diff(p1: float, p2: float, n: int) -> float:
    """Monte Carlo SE of (p1 - p2) from n draws each."""
    if n <= 0:
        return float('inf')
    return math.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)


def check(p_zero, depth, *, n_draws, teams, names=None, excused=None,
          label='board') -> Outcome:
    """`p_zero`: id -> P(zero opportunity). `depth`: id -> (rank, position).

    `teams`: id -> club. REQUIRED, and a player missing from it is refused
    rather than pooled. A room is ONE CLUB and one position: the depth vintage
    ranks offence-wide within a club, so ranks from two clubs are two
    different scales and comparing across them produces confident nonsense --
    a first pass of this check ranked Buffalo's RB1 against Detroit's and
    called it an inversion.

    Both dicts are keyed by the same player id. A player in one and not the
    other is reported rather than skipped quietly -- a silently dropped
    starter is how an ordering check passes without checking him.
    """
    names = names or {}
    excused = dict(excused or {})
    missing_depth = sorted(set(p_zero) - set(depth))
    if not p_zero:
        return Outcome.fail(
            CODE_INPUT, f'{label}: no probabilities supplied. An empty check '
                        f'is not a passed check.', cause=Cause.DATA)
    no_team = sorted(pid for pid in p_zero
                     if pid in depth and not teams.get(pid))
    if no_team:
        return Outcome.fail(
            CODE_INPUT,
            f'{label}: {len(no_team)} player(s) carry a depth rank and no '
            f'club. Ranks are club-scoped; pooling them would compare two '
            f'different scales.',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            players_without_team=no_team)

    rooms = {}
    for pid, p in p_zero.items():
        d = depth.get(pid)
        if not d:
            continue
        rank, pos = d[0], d[1]
        if rank is None or pos is None:
            continue
        rooms.setdefault((teams[pid], pos), []).append(
            (int(rank), pid, float(p)))

    inversions, excused_rows, n_pairs = [], [], 0
    for (club, pos), rows in sorted(rooms.items()):
        rows.sort()
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                r1, id1, p1 = rows[i]
                r2, id2, p2 = rows[j]
                if r1 == r2:
                    continue
                n_pairs += 1
                gap = p1 - p2
                if gap <= 0:
                    continue
                se = se_diff(p1, p2, n_draws)
                if gap <= SE_MULTIPLE * se:
                    continue
                row = {'team': club, 'position': pos,
                       'ahead': names.get(id1, id1), 'ahead_id': id1,
                       'ahead_rank': r1, 'ahead_p_zero': p1,
                       'behind': names.get(id2, id2), 'behind_id': id2,
                       'behind_rank': r2, 'behind_p_zero': p2,
                       'excess': gap, 'se': se,
                       'se_multiples': (gap / se) if se else float('inf')}
                if id1 in excused:
                    row['excused_because'] = excused[id1]
                    excused_rows.append(row)
                else:
                    inversions.append(row)

    inversions.sort(key=lambda r: -r['excess'])
    ev = {'spec_version': SPEC_VERSION, 'label': label, 'n_draws': n_draws,
          'se_multiple': SE_MULTIPLE, 'n_rooms': len(rooms),
          'n_ordered_pairs': n_pairs, 'n_inversions': len(inversions),
          'n_excused': len(excused_rows), 'excused': excused_rows,
          'players_without_depth_rank': missing_depth,
          'this_module_does_not_repair': (
              'an inversion is reported, never corrected. Which of the two '
              'rows is wrong is a modelling question this check cannot '
              'answer and must not pretend to.')}
    if inversions:
        worst = inversions[0]
        return Outcome.fail(
            CODE_INVERSION,
            f'{label}: {len(inversions)} depth-ordering inversion(s) beyond '
            f'{SE_MULTIPLE} MC standard errors. Worst: {worst["ahead"]} '
            f'(rank {worst["ahead_rank"]}) carries P(zero) '
            f'{worst["ahead_p_zero"]:.4f} against {worst["behind"]} '
            f'(rank {worst["behind_rank"]}) at {worst["behind_p_zero"]:.4f}, '
            f'{worst["se_multiples"]:.1f} SE apart.',
            cause=Cause.DATA, inversions=inversions, **ev)
    return Outcome.ok(
        CODE_OK, value=[],
        detail=f'{label}: {n_pairs} ordered pair(s) across {len(rooms)} '
               f'room(s), no inversion beyond {SE_MULTIPLE} MC SE',
        **ev)
