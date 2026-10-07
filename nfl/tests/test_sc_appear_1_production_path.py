"""SC-APPEAR-1 through the production allocator: the hook, its identity when off, leakage and refusals.

What is guarded here, and why each one matters:

  * HOOK OFF == PRODUCTION. The research path calls proj_v1.allocate_opportunity once per field with a copied depth
    table. With the candidate off that copy equals production, and every allocated volume, P(plays) and allocation
    record must equal one ordinary production call exactly -- unconditional and conditional (build()'s second pass).
  * NO 2025 IN THE FIT. Truncating the panel at 2024 must leave the depth table, group split, SC-APPEAR-1 rates and
    season priors identical; perturbing week >= W data must leave week-W predictions identical; a fit season that is
    not held out is refused.
  * NON-QUALIFYING PLAYERS UNCHANGED. Their P(plays) is the production depth rate, bit for bit.
  * EMPTY INPUT REFUSED with a named error, never an empty success.
  * PRODUCTION IS NOT TOUCHED: no attribute assignment on production modules, depth table and constants unmutated.

Run standalone:  python3.12 nfl/tests/test_sc_appear_1_production_path.py
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_MOD = _REPO / 'nfl/research/appearance/sc_appear_1_production_path.py'
_spec = importlib.util.spec_from_file_location('sc_appear_1_production_path', _MOD)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
V, FC = M.V, M.FC

PASSED = FAILED = 0
_CACHE = {}
WEEK = 7
CLUBS = ['BUF', 'DET', 'KC', 'NO', 'PHI', 'SF']


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')
    return bool(ok)


def _setup():
    if _CACHE:
        return _CACHE
    po = M.PP.load_panel()
    panel, pos_of = po.value, M.PP.position_index()
    d24, d25 = M.F1._dressed(2024), M.F1._dressed(2025)
    fitted = M.fit(panel, pos_of, d24)
    ctx = M.context(panel, pos_of, 2025, d25, snap_pos=M._snap_positions(2025))
    _CACHE.update(panel=panel, pos_of=pos_of, d24=d24, d25=d25, fitted=fitted, ctx=ctx)
    return _CACHE


def _club(ctx, fitted, club, week):
    pool = M.pool_for(ctx, club, week, 'DRESSED')
    tv, rows = M.club_rows(ctx, club, week, pool, M.starter_proxy(ctx, week), fitted['depth'])
    return tv, rows


def _refused(fn, code):
    try:
        fn()
    except M.SCAppearProductionPathError as e:
        return e.code == code
    return False


# ----------------------------------------------------------------------------------- hook off == production
def test_hook_off_equals_production_unconditional():
    S = _setup()
    n = 0
    for club in CLUBS:
        tv, rows = _club(S['ctx'], S['fitted'], club, WEEK)
        if not rows:
            continue
        a, b = copy.deepcopy(rows), copy.deepcopy(rows)
        V.allocate_opportunity(a, tv, S['fitted']['depth'], S['fitted']['groups'])
        M.allocate_with_hook(b, tv, S['fitted']['depth'], S['fitted']['groups'], rate_fn=None)
        same = M._snapshot(a) == M._snapshot(b)
        check(same, f'{club} wk{WEEK}: hook off reproduces the production allocation exactly ({len(rows)} players)')
        n += same
    check(n >= 4, f'identity exercised on {n} club-weeks')


def test_hook_off_equals_production_conditional():
    S = _setup()
    tv, rows = _club(S['ctx'], S['fitted'], 'KC', WEEK)
    a = M.conditional_pass(rows, tv, S['fitted']['depth'], S['fitted']['groups'])
    b = M.conditional_pass(rows, tv, S['fitted']['depth'], S['fitted']['groups'], rate_fn=None, hooked=True)
    check(a == b and len(a) == len(rows), f'conditional volumes (build second pass) identical with hook off ({len(a)} targets)')


def test_hook_on_reaches_the_line_879_read():
    S = _setup()
    tv, rows = _club(S['ctx'], S['fitted'], 'KC', WEEK)
    target = next(r for r in rows if r['position'] == 'WR')
    fn = lambda r, f: (0.123456 if (r['_dk'] == target['_dk'] and f == 'targets') else None)  # noqa: E731
    base, hooked = copy.deepcopy(rows), copy.deepcopy(rows)
    V.allocate_opportunity(base, tv, S['fitted']['depth'], S['fitted']['groups'])
    M.allocate_with_hook(hooked, tv, S['fitted']['depth'], S['fitted']['groups'], rate_fn=fn)
    t = next(r for r in hooked if r['_dk'] == target['_dk'])
    check(t['p_plays']['targets'] == 0.123456 and t['allocation']['targets']['appearance_rate_measured'] == 0.123456,
          'the injected rate is what the production allocator recorded as appearance_rate_measured')
    others = all(h['p_plays'][f] == b['p_plays'][f] for h, b in zip(hooked, base) for f in ('targets', 'carries', 'pass_attempts')
                 if not (h['_dk'] == target['_dk'] and f == 'targets'))
    check(others, 'every other player-field P(plays) is untouched')
    tot = sum(r['targets'] for r in hooked)
    check(abs(tot - tv['proj_targets']) < 1e-9, f'club targets still conserved under the hook ({tot:.6f})')


# ------------------------------------------------------------------------------------------- leakage guard
def _truncate(panel, last):
    return {'players': {g: {s: w for s, w in ss.items() if int(s) <= last} for g, ss in panel['players'].items()},
            'teams': {c: {s: w for s, w in ss.items() if int(s) <= last} for c, ss in panel['teams'].items()}}


def test_no_2025_data_in_the_fit():
    S = _setup()
    tr = _truncate(S['panel'], 2024)
    f2 = M.fit(tr, S['pos_of'], S['d24'])
    for k in ('depth', 'groups', 'rates', 'n_fit_rows'):
        check(f2[k] == S['fitted'][k],
              f'fit[{k}] identical with every 2025+ row removed from the panel')
    sample = sorted(g for g in S['ctx']['priors'])[::25][:40]
    p_full = FC.season_priors(S['panel'], S['ctx']['posmap'], 2025, sample)
    p_trunc = FC.season_priors(tr, S['ctx']['posmap'], 2025, sample)
    check(json.dumps(p_full, sort_keys=True, default=str) == json.dumps(p_trunc, sort_keys=True, default=str),
          f'season priors for {len(sample)} players identical with 2025+ removed')
    check(_refused(lambda: M.fit(S['panel'], S['pos_of'], S['d24'], through=2025), 'FIT_SEASON_NOT_HELD_OUT'),
          'a fit through 2025 is refused FIT_SEASON_NOT_HELD_OUT')


def test_week_w_predictions_ignore_week_w_and_later():
    S = _setup()
    ctx = S['ctx']
    pert = copy.deepcopy({'players': ctx['panel']['players'], 'teams': ctx['panel']['teams']})
    for g, ss in pert['players'].items():
        for w, d in (ss.get('2025') or {}).items():
            if int(w) >= WEEK:
                for f in ('targets', 'carries', 'pass_attempts'):
                    d[f] = (d.get(f) or 0) + 5
    for c, ss in pert['teams'].items():
        for w, d in (ss.get('2025') or {}).items():
            if int(w) >= WEEK:
                for f in ('targets', 'rush_attempts', 'pass_attempts', 'plays'):
                    d[f] = (d.get(f) or 0) * 3 + 7
    ctx2 = dict(ctx, panel=pert)
    a, _, _ = M.replay(ctx, S['fitted'], weeks=[WEEK], clubs=CLUBS)
    b, _, _ = M.replay(ctx2, S['fitted'], weeks=[WEEK], clubs=CLUBS)
    cols = ['gsis', 'field', 'rank_table', 'qualifies', 'prior3_count', 'p_cur', 'p_cand', 'e_cur', 'e_cand', 'c_cur', 'c_cand']
    check(a[cols].equals(b[cols]), f'week-{WEEK} predictions identical after perturbing weeks >= {WEEK} ({len(a)} units)')
    check(not a.actual.equals(b.actual), '  while the perturbation did reach the realised outcomes (the test can fail)')


# ------------------------------------------------------------------------------- non-qualifying unchanged
def test_non_qualifying_players_unchanged():
    S = _setup()
    df, cons, ident = M.replay(S['ctx'], S['fitted'], weeks=[WEEK, WEEK + 1])
    nq, q = df[~df.qualifies], df[df.qualifies]
    check(len(nq) > 100 and bool((nq.p_cand == nq.p_cur).all()),
          f'P(plays) exactly unchanged for all {len(nq)} non-qualifying units')
    rates = S['fitted']['rates']
    check(len(q) > 100 and all(r.p_cand == rates[(r.pos, r.field)] for r in q.itertuples()),
          f'every one of {len(q)} qualifying units carries the 2024 SC-APPEAR-1 rate for its field')
    check(set(q.pos) <= {'RB', 'WR', 'TE'}, 'no quarterback ever qualifies')
    qb = df[df.pos == 'QB']
    check(bool((qb.e_cur == qb.e_cand).all()), 'QB pass attempts identical in both arms')
    check(float((cons.sum_candidate - cons.club_total).abs().max()) < 1e-9
          and float((cons.sum_current - cons.club_total).abs().max()) < 1e-9,
          f'club totals conserved in both arms over {len(cons)} club-week-fields')
    check(ident['club_weeks'] > 0, f'hook-off identity checked on {ident["club_weeks"]} club-weeks inside replay')


# ------------------------------------------------------------------------------------------------ refusals
def test_empty_input_refused_with_named_error():
    S = _setup()
    check(_refused(lambda: M.fit({}, S['pos_of'], S['d24']), 'EMPTY_PANEL'), 'empty panel refused EMPTY_PANEL')
    check(_refused(lambda: M.fit({'players': {}, 'teams': {}}, S['pos_of'], S['d24']), 'EMPTY_PANEL'),
          'panel with no players refused EMPTY_PANEL')
    check(_refused(lambda: M.fit(S['panel'], S['pos_of'], {}), 'EMPTY_DRESSED_FIT'), 'empty fit dressed set refused')
    check(_refused(lambda: M.context(S['panel'], S['pos_of'], 2025, {}), 'EMPTY_DRESSED_TEST'),
          'empty held-out dressed set refused EMPTY_DRESSED_TEST')
    check(_refused(lambda: M.replay(S['ctx'], S['fitted'], weeks=[1, 2, 3]), 'NO_SCORED_UNITS'),
          'a replay that scores nothing is refused NO_SCORED_UNITS, not returned empty')
    check(_refused(lambda: M.pool_for(S['ctx'], 'KC', WEEK, 'BOGUS'), 'UNKNOWN_UNIVERSE'), 'unknown universe refused')


# ----------------------------------------------------------------------------------- production untouched
def test_production_not_mutated():
    S = _setup()
    names = ('DEPTH_CLAIM_BLEND', 'PRIOR_WEIGHT_CAP', 'CHART_RANK_ORDER', 'LEGACY_CROSS_FIELD_PRIOR',
             'CROSS_FIELD_PRIOR_SCOPE', 'MARKET_ARM', 'DEPTH_TABLE_FIELD')
    before = {n: copy.deepcopy(getattr(V, n)) for n in names}
    depth_before = json.dumps(S['fitted']['depth'], sort_keys=True)
    M.replay(S['ctx'], S['fitted'], weeks=[WEEK], clubs=CLUBS[:2])
    check(all(getattr(V, n) == before[n] for n in names), 'proj_v1 module constants unchanged by a hooked replay')
    check(json.dumps(S['fitted']['depth'], sort_keys=True) == depth_before, 'production depth table not mutated')
    tree = ast.parse(_MOD.read_text())
    bad = []
    for node in ast.walk(tree):
        tg = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AugAssign) else [])
        for t in tg:
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in ('V', 'FC', 'PP', 'F1'):
                bad.append(f'{t.value.id}.{t.attr}')
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'setattr':
            bad.append('setattr')
    check(not bad, f'research module assigns no attribute on a production module {bad}')


def test_artifact_is_shadow_and_recommendation_only():
    p = M.OUT
    if not check(p.exists(), f'{p.name} written'):
        return
    d = json.loads(p.read_text())
    check(d.get('STATUS') == 'SHADOW_ONLY', 'STATUS SHADOW_ONLY')
    check(str(d['PROMOTION_RECOMMENDATION']['STATUS']).startswith('RECOMMENDATION_ONLY'), 'recommendation only, nothing promoted')
    check(d['production_path']['production_file_edited'] is False, 'production file recorded unedited')
    check(d['production_path']['sha256_before'] == M._sha(M.PROJ_V1_FILE),
          'proj_v1.py on disk still hashes to the replayed version')
    txt = p.read_text().replace('PROSPECTIVELY_VALIDATED', '')
    hits = re.findall(r'\b(validated|unbiased|correct)\b', txt, flags=re.I)
    check(not hits, f'no unmargined adequacy words in the artifact {hits}')


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            print(name)
            fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
