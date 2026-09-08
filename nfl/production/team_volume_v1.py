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


def forecast(season: int, week: int, teams, m: int = 200,
             seed: int = 20260908) -> Outcome:
    """Prospective team-volume draws for one slate. Returns (metric, team) ->
    an (m,) draw vector."""
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
    out, meta = {}, {}
    for metric in METRICS:
        sel = selected(metric, season)
        pros = [{'season': season, 'week': week, 'ord': ordinal, 'team': t,
                 'coach': co.value[t], **{k: 0 for k in METRICS}}
                for t in teams]
        rows = sorted([dict(r) for r in panel] + pros,
                      key=lambda x: (x['ord'], x['team']))
        V.attach(rows, metric)                      # the FROZEN research cut
        hist = [r for r in rows if r['ord'] < ordinal and r[metric] > 0]
        lm = float(np.mean([r[metric] for r in hist]))
        for r in rows:
            r['_b'] = V.baselines(r, lm)
        for r in hist:
            r['_resid'] = r[metric] - r['_b'][sel['estimator']]
        fit = V.build_forms(hist, metric, V.SEED)
        pr = [r for r in rows if r['ord'] == ordinal]
        rng = np.random.default_rng([seed, ordinal, hash(metric) % 9973])
        # M_DRAWS is pre-declared inside the research module; draw() returns
        # that many columns, so the slice is explicit rather than implicit.
        res = V.draw(sel['form'], fit, pr, rng)[:, :m]
        for i, r in enumerate(pr):
            out[(metric, r['team'])] = np.maximum(
                r['_b'][sel['estimator']] + res[i], 0.0)
        meta[metric] = {**sel, 'league_mean': lm, 'n_train': len(hist),
                        'negative_draws_clipped_to_zero': int(
                            (np.array([r['_b'][sel['estimator']]
                                       for r in pr]).reshape(-1, 1)
                             + res < 0).sum())}
    return Outcome.ok('TEAM_VOLUME_OK', value=out,
                      detail=f'{len(teams)} team(s), {len(METRICS)} metrics, '
                             f'{m} draws',
                      spec_version=SPEC_VERSION, selections=meta,
                      coach_snapshot=co.evidence['snapshot'],
                      known_limitations=list(KNOWN_LIMITATIONS))
