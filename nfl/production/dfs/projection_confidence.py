"""Projection confidence: not every mean is equally trustworthy.

WHY THIS EXISTS, AND IT IS A SPECIFIC NIGHT

On 2026-09-17 a 40-lineup DET @ BUF Showdown portfolio was generated from the
sealed board. The board's Buffalo non-QB role defect was ALREADY DIAGNOSED and
already written down: CS1 is quarterback-only, no Buffalo running back or
receiver carries current-season role state, and the P2 diagnostic had found an
appearance inversion on that exact roster.

The optimizer was handed those projections as plain numbers. It maximised mean
DK points. Measured on the delivered file:

    Ray Davis        72.5% of lineups, 15.0% at captain
    Frank Gore Jr.   55.0% of lineups
    James Cook        0.0% of lineups

So the portfolio's third-largest exposure was the player the model was most
wrong about, and the starter he backs up was absent entirely. The optimizer
did nothing incorrect. It was told the numbers were numbers.

THE FAILURE CLASS IS NOT A PROJECTION ERROR

It is KNOWN_MODEL_DEFECT_AMPLIFIED_BY_OPTIMIZER. A projection error is a
number being wrong. This is a number being wrong IN A WAY ALREADY WRITTEN DOWN
and then being consumed by a stage that had no way to read what was written.
Every ingredient of the failure was present in the repository before the
portfolio was built; nothing downstream could see any of it.

WHAT A TAG IS AND IS NOT

A tag is a statement about the MODEL'S STATE for that quantity, not about the
player's talent, not about his likely score, and not about whether to roster
him. `ROLE_STATE_CONCERN` does not mean "Ray Davis will disappoint". It means
"this projection is produced by a layer we have already shown is not carrying
current-season role information". Those are different claims and only the
second one is ours to make.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'nfl-projection-confidence-1'

#: The vocabulary. Ordered from most to least trustworthy.
MODEL_SUPPORTED = 'MODEL_SUPPORTED'
ROLE_STATE_CONCERN = 'ROLE_STATE_CONCERN'
DATA_STATE_CONCERN = 'DATA_STATE_CONCERN'
KNOWN_INACTIVE_STALE = 'KNOWN_INACTIVE_STALE'
IDENTITY_UNRESOLVED = 'IDENTITY_UNRESOLVED'
UNSUPPORTED = 'UNSUPPORTED'

TAGS = (MODEL_SUPPORTED, ROLE_STATE_CONCERN, DATA_STATE_CONCERN,
        KNOWN_INACTIVE_STALE, IDENTITY_UNRESOLVED, UNSUPPORTED)

#: What each tag does to a portfolio. `max_exposure` is a share of lineups;
#: None means unconstrained. `blocked` removes the player outright.
#:
#: The caps are DECLARED, not fitted. There is no dataset here that could fit
#: them, and a cap invented from one night's result would be the same mistake
#: in a new place. They are deliberately round numbers chosen to bound the
#: damage a known-defective projection can do, and they are meant to be
#: replaced by evidence, not tuned by feel.
POLICY = {
    MODEL_SUPPORTED: {
        'blocked': False, 'max_exposure': None, 'max_captain_exposure': None,
        'objective_multiplier': 1.0,
        'meaning': 'the layers producing this quantity carry current state and '
                   'have no open defect recorded against them.'},
    ROLE_STATE_CONCERN: {
        'blocked': False, 'max_exposure': 0.35, 'max_captain_exposure': 0.10,
        'objective_multiplier': 1.0,
        'meaning': 'a layer this projection depends on is known not to carry '
                   'current-season role state. The projection is USABLE and it '
                   'is not TRUSTWORTHY ENOUGH TO CONCENTRATE ON.',
        'why_not_blocked': 'blocking would throw away the starter as well as '
                           'the backup -- the defect is in the SPLIT between '
                           'them, not in the existence of the touches. A cap '
                           'bounds the damage without pretending the player '
                           'does not exist.',
        'why_the_captain_cap_is_tighter': 'a captain is 1.5x the points and '
                                          '1.5x the salary, so it is the '
                                          'single largest bet a lineup makes. '
                                          'The least trustworthy projections '
                                          'should be the least likely to carry '
                                          'it.'},
    DATA_STATE_CONCERN: {
        'blocked': False, 'max_exposure': 0.25, 'max_captain_exposure': 0.05,
        'objective_multiplier': 1.0,
        'meaning': 'an input feed this projection depends on is stale, absent, '
                   'or did not join.'},
    KNOWN_INACTIVE_STALE: {
        'blocked': True, 'max_exposure': 0.0, 'max_captain_exposure': 0.0,
        'objective_multiplier': 0.0,
        'meaning': 'official evidence says the player is out and the board '
                   'still carries opportunity for him. There is no version of '
                   'this that belongs in a lineup.'},
    IDENTITY_UNRESOLVED: {
        'blocked': True, 'max_exposure': 0.0, 'max_captain_exposure': 0.0,
        'objective_multiplier': 0.0,
        'meaning': 'the projection cannot be tied to the site`s player id. '
                   'Rostering a player you cannot name is not a bet, it is a '
                   'guess about a join.'},
    UNSUPPORTED: {
        'blocked': True, 'max_exposure': 0.0, 'max_captain_exposure': 0.0,
        'objective_multiplier': 0.0,
        'meaning': 'the model does not produce this quantity at all.'},
}

#: THE OVERRIDE. A cap may be exceeded only by an explicit, named,
#: evidence-carrying override -- never by an optimizer deciding the number
#: looked good. An override with no evidence string is refused.
OVERRIDE_REQUIRED_ABOVE_CAP = True


def policy(tag: str) -> Outcome:
    p = POLICY.get(tag)
    if p is None:
        return Outcome.fail(
            'UNKNOWN_CONFIDENCE_TAG',
            f'{tag!r} is not a declared confidence tag. An untagged '
            f'projection is not thereby trustworthy -- it is untagged, and '
            f'nothing downstream can reason about it.',
            cause=Cause.GOVERNANCE, known=list(TAGS))
    return Outcome.ok('CONFIDENCE_POLICY', value=dict(p),
                      detail=f'{tag}: blocked={p["blocked"]} '
                             f'max_exposure={p["max_exposure"]}',
                      tag=tag, **p)


def assert_every_player_tagged(player_ids, tags: dict) -> Outcome:
    """An untagged player is a refusal, not a default of MODEL_SUPPORTED.

    Defaulting to trusted is how the 2026-09-17 portfolio happened: every
    projection arrived carrying no statement about itself, and the absence of
    a warning was read as the absence of a problem.
    """
    missing = sorted(p for p in player_ids if p not in tags)
    bad = sorted(p for p, t in tags.items() if t not in TAGS)
    ev = {'spec_version': SPEC_VERSION, 'n_players': len(list(player_ids)),
          'untagged': missing, 'invalid_tag': bad}
    if missing or bad:
        return Outcome.fail(
            'PROJECTION_UNTAGGED',
            f'{len(missing)} untagged player(s) and {len(bad)} invalid tag(s). '
            f'Absence of a warning is not a statement of confidence.',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok('PROJECTIONS_TAGGED', value=dict(tags),
                      detail=f'{len(tags)} player(s) tagged', **ev)
