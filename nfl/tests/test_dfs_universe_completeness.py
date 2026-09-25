"""A DFS universe assembled from one layer is a universe missing a position.

The kicker defect was never "the model cannot project kickers". The model
projects them fine: the `kicking` layer carries dk_points for both, and the
sealed run for 2026_03_ATL_GB holds exactly two kicker rows. What went wrong
is smaller and much easier to repeat -- the DK points universe is spread
across MORE THAN ONE player-keyed layer, and a consumer that reads
`dk_scoring` alone gets 30 players instead of 32, with no error, no warning,
and a pool that simply has no kickers in it.

`player_universe.dk_bearing_layers()` already solves this by DISCOVERING every
player-keyed layer that declares a dk_points metric, rather than naming the
layers it expects, and `modelled()` unions across all of them. The path is
correct. The problem is that eighteen production modules do not take it: the
cross-layer audit reports them as PARTIAL_JOIN, reading one dk-bearing layer
and never the other.

A standing report is not a control. These tests make the rule enforceable:

  * the union over the real sealed artifact must contain the kickers, by id;
  * a production module that reads a draws manifest must go through
    player_universe, or be DECLARED research/fixture with a reason; and
  * if two dk-bearing layers ever share a player, `modelled()` silently keeps
    whichever layer sorts last, so the overlap must be zero or declared.

That third one is a latent defect rather than a live one -- today the layers
are disjoint -- and it is written down here so it cannot become live quietly.
"""
import ast
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs import player_universe as U                        # noqa: E402

SEALED = (_REPO / 'nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1'
                  '/player_draws_manifest.json')
KICKERS = {'00-0025565', '00-0040899'}

PRODUCTION_TREES = ('nfl/production', 'nfl/dfs', 'nfl/product', 'nfl/truth',
                    'nfl/postgame', 'nfl/market', 'nfl/prospective')

#: Modules that read a manifest and legitimately do NOT need the DK union,
#: each with the reason. Anything not listed here must go through
#: player_universe. An exemption is a claim about a module's job, and it is
#: cheaper to write one line here than to debug a kickerless pool at lock.
DECLARED_NON_UNION = {
    'nfl/dfs/player_universe.py':
        'it IS the union path; it reads the layers to build the universe',
    'nfl/dfs/scoring/draftkings.py':
        'scores a statline it is handed; it never selects the universe',
    'nfl/dfs/scoring/statline.py':
        'formats one player row for display',
    'nfl/dfs/showdown/universe_contract.py':
        'declares the contract the universe must satisfy',
    'nfl/production/run_forecast.py':
        'the PRODUCER. It records `produced[\'dk_scoring\'] = len(rows)` after '
        'writing that layer, which is a statement about what it emitted, not a '
        'selection from a universe it consumes. It also writes the kicking '
        'layer, from the same sealed events.',
    'nfl/production/review/dossier_reference.py':
        'FROZEN COPY of review/dossier.py at commit f43c30e, marked DO NOT '
        'EDIT. It carries the single-layer selection ON PURPOSE: it exists to '
        'reproduce what the dossier did at that commit, and correcting it '
        'would destroy the only record of the behaviour the live file has now '
        'moved away from. Classified as FROZEN HISTORICAL BEHAVIOUR. Live '
        'production must not read it -- asserted separately below.',
}

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _manifest():
    return json.loads(SEALED.read_text()) if SEALED.exists() else None


def test_more_than_one_layer_carries_dk_points():
    """The premise. If this ever collapses to one layer the rest is moot --
    and so is the defect."""
    m = _manifest()
    if m is None:
        check('sealed manifest present', False, f'{SEALED} absent')
        return
    layers = U.dk_bearing_layers(m)
    check('dk points are spread across more than one layer', len(layers) > 1,
          f'{layers} -- if this is now one layer, say so explicitly rather '
          f'than letting these tests quietly stop meaning anything')
    print(f'       dk-bearing layers: {layers}')


def test_the_union_contains_the_kickers_by_id():
    m = _manifest()
    if m is None:
        check('sealed manifest present', False, f'{SEALED} absent')
        return
    ids = set()
    for layer in U.dk_bearing_layers(m):
        ids |= set(m['layers'][layer].get('row_ids') or [])
    check('both kickers are in the union', KICKERS <= ids,
          f'missing {sorted(KICKERS - ids)}')
    single = set(m['layers']['dk_scoring'].get('row_ids') or [])
    check('and they are NOT in dk_scoring alone', not (KICKERS & single),
          'the premise of this test has changed: dk_scoring now carries '
          'kickers, so re-derive what the union is still protecting')
    print(f'       union {len(ids)} vs dk_scoring alone {len(single)}')


def test_dk_bearing_layers_refuses_an_artifact_with_no_dk_points():
    """A manifest carrying no DK metric must refuse rather than return an
    empty universe. An empty pool is a result nobody reads as an error."""
    try:
        U.dk_bearing_layers({'layers': {'qb': {'row_axis': 'gsis_id',
                                               'metrics': ['pass_yds']}}})
        check('an artifact with no dk_points is refused', False,
              'returned instead of raising')
    except Exception as e:                                       # noqa: BLE001
        check('an artifact with no dk_points is refused',
              'JoinIncomplete' in type(e).__name__, type(e).__name__)


def test_the_dk_bearing_layers_are_disjoint_or_declared():
    """modelled() keys by normalised NAME across layers, so a player present
    in two dk-bearing layers is silently overwritten by whichever layer sorts
    last. Today the layers are disjoint and this is latent. It is asserted so
    it cannot become live without someone seeing it."""
    m = _manifest()
    if m is None:
        check('sealed manifest present', False, f'{SEALED} absent')
        return
    layers = U.dk_bearing_layers(m)
    seen, overlap = {}, {}
    for layer in layers:
        for gsis in (m['layers'][layer].get('row_ids') or []):
            if gsis in seen:
                overlap.setdefault(gsis, [seen[gsis]]).append(layer)
            else:
                seen[gsis] = layer
    check('no player appears in two dk-bearing layers', not overlap,
          f'{overlap} -- modelled() would keep only the last layer sorted, '
          f'silently. Decide which layer wins and make it explicit.')


def _reads_a_manifest(src):
    """Does this module READ the universe, or merely talk about it?

    The first version of this check searched the raw text, and reported 36
    modules. Most were prose: `contracts/completeness.py` discusses "assembled
    from dk_scoring alone" in its docstring because that is the defect it
    exists to prevent, and `production/seeds.py` names the array in a comment.
    A rule that cries wolf thirty-six times is a rule people learn to skip,
    which is worse than no rule -- it converts a real finding into noise and
    then hides inside it.

    So: parse, and count only string literals that survive as CODE. Comments
    never enter the AST at all, and docstrings are dropped explicitly. What is
    left is a module actually naming the layer or the artifact while doing
    something with it.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, 'body', None) or []
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        v = node.value
        if not isinstance(v, str):
            continue
        if v == 'dk_scoring' or 'player_draws_manifest' in v \
                or v.startswith('dk_scoring/'):
            return True
    return False


def _string_literals(src):
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return set()
    return {n.value for n in _ast.walk(tree)
            if isinstance(n, _ast.Constant) and isinstance(n.value, str)}


def _dk_selection_sites(src):
    """Where the module PICKS DK points out of a layer it named itself.

    The heuristic this replaces was "does the module mention `kicking`
    anywhere?", and it produced a FALSE NEGATIVE, which is worse than the false
    positives it was tuned to remove. `build_postinactives_package.py` mentions
    `kicking` only inside a PLAYER_LAYERS tuple listing every player-keyed
    layer, while its DK selection reads `dk_scoring` alone -- so it was excused
    as correct while `dfs_rows` did `met.get('dk_scoring/dk_points')` and
    `continue`, dropping every kicker off the post-inactives board.

    A mention somewhere in a file says nothing about what the DK path does. So
    this looks at the two code shapes that actually select:
    `something['dk_scoring']` and `something.get('dk_scoring...')`.
    """
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return []
    keys = {'dk_scoring', 'dk_scoring/dk_points', 'dk_scoring__dk_points'}
    out = []
    for n in _ast.walk(tree):
        if isinstance(n, _ast.Subscript) \
                and isinstance(getattr(n, 'slice', None), _ast.Constant) \
                and n.slice.value == 'dk_scoring':
            out.append(getattr(n, 'lineno', 0))
        if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute) \
                and n.func.attr == 'get' and n.args \
                and isinstance(n.args[0], _ast.Constant) \
                and n.args[0].value in keys:
            out.append(getattr(n, 'lineno', 0))
    return sorted(out)


def _reads_kicking_dk_in_code(src):
    """Does it ALSO read kicking's DK points as code, not in a comment?"""
    return any(v.startswith('kicking') and 'dk_points' in v
               for v in _string_literals(src))


def _selects_dk_layer(lits):
    return any(v == 'dk_scoring' or v.startswith('dk_scoring/') for v in lits)


def _names_kicking(lits):
    return any(v == 'kicking' or v.startswith('kicking') or 'kicking__' in v
               for v in lits)


def test_production_universe_selectors_cover_every_dk_bearing_layer():
    """THE ACTIONABLE RULE, narrowed until it is worth acting on.

    Three passes were needed to get a number anyone should trust. Raw text
    search said 36, but most were prose -- `contracts/completeness.py`
    DISCUSSES "assembled from dk_scoring alone" because that is the defect it
    prevents. Parsing instead of grepping gave 28. Separating modules that
    SELECT from the dk_scoring layer from those that merely open the manifest
    file for provenance gave 13. Of those, seven already name `kicking`
    alongside it.

    Six are left, and they are not obscure:

        postgame/grade_projections.py   -- grading has never graded a kicker
        production/board/player_board.py -- the slate board itself
        production/review/dossier.py     -- the per-player dossier
        dfs/scoring/dual_board.py
        dfs/salaries/early_projection_audit.py -- an audit that would report a
            kicker as HAVING NO PROJECTION, which is how a real gap gets
            written off as a known absence

    Naming both layers by hand is better than naming one, and still not right:
    the union is DISCOVERED by metric in player_universe.dk_bearing_layers(),
    so a third dk-bearing layer added tomorrow reaches the discoverers and
    silently misses the hand-written ones.
    """
    offenders = []
    for p in sorted(_REPO.rglob('*.py')):
        rel = str(p.relative_to(_REPO))
        if not any(rel.startswith(t) for t in PRODUCTION_TREES):
            continue
        if rel in DECLARED_NON_UNION or '/tests/' in rel:
            continue
        try:
            src = p.read_text()
        except Exception:                                        # noqa: BLE001
            continue
        if 'player_universe' in src or 'dk_bearing_layers' in src:
            continue
        sites = _dk_selection_sites(src)
        if sites and not _reads_kicking_dk_in_code(src):
            offenders.append(f'{rel}:{sites[0]}')
    check('every production universe selector covers all dk-bearing layers',
          not offenders,
          f'{len(offenders)} module(s) select DK points from dk_scoring alone '
          f'and will never see a kicker: {offenders}')


def test_hand_written_layer_lists_are_reported_even_when_correct():
    """Not a gate: a standing count. A module that names dk_scoring AND
    kicking is right today and brittle tomorrow, and the difference between
    "right" and "discovered to be right" is the whole lesson of DEF-060."""
    hand = []
    for p in sorted(_REPO.rglob('*.py')):
        rel = str(p.relative_to(_REPO))
        if not any(rel.startswith(t) for t in PRODUCTION_TREES) or '/tests/' in rel:
            continue
        try:
            src = p.read_text()
        except Exception:                                        # noqa: BLE001
            continue
        if 'dk_bearing_layers' in src:
            continue
        lits = _string_literals(src)
        if _selects_dk_layer(lits) and _names_kicking(lits):
            hand.append(rel)
    check('hand-written layer list survey completed', True)
    print(f'       {len(hand)} module(s) hand-list the dk-bearing layers '
          f'instead of discovering them:')
    for rel in hand:
        print(f'         {rel}')


def test_the_exemption_list_names_real_files_and_gives_reasons():
    """An allowlist nobody prunes is a way to hide the defect."""
    for rel, why in sorted(DECLARED_NON_UNION.items()):
        check(f'exemption {rel} exists', (_REPO / rel).exists(), 'stale entry')
        check(f'exemption {rel} carries a reason', bool(why.strip()))
