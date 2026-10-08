#!/usr/bin/env python3.12
"""Generic next-slate Showdown execution path, fail-closed. One slate config, one command per phase.

    python3.12 nfl/tools/showdown_next_slate.py run    SLATE.json [--mode final|precompute]
    python3.12 nfl/tools/showdown_next_slate.py market SLATE.json HARDROCK_BOARD.csv     # after the seal, before kickoff
    python3.12 nfl/tools/showdown_next_slate.py postgame SLATE.json --standings CID=standings.zip [--actuals A.json]

ORDER (readiness directive, 2026-10-07):
    DISCOVER -> VERIFY -> FREEZE FOOTBALL REALITY -> PROJECT -> SIMULATE -> BUILD DFS PORTFOLIOS -> RUN B4 SHADOW
    -> SEAL PROP DISTRIBUTIONS -> [COMPARE TO MARKET: separate `market` phase] -> FINAL VERIFY

SLATE.json (paths relative to the repository root):
    {"tag": "KC_JAX_2026W6", "kickoff_utc": "2026-10-12T17:00:00Z", "scenario": "OFFICIAL",
     "export": ".../DKEntries_....csv", "fc": ".../THIRDPARTY_FC_..._CONTEXT_ONLY....csv" (optional),
     "designations": "...json", "official_inactives": "...json", "official_inactives_provenance": "...json",
     "confirmed_starters": "...json", "starter_tier": "...", "depth_chart": "...csv",
     "contests": {"<id>": {"prize_pool": 100000, "entry_fee": 0.5, "max_entries": 150, "field_size": 237812}},
     "snaps": ".../snap_counts_2026.<sha16>.csv" (optional; the SC-OWN-ROTATION-2 ownership shadow needs it)}

FAIL-CLOSED. A missing official inactive list, a starter not confirmed for both clubs, a depth chart that does not
cover both clubs, a DK salary / ID failure, or a derived cache that does not match its manifest stops the run before
any projection. `--mode precompute` lets the football run without the official list, but such a run can never be
READY. A secondary-source inactive list (no provenance record saying OFFICIALLY_VERIFIED) runs and is never READY.
UNKNOWN is not ZERO and MISSING is not NOT PLAYING: nothing here fills a gap.

NON-BLOCKING SHADOWS. The field shadow, the boards and the B4 duplication shadow run AFTER the upload is written
and their failure is recorded, never fatal: nothing in them is read by selection.

HARD ROCK IS DOWNSTREAM ONLY. Its board is compared in the `market` phase, which refuses unless the prop seal
exists, and price_history.comparable refuses any price captured before the seal or after kickoff. No price
travels back into the football model, the simulation or a lineup.

REPRODUCIBILITY. FINAL VERIFY rebuilds the portfolios from the frozen worlds into a copy of the scenario and
requires the same upload bytes, and re-hashes every frozen input to prove nothing changed during the run.

REHEARSAL. A config with "rehearsal": true (and its own scenario, market_dir and a stand-in kickoff) runs every
step on a past slate to prove the path end to end. It is labelled in the ledger and can never be READY.

Nothing here uploads to DraftKings, enters a contest or recommends a wager.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PY = sys.executable or 'python3.12'
REQUIRED = ('tag', 'kickoff_utc', 'export', 'designations', 'confirmed_starters', 'starter_tier', 'depth_chart',
            'contests')
FINAL_REQUIRED = ('official_inactives', 'official_inactives_provenance')
MANIFEST = _REPO / 'nfl/production/DERIVED_REBUILD_MANIFEST.json'


class SlateError(RuntimeError):
    """A blocking failure, by name."""


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _now():
    return dt.datetime.now(dt.timezone.utc)


def _ts(s):
    return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))


class Ledger:
    def __init__(self, path):
        self.path, self.steps = path, []

    def add(self, step, state, **kw):
        self.steps.append({'step': step, 'state': state, 'at': _now().isoformat(), **kw})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({'ARTIFACT': 'SHOWDOWN_NEXT_SLATE_RUN_LEDGER', 'steps': self.steps},
                                        indent=1, default=str))
        print(f'{step:22s} {state} {json.dumps(kw, default=str)[:300]}', flush=True)


# ---------------------------------------------------------------- DISCOVER
def discover(cfg_path, mode):
    cfg = json.loads(pathlib.Path(cfg_path).read_text())
    need = REQUIRED + (FINAL_REQUIRED if mode == 'final' else ())
    miss = [k for k in need if not cfg.get(k)]
    if miss:
        raise SlateError(f'SLATE_CONFIG_MISSING {miss}')
    if '_2026' not in cfg['tag'] or len(cfg['tag'].split('_2026')[0].split('_')) != 2:
        raise SlateError(f'SLATE_TAG_SHAPE {cfg["tag"]} (expected AWAY_HOME_2026W<n>)')
    files = {k: cfg[k] for k in ('export', 'fc', 'designations', 'official_inactives', 'official_inactives_provenance',
                                 'confirmed_starters', 'confirmed_starters_provenance', 'depth_chart', 'snaps')
             if cfg.get(k)}
    absent = [f'{k}={v}' for k, v in files.items() if not (_REPO / v).is_file() or (_REPO / v).stat().st_size == 0]
    if absent:
        raise SlateError(f'INPUT_FILE_MISSING_OR_EMPTY {absent}')
    for cid, c in cfg['contests'].items():
        bad = [k for k in ('prize_pool', 'entry_fee') if not isinstance(c.get(k), (int, float))]
        # a per-user limit DK does not state is not invented: null max_entries needs a declared lower bound
        if not isinstance(c.get('max_entries'), (int, float)) and not (
                c.get('max_entries') is None and isinstance(c.get('max_entries_lower_bound'), int)):
            bad.append('max_entries')
        if bad:
            raise SlateError(f'CONTEST_FIELDS_MISSING {cid} {bad}')
    cfg['scenario'] = cfg.get('scenario') or ('OFFICIAL' if mode == 'final' else 'PRECOMPUTE')
    return cfg, {k: {'path': v, 'sha256': _sha(_REPO / v)} for k, v in files.items()}


def env_for(cfg, cfg_path):
    # EXPLICIT CONTEXT ONLY (independent P0 fixture ISO-inherited_environment): an inherited SHOWDOWN_PREFIX /
    # SHOWDOWN_WEEK / run id from an earlier slate would otherwise override this slate's derived values in
    # showdown_slate_env. Every SHOWDOWN_* key is dropped and the slate's own are set from its config.
    e = {k: v for k, v in os.environ.items() if not k.startswith('SHOWDOWN_')}
    tag = cfg['tag']
    e.update({'SHOWDOWN_TAG': tag, 'SHOWDOWN_SLATE_CONFIG': str(pathlib.Path(cfg_path).resolve()),
              'SHOWDOWN_RAW_DIR': str((_REPO / cfg['export']).parent),
              'SHOWDOWN_PREFIX': 'SHOWDOWN_' + tag.split('_2026')[0], 'SHOWDOWN_WEEK': tag.rsplit('W', 1)[-1]})
    return e


# ---------------------------------------------------------------- VERIFY
def verify_derived(env):
    if not MANIFEST.exists():
        raise SlateError('DERIVED_MANIFEST_ABSENT')
    want = json.loads(MANIFEST.read_text())['sha256']
    bad = [n for n, h in want.items() if not (_REPO / 'nfl/derived' / n).exists() or _sha(_REPO / 'nfl/derived' / n) != h]
    if bad:
        r = subprocess.run(['bash', str(_REPO / 'nfl/tools/rebuild_derived.sh')], cwd=_REPO, env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SlateError(f'DERIVED_NOT_VERIFIED {bad}: {r.stdout[-400:]}')
        return {'rebuilt': bad}
    return {'verified': sorted(want)}


def verify_football_inputs(cfg, mode):
    from nfl.tools.showdown_portfolio import dk_input_gate
    g = dk_input_gate(str(_REPO / cfg['export']))
    if g.state.value != 'PASS':
        raise SlateError(f'DK_INPUT_GATE {g.code} {g.detail}')
    teams = sorted(g.value['teams'])
    want = sorted(cfg['tag'].split('_2026')[0].split('_'))
    if teams != want:
        raise SlateError(f'SLATE_TEAMS_MISMATCH export {teams} tag {want}')
    starters = json.loads((_REPO / cfg['confirmed_starters']).read_text())
    if sorted(set(starters.values())) != teams:
        raise SlateError(f'STARTERS_NOT_CONFIRMED_FOR_BOTH_CLUBS {starters}')
    import csv
    clubs = {r.get('club_code') or r.get('team') for r in csv.DictReader(open(_REPO / cfg['depth_chart']))}
    if not set(teams) <= clubs:
        raise SlateError(f'DEPTH_CHART_DOES_NOT_COVER_BOTH_CLUBS has {sorted(c for c in clubs if c)} need {teams}')
    out = {'dk_input_gate': g.code, 'dk_sha256': g.value['sha256'], 'teams': teams,
           'contests_in_export': sorted(g.value['contests'])}
    unknown = sorted(set(g.value['contests']) - set(cfg['contests']))
    if unknown:
        raise SlateError(f'EXPORT_CONTEST_NOT_DECLARED {unknown}')
    for cid, c in cfg['contests'].items():
        held = g.value['contests'].get(cid, {}).get('entries', 0)
        cap = c.get('max_entries') if c.get('max_entries') is not None else None
        if cap is not None and held > cap:
            raise SlateError(f'ENTRIES_EXCEED_MAX {cid} held {held} max {cap}')
        if cap is None and c.get('max_entries_lower_bound') != held:
            raise SlateError(f'MAX_ENTRIES_LOWER_BOUND_NOT_HELD_COUNT {cid} bound {c.get("max_entries_lower_bound")} held {held}')
    official = False
    if cfg.get('official_inactives'):
        lst = json.loads((_REPO / cfg['official_inactives']).read_text())
        if not isinstance(lst, list) or not lst:
            raise SlateError('OFFICIAL_INACTIVES_EMPTY (an empty list is an error, not "nobody inactive")')
        prov = json.loads((_REPO / cfg['official_inactives_provenance']).read_text()) \
            if cfg.get('official_inactives_provenance') else {}
        if prov and prov.get('sha256') != _sha(_REPO / cfg['official_inactives']):
            raise SlateError('INACTIVES_PROVENANCE_DESCRIBES_ANOTHER_FILE (its sha256 does not match the list)')
        official = prov.get('OFFICIALLY_VERIFIED') is True
        out.update({'official_inactives_n': len(lst), 'officially_verified': official,
                    'inactives_evidence_tier': prov.get('EVIDENCE_TIER')})
    elif mode == 'final':
        raise SlateError('OFFICIAL_INACTIVES_REQUIRED')
    # STARTERS: a chart or a scenario file names a starter; READY needs CONFIRMATION (owner ruling 2026-10-07: TB@DAL
    # runs only with a confirmed TB starting QB). A provenance record whose sha256 is the starters file's and which says
    # CONFIRMED true (with its source) is the confirmation. Without it the run may proceed and is never READY.
    confirmed = False
    if cfg.get('confirmed_starters_provenance'):
        sp = json.loads((_REPO / cfg['confirmed_starters_provenance']).read_text())
        if sp.get('sha256') != _sha(_REPO / cfg['confirmed_starters']):
            raise SlateError('STARTERS_PROVENANCE_DESCRIBES_ANOTHER_FILE')
        confirmed = sp.get('CONFIRMED') is True and bool(sp.get('source'))
    out['starters_confirmed'] = confirmed
    out['ready_eligible'] = mode == 'final' and official and confirmed and not cfg.get('rehearsal')
    return out


# ---------------------------------------------------------------- FREEZE
def freeze(cfg, hashes, sd_root, verified):
    p = sd_root / f'FOOTBALL_REALITY_FREEZE_{cfg["scenario"]}.json'
    if p.exists():
        raise SlateError(f'FREEZE_EXISTS_WRITE_ONCE {p} (choose a new scenario name to rerun)')
    body = {'ARTIFACT': 'FOOTBALL_REALITY_FREEZE', 'tag': cfg['tag'], 'scenario': cfg['scenario'],
            'kickoff_utc': cfg['kickoff_utc'], 'inputs': hashes, 'verify': verified, 'frozen_at': _now().isoformat(),
            'RULE': 'every football input is hashed here BEFORE projection; FINAL VERIFY re-hashes them'}
    body['seal_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    sd_root.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body, indent=1, default=str))
    p.chmod(0o444)
    return p, body


def _run(cmd, env, name):
    r = subprocess.run([str(c) for c in cmd], cwd=_REPO, env=env, capture_output=True, text=True)
    tail = '\n'.join(l for l in (r.stdout + r.stderr).splitlines() if 'worlds solved' not in l)[-1500:]
    return r.returncode, tail


def run(cfg_path, mode='final'):
    from nfl.tools import showdown_slate_run as SR
    cfg, hashes = discover(cfg_path, mode)
    P = SR.paths(cfg['tag'])
    scen = cfg['scenario']
    sd = P['dir'] / scen
    pre = f'SHOWDOWN_{cfg["tag"].split("_2026")[0]}'
    lp = P['dir'] / f'RUN_LEDGER_{scen}.json'
    if sd.exists() or lp.exists():
        # write-once: a re-run that will be refused must not overwrite the original run's ledger (TB@DAL 2026-10-08:
        # a SCENARIO_EXISTS refusal rewrote RUN_LEDGER_PRECOMPUTE_TBQB_DANIELS_R7.json with the refusal)
        lp = P['dir'] / f'RUN_LEDGER_{scen}.REFUSED_{_now().strftime("%Y%m%dT%H%M%S%fZ")}.json'
    L = Ledger(lp)
    L.add('DISCOVER', 'PASS', tag=cfg['tag'], scenario=scen, mode=mode, inputs=hashes,
          REHEARSAL=bool(cfg.get('rehearsal')))
    # ONE RUN PER SLATE AT A TIME. showdown_tonight writes state / proj / draws / worlds to per-TAG paths and copies
    # them into the scenario afterwards, so two scenarios run concurrently read each other's state (TB@DAL
    # 2026-10-08: the Daniels and Mayfield precomputes produced byte-identical uploads from one state).
    import fcntl
    P['dir'].mkdir(parents=True, exist_ok=True)
    # GLOBAL, not per tag: the legacy path wrote nfl/derived/ROLE_STATE.json and DST_RATES.json, shared by all slates
    lock = open(_REPO / 'nfl/dfs/salaries/.SHOWDOWN_RUN_LOCK', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        L.add('REFUSED', 'CONCURRENT_RUN', detail='another Showdown run holds nfl/dfs/salaries/.SHOWDOWN_RUN_LOCK')
        raise SlateError(f'CONCURRENT_RUN {cfg["tag"]} (another Showdown run is in progress; run in sequence)')
    try:
        return _run_body(cfg, cfg_path, mode, hashes, P, scen, sd, pre, L)
    except SlateError as e:
        L.add('REFUSED', str(e).split()[0], detail=str(e))
        raise
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


#: Directories whose top-level files a scenario build must NOT write. Anything changed here during the build is a
#: shared write another scenario could read.
_SHARED_WATCH = ('nfl/derived', 'nfl/dfs/salaries', 'nfl/sim', 'nfl/warehouse')


#: Shared writes that are scenario-INDEPENDENT by construction, each with the reason. Anything else is a breach.
SHARED_WRITE_ALLOWED = {
    'nfl/derived/SOURCE_MEASUREMENT_CACHE.json':
        'nfl/warehouse/sources.py speed cache of capture-file measurements, keyed on path|full-content sha256|'
        'datatype since 2026-10-08 (it was path|size|mtime, which a same-second rewrite defeated -- independent P0 '
        'fixture DATA-measurement_cache); it holds no scenario input',
}


def _shared_snapshot(tag_dir):
    snap = {}
    for d in [_REPO / x for x in _SHARED_WATCH] + [tag_dir]:
        if d.is_dir():
            for f in d.iterdir():
                if f.is_file() and not f.name.startswith('.'):
                    st = f.stat()
                    snap[str(f.relative_to(_REPO))] = (st.st_size, st.st_mtime_ns)
    return snap


def shared_writes(before, after, allowed=()):
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k) and k not in allowed)


def scenario_state_matches(cfg, state, expected=None, absent_statuses=None, starters_digest=None):
    """Reason codes for every way the built state disagrees with THIS scenario; [] only when it all holds.

    Positive and complete (nfl/tools/showdown_run_guards.verify_starter_state): scenario identity, canonical ids
    against an independent identity source (the captured depth chart), team, starting flag, availability, starter
    evidence bound to this scenario's starters, designations, and OUT never overwritten. Without the inputs to
    build an expectation it REFUSES rather than passing.
    """
    try:
        from nfl.tools import showdown_run_guards as G
        desig = json.loads((_REPO / cfg['designations']).read_text())
        starters = json.loads((_REPO / cfg['confirmed_starters']).read_text())
        if expected is None:
            expected = G.expected_state(cfg['tag'], cfg['scenario'], desig, starters,
                                        G.identity_from_depth_chart(_REPO / cfg['depth_chart'],
                                                                    set(starters) | set(desig)))
        if absent_statuses is None:
            from nfl.tools import availability as AV
            absent_statuses = tuple(AV.ABSENT_STATUSES) + ('OUT',)
        return G.verify_starter_state(state, expected, absent_statuses,
                                      starters_digest if starters_digest is not None else G.starters_digest(starters))
    except Exception as e:  # noqa: BLE001
        return [f'EXPECTATION_UNAVAILABLE {type(e).__name__}: {str(e)[:160]} (refused, not passed)']

def _run_body(cfg, cfg_path, mode, hashes, P, scen, sd, pre, L):
    if _now() >= _ts(cfg['kickoff_utc']):
        raise SlateError(f'RUN_AFTER_KICKOFF {cfg["kickoff_utc"]}')
    if sd.exists():
        raise SlateError(f'SCENARIO_EXISTS {sd} (write-once; choose a new scenario name)')
    env = env_for(cfg, cfg_path)
    der = verify_derived(env)
    ver = verify_football_inputs(cfg, mode)
    L.add('VERIFY', 'PASS', derived=der, **ver)
    fp, fb = freeze(cfg, hashes, P['dir'], ver)
    L.add('FREEZE', 'PASS', freeze=str(fp.relative_to(_REPO)), seal=fb['seal_sha256'])
    # RUN CONTEXT: what the build's receipt must match for this run to finalize
    import uuid
    from nfl.tools import showdown_run_guards as G
    run = {'run_id': 'run:' + uuid.uuid4().hex, 'commit': G.git_head(_REPO), 'repo': _REPO,
           'code_dirty': G.tracked_code_dirty(_REPO), 'freeze_seal': fb['seal_sha256'],
           'scenario_identity': G.scenario_identity(cfg['tag'], scen,
                                                    json.loads((_REPO / cfg['designations']).read_text()),
                                                    json.loads((_REPO / cfg['confirmed_starters']).read_text()))}
    env.update({'SHOWDOWN_RUN_ID': run['run_id'], 'SHOWDOWN_RUN_COMMIT': str(run['commit']),
                'SHOWDOWN_FREEZE_SEAL': run['freeze_seal'], 'SHOWDOWN_SCENARIO_IDENTITY': run['scenario_identity']})
    run['environment_sha256'] = G.environment_fingerprint(env)['sha256']
    L.add('RUN_CONTEXT', 'RECORDED', **{k: (str(v) if k == 'repo' else v) for k, v in run.items()})

    cmd = [PY, 'nfl/tools/showdown_tonight.py', _REPO / cfg['export'], '--scenario', scen, '--tag', cfg['tag'],
           '--designations', _REPO / cfg['designations'], '--confirmed-starters', _REPO / cfg['confirmed_starters'],
           '--starter-tier', cfg['starter_tier'], '--depth-chart', _REPO / cfg['depth_chart']]
    if cfg.get('official_inactives'):
        cmd += ['--official-inactives', _REPO / cfg['official_inactives']]
    before = _shared_snapshot(P['dir'])
    rc, tail = _run(cmd, env, 'tonight')
    after = _shared_snapshot(P['dir'])
    benign = [k for k in shared_writes(before, after) if k in SHARED_WRITE_ALLOWED]
    breach = shared_writes(before, after, allowed=(str(L.path.relative_to(_REPO)),
                                                   *SHARED_WRITE_ALLOWED))
    if benign:
        L.add('SHARED_WRITE_ALLOWED', 'RECORDED', paths={k: SHARED_WRITE_ALLOWED[k] for k in benign})
    if breach:
        raise SlateError(f'SCENARIO_ISOLATION_BREACH the build wrote shared paths {breach[:8]}')
    up = sd / f'{pre}_DK_UPLOAD.csv'
    if rc != 0 or not up.is_file() or up.stat().st_size == 0:
        L.add('PROJECT_SIMULATE_BUILD', 'FAIL', rc=rc, tail=tail)
        g = sd / 'SCENARIO_GUARD.json'
        if g.is_file() and json.loads(g.read_text()).get('state') == 'REFUSED':
            raise SlateError(f'SCENARIO_STATE_MISMATCH_BEFORE_PROJECTION {json.loads(g.read_text())["reasons"][:4]}')
        raise SlateError(f'PIPELINE_FAILED rc={rc} upload_present={up.is_file()}')
    stf = sd / f'{pre}_{cfg["tag"].split("_", 2)[2]}_STATE.json'
    if not stf.is_file():
        raise SlateError(f'SCENARIO_STATE_ABSENT {stf}')
    mism = scenario_state_matches(cfg, json.loads(stf.read_text()))
    if mism:
        raise SlateError(f'SCENARIO_STATE_MISMATCH {mism[:4]}')
    # FOOTBALL-MODEL COMPLETENESS (owner directive 2026-10-08): the club environment is club history; it represents the
    # scenario's QB only if he threw a majority of the attempts it is built from. Not a refusal of the build -- a
    # separate readiness status that READY requires.
    try:
        from nfl.tools import showdown_run_guards as G, player_prior as PP, proj_v1 as PV
        run['football_model'] = G.football_model_status(json.loads(stf.read_text()), PP.load_panel().value,
                                                        PV.TEAM_VOLUME_PRIOR_GAMES)
    except Exception as e:  # noqa: BLE001
        run['football_model'] = {'status': 'UNDETERMINED', 'reasons': [f'{type(e).__name__}: {str(e)[:160]}']}
    L.add('FOOTBALL_MODEL', run['football_model']['status'], **run['football_model'])
    L.add('PROJECT_SIMULATE_BUILD', 'PASS', upload=str(up.relative_to(_REPO)), upload_sha256=_sha(up),
          tail=tail[-600:])

    # ---- non-blocking: field shadow, boards, B4 duplication shadow (nothing here is read by selection)
    shadows = {}
    absent = P['dir'] / f'SHADOW_ABSENT_{scen}.json'
    absent.write_text(json.dumps(json.loads((sd / 'SCENARIO.json').read_text())['absent_in_state'], indent=1))
    if cfg.get('fc'):
        fc = _REPO / cfg['fc']
        steps = [('shadow_fc', ['nfl/field/showdown_shadow_field.py', _REPO / cfg['export'], fc, P['dir'] / f'SHADOW_{scen}',
                                '--absent', absent]),
                 ('shadow_blend', ['nfl/field/showdown_shadow_field.py', _REPO / cfg['export'], fc,
                                   P['dir'] / f'SHADOW_{scen}_BLEND', '--absent', absent, '--blend-draws',
                                   sd / P['draws'].name])]
    else:
        steps = []
        shadows['shadow_field'] = 'NOT_BUILT: no FC file in the slate config (the field shadow needs it)'
    steps += [('audit', ['nfl/tools/showdown_portfolio_audit.py', _REPO / cfg['export'], sd])]
    if cfg.get('fc'):
        steps += [('board_blend', ['nfl/field/showdown_shadow_board.py', _REPO / cfg['export'], sd, P['dir'] / f'SHADOW_{scen}_BLEND']),
                  ('board_fc', ['nfl/field/showdown_shadow_board.py', _REPO / cfg['export'], sd, P['dir'] / f'SHADOW_{scen}']),
                  ('arch_blend', ['nfl/field/showdown_archetype_field.py', _REPO / cfg['export'], sd, P['dir'] / f'SHADOW_{scen}_BLEND']),
                  ('arch_fc', ['nfl/field/showdown_archetype_field.py', _REPO / cfg['export'], sd, P['dir'] / f'SHADOW_{scen}']),
                  ('fc_compare', ['nfl/tools/showdown_fc_compare.py', sd, _REPO / cfg['fc']])]
    steps += [('cycle1', ['nfl/tools/showdown_cycle1_checks.py', sd]),
              ('prelock_board', ['nfl/tools/showdown_prelock_board.py', _REPO / cfg['export'], sd])]
    for name, c in steps:
        rc, tail = _run([PY] + c, env, name)
        shadows[name] = 'PASS' if rc == 0 else f'FAIL rc={rc}: {tail[-300:]}'
    own = P['dir'] / f'SHADOW_{scen}_BLEND' / f'{pre}_SHADOW_OWNERSHIP.csv'
    b4 = P['dir'] / f'DUPE_SHADOW_B4_{scen}.json'
    if own.exists():
        sizes = []
        for cid, c in cfg['contests'].items():
            n = c.get('field_size') or round(c['prize_pool'] / (c['entry_fee'] * 0.85))
            me = c['max_entries'] if c.get('max_entries') is not None else c['max_entries_lower_bound']
            sizes += ['--contest', f'{cid}={int(n)}:{int(me)}']
            if c.get('max_entries') is None:
                shadows[f'B4_MAX_ENTRIES_{cid}'] = f'LOWER_BOUND {me} (entries held; DK name states no limit)'
        c = [PY, 'nfl/field/showdown_dupe_shadow.py', '--export', _REPO / cfg['export'], '--ownership', own,
             '--lineups', sd / f'{pre}_FINAL_LINEUPS.csv', *sizes, '--kickoff', cfg['kickoff_utc'], '--out', b4,
             '--model', 'B4', '--model', 'B3S']
        if cfg.get('rehearsal'):
            c += ['--dry-run']    # a rehearsal is never a prelock record, whatever stand-in kickoff it carries
        if cfg.get('fc'):
            c += ['--fc', _REPO / cfg['fc']]
        stack = sd / f'{pre}_DUPE_STACK_BLEND.json'
        if stack.exists():
            c += ['--legacy-dupe-stack', stack]
        rc, tail = _run(c, env, 'b4')
        shadows['B4_SHADOW'] = ('PASS ' + str(b4.relative_to(_REPO))) if rc == 0 else f'FAIL rc={rc}: {tail[-300:]}'
        if not any(cfg['contests'][x].get('field_size') for x in cfg['contests']):
            shadows['B4_SHADOW_FIELD_SIZE'] = 'ESTIMATE prize / (fee x 0.85); declare field_size when DK shows it'
    else:
        shadows['B4_SHADOW'] = 'NOT_RUN: no shadow ownership forecast (needs the FC-based field shadow)'
    # SC-OWN-ROTATION-2 ownership shadow (frozen 2026-10-07; sealed per slate; never read by selection)
    if own.exists() and cfg.get('snaps'):
        proj = sd / f'{pre}_PROJECTIONS.csv'
        ow = _REPO / 'nfl/research/ownership/predictions' / f"SC_OWN_ROTATION_2_{cfg['tag']}_{scen}.json"
        c = [PY, 'nfl/research/ownership/predict_sc_own_rotation_2.py', '--slate', cfg['tag'],
             '--week', cfg['tag'].rsplit('W', 1)[-1], '--kickoff', cfg['kickoff_utc'], '--export', _REPO / cfg['export'],
             '--baseline', own, '--projection', proj, '--depth-chart', _REPO / cfg['depth_chart'],
             '--designations', _REPO / cfg['designations'], '--snaps', _REPO / cfg['snaps'], '--out', ow]
        if cfg.get('official_inactives'):
            c += ['--inactives', _REPO / cfg['official_inactives']]
        if cfg.get('rehearsal'):
            c += ['--dry-run', '--label', 'REHEARSAL']
        rc, tail = _run(c, env, 'own2')
        shadows['OWNERSHIP_SC_OWN_ROTATION_2'] = ('PASS ' + str(ow.relative_to(_REPO))) if rc == 0 else f'FAIL rc={rc}: {tail[-300:]}'
    else:
        shadows['OWNERSHIP_SC_OWN_ROTATION_2'] = 'NOT_RUN: needs the BLEND shadow ownership and a snaps capture (SLATE.json "snaps")'
    # APPEARANCE SUCCESSOR: sealed per WEEK for every game before that week's first kickoff (nfl/prospective/appearance).
    # The runner does not recompute it; it verifies that this game is covered by a valid prelock seal and records it.
    try:
        from nfl.research.appearance import grade_appearance_seal as GA
        wk = int(cfg['tag'].rsplit('W', 1)[-1])
        sealp = _REPO / f'nfl/prospective/appearance/APPEARANCE_SUCCESSOR_W{wk}_SEAL.json'
        doc = GA.load_seal(sealp)
        gid = f"2026_{wk:02d}_{cfg['tag'].split('_2026')[0]}"
        shadows['APPEARANCE_SUCCESSOR'] = (f"SEALED {sealp.relative_to(_REPO)} seal {doc['seal_sha256'][:12]} written {doc['written_at']}"
                                           if gid in (doc.get('games') or {}) else f'NOT_COVERED: {gid} not in the week-{wk} seal')
    except Exception as e:  # noqa: BLE001 -- a shadow never blocks; its failure is recorded by name
        shadows['APPEARANCE_SUCCESSOR'] = f'NOT_VERIFIED: {type(e).__name__}: {str(e)[:200]}'
    L.add('SHADOWS_NON_BLOCKING', 'RECORDED', **shadows)

    # ---- SEAL PROP DISTRIBUTIONS (final mode only: the seal is write-once per slate, so a precompute must not take it;
    #      blocking for the market phase, not for the DFS upload)
    if mode != 'final':
        L.add('SEAL_PROPS', 'SKIPPED_PRECOMPUTE', why='the prop seal is taken once, by the final run')
        rc = 0
    else:
        mk = market_dir(cfg)
        rc, tail = _run([PY, 'nfl/market/showdown_prop_shadow.py', 'seal', '--scenario-dir', sd, '--out-dir', mk,
                         '--slate', cfg['tag'].split('_2026')[0], '--kickoff', cfg['kickoff_utc']], env, 'seal')
        L.add('SEAL_PROPS', 'PASS' if rc == 0 else 'FAIL', out=str(mk.relative_to(_REPO)), tail=tail[-300:])

    return final_verify(cfg, cfg_path, hashes, ver, L, P, sd, pre, env, prop_seal_ok=(None if mode != 'final' else rc == 0),
                        run=run)


# ---------------------------------------------------------------- FINAL VERIFY
def final_verify(cfg, cfg_path, hashes, ver, L, P, sd, pre, env, prop_seal_ok, run=None):
    blockers = []
    if run is None:
        # the legacy calling convention: no current run context, so nothing can bind the build's receipt to this run
        blockers.append('RUN_CONTEXT_ABSENT (no current run id / commit; a direct or legacy call cannot finalize)')
    changed = [k for k, v in hashes.items() if _sha(_REPO / v['path']) != v['sha256']]
    if changed:
        blockers.append(f'INPUTS_CHANGED_DURING_RUN {changed}')
    up = sd / f'{pre}_DK_UPLOAD.csv'
    want = _sha(up)
    rep = P['dir'] / f'{cfg["scenario"]}_REPRO'
    if rep.exists():
        shutil.rmtree(rep)
    shutil.copytree(sd, rep, ignore=shutil.ignore_patterns(f'{pre}_DK_UPLOAD*', f'{pre}_FINAL_*'))
    rc, tail = _run([PY, 'nfl/tools/showdown_tonight.py', _REPO / cfg['export'], '--scenario', rep.name, '--tag',
                     cfg['tag'], '--portfolio-only'], env, 'repro')
    got = _sha(rep / up.name) if (rep / up.name).exists() else None
    if got != want:
        blockers.append(f'UPLOAD_NOT_REPRODUCED {want[:12]} vs {str(got)[:12]} rc={rc}')
    if rc != 0:
        # INDEPENDENT of the hash (independent P0 fixture READY-nonzero_matching_upload): a replay that failed
        # proves nothing, whatever bytes it left behind
        blockers.append(f'REPLAY_EXIT_NONZERO rc={rc}')
    if run is not None:
        from nfl.tools import showdown_run_guards as G
        blockers += [b for b in G.verify_receipt(sd, run, cfg['tag'], cfg['scenario'], replay_rc=rc, replay_dir=rep)
                     if not b.startswith('REPLAY_EXIT_NONZERO')]
        if run.get('code_dirty') is None or run.get('code_dirty'):
            blockers.append(f'CODE_NOT_COMMITTED {run.get("code_dirty")} (a run from uncommitted code cannot be READY)')
        stf = G.football_bundle(sd, cfg['tag'])['STATE.json']
        if stf.is_file():
            mism = scenario_state_matches(cfg, json.loads(stf.read_text()))
            if mism:
                blockers.append(f'SCENARIO_STATE_MISMATCH {mism[:4]}')
    fb = sd / f'{pre}_FINAL_BOARD.json'
    if fb.exists():
        b = json.loads(fb.read_text())
        if b.get('VERIFIER_VIOLATIONS') not in (0, '0'):
            blockers.append(f'VERIFIER_VIOLATIONS {b.get("VERIFIER_VIOLATIONS")}')
        if b.get('UNCLASSIFIED'):
            blockers.append(f'UNCLASSIFIED_PLAYERS {b["UNCLASSIFIED"]}')
        if b.get('BLOCKED'):
            blockers.append(f'BLOCKED_PLAYERS {b["BLOCKED"]}')
    else:
        blockers.append('FINAL_BOARD_ABSENT')
    if cfg.get('rehearsal'):
        blockers.append('REHEARSAL_NOT_LIVE (kickoff and scenario are rehearsal values; never READY)')
    elif not ver.get('starters_confirmed'):
        blockers.append('STARTERS_NOT_CONFIRMED (no confirmed_starters_provenance with CONFIRMED true and a source)')
    elif not ver.get('ready_eligible'):
        blockers.append('INACTIVES_NOT_OFFICIALLY_VERIFIED_OR_PRECOMPUTE_MODE')
    if prop_seal_ok is False:          # None = precompute (the seal belongs to the final run)
        blockers.append('PROP_SEAL_FAILED (market phase unavailable; DFS unaffected)')
    if _now() >= _ts(cfg['kickoff_utc']):
        blockers.append('FINAL_VERIFY_AFTER_KICKOFF')
    # FOUR STATUSES, NOT ONE (owner directive 2026-10-08). Each is reported; READY needs all four.
    fm = (run or {}).get('football_model') or {'status': 'UNDETERMINED', 'reasons': ['no football-model status computed']}
    if fm['status'] != 'COMPLETE_FOR_STARTERS':
        blockers.append(f'FOOTBALL_MODEL_{fm["status"]} {fm.get("reasons", [])[:2]}')
    tech = [b for b in blockers if not b.startswith(('STARTERS_NOT_CONFIRMED', 'INACTIVES_NOT_OFFICIALLY', 'INPUTS_CHANGED',
                                                     'FOOTBALL_MODEL_', 'REHEARSAL_NOT_LIVE', 'PROP_SEAL_FAILED'))]
    data = [b for b in blockers if b.startswith(('STARTERS_NOT_CONFIRMED', 'INACTIVES_NOT_OFFICIALLY', 'INPUTS_CHANGED'))]
    readiness = {'technical': 'PASS' if not tech else 'FAIL', 'data': 'PASS' if not data else 'FAIL',
                 'football_model': fm['status'], 'dfs_decision': 'READY' if not blockers else 'NOT_READY'}
    state = 'READY' if not blockers else 'NOT_READY'
    L.add('READINESS', state, **readiness)
    L.add('FINAL_VERIFY', state, upload_sha256=want, reproduced_sha256=got, blockers=blockers, readiness=readiness,
          NOT_SUBMITTED='nothing is uploaded to DraftKings or entered; no wager is recommended')
    return state, blockers


def market_dir(cfg):
    return _REPO / (cfg.get('market_dir') or f"nfl/market/{cfg['tag'].split('_2026')[0].lower()}_2026{cfg['tag'].split('_2026')[1]}")


def market(cfg_path, board):
    cfg = json.loads(pathlib.Path(cfg_path).read_text())
    mk = market_dir(cfg)
    if not (mk / 'PROP_FORECAST_SEAL.json').exists():
        raise SlateError('MARKET_BEFORE_SEAL (the prop seal must exist before any Hard Rock board is read)')
    r = subprocess.run([PY, 'nfl/market/showdown_prop_shadow.py', 'compare', '--out-dir', str(mk), '--slate',
                        cfg['tag'].split('_2026')[0], str(board)], cwd=_REPO, capture_output=True, text=True)
    print(r.stdout, r.stderr)
    return r.returncode


def postgame(cfg_path, standings, actuals=None):
    """After the game: archive each contest's full-field standings (immutable), reconcile them, grade the sealed B4/B3S
    shadow against them (prelock records only), and settle props if official actuals are given. Evidence accumulation
    only; nothing here changes a model, a lineup or an objective."""
    from nfl.field import showdown_field_archive as FA
    from nfl.tools import showdown_slate_run as SR
    cfg = json.loads(pathlib.Path(cfg_path).read_text())
    slug = cfg['tag'].split('_2026')[0]
    P = SR.paths(cfg['tag'])
    out = {'ARTIFACT': 'SHOWDOWN_POSTGAME_EVIDENCE', 'tag': cfg['tag'], 'scenario': cfg.get('scenario'),
           'STATUS': 'SHADOW_ONLY -- EVIDENCE ACCUMULATION', 'contests': {}, 'at': _now().isoformat()}
    if not standings:
        raise SlateError('POSTGAME_NEEDS_STANDINGS (CID=path, one per contest)')
    shadow = P['dir'] / f"DUPE_SHADOW_B4_{cfg.get('scenario')}.json"
    for spec in standings:
        cid, _, path = spec.partition('=')
        if cid not in cfg['contests']:
            raise SlateError(f'POSTGAME_UNDECLARED_CONTEST {cid}')
        d = FA._dir(cid, slug)
        try:
            if not (d / 'PROVENANCE.jsonl').exists():
                FA.ingest(path, cid, slug, cfg['contests'][cid].get('name') or cid,
                          'DK contest standings export, owner download')
            rec = FA.reconcile(cid, slug, _REPO / cfg['export'])
            (d / 'RECONCILIATION.json').write_text(json.dumps(rec, indent=1))
            c = {'reconciliation': rec['VERDICT'], 'problems': rec['problems'], 'counts': {
                k: rec['counts'][k] for k in ('entries_filled', 'distinct_lineups', 'score_ties_among_distinct_lineups')}}
            if rec['VERDICT'] != 'RECONCILED':
                c['grade'] = 'NOT_GRADED: field not reconciled'
            elif not shadow.exists():
                c['grade'] = f'NOT_GRADED: no sealed shadow at {shadow.name}'
            else:
                g = FA.grade(cid, slug, shadow)
                gp = d / f"DUPE_SHADOW_GRADE.{g['shadow_seal'][:12]}.json"
                if not gp.exists():
                    gp.write_text(json.dumps(g, indent=1, default=str))
                c['grade'] = g['summary']
        except FA.ArchiveError as e:
            c = {'REFUSED': str(e)}
        out['contests'][cid] = c
    if actuals:
        r = subprocess.run([PY, 'nfl/market/showdown_prop_shadow.py', 'settle', '--out-dir', str(market_dir(cfg)),
                            '--slate', slug, str(actuals)], cwd=_REPO, capture_output=True, text=True)
        out['props'] = (r.stdout or r.stderr).strip()[-400:]
    pred = _REPO / 'nfl/research/ownership/predictions' / f"SC_OWN_ROTATION_2_{cfg['tag']}_{cfg.get('scenario')}.json"
    if pred.exists():
        for cid, c in out['contests'].items():
            if c.get('reconciliation') != 'RECONCILED':
                continue
            gp = _REPO / 'nfl/research/ownership/grades' / f"SC_OWN_ROTATION_2_{cfg['tag']}_{cid}.json"
            gp.parent.mkdir(parents=True, exist_ok=True)
            if gp.exists():
                c['ownership_grade'] = f'EXISTS {gp.relative_to(_REPO)}'
                continue
            r = subprocess.run([PY, 'nfl/research/ownership/grade_sc_own_rotation_2.py', 'grade', '--prediction', str(pred),
                                '--contest-id', cid, '--slate', slug, '--out', str(gp)], cwd=_REPO, capture_output=True, text=True)
            c['ownership_grade'] = (f'PASS {gp.relative_to(_REPO)}' if r.returncode == 0
                                    else f'REFUSED rc={r.returncode}: {(r.stdout + r.stderr)[-300:]}')
    else:
        out['ownership_grade'] = f'NOT_GRADED: no sealed SC-OWN-ROTATION-2 prediction at {pred.relative_to(_REPO)}'
    wk = int(cfg['tag'].rsplit('W', 1)[-1])
    sealp = _REPO / f'nfl/prospective/appearance/APPEARANCE_SUCCESSOR_W{wk}_SEAL.json'
    if sealp.exists() and cfg.get('snaps'):
        import glob as _g
        sched = max(_g.glob(str(_REPO / 'nfl/vintage/schedules.*.csv.gz')), key=lambda f: pathlib.Path(f).stat().st_mtime)
        gout = _REPO / 'nfl/research/appearance/grades' / f"APPEARANCE_SUCCESSOR_W{wk}_{cfg['tag']}.json"
        gout.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([PY, 'nfl/research/appearance/grade_appearance_seal.py', '--seal', str(sealp),
                            '--panel', str(_REPO / 'nfl/derived/USAGE_HISTORY_2021_2026.json'), '--snaps', str(_REPO / cfg['snaps']),
                            '--crosswalk', str(_REPO / 'nfl/postgame/raw/role_audit_history/players_crosswalk.bea61fc25c863150.csv.gz'),
                            '--schedule', sched, '--out', str(gout)], cwd=_REPO, capture_output=True, text=True)
        out['appearance_grade'] = (f'PASS {gout.relative_to(_REPO)}' if r.returncode == 0 else
                                   f'NOT_GRADED rc={r.returncode}: {(r.stdout + r.stderr)[-300:]} (needs the week-{wk} snap counts and panel rows)')
    else:
        out['appearance_grade'] = 'NOT_GRADED: no week seal or no snaps capture'
    pth = P['dir'] / f"POSTGAME_{cfg.get('scenario')}.json"
    pth.write_text(json.dumps(out, indent=1, default=str))
    print(pth)
    print(json.dumps(out['contests'], default=str)[:1500])
    return 0 if all('REFUSED' not in v for v in out['contests'].values()) else 3


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('phase', choices=('run', 'market', 'postgame'))
    ap.add_argument('config')
    ap.add_argument('board', nargs='?')
    ap.add_argument('--mode', choices=('final', 'precompute'), default='final')
    ap.add_argument('--standings', action='append', help='postgame: CONTEST_ID=standings.zip')
    ap.add_argument('--actuals', help='postgame: official actuals JSON for prop settlement')
    a = ap.parse_args()
    try:
        if a.phase == 'run':
            st, bl = run(a.config, a.mode)
            print(st, bl)
            sys.exit(0 if st == 'READY' else 4)
        if a.phase == 'postgame':
            sys.exit(postgame(a.config, a.standings, a.actuals))
        if not a.board:
            raise SlateError('MARKET_NEEDS_BOARD')
        sys.exit(market(a.config, a.board))
    except SlateError as e:
        print(f'BLOCKED[{str(e).split()[0]}] {e}')
        sys.exit(3)
