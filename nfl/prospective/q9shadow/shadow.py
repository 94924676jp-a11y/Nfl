"""Production R8 and the frozen Q9 hurdle, side by side on one set of inputs.

    python3.12 -m nfl.prospective.q9shadow.shadow --season 2025 --games 8

THE COMPARISON DESIGN, AND WHERE IT DIFFERS FROM Q9B ON PURPOSE

Q9B seeded each arm's stream with the arm name, so the two arms drew DIFFERENT
appearance matrices and DIFFERENT team budgets. That is defensible for a
four-season average and indefensible for a prospective test on a handful of
games: at that size the arms would differ by their upstream noise as much as
by their mechanism.

Here the upstream is drawn ONCE and handed to both arms:

    appearance draws   drawn once, through the production interface
    team budget draws  drawn once, from the frozen P4B point + residual pool
    draw index         one shared index; column j is one iteration in both arms
    player frame       one frame, one order
    input captures     one bundle, one set of hashes

and only the allocation stream is per-arm, keyed by the arm name through
crc32 -- never Python's `hash()`, which is randomised per process and has
already cost this project one silent defect.

THIS IS NOT A CHANGE TO THE CANDIDATE. A seed and a stream layout are
execution parameters of a comparison harness. The mechanism -- features,
coefficients, the one-target floor, the two named fallbacks and the thresholds
inside them -- is read from the frozen module and is checked against the
freeze hash before anything is sealed.

WHERE THE FEATURES COME FROM, AND WHY THAT IS AN INTERFACE

`nfl.research.q6.frame.load_frame` REFUSES any 2026 row by name
(`Q6_LIVE_SEASON_IN_FRAME`) because the live season may not be fitted. That
refusal is correct and is not routed around. So the feature row arrives
through a declared source with two implementations:

  HISTORICAL_FRAME  the Q6 panel, 2020-2025. What the dry-run proof runs on.
  LIVE_PREGAME      not implemented, and refused by name with the exact list
                    of what it would need. A stub that returned plausible
                    numbers would be the worst possible outcome here.

The features handed to the frozen featuriser are PROJECTED onto the ten keys
it reads (`inputs.project_feature_row`), so the realised target column that
the historical panel necessarily carries cannot reach the model.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from nfl.production.nonqb import layers as LAYERS                     # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                     # noqa: E402
from nfl.research.q6 import frame as Q6F                              # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                      # noqa: E402
from nfl.research.q7 import panel as Q7P                              # noqa: E402
from nfl.research.q8 import audit as AUD                              # noqa: E402
from nfl.research.q9 import hurdle as Q9                              # noqa: E402

SPEC_VERSION = 'q9-shadow-forecast-1'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'

HISTORICAL_FRAME = 'HISTORICAL_FRAME'
LIVE_PREGAME = 'LIVE_PREGAME'
FEATURE_SOURCES = (HISTORICAL_FRAME, LIVE_PREGAME)

# What a live pregame feature source would have to supply, itemised. Written
# out because "the live path is not implemented" is not an actionable
# statement and because the next person to attempt it should not have to
# re-derive the list from `Q9.featurise`.
LIVE_PREGAME_REQUIREMENTS = {
    'prior_appeared_game_history': (
        'h_target_freq, h_participation_ewma, h_share_given_positive and '
        'h_appeared_games over strictly earlier APPEARED games. Available '
        'from seasons <= 2025 in the committed panel.'),
    'point_in_time_role_class': (
        'role_class from trailing snap share, or from the lawful depth-chart '
        'vintage when no trail exists. The 2026 depth-chart captures exist.'),
    'depth_chart_rank': 'rank, from the same lawful vintage.',
    'position_and_team': 'pos and team, from the roster/depth-chart vintage.',
    'official_injury_report': (
        'inj_status, inj_practice and inj_available. BLOCKED: the 2026 '
        'captures carry rows whose report_status is unfilled, which '
        'nfl.production.nonqb.inputs refuses by name as '
        'INJURY_REPORT_INCOMPLETE. An unfiled designation is not an absence '
        'of injury and may not be defaulted to healthy.'),
    'upstream_appearance_probability': (
        'p_appear per player. Production R8 supplies it, and the committed '
        'p_R8 table covers 2020-2025 only; a live game needs the appearance '
        'layer to run, which is blocked by the same injury report.'),
    'team_target_budget': (
        'the frozen P4B point forecast and residual pool for the team-week. '
        'Estimated from seasons strictly earlier, so a 2026 week-1 budget is '
        'obtainable.'),
}


def feature_rows(source=HISTORICAL_FRAME, season=None, week=None,
                 game_id=None) -> Outcome:
    """The pregame feature rows for a slate, or a named refusal."""
    if source not in FEATURE_SOURCES:
        return Outcome.fail('Q9_UNKNOWN_FEATURE_SOURCE',
                            f'{source!r} not in {FEATURE_SOURCES}')
    if source == LIVE_PREGAME:
        return Outcome.blocked(
            'Q9_LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED',
            'there is no pregame feature builder for the live season. The Q6 '
            'frame refuses 2026 rows by design, production declares '
            'feature_build STAGE_DECLARED_UNIMPLEMENTED, and the appearance '
            'layer refuses on an incomplete injury report. Refused by name '
            'with the requirement list attached rather than stubbed: a stub '
            'returning plausible features would produce a sealed forecast '
            'that looks prospective and measures nothing.',
            cause=Cause.DEPENDENCY, requirements=LIVE_PREGAME_REQUIREMENTS,
            season=season, week=week, game_id=game_id)
    rows, ev = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, _ = Q6F.attach_opportunity(rows)
    rows = AUD._own_history(rows)
    rows = Q9.attach_hurdle_history(rows)
    return Outcome.ok('Q9_FEATURE_ROWS_OK', value=rows,
                      detail=f'{len(rows)} historical panel row(s)',
                      source=HISTORICAL_FRAME,
                      seasons=sorted({r['s'] for r in rows}),
                      frame_spec_version=ev.get('spec_version'))


def _stream_parts(seed, season, week, team, tag):
    return [int(seed), int(season), int(week), AUD._stream(team),
            AUD._stream(tag)]


def fit_for(rows, season, q7=None):
    """Every fitted block a forecast for `season` consumes. Prior seasons only."""
    train = [r for r in rows if r['s'] < season]
    if not train:
        return Outcome.blocked(
            'Q9_NO_TRAINING_ROWS',
            f'no panel row precedes {season}, so nothing can be fitted '
            f'without reading the season being forecast.', cause=Cause.DATA)
    denom = AUD.load_denom()
    bud_point, bud_resid, bud_est = AUD.budget_model(denom, season)
    bvals = np.array(list(bud_point.values()), float)
    bmean, bsd = float(bvals.mean()), float(bvals.std(ddof=1))
    model = Q9.fit_hurdle(train, bud_point, bmean, bsd)
    if model is None:
        return Outcome.blocked(
            'Q9_HURDLE_FIT_RETURNED_NOTHING',
            f'the stage-1 fit returned nothing on {len(train)} training '
            f'row(s); there is no candidate to forecast with.',
            cause=Cause.DATA, n_train=len(train))
    return Outcome.ok('Q9_FIT_OK', value={
        'hurdle': model, 'class_means': AUD._class_means(train),
        'share_k': Q6C._share_k(train, 'targets')[0],
        'budget_point': bud_point, 'budget_residual': bud_resid,
        'budget_estimator': bud_est, 'budget_mean': bmean,
        'budget_sd': bsd,
        'efficiency': AUD.efficiency_fit(q7, season) if q7 else None,
        'training_seasons': sorted({r['s'] for r in train}),
        'n_train': len(train),
    }, detail=f'fitted on {len(train)} row(s) from seasons '
              f'{sorted({r["s"] for r in train})}')


def _base_share(g, fit):
    own = np.array([r['own_share'] if r['own_share'] is not None
                    else AUD._class_of(fit['class_means'], r) for r in g],
                   float)
    n_own = np.array([r['own_n'] for r in g], float)
    cls = np.array([AUD._class_of(fit['class_means'], r) for r in g], float)
    w = np.where(n_own > 0, n_own / (n_own + fit['share_k']), 0.0)
    return np.maximum(w * own + (1 - w) * cls, 0.0)


def forecast_team_game(g, fit, p_appear, game_id, seed=CAND.SEED,
                       n_draws=CAND.N_DRAWS) -> Outcome:
    """Both arms for one team-game, on one shared set of upstream draws."""
    season, week, team = g[0]['s'], g[0]['w'], g[0]['t']
    pid_list = [r['pid'] for r in g]

    # ---- THE SHARED UPSTREAM. Drawn once, keyed to the team-game and not to
    # any arm, so neither arm can be advantaged by its own noise.
    up = np.random.default_rng(_stream_parts(seed, season, week, team,
                                             'UPSTREAM'))
    bud_key = (season, week, team)
    point = fit['budget_point'].get(bud_key, fit['budget_mean'])
    budget = np.maximum(np.rint(
        point + fit['budget_residual'][up.integers(
            0, len(fit['budget_residual']), n_draws)]), 0).astype(int)

    players = [{'gsis_id': r['pid'], 'position': r['pos'], 'team': r['t']}
               for r in g]
    ap = LAYERS.appearance(
        season, week, players,
        fixture={'_test_only': True, 'practice_progression': {},
                 'teammate_availability': {}, 'p_appear': p_appear},
        seed=seed, m=n_draws, game_id=game_id)
    if ap.state is not State.PASS:
        return Outcome.blocked(
            'Q9_SHADOW_BLOCKED_UPSTREAM_APPEARANCE',
            f'{game_id}/{team}: appearance is {ap.state.value}[{ap.code}], so '
            f'neither arm has an availability draw to allocate over.',
            cause=Cause.DATA, upstream_code=ap.code)
    A = np.array([ap.value[pid] for pid in pid_list], dtype=int).T
    if A.shape != (n_draws, len(g)):
        return Outcome.fail(
            'Q9_SHADOW_CROSS_DRAW_INDEX_MISMATCH',
            f'{game_id}/{team}: appearance draws are {A.shape}, expected '
            f'{(n_draws, len(g))}. Both arms must sit on one draw index.')

    base = _base_share(g, fit)
    bz = (point - fit['budget_mean']) / max(fit['budget_sd'], 1e-9)
    # THE PROJECTION. The frozen featuriser is handed only the ten keys it
    # reads, so the panel's realised target column cannot reach it.
    ph = np.asarray(Q9.SA.predict(
        fit['hurdle'],
        [Q9.featurise(IN.project_feature_row(r), bz) for r in g]), float)

    arms, fallbacks, recon = {}, collections.Counter(), {}
    for arm in CAND.ARMS:
        rng = np.random.default_rng(_stream_parts(seed, season, week, team,
                                                  arm))
        T = np.zeros((n_draws, len(g)))
        if arm == CAND.ARM_CANDIDATE:
            H = rng.binomial(1, np.clip(ph, 0.0, 1.0), size=(n_draws, len(g)))
            C = (A == 1) & (H == 1)
            for d in range(n_draws):
                T[d], fb = Q9.allocate_hurdle(base, C[d], int(budget[d]), rng)
                fallbacks[f'{arm}/DRAWS'] += 1
                if fb:
                    fallbacks[f'{arm}/{fb}'] += 1
        else:
            W = np.tile(np.maximum(base, 0.0), (n_draws, 1)) * A
            tot = W.sum(axis=1, keepdims=True)
            P = np.divide(W, tot, out=np.zeros_like(W), where=tot > 0)
            for d in range(n_draws):
                fallbacks[f'{arm}/DRAWS'] += 1
                if budget[d] > 0 and P[d].sum() > 0:
                    T[d] = rng.multinomial(int(budget[d]), P[d] / P[d].sum())
                elif budget[d] > 0:
                    # THE BASELINE'S OWN DEGENERATE CASE, COUNTED. Q9's
                    # equivalent is a NAMED fallback; leaving the baseline's
                    # unnamed would make the fallback counts incomparable.
                    fallbacks[f'{arm}/BASELINE_NO_ELIGIBLE_WEIGHT'] += 1
        recon[arm] = float(np.abs(T.sum(axis=1) - budget).max())
        yrng = np.random.default_rng(
            _stream_parts(seed, season, week, team, arm + '/YARDS'))
        YD = (AUD._yards(T, fit['efficiency'], yrng)
              if fit.get('efficiency') is not None else None)
        arms[arm] = {'targets': T, 'yards': YD}

    off = {a: e for a, e in recon.items() if e != 0.0}
    if off:
        return Outcome.fail(
            'Q9_SHADOW_TEAM_TARGET_RECONCILIATION_VIOLATED',
            f'{game_id}/{team}: allocated targets do not sum to the drawn '
            f'budget on every draw: {off}. Both arms partition one finite '
            f'budget, so a residual is an accounting error.',
            max_absolute_error=off)

    return Outcome.ok(
        'Q9_SHADOW_TEAM_GAME_OK',
        value={'arms': arms, 'budget': budget, 'appearance': A,
               'p_hurdle': ph, 'base_share': base, 'players': pid_list,
               'rows': g},
        detail=f'{game_id}/{team}: {len(g)} player(s), {n_draws} shared '
               f'draw(s), both arms reconcile exactly',
        game_id=game_id, team=team, season=season, week=week,
        n_players=len(g), n_draws=n_draws,
        mean_budget=round(float(budget.mean()), 4),
        fallback_states=dict(fallbacks),
        max_absolute_reconciliation_error=recon,
        upstream_appearance_spec=ap.evidence.get('appearance_spec'),
        upstream_test_only=bool(ap.evidence.get('test_only')),
        seed=seed,
        rng_policy='shared upstream; per-arm allocation stream via crc32')


def draws_sha256(res) -> str:
    """One digest over both arms' draw matrices, in declared order."""
    h = hashlib.sha256()
    for arm in CAND.ARMS:
        T = res['arms'][arm]['targets']
        h.update(arm.encode())
        h.update(np.ascontiguousarray(T, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(res['budget'], dtype=np.int64).tobytes())
    h.update(np.ascontiguousarray(res['appearance'],
                                  dtype=np.int64).tobytes())
    return h.hexdigest()


def summarise_players(res):
    """The per-player, per-arm pregame summary. No outcome is read.

    `zero_probability` is the quantity the primary metric is computed from
    later, and it is stored now, before kickoff, so the number scored is the
    number forecast rather than one recomputed afterwards.
    """
    out = []
    rows, pids = res['rows'], res['players']
    for arm in CAND.ARMS:
        T = res['arms'][arm]['targets']
        YD = res['arms'][arm]['yards']
        for j, r in enumerate(rows):
            d = T[:, j]
            pos_d = d[d > 0]
            out.append({
                'arm': arm, 'player_id': pids[j], 'position': r['pos'],
                'role_class': r['role_class'],
                'appearance_certainty': Q9._certainty(
                    float(res['appearance'][:, j].mean())),
                'p_appear_drawn': round(float(res['appearance'][:, j].mean()),
                                        6),
                'p_hurdle': round(float(res['p_hurdle'][j]), 6),
                'prior_depth_bucket': r['prior_depth_bucket'],
                'base_share': round(float(res['base_share'][j]), 8),
                'zero_probability': round(float((d == 0).mean()), 6),
                'mean_targets': round(float(d.mean()), 5),
                'p50_targets': float(np.percentile(d, 50)),
                'p90_targets': float(np.percentile(d, 90)),
                'mean_targets_given_positive': (round(float(pos_d.mean()), 5)
                                                if pos_d.size else None),
                'n_positive_draws': int(pos_d.size),
                'mean_receiving_yards': (round(float(YD[:, j].mean()), 4)
                                         if YD is not None else None),
            })
    return out


def run(season=2025, n_games=8, seed=CAND.SEED, n_draws=CAND.N_DRAWS,
        source=HISTORICAL_FRAME, progress=True):
    """The side-by-side harness on a frozen historical slice."""
    fr = feature_rows(source, season=season)
    if fr.state is not State.PASS:
        return {'status': f'{fr.state.value}[{fr.code}]', 'detail': fr.detail,
                'evidence': dict(fr.evidence), 'team_games': []}
    rows = fr.value
    q7 = Q7P.load_recv()
    rows, _ = AUD.attach_receiving(rows, q7)
    fit = fit_for(rows, season, q7)
    if fit.state is not State.PASS:
        return {'status': f'{fit.state.value}[{fit.code}]',
                'detail': fit.detail, 'team_games': []}
    p_r8 = AUD.load_p_r8()
    groups = collections.defaultdict(list)
    for r in rows:
        if r['s'] == season:
            groups[(r['s'], r['w'], r['t'])].append(r)

    done, blocked = [], []
    for gkey in sorted(groups)[:n_games]:
        g = groups[gkey]
        game_id = f'{gkey[0]}_{gkey[1]:02d}_{gkey[2]}'
        p_appear = {r['pid']: float(p_r8.get(
            (r['s'], r['w'], r['t'], r['pid']), 0.0)) for r in g}
        res = forecast_team_game(g, fit.value, p_appear, game_id, seed,
                                 n_draws)
        if res.state is not State.PASS:
            blocked.append({'game_id': game_id, 'team': gkey[2],
                            'state': res.state.value, 'code': res.code})
            continue
        done.append({'outcome': res, 'draws_sha256': draws_sha256(res.value),
                     'players': summarise_players(res.value)})
        if progress:
            print(f'  {game_id} {gkey[2]}: {res.evidence["n_players"]} '
                  f'player(s), draws {done[-1]["draws_sha256"][:16]}',
                  flush=True)
    return {'status': 'OK' if done else 'NO_TEAM_GAME_FORECAST',
            'season': season, 'seed': seed, 'n_draws': n_draws,
            'feature_source': source, 'fit': dict(fit.evidence),
            'team_games': done, 'blocked': blocked}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=2025)
    ap.add_argument('--games', type=int, default=8)
    ap.add_argument('--draws', type=int, default=CAND.N_DRAWS)
    ap.add_argument('--source', default=HISTORICAL_FRAME,
                    choices=list(FEATURE_SOURCES))
    a = ap.parse_args(argv)
    out = run(a.season, a.games, CAND.SEED, a.draws, a.source)
    print(f"status        : {out['status']}")
    print(f"team-games    : {len(out['team_games'])}")
    print(f"blocked       : {len(out.get('blocked') or [])}")
    if out.get('detail'):
        print(f"detail        : {out['detail'][:300]}")
    for tg in out['team_games'][:3]:
        ev = tg['outcome'].evidence
        print(f"  {ev['game_id']}/{ev['team']}: fallbacks "
              f"{ {k: v for k, v in ev['fallback_states'].items()
                   if not k.endswith('/DRAWS')} }")
    return 0 if out['status'] == 'OK' else 1


if __name__ == '__main__':
    sys.exit(main())
