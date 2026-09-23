"""The gate as an enforced production dependency, not an optional report.

WHAT THIS SUITE IS FOR

`test_player_review.py` proves the review finds things. This one proves the
finding STOPS something. Those are different claims and the second is the one
that was missing: last night the review would have blocked the slate and the
optimizer would have built twenty lineups from it anyway, because nothing
connected them.

THE ENFORCEMENT IS STRUCTURAL, NOT POLITE

`test_no_consumer_bypasses_the_gated_loader` greps the tree for a direct load
of a production draw artifact outside `gated_projection`. A future consumer
that opens the npz itself does not get a reminder; it gets a failing suite.

ALL EVIDENCE IS PRE-KICKOFF. The live cases read the sealed 2026-09-21
artifacts. No NYG@LAR result is admitted anywhere.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import random
import re
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import numpy as np                                                 # noqa: E402

from nfl.production.review import audit as AUD                     # noqa: E402
from nfl.production.review import dossier as DOS                   # noqa: E402
from nfl.production.review import escalation as ESC                # noqa: E402
from nfl.production.review import evidence as EV                   # noqa: E402
from nfl.production.review import gate as GATE                     # noqa: E402
from nfl.production.review import gated_projection as GP           # noqa: E402
from nfl.production.review import slate_report as SR               # noqa: E402
from nfl.production.universe import depth_role as DR               # noqa: E402

from nfl.tests import governed_draws as GD   # noqa: E402

PASSED = FAILED = 0
CUT = '2026-09-21T23:05:00Z'
GAME = '2026_02_NYG_LA'
LIVE_DRAWS = _REPO / 'nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
LIVE_REVIEW = _REPO / 'nfl/research/player_review/2026_02_NYG_LA'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


# --------------------------------------------------------------------------
# a synthetic slate: draws on disk, a review beside them
# --------------------------------------------------------------------------
def mk_row(gsis_id, **kw):
    r = {'game_id': GAME, 'season': 2026, 'week': 2, 'team': 'NYG',
         'opponent': 'LA', 'gsis_id': gsis_id, 'display_name': gsis_id,
         'roster_position': 'RB', 'roster_status': 'ACT',
         'officially_inactive': False, 'support_state': 'MODEL_SUPPORTED',
         'information_cut': CUT, 'offensive_depth_rank': 1,
         'offensive_depth_state': 'OFFENSIVE_DEPTH_RANK:RB1',
         'special_teams_role': None, 'pfr_id': None,
         'injury_report_status': None, 'injury_practice_status': None}
    r.update(kw)
    return r


def write_draws(d: pathlib.Path, per_player, n=64, seed=20260922,
                run_status='PASS'):
    """A minimal but REAL draw artifact: npz, a manifest that agrees, and a
    run status. The status is not optional: an artifact without one is now
    BLOCKED, because it is indistinguishable from one whose run refused."""
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    ids = list(per_player)
    metrics = {'dk_scoring/dk_points': 'dk_points',
               'rushing/carries': 'carries',
               'receiving/targets': 'targets'}
    arrays, layers = {}, {}
    for key, comp in metrics.items():
        layer = key.split('/')[0]
        M = np.stack([np.maximum(
            0.0, rng.normal(per_player[p].get(comp, 0.0), 0.5, n))
            for p in ids])
        arrays[key.replace('/', '__', 1)] = M
        layers.setdefault(layer, {'metrics': [], 'row_axis': 'gsis_id',
                                  'row_ids': ids, 'shape': [len(ids), n]})
        layers[layer]['metrics'].append(comp)
    np.savez(d / 'player_draws.npz', **arrays)
    if run_status is not None:
        (d / 'run_status.json').write_text(json.dumps(
            {'run_id': 'SYNTH', 'status': run_status, 'n_refusals': 0}))
    (d / 'player_draws_manifest.json').write_text(json.dumps(
        {'run_id': 'SYNTH', 'game_id': GAME, 'n_draws': n,
         'n_matrices': len(arrays), 'layers': layers,
         'arrays': {k.replace('__', '/', 1): {'shape': list(v.shape)}
                    for k, v in arrays.items()}}, indent=1))
    # THIS IS A GOVERNED SIMULATION ARTIFACT, SO IT CARRIES A COHERENCE
    # VERDICT. Before 2026-09-23 it wrote a two-key run_status and no
    # quarterback layer, and when SIMULATION_DRAW_COHERENCE_VIOLATED became
    # an advertised invariant every load over it blocked. The owner ruling
    # was to repair the fixture rather than the rule: `governed_draws.attach`
    # adds the QB layer the real checker needs and records the REAL verdict
    # of the REAL checker and certifier. No verdict is asserted here.
    if run_status is not None:
        GD.attach(d, seed=seed)
    return hashlib.sha256((d / 'player_draws.npz').read_bytes()).hexdigest()


def build_review(root, rows, draws_dir, **kw):
    return SR.review_slate(slate_key=GAME, universe_rows=rows,
                           draws_dir=draws_dir, information_cut=CUT,
                           root=str(root), deep_research_capacity=2, **kw)


def clean_slate(tmp):
    """A slate with real draws, real dossiers, and nothing contradictory."""
    draws = pathlib.Path(tmp) / 'draws'
    rows = [mk_row('CLEAN1', offensive_depth_rank=1),
            mk_row('CLEAN2', offensive_depth_rank=2)]
    write_draws(draws, {'CLEAN1': {'dk_points': 12.0, 'carries': 14.0},
                        'CLEAN2': {'dk_points': 7.0, 'carries': 8.0}})
    role = [{'gsis_id': 'CLEAN1', 'room': 'carries', 'role': 'STARTER',
             'role_support': 'ROLE_SUPPORTED', 'team': 'NYG',
             'evidence': {'current_season_usage': {'carries': 20.0,
                                                   'targets': 2.0,
                                                   'carry_share': 0.5}}},
            {'gsis_id': 'CLEAN2', 'room': 'carries', 'role': 'PRIMARY_ROTATION',
             'role_support': 'ROLE_SUPPORTED', 'team': 'NYG',
             'evidence': {'current_season_usage': {'carries': 9.0,
                                                   'targets': 1.0,
                                                   'carry_share': 0.22}}}]
    snaps = [{'pfr_player_id': 'A', 'offense_pct': '0.80', 'st_pct': '0.05',
              'week': '1', 'team': 'NYG'},
             {'pfr_player_id': 'B', 'offense_pct': '0.40', 'st_pct': '0.10',
              'week': '1', 'team': 'NYG'}]
    rows[0]['pfr_id'], rows[1]['pfr_id'] = 'A', 'B'
    root = pathlib.Path(tmp) / 'review'
    o = build_review(root, rows, draws, role_rows=role, snap_rows=snaps,
                     inactive_ids={'NOBODY'},
                     publishable_ids={'CLEAN1', 'CLEAN2'})
    return draws, root / GAME, o


# --------------------------------------------------------------------------
# 1. the optimizer refuses
# --------------------------------------------------------------------------
def test_optimizer_refuses_when_review_never_ran():
    with tempfile.TemporaryDirectory() as td:
        draws = pathlib.Path(td) / 'draws'
        write_draws(draws, {'X': {'dk_points': 10.0}})
        o = GP.load(draws, pathlib.Path(td) / 'no-such-review')
        ok(o.state.name == 'BLOCKED' and
           o.code == GATE.PLAYER_REVIEW_NOT_RUN,
           f'an unreviewed slate refuses with {GATE.PLAYER_REVIEW_NOT_RUN}')
        ok(GATE.verdict_of(o) == GATE.BLOCKED,
           'and carries the BLOCKED verdict rather than an empty pool')


def test_optimizer_refuses_a_stale_review():
    with tempfile.TemporaryDirectory() as td:
        draws, rdir, _ = clean_slate(td)
        # The projection is regenerated; the review still describes the old one.
        write_draws(draws, {'CLEAN1': {'dk_points': 12.0, 'carries': 14.0},
                            'CLEAN2': {'dk_points': 7.0, 'carries': 8.0}},
                    seed=999)
        o = GP.load(draws, rdir)
        ok(o.state.name == 'BLOCKED' and o.code == GATE.PLAYER_REVIEW_STALE,
           f'a review of a superseded artifact refuses with '
           f'{GATE.PLAYER_REVIEW_STALE}, not with a blocking verdict: '
           f'got {o.state.name}/{o.code}')
        ok(GATE.verdict_of(o) == GATE.BLOCKED,
           'and still reports BLOCKED so nothing downstream proceeds')


def test_optimizer_refuses_a_blocking_conflict():
    """A run that SUCCEEDED, whose review found a material contradiction.

    The live artifact cannot serve here any more: its run refused at sealing,
    which is a more fundamental refusal and is checked first. That ordering is
    right -- a refused run is not a forecast, so whether its review passed is
    moot -- so the review block is proved on a clean-status artifact instead,
    and the live case is proved separately under refusal propagation.
    """
    with tempfile.TemporaryDirectory() as td:
        draws, rdir, _ = clean_slate(td)
        rep = json.loads((rdir / 'slate_review_report.json').read_text())
        rep['conflicts'].append({
            'code': AUD.C_INACTIVE_OWNS_OPPORTUNITY, 'severity': AUD.BLOCKING,
            'gsis_id': 'CLEAN1', 'display_name': 'CLEAN1', 'team': 'NYG',
            'detail': 'inactive with opportunity', 'evidence': {}})
        (rdir / 'slate_review_report.json').write_text(json.dumps(rep))
        o = GP.load(draws, rdir)
        ok(o.state.name == 'FAIL' and
           o.code == 'OPTIMIZATION_REFUSED_BY_PLAYER_REVIEW',
           f'a material blocking conflict refuses the load: {o.code}')
        ok(GATE.verdict_of(o) == GATE.BLOCKED,
           f'with verdict {GATE.verdict_of(o)}, not an ambiguous green')


def test_a_clean_slate_passes_review_and_reaches_the_optimizer():
    with tempfile.TemporaryDirectory() as td:
        draws, rdir, review = clean_slate(td)
        ok(review.state.name == 'PASS', f'the review runs: {review.code}')
        verdict = review.value['verdict']
        ok(verdict in (GATE.PASS, GATE.PASS_WITH_WARNINGS),
           f'a slate with no contradiction is {verdict}')
        o = GP.load(draws, rdir)
        ok(o.state.name == 'PASS' and o.code == 'GATED_PROJECTION_LOADED',
           f'and the optimizer receives the arrays: {o.code}')
        ok('dk_scoring/dk_points' in o.value['arrays'],
           'under both array spellings, ready to use')
        idx = GP.row_index(o.value['layers'], 'dk_scoring')
        ok(idx == {'CLEAN1': 0, 'CLEAN2': 1},
           f'with a usable row index: {idx}')


def test_annotated_non_blocking_conflict_proceeds():
    with tempfile.TemporaryDirectory() as td:
        draws, rdir, _ = clean_slate(td)
        rep = json.loads((rdir / 'slate_review_report.json').read_text())
        rep['conflicts'].append({
            'code': AUD.C_RECEIVING_ROLE_ON_SNAPS_ONLY, 'severity': AUD.NOTE,
            'gsis_id': 'CLEAN1', 'display_name': 'CLEAN1', 'team': 'NYG',
            'detail': 'routes unavailable', 'evidence': {'targets': 9.0}})
        (rdir / 'slate_review_report.json').write_text(json.dumps(rep))
        o = GP.load(draws, rdir)
        ok(o.state.name == 'PASS',
           f'a route-unavailable annotation does not stop the slate: {o.code}')
        ok(o.value['verdict'] == GATE.PASS_WITH_WARNINGS and
           o.value['warning_count'] >= 1,
           f'it reads {o.value["verdict"]} with '
           f'{o.value["warning_count"]} warning(s), still visible')


# --------------------------------------------------------------------------
# 2. what blocks
# --------------------------------------------------------------------------
def _gate_on(rows, projections, *, inactive=None, role_rows=(), snaps=(),
             pool=None):
    ds = DOS.build_dossiers(universe_rows=rows, role_rows=role_rows,
                            snap_rows=snaps, inactive_ids=inactive,
                            information_cut=CUT).value['dossiers']
    for d in ds:
        for k, v in (projections.get(d.gsis_id) or {}).items():
            d.projection[k] = EV.ProjectionComponent(k, v, EV.MEASURED)
    a = AUD.audit(ds)
    res = a.value or a.evidence['value']
    e = ESC.escalate(ds, res, deep_research_capacity=2).value
    rep = SR.build_report(slate_key=GAME, dossiers=ds, audit_result=res,
                          escalation_result=e,
                          projection_source={'digests': {}})
    return GATE.evaluate(rep, dossiers=ds, optimizer_pool_ids=pool), res


def test_inactive_violation_blocks():
    g, _ = _gate_on([mk_row('A'), mk_row('B')],
                    {'B': {'carries': 9.0, 'dk_points': 12.0}},
                    inactive={'B'})
    v = g.value or g.evidence['value']
    ok(v['verdict'] == GATE.BLOCKED and
       'availability_integrity' in v['blocking_by_category'],
       'an inactive player owning opportunity blocks on availability '
       'integrity')


def test_unsupported_material_role_blocks():
    role = [{'gsis_id': 'A', 'room': 'carries', 'role': 'ROLE_UNCERTAIN',
             'role_support': 'ROLE_UNSUPPORTED', 'team': 'NYG',
             'role_unsupported_why': ['no measured participation'],
             'evidence': {}}]
    g, _ = _gate_on([mk_row('A')], {'A': {'carries': 9.0, 'dk_points': 12.0}},
                    role_rows=role)
    v = g.value or g.evidence['value']
    ok(v['verdict'] == GATE.BLOCKED and
       'unsupported_published_role' in v['blocking_by_category'],
       'material workload on a refused role blocks')


def test_material_unexplained_inversion_blocks():
    role = [{'gsis_id': 'HI', 'room': 'carries', 'role': 'BACKUP',
             'role_support': 'ROLE_SUPPORTED', 'team': 'NYG',
             'evidence': {'current_season_usage': {'carries': 2.0,
                                                   'targets': 0.0}}},
            {'gsis_id': 'LO', 'room': 'carries', 'role': 'STARTER',
             'role_support': 'ROLE_SUPPORTED', 'team': 'NYG',
             'evidence': {'current_season_usage': {'carries': 18.0,
                                                   'targets': 0.0}}}]
    snaps = [{'pfr_player_id': 'h', 'offense_pct': '0.03', 'week': '1',
              'team': 'NYG'},
             {'pfr_player_id': 'l', 'offense_pct': '0.61', 'week': '1',
              'team': 'NYG'}]
    rows = [mk_row('HI', offensive_depth_rank=4, pfr_id='h'),
            mk_row('LO', offensive_depth_rank=1, pfr_id='l')]
    g, res = _gate_on(rows, {'HI': {'carries': 8.09, 'dk_points': 9.1},
                             'LO': {'carries': 6.14, 'dk_points': 7.4}},
                      role_rows=role, snaps=snaps)
    v = g.value or g.evidence['value']
    ok(AUD.C_ROOM_ORDER_INVERTED in {c['code'] for c in res['conflicts']},
       'the Tracy/Skattebo shape is raised')
    ok(v['verdict'] == GATE.BLOCKED and
       'role_opportunity_inversion' in v['blocking_by_category'],
       'and a material unexplained inversion blocks')


def test_low_materiality_uncertainty_annotates_and_proceeds():
    """The same blocking CODE on a row too small to change anything."""
    role = [{'gsis_id': 'A', 'room': 'targets', 'role': 'ROLE_UNCERTAIN',
             'role_support': 'ROLE_UNSUPPORTED', 'team': 'NYG',
             'role_unsupported_why': ['no measured participation'],
             'evidence': {}}]
    g, res = _gate_on([mk_row('A', roster_position='TE')],
                      {'A': {'targets': 1.05, 'dk_points': 0.4}},
                      role_rows=role)
    v = g.value or g.evidence['value']
    ok(AUD.C_UNSUPPORTED_ROLE_PUBLISHED in {c['code']
                                            for c in res['conflicts']},
       'the conflict is still raised on a 0.4-point row')
    ok(v['verdict'] != GATE.BLOCKED,
       f'but it does not block: {v["verdict"]}')
    ok(v['immaterial_blocking_codes_held_as_warnings'].get(
        AUD.C_UNSUPPORTED_ROLE_PUBLISHED) == 1,
       'and it is COUNTED as a blocking code held back as immaterial, not '
       'quietly dropped')


def test_an_unregistered_conflict_code_blocks_rather_than_defaulting_safe():
    ds = DOS.build_dossiers(universe_rows=[mk_row('A')],
                            information_cut=CUT).value['dossiers']
    ds[0].projection['dk_points'] = EV.ProjectionComponent(
        'dk_points', 10.0, EV.MEASURED)
    rep = SR.build_report(slate_key=GAME, dossiers=ds,
                          audit_result={'conflicts': []},
                          escalation_result={'verdicts': []},
                          projection_source={'digests': {}})
    g = GATE.evaluate(rep, dossiers=ds, extra_conflicts=[
        {'code': 'SOME_CODE_NOBODY_CLASSIFIED', 'severity': 'REVIEW',
         'gsis_id': 'A', 'display_name': 'A', 'team': 'NYG',
         'detail': 'x', 'evidence': {}}])
    v = g.value or g.evidence['value']
    ok(v['verdict'] == GATE.BLOCKED and
       'unregistered_code' in v['blocking_by_category'],
       'a code in neither table blocks; an unknown conflict is not harmless')


# --------------------------------------------------------------------------
# 3. materiality takes no market argument
# --------------------------------------------------------------------------
def test_materiality_cannot_be_passed_a_market_value():
    import inspect
    sig = set(inspect.signature(GATE.materiality).parameters)
    banned = {'market', 'price', 'odds', 'hardrock', 'vegas', 'ownership',
              'external', 'fantasycruncher', 'fc'}
    ok(not (sig & banned),
       f'materiality() takes {sorted(sig)} -- no market or external '
       f'projection argument exists to pass')
    ok('forbidden_inputs' in GATE.MATERIALITY_RULE,
       'and the rule states the prohibition in the artifact itself')


def test_external_data_cannot_alter_dossier_football_evidence():
    ds = DOS.build_dossiers(universe_rows=[mk_row('A')],
                            information_cut=CUT).value['dossiers']
    ds[0].projection['dk_points'] = EV.ProjectionComponent(
        'dk_points', 10.0, EV.MEASURED)
    before = json.dumps(ds[0].as_dict(), sort_keys=True, default=str)
    res = AUD.audit(ds).value
    e = ESC.escalate(ds, res, deep_research_capacity=1,
                     external_disagreement={'A': {'hardrock_gap': 0.95,
                                                  'fc_gap': 0.80}}).value
    after = json.dumps(ds[0].as_dict(), sort_keys=True, default=str)
    ok(before == after,
       'a Hard Rock gap and a Fantasy Cruncher gap leave the dossier '
       'byte-identical')
    ok(e['verdicts'][0].disagreement > 0,
       'they raise the investigation priority, which is all they may do')
    m = GATE.materiality(ds[0], {'code': AUD.C_COLD_START_MATERIAL,
                                 'evidence': {}})
    ok('hardrock' not in json.dumps(m).lower() and
       'market' not in json.dumps(m).lower(),
       'and no market quantity appears anywhere in the materiality verdict')


# --------------------------------------------------------------------------
# 4. depth-row determinism
# --------------------------------------------------------------------------
DUAL = [
    ('RB1 + PR2', 'RB', [{'pos_abb': 'RB', 'pos_rank': '1', 'dt': 'T'},
                         {'pos_abb': 'PR', 'pos_rank': '2', 'dt': 'T'}]),
    ('RB4 + KR2', 'RB', [{'pos_abb': 'RB', 'pos_rank': '4', 'dt': 'T'},
                         {'pos_abb': 'KR', 'pos_rank': '2', 'dt': 'T'}]),
    ('WR5 + PR1', 'WR', [{'pos_abb': 'WR', 'pos_rank': '5', 'dt': 'T'},
                         {'pos_abb': 'PR', 'pos_rank': '1', 'dt': 'T'}]),
    ('DB (LCB1) + KR1', 'DB', [{'pos_abb': 'LCB', 'pos_rank': '1', 'dt': 'T'},
                               {'pos_abb': 'KR', 'pos_rank': '1', 'dt': 'T'}]),
]


def test_dual_role_selection_is_byte_identical_under_row_order():
    for name, pos, rows in DUAL:
        a = json.dumps(DR.select_listings(rows, pos), sort_keys=True,
                       default=str)
        b = json.dumps(DR.select_listings(list(reversed(rows)), pos),
                       sort_keys=True, default=str)
        ok(a == b, f'{name}: input A and input B give byte-identical output')


def test_dual_role_selection_is_stable_under_every_permutation():
    rnd = random.Random(20260922)
    for name, pos, rows in DUAL:
        seen = set()
        for _ in range(60):
            s = rows[:]
            rnd.shuffle(s)
            seen.add(json.dumps(DR.select_listings(s, pos), sort_keys=True,
                                default=str))
        ok(len(seen) == 1,
           f'{name}: 60 shuffles give {len(seen)} distinct result(s); 1 is '
           f'the only acceptable answer')


def test_equal_timestamps_never_make_file_order_meaningful():
    """The exact defect: every row carries the SAME dt."""
    for name, pos, rows in DUAL:
        dts = {r['dt'] for r in rows}
        ok(len(dts) == 1, f'{name}: the fixture really does tie on dt')
        s = DR.select_listings(rows, pos)
        st = s['special_teams_row']
        off = s['offensive_row']
        ok(st is not None,
           f'{name}: the special-teams listing survives ({st["pos_abb"]}'
           f'{st["pos_rank"]})')
        if pos in ('RB', 'WR'):
            ok(off is not None and
               DR.classify_group(off['pos_abb']) == 'OFFENSIVE',
               f'{name}: and so does the offensive one '
               f'({off["pos_abb"]}{off["pos_rank"]})')
        else:
            ok(off is None,
               f'{name}: a defensive listing yields no offensive row, so no '
               f'rank is borrowed into an offensive room')


# --------------------------------------------------------------------------
# 5. structural: nothing bypasses the loader
# --------------------------------------------------------------------------
#: `sealed_player_draws.npz` is a DIFFERENT artifact -- the frozen research
#: fixture under `nfl/dfs/showdown/frozen`, which is not a slate projection
#: and has no slate review. It is named here rather than silently excluded.
SEPARATE_ARTIFACTS = ('sealed_player_draws',)
LOADER = 'nfl/production/review/gated_projection.py'

#: THE BOUNDARY, stated rather than assembled from whatever happened to pass.
#: A PUBLICATION path turns draws into something a person acts on -- a card, a
#: package, a lineup -- and must come through the gate. A MEASUREMENT reader
#: computes a statistic about draws and publishes nothing, so gating it would
#: mean a blocked slate could not even be diagnosed, which is backwards.
PUBLICATION_DIRS = ('nfl/dfs/', 'nfl/product/', 'nfl/production/')
MEASUREMENT_DIRS = ('nfl/tools/', 'nfl/research/', 'nfl/postgame/')

#: `dossier.read_projection` reads the same file by design: the review must
#: read the projection it is reviewing, before any verdict exists. It is the
#: one reader inside a publication directory that produces no lineup.
PUBLICATION_READERS_ALLOWED = {'nfl/production/review/dossier.py'}

#: Measurement readers at the time the gate was wired. Pinned so that a NEW
#: one has to be classified deliberately rather than appearing unnoticed.
MEASUREMENT_READERS_AT_WIRING = 12

PAT = re.compile(r"""(np\.load|open)\s*\(\s*[^)]*player_draws\.npz""", re.S)


def _direct_readers():
    pub, meas, unclassified = [], [], []
    for f in sorted((_REPO / 'nfl').rglob('*.py')):
        rel = str(f.relative_to(_REPO)).replace('\\', '/')
        if rel == LOADER or '/tests/' in rel or '__pycache__' in rel:
            continue
        txt = f.read_text(errors='ignore')
        if any(s in txt for s in SEPARATE_ARTIFACTS):
            continue
        # Only CODE counts. A comment explaining the defect that was removed
        # is not the defect, and an earlier version of this test failed on
        # its own explanatory prose.
        code = '\n'.join(l for l in txt.splitlines()
                          if not l.lstrip().startswith('#'))
        if not PAT.search(code):
            continue
        if any(rel.startswith(d) for d in PUBLICATION_DIRS):
            pub.append(rel)
        elif any(rel.startswith(d) for d in MEASUREMENT_DIRS):
            meas.append(rel)
        else:
            unclassified.append(rel)
    return pub, meas, unclassified


def test_no_publication_path_bypasses_the_gated_loader():
    pub, meas, unclassified = _direct_readers()
    real = [o for o in pub if o not in PUBLICATION_READERS_ALLOWED]
    ok(not real,
       f'no publication path opens a production draw artifact outside the '
       f'gated loader; offenders: {real}')
    ok(not unclassified,
       f'every direct reader sits in a directory the boundary classifies; '
       f'unclassified: {unclassified}')
    ok(len(meas) <= MEASUREMENT_READERS_AT_WIRING,
       f'{len(meas)} measurement reader(s), against the '
       f'{MEASUREMENT_READERS_AT_WIRING} pinned at wiring -- a new one must '
       f'be classified deliberately: {meas}')


def test_the_live_selectors_actually_call_the_loader():
    for name in ('select_no_tracy', 'select_scale_invariant', 'cleanup_pool'):
        p = _REPO / f'nfl/dfs/showdown/{name}.py'
        txt = p.read_text()
        ok('gated_projection' in txt and '_GP.load(' in txt,
           f'{name}.py obtains its projections through the gate')


def test_guard_rank_map_is_wired_into_the_forecast_path():
    txt = (_REPO / 'nfl/production/run_forecast.py').read_text()
    ok('guard_rank_map' in txt,
       'run_forecast calls guard_rank_map')
    code = '\n'.join(l for l in txt.splitlines()
                      if not l.lstrip().startswith('#'))
    ok('dr[k] = v[1]' not in code,
       'and the unguarded `dr[k] = v[1]` assignment is gone from the '
       'production CODE (the comment recording it is not the defect)')
    ok(re.search(r'_guard\[.rank.\]', txt) is not None,
       'the rank map the forecast uses is the guarded one')


# -- 8. refusal propagation -------------------------------------------------
def test_a_run_that_refused_cannot_reach_the_optimizer():
    o = GP.load(LIVE_DRAWS, LIVE_REVIEW)
    ok(o.state.name == 'FAIL' and o.code == GP.RUN_REFUSED,
       f'the sealed run refused at artifact_sealing and is refused '
       f'downstream by name: {o.code}')
    v = GATE.payload(o)
    ok(v.get('publishable') is False and v.get('verdict') == 'BLOCKED',
       'marked non-publishable, with no ambiguous green')
    ok(v.get('stage') == 'artifact_sealing',
       f'naming the stage that refused: {v.get("stage")}')


def test_a_debugging_path_can_still_inspect_a_refused_run():
    o = GP.load(LIVE_DRAWS, LIVE_REVIEW,
                inspect_refused_non_publishable=True)
    ok(o.state.name == 'PASS' and
       o.code == 'REFUSED_ARTIFACT_OPENED_FOR_INSPECTION',
       f'an explicitly marked inspection opens it: {o.code}')
    ok(o.value['publishable'] is False and o.value['verdict'] is None,
       'but carries publishable=False and no verdict, so nothing can '
       'mistake it for a forecast')
    ok(len(o.value['arrays']) > 0,
       f'while the arrays really are readable: {len(o.value["arrays"])} '
       f'matrices, so a blocked slate can still be diagnosed')


def test_a_missing_run_status_is_not_assumed_fine():
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td) / 'draws'
        write_draws(d, {'X': {'dk_points': 10.0}}, run_status=None)
        r = GP.run_status(d)
        ok(r.state.name == 'BLOCKED' and r.code == 'RUN_STATUS_ABSENT',
           'an artifact with no run record is BLOCKED, not presumed to have '
           'passed')


def test_freshness_refusal_is_a_named_upstream_state():
    from nfl.production.nonqb import current_season_evidence as CSE
    ev = CSE.collect(2026, 2, '2026-09-21T23:05:00Z')
    f = CSE.assert_fresh(ev, season=2026, week=9)
    ok(f.state.name == 'BLOCKED' and f.code == CSE.STALE,
       f'stale current-season input refuses as {CSE.STALE}, before any world '
       f'is drawn')


def main():
    for t in (test_optimizer_refuses_when_review_never_ran,
              test_optimizer_refuses_a_stale_review,
              test_optimizer_refuses_a_blocking_conflict,
              test_a_clean_slate_passes_review_and_reaches_the_optimizer,
              test_annotated_non_blocking_conflict_proceeds,
              test_inactive_violation_blocks,
              test_unsupported_material_role_blocks,
              test_material_unexplained_inversion_blocks,
              test_low_materiality_uncertainty_annotates_and_proceeds,
              test_an_unregistered_conflict_code_blocks_rather_than_defaulting_safe,
              test_materiality_cannot_be_passed_a_market_value,
              test_external_data_cannot_alter_dossier_football_evidence,
              test_dual_role_selection_is_byte_identical_under_row_order,
              test_dual_role_selection_is_stable_under_every_permutation,
              test_equal_timestamps_never_make_file_order_meaningful,
              test_no_publication_path_bypasses_the_gated_loader,
              test_the_live_selectors_actually_call_the_loader,
              test_guard_rank_map_is_wired_into_the_forecast_path,
              test_a_run_that_refused_cannot_reach_the_optimizer,
              test_a_debugging_path_can_still_inspect_a_refused_run,
              test_a_missing_run_status_is_not_assumed_fine,
              test_freshness_refusal_is_a_named_upstream_state):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
