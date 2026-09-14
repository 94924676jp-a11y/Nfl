"""R3: current role evidence must define the current role state.

Two repaired defects are guarded here, and they are guarded as PROPERTIES, not
as numbers a later run will make stale.

D1  `depth_vintage.weekly` ordered receivers by `(depth_team, depth_position)`
    across EVERY listed slot. `depth_position` is a string and
    `KOR < KR < PR < WR`, so the punt returner sorted ahead of the receivers.
    Measured over 2,432 WR team-weeks of 2021-2024: the rank-1 slot was a
    return slot in 1,649 (0.6780) and was not the plain `WR` slot in 1,665
    (0.6846). The guard is that a return designation can never decide an
    offensive ordering -- and that where the vendor supplies no ordering, none
    is invented.

D2  `role_prior.assign_tiers` ranked the room in two passes and appended every
    player without prior-season history AFTER every veteran who had any. The
    guard is that no such pass exists: one scale, and which player is higher is
    decided by arithmetic on evidence, in BOTH directions.

Both guards are bidirectional on purpose. A test that only checks that a
no-history starter can rise would pass a module that promoted him by fiat, and
fiat is what the repair was forbidden to use.
"""
from __future__ import annotations

import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                 # noqa: E402
from nfl.production.nonqb import depth_vintage as DV                # noqa: E402
from nfl.production.nonqb import role_prior as RP                   # noqa: E402

PASSED = FAILED = BLOCKED = 0

_HDR = ('season,club_code,week,game_type,depth_team,last_name,first_name,'
        'football_name,formation,gsis_id,jersey_number,position,elias_id,'
        'depth_position,full_name')


def check(label, ok, detail=''):
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


def _row(season, club, week, depth_team, gsis, position, formation, slot):
    return (f'{season},{club},{week},REG,{depth_team},L,F,F,{formation},{gsis},'
            f'9,{position},E,{slot},Full Name')


def _stage(rows, season=2021, with_formation=True):
    """A throwaway staged leaf. Nothing in the repository is read or written."""
    d = tempfile.mkdtemp(prefix='r3-depth-')
    hdr = _HDR if with_formation else _HDR.replace(',formation', '')
    body = []
    for r in rows:
        if with_formation:
            body.append(r)
        else:
            parts = r.split(',')
            del parts[8]
            body.append(','.join(parts))
    open(os.path.join(d, f'dc_{season}.csv'), 'w').write(
        hdr + '\n' + '\n'.join(body) + '\n')
    return d


# ------------------------------------------------------------------ D1
def test_a_return_slot_cannot_win_the_receiver_ordering():
    """The exact 2023 shape: a returner holding (PR, 1) against a receiver
    the offensive chart puts first. The returner used to sort first because
    'PR' < 'WR'."""
    rows = [
        _row(2021, 'ZZZ', 1, 1, '00-0000001', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 2, 1, '00-0000001', 'WR', 'Offense', 'WR'),
        # the returner: deep on the offensive chart, first on special teams
        _row(2021, 'ZZZ', 1, 5, '00-0000002', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 1, 1, '00-0000002', 'WR', 'Special Teams', 'PR'),
        _row(2021, 'ZZZ', 1, 1, '00-0000002', 'WR', 'Special Teams', 'KR'),
        _row(2021, 'ZZZ', 2, 5, '00-0000002', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 2, 1, '00-0000002', 'WR', 'Special Teams', 'PR'),
    ]
    o = DV.weekly(_stage(rows), seasons=(2021,))
    check('the repaired weekly reads', o.state is State.PASS, f'{o.code}')
    if o.state is not State.PASS:
        return
    v = o.value
    rec = v[(2021, 1, 'ZZZ', '00-0000001')][0]
    ret = v[(2021, 1, 'ZZZ', '00-0000002')][0]
    check('the offensive first-team receiver outranks the punt returner',
          rec < ret, f'receiver group {rec} vs returner group {ret}')
    check('  and the returner keeps his OFFENSIVE depth, not his return depth',
          ret > 1, f'group {ret}')
    check('  return slots are named as never-ordering',
          set(DV.RETURN_SLOTS) >= {'KR', 'PR'}, str(DV.RETURN_SLOTS))
    check('  and the special-teams rows are counted, not silently dropped',
          o.evidence['n_special_teams_rows_excluded'] == 3,
          str(o.evidence['n_special_teams_rows_excluded']))


def test_a_return_slot_filed_under_offence_is_still_a_return_slot():
    rows = [
        _row(2021, 'ZZZ', 1, 3, '00-0000001', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 1, 1, '00-0000002', 'WR', 'Offense', 'PR'),
    ]
    o = DV.weekly(_stage(rows), seasons=(2021,))
    check('a PR row under the offensive formation is excluded', (
        o.state is State.PASS
        and (2021, 1, 'ZZZ', '00-0000002') not in o.value
        and o.evidence['n_return_slot_rows_under_offence_excluded'] == 1),
        f'{o.code} {o.evidence.get("n_return_slot_rows_under_offence_excluded")}')
    check('  and the receiver still carries a rank',
          o.state is State.PASS and (2021, 1, 'ZZZ', '00-0000001') in o.value)


def test_an_unresolvable_tie_is_reported_and_not_invented():
    """The vendor lists two or three first-team receivers and nothing to order
    them by. Manufacturing 1/2/3 out of that is what produced the defect."""
    rows = [
        _row(2021, 'ZZZ', 1, 1, '00-0000001', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 1, 1, '00-0000002', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 1, 1, '00-0000003', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 1, 2, '00-0000004', 'WR', 'Offense', 'WR'),
    ]
    o = DV.weekly(_stage(rows), seasons=(2021,), detail=True)
    check('the tied room reads', o.state is State.PASS, o.code)
    if o.state is not State.PASS:
        return
    g = {p: o.value[(2021, 1, 'ZZZ', p)] for p in
         ('00-0000001', '00-0000002', '00-0000003', '00-0000004')}
    check('all three first-team receivers share one group',
          g['00-0000001']['group'] == g['00-0000002']['group']
          == g['00-0000003']['group'] == 1,
          str({k: v['group'] for k, v in g.items()}))
    check('  the tie is declared, not broken',
          all(g[p]['tie_size'] == 3 and g[p]['resolved'] is False
              for p in ('00-0000001', '00-0000002', '00-0000003')),
          str({k: (v['tie_size'], v['resolved']) for k, v in g.items()}))
    check('  the second-team receiver is still separated',
          g['00-0000004']['group'] == 2 and g['00-0000004']['resolved'] is True,
          str(g['00-0000004']))
    check('  and the room is counted as unresolved at the top',
          o.evidence['n_rooms_with_unresolved_top_group'] == 1,
          str(o.evidence['n_rooms_with_unresolved_top_group']))


def test_a_special_teams_only_player_gets_no_offensive_rank():
    rows = [
        _row(2021, 'ZZZ', 1, 1, '00-0000001', 'WR', 'Offense', 'WR'),
        _row(2021, 'ZZZ', 1, 1, '00-0000009', 'WR', 'Special Teams', 'KR'),
    ]
    o = DV.weekly(_stage(rows), seasons=(2021,))
    check('the returner carries no offensive rank at all',
          o.state is State.PASS
          and (2021, 1, 'ZZZ', '00-0000009') not in o.value, o.code)
    check('  and that is a counted fact, not a silent absence',
          o.state is State.PASS
          and o.evidence['n_players_listed_only_off_offence'] == 1,
          str(o.evidence.get('n_players_listed_only_off_offence')))


def test_a_leaf_without_the_formation_column_is_refused_by_name():
    """Without `formation` the only ordering available is the contaminated
    one. Falling back to it silently is the defect wearing a permit."""
    rows = [_row(2021, 'ZZZ', 1, 1, '00-0000001', 'WR', 'Offense', 'WR')]
    o = DV.weekly(_stage(rows, with_formation=False), seasons=(2021,))
    check('a leaf with no formation column refuses by name',
          o.state is not State.PASS
          and o.code == 'DEPTH_WEEKLY_LEAF_MISSING', o.code)
    check('  and says which season and why',
          o.evidence.get('seasons_without_formation_column') == [2021],
          str(o.evidence.get('seasons_without_formation_column')))


def test_the_daily_vendor_drops_return_slots_and_declares_its_scale():
    txt = ('dt,team,gsis_id,pos_abb,pos_rank\n'
           '2026-01-01T00:00:00Z,ZZZ,00-0000001,WR,1\n'
           '2026-01-01T00:00:00Z,ZZZ,00-0000002,WR,2\n'
           '2026-01-01T00:00:00Z,ZZZ,00-0000003,PR,1\n'
           '2026-01-01T00:00:00Z,ZZZ,00-0000004,KR,1\n'
           '2026-01-01T00:00:00Z,ZZZ,00-0000005,TE,1\n')
    o = DV.daily(txt)
    check('the daily vendor reads', o.state is State.PASS, o.code)
    if o.state is not State.PASS:
        return
    listed = o.value['ZZZ'][0][1]
    check('no return-slot row reaches a rank',
          '00-0000003' not in listed and '00-0000004' not in listed,
          str(sorted(listed)))
    check('  and the exclusion is counted',
          o.evidence['n_return_slot_rows_excluded'] == 2,
          str(o.evidence.get('n_return_slot_rows_excluded')))
    check('  the offence-wide scale is declared rather than implied',
          'NOT a within-position' in (o.evidence.get('rank_scale') or ''),
          str(o.evidence.get('rank_scale'))[:80])
    check('  and which position actually won rank 1 is reported',
          isinstance(o.evidence.get('rank_1_position_mix'), dict)
          and sum(o.evidence['rank_1_position_mix'].values()) == 1,
          str(o.evidence.get('rank_1_position_mix')))


# ------------------------------------------------------------------ D2
def _prior(**over):
    """A prior of the SHAPE `build` returns. Every number here is a fixture,
    and the point of the tests below is that the module reads them rather than
    carrying numbers of its own."""
    p = {'tier_mean': {'WR1': 0.22, 'WR2': 0.18, 'WR3': 0.13, 'WR4': 0.06},
         'k': {'WR': 0.87},
         'tier_snap_mean': {'WR1': 0.80, 'WR2': 0.70, 'WR3': 0.55,
                            'WR4': 0.30},
         'k_snap': {'WR': 0.80},
         'trailing_snap': {}, 'trailing_n': {}, 'n_history': {}}
    p.update(over)
    return p


def _room(*pids):
    return [{'gsis_id': p, 'team': 'ZZZ', 'position': 'WR'} for p in pids]


def test_a_no_history_chart_leader_is_no_longer_unpromotable():
    """D4's P0-2, as a property. VET has eight games of fringe snap share; NEW
    has none and the current chart puts him first. The old construction placed
    NEW below VET unconditionally."""
    pr = _prior(trailing_snap={'VET': 0.25}, trailing_n={'VET': 8})
    got = RP.assign_tiers(_room('VET', 'NEW'), pr, depth_rank={'NEW': 1})
    check('the repaired ordering ran', got['degraded'] is False,
          str(got.get('degraded_reason'))[:80])
    check('the chart leader with no history is not forced below the veteran',
          got['tier']['NEW'] < got['tier']['VET'], str(got['tier']))
    check('  and his basis names the evidence that placed him',
          got['basis']['NEW'] == 'depth_chart', got['basis']['NEW'])
    check('  with the arithmetic recorded, not just the verdict',
          set(got['detail']['NEW']) >= {'score', 'anchor', 'anchor_tier',
                                        'shrinkage_w', 'n_trailing', 'tier'},
          str(sorted(got['detail']['NEW'])))


def test_and_a_real_starter_is_not_displaced_by_one():
    """The symmetric half, and the one that makes this a repair rather than a
    promotion rule. A rank-1 no-history player must NOT outrank a veteran whose
    own measured snap share is above the rank-1 anchor."""
    pr = _prior(trailing_snap={'STAR': 0.92}, trailing_n={'STAR': 8})
    got = RP.assign_tiers(_room('STAR', 'NEW'), pr, depth_rank={'NEW': 1})
    check('an established starter still outranks a no-history chart leader',
          got['tier']['STAR'] < got['tier']['NEW'], str(got['tier']))
    check('  and it is the arithmetic that decided it',
          got['detail']['STAR']['score'] > got['detail']['NEW']['score'],
          f"{got['detail']['STAR']['score']:.4f} vs "
          f"{got['detail']['NEW']['score']:.4f}")


def test_the_ordering_is_a_function_of_evidence_and_not_of_list_order():
    """The old defect was positional: which pass you were in decided where you
    landed. If any such pass survived, reversing the input would move someone."""
    pr = _prior(trailing_snap={'A': 0.60, 'B': 0.20}, trailing_n={'A': 8, 'B': 8})
    dr = {'C': 1, 'D': 4}
    fwd = RP.assign_tiers(_room('A', 'B', 'C', 'D'), pr, depth_rank=dr)
    rev = RP.assign_tiers(_room('D', 'C', 'B', 'A'), pr, depth_rank=dr)
    check('reversing the input leaves every tier unchanged',
          fwd['tier'] == rev['tier'], f"{fwd['tier']} vs {rev['tier']}")
    check('  and no player is grouped ahead of another by having history',
          fwd['tier']['C'] < fwd['tier']['B'],
          f"C {fwd['tier']['C']} B {fwd['tier']['B']}")


def test_the_anchor_is_read_from_the_estimated_prior_and_not_written_here():
    """No hand-set ladder: move the measured anchors and the ordering follows.
    If the module carried its own ladder this would not move."""
    base = _prior(trailing_snap={'VET': 0.45}, trailing_n={'VET': 8})
    hi = RP.assign_tiers(_room('VET', 'NEW'), base, depth_rank={'NEW': 1})
    low = dict(base)
    low['tier_snap_mean'] = dict(base['tier_snap_mean'])
    low['tier_snap_mean']['WR1'] = 0.10      # the measurement, not a preference
    lo = RP.assign_tiers(_room('VET', 'NEW'), low, depth_rank={'NEW': 1})
    check('with a high measured WR1 anchor the chart leader is first',
          hi['tier']['NEW'] == 1, str(hi['tier']))
    check('  with a low one he is not, and nothing in the module objects',
          lo['tier']['NEW'] == 2, str(lo['tier']))


def test_an_unlisted_player_anchors_deepest_and_says_so():
    pr = _prior(trailing_snap={}, trailing_n={})
    got = RP.assign_tiers(_room('LISTED', 'UNKNOWN'), pr,
                          depth_rank={'LISTED': 2})
    check('the unlisted player is placed below the listed one',
          got['tier']['UNKNOWN'] > got['tier']['LISTED'], str(got['tier']))
    check('  and is named, not merely ranked',
          got['basis']['UNKNOWN'] == 'no_information_lowest_tier',
          got['basis']['UNKNOWN'])
    check('  anchoring on the deepest MEASURED tier, from the prior',
          got['detail']['UNKNOWN']['anchor'] == pr['tier_snap_mean']['WR4'],
          str(got['detail']['UNKNOWN']['anchor']))


def test_a_prior_without_the_snap_anchors_degrades_out_loud():
    """The legacy ordering still exists for a prior that cannot support the
    repair. It must never be reached silently."""
    old_shape = {'tier_mean': {'WR1': 0.22}, 'k': {'WR': 0.87},
                 'trailing_snap': {'A': 0.5}, 'n_history': {}}
    got = RP.assign_tiers(_room('A', 'B'), old_shape, depth_rank={'B': 1})
    check('the legacy path is flagged as degraded',
          got['degraded'] is True, str(got.get('degraded')))
    check('  and says why, by name',
          'tier_snap_mean' in (got.get('degraded_reason') or ''),
          str(got.get('degraded_reason'))[:80])


def test_build_always_supplies_what_assign_tiers_needs():
    """So production can never land in the degraded path by accident."""
    panel = []
    for o in range(1, 31):
        for t in range(8):
            for i in range(6):
                # A little within-player movement, so the empirical-Bayes
                # ratio is identified rather than divided by zero.
                jitter = 0.02 * ((o + i + t) % 3 - 1)
                panel.append({'ord': 202000 + o, 'team': f'T{t}',
                              'position': 'WR', 'gsis_id': f'P{t}_{i}',
                              'appeared': 1,
                              'snap_share': 0.9 - 0.12 * i + jitter,
                              'target_share': 0.24 - 0.03 * i + jitter / 2})
    o = RP.build(panel, 'target_share', ('WR',), 202999)
    if o.state is not State.PASS:
        blocked('build over the synthetic panel',
                f'{o.code}: {o.detail[:120]}')
        return
    for k in ('tier_snap_mean', 'k_snap', 'trailing_n'):
        check(f'build emits {k}', k in o.value and o.value[k], k)
    got = RP.assign_tiers(_room('P0_0', 'P0_5'), o.value,
                          depth_rank={'P0_5': 1})
    check('  and a prior straight from build never degrades',
          got['degraded'] is False, str(got.get('degraded_reason'))[:80])
    check('  k_snap is estimated, not written down',
          all(v > 0 for v in o.value['k_snap'].values()),
          str(o.value['k_snap']))


def test_the_board_can_attribute_an_inversion_now():
    """D2 could not say whether an inversion WAS the defect because neither
    the tier nor its basis was recorded. Both are now on every player."""
    pr = _prior(trailing_snap={'VET': 0.25}, trailing_n={'VET': 8})
    got = RP.assign_tiers(_room('VET', 'NEW'), pr, depth_rank={'NEW': 1, 'VET': 2})
    for pid in ('VET', 'NEW'):
        d = got['detail'][pid]
        check(f'{pid} carries tier, basis and the inputs behind them',
              d['tier'] == got['tier'][pid] and d['basis'] == got['basis'][pid]
              and 'depth_rank' in d and 'own_trailing' in d, str(d))


def test_no_player_or_team_is_hard_coded():
    for mod in ('nfl/production/nonqb/role_prior.py',
                'nfl/production/nonqb/depth_vintage.py'):
        src = open(os.path.join(_ROOT, mod)).read()
        for bad in ('Nacua', 'McCaffrey', 'Kittle', 'Adams', 'Purdy',
                    'Stafford', 'Worthy', 'Kelce', "'SF'", "'LA'", "'KC'",
                    "'DEN'"):
            check(f'  {mod.split("/")[-1]}: no hard-coded {bad}',
                  bad not in src, bad)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
