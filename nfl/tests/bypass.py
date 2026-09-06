"""Helper for proving a guard is load-bearing. G0A test standard.

THE STANDARD, FROM OWNER DIRECTIVE 3 §8

    "A guard is not demonstrated merely because compliant data passes it. It
    must reject a seeded violation, and critical guards must demonstrate that
    removing/bypassing the guard causes the replay test to fail."

The second half is the part that is usually skipped, and it is the half that
matters. `assert_batch_games_are_new` is in this repository: it read a field no
row carried, so it PASSED ON EVERY INPUT IT WAS EVER GIVEN and had never once
refused anything. Every test of it passed. A test that would still pass with the
guard deleted is testing nothing.

USAGE

    with guard_bypassed('nfl.ingest.allowlist', 'assert_columns_allowed',
                        returns=Outcome.ok('STUB', value=[])):
        out = thing_under_test()          # the guard is now a no-op
    assert out did NOT catch the violation   # therefore the guard caught it

`assert_guard_is_load_bearing` wraps that into one call.
"""
from __future__ import annotations

import contextlib
import importlib
from typing import Any, Callable


@contextlib.contextmanager
def guard_bypassed(module_path: str, attr: str, returns: Any = None,
                   replacement: Callable = None):
    """Temporarily replace a guard with a no-op that always permits."""
    mod = importlib.import_module(module_path)
    if not hasattr(mod, attr):
        raise AttributeError(
            f'{module_path}.{attr} does not exist, so a test cannot claim to '
            f'bypass it. A bypass test pointed at a missing guard would pass '
            f'vacuously.')
    original = getattr(mod, attr)
    stub = replacement if replacement is not None else (lambda *a, **k: returns)
    setattr(mod, attr, stub)
    try:
        yield
    finally:
        setattr(mod, attr, original)


def assert_guard_is_load_bearing(*, run, module_path: str, attr: str,
                                 caught: Callable[[Any], bool],
                                 returns: Any = None,
                                 replacement: Callable = None) -> None:
    """Assert both halves in one call.

      1. with the guard in place, `run()` produces a result `caught()` accepts;
      2. with the guard bypassed, it does NOT -- proving (1) came from the guard.

    `run` must be a zero-argument callable that re-executes the code path; it is
    called twice.
    """
    with_guard = run()
    if not caught(with_guard):
        raise AssertionError(
            f'{module_path}.{attr}: the seeded violation was NOT caught with '
            f'the guard in place. Got {with_guard!r}. The guard does not work.')

    with guard_bypassed(module_path, attr, returns=returns,
                        replacement=replacement):
        without_guard = run()

    if caught(without_guard):
        raise AssertionError(
            f'{module_path}.{attr}: the violation was still caught with the '
            f'guard BYPASSED, so this test does not depend on the guard and '
            f'would pass if the guard were deleted. Got {without_guard!r}. '
            f'This is the assert_batch_games_are_new failure: a test that '
            f'proves nothing.')
