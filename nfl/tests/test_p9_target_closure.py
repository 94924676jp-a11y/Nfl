"""P9: target ownership closure and the receiving/pass-event identity.

WHAT THIS FILE ESTABLISHES, IN THE ORDER IT MATTERS

Two things were asked. One of them closes and one of them does not, and the
difference between them is the whole point of decomposing.

1. THE TARGET PARTITION CLOSES. Against the level the game ACTUALLY consumed
   -- the C3 targeted-throw budget, whose parent `rint(sum qb/att)` is
   recoverable from a sealed board -- the named receivers are contained in
   EVERY draw of every sealed C3 board in this repository, with a residual
   that is never negative. 113 team-runs, 139,800 draws, minimum residual
   0.0000. `deal_targets` partitions an integer budget with a multinomial, so
   this is a construction and not a coincidence.

2. THE PUBLISHED LEVEL IS NOT THAT LEVEL. `team_volume/team_targets` is D1's
   separately drawn CONTINUOUS level. Under C3 nothing consumes it --
   `football_engine` marks it `d1_team_targets_unused: True` -- and
   `run_forecast` seals it anyway under a name that asserts it is the team's
   targets. On the same 139,800 draws the named receivers EXCEED it in 71,550
   (51.18%) by up to +28.63, and equal it in 0.

   On the named cohort board 96954efc523bd7d3 (2026_01_DEN_KC,
   V1_CANDIDATE_R9, 1,000 draws):

       DEN  sum targets 31.6080  published 33.7495  over in 298/1000, max +10.63
       KC   sum targets 34.7630  published 28.7035  over in 926/1000, max +19.04
       both  exact agreement 0/1000; residual against the consumed budget
             never negative, min 0.0000

   This is the receiving analogue of R11's THIRD rush cause and only the
   third. There is no wrong coupling quantity here -- the budget is the whole
   throw process. There is no live second owner -- D1's level is inert, where
   A1's `designed_qb` was not. What remains is: the published level is not the
   level partitioned.

3. THE PRIOR FINDING IS A MIS-SPECIFIED COMPARISON WHEN READ AS A CLOSURE
   TEST. `stored_team_targets_is_not_the_denominator` reports 0 of 100,000
   draws agreeing across 68 team-runs (WS09 J-12, D6_CONSERVATION_DASHBOARD.md
   :291). Its two sides are a published-but-unused draw and the throw budget;
   NEITHER is the partitioned level and the check never gated. Read as its own
   name says -- a gauge on a second owner -- it is correctly specified, and
   test B below reproduces it rather than disputing it.

4. THE C3 PASS-EVENT IDENTITY HOLDS. Team receptions against team
   completions and receiving touchdowns against passing touchdowns are EXACT
   -- 0 violating cells in 139,800 draws, worst absolute difference 0.
   Receiving yards against passing yards is exact to 1.1369e-13, which is
   float summation order over a different row count and not a modelling
   deviation. It reproduces the figure the P4 credit migration reported.

5. WHAT IS INCOHERENT IS ON THE QUARTERBACK SIDE AND IS ALREADY OWNED. 7,407
   cells with cmp > att, 8,291 with cmp + int > att, 1,003 with ptd > cmp and
   16,133 with passing yards on zero completions -- every one on a board built
   by the SUPERSEDED `shared_pass.credit_to_passers`. Split by mode, R9 (11
   runs) and R11 (1 run) carry ZERO. That is the P4 migration's finding and
   its repair, reproduced here so this file does not claim it.

WHAT IS NOT REPAIRED HERE, AND WHY

Publishing the level that was partitioned needs `football_engine.run_game` to
return `tgt_vol`, `c3_other` and `untargeted` as vectors rather than reducing
them to means, and `run_forecast` to seal them beside
`_published_team_carries`. Neither file is this workstream's to edit. What
lands here is the composition point: `shared_pass.compose_pass_event_ownership`
holds all four vectors at once and names which one a board must publish, and
`shared_pass.assert_target_ownership_closure` is the decomposed fence that
says WHICH quantity and WHICH side when it does not.

NOTHING HERE TUNES TO DEN@KC. The realized 2026-09-15 outcome is not in this
repository. The sealed boards are FIXTURES OF THE MEASUREMENT, never a
scoreboard.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.production.nonqb import shared_pass as SP                 # noqa: E402
from nfl.product import conservation as CS                         # noqa: E402

PASSED = FAILED = BLOCKED = 0

EPS = 1e-9
COHORT = pathlib.Path(_ROOT) / (
    'nfl/research/live/2026_01_DEN_KC/'
    'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R9/96954efc523bd7d3')
_RESEARCH = pathlib.Path(_ROOT) / 'nfl' / 'research'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  PASS  {label}' + (f' -- {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL  {label}' + (f' -- {detail}' if detail else ''))


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED  {label} -- {why}')


# --------------------------------------------------------------- loading
def _load(d):
    """One sealed run as {team: vectors}, or None. A missing file is None,
    never an empty dict that would read as a clean run."""
    need = ('player_draws.npz', 'player_draws_manifest.json', 'board.json',
            'forecast_artifact.json')
    if any(not (d / f).exists() for f in need):
        return None
    man = json.load(open(d / 'player_draws_manifest.json'))
    board = json.load(open(d / 'board.json'))
    art = json.load(open(d / 'forecast_artifact.json'))
    z = np.load(d / 'player_draws.npz')
    A = {k.replace('__', '/', 1): z[k].astype(np.float64) for k in z.files}
    tr = CS.team_rows(man, board.get('players'))
    if tr.state is not State.PASS:
        return None
    reg = CS.regime_from_components(art.get('candidate_components_applied'))
    mc = board.get('model_configuration')
    out = {'regime': reg, 'arrays': A, 'teams': {},
           'mode': mc.get('mode') if isinstance(mc, dict) else mc}
    for t, lay in tr.value.items():
        out['teams'][t] = {'recv': list(lay.get('receiving') or []),
                           'qb': list(lay.get('qb') or []),
                           'tv': lay.get('team_volume')}
    return out


def _c3_cohort():
    """Every sealed run that declared C3 and carries both sides of the event."""
    runs = []
    for d in sorted({p.parent for p in _RESEARCH.rglob('player_draws.npz')}):
        r = _load(d)
        if not r or not r['regime'].get('C3'):
            continue
        if 'receiving/targets' not in r['arrays']:
            continue
        if any(v['recv'] and v['qb'] for v in r['teams'].values()):
            runs.append((d, r))
    return runs


# ------------------------------------------- A/B: the reproduction, cohort
def test_a_named_receivers_exceed_the_published_team_target_level():
    """REPRODUCTION, publication side. The board publishes a team target level
    the named receivers are dealt more than.

    This stays in the file after any repair. A board sealed before a repair
    does not stop carrying what it carried, and this records the size.
    """
    r = _load(COHORT)
    if r is None:
        blocked('cohort board readable', f'{COHORT} is not a complete run')
        return
    A = r['arrays']
    seen = 0
    for t, lay in sorted(r['teams'].items()):
        if not lay['recv'] or lay['tv'] is None:
            continue
        seen += 1
        T = A['receiving/targets'][lay['recv']].sum(0)
        lvl = A['team_volume/team_targets'][int(lay['tv'])]
        over = int((T - lvl > EPS).sum())
        exact = int((np.abs(T - lvl) <= EPS).sum())
        check(f'{t}: named receivers exceed the PUBLISHED team target level',
              over > 0,
              f'{over}/{T.size} draws, max excess {(T - lvl).max():+.4f}')
        check(f'{t}: named receivers NEVER equal the published level exactly',
              exact == 0, f'{exact}/{T.size} draws in exact agreement')
        check(f'{t}: the published level is not an integer count',
              bool((np.abs(lvl - np.rint(lvl)) > EPS).any()),
              'it is D1`s continuous draw, sealed under a count`s name')
    check('both teams were measured', seen == 2, f'{seen} team(s)')


def test_b_containment_holds_against_the_level_the_game_consumed():
    """REPRODUCTION, allocation side. The same boards, the same draws, the
    level the partition ACTUALLY consumed. The residual is the untargeted pool
    plus the unmodelled-receiver pool and it is never negative.

    A and B together are what one summed check cannot say: the partition is
    sound and the publication is not.
    """
    runs = _c3_cohort()
    if not runs:
        blocked('C3 cohort', 'no sealed run declares C3 with a receiving '
                             'layer, so there is nothing to reproduce')
        return
    tot = neg = teamruns = 0
    worst = 0.0
    for _d, r in runs:
        A = r['arrays']
        for t, lay in r['teams'].items():
            if not lay['recv'] or not lay['qb']:
                continue
            T = A['receiving/targets'][lay['recv']].sum(0)
            throws = np.rint(A['qb/att'][lay['qb']].sum(0))
            resid = throws - T
            teamruns += 1
            tot += resid.size
            neg += int((resid < -EPS).sum())
            worst = min(worst, float(resid.min()))
    check('sum of named targets never exceeds the consumed throw budget',
          neg == 0,
          f'{neg}/{tot} draws negative over {teamruns} team-runs, '
          f'minimum residual {worst:+.4f}')
    check('the cohort is the whole sealed C3 frame, not a sample',
          teamruns >= 100, f'{teamruns} team-runs, {tot} draws')


def test_c_the_partitioned_level_and_its_pools_are_absent_from_every_board():
    """THE GAP, NAMED. Three of the four vectors of the identity are not
    sealed anywhere, so the exact identity cannot be checked from a board --
    only the weak form `sum targets <= throws` can.

    This is what makes A a publication defect rather than a reporting choice:
    a consumer cannot recover the right denominator even if told to.
    """
    runs = _c3_cohort()
    if not runs:
        blocked('C3 cohort', 'no sealed C3 run to inspect')
        return
    present = set()
    for _d, r in runs:
        for k in r['arrays']:
            for want in SP.TARGET_VECTORS_NOT_SEALED:
                if k.endswith('/' + want) or k.endswith('__' + want):
                    present.add(want)
    check('no sealed board carries targeted / untargeted / other',
          not present, f'found {sorted(present)}' if present else
          f'{len(runs)} run(s) inspected, none carries any of '
          f'{list(SP.TARGET_VECTORS_NOT_SEALED)}')
    check('the module states the identity those vectors belong to',
          'untargeted' in SP.TARGET_IDENTITY and
          'NOT SEALED' in SP.TARGET_IDENTITY)


# ---------------------------------------------- D-F: the composition holds
def _synthetic(n_teams=3, n_recv=5, m=400, seed=99):
    rng = np.random.default_rng(seed)
    att = [rng.integers(0, 14, size=(2, m)).astype(float)
           for _ in range(n_teams)]
    share = rng.random((n_teams * n_recv, m)) + 0.01
    other = rng.random((n_teams, m)) * 0.3 + 0.01
    starts = [k * n_recv for k in range(n_teams)]
    counts = [n_recv] * n_teams
    return att, share, other, starts, counts


def test_d_composition_closes_both_halves_by_construction():
    """The identity, on inputs a corpus does not contain. Both halves are
    asserted separately so a failure names the half it is in."""
    att, share, other, starts, counts = _synthetic()
    o = SP.compose_pass_event_ownership(
        att, share, other, starts, counts, 0.0423,
        np.random.default_rng(7))
    if o.state is not State.PASS:
        check('compose_pass_event_ownership returns PASS', False,
              f'{o.state.value}[{o.code}] {o.detail[:120]}')
        return
    v = o.value
    per_team = np.stack([v['targets'][s0:s0 + c].sum(0)
                         for s0, c in zip(starts, counts)])
    check('partition half: sum_i targets_i + other == targeted, every cell',
          bool((per_team + v['other'] == v['targeted']).all()),
          f'{int((per_team + v["other"] != v["targeted"]).sum())} violating')
    check('budget half: targeted + untargeted == throws, every cell',
          bool((v['targeted'] + v['untargeted'] == v['throws']).all()),
          f'{int((v["targeted"] + v["untargeted"] != v["throws"]).sum())} '
          f'violating')
    check('whole identity: throws == untargeted + named + other, every cell',
          bool((v['untargeted'] + per_team + v['other'] ==
                v['throws']).all()))
    check('every vector is an integer count',
          all(np.issubdtype(v[k].dtype, np.integer)
              for k in ('targeted', 'untargeted', 'throws', 'other')))


def test_e_the_published_level_is_the_level_that_was_partitioned():
    """What the composition names as publishable IS the denominator the
    multinomial dealt from, and it is integral. This is the clause R11 had to
    add on the rush side and the one still missing on this one."""
    att, share, other, starts, counts = _synthetic(seed=1234)
    o = SP.compose_pass_event_ownership(
        att, share, other, starts, counts, 0.0423,
        np.random.default_rng(11))
    if o.state is not State.PASS:
        check('composition returns PASS', False, o.code)
        return
    v = o.value
    check('published_level IS targeted, element for element',
          bool((v['published_level'] == v['targeted']).all()))
    check('published_level is integral',
          bool(not (np.abs(v['published_level'] -
                           np.rint(v['published_level'])) > EPS).any()))
    check('the evidence says which level it is, in words',
          'team_volume/team_targets' in
          (o.evidence.get('published_level_is') or ''))


def test_f_the_composition_neither_clips_nor_renormalises():
    """No drawn value is altered. The composed targets are EXACTLY what
    `deal_targets` produces from the same generator state, so the composition
    is an ordering of existing calls and not a new estimator."""
    att, share, other, starts, counts = _synthetic(seed=555)
    o = SP.compose_pass_event_ownership(
        att, share, other, starts, counts, 0.0423,
        np.random.default_rng(31337))
    if o.state is not State.PASS:
        check('composition returns PASS', False, o.code)
        return
    rng = np.random.default_rng(31337)
    tgt = []
    for a in att:
        t = SP.targeted_throws(a, 0.0423, rng)
        if t.state is not State.PASS:
            check('replay targeted_throws', False, t.code)
            return
        tgt.append(t.value)
    dealt = SP.deal_targets(share, other, [x['targeted'] for x in tgt],
                            starts, counts, rng)
    if dealt.state is not State.PASS:
        check('replay deal_targets', False, dealt.code)
        return
    check('composed targets are bit-identical to the uncomposed deal',
          bool((np.asarray(o.value['targets']) ==
                np.asarray(dealt.value['targets'])).all()))
    check('composed other pool is bit-identical to the uncomposed deal',
          bool((np.asarray(o.value['other']) ==
                np.asarray(dealt.value['other'])).all()))
    check('the composition declares that it clips nothing',
          o.evidence.get('no_clip_truncation_or_renormalisation') is True)


# -------------------------------------------------- G/H: the fence itself
def test_g_the_closure_fence_rejects_a_seeded_breach():
    """The passes above must come from the guard, not from clean inputs. One
    target is moved into a receiver's row without moving the level."""
    m = 50
    lvl = np.full(m, 30.0)
    named = np.full(m, 28.0)
    op = np.full(m, 2.0)
    ut = np.zeros(m)
    ok = SP.assert_target_ownership_closure(
        ['AA'], {'AA': lvl}, {'AA': named}, {'AA': op}, {'AA': ut})
    check('the fence passes an exact partition', ok.state is State.PASS,
          f'{ok.state.value}[{ok.code}]')
    named2 = named.copy()
    named2[7] += 1.0
    bad = SP.assert_target_ownership_closure(
        ['AA'], {'AA': lvl}, {'AA': named2}, {'AA': op}, {'AA': ut})
    check('the fence REFUSES a one-target breach', bad.state is State.FAIL,
          f'{bad.state.value}[{bad.code}]')
    check('the refusal names which side moved',
          any(s == 'full_partition' for _t, s, _n, _w in
              (bad.evidence.get('violations') or [])),
          str(bad.evidence.get('violations')))
    check('the refusal counts exactly one draw',
          (bad.evidence.get('per_team') or {}).get('AA', {}).get(
              'full_partition_draws_not_exact') == 1)


def test_h_the_fence_names_which_side_moved_on_the_sealed_board():
    """Run the fence on the cohort exactly as a consumer would: with the
    PUBLISHED level and the only vector a board carries. It refuses, and it
    refuses on `named_plus_other` -- naming the receivers-against-the-level
    side rather than asserting a closure the artifact cannot express."""
    r = _load(COHORT)
    if r is None:
        blocked('cohort board readable', f'{COHORT} is not a complete run')
        return
    A = r['arrays']
    lvl, named = {}, {}
    for t, lay in r['teams'].items():
        if not lay['recv'] or lay['tv'] is None:
            continue
        lvl[t] = A['team_volume/team_targets'][int(lay['tv'])]
        named[t] = A['receiving/targets'][lay['recv']].sum(0)
    if not lvl:
        blocked('cohort has receiving rows', 'no team carries both vectors')
        return
    o = SP.assert_target_ownership_closure(sorted(lvl), lvl, named)
    check('the fence refuses the PUBLISHED level', o.state is State.FAIL,
          f'{o.state.value}[{o.code}]')
    sides = {s for _t, s, _n, _w in (o.evidence.get('violations') or [])}
    check('and it names the side, not a single summed number',
          sides and sides <= {'named_plus_other', 'full_partition'},
          str(sorted(sides)))
    for t, rec in sorted((o.evidence.get('per_team') or {}).items()):
        check(f'{t}: the fence records that the pools were not supplied',
              rec['other_pool_supplied'] is False and
              rec['untargeted_supplied'] is False,
              'a board carries neither, which is the gap test C names')


# ------------------------------------------- I/J/K: the pass-event identity
def test_i_the_c3_identity_holds_per_draw_across_the_sealed_frame():
    """Receptions against completions, receiving yards against passing yards,
    receiving touchdowns against passing touchdowns. Reported SEPARATELY --
    a single pass/fail over three quantities is what hides the one that moved.
    """
    runs = _c3_cohort()
    if not runs:
        blocked('C3 cohort', 'no sealed C3 run with both sides')
        return
    agg = {}
    for _d, r in runs:
        A = r['arrays']
        for t, lay in r['teams'].items():
            if not lay['recv'] or not lay['qb']:
                continue
            for name, qk, rk in (
                    ('receptions vs completions', 'qb/cmp',
                     'receiving/receptions'),
                    ('receiving yards vs passing yards', 'qb/pyds',
                     'receiving/receiving_yards'),
                    ('receiving TD vs passing TD', 'qb/ptd',
                     'receiving/receiving_td')):
                q, rr = A.get(qk), A.get(rk)
                if q is None or rr is None:
                    continue
                d = np.abs(q[lay['qb']].sum(0) - rr[lay['recv']].sum(0))
                a = agg.setdefault(name, [0, 0, 0.0])
                a[0] += d.size
                a[1] += int((d > EPS).sum())
                a[2] = max(a[2], float(d.max()))
    if not agg:
        blocked('identity quantities', 'no board carries both sides')
        return
    for name, (cells, bad, worst) in sorted(agg.items()):
        check(f'{name}: closes in every draw', bad == 0,
              f'{bad}/{cells} violating, worst |diff| {worst:.6g}')
    yd = agg.get('receiving yards vs passing yards')
    if yd:
        check('the yards residual is float summation order, not a deviation',
              yd[2] < 1e-9, f'worst {yd[2]:.6g} on integer-valued yardage')


def test_j_receiving_side_per_player_coherence():
    """The receiving rows themselves. A reception needs a target, a receiving
    touchdown needs a reception, and yardage on zero receptions is the defect
    class the superseded passer credit carried."""
    runs = _c3_cohort()
    if not runs:
        blocked('C3 cohort', 'no sealed C3 run')
        return
    cells = rc_gt = td_gt = yd_zero = 0
    for _d, r in runs:
        A = r['arrays']
        for _t, lay in r['teams'].items():
            ri = lay['recv']
            if not ri:
                continue
            tg, rc = A.get('receiving/targets'), A.get('receiving/receptions')
            ry = A.get('receiving/receiving_yards')
            rt = A.get('receiving/receiving_td')
            if tg is None or rc is None:
                continue
            cells += rc[ri].size
            rc_gt += int((rc[ri] - tg[ri] > EPS).sum())
            if rt is not None:
                td_gt += int((rt[ri] - rc[ri] > EPS).sum())
            if ry is not None:
                yd_zero += int(((ry[ri] != 0) & (rc[ri] == 0)).sum())
    check('no receiver has more receptions than targets', rc_gt == 0,
          f'{rc_gt}/{cells} player-draw cells')
    check('no receiver has more receiving TDs than receptions', td_gt == 0,
          f'{td_gt}/{cells} cells')
    check('no receiver has receiving yards on zero receptions', yd_zero == 0,
          f'{yd_zero}/{cells} cells')


def test_k_passer_line_incoherence_is_confined_to_pre_r9_boards():
    """NOT THIS WORKSTREAM'S DEFECT, measured rather than assumed.

    `shared_pass.credit_to_passers` can hand a quarterback more completions
    than attempts and yardage on zero completions. It is SUPERSEDED by
    `football_engine.credit_passing_line`. If the replacement works, boards
    built by it carry none of that -- and this is the check that says so
    instead of trusting the docstring.
    """
    runs = _c3_cohort()
    if not runs:
        blocked('C3 cohort', 'no sealed C3 run')
        return
    bymode = {}
    for _d, r in runs:
        A = r['arrays']
        cm, at = A.get('qb/cmp'), A.get('qb/att')
        it, pt, py = A.get('qb/int'), A.get('qb/ptd'), A.get('qb/pyds')
        if cm is None or at is None:
            continue
        bad = int(((cm - at) > EPS).sum())
        if it is not None:
            bad += int(((cm + it - at) > EPS).sum())
        if pt is not None:
            bad += int(((pt - cm) > EPS).sum())
        if py is not None:
            bad += int(((py != 0) & (cm == 0)).sum())
        b = bymode.setdefault(r['mode'], [0, 0])
        b[0] += 1
        b[1] += bad
    for mode, (n, bad) in sorted(bymode.items()):
        print(f'    {mode}: {n} run(s), {bad} incoherent QB cell(s)')
    modern = {m: v for m, v in bymode.items()
              if m in ('V1_CANDIDATE_R9', 'V1_CANDIDATE_R10',
                       'V1_CANDIDATE_R11', 'V1_CANDIDATE_R12')}
    check('boards built by the replacement carry zero incoherent QB cells',
          bool(modern) and all(v[1] == 0 for v in modern.values()),
          ', '.join(f'{m} {v[1]}' for m, v in sorted(modern.items()))
          or 'no post-R9 board in the cohort')
    legacy = sum(v[1] for m, v in bymode.items() if m not in modern)
    check('the superseded credit`s boards still carry it, and are not '
          'silently rewritten', legacy > 0,
          f'{legacy} cell(s) across pre-R9 modes')
    check('the module still marks the function superseded',
          'SUPERSEDED' in SP.CREDIT_TO_PASSERS_STATUS and
          SP.CREDIT_TO_PASSERS_REPLACEMENT.endswith('credit_passing_line'))


def test_l_the_module_states_the_publication_defect_by_name():
    """A finding that lives only in a report goes stale. The status string is
    in the module a future reader opens first."""
    s = SP.PUBLISHED_TARGET_LEVEL_STATUS
    check('shared_pass names the published level as not the partitioned one',
          s.startswith('NOT_THE_PARTITIONED_LEVEL'))
    check('it names the two files a repair needs',
          'football_engine' in s and 'run_forecast' in s)
    check('it states the containment that DOES hold, not only the breach',
          'holds in every one of those draws' in s)


def main():
    for fn in (test_a_named_receivers_exceed_the_published_team_target_level,
               test_b_containment_holds_against_the_level_the_game_consumed,
               test_c_the_partitioned_level_and_its_pools_are_absent_from_every_board,
               test_d_composition_closes_both_halves_by_construction,
               test_e_the_published_level_is_the_level_that_was_partitioned,
               test_f_the_composition_neither_clips_nor_renormalises,
               test_g_the_closure_fence_rejects_a_seeded_breach,
               test_h_the_fence_names_which_side_moved_on_the_sealed_board,
               test_i_the_c3_identity_holds_per_draw_across_the_sealed_frame,
               test_j_receiving_side_per_player_coherence,
               test_k_passer_line_incoherence_is_confined_to_pre_r9_boards,
               test_l_the_module_states_the_publication_defect_by_name):
        print(fn.__name__)
        fn()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
