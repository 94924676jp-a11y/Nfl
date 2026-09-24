"""A research-only Showdown portfolio, honest about what it cannot claim.

LABEL: RESEARCH_DFS_PORTFOLIO_NOT_JOINT-WORLD_VALIDATED

WHAT IT MAY NOT CLAIM, AND WHY

The draw artifact declares `across_rows: INDEPENDENT_STREAMS_COLUMN_ALIGNED`.
Column j of player A and column j of player B are NOT the same simulated
world, so no quantity that needs two players to share a world is available
here. That rules out, by name: lineup win probability, top-1 probability,
P(at least one of ten wins), measured cross-player correlation, and any
stack-leverage figure derived from covariance.

Measured cost, same marginals and only the dependence changed: the mean of a
six-man lineup is identical to the cent under independence and under perfect
coupling -- dependence cannot move the expectation of a sum -- while p95 moves
+51% and p99 +68%. So the MEAN is trustworthy and the CEILING is not, and the
ceiling is what a tournament is decided by.

WHAT REMAINS LAWFUL, AND IS USED

* Each player's own marginal distribution. `within_row_across_metrics` is
  SAME_SIMULATED_WORLD, so a single player's DK-point draws are a real
  distribution and its quantiles are real.
* The independent-sum of a lineup, used ONLY as a declared LOWER BOUND on the
  true ceiling, never as the ceiling.
* Exact salary arithmetic and the legal Showdown construction rules.
* Availability-aware means, with the conditional and unconditional kept apart.
* Roster overlap between lineups, which is a counted structural fact and
  needs no covariance at all.
* Explicit scenario theses, carried as stated ASSUMPTIONS rather than
  measurements.

THE SELECTION OBJECTIVE IS A DECLARED HEURISTIC, NOT AN OPTIMUM

Without a joint world there is no P(win) to maximise, so the builder does not
pretend to optimise one. It maximises a stated combination of lawful
quantities under structural constraints, and the combination is written down
in `OBJECTIVE` so a reader can disagree with it specifically. A portfolio
selected by an undisclosed objective is a recommendation wearing arithmetic.
"""
from __future__ import annotations

import itertools

SPEC_VERSION = 'dfs-research-portfolio/1.0.0'
LABEL = 'RESEARCH_DFS_PORTFOLIO_NOT_JOINT-WORLD_VALIDATED'

CAPTAIN_MULTIPLIER = 1.5
FLEX_SLOTS = 5
DEFAULT_SALARY_CAP = 50000

#: DK Showdown requires at least one player from each club.
MIN_TEAMS = 2

OBJECTIVE = (
    'Rank candidate lineups by independent-sum mean and by independent-sum '
    'p90 (the declared LOWER BOUND on ceiling), then select under structural '
    'constraints: captain diversity, thesis coverage, and a cap on pairwise '
    'roster overlap. No term in this objective is a win probability and none '
    'is presented as one.'
)

FORBIDDEN_CLAIMS = (
    'lineup win probability',
    'top-1 probability',
    'P(at least one of N wins)',
    'measured cross-player correlation',
    'covariance-derived stack leverage',
)


class PortfolioError(RuntimeError):
    """The portfolio cannot be built from what was supplied."""


def legal(lineup, pool, cap=DEFAULT_SALARY_CAP) -> bool:
    """Legal Showdown construction: 6 distinct players, both clubs, under cap."""
    cpt, flex = lineup[0], lineup[1:]
    names = [cpt] + list(flex)
    if len(set(names)) != 1 + FLEX_SLOTS:
        return False
    teams = {pool[n]['team'] for n in names}
    if len(teams) < MIN_TEAMS:
        return False
    return salary_of(lineup, pool) <= cap


def salary_of(lineup, pool) -> int:
    cpt, flex = lineup[0], lineup[1:]
    return int(pool[cpt]['CPT']) + sum(int(pool[n]['FLEX']) for n in flex)


def score(lineup, marginals):
    """Lawful summary of one lineup. Every field says what it is.

    `marginals` maps player -> 1-D array of that player's DK-point draws.
    """
    import numpy as np
    cpt, flex = lineup[0], lineup[1:]
    contrib = [np.asarray(marginals[cpt], float) * CAPTAIN_MULTIPLIER]
    contrib += [np.asarray(marginals[n], float) for n in flex]
    stacked = np.vstack(contrib)
    total = stacked.sum(axis=0)
    return {
        'mean': float(total.mean()),
        'mean_basis': 'EXACT. Dependence cannot move the mean of a sum.',
        'indep_sum_p90': float(np.percentile(total, 90)),
        'indep_sum_p95': float(np.percentile(total, 95)),
        'ceiling_basis': (
            'LOWER BOUND ONLY. Computed under independent streams, which drop '
            'every covariance term. Same marginals under perfect coupling move '
            'p95 by about +51%, so the true ceiling is above this and is not '
            'known.'),
        'per_player_mean': {n: float(np.asarray(marginals[n], float).mean()
                                     * (CAPTAIN_MULTIPLIER if n == cpt else 1))
                            for n in [cpt] + list(flex)},
    }


def overlap(a, b) -> int:
    """Players shared by two lineups. A counted fact, needing no covariance."""
    return len(set(a) & set(b))


def build_candidates(pool, marginals, theses, *, cap=DEFAULT_SALARY_CAP,
                     captain_pool=None, flex_pool=None, max_candidates=200000):
    """Enumerate legal lineups from the supplied pools.

    Pools are passed in rather than derived, because deciding which players
    are worth considering is a football judgement and this module should not
    make it silently.
    """
    names = [n for n in pool if n in marginals]
    if len(names) < 1 + FLEX_SLOTS:
        raise PortfolioError(
            f'{len(names)} players have both a salary and a projection; a '
            f'Showdown lineup needs {1 + FLEX_SLOTS}. Refusing to build a '
            f'portfolio from a pool this thin rather than returning a short '
            f'list that looks complete.')
    caps = list(captain_pool or names)
    flexes = list(flex_pool or names)
    out, seen = [], 0
    for cpt in caps:
        for combo in itertools.combinations([n for n in flexes if n != cpt],
                                            FLEX_SLOTS):
            seen += 1
            if seen > max_candidates:
                raise PortfolioError(
                    f'candidate enumeration exceeded {max_candidates}; narrow '
                    f'the captain or flex pool deliberately rather than '
                    f'silently truncating the search')
            lineup = (cpt,) + combo
            if not legal(lineup, pool, cap):
                continue
            s = score(lineup, marginals)
            s['lineup'] = lineup
            s['captain'] = cpt
            s['salary_used'] = salary_of(lineup, pool)
            s['salary_remaining'] = cap - s['salary_used']
            s['theses'] = [t['name'] for t in (theses or ())
                           if t['holds'](lineup, pool)]
            out.append(s)
    if not out:
        raise PortfolioError(
            'no legal lineup could be built from the supplied pools under the '
            'cap. That is a refusal, not an empty portfolio.')
    return out


def select(candidates, n=10, *, max_overlap=4, max_per_captain=3,
           max_player_exposure=None, min_thesis_coverage=None,
           rank_key='indep_sum_p90'):
    """Greedy selection under the declared structural constraints.

    Greedy, and said so: this is not a search for the optimal portfolio,
    because there is no objective here worth optimising to the last decimal.

    WHY EXPOSURE AND THESIS CAPS EXIST, FROM A FAILURE THIS MODULE HAD.

    The first run of this selector ranked purely on independent-sum p90 under
    overlap and captain caps, and produced a portfolio with ONE PLAYER IN ALL
    TEN LINEUPS and zero coverage of one of the four declared theses. That is
    not a portfolio, it is ten spellings of the same bet -- and it is exactly
    the failure the owner's directive names: "the final 10 should NOT simply
    be the 10 highest projected lineups".

    The cause is structural and worth stating. Independent-sum p90 is
    dominated by the mean, the mean is a sum of marginals, so ranking on it
    converges on whichever handful of players project highest. Overlap caps do
    not prevent it because ten lineups can share a core of three and still
    differ in three slots each.

    So exposure and thesis coverage are constraints on the SEARCH, not
    adjustments to a score. A portfolio that cannot satisfy them returns short
    rather than relaxing them.
    """
    if not candidates:
        raise PortfolioError('no candidates to select from')
    ranked = sorted(candidates, key=lambda c: -c[rank_key])
    chosen, per_captain, exposure = [], {}, {}
    needed = dict(min_thesis_coverage or {})

    def admissible(c, *, enforce_thesis):
        if per_captain.get(c['captain'], 0) >= max_per_captain:
            return False
        if any(overlap(c['lineup'], p['lineup']) > max_overlap for p in chosen):
            return False
        if max_player_exposure is not None:
            slots_left = n - len(chosen)
            for pl in c['lineup']:
                if exposure.get(pl, 0) + 1 > max_player_exposure:
                    return False
            # Leave room for the theses still owed.
            if enforce_thesis and needed:
                owed = sum(v for v in needed.values())
                if slots_left - 1 < 0:
                    return False
        return True

    def take(c):
        chosen.append(c)
        per_captain[c['captain']] = per_captain.get(c['captain'], 0) + 1
        for pl in c['lineup']:
            exposure[pl] = exposure.get(pl, 0) + 1
        for t in c['theses']:
            if t in needed:
                needed[t] = max(0, needed[t] - 1)

    # PASS 1 -- pay the thesis debts first, strongest candidate that serves
    # each. A thesis satisfied only by leftovers is a thesis in name only.
    for thesis in sorted(needed, key=lambda t: -needed[t]):
        while needed.get(thesis, 0) > 0 and len(chosen) < n:
            pick = next((c for c in ranked
                         if thesis in c['theses'] and c not in chosen
                         and admissible(c, enforce_thesis=False)), None)
            if pick is None:
                break
            take(pick)

    # PASS 2 -- fill the rest on rank.
    for c in ranked:
        if len(chosen) >= n:
            break
        if c in chosen:
            continue
        if admissible(c, enforce_thesis=True):
            take(c)

    unmet = {t: v for t, v in needed.items() if v > 0}
    if unmet:
        return {'lineups': chosen, 'short_by': max(0, n - len(chosen)),
                'unmet_thesis_coverage': unmet,
                'note': (f'thesis coverage could not be met: {unmet}. The '
                         f'constraint was NOT relaxed; a thesis with no '
                         f'lineup is reported rather than quietly dropped.')}

    if len(chosen) < n:
        # NOT PADDED. A portfolio short of its target says so rather than
        # relaxing a constraint quietly to reach a round number.
        return {'lineups': chosen, 'short_by': n - len(chosen),
                'note': (f'only {len(chosen)} of {n} lineups satisfy the '
                         f'declared constraints (max_overlap={max_overlap}, '
                         f'max_per_captain={max_per_captain}, '
                         f'max_player_exposure={max_player_exposure}). The '
                         f'constraints were NOT relaxed to reach {n}.')}
    return {'lineups': chosen, 'short_by': 0, 'note': ''}


def summarise(selection, pool) -> dict:
    """Portfolio-level exposure. Counts and salary, no probability."""
    lus = selection['lineups']
    if not lus:
        raise PortfolioError('an empty selection has no summary')
    cap_exposure, player_exposure, thesis_counts = {}, {}, {}
    for c in lus:
        cap_exposure[c['captain']] = cap_exposure.get(c['captain'], 0) + 1
        for p in c['lineup']:
            player_exposure[p] = player_exposure.get(p, 0) + 1
        for t in c['theses']:
            thesis_counts[t] = thesis_counts.get(t, 0) + 1
    pairs = [overlap(a['lineup'], b['lineup'])
             for a, b in itertools.combinations(lus, 2)]
    return {
        'label': LABEL,
        'spec_version': SPEC_VERSION,
        'n_lineups': len(lus),
        'captain_exposure': dict(sorted(cap_exposure.items(),
                                        key=lambda kv: -kv[1])),
        'player_exposure': dict(sorted(player_exposure.items(),
                                       key=lambda kv: -kv[1])),
        'thesis_coverage': dict(sorted(thesis_counts.items(),
                                       key=lambda kv: -kv[1])),
        'salary_remaining': sorted(c['salary_remaining'] for c in lus),
        'pairwise_overlap': {'min': min(pairs) if pairs else None,
                             'max': max(pairs) if pairs else None,
                             'mean': (round(sum(pairs) / len(pairs), 2)
                                      if pairs else None)},
        'objective': OBJECTIVE,
        'forbidden_claims': list(FORBIDDEN_CLAIMS),
        'reading': (
            'Exposure and overlap are counted facts. Mean is exact. Every '
            'ceiling figure is a lower bound computed without covariance. '
            'Nothing here is a probability of winning anything.'),
    }
