"""Directive 7 §9 -- sixteen requirements for the event-targeted capture path.

WHAT CHANGED, AND WHY THE PREVIOUS VERSION WAS WRONG

`attribution.claims_for` computed a capture's target set from `retrieved_at`,
which exists only after the bytes arrive. Directive 7 §6: "Do not infer the
target set after the fact from timestamps alone." Every claim it made was a
post-hoc reading of a clock, and a capture that wandered into a window by
accident was indistinguishable from one taken because the window was open.

So intent is now DECLARED before the fetch and the bytes are judged against it.
Sections A-P below are §9's sixteen requirements in order; section Q is the
guard-deletion proof for the game-attribution control.

Run standalone:  python3.12 nfl/tests/test_execution_target.py
"""
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import execution as X  # noqa: E402
from nfl.capture.coverage import coverage, load_week_plan  # noqa: E402
from nfl.capture.execution import (BASIS_ANCHORED, BASIS_LOCAL,  # noqa: E402
                                   BASIS_OPERATOR, BASIS_SWEEP,
                                   DISCHARGING_BASES, LEAGUE_WIDE, declare,
                                   declaration_basis, eligibility,
                                   eligible_targets)
from sportsplatform.governance.outcome import State  # noqa: E402

GAME = '2026_01_NE_SEA'
PASSED = FAILED = 0
_PLAN = None


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def plan():
    global _PLAN
    if _PLAN is None:
        _PLAN = load_week_plan(2026, 1).value
    return _PLAN


def target(game_id=GAME, kind='inactives'):
    return next(c for c in plan() if c.kind == kind and c.game_id == game_id)


ANCHORED = {'is_github_actions': True, 'workflow': X.ANCHORED_WORKFLOW,
            'event_name': 'schedule', 'run_id': '34076132045',
            'run_attempt': '1', 'repository': '94924676jp-a11y/Nfl'}

# A real durable artifact, so persistence and hash checks are exercised against
# bytes that exist rather than against a fixture.
BLOB = 'nfl/vintage/official_inactives.910454a5e1e59ee3.html.gz'
SHA = hashlib.sha256(gzip.open(_REPO / BLOB, 'rb').read()).hexdigest()


def _decl(at=None, ident=None, pl=None):
    t = target()
    return declare(pl if pl is not None else plan(),
                   declared_at=at or (t.window[0] + dt.timedelta(minutes=5)),
                   identity=ident or ANCHORED).value


def _elig(decl, *, source='official_inactives', state='PASS', at=None,
          sha=SHA, blob=BLOB, prov=True):
    t = target()
    return eligibility(decl, source=source, capture_state=state,
                       retrieved_at=(at or (t.window[0] +
                                            dt.timedelta(minutes=6))).isoformat()
                       if not isinstance(at, str) else at,
                       sha256=sha, blob_path=blob, provenance_valid=prov)


def _row(decl, elig, at, source='official_inactives', state='PASS'):
    return {'capture_id': 'x', 'season': 2026, 'source': source,
            'state': state, 'code': 'CAPTURED',
            'value': {'provenance': {'retrieved_at': at},
                      'blob': BLOB, 'sha256': SHA,
                      'execution_target': decl, 'discharge_eligibility': elig}}


def _ia(elig, game_id=GAME):
    """The inactives entry for one game. Index 0 is whatever the plan sorted
    first, which is usually a practice target and refuses for a different
    reason -- asserting on it tests the wrong thing."""
    return next(x for x in elig['targets']
                if x['kind'] == 'inactives' and x['game_id'] == game_id)


def _manifest(rows):
    fh = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    for r in rows:
        fh.write(json.dumps(r) + '\n')
    fh.close()
    return pathlib.Path(fh.name)


def _covers(rows, game=GAME):
    t = target(game)
    o = coverage(2026, 1, manifest_path=_manifest(rows),
                 now=t.window[1] + dt.timedelta(minutes=1))
    return not any(m['kind'] == 'inactives' and m['game_id'] == game
                   for m in o.evidence.get('missed_detail', []))


def _happy(at_offset=6):
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=at_offset)).isoformat()
    d = _decl()
    return [_row(d, _elig(d, at=at), at)]


# --------------------------------------------------------------------------
def test_A_1_target_carries_the_exact_game_id():
    print('\nA. §9.1 -- the declared target carries the exact game id')
    d = _decl()
    ids = {t['game_id'] for t in d['targets']}
    check('the declaration names games, not a count', GAME in ids, str(ids)[:90])
    ia = [t for t in d['targets'] if t['kind'] == 'inactives']
    check('exactly one inactives target is open at NE@SEA T-85',
          [t['game_id'] for t in ia] == [GAME], str(ia)[:110])
    t = ia[0]
    check('it carries the window it belongs to', t['window_start_utc']
          == target().window[0].isoformat())
    check('and the kickoff, which for a practice target is NOT recoverable '
          'from due_utc',
          t['kickoff_utc'] == '2026-09-10T00:20:00+00:00', str(t['kickoff_utc']))
    check('the declaration is marked as made before any fetch',
          d['declared_before_fetch'] is True)
    check('and carries the run identity that made it',
          d['executor']['run_id'] == '34076132045')


def test_B_2_before_the_window():
    print('\nB. §9.2 -- a capture before the window does not cover')
    t = target()
    at = (t.window[0] - dt.timedelta(minutes=5)).isoformat()
    d = _decl(at=t.window[0] - dt.timedelta(minutes=6))
    check('nothing is even declared before the window opens',
          not [x for x in d['targets'] if x['kind'] == 'inactives'])
    d2 = _decl()
    check('and bytes arriving before the declared window are refused',
          not _covers([_row(d2, _elig(d2, at=at), at)]))
    e = _elig(d2, at=at)
    check('the refusal is named, not silent',
          'RETRIEVED_AT_OUTSIDE_DECLARED_WINDOW' in _ia(e)['refusals'],
          str(_ia(e)['refusals']))


def test_C_3_after_the_window():
    print('\nC. §9.3 -- a capture after the window does not cover')
    t = target()
    for label, at in [('one second after T-10',
                       t.window[1] + dt.timedelta(seconds=1)),
                      ('after kickoff', t.window[1] + dt.timedelta(hours=2))]:
        d = _decl()
        check(f'{label} -> not covered',
              not _covers([_row(d, _elig(d, at=at.isoformat()),
                                at.isoformat())]))


def test_D_4_wrong_game():
    print('\nD. §9.4 -- in-window for the WRONG game does not cover this one')
    other = target('2026_01_DEN_KC')
    at = (other.window[0] + dt.timedelta(minutes=5))
    d = declare(plan(), declared_at=at, identity=ANCHORED).value
    ids = {x['game_id'] for x in d['targets'] if x['kind'] == 'inactives'}
    check('the DEN@KC window declares DEN@KC, not NE@SEA',
          ids == {'2026_01_DEN_KC'}, str(ids))
    e = eligibility(d, source='official_inactives', capture_state='PASS',
                    retrieved_at=at.isoformat(), sha256=SHA, blob_path=BLOB,
                    provenance_valid=True)
    check('and NE@SEA is not covered by it',
          not _covers([_row(d, e, at.isoformat())]))


def test_E_5_unattributed():
    print('\nE. §9.5 -- an unattributed capture does not cover')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    row = _row(_decl(), {'targets': [], 'n_eligible': 0}, at)
    check('no eligible target -> not covered', not _covers([row]))
    row2 = _row(None, None, at)
    check('no declaration at all -> not covered', not _covers([row2]))
    check('and a row with neither field reports no eligible targets',
          eligible_targets(row2['value']) == [])


def test_F_6_generic_source_level_pass():
    print('\nF. §9.6 -- a generic source-level PASS does not cover')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    d = _decl(ident=dict(ANCHORED, workflow='NFL vintage capture'))
    check('the baseline sweep is classified as a sweep',
          d['basis'] == BASIS_SWEEP, d['basis'])
    check('a sweep declares can_discharge False',
          d['basis_can_discharge'] is False)
    e = _elig(d, at=at)
    check('its in-window capture is refused with a named basis reason',
          any(r.startswith('BASIS_CANNOT_DISCHARGE')
              for r in _ia(e)['refusals']), str(_ia(e)['refusals']))
    check('and it does not cover -- §5, a generic background capture does not '
          'discharge',
          not _covers([_row(d, e, at)]))
    check('a manual dispatch of the anchored workflow is also refused: §11 '
          'says it is not equivalent proof',
          not _covers([_row(
              _decl(ident=dict(ANCHORED, event_name='workflow_dispatch')),
              _elig(_decl(ident=dict(ANCHORED,
                                     event_name='workflow_dispatch')), at=at),
              at)]))
    check('only the anchored scheduled basis can discharge at all',
          DISCHARGING_BASES == (BASIS_ANCHORED,), str(DISCHARGING_BASES))


def test_G_7_the_honest_case_does_cover():
    print('\nG. §9.7 -- an event-targeted PASS inside the window CAN cover')
    check('it covers', _covers(_happy()))
    d = _decl()
    e = _elig(d)
    ia = _ia(e)
    check('exactly one target is eligible, not every declared one',
          e['n_eligible'] == 1, str(e['n_eligible']))
    check('and it is the right one, with no refusals',
          ia['game_id'] == GAME and ia['refusals'] == [], str(ia)[:110])


def test_H_8_blocked_in_window():
    print('\nH. §9.8 -- BLOCKED inside the correct window does not cover')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    for state in ('BLOCKED', 'FAIL', 'DEFERRED', 'NOT_APPLICABLE'):
        d = _decl()
        e = _elig(d, state=state, at=at)
        check(f'{state} in-window -> refused',
              f'CAPTURE_NOT_PASS:{state}' in _ia(e)['refusals'],
              str(_ia(e)['refusals'])[:90])
        row = _row(d, e, at, state=state)
        check(f'{state} in-window -> not covered', not _covers([row]))


def test_I_9_persistence_failure():
    print('\nI. §9.9 -- a raw persistence failure prevents coverage')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    d = _decl()
    e = _elig(d, blob=None)
    check('no blob path -> refused at eligibility',
          'RAW_ARTIFACT_NOT_PERSISTED' in _ia(e)['refusals'])
    check('and not covered', not _covers([_row(d, e, at)]))

    # The harder case: eligibility says fine, but the file is not on disk.
    good = _elig(d)
    row = _row(d, good, at)
    row['value']['blob'] = 'nfl/vintage/does_not_exist.html.gz'
    check('a row CLAIMING an artifact that is not on disk is refused by '
          'coverage, which opens the file rather than trusting the row',
          not _covers([row]))


def test_J_10_invalid_provenance():
    print('\nJ. §9.10 -- invalid provenance prevents coverage')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    d = _decl()
    e = _elig(d, prov=False)
    check('provenance marked invalid -> refused',
          'PROVENANCE_INVALID' in _ia(e)['refusals'])
    check('and not covered', not _covers([_row(d, e, at)]))
    e2 = _elig(d, at='not-a-timestamp')
    check('an unreadable retrieval clock -> refused',
          'RETRIEVED_AT_UNREADABLE' in _ia(e2)['refusals'])


def test_K_11_incorrect_raw_hash():
    print('\nK. §9.11 -- an incorrect raw hash prevents coverage')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    d = _decl()
    check('a malformed hash is refused at eligibility',
          'RAW_SHA256_ABSENT_OR_MALFORMED'
          in _ia(_elig(d, sha='abc'))['refusals'])
    row = _row(d, _elig(d), at)
    row['value']['sha256'] = 'f' * 64
    check('a well-formed hash that does not match the bytes is caught when '
          'coverage rehashes the artifact',
          not _covers([row]))
    check('and the honest row still covers, so this is not a blanket refusal',
          _covers(_happy()))


def test_L_12_no_silent_multi_game_credit():
    print('\nL. §9.12 -- one capture cannot silently cover unrelated games')
    sunday = target('2026_01_CHI_CAR')
    at = sunday.window[0] + dt.timedelta(minutes=5)
    d = declare(plan(), declared_at=at, identity=ANCHORED).value
    ia = {x['game_id'] for x in d['targets'] if x['kind'] == 'inactives'}
    check('the 15:30Z window genuinely holds 8 simultaneous games',
          len(ia) == 8, str(len(ia)))
    check('NE@SEA is NOT among them -- its window closed days earlier',
          GAME not in ia)
    e = eligibility(d, source='official_inactives', capture_state='PASS',
                    retrieved_at=at.isoformat(), sha256=SHA, blob_path=BLOB,
                    provenance_valid=True)
    rows = [_row(d, e, at.isoformat())]
    check('and this capture does not cover NE@SEA', not _covers(rows, GAME))
    check('while it does cover a game it actually declared',
          _covers(rows, '2026_01_CHI_CAR'))


def test_M_13_declared_multi_target_covers_only_the_declared():
    print('\nM. §9.13 -- a multi-target capture covers only its declared set')
    sunday = target('2026_01_CHI_CAR')
    at = sunday.window[0] + dt.timedelta(minutes=5)
    d = declare(plan(), declared_at=at, identity=ANCHORED).value
    e = eligibility(d, source='official_inactives', capture_state='PASS',
                    retrieved_at=at.isoformat(), sha256=SHA, blob_path=BLOB,
                    provenance_valid=True)
    check('all 8 declared inactives targets are eligible together -- one page '
          'legitimately serves a shared window',
          sum(1 for x in e['targets']
              if x['kind'] == 'inactives' and x['eligible']) == 8)
    rows = [_row(d, e, at.isoformat())]
    covered = [g for g in ('2026_01_CHI_CAR', '2026_01_TB_CIN',
                           '2026_01_ATL_PIT') if _covers(rows, g)]
    check('each declared game is covered', len(covered) == 3, str(covered))
    for undeclared in ('2026_01_ARI_LAC', '2026_01_DAL_NYG',
                       '2026_01_DEN_KC'):
        check(f'{undeclared} (a LATER window the same day) is not covered',
              not _covers(rows, undeclared))
    check('the relationship is explicit -- the target set is listed on the row',
          len(d['targets']) > 0 and 'game_id' in d['targets'][0])


def test_N_14_attempting_is_not_completing():
    print('\nN. §9.14 -- the scheduler cannot claim completion by attempting')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    d = _decl()
    check('a declaration alone names targets', len(d['targets']) > 0)
    check('but declares itself non-discharging in words',
          'discharges nothing on its own' in d['note'])
    e = _elig(d, state='BLOCKED', at=None)
    row = _row(d, e, at, state='BLOCKED')
    check('a run that declared the target and then failed covers nothing',
          not _covers([row]))
    check('and the attempt is still on the record rather than vanishing',
          row['value']['execution_target']['targets'][0]['game_id'] is not None)


def test_O_15_target_stays_open_without_durable_evidence():
    print('\nO. §9.15 -- the target stays open until durable evidence exists')
    check('with no captures at all it is open',
          not _covers([]))
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()
    d = _decl()
    row = _row(d, _elig(d), at)
    row['value']['blob'] = None
    check('with a perfect declaration but no persisted artifact it is open',
          not _covers([row]))
    check('and it closes only once the artifact is really there and hashes',
          _covers(_happy()))


def test_P_16_reproducible_from_artifacts_alone():
    print('\nP. §9.16 -- coverage is reproducible from manifest + artifacts')
    rows = _happy()
    m = _manifest(rows)
    t = target()
    now = t.window[1] + dt.timedelta(minutes=1)
    a = coverage(2026, 1, manifest_path=m, now=now)
    b = coverage(2026, 1, manifest_path=m, now=now)
    check('two runs over the same files agree exactly',
          a.evidence['covered'] == b.evidence['covered']
          and a.code == b.code)
    check('and it says whether it verified the artifacts',
          a.evidence['artifacts_verified'] is True)
    check('the artifact really was read from disk, not taken on trust',
          (_REPO / BLOB).exists())
    off = coverage(2026, 1, manifest_path=m, now=now, verify_artifacts=False)
    check('the verification is a real gate: turning it off is a different, '
          'weaker computation and says so',
          off.evidence['artifacts_verified'] is False)
    check('legacy pre-Directive-7 claim rows are counted and discharge nothing',
          'legacy_claim_rows' in coverage(
              2026, 1, manifest_path=_REPO / 'nfl' / 'vintage_manifest.jsonl'
          ).evidence)


def test_Q_the_attribution_control_is_load_bearing():
    print('\nQ. guard-deletion -- what is refusing the sweep and the wrong game?')
    t = target()
    at = (t.window[0] + dt.timedelta(minutes=6)).isoformat()

    # 1. the basis gate
    d = _decl(ident=dict(ANCHORED, workflow='NFL vintage capture'))
    check('with the guard: a sweep covers nothing',
          not _covers([_row(d, _elig(d, at=at), at)]))
    original = X.DISCHARGING_BASES
    try:
        X.DISCHARGING_BASES = (BASIS_ANCHORED, BASIS_SWEEP, BASIS_OPERATOR,
                               BASIS_LOCAL)
        loose = _elig(d, at=at)
    finally:
        X.DISCHARGING_BASES = original
    check('bypassed, the SAME sweep capture becomes eligible -- so the basis '
          'gate is what refused it',
          loose['n_eligible'] > 0, str(loose['n_eligible']))
    print(f'       [bypassed: sweep claims {loose["n_eligible"]} target(s)]')

    # 2. The game-attribution gate inside coverage. This needs two games whose
    #    windows OVERLAP. The first version of this section used two games four
    #    days apart, so timing alone already refused and bypassing the
    #    attribution guard changed nothing -- the test proved nothing and said
    #    it proved attribution. Eight games share the 15:30Z Sunday window, so
    #    declare exactly one of them and ask about another.
    chi = target('2026_01_CHI_CAR')
    oat = chi.window[0] + dt.timedelta(minutes=5)
    full = declare(plan(), declared_at=oat, identity=ANCHORED).value
    d2 = dict(full, targets=[t for t in full['targets']
                             if t['game_id'] == '2026_01_CHI_CAR'
                             and t['kind'] == 'inactives'])
    check('the two games really do share one window',
          target('2026_01_TB_CIN').window == chi.window)
    check('and only CHI@CAR was declared',
          [t['game_id'] for t in d2['targets']] == ['2026_01_CHI_CAR'])
    e2 = eligibility(d2, source='official_inactives', capture_state='PASS',
                     retrieved_at=oat.isoformat(), sha256=SHA, blob_path=BLOB,
                     provenance_valid=True)
    rows = [_row(d2, e2, oat.isoformat())]
    check('with the guard: a capture declared only for CHI@CAR does not cover '
          'TB@CIN in the same window',
          not _covers(rows, '2026_01_TB_CIN'))
    check('while it does cover the game it declared',
          _covers(rows, '2026_01_CHI_CAR'))
    import nfl.capture.schedule as S
    orig_clears = S._clears
    try:
        S._clears = lambda tg, p: tg.satisfied_by(
            p[0] if isinstance(p, tuple) else p)
        bypassed = _covers(rows, '2026_01_TB_CIN')
    finally:
        S._clears = orig_clears
    check('bypassed to a pure timing check, the same capture covers TB@CIN '
          'too -- so _clears is the game-attribution control',
          bypassed)
    check('and restoring it restores the refusal',
          not _covers(rows, '2026_01_TB_CIN'))

    # 3. the artifact verifier
    row = _row(_decl(), _elig(_decl()), at)
    row['value']['sha256'] = 'f' * 64
    check('with the guard: a wrong hash blocks coverage', not _covers([row]))
    o = coverage(2026, 1, manifest_path=_manifest([row]),
                 now=t.window[1] + dt.timedelta(minutes=1),
                 verify_artifacts=False)
    check('with verification off the same row covers -- so rehashing the '
          'artifact is what caught it',
          not any(m['kind'] == 'inactives' and m['game_id'] == GAME
                  for m in o.evidence['missed_detail']))


def test_R_the_four_scopes_stay_apart():
    print('\nR. §2 -- four scopes, not one field')
    d = _decl()
    e = _elig(d)
    check('the source artifact declares itself league-wide',
          e['source_artifact_scope'] == LEAGUE_WIDE)
    check('and says so in words, so a reader cannot take the page for a '
          'document about one game',
          'does not make the artifact that target' in e['scope_note'])
    check('execution target scope is a separate structure carrying the game',
          {'game_id', 'kind', 'window_start_utc'} <= set(d['targets'][0]))
    check('coverage obligation is computed, not stored as the same field',
          'eligible' in _ia(e) and 'refusals' in _ia(e))
    check('parsed-row applicability is not decided here at all',
          not any('player' in k or 'parsed' in k for k in e))
    check('an unknown workflow falls back to the non-discharging class',
          declaration_basis({'is_github_actions': True,
                             'workflow': 'something new',
                             'event_name': 'schedule'}) == BASIS_SWEEP)
    check('and a local run is never a discharging basis',
          declaration_basis({'is_github_actions': False}) == BASIS_LOCAL
          and BASIS_LOCAL not in DISCHARGING_BASES)


def test_S_declaration_refuses_without_a_plan():
    print('\nS. an execution that cannot name its target says so')
    o = declare([], identity=ANCHORED)
    check('no plan -> BLOCKED', o.state is State.BLOCKED
          and o.code == 'DECLARATION_NO_PLAN', str(o)[:110])
    check('and it says an unnamed execution must not count',
          'must not be recorded' in o.detail, o.detail[:90])
    quiet = declare(plan(), declared_at=dt.datetime(2026, 1, 1,
                                                    tzinfo=dt.timezone.utc),
                    identity=ANCHORED)
    check('a genuinely quiet moment is PASS with an empty target list',
          quiet.state is State.PASS and quiet.value['targets'] == [])


if __name__ == '__main__':
    for fn in (test_A_1_target_carries_the_exact_game_id,
               test_B_2_before_the_window, test_C_3_after_the_window,
               test_D_4_wrong_game, test_E_5_unattributed,
               test_F_6_generic_source_level_pass,
               test_G_7_the_honest_case_does_cover, test_H_8_blocked_in_window,
               test_I_9_persistence_failure, test_J_10_invalid_provenance,
               test_K_11_incorrect_raw_hash,
               test_L_12_no_silent_multi_game_credit,
               test_M_13_declared_multi_target_covers_only_the_declared,
               test_N_14_attempting_is_not_completing,
               test_O_15_target_stays_open_without_durable_evidence,
               test_P_16_reproducible_from_artifacts_alone,
               test_Q_the_attribution_control_is_load_bearing,
               test_R_the_four_scopes_stay_apart,
               test_S_declaration_refuses_without_a_plan):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
