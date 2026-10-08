#!/usr/bin/env python3.12
"""Matched-input, matched-seed regression comparison of two Showdown scenario directories. Read-only.

    python3.12 nfl/tools/showdown_regression_compare.py BASELINE_DIR CANDIDATE_DIR [--out REPORT.json]

Owner requirement 2026-10-08 (Showdown performance preservation): a validation-only or execution/infrastructure
repair must leave valid numerical output byte-identical; any difference must be explained before release.

Compared, each reported IDENTICAL or DIFFERENT with what moved:
  projections     every projection row, and the QB/RB/WR/TE/K/DST points by position
  simulation      every player's draws, world points, club worlds, DST components, the per-world stat lines
  correlations    the published correlation board, and the pairwise correlations recomputed from the draws
  portfolio       final lineups, exposures, captain exposures, every upload file
  legality        verifier violations and illegal lineups from the final board / audit
  uniqueness      distinct lineups per contest and the largest duplicate count
  state           the slate state with run-binding metadata removed (scenario_identity, starter evidence)

Metadata that a run legitimately stamps differently (timestamps, run ids, lineage, input paths of the scenario
directory itself) is excluded from the comparison and listed as excluded, never silently.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

VOLATILE = {'built_at_utc', 'built_at', 'built_at_unix', 'generated_at_utc', 'written_at', '_lineage', 'completed_at',
            'projection_sha256', 'state_sha256'}
BINDING = {'scenario_identity', 'evidence'}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _strip(o, drop):
    if isinstance(o, dict):
        return {k: _strip(v, drop) for k, v in o.items() if k not in drop}
    if isinstance(o, list):
        return [_strip(v, drop) for v in o]
    return o


def _one(d, pat):
    hits = sorted(pathlib.Path(d).glob(pat))
    return hits[0] if hits else None


def _csv(p):
    return list(csv.DictReader(open(p))) if p else None


def compare(a, b):
    a, b = pathlib.Path(a), pathlib.Path(b)
    out = {'ARTIFACT': 'SHOWDOWN_REGRESSION_COMPARISON', 'baseline': str(a), 'candidate': str(b),
           'excluded_volatile_keys': sorted(VOLATILE), 'excluded_binding_keys_in_state': sorted(BINDING), 'checks': {}}
    C = out['checks']

    def put(name, same, **kw):
        C[name] = {'IDENTICAL': bool(same), **kw}

    # projections
    pa, pb = (json.loads(_one(x, 'SHOWDOWN_*_PROJ.json').read_text()) for x in (a, b))
    ra, rb = (_strip(p['rows'], VOLATILE) for p in (pa, pb))
    moved = sorted(k for k in set(ra) | set(rb) if ra.get(k) != rb.get(k))
    put('projection_rows', not moved, n_rows=len(ra), moved=[(ra.get(k) or rb.get(k)).get('name') for k in moved][:20])
    bypos = lambda rows: {pos: round(sum((r.get('dk_points') or 0) for r in rows.values() if r.get('position') == pos), 6)  # noqa: E731
                          for pos in ('QB', 'RB', 'WR', 'TE', 'K', 'DST')}
    put('projection_points_by_position', bypos(ra) == bypos(rb), baseline=bypos(ra), candidate=bypos(rb))
    rest_a, rest_b = (_strip({k: v for k, v in p.items() if k != 'rows'}, VOLATILE) for p in (pa, pb))
    put('projection_header', rest_a == rest_b,
        differing_keys=sorted(k for k in set(rest_a) | set(rest_b) if rest_a.get(k) != rest_b.get(k)))
    # simulation
    da, db = (json.loads(_one(x, 'SHOWDOWN_*_DRAWS.json').read_text()) for x in (a, b))
    dmoved = sorted(k for k in set(da['draws']) | set(db['draws']) if da['draws'].get(k) != db['draws'].get(k))
    put('player_draws', not dmoved, n_players=len(da['draws']), n_sims=da.get('n_sims'), seed=[da.get('seed'), db.get('seed')],
        moved=dmoved[:20])
    for k in ('world_points', 'club_worlds', 'club_scoring_worlds', 'dst_components', 'qb_interceptions', 'kickers'):
        put(f'sim_{k}', da.get(k) == db.get(k))
    wa, wb = _one(a, 'SHOWDOWN_*_WORLDS.npz'), _one(b, 'SHOWDOWN_*_WORLDS.npz')
    try:
        from nfl.tools import classic_slate_run as CR
        import numpy as np
        sa, qa, ma = CR.load_worlds(wa)
        sb, qb, mb = CR.load_worlds(wb)
        put('world_stat_lines', ma['keys'] == mb['keys'] and np.array_equal(sa, sb) and np.array_equal(qa, qb),
            shape=list(sa.shape))
        # pairwise correlations recomputed from the draws
        keys = sorted(set(da['draws']) & set(db['draws']))
        A = np.array([da['draws'][k] for k in keys], float)
        B = np.array([db['draws'][k] for k in keys], float)
        with np.errstate(invalid='ignore', divide='ignore'):
            ca, cb = np.corrcoef(A), np.corrcoef(B)
        put('player_correlations_from_draws', np.array_equal(np.nan_to_num(ca), np.nan_to_num(cb)),
            max_abs_diff=float(np.nanmax(np.abs(ca - cb))) if ca.shape == cb.shape else None)
    except Exception as e:  # noqa: BLE001
        put('world_stat_lines', False, error=f'{type(e).__name__}: {e}')
    # published boards and portfolio
    for name, pat in (('correlation_board', '*_CORRELATION.csv'), ('projections_csv', '*_PROJECTIONS.csv'),
                      ('simulation_summary', '*_SIMULATION_SUMMARY.csv'), ('final_lineups', '*_FINAL_LINEUPS.csv'),
                      ('exposures', '*_EXPOSURES.csv'), ('cpt_exposures', '*_CPT_EXPOSURES.csv'),
                      ('stack_board', '*_STACK_BOARD.csv'), ('game_script_board', '*_GAME_SCRIPT_BOARD.csv'),
                      ('cpt_board', '*_CPT_BOARD.csv'), ('candidates', '*_CANDIDATES.csv')):
        x, y = _one(a, pat), _one(b, pat)
        put(name, bool(x and y) and _sha(x) == _sha(y), baseline=_sha(x)[:16] if x else None,
            candidate=_sha(y)[:16] if y else None)
    ups = sorted(p.name for p in a.glob('*_DK_UPLOAD*.csv'))
    put('upload_files', ups == sorted(p.name for p in b.glob('*_DK_UPLOAD*.csv'))
        and all(_sha(a / n) == _sha(b / n) for n in ups), files={n: [_sha(a / n)[:16], _sha(b / n)[:16] if (b / n).exists() else None] for n in ups})
    # legality and uniqueness
    fa, fb = (json.loads(_one(x, '*_FINAL_BOARD.json').read_text()) for x in (a, b))
    put('legality', fa.get('VERIFIER_VIOLATIONS') == fb.get('VERIFIER_VIOLATIONS') == 0,
        violations=[fa.get('VERIFIER_VIOLATIONS'), fb.get('VERIFIER_VIOLATIONS')])

    def uniq(rows):
        by = collections.defaultdict(collections.Counter)
        for r in rows:
            by[r['contest_id']][(r['CPT'], tuple(sorted(r[f'FLEX{i}'] for i in range(1, 6))))] += 1
        return {c: {'n': sum(v.values()), 'distinct': len(v), 'max_dup': max(v.values())} for c, v in by.items()}
    ua, ub = uniq(_csv(_one(a, '*_FINAL_LINEUPS.csv'))), uniq(_csv(_one(b, '*_FINAL_LINEUPS.csv')))
    put('lineup_uniqueness', ua == ub, baseline=ua, candidate=ub)
    # state, with run-binding metadata removed
    sa_, sb_ = (_strip(json.loads(_one(x, 'SHOWDOWN_*_STATE.json').read_text()), VOLATILE | BINDING) for x in (a, b))
    pl = sorted(k for k in set(sa_['players']) | set(sb_['players']) if sa_['players'].get(k) != sb_['players'].get(k))
    hdr = sorted(k for k in set(sa_) | set(sb_) if k != 'players' and sa_.get(k) != sb_.get(k))
    put('slate_state_without_binding', not pl and not hdr, players_moved=pl[:20], header_keys_moved=hdr)
    numeric = ('projection_rows', 'player_draws', 'world_stat_lines', 'player_correlations_from_draws', 'final_lineups',
               'exposures', 'cpt_exposures', 'upload_files', 'lineup_uniqueness', 'legality')
    out['NUMERIC_OUTPUT_IDENTICAL'] = all(C[k]['IDENTICAL'] for k in numeric if k in C)
    out['ALL_IDENTICAL'] = all(v['IDENTICAL'] for v in C.values())
    out['DIFFERENT'] = sorted(k for k, v in C.items() if not v['IDENTICAL'])
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('baseline')
    ap.add_argument('candidate')
    ap.add_argument('--out')
    x = ap.parse_args()
    r = compare(x.baseline, x.candidate)
    if x.out:
        pathlib.Path(x.out).write_text(json.dumps(r, indent=1, default=str) + '\n')
    print(json.dumps({k: r[k] for k in ('NUMERIC_OUTPUT_IDENTICAL', 'ALL_IDENTICAL', 'DIFFERENT')}, indent=1))
    for k, v in r['checks'].items():
        if not v['IDENTICAL']:
            print('  DIFFERENT', k, json.dumps({kk: vv for kk, vv in v.items() if kk != 'IDENTICAL'}, default=str)[:400])
    sys.exit(0 if r['NUMERIC_OUTPUT_IDENTICAL'] else 2)
