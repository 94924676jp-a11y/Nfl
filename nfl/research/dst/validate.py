#!/usr/bin/env python3.12
"""DST validation split into the six components the owner named, out of sample.

Owner instruction 2026-09-30: DST validation must separate **mean scoring, sack rate, turnover rate,
defensive TD frequency, return TD frequency, and tail calibration.** A single "DST looks fine" hides
which of six different things is right.

TWO FACTS ABOUT THE MODEL DECIDE THE DESIGN OF THIS FILE, and both were read out of
`nfl/sim/dst.py` rather than assumed.

1. `DstModel.draw` picks an empirical four-tuple at random from the points-allowed band's own pool.
   The model IS the within-band empirical distribution. So evaluating it on the games it was fitted
   on compares a bootstrap of a sample against that same sample, and five of the six components pass
   by construction. **An in-sample DST validation is vacuous, not merely optimistic.** Everything
   here is therefore fitted on earlier seasons and scored on a later one.

   What is actually being tested out of sample is the part that is a modelling choice rather than a
   copy of the data: that points allowed is the right thing to condition on, that these five bands
   are the right partition, and that last season's within-band distribution transfers to this one.

2. The stored tuple is `(sacks, turnovers, def_td, safety)`. `return_td` is counted in the
   play-by-play pass in `dst.build()` and then **never stored**, so the model cannot tell a pick-six
   from a fumble-recovery touchdown from a punt return touchdown. The owner's fifth component
   therefore has nothing in the model to compare against. This file does NOT invent one: it reports
   `return_td_frequency` as REFUSED with cause DATA, states that the quantity is measured and
   discarded, and reports the realised rate so the size of the gap is on the record. A component
   scored against a model that does not represent it would be a fabricated result.

CLUSTERING. Club-games in the same week share weather, officiating and scheduling, and the two
defences in one game share the game. The standard error on each component is therefore blocked by
(season, week) rather than treated as 2 x n_games independent draws. A naive SE here would be the
same defect the MLB repo records for prop grading, where naive understated clustered by threefold.
"""
from __future__ import annotations

import collections
import csv as _csv
import gzip as _gzip
import json
import math
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import dst as D  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT = _REPO / 'nfl/research/dst/DST_VALIDATION.json'

#: Draws per club-game when a component needs the predictive DISTRIBUTION rather than its mean. Tail
#: coverage is the only component that does; the others are closed-form from the band pool.
N_DRAW = 400

#: Seed is fixed and recorded. A validation whose numbers move between runs cannot be compared with
#: itself, and an unrecorded seed is an unreproducible number.
SEED = 20260930

#: A held-out season needs enough club-games for a coverage statement to mean anything. Below this
#: the season is reported as BLOCKED rather than scored, because a coverage figure on 40 games is
#: noise presented as a measurement.
MIN_HELD_OUT_CLUB_GAMES = 200

#: Quantiles at which tail coverage is stated. The upper end is where DST pricing actually lives: a
#: defence is rostered for its ceiling, so a model that is calibrated in the middle and wrong at
#: p95 is wrong where it is used.
COVERAGE_LEVELS = (0.50, 0.80, 0.90, 0.95, 0.99)


def _pbp_events() -> Outcome:
    """Defensive touchdowns, return touchdowns and safeties per (game_id, defending club).

    Re-derived here rather than imported from `dst.build()` on purpose. A validator that reuses the
    builder's own aggregation cannot catch an error in that aggregation; it would agree with it.
    """
    from nfl.warehouse import sources
    ev = collections.defaultdict(collections.Counter)
    seasons_read, files = [], []
    for season in D.PBP_SEASONS:
        sel = sources.select(sources.registry()['play_by_play'], season=season)
        if sel.state.value != 'PASS':
            continue
        seasons_read.append(season)
        files.append(sel.value['selected'])
        with _gzip.open(_REPO / sel.value['selected'], 'rt') as fh:
            for row in _csv.DictReader(fh):
                if row.get('season_type') != 'REG':
                    continue
                gid, dft, tdt = row.get('game_id'), row.get('defteam'), row.get('td_team')
                if not gid or not dft:
                    continue
                if row.get('touchdown') == '1' and tdt and tdt == dft:
                    ev[(gid, dft)]['def_td'] += 1
                    if row.get('return_touchdown') == '1':
                        ev[(gid, dft)]['return_td'] += 1
                if row.get('safety') == '1':
                    ev[(gid, dft)]['safety'] += 1
    if not seasons_read:
        return Outcome.blocked(
            'DST_VAL_NO_PLAY_BY_PLAY',
            'no play-by-play season could be selected, so defensive and return touchdowns cannot be '
            'separated and four of the six components have no data',
            cause=Cause.DATA, seasons_requested=list(D.PBP_SEASONS))
    return Outcome.ok('DST_VAL_PBP_READ',
                      value={'events': ev, 'seasons_read': seasons_read, 'files': files})


def panel() -> Outcome:
    """One row per defending club-game: what the defence faced and what it actually produced."""
    if not D.TG.exists():
        return Outcome.blocked('DST_VAL_NO_TEAM_GAME', f'{D.TG} missing', cause=Cause.DATA)
    pe = _pbp_events()
    if pe.state.value != 'PASS':
        return pe
    ev = pe.value['events']
    art = json.loads(D.TG.read_text())
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    by = {(r['game_id'], r['club']): r for r in rows}
    seasons = set(D.PBP_SEASONS)
    out, dropped = [], collections.Counter()
    for (gid, club), r in by.items():
        if r.get('season') not in seasons:
            dropped['SEASON_OUTSIDE_PLAY_BY_PLAY'] += 1
            continue
        o = by.get((gid, r.get('opponent')))
        if o is None:
            dropped['OPPONENT_ROW_ABSENT'] += 1
            continue
        # The defence's sacks and takeaways are the OPPONENT's sacks taken and turnovers committed.
        # Reading the club's own columns would invert the model, which dst.py records as verified
        # against PLAYER_GAME on 2,782 club-games.
        if not all(isinstance(o.get(k), (int, float)) for k in ('sacks', 'turnovers', 'points')):
            dropped['OPPONENT_COLUMNS_NOT_NUMERIC'] += 1
            continue
        if not isinstance(r.get('week'), int):
            dropped['WEEK_MISSING'] += 1
            continue
        e = ev.get((gid, club), {})
        out.append({
            'season': int(r['season']), 'week': int(r['week']), 'game_id': gid, 'club': club,
            'points_allowed': float(o['points']),
            'sacks': float(o['sacks']), 'takeaways': float(o['turnovers']),
            'def_td': float(e.get('def_td', 0)), 'return_td': float(e.get('return_td', 0)),
            'safety': float(e.get('safety', 0)),
        })
    if not out:
        return Outcome.fail(
            'DST_VAL_PANEL_EMPTY',
            'the club-game panel is empty. An empty panel is an error, not a validation with no '
            'games in it.', dropped=dict(dropped))
    for r in out:
        r['dk_points'] = (D.tier(r['points_allowed'])
                          + D.SACK_POINTS * r['sacks'] + D.TAKEAWAY_POINTS * r['takeaways']
                          + D.DEFENSIVE_TD_POINTS * r['def_td'] + D.SAFETY_POINTS * r['safety'])
    return Outcome.ok('DST_VAL_PANEL_BUILT', value={
        'rows': out, 'n': len(out), 'dropped': dict(dropped),
        'seasons': sorted({r['season'] for r in out}),
        'seasons_read_from_pbp': pe.value['seasons_read'],
        'pbp_files': pe.value['files'],
    })


def _band_of(pa: float):
    for lo, hi in D.CONDITIONING_BANDS:
        if lo <= pa < hi:
            return (lo, hi)
    return D.CONDITIONING_BANDS[-1]


def fit(rows) -> dict:
    """The model as `dst.build()` builds it: the within-band empirical pool of four-tuples."""
    pool = collections.defaultdict(list)
    for r in rows:
        pool[_band_of(r['points_allowed'])].append(
            (r['sacks'], r['takeaways'], r['def_td'], r['safety']))
    return dict(pool)


def _clustered_se(residuals_by_cluster) -> tuple:
    """SE of the mean residual, blocked by cluster, plus the cluster count.

    Cluster-level means are averaged, so two defences in one week are not two independent draws.
    Returns (se, n_clusters). With fewer than two clusters there is no SE, and None is returned
    rather than a zero that would read as certainty.
    """
    means = [sum(v) / len(v) for v in residuals_by_cluster.values() if v]
    k = len(means)
    if k < 2:
        return None, k
    m = sum(means) / k
    var = sum((x - m) ** 2 for x in means) / (k - 1)
    return math.sqrt(var / k), k


def _quantile(sorted_xs, q: float) -> float:
    if not sorted_xs:
        raise ValueError('quantile of an empty sample')
    i = min(len(sorted_xs) - 1, max(0, int(round(q * (len(sorted_xs) - 1)))))
    return sorted_xs[i]


def evaluate(train_rows, test_rows, *, seed: int = SEED) -> Outcome:
    """Score one held-out season against a model fitted only on earlier seasons."""
    pool = fit(train_rows)
    thin = {f'{lo}-{hi}': len(v) for (lo, hi), v in pool.items() if len(v) < D.MIN_PER_BAND}
    if thin:
        return Outcome.blocked(
            'DST_VAL_TRAIN_BANDS_TOO_THIN',
            'a points-allowed band has fewer training club-games than the model itself requires, so '
            'this fold would score a model the builder would have refused to build',
            cause=Cause.DATA, thin_bands=thin, min_per_band=D.MIN_PER_BAND)
    missing = sorted({f'{lo}-{hi}' for lo, hi in (_band_of(r['points_allowed']) for r in test_rows)}
                     - {f'{lo}-{hi}' for lo, hi in pool})
    if missing:
        return Outcome.blocked(
            'DST_VAL_TEST_BAND_UNFITTED',
            f'{len(missing)} band(s) occur in the held-out season with no training games',
            cause=Cause.DATA, bands=missing)

    rng = random.Random(seed)
    comp = {}

    # --- 1..4: each component is the band mean under the FITTED pool against the realised value.
    # Closed form from the pool, so these carry no Monte Carlo noise at all.
    def band_mean(band, idx):
        v = pool[band]
        return sum(t[idx] for t in v) / len(v)

    def band_share_nonzero(band, idx):
        v = pool[band]
        return sum(1 for t in v if t[idx]) / len(v)

    specs = (
        ('sack_rate', lambda r: r['sacks'], lambda b: band_mean(b, 0), 'sacks per club-game'),
        ('turnover_rate', lambda r: r['takeaways'], lambda b: band_mean(b, 1),
         'takeaways per club-game'),
        ('defensive_td_frequency', lambda r: 1.0 if r['def_td'] else 0.0,
         lambda b: band_share_nonzero(b, 2), 'share of club-games with at least one defensive TD'),
    )
    for name, actual_of, pred_of, unit in specs:
        res_by_week = collections.defaultdict(list)
        acts, preds = [], []
        for r in test_rows:
            b = _band_of(r['points_allowed'])
            a, p = actual_of(r), pred_of(b)
            acts.append(a)
            preds.append(p)
            res_by_week[(r['season'], r['week'])].append(a - p)
        se, k = _clustered_se(res_by_week)
        bias = sum(a - p for a, p in zip(acts, preds)) / len(acts)
        comp[name] = {
            'unit': unit, 'n_club_games': len(acts),
            'mean_actual': round(sum(acts) / len(acts), 4),
            'mean_predicted': round(sum(preds) / len(preds), 4),
            'bias_actual_minus_predicted': round(bias, 4),
            'week_blocked_se': None if se is None else round(se, 4),
            'n_week_clusters': k,
            'z_if_se': None if not se else round(bias / se, 3),
            'SE_IS_BLOCKED_BY': '(season, week); two defences in one week are not independent draws',
        }

    # --- mean scoring: the DK total, which is where the components land together.
    res_by_week = collections.defaultdict(list)
    acts, preds = [], []
    for r in test_rows:
        b = _band_of(r['points_allowed'])
        p = (D.tier(r['points_allowed']) + D.SACK_POINTS * band_mean(b, 0)
             + D.TAKEAWAY_POINTS * band_mean(b, 1) + D.DEFENSIVE_TD_POINTS * band_mean(b, 2)
             + D.SAFETY_POINTS * band_mean(b, 3))
        acts.append(r['dk_points'])
        preds.append(p)
        res_by_week[(r['season'], r['week'])].append(r['dk_points'] - p)
    n = len(acts)
    bias = sum(a - p for a, p in zip(acts, preds)) / n
    mae = sum(abs(a - p) for a, p in zip(acts, preds)) / n
    rmse = math.sqrt(sum((a - p) ** 2 for a, p in zip(acts, preds)) / n)
    ma, mp = sum(acts) / n, sum(preds) / n
    sa = math.sqrt(sum((a - ma) ** 2 for a in acts) / (n - 1)) if n > 1 else 0.0
    sp = math.sqrt(sum((p - mp) ** 2 for p in preds) / (n - 1)) if n > 1 else 0.0
    cov = sum((a - ma) * (p - mp) for a, p in zip(acts, preds)) / (n - 1) if n > 1 else 0.0
    r_pearson = None if sa <= 0 or sp <= 0 else cov / (sa * sp)
    se, k = _clustered_se(res_by_week)
    comp['mean_scoring'] = {
        'unit': 'DK DST fantasy points per club-game',
        'n_club_games': n,
        'mean_actual': round(ma, 4), 'mean_predicted': round(mp, 4),
        'bias_actual_minus_predicted': round(bias, 4),
        'week_blocked_se': None if se is None else round(se, 4), 'n_week_clusters': k,
        'z_if_se': None if not se else round(bias / se, 3),
        'mae': round(mae, 4), 'rmse': round(rmse, 4),
        'sd_actual': round(sa, 4), 'sd_predicted': round(sp, 4),
        'sd_ratio_pred_over_actual': None if sa <= 0 else round(sp / sa, 4),
        'pearson_r': None if r_pearson is None else round(r_pearson, 4),
        'DISCRIMINATION_AND_CALIBRATION_ARE_DIFFERENT': (
            'pearson_r is discrimination and the coverage block is calibration. Passing one says '
            'nothing about the other.'),
        'WHAT_IS_ORACLED_HERE': (
            'points allowed is the REALISED value, not a prediction. This measures the DST model '
            'given a correct opponent total, which is not live predictive accuracy.'),
    }

    # --- 5: return TD frequency. The model does not represent it. Refused, with the gap measured.
    ret = sum(1 for r in test_rows if r['return_td']) / n
    anytd = sum(1 for r in test_rows if r['def_td']) / n
    comp['return_td_frequency'] = {
        'state': 'REFUSED',
        'code': 'RETURN_TD_NOT_REPRESENTED_IN_THE_MODEL',
        'cause': 'DATA',
        'why': ('dst.build() counts return_touchdown from play-by-play and then stores only the '
                'four-tuple (sacks, turnovers, def_td, safety). The band therefore cannot '
                'distinguish a punt-return touchdown from a pick-six, and there is no predicted '
                'return-TD frequency to score. Scoring one anyway would be a fabricated result.'),
        'realised_share_of_club_games_with_a_return_td': round(ret, 4),
        'realised_share_with_any_defensive_td': round(anytd, 4),
        'SIZE_OF_THE_GAP': ('the realised rates are reported so the cost of the omission is on the '
                            'record. They are NOT a validation of anything.'),
        'WOULD_RESOLVE_IT': ('store return_td in the band tuple, which requires a change to '
                            'nfl/sim/dst.py and a rebuild of DST_MODEL.json'),
    }

    # --- 6: tail calibration. Needs the predictive DISTRIBUTION, so it draws.
    hits = {q: 0 for q in COVERAGE_LEVELS}
    for r in test_rows:
        b = _band_of(r['points_allowed'])
        v = pool[b]
        draws = sorted(
            D.tier(r['points_allowed']) + D.SACK_POINTS * t[0] + D.TAKEAWAY_POINTS * t[1]
            + D.DEFENSIVE_TD_POINTS * t[2] + D.SAFETY_POINTS * t[3]
            for t in (v[rng.randrange(len(v))] for _ in range(N_DRAW)))
        for q in COVERAGE_LEVELS:
            if r['dk_points'] <= _quantile(draws, q):
                hits[q] += 1
    comp['tail_calibration'] = {
        'unit': 'share of club-games at or below the predicted quantile',
        'n_club_games': n, 'n_draws_per_club_game': N_DRAW, 'seed': seed,
        'coverage': {f'p{int(q * 100)}': round(hits[q] / n, 4) for q in COVERAGE_LEVELS},
        'nominal': {f'p{int(q * 100)}': q for q in COVERAGE_LEVELS},
        'gap': {f'p{int(q * 100)}': round(hits[q] / n - q, 4) for q in COVERAGE_LEVELS},
        'NOT_WRITABLE_AS_CALIBRATED': (
            'a gap near zero is not evidence of adequacy. Saying "calibrated" needs a predeclared '
            'equivalence margin and a two-one-sided test, and neither exists for this yet.'),
    }
    return Outcome.ok('DST_VAL_FOLD_SCORED', value=comp)


def run() -> Outcome:
    """Forward-chain across seasons: fit on everything earlier, score the next one."""
    pn = panel()
    if pn.state.value != 'PASS':
        return pn
    rows = pn.value['rows']
    seasons = pn.value['seasons']
    if len(seasons) < 2:
        return Outcome.blocked(
            'DST_VAL_ONE_SEASON_ONLY',
            f'seasons available: {seasons}. An out-of-sample fold needs an earlier season to fit on, '
            f'and an in-sample DST validation is vacuous because the model resamples its own pool.',
            cause=Cause.DATA, seasons=seasons)

    folds, blocked = [], []
    for s in seasons[1:]:
        train = [r for r in rows if r['season'] < s]
        test = [r for r in rows if r['season'] == s]
        if len(test) < MIN_HELD_OUT_CLUB_GAMES:
            blocked.append({'held_out_season': s, 'n_club_games': len(test),
                            'code': 'DST_VAL_HELD_OUT_SEASON_TOO_SMALL',
                            'floor': MIN_HELD_OUT_CLUB_GAMES,
                            'why': ('a coverage figure on this few club-games is noise presented as '
                                    'a measurement')})
            continue
        o = evaluate(train, test)
        if o.state.value != 'PASS':
            blocked.append({'held_out_season': s, 'code': o.code, 'detail': o.detail,
                            'evidence': o.evidence})
            continue
        folds.append({'held_out_season': s, 'n_train_club_games': len(train),
                      'n_test_club_games': len(test), 'components': o.value})

    if not folds:
        return Outcome.blocked(
            'DST_VAL_NO_FOLD_SCORED',
            'no season could be scored out of sample, so there is no validation result. Reporting '
            'the in-sample numbers instead would report a bootstrap of the fit as a test of it.',
            cause=Cause.DATA, blocked=blocked)

    art = {
        'ARTIFACT': 'DST_VALIDATION',
        'SIX_COMPONENTS_NOT_ONE': (
            'mean scoring, sack rate, turnover rate, defensive TD frequency, return TD frequency and '
            'tail calibration are reported separately because they are separate properties and a '
            'single verdict hides which one is wrong. Owner instruction 2026-09-30.'),
        'WHY_OUT_OF_SAMPLE': (
            'DstModel.draw resamples the within-band empirical pool, so in sample five of the six '
            'components agree with the data by construction. Each fold fits on strictly earlier '
            'seasons and scores the next one.'),
        'WHAT_THIS_DOES_NOT_MEASURE': (
            'points allowed is the REALISED opponent total, so every number here is conditional on a '
            'correct opponent score. This is the DST model in isolation, not live accuracy.'),
        'return_td_status': 'REFUSED -- measured from play-by-play and then discarded by the model',
        'seed': SEED, 'n_draws_per_club_game': N_DRAW,
        'panel': {k: pn.value[k] for k in ('n', 'dropped', 'seasons', 'seasons_read_from_pbp',
                                           'pbp_files')},
        'n_folds_scored': len(folds), 'folds': folds, 'blocked': blocked,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=2))
    return Outcome.ok('DST_VALIDATED_BY_COMPONENT', value={
        'artifact': str(OUT.relative_to(_REPO)), 'n_folds_scored': len(folds),
        'n_blocked': len(blocked),
        'summary': [{'held_out_season': f['held_out_season'],
                     'mean_scoring_bias': f['components']['mean_scoring'][
                         'bias_actual_minus_predicted'],
                     'mean_scoring_z': f['components']['mean_scoring']['z_if_se'],
                     'pearson_r': f['components']['mean_scoring']['pearson_r'],
                     'sd_ratio': f['components']['mean_scoring']['sd_ratio_pred_over_actual'],
                     'coverage': f['components']['tail_calibration']['coverage']}
                    for f in folds],
    })


if __name__ == '__main__':
    o = run()
    print(o.state.value, o.code)
    v = o.value if o.state.value == 'PASS' else (o.detail, o.evidence)
    print(json.dumps(v, indent=2, default=str)[:6000])
    raise SystemExit(0 if o.state.value == 'PASS' else 1)
