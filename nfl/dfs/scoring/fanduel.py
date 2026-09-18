"""FanDuel NFL scoring, as a mechanical adapter over the SAME StatLine.

NO SEPARATE PROJECTION MODEL EXISTS AND NONE MAY. FanDuel points here are the
same simulated football worlds read through different arithmetic. Nothing in
this file reaches back into the engine, and nothing in the engine knows this
file exists.

THE PROVENANCE PROBLEM, STATED BEFORE THE NUMBERS

DraftKings scoring in this repository is VERIFIED: the engine carries its own
implementation and the adapter reproduces it exactly. FanDuel has no such
anchor here. The coefficients below are RECALLED, and this environment cannot
reach fanduel.com to check them -- the open web is refused at CONNECT.

So they are marked `UNVERIFIED_FROM_RECOLLECTION` and the module REFUSES to
score a real board through the public entry point until a rules artifact is
supplied. Writing plausible numbers and letting a portfolio consume them is
exactly the failure this project keeps having; a scoring table that is wrong by
half a point per reception moves every receiver on the slate.

WHAT IS BELIEVED TO DIFFER FROM DRAFTKINGS, and each is load-bearing:

  * 0.5 points per reception, not 1.0. Half PPR moves pass-catchers a long way
    relative to runners.
  * NO yardage bonuses. DraftKings pays 3.0 at 300 passing / 100 rushing /
    100 receiving; FanDuel is believed to pay none, which compresses ceilings.
  * Fumble lost -2.0 rather than -1.0. Not simulated either way.

Everything else is believed identical: 0.04 per passing yard, 4 per passing
touchdown, -1 per interception, 0.1 per rushing or receiving yard, 6 per
rushing or receiving touchdown.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.scoring import statline as SL                           # noqa: E402

SPEC_VERSION = 'nfl-dfs-scoring-fanduel-1'
SITE = 'FANDUEL'

UNVERIFIED = 'UNVERIFIED_FROM_RECOLLECTION'
VERIFIED = 'VERIFIED_AGAINST_SOURCE'

#: Where a verified rules artifact would live. Until it exists, `score_board`
#: refuses.
RULES_ARTIFACT = _REPO / 'nfl/dfs/scoring/FANDUEL_RULES_VERIFIED.json'

RULES = {
    'pass_yard': 0.04, 'pass_td': 4.0, 'interception': -1.0,
    'rush_yard': 0.1, 'rush_td': 6.0,
    'rec_yard': 0.1, 'reception': 0.5, 'rec_td': 6.0,
    'fumble_lost': -2.0,          # NOT SIMULATED
    'two_point': 2.0,             # NOT SIMULATED
    'return_td': 6.0,             # NOT SIMULATED
    'fg_made_under_40': 3.0, 'fg_made_40s': 4.0, 'fg_made_50_plus': 5.0,
    'xp_made': 1.0,
}

#: No yardage bonuses, and the absence is DECLARED rather than implied by the
#: dictionary simply not having the key. A missing key reads as an oversight;
#: an explicit zero reads as a rule.
BONUSES = {'bonus_300_pass_yards': 0.0, 'bonus_100_rush_yards': 0.0,
           'bonus_100_rec_yards': 0.0}

RULE_PROVENANCE = {k: UNVERIFIED for k in list(RULES) + list(BONUSES)}

#: Per-rule confidence, so a later verification pass knows where to look first.
#: These are the three that differ from DraftKings and therefore the three that
#: change a lineup if they are wrong.
HIGHEST_RISK_IF_WRONG = ('reception', 'bonus_100_rec_yards',
                         'bonus_300_pass_yards')


def score(sl: SL.StatLine) -> np.ndarray:
    """Arithmetic only. No gate: unit tests need to exercise the formula."""
    return (RULES['pass_yard'] * sl.pass_yards
            + RULES['pass_td'] * sl.pass_td
            + RULES['interception'] * sl.interceptions
            + RULES['rush_yard'] * sl.rush_yards
            + RULES['rush_td'] * sl.rush_td
            + RULES['rec_yard'] * sl.rec_yards
            + RULES['reception'] * sl.receptions
            + RULES['rec_td'] * sl.rec_td)


def score_kicker(sl: SL.StatLine) -> np.ndarray:
    b = sl.fg_made_by_bucket
    if b:
        return (RULES['fg_made_under_40'] * (b.get('FG<20', 0)
                                             + b.get('FG20s', 0)
                                             + b.get('FG30s', 0))
                + RULES['fg_made_40s'] * b.get('FG40s', 0)
                + RULES['fg_made_50_plus'] * b.get('FG50+', 0)
                + RULES['xp_made'] * sl.xp_made)
    return RULES['fg_made_under_40'] * sl.fg_made + RULES['xp_made'] * sl.xp_made


def rules_state() -> Outcome:
    """Are the FanDuel rules verified? Today: no, and the refusal says so."""
    if RULES_ARTIFACT.exists():
        return Outcome.ok(
            'FANDUEL_RULES_VERIFIED', value=VERIFIED,
            detail=f'{RULES_ARTIFACT.name} present',
            spec_version=SPEC_VERSION)
    return Outcome.blocked(
        'FANDUEL_RULES_UNVERIFIED',
        f'the FanDuel scoring coefficients in this module are '
        f'{UNVERIFIED}. DraftKings is verified because the engine carries its '
        f'own implementation to reconcile against; FanDuel has no such anchor '
        f'here and this environment cannot reach fanduel.com. Half a point per '
        f'reception moves every pass-catcher on the slate, so the numbers are '
        f'not allowed to reach a portfolio until {RULES_ARTIFACT.name} exists.',
        cause=Cause.NETWORK, spec_version=SPEC_VERSION,
        highest_risk_if_wrong=list(HIGHEST_RISK_IF_WRONG),
        assigned_to='docs/AGENT_OUTBOX.md OUT-022',
        arithmetic_is_still_testable='score() has no gate; unit tests with '
                                     'hand-built stat lines exercise it')
