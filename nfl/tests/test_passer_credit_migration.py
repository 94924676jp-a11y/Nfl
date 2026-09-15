"""Repair 5 -- the per-row box-score coherence fence, and the migration that
is supposed to satisfy it.

WHAT THIS MODULE ASSERTS
========================
1. A BOX SCORE IS A BOX SCORE, on every row of every scanned board:
   `cmp <= att`, `cmp + int <= att`, `ptd <= cmp`, `ptd <= att`,
   `cmp == 0 -> pyds == 0`, `rushing_td <= carries`. This is the reproduction.
   Run against the sealed corpus before the migration it FAILS and names the
   boards; run against the effective corpus after it, the five passing-line
   checks are zero.
2. The corpus scanned here is the SHARED one. `sealed_index.live_draw_files()`
   finds boards by content at any depth in either encoding. This module owns
   no glob; a private one is how 17 boards stayed invisible to three fences at
   once (`nfl/tests/test_sealed_corpus_census.py`).
3. EVERY SEALED BYTE SURVIVES THE MIGRATION. The tool is run for real, into a
   temporary output root, between two full sha256 snapshots of every file in
   every sealed run directory. "The seals were preserved" is then a
   measurement on the bytes, not a claim about a code path.
4. The migration is DETERMINISTIC: the same source board migrated twice
   produces identical arrays.
5. The migration CALLS the replacement rather than re-implementing it, and
   rewrites only `qb/cmp`, `qb/pyds` and `qb/ptd`. Every other matrix is
   identical to the source's.
6. A board the replacement REFUSES is declared by name and is never written
   half-migrated.
7. The upper tail is measured against a bound DERIVED from realised football,
   never a round number, and nothing anywhere is clipped to satisfy it.

WHAT IT DOES NOT ASSERT
=======================
Nothing here says any projection is good. A coherent box score can be a
worthless forecast. No equivalence margin is predeclared and no TOST is run,
so no check is written as "correct" or "stable": each is "N violations in M
cells".

RESIDUALS ARE RED, NOT ABSORBED. Two of these checks fail after the migration
and are expected to: the upper tail on quarterback-only sides, and
`rushing_td <= carries`. Neither is produced by the passing credit and neither
is repair 5's to fix. They are named, measured, attributed to the code that
owns them, and left failing -- because a fence whose baseline moves whenever
it is tripped is not a fence.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile

import numpy as np

_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.research import sealed_index as SI                     # noqa: E402
from nfl.tools import passer_credit_migration as M              # noqa: E402
from nfl.production.nonqb import football_engine as FE          # noqa: E402
from nfl.production.nonqb import shared_pass as SP              # noqa: E402

PASSED = FAILED = BLOCKED = 0

# The five properties the replacement credit function owns and asserts on the
# values it writes (football_engine.py:285-300). These are what repair 5 is
# accountable for driving to zero.
PASSING_LINE_CHECKS = ('cmp_within_att', 'cmp_plus_int_within_att',
                       'ptd_within_cmp', 'ptd_within_att',
                       'zero_cmp_zero_pyds')


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(cond)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def _scan(dirs):
    """Coherence over a set of directories, with the per-board breakdown."""
    tot = {n: 0 for n, _, _ in M.COHERENCE_CHECKS}
    cells = {'qb': 0, 'rushing': 0}
    offenders = []
    for d in dirs:
        ao = M.arrays_at(d)
        if ao.state is not State.PASS:
            offenders.append((str(d), {'LOAD': ao.code}))
            continue
        co = M.coherence(ao.value)
        if co.state is not State.PASS:
            offenders.append((str(d), {'SCAN': co.code}))
            continue
        v = co.value['violations']
        for k in tot:
            tot[k] += v.get(k, 0)
        for k in cells:
            cells[k] += co.value['cells'][k]
        hit = {k: n for k, n in v.items() if n}
        if hit:
            offenders.append((str(d), hit))
    return tot, cells, offenders


# ---------------------------------------------------------------- the fence


def test_a_the_reproduction_on_the_sealed_corpus_as_built():
    """The defect, on the boards exactly as they were sealed.

    This is a REGRESSION FENCE ON HISTORY and it is expected to find the
    violations: the sealed bytes are immutable and the migration does not and
    must not rewrite them. If this ever reads zero, either a seal was rewritten
    or the scan stopped scanning -- both are worse than the defect.
    """
    print('\nA. the sealed corpus, as built')
    files = M.corpus(include_replay=True)
    if not check('the shared corpus discovery returns boards', bool(files),
                 f'{len(files)}'):
        return
    tot, cells, off = _scan([f.parent for f in files])
    check('  the scan covered a non-zero number of qb cells', cells['qb'] > 0,
          f'{cells["qb"]}')
    n_pass = sum(tot[k] for k in PASSING_LINE_CHECKS)
    print(f'       {len(files)} boards, {cells["qb"]:,} qb cells, '
          f'{cells["rushing"]:,} rushing cells')
    for k, expr, _ in M.COHERENCE_CHECKS:
        print(f'       {expr:26s} {tot[k]:6d} violating cell(s)')
    check('  the old-credit defect is still present in the sealed bytes, '
          'which is what makes the migration necessary and what proves no '
          'seal was rewritten', n_pass > 0,
          f'{n_pass} passing-line violations across {len(off)} board(s)')
    print(f'       worst boards: '
          + ', '.join(f'{pathlib.Path(d).name}({sum(h.values())})'
                      for d, h in sorted(off, key=lambda x: -sum(x[1].values())
                                         if all(isinstance(v, int)
                                                for v in x[1].values()) else 0
                                         )[:4]))


def test_b_every_scanned_board_is_a_box_score_after_the_migration():
    """THE ACCEPTANCE BAR. Zero impossible passing-line cells, per family.

    Scanned here is the EFFECTIVE corpus: for every sealed board, the migrated
    artifact where one exists and the sealed board where none was needed. A
    board the replacement refused is excluded from this count and is asserted
    separately, by name, in test D -- excluded loudly, never dropped.
    """
    print('\nB. the effective corpus: every board is a box score')
    eo = M.effective_corpus()
    if eo.state is not State.PASS:
        blocked('the effective corpus is not derivable',
                f'{eo.code}: {eo.detail[:160]}')
        return
    rows = eo.value
    check('a migration has actually been recorded',
          bool((eo.evidence or {}).get('ledger_present')),
          f'{M.LEDGER.name} does not exist, so nothing has been migrated and '
          f'this fence is scanning the sealed corpus exactly as built. Run '
          f'`python3.12 nfl/tools/passer_credit_migration.py`.')
    check('every board on disk is accounted for in the migration ledger',
          len(rows) == len(M.corpus(include_replay=True)),
          f'{len(rows)} ledger rows against '
          f'{len(M.corpus(include_replay=True))} boards on disk')
    fams = {'MIGRATED': [], 'UNCHANGED': [], 'UNMIGRATABLE': []}
    for r in rows:
        fams[r['status']].append(pathlib.Path(_ROOT) / r['scan'])
    for name in ('MIGRATED', 'UNCHANGED'):
        if not fams[name]:
            blocked(f'{name} family is empty, so its zero is not a result',
                    'NO_BOARDS_IN_FAMILY')
            continue
        tot, cells, off = _scan(fams[name])
        n = sum(tot[k] for k in PASSING_LINE_CHECKS)
        print(f'       {name}: {len(fams[name])} board(s), '
              f'{cells["qb"]:,} qb cells')
        for k, expr, _ in M.COHERENCE_CHECKS:
            if k in PASSING_LINE_CHECKS:
                print(f'         {expr:26s} {tot[k]:6d}')
        check(f'  {name}: the scan covered a non-zero number of cells',
              cells['qb'] > 0, f'{cells["qb"]}')
        offend = [(d, h) for d, h in off
                  if any(k in PASSING_LINE_CHECKS for k in h)]
        check(f'  {name}: ZERO impossible passing-line cells', n == 0,
              f'{n} cell(s) across {len(offend)} board(s)')
        for d, h in sorted(offend,
                           key=lambda x: -sum(x[1].get(k, 0)
                                              for k in PASSING_LINE_CHECKS)):
            print('         ' + str(pathlib.Path(d).relative_to(_ROOT))
                  + '  ' + json.dumps({k: v for k, v in h.items()
                                       if k in PASSING_LINE_CHECKS}))


def test_c_the_rushing_identity_is_not_repair_5s_and_is_still_red():
    """`rushing_td <= carries`, measured and NOT absorbed.

    The passing credit does not touch the rushing layer, so the migration
    cannot fix this and does not claim to. It is measured here because the
    acceptance bar named it, and it is left FAILING with its owner named.

    WHAT IT ACTUALLY IS. Every violating cell has `0 < carries < 1` and
    `rushing_td == 1`. `rushing/carries` is stored as float64 and most of its
    cells are not integers, so the identity is being evaluated against a
    CONTINUOUS LEVEL rather than a count of carries -- the same int-vs-float
    mismatch X1_DRAW_PATHOLOGY_CENSUS.md section 2.5 records for
    `team_volume/team_carries`. Zero cells violate it once `carries` is
    rounded to a count, which is why the underlying defect asserted here is
    the integrality, not the comparison. Dealing an integer carry count is a
    change to the rushing allocation (`nfl/production/nonqb/rushing_a1.py`),
    which this workstream does not own.
    """
    print('\nC. rushing_td <= carries -- measured, attributed, left red')
    eo = M.effective_corpus()
    if eo.state is not State.PASS:
        blocked('the effective corpus is not derivable', eo.code)
        return
    dirs = [pathlib.Path(_ROOT) / r['scan'] for r in eo.value]
    tot, cells, _ = _scan(dirs)
    nonint = n_cells = 0
    for d in dirs:
        ao = M.arrays_at(d)
        if ao.state is not State.PASS or 'rushing__carries' not in ao.value:
            continue
        rc = ao.value['rushing__carries'].astype(float)
        n_cells += rc.size
        nonint += int((np.abs(rc - np.rint(rc)) > 1e-9).sum())
    check('the rushing scan covered a non-zero number of cells', n_cells > 0,
          f'{n_cells}')
    print(f'       rushing_td > carries: {tot["rushing_td_within_carries"]} '
          f'cell(s) of {cells["rushing"]:,}')
    print(f'       carries not an integer: {nonint:,} of {n_cells:,} '
          f'({nonint / max(n_cells, 1):.1%})')
    check('rushing/carries is a COUNT of carries', nonint == 0,
          f'{nonint:,} of {n_cells:,} cells are not integers, so '
          f'`rushing_td <= carries` is comparing a count against a continuous '
          f'level. Owner: the rushing allocation '
          f'(nfl/production/nonqb/rushing_a1.py). NOT repair 5.')
    check('rushing_td <= carries on every row',
          tot['rushing_td_within_carries'] == 0,
          f'{tot["rushing_td_within_carries"]} cell(s); every one has '
          f'0 < carries < 1 and rushing_td == 1. Downstream of the check '
          f'above. NOT repair 5.')


def test_d_a_board_the_replacement_refuses_is_declared_by_name():
    """An unmigratable board is a fine outcome. An undeclared one is not."""
    print('\nD. refusals are declared, not dropped')
    eo = M.effective_corpus()
    if eo.state is not State.PASS:
        blocked('the effective corpus is not derivable', eo.code)
        return
    bad = [r for r in eo.value if r['status'] == 'UNMIGRATABLE']
    if not bad:
        check('there are no unmigratable boards to declare', True,
              'every C3 board migrated')
        return
    print(f'       {len(bad)} board(s) refused:')
    for r in bad:
        codes = {x['code'] for x in (r.get('refusals') or [])}
        print(f'        - {r["source"]}  {sorted(codes)}')
    check('every refusal carries a NAMED code and a team',
          all((r.get('refusals') and
               all(x.get('code') and x.get('team') for x in r['refusals']))
              for r in bad),
          'a refusal without a code is an unexplained drop')
    check('  and every refusal is the upstream coupling gap the replacement '
          'refuses BY NAME rather than clipping',
          all(x['code'] == 'PASSER_CREDIT_EXCEEDS_COMPLETABLE_ATTEMPTS'
              for r in bad for x in r['refusals']),
          str(sorted({x['code'] for r in bad for x in r['refusals']})))


def test_e_the_migration_leaves_every_sealed_byte_alone():
    """Run the tool for real, into a temp root, between two hash snapshots."""
    print('\nE. the seals survive the migration, byte for byte')
    before = M.seal_snapshot(include_replay=True)
    if not check('the snapshot covers a non-zero number of sealed files',
                 len(before) > 0, f'{len(before)} files'):
        return
    tmp = tempfile.mkdtemp(prefix='p4-seal-proof-')
    try:
        o = M.run(include_replay=True, out_root=tmp, write=True)
        check('the migration ran', o.state is State.PASS,
              f'{o.state.value}[{o.code}]')
        after = M.seal_snapshot(include_replay=True)
        moved = sorted(k for k in before if before[k] != after.get(k))
        gone = sorted(set(before) - set(after))
        added = sorted(set(after) - set(before))
        check('  every sealed file has the same sha256 afterwards', not moved,
              f'{len(moved)} changed: {moved[:4]}')
        check('  no sealed file was removed', not gone, f'{gone[:4]}')
        check('  no file was added inside a sealed run directory', not added,
              f'{added[:4]}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_f_the_migration_is_deterministic_and_rewrites_only_three_matrices():
    print('\nF. determinism, and the blast radius of the rewrite')
    eo = M.effective_corpus()
    if eo.state is not State.PASS:
        blocked('the effective corpus is not derivable', eo.code)
        return
    mig = [r for r in eo.value if r['status'] == 'MIGRATED']
    if not mig:
        blocked('no migrated board to re-run', 'NO_MIGRATED_BOARD')
        return
    src = pathlib.Path(_ROOT) / mig[0]['source']
    a = M.migrate(src, out_root=tempfile.gettempdir(), write=False)
    b = M.migrate(src, out_root=tempfile.gettempdir(), write=False)
    if not check('a migrated board re-migrates', a.state is State.PASS
                 and b.state is State.PASS,
                 f'{a.state.value}[{a.code}] / {b.state.value}[{b.code}]'):
        return
    same = all(np.array_equal(a.value['arrays'][k], b.value['arrays'][k])
               for k in a.value['arrays'])
    check('  two runs on the same board produce identical arrays', same,
          'the declared stream is not reproducible')
    check('  and the same migrated run id', a.value['run_id'] == b.value['run_id'],
          f'{a.value["run_id"]} vs {b.value["run_id"]}')
    so = M.arrays_at(src)
    if so.state is not State.PASS:
        blocked('the source draws did not load', so.code)
        return
    changed = sorted(k for k in so.value
                     if not np.array_equal(np.asarray(so.value[k]),
                                           np.asarray(a.value['arrays'][k])))
    check('  only qb/cmp, qb/pyds and qb/ptd differ from the source',
          set(changed) <= set(M.CREDITED), f'also changed: '
          f'{sorted(set(changed) - set(M.CREDITED))}')
    check('  and all three of them did change', set(M.CREDITED) <= set(changed),
          f'unchanged: {sorted(set(M.CREDITED) - set(changed))}')


def test_g_the_replacement_is_called_not_reimplemented():
    print('\nG. the repair in the tree is the repair being applied')
    import ast
    src = pathlib.Path(M.__file__).read_text()
    tree = ast.parse(src)
    called = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            called.add(f.attr if isinstance(f, ast.Attribute)
                       else getattr(f, 'id', ''))
    check('the migration CALLS credit_passing_line',
          'credit_passing_line' in called,
          f'the replacement is never called; calls seen: '
          f'{sorted(c for c in called if "credit" in c)}')
    check('  and never calls the superseded credit',
          'credit_to_passers' not in called,
          'the superseded function is called from the migration body')
    check('  and the replacement still declares coherence by construction, '
          'so "by construction" stays a claim anyone can check',
          'coherent_by_construction' in pathlib.Path(FE.__file__).read_text()
          and all(s in (FE.credit_passing_line.__doc__ or '')
                  for s in ('hypergeometric', 'COMPLETION share')),
          'football_engine.credit_passing_line no longer declares the scheme '
          'this migration is applying')
    check('  and shared_pass records that its credit is superseded',
          getattr(SP, 'CREDIT_TO_PASSERS_STATUS', '').startswith('SUPERSEDED'),
          'shared_pass.credit_to_passers carries no supersession marker, so a '
          'caller has nothing to read')


def test_h_the_upper_tail_is_measured_against_a_derived_bound():
    """The bound is derived from realised football and nothing is clipped."""
    print('\nH. the upper tail, against a bound derived from realised games')
    bo = M.historical_tail_bound()
    if bo.state is not State.PASS:
        blocked('the tail bound is not derivable',
                f'{bo.code}: {bo.detail[:160]}')
        return
    b = bo.value
    print(f'       derivation: {b["n_history"]} realised QB game-lines with a '
          f'completion, max {b["observed_max"]:.0f} yards, '
          f'{b["exceedances_in_history"]} above {b["record"]:.0f}')
    print(f'       rule of three -> 95% one-sided limit on the exceedance '
          f'rate {b["max_exceedance_rate"]:.3e}')
    check('the bound rests on a non-trivial history', b['n_history'] >= 1000,
          f'{b["n_history"]}')
    check('  and on zero realised exceedances of the record, which is what '
          'makes the rule of three the right limit',
          b['exceedances_in_history'] == 0,
          f'{b["exceedances_in_history"]}')
    eo = M.effective_corpus()
    if eo.state is not State.PASS:
        blocked('the effective corpus is not derivable', eo.code)
        return
    # Scoped to the same boards as test B: a board the replacement REFUSED is
    # declared in test D and is not counted here either, so the two fences do
    # not disagree about what the corpus is.
    agg, refused = {}, {}
    for r in eo.value:
        d = pathlib.Path(_ROOT) / r['scan']
        ao, so = M.arrays_at(d), M.side_map_from(d)
        if ao.state is not State.PASS or so.state is not State.PASS:
            continue
        t = M.tail_scan(ao.value, so.value)
        if t.state is not State.PASS:
            continue
        into = refused if r['status'] == 'UNMIGRATABLE' else agg
        for fam, v in t.value.items():
            a = into.setdefault(fam, {'cells': 0, 'above_record': 0,
                                      'above_99_per_cmp': 0, 'max': 0.0})
            a['cells'] += v['cells']
            a['above_record'] += v['above_record']
            a['above_99_per_cmp'] += v['above_99_per_cmp']
            a['max'] = max(a['max'], v['max'])
    if refused:
        print('       declared UNMIGRATABLE boards, counted apart: '
              + '; '.join(f'{k} {v["above_record"]}/{v["cells"]:,} above the '
                          f'record, {v["above_99_per_cmp"]} outside 99*cmp'
                          for k, v in sorted(refused.items())))
    if not check('the tail scan covered at least one side family',
                 len(agg) >= 1, f'{sorted(agg)}'):
        return
    for fam, v in sorted(agg.items()):
        rate = v['above_record'] / max(v['cells'], 1)
        print(f'       {fam}: {v["above_record"]} of {v["cells"]:,} above '
              f'{b["record"]:.0f} ({rate:.3e}), max {v["max"]:.0f}')
        check(f'  {fam}: the hard rule bound abs(pyds) <= 99*cmp holds',
              v['above_99_per_cmp'] == 0,
              f'{v["above_99_per_cmp"]} cell(s) outside a bound no football '
              f'game can be outside')
        check(f'  {fam}: the record-exceedance rate is inside the derived '
              f'95% limit', rate <= b['max_exceedance_rate'],
              f'{rate:.3e} against {b["max_exceedance_rate"]:.3e}, max draw '
              f'{v["max"]:.0f} yards. The passing credit does not generate '
              f'this: it is qb2_lib.py:306-307, PY = CMP * ypc_d, a game-level '
              f'yards-per-completion ratio resampled whole and multiplied by '
              f'an independently drawn completion count. NOT repair 5, and '
              f'NOT to be fixed by clipping.')


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
