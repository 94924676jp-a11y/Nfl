"""Typed contracts for archived DraftKings contest evidence.

WHY THIS EXISTS AND WHY NOW

The research accepted for this workstream reports that DraftKings' own
GameCenter contest exports -- the only first-party source of a COMPLETE
contest field with per-athlete ownership -- are retained for roughly ten
days after a contest completes. Everything we do not save inside that window
becomes history we cannot reconstruct from the operator, at any later price.

So this package is an ARCHIVE, not a model. It does not predict ownership,
does not simulate a field, does not price a lineup and does not touch a
football projection. Its whole job is that a contest file captured today is
still a verifiable research artifact years from now, without DraftKings
still hosting it.

RAW BYTES ARE AUTHORITATIVE

The operator's file as delivered is the source of record. It is hashed and
stored unchanged before anything parses it, and every derived table points
back at that hash. A parser improves; the bytes do not. This is the same
discipline `oddsclient` and `inactives` already follow -- write the bytes,
then interpret them -- and it exists because a parser change must never make
an earlier capture unrecoverable.

THERE MAY NOT BE ONE THING CALLED "ACTUAL OWNERSHIP"

An NFL Classic slate has late swap. The field an hour after initial lock is
not necessarily the field after the early games finish, which is not
necessarily the field at settlement. So an ownership number here is never a
bare float on a player; it is an OBSERVATION with a time and a snapshot
type. Nothing in this package infers late-swap behaviour -- it records what
was observed and when, and leaves the modelling question open.

NOTHING HERE IS A PREDICTIVE FEATURE

These artifacts are downstream DFS-environment evidence. They are not
registered in the FeatureRegistry, are not reachable from a projection, and
must not become one without a separate decision.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'nfl-dfs-history-contracts-0'

# --- how strongly a claim is supported ------------------------------------
#: We read it ourselves, in a primary artifact we hold.
VERIFIED_PRIMARY = 'VERIFIED_PRIMARY'
#: Two sources we hold agree.
VERIFIED_INDEPENDENTLY = 'VERIFIED_INDEPENDENTLY'
#: The provider says so, in its own documentation or marketing.
PROVIDER_CLAIM = 'PROVIDER_CLAIM'
#: A practitioner who uses the source reports it.
PRACTITIONER_REPORT = 'PRACTITIONER_REPORT'
#: Forums, social posts, aggregated hearsay.
COMMUNITY_REPORT = 'COMMUNITY_REPORT'
#: Nobody has established it either way. The DEFAULT.
UNKNOWN = 'UNKNOWN'
CONFIDENCE = (VERIFIED_PRIMARY, VERIFIED_INDEPENDENTLY, PROVIDER_CLAIM,
              PRACTITIONER_REPORT, COMMUNITY_REPORT, UNKNOWN)

# --- when a field was observed --------------------------------------------
#: Shortly after the slate's first games lock. Late swap has not happened.
POST_INITIAL_LOCK = 'POST_INITIAL_LOCK'
#: Somewhere between: early games done, later ones not yet locked.
INTERMEDIATE = 'INTERMEDIATE'
#: After settlement. Lineups can no longer change.
FINAL = 'FINAL'
#: Captured, but which of the three is not established.
SNAPSHOT_UNKNOWN = 'SNAPSHOT_UNKNOWN'
SNAPSHOTS = (POST_INITIAL_LOCK, INTERMEDIATE, FINAL, SNAPSHOT_UNKNOWN)

# --- what a captured file is ----------------------------------------------
SALARY_FILE = 'SALARY_FILE'
CONTEST_STANDINGS = 'CONTEST_STANDINGS'
CONTEST_METADATA = 'CONTEST_METADATA'
PAYOUT_STRUCTURE = 'PAYOUT_STRUCTURE'
ENTRY_FILE = 'ENTRY_FILE'
OTHER = 'OTHER'
ARTIFACT_TYPES = (SALARY_FILE, CONTEST_STANDINGS, CONTEST_METADATA,
                  PAYOUT_STRUCTURE, ENTRY_FILE, OTHER)

# --- whether the field we hold is the whole field --------------------------
#: Every entry the contest had is in this artifact, and that is ESTABLISHED.
COMPLETE = 'COMPLETE'
#: Entries are missing, or the count disagrees with the contest's own.
INCOMPLETE = 'INCOMPLETE'
#: We hold entries and cannot establish whether they are all of them.
COMPLETENESS_UNKNOWN = 'COMPLETENESS_UNKNOWN'
COMPLETENESS = (COMPLETE, INCOMPLETE, COMPLETENESS_UNKNOWN)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      default=str).encode()


@dataclass(frozen=True)
class DFSContestIdentity:
    """What contest this is, in the operator's own terms.

    NOTHING IS FABRICATED. A field the source did not supply stays None. A
    contest id we invented would look exactly like one DraftKings issued,
    and the whole point of an archive is that a reader years later can tell
    the difference.
    """
    provider: str = 'DRAFTKINGS'
    sport: str = 'NFL'
    contest_id: Optional[str] = None
    draft_group_id: Optional[str] = None
    contest_name: Optional[str] = None
    contest_type: Optional[str] = None      # GPP, DOUBLE_UP, ... as given
    slate_type: Optional[str] = None        # CLASSIC, SHOWDOWN, ... as given
    entry_limit: Optional[int] = None
    field_size: Optional[int] = None
    entry_fee: Optional[float] = None
    start_time_utc: Optional[str] = None
    season: Optional[int] = None
    week: Optional[int] = None

    @property
    def key(self) -> str:
        """A stable handle. Uses the operator's contest id when there is one
        and says so when there is not -- never a manufactured substitute."""
        if self.contest_id:
            return f'{self.provider}:{self.sport}:{self.contest_id}'
        return (f'{self.provider}:{self.sport}:NO_CONTEST_ID:'
                + sha256_bytes(_canon(self.as_dict()))[:16])

    @property
    def has_operator_id(self) -> bool:
        return bool(self.contest_id)

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class DFSRawArtifact:
    """One captured file, described well enough to be trusted later."""
    artifact_type: str
    provider: str
    contest: DFSContestIdentity
    retrieved_at: str
    raw_sha256: str
    original_filename: Optional[str] = None
    provider_timestamp: Optional[str] = None
    stored_path: Optional[str] = None
    n_bytes: Optional[int] = None
    schema_fingerprint: Optional[str] = None
    row_count: Optional[int] = None
    parser_version: Optional[str] = None
    snapshot_type: str = SNAPSHOT_UNKNOWN
    acquisition: str = 'MANUAL_OWNER_DOWNLOAD'
    confidence: str = UNKNOWN
    note: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d['contest'] = self.contest.as_dict()
        return d


@dataclass
class DFSContestManifest:
    """Everything captured for one contest, and what is still missing."""
    contest: DFSContestIdentity
    artifacts: List[DFSRawArtifact] = field(default_factory=list)
    information_cut: Optional[str] = None
    snapshot_type: str = SNAPSHOT_UNKNOWN
    completeness: str = COMPLETENESS_UNKNOWN
    completeness_why: Optional[str] = None
    spec_version: str = SPEC_VERSION
    notes: List[str] = field(default_factory=list)

    def of_type(self, artifact_type: str) -> List[DFSRawArtifact]:
        return [a for a in self.artifacts
                if a.artifact_type == artifact_type]

    def body(self) -> Dict[str, Any]:
        return {
            'spec_version': self.spec_version,
            'contest': self.contest.as_dict(),
            'contest_key': self.contest.key,
            'has_operator_contest_id': self.contest.has_operator_id,
            'information_cut': self.information_cut,
            'snapshot_type': self.snapshot_type,
            'completeness': self.completeness,
            'completeness_why': self.completeness_why,
            'artifacts': [a.as_dict() for a in
                          sorted(self.artifacts,
                                 key=lambda x: (x.artifact_type,
                                                x.raw_sha256))],
            'notes': list(self.notes),
        }

    def identity_body(self) -> Dict[str, Any]:
        """`body()` with every artifact's `stored_path` dropped.

        THE HASH MUST NOT KEY ON WHERE THE FILE SITS. `store.py` states the
        contract plainly -- "a directory can be reorganised without anything
        downstream noticing, and nothing may key on the path" -- and a
        manifest hash that moved when the archive was reorganised, or that
        differed between two machines holding the identical bytes, would
        break exactly the property this package exists to provide. What
        identifies a capture is the contest, the artifacts' sha256 digests
        and what we declared about them.

        `stored_path` stays in `body()` and in the file on disk, because a
        reader still has to find the bytes. It is a locator, not identity.
        """
        d = dict(self.body())
        d['artifacts'] = [{k: v for k, v in a.items() if k != 'stored_path'}
                          for a in d['artifacts']]
        return d

    def manifest_hash(self) -> str:
        return 'DFSM-' + sha256_bytes(_canon(self.identity_body()))[:16]

    def as_dict(self) -> Dict[str, Any]:
        d = self.body()
        d['manifest_hash'] = self.manifest_hash()
        d['n_artifacts'] = len(self.artifacts)
        d['artifact_types_present'] = sorted(
            {a.artifact_type for a in self.artifacts})
        return d


@dataclass(frozen=True)
class OwnershipObservation:
    """Ownership is never a bare number on a player.

    `observed_at` and `observation_type` are what make two numbers for the
    same athlete in the same contest comparable rather than contradictory.
    An NFL Classic slate has late swap, so a field observed after initial
    lock and a field observed at settlement are DIFFERENT POPULATIONS and
    the schema refuses to pretend otherwise.
    """
    contest_key: str
    athlete_name: str
    observed_at: str
    observation_type: str
    ownership: Optional[float]
    source: str                      # OPERATOR_PUBLISHED | DERIVED_FROM_FIELD
    denominator: Optional[int] = None
    roster_position: Optional[str] = None
    athlete_id: Optional[str] = None
    fantasy_points: Optional[float] = None
    derivation_version: Optional[str] = None
    completeness: str = COMPLETENESS_UNKNOWN
    raw_sha256: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


OPERATOR_PUBLISHED = 'OPERATOR_PUBLISHED'
DERIVED_FROM_FIELD = 'DERIVED_FROM_FIELD'


@dataclass(frozen=True)
class ContestEntry:
    """One entrant's row, in the source's own terms."""
    entry_id: Optional[str]
    entry_name: Optional[str]
    rank: Optional[int]
    points: Optional[float]
    lineup_raw: Optional[str]
    lineup_slots: Tuple[Tuple[str, str], ...] = ()   # (slot, athlete)
    time_remaining: Optional[str] = None
    snapshot_type: str = SNAPSHOT_UNKNOWN
    raw_sha256: Optional[str] = None

    @property
    def parsed(self) -> bool:
        return bool(self.lineup_slots)

    def as_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d['lineup_slots'] = [list(x) for x in self.lineup_slots]
        d['parsed'] = self.parsed
        return d


@dataclass(frozen=True)
class ContestAthleteSummary:
    """The operator's own per-athlete section, where the file carries one."""
    athlete_name: str
    roster_position: Optional[str] = None
    percent_drafted: Optional[float] = None
    fantasy_points: Optional[float] = None
    athlete_id: Optional[str] = None
    raw_sha256: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)
