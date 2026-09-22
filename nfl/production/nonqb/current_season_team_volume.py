"""Current-season TEAM volume, measured from the same lawful capture as usage.

WHY THIS EXISTS

`denom_panel` supplies the team denominators -- carries, targets, dropbacks --
and its newest ordinal is 202518. `freshness.REGISTRY` blocks it by declaration
with `CURRENT_SEASON_SOURCE_UNVERIFIED`, and the registry's own note says why
the block is not blunt: of five team-volume metrics, four are history-only by
construction and ONE is genuinely degraded -- `team_targets`, an EWMA whose
most recent observation is 2025 week 18 for every club.

The declared block was correct when it was written, because the reason given
was that the 2026 source's "vintage, completeness, coverage, field definitions
and identity behaviour are not established". This module establishes them:

    vintage      the governed store, selected by clock <= information cut,
                 exactly as `usage_vintage` selects it
    completeness measured and returned -- games and clubs present, against the
                 schedule's own count for those weeks
    coverage     per (week, club), and a club absent from the capture is a
                 NAMED state, never a zero
    definitions  the SAME counting rules as the player panel, imported rather
                 than restated, so a share and its denominator cannot drift
    identity     none. Team volume is counted on `posteam`; no player
                 identity is involved, which is why this input is tractable
                 now while the player-level denominator was not

WHAT IT DOES NOT DO

It does not lift the declared block by itself. It measures, and it reports
completeness. Whether that is enough to publish is a governance decision, made
by `assert_publishable` below against a stated completeness requirement, not by
this module deciding it looks fine.

A PARTIAL DENOMINATOR IS WORSE THAN A MISSING ONE, and that is the whole
reason for the original block: a share computed over a denominator that is
missing three clubs is confidently wrong rather than nameably absent. So
completeness is not a footnote here; it is the gate.
"""
from __future__ import annotations

import collections
import csv
import gzip
import pathlib
import sys
from typing import Any, Dict, List, Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import usage_vintage as UV             # noqa: E402
from nfl.production.nonqb import current_season_nonqb_panel as CSP  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome        # noqa: E402

SPEC_VERSION = 'current-season-team-volume-1'

#: The counting rules, imported by reference from the player panel so a share
#: and its denominator are counted the same way. Restating them here would let
#: them drift, which is how a numerator and denominator come to disagree.
COUNTING_IMPORTED_FROM = 'current_season_nonqb_panel.COUNTING_RULES'

METRICS = ('team_carries', 'team_targets', 'team_dropbacks',
           'team_rz_carries', 'team_plays')

#: All 32 clubs must be present for a week to be publishable. Not a tuning
#: parameter: a league-wide share denominator missing a club is wrong for every
#: player at that club and silently wrong for everyone else's rank.
REQUIRED_CLUBS = 32

CLUB_ABSENT = 'CLUB_ABSENT_FROM_CAPTURE'


def _one(v) -> bool:
    return str(v).strip() in ('1', '1.0', 'True', 'true')


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def collect(season: int, week: int, as_of: str) -> Outcome:
    """Per (week, club) team volume from weeks strictly before `week`.

    Same selector, same clock discipline and same counting as the player
    usage panel. Returns completeness alongside the numbers, because the
    numbers alone cannot say whether they may be used.
    """
    co = UV.candidates(season, as_of)
    if co.state.name != 'PASS':
        return co
    pick = co.value[0]

    per: Dict[Any, Dict[str, float]] = collections.defaultdict(
        lambda: {m: 0.0 for m in METRICS})
    weeks: collections.Counter = collections.Counter()
    games: set = set()

    with gzip.open(pick['path'], 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            club = (r.get('posteam') or '').strip()
            w = r.get('week')
            if not club or w is None:
                continue
            try:
                wi = int(float(w))
            except (TypeError, ValueError):
                continue
            if wi >= int(week):
                continue
            if _one(r.get('two_point_attempt')):
                continue
            d = per[(wi, club)]
            weeks[wi] += 1
            if r.get('game_id'):
                games.add(r['game_id'])
            d['team_plays'] += 1
            if _one(r.get('rush_attempt')):
                d['team_carries'] += 1
                if (_f(r.get('yardline_100'), 99) or 99) <= 20:
                    d['team_rz_carries'] += 1
            if _one(r.get('pass_attempt')):
                d['team_targets'] += 1
            if _one(r.get('qb_dropback')):
                d['team_dropbacks'] += 1

    if not per:
        return Outcome.fail(
            'TEAM_VOLUME_EMPTY',
            f'the lawful capture for {season} before week {week} produced no '
            f'team rows. An empty denominator read as zero volume would make '
            f'every share infinite or undefined.',
            value={'blob': pick['blob']})

    by_week: Dict[int, List[str]] = collections.defaultdict(list)
    for (wi, club) in per:
        by_week[wi].append(club)
    completeness = {
        str(wi): {'clubs_present': len(set(cs)),
                  'clubs_required': REQUIRED_CLUBS,
                  'complete': len(set(cs)) == REQUIRED_CLUBS,
                  'missing_count': REQUIRED_CLUBS - len(set(cs))}
        for wi, cs in sorted(by_week.items())}
    all_complete = all(v['complete'] for v in completeness.values())

    return Outcome.ok(
        'TEAM_VOLUME_MEASURED',
        {'by_week_club': {f'{wi}|{club}': dict(v)
                          for (wi, club), v in sorted(per.items())},
         'weeks_present': sorted(by_week),
         'max_week_used': max(by_week) if by_week else None,
         'n_games': len(games),
         'completeness': completeness,
         'all_weeks_complete': all_complete,
         'metrics': list(METRICS),
         'counting_imported_from': COUNTING_IMPORTED_FROM,
         'counting_rules': dict(CSP.COUNTING_RULES),
         'source': {'blob': pick['blob'], 'clock': pick['clock'],
                    'store': pick['store'], 'path': str(pick['path'])},
         'spec_version': SPEC_VERSION},
        detail=f'{len(per)} (week, club) row(s) over weeks '
               f'{sorted(by_week)} from {pick["blob"]}; '
               f'complete={all_complete}')


def assert_publishable(tv: Outcome, *, season: int, week: int) -> Outcome:
    """May these denominators be used for a published forecast?

    The governance decision the original `denom_panel` block was protecting.
    It is answered against a stated completeness requirement rather than by
    inspection.
    """
    if tv.state.name != 'PASS':
        return Outcome.blocked(
            'TEAM_VOLUME_UNAVAILABLE',
            f'current-season team volume is {tv.state.name}[{tv.code}], so no '
            f'share can be published against it.', cause=Cause.DATA)
    v = tv.value
    need = int(week) - 1
    if v['max_week_used'] != need:
        return Outcome.blocked(
            'TEAM_VOLUME_STALE',
            f'the newest team-volume week measured is {v["max_week_used"]} and '
            f'a week-{week} forecast needs week {need}. A denominator that '
            f'stops short of the forecast makes every share a share of the '
            f'wrong game.', cause=Cause.DATA,
            value={'max_week_used': v['max_week_used'], 'need': need})
    bad = {w: c for w, c in v['completeness'].items() if not c['complete']}
    if bad:
        return Outcome.blocked(
            'TEAM_VOLUME_INCOMPLETE',
            f'week(s) {sorted(bad)} are missing {sorted(c["missing_count"] for c in bad.values())} '
            f'club(s) of {REQUIRED_CLUBS}. A partial denominator is worse than '
            f'a missing one: it produces confidently wrong shares instead of a '
            f'nameable refusal, which is exactly what the denom_panel block '
            f'was protecting against.', cause=Cause.DATA,
            value={'incomplete_weeks': bad})
    return Outcome.ok(
        'TEAM_VOLUME_PUBLISHABLE',
        {'max_week_used': v['max_week_used'],
         'weeks_present': v['weeks_present'],
         'n_games': v['n_games'],
         'completeness': v['completeness'],
         'source': v['source'],
         'supersedes': 'denom_panel for the 2026 metrics measured here',
         'still_from_denom_panel': [
             'the historical training corpus for the coach-prior and '
             'league-mean estimators, which are history-only by construction '
             'and are NOT made stale by a new season'],
         'spec_version': SPEC_VERSION},
        detail=f'weeks {v["weeks_present"]}, {v["n_games"]} game(s), all 32 '
               f'clubs present in every week')
