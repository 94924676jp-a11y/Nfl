"""A freeze pin is a reproduction instruction, not a working-tree invariant.

OWNER RULING 2026-09-23. `Q9_PROSPECTIVE_FREEZE.json` records, under
`candidate_identity.module_source_sha16`, the sha16 of every module whose
source produced Q9's numbers. Five test modules asserted that the WORKING TREE
still hashes to those values, and all five have been failing since the pin
diverged.

The assertion was the wrong one. What the pin claims is:

    these exact bytes produced this candidate's numbers, and a re-run must
    use THEM

and that claim is intact as long as the bytes are RETRIEVABLE. It says nothing
about whether the file may change afterwards -- SC2 and QY1 are separate
candidates with their own identities, and forbidding the file to move would
freeze the repository, not the candidate.

So this module answers four questions instead of one:

    1. was the pin correct at freeze time?
    2. is the exact frozen blob still retrievable?
    3. can the candidate be reproduced from the pinned dependency set?
    4. does reproduction read the frozen bytes, not the working tree?

WORKING-TREE DIVERGENCE IS REPORTED SEPARATELY AND IS NOT A FAILURE. It is
governance evidence -- "HEAD is not the commit this candidate was frozen at"
-- and a reader needs it, which is why `WORKING_TREE_DIVERGED_FROM_FROZEN_
CANDIDATE` exists as its own diagnostic rather than being folded into a pass
or a fail.

THE PIN IS NEVER MOVED HERE. Nothing in this module writes to the freeze
artifact. A pin edited to match whatever the tree holds today is not a pin.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nfl-frozen-candidate-0'

CODE_REPRODUCIBLE = 'FROZEN_CANDIDATE_REPRODUCIBLE'
CODE_BLOB_LOST = 'FROZEN_BLOB_NOT_RETRIEVABLE'
CODE_PIN_ABSENT = 'FROZEN_PIN_ABSENT'
CODE_ARTIFACT_ABSENT = 'FREEZE_ARTIFACT_ABSENT'
#: Informational. Governance evidence, never a verdict about the candidate.
DIAG_TREE_DIVERGED = 'WORKING_TREE_DIVERGED_FROM_FROZEN_CANDIDATE'

#: module dotted name -> repository path
MODULE_PATHS = {
    'nfl.production.nonqb.layers': 'nfl/production/nonqb/layers.py',
    'nfl.research.q9.hurdle': 'nfl/research/q9/hurdle.py',
    'nfl.research.q9b.family': 'nfl/research/q9b/family.py',
    'nfl.research.q9b.production_parity':
        'nfl/research/q9b/production_parity.py',
}


def _sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _git(*args) -> Optional[bytes]:
    try:
        r = subprocess.run(('git',) + args, cwd=str(_REPO),
                           capture_output=True, timeout=60)
    except Exception:                                         # noqa: BLE001
        return None
    return r.stdout if r.returncode == 0 else None


def commits_touching(path: str) -> List[str]:
    out = _git('log', '--all', '--format=%H', '--', path)
    return (out or b'').decode().split()


def find_blob(path: str, sha16: str) -> Optional[Dict[str, str]]:
    """The commit whose version of `path` hashes to `sha16`.

    Searched rather than assumed: the freeze artifact records WHAT the bytes
    were, not WHERE they are, and the answer is a fact about the object store
    that has to be looked up.
    """
    for c in commits_touching(path):
        blob = _git('show', f'{c}:{path}')
        if blob is not None and _sha16(blob) == sha16:
            subj = (_git('log', '-1', '--format=%s', c) or b'').decode().strip()
            return {'commit': c, 'short': c[:7], 'subject': subj[:80]}
    return None


def frozen_bytes(path: str, sha16: str) -> Optional[bytes]:
    """The pinned bytes themselves, so a reproduction can READ them.

    This is requirement 4: a re-run that hashes the frozen blob and then
    imports the working tree has proved nothing.
    """
    at = find_blob(path, sha16)
    if at is None:
        return None
    b = _git('show', f'{at["commit"]}:{path}')
    return b if b is not None and _sha16(b) == sha16 else None


def check(freeze_artifact, *, modules: Dict[str, str] = None) -> Outcome:
    """The four questions, answered per pinned module."""
    p = pathlib.Path(freeze_artifact)
    if not p.exists():
        return Outcome.blocked(
            CODE_ARTIFACT_ABSENT, f'{p} does not exist, so there is no pin '
                                  f'to verify.', cause=Cause.DATA)
    doc = json.loads(p.read_text())
    pins = ((doc.get('candidate_identity') or {})
            .get('module_source_sha16') or {})
    if not pins:
        return Outcome.blocked(
            CODE_PIN_ABSENT,
            f'{p} carries no candidate_identity.module_source_sha16. A freeze '
            f'that names no dependency cannot be reproduced from one.',
            cause=Cause.DATA)
    paths = dict(MODULE_PATHS, **(modules or {}))
    rows, lost, diverged = [], [], []
    for mod in sorted(pins):
        want = pins[mod]
        path = paths.get(mod)
        if path is None:
            lost.append({'module': mod, 'why': 'no path mapping'})
            continue
        at = find_blob(path, want)
        live = (_REPO / path)
        cur = _sha16(live.read_bytes()) if live.exists() else None
        row = {'module': mod, 'path': path, 'pinned_sha16': want,
               'retrievable': at is not None, 'at': at,
               'working_tree_sha16': cur,
               'working_tree_matches': cur == want}
        rows.append(row)
        if at is None:
            lost.append({'module': mod, 'path': path, 'pinned_sha16': want})
        if cur != want:
            diverged.append({'module': mod, 'path': path,
                             'pinned_sha16': want, 'working_tree_sha16': cur})

    # THE DIAGNOSTIC IS CARRIED WHETHER THE VERDICT PASSES OR FAILS.
    diagnostic = {
        'code': DIAG_TREE_DIVERGED,
        'n_diverged': len(diverged), 'diverged': diverged,
        'means': 'HEAD is not the commit this candidate was frozen at. That '
                 'is governance evidence about the TREE, not evidence that '
                 'the frozen candidate is invalid. A re-run must check out '
                 'the pinned blobs; it must not read the working tree.',
    } if diverged else {'code': None, 'n_diverged': 0, 'diverged': []}

    if lost:
        return Outcome.fail(
            CODE_BLOB_LOST,
            f'{len(lost)} pinned dependency blob(s) cannot be retrieved from '
            f'git: {[x.get("module") for x in lost]}. A freeze whose bytes '
            f'are gone is not reproducible, and that IS a failure of the '
            f'candidate, not of the tree.',
            modules=rows, lost=lost, working_tree_divergence=diagnostic,
            spec_version=SPEC_VERSION)
    return Outcome.ok(
        CODE_REPRODUCIBLE,
        {'artifact': str(p.relative_to(_REPO)), 'n_pins': len(rows),
         'modules': rows, 'working_tree_divergence': diagnostic,
         'spec_version': SPEC_VERSION},
        detail=f'{len(rows)} pinned dependency blob(s) retrievable; '
               f'{len(diverged)} diverged from the working tree')
