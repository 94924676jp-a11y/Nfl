#!/usr/bin/env python3.12
"""SC-OWN-ROTATION-2 prelock predictor: sealed, write-once CPT% / FLEX% per player. SHADOW_ONLY.

    python3.12 nfl/research/ownership/predict_sc_own_rotation_2.py \
        --slate TB_DAL_2026W5 --week 5 --kickoff 2026-10-09T00:15:00Z \
        --export   nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/DKEntries_TB_DAL_SHOWDOWN_2026W5.<sha16>.csv \
        --baseline nfl/dfs/salaries/showdown_tb_dal/SHADOW_OFFICIAL_BLEND/SHOWDOWN_TB_DAL_SHADOW_OWNERSHIP.csv \
        --projection nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_PROJECTIONS.csv \
        --depth-chart nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/depth_charts_2026_TB_DAL.9e86fc58e24e74ee.csv \
        --designations nfl/dfs/salaries/showdown_tb_dal/DESIGNATIONS_TB_DAL_2026W5.json \
        [--inactives nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/OFFICIAL_INACTIVES_TB_DAL_2026W5.json] \
        --snaps nfl/dfs/salaries/raw/showdown_atl_no_2026W4/snap_counts_2026.53720f396f9c2bfa.csv \
        --out nfl/research/ownership/predictions/SC_OWN_ROTATION_2_TB_DAL_2026W5.json \
        [--dry-run --label DRY_RUN_IN_SAMPLE]

Loads nfl/research/ownership/SC_OWN_ROTATION_2_FREEZE.json and REFUSES if its content hash, the pre-registration
hash, or any enforced module hash differs (no refit, no edited code). Inputs: the slate's DK export (salaries,
positions, clubs), its FROZEN prelock BLEND shadow ownership CSV (the baseline AND the model's base), OUR frozen
football-only projection (CSV with player, proj_dk_points; or a PROJ.json), the depth-chart capture (latest snapshot
strictly before kickoff is used), designations (OUT = absent), and the official inactive list when it exists. Without
--inactives, absent and `opened` rest on designations only, and the record says DESIGNATIONS_ONLY.

The baseline must carry no mass on an absent player (BASELINE_MASS_ON_ABSENT): build the BLEND with the same absent
list (the OFFICIAL scenario, after inactives) before calling this.

Writes ONE sealed JSON: seal_sha256 = sha256(json.dumps(body, sort_keys=True, default=str)), the convention of
nfl/field/showdown_field_archive._verify_seal; file mode 0444; never overwritten (PREDICTION_EXISTS). Without
--dry-run it refuses at or after --kickoff (PREDICTION_AT_OR_AFTER_KICKOFF), refuses a development slate, and refuses
a slate whose lock does not postdate the freeze. A --dry-run record is MODE DRY_RUN and is never graded as evidence.
Nothing here is read by lineup selection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.ownership import sc_own_rotation_2 as M  # noqa: E402

RotationError = M.RotationError
need = M.need


def seal(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def verify_seal(doc):
    if 'seal_sha256' not in doc:
        return False
    body = {k: v for k, v in doc.items() if k != 'seal_sha256'}
    return seal(body) == doc['seal_sha256']


def is_development(slate):
    return any(str(slate).upper().startswith(d) for d in M.DEVELOPMENT_SLATES)


def _inp(p):
    return {'path': M.rel(p), 'sha256': M.sha_file(p)}


def predict(slate, week, kickoff, export, baseline, projection, depth_chart, designations, snaps, out,
            inactives=None, dry_run=False, label=None, freeze_path=M.FREEZE_PATH, now=None):
    t_now = now or M.now_utc()
    ko = M.parse_ts(kickoff)
    mode = 'DRY_RUN' if dry_run else 'PRELOCK'
    if not dry_run:
        need(t_now < ko, 'PREDICTION_AT_OR_AFTER_KICKOFF', f'{t_now.isoformat()} >= {kickoff}')
        need(not is_development(slate), 'DEVELOPMENT_SLATE', f'{slate} is in {M.DEVELOPMENT_SLATES}; use --dry-run')
    else:
        need(label, 'DRY_RUN_NEEDS_LABEL', 'a dry run must say what it is (e.g. DRY_RUN_IN_SAMPLE)')
    out = pathlib.Path(out)
    need(not out.exists(), 'PREDICTION_EXISTS', M.rel(out))
    fz, fz_sha = M.load_freeze(freeze_path)
    covered = M.parse_ts(fz['written_at']) < ko
    if not dry_run:
        need(covered, 'FREEZE_NOT_BEFORE_LOCK', f"freeze {fz['written_at']} vs lock {kickoff}: slate not covered")
    for p in (export, baseline, projection, depth_chart, designations, snaps):
        need(p and pathlib.Path(p).is_file() and pathlib.Path(p).stat().st_size > 0, 'INPUT_MISSING_OR_EMPTY', str(p))
    if inactives is not None:
        need(pathlib.Path(inactives).is_file() and pathlib.Path(inactives).stat().st_size > 0,
             'INPUT_MISSING_OR_EMPTY', str(inactives))
    pool, _ = M.load_pool(export)
    teams = {v['team'] for v in pool.values()}
    base = M.load_baseline(baseline)
    proj = M.load_projection(projection)
    des = M.load_designations(designations)
    ina = M.load_names(inactives) if inactives is not None else []
    absent = M.absent_set(pool, ina, des)
    depth = M.load_depth(depth_chart, teams, ko)
    feat = M.build_features(slate, pool, base, proj, depth, absent, snaps, int(week))
    w = fz['coefficients']['vector']
    P = M.predict(feat, pool, w)
    rows = []
    for n in sorted(feat['rows']):
        r = feat['rows'][n]
        rows.append({'name': n, 'team': r['team'], 'position': r['position'], 'flex_salary': r['flex_salary'],
                     'cpt_salary': r['cpt_salary'], 'active': r['active'], 'bucket': r['bucket'],
                     'in_universe': r['in_universe'],
                     'candidate_cpt_pct': P['candidate']['cpt'][n], 'candidate_flex_pct': P['candidate']['flex'][n],
                     'candidate_cpt_pct_smoothed': P['candidate_smoothed']['cpt'][n],
                     'candidate_flex_pct_smoothed': P['candidate_smoothed']['flex'][n],
                     'baseline_cpt_pct': P['baseline']['cpt'][n], 'baseline_flex_pct': P['baseline']['flex'][n],
                     'baseline_cpt_pct_smoothed': P['baseline_smoothed']['cpt'][n],
                     'baseline_flex_pct_smoothed': P['baseline_smoothed']['flex'][n],
                     'features': {k: r.get(k) for k in ('proj_pts', 'proj_state', 'value_z', 'salary_rank_at_pos',
                                                        'depth_rank', 'role_depth_inv', 'role_snap_share', 'opened',
                                                        'opened_by', 'cheap_active', 'log_base_cpt', 'log_base_flex')}})
    tot = {f'candidate_{s}': sum(P['candidate'][s].values()) for s in M.SLOTS}
    tot.update({f'candidate_{s}_smoothed': sum(P['candidate_smoothed'][s].values()) for s in M.SLOTS})
    tot['max_slot_share'] = max(max(P['candidate'][s].values()) for s in M.SLOTS)
    t_write = M.now_utc() if now is None else now
    if not dry_run:
        need(t_write < ko, 'PREDICTION_AT_OR_AFTER_KICKOFF', f'{t_write.isoformat()} >= {kickoff} (at write)')
    body = {
        'ARTIFACT': 'SC_OWN_ROTATION_2_PREDICTION', 'candidate_id': M.CANDIDATE_ID, 'LABEL': M.LABEL,
        'MODE': mode, 'run_label': label or 'PRELOCK',
        'EVIDENCE_STATUS': ('PROSPECTIVE_PRELOCK_RECORD (scored only after the full field is archived; one of the '
                            'N >= 4 slates the bar needs)' if not dry_run else
                            f'{label}: NOT EVIDENCE (dry run; never graded as evidence)'),
        'NOT_A_FOOTBALL_INPUT': True, 'INFLUENCES_SELECTION': False,
        'slate': slate, 'week': int(week), 'kickoff': ko.isoformat(),
        'freeze': {'path': M.rel(freeze_path), 'sha256': fz_sha, 'content_sha256': fz['content_sha256'],
                   'written_at': fz['written_at'], 'covers_this_slate': covered},
        'prereg_sha256': fz['prereg']['sha256'],
        'inputs': {'export': _inp(export), 'baseline_blend': _inp(baseline), 'projection': _inp(projection),
                   'depth_chart': _inp(depth_chart), 'designations': _inp(designations), 'snaps': _inp(snaps),
                   'inactives': _inp(inactives) if inactives is not None else 'NOT_PROVIDED'},
        'absent_basis': 'OFFICIAL_INACTIVES_AND_DESIGNATIONS_OUT' if inactives is not None else 'DESIGNATIONS_OUT_ONLY',
        'pool_sha256': M.sha_obj(pool),
        'declared_features': feat['declared'],
        'universe_lineups': P['universe_lineups'],
        'totals_check': tot,
        'smoothing': {'floor_pct': M.FLOOR_PCT, 'inactive': 0.0, 'take': 'proportional within slot',
                      'use': 'log score only; MAE and bias use the raw marginals'},
        'players': rows,
        'written_at': t_write.isoformat(),
    }
    body_sealed = dict(body)
    body_sealed['seal_sha256'] = seal(body)
    out.parent.mkdir(parents=True, exist_ok=True)
    M.write_once(out, body_sealed)
    return body_sealed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--slate', required=True)
    ap.add_argument('--week', required=True, type=int)
    ap.add_argument('--kickoff', required=True)
    ap.add_argument('--export', required=True)
    ap.add_argument('--baseline', required=True, help='frozen prelock BLEND *_SHADOW_OWNERSHIP.csv')
    ap.add_argument('--projection', required=True, help='our frozen football-only projection (CSV or PROJ.json)')
    ap.add_argument('--depth-chart', required=True)
    ap.add_argument('--designations', required=True)
    ap.add_argument('--inactives')
    ap.add_argument('--snaps', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--freeze', default=str(M.FREEZE_PATH))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--label')
    a = ap.parse_args(argv)
    try:
        d = predict(a.slate, a.week, a.kickoff, a.export, a.baseline, a.projection, a.depth_chart, a.designations,
                    a.snaps, a.out, inactives=a.inactives, dry_run=a.dry_run, label=a.label, freeze_path=a.freeze)
    except RotationError as e:
        print(f'REFUSED[{e.code}] {e}')
        return 3
    print(a.out, d['MODE'], d['seal_sha256'], json.dumps(d['totals_check']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
