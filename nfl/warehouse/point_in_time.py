#!/usr/bin/env python3.12
"""One point-in-time data-selection contract for every captured data family. Owner directive 2026-10-08.

    python3.12 nfl/warehouse/point_in_time.py build --cutoff 2026-10-05T23:47:00Z --label ATL_NO_2026W4 \
        [--derived-pins nfl/production/DERIVED_REBUILD_MANIFEST.ATL_NO_REPRO_2026-10-07.json] [--input PATH ...]
    python3.12 nfl/warehouse/point_in_time.py verify PIT_MANIFEST.<seal>.json

THE DEFECTS THIS CLOSES (docs/SHOWDOWN_BASELINE_REPRODUCTION.md F1-F3). A historical replay on today's tree read:
  F1  today's TEAM_GAME, so the export resolved to a game that did not exist at lock;
  F2  every roster capture ever taken (`player_prior` globs them all, last wins);
  F3  the largest play-by-play capture per season (`dst_model._capture`), which by then held the game itself.
Each was "the newest file on disk" standing in for "what was known at the cutoff". The replay that reproduced
production did it by DELETING the post-lock files in a worktree. This module does the same thing without deleting
anything: a run reads only what an explicit, sealed, immutable manifest authorizes.

THE CONTRACT
  1. A cutoff is an explicit UTC instant with a stated basis (kickoff, the production commit time, ...). There is no
     default. Building a manifest without one is refused.
  2. Every capture under a GUARDED ROOT is classified once, at build time, by its RETRIEVAL clock:
       nfl/vintage/*, nfl_vintage/raw/*  the earliest PASS row for that content id in nfl/vintage_manifest.jsonl
       nfl/research/postgame/pbp_*       the capture's own provenance sidecar (`retrieved_at`)
     no such record, but committed   the commit time that FIRST added the file (GIT_FIRST_COMMIT): bytes cannot have
                                     been retrieved after the commit that added them, so this is an upper bound on
                                     retrieval time and can only ever admit too late, never too early
     retrieved_at <= cutoff -> ADMITTED (pinned by sha256); later -> REFUSED_AFTER_CUTOFF; no clock -> REFUSED_UNCLOCKED.
     Retrieval time is conservative: bytes can only be known after we fetched them. It is also an evidence ceiling --
     a 2025 file fetched in 2026 is not admitted for a 2025 cutoff, and the manifest says so rather than guessing.
  3. Fixed-path derived artifacts are RESOLVED, never overwritten: `nfl/warehouse/TEAM_GAME.json` resolves to the
     last git commit of that path at or before the cutoff (clock basis COMMIT_TIME), materialized read-only into a
     run-scoped scratch directory and pinned by sha256.
  4. The nfl/derived caches are admitted only against declared pins (an explicit rebuild manifest). Unpinned derived
     caches are refused in a sealed run: a cache built from unknown vintages is not point-in-time evidence.
  5. Explicit per-slate inputs (DK export, depth chart, designations, ...) are pinned by sha256 and carry the capture
     clock their slate PROVENANCE.jsonl records, or CLOCK_UNRECORDED. They are bound again by the runner's FREEZE seal.
  6. The manifest is sealed: `seal` = sha256 of its canonical JSON without the seal. It is written once, to a file
     named by its seal; a different manifest can never take its name.

ENFORCEMENT, IN TWO LAYERS
  * Selection: every reader that enumerates captures passes its candidate list through `admit(paths, family)`, which
    keeps the caller's own order and drops what the manifest does not admit. Fixed paths pass through
    `resolve(path)`. With no manifest active both are the identity, so the live path is unchanged byte for byte.
  * Backstop: with a manifest active, a `sys.addaudithook` hook refuses (PITUnauthorizedRead) any `open` of a guarded
    file that the manifest does not admit, and any admitted file whose bytes no longer match the pin. A reader that
    was never wired therefore fails loudly instead of leaking. Deliberately injected post-cutoff files are not
    admitted (they are not in the sealed manifest), so they cannot reach a sealed replay.

ACTIVATION. `NFL_PIT_MANIFEST=<path>` in the environment. Child processes inherit it. Nothing else turns it on.
`NFL_PIT_TRACE=<prefix>` additionally writes `<prefix>.<pid>.json`: every repository data file the process opened for
reading, classified (admitted / resolved / pinned derived / UNGUARDED). It is the read inventory of a sealed run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import threading

_REPO = pathlib.Path(__file__).resolve().parents[2]
SPEC_VERSION = 'pit-1'
ENV = 'NFL_PIT_MANIFEST'
OUT_DIR = _REPO / 'nfl/warehouse/pit_manifests'
SCRATCH = _REPO / 'nfl/dfs/salaries/runs/pit'          # git-ignored
VINTAGE_MANIFEST = 'nfl/vintage_manifest.jsonl'

# (root, filename pattern, family, clock source). A file is GUARDED when it sits directly in a root and matches.
GUARDED = (
    ('nfl/vintage', '*.*.*', 'vintage', 'VINTAGE_MANIFEST_FIRST_PASS'),
    ('nfl_vintage/raw', '*.*.*', 'vintage_raw', 'VINTAGE_MANIFEST_FIRST_PASS'),
    ('nfl/research/postgame', 'pbp_*.csv.gz', 'pbp', 'PROVENANCE_SIDECAR'),
)
NOT_CAPTURES = ('SYNC_PROVENANCE.jsonl',)
RESOLVED = ('nfl/warehouse/TEAM_GAME.json',)
DERIVED_DIR = 'nfl/derived'
DERIVED_RUN_CACHES = ('ROLE_STATE.json', 'SOURCE_MEASUREMENT_CACHE.json')   # rebuilt per run / content-keyed
_ID = re.compile(r'^(?P<src>[A-Za-z_]+?)(?:_(?P<season>\d{4}))?\.(?P<id>[0-9a-f]{16})\.')


class PITError(RuntimeError):
    """Base for every named point-in-time refusal. The message starts with its code."""


class PITCutoffUnresolved(PITError):
    pass


class PITManifestInvalid(PITError):
    pass


class PITUnauthorizedRead(PITError):
    pass


# ------------------------------------------------------------------ clocks
def parse_utc(s) -> dt.datetime | None:
    if not s:
        return None
    s = str(s).strip()
    for f in (lambda x: dt.datetime.fromisoformat(x.replace('Z', '+00:00')),
              lambda x: dt.datetime.strptime(x, '%a %b %d %H:%M:%S UTC %Y').replace(tzinfo=dt.timezone.utc),
              lambda x: dt.datetime.strptime(' '.join(x.split()), '%a %b %d %H:%M:%S UTC %Y').replace(
                  tzinfo=dt.timezone.utc)):
        try:
            t = f(s)
            return t if t.tzinfo else None
        except ValueError:
            continue
    return None


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _rel(p, root: pathlib.Path) -> str | None:
    try:
        return str(pathlib.Path(os.path.abspath(p)).relative_to(root))
    except ValueError:
        return None


def _guard_of(rel: str):
    d, name = os.path.split(rel)
    if name in NOT_CAPTURES or name.endswith('.provenance.json'):
        return None
    for root, pat, fam, clk in GUARDED:
        if d == root and fnmatch.fnmatch(name, pat) and _ID.match(name):
            return fam, clk
    return None


def _first_pass_clocks(root: pathlib.Path) -> dict:
    """content id (16 hex) -> earliest retrieved_at of a PASS row for it. Read once; order-free."""
    out = {}
    p = root / VINTAGE_MANIFEST
    if not p.is_file():
        return out
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        t = parse_utc(v.get('retrieved_at') or (v.get('provenance') or {}).get('retrieved_at'))
        m = _ID.match(os.path.basename(v.get('blob') or ''))
        if t is None or not m:
            continue
        k = m['id']
        if k not in out or t < out[k]:
            out[k] = t
    return out


def _first_commit_clocks(root: pathlib.Path) -> dict:
    """repo-relative path -> commit time of the commit that first added it, for the guarded roots. One git pass."""
    out, t = {}, None
    txt = _git(root, 'log', '--diff-filter=A', '--format=%x00%cI', '--name-only', '--',
               *[r for r, *_ in GUARDED if (root / r).is_dir()])
    for line in txt.splitlines():
        if line.startswith('\x00'):
            t = parse_utc(line[1:])
        elif line.strip() and t is not None:
            if line not in out or t < out[line]:
                out[line] = t
    return out


def _git(root, *a):
    return subprocess.run(['git', *a], cwd=root, capture_output=True, text=True, check=True).stdout


# ------------------------------------------------------------------ build
def build(cutoff: str, label: str, cutoff_basis: str, root=None, derived_pins=None, inputs=(), out_dir=None):
    """Classify every guarded capture against the cutoff, resolve fixed paths, seal, write. Returns (path, manifest)."""
    root = pathlib.Path(root or _REPO)
    cut = parse_utc(cutoff)
    if cut is None:
        raise PITCutoffUnresolved(f'PIT_CUTOFF_UNRESOLVED: {cutoff!r} is not an aware UTC instant')
    if not cutoff_basis:
        raise PITCutoffUnresolved('PIT_CUTOFF_BASIS_MISSING: state what the cutoff is (kickoff, production commit, ...)')
    clocks = _first_pass_clocks(root)
    committed = _first_commit_clocks(root)
    admitted, refused = {}, {}
    for groot, pat, fam, clk in GUARDED:
        d = root / groot
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            rel = str(f.relative_to(root))
            if not f.is_file() or _guard_of(rel) is None:
                continue
            m = _ID.match(f.name)
            if clk == 'PROVENANCE_SIDECAR':
                sc = f.with_name(f.name[:-3] + '.provenance.json') if f.name.endswith('.gz') else None
                t = parse_utc(json.loads(sc.read_text()).get('retrieved_at')) if sc and sc.is_file() else None
            else:
                t = clocks.get(m['id'])
            basis = clk
            if t is None and rel in committed:
                t, basis = committed[rel], 'GIT_FIRST_COMMIT'
            rec = {'family': fam, 'source': m['src'], 'season': int(m['season']) if m['season'] else None,
                   'clock': _iso(t) if t else None, 'clock_basis': basis}
            if t is None:
                refused[rel] = {**rec, 'reason': 'REFUSED_UNCLOCKED'}
            elif t > cut:
                refused[rel] = {**rec, 'reason': 'REFUSED_AFTER_CUTOFF'}
            else:
                admitted[rel] = {**rec, 'sha256': sha256(f)}
                if clk == 'PROVENANCE_SIDECAR' and sc is not None and sc.is_file():
                    admitted[str(sc.relative_to(root))] = {**rec, 'companion_of': rel, 'sha256': sha256(sc)}
    resolved = {}
    for rel in RESOLVED:
        hist = [ln.split(' ', 1) for ln in _git(root, 'log', '--format=%H %cI', '--', rel).splitlines() if ln.strip()]
        lawful = [(h, parse_utc(t)) for h, t in hist if parse_utc(t) and parse_utc(t) <= cut]
        if not lawful:
            refused[rel] = {'family': 'resolved', 'reason': 'NO_COMMIT_AT_OR_BEFORE_CUTOFF'}
            continue
        h, t = max(lawful, key=lambda x: x[1])
        blob = _git(root, 'rev-parse', f'{h}:{rel}').strip()
        data = subprocess.run(['git', 'cat-file', 'blob', blob], cwd=root, capture_output=True, check=True).stdout
        resolved[rel] = {'family': 'resolved', 'source': 'git', 'commit': h, 'git_blob': blob,
                         'clock': _iso(t), 'clock_basis': 'COMMIT_TIME', 'sha256': hashlib.sha256(data).hexdigest()}
    pins = None
    if derived_pins:
        dp = json.loads(pathlib.Path(derived_pins).read_text())
        pins = {'source': str(derived_pins), 'sha256': dp['sha256']}
    explicit = {}
    for p in inputs:
        f = (root / p) if not os.path.isabs(p) else pathlib.Path(p)
        rel = _rel(f, root) or str(f)
        t = _slate_clock(f)
        if t is not None and t > cut:
            refused[rel] = {'family': 'explicit_input', 'reason': 'REFUSED_AFTER_CUTOFF', 'clock': _iso(t)}
            continue
        explicit[rel] = {'family': 'explicit_input', 'sha256': sha256(f), 'clock': _iso(t) if t else None,
                         'clock_basis': 'SLATE_PROVENANCE' if t else 'CLOCK_UNRECORDED'}
    man = {'ARTIFACT': 'PIT_MANIFEST', 'spec_version': SPEC_VERSION, 'label': label, 'cutoff_utc': _iso(cut),
           'cutoff_basis': cutoff_basis, 'built_from_commit': _git(root, 'rev-parse', 'HEAD').strip(),
           'rule': 'admit a guarded capture iff its retrieval clock <= cutoff; resolve fixed paths to the last commit '
                   '<= cutoff; derived caches only against declared pins',
           'guarded': [{'root': r, 'pattern': p, 'family': f, 'clock_source': c} for r, p, f, c in GUARDED],
           'admitted': admitted, 'refused': refused, 'resolved': resolved, 'derived_pins': pins,
           'explicit_inputs': explicit,
           'counts': {'admitted': len(admitted), 'refused_after_cutoff':
                      sum(1 for v in refused.values() if v['reason'] == 'REFUSED_AFTER_CUTOFF'),
                      'refused_unclocked': sum(1 for v in refused.values() if v['reason'] == 'REFUSED_UNCLOCKED')}}
    man['seal'] = _seal(man)
    out = pathlib.Path(out_dir or (root / OUT_DIR.relative_to(_REPO))) / f'PIT_MANIFEST.{label}.{man["seal"][:16]}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(man, indent=1, sort_keys=True) + '\n'
    if out.exists() and out.read_text() != text:
        raise PITManifestInvalid(f'PIT_MANIFEST_IMMUTABLE: {out} exists with different content')
    out.write_text(text)
    return out, man


def _slate_clock(f: pathlib.Path):
    prov = f.parent / 'PROVENANCE.jsonl'
    if not prov.is_file():
        return None
    ts = []
    for line in prov.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('file') == f.name:
            t = parse_utc(r.get('retrieved_at') or r.get('captured_at_utc') or r.get('captured_at'))
            if t:
                ts.append(t)
    return min(ts) if ts else None


def _seal(man: dict) -> str:
    body = {k: v for k, v in man.items() if k != 'seal'}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


# ------------------------------------------------------------------ the active manifest
class Active:
    def __init__(self, path: pathlib.Path, man: dict, root: pathlib.Path):
        self.path, self.man, self.root = path, man, root
        self.admitted = man['admitted']
        self.refused = man['refused']
        self.verified: set[str] = set()
        self.scratch = root / SCRATCH.relative_to(_REPO) / man['seal'][:16]
        self.reads: dict[str, int] = {}

    def check(self, rel: str):
        """Verify an admitted file's bytes against its pin (once per process)."""
        if rel in self.verified:
            return
        rec = self.admitted.get(rel) or self.man['explicit_inputs'].get(rel)
        got = sha256(self.root / rel)
        if got != rec['sha256']:
            raise PITUnauthorizedRead(f'PIT_ADMITTED_FILE_CHANGED: {rel} sha256 {got[:16]} != pinned {rec["sha256"][:16]}')
        self.verified.add(rel)


_ACTIVE: Active | None = None
_LOADED = False
_GUARD = threading.local()


def load(path, root=None) -> Active:
    root = pathlib.Path(root or _REPO)
    p = pathlib.Path(path)
    if not p.is_file():
        raise PITManifestInvalid(f'PIT_MANIFEST_ABSENT: {p}')
    man = json.loads(p.read_text())
    if man.get('ARTIFACT') != 'PIT_MANIFEST' or man.get('spec_version') != SPEC_VERSION:
        raise PITManifestInvalid(f'PIT_MANIFEST_FOREIGN: {p}')
    if _seal(man) != man.get('seal'):
        raise PITManifestInvalid(f'PIT_MANIFEST_SEAL_BROKEN: {p} does not hash to its seal')
    missing = [r for r in man['admitted'] if not (root / r).is_file()]
    if missing:
        raise PITManifestInvalid(f'PIT_ADMITTED_FILE_MISSING: {len(missing)} admitted file(s) absent, e.g. {missing[0]}')
    return Active(p, man, root)


def active() -> Active | None:
    """The manifest named by NFL_PIT_MANIFEST, loaded and verified once per process, or None (live mode)."""
    global _ACTIVE, _LOADED
    if not _LOADED:
        _LOADED = True
        if os.environ.get(ENV):
            _ACTIVE = load(os.environ[ENV])
            _install_hook()
    return _ACTIVE


def admit(paths, family='capture'):
    """The caller's candidate list, in the caller's order, minus every file the active manifest does not admit.

    Identity with no manifest active. With one, a guarded candidate is kept only if admitted (and its bytes still
    match the pin); unguarded candidates pass through. `family` is recorded, not used for selection.
    """
    a = active()
    if a is None:
        return list(paths)
    out = []
    for p in paths:
        rel = _rel(p, a.root)
        if rel is None or _guard_of(rel) is None:
            out.append(p)
        elif rel in a.admitted:
            a.check(rel)
            out.append(p)
    return out


def resolve(path):
    """A fixed-path artifact as of the cutoff (materialized from git), or the path itself in live mode."""
    a = active()
    if a is None:
        return path
    rel = _rel(path, a.root)
    rec = a.man['resolved'].get(rel)
    if rec is None:
        if rel in RESOLVED:
            raise PITUnauthorizedRead(f'PIT_NO_LAWFUL_VINTAGE: {rel} has no commit at or before {a.man["cutoff_utc"]}')
        return path
    dst = a.scratch / rel
    if not dst.is_file() or sha256(dst) != rec['sha256']:
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = subprocess.run(['git', 'cat-file', 'blob', rec['git_blob']], cwd=a.root, capture_output=True,
                              check=True).stdout
        if hashlib.sha256(data).hexdigest() != rec['sha256']:
            raise PITUnauthorizedRead(f'PIT_RESOLVED_BLOB_CHANGED: {rel} git blob {rec["git_blob"]}')
        tmp = dst.with_suffix(dst.suffix + '.tmp')
        tmp.write_bytes(data)
        tmp.replace(dst)
    return type(path)(dst) if isinstance(path, (str, pathlib.PurePath)) else dst


def record() -> dict | None:
    """What this process read under the manifest, for receipts and replay evidence."""
    a = active()
    if a is None:
        return None
    return {'manifest': str(a.path), 'seal': a.man['seal'], 'cutoff_utc': a.man['cutoff_utc'],
            'guarded_reads': dict(sorted(a.reads.items()))}


# ------------------------------------------------------------------ backstop
TRACE_ENV = 'NFL_PIT_TRACE'
_TRACE: dict[str, str] = {}


def _classify(a, rel):
    if rel in a.admitted or rel in a.man['explicit_inputs']:
        return 'ADMITTED'
    if rel in RESOLVED:
        return 'RESOLVED_ONLY'
    if a.scratch in (a.root / rel).parents:
        return 'RESOLVED_VINTAGE'
    d, name = os.path.split(rel)
    if d == DERIVED_DIR:
        return 'DERIVED_RUN_CACHE' if name in DERIVED_RUN_CACHES else 'DERIVED_PINNED'
    return 'UNGUARDED'


def _write_trace():
    if _TRACE and os.environ.get(TRACE_ENV):
        out = pathlib.Path(f'{os.environ[TRACE_ENV]}.{os.getpid()}.json')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({'argv': sys.argv[:3], 'reads': dict(sorted(_TRACE.items()))}, indent=1) + '\n')


def _hook(event, args):
    if event != 'open' or _ACTIVE is None or getattr(_GUARD, 'busy', False):
        return
    p = args[0]
    if isinstance(p, int):
        return
    if isinstance(p, bytes):
        p = os.fsdecode(p)
    a = _ACTIVE
    rel = _rel(p, a.root)
    if rel is None:
        return
    mode = args[1] or ''
    writing = any(c in str(mode) for c in 'wax+')
    _GUARD.busy = True
    try:
        if (not writing and os.environ.get(TRACE_ENV) and not rel.endswith(('.py', '.pyc'))
                and '__pycache__' not in rel and not rel.startswith('.git')):
            _TRACE.setdefault(rel, _classify(a, rel))
        if rel in RESOLVED:
            if not writing:
                raise PITUnauthorizedRead(f'PIT_UNRESOLVED_READ: {rel} opened directly; it must pass through resolve()')
            return
        d, name = os.path.split(rel)
        if d == DERIVED_DIR and name not in DERIVED_RUN_CACHES and name.endswith('.json') and not writing:
            pins = (a.man.get('derived_pins') or {}).get('sha256') or {}
            if name not in pins:
                raise PITUnauthorizedRead(f'PIT_DERIVED_UNPINNED: {rel} read in a sealed run without a declared pin')
            if rel not in a.verified:
                got = sha256(a.root / rel)
                if got != pins[name]:
                    raise PITUnauthorizedRead(f'PIT_DERIVED_VINTAGE_MISMATCH: {rel} {got[:16]} != pin {pins[name][:16]}')
                a.verified.add(rel)
            a.reads[rel] = a.reads.get(rel, 0) + 1
            return
        if _guard_of(rel) is None or writing:
            return
        if rel not in a.admitted:
            why = a.refused.get(rel, {}).get('reason', 'NOT_IN_SEALED_MANIFEST')
            raise PITUnauthorizedRead(f'PIT_UNAUTHORIZED_READ: {rel} ({why}) under manifest {a.man["seal"][:16]} '
                                      f'cutoff {a.man["cutoff_utc"]}')
        a.check(rel)
        a.reads[rel] = a.reads.get(rel, 0) + 1
    finally:
        _GUARD.busy = False


_HOOKED = False


def _install_hook():
    global _HOOKED
    if not _HOOKED:
        sys.addaudithook(_hook)
        if os.environ.get(TRACE_ENV):
            import atexit
            atexit.register(_write_trace)
        _HOOKED = True


def _reset_for_tests(manifest_path=None, root=None):
    """Tests only: activate a manifest in-process (audit hooks cannot be removed, so deactivation clears state)."""
    global _ACTIVE, _LOADED
    _ACTIVE = load(manifest_path, root) if manifest_path else None
    _LOADED = True
    if _ACTIVE is not None:
        _install_hook()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    b = sp.add_parser('build')
    b.add_argument('--cutoff', required=True)
    b.add_argument('--cutoff-basis', required=True)
    b.add_argument('--label', required=True)
    b.add_argument('--derived-pins')
    b.add_argument('--input', action='append', default=[])
    b.add_argument('--out-dir')
    v = sp.add_parser('verify')
    v.add_argument('manifest')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        p, m = build(a.cutoff, a.label, a.cutoff_basis, derived_pins=a.derived_pins, inputs=a.input, out_dir=a.out_dir)
        print(json.dumps({'manifest': str(p), 'seal': m['seal'], 'counts': m['counts'],
                          'resolved': {k: v['commit'][:8] for k, v in m['resolved'].items()}}, indent=1))
        return 0
    m = load(a.manifest).man
    print(json.dumps({'seal': m['seal'], 'cutoff_utc': m['cutoff_utc'], 'counts': m['counts'], 'ok': True}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
