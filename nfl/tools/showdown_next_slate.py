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
     "contests": {"<id>": {"prize_pool": 100000, "entry_fee": 0.5, "max_entries": 150, "field_size": 237812}}}

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
                                 'confirmed_starters', 'depth_chart') if cfg.get(k)}
    absent = [f'{k}={v}' for k, v in files.items() if not (_REPO / v).is_file() or (_REPO / v).stat().st_size == 0]
    if absent:
        raise SlateError(f'INPUT_FILE_MISSING_OR_EMPTY {absent}')
    for cid, c in cfg['contests'].items():
        bad = [k for k in ('prize_pool', 'entry_fee', 'max_entries') if not isinstance(c.get(k), (int, float))]
        if bad:
            raise SlateError(f'CONTEST_FIELDS_MISSING {cid} {bad}')
    cfg['scenario'] = cfg.get('scenario') or ('OFFICIAL' if mode == 'final' else 'PRECOMPUTE')
    return cfg, {k: {'path': v, 'sha256': _sha(_REPO / v)} for k, v in files.items()}


def env_for(cfg, cfg_path):
    e = dict(os.environ)
    e.update({'SHOWDOWN_TAG': cfg['tag'], 'SHOWDOWN_SLATE_CONFIG': str(pathlib.Path(cfg_path).resolve()),
              'SHOWDOWN_RAW_DIR': str((_REPO / cfg['export']).parent)})
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
    out['ready_eligible'] = mode == 'final' and official and not cfg.get('rehearsal')
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
    L = Ledger(P['dir'] / f'RUN_LEDGER_{scen}.json')
    L.add('DISCOVER', 'PASS', tag=cfg['tag'], scenario=scen, mode=mode, inputs=hashes,
          REHEARSAL=bool(cfg.get('rehearsal')))
    try:
        return _run_body(cfg, cfg_path, mode, hashes, P, scen, sd, pre, L)
    except SlateError as e:
        L.add('REFUSED', str(e).split()[0], detail=str(e))
        raise


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

    cmd = [PY, 'nfl/tools/showdown_tonight.py', _REPO / cfg['export'], '--scenario', scen, '--tag', cfg['tag'],
           '--designations', _REPO / cfg['designations'], '--confirmed-starters', _REPO / cfg['confirmed_starters'],
           '--starter-tier', cfg['starter_tier'], '--depth-chart', _REPO / cfg['depth_chart']]
    if cfg.get('official_inactives'):
        cmd += ['--official-inactives', _REPO / cfg['official_inactives']]
    rc, tail = _run(cmd, env, 'tonight')
    up = sd / f'{pre}_DK_UPLOAD.csv'
    if rc != 0 or not up.is_file() or up.stat().st_size == 0:
        L.add('PROJECT_SIMULATE_BUILD', 'FAIL', rc=rc, tail=tail)
        raise SlateError(f'PIPELINE_FAILED rc={rc} upload_present={up.is_file()}')
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
            sizes += ['--contest', f'{cid}={int(n)}:{int(c["max_entries"])}']
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
    L.add('SHADOWS_NON_BLOCKING', 'RECORDED', **shadows)

    # ---- SEAL PROP DISTRIBUTIONS (blocking for the market phase, not for the DFS upload)
    mk = market_dir(cfg)
    rc, tail = _run([PY, 'nfl/market/showdown_prop_shadow.py', 'seal', '--scenario-dir', sd, '--out-dir', mk,
                     '--slate', cfg['tag'].split('_2026')[0], '--kickoff', cfg['kickoff_utc']], env, 'seal')
    L.add('SEAL_PROPS', 'PASS' if rc == 0 else 'FAIL', out=str(mk.relative_to(_REPO)), tail=tail[-300:])

    return final_verify(cfg, cfg_path, hashes, ver, L, P, sd, pre, env, prop_seal_ok=rc == 0)


# ---------------------------------------------------------------- FINAL VERIFY
def final_verify(cfg, cfg_path, hashes, ver, L, P, sd, pre, env, prop_seal_ok):
    blockers = []
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
    elif not ver.get('ready_eligible'):
        blockers.append('INACTIVES_NOT_OFFICIALLY_VERIFIED_OR_PRECOMPUTE_MODE')
    if not prop_seal_ok:
        blockers.append('PROP_SEAL_FAILED (market phase unavailable; DFS unaffected)')
    if _now() >= _ts(cfg['kickoff_utc']):
        blockers.append('FINAL_VERIFY_AFTER_KICKOFF')
    state = 'READY' if not blockers else 'NOT_READY'
    L.add('FINAL_VERIFY', state, upload_sha256=want, reproduced_sha256=got, blockers=blockers,
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
