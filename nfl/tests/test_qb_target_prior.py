#!/usr/bin/env python3.12
"""The cross-field depth prior (DEFECT-QBTGT, 2026-10-02), forced in both directions.

Each position's depth table is measured on ONE field (QB on pass attempts, RB on carries,
WR/TE on targets). The allocator reused that one share as the prior for every field, so a
quarterback's 0.95 pass-attempt share became his target prior and Deshaun Watson carried 5.04
projected targets; nine of sixty main-slate quarterbacks carried 4.4-5.7. The simulator gives a
quarterback no target share, so those targets went to nobody in every joint world.

The fix: when the table's field differs from the field being allocated, the prior is the
measured GROUP SPLIT for that field times the WITHIN-GROUP concentration the table gives. When
the fields match, the table's share is already a club share and is used as before.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import proj_v1 as PV  # noqa: E402
from nfl.tools import football_sanity as FS  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _club():
    """One club: a starting QB with a measured ZERO target claim, a back, two receivers."""
    def row(name, pos, claims, **kw):
        r = {'name': name, 'position': pos, '_claims': claims, '_dk': name,
             'is_predicted_starter': kw.pop('starter', False), 'role_band': kw.pop('band', 'PRIMARY')}
        r.update(kw)
        return r
    crows = [
        row('QB One', 'QB', {'pass_attempts': 0.99, 'carries': 0.27, 'targets': 0.0}, starter=True, band='ALPHA'),
        row('Back One', 'RB', {'pass_attempts': 0.0, 'carries': 0.60, 'targets': 0.10}, starter=True, band='ALPHA'),
        row('Wide One', 'WR', {'pass_attempts': 0.0, 'carries': 0.01, 'targets': 0.28}, starter=True, band='ALPHA'),
        row('Wide Two', 'WR', {'pass_attempts': 0.0, 'carries': 0.0, 'targets': 0.18}, band='SECONDARY'),
    ]
    tv = {'proj_pass_attempts': 34.0, 'proj_rush_attempts': 25.0, 'proj_targets': 30.0}
    # depth tables: ONE per position, measured on that position's own field (club shares)
    depth = {
        'QB': {'by_rank': {'rank_1': {'unconditional_expected_share': 0.95, 'appearance_rate': 1.0}}},
        'RB': {'by_rank': {'rank_1': {'unconditional_expected_share': 0.50, 'appearance_rate': 1.0}}},
        'WR': {'by_rank': {'rank_1': {'unconditional_expected_share': 0.25, 'appearance_rate': 1.0},
                           'rank_2': {'unconditional_expected_share': 0.15, 'appearance_rate': 1.0}}},
    }
    # measured group split of the CLUB's targets and carries by position group
    groups = {'targets': {'QB': 0.0005, 'RB': 0.20, 'WR': 0.55, 'TE': 0.2495},
              'carries': {'QB': 0.19, 'RB': 0.78, 'WR': 0.03, 'TE': 0.0}}
    return crows, tv, depth, groups


@check('a quarterback whose table measures pass attempts gets a near-zero TARGET prior, not 0.95')
def _qb_targets_near_zero():
    crows, tv, depth, groups = _club()
    PV.allocate_opportunity(crows, tv, depth, groups)
    qb = crows[0]
    a = qb['allocation']['targets']
    assert a['depth_prior_basis'] == 'GROUP_SPLIT_X_WITHIN_GROUP_CONCENTRATION', a
    assert a['depth_table_measured_on'] == 'pass_attempts'
    assert qb['targets'] < 0.1, qb['targets']
    assert a['prior_expected_share_normalised'] < 0.01, a
    return f"QB targets {qb['targets']:.4f}, prior share {a['prior_expected_share_normalised']}"


@check('the SAME-field branch is unchanged: a receiver\'s target prior is the table\'s club share as before')
def _same_field_unchanged():
    crows, tv, depth, groups = _club()
    PV.allocate_opportunity(crows, tv, depth, groups)
    w1 = crows[2]['allocation']['targets']
    assert w1['depth_prior_basis'] == 'CLUB_SHARE_OF_SAME_FIELD', w1
    assert w1['depth_share_in_group_measured'] == 0.25
    assert 'prior_expected_share_of_club' not in w1
    return f"WR1 prior basis {w1['depth_prior_basis']}, table share {w1['depth_share_in_group_measured']}"


@check('the club identity still holds by construction after the fix: targets and carries sum to the club')
def _identity_holds():
    crows, tv, depth, groups = _club()
    acct = PV.allocate_opportunity(crows, tv, depth, groups)
    for field, key in (('targets', 'proj_targets'), ('carries', 'proj_rush_attempts'), ('pass_attempts', 'proj_pass_attempts')):
        s = sum(r[field] for r in crows)
        assert abs(s - tv[key]) < 1e-6, (field, s, tv[key])
        assert acct[field]['IDENTITY_BY_CONSTRUCTION'] is True
    return f"targets {sum(r['targets'] for r in crows):.3f}/30, carries {sum(r['carries'] for r in crows):.3f}/25"


@check('a quarterback\'s CARRY prior now carries the measured 0.19 group split, not his pass-attempt share')
def _qb_carries_use_group_split():
    crows, tv, depth, groups = _club()
    PV.allocate_opportunity(crows, tv, depth, groups)
    a = crows[0]['allocation']['carries']
    assert a['depth_prior_basis'] == 'GROUP_SPLIT_X_WITHIN_GROUP_CONCENTRATION'
    assert abs(a['prior_expected_share_of_club'] - 0.19) < 1e-9, a
    return f"QB carry prior share of club {a['prior_expected_share_of_club']} (= group split x 1.0 concentration)"


@check('the gate REFUSES a quarterback above one projected target a game, and passes him with a reason or below it')
def _gate():
    from nfl.tests.test_football_sanity import _clean

    def with_qb_targets(tg, reason=None):
        # the club total moves with the row, so club reconciliation stays exact and the ONLY
        # thing under test is the quarterback ceiling
        a = _clean(); a['rows']['q1']['targets'] = tg; a['team_volume']['AAA']['proj_targets'] += tg
        if reason:
            a['rows']['q1']['allocation'] = {'targets': {'explicit_reason': reason}}
        return FS.assess(a, absent={'Out Guy'})
    o = with_qb_targets(5.04)
    probs = (o.evidence or {}).get('problems', {})
    assert o.state.name == 'FAIL' and list(probs) == [FS.QB_RECEIVER_VOLUME], (o.code, probs)
    o = with_qb_targets(0.4); assert o.state.name == 'PASS', (o.code, (o.evidence or {}).get('problems'))
    o = with_qb_targets(1.5, 'gadget package measured in weeks 1-3'); assert o.state.name == 'PASS', o.code
    return f"refused at 5.04 ({FS.QB_RECEIVER_VOLUME}); passed at 0.4; passed at 1.5 with a recorded reason"


@check('the delivered PIT/CLE projection is refused by the gate on exactly this defect (historical record, unchanged)')
def _delivered_artifact_refused():
    import json
    p = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ.json'
    if not p.exists():
        return 'artifact absent in this checkout; nothing to assert'
    o = FS.assess(json.loads(p.read_text()))
    probs = (o.evidence or {}).get('problems', {})
    assert o.state.name == 'FAIL' and list(probs) == [FS.QB_RECEIVER_VOLUME], (o.code, list(probs))
    fixed = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ_QBTGT_FIXED.json'
    o2 = FS.assess(json.loads(fixed.read_text()))
    assert o2.state.name == 'PASS', (o2.code, (o2.evidence or {}).get('problems'))
    return f"delivered {o.code}: {probs[FS.QB_RECEIVER_VOLUME]}; rebuilt {o2.code}"


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
