"""Absence from an incomplete negative list is not affirmative evidence.

The single claim this suite defends: no evidence reachable in this checkout
can make a player ACTIVE, and completeness is carried as a verdict rather
than inferred from the shape of a container.
"""
from __future__ import annotations

import ast
import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import dossier as D                        # noqa: E402
from nfl.production.review import dossier_reference as R              # noqa: E402
from nfl.production.review import evidence as EV                      # noqa: E402
from nfl.production.state import availability as AV                   # noqa: E402
from nfl.production.state import slate_state as SS                    # noqa: E402
from nfl.production.universe import player_universe as PU             # noqa: E402

PASSED = FAILED = 0
GAME, CUT = '2026_02_CAR_ATL', '2026-09-22T23:00:00Z'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def rows():
    return PU.build(2026, 2, GAME, CUT).value


def complete_evidence(ids):
    return AV.InactiveEvidence(
        game_id=GAME, clubs=('CAR', 'ATL'), clubs_declared=('ATL', 'CAR'),
        inactive_ids=frozenset(ids), completeness_verdict=AV.COMPLETE,
        source='official_inactives', retrieved_at=CUT,
        declaration_timestamp=CUT, kickoff_utc='2026-09-20T17:00:00Z',
        content_hash='deadbeef', why='both clubs declared')


# -- 1. the vocabulary ------------------------------------------------------
def test_the_states_are_declared_and_closed():
    ok(set(AV.STATES) == {AV.OFFICIAL_INACTIVE, AV.INJURY_OUT,
                          AV.INJURY_DOUBTFUL, AV.INJURY_QUESTIONABLE,
                          AV.GAME_ACTIVE, AV.NOT_ON_INACTIVE_LIST,
                          AV.UNKNOWN},
       f'seven declared availability states: {len(AV.STATES)}')
    ok(set(AV.COMPLETENESS) == {AV.COMPLETE, AV.PARTIAL, AV.ABSENT,
                                AV.INVALID},
       'four declared completeness verdicts')
    ok(AV.GAME_ACTIVE not in AV.ASSERTS_NOTHING
       and AV.NOT_ON_INACTIVE_LIST in AV.ASSERTS_NOTHING,
       'NOT_ON_INACTIVE_LIST is classified as asserting nothing, and '
       'GAME_ACTIVE is not')
    ok(set(AV.WILL_NOT_PLAY) == {AV.OFFICIAL_INACTIVE, AV.INJURY_OUT},
       'only the two affirmative negatives assert he will not play')


# -- 2. completeness is carried, never inferred ----------------------------
def test_a_bare_set_is_always_partial():
    for n in (0, 1, 7, 53):
        ev = AV.InactiveEvidence.from_ids({f'p{i}' for i in range(n)})
        ok(ev.completeness_verdict == AV.PARTIAL,
           f'a set of {n} id(s) is PARTIAL, not COMPLETE: '
           f'{ev.completeness_verdict}')
    ok(AV.InactiveEvidence.absent().completeness_verdict == AV.ABSENT,
       'and nothing supplied is ABSENT')


def test_completeness_comes_from_the_inactives_layer():
    class O:
        def __init__(self, code, ev):
            self.code, self.evidence = code, ev
    base = {'game_id': GAME, 'inactive_by_team': {'CAR': ['a'], 'ATL': ['b']},
            'retrieved_at': CUT, 'kickoff_utc': '2026-09-20T17:00:00Z',
            'teams_without_a_list': []}
    e = AV.InactiveEvidence.from_inactives_outcome(
        O('POST_INACTIVES_COMPLETE', base))
    ok(e.completeness_verdict == AV.COMPLETE
       and set(e.clubs_declared) == {'CAR', 'ATL'},
       f'POST_INACTIVES_COMPLETE becomes COMPLETE with both clubs named: '
       f'{e.clubs_declared}')
    part = dict(base, inactive_by_team={'CAR': ['a'], 'ATL': []},
                teams_without_a_list=['ATL'])
    e = AV.InactiveEvidence.from_inactives_outcome(
        O('POST_INACTIVES_INCOMPLETE', part))
    ok(e.completeness_verdict == AV.PARTIAL,
       'one club\'s list is PARTIAL, and the missing club is named')
    e = AV.InactiveEvidence.from_inactives_outcome(
        O('INACTIVES_POST_KICKOFF', base))
    ok(e.completeness_verdict == AV.INVALID,
       'a list retrieved at or after kickoff is INVALID, not PARTIAL')
    ok(not e.usable, 'and an INVALID capture may decide nothing at all')


def test_no_container_shape_is_used_as_evidence():
    """The defect in its original form: `if inactive_ids:`. This reads the
    syntax tree of both modules for a truth test on the ids container."""
    for mod in ('nfl/production/state/availability.py',
                'nfl/production/state/slate_state.py',
                'nfl/production/review/dossier.py'):
        src = (_REPO / mod).read_text()
        tree = ast.parse(src)
        bad = []
        for n in ast.walk(tree):
            if isinstance(n, ast.If) and isinstance(n.test, ast.Name) \
                    and n.test.id in ('inactive_ids', 'have_inactives'):
                bad.append(n.test.id)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id == 'bool' and n.args \
                    and isinstance(n.args[0], ast.Name) \
                    and n.args[0].id == 'inactive_ids':
                bad.append('bool(inactive_ids)')
        ok(not bad, f'{mod.split("/")[-1]} makes no truth test on the ids '
                    f'container: {bad}')


# -- 3. ACTIVE is unreachable ----------------------------------------------
def test_incomplete_evidence_can_never_produce_active():
    for ev in (AV.InactiveEvidence.absent(),
               AV.InactiveEvidence.from_ids(set()),
               AV.InactiveEvidence.from_ids({'other'}),
               AV.InactiveEvidence(completeness_verdict=AV.INVALID,
                                   why='post kickoff')):
        for inj in (None, '', 'Questionable', 'Doubtful', 'Out'):
            a = AV.classify('p', evidence=ev, injury_report_status=inj)
            ok(a.value != AV.GAME_ACTIVE,
               f'{ev.completeness_verdict}/{inj!r} -> {a.value}, not '
               f'GAME_ACTIVE')


def test_even_a_complete_board_does_not_produce_active():
    r = rows()
    ids = [x['gsis_id'] for x in r if x['gsis_id']][:4]
    st = SS.build_one_game(2026, 2, GAME, CUT,
                           inactive_evidence=complete_evidence(ids)).value
    vals = collections.Counter(p.availability.value for p in st.players)
    ok(AV.GAME_ACTIVE not in vals,
       f'with BOTH clubs declared, nobody reaches GAME_ACTIVE: {dict(vals)}')
    unlisted = [p for p in st.players if p.gsis_id not in set(ids)
                and p.availability.value == AV.NOT_ON_INACTIVE_LIST]
    ok(unlisted, f'{len(unlisted)} unlisted players read NOT_ON_INACTIVE_LIST')
    ok(all(p.availability.grade == EV.DECLARED for p in unlisted),
       'graded DECLARED, because the absence itself is now established -- '
       'which is a different fact from being declared available')
    ok('not a claim that he is dressing' in (unlisted[0].availability.note
                                             or '').lower(),
       'and the axis says so in its own note')


def test_the_grade_separates_complete_from_partial():
    r = rows()
    ids = [x['gsis_id'] for x in r if x['gsis_id']][:4]
    comp = SS.build_one_game(2026, 2, GAME, CUT,
                             inactive_evidence=complete_evidence(ids)).value
    part = SS.build_one_game(2026, 2, GAME, CUT,
                             inactive_ids=set(ids)).value
    c = {p.gsis_id: p.availability for p in comp.players}
    q = {p.gsis_id: p.availability for p in part.players}
    shared = [pid for pid in c
              if c[pid].value == q[pid].value == AV.NOT_ON_INACTIVE_LIST]
    ok(shared, f'{len(shared)} players read the same value under both')
    ok(all(c[pid].grade == EV.DECLARED and q[pid].grade == EV.UNAVAILABLE
           for pid in shared),
       'and the same value carries a different GRADE: DECLARED under a '
       'complete board, UNAVAILABLE under a bare set. The value says what '
       'is known; the grade says how well.')


def test_an_out_designation_outranks_an_absent_list():
    ev = AV.InactiveEvidence.absent()
    ok(AV.classify('p', evidence=ev,
                   injury_report_status='Out').value == AV.INJURY_OUT,
       'OUT is an affirmative club statement and is used where the list '
       'decides nothing')
    for s, want in (('Doubtful', AV.INJURY_DOUBTFUL),
                    ('Questionable', AV.INJURY_QUESTIONABLE)):
        a = AV.classify('p', evidence=ev, injury_report_status=s)
        ok(a.value == want, f'{s} -> {want}')
        ok('establishes nothing either way' in (a.note or ''),
           f'and {s} is recorded as uncertainty, not availability')
    listed = AV.InactiveEvidence.from_ids({'p'})
    ok(AV.classify('p', evidence=listed,
                   injury_report_status='Out').value == AV.OFFICIAL_INACTIVE,
       'the official list outranks the designation for a player it names')


def test_a_complete_board_that_contradicts_an_out_records_both():
    ev = complete_evidence({'someone_else'})
    a = AV.classify('p', evidence=ev, injury_report_status='Out')
    ok(a.value == AV.INJURY_OUT, f'the OUT designation stands: {a.value}')
    ok('disagrees with an OUT designation' in (a.note or ''),
       'and the disagreement with the complete board is recorded rather '
       'than silently resolved')


# -- 4. the dossier relabels rather than decides ---------------------------
def test_the_dossier_no_longer_decides_availability():
    src = (_REPO / 'nfl/production/review/dossier.py').read_text()
    ok("'ACTIVE'" not in src.replace("'NOT_ON_INACTIVE_LIST'", 'X')
       .replace('GAME_ACTIVE', 'X'),
       'the literal ACTIVE is gone from the dossier')
    ok('AVAILABILITY_ALIAS' in src and 'SERIALISED_ALIASES' in src,
       'and the one rename it does make is DERIVED from the canonical '
       'alias table rather than restated here, so the vocabulary has one '
       'owner')
    ok(D.AVAILABILITY_ALIAS == {AV.OFFICIAL_INACTIVE: 'INACTIVE'},
       f'exactly one alias, kept because three consumers key on the literal '
       f"'INACTIVE': {D.AVAILABILITY_ALIAS}")


def test_every_availability_change_is_enumerated():
    r = rows()
    ids = [x['gsis_id'] for x in r if x['gsis_id']]
    a = R.build_dossiers(universe_rows=r, inactive_ids=set(ids[:4]),
                         information_cut=CUT)
    b = D.build_dossiers(universe_rows=r, inactive_ids=set(ids[:4]),
                         information_cut=CUT)
    A = {d.gsis_id: d for d in a.value['dossiers']}
    B = {d.gsis_id: d for d in b.value['dossiers']}
    became = [pid for pid in A
              if B[pid].axis('official_availability').value == 'ACTIVE']
    ok(not became, f'no player reads ACTIVE after the change: {len(became)}')
    was = sum(1 for pid in A
              if A[pid].axis('official_availability').value == 'ACTIVE')
    ok(was == 155, f'{was} players read ACTIVE before it, on this fixture')
    other = collections.Counter()
    for pid in A:
        da, db = A[pid].as_dict(), B[pid].as_dict()
        for k in ('evidence_provenance', 'state_identity', 'canonical'):
            db.pop(k, None)
        da.pop('spec_version'), db.pop('spec_version')
        for k in sorted(set(da) | set(db)):
            if k == 'axes':
                for ax in sorted(set(da['axes']) | set(db['axes'])):
                    if ax != 'official_availability' \
                            and da['axes'].get(ax) != db['axes'].get(ax):
                        other[f'axes.{ax}'] += 1
            elif da.get(k) != db.get(k):
                other[k] += 1
    ok(not other, f'and NO non-availability field changed anywhere: '
                  f'{dict(other) or "none"}')
    ok(a.value['by_uncertainty_state'] == b.value['by_uncertainty_state'],
       f'uncertainty classification is unchanged: '
       f'{b.value["by_uncertainty_state"]}')


def test_the_change_artifact_exists_and_agrees():
    p = _REPO / 'nfl/research/state/AVAILABILITY_SEMANTICS_CHANGE.json'
    ok(p.exists(), 'the change enumeration artifact is written')
    doc = json.loads(p.read_text())
    ok(doc['total_became_active'] == 0,
       f'it records that nobody became ACTIVE: {doc["total_became_active"]}')
    ok(doc['complete_board_scenario']['n_active'] == 0,
       'including under a COMPLETE both-club declaration')
    ok(all(not s['non_availability_fields_changed'] for s in doc['scenarios']),
       'and that no non-availability field moved in any scenario')


# -- 5. run_board must not run on import -----------------------------------
def test_importing_run_board_runs_nothing():
    src = (_REPO / 'nfl/production/board/run_board.py').read_text()
    tree = ast.parse(src)
    ok(any(isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
           and isinstance(n.test.left, ast.Name)
           and n.test.left.id == '__name__' for n in tree.body),
       'run_board has a __main__ guard')
    ok(any(isinstance(n, ast.FunctionDef) and n.name == 'main'
           for n in tree.body), 'and a main() entry point')
    def _name(call):
        f = call.func
        parts = []
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
        return '.'.join(reversed(parts))

    # sys.path.insert is bootstrap, not work. Everything else at module
    # level is something that runs because somebody imported the module.
    top_calls = [_name(n.value) for n in tree.body
                 if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                 and _name(n.value) != 'sys.path.insert']
    ok(not top_calls,
       f'no work executes at module level: {top_calls}')
    assigns = [t.id for n in tree.body if isinstance(n, ast.Assign)
               for t in n.targets if isinstance(t, ast.Name)]
    ok(all(a.isupper() or a == '_' for a in assigns),
       f'and module level holds only constants: {assigns}')
    board = _REPO / 'nfl/research/board/2026_02_NYG_LA/PLAYER_BOARD.json'
    before = board.read_bytes() if board.exists() else None
    import importlib
    from nfl.production.board import run_board as RB
    importlib.reload(RB)
    ok(board.read_bytes() == before if before else True,
       'and importing it writes no artifact')


def main():
    for t in (test_the_states_are_declared_and_closed,
              test_a_bare_set_is_always_partial,
              test_completeness_comes_from_the_inactives_layer,
              test_no_container_shape_is_used_as_evidence,
              test_incomplete_evidence_can_never_produce_active,
              test_even_a_complete_board_does_not_produce_active,
              test_the_grade_separates_complete_from_partial,
              test_an_out_designation_outranks_an_absent_list,
              test_a_complete_board_that_contradicts_an_out_records_both,
              test_the_dossier_no_longer_decides_availability,
              test_every_availability_change_is_enumerated,
              test_the_change_artifact_exists_and_agrees,
              test_importing_run_board_runs_nothing):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
