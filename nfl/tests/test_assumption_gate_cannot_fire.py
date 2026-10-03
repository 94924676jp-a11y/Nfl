"""`assert_promotable` is correct, and cannot block anything in production.

THE GUARD IS NOT THE PROBLEM. `assert_promotable` is well built: a FALSIFIED
CRITICAL assumption blocks, a still-DECLARED CRITICAL one blocks when
`require_tested`, a FALSIFIED MATERIAL one only warns, and it rewrites nothing.
Its logic is exercised below and it behaves as documented.

WHAT THIS FILE PINS IS THE WIRING (DEF-090). Two independent reasons the
assumption gate cannot refuse a production action today:

  1. THE ENFORCING FUNCTION HAS NO PRODUCTION CALLER. The chain is
     `assert_promotable` -> `adjustment_registry._assumption_gate` ->
     `assert_may_apply`, and `assert_may_apply` is called only from tests.
     Nothing in production converts the verdict into a refusal.

  2. THE JOIN KEY IS IN THE WRONG NAMESPACE. `_assumption_gate` passes
     `consumer=calling_layer`, and `assert_promotable` selects assumptions by
     `consumer in a.downstream_dependencies`. The adjustment registry's layer
     names are short -- `team_volume`, `line_play`, `coverage`, `game_state`,
     `team_environment` -- while `downstream_dependencies` holds dotted module
     paths and SCREAMING_CASE candidate names. The intersection is EMPTY, so
     `mine` is always empty, so the gate never examines anything. Even if (1)
     were fixed, the gate would still judge nothing. (OWNER RULE 1, 2026-10-02:
     `assert_promotable` now refuses an empty selection as BLOCKED/EMPTY_INPUT
     instead of returning PASS; the wiring defect is unchanged and the tests
     below pin its honest shape.)

THE ASYMMETRY IS THE INTERESTING PART, and it is why this went unnoticed.
`nfl/production/assumptions/run_audit.py` also calls the guard, and there the
consumers are drawn FROM the assumptions themselves -- `{d for a in settled for
d in a.downstream_dependencies}` -- so that join always matches by construction
and the report looks healthy and meaningful. The guard is therefore informative
exactly where it only reports, and inert exactly where it would enforce.

WHY THIS IS NOT FILED AS A GUARD DEFECT, AND WHAT IT IS INSTEAD. Nothing here
says the guard should be rewired today: which namespace is correct, and whether
an adjustment layer should be a promotion consumer at all, is a design question
about what the assumption registry governs. What is not acceptable is the census
reading `effect_on_failure: STOP` for this guard while both of the above hold, so
these tests exist to keep the claim honest and to fail loudly if someone
"repairs" one half and assumes the gate now works.
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import adjustment_registry as ADJ           # noqa: E402
from nfl.production.assumptions import registry as AR           # noqa: E402
from sportsplatform.governance import assumption as AS          # noqa: E402
from sportsplatform.governance.outcome import State             # noqa: E402

PASSED = FAILED = 0
REPO = pathlib.Path(_ROOT)


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _deps():
    out = set()
    for a in AR.all_assumptions():
        out |= set(a.downstream_dependencies)
    return out


def _applied_at():
    return {a.get('applied_at') for a in ADJ.ADJUSTMENTS.values()
            if a.get('applied_at')}


# ===================================== the guard's own logic is CORRECT

def test_a_falsified_critical_assumption_blocks():
    a = [x for x in AR.all_assumptions()
         if x.status == AS.FALSIFIED and x.criticality == AS.CRITICAL]
    check('the registry carries a falsified CRITICAL assumption to test with',
          bool(a), 'none present -- this test would be vacuous')
    if not a:
        return
    consumer = sorted(a[0].downstream_dependencies)[0]
    o = AS.assert_promotable(AR.all_assumptions(), consumer=consumer)
    check(f'promotion of {consumer!r} is refused', o.state is not State.PASS,
          f'{o.state} {o.code}')
    check('and the falsified assumption is named',
          a[0].id in (o.evidence.get('falsified_critical') or []),
          str(o.evidence.get('falsified_critical')))


def test_untested_is_not_passed():
    a = [x for x in AR.all_assumptions()
         if x.status == AS.DECLARED and x.criticality == AS.CRITICAL]
    if not a:
        print('  skip  no DECLARED CRITICAL assumption present')
        return
    consumer = sorted(a[0].downstream_dependencies)[0]
    strict = AS.assert_promotable(AR.all_assumptions(), consumer=consumer,
                                  require_tested=True)
    lax = AS.assert_promotable(AR.all_assumptions(), consumer=consumer,
                               require_tested=False)
    check('require_tested=True refuses an untested CRITICAL assumption',
          strict.state is not State.PASS, f'{strict.state} {strict.code}')
    check('and the two settings genuinely differ, so the flag is real',
          strict.code != lax.code or strict.state is not lax.state,
          f'{strict.code} vs {lax.code}')


def test_an_unknown_consumer_passes_vacuously():
    """The mechanism behind reason (2), shown in one line.

    OWNER RULE 1 (2026-10-02): this used to pin the vacuous PASS itself. A
    consumer no assumption names selects zero records, and a gate that examined
    nothing may not say NOT_BLOCKED. It now refuses with cause EMPTY_INPUT --
    which is still not a verdict about the consumer, and still proves reason
    (2): the join selected nothing.
    """
    # OWNER RULE 1 (2026-10-02): converted from a pin of the vacuous PASS.
    o = AS.assert_promotable(AR.all_assumptions(),
                             consumer='a_layer_no_assumption_names')
    check('a consumer no assumption names is refused as EMPTY_INPUT, not passed',
          o.state is State.BLOCKED and o.code == AS.CODE_EMPTY
          and o.evidence.get('cause') == 'EMPTY_INPUT', f'{o.state} {o.code}')
    check('because zero assumptions were selected',
          o.evidence.get('n_assumptions') == 0,
          str(o.evidence.get('n_assumptions')))


# ============================== reason 2: the join key namespaces disagree

def test_the_two_registries_share_no_consumer_identifier():
    deps, applied = _deps(), _applied_at()
    inter = sorted(deps & applied)
    check('NO adjustment layer appears in any downstream_dependencies',
          not inter,
          f'intersection {inter} -- if this fails the gate may now be able to '
          f'fire, which is GOOD, but DEF-090 and the census entry must be '
          f'updated rather than left claiming it cannot')
    print(f'       {len(applied)} adjustment layer(s), '
          f'{len(deps)} dependency name(s), {len(inter)} shared')


def test_every_adjustment_layer_passes_the_gate_vacuously():
    """Not one adjustment can be JUDGED by an assumption today.

    OWNER RULE 1 (2026-10-02): before the rule, every layer came back PASS
    with n_assumptions=0 and this test pinned that. Now every layer comes back
    BLOCKED/EMPTY_INPUT for the same reason -- the join selects nothing -- and
    that is the honest shape of DEF-090: the gate cannot find a falsified
    assumption for any layer because it cannot find ANY assumption for any
    layer. What is asserted is that no layer is refused for a MEASURED reason
    (CODE_BLOCKED / CODE_UNTESTED); the refusal every layer gets is the
    non-evidentiary one.
    """
    # OWNER RULE 1 (2026-10-02): converted from a pin of the vacuous PASS.
    judged = []
    for layer in sorted(_applied_at()):
        o = AS.assert_promotable(AR.all_assumptions(), consumer=layer,
                                 require_tested=False)
        if o.code in (AS.CODE_BLOCKED, AS.CODE_UNTESTED) \
                or o.evidence.get('cause') != 'EMPTY_INPUT':
            judged.append((layer, o.state.value, o.code))
    check('no adjustment layer is refused by the assumption gate for a measured '
          'reason; each gets the EMPTY_INPUT refusal', not judged, str(judged))
    check('and that is because each selects zero assumptions, not because '
          'each is sound',
          all(AS.assert_promotable(AR.all_assumptions(), consumer=l,
                                   require_tested=False)
              .evidence.get('n_assumptions') == 0
              for l in _applied_at()),
          'some layer DID select assumptions -- re-read DEF-090')


# ==================== reason 1: the enforcing function has no prod caller

def _callers_of(name):
    """Modules that call `name`, split into production and test."""
    prod, test = set(), set()
    for p in sorted(REPO.rglob('*.py')):
        s = str(p)
        if '/__pycache__/' in s or '/.git/' in s:
            continue
        try:
            tree = ast.parse(p.read_text())
        except Exception:                                      # noqa: BLE001
            continue
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            got = (getattr(f, 'attr', None) if isinstance(f, ast.Attribute)
                   else getattr(f, 'id', None))
            if got != name:
                continue
            rel = str(p.relative_to(REPO))
            if f'def {name}' in p.read_text() and rel.endswith(
                    'adjustment_registry.py') and name == 'assert_may_apply':
                pass
            (test if '/tests/' in rel or rel.startswith('nfl/tests')
             else prod).add(rel)
    return prod, test


def test_assert_may_apply_is_called_only_by_tests():
    prod, test = _callers_of('assert_may_apply')
    prod = {m for m in prod if not m.endswith('adjustment_registry.py')}
    check('assert_may_apply has at least one test caller', bool(test),
          'no caller at all -- then this file is testing nothing')
    check('assert_may_apply has NO production caller', not prod,
          f'{sorted(prod)} -- if a production caller now exists the gate may '
          f'be able to refuse, and DEF-090 plus the census must be updated')
    print(f'       production callers: {sorted(prod) or "none"}; '
          f'test callers: {len(test)}')


def test_the_gate_helper_is_reached_only_through_that_function():
    """So (1) is sufficient on its own to make the gate unreachable."""
    src = (REPO / 'nfl/production/adjustment_registry.py').read_text()
    check('_assumption_gate is called exactly once in its module',
          src.count('_assumption_gate(') == 2,   # the def plus one call
          str(src.count('_assumption_gate(')))
    check('and that one call is inside assert_may_apply',
          src.index('def assert_may_apply')
          < src.index('ga = _assumption_gate('),
          'the call is not inside assert_may_apply any more -- re-verify')


# ================================ the asymmetry that hid this for so long

def test_the_audit_path_always_matches_by_construction():
    """run_audit draws consumers FROM the assumptions, so its join cannot miss.

    That is why the promotion report looks meaningful while the enforcing path
    is inert. The guard is informative exactly where it only reports.
    """
    src = (REPO / 'nfl/production/assumptions/run_audit.py').read_text()
    check('run_audit derives its consumers from downstream_dependencies',
          'for d in a.downstream_dependencies' in src
          or 'd for a in settled' in src, 'the derivation has changed')
    check('and it writes the verdict into a report body rather than refusing',
          "body['promotion']" in src, 'run_audit may now enforce -- re-check')
    # every consumer it reports on selects at least one assumption
    consumers = sorted({d for a in AR.all_assumptions()
                        for d in a.downstream_dependencies})
    empty = [c for c in consumers
             if AS.assert_promotable(AR.all_assumptions(), consumer=c,
                                     require_tested=False)
             .evidence.get('n_assumptions') == 0]
    check('every consumer the audit reports on selects >=1 assumption',
          not empty, str(empty))
    print(f'       audit reports on {len(consumers)} consumer(s), '
          f'{len(empty)} of them vacuous')


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
