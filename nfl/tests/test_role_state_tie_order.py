"""A tied depth rank is broken by football evidence, never by an identifier (W5-G13, found 2026-10-09).

classic_slate_state gives a back or receiver the MINIMUM of his usage-history rank and his captured-chart rank, so the
chart WR1 and the usage WR1 can both hold rank 1. role_state sorted (rank, dk_id), so the DK id decided which of them
took the DEPTH_RANK_1 ceiling: the same football facts projected differently under DK ids and research ids. The order is
now rank, the chart rank that produced it, usage rank, observed share, and the id only when nothing else separates them.
"""
import copy
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import role_state as RS, availability as AV, classic_slate_state as CS  # noqa: E402

PASSED = FAILED = 0
ACTIVE = AV.UNKNOWN_ACTIVE_STATE


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _p(name, rank, usage, chart, share=0.2, pos='WR', team='XXX', record_chart=True):
    row = {'name': name, 'team': team, 'position': pos, 'depth_rank': rank, 'depth_usage_rank': usage,
           'observed_2026': {'combined': {'target_share': share, 'rush_share': share}},
           'current_availability': {'status': ACTIVE}}
    if record_chart:
        row['depth_chart_rank'] = chart
    return row


def test_chart_breaks_a_tie_whatever_the_ids():
    for ids in (('a', 'b'), ('b', 'a'), ('zz', '00')):
        P = {ids[0]: _p('Usage One', 1, 1, 2), ids[1]: _p('Chart One', 1, 2, 1)}
        r = RS._position_scoped_ranks(P)
        check(r[ids[1]] == 1 and r[ids[0]] == 2, f'ids {ids}: the chart WR1 ranks 1, the usage WR1 ranks 2 ({r})')


def test_derived_when_the_state_does_not_record_the_chart():
    P = {'a': _p('Usage One', 1, 1, None, record_chart=False), 'b': _p('Chart One', 1, 2, None, record_chart=False)}
    r = RS._position_scoped_ranks(P)
    check(r == {'b': 1, 'a': 2}, f'a rank below the usage rank is read as chart-derived ({r})')


def test_observed_share_before_id():
    P = {'a': _p('Low', 1, None, None, share=0.10, record_chart=False), 'b': _p('High', 1, None, None, share=0.25, record_chart=False)}
    r = RS._position_scoped_ranks(P)
    check(r == {'b': 1, 'a': 2}, f'with no rank evidence the larger observed share ranks first ({r})')


def test_untied_order_unchanged():
    P = {'1': _p('A', 1, 1, 1), '2': _p('B', 3, 3, 4), '3': _p('C', 2, 2, 2)}
    check(RS._position_scoped_ranks(P) == {'1': 1, '3': 2, '2': 3}, 'an untied order is exactly the supplied order')


def test_depth_ranks_records_the_chart_rank():
    chart = {'CIN': {'order': [], 'by_pos': {'WR': ['CH', 'HI']}}}
    depth = {'CH': {'pregame_rank': 2}, 'HI': {'pregame_rank': 1}}
    check(CS._depth_ranks('WR', 'CIN', 'CH', chart, depth) == (1, 1), 'chart WR1 with usage 2: rank 1, chart 1')
    check(CS._depth_ranks('WR', 'CIN', 'HI', chart, depth) == (1, 2), 'usage WR1 with chart 2: rank 1, chart 2')
    check(CS._qb_rank('WR', 'CIN', 'HI', chart, depth) == 1, '_qb_rank keeps its contract')


def test_real_state_is_invariant_to_ids():
    p = _REPO / 'nfl/dfs/salaries/DK_2026W4_EARLY_STATE.json'
    P = json.loads(p.read_text())['players']
    a, _ = RS.assign(P)
    relabel = {('Z' + k[::-1]): copy.deepcopy(v) for k, v in P.items()}
    b, _ = RS.assign(relabel)
    back = {('Z' + k[::-1]): k for k in P}
    diff = [P[back[k]]['name'] for k, v in b.items() if (v.get('askable_ceiling'), v.get('role_band')) !=
            (a[back[k]].get('askable_ceiling'), a[back[k]].get('role_band'))]
    check(not diff, f'W4 Early: relabelling every id changes no ceiling or band ({diff[:5]})')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and n != 'test_zz_every_check_passed':
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
