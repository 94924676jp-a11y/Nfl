"""Integrity findings, and the coverage that says whether anybody looked.

THE GOVERNANCE HOLE THIS CLOSES

`review/gate.py` declared eight integrity conflict codes as BLOCKING. All
eight had ZERO producers anywhere in the repository. They could only arrive
through the gate's `extra_conflicts` argument, which nothing in production
supplies. So the gate advertised guarantees -- no duplicate identities, no
row-axis mismatch, no forbidden external input -- that production never
evaluated, and a clean gate record meant only that nobody had checked.

ABSENCE OF A FINDING IS NOT A PASS. That is the whole point of this module.
A report carries COVERAGE as well as findings, and coverage distinguishes
four states that were previously all rendered as silence:

    CHECKED_AND_PASSING   a producer ran and found nothing
    CHECKED_AND_FAILING   a producer ran and found something
    NOT_CHECKED           no producer ran. NOT a pass.
    NOT_APPLICABLE        the invariant cannot apply to this run, with a
                          reason

THE GATE CONSUMES THIS. IT DOES NOT PRODUCE IT.

An integrity invariant belongs to the subsystem that owns the data it is
about. Duplicate canonical identity is the state layer's; a draw row axis is
the simulation artifact's; opportunity conservation is the allocation
layer's. Putting all eight inside the gate would make the governance layer a
second implementation of every subsystem it governs, which is the
fragmentation this whole migration exists to remove.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'nfl-integrity-contract-0'

BLOCKING, REVIEW, NOTE = 'BLOCKING', 'REVIEW', 'NOTE'
SEVERITIES = (BLOCKING, REVIEW, NOTE)

CHECKED_AND_PASSING = 'CHECKED_AND_PASSING'
CHECKED_AND_FAILING = 'CHECKED_AND_FAILING'
NOT_CHECKED = 'NOT_CHECKED'
NOT_APPLICABLE = 'NOT_APPLICABLE'
COVERAGE_STATES = (CHECKED_AND_PASSING, CHECKED_AND_FAILING, NOT_CHECKED,
                   NOT_APPLICABLE)

# --- owning subsystems ----------------------------------------------------
OWNER_STATE = 'canonical_state_identity'
OWNER_SIMULATION = 'simulation_artifact'
OWNER_ELIGIBILITY = 'dfs_eligibility_boundary'
OWNER_ALLOCATION = 'opportunity_allocation'
OWNER_PROVENANCE = 'feature_provenance_governance'


@dataclass(frozen=True)
class IntegrityFinding:
    """One violated invariant, attributable to a subject and a producer."""
    code: str
    subject: Optional[str]
    subject_kind: str
    severity: str
    owner: str
    detail: str
    producer: str
    producer_version: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    source_artifacts: Dict[str, str] = field(default_factory=dict)
    information_cut: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def as_conflict(self) -> Dict[str, Any]:
        """The shape the review gate already reads a conflict in.

        The gate's conflict row is the established interface between the
        audit and the gate, and an integrity finding is the same kind of
        object: a code, a subject, a severity and evidence. Reusing the shape
        means the gate does not grow a second classification path.
        """
        return {'code': self.code, 'severity': self.severity,
                'gsis_id': self.subject if self.subject_kind == 'player'
                else None,
                'display_name': self.subject,
                'team': None, 'detail': self.detail,
                'evidence': {**self.evidence, 'integrity_owner': self.owner,
                             'producer': self.producer,
                             'producer_version': self.producer_version,
                             'source_artifacts': self.source_artifacts},
                'integrity': True}


@dataclass(frozen=True)
class InvariantCoverage:
    """Whether anybody checked, and what they found. Never inferred."""
    code: str
    owner: str
    state: str
    producer: Optional[str] = None
    producer_version: Optional[str] = None
    n_subjects_checked: Optional[int] = None
    detail: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class IntegrityReport:
    """Findings plus the coverage that gives them meaning."""
    slate_key: Optional[str] = None
    information_cut: Optional[str] = None
    findings: List[IntegrityFinding] = field(default_factory=list)
    coverage: List[InvariantCoverage] = field(default_factory=list)
    source_artifacts: Dict[str, str] = field(default_factory=dict)
    spec_version: str = SPEC_VERSION

    # -- reading -----------------------------------------------------------
    def coverage_of(self, code: str) -> Optional[InvariantCoverage]:
        return next((c for c in self.coverage if c.code == code), None)

    def state_of(self, code: str) -> str:
        c = self.coverage_of(code)
        return c.state if c else NOT_CHECKED

    def codes_checked(self) -> Tuple[str, ...]:
        return tuple(sorted(c.code for c in self.coverage
                            if c.state in (CHECKED_AND_PASSING,
                                           CHECKED_AND_FAILING)))

    def producer_versions(self) -> Dict[str, str]:
        return {c.code: (c.producer_version or '')
                for c in sorted(self.coverage, key=lambda x: x.code)}

    def conflicts(self) -> List[Dict[str, Any]]:
        return [f.as_conflict() for f in self.findings]

    # -- identity ----------------------------------------------------------
    def body(self) -> Dict[str, Any]:
        return {
            'spec_version': self.spec_version,
            'slate_key': self.slate_key,
            'information_cut': self.information_cut,
            'source_artifacts': dict(sorted(self.source_artifacts.items())),
            'coverage': [c.as_dict() for c in
                         sorted(self.coverage, key=lambda x: x.code)],
            'findings': [f.as_dict() for f in
                         sorted(self.findings,
                                key=lambda x: (x.code, str(x.subject)))],
        }

    def report_hash(self) -> str:
        blob = json.dumps(self.body(), sort_keys=True,
                          separators=(',', ':'), default=str).encode()
        return 'IR-' + hashlib.sha256(blob).hexdigest()[:16]

    def as_dict(self) -> Dict[str, Any]:
        d = self.body()
        d['report_hash'] = self.report_hash()
        d['n_findings'] = len(self.findings)
        d['codes_checked'] = list(self.codes_checked())
        d['producer_versions'] = self.producer_versions()
        return d

    # -- composition -------------------------------------------------------
    @staticmethod
    def compose(parts: Sequence['IntegrityReport'], *,
                slate_key: str = None,
                information_cut: str = None) -> 'IntegrityReport':
        """Merge producer outputs. A code claimed twice is a defect.

        Two producers reporting coverage of the same invariant means two
        subsystems believe they own it, and the report would silently keep
        whichever came last. That is how a governance layer starts
        disagreeing with itself.
        """
        findings: List[IntegrityFinding] = []
        coverage: Dict[str, InvariantCoverage] = {}
        arts: Dict[str, str] = {}
        for p in parts:
            findings.extend(p.findings)
            arts.update(p.source_artifacts)
            for c in p.coverage:
                if c.code in coverage:
                    raise AssertionError(
                        f'{c.code} is claimed by two producers: '
                        f'{coverage[c.code].producer} and {c.producer}. One '
                        f'invariant, one owner.')
                coverage[c.code] = c
        return IntegrityReport(
            slate_key=slate_key or next(
                (p.slate_key for p in parts if p.slate_key), None),
            information_cut=information_cut or next(
                (p.information_cut for p in parts if p.information_cut), None),
            findings=findings, coverage=list(coverage.values()),
            source_artifacts=arts)


def finding_report(code: str, *, owner: str, producer: str, version: str,
                   findings: Sequence[IntegrityFinding],
                   n_checked: int, detail: str,
                   source_artifacts: Dict[str, str] = None,
                   information_cut: str = None,
                   slate_key: str = None) -> IntegrityReport:
    """One producer's result, with its coverage stated rather than implied."""
    state = CHECKED_AND_FAILING if findings else CHECKED_AND_PASSING
    return IntegrityReport(
        slate_key=slate_key, information_cut=information_cut,
        findings=list(findings),
        coverage=[InvariantCoverage(
            code=code, owner=owner, state=state, producer=producer,
            producer_version=version, n_subjects_checked=n_checked,
            detail=detail)],
        source_artifacts=dict(source_artifacts or {}))


def not_applicable(code: str, *, owner: str, producer: str, version: str,
                   why: str) -> IntegrityReport:
    """The invariant cannot apply to this run, and here is why."""
    return IntegrityReport(coverage=[InvariantCoverage(
        code=code, owner=owner, state=NOT_APPLICABLE, producer=producer,
        producer_version=version, detail=why)])
