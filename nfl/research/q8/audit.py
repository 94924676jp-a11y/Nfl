"""Q8 step 1: ATTRIBUTION AUDIT. Rank the five sources before repairing any.

    python3.12 -m nfl.research.q8.audit

THE QUESTION. Q7 established that about 72 % of RC2's confirmed receiving-yard
bias (+2.1801 unconditional, +0.602 given realised receptions) is generated
upstream of receiving efficiency. This ranks WHERE upstream, before anything is
built.

THE CHAIN, and which component each oracle replaces:

    team targets            <- BUDGET
      -> player appears     <- APPEAR
      -> target share       <- CLASS (the prior level)
                               SHRINK (how hard own history is trusted)
      -> renormalise        <- REDIST (what happens after an absence)
      -> player targets
      -> fixed receiving efficiency   (never oracled, never varied)

TWO KINDS OF ORACLE, AND THE DIFFERENCE MATTERS.

  * REALISATION oracles -- BUDGET and APPEAR -- hand the model a game-level
    fact it would have had to predict. Their contribution is "how much error
    comes from not knowing this about this game".
  * PARAMETER oracles -- CLASS, SHRINK, REDIST -- hand the model the right
    POPULATION value, taken as an evaluation-season aggregate, never that
    team-week's own answer. Their contribution is "how much error comes from
    estimating this quantity wrong", not from irreducible game noise.

Mixing the two silently would make the ranking meaningless, so each source is
labelled with its kind on every row of the artifact.

ATTRIBUTION IS EXACT SHAPLEY over all 32 subsets, using the repository's own
`qb2_lib.shapley`. A single ordering would hand the first component every
interaction it shares with the others; averaging over all orderings is what
makes the five numbers add up to the whole.

WHAT IS HELD FIXED, per the directive: team volume is the frozen P4B estimator,
receiving efficiency is one fitted catch rate and one per-catch yardage pool
shared by every configuration, the touchdown layer is untouched, and appearance
is production R8 -- read from the committed Q6 forward chain rather than refit,
so it is literally the same numbers.

NO REPAIR IS BUILT HERE. The audit ranks; the repair comes after, and only the
smallest one the ranking justifies.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import itertools
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b'),
           str(_REPO / 'nfl' / 'research' / 'qb2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p4b_volume as V                                            # noqa: E402
import qb2_lib as QB2                                             # noqa: E402
from nfl.research.q6 import frame as Q6F                          # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                  # noqa: E402
from nfl.research.q7 import panel as Q7P                          # noqa: E402

SPEC_VERSION = 'q8-attribution-audit-1'
HERE = _REPO / 'nfl' / 'research' / 'q8'
Q6_ROWS = _REPO / 'nfl' / 'research' / 'q6' / 'Q6_APPEARANCE_ROWS.csv.gz'
P4B_RESULTS = _REPO / 'nfl' / 'research' / 'p4b' / 'volume_results.json'
DENOM = _REPO / 'nfl' / 'research' / 'inputs' / 'denom_panel.csv.gz'

COMPONENTS = ('BUDGET', 'APPEAR', 'CLASS', 'SHRINK', 'REDIST')
COMPONENT_KIND = {
    'BUDGET': 'REALISATION', 'APPEAR': 'REALISATION',
    'CLASS': 'PARAMETER', 'SHRINK': 'PARAMETER', 'REDIST': 'PARAMETER',
}
COMPONENT_MEANS = {
    'BUDGET': 'the team target budget: how many passes the team threw',
    'APPEAR': 'which players were available, from production R8',
    'CLASS': 'the class-level target-share prior for a position and role class',
    'SHRINK': 'how hard a player\'s own share history is trusted, n/(n+k)',
    'REDIST': 'how an absent teammate\'s share is redistributed',
}
EVAL_SEASONS = (2022, 2023, 2024, 2025)
N_DRAWS = 200
SEED = 20260917
# Declared as a grid, searched only on the evaluation season and only to give
# the SHRINK oracle a value. Nothing in any candidate arm reads it.
K_GRID = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)


def _stream(text):
    import zlib
    return int(zlib.crc32(str(text).encode()) & 0x7FFFFFFF)


def load_p_r8():
    """Production R8's forward-chained appearance probability, as committed."""
    if not Q6_ROWS.exists():
        raise SystemExit(
            f'Q8_R8_APPEARANCE_MISSING: {Q6_ROWS} is absent. The directive '
            f'fixes the appearance mechanism to production R8; refitting it '
            f'here would be a second copy to drift from the first.')
    out = {}
    with gzip.open(Q6_ROWS, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            out[(int(r['season']), int(r['week']), r['team'], r['pid'])] = \
                float(r['p_R8'])
    return out


def load_denom():
    rows = []
    with gzip.open(DENOM, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            for k in ('season', 'week', 'ord'):
                r[k] = int(r[k])
            r['team_targets'] = int(r['team_targets'])
            rows.append(r)
    rows.sort(key=lambda x: (x['ord'], x['team']))
    return rows


def budget_model(denom, season):
    """The frozen P4B team-target estimator, WITH its predictive spread.

    A POINT BUDGET IS NOT WHAT PRODUCTION DOES, and using one here would have
    invented the finding. The first version of this audit handed every draw
    the same integer budget; a budget with no spread under-disperses every
    player's target count, inflates their CRPS, and then hands the whole of
    that inflation to the BUDGET oracle when it is removed. The contribution
    would have been an artefact of the harness rather than a property of the
    system. So the point estimate carries the residual pool it is drawn with,
    exactly as P4B draws it: point + a residual resampled from strictly
    earlier team-games.
    """
    res = json.loads(P4B_RESULTS.read_text())['team_targets']
    if str(season) in res:
        est = res[str(season)]['point_estimator']
    else:
        est = res[str(max(int(k) for k in res if int(k) < season))][
            'point_estimator']
    rows = [dict(r) for r in denom]
    V.attach(rows, 'team_targets')
    cut = season * 100
    hist = [r for r in rows if r['ord'] < cut and r['team_targets'] > 0]
    lm = float(np.mean([r['team_targets'] for r in hist])) if hist else 30.0
    point = {(r['season'], r['week'], r['team']):
             float(V.baselines(r, lm)[est]) for r in rows}
    resid = np.array([r['team_targets'] - point[(r['season'], r['week'],
                                                 r['team'])]
                      for r in hist], float)
    if not len(resid):
        resid = np.array([0.0])
    return point, resid, est


def efficiency_fit(q7_recv, season):
    """ONE catch rate and ONE per-catch yardage pool, shared by every config.

    The directive holds receiving efficiency fixed. It is fitted once per
    evaluation season on strictly earlier seasons and then handed unchanged to
    all thirty-two oracle configurations, so no difference between them can be
    an efficiency difference.
    """
    tr = [r for r in q7_recv if r['season'] < season]
    tg = sum(r['targets'] for r in tr)
    rc = sum(r['rec'] for r in tr)
    pool = np.array([y for r in tr for y in r['rec_yards_list']], float)
    if not len(pool):
        pool = np.array([10.0])
    return {'catch_rate': (rc / tg) if tg else 0.62, 'yard_pool': pool,
            'n_pool': int(len(pool))}


def _yards(T, eff, rng):
    """Receiving yards for a (draws, players) target matrix. Exact, vectorised.

    Receptions are binomial in the targets; each reception then draws its own
    yardage from the per-catch pool. RC1 measured skew 2.197 and excess
    kurtosis 7.830 on that quantity with the Gaussian tail thirteen times too
    thin, so it is resampled per catch and never parameterised.
    """
    R = rng.binomial(np.maximum(T, 0).astype(int), eff['catch_rate'])
    flat = R.reshape(-1)
    total = int(flat.sum())
    if total == 0:
        return np.zeros(T.shape, float)
    draws = eff['yard_pool'][rng.integers(0, len(eff['yard_pool']), total)]
    ends = np.cumsum(flat)
    starts = ends - flat
    csum = np.concatenate([[0.0], np.cumsum(draws)])
    out = (csum[ends] - csum[starts]).reshape(T.shape)
    return out


# ------------------------------------------------------------- the ladder
def _crps(draws, y):
    return float(V.crps_samples(np.asarray(draws, float).reshape(1, -1),
                                np.array([float(y)]))[0])


def _own_history(rows):
    """Each row's own trailing target share, from strictly earlier games."""
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: (x['s'], x['w'], x['t'], x['pid'])):
        h = hist[r['pid']]
        r['own_n'] = len(h)
        r['own_share'] = float(np.mean(h[-Q6F.TRAIL:])) if h else None
        if r['appeared'] and r.get('share_targets') is not None:
            hist[r['pid']].append(r['share_targets'])
    return rows


def attach_receiving(rows, q7_recv):
    """Realised receiving yards onto the appearance frame, by exact key.

    A frame row with no receiver panel row took no target, so its realised
    receiving yardage is ZERO BY ABSENCE rather than missing -- the same
    distinction the postgame layer draws between a missing player, which is a
    realised zero, and a missing field, which is a mapping bug.
    """
    by = {(r['season'], r['week'], r['team'], r['gsis_id']): r
          for r in q7_recv}
    n_join = 0
    for r in rows:
        got = by.get((r['s'], r['w'], r['t'], r['pid']))
        if got is None:
            r['q7_yds'] = 0.0
            r['q7_basis'] = 'ZERO_BY_ABSENCE_FROM_RECEIVER_PANEL'
        else:
            r['q7_yds'] = float(got['rec_yds'])
            r['q7_basis'] = 'OBSERVED'
            n_join += 1
    return rows, {'n_rows_joined_to_receiver_panel': n_join,
                  'n_rows_zero_by_absence': len(rows) - n_join}


def _class_means(rows):
    out = collections.defaultdict(list)
    for r in rows:
        if r['appeared'] and r.get('share_targets') is not None:
            out[(r['pos'], r['role_class'])].append(r['share_targets'])
            out[('__ALL__', r['pos'])].append(r['share_targets'])
    return {k: float(np.mean(v)) for k, v in out.items() if v}


def _class_of(cm, r):
    v = cm.get((r['pos'], r['role_class']))
    return v if v is not None else (cm.get(('__ALL__', r['pos'])) or 0.0)


def _best_k(test, cm_fit):
    """The shrinkage strength that would have minimised eval-season error.

    This is the SHRINK oracle's value and nothing else reads it. The grid is
    declared; the search runs on the evaluation season by design, because the
    question this answers is "how much error comes from getting k wrong",
    which cannot be asked without knowing what right would have been.
    """
    best_sse = None
    chosen = K_GRID[0]
    for k in K_GRID:
        sse = 0.0
        n = 0
        for r in test:
            if not (r['appeared'] and r.get('share_targets') is not None):
                continue
            w = r['own_n'] / (r['own_n'] + k) if r['own_n'] else 0.0
            own = r['own_share'] if r['own_share'] is not None else 0.0
            base = w * own + (1 - w) * _class_of(cm_fit, r)
            sse += (base - r['share_targets']) ** 2
            n += 1
        if n and (best_sse is None or sse < best_sse):
            best_sse, chosen = sse, k
    return float(chosen)


def run(eval_seasons=EVAL_SEASONS, n_draws=N_DRAWS, seed=SEED, progress=True):
    rows, _ = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, opp_ev = Q6F.attach_opportunity(rows)
    rows = _own_history(rows)
    p_r8 = load_p_r8()
    denom = load_denom()
    q7_recv = Q7P.load_recv()
    rows, join_ev = attach_receiving(rows, q7_recv)

    subsets = [frozenset(c) for k in range(len(COMPONENTS) + 1)
               for c in itertools.combinations(COMPONENTS, k)]
    acc = {S: collections.Counter() for S in subsets}
    strata = collections.defaultdict(lambda: collections.Counter())
    detail, fit_log = [], []

    for Y in eval_seasons:
        train = [r for r in rows if r['s'] < Y]
        test = [r for r in rows if r['s'] == Y]
        if not train or not test:
            continue
        cm_fit = _class_means(train)
        cm_oracle = _class_means(test)
        k_fit, k_ev = Q6C._share_k(train, 'targets')
        k_oracle = _best_k(test, cm_fit)
        bud_pred, bud_resid, bud_est = budget_model(denom, Y)
        eff = efficiency_fit(q7_recv, Y)
        Q6C.role_base(rows, 'targets', k_fit, cm_fit)
        vac_oracle, vac_ev = Q6C.fit_vacancy(test, 'targets')

        groups = collections.defaultdict(list)
        for r in test:
            groups[(r['s'], r['w'], r['t'])].append(r)

        for gkey, g in sorted(groups.items()):
            den = int(g[0]['den_targets'])
            if den <= 0:
                continue
            pred_point = float(bud_pred.get(gkey, den))
            if pred_point <= 0:
                continue
            own = np.array([r['own_share'] if r['own_share'] is not None
                            else _class_of(cm_fit, r) for r in g], float)
            n_own = np.array([r['own_n'] for r in g], float)
            cls_fit = np.array([_class_of(cm_fit, r) for r in g], float)
            cls_or = np.array([_class_of(cm_oracle, r) for r in g], float)
            pv = np.array([p_r8.get((r['s'], r['w'], r['t'], r['pid']), 0.0)
                           for r in g], float)
            app = np.array([float(r['appeared']) for r in g], float)
            cls_idx = [r['role_class'] for r in g]
            starter_i = [j for j, r in enumerate(g)
                         if r['role_class'] == 'starter']
            y_tgt = np.array([float(r['targets']) for r in g], float)
            y_yds = np.array([float(r['q7_yds']) for r in g], float)

            for S in subsets:
                # COMMON RANDOM NUMBERS: the same stream drives every subset,
                # so a difference between them is the oracle and not the draw.
                rng = np.random.default_rng(
                    [seed, Y, gkey[1], _stream(gkey[2])])
                k = k_oracle if 'SHRINK' in S else k_fit
                w = np.where(n_own > 0, n_own / (n_own + k), 0.0)
                cls = cls_or if 'CLASS' in S else cls_fit
                base = np.maximum(w * own + (1 - w) * cls, 0.0)
                if 'APPEAR' in S:
                    A = np.tile(app, (n_draws, 1))
                else:
                    A = rng.binomial(1, np.clip(pv, 0.0, 1.0),
                                     size=(n_draws, len(g)))
                W = np.tile(base, (n_draws, 1)) * A
                if 'REDIST' in S and starter_i:
                    out_any = (A[:, starter_i] == 0).any(axis=1)
                    boost = np.array([float(vac_oracle.get(c, 1.0))
                                      for c in cls_idx])
                    W = np.where(out_any.reshape(-1, 1), W * boost, W)
                tot = W.sum(axis=1, keepdims=True)
                P = np.divide(W, tot, out=np.zeros_like(W), where=tot > 0)
                if 'BUDGET' in S:
                    budget = np.full(n_draws, den, int)
                else:
                    budget = np.maximum(np.rint(
                        pred_point +
                        bud_resid[rng.integers(0, len(bud_resid), n_draws)]
                    ), 0).astype(int)
                ok = (P.sum(axis=1) > 0) & (budget > 0)
                T = np.zeros(P.shape)
                if ok.any():
                    Q = P[ok] / P[ok].sum(axis=1, keepdims=True)
                    bl = budget[ok]
                    # per-draw budget, so the multinomial is drawn row by row
                    # where the counts differ
                    idx = np.where(ok)[0]
                    for u, row in enumerate(idx):
                        T[row] = rng.multinomial(int(bl[u]), Q[u])
                YD = _yards(T, eff, rng)
                a = acc[S]
                for j, r in enumerate(g):
                    te = float(T[:, j].mean()) - y_tgt[j]
                    tc = _crps(T[:, j], y_tgt[j])
                    ye = float(YD[:, j].mean()) - y_yds[j]
                    yc = _crps(YD[:, j], y_yds[j])
                    a['n'] += 1
                    a['tgt_err'] += te
                    a['tgt_crps'] += tc
                    a['yds_err'] += ye
                    a['yds_crps'] += yc
                    a['zero_pred'] += float((T[:, j] <= 0).mean())
                    a['zero_act'] += 1.0 if y_tgt[j] == 0 else 0.0
                    # THE RC2-COMPARABLE POPULATION, accumulated separately.
                    #
                    # RC2 and Q7 scored APPEARED players carrying at least one
                    # prior appeared game. This frame is the whole union
                    # frame, half of which never took a target, and averaging
                    # a bias over those rows drives it to zero whatever the
                    # model does. Attributing a bias the harness does not
                    # reproduce would be attributing nothing, so the same
                    # population is carried beside the full one.
                    if r['appeared'] and (r['own_n'] or 0) >= 1:
                        a['rc2_n'] += 1
                        a['rc2_tgt_err'] += te
                        a['rc2_tgt_crps'] += tc
                        a['rc2_yds_err'] += ye
                        a['rc2_yds_crps'] += yc
                if S in (frozenset(), frozenset(COMPONENTS)):
                    label = 'BASELINE' if not S else 'FULL_ORACLE'
                    for j, r in enumerate(g):
                        st = _strata(r, y_tgt[j], pv[j])
                        strata[(label, st['pos'], st['role_class'],
                                st['regime'], st['appearance_certainty'])
                               ].update({
                                   'n': 1,
                                   'tgt_err': float(T[:, j].mean()) - y_tgt[j],
                                   'tgt_crps': _crps(T[:, j], y_tgt[j]),
                                   'yds_err': float(YD[:, j].mean()) - y_yds[j],
                                   'yds_crps': _crps(YD[:, j], y_yds[j]),
                                   'tgt_pred': float(T[:, j].mean()),
                                   'tgt_act': y_tgt[j]})
                        if label == 'BASELINE':
                            detail.append({
                                'season': r['s'], 'week': r['w'],
                                'team': r['t'], 'pid': r['pid'],
                                'pos': r['pos'], 'role_class': r['role_class'],
                                'team_game': f"{r['s']}-{r['w']}-{r['t']}",
                                'appeared': int(r['appeared']),
                                'p_r8': round(float(pv[j]), 6),
                                'appearance_certainty':
                                    st['appearance_certainty'],
                                'target_regime': st['regime'],
                                'actual_targets': y_tgt[j],
                                'pred_targets': round(float(T[:, j].mean()), 4),
                                'actual_rec_yards': y_yds[j],
                                'pred_rec_yards': round(float(YD[:, j].mean()), 4),
                                'target_crps': round(_crps(T[:, j], y_tgt[j]), 5),
                                'rec_yard_crps': round(_crps(YD[:, j], y_yds[j]), 5),
                                'p_zero_targets': round(
                                    float((T[:, j] <= 0).mean()), 5),
                            })
        fit_log.append({
            'eval_season': Y, 'n_train': len(train), 'n_test': len(test),
            'budget_estimator': bud_est,
            'budget_residual_pool': int(len(bud_resid)),
            'budget_residual_sd': round(float(bud_resid.std(ddof=1)), 4),
            'k_fitted': k_ev, 'k_oracle': k_oracle, 'k_grid': list(K_GRID),
            'catch_rate': round(eff['catch_rate'], 5),
            'per_catch_pool_size': eff['n_pool'],
            'vacancy_oracle': vac_ev,
        })
        if progress:
            print(f'  {Y}: {len(test)} rows, k_fit '
                  f'{k_fit:.3f} k_oracle {k_oracle:.3f}', flush=True)
    return {'acc': acc, 'strata': strata, 'detail': detail,
            'fit_log': fit_log, 'opportunity_evidence': opp_ev,
            'receiving_join_evidence': join_ev, 'subsets': subsets}


TARGET_REGIMES = ((0, 0, '0'), (1, 2, '1-2'), (3, 5, '3-5'), (6, 9, '6-9'),
                  (10, 10 ** 6, '10+'))


def _strata(r, y_tgt, p):
    cert = ('near_certain' if p >= 0.9 else 'likely' if p >= 0.7
            else 'uncertain' if p >= 0.4 else 'doubtful')
    reg = TARGET_REGIMES[-1][2]
    for lo, hi, lab in TARGET_REGIMES:
        if lo <= y_tgt <= hi:
            reg = lab
            break
    return {'pos': r['pos'], 'role_class': r['role_class'], 'regime': reg,
            'appearance_certainty': cert}


# ------------------------------------------------------------- attribution
VALUE_FUNCTIONS = {
    'receiving_yard_bias': ('rc2_yds_err', 'rc2_n',
                            'mean signed receiving-yard error on the '
                            'RC2-comparable population'),
    'receiving_yard_crps': ('rc2_yds_crps', 'rc2_n',
                            'mean receiving-yard CRPS, same population'),
    'player_target_crps': ('rc2_tgt_crps', 'rc2_n',
                           'mean player-target CRPS, same population'),
    'player_target_bias': ('rc2_tgt_err', 'rc2_n',
                           'mean signed player-target error, same population'),
    'receiving_yard_bias_full_frame': ('yds_err', 'n',
                                       'the same bias over the WHOLE union '
                                       'frame, where half the rows never took '
                                       'a target and the mean is driven to '
                                       'zero whatever the model does'),
}


def attribute(acc, num, den):
    """Exact Shapley over all 32 subsets, using the repository's own routine.

    A single ordering hands the first component every interaction it shares
    with the others. Averaging over all orderings is what makes the five
    numbers add up to the whole, and `qb2_lib.shapley` is the implementation
    this project already uses for exactly that.
    """
    vals = {}
    for S, a in acc.items():
        n = a[den]
        vals[frozenset(S)] = (a[num] / n) if n else 0.0
    phi = QB2.shapley(vals, list(COMPONENTS))
    v0 = vals[frozenset()]
    v1 = vals[frozenset(COMPONENTS)]
    total = v1 - v0
    out = {'baseline': round(v0, 6), 'full_oracle': round(v1, 6),
           'total_movement': round(total, 6), 'components': {}}
    for c in COMPONENTS:
        out['components'][c] = {
            'shapley': round(float(phi[c]), 6),
            'share_of_total_movement': (round(float(phi[c]) / total, 5)
                                        if abs(total) > 1e-12 else None),
            'marginal_alone': round(
                vals[frozenset([c])] - v0, 6),
            'marginal_last': round(
                v1 - vals[frozenset(COMPONENTS) - {c}], 6),
            'kind': COMPONENT_KIND[c], 'means': COMPONENT_MEANS[c],
        }
    ranked = sorted(COMPONENTS, key=lambda c: -abs(float(phi[c])))
    out['ranked_by_absolute_contribution'] = ranked
    out['sum_of_shapley_values'] = round(
        float(sum(phi[c] for c in COMPONENTS)), 6)
    out['adds_up'] = bool(abs(out['sum_of_shapley_values'] - total) < 1e-6)
    return out


def summarise(res):
    acc = res['acc']
    out = {
        'artifact': 'NFL_Q8_ATTRIBUTION_AUDIT',
        'spec_version': SPEC_VERSION,
        'promoted': False, 'is_research_only': True,
        'no_repair_built': True,
        'market_inputs_used': [], 'live_2026_rows_used': 0,
        'components': {c: {'kind': COMPONENT_KIND[c],
                           'means': COMPONENT_MEANS[c]} for c in COMPONENTS},
        'oracle_kinds_note': (
            'REALISATION oracles hand the model a game-level fact it would '
            'have had to predict; PARAMETER oracles hand it the right '
            'population value as an evaluation-season aggregate, never that '
            'team-week\'s own answer. The two answer different questions and '
            'each row says which it is.'),
        'held_fixed': [
            'team volume: the frozen P4B estimator, read not re-chosen',
            'receiving efficiency: one catch rate and one per-catch yardage '
            'pool per season, shared by all thirty-two configurations',
            'the touchdown layer is untouched',
            'appearance: production R8, read from the committed Q6 forward '
            'chain rather than refit',
        ],
        'n_subsets': len(acc),
        'n_rows_scored': acc[frozenset()]['n'],
        'n_rows_rc2_population': acc[frozenset()]['rc2_n'],
        'population_note': (
            'the RC2-comparable population is appeared players carrying at '
            'least one prior appeared game -- the rule RC1 stage 2 accepted '
            'and RC2 and Q7 scored on. The full union frame is reported '
            'beside it because half its rows never took a target, which '
            'drives any mean bias to zero whatever the model does.'),
        'attribution': {},
        'zero_target_probability': {},
        'fit_log': res['fit_log'],
        'receiving_join_evidence': res['receiving_join_evidence'],
    }
    for name, (num, den, note) in VALUE_FUNCTIONS.items():
        a = attribute(acc, num, den)
        a['value_function'] = note
        out['attribution'][name] = a
    b = acc[frozenset()]
    f = acc[frozenset(COMPONENTS)]
    out['zero_target_probability'] = {
        'baseline_predicted': round(b['zero_pred'] / b['n'], 5),
        'full_oracle_predicted': round(f['zero_pred'] / f['n'], 5),
        'observed': round(b['zero_act'] / b['n'], 5),
        'baseline_error': round((b['zero_pred'] - b['zero_act']) / b['n'], 5),
    }
    out['strata'] = _strata_block(res['strata'])
    out['headline'] = _headline(out)
    return out


def _strata_block(strata):
    out = collections.defaultdict(dict)
    for (label, pos, rc, reg, cert), c in strata.items():
        n = c['n']
        if n < 25:
            continue
        out[label][f'{pos}|{rc}|{reg}|{cert}'] = {
            'n': n,
            'target_bias': round(c['tgt_err'] / n, 5),
            'target_crps': round(c['tgt_crps'] / n, 5),
            'receiving_yard_bias': round(c['yds_err'] / n, 5),
            'receiving_yard_crps': round(c['yds_crps'] / n, 5),
            'mean_predicted_targets': round(c['tgt_pred'] / n, 5),
            'mean_actual_targets': round(c['tgt_act'] / n, 5),
        }
    return dict(out)


def _headline(out):
    bias = out['attribution']['receiving_yard_bias']
    crps = out['attribution']['player_target_crps']
    return {
        'bias_is_dominated_by': bias['ranked_by_absolute_contribution'][0],
        'bias_ranking': bias['ranked_by_absolute_contribution'],
        'target_crps_is_dominated_by':
            crps['ranked_by_absolute_contribution'][0],
        'target_crps_ranking': crps['ranked_by_absolute_contribution'],
        'note': ('the two value functions can rank differently, and where '
                 'they do that IS the finding rather than a problem to '
                 'resolve by picking one'),
    }


def write_detail(detail, path):
    if not detail:
        raise SystemExit('Q8_EMPTY_DETAIL: an empty diagnostics table is an '
                         'error, not a result.')
    with gzip.open(path, 'wt', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(detail[0]))
        w.writeheader()
        w.writerows(detail)
    return len(detail)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in EVAL_SEASONS))
    ap.add_argument('--draws', type=int, default=N_DRAWS)
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')), a.draws)
    s = summarise(res)
    s['n_draws'] = a.draws
    (HERE / 'Q8_ATTRIBUTION_AUDIT.json').write_text(
        json.dumps(s, indent=1, default=str) + '\n')
    n = write_detail(res['detail'], HERE / 'Q8_AUDIT_ROWS.csv.gz')
    print(f'\nrows scored        : {s["n_rows_scored"]}')
    print(f'RC2-population     : {s["n_rows_rc2_population"]}')
    print(f'detail rows        : {n}')
    for name, att in s['attribution'].items():
        print(f'\n{name}: baseline {att["baseline"]:+.4f} -> full oracle '
              f'{att["full_oracle"]:+.4f}  (adds up: {att["adds_up"]})')
        for c in att['ranked_by_absolute_contribution']:
            e = att['components'][c]
            sh = e['share_of_total_movement']
            print(f'   {c:8s} [{e["kind"]:11s}] shapley {e["shapley"]:+9.5f}'
                  + (f'  {100 * sh:6.1f}% of the movement' if sh is not None
                     else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
