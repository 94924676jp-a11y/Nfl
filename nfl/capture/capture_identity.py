"""Which implementation produced this capture row?

D24. Until now, nothing. A manifest row records what was fetched, when, and by
which executor -- and says nothing about the CODE that parsed it. So a repair
could land on the development branch, its test could pass there, and the
scheduled capture could go on running something else entirely, with no row
carrying the difference.

MEASURED 2026-09-15, and it is not "slightly older logic":

    nfl/capture/payload_contract.py        ABSENT ON main
    nfl/capture/persisted_provenance.py    ABSENT ON main
    nfl/capture/evidence_layers.py         ABSENT ON main
    nfl/tools/capture_vintage.py           differs
    nfl/capture/registry.py                differs
    nfl/capture/coverage.py                differs

`.github/workflows/nfl-capture.yml` uses `actions/checkout@v4` with NO `ref:`,
and a `schedule:` trigger checks out the DEFAULT branch. So every scheduled
capture runs main's copy, and every D20/D22/D24 repair is absent from the only
code that actually captures. A correct test on one branch coexisting with
defective capture on another is precisely the shape this module exists to make
impossible to miss.

WHAT THIS MODULE DOES. It computes a durable identity for the capture
implementation -- the contents of the files that decide what a capture MEANS --
so every row can prove which implementation produced it, and so a preflight can
refuse to capture with logic materially older than what was validated.

WHAT IT DOES NOT DO. It does not decide the deployment. Whether main should
carry this code, or the workflow should pin a ref, or the branches should
reconcile on a cadence, is an owner decision with tradeoffs this module cannot
weigh. It makes the drift VISIBLE and REFUSABLE; it does not pick the remedy.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]

SPEC_VERSION = 'capture_identity/1.0.0'

#: The files that determine what a capture MEANS -- what is fetched, what
#: counts as substance, what a verdict is, and what may discharge an
#: obligation. A change to any of them changes the semantics of every row
#: written afterwards, which is why they are hashed together rather than
#: individually: a partial upgrade is its own defect and should not look like
#: either endpoint.
CAPTURE_SURFACE = (
    'nfl/tools/capture_vintage.py',
    'nfl/capture/registry.py',
    'nfl/capture/payload_contract.py',
    'nfl/capture/evidence_layers.py',
    'nfl/capture/persisted_provenance.py',
    'nfl/capture/coverage.py',
)

#: Where the validated identity is recorded. Written deliberately by a human
#: or a governed step, never by a capture run -- a file the capture path could
#: update would certify itself.
CONTRACT = _REPO / 'nfl' / 'capture' / 'VALIDATED_CAPTURE_CONTRACT.json'


def file_sha(rel: str):
    """sha256 of one surface file, or None if it does not exist.

    ABSENT IS A VALUE, NOT A ZERO. A missing module hashed as the empty string
    is indistinguishable from an empty one, and on main three of these files
    ARE missing -- that is the finding, and it must not be flattened into a
    hash that merely differs.
    """
    p = _REPO / rel
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def surface() -> dict:
    """Per-file digest of the capture surface, absent files marked as such."""
    return {rel: file_sha(rel) for rel in CAPTURE_SURFACE}


def capture_code_sha(surf=None) -> str:
    """One digest over the whole surface, order-stable and absence-aware."""
    s = surface() if surf is None else surf
    parts = [f'{rel}:{s.get(rel) or "ABSENT"}' for rel in CAPTURE_SURFACE]
    parts.append(f'spec:{SPEC_VERSION}')
    return hashlib.sha256('\n'.join(parts).encode()).hexdigest()


def identity(source_contract_version=None, parser_version=None) -> dict:
    """The block every capture row should carry.

    `workflow_sha` and the executor fields come from the environment the run
    actually happened in; they are READ, never invented, and absent values stay
    None rather than being filled with a plausible default.
    """
    surf = surface()
    return {
        'spec_version': SPEC_VERSION,
        'capture_code_sha': capture_code_sha(surf),
        'capture_surface': surf,
        'n_surface_files_absent': sum(1 for v in surf.values() if v is None),
        'workflow_sha': os.environ.get('GITHUB_SHA'),
        'workflow_ref': os.environ.get('GITHUB_REF'),
        'workflow_name': os.environ.get('GITHUB_WORKFLOW'),
        'workflow_run_id': os.environ.get('GITHUB_RUN_ID'),
        'is_github_actions': os.environ.get('GITHUB_ACTIONS') == 'true',
        'parser_version': parser_version,
        'source_contract_version': source_contract_version,
    }


def validated() -> dict | None:
    """The contract this deployment is supposed to be running, or None."""
    if not CONTRACT.exists():
        return None
    return json.loads(CONTRACT.read_text())


def drift(validated_contract=None) -> dict:
    """How the running surface differs from the validated one.

    Returns a verdict, never a bare boolean: `MATCHES`, `NO_CONTRACT`,
    `SURFACE_FILES_ABSENT` (strictly worse than a mere difference), or
    `SURFACE_DIFFERS`.
    """
    v = validated() if validated_contract is None else validated_contract
    surf = surface()
    running = capture_code_sha(surf)
    if v is None:
        return {'verdict': 'NO_CONTRACT', 'running_capture_code_sha': running,
                'detail': 'no VALIDATED_CAPTURE_CONTRACT.json to compare '
                          'against, so drift cannot be measured -- which is '
                          'not the same as no drift'}
    want_surface = v.get('capture_surface') or {}
    absent = sorted(rel for rel, sha in surf.items()
                    if sha is None and want_surface.get(rel) is not None)
    differing = sorted(rel for rel, sha in surf.items()
                       if sha is not None
                       and want_surface.get(rel) is not None
                       and sha != want_surface[rel])
    if absent:
        return {'verdict': 'SURFACE_FILES_ABSENT',
                'running_capture_code_sha': running,
                'validated_capture_code_sha': v.get('capture_code_sha'),
                'absent': absent, 'differing': differing,
                'detail': f'{len(absent)} validated capture module(s) do not '
                          f'exist in the running tree: {absent}. This is not '
                          f'older logic, it is missing logic -- every check '
                          f'they perform is simply not happening.'}
    if differing or running != v.get('capture_code_sha'):
        return {'verdict': 'SURFACE_DIFFERS',
                'running_capture_code_sha': running,
                'validated_capture_code_sha': v.get('capture_code_sha'),
                'absent': [], 'differing': differing,
                'detail': f'{len(differing)} capture module(s) differ from the '
                          f'validated contract: {differing}'}
    return {'verdict': 'MATCHES', 'running_capture_code_sha': running,
            'validated_capture_code_sha': v.get('capture_code_sha'),
            'absent': [], 'differing': []}


def write_contract(path=None) -> dict:
    """Record the CURRENT surface as validated. Governed step, not a capture.

    Deliberately separate from `identity()` so that nothing on the capture path
    can call it: a capture run that could stamp its own code as validated would
    certify itself, which is the guard equivalent of marking your own homework.
    """
    surf = surface()
    doc = {'spec_version': SPEC_VERSION,
           'capture_code_sha': capture_code_sha(surf),
           'capture_surface': surf,
           'note': ('The capture implementation validated for production. '
                    'Written by a governed step, never by a capture run. A '
                    'running tree whose surface differs from this has not been '
                    'validated, whatever its tests say on another branch.')}
    p = pathlib.Path(path) if path else CONTRACT
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    return doc
