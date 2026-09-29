#!/usr/bin/env python3.12
"""The product requirement: a slate file in, a legal portfolio out, autonomously.

This is the test that would have caught the real Week 3 failure. Not "is the projection
good" -- the owner had to come to the session to get 48 lineups, which means no test
existed asserting that the system can produce them at all. This one does, and it runs
without a human in the loop.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import slate_to_portfolio as SP  # noqa: E402

ENTRIES = _REPO / 'nfl/dfs/salaries/raw/DKEntries_EARLY_ONLY_2026W3_62.csv'
OWNER = _REPO / 'nfl/dfs/salaries/raw/OWNER_PLACEHOLDERS_FC_48_2026W3.csv'
OWNER_SHA = '13ce2da14da94f961f8288f46faabeea016394290594338ca77124297f216e53'
ID = re.compile(r'\((\d+)\)')
from nfl.tests import _registry  # noqa: E402

#: RUN THIS MODULE IN A FRESH INTERPRETER. run_suite reads this from source and re-runs the
#: module through itself in a subprocess, so it is judged by identical logic.
REQUIRES_OWN_PROCESS = 'the end-to-end slate product reads the external FantasyCruncher context, which the firewall refuses in a proprietary interpreter'

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


_BOARD = None


def board():
    global _BOARD
    if _BOARD is None:
        _BOARD = SP.run(ENTRIES)
    return _BOARD


@check('THE PRODUCT REQUIREMENT: a slate file autonomously yields a legal portfolio')
def t_delivers():
    b = board()
    assert b['product_delivered'] is True, (
        f'stopped at {b["stopped_at"]} ({b["stopped_code"]}) -- by the Saturday rule the '
        f'system is not production-ready')
    assert b['slate_status'] in (SP.STATUS_FULL, SP.STATUS_HYBRID, SP.STATUS_FALLBACK)
    return (f'{b["slate_status"]}, all {len(b["stages_passed"])} stages passed, CSV '
            f'written with no human in the loop')


@check('every pipeline stage reports, and a stopped run still emits a board')
def t_stages_report():
    b = board()
    names = [s['stage'] for s in b['stages']]
    for want in ('ingest_slate', 'verify_identity', 'availability', 'current_role',
                 'projections', 'candidate_generation', 'portfolio_selection',
                 'legality_validation', 'dk_upload_csv'):
        assert want in names, f'{want} produced no stage row'
    assert SP.OUT_BOARD.exists() and SP.OUT_MD.exists()
    assert 'SATURDAY_RULE' in b
    return f'{len(names)} stages, board + markdown written'


@check('ONE deliverable: the status board carries status, coverage, portfolio, honesty')
def t_single_deliverable():
    b = json.loads(SP.OUT_BOARD.read_text())
    for k in ('slate_status', 'projection_coverage', 'portfolio', 'CORRELATION_BASIS',
              'unknown_by_design', 'SATURDAY_RULE'):
        assert k in b, f'the board lacks {k}'
    cov = b['projection_coverage']
    for pos in SP.PRD.REQUIRED_POSITIONS:
        assert pos in cov, f'coverage missing {pos}'
        assert cov[pos]['pct'] is not None
    return (f'status {b["slate_status"]}, coverage for '
            f'{len(cov)} positions, portfolio of {b["portfolio"]["n_lineups"]}')


@check('the generated CSV is legal on an independent re-read')
def t_csv_legal():
    board()
    post = json.loads(
        (_REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json').read_text()
    )['players']
    absent = {k for k, v in post.items()
              if v['current_availability']['status'] in AV.ABSENT_STATUSES}
    rows = list(csv.reader(SP.OUT_CSV.open(newline='', encoding='utf-8')))
    hdr = rows[0]
    slot = [i for i, c in enumerate(hdr) if c in ('QB', 'RB', 'WR', 'TE', 'FLEX', 'DST')]
    assert len(slot) == 9, len(slot)
    assert len(rows) - 1 == 48, len(rows) - 1
    for r in rows[1:]:
        ids = [ID.search(r[i]).group(1) for i in slot if ID.search(r[i])]
        assert len(ids) == 9, (r[0], len(ids))
        assert len(set(ids)) == 9, f'{r[0]} duplicates a player'
        assert not [i for i in ids if i in absent], f'{r[0]} rosters a reported absence'
        assert all(i in post for i in ids), f'{r[0]} has an id outside the universe'
        s = sum(post[i]['salary'] for i in ids)
        assert s <= SP.SALARY_CAP, f'{r[0]} salary {s}'
        c = collections.Counter(post[i]['position'] for i in ids)
        assert c['QB'] == 1 and c['DST'] == 1 and c['RB'] >= 2 and c['WR'] >= 3 \
            and c['TE'] >= 1, (r[0], dict(c))
    alloc = collections.Counter(r[2] for r in rows[1:])
    assert dict(alloc) == {'195955835': 2, '196110787': 20, '196117165': 6,
                           '196122720': 20}, dict(alloc)
    return '48 rows, zero failures, 2/20/6/20 allocation preserved'


@check('the declared correlation rules actually hold in the output')
def t_correlation_rules():
    b = board()
    p = b['portfolio']
    for lu in p['lineups']:
        n = len(lu['stack'])
        assert SP.MIN_STACK <= n <= SP.MAX_STACK, f'stack size {n}'
    assert p['max_pairwise_overlap'] <= SP.MAX_OVERLAP, p['max_pairwise_overlap']
    for name, pct in p['qb_exposure'].items():
        assert float(pct.rstrip('%')) <= SP.MAX_QB_EXPOSURE * 100 + 1e-9, (name, pct)
    for name, pct in p['top_player_exposure'].items():
        assert float(pct.rstrip('%')) <= SP.MAX_PLAYER_EXPOSURE * 100 + 1e-9, (name, pct)
    return (f'stacks {p["stack_sizes"]}, max overlap {p["max_pairwise_overlap"]}/9, '
            f'QB exposure capped, bring-back {p["bring_back_rate"]}')


@check('no DST is paired against our own quarterback')
def t_no_dst_vs_own_qb():
    b = board()
    post = json.loads(
        (_REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json').read_text()
    )['players']
    club_opp = {v['team']: v['opponent'] for v in post.values()}
    bad = []
    for lu in b['portfolio']['lineups']:
        qb_club = next((v['team'] for v in post.values() if v['name'] == lu['qb']), None)
        if qb_club and lu['dst'] == club_opp.get(qb_club):
            bad.append((lu['qb'], lu['dst']))
    assert not bad, f'contradictory scoring stories: {bad}'
    return f'{len(b["portfolio"]["lineups"])} lineups, zero own-DST-against-own-QB'


@check('ceiling, duplication and payout are UNKNOWN, not invented')
def t_no_invented_metrics():
    b = board()
    for k in ('lineup_ceiling', 'duplication_probability', 'expected_payout',
              'first_place_probability', 'projected_ownership'):
        assert k in b['unknown_by_design'], f'{k} not declared unknown'
    blob = json.dumps(b['portfolio'])
    for banned in ('ceiling', 'duplication', 'expected_payout', 'ownership'):
        assert banned not in blob, f'the portfolio carries a {banned} figure it cannot know'
    assert 'NOT_SIMULATION' in b['CORRELATION_BASIS']
    return 'five metrics declared UNKNOWN; none appears in the portfolio output'


@check("the owner's own entry files are never written")
def t_owner_untouched():
    board()
    assert hashlib.sha256(OWNER.read_bytes()).hexdigest() == OWNER_SHA, (
        'the owner placeholder file changed')
    assert SP.OUT_CSV != OWNER and SP.OUT_CSV.name == 'DK_UPLOAD_GENERATED.csv'
    return f'{OWNER.name} byte-identical; output goes to {SP.OUT_CSV.name}'


# EXPOSE EVERY CHECK TO run_suite, the authoritative execution path. Before this the runner
# reported `0 fn, NO TALLY` for this module and executed NONE of its checks, while a direct run of
# the file printed a confident pass. See nfl/tests/_registry.py.
_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
