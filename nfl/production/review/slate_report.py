"""The saved slate review, and the gate that stops an unreviewed slate.

TWO THINGS LIVE HERE AND THEY ARE DIFFERENT

`write_report` produces the artifact: one JSON per slate plus one JSON per
player, on disk, so that three weeks later the question "why did the model
have this guy at 14.8?" is answered by opening a file rather than by
reconstructing a run.

`assert_player_review_complete` is the PIPELINE GATE. It is the thing that
makes this stage mandatory rather than advisory. It returns FAIL when any
publishable player has no dossier, when any blocking conflict is unresolved,
or when the review read a different draw artifact from the one the optimizer
is about to consume. An optimizer that runs anyway is running on a slate
nobody looked at, which is the state this whole module exists to end.

WHAT COVERAGE MEANS HERE

Coverage is measured against the PUBLISHABLE population -- the players whose
numbers can actually reach a lineup -- and reported separately from the
universe count. 100% of the universe is not the claim and would be a weaker
one: the universe includes practice-squad players nobody will roster. The
claim that matters is that every number an optimizer can use has a dossier
behind it.
"""
from __future__ import annotations

import collections
import datetime as _dt
import hashlib
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import audit as AUD                     # noqa: E402
from nfl.production.review import dossier as DOS                   # noqa: E402
from nfl.production.review import escalation as ESC                # noqa: E402
from nfl.production.review import evidence as EV                   # noqa: E402
from nfl.production.review import gate as GATE                     # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'slate-review-report-1'

#: Where a slate's review lands. One directory per slate key, never
#: overwritten in place by a different run -- the run_id is part of the key.
REVIEW_ROOT = 'nfl/research/player_review'


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def build_report(*, slate_key: str, dossiers: Sequence[Any],
                 audit_result: Dict[str, Any],
                 escalation_result: Dict[str, Any],
                 projection_source: Optional[Dict[str, Any]] = None,
                 publishable_ids=None,
                 information_cut: Optional[str] = None,
                 notes: Optional[List[str]] = None) -> Dict[str, Any]:
    """The slate-level summary. Pure: builds a dict, writes nothing."""
    publishable = (None if publishable_ids is None else set(publishable_ids))
    have = {d.gsis_id for d in dossiers}
    missing = sorted((publishable - have)) if publishable is not None else []

    by_unc = collections.Counter(d.uncertainty_state for d in dossiers)
    by_team = collections.Counter(d.team for d in dossiers)
    verdicts = escalation_result.get('verdicts', [])

    covered = (len(have & publishable) if publishable is not None
               else len(have))
    denom = (len(publishable) if publishable is not None else len(have))

    return {
        'spec_version': SPEC_VERSION,
        'slate_key': slate_key,
        'built_at_utc': _now(),
        'information_cut': information_cut,
        'stage_order': ['raw evidence', 'player dossier',
                        'evidence reconciliation', 'role/opportunity state',
                        'projection', 'simulation', 'projection audit',
                        'optimizer'],
        'coverage': {
            'n_universe': len(dossiers),
            'n_with_projection': sum(1 for d in dossiers if d.projection),
            'n_publishable': (None if publishable is None
                              else len(publishable)),
            'n_publishable_with_dossier': covered,
            'publishable_coverage': (covered / denom) if denom else 0.0,
            'publishable_without_dossier': missing,
            'by_team': dict(by_team),
        },
        'uncertainty': {'by_state': dict(by_unc)},
        'audit': {k: v for k, v in audit_result.items() if k != 'conflicts'},
        'conflicts': audit_result.get('conflicts', []),
        'escalation': {
            'by_tier': escalation_result.get('by_tier'),
            'n_forced_by_blocking':
                escalation_result.get('n_forced_by_blocking'),
            'deep_research_capacity':
                escalation_result.get('deep_research_capacity'),
            'weight_provenance': escalation_result.get('weight_provenance'),
            'external_disagreement_quarantine':
                escalation_result.get('external_disagreement_quarantine'),
            'queue': [v.as_dict() for v in verdicts
                      if v.tier != ESC.AUTOMATED_ONLY],
        },
        'projection_source': projection_source or {},
        'unavailable_evidence': {k: v for k, v
                                 in sorted(EV.UNAVAILABLE_SOURCES.items())},
        'notes': notes or [],
    }


def write_report(report: Dict[str, Any],
                 dossiers: Sequence[Any], *,
                 root: Optional[str] = None) -> Outcome:
    """Write the slate report and one dossier file per player.

    Refuses to report success on an empty write, and digests every file it
    produces so a later reader can prove the artifact has not moved.
    """
    if not dossiers:
        return Outcome.blocked(
            'NO_DOSSIERS_TO_WRITE',
            'writing an empty review would record that a slate was reviewed '
            'when it was not.', cause=Cause.DATA)

    base = pathlib.Path(root or (_REPO / REVIEW_ROOT))
    slate_dir = base / report['slate_key']
    pdir = slate_dir / 'player_dossiers'
    pdir.mkdir(parents=True, exist_ok=True)

    written: Dict[str, str] = {}
    for d in dossiers:
        p = pdir / f'{d.gsis_id or "UNKNOWN"}.json'
        body = json.dumps(d.as_dict(), indent=1, sort_keys=True,
                          default=str).encode()
        p.write_bytes(body)
        written[str(p.relative_to(base))] = hashlib.sha256(body).hexdigest()

    report = dict(report)
    report['player_files'] = written
    rp = slate_dir / 'slate_review_report.json'
    body = json.dumps(report, indent=1, sort_keys=True, default=str).encode()
    rp.write_bytes(body)

    n_on_disk = len(list(pdir.glob('*.json')))
    if n_on_disk != len(dossiers):
        return Outcome.fail(
            'DOSSIER_WRITE_COUNT_MISMATCH',
            f'{len(dossiers)} dossiers were built but {n_on_disk} files are '
            f'on disk at {pdir}. A partial write read as success is the '
            f'defect class this project pays for most.',
            value={'built': len(dossiers), 'on_disk': n_on_disk})

    return Outcome.ok(
        'SLATE_REVIEW_WRITTEN',
        {'report_path': str(rp), 'players_dir': str(pdir),
         'n_player_files': n_on_disk,
         'report_sha256': hashlib.sha256(body).hexdigest(),
         'player_file_digests': written},
        detail=f'{n_on_disk} player dossiers + slate report at {rp}')


def assert_player_review_complete(report: Dict[str, Any], *,
                                  publishable_ids=None,
                                  consumed_draw_digest: Optional[str] = None,
                                  resolved_conflict_codes=None) -> Outcome:
    """THE GATE. No slate reaches an optimizer without passing this.

    `resolved_conflict_codes` is how a human clears a blocking conflict: by
    naming it, in the run, on the record. There is no argument that clears
    them all at once, because "ignore the audit" should cost more keystrokes
    than reading it.
    """
    resolved = set(resolved_conflict_codes or ())
    cov = report.get('coverage', {})
    missing = list(cov.get('publishable_without_dossier') or [])
    if publishable_ids is not None:
        # Re-derive rather than trust the stored number: a report that says
        # it covered everyone is exactly the artifact worth re-checking.
        want = set(publishable_ids)
        have = {k.split('/')[-1].removesuffix('.json')
                for k in (report.get('player_files') or {})
                if k.startswith('player_dossiers/')}
        if have:
            missing = sorted(want - have)

    if missing:
        return Outcome.fail(
            'PLAYER_REVIEW_INCOMPLETE',
            f'{len(missing)} publishable player(s) have no dossier: '
            f'{missing[:8]}{"..." if len(missing) > 8 else ""}. Every number '
            f'an optimizer can use must have a reviewed dossier behind it.',
            value={'missing': missing})

    blocking = [c for c in report.get('conflicts', [])
                if c.get('severity') == AUD.BLOCKING
                and c.get('code') not in resolved]
    if blocking:
        return Outcome.fail(
            'PLAYER_REVIEW_BLOCKING_CONFLICTS_UNRESOLVED',
            f'{len(blocking)} blocking conflict(s) remain unresolved: '
            f'{sorted({c["code"] for c in blocking})}. Each must be fixed or '
            f'named in resolved_conflict_codes with a reason on the record.',
            value={'blocking': blocking[:20],
                   'codes': sorted({c['code'] for c in blocking})})

    if consumed_draw_digest is not None:
        digests = (report.get('projection_source') or {}).get('digests') or {}
        reviewed = digests.get('player_draws.npz')
        if reviewed is None:
            return Outcome.blocked(
                'REVIEWED_ARTIFACT_NOT_DIGESTED',
                'the report does not record which draw artifact it reviewed, '
                'so it cannot be shown to be the one about to be consumed.',
                cause=Cause.DATA)
        if reviewed != consumed_draw_digest:
            return Outcome.fail(
                'REVIEW_READ_A_DIFFERENT_ARTIFACT',
                f'the review read draws {reviewed[:16]}... and the optimizer '
                f'is about to consume {consumed_draw_digest[:16]}.... A '
                f'review of a different run is not a review of this one.',
                value={'reviewed': reviewed,
                       'consumed': consumed_draw_digest})

    return Outcome.ok(
        'PLAYER_REVIEW_COMPLETE',
        {'n_universe': cov.get('n_universe'),
         'n_publishable': cov.get('n_publishable'),
         'publishable_coverage': cov.get('publishable_coverage'),
         'n_conflicts': len(report.get('conflicts', [])),
         'n_blocking_resolved_by_name': sorted(resolved),
         'deep_research_queue':
             len([v for v in (report.get('escalation', {}).get('queue') or [])
                  if v.get('tier') == ESC.DEEP_RESEARCH])},
        detail=f'{cov.get("n_universe")} dossiers, coverage '
               f'{cov.get("publishable_coverage"):.4f} of the publishable '
               f'population, no unresolved blocking conflict')


def review_slate(*, slate_key: str, universe_rows, role_rows=(),
                 snap_rows=(), usage_rows=(), draws_dir=None,
                 inactive_ids=None, vacated=None, publishable_ids=None,
                 information_cut=None, deep_research_capacity: int = 12,
                 standard_review_capacity: Optional[int] = None,
                 external_disagreement=None, root=None,
                 optimizer_pool_ids=None, resolved_conflict_codes=None,
                 notes=None) -> Outcome:
    """The whole stage, end to end, in the fixed order. One call per slate.

    Returns the report, the gate outcome and the paths written. Any stage
    that refuses stops the chain and its own Outcome is returned, so a caller
    never receives a half-built review that looks complete.
    """
    projection = None
    if draws_dir is not None:
        po = DOS.read_projection(draws_dir)
        if po.state.name != 'PASS':
            return po
        projection = po.value

    do = DOS.build_dossiers(
        universe_rows=universe_rows, role_rows=role_rows, snap_rows=snap_rows,
        usage_rows=usage_rows, projection=projection,
        inactive_ids=inactive_ids, vacated=vacated,
        information_cut=information_cut)
    if do.state.name != 'PASS':
        return do
    dossiers = do.value['dossiers']

    ao = AUD.audit(dossiers, publishable_ids=publishable_ids)
    audit_result = ao.value if ao.state.name == 'PASS' else ao.evidence.get(
        'value', {})
    if not audit_result:
        return ao

    eo = ESC.escalate(dossiers, audit_result,
                      deep_research_capacity=deep_research_capacity,
                      standard_review_capacity=standard_review_capacity,
                      external_disagreement=external_disagreement)
    if eo.state.name != 'PASS':
        return eo

    for d in dossiers:
        d.conflicts = [c for c in audit_result.get('conflicts', [])
                       if c.get('gsis_id') == d.gsis_id]

    report = build_report(
        slate_key=slate_key, dossiers=dossiers, audit_result=audit_result,
        escalation_result=eo.value,
        projection_source={'run_id': (projection or {}).get('run_id'),
                           'digests': (projection or {}).get('digests'),
                           'n_draws': (projection or {}).get('n_draws'),
                           'metrics_absent':
                               (projection or {}).get('metrics_absent')},
        publishable_ids=publishable_ids, information_cut=information_cut,
        notes=notes)

    wo = write_report(report, dossiers, root=root)
    if wo.state.name != 'PASS':
        return wo
    report['player_files'] = wo.value['player_file_digests']

    # THE GATE RUNS HERE, inside the stage, so a caller cannot obtain a
    # review without also obtaining its verdict. A review whose verdict is
    # optional is a report, and a report does not stop anything.
    consumed = ((projection or {}).get('digests') or {}).get(
        'player_draws.npz')
    gate_o = GATE.evaluate(report, dossiers=dossiers,
                           projection_digest=consumed,
                           optimizer_pool_ids=optimizer_pool_ids,
                           resolved_conflict_codes=resolved_conflict_codes)
    gate_v = gate_o.value or gate_o.evidence.get('value') or {
        'verdict': GATE.BLOCKED, 'refusal_code': gate_o.code,
        'refusal_detail': gate_o.detail, 'spec_version': GATE.SPEC_VERSION}
    slate_dir = pathlib.Path(root or (_REPO / REVIEW_ROOT)) / slate_key
    gw = GATE.write_gate(gate_v, slate_dir / 'review_gate.json')
    if gw.state.name != 'PASS':
        return gw
    ap = slate_dir / 'projection_audit.json'
    ap.write_bytes(json.dumps(
        {'spec_version': AUD.SPEC_VERSION, 'slate_key': slate_key,
         'audit_state': ao.state.name, 'audit_code': ao.code,
         **audit_result}, indent=1, sort_keys=True, default=str).encode())

    complete = assert_player_review_complete(
        report, publishable_ids=publishable_ids)
    return Outcome.ok(
        'SLATE_REVIEWED',
        {'report': report, 'dossiers': dossiers, 'gate': gate_v,
         'audit_state': ao.state.name, 'audit_code': ao.code,
         'verdict': gate_v.get('verdict'),
         'gate_state': gate_o.state.name, 'gate_code': gate_o.code,
         'completeness_state': complete.state.name,
         'completeness_code': complete.code,
         'written': {**{k: v for k, v in wo.value.items()
                        if k != 'player_file_digests'},
                     'gate_path': gw.value['path'],
                     'gate_sha256': gw.value['sha256'],
                     'audit_path': str(ap)}},
        detail=f'{len(dossiers)} dossiers; audit {ao.code}; '
               f'verdict {gate_v.get("verdict")}')
