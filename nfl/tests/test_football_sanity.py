#!/usr/bin/env python3.12
"""Every contradiction the football-sanity gate refuses is forced in BOTH directions: a clean
artifact passes, and each named contradiction, introduced alone, is refused by its own name. The
real 2026 W4 artifact is checked last, so the gate is proven on the thing it will guard.
"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import football_sanity as FS  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _row(name, team, pos, **kw):
    base = {'name': name, 'team': team, 'position': pos, 'projection_state': 'PROJECTED',
            'dk_points': 10.0, 'role_band': 'PRIMARY', 'askable_ceiling': 'ALPHA',
            'is_predicted_starter': False, 'appearance_adjustment': {'applied': False}}
    base.update(kw)
    return base


def _clean():
    rows = {
        'q1': _row('QB One', 'AAA', 'QB', pass_attempts=30.0, carries=3.0, targets=0.0,
                   is_predicted_starter=True, role_band='ALPHA',
                   appearance_adjustment={'applied': False, 'depth_rank': 1,
                                          'reason': 'DEPTH_RANK_1_IS_THE_STARTER'}),
        'q2': _row('QB Two', 'AAA', 'QB', pass_attempts=0.5, carries=0.1, targets=0.0, dk_points=0.3,
                   role_band='SECONDARY', askable_ceiling='SECONDARY',
                   appearance_adjustment={'applied': True, 'depth_rank': 2, 'reason': 'DEPTH_RANK_2'}),
        'r1': _row('Back One', 'AAA', 'RB', carries=15.0, targets=4.0, pass_attempts=0.0),
        'w1': _row('Wide One', 'AAA', 'WR', targets=9.0, carries=0.4, pass_attempts=0.0),
        't1': _row('Tight One', 'AAA', 'TE', targets=5.0, carries=0.0, pass_attempts=0.0),
        'k1': _row('Kick One', 'AAA', 'K', projection_state='PROJECTED_KICKER', dk_points=7.0),
        'd1': _row('Defence', 'AAA', 'DST', projection_state='PROJECTED_DST', dk_points=6.0),
        'q3': _row('QB Three', 'BBB', 'QB', pass_attempts=28.0, carries=2.0, targets=0.0,
                   is_predicted_starter=True, role_band='ALPHA',
                   appearance_adjustment={'applied': False, 'depth_rank': 1}),
        'r2': _row('Back Two', 'BBB', 'RB', carries=20.0, targets=3.0, pass_attempts=0.0),
        'w2': _row('Wide Two', 'BBB', 'WR', targets=12.0, carries=0.0, pass_attempts=0.0),
        'k2': _row('Kick Two', 'BBB', 'K', projection_state='PROJECTED_KICKER', dk_points=6.0),
        'd2': _row('Defence Two', 'BBB', 'DST', projection_state='PROJECTED_DST', dk_points=5.0),
        'x1': {'name': 'Out Guy', 'team': 'AAA', 'position': 'WR', 'dk_points': None,
               'projection_state': 'NOT_PLAYING_REPORTED_INACTIVE'},
    }
    tv = {'AAA': {'proj_pass_attempts': 30.5, 'proj_rush_attempts': 18.5, 'proj_targets': 18.0},
          'BBB': {'proj_pass_attempts': 28.0, 'proj_rush_attempts': 22.0, 'proj_targets': 15.0}}
    return {'rows': rows, 'team_volume': tv}


@check('a clean two-club artifact PASSES')
def _clean_passes():
    o = FS.assess(_clean(), absent={'Out Guy'})
    assert o.state.name == 'PASS', (o.code, o.evidence.get('problems'))
    return f"{o.code}: {o.detail}"


def _refuses(mutate, code):
    a = _clean(); mutate(a)
    o = FS.assess(a, absent={'Out Guy'})
    assert o.state.name == 'FAIL' and o.code == FS.FAIL_CODE, (o.state.name, o.code)
    probs = o.evidence['problems']
    assert code in probs, (code, sorted(probs))
    return f"{code}: {probs[code][0][:110]}"


@check('confirmed starter + backup appearance penalty -> STARTER_CARRIES_APPEARANCE_PENALTY')
def _starter_penalised():
    def m(a): a['rows']['q1']['appearance_adjustment'] = {
        'applied': True, 'depth_rank': 1, 'reason': 'NOT_PREDICTED_STARTER'}
    return _refuses(m, FS.STARTER_PENALISED)


@check('rank-1 QB + NOT_PREDICTED_STARTER -> RANK1_QB_NOT_PREDICTED_STARTER (the W4 defect)')
def _rank1_not_starter():
    def m(a): a['rows']['q1']['appearance_adjustment'] = {
        'applied': True, 'depth_rank': 1, 'reason': 'NOT_PREDICTED_STARTER'}
    return _refuses(m, FS.RANK1_NOT_STARTER)


@check('club pass attempts not reconciling with QB allocation -> CLUB_PASS_ATTEMPTS_NOT_RECONCILED')
def _pass_unreconciled():
    def m(a): a['rows']['q1']['pass_attempts'] = 24.0
    return _refuses(m, FS.PASS_ATT_UNRECONCILED)


@check('club carries not reconciling -> CLUB_CARRIES_NOT_RECONCILED')
def _carries_unreconciled():
    def m(a): a['team_volume']['BBB']['proj_rush_attempts'] = 30.0
    return _refuses(m, FS.CARRIES_UNRECONCILED)


@check('club targets not reconciling -> CLUB_TARGETS_NOT_RECONCILED')
def _targets_unreconciled():
    def m(a): a['rows']['w2']['targets'] = 2.0
    return _refuses(m, FS.TARGETS_UNRECONCILED)


@check('inactive player carrying positive opportunity -> INACTIVE_PLAYER_HAS_OPPORTUNITY')
def _inactive_opportunity():
    def m(a):
        a['rows']['x1'].update({'dk_points': 4.0, 'targets': 3.0, 'projection_state': 'PROJECTED'})
        a['team_volume']['AAA']['proj_targets'] = 21.0
    return _refuses(m, FS.INACTIVE_OPPORTUNITY)


@check('role above declared ceiling without reason -> ROLE_ABOVE_CEILING_WITHOUT_REASON')
def _above_ceiling():
    def m(a): a['rows']['t1'].update({'role_band': 'ALPHA', 'askable_ceiling': 'ROTATIONAL'})
    return _refuses(m, FS.ABOVE_CEILING)


@check('role above ceiling WITH a recorded cap_reason is allowed')
def _above_ceiling_with_reason():
    a = _clean()
    a['rows']['t1'].update({'role_band': 'ALPHA', 'askable_ceiling': 'ROTATIONAL',
                            'cap_reason': 'observed usage capped; see REPLACEMENT_EXPIRES'})
    o = FS.assess(a, absent={'Out Guy'})
    assert o.state.name == 'PASS', o.evidence.get('problems')
    return 'a reason is recorded, so no contradiction'


@check('a projected row at exactly 0.0 -> ZERO_WITHOUT_NAMED_STATE (the kicker defect)')
def _zero_unnamed():
    def m(a): a['rows']['k1']['dk_points'] = 0.0
    return _refuses(m, FS.ZERO_UNNAMED)


@check('missing input on a projected row -> MISSING_INPUT_READ_AS_ZERO')
def _missing_as_zero():
    def m(a):
        a['rows']['w1']['targets'] = None
        a['team_volume']['AAA']['proj_targets'] = 9.0
    return _refuses(m, FS.MISSING_AS_ZERO)


@check('a club without a projected kicker or DST -> KICKER_OR_DST_MISSING')
def _unit_missing():
    def m(a): del a['rows']['d2']
    return _refuses(m, FS.UNIT_MISSING)


@check('every contradiction is reported, not just the first')
def _reports_all():
    a = _clean()
    a['rows']['k1']['dk_points'] = 0.0
    del a['rows']['d2']
    o = FS.assess(a, absent={'Out Guy'})
    assert o.state.name == 'FAIL'
    assert {FS.ZERO_UNNAMED, FS.UNIT_MISSING} <= set(o.evidence['problems']), o.evidence['problems']
    return f"classes refused together: {sorted(o.evidence['problems'])}"


@check('THE REAL 2026 W4 PIT@CLE ARTIFACT: delivered copy refused on exactly the quarterback-target '
       'defect found after delivery; the post-fix rebuild PASSES')
def _real_artifact():
    # HISTORY, NOT A LOOSENING. This check read "PASSES after the starter repair" until 2026-10-02,
    # when the centred-arm reconciliation exposed that Deshaun Watson carried 5.04 projected targets
    # (DEFECT-QBTGT). The delivered artifact is preserved unchanged as the record of what was
    # delivered, so the gate now refuses it on that one class and nothing else; the rebuild with
    # the repaired allocator (SHOWDOWN_TONIGHT_PROJ_QBTGT_FIXED.json, post-game, descriptive) passes.
    inact = json.loads((_REPO / 'nfl/dfs/salaries/raw/OFFICIAL_INACTIVES_PIT_CLE_2026W4.json').read_text())
    delivered = json.loads((_REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ.json').read_text())
    o = FS.assess(delivered, absent=set(inact), clubs=('PIT', 'CLE'))
    probs = (o.evidence or {}).get('problems') or {}
    assert o.state.name == 'FAIL' and list(probs) == [FS.QB_RECEIVER_VOLUME], (o.code, probs)
    assert probs[FS.QB_RECEIVER_VOLUME] == ['Deshaun Watson (CLE QB): 5.04 projected targets above the '
                                            '1.0 ceiling, no reason'], probs
    fixed = json.loads((_REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ_QBTGT_FIXED.json').read_text())
    o2 = FS.assess(fixed, absent=set(inact), clubs=('PIT', 'CLE'))
    assert o2.state.name == 'PASS', (o2.code, o2.evidence.get('problems'))
    return (f"delivered: {o.code} on {list(probs)}; rebuilt: {o2.detail}; "
            f"reconcile_tol={o2.evidence['reconcile_tol']}")


@check('THE PRE-REPAIR BASELINE-A ARTIFACT IS REFUSED -- the gate would have caught W4')
def _baseline_a_refused():
    import subprocess
    raw = subprocess.run(['git', 'show', '6e6c82dd:nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ.json'],
                         cwd=_REPO, capture_output=True, text=True, check=True).stdout
    art = json.loads(raw)
    inact = json.loads((_REPO / 'nfl/dfs/salaries/raw/OFFICIAL_INACTIVES_PIT_CLE_2026W4.json').read_text())
    o = FS.assess(art, absent=set(inact), clubs=('PIT', 'CLE'))
    assert o.state.name == 'FAIL', o.code
    probs = o.evidence['problems']
    # Both the direct contradiction AND its mechanical consequence must be named: the old
    # artifact capped the starters' pass-attempt claims, so the club total no longer reconciled.
    assert FS.RANK1_NOT_STARTER in probs, sorted(probs)
    # CORRECTED 2026-10-02. This check used to also assert CLUB_PASS_ATTEMPTS_NOT_RECONCILED and
    # explain it as the capped starters' attempts leaving the club total. Measured, that was false:
    # the residual (CLE 0.247, PIT 0.515 attempts) is the ordinary trick-play mass on receivers'
    # rows, present in every artifact, which a quarterbacks-only sum under a 0.1% tolerance reads
    # as unreconciled. The gate now sums the pool the allocator keeps and bounds that mass. The
    # REAL consequence of capping Watson's and Rodgers' claims is visible on the quarterback rows
    # themselves: the backups absorbed the attempts (Shedeur Sanders 4.00, Mason Rudolph 4.26).
    assert FS.PASS_ATT_UNRECONCILED not in probs, sorted(probs)
    assert FS.NON_QB_PASS_ATTEMPTS not in probs, sorted(probs)
    backups = {r['name']: round(r.get('pass_attempts') or 0.0, 2) for r in art['rows'].values()
               if r.get('position') == 'QB' and r['name'] in ('Shedeur Sanders', 'Mason Rudolph')}
    assert backups == {'Shedeur Sanders': 4.0, 'Mason Rudolph': 4.26}, backups
    names = ' '.join(probs[FS.RANK1_NOT_STARTER])
    assert 'Deshaun Watson' in names and 'Aaron Rodgers' in names, names
    return f"refused {sorted(probs)}; {probs[FS.RANK1_NOT_STARTER][0][:90]}"



@check('DRAWS CONSISTENCY: absent sidecar is named, present sidecar yields per-club ratios')
def _draws_measure():
    import tempfile, shutil, numpy as np
    art = _clean()
    assert FS.measure_draws(art, {})['state'] == FS.DRAWS_SIDECAR_ABSENT
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        fields = ['pass_att','pass_yards','pass_td','carries','rush_yards','rush_td','targets','receptions','rec_yards','rec_td']
        q = np.zeros((4, 10)); q[:, 0] = 30.0; q[:, 3] = 3.0
        r = np.zeros((4, 10)); r[:, 3] = 15.0; r[:, 6] = 4.0
        w = np.zeros((4, 10)); w[:, 6] = 9.0; w[:, 3] = 0.4
        np.savez_compressed(tmp / 'S.npz', **{'QB One|AAA': q, 'Back One|AAA': r, 'Wide One|AAA': w})
        dd = {'stat_draws_sidecar': {'path': 'S.npz', 'STAT_FIELDS': fields}}
        m = FS.measure_draws(art, dd, repo_root=tmp)
        assert m['state'] == FS.DRAWS_MEASURED, m
        aaa = m['per_club']['AAA']
        assert abs(aaa['pass_attempts']['ratio_minus_one'] - round(30.0 / 30.5 - 1, 4)) < 1e-6, aaa
        assert abs(aaa['carries']['simulated_mean'] - 18.4) < 1e-9, aaa
        assert m['worst_abs_ratio_minus_one'] is not None
        return f"absent -> {FS.DRAWS_SIDECAR_ABSENT}; present -> AAA pass {aaa['pass_attempts']}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

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
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
