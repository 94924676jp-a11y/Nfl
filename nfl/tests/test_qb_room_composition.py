"""WS-G: QB-ROOM COMPOSITION MUST COME FROM THE SEAL, NEVER FROM THE OUTCOME.

THE DEFECT THESE TESTS PIN DOWN (WS22 verdict item 5, leakage L2).

`postgame.qb_room_aggregate` composed each team's quarterback room by asking
the realised play-by-play who threw a pass:

    by_team[_team_of(rows, pid) or 'UNKNOWN'].append(pid)   # 'UNKNOWN' skipped

A quarterback who was FORECAST to play and recorded ZERO attempts has no
`passer_player_id` row anywhere in the outcome, resolves to 'UNKNOWN', and was
deleted from his own team's room. The forecast population was therefore
selected after the result was known. Measured on the ten stored 2026 week-1
games: 457 of 650 sealed QB room memberships were deleted that way -- 70.3%
of the forecast rooms -- and the mean room shrank from 3.85 quarterbacks to
1.15.

The realised value is untouched by the deletion (a quarterback who did not
play contributes a realised zero either way), so the whole movement is on the
FORECAST side. That is what makes it selection on the outcome rather than a
measurement choice.

WHAT IS ASSERTED HERE, and why each one is needed.

  a  A QB forecast to play with ZERO realised attempts REMAINS in the room.
     This is the defect itself, stated as a property.
  b  Composition is STRUCTURALLY independent of the outcome, proved three
     ways: the composer takes no outcome argument at all; mutating the
     realised play-by-play does not move a single composition byte; and
     sabotaging `_team_of` -- the function the old path composed from --
     changes nothing.
  c  The room RECONSTRUCTS FROM SEALED BYTES ALONE, in a directory that
     contains no outcome file, for every sealed forecast this repository
     holds.
  d  An unresolvable member is a NAMED REFUSAL of the whole room, not a
     dropped row. A room missing a forecast member is a different quantity
     from the room that was forecast.
  e  Two pregame sources disagreeing about a member is a named refusal too.
     No precedence rule silently picks a winner.
  f  A team code on the sealed row axis that does not join to the realised
     outcome is a NAMED refusal (`TEAM_CODE_NOT_IN_REALISED_OUTCOME`), where
     it used to be an unexplained `continue`.

EVALUATION-ONLY. Nothing here touches a projection or a price. Every sealed
forecast distribution is read exactly as sealed; what changed is which of
those sealed distributions are summed into a room row, and how a refusal is
named.

NOTHING HERE WRITES INTO A SEAL, A LEDGER, OR THE LIVE POSTGAME STORE.
"""
from __future__ import annotations

import copy
import inspect
import json
import os
import pathlib
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import Outcome, State           # noqa: E402
from nfl.research import postgame as PG                                # noqa: E402
from nfl.research import sealed_index as SI                            # noqa: E402
from nfl.research.shadow import actuals as ACT                         # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


# ------------------------------------------------------------- fixtures
_BLOB = pathlib.Path(_ROOT) / 'nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz'
_IDENT = {'forecast_id': 'FC-TEST', 'candidate': 'TEST', 'outcome_sha16': 'f' * 16}


def _seals_with_draws():
    out = []
    for rec in SI.discover_all():
        d = pathlib.Path(rec['dir'])
        if (d / 'player_draws_manifest.json').exists() and rec.get('has_draws'):
            out.append(rec)
    return out


def _pick():
    """One real sealed forecast for a game whose outcome this repo stores."""
    if not _BLOB.exists():
        return None, None, None
    games = set(json.loads(
        _BLOB.with_suffix('').with_suffix('.csv.provenance.json').read_text()
    )['games'])
    for rec in sorted(_seals_with_draws(), key=lambda r: r['rel_dir']):
        if rec.get('game_id') not in games:
            continue
        man = json.loads(
            (pathlib.Path(rec['dir']) / 'player_draws_manifest.json').read_text())
        ids = ((man.get('layers') or {}).get('qb') or {}).get('row_ids') or []
        if len(ids) >= 3:
            return rec, man, ACT.load(_BLOB, rec['game_id'])
    return None, None, None


def _composition(rowlist):
    """The composition fields only -- what must never depend on the outcome."""
    return sorted((r['team'], r['metric'], r['room_composition_digest'],
                   tuple(r['room_members']), r['n_quarterbacks'],
                   r['mean'], r['sd'],
                   json.dumps(r['percentiles'], sort_keys=True))
                  for r in rowlist)


# --------------------------------------------------------------- a
def test_a_zero_attempt_quarterback_stays_in_the_room():
    print('\n-- a. a forecast QB with zero realised attempts is RETAINED --')
    rec, man, rows = _pick()
    if rec is None:
        check('a sealed forecast with a stored outcome exists', False)
        return
    draws = SI.load_draws(pathlib.Path(rec['dir']))
    qa = ACT.qb_actuals(rows)
    out, refused = PG.qb_room_aggregate(
        dict(rec), man, draws, qa, rows, dict(_IDENT))
    check('the room scores at all', bool(out), f'{len(out)} row(s)')
    if not out:
        return
    ids = ((man.get('layers') or {}).get('qb') or {}).get('row_ids') or []
    zero = [p for p in ids if PG._team_of(rows, p) is None]
    check('the fixture actually contains a zero-attempt forecast QB',
          bool(zero), f'{len(zero)} of {len(ids)}')
    members = set()
    for r in out:
        members |= set(r['room_members'])
    check('  every zero-attempt forecast QB is still a room member',
          all(p in members for p in zero),
          f'{sum(1 for p in zero if p in members)}/{len(zero)} retained')
    check('  every sealed row_id is a member of exactly one room',
          members == set(ids), f'{len(members)} of {len(ids)}')
    check('  and the row says so in a counted field, not only in prose',
          all(r['n_quarterbacks_zero_attempt_retained']
              == r['n_quarterbacks'] - r['n_quarterbacks_with_realised_attempt']
              for r in out))
    retained = sum(r['n_quarterbacks_zero_attempt_retained']
                   for r in out if r['metric'] == 'qb/att')
    check('  the retained count is positive on this fixture',
          retained > 0, f'{retained} retained on {rec["rel_dir"]}')
    check('no room refusal was generated for a healthy seal',
          refused == [], str(refused[:1]))


# --------------------------------------------------------------- b
def test_b_composition_cannot_see_the_outcome():
    print('\n-- b. the realised outcome cannot reach composition --')
    rec, man, rows = _pick()
    if rec is None:
        check('a sealed forecast with a stored outcome exists', False)
        return
    draws = SI.load_draws(pathlib.Path(rec['dir']))

    # b1. THE ARGUMENT LIST. A function cannot condition on what it is not
    # given. This is the structural claim, and it does not depend on data.
    sig = list(inspect.signature(PG.pregame_room_membership).parameters)
    check('the composer takes no outcome argument',
          sig == ['seal_dir', 'manifest', 'layer'], str(sig))
    src = inspect.getsource(PG.pregame_room_membership)
    for forbidden in ('passer_player_id', 'posteam', '_team_of', 'qb_act'):
        check(f'  and never names {forbidden!r}', forbidden not in src)

    # b2. MUTATE THE OUTCOME. Every composition byte must be identical.
    base_rows = [dict(r) for r in rows]
    qa = ACT.qb_actuals(base_rows)
    base, _ = PG.qb_room_aggregate(
        dict(rec), man, draws, qa, base_rows, dict(_IDENT))

    erased = [dict(r, passer_player_id='') for r in rows]
    swapped = []
    for r in rows:
        r2 = dict(r)
        if r2.get('posteam'):
            r2['posteam'] = 'ZZZ'
        swapped.append(r2)
    empty = []

    for label, mutant in (('every passer id erased', erased),
                          ('every posteam relabelled ZZZ', swapped),
                          ('the outcome removed entirely', empty)):
        got, _ref = PG.qb_room_aggregate(
            dict(rec), man, draws, ACT.qb_actuals(mutant) if mutant else {},
            mutant, dict(_IDENT))
        check(f'  composition is byte-identical with {label}',
              _composition(got) == _composition(base),
              f'{len(got)} row(s) vs {len(base)}')

    # b3. AND the realised half DOES move, so b2 is not vacuous.
    got, _ = PG.qb_room_aggregate(
        dict(rec), man, draws, {}, empty, dict(_IDENT))
    moved = [(r['team'], r['metric']) for r in base
             if any(g['team'] == r['team'] and g['metric'] == r['metric']
                    and g['actual'] != r['actual'] for g in got)]
    check('  the realised side DOES move when the outcome is removed',
          bool(moved), f'{len(moved)} row(s) changed actual')

    # b4. SABOTAGE THE OLD COMPOSER. `_team_of` is what the defect composed
    # from; if composition still used it, lying to it would move the rooms.
    original = PG._team_of
    try:
        PG._team_of = lambda _rows, _pid: 'SABOTAGE'
        got, _ = PG.qb_room_aggregate(
            dict(rec), man, draws, qa, base_rows, dict(_IDENT))
        check('  composition survives _team_of returning a fabricated team',
              _composition(got) == _composition(base))
        check('    and _team_of survives only as a diagnostic count',
              all(r['n_quarterbacks_with_realised_attempt'] == 0
                  for r in got))
    finally:
        PG._team_of = original

    # b5. PROVENANCE IS STAMPED, so a reader never has to infer it.
    check('every room row names its composition source',
          all(r['room_composition_source'] == 'PREGAME_SEAL' for r in base))
    check('  and the sealed files it was read from',
          all(r['room_composition_inputs'] for r in base))
    check('  and addresses members by the sealed row axis, not by position',
          all(r['room_row_axis'] == 'gsis_id' for r in base),
          str({r['room_row_axis'] for r in base}))


# --------------------------------------------------------------- c
def test_c_the_room_reconstructs_from_sealed_bytes_alone():
    print('\n-- c. pregame identity is recoverable from the seal --')
    seals = _seals_with_draws()
    check('this repository holds sealed forecasts to reconstruct',
          len(seals) > 0, f'{len(seals)} seal(s)')
    states, n_members, no_source = {}, 0, []
    for rec in seals:
        o = PG.pregame_room_from_seal(rec['dir'], layer='qb')
        states[o.code] = states.get(o.code, 0) + 1
        if o.state is State.PASS:
            n_members += len(o.value['membership'])
        else:
            no_source.append((rec['rel_dir'], o.code))
    check('every sealed forecast reconstructs its QB room from its own bytes',
          not no_source, str(no_source[:3]))
    check('  and the reconstruction is not empty',
          n_members > 0, f'{n_members} member(s) across {len(seals)} seal(s)')

    # THE HARD VERSION: copy the seal somewhere with NO outcome anywhere near
    # it, and reconstruct there. If this needs the outcome, it fails.
    rec, man, rows = _pick()
    if rec is None:
        return
    live = PG.pregame_room_membership(rec['dir'], man, layer='qb')
    check('the live seal composes', live.state is State.PASS, live.code)
    with tempfile.TemporaryDirectory() as td:
        dst = pathlib.Path(td) / 'seal_only'
        shutil.copytree(rec['dir'], dst)
        for junk in dst.rglob('*'):
            if junk.is_file() and ('pbp' in junk.name
                                   or junk.name == 'EVALUATION.json'
                                   or junk.name == 'REALIZED_OUTCOMES.json'):
                junk.unlink()
        iso = PG.pregame_room_from_seal(dst, layer='qb')
        check('  and reconstructs identically from an isolated copy',
              iso.state is State.PASS
              and iso.value['digest'] == live.value['digest'],
              f'{iso.code} {iso.evidence.get("digest")}')
        check('    with the same membership, member for member',
              iso.state is State.PASS
              and iso.value['membership'] == live.value['membership'])
        names = {p.name for p in dst.iterdir()}
        check('    from an isolated directory that holds no outcome file',
              not any('pbp' in n for n in names), str(sorted(names)))

    # The digest is a real discriminator, not a constant.
    digests = {PG.pregame_room_from_seal(r['dir']).evidence.get('digest')
               for r in seals}
    check('  the composition digest distinguishes different rooms',
          len(digests) > 1, f'{len(digests)} distinct digest(s)')
    check('  and moving one member changes it',
          PG.room_digest({'a': 'NE', 'b': 'NE'})
          != PG.room_digest({'a': 'NE', 'b': 'SEA'}))
    check('  while dict ordering does not',
          PG.room_digest({'a': 'NE', 'b': 'SEA'})
          == PG.room_digest({'b': 'SEA', 'a': 'NE'}))


# --------------------------------------------------------------- d + e
def _copy_seal(rec, td):
    dst = pathlib.Path(td) / 'seal'
    shutil.copytree(rec['dir'], dst)
    return dst


def test_d_an_unresolvable_member_refuses_the_room_by_name():
    print('\n-- d. a member with no pregame team refuses the WHOLE room --')
    rec, man, rows = _pick()
    if rec is None:
        check('a sealed forecast with a stored outcome exists', False)
        return
    draws = SI.load_draws(pathlib.Path(rec['dir']))
    qa = ACT.qb_actuals(rows)
    ids = ((man.get('layers') or {}).get('qb') or {}).get('row_ids') or []
    victim = ids[0]
    with tempfile.TemporaryDirectory() as td:
        dst = _copy_seal(rec, td)
        for fname in ('board.json', 'SEALED_FORECAST.json'):
            p = dst / fname
            if not p.exists():
                continue
            doc = json.loads(p.read_text())
            if doc.get('players'):
                doc['players'] = [x for x in doc['players']
                                  if x.get('gsis_id') != victim]
            if doc.get('depth_chart'):
                doc['depth_chart'] = {k: v for k, v in doc['depth_chart'].items()
                                      if v != victim}
            p.write_text(json.dumps(doc))
        o = PG.pregame_room_membership(dst, man, layer='qb')
        check('composition refuses rather than dropping the member',
              o.state is State.BLOCKED, f'{o.state.name}[{o.code}]')
        check('  under a NAMED code', o.code == PG.ROOM_MEMBER_UNRESOLVED,
              o.code)
        check('  that names the member it could not resolve',
              victim in (o.evidence.get('unresolved') or []),
              str(o.evidence.get('unresolved')))
        sealed = dict(rec)
        sealed['dir'] = str(dst)
        out, refused = PG.qb_room_aggregate(
            sealed, man, draws, qa, rows, dict(_IDENT))
        check('  the aggregate produces ZERO room rows', out == [],
              f'{len(out)} row(s)')
        check('  and exactly one named refusal instead of silence',
              len(refused) == 1
              and refused[0]['code'] == PG.ROOM_MEMBER_UNRESOLVED,
              str([r['code'] for r in refused]))
        check('  the refusal carries a human-readable reason',
              bool(refused and refused[0].get('detail')))
        # NOT VACUOUS: the untouched copy composes.
        clean = _copy_seal(rec, tempfile.mkdtemp())
        check('  while the same seal untouched still composes',
              PG.pregame_room_membership(clean, man, 'qb').state is State.PASS)
        shutil.rmtree(clean, ignore_errors=True)


def test_e_two_pregame_sources_disagreeing_is_a_named_refusal():
    print('\n-- e. no precedence rule silently breaks a tie --')
    rec, man, rows = _pick()
    if rec is None:
        check('a sealed forecast with a stored outcome exists', False)
        return
    ids = ((man.get('layers') or {}).get('qb') or {}).get('row_ids') or []
    victim = ids[0]
    with tempfile.TemporaryDirectory() as td:
        dst = _copy_seal(rec, td)
        base = PG.pregame_room_membership(dst, man, layer='qb')
        check('the copy composes before the sabotage',
              base.state is State.PASS, base.code)
        if base.state is not State.PASS:
            return
        real_team = base.value['membership'][victim]
        other = next(t for t in set(base.value['membership'].values())
                     if t != real_team)
        dc = {f'{other}|QB|9': victim}
        p = dst / 'SEALED_FORECAST.json'
        doc = json.loads(p.read_text()) if p.exists() else {}
        doc['depth_chart'] = dict(doc.get('depth_chart') or {}, **dc)
        p.write_text(json.dumps(doc))
        o = PG.pregame_room_membership(dst, man, layer='qb')
        check('a two-source disagreement refuses',
              o.state is State.BLOCKED, f'{o.state.name}[{o.code}]')
        check('  under its own code, distinct from the unresolved one',
              o.code == PG.ROOM_MEMBERSHIP_CONFLICT
              and PG.ROOM_MEMBERSHIP_CONFLICT != PG.ROOM_MEMBER_UNRESOLVED,
              o.code)
        conflicted = [c['gsis_id'] for c in (o.evidence.get('conflicts') or [])]
        check('  and names the disputed member and both claimants',
              victim in conflicted
              and {real_team, other} <= set(
                  (o.evidence['conflicts'][0]['claims'] or {}).keys()),
              str(o.evidence.get('conflicts'))[:200])


# --------------------------------------------------------------- f
def test_f_a_team_code_that_does_not_join_is_named_not_dropped():
    print('\n-- f. the silent `continue` on a team-code join failure --')
    rec, man, rows = _pick()
    if rec is None:
        check('a sealed forecast with a stored outcome exists', False)
        return
    t_ids = ((man.get('layers') or {}).get('team_volume') or {}).get(
        'row_ids') or []
    check('the fixture carries sealed team rows', bool(t_ids), str(t_ids))
    if not t_ids:
        return
    # Rename every posteam so NO sealed team code joins. Under the old code
    # this deleted every team row and reported success.
    broken = [dict(r, posteam=('ZZZ' if r.get('posteam') else r.get('posteam')))
              for r in rows]

    # SCAFFOLD, DECLARED: `score_game` refuses every real seal today on
    # CURRENT-CONTRACT ADMISSIBILITY (WS22 section 3), so the refusal under
    # test is unreachable without standing that gate down for this call. The
    # gate is restored in `finally` and nothing is written anywhere.
    original = PG.REUSE.assert_currently_admissible
    try:
        PG.REUSE.assert_currently_admissible = lambda _a: Outcome.ok(
            'TEST_SCAFFOLD_ADMISSIBILITY_STOOD_DOWN',
            detail='test-local only; restored immediately after this call',
            value={'scaffold': True})
        fin = PG.game_finality(broken)
        o = PG.score_game(dict(rec), broken, 'f' * 64, finality=fin)
        check('the game still scores rather than raising',
              o.state in (State.PASS, State.BLOCKED, State.DEFERRED),
              f'{o.state.name}[{o.code}]')
        if o.state is not State.PASS:
            check('  (scoring reached the estimand loop)', False, o.code)
            return
        refused = o.value['refused']
        codes = {r['code'] for r in refused}
        check('  an unjoinable team code is refused BY NAME',
              PG.TEAM_CODE_UNJOINED in codes, str(sorted(codes))[:300])
        named = [r for r in refused if r['code'] == PG.TEAM_CODE_UNJOINED]
        check('    once per sealed team row and metric',
              {r['team'] for r in named} == set(t_ids),
              str(sorted({r['team'] for r in named})))
        check('    and the refusal shows what the outcome DID carry',
              all('ZZZ' in (r.get('realised_team_codes') or []) for r in named))
        check('  no team row is scored on a code that did not join',
              not any(r.get('entity') == 'team' for r in o.value['scored']))

        # NOT VACUOUS: on the real outcome the same codes join and score.
        fin2 = PG.game_finality(rows)
        o2 = PG.score_game(dict(rec), rows, 'f' * 64, finality=fin2)
        check('  while the UNMUTATED outcome joins and scores team rows',
              o2.state is State.PASS
              and any(r.get('entity') == 'team' for r in o2.value['scored']),
              f'{o2.state.name}[{o2.code}]')
        check('    with no unjoined-team refusal at all',
              PG.TEAM_CODE_UNJOINED not in {
                  r['code'] for r in o2.value['refused']})
        check('  the two refusal causes are distinct codes',
              PG.TEAM_CODE_UNJOINED != PG.TEAM_NO_FORECAST)
    finally:
        PG.REUSE.assert_currently_admissible = original
    check('the admissibility gate is restored',
          PG.REUSE.assert_currently_admissible is original)


# --------------------------------------------------------------- g
def test_g_the_old_composer_is_gone_from_the_composition_path():
    print('\n-- g. the defect cannot come back by editing one line --')
    src = inspect.getsource(PG.qb_room_aggregate)
    check('the aggregate composes from pregame_room_membership',
          'pregame_room_membership' in src)
    check('  and never keys a room on a realised team',
          "_team_of(rows, pid) or 'UNKNOWN'" not in src)
    check("  and no 'UNKNOWN' bucket survives to be skipped",
          "== 'UNKNOWN'" not in src)
    check('the aggregate returns refusals beside rows',
          len(inspect.signature(PG.qb_room_aggregate).parameters) == 6)
    rec, man, rows = _pick()
    if rec is None:
        return
    draws = SI.load_draws(pathlib.Path(rec['dir']))
    got = PG.qb_room_aggregate(dict(rec), man, draws,
                               ACT.qb_actuals(rows), rows, dict(_IDENT))
    check('  as a 2-tuple, so a refusal cannot be dropped by the caller',
          isinstance(got, tuple) and len(got) == 2)
    caller = inspect.getsource(PG.score_game)
    check('  and score_game extends `refused` with them',
          'refused.extend(agg_refused)' in caller)


def main():
    for fn in (test_a_zero_attempt_quarterback_stays_in_the_room,
               test_b_composition_cannot_see_the_outcome,
               test_c_the_room_reconstructs_from_sealed_bytes_alone,
               test_d_an_unresolvable_member_refuses_the_room_by_name,
               test_e_two_pregame_sources_disagreeing_is_a_named_refusal,
               test_f_a_team_code_that_does_not_join_is_named_not_dropped,
               test_g_the_old_composer_is_gone_from_the_composition_path):
        fn()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
