"""DraftKings NFL Classic roster rules, stated once.

These are CONTEST RULES, not model constants. They come from DraftKings and
nothing in this repository may tune them. They are separated from the
optimizer so that a rule change is a one-line edit in a file that contains no
optimisation logic, and so a reader can check them against the contest page
without reading a solver.

THE FLEX IS WHY THE SHAPE ENUMERATION EXISTS

A Classic roster is QB1 / RB2 / WR3 / TE1 / FLEX1 / DST1 = 9 players. The FLEX
takes an RB, WR or TE, so the roster is exactly one of three position
multisets. Enumerating them is not an approximation -- it is the complete set,
and having it explicit means the optimizer never has to reason about "a flex"
as a special slot.
"""
from __future__ import annotations

from typing import Dict, Tuple

SPEC_VERSION = 'dk-nfl-classic-rules-1'

SALARY_CAP = 50_000
ROSTER_SIZE = 9

#: Fixed slots, before the FLEX.
BASE = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'DST': 1}
FLEX_ELIGIBLE = ('RB', 'WR', 'TE')

#: The complete set of position multisets a legal roster can take. Derived
#: from BASE + one FLEX, not hand-written, so it cannot drift from the rules
#: above.
SHAPES: Tuple[Dict[str, int], ...] = tuple(
    {**BASE, flex: BASE[flex] + 1} for flex in FLEX_ELIGIBLE)

#: DK salaries are whole hundreds. Used only to make the search's salary
#: arithmetic exact; nothing rounds to it.
SALARY_STEP = 100

POSITIONS = ('QB', 'RB', 'WR', 'TE', 'DST')


#: The shapes as plain dicts, built once. Comparing against these is how a
#: roster's legality is decided, everywhere.
LEGAL_SHAPES = tuple(dict(s) for s in SHAPES)


def shape_is_legal(counts: Dict[str, int]) -> bool:
    """Does this position multiset match one of the three legal shapes?"""
    return any(counts == s for s in LEGAL_SHAPES)


def assert_roster_legal(positions, salaries, *, cap: int = SALARY_CAP,
                        floor: int = 0) -> Tuple[bool, str]:
    """(legal, why). The single place a roster is judged legal.

    Returns a REASON on failure rather than a bare False, because "illegal"
    without a reason is what makes an optimizer bug take an afternoon.
    """
    if len(positions) != ROSTER_SIZE:
        return False, (f'roster has {len(positions)} players, not '
                       f'{ROSTER_SIZE}')
    counts: Dict[str, int] = {}
    for p in positions:
        counts[p] = counts.get(p, 0) + 1
    if not shape_is_legal(counts):
        return False, (f'position counts {counts} are not one of the '
                       f'{len(LEGAL_SHAPES)} legal shapes {list(LEGAL_SHAPES)}')
    total = sum(salaries)
    if total > cap:
        return False, f'salary {total} exceeds the cap {cap}'
    if floor and total < floor:
        return False, f'salary {total} is below the declared floor {floor}'
    return True, 'legal'
