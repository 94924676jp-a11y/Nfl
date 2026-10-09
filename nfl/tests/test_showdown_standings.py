"""DK standings for TB@DAL 2026W5 (owner upload 2026-10-09): DK held the corrected R1 lineup for every one of our 190
entries, and DK's points equal ours recomputed from nflverse actuals for every entry (scorer parity)."""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

PASSED = FAILED = 0
DOC = _REPO / 'nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_STANDINGS.json'


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def test_accepted_lineups_and_scorer_parity():
    d = json.loads(DOC.read_text())
    ident = d['accepted_lineup_identification_all']
    n = sum(ident.values())
    check(n == 190, f'all 190 of our entries found in the standings ({n})')
    check(all('CORRECTED_ELIGIBILITY_R1' in k for k in ident), f'every held lineup is the corrected R1 lineup {ident}')
    for cid, c in d['contests'].items():
        check(c['scorer_parity_mismatches'] == [], f'{cid}: DK points == ours for every entry')
        check(c['our_entries_missing'] == [], f'{cid}: no entry missing')
        check(c['financial']['winnings'] == 'UNKNOWN', f'{cid}: winnings stay UNKNOWN without a payout source')


def test_standings_preserved_with_provenance():
    raw = _REPO / 'nfl/postgame/raw/showdown_tb_dal_2026W5'
    recs = [json.loads(x) for x in (raw / 'STANDINGS_PROVENANCE.jsonl').read_text().splitlines() if x.strip()]
    check({r['contest_id'] for r in recs} == {'196438543', '196438555', '196438556'}, 'three contests preserved')
    check(all((_REPO / r['file']).is_file() for r in recs), 'every preserved file exists')


if __name__ == '__main__':
    test_accepted_lineups_and_scorer_parity()
    test_standings_preserved_with_provenance()
