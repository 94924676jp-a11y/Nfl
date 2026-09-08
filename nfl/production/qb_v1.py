"""QB V1 production layer. A BASELINE SELECTION, not a promotion.

    dropbacks = pass_attempts + scrambles - spikes

Policy: TEAM-QB AGGREGATE THEN ALLOCATION. Forecast team dropbacks, allocate by
a prior-only share, apply per-QB conversion. 22.7% of team-games carry more
than one QB with a dropback, so one-QB-per-game is wrong one time in four.

KNOWN LIMITATION, QUANTIFIED AND NOT HIDDEN: in multi-QB team-games this layer
over-predicts passing yards by +79.8 on average (n=699) against -13.8 in
single-QB games, with nominal-90 coverage 0.794 against 0.961. The prior-only
share of a QB who is later pulled is necessarily too high, and no pregame
information in this project resolves it. It is reported on every run rather
than smoothed away.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
for q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
          str(_REPO / 'nfl' / 'research' / 'rc1')):
    if q not in sys.path:
        sys.path.insert(0, q)

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'qb-v1-aggregate-then-allocate-1'
FIELDS = ('db', 'att', 'cmp', 'sacks', 'scr', 'pyds', 'ptd', 'int',
          'rush_opp', 'ryds', 'rtd')

KNOWN_LIMITATIONS = {
    'multi_qb_over_prediction': {
        'measured_bias_pass_yards': 79.89,
        'n': 699,
        'single_qb_bias': -13.81,
        'multi_qb_cover90': 0.794,
        'single_qb_cover90': 0.961,
        'mechanism': ('prior-only dropback shares are not normalised within a '
                      'team-game. Measured 2024: multi-QB team-games draw '
                      '62.51 team dropbacks against a realised 36.61, '
                      '+25.90; single-QB team-games draw 34.45 against '
                      '36.80, -2.35.'),
        'cause': 'the prior-only dropback share of a QB later pulled is '
                 'necessarily too high; no pregame information in this project '
                 'resolves it',
        'policy': 'reported on every run, never smoothed away',
    },
    'int_discrimination': {
        'pearson_r': 0.0348,
        'note': 'interception counts carry essentially no game-level '
                'discrimination in this layer. Recorded rather than dressed up.',
    },
    'discrete_low_count_intervals': {
        'note': ('for counts that are zero in most games -- interceptions, '
                 'rushing touchdowns, passing touchdowns -- the central 50% '
                 'interval covers far more than 50% (0.858, 0.902, 0.801) '
                 'because the distribution has an atom at zero. This is '
                 'discreteness, not over-wide intervals, and it is recorded '
                 'so the coverage table is not read as a calibration defect.'),
    },
}

# The predeclared four-rung ladder, measured. L1 is the production baseline.
LADDER_RESULT = {
    'metric': 'pass-yards CRPS, 2022-2025, n=2,494 over 1,087 games',
    'bootstrap': 'game-clustered, 400 resamples',
    'L0_pooled': {'crps': 54.9452, 'delta_vs_L1': +6.3021,
                  'ci': [+5.3420, +7.2837], 'separates': True},
    'L1_shrunk': {'crps': 48.6431, 'reference': True},
    'L2_ewma': {'crps': 51.0475, 'delta_vs_L1': +2.4044,
                'ci': [+1.1912, +3.4598], 'separates': True},
    'L3_shrunk_ewma': {'crps': 49.0105, 'delta_vs_L1': +0.3674,
                       'ci': [-0.4738, +1.1892], 'separates': False},
    'selection': 'L1',
    'why': ('L0 and L2 are worse and their intervals exclude zero. L3 does '
            'NOT separate from L1, so the ladder does not establish that '
            'either is better; L1 is retained as the simpler of two '
            'indistinguishable rungs. This is a production BASELINE '
            'SELECTION on mined data, not evidence that L1 is superior and '
            'not a promotion.'),
}


FRAME_PATH = _REPO / 'nfl' / 'research' / 'qb2' / 'qb.pkl'


def artifact_hash() -> Outcome:
    """sha256 of the QB frame this layer consumes.

    The frame is a DERIVED MODEL ARTIFACT, not a prospective capture, so it is
    hashed here rather than declared to the capture registry -- that registry
    governs sources with T-90 availability windows, and putting a bulk
    historical derivative in it would misrepresent what was capturable when.
    """
    import hashlib
    if not FRAME_PATH.exists():
        return Outcome.blocked(
            'QB_FRAME_MISSING',
            f'{FRAME_PATH} is absent; the layer has no inputs and returns a '
            f'named refusal rather than an empty forecast', cause=Cause.DATA)
    h = hashlib.sha256(FRAME_PATH.read_bytes()).hexdigest()
    return Outcome.ok('QB_FRAME_HASHED', value=h,
                      detail=f'{FRAME_PATH.name} {FRAME_PATH.stat().st_size} '
                             f'bytes', path=str(FRAME_PATH.relative_to(_REPO)))


def slate(season: int, week: int, game_ids=None) -> Outcome:
    """Load the QB frame the way live execution would: the layer fetches its
    own inputs rather than being handed a dictionary."""
    import qb2_lib as Q
    allrows = Q.load()
    rows = [r for r in allrows
            if r['season'] == season and r['week'] == week
            and Q.eligible(r)
            and (game_ids is None or r['game_id'] in set(game_ids))]
    if not rows:
        return Outcome.blocked(
            'QB_SLATE_EMPTY',
            f'no eligible QB rows for season {season} week {week}'
            + (f' games {sorted(set(game_ids))}' if game_ids else '')
            + '. An empty slate is a refusal, not a forecast of nothing.',
            cause=Cause.DATA, season=season, week=week)
    return Outcome.ok('QB_SLATE_LOADED', value=(rows, allrows),
                      detail=f'{len(rows)} QB-game(s) over '
                             f'{len({r["game_id"] for r in rows})} game(s)',
                      n_rows=len(rows), n_frame=len(allrows))


def forecast(rows, season, allrows, seed=20260908, m=1000) -> Outcome:
    """Run the V1 layer. Returns draw matrices keyed by statistic."""
    import time as _time
    import qb2_lib as Q
    if not rows:
        return Outcome.blocked(
            'STAGE_NOT_IMPLEMENTED',
            'no eligible QB rows were supplied; a named refusal is returned '
            'rather than a fabricated forecast', cause=Cause.DEPENDENCY)
    t0 = _time.perf_counter()
    try:
        D = Q.simulate(rows, season, allrows, seed=seed, m=m)
    except Exception as exc:                                     # noqa: BLE001
        return Outcome.fail('QB_V1_RAISED', f'{type(exc).__name__}: {exc}')
    # ACTUAL DRAW GENERATION, timed around the simulate call alone. Orchestrator
    # overhead is measured separately by the pipeline and is not this number.
    draw_seconds = _time.perf_counter() - t0
    missing = [f for f in FIELDS if f not in D]
    if missing:
        return Outcome.fail('QB_V1_INCOMPLETE',
                            f'missing {missing}; a partial QB draw set is not '
                            f'a draw set', missing=missing)
    # per-draw coherence, checked here rather than trusted downstream
    bad = int((D['cmp'] > D['att']).sum())
    bad += int((D['att'] + D['sacks'] + D['scr'] > D['db'] + 1e-9).sum())
    if bad:
        return Outcome.fail(
            'QB_V1_INCOHERENT_DRAWS',
            f'{bad} draw cell(s) violate completions <= attempts or '
            f'attempts + sacks + scrambles <= dropbacks', n_bad=bad)
    return Outcome.ok(
        'QB_V1_FORECAST', value=D,
        detail=f'{len(rows)} QB-game(s), {m} draws, {SPEC_VERSION}',
        spec_version=SPEC_VERSION,
        draw_generation_seconds=round(draw_seconds, 4),
        n_qb_games=len(rows), n_draws=m,
        draw_cells=int(D['db'].size) * len(FIELDS),
        known_limitations=list(KNOWN_LIMITATIONS))


def identity_check(D) -> Outcome:
    """dropbacks == attempts + sacks + scrambles, per draw."""
    lhs = D['att'] + D['sacks'] + D['scr']
    bad = int((np.abs(lhs - D['db']) > 1e-9).sum())
    if bad:
        return Outcome.fail(
            'QB_DROPBACK_IDENTITY_VIOLATED',
            f'{bad} draw cell(s) where attempts + sacks + scrambles != '
            f'dropbacks. This is the identity the whole layer rests on.',
            n_bad=bad)
    return Outcome.ok('QB_DROPBACK_IDENTITY_HOLDS',
                      value=int(D['db'].size),
                      detail=f'holds on all {D["db"].size} draw cells')
