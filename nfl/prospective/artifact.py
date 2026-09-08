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

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

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

OPTIONAL = ('draw_artifact_sha256', 'cold_start_freeze_identity',
            'refusal_codes', 'supersedes')

COMPLETENESS = ('COMPLETE', 'PARTIAL_PLAYER_COVERAGE', 'REFUSED')


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
