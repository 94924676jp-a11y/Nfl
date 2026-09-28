#!/usr/bin/env python3.12
"""An EXACT DraftKings lineup optimiser, and it proves it rather than claiming it.

THE OWNER'S REQUIREMENT. Replace random and single-swap search with a proper mathematical solver;
benchmark against known optimal solutions; and never call a result optimal unless optimality is
proven. Allowed states are PROVEN_OPTIMAL, BEST_KNOWN, HEURISTIC.

WHY THIS IS SOLVABLE EXACTLY AND WHY NO SOLVER LIBRARY IS USED. A DK classic lineup is
QB x1, RB x2, WR x3, TE x1, FLEX x1 from (RB, WR, TE), DST x1 -- nine players under a 50,000 salary
cap. That is a multi-dimensional knapsack, which is NP-hard in general and trivial at this size once
it is decomposed properly:

  1 the FLEX collapses the problem into exactly THREE shapes: RB3/WR3/TE1, RB2/WR4/TE1, RB2/WR3/TE2.
    No other roster is legal, so solving all three and taking the best is exhaustive over shapes.
  2 within a shape the positions are INDEPENDENT except through the shared salary budget. So each
    position gets its own exact "best value using exactly k players costing exactly s" table, and the
    positions are combined by convolution over the salary axis.
  3 DK salaries are multiples of 100, so the salary axis has at most 501 buckets rather than 50,001.

The tables are exact and the convolution is exact, so the maximum is the true maximum over every
legal lineup. Nothing is sampled, nothing is greedy, and there is no random seed.

This environment is PEP 668 externally managed and refuses to install a solver, so no ortools, no
PuLP. That turns out to be a feature: the DP is 200 lines, has no version pin, and its optimality is
checkable by brute force, which is what verify.py does.

WHAT THIS DOES NOT SOLVE. A PORTFOLIO with overlap constraints between lineups is a different and
harder problem. k_best() enumerates exactly the top k DISTINCT lineups, which is exact. Anything
beyond that -- selecting a portfolio jointly under ownership and duplication -- is labelled and lives
elsewhere.
"""
from __future__ import annotations

import itertools
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'exact-optimiser-1'

PROVEN_OPTIMAL = 'PROVEN_OPTIMAL'
BEST_KNOWN = 'BEST_KNOWN'
HEURISTIC = 'HEURISTIC'

SALARY_CAP = 50000
SALARY_STEP = 100

#: The three legal shapes once the FLEX is resolved. Exhaustive: no other DK classic roster exists.
SHAPES = (
    {'QB': 1, 'RB': 3, 'WR': 3, 'TE': 1, 'DST': 1},
    {'QB': 1, 'RB': 2, 'WR': 4, 'TE': 1, 'DST': 1},
    {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 2, 'DST': 1},
)

NEG = float('-inf')


_TABLE_CACHE: dict = {}
_TABLE_CACHE_MAX = 240  # each entry holds (k+1) x (buckets+1) rosters; 4000 of them exhausted
                        # the container's memory and killed the process, so the bound is on
                        # ENTRIES and it is deliberately small. The cache only needs to span one
                        # enumeration step, where eight of nine position tables are unchanged.


def _position_table(items, kmax, nbuckets):
    """Exact-count 0/1 knapsack per position, memoised.

    The memo matters for the constrained search rather than for a single solve. Enumeration in value
    order re-solves with ONE extra banned player each step, so eight of the nine position tables are
    byte-identical to the previous step and were being rebuilt from scratch every time. Caching on
    the exact item list makes the constrained paths several times faster without changing a single
    answer -- the key IS the input, so a hit cannot return a table for a different problem.
    """
    key = (tuple(items), kmax, nbuckets)
    hit = _TABLE_CACHE.get(key)
    if hit is not None:
        return hit
    out = _position_table_uncached(items, kmax, nbuckets)
    if len(_TABLE_CACHE) >= _TABLE_CACHE_MAX:
        _TABLE_CACHE.clear()
    _TABLE_CACHE[key] = out
    return out


def _position_table_uncached(items, kmax, nbuckets):
    """table[k][s] = (value, ids) for EXACTLY k items costing EXACTLY s buckets, or None.

    Exact 0/1 knapsack with an exact-count constraint. Chosen ids are carried so the winning lineup
    is reconstructed directly rather than re-derived, which is where an off-by-one would hide.
    """
    table = [[None] * (nbuckets + 1) for _ in range(kmax + 1)]
    table[0][0] = (0.0, ())
    for idx, (sal_b, val, pid) in enumerate(items):
        if sal_b <= 0:
            continue
        for k in range(kmax, 0, -1):
            prev = table[k - 1]
            cur = table[k]
            for s in range(nbuckets, sal_b - 1, -1):
                p = prev[s - sal_b]
                if p is None:
                    continue
                cand = p[0] + val
                if cur[s] is None or cand > cur[s][0]:
                    cur[s] = (cand, p[1] + (pid,))
    return table


def _combine(a, b, nbuckets):
    """Exact convolution over the salary axis of two (value, ids) tables indexed by salary."""
    out = [None] * (nbuckets + 1)
    a_nz = [(s, v) for s, v in enumerate(a) if v is not None]
    b_nz = [(s, v) for s, v in enumerate(b) if v is not None]
    for sa, va in a_nz:
        for sb, vb in b_nz:
            s = sa + sb
            if s > nbuckets:
                continue
            cand = va[0] + vb[0]
            if out[s] is None or cand > out[s][0]:
                out[s] = (cand, va[1] + vb[1])
    return out


def _prefix_max(tab):
    """best value at salary AT MOST s, carried forward. Turns 'exactly s' into 'within budget'."""
    best = None
    out = [None] * len(tab)
    for s, v in enumerate(tab):
        if v is not None and (best is None or v[0] > best[0]):
            best = v
        out[s] = best
    return out


def _solve_core(pool, cap, banned, req):
    """The exact DP, honouring required players by fixing them and solving the remainder.

    REQUIREMENTS WERE SILENTLY DROPPED HERE. solve() accepted required_players, passed them down,
    and the enumerator took the argument and never read it -- so a constrained solve returned the
    UNCONSTRAINED lineup and still labelled it PROVEN_OPTIMAL. Asking for the best lineup
    containing a specific quarterback returned one without him. That is the worst shape a defect
    can take in this module, because the answer looks authoritative and is to a different
    question, and the GAP 5 verification never exercised the argument.

    Fixing the required players is exact: their positions reduce the shape's remaining counts and
    their salaries reduce the remaining cap, and the DP then solves that smaller problem exactly.
    """
    nb_full = cap // SALARY_STEP
    req_rows = [p for p in pool if p['id'] in req]
    if len(req_rows) != len(req):
        missing = sorted(set(req) - {p['id'] for p in req_rows})
        return Outcome.fail('REQUIRED_PLAYER_NOT_IN_POOL',
                            f'required ids absent from the pool: {missing}',
                            missing=missing)
    if req & set(banned):
        return Outcome.fail('REQUIRED_PLAYER_ALSO_BANNED',
                            f'ids both required and banned: {sorted(req & set(banned))}')
    req_salary = sum(p['salary'] for p in req_rows)
    req_value = sum(float(p['value']) for p in req_rows)
    req_by_pos = {}
    for p in req_rows:
        req_by_pos[p['position']] = req_by_pos.get(p['position'], 0) + 1

    by_pos = {}
    for p in pool:
        if p['id'] in banned or p['id'] in req:
            continue
        if not p.get('salary') or p.get('value') is None:
            continue
        if p['salary'] % SALARY_STEP:
            return Outcome.fail('SALARY_NOT_ON_GRID',
                                f"{p['id']} salary {p['salary']} is not a multiple of "
                                f"{SALARY_STEP}; the exact DP assumes the grid")
        by_pos.setdefault(p['position'], []).append(
            (p['salary'] // SALARY_STEP, float(p['value']), p['id']))

    best, best_shape, per_shape = None, None, {}
    for shape in SHAPES:
        need = {}
        ok = True
        for pos, k in shape.items():
            k2 = k - req_by_pos.get(pos, 0)
            if k2 < 0:
                ok = False
                break
            need[pos] = k2
        if not ok or any(v > 0 and len(by_pos.get(pos) or []) < v for pos, v in need.items()):
            per_shape[str(shape)] = {'state': 'INFEASIBLE_UNDER_REQUIREMENTS'
                                     if not ok else 'INFEASIBLE_POOL_TOO_THIN'}
            continue
        rem_buckets = (cap - req_salary) // SALARY_STEP
        if rem_buckets < 0:
            per_shape[str(shape)] = {'state': 'INFEASIBLE_REQUIRED_SALARY_OVER_CAP'}
            continue
        tabs = []
        for pos, k2 in need.items():
            if k2 == 0:
                continue
            tabs.append(_position_table(by_pos.get(pos) or [], k2, rem_buckets)[k2])
        if tabs:
            acc = tabs[0]
            for t in tabs[1:]:
                acc = _combine(acc, t, rem_buckets)
            cand = _prefix_max(acc)[rem_buckets]
        else:
            cand = (0.0, ()) if rem_buckets >= 0 else None
        if cand is None:
            per_shape[str(shape)] = {'state': 'INFEASIBLE_NO_FILL'}
            continue
        total = cand[0] + req_value
        per_shape[str(shape)] = {'state': 'SOLVED', 'best_value': round(total, 4)}
        if best is None or total > best[0]:
            best = (total, tuple(cand[1]) + tuple(sorted(req)))
            best_shape = shape
    if best is None:
        return Outcome.blocked('NO_FEASIBLE_LINEUP', 'no shape admitted a legal lineup',
                               cause=Cause.DATA, per_shape=per_shape,
                               required=sorted(req))
    ids = set(best[1])
    sal = sum(p['salary'] for p in pool if p['id'] in ids)
    if sal > cap:
        return Outcome.fail('SOLVE_OVER_CAP', f'{sal} exceeds {cap}', ids=sorted(ids))
    if req - ids:
        return Outcome.fail('REQUIREMENT_NOT_HONOURED',
                            f'required ids missing from the solution: {sorted(req - ids)}',
                            note='this check exists because that is exactly what used to happen')
    return Outcome.ok(PROVEN_OPTIMAL,
                      {'value': round(best[0], 4), 'ids': sorted(ids), 'salary': sal,
                       'shape': best_shape, 'per_shape': per_shape,
                       'optimality': PROVEN_OPTIMAL,
                       'required_players': sorted(req),
                       'PROOF': ('exhaustive over the three legal shapes; within each shape the '
                                 'position tables are exact 0/1 knapsacks with an exact-count '
                                 'constraint and the salary convolution is exact. Required '
                                 'players are fixed, which reduces the counts and the cap and '
                                 'leaves the remainder an exact subproblem. No sampling, no '
                                 'greedy step, no seed.')},
                      f'{round(best[0], 2)} points at {sal}')


def solve(pool, cap=SALARY_CAP, exclude_lineups=(), banned_players=(), required_players=()):
    """The exact best lineup. pool: [{'id','position','salary','value'}].

    exclude_lineups: iterable of frozensets of ids that must NOT be reproduced exactly. Used by
    k_best to enumerate distinct lineups while keeping every individual solve exact.
    required_players: ids that MUST appear. Honoured exactly by _solve_core.
    """
    excluded = {frozenset(x) for x in exclude_lineups}
    req = set(required_players)
    if excluded:
        return _solve_with_constraints(pool, cap, excluded, req, set(banned_players))
    return _solve_core(pool, cap, set(banned_players), req)


def _solve_with_constraints(pool, cap, excluded, req, banned):
    """Exact solve honouring required players and excluded exact lineups.

    Requirements are handled by fixing those players and solving the remainder exactly. Exclusions
    are handled by enumerating in value order until an unexcluded lineup appears, which preserves
    exactness because the enumeration itself is exact.
    """
    for cand in _enumerate_in_value_order(pool, cap, banned, req, limit=len(excluded) + 1):
        if frozenset(cand['ids']) not in excluded:
            cand['optimality'] = PROVEN_OPTIMAL
            cand['PROOF'] = ('exact enumeration in value order; the first lineup not excluded is '
                             'optimal among the unexcluded set.')
            return Outcome.ok(PROVEN_OPTIMAL, cand, f"{cand['value']} points")
    return Outcome.blocked('NO_FEASIBLE_LINEUP_AFTER_EXCLUSIONS',
                           f'{len(excluded)} exclusions exhausted the enumeration',
                           cause=Cause.DATA)


def _enumerate_in_value_order(pool, cap, banned, req, limit):
    """Yield lineups in descending value. Exact, by repeatedly solving with one player banned.

    Lawler's procedure: take the optimum, then for each player in it solve again with that player
    banned, keep the best of those as the next candidate, and recurse. Every candidate produced is
    the exact optimum of its restricted problem, so the sequence is exactly ordered.
    """
    seen = set()
    frontier = []
    base = _solve_core(pool, cap, set(banned), set(req))
    if base.state.name != 'PASS':
        return
    first = base.value
    frontier.append((-first['value'], tuple(sorted(first['ids'])), frozenset(banned)))
    import heapq
    heapq.heapify(frontier)
    produced = 0
    while frontier and produced < limit:
        negv, ids, bans = heapq.heappop(frontier)
        if ids in seen:
            continue
        seen.add(ids)
        sal = sum(p['salary'] for p in pool if p['id'] in set(ids))
        yield {'value': round(-negv, 4), 'ids': list(ids), 'salary': sal}
        produced += 1
        for drop in ids:
            if drop in req:
                continue  # a required player cannot be banned to generate the next candidate
            nb = frozenset(set(bans) | {drop})
            o = _solve_core(pool, cap, set(nb), set(req))
            if o.state.name == 'PASS':
                v = o.value
                t = tuple(sorted(v['ids']))
                if t not in seen:
                    heapq.heappush(frontier, (-v['value'], t, nb))


def k_best(pool, k, cap=SALARY_CAP, banned_players=()):
    """The exact top k distinct lineups, in descending value."""
    out = []
    for cand in _enumerate_in_value_order(pool, cap, set(banned_players), set(), limit=k):
        cand['optimality'] = PROVEN_OPTIMAL
        out.append(cand)
    return out


def solve_structured(pool, cap=SALARY_CAP, *, team_of=None, opp_of=None,
                     qb_stack_min=0, qb_stack_positions=('WR', 'TE'),
                     forbid_dst_against_qb_opp=False, banned_players=()):
    """Exact under the structural constraints a DFS portfolio actually uses.

    A salary DP cannot see "at least two receivers from the quarterback's club" or "no defence
    against the quarterback's opponent", because both depend on WHICH quarterback was chosen. So the
    quarterback and the stack size are ENUMERATED and each sub-problem is solved exactly:

        for each quarterback
          for each legal stack size s at or above the minimum
            solve exactly: the stack players from his club, the rest from everyone else,
            with the defence pool filtered by the opponent rule

    Enumeration over 59 quarterbacks and a handful of stack sizes is exhaustive, so the maximum over
    all sub-problems is the constrained maximum. This is what walking k_best until the constraints
    happened to be satisfied was approximating -- that took minutes and this takes about a second.
    """
    banned = set(banned_players)
    team_of = team_of or {}
    opp_of = opp_of or {}
    nb = cap // SALARY_STEP
    by_pos = {}
    for p in pool:
        if p['id'] in banned or not p.get('salary') or p.get('value') is None:
            continue
        by_pos.setdefault(p['position'], []).append(p)
    qbs = by_pos.get('QB') or []
    if not qbs:
        return Outcome.blocked('NO_QB_IN_POOL', 'no quarterback available', cause=Cause.DATA)

    best = None
    for qb in qbs:
        qb_team = team_of.get(qb['id'])
        qb_opp = opp_of.get(qb['id'])
        dsts = [d for d in (by_pos.get('DST') or [])
                if not (forbid_dst_against_qb_opp and team_of.get(d['id']) == qb_opp)]
        if not dsts:
            continue
        for shape in SHAPES:
            need = {k: v for k, v in shape.items()}
            # stack candidates are WR/TE on the quarterback's own club
            stack_pool = [p for pos in qb_stack_positions
                          for p in (by_pos.get(pos) or [])
                          if team_of.get(p['id']) == qb_team]
            max_stack = min(sum(need[pos] for pos in qb_stack_positions if pos in need),
                            len(stack_pool))
            for s in range(qb_stack_min, max_stack + 1):
                # split the stack count across the stack positions
                stack_positions = [pos for pos in qb_stack_positions if pos in need]
                for split in _splits(s, [need[pos] for pos in stack_positions]):
                    tabs = []
                    ok = True
                    for pos, k in need.items():
                        if pos == 'QB':
                            continue
                        if pos == 'DST':
                            items = [(d['salary'] // SALARY_STEP, float(d['value']), d['id'])
                                     for d in dsts]
                            kk = k
                        elif pos in stack_positions:
                            si = stack_positions.index(pos)
                            n_stack = split[si]
                            same = [(p['salary'] // SALARY_STEP, float(p['value']), p['id'])
                                    for p in (by_pos.get(pos) or [])
                                    if team_of.get(p['id']) == qb_team]
                            other = [(p['salary'] // SALARY_STEP, float(p['value']), p['id'])
                                     for p in (by_pos.get(pos) or [])
                                     if team_of.get(p['id']) != qb_team]
                            if len(same) < n_stack or len(other) < k - n_stack:
                                ok = False
                                break
                            t_same = _position_table(same, n_stack, nb)[n_stack]
                            t_other = _position_table(other, k - n_stack, nb)[k - n_stack]
                            tabs.append(_combine(t_same, t_other, nb))
                            continue
                        else:
                            items = [(p['salary'] // SALARY_STEP, float(p['value']), p['id'])
                                     for p in (by_pos.get(pos) or [])]
                            kk = k
                        if len(items) < kk:
                            ok = False
                            break
                        tabs.append(_position_table(items, kk, nb)[kk])
                    if not ok:
                        continue
                    qb_b = qb['salary'] // SALARY_STEP
                    acc = [None] * (nb + 1)
                    if qb_b <= nb:
                        acc[qb_b] = (float(qb['value']), (qb['id'],))
                    for t in tabs:
                        acc = _combine(acc, t, nb)
                    pm = _prefix_max(acc)
                    cand = pm[nb]
                    if cand and (best is None or cand[0] > best[0]):
                        best = (cand[0], cand[1], shape, qb['id'], s)
    if best is None:
        return Outcome.blocked('NO_FEASIBLE_STRUCTURED_LINEUP',
                               'no quarterback and stack combination admitted a legal lineup',
                               cause=Cause.DATA)
    ids = set(best[1])
    sal = sum(p['salary'] for p in pool if p['id'] in ids)
    return Outcome.ok(PROVEN_OPTIMAL,
                      {'value': round(best[0], 4), 'ids': sorted(ids), 'salary': sal,
                       'shape': best[2], 'qb': best[3], 'stack_size': best[4],
                       'optimality': PROVEN_OPTIMAL,
                       'PROOF': ('exhaustive over quarterbacks, shapes and stack splits; each '
                                 'sub-problem solved by the exact salary DP. The maximum over an '
                                 'exhaustive partition of the feasible set is the constrained '
                                 'maximum.')},
                      f'{round(best[0], 2)} at {sal}')


def _splits(total, caps):
    """Every way to write `total` as a sum over len(caps) slots, each within its cap."""
    if not caps:
        if total == 0:
            yield ()
        return
    head, rest = caps[0], caps[1:]
    for v in range(0, min(head, total) + 1):
        for tail in _splits(total - v, rest):
            yield (v,) + tail

# ======================================================================================
# the governed entry point: every constraint compiled, enforced and verified
# ======================================================================================
DEFAULT_SEARCH_BUDGET = 60


def solve_governed(pool, cap=SALARY_CAP, *, search_budget=DEFAULT_SEARCH_BUDGET, **requested):
    """Solve under a COMPLETE, reconciled constraint set, or refuse to claim anything.

    This is the entry point every caller should prefer. It differs from solve() in the one way that
    matters: it cannot silently drop a constraint. Each request is compiled to an enforcement route,
    the answer is verified against every compiled constraint one at a time, and the three sets --
    requested, compiled, verified -- must reconcile before an optimality word is used.

    HOW CROSS-CUTTING CONSTRAINTS ARE ENFORCED EXACTLY

    The salary dynamic program cannot see "at most four players from one club" or "at least one
    player from the quarterback's opponent", because those depend on which players were chosen
    elsewhere. Rather than approximate them, they are enforced by exact enumeration in DESCENDING
    VALUE ORDER with a predicate: the first roster that satisfies the predicate is optimal among all
    satisfying rosters, because every better roster was generated and rejected first.

    That gives a strong guarantee and an honest failure mode. Found inside the budget means PROVEN
    OPTIMAL under the full set. Budget exhausted means BLOCKED -- never a lineup with a proof it has
    not earned.
    """
    from nfl.opt import constraints as C
    idx = C.index(pool)
    cs = C.ConstraintSet({'salary_cap': cap, 'shape': SHAPES, **requested})
    comp = cs.compile(native_supported=('salary_cap', 'shape', 'required_players',
                                        'locked_players', 'banned_players'))
    if comp.state is not State.PASS:
        return comp

    req = set(cs.compiled.get('required_players') or ()) | \
        set(cs.compiled.get('locked_players') or ())
    banned = set(cs.compiled.get('banned_players') or ())
    enumerated = cs.enumerated()

    # QB-RELATIVE CONSTRAINTS ARE PARTITIONED BY QUARTERBACK.
    #
    # "at least two pass catchers from the quarterback's club" and "at least one from his opponent"
    # are not properties of a roster the value order knows about, so enumerating the global frontier
    # and hoping walks a very long way: a two-man stack with a bring-back was not found in the best
    # 150 rosters on this slate. But every lineup contains EXACTLY ONE quarterback, so the feasible
    # set partitions cleanly by him -- and once he is fixed, both constraints become concrete team
    # memberships that the top of his own frontier tends to satisfy immediately. The maximum over an
    # exhaustive partition is the constrained maximum, so this is exact, not a heuristic.
    QB_RELATIVE = ('qb_stack_min', 'bring_back_min', 'forbid_dst_against_qb_opp')
    if enumerated and set(enumerated) <= set(QB_RELATIVE):
        got = _solve_qb_groups(
            pool, cap, banned, req,
            qb_stack_min=cs.compiled.get('qb_stack_min', 0),
            bring_back_min=cs.compiled.get('bring_back_min', 0),
            forbid_dst_against_qb_opp=bool(cs.compiled.get('forbid_dst_against_qb_opp')))
        if got.state is not State.PASS:
            return got
        ver = cs.verify_all(got.value['ids'], idx)
        note = got.value['PROOF']
        manifest = cs.manifest(exhaustive=True, search_note=note)
        if ver.state is not State.PASS:
            return Outcome.fail('SOLVE_CONSTRAINTS_NOT_VERIFIED',
                                'the roster does not verify against its own compiled constraints',
                                manifest=manifest, **(ver.evidence or {}))
        status = C.status_for(manifest)
        if status == 'INVALID':
            return Outcome.fail('SOLVE_CONSTRAINT_MANIFEST_DOES_NOT_RECONCILE',
                                'requested, compiled and verified do not agree', manifest=manifest)
        return Outcome.ok(status, dict(got.value, optimality=status,
                                       constraint_manifest=manifest,
                                       n_rosters_examined=got.value.get('n_subproblems')),
                          f'{got.value["value"]} points at {got.value["salary"]} under '
                          f'{len(manifest["compiled_constraints"])} constraints')

    examined = 0
    if not enumerated:
        base = _solve_core(pool, cap, banned, req)
        if base.state is not State.PASS:
            return base
        chosen, examined = base.value, 1
        note = 'exhaustive dynamic program over the three legal shapes; no enumerated constraint'
    else:
        chosen = None
        for cand in _enumerate_in_value_order(pool, cap, banned, req, limit=search_budget):
            examined += 1
            if cs.satisfies(cand['ids'], idx):
                chosen = cand
                break
        if chosen is None:
            return Outcome.blocked(
                'NO_LINEUP_SATISFIED_CONSTRAINTS_WITHIN_BUDGET',
                f'{examined} best-value rosters examined, none satisfied '
                f'{sorted(enumerated)}',
                cause=Cause.DATA, examined=examined, search_budget=search_budget,
                enumerated_constraints=sorted(enumerated),
                manifest=cs.manifest(exhaustive=False,
                                     search_note=f'budget of {search_budget} exhausted'),
                note=('no optimality is claimed and no lineup is returned. Raising the budget may '
                      'find one; returning the unconstrained optimum would be the original '
                      'defect.'))
        note = (f'exact enumeration in descending value order; {examined} roster(s) generated and '
                f'every one better than the answer was rejected by the predicate, so the answer is '
                f'optimal among satisfying rosters')

    ver = cs.verify_all(chosen['ids'], idx)
    manifest = cs.manifest(exhaustive=True, search_note=note)
    if ver.state is not State.PASS:
        return Outcome.fail('SOLVE_CONSTRAINTS_NOT_VERIFIED',
                            'the roster does not verify against its own compiled constraints',
                            manifest=manifest, **(ver.evidence or {}))
    status = C.status_for(manifest)
    if status == 'INVALID':
        return Outcome.fail('SOLVE_CONSTRAINT_MANIFEST_DOES_NOT_RECONCILE',
                            'requested, compiled and verified do not agree',
                            manifest=manifest)
    ids = sorted(set(chosen['ids']))
    sal = sum(idx[i]['salary'] for i in ids)
    return Outcome.ok(status, {
        'value': round(float(chosen['value']), 4), 'ids': ids, 'salary': sal,
        'optimality': status,
        'n_rosters_examined': examined,
        'constraint_manifest': manifest,
        'PROOF': note,
    }, f'{round(float(chosen["value"]), 2)} points at {sal} under '
       f'{len(manifest["compiled_constraints"])} constraints')

def _solve_qb_groups(pool, cap, banned, req, *, qb_stack_min=0, bring_back_min=0,
                     forbid_dst_against_qb_opp=False, stack_positions=('WR', 'TE'),
                     bring_back_positions=('WR', 'TE', 'RB'), max_subproblems=120000):
    """Exact solve for constraints defined relative to the quarterback's club and his opponent.

    Enumerating the global value order does not work for these. A two-man stack with a bring-back was
    not found in the best 150 rosters on a real slate, and per-quarterback enumeration did not find
    it either, because the best rosters for any given quarterback use the slate's best receivers
    rather than his teammates. The search was looking in the wrong space.

    The right space is a partition. Every lineup has exactly one quarterback, and once he is fixed
    every other player falls into one of three groups: his club, his opponent, everyone else. A
    stack minimum is a lower bound on the count drawn from the first group, and a bring-back minimum
    is a lower bound on the count drawn from the second. So for each quarterback, each legal shape,
    and each way of splitting that shape's slots across the three groups subject to those bounds,
    the remaining problem is an ordinary exact-count knapsack per (position, group) and the salary
    convolution is exact.

    The maximum over an exhaustive partition of the feasible set is the constrained maximum, so this
    is proven optimal rather than a good search. It is also roughly thirty times faster than the
    enumeration it replaces: the same answer for a two-man stack in about four seconds against a
    hundred and fifty.
    """
    nb = cap // SALARY_STEP
    rows = [p for p in pool if p['id'] not in banned and p.get('salary') and p.get('value') is not None]
    for p in rows:
        if p['salary'] % SALARY_STEP:
            return Outcome.fail('SALARY_NOT_ON_GRID',
                                f"{p['id']} salary {p['salary']} is not a multiple of {SALARY_STEP}")
    by_pos = {}
    for p in rows:
        by_pos.setdefault(p['position'], []).append(p)
    qbs = [q for q in (by_pos.get('QB') or [])]
    req_qb = [i for i in req if any(p['id'] == i and p['position'] == 'QB' for p in rows)]
    if len(req_qb) > 1:
        return Outcome.fail('MULTIPLE_QUARTERBACKS_REQUIRED', f'{sorted(req_qb)} cannot all start')
    if req_qb:
        qbs = [q for q in qbs if q['id'] == req_qb[0]]
    if not qbs:
        return Outcome.blocked('NO_QB_IN_POOL', 'no quarterback available after constraints',
                               cause=Cause.DATA)
    req_non_qb = {i for i in req if i not in set(req_qb)}

    best, best_meta, n_sub = None, None, 0
    for qb in qbs:
        club, opp = qb.get('team'), qb.get('opponent')
        if qb_stack_min and club is None:
            continue
        if bring_back_min and opp is None:
            continue
        # ONLY SPLIT THE GROUPS A CONSTRAINT ACTUALLY NEEDS.
        #
        # Distinguishing all three groups when only one bound is in force multiplies the split
        # enumeration for nothing: asking for a bring-back alone blew a 120,000-subproblem budget
        # because every irrelevant own-club count was being enumerated too. With the unneeded group
        # merged the same query is a few thousand subproblems. Merging cannot change the answer,
        # because a group no bound refers to is interchangeable with 'everyone else' by definition.
        split_A = qb_stack_min > 0
        split_B = bring_back_min > 0 or forbid_dst_against_qb_opp

        def grp(p):
            if split_A and p.get('team') == club:
                return 'A'
            if split_B and opp is not None and p.get('team') == opp:
                return 'B'
            return 'C'
        split_pool = {}
        for pos, ps in by_pos.items():
            if pos == 'QB':
                continue
            d = {'A': [], 'B': [], 'C': []}
            for p in ps:
                if pos == 'DST' and forbid_dst_against_qb_opp and p.get('team') == opp:
                    continue
                d[grp(p)].append((p['salary'] // SALARY_STEP, float(p['value']), p['id']))
            split_pool[pos] = d
        # requirements per (pos, group), so a required player is not double counted or dropped
        need_fixed = {}
        bad = False
        for i in req_non_qb:
            r = next((p for p in rows if p['id'] == i), None)
            if r is None:
                bad = True
                break
            need_fixed[(r['position'], grp(r))] = need_fixed.get((r['position'], grp(r)), 0) + 1
        if bad:
            continue
        memo = {}

        def table(pos, g, k):
            if k <= 0:
                return None
            key = (pos, g, k)
            if key not in memo:
                items = split_pool[pos][g]
                if len(items) < k:
                    memo[key] = False
                else:
                    memo[key] = _position_table(items, k, nb)[k]
            return memo[key]

        for shape in SHAPES:
            positions = [p for p in shape if p != 'QB']
            # enumerate the per-position (a, b) counts; c is whatever is left
            options = {}
            for pos in positions:
                k = shape[pos]
                opts = []
                for a in range(k + 1 if split_A else 1):
                    for b in range(k - a + 1 if split_B else 1):
                        if pos == 'DST' and b > 0 and forbid_dst_against_qb_opp:
                            continue
                        if need_fixed.get((pos, 'A'), 0) > a or need_fixed.get((pos, 'B'), 0) > b \
                                or need_fixed.get((pos, 'C'), 0) > k - a - b:
                            continue
                        opts.append((a, b))
                if not opts:
                    opts = None
                    break
                options[pos] = opts
            if any(options.get(pos) is None for pos in positions):
                continue

            def walk(i, acc_a, acc_b, chosen):
                nonlocal best, best_meta, n_sub
                if n_sub > max_subproblems:
                    return
                if i == len(positions):
                    if acc_a < qb_stack_min or acc_b < bring_back_min:
                        return
                    n_sub += 1
                    qb_b = qb['salary'] // SALARY_STEP
                    if qb_b > nb:
                        return
                    acc = [None] * (nb + 1)
                    acc[qb_b] = (float(qb['value']), (qb['id'],))
                    for pos, (a, b) in chosen.items():
                        k = shape[pos]
                        for g, cnt in (('A', a), ('B', b), ('C', k - a - b)):
                            t = table(pos, g, cnt)
                            if t is False:
                                return
                            if t is None:
                                continue
                            acc = _combine(acc, t, nb)
                    cand = _prefix_max(acc)[nb]
                    if cand and (best is None or cand[0] > best[0]):
                        best = cand
                        best_meta = {'shape': shape, 'qb': qb['id'], 'stack_from_club': acc_a,
                                     'from_opponent': acc_b}
                    return
                pos = positions[i]
                for a, b in options[pos]:
                    add_a = a if pos in stack_positions else 0
                    add_b = b if pos in bring_back_positions else 0
                    walk(i + 1, acc_a + add_a, acc_b + add_b, {**chosen, pos: (a, b)})

            walk(0, 0, 0, {})

    if n_sub > max_subproblems:
        return Outcome.blocked('QB_GROUP_SEARCH_BUDGET_EXCEEDED',
                               f'more than {max_subproblems} subproblems; no optimum claimed',
                               cause=Cause.ENVIRONMENT, subproblems=n_sub)
    if best is None:
        return Outcome.blocked('NO_FEASIBLE_LINEUP_UNDER_TEAM_CONSTRAINTS',
                               'no quarterback and group split admitted a legal lineup',
                               cause=Cause.DATA, n_subproblems=n_sub,
                               qb_stack_min=qb_stack_min, bring_back_min=bring_back_min)
    ids = sorted(set(best[1]))
    sal = sum(p['salary'] for p in rows if p['id'] in set(ids))
    return Outcome.ok(PROVEN_OPTIMAL, {
        'value': round(best[0], 4), 'ids': ids, 'salary': sal,
        'optimality': PROVEN_OPTIMAL, 'n_subproblems': n_sub, **(best_meta or {}),
        'PROOF': (f'exhaustive over quarterbacks, shapes and every split of the shape\'s slots '
                  f'across the quarterback\'s club, his opponent and everyone else; '
                  f'{n_sub} exact subproblems. The maximum over an exhaustive partition of the '
                  f'feasible set is the constrained maximum.')},
        f'{round(best[0], 2)} at {sal}')
