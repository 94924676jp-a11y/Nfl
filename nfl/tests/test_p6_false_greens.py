"""P6 false-green reproductions. EVERY FAILING CHECK HERE IS DELIBERATE.

READ THIS BEFORE "FIXING" ANYTHING IN THIS FILE.

This module contains one reproduction per ACTIVE false green found by the P6
audit (`nfl/research/v4/p6/P6_INVARIANT_MANIFEST.md`). A false green is a check
that reports success it has not earned: a tautology that cannot fail, a fence
that scans less than it claims, a refusal read as a pass, a source window that
stops covering what it names, a built column that is structurally constant.

So these checks FAIL ON PURPOSE, and a red suite here is the correct state
until the module each one names is repaired BY ITS OWNER. P6 does not own the
production and research modules implicated below and deliberately did not touch
them; the defect belongs to the owner, the reproduction belongs here.

DO NOT make this file green by weakening a check. That is the exact move this
repository has already paid for twice: `test_refbands` was once cheapest to
green by deleting the comment it caught, and `test_r5_active_pool` reported a
repair as missing because the file it read got longer. If a finding is wrong,
delete the whole function and say in writing why the defect is not real. If it
is right, the repair goes in the module named in the docstring, and then this
check turns green by itself.

The findings, in the order a reader would have trusted them:

  P6-FG-1  nfl/research/same_day_retrospective.py:803
           nfl/research/v2/d7/d7_central_tendency.py:289
           nfl/research/market_outcome_audit.py:189
           `cfg.glob('*/board.json')` hard-codes one directory level and sees
           104 of the 121 sealed boards. Same defect, same count, as the three
           corpus fences already repaired in `nfl/research/sealed_index.py` --
           those were repaired for the DRAW files and these board readers were
           not. D7_ROWS_ALL_SEALS_2026W1.csv is named ALL_SEALS and holds one
           seal for 2026_01_SF_LA against four to eight for every other game.

  P6-FG-2  nfl/research/q6/forward_chain.py:489
           nfl/research/q9b/family.py:282
           `recon_error` is `|multinomial(n, p).sum() - n|`, which numpy
           guarantees is zero. Published as exactly 0.0 on 200,001 Q6 rows and
           104,130 Q9B rows, where it reads as "the allocator reconciles to the
           team total on every draw". It reconciles numpy.

  P6-FG-3  nfl/research/track1/build_state_panel.py:160
           The per-QB scramble column counts `qb_scramble` against
           `passer_player_id`, and a scramble play carries no passer id. One
           scramble across 4,024 QB-games. This is the SAME root cause q7
           found, repaired and documented in `Q7_PANEL_SUPERSESSION.json`;
           track1 carries it still and has no supersession record.

  P6-FG-4  nfl/research/refbands/build_refbands.py:84
           `starter_class` is written with `r.get(k, '')` before any row has
           the key, so the published USAGE_PANEL carries the column empty in
           all 21,558 rows. `write()` refuses zero bytes and not an empty
           column.

  P6-FG-5  nfl/research/v3/h1/h1_frame.py:40
           reads `q7/q7_qb_game.csv.gz`, which `q7/panel.py:102` names
           SUPERSEDED_QB and `Q7_PANEL_SUPERSESSION.json` declares superseded
           with its sha256. That record enumerates the ARTIFACTS drawn from
           the old panel; it does not enumerate the CODE that still reads it,
           and h1_frame's crosscheck therefore reconciles against the
           1-scramble panel rather than the 5,864-scramble repair.

  P6-FG-6  nfl/tests/test_capture_manifest_integrity.py:191
           nfl/tests/test_v1_entrypoint_integration.py:208
           nfl/tests/test_v1_game_stream_separation.py:143
           Three "the guard fails when bypassed" proofs that compare string
           literals written in the test body, or re-seed one RNG twice. None
           calls the code it claims to be proving load-bearing.

  P6-FG-7  nfl/tests/test_v1_entrypoint_integration.py:195
           nfl/tests/test_appearance_staging.py:187
           A fixed-width source window carrying a NEGATIVE assertion
           (`X not in window`). A positive windowed assertion fails falsely
           when the file grows -- that is the R5 defect and it is loud. A
           negative one PASSES falsely when the file grows, and is silent.
"""
from __future__ import annotations

import ast
import collections
import csv
import gzip
import os
import pathlib
import sys

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from nfl.research import allocation_residual as AR                 # noqa: E402

PASSED = FAILED = BLOCKED = 0
LIVE = _ROOT / 'nfl' / 'research' / 'live'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        # The detail on a passing check is the FAILURE message and printing it
        # beside "ok" reads as a failure to a skimming reader.
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    """Counted apart and never as a pass. `test_volatility.py`'s construction."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


# ==========================================================================
# P6-FG-1  silent narrowing: a board fence that scans one level
# ==========================================================================
def test_fg1_the_board_selectors_see_every_sealed_board():
    """OWNER: whoever owns same_day_retrospective / d7 / market_outcome_audit.

    The repair already exists one directory away:
    `nfl.research.sealed_index.live_draw_files()` finds sealed artifacts at ANY
    depth and its docstring explains why depth, not extension, was the cause.
    These three board readers kept the pre-repair shape.
    """
    print('\nP6-FG-1. cfg.glob("*/board.json") vs any depth')
    if not LIVE.exists():
        blocked('the sealed live tree', 'nfl/research/live absent')
        return
    one = deep = 0
    missed = []
    for gdir in sorted(p for p in LIVE.iterdir() if p.is_dir()):
        for cfg in sorted(p for p in gdir.iterdir() if p.is_dir()):
            a = set(cfg.glob('*/board.json'))
            b = set(cfg.rglob('board.json'))
            one += len(a)
            deep += len(b)
            missed += [str(p.relative_to(LIVE)) for p in sorted(b - a)]
    check('there is something to measure', deep > 0, f'{deep} board(s)')
    check('the one-level glob these three modules use finds every sealed '
          'board', one == deep,
          f'ONE_LEVEL_GLOB_NARROWS_THE_FRAME: {one} of {deep}; missed '
          f'{missed[:6]}')
    r8_one = r8_deep = 0
    for gdir in sorted(p for p in LIVE.iterdir() if p.is_dir()):
        for cfg in sorted(gdir.glob('*_V1_CANDIDATE_R8')):
            r8_one += len(list(cfg.glob('*/board.json')))
            r8_deep += len(list(cfg.rglob('board.json')))
    check('  and every R8 board in particular', r8_one == r8_deep,
          f'R8_BOARDS_MISSED: {r8_one} of {r8_deep}')
    # The source shape, named so the repair has an address.
    for rel, ln in (('nfl/research/same_day_retrospective.py', 803),
                    ('nfl/research/v2/d7/d7_central_tendency.py', 289),
                    ('nfl/research/market_outcome_audit.py', 189)):
        p = _ROOT / rel
        if not p.exists():
            blocked(rel, 'module absent')
            continue
        s = p.read_text()
        check(f'  {rel} no longer hard-codes one level',
              "glob('*/board.json')" not in s and
              'glob(f\'*/board.json\')' not in s,
              'FIXED_DEPTH_BOARD_GLOB still present')


def test_fg1b_the_all_seals_artifact_is_not_all_seals():
    """The consequence, measured on the published artifact rather than argued."""
    print('\nP6-FG-1b. D7_ROWS_ALL_SEALS_2026W1.csv against the tree')
    p = _ROOT / 'nfl' / 'research' / 'v2' / 'd7' / 'D7_ROWS_ALL_SEALS_2026W1.csv'
    if not p.exists():
        blocked('D7_ROWS_ALL_SEALS_2026W1.csv', 'artifact absent')
        return
    rows = list(csv.DictReader(p.open()))
    check('the artifact has rows', len(rows) > 0, f'{len(rows)}')
    col = 'run_id' if 'run_id' in (rows[0] if rows else {}) else None
    seals = collections.defaultdict(set)
    for r in rows:
        seals[r['game_id']].add(r.get(col) or r.get('seal_written_at'))
    sf = seals.get('2026_01_SF_LA', set())
    others = [len(v) for k, v in seals.items() if k != '2026_01_SF_LA']
    on_disk = len(list((LIVE / '2026_01_SF_LA').rglob('board.json'))) \
        if (LIVE / '2026_01_SF_LA').exists() else 0
    check('SF_LA is not the one game in the slate with a single seal, while '
          'ten boards sit in its directory',
          not (len(sf) == 1 and others and min(others) > 1),
          f'ALL_SEALS_IS_NOT_ALL_SEALS: SF_LA contributes {len(sf)} seal(s) '
          f'against {min(others) if others else 0}-{max(others) if others else 0} '
          f'elsewhere, with {on_disk} board.json on disk')


# ==========================================================================
# P6-FG-2  tautology: a reconciliation statistic that reconciles numpy
# ==========================================================================
def _recon(T, budget):
    """The published statistic, transcribed from q9b/family.py:282."""
    return float(np.abs(T.sum(axis=1) - budget).max())


def test_fg2_the_reconciliation_error_can_detect_a_wrong_allocation():
    """OWNER: whoever owns nfl/research/q6 and nfl/research/q9b.

    q7/panel.py already wrote the general lesson down: composing `db = att +
    sacks + scr` and then asserting `att + sacks + scr == db` "cannot drift
    from itself", and what it cannot do is notice that one of the three terms
    is structurally zero. The reconciliation statistic here is the same shape
    against numpy's multinomial contract.
    """
    print('\nP6-FG-2. recon_error under a maximally wrong allocation')
    rng = np.random.default_rng(20260915)
    n_draws, n_players, budget_scalar = 64, 5, 30
    budget = np.full(n_draws, budget_scalar, dtype=float)
    P = np.full((n_draws, n_players), 1.0 / n_players)
    T = np.array([rng.multinomial(budget_scalar, P[d]) for d in range(n_draws)])
    check('a correct allocation scores zero', _recon(T, budget) == 0.0,
          str(_recon(T, budget)))
    # 1. every unit onto one player: the worst possible allocation.
    one = np.zeros_like(T)
    one[:, 0] = budget_scalar
    # 2. a player silently dropped, his mass handed to his neighbour.
    drop = T.copy()
    drop[:, 1] += drop[:, 2]
    drop[:, 2] = 0
    # 3. the budget itself wrong, and the allocation built from the wrong one.
    wrong_budget_scalar = budget_scalar * 3
    wb = np.array([rng.multinomial(wrong_budget_scalar, P[d])
                   for d in range(n_draws)])
    # THE TAUTOLOGY, KEPT AND INVERTED. These two assertions used to read
    # `_recon(...) > 0` and FAILED, which is how the defect was reported. The
    # statistic is now replaced rather than patched, so what must be preserved
    # here is the DEMONSTRATION that the old one was inert -- if either of
    # these ever stops being 0.0, the transcription in `_recon` has drifted
    # from what q9b/family.py:282 actually published and this file is lying
    # about the history it exists to record.
    check('HISTORY: the old statistic could not see one player given every '
          'unit', _recon(one, budget) == 0.0, str(_recon(one, budget)))
    check('HISTORY: nor a player deleted and his mass moved',
          _recon(drop, budget) == 0.0, str(_recon(drop, budget)))

    # AND THE REPLACEMENT, on exactly the same seeded violations.
    z_ok = AR.allocation_residual_z(T, P, budget)
    z_one = AR.allocation_residual_z(one, P, budget)
    z_drop = AR.allocation_residual_z(drop, P, budget)
    null = AR.null_quantiles(n_players=n_players, budget=budget_scalar,
                             n_draws=n_draws)
    print(f'       null over {null["n_seeds"]} seeds: median '
          f'{null["median"]:.2f}, p95 {null["p95"]:.2f}, max {null["max"]:.2f}')
    check('  the replacement scores a CORRECT allocation inside its own null',
          z_ok <= null['max'], f'z={z_ok:.4f} vs null max {null["max"]:.4f}')
    check('  and sees one player given every unit',
          z_one > null['max'], f'z={z_one:.4f} vs null max {null["max"]:.4f}')
    check('  and sees a player deleted and his mass moved',
          z_drop > null['max'], f'z={z_drop:.4f} vs null max {null["max"]:.4f}')
    # A STATISTIC WITH NO NULL IS A NUMBER NOBODY CAN READ. The separation is
    # reported, not thresholded: nothing in production gates on this.
    check('  and the separation is an order of magnitude, not a hair',
          min(z_one, z_drop) > 5 * null['max'],
          f'one={z_one:.2f} drop={z_drop:.2f} null_max={null["max"]:.2f}')
    # THE HONEST LIMIT, ASSERTED SO IT CANNOT BE FORGOTTEN. The replacement
    # scores the deal against the intent it was HANDED. Wrong intent, faithfully
    # dealt, reads clean -- reconciliation is not validation.
    wrong_P = np.zeros_like(P)
    wrong_P[:, 0] = 1.0
    faithful = np.zeros_like(T)
    faithful[:, 0] = budget_scalar
    check('  but a WRONG intent, faithfully dealt, still reads clean -- '
          'reconciliation is not validation',
          AR.allocation_residual_z(faithful, wrong_P, budget) == 0.0,
          str(AR.allocation_residual_z(faithful, wrong_P, budget)))
    # REPORTED AS A PASS AND KEPT, BECAUSE IT BOUNDS THE CLAIM. The statistic
    # is not inert in every direction: an allocation built to one budget and
    # scored against a different one IS caught. What it cannot see is any
    # error that preserves the total -- which is every allocation error.
    check('an allocation built to a DIFFERENT budget than it is scored '
          'against is caught, so the statistic is not inert in every '
          'direction', _recon(wb, budget) > 0,
          f'recon_error={_recon(wb, budget)}')
    # AND THE PUBLISHED ARTIFACTS. The producers now emit
    # `alloc_residual_z`; these files still carry the old constant column
    # because they have not been regenerated yet. That is a REPUBLICATION debt,
    # not a code defect, and it stays visible here until the pipelines are
    # re-run -- deleting the check would hide the fact that every consumer of
    # these three files is still reading 385,446 rows of zero.
    for rel, col in (('nfl/research/q6/Q6_DIAGNOSTICS.csv.gz', 'recon_error'),
                     ('nfl/research/q9b/Q9B_FAMILY_ROWS.csv.gz', 'recon_error'),
                     ('nfl/research/q9/Q9_DIAGNOSTICS.csv',
                      'max_reconciliation_error')):
        p = _ROOT / rel
        if not p.exists():
            blocked(rel, 'artifact absent')
            continue
        op = gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()
        with op as fh:
            vals = collections.Counter(r[col] for r in csv.DictReader(fh)
                                       if col in r)
        check(f'  {os.path.basename(rel)}:{col} is not a constant column',
              len(vals) > 1,
              f'CONSTANT_RECONCILIATION_STATISTIC: '
              f'{list(vals)[0]!r} on {sum(vals.values())} rows')


# ==========================================================================
# P6-FG-3 / P6-FG-4  structurally degenerate built columns
# ==========================================================================
def _degenerate(path, col, floor=0.999):
    op = gzip.open(path, 'rt') if str(path).endswith('.gz') else open(path)
    with op as fh:
        vals = collections.Counter(r.get(col) for r in csv.DictReader(fh))
    n = sum(vals.values())
    top, tn = vals.most_common(1)[0]
    return n, top, tn, (tn / n if n else 1.0) >= floor


def _declared_superseded():
    """Artifacts a supersession record names, with the record that names them.

    A DECLARED exclusion is honoured and an undeclared one is not, which is the
    same rule `sealed_index.FENCE_EXCLUDED_NAMESPACES` follows. q7 found this
    exact defect in its own panel, repaired it into `q7_qb_game_r2.csv.gz` and
    wrote `Q7_PANEL_SUPERSESSION.json` saying so in full, including -- in its
    own words -- that "the only dropback check was the composed identity
    att + sacks + scr == db, which is true of any three numbers". Flagging the
    retained file again would be this audit failing to read the repository's
    own record.
    """
    import json as _json
    out = {}
    for rec in (_ROOT / 'nfl').rglob('*SUPERSESSION*.json'):
        try:
            d = _json.loads(rec.read_text())
        except ValueError:
            continue
        for k in (d.get('superseded_artifacts') or {}):
            out[k] = str(rec.relative_to(_ROOT))
    return out


def test_fg3_built_count_columns_are_not_structurally_zero():
    """OWNER of track1: nfl/research/track1/build_state_panel.py:160.

    A count column that is one non-zero value across four thousand games is
    not a measurement, and nothing in the build refused it. The root cause is
    the one q7 already found and wrote down: `qb_scramble` is counted against
    `passer_player_id`, and a scramble play carries no passer id -- it carries
    `rusher_player_id`, which `build_state_panel.py` does not even read
    (its column list at line 61 omits it).
    """
    print('\nP6-FG-3. per-QB scramble columns')
    sup = _declared_superseded()
    check('(setup) a supersession record is read rather than assumed',
          isinstance(sup, dict), f'{len(sup)} declared superseded artifact(s)')
    for rel, col, why in (
            ('nfl/research/track1/state_qb_game.csv.gz', 'scrambles',
             'build_state_panel.py:160 counts qb_scramble against '
             'passer_player_id, which a scramble play does not carry'),
            ('nfl/research/q7/q7_qb_game.csv.gz', 'scr',
             'the pre-repair q7 panel')):
        p = _ROOT / rel
        if not p.exists():
            blocked(rel, 'artifact absent')
            continue
        if rel in sup:
            print(f'  ..   {rel} is DECLARED superseded by {sup[rel]} and '
                  f'retained on purpose -- not counted against anyone')
            continue
        n, top, tn, bad = _degenerate(p, col)
        check(f'{os.path.basename(rel)}:{col} is not structurally constant',
              not bad,
              f'STRUCTURALLY_DEGENERATE_COLUMN: {top!r} in {tn} of {n} rows. '
              f'{why}')


def test_fg4_a_published_panel_column_is_not_empty_in_every_row():
    """OWNER: nfl/research/refbands/build_refbands.py."""
    print('\nP6-FG-4. USAGE_PANEL.starter_class')
    p = _ROOT / 'nfl' / 'research' / 'refbands' / 'USAGE_PANEL.csv.gz'
    if not p.exists():
        blocked('USAGE_PANEL.csv.gz', 'artifact absent')
        return
    n, top, tn, bad = _degenerate(p, 'starter_class')
    check('starter_class carries a value', not (bad and top in ('', None)),
          f'EMPTY_PUBLISHED_COLUMN: {top!r} in {tn} of {n} rows. '
          f'panel_csv() writes r.get("starter_class", "") and refbands.py:493 '
          f'assigns the key later, so the default is what ships.')


def test_fg5_no_module_reads_an_artifact_its_owner_calls_superseded():
    """OWNER: nfl/research/v3/h1/h1_frame.py."""
    print('\nP6-FG-5. a superseded panel still has a reader')
    panel = _ROOT / 'nfl' / 'research' / 'q7' / 'panel.py'
    h1 = _ROOT / 'nfl' / 'research' / 'v3' / 'h1' / 'h1_frame.py'
    if not (panel.exists() and h1.exists()):
        blocked('q7/panel.py or v3/h1/h1_frame.py', 'module absent')
        return
    ps = panel.read_text()
    check('(setup) q7 declares a superseded panel', 'SUPERSEDED_QB' in ps)
    sup = [ln for ln in ps.splitlines() if 'SUPERSEDED_QB' in ln and '=' in ln]
    name = 'q7_qb_game.csv.gz' if any('q7_qb_game.csv.gz' in l for l in sup) \
        else None
    check('(setup) the superseded file is named', name is not None, str(sup))
    if name is None:
        return
    check('no other module reads the superseded panel',
          name not in h1.read_text(),
          f'SUPERSEDED_ARTIFACT_STILL_READ: v3/h1/h1_frame.py reads {name}, '
          f'whose scramble column q7 repaired into q7_qb_game_r2.csv.gz. '
          f'Q7_PANEL_SUPERSESSION.json lists the artifacts drawn from the old '
          f'panel and does not list the code still reading it.')


# ==========================================================================
# P6-FG-6  tautology: a bypass proof that bypasses nothing
# ==========================================================================
_BYPASS_FN = ('test_the_guards_fail_when_bypassed',
              'test_the_guard_fails_when_bypassed')


_REPO_MODULE_NAMES = None


def _repo_module_names():
    """Bare module names that resolve to a file inside this repository.

    Several test modules `sys.path.insert` a directory and then
    `import a1_lib as A` or `import capture_vintage as cv`, so a rule that
    only recognised `nfl.` prefixes would call those modules "reaches no
    production code" when they plainly do. Over-reporting here would be this
    audit committing the defect it is auditing, in reverse.
    """
    global _REPO_MODULE_NAMES
    if _REPO_MODULE_NAMES is None:
        _REPO_MODULE_NAMES = {
            q.stem for q in (_ROOT / 'nfl').rglob('*.py')
            if 'tests' not in q.parts}
        _REPO_MODULE_NAMES |= {
            q.stem for q in (_ROOT / 'sportsplatform').rglob('*.py')}
    return _REPO_MODULE_NAMES


def _production_aliases(tree):
    """Every alias in this file bound to code that lives in this repository,
    at module level or inside a function, by dotted path or by bare name."""
    repo = _repo_module_names()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                head = a.name.split('.')[0]
                if head in ('nfl', 'sportsplatform') or \
                        a.name.split('.')[-1] in repo:
                    out.add((a.asname or a.name).split('.')[0])
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ''
            if mod.startswith('nfl.tests'):
                continue
            if mod.split('.')[0] in ('nfl', 'sportsplatform') \
                    or mod.split('.')[-1] in repo:
                for a in n.names:
                    out.add(a.asname or a.name)
    return out


def test_fg6_a_bypass_proof_executes_the_thing_it_proves():
    """OWNERS: the six modules named in the failure detail.

    `nfl/tests/bypass.py` exists precisely for this and says why: "A test that
    would still pass with the guard deleted is testing nothing." A function
    named for that standard must do ONE of two things -- go through
    `guard_bypassed` / `assert_guard_is_load_bearing`, or at minimum call the
    production symbol it is proving load-bearing. A function that does neither
    is asserting over values it constructed itself, or over a copy of the
    guard's logic re-typed into the test body, and it would pass with the real
    guard deleted.

    THE CRITERION IS DELIBERATELY WEAK so that it cannot over-report: reaching
    ANY production alias once is enough to clear it. `test_v1_scramble_
    coherence` clears on one `SC.couple(...)` call even though two of its three
    arms are numpy identities, and that is the right outcome for a mechanical
    check -- the remaining judgement belongs in the write-up, not here.
    """
    print('\nP6-FG-6. "fails when bypassed" functions that call nothing')
    offenders, cleared = [], 0
    for f in sorted((_ROOT / 'nfl' / 'tests').glob('test_*.py')):
        if f.name == os.path.basename(__file__):
            continue
        try:
            src = f.read_text()
            tree = ast.parse(src, str(f))
        except SyntaxError:
            continue
        aliases = _production_aliases(tree)
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            # NAMED BY SHAPE, NOT BY THE WORD "bypass" ALONE. `test_22_
            # bypass_batches_are_audit_evidence_not_the_control` is about a
            # domain object called a bypass batch and is not a guard proof;
            # requiring "guard" alongside excludes it without an exemption
            # list.
            nm = fn.name
            if not ('guard' in nm and ('bypass' in nm or 'fail' in nm)):
                continue
            nodes = list(ast.walk(fn))
            reaches = False
            for c in nodes:
                if not isinstance(c, ast.Call):
                    continue
                fu = c.func
                if isinstance(fu, ast.Name) and fu.id in (
                        'guard_bypassed', 'assert_guard_is_load_bearing'):
                    reaches = True
                if isinstance(fu, ast.Attribute) and isinstance(
                        fu.value, ast.Name) and fu.value.id in aliases:
                    reaches = True
                if isinstance(fu, ast.Name) and fu.id in aliases:
                    reaches = True
            const_cmp = sum(
                1 for n in nodes if isinstance(n, ast.Compare)
                and isinstance(n.left, ast.Constant)
                and all(isinstance(x, ast.Constant) for x in n.comparators))
            if reaches:
                cleared += 1
            else:
                offenders.append(
                    (f'{f.relative_to(_ROOT)}::{fn.name}',
                     f'{const_cmp} literal-vs-literal comparison(s), reaches '
                     f'no production alias of {sorted(aliases)[:4]}'))
    check('there are functions claiming the bypass standard',
          cleared + len(offenders) > 0,
          f'{cleared} clear, {len(offenders)} do not')
    check('every "fails when bypassed" proof reaches the code it claims to '
          'prove load-bearing', not offenders,
          'TAUTOLOGICAL_BYPASS_PROOF: '
          + '; '.join(f'{a} [{b}]' for a, b in offenders))


def test_fg6b_an_rng_reseeded_identically_proves_nothing():
    """The same defect wearing numpy. Stated as a measurement so the claim is
    not an opinion: the assertion holds for ANY seed, so it cannot be about
    the seed vector the test names."""
    print('\nP6-FG-6b. two identical seeds always agree')
    same = all(np.array_equal(
        np.random.default_rng([s, 1, 2]).binomial(1, 0.7, 200),
        np.random.default_rng([s, 1, 2]).binomial(1, 0.7, 200))
        for s in (1, 7, 20260908, 999999))
    check('(measurement) identical seeds agree for every seed tried, so the '
          'assertion is numpy\'s contract and not a property of this '
          'repository', same)
    f = _ROOT / 'nfl' / 'tests' / 'test_v1_game_stream_separation.py'
    if not f.exists():
        blocked('test_v1_game_stream_separation.py', 'module absent')
        return
    tree = ast.parse(f.read_text(), str(f))
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name == 'test_the_guard_fails_when_bypassed'), None)
    if fn is None:
        check('the tautological RNG proof is gone', True, 'function removed')
        return
    calls = {c.func.id if isinstance(c.func, ast.Name)
             else getattr(c.func, 'attr', '') for c in ast.walk(fn)
             if isinstance(c, ast.Call)}
    check('the stream-separation bypass proof calls the production seeding it '
          'claims to prove', bool(calls & {'_game_stream', 'targets_carries',
                                           'guard_bypassed',
                                           'assert_guard_is_load_bearing'}),
          f'TAUTOLOGICAL_BYPASS_PROOF: it calls {sorted(calls)} and reaches no '
          f'production seeding path')


# ==========================================================================
# P6-FG-7  a negative assertion over a fixed-width source window
# ==========================================================================
def _required_stage_window_logic(src, width=220):
    """`test_v1_entrypoint_integration::test_required_stages_still_halt`,
    transcribed. Returns the stages it would report as non-halting."""
    i = src.find('NONQB_CHAIN = (')
    if i < 0:
        return None
    window = src[i:i + width]
    return [r for r in ('qb_layer', 'team_environment', 'capture_validation',
                        'identity_resolution', 'joint_reconciliation',
                        'artifact_sealing', 'player_draws')
            if f"'{r}'" in window]


def test_fg7_a_negative_source_window_cannot_narrow_itself_into_a_pass():
    """OWNERS: test_v1_entrypoint_integration, test_appearance_staging.

    A POSITIVE windowed assertion ("the refusal is in this window") fails
    loudly when the file grows past the window -- that is exactly what
    happened to `test_r5_active_pool`, and its repair is documented in place.
    A NEGATIVE one ("the required stage is NOT in this window") goes the other
    way: the window stops covering the construct, the forbidden token is no
    longer inside it, and the check passes. Nothing announces it.

    This is demonstrated on a SYNTHETIC source rather than argued, and no
    production module is touched.
    """
    print('\nP6-FG-7. "not in window" over a fixed width')
    run = _ROOT / 'nfl' / 'production' / 'run_forecast.py'
    if not run.exists():
        blocked('run_forecast.py', 'module absent')
        return
    real = run.read_text()
    now = _required_stage_window_logic(real)
    check('(setup) the window logic finds the construct today', now is not None)
    check('(setup) and reports no required stage as non-halting today',
          now == [], str(now))
    # Seed the defect: a chain longer than the window with a required stage
    # placed beyond it. Every line the test greps for is present and wrong.
    pad = ',\n                   '.join(f"'filler_layer_{k}'" for k in range(12))
    seeded = ("NONQB_CHAIN = ('appearance', 'participation',\n"
              f"                   {pad},\n"
              "                   'qb_layer')\n")
    tail = _required_stage_window_logic(seeded)
    check('a required stage moved past the window is still caught',
          tail == ['qb_layer'],
          f'NEGATIVE_WINDOW_NARROWS_SILENTLY: the seeded chain declares '
          f"'qb_layer' non-halting at character "
          f"{seeded.find(chr(39) + 'qb_layer')} and the 220-character window "
          f'reports {tail}. The halting guarantee is proven by a substring '
          f'search over a region that shrinks relative to what it must cover.')
    # The staging leak guard, same shape, same direction.
    am = _ROOT / 'nfl' / 'production' / 'nonqb' / 'appearance_model.py'
    if not am.exists():
        blocked('appearance_model.py', 'module absent')
        return
    s = am.read_text()
    i = s.index('def stage_inputs')
    nxt = len(s)
    for k in range(i + 1, len(s)):
        if s.startswith('\ndef ', k) or s.startswith('\nclass ', k):
            nxt = k + 1
            break
    fn_len = nxt - i
    check('the 3000-character staging window covers exactly the function it '
          'names', fn_len == 3000,
          f'WINDOW_DOES_NOT_MATCH_ITS_SUBJECT: stage_inputs is {fn_len} '
          f'characters, so the window under-covers it when it grows past 3000 '
          f"(a new mkdtemp beyond that is invisible) and today over-covers it "
          f'by {3000 - fn_len} characters of neighbouring functions')


# ==========================================================================
# P6-FG-9  a production identity that restates its own definition
# ==========================================================================
def test_fg9_the_stat_contract_identities_are_not_their_own_definitions():
    """OWNER: nfl/production/stat_contract.py.

    `tabulate()` computes
        agg = {k: sum(c[t] for t in terms) for k, terms in AGGREGATES.items()}
    with AGGREGATES['dropbacks'] == ('pass_attempt', 'sack', 'scramble'), and
    then records
        ident['dropback_partition'] = (agg['dropbacks']
                                       == c['pass_attempt'] + c['sack']
                                       + c['scramble'])
    which is `X == X`. All three identities are that shape, so `broken` is
    always empty and STAT_CONTRACT_IDENTITY_BROKEN cannot be raised by this
    path. The docstring calls a failure "an arithmetic defect in this module";
    the arithmetic is Python's.

    THIS ONE IS MITIGATED AND STILL REAL. `VERIFIED_AGAINST` pins the corpus
    class counts and `test_stat_contract.py:96` re-measures them, so a
    `classify_play` regression IS caught -- elsewhere. What is not true is the
    thing a reader takes from `identities_hold`: that the partition was
    checked on the rows just counted.
    """
    print('\nP6-FG-9. stat_contract identities over random count vectors')
    try:
        from nfl.production import stat_contract as ST
    except Exception as exc:                                     # noqa: BLE001
        blocked('nfl.production.stat_contract', f'{type(exc).__name__}: {exc}')
        return
    rng = np.random.default_rng(20260915)
    held = 0
    trials = 2000
    for _ in range(trials):
        c = {k: int(v) for k, v in
             zip(ST.CLASSES, rng.integers(0, 10 ** 6, len(ST.CLASSES)))}
        agg = {k: sum(c[t] for t in terms)
               for k, terms in ST.AGGREGATES.items()}
        ident = {
            'dropback_partition': (agg['dropbacks'] == c['pass_attempt']
                                   + c['sack'] + c['scramble']),
            'att_raw_decomposition': (agg['att_raw'] == c['pass_attempt']
                                      + c['sack'] + c['spike']),
            'rush_attempt_partition': (agg['rush_attempts'] == c['scramble']
                                       + c['kneel'] + c['designed_rush']),
        }
        held += all(ident.values())
    check('(setup) the identities are transcribed from the module\'s own '
          'AGGREGATES', set(ST.AGGREGATES) >= {'dropbacks', 'att_raw',
                                               'rush_attempts'})
    check('there exists a class-count vector for which a stat-contract '
          'identity fails', held < trials,
          f'SELF_PROVING_IDENTITY: all three identities held on {held} of '
          f'{trials} RANDOM count vectors, including vectors no play stream '
          f'could produce. The check restates AGGREGATES rather than testing '
          f'anything the rows decided.')


# ==========================================================================
# P6-FG-8  WS11's FG-4, still length-only: the missing proof, supplied
# ==========================================================================
def test_fg8_the_frozen_module_hashes_are_recomputed_not_measured_for_length():
    """WS11 FG-4, re-checked 2026-09-15 and STILL LATENT.

    `test_q9b_model_family.py:368` asserts
    `len(ci['module_source_sha16']) >= 4 and all(len(v) == 16 ...)` -- the
    frozen hashes are checked for LENGTH and never recomputed, while
    `freeze._module_hash` sits in the same package. P6 does not own that
    module, so rather than edit it this function supplies the proof it lacks:
    the four hashes are recomputed against the live source and compared.

    It PASSES today, and that is the honest result -- all four still match, so
    the defect is that the freeze COULD stop describing the candidate it names
    without anything saying so, not that it already has. If this ever fails,
    the freeze and the code have parted company.
    """
    print('\nP6-FG-8. recompute the frozen module hashes')
    try:
        import importlib
        from nfl.research.q9b import freeze as F
    except Exception as exc:                                     # noqa: BLE001
        blocked('nfl.research.q9b.freeze', f'{type(exc).__name__}: {exc}')
        return
    art = _ROOT / 'nfl' / 'research' / 'q9b' / 'Q9_PROSPECTIVE_FREEZE.json'
    if not art.exists():
        blocked('Q9_PROSPECTIVE_FREEZE.json', 'artifact absent')
        return
    import json as _json

    def _find(o):
        if isinstance(o, dict):
            if 'module_source_sha16' in o:
                return o['module_source_sha16']
            for v in o.values():
                r = _find(v)
                if r:
                    return r
        return None

    stored = _find(_json.loads(art.read_text()))
    check('the freeze records module hashes', bool(stored), str(stored)[:60])
    if not stored:
        return
    for name, want in sorted(stored.items()):
        try:
            got = F._module_hash(importlib.import_module(name))
        except Exception as exc:                                 # noqa: BLE001
            blocked(f'{name}', f'{type(exc).__name__}: {exc}')
            continue
        check(f'  {name} still hashes to what the freeze recorded', got == want,
              f'FREEZE_NO_LONGER_DESCRIBES_THE_CANDIDATE: recorded {want}, '
              f'source now {got}')


# ==========================================================================
def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(
            f'{FAILED} P6 reproduction(s) are still failing. That is the '
            f'reported state of the repository, not a defect in this file. '
            f'See nfl/research/v4/p6/P6_INVARIANT_MANIFEST.md.')


if __name__ == '__main__':
    for _n in sorted(n for n in dict(globals()) if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    sys.exit(1 if FAILED else 0)
