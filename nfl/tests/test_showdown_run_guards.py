"""Showdown run guards on REAL TB@DAL states: starter integrity and the execution receipt.

The independent P0 pack exercises these guards on synthetic fixtures. This file exercises them on the actual slate
states the production path built on 2026-10-08, including the one contaminated by the concurrent run.
"""
import copy
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import showdown_run_guards as G  # noqa: E402

PASSED = FAILED = 0
R = _REPO / 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5'
D = _REPO / 'nfl/dfs/salaries/showdown_tb_dal'
ABS = tuple(AV.ABSENT_STATUSES) + ('OUT',)


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print('  ok  ', msg)
    else:
        FAILED += 1
        print('  FAIL', msg)


def _scenario(cfg_name, scen):
    c = json.loads((R / cfg_name).read_text())
    des = json.loads((_REPO / c['designations']).read_text())
    st = json.loads((_REPO / c['confirmed_starters']).read_text())
    exp = G.expected_state(c['tag'], scen, des, st,
                           G.identity_from_depth_chart(_REPO / c['depth_chart'], set(st) | set(des)))
    return c, des, st, exp


def _bound(state, exp, st, tier):
    s = copy.deepcopy(state)
    return G.bind_scenario(s, exp['scenario_identity'], G.starters_digest(st), tier)


def _by_name(state, n):
    return next(p for p in state['players'].values() if p['name'] == n)


def test_real_states():
    for cfg_name, scen_dir, scen in (('SLATE_PRECOMPUTE_TBQB_DANIELS.json', 'PRECOMPUTE_TBQB_DANIELS_R3', 'D'),
                                     ('SLATE_PRECOMPUTE_TBQB_MAYFIELD.json', 'PRECOMPUTE_TBQB_MAYFIELD_R2', 'M')):
        p = D / scen_dir / 'SHOWDOWN_TB_DAL_2026W5_STATE.json'
        if not p.is_file():
            check(False, f'{scen_dir} state present')
            continue
        c, des, st, exp = _scenario(cfg_name, scen)
        state = json.loads(p.read_text())
        dig = G.starters_digest(st)
        good = _bound(state, exp, st, c['starter_tier'])
        check(G.verify_starter_state(good, exp, ABS, dig) == [], f'{scen_dir}: the real bound state passes')
        check(any(b.startswith('SCENARIO') for b in G.verify_starter_state(state, exp, ABS, dig)),
              f'{scen_dir}: the same state unbound (no scenario identity) refuses')
        qb = next(n for n, club in st.items() if club == 'TB')
        bad = copy.deepcopy(good)
        _by_name(bad, qb)['gsis_id'] = '00-0000000'
        check(any(b.startswith('STARTER_MISSING') or b.startswith('IDENTITY') for b in
                  G.verify_starter_state(bad, exp, ABS, dig)), f'{scen_dir}: wrong canonical id for {qb} refuses')
        bad = copy.deepcopy(good)
        _by_name(bad, qb)['team'] = 'DAL'
        check(any(b.startswith('TEAM') for b in G.verify_starter_state(bad, exp, ABS, dig)),
              f'{scen_dir}: {qb} on the wrong team refuses')
        bad = copy.deepcopy(good)
        _by_name(bad, qb)['predicted_lineup_context']['in_predicted_starting_group'] = False
        check(any(b.startswith('STARTING_FLAG') for b in G.verify_starter_state(bad, exp, ABS, dig)),
              f'{scen_dir}: {qb} without the starting flag refuses')
        bad = copy.deepcopy(good)
        _by_name(bad, qb)['predicted_lineup_context'].pop('evidence')
        check(any(b.startswith('STARTER_EVIDENCE') for b in G.verify_starter_state(bad, exp, ABS, dig)),
              f'{scen_dir}: {qb} without starter evidence refuses')
        check(any(b.startswith('STARTER_EVIDENCE_FOREIGN') for b in
                  G.verify_starter_state(good, exp, ABS, G.starters_digest({'Somebody Else': 'TB'}))),
              f'{scen_dir}: starter evidence bound to another scenario\'s starters refuses')
        bad = copy.deepcopy(good)
        del bad['players'][next(k for k, v in bad['players'].items() if v['name'] == qb)]
        check(any(b.startswith('STARTER_MISSING') or b.startswith('IDENTITY') for b in
                  G.verify_starter_state(bad, exp, ABS, dig)), f'{scen_dir}: {qb} missing from the state refuses')
        if scen == 'D':
            bad = copy.deepcopy(good)
            _by_name(bad, 'Baker Mayfield')['current_availability']['status'] = 'UNKNOWN_ACTIVE_STATE'
            check(any(b.startswith('OUT_OVERWRITTEN') for b in G.verify_starter_state(bad, exp, ABS, dig)),
                  f'{scen_dir}: Mayfield OUT overwritten by an active status refuses')
            # a legitimate backup: Mayfield OUT, other TB QBs active without a starting flag -> still passes
            check(all(not b.startswith('STARTER_SET') for b in G.verify_starter_state(good, exp, ABS, dig)),
                  f'{scen_dir}: active backups with no starting flag are legitimate')


def test_contaminated_state_refuses():
    p = D / 'PRECOMPUTE_TBQB_DANIELS_R2' / 'SHOWDOWN_TB_DAL_2026W5_STATE.json'
    if not p.is_file():
        check(False, 'contaminated Daniels R2 state present')
        return
    c, des, st, exp = _scenario('SLATE_PRECOMPUTE_TBQB_DANIELS.json', 'D')
    state = _bound(json.loads(p.read_text()), exp, st, c['starter_tier'])
    bad = G.verify_starter_state(state, exp, ABS, G.starters_digest(st))
    check(any(b.startswith('STARTING_FLAG') or b.startswith('STARTER_SET') for b in bad)
          and any(b.startswith('DESIGNATION') or b.startswith('OUT') for b in bad),
          f'the 2026-10-08 contaminated Daniels state refuses even after binding: {bad[:4]}')


def test_receipt():
    td = pathlib.Path(tempfile.mkdtemp())
    sd = td / 'S'
    sd.mkdir()
    b = G.football_bundle(sd, 'X_Y_2026W1')
    for k, p in b.items():
        p.write_text(k)
    up = sd / 'UP.csv'
    up.write_text('u')
    head = G.git_head(_REPO)
    run = {'run_id': 'run:a', 'commit': head, 'repo': _REPO, 'freeze_seal': 's', 'scenario_identity': 'i'}
    G.write_receipt(sd, run_id='run:a', commit=head, scenario='S', scenario_identity='i', freeze_seal='s', env={},
                    tag='X_Y_2026W1', publication=[up])
    rep = td / 'REP'
    import shutil
    shutil.copytree(sd, rep)
    check(G.verify_receipt(sd, run, 'X_Y_2026W1', 'S', replay_rc=0, replay_dir=rep) == [], 'a complete receipt passes')
    check(any(x.startswith('REPLAY_EXIT_NONZERO') for x in
              G.verify_receipt(sd, run, 'X_Y_2026W1', 'S', replay_rc=17, replay_dir=rep)), 'replay rc 17 refuses')
    check(any('RUN_ID' in x for x in G.verify_receipt(sd, {**run, 'run_id': 'run:b'}, 'X_Y_2026W1', 'S', replay_rc=0)),
          'a receipt from another run refuses')
    check(any('COMMIT' in x for x in G.verify_receipt(sd, {**run, 'commit': 'f' * 40}, 'X_Y_2026W1', 'S', replay_rc=0)),
          'a receipt from another commit refuses')
    (rep / b['STATE.json'].name).write_text('other')
    check(any(x.startswith('REPLAY_FOOTBALL_STATE_DIFFERS') for x in
              G.verify_receipt(sd, run, 'X_Y_2026W1', 'S', replay_rc=0, replay_dir=rep)),
          'a replay with a different football state refuses')
    b['WORLDS.npz'].unlink()
    check(any(x.startswith('ARTIFACT_MISSING') for x in G.verify_receipt(sd, run, 'X_Y_2026W1', 'S', replay_rc=0)),
          'a missing world bundle refuses')
    (sd / G.RECEIPT).unlink()
    check(any(x.startswith('RUN_RECEIPT_ABSENT') for x in G.verify_receipt(sd, run, 'X_Y_2026W1', 'S', replay_rc=0)),
          'a missing receipt refuses')
    check(G.verify_receipt(sd, None, 'X_Y_2026W1', 'S', replay_rc=0)[0].startswith('RUN_CONTEXT_ABSENT'),
          'no run context refuses')


def test_football_model_completeness():
    panel = {'teams': {'TB': {'2026': {'1': {'pass_attempts': 40}, '2': {'pass_attempts': 40}, '3': {'pass_attempts': 40}},
                              '2025': {str(w): {'pass_attempts': 35} for w in range(1, 18)}}},
             'players': {'Q1': {'2026': {'1': {'pass_attempts': 40, 'team': 'TB'}, '2': {'pass_attempts': 40, 'team': 'TB'}},
                                '2025': {str(w): {'pass_attempts': 35, 'team': 'TB'} for w in range(1, 18)}},
                         'Q2': {'2026': {'3': {'pass_attempts': 40, 'team': 'TB'}}}}}
    a = G.qb_environment_share(panel, 'TB', 'Q1', 2026, 4, 4.0)
    b = G.qb_environment_share(panel, 'TB', 'Q2', 2026, 4, 4.0)
    check(abs(a['blended_share'] - (3 * (80 / 120) + 4 * 1.0) / 7) < 1e-12, f"incumbent blended share {a['blended_share']:.4f}")
    check(abs(b['blended_share'] - (3 * (40 / 120)) / 7) < 1e-12, f"backup blended share {b['blended_share']:.4f}")
    st = lambda qb: {'season': 2026, 'week': 4, 'players': {'x': {'name': qb, 'team': 'TB', 'position': 'QB', 'gsis_id': qb,  # noqa: E731
                                                                  'predicted_lineup_context': {'in_predicted_starting_group': True}}}}
    check(G.football_model_status(st('Q1'), panel, 4.0)['status'] == 'COMPLETE_FOR_STARTERS',
          'a starter whose club environment is predominantly his is COMPLETE')
    check(G.football_model_status(st('Q2'), panel, 4.0)['status'] == 'INCOMPLETE_QB_ENVIRONMENT',
          'a starter whose club environment is another QB\'s is INCOMPLETE (QB change not modelled)')
    from nfl.tools import player_prior as PP, proj_v1 as PV
    real = PP.load_panel().value
    for scen, want in (('PRECOMPUTE_TBQB_DANIELS_R7', 'INCOMPLETE_QB_ENVIRONMENT'), ('PRECOMPUTE_TBQB_MAYFIELD_R4', 'COMPLETE_FOR_STARTERS')):
        p = D / scen / 'SHOWDOWN_TB_DAL_2026W5_STATE.json'
        if p.is_file():
            got = G.football_model_status(json.loads(p.read_text()), real, PV.TEAM_VOLUME_PRIOR_GAMES)['status']
            check(got == want, f'{scen}: {got}')


if __name__ == '__main__':
    for t in (test_real_states, test_contaminated_state_refuses, test_receipt, test_football_model_completeness):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
