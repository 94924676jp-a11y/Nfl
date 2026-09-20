"""Emit the ONE file that goes to an independent downstream reviewer.

WHY A SINGLE SELF-DESCRIBING FILE

The reviewer has no access to this repository, cannot open an npz, and cannot
re-run anything. So every number they need is inlined, and every caveat that
would change how a number should be read travels in the same file rather than
in a message that can be separated from it.

WHAT IS DELIBERATELY IN THE HEADER, BEFORE ANY NUMBER

The board is a CANDIDATE, not the accepted baseline. It is UNSEALED. DST does
not exist. The market snapshot predates the inactive declarations. A reader who
sees only the tables would draw conclusions the evidence does not support, so
the file refuses to lead with tables.
"""
from __future__ import annotations

import datetime as _dt
import glob
import gzip
import csv
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import build_postinactives_package as B  # noqa: E402

RUNS = '/tmp/claude-0/postinact/*/'
#: PRIMARY comparator: the POST-INACTIVES capture. The 04:52Z board is kept
#: for chronology and is never overwritten, but it predates the inactive
#: publication and must not be the board a final edge is computed against.
MARKET = ('nfl/research/market/EARLY_1PM_2026W2/raw/'
          'NFL_wk2_1pm_hardrock_markets_POSTINACTIVES_2026-09-20T1635Z.csv')
MARKET_PRIOR = ('nfl/research/market/EARLY_1PM_2026W2/raw/'
                'NFL_wk2_1pm_hardrock_markets_2026-09-20T0452Z.csv')
DELTA = ('nfl/research/market/EARLY_1PM_2026W2/raw/'
         'NFL_wk2_1pm_hardrock_mainline_delta_0452Z_to_1635Z.csv')
ROSTER = 'nfl/vintage/weekly_rosters.73f1d36a204ec591.raw.csv.gz'
STATE = 'nfl/research/sunday/official_inactives_2026W2/OFFICIAL_INACTIVES_STATE.json'
EARLY = ('2026_02_CAR_ATL', '2026_02_CIN_HOU', '2026_02_CLE_TB',
         '2026_02_GB_NYJ', '2026_02_MIN_CHI', '2026_02_NO_BAL',
         '2026_02_PHI_TEN', '2026_02_PIT_NE')


def roster_map():
    out = {}
    with gzip.open(_REPO / ROSTER, 'rt') as f:
        for r in csv.DictReader(f):
            if r.get('season') == '2026' and r.get('week') == '2':
                out[r['gsis_id']] = r
    return out


def build() -> dict:
    ros = roster_map()
    st = json.loads((_REPO / STATE).read_text())
    inact_by_club = {}
    for r in st['resolved']:
        inact_by_club.setdefault(r['club'], []).append(r['gsis_id'])
    inact_ids = {r['gsis_id'] for r in st['resolved']}

    runs = []
    for d in sorted(glob.glob(RUNS)):
        p = pathlib.Path(d)
        if (p / 'player_draws_manifest.json').exists():
            runs.append(B.read_run(p))
    runs = [r for r in runs if r['game_id'] in EARLY]
    got = {r['game_id'] for r in runs}
    missing = [g for g in EARLY if g not in got]

    foot = B.football_rows(runs, ros)
    dfs = B.dfs_rows(runs, ros)
    sup = B.position_support(runs, ros)
    gate = B.assert_no_inactive_in_playable(runs, inact_by_club, ros)
    shared = B.assert_shared_draws(runs)
    cut = runs[0]['written_at'] if runs else None
    props = B.prop_rows(runs, ros, _REPO / MARKET, inact_ids,
                        delta_csv=_REPO / DELTA, model_cut=cut) if runs else {
        'rows': [], 'counts': {}}

    return {
        'READ_THIS_FIRST': {
            'what_this_is': (
                'A post-inactives football simulation board for the eight '
                '1:00 PM ET DraftKings Early Only games of 2026 week 2, with '
                'a DraftKings scoring view and an exact player-prop '
                'probability view derived from THE SAME simulation draws.'),
            'model_configuration': 'V1_CANDIDATE_R9_W1P_GSVUCY',
            'candidate_status': 'CANDIDATE_NOT_ACCEPTED_BASELINE',
            'what_that_means': (
                'This is NOT the accepted production baseline (R8). The owner '
                'authorised it for TODAY ONLY as a downstream decision board. '
                'It is not promoted, and nothing here changes the model '
                'registry.'),
            'board_is_unsealed': True,
            'why_unsealed': (
                'artifact_sealing refuses on current_season_input_freshness: '
                'denom_panel and team_volume_history both read a panel whose '
                'newest ordinal is 202518, with zero 2026 rows. The football '
                'layers ran and their draws are real; the board did not pass '
                'the sealing gate.'),
            'DST': 'DST_UNSUPPORTED. The engine emits no team-defence outputs '
                   'at all, and points allowed has no simulated scoreboard to '
                   'read. NO DST PROJECTION EXISTS AND NONE MAY BE INVENTED. '
                   'A DraftKings Classic lineup requires one, so a legal '
                   'lineup cannot be certified from this board alone.',
            'market_clock': (
                'The prop board is evaluated against the POST-INACTIVES Hard '
                'Rock capture of 2026-09-20T16:35:11Z-16:35:47Z (6,694 rows, '
                '624 main lines, freshest book stamp 16:35:33.717Z). Both the '
                'model cut (16:22:00Z) and that capture postdate the ~15:30Z '
                'inactive publication, so both carry the inactive '
                'information: TIME_ALIGNED_POST_INACTIVES. THE CLOCKS ARE NOT '
                'IDENTICAL -- the book was captured about 13 minutes AFTER '
                'the model cut, and anything it absorbed in that window is '
                'not in the model. Each row states that gap in seconds.'),
            'market_movement': (
                'Every main-line row carries the 04:52Z -> 16:35Z change so a '
                'reader can separate model disagreement from a book that has '
                'already absorbed the news: 389 main lines changed, 218 '
                'unchanged, 17 new, 40 removed. The 04:52Z board is preserved '
                'unmodified for chronology and is NOT the comparator. A '
                'market absent from the fresh board is recorded as removed, '
                'which is not evidence it was suspended, and it is never '
                'evaluated as a current opportunity.'),
            'v2_status': 'V2 NOT YET EARNED',
            'forbidden_inputs_confirmed': (
                'No sportsbook price, no DraftKings salary and no ownership '
                'estimate entered the football forecast. The DFS and prop '
                'views are strictly downstream of the draws.'),
        },
        'spec_version': B.SPEC_VERSION,
        'generated_at_utc': _dt.datetime.now(_dt.UTC).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        'provenance': {
            'information_cut': runs[0]['written_at'] if runs else None,
            'n_draws_per_game': sorted({r['n_draws'] for r in runs}),
            'games_expected': list(EARLY),
            'games_present': sorted(got),
            'games_missing': missing,
            'runs': [{'game_id': r['game_id'], 'run_id': r['run_id'],
                      'status': r['status'],
                      'first_failure': r['first_failure'],
                      'n_draws': r['n_draws'],
                      'execution_identity': r['execution_identity'],
                      'code_commit': r['code_commit'],
                      'draw_content_digest': r['content_digest'],
                      'layers': r['layers']} for r in runs],
            'market_boards': {
                'primary_post_inactives': {
                    'file': MARKET,
                    'sha256': '3215f93a097d0b96da03bbd8a93831f2d5a0b41ce'
                              '6236310b5e10b0005cb5118',
                    'retrieved_utc': '2026-09-20T16:35:11Z..16:35:47Z',
                    'rows': 6694, 'main_lines': 624, 'games': 8},
                'prior_chronology_only': {
                    'file': MARKET_PRIOR,
                    'sha256': '1c097f532fbd81bc0b82bc2c4aa43453b021252a5'
                              '55610dd479d3cd0fb684ec6',
                    'retrieved_utc': '2026-09-20T04:52Z',
                    'role': 'PRESERVED FOR MOVEMENT ANALYSIS ONLY, never the '
                            'comparator for a final edge'},
                'delta': {'file': DELTA,
                          'sha256': '75ffbf9099a63a1e4d3d384254b36392fe998dc'
                                    '8f82f4609a51b72702c944e03',
                          'changed': 389, 'unchanged': 218, 'new': 17,
                          'removed': 40},
            },
            'inactive_evidence': {
                'source': 'OFFICIAL_NFL_AND_TEAM_SITES',
                'package_sha256': st['provenance']['package_hashes'],
                'league_published_utc':
                    st['provenance']['league_datePublished_utc'],
                'league_retrieved_utc':
                    st['provenance']['league_retrieved_utc'],
                'declarations': st['provenance']['declarations'],
                'membership_conflicts':
                    st['provenance']['membership_conflicts'],
                'n_resolved': st['identity']['n_resolved'],
                'n_unresolved': st['identity']['n_unresolved'],
                'states': st['states'],
                'emergency_third_qb_handling':
                    st['emergency_third_qb_handling'],
                'unresolved': st['unresolved'],
            },
        },
        'audits': {
            'inactive_exclusion': gate,
            'shared_draws': shared,
            'position_support_per_game': sup,
        },
        'football_board': foot,
        'dfs_board': dfs,
        'prop_board': props,
    }


def main():
    out = build()
    p = (_REPO / 'nfl' / 'research' / 'sunday'
         / 'EARLY_ONLY_POSTINACTIVES_PACKAGE_2026W2.json')
    p.write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
    print(f'wrote {p}  {p.stat().st_size} bytes')
    print('games present :', len(out['provenance']['games_present']))
    print('games missing :', out['provenance']['games_missing'])
    print('football rows :', len(out['football_board']))
    print('dfs rows      :', len(out['dfs_board']))
    print('prop rows     :', len(out['prop_board']['rows']),
          out['prop_board']['counts'])
    print('inactive gate :', out['audits']['inactive_exclusion']['code'])
    print('shared draws  :', out['audits']['shared_draws']['code'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
