#!/usr/bin/env python3.12
"""Artifact lineage: a correct module behind a stale artifact must be mechanically detectable.

THE DEFECT THAT MOTIVATED THIS

nfl/tools/role_state.py was fixed. The projection still produced identical numbers, because it reads
nfl/derived/ROLE_STATE.json and that artifact had not been rebuilt. Nothing failed, nothing warned,
and the two runs were indistinguishable from outside. A correct module behind a stale artifact is
indistinguishable from a broken module.

WHY TIMESTAMPS CANNOT CATCH IT

The readiness board compares ages, and ages get this wrong in both directions. An artifact rebuilt
from an unchanged warehouse gets a fresh timestamp and no new information. An artifact built five
minutes before its builder was edited looks current and is not. Time is a proxy for provenance, and
the proxy fails exactly when the question matters.

WHAT IS RECORDED INSTEAD

Every stamped artifact carries a `_lineage` block naming, by CONTENT HASH:

    inputs        each upstream artifact it was built from, with that input's own lineage id
    code          the source of the builder that produced it
    built_at      wall-clock, for humans, never used for a staleness decision
    lineage_id    a hash over all of the above, so a downstream artifact can name its parent exactly

Verification recomputes those hashes from what is on disk now. If any differs, the artifact is
STALE_DEPENDENCY and the specific input or module that moved is named. Nothing downstream of a
STALE_DEPENDENCY artifact may report full readiness, because its number was produced from something
that no longer exists.

THIS IS A CONTENT COMPARISON, NOT A VERSION STRING

Nobody has to remember to bump anything. The hash of the builder's source IS the code version, so
editing role_state.py invalidates ROLE_STATE.json the moment the edit is saved, and rebuilding
revalidates it.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

LINEAGE_KEY = '_lineage'
FRESH = 'LINEAGE_FRESH'
STALE_DEPENDENCY = 'STALE_DEPENDENCY'
UNSTAMPED = 'LINEAGE_UNSTAMPED'
ABSENT = 'LINEAGE_ARTIFACT_ABSENT'


def digest(path) -> str | None:
    p = pathlib.Path(path)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _lineage_id_of(path) -> str | None:
    """A stamped artifact's own lineage id, so children can name their parent exactly."""
    try:
        art = json.loads(pathlib.Path(path).read_text())
    except Exception:
        return None
    if isinstance(art, dict):
        return (art.get(LINEAGE_KEY) or {}).get('lineage_id')
    return None


def stamp(artifact_path, *, inputs=(), code=()) -> Outcome:
    """Write a `_lineage` block into a JSON artifact naming what produced it.

    Called by a builder AFTER it has written its output. Refuses rather than stamping when the
    artifact is missing or is not a JSON object, because an unstampable artifact must be visible as
    unstamped rather than silently skipped.
    """
    p = pathlib.Path(artifact_path)
    if not p.exists():
        return Outcome.blocked('LINEAGE_NOTHING_TO_STAMP', f'{p} does not exist', cause=Cause.DATA)
    try:
        art = json.loads(p.read_text())
    except Exception as e:  # noqa: BLE001
        return Outcome.fail('LINEAGE_ARTIFACT_NOT_JSON', f'{p}: {e}')
    if not isinstance(art, dict):
        return Outcome.fail('LINEAGE_ARTIFACT_NOT_AN_OBJECT',
                            f'{p} holds a {type(art).__name__}; a lineage block needs an object')

    in_rows = []
    missing = []
    for i in inputs:
        ip = pathlib.Path(i)
        d = digest(ip)
        if d is None:
            missing.append(str(i))
            continue
        in_rows.append({'path': str(ip.relative_to(_REPO)) if ip.is_absolute() else str(i),
                        'sha256': d, 'lineage_id': _lineage_id_of(ip)})
    code_rows = []
    for c in code:
        cp = pathlib.Path(c)
        d = digest(cp)
        if d is None:
            missing.append(str(c))
            continue
        code_rows.append({'path': str(cp.relative_to(_REPO)) if cp.is_absolute() else str(c),
                          'sha256': d})
    if missing:
        return Outcome.fail('LINEAGE_INPUT_ABSENT',
                            f'cannot stamp against inputs that do not exist: {missing}',
                            missing=missing)

    payload = {'inputs': in_rows, 'code': code_rows}
    lid = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
    art[LINEAGE_KEY] = {
        **payload,
        'lineage_id': lid,
        'built_at_unix': int(time.time()),
        'BUILT_AT_IS_NOT_A_FRESHNESS_TEST': (
            'wall-clock is recorded for humans. Staleness is decided by comparing content hashes, '
            'because an artifact rebuilt from unchanged inputs is not newer information and an '
            'artifact built just before its builder was edited is not current.'),
    }
    p.write_text(json.dumps(art, indent=2))
    return Outcome.ok('LINEAGE_STAMPED', value={'path': str(p.relative_to(_REPO)),
                                                'lineage_id': lid,
                                                'n_inputs': len(in_rows), 'n_code': len(code_rows)})


def verify(artifact_path) -> Outcome:
    """Recompute the recorded hashes against what is on disk now."""
    p = pathlib.Path(artifact_path)
    if not p.exists():
        return Outcome.blocked(ABSENT, f'{p} does not exist', cause=Cause.DATA)
    try:
        art = json.loads(p.read_text())
    except Exception as e:  # noqa: BLE001
        return Outcome.fail('LINEAGE_ARTIFACT_NOT_JSON', f'{p}: {e}')
    lin = (art or {}).get(LINEAGE_KEY) if isinstance(art, dict) else None
    if not lin:
        return Outcome.deferred(
            UNSTAMPED, f'{p} carries no lineage block',
            owed='stamp this artifact at build time',
            note=('an unstamped artifact cannot be proven current. It is DEFERRED rather than '
                  'passed, so it is visible as an outstanding debt instead of an assumed success.'))
    moved = []
    for row in lin.get('inputs', []) + lin.get('code', []):
        now = digest(_REPO / row['path'])
        if now is None:
            moved.append({'path': row['path'], 'why': 'INPUT_NOW_ABSENT'})
        elif now != row['sha256']:
            moved.append({'path': row['path'], 'why': 'CONTENT_CHANGED_SINCE_BUILD',
                          'recorded': row['sha256'][:12], 'current': now[:12]})
    if moved:
        return Outcome.fail(
            STALE_DEPENDENCY,
            f'{len(moved)} input or code file changed since {p.name} was built',
            artifact=str(p.relative_to(_REPO)), moved=moved,
            lineage_id=lin.get('lineage_id'),
            note=('this artifact was produced from content that no longer exists, so nothing '
                  'downstream of it may report full readiness. Rebuild it.'))
    return Outcome.ok(FRESH, value={'artifact': str(p.relative_to(_REPO)),
                                    'lineage_id': lin.get('lineage_id'),
                                    'n_inputs': len(lin.get('inputs', [])),
                                    'n_code': len(lin.get('code', []))})


def audit(stages) -> dict:
    """Verify a list of (name, path) and summarise, for the readiness board."""
    rows, counts = [], {}
    for name, path in stages:
        o = verify(_REPO / path)
        state = o.code if o.state.value != 'PASS' else FRESH
        counts[state] = counts.get(state, 0) + 1
        rows.append({'stage': name, 'path': path, 'lineage_state': state,
                     'detail': (o.evidence or {}).get('moved') if state == STALE_DEPENDENCY else None,
                     'lineage_id': ((o.value or {}) or (o.evidence or {})).get('lineage_id')})
    return {
        'rows': rows, 'counts': counts,
        'any_stale_dependency': any(r['lineage_state'] == STALE_DEPENDENCY for r in rows),
        'RULE': ('nothing downstream of a STALE_DEPENDENCY artifact may report full readiness. '
                 'An UNSTAMPED artifact is a recorded debt, not a pass.'),
    }
