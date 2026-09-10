"""Stage 9: the prospective forecast artifact contract.

THE ONE RULE THAT MAKES EVERYTHING ELSE MEANINGFUL

    retrieved_at  <=  written_at  <  kickoff

A forecast written after kickoff is not a forecast. A forecast built on bytes
retrieved after it was written did not exist when it claims to have existed.
Both are checked, and neither is inferable from a file's modification time.

IMMUTABILITY. No artifact may be rewritten after `written_at`. A correction is
a NEW artifact with a new version pointing at the one it supersedes. Mutation
is refused, because an artifact that can be edited after the fact cannot be
evidence about what was believed before the game.

ARMS. A, B and C carry different evidentiary status and MAY NEVER BE POOLED.

  A  static pre-2026 benchmark; consumes NO 2026 outcome, all season.
  B  frozen-spec prequential; may consume EARLIER 2026 outcomes, by frozen rule.
  C  adaptive prospective; separate and weakest evidentiary status.

B13. A MODEL-SOURCED ARTIFACT MUST REFERENCE ITS DRAWS. Four quantiles cannot
produce a proper score, a PIT value, a tail probability or any dependence
diagnostic, so `draw_artifact_sha256` is required of any artifact whose numbers
came from the model. The draws live in a sidecar; the artifact carries the hash.

B14. AND IT MUST CARRY ITS ACCOUNTING VERDICTS. `INVARIANTS` below is the one
place that says which verdicts GATE publication and which are recorded
diagnostics, and `validate` refuses an artifact carrying a HARD failure.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

CONTRACT_VERSION = 'nfl-forecast-artifact-1'

ARMS = {
    'A': {'name': 'static pre-2026 benchmark',
          'may_consume_2026_outcomes': False,
          'note': 'consumes no 2026 outcome at any point in the season'},
    'B': {'name': 'frozen-spec prequential',
          'may_consume_2026_outcomes': 'EARLIER_ONLY_BY_FROZEN_RULE',
          'note': 'may consume 2026 outcomes strictly earlier than the '
                  'forecast week, and only through a rule frozen in advance'},
    'C': {'name': 'adaptive prospective',
          'may_consume_2026_outcomes': 'EARLIER_ONLY',
          'note': 'separate and WEAKEST evidentiary status'},
}

REQUIRED = ('game_id', 'kickoff_utc', 'written_at', 'source_captures',
            'model_arm', 'spec_hash', 'code_commit', 'seed_protocol',
            'feature_set_hash', 'eligibility_verdict', 'player_ids',
            'team_ids', 'distributions', 'completeness', 'contract_version')

OPTIONAL = ('draw_artifact_sha256', 'draw_artifact', 'accounting_verdicts',
            'cold_start_freeze_identity', 'refusal_codes', 'supersedes')

COMPLETENESS = ('COMPLETE', 'PARTIAL_PLAYER_COVERAGE', 'REFUSED')


# =====================================================================
# B14: WHICH VERDICTS GATE PUBLICATION, DECLARED IN ONE READABLE PLACE
# =====================================================================
#
# The defect being closed: accounting verdicts were written into the artifact
# as display strings -- `f'{state}[{code}]'` -- and the run continued. An
# artifact could therefore represent itself as a valid forecast while carrying
# FAIL on an invariant the whole layer rests on, and nothing in the contract
# noticed, because a string is not a gate.
#
# The owner's distinction, implemented here and nowhere else, so that no
# scattered conditional can quietly change it:
#
#   HARD        an accounting or statistical INVARIANT. If it fails, the
#               numbers are not internally consistent, so there is no valid
#               forecast to seal. Refuse.
#   DIAGNOSTIC  a provider/model DISAGREEMENT or a characterised limitation.
#               Recorded on every run, never smoothed away, and NOT a gate --
#               refusing on it would refuse a forecast that is internally
#               coherent and merely known to be imperfect.
#
# Partial player coverage is the third case and is deliberately NOT in this
# table: it is carried by `completeness` / `absent_layers`, which already work.
#
# TWO RULES THAT MAKE THE TABLE MEAN SOMETHING
#   * A verdict may not claim a class this table does not give it. Promoting a
#     diagnostic to a gate, or demoting a hard invariant to a diagnostic, is a
#     change to this table and to nothing else.
#   * Every invariant here must carry a verdict in every model-sourced
#     artifact. A missing verdict is not a pass -- an invariant that did not
#     run has not been satisfied.
HARD = 'HARD'
DIAGNOSTIC = 'DIAGNOSTIC'
INVARIANT_CLASSES = (HARD, DIAGNOSTIC)

# States that a HARD invariant may not be in if the artifact is to seal.
# FAIL     the invariant was evaluated and violated.
# BLOCKED  the invariant could not be evaluated. A check that did not run has
#          not passed, and this project has been bitten by treating the two the
#          same. DEFERRED is different: it is an explicit, recorded debt with
#          an `owed` payload, and it is carried into the artifact rather than
#          silently cleared.
HARD_REFUSING_STATES = ('FAIL', 'BLOCKED')

INVARIANTS = {
    # ---- HARD: internal consistency of the numbers being sealed ----------
    'qb_dropback_identity': {
        'class': HARD, 'evaluator': 'nfl.production.qb_v1.identity_check',
        'asserts': 'attempts + sacks + scrambles == dropbacks, per draw cell',
        'why_hard': 'the identity the entire QB layer is built on; a violation '
                    'means the components do not describe one football game.'},
    'rushing_single_owner': {
        'class': HARD,
        'evaluator': 'nfl.production.nonqb.rushing_a1.allocate',
        'asserts': 'one multinomial partitions the rush-play budget across '
                   'kneel / designed QB / RB / WR / TE / fringe, so every '
                   'carry has exactly one owner and the six categories close '
                   'to the budget exactly in every draw',
        'why_hard': 'the incumbent let a QB rush draw exceed the carry pool it '
                    'sat inside -- the quarterback counted twice. Duplicate '
                    'ownership of a finite budget is not a calibration '
                    'question and cannot be averaged away.'},
    'qb_per_draw_accounting': {
        'class': HARD,
        'evaluator': 'nfl.production.qb_accounting.reconcile_draws',
        'asserts': 'the per-draw accounting identities across QB fields',
        'why_hard': 'a per-draw violation cannot be averaged away; every '
                    'downstream score reads those same cells.'},
    'qb_team_accounting': {
        'class': HARD,
        'evaluator': 'nfl.production.qb_accounting.reconcile_team',
        'asserts': 'QB draws against the team quantities they are allocated '
                   'from',
        'why_hard': 'players summing to something other than their team is a '
                    'mass error, not a modelling opinion.'},
    'qb_cross_layer_reconciliation': {
        'class': HARD,
        'evaluator': 'nfl.production.qb_accounting.reconcile_cross_layer',
        'asserts': 'team passing yards == player receiving yards and passing '
                   'TD == receiving TD, on the same draw index',
        'why_hard': 'these are the same quantity counted twice; disagreement '
                    'is arithmetic, not disagreement about football. DEFERRED '
                    'while the receiving layer is not in the run is a recorded '
                    'debt and is not treated as satisfied.'},
    'draw_set_non_empty': {
        'class': HARD, 'evaluator': 'nfl.production.draws_artifact.DrawSet',
        'asserts': 'at least one layer produced a draw matrix',
        'why_hard': 'absence is never success; an artifact with no draws is '
                    'not a forecast.'},
    'draw_index_shared': {
        'class': HARD, 'evaluator': 'nfl.production.draws_artifact.verify',
        'asserts': 'every stored matrix has the same number of columns, so '
                   'column j means one iteration everywhere',
        'why_hard': 'a ragged draw index destroys every dependence diagnostic '
                    'silently -- the numbers still look fine.'},
    'draw_encoding_lossless': {
        'class': HARD, 'evaluator': 'nfl.production.draws_artifact.DrawSet.write',
        'asserts': 'the stored encoding reproduces every draw exactly',
        'why_hard': 'a lossy store is a post-hoc correction of the model\'s '
                    'own output.'},
    'draw_artifact_integrity': {
        'class': HARD, 'evaluator': 'nfl.production.draws_artifact.verify',
        'asserts': 'the referenced file re-reads, and hashes to the recorded '
                   'digest',
        'why_hard': 'deterministic replay is the claim the hash exists to '
                    'support.'},
    'draw_summary_consistency': {
        'class': HARD,
        'evaluator': 'nfl.production.draws_artifact.assert_summary_consistent',
        'asserts': 'the quantile view in `distributions` is recomputable, '
                   'exactly, from the stored draws',
        'why_hard': 'the summary is what a reader trusts on sight; if it and '
                    'the draws disagree, the artifact carries two different '
                    'forecasts and says nothing about it.'},

    # ---- DIAGNOSTIC: recorded on every run, never a gate ------------------
    'qb_known_limitations': {
        'class': DIAGNOSTIC,
        'evaluator': 'nfl.production.qb_v1.KNOWN_LIMITATIONS',
        'asserts': 'the measured, characterised weaknesses of the QB layer '
                   '(multi-QB over-prediction, interception discrimination, '
                   'discrete low-count interval width)',
        'why_not_hard': 'these are measurements of how good the model is, not '
                        'of whether its numbers are self-consistent. Refusing '
                        'on them would refuse every run the project has ever '
                        'made, and would be a quality bar wearing an '
                        'invariant\'s clothes.'},
    'qb_allocation_residual': {
        'class': DIAGNOSTIC,
        'evaluator': 'nfl.production.qb_accounting.reconcile_team (warnings)',
        'asserts': 'the named residual between summed QB dropbacks and team '
                   'dropbacks',
        'why_not_hard': 'the residual is NAMED and quantified by the layer '
                        'itself rather than clipped; it is a declared property '
                        'of the prior-only share model.'},
    'nonqb_layer_availability': {
        'class': DIAGNOSTIC,
        'evaluator': 'nfl.production.run_forecast (non-QB chain states)',
        'asserts': 'which completeness layers ran and which are waiting on a '
                   'captured input',
        'why_not_hard': 'a layer blocked on a feed is a coverage fact, carried '
                        'by `completeness` and `absent_layers`. It is reported '
                        'here so the artifact says WHICH, not only HOW MANY.'},
}

HARD_INVARIANTS = tuple(sorted(k for k, v in INVARIANTS.items()
                               if v['class'] == HARD))
DIAGNOSTIC_INVARIANTS = tuple(sorted(k for k, v in INVARIANTS.items()
                                     if v['class'] == DIAGNOSTIC))


def verdict(name: str, outcome, **extra) -> dict:
    """One invariant's verdict, classified from the table and never by hand.

    The class is READ from INVARIANTS. A call site cannot supply one, which is
    what makes "never silently promoted or demoted" structural rather than a
    convention someone remembers.
    """
    if name not in INVARIANTS:
        raise KeyError(
            f'INVARIANT_NOT_DECLARED: {name!r} is not in artifact.INVARIANTS. '
            f'An invariant that is not in the table has no declared class, so '
            f'nobody can say whether it gates. Add it there, deliberately.')
    spec = INVARIANTS[name]
    st = getattr(getattr(outcome, 'state', None), 'value', None)
    if st is None:
        raise TypeError(
            f'INVARIANT_VERDICT_NOT_AN_OUTCOME: {name} was given '
            f'{type(outcome).__name__}. A verdict recorded as a bare string is '
            f'exactly the defect this replaces.')
    reserved = sorted(set(extra) & {'class', 'invariant', 'state', 'code'})
    if reserved:
        raise KeyError(
            f'INVARIANT_VERDICT_FIELD_RESERVED: {name} tried to set {reserved} '
            f'from the call site. The class comes from the table and the state '
            f'comes from the Outcome; allowing either to be overridden here '
            f'would put the promotion/demotion decision back in the place this '
            f'function exists to take it out of.')
    v = {'invariant': name, 'class': spec['class'], 'state': st,
         'code': getattr(outcome, 'code', None),
         'detail': (getattr(outcome, 'detail', '') or '')[:400],
         'evaluator': spec['evaluator']}
    if st == 'DEFERRED':
        v['owed'] = (getattr(outcome, 'evidence', {}) or {}).get('owed')
    v.update(extra)
    return v


def assert_hard_invariants(verdicts) -> Outcome:
    """The gate. HARD FAIL or BLOCKED refuses; DIAGNOSTIC never refuses.

    Four ways to refuse, and each names a different mistake:
      MISCLASSIFIED    a verdict claims a class the table does not give it
      UNDECLARED       a verdict names an invariant not in the table
      MISSING          a declared invariant has no verdict at all
      HARD_FAILED      a hard invariant is FAIL or BLOCKED
    """
    if not verdicts:
        return Outcome.fail(
            'ACCOUNTING_VERDICTS_ABSENT',
            'no accounting verdict was recorded. An artifact that carries no '
            'verdicts has not passed its invariants -- it has not been asked.')
    seen, misclassified, undeclared = {}, [], []
    for v in verdicts:
        name = v.get('invariant')
        if name not in INVARIANTS:
            undeclared.append(name)
            continue
        if v.get('class') != INVARIANTS[name]['class']:
            misclassified.append(
                {'invariant': name, 'declared': INVARIANTS[name]['class'],
                 'claimed': v.get('class')})
        seen[name] = v
    if undeclared:
        return Outcome.fail(
            'INVARIANT_UNDECLARED',
            f'{undeclared} carry verdicts but are not in the invariant table, '
            f'so nothing says whether they gate.', invariants=undeclared)
    if misclassified:
        return Outcome.fail(
            'INVARIANT_MISCLASSIFIED',
            f'{len(misclassified)} verdict(s) claim a class the table does not '
            f'give them. A hard invariant relabelled DIAGNOSTIC would stop '
            f'gating, and a diagnostic relabelled HARD would start refusing '
            f'runs it was never meant to judge -- both silently.',
            offences=misclassified)
    missing = sorted(set(INVARIANTS) - set(seen))
    if missing:
        return Outcome.fail(
            'INVARIANT_VERDICT_MISSING',
            f'{missing} are declared invariants with no verdict in this '
            f'artifact. Silence is not one of the permitted answers: an '
            f'invariant that did not run has not been satisfied.',
            missing=missing)
    failed = [seen[k] for k in HARD_INVARIANTS
              if seen[k]['state'] in HARD_REFUSING_STATES]
    if failed:
        return Outcome.fail(
            'HARD_INVARIANT_FAILED',
            f'{len(failed)} hard invariant(s) did not hold: '
            + '; '.join(f'{v["invariant"]}={v["state"]}[{v["code"]}]'
                        for v in failed)
            + '. A forecast whose own accounting does not hold may not be '
              'sealed as valid, whatever else in the run succeeded.',
            offences=failed)
    owed = [k for k in HARD_INVARIANTS if seen[k]['state'] == 'DEFERRED']
    diag = [k for k in DIAGNOSTIC_INVARIANTS
            if seen[k]['state'] in ('FAIL', 'BLOCKED')]
    return Outcome.ok(
        'HARD_INVARIANTS_HOLD',
        value={'n_hard': len(HARD_INVARIANTS),
               'n_diagnostic': len(DIAGNOSTIC_INVARIANTS),
               'hard_owed': owed, 'diagnostics_not_clean': diag},
        detail=f'{len(HARD_INVARIANTS)} hard invariant(s) hold'
               + (f'; {len(owed)} carried as OWED: {owed}' if owed else '')
               + (f'; {len(diag)} diagnostic(s) not clean (recorded, not '
                  f'gating): {diag}' if diag else ''),
        hard_owed=owed, diagnostics_not_clean=diag)


def _p(ts):
    d = _dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def validate(art: dict) -> Outcome:
    """Every gate the contract declares. No silent defaults anywhere."""
    missing = [f for f in REQUIRED if f not in art or art[f] in (None, '', [])]
    if missing:
        return Outcome.fail(
            'ARTIFACT_INCOMPLETE',
            f'missing {missing}. A forecast artifact that omits a required '
            f'field cannot be evaluated later, and filling it in afterwards '
            f'would be exactly the backfill this contract exists to prevent.',
            missing=missing)
    if art['contract_version'] != CONTRACT_VERSION:
        return Outcome.fail('CONTRACT_VERSION_MISMATCH',
                            f'{art["contract_version"]!r} != {CONTRACT_VERSION!r}')
    if art['model_arm'] not in ARMS:
        return Outcome.fail(
            'UNKNOWN_ARM', f'{art["model_arm"]!r} is not an A/B/C arm. An '
            f'unlabelled forecast cannot be kept out of the wrong pool.')
    if art['completeness'] not in COMPLETENESS:
        return Outcome.fail('UNKNOWN_COMPLETENESS',
                            f'{art["completeness"]!r} not in {COMPLETENESS}')

    caps = art['source_captures']
    if not isinstance(caps, list) or not caps:
        return Outcome.fail('NO_SOURCE_CAPTURES',
                            'a forecast with no named input captures cannot be '
                            'reproduced or audited.')
    for c in caps:
        if not c.get('sha256') or not c.get('retrieved_at') or not c.get('source'):
            return Outcome.fail(
                'CAPTURE_WITHOUT_EVIDENCE',
                f'a source capture is missing source/sha256/retrieved_at: '
                f'{c!r}. A hash-free input is an unverifiable input.')

    try:
        wrote, kick = _p(art['written_at']), _p(art['kickoff_utc'])
        gots = [_p(c['retrieved_at']) for c in caps]
    except (ValueError, TypeError) as exc:
        return Outcome.fail('CLOCK_UNPARSEABLE', str(exc))

    if not wrote < kick:
        return Outcome.fail(
            'WRITTEN_AFTER_KICKOFF',
            f'written_at {art["written_at"]} is not before kickoff '
            f'{art["kickoff_utc"]}. A forecast written at or after kickoff is '
            f'not a forecast.', written_at=str(wrote), kickoff=str(kick))
    late = [c['source'] for c, g in zip(caps, gots) if g > wrote]
    if late:
        return Outcome.fail(
            'INPUT_RETRIEVED_AFTER_FORECAST',
            f'{late} were retrieved AFTER written_at. The forecast could not '
            f'have used them, so claiming them as inputs is false provenance.',
            sources=late)

    # ---- B13/B14: a MODEL-sourced artifact must carry its draws and its
    # accounting verdicts. Scoped to `distributions_source == "MODEL"` on
    # purpose: a fixture-sourced artifact is already stamped TEST_ONLY and is
    # not a forecast, so demanding model gates of it would say nothing.
    if art.get('distributions_source') == 'MODEL':
        if not art.get('draw_artifact_sha256'):
            return Outcome.fail(
                'MODEL_ARTIFACT_WITHOUT_DRAWS',
                'a model-sourced forecast artifact carries no '
                'draw_artifact_sha256. Four quantiles cannot produce a proper '
                'score, a PIT value, a tail probability or any dependence '
                'diagnostic, so an artifact that keeps only the summary has '
                'thrown the forecast away and kept a picture of it.')
        if not art.get('accounting_verdicts'):
            return Outcome.fail(
                'MODEL_ARTIFACT_WITHOUT_ACCOUNTING_VERDICTS',
                'a model-sourced forecast artifact records no accounting '
                'verdicts. Verdicts written as display strings and then '
                'ignored are how an artifact came to represent itself as valid '
                'while carrying FAIL on a hard invariant.')
    if art.get('accounting_verdicts'):
        g = assert_hard_invariants(art['accounting_verdicts'])
        if g.state is not State.PASS:
            return Outcome.fail(
                g.code, g.detail,
                **{k: v for k, v in dict(g.evidence).items() if k != 'owed'})

    return Outcome.ok(
        'ARTIFACT_VALID',
        value={'game_id': art['game_id'], 'arm': art['model_arm'],
               'written_at': art['written_at'], 'n_captures': len(caps)},
        detail=f'{art["game_id"]} arm {art["model_arm"]}: ordering holds, '
               f'{len(caps)} capture(s) hashed')


def artifact_id(art: dict) -> str:
    """Content hash over the fields that define the forecast."""
    payload = {k: art.get(k) for k in sorted(REQUIRED)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     default=str).encode()).hexdigest()


def assert_not_mutated(before: dict, after: dict) -> Outcome:
    """An artifact is immutable after written_at. A correction is a NEW one."""
    if artifact_id(before) == artifact_id(after):
        return Outcome.ok('ARTIFACT_UNCHANGED', value=artifact_id(after))
    if after.get('supersedes') == artifact_id(before) and \
            after.get('written_at') != before.get('written_at'):
        return Outcome.ok(
            'ARTIFACT_SUPERSEDED',
            value=artifact_id(after),
            detail='a NEW artifact that names the one it supersedes -- the '
                   'only lawful way to correct a forecast')
    return Outcome.fail(
        'ARTIFACT_MUTATED',
        'an artifact changed in place after written_at. A correction must be a '
        'NEW artifact carrying `supersedes` and its own written_at; editing '
        'the original destroys the only record of what was believed before '
        'the game.',
        before=artifact_id(before)[:16], after=artifact_id(after)[:16])


def assert_arms_not_pooled(artifacts: list) -> Outcome:
    """A and B and C may never be scored together."""
    arms = sorted({a.get('model_arm') for a in artifacts})
    if len(arms) > 1:
        return Outcome.fail(
            'ARMS_POOLED',
            f'a single evaluation set mixes arms {arms}. They carry different '
            f'evidentiary status -- A sees no 2026 outcome at all, C is '
            f'adaptive and weakest -- and pooling them produces a number that '
            f'describes none of them.', arms=arms)
    return Outcome.ok('SINGLE_ARM', value=arms[0] if arms else None)
