"""A future legitimate T-90 capture would satisfy the frozen predicate.

Proved SYNTHETICALLY: a fabricated plan with fabricated kickoffs, an injected
`declared_at` and an injected `retrieved_at`. No wall clock, no network, no
live schedule -- so this proves the PREDICATE is satisfiable and the plumbing
carries the anchor, not that any particular real run happened.

Nothing here backfills Week 1 or grants retroactive credit: the fixture games
are invented ids that appear in no plan and no manifest.

The frozen rule is not touched. What is proved is that a capture which is
in-window, anchored, from an authorised source and attributed to the game is
ACCEPTED, and that each of those four properties is individually necessary.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.capture.execution import declare, eligibility          # noqa: E402
from nfl.capture.schedule import CaptureDue, WINDOWS             # noqa: E402
from nfl.capture.execution import ANCHORED_WORKFLOW              # noqa: E402

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


GAME = '2099_09_AAA_BBB'          # invented: in no plan, no manifest
KICK = dt.datetime(2099, 9, 20, 0, 20, tzinfo=dt.timezone.utc)
# The DUE time and the window come from the frozen WINDOWS table, not from
# numbers typed here -- a fixture that invented its own window would prove
# nothing about the rule the real capture must satisfy.
DUE = KICK - dt.timedelta(minutes=90)
_LO, _HI = WINDOWS['inactives']
W_START, W_END = DUE + _LO, DUE + _HI
IN_WINDOW = W_START + (W_END - W_START) / 2


def _plan():
    """One inactives obligation, built with the planner's own type."""
    return [CaptureDue(game_id=GAME, label='inactives', due_utc=DUE,
                       kind='inactives', confirmed=True,
                       note='synthetic fixture', kickoff_utc=KICK)]


# The executor identity a REAL scheduled anchored run presents. Injected
# explicitly, and named as an injection: run locally the basis is
# LOCAL_INVOCATION, which correctly cannot discharge, so without this the
# fixture would only re-prove that local runs are refused. The workflow name is
# read from the frozen constant, not typed here, so a rename breaks this test
# instead of silently making it vacuous.
ANCHORED_IDENTITY = {
    'workflow': ANCHORED_WORKFLOW, 'event_name': 'schedule',
    'is_github_actions': True, 'run_id': '0000000000',
    'run_attempt': '1', 'run_number': '1',
    'repository': '94924676jp-a11y/Nfl', 'ref': 'refs/heads/main',
    'sha': '0' * 40, 'runner_os': 'Linux',
}


def _decl(at=IN_WINDOW, identity=None, **kw):
    return declare(_plan(), declared_at=at, identity=identity
                   if identity is not None else ANCHORED_IDENTITY,
                   plan_snapshot='schedules.synthetic.csv.gz', **kw)


def _n_eligible(e) -> int:
    """The contract's own answer: how many declared targets these bytes may
    discharge. Read from `n_eligible`/`targets[].eligible`, which is the shape
    `eligibility` actually returns -- an assertion against a field that does
    not exist would pass or fail for the wrong reason."""
    n = e.get('n_eligible')
    if isinstance(n, int):
        return n
    return sum(1 for t in (e.get('targets') or []) if t.get('eligible'))


def test_the_declaration_carries_the_anchored_target():
    o = _decl()
    assert check('declaration succeeds', o.state.name == 'PASS',
                 f'{o.code}: {o.detail[:150]}')
    d = o.value
    assert check('  it declares exactly the one open target',
                 len(d.get('targets', [])) == 1, str(len(d.get('targets', []))))
    t = d['targets'][0]
    assert check('  carrying the game id', t['game_id'] == GAME, t.get('game_id'))
    assert check('  and the kind', t['kind'] == 'inactives', t.get('kind'))
    assert check('  and the window', t['window_start_utc'][:16] ==
                 W_START.isoformat()[:16], t.get('window_start_utc'))
    assert check('  declared BEFORE any fetch',
                 d.get('declared_before_fetch') is True)
    assert check('  and the plan snapshot is named',
                 d.get('plan_snapshot') == 'schedules.synthetic.csv.gz')


def test_a_legitimate_in_window_capture_is_eligible_to_discharge():
    """The whole point: this is what the next real window must produce."""
    d = _decl().value
    e = eligibility(d, source='official_inactives', capture_state='PASS',
                    retrieved_at=IN_WINDOW.isoformat(),
                    sha256='a' * 64,
                    blob_path='nfl/vintage/official_inactives.dead.html.gz',
                    provenance_valid=True)
    assert check('an in-window authorised game-attributed capture is eligible',
                 _n_eligible(e) == 1,
                 f'SYNTHETIC_LEGITIMATE_CAPTURE_REFUSED: {e}')
    t = (e.get('targets') or [{}])[0]
    assert check('  with no refusals recorded against it',
                 not t.get('refusals'), str(t.get('refusals')))
    assert check('  and it names the game it may discharge',
                 t.get('game_id') == GAME, str(t.get('game_id')))
    assert check('  and the kind', t.get('kind') == 'inactives')
    assert check('  and the basis can discharge',
                 d.get('basis_can_discharge') is True, str(d.get('basis')))


def test_out_of_window_cannot_discharge():
    d = _decl().value
    late = (W_END + dt.timedelta(minutes=5)).isoformat()
    e = eligibility(d, source='official_inactives', capture_state='PASS',
                    retrieved_at=late, sha256='a' * 64,
                    blob_path='nfl/vintage/x.html.gz', provenance_valid=True)
    assert check('a capture after the window closes cannot discharge',
                 _n_eligible(e) == 0, f'OUT_OF_WINDOW_ACCEPTED: {e}')


def test_a_sweep_basis_cannot_discharge():
    """A periodic run that happens to land inside a window is not an anchored
    capture. This is the substitution the frozen rule exists to forbid."""
    o = declare([], declared_at=IN_WINDOW, identity=ANCHORED_IDENTITY,
                plan_snapshot='schedules.synthetic.csv.gz')
    d = o.value if o.state.name == 'PASS' else {}
    assert check('a declaration with no open target is a sweep',
                 d.get('basis') != 'SCHEDULED_WINDOW_ANCHORED',
                 str(d.get('basis')))
    assert check('  and a sweep basis cannot discharge',
                 d.get('basis_can_discharge') is not True,
                 str(d.get('basis_can_discharge')))


def test_a_failed_capture_cannot_discharge():
    d = _decl().value
    e = eligibility(d, source='official_inactives', capture_state='FAIL',
                    retrieved_at=IN_WINDOW.isoformat(), sha256=None,
                    blob_path=None, provenance_valid=False)
    assert check('a FAILed source cannot discharge',
                 _n_eligible(e) == 0, f'FAILED_CAPTURE_ACCEPTED: {e}')


def test_an_unauthorised_source_cannot_discharge():
    d = _decl().value
    e = eligibility(d, source='some_blog', capture_state='PASS',
                    retrieved_at=IN_WINDOW.isoformat(), sha256='a' * 64,
                    blob_path='nfl/vintage/x.html.gz', provenance_valid=True)
    assert check('an unauthorised source cannot discharge',
                 _n_eligible(e) == 0, f'UNAUTHORISED_SOURCE_ACCEPTED: {e}')


def test_a_wrong_kind_cannot_discharge_the_inactives_obligation():
    """A practice capture may not stand in for inactives."""
    d = _decl().value
    e = eligibility(d, source='official_injury_report', capture_state='PASS',
                    retrieved_at=IN_WINDOW.isoformat(), sha256='a' * 64,
                    blob_path='nfl/vintage/x.html.gz', provenance_valid=True)
    kinds = {str(t.get('kind')) for t in (e.get('targets') or [])
             if t.get('eligible')}
    assert check('a practice-kind source does not discharge inactives',
                 'inactives' not in kinds, f'WRONG_KIND_CREDITED: {e}')
    assert check('  and nothing at all is eligible from it',
                 _n_eligible(e) == 0, str(e.get('n_eligible')))


def test_the_synthetic_fixture_touches_no_real_obligation():
    """No backfill, no retroactive credit."""
    man = os.path.join(_ROOT, 'nfl', 'vintage_manifest.jsonl')
    body = open(man).read() if os.path.exists(man) else ''
    assert check('the fixture game appears in no manifest row',
                 GAME not in body, 'SYNTHETIC_LEAKED_INTO_MANIFEST')
    assert check('  and its season is far outside any real plan',
                 GAME.startswith('2099'))


def test_a_manual_dispatch_of_the_anchored_workflow_cannot_discharge():
    """Same workflow, event_name workflow_dispatch. The frozen rule credits the
    SCHEDULE, not the file that ran."""
    ident = dict(ANCHORED_IDENTITY, event_name='workflow_dispatch')
    d = _decl(identity=ident).value
    assert check('a hand-dispatched anchored run is not the anchored basis',
                 d.get('basis') != 'SCHEDULED_WINDOW_ANCHORED',
                 str(d.get('basis')))
    assert check('  and it cannot discharge',
                 d.get('basis_can_discharge') is not True,
                 str(d.get('basis_can_discharge')))


def test_a_local_run_cannot_discharge():
    d = _decl(identity=dict(ANCHORED_IDENTITY, is_github_actions=False)).value
    assert check('a local invocation cannot discharge',
                 d.get('basis_can_discharge') is not True,
                 str(d.get('basis')))
