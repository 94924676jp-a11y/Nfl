#!/usr/bin/env python3.12
"""Historical DFS structure, measured — and what the market is already doing for us.

THE INSTRUCTION AND HOW IT IS HONOURED

"Do NOT hard-code conclusions from these studies directly." So nothing here writes a coefficient
into a model. Each study emits a measurement with an interval and a plain statement of what it does
and does not support, and the consuming code is the joint simulator, which produces these structures
itself or fails to. A study that found stacking valuable would not license a stacking bonus; it
would license checking whether the simulator reproduces it.

WHAT IS MEASURABLE HERE AND WHAT IS NOT

Measurable from the warehouse: stack co-movement, bring-back, correlation by total and by spread,
and how much of a club's scoring view is the market's rather than ours.

NOT measurable, and not guessed: duplication rates and chalk failure. Both need archived contest
ownership and entry lists, which this checkout does not contain. They are reported as BLOCKED with
the request that would close them rather than approximated from a field model whose own ownership
level is uncalibrated.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

PG = _REPO / 'nfl/warehouse/PLAYER_GAME.json'
RH = _REPO / 'nfl/warehouse/ROLE_HISTORY.json'
TG = _REPO / 'nfl/warehouse/TEAM_GAME.json'
OUT = _REPO / 'nfl/research/dfs/DFS_STUDIES.json'

RANK_MEASURE = {'QB': 'pass_attempts', 'RB': 'carries', 'WR': 'targets', 'TE': 'targets'}
MIN_N = 80
BOOT = 500


def _rows(p):
    a = json.loads(p.read_text())
    r = a['rows']
    return r if isinstance(r, list) else list(r.values())


def _q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def _boot_ratio(pairs, fn, seed=61):
    """Bootstrap over GAMES, since players inside a game are not independent."""
    keys = list(pairs)
    if len(keys) < 20:
        return None
    rng = random.Random(seed)
    out = []
    for _ in range(BOOT):
        smp = []
        for _ in keys:
            smp.extend(pairs[keys[rng.randrange(len(keys))]])
        v = fn(smp)
        if v is not None:
            out.append(v)
    if len(out) < BOOT // 3:
        return None
    out.sort()
    return [round(out[int(0.025 * len(out))], 4), round(out[int(0.975 * len(out))], 4)]


def build() -> Outcome:
    for f in (PG, RH, TG):
        if not f.exists():
            return Outcome.blocked('STUDIES_INPUT_ABSENT', f'{f.name} missing', cause=Cause.DATA)
    pg, rh, tg = _rows(PG), _rows(RH), _rows(TG)

    rank = {}
    for r in rh:
        if RANK_MEASURE.get(r.get('position')) != r.get('measure'):
            continue
        if isinstance(r.get('depth_rank'), (int, float)):
            rank[(int(r['season']), int(r['week']), r['player_id'])] = (r['position'],
                                                                       int(r['depth_rank']))
    market = {}
    for r in tg:
        if r.get('total_line') is not None and r.get('club_spread') is not None:
            market[(r['game_id'], r['club'])] = (float(r['total_line']), float(r['club_spread']))

    slot = collections.defaultdict(dict)
    for r in pg:
        pr = rank.get((int(r['season']), int(r['week']), r['player_id']))
        if pr is None or pr[1] > 3:
            continue
        slot[(r['game_id'], r['club'])][f'{pr[0]}{pr[1]}'] = float(r['dk_points_current_rules'])
    clubs = collections.defaultdict(list)
    for gid, club in slot:
        clubs[gid].append(club)

    # ---- STUDY 1: does a stack go big together more often than independence implies? ----------
    def stack_study(a, b, cross=False):
        by_game = collections.defaultdict(list)
        for gid, cl in clubs.items():
            if cross:
                if len(cl) != 2:
                    continue
                c1, c2 = cl
                for x, y in ((c1, c2), (c2, c1)):
                    va, vb = slot[(gid, x)].get(a), slot[(gid, y)].get(b)
                    if va is not None and vb is not None:
                        by_game[gid].append((va, vb))
            else:
                for club in cl:
                    d = slot[(gid, club)]
                    if a in d and b in d:
                        by_game[gid].append((d[a], d[b]))
        flat = [p for g in by_game for p in by_game[g]]
        if len(flat) < MIN_N:
            return {'state': 'NOT_IDENTIFIED_TOO_FEW', 'n': len(flat)}
        qa = _q([x for x, _ in flat], 0.8)
        qb = _q([y for _, y in flat], 0.8)

        def lift(sample):
            if not sample:
                return None
            na = sum(1 for x, _ in sample if x >= qa) / len(sample)
            nb = sum(1 for _, y in sample if y >= qb) / len(sample)
            both = sum(1 for x, y in sample if x >= qa and y >= qb) / len(sample)
            ind = na * nb
            return None if ind <= 0 else both / ind
        point = lift(flat)
        return {
            'state': 'MEASURED',
            'n_pairs': len(flat), 'n_games': len(by_game),
            'threshold_a_p80': round(qa, 3), 'threshold_b_p80': round(qb, 3),
            'joint_top20_lift_over_independence': None if point is None else round(point, 4),
            'ci95_game_blocked': _boot_ratio(by_game, lift),
            'MEANING': ('how many times more often both players clear their own 80th percentile '
                        'together than two independent players would. 1.0 is independence.'),
            'DOES_NOT_SUPPORT': ('any bonus added to a lineup for containing this pair. The '
                                 'simulator either reproduces this lift or it does not, and that '
                                 'is what SIM_VS_MEASURED_CORRELATION checks.'),
        }

    stacks = {
        'QB1+WR1_same_club': stack_study('QB1', 'WR1'),
        'QB1+TE1_same_club': stack_study('QB1', 'TE1'),
        'QB1+RB1_same_club': stack_study('QB1', 'RB1'),
        'WR1+WR2_same_club': stack_study('WR1', 'WR2'),
        'bring_back_QB1+opposing_WR1': stack_study('QB1', 'WR1', cross=True),
        'bring_back_WR1+opposing_WR1': stack_study('WR1', 'WR1', cross=True),
    }

    # ---- STUDY 2: correlation by total and by spread ------------------------------------------
    def cond_corr(a, b, cross, key, bands):
        out = {}
        for lbl, (lo, hi) in bands.items():
            xs, ys, ng = [], [], set()
            for gid, cl in clubs.items():
                for club in cl:
                    m = market.get((gid, club))
                    if m is None:
                        continue
                    v = m[0] if key == 'total' else m[1]
                    if not (lo <= v < hi):
                        continue
                    if cross:
                        if len(cl) != 2:
                            continue
                        other = [c for c in cl if c != club][0]
                        va, vb = slot[(gid, club)].get(a), slot[(gid, other)].get(b)
                    else:
                        va, vb = slot[(gid, club)].get(a), slot[(gid, club)].get(b)
                    if va is not None and vb is not None:
                        xs.append(va)
                        ys.append(vb)
                        ng.add(gid)
            if len(xs) < MIN_N:
                out[lbl] = {'state': 'NOT_IDENTIFIED_TOO_FEW', 'n': len(xs)}
                continue
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            sxx = sum((x - mx) ** 2 for x in xs)
            syy = sum((y - my) ** 2 for y in ys)
            r = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)
                 if sxx > 0 and syy > 0 else None)
            out[lbl] = {'r': None if r is None else round(r, 4), 'n_pairs': n,
                        'n_games': len(ng)}
        return out

    total_bands = {'under_44': (0, 44), '44_to_49': (44, 49), '49_plus': (49, 99)}
    spread_bands = {'underdog_by_4+': (-99, -4), 'close': (-4, 4), 'favoured_by_4+': (4, 99)}
    conditional = {
        'QB1~WR1_by_total': cond_corr('QB1', 'WR1', False, 'total', total_bands),
        'QB1~WR1_by_spread': cond_corr('QB1', 'WR1', False, 'spread', spread_bands),
        'QB1~RB1_by_spread': cond_corr('QB1', 'RB1', False, 'spread', spread_bands),
        'bring_back_by_total': cond_corr('QB1', 'WR1', True, 'total', total_bands),
    }

    # ---- STUDY 3: whose view of club scoring is it, ours or the market's? ---------------------
    # The simulator draws a game total around the market line, so its club-level scoring view IS
    # the market's by construction. Worth stating with a number rather than as an aside, because it
    # bounds where any edge can live: in allocation within a club, not in the club total.
    pts, imp = [], []
    for r in tg:
        if r.get('points') is None or r.get('implied_total') is None:
            continue
        if not isinstance(r['implied_total'], (int, float)):
            continue
        pts.append(float(r['points']))
        imp.append(float(r['implied_total']))
    anchor = {'state': 'NOT_IDENTIFIED'}
    if len(pts) >= 500:
        n = len(pts)
        mp, mi = sum(pts) / n, sum(imp) / n
        spp = sum((x - mp) ** 2 for x in pts)
        sii = sum((x - mi) ** 2 for x in imp)
        r = (sum((a - mp) * (b - mi) for a, b in zip(pts, imp)) / math.sqrt(spp * sii)
             if spp > 0 and sii > 0 else None)
        mae = sum(abs(a - b) for a, b in zip(pts, imp)) / n
        anchor = {
            'state': 'MEASURED', 'n_club_games': n,
            'market_implied_total_vs_actual': {
                'r': None if r is None else round(r, 4),
                'r2': None if r is None else round(r * r, 4),
                'mae': round(mae, 4),
                'bias_actual_minus_implied': round(mp - mi, 4),
                'sd_of_implied': round(math.sqrt(sii / (n - 1)), 4),
                'sd_of_actual': round(math.sqrt(spp / (n - 1)), 4),
            },
            'WHAT_THIS_MEANS_FOR_US': (
                'the joint simulator draws each game total around the market line, so its view of '
                'how many points a club scores IS this view. We are not competing with the market '
                'at club level; we are inheriting it. Any edge therefore has to come from '
                'ALLOCATION inside a club -- who gets the targets, carries and scores -- and from '
                'the joint structure, not from disagreeing about team totals.'),
            'WHAT_IT_DOES_NOT_MEAN': (
                'it is not evidence the market is unbiased or efficient, and it is not a reason to '
                'anchor on the market permanently. An independent team-total model is a legitimate '
                'future experiment; it simply does not exist yet and no current number should be '
                'read as though it did.'),
        }

    blocked = {
        'duplication_rates': {
            'state': 'BLOCKED', 'needs': 'archived contest entry lists', 'request': 'OUT-040',
            'why_not_approximated': (
                'the field model generates 19,999 distinct lineups out of 20,000 because entries '
                'are sampled independently, so its duplication figure is a floor and is already '
                'marked DUPLICATION_USABLE: NO. Studying duplication from it would be studying '
                'the sampler.'),
        },
        'chalk_failure_rates': {
            'state': 'BLOCKED', 'needs': 'archived contest ownership per player-week',
            'request': 'OUT-040',
            'why_not_approximated': (
                'chalk is defined by ownership, and the only ownership here is a structural model '
                'whose level is uncalibrated. Measuring how often chalk fails against modelled '
                'ownership would measure the model.'),
        },
    }

    art = {
        'ARTIFACT': 'DFS_STUDIES',
        'INSTRUCTION_HONOURED': ('no conclusion here is hard-coded into a model. Each study is a '
                                 'measurement the simulator is checked against, never a bonus '
                                 'applied to a lineup.'),
        'INTERVALS': 'bootstrap over whole games; players inside a game are not independent',
        'stack_studies': stacks,
        'conditional_correlation': conditional,
        'market_anchoring': anchor,
        'blocked_studies': blocked,
    }
    OUT.write_text(json.dumps(art, indent=2))
    return Outcome.ok('DFS_STUDIES_MEASURED', value=art)


if __name__ == '__main__':
    o = build()
    print(o.state.value, o.code)
    if not o.value:
        print(o.evidence)
        raise SystemExit(1)
    v = o.value
    print('--- stack lift over independence (both clear their own 80th percentile)')
    for k, s in v['stack_studies'].items():
        if s.get('state') == 'MEASURED':
            print(f"  {k:32s} lift {s['joint_top20_lift_over_independence']:.3f} "
                  f"ci{s['ci95_game_blocked']}  n={s['n_pairs']}")
        else:
            print(f"  {k:32s} {s['state']} n={s.get('n')}")
    print('--- correlation by condition')
    for k, bands in v['conditional_correlation'].items():
        cells = ' '.join(f"{b}={d.get('r')}" for b, d in bands.items())
        print(f"  {k:26s} {cells}")
    a = v['market_anchoring']
    if a.get('state') == 'MEASURED':
        m = a['market_implied_total_vs_actual']
        print(f"--- market implied club total vs actual: r={m['r']} (r2 {m['r2']}), "
              f"MAE {m['mae']}, bias {m['bias_actual_minus_implied']:+.3f}, "
              f"sd implied {m['sd_of_implied']} vs actual {m['sd_of_actual']}, n={a['n_club_games']}")
    print(f"--- blocked: {list(v['blocked_studies'])} (both need OUT-040)")
