"""Every number somebody has to certify, in one place, with its certification.

WHY THIS FILE EXISTS

A threshold decides what passes. If it can be supplied at a call site, then
whoever is writing that call decides what passes, and the decision is made at
the moment it is least visible -- while trying to get a green board out before
a deadline. That is how a 25% unresolved-participation tolerance turned a
BLOCKED participation layer into a PASSING gate.

THE THREE STATES A NUMBER CAN BE IN, AND THEY ARE NOT INTERCHANGEABLE

    MEASURED                 what the data actually is. Not a threshold.
    CANDIDATE                a threshold someone proposed. It may be
                             reasonable. It has not been shown to be safe.
    PRODUCTION_CERTIFIED     a threshold with prospective empirical evidence
                             that operating at it does not produce the harm
                             it is meant to prevent.

ONLY PRODUCTION_CERTIFIED MAY CLEAR A GATE. A CANDIDATE threshold may be used
to compute and report -- that is how one earns certification -- but a gate
evaluated against it returns a non-passing state, and the verdict machine then
reads RESEARCH_ONLY. That is the correct answer: the system is not ready to
make the claim, because the standard it would be judged against has not been
shown to mean anything.

WHAT IS IN HERE TODAY, HONESTLY

Nothing is PRODUCTION_CERTIFIED. Every entry is CANDIDATE, because this
project has run two weeks of prospective football and has no evidence about
how much staleness or how much unreconstructed mass is survivable. Writing
CERTIFIED beside any of them today would be the fitted constant this project
forbids, wearing a governance word.

Certification is not a decision taken in this file. It requires the
prospective evidence named in each entry's `certification_requires`, and that
evidence does not exist yet.
"""
from __future__ import annotations

MEASURED = 'MEASURED'
CANDIDATE = 'CANDIDATE'
PRODUCTION_CERTIFIED = 'PRODUCTION_CERTIFIED'
CERTIFICATION_STATES = (MEASURED, CANDIDATE, PRODUCTION_CERTIFIED)

#: Only this one clears a gate.
CLEARING_CERTIFICATION = (PRODUCTION_CERTIFIED,)

SPEC_VERSION = 'nfl-governed-thresholds-1'


# --- freshness --------------------------------------------------------------
#: Per vintage family, the maximum age in hours a capture may carry at the
#: information cut. A family with NO entry cannot be certified fresh -- the
#: absence is a refusal, not a pass.
#:
#: The hours below are the SHAPE of the requirement, proposed from what the
#: family is for. They are not measurements of how much a stale capture costs,
#: because that measurement does not exist.
FRESHNESS_HOURS = {
    'injuries': {
        'max_age_hours': 6.0,
        'certification': CANDIDATE,
        'why_proposed': (
            'practice and game-status designations change on a daily cycle '
            'and the final Friday or Saturday report supersedes everything '
            'before it. A capture older than a report cycle can disagree '
            'with the league in the direction that matters most -- a player '
            'ruled out after the capture still reads available.'),
        'certification_requires': (
            'prospective measurement of how often a designation changed '
            'between capture and kickoff, by age bucket, over enough game '
            'weeks to separate that rate from noise. Two weeks of football '
            'cannot support it.'),
    },
    'depth_charts': {
        'max_age_hours': 24.0,
        'certification': CANDIDATE,
        'why_proposed': (
            'the vendor stamps a daily `dt`, so intra-day change is not '
            'recoverable from the family at all and a sub-daily requirement '
            'would be asking for precision the source does not carry.'),
        'certification_requires': (
            'measurement of how often a listing moved within a week and '
            'whether the move preceded a usage change.'),
    },
    'weekly_rosters': {
        'max_age_hours': 24.0,
        'certification': CANDIDATE,
        'why_proposed': (
            'roster status changes on transactions, which cluster on the '
            'Tuesday and Saturday cycles rather than continuously.'),
        'certification_requires': (
            'measurement of transaction arrival against capture age.'),
    },
    'schedules': {
        'max_age_hours': 168.0,
        'certification': CANDIDATE,
        'why_proposed': (
            'kickoff times and the fixture list are near-static within a '
            'week; this family is the least perishable of the four.'),
        'certification_requires': (
            'measurement of in-week schedule changes, which are rare enough '
            'that establishing the rate needs seasons, not weeks.'),
    },
}


# --- participation ----------------------------------------------------------
#: How much of a club's five-man snap budget an allocator may carry
#: unreconstructed and still be considered to have a usable denominator.
PARTICIPATION_UNRESOLVED_FRACTION = {
    'max_unresolved_fraction': 0.05,
    'certification': CANDIDATE,
    'why_proposed': (
        'a twentieth of a club\'s offence is roughly one player on the field '
        'for a fifth of the snaps. Below that an allocation error is '
        'unlikely to move a room\'s ordering; above it, it can.'),
    'certification_requires': (
        'prospective measurement of realised opportunity error against '
        'unresolved mass, by bucket, on games whose outcomes were not used '
        'to choose the bucket edges. What is needed is the CONDITIONAL error '
        'given unresolved mass, and no such series exists.'),
    'note': (
        'the 0.25 used on 2026-09-21 was supplied at the call site and had '
        'no justification at all. It is recorded here as what it was: a '
        'number chosen to let a board through.'),
}


# --- redistribution ---------------------------------------------------------
#: Where does opportunity go when the player who held it is no longer in the
#: set? There is no model for this, so there is no threshold either.
REDISTRIBUTION_MODEL = {
    'model': None,
    'certification': CANDIDATE,
    'why_none': (
        'renormalising gives the survivors the departed player\'s share in '
        'proportion to what they already had. That is one hypothesis among '
        'several -- the opportunity may go disproportionately to the same '
        'position, to the next man on the listing, or to a personnel '
        'grouping that changes the room entirely -- and this project has '
        'measured none of them.'),
    'certification_requires': (
        'a forward-chained comparison of candidate redistribution rules '
        'against realised shares on games where a measurable share of a '
        'room departed, scored out of sample.'),
    'max_reassigned_fraction_without_a_model': 0.0,
    'why_zero': (
        'with no validated destination for the mass, ANY reassignment is an '
        'assumption about where it went. Zero is not a strict threshold '
        'chosen to be safe; it is the only fraction that involves no '
        'unvalidated claim.'),
}


def freshness_requirement(family: str) -> dict:
    """The governed requirement for one family, or an explicit absence."""
    spec = FRESHNESS_HOURS.get(family)
    if spec is None:
        return {'family': family, 'max_age_hours': None,
                'certification': None,
                'why_absent': (
                    'no freshness requirement is declared for this family. '
                    'An undeclared requirement cannot be met, so the family '
                    'cannot be certified fresh -- absence refuses rather '
                    'than passes.')}
    return {'family': family, **spec}


def is_clearing(certification) -> bool:
    """Whether a certification state may clear a gate. Only one may."""
    return certification in CLEARING_CERTIFICATION


def summary() -> dict:
    """Everything certifiable in the system and where it stands."""
    items = [{'name': f'freshness.{k}', 'value': v['max_age_hours'],
              'unit': 'hours', 'certification': v['certification']}
             for k, v in sorted(FRESHNESS_HOURS.items())]
    items.append({'name': 'participation.max_unresolved_fraction',
                  'value': PARTICIPATION_UNRESOLVED_FRACTION[
                      'max_unresolved_fraction'],
                  'unit': 'fraction',
                  'certification': PARTICIPATION_UNRESOLVED_FRACTION[
                      'certification']})
    items.append({'name': 'redistribution.model',
                  'value': REDISTRIBUTION_MODEL['model'], 'unit': None,
                  'certification': REDISTRIBUTION_MODEL['certification']})
    return {
        'spec_version': SPEC_VERSION, 'items': items,
        'n_production_certified': sum(
            1 for i in items if i['certification'] == PRODUCTION_CERTIFIED),
        'n_candidate': sum(1 for i in items
                           if i['certification'] == CANDIDATE),
        'the_point': (
            'nothing here is PRODUCTION_CERTIFIED. Every gate evaluated '
            'against a CANDIDATE threshold returns a non-passing state, and '
            'the verdict machine reads RESEARCH_ONLY. That is the correct '
            'answer while the evidence that would certify these numbers does '
            'not exist.'),
    }
