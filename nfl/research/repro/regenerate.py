"""Canonical regeneration of the derived research artifacts, from this
repository alone. Stage 1 of the 2026-09-08 directive.

`panel_enriched.pkl` and `volume_store.npy` are NOT committed. They do not need
to be: both are byte-for-byte regenerable from thirteen leaf CSVs (committed
gzipped under `nfl/research/inputs/`) plus the P1-P4B code that was already
committed. The generation mechanism plus the leaves is smaller than the
binaries and, unlike them, can be audited.

Committing the leaves is the point. The sibling MLB project lost `v7/corpus/`
-- never committed, and its M0 baseline is now permanently non-reproducible,
with a four-state status field existing solely to keep saying so. This
repository is one expired session away from the same outcome for every phase
from P4B on. It is not any more.

FAIL CLOSED. Every input hash is checked before it is used, every output hash
is checked after it is produced, and a mismatch anywhere is a refusal that
names what moved. There is no mode in which this script produces an
unverified artifact.

    python3.12 nfl/research/repro/regenerate.py            # verify only
    python3.12 nfl/research/repro/regenerate.py --emit DIR # also keep outputs
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.dirname(HERE)
INPUTS = os.path.join(RESEARCH, 'inputs')
MANIFEST = os.path.join(INPUTS, 'INPUT_MANIFEST.json')
SPEC = os.path.join(HERE, 'ABC_MPR_IDENTITY.json')

# Which decompressed leaf belongs in which code directory. The builders resolve
# their inputs relative to their own file, so the work tree has to look like the
# research tree.
PLACEMENT = {'panel_p3.csv': 'p1', 'denom_panel.csv': 'p4b'}
for _y in range(2020, 2025):
    PLACEMENT[f'dc_{_y}.csv'] = 'p1'
for _y in range(2020, 2026):
    PLACEMENT[f'inj_{_y}.csv'] = 'p1'

CODE_DIRS = ('p1', 'p2', 'p3', 'p4b')


class RegenerationRefused(RuntimeError):
    """Any condition under which an artifact must not be trusted."""


def sha256_file(path):
    """Hash of an archive as it sits on disk."""
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for c in iter(lambda: fh.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def sha256_bytes(data):
    """Hash of decompressed CONTENT. Deliberately a separate, named function
    from `sha256_file` rather than an inline call: the two are independent
    guards -- one catches a damaged archive, the other catches a forged
    manifest -- and a guard you cannot delete on its own is a guard you cannot
    prove is load-bearing."""
    return hashlib.sha256(data).hexdigest()


def stage_inputs(work):
    """Decompress the leaves into a work tree, verifying each as it lands."""
    if not os.path.exists(MANIFEST):
        raise RegenerationRefused(f'MANIFEST_ABSENT: {MANIFEST}')
    man = json.load(open(MANIFEST))
    if not man.get('files'):
        raise RegenerationRefused('MANIFEST_EMPTY: no files declared')
    for d in CODE_DIRS:
        src = os.path.join(RESEARCH, d)
        dst = os.path.join(work, d)
        if not os.path.isdir(src):
            raise RegenerationRefused(f'CODE_DIR_ABSENT: {src}')
        os.makedirs(dst, exist_ok=True)
        for n in os.listdir(src):
            s = os.path.join(src, n)
            if os.path.isfile(s):
                os.symlink(s, os.path.join(dst, n))
    placed = {}
    for name, meta in sorted(man['files'].items()):
        gz = os.path.join(INPUTS, name + '.gz')
        if not os.path.exists(gz):
            raise RegenerationRefused(f'LEAF_ABSENT: {gz}')
        got_gz = sha256_file(gz)
        if got_gz != meta['sha256_gz']:
            raise RegenerationRefused(
                f'LEAF_ARCHIVE_HASH_MISMATCH: {name}.gz is {got_gz[:12]}, '
                f'manifest says {meta["sha256_gz"][:12]}')
        raw = gzip.decompress(open(gz, 'rb').read())
        got = sha256_bytes(raw)
        if got != meta['sha256_decompressed']:
            raise RegenerationRefused(
                f'LEAF_CONTENT_HASH_MISMATCH: {name} decompresses to '
                f'{got[:12]}, manifest says {meta["sha256_decompressed"][:12]}')
        if len(raw) != meta['bytes_decompressed']:
            raise RegenerationRefused(f'LEAF_SIZE_MISMATCH: {name}')
        sub = PLACEMENT.get(name)
        if sub is None:
            raise RegenerationRefused(f'LEAF_UNPLACED: {name} has no declared '
                                      f'home in the work tree')
        dst = os.path.join(work, sub, name)
        if os.path.islink(dst):
            os.unlink(dst)
        open(dst, 'wb').write(raw)
        placed[name] = got
    return placed, man


def _run(work, script, code):
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    p = subprocess.run([sys.executable, '-c', code], cwd=os.path.join(work, script),
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RegenerationRefused(
            f'BUILD_FAILED in {script}: rc={p.returncode}\n'
            f'{p.stdout[-1500:]}\n{p.stderr[-1500:]}')
    return p.stdout


def regenerate(work, expect):
    """Rebuild both artifacts and hash them. Nothing is trusted unverified."""
    out = {}
    log = _run(work, 'p4b',
               'import sys,os,pickle;sys.path.insert(0,os.getcwd());'
               'import p4b_panel as P;k,s=P.build();'
               'pickle.dump(k,open("panel_enriched.pkl","wb"),protocol=4);'
               'print("rows",len(k))')
    out['panel_enriched.pkl'] = {
        'path': os.path.join(work, 'p4b', 'panel_enriched.pkl'),
        'build_log': log.strip().splitlines()[-2:]}
    log = _run(work, 'p4b',
               'import sys,os;sys.path.insert(0,os.getcwd());'
               'import p4b_volume as V;V.main()')
    out['volume_store.npy'] = {
        'path': os.path.join(work, 'p4b', 'volume_store.npy'),
        'build_log': log.strip().splitlines()[-1:]}
    for name, rec in out.items():
        if not os.path.exists(rec['path']):
            raise RegenerationRefused(f'OUTPUT_ABSENT: {name} was not produced')
        if os.path.getsize(rec['path']) == 0:
            raise RegenerationRefused(f'OUTPUT_EMPTY: {name} is zero bytes')
        rec['sha256'] = sha256_file(rec['path'])
        rec['bytes'] = os.path.getsize(rec['path'])
        want = expect[name]['sha256']
        rec['expected_sha256'] = want
        rec['byte_identical'] = rec['sha256'] == want
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--emit', default=None,
                    help='directory to copy the verified artifacts into')
    ap.add_argument('--work', default=None, help='work tree (default: temp)')
    args = ap.parse_args()
    t0 = time.time()
    if not os.path.exists(SPEC):
        raise RegenerationRefused(f'SPEC_ABSENT: {SPEC}')
    spec = json.load(open(SPEC))
    expect = spec['derived_artifacts']

    tmp = args.work or tempfile.mkdtemp(prefix='nfl_regen_')
    os.makedirs(tmp, exist_ok=True)
    try:
        print(f'work tree {tmp}')
        placed, man = stage_inputs(tmp)
        print(f'staged {len(placed)} leaf inputs, all hashes verified')
        out = regenerate(tmp, expect)
        bad = [n for n, r in out.items() if not r['byte_identical']]
        for n, r in out.items():
            print(f'  {"OK " if r["byte_identical"] else "BAD"} {n:22s} '
                  f'{r["sha256"][:16]}  {r["bytes"]:>10d} bytes  '
                  f'(expected {r["expected_sha256"][:16]})')
        rep = {'regenerated': {n: {k: v for k, v in r.items() if k != 'path'}
                               for n, r in out.items()},
               'leaf_inputs_verified': len(placed),
               'all_byte_identical': not bad,
               'python': sys.version.split()[0],
               'seconds': round(time.time() - t0, 1)}
        if bad:
            raise RegenerationRefused(
                f'OUTPUT_HASH_MISMATCH: {bad}. The regenerated artifact is not '
                f'the frozen one, so it is refused rather than emitted. This is '
                f'a DIFFERENT_INPUT_GENERATION, not a failed build.')
        if args.emit:
            os.makedirs(args.emit, exist_ok=True)
            for n, r in out.items():
                shutil.copy2(r['path'], os.path.join(args.emit, n))
            print(f'emitted verified artifacts to {args.emit}')
        json.dump(rep, open(os.path.join(HERE, 'regeneration_report.json'), 'w'),
                  indent=1)
        print(f'\nEXACT_REPRODUCIBLE -- both artifacts byte-identical in '
              f'{rep["seconds"]}s')
        return 0
    finally:
        if not args.work:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RegenerationRefused as exc:
        print(f'\nREFUSED: {exc}')
        sys.exit(2)
