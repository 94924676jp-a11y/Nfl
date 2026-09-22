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

#: DraftKings' OWN support documentation, supplied by the 2026-09-22 data
#: capability packet, which quotes each article directly.
#:
#: WHY THIS RAISES A CONFIDENCE LEVEL AND DOES NOT SETTLE ANYTHING.
#: A statement by the operator about its own product is a PROVIDER_CLAIM:
#: better than a practitioner's recollection, and still not something this
#: repository has observed. It becomes VERIFIED_PRIMARY only when we hold a
#: real export and the parser reads it. Until then a column spelling here is
#: documented, not confirmed, and `gamecenter.parse` still matches headers
#: rather than positions so that being wrong refuses by name.
KB0010448 = ('DraftKings support KB0010448, "How do I download a CSV to see '
             'GameCenter standings for a contest?", quoted in the 2026-09-22 '
             'data capability packet: '
             'https://support.draftkings.com/dk/en-us/how-do-i-download-a-'
             'csv-to-see-gamecenter-standings-for-a-contest'
             '?id=kb_article_view&sysparm_article=KB0010448')
KB0010720 = ('DraftKings support KB0010720, "How does DraftKings keep Fantasy '
             'Sports contests transparent?", quoted in the same packet: '
             'https://support.draftkings.com/dk/en-us/how-does-draftkings-'
             'keep-fantasy-sports-contests-transparent'
             '?id=kb_article_view&sysparm_article=KB0010720')
KB0010392 = ('DraftKings support KB0010392, "GameCenter - Overview", quoted '
             'in the same packet: '
             'https://support.draftkings.com/dk/en-us/gamecenter-overview'
             '?id=kb_article_view&sysparm_article=KB0010392')

DRAFTKINGS_GAMECENTER = SourceCapability('DRAFTKINGS', 'GAMECENTER')
(DRAFTKINGS_GAMECENTER
 .add('first_party', True, C.PROVIDER_CLAIM,
      'the export is served by the operator that ran the contest, so it is '
      'the operator\'s own record of its own contest. ' + KB0010720
      + ' -- DraftKings states customers can download CSV files for any '
      'Fantasy Sports contest, including ones they did not enter.')
 .add('complete_contest_field', True, C.PROVIDER_CLAIM,
      KB0010392 + ' -- GameCenter displays the top 500 entries plus the last '
      'entry of each payout tier, and the CSV is the complete record. '
      'STILL NOT VERIFIED HERE: no GameCenter export exists in this '
      'checkout, and completeness is established per artifact by '
      'store.assert_completeness against a field size the operator declared, '
      'never by this claim.')
 .add('per_athlete_ownership_published', True, C.PROVIDER_CLAIM,
      KB0010448 + ' -- the export carries an Athlete Information section '
      'with Player, Roster Position, %Drafted and FPTS. Not read first-hand '
      'here.')
 .add('retention_window_days', 10, C.PROVIDER_CLAIM,
      KB0010448 + ' -- "CSV downloads are available for 10 days after the '
      'contest ends". This is DraftKings stating it, not us observing it, '
      'and it is the whole reason this archive exists. Treat it as a '
      'deadline to beat rather than a guarantee: if the real window is ever '
      'shorter, the only thing protecting the data is having captured it '
      'earlier. PROCEDURE.md therefore asks for capture within 48 hours.')
 .add('entrant_lineups_available', True, C.PROVIDER_CLAIM,
      KB0010448 + ' -- the Contest Entrant Information section carries Rank, '
      'Entry ID, Entry Name (with an "(n)" multiple-entry suffix), '
      'TimeRemaining, Points and Lineup.')
 .add('athlete_id_column_present', C.UNKNOWN, C.UNKNOWN,
      'not established. The parser reads an athlete id where a column '
      'supplies one and records its absence otherwise; it never assumes one.')
 .add('salary_column_present', C.UNKNOWN, C.UNKNOWN,
      'not established. Salaries come from the SALARY_FILE artifact, which '
      'this repository HAS read first-hand; nothing here assumes the '
      'standings export repeats them.')
 .add('multiple_field_snapshots_available', True, C.PROVIDER_CLAIM,
      KB0010720 + ' -- a CSV cannot be downloaded until the contest locks; '
      'downloads taken while it is live are "frozen in time with current '
      'in-game stats"; and official scoring validation "will provide a '
      'completed CSV file". So the operator describes at least two obtainable '
      'snapshots of one contest, which is what POST_INITIAL_LOCK / '
      'INTERMEDIATE / FINAL exist to distinguish. WHAT IS STILL UNKNOWN is '
      'whether a live download reflects the field as it stood at initial '
      'lock or as it stands at the moment of download under late swap; a '
      'capture is therefore never labelled POST_INITIAL_LOCK by inference.')
 .add('payout_structure_in_standings_export', False, C.PROVIDER_CLAIM,
      KB0010448 + ' -- the two documented sections are Contest Entrant '
      'Information and Athlete Information. Neither carries entry fee, prize '
      'pool, payout table, max entries or field size, so all of it must be '
      'captured separately from the contest lobby AT THE TIME OF CAPTURE and '
      'stored beside the CSV. This is why PAYOUT_STRUCTURE and '
      'CONTEST_METADATA are their own artifact types and why '
      'DFSContestIdentity carries field_size: without them a capture is '
      'permanently COMPLETENESS_UNKNOWN and PayoutEV is not computable at '
      'all.')
 .add('licensing_for_internal_model_training', C.UNKNOWN, C.UNKNOWN,
      'not established. No model is trained on this data in this slice, so '
      'nothing currently depends on the answer -- but nothing may until it '
      'is answered.')
 .add('bulk_historical_extraction', False, C.PROVIDER_CLAIM,
      KB0010448 + ' -- exports are per contest, from desktop or mobile web '
      '(not the app), within the ten-day window. The window is precisely why '
      'older complete fields cannot be reconstructed from the operator at '
      'any later price.')
 .add('automated_acquisition_built', False, C.VERIFIED_PRIMARY,
      'read from this repository: no browser automation, scraping, session '
      'handling or unattended download exists, by instruction. Ingestion is '
      'manual.')
 .add('scripted_export_permitted', C.UNKNOWN, C.UNKNOWN,
      'NOT STATED in any DraftKings support article read by the 2026-09-22 '
      'packet, which routes the question to counsel. A practitioner note '
      'records a direct export URL pattern; its current validity and its '
      'permissibility are both UNKNOWN and it is deliberately not written '
      'down in this package. Owner ruling 2026-09-22: capture stays manual '
      'until this is resolved. UNKNOWN here does not mean "probably fine".')
 .add('export_size_or_rate_limit', C.UNKNOWN, C.UNKNOWN,
      'NOT STATED in any support article read, including for contests with '
      'six-figure fields. A capture of a very large contest may therefore '
      'fail or truncate in ways we cannot anticipate, which is a further '
      'reason store.assert_completeness compares entries held against the '
      'declared field size instead of trusting the file.'))

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
