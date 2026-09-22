"""Enumerate every availability classification this slice changes, and prove
that nothing else moved.

Writes AVAILABILITY_SEMANTICS_CHANGE.json. The old behaviour is the frozen
`review/dossier_reference.py`; the new one is the live module.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import dossier as D                        # noqa: E402
from nfl.production.review import dossier_reference as R              # noqa: E402
from nfl.production.state import availability as AV                   # noqa: E402
from nfl.production.universe import player_universe as PU             # noqa: E402

GAME, CUT = '2026_02_CAR_ATL', '2026-09-22T23:00:00Z'
OUT = _REPO / 'nfl/research/state/AVAILABILITY_SEMANTICS_CHANGE.json'


def _board_impact():
    """End-to-end impact on the player board, measured rather than argued.

    HOW IT WAS MEASURED. `nfl/research/board/2026_02_NYG_LA/PLAYER_BOARD.json`
    was copied before the change, `run_board.main()` was run after it, and
    the two files were compared row by row. To repeat it: check out the
    parent commit, run `python3.12 -m nfl.production.board.run_board`, keep
    the JSON, return, run it again, and diff.
    """
    return {
        'how_measured': 'PLAYER_BOARD.json before the change vs after, '
                        'row by row, 2026_02_NYG_LA week 2',
        'rows': 156,
        'row_fields_that_changed': {'availability': 143},
        'example': "Jaxson Dart: 'ACTIVE' -> 'NOT_ON_INACTIVE_LIST'",
        'review_verdicts': {'before': {'BLOCKING_REVIEW': 9, 'CLEARED': 133,
                                       'CLEARED_WITH_WARNING': 14},
                            'after': {'BLOCKING_REVIEW': 9, 'CLEARED': 133,
                                      'CLEARED_WITH_WARNING': 14},
                            'changed': False},
        'n_changes': {'before': 4, 'after': 4, 'changed': False},
        'n_unexplained_changes': {'before': 0, 'after': 0, 'changed': False},
        'n_with_salary': {'before': 32, 'after': 32, 'changed': False},
        'conclusion': 'the ONLY downstream field that moved is the board\'s '
                      'own availability column. Conflict generation, review '
                      'verdict, board status and optimizer eligibility are '
                      'all unchanged, because every consumer keys on the '
                      'literal INACTIVE and NOT_ON_INACTIVE_LIST is not it.',
        'registered_defect_this_makes_reachable': {
            'where': 'nfl/production/board/player_board.py:220',
            'code': "'PRACTICE_OR_INJURY' if 'INACTIVE' not in str(av) "
                    "else 'TEAMMATE_INACTIVE'",
            'problem': "this is a SUBSTRING test, and the string "
                       "'NOT_ON_INACTIVE_LIST' contains 'INACTIVE'. A player "
                       "moving from UNKNOWN to NOT_ON_INACTIVE_LIST would be "
                       "labelled TEAMMATE_INACTIVE, which is wrong. It did "
                       "not fire in the measurement above because the branch "
                       "needs availability to differ between two board runs "
                       "and both were built under the same code.",
            'status': 'REGISTERED, NOT FIXED -- player_board is out of scope '
                      'for this slice. It must be fixed before a board is '
                      'run against a previous board built before this '
                      'change.'},
    }


def scenario(name, rows, **kw):
    a = R.build_dossiers(universe_rows=rows, information_cut=CUT, **kw)
    b = D.build_dossiers(universe_rows=rows, information_cut=CUT, **kw)
    A = {d.gsis_id: d for d in a.value['dossiers']}
    B = {d.gsis_id: d for d in b.value['dossiers']}

    changed, other = [], collections.Counter()
    for pid in sorted(A):
        ax_a, ax_b = (A[pid].axis('official_availability'),
                      B[pid].axis('official_availability'))
        if ax_a.value != ax_b.value or ax_a.grade != ax_b.grade:
            changed.append({
                'gsis_id': pid, 'player': A[pid].display_name,
                'team': A[pid].team,
                'old_value': ax_a.value, 'old_grade': ax_a.grade,
                'new_value': ax_b.value, 'new_grade': ax_b.grade,
                'injury_report_status': (
                    A[pid].axis('injury_designation').value or {}).get(
                        'report'),
                'evidence_for_new_value': ax_b.note,
            })
        # every OTHER field of the dossier must be untouched
        da, db = A[pid].as_dict(), B[pid].as_dict()
        for k in ('evidence_provenance', 'state_identity'):
            db.pop(k, None)
        da.pop('spec_version'), db.pop('spec_version')
        for k in sorted(set(da) | set(db)):
            if k == 'axes':
                for axn in sorted(set(da['axes']) | set(db['axes'])):
                    if axn == 'official_availability':
                        continue
                    if da['axes'].get(axn) != db['axes'].get(axn):
                        other[f'axes.{axn}'] += 1
            elif da.get(k) != db.get(k):
                other[k] += 1

    became_active = [c for c in changed
                     if c['new_value'] in ('ACTIVE', AV.GAME_ACTIVE)]
    return {
        'scenario': name,
        'n_players': len(A),
        'n_availability_changed': len(changed),
        'old_distribution': dict(collections.Counter(
            d.axis('official_availability').value for d in A.values())),
        'new_distribution': dict(collections.Counter(
            d.axis('official_availability').value for d in B.values())),
        'transitions': dict(collections.Counter(
            f'{c["old_value"]} -> {c["new_value"]}' for c in changed)),
        'non_availability_fields_changed': dict(other),
        'n_became_active': len(became_active),
        'uncertainty_state_old': dict(a.value['by_uncertainty_state']),
        'uncertainty_state_new': dict(b.value['by_uncertainty_state']),
        'changed_players': changed,
    }


def main():
    rows = PU.build(2026, 2, GAME, CUT).value
    ids = [r['gsis_id'] for r in rows if r['gsis_id']]
    complete = AV.InactiveEvidence(
        game_id=GAME, clubs=('CAR', 'ATL'), clubs_declared=('ATL', 'CAR'),
        inactive_ids=frozenset(ids[:4]), completeness_verdict=AV.COMPLETE,
        source='official_inactives', retrieved_at=CUT,
        why='constructed for this report to exercise the COMPLETE branch; '
            'both clubs declared')
    scenarios = [
        scenario('no inactive evidence supplied', rows),
        scenario('a bare set of inactive ids (the old ACTIVE trigger)', rows,
                 inactive_ids=set(ids[:4])),
    ]
    # The COMPLETE branch cannot be reached through the legacy signature, so
    # it is measured directly on the canonical state.
    from nfl.production.state import slate_state as SS
    st = SS.build_one_game(2026, 2, GAME, CUT, inactive_evidence=complete)
    dc = D.build_from_state(st.value, information_cut=CUT)
    comp = collections.Counter(
        d.axis('official_availability').value for d in dc.value['dossiers'])
    doc = {
        'artifact': 'AVAILABILITY_SEMANTICS_CHANGE',
        'spec_version': 'availability-semantics-change-1',
        'fixture': {'game_id': GAME, 'information_cut': CUT,
                    'n_players': len(rows)},
        'reproduce': 'python3.12 nfl/research/state/availability_change.py',
        'the_defect': 'the dossier read a non-empty inactive_ids set as proof '
                      'that the official inactive board was COMPLETE, and '
                      'then called every unlisted player ACTIVE.',
        'why_active_is_now_unreachable': AV.WHY_GAME_ACTIVE_IS_UNREACHABLE,
        'prior_ruling': 'owner ruling 2026-09-10 item 4, implemented in '
                        'nfl/production/nonqb/inactives.py, which returns no '
                        'set named `active` and states that the complement '
                        'of the inactive list contains players who will '
                        'dress alongside practice-squad members who were '
                        'never going to.',
        'scenarios': scenarios,
        'complete_board_scenario': {
            'what': 'a COMPLETE both-club declaration, built explicitly',
            'distribution': dict(comp),
            'n_active': comp.get('ACTIVE', 0) + comp.get(AV.GAME_ACTIVE, 0),
            'finding': 'even with both clubs declared, no player reaches '
                       'ACTIVE. Completeness is necessary for a positive '
                       'claim and it is not sufficient.'},
        'total_became_active': sum(s['n_became_active'] for s in scenarios),
        'downstream_impact': _board_impact(),
    }
    OUT.write_text(json.dumps(doc, indent=1) + '\n')
    for s in scenarios:
        print(f'== {s["scenario"]}')
        print(f'   old {s["old_distribution"]}')
        print(f'   new {s["new_distribution"]}')
        print(f'   transitions {s["transitions"]}')
        print(f'   non-availability fields changed: '
              f'{s["non_availability_fields_changed"] or "NONE"}')
        print(f'   uncertainty old {s["uncertainty_state_old"]}')
        print(f'   uncertainty new {s["uncertainty_state_new"]}')
        print(f'   became ACTIVE: {s["n_became_active"]}')
    print(f'== COMPLETE board: {dict(comp)}  '
          f'ACTIVE={doc["complete_board_scenario"]["n_active"]}')
    print(f'wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
