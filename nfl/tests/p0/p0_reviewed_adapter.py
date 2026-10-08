"""Reviewed boundary adapter for the independent NFL P0 regression fixture pack (2026-10-08).

API (pack README): evaluate(request, scratch, source) -> observation. It changes HOW a fixture reaches the real
consumer, never the fixed expectation or the oracle (`acceptance_oracle.check`), and it never computes a decision
itself: every `decision` below is read off the REAL production function's return value.

WHY IT EXISTS. The repaired finalizer and starter matcher bind evidence the legacy calling convention does not supply
(a current run context; an expectation built from an independent identity source). Called the legacy way they refuse
-- correctly -- so the legacy adapter would report the valid controls as failures. This adapter supplies that context
from each fixture's own declared facts, and nothing else.

GROUPS
  ready  REAL `showdown_next_slate.final_verify` (imported from the target checkout), with a run context. The
         fixture's synthetic artifacts are mapped onto the production artifact names the receipt binds:
           FOOTBALL_STATE.json -> SHOWDOWN_<TAG>_STATE.json (+ PROJ, DRAWS, WORLDS: the football bundle)
           WORLD_BUNDLE.json   -> SHOWDOWN_<TAG>_WORLDS.npz
           SUITE_CERTIFICATE / COMPLETION -> RUN_RECEIPT.json, written by the REAL `showdown_run_guards.write_receipt`
         Variant -> condition (the fixture's own definition, legacy_adapter.ready):
           valid                          complete receipt for this run and commit; replay exits 0, copies upload
           nonzero_matching_upload        replay copies the matching upload and exits 17
           stale_certificate              receipt commit is 'STALE_HEAD'
           missing_completion             receipt deleted
           partial_world_bundle           WORLDS.npz deleted after the receipt was written
           matching_upload_different_state  replay copies the matching upload and rewrites the football state
           missing_board / missing_replay_upload  as in the legacy fixture
         Mocked, exactly as in the legacy adapter: `_run` (a real isolated child process, not an NFL replay), `_now`.
  qb     REAL `showdown_next_slate.scenario_state_matches`, given the fixture's declared expectation mapped field for
         field onto the production expectation (scenario_digest -> scenario_identity; starting_qbs, required_ids,
         ordinary_out, designations unchanged). The fixture's starter evidence digest is a synthetic token, not derived
         from its starters file, so the evidence-binding comparison is disabled here (starters_digest='') and is
         tested instead on the real TB@DAL states (nfl/tests/test_showdown_run_guards.py).
  other  delegated unchanged to the pack's legacy adapter.

A target whose finalizer has no `run` parameter is the pre-repair shape: reported UNVERIFIED, not PASS.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib
import inspect
import json
import pathlib
import shutil
import subprocess
import sys
import types

import legacy_adapter as LA                       # the pack's own adapter (the pack dir is on sys.path)

TAG = 'TB_DAL_2026W5'
PRE = 'SHOWDOWN_TEST'


def _import_target(source):
    src = str(pathlib.Path(source).resolve())
    if src not in sys.path:
        sys.path.insert(0, src)
    for m in [m for m in sys.modules if m == 'nfl' or m.startswith('nfl.') or m.startswith('sportsplatform')]:
        del sys.modules[m]
    NS = importlib.import_module('nfl.tools.showdown_next_slate')
    if not pathlib.Path(NS.__file__).resolve().is_relative_to(pathlib.Path(src)):
        raise LA.SourceShapeUnavailable(f'imported {NS.__file__}, not the target checkout')
    return NS


def _ready(req, scratch, source):
    NS = _import_target(source)
    if 'run' not in inspect.signature(NS.final_verify).parameters:
        raise LA.SourceShapeUnavailable('final_verify has no run context parameter (pre-repair shape)')
    G = importlib.import_module('nfl.tools.showdown_run_guards')
    variant = req['variant']
    root = pathlib.Path(scratch)
    sd = root / 'SCENARIO'
    sd.mkdir()
    bundle = G.football_bundle(sd, TAG)
    bundle['STATE.json'].write_text(json.dumps({'starter': 'fixture:mayfield', 'players': {}}))
    bundle['PROJ.json'].write_text('{"rows":{}}')
    bundle['DRAWS.json'].write_text('{"draws":{}}')
    bundle['WORLDS.npz'].write_bytes(b'fixture-worlds')
    up = sd / f'{PRE}_DK_UPLOAD.csv'
    up.write_text('CPT,FLEX\n101,202\n')
    board = sd / f'{PRE}_FINAL_BOARD.json'
    board.write_text(json.dumps({'VERIFIER_VIOLATIONS': 0, 'UNCLASSIFIED': [], 'BLOCKED': []}))
    commit = G.git_head(source)
    run = {'run_id': 'fixture:run', 'commit': commit, 'repo': pathlib.Path(source), 'code_dirty': [],
           'freeze_seal': 'fixture:seal', 'scenario_identity': 'fixture:scn', 'environment_sha256': None,
           # football-model completeness (owner directive 2026-10-08) is not part of the READY fixtures' contract;
           # supplied as complete so these fixtures test only what they define. It is tested in
           # nfl/tests/test_showdown_run_guards.py on the real TB@DAL states.
           'football_model': {'status': 'COMPLETE_FOR_STARTERS', 'reasons': []},
           # simulation accounting (owner ruling 2026-10-08) is likewise outside the READY fixtures' contract (their
           # worlds are placeholder bytes). Supplied as PASS so these fixtures test only what they define; the
           # accounting status and the release classification are tested in nfl/tests/test_release_classification.py.
           'accounting': {'status': 'PASS', 'violated': {}}}
    G.write_receipt(sd, run_id=run['run_id'], commit='STALE_HEAD' if variant == 'stale_certificate' else commit,
                    scenario='SCENARIO', scenario_identity=run['scenario_identity'], freeze_seal=run['freeze_seal'],
                    env={}, tag=TAG, publication=[up, board])
    if variant == 'missing_completion':
        (sd / G.RECEIPT).unlink()
    if variant == 'partial_world_bundle':
        bundle['WORLDS.npz'].unlink()
    if variant == 'missing_board':
        board.unlink()
    replay_runs = []

    def replay(cmd, env, label):
        rep = root / 'SCENARIO_REPRO'
        child = ("from pathlib import Path; import sys; "
                 "src,dst,v,state=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3],sys.argv[4]; "
                 "(dst/src.name).write_bytes(src.read_bytes()) if v!='missing_replay_upload' else None; "
                 "(dst/state).write_text('{\"starter\":\"fixture:daniels\"}') "
                 "if v=='matching_upload_different_state' else None; "
                 "print('isolated replay fixture child completed output step'); "
                 "raise SystemExit(17 if v=='nonzero_matching_upload' else 0)")
        r = subprocess.run([sys.executable, '-B', '-c', child, str(up), str(rep), variant, bundle['STATE.json'].name],
                           cwd=root, capture_output=True, text=True, timeout=10)
        replay_runs.append({'returncode': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr,
                            'fixture_child_sha256': hashlib.sha256(child.encode()).hexdigest()})
        return r.returncode, r.stdout + r.stderr

    NS._run = replay
    NS._now = lambda: datetime.datetime(2026, 10, 8, tzinfo=datetime.timezone.utc)
    NS.scenario_state_matches = lambda cfg, state, *a, **k: []   # starter state is the qb group's boundary
    cfg = {'scenario': 'SCENARIO', 'tag': TAG, 'export': 'unused.csv', 'kickoff_utc': '2026-10-09T00:00:00+00:00'}
    ledger = []
    got = NS.final_verify(cfg, 'unused.json', {}, {'starters_confirmed': True, 'ready_eligible': True},
                          types.SimpleNamespace(add=lambda *a, **kw: ledger.append({'args': a, **kw})),
                          {'dir': root}, sd, PRE, {}, True, run=run)
    return {'decision': 'REJECT' if got[0] != 'READY' else 'ACCEPT', 'verdict': got, 'ledger': ledger,
            'replay_process_records': replay_runs, 'real_fixture_child_executed': True,
            'consumer': f'{NS.__file__}:final_verify', 'receipt_writer': f'{G.__file__}:write_receipt',
            'mocks': ['_run: real isolated fixture child, not an NFL replay', '_now: prekickoff clock',
                      'scenario_state_matches: neutral here (exercised by the qb group)']}


def _qb(req, scratch, source):
    NS = _import_target(source)
    if 'expected' not in inspect.signature(NS.scenario_state_matches).parameters:
        raise LA.SourceShapeUnavailable('scenario_state_matches takes no expectation (pre-repair shape)')
    f = req['fixture']
    root = pathlib.Path(scratch)
    (root / 'designations.json').write_text(json.dumps(f['designations']))
    (root / 'starters.json').write_text(json.dumps(f['confirmed_starters']))
    e = f['expected_state']
    expected = {'scenario_identity': e['scenario_digest'], 'starting_qbs': e['starting_qbs'],
                'starter_names': f['confirmed_starters'], 'required_ids': e['required_ids'],
                'ordinary_out': e['ordinary_out'], 'designations': f['designations'], 'identity_problems': []}
    AV = importlib.import_module('nfl.tools.availability')
    got = NS.scenario_state_matches({'designations': str(root / 'designations.json'),
                                     'confirmed_starters': str(root / 'starters.json')},
                                    {**f['state'], 'scenario_identity': f['state'].get('scenario_digest')},
                                    expected=expected, absent_statuses=tuple(AV.ABSENT_STATUSES) + ('OUT',),
                                    starters_digest='')
    return {'decision': 'REJECT' if got else 'ACCEPT', 'mismatches': got,
            'consumer': f'{NS.__file__}:scenario_state_matches'}


def evaluate(request, scratch, source):
    g = request['group']
    if g == 'ready':
        return _ready(request, scratch, source)
    if g == 'qb':
        return _qb(request, scratch, source)
    return LA.Adapter(source, scratch).evaluate(request)
