"""classic_finalize: FINAL files exist only for a fully gated post-news run, and never for a rehearsal."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_finalize as F   # noqa: E402
from nfl.tests._controls import observe       # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


HEAD = 'Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST'


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _world(td, oi_state='APPLIED_OWNER_RELAYED', prelock='NO_RERUN_REQUIRED', repro='PASS', lists=('A', 'H')):
    d = pathlib.Path(td)
    w = lambda n, v: (d / f'DK_T_EARLY_{n}').write_text(v if isinstance(v, str) else json.dumps(v))  # noqa: E731
    F.EARLY_ONLY_GAMES['T'] = frozenset({('A', 'H')})
    w('STATE.json', {'built_at_utc': '2026-10-04T14:40:00+00:00', 'games': {'G': {'away': 'A', 'home': 'H'}},
                     'kickoff': '10/04/2026 01:00PM ET',
                     'players': {str(i): {'name': f'P{i}', 'team': 'A', 'game_id': 'G'} for i in range(1, 10)},
                     'official_inactives': {'STATE': oi_state, 'packet_id': 'pk', 'source': 'OWNER_RELAYED',
                                            'clubs_with_full_list': lists}})
    w('PROJ.json', {'rows': {}})
    (d / 'DK_T_EARLY_WORLDS.npz').write_bytes(b'worlds')
    w('DRAWS.json', {'d': 1})
    rows = [HEAD] + [f'{i},c,{cid},$1,1,2,3,4,5,6,7,8,9' for cid, n in (('1', 150), ('2', 20), ('3', 3)) for i in range(n)]
    w('UPLOAD.csv', '\n'.join(rows) + '\n')
    contests = [{'profile': p, 'contest_id': c, 'n_entries': n, 'FILLED': True,
                 'lineups': [{'entry_id': str(i), 'slots': [{'dk_id': '1', 'name': 'P1'}]} for i in range(n)],
                 'report': {'game_exposure': {'G': 1.0}}}
                for p, c, n in (('MAX150', '1', 150), ('MAX20', '2', 20), ('MAX3', '3', 3))]
    inputs = {k: str(d / f'DK_T_EARLY_{n}') for k, n in (('state', 'STATE.json'), ('proj', 'PROJ.json'), ('draws', 'DRAWS.json'))}
    w('PORTFOLIOS.json', {'built_at_utc': '2026-10-04T14:50:00+00:00', 'inputs': inputs,
                          'inputs_sha256': {k: _sha(pathlib.Path(v)) for k, v in inputs.items()}, 'contests': contests})
    w('SEAL.json', {'projection_sha256': _sha(d / 'DK_T_EARLY_PROJ.json'), 'worlds_sha256': _sha(d / 'DK_T_EARLY_WORLDS.npz')})
    w('UPLOAD_VERIFY.json', {'state': 'PASS', 'code': 'UPLOAD_VERIFIED', 'upload_sha256': _sha(d / 'DK_T_EARLY_UPLOAD.csv')})
    w('AUDIT.json', {'built_at_utc': '2026-10-04T14:55:00+00:00', 'accounting': {'state': 'PASS'},
                     'reproducibility': {'state': repro}})
    w('PRELOCK.json', {'state': 'PASS' if prelock == 'NO_RERUN_REQUIRED' else 'FAIL', 'code': prelock,
                       'checked_at_utc': '2026-10-04T14:56:00+00:00'})
    return d


def test_01_a_gated_owner_relayed_run_finalizes_and_says_so():
    d = _world(tempfile.mkdtemp())
    o = F.finalize('T', d)
    check('negative control: every gate passes -> FINAL populated', o.state.value == 'PASS', f'{o.code} {o.detail}')
    man = json.loads((d / 'DK_T_EARLY_FINAL_MANIFEST.json').read_text())
    check('  labelled owner-relayed, never official', man['STATE'] == 'FINAL_POST_INACTIVES_OWNER_RELAYED_NOT_OFFICIAL', man['STATE'])
    n = {k: len((d / f'DK_T_EARLY_{v}').read_text().splitlines()) - 1 for k, v in F.PROFILE_FILE.items()}
    check('  each contest file holds exactly its own entries', n == {'MAX150': 150, 'MAX20': 20, 'MAX3': 3}, n)
    check('  the FINAL upload is byte-identical to the verified upload',
          _sha(d / 'DK_T_EARLY_FINAL_DK_UPLOAD_POST_INACTIVES.csv') == _sha(d / 'DK_T_EARLY_UPLOAD.csv'))


def test_02_rehearsal_and_awaiting_never_finalize():
    for st in ('REHEARSAL_NOT_EVIDENCE', 'AWAITING_OFFICIAL_INACTIVES', 'APPLIED_NAME_LIST_NOT_CAPTURED'):
        d = _world(tempfile.mkdtemp(), oi_state=st)
        o = F.finalize('T', d)
        if st == 'REHEARSAL_NOT_EVIDENCE':
            observe('nfl.tools.classic_finalize:finalize:FINAL_NOT_POPULATED', o)
        check(f'positive control: {st} -> NOT_POPULATED on the EVIDENCE gate',
              o.code == 'FINAL_NOT_POPULATED' and 'EVIDENCE' in o.evidence['failed']
              and not (d / 'DK_T_EARLY_FINAL_DK_UPLOAD_POST_INACTIVES.csv').exists(), o.detail)


def test_03_each_chain_gate_refuses():
    d = _world(tempfile.mkdtemp(), prelock='RERUN_REQUIRED')
    check('positive control: prelock still wants a rerun -> refused', 'PRELOCK' in F.finalize('T', d).evidence['failed'])
    d = _world(tempfile.mkdtemp(), repro='STALE')
    check('positive control: stale reproducibility -> refused', 'AUDIT' in F.finalize('T', d).evidence['failed'])
    d = _world(tempfile.mkdtemp())
    (d / 'DK_T_EARLY_PROJ.json').write_text('{"rows": {"x": 1}}')
    f = F.finalize('T', d).evidence['failed']
    check('positive control: projection changed after the seal and the portfolio -> refused on both',
          {'SEAL_COVERS_CURRENT_FORECAST', 'PORTFOLIO_ON_CURRENT_INPUTS'} <= set(f), f)
    d = _world(tempfile.mkdtemp())
    (d / 'DK_T_EARLY_UPLOAD.csv').write_text(HEAD + '\n')
    check('positive control: upload edited after verification -> refused',
          'UPLOAD_VERIFIED' in F.finalize('T', d).evidence['failed'])


def test_03b_a_club_without_its_list_refuses():
    d = _world(tempfile.mkdtemp(), lists=('A',))
    o = F.finalize('T', d)
    check('positive control: one club has no game-day list -> refused on EVERY_CLUB_HAS_ITS_INACTIVE_LIST',
          'EVERY_CLUB_HAS_ITS_INACTIVE_LIST' in o.evidence['failed'], o.detail)


def test_03c_anything_outside_the_early_only_games_refuses():
    d = _world(tempfile.mkdtemp())
    st = json.loads((d / 'DK_T_EARLY_STATE.json').read_text())
    st['players']['99'] = {'name': 'Late Game Star', 'team': 'KC', 'game_id': 'G_LATE'}
    (d / 'DK_T_EARLY_STATE.json').write_text(json.dumps(st))
    po = json.loads((d / 'DK_T_EARLY_PORTFOLIOS.json').read_text())
    po['contests'][2]['lineups'][0]['slots'].append({'dk_id': '99', 'name': 'Late Game Star'})
    (d / 'DK_T_EARLY_PORTFOLIOS.json').write_text(json.dumps(po))
    o = F.finalize('T', d)
    g = json.loads((d / 'DK_T_EARLY_FINAL_MANIFEST.json').read_text())['gates']['SCOPE_EARLY_ONLY_1PM']
    check('positive control: a 4 PM player in the pool and in a 3-entry lineup -> refused on SCOPE_EARLY_ONLY_1PM',
          'SCOPE_EARLY_ONLY_1PM' in o.evidence['failed'] and any('Late Game Star' in v for v in g['violations']), g)
    d = _world(tempfile.mkdtemp())
    st = json.loads((d / 'DK_T_EARLY_STATE.json').read_text())
    st['games']['G2'] = {'away': 'KC', 'home': 'LV'}
    (d / 'DK_T_EARLY_STATE.json').write_text(json.dumps(st))
    check('positive control: a ninth game in the state -> refused', 'SCOPE_EARLY_ONLY_1PM' in F.finalize('T', d).evidence['failed'])
    d = _world(tempfile.mkdtemp())
    (d / 'DK_T_EARLY_HARD_ROCK_SLOTS.json').write_text(json.dumps({'rows': [{'team': 'KC', 'player': 'X'}]}))
    check('positive control: a Hard Rock row for a non-Early club -> refused', 'SCOPE_EARLY_ONLY_1PM' in F.finalize('T', d).evidence['failed'])


def test_04_a_stale_final_is_moved_aside():
    d = _world(tempfile.mkdtemp())
    F.finalize('T', d)
    p = json.loads((d / 'DK_T_EARLY_PRELOCK.json').read_text())
    p.update(state='FAIL', code='RERUN_REQUIRED')
    (d / 'DK_T_EARLY_PRELOCK.json').write_text(json.dumps(p))
    o = F.finalize('T', d)
    man = json.loads((d / 'DK_T_EARLY_FINAL_MANIFEST.json').read_text())
    check('positive control: a later refused run leaves no FINAL file beside it',
          o.code == 'FINAL_NOT_POPULATED' and not any((d / f'DK_T_EARLY_{n}').exists()
                                                      for n in (*F.PROFILE_FILE.values(), F.UPLOAD_FILE)))
    check('  and the old FINALs are kept (moved, not deleted)', len(man['moved_aside']) == 4
          and all(pathlib.Path(x).exists() for x in man['moved_aside']), man.get('moved_aside'))


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
