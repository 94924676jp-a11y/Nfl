"""Release gate: an upload carrying a player without positive roster evidence can never be READY or PROVISIONAL.

Matched regression on the real TB@DAL 2026W5 files (owner directive 2026-10-08):
  * the sealed OFFICIAL upload (e01cd488) held 11 lineups with ineligible players -> ROSTER_INELIGIBLE_IN_UPLOAD,
    LINEUP_ELIGIBILITY_VALID FAIL, decision NOT_READY;
  * the corrected R1 upload (9d05d9bb) -> no eligibility blocker;
  * no roster capture, or a capture with no rows for the week -> ROSTER_ELIGIBILITY_UNVERIFIED (fail closed).
"""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import showdown_run_guards as G  # noqa: E402

PASSED = FAILED = 0
RAW = _REPO / 'nfl/dfs/salaries/raw/showdown_tb_dal_2026W5'
SD = _REPO / 'nfl/dfs/salaries/showdown_tb_dal'
EXPORT = RAW / 'DKEntries_TB_DAL_SHOWDOWN_2026W5.5d559e413e680cae.csv'
ROSTERS = _REPO / 'nfl/vintage/weekly_rosters.dba8eeff1f9c0878.raw.csv.gz'
INACT = json.loads((RAW / 'ROTOWIRE_INACTIVES_TB_DAL_2026W5.json').read_text())
TX = json.loads((SD / 'OFFICIAL_ELIGIBILITY_FIX_R1/TRANSACTIONS_OWNER_RELAYED.json').read_text())
EL = json.loads((SD / 'OFFICIAL_ELIGIBILITY_FIX_R1/ELEVATIONS_OWNER_RELAYED.json').read_text())


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _gate(upload, rosters=ROSTERS, week=5):
    return G.upload_roster_eligibility(upload, EXPORT, rosters, 2026, week, INACT, TX, EL)


def test_official_upload_is_refused():
    b, rep = _gate(SD / 'OFFICIAL/SHOWDOWN_TB_DAL_DK_UPLOAD.csv')
    check(len(b) == 1 and b[0].startswith('ROSTER_INELIGIBLE_IN_UPLOAD'), f'official upload blocked: {b[:1]}')
    check(rep['lineups_with_ineligible'] == 11, f"11 lineups flagged ({rep['lineups_with_ineligible']})")
    names = set(rep['ineligible_players'])
    for k in ('David Sills V|TB', 'Emari Demercado|DAL', 'Josh Williams|TB'):
        check(k in names, f'{k} named ({rep["ineligible_players"].get(k)})')
    rel = G.release_classification(b, {'status': 'COMPLETE_FOR_STARTERS'}, {'status': 'PASS'})
    check(rel['decision'] == 'NOT_READY' and rel['statuses']['LINEUP_ELIGIBILITY_VALID'] == 'FAIL',
          f"release NOT_READY with eligibility FAIL even when every other status passes ({rel['decision']})")


def test_corrected_upload_passes_the_gate():
    b, rep = _gate(SD / 'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_DK_UPLOAD.csv')
    check(b == [] and rep['status'] == 'PASS', f'corrected upload carries no ineligible player ({b})')
    check(len(rep['blocked_in_pool']) == 20, f"20 DK-pool players blocked ({len(rep['blocked_in_pool'])})")


def test_fails_closed_without_roster_evidence():
    b, rep = _gate(SD / 'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_DK_UPLOAD.csv', rosters=None)
    check(b and b[0].startswith('ROSTER_ELIGIBILITY_UNVERIFIED'), 'no roster capture -> UNVERIFIED, never PASS')
    b2, rep2 = _gate(SD / 'OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_DK_UPLOAD.csv', week=19)
    check(b2 and rep2['reason'] == 'EMPTY_ROSTER_WEEK', 'a capture with no rows for the week -> UNVERIFIED (an empty is an error)')
    rel = G.release_classification(b, {'status': 'COMPLETE_FOR_STARTERS'}, {'status': 'PASS'})
    check(rel['decision'] == 'NOT_READY', 'unverified eligibility cannot be READY or PROVISIONAL')


def test_final_verify_calls_the_gate():
    src = (_REPO / 'nfl/tools/showdown_next_slate.py').read_text()
    fv = src[src.index('def final_verify('):src.index('def ', src.index('def final_verify(') + 10)]
    check('upload_roster_eligibility(' in fv and 'blockers += eb' in fv,
          'final_verify feeds the roster-eligibility blockers into the release decision')


if __name__ == '__main__':
    for f in (test_official_upload_is_refused, test_corrected_upload_passes_the_gate,
              test_fails_closed_without_roster_evidence, test_final_verify_calls_the_gate):
        f()
    print(PASSED, FAILED)
