"""The six identities a run has, separated, and the one invariant that binds them.

    A  committed source identity      git commit sha of HEAD
    B  dirty source-content identity  sha256 over the CONTENT of dirty SOURCE
    C  runtime / environment identity interpreter + numeric library versions
    D  generated artifact state       a run's own outputs -- EXCLUDED FROM ALL
    E  predictive candidate identity  spec_sha256 / candidate freeze -- not here
    F  execution / run identity       ExecutionIdentity.fingerprint() over A,B,C,E
                                      and the consumed input hashes

THE INVARIANT

    A run must not change its own identity by writing its own outputs.

    F = f(A, B, C, E, inputs)          and                dF/dD = 0

THE DEFECT THIS REPLACES, STATED EXACTLY

`seal._code_commit()` returned `<sha> + '+dirty[' + N + ']'` where N was
`len(git status --porcelain)` -- a COUNT OF LINES describing the working tree at
the instant of the call. Three separate workstreams (WS01, WS18 F3, WS19) found
the same thing independently, and WS18 measured it live: two bit-identical draw
sets, sealed seconds apart in one process, received two different execution
identities (`9c67f1d2632b99a9` then `cad791b9ccb99e5e`) because a file appeared
and vanished in the tree meanwhile. The sealing path's OWN outputs move that
count -- run 1 writes `dryrun/proof/...`, so run 2 sees a different tree -- which
is `dF/dD != 0`. Measured on this checkout at HEAD 837d52f, 2026-09-14:

    before writing anything          ...+dirty[30]
    after one output directory       ...+dirty[31]
    after a second output directory  ...+dirty[32]
    after deleting both              ...+dirty[30]

Nothing about the forecast changed in any of those four calls.

A count has a second failure, in the opposite direction and worse: it does not
identify anything. Any two working trees with the same NUMBER of dirty paths
produce the same string. A tree with an edited `layers.py` and a tree with an
unrelated scratch note are indistinguishable in the sealed bytes. The artifact
said THAT the tree was dirty and never said HOW, so WS19 classified working-tree
state NOT_RECOVERABLE on every sealed run it tested.

WHY THE REPAIR IS NOT "A BETTER COUNT"

Replacing `len(porcelain)` with `sha256(porcelain)` fixes the aliasing and keeps
the self-reference: porcelain output still names every generated file, so a run
that writes an output still changes its own digest. Both halves have to move at
once, and the half that actually decides it is the SCOPE, not the hash:

    hash, not count      -- so two different trees cannot alias to one identity
    SOURCE, not tree     -- so a run's own products are not part of its identity

SCOPE, AND WHY IT IS INSIDE THE DIGEST

`SOURCE_ROOTS` x `SOURCE_SUFFIXES` minus `EXCLUDED_SUBTREES` is the declared
scope. The declaration itself is hashed into the digest, so a later widening or
narrowing of the scope cannot produce a digest that aliases to one computed
under the old rule. Changing what identity MEANS changes the identity.

WHAT IS DELIBERATELY OUT OF SCOPE, AND WHY -- `nfl/research/**`

Research modules are not uniformly irrelevant: `nfl.research.q9.hurdle`,
`nfl.research.q9b.family` and `nfl.research.q9b.production_parity` are causal for
the Q9 candidate. They are already hashed INDIVIDUALLY AND BY CONTENT into
`module_source_sha16`, which is inside `spec_sha256` (identity E), which is
inside the fingerprint (F). So a change to a causal research module already moves
the run identity, through E, without `nfl/research/**` being in B.

Putting the whole of `nfl/research/**` into B would instead add several thousand
non-causal files -- write-ups, one-off scripts, every workstream's notes -- whose
churn would move every run id for no causal reason. That is the same defect class
as the dirty count, arriving more slowly. So: out of scope, by decision, recorded
here rather than left to be inferred. `RESIDUAL_GAPS` names what that costs.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

CONTRACT_VERSION = 'nfl-code-identity-1'

# ---------------------------------------------------------------------------
# A + B -- what counts as SOURCE
# ---------------------------------------------------------------------------
#
# The shipped path plus the governance library. A change to any of it can change
# a number, so it belongs in the identity.
SOURCE_ROOTS = (
    'nfl/production',
    'nfl/prospective',
    'nfl/identity',
    'nfl/product',
    'nfl/schema',
    'nfl/tools',
    'sportsplatform',
)

# Source is CODE. A `.json` written next to a module is an artifact, not source,
# and this single rule is what keeps every run product out of B even when it
# lands inside a source root.
SOURCE_SUFFIXES = ('.py',)

# ---------------------------------------------------------------------------
# D -- generated artifact state, named so it can be asserted rather than assumed
# ---------------------------------------------------------------------------
#
# Every path here is a place a RUN writes. The suffix rule above already excludes
# all of it; this list is the belt to that braces, and it is what
# `nfl/tests/test_execution_identity.py` iterates when it proves dF/dD = 0. A
# future `.py` dropped into one of these -- a generated module, a scratch script
# beside a proof -- would otherwise silently re-enter the identity.
EXCLUDED_SUBTREES = (
    'nfl/prospective/q9shadow/dryrun',
    'nfl/prospective/q9shadow/sealed',
    'nfl/production/runs',
    'nfl/derived',
    'nfl/research',
    'nfl/vintage',
)

GENERATED_SUBTREES = EXCLUDED_SUBTREES

# ---------------------------------------------------------------------------
# C -- runtime identity: what is hashed, what is only recorded
# ---------------------------------------------------------------------------
#
# HASHED: things that can change a number and that a rerun can hold fixed.
# numpy's version is in because the draws come out of `numpy.random` and its
# reductions; the interpreter version is in because 3.11 cannot even parse parts
# of the sibling MLB engine, which is how cheap an interpreter difference can be.
RUNTIME_HASHED_KEYS = ('implementation', 'python_version', 'numpy_version')

# RECORDED, NOT HASHED, and each for a stated reason:
#
#   platform      hashing it makes every machine a different identity BY
#                 CONSTRUCTION, which would define away the cross-machine
#                 reproduction question WS18 calls its largest evidence gap. You
#                 cannot demonstrate two machines agreeing if agreement is
#                 impossible by definition. Recorded so a machine difference is
#                 visible to a reader; not hashed so it stays a question.
#
#   thread_env    OMP/MKL/OPENBLAS thread counts can change BLAS reduction order
#                 and therefore the last bits of a float. Plausible, and NOT
#                 MEASURED here. Hashing an unmeasured cause would put a silent
#                 constant inside the identity. Recorded, and RESIDUAL_GAPS says
#                 what would promote it.
RUNTIME_RECORDED_KEYS = ('platform', 'thread_env')

_THREAD_ENV = ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
               'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')

RESIDUAL_GAPS = (
    'IMPORTED_RESEARCH_MODULES_NOT_IN_B: a research module that the sealing '
    'path imports but that is not one of the four in module_source_sha16 -- '
    'nfl.research.q7.panel and nfl.research.q8.audit are the live examples -- '
    'is in neither B nor E. Remedy: hash each imported module file by content '
    'into the candidate identity. That is candidate.py, not this module.',
    'NON_PY_SOURCE_NOT_IN_B: a frozen parameter file under a source root '
    '(nfl/production/nonqb/frozen/*.json.gz) is not source by SOURCE_SUFFIXES. '
    'For Q9 these are covered by the candidate parameter hashes in E. Remedy '
    'elsewhere: seal the resolved path and sha256, which is WS18 F1.',
    'THREAD_ENV_RECORDED_NOT_HASHED: promote to RUNTIME_HASHED_KEYS if and '
    'when a measured draw difference is attributed to thread count. Not '
    'before -- an unmeasured coefficient in an identity is a silent constant.',
    'STAGING_NOT_DISTINGUISHED: B hashes worktree CONTENT, so a staged and an '
    'unstaged edit of identical bytes are the same identity. Deliberate: the '
    'bytes the interpreter reads are the bytes that matter.',
)

# The digest of an empty dirty set. A clean tree is not a special case with its
# own format; it is this value. Recomputed, never typed in.
_CLEAN_SENTINEL: Optional[str] = None


def _git(args):
    try:
        r = subprocess.run(['git'] + list(args), cwd=str(_REPO),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if r.returncode != 0:
        return None, (r.stderr or '').strip() or f'git {args[0]} exit {r.returncode}'
    return r.stdout, None


def in_source_scope(relpath: str) -> bool:
    """Is this path SOURCE for the purposes of identity B?

    Three tests, in the order that makes the reason readable when it says no.
    """
    p = relpath.replace('\\', '/').lstrip('./')
    if not any(p == r or p.startswith(r + '/') for r in SOURCE_ROOTS):
        return False
    if any(p == x or p.startswith(x + '/') for x in EXCLUDED_SUBTREES):
        return False
    return p.endswith(SOURCE_SUFFIXES)


def _porcelain_paths():
    """Every differing path, one per file. Returns (paths, error).

    `-uall` is load-bearing. Without it git COLLAPSES an untracked directory to
    a single entry, so a new `.py` inside an already-untracked directory would
    be invisible to B -- silently, and exactly for new code.
    """
    out, err = _git(['status', '--porcelain', '-z', '-uall'])
    if out is None:
        return None, err
    paths, toks, i = [], out.split('\0'), 0
    while i < len(toks):
        t = toks[i]
        i += 1
        if not t.strip():
            continue
        xy, path = t[:2], t[3:]
        if xy and xy[0] == 'R':
            # `R  new\0old`. Both sides are real changes to the tree.
            if i < len(toks):
                paths.append(toks[i])
                i += 1
        paths.append(path)
    return paths, None


def _digest_entries(entries) -> str:
    """sha256 over the entries AND the scope declaration that produced them.

    Sorted HERE, not by the caller, so the digest cannot depend on the order git
    happened to report paths in. `partitions` in `ExecutionIdentity.as_dict()`
    is sorted for the same reason and the reason is worth keeping in one place:
    a fingerprint that depends on read order is a fingerprint that moves for
    nothing.
    """
    blob = json.dumps({
        'contract_version': CONTRACT_VERSION,
        'source_roots': list(SOURCE_ROOTS),
        'source_suffixes': list(SOURCE_SUFFIXES),
        'excluded_subtrees': list(EXCLUDED_SUBTREES),
        'entries': sorted(entries, key=lambda e: e['path']),
    }, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(blob).hexdigest()


def clean_source_digest() -> str:
    """The B digest of a tree with no dirty source. Computed, not a literal."""
    global _CLEAN_SENTINEL
    if _CLEAN_SENTINEL is None:
        _CLEAN_SENTINEL = _digest_entries([])
    return _CLEAN_SENTINEL


def runtime_identity() -> dict:
    """C. Everything recorded; RUNTIME_HASHED_KEYS is the part inside F."""
    try:
        import numpy as _np
        npv = str(_np.__version__)
    except Exception:                                            # noqa: BLE001
        npv = 'ABSENT'
    return {
        'implementation': platform.python_implementation(),
        'python_version': platform.python_version(),
        'numpy_version': npv,
        'platform': platform.platform(),
        'thread_env': {k: os.environ.get(k) for k in _THREAD_ENV},
        'hashed_keys': list(RUNTIME_HASHED_KEYS),
        'recorded_not_hashed_keys': list(RUNTIME_RECORDED_KEYS),
    }


def runtime_token(rt: Optional[dict] = None) -> str:
    """The C value that goes INTO the fingerprint, as a readable string.

    This is what `ExecutionIdentity.interpreter` carries. The field already
    existed and held `python3.12` -- a value so coarse that WS19 classified
    interpreter and library versions NOT_RECOVERABLE on every run it read.
    """
    rt = rt or runtime_identity()
    return '+'.join(f'{k}={rt.get(k)}' for k in RUNTIME_HASHED_KEYS)


def code_identity() -> Outcome:
    """A, B, C and the reconstruction material, or a named refusal.

    PASS value is a dict that is written verbatim into the sealed artifact. It
    carries the per-file digest MATERIAL, not only the rolled-up digest, because
    a digest nobody can reconstruct is a number you can compare and cannot audit
    -- and WS19's whole finding was that the sealed bytes could not answer the
    question at all.
    """
    rev, err = _git(['rev-parse', 'HEAD'])
    if rev is None:
        return Outcome.blocked(
            'CODE_IDENTITY_NO_COMMIT',
            f'git rev-parse HEAD failed ({err}). A run whose committed source '
            f'cannot be named is not identifiable, and the old behaviour -- '
            f'substituting the literal string UNKNOWN and sealing anyway -- '
            f'produced an artifact that claimed an identity it did not have.',
            cause=Cause.ENVIRONMENT)
    commit = rev.strip()

    paths, err = _porcelain_paths()
    if paths is None:
        return Outcome.blocked(
            'CODE_IDENTITY_NO_WORKTREE_STATE',
            f'git status failed ({err}). Dirty source cannot be digested, so '
            f'identity B is unknown; sealing on the commit alone would assert '
            f'a clean tree that was never checked.',
            cause=Cause.ENVIRONMENT)

    entries, seen = [], set()
    for p in paths:
        if p in seen or not in_source_scope(p):
            continue
        seen.add(p)
        f = _REPO / p
        if f.is_file():
            b = f.read_bytes()
            entries.append({'path': p, 'state': 'PRESENT',
                            'sha256': hashlib.sha256(b).hexdigest(),
                            'bytes': len(b)})
        else:
            entries.append({'path': p, 'state': 'ABSENT',
                            'sha256': None, 'bytes': None})
    entries.sort(key=lambda e: e['path'])

    digest = _digest_entries(entries)
    rt = runtime_identity()
    ident = {
        'contract_version': CONTRACT_VERSION,
        # A
        'commit': commit,
        # B
        'source_scope_sha256': digest,
        'source_scope_clean': not entries,
        'dirty_source_files': entries,
        'n_dirty_source_files': len(entries),
        # THE DEMOTED COUNT IS NOT HERE, AND THE REASON IS WORTH THE LINES.
        #
        # A first version of this repair kept `len(porcelain)` in this dict as
        # `n_dirty_tree_entries_recorded_not_hashed` -- outside the digest,
        # "recorded, not hashed", purely so a reader could watch it move while
        # the identity did not. It is outside `source_scope_sha256`, outside
        # `code_version`, outside `ExecutionIdentity`, and therefore outside
        # `identity_fingerprint` and `artifact_id`.
        #
        # THE Q9 DRY-RUN PROOF CAUGHT IT ANYWAY, and it was right to. This whole
        # dict is written into the artifact as `code_identity`, and the artifact
        # minus two keys IS the sealed payload -- so the count reached
        # `seal_payload_sha256` and `forecast_id`. Run 1 wrote its outputs, the
        # whole-tree count went up, and run 2 sealed a different forecast_id for
        # byte-identical draws. Measured, not argued: ARI Q9SH-67ccb0832ee54741
        # then Q9SH-440b173d2f5a2556, while `artifact_id` and
        # `identity_fingerprint` stayed equal.
        #
        # The generalised rule, which is stronger than "keep it out of the
        # digest": NOTHING THAT READS GENERATED ARTIFACT STATE (D) MAY ENTER THE
        # SEALED BODY, whether or not it is hashed into the fingerprint, because
        # the body is hashed into an identity of its own. The count survives as
        # Outcome evidence below, where it is a diagnostic and not a sealed byte.
        'scope': {
            'source_roots': list(SOURCE_ROOTS),
            'source_suffixes': list(SOURCE_SUFFIXES),
            'excluded_subtrees': list(EXCLUDED_SUBTREES),
            'generated_subtrees_excluded': list(GENERATED_SUBTREES),
            'research_out_of_scope_why':
                'causal research modules are hashed by content into '
                'module_source_sha16, which is inside spec_sha256 (identity E), '
                'which is inside the fingerprint. Adding nfl/research/** to B '
                'would move every run id for thousands of non-causal files.',
        },
        # C
        'runtime': rt,
        'runtime_token': runtime_token(rt),
        'clean_source_sentinel_sha256': clean_source_digest(),
        'residual_gaps': list(RESIDUAL_GAPS),
    }
    ident['code_version'] = code_version(ident)
    return Outcome.ok(
        'CODE_IDENTITY_RESOLVED', value=ident,
        detail=f'{commit[:12]} with {len(entries)} dirty source file(s) '
               f'digested by content; {len(paths)} dirty tree entries total, '
               f'which the identity does not read',
        code_version=ident['code_version'],
        n_dirty_source_files=len(entries),
        # DIAGNOSTIC ONLY, and deliberately not in `ident`. See above.
        n_dirty_tree_entries_observed=len(paths))


def code_version(ident: dict) -> str:
    """A and B as one string, in ONE format whether or not the tree is dirty.

    `<40-hex commit>+src1[<16 hex of the B digest>]`

    A single format on purpose. A string that reads `<sha>` when clean and
    `<sha>+something` when dirty invites a parser with two branches, and the
    branch nobody exercises is the one that is wrong. A clean tree is not absent
    from the format; it is `clean_source_digest()`.
    """
    return f'{ident["commit"]}+src1[{ident["source_scope_sha256"][:16]}]'


KEYS_ON_COUNT_MARKER = '+dirty['


def refuses_count_keyed(code_version_string: str) -> bool:
    """True if this string is the withdrawn count-keyed form."""
    return KEYS_ON_COUNT_MARKER in str(code_version_string)
