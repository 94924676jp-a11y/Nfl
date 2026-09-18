"""Single-game roster legality, per site, in config rather than in code.

DO NOT ASSUME DRAFTKINGS RULES APPLY TO FANDUEL. The two formats differ in
ways that change every lineup, and the one that matters most is the salary
treatment of the multiplier slot:

  * DraftKings Showdown multiplies the CAPTAIN'S SALARY by 1.5 as well as his
    points. A captain therefore costs real money and the cap binds hard -- on
    the DET @ BUF slate the naive best five under a captain fit the cap in only
    57.3% of worlds.
  * FanDuel Single Game is believed NOT to multiply the MVP's salary. If that
    is right, the MVP is a free 0.5x of points and the optimisation problem is
    a different shape, not a rescaled one.

Getting that backwards does not produce slightly wrong lineups; it produces
lineups that cannot be submitted, or leaves half the cap unspent.

PROVENANCE IS PER SITE AND IT IS NOT EQUAL.

DraftKings is VERIFIED against the DK entries file for this slate: roster shape
and cap were read out of the real upload template, and separate CPT/FLEX ids
with a 1.5x salary ratio are visible in it.

FanDuel is UNVERIFIED_FROM_RECOLLECTION. No FanDuel salary file exists in this
repository and the open web is refused at CONNECT. `assert_verified` therefore
refuses FanDuel, and the refusal names what would clear it: one FanDuel NFL
single-game salary export, which carries the roster shape, the cap and the MVP
salary treatment on its face.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'nfl-dfs-site-rules-1'

VERIFIED = 'VERIFIED_AGAINST_SITE_FILE'
UNVERIFIED = 'UNVERIFIED_FROM_RECOLLECTION'

SITES = {
    'DRAFTKINGS_SHOWDOWN': {
        'site': 'DRAFTKINGS',
        'format': 'Showdown Captain Mode',
        'roster_size': 6,
        'multiplier_slot': 'CPT',
        'n_multiplier_slots': 1,
        'n_flex_slots': 5,
        'points_multiplier': 1.5,
        'salary_is_multiplied': True,
        'salary_multiplier': 1.5,
        'salary_cap': 50000,
        'min_teams_represented': 2,
        'positional_eligibility': 'any position may fill any slot, including '
                                  'the captain slot; DST is a roster spot',
        'dst_is_rosterable': True,
        'separate_ids_per_slot': True,
        'provenance': VERIFIED,
        'evidence': 'nfl/research/dfs/DET_BUF_2026W2/frozen/'
                    'DKSalaries_showdown.csv -- every player appears twice, '
                    'once CPT and once FLEX, at a 1.5x salary ratio '
                    '(Gibbs 18000 / 12000), and the upload header is '
                    'CPT + 5 x FLEX',
    },
    'FANDUEL_SINGLE_GAME': {
        'site': 'FANDUEL',
        'format': 'Single Game (MVP)',
        'roster_size': 5,
        'multiplier_slot': 'MVP',
        'n_multiplier_slots': 1,
        'n_flex_slots': 4,
        'points_multiplier': 1.5,
        'salary_is_multiplied': False,
        'salary_multiplier': 1.0,
        'salary_cap': 60000,
        'min_teams_represented': 2,
        'positional_eligibility': 'believed any position; kickers are believed '
                                  'NOT offered on FanDuel single-game slates, '
                                  'which would remove two rosterable players '
                                  'relative to DraftKings',
        'dst_is_rosterable': False,
        'separate_ids_per_slot': False,
        'provenance': UNVERIFIED,
        'evidence': None,
        'what_would_verify_it': 'one FanDuel NFL single-game salary export. It '
                               'carries roster shape, cap, and whether the MVP '
                               'row has its own salary, on its face.',
        'highest_risk_if_wrong': ('salary_is_multiplied', 'salary_cap',
                                  'roster_size'),
    },
}


def get(site_key: str) -> Outcome:
    s = SITES.get(site_key)
    if s is None:
        return Outcome.fail(
            'UNKNOWN_SITE_FORMAT', f'{site_key!r} is not declared',
            cause=Cause.GOVERNANCE, known=sorted(SITES))
    return Outcome.ok('SITE_RULES', value=dict(s),
                      detail=f'{site_key}: {s["roster_size"]} slots, '
                             f'${s["salary_cap"]} cap, {s["provenance"]}',
                      site_key=site_key, **{k: v for k, v in s.items()
                                            if k != 'evidence'})


def assert_verified(site_key: str) -> Outcome:
    """Gate for anything that builds a real, submittable lineup."""
    r = get(site_key)
    if r.state is not State.PASS:
        return r
    s = r.value
    if s['provenance'] != VERIFIED:
        return Outcome.blocked(
            'SITE_RULES_UNVERIFIED',
            f'{site_key} rules are {s["provenance"]}. '
            f'{s.get("what_would_verify_it", "")} Until then no lineup built '
            f'against them may be submitted: the highest-risk fields are '
            f'{s.get("highest_risk_if_wrong")}, and getting '
            f'salary_is_multiplied backwards changes the shape of the '
            f'optimisation rather than rescaling it.',
            cause=Cause.NETWORK, site_key=site_key,
            provenance=s['provenance'],
            assigned_to='docs/AGENT_OUTBOX.md OUT-022')
    return Outcome.ok('SITE_RULES_VERIFIED', value=dict(s),
                      detail=f'{site_key} verified against {s["evidence"]}',
                      site_key=site_key)


def assert_lineup_legal(site_key: str, salaries, teams,
                        multiplier_index: int = 0) -> Outcome:
    """Roster shape, cap and team representation, per that site's own config."""
    r = get(site_key)
    if r.state is not State.PASS:
        return r
    s = r.value
    n = len(salaries)
    if n != s['roster_size']:
        return Outcome.fail(
            'LINEUP_WRONG_ROSTER_SIZE',
            f'{n} player(s) against {s["roster_size"]} for {site_key}',
            cause=Cause.GOVERNANCE, site_key=site_key)
    total = 0.0
    for i, sal in enumerate(salaries):
        total += (sal * s['salary_multiplier'] if i == multiplier_index
                  else sal)
    if total > s['salary_cap']:
        return Outcome.fail(
            'LINEUP_OVER_CAP',
            f'{total:.0f} over the {site_key} cap of {s["salary_cap"]}',
            cause=Cause.GOVERNANCE, salary=total, cap=s['salary_cap'])
    if len(set(teams)) < s['min_teams_represented']:
        return Outcome.fail(
            'LINEUP_TOO_FEW_TEAMS',
            f'{len(set(teams))} team(s) against a minimum of '
            f'{s["min_teams_represented"]}', cause=Cause.GOVERNANCE)
    return Outcome.ok('LINEUP_LEGAL', value={'salary': total},
                      detail=f'{site_key}: {n} players, {total:.0f} of '
                             f'{s["salary_cap"]}',
                      site_key=site_key, salary=total,
                      rules_provenance=s['provenance'])
