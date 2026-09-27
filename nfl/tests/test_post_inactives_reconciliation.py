#!/usr/bin/env python3.12
"""Phase-10 validation for the POST-INACTIVES reconciliation, as executable checks.

Every item the owner listed under "Before committing" is a test here rather than a
sentence in a report, because a sentence in a report is not re-checked when the code
changes and a test is.

Three of these are BYPASS proofs. A guard that reports a violation and still returns its
rows is advisory; a guard that refuses is load-bearing. The only way to show the
difference is to stub the guard out and confirm the protected action then happens, so
that is what the bypass tests do.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests.bypass import guard_bypassed  # noqa: E402
from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import post_inactives_state as PS  # noqa: E402
from nfl.tools import redistribution as RD  # noqa: E402
from nfl.tools import state_compare as SC  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

PRE = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE.json'
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
EARLY = ('CAR@CLE', 'CIN@PIT', 'HOU@IND', 'KC@MIA', 'LAC@BUF',
         'NE@JAX', 'NYJ@DET', 'SEA@WAS', 'TEN@NYG')

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _pre():
    return json.loads(PRE.read_text())


def _post():
    return json.loads(POST.read_text())


# --- preservation ------------------------------------------------------------
@check('all 457 DK rows preserved, zero silent drops')
def t_rows():
    pre, post = _pre()['players'], _post()['players']
    assert len(pre) == 457, f'PRE has {len(pre)} rows, expected 457'
    assert len(post) == 457, f'POST has {len(post)} rows, expected 457'
    assert set(pre) == set(post), f'{len(set(pre) ^ set(post))} dk_ids differ'
    return f'{len(post)} rows, identical dk_id sets'


@check('the PRE artifact is byte-identical to the digest the POST state recorded')
def t_pre_unchanged():
    r = SC.assert_pre_artifact_unchanged(_post())
    assert r.state is State.PASS, str(r)
    return r.detail


@check('every DST row survived and no DST was given an availability it cannot have')
def t_dst():
    post = _post()['players']
    dst = [v for v in post.values() if v['position'] == 'DST']
    assert len(dst) == 18, f'{len(dst)} DST rows, expected 18'
    bad = [v['name'] for v in dst
           if v['current_availability']['status'] in AV.ABSENT_STATUSES]
    assert not bad, f'a team defence cannot be inactive: {bad}'
    return f'{len(dst)} DST rows, none marked absent'


# --- the four zeros ----------------------------------------------------------
@check('zero missing-to-zero conversions')
def t_missing_not_zero():
    post = _post()
    slay = next(v for v in post['players'].values() if v['name'] == 'Darius Slayton')
    tree = post['redistribution'].get('IND:Darius Slayton')
    assert tree is not None, 'Slayton is reported inactive but has no tree'
    assert tree['vacated']['observed_state'] == RD.UNKNOWN_NO_ROW, \
        f'Slayton vacated reads {tree["vacated"]["observed_state"]}, must be UNKNOWN'
    for k in ('carries', 'targets', 'offense_snaps'):
        assert tree['vacated'][k] == RD.UNKNOWN_NO_ROW, \
            f'Slayton {k} rendered as {tree["vacated"][k]!r} rather than UNKNOWN'
    q = tree['ten_questions']['what_observed_opportunity_disappears']
    assert q['measured'] == RD.UNKNOWN_NO_ROW, 'question 1 collapsed UNKNOWN to a number'
    assert any('NO_OBSERVED_2026_ROW' in s for s in slay['data_quality_warnings']), \
        'no data-quality warning on a player with no observed row'
    # and a player WITH a row still gets real zeros, not UNKNOWN
    leg = post['redistribution']['CAR:Xavier Legette']['vacated']
    assert leg['carries'] == 0.0, f'Legette carries {leg["carries"]!r}, expected real 0'
    assert leg['observed_state'] == 'OBSERVED'
    return 'Slayton UNKNOWN_NO_OBSERVED_ROW; Legette a real zero. Both states kept'


@check('zero predicted-to-confirmed promotions')
def t_no_confirmed():
    post = _post()['players']
    confirmed = [(v['name'], v['current_availability']['status'])
                 for v in post.values()
                 if v['current_availability']['status'] in
                 (AV.CONFIRMED_INACTIVE, AV.CONFIRMED_ACTIVE,
                  AV.ACTIVE_NOT_ON_INACTIVE_LIST)]
    assert not confirmed, (
        f'{len(confirmed)} rows claim a confirmed status while no official document is '
        f'held: {confirmed[:6]}')
    held = [v['name'] for v in post.values()
            if v['current_availability'].get('document_held')]
    assert not held, f'{len(held)} rows claim a held document; none exists'
    return f'{len(post)} rows, zero confirmed statuses, zero claimed documents'


@check('a predicted lineup confers no availability status')
def t_predicted_is_not_availability():
    post = _post()['players']
    pred = [v for v in post.values()
            if (v.get('predicted_lineup_context') or {})
            .get('in_predicted_starting_group')]
    assert pred, 'no predicted-lineup members found; the reader is broken'
    leaked = [v['name'] for v in pred
              if v['current_availability']['evidence_tier'] == AV.TIER_PREDICTED
              or v['current_availability']['status'] in AV.PRESENT_STATUSES
              and v['current_availability']['resolution_method'].startswith('PREDICTED')]
    assert not leaked, f'predicted lineup laundered into availability for {leaked[:6]}'
    unresolved = [v['name'] for v in pred
                  if v['current_availability']['status'] == AV.UNKNOWN_NOT_RELAYED]
    assert unresolved, (
        'every predicted starter resolved to an availability state, which means being '
        'named in a lineup granted one')
    return (f'{len(pred)} predicted starters, {len(unresolved)} still '
            f'UNKNOWN_NOT_RELAYED')


@check('zero FantasyCruncher contamination of any football field')
def t_fc_firewall():
    post = _post()['players']
    banned = ('fc_projection', 'fc_floor', 'fc_ceiling', 'fc_ownership', 'projection',
              'floor', 'ceiling', 'ownership')
    hits = []
    for v in post.values():
        for k in v:
            if k == 'external_fc_context':
                continue
            if any(b in k.lower() for b in banned):
                hits.append((v['name'], k))
        ctx = v.get('external_fc_context') or {}
        for k in ctx:
            if any(b in str(k).lower() for b in ('projection', 'floor', 'ceiling',
                                                 'ownership')):
                hits.append((v['name'], f'external_fc_context.{k}'))
    assert not hits, f'FC values reached a football field: {hits[:8]}'
    return ('no FC projection, floor, ceiling or ownership value appears in any field, '
            'inside or outside the quarantined context block')


@check('no questionable-to-active assumption without authoritative evidence')
def t_questionable():
    post = _post()['players']
    bad = []
    for v in post.values():
        av = v['current_availability']
        if av['status'] in AV.PRESENT_STATUSES:
            if av['evidence_tier'] not in (AV.TIER_AGGREGATOR_REPORTED,
                                           AV.TIER_OFFICIAL_RELEASE_CITED,
                                           AV.TIER_OFFICIAL_CAPTURED, AV.TIER_OBSERVED):
                bad.append((v['name'], av['status'], av['evidence_tier']))
            assert av.get('source_quote'), \
                f'{v["name"]} is reported available with no quoted source sentence'
    assert not bad, f'availability asserted on a weak tier: {bad}'
    return 'every available row rests on a reported list and carries its quote'


# --- coverage and provenance -------------------------------------------------
@check('all nine Early Only games covered')
def t_nine_games():
    post = _post()
    gf = post['game_findings']
    assert set(gf) == set(EARLY), f'games {sorted(gf)} != {sorted(EARLY)}'
    for g, v in gf.items():
        assert len(v['clubs']) == 2, f'{g} has {len(v["clubs"])} clubs'
        assert v['environment'].get('total'), f'{g} has no market total'
    return f'{len(gf)} games, 2 clubs each, market present on all'


@check('availability provenance recorded on every single row')
def t_provenance():
    post = _post()['players']
    for v in post.values():
        p = v['current_availability_provenance']
        for f in ('evidence_tier', 'resolution_method', 'document_held'):
            assert f in p, f'{v["name"]} provenance lacks {f}'
        assert p['evidence_tier'] in AV.TIERS, \
            f'{v["name"]} undeclared tier {p["evidence_tier"]!r}'
    resolved = [v for v in post.values()
                if v['current_availability']['status'] != AV.UNKNOWN_NOT_RELAYED]
    for v in resolved:
        p = v['current_availability_provenance']
        assert p['source'] and p['source_timestamp'] and p['retrieval_timestamp'], \
            f'{v["name"]} is resolved but lacks source or timestamps'
        assert p['source_quote'], f'{v["name"]} is resolved with no quoted sentence'
    return (f'{len(post)} rows carry a declared tier; all {len(resolved)} resolved rows '
            f'carry source, both timestamps and a quote')


@check('every material inactive has a redistribution record')
def t_every_absence_has_a_tree():
    post = _post()
    absent = [(v['team'], v['name']) for v in post['players'].values()
              if v['current_availability']['status'] in AV.ABSENT_STATUSES]
    trees = post['redistribution']
    missing = [f'{c}:{n}' for c, n in absent if f'{c}:{n}' not in trees]
    assert not missing, f'reported absent with no tree: {missing}'
    for k, t in trees.items():
        assert t['inheritance'] == RD.UNRESOLVED, \
            f'{k} assigned an inheritance rather than leaving it unresolved'
        assert t['competing_non_player_sinks'], f'{k} lists no competing sink'
        assert t['rank_basis'], f'{k} ranks candidates with no declared basis'
    return f'{len(absent)} absences, {len(trees)} trees, every inheritance unresolved'


@check('routes remain unknown everywhere and are never inferred from pass snaps')
def t_routes():
    post = _post()
    n = 0
    for v in post['players'].values():
        o = (v.get('observed_2026') or {})
        for f in ('routes', 'route_participation'):
            if f in o:
                assert o[f] == 'UNKNOWN_SOURCE_UNAVAILABLE', \
                    f'{v["name"]} {f} = {o[f]!r}'
                n += 1
    for k, t in post['redistribution'].items():
        assert t['vacated']['routes'] == 'UNKNOWN_SOURCE_UNAVAILABLE', \
            f'{k} vacated routes = {t["vacated"]["routes"]!r}'
    return f'{n} route fields, all UNKNOWN_SOURCE_UNAVAILABLE'


@check('the Q9 projection board stays blocked and is not bypassed')
def t_q9_blocked():
    post = _post()
    pb = post['proprietary_projection_board']
    assert pb['exists'] is False, 'a projection board is claimed to exist'
    assert pb['code'] == 'STAGE_DECLARED_UNIMPLEMENTED', pb['code']
    assert pb['not_bypassed'] is True
    for v in post['players'].values():
        for k in v:
            assert 'projected_points' not in k and 'fantasy_points' not in k, \
                f'{v["name"]} carries {k}, which would be a projection'
    return 'no projection produced, refusal preserved, no projected field on any row'


@check('the QB layer stays a PRE-R2 intermediate and is not read as a week-3 number')
def t_qb_layer():
    post = _post()['players']
    qb = [v for v in post.values() if v.get('qb_layer_pre_r2_context')]
    assert qb, 'no QB layer context carried at all'
    for v in qb:
        c = v['qb_layer_pre_r2_context']
        blob = json.dumps(c)
        assert 'IS_NOT_A_WEEK3_PROJECTION' in blob or 'NOT_A_WEEK3' in blob, \
            f'{v["name"]} QB context lacks its warning'
    for g in _post()['game_findings'].values():
        for club in g['clubs'].values():
            assert 'PRE-R2' in club['qb_implications']['qb_layer_warning']
    return f'{len(qb)} QB rows carry the PRE-R2 warning; all 18 clubs restate it'


@check('the observed-2026 staleness correction is preserved, not regressed')
def t_observed_correction():
    post = _post()
    oc = post['OBSERVED_2026_CORRECTION_PRESERVED']
    for n in ('Carnell Tate', 'Denzel Boston', 'Caleb Douglas', 'Malachi Fields',
              'KC Concepcion Jr.', 'Jadarian Price'):
        assert n in oc['named_examples'], f'{n} dropped from the preserved correction'
    assert '19 of 53' in oc['finding']
    players = post['players']
    tate = next(v for v in players.values() if v['name'] == 'Carnell Tate')
    assert tate['historical_role_class_valid_for_current_role'] is False, \
        'Tate historical role flagged valid again, regressing the correction'
    assert tate['materially_active_2026'] is True
    return ('correction intact, six named examples present, Tate still carries '
            'historical_role_class_valid_for_current_role = false')


@check('the second pass resolved 20 rows and left the rest honestly unresolved')
def t_counts():
    post = _post()
    counts = post['availability_counts']
    assert sum(counts.values()) == 457, sum(counts.values())
    resolved = sum(v for k, v in counts.items() if k != AV.UNKNOWN_NOT_RELAYED)
    assert resolved == 20, f'{resolved} resolved, expected 20'
    assert counts[AV.UNKNOWN_NOT_RELAYED] == 437
    assert post['COMPLETENESS']['lists_enumerated_to_this_repository'] == 0
    return f'{resolved} resolved, {counts[AV.UNKNOWN_NOT_RELAYED]} UNKNOWN_NOT_RELAYED'


# --- the comparator ----------------------------------------------------------
@check('the semantic comparator separates football from DraftKings changes')
def t_compare():
    r = SC.run()
    assert r.state is State.PASS, str(r)
    v = r.value
    assert v['n_football_availability_changes'] == 20, \
        v['n_football_availability_changes']
    assert v['n_status_relabels_no_football_change'] == 437
    assert not v['opportunity_changes'], (
        f'observed weeks 1-2 moved between passes for '
        f'{len(v["opportunity_changes"])} players, which is a builder defect')
    for row in v['NON_FOOTBALL_CHANGES_QUARANTINED']['rows']:
        assert row['football_change'] is False
    moved = [e['game'] for e in v['environment_changes'] if e['change'] == 'MOVED']
    assert len(moved) == 5, f'{len(moved)} games moved, expected 5'
    return (f'20 football changes, 437 relabels, 0 opportunity drift, '
            f'{len(moved)} market moves')


# --- bypass proofs ----------------------------------------------------------
@check('BYPASS: the confirmation guard is load-bearing, not advisory')
def t_bypass_confirmation():
    rows = {'x': {'current_availability': {
        'status': AV.CONFIRMED_INACTIVE, 'evidence_tier': AV.TIER_AGGREGATOR_REPORTED}}}
    real = AV.assert_no_unauthorised_confirmation(rows)
    assert real.state is State.FAIL, f'guard permitted the violation: {real}'
    assert real.code == 'AVAILABILITY_CONFIRMED_WITHOUT_EVIDENCE'
    with guard_bypassed('nfl.tools.availability',
                        'assert_no_unauthorised_confirmation',
                        returns=Outcome.ok('STUB', value=1)):
        stubbed = AV.assert_no_unauthorised_confirmation(rows)
    assert stubbed.state is State.PASS, 'the bypass did not take effect'
    return ('a CONFIRMED_INACTIVE on a reported tier FAILs with the guard and PASSes '
            'without it, so the guard is what rejects it')


@check('BYPASS: the comparator refuses its whole report when PRE has been mutated')
def t_bypass_pre_mutated():
    post = _post()
    post['upstream_artifacts']['pre_inactives_state']['sha256'] = '0' * 64
    real = SC.assert_pre_artifact_unchanged(post)
    assert real.state is State.FAIL and real.code == 'PRE_ARTIFACT_MUTATED', str(real)
    pre = _pre()
    with guard_bypassed('nfl.tools.state_compare', 'assert_pre_artifact_unchanged',
                        returns=Outcome.ok('STUB', value='x')):
        out = SC.compare(pre, post)
    assert out.state is State.PASS, (
        'the comparison still refused with the guard stubbed, so something else was '
        'rejecting it and this test proves nothing about this guard')
    assert 'availability_changes' in out.value, 'no rows were produced'
    real_run = SC.compare(pre, post)
    assert real_run.state is State.FAIL and real_run.code == 'PRE_ARTIFACT_MUTATED', \
        'compare returned rows on a mutated PRE, so the guard is advisory'
    return ('with the guard in place compare() returns FAIL and NO rows; with it '
            'stubbed the same input yields a full report. The protected action is the '
            'report, and the guard stops it')


@check('BYPASS: the comparator refuses when a DK row has been dropped')
def t_bypass_row_dropped():
    pre, post = _pre(), _post()
    victim = next(iter(post['players']))
    name = post['players'][victim]['name']
    del post['players'][victim]
    real = SC.compare(pre, post)
    assert real.state is State.FAIL and real.code == 'DK_ROWS_DROPPED', str(real)
    with guard_bypassed('nfl.tools.state_compare', 'assert_no_row_dropped',
                        returns=Outcome.ok('STUB', value=0)):
        out = SC.compare(pre, post)
    assert out.state is State.PASS, 'the bypass did not take effect'
    return (f'dropping {name} FAILs DK_ROWS_DROPPED and returns no report; stubbing '
            f'the guard lets the same 456-row input through')


@check('official inactive capture state is recorded as BLOCKED, not as absence of need')
def t_capture_state():
    post = _post()
    cs = post['official_capture_state']
    assert cs['state'] == 'BLOCKED', cs['state']
    assert cs['code'] == 'OFFICIAL_INACTIVES_NOT_CAPTURED'
    assert cs['evidence']['cause'] == 'DATA'
    assert cs['evidence']['n_absent'] == 9
    outbox = (_REPO / 'docs/AGENT_OUTBOX.md').read_text()
    assert 'OUT-035' in outbox, 'blocked on outside data with no outbox request filed'
    return ('capture BLOCKED with cause DATA on all 9 games, and OUT-035 carries the '
            'request rather than the task being called blocked for the project')


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
