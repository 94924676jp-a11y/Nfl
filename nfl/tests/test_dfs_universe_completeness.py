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
    return bool(re.search(r'player_draws_manifest|dk_scoring', src))


def test_production_manifest_readers_go_through_the_union():
    """THE RULE, not the instance. Eighteen modules were reported PARTIAL_JOIN;
    a report does not stop the nineteenth."""
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
        if not _reads_a_manifest(src):
            continue
        if 'player_universe' in src or 'dk_bearing_layers' in src:
            continue
        offenders.append(rel)
    check('every production manifest reader takes the union path',
          not offenders,
          f'{len(offenders)} module(s) read the DK universe without '
          f'player_universe, so each sees whichever layers it happens to name: '
          f'{offenders[:8]}')


def test_the_exemption_list_names_real_files_and_gives_reasons():
    """An allowlist nobody prunes is a way to hide the defect."""
    for rel, why in sorted(DECLARED_NON_UNION.items()):
        check(f'exemption {rel} exists', (_REPO / rel).exists(), 'stale entry')
        check(f'exemption {rel} carries a reason', bool(why.strip()))
