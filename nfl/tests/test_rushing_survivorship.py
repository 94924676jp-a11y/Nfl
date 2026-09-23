"""The stratified control must not be estimated on league survivors only.

REPRODUCTION FIRST. `test_roster_only_bridge_drops_carries` rebuilds the
original defect -- position resolved from the 2026 roster alone -- and asserts
it loses carries and biases the mean up. If that test ever passes trivially the
defect has stopped being reproducible and this file is measuring nothing.
"""
import csv
import glob
import gzip
import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
for q in (str(REPO), str(REPO / 'nfl' / 'research' / 'p5a')):
    if q not in sys.path:
        sys.path.insert(0, q)

from nfl.production.nonqb import rushing_conversion as R   # noqa: E402

CUT = 202602
AUDIT = REPO / 'nfl' / 'production' / 'nonqb' / 'SURVIVORSHIP_AUDIT.json'

_P, _F = [], []


def ck(name, cond, detail=''):
    (_P if cond else _F).append(name)
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + detail) if detail else ''))


def _roster_only():
    m = {}
    for f in sorted(glob.glob(str(REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        for r in csv.DictReader(gzip.open(f, 'rt')):
            g = (r.get('gsis_id') or '').strip()
            if g and g not in m:
                m[g] = (r.get('position') or '').strip()
    return m


def _sweep(bridge):
    y = {'RB': [], 'NON_RB': []}
    dropped = 0
    for f in sorted(glob.glob(str(REPO / 'nfl/research/postgame/pbp_20*.csv.gz'))):
        for r in csv.DictReader(gzip.open(f, 'rt')):
            s, w = r.get('season'), r.get('week')
            if not s or not w:
                continue
            try:
                if int(s) * 100 + int(w) >= CUT:
                    continue
            except ValueError:
                continue
            if str(r.get('rush_attempt') or '0') not in ('1', '1.0'):
                continue
            rid = (r.get('rusher_player_id') or '').strip()
            if not rid:
                continue
            pos = bridge.get(rid)
            if pos is None:
                dropped += 1
                continue
            try:
                y[R._stratum(pos)].append(float(r.get('yards_gained') or 0))
            except (TypeError, ValueError):
                pass
    return y, dropped


def main():
    if not list(glob.glob(str(REPO / 'nfl/research/postgame/pbp_20*.csv.gz'))):
        print('BLOCKED RUSHSURV_NO_PBP cause=DATA')
        return 0

    # --- the defect, reproduced ---
    ro_y, ro_dropped = _sweep(_roster_only())
    ck('roster_only_bridge_still_drops_carries', ro_dropped > 10000,
       f'dropped={ro_dropped}')

    out = R.pools(CUT)
    ck('pools_build', out.state.name == 'PASS', out.code)
    if out.state.name != 'PASS':
        return 1
    prov = out.as_dict()['evidence']['provenance']

    # --- the fix ---
    ck('no_carry_left_without_a_position',
       prov['carries_with_no_position'] == 0,
       str(prov['carries_with_no_position']))
    ck('panel_takes_precedence_over_2026_roster',
       prov['position_precedence'] == 'panel_p3_historical > weekly_rosters_2026')

    for s in ('RB', 'NON_RB'):
        n_fixed = prov['strata'][s]['n_carries']
        n_old = len(ro_y[s])
        ck(f'{s}_pool_grew', n_fixed > n_old, f'{n_old} -> {n_fixed}')
        # survivors rush better, so removing the survivorship lowers the mean
        old_mean = float(np.mean(ro_y[s]))
        ck(f'{s}_mean_fell_when_survivorship_removed',
           prov['strata'][s]['mean'] < old_mean,
           f'{old_mean:.4f} -> {prov["strata"][s]["mean"]:.4f}')

    # --- the audit artifact must agree with the module, not drift from it ---
    ck('audit_artifact_present', AUDIT.exists())
    if AUDIT.exists():
        a = json.loads(AUDIT.read_text())
        ck('audit_total_matches_measured_drop', a['total_dropped'] == ro_dropped,
           f"audit={a['total_dropped']} measured={ro_dropped}")
        ck('audit_resolves_everything', a['still_unresolved_after_panel'] == 0)
        ck('audit_carries_every_requested_dimension',
           all(k in a for k in ('by_season', 'by_position', 'by_team',
                                'by_identity_state', 'by_stratum',
                                'yards_per_carry', 'materiality')))
        ck('audit_covers_all_32_teams', len(a['by_team']) == 32,
           str(len(a['by_team'])))
        ck('survivorship_is_systematic_by_season',
           a['by_season']['2021'] > 5 * a['by_season']['2025'],
           f"2021={a['by_season']['2021']} 2025={a['by_season']['2025']}")
        ck('RB_shift_exceeds_two_SE_of_retained_mean',
           abs(a['materiality']['RB']['delta_in_SE_of_retained_mean']) > 2.0,
           str(a['materiality']['RB']['delta_in_SE_of_retained_mean']))

    print(f'\n{len(_P)} passed, {len(_F)} failed')
    if _F:
        print('FAILED: ' + ', '.join(_F))
    return 1 if _F else 0



# ---------------------------------------------------------------- the runner
# THIS MODULE'S CHECKS WERE INVISIBLE TO `run_suite`. It records into `_P`/`_F`
# and runs everything from `main()`, so the runner discovered ZERO `test_*`
# functions and executed NONE of them. Found 2026-09-23 by
# `test_harness_audit`'s "no module has zero test functions", which had been
# failing and telling the truth, and confirmed by invoking this file directly:
# it reports real numbers the suite had never seen.
#
# That is the false-green class INSIDE the measurement system -- the same
# defect `run_suite.py` was written to end, one level further out.
#
# NOTHING BELOW CHANGES WHAT THIS MODULE ASSERTS. It exposes the integer
# counters the runner reads (`_P`/`_F` are lists and underscore-prefixed, so
# `tally()` could not see them either) and gives the runner one function to
# call, in the same shape the other fifty modules use.
PASSED = FAILED = 0
blocked_count = 0


def test_every_check_in_this_module():
    global PASSED, FAILED, blocked_count
    main()
    PASSED, FAILED = len(_P), len(_F)
    # `main()` returns early, without recording a check, when its inputs are
    # absent. Counted as BLOCKED so it is distinguishable from silence: a
    # module that could not measure said so, and is not a pass.
    if not _P and not _F:
        blocked_count = 1


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')

if __name__ == '__main__':
    raise SystemExit(main())
