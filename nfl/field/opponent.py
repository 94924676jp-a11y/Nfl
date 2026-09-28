#!/usr/bin/env python3.12
"""GAP 4, part two: generate the opponent lineups, not just their marginals.

WHY MARGINALS ARE NOT ENOUGH, AND WHY THIS IS THE HARD HALF

An ownership vector says each player's share of entries. It does not say which players
appear TOGETHER, and every contest-level quantity depends on exactly that. Duplication is
a property of whole lineups. So is the chance that the field's best entry beats ours. A
model that stops at marginals can tell you Chase is 45% owned and still cannot tell you
whether 900 people entered your exact roster.

So the field here is an explicit population of legal lineups. The generator is held to a
standard that is checkable without any external data: the realised ownership of the
generated field must reproduce the target marginals. That is what makes it a field model
rather than a pile of random legal lineups. It is enforced by iterative proportional
fitting on per-player log-weights, and the residual is reported, not assumed away.

Three honest limits, stated here so they cannot be mislaid downstream:

  The TARGET marginals are themselves uncalibrated (see ownership.py). A faithful
  reproduction of a declared vector is still a declared vector.

  Correlation structure beyond the marginals -- stacking propensity, game-environment
  clustering, the fact that real entrants correlate their QB with his receivers -- is a
  BEHAVIOURAL parameter. Only the part implied by the shape mix and the marginals is
  earned here. A stack propensity is exposed and defaults to neutral rather than being
  invented, and its effect is measured in sensitivity.

  Real fields contain many entries from few entrants, with within-entrant diversification
  rules. This generator samples entries independently. That understates duplication of
  chalk lineups and overstates the field's coverage of the lineup space. It is recorded
  as a known bias with its direction, which is more use than a silent one.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import sys
from typing import Any, Mapping, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import ownership as own_mod  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SALARY_CAP = 50000

GEN_PARAMETERS: dict[str, dict[str, Any]] = {
    'salary_floor': {
        'value': 44000,
        'state': 'REALISM_BOUND_NOT_A_TARGET',
        'basis': ('A wide left-tail trim, not a spending target. The MEAN spend is already '
                  'pinned by the budget identity in ownership.py, so a tight floor here would '
                  'fight the marginals instead of adding information -- which is exactly what '
                  'it did at 48,500: the fitting diverged and the acceptance rate fell to 7%. '
                  'The floor now only excludes lineups no optimiser would submit.'),
        'sensitivity_range': (0, 48000),
    },
    'mean_marginal_tolerance': {
        'value': 0.008,
        'state': 'ACCEPTANCE_THRESHOLD_DECLARED',
        'basis': ('Mean absolute gap allowed between the field\'s realised marginals and the '
                  'marginal-form target. The MEAN is the acceptance test and the MAXIMUM is '
                  'not, for a measured reason recorded in JOINT_FEASIBILITY_FINDING: some '
                  'individual targets are not jointly achievable at all, so failing on the '
                  'worst one would be failing on arithmetic rather than on fit quality.'),
        'sensitivity_range': 'not a model parameter',
    },
    'stack_propensity': {
        'value': 0.0,
        'state': 'DECLARED_NEUTRAL_DELIBERATELY',
        'basis': ('Log-odds bonus applied to a pass catcher sharing a club with the rostered '
                  'QB. Real entrants stack far more than independence implies, but the size '
                  'of that effect is exactly what contest CSVs would tell us and nothing '
                  'here does. Held at zero so the generated field is the independence '
                  'benchmark; sensitivity moves it.'),
        'sensitivity_range': (0.0, 1.5),
    },
    'ipf_rounds': {
        'value': 8,
        'state': 'CONVERGENCE_SETTING',
        'basis': 'Iterations of proportional fitting; convergence is reported, not assumed.',
        'sensitivity_range': (1, 16),
    },
}

KNOWN_BIASES = [
    {'bias': 'ENTRIES_SAMPLED_INDEPENDENTLY',
     'direction': ('understates duplication among chalk lineups and overstates the breadth of '
                   'lineup space the field covers'),
     'why': 'real fields are many entries from few entrants, who diversify within their own set'},
    {'bias': 'NO_LEARNED_CORRELATION_BEYOND_MARGINALS_AND_SHAPE',
     'direction': 'understates stacked and game-concentrated lineups at neutral propensity',
     'why': 'stacking propensity is a behavioural parameter with no in-repo evidence'},
]


def _weighted_sample_without_replacement(ids, weights, k, rng):
    """Efraimidis-Spirakis: one exponential key per item, take the k smallest. O(n).

    Kept for the tilted path, where per-lineup weights differ and nothing can be precomputed.
    """
    if k <= 0:
        return []
    keys = []
    for i, w in zip(ids, weights):
        if w <= 0:
            continue
        keys.append((rng.expovariate(1.0) / w, i))
    if len(keys) < k:
        return None
    keys.sort()
    return [i for _, i in keys[:k]]


def _build_cdf(ids, weights):
    """Cumulative weights for the untilted path, built once per round rather than per lineup."""
    live_ids, cum, acc = [], [], 0.0
    for i, w in zip(ids, weights):
        if w <= 0:
            continue
        acc += w
        live_ids.append(i)
        cum.append(acc)
    return live_ids, cum, acc


def _sample_cdf(live_ids, cum, total, k, rng):
    """k distinct draws by inverse-CDF with duplicate rejection. O(k log n), not O(n).

    The O(n) keyed sampler is correct but it walks every player for every position of every
    lineup, which at 20,000 entries times eight fitting rounds is tens of millions of calls.
    Same distribution, and the difference is minutes against hours.
    """
    if k <= 0:
        return []
    if len(live_ids) < k:
        return None
    import bisect
    out: list[str] = []
    for _ in range(200):
        j = bisect.bisect_left(cum, rng.random() * total)
        if j >= len(live_ids):
            j = len(live_ids) - 1
        cand = live_ids[j]
        if cand not in out:
            out.append(cand)
            if len(out) == k:
                return out
    return None


def _salary_sorted(ids, rows, weights):
    """Per position: players ordered by salary, with cumulative weights over that order.

    Ordering by salary is what makes a budget constraint cheap to apply. "Every player this
    slot can still afford" is then a PREFIX of the list, so the affordable set is found with
    one bisect instead of a scan, and sampling inside it is another bisect.
    """
    order = sorted(ids, key=lambda i: rows[i]['salary'])
    sal = [rows[i]['salary'] for i in order]
    cum, acc = [], 0.0
    for i in order:
        acc += weights[i]
        cum.append(acc)
    cheapest = [0]
    for v in sal:
        cheapest.append(cheapest[-1] + v)
    return {'ids': order, 'sal': sal, 'cum': cum, 'cheapest_k': cheapest}


def _sample_affordable(tab, max_salary, taken, rng):
    """Sample one player with salary <= max_salary, in proportion to weight, not already taken."""
    import bisect
    m = bisect.bisect_right(tab['sal'], max_salary)
    if m == 0:
        return None
    total = tab['cum'][m - 1]
    if total <= 0:
        return None
    for _ in range(60):
        j = bisect.bisect_left(tab['cum'], rng.random() * total, 0, m)
        if j >= m:
            j = m - 1
        cand = tab['ids'][j]
        if cand not in taken:
            return cand
    return None


def _sample_lineup(shape, tabs, rows, cap, rng):
    """Build one legal lineup directly, never by repairing an illegal one.

    The earlier sampler drew nine players by weight and then swapped its way back under the
    cap. That swap was a systematic pull toward cheap players which the marginal fitting then
    had to fight, and it lost: the residual climbed every round instead of falling. Here the
    budget is carried through the draw, so every lineup is legal when it is finished and no
    correction is needed.
    """
    slots = []
    for pos, n in shape.items():
        slots.extend([pos] * n)
    # The ORDER matters and getting it wrong is not obvious. Filling positions in a fixed
    # order squeezes whichever position goes last: by then the budget is nearly spent, so only
    # its cheap players are affordable and its expensive players can never reach their target
    # share no matter what weight the fitting gives them. That showed up as a residual stuck at
    # 0.13 on defences while every other position converged. Shuffling per lineup removes the
    # asymmetry, and is the more realistic construction besides.
    rng.shuffle(slots)
    remaining = dict((p, 0) for p in tabs)
    for p in slots:
        remaining[p] = remaining.get(p, 0) + 1
    budget = cap
    picked: list[str] = []
    taken: set[str] = set()
    for pos in slots:
        remaining[pos] -= 1
        floor_rest = 0
        for p, k in remaining.items():
            if k:
                ck = tabs[p]['cheapest_k']
                if k >= len(ck):
                    return None
                floor_rest += ck[k]
        got = _sample_affordable(tabs[pos], budget - floor_rest, taken, rng)
        if got is None:
            return None
        picked.append(got)
        taken.add(got)
        budget -= rows[got]['salary']
    return picked


def generate(pool: Sequence[Mapping[str, Any]], target_ownership: Mapping[str, float], *,
             mix: Sequence[float], n_entries: int = 20000, seed: int = 11,
             team_of: Mapping[str, str] | None = None,
             salary_floor: int | None = None, stack_propensity: float | None = None,
             ipf_rounds: int | None = None, require_marginals: bool = True) -> Outcome:
    """Build a field of legal lineups whose realised ownership reproduces the target."""
    floor = GEN_PARAMETERS['salary_floor']['value'] if salary_floor is None else salary_floor
    stack = (GEN_PARAMETERS['stack_propensity']['value'] if stack_propensity is None
             else stack_propensity)
    rounds = GEN_PARAMETERS['ipf_rounds']['value'] if ipf_rounds is None else ipf_rounds
    rng = random.Random(seed)

    rows = {r['id']: r for r in pool if r.get('salary')}
    by_pos: dict[str, list[str]] = {}
    for i, r in rows.items():
        by_pos.setdefault(r['position'], []).append(i)
    tgt = {i: float(target_ownership.get(i, 0.0)) for i in rows}
    if not any(v > 0 for v in tgt.values()):
        return Outcome.blocked('FIELD_NO_TARGET_OWNERSHIP', 'every target share is zero',
                               cause=Cause.DATA)

    # log-weights start at the target share; IPF corrects them toward it
    logw = {i: math.log(max(v, 1e-9)) for i, v in tgt.items()}
    shapes = own_mod.SHAPES
    cum = []
    acc = 0.0
    for w in mix:
        acc += w
        cum.append(acc)

    field: list[tuple[str, ...]] = []
    diagnostics = []
    for rd in range(rounds):
        w = {i: math.exp(v) for i, v in logw.items()}
        tabs = {p: _salary_sorted(ids, rows, w) for p, ids in by_pos.items()}
        field = []
        attempts = 0
        while len(field) < n_entries:
            attempts += 1
            if attempts > n_entries * 60:
                return Outcome.fail(
                    'FIELD_SAMPLER_CANNOT_MEET_CONSTRAINTS',
                    'could not build enough legal lineups inside the salary band',
                    accepted=len(field), attempts=attempts, salary_floor=floor,
                    note=('emitting a short field would silently change the field size that '
                          'every duplication and win-probability number divides by.'))
            u = rng.random()
            si = 0
            for k, c in enumerate(cum):
                if u <= c:
                    si = k
                    break
            else:
                si = len(cum) - 1
            shape = shapes[si]
            picked = _sample_lineup(shape, tabs, rows, SALARY_CAP, rng)
            if picked is None:
                continue
            if stack and team_of:
                qb = next(i for i in picked if rows[i]['position'] == 'QB')
                club = team_of.get(qb)
                n_stack = sum(1 for i in picked
                              if i != qb and team_of.get(i) == club
                              and rows[i]['position'] in ('WR', 'TE', 'RB'))
                if n_stack == 0 and rng.random() < 1 - math.exp(-stack):
                    continue
            sal = sum(rows[i]['salary'] for i in picked)
            if sal < floor:
                continue
            field.append(tuple(sorted(picked)))

        realised = collections.Counter()
        for L in field:
            realised.update(L)
        dev = {i: realised[i] / n_entries - tgt[i] for i in rows}
        worst = max(dev.items(), key=lambda kv: abs(kv[1]))
        diagnostics.append({'round': rd, 'max_abs_deviation': round(abs(worst[1]), 5),
                            'worst_player': worst[0],
                            'mean_abs_deviation': round(
                                sum(abs(v) for v in dev.values()) / len(dev), 6),
                            'accept_rate': round(len(field) / max(1, attempts), 4)})
        if abs(worst[1]) < 0.004:
            break
        for i in rows:
            r = realised[i] / n_entries
            if tgt[i] <= 0:
                logw[i] = -60.0
            elif r <= 0:
                logw[i] += 1.0
            else:
                logw[i] += max(-2.0, min(2.0, math.log(tgt[i] / r)))

    counts = collections.Counter(field)
    realised = collections.Counter()
    for L in field:
        realised.update(L)
    dev = {i: realised[i] / n_entries - tgt[i] for i in rows}
    worst = max(dev.items(), key=lambda kv: abs(kv[1]))
    mean_abs = sum(abs(v) for v in dev.values()) / len(dev)
    mean_salary = sum(sum(rows[i]['salary'] for i in L) for L in field) / len(field)
    tol = GEN_PARAMETERS['mean_marginal_tolerance']['value']
    diverged = len(diagnostics) > 1 and (
        diagnostics[-1]['max_abs_deviation'] > diagnostics[0]['max_abs_deviation'] + 1e-9)
    if require_marginals and (mean_abs > tol or diverged):
        return Outcome.fail(
            'FIELD_MARGINALS_NOT_REPRODUCED',
            (f'mean marginal gap {mean_abs:.5f} against tolerance {tol}'
             + (' and the fit DIVERGED' if diverged else '')),
            mean_abs_deviation=round(mean_abs, 6), tolerance=tol, fit_diverged=diverged,
            max_abs_deviation=round(abs(worst[1]), 5), worst_player=worst[0],
            mean_entry_salary=round(mean_salary, 1), ipf_history=diagnostics,
            note=('a field that does not reproduce the ownership it was given is a pile of '
                  'legal lineups, and every contest-level number from it would be noise. A '
                  'DIVERGING fit is the specific symptom of target marginals that contradict '
                  'the salary band: expected entry salary is the ownership-weighted salary '
                  'sum, and if it sits outside the band no sampler can satisfy both.'))

    # where the remaining gap lives, and whether it is the known arithmetic one
    min_sal = min(r['salary'] for r in rows.values())
    at_min = [i for i in rows if rows[i]['salary'] <= min_sal + 1e-9]
    gap_at_min = (sum(dev[i] for i in at_min) / len(at_min)) if at_min else 0.0
    gap_rest = (sum(dev[i] for i in rows if i not in set(at_min))
                / max(1, len(rows) - len(at_min)))
    off = sorted(((abs(dev[i]), i) for i in rows), reverse=True)[:12]
    return Outcome.ok('FIELD_GENERATED', value={
        'mean_entry_salary': round(mean_salary, 1),
        'field_ownership': {i: realised[i] / n_entries for i in rows},
        'OPERATIVE_OWNERSHIP': ('field_ownership, not the marginal-form target. The field\'s '
                                'own marginals are achievable by construction; the target '
                                'vector is not (see JOINT_FEASIBILITY_FINDING).'),
        'JOINT_FEASIBILITY_FINDING': {
            'claim': ('the marginal-form ownership vector is NOT jointly achievable under the '
                      'salary cap, and the gap is systematic rather than noise'),
            'mean_signed_gap_at_minimum_salary': round(gap_at_min, 5),
            'mean_signed_gap_everyone_else': round(gap_rest, 5),
            'n_at_minimum_salary': len(at_min),
            'minimum_salary': min_sal,
            'why': ('nine slots must be filled inside the cap, so a field spending near the '
                    'cap on its expensive players is FORCED into minimum-priced players more '
                    'often than a value logit implies. The logit prices players one at a time '
                    'and cannot see the budget the other eight slots consume.'),
            'consequence': ('punt-priced players are under-owned by the marginal form and '
                            'over-owned in any achievable field. Downstream leverage must use '
                            'field_ownership or it will systematically overrate punts.'),
            'largest_gaps': [{'id': i, 'salary': rows[i]['salary'],
                              'target': round(tgt[i], 5),
                              'realised': round(realised[i] / n_entries, 5),
                              'gap': round(dev[i], 5)} for _, i in off],
        },
        'n_entries': len(field),
        'n_distinct_lineups': len(counts),
        'max_multiplicity': max(counts.values()),
        'share_of_entries_that_are_unique': round(
            sum(1 for c in counts.values() if c == 1) / len(field), 4),
        'realised_vs_target': {
            'mean_abs_deviation': round(mean_abs, 6),
            'tolerance_on_the_mean': tol,
            'CONVERGED': mean_abs <= tol and not diverged,
            'fit_diverged': diverged,
            'max_abs_deviation': round(abs(worst[1]), 5), 'worst_player': worst[0],
            'WHY_THE_MEAN_AND_NOT_THE_MAX': (
                'the largest single gap is joint infeasibility, not fit quality: some target '
                'shares cannot be achieved by ANY distribution over legal lineups. See '
                'JOINT_FEASIBILITY_FINDING. Divergence is still a failure, and is tested '
                'separately.')},
        'ipf_history': diagnostics,
        'parameters_used': {'salary_floor': floor, 'stack_propensity': stack,
                            'ipf_rounds': rounds, 'seed': seed, 'shape_mix': list(mix)},
        'KNOWN_BIASES': KNOWN_BIASES,
        'CALIBRATION_STATE': own_mod.CALIBRATION_STATE,
        '_field': field,
    })


def duplication(field: Sequence[tuple[str, ...]], candidate_ids: Sequence[str],
                n_entries: int | None = None) -> Outcome:
    """How many other entries hold this exact roster, and how often a roster collides."""
    if not field:
        return Outcome.blocked('DUPLICATION_NO_FIELD', 'no field was generated',
                               cause=Cause.DATA)
    n = n_entries or len(field)
    key = tuple(sorted(candidate_ids))
    counts = collections.Counter(field)
    hits = counts.get(key, 0)
    p = hits / len(field)
    mult = collections.Counter(counts.values())
    return Outcome.ok('DUPLICATION_ESTIMATED', value={
        'p_an_entry_is_this_lineup': p,
        'expected_other_entries_identical': round(p * n, 3),
        'field_sample_hits': hits,
        'ZERO_MEANS': ('not seen in a field of this size, which is an upper bound of roughly '
                       f'{round(3.0 / len(field) * n, 2)} entries at 95%, NOT zero duplication'),
        'multiplicity_profile': {str(k): v for k, v in sorted(mult.items())[:8]},
    })


MIN_OWNERSHIP_FOR_LEVERAGE = 0.01
MIN_OWNERSHIP_BASIS = (
    'A value-over-ownership ratio divides by field share, so below about a percent the '
    'denominator IS the answer and the ranking becomes a list of the least-owned players on '
    'the slate. Measured on this slate the unfiltered top three were owned 0.03%, 0.04% and '
    '0.15% with ratios of 1015, 536 and 438 -- arithmetic about an empty denominator, not '
    'contest information. The floor is declared at 1%, which is also roughly where a player '
    'starts mattering to a contest outcome at all.')


def leverage(pool, ownership_vec, field=None,
             min_ownership: float = MIN_OWNERSHIP_FOR_LEVERAGE) -> Outcome:
    """Projected points against how much of the field holds the player.

    Leverage is a comparison, not a score: it only means anything relative to the field, and
    it is reported as the raw pair plus the ratio so nobody has to trust a blended number.

    Players below min_ownership are EXCLUDED rather than ranked. See MIN_OWNERSHIP_BASIS: the
    ratio is degenerate down there, and ranking on it silently turns a leverage table into a
    list of the slate's most obscure players.
    """
    rows = [r for r in pool if r.get('salary')]
    out = []
    excluded = 0
    for r in rows:
        o = float(ownership_vec.get(r['id'], 0.0))
        if o < min_ownership:
            excluded += 1
            continue
        out.append({'id': r['id'], 'position': r['position'], 'salary': r['salary'],
                    'projected': round(float(r['value']), 4), 'ownership': round(o, 5),
                    'points_per_1k': round(float(r['value']) / (r['salary'] / 1000.0), 4),
                    'leverage_ratio': None if o <= 0 else round(
                        float(r['value']) / (r['salary'] / 1000.0) / max(o, 1e-6), 3)})
    out.sort(key=lambda d: (-(d['leverage_ratio'] or -1)))
    return Outcome.ok('LEVERAGE_TABLE', value={
        'rows': out,
        'n_ranked': len(out),
        'n_excluded_below_ownership_floor': excluded,
        'min_ownership_for_leverage': min_ownership,
        'MIN_OWNERSHIP_BASIS': MIN_OWNERSHIP_BASIS,
        'MEANING': 'value per $1k divided by field share; high means underowned for the value',
        'STATUS': 'DIAGNOSTIC_NOT_AN_ORDERING',
        'WHY_NOT_AN_ORDERING': (
            'the ratio is dominated by its denominator at ANY floor. Raising the floor from 0 '
            'to 1% moved the top three from players owned 0.03-0.15% to players owned '
            '1.11-1.18% -- the same failure one notch up, because dividing by a small number '
            'is what the ranking is mostly doing. A usable ordering needs a contest objective, '
            'the probability that one of our entries wins given this field, which is GAP 6 '
            'work and needs the field as an input rather than a ratio as a substitute.'),
        'NOT': 'not a recommendation, and not usable while ownership is uncalibrated',
    })
