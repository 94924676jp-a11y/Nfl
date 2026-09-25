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
    """Every player-keyed layer carrying DK points, discovered not listed."""
    out = []
    for name, d in sorted((manifest.get('layers') or {}).items()):
        if d.get('row_axis') != 'gsis_id':
            continue
        if DK_METRIC in (d.get('metrics') or ()):
            out.append(name)
    if not out:
        raise CC.JoinIncomplete(
            'no player-keyed layer declares a dk_points metric; a DFS universe '
            'cannot be built from this artifact and must not be faked')
    return out


def modelled(manifest: dict, npz, name_by_gsis: dict) -> dict:
    """norm(name) -> {'gsis_id', 'layer', 'row', 'draws'} across every layer."""
    sup = {}
    for layer in dk_bearing_layers(manifest):
        key = f'{layer}__{DK_METRIC}'
        if key not in getattr(npz, 'files', ()):
            continue
        arr = np.asarray(npz[key], dtype=np.float64)
        ids = manifest['layers'][layer].get('row_ids') or []
        for row, gsis in enumerate(ids):
            if row >= arr.shape[0]:
                continue
            nm = name_by_gsis.get(gsis)
            if not nm:
                continue
            sup[norm(nm)] = {'gsis_id': gsis, 'layer': layer, 'row': row,
                             'draws': arr[row]}
    return sup


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
        present_keys=present)
    report['layers_joined'] = dk_bearing_layers(manifest)
    report['spec_version_universe'] = SPEC_VERSION
    return universe, CC.assert_complete(report, consumer)
