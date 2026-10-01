#!/usr/bin/env python3.12
"""A missing predicted-lineup feed must never arrive at the projection as "he is not the starter".

THE DEFECT THESE CHECKS EXIST FOR. On the 2026 week 4 PIT@CLE showdown both quarterbacks came out
of the projection at depth_rank 1, role_band ALPHA, claiming over 96 per cent of their club's pass
attempts from their own measured usage -- and carrying
`appearance_adjustment.reason = NOT_PREDICTED_STARTER` with a rank-2 appearance rate of 0.13789.
Deshaun Watson lost 5.14 DK points to it and Aaron Rodgers 2.46.

The chain was three links, each individually reasonable:

  showdown_slate_state  hard-coded `predicted_lineup_context: {}` -- no ingestion path existed
  role_state.assign     pred = bool({}.get('in_predicted_starting_group'))  ->  False
  proj_v1               `if pos == 'QB' and is_predicted_starter is False` -> charge rank 2

bool(None) is False, so ABSENCE OF A FEED became positive evidence of backup status. That is the
project's oldest defect class wearing new clothes: a step that returned nothing was read as an
answer. UNKNOWN is not NO.

Each check forces a direction rather than asserting today's artifact happens to be clean: the
penalty must apply to a player with positive backup evidence, must NOT apply to a rank-1 starter,
and must NOT apply when nothing is known either way.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_slate_state as S  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


# --------------------------------------------------------------------------- starter ingestion

@check('confirmed starter evidence reaches the state as in_predicted_starting_group True')
def _starter_ingested():
    c = S._starter_context('Deshaun Watson', 'CLE', {'Deshaun Watson': 'CLE'})
    assert c.get('in_predicted_starting_group') is True, c
    assert c.get('state') == S.STARTER_TIER, c
    return f"state={c['state']}, in_predicted_starting_group={c['in_predicted_starting_group']}"


@check('a bare list of names is accepted and attributed to the slate club')
def _starter_list_form():
    c = S._starter_context('Aaron Rodgers', 'PIT', ['Aaron Rodgers'])
    assert c.get('in_predicted_starting_group') is True, c
    return f"list form -> {c['state']}"


@check('WRONG-CLUB starter evidence FAILS CLOSED and is not applied')
def _starter_wrong_club():
    c = S._starter_context('Deshaun Watson', 'CLE', {'Deshaun Watson': 'PIT'})
    assert c.get('state') == 'STARTER_EVIDENCE_REJECTED_CLUB_MISMATCH', c
    assert c.get('in_predicted_starting_group') is False, c
    return f"rejected: relayed {c['relayed_club']} vs slate {c['slate_club']}"


@check('MISSING starter evidence stays missing -- it is not inferred either way')
def _starter_missing():
    assert S._starter_context('Somebody Else', 'CLE', {'Deshaun Watson': 'CLE'}) == {}
    assert S._starter_context('Deshaun Watson', 'CLE', None) == {}
    assert S._starter_context('Deshaun Watson', 'CLE', {}) == {}
    return 'absent from the list, and no list at all, both give {} (UNKNOWN, not NO)'


# --------------------------------------------------------------- the QB appearance gate itself

_DEPTH = {'QB': {'by_rank': {
    'rank_1': {'appearance_rate': 0.98, 'unconditional_expected_share': 0.96,
               'conditional_mean_share': 0.98},
    'rank_2': {'appearance_rate': 0.13789, 'unconditional_expected_share': 0.01939,
               'conditional_mean_share': 0.14069},
    'rank_3': {'appearance_rate': 0.02, 'unconditional_expected_share': 0.002,
               'conditional_mean_share': 0.1},
}}}


def _gate(depth_rank, is_predicted_starter, feed_covers_club, depth=None):
    """Run ONLY the appearance gate, with the surrounding projection stubbed out.

    The gate is a block inside project_player, so it is exercised through a minimal stand-in that
    reproduces its inputs exactly: the same claims dict shape, the same depth table, the same three
    flags. Reproducing the branch rather than importing it would test a copy, so the real source is
    executed by slicing it out of the module and running it.
    """
    import ast
    import textwrap
    src = (_REPO / 'nfl/tools/proj_v1.py').read_text()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == 'project_player')
    block = next(n for n in fn.body
                 if isinstance(n, ast.If) and 'QB' in ast.dump(n.test))
    code = ast.get_source_segment(src, block)
    assert code, 'appearance gate block not found in project_player'
    # The block declares `nonlocal rzc_share`, which needs an enclosing function to bind to, so the
    # real source is wrapped in one that supplies exactly the names project_player has in scope.
    wrapper = ('def _gate_under_test(pos, depth, depth_rank, is_predicted_starter,\n'
               '                     predicted_feed_covers_club, claims, rzc_share, out):\n'
               + textwrap.indent(textwrap.dedent(code), '    ')
               + '\n    return out, claims, rzc_share\n')
    env = {}
    exec(compile(wrapper, '<gate>', 'exec'), env)  # noqa: S102
    out, claims, _ = env['_gate_under_test'](
        'QB', depth if depth is not None else _DEPTH, depth_rank, is_predicted_starter,
        feed_covers_club, {'pass_attempts': 0.99, 'carries': 0.05}, 0.02, {})
    return out.get('appearance_adjustment') or {}, claims


@check('a DEPTH_RANK_1 quarterback is NEVER charged an appearance penalty')
def _rank1_never_penalised():
    for feed in (True, False):
        for ips in (True, False):
            aa, claims = _gate(1, ips, feed)
            assert aa.get('applied') is False, (feed, ips, aa)
            assert aa.get('reason') == 'DEPTH_RANK_1_IS_THE_STARTER', aa
            assert claims['pass_attempts'] == 0.99, claims
    return ('rank 1 keeps his full 0.99 pass-attempt claim under all four '
            'combinations of is_predicted_starter and feed coverage')


@check('a confirmed starter cannot emerge as NOT_PREDICTED_STARTER')
def _confirmed_starter_not_penalised():
    # Confirmed starter, and suppose his depth rank were never captured at all.
    aa, claims = _gate(None, True, True)
    assert aa.get('applied') is False, aa
    assert 'NOT_PREDICTED_STARTER' not in str(aa.get('reason')), aa
    assert claims['pass_attempts'] == 0.99, claims
    return f"reason={aa.get('reason')}, claim untouched at {claims['pass_attempts']}"


@check('MISSING evidence does not trigger the penalty -- the 2026 W4 regression')
def _missing_evidence_no_penalty():
    # Exactly tonight's state before the repair: no rank, no feed, flag False from bool(None).
    aa, claims = _gate(None, False, False)
    assert aa.get('applied') is False, aa
    assert aa.get('reason') == 'NO_EVIDENCE_OF_BACKUP_STATUS', aa
    assert claims['pass_attempts'] == 0.99, claims
    assert 'UNMODELLED_RISK' in aa, aa
    return 'no rank + no feed -> not applied, and the unguarded volume is declared'


@check('a DEPTH_RANK_2 quarterback IS charged, so the Fields protection still holds')
def _rank2_still_penalised():
    aa, claims = _gate(2, False, False)
    assert aa.get('applied') is True, aa
    assert aa.get('reason') == 'DEPTH_RANK_2', aa
    assert claims['pass_attempts'] == 0.01939, claims
    assert abs(claims['carries'] - 0.05 * 0.13789) < 1e-12, claims
    return f"rank 2 capped to {claims['pass_attempts']} and carries scaled by appearance rate"


@check('the penalty is indexed by the player OWN rank, not always rank 2')
def _indexed_by_own_rank():
    aa, claims = _gate(3, False, False)
    assert aa.get('rank_curve_used') == 'rank_3', aa
    assert claims['pass_attempts'] == 0.002, claims
    a2, _ = _gate(2, False, False)
    assert a2.get('rank_curve_used') == 'rank_2', a2
    return 'rank 3 uses rank_3 (0.002), rank 2 uses rank_2 (0.01939)'


@check('a feed that covered his club and omitted him IS positive backup evidence')
def _feed_omission_is_evidence():
    aa, _ = _gate(None, False, True)
    assert aa.get('applied') is True, aa
    assert aa.get('reason') == 'NOT_IN_PREDICTED_LINEUP_FEED_THAT_COVERED_HIS_CLUB', aa
    return aa['reason']


@check('an absent rank curve is recorded, never silently skipped')
def _absent_curve_recorded():
    import copy
    d = copy.deepcopy(_DEPTH)
    del d['QB']['by_rank']['rank_2']
    del d['QB']['by_rank']['rank_3']
    aa, claims = _gate(2, False, False, depth=d)
    assert aa.get('applied') is False, aa
    assert aa.get('reason') == 'DEPTH_RANK_CURVE_ABSENT', aa
    assert claims['pass_attempts'] == 0.99, claims
    return f"recorded {aa['reason']} with ranks_available={aa.get('ranks_available')}"


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
