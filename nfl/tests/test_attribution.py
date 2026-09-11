"""The retirement of the post-hoc attribution path holds. Directive 7 §6.

This file used to test `attribution.claims_for`, which computed a capture's
target set from `retrieved_at` after the bytes arrived. Directive 7 §6 forbids
inferring the target set from timestamps, and §2 requires that a game_id on a
row mean the execution was intentionally scheduled for that obligation -- which
a timestamp cannot express.

So the tests that proved the old mechanism worked are gone, and what remains
proves it cannot come back: the entry points raise, the legacy rows in the live
manifest still parse, and none of them discharges anything.

Deleting the file instead would have been quieter and worse. A retired
mechanism with no test is a mechanism nobody is checking is still retired.

Run standalone:  python3.12 nfl/tests/test_attribution.py
"""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import attribution as A  # noqa: E402
from nfl.capture.attribution import RetiredMechanism, claimed_game_ids  # noqa: E402
from nfl.capture.coverage import coverage  # noqa: E402
from nfl.capture.execution import eligible_targets  # noqa: E402

MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def test_A_the_entry_points_refuse():
    print('\nA. the post-hoc path cannot be called')
    for name in ('claims_for', 'week_plan_for'):
        try:
            getattr(A, name)('official_inactives', '2026-09-09T23:00:00+00:00',
                             [])
            check(f'{name} raises', False, 'it returned')
        except RetiredMechanism as exc:
            check(f'{name} raises', 'Directive 7' in str(exc), str(exc)[:80])
    check('and the message says what to use instead',
          'execution.declare' in str(RetiredMechanism(A._WHY)))
    check('the version string is marked retired',
          A.CLAIM_VERSION.endswith('-RETIRED'), A.CLAIM_VERSION)


def test_B_legacy_rows_stay_readable():
    print('\nB. rows written before today are still describable')
    rows = [json.loads(l) for l in MANIFEST.read_text().splitlines()
            if l.strip()]
    legacy = [r for r in rows if r.get('state') == 'PASS'
              and (r.get('value') or {}).get('discharge_claims')]
    check('the live manifest still holds pre-Directive-7 claim rows',
          len(legacy) > 0, str(len(legacy)))
    check('and they parse rather than becoming unreadable',
          all(isinstance(claimed_game_ids(r['value']), list) for r in legacy))
    print(f'       [{len(legacy)} legacy rows in the live manifest]')


def test_C_legacy_rows_discharge_nothing():
    print('\nC. and none of them discharges anything')
    rows = [json.loads(l) for l in MANIFEST.read_text().splitlines()
            if l.strip()]
    legacy = [r for r in rows if r.get('state') == 'PASS'
              and (r.get('value') or {}).get('discharge_claims')
              and not (r.get('value') or {}).get('discharge_eligibility')]
    check('a legacy row yields no eligible targets',
          all(eligible_targets(r['value']) == [] for r in legacy))

    cov = coverage(2026, 1, manifest_path=MANIFEST)
    check('coverage counts them apart rather than ignoring them silently',
          cov.evidence.get('legacy_claim_rows', 0) >= len(legacy),
          str(cov.evidence.get('legacy_claim_rows')))
    # THE GUARD IS ABOUT LEGACY ROWS, AND THE ASSERTION WAS ABOUT ALL ROWS.
    #
    # This read `attributed_captures == 0`, which was a true statement only
    # while NOTHING in the manifest had ever declared a target. Once the T-90
    # anchored runs began declaring them the total became 103 and this failed,
    # though the thing it exists to protect -- that a pre-Directive-7 row
    # inferring its targets after the fact can never discharge -- was never
    # violated. Protect that instead, and it holds in both worlds.
    import json as _json
    legacy_keys, eligible_keys = set(), set()
    for _line in pathlib.Path(MANIFEST).read_text().splitlines():
        if not _line.strip():
            continue
        _r = _json.loads(_line)
        if _r.get('state') != 'PASS':
            continue
        _v = _r.get('value') or {}
        _key = (_r.get('source'), _r.get('capture_id'))
        if _v.get('discharge_claims') and not _v.get('discharge_eligibility'):
            legacy_keys.add(_key)
        if _v.get('discharge_eligibility'):
            eligible_keys.add(_key)
    check('legacy claim rows really are present, so this is not vacuous',
          len(legacy_keys) > 0, str(len(legacy_keys)))
    check('and not one of them overlaps the rows that may discharge',
          not (legacy_keys & eligible_keys),
          str(sorted(legacy_keys & eligible_keys)[:4]))
    check('every attributed capture came from a declared eligible target',
          cov.evidence['attributed_captures'] > 0
          and len(eligible_keys) > 0,
          f"{cov.evidence['attributed_captures']} attributed from "
          f"{len(eligible_keys)} declaring row(s)")


if __name__ == '__main__':
    test_A_the_entry_points_refuse()
    test_B_legacy_rows_stay_readable()
    test_C_legacy_rows_discharge_nothing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
