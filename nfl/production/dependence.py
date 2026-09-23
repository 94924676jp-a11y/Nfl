"""Whether a cross-player correlation read off an artifact means anything.

OWNER RULING 2026-09-23. This module exists because a number travelled three
documents as a "verified project computation" and, when it was finally traced,
had no computation behind it at all -- and the only artifacts that could have
produced it carry a manifest line saying that reading them that way measures
the random number generator rather than football.

Nothing here calibrates anything. It is the rule that decides whether a
dependence measurement is admissible in the first place, plus the vocabulary
the later SimulationCalibration and HistoricalSlateReplay slices must use
rather than inventing their own.

THREE SEPARATE THINGS ARE KEPT APART HERE

1. ELIGIBILITY. An artifact whose rows are independently seeded cannot
   support a cross-player correlation. `assert_cross_player_eligible` refuses
   one by name instead of returning a number nobody can interpret.

2. ESTIMAND. "Correlation = 0.15" is not a measurement. A measurement names
   its population, its conditioning state, which dimension is random, what
   the outcome is and at what level it aggregates. `Estimand` refuses to
   exist without all five, so a metric cannot be reported without them.

3. EVIDENCE STATE FOR A REPLAY CUT. Some history is not weakly
   reconstructable; it is gone. `UNRECOVERABLE_FOR_CUT` is a different answer
   from `HISTORICAL_RECONSTRUCTION_ONLY`, and a cut carrying it is not a
   backtest.

COLUMN ALIGNMENT IS NOT A SHARED WORLD

    COLUMN_ALIGNED        every player has a 17th draw
    SHARED_FOOTBALL_WORLD world 17 means the same football scenario for all
                          of them

The second requires shared latent causes -- pace, team play volume, script,
dropbacks, rush attempts, drive outcomes, touchdown opportunity, opportunity
allocation -- from which each player's line derives conditionally. Only then
does a cross-player correlation carry football meaning. Measured across this
repository on 2026-09-23: 351 of 351 sealed draw artifacts declare
INDEPENDENT_STREAMS_COLUMN_ALIGNED and none declares a shared world.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nfl-dependence-eligibility-0'

# --- 1. eligibility -------------------------------------------------------

ELIGIBLE = 'DEPENDENCE_CALIBRATION_ELIGIBLE'
INELIGIBLE = 'DEPENDENCE_CALIBRATION_INELIGIBLE'
#: Not the same as INELIGIBLE. An artifact that never declared its draw-index
#: semantics has not told us the rows are independent -- it has told us
#: nothing, and we may not read that silence either way.
UNDECLARED = 'DEPENDENCE_CALIBRATION_SEMANTICS_UNDECLARED'
ELIGIBILITY_STATES = (ELIGIBLE, INELIGIBLE, UNDECLARED)

#: Draw-index semantics this repository's artifacts actually declare.
INDEPENDENT_STREAMS = 'INDEPENDENT_STREAMS_COLUMN_ALIGNED'
#: The value a generator would have to declare for cross-player dependence to
#: be a football quantity. NOTHING IN THIS REPOSITORY DECLARES IT and nothing
#: may start declaring it because a calibration slice would like it to be
#: true: the declaration is a claim about the generator, and it is earned by
#: the generator drawing shared latent football causes once per world.
SHARED_FOOTBALL_WORLD = 'SHARED_FOOTBALL_WORLD'

#: The latent causes a world must share before the declaration is earned.
#: Listed so the SimulationCalibration slice inspects a named set rather than
#: deciding case by case what counts.
REQUIRED_SHARED_LATENTS = (
    'game_pace',
    'team_play_volume',
    'score_script',
    'dropbacks',
    'rush_attempts',
    'drive_outcomes',
    'touchdown_opportunity',
    'team_opportunity_allocation',
)


def declared_semantics(manifest: Dict[str, Any]) -> Optional[str]:
    """`draw_index_semantics.across_rows`, or None when absent."""
    d = ((manifest or {}).get('draw_index_semantics') or {})
    v = d.get('across_rows')
    return v if isinstance(v, str) and v else None


def cross_player_eligibility(manifest: Dict[str, Any]) -> Dict[str, str]:
    """Verdict plus the reason, never a bare boolean."""
    declared = declared_semantics(manifest)
    if declared is None:
        return {
            'verdict': UNDECLARED, 'declared': None,
            'why': 'the artifact carries no draw_index_semantics.across_rows. '
                   'An artifact that has not said how its rows relate has not '
                   'said they are coupled, and silence may not be read as '
                   'either answer.'}
    if declared == SHARED_FOOTBALL_WORLD:
        return {
            'verdict': ELIGIBLE, 'declared': declared,
            'why': 'the generator declares that one column is one shared '
                   'football world across rows, so a cross-player '
                   'correlation read off that axis is a football quantity.'}
    if declared == INDEPENDENT_STREAMS:
        return {
            'verdict': INELIGIBLE, 'declared': declared,
            'why': 'the artifact\'s own manifest states that rows are seeded '
                   'independently, so a cross-row correlation read off the '
                   'column axis measures the generator\'s lack of coupling, '
                   'not a football quantity. Column alignment makes '
                   'CROSS-METRIC dependence within one row real; it does '
                   'nothing for cross-player dependence.'}
    return {
        'verdict': UNDECLARED, 'declared': declared,
        'why': f'{declared!r} is not a semantics this rule knows. It is '
               f'treated as undeclared rather than guessed at, because a '
               f'wrong guess here silently licenses an inadmissible '
               f'measurement.'}


def assert_cross_player_eligible(manifest: Dict[str, Any], *,
                                 what: str = 'a cross-player correlation',
                                 artifact: str = None) -> Outcome:
    """PASS only for an artifact that declares a shared football world."""
    v = cross_player_eligibility(manifest)
    ev = {'eligibility': v['verdict'], 'declared_semantics': v['declared'],
          'artifact': artifact, 'why': v['why'],
          'spec_version': SPEC_VERSION}
    if v['verdict'] == ELIGIBLE:
        return Outcome.ok('DEPENDENCE_CALIBRATION_ELIGIBLE', ev,
                          detail=f'{what} is admissible from {artifact}')
    if v['verdict'] == INELIGIBLE:
        return Outcome.fail(
            'DEPENDENCE_CALIBRATION_INELIGIBLE',
            f'{what} may not be computed from {artifact}: {v["why"]}',
            **ev)
    return Outcome.blocked(
        'DEPENDENCE_CALIBRATION_SEMANTICS_UNDECLARED',
        f'{what} may not be computed from {artifact}: {v["why"]}',
        cause=Cause.GOVERNANCE, **ev)


# --- 2. estimands ---------------------------------------------------------

#: The dimension the randomness runs over. These are NOT interchangeable and
#: the whole retraction below exists because two of them were compared.
ACROSS_GAMES = 'ACROSS_GAMES'
ACROSS_WORLDS = 'ACROSS_SIMULATION_WORLDS'
ACROSS_PLAYER_GAMES = 'ACROSS_PLAYER_GAMES'
RANDOM_DIMENSIONS = (ACROSS_GAMES, ACROSS_WORLDS, ACROSS_PLAYER_GAMES)


@dataclass(frozen=True)
class Estimand:
    """What a dependence number is a number ABOUT.

    Every field is required. A dependence metric reported without one of
    them is not admissible, which is the rule this class enforces by being
    impossible to construct incompletely.
    """
    name: str
    population: str            # which units
    conditioning: str          # what is held fixed
    random_dimension: str      # what varies
    outcome: str               # what is measured on each unit
    aggregation: str           # at what level it is combined
    note: Optional[str] = None

    def __post_init__(self):
        missing = [f.name for f in dataclasses.fields(self)
                   if f.name != 'note' and not getattr(self, f.name)]
        if missing:
            raise AssertionError(
                f'estimand {self.name or "<unnamed>"} is missing {missing}. '
                f'A bare correlation is not a measurement: without a '
                f'population, a conditioning state, a random dimension, an '
                f'outcome definition and an aggregation level, two numbers '
                f'cannot be known to be about the same thing.')
        if self.random_dimension not in RANDOM_DIMENSIONS:
            raise AssertionError(
                f'{self.random_dimension!r} is not one of '
                f'{RANDOM_DIMENSIONS}.')

    def comparable_to(self, other: 'Estimand') -> Tuple[bool, str]:
        """Two numbers may be compared only when they measure the same thing.

        Returns the verdict AND the reason, because "not comparable" is a
        finding a reader needs to see stated, not a silent False.
        """
        diffs = [f.name for f in dataclasses.fields(self)
                 if f.name not in ('name', 'note')
                 and getattr(self, f.name) != getattr(other, f.name)]
        if not diffs:
            return True, 'same population, conditioning, random dimension, ' \
                         'outcome and aggregation'
        return False, (
            f'{self.name} and {other.name} differ in {diffs}. Numerical '
            f'equality between them is not a calibration target and their '
            f'difference is not a defect.')

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


#: The two estimands the retracted comparison ran together.
OBSERVED_TEAM_VS_OPPONENT = Estimand(
    name='observed_team_vs_opponent_offense_dk',
    population='completed NFL games',
    conditioning='NOTHING IS HELD FIXED -- game environments vary across the '
                 'sample and that variation is part of what is measured',
    random_dimension=ACROSS_GAMES,
    outcome='summed DraftKings points of a club\'s offensive players in a '
            'game, against the same for its opponent',
    aggregation='one pair per game, pooled over a season',
    note='re-derived from repository bytes on 2026-09-22 from '
         'nfl/research/postgame/pbp_2024 and pbp_2025, scored with '
         'nfl/dfs/scoring/draftkings.py.')

SIMULATED_TEAM_VS_OPPONENT = Estimand(
    name='simulated_team_vs_opponent_offense_dk',
    population='simulated worlds of ONE slate',
    conditioning='the game and slate state are FIXED -- one matchup, one '
                 'environment, one information cut',
    random_dimension=ACROSS_WORLDS,
    outcome='summed DraftKings points of a club\'s simulated offensive '
            'players in a world, against the same for its opponent',
    aggregation='one pair per world, within one game',
    note='this is a conditional dependence given an environment; the '
         'observed estimand pools over environments.')


# --- 3. the 2026-09-23 retraction ----------------------------------------

#: Values that travelled as evidence and are NOT admissible as calibration
#: targets. Recorded rather than deleted: a retraction nobody can find gets
#: re-quoted from the document that overstated it.
UNVERIFIED = {
    'simulated_team_vs_opponent_offense_dk = -0.128': {
        'status': 'UNVERIFIED',
        'claimed_as': 'VERIFIED FACT (project computation) in the 2026-09-22 '
                      'data-capability packet',
        'why_unverified':
            'no re-derivable computation for it exists in this repository. '
            'The chain is packet -> external-research/'
            'nfl-fullslate-dfs-construction-2026-09-18/'
            'nfl-fullslate-dfs-lineup-construction.pplx.md:617 -> "the prior '
            'second-opinion work in this project", and there the trail ends: '
            'no script, no artifact, no JSON.',
        'why_it_would_be_inadmissible_anyway':
            'every sealed draw artifact here -- 351 of 351 on 2026-09-23 -- '
            'declares INDEPENDENT_STREAMS_COLUMN_ALIGNED, which this module '
            'classifies INELIGIBLE. A number read off that axis measures the '
            'seeding scheme.',
        'and_separately':
            'it was compared against an ACROSS_GAMES observed value. Those '
            'are different estimands and their numerical equality is not a '
            'target. See Estimand.comparable_to.',
        'ruling': 'it is not a calibration target and not a defect. It may '
                  'become evidence only when re-derived from an ELIGIBLE '
                  'artifact under a declared estimand, and until then it is '
                  'not quoted at all.',
    },
}

#: Observed values that ARE admissible, because this repository re-derived
#: them from its own bytes with its own verified scoring adapter. They are
#: admissible AS OBSERVATIONS; they are not thereby within-world targets.
REDERIVED_OBSERVED = {
    'estimand': OBSERVED_TEAM_VS_OPPONENT.name,
    'source': 'nfl/research/postgame/pbp_2024.23370d5d10f8104d.csv.gz and '
              'pbp_2025.2f135887790a013f.csv.gz',
    'scoring': 'nfl/dfs/scoring/draftkings.py, the adapter reconciled to the '
               'engine\'s own dk_scoring array',
    'rederived_at': '2026-09-22',
    'values': {'2024_REG': 0.1471, '2025_REG': 0.2068},
    'n_games': {'2024_REG': 272, '2025_REG': 272},
    'sensitivity': 'four variants each -- symmetric and away-vs-home '
                   'ordering, with and without fumbles and two-point '
                   'conversions, REG and REG+POST -- span +0.147 to +0.158 '
                   'for 2024 and +0.207 to +0.232 for 2025.',
    'not_canonical': 'the packet\'s +0.1201 for 2024 did NOT reproduce under '
                     'any variant. The gap is about 0.03 and is a '
                     'definitional difference, most likely over which '
                     'players count as offense. Quote the re-derived values '
                     'and the reconciliation as open; do not carry +0.1201 '
                     'forward as canonical.',
}

#: Better first adversarial targets, and why they are only CANDIDATES.
CANDIDATE_TARGETS = {
    'QB_WITH_OWN_RECEIVER': {
        'simulated': 0.1054,
        'simulated_source': 'nfl/research/dfs/DET_BUF_2026W2/'
                            'CORRELATION.json, by_class mean_r over 36 pairs',
        'observed': {'QB_PC1': (0.368, 0.274), 'QB_PC2': (0.296, 0.318),
                     'QB_PC3': (0.208, 0.259)},
        'observed_source': '2026-09-22 packet section 8.2, NOT re-derived '
                           'here',
        'why_a_candidate_not_a_target':
            'the simulated side comes from an artifact this module '
            'classifies INELIGIBLE, and the observed side is an ACROSS_GAMES '
            'quantity. The direction is nonetheless informative: the sealed '
            'artifact\'s own caveat says a NEAR-ZERO reading understates '
            'coupling, so a positive +0.105 against an observed +0.21 to '
            '+0.37 is a floor on the gap rather than a measurement of it.',
    },
    'SAME_TEAM_BACKS': {
        'simulated': -0.2212,
        'simulated_source': 'the same CORRELATION.json, 4 pairs',
        'observed': {'RB1_RB2': (-0.121, -0.104)},
        'observed_source': '2026-09-22 packet section 8.2, NOT re-derived '
                           'here',
        'why_a_candidate_not_a_target':
            'the simulated side comes from an artifact this module '
            'classifies INELIGIBLE, and the observed side is an ACROSS_GAMES '
            'quantity -- the same two problems. Here they bite harder: the '
            'caveat says a near-zero reading understates coupling, which '
            'gives no bound at all on a reading that is already strongly '
            'negative, and n=4 pairs on one game is far too thin to carry a '
            'conclusion in either direction.',
    },
}

#: The estimand the owner asked to be investigated instead of raw totals.
RESIDUAL_DEPENDENCE_PROPOSAL = (
    'Estimate historical dependence on RESIDUAL outcomes -- actual minus the '
    'pregame expected mean -- paired within a game, rather than on raw '
    'cross-game DraftKings totals. Conditioning on team expectation, player '
    'expectation, role and game environment removes exactly the '
    'between-environment variation that the simulator holds fixed, which is '
    'what would make an observed number and a within-world number estimands '
    'of the same thing. TO BE INVESTIGATED AND RETURNED WITH EVIDENCE '
    'BEFORE IMPLEMENTATION -- it is a proposal here, not a decision.')


# --- 4. replay evidence states -------------------------------------------

PIT_SAFE = 'PIT_SAFE'
HISTORICAL_RECONSTRUCTION_ONLY = 'HISTORICAL_RECONSTRUCTION_ONLY'
#: The third state, and the reason it had to exist. Some sources are
#: overwritten in place -- nflverse rosters are rewritten daily at 07:00 UTC
#: -- so before this repository's first archive date there is no weaker
#: reconstruction available. There is nothing. A cut that needs one of those
#: is not a worse backtest; it is not a backtest.
UNRECOVERABLE_FOR_CUT = 'UNRECOVERABLE_FOR_CUT'
REPLAY_EVIDENCE_STATES = (PIT_SAFE, HISTORICAL_RECONSTRUCTION_ONLY,
                          UNRECOVERABLE_FOR_CUT)


@dataclass(frozen=True)
class ReplayEvidenceStatus:
    """A CUT-level verdict, not a note attached to one feature.

    A cut is only as replayable as its least replayable required capability,
    so the verdict is computed from the whole required set by `for_cut` and
    may not be asserted directly above what that set supports.
    """
    status: str
    reason: str
    missing_capabilities: Tuple[str, ...] = ()
    reconstructed_capabilities: Tuple[str, ...] = ()
    cut: Optional[str] = None

    def __post_init__(self):
        if self.status not in REPLAY_EVIDENCE_STATES:
            raise AssertionError(
                f'{self.status!r} is not one of {REPLAY_EVIDENCE_STATES}.')
        if self.status == UNRECOVERABLE_FOR_CUT and \
                not self.missing_capabilities:
            raise AssertionError(
                'UNRECOVERABLE_FOR_CUT without naming what is missing is an '
                'unfalsifiable refusal.')
        if self.status == PIT_SAFE and (self.missing_capabilities
                                        or self.reconstructed_capabilities):
            raise AssertionError(
                'PIT_SAFE is refused while any required capability is '
                'unrecoverable or merely reconstructed: '
                f'missing={list(self.missing_capabilities)} '
                f'reconstructed={list(self.reconstructed_capabilities)}.')

    @property
    def may_be_called_a_backtest(self) -> bool:
        return self.status != UNRECOVERABLE_FOR_CUT

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def for_cut(cut: str, capabilities: Dict[str, str]) -> ReplayEvidenceStatus:
    """The cut's verdict from its required capabilities' own states.

    `capabilities` maps a required capability name to one of the three
    states. An empty set is NOT PIT_SAFE: a cut that requires nothing has
    not been analysed.
    """
    bad = sorted(k for k, v in capabilities.items()
                 if v not in REPLAY_EVIDENCE_STATES)
    if bad:
        raise AssertionError(
            f'capabilities {bad} carry a state outside '
            f'{REPLAY_EVIDENCE_STATES}.')
    if not capabilities:
        return ReplayEvidenceStatus(
            status=UNRECOVERABLE_FOR_CUT, cut=cut,
            missing_capabilities=('<none declared>',),
            reason='no required capability was declared for this cut. A cut '
                   'whose requirements nobody enumerated has not been shown '
                   'replayable; it has not been examined.')
    missing = tuple(sorted(k for k, v in capabilities.items()
                           if v == UNRECOVERABLE_FOR_CUT))
    recon = tuple(sorted(k for k, v in capabilities.items()
                         if v == HISTORICAL_RECONSTRUCTION_ONLY))
    if missing:
        return ReplayEvidenceStatus(
            status=UNRECOVERABLE_FOR_CUT, cut=cut,
            missing_capabilities=missing, reconstructed_capabilities=recon,
            reason=f'{len(missing)} required capability(ies) no longer exist '
                   f'in a form that reconstructs what was known at this cut: '
                   f'{list(missing)}. A run over this cut may not be '
                   f'presented as a backtest.')
    if recon:
        return ReplayEvidenceStatus(
            status=HISTORICAL_RECONSTRUCTION_ONLY, cut=cut,
            reconstructed_capabilities=recon,
            reason=f'{len(recon)} required capability(ies) are rebuilt after '
                   f'the fact rather than read from a vintage captured at '
                   f'the cut: {list(recon)}. Usable, and not point-in-time.')
    return ReplayEvidenceStatus(
        status=PIT_SAFE, cut=cut,
        reason=f'all {len(capabilities)} required capability(ies) are '
               f'available as vintages captured at or before this cut.')


def as_dict() -> Dict[str, Any]:
    return {
        'spec_version': SPEC_VERSION,
        'eligibility_states': list(ELIGIBILITY_STATES),
        'required_shared_latents': list(REQUIRED_SHARED_LATENTS),
        'replay_evidence_states': list(REPLAY_EVIDENCE_STATES),
        'estimands': {e.name: e.as_dict() for e in
                      (OBSERVED_TEAM_VS_OPPONENT,
                       SIMULATED_TEAM_VS_OPPONENT)},
        'unverified': UNVERIFIED,
        'rederived_observed': REDERIVED_OBSERVED,
        'candidate_targets': CANDIDATE_TARGETS,
        'residual_dependence_proposal': RESIDUAL_DEPENDENCE_PROPOSAL,
    }
