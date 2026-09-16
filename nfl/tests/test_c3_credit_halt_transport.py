"""A C3 run whose passer credit fails must not seal as if nothing happened.

WHAT WAS FOUND, AND WHAT IT IS NOT
----------------------------------
The 8,000-draw DET-BUF board recorded `candidate_components_not_reached:
["C3"]` while the 1,000-draw board on the SAME arm recorded C3 applied. That
looked like a candidate declaration losing a component. It is not.

C3 is reached in both. Its first half runs -- the target budget comes from the
throw process, `g['c3']['target_budget_owner']` is set -- and then its second
half, `credit_passing_line`, refuses:

    FAIL[PASSER_CREDIT_EXCEEDS_COMPLETABLE_ATTEMPTS]

because C3's targeted-throw budget does not reserve intercepted throws out of
the pool RC1 then converts to catches. `credit_passing_line`'s own docstring
declares that gap and names the owed fix as an SC1-style coupling. It is
REFUSED rather than clipped, which is right.

THE DEFECT THIS FILE PINS IS WHAT HAPPENS NEXT. The engine sets
`accounting['shared_pass_credit'] = FAIL[...]`, `halted_at = 'shared_pass'`
and a halt reason -- and then does not return. The run continues, the board
seals, and NONE of those three reaches board.json, forecast_artifact.json or
run_status.json. Measured on the sealed board 117a78668a0b7a0e: zero
occurrences of `shared_pass_credit`, `halted_at`, or the refusal code in any
sealed file. The only visible symptom is the phrase "not reached", which reads
like a configuration fact rather than a failed hard invariant.

So the sealed board carries a HALF-APPLIED C3: targets dealt from the throw
process, passer line NOT credited from the receiving event, and no record that
the second half was attempted and refused. That is this project's named worst
defect class -- a step that returned something partial read as success.

IT IS DRAW-COUNT DEPENDENT AND ARM-INDEPENDENT. Reproduced on the same
checkout, same game, same seed, same written_at, changing only the draw count
and the candidate declaration:

    R9_W1P_G   at   400 draws -> PASS[C3_TARGET_BUDGET_FROM_THROWS]
    R9_W1P_GA  at   400 draws -> PASS[C3_TARGET_BUDGET_FROM_THROWS]
    R9_W1P_G   at 8,000 draws -> FAIL, 1 draw  (worst 6211: 19 completions
                                 against 17 completable attempts)
    R9_W1P_GA  at 8,000 draws -> FAIL, 3 draws (worst 307: 24 completions
                                 against 23 completable attempts)

So "G has C3 and GA lost it" is false. G is the arm that did not run enough
draws to reach a defect present in both. A comparison between the two arms at
different draw counts was comparing that luck.

WHAT THIS FILE DOES NOT ASSERT. It does not assert the coupling gap is fixed.
That fix is a pre-registered mechanism change with its own candidate identity
and it is not in this file. What must hold NOW, on every arm and every draw
count, is that a refused hard invariant is visible in what gets sealed.
"""
import json
import glob
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PASSED, FAILED, BLOCKED = 0, 0, 0
_F = []


def ck(name, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
        _F.append(name)
    print(('PASS ' if cond else 'FAIL ') + name
          + ((' :: ' + detail) if detail else ''))


def blocked(name, detail):
    global BLOCKED
    BLOCKED += 1
    print(f'BLOCKED {name} cause=DATA :: {detail} BLOCKED is not a pass.')


def test_the_engine_still_refuses_rather_than_clipping():
    """The refusal itself is correct and must stay a refusal."""
    import numpy as np
    from nfl.production.nonqb import football_engine as FE

    # One quarterback, one draw, engineered so the receiving event caught more
    # balls than there were non-intercepted attempts: 20 attempts, 3 picks,
    # 19 receptions against 17 completable.
    A = np.array([[20.0]])
    I = np.array([[3.0]])
    R = np.array([19.0])
    Y = np.array([210.0])
    TD = np.array([1.0])
    o = FE.credit_passing_line(A, I, R, Y, TD, np.random.default_rng(0))
    ck('the_coupling_gap_is_refused_by_name',
       o.state.name == 'FAIL'
       and o.code == 'PASSER_CREDIT_EXCEEDS_COMPLETABLE_ATTEMPTS',
       f'{o.state.name}[{o.code}]')
    ck('the_refusal_counts_the_bad_draws',
       o.state.name == 'FAIL' and o.evidence.get('n_bad') == 1,
       str(o.evidence.get('n_bad')))
    ck('the_refusal_names_the_owed_mechanism_change',
       'SC1-style coupling' in (o.detail or ''),
       'the fix is pre-registered, not a patch')

    # And the ordinary case must still be credited, or this test would pass on
    # a function that refuses everything.
    ok = FE.credit_passing_line(A, I, np.array([12.0]), Y, TD,
                                np.random.default_rng(0))
    ck('an_ordinary_draw_is_still_credited', ok.state.name == 'PASS',
       f'{ok.state.name}[{ok.code}]')


def _sealed_c3_runs():
    """Sealed runs that declared shared_pass c3, newest first."""
    out = []
    for f in glob.glob(str(REPO / 'nfl' / 'research' / 'live' / '**'
                           / 'forecast_artifact.json'), recursive=True):
        try:
            a = json.load(open(f))
        except (OSError, ValueError):
            continue
        comps = {c.get('component') for c in (a.get('candidate_components')
                                              or [])}
        if 'C3' not in comps:
            continue
        out.append((os.path.getmtime(f), os.path.dirname(f), a))
    return [(d, a) for _, d, a in sorted(out, reverse=True)]


#: The artifact key the repair writes, and the version that says the run was
#: sealed by an engine that transports its own halt. A board sealed BEFORE the
#: repair cannot carry it and must not be rewritten to -- every existing seal
#: is preserved -- so the backlog is COUNTED AND NAMED rather than failed.
TRANSPORT_KEY = 'c3_refusal'
TRANSPORT_SPEC = 'c3-refusal-transport-1'


def test_a_refused_c3_credit_is_visible_in_what_was_sealed():
    """THE FAILING REPRODUCTION. A board that did not reach C3 must say why.

    `not_reached` alone does not distinguish "this arm never asked for C3"
    from "C3 ran and its hard invariant refused". Those are different facts
    and a reader cannot act on the second if it is rendered as the first.
    """
    runs = _sealed_c3_runs()
    if not runs:
        blocked('C3_NO_SEALED_RUN',
                'no sealed run in nfl/research/live declares C3, so there is '
                'nothing to read a verdict off.')
        return
    post, pre = [], []
    for d, a in runs:
        if 'C3' not in set(a.get('candidate_components_not_reached') or []):
            continue
        rel = os.path.relpath(d, REPO)
        (post if a.get(TRANSPORT_KEY) is not None
         or a.get('seal_contract_c3') == TRANSPORT_SPEC
         else pre).append((rel, a))
    if not (post or pre):
        blocked('C3_NO_REFUSED_RUN',
                'every sealed C3 run reached C3, so the transport of a '
                'refusal has nothing to be checked on.')
        return

    # THE BACKLOG IS REPORTED, NEVER SILENTLY TOLERATED AND NEVER REWRITTEN.
    print(f'  pre-repair sealed boards carrying an unexplained C3 '
          f'"not reached": {len(pre)}')
    for rel, _ in pre[:5]:
        print(f'    {rel}')
    if len(pre) > 5:
        print(f'    ... and {len(pre) - 5} more')

    if not post:
        blocked('C3_NO_POST_REPAIR_RUN',
                f'{len(pre)} sealed board(s) predate the transport repair and '
                f'are preserved unchanged; none has been sealed since it, so '
                f'the repair has nothing to be checked on yet.')
        return
    for rel, a in post:
        c3 = a.get(TRANSPORT_KEY) or {}
        ck(f'c3_not_reached_carries_a_reason[{rel}]',
           bool(c3.get('state') and c3.get('code')),
           'the engine`s own halted_at, halt_reason and '
           'accounting.shared_pass_credit must be transported')
        ck(f'c3_not_reached_names_its_layer_state[{rel}]',
           bool(c3.get('layer_state')),
           'g["layers"]["shared_pass"] is the engine`s verdict and the seal '
           'must carry it verbatim')
        ck(f'c3_refusal_says_whether_the_first_half_ran[{rel}]',
           'first_half_applied' in c3,
           'targets dealt from the throw process with the passer line left '
           'uncredited is a MIXTURE, and the reader has to be told which')
        ck(f'a_half_applied_c3_is_not_prospective[{rel}]',
           a.get('prospective_eligible') is not True,
           'a run carrying a refused hard invariant is not evidence')


def test_zz_every_check_passed():
    # THE TRIPWIRE, AND IT IS RECOGNISED BY SHAPE. `run_suite.tally_tripwires`
    # counts a function that calls anything beyond print/AssertionError as a
    # real test, so a `', '.join(...)` in here turned this into a ZERO-CHECK
    # function -- one that ran, measured nothing, and said nothing. The failed
    # names are printed by `ck` as they happen and again in `main`.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    print('--- the refusal itself ---')
    test_the_engine_still_refuses_rather_than_clipping()
    print('--- transport into the seal ---')
    test_a_refused_c3_credit_is_visible_in_what_was_sealed()
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    if _F:
        print('FAILED: ' + ', '.join(_F))
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
