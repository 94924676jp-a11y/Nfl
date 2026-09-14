"""A board row must carry a human-readable name, or say why it does not.

WHAT THIS MODULE EXISTS TO STOP COMING BACK

On 2026-09-14 `quality_gates.IDENTITY_DEPTH_ROLE_CONFLICT` withheld all 19
rows of the rebuilt DEN@KC board -- 20 findings, being 19 row findings plus the
board-scope escalation -- on one condition: no row carried a name.
`board.build` joined identity from the roster vintage and read `position` and
`team` out of it while leaving `full_name` in the file. Every other hard
finding on that board was a modelling question; this one was a product defect
with a one-column cause.

WHAT IS ASSERTED, IN ORDER OF HOW MUCH IT MATTERS

1. A NAME IS NEVER INVENTED. The modules resolve from capture blobs and
   nothing else: no dict literal of names in the source, no difflib, no
   rapidfuzz, no fuzzy matching on a person. Asserted on the AST, so a
   convenience table added later fails here rather than in a board.
2. AN UNRESOLVED ID STAYS UNRESOLVED AND SAYS SO. A row for a player no lawful
   capture names carries `name: None` and a `name_provenance` whose code is
   NAME_UNRESOLVED_AT_CUT, and the board lists him. A blank cell and a guessed
   name are the same lie told two ways.
3. NOTHING POST-CUT IS READ. Every capture consulted for a name is bounded by
   the board's own `as_of`, the same bound every other vintage takes.
4. THE REDUCED VINTAGE STILL WORKS. `capture/registry.py` reduces
   weekly_rosters to (season, week, team, gsis_id, position) and that
   reduction is deliberate -- its output bytes are the artifact identity. A
   board selecting the reduced blob must therefore resolve names from a second
   lawful capture, not fail and not fabricate.
5. EVERY NAME CARRIES PROVENANCE. Blob and column, per row.

WHAT IS NOT ASSERTED. Nothing here says a name is CORRECT. Correctness of a
vendor's spelling is not a property this repository can measure; what it can
measure is that the name came from a named blob observed before the cut.
"""
from __future__ import annotations

import ast
import csv
import gzip
import io
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import board as PB                            # noqa: E402
from nfl.product import names as NM                            # noqa: E402

PASSED = FAILED = BLOCKED = 0

CUT = '2026-09-14T20:58:33Z'
RAW = 'nfl/vintage/weekly_rosters.bdab6ecee12d44a4.raw.csv.gz'
REDUCED = 'nfl/vintage/weekly_rosters.bdab6ecee12d44a4.reduced.csv.gz'
# Six ids and the names an INDEPENDENT artifact gives them:
# nfl/research/v2/r2/R2_ELIGIBILITY_SNAPSHOT_2026_01_DEN_KC.json, whose
# full_roster_snapshot.rows map was built by a different tool from this one.
# They are here as a cross-check on the join, not as a source: nothing in
# nfl/product reads this dict, and a failure here means the two disagree, not
# that either is authoritative.
KNOWN = {'00-0033873': 'Patrick Mahomes',
         '00-0030506': 'Travis Kelce',
         '00-0038134': 'Kenneth Walker III',
         '00-0041013': 'Emmett Johnson',
         '00-0039067': 'Rashee Rice',
         '00-0039732': 'Bo Nix'}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    """A check that could not run. Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


def _p(rel):
    return pathlib.Path(_ROOT) / rel


# =========================================================== 1. never invented
def test_a_no_name_is_ever_invented():
    """Asserted on the AST of the two modules that join a name."""
    banned = {'difflib', 'rapidfuzz', 'fuzzywuzzy', 'Levenshtein', 'jellyfish'}
    for rel in ('nfl/product/names.py', 'nfl/product/board.py'):
        src = _p(rel).read_text()
        tree = ast.parse(src, rel)
        imported = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imported |= {a.name.split('.')[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                imported.add(n.module.split('.')[0])
        check(f'{rel} imports no fuzzy matcher', not (imported & banned),
              sorted(imported & banned))
        # A literal gsis_id in the source would be the first brick of a
        # hardcoded name table. Docstrings are excluded: naming the defect is
        # not committing it.
        docs = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                d = ast.get_docstring(n, clean=False)
                if d:
                    docs.add(d)
        lits = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and '00-00' in n.value and n.value not in docs]
        check(f'{rel} contains no gsis_id string literal, so it carries no '
              f'hardcoded name table', not lits, lits[:4])


# ========================================================= 2 & 5. provenance
def test_b_every_resolved_name_names_its_blob_and_column():
    if not _p(RAW).exists():
        blocked('raw roster vintage present', f'{RAW} absent')
        return
    NM.cache_clear()
    resolved, consulted = NM.resolve(CUT)
    check('the resolver answered for more than zero ids -- an empty map is an '
          'error, not a board with no people', bool(resolved), len(resolved))
    check('  and every capture it consulted is named with its observation '
          'time', bool(consulted) and all(c.get('blob') for c in consulted))
    bad = [g for g, v in resolved.items()
           if not v.get('blob') or not v.get('column')]
    check('every resolved id names the blob and the column that answered',
          not bad, bad[:4])
    cols = {v['column'] for v in resolved.values()}
    check('  and the column is one this module declares',
          cols <= set(NM.NAME_COLUMNS), sorted(cols))
    for gid, want in KNOWN.items():
        got = (resolved.get(gid) or {}).get('name')
        check(f'{gid} resolves to {want}, agreeing with the independent R2 '
              f'eligibility snapshot', got == want, repr(got))
    NM.cache_clear()


# ================================================== 3. nothing after the cut
def test_c_no_capture_after_the_cut_is_read():
    NM.cache_clear()
    cut = NM._parse(CUT)
    cands = NM._candidates(cut)
    if not cands:
        blocked('name captures lawful at the cut', 'no capture blob on disk')
        return
    late = [c for c in cands if c['_at'] is None or c['_at'] > cut]
    check('every capture consulted for a name was observed at or before the '
          'board cut', not late,
          [(c['blob'], c['observed_at']) for c in late][:3])
    check('  and a capture the manifest cannot date is refused under a cut '
          'rather than used unclocked',
          all(c['_at'] is not None for c in cands))
    early = NM._candidates(NM._parse('2020-01-01T00:00:00Z'))
    check('a cut before every capture resolves no names at all, rather than '
          'falling back to the newest file on disk', early == [], len(early))
    NM.cache_clear()
    check('  and the resolver agrees', NM.lookup('2020-01-01T00:00:00Z') == {})
    NM.cache_clear()


def test_d_precedence_is_chronological_not_glob_order():
    NM.cache_clear()
    cands = NM._candidates(NM._parse(CUT))
    if len(cands) < 2:
        blocked('two or more lawful captures', f'{len(cands)} on disk')
        return
    times = [c['_at'] for c in cands]
    check('captures are ordered oldest first, so the NEWEST lawful one is the '
          'one whose spelling survives', times == sorted(times))
    check('  and the last one consulted really is the newest',
          cands[-1]['_at'] == max(times))
    NM.cache_clear()


# ============================================ 4. the reduced vintage, and 2
def test_e_the_reduced_vintage_carries_no_name_and_says_so():
    if not _p(REDUCED).exists():
        blocked('reduced roster vintage present', f'{REDUCED} absent')
        return
    o = PB.roster_identity_outcome(2026, 1, ('DEN', 'KC'), blob=REDUCED,
                                   as_of=CUT)
    if o.state.name != 'PASS':
        blocked('reduced vintage readable', f'{o.code}')
        return
    ch = o.evidence['chosen']
    check('the reduced vintage is reported as carrying NO name column, which '
          'is a different state from carrying one and being empty',
          ch['name_column_absent'] is True
          and ch['name_columns_present'] == [], ch)
    check('  and it names zero players, without raising',
          ch['n_named'] == 0 and len(o.value) > 0, ch['n_named'])
    check('  while still resolving position and team, which is what the '
          'reduction was kept for',
          all(v.get('position') and v.get('team') for v in o.value.values()))


def test_f_the_raw_vintage_answers_from_its_own_bytes():
    if not _p(RAW).exists():
        blocked('raw roster vintage present', f'{RAW} absent')
        return
    o = PB.roster_identity_outcome(2026, 1, ('DEN', 'KC'), blob=RAW, as_of=CUT)
    if o.state.name != 'PASS':
        blocked('raw vintage readable', f'{o.code}')
        return
    ch = o.evidence['chosen']
    check('the raw vintage carries full_name',
          'full_name' in ch['name_columns_present'],
          ch['name_columns_present'])
    check('  and names every player it identifies -- a partial join is the '
          'defect this test exists for',
          ch['n_named'] == len(o.value), f'{ch["n_named"]}/{len(o.value)}')
    for gid, want in KNOWN.items():
        if gid not in o.value:
            blocked(f'{gid} on this roster vintage', 'not a DEN/KC week-1 row')
            continue
        got = (o.value.get(gid) or {}).get('name')
        check(f'{gid} is named {want} straight from the roster blob',
              got == want, repr(got))


# ===================================== 2. an unresolvable id stays unresolved
def _synth_roster(tmp, rows, cols):
    p = pathlib.Path(tmp) / 'roster.csv.gz'
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, '') for c in cols})
    with gzip.open(p, 'wt') as fh:
        fh.write(buf.getvalue())
    return p


def test_g_an_id_no_capture_names_is_reported_not_guessed():
    """The honest-absence path, on a blob built here so the state is reachable."""
    nameless = '00-' + '9999001'
    named = '00-' + '9999002'
    with tempfile.TemporaryDirectory(dir=_ROOT) as t:
        rows = [{'season': '2026', 'week': '1', 'team': 'KC',
                 'gsis_id': nameless, 'position': 'QB', 'full_name': ''},
                {'season': '2026', 'week': '1', 'team': 'KC',
                 'gsis_id': named, 'position': 'WR',
                 'full_name': 'Real Person'}]
        cols = ['season', 'week', 'team', 'gsis_id', 'position', 'full_name']
        p = _synth_roster(t, rows, cols)
        rel = os.path.relpath(p, _ROOT)
        o = PB.roster_identity_outcome(2026, 1, ('KC',), blob=rel, as_of=CUT)
        if o.state.name != 'PASS':
            blocked('synthetic roster readable', o.code)
            return
        check('a row whose name cell is empty resolves to None, not to the '
              'empty string and not to the id',
              o.value[nameless]['name'] is None, repr(o.value[nameless]['name']))
        check('  and the row beside it still resolves',
              o.value[named]['name'] == 'Real Person')
        check('  so n_named counts the named ones only',
              o.evidence['chosen']['n_named'] == 1,
              o.evidence['chosen']['n_named'])
    NM.cache_clear()
    check('an id no capture anywhere names is absent from the resolver '
          'rather than given a placeholder', nameless not in NM.resolve(CUT)[0])
    NM.cache_clear()


# ============================================ the gate's own condition, direct
def test_h_the_gate_condition_is_satisfied_by_a_named_row():
    from nfl.product import quality_gates as QG
    board = {'teams': ['KC'], 'players': [
        {'gsis_id': '00-' + '0033873', 'team': 'KC', 'position': 'QB',
         'depth_chart': 'QB1', 'layers': ['qb'], 'name': 'Patrick Mahomes'}]}
    f = QG.gate_identity_depth_role(board, {}, {})
    fired = [x for x in f if x['state'] == QG.FIRED]
    check('a row carrying a name, a declared position, allowed layers and a '
          'matching depth tag does not fire the identity gate', not fired,
          [x['why'][:120] for x in fired])
    board['players'][0]['name'] = None
    f2 = QG.gate_identity_depth_role(board, {}, {})
    fired2 = [x for x in f2 if x['state'] == QG.FIRED]
    check('  and removing the name fires it again, so this test can fail',
          bool(fired2))
    check('  with the board-scope escalation when EVERY row is nameless',
          any(x['action'] == QG.WITHHOLD_BOARD for x in fired2))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} failing check(s)')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(fn)
        globals()[fn]()
    print(f'PASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
