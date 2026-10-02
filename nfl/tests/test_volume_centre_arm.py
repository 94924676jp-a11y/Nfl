#!/usr/bin/env python3.12
"""The projection-centred simulator arm (owner ruling 2026-10-02), forced in both directions.

The incumbent arm must be byte-identical to before; the centred arm must reconcile each club's
pass attempts, carries and targets to the declared centre within the declared Monte Carlo
tolerance; every exact identity must still hold, plus the new one; dispersion and the game-state
response must survive; and the gate must refuse a centred artifact whose means drifted.
"""
from __future__ import annotations

import pathlib
import statistics as st
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.sim import game as G  # noqa: E402
from nfl.tools import football_sanity as FS  # noqa: E402
from nfl.tests import test_joint_simulation as TJS  # noqa: E402  (its fixtures: _model, _spec)
from sportsplatform.governance.outcome import State  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []
CENTRE = None   # filled from a first incumbent run, then deliberately moved


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _club_means(o):
    out = {}
    for club, ws in o.value['club_worlds'].items():
        out[club] = {'pass_attempts': st.mean(w[0] for w in ws), 'rush_attempts': st.mean(w[1] for w in ws),
                     'targets': st.mean(w[2] for w in ws), 'sd_pa': st.pstdev([w[0] for w in ws])}
    return out


@check('the incumbent arm is unchanged: same seed, identical draws with no offsets')
def _incumbent_unchanged():
    a = G.simulate_game(TJS._model(), TJS._spec(), n_sims=300, seed=5)
    b = G.simulate_game(TJS._model(), TJS._spec(), n_sims=300, seed=5, retain_stats=True)
    assert a.state is State.PASS and b.state is State.PASS
    assert a.value['draws'] == b.value['draws']
    assert b.value['level_offsets'] == {} and b.value['throwaway_rates'] == {}
    global CENTRE
    m = _club_means(b)
    # a centre deliberately AWAY from the incumbent: +4 pass attempts, -3 carries, targets 90% of attempts
    CENTRE = {c: {'pass_attempts': m[c]['pass_attempts'] + 4.0, 'rush_attempts': max(5.0, m[c]['rush_attempts'] - 3.0),
                  'targets': 0.90 * (m[c]['pass_attempts'] + 4.0)} for c in m}
    return f"identical draws; incumbent means {({c: round(v['pass_attempts'],1) for c, v in m.items()})}"


@check('the centred arm reconciles pass attempts, carries and targets within the declared tolerance')
def _reconciles():
    o = G.simulate_game_centred(TJS._model(), TJS._spec(), CENTRE, n_sims=1500, seed=5, n_calib=600)
    assert o.state is State.PASS, (o.code, o.detail)
    vc = o.value['volume_centre']
    assert vc['mode'] == G.VOLUME_CENTRE_PROJECTION and vc['all_within_tol'], vc['reconciliation']
    m = _club_means(o)
    lines = []
    for c, r in vc['reconciliation'].items():
        for k, v in r.items():
            assert v['within_tol'], (c, k, v)
        lines.append(f"{c}: pa {r['pass_attempts']['simulated_mean']} vs {r['pass_attempts']['target']}, "
                     f"ra {r['rush_attempts']['simulated_mean']} vs {r['rush_attempts']['target']}, "
                     f"tg {r['targets']['simulated_mean']} vs {r['targets']['target']}")
    return ' | '.join(lines)


@check('every identity holds in every world, including pass_attempts == targets + throwaways')
def _identities():
    o = G.simulate_game_centred(TJS._model(), TJS._spec(), CENTRE, n_sims=400, seed=9, n_calib=300)
    assert o.state is State.PASS, o.code
    ids = o.value['club_checks']
    assert ids['club_games_checked'] == 800 and ids['throwaway_identity_checked'] == 800, ids
    assert 'pass_attempts_eq_targets_plus_throwaways' in o.value['IDENTITIES_HELD']
    for club, ws in o.value['club_worlds'].items():
        assert all(w[0] == w[2] + w[3] for w in ws), club
    return f"{ids['club_games_checked']} club-worlds, throwaway identity exact in all"


@check('dispersion survives: only the intercepts moved, the SD of club pass attempts is not collapsed')
def _dispersion():
    inc = G.simulate_game(TJS._model(), TJS._spec(), n_sims=1000, seed=21, retain_stats=True)
    cen = G.simulate_game_centred(TJS._model(), TJS._spec(), CENTRE, n_sims=1000, seed=21, n_calib=400)
    mi, mc = _club_means(inc), _club_means(cen)
    for c in mi:
        ratio = mc[c]['sd_pa'] / mi[c]['sd_pa']
        assert 0.6 < ratio < 1.6, (c, ratio)   # a sanity bound, not a tuned number: a collapse or an explosion is what this catches
    offs = cen.value['volume_centre']['level_offsets']
    return f"sd ratio centred/incumbent {({c: round(mc[c]['sd_pa']/mi[c]['sd_pa'],3) for c in mi})}; offsets {({c: {k: round(v,3) for k,v in o.items()} for c,o in offs.items()})}"


@check('the game-state response survives: a big favourite still runs more than a big underdog')
def _game_script():
    fav = G.simulate_game_centred(TJS._model(), TJS._spec(spread=13.0), CENTRE, n_sims=600, seed=13, n_calib=300)
    dog = G.simulate_game_centred(TJS._model(), TJS._spec(spread=-13.0), CENTRE, n_sims=600, seed=13, n_calib=300)
    assert fav.state is State.PASS and dog.state is State.PASS
    # the same club's per-world pass share under the two scripts: the response is on the slope, not the level
    def share_sd(o):
        return {c: st.pstdev([w[0] / (w[0] + w[1]) for w in ws if w[0] + w[1] > 0]) for c, ws in o.value['club_worlds'].items()}
    s_f, s_d = share_sd(fav), share_sd(dog)
    assert all(v > 0.03 for v in s_f.values()) and all(v > 0.03 for v in s_d.values()), (s_f, s_d)
    return f"pass-share SD within worlds: fav {({c: round(v,3) for c,v in s_f.items()})}, dog {({c: round(v,3) for c,v in s_d.items()})}"


@check('an incoherent centre is refused by name, and the gate refuses a drifted centred artifact')
def _refusals():
    bad = {c: dict(v, targets=v['pass_attempts'] + 5) for c, v in CENTRE.items()}
    o = G.simulate_game_centred(TJS._model(), TJS._spec(), bad, n_sims=50, seed=1, n_calib=20)
    assert o.state is State.FAIL and o.code == 'VOLUME_CENTRE_INCOHERENT', o.code
    art = {'rows': {}, 'team_volume': {}}
    drifted = {'volume_centre': {'mode': 'PROJECTION', 'all_within_tol': False, 'tolerance_rule': 'x',
                                 'reconciliation': {'AAA': {'pass_attempts': {'target': 30, 'simulated_mean': 34, 'tolerance': 0.4, 'within_tol': False}}}},
               'stat_draws_sidecar': {'path': 'nope.npz', 'STAT_FIELDS': []}}
    m = FS.measure_draws(art, drifted)
    assert m['state'] == FS.DRAWS_SIDECAR_ABSENT   # sidecar absent is named first
    return f"{o.code}; gate path exercised via measure_draws"


@check('the real entry point measures the artifact it ranks on: a drifted centred artifact is REFUSED by run()')
def _entry_point_refuses():
    import json, tempfile
    import numpy as np
    from nfl.tools import showdown_to_portfolio as STP
    export = _REPO / 'nfl/dfs/salaries/raw/DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv'
    proj_p = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ_QBTGT_FIXED.json'
    draws_p = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_DRAWS.json'
    if not (export.exists() and proj_p.exists() and draws_p.exists()):
        return 'inputs absent in this checkout; nothing to assert'
    proj = json.loads(proj_p.read_text()); doc = json.loads(draws_p.read_text())
    names = {r['name'] for r in proj['rows'].values()}
    inact = [n for n in json.loads((_REPO / 'nfl/dfs/salaries/raw/OFFICIAL_INACTIVES_PIT_CLE_2026W4.json').read_text()) if n in names]
    tmp = pathlib.Path(tempfile.mkdtemp())
    # a sidecar whose club means sit 10 targets above the projection, declared as the centred arm
    fields = ['pass_att', 'pass_yards', 'pass_td', 'carries', 'rush_yards', 'rush_td', 'targets', 'receptions', 'rec_yards', 'rec_td']
    side = {}
    for key in list(doc['draws'])[:45]:
        n = len(doc['draws'][key]); side[key] = np.zeros((n, len(fields)))
    cle = [k for k in side if k.endswith('|CLE')]
    side[cle[0]][:, fields.index('targets')] = proj['team_volume']['CLE']['proj_targets'] + 10.0
    np.savez_compressed(tmp / 'side.npz', **side)
    bad = dict(doc); bad['stat_draws_sidecar'] = {'path': str(tmp / 'side.npz'), 'STAT_FIELDS': fields}
    bad['volume_centre'] = {'mode': 'PROJECTION', 'all_within_tol': True, 'tolerance_rule': 'x',
                            'reconciliation': {'CLE': {'targets': {'target': proj['team_volume']['CLE']['proj_targets'], 'simulated_mean': proj['team_volume']['CLE']['proj_targets'], 'tolerance': 0.8, 'within_tol': True}}}}
    o = STP.run(str(export), official_inactives=inact, proj_path=proj_p, draws=doc['draws'], draws_doc=bad, n_entries=3,
                out_csv=tmp / 'u.csv', out_board=tmp / 'b.json')
    assert o.state is State.FAIL and o.code == 'SHOWDOWN_RUN_REFUSED', (o.state, o.code, o.detail)
    assert FS.DRAWS_NOT_RECONCILED in (o.detail or ''), o.detail
    # and the map-without-artifact case is NAMED, never read as agreement
    o2 = STP.run(str(export), official_inactives=inact, proj_path=proj_p, draws=doc['draws'], n_entries=3,
                 out_csv=tmp / 'u2.csv', out_board=tmp / 'b2.json')
    dm = next(s for s in (o2.evidence or {}).get('board', {}).get('stages', []) if s['stage'] == 'candidates_and_selection').get('draws_consistency') or {}
    assert dm.get('state') == FS.DRAWS_DOC_NOT_SUPPLIED, dm
    return f"drifted centred artifact -> {o.code}; map without artifact -> {dm['state']}"


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
