"""Read-only consumption of the derived research artifacts.

THE ARCHITECTURE THE R4 PACKET ASKS FOR

    research artifact generation  ->  immutable derived artifact  ->  production
                                                                     READ-ONLY

R3 got this wrong in a way the snapshot-and-restore fix concealed rather than
corrected. Production shelled out to `regenerate.py`'s COMMAND LINE, whose
`main()` writes a run report into `nfl/research/repro/`. Restoring the file
afterwards left the tree clean and left the architecture wrong: a forecast was
still invoking a mutating research command, and the restore was one exception
away from not happening.

The correction is structural. `regenerate.py` separates cleanly into pure
functions -- `stage_inputs(work)` and `regenerate(work, expect)` -- that build
into a TEMPORARY work tree and write nothing anywhere else. Only `main()`
writes the report. So production imports the module and calls the pure
functions, never the command, and copies the verified outputs into its own
cache outside the research tree.

WHERE THE CACHE LIVES. `nfl/derived/` by default, overridable with
NFL_DERIVED_DIR. It is gitignored: these artifacts are byte-for-byte
regenerable from the committed leaves, which is why they were never committed.

EVERY READ IS VERIFIED. A cached artifact whose hash does not match
`ABC_MPR_IDENTITY.json` is refused and rebuilt rather than used, so a corrupted
or stale cache cannot quietly become the model.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'repro')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome      # noqa: E402

RESEARCH = _REPO / 'nfl' / 'research'
SPEC = RESEARCH / 'repro' / 'ABC_MPR_IDENTITY.json'
ARTIFACTS = ('panel_enriched.pkl', 'volume_store.npy')
DEFAULT_CACHE = _REPO / 'nfl' / 'derived'

_READY = None


def cache_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get('NFL_DERIVED_DIR') or DEFAULT_CACHE)


def _sha(p) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def expected() -> dict:
    return {k: v['sha256']
            for k, v in json.loads(SPEC.read_text())['derived_artifacts'].items()}


def verify(d: pathlib.Path) -> Outcome:
    """Are all artifacts present in `d` and byte-identical to the frozen set?"""
    want = expected()
    got, bad = {}, []
    for a in ARTIFACTS:
        p = d / a
        if not p.exists():
            bad.append({'artifact': a, 'why': 'absent'})
            continue
        h = _sha(p)
        got[a] = h
        if want.get(a) and h != want[a]:
            bad.append({'artifact': a, 'why': 'hash differs',
                        'got': h[:16], 'want': want[a][:16]})
    if bad:
        return Outcome.fail('DERIVED_ARTIFACTS_UNVERIFIED',
                            f'{len(bad)} artifact(s) missing or wrong',
                            problems=bad)
    return Outcome.ok('DERIVED_ARTIFACTS_VERIFIED', value=str(d),
                      hashes={k: v[:16] for k, v in got.items()})


def _point_research_at_cache(d):
    """Tell the research loaders where production keeps the derived artifacts.

    Every research module that reads `panel_enriched.pkl` resolves it through
    `p4c_build.P4B`, which defaults to the research tree. Setting it in ONE
    place means a production layer cannot silently depend on a stale copy
    sitting in nfl/research/p4b -- which is exactly what the QB layer was
    doing, undetected, until that copy was removed.
    """
    try:
        import p4c_build as CB
    except ImportError:
        for q in ('p1', 'p2', 'p3', 'p4b', 'p4c', 'rc1', 's2', 'td2', 'qb2'):
            sys.path.insert(0, str(RESEARCH / q))
        import p4c_build as CB
    CB.P4B = str(d)
    return CB


def artifacts(build_if_missing: bool = True) -> Outcome:
    """The directory holding verified derived artifacts, building if needed.

    Building imports the regeneration module's PURE FUNCTIONS. It never invokes
    `regenerate.main()`, which is the part that writes into nfl/research.
    """
    global _READY
    if _READY is not None:
        _point_research_at_cache(_READY)
        return Outcome.ok('DERIVED_ARTIFACTS_READY', value=str(_READY),
                          cached=True)
    d = cache_dir()
    v = verify(d) if d.exists() else Outcome.fail('DERIVED_CACHE_ABSENT',
                                                  f'{d} does not exist')
    if v.state.name == 'PASS':
        _READY = d
        _point_research_at_cache(d)
        return Outcome.ok('DERIVED_ARTIFACTS_READY', value=str(d), cached=True,
                          **v.evidence)
    if not build_if_missing:
        return Outcome.blocked(
            'DERIVED_ARTIFACTS_NOT_BUILT',
            f'{v.code}: {v.detail}. Build them with '
            f'`python3.12 nfl/tools/build_derived.py`.', cause=Cause.DATA)
    return build(d)


def build(dest=None) -> Outcome:
    """Regenerate into a temp work tree, verify, then place in the cache."""
    global _READY
    import regenerate as REG
    d = pathlib.Path(dest) if dest else cache_dir()
    t0 = time.time()
    work = tempfile.mkdtemp(prefix='nfl_derived_')
    try:
        placed, _man = REG.stage_inputs(work)
        # THE MUTATION R3's FIX DID NOT CATCH, AND IT WAS THE LARGER ONE.
        # `stage_inputs` symlinks every file in the research code directories
        # into the work tree. When a previous build has left
        # panel_enriched.pkl and volume_store.npy sitting in nfl/research/p4b
        # -- they are gitignored, so `git status` says nothing -- the builders
        # open those names for writing with the work tree as cwd and write 138
        # MB straight THROUGH the symlinks into the research tree. R3 restored
        # the small JSON report and never saw this.
        #
        # Breaking the symlink here makes the build write into the work tree,
        # which is what it was always supposed to do.
        for _a in ARTIFACTS:
            _l = pathlib.Path(work) / 'p4b' / _a
            if _l.is_symlink():
                _l.unlink()
        out = REG.regenerate(work, json.loads(SPEC.read_text())['derived_artifacts'])
        bad = [n for n, r in out.items() if not r['byte_identical']]
        if bad:
            return Outcome.fail(
                'DERIVED_ARTIFACT_HASH_MISMATCH',
                f'{bad} did not reproduce byte-identically, so they are '
                f'refused rather than cached', artifacts=bad)
        d.mkdir(parents=True, exist_ok=True)
        for n, r in out.items():
            shutil.copy2(r['path'], d / n)
    except Exception as e:                                     # noqa: BLE001
        return Outcome.fail('DERIVED_BUILD_FAILED',
                            f'{type(e).__name__}: {e}'[:400])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    v = verify(d)
    if v.state.name != 'PASS':
        return v
    _READY = d
    _point_research_at_cache(d)
    return Outcome.ok('DERIVED_ARTIFACTS_BUILT', value=str(d), cached=False,
                      n_leaf_inputs_verified=len(placed),
                      seconds=round(time.time() - t0, 1), **v.evidence)


def reset():
    global _READY
    _READY = None


# ------------------------------------------------------------------ guard
def research_tree_hashes() -> dict:
    """Hash every tracked-shaped file under nfl/research."""
    out = {}
    for p in sorted(RESEARCH.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:
            continue
        out[str(p.relative_to(_REPO))] = _sha(p)
    return out


def assert_research_tree_unchanged(fn, *a, **kw) -> Outcome:
    """Snapshot, run production, assert the research tree is byte-identical.

    This is the hard test §I asks for. A production run that changes anything
    under nfl/research -- a report, a cache, a stray __pycache__ sibling -- is
    a FAIL naming the file, not a tidy-up afterwards.
    """
    before = research_tree_hashes()
    result = fn(*a, **kw)
    after = research_tree_hashes()
    changed = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    if not before:
        return Outcome.fail('RESEARCH_TREE_SNAPSHOT_EMPTY',
                            'no research file was hashed, so nothing was '
                            'proven')
    if changed:
        return Outcome.fail(
            'RESEARCH_TREE_MUTATED',
            f'{len(changed)} file(s) under nfl/research changed while '
            f'production ran: {changed[:5]}', changed=changed[:20],
            n_files_watched=len(before))
    return Outcome.ok('RESEARCH_TREE_IMMUTABLE', value=result,
                      n_files_watched=len(before),
                      detail=f'{len(before)} research files byte-identical '
                             f'across a production run')
