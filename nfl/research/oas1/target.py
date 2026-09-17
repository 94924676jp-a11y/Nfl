"""The ONE module permitted to read `epa`, and only as the regression target.

`nfl/ingest/allowlist.py` names this module by its dotted path in
`OAS1_TARGET_MODULE`. Any other caller of `assert_oas1_epa_target` is refused
with `OAS1_EPA_TARGET_WRONG_CALLER`, including another OAS1 module. The
general quarantine is untouched: `assert_columns_allowed('pbp', ['epa'],
Purpose.FORECAST)` still returns `MODEL_DERIVED_COLUMN_ACCESS`.

WHAT THE TARGET IS, STATED SO A PROMOTION CLAIM INHERITS IT

`oas1_epa_target` is the `epa` column of the nflverse pbp release for a season,
as served at a recorded `retrieved_at`, with the file's sha256 recorded,
restricted to the kept rows of the OAS1 frame, and tagged with the
`fastrmodels` generation in effect.

It is a THIRD-PARTY MODEL OUTPUT whose fit design is UNKNOWN and whose values
are revisable without notice. The training window is established as ending in
2019, so no 2026 play influenced its parameters; whether the shipped artifact
is the leave-one-season-out model from the published calibration article or a
single all-seasons fit is not established anywhere this project could find.
Both facts travel in the artifact.

MODEL GENERATION IS `UNKNOWN` AND SAYS SO. The pbp CSV export carries no
`fastrmodels` version column -- checked against the 372-column header -- so
there is nothing to read. It is recorded as UNKNOWN rather than guessed from
a release date, because a guessed provenance field is worse than an absent
one: it looks like evidence.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.ingest import allowlist as AL                              # noqa: E402

SPEC_VERSION = 'oas1-epa-target-1'

#: This module's own dotted name, asserted against the allowlist's declaration
#: at import so a rename cannot silently move the exemption to a module the
#: ruling never named.
MODULE_NAME = 'nfl.research.oas1.target'
assert MODULE_NAME == AL.OAS1_TARGET_MODULE, (
    f'this module is {MODULE_NAME!r} and the allowlist authorises '
    f'{AL.OAS1_TARGET_MODULE!r}. A renamed module does not inherit an '
    f'exemption granted to a name.')

MODEL_GENERATION_UNKNOWN = (
    'UNKNOWN -- the pbp CSV export carries no fastrmodels version column. '
    'Recorded as unknown rather than inferred from a release date.')

PROVENANCE_CAVEAT = (
    'the target is a third-party model output. Its training window is '
    'established as ending in 2019, so no 2026 play influenced its '
    'parameters. Its FIT DESIGN is UNKNOWN: whether the shipped fastrmodels '
    'artifact is the published leave-one-season-out model or a single '
    'all-seasons fit is not established. Its values are documented as '
    'revisable -- models rebuilt in nflfastR 2.0.5, EPA fixes in 4.0.0, '
    '4.4.0 and 5.0.0 reaching back into past seasons, and NFL stat '
    'corrections Monday to Wednesday. Any promotion claim inherits this.')

CODE_OK = 'OAS1_TARGET_BUILT'
CODE_REFUSED = 'OAS1_TARGET_REFUSED'
CODE_NON_FINITE = 'OAS1_TARGET_NON_FINITE'
CODE_EMPTY = 'OAS1_TARGET_EMPTY'


def build(kept_rows, *, vintage_sha256: str) -> Outcome:
    """The target vector for the frame's kept rows, behind the exemption.

    The exemption is checked FIRST, before a single value is read, so a
    refusal happens before the quarantined column is touched at all.
    """
    gate = AL.assert_oas1_epa_target(
        ['epa'], caller_module=MODULE_NAME, vintage_sha256=vintage_sha256)
    if gate.state is not State.PASS:
        return Outcome.fail(
            CODE_REFUSED,
            f'the target-only exemption refused this read: '
            f'{gate.code}: {gate.detail}',
            cause=Cause.GOVERNANCE, gate_code=gate.code,
            gate_detail=gate.detail)
    if not kept_rows:
        return Outcome.fail(CODE_EMPTY, 'no kept rows were supplied')
    y = np.asarray([r['epa'] for r in kept_rows], dtype=np.float64)
    if not np.isfinite(y).all():
        n = int((~np.isfinite(y)).sum())
        return Outcome.fail(
            CODE_NON_FINITE,
            f'{n} of {y.size} target value(s) are not finite. The frame is '
            f'supposed to have excluded null epa already, so this is a defect '
            f'in the frame, not in the data.',
            cause=Cause.DATA, n_bad=n)
    ev = {'spec_version': SPEC_VERSION, 'target': 'oas1_epa_target',
          'source_column': 'epa', 'n': int(y.size),
          'mean': float(y.mean()), 'sd': float(y.std(ddof=1)),
          'min': float(y.min()), 'max': float(y.max()),
          'vintage_sha256': vintage_sha256,
          'model_generation': MODEL_GENERATION_UNKNOWN,
          'provenance_caveat': PROVENANCE_CAVEAT,
          'exemption': gate.code, 'used_as': 'REGRESSION TARGET ONLY',
          'feature_use': 'REFUSED -- see allowlist.assert_no_epa_in_features'}
    return Outcome.ok(CODE_OK, value=y,
                      detail=f'{y.size} target value(s), mean {y.mean():.4f}, '
                             f'sd {y.std(ddof=1):.4f}, vintage '
                             f'{vintage_sha256[:16]}',
                      **ev)
