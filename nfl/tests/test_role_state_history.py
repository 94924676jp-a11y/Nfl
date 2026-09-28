#!/usr/bin/env python3.12
"""A pregame role state must be pregame, and the oracle arm must be unable to pretend it isn't.

`forward_chain.historical_band` said a historical role state was not reconstructible, so the cap that
stops an injury-replacement share outliving the injury was asserted in production and measured
nowhere. It is reconstructible from prior weeks. The risk in doing so is obvious: ROLE_HISTORY already
carries a `depth_rank` per season-week that LOOKS like what is wanted and is ranked on that week's own
usage, so reading it would be direct outcome leakage under a plausible name.

So the load-bearing check here rebuilds the state from a panel with the scored week and everything
after it deleted, and requires every band and rank to be identical. The others make the two arms
refuse to be confused with each other.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# NOT `as F`/`as P`: run_suite.tally() treats module-level names P and F as a
# pass/fail counter pair, so single-letter module aliases here crashed the runner.
from nfl.tools import forward_chain as FC  # noqa: E402
from nfl.tools import player_prior as PP  # noqa: E402
from nfl.tools import role_state_history as RH  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []
_CACHE = {}


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _ctx(season):
    if season not in _CACHE:
        po = PP.load_panel()
        assert po.state.name == 'PASS', po.detail
        panel = po.value
        roster_pos = PP.position_index()
        pos_map, _inf = FC.positions_for_chain(panel, roster_pos)
        _CACHE[season] = (panel, FC._SeasonPos(pos_map, season, roster_pos))
    return _CACHE[season]


@check('the state is identical when the scored week and everything after it is deleted')
def t_no_leakage():
    checked = []
    for season, week in ((2023, 6), (2024, 8), (2024, 15), (2025, 5)):
        panel, sp = _ctx(season)
        o = RH.assert_no_leakage(panel, sp, season, week, FC.historical_band)
        assert o.state.name == 'PASS', (
            f'{season} week {week}: {o.code} {o.detail} {o.evidence.get("moved", "")[:3]}')
        checked.append(f'{season}w{week}:{o.value["n_players_checked"]}')
    return 'point-in-time at ' + ', '.join(checked)


@check('a prior week beyond the lookback window cannot reach the rank')
def t_lookback_bounded():
    panel, sp = _ctx(2024)
    d = RH.pregame_depth(panel, sp, 2024, 12)
    trimmed = {'players': {}, 'teams': panel['teams']}
    for g, ss in panel['players'].items():
        trimmed['players'][g] = {
            s: {w: r for w, r in ws.items()
                if not (int(s) == 2024 and int(w) < 12 - RH.LOOKBACK_WEEKS)}
            for s, ws in ss.items()}
    d2 = RH.pregame_depth(trimmed, sp, 2024, 12)
    moved = [g for g in set(d) & set(d2) if d[g]['pregame_rank'] != d2[g]['pregame_rank']]
    assert not moved, (
        f'{len(moved)} ranks change when weeks outside the declared {RH.LOOKBACK_WEEKS}-week '
        f'lookback are removed, so the window is not the window it says it is')
    return f'ranks unchanged when everything before week {12 - RH.LOOKBACK_WEEKS} is removed'


@check('the oracle arm refuses to run without its oracle')
def t_oracle_needs_oracle():
    panel, sp = _ctx(2024)
    o = RH.role_state_for_week(panel, sp, 2024, 8, FC.historical_band, arm=RH.ARM_ORACLE)
    assert o.state.name == 'FAIL' and o.code == 'ORACLE_ARM_WITHOUT_ORACLE', o.code
    return 'asking for the oracle arm with no appearance set FAILs rather than quietly going pregame'


@check('the pregame arm refuses to be handed the outcome')
def t_pregame_refuses_outcome():
    panel, sp = _ctx(2024)
    o = RH.role_state_for_week(panel, sp, 2024, 8, FC.historical_band, arm=RH.ARM_PREGAME,
                               appeared={'00-0000001'})
    assert o.state.name == 'FAIL' and o.code == 'PREGAME_ARM_GIVEN_THE_OUTCOME', o.code
    return 'handing the appearance set to the pregame arm FAILs instead of being ignored'


@check('the two arms differ, and the pregame arm states that availability is unknown')
def t_arms_differ():
    panel, sp = _ctx(2024)
    import json as _j
    pg = _j.loads((_REPO / 'nfl/warehouse/PLAYER_GAME.json').read_text())['rows']
    appeared = {r['player_id'] for r in pg.values()
                if r['season'] == 2024 and int(r['week']) == 8}
    a = RH.role_state_for_week(panel, sp, 2024, 8, FC.historical_band)
    b = RH.role_state_for_week(panel, sp, 2024, 8, FC.historical_band, arm=RH.ARM_ORACLE,
                               appeared=appeared)
    assert a.state.name == b.state.name == 'PASS'
    diff = [g for g in set(a.value['rows']) & set(b.value['rows'])
            if a.value['rows'][g]['role_band'] != b.value['rows'][g]['role_band']]
    assert diff, ('the oracle arm produced the same state as the pregame arm, so either no starter '
                  'missed week 8 of 2024 or the oracle is not wired in')
    assert 'OUT-038' in a.value['AVAILABILITY'], (
        'the pregame arm must say that availability is unknown and name what would fix it, rather '
        'than presenting an unknown as a known')
    assert 'ORACLE' in b.value['AVAILABILITY']
    return f'{len(diff)} players differ between the arms; the pregame arm names OUT-038'


@check('the cap only ever lowers a band, never raises one')
def t_cap_direction():
    panel, sp = _ctx(2024)
    o = RH.role_state_for_week(panel, sp, 2024, 8, FC.historical_band)
    raised = [g for g, r in o.value['rows'].items()
              if RH.TIER_ORDER.index(r['role_band']) > RH.TIER_ORDER.index(r['band_before_cap'])]
    assert not raised, (
        f'{len(raised)} players come out of the cap STRONGER than they went in. A ceiling that '
        f'promotes is not a ceiling, and it would hand an unearned starter share to a reserve.')
    capped = sum(1 for r in o.value['rows'].values() if r['was_capped'])
    assert capped, 'nothing was capped at all, so the mechanism is not reaching any player'
    n = len(o.value['rows'])
    return f'{capped} of {n} players capped, none raised'


@check('a player with no prior usage in the window gets a floor, not a starter slot')
def t_no_usage_is_not_a_starter():
    panel, sp = _ctx(2024)
    d = RH.pregame_depth(panel, sp, 2024, 8)
    none_used = [r for r in d.values() if r['ceiling_source'] == 'NO_PRIOR_USAGE_IN_LOOKBACK']
    assert none_used, 'no player lacked prior usage, so this path is untested on real data'
    assert all(r['pregame_rank'] is None and r['ceiling'] == RH.CEILING_BEYOND_RANK_3
               for r in none_used), 'a player with no prior usage was given a rank'
    return (f'{len(none_used)} players with no usage in the window are unranked at '
            f'{RH.CEILING_BEYOND_RANK_3}, not promoted into an empty slot')


@check('the study artifact keeps the oracle arm separated from the pregame arm')
def t_artifact_labels_the_oracle():
    art = _REPO / 'nfl/research/rolestate/ROLE_STATE_STUDY.json'
    if not art.exists():
        raise AssertionError(f'{art} not built; run nfl/research/rolestate/study.py')
    d = json.loads(art.read_text())
    txt = d['ORACLE_ARM_IS_NOT_LIVE_PERFORMANCE']
    assert 'never be quoted as live performance' in txt and 'OUT-038' in txt
    assert d['PROJECTION_SYSTEM_STATE'] == 'NOT_VALIDATED', (
        'one demonstrated cell is not a validated system, and the artifact must not say otherwise')
    assert 'WEEKLY_CAPPED_ORACLE' in d['PREREGISTERED']['arms']
    assert d['PREREGISTERED']['reference_arm'] == 'SEASON_CONSTANT'
    return 'the oracle is labelled, names what would close the gap, and NOT_VALIDATED still holds'


@check('the superseding claim in the artifact matches the numbers in the artifact')
def t_supersede_is_backed():
    d = json.loads((_REPO / 'nfl/research/rolestate/ROLE_STATE_STUDY.json').read_text())
    vs = d['paired_vs_current_season_only']
    sc = vs['SEASON_CONSTANT']
    wk = vs['WEEKLY_CAPPED_PREGAME']
    k = 'mean_diff_vs_current_season_only'
    for split in ('selection', 'confirmation'):
        assert sc[f'{split}.rho'][k] < 0, (
            f'the season-constant band no longer loses to the current-season baseline on {split}, '
            f'so it no longer reproduces FORWARD_CHAIN_VERDICT.md and the supersede note is stale')
        assert wk[f'{split}.rho'][k] > 0, (
            f'the weekly capped band no longer beats the current-season baseline on {split}. '
            f'FORWARD_CHAIN_VERDICT.md is marked superseded on exactly this, so if this flips back '
            f'that note and the GAP_STATUS confidence line are both wrong and must be reverted.')
        z = wk[f'{split}.rho']['z']
        assert z is not None and z > 2, f'{split} z is {z}, below the 2 the write-up claims'
    sup = (_REPO / 'nfl/production/FORWARD_CHAIN_VERDICT.md').read_text()
    assert 'SUPERSEDED 2026-09-28' in sup, (
        'the verdict document must carry the supersede note, or its ranking conclusion will be '
        'quoted again by the next session')
    return (f'season-constant {sc["selection.rho"][k]:+.4f} loses, weekly capped '
            f'{wk["selection.rho"][k]:+.4f} wins, z {wk["selection.rho"]["z"]}')


# EXPOSE EVERY CHECK TO run_suite, which is the authoritative execution path. Without this the
# runner reports `0 fn, NO TALLY` and executes NONE of them, while a direct run of this file prints
# a confident pass. See nfl/tests/_registry.py.
_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    test_zz_every_check_passed.__doc__
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
