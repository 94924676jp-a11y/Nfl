"""A player the run declared unavailable must own no football mass.

WHY AN OUTPUT-SIDE CHECK AND NOT ANOTHER UPSTREAM REPAIR

run_forecast already removes terminal-state players before allocation, and its
own comments record two occasions when that removal silently removed nobody --
once when all 108 players resolved to UNRESOLVED_IDENTITY, and once when a
back took 4.1 carries in a week the feed listed him OUT. Both were repaired at
the point of failure. This check reads the finished draws against the run's
own truth snapshot instead, so it does not care which way the removal fails.

WHAT IT FOUND ON THE RUN IT WAS WRITTEN AGAINST

Run 2fc4e9599f0889f1 declares five players terminal. Four own nothing, which
is the removal path working. The fifth, Jayden Reed (GB, WR, OUT, neck, did
not practise), is absent from `receiving` and `rushing` -- so he WAS removed
-- and present in `gadget_rush`, where he holds the largest WR gadget share in
the game at 0.241 of draws, above Green Bay's WR1. That mass then flows into
`rushing_total` and `dk_scoring`.

So the defect is narrow and precisely located: the gadget pool is built from a
candidate list that does not carry the availability filter the other layers
use. The test pins the finding so a rerun cannot quietly repeat it.

WHAT THIS MODULE ASSERTS
========================
1. ONLY TERMINAL STATES ACT. OUT and the official-inactive states trigger;
   DOUBTFUL and QUESTIONABLE deliberately do not, because no calibrated
   transition for them exists and turning a probability into a certainty is
   the fabrication this project forbids.
2. OPPORTUNITY IS CHECKED, NOT OUTCOME. A carry for no gain is still a carry,
   and a check keyed on yards would miss the case it exists for.
3. AN EMPTY SNAPSHOT RAISES rather than passing vacuously, and a snapshot
   declaring nobody terminal returns NOT_APPLICABLE rather than PASS -- "there
   was nothing to catch" is not "the removal worked".
4. THE REAL RUN FAILS THIS CHECK, for exactly one player, in exactly one
   layer, and the other four declared-unavailable players pass.
"""
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.unsealed.unavailable_owns_nothing import (  # noqa: E402
    InvariantError,
    check,
    declared_unavailable,
    violations,
)

PASSED = FAILED = BLOCKED = 0

RUN = os.path.join(_ROOT, 'nfl', 'research', 'unsealed',
                   '2026_03_ATL_GB', '2fc4e9599f0889f1')


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def _truth(*players):
    return {'players': [dict(zip(('gsis_id', 'full_name', 'team',
                                  'position', 'availability'), p))
                        for p in players]}


def _art(gsis_id, layer, metric, row):
    return ({f'{layer}__{metric}': np.array([row], dtype=float)},
            {layer: {'row_ids': [gsis_id]}})


def test_a_terminal_player_holding_opportunity_is_caught():
    arrays, layers = _art('X', 'gadget_rush', 'wr', [0, 2, 0, 1])
    v = check(arrays, layers, _truth(('X', 'A Player', 'GB', 'WR', 'OUT')))
    chk('the check fails', v['state'] == 'FAIL', v['state'])
    chk('with the named code', v['code'] == 'UNAVAILABLE_PLAYER_OWNS_OPPORTUNITY')
    chk('and names the layer and metric',
        v['violations'][0]['holds'][0]['layer'] == 'gadget_rush'
        and v['violations'][0]['holds'][0]['metric'] == 'wr')
    chk('and reports the share of draws',
        abs(v['violations'][0]['holds'][0]['p_nonzero'] - 0.5) < 1e-9)


def test_a_terminal_player_holding_nothing_passes():
    arrays, layers = _art('X', 'receiving', 'targets', [0, 0, 0, 0])
    v = check(arrays, layers, _truth(('X', 'A Player', 'GB', 'WR', 'OUT')))
    chk('the check passes', v['state'] == 'PASS', v['state'])
    chk('with the named code', v['code'] == 'UNAVAILABLE_OWN_NOTHING')


def test_probabilistic_designations_deliberately_do_not_act():
    for state in ('QUESTIONABLE', 'DOUBTFUL'):
        arrays, layers = _art('X', 'receiving', 'targets', [3, 0, 2, 1])
        v = check(arrays, layers, _truth(('X', 'A Player', 'GB', 'WR', state)))
        chk(f'{state} does not trigger the invariant',
            v['state'] == 'NOT_APPLICABLE', f"{state} -> {v['state']}")
    chk('and the verdict says which states were deliberately excluded',
        'QUESTIONABLE' in v['states_deliberately_not_acting'])


def test_an_outcome_is_not_an_opportunity():
    """Carries with zero yards still count as owning mass."""
    arrays = {'rushing__carries': np.array([[2.0, 0.0]]),
              'rushing__rushing_yards': np.array([[0.0, 0.0]])}
    layers = {'rushing': {'row_ids': ['X']}}
    v = check(arrays, layers, _truth(('X', 'A Player', 'GB', 'RB', 'OUT')))
    chk('a zero-yard carry is still a violation', v['state'] == 'FAIL',
        v['state'])


def test_nothing_to_catch_is_not_a_pass():
    arrays, layers = _art('X', 'receiving', 'targets', [1, 1])
    v = check(arrays, layers, _truth(('X', 'A Player', 'GB', 'WR', 'ACTIVE')))
    chk('a snapshot with nobody terminal is NOT_APPLICABLE, not PASS',
        v['state'] == 'NOT_APPLICABLE', v['state'])
    chk('and says so in words',
        'must not be read as a pass' in v['detail'])


def test_an_empty_snapshot_raises_rather_than_passing_vacuously():
    try:
        declared_unavailable({'players': []})
        chk('an empty snapshot raises', False, 'returned instead')
    except InvariantError:
        chk('an empty snapshot raises', True)


def test_the_real_run_fails_for_one_player_in_one_layer():
    manifest = os.path.join(RUN, 'player_draws_manifest.json')
    npz = os.path.join(RUN, 'player_draws.npz')
    truth = os.path.join(RUN, 'TRUTH_SNAPSHOT_as_run.json')
    if not all(os.path.exists(p) for p in (manifest, npz, truth)):
        return blocked('real run', f'artifacts absent under {RUN}')
    m = json.load(open(manifest))
    z = np.load(npz, allow_pickle=True)
    t = json.load(open(truth))
    v = check({k: z[k] for k in z.keys()}, m['layers'], t)

    chk('the run declares five players terminal',
        v['n_declared_unavailable'] == 5, str(v['n_declared_unavailable']))
    chk('exactly one of them owns opportunity',
        v['n_violating'] == 1, str(v['n_violating']))
    chk('so the removal path worked for the other four',
        v['n_declared_unavailable'] - v['n_violating'] == 4)

    bad = v['violations'][0]
    chk('the violator is Jayden Reed', bad['name'] == 'Jayden Reed', str(bad['name']))
    chk('declared OUT on a game designation',
        bad['availability'] == 'OUT'
        and bad['basis'] == 'DECLARED_GAME_DESIGNATION',
        f"{bad['availability']} / {bad['basis']}")
    chk('he owns mass in exactly one layer', len(bad['holds']) == 1,
        str(bad['holds']))
    chk('and that layer is gadget_rush',
        bad['holds'][0]['layer'] == 'gadget_rush', str(bad['holds'][0]))

    layers = m['layers']
    chk('he was correctly removed from receiving',
        '00-0039146' not in (layers['receiving']['row_ids'] or []))
    chk('and from rushing',
        '00-0039146' not in (layers['rushing']['row_ids'] or []))
    chk('but survives in gadget_rush, which is the whole defect',
        '00-0039146' in (layers['gadget_rush']['row_ids'] or []))
    print(f"       {bad['name']}: gadget_rush__wr in "
          f"{bad['holds'][0]['p_nonzero']:.3f} of draws, max "
          f"{bad['holds'][0]['max']:.0f} carries")


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
