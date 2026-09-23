"""Simulation artifact invariants. Owned by the artifact, not by the gate.

Two invariants, both about the ROW AXIS of a player-draw artifact:

  MISSING_ROW_IDS         a layer that carries draws but cannot say whose
  SIMULATION_ROW_MISMATCH a layer whose row_ids and whose array disagree
                          about how many players there are

Both are about the npz and its manifest, so they belong beside them. The
second is the more dangerous: a row axis off by one attributes every
player's draws to somebody else, and every number downstream stays perfectly
self-consistent while being about the wrong person. `dossier.read_projection`
already refuses on it for the metrics IT reads; this producer checks EVERY
layer in the manifest, including ones no dossier consumes, and reports rather
than raising so a governance layer can weigh it.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Dict, Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.integrity import contract as IC                   # noqa: E402

SPEC_VERSION = 'nfl-simulation-integrity-0'
PRODUCER_ROWS = 'simulation_integrity.missing_row_ids'
PRODUCER_MISMATCH = 'simulation_integrity.simulation_row_mismatch'
C_MISSING_ROW_IDS = 'MISSING_ROW_IDS'
C_SIM_ROW_MISMATCH = 'SIMULATION_ROW_MISMATCH'


def _rows_for(layer: str, manifest: Dict[str, Any],
              arrays: Dict[str, Any]) -> Optional[int]:
    """How many rows the stored arrays actually have for a layer.

    The manifest spells a metric `layer/metric`; the npz stores it
    `layer__metric`. Both spellings are accepted because a reader that knew
    only one of them would report a clean artifact as broken.
    """
    for k, a in arrays.items():
        base = k.split('/', 1)[0] if '/' in k else k.split('__', 1)[0]
        if base == layer and getattr(a, 'shape', None):
            return int(a.shape[0])
    return None


def missing_row_ids(manifest: Dict[str, Any], *, slate_key: str = None,
                    information_cut: str = None,
                    source_artifacts: Dict[str, str] = None
                    ) -> IC.IntegrityReport:
    """Every layer that carries draws must say whose draws they are."""
    layers = (manifest or {}).get('layers') or {}
    if not layers:
        return IC.not_applicable(
            C_MISSING_ROW_IDS, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_ROWS, version=SPEC_VERSION,
            why='the manifest declares no layers, so there is no row axis to '
                'check. An artifact with no layers is a different failure '
                'and is not this invariant.',
            n_layers_declared=0,
            manifest_keys=sorted((manifest or {}).keys()))
    findings = []
    for name in sorted(layers):
        ids = (layers[name] or {}).get('row_ids')
        if ids:
            continue
        findings.append(IC.IntegrityFinding(
            code=C_MISSING_ROW_IDS, subject=name, subject_kind='layer',
            severity=IC.BLOCKING, owner=IC.OWNER_SIMULATION,
            detail=f'layer {name!r} declares no row_ids, so its draws cannot '
                   f'be attributed to any player. Draws nobody can be '
                   f'attributed are not a projection.',
            producer=PRODUCER_ROWS, producer_version=SPEC_VERSION,
            evidence={'layer': name,
                      'row_ids': None if ids is None else list(ids)},
            source_artifacts=dict(source_artifacts or {}),
            information_cut=information_cut))
    return IC.finding_report(
        C_MISSING_ROW_IDS, owner=IC.OWNER_SIMULATION, producer=PRODUCER_ROWS,
        version=SPEC_VERSION, findings=findings, n_checked=len(layers),
        detail=f'{len(layers)} layer(s) checked for a row axis',
        source_artifacts=source_artifacts, information_cut=information_cut,
        slate_key=slate_key)


def simulation_row_mismatch(manifest: Dict[str, Any], arrays: Dict[str, Any],
                            *, slate_key: str = None,
                            information_cut: str = None,
                            source_artifacts: Dict[str, str] = None
                            ) -> IC.IntegrityReport:
    """A layer's row_ids and its stored arrays must agree on the count."""
    layers = (manifest or {}).get('layers') or {}
    if not layers or not arrays:
        return IC.not_applicable(
            C_SIM_ROW_MISMATCH, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_MISMATCH, version=SPEC_VERSION,
            why='no layers or no arrays were supplied, so there are no two '
                'things to disagree.',
            n_layers_declared=len(layers or {}),
            n_arrays_supplied=len(arrays or {}))
    findings, checked = [], 0
    for name in sorted(layers):
        ids = (layers[name] or {}).get('row_ids') or []
        rows = _rows_for(name, manifest, arrays)
        if rows is None or not ids:
            # A layer with no array here, or no ids, is the OTHER invariant's
            # business. Reporting it twice would double-count one defect.
            continue
        checked += 1
        if rows != len(ids):
            findings.append(IC.IntegrityFinding(
                code=C_SIM_ROW_MISMATCH, subject=name, subject_kind='layer',
                severity=IC.BLOCKING, owner=IC.OWNER_SIMULATION,
                detail=f'layer {name!r} names {len(ids)} row_ids and its '
                       f'arrays carry {rows} rows. A row axis that does not '
                       f'line up attributes one player\'s draws to another, '
                       f'and every number downstream stays perfectly '
                       f'self-consistent while being about the wrong person.',
                producer=PRODUCER_MISMATCH, producer_version=SPEC_VERSION,
                evidence={'layer': name, 'n_row_ids': len(ids),
                          'n_array_rows': rows},
                source_artifacts=dict(source_artifacts or {}),
                information_cut=information_cut))
    if not checked:
        return IC.not_applicable(
            C_SIM_ROW_MISMATCH, owner=IC.OWNER_SIMULATION,
            producer=PRODUCER_MISMATCH, version=SPEC_VERSION,
            why='no layer carried both a row axis and an array, so no pair '
                'could be compared.',
            n_layers_declared=len(layers or {}),
            layers_with_row_ids=sorted(
                n for n in (layers or {})
                if (layers[n] or {}).get('row_ids')),
            array_keys=sorted(arrays or {}))
    return IC.finding_report(
        C_SIM_ROW_MISMATCH, owner=IC.OWNER_SIMULATION,
        producer=PRODUCER_MISMATCH, version=SPEC_VERSION, findings=findings,
        n_checked=checked,
        detail=f'{checked} layer(s) with both a row axis and an array',
        source_artifacts=source_artifacts, information_cut=information_cut,
        slate_key=slate_key)
