"""appearance's positions must stay inside participation_prior's. DEF-066.

`layers.participation` used `share_prior.get(pid, 0.0)`: a player with no share
prior silently got share zero, and participation feeds volume. Measured, that
default is UNREACHABLE on the production path — but only because of a single
filter expression, and it is reachable the moment either of two sets moves.

THE CONTAINMENT, and why each half matters:

  run_forecast.py hands the SAME `players` object to slate_fits (line 1658,
  which builds the prior via PP.share_prior) and to run_game (line 1730), with
  no reassignment between them. `players` is `qbs + list(pool.value)`, so it
  DOES contain quarterbacks, and share_prior skips them on
  `if pos not in POSITIONS: continue` — they are genuinely absent from the map.
  What saves it is run_game line 716: `recv = [q for q in players if
  q['position'] in RECEIVING_POS]`, and line 872 passes `recv`, not `players`,
  to appearance.

  So: RECEIVING_POS ⊆ POSITIONS keeps the default unreachable. If RECEIVING_POS
  ever gains a position the prior does not cover, or appearance is ever handed
  `players` instead of `recv`, quarterbacks land in participation at share 0.0
  and nothing says so.

`participation` now REFUSES with PARTICIPATION_PRIOR_INCOMPLETE instead of
defaulting, so the failure is fail-closed rather than silent. This suite exists
so the containment cannot rot unnoticed underneath that refusal — a refusal
that fires every week is a broken pipeline, not a working guard.
"""
import ast
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import football_engine as FE          # noqa: E402
from nfl.production.nonqb import layers as LY                   # noqa: E402
from nfl.production.nonqb import participation_prior as PP      # noqa: E402
from sportsplatform.governance.outcome import Outcome, State    # noqa: E402

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


def test_the_containment_holds():
    print('\n[1] RECEIVING_POS is inside POSITIONS')
    extra = sorted(set(FE.RECEIVING_POS) - set(PP.POSITIONS))
    check('every position appearance is given has a share prior', not extra,
          f'uncovered: {extra} -- these would reach participation with no '
          f'prior' if extra else
          f'{FE.RECEIVING_POS} within {PP.POSITIONS}')
    check('both sets are non-empty', bool(FE.RECEIVING_POS) and bool(PP.POSITIONS))


def test_appearance_is_handed_recv_and_not_players():
    print('\n[2] the filter that makes the containment load-bearing')
    src = (_REPO / 'nfl/production/nonqb/football_engine.py').read_text()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute)
             and n.func.attr == 'appearance']
    check('appearance is called', bool(calls), f'{len(calls)} call site(s)')
    bad = []
    for c in calls:
        args = [ast.unparse(a) for a in c.args]
        # third positional is the player pool
        if len(args) >= 3 and args[2] != 'recv':
            bad.append(args[2])
    check('every call passes `recv`, never the unfiltered pool', not bad,
          str(bad) or 'the pool reaching appearance is position-filtered')
    check('and the filter names RECEIVING_POS',
          'in RECEIVING_POS' in src,
          'so widening RECEIVING_POS is the only way to widen the pool')


def test_a_missing_prior_refuses_rather_than_zeroing():
    print('\n[3] the refusal, executed')
    # An appearance result with a pid the prior does not carry. Before DEF-066
    # this returned PARTICIPATION_OK with that player at share 0.0.
    import numpy as np
    ap = Outcome.ok('APPEARANCE_OK',
                    value={'p1': np.ones(4), 'ghost': np.ones(4)},
                    spec_version='t', test_only=True, n_players=2)
    r = LY.participation(ap, {'p1': 0.6})
    check('it does not PASS', r.state is not State.PASS,
          f'{r.state.name}[{r.code}]')
    check('...with the named code', r.code == 'PARTICIPATION_PRIOR_INCOMPLETE',
          str(r.code))
    check('...naming the player it will not invent a share for',
          'ghost' in (r.detail or ''), (r.detail or '')[:80])
    # And the complete case is unaffected.
    ok = LY.participation(ap, {'p1': 0.6, 'ghost': 0.4})
    check('a COMPLETE prior still passes', ok.state is State.PASS,
          f'{ok.state.name}[{ok.code}]')
    check('...and the arithmetic is unchanged',
          abs(float(ok.value['p1'][0]) - 0.6) < 1e-9
          and abs(float(ok.value['ghost'][0]) - 0.4) < 1e-9,
          'share only when he appears')


def test_no_silent_zero_default_remains_in_the_layer():
    """By AST, because a substring check matches its own documentation.

    My first version of this grepped layers.py for the literal
    `share_prior.get(pid, 0.0)` -- and failed, because the comment explaining
    that the default was REMOVED quotes it. That is the third time in one
    session I have written a source-text assertion that matched the prose
    describing the thing it forbids: the same shape as the two attempts
    test_orchestrator documents rejecting, and as my first content check on the
    mock fixtures. A text search cannot tell code from a description of code.
    The tree can.
    """
    print('\n[4] the default is gone, not merely guarded (by AST)')
    src = (_REPO / 'nfl/production/nonqb/layers.py').read_text()
    tree = ast.parse(src)
    defaults = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'get' and len(n.args) == 2
                and isinstance(n.args[1], ast.Constant)
                and isinstance(n.args[1].value, (int, float))
                and not isinstance(n.args[1].value, bool)):
            base = ast.unparse(n.func.value)
            if 'share_prior' in base or 'prior' in base:
                defaults.append((base, n.lineno, ast.unparse(n.args[0])))
    # DECLARED, NOT HIDDEN. This check found a SECOND instance the moment it
    # was written by AST rather than by substring, and narrowing the filter to
    # make the suite green would have been the whole defect class again:
    #
    #   priors['pos_catch_rate'].get(pos, 0.0)   layers.py receiving_conversion
    #
    # Keyed on POSITION, not player id, so it is a different reachability
    # question -- and a worse consequence. When a player has no personal
    # history the layer sets `c = pos_rate` directly, so an uncovered position
    # means a catch rate of ZERO: he catches nothing in any draw. frozen_priors
    # builds that map from observed history and refuses only when it is
    # entirely empty, so nothing guarantees it covers every position on a
    # slate. Recorded as DEF-069 and deliberately NOT fixed here, because what
    # a missing positional catch rate should be is a model decision with its
    # own evidence, not a plumbing repair.
    KNOWN = {("priors['pos_catch_rate']", 'pos'): 'DEF-069'}
    undeclared = [d for d in defaults if (d[0], d[2]) not in KNOWN]
    check('no UNDECLARED prior lookup defaults to a number', not undeclared,
          str(undeclared) or f'{len(defaults)} declared: '
                             f'{sorted(KNOWN.values())}')
    check('the player-keyed default DEF-066 removed has not returned',
          not [d for d in defaults if 'share_prior' in d[0]],
          'share_prior is looked up by player id, which is the DEF-066 class')
    check('every declared exception names an open defect',
          all(v.startswith('DEF-') for v in KNOWN.values()),
          'an exception with no defect id is an excuse')
    fns = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    check('participation is still defined', 'participation' in fns)
    check('the refusal code is raised inside participation',
          any(isinstance(n, ast.Constant)
              and n.value == 'PARTICIPATION_PRIOR_INCOMPLETE'
              for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == 'participation'
              for n in ast.walk(f)),
          'not merely present somewhere in the module')


def main():
    print(__doc__.strip().splitlines()[0])
    test_the_containment_holds()
    test_appearance_is_handed_recv_and_not_players()
    test_a_missing_prior_refuses_rather_than_zeroing()
    test_no_silent_zero_default_remains_in_the_layer()
    print(f'\n{PASSED} passed, {FAILED} failed')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
