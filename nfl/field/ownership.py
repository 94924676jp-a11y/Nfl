#!/usr/bin/env python3.12
"""GAP 4, part one: how much of the field owns each player.

WHAT THIS IS AND, MORE IMPORTANTLY, WHAT IT IS NOT

An ownership model is normally FITTED: you keep the contest CSVs you entered, they carry
each player's %Drafted, and you regress that on projection, salary and slate structure.
This checkout has no archived contest ownership at all. The research packet says the same
thing in its own words -- field labels come "from self-archived contest CSVs" -- and none
were archived. Published work on field generation (Haugh & Singal) gives the problem
shape but no coefficients, and the commercial products state plainly that their pOWN
formulas are unpublished.

So this module is declared STRUCTURAL and NOT CALIBRATED, and it says so in every
artifact it writes. It is not a measurement of ownership. It is a generator with a stated
functional form whose parameters are declared priors, and its defensibility rests on
three things that ARE checkable inside this repository:

  1. AN EXACT ACCOUNTING IDENTITY. Ownership is not a free vector. Across all players the
     shares must sum to exactly nine roster slots per entry, and no player may exceed
     100% of entries. Both hold here by construction, not by hope: the within-position
     scaling is solved by bisection against the cap, and infeasibility BLOCKS.

  2. A MEASURED SHAPE MIX. The per-position slot counts are not constants -- DK's FLEX
     makes them depend on how the field splits between the three legal shapes. That split
     is measured from the 48 lineups a mainstream tool actually produced for this slate
     (structure only: which positions were rostered, never that tool's projections).

  3. SENSITIVITY IN PLACE OF CALIBRATION. Since the steepness cannot be fitted, the
     honest question is not "is it right" but "does anything we decide change across the
     range it could plausibly take". That is measured in sensitivity() and reported. If a
     decision is stable across the range, an uncalibrated field is still usable for it. If
     it is not, the decision is BLOCKED pending archived contest data, and the request for
     that data is OUT-040.

Ownership rises with projected value (points per $1,000) because that is the one
qualitative regularity every published description agrees on. The steepness is a prior,
not a fit. There is deliberately no second free parameter: a salary tilt is exposed at
zero so sensitivity can move it, because inventing a coefficient we cannot estimate is
the failure this project logs as a bug.
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from typing import Any, Iterable, Mapping, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

# --- the three legal DK Classic shapes, as counts of the FLEX-eligible positions -------
SHAPES: tuple[Mapping[str, int], ...] = (
    {'QB': 1, 'RB': 3, 'WR': 3, 'TE': 1, 'DST': 1},
    {'QB': 1, 'RB': 2, 'WR': 4, 'TE': 1, 'DST': 1},
    {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 2, 'DST': 1},
)
SLOTS_PER_ENTRY = 9

# --- declared parameters, each with the reason it has the value it has -----------------
PARAMETERS: dict[str, dict[str, Any]] = {
    'value_beta': {
        'value': 1.25,
        'state': 'DECLARED_PRIOR_NOT_FITTED',
        'basis': ('Steepness of ownership in position-standardised points per $1,000. No '
                  'archived contest ownership exists here to fit it. 1.25 places a +2SD '
                  'value player near 12x the entry rate of a -1SD player, which reproduces '
                  'the order of magnitude every public field description implies without '
                  'claiming a measurement.'),
        'sensitivity_range': (0.6, 2.2),
    },
    'salary_tilt': {
        'value': 'SOLVED_FROM_BUDGET_IDENTITY',
        'state': 'DERIVED_NOT_DECLARED',
        'basis': ('Originally declared at zero because "the field over-rosters expensive '
                  'players" is a real regularity with no coefficient available. It turned out '
                  'not to need one. Expected lineup salary is an identity -- the ownership-'
                  'weighted salary sum -- so the tilt is SOLVED by bisection to hit the '
                  'field salary usage below. That makes it a derivation rather than a guess, '
                  'and it is what caught the contradiction described in field_salary_usage.'),
        'sensitivity_range': 'not a free parameter; moves only with field_salary_usage',
    },
    'field_salary_usage': {
        'value': 49200,
        'state': 'DECLARED_PRIOR_NOT_FITTED',
        'basis': ('Target expected salary of a field entry. Field entries are built by '
                  'optimisers, which spend the cap, so the mean lands just under it. Declared, '
                  'because measuring it needs contest CSVs.\n'
                  'THIS PARAMETER EXISTS BECAUSE OF A CONTRADICTION THE BUILD FOUND. A pure '
                  'value logit implied E[lineup salary] = 42,618 against a generator that was '
                  'told field entries spend at least 48,500. Those two statements cannot both '
                  'hold, and the symptom was the fitting DIVERGING -- residual climbing 0.353 '
                  'to 0.518 over eight rounds while the acceptance rate fell from 0.71 to '
                  '0.07. The generator was being asked to reproduce marginals that describe a '
                  'cheaper field than the one it was required to build.'),
        'sensitivity_range': (47000, 49900),
    },
    'max_ownership': {
        'value': 1.0,
        'state': 'STRUCTURAL_CEILING',
        'basis': ('A player cannot appear in more than 100% of entries. This is arithmetic, '
                  'not a preference, and it is what makes the within-position scaling a '
                  'capped water-filling problem rather than a normalisation.'),
        'sensitivity_range': (0.75, 1.0),
    },
    'shape_mix': {
        'value': None,  # measured; filled by measure_shape_mix()
        'state': 'MEASURED_FROM_48_TOOL_LINEUPS',
        'basis': ('Per-position expected slots depend on the FLEX split. Measured from the '
                  'positional composition of the 48 placeholder lineups for this slate. '
                  'STRUCTURE ONLY -- which positions were rostered. The external tool\'s '
                  'projections are not read here and must never reach a projection.'),
        'sensitivity_range': 'uniform over the three shapes, and each shape pure',
    },
}

CALIBRATION_STATE = 'NOT_CALIBRATED_NO_ARCHIVED_CONTEST_OWNERSHIP'
DATA_REQUEST = 'OUT-040'

FC48 = _REPO / 'nfl/dfs/salaries/raw/OWNER_PLACEHOLDERS_FC_48_AUDIT_2026W3.csv'


# ======================================================================================
# the measured part
# ======================================================================================
def measure_shape_mix(v1_rows: Mapping[str, Mapping[str, Any]] | None = None) -> Outcome:
    """Measure the FLEX split from the 48 placeholder lineups. Structure only.

    Reads only the roster composition. The file is opened read-only and never written:
    it is the owner's entry record and is a placeholder set, not a recommendation.
    """
    if not FC48.exists():
        return Outcome.blocked('SHAPE_MIX_SOURCE_ABSENT', cause=Cause.EMPTY_INPUT, path=str(FC48))
    if v1_rows is None:
        art = json.loads((_REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json').read_text())
        v1_rows = art['rows']
    pos_by_name: dict[str, str] = {}
    for r in v1_rows.values():
        pos_by_name.setdefault(_norm(r['name']), r['position'])

    import csv
    counts: dict[tuple, int] = {}
    unmatched: set[str] = set()
    n_lineups = 0
    with FC48.open(newline='') as fh:
        for row in csv.DictReader(fh):
            raw = (row.get('Players') or '').strip()
            if not raw:
                continue
            n_lineups += 1
            tally = {'QB': 0, 'RB': 0, 'WR': 0, 'TE': 0, 'DST': 0}
            for tok in raw.split('|'):
                tok = tok.strip()
                if not tok:
                    continue
                p = pos_by_name.get(_norm(tok))
                if p is None:
                    # club nicknames appear as the defence slot
                    p = 'DST' if _looks_like_club(tok, v1_rows) else None
                if p is None:
                    unmatched.add(tok)
                    continue
                tally[p] += 1
            key = tuple(sorted(tally.items()))
            counts[key] = counts.get(key, 0) + 1

    if n_lineups == 0:
        return Outcome.fail('SHAPE_MIX_NO_LINEUPS_READ', evidence={'path': str(FC48)})

    legal, illegal = {}, {}
    for key, c in counts.items():
        d = dict(key)
        if any(d == dict(s) for s in SHAPES):
            legal[key] = c
        else:
            illegal[key] = c
    n_legal = sum(legal.values())
    if n_legal == 0:
        return Outcome.fail(
            'SHAPE_MIX_NO_LEGAL_SHAPE_RECOGNISED',
            evidence={'compositions_seen': {str(dict(k)): v for k, v in counts.items()},
                      'unmatched_tokens': sorted(unmatched)[:12],
                      'note': ('every lineup read as an illegal shape, which means the name '
                               'join failed rather than that the lineups are illegal')})
    mix = []
    for s in SHAPES:
        key = tuple(sorted(s.items()))
        mix.append(legal.get(key, 0) / n_legal)
    return Outcome.ok('SHAPE_MIX_MEASURED', value={
        'mix': mix,
        'n_lineups_read': n_lineups,
        'n_legal': n_legal,
        'n_unrecognised_composition': sum(illegal.values()),
        'unmatched_tokens': sorted(unmatched)[:12],
        'SOURCE': 'positional composition of 48 placeholder lineups, structure only',
        'NOT': 'not the contest field, and not that tool\'s projections',
    })


def _norm(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum() or ch == ' ':
            out.append(ch)
    return ' '.join(''.join(out).split())


def _looks_like_club(tok: str, v1_rows) -> bool:
    t = _norm(tok)
    for r in v1_rows.values():
        if r['position'] == 'DST' and (t in _norm(r['name']) or _norm(r['name']) in t):
            return True
    return False


def expected_slots(mix: Sequence[float]) -> dict[str, float]:
    """Per-position expected slots under a shape mix. Sums to exactly 9 for any mix."""
    out = {'QB': 0.0, 'RB': 0.0, 'WR': 0.0, 'TE': 0.0, 'DST': 0.0}
    for w, shape in zip(mix, SHAPES):
        for p, n in shape.items():
            out[p] += w * n
    return out


# ======================================================================================
# the capped scaling -- an exact solve, not a normalisation
# ======================================================================================
def _waterfill(weights: Sequence[float], target: float, cap: float) -> tuple[list[float], float]:
    """Find k with sum(min(cap, k*w)) == target. Monotone in k, so bisect.

    This is the step a plain normalisation gets wrong. Scaling to hit the slot total pushes
    the chalk above 100% ownership, which is not a small error -- it is an impossible one,
    and it silently steals ownership from everyone else.
    """
    n = len(weights)
    if target > cap * n + 1e-12:
        raise ValueError(f'target {target} exceeds cap*n {cap * n}')
    tot = sum(weights)
    if tot <= 0:
        return [target / n] * n, float('nan')
    lo, hi = 0.0, target / min(w for w in weights if w > 0) + 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        s = sum(min(cap, mid * w) for w in weights)
        if s < target:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    return [min(cap, k * w) for w in weights], k


def _tilted_ownership(rows_by_pos, slots, beta, tau, cap):
    """Water-filled shares under a value tilt beta and a salary tilt tau."""
    own, detail = {}, {}
    for pos, rows in rows_by_pos.items():
        vals = [max(0.0, float(r['value'])) / (r['salary'] / 1000.0) for r in rows]
        m = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - m) ** 2 for v in vals) / max(1, len(vals) - 1)) or 1.0
        sal = [r['salary'] / 1000.0 for r in rows]
        ms = sum(sal) / len(sal)
        sds = math.sqrt(sum((s - ms) ** 2 for s in sal) / max(1, len(sal) - 1)) or 1.0
        w = [math.exp(beta * (v - m) / sd + tau * (s - ms) / sds) for v, s in zip(vals, sal)]
        shares, k = _waterfill(w, slots[pos], cap)
        for r, sh in zip(rows, shares):
            own[r['id']] = sh
        detail[pos] = {'n': len(rows), 'slots': round(slots[pos], 4),
                       'n_at_cap': sum(1 for s in shares if s >= cap - 1e-9),
                       'scale_k': None if k != k else round(k, 6),
                       'max_share': round(max(shares), 4)}
    return own, detail


def _expected_salary(own, salary_of):
    """E[salary of a field entry]. An identity: sum of share times salary over all players."""
    return sum(own[i] * salary_of[i] for i in own)


def ownership(pool: Sequence[Mapping[str, Any]], *, mix: Sequence[float],
              value_beta: float | None = None, budget: float | None = None,
              max_ownership: float | None = None) -> Outcome:
    """Ownership share per player: expected fraction of entries rostering them.

    pool rows need id, position, salary, value (unconditional projected points -- the field
    sees the same injury news we do, so a doubtful player should be dampened here too).

    Two identities are enforced rather than hoped for. Shares sum to exactly nine slots per
    entry, and the ownership-weighted salary equals the field's expected spend. The second is
    what the salary tilt is solved against: it is a derivation, not a coefficient.
    """
    beta = PARAMETERS['value_beta']['value'] if value_beta is None else value_beta
    cap = PARAMETERS['max_ownership']['value'] if max_ownership is None else max_ownership
    bud = PARAMETERS['field_salary_usage']['value'] if budget is None else budget

    by_pos: dict[str, list[Mapping[str, Any]]] = {}
    salary_of: dict[str, float] = {}
    for r in pool:
        if not r.get('salary'):
            continue
        by_pos.setdefault(r['position'], []).append(r)
        salary_of[r['id']] = float(r['salary'])
    slots = expected_slots(mix)

    short = {p: (s, len(by_pos.get(p, []))) for p, s in slots.items()
             if s > cap * len(by_pos.get(p, [])) + 1e-12}
    if short:
        return Outcome.blocked(
            'OWNERSHIP_INFEASIBLE_NOT_ENOUGH_PLAYERS',
            'the field cannot fill the slate from this pool',
            cause=Cause.DATA,
            positions_short_of_slots={p: {'slots_needed': s, 'players': n}
                                      for p, (s, n) in short.items()},
            note=('this is a pool defect. Returning a normalised vector anyway would hide it.'))

    # solve the salary tilt against the budget identity. E[salary] rises monotonically in tau.
    lo, hi = -8.0, 8.0
    o_lo, _ = _tilted_ownership(by_pos, slots, beta, lo, cap)
    o_hi, _ = _tilted_ownership(by_pos, slots, beta, hi, cap)
    s_lo, s_hi = _expected_salary(o_lo, salary_of), _expected_salary(o_hi, salary_of)
    if not (s_lo - 1e-9 <= bud <= s_hi + 1e-9):
        return Outcome.blocked(
            'OWNERSHIP_BUDGET_UNREACHABLE',
            f'no salary tilt in [{lo}, {hi}] gives an expected entry salary of {bud}',
            cause=Cause.DATA,
            budget_target=bud, reachable_range=[round(s_lo, 1), round(s_hi, 1)],
            note=('the pool cannot support a field spending this much (or this little), so '
                  'either the budget or the pool is wrong. Silently taking the nearest '
                  'reachable value would make every downstream salary number a fiction.'))
    tau = 0.0
    for _ in range(80):
        tau = (lo + hi) / 2
        o_mid, _ = _tilted_ownership(by_pos, slots, beta, tau, cap)
        if _expected_salary(o_mid, salary_of) < bud:
            lo = tau
        else:
            hi = tau
    tau = (lo + hi) / 2
    own, detail = _tilted_ownership(by_pos, slots, beta, tau, cap)
    exp_sal = _expected_salary(own, salary_of)

    total = sum(own.values())
    if abs(total - SLOTS_PER_ENTRY) > 1e-6:
        return Outcome.fail('OWNERSHIP_ACCOUNTING_IDENTITY_VIOLATED',
                            'nine roster slots per entry is an identity, not a target',
                            sum_of_shares=total, must_equal=SLOTS_PER_ENTRY)
    if any(v > cap + 1e-9 for v in own.values()):
        return Outcome.fail('OWNERSHIP_EXCEEDS_CEILING',
                            'a player cannot appear in more than 100% of entries',
                            max=max(own.values()), cap=cap)
    if abs(exp_sal - bud) > 50:
        return Outcome.fail('OWNERSHIP_BUDGET_IDENTITY_NOT_MET',
                            'the solved tilt does not reproduce the declared field spend',
                            achieved=round(exp_sal, 1), target=bud)

    return Outcome.ok('OWNERSHIP_STRUCTURAL', value={
        'ownership': own,
        'by_position': detail,
        'sum_of_shares': round(total, 9),
        'expected_entry_salary': round(exp_sal, 1),
        'salary_tilt_solved': round(tau, 5),
        'expected_slots': {p: round(s, 4) for p, s in slots.items()},
        'parameters_used': {'value_beta': beta, 'field_salary_usage': bud,
                            'max_ownership': cap, 'shape_mix': list(mix),
                            'salary_tilt': round(tau, 5)},
        'IDENTITIES_ENFORCED': [
            'sum of shares == 9 slots per entry',
            'no share > 100%',
            'sum of share*salary == declared field spend (this is what solves the tilt)'],
        'CALIBRATION_STATE': CALIBRATION_STATE,
        'MEANING': ('expected fraction of entries rostering the player, under a declared '
                    'functional form. NOT a measurement of ownership.'),
        'DATA_REQUEST': DATA_REQUEST,
    })


# ======================================================================================
# the shape mix, and why it ends up declared rather than measured
# ======================================================================================
FRONTIER_DEPTH = 150
DECLARED_SHAPE_MIX = (0.06, 0.1333, 0.8067)  # 3RB, 4WR, 2TE -- frontier at depth 150


def shape_mix_from_frontier(pool, depth: int = FRONTIER_DEPTH) -> Outcome:
    """Shape split across the top `depth` lineups by value. Exact, and depth-dependent."""
    import collections
    from nfl.opt import exact
    pos = {r['id']: r['position'] for r in pool}
    out = exact.k_best(list(pool), depth)
    if not out:
        return Outcome.fail('FRONTIER_EMPTY', evidence={'depth': depth})
    c: collections.Counter = collections.Counter()
    for L in out:
        t = collections.Counter(pos[i] for i in L['ids'])
        c[(t['RB'], t['WR'], t['TE'])] += 1
    tot = sum(c.values())
    mix = [c.get((s['RB'], s['WR'], s['TE']), 0) / tot for s in SHAPES]
    return Outcome.ok('FRONTIER_SHAPE_MIX', value={
        'mix': mix, 'depth': depth, 'n_lineups': tot,
        'MEANING': 'the shape split a value-maximising field would show at this depth',
        'CAVEAT': 'the field is not value-maximising, and the mix moves with depth',
    })


def shape_mix_decision(frontier_shallow, frontier_deep, fc_mix) -> Outcome:
    """Choose the shape mix, and record that neither candidate measurement identifies it.

    Both available measurements were run and both failed as identifications, in different
    ways, and that is the finding rather than an obstacle to route around:

      The 48 placeholder lineups are DEGENERATE -- every one of them is the same shape. That
      is one tool at one setting, so it measures the setting, not the field.

      Our own value frontier is DEPTH-DEPENDENT -- the leading shape falls from 94% at depth
      50 to 81% at depth 150 and keeps drifting toward uniform. Any single number from it is
      a choice of depth, and the depth that would match a 20,000-entry field is out of
      compute reach and rests on an unvalidated premise besides, that field entries look
      like top-value lineups.

    So the mix is DECLARED, from the deepest frontier measured, and the sensitivity grid
    spans uniform and each pure shape so that nothing downstream can quietly depend on it.
    """
    degenerate = fc_mix is not None and max(fc_mix) >= 0.95
    drift = None
    if frontier_shallow and frontier_deep:
        drift = round(max(frontier_shallow) - max(frontier_deep), 4)
    return Outcome.ok('SHAPE_MIX_DECLARED', value={
        'selected_mix': list(DECLARED_SHAPE_MIX),
        'selected_because': f'value frontier at depth {FRONTIER_DEPTH}, the deepest measured',
        'state': 'DECLARED_PRIOR_NOT_IDENTIFIED',
        'candidate_1_tool_lineups': {
            'mix': None if fc_mix is None else list(fc_mix),
            'verdict': 'DEGENERATE_SINGLE_SHAPE' if degenerate else 'usable',
            'why': ('48 of 48 lineups share one shape, so this measures one tool setting '
                    'rather than a field distribution') if degenerate else '',
            'rejected_as_field_mix': bool(degenerate)},
        'candidate_2_value_frontier': {
            'mix_shallow': None if not frontier_shallow else list(frontier_shallow),
            'mix_deep': None if not frontier_deep else list(frontier_deep),
            'leading_shape_drift_between_depths': drift,
            'verdict': 'DEPTH_DEPENDENT_NOT_AN_IDENTIFICATION'},
        'CONSEQUENCE': ('every quantity depending on the mix carries a sensitivity result, '
                        'and any decision that is not stable across the grid is BLOCKED'),
        'DATA_REQUEST': DATA_REQUEST,
    })


def sensitivity(pool, *, base_mix=DECLARED_SHAPE_MIX, top_n: int = 40) -> Outcome:
    """Since the parameters cannot be fitted, measure whether any decision depends on them.

    This is the substitute for calibration and it is the load-bearing part of GAP 4. The
    question is not whether 1.25 is the right steepness -- nothing here can answer that. It
    is whether the set of players a contest-aware portfolio would lean on changes across the
    whole plausible range. If it does not, an uncalibrated field is still usable for that
    decision. If it does, the decision is blocked and the data request is the only way out.
    """
    grid = []
    betas = (0.6, 1.25, 2.2)
    budgets = (47000, 48500, 49200, 49900)
    mixes = {'declared': tuple(base_mix), 'uniform': (1 / 3, 1 / 3, 1 / 3),
             'pure_3RB': (1.0, 0.0, 0.0), 'pure_4WR': (0.0, 1.0, 0.0),
             'pure_2TE': (0.0, 0.0, 1.0)}
    base = ownership(pool, mix=base_mix)
    if base.state.value != 'PASS':
        return Outcome.fail('SENSITIVITY_BASE_FAILED', evidence={'base': base.code})
    bown = base.value['ownership']

    def lev_top(ownvec):
        # the same ownership floor the leverage table uses. Without it this ranks the slate's
        # least-owned players, whose ratios are arithmetic about an empty denominator, and the
        # stability result would be measuring noise in the tail rather than any decision.
        from nfl.field.opponent import MIN_OWNERSHIP_FOR_LEVERAGE as FLOOR
        rows = []
        for r in pool:
            if not r.get('salary'):
                continue
            o = ownvec.get(r['id'], 0.0)
            if o < FLOOR:
                continue
            rows.append((float(r['value']) / (r['salary'] / 1000.0) / o, r['id']))
        rows.sort(reverse=True)
        return {i for _, i in rows[:top_n]}

    btop = lev_top(bown)
    worst_overlap, worst_setting, worst_delta = 1.0, None, 0.0
    for b in betas:
        for bud in budgets:
            for mname, m in mixes.items():
                o = ownership(pool, mix=m, value_beta=b, budget=bud)
                if o.state.value != 'PASS':
                    grid.append({'beta': b, 'budget': bud, 'mix': mname, 'state': o.code})
                    continue
                ov = o.value['ownership']
                overlap = len(btop & lev_top(ov)) / max(1, len(btop))
                delta = max(abs(ov[i] - bown[i]) for i in bown)
                grid.append({'beta': b, 'budget': bud, 'mix': mname,
                             'top_leverage_overlap': round(overlap, 4),
                             'max_ownership_change': round(delta, 4)})
                if overlap < worst_overlap:
                    worst_overlap, worst_setting = overlap, f'beta={b} budget={bud} mix={mname}'
                worst_delta = max(worst_delta, delta)
    # WHICH parameter drives the instability, since that says what the missing data buys
    def sweep(**kw):
        lo = 1.0
        for val in kw['values']:
            args = {'mix': base_mix, 'value_beta': None, 'budget': None}
            args[kw['name']] = val
            o = ownership(pool, mix=args['mix'], value_beta=args['value_beta'],
                          budget=args['budget'])
            if o.state.value != 'PASS':
                continue
            lo = min(lo, len(btop & lev_top(o.value['ownership'])) / max(1, len(btop)))
        return round(lo, 4)

    one_at_a_time = {
        'value_beta_alone': sweep(name='value_beta', values=betas),
        'budget_alone': sweep(name='budget', values=budgets),
        'shape_mix_alone': sweep(name='mix', values=list(mixes.values())),
    }
    dominant = min(one_at_a_time.items(), key=lambda kv: kv[1])

    stable = worst_overlap >= 0.80
    return Outcome.ok('SENSITIVITY_MEASURED', value={
        'one_parameter_at_a_time': one_at_a_time,
        'DOMINANT_PARAMETER': dominant[0],
        'DOMINANT_MEANING': (
            f'moving {dominant[0].replace("_alone", "")} alone, with everything else at its '
            f'declared value, already drops the top-{top_n} leverage overlap to {dominant[1]}. '
            f'That is the parameter archived contest ownership would pin down first.'),
        'n_settings': len(grid), 'n_settings_that_refused':
            sum(1 for g in grid if 'state' in g), 'grid': grid,
        'worst_top_leverage_overlap': round(worst_overlap, 4),
        'worst_setting': worst_setting,
        'max_ownership_change_anywhere': round(worst_delta, 4),
        'VERDICT': ('LEVERAGE_SET_STABLE_ACROSS_UNCALIBRATED_RANGE' if stable
                    else 'DECISION_SENSITIVE_TO_UNCALIBRATED_PARAMETERS'),
        'THEREFORE': ('a contest-aware portfolio may use the leverage ordering while the '
                      'ownership LEVEL stays uncalibrated' if stable else
                      'no contest-aware decision may rely on this field until archived '
                      'contest ownership exists; see ' + DATA_REQUEST),
        'threshold': {'top_n': top_n, 'overlap_required': 0.80,
                      'declared_before_running': True},
    })
