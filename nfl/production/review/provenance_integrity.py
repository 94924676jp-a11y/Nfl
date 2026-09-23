"""Does a MEASURED claim rest on anything measured?

`UNAVAILABLE_EVIDENCE_CLAIMED_AS_MEASURED`, owned by the provenance layer
because it is a statement about EVIDENCE GRADES, not about football.

The invariant is narrow and it is the one worth having: a projection
component may not be published as MEASURED when not a single canonical
evidence axis behind that player is MEASURED. Grades are the whole basis on
which the gate halves its materiality thresholds and the audit raises
cold-start conflicts, so a component that calls itself MEASURED while
resting on nothing measured defeats both at once -- quietly, because
everything downstream reads the grade and nothing re-derives it.

IT READS `evidence_provenance`, WHICH IS SERIALISED. The check therefore
gives the same answer live and when a verdict is re-derived from a saved
artifact, which is the property the gate needs and the reason it is not
written against the live PlayerState reference.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Dict, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.integrity import contract as IC                   # noqa: E402
from nfl.production.review import evidence as EV                      # noqa: E402

SPEC_VERSION = 'nfl-provenance-integrity-0'
PRODUCER = 'review.provenance_integrity.unavailable_claimed_as_measured'
C_UNAVAILABLE_CLAIMED = 'UNAVAILABLE_EVIDENCE_CLAIMED_AS_MEASURED'


def unavailable_claimed_as_measured(dossiers: Sequence[Any], *,
                                    slate_key: str = None,
                                    information_cut: str = None,
                                    source_artifacts: Dict[str, str] = None
                                    ) -> IC.IntegrityReport:
    """A MEASURED component with no MEASURED canonical axis behind it."""
    usable = [d for d in dossiers if getattr(d, 'evidence_provenance', None)]
    if not usable:
        return IC.not_applicable(
            C_UNAVAILABLE_CLAIMED, owner=IC.OWNER_PROVENANCE,
            producer=PRODUCER, version=SPEC_VERSION,
            why=f'none of the {len(dossiers)} dossier(s) carries canonical '
                f'evidence provenance, so there is no grade to compare a '
                f'claim against. Reporting that as passing would be the hole '
                f'this producer exists to close.',
            n_dossiers_supplied=len(dossiers),
            n_with_evidence_provenance=len(usable))
    findings = []
    for d in usable:
        claimed = sorted(c for c, comp in d.projection.items()
                         if getattr(comp, 'grade', None) == EV.MEASURED)
        if not claimed:
            continue
        measured_axes = sorted(
            k for k, v in d.evidence_provenance.items()
            if isinstance(v, dict) and v.get('grade') == EV.MEASURED)
        if measured_axes:
            continue
        grades = sorted({v.get('grade') for v in
                         d.evidence_provenance.values()
                         if isinstance(v, dict) and v.get('grade')})
        findings.append(IC.IntegrityFinding(
            code=C_UNAVAILABLE_CLAIMED, subject=d.gsis_id,
            subject_kind='player', severity=IC.BLOCKING,
            owner=IC.OWNER_PROVENANCE,
            detail=f'{len(claimed)} projection component(s) published as '
                   f'MEASURED for {d.display_name or d.gsis_id}, and NOT ONE '
                   f'canonical evidence axis behind him is MEASURED -- the '
                   f'grades present are {grades}. The gate halves its '
                   f'materiality thresholds on a non-measured row and the '
                   f'audit raises a cold-start conflict on one; a component '
                   f'that misreports its own grade defeats both at once.',
            producer=PRODUCER, producer_version=SPEC_VERSION,
            evidence={'components_claimed_measured': claimed,
                      'canonical_grades_present': grades,
                      'n_axes': len(d.evidence_provenance)},
            source_artifacts=dict(source_artifacts or {}),
            information_cut=information_cut))
    return IC.finding_report(
        C_UNAVAILABLE_CLAIMED, owner=IC.OWNER_PROVENANCE, producer=PRODUCER,
        version=SPEC_VERSION, findings=findings, n_checked=len(usable),
        detail=f'{len(usable)} dossier(s) with canonical provenance, of '
               f'{len(dossiers)} supplied',
        source_artifacts=source_artifacts, information_cut=information_cut,
        slate_key=slate_key)
