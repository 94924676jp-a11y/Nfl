"""classic_prop_compare: sealed distributions against Hard Rock, in order, read from stored worlds."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_prop_compare as C   # noqa: E402
from nfl.tools import classic_slate_run as R      # noqa: E402
from nfl.tests._controls import observe           # noqa: E402

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


HDR = 'market,selection,points,is_main,over,under,price,ts_utc,age_min,flag,over_id,under_id,price_id,player_id,team_id'


def _card(name, pos, conf='HIGH', desig=None, starter=None, conflicts=()):
    return {'key': f'{name}|CIN', 'name': name, 'position': pos, 'role_types': [], 'projection': {'role_band': 'ALPHA'},
            'status': {'availability': 'UNKNOWN_ACTIVE_STATE', 'designation': desig, 'reported_starter': starter},
            'uncertainty': {'role_confidence': conf, 'conflicts': list(conflicts)}, 'measured_2026': {'games': 3}}


def _fixture(td):
    rng = np.random.default_rng(5)
    n = 2000
    worlds = {'Joe Burrow|CIN': [(38, max(0, 260 + 60 * rng.standard_normal()), 2, 2, 8, 0, 0, 0, 0, 0, 1) for _ in range(n)],
              "Ja'Marr Chase|CIN": [(0, 0, 0, 0, 0, 0, t, max(0, t - 3), max(0, 9.5 * t + 12 * rng.standard_normal()), 0, 0)
                                    for t in rng.integers(4, 16, n)],
              'Chase Brown|CIN': [(0, 0, 0, 15, 70, 1, 4, 3, 25, 0, 0)] * n}
    gw = {'2026_04_JAX_CIN': {'world_points': {'home': 'CIN', 'away': 'JAX',
                                               'points': [(24 + rng.normal(0, 9), 24 + rng.normal(0, 9)) for _ in range(n)]}}}
    R._write_worlds(td / 'DK_T_EARLY_WORLDS.npz', worlds, gw, 'projsha')
    yc = {'gap': 4.0, 'qbs_pass_yards': 260.0}
    book = {'ACCOUNTING': {'state': 'PASS'},
            'games': {'2026_04_JAX_CIN': {'away': 'JAX', 'home': 'CIN', 'teams': {'CIN': {
                'home': True, 'accounting': {'yards_closure_DIAGNOSTIC_NOT_A_GATE': yc}, 'players': [
                    _card('Joe Burrow', 'QB'), _card("Ja'Marr Chase", 'WR'), _card('Chase Brown', 'RB', conf='LOW')]}}}}}
    (td / 'DK_T_EARLY_RESEARCH_BOOK.json').write_text(json.dumps(book))
    (td / 'DK_T_EARLY_PROJ.json').write_text(json.dumps({'market_arm': 'FOOTBALL_ONLY'}))
    (td / 'DK_T_EARLY_STATE.json').write_text(json.dumps({'official_inactives': {'STATE': 'APPLIED'},
                                                           'injury_report': {'retrieved_at': ['2026-10-04T15:40:00Z']}}))
    sh = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    (td / 'DK_T_EARLY_SEAL.json').write_text(json.dumps({'projection_sha256': sh(td / 'DK_T_EARLY_PROJ.json'),
        'written_at': '2026-10-03T18:20:00+00:00', 'kickoff_utc': '2026-10-04T17:00:00+00:00',
        'worlds_sha256': sh(td / 'DK_T_EARLY_WORLDS.npz'), 'research_book_sha256': sh(td / 'DK_T_EARLY_RESEARCH_BOOK.json')}))
    b = td / 'HR_JAX_CIN_BOARD_2026-10-04T1500Z.csv'
    rows = [('player_passing_yards', 'Joe Burrow', '240.5', '-115', '-115', '2026-10-04T15:00:00+00:00'),
            ('player_receiving_yards', "Ja'Marr Chase", '120.5', '-110', '-110', '2026-10-04T15:00:00+00:00'),
            ('player_rushing_yards', 'Chase Brown', '50.5', '-115', '-115', '2026-10-04T15:00:00+00:00'),
            ('player_receptions', "Ja'Marr Chase", '6.5', '-120', '100', '2026-10-03T12:00:00+00:00'),
            ('player_longest_reception', "Ja'Marr Chase", '24.5', '-115', '-115', '2026-10-04T15:00:00+00:00'),
            ('player_receiving_yards', 'Nobody Here', '20.5', '-115', '-115', '2026-10-04T15:00:00+00:00')]
    lines = [HDR] + [f'{m},"{s}",{p},True,{o},{u},,{t},1,,{m}:{s}:o:{p},{m}:{s}:u:{p},,,' for m, s, p, o, u, t in rows]
    b.write_text('\n'.join(lines))
    return b


def test_01_no_vig_is_multiplicative():
    check('even prices de-vig to one half', abs(C.no_vig('-110', '-110') - 0.5) < 1e-12)
    p = C.no_vig('-150', '+130')
    check('  -150 / +130 -> 0.6 / (0.6 + 0.4348)', abs(p - 0.6 / (0.6 + 100 / 230)) < 1e-9, p)
    check('negative control: a one-sided price has no no-vig probability', C.no_vig('-110', '') is None)


def test_02_sealed_comparison_end_to_end():
    td = pathlib.Path(tempfile.mkdtemp())
    board = _fixture(td)
    old = C.OUT_DIR
    C.OUT_DIR = td
    try:
        o = C.compare('T', [str(board)])
        doc = json.loads((td / 'DK_T_EARLY_PROP_DIAGNOSTIC.json').read_text())
    finally:
        C.OUT_DIR = old
    check('positive control: comparable rows are measured', o.state.value == 'PASS', f'{o.code} {o.detail}')
    why = {(r.get('market'), r.get('player')): r['why'] for r in doc['refused']}
    check('  a price captured before the seal is refused by name',
          why.get(('player_receptions', "Ja'Marr Chase")) == 'PRICE_PREDATES_THE_SEAL', str(why))
    check('  a market the simulator does not draw is refused, not guessed',
          why.get(('player_longest_reception', "Ja'Marr Chase")) == 'MARKET_NOT_DRAWN_BY_THE_SIMULATOR')
    check('  an unknown player is refused', why.get(('player_receiving_yards', 'Nobody Here')) == 'PLAYER_NOT_MATCHED')
    rows = {(r['market'], r['player']): r for r in doc['rows']}
    r = rows[('player_passing_yards', 'Joe Burrow')]
    check('  P(over) + P(under) + P(push) = 1', abs(r['p_over'] + r['p_under'] + r['p_push'] - 1) < 1e-9)
    check('  P(over) is read from the worlds (about 0.63 for N(260, 60) over 240.5)', 0.57 < r['p_over'] < 0.69, r['p_over'])
    check('  the decomposition carries volume and efficiency', 'volume' in r['decomposition'] and 'efficiency' in r['decomposition'])
    lq = rows[('player_rushing_yards', 'Chase Brown')]
    check('negative control: a low-confidence player is never flagged for attention',
          lq['evidence_low_quality'] and not lq['ATTENTION'])
    check('  every row says it is not a recommendation', 'NOT_A_RECOMMENDATION' in doc)


def test_03_no_board_for_the_slate_is_blocked():
    td = pathlib.Path(tempfile.mkdtemp())
    _fixture(td)
    other = td / 'HR_NYG_LAR_BOARD_2026-09-21T2320Z.csv'
    other.write_text(HDR + '\n')
    old = C.OUT_DIR
    C.OUT_DIR = td
    try:
        o = C.compare('T', [str(other)])
    finally:
        C.OUT_DIR = old
    observe('nfl.tools.classic_prop_compare:compare:PROPS_NO_HARD_ROCK_BOARD', o)
    check('positive control: a board for another game leaves the slate with no board', o.code == 'PROPS_NO_HARD_ROCK_BOARD', o.code)


def _run(td, board):
    old = C.OUT_DIR
    C.OUT_DIR = td
    try:
        o = C.compare('T', [str(board)])
        return o, json.loads((td / 'DK_T_EARLY_PROP_DIAGNOSTIC.json').read_text()) if (td / 'DK_T_EARLY_PROP_DIAGNOSTIC.json').exists() else None
    finally:
        C.OUT_DIR = old


def test_04_quality_gates_block_attention():
    td = pathlib.Path(tempfile.mkdtemp())
    board = _fixture(td)
    o, doc = _run(td, board)
    r = {(x['market'], x['player']): x for x in doc['rows']}[('player_passing_yards', 'Joe Burrow')]
    check('negative control: every gate open for a closed, current, sealed row', r['blocked_by'] == [], r['blocked_by'])
    # inactives not applied -> availability not current
    (td / 'DK_T_EARLY_STATE.json').write_text(json.dumps({'official_inactives': {'STATE': 'NOT_YET_PUBLISHED'}}))
    o, doc = _run(td, board)
    r = {(x['market'], x['player']): x for x in doc['rows']}[('player_passing_yards', 'Joe Burrow')]
    check('positive control: before official inactives, nothing can be elevated',
          'availability_current' in r['blocked_by'] and not r['ATTENTION'], r['blocked_by'])
    # a non-closing team blocks its yards props only
    td2 = pathlib.Path(tempfile.mkdtemp())
    board2 = _fixture(td2)
    b = json.loads((td2 / 'DK_T_EARLY_RESEARCH_BOOK.json').read_text())
    b['games']['2026_04_JAX_CIN']['teams']['CIN']['accounting']['yards_closure_DIAGNOSTIC_NOT_A_GATE']['gap'] = 40.0
    (td2 / 'DK_T_EARLY_RESEARCH_BOOK.json').write_text(json.dumps(b))
    s = json.loads((td2 / 'DK_T_EARLY_SEAL.json').read_text())
    s['research_book_sha256'] = hashlib.sha256((td2 / 'DK_T_EARLY_RESEARCH_BOOK.json').read_bytes()).hexdigest()
    (td2 / 'DK_T_EARLY_SEAL.json').write_text(json.dumps(s))
    o, doc = _run(td2, board2)
    rows = {(x['market'], x['player']): x for x in doc['rows']}
    check('positive control: a 15% yards non-closure blocks the passing-yards prop',
          'stat_accounting_pass' in rows[('player_passing_yards', 'Joe Burrow')]['blocked_by'])
    check('  and the receiving-yards prop', 'stat_accounting_pass' in rows[('player_receiving_yards', "Ja'Marr Chase")]['blocked_by'])
    # a projection changed after the seal is refused outright
    (td2 / 'DK_T_EARLY_PROJ.json').write_text(json.dumps({'market_arm': 'MARKET'}))
    o, _ = _run(td2, board2)
    observe('nfl.tools.classic_prop_compare:compare:PROPS_PROJECTION_CHANGED_AFTER_SEAL', o)
    check('positive control: a projection that changed after the seal (here, to a market arm) is refused',
          o.code == 'PROPS_PROJECTION_CHANGED_AFTER_SEAL', o.code)
    # stale capture: an older board for the same game
    td3 = pathlib.Path(tempfile.mkdtemp())
    board3 = _fixture(td3)
    newer = td3 / 'HR_JAX_CIN_BOARD_2026-10-04T1600Z.csv'
    newer.write_text(board3.read_text())
    old = C.OUT_DIR
    C.OUT_DIR = td3
    try:
        C.compare('T', [str(board3), str(newer)])
        doc = json.loads((td3 / 'DK_T_EARLY_PROP_DIAGNOSTIC.json').read_text())
    finally:
        C.OUT_DIR = old
    check('positive control: an older board for the same game is refused as stale',
          any(x.get('file') == board3.name and x['why'] == 'STALE_CAPTURE_A_NEWER_BOARD_EXISTS' for x in doc['refused']))


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
