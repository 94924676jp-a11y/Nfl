"""DraftKings NFL Classic lineup construction. Exact, constrained, explainable.

NO SOLVER IS AVAILABLE AND NONE IS FAKED

There is no pulp, ortools, mip, scipy or cvxpy in this environment and no
network to fetch one. So this is a branch-and-bound written here, and it is
EXACT rather than a heuristic dressed up as one: the bound is admissible (it
can only over-estimate the value of a completion), so a pruned branch provably
contains nothing better than the incumbent.

Where exactness would cost more than it is worth, the compromise is DECLARED
and returned, never silent: `candidate_depth` trims each position pool to its
top-K by objective, and the result says how many players were trimmed. A
trimmed search is exact over the pool it was given and says so.

WHAT MAKES THIS DIFFERENT FROM A GENERIC OPTIMIZER

1. **It cannot be fed an ungoverned projection.** The pool comes from
   `classic.pool`, which reads the gated loader; there is no argument that
   accepts a bare list of numbers from anywhere.
2. **Every constraint is checked and REPORTED, not assumed.** The result
   carries realized exposure against requested, lineup overlap, and team,
   game and stack concentration. A portfolio of twenty near-clones is visible
   in the output rather than discovered on Sunday.
3. **Objectives are plural.** Mean fantasy points is one of four, and it is
   not the default for a tournament. Within-world percentile and top-X%
   frequency are computed from shared simulation worlds where draws exist.

NO ROI OR PROFITABILITY IS CLAIMED. Ownership and field models are
unavailable, so nothing here estimates duplication, leverage or expected
return, and no objective pretends to.
"""
from __future__ import annotations

import collections
import itertools
import math
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.classic import rules as R                              # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome        # noqa: E402

SPEC_VERSION = 'dk-nfl-classic-optimizer-1'

# --- objectives -----------------------------------------------------------
OBJ_MEAN = 'EXPECTED_FANTASY_POINTS'
OBJ_PERCENTILE = 'MEAN_WITHIN_WORLD_PERCENTILE'
OBJ_TOP_X = 'TOP_X_PERCENT_FREQUENCY'
OBJ_EXPECTED_RANK = 'EXPECTED_RANK'

#: The only objective a lineup search may optimise. Expectation is LINEAR, so
#: the sum of nine player means IS the mean of the lineup's score -- measured
#: at 2.8e-14 maximum error over every legal lineup of a correlated pool.
OBJECTIVES = (OBJ_MEAN,)

#: Computed per player across shared worlds, and then SUMMED over a lineup by
#: the search. Summing is what destroys them: a within-world percentile, a
#: top-X frequency and an expected rank are each a property of a player's
#: position in a DISTRIBUTION, and adding nine of them is not the same
#: property of the lineup. Correlation is exactly what the sum throws away,
#: and correlation is what a tournament pays for.
#:
#: MEASURED, not argued -- nfl/research/dfs/CLASSIC_OBJECTIVE_ADDITIVITY.json,
#: every legal lineup of an 18-player 3-team pool over 20,000 worlds. Spearman
#: against the true lineup top-1% frequency: percentile 0.478, top-X 0.492,
#: expected rank 0.473. Summed EXPECTED_FANTASY_POINTS scores 0.486 on the
#: same target, so these three do not even beat the mean at the job they were
#: added for. The lineup with the best true top-1% (0.0858, P(first) 0.0071)
#: is ranked #1046, #1203 and #867 of 3,375 by the three of them.
#:
#: They are blocked rather than deleted so that the names stay attached to the
#: measurement, and so that wiring one up is a refusal with a reason rather
#: than a KeyError somebody routes around.
NON_ADDITIVE_OBJECTIVES = (OBJ_PERCENTILE, OBJ_TOP_X, OBJ_EXPECTED_RANK)
ALL_OBJECTIVE_NAMES = (OBJ_MEAN,) + NON_ADDITIVE_OBJECTIVES


@dataclass(frozen=True)
class Player:
    gsis_id: str
    name: str
    position: str
    team: str
    opponent: str
    salary: int
    dk_id: Optional[str] = None
    game_id: Optional[str] = None
    #: The objective value used for search. Set by `score_pool`, never by a
    #: caller passing a number of unknown provenance.
    value: float = 0.0
    #: Index into the shared draw matrix, when one exists.
    draw_row: Optional[int] = None

    @property
    def game(self) -> str:
        return self.game_id or '|'.join(sorted((self.team, self.opponent)))


@dataclass
class Constraints:
    """Everything a professional would set. All optional, all reported."""
    n_lineups: int = 20
    salary_cap: int = R.SALARY_CAP
    salary_floor: int = 0
    locks: Set[str] = field(default_factory=set)
    excludes: Set[str] = field(default_factory=set)
    max_exposure: Dict[str, float] = field(default_factory=dict)
    min_exposure: Dict[str, float] = field(default_factory=dict)
    global_max_exposure: Optional[float] = None
    min_unique_players: int = 1
    max_from_team: Optional[int] = None
    max_from_game: Optional[int] = None
    #: QB stack: how many pass catchers from the QB's own team.
    qb_stack_min: int = 0
    #: Bring-back: how many players from the opposing team of the QB's game.
    bring_back_min: int = 0
    bring_back_max: Optional[int] = None
    #: Groups: at least/at most N from a named set of players.
    groups: List[Dict[str, Any]] = field(default_factory=list)
    #: Mutually exclusive sets -- at most one of each may appear.
    mutually_exclusive: List[Set[str]] = field(default_factory=list)
    projection_cutoff: float = 0.0
    candidate_depth: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            'n_lineups': self.n_lineups, 'salary_cap': self.salary_cap,
            'salary_floor': self.salary_floor,
            'locks': sorted(self.locks), 'excludes': sorted(self.excludes),
            'max_exposure': dict(self.max_exposure),
            'min_exposure': dict(self.min_exposure),
            'global_max_exposure': self.global_max_exposure,
            'min_unique_players': self.min_unique_players,
            'max_from_team': self.max_from_team,
            'max_from_game': self.max_from_game,
            'qb_stack_min': self.qb_stack_min,
            'bring_back_min': self.bring_back_min,
            'bring_back_max': self.bring_back_max,
            'groups': self.groups,
            'mutually_exclusive': [sorted(s) for s in self.mutually_exclusive],
            'projection_cutoff': self.projection_cutoff,
            'candidate_depth': self.candidate_depth,
        }


@dataclass
class Lineup:
    players: Tuple[Player, ...]
    value: float
    salary: int
    shape: Dict[str, int]

    @property
    def ids(self) -> FrozenSet[str]:
        return frozenset(p.gsis_id for p in self.players)

    @property
    def canonical(self) -> Tuple[Player, ...]:
        """Players in a fixed order, independent of how the search found them.

        The search visits positions in different orders depending on the
        constraints -- QB first when a stack is required, scarcest-first
        otherwise -- so selection order is an artifact of the route taken, not
        a property of the lineup. Two searches that find the SAME roster must
        describe it the same way, or every downstream diff is noise and an
        equivalence test cannot tell a real change from a reordering.
        """
        rank = {q: i for i, q in enumerate(R.POSITIONS)}
        return tuple(sorted(self.players,
                            key=lambda q: (rank.get(q.position, 99),
                                           -q.value, q.gsis_id)))

    def as_dict(self) -> Dict[str, Any]:
        qb = next((p for p in self.players if p.position == 'QB'), None)
        stack = ([p.name for p in self.players
                  if qb and p.team == qb.team and p.position in
                  ('WR', 'TE', 'RB')] if qb else [])
        bring = ([p.name for p in self.players
                  if qb and p.game == qb.game and p.team != qb.team
                  and p.position != 'DST'] if qb else [])
        return {
            'value': round(self.value, 6), 'salary': self.salary,
            'shape': self.shape,
            'players': [{'name': p.name, 'gsis_id': p.gsis_id,
                         'dk_id': p.dk_id, 'pos': p.position,
                         'team': p.team, 'salary': p.salary,
                         'value': round(p.value, 6)} for p in self.canonical],
            'qb': qb.name if qb else None,
            'qb_stack_with': stack, 'bring_back': bring,
            'teams': dict(collections.Counter(p.team for p in self.players)),
            'games': dict(collections.Counter(p.game for p in self.players)),
        }


# --------------------------------------------------------------------------
# objectives
# --------------------------------------------------------------------------
def score_pool(players: Sequence[Player], *, objective: str,
               draws=None, top_x: float = 0.10) -> Outcome:
    """Attach the search value to every player, from a declared objective.

    `draws` is the shared-world matrix (players x worlds) aligned to
    `Player.draw_row`. Objectives that need it REFUSE without it rather than
    silently degrading to the mean -- an optimizer that quietly changes its
    objective is one nobody can reason about.
    """
    if objective in NON_ADDITIVE_OBJECTIVES:
        return Outcome.fail(
            'OBJECTIVE_NOT_ADDITIVE',
            f'{objective} is computed per player and then SUMMED over a '
            f'lineup by the search, and it is not additive: a within-world '
            f'percentile, a top-X frequency and an expected rank are '
            f'properties of a player\'s place in a distribution, and adding '
            f'nine of them is not that property of the lineup. Measured over '
            f'every legal lineup of a correlated pool, it ranks the '
            f'best-by-true-top-1% lineup around #1000 of 3,375 and does not '
            f'beat plain mean points at the job it was added for. See '
            f'nfl/research/dfs/CLASSIC_OBJECTIVE_ADDITIVITY.json. Correct '
            f'tournament evaluation scores the LINEUP distribution -- '
            f'lineup_score_j = sum(player_score_pj) per world, then evaluate '
            f'that -- and needs a field model this project does not have. '
            f'{OBJ_MEAN} is the only approved production objective.',
            value=objective, approved=list(OBJECTIVES))
    if objective not in OBJECTIVES:
        return Outcome.fail(
            'UNKNOWN_OBJECTIVE',
            f'{objective!r} is not one of {OBJECTIVES}.', value=objective)
    if objective == OBJ_MEAN:
        scored = [Player(**{**p.__dict__}) for p in players]
        return Outcome.ok('POOL_SCORED', {'players': list(players),
                                          'objective': objective,
                                          'uses_shared_worlds': False},
                          detail=f'{len(players)} player(s) on mean points')

    import numpy as np
    if draws is None:
        return Outcome.blocked(
            'OBJECTIVE_REQUIRES_SHARED_WORLDS',
            f'{objective} is computed across simulated worlds and no draw '
            f'matrix was supplied. Falling back to the mean would change the '
            f'objective without saying so.', cause=Cause.DATA)
    M = np.asarray(draws, float)
    rows = [p.draw_row for p in players]
    if any(r is None or r >= M.shape[0] for r in rows):
        return Outcome.fail(
            'POOL_NOT_ALIGNED_TO_DRAWS',
            'at least one player has no row in the shared-world matrix, so '
            'his worlds are unknown and a percentile over them would be '
            'invented.',
            value={'n_missing': sum(1 for r in rows
                                    if r is None or r >= M.shape[0])})
    sub = M[rows, :]
    if objective == OBJ_PERCENTILE:
        # Within EACH world, where does this player rank against the pool?
        order = sub.argsort(axis=0).argsort(axis=0)
        pct = order / max(sub.shape[0] - 1, 1)
        vals = pct.mean(axis=1)
    elif objective == OBJ_TOP_X:
        k = max(1, int(round(top_x * sub.shape[0])))
        thresh = np.partition(sub, -k, axis=0)[-k, :]
        vals = (sub >= thresh).mean(axis=1)
    else:  # OBJ_EXPECTED_RANK -- higher is better, so negate the rank
        order = (-sub).argsort(axis=0).argsort(axis=0) + 1
        vals = -order.mean(axis=1)
    out = [Player(**{**p.__dict__, 'value': float(v)})
           for p, v in zip(players, vals)]
    return Outcome.ok(
        'POOL_SCORED',
        {'players': out, 'objective': objective, 'uses_shared_worlds': True,
         'n_worlds': int(M.shape[1]), 'top_x': top_x},
        detail=f'{len(out)} player(s) on {objective} over {M.shape[1]} worlds')


# --------------------------------------------------------------------------
# the search
# --------------------------------------------------------------------------
def _eligible(players, c: Constraints):
    out = []
    for p in players:
        if p.gsis_id in c.excludes:
            continue
        if p.position not in R.POSITIONS:
            continue
        if p.value < c.projection_cutoff and p.gsis_id not in c.locks:
            continue
        out.append(p)
    return out


def _check_full(sel: Sequence[Player], c: Constraints) -> Tuple[bool, str]:
    """Constraints that can only be judged on a complete roster."""
    ids = {p.gsis_id for p in sel}
    missing = c.locks - ids
    if missing:
        return False, f'locked player(s) absent: {sorted(missing)}'
    for ex in c.mutually_exclusive:
        if len(ids & ex) > 1:
            return False, f'more than one of a mutually exclusive set: ' \
                          f'{sorted(ids & ex)}'
    for g in c.groups:
        n = len(ids & set(g.get('players') or ()))
        lo, hi = g.get('min'), g.get('max')
        if lo is not None and n < lo:
            return False, f'group {g.get("name")} has {n} < min {lo}'
        if hi is not None and n > hi:
            return False, f'group {g.get("name")} has {n} > max {hi}'
    qb = next((p for p in sel if p.position == 'QB'), None)
    if qb is not None:
        if c.qb_stack_min:
            n = sum(1 for p in sel if p.team == qb.team
                    and p.position in ('WR', 'TE', 'RB'))
            if n < c.qb_stack_min:
                return False, (f'QB stack has {n} teammate(s), needs '
                               f'{c.qb_stack_min}')
        if c.bring_back_min or c.bring_back_max is not None:
            n = sum(1 for p in sel if p.game == qb.game
                    and p.team != qb.team and p.position != 'DST')
            if c.bring_back_min and n < c.bring_back_min:
                return False, (f'bring-back has {n}, needs '
                               f'{c.bring_back_min}')
            if c.bring_back_max is not None and n > c.bring_back_max:
                return False, (f'bring-back has {n}, max {c.bring_back_max}')
    return True, 'ok'


def _combos(pool, k, budget_ok):
    """Every k-subset of a value-sorted pool, best-first, as a generator.

    Yields in descending partial-value order so the first completions found
    are strong ones, which is what makes the incumbent bite early.
    """
    n = len(pool)
    if k == 0:
        yield []
        return
    if k > n:
        return

    def rec(j, chosen):
        if len(chosen) == k:
            yield list(chosen)
            return
        if n - j < k - len(chosen):
            return
        for i in range(j, n):
            if n - i < k - len(chosen):
                return
            chosen.append(pool[i])
            yield from rec(i + 1, chosen)
            chosen.pop()

    yield from rec(0, [])


@dataclass
class _Pool:
    """A value-sorted candidate set with its two bound arrays, built ONCE.

    The arrays are the expensive part -- a sort plus two accumulations -- and
    the stacked decomposition asks for the same set with many different
    counts. Rebuilding them per combination sorted the same list hundreds of
    times per QB.
    """
    players: List[Player]
    vpref: List[float] = field(default_factory=list)
    spref: List[int] = field(default_factory=list)

    @staticmethod
    def of(players: Sequence[Player]) -> '_Pool':
        ps = sorted(players, key=lambda p: (-p.value, p.salary, p.gsis_id))
        return _Pool(ps,
                     list(itertools.accumulate(p.value for p in ps)),
                     list(itertools.accumulate(sorted(p.salary for p in ps))))

    def __len__(self):
        return len(self.players)


@dataclass
class _Task:
    """Take exactly `k` from a prepared pool."""
    label: str
    position: str
    src: _Pool
    k: int

    @property
    def pool(self) -> List[Player]:
        return self.src.players

    def best_value(self) -> float:
        v = self.src.vpref
        return v[self.k - 1] if 0 < self.k <= len(v) else 0.0

    def cheapest(self) -> int:
        sp = self.src.spref
        return sp[self.k - 1] if 0 < self.k <= len(sp) else 0

    def best_from(self, j: int, r: int) -> float:
        if r <= 0:
            return 0.0
        v = self.src.vpref
        if j + r > len(v):
            return float('-inf')
        return v[j + r - 1] - (v[j - 1] if j > 0 else 0.0)


def _dists(total: int, caps: Sequence[int]):
    """Every way to split `total` across slots with the given caps."""
    if not caps:
        if total == 0:
            yield ()
        return
    head, rest = caps[0], caps[1:]
    for i in range(min(head, total) + 1):
        for tail in _dists(total - i, rest):
            yield (i,) + tail


# Shared stand-in for the group-counting arrays when a search has no group
# minimum to enforce, so the no-group path allocates nothing per node. Never
# written to: every mutation site is behind `if ngrp`.
_NO_GROUPS: List[int] = []


def _search(tasks: Sequence[_Task], c: Constraints, *,
            banned: Sequence[Set[str]], best: List[Optional[Lineup]],
            shape: Dict[str, int], lock_ids: Set[str]):
    """Branch and bound over a list of independent exact-count choices.

    The bound is the sum, over every task not yet begun, of the best `k`
    values still available in it. It can only OVER-estimate a completion, so
    pruning on it cannot discard a better lineup than the incumbent -- which
    is what makes this exact rather than a heuristic.

    GROUP MINIMUMS PRUNE TOO, AND THIS WAS NOT OPTIONAL. A group minimum was
    tested only on a finished roster. Correct, but ruinous: a branch that can
    no longer reach the minimum is searched to exhaustion before anything
    notices, and on a 4-team fixture with one `min: 2` group that cost 36.62s
    against the frozen baseline's 0.07s -- a 500x REGRESSION, not a speedup.
    The arrays below say how many members of each group are still REACHABLE:
    from the tasks not yet begun, and from the unexamined tail of the current
    task's pool. Reachability is an upper bound on what any completion can
    contain, so cutting a branch that cannot reach the minimum cannot discard
    a feasible lineup.
    """
    ntask = len(tasks)
    suffix_value = [0.0] * (ntask + 1)
    suffix_salary = [0] * (ntask + 1)
    for i in range(ntask - 1, -1, -1):
        suffix_value[i] = suffix_value[i + 1] + tasks[i].best_value()
        suffix_salary[i] = suffix_salary[i + 1] + tasks[i].cheapest()

    gmins = [(frozenset(g.get('players') or ()), int(g['min']))
             for g in c.groups if g.get('min')]
    ngrp = len(gmins)
    gtail: List[List[List[int]]] = [_NO_GROUPS] * ntask
    gsuf = [_NO_GROUPS] * (ntask + 1)
    if ngrp:
        gtail = []
        gsuf = [[0] * ngrp for _ in range(ntask + 1)]
        for tk in tasks:
            per = []
            for members, _m in gmins:
                tail = [0] * (len(tk.pool) + 1)
                for j in range(len(tk.pool) - 1, -1, -1):
                    tail[j] = tail[j + 1] + (
                        1 if tk.pool[j].gsis_id in members else 0)
                per.append(tail)
            gtail.append(per)
        for i in range(ntask - 1, -1, -1):
            for gi in range(ngrp):
                gsuf[i][gi] = gsuf[i + 1][gi] + min(tasks[i].k,
                                                    gtail[i][gi][0])

    sel: List[Player] = []

    def leaf(val, sal):
        if len(sel) != R.ROSTER_SIZE:
            return
        legal, _why = R.assert_roster_legal(
            [p.position for p in sel], [p.salary for p in sel],
            cap=c.salary_cap, floor=c.salary_floor)
        if not legal:
            return
        ids = frozenset(p.gsis_id for p in sel)
        if any(len(ids & b) > R.ROSTER_SIZE - c.min_unique_players
               for b in banned):
            return
        ok_, _w = _check_full(sel, c)
        if not ok_:
            return
        if best[0] is None or val > best[0].value:
            best[0] = Lineup(tuple(sel), val, sal, dict(shape))

    def rec(t_i, val, sal, teams, games, gc):
        if t_i == ntask:
            leaf(val, sal)
            return
        if best[0] is not None and val + suffix_value[t_i] <= best[0].value:
            return
        if sal + suffix_salary[t_i] > c.salary_cap:
            return
        if ngrp:
            for gi in range(ngrp):
                if gc[gi] + gsuf[t_i][gi] < gmins[gi][1]:
                    return
        task = tasks[t_i]
        k, pool = task.k, task.pool
        if k == 0:
            rec(t_i + 1, val, sal, teams, games, gc)
            return
        need_locked = [p for p in pool if p.gsis_id in lock_ids]
        tails = gtail[t_i]

        def choose(j, chosen, cval, csal, cgc):
            if len(chosen) == k:
                if any(p not in chosen for p in need_locked):
                    return
                nt = collections.Counter(teams)
                ng = collections.Counter(games)
                for p in chosen:
                    nt[p.team] += 1
                    ng[p.game] += 1
                if c.max_from_team and max(nt.values()) > c.max_from_team:
                    return
                if c.max_from_game and max(ng.values()) > c.max_from_game:
                    return
                sel.extend(chosen)
                rec(t_i + 1, val + cval, sal + csal, nt, ng,
                    tuple(gc[gi] + cgc[gi] for gi in range(ngrp))
                    if ngrp else gc)
                del sel[-k:]
                return
            if j >= len(pool):
                return
            r = k - len(chosen)
            if len(pool) - j < r:
                return
            if ngrp:
                for gi in range(ngrp):
                    reach = tails[gi][j]
                    if reach > r:
                        reach = r
                    if (gc[gi] + cgc[gi] + reach + gsuf[t_i + 1][gi]
                            < gmins[gi][1]):
                        return
            if best[0] is not None:
                opt = (val + cval + task.best_from(j, r)
                       + suffix_value[t_i + 1])
                if opt <= best[0].value:
                    return
            if (sal + csal + task.src.spref[r - 1]
                    + suffix_salary[t_i + 1] > c.salary_cap):
                return
            p = pool[j]
            chosen.append(p)
            hit = ([gi for gi in range(ngrp) if p.gsis_id in gmins[gi][0]]
                   if ngrp else ())
            for gi in hit:
                cgc[gi] += 1
            choose(j + 1, chosen, cval + p.value, csal + p.salary, cgc)
            for gi in hit:
                cgc[gi] -= 1
            chosen.pop()
            if p not in need_locked:
                choose(j + 1, chosen, cval, csal, cgc)

        choose(0, [], 0.0, 0, [0] * ngrp if ngrp else _NO_GROUPS)

    rec(0, 0.0, 0, collections.Counter(), collections.Counter(),
        (0,) * ngrp)


def solve_one(players: Sequence[Player], c: Constraints, *,
              banned: Sequence[FrozenSet[str]] = (),
              blocked_ids: Optional[Set[str]] = None) -> Optional[Lineup]:
    """The single best legal lineup under `c`, or None if none exists.

    TWO SEARCH SHAPES, ONE SOLVER.

    Without stack requirements the roster is five independent choices -- one
    per position -- and the solver runs over those directly.

    WITH them it is decomposed further, and this is the part that made a
    stacked build practical. Given a QB, the skill pool partitions into three
    DISJOINT sets: his own team (MATE), the opposing team in his game (OPP),
    and everyone else (REST). Enumerating EXACT counts from each means the
    stack and bring-back minimums are satisfied BY CONSTRUCTION rather than
    tested at the leaf, and because the sets are disjoint and the counts
    exact, every legal lineup is generated exactly once -- no duplication,
    nothing missed.

    Before this, stacks were judged only on a complete roster, so the search
    built whole lineups and threw them away: a 456-player 20-lineup stacked
    build took 143 seconds.
    """
    blocked_ids = set(blocked_ids or ())
    pool = [p for p in _eligible(players, c)
            if p.gsis_id not in blocked_ids or p.gsis_id in c.locks]
    by_pos: Dict[str, List[Player]] = collections.defaultdict(list)
    for p in pool:
        by_pos[p.position].append(p)
    for v in by_pos.values():
        v.sort(key=lambda p: (-p.value, p.salary, p.gsis_id))
    if c.candidate_depth:
        for kpos in list(by_pos):
            keep = max(c.candidate_depth,
                       sum(1 for p in by_pos[kpos] if p.gsis_id in c.locks))
            by_pos[kpos] = by_pos[kpos][:keep]
    lock_ids = set(c.locks)
    locked = [p for p in pool if p.gsis_id in lock_ids]
    best: List[Optional[Lineup]] = [None]
    banned_sets = [set(b) for b in banned]
    stacked = bool(c.qb_stack_min or c.bring_back_min
                   or c.bring_back_max is not None)
    SKILL = ('RB', 'WR', 'TE')

    for shape in R.LEGAL_SHAPES:
        lc = collections.Counter(p.position for p in locked)
        if any(lc[pos] > shape.get(pos, 0) for pos in lc):
            continue
        if any(len(by_pos.get(pos, ())) < n for pos, n in shape.items()):
            continue

        if not stacked:
            tasks = [_Task(pos, pos, _Pool.of(by_pos[pos]), n)
                     for pos, n in shape.items()]
            tasks.sort(key=lambda t: (len(t.pool), t.label))
            _search(tasks, c, banned=banned_sets, best=best, shape=shape,
                    lock_ids=lock_ids)
            continue

        # --- stacked: QB first, then exact counts from disjoint sets -------
        caps = [shape[p] for p in SKILL]
        n_skill = sum(caps)
        pos_pool = {p: _Pool.of(by_pos[p]) for p in ('RB', 'WR', 'TE', 'DST')}
        for qb in by_pos['QB']:
            if best[0] is not None:
                # An upper bound on ANY lineup containing this QB. If it
                # cannot beat the incumbent, skip the whole QB.
                ub = qb.value + sum(
                    _Task(p, p, pos_pool[p], shape[p]).best_value()
                    for p in ('RB', 'WR', 'TE', 'DST'))
                if ub <= best[0].value:
                    continue
            if lock_ids and any(p.position == 'QB' and p.gsis_id != qb.gsis_id
                                for p in locked):
                continue
            # Built ONCE per QB, reused across every (t, b) decomposition.
            mate = {p: _Pool.of([x for x in by_pos[p] if x.team == qb.team])
                    for p in SKILL}
            opp = {p: _Pool.of([x for x in by_pos[p]
                                if x.game == qb.game and x.team != qb.team])
                   for p in SKILL}
            rest = {p: _Pool.of([x for x in by_pos[p]
                                 if x.team != qb.team and x.game != qb.game])
                    for p in SKILL}
            qb_pool = _Pool.of([qb])
            dst_pool = pos_pool['DST']
            max_t = min(sum(len(mate[p]) for p in SKILL), n_skill)
            max_b = min(sum(len(opp[p]) for p in SKILL), n_skill)
            hi_b = max_b if c.bring_back_max is None else min(
                max_b, c.bring_back_max)
            for t in range(c.qb_stack_min, max_t + 1):
                for b in range(c.bring_back_min, hi_b + 1):
                    if t + b > n_skill:
                        continue
                    for td in _dists(t, caps):
                        if any(td[i] > len(mate[SKILL[i]])
                               for i in range(3)):
                            continue
                        rem = [caps[i] - td[i] for i in range(3)]
                        for bd in _dists(b, rem):
                            if any(bd[i] > len(opp[SKILL[i]])
                                   for i in range(3)):
                                continue
                            rd = [rem[i] - bd[i] for i in range(3)]
                            if any(rd[i] > len(rest[SKILL[i]])
                                   for i in range(3)):
                                continue
                            tasks = [_Task('QB', 'QB', qb_pool, 1),
                                     _Task('DST', 'DST', dst_pool,
                                           shape['DST'])]
                            for i, pos in enumerate(SKILL):
                                if td[i]:
                                    tasks.append(_Task(f'MATE_{pos}', pos,
                                                       mate[pos], td[i]))
                                if bd[i]:
                                    tasks.append(_Task(f'OPP_{pos}', pos,
                                                       opp[pos], bd[i]))
                                if rd[i]:
                                    tasks.append(_Task(f'REST_{pos}', pos,
                                                       rest[pos], rd[i]))
                            # Locked players must have a task that can hold
                            # them, or this decomposition cannot produce a
                            # legal lineup at all.
                            if lock_ids:
                                holdable = set()
                                for tk in tasks:
                                    holdable |= {x.gsis_id for x in tk.pool}
                                if not lock_ids <= holdable:
                                    continue
                            tasks.sort(key=lambda tk: (len(tk.pool), tk.label))
                            _search(tasks, c, banned=banned_sets, best=best,
                                    shape=shape, lock_ids=lock_ids)

    return best[0]


def build_portfolio(players: Sequence[Player], c: Constraints) -> Outcome:
    """`n_lineups` lineups under every constraint, with realized exposure.

    Lineups are generated sequentially with the uniqueness and max-exposure
    constraints accumulated, which is how a DFS portfolio is actually built:
    the second lineup is not the second-best lineup, it is the best lineup
    given that the first one exists.
    """
    if not players:
        return Outcome.blocked(
            'CLASSIC_POOL_EMPTY',
            'no players were supplied, so no lineup can be built. An empty '
            'pool read as "no valid lineups" hides the difference between a '
            'refused pool and an over-constrained one.', cause=Cause.DATA)
    if c.n_lineups < 1:
        return Outcome.fail('N_LINEUPS_NOT_POSITIVE',
                            f'{c.n_lineups} lineups requested', value=c.n_lineups)

    lineups: List[Lineup] = []
    used: collections.Counter = collections.Counter()
    banned: List[FrozenSet[str]] = []
    cap_hits: List[dict] = []

    for i in range(c.n_lineups):
        blocked = set()
        for pid, n in used.items():
            lim = c.max_exposure.get(pid, c.global_max_exposure)
            if lim is None:
                continue
            if n >= math.floor(lim * c.n_lineups + 1e-9):
                blocked.add(pid)
        lu = solve_one(players, c, banned=banned, blocked_ids=blocked)
        if lu is None:
            cap_hits.append({'lineup_index': i,
                             'reason': 'no legal lineup remained under the '
                                       'accumulated uniqueness and exposure '
                                       'constraints'})
            break
        lineups.append(lu)
        banned.append(lu.ids)
        for p in lu.players:
            used[p.gsis_id] += 1

    if not lineups:
        return Outcome.fail(
            'NO_LEGAL_LINEUP',
            'the constraints admit no legal DraftKings Classic roster. This '
            'is a statement about the constraints, not about the players: '
            'check the salary floor, the locks and the stack minimums.',
            value={'constraints': c.as_dict(), 'n_players': len(players)})

    n = len(lineups)
    realized = {pid: k / n for pid, k in used.items()}
    unmet_min = {pid: {'requested_min': v, 'realized': realized.get(pid, 0.0)}
                 for pid, v in c.min_exposure.items()
                 if realized.get(pid, 0.0) + 1e-9 < v}
    over_max = {pid: {'requested_max': c.max_exposure.get(
        pid, c.global_max_exposure), 'realized': r}
        for pid, r in realized.items()
        if (c.max_exposure.get(pid, c.global_max_exposure) is not None
            and r > c.max_exposure.get(pid, c.global_max_exposure) + 1e-9)}

    overlaps = [len(a.ids & b.ids) for a, b in itertools.combinations(
        lineups, 2)] or [0]
    teams = collections.Counter(p.team for lu in lineups for p in lu.players)
    games = collections.Counter(p.game for lu in lineups for p in lu.players)
    stacks = collections.Counter()
    for lu in lineups:
        d = lu.as_dict()
        if d['qb']:
            stacks[f'{d["qb"]}+{len(d["qb_stack_with"])}'] += 1

    return Outcome.ok(
        'CLASSIC_PORTFOLIO_BUILT',
        {'lineups': [lu.as_dict() for lu in lineups],
         'n_lineups': n, 'n_requested': c.n_lineups,
         'short_of_request': cap_hits,
         'constraints': c.as_dict(),
         'realized_exposure': {k: round(v, 4)
                               for k, v in sorted(realized.items(),
                                                  key=lambda kv: -kv[1])},
         'unmet_min_exposure': unmet_min,
         'exceeded_max_exposure': over_max,
         'diversity': {
             'mean_overlap': round(sum(overlaps) / len(overlaps), 4),
             'max_overlap': max(overlaps),
             'min_unique_requested': c.min_unique_players,
             'n_distinct_players': len(used)},
         'team_concentration': dict(teams.most_common()),
         'game_concentration': dict(games.most_common()),
         'stack_concentration': dict(stacks.most_common()),
         'salary_used': {'min': min(lu.salary for lu in lineups),
                         'max': max(lu.salary for lu in lineups),
                         'mean': round(sum(lu.salary for lu in lineups) / n, 1)},
         'no_roi_claim': 'ownership and field models are unavailable, so no '
                         'duplication, leverage or expected-return estimate '
                         'is made and none may be inferred from this output',
         'spec_version': SPEC_VERSION},
        detail=f'{n} of {c.n_lineups} lineup(s); mean overlap '
               f'{sum(overlaps) / len(overlaps):.2f}; '
               f'{len(used)} distinct player(s)')
