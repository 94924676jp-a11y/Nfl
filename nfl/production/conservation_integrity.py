"""Conservation and coherence, as integrity findings the gate can consume.

THE AUDIT THIS IMPLEMENTS. `nfl/research/integrity/CONSERVATION_OWNERSHIP.json`
established that OPPORTUNITY_CONSERVATION_FAILURE named two producers that do
not enforce the same invariant: one runs on deterministic shares BEFORE the
generator, the other on the published draw cells AFTER it, and either can pass
while the other fails. One integrity code cannot own both.

THREE CODES, THREE INVARIANTS, TWO OWNERS

  OPPORTUNITY_CONSERVATION_FAILURE      allocation   a club-room composition's
                                                     allocated shares do not
                                                     sum to one, or a club
                                                     carries negative
                                                     reassigned mass
  OPPORTUNITY_CONSUMER_OUT_OF_SCOPE     allocation   a downstream layer
                                                     intends to read a player
                                                     the composition does not
                                                     contain
  SIMULATION_DRAW_COHERENCE_VIOLATED    simulation   the final published draw
                                                     matrices contain a
                                                     football-impossible cell

THE OPEN QUESTION IS RULED. The audit left open whether
CONSUMER_READS_OUTSIDE_THE_COMPOSITION gets its own code. It does. It is a
SCOPE invariant -- does a downstream layer stay inside the set -- and folding
it into the conservation code would make one code mean two things, which is
the defect the audit exists to prevent. A room can conserve perfectly while
the consumer reads somebody who is not in it, and the two failures need
different repairs.

THESE PRODUCERS CONSUME STORED VERDICTS, THEY DO NOT RE-RUN THE CHECKS

`assert_draw_coherence` needs `shared_pass_live`, which `run_forecast` reads
from the run's applied-component list and which the draw manifest does NOT
record. Re-running the check here would mean guessing that flag, and guessing
False silently skips the team-closure component and returns a PASS that never
looked -- the false-green class this layer exists to end. So the producer
reads the verdict the run already stored WHOLE in `run_status.json` and
refuses to invent one.

AND A COHERENCE PASS IS WORTH NOTHING WITHOUT THE CERTIFICATE. Commit 8c81079
is titled "The guard ran, then the values it guarded were overwritten": the
failure is the gap between the check and the seal, not an absent check. So a
stored DRAW_COHERENCE_HOLDS whose `coherence_certificate_verdict` does not
verify is NOT_CHECKED here, not passing.

ABSENCE IS NEVER A PASS. Every producer returns NOT_CHECKED with a named
reason when the verdict it needs is not on the artifact. The gate treats an
advertised invariant that is NOT_CHECKED as blocking, which is the point.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Dict, List, Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.integrity import contract as IC                   # noqa: E402

SPEC_VERSION = 'nfl-conservation-integrity-0'

C_CONSERVATION = 'OPPORTUNITY_CONSERVATION_FAILURE'
C_CONSUMER_SCOPE = 'OPPORTUNITY_CONSUMER_OUT_OF_SCOPE'
C_DRAW_COHERENCE = 'SIMULATION_DRAW_COHERENCE_VIOLATED'

PRODUCER_CONSERVATION = 'conservation_integrity.allocation_conserves'
PRODUCER_SCOPE = 'conservation_integrity.consumer_within_composition'
PRODUCER_COHERENCE = 'conservation_integrity.draw_coherence'

#: Codes `assert_allocation_conserves` can return, and what each means here.
#: Listed so a code this module has never seen is treated as unrecognised
#: rather than quietly bucketed as fine.
ALLOC_CONSERVES = 'ALLOCATION_CONSERVES'
ALLOC_FAILS = 'ALLOCATION_DOES_NOT_CONSERVE'
ALLOC_SCOPE_FAILS = 'CONSUMER_READS_OUTSIDE_THE_COMPOSITION'
ALLOC_NO_CONSUMER = 'NO_CONSUMING_SET_DECLARED'

COHERENCE_HOLDS = 'DRAW_COHERENCE_HOLDS'
COHERENCE_VIOLATED = 'DRAW_COHERENCE_VIOLATED'
COHERENCE_NOT_EVALUABLE = 'DRAW_COHERENCE_NOT_EVALUABLE'
COHERENCE_VACUOUS = 'DRAW_COHERENCE_VACUOUS'

CERTIFICATE_VERIFIED = 'COHERENCE_CERTIFICATE_VERIFIED'


def _not_checked(code: str, *, owner: str, producer: str, why: str,
                 applicability: 'IC.Applicability' = None
                 ) -> IC.IntegrityReport:
    """A check that did not run has not passed. It is also not NOT_APPLICABLE:
    the invariant still applies, nobody evaluated it."""
    ap = applicability or IC.applicable_but_unchecked(why)
    return IC.IntegrityReport(coverage=[IC.InvariantCoverage(
        code=code, owner=owner, state=IC.NOT_CHECKED, producer=producer,
        producer_version=SPEC_VERSION, detail=why,
        applicability=IC.APPLICABLE_BUT_NOT_CHECKED,
        applicability_evidence=dict(ap.evidence))])


def _gates(chain: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per-room allocation gate verdicts out of a run_chain result."""
    layers = ((chain or {}).get('layers') or {})
    alloc = (layers.get('allocation') or {})
    out = {}
    for room, entry in alloc.items():
        g = (entry or {}).get('gate')
        if isinstance(g, dict) and g.get('code'):
            out[room] = g
    return out


# --------------------------------------------------------------------------
# 1. allocation conservation
# --------------------------------------------------------------------------
def allocation_conserves(chain: Optional[Dict[str, Any]] = None, *,
                         slate_key: str = None, information_cut: str = None,
                         source_artifacts: Dict[str, str] = None
                         ) -> IC.IntegrityReport:
    """Every club-room composition conserves the opportunity it allocates."""
    gates = _gates(chain)
    if not gates:
        return _not_checked(
            C_CONSERVATION, owner=IC.OWNER_ALLOCATION,
            producer=PRODUCER_CONSERVATION,
            why='no run_chain allocation gate verdict was supplied. '
                'assert_allocation_conserves runs in '
                'universe/run_chain.py, which is a SEPARATE entry point from '
                'run_forecast.py -- its verdict has no path into '
                'run_status.json, the artifact this gate re-derives from. '
                'Recomputing it here is not available either: the review '
                'layer does not hold the allocation rows. The invariant '
                'applies and nobody has evaluated it on this artifact.')
    findings: List[IC.IntegrityFinding] = []
    unrecognised = []
    for room, g in sorted(gates.items()):
        code = g.get('code')
        if code == ALLOC_FAILS:
            for off in (g.get('offending') or [{}]):
                findings.append(IC.IntegrityFinding(
                    code=C_CONSERVATION, subject=off.get('club') or room,
                    subject_kind='club_room', severity=IC.BLOCKING,
                    owner=IC.OWNER_ALLOCATION,
                    detail=f'{room}: club {off.get("club")} '
                           f'{off.get("kind")} -- a room whose shares do not '
                           f'sum to one has lost or invented opportunity, '
                           f'and every number derived from it inherits that.',
                    producer=PRODUCER_CONSERVATION,
                    producer_version=SPEC_VERSION,
                    evidence={'room': room, **{k: v for k, v in off.items()}},
                    source_artifacts=dict(source_artifacts or {}),
                    information_cut=information_cut))
        elif code in (ALLOC_CONSERVES, ALLOC_SCOPE_FAILS):
            # CONSUMER_READS_OUTSIDE means conservation PASSED and the
            # function went on to the scope check, which is the other
            # producer's business. Conservation held.
            continue
        elif code == ALLOC_NO_CONSUMER:
            # Conservation held; the function stopped before scope. Still a
            # pass for THIS invariant.
            continue
        else:
            unrecognised.append({'room': room, 'code': code})
    if unrecognised:
        return _not_checked(
            C_CONSERVATION, owner=IC.OWNER_ALLOCATION,
            producer=PRODUCER_CONSERVATION,
            why=f'the allocation gate returned code(s) this producer does '
                f'not recognise: {unrecognised}. An unrecognised verdict is '
                f'not evidence the invariant held; it is evidence the two '
                f'sides have drifted apart.')
    return IC.finding_report(
        C_CONSERVATION, owner=IC.OWNER_ALLOCATION,
        producer=PRODUCER_CONSERVATION, version=SPEC_VERSION,
        findings=findings, n_checked=len(gates),
        detail=f'{len(gates)} club-room composition gate(s) read; '
               f'{len(findings)} conservation violation(s)',
        source_artifacts=source_artifacts, information_cut=information_cut,
        slate_key=slate_key)


# --------------------------------------------------------------------------
# 2. consumer scope -- a DIFFERENT invariant, hence a different code
# --------------------------------------------------------------------------
def consumer_within_composition(chain: Optional[Dict[str, Any]] = None, *,
                                slate_key: str = None,
                                information_cut: str = None,
                                source_artifacts: Dict[str, str] = None
                                ) -> IC.IntegrityReport:
    """Nobody downstream reads a player the composition does not contain."""
    gates = _gates(chain)
    if not gates:
        return _not_checked(
            C_CONSUMER_SCOPE, owner=IC.OWNER_ALLOCATION,
            producer=PRODUCER_SCOPE,
            why='no run_chain allocation gate verdict was supplied; see '
                'OPPORTUNITY_CONSERVATION_FAILURE for why. This invariant is '
                'about SCOPE, not conservation: whether the layer that reads '
                'the composition stays inside it.')
    findings: List[IC.IntegrityFinding] = []
    short_circuited = []
    for room, g in sorted(gates.items()):
        code = g.get('code')
        if code == ALLOC_SCOPE_FAILS:
            for off in (g.get('offending') or [{}]):
                findings.append(IC.IntegrityFinding(
                    code=C_CONSUMER_SCOPE, subject=off.get('gsis_id'),
                    subject_kind='player', severity=IC.BLOCKING,
                    owner=IC.OWNER_ALLOCATION,
                    detail=f'{room}: the consumer intends to read '
                           f'{off.get("display_name") or off.get("gsis_id")}'
                           f', who carries no allocated share '
                           f'({off.get("allocation_state")}). The number '
                           f'comes from somewhere this layer did not put it.',
                    producer=PRODUCER_SCOPE, producer_version=SPEC_VERSION,
                    evidence={'room': room, **{k: v for k, v in off.items()}},
                    source_artifacts=dict(source_artifacts or {}),
                    information_cut=information_cut))
        elif code in (ALLOC_FAILS, ALLOC_NO_CONSUMER):
            # THE FUNCTION RETURNED BEFORE IT LOOKED. assert_allocation_
            # conserves evaluates conservation first and returns early on
            # failure, and with no consuming set it never reaches the scope
            # branch at all. Either way scope was NOT evaluated, and
            # reporting it as passing would be asserting a check that never
            # ran on the strength of a different check failing.
            short_circuited.append({'room': room, 'code': code})
    if short_circuited:
        return _not_checked(
            C_CONSUMER_SCOPE, owner=IC.OWNER_ALLOCATION,
            producer=PRODUCER_SCOPE,
            why=f'the allocation gate returned before evaluating scope in '
                f'{len(short_circuited)} room(s): {short_circuited}. '
                f'Conservation is checked first and returns early, and '
                f'NO_CONSUMING_SET_DECLARED never reaches the scope branch. '
                f'Scope was not evaluated on this run.')
    return IC.finding_report(
        C_CONSUMER_SCOPE, owner=IC.OWNER_ALLOCATION,
        producer=PRODUCER_SCOPE, version=SPEC_VERSION,
        findings=findings, n_checked=len(gates),
        detail=f'{len(gates)} club-room composition gate(s) read; '
               f'{len(findings)} out-of-scope consumer read(s)',
        source_artifacts=source_artifacts, information_cut=information_cut,
        slate_key=slate_key)


# --------------------------------------------------------------------------
# 3. draw coherence
# --------------------------------------------------------------------------
def simulation_applicability(manifest: Optional[Dict[str, Any]] = None, *,
                             simulation_artifact_declared: Optional[bool]
                             = None) -> IC.Applicability:
    """Does this governed artifact contain a simulation population at all?

    THE ONE RULE THAT MATTERS HERE. An artifact that CLAIMS to be an NFL
    simulation is APPLICABLE even if the layer the checker wanted is absent.
    A full simulation carrying no quarterback row is a DEFECTIVE simulation,
    not an artifact the coherence invariant does not apply to, and letting an
    absent array buy NOT_APPLICABLE is exactly how "the checker could not
    evaluate this" becomes "this passed".

    So NOT_APPLICABLE needs an explicit negative declaration from the caller
    -- `simulation_artifact_declared=False` -- AND a manifest that carries no
    draw layers to contradict it. Silence gives APPLICABLE, which fails
    closed.
    """
    layers = sorted((manifest or {}).get('layers') or {})
    if simulation_artifact_declared is False:
        if layers:
            return IC.applicable(
                'the caller declared no publishable simulation artifact, but '
                'the manifest carries draw layers, so one exists. The '
                'artifact contradicts the declaration and the artifact wins.',
                declared_simulation_artifact=False,
                layers_present=layers)
        return IC.inapplicable(
            'the caller declared that this governed artifact carries no '
            'publishable simulation population, and the manifest carries no '
            'draw layers to contradict it.',
            declared_simulation_artifact=False,
            layers_present=[],
            manifest_supplied=manifest is not None)
    return IC.applicable(
        f'the governed artifact carries {len(layers)} draw layer(s), so it '
        f'contains a simulation population this invariant is about'
        if layers else
        'no negative declaration was supplied, so the invariant is presumed '
        'to apply. An artifact that has not said it lacks a simulation '
        'population is not an artifact that lacks one.',
        layers_present=layers,
        declared_simulation_artifact=simulation_artifact_declared)


def draw_coherence(run_status: Optional[Dict[str, Any]] = None, *,
                   manifest: Optional[Dict[str, Any]] = None,
                   simulation_artifact_declared: Optional[bool] = None,
                   slate_key: str = None, information_cut: str = None,
                   source_artifacts: Dict[str, str] = None
                   ) -> IC.IntegrityReport:
    """No football-impossible cell survives into the published draws."""
    ap = simulation_applicability(
        manifest, simulation_artifact_declared=simulation_artifact_declared)
    if ap.state == IC.NOT_APPLICABLE:
        return IC.applicability_report(
            C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_COHERENCE, version=SPEC_VERSION,
            applicability=ap, n_checked=0,
            source_artifacts=source_artifacts,
            information_cut=information_cut, slate_key=slate_key)

    rs = run_status or {}
    dc = rs.get('draw_coherence')
    if not isinstance(dc, dict) or not dc.get('code'):
        return _not_checked(
            C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_COHERENCE,
            why='run_status.json carries no draw_coherence verdict, and this '
                'artifact contains a simulation population, so the invariant '
                'APPLIED AND NOBODY EVALUATED IT. The check is NOT re-run '
                'here: assert_draw_coherence requires shared_pass_live, '
                'which run_forecast reads from the run\'s applied-component '
                'list and which the draw manifest does not record. Guessing '
                'it False would skip team closure and return a PASS that '
                'never looked.',
            applicability=ap)

    code = dc.get('code')
    comps = dc.get('components') or {}

    # THE CERTIFICATE GATES THE PASS, NOT THE FAILURE.
    #
    # A violation found on the pre-publication arrays is a violation whatever
    # happened afterwards, so a FAIL is reported regardless. A PASS is only
    # worth something if the arrays it certified are the arrays that were
    # sealed -- otherwise the guard ran and the values it guarded were
    # replaced, which is a defect this repository has already shipped once.
    cert = rs.get('coherence_certificate_verdict') or {}
    cert_ok = cert.get('code') == CERTIFICATE_VERIFIED

    if code == COHERENCE_VIOLATED:
        findings = []
        for comp in (dc.get('failed') or sorted(
                k for k, v in comps.items()
                if (v or {}).get('state') == 'FAIL')) or ['<unnamed>']:
            v = comps.get(comp) or {}
            findings.append(IC.IntegrityFinding(
                code=C_DRAW_COHERENCE, subject=comp,
                subject_kind='draw_component', severity=IC.BLOCKING,
                owner=IC.OWNER_SIMULATION,
                detail=f'{comp}: {v.get("code")} -- the final published draw '
                       f'matrices contain a football-impossible cell. '
                       f'{dc.get("detail", "")[:200]}',
                producer=PRODUCER_COHERENCE, producer_version=SPEC_VERSION,
                evidence={'component': comp, 'code': v.get('code'),
                          'violations': v.get('violations'),
                          'cells_checked': v.get('cells_checked'),
                          'certificate_verified': cert_ok},
                source_artifacts=dict(source_artifacts or {}),
                information_cut=information_cut))
        return IC.finding_report(
            C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_COHERENCE, version=SPEC_VERSION,
            findings=findings, n_checked=len(comps),
            detail=f'{len(findings)} coherence component(s) violated on the '
                   f'published draws',
            source_artifacts=source_artifacts,
            information_cut=information_cut, slate_key=slate_key)

    if code in (COHERENCE_NOT_EVALUABLE, COHERENCE_VACUOUS):
        return _not_checked(
            C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_COHERENCE,
            why=f'the run stored {code}: '
                f'{str(dc.get("detail"))[:220]} A check that did not run has '
                f'not passed, and zero cells evaluated is an error rather '
                f'than a clean result.')

    if code == COHERENCE_HOLDS:
        if not cert_ok:
            return _not_checked(
                C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
                producer=PRODUCER_COHERENCE,
                why=f'coherence held on the arrays it examined, but the '
                    f'coherence certificate did not verify '
                    f'({cert.get("code") or cert.get("state") or "absent"}), '
                    f'so there is no evidence the certified arrays are the '
                    f'arrays that were published. A guard that ran before '
                    f'its values were overwritten has not guarded them.')
        return IC.finding_report(
            C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_COHERENCE, version=SPEC_VERSION,
            findings=[], n_checked=len(comps),
            detail=f'{len(comps)} coherence component(s) recorded and the '
                   f'certificate verifies the published arrays are the '
                   f'certified ones',
            source_artifacts=source_artifacts,
            information_cut=information_cut, slate_key=slate_key)

    return _not_checked(
        C_DRAW_COHERENCE, owner=IC.OWNER_SIMULATION,
        producer=PRODUCER_COHERENCE,
        why=f'run_status carries draw_coherence code {code!r}, which this '
            f'producer does not recognise. An unrecognised verdict is not '
            f'evidence the invariant held.')
