"""Negative controls for game-day eligibility (owner directive 2026-10-08, TB@DAL): real players who were selected
while not on an active roster must be BLOCKED; real active players and an elevated practice-squad QB must be ELIGIBLE.
Uses the real TB@DAL DK export and the real week-5 roster capture."""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import roster_eligibility as E  # noqa: E402

PASSED = FAILED = 0
EXPORT = _REPO / 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv'
ROSTERS = _REPO / 'nfl/vintage/weekly_rosters.dba8eeff1f9c0878.raw.csv.gz'
INACT = _REPO / 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5/ROTOWIRE_INACTIVES_TB_DAL_2026W5.json'


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def test_tb_dal_negative_controls():
    r = E.classify(E.dk_pool(EXPORT), E.roster_rows(ROSTERS, 2026, 5), json.loads(INACT.read_text()),
                   {'Emari Demercado': 'waived by DAL 2026-10-08 (owner relay of ESPN / A. Schefter)'}, ['Easton Stick'])
    # Sills: RESERVE since 2026-10-09 -- with generational suffixes normalised, 'David Sills V' matches his roster
    # record 'David Sills' (status RES = IR, as the owner reported). Before, the exact-name miss read NOT_ON_WEEK_ROSTER.
    want_blocked = {('David Sills V', 'TB'): 'RESERVE', ('Josh Williams', 'TB'): 'PRACTICE_SQUAD_NOT_ELEVATED',
                    ('Emari Demercado', 'DAL'): 'RELEASED', ('Jalen McMillan', 'TB'): 'RESERVE',
                    ('Malik Davis', 'DAL'): 'RESERVE', ('Baker Mayfield', 'TB'): 'GAME_DAY_INACTIVE',
                    ('Camden Brown', 'DAL'): 'GAME_DAY_INACTIVE', ('Brett Rypien', 'TB'): 'PRACTICE_SQUAD_NOT_ELEVATED'}
    for k, reason in want_blocked.items():
        v = r.get(k, {})
        check(v.get('eligible') is False and v.get('reason') == reason, f'{k[0]} BLOCKED ({v.get("reason")})')
    for k in (('Jalon Daniels', 'TB'), ('Dak Prescott', 'DAL'), ('Emeka Egbuka', 'TB'), ('Kenny Gainwell', 'TB'),
              ('Cowboys', 'DAL')):
        check(r.get(k, {}).get('eligible') is True, f'{k[0]} ELIGIBLE ({r.get(k, {}).get("reason")})')
    check(r[('Easton Stick', 'TB')]['eligible'] and r[('Easton Stick', 'TB')]['reason'] == 'PRACTICE_SQUAD_ELEVATED',
          'Easton Stick ELIGIBLE only through his elevation record')
    r2 = E.classify(E.dk_pool(EXPORT), E.roster_rows(ROSTERS, 2026, 5))
    check(r2[('Easton Stick', 'TB')]['eligible'] is False, 'without the elevation record Stick is BLOCKED (unknown is never eligible)')
    check(r2[('David Sills V', 'TB')]['eligible'] is False, 'Sills is BLOCKED even with no inactive list at all')


if __name__ == '__main__':
    test_tb_dal_negative_controls()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
