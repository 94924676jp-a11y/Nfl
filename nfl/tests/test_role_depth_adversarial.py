#!/usr/bin/env python3.12
"""Postgame item 6 -- adversarial role / depth-chart tests across every position (Delp/Welch bug class).

    python3.12 nfl/tests/test_role_depth_adversarial.py

Synthetic, hostile-but-plausible inputs against the PRODUCTION functions (classic_slate_state._qb_rank and
proj_v1.allocate_opportunity), then the same invariants read off the sealed ATL@NO v2 run. A test here that FAILS
is a defect report, not something to quiet: the one open class (specialist leakage) is asserted as the detector
finding it, with the defect id, so it cannot be mistaken for a pass of the claim.

  QB    reported-out QB1 vacates the rank; QB absent from a chart that covers his club ranks below all listed
  RB    no-usage RB3 on the chart is not lifted past RB2 (declared limit); returning RB1 takes the better rank
  WR    returning WR1 (usage rank 3, chart 1) ranks 1; no-usage WR5 is not lifted past WR4
  TE    Delp/Welch replay: chart-ranked TE sorts ahead of an unranked TE with a 10x larger claim
  ORDER allocator ordering is rank-first for RB, WR and TE (not only QB)
  K/DST sealed v2: team-unit rows carry no skill volume
  LS    DEFECT-SPECIALIST-AUTO: a DK-listed TE whose captured chart rows are ALL special-teams slots (LS) reaches
        the skill allocator unless hand-designated. The detector must flag Cal Adomitis on the captured chart.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import classic_slate_state as CS  # noqa: E402
from nfl.tools import proj_v1 as PV  # noqa: E402

V2 = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
CHART = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/depth_charts_2026_ATL_NO.1e6aa6437a6ae01b.csv'
OFFENSIVE_GROUPS_PREFIX = ('1WR', '2WR', '3WR', '4WR', '5WR')   # nflverse offensive personnel groups

P = F = 0


def check(ok, msg):
    global P, F
    P, F = P + bool(ok), F + (not ok)
    print(('  ok   ' if ok else '  FAIL ') + msg)


def _chart(qb=(), **by_pos):
    return {'AAA': {'order': list(qb), 'by_pos': {k: list(v) for k, v in by_pos.items()}, 'dt': 'x', 'capture_id': 't'}}


def _usage(**ranks):
    return {g: {'pregame_rank': r} for g, r in ranks.items()}


def test_qb():
    ch = _chart(qb=('q1', 'q2', 'q3'))
    check(CS._qb_rank('QB', 'AAA', 'q2', ch, {}, out_gsis={'q1'}) == 1, 'QB: reported-out QB1 vacates rank 1 for QB2')
    check(CS._qb_rank('QB', 'AAA', 'q3', ch, {}, out_gsis={'q1'}) == 2, 'QB: QB3 moves to 2 when QB1 is out')
    check(CS._qb_rank('QB', 'AAA', 'qx', ch, {}) == 4, 'QB: QB absent from a chart covering his club ranks below all listed')
    check(CS._qb_rank('QB', 'AAA', 'q2', ch, _usage(q2=1)) == 2, 'QB: usage history does not override the QB chart')


def test_rb():
    ch = _chart(RB=('r1', 'r2', 'r3'))
    check(CS._qb_rank('RB', 'AAA', 'r3', ch, {}) is None, 'RB: no-usage RB3 on the chart is NOT lifted past RB2')
    check(CS._qb_rank('RB', 'AAA', 'r2', ch, {}) == 2, 'RB: no-usage RB2 keeps the chart rank (within the limit)')
    check(CS._qb_rank('RB', 'AAA', 'r1', ch, _usage(r1=3)) == 1, 'RB: returning RB1 (usage 3) takes the better chart rank')
    check(CS._qb_rank('RB', 'AAA', 'r2', ch, _usage(r2=1)) == 1, 'RB: usage rank 1 is never worsened by chart rank 2')


def test_wr():
    ch = _chart(WR=('w1', 'w2', 'w3', 'w4', 'w5'))
    check(CS._qb_rank('WR', 'AAA', 'w1', ch, _usage(w1=3)) == 1, 'WR: returning WR1 (usage 3, chart 1) ranks 1')
    check(CS._qb_rank('WR', 'AAA', 'w5', ch, {}) is None, 'WR: no-usage WR5 is not lifted past WR4')
    check(CS._qb_rank('WR', 'AAA', 'w4', ch, {}) == 4, 'WR: no-usage WR4 keeps chart 4 (slot/WR3 plus one)')
    check(CS._qb_rank('WR', 'AAA', 'w2', ch, {}, out_gsis={'w1'}) == 1, 'WR: reported-out WR1 vacates the rank')


def _alloc_rows(pos, specs):
    rows = []
    for i, (claim, chart, starter) in enumerate(specs):
        rows.append({'position': pos, '_dk': f'{pos}{i}', '_claims': {'targets': claim, 'carries': claim},
                     'role_band': 'ROTATIONAL', 'is_predicted_starter': starter, '_chart_rank': chart})
    return rows


def _depth(pos, n=6):
    return {pos: {'by_rank': {f'rank_{k}': {'unconditional_expected_share': 0.5 / k, 'appearance_rate': 1.0 / k}
                              for k in range(1, n + 1)}}}


def _ranks(rows, field):
    return {r['_dk']: (r.get('allocation') or {}).get(field, {}).get('depth_rank_in_group') for r in rows}


def test_te_delp_welch_replay():
    # TE1 starter; Delp: chart 2, small claim; Welch: NO chart rank, 10x the claim (archetype-only prior)
    rows = _alloc_rows('TE', [(0.20, 1, True), (0.01, 2, False), (0.10, None, False)])
    PV.allocate_opportunity(rows, {'proj_targets': 35.0, 'proj_rush_attempts': 25.0, 'proj_pass_attempts': 35.0},
                            _depth('TE'), {'targets': {'TE': 1.0}, 'carries': {}})
    rk = _ranks(rows, 'targets')
    check(rk == {'TE0': 1, 'TE1': 2, 'TE2': 3}, f'TE: chart-ranked Delp ranks 2, unranked Welch 3 despite 10x claim ({rk})')
    pp = {r['_dk']: r['p_plays']['targets'] for r in rows}
    check(pp['TE1'] > pp['TE2'], f'TE: P(plays) follows the rank, Delp {pp["TE1"]:.2f} > Welch {pp["TE2"]:.2f}')
    tot = sum(r['targets'] for r in rows)
    check(abs(tot - 35.0) < 1e-6, f'TE: club target identity holds ({tot:.4f})')


def test_rank_first_all_positions():
    for pos, field, grp in (('RB', 'carries', {'targets': {}, 'carries': {'RB': 1.0}}),
                            ('WR', 'targets', {'targets': {'WR': 1.0}, 'carries': {}})):
        rows = _alloc_rows(pos, [(0.05, 2, False), (0.40, None, False), (0.30, 1, True), (0.20, 3, False)])
        PV.allocate_opportunity(rows, {'proj_targets': 35.0, 'proj_rush_attempts': 25.0, 'proj_pass_attempts': 35.0},
                                _depth(pos), grp)
        rk = _ranks(rows, field)
        check(rk == {f'{pos}2': 1, f'{pos}0': 2, f'{pos}3': 3, f'{pos}1': 4},
              f'{pos}: order is starter, chart 2, chart 3, then the unranked big claim ({rk})')


def test_sealed_v2():
    proj = json.loads(next(V2.glob('SHOWDOWN_*_2026W4_PROJ.json')).read_text())['rows']
    ku = [r for r in proj.values() if r.get('position') in ('K', 'DST')]
    check(len(ku) >= 4 and all(not (r.get('targets') or r.get('carries')) for r in ku),
          f'K/DST: {len(ku)} team-unit rows carry no skill volume')
    bad = []
    for club in {r.get('club') or r.get('team') for r in proj.values()}:
        for pos in ('RB', 'WR', 'TE'):
            field = 'carries' if pos == 'RB' else 'targets'
            g = [r for r in proj.values() if (r.get('club') or r.get('team')) == club and r.get('position') == pos
                 and ((r.get('allocation') or {}).get(field) or {}).get('depth_rank_in_group')]
            ranked = [r for r in g if r.get('_chart_rank') is not None]
            unranked = [r for r in g if r.get('_chart_rank') is None]
            ar = lambda r: r['allocation'][field]['depth_rank_in_group']
            if ranked and unranked and min(ar(r) for r in unranked) < max(ar(r) for r in ranked):
                bad.append((club, pos))
            srt = sorted(ranked, key=lambda r: r['_chart_rank'])
            if [ar(r) for r in srt] != sorted(ar(r) for r in srt):
                bad.append((club, pos, 'order'))
    check(not bad, f'sealed v2: no unranked player outranks a ranked one; allocation order follows rank ({bad or "clean"})')


def specialist_candidates(chart_csv, dk_skill):
    """DK skill-position players whose rows in the LATEST captured chart are all non-offensive slots."""
    rows = [r for r in csv.DictReader(open(chart_csv))]
    last = {}
    for r in rows:
        last[r['team']] = max(last.get(r['team'], ''), r['dt'])
    by = {}
    for r in rows:
        if r['dt'] == last[r['team']]:
            by.setdefault((r['player_name'], r['team']), []).append(r)
    out = []
    for (name, team), rs in by.items():
        if (name, team) in dk_skill and not any(r['pos_grp'].startswith(OFFENSIVE_GROUPS_PREFIX) for r in rs):
            out.append({'player': name, 'team': team, 'chart_slots': sorted({r['pos_abb'] for r in rs})})
    return out


def test_specialist_detector():
    proj = list(csv.DictReader(open(next(V2.glob('SHOWDOWN_*_PROJECTIONS.csv')))))
    skill = {(r['player'], r['team']) for r in proj if r['pos'] in ('RB', 'WR', 'TE')}
    found = specialist_candidates(CHART, skill)
    names = {f['player'] for f in found}
    check('Cal Adomitis' in names, f'DEFECT-SPECIALIST-AUTO detector flags Cal Adomitis (chart slots LS only): {found}')
    src = (_REPO / 'nfl/tools/showdown_slate_state.py').read_text()
    auto = 'specialist_candidates' in src or 'OFFENSIVE_GROUPS_PREFIX' in src
    print(f'  info DEFECT-SPECIALIST-AUTO status: {"AUTOMATED" if auto else "OPEN -- NO_OFFENSIVE_ROLE comes only from hand designations"}')


if __name__ == '__main__':
    for t in (test_qb, test_rb, test_wr, test_te_delp_welch_replay, test_rank_first_all_positions, test_sealed_v2,
              test_specialist_detector):
        print(t.__name__)
        t()
    print(f'{P} passed, {F} failed')
    sys.exit(1 if F else 0)
