"""A1's test: does football support the certainty the estimator asserts?

THE COHORT IS THE ASSUMPTION, MADE INTO A GROUP OF PEOPLE

CS2's estimator returns exactly 1.0 for a player whose prior-season
appearance rate is 1.0 and who has taken opportunity in every week so far.
So: find every such player-week in history and ask how often the next week
actually happened.

  cohort member   a non-QB with prior-season appearance rate == 1.0 who has
                  taken a carry or a target in every week 1..W-1 of the
                  current season, whose club plays in week W.
  outcome         did he take a carry or a target in week W.

If the assumption is right the rate is 1.0 and no member ever fails. The
falsifier was written before this ran: an upper Wilson bound below 1.0, or a
single observed failure.

WHAT IS AND IS NOT CONTROLLED

An appearance proxy, not a snap count: a man who played and was neither handed
the ball nor thrown to counts as absent here, exactly as in CS2, and that
makes the measured rate a LOWER bound on true participation. It is the right
quantity anyway, because it is the quantity CS2 predicts.

Clubs on bye are excluded by construction -- a club with no week-W plays
contributes no member. Retirement and mid-season injury are NOT excluded, and
must not be: they are precisely the events certainty denies.

NO CLIPPING VALUE IS PRODUCED. The output is a rate and an interval. What
floor, if any, should follow is a separate preregistered decision.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.production.nonqb import current_season_nonqb_panel as P       # noqa: E402

SPEC_VERSION = 'a1-cohort-appearance-certainty-1'
SEASONS = (2022, 2023, 2024, 2025)
FIRST_WEEK, LAST_WEEK = 2, 18


def wilson(k, n, z=1.96):
    """Wilson interval. Chosen because at k == n a normal interval is [1, 1],
    which would make a perfect run look like proof."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def _appeared(d):
    return (d.get('carries', 0.0) + d.get('targets', 0.0)) > 0


def measure(seasons=SEASONS, verbose=True) -> Outcome:
    hits, trials = 0, 0
    failures, per_season = [], {}
    for season in seasons:
        cur = P.usage_season(season)
        prev = P.usage_season(season - 1)
        if cur.state is not State.PASS or prev.state is not State.PASS:
            continue
        # prior-season appearance rate, per (club, player), over CLUB weeks
        club_weeks = collections.defaultdict(set)
        appeared_prev = collections.defaultdict(set)
        for (wk, club, pid), d in prev.value.items():
            club_weeks[club].add(wk)
            if _appeared(d):
                appeared_prev[(club, pid)].add(wk)
        perfect = {k for k, wks in appeared_prev.items()
                   if club_weeks[k[0]] and len(wks) == len(club_weeks[k[0]])}
        # current season, by week
        by_week = collections.defaultdict(dict)
        for (wk, club, pid), d in cur.value.items():
            by_week[wk][(club, pid)] = d
        played = {wk: {k[0] for k in v} for wk, v in by_week.items()}
        s_hits = s_trials = 0
        for W in range(FIRST_WEEK, LAST_WEEK + 1):
            if W not in by_week:
                continue
            for key in perfect:
                club, _pid = key
                if club not in played[W]:
                    continue                       # bye, or club not in blob
                earlier = [w for w in range(1, W) if w in by_week]
                if not earlier:
                    continue
                # must have appeared in EVERY earlier week his club played
                club_earlier = [w for w in earlier if club in played[w]]
                if not club_earlier:
                    continue
                if not all(_appeared(by_week[w].get(key, {}))
                           for w in club_earlier):
                    continue
                s_trials += 1
                if _appeared(by_week[W].get(key, {})):
                    s_hits += 1
                else:
                    failures.append({'season': season, 'week': W,
                                     'team': club, 'player_id': key[1],
                                     'weeks_before': len(club_earlier)})
        per_season[season] = {'n': s_trials, 'appeared': s_hits,
                              'rate': (s_hits / s_trials) if s_trials else None,
                              'ci95': wilson(s_hits, s_trials)}
        hits += s_hits
        trials += s_trials
        if verbose:
            print(f'  {season}: {s_hits}/{s_trials}', flush=True)

    if trials < 30:
        return Outcome.blocked(
            'A1_COHORT_TOO_SMALL',
            f'{trials} cohort week(s); too few to say anything',
            cause=Cause.DATA, n=trials)
    rate = hits / trials
    ci = wilson(hits, trials)
    # THE FALSIFIER, APPLIED AS WRITTEN. Either limb alone falsifies.
    upper_below_one = ci is not None and ci[1] < 1.0
    any_failure = (trials - hits) > 0
    falsified = bool(upper_below_one or any_failure)
    by_club = collections.Counter((f['season'], f['team']) for f in failures)
    return Outcome.ok(
        'A1_COHORT_MEASURED',
        value={'rate': rate, 'ci95': ci, 'n': trials, 'appeared': hits,
               'failures': trials - hits, 'per_season': per_season,
               'failure_examples': failures[:25]},
        detail=f'{hits}/{trials} = {rate:.6f}, 95% Wilson '
               f'[{ci[0]:.6f}, {ci[1]:.6f}]; {trials - hits} failure(s)',
        spec_version=SPEC_VERSION, seasons=list(seasons),
        n_cohort_weeks=trials, n_appeared=hits, n_failed=trials - hits,
        rate=rate, ci95=ci,
        falsifier_limb_upper_bound_below_one=bool(upper_below_one),
        falsifier_limb_any_observed_failure=bool(any_failure),
        falsifies_a1=falsified,
        n_distinct_clubs_with_a_failure=len(by_club),
        appearance_is_a_proxy=(
            'a man who played and was neither handed the ball nor thrown to '
            'counts as absent, exactly as in CS2, so this rate is a LOWER '
            'bound on true participation -- and it is the quantity CS2 '
            'predicts, which is what matters here'),
        no_clipping_value_is_produced=(
            'the output is a rate and an interval. What floor should follow, '
            'if any, is a separate preregistered decision.'),
        uses_live_game_outcome_data=False)
