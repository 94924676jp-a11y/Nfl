"""B0-B5: the comparator suite, built BEFORE the candidate so it cannot be
reverse-engineered to favour it.

WHY A SIBLING MODULE RATHER THAN AN EXTENSION OF
`nfl/research/baselines/estimators.py`

That module's estimators take `hist`, a list of `(ordinal, value)` pairs for
ONE SUBJECT -- a player -- and reduce it. OAS1's baselines predict a PLAY's
EPA from two team units and a league level, which is a different unit of
observation, a different target and a different cold-start question. Forcing
them into one module would make both harder to read.

What is NOT duplicated: `prior`, `mean`, `recent_n` and `ewma` are IMPORTED
from that module and called. `prior` in particular is the point-in-time cut
this whole package depends on, and reimplementing it here is precisely the
Class C duplication the repository warns about -- the permissive copy is the
one a caller reaches for.

THE FAIRNESS CONSTRAINT, WHICH IS THE MOST LIKELY PLACE FOR SELF-DECEPTION

Every baseline and the candidate consume the IDENTICAL row set with the
IDENTICAL exclusions and the IDENTICAL cold-start ladder. A baseline built
with less care than the candidate makes the comparison unfair in the
candidate's favour and requires no bad intent to happen -- only asymmetric
effort. `chain()` therefore hands every estimator the same `hist` and the same
`test` objects, and records the row-set hash so the claim is checkable.

B4 AND B5 ARE THE ONES THAT MATTER. B4 removes opponent quality by
subtraction rather than joint estimation -- the cheap, transparent version of
what OAS1 claims to do. B5 adds the shrinkage that does most of the work at
Week 2. If OAS1 cannot beat B5 out of sample on a clustered interval, the
ridge's extra machinery is unjustified and B5 is the answer.

B4 ON A SINGLE WEEK PRODUCES ZERO ADJUSTMENT FOR EVERY UNIT, because each
unit's opponents-faced mean is that one opponent. That is the same
identification collapse the rank-32 test proves formally, expressed
arithmetically, and `test_oas1_baselines` asserts it.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
# REUSED, NOT REIMPLEMENTED. `prior` is the point-in-time cut.
from nfl.research.baselines.estimators import (                # noqa: E402
    prior as pit_prior, mean as seq_mean, recent_n as seq_recent_n,
    ewma as seq_ewma, Undefined)

SPEC_VERSION = 'oas1-baselines-1'

NAMES = ('B0', 'B1', 'B2', 'B3', 'B4', 'B5')

#: Every hyperparameter grid, declared as a literal so a test reads it from
#: code rather than from prose.
GRIDS = {
    'B0': {},
    'B1': {'rho': (0.5, 0.7, 0.85, 1.0)},
    'B2': {'n_games': (2, 4, 8)},
    'B3': {'half_life': (2.0, 4.0, 8.0)},
    # B4 HAS NO HYPERPARAMETER, AND A MEASUREMENT TOOK ONE AWAY.
    #
    # It was declared with `n_passes: (1, 2, 4)`. Undamped Jacobi iteration
    # OSCILLATES WITH PERIOD 2 on a design where each unit faces exactly one
    # opponent: measured on a synthetic one-week frame, max |off| is 0.0000 at
    # 1, 3 and 5 passes and 0.9000 at 2 and 4. A tuner choosing `n_passes`
    # there is choosing between two arbitrary answers, not tuning anything.
    #
    # On a connected schedule it converges properly -- full 2025 pass frame,
    # the iterate-to-iterate change decays 0.01362, 0.00880, 0.00191,
    # 0.00189, 0.00039 and reaches 0.00004 by the eleventh pass. So the
    # estimator iterates to a TOLERANCE and reports whether it converged,
    # instead of carrying a pass count that means different things on the two
    # designs.
    'B4': {},
    'B5': {'kappa': (0.25, 0.5, 0.75), 'rho': (0.7, 0.85, 1.0)},
}

SPECS = {
    'B0': {
        'name': 'league constant',
        'formula': 'yhat = mean(epa) over all plays of this class with '
                   'ordinal < forecast ordinal',
        'information_set': 'every prior play of this class, both seasons',
        'cold_start': 'trivially defined; no subject-level history needed',
        'hyperparameters': 'none',
        'tuning_rule': 'not applicable',
    },
    'B1': {
        'name': 'prior-season unit prior',
        'formula': 'yhat = mu_hist + rho*(off_prev[o] + def_prev[d]), where '
                   'off_prev and def_prev are prior-SEASON mean residuals per '
                   'unit and rho is offseason regression',
        'information_set': 'the complete prior season only; no current-season '
                           'play is read',
        'cold_start': 'a club absent from the prior season falls back to B0',
        'hyperparameters': 'rho',
        'tuning_rule': 'forward-chained, one-SE, most-shrunken = smallest rho',
    },
    'B2': {
        'name': 'rolling unit mean',
        'formula': 'yhat = mu_hist + rbar(o, n) + rbar(d, n), rbar the mean '
                   'residual over the unit`s last n games',
        'information_set': 'current season to date, spilling into the prior '
                           'season when fewer than n games exist',
        'cold_start': 'spills into the prior season, then B1, then B0',
        'hyperparameters': 'n_games',
        'tuning_rule': 'forward-chained, one-SE, most-shrunken = largest n',
    },
    'B3': {
        'name': 'EWMA unit mean',
        'formula': 'as B2 with exponentially weighted residuals at the tuned '
                   'half-life, weight 0.5 ** (games_back / half_life)',
        'information_set': 'as B2',
        'cold_start': 'as B2',
        'hyperparameters': 'half_life',
        'tuning_rule': 'forward-chained, one-SE, most-shrunken = largest '
                       'half_life',
    },
    'B4': {
        'name': 'simple opponent-adjusted',
        'formula': 'iterative subtraction: off[o] <- mean residual of o`s '
                   'plays minus the mean def of the opponents faced; def[d] '
                   'symmetrically; iterated to B4_TOL or B4_MAX_ITER. No '
                   'penalty, no matrix inversion',
        'information_set': 'as B2 plus the schedule',
        'cold_start': 'a unit with no prior plays falls back to B1, then B0',
        'hyperparameters': 'none. Declared with `n_passes` and measured out '
                           'of existence: undamped Jacobi oscillates with '
                           'period 2 on an unidentified design, so a pass '
                           'count selects between two arbitrary answers. It '
                           'iterates to B4_TOL and reports convergence',
        'tuning_rule': 'not applicable; convergence is not a hyperparameter',
        'non_convergence': 'falls back to the SINGLE-PASS estimate, which is '
                           'the declared definition -- unit mean minus the '
                           'mean of the opponents faced -- and is the only '
                           'pass with a defensible reading. Recorded as '
                           'converged=False, never silently',
    },
    'B5': {
        'name': 'shrunken opponent-adjusted -- THE DECISIVE COMPARATOR',
        'formula': 'yhat = mu_hist + blend(o) + blend(d), blend(u) = '
                   'kappa*B4(u) + (1-kappa)*rho*B1_prev(u)',
        'information_set': 'as B4',
        'cold_start': 'as B4',
        'hyperparameters': 'kappa, rho',
        'tuning_rule': 'forward-chained, one-SE, most-shrunken = smallest '
                       'kappa then smallest rho',
    },
}
for _n in NAMES:
    SPECS[_n].update({'target': 'oas1_epa_target, one play',
                      'metrics': ('mae', 'rmse', 'crps', 'calibration_slope'),
                      'grid': GRIDS[_n]})

#: The most-shrunken direction per hyperparameter, pre-declared so the
#: tie-break is mechanical. True = larger is more shrunken.
SHRINK_DIRECTION = {'rho': False, 'n_games': True, 'half_life': True,
                    'kappa': False}

#: B4's iteration controls. Not hyperparameters: a convergence tolerance is a
#: numerical setting, and tuning it would be tuning the arithmetic.
B4_TOL = 1e-6
B4_MAX_ITER = 50

TIE_BREAK = ('among configurations within one standard error of the best mean '
             'score, take the most shrunken, using SHRINK_DIRECTION per '
             'hyperparameter in the order the grid declares them')

CODE_OK = 'OAS1_BASELINE_PREDICTED'
CODE_NO_HIST = 'OAS1_BASELINE_NO_HISTORY'
CODE_UNKNOWN = 'OAS1_BASELINE_UNKNOWN'


def rowset_hash(rows) -> str:
    """Identifies the exact row set an estimator was given.

    This is what makes "identical information sets" checkable instead of
    asserted. Comparing a candidate to a baseline computed on a different row
    set is the most common way a spurious win appears.
    """
    keys = sorted((r['game_id'], r['play_id']) for r in rows)
    return hashlib.sha256(json.dumps(keys).encode()).hexdigest()


def _mu(hist):
    return float(np.mean([r['epa'] for r in hist])) if hist else 0.0


def _unit_games(hist, mu):
    """Per unit, an ascending `(ordinal, mean_residual)` series by game.

    Game-level rather than play-level so that `recent_n` and `ewma` count
    GAMES, matching the reused estimators' declared semantics.
    """
    acc = {}
    for r in hist:
        for side, t in (('off', r['offense_team']), ('def', r['defense_team'])):
            acc.setdefault((side, t), {}).setdefault(
                (r['ordinal'], r['game_id']), []).append(r['epa'] - mu)
    out = {}
    for k, games in acc.items():
        out[k] = [(ordi, float(np.mean(v)))
                  for (ordi, _g), v in sorted(games.items())]
    return out


def _prev_season_units(hist, season, mu):
    """Prior-SEASON mean residual per unit. B1's estimate."""
    prev = [r for r in hist if r['season'] == season - 1]
    if not prev:
        return {}
    acc = {}
    for r in prev:
        acc.setdefault(('off', r['offense_team']), []).append(r['epa'] - mu)
        acc.setdefault(('def', r['defense_team']), []).append(r['epa'] - mu)
    return {k: float(np.mean(v)) for k, v in acc.items()}


def _b4(hist, mu, tol: float = B4_TOL, max_iter: int = B4_MAX_ITER):
    """Iterative opponent subtraction, to a tolerance. Returns (off, def, info).

    THE SINGLE PASS IS THE DECLARED ESTIMATOR: a unit's raw mean residual
    minus the mean of the opponents it faced. Further passes refine it by
    using the refined opponent estimates, and on a connected schedule that
    converges. On an UNIDENTIFIED design it does not converge -- it flips
    between giving all the credit to the offence and all of it to the defence
    -- and in that case the single pass is returned and `converged` is False.

    Returning the single pass rather than the last iterate is a choice with a
    reason: pass 1 is the only iterate with a defensible reading when the
    sequence has not settled, and on a one-week frame it is exactly zero,
    which is the identification collapse correctly expressed.
    """
    plays_off, plays_def = {}, {}
    for r in hist:
        plays_off.setdefault(r['offense_team'], []).append(
            (r['epa'] - mu, r['defense_team']))
        plays_def.setdefault(r['defense_team'], []).append(
            (r['epa'] - mu, r['offense_team']))
    raw_off = {t: float(np.mean([x for x, _ in v]))
               for t, v in plays_off.items()}
    raw_def = {t: float(np.mean([x for x, _ in v]))
               for t, v in plays_def.items()}
    off, dfn = dict(raw_off), dict(raw_def)
    first = None
    changes = []
    converged = False
    n_iter = 0
    for i in range(int(max_iter)):
        n_iter = i + 1
        new_off = {t: float(np.mean([x - dfn.get(op, 0.0)
                                     for x, op in plays_off[t]]))
                   for t in plays_off}
        new_def = {t: float(np.mean([x - off.get(op, 0.0)
                                     for x, op in plays_def[t]]))
                   for t in plays_def}
        ch = max([abs(new_off[t] - off[t]) for t in new_off]
                 + [abs(new_def[t] - dfn[t]) for t in new_def] or [0.0])
        changes.append(float(ch))
        off, dfn = new_off, new_def
        if first is None:
            first = (dict(off), dict(dfn))
        if ch < float(tol):
            converged = True
            break
    info = {'converged': bool(converged), 'n_iter': int(n_iter),
            'final_change': changes[-1] if changes else 0.0,
            'tol': float(tol), 'max_iter': int(max_iter),
            'change_trace': changes[:12]}
    if not converged and first is not None:
        # NOT SILENT. The single-pass estimate is returned and said so.
        info['used'] = 'SINGLE_PASS_FALLBACK'
        info['why'] = ('the iteration did not converge within max_iter, '
                       'which on an unidentified design means it is '
                       'oscillating rather than settling. The single-pass '
                       'estimate is the declared definition and the only '
                       'iterate with a defensible reading here.')
        return first[0], first[1], info
    info['used'] = 'CONVERGED_ITERATE'
    return off, dfn, info


def predict(name, hist, test, cfg) -> Outcome:
    """One baseline, one forecast week. `hist` is already cut by the caller.

    The signature is the point-in-time guarantee: the week being forecast is
    not reachable from `hist`, and `test` supplies only the two team codes and
    the home flag, never the outcome.
    """
    if name not in NAMES:
        return Outcome.fail(CODE_UNKNOWN, f'{name!r} is not one of {NAMES}')
    if not hist:
        return Outcome.fail(
            CODE_NO_HIST, f'{name}: no prior history, so no forecast is '
                          f'defined. Refused rather than defaulted to zero.',
            cause=Cause.DATA)
    mu = _mu(hist)
    season = test[0]['season']
    fallbacks = {'to_B0': 0, 'to_B1': 0}
    prev = _prev_season_units(hist, season, mu)
    rho = float(cfg.get('rho', 1.0))

    def b1_unit(side, t):
        v = prev.get((side, t))
        if v is None:
            fallbacks['to_B0'] += 1
            return 0.0
        return rho * v

    if name == 'B0':
        def f(side, t):
            return 0.0
    elif name == 'B1':
        f = b1_unit
    elif name in ('B2', 'B3'):
        series = _unit_games(hist, mu)

        def f(side, t):
            s = series.get((side, t))
            if not s:
                fallbacks['to_B1'] += 1
                return b1_unit(side, t)
            try:
                if name == 'B2':
                    return seq_recent_n(s, int(cfg['n_games']))
                return seq_ewma(s, float(cfg['half_life']))
            except Undefined:
                fallbacks['to_B1'] += 1
                return b1_unit(side, t)
    elif name in ('B4', 'B5'):
        off, dfn, b4info = _b4(hist, mu)
        fallbacks['b4'] = b4info
        kappa = float(cfg.get('kappa', 1.0)) if name == 'B5' else 1.0

        def f(side, t):
            v = (off if side == 'off' else dfn).get(t)
            if v is None:
                fallbacks['to_B1'] += 1
                return b1_unit(side, t)
            if name == 'B5':
                return kappa * v + (1.0 - kappa) * b1_unit(side, t)
            return v
    yhat = np.array([mu + f('off', r['offense_team']) + f('def', r['defense_team'])
                     for r in test], dtype=np.float64)
    return Outcome.ok(
        CODE_OK, value=yhat,
        detail=f'{name}: {len(test)} prediction(s), cfg {cfg}',
        spec_version=SPEC_VERSION, baseline=name, cfg=dict(cfg),
        mu=mu, n_hist=len(hist), n_test=len(test),
        fallbacks=dict(fallbacks),
        hist_rowset_sha256=rowset_hash(hist),
        test_rowset_sha256=rowset_hash(test))
