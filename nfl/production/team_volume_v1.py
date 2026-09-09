"""D1 team environment: prospective team-volume draws.

RESEARCH-TO-PRODUCTION EQUIVALENCE BY CONSTRUCTION, NOT BY REIMPLEMENTATION.

This module does not re-derive P4B. It IMPORTS `p4b_volume` and calls its own
`attach`, `baselines`, `build_forms` and `draw`. There is therefore no second
copy of the mathematics to drift from the first, and the equivalence test in
nfl/tests/test_v1_nonqb_production.py checks that identical inputs and seeds
give identical numbers rather than merely similar ones.

WHAT THE ACCEPTED RESEARCH SAYS, PRESERVED RATHER THAN IMPROVED

P4 found team volume close to unforecastable -- the best simple baseline was
the league mean in two seasons of four, and correlation peaked at 0.167. P4B's
job was to make that uncertainty explicit rather than to reduce it. The
selected point estimators for 2025, the most recent evaluated season, are:

    team_off_snaps        league_mean
    team_dropbacks_part   coach_prior
    team_targets          ewma
    team_carries          coach_prior
    team_rz_carries       coach_prior

Those selections are READ from the frozen research output, never re-chosen
here. Re-selecting an estimator inside production would be exactly the retuning
this packet forbids.

CHRONOLOGY. The prospective row for an upcoming week is appended to the
historical panel at its own ordinal and the research `attach` is re-run over
the whole sorted list, so each row inherits the frozen strictly-earlier cut.
The same discipline as the QB layer, for the same reason.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4b')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

SPEC_VERSION = 'team-volume-v1-p4b-frozen-1'
METRICS = ('team_off_snaps', 'team_dropbacks_part', 'team_targets',
           'team_carries', 'team_rz_carries')
RESULTS = _REPO / 'nfl' / 'research' / 'p4b' / 'volume_results.json'
PANEL = _REPO / 'nfl' / 'research' / 'inputs' / 'denom_panel.csv.gz'
SCHED_GLOB = 'schedules.*.csv.gz'

KNOWN_LIMITATIONS = {
    'team_volume_is_near_unforecastable': {
        'source': 'P4 / P4B, accepted',
        'note': 'the best simple baseline was the league mean in two seasons '
                'of four and correlation peaked at 0.167. These draws are '
                'honest about that width; they do not narrow it.',
        'policy': 'reported on every run, never presented as skill',
    },
}


def _panel():
    rows = []
    with gzip.open(PANEL, 'rt') as fh:
        for r in csv.DictReader(fh):
            for k in ('season', 'week', 'ord'):
                r[k] = int(r[k])
            for k in METRICS:
                r[k] = int(r[k])
            rows.append(r)
    rows.sort(key=lambda x: (x['ord'], x['team']))
    return rows


def coaches(season, week):
    """Head coach per team for an upcoming week, from the captured schedule.

    `coach_prior` is the selected estimator for three of the five metrics, so
    this is a load-bearing prediction-time input, not a convenience.
    """
    import glob
    snaps = sorted(glob.glob(str(_REPO / 'nfl' / 'vintage' / SCHED_GLOB)))
    if not snaps:
        return Outcome.blocked('NO_SCHEDULE_SNAPSHOT',
                               'no schedules artifact has been captured',
                               cause=Cause.DEPENDENCY)
    out = {}
    with gzip.open(snaps[-1], 'rt') as fh:
        for r in csv.DictReader(fh):
            if (r.get('season') != str(season) or r.get('week') != str(week)
                    or r.get('game_type') != 'REG'):
                continue
            for side in ('home', 'away'):
                t, c = r.get(f'{side}_team'), (r.get(f'{side}_coach') or '')
                if t and c.strip():
                    out[t] = c.strip()
    if not out:
        return Outcome.blocked(
            'NO_COACH_FOR_SLATE',
            f'the captured schedule carries no head coach for {season} week '
            f'{week}; three of five volume metrics select coach_prior, so an '
            f'absent coach is a missing model input rather than a cosmetic gap',
            cause=Cause.DATA)
    return Outcome.ok('COACHES_RESOLVED', value=out, n_teams=len(out),
                      snapshot=os.path.basename(snaps[-1]))


def selected(metric, season):
    """The estimator and form chosen by the frozen research walk-forward.

    Read, never re-chosen. The latest evaluated season's selection is used for
    a season the research never evaluated, which is the same rule the research
    applied to itself: choose on prior seasons only.
    """
    res = json.loads(RESULTS.read_text())[metric]
    ev = max(int(k) for k in res if int(k) < season)
    r = res[str(ev)]
    return {'estimator': r['point_estimator'],
            'form': r.get('form_C') or r.get('form_B') or 'empirical',
            'selected_on_season': ev}


# PER-SLATE FIT CACHE (s.J). The fit depends ONLY on history -- the attached
# panel, the league mean and the residual pools -- and not on which teams are
# being forecast. So it can be computed once per (season, week, metric) and
# reused across all 16 games, while `V.draw` still runs per game with the same
# rng seed and the same row count as before.
#
# THIS IS WHY IT IS DRAW-EQUIVALENT: nothing cached touches the random stream.
# A cache that also hoisted the draw would change every number, because the rng
# is consumed row by row; that version was rejected rather than shipped.
_FIT_CACHE: dict = {}


def _fit_for(metric, season, week, ordinal):
    key = (metric, season, week)
    if key in _FIT_CACHE:
        return _FIT_CACHE[key]
    import p4b_volume as V
    sel = selected(metric, season)
    panel = _panel()
    hist = [r for r in panel if r['ord'] < ordinal and r[metric] > 0]
    lm = float(np.mean([r[metric] for r in hist]))
    _FIT_CACHE[key] = (sel, panel, lm, None)
    return _FIT_CACHE[key]


def cache_clear():
    _FIT_CACHE.clear()


# J1: the five metrics were drawn INDEPENDENTLY -- a separate RNG stream per
# metric -- which reproduced corr(team_carries, team_dropbacks) = -0.004
# against a historical -0.393. J1 tested four architectures walk-forward over
# 2,174 team-games and the winner was the cheapest: draw ONE historical
# team-game index per simulation draw and take every residual from that same
# game. Marginals are untouched to three decimal places, the accounting
# invariants go to zero, clipping goes to zero, and the reproduced correlation
# becomes -0.406.
#
# IT IS OFF BY DEFAULT AND THAT IS DELIBERATE. No fit changes, but every drawn
# number changes, so switching it on is an owner decision rather than an
# engineering one. See nfl/research/j1/J1_FINDING.md.
JOINT_RESIDUALS_DEFAULT = False


def forecast(season: int, week: int, teams, m: int = 200,
             seed: int = 20260908, joint_residuals: bool = None) -> Outcome:
    """Prospective team-volume draws for one slate. Returns (metric, team) ->
    an (m,) draw vector.

    `joint_residuals` selects the J1 draw mode. None means the module default.
    """
    import p4b_volume as V
    if not teams:
        return Outcome.blocked('TEAM_VOLUME_NO_TEAMS',
                               'no teams supplied for the slate',
                               cause=Cause.DATA)
    co = coaches(season, week)
    if co.state.name != 'PASS':
        return co
    panel = _panel()
    ordinal = season * 100 + week
    if any(r['ord'] >= ordinal for r in panel):
        return Outcome.fail(
            'TEAM_VOLUME_HISTORY_NOT_STRICTLY_EARLIER',
            f'the volume panel already contains rows at or after ordinal '
            f'{ordinal}')
    missing = [t for t in teams if t not in co.value]
    if missing:
        return Outcome.blocked(
            'NO_COACH_FOR_SLATE',
            f'no head coach resolved for {missing}', cause=Cause.DATA,
            teams=missing)
    joint = (JOINT_RESIDUALS_DEFAULT if joint_residuals is None
             else bool(joint_residuals))
    out, meta = {}, {}
    fits = {}
    for metric in METRICS:
        sel, panel_c, lm, fit_c = _fit_for(metric, season, week, ordinal)
        pros = [{'season': season, 'week': week, 'ord': ordinal, 'team': t,
                 'coach': co.value[t], **{k: 0 for k in METRICS}}
                for t in teams]
        rows = sorted([dict(r) for r in panel_c] + pros,
                      key=lambda x: (x['ord'], x['team']))
        V.attach(rows, metric)                      # the FROZEN research cut
        hist = [r for r in rows if r['ord'] < ordinal and r[metric] > 0]
        for r in rows:
            r['_b'] = V.baselines(r, lm)
        for r in hist:
            r['_resid'] = r[metric] - r['_b'][sel['estimator']]
        # The fit is history-only: `hist` and every `_resid` in it are
        # unaffected by which teams are prospective, because attach processes
        # in ordinal order and the prospective rows sort last. So it is
        # identical across the 16 games of a slate and is computed once.
        fit = fit_c if fit_c is not None else V.build_forms(hist, metric,
                                                            V.SEED)
        _FIT_CACHE[(metric, season, week)] = (sel, panel_c, lm, fit)
        pr = [r for r in rows if r['ord'] == ordinal]
        fits[metric] = (sel, fit, pr, hist)
        if joint:
            continue                      # assembled jointly, below
        rng = np.random.default_rng([seed, ordinal, hash(metric) % 9973])
        res = V.draw(sel['form'], fit, pr, rng)[:, :m]
        for i, r in enumerate(pr):
            out[(metric, r['team'])] = np.maximum(
                r['_b'][sel['estimator']] + res[i], 0.0)
        meta[metric] = {**sel, 'league_mean': lm, 'n_train': len(hist),
                        'negative_draws_clipped_to_zero': int(
                            (np.array([r['_b'][sel['estimator']]
                                       for r in pr]).reshape(-1, 1)
                             + res < 0).sum())}
    if joint:
        # ONE historical team-game per draw, every residual from that game.
        #
        # THE INDEX MUST BE DRAWN FROM THE SAME POOL THE FITTED FORM USES.
        # All five metrics select `coach_empirical`, so the residual for a
        # prospective row is resampled from THAT COACH's residuals. A first
        # version of this drew the shared index from the global pool, which is
        # a different distribution: it moved the team_rz_carries mean by 5.2%
        # and put 0.49% of its draws on the zero floor, while claiming no
        # marginal had been touched. Sharing an index across metrics is only
        # legitimate if each metric still draws from its own fitted pool.
        keyed = {}
        for metric, (sel, fit, pr, hist) in fits.items():
            keyed[metric] = {(h['team'], h['ord']):
                             h[metric] - h['_b'][sel['estimator']]
                             for h in hist}
        common = [k for k in keyed[METRICS[0]]
                  if all(k in keyed[mm] for mm in METRICS)]
        if not common:
            return Outcome.fail(
                'JOINT_RESIDUAL_POOL_EMPTY',
                'no historical team-game carries a residual for every metric, '
                'so a joint resample is impossible')
        coach_of = {}
        for _m, (_s, _f, _p, hh) in fits.items():
            for h in hh:
                coach_of[(h['team'], h['ord'])] = h.get('coach')
        by_coach = {}
        for k in common:
            by_coach.setdefault(coach_of.get(k), []).append(k)
        rng = np.random.default_rng([seed, ordinal, 4242])
        pr0 = fits[METRICS[0]][2]
        n_fallback = 0
        for i, r0 in enumerate(pr0):
            pool_keys = by_coach.get(r0.get('coach'))
            if not pool_keys:
                pool_keys = common          # the same fallback V.draw uses
                n_fallback += 1
            pick = rng.integers(0, len(pool_keys), m)
            chosen = [pool_keys[j] for j in pick]
            for metric in METRICS:
                sel, fit, pr, _h = fits[metric]
                res_v = np.array([keyed[metric][k] for k in chosen])
                out[(metric, pr[i]['team'])] = np.maximum(
                    pr[i]['_b'][sel['estimator']] + res_v, 0.0)
        for metric, (sel, fit, pr, hist) in fits.items():
            meta[metric] = {**sel, 'league_mean': lm, 'n_train': len(hist),
                            'draw_mode': 'joint_residuals',
                            'joint_pool_team_games': len(common),
                            'coaches_with_a_pool': len(by_coach),
                            'rows_on_global_fallback': n_fallback}
    return Outcome.ok('TEAM_VOLUME_OK', value=out,
                      detail=f'{len(teams)} team(s), {len(METRICS)} metrics, '
                             f'{m} draws',
                      spec_version=SPEC_VERSION, selections=meta,
                      draw_mode=('joint_residuals' if joint
                                 else 'independent_per_metric'),
                      coach_snapshot=co.evidence['snapshot'],
                      known_limitations=list(KNOWN_LIMITATIONS))
