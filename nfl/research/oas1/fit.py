"""Weighted ridge for OAS1, with clustered uncertainty and a forward-chained lambda.

FOUR DECISIONS, EACH WITH ITS REASON

1. THE INTERCEPT AND HOME TERM ARE UNPENALISED. If the intercept is penalised
   the league mean is absorbed into the shrunken dummies and every unit
   estimate is biased by it. This is the standard construction and it is
   enforced by `penalty_mask`, not left to a caller.

2. NO EXPLICIT SUM-TO-ZERO CONSTRAINT. Ridge already resolves the dummy
   redundancy by shrinking toward zero, and imposing sum-to-zero as well is a
   double constraint whose interaction with lambda is easy to misread.
   Coefficients are CENTRED WITHIN EACH UNIT FAMILY AFTER fitting, purely for
   reporting, which is a relabelling and changes no fitted value.

3. UNCERTAINTY IS CLUSTERED BY GAME. All plays in a game share weather,
   officiating, script and both rosters, so i.i.d. standard errors are wrong
   here in a known direction and a known magnitude -- this project has already
   measured i.i.d. intervals as roughly threefold too narrow. The estimator is
   the cluster-robust sandwich around the ridge solution.

4. LAMBDA IS SELECTED BY FORWARD CHAINING INSIDE THE SEASON, never by fitting
   the whole season and picking what scores best on it. For a prior-season fit
   the chain is over that season's own weeks: fit on weeks < w, score week w,
   average, and apply the one-standard-error rule with the most-shrunken
   tie-break DECLARED BEFORE the grid runs. A lambda chosen on the full season
   and then used to fit the full season is tuning on the evaluation set.

THE TIE-BREAK IS PRE-DECLARED HERE, IN CODE, so a test can read it: among
configurations within one standard error of the best mean score, take the
LARGEST lambda. More shrinkage is the more conservative claim, and the
alternative -- taking the best point on a flat surface -- is selecting noise.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.research.oas1 import design as DS                          # noqa: E402

SPEC_VERSION = 'oas1-ridge-fit-1'

#: The lambda grid, 12 points log-spaced, declared as a literal.
LAMBDA_GRID = tuple(float(x) for x in np.logspace(-1, 4, 12))

#: The tie-break, pre-declared. Read by a test, not described in prose.
TIE_BREAK = 'among configurations within 1 SE of the best mean score, take ' \
            'the LARGEST lambda'

#: A NAMED DIAGNOSTIC, NOT A LICENCE TO WIDEN THE GRID.
#:
#: The 2025 prior-season fit selected lambda = 10000 for BOTH play classes,
#: which is `max(LAMBDA_GRID)`. A selection at the edge of a search space means
#: the rule wanted more shrinkage than the space offers, and the resulting
#: prior is nearly degenerate: off_pass sd 0.0074 against a residual sd of
#: 1.5684, about 1.8 mean standard errors at the extremes.
#:
#: THE GRID IS NOT EXPANDED IN RESPONSE. Widening a search space after seeing
#: which end of it was selected is retuning on the result, and it is forbidden
#: here for the same reason a threshold may not be loosened after a test
#: fails. Any expansion is a NEW pre-registered experiment with a new
#: identity, not an edit to this one.
CODE_GRID_BOUNDARY = 'RIDGE_GRID_BOUNDARY_SELECTED'


def grid_boundary_check(chosen: float, grid=LAMBDA_GRID) -> dict:
    """Is the selected lambda at an end of the declared grid?

    Returns a diagnostic dict, never a refusal: the selection is lawful and
    pre-registered. What is not lawful is leaving the condition unreported.
    """
    g = [float(x) for x in grid]
    at_max = float(chosen) >= max(g)
    at_min = float(chosen) <= min(g)
    return {
        'code': CODE_GRID_BOUNDARY if (at_max or at_min) else 'RIDGE_GRID_INTERIOR',
        'chosen_lambda': float(chosen),
        'grid_min': min(g), 'grid_max': max(g), 'n_grid': len(g),
        'at_grid_maximum': bool(at_max), 'at_grid_minimum': bool(at_min),
        'at_boundary': bool(at_max or at_min),
        'meaning': ('the one-standard-error most-shrunken rule wanted MORE '
                    'shrinkage than the declared grid offers'
                    if at_max else
                    'the rule wanted LESS shrinkage than the grid offers'
                    if at_min else
                    'the selection is interior to the grid'),
        'grid_must_not_be_expanded': ('expanding the search space after '
                                      'observing which end was selected is '
                                      'retuning on the result. Any expansion '
                                      'is a NEW pre-registered experiment.'),
    }

CODE_OK = 'OAS1_FIT_OK'
CODE_UNIDENTIFIED = 'OAS1_FIT_ON_UNIDENTIFIED_DESIGN'
CODE_NO_FOLDS = 'OAS1_FIT_NO_FOLDS'
CODE_SINGULAR = 'OAS1_FIT_SINGULAR'


def penalty_mask(n_cols: int) -> np.ndarray:
    """1 for a penalised column, 0 for the intercept and the home term."""
    p = np.ones(n_cols, dtype=np.float64)
    p[0] = 0.0
    p[-1] = 0.0
    return p


def ridge(X, y, lam, w=None) -> np.ndarray:
    """Weighted ridge with the intercept and home term unpenalised."""
    X = np.asarray(X, float)
    y = np.asarray(y, float).reshape(-1)
    n, k = X.shape
    W = np.ones(n) if w is None else np.asarray(w, float).reshape(-1)
    A = X.T @ (X * W[:, None]) + float(lam) * np.diag(penalty_mask(k))
    return np.linalg.solve(A, X.T @ (W * y))


def cluster_se(X, y, theta, lam, clusters, w=None) -> np.ndarray:
    """Cluster-robust sandwich standard errors around the ridge solution.

    Var = A^-1 ( sum_g X_g' e_g e_g' X_g ) A^-1, clusters g. Looped over
    clusters rather than built as one large matrix, because a
    replicate-by-observation construction has already exhausted this sandbox
    once on a different layer.
    """
    X = np.asarray(X, float)
    y = np.asarray(y, float).reshape(-1)
    n, k = X.shape
    W = np.ones(n) if w is None else np.asarray(w, float).reshape(-1)
    A = X.T @ (X * W[:, None]) + float(lam) * np.diag(penalty_mask(k))
    Ainv = np.linalg.inv(A)
    e = (y - X @ theta) * W
    meat = np.zeros((k, k))
    order = np.argsort(np.asarray(clusters, dtype=object).astype(str))
    cl = np.asarray(clusters, dtype=object).astype(str)[order]
    Xs, es = X[order], e[order]
    start = 0
    n_cl = 0
    for i in range(1, len(cl) + 1):
        if i == len(cl) or cl[i] != cl[start]:
            Xg, eg = Xs[start:i], es[start:i]
            s = Xg.T @ eg
            meat += np.outer(s, s)
            start = i
            n_cl += 1
    V = Ainv @ meat @ Ainv
    return np.sqrt(np.maximum(np.diag(V), 0.0)), n_cl


def center_within_family(theta, n_teams: int) -> dict:
    """Centre each unit family on its own mean. A RELABELLING, not a refit.

    Reporting only. The fitted values are unchanged; what moves is where the
    zero sits, and the league level stays in the intercept where the
    unpenalised fit put it.
    """
    off = np.asarray(theta[1:1 + n_teams], float)
    dfn = np.asarray(theta[1 + n_teams:1 + 2 * n_teams], float)
    return {'offense': off - off.mean(), 'defense': dfn - dfn.mean(),
            'offense_raw': off, 'defense_raw': dfn,
            'offense_shift': float(off.mean()),
            'defense_shift': float(dfn.mean()),
            'intercept': float(theta[0]), 'home': float(theta[-1])}


def select_lambda_forward(rows, *, play_class: str,
                          grid=LAMBDA_GRID) -> Outcome:
    """Forward-chained lambda selection inside one season, with the 1-SE rule.

    Fold w: fit on that season's weeks strictly before w, score week w by
    mean absolute error. Every fold's fitting set is checked against the fold
    ordinal, so the leakage guard is an assertion and not a comment.
    """
    kept = [r for r in rows if r.get('play_class') == play_class
            and r.get('excluded_reason') == 'none'
            and r.get('offense_team') and r.get('defense_team')]
    if not kept:
        return Outcome.fail(CODE_NO_FOLDS, f'no kept {play_class} rows')
    weeks = sorted({r['week'] for r in kept})
    folds = [w for w in weeks if any(r['week'] < w for r in kept)]
    if len(folds) < 2:
        return Outcome.fail(
            CODE_NO_FOLDS,
            f'{play_class}: {len(folds)} usable fold(s). A lambda cannot be '
            f'chosen by forward chaining with fewer than two.',
            n_weeks=len(weeks))
    # The union team list, so every fold shares one column space.
    teams = sorted({r['offense_team'] for r in kept}
                   | {r['defense_team'] for r in kept})
    ti = {t: i for i, t in enumerate(teams)}
    n = len(teams)

    def mat(sub):
        X = np.zeros((len(sub), 1 + 2 * n + 1))
        yv = np.zeros(len(sub))
        for k, r in enumerate(sub):
            X[k, 0] = 1.0
            X[k, 1 + ti[r['offense_team']]] = 1.0
            X[k, 1 + n + ti[r['defense_team']]] = 1.0
            X[k, 1 + 2 * n] = 1.0 if r['offense_is_home'] else 0.0
            yv[k] = r['epa']
        return X, yv

    per_fold = {float(l): [] for l in grid}
    fold_info = []
    for w in folds:
        tr = [r for r in kept if r['week'] < w]
        te = [r for r in kept if r['week'] == w]
        if not tr or not te:
            continue
        # THE ORDINAL GUARD, AS AN ASSERTION.
        assert max(r['week'] for r in tr) < w, \
            f'fold {w} fitting set reaches week {max(r["week"] for r in tr)}'
        Xtr, ytr = mat(tr)
        Xte, yte = mat(te)
        for l in grid:
            th = ridge(Xtr, ytr, l)
            per_fold[float(l)].append(float(np.abs(yte - Xte @ th).mean()))
        # THE PER-FOLD RANK, RECORDED. An early fold trains on one week and is
        # structurally unidentified: measured on 2025 pass, the week-2 fold
        # trains on 1,164 plays at rank 32 of 66, deficiency 34. Its estimates
        # are the penalty's choices. Recording rank per fold is what stops a
        # chain average from hiding which folds were identified -- and it is
        # why `n_folds_identified` travels with the selection.
        rk = int(np.linalg.matrix_rank(Xtr))
        fold_info.append({'week': int(w), 'n_train': len(tr),
                          'n_test': len(te), 'train_rank': rk,
                          'train_cols': int(Xtr.shape[1]),
                          'train_deficiency': int(Xtr.shape[1] - rk),
                          'train_identified': int(Xtr.shape[1] - rk) == 2})
    means = {l: float(np.mean(v)) for l, v in per_fold.items() if v}
    ses = {l: float(np.std(v, ddof=1) / np.sqrt(len(v)))
           for l, v in per_fold.items() if len(v) > 1}
    best = min(means, key=lambda l: means[l])
    thresh = means[best] + ses.get(best, 0.0)
    within = [l for l in means if means[l] <= thresh]
    chosen = max(within)          # THE PRE-DECLARED TIE-BREAK
    ev = {'spec_version': SPEC_VERSION, 'play_class': play_class,
          'grid': [float(x) for x in grid], 'n_folds': len(fold_info),
          'folds': fold_info, 'fold_weeks': [f['week'] for f in fold_info],
          'mae_by_lambda': {str(k): v for k, v in sorted(means.items())},
          'se_by_lambda': {str(k): v for k, v in sorted(ses.items())},
          'best_lambda_by_score': float(best),
          'best_score': means[best],
          'one_se_threshold': thresh,
          'within_one_se': sorted(float(x) for x in within),
          'tie_break': TIE_BREAK,
          'chosen_lambda': float(chosen),
          'chosen_is_more_shrunken_than_best': chosen >= best,
          'grid_boundary': grid_boundary_check(chosen, grid),
          'n_folds_identified': sum(1 for f in fold_info
                                    if f['train_identified']),
          'n_folds_unidentified': sum(1 for f in fold_info
                                      if not f['train_identified']),
          'unidentified_fold_weeks': [f['week'] for f in fold_info
                                      if not f['train_identified']],
          'score_metric': 'mean absolute error on the held-out week'}
    # THE WORDING HERE IS DELIBERATE AND IT WAS WRONG ONCE. An earlier version
    # read "best score at {best:g}", where `best` is the best LAMBDA, so the
    # line printed "best score at 151.991" for a target whose scale is about
    # 1.15 -- and I misdiagnosed it as a numeric blow-up before checking. The
    # score and the lambda are now labelled separately.
    return Outcome.ok(
        'OAS1_LAMBDA_SELECTED', value=float(chosen),
        detail=f'{play_class}: lambda {chosen:g} chosen from {len(means)} '
               f'grid point(s) over {len(fold_info)} forward fold(s); the '
               f'best-scoring lambda was {best:g} at MAE {means[best]:.5f}, '
               f'and {len(within)} of {len(means)} grid points fall within '
               f'1 SE of it, so the surface is flat and the tie-break decides',
        **ev)


def fit_season(rows, *, play_class: str, lam: float,
               allow_unidentified: bool = False,
               unidentified_reason: str = '') -> Outcome:
    """One season, one play class. Refuses an unidentified design by default."""
    ident = DS.identify(rows, play_class=play_class)
    if ident.state is not State.PASS and not allow_unidentified:
        return Outcome.blocked(
            CODE_UNIDENTIFIED,
            f'refusing to fit: {ident.detail}',
            cause=Cause.DATA, identification=ident.evidence)
    if ident.state is not State.PASS and not unidentified_reason:
        return Outcome.fail(
            CODE_UNIDENTIFIED,
            'allow_unidentified was set without a reason. A deliberate fit on '
            'an unidentified design must say why in the artifact.',
            cause=Cause.GOVERNANCE)
    d = DS.build(rows, play_class=play_class)
    if d.state is not State.PASS:
        return d
    X, teams, sub = d.value['X'], d.value['teams'], d.value['rows']
    y = np.asarray([r['epa'] for r in sub], float)
    try:
        theta = ridge(X, y, lam)
    except np.linalg.LinAlgError as e:
        return Outcome.fail(CODE_SINGULAR, f'ridge solve failed: {e}')
    se, n_cl = cluster_se(X, y, theta, lam,
                          [r['game_id'] for r in sub])
    c = center_within_family(theta, len(teams))
    resid = y - X @ theta
    n_off = {t: sum(1 for r in sub if r['offense_team'] == t) for t in teams}
    n_def = {t: sum(1 for r in sub if r['defense_team'] == t) for t in teams}
    units = []
    for i, t in enumerate(teams):
        units.append({
            'team': t, 'unit': f'off_{play_class}',
            'strength': float(c['offense'][i]),
            'strength_uncentered': float(c['offense_raw'][i]),
            'se_clustered_by_game': float(se[1 + i]),
            'n_plays': int(n_off[t])})
        units.append({
            'team': t, 'unit': f'def_{play_class}',
            'strength': float(c['defense'][i]),
            'strength_uncentered': float(c['defense_raw'][i]),
            'se_clustered_by_game': float(se[1 + len(teams) + i]),
            'n_plays': int(n_def[t])})
    ev = {'spec_version': SPEC_VERSION, 'play_class': play_class,
          'lambda': float(lam), 'n_rows': int(X.shape[0]),
          'n_teams': len(teams), 'n_game_clusters': int(n_cl),
          'intercept': c['intercept'], 'intercept_se': float(se[0]),
          'home': c['home'], 'home_se': float(se[-1]),
          'identified': ident.state is State.PASS,
          'identification': ident.evidence,
          'allow_unidentified': bool(allow_unidentified),
          'unidentified_reason': unidentified_reason or None,
          'residual_sd': float(resid.std(ddof=1)),
          'in_sample_mae': float(np.abs(resid).mean()),
          'sign_convention': DS.SIGN_CONVENTION,
          'centering': 'coefficients centred within unit family for '
                       'reporting; a relabelling, not a refit',
          'offense_shift': c['offense_shift'],
          'defense_shift': c['defense_shift']}
    return Outcome.ok(
        CODE_OK, value={'units': units, 'theta': theta.tolist(),
                        'teams': teams, **ev},
        detail=f'{play_class}: {X.shape[0]} row(s), lambda {lam:g}, '
               f'{len(teams)} club(s), {n_cl} game cluster(s), home '
               f'{c["home"]:+.4f} (SE {se[-1]:.4f})',
        **ev)
