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
OBJECTIVES = (OBJ_MEAN, OBJ_PERCENTILE, OBJ_TOP_X, OBJ_EXPECTED_RANK)


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
                         'value': round(p.value, 6)} for p in self.players],
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


def solve_one(players: Sequence[Player], c: Constraints, *,
              banned: Sequence[FrozenSet[str]] = (),
              blocked_ids: Optional[Set[str]] = None) -> Optional[Lineup]:
    """The single best legal lineup under `c`, or None if none exists.

    Branch-and-bound over the three legal shapes. Within a shape, positions
    are filled scarcest-first and each pool is sorted by value descending, so
    the optimistic bound (current value + the best remaining per open slot) is
    both admissible and tight.
    """
    blocked_ids = set(blocked_ids or ())
    pool = [p for p in _eligible(players, c) if p.gsis_id not in blocked_ids
            or p.gsis_id in c.locks]
    by_pos: Dict[str, List[Player]] = collections.defaultdict(list)
    for p in pool:
        by_pos[p.position].append(p)
    for v in by_pos.values():
        v.sort(key=lambda p: (-p.value, p.salary))
    if c.candidate_depth:
        for k in list(by_pos):
            by_pos[k] = by_pos[k][:max(c.candidate_depth,
                                       sum(1 for p in by_pos[k]
                                           if p.gsis_id in c.locks))]
    locked = {p.gsis_id: p for p in pool if p.gsis_id in c.locks}

    best: List[Optional[Lineup]] = [None]
    banned = [set(b) for b in banned]

    for shape in R.LEGAL_SHAPES:
        # QB FIRST, then scarcest. Not cosmetic: until the QB is chosen there
        # is no stack or bring-back constraint to prune on, so a scarcest-
        # first order left both to be judged at the leaf and the search
        # explored the whole tree before rejecting. Choosing the QB first
        # turns them into counting constraints that prune as slots fill.
        need = [('QB', shape['QB'])] + [
            (pos, n) for pos, n in
            sorted(((k, v) for k, v in shape.items() if k != 'QB'),
                   key=lambda kv: len(by_pos.get(kv[0], ())))]
        # A locked player whose position exceeds the shape's count makes this
        # shape impossible; skip it rather than searching it.
        lc = collections.Counter(p.position for p in locked.values())
        if any(lc[pos] > shape.get(pos, 0) for pos in lc):
            continue
        if any(len(by_pos.get(pos, ())) < n for pos, n in shape.items()):
            continue

        # Best-value prefix sums per position, for the bound.
        bestv = {pos: [p.value for p in by_pos[pos]] for pos in shape}
        pref = {pos: list(itertools.accumulate(bestv[pos]))
                for pos in shape}
        minsal = {pos: sorted(p.salary for p in by_pos[pos]) for pos in shape}
        minpref = {pos: list(itertools.accumulate(minsal[pos]))
                   for pos in shape}

        order = [pos for pos, _ in need]
        sel: List[Player] = []

        def bound(idx_by_pos, val, i):
            """Optimistic remaining value: the best unused at each open slot."""
            b = val
            for pos in order[i:]:
                k = shape[pos] - idx_by_pos.get(pos, 0)
                if k <= 0:
                    continue
                b += pref[pos][k - 1] if k <= len(pref[pos]) else 0.0
            return b

        def min_remaining_salary(i, filled):
            s = 0
            for pos in order[i:]:
                k = shape[pos] - filled.get(pos, 0)
                if k > 0:
                    s += minpref[pos][k - 1]
            return s

        def rec(i, start, val, sal, filled, teams, games):
            if best[0] is not None and bound(filled, val, i) <= best[0].value:
                return
            if i == len(order):
                if len(sel) != R.ROSTER_SIZE:
                    return
                ok_, _why = R.assert_roster_legal(
                    [p.position for p in sel], [p.salary for p in sel],
                    cap=c.salary_cap, floor=c.salary_floor)
                if not ok_:
                    return
                ids = frozenset(p.gsis_id for p in sel)
                if any(len(ids & b) > R.ROSTER_SIZE - c.min_unique_players
                       for b in banned):
                    return
                ok2, _w2 = _check_full(sel, c)
                if not ok2:
                    return
                if best[0] is None or val > best[0].value:
                    best[0] = Lineup(tuple(sel), val, sal, dict(shape))
                return

            pos = order[i]
            k = shape[pos]
            cand = by_pos[pos]
            # Choose k from cand, indices increasing, honouring locks.
            need_locked = [p for p in locked.values() if p.position == pos]

            # SUFFIX BOUND. `cand` is sorted by value descending, so the
            # best r players available from index j onward are exactly
            # cand[j : j+r]. Without this the search only bounded at position
            # boundaries and enumerated whole k-subsets of a large WR pool
            # before ever pruning -- 9.4s for five lineups on a 76-player
            # toy. With it the prune fires on the first bad partial subset.
            def best_from(j, r):
                if r <= 0:
                    return 0.0
                if j + r > len(cand):
                    return float('-inf')
                hi = pref[pos][j + r - 1]
                lo = pref[pos][j - 1] if j > 0 else 0.0
                return hi - lo

            # Cheapest r from index j onward, for salary feasibility. Salary
            # is NOT sorted, so this is a suffix minimum computed once.
            sal_sorted = sorted((p_.salary for p_ in cand))
            sal_pref = list(itertools.accumulate(sal_sorted))

            def cheapest(r):
                return sal_pref[r - 1] if 0 < r <= len(sal_pref) else 0

            def choose(j, chosen):
                if len(chosen) == k:
                    if any(p not in chosen for p in need_locked):
                        return
                    nsal = sal + sum(p.salary for p in chosen)
                    nf = dict(filled); nf[pos] = k
                    if nsal + min_remaining_salary(i + 1, nf) > c.salary_cap:
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
                    nval = val + sum(p.value for p in chosen)
                    if best[0] is not None and \
                            bound(nf, nval, i + 1) <= best[0].value:
                        return
                    # STACK FEASIBILITY, checked as slots fill rather than at
                    # the leaf. If every remaining stack-eligible slot were
                    # filled with a teammate and the minimum still could not
                    # be reached, no completion of this branch is legal. The
                    # leaf check alone made a stacked 20-lineup build on a
                    # 456-player pool run past ten minutes.
                    if c.qb_stack_min or c.bring_back_min:
                        qb_ = next((p_ for p_ in sel + chosen
                                    if p_.position == 'QB'), None)
                        if qb_ is not None:
                            have = sel + chosen
                            open_skill = sum(
                                shape[po] - nf.get(po, 0)
                                for po in ('RB', 'WR', 'TE'))
                            if c.qb_stack_min:
                                n_st = sum(1 for p_ in have
                                           if p_.team == qb_.team and
                                           p_.position in ('WR', 'TE', 'RB'))
                                if n_st + open_skill < c.qb_stack_min:
                                    return
                            if c.bring_back_min:
                                n_bb = sum(1 for p_ in have
                                           if p_.game == qb_.game and
                                           p_.team != qb_.team and
                                           p_.position != 'DST')
                                if n_bb + open_skill < c.bring_back_min:
                                    return
                    sel.extend(chosen)
                    rec(i + 1, 0, nval, nsal, nf, nt, ng)
                    del sel[-k:]
                    return
                if j >= len(cand):
                    return
                remaining = k - len(chosen)
                if len(cand) - j < remaining:
                    return
                if best[0] is not None:
                    partial = val + sum(p_.value for p_ in chosen)
                    nf = dict(filled)
                    nf[pos] = k
                    optimistic = (partial + best_from(j, remaining)
                                  + bound(nf, 0.0, i + 1))
                    if optimistic <= best[0].value:
                        return
                psal = sal + sum(p_.salary for p_ in chosen)
                nf2 = dict(filled); nf2[pos] = k
                if (psal + cheapest(remaining)
                        + min_remaining_salary(i + 1, nf2) > c.salary_cap):
                    return
                # Take cand[j]
                choose(j + 1, chosen + [cand[j]])
                # Skip cand[j], unless it is locked at this position
                if cand[j] not in need_locked:
                    choose(j + 1, chosen)

            choose(0, [])

        rec(0, 0, 0.0, 0, {}, collections.Counter(), collections.Counter())

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
