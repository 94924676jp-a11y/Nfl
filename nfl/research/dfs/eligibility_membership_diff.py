"""Who enters the Classic pool under the old rule and under the canonical one?

Runs the real held slate through both and enumerates every membership change.
Writes ELIGIBILITY_MEMBERSHIP_DIFF.json. Changes nothing.
"""
from __future__ import annotations

import collections
import contextlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.classic import pool as POOL                              # noqa: E402
from nfl.production.state import availability as AV                   # noqa: E402

BOARD = _REPO / 'nfl/research/board/2026_02_NYG_LA'
REVIEW = _REPO / 'nfl/research/player_review/2026_02_NYG_LA'
DRAWS = _REPO / 'nfl/research/engine_repair/cs6_after/5dd61c7b2f318d3e'
OUT = _REPO / 'nfl/research/dfs/ELIGIBILITY_MEMBERSHIP_DIFF.json'


@contextlib.contextmanager
def old_rule():
    """The exact test the pool used before this slice."""
    class _Old:
        WILL_NOT_PLAY = AV.WILL_NOT_PLAY
        SERIALISED_ALIASES = AV.SERIALISED_ALIASES
        canonical = staticmethod(AV.canonical)

        @staticmethod
        def will_not_play(v):
            return str(v) == 'INACTIVE'

    keep = POOL.AV
    POOL.AV = _Old
    try:
        yield
    finally:
        POOL.AV = keep


def run():
    return POOL.build_pool(board_dir=BOARD, draws_dir=DRAWS,
                           review_dir=REVIEW)


def members(o):
    v = o.value or (getattr(o, 'evidence', {}) or {}).get('value') or {}
    return ({p.gsis_id: {'name': p.name, 'position': p.position,
                         'salary': p.salary, 'value': p.value}
             for p in v.get('players') or ()}, v)


def main():
    if not (BOARD / 'PLAYER_BOARD.json').exists():
        print('board absent; nothing to measure')
        return 1
    board = json.loads((BOARD / 'PLAYER_BOARD.json').read_text())
    avail = collections.Counter(r.get('availability')
                                for r in board.get('rows') or ())

    with old_rule():
        old_o = run()
    new_o = run()
    old_m, old_v = members(old_o)
    new_m, new_v = members(new_o)

    removed = sorted(set(old_m) - set(new_m))
    added = sorted(set(new_m) - set(old_m))
    shared = sorted(set(old_m) & set(new_m))
    changed_fields = collections.Counter()
    for pid in shared:
        for k in ('name', 'position', 'salary', 'value'):
            if old_m[pid][k] != new_m[pid][k]:
                changed_fields[k] += 1

    by_avail = {r['gsis_id']: r.get('availability')
                for r in board.get('rows') or ()}
    # BOARD-LEVEL diff, independent of whether a pool could be built. This
    # is the question "who would the two rules classify differently", and it
    # is answerable even when the run itself refused.
    old_rule_out, new_rule_out = [], []
    for r in board.get('rows') or ():
        a = r.get('availability')
        if str(a) == 'INACTIVE':
            old_rule_out.append(r)
        if AV.will_not_play(a):
            new_rule_out.append(r)
    old_ids = {r.get('gsis_id') for r in old_rule_out}
    new_ids = {r.get('gsis_id') for r in new_rule_out}
    newly_blocked = [r for r in new_rule_out
                     if r.get('gsis_id') not in old_ids]

    doc = {
        'artifact': 'ELIGIBILITY_MEMBERSHIP_DIFF',
        'spec_version': 'eligibility-membership-diff-1',
        'reproduce': 'python3.12 nfl/research/dfs/'
                     'eligibility_membership_diff.py',
        'slate': board.get('slate_key'),
        'information_cut': board.get('information_cut'),
        'board_rows': len(board.get('rows') or ()),
        'board_availability_distribution': dict(avail),
        'old_rule': "availability == 'INACTIVE'",
        'new_rule': 'AV.will_not_play(availability), tied to '
                    'AV.WILL_NOT_PLAY = {OFFICIAL_INACTIVE, INJURY_OUT} '
                    'plus the dossier alias',
        'old_outcome': old_o.code, 'new_outcome': new_o.code,
        'old_pool_size': len(old_m), 'new_pool_size': len(new_m),
        'removed_by_the_canonical_rule': [
            {'gsis_id': p, 'name': old_m[p]['name'],
             'availability': by_avail.get(p),
             'salary': old_m[p]['salary'], 'dk_mean': old_m[p]['value'],
             'why': 'canonical availability is WILL_NOT_PLAY and the old '
                    'string test did not cover it'}
            for p in removed],
        'added_by_the_canonical_rule': [
            {'gsis_id': p, 'name': new_m[p]['name'],
             'availability': by_avail.get(p)} for p in added],
        'unchanged_members': len(shared),
        'fields_that_moved_on_an_unchanged_member': dict(changed_fields),
        'exclusions_new': (new_v.get('exclusions') or {}).get(
            'by_kind_and_reason'),
        'exclusions_old': (old_v.get('exclusions') or {}).get(
            'by_kind_and_reason'),
        'gate_verdict_old': old_v.get('gate_verdict'),
        'gate_verdict_new': new_v.get('gate_verdict'),
        'integrity_coverage_new': new_v.get('integrity_coverage'),
        'board_level_diff': {
            'what': 'which board rows each rule classifies as will-not-play, '
                    'answerable even when no pool could be built',
            'old_rule_excludes': len(old_ids),
            'new_rule_excludes': len(new_ids),
            'newly_excluded_by_the_canonical_rule': [
                {'gsis_id': r.get('gsis_id'), 'name': r.get('player'),
                 'availability': r.get('availability')}
                for r in newly_blocked],
            'no_longer_excluded': sorted(old_ids - new_ids),
        },
        'caveat': 'THIS SLATE CANNOT EXERCISE THE CHANGE. Its board carries '
                  'no INJURY_OUT row -- by the time an official inactive '
                  'list exists, a player his club declared OUT is normally '
                  'ON that list and already reads OFFICIAL_INACTIVE. The '
                  'window the defect lives in is the one BEFORE inactives '
                  'publish, when INJURY_OUT is the only availability '
                  'evidence there is, and this held artifact is from after '
                  'it. The synthetic fixture in '
                  'nfl/tests/test_dfs_eligibility.py is what exercises it.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str) + '\n')
    print(f'slate {doc["slate"]}  board rows {doc["board_rows"]}')
    print(f'  availability distribution {doc["board_availability_distribution"]}')
    print(f'  old {old_o.code} pool {len(old_m)}   '
          f'new {new_o.code} pool {len(new_m)}')
    print(f'  REMOVED by the canonical rule: {len(removed)}')
    for r in doc['removed_by_the_canonical_rule']:
        print(f'     {r["name"]:24s} {r["availability"]:22s} '
              f'sal {r["salary"]} dk {r["dk_mean"]}')
    print(f'  ADDED: {len(added)}   unchanged {len(shared)}   '
          f'fields moved on an unchanged member {dict(changed_fields)}')
    print(f'  gate verdict {old_v.get("gate_verdict")} -> '
          f'{new_v.get("gate_verdict")}')
    print(f'wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
