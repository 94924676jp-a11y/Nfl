"""A ratchet on stages that can discover their own evidence after freeze.

THE RULE

    After freeze, forecast execution must not perform independent discovery.
    Every reader consumes declared artifacts from the frozen contract.

WHAT IS ACTUALLY TRUE TODAY, MEASURED

The boundary holds at the CONTRACT layer -- the adversarial battery shows a
newer undeclared file changes no verdict and does not move the evidence digest
-- and it does NOT hold downstream. Eight production modules glob the vintage
store directly at forecast time and select their own evidence from whatever is
on disk:

    appearance_panel_2026  availability_feed  depth_vintage  panel_2026w1
    qb_allocation (x2)     rushing_conversion  team_volume_v1

That is the same `sorted(glob(...))` shape that, earlier on 2026-09-24, picked
a weeks-1-2 roster capture over the weeks-1-3 one in use and left 137 of 159
players unnamed. The pattern is not hypothetical and it is in production.

WHY A RATCHET RATHER THAN A FAILING TEST

Deleting eight call sites tonight would change which evidence the model reads
hours before a game, which is a worse risk than the one being fixed. So this
pins the CURRENT population by name. The list may shrink freely; it may not
grow. A new module that globs the vintage store fails this test and has to be
added deliberately, which is the conversation that should happen before the
boundary widens again.

A ratchet is an honest instrument: it does not claim the problem is solved, it
claims the problem stopped getting worse on a known date.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import discovery_audit as DA  # noqa: E402

PASSED = FAILED = BLOCKED = 0

#: Production modules known to glob the vintage store, as of 2026-09-24.
#: SHRINK THIS FREELY. Do not grow it without an explicit decision.
KNOWN_VINTAGE_DISCOVERY = {
    'nfl/production/nonqb/appearance_panel_2026.py',
    'nfl/production/nonqb/availability_feed.py',
    'nfl/production/nonqb/depth_vintage.py',
    'nfl/production/nonqb/panel_2026w1.py',
    'nfl/production/nonqb/qb_allocation.py',
    'nfl/production/nonqb/rushing_conversion.py',
    'nfl/production/team_volume_v1.py',
}

#: Total discovery primitives on the production path, same date.
BASELINE_TOTAL_HITS = 42


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _vintage_files(report):
    out = set()
    for h in report['hits']:
        if h['primitive'] not in ('glob', 'rglob'):
            continue
        code = h['code'].lower()
        if 'vintage' not in code:
            continue
        # A docstring mentioning VINTAGE.glob is prose, not a call site.
        if code.lstrip().startswith(('`', '"', "'")) or '`' in code:
            continue
        out.add(h['file'])
    return out


def test_no_new_module_may_glob_the_vintage_store():
    rep = DA.scan()
    found = _vintage_files(rep)
    new = sorted(found - KNOWN_VINTAGE_DISCOVERY)
    chk('no NEW production module globs the vintage store', not new,
        f'new offenders: {new}')
    gone = sorted(KNOWN_VINTAGE_DISCOVERY - found)
    if gone:
        print(f'       {len(gone)} module(s) stopped globbing: {gone} — '
              f'remove them from KNOWN_VINTAGE_DISCOVERY')
    chk('the known population is eight or fewer',
        len(found) <= len(KNOWN_VINTAGE_DISCOVERY), str(sorted(found)))


def test_the_total_discovery_surface_does_not_grow():
    rep = DA.scan()
    chk('total discovery primitives have not increased',
        rep['n_hits'] <= BASELINE_TOTAL_HITS,
        f"{rep['n_hits']} against a baseline of {BASELINE_TOTAL_HITS}")
    if rep['n_hits'] < BASELINE_TOTAL_HITS:
        print(f"       surface shrank to {rep['n_hits']}; lower "
              f"BASELINE_TOTAL_HITS to lock the gain in")


def test_the_auditor_does_not_count_itself():
    rep = DA.scan()
    chk('the auditor excludes its own PRIMITIVES table',
        not any(h['file'].endswith('discovery_audit.py')
                for h in rep['hits']),
        'it counted itself, which inflates every number it reports')


def test_the_audit_scans_a_real_population():
    rep = DA.scan()
    chk('it scanned the production tree',
        rep['n_files_scanned'] > 100, str(rep['n_files_scanned']))
    chk('and found hits in a minority of files',
        0 < rep['n_files_with_hits'] < rep['n_files_scanned'],
        f"{rep['n_files_with_hits']}/{rep['n_files_scanned']}")
    chk('an empty scan would not pass silently',
        rep['n_hits'] > 0,
        'zero hits would mean the scanner is broken, not that the tree is clean')


def test_the_report_states_that_a_hit_is_a_capability():
    rep = DA.scan()
    chk('the reading distinguishes capability from occurrence',
        'it cannot happen' in rep['reading'])
    chk('and refuses to score the hits itself',
        'rather than scored' in rep['reading'])


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
