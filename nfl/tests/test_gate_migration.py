"""The gate decides publishability; it does not create football truth.

`review/gate_reference.py` is the frozen gate at 7dadfee. The comparison that
matters here is run TWICE, because two different questions are being asked:

  GATE-ONLY   the same (migrated) audit into both gates. Isolates this
              slice. Any difference at all is a regression.
  END-TO-END  frozen audit into frozen gate, versus migrated into migrated.
              Differences are permitted only where they follow from the
              already-approved INJURY_OUT semantics, and every one is
              enumerated.
"""
from __future__ import annotations

import ast
import collections
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(_REPO), str(_REPO / 'nfl' / 'tests')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nfl.production.review import audit as A                          # noqa: E402
from nfl.production.review import audit_reference as AR               # noqa: E402
from nfl.production.review import dossier as D                        # noqa: E402
from nfl.production.review import escalation as ESC                   # noqa: E402
from nfl.production.review import gate as G                           # noqa: E402
from nfl.production.review import gate_reference as GR                # noqa: E402
from nfl.production.review import slate_report as SR                  # noqa: E402
from nfl.production.state import availability as AV                   # noqa: E402

import test_audit_migration as AM                                     # noqa: E402
import test_dossier_migration as T                                    # noqa: E402

PASSED = FAILED = 0
SLATE, CUT = '2026_02_CAR_ATL', '2026-09-22T23:00:00Z'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def report_for(auditmod, kw, ds, publishable=True):
    pub = set(kw['projection']['per_player']) if publishable else None
    a = auditmod.audit(ds, publishable_ids=pub)
    res = a.value or a.evidence['value']
    e = ESC.escalate(ds, res, deep_research_capacity=12).value
    rep = SR.build_report(slate_key=SLATE, dossiers=ds, audit_result=res,
                          escalation_result=e,
                          projection_source={'digests': {}},
                          publishable_ids=pub, information_cut=CUT)
    return rep, (pub or set())


def rowkey(r):
    return (r.get('gsis_id'), r.get('code'))


def index(v):
    return {rowkey(r): r for r in v['conflicts']}


def diff_rows(va, vb):
    ia, ib = index(va), index(vb)
    d = collections.Counter()
    for k in set(ia) & set(ib):
        for f in ('disposition', 'category', 'immaterial_blocking_code',
                  'detail', 'severity'):
            if ia[k].get(f) != ib[k].get(f):
                d[f] += 1
        for f in ('material', 'exempt', 'measured', 'fired',
                  'evidence_grade_scale', 'cold_start_dominated', 'why'):
            if ia[k]['materiality'].get(f) != ib[k]['materiality'].get(f):
                d[f'materiality.{f}'] += 1
    return ia, ib, sorted(set(ib) - set(ia)), sorted(set(ia) - set(ib)), d


def per_player(v):
    """Verdict-shaped view per player: what blocks him, what warns him."""
    out = collections.defaultdict(lambda: {'blocking': set(), 'warning': set(),
                                           'material': set()})
    for r in v['conflicts']:
        pid = r.get('gsis_id')
        if r['disposition'] == 'BLOCKING':
            out[pid]['blocking'].add(r['code'])
        else:
            out[pid]['warning'].add(r['code'])
        if r['materiality'].get('material'):
            out[pid]['material'].add(r['code'])
    return {k: {kk: sorted(vv) for kk, vv in val.items()}
            for k, val in out.items()}


# -- 1. the isolation proof -------------------------------------------------
def test_the_gate_change_alone_changes_nothing():
    """Same conflicts into both gates. This is the whole slice, measured."""
    for name, kw in (('migration fixture', T.fixture()),
                     ('room fixture', AM.room_fixture()),
                     ('room fixture stale', AM.room_fixture(stale=True))):
        ds = D.build_dossiers(**kw).value['dossiers']
        rep, pub = report_for(A, kw, ds)
        a = GR.evaluate(rep, dossiers=ds, optimizer_pool_ids=pub)
        b = G.evaluate(rep, dossiers=ds, optimizer_pool_ids=pub)
        va, vb = GR.payload(a), G.payload(b)
        ok(va['verdict'] == vb['verdict'],
           f'{name}: same verdict {vb["verdict"]}')
        ok(a.code == b.code, f'{name}: same outcome code {b.code}')
        ia, ib, added, dropped, d = diff_rows(va, vb)
        # ONE DECLARED DIFFERENCE. The frozen gate weighs the team share
        # with `carry_share or target_share`; the live one takes the larger
        # of the two. The VALUE moves on a row that owns both; no DECISION
        # does, which is the claim that matters and is asserted next.
        decisions = {k: n for k, n in d.items()
                     if k not in ('materiality.measured',)}
        ok(not added and not dropped and not decisions,
           f'{name}: {len(ia)} conflict rows, identical in disposition, '
           f'category, materiality DECISION and detail -- added '
           f'{len(added)}, dropped {len(dropped)}, field diffs '
           f'{dict(decisions) or "none"}')
        if d.get('materiality.measured'):
            print(f'      (team share VALUE moved on '
                  f'{d["materiality.measured"]} row(s) under the corrected '
                  f'share rule; no materiality decision moved)')
        ok(per_player(va) == per_player(vb),
           f'{name}: per-player blocking/warning/material sets identical '
           f'across {len(per_player(vb))} player(s)')
        for f in ('blocking_by_category', 'warning_by_category',
                  'blocking_players', 'warning_players',
                  'immaterial_blocking_codes_held_as_warnings',
                  'blocking_conflict_count', 'warning_count'):
            ok(va[f] == vb[f], f'{name}: {f} identical')


# -- 2. end to end, with the audit correction flowing through ---------------
def test_end_to_end_changes_are_only_the_out_correction():
    kw = T.fixture()
    ds = D.build_dossiers(**kw).value['dossiers']
    rep_old, pub = report_for(AR, kw, ds)
    rep_new, _ = report_for(A, kw, ds)
    a = GR.evaluate(rep_old, dossiers=ds, optimizer_pool_ids=pub)
    b = G.evaluate(rep_new, dossiers=ds, optimizer_pool_ids=pub)
    va, vb = GR.payload(a), G.payload(b)
    ok(va['verdict'] == vb['verdict'] == G.BLOCKED,
       f'the slate verdict is unchanged: {va["verdict"]} -> {vb["verdict"]}')
    ia, ib, added, dropped, d = diff_rows(va, vb)
    ok(not dropped, f'no conflict row disappeared: {dropped}')
    ok(all(k[1] == A.C_INACTIVE_OWNS_OPPORTUNITY for k in added),
       f'every added row is the widened availability code: '
       f'{sorted({k[1] for k in added})}')
    for pid, code in added:
        r = ib[(pid, code)]
        ok(r['disposition'] == 'BLOCKING'
           and r['category'] == 'availability_integrity',
           f'ADDED {r.get("display_name")}: {code} blocks under '
           f'{r["category"]}, availability {r["evidence"].get("availability")}')
    ok(set(d) <= {'detail', 'materiality.measured'},
       f'the only fields that moved on a shared row are the audit\'s detail '
       f'wording and the team-share VALUE under the corrected share rule: '
       f'{dict(d)}')
    ok('materiality.material' not in d and 'disposition' not in d,
       'and no materiality decision or disposition moved with them')
    old_pp, new_pp = per_player(va), per_player(vb)
    changed = [p for p in set(old_pp) | set(new_pp)
               if old_pp.get(p) != new_pp.get(p)]
    ok(len(changed) == 2,
       f'exactly {len(changed)} players have a different per-player verdict')
    for p in sorted(changed):
        ok(set(new_pp[p]['blocking']) - set(old_pp.get(p, {}).get(
            'blocking', [])) == {A.C_INACTIVE_OWNS_OPPORTUNITY},
           f'{p}: gains only {A.C_INACTIVE_OWNS_OPPORTUNITY}')
    ok(va['blocking_players'] == vb['blocking_players'],
       f'and the blocking-player list is unchanged at '
       f'{len(vb["blocking_players"])} -- both were already blocked for '
       f'other reasons')


def test_a_passing_and_a_warning_slate_are_unchanged():
    """A BLOCKED slate is the easy case. These are the ones where a
    materiality change would show up as a verdict flip."""
    kw = AM.room_fixture()
    ds = D.build_dossiers(**kw).value['dossiers']
    # drop the inversion so only the routes NOTE survives -> WARNINGS
    kw2 = AM.room_fixture()
    kw2['projection']['per_player']['RB4']['carries']['mean'] = 1.0
    ds2 = D.build_dossiers(**kw2).value['dossiers']
    for label, dset, kwx, want in (('blocking room', ds, kw, G.BLOCKED),
                                   ('warning only', ds2, kw2,
                                    G.PASS_WITH_WARNINGS)):
        rep, pub = report_for(A, kwx, dset)
        a = GR.evaluate(rep, dossiers=dset, optimizer_pool_ids=pub)
        b = G.evaluate(rep, dossiers=dset, optimizer_pool_ids=pub)
        va, vb = GR.payload(a), G.payload(b)
        ok(va['verdict'] == vb['verdict'] == want,
           f'{label}: both gates return {vb["verdict"]}')
        ok(per_player(va) == per_player(vb),
           f'{label}: per-player dispositions identical')


# -- 3. the one football field ---------------------------------------------
def test_the_team_share_comes_from_canonical_state():
    kw = AM.room_fixture()
    # The room fixture deliberately carries no shares, so give this one a
    # known carry share and a known target share. The point is WHERE the
    # number is read from, which needs a number to read.
    for r in kw['role_rows']:
        cu = r['evidence']['current_season_usage']
        cu['carry_share'] = 0.31 if r['gsis_id'] == 'RB1' else 0.08
        cu['target_share'] = 0.12
    ds = D.build_dossiers(**kw).value['dossiers']
    d = next(x for x in ds if x.gsis_id == 'RB1')
    ps = d.player_state
    share = G.team_opportunity_share(d)
    ok(share == ps.current_season_opportunity['carry_share'].value
       == d.canonical.carry_share == 0.31,
       f'the share is the PlayerState value, carried on the dossier as a '
       f'typed canonical fact: {share}')
    ok(d.canonical.carry_share_grade
       == ps.current_season_opportunity['carry_share'].grade,
       f'with the grade the state gave it: {d.canonical.carry_share_grade}')
    ok(d.canonical.source_axes['carry_share']
       == 'current_season_opportunity.carry_share',
       'and the state axis it came from')
    ok(share == d.value('carry_share'),
       'and it agrees with the dossier\'s relabelled copy, which is why '
       'this migration changes no verdict')
    wr = next(x for x in ds if x.gsis_id == 'WR1')
    wr.canonical = D.CanonicalFacts.from_dict(
        dict(wr.canonical.as_dict(), carry_share=None))
    ok(G.team_opportunity_share(wr) == 0.12,
       'a player with no carry share falls to his target share')
    # THIS ASSERTION USED TO PIN THE DEFECT. It read: "a player with BOTH
    # is weighed on his carry share alone, never the larger of the two --
    # PRESERVED and REGISTERED". The correction has since been made and
    # measured, so the test asserts the rule rather than the bug.
    rb4 = next(x for x in ds if x.gsis_id == 'RB4')
    m = G.team_opportunity_materiality(rb4)
    ok(m.value == 0.12 and m.selected_metric == G.TARGET_SHARE,
       f'a player with BOTH is weighed on the LARGER of the two: '
       f'carry {m.carry_share}, target {m.target_share} -> {m.value} '
       f'({m.selected_metric})')
    ok(G.team_opportunity_share(rb4) == 0.12,
       'and the threshold comparison uses that number')
    src = (_REPO / 'nfl/production/review/gate.py').read_text()
    ok("dossier.value('carry_share')" not in src
       and "dossier.value('target_share')" not in src,
       'the gate no longer reads either share off a dossier axis')
    ok('canonical' in src and 'carry_share' in src,
       'and reads the typed canonical fact instead')


def test_the_gate_never_rebuilds_a_denominator():
    src = (_REPO / 'nfl/production/review/gate.py').read_text()
    for token in ('team_carries', 'team_targets', 'team_dropbacks',
                  'current_season_team_volume', 'TeamState'):
        ok(token not in src,
           f'the gate computes no club total of its own: {token!r}')
    ok('NO DENOMINATOR IS REBUILT HERE' in src,
       'and says so where the share is read')


def test_a_stateless_dossier_fails_closed():
    d = D.PlayerPregameDossier(
        gsis_id='X', display_name='X', team='CAR', opponent='ATL',
        game_id=SLATE, season=2026, week=2, information_cut=CUT,
        support_state='MODEL_SUPPORTED')
    try:
        G.team_opportunity_share(d)
        ok(False, 'a dossier with no canonical facts should not yield a '
                  'share')
    except AssertionError as e:
        ok('no canonical facts' in str(e),
           'the share accessor refuses by name')
    rep = {'conflicts': [{'gsis_id': 'X', 'code': A.C_COLD_START_MATERIAL,
                          'severity': 'REVIEW', 'display_name': 'X'}],
           'projection_source': {'digests': {}}, 'coverage': {}}
    g = G.evaluate(rep, dossiers=[d])
    v = G.payload(g)
    ok(v['verdict'] == G.BLOCKED,
       'and the gate BLOCKS rather than raising out of a governance call')
    ok(v['conflicts'][0]['category'] == 'integrity'
       and 'no canonical facts'
       in v['conflicts'][0]['materiality']['why'],
       'recording why it could not be assessed')


# -- 4. the widened code ----------------------------------------------------
def test_the_widened_code_keeps_its_name_and_states_its_meaning():
    ok(A.C_INACTIVE_OWNS_OPPORTUNITY == 'INACTIVE_PLAYER_OWNS_OPPORTUNITY',
       'the identifier is unchanged')
    ok(A.C_INACTIVE_OWNS_OPPORTUNITY in G.BLOCKING_CODES
       and G.BLOCKING_CODES[A.C_INACTIVE_OWNS_OPPORTUNITY]
       == 'availability_integrity',
       'still blocking, still under availability_integrity')
    m = G.WIDENED_CODE_MEANING[A.C_INACTIVE_OWNS_OPPORTUNITY]
    for token in ('WILL_NOT_PLAY', 'OFFICIAL_INACTIVE', 'INJURY_OUT',
                  'material projected opportunity'):
        ok(token in m, f'the documented meaning names {token!r}')
    ok(A.C_INACTIVE_OWNS_OPPORTUNITY in G.MATERIALITY_EXEMPT,
       'and it stays materiality-exempt: an availability failure corrupts '
       'the frame regardless of the row\'s size')


# -- 5. refusals ------------------------------------------------------------
def test_refusal_states_are_preserved():
    g = G.evaluate(None)
    ok(g.code == G.PLAYER_REVIEW_NOT_RUN and G.verdict_of(g) == G.BLOCKED,
       f'no report -> {g.code}')
    rep = {'conflicts': [], 'projection_source': {'digests': {}},
           'coverage': {}}
    g = G.evaluate(rep, projection_digest='abc123')
    ok(g.code == G.PLAYER_REVIEW_STALE and G.verdict_of(g) == G.BLOCKED,
       f'a review with no draw digest, against a digest -> {g.code}')
    rep2 = {'conflicts': [],
            'projection_source': {'digests': {'player_draws.npz': 'dead'}},
            'coverage': {}}
    g = G.evaluate(rep2, projection_digest='beef')
    ok(g.code == G.PLAYER_REVIEW_STALE and G.verdict_of(g) == G.BLOCKED,
       f'a review of a different run -> {g.code}')
    g = G.evaluate(rep2, projection_digest='dead')
    ok(G.verdict_of(g) == G.PASS, f'and a matching digest passes: {g.code}')


def test_an_unknown_conflict_code_still_blocks():
    kw = AM.room_fixture()
    ds = D.build_dossiers(**kw).value['dossiers']
    rep, pub = report_for(A, kw, ds)
    rep['conflicts'] = []
    g = G.evaluate(rep, dossiers=ds, extra_conflicts=[
        {'code': 'A_CODE_NOBODY_REGISTERED', 'severity': 'NOTE',
         'gsis_id': 'RB1', 'display_name': 'RB1'}])
    v = G.payload(g)
    ok(v['verdict'] == G.BLOCKED, f'an unregistered code blocks: {g.code}')
    ok(v['conflicts'][0]['category'] == 'unregistered_code',
       'under its own category, so it is countable')


def test_a_conflict_with_no_dossier_still_blocks():
    rep = {'conflicts': [{'gsis_id': 'GHOST', 'code': A.C_COLD_START_MATERIAL,
                          'severity': 'REVIEW'}],
           'projection_source': {'digests': {}}, 'coverage': {}}
    g = G.evaluate(rep, dossiers=[])
    v = G.payload(g)
    ok(v['verdict'] == G.BLOCKED,
       'a conflict whose subject has no dossier cannot be assessed and '
       'blocks')
    ok(v['conflicts'][0]['category'] == 'integrity',
       'as an integrity failure')


def test_require_pass_and_write_gate_are_unweakened():
    rep = {'conflicts': [], 'projection_source': {'digests': {}},
           'coverage': {}}
    g = G.evaluate(rep)
    ok(G.require_pass(g).state.name == 'PASS', 'a PASS permits optimization')
    bad = G.evaluate(None)
    r = G.require_pass(bad)
    ok(r.state.name == 'FAIL'
       and r.code == 'OPTIMIZATION_REFUSED_BY_PLAYER_REVIEW',
       f'a refusal refuses optimization: {r.code}')
    w = G.write_gate({'verdict': None}, _REPO / 'nfl/research/_unused.json')
    ok(w.code == 'GATE_RECORD_WITHOUT_A_VERDICT',
       'and a verdict-free record is not writable')


def test_partial_player_coverage_is_not_governed_here_and_is_untouched():
    """It is governed in run_forecast and authorization, not in the gate.
    This slice must not have moved it, and must not have given the gate a
    quiet second opinion about it."""
    src = (_REPO / 'nfl/production/review/gate.py').read_text()
    ok('PARTIAL_PLAYER_COVERAGE' not in src,
       'the gate neither reads nor sets PARTIAL_PLAYER_COVERAGE')
    for mod in ('nfl/production/run_forecast.py',
                'nfl/production/authorization.py'):
        ok('PARTIAL_PLAYER_COVERAGE' in (_REPO / mod).read_text(),
           f'and it is still governed in {mod.split("/")[-1]}')


# -- 6. structural boundary -------------------------------------------------
def test_the_gate_reads_no_raw_football_source():
    src = (_REPO / 'nfl/production/review/gate.py').read_text()
    tree = ast.parse(src)
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                imported.add(a.name)
            if n.module:
                imported.add(n.module.split('.')[-1])
        elif isinstance(n, ast.Import):
            for a in n.names:
                imported.add(a.name.split('.')[-1])
    forbidden = {'vintage_selector', 'player_universe', 'depth_role',
                 'role_state', 'usage_vintage', 'depth_vintage', 'inactives',
                 'current_season_evidence', 'current_season_team_volume',
                 'snap_counts', 'availability_feed', 'csv', 'gzip'}
    hit = sorted(imported & forbidden)
    ok(not hit, f'the gate imports no football-source module or table '
                f'reader: {hit}')
    for token in ('.csv', '.gz', 'vintage/', 'vintage_manifest',
                  'weekly_rosters', 'depth_charts', 'official_inactives',
                  'snap_counts', 'schedules', 'read_bytes', 'read_text'):
        ok(token not in src,
           f'and names no raw football source or read: {token!r}')
    ok('write_bytes' in src,
       'while it still writes its own gate record, which is its job')
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in ('axis', 'value')
             and n.args and isinstance(n.args[0], ast.Constant)]
    ok(not calls,
       f'and it reads no dossier axis by name at all: '
       f'{sorted({c.args[0].value for c in calls})}')


def test_materiality_still_refuses_a_market_argument():
    import inspect
    sig = set(inspect.signature(G.materiality).parameters)
    ok(sig == {'dossier', 'conflict', 'in_optimizer_pool', 'rule'},
       f'materiality() takes {sorted(sig)} -- no market, ownership, external '
       f'projection or optimizer metric, by construction')


def test_a_verdict_re_derived_from_the_saved_artifact_reads_the_same_share():
    """THE DEFECT THIS SLICE FOUND. `gated_projection.load` re-derives the
    gate verdict from the SAVED dossiers, so that a verdict is a property of
    the artifact rather than of whoever is holding objects in memory. The
    live PlayerState reference is not serialised, so the first migrated gate
    blocked every rehydrated slate -- correctly by its own rule, and wrongly
    in fact. The typed CanonicalFacts is what crosses the artifact boundary.
    """
    kw = AM.room_fixture()
    for r in kw['role_rows']:
        r['evidence']['current_season_usage']['carry_share'] = 0.27
    ds = D.build_dossiers(**kw).value['dossiers']
    live = ds[0]
    saved = live.as_dict()
    ok('canonical' in saved and saved['canonical'],
       'the dossier artifact carries its canonical facts')
    ok('player_state' not in saved,
       'and does NOT carry the live state reference')
    rehydrated = D.PlayerPregameDossier(
        gsis_id=saved['gsis_id'], display_name=saved['display_name'],
        team=saved['team'], opponent=saved['opponent'],
        game_id=saved['game_id'], season=saved['season'],
        week=saved['week'], information_cut=saved['information_cut'],
        support_state=saved['support_state'],
        canonical=D.CanonicalFacts.from_dict(saved['canonical']))
    ok(G.team_opportunity_share(rehydrated)
       == G.team_opportunity_share(live) == 0.27,
       f'a rehydrated dossier weighs the same share as the live one: '
       f'{G.team_opportunity_share(rehydrated)}')
    ok(rehydrated.canonical.registry_identity
       == live.canonical.registry_identity,
       'and carries the registry identity that defined it')
    src = (_REPO / 'nfl/production/review/gated_projection.py').read_text()
    ok('CanonicalFacts.from_dict' in src,
       'and gated_projection rehydrates it when re-deriving a verdict')
    ok(D.CanonicalFacts.from_dict(None) is None,
       'an artifact written before this field existed yields None, not '
       'empty facts -- zero shares are not absent shares, and the gate '
       'fails closed rather than weighing a fabricated zero')


def main():
    for t in (test_the_gate_change_alone_changes_nothing,
              test_end_to_end_changes_are_only_the_out_correction,
              test_a_passing_and_a_warning_slate_are_unchanged,
              test_the_team_share_comes_from_canonical_state,
              test_the_gate_never_rebuilds_a_denominator,
              test_a_stateless_dossier_fails_closed,
              test_the_widened_code_keeps_its_name_and_states_its_meaning,
              test_refusal_states_are_preserved,
              test_an_unknown_conflict_code_still_blocks,
              test_a_conflict_with_no_dossier_still_blocks,
              test_require_pass_and_write_gate_are_unweakened,
              test_partial_player_coverage_is_not_governed_here_and_is_untouched,
              test_the_gate_reads_no_raw_football_source,
              test_materiality_still_refuses_a_market_argument,
              test_a_verdict_re_derived_from_the_saved_artifact_reads_the_same_share):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
