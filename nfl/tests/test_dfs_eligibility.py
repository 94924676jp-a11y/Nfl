"""A player the football state says will not play must not reach a lineup.

Three mechanisms, tested separately because they fail separately:

    PREVENTION  pool.build_pool excludes him
    RECORDING   the exclusion ledger says who, why, and on what evidence
    DETECTION   dfs/eligibility_integrity proves it, and a failure refuses
                the pool and blocks publication

The bypass test is the one that matters most: it restores the exact rule the
pool used before this slice -- `availability == 'INACTIVE'` -- and proves the
detective mechanism catches what the preventive one then misses.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(_REPO), str(_REPO / 'nfl' / 'tests')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nfl.dfs import eligibility_integrity as EI                       # noqa: E402
from nfl.dfs import exclusion as EX                                   # noqa: E402
from nfl.dfs.classic import pool as POOL                              # noqa: E402
from nfl.production.integrity import contract as IC                   # noqa: E402
from nfl.production.review import dossier as DOS                      # noqa: E402
from nfl.production.review import gate as GATE                        # noqa: E402
from nfl.production.state import availability as AV                   # noqa: E402

import test_review_enforcement as TRE                                 # noqa: E402

from nfl.tests import governed_draws as GD   # noqa: E402

PASSED = FAILED = 0
CUT, GAME = TRE.CUT, TRE.GAME
OUT_ID = 'OUTMAN'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _val(o):
    return o.value or (getattr(o, 'evidence', {}) or {}).get('value') or {}


def write_draws(d, per_player, zeroed=(), zero_metrics=None,
                n=64, seed=20260922):
    """Like the enforcement suite's, but able to write EXACT zeros.

    `apply_to_appearance` zeroes an inactive player's draws in place and
    leaves the row, so a fixture that cannot produce exact zeros cannot
    represent the state production actually writes.
    """
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    ids = list(per_player)
    metrics = {'dk_scoring/dk_points': 'dk_points',
               'rushing/carries': 'carries',
               'receiving/targets': 'targets'}
    arrays, layers = {}, {}
    for key, comp in metrics.items():
        layer = key.split('/')[0]
        rowset = []
        for p in ids:
            if p in set(zeroed) or comp in (zero_metrics or {}).get(p, ()):
                rowset.append(np.zeros(n))
            else:
                rowset.append(np.maximum(
                    0.0, rng.normal(per_player[p].get(comp, 0.0), 0.5, n)))
        M = np.stack(rowset)
        arrays[key.replace('/', '__', 1)] = M
        layers.setdefault(layer, {'metrics': [], 'row_axis': 'gsis_id',
                                  'row_ids': ids, 'shape': [len(ids), n]})
        layers[layer]['metrics'].append(comp)
    np.savez(d / 'player_draws.npz', **arrays)
    (d / 'run_status.json').write_text(json.dumps(
        {'run_id': 'SYNTH', 'status': 'PASS', 'n_refusals': 0}))
    (d / 'player_draws_manifest.json').write_text(json.dumps(
        {'run_id': 'SYNTH', 'game_id': GAME, 'n_draws': n,
         'n_matrices': len(arrays), 'layers': layers,
         'arrays': {k.replace('__', '/', 1): {'shape': list(v.shape)}
                    for k, v in arrays.items()}}, indent=1))
    # A GOVERNED SIMULATION ARTIFACT CARRIES A COHERENCE VERDICT. See the
    # same note in test_review_enforcement: the QB layer and the real
    # checker's verdict are attached here rather than the advertised
    # invariant being weakened. The zeroed rows this fixture cares about are
    # untouched -- `attach` adds a layer, it does not rewrite one.
    GD.attach(d, seed=7, zero_row_ids=tuple(zeroed or ())
              + tuple((zero_metrics or {})))
    return hashlib.sha256((d / 'player_draws.npz').read_bytes()).hexdigest()


#: What the simulation artifact holds for the OUT player.
ZEROED = 'zeroed'                      # what apply_to_appearance writes
LIVE_POINTS_ONLY = 'live_points_only'  # zero opportunity, live DK points
LIVE_OPPORTUNITY = 'live_opportunity'  # never zeroed at all


def slate(tmp, *, out_mode=ZEROED):
    """CLEAN1, CLEAN2 and an INJURY_OUT player with salary, a projection and
    a DK id -- otherwise perfectly eligible."""
    tmp = pathlib.Path(tmp)
    draws = tmp / 'draws'
    rows = [TRE.mk_row('CLEAN1', pfr_id='A', offensive_depth_rank=1),
            TRE.mk_row('CLEAN2', pfr_id='B', offensive_depth_rank=2),
            TRE.mk_row(OUT_ID, pfr_id='C', offensive_depth_rank=3,
                       injury_report_status='Out')]
    per = {'CLEAN1': {'dk_points': 12.0, 'carries': 14.0},
           'CLEAN2': {'dk_points': 7.0, 'carries': 8.0},
           OUT_ID: {'dk_points': 9.0, 'carries': 11.0}}
    write_draws(draws, per,
                zeroed=(OUT_ID,) if out_mode == ZEROED else (),
                zero_metrics=({OUT_ID: ('carries', 'targets')}
                              if out_mode == LIVE_POINTS_ONLY else None))
    role = [{'gsis_id': p, 'room': 'carries', 'role': 'STARTER',
             'role_support': 'ROLE_SUPPORTED', 'team': 'NYG',
             'evidence': {'current_season_usage': {
                 'carries': 20.0, 'targets': 2.0, 'carry_share': 0.4}}}
            for p in ('CLEAN1', 'CLEAN2', OUT_ID)]
    snaps = [{'pfr_player_id': x, 'offense_pct': '0.70', 'st_pct': '0.05',
              'week': '1', 'team': 'NYG'} for x in ('A', 'B', 'C')]
    root = tmp / 'review'
    TRE.build_review(root, rows, draws, role_rows=role, snap_rows=snaps,
                     inactive_ids={'NOBODY'},
                     publishable_ids={'CLEAN1', 'CLEAN2', OUT_ID})

    # The board, with availability taken from the DOSSIER rather than typed
    # in, so the fixture carries whatever canonical state actually says.
    ds = {d.gsis_id: d for d in DOS.build_dossiers(
        universe_rows=rows, role_rows=role, snap_rows=snaps,
        inactive_ids={'NOBODY'}, information_cut=CUT).value['dossiers']}
    means = {'CLEAN1': 12.0, 'CLEAN2': 7.0,
             OUT_ID: 0.0 if out_mode == ZEROED else 9.0}
    bdir = tmp / 'board'
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / 'PLAYER_BOARD.json').write_text(json.dumps({
        'slate_key': GAME, 'information_cut': CUT,
        'run_identity': 'SYNTH',
        'rows': [{'gsis_id': p, 'player': p, 'team': 'NYG', 'opponent': 'LA',
                  'position': 'carries', 'review_verdict': 'CLEARED',
                  'availability': ds[p].axis('official_availability').value,
                  'evidence_grade': 'MEASURED',
                  'salary': 5000, 'dk_mean': means[p]}
                 for p in ('CLEAN1', 'CLEAN2', OUT_ID)]}))
    return bdir, draws, root / GAME


def build(bdir, draws, rdir):
    return POOL.build_pool(board_dir=bdir, draws_dir=draws, review_dir=rdir,
                           dk_ids={'CLEAN1': '1', 'CLEAN2': '2',
                                   OUT_ID: '3'})


@contextlib.contextmanager
def bypassed_prevention():
    """Restore the EXACT rule the pool used before this slice, in the POOL
    ONLY.

    `pool` and `eligibility_integrity` both hold the same availability
    module, so patching the module's function would defeat the detector as
    well as the preventer and prove nothing. Rebinding only the pool's own
    name leaves the producer looking at real canonical truth, which is the
    situation this test is about: prevention broken, detection intact.
    """
    class _OldRule:
        WILL_NOT_PLAY = AV.WILL_NOT_PLAY
        SERIALISED_ALIASES = AV.SERIALISED_ALIASES
        canonical = staticmethod(AV.canonical)

        @staticmethod
        def will_not_play(v):
            return str(v) == 'INACTIVE'

    original = POOL.AV
    POOL.AV = _OldRule
    try:
        yield
    finally:
        POOL.AV = original


# -- 1. the fixture really is an OUT player who is otherwise eligible ------
def test_the_fixture_is_an_out_player_with_everything_else_in_order():
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td)
        board = json.loads((bdir / 'PLAYER_BOARD.json').read_text())
        r = next(x for x in board['rows'] if x['gsis_id'] == OUT_ID)
        ok(r['availability'] == AV.INJURY_OUT,
           f'canonical availability is {r["availability"]}, taken from the '
           f'dossier rather than typed into the fixture')
        ok(AV.will_not_play(r['availability']),
           'and it is WILL_NOT_PLAY')
        ok(r['review_verdict'] == 'CLEARED' and isinstance(r['salary'], int)
           and isinstance(r['dk_mean'], float),
           'he is CLEARED, priced and projected -- nothing but availability '
           'disqualifies him')
        ok(not AV.will_not_play(AV.INJURY_QUESTIONABLE)
           and not AV.will_not_play(AV.INJURY_DOUBTFUL)
           and not AV.will_not_play(AV.NOT_ON_INACTIVE_LIST)
           and not AV.will_not_play(AV.UNKNOWN),
           'while QUESTIONABLE, DOUBTFUL, NOT_ON_INACTIVE_LIST and UNKNOWN '
           'are none of them will-not-play')


# -- 2. prevention, recording, detection -----------------------------------
def test_the_out_player_is_excluded_recorded_and_verified():
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td)
        o = build(bdir, draws, rdir)
        v = _val(o)
        ok(o.state.name == 'PASS', f'the pool builds: {o.code}')
        ids = {p.gsis_id for p in v['players']}
        ok(OUT_ID not in ids,
           f'PREVENTION: the OUT player is not in the pool: {sorted(ids)}')
        ok(ids == {'CLEAN1', 'CLEAN2'},
           'and everyone else survives unchanged')
        led = v['exclusions']
        e = next(x for x in led['governance'] if x['gsis_id'] == OUT_ID)
        ok(e['reason'] == EX.WILL_NOT_PLAY and e['kind'] == EX.GOVERNANCE,
           f'RECORDING: {e["reason"]} / {e["kind"]}')
        ok(e['availability'] == AV.INJURY_OUT
           and e['excluded_from'] == EX.FROM_OPTIMIZER,
           f'with the canonical state that justified it: {e["availability"]} '
           f'from {e["excluded_from"]}')
        ok(e['evidence_grade'] and e['state_identity'],
           f'and its evidence grade and source state identity: '
           f'{e["evidence_grade"]} / {e["state_identity"]}')
        ok(led['n_strategy'] == 0,
           'no strategy exclusion is reported on this slate, because none '
           'happened')
        it = v['integrity']
        ok(it['coverage'][0]['state'] == IC.CHECKED_AND_PASSING,
           f'DETECTION: the invariant is CHECKED_AND_PASSING: '
           f'{it["coverage"][0]["state"]}')
        ok(it['n_findings'] == 0 and it['report_hash'].startswith('IR-'),
           f'no finding, report {it["report_hash"]}')
        ok(v['integrity_coverage'][EI.C_INACTIVE_IN_POOL]
           == IC.CHECKED_AND_PASSING,
           'and the pool result carries the coverage explicitly')


# -- 3. the bypass: prevention defeated, detection holds -------------------
def test_when_the_exclusion_is_defeated_the_producer_blocks_the_pool():
    """Restores the EXACT rule the pool used before this slice."""
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td)
        with bypassed_prevention():
            o = build(bdir, draws, rdir)
        v = _val(o)
        ok(o.state.name == 'FAIL' and o.code == EI.C_INACTIVE_IN_POOL,
           f'the pool REFUSES rather than returning a pool with him in it: '
           f'{o.code}')
        f = v['integrity']['findings'][0]
        ok(f['subject'] == OUT_ID and f['severity'] == IC.BLOCKING,
           f'the finding names him at BLOCKING: {f["subject"]}')
        ok(f['evidence']['population'] == EI.POP_OPTIMIZER,
           f'and names the population that failed: '
           f'{f["evidence"]["population"]}')
        ok(f['evidence']['availability'] == AV.INJURY_OUT
           and f['owner'] == IC.OWNER_ELIGIBILITY,
           f'with the state and the owning subsystem: {f["owner"]}')
        cov = {c['code']: c['state'] for c in v['integrity']['coverage']}
        ok(cov[EI.C_INACTIVE_IN_POOL] == IC.CHECKED_AND_FAILING,
           f'coverage reads CHECKED_AND_FAILING: {cov}')
        ok(any(x['gsis_id'] == OUT_ID for x in v['exclusions']['governance'])
           is False,
           'and the ledger honestly shows he was NOT excluded, because he '
           'was not')


def test_the_gate_blocks_on_the_same_finding():
    """The pool refuses, and the same finding is a blocking gate conflict --
    so a caller that reached the gate directly would also stop."""
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td)
        with bypassed_prevention():
            o = build(bdir, draws, rdir)
        findings = _val(o)['integrity']['findings']
        rep = {'conflicts': [], 'projection_source': {'digests': {}},
               'coverage': {}}
        g = GATE.evaluate(rep, extra_conflicts=[
            {'code': f['code'], 'severity': f['severity'],
             'gsis_id': None, 'display_name': f['subject'],
             'detail': f['detail'], 'evidence': f['evidence']}
            for f in findings])
        ok(GATE.payload(g)['verdict'] == GATE.BLOCKED,
           f'the gate blocks on it: {g.code}')
        ok(EI.C_INACTIVE_IN_POOL in GATE.BLOCKING_CODES,
           'because the code is advertised as blocking again')
        ok(GATE.BLOCKING_CODES[EI.C_INACTIVE_IN_POOL]
           == 'availability_integrity',
           'under availability_integrity')


# -- 4. the simulation population ------------------------------------------
def test_a_zeroed_row_is_expected_and_a_live_one_is_not():
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td, out_mode=ZEROED)
        v = _val(build(bdir, draws, rdir))
        man = json.loads((draws / 'player_draws_manifest.json').read_text())
        ok(all(OUT_ID in (spec.get('row_ids') or [])
               for spec in man['layers'].values()),
           'the OUT player IS a row in every simulation layer -- '
           'apply_to_appearance zeroes in place and leaves the row')
        ok(v['integrity']['n_findings'] == 0,
           'and a zeroed row is NOT a violation, so nothing fires')

    # A row never zeroed, still carrying OPPORTUNITY, is caught UPSTREAM by
    # the audit -- INACTIVE_PLAYER_OWNS_OPPORTUNITY -- and the gate stops the
    # slate before a pool is ever built. Proving that is proving the layering
    # works, not a gap.
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td, out_mode=LIVE_OPPORTUNITY)
        o = build(bdir, draws, rdir)
        ok(o.state.name == 'FAIL'
           and o.code == 'OPTIMIZATION_REFUSED_BY_PLAYER_REVIEW',
           f'a will-not-play player still owning opportunity is blocked by '
           f'the AUDIT, upstream of the pool: {o.code}')

    # The case the audit CANNOT see: zero opportunity, live DK points. The
    # audit weighs opportunity, so nothing fires there; the eligibility
    # producer weighs the draws themselves and does.
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td, out_mode=LIVE_POINTS_ONLY)
        o = build(bdir, draws, rdir)
        v = _val(o)
        ok(o.state.name == 'FAIL' and o.code == EI.C_INACTIVE_IN_POOL,
           f'a row that was never zeroed IS a violation: {o.code}')
        f = next(x for x in v['integrity']['findings']
                 if x['evidence']['population'] == EI.POP_SIMULATION)
        ok(f['evidence']['layers_not_zeroed'],
           f'naming the layers that still carry draws: '
           f'{f["evidence"]["layers_not_zeroed"]}')
        pops = {x['evidence']['population']
                for x in v['integrity']['findings']}
        ok(pops == {EI.POP_SIMULATION},
           f'and the optimizer pool is NOT implicated, because prevention '
           f'worked there: {sorted(pops)}')


# -- 5. governance vs strategy ---------------------------------------------
def test_governance_and_strategy_exclusions_are_not_the_same_thing():
    ok(EX.REASON_KIND[EX.WILL_NOT_PLAY] == EX.GOVERNANCE
       and EX.REASON_KIND[EX.BLOCKED_BY_REVIEW] == EX.GOVERNANCE
       and EX.REASON_KIND[EX.IDENTITY_UNRESOLVED] == EX.GOVERNANCE,
       'a player who may not enter is a GOVERNANCE exclusion')
    ok(EX.REASON_KIND[EX.PROJECTION_CUTOFF] == EX.STRATEGY
       and EX.REASON_KIND[EX.EXPLICIT_USER_EXCLUDE] == EX.STRATEGY,
       'a player the caller chose not to use is a STRATEGY exclusion')
    ok(EX.REASON_KIND[EX.NO_DK_POSITION] == EX.GOVERNANCE
       and EX.REASON_KIND[EX.NO_PROJECTION] == EX.GOVERNANCE,
       'and a player DraftKings will not accept, or one the model wrote no '
       'number for, is GOVERNANCE -- not a preference')
    led = EX.ExclusionLedger()
    led.add(gsis_id='A', name='A', team='T', reason=EX.WILL_NOT_PLAY)
    led.add(gsis_id='B', name='B', team='T', reason=EX.PROJECTION_CUTOFF)
    d = led.as_dict()
    ok(d['n_governance'] == 1 and d['n_strategy'] == 1
       and d['by_kind_and_reason'][EX.GOVERNANCE] == {EX.WILL_NOT_PLAY: 1},
       f'and they are counted apart: {d["by_kind_and_reason"]}')
    try:
        led.add(gsis_id='C', name='C', team='T', reason='JUST_BECAUSE')
        ok(False, 'an undeclared reason should be refused')
    except AssertionError as e:
        ok('not a declared exclusion reason' in str(e),
           'an undeclared reason is refused, because it could not be '
           'classified either way')


def test_every_pool_exclusion_path_writes_to_the_ledger():
    """A removal that is not in the ledger is a player who vanished."""
    src = (_REPO / 'nfl/dfs/classic/pool.py').read_text()
    import ast
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == 'build_pool')
    loop = next(n for n in ast.walk(fn) if isinstance(n, ast.For))
    continues = sum(1 for n in ast.walk(loop)
                    if isinstance(n, ast.Continue))
    drops = sum(1 for n in ast.walk(loop)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == 'drop')
    ok(continues == drops and drops >= 6,
       f'every exclusion path in the board loop records a ledger entry: '
       f'{drops} drop(s), {continues} continue(s)')
    # AST, not text: the docstring QUOTES the old rule to explain the
    # defect, and a substring test would fail on the explanation. That
    # mistake has been made twice in this migration already.
    literals = [n for n in ast.walk(tree)
                if isinstance(n, ast.Compare)
                and any(isinstance(c, ast.Constant)
                        and c.value in ('INACTIVE', 'OFFICIAL_INACTIVE',
                                        'INJURY_OUT')
                        for c in n.comparators)]
    ok(not literals,
       f'no string-literal availability comparison EXECUTES in the pool: '
       f'{len(literals)}')
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == 'will_not_play']
    ok(calls, f'it asks the canonical membership test instead: '
              f'{len(calls)} call site(s)')


# -- 6. coverage restoration ------------------------------------------------
def test_the_code_is_advertised_again_and_checked_on_a_dfs_load():
    ok(EI.C_INACTIVE_IN_POOL in GATE.ADVERTISED_INTEGRITY,
       'the code is back in the gate\'s advertised coverage')
    ok(EI.C_INACTIVE_IN_POOL not in GATE.RELINQUISHED_CODES,
       'and out of RELINQUISHED_CODES')
    spec = GATE.ADVERTISED_INTEGRITY[EI.C_INACTIVE_IN_POOL]
    ok(spec['owner'] == IC.OWNER_ELIGIBILITY
       and spec['producer'].endswith('will_not_play_in_dfs_populations'),
       f'owned by the DFS eligibility boundary: {spec["producer"]}')
    with tempfile.TemporaryDirectory() as td:
        bdir, draws, rdir = slate(td)
        v = _val(build(bdir, draws, rdir))
        ok(v['integrity_coverage'][EI.C_INACTIVE_IN_POOL]
           == IC.CHECKED_AND_PASSING,
           'and on a DFS load it is actually CHECKED, not merely declared')
    from nfl.production.review import gated_projection as GP
    with tempfile.TemporaryDirectory() as td:
        d2, r2, _ = TRE.clean_slate(td)
        gv = _val(GP.load(d2, r2))
        ok(gv['integrity']['coverage'][EI.C_INACTIVE_IN_POOL]
           == IC.NOT_APPLICABLE,
           'while a plain gated load -- where no DFS population exists yet '
           '-- reads NOT_APPLICABLE with a reason, never passing')


def main():
    for t in (test_the_fixture_is_an_out_player_with_everything_else_in_order,
              test_the_out_player_is_excluded_recorded_and_verified,
              test_when_the_exclusion_is_defeated_the_producer_blocks_the_pool,
              test_the_gate_blocks_on_the_same_finding,
              test_a_zeroed_row_is_expected_and_a_live_one_is_not,
              test_governance_and_strategy_exclusions_are_not_the_same_thing,
              test_every_pool_exclusion_path_writes_to_the_ledger,
              test_the_code_is_advertised_again_and_checked_on_a_dfs_load):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
