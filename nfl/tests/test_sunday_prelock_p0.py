"""Sunday prelock P0 corrections, on the live state path with the committed W5 data (2026-10-10).

1. A club-published starter admitted through the evidence packet takes QB1; the incumbent's chart rank cannot defeat
   it, and the incumbent is NOT made inactive to get there (he stays Questionable, an eligible backup).
2. A player who changed clubs carries no other club's usage rank, observed share or depth detail into his new club's
   state. (The matching projection-side fix in proj_v1.current_season_shares is a PROPOSED patch awaiting the owner,
   docs/sunday_executor/proj_v1_current_club_shares.PROPOSED.patch, because editing proj_v1 invalidates the recorded
   SC-APPEAR-1 replay pin.)
"""
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import research_universe as RU, classic_slate_state as CS, sunday_evidence as SE  # noqa: E402
from nfl.tools import availability as AV  # noqa: E402

PASSED = FAILED = 0
RAW = _REPO / 'nfl/dfs/salaries/raw/classic_early_2026W5'
PKT = _REPO / 'nfl/dfs/salaries/classic_early_2026W5/evidence_packets/2026W5_OWNER_20261010_CHI_STARTER.json'
AS_OF = '2026-10-10T18:20:00Z'
_CACHE = {}


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def _state(with_packet):
    if with_packet not in _CACHE:
        u = RU.build('2026W5', RAW)
        pk = SE.load(PKT).value if with_packet else None
        _CACHE[with_packet] = CS.build('2026W5', as_of=AS_OF, research_universe=u, evidence_packet=pk).value['players']
    return _CACHE[with_packet]


def _row(P, name, team):
    hit = [p for p in P.values() if p['name'] == name and p['team'] == team]
    return hit[0] if len(hit) == 1 else None


def test_admitted_starter_defeats_the_chart_without_inactivating_the_incumbent():
    before, after = _state(False), _state(True)
    w0, b0 = _row(before, 'Caleb Williams', 'CHI'), _row(before, 'Tyson Bagent', 'CHI')
    check(w0['depth_rank'] == 1 and b0['depth_rank'] == 2, 'before: the chart starts Williams (the defect case)')
    w1, b1 = _row(after, 'Caleb Williams', 'CHI'), _row(after, 'Tyson Bagent', 'CHI')
    check(b1['depth_rank'] == 1 and w1['depth_rank'] == 2, 'after: the admitted release starts Bagent, Williams is QB2')
    check(b1['predicted_lineup_context'].get('state') == 'CONFIRMED_BY_TEAM_PUBLISHED_EVIDENCE'
          and b1['predicted_lineup_context'].get('packet_id') == '2026W5-owner-20261010-chi-starter',
          'the starter carries the packet provenance')
    st = w1['current_availability']['status']
    check(st not in AV.ABSENT_STATUSES and w1['current_availability']['designation'] == 'QUESTIONABLE',
          f'Williams is not made inactive to install Bagent ({st}, Questionable): an eligible backup')


def test_a_packet_cannot_name_an_inactive_starter():
    pk = json.loads(PKT.read_text())
    pk['players'] = [{'name': 'Tyson Bagent', 'team': 'CHI', 'status': 'INACTIVE', 'cited': 'OFFICIAL_RELEASE'}]
    pool = [{'dk_id': r['dk_id'], 'dk_name': r['dk_name'], 'team': r['team'], 'dk_pos': r['dk_pos']}
            for r in RU.build('2026W5', RAW).value]
    o = SE.resolve(pk, pool)
    check(o.code == 'EVIDENCE_PACKET_UNRESOLVED_PLAYER' and 'NAMED_STARTER_AND_INACTIVE' in json.dumps(o.evidence),
          'a starter who is also listed inactive is refused')


def test_a_transferred_player_carries_no_other_clubs_usage():
    before_guard = json.loads((_REPO / 'nfl/dfs/salaries/classic_early_2026W5/research_projection/'
                               'rebuild_2026-10-10_roster/STATE.json').read_text())['players']
    a0 = _row(before_guard, 'Kaytron Allen', 'MIA')
    check(a0['depth_usage_rank'] == 3 and (a0['observed_2026'] or {}).get('club') == 'WAS',
          'before: MIA row ranked by WAS usage (the defect case, frozen build)')
    a1 = _row(_state(True), 'Kaytron Allen', 'MIA')
    check(a1['club_transfer'] and a1['club_transfer']['usage_club'] == 'WAS', 'after: the transfer is recorded')
    check(a1['depth_usage_rank'] is None and a1['observed_2026'] == {} and a1['depth_detail'] == {},
          'after: no WAS usage rank, observed share or depth detail at MIA')
    others = [p for p in _state(True).values() if p.get('club_transfer')]
    check([p['name'] for p in others] == ['Kaytron Allen'], f'only the transferred player is touched: {[p["name"] for p in others]}')



def test_the_state_keeps_the_secondary_injury():
    P = _state(True)
    j, k = _row(P, 'Ashton Jeanty', 'LV'), _row(P, 'Keenan Allen', 'IND')
    check(j['current_availability']['injury'] == 'Ankle' and j['current_availability']['injury_secondary'] == 'Foot',
          f"Jeanty Ankle + Foot: {j['current_availability']['injury']}, {j['current_availability']['injury_secondary']}")
    check(k['current_availability']['injury_secondary'] == 'Groin', 'Keenan Allen keeps Groin behind the rest day')
