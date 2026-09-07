"""Gates must read their truth from the artifact. Rule 006 made executable.

The defect this exists to prevent happened on 2026-09-07, in P4E, to the agent
writing this module.

The P4E baseline gate had to reproduce P4C's published carry CRPS exactly. The
comparison values were written into the source as literals:

    PUBLISHED = {2022: 1.9295579791069031, ...}

They were wrong. `p4c_results.json` says 1.9295611633207923. The literal agreed
with the artifact to **four** decimal places -- exactly the precision printed by
`run_p4c.log` -- and diverged after it, because it had been copied off the log
line and the tail invented. The gate then failed at 1.8e-05 against a 1e-9
tolerance and cost a full diagnostic cycle: two wrong hypotheses, a literal
re-execution of the control, and a byte-comparison of the artifact, before the
answer turned out to be that nobody had ever read the number.

That is the same shape as the V7 defects Rule 001 exists for -- something never
actually read, reported as though it had been -- so it gets the same treatment:
a type that makes the wrong thing hard and the right thing one call.

Three properties, and the third is the one people skip:

  1. the comparison value is LOADED from the canonical artifact, not typed;
  2. the artifact's identity is HASHED and the hash travels with the value, so
     the run output can say which bytes it compared against;
  3. a value that arrives without that provenance is REFUSED rather than
     trusted, because a literal and a loaded value are indistinguishable once
     they are both just floats.

And one prohibition with a name: a display-rounded log is never gate truth.
`run_p4c.log` was not lying. It printed four decimals because four decimals is
what a human reads. Reading a gate constant out of it is the error.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
from typing import Any, Sequence

from .outcome import Cause, Outcome, State

# Formats whose whole purpose is to be read by a person. A gate that sources a
# number from one of these is sourcing a rounded rendering of a number.
DISPLAY_ONLY_SUFFIXES = ('.log', '.txt', '.out', '.md', '.rst')

# How many decimals a plausible hand transcription might carry. Used only to
# EXPLAIN a mismatch, never to accept one.
_MAX_TRANSCRIBED_DECIMALS = 12


class ArtifactReferenceError(RuntimeError):
    """Raised when a gate is constructed in a way that cannot be audited."""


@dataclasses.dataclass(frozen=True)
class ArtifactRef:
    """A value together with the bytes it came out of.

    Constructing this by hand with a typed value is possible -- Python always
    allows that -- which is why `verify` exists and why every gate calls it.
    """
    path: str
    sha256: str
    selector: tuple
    value: Any

    @property
    def short_sha(self) -> str:
        return self.sha256[:12]

    def describe(self) -> str:
        sel = '/'.join(str(s) for s in self.selector)
        return f'{os.path.basename(self.path)}[{sel}] sha256:{self.short_sha}'


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _walk(obj, selector: Sequence):
    cur = obj
    for key in selector:
        if isinstance(cur, dict):
            if key in cur:
                cur = cur[key]
                continue
            skey = str(key)
            if skey in cur:
                cur = cur[skey]
                continue
            raise KeyError(key)
        if isinstance(cur, (list, tuple)):
            cur = cur[int(key)]
            continue
        raise KeyError(key)
    return cur


def read_gate_value(path: str, selector: Sequence) -> Outcome:
    """Load one comparison value out of a canonical artifact, hash and all.

    Returns PASS carrying an ArtifactRef, or a named non-PASS. It never returns
    a bare number, because a bare number is exactly what cannot be audited.
    """
    if not isinstance(selector, (list, tuple)) or not selector:
        return Outcome.fail(
            'GATE_SELECTOR_MISSING',
            'a gate must say WHICH value in the artifact it is comparing '
            'against; an empty selector reads the whole file and means nothing',
            path=path)
    suffix = os.path.splitext(path)[1].lower()
    if suffix in DISPLAY_ONLY_SUFFIXES:
        return Outcome.blocked(
            'GATE_SOURCE_IS_DISPLAY_ONLY',
            f'{path} is a {suffix} rendering meant for a person to read. Its '
            f'numbers are rounded for display, so they are not gate truth. '
            f'Point the gate at the artifact the renderer was built from.',
            cause=Cause.GOVERNANCE, path=path)
    if not os.path.exists(path):
        return Outcome.blocked(
            'GATE_ARTIFACT_ABSENT', f'{path} does not exist, so there is '
            f'nothing to compare against. An absent artifact is not a passing '
            f'gate.', cause=Cause.DEPENDENCY, path=path)
    raw = open(path, 'rb').read()
    if not raw:
        return Outcome.blocked(
            'GATE_ARTIFACT_EMPTY', f'{path} is zero bytes.',
            cause=Cause.DATA, path=path)
    try:
        obj = json.loads(raw)
    except ValueError as exc:
        return Outcome.blocked(
            'GATE_ARTIFACT_UNPARSEABLE', f'{path}: {exc}',
            cause=Cause.DATA, path=path)
    try:
        value = _walk(obj, selector)
    except (KeyError, IndexError, TypeError, ValueError):
        return Outcome.fail(
            'GATE_SELECTOR_NOT_FOUND',
            f'{path} has no value at {list(selector)}. The gate cannot quietly '
            f'fall back to a literal.', path=path, selector=list(selector))
    if value is None:
        return Outcome.fail(
            'GATE_VALUE_NULL', f'{path}{list(selector)} is null.',
            path=path, selector=list(selector))
    ref = ArtifactRef(path=os.path.abspath(path), sha256=hashlib.sha256(raw).hexdigest(),
                      selector=tuple(selector), value=value)
    return Outcome.ok('GATE_VALUE_LOADED', ref,
                      detail=f'read {ref.describe()}',
                      sha256=ref.sha256, selector=list(selector))


def verify(ref: ArtifactRef) -> Outcome:
    """Re-read the artifact and prove the ref still describes it.

    This is what catches a hand-built ArtifactRef carrying a typed literal, and
    it is what catches an artifact that changed under a cached reference.
    """
    if not isinstance(ref, ArtifactRef):
        return Outcome.fail(
            'GATE_VALUE_UNSOURCED',
            f'{type(ref).__name__} is not an ArtifactRef, so this comparison '
            f'value has no artifact behind it. A gate may not compare against '
            f'a number that was typed rather than read.')
    fresh = read_gate_value(ref.path, ref.selector)
    if fresh.state is not State.PASS:
        return fresh
    live = fresh.unwrap()
    if live.sha256 != ref.sha256:
        return Outcome.fail(
            'GATE_ARTIFACT_CHANGED',
            f'{ref.path} now hashes to {live.short_sha}, not {ref.short_sha}. '
            f'The reference was taken against different bytes.',
            expected_sha256=ref.sha256, actual_sha256=live.sha256)
    if not _same(live.value, ref.value):
        hint = transcription_signature(ref.value, live.value)
        detail = (f'{ref.describe()} holds {live.value!r}, but this reference '
                  f'carries {ref.value!r}.')
        if hint is not None:
            detail += (f' The two agree to {hint} decimal places and diverge '
                       f'after, which is the signature of a value transcribed '
                       f'from a display rounding rather than read from the '
                       f'artifact.')
        return Outcome.fail('GATE_VALUE_NOT_FROM_ARTIFACT', detail,
                            artifact_value=live.value, reference_value=ref.value,
                            agreeing_decimals=hint)
    return Outcome.ok('GATE_REFERENCE_VERIFIED', ref,
                      detail=f'verified {ref.describe()}', sha256=ref.sha256)


def _same(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return float(a) == float(b) or (math.isnan(float(a))
                                            and math.isnan(float(b)))
        except (TypeError, ValueError):
            return False
    return a == b


def transcription_signature(literal, exact):
    """The number of decimals at which `literal` equals `exact`, if `literal`
    looks like a display rounding of it. None when it is simply a different
    number.

    Diagnostic only. It explains a mismatch; it never excuses one.
    """
    try:
        lit, ex = float(literal), float(exact)
    except (TypeError, ValueError):
        return None
    if lit == ex or not math.isfinite(lit) or not math.isfinite(ex):
        return None
    # The LARGEST agreeing precision, not the first. Two different numbers
    # almost always agree at one decimal; what identifies a transcription is
    # where the agreement STOPS -- 4 decimals for the P4E constant, which is
    # exactly what run_p4c.log printed.
    best = None
    for k in range(1, _MAX_TRANSCRIBED_DECIMALS + 1):
        if round(lit, k) == round(ex, k):
            best = k
    return best


def assert_gate(observed, path: str, selector: Sequence, *, tolerance: float,
                code: str) -> Outcome:
    """The whole rule in one call: load, verify, compare, and carry the hash.

    `tolerance` is absolute and must be stated by the caller. There is no
    default, because a default tolerance is a threshold nobody chose.
    """
    if tolerance < 0:
        raise ArtifactReferenceError(
            f'NEGATIVE_TOLERANCE: {tolerance!r} cannot be satisfied.')
    loaded = read_gate_value(path, selector)
    if loaded.state is not State.PASS:
        return loaded
    ref = loaded.unwrap()
    ok = verify(ref)
    if ok.state is not State.PASS:
        return ok
    try:
        diff = abs(float(observed) - float(ref.value))
    except (TypeError, ValueError):
        return Outcome.fail(
            f'{code}_UNCOMPARABLE',
            f'observed {observed!r} and artifact {ref.value!r} are not both '
            f'numbers.', reference=ref.describe())
    ev = dict(observed=float(observed), expected=float(ref.value),
              abs_diff=diff, tolerance=tolerance, sha256=ref.sha256,
              artifact=ref.path, selector=list(selector))
    if diff > tolerance:
        hint = transcription_signature(observed, ref.value)
        detail = (f'{observed!r} against {ref.describe()} = {ref.value!r}; '
                  f'|diff| {diff:.3e} exceeds {tolerance:.3e}')
        if hint is not None:
            detail += (f'. The two agree to {hint} decimals, so check whether '
                       f'the observed value came from a rendering rather than '
                       f'a computation')
        return Outcome.fail(code, detail, **ev)
    return Outcome.ok(code, float(observed),
                      detail=f'matches {ref.describe()} within {tolerance:.1e}',
                      **ev)
