"""Kickers, resolved BY PLAYER ID. The (team, position) join is refused.

A CORRECTION TO THE REVIEW FINDING, AND IT MATTERS

The review recorded this as "kicker projections were team-keyed and later
resolved through (team, position)". The first half is **false on the
evidence** and the second half is the real defect.

Read the sealed manifest. `layers.kicking.row_ids` is
`['00-0036162', '00-0039172']` -- those are gsis_ids, not clubs. `row_teams`
is `['BUF', 'DET']`, an extra descriptive column beside the key, not the key
itself. The 2026-09-18 outcome capture confirms the two ids independently:
nflverse gives Tyler Bass `00-0036162` and Jake Bates `00-0039172`.

**The kicking layer was player-keyed all along.** What was missing is a NAME.
`frozen_board_names.json` publishes 29 offensive gsis_ids and omits these two,
so every downstream name-based join failed, and the only thing left to fall
back on was club and position. The defect is a publication gap in the name
map, and the (team, position) join was the symptom.

That distinction changes the repair. There is nothing to re-key and no model
to rebuild. The id needs a name from a governed, pregame-lawful source.

THE SOURCE. The weekly roster vintage `698183b8ab2a09fa` -- the same blob the
official-inactives ingestion resolved names against, captured before the seal.
It carries gsis_id, full name, club and position for both kickers in weeks 1
and 2.

THE REFUSAL. `resolve` matches on ID ONLY. `assert_not_positional` exists so
that a caller who tries to reach a kicker through club and position gets
`KICKER_IDENTITY_MUST_BE_PLAYER_KEYED` rather than a plausible answer. Two
kickers on one club, an in-season signing, a club that dresses two -- each
would make the positional join wrong silently, and on a DFS product silently
wrong means the wrong man in a submitted lineup.
"""
from __future__ import annotations

import csv
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome          # noqa: E402

SPEC_VERSION = 'nfl-kicker-identity-1'

FROZEN = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/frozen'
MANIFEST = FROZEN / 'sealed_player_draws_manifest.json'
#: The roster vintage the inactives ingestion used. Captured before the seal.
ROSTER = _REPO / 'nfl/vintage/weekly_rosters.698183b8ab2a09fa.raw.csv.gz'

CODE_POSITIONAL = 'KICKER_IDENTITY_MUST_BE_PLAYER_KEYED'
CODE_UNRESOLVED = 'KICKER_IDENTITY_UNRESOLVED'


def assert_not_positional(join_keys) -> Outcome:
    """A kicker may never be reached through club and position."""
    keys = {str(k).lower() for k in join_keys}
    if 'gsis_id' in keys or 'player_id' in keys:
        return Outcome.ok(
            'KICKER_IDENTITY_PLAYER_KEYED', value=sorted(keys),
            detail=f'join on {sorted(keys)} carries a player id',
            spec_version=SPEC_VERSION)
    if {'team', 'position'} <= keys or {'club', 'position'} <= keys:
        return Outcome.fail(
            CODE_POSITIONAL,
            f'a join on {sorted(keys)} identifies a ROLE, not a man. Two '
            f'kickers on one club, a mid-season signing, or a club dressing '
            f'two all make it wrong without making it fail, and on a DFS '
            f'product that means the wrong player in a submitted lineup.',
            cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION,
            join_keys=sorted(keys))
    return Outcome.fail(
        CODE_UNRESOLVED,
        f'a join on {sorted(keys)} carries no player id at all.',
        cause=Cause.GOVERNANCE, join_keys=sorted(keys))


def _roster_index(path=None) -> dict:
    p = pathlib.Path(path or ROSTER)
    out = {}
    with gzip.open(p, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            gid = (r.get('gsis_id') or r.get('player_id') or '').strip()
            nm = (r.get('full_name') or r.get('player_name') or '').strip()
            if gid and nm and gid not in out:
                out[gid] = {'name': nm, 'team': (r.get('team') or '').strip(),
                            'position': (r.get('position') or '').strip()}
    return out


def resolve(manifest_path=None, roster_path=None, frozen=None) -> Outcome:
    """gsis_id -> name for every row of the sealed kicking layer.

    `frozen` names the slate's directory. It exists so `universe.build` can
    hand its own slate down rather than have this module silently reach for
    DET@BUF's manifest while the caller believes it is reading another game.
    An explicit `manifest_path` still wins, since it says exactly which file.
    """
    if manifest_path is None and frozen is not None:
        manifest_path = pathlib.Path(frozen) / 'sealed_player_draws_manifest.json'
    mp = pathlib.Path(manifest_path or MANIFEST)
    if not mp.exists():
        return Outcome.blocked('KICKER_MANIFEST_MISSING', str(mp),
                               cause=Cause.DATA)
    man = json.loads(mp.read_text())
    layer = (man.get('layers') or {}).get('kicking')
    if not layer:
        return Outcome.fail('KICKER_LAYER_ABSENT',
                            'the sealed manifest carries no kicking layer',
                            cause=Cause.DATA)
    ids = list(layer['row_ids'])
    teams = list(layer.get('row_teams') or [None] * len(ids))
    idx = _roster_index(roster_path)
    rows, unresolved, disagree = [], [], []
    for i, (gid, club) in enumerate(zip(ids, teams)):
        hit = idx.get(gid)
        if hit is None:
            unresolved.append(gid)
            continue
        if club and hit['team'] and club != hit['team']:
            # The club column beside the key must agree with the club the
            # roster gives that id. A disagreement means the layer's extra
            # column is stale, and it is reported rather than preferred.
            disagree.append({'gsis_id': gid, 'layer_team': club,
                             'roster_team': hit['team']})
        rows.append({'row': i, 'gsis_id': gid, 'name': hit['name'],
                     'team': hit['team'], 'position': hit['position'],
                     'layer_team': club, 'resolved_by': 'gsis_id'})
    ev = {'spec_version': SPEC_VERSION, 'n_rows': len(ids),
          'n_resolved': len(rows), 'unresolved': unresolved,
          'club_column_disagreements': disagree,
          'roster_blob': str(pathlib.Path(roster_path or ROSTER).name),
          'resolved_by': 'gsis_id', 'never_by': '(team, position)',
          'the_layer_was_always_player_keyed': True}
    if unresolved or disagree:
        return Outcome.fail(
            CODE_UNRESOLVED,
            f'{len(unresolved)} kicking row id(s) have no roster name and '
            f'{len(disagree)} disagree with the layer club column. Neither is '
            f'repaired by guessing.', cause=Cause.DATA, **ev)
    return Outcome.ok(
        'KICKER_IDENTITY_RESOLVED',
        value={r['gsis_id']: r for r in rows},
        detail=', '.join(f"{r['gsis_id']} = {r['name']} ({r['team']})"
                         for r in rows), **ev)


def main() -> int:
    o = resolve()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    bad = assert_not_positional(('team', 'position'))
    print(f'{bad.state.value}[{bad.code}] (a positional join, refused)')
    good = assert_not_positional(('gsis_id',))
    print(f'{good.state.value}[{good.code}]')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
