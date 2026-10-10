"""Availability scenarios on a frozen research state. RESEARCH ONLY: production and the frozen base are never written.

    python3.12 run_scenarios.py BASE_STATE.json SPEC.json OUT_DIR LABEL [--sims 2000] [--keep-worlds DIR]

A scenario is the base state with named players set to REPORTED_OUT_UNVERIFIED (tier SCENARIO) and, when the
scenario names one, a quarterback promoted to depth rank 1 with the other QBs re-ranked behind him. Nothing else is
edited: who replaces an absent receiver or back is decided by the engine's own role layer (the committed
absent-rank fix), not by this script. The label BASE runs the base state unchanged, as a reproducibility check.

Each run writes STATE.json, PROJ.json.gz, ROLE_STATE.json and RUN_OUTCOME.json into OUT_DIR/LABEL. The simulated
worlds go to --keep-worlds when given (they are large and re-derivable), never into the repository.
"""
import argparse
import copy
import gzip
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))


def apply(state, sc):
    st = copy.deepcopy(state)
    P = st['players']
    by_name = {}
    for k, p in P.items():
        by_name.setdefault(p['name'], []).append(k)
    for name in sc.get('out', []):
        ks = by_name.get(name, [])
        if len(ks) != 1:
            raise SystemExit(f'SCENARIO_PLAYER_NOT_UNIQUE: {name!r} matches {len(ks)} rows')
        av = dict(P[ks[0]].get('current_availability') or {})
        av.update(status='REPORTED_OUT_UNVERIFIED', tier='SCENARIO',
                  resolution={'SCENARIO': sc['label'], 'WHY': sc.get('why', '')})
        P[ks[0]]['current_availability'] = av
    for name in sc.get('active', []):
        ks = by_name.get(name, [])
        if len(ks) != 1:
            raise SystemExit(f'SCENARIO_PLAYER_NOT_UNIQUE: {name!r} matches {len(ks)} rows')
    if sc.get('qb_starts'):
        name = sc['qb_starts']
        k = by_name[name][0]
        club = P[k]['team']
        qbs = [kk for kk, p in P.items() if p['team'] == club and p['position'] == 'QB']
        out = {by_name[n][0] for n in sc.get('out', []) if n in by_name}
        rest = sorted((kk for kk in qbs if kk != k and kk not in out), key=lambda kk: P[kk].get('depth_rank') or 99)
        order = [k] + rest + sorted(out & set(qbs))
        for r, kk in enumerate(order, start=1):
            P[kk]['depth_rank'] = r
            P[kk]['depth_chart_rank'] = r
    st['SCENARIO'] = {'label': sc['label'], 'out': sc.get('out', []), 'qb_starts': sc.get('qb_starts'),
                      'why': sc.get('why', ''), 'base_as_of': state.get('as_of'),
                      'IS_NOT': 'a forecast of whether the player plays; it is the projection if he does not'}
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('base_state')
    ap.add_argument('spec')
    ap.add_argument('out_dir')
    ap.add_argument('label')
    ap.add_argument('--sims', type=int, default=2000)
    ap.add_argument('--keep-worlds')
    a = ap.parse_args()
    base = json.loads(pathlib.Path(a.base_state).read_text())
    specs = {s['label']: s for s in json.loads(pathlib.Path(a.spec).read_text())['scenarios']}
    sc = specs[a.label] if a.label != 'BASE' else {'label': 'BASE'}
    out = (pathlib.Path(a.out_dir) / a.label).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f'REFUSED: {out} is not empty')
    out.mkdir(parents=True, exist_ok=True)
    st = base if a.label == 'BASE' else apply(base, sc)
    (out / 'STATE.json').write_text(json.dumps(st, indent=1, default=str) + '\n')
    from nfl.tools import classic_slate_run as CR, role_state as RS, proj_v1 as PV
    wdir = pathlib.Path(a.keep_worlds).resolve() / a.label if a.keep_worlds else out
    wdir.mkdir(parents=True, exist_ok=True)
    CR.paths = lambda s: {'state': out / 'STATE.json', 'proj': out / 'PROJ.json', 'draws': wdir / 'DRAWS.json',
                          'worlds': wdir / 'WORLDS.npz'}
    RS.OUT = PV.ROLE = out / 'ROLE_STATE.json'
    o = CR.run('2026W5', n_sims=a.sims)
    import hashlib
    import subprocess
    head = subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '--', 'nfl/tools', 'nfl/sim',
                            'nfl/production'], capture_output=True, text=True).stdout.strip()
    receipt = {'scenario_id': a.label, 'code_commit': head, 'engine_code_dirty': bool(dirty),
               'engine_dirty_files': dirty.splitlines()[:20],
               'base_state': a.base_state, 'base_state_sha256': hashlib.sha256(pathlib.Path(a.base_state).read_bytes()).hexdigest(),
               'cutoff_as_of': base.get('as_of'), 'evidence_packet': (base.get('official_inactives') or {}).get('packet_id'),
               'seed_policy': 'engine per-game seeds (DRAWS.per_game[*].seed), identical across scenarios',
               'n_sims': a.sims, 'injury_state_probability': 'NOT_ESTIMATED',
               'labels': {'research_only': True, 'legal_pool_ready': False, 'game_day_state_ready': False,
                          'upload_ready': False}}
    (out / 'RUN_OUTCOME.json').write_text(json.dumps({'state': o.state.value, 'code': o.code, 'detail': o.detail,
                                                      'scenario': st.get('SCENARIO'), 'receipt': receipt,
                                                      'evidence': o.evidence}, indent=1, default=str))
    pj = out / 'PROJ.json'
    if pj.exists():
        with open(pj, 'rb') as f, gzip.GzipFile(out / 'PROJ.json.gz', 'wb', mtime=0) as g:
            shutil.copyfileobj(f, g)
        pj.unlink()
    print(a.label, o.state.value, o.code, o.detail)


if __name__ == '__main__':
    main()
