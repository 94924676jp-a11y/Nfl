"""'Missing' is a state. 'Zero' is an outcome. Never confuse them.

Owner directive 2026-09-25, raised from a postgame grading rule to a repo-wide
invariant. This suite is the permanent guard.

It checks four things, and they are deliberately separate:

  1. THE VOCABULARY EXISTS AND DOES NOT COLLAPSE. Four states, five joins,
     distinct strings, and two of them explicitly NOT gradeable.
  2. THE CONTRACT REFUSES each way the distinction can be lost -- an
     undeclared join, an ungradeable join carrying a number, and a zero with
     no stated basis.
  3. THE LIVE GRADER'S EVERY GRADED ROW PROVES ITS JOIN. Not a sample: every
     row, from a real run, with the tally reported.
  4. THE DEF-063 REGRESSION CANNOT RETURN. A board player whose name the
     index does not know is refused, not zeroed -- proven by constructing
     exactly that input rather than by reading the source.

Why the invariant is repo-wide and not just about grading: a zero that came
from a failed lookup is indistinguishable from a real zero ONCE IT IS A
FLOAT. Every layer downstream of the join -- the ledger, the buckets, the
prospective scoring, any future calibration -- inherits the confusion and
cannot undo it. The only place the difference still exists is the join
itself, so that is where it must be recorded.
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import join_provenance as JP  # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  PASS {label}' + (f' -- {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f' -- {detail}' if detail else ''))


def _refuses(fn, *a, **kw):
    """Did it raise one of the contract's own errors?"""
    try:
        fn(*a, **kw)
    except (JP.AnonymousZero, JP.JoinNotDeclared) as e:
        return type(e).__name__
    except Exception as e:                       # any other error is a bug
        return f'WRONG_ERROR:{type(e).__name__}:{e}'
    return None


def test_the_four_states_are_four_distinct_things():
    print('\n[1] the vocabulary does not collapse')
    names = ('REAL_ZERO', 'PLAYER_NOT_IN_OUTCOME', 'IDENTITY_NOT_ESTABLISHED',
             'ABSENCE_RESOLVED_TO_ZERO')
    vals = [getattr(JP, n, None) for n in names]
    check('all four states are defined', all(vals),
          ', '.join(f'{n}={v}' for n, v in zip(names, vals)))
    check('the four are distinct values', len(set(vals)) == 4)
    check('five joins, all distinct', len(set(JP.JOINS)) == len(JP.JOINS) == 5,
          str(JP.JOINS))
    # THE LOAD-BEARING ONE. If either of these ever became gradeable, a failed
    # join would be allowed to carry a number again.
    check('IDENTITY_NOT_ESTABLISHED is NOT gradeable',
          JP.IDENTITY_NOT_ESTABLISHED not in JP.GRADEABLE)
    check('PLAYER_NOT_IN_OUTCOME is NOT gradeable',
          JP.PLAYER_NOT_IN_OUTCOME not in JP.GRADEABLE)
    check('a governed absence IS gradeable',
          JP.ABSENCE_RESOLVED_TO_ZERO in JP.GRADEABLE,
          'his club played and he recorded nothing; zero is the measurement')
    check('REAL_ZERO is a zero BASIS, not a join',
          JP.REAL_ZERO in JP.ZERO_BASES and JP.REAL_ZERO not in JP.JOINS,
          'how a zero came to be, not how the row was matched')


def test_the_contract_refuses_every_way_the_zero_can_go_anonymous():
    print('\n[2] the contract refuses, rather than documenting')
    check('a graded row with NO provenance is refused',
          _refuses(JP.assert_graded_row, {}, actual=12.4) == 'JoinNotDeclared')
    for bad in (JP.IDENTITY_NOT_ESTABLISHED, JP.PLAYER_NOT_IN_OUTCOME):
        row = {'join_provenance': JP.stamp(bad, key='x')}
        # NOT a zero -- an ungradeable join may not carry ANY number.
        check(f'{bad} carrying 12.4 is refused',
              _refuses(JP.assert_graded_row, row, actual=12.4)
              == 'AnonymousZero')
    row = {'join_provenance': JP.stamp(JP.MATCHED_BY_IDENTITY, key='g')}
    check('a matched row with 0.0 and no zero_basis is refused',
          _refuses(JP.assert_graded_row, row, actual=0.0) == 'AnonymousZero',
          'a real zero and a failed join are the same float')
    check('...but the same row with a NON-zero actual is fine',
          _refuses(JP.assert_graded_row, row, actual=8.2) is None)
    ok = {'join_provenance': JP.stamp(JP.MATCHED_BY_IDENTITY, key='g',
                                      zero_basis=JP.REAL_ZERO)}
    check('a matched row with 0.0 and REAL_ZERO is accepted',
          _refuses(JP.assert_graded_row, ok, actual=0.0) is None,
          'Ray Davis was active and did nothing; the model owns that miss')
    check('an invented zero_basis is refused at stamp time',
          _refuses(JP.stamp, JP.MATCHED_BY_IDENTITY,
                   zero_basis='PROBABLY_FINE') == 'AnonymousZero')
    check('an invented join is refused at stamp time',
          _refuses(JP.stamp, 'LOOKS_RIGHT') == 'JoinNotDeclared')


def test_every_graded_row_from_the_live_grader_proves_its_join():
    print('\n[3] the live grader: every row, not a sample')
    from nfl.postgame import grade_projections as G
    r = G.grade()
    if r.state.name != 'PASS':
        check('grading ran', False, f'{r.state.name} {r.code}')
        return
    rows = r.value['rows']
    ev = r.as_dict()['evidence']
    graded = [(x, s, d) for x in rows for s, d in x['stats'].items()
              if d.get('state') == 'GRADED']
    check('the run produced graded rows', len(graded) > 0,
          f'{len(rows)} players, {len(graded)} graded observations')
    bad = []
    for x, s, d in graded:
        try:
            JP.assert_graded_row(x, actual=d.get('actual'),
                                 where=f"{x.get('player')}/{s}")
        except (JP.AnonymousZero, JP.JoinNotDeclared) as e:
            bad.append(str(e))
    check('EVERY graded observation proves its join', not bad,
          f'{len(graded)} checked' if not bad else bad[0])
    aud = ev.get('join_provenance') or {}
    check('the run reports its provenance tally', bool(aud.get('by_join')),
          str(aud.get('by_join')))
    check('the tally reports no anonymous rows', aud.get('clean') is True,
          str(aud.get('anonymous')))
    zb = aud.get('graded_zeros_by_basis') or {}
    check('graded zeros are split by basis, not pooled',
          'UNDECLARED' not in zb and sum(zb.values()) > 0, str(zb))
    # The finding worth keeping: identity was available all along.
    byj = aud.get('by_join') or {}
    check('identity carries the run; the name path is not load-bearing',
          byj.get(JP.MATCHED_BY_IDENTITY, 0) > 0, str(byj))


def test_the_def_063_regression_cannot_return():
    """RUN the inputs through the real grader, don't read the source.

    A source-order check ('the guard appears before resolve_absent') argues
    that a fix is present. It does not establish that the fix fires, and it
    cannot tell an over-strict guard from a correct one. So both shapes are
    constructed and executed.

    THE SECOND ONE IS HERE BECAUSE I GOT IT WRONG. My first guard refused any
    board id the name index could not name. The two unnamed ids in this run
    are the kickers, and a gsis_id IS an identity -- refusing them would have
    re-broken kicker grading from the opposite direction. The postgame harness
    caught it. The rule is that the CLUB governs the zero, resolved by
    identity; a missing display name is a missing label, not a missing player.
    """
    import json
    import numpy as np
    from nfl.postgame import grade_projections as G
    from nfl.postgame import outcome as OC
    from nfl.dfs import player_universe as PU

    print('\n[4] both shapes, executed through the real grader')
    res = OC.require(sl=OC._DEFAULT).value
    line, code = OC.resolve_absent('whoever', 'BUF', res)
    check('a covered club makes absence a governed zero',
          line is not None and code == OC.ZERO_BY_ABSENCE, f'code={code}')
    line2, code2 = OC.resolve_absent('whoever', None, res)
    check('NO club makes it unscorable, never zero',
          line2 is None and code2 == OC.UNSCORABLE, f'code={code2}')

    real = PU.dk_points_by_id
    real_loads = json.loads

    def _run(ghost, club):
        """Insert a board id with a confident projection and maybe a club."""
        def _draws(man, npz, **kw):
            d, rep = real(man, npz, **kw)
            return dict(d, **{ghost: np.full(8000, 9.9)}), rep

        def _loads(txt, **kw):
            o = real_loads(txt, **kw)
            if club and isinstance(o, dict) and 'layers' in o:
                spec = o['layers'].get('dk_scoring') or {}
                rt = spec.get('row_teams')
                if isinstance(rt, dict):
                    rt[ghost] = club
                elif isinstance(rt, list):
                    spec['row_ids'].append(ghost)
                    rt.append(club)
            return o

        G.PU.dk_points_by_id, G.json.loads = _draws, _loads
        try:
            return G.grade()
        finally:
            G.PU.dk_points_by_id, G.json.loads = real, real_loads

    # (a) A STRANGER: an id nothing in the sealed run places on a roster.
    GHOST = '00-0000000'
    check('the stranger id is absent from the outcome',
          not any((v or {}).get('player_id') == GHOST
                  for v in res['players'].values()))
    r = _run(GHOST, None)
    if r.state.name != 'PASS':
        check('the grader ran on the stranger fixture', False, str(r.code))
        return
    ev = r.as_dict()['evidence']
    check('(a) a stranger is NOT graded',
          not any(x['player'] == GHOST for x in r.value['rows']),
          'a 9.9 projection with nothing to join to produces no row')
    check('(a) a stranger is NOT zeroed',
          GHOST not in (ev.get('players_zero_by_absence') or []))
    rep = [x for x in (ev.get('players_not_in_outcome') or [])
           if x.get('player') == GHOST]
    check('(a) he is reported IDENTITY_NOT_ESTABLISHED',
          bool(rep) and rep[0].get('reason') == JP.IDENTITY_NOT_ESTABLISHED,
          str(rep))
    check('(a) the report says WHY, not just that it failed',
          bool(rep) and 'club' in (rep[0].get('detail') or ''),
          (rep[0].get('detail') if rep else ''))

    # (b) THE KICKER SHAPE: a valid identity on a covered roster with no
    # display name. This MUST be graded, and its zero MUST be governed.
    r2 = _run(GHOST, 'BUF')
    ev2 = r2.as_dict()['evidence']
    row = [x for x in r2.value['rows'] if x['player'] == GHOST]
    check('(b) an unnamed id ON A COVERED CLUB is graded, not refused',
          bool(row), 'a gsis_id is an identity; the missing name is a label')
    check('(b) and his zero is governed, never anonymous',
          bool(row) and row[0]['join_provenance'].get('zero_basis')
          == JP.ABSENCE_RESOLVED_TO_ZERO,
          row[0]['join_provenance'] if row else '')
    check('(b) he is NOT in the unscorable list',
          not [x for x in (ev2.get('players_not_in_outcome') or [])
               if x.get('player') == GHOST])
    check('(b) the two shapes reach DIFFERENT states from the same id',
          bool(rep) and bool(row),
          'club present vs absent is the whole difference')

    # The ordering that makes the real slate work, now that it is proven.
    src = (Path(_REPO) / 'nfl/postgame/grade_projections.py').read_text()
    check('identity is tried before the name index',
          src.index('actual_by_id.get(gid)')
          < src.index('actual.get(UNI.norm'),
          'prefer the id, fall back to the name')


def test_the_other_production_graders_carry_the_same_stamp():
    print('\n[5] the invariant is repo-wide, not one module')
    gw = (Path(_REPO) / 'nfl/postgame/grade_week.py').read_text()
    check('grade_week stamps its rows', "'join_provenance':" in gw,
          f"{gw.count(chr(39) + 'join_provenance' + chr(39))} row type(s)")
    check('grade_week joins on identity only',
          "by_id.get(r['gsis_id'])" in gw and 'UNI.norm' not in gw,
          'no name path exists there to fall back to')
    # Every GRADED emitter in the postgame namespace is accounted for. A new
    # one appearing here should fail this and be classified deliberately.
    emitters = sorted(
        p.name for p in (Path(_REPO) / 'nfl/postgame').glob('*.py')
        if "'state': 'GRADED'" in p.read_text()
        or "'grade_state': ('GRADED'" in p.read_text())
    known = {'grade_projections.py', 'grade_week.py'}
    check('no unaccounted GRADED emitter in nfl/postgame',
          set(emitters) <= known, f'{emitters} vs known {sorted(known)}')
    for m in emitters:
        check(f'{m} imports the contract',
              'join_provenance' in (Path(_REPO) / 'nfl/postgame' / m).read_text())


def main():
    print(__doc__.strip().splitlines()[0])
    test_the_four_states_are_four_distinct_things()
    test_the_contract_refuses_every_way_the_zero_can_go_anonymous()
    test_every_graded_row_from_the_live_grader_proves_its_join()
    test_the_def_063_regression_cannot_return()
    test_the_other_production_graders_carry_the_same_stamp()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
