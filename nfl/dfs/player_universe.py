"""One joined DFS player universe, with its coverage proved rather than assumed.

WHY THIS REPLACES READING `dk_scoring` DIRECTLY

The scoring layers that carry DK points are DISCOVERED FROM THE MANIFEST, by
looking for a `dk_points` metric on a player-keyed layer, rather than named in a
constant here. That is the whole point. On 2026-09-24 a selector read
`dk_scoring` and missed `kicking`, and a constant listing `('dk_scoring',
'kicking')` would have fixed that one instance while leaving the next one -- a
DST layer, a returner layer, a two-point-conversion layer -- to be missed the
same way by the same reasoning.

A layer added upstream is therefore picked up here with no edit, and a consumer
that cannot cover the priced contest refuses through
`contracts.completeness`, whose default is refusal.

WHAT IT DOES NOT DO

It does not invent a projection for a player it cannot find, and it does not
drop him quietly. He appears in `missing_right` and, for a consumer that
requires completeness, he stops the build. A kicker priced at $4,800 with no
model row is a hole in the search space, and the correct response is to say so
before kickoff rather than to hand over ten lineups that never considered him.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import numpy as np

from nfl.dfs import gate_enforcement as GE
from nfl.production.contracts import completeness as CC
from nfl.production.contracts import registry as _registry

SPEC_VERSION = 'dfs-player-universe/1.0.0'

#: The metric that marks a layer as carrying DK points for a player.
DK_METRIC = 'dk_points'

#: DK roster positions that are players or team units in a Showdown pool.
DK_POSITIONS = ('QB', 'RB', 'WR', 'TE', 'K', 'DST')


def norm(name: str) -> str:
    """Declared normalisation. No fuzzy matching anywhere in this module."""
    s = (name or '').lower().replace('.', ' ').replace("'", '')
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def dk_bearing_layers(manifest: dict) -> list:
    """Every player-keyed layer carrying DK points, discovered not listed.

    The implementation now lives with the ARTIFACT CONTRACT
    (`production.contracts.registry`), because which layers carry DK points is
    a fact about the artifact rather than about DFS. Modules that may not
    import this one -- `review/dossier.py` is forbidden it by name, so that
    football evidence arrives only through PregameSlateState -- can take the
    fact from the registry instead. Kept here, raising the same
    JoinIncomplete, so existing DFS callers are unaffected.
    """
    try:
        return _registry.dk_bearing_layers(manifest)
    except _registry.NoDkBearingLayer as exc:
        raise CC.JoinIncomplete(str(exc)) from exc


class _Modelled(dict):
    """A player mapping that also carries its own coverage.

    A dict so existing callers iterate it unchanged; attributes so the
    coverage travels with the data instead of being recomputed, or worse,
    assumed. `report` carries the mandatory completeness fields,
    `name_collisions` the players two names collapsed into one, and
    `ids_without_a_name` the rows that had football but no identity to attach
    it to.
    """
    report: dict = {}
    name_collisions: dict = {}
    ids_without_a_name: list = []


#: How a player found in more than one DK-bearing layer is resolved. There is
#: deliberately no default that silently picks one: the old `modelled()` keyed
#: by normalised NAME, so a player in two layers was overwritten by whichever
#: layer sorted last, with nothing raised and nothing logged.
NO_DUPLICATES_EXPECTED = 'NO_DUPLICATES_EXPECTED'
LAST_LAYER_WINS = 'LAST_LAYER_WINS'
FIRST_LAYER_WINS = 'FIRST_LAYER_WINS'
MERGE_POLICIES = (NO_DUPLICATES_EXPECTED, LAST_LAYER_WINS, FIRST_LAYER_WINS)


class DuplicateLayerOwnership(RuntimeError):
    """One player carries DK points in two layers and nobody said which wins."""


def dk_universe(manifest: dict, *, consumer: str,
                merge_policy: str = NO_DUPLICATES_EXPECTED,
                expected_ids=None) -> dict:
    """THE ONE SANCTIONED WAY TO ASK FOR THE DK PLAYER UNIVERSE.

    DK points are not in one layer. On the sealed ATL@GB artifact they are in
    `dk_scoring` (30 rows) and `kicking` (2), and any consumer that reads
    `dk_scoring` alone gets 30 players, no error, and a board with no kickers
    on it. Six production modules did exactly that -- including the slate
    board, the per-player dossier, and postgame grading, so a kicker had never
    been graded at all. The audit whose job was to report missing projections
    read the same single layer, and would have reported a kicker as HAVING NO
    PROJECTION: a real gap written off as a known absence.

    Four properties, because the defect needed all four to happen:

    * DISCOVERED, not listed. `dk_bearing_layers` finds every player-keyed
      layer declaring a dk_points metric. Seven other modules name dk_scoring
      AND kicking by hand; they are right today and silently wrong the day a
      third layer appears.
    * IDENTITY IS THE gsis_id. Never the name. `modelled()` keyed by
      normalised name, which is both collidable and unstable.
    * DUPLICATES REFUSE. A player in two layers raises unless the caller
      declares a merge policy, because "whichever sorted last" is not a
      decision anyone made.
    * COVERAGE IS RETURNED, not assumed. The report carries the mandatory
      completeness fields, so a consumer can see what it did not get instead
      of inferring completeness from the absence of an exception.
    """
    if merge_policy not in MERGE_POLICIES:
        raise ValueError(f'{merge_policy!r} is not a merge policy; '
                         f'choose from {MERGE_POLICIES}')
    layers = dk_bearing_layers(manifest)
    owner, dupes, rows_per_layer, row_of = {}, {}, {}, {}
    for layer in layers:
        ids = list(manifest['layers'][layer].get('row_ids') or [])
        rows_per_layer[layer] = len(ids)
        for row, gsis in enumerate(ids):
            if gsis in owner:
                dupes.setdefault(gsis, [owner[gsis]]).append(layer)
                if merge_policy == LAST_LAYER_WINS:
                    owner[gsis], row_of[gsis] = layer, (layer, row)
                continue
            owner[gsis], row_of[gsis] = layer, (layer, row)
    if dupes and merge_policy == NO_DUPLICATES_EXPECTED:
        raise DuplicateLayerOwnership(
            f'{consumer}: {len(dupes)} player(s) carry DK points in more than '
            f'one layer ({ {k: v for k, v in list(dupes.items())[:4]} }). '
            f'Declare a merge policy naming which layer wins; silently keeping '
            f'one is how the name-keyed version lost rows.')

    ids = sorted(owner)
    report = CC.join_report(
        'dk_bearing_layer_union',
        expected_keys=(set(expected_ids) if expected_ids else set(ids)),
        left_keys=ids, right_keys=ids, present_keys=ids,
        left_name='dk_bearing_layers', right_name='union')
    report['layers_discovered'] = layers
    report['rows_per_layer'] = rows_per_layer
    report['duplicate_owners'] = {k: sorted(set(v)) for k, v in dupes.items()}
    report['merge_policy'] = merge_policy
    report['expected_derived_from_present'] = expected_ids is None
    return {'ids': ids, 'layers': layers, 'layer_by_id': owner,
            'row_by_id': row_of, 'report': report, 'consumer': consumer}


def dk_metric_keys(manifest: dict) -> tuple:
    """Every '<layer>/dk_points' key a player's DK points may arrive under.

    For consumers that map a METRIC NAME rather than select a row set. Three
    production modules hardcoded 'dk_scoring/dk_points' as the one key --
    the slate board, the per-player dossier, and the projection audit -- so a
    kicker, whose points arrive as 'kicking/dk_points', read as a player with
    no DK metric at all. In the audit's case that was reported as HAVING NO
    PROJECTION, turning a real omission into a recorded absence.
    """
    return tuple(f'{layer}/{DK_METRIC}' for layer in dk_bearing_layers(manifest))


def dk_points_by_id(manifest: dict, npz, *, consumer: str,
                    merge_policy: str = NO_DUPLICATES_EXPECTED) -> tuple:
    """(gsis_id -> draws row, report). For consumers that select a ROW SET.

    `L['dk_scoring']['row_ids']` with `z['dk_scoring__dk_points']` is the shape
    that drops kickers outright: the ids come from one layer and the array is
    that layer's, so a kicker is not merely unscored, it is not enumerated.
    Both the dual board and postgame grading were built this way, which is why
    no kicker has ever been graded.

    Returning a mapping rather than (ids, array) is deliberate. The old shape
    forced `ids.index(gid)` into one array, which cannot express a universe
    whose rows live in different arrays -- so any fix that kept the shape
    would have had to pick a layer again.
    """
    uni = dk_universe(manifest, consumer=consumer, merge_policy=merge_policy)
    arrays, missing_arrays = {}, []
    for layer in uni['layers']:
        key = f'{layer}__{DK_METRIC}'
        if key in getattr(npz, 'files', ()):
            arrays[layer] = np.asarray(npz[key], dtype=np.float64)
        else:
            missing_arrays.append(key)
    out, no_row = {}, []
    for gsis in uni['ids']:
        layer, row = uni['row_by_id'][gsis]
        arr = arrays.get(layer)
        if arr is None or row >= arr.shape[0]:
            no_row.append(gsis)
            continue
        out[gsis] = arr[row]
    rep = dict(uni['report'])
    rep['arrays_absent'] = missing_arrays
    rep['ids_without_draws'] = no_row
    rep['n_with_draws'] = len(out)
    if missing_arrays or no_row:
        # Named, not swallowed. A universe of 32 that yields 30 rows of draws
        # is the same defect one layer down, and it must not read as success.
        rep['complete'] = False
    return out, rep


def modelled(manifest: dict, npz, name_by_gsis: dict, *,
             consumer: str = 'player_universe.modelled',
             merge_policy: str = NO_DUPLICATES_EXPECTED) -> dict:
    """norm(name) -> {'gsis_id', 'layer', 'row', 'draws'} across every layer.

    The return is still name-keyed because its callers match DK contest names,
    but the UNIVERSE is now resolved by `dk_universe` on gsis_id first, so
    layer ownership is decided once, explicitly, and a player in two layers
    refuses instead of being overwritten by whichever layer sorted last.

    Two distinct losses were possible here and only one of them was the
    kicker defect:

    * a player in two DK-bearing layers silently lost one of them -- now a
      refusal unless a merge policy is declared; and
    * TWO PLAYERS WHOSE NAMES NORMALISE THE SAME silently collapsed into one
      row. That is not hypothetical in this project: the B. Robinson case is
      exactly a normalised-name collision. It is now recorded in
      `name_collisions` rather than resolved by iteration order.
    """
    uni = dk_universe(manifest, consumer=consumer, merge_policy=merge_policy)
    sup, collisions, unnamed = {}, {}, []
    arrays = {}
    for layer in uni['layers']:
        key = f'{layer}__{DK_METRIC}'
        if key in getattr(npz, 'files', ()):
            arrays[layer] = np.asarray(npz[key], dtype=np.float64)
    for gsis in uni['ids']:
        layer, row = uni['row_by_id'][gsis]
        arr = arrays.get(layer)
        if arr is None or row >= arr.shape[0]:
            continue
        nm = name_by_gsis.get(gsis)
        if not nm:
            unnamed.append(gsis)
            continue
        k = norm(nm)
        if k in sup and sup[k]['gsis_id'] != gsis:
            collisions.setdefault(k, [sup[k]['gsis_id']]).append(gsis)
            continue
        sup[k] = {'gsis_id': gsis, 'layer': layer, 'row': row,
                  'draws': arr[row]}
    # METADATA ON AN ATTRIBUTE, NOT A SENTINEL KEY. A first version put it
    # under sup['__universe__'], which every caller iterating this mapping
    # would have silently treated as a player -- inventing exactly the kind of
    # phantom row this module exists to prevent. build() iterates it directly.
    out = _Modelled(sup)
    out.report = uni['report']
    out.name_collisions = collisions
    out.ids_without_a_name = unnamed
    return out


#: A DK name whose first token is a bare initial, with or without a dot.
_ABBREV = re.compile(r'^[a-z]\.?$')


def abbreviated(name: str) -> bool:
    """True when the demand side gave us an initial instead of a first name."""
    parts = norm(name).split()
    return len(parts) >= 2 and bool(_ABBREV.match(parts[0]))


def ambiguous_identities(rows, supply_names_by_team) -> list:
    """Abbreviated DK names that more than one rostered player could be.

    The owner ruled on 2026-09-24 that identity is never inferred from salary
    arithmetic when a source can name the player. This is the detector for the
    case that ruling was about: Atlanta rosters Bijan Robinson and Brian
    Robinson Jr., and a contest export reading `B. Robinson` resolves to both.
    Measured on the 2026-09-24 pool, that is the ONLY such pair in 53 rows --
    which is exactly why nothing caught it by accident.

    A hit is returned for refusal, never resolved. Picking the likelier man is
    how the wrong player enters a lineup.
    """
    out = []
    for r in rows:
        if not abbreviated(r['name']):
            continue
        surname = norm(r['name']).split()[-1]
        initial = norm(r['name']).split()[0][0]
        cands = sorted(
            n for n in supply_names_by_team.get(r['team'], ())
            if n.split()[-1] == surname and n.split()[0][0] == initial)
        if len(cands) > 1:
            out.append(f"{r['name']} [{r['team']}] -> {', '.join(cands)}")
    return out


def priced(salary_csv: Path) -> list:
    """The contest's own demand side, read from the DK export."""
    rows = []
    for r in csv.reader(Path(salary_csv).read_text().splitlines()):
        if len(r) > 18 and r[11] in DK_POSITIONS and r[15] in ('CPT', 'FLEX'):
            rows.append({'pos': r[11], 'name': r[13].strip(), 'dk_id': r[14],
                         'slot': r[15], 'salary': int(r[16]), 'team': r[18]})
    if not rows:
        raise CC.JoinIncomplete(f'{salary_csv} yielded no priced rows')
    return rows


def build(manifest_path, npz_path, salary_csv, name_by_gsis, consumer,
          eligible=None, min_salary=0, gate_verdicts=None) -> tuple:
    """(universe, coverage_report). Raises for a consumer needing completeness.

    `eligible` is the availability-resolved set of norm(name) the contest can
    actually field. It is REQUIRED to be supplied explicitly: defaulting it to
    "everyone priced" is how an inactive player stays in a universe.

    `gate_verdicts` is gate id -> state for `gate_enforcement`. A consumer that
    REQUIRES_COMPLETE cannot build without them: omitting the argument is not
    treated as "the gates passed", because that substitution is exactly how the
    2026-09-24 selector consumed a state the board had already refused.
    """
    pol, _ = CC.policy_for(consumer)
    if pol == CC.REQUIRES_COMPLETE:
        GE.assert_may_consume(gate_verdicts or {}, consumer)
    manifest = json.loads(Path(manifest_path).read_text())
    npz = np.load(npz_path, allow_pickle=True)
    sup = modelled(manifest, npz, name_by_gsis)
    rows = priced(salary_csv)

    demand, expected = {}, set()
    for r in rows:
        k = norm(r['name'])
        demand[k] = r
        if eligible is not None and k not in eligible:
            continue
        if r['salary'] < min_salary:
            continue
        expected.add(k)

    by_team = {}
    for k, r in demand.items():
        if k in sup:
            by_team.setdefault(r['team'], set()).add(k)
    unmatched = ambiguous_identities(
        [demand[k] for k in sorted(expected)], by_team)

    present, universe = set(), []
    for k in sorted(expected):
        m = sup.get(k)
        if m is None:
            continue
        present.add(k)
        universe.append({**demand[k], 'key': k, 'gsis_id': m['gsis_id'],
                         'layer': m['layer'], 'draws': m['draws']})

    report = CC.join_report(
        join_id='dfs.player_universe',
        left_name='dk_priced_contest', right_name='modelled_dk_layers',
        expected_keys=expected, left_keys=set(demand), right_keys=set(sup),
        present_keys=present, unmatched_identities=unmatched)
    report['layers_joined'] = dk_bearing_layers(manifest)
    report['spec_version_universe'] = SPEC_VERSION
    return universe, CC.assert_complete(report, consumer)
