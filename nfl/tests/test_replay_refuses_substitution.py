#!/usr/bin/env python3.12
"""ENG-001, the three acceptance criteria its own test never asserted.

`nfl/tests/test_replay_pins_its_inputs.py` proves the POSITIVE half of ENG-001:
an ORIGINAL_REPLAY reproduces the seal's input digest and re-selecting at the
same clock does not. That is the D23 measurement and it stands.

But ENG-001's acceptance list in coordination/ENGINEERING_QUEUE.json names seven
criteria, and three of them are about what must NOT happen:

    3. missing sealed inputs fail closed
    4. current source availability cannot substitute for a missing sealed
       artifact
    7. NEGATIVE FIXTURE: historical seal A + current manifest containing newer
       source B -> replay consumes A only

None of those was asserted anywhere. `bundle_from_partition_ids` claims the
behaviour in its own docstring -- "resolves exactly those, or it refuses. A
missing partition is never replaced by the nearest lawful blob: that would
produce a different forecast and present it as the original" -- and a docstring
is not a test. This file asserts it, and asserts criteria 5 and 6 with it.

WHY THE PRECONDITION IS ASSERTED RATHER THAN ASSUMED. Criterion 7 only means
anything while the manifest actually holds newer observations of the sealed
sources. If the manifest stopped growing, "replay consumed A only" would be
trivially true and this file would pass while measuring nothing. The sibling test
already names that trap for the digest check -- "if this reads AGREES_TODAY the
manifest has stopped growing and the defect is dormant, which is not the same as
fixed". So the newer-observation premise is a CHECK here, not a background
assumption, and it fails loudly rather than passing vacuously.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from nfl.prospective.q9shadow import inputs as INP
from nfl.research.shadow import information_set as ISET
from nfl.research.shadow import replay_contract as RC
from sportsplatform.governance.outcome import State

passed = failed = blocked_count = 0

SEAL = (_REPO / 'nfl/prospective/q9shadow/dryrun/2024_01_ARI_BUF/ARI'
        / 'SEALED_FORECAST.json')
_CACHE = {}


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def blocked(label, why):
    global blocked_count
    blocked_count += 1
    print(f'  BLOCKED {label}  {why}')


def _find(o, key):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                yield v
            yield from _find(v, key)
    elif isinstance(o, list):
        for v in o:
            yield from _find(v, key)


def seal():
    """(consumed_partition_ids, kickoff_utc) from the real sealed forecast."""
    if 'seal' not in _CACHE:
        if not SEAL.exists():
            _CACHE['seal'] = (None, None)
        else:
            art = json.loads(SEAL.read_text())
            ids = next(iter(_find(art, 'consumed_partition_ids')), None)
            ko = next(iter(_find(art, 'kickoff_utc')), None)
            _CACHE['seal'] = (list(ids) if ids else None, ko)
    return _CACHE['seal']


def test_1_a_missing_sealed_input_fails_closed():
    """Criterion 3. A partition the manifest does not hold is a refusal."""
    ids, ko = seal()
    if not ids:
        blocked('criterion 3', 'no sealed forecast to take real ids from')
        return
    o = INP.bundle_from_partition_ids(ids + ['injuries@deadbeefdeadbeef'], ko)
    check('one unavailable partition refuses the whole build',
          o.state is not State.PASS, f'{o.state.value}[{o.code}]')
    check('  named ORIGINAL_PARTITION_UNAVAILABLE',
          o.code == 'ORIGINAL_PARTITION_UNAVAILABLE', o.code)
    miss = o.evidence.get('missing') or []
    check('  and it names WHICH partition and why',
          any(m.get('partition_id') == 'injuries@deadbeefdeadbeef'
              and m.get('why') == 'NOT_IN_MANIFEST' for m in miss), miss)
    # Six good partitions do not buy a seventh. A partial input set presented as
    # the original is the exact failure this refusal exists to prevent.
    check('  the six resolvable partitions do NOT yield a partial bundle',
          o.value in (None, {}) or not (o.value or {}).get('sources'),
          str(o.value)[:120])


def test_2_an_empty_recorded_set_is_not_an_empty_input_set():
    """Criterion 3, the degenerate case. Missing is a state, not zero inputs."""
    for empty in ([], None, ()):
        o = INP.bundle_from_partition_ids(empty, '2026-09-13T12:00:00Z')
        check(f'{empty!r} refuses rather than building an empty bundle',
              o.state is not State.PASS and o.code == 'NO_RECORDED_PARTITIONS',
              f'{o.state.value}[{o.code}]')


def test_3_a_malformed_partition_id_refuses_by_name():
    """A bypass shape: an id that cannot be parsed must not be skipped."""
    for bad in ('injuries', '', None, 'no-at-sign', '@abc', 123):
        try:
            RC.parse_partition_id(bad)
            check(f'{bad!r} refuses at the parser', False, 'returned a value')
        except RC.ReplayRefusal as exc:
            check(f'{bad!r} refuses at the parser',
                  exc.code == 'PARTITION_ID_MALFORMED', exc.code)
    # And the refusal survives the boundary as an Outcome rather than escaping
    # as a traceback, because every stage here owes a NAMED outcome.
    o = INP.bundle_from_partition_ids(['not-a-partition-id'],
                                      '2026-09-13T12:00:00Z')
    check('a malformed id reaching the builder becomes a named FAIL',
          o.state is not State.PASS and o.code == 'PARTITION_ID_MALFORMED',
          f'{o.state.value}[{o.code}]')


def test_4_the_manifest_really_does_hold_newer_observations():
    """The PREMISE of criterion 7, asserted so it cannot pass vacuously.

    If every sealed source had exactly one observation, "replay consumed only
    what the seal recorded" would be true by having nothing else to choose.
    """
    ids, _ = seal()
    if not ids:
        blocked('criterion 7 premise', 'no sealed forecast')
        return
    by_src = {}
    for (src, sha), obs in ISET.first_observation().items():
        by_src.setdefault(src, []).append((obs['observed_at'], sha[:16]))
    thin = []
    for pid in ids:
        src, addr = RC.parse_partition_id(pid)
        obs = sorted(by_src.get(src, []))
        newest = obs[-1][1] if obs else None
        if len(obs) < 2 or newest == addr[:16]:
            thin.append({'source': src, 'n_observations': len(obs),
                         'sealed': addr[:16], 'newest': newest})
    check('every sealed source has a NEWER observation available to be wrongly '
          'substituted, so criterion 7 is a real test',
          not thin,
          f'{thin} -- if the manifest stopped growing this file measures '
          f'nothing, which is not the same as the defect being fixed')


def test_5_the_negative_fixture_replay_consumes_the_seal_not_the_newer_source():
    """Criteria 4, 5 and 7 together, on the real seal and the real manifest."""
    ids, ko = seal()
    if not ids:
        blocked('criteria 4/5/7', 'no sealed forecast')
        return
    o = INP.bundle_from_partition_ids(ids, ko)
    check('the pinned build resolves', o.state is State.PASS,
          f'{o.state.value}[{o.code}]')
    if o.state is not State.PASS:
        return
    got = {s: r['sha256'][:16] for s, r in (o.value['sources'] or {}).items()}
    want = {}
    for pid in ids:
        src, addr = RC.parse_partition_id(pid)
        want[src] = addr[:16]
    check('every source resolves to the RECORDED content, not the newest',
          got == want, {s: (want.get(s), got.get(s))
                        for s in set(want) | set(got) if want.get(s) != got.get(s)})
    check('  and no extra source entered the bundle',
          set(got) == set(want), sorted(set(got) ^ set(want)))
    check('  the bundle is stamped as pinned',
          o.evidence.get('pinned') is True, o.evidence.get('pinned'))


def test_6_the_clock_bounds_selection_it_does_not_determine_it():
    """Criterion 6. The pinned set must not move when the clock moves.

    `kickoff_utc` is documented as affecting only reported
    hours_before_kickoff. If it could change WHICH partitions resolve, the
    pinned path would be selecting after all.
    """
    ids, ko = seal()
    if not ids:
        blocked('criterion 6', 'no sealed forecast')
        return
    a = INP.bundle_from_partition_ids(ids, ko)
    b = INP.bundle_from_partition_ids(ids, '2030-01-01T00:00:00Z')
    if a.state is not State.PASS or b.state is not State.PASS:
        check('both clocks build', False, f'{a.code} / {b.code}')
        return
    ha = {s: r['sha256'] for s, r in a.value['sources'].items()}
    hb = {s: r['sha256'] for s, r in b.value['sources'].items()}
    check('a six-year-later clock resolves the identical content', ha == hb,
          {s: (ha.get(s), hb.get(s)) for s in set(ha) | set(hb)
           if ha.get(s) != hb.get(s)})
    # And the reporting field DOES move, so the clock is not simply ignored.
    da = {s: r['hours_before_kickoff'] for s, r in a.value['sources'].items()}
    db = {s: r['hours_before_kickoff'] for s, r in b.value['sources'].items()}
    check('  while hours_before_kickoff does move, so the clock is read',
          da != db)


def test_7_the_pinned_path_does_not_consult_the_selector_at_all():
    """Criterion 6, the strong form: delete the selector and pinning survives.

    A structural check can show `IN.bundle(` is absent from the branch. This
    shows something better: if the pinned path secretly re-selected, replacing
    the selector with something that raises would break it. It does not.
    """
    ids, ko = seal()
    if not ids:
        blocked('criterion 6 strong form', 'no sealed forecast')
        return
    original = INP.bundle

    def _exploding(*a, **k):
        raise AssertionError('the pinned path re-selected; it must not')

    try:
        INP.bundle = _exploding
        o = INP.bundle_from_partition_ids(ids, ko)
        check('pinning succeeds with the selector removed',
              o.state is State.PASS, f'{o.state.value}[{o.code}]')
    except AssertionError as exc:
        check('pinning succeeds with the selector removed', False, str(exc))
    finally:
        INP.bundle = original
    check('  and the selector is restored', INP.bundle is original)


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_replay_refuses_substitution: {passed} ok, {failed} failed, '
          f'{blocked_count} blocked')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
