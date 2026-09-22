"""What we claim this source can do, and how well we know it.

DELIBERATELY NARROW. This records ONLY the DraftKings GameCenter claims the
accepted research supports, at the confidence that research actually earns.
Broad NFL provider capabilities are NOT populated: a capability table filled
with plausible entries is worse than an empty one, because it reads like
evidence.

EVERY UNRESOLVED FIELD IS UNKNOWN. Not None, not absent, not an optimistic
default. UNKNOWN is a state somebody can act on; a missing key is not.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.history import contracts as C                           # noqa: E402

SPEC_VERSION = 'nfl-dfs-capability-0'


@dataclass(frozen=True)
class Claim:
    """One assertion about a source, with the evidence behind it."""
    subject: str
    value: Any
    confidence: str
    evidence: Optional[str] = None

    def __post_init__(self):
        if self.confidence not in C.CONFIDENCE:
            raise AssertionError(
                f'{self.confidence!r} is not one of {C.CONFIDENCE}. A claim '
                f'whose confidence is undeclared reads exactly like a '
                f'verified one.')

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class SourceCapability:
    provider: str
    surface: str
    sport: str = 'NFL'
    claims: Dict[str, Claim] = field(default_factory=dict)
    spec_version: str = SPEC_VERSION

    def add(self, subject: str, value: Any, confidence: str,
            evidence: str = None) -> 'SourceCapability':
        self.claims[subject] = Claim(subject, value, confidence, evidence)
        return self

    def unknowns(self):
        return tuple(sorted(k for k, v in self.claims.items()
                            if v.confidence == C.UNKNOWN))

    def at_least(self, confidence_levels) -> tuple:
        want = set(confidence_levels)
        return tuple(sorted(k for k, v in self.claims.items()
                            if v.confidence in want))

    def as_dict(self) -> Dict[str, Any]:
        return {'provider': self.provider, 'surface': self.surface,
                'sport': self.sport, 'spec_version': self.spec_version,
                'n_claims': len(self.claims),
                'n_unknown': len(self.unknowns()),
                'unknown_subjects': list(self.unknowns()),
                'claims': {k: v.as_dict()
                           for k, v in sorted(self.claims.items())}}


#: The accepted research for this workstream. Cited once, referenced by every
#: claim that rests on it, so a reader can find what a claim is standing on.
RESEARCH = ('accepted DFS-source research for this workstream, owner brief '
            '2026-09-22: DraftKings GameCenter exports as prospective '
            'first-party truth with an approximately ten-day retention '
            'window')

DRAFTKINGS_GAMECENTER = SourceCapability('DRAFTKINGS', 'GAMECENTER')
(DRAFTKINGS_GAMECENTER
 .add('first_party', True, C.PROVIDER_CLAIM,
      'the export is served by the operator that ran the contest, so it is '
      'the operator\'s own record of its own contest')
 .add('complete_contest_field', True, C.PRACTITIONER_REPORT,
      RESEARCH + '. NOT verified here: no GameCenter export exists in this '
      'checkout, and completeness is established per artifact by '
      'store.assert_completeness, never by this claim.')
 .add('per_athlete_ownership_published', True, C.PRACTITIONER_REPORT,
      RESEARCH + '; the `% Drafted` column. Not read first-hand here.')
 .add('retention_window_days', 10, C.PRACTITIONER_REPORT,
      RESEARCH + '. APPROXIMATE, and it is the whole reason this archive '
      'exists: it is treated as a floor to plan against, not a deadline to '
      'rely on.')
 .add('entrant_lineups_available', True, C.PRACTITIONER_REPORT,
      RESEARCH + '; the lineup column per entry row.')
 .add('athlete_id_column_present', C.UNKNOWN, C.UNKNOWN,
      'not established. The parser reads an athlete id where a column '
      'supplies one and records its absence otherwise; it never assumes one.')
 .add('salary_column_present', C.UNKNOWN, C.UNKNOWN,
      'not established. Salaries come from the SALARY_FILE artifact, which '
      'this repository HAS read first-hand; nothing here assumes the '
      'standings export repeats them.')
 .add('multiple_field_snapshots_available', C.UNKNOWN, C.UNKNOWN,
      'whether the operator serves a field as it stood BEFORE late swap is '
      'not established. The archive supports several snapshots per contest '
      'because it must not assume one immutable field, not because a second '
      'snapshot is known to be obtainable.')
 .add('payout_structure_in_standings_export', C.UNKNOWN, C.UNKNOWN,
      'not established; PAYOUT_STRUCTURE is a separate artifact type.')
 .add('licensing_for_internal_model_training', C.UNKNOWN, C.UNKNOWN,
      'not established. No model is trained on this data in this slice, so '
      'nothing currently depends on the answer -- but nothing may until it '
      'is answered.')
 .add('bulk_historical_extraction', False, C.PRACTITIONER_REPORT,
      RESEARCH + '. The retention window is precisely why older complete '
      'fields cannot be reconstructed from the operator.')
 .add('automated_acquisition_built', False, C.VERIFIED_PRIMARY,
      'read from this repository: no browser automation, scraping, session '
      'handling or unattended download exists, by instruction. Ingestion is '
      'manual.'))

#: Commercial historical backfill. A CANDIDATE, not an accepted source, and
#: it is recorded with nothing claimed so that nobody can mistake the entry
#: for an evaluation.
COMMERCIAL_BACKFILL = SourceCapability('UNEVALUATED_COMMERCIAL_VENDOR',
                                       'HISTORICAL_DFS_API')
for _subject in ('nfl_seasons_covered', 'complete_contest_fields',
                 'ownership_fields', 'salary_fields', 'payout_fields',
                 'contest_and_lineup_schema', 'stable_identifiers',
                 'timestamps', 'licensing_for_internal_model_training',
                 'local_raw_retention_rights', 'rate_limit',
                 'bulk_historical_extraction', 'pricing', 'trial_access',
                 'agreement_with_our_own_dk_first_party_export'):
    COMMERCIAL_BACKFILL.add(
        _subject, C.UNKNOWN, C.UNKNOWN,
        'no trial, no sample response and no schema has been inspected. '
        'This row exists to hold the question, not to answer it.')

SOURCES = {'DRAFTKINGS_GAMECENTER': DRAFTKINGS_GAMECENTER,
           'COMMERCIAL_BACKFILL': COMMERCIAL_BACKFILL}


def as_dict() -> Dict[str, Any]:
    return {'spec_version': SPEC_VERSION,
            'scope': 'DFS contest-environment sources only. These are NOT '
                     'football features and are not registered in the '
                     'FeatureRegistry.',
            'sources': {k: v.as_dict() for k, v in sorted(SOURCES.items())}}
