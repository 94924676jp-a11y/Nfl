"""postgame.classic_week: grades the locked Week-4 state against results, refuses partial results by name.

All results here are SYNTHETIC fixtures written to a temp directory; nothing touches nfl/postgame/raw/."""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.postgame import classic_week as W   # noqa: E402
from nfl.tests._controls import observe      # noqa: E402

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


def _sandbox():
    td = pathlib.Path(tempfile.mkdtemp())
    W.RAW, W.OUT, W.PROVENANCE = td / 'raw', td / 'out', td / 'raw' / 'PROVENANCE.jsonl'
    return td


def _fixture_week(lock, td, drop_club=None):
    cols = ['player_id', 'player_display_name', 'position', 'team', 'season', 'week'] + list(W.SKILL_COLS) + \
           ['passing_2pt_conversions', 'rushing_2pt_conversions', 'receiving_2pt_conversions', 'special_teams_tds'] + list(W.DST_COLS)
    rows = []
    for dk, p in lock['state']['players'].items():
        r = lock['proj'].get(dk) or {}
        if p['position'] == 'DST' or not p.get('gsis_id') or (r.get('dk_points') or 0) < 0.5 or p['team'] == drop_club:
            continue
        d = {c: 0 for c in cols}
        d.update(player_id=p['gsis_id'], player_display_name=p['name'], position=p['position'], team=p['team'], season=2026, week=4,
                 attempts=round(r.get('pass_attempts') or 0), passing_yards=round(r.get('pass_yards') or 0),
                 carries=round(r.get('carries') or 0), rushing_yards=round(r.get('rush_yards') or 0),
                 targets=round(r.get('targets') or 0), receptions=round(r.get('receptions') or 0),
                 receiving_yards=round(r.get('rec_yards') or 0))
        rows.append(d)
    for club in {g[s] for g in lock['state']['games'].values() for s in ('away', 'home')} - {drop_club}:
        d = {c: 0 for c in cols}
        d.update(player_id=f'DEF_{club}', player_display_name='def', position='LB', team=club, season=2026, week=4,
                 def_sacks=2, def_interceptions=1)
        rows.append(d)
    p = td / 'stats_player_week_2026.csv'
    with p.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    g = td / 'games.csv'
    with g.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['season', 'week', 'away_team', 'home_team', 'away_score', 'home_score'])
        for gg in lock['state']['games'].values():
            w.writerow([2026, 4, gg['away'], gg['home'], 17, 24])
    return p, g


def test_01_lock_is_the_submitted_state():
    o = W.locked()
    check('the lock commit holds the submitted upload, and the seal predates kickoff', o.state.value == 'PASS', o.detail)
    check('  173 locked entries', len(o.value['upload']) == 173)


def test_02_refusals():
    _sandbox()
    lock = W.locked().value
    o = W.grade()
    observe('nfl.postgame.classic_week:grade:POSTGAME_NO_RESULTS', o)
    check('positive control: no results ingested -> POSTGAME_NO_RESULTS, never a zero grade', o.code == 'POSTGAME_NO_RESULTS', o.code)
    td = _sandbox()
    p, _g = _fixture_week(lock, td, drop_club='CHI')
    W.ingest('NFL_PLAYER_WEEK', p, 'SYNTHETIC TEST', '2026-10-05T00:00:00Z')
    o = W.player_week(lock)
    observe('nfl.postgame.classic_week:player_week:ACTUALS_GAMES_MISSING', o)
    check('positive control: a feed missing one club is refused by name', o.code == 'ACTUALS_GAMES_MISSING' and o.evidence['missing'] == ['CHI'], o.detail)
    check('the lineup parser reads DraftKings lineup strings',
          W.parse_lineup('QB Josh Allen RB James Cook III RB Bucky Irving WR A WR B WR C TE D FLEX E DST Bears')[1] == ('RB', 'James Cook III'))


def test_03_grades_a_complete_synthetic_slate():
    td = _sandbox()
    lock = W.locked().value
    p, g = _fixture_week(lock, td)
    W.ingest('NFL_PLAYER_WEEK', p, 'SYNTHETIC TEST', '2026-10-05T00:00:00Z')
    W.ingest('NFL_GAMES', g, 'SYNTHETIC TEST', '2026-10-05T00:00:00Z')
    o = W.grade()
    check('negative control: a complete feed grades', o.state.value == 'PASS', f'{o.code} {o.detail}')
    doc = json.loads((W.OUT / 'DK_2026W4_EARLY_POSTGAME.json').read_text())
    check('  all 173 lineups graded', doc['all_173_graded'] is True)
    opt = doc['optimal_lineup']
    best = max(x['points'] for prof in doc['lineups'].values() for x in [prof['best']])
    check('  the exact optimal lineup is legal (9 players, salary <= 50,000) and beats every one of ours',
          len(opt['players']) == 9 and opt['salary'] <= 50000 and opt['points'] >= best - 1e-6, (opt['points'], best, opt['salary']))
    pos = sorted(x[1] for x in opt['players'])
    check('  the optimal lineup has a legal position mix', pos.count('QB') == 1 and pos.count('DST') == 1 and pos.count('TE') in (1, 2)
          and 2 <= pos.count('RB') <= 3 and 3 <= pos.count('WR') <= 4, pos)
    check('  DST graded from components with points allowed', any('COMPONENTS (2-pt' in k for k in doc['actual_basis_counts']), doc['actual_basis_counts'])
    check('  concentration audit produced', isinstance(doc['concentration'], dict) and doc['concentration']['by_depth_band'])
    check('CRPS of a point forecast at the outcome is zero', abs(W._crps(np.full(50, 7.0), 7.0)) < 1e-9)


def test_04_standings_rank_our_entries_and_find_what_kept_us_from_first():
    td = _sandbox()
    lock = W.locked().value
    p, g = _fixture_week(lock, td)
    W.ingest('NFL_PLAYER_WEEK', p, 'SYNTHETIC TEST', '2026-10-05T00:00:00Z')
    W.ingest('NFL_GAMES', g, 'SYNTHETIC TEST', '2026-10-05T00:00:00Z')
    st = lock['state']['players']
    hdr = lock['upload_header']
    sl = [i for i, h in enumerate(hdr) if h in ('QB', 'RB', 'WR', 'TE', 'FLEX', 'DST')]
    mine = [r for r in lock['upload'] if r[2] == '196208417']
    sp = td / 'standings.csv'
    with sp.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['Rank', 'EntryId', 'EntryName', 'TimeRemaining', 'Points', 'Lineup', '', 'Player', 'Roster Position', '%Drafted', 'FPTS'])
        w.writerow([1, '999', 'rival', 0, 300.0, 'QB X RB A RB B WR C WR D WR E TE F FLEX G DST Bears', '', 'Zay Flowers', 'WR', '31.2%', 25.4])
        for k, r in enumerate(mine, start=2):
            lu = ' '.join(f"{hdr[i]} {st[r[i]]['name']}" for i in sl)
            w.writerow([k, r[0], 'owner', 0, 150.0 - k, lu, '', '', '', '', ''])
    W.ingest('DK_STANDINGS', sp, 'SYNTHETIC TEST', '2026-10-05T00:00:00Z')
    o = W.grade()
    doc = json.loads((W.OUT / 'DK_2026W4_EARLY_POSTGAME.json').read_text())
    m = doc['lineups']['MAX20']
    check('standings identify the contest by our Entry IDs and rank our 20', o.state.value == 'PASS' and m['best_rank'] == 2
          and m['field_size'] == 21, (o.detail, m.get('best_rank'), m.get('field_size')))
    check('  gap to first and the players that differed are reported', m['gap_to_first'] == 152.0
          and 'X' in m['what_kept_best_from_first']['only_winner'], m.get('what_kept_best_from_first'))
    check('  DraftKings FPTS is kept as a cross-check against our own components',
          doc['dk_reconciliation']['n_checked'] >= 1, doc['dk_reconciliation'])


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
