"""The Week-2 OAS1 fitting body. Research-only, and it does not score itself.

`fit_week2.py` has run thirteen preflight checks and then raised
"the fitting body is not implemented in this pass" since it was written. This
is that body.

WHAT IT FITS

The construction the pre-registration declares, and not the one the data
invites. 2026 week 1 alone is rank 32 of 66 with 32 two-node graph components,
so 32 dimensions of a week-1 ridge carry no information; a fit presented as
having learned separate offense and defense strengths from it would be
reporting the penalty's choices. So the prior-season identified strengths do
the identifying and week 1 updates them, with the prior entering exactly as
`WEEK2_FIT_CONFIG.json` says: weighted pseudo-observations, one per unit,
response `rho * theta_prev[u]`, weight `kappa`.

THREE THINGS THIS MODULE DECIDED, EACH RECORDED BECAUSE EACH COULD HAVE GONE
THE OTHER WAY

**1. The inner chain's prior is per fold, and the obvious version leaks.**
The natural implementation gives every inner fold the committed 2025 prior.
That prior is fitted on ALL of 2025, so a fold forecasting 2025 week 12 would
carry weeks 12 through 18 inside its own prior -- the rest of the season
leaking backwards. Measured consequence: it would flatter every configuration
that leans on the prior, which is exactly the `kappa` and `rho` axes being
selected. So each fold takes the prior of the season before ITS OWN season:
2024 for the 2025 folds, 2025 for the 2026 fold. That is the declared
carryover depth of one prior season applied to every fold instead of only to
the last one, and it is why `prior_season.build` had to exist.

**2. Garbage-time rules change the rowset, so they are scored on the common
one.** `search_spaces.garbage_time` asks for three rules to be searched while
`IDENTICAL_ROWSETS_REQUIRED` forbids comparing scores computed on different
rows -- and a mean absolute error over different plays is not a comparison at
all. Resolved by scoring EVERY configuration on the intersection of the rows
kept under all three rules, while each configuration still TRAINS under its own
rule. The alternative -- fixing the rule at `none` and not searching it -- was
available and is narrower than the pre-registration asks for. This is an
interpretation of an ambiguity, it is recorded in the artifact as one, and it
is reversible.

**3. `rho` is unidentified at `kappa = 0` and the tie-break decides it.**
With no prior weight, every `rho` gives the identical fit and the identical
score. The amended tie-break order is ('max lambda', 'max kappa', 'min rho'),
so `rho` is decided last and lands on the grid minimum. The artifact records
`rho_identified_at_chosen_kappa` so nobody reads 0.5 as a measurement.

WHAT IT DOES NOT DO, AND CANNOT HERE

It does not score OAS1 against B5. Scoring a Week-2 forecast needs Week-2
plays, and the captured 2026 blob carries week 1 only -- 2,756 rows, all week
1, verified rather than assumed. Those bytes are outside this checkout, so the
scoring half is ASSIGNED rather than blocked and the request is written into
`docs/AGENT_OUTBOX.md`. The artifact carries `SCORE_NOT_COMPUTABLE_HERE` with
the reason, and no hurdle is recorded as passed, failed or waived.

And it promotes nothing. Both OAS1 adjustment ids are RESEARCH_ONLY in the
registry; the artifact carries `research_only: true` and
`downstream_authorized: false`.
"""
from __future__ import annotations

import datetime as _dt
import itertools
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.research.oas1 import amendment as AM                        # noqa: E402
from nfl.research.oas1 import frame as FR                            # noqa: E402
from nfl.research.oas1 import preregistration as PRE                 # noqa: E402
from nfl.research.oas1 import prior_season as PS                     # noqa: E402

SPEC_VERSION = 'oas1-week2-fit-1'

CODE_OK = 'OAS1_WEEK2_FITTED'
CODE_NO_FOLDS = 'OAS1_WEEK2_NO_INNER_FOLDS'
CODE_NO_ROWS = 'OAS1_WEEK2_NO_TRAINING_ROWS'
CODE_PRIOR = 'OAS1_WEEK2_PRIOR_UNAVAILABLE'
CODE_NO_SCORE = 'OAS1_WEEK2_SCORE_NOT_COMPUTABLE_HERE'

CLASSES = ('pass', 'rush')
#: The prior is built at gt_rule 'none' whatever the candidate's own rule is,
#: matching the committed 2025 artifact exactly. Rebuilding the prior per rule
#: would make `theta_prev` a function of the axis being searched, so a
#: configuration would be compared against a different prior rather than a
#: different treatment.
PRIOR_GT_RULE = 'none'


def _ordinal(season, week) -> int:
    return int(season) * 100 + int(week)


def training_frames(gt_rules, *, forecast_ordinal: int) -> Outcome:
    """One frame per garbage-time rule over the training seasons.

    Every row with `ordinal >= forecast_ordinal` is dropped HERE, once, so no
    later step can reach past the cut by forgetting to filter.
    """
    out, prov = {}, {}
    for g in gt_rules:
        rows = []
        for season in PRE.TRAINING_SEASONS:
            rel = PS.BLOBS.get(int(season))
            if rel is None or not (_REPO / rel).exists():
                return Outcome.blocked(
                    CODE_NO_ROWS,
                    f'training season {season} has no captured blob',
                    cause=Cause.DATA)
            blob = _REPO / rel
            sha = PS._sha_of(blob)
            f = FR.build(blob, vintage_sha256=sha, gt_rule=g, reg_only=True)
            if f.state is not State.PASS:
                return Outcome.fail(CODE_NO_ROWS,
                                    f'{season} {g}: {f.code}: {f.detail}')
            r = f.value['rows'] if isinstance(f.value, dict) else f.value
            rows.extend(r)
            prov[str(season)] = {'blob': rel, 'sha256': sha}
        out[g] = [x for x in rows if x['ordinal'] < forecast_ordinal]
    return Outcome.ok('OAS1_WEEK2_FRAMES_BUILT', value={'by_rule': out,
                                                        'provenance': prov})


def _keep(rows, play_class):
    return [r for r in rows
            if r.get('play_class') == play_class
            and r.get('excluded_reason') == 'none'
            and r.get('offense_team') and r.get('defense_team')
            and r.get('epa') is not None]


def common_keys(by_rule, play_class) -> set:
    """Plays kept under EVERY garbage-time rule.

    The comparison rowset. `IDENTICAL_ROWSETS_REQUIRED` is in the
    pre-registration and a mean absolute error over different plays is not a
    comparison; each rule still trains on its own rows.
    """
    sets = []
    for g, rows in by_rule.items():
        sets.append({(r['game_id'], r['play_id']) for r in _keep(rows,
                                                                play_class)})
    return set.intersection(*sets) if sets else set()


def _matrices(rows, teams_index, n_teams):
    """[intercept | offense | defense | home]. The declared design."""
    n = len(rows)
    X = np.zeros((n, 2 + 2 * n_teams))
    y = np.zeros(n)
    for k, r in enumerate(rows):
        X[k, 0] = 1.0
        X[k, 1 + teams_index[r['offense_team']]] = 1.0
        X[k, 1 + n_teams + teams_index[r['defense_team']]] = 1.0
        X[k, -1] = 1.0 if r['offense_is_home'] else 0.0
        y[k] = float(r['epa'])
    return X, y


def penalty_vector(n_teams: int) -> np.ndarray:
    """Ridge penalises the two team families and NOTHING else.

    `intercept_penalised: false` and `home_penalised: false` are both in the
    config. Penalising the intercept shrinks the league mean toward zero, which
    is a different model and not the declared one.
    """
    p = np.ones(2 + 2 * n_teams)
    p[0] = 0.0
    p[-1] = 0.0
    return p


def prior_vector(theta_prev: dict, teams, play_class: str):
    """`theta_prev` laid out on the design's columns, plus a mask.

    A unit with no prior -- a club absent from the prior season -- gets NO
    pseudo-observation rather than a zero one. A zero pseudo-observation is not
    "no information", it is the assertion that the unit is exactly league
    average, and asserting that about a club we have never seen is the
    cold-start defect this project has already paid for once.
    """
    n = len(teams)
    v = np.zeros(2 + 2 * n)
    m = np.zeros(2 + 2 * n)
    missing = []
    for i, t in enumerate(teams):
        for off, col in ((True, 1 + i), (False, 1 + n + i)):
            key = (t, f'{"off" if off else "def"}_{play_class}')
            if key in theta_prev:
                v[col] = float(theta_prev[key])
                m[col] = 1.0
            else:
                missing.append(f'{t}/{key[1]}')
    return v, m, missing


def solve(XtX, Xty, *, lam: float, kappa: float, rho: float,
          pen: np.ndarray, prior_v: np.ndarray, prior_m: np.ndarray):
    """One augmented ridge solve from precomputed normal equations.

    The pseudo-observations are a diagonal addition and a right-hand-side
    addition, which is why 864 configurations cost 864 tiny solves and not 864
    passes over thirty thousand plays.
    """
    A = XtX + np.diag(lam * pen + kappa * prior_m)
    b = Xty + kappa * rho * prior_v * prior_m
    return np.linalg.solve(A, b)


def _shrink_key(cfg):
    """The AMENDED tie-break, read from `amendment`, never restated here."""
    order = AM.AMENDED_TIE_BREAK_ORDER
    key = []
    for axis in order:
        if axis == 'max lambda':
            key.append(cfg['lambda'])
        elif axis == 'max kappa':
            key.append(cfg['kappa'])
        elif axis == 'min rho':
            key.append(-cfg['rho'])
        else:
            raise ValueError(f'undeclared tie-break axis {axis!r}')
    return tuple(key)


def inner_chain(by_rule, *, play_class: str, inner_k: int = PRE.INNER_K,
                forecast_ordinal: int) -> Outcome:
    """Forward-chained selection over (lambda, kappa, rho, garbage_time)."""
    space = AM.effective_space()
    lams = [float(x) for x in space['lambda']]
    kaps = [float(x) for x in space['kappa']]
    rhos = [float(x) for x in space['rho']]
    gts = [str(g) for g in space['garbage_time']]

    base = by_rule[gts[0]]
    ords = sorted({r['ordinal'] for r in _keep(base, play_class)})
    folds = [o for o in ords if any(x < o for x in ords)][-inner_k:]
    if len(folds) < 2:
        return Outcome.fail(
            CODE_NO_FOLDS,
            f'{play_class}: {len(folds)} usable inner fold(s). The declared '
            f'selection is forward-chained and cannot run on fewer than two.',
            n_ordinals=len(ords))

    teams = sorted({r['offense_team'] for g in gts
                    for r in _keep(by_rule[g], play_class)}
                   | {r['defense_team'] for g in gts
                      for r in _keep(by_rule[g], play_class)})
    ti = {t: i for i, t in enumerate(teams)}
    nT = len(teams)
    pen = penalty_vector(nT)
    keys_common = common_keys(by_rule, play_class)

    per_cfg: dict = {}
    fold_info, prior_used = [], {}
    for o in folds:
        prior_season = o // 100 - 1
        pr = PS.build(prior_season, gt_rule=PRIOR_GT_RULE)
        if pr.state is not State.PASS:
            return Outcome.blocked(
                CODE_PRIOR,
                f'fold {o} needs the {prior_season} prior and it is '
                f'unavailable: {pr.code}: {pr.detail}',
                cause=Cause.DATA, fold=o, prior_season=prior_season)
        prior_used[str(o)] = {'prior_season': prior_season,
                              'blob_sha256': pr.value['blob_sha256']}
        pv, pm, pmiss = prior_vector(pr.value['theta_prev'], teams, play_class)
        te_rows = [r for r in _keep(by_rule[gts[0]], play_class)
                   if r['ordinal'] == o
                   and (r['game_id'], r['play_id']) in keys_common]
        if not te_rows:
            continue
        Xte, yte = _matrices(te_rows, ti, nT)
        info = {'ordinal': int(o), 'n_test_common': len(te_rows),
                'prior_season': prior_season,
                'n_units_without_prior': len(pmiss), 'by_rule': {}}
        for g in gts:
            tr = [r for r in _keep(by_rule[g], play_class)
                  if r['ordinal'] < o]
            if not tr:
                continue
            # THE ORDINAL GUARD, AS AN ASSERTION, not a comment.
            assert max(r['ordinal'] for r in tr) < o, \
                f'fold {o} training set reaches {max(r["ordinal"] for r in tr)}'
            assert o < forecast_ordinal, \
                f'inner fold {o} is not strictly before the forecast'
            Xtr, ytr = _matrices(tr, ti, nT)
            XtX = Xtr.T @ Xtr
            Xty = Xtr.T @ ytr
            rk = int(np.linalg.matrix_rank(Xtr))
            info['by_rule'][g] = {
                'n_train': len(tr), 'train_rank': rk,
                'train_cols': int(Xtr.shape[1]),
                'train_deficiency': int(Xtr.shape[1] - rk),
                'train_identified': int(Xtr.shape[1] - rk)
                == PRE.STRUCTURAL_DEFICIENCY}
            for lam, kap, rho in itertools.product(lams, kaps, rhos):
                th = solve(XtX, Xty, lam=lam, kappa=kap, rho=rho,
                           pen=pen, prior_v=pv, prior_m=pm)
                mae = float(np.abs(yte - Xte @ th).mean())
                per_cfg.setdefault((lam, kap, rho, g), []).append(mae)
        fold_info.append(info)

    if not per_cfg:
        return Outcome.fail(CODE_NO_FOLDS,
                            f'{play_class}: no fold produced a score')
    n_folds = max(len(v) for v in per_cfg.values())
    full = {k: v for k, v in per_cfg.items() if len(v) == n_folds}
    means = {k: float(np.mean(v)) for k, v in full.items()}
    ses = {k: float(np.std(v, ddof=1) / np.sqrt(len(v)))
           for k, v in full.items() if len(v) > 1}
    best = min(means, key=lambda k: means[k])
    thresh = means[best] + ses.get(best, 0.0)
    within = [k for k in means if means[k] <= thresh]
    cfgs = [{'lambda': k[0], 'kappa': k[1], 'rho': k[2], 'garbage_time': k[3]}
            for k in within]
    chosen_cfg = max(cfgs, key=_shrink_key)
    gt_in_tie = sorted({c['garbage_time'] for c in cfgs})
    after = [c for c in cfgs if _shrink_key(c) == _shrink_key(chosen_cfg)]
    gt_undecided = sorted({c['garbage_time'] for c in after})
    ev = {
        'spec_version': SPEC_VERSION, 'play_class': play_class,
        'n_configurations': len(means), 'n_inner_folds': n_folds,
        'fold_ordinals': [f['ordinal'] for f in fold_info],
        'folds': fold_info,
        'prior_per_fold': prior_used,
        'n_common_scoring_rows': len(keys_common),
        'best_config_by_score': {'lambda': best[0], 'kappa': best[1],
                                 'rho': best[2], 'garbage_time': best[3]},
        'best_score_mae': means[best],
        'one_se_threshold': thresh,
        'n_within_one_se': len(within),
        'tie_break_order': list(AM.AMENDED_TIE_BREAK_ORDER),
        'chosen_config': chosen_cfg,
        'chosen_score_mae': means[(chosen_cfg['lambda'], chosen_cfg['kappa'],
                                   chosen_cfg['rho'],
                                   chosen_cfg['garbage_time'])],
        'garbage_time_values_within_one_se': gt_in_tie,
        'garbage_time_still_tied_after_declared_axes': (
            gt_undecided if len(gt_undecided) > 1 else []),
        'rho_identified_at_chosen_kappa': chosen_cfg['kappa'] > 0.0,
        'scoring_rowset':
            'the intersection of rows kept under every garbage-time rule; '
            'each rule trains on its own rows',
        'metric': 'mean absolute error on the held-out ordinal',
    }
    ev['undecided_axis'] = 'garbage_time' if len(gt_undecided) > 1 else None
    ev['undecided_variants'] = [
        dict(chosen_cfg, garbage_time=g) for g in gt_undecided]
    ev['undecided_variant_scores'] = {
        g: means[(chosen_cfg['lambda'], chosen_cfg['kappa'],
                  chosen_cfg['rho'], g)] for g in gt_undecided}
    if len(gt_undecided) > 1:
        # AN UNDECLARED TIE-BREAK IS NOT MINE TO INVENT, AND I HAVE NOW SEEN
        # THE SCORES.
        #
        # `garbage_time` is in the declared search space and in NEITHER
        # tie-break order -- not the original five-axis one and not the
        # amended three-axis one. It is a pre-existing gap in the
        # pre-registration, found by executing it rather than by reading it.
        #
        # The rules are not degenerate: measured on the captured blobs, rule A
        # drops 425 plays of 2025 and 13 of 2026, rule B drops 1,393 and 102,
        # against 0 for `none`. So they train on different rows and score
        # differently, and the declared procedure cannot choose between them.
        #
        # Writing a rule now would be a selection rule written after seeing the
        # scores, which is the thing the one-SE rule and the tie-break exist to
        # prevent. So the axis is left UNDECIDED, every tied variant is fitted,
        # and the artifact reports how far apart they actually are -- which
        # turns "we cannot choose" into a measurement of whether the choice
        # moves anything.
        return Outcome.blocked(
            'OAS1_WEEK2_TIE_BREAK_UNDECLARED',
            f'{play_class}: after the declared axes {gt_undecided} remain '
            f'tied on garbage_time, and neither tie-break order declares a '
            f'rule for it. Every tied variant is fitted and none is selected.',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok(
        'OAS1_WEEK2_CONFIG_SELECTED', value=chosen_cfg,
        detail=f'{play_class}: {chosen_cfg} from {len(means)} configuration(s) '
               f'over {n_folds} inner fold(s); {len(within)} within one SE of '
               f'the best ({means[best]:.5f}), so the tie-break decides',
        **ev)


def fit(play_class: str, by_rule, cfg, *, forecast_ordinal: int) -> Outcome:
    """The Week-2 estimate at the selected configuration."""
    rows = [r for r in _keep(by_rule[cfg['garbage_time']], play_class)
            if r['ordinal'] < forecast_ordinal]
    if not rows:
        return Outcome.fail(CODE_NO_ROWS, f'{play_class}: no training rows')
    assert max(r['ordinal'] for r in rows) < forecast_ordinal
    prior_season = forecast_ordinal // 100 - 1
    pr = PS.build(prior_season, gt_rule=PRIOR_GT_RULE)
    if pr.state is not State.PASS:
        return Outcome.blocked(CODE_PRIOR, f'{pr.code}: {pr.detail}',
                               cause=Cause.DATA)
    teams = sorted({r['offense_team'] for r in rows}
                   | {r['defense_team'] for r in rows})
    ti = {t: i for i, t in enumerate(teams)}
    nT = len(teams)
    X, y = _matrices(rows, ti, nT)
    pen = penalty_vector(nT)
    pv, pm, pmiss = prior_vector(pr.value['theta_prev'], teams, play_class)
    rk = int(np.linalg.matrix_rank(X))
    theta = solve(X.T @ X, X.T @ y, lam=cfg['lambda'], kappa=cfg['kappa'],
                  rho=cfg['rho'], pen=pen, prior_v=pv, prior_m=pm)
    cur = [r for r in rows if r['ordinal'] >= PRE.FORECAST_SEASON * 100]
    n_cur_off = {t: sum(1 for r in cur if r['offense_team'] == t)
                 for t in teams}
    n_cur_def = {t: sum(1 for r in cur if r['defense_team'] == t)
                 for t in teams}
    n_all_off = {t: sum(1 for r in rows if r['offense_team'] == t)
                 for t in teams}
    off = theta[1:1 + nT]
    dfn = theta[1 + nT:1 + 2 * nT]
    units = []
    for i, t in enumerate(teams):
        for label, vals, ncur in (('off', off, n_cur_off),
                                  ('def', dfn, n_cur_def)):
            units.append({
                'season': PRE.FORECAST_SEASON, 'week': PRE.FORECAST_WEEK,
                'team': t, 'unit': f'{label}_{play_class}',
                'strength': float(vals[i] - float(vals.mean())),
                'strength_uncentered': float(vals[i]),
                'n_plays_current_season': int(ncur[t]),
                'n_plays_training': int(n_all_off[t]),
                'prior_weight_effective': float(cfg['kappa']),
                'prior_response': float(
                    cfg['rho'] * pr.value['theta_prev'].get(
                        (t, f'{label}_{play_class}'), 0.0)),
                'has_prior': (t, f'{label}_{play_class}')
                             in pr.value['theta_prev'],
                'design_rank': rk, 'design_cols': int(X.shape[1]),
                'identified': int(X.shape[1] - rk)
                == PRE.STRUCTURAL_DEFICIENCY,
                'cfg_lambda': cfg['lambda'], 'cfg_kappa': cfg['kappa'],
                'cfg_rho': cfg['rho'],
                'cfg_garbage_time': cfg['garbage_time'],
                'fit_vintage': pr.value['blob_sha256'][:16]})
    return Outcome.ok(
        CODE_OK,
        value={'units': units, 'teams': teams,
               'intercept': float(theta[0]), 'home': float(theta[-1])},
        play_class=play_class, n_rows=len(rows), n_teams=nT,
        design_rank=rk, design_cols=int(X.shape[1]),
        design_deficiency=int(X.shape[1] - rk),
        identified=int(X.shape[1] - rk) == PRE.STRUCTURAL_DEFICIENCY,
        n_units_without_prior=len(pmiss),
        units_without_prior=pmiss[:20],
        prior_season=prior_season,
        prior_blob_sha256=pr.value['blob_sha256'],
        config=dict(cfg), sign_convention=PRE.SIGN_CONVENTION,
        detail=f'{play_class}: {len(rows)} training row(s) over {nT} club(s), '
               f'rank {rk}/{X.shape[1]}, home {float(theta[-1]):+.4f}')


def _variant_spread(fits_by_gt, units) -> dict:
    """How far apart the undecided variants actually are.

    An undecided axis matters only if it moves the numbers. This reports the
    maximum absolute difference in unit strength across the tied variants, so
    a reader can tell an unresolved choice that changes nothing from one that
    changes the answer. It does NOT select on it: a small spread is a reason to
    stop worrying, never a reason to pick.
    """
    if len(fits_by_gt) < 2:
        return {'n_variants': len(fits_by_gt), 'max_abs_difference': None,
                'note': 'one variant; nothing to compare'}
    by_unit: dict = {}
    for u in units:
        by_unit.setdefault((u['team'], u['unit']), {})[
            u['cfg_garbage_time']] = u['strength']
    diffs = {}
    for k, vals in by_unit.items():
        if len(vals) >= 2:
            diffs[f'{k[0]}/{k[1]}'] = max(vals.values()) - min(vals.values())
    if not diffs:
        return {'n_variants': len(fits_by_gt), 'max_abs_difference': None}
    worst = max(diffs, key=lambda k: abs(diffs[k]))
    vals = [abs(v) for v in diffs.values()]
    return {'n_variants': len(fits_by_gt), 'n_units_compared': len(diffs),
            'max_abs_difference': float(max(vals)),
            'mean_abs_difference': float(sum(vals) / len(vals)),
            'widest_unit': worst,
            'interpretation': 'the spread across the tied garbage-time '
                              'variants. It measures how much the undecided '
                              'axis moves the estimate; it is not a selection '
                              'criterion.'}


def score_availability(forecast_ordinal: int) -> Outcome:
    """Can this checkout score the Week-2 forecast? Measured, not assumed."""
    rel = PS.BLOBS.get(int(PRE.FORECAST_SEASON))
    blob = _REPO / rel if rel else None
    if blob is None or not blob.exists():
        return Outcome.blocked(
            CODE_NO_SCORE, f'no {PRE.FORECAST_SEASON} capture exists',
            cause=Cause.DATA)
    sha = PS._sha_of(blob)
    f = FR.build(blob, vintage_sha256=sha, gt_rule='none', reg_only=True)
    if f.state is not State.PASS:
        return Outcome.fail(CODE_NO_SCORE, f'{f.code}: {f.detail}')
    rows = f.value['rows'] if isinstance(f.value, dict) else f.value
    weeks = sorted({r['week'] for r in rows})
    n_at = sum(1 for r in rows if r['ordinal'] == forecast_ordinal)
    if n_at:
        return Outcome.ok('OAS1_WEEK2_OUTCOMES_PRESENT',
                          value={'n_rows_at_forecast_ordinal': n_at},
                          weeks_captured=weeks)
    return Outcome.blocked(
        CODE_NO_SCORE,
        f'the captured {PRE.FORECAST_SEASON} play-by-play carries weeks '
        f'{weeks} and zero rows at ordinal {forecast_ordinal}. The Week-2 '
        f'plays are not in this checkout, so OAS1 cannot be scored against B5 '
        f'here. This is ASSIGNED, not blocked: the bytes exist outside this '
        f'repository and the request is in docs/AGENT_OUTBOX.md. No hurdle is '
        f'recorded as passed, failed or waived.',
        cause=Cause.DATA, weeks_captured=weeks,
        blob=rel, blob_sha256=sha,
        n_rows_at_forecast_ordinal=0)


def run() -> Outcome:
    fo = _ordinal(PRE.FORECAST_SEASON, PRE.FORECAST_WEEK)
    space = AM.effective_space()
    fr = training_frames([str(g) for g in space['garbage_time']],
                         forecast_ordinal=fo)
    if fr.state is not State.PASS:
        return fr
    by_rule = fr.value['by_rule']
    out = {'spec_version': SPEC_VERSION,
           'artifact': 'OAS1_WEEK2_RESULT',
           'built_at': _dt.datetime.now(_dt.timezone.utc).isoformat(),
           'candidate_identity': 'V1_CANDIDATE_OAS1_W2',
           'forecast': {'season': PRE.FORECAST_SEASON,
                        'week': PRE.FORECAST_WEEK, 'ordinal': fo},
           'research_only': True, 'downstream_authorized': False,
           'promoted': False,
           'training_provenance': fr.value['provenance'],
           'prior_gt_rule': PRIOR_GT_RULE,
           'selection': {}, 'fits': {}, 'units': [],
           'interpretations': [
               {'id': 'PER_FOLD_PRIOR',
                'decision': 'each inner fold takes the prior of the season '
                            'before its own season, not the committed 2025 '
                            'prior',
                'why': 'the 2025 prior is fitted on all of 2025, so giving it '
                       'to a 2025 fold leaks the rest of that season '
                       'backwards into the fold, and it would flatter exactly '
                       'the kappa and rho axes being selected'},
               {'id': 'COMMON_SCORING_ROWSET',
                'decision': 'every configuration is scored on the '
                            'intersection of rows kept under all three '
                            'garbage-time rules; each trains on its own rows',
                'why': 'the search space asks for the rule to be searched '
                       'while IDENTICAL_ROWSETS_REQUIRED forbids comparing '
                       'scores over different rows. The alternative -- fixing '
                       'the rule at none and not searching it -- was '
                       'available and is narrower than the pre-registration '
                       'asks for'},
           ]}
    out['selection_complete'] = True
    for cls in CLASSES:
        sel = inner_chain(by_rule, play_class=cls, forecast_ordinal=fo)
        out['selection'][cls] = {k: v for k, v in sel.evidence.items()
                                 if k != 'folds'}
        out['selection'][cls]['folds'] = sel.evidence.get('folds')
        out['selection'][cls]['state'] = sel.state.value
        out['selection'][cls]['code'] = sel.code
        if sel.state is State.PASS:
            variants = [sel.value]
        elif sel.code == 'OAS1_WEEK2_TIE_BREAK_UNDECLARED':
            out['selection_complete'] = False
            variants = sel.evidence['undecided_variants']
        else:
            return Outcome.fail(sel.code, sel.detail, **out)
        out['fits'][cls] = {}
        for v in variants:
            f = fit(cls, by_rule, v, forecast_ordinal=fo)
            if f.state is not State.PASS:
                return Outcome.fail(f.code, f.detail, **out)
            tag = v['garbage_time']
            out['fits'][cls][tag] = {k: q for k, q in f.evidence.items()}
            out['fits'][cls][tag]['intercept'] = f.value['intercept']
            out['fits'][cls][tag]['home'] = f.value['home']
            out['fits'][cls][tag]['selected'] = len(variants) == 1
            out['units'].extend(f.value['units'])
        out['fits'][cls]['variant_spread'] = _variant_spread(
            {v['garbage_time']: out['fits'][cls][v['garbage_time']]
             for v in variants},
            [u for u in out['units'] if u['unit'].endswith(cls)])
    sc = score_availability(fo)
    out['scoring'] = {
        'state': sc.state.value, 'code': sc.code, 'detail': sc.detail,
        'evidence': {k: v for k, v in sc.evidence.items()
                     if k != 'rows'},
        'hurdles_evaluated': False,
        'hurdle_status': 'NOT_EVALUATED -- not passed, not failed, not waived',
    }
    out['n_units'] = len(out['units'])
    if not out['selection_complete']:
        out['candidate_status'] = (
            'NOT SELECTED. The pre-registration declares garbage_time as a '
            'search axis and no tie-break for it, in either the original or '
            'the amended order. Every tied variant is fitted and reported; '
            'none is the Week-2 candidate until the tie-break is declared, '
            'and it may not be declared by whoever has seen these scores.')
    else:
        out['candidate_status'] = 'SELECTED BY THE DECLARED PROCEDURE'
    return Outcome.ok(
        CODE_OK, value=out,
        detail=f'{len(out["units"])} unit(s) over {len(CLASSES)} class(es); '
               f'scoring {sc.state.value}[{sc.code}]',
        n_units=len(out['units']), scoring_state=sc.state.value,
        scoring_code=sc.code)


def main() -> int:
    o = run()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is State.PASS:
        p = _REPO / 'nfl/research/oas1/OAS1_WEEK2_RESULT.json'
        p.write_text(json.dumps(o.value, indent=1, sort_keys=True,
                                default=str) + '\n')
        print(f'wrote {p.relative_to(_REPO)}')
        for cls in CLASSES:
            s = o.value['selection'][cls]
            print(f'  {cls}: {s["code"]}; {s["n_configurations"]} config(s), '
                  f'{s["n_within_one_se"]} within 1 SE, '
                  f'MAE {s["chosen_score_mae"]:.5f}')
            if s.get('undecided_axis'):
                print(f'      UNDECIDED on {s["undecided_axis"]}: '
                      f'{s["undecided_variant_scores"]}')
            sp = o.value['fits'][cls].get('variant_spread') or {}
            if sp.get('max_abs_difference') is not None:
                print(f'      variant spread: max |d strength| '
                      f'{sp["max_abs_difference"]:.6f} over '
                      f'{sp["n_units_compared"]} unit(s)')
        print(f'  scoring: {o.value["scoring"]["state"]}'
              f'[{o.value["scoring"]["code"]}]')
    return 0 if o.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
