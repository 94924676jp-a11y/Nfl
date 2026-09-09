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


def slate_prospective(season: int, week: int, qb_players,
                      include_cold_start: bool = False) -> Outcome:
    """The player set for an UPCOMING game comes from the ROSTER, not history.

    THE DEFECT THIS FIXES, found by the NFL-V1-R1 full-slate rehearsal:
    `slate()` filters the historical frame by season, so for a season that has
    not been played it returns nothing and the layer refuses every game
    (QB_SLATE_EMPTY on 15 of 16). A layer that can only name players already in
    its history can only ever forecast the past.

    WHY THIS IS SAFE. Every outcome-field reference in `qb2_lib.simulate` sits
    inside an oracle branch -- verified by reading them all. The candidate path
    reads history only, so a row with no realised outcomes simulates correctly.
    The outcome fields are set to zero here and are never read.

    CHRONOLOGY IS NOT REIMPLEMENTED. The prospective rows are appended to the
    historical frame at their own ordinal and `attach` is re-run over the whole
    sorted list, so each one inherits exactly the frozen strictly-earlier
    prefix cut rather than a second copy of that logic.
    """
    import qb2_lib as Q
    allrows = Q.load()
    ordinal = season * 100 + week
    if any(r['ord'] >= ordinal for r in allrows):
        return Outcome.fail(
            'QB_HISTORY_NOT_STRICTLY_EARLIER',
            f'the historical frame already contains rows at or after ordinal '
            f'{ordinal}; forecasting a week the frame has already seen would '
            f'let the outcome inform its own prediction.')
    want = {p['gsis_id']: p for p in qb_players if p.get('gsis_id')}
    if not want:
        return Outcome.blocked(
            'QB_SLATE_EMPTY',
            f'no identified quarterback on the {season} week {week} roster for '
            f'this game', cause=Cause.DATA, season=season, week=week)
    fields = ('db', 'team_db', 'att', 'sacks', 'scr', 'spikes', 'cmp', 'pyds',
              'ptd', 'int', 'drush', 'ryds', 'rtd', 'rush_opp')
    pros = []
    for gid, p in want.items():
        pros.append({'season': season, 'week': week, 'team': p['team'],
                     'gsis_id': gid, 'position': 'QB', 'ord': ordinal,
                     'game_id': p.get('game_id', f'{season}_{week:02d}_SLATE'),
                     **{f: 0 for f in fields}})
    Q.attach(sorted(allrows + pros,
                    key=lambda r: (r['ord'], r['team'], r['gsis_id'])))
    # A quarterback with no prior appearance falls back to the positional pool
    # rather than to a guessed depth position; he is named, not dropped.
    #
    # OWN-3 CANDIDATE C0, DEFAULT OFF. `include_cold_start` keeps the
    # zero-history rows instead of naming and discarding them. It is safe to do
    # so because this layer's own machinery already handles them --
    # `rung_weight` returns 0 at h_games == 0, `rung_rate` returns the pool
    # value on an empty h_seq, and `_mix` returns a pure pool resample on an
    # empty own-history array -- so a kept row is forecast entirely from the
    # positional pool with no new parameter anywhere.
    #
    # Excluding them is what made 5.3168% of allocated team dropbacks reach
    # nobody on the 2026 week-1 slate (OWN-1). Keeping them is pre-registered
    # under nfl/research/own3/predeclaration_own3.md and is NOT promoted: the
    # production default is unchanged and the flag is off.
    cold = [r for r in pros if r['h_games'] < 1]
    rows = [r for r in pros if r['h_games'] >= 1]
    no_hist = [r['gsis_id'] for r in cold]
    if include_cold_start:
        for r in cold:
            r['cold_start'] = True
        rows = sorted(rows + cold, key=lambda r: (r['team'], r['gsis_id']))
    if not rows:
        return Outcome.blocked(
            'QB_SLATE_EMPTY',
            f'{len(pros)} rostered quarterback(s) but none has a prior '
            f'appearance, so none can be forecast from history',
            cause=Cause.DATA, no_history=no_hist)
    return Outcome.ok('QB_SLATE_PROSPECTIVE', value=(rows, allrows),
                      detail=f'{len(rows)} rostered QB row(s); '
                             f'{len(no_hist)} without prior history, '
                             f'{"KEPT on the pool path" if include_cold_start else "excluded"}',
                      n_rows=len(rows), n_no_history=len(no_hist),
                      no_history=no_hist,
                      cold_start_included=bool(include_cold_start),
                      n_cold_start_rows=len(cold) if include_cold_start else 0,
                      cold_start_spec=('own3-c0-pool-path-passthrough'
                                       if include_cold_start else None))


def forecast(rows, season, allrows, seed=20260908, m=1000,
             db_external=None) -> Outcome:
    """Run the V1 layer. Returns draw matrices keyed by statistic.

    `db_external` is R2: an (n_rows, m) integer dropback level owned by
    D1 x QB3 and apportioned by largest remainder. When supplied this layer
    draws no level of its own and contributes conditional rates only.
    """
    import time as _time
    import qb2_lib as Q
    if not rows:
        return Outcome.blocked(
            'STAGE_NOT_IMPLEMENTED',
            'no eligible QB rows were supplied; a named refusal is returned '
            'rather than a fabricated forecast', cause=Cause.DEPENDENCY)
    t0 = _time.perf_counter()
    try:
        D = Q.simulate(rows, season, allrows, seed=seed, m=m,
                       db_external=db_external)
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
