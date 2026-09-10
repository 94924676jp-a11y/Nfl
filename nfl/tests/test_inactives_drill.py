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


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
