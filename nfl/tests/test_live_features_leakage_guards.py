#!/usr/bin/env python3.12
"""The live feature builder's leakage guards, proven through build().

These four sit in nfl/prospective/q9shadow/live_features.py and the census had
them NOT_ESTABLISHED. `build()` does propagate them --

    for g in (assert_sources_permitted(sources),
              assert_no_roster_status(players),
              assert_feature_schema_matches_freeze()):
        if g.state is not State.PASS:
            return g

-- but reading that is not proving it, so nothing was classified on the strength
of the reading. This file drives a seeded violation through the real entry point
for each one, and bypasses each to show the refusal was the guard's.

THE PROPAGATION IS VISIBLE BECAUSE OF AN ACCIDENT OF ORDER, and the tests lean on
it deliberately: the guards run BEFORE build's own Q9_LIVE_NO_TEAMS check, so a
clean call with no team frame returns NO_TEAMS while a seeded call returns the
guard's own code. Bypassing the guard makes the seeded call fall through to
NO_TEAMS too, which is exactly the signal that the guard was what caught it.

A NOTE ON THE BYPASS STUB. `nfl/tests/bypass.py` replaces a guard with
`lambda *a, **k: returns`, so `returns` must match the guard's PASS SHAPE. These
guards return `Outcome.ok` on pass, unlike the team_volume_v1 coupling guards
which return `None`, and stubbing these with None makes build() raise on
`None.state` rather than proceed. The stub is an Outcome here for that reason.

WHAT THEY PROTECT. Roster status, official inactives and player stats are
post-decision information for a pregame forecast. `assert_no_live_outcome` puts
it best, and it is this repository's central invariant at the leakage boundary:
"Every realised field must be PRESENT and None -- omitting it would let a later
`.get` default it to zero, which is how an unplayed game acquires a realised
result."
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from nfl.prospective.q9shadow import live_features as LF
from nfl.tests import bypass as BP
from sportsplatform.governance.outcome import Outcome, State

passed = failed = 0
MOD = 'nfl.prospective.q9shadow.live_features'
#: build()'s own refusal, reached only once every guard above it has passed.
DOWNSTREAM = 'Q9_LIVE_NO_TEAMS'
PERMISSIVE = Outcome.ok('STUB_PERMITS', None, 'bypass stub, matches pass shape')

CLEAN = [{'gsis_id': '00-0000001', 'pos': 'WR'}]


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def build(players=None, sources=None):
    return LF.build(2026, 3, players if players is not None else CLEAN,
                    '2026-09-20T12:00:00Z', sources=sources)


def propagates(label, attr, seeded, code):
    """Seeded violation -> the guard's code out of build(); bypassed -> not."""
    with_guard = build(**seeded)
    check(f'{label}: build returns the guard code',
          with_guard.code == code, f'got {with_guard.code}')
    with BP.guard_bypassed(MOD, attr, returns=PERMISSIVE):
        without = build(**seeded)
    check(f'{label}: bypassed, the violation is NOT caught',
          without.code != code, f'still {without.code}, so this proves nothing')
    check(f'{label}: and it falls through to build\'s own refusal',
          without.code == DOWNSTREAM, without.code)


def test_a_clean_call_reaches_builds_own_refusal_not_a_guard():
    """The ordering this file depends on, asserted rather than assumed."""
    o = build()
    check('a clean call passes every guard and reaches NO_TEAMS',
          o.code == DOWNSTREAM, f'{o.state.value}[{o.code}]')


def test_a_supplied_roster_status_field_is_refused():
    # Roster status is post-decision information. A pregame feature build that
    # accepted it would be conditioning on the answer.
    for field in sorted(LF.ROSTER_STATUS_FIELDS):
        o = build(players=[{'gsis_id': '00-0000001', 'pos': 'WR', field: 'ACT'}])
        check(f'a descriptor carrying {field!r} is refused',
              o.code == 'Q9_LIVE_ROSTER_STATUS_SUPPLIED',
              f'{o.state.value}[{o.code}]')
    propagates('roster status', 'assert_no_roster_status',
               dict(players=[{'gsis_id': '00-0000001', 'roster_status': 'ACT'}]),
               'Q9_LIVE_ROSTER_STATUS_SUPPLIED')


def test_every_forbidden_source_is_refused_by_name():
    for src in sorted(LF.FORBIDDEN_SOURCES):
        o = build(sources=[src])
        check(f'{src} is refused', o.code == 'Q9_LIVE_SOURCE_NOT_PERMITTED',
              f'{o.state.value}[{o.code}]')
    propagates('forbidden source', 'assert_sources_permitted',
               dict(sources=['weekly_rosters']), 'Q9_LIVE_SOURCE_NOT_PERMITTED')


def test_a_permitted_source_is_not_refused():
    """The inverted check. A guard that refuses every source is not a guard."""
    for src in sorted(LF.PERMITTED_SOURCES):
        o = build(sources=[src])
        check(f'{src} is permitted', o.code != 'Q9_LIVE_SOURCE_NOT_PERMITTED',
              f'{o.state.value}[{o.code}]')


def test_a_feature_schema_that_drifted_from_the_freeze_is_refused():
    """A builder emitting a different schema is building for a different
    candidate, so the hash must match the frozen one."""
    o = LF.assert_feature_schema_matches_freeze()
    check('the live schema currently matches the freeze',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')
    real = LF.Q9.FEATURE_NAMES
    try:
        LF.Q9.FEATURE_NAMES = tuple(list(real) + ['a_feature_nobody_froze'])
        drifted = LF.assert_feature_schema_matches_freeze()
        check('a drifted schema refuses',
              drifted.code == 'Q9_LIVE_FEATURE_SCHEMA_MISMATCH',
              f'{drifted.state.value}[{drifted.code}]')
        check('  and the refusal carries both hashes',
              drifted.evidence.get('live') and drifted.evidence.get('frozen')
              and drifted.evidence['live'] != drifted.evidence['frozen'],
              drifted.evidence)
        out = build()
        check('  and build() refuses rather than emitting features',
              out.code == 'Q9_LIVE_FEATURE_SCHEMA_MISMATCH', out.code)
    finally:
        LF.Q9.FEATURE_NAMES = real
    check('the schema is restored',
          LF.assert_feature_schema_matches_freeze().state is State.PASS)


def test_an_absent_freeze_artifact_blocks_rather_than_passes():
    """NOT_EVALUATED is not PASS. With no freeze there is nothing to compare
    against, and the guard must say so rather than wave the build through."""
    real = LF.CAND.freeze_identity
    try:
        LF.CAND.freeze_identity = lambda *a, **k: None
        o = LF.assert_feature_schema_matches_freeze()
        check('no freeze artifact -> BLOCKED, not PASS',
              o.state is not State.PASS
              and o.code == 'Q9_FREEZE_ARTIFACT_ABSENT',
              f'{o.state.value}[{o.code}]')
        check('  and build() stops there too',
              build().code == 'Q9_FREEZE_ARTIFACT_ABSENT')
    finally:
        LF.CAND.freeze_identity = real


def test_a_realised_field_must_be_present_and_None_not_absent():
    """assert_no_live_outcome, the invariant stated at the leakage boundary.

    Its own words: omitting a realised field would let a later `.get` default it
    to zero, "which is how an unplayed game acquires a realised result". So an
    ABSENT field is as much a violation as a populated one, and both are checked.
    """
    f = sorted(LF.REALISED_FIELDS)[0]
    present_none = {'pid': 'p1', 's': 2026, **{k: None for k in LF.REALISED_FIELDS}}
    o = LF.assert_no_live_outcome([present_none], 2026)
    check('every realised field present and None is clean',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')

    populated = dict(present_none, **{f: 7})
    o = LF.assert_no_live_outcome([populated], 2026)
    check(f'a populated {f} is refused',
          o.code == 'Q9_LIVE_ROW_CARRIES_AN_OUTCOME', o.code)

    omitted = {k: v for k, v in present_none.items() if k != f}
    o = LF.assert_no_live_outcome([omitted], 2026)
    check(f'an OMITTED {f} is refused too, not treated as clean',
          o.code == 'Q9_LIVE_ROW_CARRIES_AN_OUTCOME',
          f'{o.state.value}[{o.code}] -- absence must not read as zero')

    older = dict(populated, s=2025)
    o = LF.assert_no_live_outcome([older], 2026)
    check('a row from an EARLIER season may carry its outcome',
          o.state is State.PASS, f'{o.state.value}[{o.code}]')


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_live_features_leakage_guards: {passed} ok, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
