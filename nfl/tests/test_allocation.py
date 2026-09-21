"""The widest lawful corpus, and a composition that conserves what it divides.

THE CORPUS DEFECT THIS PINS

`current_season_nonqb_panel` globs one directory and cannot see the governed
vintage store. For 2026 it finds ten week-1 games; the vintage store holds
sixteen, and the six it adds include both clubs of the Monday night game. A
layer asking what the Giants did in week one was told nothing, and nothing is
indistinguishable from no usage unless somebody names it.

The accepted panel is NOT edited. It feeds the accepted R8 and Q9 chain, so
changing which bytes it reads is a production change with its own
before-and-after. The candidate loader sees the whole corpus, reports the
difference, and leaves the panel alone -- and the test checks BOTH halves of
that: that the wider corpus really is wider, and that the panel is untouched.

THE ALLOCATION PROPERTIES

1. The composition sums to one. A room whose shares do not is losing or
   inventing opportunity, and everything derived from it inherits that.
2. Renormalising is an ASSUMPTION and is published as one. Both compositions
   travel -- the raw shares that sum to the retained mass, and the
   renormalised shares that sum to one -- with the difference named. On this
   game New York's carries room reassigns 29.7% of its mass, which is the
   difference between a 49% back and a 69% back.
3. Nobody outside the participation-resolved set receives a share, and a
   consumer reading outside the composition fails the gate.
4. No share is smoothed, regressed or bounded. `n_observed_games` travels
   instead, because a shrinkage constant chosen in that file would be a
   fitted constant.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import allocation as AL               # noqa: E402
from nfl.production.universe import participation as PA            # noqa: E402
from nfl.production.universe import player_universe as PU          # noqa: E402
from nfl.production.universe import role_state as RS               # noqa: E402
from nfl.production.universe import usage_vintage as UV            # noqa: E402
from nfl.production.nonqb import (                                 # noqa: E402
    current_season_nonqb_panel as CP)
from sportsplatform.governance.outcome import State                # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T19:35:00Z'
GAME = '2026_02_NYG_LA'
_C = {}


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _ctx():
    if 'wide' not in _C:
        _C['wide_o'] = UV.usage_season(2026, CUT, before_week=2)
        _C['wide'] = _C['wide_o'].value if _C['wide_o'].state is State.PASS \
            else {}
        s = RS.load_snaps(2026, 2)
        _C['snaps'] = s.value if s.state is State.PASS else []
        _C['budget'] = PA.measure_budget(_C['snaps'])
        uni = PU.build(2026, 2, GAME, CUT)
        _C['role'] = RS.assign(uni.value, season=2026, week=2,
                               usage_rows=_C['wide'])
        _C['part'] = PA.assess(_C['role'].value, budget=_C['budget'].value)
    return _C


def _alloc(room):
    c = _ctx()
    k = f'alloc::{room}'
    if k not in _C:
        _C[k] = AL.allocate(c['part'], c['wide'], room=room)
    return _C[k]


def test_the_candidate_corpus_is_wider_and_the_accepted_panel_is_untouched():
    c = _ctx()
    o = c['wide_o']
    ok(o.state is State.PASS, f'the widest lawful corpus loads: {o.code}')
    e = o.evidence
    ok(e['n_games'] > e['accepted_panel_sees_n_games'],
       f'it is genuinely wider: {e["n_games"]} games against the accepted '
       f'panel\'s {e["accepted_panel_sees_n_games"]}')
    extra = e['games_the_accepted_panel_cannot_see']
    ok(extra, f'and names exactly what the panel cannot see: {len(extra)}')
    ok(any('NYG' in g for g in extra) and any('KC' in g for g in extra),
       f'including both Monday clubs, which is why this matters tonight: '
       f'{extra}')
    ok(e['store'] == 'vintage',
       f'the widest blob comes from the governed store: {e["store"]}')
    ok(len(e['clubs']) == 32,
       f'every club in the league is measured: {len(e["clubs"])}')
    ok(e['counting_imported_from'] == 'current_season_nonqb_panel',
       'the counting rules are imported, so there is no second definition of '
       'a target to drift from the first')
    ok(e['counting_rules'] is CP.COUNTING_RULES,
       'and it is the same object, not a copy')

    # THE ACCEPTED PANEL IS UNTOUCHED. Its glob still names one directory and
    # it still sees what it saw.
    ok(CP.PBP_GLOB == 'nfl/research/postgame/pbp_%d.*.csv.gz',
       f'the accepted panel still globs one directory: {CP.PBP_GLOB}')
    acc = CP.usage_season(2026, as_of=CUT)
    ok(acc.state is State.PASS,
       f'the accepted panel still runs unchanged: {acc.code}')
    ok(len(acc.evidence['games']) == e['accepted_panel_sees_n_games'],
       f'and still sees its own {len(acc.evidence["games"])} game(s)')


def test_the_corpus_is_never_its_own_evidence():
    c = _ctx()
    ok(all(v['week'] < 2 for v in c['wide'].values()),
       'no row from week 2 or later is in a week-2 forecast\'s corpus')
    late = UV.usage_season(2026, '2020-01-01T00:00:00Z', before_week=2)
    ok(late.state is State.BLOCKED and late.code == 'USAGE_NO_LAWFUL_CAPTURE',
       f'a cut before every capture blocks rather than reaching back: '
       f'{late.code}')
    bad = UV.usage_season(2026, 'whenever', before_week=2)
    ok(bad.state is State.BLOCKED and bad.code == 'USAGE_CUT_UNPARSEABLE',
       f'an unparseable cut is refused, because a corpus selected without a '
       f'clock may contain its own answer: {bad.code}')
    w1 = UV.usage_season(2026, CUT, before_week=1)
    ok(w1.state is State.BLOCKED,
       f'week 1 has no prior week and the loader says so: {w1.code}')


def test_the_composition_sums_to_one():
    for room in (RS.ROOM_TARGETS, RS.ROOM_CARRIES):
        ao = _alloc(room)
        ok(ao.state is State.PASS, f'{room} composes: {ao.code}')
        for club, v in ao.evidence['clubs'].items():
            s = sum(r['share_renormalised'] for r in ao.value
                    if r['team'] == club
                    and r['share_renormalised'] is not None)
            ok(abs(s - 1.0) < 1e-9,
               f'{club} {room}: the renormalised composition sums to '
               f'{s:.12f}')
            raw = sum(r['share_of_measured'] for r in ao.value
                      if r['team'] == club
                      and r['share_of_measured'] is not None)
            ok(abs(raw - v['retained_share_mass']) < 1e-9,
               f'{club} {room}: the raw shares sum to the retained mass '
               f'{raw:.6f}, not to one')
            ok(abs((v['retained_share_mass'] + v['reassigned_mass']) - 1.0)
               < 1e-9,
               f'{club} {room}: retained plus reassigned is one, so the '
               f'missing mass is accounted rather than dropped')
        g = AL.assert_allocation_conserves(
            ao, consuming_ids={r['gsis_id'] for r in ao.value
                               if r['allocation_state'] == AL.ALLOCATED})
        ok(g.state is State.PASS, f'{room} passes the conservation gate: '
                                  f'{g.code}')


def test_renormalisation_is_published_as_an_assumption():
    ao = _alloc(RS.ROOM_CARRIES)
    for club, v in ao.evidence['clubs'].items():
        ok('assumption, not a measurement' in v['renormalisation_assumption'],
           f'{club}: the assumption is stated in words on the club record')
        ok(v['reassigned_mass'] is not None,
           f'{club}: and its size is given: {v["reassigned_mass"]:+.4f}')
    rows = [r for r in ao.value if r['share_renormalised'] is not None]
    ok(all(r['share_renormalised'] >= r['share_of_measured'] - 1e-12
           for r in rows),
       'renormalising never reduces a share, so the direction of the '
       'assumption is visible')
    big = [r for r in rows
           if r['share_renormalised'] - r['share_of_measured'] > 0.10]
    ok(all(r['share_of_measured'] is not None for r in big),
       f'{len(big)} player(s) gain more than ten points from the assumption '
       f'and each keeps his unassumed number beside it')
    ok(all(r['n_observed_games'] is not None for r in rows),
       'every share carries how many games it rests on')
    ok(any(r['evidence_is_thin'] for r in rows),
       'and thin evidence is flagged rather than left for a reader to notice')
    ok('fitted constant' in ao.evidence['no_shrinkage_note'],
       'the layer states that it smooths nothing and why')


def test_nobody_outside_the_resolved_set_receives_a_share():
    c = _ctx()
    prows = c['part'].value or (c['part'].evidence or {}).get('value') or []
    resolved = {r['gsis_id'] for r in prows
                if r['participation_state'] == PA.RESOLVED}
    for room in (RS.ROOM_TARGETS, RS.ROOM_CARRIES):
        ao = _alloc(room)
        got = {r['gsis_id'] for r in ao.value
               if r['share_of_measured'] is not None}
        ok(got <= resolved,
           f'{room}: every allocated player is participation-resolved '
           f'({len(got - resolved)} outside)')
        none_ = [r for r in ao.value
                 if r['allocation_state'] == AL.NO_EVIDENCE]
        ok(all(r['share_of_measured'] is None for r in none_),
           f'{room}: a resolved player with no measured opportunity gets no '
           f'share')
        ok(all('not set to zero' in (r.get('why') or '') for r in none_),
           f'{room}: and the row distinguishes "no target" from "not '
           f'measured", which are different facts')

    ao = _alloc(RS.ROOM_TARGETS)
    g = AL.assert_allocation_conserves(ao, consuming_ids={'00-9999999'})
    ok(g.state is State.FAIL
       and g.code == 'CONSUMER_READS_OUTSIDE_THE_COMPOSITION',
       f'a consumer reading a player the composition does not contain fails: '
       f'{g.code}')
    ok(AL.assert_allocation_conserves(ao).state is State.BLOCKED,
       'and no declared consumer blocks rather than certifying')


def test_concentration_is_reported_against_the_league_not_a_feeling():
    for room in (RS.ROOM_TARGETS, RS.ROOM_CARRIES):
        ao = _alloc(room)
        for club, v in ao.evidence['clubs'].items():
            c = v['concentration']
            ok(c['n'] > 0, f'{club} {room}: the room has players: {c["n"]}')
            ok(abs(c['top3'] - min(1.0, c['top3'])) < 1e-12
               and c['top1'] <= c['top2'] + 1e-12 <= c['top3'] + 1e-12,
               f'{club} {room}: top-k is non-decreasing in k')
            ok(0 < c['hhi'] <= 1.0 + 1e-12,
               f'{club} {room}: HHI is a proportion: {c["hhi"]:.4f}')
            ok(abs(c['effective_players'] - 1.0 / c['hhi']) < 1e-9,
               f'{club} {room}: effective players is 1/HHI')
            ok(c['entropy_max_nats'] is not None
               and c['entropy_nats'] <= c['entropy_max_nats'] + 1e-12,
               f'{club} {room}: entropy is reported beside its maximum, '
               f'because entropy alone is not comparable between room sizes')
            vl = v['concentration_vs_league']['top1']
            ok(vl['league_median'] is not None
               and vl['percentile_in_league'] is not None,
               f'{club} {room}: concentration is placed against the league '
               f'({vl["value"]:.3f} vs median {vl["league_median"]:.3f}, '
               f'p{vl["percentile_in_league"]:.0%})')
        ok(ao.evidence['league_frame_state'] == 'ALLOCATION_LEAGUE_FRAME',
           f'{room}: the reference frame is measured from the same bytes at '
           f'the same cut')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_the_candidate_corpus_is_wider_and_the_accepted_panel_is_untouched,
              test_the_corpus_is_never_its_own_evidence,
              test_the_composition_sums_to_one,
              test_renormalisation_is_published_as_an_assumption,
              test_nobody_outside_the_resolved_set_receives_a_share,
              test_concentration_is_reported_against_the_league_not_a_feeling):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
