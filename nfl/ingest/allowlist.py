"""Column quarantine at ingest. G0A item 6.

WHY

Three separate classes of column in the reachable NFL data would each, on their
own, silently invalidate a historical forecasting experiment:

  MARKET      the sportsbook, shipped inside the "neutral" feed. CLAUDE.md rule 1
              forbids optimising toward the book; a feature that IS the book is
              the limiting case. Measured: already populated for 112 of the 272
              unplayed 2026 games in `schedules`, and re-stamped by `pbp` onto
              all 49,492 rows, so quarantining one file is insufficient.
  OUTCOME     the realised result, replicated onto every play row.
  POSTHOC     facts only knowable after kickoff, wearing the shape of a weekly
              or pre-game field. `weekly_rosters.status` is the dangerous one --
              measured ACT -> 0.9715 snap rate, INA -> 0 of 3,438. A near-perfect
              predictor of playing, available only afterwards.
  MODEL_DERIVED  nflfastR-fitted columns whose historical information set is not
              established. External review found pooled multi-season fitting and
              retroactive application, not row-wise point-in-time fitting.

THE PURPOSE DISTINCTION, WHICH IS THE POINT OF THIS MODULE

A column that must never reach a forecast may still be legitimate to archive, and
may be legitimate to READ descriptively. Owner Directive 3 §7: "archival raw
material may remain separately quarantined". So the quarantine is not a delete --
it is a boundary that a caller crosses only by declaring why.

  Purpose.ARCHIVE     store the bytes. Everything allowed; nothing is dropped.
  Purpose.DESCRIPTIVE human reads it; never enters a projection.
  Purpose.FORECAST    a predictive artifact. The quarantine bites here.

Column names below were read from the real headers on 2026-09-06, not recalled.
"""
from __future__ import annotations

import enum
import sys
import pathlib
from typing import Iterable, Mapping

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402


class Purpose(str, enum.Enum):
    ARCHIVE = 'ARCHIVE'
    DESCRIPTIVE = 'DESCRIPTIVE'
    FORECAST = 'FORECAST'


class Category(str, enum.Enum):
    MARKET = 'MARKET'
    OUTCOME = 'OUTCOME'
    POSTHOC = 'POSTHOC'
    MODEL_DERIVED = 'MODEL_DERIVED'


_CODE = {
    Category.MARKET: 'MARKET_COLUMN_ACCESS',
    Category.OUTCOME: 'OUTCOME_COLUMN_ACCESS',
    Category.POSTHOC: 'POSTHOC_COLUMN_ACCESS',
    Category.MODEL_DERIVED: 'MODEL_DERIVED_COLUMN_ACCESS',
}

# --- pbp -------------------------------------------------------------------
_PBP_MARKET = ('spread_line', 'total_line', 'vegas_wp', 'vegas_wpa',
               'vegas_home_wp', 'vegas_home_wpa')
_PBP_OUTCOME = ('result', 'total', 'home_score', 'away_score')
# Fitted columns present in the 2024 header, enumerated rather than
# pattern-matched at runtime, so adding a column upstream cannot silently widen
# what is permitted. NO COUNT IS WRITTEN IN THIS COMMENT: an earlier version said
# "all 45" over a tuple of 41 while W1_DATA_PROVENANCE said 31 -- three copies,
# three numbers, nothing comparing them, which is Failure Taxonomy Class C
# exactly. The count is derived below and asserted at import.
_PBP_MODEL = (
    'no_score_prob', 'opp_fg_prob', 'opp_safety_prob', 'opp_td_prob', 'fg_prob',
    'safety_prob', 'td_prob', 'extra_point_prob', 'two_point_conversion_prob',
    'ep', 'epa', 'wp', 'def_wp', 'home_wp', 'away_wp', 'wpa',
    'total_home_rush_wpa', 'total_away_rush_wpa', 'total_home_pass_wpa',
    'total_away_pass_wpa', 'air_wpa', 'yac_wpa', 'comp_air_wpa', 'comp_yac_wpa',
    'total_home_comp_air_wpa', 'total_away_comp_air_wpa',
    'total_home_comp_yac_wpa', 'total_away_comp_yac_wpa',
    'total_home_raw_air_wpa', 'total_away_raw_air_wpa',
    'total_home_raw_yac_wpa', 'total_away_raw_yac_wpa',
    'cp', 'cpoe', 'xyac_epa', 'xyac_mean_yardage', 'xyac_median_yardage',
    'xyac_success', 'xyac_fd', 'xpass', 'pass_oe',
    # Added after adversarial testing cross-checked the tuple against
    # W1_DATA_PROVENANCE.md sections 5.2/5.3. qb_epa is the costly omission:
    # availability 1.0000 on dropbacks, and precisely what a QB model reaches for.
    'air_epa', 'yac_epa', 'comp_air_epa', 'comp_yac_epa', 'success', 'qb_epa',
)

# --- schedules -------------------------------------------------------------
_SCH_MARKET = ('away_moneyline', 'home_moneyline', 'spread_line',
               'away_spread_odds', 'home_spread_odds', 'total_line',
               'under_odds', 'over_odds')
_SCH_OUTCOME = ('away_score', 'home_score', 'result', 'total', 'overtime')
# Measured: 285/285 populated for 2024, 0/272 for 2026. The zeros are the tell --
# it is filled in after the fact.
_SCH_POSTHOC = (
    'away_qb_id', 'home_qb_id', 'away_qb_name', 'home_qb_name',
    # All 0/272 on unplayed 2026 games -- populated only after the fact.
    # temp and wind are OBSERVED game-time conditions, not forecasts, so a totals
    # model taking them from the archive is reading the weather it is predicting
    # under. A forecast vintage is a different field and would be registered
    # separately.
    'referee', 'temp', 'wind', 'gsis', 'nfl_detail_id', 'pff', 'ftn',
)

QUARANTINE: Mapping[str, Mapping[str, Category]] = {
    'pbp': {**{c: Category.MARKET for c in _PBP_MARKET},
            **{c: Category.OUTCOME for c in _PBP_OUTCOME},
            **{c: Category.MODEL_DERIVED for c in _PBP_MODEL}},
    'schedules': {**{c: Category.MARKET for c in _SCH_MARKET},
                  **{c: Category.OUTCOME for c in _SCH_OUTCOME},
                  **{c: Category.POSTHOC for c in _SCH_POSTHOC}},
    'weekly_rosters': {'status': Category.POSTHOC},
    'injuries': {},
    'depth_charts': {},
    # Declared with empty maps: nothing in them is currently known to leak, and
    # a source with no entry at all is refused rather than assumed clean.
    'pbp_participation': {},
    'ftn_charting': {},
    'snap_counts': {},
    'players': {},
}

REASONS = {
    Category.MARKET:
        'the sportsbook, shipped inside the data feed. CLAUDE.md rule 1.',
    Category.OUTCOME:
        'the realised result of the game being forecast.',
    Category.POSTHOC:
        'only knowable after kickoff, in a field shaped like a pre-game one.',
    Category.MODEL_DERIVED:
        'fitted upstream with an unestablished information set; quarantined '
        'until proven point-in-time safe or reconstructed (Directive 3 §5).',
}


# One declaration, everything else reads it (Class C prevention).
N_QUARANTINED_MODEL_DERIVED = len(_PBP_MODEL)
assert len(set(_PBP_MODEL)) == len(_PBP_MODEL), \
    'duplicate entry in _PBP_MODEL; the quarantine declaration is inconsistent'


def quarantined_columns(source: str) -> Mapping[str, Category]:
    return dict(QUARANTINE.get(source, {}))


def assert_columns_allowed(source: str, columns: Iterable[str],
                           purpose: Purpose) -> Outcome:
    """The gate. Returns an Outcome; never a bare bool.

    ARCHIVE and DESCRIPTIVE pass everything -- the bytes are allowed to exist and
    a human is allowed to look at them. FORECAST is where the boundary bites.
    """
    cols = list(columns)
    if not cols:
        # Rule 001 / Class A: an empty column set is not a compliant read.
        return Outcome.fail(
            'EMPTY_COLUMN_SET',
            f'{source}: no columns named. An empty request is not a permitted '
            f'read; it is a missing one.', source=source)

    if source not in QUARANTINE:
        return Outcome.blocked(
            'SOURCE_NOT_REGISTERED',
            f'{source!r} has no quarantine declaration. A source with no '
            f'declaration is not thereby clean -- it is undeclared. Add it to '
            f'QUARANTINE, even if the mapping is empty.',
            cause=Cause.GOVERNANCE, source=source)

    if purpose is not Purpose.FORECAST:
        return Outcome.ok('COLUMNS_ALLOWED', value=cols,
                          detail=f'{source}: {len(cols)} columns for '
                                 f'{purpose.value}; quarantine does not apply.',
                          source=source, purpose=purpose.value)

    q = QUARANTINE[source]
    hits = [(c, q[c]) for c in cols if c in q]
    if hits:
        by_cat: dict[Category, list[str]] = {}
        for c, cat in hits:
            by_cat.setdefault(cat, []).append(c)
        # Deterministic: report the most serious category, ordered as declared.
        for cat in (Category.MARKET, Category.OUTCOME, Category.POSTHOC,
                    Category.MODEL_DERIVED):
            if cat in by_cat:
                bad = sorted(by_cat[cat])
                return Outcome.fail(
                    _CODE[cat],
                    f'{source}: forecast use of {bad} refused -- '
                    f'{REASONS[cat]}',
                    source=source, columns=bad, category=cat.value,
                    all_violations={k.value: sorted(v)
                                    for k, v in by_cat.items()})

    return Outcome.ok('COLUMNS_ALLOWED', value=cols,
                      detail=f'{source}: {len(cols)} columns cleared for '
                             f'FORECAST use.',
                      source=source, purpose=purpose.value)


def forecast_safe_columns(source: str, columns: Iterable[str]) -> list[str]:
    """The columns of `columns` a forecast may consume. For building an
    allowlist, never for silently filtering a caller's request -- filtering a
    request is how a quarantine becomes invisible.

    RAISES on an unregistered source. It previously used `QUARANTINE.get(source,
    {})`, which returned every column -- `spread_line` included -- as
    forecast-safe for any name not in the map, silently contradicting
    `assert_columns_allowed`, which BLOCKS the same case. Two functions
    disagreeing about the same rule is Class C, and the permissive one is the
    one callers reach for.
    """
    if source not in QUARANTINE:
        raise KeyError(
            f'{source!r} has no quarantine declaration, so no column of it can '
            f'be certified forecast-safe. An undeclared source is not clean; it '
            f'is undeclared. Add it to QUARANTINE, even if the mapping is empty.')
    q = QUARANTINE[source]
    return [c for c in columns if c not in q]
