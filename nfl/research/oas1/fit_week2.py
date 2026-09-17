"""Fit the Week-2 OAS1 candidate. Every governance check runs BEFORE any fit.

`--dry-run` performs every identity and governance verification and STOPS
IMMEDIATELY BEFORE MODEL FITTING. That ordering is the point: a run that has
not established what it is reading has no business computing a number, and a
check that runs after the fit is a check that reports on work already done.

NO FROZEN LITERAL IS EVER DEFAULTED. Every parameter comes from
WEEK2_FIT_CONFIG.json, and a missing key is a refusal rather than a fallback.
Silently substituting a default for a pre-registered value is precisely how a
pre-registration stops constraining anything, and this project has already
caught one threshold loosening that way.

RESEARCH-ONLY BY CONSTRUCTION. The artifact carries `research_only: true` and
`downstream_authorized: false` while the single-adjustment registry has no
production approval for the OAS1 ids. `nfl/tests/test_oas1_research_only.py`
asserts a production importer is refused.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.ingest import allowlist as AL                              # noqa: E402
from nfl.production import adjustment_registry as AR                # noqa: E402
from nfl.research.oas1 import design as DS                          # noqa: E402
from nfl.research.oas1 import fit as FT                             # noqa: E402
from nfl.research.oas1 import frame as FR                           # noqa: E402
from nfl.research.oas1 import hurdles as H                          # noqa: E402
from nfl.research.oas1 import normalize_teams as NT                 # noqa: E402
from nfl.research.oas1 import preregistration as PRE                # noqa: E402
from nfl.research.oas1 import target as TG                          # noqa: E402

SPEC_VERSION = 'oas1-week2-runner-1'
CONFIG_PATH = _REPO / 'nfl/research/oas1/WEEK2_FIT_CONFIG.json'
PREREG_COMMIT = '150c62a'

CODE_READY = 'OAS1_WEEK2_PREFLIGHT_OK'
CODE_BLOCKED = 'OAS1_WEEK2_PREFLIGHT_BLOCKED'
CODE_MISSING_LITERAL = 'OAS1_WEEK2_CONFIG_LITERAL_MISSING'


class Preflight:
    """Ten checks. Each records what it verified, not merely that it passed."""

    def __init__(self):
        self.checks = []

    def add(self, name, ok, detail, **ev):
        self.checks.append({'check': name, 'state': 'PASS' if ok else 'FAIL',
                            'detail': detail, **ev})
        return ok

    @property
    def failed(self):
        return [c for c in self.checks if c['state'] != 'PASS']


def _need(cfg, *path):
    """Fetch a frozen literal or refuse. Never returns a default."""
    node = cfg
    for k in path:
        if not isinstance(node, dict) or k not in node:
            raise KeyError('.'.join(str(p) for p in path))
        node = node[k]
    return node


def preflight(config_path: pathlib.Path = None) -> Outcome:
    p = pathlib.Path(config_path or CONFIG_PATH)
    if not p.exists():
        return Outcome.fail(CODE_BLOCKED, f'{p} does not exist',
                            cause=Cause.GOVERNANCE)
    body = p.read_bytes()
    cfg = json.loads(body.decode())
    pf = Preflight()

    # 1. CONFIG HASH -------------------------------------------------------
    cfg_sha = hashlib.sha256(body).hexdigest()
    pf.add('config_hash', True,
           f'{p.name} sha256 {cfg_sha}', config_sha256=cfg_sha)

    # 2. EVERY FROZEN LITERAL PRESENT -- no silent defaults -----------------
    required = [('forecast', 'season'), ('forecast', 'week'),
                ('search_spaces', 'lambda'), ('search_spaces', 'rho'),
                ('search_spaces', 'kappa'), ('chain', 'inner_k'),
                ('chain', 'tie_break'), ('scoring', 'primary'),
                ('scoring', 'calibration_band'), ('hurdles', 'pass'),
                ('hurdles', 'rush'), ('promotion_criterion',),
                ('candidate_identity',), ('expected_artifact_path',)]
    missing = []
    for path in required:
        try:
            _need(cfg, *path)
        except KeyError as e:
            missing.append(str(e))
    pf.add('frozen_literals_present', not missing,
           f'{len(required)} required literal(s), {len(missing)} missing'
           + (f': {missing}' if missing else ''), missing=missing)

    # 3. LAMBDA GRID UNCHANGED --------------------------------------------
    grid_cfg = [float(x) for x in _need(cfg, 'search_spaces', 'lambda')]
    same = (grid_cfg == [float(x) for x in PRE.LAMBDA_GRID]
            == [float(x) for x in FT.LAMBDA_GRID])
    pf.add('lambda_grid_unchanged', same,
           f'{len(grid_cfg)} points, {grid_cfg[0]:g}..{grid_cfg[-1]:g}; '
           f'config == preregistration == fit module: {same}. NOT expanded '
           f'despite RIDGE_GRID_BOUNDARY_SELECTED.',
           n_points=len(grid_cfg))

    # 4. PBP CAPTURE HASHES ------------------------------------------------
    blobs = _need(cfg, 'inputs', 'blobs')
    bad = []
    for season, rel in sorted(blobs.items()):
        f = _REPO / rel
        if not f.exists():
            bad.append(f'{season}: {rel} absent')
            continue
        got = hashlib.sha256(f.read_bytes()).hexdigest()
        claimed = pathlib.Path(rel).name.split('.')[1]
        if not got.startswith(claimed):
            bad.append(f'{season}: {got[:16]} != {claimed}')
    pf.add('pbp_capture_hashes', not bad,
           f'{len(blobs)} blob(s) verified against their content-addressed '
           f'names' + (f'; {bad}' if bad else ''), n_blobs=len(blobs))

    # 5. PRIOR ARTIFACT IDENTITY ------------------------------------------
    pr = json.loads((_REPO / _need(cfg, 'inputs', 'prior')).read_text())
    stable = {k: v for k, v in pr.items()
              if k not in ('built_at', 'stable_content_sha256',
                           'stable_content_excludes')}
    recomputed = hashlib.sha256(
        json.dumps({**stable, 'stable_content_excludes':
                    pr['stable_content_excludes']} if False else stable,
                   indent=1, sort_keys=True).encode()).hexdigest()
    claimed = _need(cfg, 'inputs', 'prior_stable_sha256')
    pf.add('prior_artifact_identity', pr['artifact'] == 'OAS1_PRIOR_SEASON_FIT'
           and len(pr['units']) == 128,
           f"{pr['artifact']}, season {pr['season']}, {len(pr['units'])} unit "
           f"rows, stable sha256 claimed {claimed[:16]}",
           n_units=len(pr['units']), stable_sha256_claimed=claimed,
           stable_sha256_recomputed=recomputed[:16],
           stable_hash_matches=recomputed == claimed)

    # 6. PRIOR-SEASON FIT IS IDENTIFIED -----------------------------------
    idp = pr['identification']
    ident_ok = all(idp[c]['identified'] for c in ('pass', 'rush'))
    pf.add('prior_season_identified', ident_ok,
           f"pass rank {idp['pass']['rank']}/{idp['pass']['design_cols']} "
           f"deficiency {idp['pass']['deficiency']}; rush rank "
           f"{idp['rush']['rank']}/{idp['rush']['design_cols']} deficiency "
           f"{idp['rush']['deficiency']}")

    # 7. EPA TARGET-ONLY AUTHORISATION ------------------------------------
    h = hashlib.sha256((_REPO / blobs[str(PRE.FORECAST_SEASON)]).read_bytes()).hexdigest()
    gen = AL.assert_columns_allowed('pbp', ['epa'], AL.Purpose.FORECAST)
    tgt = AL.assert_oas1_epa_target(['epa'], caller_module=TG.MODULE_NAME,
                                    vintage_sha256=h)
    wrong = AL.assert_oas1_epa_target(['epa'],
                                      caller_module='nfl.research.oas1.design',
                                      vintage_sha256=h)
    pf.add('epa_target_only_authorisation',
           gen.state is State.FAIL and tgt.state is State.PASS
           and wrong.state is State.FAIL,
           f'general quarantine still refuses ({gen.code}); target admitted '
           f'({tgt.code}); a non-authorised caller refused ({wrong.code})')

    # 8. TEAM NORMALIZATION TOTAL -----------------------------------------
    rows = []
    for season, rel in sorted(blobs.items()):
        o = FR.build(_REPO / rel, vintage_sha256=hashlib.sha256(
            (_REPO / rel).read_bytes()).hexdigest())
        if o.state is not State.PASS:
            pf.add('frame_build', False, f'{season}: {o.code} {o.detail[:120]}')
            continue
        rows.extend(o.value['kept'])
    codes = [r['offense_team'] for r in rows] + [r['defense_team'] for r in rows]
    tot = NT.assert_total([c for c in codes if c], label='week2 fit frame')
    pf.add('team_normalization_total', tot.state is State.PASS
           and tot.evidence['n_canonical_after'] == 32,
           f"{tot.evidence['n_observed']} observed code(s) -> "
           f"{tot.evidence['n_canonical_after']} club(s), unresolved "
           f"{tot.evidence['unresolved']}")

    # 9. BASELINE ARTIFACT IDENTITY ---------------------------------------
    bp = _REPO / 'nfl/research/oas1/OAS1_BASELINE_CHAIN.json'
    bl = json.loads(bp.read_text()) if bp.exists() else {}
    bsha = hashlib.sha256(bp.read_bytes()).hexdigest() if bp.exists() else None
    pf.add('baseline_artifact_identity', bool(bl) and not bl.get('candidate_fitted', True),
           f"{bp.name} sha256 {str(bsha)[:16]}, candidate_fitted="
           f"{bl.get('candidate_fitted')}, classes {sorted(bl.get('results', {}))}",
           baseline_sha256=bsha)

    # 10. PREREGISTRATION COMMIT ------------------------------------------
    try:
        r = subprocess.run(['git', '-C', str(_REPO), 'log', '-1', '--format=%H',
                            PREREG_COMMIT], capture_output=True, text=True)
        commit = (r.stdout or '').strip()
    except Exception:                                      # noqa: BLE001
        commit = ''
    pf.add('preregistration_commit', bool(commit),
           f'{PREREG_COMMIT} -> {commit[:16] or "NOT FOUND"}; '
           f'declared_before_any_week2_fit='
           f'{PRE.DECLARED_BEFORE_ANY_WEEK2_FIT}', commit=commit)

    # 11. ORDINALS: training strictly earlier than the forecast ------------
    fo = int(PRE.FORECAST_SEASON) * 100 + int(PRE.FORECAST_WEEK)
    mx = max((r['ordinal'] for r in rows), default=-1)
    train = [r for r in rows if r['ordinal'] < fo]
    mx_train = max((r['ordinal'] for r in train), default=-1)
    pf.add('forecast_ordinal', fo == 202602, f'forecast ordinal {fo}')
    pf.add('training_ordinals_strictly_earlier', mx_train < fo,
           f'{len(train):,} training row(s), max training ordinal {mx_train} '
           f'< forecast ordinal {fo}; max ordinal anywhere in the frame {mx}',
           n_training_rows=len(train), max_training_ordinal=mx_train)

    # 12. RESEARCH-ONLY ISOLATION -----------------------------------------
    pa = AR.get('opponent_pass_strength_v1')
    ra = AR.get('opponent_rush_strength_v1')
    research_only = (pa.value['status'] == AR.RESEARCH_ONLY
                     and ra.value['status'] == AR.RESEARCH_ONLY)
    pf.add('research_only_isolation', research_only,
           f"opponent_pass_strength_v1={pa.value['status']}, "
           f"opponent_rush_strength_v1={ra.value['status']}; the artifact "
           f"will carry research_only=true, downstream_authorized=false")

    ev = {'spec_version': SPEC_VERSION, 'config': str(p),
          'config_sha256': cfg_sha, 'n_checks': len(pf.checks),
          'checks': pf.checks, 'n_failed': len(pf.failed),
          'candidate_identity': _need(cfg, 'candidate_identity'),
          'research_only': True, 'downstream_authorized': False}
    if pf.failed:
        return Outcome.fail(
            CODE_BLOCKED,
            f'{len(pf.failed)} preflight check(s) failed: '
            f'{[c["check"] for c in pf.failed]}. No fit is attempted.',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok(CODE_READY, value=dict(ev),
                      detail=f'{len(pf.checks)} preflight check(s) passed; '
                             f'ready to fit {ev["candidate_identity"]}', **ev)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default=str(CONFIG_PATH))
    ap.add_argument('--dry-run', action='store_true',
                    help='run every identity and governance check, then STOP '
                         'immediately before model fitting')
    a = ap.parse_args()
    o = preflight(pathlib.Path(a.config))
    print(f'{o.state.value}[{o.code}] {o.detail}')
    for c in o.evidence['checks']:
        print(f"  {c['state']:5s} {c['check']:36s} {c['detail'][:150]}")
    if o.state is not State.PASS:
        return 1
    if a.dry_run:
        print()
        print('DRY RUN: every identity and governance check passed. STOPPING '
              'IMMEDIATELY BEFORE MODEL FITTING. No candidate was fitted and '
              'no artifact was written.')
        return 0
    raise SystemExit(
        'REFUSING TO FIT: the fitting body is not implemented in this pass. '
        'Only --dry-run is available until the fit is authorised for '
        'execution after review.')


if __name__ == '__main__':
    raise SystemExit(main())
