#!/usr/bin/env python3.12
"""Era coverage: what each statistic can mean in each season, and what it cannot.

THE RULE THIS FILE EXISTS TO ENFORCE. A statistic that did not exist in a season is
NOT_AVAILABLE_FOR_ERA. It is never zero, never a league average, never quietly imputed. A model
trained on a zero-filled 2004 snap count would learn that nobody played in 2004.

TWO KINDS OF WINDOW, AND THEY ARE KEPT APART ON PURPOSE.

  CLAIMED   what a source says it covers, with the claim's provenance attached. A claim is not a
            measurement, and several claims here come from the owner's briefing rather than from
            anything this checkout can see.
  MEASURED  what THIS repository demonstrably holds, established by reading the files. Written by
            coverage.py, never by hand.

Code asks `available(stat, season)` and gets one of AVAILABLE / NOT_AVAILABLE_FOR_ERA /
UNKNOWN_PENDING_ACQUISITION. The third is not a soft yes. A feature whose availability is unknown
must be treated as unavailable by any model, and the state exists so the difference between "this
did not exist" and "we have not acquired it" survives into the artifacts.
"""
from __future__ import annotations

#: The sentinel. Any consumer that sees this must propagate it, not coerce it.
NOT_AVAILABLE_FOR_ERA = 'NOT_AVAILABLE_FOR_ERA'
UNKNOWN_PENDING_ACQUISITION = 'UNKNOWN_PENDING_ACQUISITION'
AVAILABLE = 'AVAILABLE'

#: The warehouse's declared span. 2000 is the owner's floor; earlier seasons are not excluded from
#: the data that happens to reach back further, they are simply outside the warehouse's contract.
FIRST_SEASON = 2000
#: Set by the caller for a live build; kept explicit so a stale constant cannot silently bound a
#: coverage report.
CURRENT_SEASON = 2026

#: Provenance tags for a claimed window.
PFR = 'PRO_FOOTBALL_REFERENCE_COVERAGE_STATEMENT_VIA_OWNER_BRIEFING_2026-09-28'
NFLVERSE = 'NFLVERSE_PBP_SCHEMA'
REPO = 'MEASURED_IN_THIS_CHECKOUT'
UNVERIFIED = 'UNVERIFIED_NO_SOURCE_IN_CHECKOUT'

#: statistic -> (first_season_claimed, last_season_or_None, provenance, note)
#:
#: A first_season of None means the claim is that it does not exist at any season we can reach.
CLAIMED_WINDOWS = {
    # ---- market and environment. The repository's own schedules file settles these.
    'spread': (1952, None, PFR, 'PFR states spreads back to 1952; this checkout holds 1999+'),
    'total_line': (1952, None, PFR, 'as spread'),
    # CORRECTED 2026-09-28. The first version claimed 1999 on the strength of the column existing
    # in the capture, without measuring it per season. Measured: zero coverage 1999-2005, 0.82 in
    # 2006, and effectively complete from 2007 with dips to 0.73 in 2008 and 0.95 in 2009. A column
    # that exists is not a column that is populated, and the coverage ledger caught the difference.
    'moneyline': (2006, None, REPO,
                  'MEASURED per season in nfl/vintage/schedules: none before 2006, 0.82 in 2006, '
                  'complete from 2007 with dips in 2008 (0.73) and 2009 (0.95)'),
    'weather_temp': (1960, None, PFR,
                     'PFR states weather back to 1960. Null for domes, where roof carries the '
                     'information instead -- a null here is NOT a missing measurement.'),
    'weather_wind': (1960, None, PFR, 'as temp'),
    'roof': (1999, None, REPO, ''),
    'surface': (1999, None, REPO, ''),
    'rest_days': (1999, None, REPO, ''),
    'overtime': (1999, None, REPO, ''),
    'final_score': (1920, None, PFR, 'box scores reach far earlier than the warehouse floor'),

    # ---- box score player statistics
    'pass_attempts': (1932, None, PFR, 'player game stats reach much earlier than 2000'),
    'completions': (1932, None, PFR, ''),
    'passing_yards': (1932, None, PFR, ''),
    'passing_td': (1932, None, PFR, ''),
    'interceptions_thrown': (1932, None, PFR, ''),
    'rush_attempts': (1932, None, PFR, ''),
    'rushing_yards': (1932, None, PFR, ''),
    'rushing_td': (1932, None, PFR, ''),
    'receptions': (1932, None, PFR, ''),
    'receiving_yards': (1932, None, PFR, ''),
    'receiving_td': (1932, None, PFR, ''),
    'sacks_taken': (1969, None, PFR, 'sacks became an official statistic in 1982; PFR carries '
                                     'earlier reconstructions. Treated as reliable from 1982.'),

    # ---- TARGETS. The single most important era boundary for a DFS receiving model.
    'targets': (1992, None, PFR,
                'targets are NOT a historical box-score universal. PFR carries them from the '
                'early 1990s. A receiving model that assumes targets exist in every season the '
                'warehouse spans is fine from 2000, which is why 2000 is a sound floor.'),

    # ---- play-by-play derived
    'play_by_play': (1977, None, PFR, 'PFR states PBP-derived data from 1977'),
    'red_zone_usage': (1977, None, PFR, 'derivable wherever play-by-play with yardline exists'),
    'goal_line_usage': (1977, None, PFR, 'as red zone'),
    'team_plays': (1977, None, PFR, ''),
    'team_drives': (1977, None, PFR, ''),
    'situation_neutral_pass_rate': (1977, None, PFR, 'needs score and clock on each play'),
    'game_script': (1977, None, PFR, ''),
    'pace': (1977, None, PFR, ''),
    'qb_scramble': (1999, None, NFLVERSE,
                    'nflverse marks scrambles; earlier PBP does not separate a designed run from '
                    'a scramble, so the DISTINCTION is unavailable even where runs are.'),

    # ---- the hard boundaries the owner called out
    'snap_counts': (2012, None, PFR,
                    'PFR snap-count coverage begins in 2012. A 2000-2011 role model must use '
                    'starts, participation, touches, targets, carries and play-by-play as '
                    'proxies. Fabricating a snap share before 2012 is forbidden.'),
    'air_yards': (2006, None, NFLVERSE,
                  'nflverse air yards from the mid-2000s. Verified present 2021-2026 in this '
                  'checkout; earlier seasons are a claim, not a measurement.'),
    'routes_run': (None, None, UNVERIFIED,
                   'route counts are a charted product (PFF/FTN/SIS). NOTHING in this checkout '
                   'carries them at any season. Never infer routes from pass snaps -- that is a '
                   'standing prohibition in this project, not a preference.'),
    'alignment_slot_wide': (None, None, UNVERIFIED,
                            'alignment is charted. Roster position is NOT alignment and must '
                            'never be used as a proxy for it.'),
    'pressure_time_to_throw': (2016, None, UNVERIFIED,
                               'NGS-derived; nothing in this checkout carries it.'),
    'separation_cushion': (2016, None, UNVERIFIED, 'NGS-derived; absent here.'),
    'ownership_dfs': (None, None, UNVERIFIED,
                      'archived contest ownership. Nothing in this checkout. Required for the '
                      'field model to be validated rather than asserted.'),
    'college_production': (None, None, UNVERIFIED, 'not in this checkout'),
    'draft_capital': (None, None, UNVERIFIED, 'not in this checkout'),
}

#: Statistics whose ABSENCE in an era must be handled by a named proxy rather than a zero, with the
#: proxy stated. This is the era-awareness the owner asked for, made explicit.
ERA_PROXIES = {
    'snap_counts': {
        'unavailable_before': 2012,
        'proxy': ('starter status, game participation, touches, targets, carries and '
                  'play-by-play participation'),
        'forbidden': 'any fabricated snap count or snap share',
        'note': ('a role model for 2000-2011 is built on opportunity rather than participation. '
                 'The two are not the same quantity and the warehouse does not pretend they are: '
                 'a snap-share column stays NOT_AVAILABLE_FOR_ERA and the role model reads the '
                 'proxy columns instead.'),
    },
    'qb_scramble': {
        'unavailable_before': 1999,
        'proxy': 'quarterback rush attempts, undifferentiated',
        'forbidden': 'splitting designed runs from scrambles before the distinction is recorded',
    },
    'air_yards': {
        'unavailable_before': 2006,
        'proxy': 'yards per target and catch rate',
        'forbidden': 'imputing a depth of target from yardage',
    },
}


def available(stat, season, measured=None):
    """AVAILABLE / NOT_AVAILABLE_FOR_ERA / UNKNOWN_PENDING_ACQUISITION for one statistic-season.

    `measured` is the coverage ledger's measured map when one exists; a measurement always
    outranks a claim, in both directions. A statistic a source claims to cover and this checkout
    demonstrably lacks is UNKNOWN_PENDING_ACQUISITION, not AVAILABLE.
    """
    if stat not in CLAIMED_WINDOWS:
        return UNKNOWN_PENDING_ACQUISITION
    first, last, prov, _note = CLAIMED_WINDOWS[stat]
    if first is None:
        return UNKNOWN_PENDING_ACQUISITION
    if season < first or (last is not None and season > last):
        return NOT_AVAILABLE_FOR_ERA
    if measured is not None:
        seen = (measured.get(stat) or {}).get(str(season))
        if seen is None:
            return UNKNOWN_PENDING_ACQUISITION
        return AVAILABLE if seen else NOT_AVAILABLE_FOR_ERA
    if prov in (UNVERIFIED,):
        return UNKNOWN_PENDING_ACQUISITION
    return AVAILABLE


def era_weight(season, forecast_season, halflife=4.0, floor=0.04):
    """Weight on a historical season for learning a CURRENT relationship.

    The owner's refinement, made operational: twenty-five years of history is for stable
    relationships, archetypes and rare-event behaviour, and recent seasons carry more weight for
    current efficiency and usage. So this is an exponential decay with a floor -- the floor is what
    keeps a 2001 season contributing to a rare-event prior instead of vanishing.

    DECLARED, not fitted, and deliberately separate from player_prior's own recency halflife: that
    one weights a PLAYER's observations, this one weights an ERA. A four-season halflife means 2018
    carries about a quarter the weight of 2026 for a current-efficiency question.
    """
    back = max(0, forecast_season - season)
    return max(floor, 0.5 ** (back / halflife))


def summary():
    return {
        'FIRST_SEASON': FIRST_SEASON,
        'NOT_AVAILABLE_FOR_ERA': NOT_AVAILABLE_FOR_ERA,
        'n_statistics_declared': len(CLAIMED_WINDOWS),
        'unverified_statistics': sorted(k for k, v in CLAIMED_WINDOWS.items()
                                        if v[2] == UNVERIFIED),
        'era_proxies': sorted(ERA_PROXIES),
        'RULE': ('a statistic that did not exist in a season is NOT_AVAILABLE_FOR_ERA. Never zero, '
                 'never a league average, never quietly imputed.'),
    }
