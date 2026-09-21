"""Contract validation. Every failure is NAMED; none is a boolean.

THE DEFECT THIS EXISTS TO KILL

`run_forecast._draws` returned `Outcome.ok('DRAWS_BUILT', ...)` carrying
`layers_absent=['receiving','rushing']` as EVIDENCE. The stage computed the
fact that its own required output was missing, attached it to a PASS, and
handed the artifact downstream. PHI@TEN then reached a delivery board with
four quarterbacks, two kickers and no skill position at all.

The information was never missing. It was captured and not acted on. So the
fix is not more evidence -- it is that the same computation now decides the
outcome instead of decorating it.

WHAT IS CHECKED HERE AND WHAT IS DELIBERATELY NOT

Checked: the artifact against its own CLASS contract and against its own
manifest. Required layer present; declared metric has bytes; row axis
non-empty; row ids unique; row count equals row-id count; draw width equals
the run's n_draws; values finite.

Not checked: whether BOTH clubs in a game got rows, whether every rostered
player was accounted for, whether a position room is plausible. Those need a
point-in-time roster and a club-level expectation, and they belong to the
coverage layer. Pulling them in here would make an artifact schema depend on
a roster file, and the schema would then move every time a roster did.

`draws_artifact.verify()` is NOT replaced. It checks the file against the
manifest -- per-array shape, per-array sha256, ragged width, file hash -- and
it stays exactly as it is. This module checks a level above it: the LAYER
declarations, which `verify()` never looked at.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.contracts.registry import get  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa

#: Every refusal this module can raise, named once so a caller can assert on
#: the name rather than on a substring of prose.
CODES = (
    'CONTRACT_DECLARED_LAYER_ABSENT',
    'CONTRACT_DECLARED_METRIC_BYTES_ABSENT',
    'CONTRACT_REQUIRED_ROW_AXIS_EMPTY',
    'CONTRACT_DUPLICATE_ROW_IDS',
    'CONTRACT_DRAW_VALUES_NOT_FINITE',
    'CONTRACT_ROW_COUNT_MISMATCH',
    'CONTRACT_DRAW_WIDTH_MISMATCH',
    'CONTRACT_ROW_AXIS_MISMATCH',
    'CONTRACT_UNDECLARED_EMPTY_OUTPUT',
    'CONTRACT_UNDECLARED_LAYER',
    'CONTRACT_MISSING_RUN_IDENTITY',
    'DECLARED_DRAW_ARTIFACT_INCOMPLETE',
)


def _arr(arrays, layer, metric):
    """The matrix for one layer/metric, under either spelling.

    The manifest spells a key `layer/metric`; the npz stores `layer__metric`.
    Both are tried because a reader that knows only one spelling reports a
    present array as absent, which is the same false negative one level down.
    """
    for k in (f'{layer}__{metric}', f'{layer}/{metric}'):
        if k in arrays:
            return arrays[k]
    return None


def validate_draw_manifest(manifest: dict, arrays=None,
                           contract_name: str = 'player_draws',
                           scope: str = 'football') -> Outcome:
    """A draw manifest (and optionally its arrays) against its class contract.

    `arrays` may be an npz, a dict of matrices, or None. With None the layer
    declarations are still checked -- which is enough to catch PHI@TEN, since
    there the layer was absent from the manifest itself.

    `scope` names the PRODUCT being certified. The default is `football`,
    because the football simulation is the thing that must be valid on its
    own: a DraftKings transform that did not run blocks a DK board and says
    nothing about the simulation underneath it. A DFS builder asks for
    `dfs_product` and gets the stricter answer. Whatever the scope, every
    PRESENT layer is checked for malformation -- an emitted layer with
    absent bytes, duplicate ids or non-finite values is broken in every
    scope.
    """
    c = get(contract_name)
    required = set(c.required_layers(scope))
    declared = manifest.get('layers') or {}
    offences, blocks_other_scope = [], []

    if c.requires_run_identity:
        for k in ('run_id', 'content_digest'):
            if not manifest.get(k):
                offences.append({
                    'code': 'CONTRACT_MISSING_RUN_IDENTITY', 'field': k,
                    'why': f'the artifact carries no {k}, so it cannot be '
                           f'traced to the run that produced it. The '
                           f'information cut is deliberately NOT checked '
                           f'here: this class records provenance by '
                           f'reference and the cut lives in '
                           f'run_status.json.'})

    n_draws = manifest.get('n_draws')
    known = {ls.name for ls in c.layers}
    for name in sorted(set(declared) - known):
        offences.append({
            'layer': name, 'code': 'CONTRACT_UNDECLARED_LAYER',
            'why': f'{name!r} is emitted but the {c.name} contract does not '
                   f'describe it, so no reader can know what it means or '
                   f'whether it is complete'})

    for ls in c.layers:
        lay = declared.get(ls.name)
        if lay is None:
            if ls.name in required:
                offences.append({
                    'layer': ls.name, 'scope': ls.scope,
                    'code': 'CONTRACT_DECLARED_LAYER_ABSENT',
                    'why': f'{ls.name!r} is required by the {c.name} '
                           f'contract for scope {scope!r} and is absent. '
                           f'Zero-row rule: {ls.zero_rows_legal_when}'})
            elif ls.required:
                # Required for a DIFFERENT product. Not an offence here, but
                # recorded so a caller can see which product it blocks
                # instead of discovering it downstream.
                blocks_other_scope.append({'layer': ls.name,
                                           'blocks_scope': ls.scope})
            continue

        axis = lay.get('row_axis')
        if axis and axis != ls.row_axis:
            offences.append({
                'layer': ls.name, 'code': 'CONTRACT_ROW_AXIS_MISMATCH',
                'why': f'rows are keyed on {axis!r}, contract says '
                       f'{ls.row_axis!r}'})

        ids = list(lay.get('row_ids') or [])
        if len(ids) < ls.min_rows:
            offences.append({
                'layer': ls.name,
                'code': ('CONTRACT_REQUIRED_ROW_AXIS_EMPTY' if not ids
                         else 'CONTRACT_UNDECLARED_EMPTY_OUTPUT'),
                'n_rows': len(ids), 'min_rows': ls.min_rows,
                'why': f'{len(ids)} row(s) against a declared minimum of '
                       f'{ls.min_rows}. Zero-row rule: '
                       f'{ls.zero_rows_legal_when}'})
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            offences.append({
                'layer': ls.name, 'code': 'CONTRACT_DUPLICATE_ROW_IDS',
                'ids': dupes[:10],
                'why': f'{len(dupes)} id(s) appear more than once on the row '
                       f'axis, so a row cannot be attributed to one player'})

        emitted_metrics = set(lay.get('metrics') or [])
        for m in ls.metrics:
            if m not in emitted_metrics:
                offences.append({
                    'layer': ls.name, 'metric': m,
                    'code': 'CONTRACT_DECLARED_METRIC_BYTES_ABSENT',
                    'why': f'{ls.name}/{m} is declared by the contract and '
                           f'the layer does not list it'})
                continue
            if arrays is None:
                continue
            a = _arr(arrays, ls.name, m)
            if a is None:
                offences.append({
                    'layer': ls.name, 'metric': m,
                    'code': 'CONTRACT_DECLARED_METRIC_BYTES_ABSENT',
                    'why': f'the manifest declares {ls.name}/{m} and the '
                           f'draw file carries no bytes for it'})
                continue
            a = np.asarray(a)
            if a.ndim != 2 or a.shape[0] != len(ids):
                offences.append({
                    'layer': ls.name, 'metric': m,
                    'code': 'CONTRACT_ROW_COUNT_MISMATCH',
                    'shape': list(a.shape), 'n_row_ids': len(ids),
                    'why': 'the matrix does not carry one row per row id, so '
                           'row i is not a known player'})
                continue
            if n_draws and int(a.shape[1]) != int(n_draws):
                offences.append({
                    'layer': ls.name, 'metric': m,
                    'code': 'CONTRACT_DRAW_WIDTH_MISMATCH',
                    'width': int(a.shape[1]), 'n_draws': int(n_draws),
                    'why': 'column j must mean the same simulated world in '
                           'every matrix; a different width means it does '
                           'not'})
                continue
            if not np.isfinite(np.asarray(a, dtype=float)).all():
                offences.append({
                    'layer': ls.name, 'metric': m,
                    'code': 'CONTRACT_DRAW_VALUES_NOT_FINITE',
                    'why': 'a non-finite draw cannot be counted, scored or '
                           'compared against a line'})

    if offences:
        codes = sorted({o['code'] for o in offences})
        return Outcome.fail(
            'DECLARED_DRAW_ARTIFACT_INCOMPLETE',
            f'{len(offences)} contract offence(s) against {c.name} '
            f'({c.schema_version}): {", ".join(codes)}. A stage may not '
            f'return PASS while its own output is incomplete.',
            contract=c.name, schema_version=c.schema_version, scope=scope,
            offence_codes=codes, offences=offences[:20],
            n_offences=len(offences), blocks_other_scope=blocks_other_scope)
    return Outcome.ok(
        'CONTRACT_SATISFIED',
        value={'contract': c.name, 'schema_version': c.schema_version,
               'scope': scope, 'layers_checked': sorted(declared),
               'required_layers': list(required),
               'blocks_other_scope': blocks_other_scope,
               'arrays_checked': arrays is not None},
        detail=f'{len(declared)} declared layer(s) satisfy {c.name} for '
               f'scope {scope!r}; every layer required by that scope is '
               f'present and every declared metric accounted for'
               + (f'. Absent layers blocking another product: '
                  f'{[b["layer"] for b in blocks_other_scope]}'
                  if blocks_other_scope else ''),
        scope=scope, blocks_other_scope=blocks_other_scope)


def validate_row_count(stage: str, n_rows: int, min_rows: int,
                       zero_rows_legal_when: str | None) -> Outcome:
    """The generic emptiness rule for a non-draw stage.

    A caller that passes `zero_rows_legal_when=None` is refused rather than
    defaulted: an undeclared emptiness rule is the defect, and defaulting it
    to "legal" or "illegal" would invent the stage's semantics on its behalf.
    """
    if not zero_rows_legal_when:
        return Outcome.fail(
            'CONTRACT_UNDECLARED_EMPTY_OUTPUT',
            f'{stage} returned {n_rows} row(s) and declares no '
            f'zero_rows_legal_when. Whether emptiness is a result or a '
            f'failure is a property of the stage and cannot be guessed here.',
            stage=stage, n_rows=n_rows, cause=Cause.GOVERNANCE)
    if n_rows < min_rows:
        return Outcome.fail(
            'CONTRACT_UNDECLARED_EMPTY_OUTPUT' if n_rows == 0
            else 'CONTRACT_ROW_COUNT_MISMATCH',
            f'{stage} returned {n_rows} row(s) against a declared minimum of '
            f'{min_rows}. Zero-row rule: {zero_rows_legal_when}',
            stage=stage, n_rows=n_rows, min_rows=min_rows)
    return Outcome.ok('ROW_COUNT_OK', value=n_rows, stage=stage)
