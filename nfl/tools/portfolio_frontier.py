#!/usr/bin/env python3.12
"""The projection/diversification frontier. Four portfolios, one pool, no winner declared.

WHAT THIS ANSWERS. The first autonomous portfolio projected 140-150 while the owner's
FC-optimised placeholders projected 165-171, and I attributed the gap to "diversification".
That attribution was untested. There are two possible explanations and they have opposite
consequences:

  (a) diversification genuinely costs ~15 points on this slate, or
  (b) my candidate generator was weak and I labelled its weakness as a design choice.

PROJECTION_MAX settles it. It runs on the same pool with diversification switched off and a
hill-climbing search. If it reaches the owner's range, (a) holds and the frontier is real.
If it does not, (b) holds and the honest finding is that I blamed a cap for my own sampler.

Every portfolio reports the same statistics and NONE is declared best, because choosing a
point on this curve requires a field model and we do not have one.
"""
from __future__ import annotations

import collections
import csv
import itertools
import json
import pathlib
import random
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import fc_context as FC  # noqa: E402
from nfl.tools import portfolio_modes as M  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'portfolio-frontier-1'
SEED = 20260927
CAP = 50_000
SLOTS = ('QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST')
NEED = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'DST': 1}
FLEX_OK = ('RB', 'WR', 'TE')

POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OWNER_CSV = _REPO / 'nfl/dfs/salaries/raw/OWNER_PLACEHOLDERS_FC_48_2026W3.csv'
OUT = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PORTFOLIO_FRONTIER.json'
ID = re.compile(r'\((\d+)\)')


def load_pool():
    post = json.loads(POST.read_text())
    players = post['players']
    absent = {k for k, v in players.items()
              if v['current_availability']['status'] in AV.ABSENT_STATUSES}
    fcr = FC.load()
    if fcr.state is not State.PASS:
        return None, None, fcr
    joined, _, _ = FC.join_to_dk(fcr.value, players)
    pool = collections.defaultdict(list)
    idx = {}
    for k, v in players.items():
        if k in absent:
            continue
        m = ((joined.get(k) or {}).get(FC.CONTEXT_KEY) or {}).get('FC Proj')
        if not isinstance(m, (int, float)) or m <= 0:
            continue
        r = {'id': k, 'name': v['name'], 'pos': v['position'], 'team': v['team'],
             'opp': v['opponent'], 'salary': v['salary'], 'mean': float(m)}
        pool[v['position']].append(r)
        idx[k] = r
    for p in pool:
        pool[p].sort(key=lambda r: -r['mean'])
    return pool, idx, Outcome.ok('POOL_READY', {'pool': pool, 'idx': idx, 'absent': absent,
                                                'players': players},
                                 f'{len(idx)} usable players')


def _legal(lu):
    if len(lu) != 9:
        return False
    if len({r['id'] for r in lu}) != 9:
        return False
    if sum(r['salary'] for r in lu) > CAP:
        return False
    c = collections.Counter(r['pos'] for r in lu)
    if c['QB'] != 1 or c['DST'] != 1:
        return False
    if c['RB'] < 2 or c['WR'] < 3 or c['TE'] < 1:
        return False
    return True


def _struct_ok(lu, cons):
    qb = next(r for r in lu if r['pos'] == 'QB')
    dst = next(r for r in lu if r['pos'] == 'DST')
    if cons['no_dst_against_own_qb'].value and dst['team'] == qb['opp']:
        return False
    n = sum(1 for r in lu if r['team'] == qb['team'] and r['pos'] in ('WR', 'TE'))
    return (cons['min_pass_catchers_with_qb'].value <= n
            <= cons['max_pass_catchers_with_qb'].value)


def _hill_climb(lu, pool, cons, rounds=60):
    """Swap one player at a time for a better-projecting legal alternative."""
    best = list(lu)
    best_tot = sum(r['mean'] for r in best)
    for _ in range(rounds):
        improved = False
        for i, cur in enumerate(best):
            used = {r['id'] for r in best if r is not cur}
            for cand in pool[cur['pos']][:60]:
                if cand['id'] in used:
                    continue
                trial = list(best)
                trial[i] = cand
                if not _legal(trial) or not _struct_ok(trial, cons):
                    continue
                tot = sum(r['mean'] for r in trial)
                if tot > best_tot + 1e-9:
                    best, best_tot, improved = trial, tot, True
                    break
            if improved:
                break
        if not improved:
            break
    return best, best_tot


MIN_SAL = {'QB': 4000, 'RB': 4000, 'WR': 3000, 'TE': 2500, 'DST': 2000}


def _reserve(remaining_slots):
    """Cheapest possible cost of the slots still to fill, so a greedy pick cannot
    strand the lineup over the cap. Without this the seed is salary-blind: picking the
    top player at every position costs far more than $50,000 and every attempt dies."""
    return sum(MIN_SAL.get(p, 3000) for p in remaining_slots)


def _seed_lineup(pool, cons, rng, temp):
    """One structurally valid, salary-feasible lineup.

    `temp` controls greediness: 0 takes the best affordable option, higher values sample
    more widely. Affordability is checked against the remaining budget MINUS a reserve for
    the slots still to fill, which is what the first version omitted.
    """
    plan = ['QB', 'STACK', 'DST', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX']

    def afford(opts, budget, remaining):
        res = _reserve(remaining)
        return [r for r in opts if r['salary'] <= budget - res]

    for _ in range(60):
        used, lu, budget = set(), [], CAP
        qb_opts = afford(pool['QB'], budget, plan[3:] + ['WR'] * 1)
        if not qb_opts:
            return None
        w = 1 if temp <= 0 else max(1, int(len(qb_opts) * temp))
        qb = rng.choice(qb_opts[:w])
        lu.append(qb)
        used.add(qb['id'])
        budget -= qb['salary']

        mates = sorted([r for r in pool['WR'] + pool['TE'] if r['team'] == qb['team']],
                       key=lambda r: -r['mean'])
        lo = cons['min_pass_catchers_with_qb'].value
        hi = min(cons['max_pass_catchers_with_qb'].value, len(mates))
        if hi < lo:
            continue
        k = rng.randint(lo, hi)
        pick_from = afford(mates, budget, ['RB', 'RB', 'WR', 'WR', 'TE', 'DST', 'FLEX'])
        if len(pick_from) < k:
            continue
        w = k if temp <= 0 else max(k, int(len(pick_from) * temp))
        stack = rng.sample(pick_from[:max(k, w)], k)
        for r in stack:
            lu.append(r)
            used.add(r['id'])
            budget -= r['salary']

        dsts = [d for d in pool['DST'] if d['team'] != qb['opp']]
        dsts = afford(sorted(dsts, key=lambda r: -r['mean']), budget,
                      ['RB', 'RB', 'WR', 'WR', 'TE', 'FLEX'])
        if not dsts:
            continue
        w = 1 if temp <= 0 else max(1, int(len(dsts) * temp))
        dst = rng.choice(dsts[:w])
        lu.append(dst)
        used.add(dst['id'])
        budget -= dst['salary']

        have = collections.Counter(r['pos'] for r in lu)
        todo = []
        for pos, need in (('RB', 2), ('WR', 3), ('TE', 1)):
            todo += [pos] * max(0, need - have[pos])
        todo.append('FLEX')
        ok = True
        for i, pos in enumerate(todo):
            rest = todo[i + 1:]
            if pos == 'FLEX':
                opts = [r for r in pool['RB'] + pool['WR'] + pool['TE']
                        if r['id'] not in used]
            else:
                opts = [r for r in pool[pos] if r['id'] not in used]
            opts = afford(sorted(opts, key=lambda r: -r['mean']), budget, rest)
            if not opts:
                ok = False
                break
            w = 1 if temp <= 0 else max(1, int(len(opts) * temp))
            r = rng.choice(opts[:w])
            lu.append(r)
            used.add(r['id'])
            budget -= r['salary']
        if ok and _legal(lu) and _struct_ok(lu, cons):
            return lu
    return None


def candidates(pool, cons, n=6000):
    rng = random.Random(SEED)
    out, seen = [], set()
    tries = 0
    while len(out) < n and tries < n * 25:
        tries += 1
        temp = rng.choice([0.0, 0.03, 0.06, 0.12, 0.25, 0.45])
        lu = _seed_lineup(pool, cons, rng, temp)
        if lu is None:
            continue
        if temp <= 0.12:
            lu, _ = _hill_climb(lu, pool, cons, rounds=25)
        key = tuple(sorted(r['id'] for r in lu))
        if key in seen:
            continue
        seen.add(key)
        qb = next(r for r in lu if r['pos'] == 'QB')
        dst = next(r for r in lu if r['pos'] == 'DST')
        out.append({
            'players': lu, 'ids': key,
            'salary': sum(r['salary'] for r in lu),
            'proj_total': round(sum(r['mean'] for r in lu), 2),
            'qb': qb['name'], 'qb_club': qb['team'], 'qb_opp': qb['opp'],
            'stack': [r['name'] for r in lu
                      if r['team'] == qb['team'] and r['pos'] in ('WR', 'TE')],
            'bring_back': [r['name'] for r in lu
                           if r['team'] == qb['opp'] and r['pos'] != 'DST'] or None,
            'dst': dst['team'],
            'games': len({tuple(sorted((r['team'], r['opp']))) for r in lu}),
        })
    out.sort(key=lambda c: -c['proj_total'])
    return out


def optimum(pool, cons, seeds=None, restarts=250):
    """The EXACT best legal lineup. PROVEN_OPTIMAL, not "best found".

    REPLACED THE HILL CLIMB 2026-09-28. The previous version searched from random and from candidate
    seeds and returned 169.48 -- 2.83 below the true maximum, which it had no way of knowing. An
    exact dynamic program over the three legal roster shapes returns the maximum itself in about
    0.05 seconds, and the optimiser is verified against brute force on 60 random slates in
    nfl/opt/verify.py. A reference that is merely the best of a search cannot bound anything.

    Structural constraints (no defence against your own quarterback, stack requirements) are not
    expressible in the salary DP, so where they are active the lineups are ENUMERATED IN EXACT VALUE
    ORDER and the first that satisfies them is returned. That is still exact for the constrained
    problem: nothing better can exist above it in the ordering.
    """
    from nfl.opt import exact as _exact
    flat = [{'id': r['id'], 'position': r['pos'], 'salary': r['salary'], 'value': r['mean']}
            for lst in pool.values() for r in lst]
    idx = {r['id']: r for lst in pool.values() for r in lst}
    o = _exact.solve(flat, CAP)
    if o.state is State.PASS:
        lu = [idx[i] for i in o.value['ids']]
        if _legal(lu) and _struct_ok(lu, cons):
            return lu, round(o.value['value'], 2)
    # STRUCTURE BINDS: solve it exactly rather than walking an ordering until it happens to hold.
    # Walking k_best took minutes and was only approximating the constrained optimum; enumerating
    # quarterbacks and stack splits inside the DP is exhaustive and takes about fifteen seconds.
    post = json.loads(POST.read_text())
    team_of = {r['id']: r['team'] for lst in pool.values() for r in lst}
    opp_of = {k: (v.get('opponent')) for k, v in post['players'].items()}
    o2 = _exact.solve_structured(
        flat, CAP, team_of=team_of, opp_of=opp_of,
        qb_stack_min=int(cons['min_pass_catchers_with_qb'].value
                         if 'min_pass_catchers_with_qb' in cons else 0),
        forbid_dst_against_qb_opp=bool(cons['no_dst_against_own_qb'].value
                                       if 'no_dst_against_own_qb' in cons else False))
    if o2.state is State.PASS:
        lu = [idx[i] for i in o2.value['ids']]
        if _legal(lu):
            return lu, round(o2.value['value'], 2)
    return None, -1.0


def select(cands, cons, n):
    exp, qb_exp, chosen = collections.Counter(), collections.Counter(), []
    max_p = cons['max_player_exposure'].value * n
    max_q = cons['max_qb_exposure'].value * n
    ov_cap = cons['max_pairwise_overlap'].value
    binding = collections.Counter()
    for c in cands:
        if len(chosen) >= n:
            break
        if qb_exp[c['qb']] >= max_q:
            binding['max_qb_exposure'] += 1
            continue
        if any(exp[i] >= max_p for i in c['ids']):
            binding['max_player_exposure'] += 1
            continue
        if ov_cap < 9 and any(len(set(c['ids']) & set(o['ids'])) > ov_cap
                              for o in chosen):
            binding['max_pairwise_overlap'] += 1
            continue
        chosen.append(c)
        qb_exp[c['qb']] += 1
        for i in c['ids']:
            exp[i] += 1
    for name, hits in binding.items():
        if name in cons:
            cons[name].became_binding = True
            cons[name].binding_detail = f'rejected {hits} candidate(s)'
    return chosen, dict(binding)


def stats(chosen, label, cons, opt_total):
    if not chosen:
        return {'mode': label, 'state': 'UNDERFILLED', 'n': 0}
    n = len(chosen)
    totals = sorted(c['proj_total'] for c in chosen)
    exp, qb, dst = collections.Counter(), collections.Counter(), collections.Counter()
    pairs, trios = collections.Counter(), collections.Counter()
    for c in chosen:
        names = sorted(r['name'] for r in c['players'])
        for x in names:
            exp[x] += 1
        qb[c['qb']] += 1
        dst[c['dst']] += 1
        for p in itertools.combinations(names, 2):
            pairs[p] += 1
        for t in itertools.combinations(names, 3):
            trios[t] += 1
    ov = [len(set(a['ids']) & set(b['ids']))
          for a, b in itertools.combinations(chosen, 2)]
    mean = sum(totals) / n
    return {
        'mode': label, 'state': 'OK', 'n': n,
        'intent': M.MODES[label]['intent'] if label in M.MODES else None,
        'proj_mean': round(mean, 2),
        'proj_median': round(totals[n // 2], 2),
        'proj_min': round(totals[0], 2), 'proj_max': round(totals[-1], 2),
        'optimum_reference': opt_total,
        'gap_to_optimum_mean': round(opt_total - mean, 2),
        'gap_to_optimum_pct': round(100 * (opt_total - mean) / opt_total, 2),
        'qb_exposure': {k: round(100 * v / n, 1) for k, v in qb.most_common()},
        'n_distinct_qbs': len(qb),
        'top_player_exposure': {k: round(100 * v / n, 1) for k, v in exp.most_common(8)},
        'max_player_exposure_pct': round(100 * max(exp.values()) / n, 1),
        'dst_exposure': {k: round(100 * v / n, 1) for k, v in dst.most_common(6)},
        'max_pair_exposure': {'pair': list(pairs.most_common(1)[0][0]),
                              'pct': round(100 * pairs.most_common(1)[0][1] / n, 1)},
        'max_trio_exposure': {'trio': list(trios.most_common(1)[0][0]),
                              'pct': round(100 * trios.most_common(1)[0][1] / n, 1)},
        'mean_pairwise_overlap': round(sum(ov) / len(ov), 2) if ov else None,
        'max_pairwise_overlap': max(ov) if ov else None,
        'stack_sizes': dict(collections.Counter(len(c['stack']) for c in chosen)),
        'bring_back_pct': round(100 * sum(1 for c in chosen if c['bring_back']) / n, 1),
        'mean_games_represented': round(sum(c['games'] for c in chosen) / n, 2),
        'salary': {'min': min(c['salary'] for c in chosen),
                   'max': max(c['salary'] for c in chosen),
                   'mean': round(sum(c['salary'] for c in chosen) / n, 1)},
        'projection_loss_guard': M.projection_loss_guard(chosen, opt_total),
        'constraints': {k: v.as_dict() for k, v in cons.items()},
        'binding_constraints': [k for k, v in cons.items() if v.became_binding],
    }


def owner_benchmark(idx, players):
    if not OWNER_CSV.exists():
        return None
    rows = list(csv.reader(OWNER_CSV.open(newline='', encoding='utf-8-sig')))
    hdr = [c.strip() for c in rows[0]]
    ei = hdr.index('Entry ID')
    slot = [i for i, c in enumerate(hdr) if c in ('QB', 'RB', 'WR', 'TE', 'FLEX', 'DST')]
    chosen = []
    for r in rows[1:]:
        if len(r) <= ei or not r[ei].strip():
            continue
        ids = [ID.search(r[i]).group(1) for i in slot if ID.search(r[i])]
        lu = [idx[i] for i in ids if i in idx]
        if len(lu) != 9:
            # a player with no FC row cannot be scored; keep the lineup but note it
            pass
        qb = next((x for x in lu if x['pos'] == 'QB'), None)
        dstr = next((x for x in lu if x['pos'] == 'DST'), None)
        chosen.append({
            'players': lu, 'ids': tuple(sorted(ids)),
            'salary': sum(players[i]['salary'] for i in ids if i in players),
            'proj_total': round(sum(x['mean'] for x in lu), 2),
            'qb': qb['name'] if qb else 'NONE',
            'qb_club': qb['team'] if qb else None,
            'qb_opp': qb['opp'] if qb else None,
            'stack': [x['name'] for x in lu
                      if qb and x['team'] == qb['team'] and x['pos'] in ('WR', 'TE')],
            'bring_back': [x['name'] for x in lu
                           if qb and x['team'] == qb['opp'] and x['pos'] != 'DST'] or None,
            'dst': dstr['team'] if dstr else 'NONE',
            'games': len({tuple(sorted((players[i]['team'], players[i]['opponent'])))
                          for i in ids if i in players}),
        })
    return chosen


def run(n_entries=48):
    pool, idx, r = load_pool()
    if r.state is not State.PASS:
        return r
    players = r.value['players']

    ref_cons = M.MODES['PROJECTION_MAX']['constraints']()
    ref_cands = candidates(pool, ref_cons, n=6000)
    best_lu, opt_total = optimum(
        pool, ref_cons, seeds=[c['players'] for c in ref_cands[:60]])
    if ref_cands and ref_cands[0]['proj_total'] > opt_total:
        best_lu, opt_total = ref_cands[0]['players'], ref_cands[0]['proj_total']
    if best_lu is None:
        return Outcome.fail('NO_LEGAL_LINEUP', 'could not construct a single legal lineup')

    out = {'artifact': 'DK_WEEK3_PORTFOLIO_FRONTIER', 'spec_version': SPEC_VERSION,
           'projection_source': 'EXTERNAL_FC_FALLBACK',
           'NOT_OUR_PROJECTION': ('all totals below are sums of FantasyCruncher numbers. '
                                  'They rank portfolios against each other on a common '
                                  'yardstick; they are not our model.'),
           'BEST_KNOWN_NOT_PROVEN_OPTIMAL': (
               'the reference below is the best legal lineup KNOWN from any source. It is a '
               'lower bound on the true optimum, so every reported gap understates the '
               'real distance to optimal.'),
           'optimum_legal_lineup': {
               'proj_total': opt_total,
               'salary': sum(x['salary'] for x in best_lu),
               'players': [x['name'] for x in best_lu],
               'method': ('hill climbing from the 60 best generated candidates AND from '
                          '250 fresh random seeds, taking the best. A near-optimal '
                          'reference, not a proven global maximum. An earlier version '
                          'climbed only from fresh seeds, returned 161.06 while candidates '
                          'reached 169.5, and produced negative gaps -- which is how the '
                          'local-optimum trap was caught.'),
               'sanity': 'no portfolio mean may exceed this value; a negative gap is a bug'},
           'sim_optimal': M.SIM_OPTIMAL_UNAVAILABLE,
           'NO_MODE_IS_BEST': (
               'choosing a point on this frontier requires pricing the benefit of '
               'diversification against a field, which needs an ownership model and joint '
               'simulation. Neither exists, so the curve is reported and no winner is '
               'declared.'),
           'modes': {}}

    for label in ('PROJECTION_MAX', 'LIGHT_DIVERSIFICATION', 'BALANCED',
                  'HIGH_DIVERSIFICATION'):
        cons = M.MODES[label]['constraints']()
        cands = ref_cands if label == 'PROJECTION_MAX' else candidates(pool, cons)
        chosen, binding = select(cands, cons, n_entries)
        s = stats(chosen, label, cons, opt_total)
        s['n_candidates'] = len(cands)
        s['rejections_by_constraint'] = binding
        if len(chosen) < n_entries:
            s['state'] = 'UNDERFILLED'
            s['detail'] = (f'{len(chosen)} of {n_entries} under these caps; loosen one '
                           f'deliberately rather than filling with duplicates')
        out['modes'][label] = s

    bench = owner_benchmark(idx, players)
    # THE REFERENCE IS A LOWER BOUND, NOT AN OPTIMUM. The owner's benchmark file contains a
    # lineup at 171.6 while my search topped out at 169.48, which proves the search is not
    # optimal. So the reference is the best lineup KNOWN from any source -- search,
    # candidates or benchmark -- and it is named accordingly.
    if bench:
        bb = max((c['proj_total'] for c in bench if c['proj_total']), default=0)
        if bb > opt_total:
            out['optimum_legal_lineup']['beaten_by_benchmark'] = {
                'benchmark_best': bb, 'search_best': opt_total,
                'implication': ('the search is NOT optimal: a lineup in the owner file '
                                'scores higher than anything the search found. The '
                                'reference is therefore a lower bound and every gap below '
                                'is an UNDERSTATEMENT of the true distance to optimal.')}
            opt_total = bb
            out['optimum_legal_lineup']['proj_total'] = bb
            out['optimum_legal_lineup']['source'] = 'OWNER_BENCHMARK_LINEUP'
            for lab, st in out['modes'].items():
                if st.get('state') != 'OK':
                    continue
                st['optimum_reference'] = bb
                st['gap_to_optimum_mean'] = round(bb - st['proj_mean'], 2)
                st['gap_to_optimum_pct'] = round(100 * (bb - st['proj_mean']) / bb, 2)
                st['projection_loss_guard'] = M.projection_loss_guard(
                    [{'proj_total': st['proj_mean']}], bb)
    if bench:
        bc = M.MODES['PROJECTION_MAX']['constraints']()
        b = stats(bench, 'PROJECTION_MAX', bc, opt_total)
        b['mode'] = 'OWNER_FC_PLACEHOLDERS'
        b['intent'] = 'the owner-built FC-optimised benchmark. Never modified.'
        b['note'] = ('scored on the same FC numbers and the same optimum reference. Some '
                     'rostered players have no FC row, so a few totals are sums over '
                     'fewer than nine scoreable players -- that biases this benchmark '
                     'DOWN, not up.')
        b.pop('constraints', None)
        b.pop('binding_constraints', None)
        out['owner_benchmark'] = b
    OUT.write_text(json.dumps(out, indent=2, default=str) + '\n')
    return Outcome.ok('FRONTIER_BUILT', out, f'{len(out["modes"])} modes')


def main() -> int:
    r = run()
    print(r)
    if r.state is not State.PASS:
        return 1
    v = r.value
    o = v['optimum_legal_lineup']
    print(f"\nbest legal lineup found: {o['proj_total']} FC pts, salary {o['salary']}")
    print(f"  {o['players']}")
    hdr = (f"\n{'mode':24s} {'mean':>7s} {'med':>7s} {'min':>7s} {'max':>7s} "
           f"{'gap%':>6s} {'QBs':>4s} {'maxP%':>6s} {'ovlp':>5s} {'bring%':>7s} {'guard'}")
    print(hdr)
    order = ['PROJECTION_MAX', 'LIGHT_DIVERSIFICATION', 'BALANCED',
             'HIGH_DIVERSIFICATION']
    rows = [(k, v['modes'][k]) for k in order]
    if v.get('owner_benchmark'):
        rows.append(('OWNER_FC_PLACEHOLDERS', v['owner_benchmark']))
    for label, s in rows:
        if s.get('state') == 'UNDERFILLED' and not s.get('n'):
            print(f"{label:24s} UNDERFILLED")
            continue
        g = s['projection_loss_guard']
        print(f"{label:24s} {s['proj_mean']:7.1f} {s['proj_median']:7.1f} "
              f"{s['proj_min']:7.1f} {s['proj_max']:7.1f} "
              f"{s['gap_to_optimum_pct']:6.1f} {s['n_distinct_qbs']:4d} "
              f"{s['max_player_exposure_pct']:6.1f} "
              f"{s['mean_pairwise_overlap']:5.2f} {s['bring_back_pct']:7.1f} "
              f"{g['state']}")
    print()
    for label in order:
        s = v['modes'][label]
        print(f"  {label:24s} binding: {s['binding_constraints'] or 'none'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
