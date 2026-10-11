#!/usr/bin/env python3.12
"""Is this checkout's test environment complete? The git-ignored inputs the suite reads, verified by hash.

    python3.12 nfl/tools/test_env_check.py [--json OUT]

WHY (found 2026-10-10, Phase 1). A fresh worktree has no `nfl/derived/` and no `nfl_vintage/raw/`: both are
git-ignored. The suite then did not say "environment incomplete". Three test functions raised TypeError (a refused
state build subscripted as if it had passed), and two modules ran fewer checks without saying why. A regression
comparison between such a checkout and the main one measures missing data, not code.

WHAT IS CHECKED, and how each input is reproduced:
  nfl/derived/<artifact>   sha256 against nfl/production/DERIVED_REBUILD_MANIFEST.json (generation recorded there).
                           REPRODUCE: `bash nfl/tools/rebuild_derived.sh` (rebuilds from committed inputs and fails
                           with exit 4 on any hash mismatch). Never copy it from another checkout without this check.
  nfl_vintage/raw/<file>   the full capture files named `<source>.<sha16>.<ext>`: sha256 must start with sha16 and
                           equal the PASS row of nfl/vintage_manifest.jsonl that names it. These are scheduled-capture
                           outputs (nflverse public data); the committed manifest is their provenance.
                           REPRODUCE: re-run the capture that produced them, or copy from a checkout that has them
                           and let this tool verify every hash; a file no manifest row names is UNVERIFIABLE,
                           never OK, and makes the environment INCOMPLETE (no provenance, no completeness).
  python packages          numpy and pandas importable (rebuild_derived.sh installs them into PYLIB).

Exit 0 COMPLETE; 2 INCOMPLETE (anything MISSING, MISMATCH or UNVERIFIABLE). Read-only: writes nothing but --json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC_VERSION = 'test-env-check-2'


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def derived(root=ROOT):
    man_p = root / 'nfl' / 'production' / 'DERIVED_REBUILD_MANIFEST.json'
    out = []
    try:
        man = json.loads(man_p.read_text())
    except (OSError, ValueError) as e:
        return [{'input': str(man_p.relative_to(root)), 'state': 'MISSING', 'why': f'manifest unreadable: {e}'}], None
    for name, want in sorted(man.get('sha256', {}).items()):
        p = root / 'nfl' / 'derived' / name
        if not p.exists():
            out.append({'input': f'nfl/derived/{name}', 'state': 'MISSING',
                        'reproduce': 'bash nfl/tools/rebuild_derived.sh'})
        else:
            got = _sha(p)
            out.append({'input': f'nfl/derived/{name}', 'state': 'OK' if got == want else 'MISMATCH',
                        'sha256': got, 'expected': want, 'reproduce': 'bash nfl/tools/rebuild_derived.sh'})
    return out, man.get('generation')


def vintage_raw(root=ROOT):
    raw = root / 'nfl_vintage' / 'raw'
    out = []
    manifest_sha = {}
    try:
        for ln in open(root / 'nfl' / 'vintage_manifest.jsonl'):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            v = r.get('value') or {}
            if r.get('state') == 'PASS' and v.get('sha256'):
                manifest_sha.setdefault(v['sha256'][:16], v['sha256'])
    except OSError:
        pass
    if not raw.is_dir():
        return [{'input': 'nfl_vintage/raw/', 'state': 'MISSING',
                 'reproduce': 're-run the capture, or copy from a checkout that has it and re-run this check'}]
    for p in sorted(raw.iterdir()):
        if p.name.startswith('.'):
            continue
        m = re.match(r'^(.+?)\.([0-9a-f]{16})\.[^/]+$', p.name)
        if not m:
            out.append({'input': f'nfl_vintage/raw/{p.name}', 'state': 'UNVERIFIABLE', 'why': 'no sha16 in the name'})
            continue
        got = _sha(p)
        want = manifest_sha.get(m.group(2))
        if not got.startswith(m.group(2)):
            state = 'MISMATCH'
        elif want is None:
            state = 'UNVERIFIABLE'
        else:
            state = 'OK' if got == want else 'MISMATCH'
        out.append({'input': f'nfl_vintage/raw/{p.name}', 'state': state, 'sha256': got,
                    'manifest_row': bool(want)})
    if not out:
        out.append({'input': 'nfl_vintage/raw/', 'state': 'MISSING', 'why': 'directory is empty'})
    return out


def packages():
    out = []
    for mod in ('numpy', 'pandas'):
        try:
            __import__(mod)
            out.append({'input': f'python:{mod}', 'state': 'OK'})
        except ImportError:
            out.append({'input': f'python:{mod}', 'state': 'MISSING',
                        'reproduce': 'PYLIB=<dir> bash nfl/tools/rebuild_derived.sh (installs into PYLIB)'})
    return out


def check(root=ROOT):
    d, gen = derived(root)
    rows = d + vintage_raw(root) + packages()
    bad = [r for r in rows if r['state'] in ('MISSING', 'MISMATCH', 'UNVERIFIABLE')]
    return {'ARTIFACT': 'TEST_ENVIRONMENT_CHECK', 'spec_version': SPEC_VERSION, 'root': str(root),
            'derived_manifest_generation': gen, 'verdict': 'INCOMPLETE' if bad else 'COMPLETE',
            'n_inputs': len(rows), 'n_missing': sum(r['state'] == 'MISSING' for r in rows),
            'n_mismatch': sum(r['state'] == 'MISMATCH' for r in rows),
            'n_unverifiable': sum(r['state'] == 'UNVERIFIABLE' for r in rows), 'inputs': rows,
            'READING': 'a suite result from an INCOMPLETE environment measures missing data, not the code'}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    rep = check()
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rep, indent=1) + '\n')
    print(f"TEST_ENVIRONMENT {rep['verdict']}: {rep['n_inputs']} inputs, {rep['n_missing']} missing, "
          f"{rep['n_mismatch']} mismatch, {rep['n_unverifiable']} unverifiable (derived generation "
          f"{rep['derived_manifest_generation']})")
    for r in rep['inputs']:
        if r['state'] != 'OK':
            print(f"  {r['state']:12} {r['input']}  {r.get('reproduce') or r.get('why') or ''}")
    return 0 if rep['verdict'] == 'COMPLETE' else 2


if __name__ == '__main__':
    sys.exit(main())
