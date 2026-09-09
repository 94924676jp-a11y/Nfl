"""OWN-10: the metric contract, made load-bearing.

The defect OWN-10 withdraws is not a wrong number, it is a wrong STATISTIC: a
per-team-game predictive MEAN correlated against a realised series. This suite
refuses to let that comparison come back, and refuses to let A2 be promoted on
the strength of a premise the measurement removed.

Every check here is structural or arithmetic. None of it needs the play-by-play
corpus, so none of it is skipped when the corpus is absent.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OWN9 = os.path.join(ROOT, 'nfl', 'research', 'own9')
OWN10 = os.path.join(ROOT, 'nfl', 'research', 'own10')
for _q in (ROOT, OWN9, OWN10):
    if _q not in sys.path:
        sys.path.insert(0, _q)

PREDECL_SHA = '59ea7fa4363b202899e76f7668d2d3f8e517e2c572e4afd040079dbb14de5954'


def test_predeclaration_is_committed_and_unmodified():
    p = os.path.join(OWN10, 'predeclaration_own10.md')
    assert os.path.exists(p), 'OWN10_PREDECLARATION_MISSING'
    got = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    assert got == PREDECL_SHA, f'OWN10_PREDECLARATION_MODIFIED: {got}'


def test_runner_pins_the_same_hash():
    src = open(os.path.join(OWN10, 'run_own10.py')).read()
    assert PREDECL_SHA in src, 'OWN10_RUNNER_DOES_NOT_PIN_PREDECLARATION'


def _assigned_calls(path, target_name):
    """Every call whose result is appended to a list named `target_name`."""
    tree = ast.parse(open(path).read())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == 'append'):
            continue
        # co[arm]['designed_qb'].append(...)  ->  the subscript key
        v = f.value
        if isinstance(v, ast.Subscript) and isinstance(v.slice, ast.Constant) \
                and v.slice.value == target_name:
            found.extend(node.args)
    return found


def test_own9_no_longer_correlates_predictive_means_against_reality():
    """The exact defect: np.mean(draws) appended to the co-movement series.

    An AST walk, not a substring search -- a substring guard on this file would
    match the comment that EXPLAINS the defect, which is how an earlier guard
    in this project failed.
    """
    path = os.path.join(OWN9, 'run_own9.py')
    src = open(path).read()
    tree = ast.parse(src)
    # the corrected runner must expose a per-draw correlation helper
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert 'per_draw_corr' in names, 'OWN9_PER_DRAW_CORR_ABSENT'

    # and every co_movement key that is compared against a realised series must
    # either be per-draw or be NAMED as not comparable
    res = json.load(open(os.path.join(OWN9, 'own9_results.json')))
    for arm, d in res['co_movement'].items():
        for k, v in d.items():
            if 'MEAN_BASED' in k or 'NOT_COMPARABLE' in k:
                continue
            assert isinstance(v, dict) and 'per_draw_mean' in v, (
                f'OWN9_CO_MOVEMENT_NOT_PER_DRAW: {arm}.{k} = {v!r}. A statistic '
                f'compared against a realised series must be computed one draw '
                f'per team-game, or be named as not comparable.')


def test_the_guard_fails_when_bypassed():
    """A guard that cannot fail is not a guard. Seed the defect and require it."""
    fake = {'co_movement': {'A1': {'designed_qb_vs_team_carries': 0.5070}}}
    caught = False
    try:
        for arm, d in fake['co_movement'].items():
            for k, v in d.items():
                if 'MEAN_BASED' in k or 'NOT_COMPARABLE' in k:
                    continue
                assert isinstance(v, dict) and 'per_draw_mean' in v
    except AssertionError:
        caught = True
    assert caught, 'OWN10_METRIC_GUARD_IS_INERT'


def test_a2_tau_zero_is_exactly_a1_on_a_synthetic_row():
    """tau = 0 must reproduce A1 draw for draw, or the grid does not contain
    its own null and every comparison against A1 is confounded."""
    import a1_lib as A
    import a2_lib as A2

    row = {'rush_play_budget': 30, 'h_n': 3,
           'h_kneel': [0.03, 0.02, 0.04], 'h_designed_qb': [0.08, 0.06, 0.10],
           'h_rb': [0.80, 0.82, 0.78], 'h_wr': [0.05, 0.06, 0.04],
           'h_te': [0.01, 0.01, 0.02], 'h_fringe': [0.03, 0.03, 0.02]}
    rs = np.random.default_rng(11)
    par = {'league': {c: 1.0 / len(A.CATEGORIES) for c in A.CATEGORIES},
           'resid': {c: rs.normal(0, 0.03, 500).astype(np.float32)
                     for c in A.CATEGORIES}}
    d1, deg1 = A.draw_a1(row, par, np.random.default_rng(7), 256)
    d2, deg2, floor = A2.draw_a2(row, par, np.random.default_rng(7), 256, 0.0)
    assert deg1 == deg2
    for c in A.CATEGORIES:
        assert np.array_equal(d1[c], d2[c]), f'A2_TAU_ZERO_NOT_A1: {c}'
    assert floor >= 0


def test_a2_latent_cannot_break_closure():
    """The latent moves a probability, never a carry. Every draw must still
    partition the same integer budget exactly, at every tau in the grid."""
    import a1_lib as A
    import a2_lib as A2

    row = {'rush_play_budget': 27, 'h_n': 2,
           **{f'h_{c}': [0.1, 0.2] for c in A.CATEGORIES}}
    rs = np.random.default_rng(3)
    par = {'league': {c: 1.0 / len(A.CATEGORIES) for c in A.CATEGORIES},
           'resid': {c: rs.normal(0, 0.05, 400).astype(np.float32)
                     for c in A.CATEGORIES}}
    for tau in A2.TAU_GRID:
        d, deg, floor = A2.draw_a2(row, par, np.random.default_rng(5), 512, tau)
        tot = sum(np.asarray(d[c], np.int64) for c in A.CATEGORIES)
        assert np.all(tot == row['rush_play_budget']), (
            f'A2_CLOSURE_VIOLATION at tau={tau}')
        for c in A.CATEGORIES:
            assert np.all(np.asarray(d[c]) >= 0), f'A2_NEGATIVE at tau={tau}'
            assert np.all(np.asarray(d[c]) <= row['rush_play_budget']), (
                f'A2_CATEGORY_OVERRUN at tau={tau}')


def test_tau_grid_is_the_predeclared_one_and_contains_zero():
    import a2_lib as A2
    assert A2.TAU_GRID[0] == 0.0, 'A2_GRID_MISSING_ITS_NULL'
    assert list(A2.TAU_GRID) == [0.0, 0.0025, 0.005, 0.01, 0.02, 0.04], (
        'A2_GRID_CHANGED_AFTER_PREDECLARATION')
    txt = open(os.path.join(OWN10, 'predeclaration_own10.md')).read()
    for t in A2.TAU_GRID:
        assert f'{t:g}' in txt, f'A2_TAU_{t}_NOT_PREDECLARED'


def test_results_record_the_rejection_and_promote_nothing():
    p = os.path.join(OWN10, 'own10_results.json')
    if not os.path.exists(p):
        return  # the run needs the corpus; the contract tests above do not
    d = json.load(open(p))
    assert d['promoted'] is False, 'OWN10_PROMOTED'
    assert d['research_only'] is True
    assert d['production_files_changed'] == 0, 'OWN10_TOUCHED_PRODUCTION'
    assert d['consumed_2026_outcomes'] is False, 'OWN10_CONSUMED_2026'
    assert d['predeclaration_sha256'] == PREDECL_SHA
    for k, arm in d['arms'].items():
        g = arm['gates']
        assert g['closure_violations'] == 0, f'OWN10_CLOSURE_VIOLATION in {k}'
        assert g['negative'] == 0, f'OWN10_NEGATIVE in {k}'
        assert g['category_budget_overruns'] == 0, f'OWN10_OVERRUN in {k}'


WITHDRAWN_CONTEXT = ('not comparable', 'mean-based', 'artifact', 'ruling',
                     'withdraw', 'inflated', 'never the same statistic')


def _blocks(txt):
    """Paragraphs, because the qualification lives near the number, not on the
    same line as it. A line-scoped version of this check fired on the ruling's
    own blockquote, which is qualified by the sentence directly beneath it."""
    out, cur = [], []
    for line in txt.splitlines():
        if line.strip():
            cur.append(line)
        elif cur:
            out.append('\n'.join(cur))
            cur = []
    if cur:
        out.append('\n'.join(cur))
    return out


def test_the_withdrawn_premise_is_not_quotable_as_a_measurement():
    """+0.507 may appear only where its paragraph says what it is. A future
    reader must not be able to lift it as a measurement of A1's coupling."""
    for name in ('predeclaration_own10.md',):
        txt = open(os.path.join(OWN10, name)).read()
        for i, blk in enumerate(_blocks(txt)):
            if '0.5070' not in blk and '+0.507' not in blk:
                continue
            low = blk.lower()
            # a blockquote is qualified by the paragraph that answers it
            nxt = _blocks(txt)[i + 1].lower() if i + 1 < len(_blocks(txt)) else ''
            assert any(w in low or w in nxt for w in WITHDRAWN_CONTEXT), (
                f'OWN10_WITHDRAWN_NUMBER_QUOTED_BARE: {blk!r}')


def test_the_withdrawn_number_guard_fails_when_bypassed():
    """Seed a bare quotation and require rejection."""
    bad = 'A1 couples at +0.507 against an observed +0.314.\n\nNext paragraph.'
    caught = False
    for i, blk in enumerate(_blocks(bad)):
        if '+0.507' not in blk:
            continue
        low = blk.lower()
        nxt = _blocks(bad)[i + 1].lower() if i + 1 < len(_blocks(bad)) else ''
        if not any(w in low or w in nxt for w in WITHDRAWN_CONTEXT):
            caught = True
    assert caught, 'OWN10_WITHDRAWN_NUMBER_GUARD_IS_INERT'
