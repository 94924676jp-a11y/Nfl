"""PART 2: the full post-inactives drill, on an isolated synthetic root.

One pass through every stage the real lists will take:

    raw bytes -> immutable hash -> parse -> game/team identity -> player
    identity -> both-team completeness -> appearance override -> opportunity
    allocation -> a sealed tournament's inputs

and, at each end of it, a proof that the LIVE root was not touched. That proof
is not decoration: the first version of the propagation tests wrote a synthetic
inactives blob into the live vintage and the information-set selector began
choosing it as tonight's official list.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
import tempfile

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production.nonqb import accounting as ACC                   # noqa: E402
from nfl.production.nonqb import inactives as INA                    # noqa: E402

PASSED = FAILED = 0
KO = '2026-09-11T00:35:00Z'
T90 = '2026-09-10T23:05:00Z'
LIVE = pathlib.Path(_ROOT) / 'nfl'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _live_fingerprint():
    """A hash of the live manifest plus the set of live inactives blobs."""
    man = LIVE / 'vintage_manifest.jsonl'
    h = hashlib.sha256(man.read_bytes()).hexdigest()
    blobs = sorted(p.name for p in (LIVE / 'vintage').glob('official_inactives.*'))
    return h, tuple(blobs)


# The seeded roster. Two clubs, and the five cases the directive names.
ROSTER = {
    # SF -- a starting WR, RB and TE, each of whom will be listed inactive
    '00-0010001': {'name': 'Wide Starter', 'team': 'SF', 'position': 'WR'},
    '00-0010002': {'name': 'Back Starter', 'team': 'SF', 'position': 'RB'},
    '00-0010003': {'name': 'End Starter', 'team': 'SF', 'position': 'TE'},
    '00-0010004': {'name': 'Wide Backup', 'team': 'SF', 'position': 'WR'},
    '00-0010005': {'name': 'Back Backup', 'team': 'SF', 'position': 'RB'},
    # LA -- untouched by the SF list, and one AMBIGUOUS pair
    '00-0020001': {'name': 'Rams Receiver', 'team': 'LA', 'position': 'WR'},
    '00-0020002': {'name': 'Rams Runner', 'team': 'LA', 'position': 'RB'},
    '00-0020003': {'name': 'Chris Smith', 'team': 'LA', 'position': 'WR'},
    '00-0020004': {'name': 'Chris Smith', 'team': 'LA', 'position': 'TE'},
}

DOC = """<html><body>
<h2>SF</h2><ul><li>Wide Starter</li><li>Back Starter</li><li>End Starter</li>
<li>Ghost Player</li></ul>
<h2>LA</h2><ul><li>Rams Runner</li></ul>
</body></html>"""

DOC_AMBIGUOUS = """<html><body>
<h2>SF</h2><ul><li>Wide Starter</li></ul>
<h2>LA</h2><ul><li>Chris Smith</li></ul>
</body></html>"""

DOC_ONE_TEAM = """<html><body>
<h2>SF</h2><ul><li>Wide Starter</li></ul>
</body></html>"""


def test_the_drill_runs_end_to_end_on_a_synthetic_root():
    before = _live_fingerprint()
    root = pathlib.Path(tempfile.mkdtemp(prefix='inactives-drill-'))
    raw = DOC.encode()

    # 1-3. bytes, hash, immutable store, clocks
    st = INA.store(raw, retrieved_at=T90, published_at='2026-09-10T23:03:00Z',
                   source_url='https://www.nfl.com/inactives/',
                   game_id='2026_01_SF_LA', http_status=200, root=root)
    if not check('1. raw bytes stored before parsing', st.state is State.PASS,
                 st.code):
        return
    check('   the hash is of the bytes we handed it',
          st.evidence['sha256'] == hashlib.sha256(raw).hexdigest())
    check('   publication and retrieval clocks are separate',
          st.evidence['published_at'] == '2026-09-10T23:03:00Z' and
          st.evidence['retrieved_at'] == T90)
    check('   the game is carried on the capture row',
          st.evidence['game_id'] == '2026_01_SF_LA')

    # 4. parse, both clubs present
    pa = INA.parse(raw.decode(), ['SF', 'LA'])
    if not check('2. both clubs parse', pa.state is State.PASS, pa.code):
        return

    # 5. player identity -- deterministic, with the unknown NAMED
    rs = INA.resolve(pa.value, ROSTER)
    if not check('3. identity resolves', rs.state is State.PASS, rs.code):
        return
    check('   the three SF starters map',
          sorted(rs.value['SF']) == ['00-0010001', '00-0010002', '00-0010003'],
          str(rs.value['SF']))
    check('   the unknown player is RECORDED, not silently mapped',
          rs.evidence['n_unmapped'] >= 1 and
          any('Ghost Player' in u for u in rs.evidence['unmapped']),
          str(rs.evidence['unmapped']))
    check('   and he reaches no inactive set',
          not any(p.startswith('00-009') for v in rs.value.values() for p in v))

    # 6. both-team completeness
    se = INA.sets(rs.value, ROSTER, ['SF', 'LA'], retrieved_at=T90,
                  kickoff_utc=KO, game_id='2026_01_SF_LA')
    if not check('4. both clubs present -> COMPLETE',
                 se.state is State.PASS and se.code == INA.COMPLETE, se.code):
        return
    check('   SF has three inactive, LA one',
          se.evidence['n_inactive_by_team'] == {'SF': 3, 'LA': 1},
          str(se.evidence['n_inactive_by_team']))
    # OWNER RULING item 4: absence from the list is not a positive claim.
    st_map = se.value['states']
    check('   every listed player is OFFICIAL_INACTIVE',
          all(st_map[p] == INA.OFFICIAL_INACTIVE for p in se.value['inactive']))
    check('   and NO player is designated GAME_ACTIVE by this source',
          not any(v == INA.GAME_ACTIVE for v in st_map.values()),
          str({k: v for k, v in st_map.items() if v == INA.GAME_ACTIVE}))
    check('   the unlisted keep only ROSTER_ACTIVE',
          all(st_map[p] == INA.ROSTER_ACTIVE
              for p in se.value['not_listed_inactive']))
    check('   and the list is timed before kickoff',
          se.evidence['hours_before_kickoff'] == 1.5,
          str(se.evidence['hours_before_kickoff']))

    # 7. appearance override
    draws = {p: np.ones(200, dtype=np.int64) for p in ROSTER}
    ap = INA.apply_to_appearance(draws, list(se.value['inactive']))
    if not check('5. the override applies', ap.state is State.PASS, ap.code):
        return
    for pid, what in (('00-0010001', 'WR'), ('00-0010002', 'RB'),
                      ('00-0010003', 'TE')):
        check(f'   the inactive {what} appears in NO draw',
              int(np.asarray(ap.value[pid]).sum()) == 0)
    check('   the SF backups are bit-identical',
          all(np.array_equal(np.asarray(ap.value[p]), draws[p])
              for p in ('00-0010004', '00-0010005')))
    la_live = [p for p in ROSTER if p.startswith('00-002')
               and p not in se.value['inactive']]
    check('   every LA player not on the list is bit-identical',
          all(np.array_equal(np.asarray(ap.value[p]), draws[p])
              for p in la_live), str(la_live))

    # 8. opportunity allocation refuses to give an inactive player share
    n, m = 3, 8
    A = np.ones((n, m))
    A[0] = 0.0                                  # the inactive WR
    share = np.zeros((n, m))
    share[1] = share[2] = 0.5
    tv = np.full((1, m), 30.0)
    o = ACC.reconcile_nonqb(share, np.zeros((1, m)), tv,
                            share * tv[0][None, :], A,
                            np.array([0]), np.array([n]))
    check('6. zero appearance with zero share reconciles',
          o.state is State.PASS, f'{o.state}[{o.code}]')
    bad = share.copy()
    bad[0] = 0.2
    bad[1] = bad[2] = 0.4
    o2 = ACC.reconcile_nonqb(bad, np.zeros((1, m)), tv,
                             bad * tv[0][None, :], A,
                             np.array([0]), np.array([n]))
    check('   an inactive player holding share is REFUSED',
          o2.state is not State.PASS, f'{o2.state}[{o2.code}]')

    # 9. the live root is untouched
    check('7. the live manifest is byte-identical', _live_fingerprint() == before,
          'the drill wrote into the live root')
    check('   and the synthetic blob is under the synthetic root only',
          (root / st.value).exists() and
          not (LIVE / 'vintage' / pathlib.Path(st.value).name).exists())


def test_an_ambiguous_identity_refuses_the_whole_list():
    root = pathlib.Path(tempfile.mkdtemp(prefix='inactives-drill-'))
    before = _live_fingerprint()
    st = INA.store(DOC_AMBIGUOUS.encode(), retrieved_at=T90,
                   source_url='u', game_id='2026_01_SF_LA', root=root)
    pa = INA.parse(DOC_AMBIGUOUS, ['SF', 'LA'])
    rs = INA.resolve(pa.value, ROSTER)
    check('two rostered players share one name -> FAIL',
          rs.state is State.FAIL and
          rs.code == 'INACTIVES_IDENTITY_AMBIGUOUS', f'{rs.state}[{rs.code}]')
    check('  and no partial inactive set is produced', rs.value is None,
          str(rs.value)[:80])
    check('  the live root is still untouched', _live_fingerprint() == before)


def test_a_one_team_list_refuses_the_complete_label():
    pa = INA.parse(DOC_ONE_TEAM, ['SF', 'LA'])
    check('a document naming one club defers at parse',
          pa.state is State.DEFERRED and
          pa.code == 'INACTIVES_TEAM_NOT_REPRESENTED', pa.code)
    se = INA.sets({'SF': ['00-0010001'], 'LA': []}, ROSTER, ['SF', 'LA'],
                  retrieved_at=T90, kickoff_utc=KO, game_id='2026_01_SF_LA')
    check('  and an empty club list refuses COMPLETE',
          se.state is State.DEFERRED and se.code == INA.INCOMPLETE, se.code)
    check('  naming the club that is missing',
          se.evidence['teams_without_a_list'] == ['LA'])


def test_the_pre_inactives_artifacts_are_immutable():
    """Nothing in this drill may alter a board already sealed tonight."""
    base = LIVE / 'research' / 'live' / '2026_01_SF_LA'
    if not base.exists():
        print('  ..   no pre-inactives boards sealed yet; skipped')
        return
    seen = 0
    for art in sorted(base.glob('pre_inactives_*/forecast_artifact.json')):
        a = json.loads(art.read_text())
        seen += 1
        check(f'  {art.parent.name}: still promoted=False',
              a.get('promoted') is False)
        check(f'    and still labelled {a.get("model_configuration")}',
              a.get('model_configuration', '').startswith('V1_CANDIDATE'))
        check('    and carries no post-inactives claim',
              INA.COMPLETE not in json.dumps(a))
    check('every sealed pre-inactives board was inspected', seen == 5, str(seen))


# The fixture is a REAL nfl.com capture that lives in this repository, taken
# 2026-09-08 while egress to nfl.com still worked. Its main content reads
# "Please check back soon for NFL Inactive Reports for this Season" -- a real
# fetch of a real page carrying no list at all. Every synthetic document in
# this module was written by me and shares my assumptions; this one does not,
# and it is the only adversarial input here that the site actually served.
REAL_EMPTY_PAGE = (LIVE / 'vintage'
                   / 'official_inactives.88a19528350ea23f.html.gz')


def _real_empty_page():
    import gzip
    return gzip.open(REAL_EMPTY_PAGE, 'rb').read().decode('utf-8', 'replace')


def test_the_real_empty_page_is_refused_under_every_team_spelling():
    """The defect this fixture caught, and the reason it is now a fixture.

    Before the guards, this page parsed to State.PASS with 311 "names" --
    'NFL Week', 'Lumen Field', 'Americano NFL', 'The Seattle Seahawks' --
    swept out of the navigation and the news tray, every one of them assigned
    to a single club and none to the other. The team-token spelling was all
    that stood between that and an inactive list fabricated out of headlines.
    """
    if not REAL_EMPTY_PAGE.exists():
        print('  ..   real capture fixture absent; skipped')
        return
    html = _real_empty_page()
    check('the fixture really is the empty state, not a populated list',
          'check back soon' in html.lower())
    check('and it really does carry the news promos that fooled the parser',
          'Nacua' in html and 'Kittle' in html)
    for teams in (['SF', 'LA'], ['49ers', 'Rams'],
                  ['San Francisco', 'Los Angeles']):
        o = INA.parse(html, teams)
        check(f'  {teams} -> refused, not parsed', o.state is not State.PASS,
              f'{o.state.name} {o.code}')
        check('    and no names escaped', not o.value)


def test_each_guard_is_load_bearing_on_its_own():
    """A guard masked by an earlier guard is not evidence that it works.

    Guard 1 is defeated deliberately so guards 2 and 3 are exercised on the
    real document rather than on my idea of one.
    """
    if not REAL_EMPTY_PAGE.exists():
        print('  ..   real capture fixture absent; skipped')
        return
    import re as _re
    html = _re.sub(r'(?i)check back soon', 'XXXX', _real_empty_page())

    o = INA.parse(html, ['49ers', 'Rams'])
    check('guard 1 defeated: a later guard still refuses',
          o.state is not State.PASS, f'{o.state.name} {o.code}')
    check('  and it is the empty-club guard that fires',
          o.code == 'INACTIVES_TEAM_HAS_NO_NAMES', o.code)
    owed = (o.evidence or {}).get('owed', {})
    check('  which names the club that got nothing',
          owed.get('teams_without_names') == ['49ers'], str(owed.get(
              'teams_without_names')))
    check('  and the label filter did real work',
          (owed.get('n_rejected_as_labels') or {}).get('Rams', 0) > 100,
          str(owed.get('n_rejected_as_labels')))

    # Guards 1 and 2 both defeated: the size ceiling must still hold.
    many = ''.join(f'<li>Alpha Player{chr(65 + i)}</li>' for i in range(20))
    doc = f'<html><body><h2>SF</h2><ul>{many}</ul>' \
          f'<h2>LA</h2><ul>{many}</ul></body></html>'
    o3 = INA.parse(doc, ['SF', 'LA'])
    check('guards 1 and 2 defeated: the size ceiling refuses',
          o3.code == 'INACTIVES_BLOCK_IMPLAUSIBLY_LARGE', o3.code)

    # And the ceiling must not be so tight that a real list trips it.
    six = ''.join(f'<li>Alpha Player{chr(65 + i)}</li>' for i in range(6))
    doc2 = f'<html><body><h2>SF</h2><ul>{six}</ul>' \
           f'<h2>LA</h2><ul>{six}</ul></body></html>'
    o4 = INA.parse(doc2, ['SF', 'LA'])
    check('a realistic 6-and-6 list still passes',
          o4.state is State.PASS and {t: len(v) for t, v in o4.value.items()}
          == {'SF': 6, 'LA': 6}, f'{o4.state.name} {o4.code}')


def test_club_and_chrome_labels_are_not_people():
    """The exact strings the real page produced, asserted one by one."""
    for label in ('The Seattle Seahawks', 'New England Patriots', 'NFL Week',
                  'Lumen Field', 'Americano NFL', 'San Francisco',
                  'Los Angeles Rams', 'The New York Giants'):
        check(f'  {label!r} is not read as a player',
              not INA._plausible_person(label))
    # These are the ones that matter. A token-level club filter rejected
    # every one of them, including the drill's own "Rams Runner", and would
    # have silently dropped a real inactive whose surname is a club word.
    for person in ('Wide Starter', 'Brock Purdy', "De'Von Achane",
                   'Amon-Ra St. Brown', 'Puka Nacua', 'Rams Runner',
                   'Justin Houston', 'A.J. Green', 'Dwayne Washington'):
        check(f'  {person!r} still is', INA._plausible_person(person))


def test_a_supplied_name_must_come_from_the_stored_bytes():
    """The operator path, and the reason it cannot become a back door.

    parse() has never seen a populated inactives page, so it may refuse bytes
    that plainly carry both lists. verify_supplied_names() is the way through,
    and its whole discipline is one rule: a name that does not occur verbatim
    in the stored official document is refused by code. That is what stops a
    reporter's expectation or a remembered list from being typed in -- to pass
    this check a name must already be the league's own words.
    """
    if not REAL_EMPTY_PAGE.exists():
        print('  ..   real capture fixture absent; skipped')
        return
    html = _real_empty_page()

    # 'George Kittle' and 'Puka Nacua' really are in this document -- in its
    # news promos. That is exactly why the substring check is necessary but
    # NOT sufficient on its own, and why it is paired with a real fetch of a
    # real inactives page rather than any page at all.
    ok = INA.verify_supplied_names(html, {'SF': ['George Kittle'],
                                          'LA': ['Puka Nacua']})
    check('names that occur in the document are accepted',
          ok.state is State.PASS, f'{ok.state.name} {ok.code}')
    check('  and the artifact says the segmentation was assisted',
          ok.evidence.get('segmentation')
          == 'operator_supplied_verified_against_bytes',
          str(ok.evidence.get('segmentation')))

    bad = INA.verify_supplied_names(html, {'SF': ['George Kittle'],
                                           'LA': ['Fabricated Person']})
    check('a name absent from the document is refused',
          bad.state is State.FAIL, f'{bad.state.name} {bad.code}')
    check('  under a named code',
          bad.code == 'INACTIVES_SUPPLIED_NAME_NOT_IN_BYTES', bad.code)
    check('  and it names the offending entry',
          (bad.evidence.get('owed') or {}).get('names_not_in_document')
          == {'LA': ['Fabricated Person']})
    check('  and NOTHING is accepted from a partly-bad call',
          not bad.value, str(bad.value))

    empty = INA.verify_supplied_names(html, {'SF': ['George Kittle'],
                                             'LA': []})
    check('a club supplied with no names is refused',
          empty.code == 'INACTIVES_SUPPLIED_LIST_INCOMPLETE', empty.code)

    big = INA.verify_supplied_names(
        html, {'SF': ['George Kittle'], 'LA': ['Puka Nacua'] * 1})
    check('a plausible pair still passes', big.state is State.PASS, big.code)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
