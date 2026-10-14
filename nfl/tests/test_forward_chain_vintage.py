#!/usr/bin/env python3.12
"""Forward-chain vintage (ledger PIT-D4; benchmark mandate 2026-10-14).

STRICT (the default) fits the positional touchdown rates, the pass/rush touchdown split and the interception rate on
seasons BEFORE the evaluated one; LEGACY reproduces the pre-2026-10-14 full-period fit. Production's own td_rates
defaults are unchanged. An unknown vintage refuses."""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import forward_chain as F, player_prior as P, proj_v1 as V, td_rates as R  # noqa: E402

PASSED = FAILED = 0


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def _record(vintage, season=2024):
    """Run one evaluated week and record the seasons each fitted input was given."""
    seen = {}
    real = (R.positional_rates, R.pass_rush_split, V.int_rate)
    R.positional_rates = lambda panel, pos_of, seasons=None: (seen.setdefault('prates', seasons), real[0](panel, pos_of, seasons))[1]
    R.pass_rush_split = lambda panel, seasons=None: (seen.setdefault('split', seasons), real[1](panel, seasons))[1]
    V.int_rate = lambda panel, pos_of, through=None: (seen.setdefault('int', through), real[2](panel, pos_of, through))[1]
    saved = F.VINTAGE[0]
    try:
        F.VINTAGE[0] = vintage
        po = P.load_panel()
        F.evaluate(po.value, P.position_index(), [season], [('PROD', 1.0, None)], max_weeks=1)
        return seen, F.PASS_SHARE[0]
    finally:
        R.positional_rates, R.pass_rush_split, V.int_rate = real
        F.VINTAGE[0] = saved


def test_strict_is_the_default_and_fits_only_earlier_seasons():
    check(F.VINTAGE[0] == 'STRICT', f'the default vintage is STRICT ({F.VINTAGE[0]})')
    seen, share = _record('STRICT', 2024)
    check(seen.get('prates') is not None and max(seen['prates']) <= 2023,
          f"touchdown rates fit on seasons <= 2023 when 2024 is scored ({seen.get('prates')})")
    check(seen.get('split') is not None and max(seen['split']) <= 2023,
          f"pass/rush split fit on seasons <= 2023 ({seen.get('split')})")
    check(seen.get('int') == 2023, f"interception rate measured through 2023 ({seen.get('int')})")
    check(isinstance(share, float) and share != 0.6156, f'the pass share is measured, not the full-period literal ({share})')


def test_legacy_reproduces_the_old_fit_and_unknown_refuses():
    seen, share = _record('LEGACY', 2024)
    check(seen.get('prates') is None and seen.get('int') is None and share == 0.6156,
          'LEGACY uses the full-period fit and the 0.6156 literal (reproduction of pre-2026-10-14 results only)')
    try:
        _record('BOGUS', 2024)
        refused = False
    except ValueError as e:
        refused = 'FORWARD_CHAIN_VINTAGE_UNKNOWN' in str(e)
    check(refused, 'an unknown vintage refuses')


def test_production_defaults_are_unchanged():
    po = P.load_panel()
    check(R.pass_rush_split(po.value).get('mean_pass_share_of_offensive_td') == 0.6156,
          'td_rates.pass_rush_split default (the production fit) is unchanged: 0.6156')
    check(R.positional_rates(po.value, P.position_index()) == R.positional_rates(po.value, P.position_index(), seasons=R.FIT_SEASONS),
          'positional_rates default equals the explicit FIT_SEASONS fit')


def test_unconditional_rows_do_not_depend_on_call_order():
    """FC-D1: the zero-fill for absent pool candidates used the PREVIOUS call's pool (empty on a process's first week)."""
    po = P.load_panel()

    def run():
        F.PER_PLAYER_SINK_DFS = []
        F.evaluate(po.value, P.position_index(), [2024], [('PROD', 1.0, None)], max_weeks=2)
        return list(F.PER_PLAYER_SINK_DFS)
    saved = (F.POOL[0], F.PER_PLAYER_SINK_DFS)
    try:
        F.POOL[0] = set()          # a fresh process
        first = run()
        second = run()
        check(first == second and len(first) > 0, f'two consecutive runs give identical unconditional rows ({len(first)}, {len(second)})')
        absent = [r for r in first if not r[7]]
        check(len(absent) > 0, f'the first run already zero-fills absent pool candidates ({len(absent)})')
        F.D1_W[0] = 0.0
        check(run() == first, 'D1 at w = 0 reproduces the incumbent rows exactly (golden)')
    finally:
        F.D1_W[0] = None
        F.POOL[0], F.PER_PLAYER_SINK_DFS = saved


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and callable(f):
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
